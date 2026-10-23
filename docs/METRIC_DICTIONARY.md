# Metric Dictionary

## Source data used

The workbook contains four worksheets:

- `commits`
- `builds`
- `incidents`
- `projects`

## Measures and proxies in this implementation

### Deployment frequency

Available proxy: count of distinct build IDs per project within a reporting month.

Source fields:

- `builds.build_id`
- `builds.pipeline_end_time`
- `builds.project_sk`

Calculation:

- Bucket each build record by project and month using its end timestamp.
- Count distinct build IDs within the month.

Quality note:

- The workbook does not identify production deployment events or deployment environments. Do not present this value as verified production deployment frequency without validating the build record semantics with source owners.

### Change failure rate

Available proxy: deployment-related incidents divided by pipeline build count in the same project/month.

Source fields:

- `incidents.caused_by_deployment`
- `incidents.incident_started_datetime`
- `builds.project_sk`

Calculation:

- Count incidents marked `caused_by_deployment`.
- Divide by build count for the same project and month.

Quality note:

- The workbook has no event-level incident-to-deployment link. This is a limited approximation, not a validated DORA change failure rate.

### Mean time to restore

Measure: average elapsed hours from incident start to incident resolution.

Source fields:

- `incidents.incident_started_datetime`
- `incidents.incident_resolved_datetime`

Calculation:

- Subtract start from resolution for valid rows.
- Aggregate by project and month.

## Metrics intentionally not computed or qualified

### Lead time for changes

Rationale: the workbook does not contain a reliable, explicit relation between commit records and deployment records. The `build_sk` fields do not provide a direct, valid join key to the build records as provided in the sample workbook.

Result: this metric is represented as unavailable rather than inferred from weak assumptions.

### Production deployment frequency

The `builds` sheet contains pipeline start/end timestamps but no environment or deployment event indicator. The pipeline's build count is therefore only a proxy until the source event grain is confirmed.

## Data quality status

Each Gold row includes a quality flag:

- `validated`: the row has complete relevant fields and no material issues
- `limited`: the row is derived but constrained by missing metadata or survey-like assumptions
- `unavailable`: metric not supported by the supplied source model
