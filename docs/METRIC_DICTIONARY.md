# Metric Dictionary

> **Superseded for the DORA report by [`METRIC_SPEC.md`](./METRIC_SPEC.md).**
> The spec is authoritative for grain, formulas and limitations. This page keeps
> the short reference and the correction history.

## Source data used

The workbook contains four worksheets: `commits`, `builds`, `incidents`, `projects`.

## Measures in the current implementation

| Metric | Formula | Source |
|---|---|---|
| Deployment frequency | count of distinct `build_id` per project per month; per-day form divides by days in month | `builds.build_id`, `builds.pipeline_end_time`, `builds.project_sk` |
| Lead time for changes | median of `pipeline_end_time - commits.author_date` in hours, for valid commit-to-build links | `commits.build_sk` joined to `builds.build_id` |
| Change failure rate | incidents flagged `caused_by_deployment` / deployment count, same project-month | `incidents.caused_by_deployment` |
| Mean time to restore | median of `incident_resolved_datetime - incident_started_datetime`, deployment-caused incidents only | `incidents.*` timestamps |

## Correction to the earlier statement about lead time

An earlier version of this document said the workbook had no usable
commit-to-deployment relation. **That was wrong.** `commits.build_sk` matches
`builds.build_id`: 134 of 160 commit rows resolve to a completed build, giving 84%
link coverage and a usable lead-time signal.

The real limitation is different and is recorded in the spec: a completed build is
a proxy for a deployment, the link is at commit-to-build association grain, and one
association was chronologically impossible and was rejected.

## Data quality status

Each Gold row carries `data_quality_status`:

- `validated` - metrics available with a usable sample (lead time n >= 5)
- `partial` - some metrics available; at least one is blank or thin
- `unavailable` - no metric available for that project-month

Blank metric values mean **not observed**. They are never zero-filled.

## Related

- [`METRIC_SPEC.md`](./METRIC_SPEC.md) - authoritative definition, grain, ownership
- [`DATA_QUALITY.md`](./DATA_QUALITY.md) - quality rules and executable checks
- [`../analytics/powerbi/POWERBI_DESKTOP_GUIDE.md`](../analytics/powerbi/POWERBI_DESKTOP_GUIDE.md) - report build
