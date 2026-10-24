# Power BI Desktop Report Guide

## Status

The local pipeline generates the Gold CSV and this folder provides Power Query and DAX starter assets for a report in Power BI Desktop. A `.pbix` report has not been authored or validated in this repository.

## Refresh the data

From the repository root, run:

```powershell
python analytics/run_pipeline.py
```

The report input is `analytics/gold/dora_metrics.csv`. Power BI Desktop is needed to create and save the `.pbix` file.

## Create the report

1. Open Power BI Desktop.
2. Select **Get data → Text/CSV** and choose `analytics/gold/dora_metrics.csv`.
3. Select **Transform Data** and set `project_sk` and `reporting_month` to text, count fields to whole numbers, and rate/hour fields to decimal numbers.
4. Name the query `DoraMetrics`.
5. Add the measures from `DORA_MEASURES.dax`, updating the table name if needed.
6. Build a monthly trend visual and a project comparison table. Include `data_quality_status` as a visible filter or status indicator.
7. Save the report as `analytics/powerbi/DORA_DASHBOARD.pbix`.

For a repeatable transformation, the starter query in `DORA_POWER_QUERY.m` can be pasted into **Transform Data → Advanced Editor**. Replace the example absolute path with the full path to this repository's Gold CSV.

## Interpretation cautions

- `builds` contains pipeline build records, not an explicit production deployment event table. Treat `deployment_count` as a build-run proxy until source owners verify what each record represents.
- The workbook has no reliable commit-to-deployment relationship, so lead time for changes is unavailable.
- Incident-to-deployment matching is not available at event level. Treat the generated change failure rate as a limited approximation, not an authoritative DORA measure.
- The input workbook is a case-study dataset, not production telemetry.

## Sharing

Local authoring in Power BI Desktop is separate from publishing and sharing. Power BI service distribution depends on organizational tenant settings, access controls, and licensing.
