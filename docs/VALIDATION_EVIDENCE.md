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
| Pipeline Bronze -> Silver -> Gold | Passed: 345 deployments, 152 commit links (149 linkable), 11 incidents, 9 metric rows |
| DQ-01 referential integrity and grain | PASS |
| DQ-02 temporal validity | PASS |
| DQ-03 metric reconciliation | PASS |
| Negative test (`--fixtures`) | All three checks failed as required |
| Dashboard layout reference | Rendered, 2400 x 1350 PNG |
| Power BI project (`DORA_Project/DORA.pbip`) | Generated, 19 visuals on 2 pages; 25/25 definition files schema-valid; all field references resolve; opened in Power BI Desktop with 38.33 / 20.5 h / 0.87% / 2.0 h |
| TMDL semantic model | Generated, 8 tables / 8 relationships / 17 measures, structural self-check passed |
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
| Definition files validate against the Microsoft schemas (`validate_pbip.py`) | 25/25 |
| Every visual field reference resolves to a model column or measure | all resolve |
| Project opens in Power BI Desktop | yes, window title `DORA`, no visual error on either page |
| Cards match Gold after **Refresh now** | 38.33 / 20.5 h / 0.87% / 2.0 h |
| Page 1 inventory | 12 visuals: navy header, title, subtitle, 4 KPI cards, deployment trend, lead-time column chart, 9-row grain table, caveat panel, footer |
| Page 2 inventory | 7 visuals: header, title, subtitle, Bronze/Silver/Gold lineage table, data-quality table, all-column grain table, footer |

The captured windows are `analytics/dashboard/dora_powerbi_desktop.png` (page 1) and
`analytics/dashboard/dora_powerbi_lineage.png` (page 2).

Three problems were found and fixed through this loop rather than assumed away:
`Missing_References` on the Deployment Frequency card and the lead-time chart
(a measure name and a non-existent `Chart Label` column); a Deployment Frequency
measure that divided by distinct months (57.0) instead of project-months (38.33); and
the timestamp-parsing defect described below.
`check_references.py` now catches the first class of bug offline.

## Data defect found and fixed: mixed timestamp precision

The first published numbers were wrong, and the cause was a silent data loss rather
than a formula error. `utc()` called `pd.to_datetime(series, errors="coerce", utc=True)`
with no `format=`. pandas infers a single format from the first non-null value:

- In `builds`, the first `pipeline_end_time` carries microseconds
  (`2024-07-11 06:36:17.100000`), so the 3 rows written without them became `NaT`
  and were dropped as `missing_required_field`.
- In `commits`, the first `author_date` has no microseconds, so the 4 rows that do
  carry them became `NaT` and were dropped the same way.

The effect: 342 instead of 345 builds, 160 instead of 164 commits, 134 instead of 149
lead-time observations, and two project-months understated (B 2024-09 140 vs 141,
B 2024-11 71 vs 73). Every downstream KPI moved: DF 38.0 → 38.33, lead time
18.24 h → 20.49 h, CFR 0.88% → 0.87%, link coverage 84.3% → 98.0%.

Fixed by parsing with `format="mixed"` in `run_pipeline.py`,
`run_quality_checks.py` and `verify_solution.py`. `verify_solution.py` now reconciles
Gold against the source workbook directly ("Every valid source build reached Gold",
"No timestamp is dropped by the parser"), because every earlier check compared Gold to
Silver or to itself and a row lost during ingestion was invisible to them.

## Second defect found and fixed: monthly visuals ignored the grain

After the timestamp fix the cards were right but the lead-time chart was not: it drew
the same ~20.49 h bar for all six months while the table beside it correctly showed
blank, 25.98, 0.57, 22.18 and 18.29.

The cause was the model, not the DAX. `DoraServiceMonth[reporting_month]` was used as
the chart axis, but `DoraServiceMonth` reaches `FactCommitLink` only through
`DimProject`, and both relationships point outward from `DimProject`. A month filter
therefore reached the metric table and stopped there, so
`MEDIAN ( FactCommitLink[lead_time_hours] )` always evaluated over every link and
returned the period-wide median in each month.

Fixed by giving the facts their own date columns and relationships:

- `fact_commit_link.deployed_date` and `fact_incident.started_date` are now published
  in Gold, related to `DimDate[Date]` (8 relationships, up from 6)
- the chart axis is `FactCommitLink[reporting_month]`, the fact's own month, so the
  measure filters correctly and unobserved months stay blank

`verify_solution.py` now asserts that all four facts have a date column related to
`DimDate` and that the lead-time chart's axis belongs to a table with a filter path to
its measure.

## Cross-check against the raw workbook

Recomputed directly from the Excel sheets, independently of the pipeline:

- `commits.build_sk` matches `builds.build_id`; 149 of 152 commit links resolve to a
  completed build, a 98.0% coverage rate.
- 12 associations are chronologically impossible (the build finished before the commit
  was authored) and are rejected, not repaired.
- 5 builds end before they start; rejected. No build is missing a completion time.
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
