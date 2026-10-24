"""Executable data-quality checks for the DORA gold layer.

Three independent checks, each returning PASS or FAIL with evidence:

  DQ-01  Referential integrity and grain uniqueness
  DQ-02  Temporal validity of deployment, commit-link and incident facts
  DQ-03  Metric reconciliation between facts and the published metric table

Usage
-----
  python analytics/quality-checks/run_quality_checks.py
  python analytics/quality-checks/run_quality_checks.py --fixtures   # negative test

Exit code is 0 only when every check passes. The --fixtures mode deliberately
corrupts a copy of the gold layer and asserts that the checks detect it; it exits
non-zero if a check fails to catch the injected defect.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ANALYTICS_DIR = Path(__file__).resolve().parents[1]
GOLD = ANALYTICS_DIR / "gold"
OUTPUT = Path(__file__).resolve().parent / "dq_results.json"

REQUIRED_FILES = [
    "dim_project.csv",
    "fact_deployment.csv",
    "fact_commit_link.csv",
    "fact_incident.csv",
    "dora_service_month.csv",
    "dora_period_summary.csv",
]

TOLERANCE = 0.05


@dataclass
class Check:
    check_id: str
    name: str
    question: str
    status: str = "PASS"
    findings: list[str] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.status = "FAIL"
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.findings.append(message)

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "question": self.question,
            "status": self.status,
            "errors": self.errors,
            "findings": self.findings,
            "metrics": self.metrics,
        }


def load(base: Path) -> dict[str, pd.DataFrame]:
    missing = [name for name in REQUIRED_FILES if not (base / name).exists()]
    if missing:
        raise FileNotFoundError(f"missing gold inputs: {', '.join(missing)}")
    return {name.replace(".csv", ""): pd.read_csv(base / name) for name in REQUIRED_FILES}


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1"])


# ---------------------------------------------------------------- DQ-01
def dq_01_referential_integrity(tables: dict[str, pd.DataFrame]) -> Check:
    check = Check(
        "DQ-01",
        "Referential integrity and grain uniqueness",
        "Does every fact resolve to a dimension row, and is each declared grain unique?",
    )
    dim = tables["dim_project"]
    deployments = tables["fact_deployment"]
    links = tables["fact_commit_link"]
    incidents = tables["fact_incident"]
    dora = tables["dora_service_month"]

    project_keys = set(dim["project_sk"].astype(str))
    duplicate_keys = int(dim["project_sk"].duplicated().sum())
    check.metrics["projects"] = len(dim)
    check.metrics["duplicate_project_keys"] = duplicate_keys
    if duplicate_keys:
        check.fail(f"dim_project has {duplicate_keys} duplicate project keys")

    orphans = {
        "fact_deployment": int((~deployments["project_sk"].astype(str).isin(project_keys)).sum()),
        "fact_commit_link": int((~links["project_sk"].astype(str).isin(project_keys)).sum()),
        "fact_incident": int((~incidents["project_sk"].astype(str).isin(project_keys)).sum()),
        "dora_service_month": int((~dora["project_sk"].astype(str).isin(project_keys)).sum()),
    }
    check.metrics["orphan_rows_by_table"] = orphans
    for table, count in orphans.items():
        if count:
            check.fail(f"{table} has {count} rows with a project_sk absent from dim_project")

    duplicates = {
        "fact_deployment.deployment_id": int(deployments["deployment_id"].duplicated().sum()),
        "fact_incident.workitem_id": int(incidents["workitem_id"].duplicated().sum()),
        "dora_service_month(project_sk, reporting_month)": int(
            dora.duplicated(subset=["project_sk", "reporting_month"]).sum()
        ),
        "fact_commit_link(commit_id, deployment_id)": int(
            links.duplicated(subset=["commit_id", "deployment_id"]).sum()
        ),
    }
    check.metrics["duplicate_rows_by_key"] = duplicates
    for label, count in duplicates.items():
        if count:
            check.fail(f"{label} is not unique: {count} duplicates")

    unresolved = int(
        (~links["deployment_id"].astype(str).isin(set(deployments["deployment_id"].astype(str)))).sum()
    )
    check.metrics["commit_links_without_deployment_row"] = unresolved
    if unresolved:
        check.warn(
            f"{unresolved} commit links reference a deployment_id absent from fact_deployment "
            "(build rejected in the silver layer; excluded from lead time)"
        )
    return check


# ---------------------------------------------------------------- DQ-02
def dq_02_temporal_validity(tables: dict[str, pd.DataFrame]) -> Check:
    check = Check(
        "DQ-02",
        "Temporal validity",
        "Are timestamps ordered and are published lead times non-negative?",
    )
    deployments = tables["fact_deployment"].copy()
    links = tables["fact_commit_link"].copy()
    incidents = tables["fact_incident"].copy()

    deployments["started"] = pd.to_datetime(deployments["pipeline_start_time"], errors="coerce", utc=True, format="mixed")
    deployments["completed"] = pd.to_datetime(deployments["pipeline_end_time"], errors="coerce", utc=True, format="mixed")
    incidents["started"] = pd.to_datetime(incidents["started_at"], errors="coerce", utc=True, format="mixed")
    incidents["resolved"] = pd.to_datetime(incidents["resolved_at"], errors="coerce", utc=True, format="mixed")

    null_starts = int(deployments["started"].isna().sum())
    null_ends = int(deployments["completed"].isna().sum())
    inverted_deploy = int((deployments["completed"] < deployments["started"]).sum())
    null_incident = int(incidents[["started", "resolved"]].isna().any(axis=1).sum())
    inverted_incident = int((incidents["resolved"] < incidents["started"]).sum())

    linkable = links[truthy(links["is_linkable"])]
    lead = num(linkable["lead_time_hours"])
    negative_lead = int((lead < 0).sum())
    null_lead = int(lead.isna().sum())

    check.metrics.update(
        {
            "deployments_null_start": null_starts,
            "deployments_null_end": null_ends,
            "deployments_end_before_start": inverted_deploy,
            "incidents_null_timestamps": null_incident,
            "incidents_resolved_before_started": inverted_incident,
            "commit_links_checked": int(len(linkable)),
            "commit_links_negative_lead_time": negative_lead,
            "commit_links_null_lead_time": null_lead,
        }
    )

    if null_starts or null_ends:
        check.fail(f"fact_deployment has {null_starts + null_ends} null start/end timestamps")
    if inverted_deploy:
        check.fail(f"fact_deployment has {inverted_deploy} rows where completion precedes start")
    if null_incident:
        check.fail(f"fact_incident has {null_incident} rows with a missing start or resolution")
    if inverted_incident:
        check.fail(f"fact_incident has {inverted_incident} rows resolved before they started")
    if null_lead:
        check.fail(f"{null_lead} linked commits have no computable lead time")
    if negative_lead:
        check.fail(
            f"{negative_lead} commit links have a commit timestamp after build completion "
            "(source defect: a commit cannot be authored after the build that contains it)"
        )

    flagged = int((~truthy(linkable["is_valid_lead_time"])).sum())
    if flagged and not negative_lead:
        check.warn(f"{flagged} links are flagged invalid for reasons other than negative time")
    return check


# ---------------------------------------------------------------- DQ-03
def dq_03_metric_reconciliation(tables: dict[str, pd.DataFrame]) -> Check:
    check = Check(
        "DQ-03",
        "Metric reconciliation",
        "Do the published DORA values recompute from the facts at the declared grain?",
    )
    deployments = tables["fact_deployment"]
    links = tables["fact_commit_link"]
    incidents = tables["fact_incident"]
    dora = tables["dora_service_month"].copy()
    summary = tables["dora_period_summary"].iloc[0]

    recomputed = deployments.groupby(["project_sk", "reporting_month"], as_index=False).agg(
        expected_deployments=("deployment_id", "nunique")
    )
    merged = dora.merge(
        recomputed, on=["project_sk", "reporting_month"], how="outer", indicator=True
    )
    unmatched = int((merged["_merge"] != "both").sum())
    check.metrics["metric_rows_not_matching_fact_grain"] = unmatched
    if unmatched:
        check.fail(f"{unmatched} metric rows do not align with the deployment fact grain")

    mismatch = int(
        (num(merged["deployment_count"]).fillna(-1) != num(merged["expected_deployments"]).fillna(-2)).sum()
    )
    check.metrics["deployment_count_mismatches"] = mismatch
    if mismatch:
        check.fail(f"{mismatch} rows publish a deployment_count that differs from fact_deployment")

    days = pd.PeriodIndex(merged["reporting_month"].astype(str), freq="M").days_in_month
    expected_df = (num(merged["deployment_count"]) / days).round(3)
    df_mismatch = int(((num(merged["deployment_frequency_per_day"]) - expected_df).abs() > TOLERANCE).sum())
    check.metrics["deployment_frequency_mismatches"] = df_mismatch
    if df_mismatch:
        check.fail(f"{df_mismatch} rows publish a deployment frequency inconsistent with count / days")

    cfr_expected = (num(merged["failed_deployments"]) / num(merged["deployment_count"]) * 100).round(2)
    cfr_mismatch = int(((num(merged["change_failure_rate_pct"]) - cfr_expected).abs() > TOLERANCE).sum())
    check.metrics["change_failure_rate_mismatches"] = cfr_mismatch
    if cfr_mismatch:
        check.fail(f"{cfr_mismatch} rows publish a change failure rate inconsistent with its numerator")

    over_denominator = int((num(merged["failed_deployments"]) > num(merged["deployment_count"])).sum())
    check.metrics["rows_where_failed_exceeds_deployments"] = over_denominator
    if over_denominator:
        check.fail(f"{over_denominator} rows have more failed deployments than deployments")

    valid_links = links[truthy(links["is_valid_lead_time"])].copy()
    valid_links["reporting_month"] = (
        pd.to_datetime(valid_links["deployed_at"], errors="coerce", utc=True, format="mixed")
        .dt.tz_localize(None)
        .dt.to_period("M")
        .astype(str)
    )
    lead_expected = (
        valid_links.groupby(["project_sk", "reporting_month"], as_index=False)
        .agg(expected_lead=("lead_time_hours", "median"), expected_n=("lead_time_hours", "size"))
    )
    lead_merged = merged.merge(lead_expected, on=["project_sk", "reporting_month"], how="left")
    lead_mismatch = int(
        ((num(lead_merged["lead_time_median_hours"]) - num(lead_merged["expected_lead"])).abs() > TOLERANCE).sum()
    )
    sample_mismatch = int(
        (
            num(lead_merged["lead_time_sample_size"]).fillna(0)
            != num(lead_merged["expected_n"]).fillna(0)
        ).sum()
    )
    check.metrics["lead_time_median_mismatches"] = lead_mismatch
    check.metrics["lead_time_sample_mismatches"] = sample_mismatch
    if lead_mismatch:
        check.fail(f"{lead_mismatch} rows publish a lead time median inconsistent with fact_commit_link")
    if sample_mismatch:
        check.fail(f"{sample_mismatch} rows publish a lead time sample size inconsistent with the facts")

    failed_expected = (
        incidents[incidents["caused_by_deployment"] == 1]
        .groupby(["project_sk", "reporting_month"], as_index=False)
        .agg(expected_failed=("workitem_id", "count"))
    )
    failed_merged = merged.merge(failed_expected, on=["project_sk", "reporting_month"], how="left")
    failed_mismatch = int(
        (
            num(failed_merged["failed_deployments"]).fillna(0)
            != num(failed_merged["expected_failed"]).fillna(0)
        ).sum()
    )
    check.metrics["failed_deployment_mismatches"] = failed_mismatch
    if failed_mismatch:
        check.fail(f"{failed_mismatch} rows publish failed_deployments inconsistent with fact_incident")

    total_published = int(num(dora["deployment_count"]).sum())
    total_summary = int(num(pd.Series([summary["total_deployments"]])).iloc[0])
    check.metrics["deployments_in_grain"] = total_published
    check.metrics["deployments_in_summary"] = total_summary
    if total_published != total_summary:
        check.fail(
            f"period summary reports {total_summary} deployments but grain rows total {total_published}"
        )
    return check


CHECKS = (dq_01_referential_integrity, dq_02_temporal_validity, dq_03_metric_reconciliation)


def run(base: Path) -> list[Check]:
    tables = load(base)
    return [fn(tables) for fn in CHECKS]


def report(results: list[Check], destination: Path | None) -> None:
    width = 78
    print("=" * width)
    print("DORA DATA QUALITY REPORT")
    print("=" * width)
    for result in results:
        print(f"\n[{result.status}] {result.check_id}  {result.name}")
        print(f"  question : {result.question}")
        for key, value in result.metrics.items():
            print(f"  metric   : {key} = {value}")
        for error in result.errors:
            print(f"  FAIL     : {error}")
        for finding in result.findings:
            print(f"  note     : {finding}")
    failed = [r for r in results if r.status == "FAIL"]
    print("\n" + "-" * width)
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} checks passed")
    print("-" * width)

    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                {
                    "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                    "checks_run": len(results),
                    "checks_failed": len(failed),
                    "overall_status": "PASS" if not failed else "FAIL",
                    "results": [r.to_dict() for r in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {destination}")

        # Publish the outcome as a Gold table so the report reads the real status
        # instead of repeating a caption that has to be edited by hand.
        gold = destination.parent.parent / "gold" if destination.parent.name == "quality-checks" else None
        if gold is not None and gold.is_dir():
            frame = pd.DataFrame([
                {
                    "check_id": r.check_id,
                    "name": r.name,
                    "question": r.question,
                    "status": r.status,
                    "checks_passed": 0 if r.status == "FAIL" else 1,
                    "detail": (
                        "; ".join(r.errors[:2]) if r.errors
                        else "; ".join(f"{k}={v}" for k, v in list(r.metrics.items())[:3])
                    ),
                }
                for r in results
            ])
            frame.to_csv(gold / "dq_check_results.csv", index=False)
            print(f"Wrote {gold / 'dq_check_results.csv'}")


# ------------------------------------------------------------ negative test
def corrupt_copy(source: Path, destination: Path) -> None:
    for name in REQUIRED_FILES:
        shutil.copy(source / name, destination / name)

    dora = pd.read_csv(destination / "dora_service_month.csv")
    dora = pd.concat([dora, dora.iloc[[0]]], ignore_index=True)
    dora.loc[0, "deployment_count"] = int(dora.loc[0, "deployment_count"]) + 7
    dora.to_csv(destination / "dora_service_month.csv", index=False)

    links = pd.read_csv(destination / "fact_commit_link.csv")
    linked = links.index[truthy(links["is_linkable"])]
    links.loc[linked[0], "lead_time_hours"] = -48.0
    links.loc[linked[0], "is_valid_lead_time"] = True
    links.to_csv(destination / "fact_commit_link.csv", index=False)


def run_negative_test() -> int:
    with tempfile.TemporaryDirectory() as handle:
        staged = Path(handle)
        corrupt_copy(GOLD, staged)
        results = run(staged)
        report(results, None)
        detected = [r.check_id for r in results if r.status == "FAIL"]
        undetected = [r.check_id for r in results if r.status != "FAIL"]
        print("\nNEGATIVE TEST")
        print("  injected defects: duplicate metric grain row, altered deployment_count, negative lead time")
        print(f"  checks that failed as expected: {detected}")
        if undetected:
            print(f"  NOT DETECTED by: {undetected}")
            return 1
        print("  all three checks detected the injected defects")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the three DORA data-quality checks.")
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="run the negative test against deliberately corrupted gold data",
    )
    args = parser.parse_args()

    if args.fixtures:
        return run_negative_test()

    results = run(GOLD)
    report(results, OUTPUT)
    return 0 if all(r.status == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
