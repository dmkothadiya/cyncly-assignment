# Dashboard Verification Guide

How to verify the DORA dashboard end to end: the data, the four metrics, the quality
gates, the semantic model, and the report itself.

Verification is in five levels. Each level can fail independently, so work top to
bottom — a wrong number at level 2 makes every visual at level 5 wrong in a way you
cannot see by looking at the screen.

| Level | What is being verified | Command or step |
|---|---|---|
| 1 | Data exists and is the expected shape | Steps 1-2 |
| 2 | Metrics recompute from the facts | Step 3 |
| 3 | Quality gates pass and can fail | Steps 4-5 |
| 4 | Semantic model is structurally sound | Step 6 |
| 5 | The rendered report matches the numbers | Steps 7-8 |

Want to open it right now? Jump to [Step 7](#step-7---open-it-in-power-bi-desktop).
The Power BI project `analytics/powerbi/DORA_Project/DORA.pbip` is already built and
verified, so opening it and refreshing is the whole job.

---

## Step 0 - One command that checks almost everything

```powershell
python analytics/verify_solution.py
```

Expected: `RESULT: 21/21 checks passed` and exit code 0.

It verifies, without trusting the published table:

- the six Gold tables and the Power BI assets exist
- all four metrics recompute from the fact tables
- six known-answer spot checks against values confirmed from the raw workbook
- grain rows sum to the published total
- the three quality checks passed
- source deduplication was recorded rather than applied silently
- every field reference in the report resolves to a model column or measure
- the Deployment Frequency measure divides by project-months, not by distinct months

If this fails, stop. Everything downstream inherits the failure.

---

## Step 1 - Regenerate the data

```powershell
python -m pip install -r requirements.txt
python analytics/run_pipeline.py
```

Expected output:

```
Bronze: commits=164, builds=350, incidents=11, projects=2
Silver: builds=345, commits=164, incidents=11
Gold:   grain rows=9, projects=2, months=6
```

Why the row counts differ at each layer — and they should:

| Layer | Count | Reason |
|---|---|---|
| Bronze builds | 350 | raw sheet |
| Silver builds | 345 | 5 builds end before they start |
| Bronze commits | 164 | raw sheet, includes re-reported snapshots |
| Silver commits | 160 | duplicate (commit, build) pairs resolved by latest ingestion |
| Gold grain | 9 | 2 projects x 6 months, minus months with no builds |

If a number moves, treat it as a regression until proven otherwise.

---

## Step 2 - Inspect the Gold outputs

```powershell
Get-ChildItem analytics/gold
Get-Content analytics/gold/dora_period_summary.csv
```

Expect six files: `dim_project`, `fact_deployment`, `fact_commit_link`,
`fact_incident`, `dora_service_month`, `dora_period_summary`.

The period summary must read:

| Field | Expected |
|---|---|
| `total_deployments` | 345 |
| `deployment_frequency_per_month` | 38.33 |
| `lead_time_median_hours` | 20.49 |
| `lead_time_sample_size` | 149 |
| `commit_link_coverage_pct` | 98.03 |
| `change_failure_rate_pct` | 0.87 |
| `deployment_related_incidents` | 3 |
| `mttr_median_hours` | 2.03 |
| `mttr_sample_size` | 3 |

---

## Step 3 - Verify the formulas yourself

Do not take the pipeline's word for it. Recompute one grain row from the facts:

```powershell
python -c "import pandas as pd; d=pd.read_csv('analytics/gold/fact_deployment.csv'); print(len(d[(d.project_name=='Project A') & (d.reporting_month=='2024-08')]))"
```

Expected `10` — matching `deployment_count` for Project A, 2024-08.

```powershell
python -c "import pandas as pd; l=pd.read_csv('analytics/gold/fact_commit_link.csv'); v=l[(l.is_valid_lead_time==True) & (l.project_sk.str.startswith('c099'))]; v['m']=pd.to_datetime(v.deployed_at,utc=True).dt.tz_localize(None).dt.to_period('M').astype(str); print(v[v.m=='2024-12'].lead_time_hours.median().round(2), len(v[v.m=='2024-12']))"
```

Expected `18.29 77` — matching Project B, 2024-12.

| Grain row | Deployments | Lead time (n) | CFR | MTTR (n) |
|---|---|---|---|---|
| Project A, 2024-08 | 10 | n/a | 30.0% | 2.03 h (3) |
| Project B, 2024-09 | 140 | 2.00 h (7) | 0.0% | n/a |
| Project B, 2024-11 | 71 | 22.18 h (46) | 0.0% | n/a |
| Project B, 2024-12 | 35 | 18.29 h (77) | 0.0% | n/a |

`n/a` is correct where no observation exists. It is never zero.

---

## Step 4 - Run the three quality checks

```powershell
python analytics/quality-checks/run_quality_checks.py
```

Expected: `RESULT: 3/3 checks passed`, exit code 0, and
`analytics/quality-checks/dq_results.json` with `"overall_status": "PASS"`.

Check the reported counts, not just the status:

| Check | Field | Expected |
|---|---|---|
| DQ-01 | `projects` | 4 (2 real + 2 `unmapped::` for orphan incidents) |
| DQ-01 | `duplicate_rows_by_key` | all zero |
| DQ-02 | `commit_links_checked` | 149 |
| DQ-02 | `commit_links_negative_lead_time` | 0 |
| DQ-03 | `deployments_in_grain` / `_in_summary` | 345 / 345 |

---

## Step 5 - Prove the checks can actually fail

A green tick means nothing if the check cannot go red.

```powershell
python analytics/quality-checks/run_quality_checks.py --fixtures
```

Expected: `0/3 checks passed`, each check naming its own injected defect
(duplicate grain row, negative lead time, inflated deployment count), and exit code 0
because the negative test itself succeeded.

If a check passes here, that check is decorative — fix it before trusting Step 4.

---

## Step 6 - Verify the semantic model

```powershell
Get-ChildItem analytics/powerbi/DORA.SemanticModel/definition/tables
Select-String -Path analytics/powerbi/DORA.SemanticModel/definition/relationships.tmdl -Pattern 'fromColumn|toColumn'
```

Expect 8 table files and 8 relationships:

| From | To | Why it matters |
|---|---|---|
| `FactDeployment.project_sk` | `DimProject.project_sk` | project filtering |
| `FactCommitLink.project_sk` | `DimProject.project_sk` | project filtering |
| `FactIncident.project_sk` | `DimProject.project_sk` | project filtering |
| `DoraServiceMonth.project_sk` | `DimProject.project_sk` | project filtering |
| `DoraServiceMonth.month_start` | `DimDate.Date` | month filtering of the metric table |
| `FactDeployment.deployment_date` | `DimDate.Date` | month filtering of deployments |
| `FactCommitLink.deployed_date` | `DimDate.Date` | **month filtering of lead time** |
| `FactIncident.started_date` | `DimDate.Date` | **month filtering of CFR and MTTR** |

The last two are easy to miss and their absence is invisible until you look at a
monthly visual: with only the `DimProject` path, a month slicer reaches
`DoraServiceMonth` but never reaches the facts, so every month shows the period-wide
value. That is exactly the bug that made the lead-time chart repeat 20.49 h in all six
months while the table showed the correct per-month numbers.

> **Verify:** six of the eight relationships must point at `DimDate.Date` or
> `DimProject.project_sk`; every fact table must appear at least once with a date
> column.

Then confirm the types did not silently change:

```powershell
Select-String -Path analytics/powerbi/DORA.SemanticModel/definition/tables/FactDeployment.tmdl -Pattern 'column deployment_id' -Context 0,2
```

`deployment_id` must be `string`, not a number. Identifiers that become numbers lose
leading zeros and get summed by accident.

---

## Step 7 - Open it in Power BI Desktop

Three routes. **Route 0 needs no clicks** - the report is already built and verified;
you only open it and refresh. Routes A and B exist for the case where you want to
rebuild the page by hand.

### Route 0 - open the prebuilt project (fastest, verified)

`analytics/powerbi/DORA_Project/DORA.pbip` is a text-based Power BI project (PBIR
report + TMDL semantic model). Double-click it, or **File → Open** in Power BI
Desktop. Everything both pages need is already authored: 19 visuals, 8 tables,
8 relationships, 17 measures.

1. Open `analytics/powerbi/DORA_Project/DORA.pbip`.
2. Wait for the **Load** dialog. Each table shows *Evaluating...* while the CSV files
   are read; the whole load takes well under a minute.
3. If the yellow banner **"Some of the tables have incomplete or no data"** is still
   visible, click **Refresh now** in the banner. That banner appears before the first
   data load completes and is not an error.
4. The four cards must read **38.33 / 20.5 h / 0.87% / 2.0 h**.
5. Check the lead-time chart: it must show **four** bars (2024-09 to 2024-12), not six
   identical ones. Six equal bars means a monthly visual lost its filter path.
6. Open the second page, **Grain, lineage & quality**: the Bronze/Silver/Gold table,
   the three DQ results and all 16 published columns are there.
7. **File → Save as → Power BI file (\*.pbix)** to produce the single-file dashboard,
   then verify it with the command in Step 8.

The rendered pages are captured in
[`analytics/dashboard/dora_powerbi_desktop.png`](../analytics/dashboard/dora_powerbi_desktop.png)
and [`dora_powerbi_lineage.png`](../analytics/dashboard/dora_powerbi_lineage.png) -
those images are real screenshots of Power BI Desktop showing this project, not
mock-ups.

What is already proven for this route (see `docs/VALIDATION_EVIDENCE.md`):

| Check | Result |
|---|---|
| PBIR/TMDL definition files validate against the Microsoft schemas | 25/25 |
| Every visual field reference resolves to a model column or measure | all resolve |
| Report renders in Power BI Desktop without a visual error | yes, both pages |
| Cards match the Gold numbers | 38.33 / 20.5 h / 0.87% / 2.0 h |
| Monthly lead-time bars match the grain table | 25.98 / 0.57 / 22.18 / 18.29 |

To regenerate the project after a pipeline change:

```powershell
python analytics/powerbi/generate_tmdl_model.py
python analytics/powerbi/build_pbip.py
python analytics/powerbi/validate_pbip.py     # schemas + field references
```

### Route A - rebuild from one workbook (~10 minutes)

Pre-built for you: `analytics/powerbi/DORA_Data.xlsx` -
`DimProject` 4 rows, `FactDeployment` 345, `FactCommitLink` 152, `FactIncident` 11,
`DoraServiceMonth` 9. It also carries the two date columns the model needs
(`month_start`, `deployment_date`), so no Power Query editing is required.

The workbook is plain data - five sheets, no queries, no model. It must be pulled in
through **Get data**, never opened directly with Power BI.

**7.1 Connect**

> Do **not** double-click the workbook, and do not pass it to `PBIDesktop.exe` as an
> argument. Power BI interprets a workbook opened that way as an *Excel workbook that
> contains Power BI queries or a model* and fails with **"Migration failed: the
> following Excel workbook doesn't contain any queries or a model to import"**.
> The workbook is plain data, so it must be connected through **Get data**.

1. Open **Power BI Desktop** → **Blank report**.
2. **Home → Get data → Excel workbook**.
3. Browse to `analytics/powerbi/DORA_Data.xlsx` → **Open**.
4. In the Navigator, tick all five sheets: `DimProject`, `FactDeployment`,
   `FactCommitLink`, `FactIncident`, `DoraServiceMonth`.
5. Click **Transform Data** (not Load) → the Power Query Editor opens.
6. Verify each sheet shows the expected column count and that dates have a calendar
   icon. Then **Close & Apply**.

> **Verify:** the Data pane on the right lists five tables. Row counts match
> 4 / 345 / 152 / 11 / 9. If `deployment_id` shows a sigma symbol, its type is
> numeric - select the column, **Transform → Data Type → Text**.

**7.2 Create the date table**

**Modeling → New table**, paste and confirm:

```dax
DimDate =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2024, 1, 1 ), DATE ( 2025, 12, 31 ) ),
    "Year", YEAR ( [Date] ),
    "Month Number", MONTH ( [Date] ),
    "Month", FORMAT ( [Date], "MMM" ),
    "Month Key", FORMAT ( [Date], "yyyy-MM" )
)
```

Then select the `DimDate` table → **Table tools → Mark as date table** → column
`Date` → **OK**.

> **Verify:** `DimDate` has 731 rows (2024-01-01 to 2025-12-31) and the date-table
> icon appears next to the table name.

**7.3 Create the relationships**

**Model view** (left rail, third icon). Drag the column from one table onto the other;
each dialog should read *Cardinality: One to many*, *Cross filter direction: Single*.

| Drag this column | Onto this column |
|---|---|
| `DimProject[project_sk]` | `DoraServiceMonth[project_sk]` |
| `DimProject[project_sk]` | `FactDeployment[project_sk]` |
| `DimProject[project_sk]` | `FactCommitLink[project_sk]` |
| `DimProject[project_sk]` | `FactIncident[project_sk]` |
| `DimDate[Date]` | `DoraServiceMonth[month_start]` |
| `DimDate[Date]` | `FactDeployment[deployment_date]` |

> **Verify:** six lines, arrowheads pointing away from `DimProject` and `DimDate`.
> If Power BI offers a *many-to-many* relationship, a key has the wrong type -
> go back to 7.1 and fix the type, do not accept it.

**7.4 Add the measures**

For each row below: right-click `DoraServiceMonth` in the Data pane →
**New measure** → paste the DAX → **Enter**. The remaining eight measures in
`DORA_MEASURES.dax` are optional extras.

| Measure name | DAX |
|---|---|
| `Deployments` | `SUM ( DoraServiceMonth[deployment_count] )` |
| `Deployment Frequency (per project-month)` | `AVERAGE ( DoraServiceMonth[deployment_count] )` |
| `Lead Time for Changes (median h)` | `CALCULATE ( MEDIAN ( FactCommitLink[lead_time_hours] ), FactCommitLink[is_valid_lead_time] = TRUE () )` |
| `Change Failure Rate %` | `DIVIDE ( SUM ( DoraServiceMonth[failed_deployments] ), [Deployments] )` |
| `MTTR (median h)` | `CALCULATE ( MEDIAN ( FactIncident[restore_hours] ), FactIncident[caused_by_deployment] = 1 )` |
| `Sample Size Note` | `"Lead time n=" & FORMAT ( CALCULATE ( COUNTROWS ( FactCommitLink ), FactCommitLink[is_valid_lead_time] = TRUE () ), "#,##0" ) & "  \|  MTTR n=" & FORMAT ( CALCULATE ( COUNTROWS ( FactIncident ), FactIncident[caused_by_deployment] = 1 ), "#,##0" )` |

Set formats: `Deployments` whole number, frequency `0.0`, lead time `0.0 "h"`,
change failure rate `0.00%`, MTTR `0.0 "h"`.

> **Verify immediately:** drop `Deployments` on a blank canvas. It must read **345**.
> `Deployment Frequency (per project-month)` must read **38.33**. If Deployments shows
> something else, the table or the column is wrong - stop and fix it here rather than
> debugging a visual later.

**7.5 Build the page**

Report view. **View → Page view → Actual size**, then **Format page → Canvas settings
→ 16:9** (1280 x 720). The reference image
`analytics/dashboard/dora_baseline_dashboard.png` is 1600 x 900 - the same ratio.

**7.5.1 Load the theme (optional, sets the colours once)**

**View → Themes → Browse for themes** → `analytics/powerbi/DORA_theme.json`.
This makes series 1 teal `#1F6F78` and series 2 purple `#7A5CA0`, matching the image.
Also set **View → Snap to grid** on.

**7.5.2 Add two calculated columns for the bar chart**

The bar chart in the reference has one bar per *observed* project-month, labelled
"B Sep", "B Oct", "B Nov", "B Dec". Create them on `DoraServiceMonth`
(right-click table → **New column**):

```dax
Month Label = FORMAT ( DoraServiceMonth[month_start], "MMM" )
```

```dax
Chart Label = RIGHT ( DoraServiceMonth[project_name], 1 ) & " " & [Month Label]
```

Then select `Chart Label` → **Column tools → Sort by column → `month_start`**, so the
labels sort by date rather than alphabetically.

**7.5.3 Lay out the page**

Positions are for a 1280 x 720 canvas; use the Format pane's X / Y / Width / Height.

| # | Element | Visual | X | Y | W | H |
|---|---|---|---|---|---|---|
| 1 | Header band | Shape → Rectangle | 0 | 0 | 1280 | 70 |
| 2 | Title | Text box | 20 | 12 | 900 | 30 |
| 3 | Subtitle | Text box | 20 | 42 | 900 | 20 |
| 4 | KPI 1-4 | Card (new) ×4 | 20 / 326 / 632 / 938 | 82 | 302 | 96 |
| 5 | Trend | Line chart | 20 | 192 | 700 | 192 |
| 6 | Lead time | Clustered column chart | 736 | 192 | 524 | 192 |
| 7 | Grain table | Table | 20 | 398 | 700 | 196 |
| 8 | Caveats | Text box | 736 | 398 | 524 | 196 |
| 9 | Footer | Text box | 20 | 606 | 1240 | 20 |

**7.5.4 Configure each element**

**1-3. Header.** Rectangle: fill `#16324F`, no border, no shadow. Title text box:
white, bold, 20 pt, text `DORA baseline  |  July - December 2024`. Subtitle: `#C9D6E3`,
10 pt, text `2 projects  |  345 completed builds  |  2024-07 to 2024-12  |  deployment proxy, not a release event`.

> **Verify:** in the generated project the subtitle is computed from Gold, so it cannot
> disagree with the cards. If you are rebuilding by hand, type 345.

**4. KPI cards.** Use the **Card (new)** visual, because it supports a reference label
under the value, which is how the image shows "median | n=149".

- Value: the measure (`Deployment Frequency (per project-month)`, `Lead Time for Changes
  (median h)`, `Change Failure Rate %`, `MTTR (median h)`).
- **Format → Callout value**: font 30, bold, colour `#16324F`.
- **Format → Category label** (the title): turn on, custom text, 9 pt bold, colour
  `#4A5568`, uppercase - e.g. `DEPLOYMENT FREQUENCY`.
- **Format → Reference labels**: add a second field for the sub-line:
  `Deployments` for card 1, `Sample Size Note` for card 2, `Failed Deployments` for
  card 3, `MTTR Sample` for card 4.
- **Format → Background**: `#F2F5F8`, transparency 0. Border off.
- Add a 4 px accent rectangle on the left edge: `#1F6F78` for cards 1-2, `#8A5A00` for
  cards 3-4.

If your Desktop build lacks Reference labels, use the classic **Card** plus a small
text box underneath with the sample-size measure.

> **Verify:** 38.33 · 20.5 h · 0.87 % · 2.0 h.

**5. Line chart.** Title off (the header text box carries it) - or set the visual title
to `Deployment volume by project and month`.
- X axis: `DoraServiceMonth[month_start]`
- Y axis: `Deployments`
- Legend: `DoraServiceMonth[project_name]`

Format: **Markers** on, size 3; **Line width** 2; **Y axis** start 0; **X axis** type
`Continuous`, format `MMM`; gridlines Y only, colour `#CBD5E0`; title fonts 10 pt `#16324F`.

> **Verify:** six points per series (Jul-Dec), Project B peaking at **140** in September.
> If the X axis shows `2024-07` strings, the column is text - use `month_start`.

**6. Lead time column chart.** Title `Lead time, median hours (where observed)`.
- X axis: `DoraServiceMonth[Chart Label]`
- Y axis: `Lead Time for Changes (median h)`
- **Filters on this visual → `Lead Time for Changes (median h)` → is not blank**

Format: data colour `#1F6F78`, data labels on (0.0), X axis 8.5 pt, gridlines light.

> **Verify:** exactly **four** bars - B Sep **2.0**, B Oct **0.6**, B Nov **22.2**,
> B Dec **18.3**. Nine bars means the blank filter is missing; three bars means the
> relationship or the valid-flag filter is wrong.

> Note: the reference image uses a column chart with short bars for 2.0 and 0.6 and
> tall bars for 22.2 and 18.3. If you prefer the image's horizontal look, use
> **Clustered bar chart** instead - same fields, axis on the left.

**7. Grain table.** **Table** visual, fields in this order, then use
**Rename for this visual** to match the header row:

| Field | Summarisation | Header |
|---|---|---|
| `project_name` | Don't summarize | Project |
| `reporting_month` | Don't summarize | Month |
| `deployment_count` | Sum | Builds |
| `lead_time_median_hours` | **Don't summarize** | Lead h |
| `lead_time_sample_size` | **Don't summarize** | n |
| `change_failure_rate_pct` | **Don't summarize** | CFR % |
| `mttr_median_hours` | **Don't summarize** | MTTR h |
| `data_quality_status` | Don't summarize | Status |

"Do not summarize" matters: these columns are already per-grain values. Summing
`change_failure_rate_pct` would produce a meaningless 88.9.

Format: header background `#16324F`, header text white 9.5 pt; values 9.5 pt; grid rows
off, banded rows on with `#F2F5F8`.

> **Verify:** nine rows, and the Builds column sums to **345**.

**8. Caveat panel.** Text box with fill `#F2F5F8`, no border, plus a 4 px rectangle on
the left in `#8A5A00`. Contents:

```
READ BEFORE QUOTING
- Builds are a deployment proxy - no release or environment event exists in the source.
- Change failure rate matches incidents to the project-month, not to a specific deployment.
- MTTR rests on 3 incidents; treat as indicative.
- Blank means not observed. It is never zero.
```

**9. Footer.** Text box, 8 pt `#4A5568`:
`Layout reference rendered from the Gold layer - not a Power BI screenshot. Data quality: 3/3 data-quality checks passed.`
Right-aligned: `Source: Case Study - DORA Metrics Data.xlsx`.

**7.6 Save**

**File → Save as** → `analytics/powerbi/DORA_DASHBOARD.pbix` inside the repo. Saving
inside the repo is what lets Step 8 inspect the real file.

### Route B - CSV and M queries

Paste the six queries from `DORA_POWER_QUERY.m` into a blank report via
**Transform data → Advanced Editor**, setting `GoldFolder` to the absolute path of
`analytics/gold`. Then continue from 7.3.
`DORA_POWER_QUERY.m` already computes `month_start`, so 7.2 is optional here.

### What the page must show

The report is wrong until every line matches:

| Visual | Field | Must read | If it does not |
|---|---|---|---|
| Card | Deployment Frequency (per project-month) | **38.33** | `deployment_count` summed twice, or grain duplicated |
| Card | Lead Time for Changes (median h) | **20.5 h** | `is_valid_lead_time` filter missing |
| Card | Change Failure Rate % | **0.87%** | failed incidents joined to the wrong table |
| Card | MTTR (median h) | **2.0 h** | incidents not filtered to `caused_by_deployment = 1` |
| Line chart | points per month | 6 months, 2 series | month axis is text, not a date |
| Column chart | bars | 6 bars, one per month (2024-07 to 2024-12) | month axis came through as text, or the valid-flag filter dropped rows |
| Grain table | rows | 9 rows, Builds column totals **345** | grain duplicated, or a rate column summed |
| Header / footer text | derived from Gold | 345 and "3/3 data-quality checks passed" | the project computes these, so a stale value means Gold is stale |
| *(optional)* Matrix | project x month | 9 populated cells, total **345** | relationship missing or many-to-many |
| *(optional)* Slicer | Project A only | 13 deployments, CFR 23.1%, MTTR 2.0 h | cross-filter direction is not Single |
| *(optional)* Slicer | year 2024 only | 345 deployments (all data is 2024) | date table not related |

The reference image has no slicers - add them only if you want to demonstrate filter
propagation during a review; they are the fastest way to prove the relationships work.

Two manual checks worth doing once:

- **Blank, not zero.** Filter the matrix to Project B, 2024-09. MTTR must be blank,
  never 0. A zero means something is filling gaps.
- **Context propagates.** With no slicer, `Deployments` = 345; select Project A and it
  must fall to 13 (2 + 10 + 1). If it stays 345, the relationships are missing.

---

## Step 8 - Verify the saved `.pbix` programmatically

Once the file exists:

```powershell
python analytics/verify_solution.py --pbix analytics/powerbi/DORA_DASHBOARD.pbix
```

This re-runs every Step 0 check and additionally inspects inside the `.pbix`:

| Check | Passes when |
|---|---|
| Four DORA measures exist in the model | all four measure names are found in `DataModelSchema` |
| Expected tables are in the model | `DoraServiceMonth`, `FactDeployment`, `FactCommitLink`, `FactIncident`, `DimProject` present |
| Report page contains visuals | at least 4 visual definitions in `Report/Layout` |

It reads the package, not a screenshot. If the file cannot be read, the message says
so instead of guessing.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Yellow banner **"Some of the tables have incomplete or no data"** on first open | the tables have not been loaded yet; the banner can persist until a refresh runs | click **Refresh now** in the banner |
| The **Load** dialog sits on *Evaluating...* for minutes | a mashup container from a previous session is still running, or a stale instance holds the model | close Power BI Desktop, end any `Microsoft.Mashup.Container.*` processes, reopen the `.pbip`, then **Refresh now** |
| Visual says **"Something's wrong with one or more fields"** | a visual references a table, column or measure the model does not expose; Power BI reports the code `Missing_References` | run `python analytics/powerbi/validate_pbip.py` - it resolves every visual reference against the TMDL and names the missing field |
| TMDL error `Failed to convert the value 'dateTimeZone' to the expected type DataType` | the tabular model has no `dateTimeZone` type, only `dateTime` | keep `dataType: dateTime` and drop the offset in M (`DateTimeZone.RemoveZone ( DateTimeZone.FromText ( _ ) )`) - already handled by `generate_tmdl_model.py` |
| **"Migration failed - the following Excel workbook doesn't contain any queries or a model to import"** | the `.xlsx` was opened by double-click or passed as a command-line argument, so Power BI tried to import a Power BI model from it | **Close** the dialog, then **Home → Get data → Excel workbook → DORA_Data.xlsx**. The workbook is plain data; there is no model to import |
| `RESULT: 0/3` on the normal quality run | pipeline not rerun after an edit | rerun Step 1 |
| `dq_results.json not found` | checks never executed | Step 4 |
| Card shows a number but the table is blank | missing relationship | Step 6 |
| Lead time card blank | `is_valid_lead_time` filter missing, or no rows in context | compare with Step 3 |
| MTTR shows 0.00 instead of blank | zero-fill in DAX or in the query | remove `?? 0` style handling |
| Deployment count inflated | `fact_commit_link` joined to deployments without care | count distinct `deployment_id` |
| `.pbix` inspection says measures not found | measure names edited in Desktop | rename to match `DORA_MEASURES.dax`, or update the checker |

---

## What this guide cannot verify

- That the page *looks* right to a human reviewer. Route 0 has been rendered and read
  back in Power BI Desktop (see `analytics/dashboard/dora_powerbi_desktop.png`), so the
  numbers and the visual inventory are confirmed; aesthetics remain a judgement call.
- Scheduled refresh or publishing to the Power BI service — neither exists here.
- Whether a completed pipeline run is a production *deployment*. The source has no
  environment or release event, which is why every number carries that caveat.

Statements of these limits are in `docs/METRIC_SPEC.md` and
`docs/VALIDATION_EVIDENCE.md`.
