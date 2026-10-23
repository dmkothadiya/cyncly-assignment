# Data Quality and Validation

## Source workbook checks

The supplied workbook is materially useful for demonstration but not a perfect production dataset. The local pipeline validates the following characteristics:

1. Required columns exist in each sheet.
2. Duplicate IDs are identified and counted.
3. Date fields are parsed consistently.
4. Temporal relationships are checked (for example, incident resolution after start time).
5. Project identifiers are checked against the project reference table.

## Quality checks implemented

### Check 1: completeness

- Ensure required fields are populated for each table.
- Reject rows where an ID or date is missing.

### Check 2: deduplication and referential integrity

- Count duplicate `workitem_id`, `build_id`, and `project_id` records.
- Ensure incident and build records refer to valid project references.

### Check 3: time consistency

- Confirm `pipeline_end_time` is not earlier than `pipeline_start_time`.
- Confirm `incident_resolved_datetime` is not earlier than `incident_started_datetime`.

## Output conventions

The Silver layer records accepted rows and a rejected rows file when any rows fail validation.

Quality rules are deliberately explicit rather than silent: data is either kept with a quality flag or rejected for review.

## Known limitations

- The workbook includes only 11 incident rows and 2 project rows, limiting statistical confidence.
- No direct deployment-to-commit mapping is available, so a full lead-time signal cannot be derived safely.
- The dataset is best treated as a case study rather than production telemetry.
