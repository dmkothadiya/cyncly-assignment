# Implementation Plan

## 1. Requirements mapped to deliverables

| Requirement | Deliverable | Status |
|---|---|---|
| .NET 8 sample repository | `src/CynclyDoraMetrics` + unit tests | Implemented and locally verified |
| CI validation on PRs | `.github/workflows/pr-validation.yml` | Implemented and locally verified |
| Reusable platform component | `.github/actions/setup-dotnet/action.yml` | Implemented |
| SAST and SCA | `.github/workflows/security-scans.yml`, repository CodeQL default setup | Implemented; NuGet Audit and Dependency Review passed on PR |
| Data source inspection | Workbook profiling and source mapping | Implemented and locally verified |
| Bronze/Silver/Gold pipeline | `analytics/run_pipeline.py` | Implemented and locally verified |
| DORA gold dataset | `analytics/gold/dora_metrics.csv` | Implemented and locally verified |
| Power BI Desktop reporting | `analytics/powerbi/` guide, Power Query and DAX starters | Starter assets implemented; `.pbix` authoring not verified |
| Executive documentation | `docs/ARCHITECTURE.md`, `docs/MIGRATION_AND_GOVERNANCE.md` | Implemented |
| Executive recommendation | `docs/EXECUTIVE_RECOMMENDATION.pdf` | Implemented |
| Executive presentation | `presentation/EXECUTIVE_PRESENTATION.pptx` | Implemented |

## 2. Available inputs and missing inputs

Available inputs:

- `docs/Case Study - DORA Metrics Data.xlsx`
- `docs/case-study-ado-pipeline.yaml`
- Candidate brief in the session prompt

Missing or unavailable inputs:

- Real GitHub Enterprise configuration
- Power BI Desktop `.pbix` report; author it locally from the generated Gold dataset
- Live Azure Boards project metadata and enterprise policies
- Production deployment telemetry or branch protection settings

## 3. Architecture and technology decisions

### Platform engineering

- .NET 8 library selected because the assignment explicitly calls for it and the environment supports it.
- xUnit selected for the sample test suite because it is lightweight and widely understood.
- GitHub Actions selected as the target pipeline platform to replace the supplied Azure Pipelines YAML.
- Reusable composite action chosen because it reduces duplication and is simple to explain in interviews.
- SAST uses the repository's configured GitHub CodeQL default setup. The custom workflow deliberately does not run CodeQL advanced setup as well: GitHub rejects advanced SARIF uploads while default setup is enabled.
- SCA uses NuGet Audit for the full direct/transitive dependency tree and Dependency Review for newly introduced vulnerable dependencies in pull requests. Their advisory data overlaps, but their scopes differ; both are retained.
- GitHub's Automatic Dependency Submission (`submit-nuget`) is a dependency inventory submission, not a vulnerability scan. It feeds the dependency graph and is complementary, not a duplicate of either SCA check.
- Workflow permissions are read-only by default and narrowed by job; action references are pinned to full commit SHAs.
- `.github/rulesets/main-protection.json` targets `main` in Evaluate mode and lists the build, NuGet audit, and Dependency Review checks. Evaluate mode is intentional until the rules and check names are verified on GitHub.

### Data engineering

- Python + pandas + openpyxl selected for local, reproducible workbook processing.
- Bronze preserves raw workbook exports with traceable ingestion metadata.
- Silver standardizes date and key fields and records quality rejections.
- Gold aggregates monthly project and incident metrics for dashboard readiness.
- Power BI Desktop is the visualization target; a Power Query starter and DAX measures are supplied for local report authoring.

### Executive reporting

- PDF recommendation and five-slide PPTX deck are produced locally using Python libraries to remain reproducible and reviewable.
- No invented metrics or fabricated success claims are included.

## 4. Prioritized implementation plan (fits within eight hours)

1. Inspect workbook and Azure Pipelines YAML; confirm actual input and dimensions.
2. Scaffold .NET 8 sample solution with library and tests.
3. Implement unit tests around DORA logic and validation behavior.
4. Build GitHub Actions workflow with minimal permissions and reusable action.
5. Add CodeQL-default-compatible SAST documentation and NuGet Audit/Dependency Review SCA workflow.
6. Implement local data pipeline and quality checks; prepare Power BI Desktop starter assets.
7. Produce strategy, architecture, data-quality, governance, executive recommendation, and presentation artifacts.
8. Run local and GitHub validation, resolve failures, and record evidence.

## 5. Validation commands and acceptance criteria

### .NET acceptance criteria

```powershell
dotnet restore CynclyAssignment.sln
dotnet build CynclyAssignment.sln --configuration Release
dotnet test CynclyAssignment.sln --configuration Release --collect:"XPlat Code Coverage" --results-directory TestResults
```

Expected result: build succeeds, tests pass, coverage is generated.

### Data pipeline acceptance criteria

```powershell
python analytics/run_pipeline.py
```

Expected result: Bronze/Silver/Gold outputs are created and quality checks report pass/fail status.

### Workflow validation

- YAML reviewed for permissions and secret handling.
- Reusable action exists and is referenced.
- Artifact upload and test execution are configured in the workflow.
- NuGet Audit and Dependency Review run in `.github/workflows/security-scans.yml`; CodeQL SAST is provided by repository default setup, not a second advanced workflow.
- Automatic Dependency Submission is reported separately from vulnerability scans because it submits dependency inventory to GitHub.
- Before enforcing the ruleset, verify its required check names and confirm CodeQL results in the repository Security tab.

## 6. Validation evidence and scan interpretation

### Locally verified

- .NET 8 Release build succeeds.
- Unit tests pass and coverage is generated.
- NuGet Audit restore succeeds with `NU1900` through `NU1904` escalated to errors.
- The workbook pipeline generates Bronze, Silver, Gold, and quality outputs.
- Workflow YAML and ruleset JSON parse successfully.
- The generated presentation contains five slides.

### GitHub PR validation

PR #1 (`feat/security-scans-powerbi-submission`) was updated to commit `bbbda4259a68727c2b2debdea59376b2cdf55869`. The observed checks for that commit completed successfully:

- `Build, test, and coverage`
- `NuGet vulnerability audit`
- `Dependency review`
- `Automatic Dependency Submission (NuGet)` (`submit-nuget`)

The dependency-submission job is not a vulnerability scan; it submits the NuGet dependency inventory to GitHub's dependency graph. NuGet Audit scans the full resolved tree, while Dependency Review focuses on dependency changes in the PR. They overlap in advisory sources but are not duplicate jobs.

GitHub reported repository CodeQL default setup as configured. An earlier custom CodeQL advanced-setup job failed because the same repository had default setup enabled. The advanced job was removed, leaving default setup as the single CodeQL configuration. Confirm the resulting CodeQL analysis is visible in the repository Security tab; no CodeQL job is required in the custom workflow.

The main ruleset file is supplied in Evaluate mode only. GitHub branch protection/ruleset enforcement is not claimed as active.

## 7. Risks, assumptions, and limitations

- The workbook does not include a direct commit-to-build mapping, which limits lead-time calculations.
- Power BI Desktop authoring and report publishing are not verified by this implementation; service sharing may require additional licensing.
- GitHub Enterprise-specific controls are modeled as proposed enterprise patterns, not live implementations.
- This repository intentionally avoids real secrets and production claims.
- The dataset is a synthetic case-study workbook for demonstration and interview defense.

## 8. Deferred work

- Live GitHub Actions execution against an external repository
- Authoring and validating the Power BI Desktop `.pbix` report
- Publishing and sharing the report through the Power BI service
- Real branch protection enforcement and enterprise identity federation
- Azure Boards integration beyond design documentation
- Confirm CodeQL default-setup results and, after validation, decide whether to activate the main ruleset
