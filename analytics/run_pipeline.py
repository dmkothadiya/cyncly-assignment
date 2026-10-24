from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_XLSX = ROOT / 'data' / 'source' / 'Case Study - DORA Metrics Data.xlsx'
WORKBOOK_PATH = ROOT / 'docs' / 'Case Study - DORA Metrics Data.xlsx'
BRONZE_DIR = ROOT / 'analytics' / 'bronze'
SILVER_DIR = ROOT / 'analytics' / 'silver'
GOLD_DIR = ROOT / 'analytics' / 'gold'
QUALITY_DIR = ROOT / 'analytics' / 'quality-checks'
DASHBOARD_DIR = ROOT / 'analytics' / 'dashboard'


def ensure_source_copy() -> None:
    SOURCE_XLSX.parent.mkdir(parents=True, exist_ok=True)
    if not SOURCE_XLSX.exists():
        SOURCE_XLSX.write_bytes(WORKBOOK_PATH.read_bytes())


def read_all_sheets(path: Path) -> dict[str, pd.DataFrame]:
    sheet_names = pd.ExcelFile(path).sheet_names
    return {
        sheet_name: pd.read_excel(path, sheet_name=sheet_name, dtype=str)
        for sheet_name in sheet_names
    }


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def bronze_step() -> dict[str, pd.DataFrame]:
    raw = read_all_sheets(WORKBOOK_PATH)
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    for sheet_name, df in raw.items():
        write_csv(df, BRONZE_DIR / f'{sheet_name}.csv')

    metadata = {
        'source_excel': WORKBOOK_PATH.relative_to(ROOT).as_posix(),
        'source_rows': {name: len(df) for name, df in raw.items()},
        'source_columns': {name: list(df.columns) for name, df in raw.items()},
        'generated_at_utc': pd.Timestamp.now(tz='UTC').isoformat(),
    }
    (BRONZE_DIR / 'ingestion_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return raw


def normalize_date_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors='coerce', utc=True)
    return result


def silver_step(raw_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    silver_tables: dict[str, pd.DataFrame] = {}
    rejected_rows: list[dict[str, object]] = []

    for sheet_name, raw_df in raw_tables.items():
        working = raw_df.copy()
        if sheet_name == 'commits':
            working = normalize_date_columns(working, ['author_date', 'committer_date', 'ingestion_datetime'])
            working['change_count'] = pd.to_numeric(working['change_count'], errors='coerce')
            required = ['commit_id', 'project_sk', 'repository_sk', 'author_date']
        elif sheet_name == 'builds':
            working = normalize_date_columns(working, ['pipeline_start_time', 'pipeline_end_time', 'ingestion_datetime'])
            required = ['build_id', 'project_sk', 'pipeline_start_time', 'pipeline_end_time']
        elif sheet_name == 'incidents':
            working = normalize_date_columns(
                working,
                [
                    'incident_started_datetime',
                    'incident_reported_customersupport_datetime',
                    'incident_reported_engineering_datetime',
                    'investigation_started_datetime',
                    'incident_resolved_datetime',
                    'ingestion_datetime',
                ],
            )
            working['caused_by_deployment'] = pd.to_numeric(working['caused_by_deployment'], errors='coerce').astype('Int64')
            required = ['workitem_id', 'area_path', 'incident_started_datetime', 'incident_resolved_datetime']
        elif sheet_name == 'projects':
            required = ['project_id', 'project_name']
        else:
            required = []

        if required:
            missing_mask = working[required].isna().any(axis=1)
            if missing_mask.any():
                rejected_rows.extend(working.loc[missing_mask].to_dict(orient='records'))
                working = working.loc[~missing_mask].copy()

        working = working.drop_duplicates(subset=[column for column in working.columns if 'id' in column.lower() or column in {'project_sk', 'project_id', 'repository_sk'}], keep='first')
        silver_tables[sheet_name] = working
        write_csv(working, SILVER_DIR / f'{sheet_name}.csv')

    if rejected_rows:
        (SILVER_DIR / 'rejected_rows.json').write_text(json.dumps(rejected_rows, default=str, indent=2), encoding='utf-8')

    quality_summary = {
        'rows_processed': {name: len(df) for name, df in raw_tables.items()},
        'rows_validated': {name: len(df) for name, df in silver_tables.items()},
        'rejected_rows': len(rejected_rows),
        'checks': ['required_columns_present', 'missing_values_flagged', 'duplicate_records_removed', 'dates_normalized'],
    }
    (QUALITY_DIR / 'silver_quality_summary.json').write_text(json.dumps(quality_summary, indent=2), encoding='utf-8')
    return silver_tables


def gold_step(silver_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    projects = silver_tables.get('projects', pd.DataFrame()).copy()
    builds = silver_tables.get('builds', pd.DataFrame()).copy()
    incidents = silver_tables.get('incidents', pd.DataFrame()).copy()

    if projects.empty or builds.empty or incidents.empty:
        raise ValueError('Silver layer must contain non-empty projects, builds, and incidents tables.')

    builds['reporting_month'] = (
        pd.to_datetime(builds['pipeline_end_time'], utc=True)
        .dt.tz_localize(None)
        .dt.to_period('M')
        .astype(str)
    )
    projects['project_id'] = projects['project_id'].astype(str)
    builds['project_sk'] = builds['project_sk'].astype(str)
    project_builds = (
        builds.groupby(['project_sk', 'reporting_month'], as_index=False)
        .agg(deployment_count=('build_id', 'nunique'))
    )

    project_names = projects.rename(columns={'project_id': 'project_sk', 'project_name': 'project_name'})
    project_builds = project_builds.merge(project_names[['project_sk', 'project_name']], on='project_sk', how='left')

    incidents['reporting_month'] = (
        pd.to_datetime(incidents['incident_started_datetime'], utc=True)
        .dt.tz_localize(None)
        .dt.to_period('M')
        .astype(str)
    )
    incidents['project_reference'] = (
        incidents['area_path']
        .str.replace('Product Management\\Demo Projects\\', '', regex=False)
        .str.replace('Demo Project', 'Project', regex=False)
    )
    incident_month = (
        incidents.groupby(['project_reference', 'reporting_month'], as_index=False)
        .agg(
            total_incidents=('workitem_id', 'count'),
            deployment_related_incidents=('caused_by_deployment', lambda values: int((values == 1).sum())),
        )
    )
    incident_month = incident_month.rename(columns={'project_reference': 'project_name'})

    working = project_builds.merge(incident_month, left_on=['project_name', 'reporting_month'], right_on=['project_name', 'reporting_month'], how='left')
    working['total_incidents'] = working['total_incidents'].fillna(0).astype(int)
    working['deployment_related_incidents'] = working['deployment_related_incidents'].fillna(0).astype(int)
    working['change_failure_rate'] = working.apply(
        lambda row: (row['deployment_related_incidents'] / row['deployment_count']) if row['deployment_count'] else 0.0,
        axis=1,
    )

    incident_durations = (
        incidents.assign(restore_hours=(incidents['incident_resolved_datetime'] - incidents['incident_started_datetime']).dt.total_seconds() / 3600)
        .groupby(['project_reference', 'reporting_month'], as_index=False)
        .agg(mean_time_to_restore_hours=('restore_hours', 'mean'))
        .rename(columns={'project_reference': 'project_name'})
    )
    working = working.merge(incident_durations, on=['project_name', 'reporting_month'], how='left')
    if 'mean_time_to_restore_hours' not in working.columns:
        working['mean_time_to_restore_hours'] = 0.0
    working['mean_time_to_restore_hours'] = working['mean_time_to_restore_hours'].fillna(0.0)
    working['lead_time_for_changes_hours'] = None
    working['data_quality_status'] = 'limited'
    working['metric_notes'] = 'Deployment frequency and change failure rate derived from the case-study workbook; lead time for changes unavailable because the source workbook does not provide a reliable commit-to-deployment join.'

    write_csv(working, GOLD_DIR / 'dora_metrics.csv')
    dashboard_summary = working[['project_name', 'reporting_month', 'deployment_count', 'change_failure_rate', 'mean_time_to_restore_hours']].copy()
    write_csv(dashboard_summary, DASHBOARD_DIR / 'dora_dashboard_summary.csv')
    (DASHBOARD_DIR / 'dora_dashboard_summary.txt').write_text(
        dashboard_summary.to_string(index=False),
        encoding='utf-8',
    )
    (QUALITY_DIR / 'gold_quality_summary.json').write_text(json.dumps({
        'metrics_generated': list(working.columns),
        'rows': len(working),
        'data_quality_status_counts': working['data_quality_status'].value_counts().to_dict(),
        'lead_time_for_changes_unavailable': True,
    }, indent=2), encoding='utf-8')
    return working


def main() -> None:
    ensure_source_copy()
    raw_tables = bronze_step()
    silver_tables = silver_step(raw_tables)
    gold_step(silver_tables)
    print('Bronze, Silver, Gold, and quality artifacts generated in analytics/')


if __name__ == '__main__':
    main()
