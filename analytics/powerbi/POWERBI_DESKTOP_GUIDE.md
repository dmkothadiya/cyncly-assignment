# Power BI Desktop: DORA baseline report

This folder is the Power BI layer of the medallion solution. It contains executable
query assets, a TMDL semantic model, DAX measures, a ready-to-open Power BI project,
and the exact build steps for the report.

## Status and verification

| Item | State |
|---|---|
| Bronze / Silver / Gold data | Generated and verified by `analytics/run_pipeline.py` |
| Data-quality checks | Executed; 3/3 pass, and all 3 fail on injected defects |
| Power Query (M) | Provided, matches the generated column names exactly |
| TMDL semantic model (`DORA.SemanticModel/`, `DORA_Project/DORA.SemanticModel/`) | Generated from the actual Gold columns; structural self-check passes |
| DAX measures | 14 measures, all column references verified against the model |
| Report (`DORA_Project/DORA.pbip`) | **Generated and verified**: 12 visuals, 17/17 definition files schema-valid, all field references resolve, renders in Power BI Desktop |
| Dashboard captures | `analytics/dashboard/dora_powerbi_desktop.png` is a real Desktop screenshot; `dora_baseline_dashboard.png` is the earlier layout reference |

### Report format: PBIP, not `.pbix`

A `.pbix` package is signed by Power BI Desktop when it writes it. Editing or
repacking one by hand invalidates the signature and Desktop refuses to open it
("This file is corrupted or was created by an unrecognized version"), which was
confirmed experimentally with a single added text box.

The supported authoring format is a Power BI project: a PBIR report definition plus
TMDL model, both plain text, both schema-validated by
`analytics/powerbi/validate_pbip.py`. `DORA_Project/DORA.pbip` opens directly in
Desktop and renders the whole page; **File → Save as → Power BI file (\*.pbix)**
converts it to a single file if you need one.

Do not present the layout-reference PNG as a Power BI screenshot. Use
`dora_powerbi_desktop.png` for that - it is the real application window.

## 0. The generated semantic model

`DORA.SemanticModel/` is a TMDL model item (`definition.pbism` + `definition/`):

| Table | Rows | Notes |
|---|---|---|
| `DimProject` | 4 | includes `unmapped::` members for orphan incidents |
| `DimDate` | generated | 2024-01-01 to 2025-12-31, mark as date table |
| `FactDeployment` | 342 | one row per completed build |
| `FactCommitLink` | 159 | commit x deployment associations (134 linkable) |
| `FactIncident` | 11 | incidents with restore hours |
| `DoraServiceMonth` | 9 | published metric grain, plus 14 measures |

Six relationships, all single-direction: `DimProject` to each fact and
`DoraServiceMonth`, and `DimDate` to `DoraServiceMonth[month_start]` and
`FactDeployment[deployment_date]`. `GoldFolder` is a text parameter pointing at
`analytics/gold`.

Regenerate it after any pipeline change:

```powershell
python analytics/powerbi/generate_tmdl_model.py
```

**How to consume it:** open `DORA_Project/DORA.pbip` - Desktop loads this model and
the report together. The bare TMDL folder `DORA.SemanticModel/` is the generator
output that `build_pbip.py` copies into the project; it is not openable on its own.
The manual build in section 2 onward remains available if you prefer to construct the
model by hand.

## 1. Refresh the data first

From the repository root:

```powershell
python -m pip install -r requirements.txt
python analytics/run_pipeline.py
python analytics/quality-checks/run_quality_checks.py
```

Gold outputs land in `analytics/gold/`. Never point Power BI at Bronze or Silver
for the dashboard: those layers exist to be traced, not reported.

## 2. Connect

The fastest path needs no connection work at all: open
`DORA_Project/DORA.pbip`, press **Refresh now**, and the model, relationships and
page are already there. To build the model by hand instead:

- use **Home > Transform data > Advanced Editor** and paste each query from
  `DORA_POWER_QUERY.m`, creating the `GoldFolder` parameter first, or
- import the five tables from `DORA_Data.xlsx` with **Get data > Excel workbook**.

Set `GoldFolder` to the absolute path of `analytics/gold` on your machine.

## 3. Build the semantic model

Import these six tables: `DimProject`, `DimDate`, `FactDeployment`,
`FactCommitLink`, `FactIncident`, `DoraServiceMonth`.

Relationships (all single direction):

| From | To | Cardinality |
|---|---|---|
| `DimProject[project_sk]` | `DoraServiceMonth[project_sk]` | 1 to many |
| `DimProject[project_sk]` | `FactDeployment[project_sk]` | 1 to many |
| `DimProject[project_sk]` | `FactCommitLink[project_sk]` | 1 to many |
| `DimProject[project_sk]` | `FactIncident[project_sk]` | 1 to many |
| `DimDate[Date]` | `DoraServiceMonth[month_start]` | 1 to many |
| `DimDate[Date]` | `FactDeployment[deployment_date]` | 1 to many |

Then: **Table tools > Mark as date table > DimDate[Date]**, and hide the
technical keys (`project_sk`, `grain`, `notes`) from the report view.

Add the measures from `DORA_MEASURES.dax`.

## 4. Report page: "DORA baseline"

Page size 16:9, background `#FFFFFF`, header band `#16324F`.

| Zone | Visual | Fields |
|---|---|---|
| Header | Text box | "DORA baseline - 2024 H2" + `Deployment Proxy Note` measure |
| KPI row | 4 x Card | `Deployment Frequency (per month)`, `Lead Time for Changes (median h)`, `Change Failure Rate %`, `MTTR (median h)` |
| Trend | Line chart | Axis `DimDate[Month]`, values the four KPI measures, small multiples off |
| Comparison | Matrix | Rows `DimProject[project_name]`, columns `DoraServiceMonth[reporting_month]`, values `Deployment Frequency (per day)` |
| Trust panel | Card + table | `Sample Size Note`, `Data Quality Status`, and a table of `reporting_month`, `lead_time_sample_size`, `mttr_sample_size`, `data_quality_status` |
| Slicers | 2 slicers | `DimDate[Year]`, `DimProject[project_name]` |

Formatting rules:

- Conditional formatting on `Data Quality Status`: `Validated` -> green
  `#1E6B4E`, anything else -> amber `#8A5A00`.
- Show the sample-size note on the same page as the KPI cards, always. A metric
  without its `n` invites the argument you are trying to end.
- Sort `reporting_month` by `month_start`, not alphabetically.

Do not add a gauge, target line or trend arrow unless a target has been agreed
with the metric owner. The source supports a baseline, not a scorecard.

## 5. Metric contract

Grain, formulas, sources, rules, ownership and limitations live in
[`docs/METRIC_SPEC.md`](../../docs/METRIC_SPEC.md). The dashboard must not publish
a definition that contradicts it.

## 6. Refresh and share

- Data refresh is a file refresh: rerun the pipeline, then **Home > Refresh**.
- For scheduled refresh you need a gateway or a hosted copy of the Gold files.
  That is a licensing and infrastructure decision, not something this folder
  assumes.
- Publishing to the Power BI service requires a workspace and appropriate
  licensing. Local authoring in Power BI Desktop does not.

## 7. Known limitations

1. Deployment frequency counts completed pipeline runs; the source has no
   environment or release event, so this is a documented proxy.
2. Change failure rate matches incidents flagged `caused_by_deployment` to the
   project-month deployment count. There is no event-level deployment link.
3. MTTR is blank for any project-month without a deployment-caused incident -
   blank means "not observed", never zero.
4. Three incidents reference projects that are not in the project sheet; they are
   held against an `unmapped::` dimension member so the loss is visible.
5. Lead time is computed at commit-to-build association grain, so a commit that
   was rebuilt several times contributes once per build.
