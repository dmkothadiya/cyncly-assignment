# Validation Evidence

## Local validation performed

The following commands were executed successfully in the local environment:

```powershell
$env:Path = "$HOME\.dotnet;" + $env:Path

dotnet restore CynclyAssignment.sln
dotnet build CynclyAssignment.sln --configuration Release
dotnet test CynclyAssignment.sln --configuration Release --collect:"XPlat Code Coverage" --results-directory TestResults
python analytics/run_pipeline.py
```

## Results

- .NET solution restored successfully.
- Build completed in Release mode.
- XUnit tests passed.
- Coverage reports were generated under `TestResults`.
- Bronze, Silver, Gold, and quality-check outputs were generated in `analytics/`.
- The Gold CSV contains 9 monthly project rows, all flagged `limited` because the source does not provide verified production deployment events or event-level incident/deployment linkage.
- Power BI Desktop guide, Power Query M, DAX measure starter, and five-slide presentation were generated and checked for expected files/slide count.

## Evidence limitations

- GitHub Actions remote execution was not run against an external repository in this environment.
- A Power BI Desktop `.pbix` report was not authored or executed in this environment. The pipeline output and starter Power Query/DAX assets are prepared for local report creation.
- Publishing and sharing through the Power BI service were not verified.
- The generated PDF and PPTX were produced locally with Python tooling only; they are review artifacts rather than enterprise official artifacts.
