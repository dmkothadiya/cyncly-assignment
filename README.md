# Cyncly Head of DevOps & Analytics Case Study

This repository contains a working, locally verified sample implementation for the Cyncly candidate brief. It demonstrates a small .NET 8 platform engineering pattern, a GitHub Actions pull-request validation workflow, and a local DORA data pipeline implemented from the supplied workbook in `docs/Case Study - DORA Metrics Data.xlsx`. Power BI Desktop is the intended local visualization tool for the generated Gold dataset.

## Scope and architecture overview

The delivery is intentionally small enough to explain in an interview while still covering the required constructs:

- Platform engineering: .NET 8 library + xUnit tests + GitHub Actions PR validation
- Data engineering: Bronze/Silver/Gold pipeline, four DORA metrics at a documented grain, three executable quality checks, and a Power BI Desktop report layer
- Governance: metric specification with ownership, quality rules, migration notes, and executive recommendation
- Delivery artifacts: Implementation plan, architecture notes, migration strategy, executive recommendation PDF, and a five-slide presentation

The architecture follows a pragmatic enterprise model:

- GitHub Actions for pull-request validation and artifact publication
- Reusable composite action for .NET setup and dependency caching
- Local Python pipeline for workbook ingestion and DORA transformations
- Synthetic but realistic DORA outputs for review and demonstration

## Prerequisites

Local developer environment requirements:

- .NET 8 SDK (8.0.100+)
- Git
- Python 3.11+ with packages from `requirements.txt`
- Optional: PowerPoint export tooling for the executive deck

## .NET build and test

Use the following commands from the repository root:

```powershell
$env:Path = "$HOME\.dotnet;" + $env:Path

dotnet restore CynclyAssignment.sln
dotnet build CynclyAssignment.sln --configuration Release
dotnet test CynclyAssignment.sln --configuration Release --collect:"XPlat Code Coverage" --results-directory TestResults
```

Coverage output is stored under `TestResults/` in Cobertura or JSON format depending on the installed tooling package. Review the generated `.xml` and `.json` files under `TestResults`.

## Data pipeline

Install the Python packages once, then run the pipeline:

```powershell
python -m pip install -r requirements.txt
python analytics/run_pipeline.py
```

Outputs are generated in:

| Path | Layer |
|---|---|
| `analytics/bronze/` | Raw sheet copies plus ingestion metadata (SHA-256, row counts) |
| `analytics/silver/` | Typed, validated, deduplicated tables and `rejected_rows.csv` |
| `analytics/gold/` | `dim_project`, three facts, `dora_service_month` (grain), `dora_period_summary` |
| `analytics/quality-checks/` | `dq_results.json`, `silver_profile.json` |
| `analytics/dashboard/` | `DORA_DASHBOARD.pbix` - saved single-file report (2 pages, 19 visuals) |

The published grain is **project x calendar month**. All four DORA metrics are
computed: deployment frequency, lead time for changes, change failure rate and mean
time to restore. Definitions, exclusions and ownership are in
[`docs/METRIC_SPEC.md`](docs/METRIC_SPEC.md).

## Data-quality checks

Three executable checks gate the Gold layer:

```powershell
python analytics/quality-checks/run_quality_checks.py            # exit 0 when all pass
python analytics/quality-checks/run_quality_checks.py --fixtures # negative test
```

| ID | Guards against |
|---|---|
| DQ-01 | Broken references and duplicate grain |
| DQ-02 | Impossible timestamps, including negative lead time |
| DQ-03 | Published metrics that do not reconcile to the facts |

The negative test corrupts a copy of Gold and requires every check to fail, proving
the checks can actually fail. Rules and known source defects are in
[`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md).

## Power BI Desktop

The Power BI layer is in `analytics/powerbi/`:

- `DORA_Project/DORA.pbip` - **the report**. A Power BI project (PBIR report + TMDL model): 19 visuals on two 1920x1080 pages, 8 tables, 8 relationships, 17 measures. Open it in Desktop and press **Refresh now**
- `build_pbip.py` - generates the project (`DORA.Report/` + `DORA.SemanticModel/`)
- `generate_tmdl_model.py` - generates the TMDL model from the actual Gold columns
- `validate_pbip.py` - validates every definition file against the Microsoft schemas and resolves every visual field reference against the model
- `check_references.py` - offline reference resolution used by the validator
- `DORA_POWER_QUERY.m` - Power Query for the dimension, three facts and date table
- `DORA_MEASURES.dax` - the four DORA measures plus sample-size and caveat measures
- `DORA_theme.json` - the report theme
- `DORA_Data.xlsx` - the same five tables as a workbook, for the manual route
- `POWERBI_DESKTOP_GUIDE.md` - relationship map, visual-by-visual page spec, limitations

```powershell
python analytics/powerbi/generate_tmdl_model.py     # TMDL model
python analytics/powerbi/build_pbip.py              # PBIR report + project
python analytics/powerbi/validate_pbip.py           # schemas + field references
```

`analytics/dashboard/DORA_DASHBOARD.pbix` is that report saved from Power BI Desktop
(**File → Save as → Power BI file (\*.pbix)**): 2 pages, 19 visuals, cards reading
38.33 / 20.5 h / 0.87% / 2.0 h.
`analytics/dashboard/dora_powerbi_desktop.png` is a real screenshot of it open in
Desktop.

**About the `.pbix`:** a `.pbix` package is signed when Desktop writes it, so it
cannot be produced or edited by hand - repacking one fails with "This file is
corrupted or was created by an unrecognized version". The PBIP project above is
therefore kept as the authorable, reviewable equivalent; the committed `.pbix` is a
save from that project, so re-save it in Desktop after changing the model rather
than editing the binary.

## Dashboard verification

Step-by-step guide with expected values, manual report checks and troubleshooting:
[`docs/DASHBOARD_VERIFICATION_GUIDE.md`](docs/DASHBOARD_VERIFICATION_GUIDE.md).

```powershell
python analytics/verify_solution.py                                        # 21 checks
python analytics/verify_solution.py --pbix analytics/powerbi/DORA_DASHBOARD.pbix
```

The verifier recomputes all four metrics from the fact tables, checks six known-answer
spot values, reconciles totals, confirms the quality results, and - once you save a
`.pbix` - inspects the file's model and report layout directly.

## Review package

`DORA_PowerBI_Solution.zip` bundles the pipeline, Silver and Gold data, the quality
results, the Power BI assets, the metric specification and the dashboard reference.
Raw Bronze rows are excluded because they contain commit author names and e-mails.


## GitHub Actions workflow

The repository includes:

- `.github/workflows/pr-validation.yml`
- `.github/workflows/security-scans.yml`
- `.github/actions/setup-dotnet/action.yml`

The workflow runs on pull requests and pushes to `main`, restores dependencies, builds in Release mode, runs tests, generates coverage, and uploads artifacts. The reusable composite action ensures the same .NET bootstrap is used consistently across jobs.

The separate security workflow runs NuGet Audit and Dependency Review; repository-level CodeQL default setup provides C# SAST. The workflow does not run a second advanced CodeQL upload because GitHub rejects simultaneous default and advanced CodeQL configurations. NuGet Audit checks direct and transitive packages and treats audit-service errors or vulnerability advisories as failures; Dependency Review rejects newly introduced high-or-critical severity dependency vulnerabilities on PRs. External actions are pinned to full commit SHAs.

## Permissions and secrets

The workflow uses explicit minimal permissions:

```yaml
permissions:
  contents: read
```

No secrets are required for the sample workflow. Any production-grade replacement should use GitHub Environments, OIDC, or secrets scoped to the repository or environment as appropriate.

## Validation evidence and limitations

Implemented and locally verified:

- .NET solution builds and unit tests pass
- Coverage generation runs successfully in the local environment
- DORA pipeline reads the workbook and writes Bronze/Silver/Gold CSV datasets
- Strategy and governance notes are present in `docs/`

Implemented but not externally verified:

- GitHub Actions execution against a remote repository
- Power BI Desktop report authoring; Power Query and DAX starter assets are provided, but the `.pbix` must be created in the desktop application

Proposed enterprise design:

- Power BI report distribution with organization-approved access and licensing
- GitHub Enterprise branch protection, environment approvals, and Azure Boards traceability

Assumption and limitation:

- The source workbook does not contain an explicit commit-to-deployment join key, so
  lead time is derived from the commit-to-build association. Project A has no commits
  at all in the source, so its lead time is `not_observed` rather than inferred.
- Report publishing and sharing permissions depend on the organization's Power BI licensing and tenant configuration.

## Relevant locations

- Strategy and implementation plan: `docs/IMPLEMENTATION_PLAN.md`
- Architecture: `docs/ARCHITECTURE.md`
- Governance and migration: `docs/MIGRATION_AND_GOVERNANCE.md`
- Metric dictionary: `docs/METRIC_DICTIONARY.md`
- Data quality: `docs/DATA_QUALITY.md`
- Power BI Desktop guide and starter query/measures: `analytics/powerbi/`
- Validation evidence: `docs/VALIDATION_EVIDENCE.md`
- AI usage statement: `docs/AI_USE_STATEMENT.md`
- Executive recommendation PDF: `docs/EXECUTIVE_RECOMMENDATION.pdf` (1 page - Part D
  decision paper: priorities, investment, trusted metrics, risks, decisions)
- CTO briefing PDF: `docs/DEVOPS_STRATEGY_FOR_LEADERSHIP.pdf` (10 pages - architecture,
  operating model, governance, roadmap, risks, decisions)
- Executive presentation: `presentation/EXECUTIVE_PRESENTATION.pptx`

## Synthetic data notice

The files under `docs/` are intentionally based on a demonstration workbook and are not real production telemetry. This repository is designed to be reproducible and explainable, with all assumptions explicitly called out.
