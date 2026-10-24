# Data Quality

Three executable checks guard the Gold layer. They run in the pipeline workflow and
can be repeated locally.

```powershell
python analytics/quality-checks/run_quality_checks.py            # exit 0 when all pass
python analytics/quality-checks/run_quality_checks.py --fixtures # negative test
```

Results are written to `analytics/quality-checks/dq_results.json`. The command exits
non-zero when any check fails, so it can be a CI gate.

## The three checks

| ID | Question | Fails when |
|---|---|---|
| DQ-01 | Referential integrity and grain uniqueness | a fact row points at a missing project; a declared key or grain is duplicated |
| DQ-02 | Temporal validity | a deployment ends before it starts; an incident resolves before it starts; a linked commit is timestamped after its build completed |
| DQ-03 | Metric reconciliation | published deployment count, frequency, failure rate, lead-time median or sample size cannot be recomputed from the facts; summary totals disagree with grain rows |

DQ-01 also reports, without failing, how many commit links point at builds that were
rejected in Silver. That is a coverage limitation, not a corruption.

## Negative test

`--fixtures` copies the Gold layer, injects three defects, and requires every check
to fail:

1. a duplicated metric grain row (DQ-01 must catch it)
2. a negative lead time on a linked commit (DQ-02 must catch it)
3. an inflated `deployment_count` (DQ-03 must catch it)

If a check fails to detect its defect, the command exits non-zero. A check that
cannot fail is not a check.

## Layer rules

**Bronze** keeps the source values exactly, with a SHA-256 of the workbook, row
counts and ingestion timestamp.

**Silver** parses types, enforces required keys, rejects impossible timestamps and
resolves duplicate snapshots by keeping the latest `ingestion_datetime`. Rejected
rows are written to `analytics/silver/rejected_rows.csv` with a reason and without
personal data; author and committer names and e-mails are dropped from every Silver
and Gold table.

**Gold** publishes the metric grain, the facts behind it, and a per-row status of
`complete`, `partial` or `minimal`, with a per-row `status_reason`.

## Defects found in the supplied data

| Finding | Count | Treatment |
|---|---|---|
| Builds where end precedes start | 5 | Rejected in Silver as `end_before_start` |
| Commit-to-build associations that are chronologically impossible | 12 | Rejected with reason `association_precedes_commit` |
| Commit links pointing at a `build_sk` with no Silver row | 3 | Retained as rows, excluded from lead time |
| Timestamps written with two different precisions in one column | 7 rows | Parsed with `format="mixed"`; an inferred single format silently dropped them |
| Incidents whose project is absent from the project sheet | 3 | Held under an `unmapped::` dimension member |
| Deployment-caused incidents with an identical restore time (2.03 h) | 3 | Published, flagged as not statistically meaningful |

## Interpreting the output

- A blank metric means not observed in that project-month. Never read it as zero.
- `data_quality_status` is `complete` (4 of 4 metrics), `partial` (3) or `minimal` (2:
  only deployment count and failure rate). `status_reason` names the missing evidence
  and why it cannot exist, so a blank is never mistaken for a broken pipeline.
- `mttr_all_incidents_hours` is all-cause incident recovery, **not** the DORA MTTR.
  It exists so reliability readers have a number where DORA MTTR is undefined.
- `mttr_sample_size = 3` across the whole period. Any MTTR statement beyond
  "roughly two hours in this dataset" overstates the evidence.
- A rising DQ-01 link count is a signal about source data, not about the check.
