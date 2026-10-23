# Implementation Plan

## 1. Requirements mapped to deliverables

| Requirement | Deliverable | Status |
|---|---|---|
| .NET 8 sample repository | `src/CynclyDoraMetrics` + unit tests | Implemented and locally verified |
| CI validation on PRs | `.github/workflows/pr-validation.yml` | Implemented and locally verified |
| Reusable platform component | `.github/actions/setup-dotnet/action.yml` | Implemented |
| Data source inspection | Workbook profiling and source mapping | Implemented and locally verified |
| Bronze/Silver/Gold pipeline | `analytics/run_pipeline.py` | Implemented and locally verified |
| DORA gold dataset | `analytics/gold/dora_metrics.csv` | Implemented and locally verified |
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
- Power BI Desktop report file (`.pbix`); Power BI Desktop is to be used locally to author it from the generated Gold dataset
- Live Azure Boards project metadata and enterprise policies
- Production deployment telemetry or branch protection settings

## 3. Architecture and technology decisions

### Platform engineering

- .NET 8 library selected because the assignment explicitly calls for it and the environment supports it.
- xUnit selected for the sample test suite because it is lightweight and widely understood.
- GitHub Actions selected as the target pipeline platform to replace the supplied Azure Pipelines YAML.
- Reusable composite action chosen because it reduces duplication and is simple to explain in interviews.

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
5. Implement local data pipeline and quality checks.
6. Produce strategy, architecture, data-quality, and governance documents.
7. Produce recommendation PDF and five-slide presentation.
8. Run validation commands, fix issues, and record evidence.

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

## 6. Risks, assumptions, and limitations

- The workbook does not include a direct commit-to-build mapping, which limits lead-time calculations.
- Power BI Desktop authoring and report publishing are not verified by this implementation; service sharing may require additional licensing.
- GitHub Enterprise-specific controls are modeled as proposed enterprise patterns, not live implementations.
- This repository intentionally avoids real secrets and production claims.
- The dataset is a synthetic case-study workbook for demonstration and interview defense.

## 7. Deferred work

- Live GitHub Actions execution against an external repository
- Authoring and validating the Power BI Desktop `.pbix` report
- Publishing and sharing the report through the Power BI service
- Real branch protection enforcement and enterprise identity federation
- Azure Boards integration beyond design documentation
