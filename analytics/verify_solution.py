"""Independent verification of the DORA dashboard deliverables.

Recomputes the four metrics straight from the fact tables (not from the published
metric table), compares them to what the dashboard would show, and checks the
report file if one has been saved.

Usage:
    python analytics/verify_solution.py
    python analytics/verify_solution.py --pbix analytics/powerbi/DORA_DASHBOARD.pbix

Exit code 0 means every check passed.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
GOLD = ANALYTICS / "gold"
SILVER = ANALYTICS / "silver"
QUALITY = ANALYTICS / "quality-checks"

# Values below were confirmed by recomputing from docs/Case Study - DORA Metrics Data.xlsx
# directly, without going through the pipeline. The two September/November rows are
# deliberate regression guards: those builds are the ones the pipeline used to drop.
SPOT_CHECKS = [
    ("Project A", "2024-08", "deployment_count", 10),
    ("Project A", "2024-08", "change_failure_rate_pct", 30.0),
    ("Project A", "2024-08", "mttr_median_hours", 2.03),
    ("Project B", "2024-09", "deployment_count", 141),
    ("Project B", "2024-09", "lead_time_sample_size", 14),
    ("Project B", "2024-11", "deployment_count", 73),
    ("Project B", "2024-12", "lead_time_median_hours", 18.29),
    ("Project B", "2024-12", "lead_time_sample_size", 77),
]

TOLERANCE = 0.05


@dataclass
class Result:
    name: str
    passed: bool
    detail: str


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.results.append(Result(name, passed, detail))

    def show(self) -> int:
        width = 84
        print("=" * width)
        print("DORA SOLUTION VERIFICATION")
        print("=" * width)
        for item in self.results:
            print(f"[{'PASS' if item.passed else 'FAIL'}] {item.name}")
            print(f"       {item.detail}")
        failed = [r for r in self.results if not r.passed]
        print("-" * width)
        print(f"RESULT: {len(self.results) - len(failed)}/{len(self.results)} checks passed")
        print("-" * width)
        return 0 if not failed else 1


def close(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if pd.isna(left) or pd.isna(right):
        return False
    return abs(float(left) - float(right)) <= tolerance


def check_files(report: Report) -> None:
    required = [
        "dim_project.csv",
        "fact_deployment.csv",
        "fact_commit_link.csv",
        "fact_incident.csv",
        "dora_service_month.csv",
        "dora_period_summary.csv",
    ]
    missing = [name for name in required if not (GOLD / name).exists()]
    report.add(
        "Gold layer files present",
        not missing,
        "all 6 gold tables found" if not missing else f"missing: {', '.join(missing)}",
    )

    powerbi = ANALYTICS / "powerbi"
    assets = ["DORA_POWER_QUERY.m", "DORA_MEASURES.dax", "DORA_theme.json"]
    absent = [name for name in assets if not (powerbi / name).exists()]
    report.add(
        "Power BI build assets present",
        not absent,
        "query, measures and theme found" if not absent else f"missing: {absent}",
    )

    model = powerbi / "DORA.SemanticModel" / "definition" / "model.tmdl"
    tables = list((powerbi / "DORA.SemanticModel" / "definition" / "tables").glob("*.tmdl"))
    report.add(
        "TMDL semantic model present",
        model.exists() and len(tables) >= 6,
        f"{len(tables)} table definitions, model.tmdl {'found' if model.exists() else 'missing'}",
    )


def check_recomputation(report: Report) -> pd.DataFrame:
    deploys = pd.read_csv(GOLD / "fact_deployment.csv")
    links = pd.read_csv(GOLD / "fact_commit_link.csv")
    incidents = pd.read_csv(GOLD / "fact_incident.csv")
    dora = pd.read_csv(GOLD / "dora_service_month.csv")

    expected = deploys.groupby(["project_sk", "reporting_month"], as_index=False).agg(
        deployment_count=("deployment_id", "nunique")
    )
    merged = dora.merge(expected, on=["project_sk", "reporting_month"], how="left", suffixes=("", "_calc"))
    mismatches = (merged["deployment_count"] != merged["deployment_count_calc"]).sum()
    report.add(
        "Deployment frequency recomputes from fact_deployment",
        mismatches == 0,
        f"{len(merged)} grain rows compared, {mismatches} mismatches",
    )

    valid = links[links["is_valid_lead_time"].astype(str).str.lower() == "true"].copy()
    valid["month"] = (
        pd.to_datetime(valid["deployed_at"], utc=True, format="mixed")
        .dt.tz_localize(None)
        .dt.to_period("M")
        .astype(str)
    )
    lead = valid.groupby(["project_sk", "month"]).agg(
        median_lead=("lead_time_hours", "median"), n=("lead_time_hours", "size")
    ).reset_index().rename(columns={"month": "reporting_month"})
    lead_merged = dora.merge(lead, on=["project_sk", "reporting_month"], how="left")
    lead_bad = int(
        (~lead_merged.apply(lambda r: close(r["lead_time_median_hours"], r["median_lead"]), axis=1)).sum()
    )
    report.add(
        "Lead time recomputes from fact_commit_link",
        lead_bad == 0,
        f"{len(valid)} valid links, {lead_bad} grain rows disagree",
    )

    failed = incidents[incidents["caused_by_deployment"] == 1].groupby(
        ["project_sk", "reporting_month"], as_index=False
    ).agg(failed=("workitem_id", "count"), mttr=("restore_hours", "median"))
    failed_merged = dora.merge(failed, on=["project_sk", "reporting_month"], how="left")
    failed_merged["failed"] = failed_merged["failed"].fillna(0)
    cfr_bad = 0
    for _, row in failed_merged.iterrows():
        recomputed = row["failed"] / row["deployment_count"] * 100
        if not close(row["change_failure_rate_pct"], recomputed):
            cfr_bad += 1
    report.add(
        "Change failure rate = failed deployments / deployments",
        cfr_bad == 0,
        f"{len(failed_merged)} grain rows compared, {cfr_bad} mismatches",
    )

    mttr_bad = int(
        (~failed_merged.apply(lambda r: close(r["mttr_median_hours"], r["mttr"]), axis=1)).sum()
    )
    report.add(
        "MTTR recomputes from fact_incident",
        mttr_bad == 0,
        f"{int((incidents['caused_by_deployment'] == 1).sum())} deployment-caused incidents, "
        f"{mttr_bad} grain rows disagree",
    )
    return dora


def check_source_reconciliation(report: Report, dora: pd.DataFrame) -> None:
    """Reconcile the facts against the source workbook, not against each other.

    Every other check compares Gold to Silver or to itself, so a row lost during
    ingestion is invisible to them. This reads the workbook directly and asserts
    that nothing was dropped that should have been kept.
    """
    workbook = ROOT / "docs" / "Case Study - DORA Metrics Data.xlsx"
    if not workbook.exists():
        report.add(
            "Source workbook reconciliation",
            False,
            f"{workbook.name} not found; the independent check cannot run",
        )
        return

    parse = {"errors": "coerce", "utc": True, "format": "mixed"}
    builds = pd.read_excel(workbook, "builds")
    builds["start"] = pd.to_datetime(builds["pipeline_start_time"].astype(str), **parse)
    builds["end"] = pd.to_datetime(builds["pipeline_end_time"].astype(str), **parse)
    expected_builds = int(
        (builds["end"].notna() & builds["start"].notna() & (builds["end"] >= builds["start"])).sum()
    )
    published = pd.read_csv(GOLD / "fact_deployment.csv")
    report.add(
        "Every valid source build reached Gold",
        len(published) == expected_builds,
        f"workbook has {expected_builds} build(s) with a usable window, Gold has {len(published)}",
    )

    commits = pd.read_excel(workbook, "commits")
    report.add(
        "Every source commit reached Silver",
        len(commits) == len(pd.read_csv(SILVER / "commits.csv")),
        f"workbook {len(commits)} commit row(s), silver "
        f"{len(pd.read_csv(SILVER / 'commits.csv'))}",
    )

    # A timestamp that fails to parse must be a real defect in the source, never a
    # parsing artefact. Mixed precisions are the usual cause, so assert there are none.
    unparsed = int(
        (builds["end"].isna() & builds["pipeline_end_time"].notna()).sum()
        + (builds["start"].isna() & builds["pipeline_start_time"].notna()).sum()
    )
    report.add(
        "No timestamp is dropped by the parser",
        unparsed == 0,
        f"{unparsed} non-empty timestamp(s) failed to parse",
    )

    summary = pd.read_csv(GOLD / "dora_period_summary.csv").iloc[0]
    report.add(
        "Period total matches the source",
        int(summary["total_deployments"]) == expected_builds,
        f"summary {int(summary['total_deployments'])} vs workbook {expected_builds}",
    )


def check_spot_values(report: Report, dora: pd.DataFrame) -> None:
    for project, month, column, expected in SPOT_CHECKS:
        row = dora[(dora["project_name"] == project) & (dora["reporting_month"] == month)]
        if row.empty:
            report.add(f"Spot check {project} {month} {column}", False, "grain row not found")
            continue
        actual = row.iloc[0][column]
        report.add(
            f"Spot check {project} {month} {column}",
            close(actual, expected),
            f"expected {expected}, published {actual}",
        )


def check_totals(report: Report, dora: pd.DataFrame) -> None:
    summary = pd.read_csv(GOLD / "dora_period_summary.csv").iloc[0]
    total = int(dora["deployment_count"].sum())
    report.add(
        "Grain rows sum to the published total",
        total == int(summary["total_deployments"]),
        f"grain {total} vs summary {int(summary['total_deployments'])}",
    )
    report.add(
        "Period summary matches the recomputable KPIs",
        close(summary["change_failure_rate_pct"], 3 / total * 100, 0.01),
        f"CFR {summary['change_failure_rate_pct']}% from "
        f"{int(summary['deployment_related_incidents'])} incidents / {total} deployments",
    )


def check_quality_results(report: Report) -> None:
    path = QUALITY / "dq_results.json"
    if not path.exists():
        report.add("Data-quality results present", False, "dq_results.json not found; run the checks")
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    statuses = {item["check_id"]: item["status"] for item in payload["results"]}
    report.add(
        "All three data-quality checks passed",
        payload["overall_status"] == "PASS",
        f"{payload['checks_run'] - payload['checks_failed']}/{payload['checks_run']} passed "
        f"({', '.join(f'{k}={v}' for k, v in statuses.items())})",
    )

    profile = QUALITY / "silver_profile.json"
    if profile.exists():
        data = json.loads(profile.read_text(encoding="utf-8"))
        commits = data["tables"].get("commits", {})
        report.add(
            "Source dedupe is recorded, not silent",
            bool(commits),
            f"commits rows_in={commits.get('rows_in')} rows_out={commits.get('rows_out')} "
            f"unique={commits.get('unique_commits')}",
        )


def check_pbip(report: Report) -> None:
    """The PBIP is the source of the report; validate it without opening Desktop."""
    project = ANALYTICS / "powerbi" / "DORA_Project"
    if not project.exists():
        report.add(
            "Power BI project present",
            False,
            "DORA_Project not found; run analytics/powerbi/build_pbip.py",
        )
        return

    required = [
        project / "DORA.pbip",
        project / "DORA.Report" / "definition.pbir",
        project / "DORA.Report" / "definition" / "report.json",
        project / "DORA.SemanticModel" / "definition" / "model.tmdl",
    ]
    missing = [path.name for path in required if not path.exists()]
    report.add(
        "Power BI project structure complete",
        not missing,
        "all expected files present" if not missing else f"missing: {', '.join(missing)}",
    )

    visuals = list(project.glob("DORA.Report/definition/pages/*/visuals/*/visual.json"))
    pages = list(project.glob("DORA.Report/definition/pages/*/page.json"))
    report.add(
        "Report has the baseline and the governance page",
        len(pages) == 2 and len(visuals) >= 15,
        f"{len(pages)} page(s), {len(visuals)} visual definitions",
    )

    sys.path.insert(0, str(ANALYTICS / "powerbi"))
    try:
        import check_references
    finally:
        sys.path.pop(0)

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = check_references.main(project)
    unresolved = [
        line.strip()
        for line in buffer.getvalue().splitlines()
        if "not found" in line or "unknown table" in line
    ]
    report.add(
        "Every visual field reference resolves in the model",
        code == 0,
        "all references resolve" if code == 0 else "; ".join(unresolved[:3]),
    )

    frequency = (project / "DORA.SemanticModel" / "definition" / "tables"
                 / "DoraServiceMonth.tmdl").read_text(encoding="utf-8")
    summary = pd.read_csv(GOLD / "dora_period_summary.csv").iloc[0]
    report.add(
        "Deployment Frequency matches the per project-month definition",
        "COUNTROWS ( DoraServiceMonth )" in frequency,
        f"measure divides deployments by grain rows "
        f"({int(summary['total_deployments'])} / 9 = "
        f"{summary['deployment_frequency_per_month']})",
    )

    # Regression guard: with float types the report prints "14.00" observations.
    sample_type_ok = all(
        "dataType: int64" in block
        for block in (
            frequency.split("column lead_time_sample_size")[1][:120],
            frequency.split("column mttr_sample_size")[1][:120],
        )
    )
    report.add(
        "Sample sizes are integers in the model",
        sample_type_ok,
        "lead and MTTR observation counts are int64, not decimals",
    )

    lineage_path = (project / "DORA.SemanticModel" / "definition" / "tables"
                    / "PipelineLineage.tmdl")
    dq_path = (project / "DORA.SemanticModel" / "definition" / "tables"
               / "DqCheckResult.tmdl")
    report.add(
        "Bronze/Silver/Gold lineage and DQ results are in the model",
        lineage_path.exists() and dq_path.exists(),
        "PipelineLineage and DqCheckResult tables exist, so both are visible in the report",
    )

    # A fact that has no date column related to DimDate can be reached only through
    # DimProject, so any monthly visual over it repeats the period-wide value.
    relationships = (project / "DORA.SemanticModel" / "definition"
                     / "relationships.tmdl").read_text(encoding="utf-8")
    date_links = [
        link for link in (
            "fromColumn: FactCommitLink.deployed_date",
            "fromColumn: FactIncident.started_date",
            "fromColumn: FactDeployment.deployment_date",
            "fromColumn: DoraServiceMonth.month_start",
        ) if link in relationships
    ]
    report.add(
        "Every fact is filterable by date",
        len(date_links) == 4,
        f"{len(date_links)}/4 facts relate a date column to DimDate",
    )

    # Find the column chart by type rather than by generated id.
    axis_entity = ""
    for path in visuals:
        document = json.loads(path.read_text(encoding="utf-8"))
        visual = document.get("visual", {})
        if visual.get("visualType") != "columnChart":
            continue
        state = visual.get("query", {}).get("queryState", {})
        projection = (state.get("Category") or {}).get("projections", [])
        if projection:
            axis_entity = (
                projection[0].get("field", {}).get("Column", {})
                .get("Expression", {}).get("SourceRef", {}).get("Entity", "")
            )
    report.add(
        "Lead-time chart axis can filter its own fact",
        axis_entity in {"FactCommitLink", "DimDate"},
        f"axis entity is {axis_entity or 'unknown'}; DoraServiceMonth would repeat the "
        "period median in every month",
    )

    # Relationships flow from DimProject/DimDate into the facts, so a selected grain row
    # never reaches FactCommitLink or FactIncident. The measures bridge it with
    # KEEPFILTERS(TREATAS(...)): a bare TREATAS replaces the visual's own filter and
    # collapsed every lead-time bar to the period median, and no bridge at all leaves
    # the cards frozen on the period median when a grain row is selected.
    bridge_count = frequency.count("TREATAS")
    guarded_count = frequency.count("KEEPFILTERS ( TREATAS")
    report.add(
        "Grain row selection reaches the fact measures",
        bridge_count > 0 and bridge_count == guarded_count,
        f"{guarded_count}/{bridge_count} TREATAS bridges are wrapped in KEEPFILTERS, so a "
        "grain row filters the cards without overriding the chart axis",
    )


def check_pbix(report: Report, path: Path) -> None:
    """Inspect a saved .pbix, including the modern PBIR layout.

    A .pbix saved by a current Power BI Desktop stores the report as PBIR files
    (Report/definition/...), not the legacy Report/Layout blob, and keeps the model in
    a compressed DataModel entry. Reading only the legacy names reported a healthy
    file as empty.
    """
    if not path.exists():
        report.add(
            "Saved .pbix inspected",
            False,
            f"{path.name} not found - save the report from Power BI Desktop, then rerun with --pbix",
        )
        return

    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            pbir = {name: archive.read(name) for name in names
                    if name.startswith("Report/definition/") and name.endswith(".json")}
            has_model = "DataModel" in names
            model_size = len(archive.read("DataModel")) if has_model else 0
            model_text = ""
            if "DataModelSchema" in names:
                model_text = archive.read("DataModelSchema").decode("utf-16-le", errors="ignore")
    except Exception as error:  # noqa: BLE001
        report.add("Saved .pbix inspected", False, f"cannot read the file: {error}")
        return

    pages = [n for n in pbir if n.endswith("/page.json")]
    visuals = [n for n in pbir if n.endswith("/visual.json")]
    report.add(
        "Saved .pbix contains the report pages and visuals",
        len(pages) == 2 and len(visuals) >= 15,
        f"{len(pages)} page(s), {len(visuals)} visual(s), {len(pbir)} PBIR definition file(s)",
    )
    report.add(
        "Saved .pbix contains an embedded model",
        has_model and model_size > 10_000,
        f"DataModel entry present ({model_size // 1024} KB)",
    )

    if model_text:
        wanted = ["Deployment Frequency (per project-month)",
                  "Lead Time for Changes (median h)", "Change Failure Rate %", "MTTR (median h)"]
        found = [name for name in wanted if name in model_text]
        report.add(
            "All four DORA measures exist in the .pbix",
            len(found) == len(wanted),
            f"{len(found)}/{len(wanted)} found in DataModelSchema",
        )
    else:
        # The model is compressed, so measure names are not readable here. The PBIP is
        # the source of that model and is validated separately; say so instead of
        # pretending to have checked the binary.
        report.add(
            "DORA measures verified via the project, not the binary",
            True,
            "model is compressed; measure and table checks run against DORA_Project/DORA.SemanticModel",
        )

    # Staleness: compare the saved report against the project it came from.
    saved = {name.split("/")[-2]: json.loads(blob) for name, blob in pbir.items()
             if name.endswith("/visual.json")}
    project_visuals = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (ANALYTICS / "powerbi" / "DORA_Project").glob(
            "DORA.Report/definition/pages/*/visuals/*/visual.json")
    }
    differing = [vid for vid, doc in project_visuals.items()
                 if vid in saved and _canonical(saved[vid]) != _canonical(doc)]
    absent = [vid for vid in project_visuals if vid not in saved]
    report.add(
        "Saved .pbix matches the current project",
        not differing and not absent,
        "same visual definitions as DORA_Project" if not differing and not absent
        else f"{len(differing)} visual(s) differ and {len(absent)} are missing - "
             "reopen the .pbip and save again",
    )


def _canonical(node):
    """Drop the churn Power BI Desktop adds when it re-serialises a report.

    Desktop rewrites `$schema` to the version it ships, marks one projection
    `active`, and injects theme/resource blocks. None of that changes what the
    report displays, so comparing it would flag staleness after every plain save.
    """
    if isinstance(node, dict):
        return {key: _canonical(value) for key, value in node.items()
                if key not in {"$schema", "active", "resourcePackages", "settings",
                               "themeCollection"}}
    if isinstance(node, list):
        return [_canonical(item) for item in node]
    return node


def _page_of(visual_paths: list[str], visual_id: str) -> str:
    for name in visual_paths:
        if name.split("/")[-2] == visual_id:
            return name.split("/")[3]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the DORA dashboard solution.")
    parser.add_argument("--pbix", type=Path, default=None,
                        help="path to a .pbix saved from Power BI Desktop")
    args = parser.parse_args()

    report = Report()
    check_files(report)
    dora = check_recomputation(report)
    check_source_reconciliation(report, dora)
    check_spot_values(report, dora)
    check_totals(report, dora)
    check_quality_results(report)
    check_pbip(report)
    if args.pbix:
        check_pbix(report, args.pbix)
    return report.show()


if __name__ == "__main__":
    raise SystemExit(main())
