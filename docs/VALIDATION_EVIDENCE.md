# Validation Evidence

## Environment

Windows, .NET SDK 8.0.100, Python 3.13, pandas 3.1, openpyxl 3.1, Pillow,
Power BI Desktop (Store build 2.159.883.0).

## Commands executed

```powershell
$env:Path = "$HOME\.dotnet;" + $env:Path

dotnet restore CynclyAssignment.sln
dotnet build CynclyAssignment.sln --configuration Release
dotnet test CynclyAssignment.sln --configuration Release --collect:"XPlat Code Coverage" --results-directory TestResults

python analytics/run_pipeline.py
python analytics/quality-checks/run_quality_checks.py
python analytics/quality-checks/run_quality_checks.py --fixtures
python analytics/powerbi/generate_tmdl_model.py
python analytics/powerbi/build_pbip.py
python analytics/powerbi/validate_pbip.py
python analytics/generate_dashboard_preview.py
python analytics/verify_solution.py
python analytics/package_solution.py
```

## Results

| Item | Result |
|---|---|
| .NET restore / Release build | Passed |
| .NET unit tests | 4/4 passed, coverage file generated |
| Pipeline Bronze -> Silver -> Gold | Passed: 342 deployments, 159 commit links (134 linkable), 11 incidents, 9 metric rows |
| DQ-01 referential integrity and grain | PASS |
| DQ-02 temporal validity | PASS |
| DQ-03 metric reconciliation | PASS |
| Negative test (`--fixtures`) | All three checks failed as required |
| Dashboard layout reference | Rendered, 2400 x 1350 PNG |
| Power BI project (`DORA_Project/DORA.pbip`) | Generated, 12 visuals; 17/17 definition files schema-valid; all field references resolve; opened in Power BI Desktop with 38.0 / 18.2 h / 0.88% / 2.0 h |
| TMDL semantic model | Generated, 6 tables / 6 relationships / 14 measures, structural self-check passed |
| Review package | Regenerated with the model included |

## Power BI Desktop status

Power BI Desktop **is** installed (Store build 2.159.883.0). An earlier version of
this document said it was not available; that was wrong and is corrected here.

The report is authored as a **Power BI project** (`analytics/powerbi/DORA_Project/`):
a PBIR report definition plus a TMDL semantic model, both plain text. A `.pbix` is
signed by Desktop when Desktop writes it, so a hand-built package is rejected as
"corrupted or created by an unrecognized version" - verified by adding one text box
to a copy and repacking it. The project is therefore the authorable artefact, and
**File → Save as → Power BI file (\*.pbix)** converts it inside Desktop.

Verified on the authoring machine:

| Check | Result |
|---|---|
| Definition files validate against the Microsoft schemas (`validate_pbip.py`) | 17/17 |
| Every visual field reference resolves to a model column or measure | all resolve |
| Project opens in Power BI Desktop | yes, window title `DORA`, no visual error |
| Cards match Gold after **Refresh now** | 38.0 / 18.2 h / 0.88% / 2.0 h |
| Page inventory | 12 visuals: navy header, title, subtitle, 4 KPI cards, deployment trend, lead-time column chart, 9-row grain table, caveat panel, footer |

The captured window is `analytics/dashboard/dora_powerbi_desktop.png`.

Two problems were found and fixed through this loop rather than assumed away:
`Missing_References` on the Deployment Frequency card and the lead-time chart
(a measure name and a non-existent `Chart Label` column), and a Deployment Frequency
measure that divided by distinct months (57.0) instead of project-months (38.0).
`check_references.py` now catches the first class of bug offline.

## Cross-check against the raw workbook

Recomputed independently from the Excel sheets before building the pipeline:

- `commits.build_sk` matches `builds.build_id`; commit links resolve to a completed
  build at 84% coverage.
- One association is chronologically impossible (build finished before the commit
  was authored) and is rejected, not repaired.
- 8 builds have no completion timestamp and 5 have end before start; all rejected.
- 3 incidents belong to projects absent from the project sheet and are held under
  unmapped dimension members.
- 3 deployment-caused incidents all report a 2.03 h restore time, so MTTR is
  published as indicative only.

## Correction recorded

An earlier version of `METRIC_DICTIONARY.md` claimed the workbook had no usable
commit-to-deployment join and left lead time blank. That claim was wrong; lead time
is now computed and the correction is recorded in
[`METRIC_DICTIONARY.md`](METRIC_DICTIONARY.md) and
[`METRIC_SPEC.md`](METRIC_SPEC.md).

## Evidence limitations

- GitHub Actions remote execution was not run against an external repository here.
- The report has been rendered and read back in Power BI Desktop, but publishing to
  the Power BI service and scheduled refresh were not verified - neither exists for a
  local project.
- The `.pbix` single-file format was not produced here. Desktop only writes it; the
  project is the authorable form and converts in one menu action.
- The case-study workbook is synthetic and is not a production source of truth.

## Reproduction

```powershell
python -m pip install -r requirements.txt
python analytics/run_pipeline.py
python analytics/quality-checks/run_quality_checks.py
python analytics/quality-checks/run_quality_checks.py --fixtures
```

Expected: the first check run exits 0 with `3/3 checks passed`; the negative test
exits 0 after reporting that all three checks detected the injected defects.
