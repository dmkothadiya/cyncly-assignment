# DORA Metric Specification

Authoritative definition of every number published from the DORA solution. If a
report, deck or dashboard disagrees with this document, the document wins and the
report is defective.

**Scope:** `docs/Case Study - DORA Metrics Data.xlsx` (commits, builds, incidents,
projects sheets).
**Status:** baseline definition. No targets have been agreed; the data supports a
baseline, not a scorecard.
**Version:** 1.0, 24 October 2026.

---

## 1. Reporting grain

| Table | Grain | Rows in current data |
|---|---|---|
| `dora_service_month` | `project_sk` x `reporting_month` | 9 |
| `pipeline_lineage` | `layer` x `table_name` - Bronze/Silver/Gold row counts | 15 |
| `dq_check_results` | one row per executable quality check | 3 |
| `fact_deployment` | one row per completed build run | 345 |
| `fact_commit_link` | one row per commit-to-build association (`commit_id` x `deployment_id`) | 152 |
| `fact_incident` | one row per work item | 11 |
| `dim_project` | one row per project, plus unmapped incident projects | 4 |

`project_sk` is the service proxy. The source has no separate service, team or
environment dimension, so a "service" here is the project that owns the pipeline.

`reporting_month` is `yyyy-MM`, derived from the deployment completion timestamp
(deployment metrics) or the incident start timestamp (reliability metrics).

A commit can appear on several rows of `fact_commit_link` when it is rebuilt more
than once. That is the true grain of the source, not a duplicate.

---

## 2. Metric definitions

### DF - Deployment Frequency

| Item | Definition |
|---|---|
| Question | How often does this project put change into the pipeline output? |
| Formula | `count(distinct deployment_id)` per `project_sk` x `reporting_month` |
| Per-day form | `deployment_count / days_in_month` |
| Source | `builds.build_id`, `builds.pipeline_end_time`, `builds.project_sk` |
| Window | Calendar month of build completion |
| Exclusions | Builds with no end timestamp; builds where end precedes start; duplicate `build_id` snapshots (latest ingestion wins) |
| Published column | `deployment_count`, `deployment_frequency_per_day` |
| Limitation | A completed build is a **proxy** for a deployment. No environment or release event exists in the source. |

### LTFC - Lead Time for Changes

| Item | Definition |
|---|---|
| Question | How long from commit authored to the build that contains it completing? |
| Formula | `median(pipeline_end_time - commit.author_date)` in hours, over valid links |
| Source | `commits.commit_id`, `commits.author_date`, `commits.build_sk`, `builds.build_id`, `builds.pipeline_end_time` |
| Window | Month of build completion |
| Exclusions | Links whose build has no end timestamp; links where the build finished **before** the commit was authored (logically impossible, rejected with reason `association_precedes_commit`) |
| Published column | `lead_time_median_hours`, `lead_time_sample_size` |
| Limitation | Association grain: a commit rebuilt three times contributes three observations. 12 links point at builds that finished before the commit was authored and are excluded. |

### CFR - Change Failure Rate

| Item | Definition |
|---|---|
| Question | What share of deployments is associated with an incident caused by deployment? |
| Formula | `failed_deployments / deployment_count` for the same `project_sk` x `reporting_month` |
| Source | `incidents.caused_by_deployment`, `incidents.area_path`, `builds.project_sk` |
| Window | Incident start month aligned to deployment month |
| Exclusions | Incidents not flagged `caused_by_deployment` count toward MTTR only if flagged; they never enter the CFR numerator |
| Published column | `failed_deployments`, `change_failure_rate_pct` |
| Limitation | There is **no event-level deployment link**. An incident is matched to the project-month, not to a specific deployment. Treat CFR as a directional proxy. |

### MTTR - Mean Time to Restore

| Item | Definition |
|---|---|
| Question | How long does restoration take once an incident starts? |
| Formula | `median(incident_resolved_datetime - incident_started_datetime)` in hours, for deployment-caused incidents |
| Source | `incidents.incident_started_datetime`, `incidents.incident_resolved_datetime`, `incidents.caused_by_deployment` |
| Window | Incident start month |
| Exclusions | Incidents resolved before they started; incidents without both timestamps |
| Published column | `mttr_median_hours`, `mttr_sample_size` |
| Limitation | Blank when no deployment-caused incident exists in the window. Blank means **not observed**, never zero. Only 3 qualifying incidents exist, so the median is indicative only. |

#### Companion column - all-cause incident recovery

`mttr_all_incidents_hours` / `mttr_all_incidents_sample` repeat the same calculation
over **every** incident, including the 8 not flagged `caused_by_deployment`.

| Item | Definition |
|---|---|
| Why it exists | DORA MTTR is only defined for failed deployments, so it is blank in 8 of 9 project-months. Reliability readers still need a recovery number. |
| Status | **Not the DORA metric.** Never quote it as MTTR in a DORA context. |
| Bound | Must never feed `data_quality_status`, `metrics_observed` or any DORA card. |

## 2a. Observation status per row

Three columns state how much of the metric set a row actually supports. They exist
because a blank cell alone does not tell a reader whether evidence is missing or the
pipeline is broken.

| Column | Values | Meaning |
|---|---|---|
| `lead_time_status` | `observed`, `below_threshold`, `not_observed` | `below_threshold` when fewer than 5 observations support the median |
| `mttr_status` | `observed`, `not_observed` | deployment-caused incidents only |
| `metrics_observed` | 2 to 4 | deployments and failure rate are always computable; lead time and MTTR add one each |
| `data_quality_status` | `complete`, `partial`, `minimal` | 4, 3 or 2 metrics observed |
| `status_reason` | text | names the missing evidence and why it cannot exist |

`complete` is currently unreachable, and that is a property of the source, not a
defect: the only project-month with a deployment-caused incident (Project A, 2024-08)
has no commits, and the project-months with commits (Project B, 2024-09 to 2024-12)
have no deployment-caused incident. No row can hold both.


Median rather than mean is used for LTFC and MTTR because both distributions are
heavy-tailed: in this dataset lead time ranges from 0.2 h to 311 h.

---

## 3. Transformation rules

1. **Bronze is lossless.** Raw sheets are copied with original values and text
   types, plus a SHA-256 of the workbook and a row count per sheet.
2. **Silver is typed and validated.** Dates parsed as UTC, numerics cast, required
   keys enforced. Rejected rows are written to `analytics/silver/rejected_rows.csv`
   with a reason and **no personal data**.
3. **Snapshot dedupe.** Duplicate business keys are resolved by keeping the row
   with the latest `ingestion_datetime`. Counts are recorded in
   `analytics/quality-checks/silver_profile.json`.
4. **Impossible associations are rejected, not repaired.** If build completion
   precedes commit authorship, the pair is removed and logged.
5. **Unmapped incidents stay visible.** Incident projects absent from the project
   sheet are added to `dim_project` as `unmapped::<name>` with `is_mapped = false`,
   so referential integrity holds and the loss cannot be silently absorbed.
6. **Availability is published, not implied.** Each metric row carries
   `data_quality_status` = `validated` (all metrics with a usable sample),
   `partial` (some metrics available) or `unavailable` (none).
7. **No silent zero-fill.** Missing metric values are null, never 0.

---

## 4. Ownership

| Role | Accountable for | Current assignee |
|---|---|---|
| Metric owner | This specification, definition changes, reconciliation decisions | Head of DevOps & Analytics |
| Data steward | Pipeline correctness, schema, dedupe and rejection rules | Data Engineering |
| Platform owner | Collection of deployment events and incident linkage at source | Platform Engineering |
| Security reviewer | Handling of incident and personnel data | Security |
| Consumer | Using the baseline with the stated limitations | Engineering leadership, Product |

Change control: any change to a formula, grain, exclusion or threshold is a version
bump in this document, a pipeline change, and a note in the release summary. A
metric may not be redefined inside a dashboard.

---

## 5. Known data defects and limitations

| # | Observation | Impact | Treatment |
|---|---|---|---|
| 1 | 5 builds end before they start; no build lacks a completion timestamp | Excluded from deployment counts | Rejected in Silver as `end_before_start` |
| 2 | 12 commit-to-build associations are chronologically impossible | Removed from lead time | Rejected with `association_precedes_commit` |
| 3 | 3 commit links reference a `build_sk` with no row in Silver builds | Lead-time coverage is 98.0% (149 of 152 links) | Reported as `commit_links_without_deployment_row` |
| 4 | 3 incidents belong to projects not in the project sheet | CFR understated for those projects | Held under `unmapped::` dimension members |
| 5 | Only 3 deployment-caused incidents exist and all have an identical restore time of 2.03 h | MTTR is not statistically meaningful | Published with `mttr_sample_size`; flagged |
| 6 | Same commit appears with different `author_date` values across snapshots | Ambiguity in "true" commit time | Latest ingestion wins; documented, not hidden |
| 7 | No environment, release or deployment-event column | Deployment frequency and CFR are proxies | Stated on every report page |
| 8 | The `commits` sheet contains rows for **one** project only; Project A's 13 builds have no commit anywhere in the source | Lead time can never be computed for Project A | `lead_time_status = not_observed`; `status_reason` says the project has no commit |
| 9 | Project B's builds in 2024-07 and 2024-08 have no linked commit either | Lead time starts in 2024-09 | Same treatment; reason distinguishes "no commit for the project" from "no link this month" |

Rows 8 and 9 are the reason 4 of 9 project-months report `minimal`: deployment count
and failure rate are computable, lead time and MTTR have no evidence behind them. No
amount of pipeline work produces those numbers - the linkage has to be captured at
source.

These are properties of the supplied workbook, not of the pipeline. Fixing them
requires a source-system change: emit deployment events with environment,
service and change linkage.

---

## 6. What this metric set must not be used for

- Ranking individuals or teams.
- Contractual or SLA reporting.
- Comparing this organisation to external DORA benchmarks, because the
  population and definitions differ.
- Investment cases that require statistically robust reliability numbers
  (n = 3 incidents).
