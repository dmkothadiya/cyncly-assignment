# Cyncly Head of DevOps & Analytics Case Study

This repository contains a working, locally verified sample implementation for the Cyncly candidate brief. It demonstrates a small .NET 8 platform engineering pattern, a GitHub Actions pull-request validation workflow, and a local DORA data pipeline implemented from the supplied workbook in `docs/Case Study - DORA Metrics Data.xlsx`. Power BI Desktop is the intended local visualization tool for the generated Gold dataset.

## Scope and architecture overview

The delivery is intentionally small enough to explain in an interview while still covering the required constructs:

- Platform engineering: .NET 8 library + xUnit tests + GitHub Actions PR validation
- Data engineering: Bronze/Silver/Gold pipeline using a local Python script and the supplied workbook
- Governance: DORA metric definitions, quality checks, migration notes, and executive recommendation
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

Install the Python packages once, then run the pipeline. The workbook is copied into `data/source` for traceability and processed locally:

```powershell
python -m pip install -r requirements.txt
python analytics/run_pipeline.py
```

Outputs are generated in:

- `analytics/bronze/`
- `analytics/silver/`
- `analytics/gold/`
- `analytics/quality-checks/`
- `analytics/dashboard/`

This pipeline preserves the raw workbook, validates date and key fields, and produces a Gold DORA dataset with monthly project-level outcome measures.

## Power BI Desktop

Run the pipeline, then open Power BI Desktop and import `analytics/gold/dora_metrics.csv` using **Home → Get data → Text/CSV**. Apply the Power Query types and measures described in `analytics/powerbi/POWERBI_DESKTOP_GUIDE.md`. The generated dashboard summary is also available under `analytics/dashboard/`.

The repository includes a Power Query M starter script, DAX measure definitions, and setup steps under `analytics/powerbi/`. The `.pbix` report itself must be created and saved from Power BI Desktop; it has not been generated or verified here.

Power BI Desktop supports local report authoring. Publishing and sharing reports through the Power BI service may require a paid license or eligible capacity.

The sample workbook is a realistic demonstration dataset and not a production source of truth; therefore it is labeled as synthetic and intentionally limited for interview preparation.

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

- The source workbook does not contain an explicit commit-to-deployment join key, so lead time for changes is recorded as unavailable rather than inferred.
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
- Executive recommendation PDF: `docs/EXECUTIVE_RECOMMENDATION.pdf`
- Leadership strategy PDF: `docs/DEVOPS_STRATEGY_FOR_LEADERSHIP.pdf`
- Executive presentation: `presentation/EXECUTIVE_PRESENTATION.pptx`

## Synthetic data notice

The files under `docs/` are intentionally based on a demonstration workbook and are not real production telemetry. This repository is designed to be reproducible and explainable, with all assumptions explicitly called out.
