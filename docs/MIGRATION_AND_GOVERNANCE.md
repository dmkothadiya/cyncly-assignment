# Migration and Governance

## Migration approach

The supplied Azure Pipelines YAML is a useful baseline but not a direct replacement for GitHub Actions. The conversion here preserves the intent of PR validation, build verification, test execution, and artifact publication while simplifying the implementation to a small, reviewable sample.

### Conversion decisions

Implemented migration decisions:

- Build and test stages preserved in the GitHub Actions workflow
- Release build retained as the validation target
- Coverage generation kept as a required output artifact
- Reusable setup logic extracted to a composite action

Deliberate differences:

- The sample workflow uses hosted Ubuntu runners, which is a simpler model than the original Azure Pipeline's Windows x86 environment
- The direct x86 and VC++ installation steps from the Azure YAML are documented as a legacy exception, not assumed in GitHub-hosted Linux runners
- The repository does not claim live branch protection or enterprise policies that cannot be verified here

## Governance model

### Central platform engineering

Owns the CI/CD framework, reusable workflow, runner strategy, and security defaults.

### Application teams

Own the business logic, quality gates, and acceptance tests for their services.

### Security and compliance

Own validation of secrets, approvals, and dependency controls.

### Data engineering and analytics

Own metric definition, data-quality checks, and dashboard evidence.

## Operational controls

- Minimal permissions in workflows
- No credential leakage in logs
- Explicit artifact retention for review
- Quality checks to differentiate validated signals from incomplete data
- Documented assumptions for any metric not fully supported by source data

## Residual risk

A real enterprise migration would require:

- repository owners and branch protection settings
- environment approvals and OIDC identity federation
- self-hosted runner governance for legacy workloads
- Power BI report ownership, workspace access, and licensing for shared reports
- data stewardship for DORA metric definitions
