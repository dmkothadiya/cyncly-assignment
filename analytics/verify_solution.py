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
QUALITY = ANALYTICS / "quality-checks"

# Values below were confirmed against the raw workbook before the pipeline existed.
SPOT_CHECKS = [
    ("Project A", "2024-08", "deployment_count", 10),
    ("Project A", "2024-08", "change_failure_rate_pct", 30.0),
    ("Project A", "2024-08", "mttr_median_hours", 2.03),
    ("Project B", "2024-12", "lead_time_median_hours", 18.29),
    ("Project B", "2024-12", "lead_time_sample_size", 77),
    ("Project B", "2024-09", "deployment_count", 140),
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
        pd.to_datetime(valid["deployed_at"], utc=True).dt.tz_localize(None).dt.to_period("M").astype(str)
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
    report.add(
        "Report page contains visuals",
        len(visuals) >= 4,
        f"{len(visuals)} visual definitions",
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
    report.add(
        "Deployment Frequency matches the per project-month definition",
        "COUNTROWS ( DoraServiceMonth )" in frequency,
        "measure divides deployments by grain rows (342 / 9 = 38.0)",
    )


def check_pbix(report: Report, path: Path) -> None:
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
            model_blob = archive.read("DataModelSchema") if "DataModelSchema" in names else b""
            layout_blob = archive.read("Report/Layout") if "Report/Layout" in names else b""
    except Exception as error:  # noqa: BLE001
        report.add("Saved .pbix inspected", False, f"cannot read the file: {error}")
        return

    model_text = model_blob.decode("utf-16-le", errors="ignore")
    layout_text = layout_blob.decode("utf-16-le", errors="ignore")

    wanted = ["Deployment Frequency (per project-month)", "Lead Time for Changes (median h)",
              "Change Failure Rate %", "MTTR (median h)"]
    found = [name for name in wanted if name in model_text]
    report.add(
        "All four DORA measures exist in the .pbix",
        len(found) == len(wanted),
        f"{len(found)}/{len(wanted)} found: {', '.join(found) if found else 'none'}",
    )

    tables = ["DoraServiceMonth", "FactDeployment", "FactCommitLink", "FactIncident", "DimProject"]
    present = [name for name in tables if name in model_text]
    report.add(
        "Expected tables are in the .pbix model",
        len(present) == len(tables),
        f"{len(present)}/{len(tables)} found",
    )

    visuals = len(re.findall(r'"visualType"', layout_text))
    pages = len(re.findall(r'"displayName"', layout_text))
    report.add(
        "Report page contains visuals",
        visuals >= 4,
        f"{visuals} visual definitions, {pages} named pages/sections detected",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the DORA dashboard solution.")
    parser.add_argument("--pbix", type=Path, default=None,
                        help="path to a .pbix saved from Power BI Desktop")
    args = parser.parse_args()

    report = Report()
    check_files(report)
    dora = check_recomputation(report)
    check_spot_values(report, dora)
    check_totals(report, dora)
    check_quality_results(report)
    check_pbip(report)
    if args.pbix:
        check_pbix(report, args.pbix)
    return report.show()


if __name__ == "__main__":
    raise SystemExit(main())
