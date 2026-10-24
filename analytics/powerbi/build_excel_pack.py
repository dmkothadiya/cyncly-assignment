"""Build a single Excel workbook containing every table Power BI needs.

Power BI Desktop connects to one workbook and picks all sheets in a single dialog,
which is far fewer steps than six separate CSV connections. Two convenience date
columns are added here (they are computed in the M query for the CSV path).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "analytics" / "gold"
OUTPUT = Path(__file__).resolve().parent / "DORA_Data.xlsx"

DATETIME_COLUMNS = {
    "FactDeployment": ["pipeline_start_time", "pipeline_end_time"],
    "FactCommitLink": ["author_date", "deployed_at"],
    "FactIncident": ["started_at", "resolved_at"],
}
DATE_COLUMNS = {
    "FactDeployment": ["deployment_date"],
}


def main() -> None:
    dim = pd.read_csv(GOLD / "dim_project.csv")

    deployment = pd.read_csv(GOLD / "fact_deployment.csv")
    deployment["deployment_date"] = pd.to_datetime(deployment["deployment_date"]).dt.date

    links = pd.read_csv(GOLD / "fact_commit_link.csv")
    incidents = pd.read_csv(GOLD / "fact_incident.csv")

    dora = pd.read_csv(GOLD / "dora_service_month.csv")
    dora.insert(
        dora.columns.get_loc("reporting_month") + 1,
        "month_start",
        pd.to_datetime(dora["reporting_month"] + "-01").dt.date,
    )

    frames = {
        "DimProject": dim,
        "FactDeployment": deployment,
        "FactCommitLink": links,
        "FactIncident": incidents,
        "DoraServiceMonth": dora,
    }

    for sheet, columns in DATETIME_COLUMNS.items():
        for column in columns:
            frames[sheet][column] = pd.to_datetime(
                frames[sheet][column], errors="coerce", utc=True
            ).dt.tz_localize(None)

    for sheet, columns in DATE_COLUMNS.items():
        for column in columns:
            frames[sheet][column] = pd.to_datetime(frames[sheet][column], errors="coerce").dt.date

    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        for sheet, frame in frames.items():
            frame.to_excel(writer, sheet_name=sheet, index=False)

    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    for sheet, frame in frames.items():
        print(f"  {sheet:18s} {len(frame):4d} rows  {len(frame.columns):2d} columns")

    # read back to prove the workbook is loadable and nothing was truncated
    for sheet, frame in frames.items():
        reloaded = pd.read_excel(OUTPUT, sheet_name=sheet)
        assert len(reloaded) == len(frame), f"{sheet} row count changed on round-trip"
        assert list(reloaded.columns) == list(frame.columns), f"{sheet} columns changed"
    print("  round-trip check: row and column counts match for all sheets")


if __name__ == "__main__":
    main()
