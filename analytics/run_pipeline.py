"""Bronze -> Silver -> Gold pipeline for the supplied DORA case-study workbook.

Layer contract
--------------
Bronze  Raw sheet copies, untyped, plus ingestion metadata (hash, counts, timestamp).
Silver  Typed, deduplicated, validated. Rejected rows are recorded with a reason
        and without personal data.
Gold    Facts, dimensions, a documented reporting grain, and the DORA metric table.

Reporting grain for the metric table is project_sk x reporting_month.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "docs" / "Case Study - DORA Metrics Data.xlsx"
BRONZE = ROOT / "analytics" / "bronze"
SILVER = ROOT / "analytics" / "silver"
GOLD = ROOT / "analytics" / "gold"
QUALITY = ROOT / "analytics" / "quality-checks"
PII_COLUMNS = {"author_name", "author_email", "committer_name", "committer_email"}


def utc(series: pd.Series) -> pd.Series:
    """Parse timestamps whose text mixes precisions.

    Without format="mixed" pandas infers a single format from the first non-null
    value and coerces every row that differs to NaT - the source column holds both
    "2024-09-04 15:01:48" and "2024-09-04 15:01:48.047", so whichever precision does
    not match the first row would be dropped as if it were missing data.
    """
    return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")


def month_of(series: pd.Series) -> pd.Series:
    return (
        pd.to_datetime(series, utc=True, format="mixed")
        .dt.tz_localize(None)
        .dt.to_period("M")
        .astype(str)
    )


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# --------------------------------------------------------------------------- bronze
def bronze() -> dict[str, pd.DataFrame]:
    BRONZE.mkdir(parents=True, exist_ok=True)
    sheet_names = pd.ExcelFile(WORKBOOK).sheet_names
    raw = {name: pd.read_excel(WORKBOOK, sheet_name=name, dtype=str) for name in sheet_names}
    for name, df in raw.items():
        write(df, BRONZE / f"{name}.csv")

    digest = hashlib.sha256()
    with WORKBOOK.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    metadata = {
        "source_workbook": WORKBOOK.relative_to(ROOT).as_posix(),
        "source_sha256": digest.hexdigest(),
        "ingested_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "granularity": "one row per source row, values preserved as text",
        "tables": {
            name: {"rows": int(len(df)), "columns": list(df.columns)}
            for name, df in raw.items()
        },
    }
    (BRONZE / "ingestion_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return raw


# --------------------------------------------------------------------------- silver
def silver(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    SILVER.mkdir(parents=True, exist_ok=True)
    QUALITY.mkdir(parents=True, exist_ok=True)
    rejects: list[dict[str, object]] = []
    dedupe: dict[str, dict[str, int]] = {}

    def reject(table: str, frame: pd.DataFrame, reason: str, key: str) -> None:
        for value in frame[key].astype(str).tolist():
            rejects.append({"table": table, "record_key": value, "reason": reason})

    def keep_latest(table: str, frame: pd.DataFrame, key: str) -> pd.DataFrame:
        """Duplicate keys are re-reported snapshots; the latest ingestion wins."""
        ordered = frame.assign(
            _ingested=utc(frame["ingestion_datetime"])
        ).sort_values("_ingested", na_position="first")
        before = len(ordered)
        kept = ordered.drop_duplicates(subset=[key], keep="last").drop(columns=["_ingested"])
        dedupe[table] = {
            "rows_in": before,
            "rows_out": len(kept),
            "duplicate_snapshots_resolved": before - len(kept),
        }
        return kept

    projects = raw["projects"].copy().apply(lambda c: c.astype(str).str.strip())
    bad = projects[
        projects["project_id"].isin(["", "nan"]) | projects["project_name"].isin(["", "nan"])
    ]
    reject("projects", bad, "missing_required_key", "project_id")
    projects = projects.drop(bad.index).drop_duplicates(subset=["project_id"], keep="last")

    builds = raw["builds"].copy()
    builds["pipeline_start_time"] = utc(builds["pipeline_start_time"])
    builds["pipeline_end_time"] = utc(builds["pipeline_end_time"])
    builds["project_sk"] = builds["project_sk"].astype(str).str.strip()
    builds["build_id"] = builds["build_id"].astype(str).str.strip()
    missing = builds[
        builds[["build_id", "project_sk", "pipeline_start_time", "pipeline_end_time"]].isna().any(axis=1)
    ]
    reject("builds", missing, "missing_required_field", "build_id")
    builds = builds.drop(missing.index)
    inverted = builds[builds["pipeline_end_time"] < builds["pipeline_start_time"]]
    reject("builds", inverted, "end_before_start", "build_id")
    builds = builds.drop(inverted.index)
    builds = keep_latest("builds", builds, "build_id")
    builds["duration_minutes"] = (
        (builds["pipeline_end_time"] - builds["pipeline_start_time"]).dt.total_seconds() / 60
    ).round(2)

    commits = raw["commits"].copy()
    commits["author_date"] = utc(commits["author_date"])
    commits["committer_date"] = utc(commits["committer_date"])
    commits["build_sk"] = commits["build_sk"].astype(str).str.strip()
    commits["commit_id"] = commits["commit_id"].astype(str).str.strip()
    commits["project_sk"] = commits["project_sk"].astype(str).str.strip()
    commits["change_count"] = pd.to_numeric(commits["change_count"], errors="coerce")
    missing = commits[commits[["commit_id", "project_sk", "author_date"]].isna().any(axis=1)]
    reject("commits", missing, "missing_required_field", "commit_id")
    commits = commits.drop(missing.index)

    before = len(commits)
    commits = (
        commits.assign(_ingested=utc(commits["ingestion_datetime"]))
        .sort_values("_ingested", na_position="first")
        .drop_duplicates(subset=["commit_id", "build_sk"], keep="last")
        .drop(columns=["_ingested"])
    )
    dedupe["commits"] = {
        "rows_in": before,
        "rows_out": len(commits),
        "grain": "commit_id x build_sk (commit-to-build association)",
        "unique_commits": int(commits["commit_id"].nunique()),
        "duplicate_link_rows_resolved": before - len(commits),
    }

    incidents = raw["incidents"].copy()
    incidents["incident_started_datetime"] = utc(incidents["incident_started_datetime"])
    incidents["incident_resolved_datetime"] = utc(incidents["incident_resolved_datetime"])
    incidents["caused_by_deployment"] = (
        pd.to_numeric(incidents["caused_by_deployment"], errors="coerce").fillna(0).astype(int)
    )
    incidents["workitem_id"] = incidents["workitem_id"].astype(str).str.strip()
    incidents["project_name"] = (
        incidents["area_path"].astype(str)
        .str.replace(r"^.*\\", "", regex=True)
        .str.replace("Demo Project", "Project", regex=False)
        .str.strip()
    )
    missing = incidents[
        incidents[
            ["workitem_id", "incident_started_datetime", "incident_resolved_datetime"]
        ].isna().any(axis=1)
    ]
    reject("incidents", missing, "missing_required_field", "workitem_id")
    incidents = incidents.drop(missing.index)
    inverted = incidents[
        incidents["incident_resolved_datetime"] < incidents["incident_started_datetime"]
    ]
    reject("incidents", inverted, "resolved_before_started", "workitem_id")
    incidents = incidents.drop(inverted.index)
    incidents = keep_latest("incidents", incidents, "workitem_id")
    incidents["restore_hours"] = (
        (incidents["incident_resolved_datetime"] - incidents["incident_started_datetime"])
        .dt.total_seconds() / 3600
    ).round(2)

    tables = {"projects": projects, "builds": builds, "commits": commits, "incidents": incidents}
    for name, df in tables.items():
        tables[name] = df[[c for c in df.columns if c not in PII_COLUMNS]]

    # A build that completed before a commit was authored cannot contain it: the
    # association is impossible, so it is rejected rather than silently published.
    links = commits.merge(
        builds[["build_id", "pipeline_end_time"]].rename(columns={"build_id": "build_sk"}),
        on="build_sk",
        how="left",
    )
    links["deployed_at"] = links["pipeline_end_time"]
    links["lead_time_hours"] = (
        (links["deployed_at"] - links["author_date"]).dt.total_seconds() / 3600
    ).round(2)
    links["is_linkable"] = links["deployed_at"].notna()
    impossible = links[links["is_linkable"] & (links["lead_time_hours"] < 0)]
    for value in impossible["commit_id"].astype(str).tolist():
        rejects.append(
            {"table": "commit_links", "record_key": value, "reason": "association_precedes_commit"}
        )
    links = links.drop(impossible.index)
    links["is_valid_lead_time"] = links["is_linkable"]
    links["grain"] = "commit_id x deployment_id"
    commit_links = links.rename(columns={"build_sk": "deployment_id"})[
        [
            "commit_id", "deployment_id", "project_sk", "author_date", "deployed_at",
            "lead_time_hours", "is_linkable", "is_valid_lead_time", "grain",
        ]
    ]
    tables["commit_links"] = commit_links
    write(commit_links, SILVER / "commit_links.csv")
    dedupe["commit_links"] = {
        "rows_in": len(commits),
        "rows_out": len(commit_links),
        "impossible_associations_rejected": int(len(impossible)),
        "unlinked_commits": int((~commit_links["is_linkable"]).sum()),
    }

    for name in ("projects", "builds", "commits", "incidents"):
        write(tables[name], SILVER / f"{name}.csv")

    reject_frame = pd.DataFrame(rejects, columns=["table", "record_key", "reason"])
    write(reject_frame, SILVER / "rejected_rows.csv")
    (QUALITY / "silver_profile.json").write_text(
        json.dumps(
            {
                "dedupe_policy": "keep the latest ingestion_datetime per business key",
                "tables": dedupe,
                "rejected_rows": int(len(reject_frame)),
                "pii_columns_dropped": sorted(PII_COLUMNS),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return tables


# --------------------------------------------------------------------------- gold
def build_lineage(
    *,
    bronze_rows: dict[str, int],
    silver_rows: dict[str, int],
    rejects: pd.DataFrame,
    dim_project: pd.DataFrame,
    fact_deployment: pd.DataFrame,
    fact_commit_link: pd.DataFrame,
    fact_incident: pd.DataFrame,
    dora: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    """Describe what each medallion layer holds and what the next layer removed.

    The dashboard has to show the Bronze/Silver/Gold story from data rather than
    from a caption, so the counts travel with the pipeline that produced them.
    """

    def dropped(table: str) -> int:
        return int((rejects["table"] == table).sum())

    bronze_rule = {
        "projects": "source sheet, every value preserved as text",
        "builds": "source sheet, every value preserved as text",
        "commits": "source sheet, every value preserved as text",
        "incidents": "source sheet, every value preserved as text",
    }
    silver_rule = {
        "projects": "dropped rows without a project id or name",
        "builds": "dropped builds with no completion time, or ending before they started",
        "commits": "dropped commits without an id, project or author date",
        "incidents": "dropped incidents without an id, start or resolution time",
    }

    rows: list[dict[str, object]] = []
    for table in ("projects", "builds", "commits", "incidents"):
        source_rows = bronze_rows.get(table, 0)
        rows.append({
            "layer": "Bronze", "table_name": table,
            "rows_in": source_rows, "rows_out": source_rows, "rows_dropped": 0,
            "rule": bronze_rule[table],
        })
        rows.append({
            "layer": "Silver", "table_name": table,
            "rows_in": source_rows, "rows_out": silver_rows.get(table, 0),
            "rows_dropped": dropped(table),
            "rule": silver_rule[table],
        })

    links_in = silver_rows.get("commits", 0)
    rows.append({
        "layer": "Silver", "table_name": "commit_links",
        "rows_in": links_in, "rows_out": len(fact_commit_link),
        "rows_dropped": dropped("commit_links"),
        "rule": "dropped links to a build that finished before the commit was authored",
    })

    # Aggregation is not deletion: those rows legitimately collapse to a coarser
    # grain, so rows_dropped stays 0 and the rule says what the grain became.
    gold_tables = [
        ("dim_project", silver_rows.get("projects", 0), len(dim_project), 0,
         "source projects plus unmapped members referenced by incidents"),
        ("fact_deployment", silver_rows.get("builds", 0), len(fact_deployment), 0,
         "one row per completed build, the deployment proxy"),
        ("fact_commit_link", silver_rows.get("commit_links", 0), len(fact_commit_link), 0,
         "commit x build associations that carry a lead time"),
        ("fact_incident", silver_rows.get("incidents", 0), len(fact_incident), 0,
         "one row per incident with restore hours"),
        ("dora_service_month", len(fact_deployment), len(dora), 0,
         f"aggregated {len(fact_deployment)} builds to {len(dora)} project-months"),
        ("dora_period_summary", len(dora), len(summary), 0,
         f"rolled {len(dora)} project-months into one period row"),
    ]
    for table, rows_in, rows_out, rows_dropped, rule in gold_tables:
        rows.append({
            "layer": "Gold", "table_name": table,
            "rows_in": rows_in, "rows_out": rows_out, "rows_dropped": rows_dropped,
            "rule": rule,
        })

    lineage = pd.DataFrame(rows)
    for column in ("rows_in", "rows_out", "rows_dropped"):
        lineage[column] = lineage[column].astype("Int64")
    return lineage


def gold(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    GOLD.mkdir(parents=True, exist_ok=True)
    projects, builds = tables["projects"], tables["builds"]
    inline_links = tables["commit_links"]
    incidents = tables["incidents"]

    dim_project = projects.rename(columns={"project_id": "project_sk"})[
        ["project_sk", "project_name"]
    ].assign(is_mapped=True)

    # incidents can reference projects that are absent from the project sheet
    unmapped_names = sorted(
        set(incidents["project_name"].dropna()) - set(dim_project["project_name"])
    )
    if unmapped_names:
        extra = pd.DataFrame(
            {
                "project_sk": [f"unmapped::{name}" for name in unmapped_names],
                "project_name": unmapped_names,
                "is_mapped": False,
            }
        )
        dim_project = pd.concat([dim_project, extra], ignore_index=True)

    fact_deployment = (
        builds.assign(
            deployment_date=builds["pipeline_end_time"].dt.tz_localize(None).dt.date.astype(str),
            reporting_month=month_of(builds["pipeline_end_time"]),
        )
        .rename(columns={"build_id": "deployment_id", "build_name": "component_name"})[
            [
                "deployment_id", "project_sk", "component_name", "pipeline_id",
                "pipeline_start_time", "pipeline_end_time", "duration_minutes",
                "deployment_date", "reporting_month",
            ]
        ]
        .merge(dim_project, on="project_sk", how="left")
    )

    # A date column is required to filter the association fact by month. Without it
    # the fact is reachable only through DimProject, so a month slicer cannot reach it
    # and any monthly measure silently returns the period-wide value.
    fact_commit_link = inline_links.assign(
        deployed_date=inline_links["deployed_at"].dt.strftime("%Y-%m-%d"),
        reporting_month=inline_links["deployed_at"].dt.strftime("%Y-%m"),
    )

    fact_incident = (
        incidents.merge(dim_project[["project_sk", "project_name"]], on="project_name", how="left")
        .rename(columns={
            "incident_started_datetime": "started_at",
            "incident_resolved_datetime": "resolved_at",
        })[
            [
                "workitem_id", "project_sk", "project_name", "caused_by_deployment",
                "started_at", "resolved_at", "restore_hours",
            ]
        ]
    )
    fact_incident["reporting_month"] = month_of(fact_incident["started_at"])
    fact_incident["started_date"] = fact_incident["started_at"].dt.tz_localize(None).dt.strftime(
        "%Y-%m-%d"
    )

    deploy_month = fact_deployment.groupby(
        ["project_sk", "reporting_month"], as_index=False
    ).agg(
        deployment_count=("deployment_id", "nunique"),
        median_build_minutes=("duration_minutes", "median"),
    )

    valid_links = fact_commit_link[fact_commit_link["is_valid_lead_time"]].assign(
        reporting_month=month_of(fact_commit_link.loc[
            fact_commit_link["is_valid_lead_time"], "deployed_at"
        ])
    )
    lead_month = valid_links.groupby(["project_sk", "reporting_month"], as_index=False).agg(
        lead_time_median_hours=("lead_time_hours", "median"),
        lead_time_sample_size=("lead_time_hours", "size"),
    )

    failed_month = (
        fact_incident[fact_incident["caused_by_deployment"] == 1]
        .groupby(["project_sk", "reporting_month"], as_index=False)
        .agg(
            failed_deployments=("workitem_id", "count"),
            mttr_median_hours=("restore_hours", "median"),
            mttr_sample_size=("restore_hours", "size"),
        )
    )

    dora = deploy_month.merge(lead_month, on=["project_sk", "reporting_month"], how="left")
    dora = dora.merge(failed_month, on=["project_sk", "reporting_month"], how="left")
    dora = dora.merge(dim_project, on="project_sk", how="left")

    dora["days_in_month"] = pd.PeriodIndex(dora["reporting_month"], freq="M").days_in_month
    dora["deployment_frequency_per_day"] = (dora["deployment_count"] / dora["days_in_month"]).round(3)
    dora["failed_deployments"] = dora["failed_deployments"].fillna(0).astype(int)
    dora["change_failure_rate_pct"] = (
        dora["failed_deployments"] / dora["deployment_count"] * 100
    ).round(2)
    dora["lead_time_median_hours"] = dora["lead_time_median_hours"].round(2)
    dora["mttr_median_hours"] = dora["mttr_median_hours"].round(2)
    dora["lead_time_available"] = dora["lead_time_median_hours"].notna()
    dora["mttr_available"] = dora["mttr_median_hours"].notna()

    def availability(row: pd.Series) -> str:
        lead_ok = bool(row["lead_time_available"]) and (row["lead_time_sample_size"] or 0) >= 5
        mttr_ok = bool(row["mttr_available"]) and (row["mttr_sample_size"] or 0) >= 1
        if lead_ok and mttr_ok:
            return "validated"
        if bool(row["lead_time_available"]) or bool(row["mttr_available"]):
            return "partial"
        return "unavailable"

    dora["data_quality_status"] = dora.apply(availability, axis=1)
    dora["grain"] = "project_sk x reporting_month"
    dora["notes"] = (
        "Build runs are a deployment proxy: the source records no environment or release event. "
        "Lead time is calculated at commit-to-build association grain, so a commit rebuilt several times "
        "appears once per build. CFR matches incidents flagged caused_by_deployment to project-month "
        "deployments because no event-level deployment link exists. MTTR is blank where no "
        "deployment-caused incident was recorded."
    )
    # Counts are integers, not measurements. Written as floats they would read "7.0"
    # in the report and force the model to treat a sample size as a decimal.
    for column in (
        "days_in_month", "deployment_count", "failed_deployments",
        "lead_time_sample_size", "mttr_sample_size",
    ):
        dora[column] = dora[column].astype("Int64")
    dora = dora[
        [
            "project_sk", "project_name", "reporting_month", "grain", "days_in_month",
            "deployment_count", "deployment_frequency_per_day",
            "lead_time_median_hours", "lead_time_sample_size", "lead_time_available",
            "failed_deployments", "change_failure_rate_pct",
            "mttr_median_hours", "mttr_sample_size", "mttr_available",
            "median_build_minutes", "data_quality_status", "notes",
        ]
    ].sort_values(["reporting_month", "project_name"]).reset_index(drop=True)

    valid_lead = fact_commit_link[fact_commit_link["is_valid_lead_time"]]
    failed_incidents = fact_incident[fact_incident["caused_by_deployment"] == 1]
    summary = pd.DataFrame(
        [
            {
                "period_start": dora["reporting_month"].min(),
                "period_end": dora["reporting_month"].max(),
                "projects": int(dora["project_sk"].nunique()),
                "months": int(dora["reporting_month"].nunique()),
                "total_deployments": int(dora["deployment_count"].sum()),
                "deployment_frequency_per_month": round(dora["deployment_count"].mean(), 2),
                "lead_time_median_hours": round(valid_lead["lead_time_hours"].median(), 2),
                "lead_time_sample_size": int(len(valid_lead)),
                "unique_commits": int(fact_commit_link["commit_id"].nunique()),
                "commit_link_coverage_pct": round(fact_commit_link["is_linkable"].mean() * 100, 2),
                "invalid_lead_links": int(
                    (fact_commit_link["is_linkable"] & ~fact_commit_link["is_valid_lead_time"]).sum()
                ),
                "change_failure_rate_pct": round(
                    failed_incidents["workitem_id"].nunique()
                    / dora["deployment_count"].sum()
                    * 100,
                    2,
                ),
                "deployment_related_incidents": int(failed_incidents["workitem_id"].nunique()),
                "mttr_median_hours": round(failed_incidents["restore_hours"].median(), 2),
                "mttr_sample_size": int(len(failed_incidents)),
                "data_quality_status": "partial",
                "notes": "Period-wide rollup; deployment-proxy and incident-matching caveats apply.",
            }
        ]
    )

    lineage = build_lineage(
        bronze_rows={path.stem: len(pd.read_csv(path, dtype=str))
                     for path in sorted(BRONZE.glob("*.csv"))},
        silver_rows={path.stem: len(pd.read_csv(path))
                     for path in sorted(SILVER.glob("*.csv"))
                     if path.stem != "rejected_rows"},
        rejects=pd.read_csv(SILVER / "rejected_rows.csv"),
        dim_project=dim_project,
        fact_deployment=fact_deployment,
        fact_commit_link=fact_commit_link,
        fact_incident=fact_incident,
        dora=dora,
        summary=summary,
    )

    outputs = {
        "dim_project": dim_project,
        "fact_deployment": fact_deployment,
        "fact_commit_link": fact_commit_link,
        "fact_incident": fact_incident,
        "dora_service_month": dora,
        "dora_period_summary": summary,
        "pipeline_lineage": lineage,
    }
    for name, df in outputs.items():
        write(df, GOLD / f"{name}.csv")
    return outputs


def main() -> None:
    raw = bronze()
    tables = silver(raw)
    outputs = gold(tables)
    dora = outputs["dora_service_month"]
    print("Bronze:", ", ".join(f"{k}={len(v)}" for k, v in raw.items()))
    print(
        f"Silver: builds={len(tables['builds'])}, commits={len(tables['commits'])}, "
        f"incidents={len(tables['incidents'])}"
    )
    print(
        f"Gold:   grain rows={len(dora)}, projects={dora['project_sk'].nunique()}, "
        f"months={dora['reporting_month'].nunique()}"
    )


if __name__ == "__main__":
    main()
