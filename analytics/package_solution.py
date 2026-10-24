"""Assemble the reviewable DORA / Power BI delivery into a single zip.

Deliberate omission: raw Bronze rows contain commit author names and e-mail
addresses, so only the Bronze ingestion manifest is packaged. Bronze can be
regenerated from the workbook with the packaged pipeline.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
OUTPUT = ROOT / "DORA_PowerBI_Solution.zip"

INNER_README = """# DORA baseline - Power BI Desktop solution

Built from `Case Study - DORA Metrics Data.xlsx`. The folder layout mirrors the
source repository, so every script runs unmodified from the package root.

## Contents

| Path | What it is |
|---|---|
| `analytics/run_pipeline.py` | Bronze -> Silver -> Gold pipeline |
| `analytics/quality-checks/run_quality_checks.py` | The three executable data-quality checks |
| `analytics/generate_dashboard_preview.py` | Renders the layout reference PNG |
| `analytics/verify_solution.py` | Independent verifier: recomputes metrics and inspects a saved `.pbix` |
| `analytics/silver/` | Typed, validated, deduplicated tables (no personal data) |
| `analytics/gold/` | Facts, dimension, published metric grain, period summary |
| `analytics/quality-checks/dq_results.json` | Latest check result |
| `analytics/powerbi/` | Power BI project (`DORA_Project/`), Power Query, DAX measures, single-workbook data pack, TMDL semantic model, build guide |
| `analytics/dashboard/` | `dora_powerbi_desktop.png` - real Power BI Desktop capture; `dora_baseline_dashboard.png` - layout reference |
| `docs/METRIC_SPEC.md` | Grain, formulas, sources, rules, ownership, limitations |
| `docs/DATA_QUALITY.md` | Quality rules and known defects |
| `docs/DASHBOARD_VERIFICATION_GUIDE.md` | Step-by-step verification, expected values, troubleshooting |
| `validation/run_log.txt` | Captured validation summary |

Raw Bronze rows are not packaged because they contain commit author names and
e-mail addresses; `analytics/bronze/README.md` explains how to regenerate them.

## Reproduce

Place the source workbook at `docs/Case Study - DORA Metrics Data.xlsx`, then:

```powershell
python -m pip install -r requirements.txt
python analytics/run_pipeline.py
python analytics/quality-checks/run_quality_checks.py            # exit 0 = all pass
python analytics/quality-checks/run_quality_checks.py --fixtures # negative test
python analytics/verify_solution.py                          # 21 independent checks
python analytics/verify_solution.py --pbix analytics/powerbi/DORA_DASHBOARD.pbix
python analytics/powerbi/build_pbip.py
python analytics/powerbi/validate_pbip.py
python analytics/generate_dashboard_preview.py
```

Verification steps and expected values: `docs/DASHBOARD_VERIFICATION_GUIDE.md`.

## Open in Power BI Desktop

1. Run the pipeline so `analytics/gold` is populated.
2. Open `analytics/powerbi/DORA_Project/DORA.pbip`.
3. Press **Refresh now** in the banner; the four cards must read
   38.0 / 18.2 h / 0.88% / 2.0 h.
4. **File -> Save as -> Power BI file (.pbix)** if you need a single-file report.

The project is the authorable form: a PBIR report definition plus a TMDL semantic
model, both plain text and both schema-validated. A `.pbix` is signed by Power BI
Desktop when Desktop writes it, so it cannot be produced outside the app.
`analytics/powerbi/DORA.SemanticModel/` is the generator output that `build_pbip.py`
copies into the project.
"""

BRONZE_NOTE = """# Raw Bronze is intentionally not packaged

The Bronze layer preserves the source sheets exactly, including `author_email`,
`committer_email`, `author_name` and `committer_name`.

Those columns are synthetic case-study values, but packaging them would
redistribute personal-style data for no analytical benefit. The Silver and Gold
layers drop those columns, and every metric in this package is reproducible from
the Silver tables alone.

To regenerate Bronze, place the workbook at `docs/Case Study - DORA Metrics Data.xlsx`
and run:

```powershell
python analytics/run_pipeline.py
```

The ingestion manifest (`bronze_ingestion_metadata.json`) is included so the source
workbook can be identified by SHA-256.
"""


def stage() -> Path:
    staging = ROOT / ".zip_staging" / "DORA_PowerBI_Solution"
    if staging.parent.exists():
        shutil.rmtree(staging.parent)
    analytics = staging / "analytics"
    for relative in ("bronze", "silver", "gold", "dashboard", "powerbi",
                     "quality-checks"):
        (analytics / relative).mkdir(parents=True, exist_ok=True)
    (staging / "docs").mkdir(parents=True, exist_ok=True)
    (staging / "validation").mkdir(parents=True, exist_ok=True)

    (staging / "README.md").write_text(INNER_README, encoding="utf-8")
    (analytics / "bronze" / "README.md").write_text(BRONZE_NOTE, encoding="utf-8")
    shutil.copy(ROOT / "requirements.txt", staging / "requirements.txt")

    for name in ("run_pipeline.py", "generate_dashboard_preview.py", "verify_solution.py"):
        shutil.copy(ANALYTICS / name, analytics / name)
    shutil.copy(ANALYTICS / "quality-checks" / "run_quality_checks.py",
                analytics / "quality-checks" / "run_quality_checks.py")

    for name in ("projects.csv", "builds.csv", "commits.csv", "incidents.csv",
                 "commit_links.csv", "rejected_rows.csv"):
        source = ANALYTICS / "silver" / name
        if source.exists():
            shutil.copy(source, analytics / "silver" / name)

    for name in ("dim_project.csv", "fact_deployment.csv", "fact_commit_link.csv",
                 "fact_incident.csv", "dora_service_month.csv",
                 "dora_period_summary.csv"):
        shutil.copy(ANALYTICS / "gold" / name, analytics / "gold" / name)

    for name in ("dq_results.json", "silver_profile.json"):
        source = ANALYTICS / "quality-checks" / name
        if source.exists():
            shutil.copy(source, analytics / "quality-checks" / name)

    manifest = ANALYTICS / "bronze" / "ingestion_metadata.json"
    if manifest.exists():
        shutil.copy(manifest, analytics / "bronze_ingestion_metadata.json")

    for name in ("DORA_POWER_QUERY.m", "DORA_MEASURES.dax",
                 "POWERBI_DESKTOP_GUIDE.md", "generate_tmdl_model.py",
                 "build_excel_pack.py", "build_pbip.py", "check_references.py",
                 "validate_pbip.py", "DORA_Data.xlsx", "DORA_theme.json"):
        shutil.copy(ANALYTICS / "powerbi" / name, analytics / "powerbi" / name)

    model_source = ANALYTICS / "powerbi" / "DORA.SemanticModel"
    model_target = analytics / "powerbi" / "DORA.SemanticModel"
    shutil.copytree(model_source, model_target)

    project_source = ANALYTICS / "powerbi" / "DORA_Project"
    if project_source.exists():
        shutil.copytree(project_source, analytics / "powerbi" / "DORA_Project")

    for png_name in ("dora_baseline_dashboard.png", "dora_powerbi_desktop.png"):
        png = ANALYTICS / "dashboard" / png_name
        if png.exists():
            shutil.copy(png, analytics / "dashboard" / png_name)

    for name in ("METRIC_SPEC.md", "DATA_QUALITY.md", "METRIC_DICTIONARY.md",
                 "DASHBOARD_VERIFICATION_GUIDE.md"):
        shutil.copy(ROOT / "docs" / name, staging / "docs" / name)


    results = ANALYTICS / "quality-checks" / "dq_results.json"
    summary = {}
    if results.exists():
        payload = json.loads(results.read_text(encoding="utf-8"))
        summary = {
            "generated_at_utc": payload.get("generated_at_utc"),
            "overall_status": payload.get("overall_status"),
            "checks": [
                {"check_id": r["check_id"], "name": r["name"], "status": r["status"]}
                for r in payload.get("results", [])
            ],
        }
    (staging / "validation" / "run_log.txt").write_text(
        "DORA solution validation\n"
        "========================\n\n"
        "Pipeline: bronze -> silver -> gold\n"
        "Quality checks: 3 executable checks\n"
        "Negative test: corrupted gold must fail all three checks\n\n"
        + json.dumps(summary, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return staging


def main() -> None:
    staging = stage()
    if OUTPUT.exists():
        OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if not path.is_file():
                continue
            # .pbi holds per-machine editor state, not part of the deliverable.
            if ".pbi" in path.relative_to(staging).parts:
                continue
            archive.write(path, path.relative_to(staging.parent).as_posix())
    shutil.rmtree(staging.parent, ignore_errors=True)
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
