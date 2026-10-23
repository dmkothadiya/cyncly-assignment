# SAST and SCA Workflow

The repository adds `.github/workflows/security-scans.yml` to perform security analysis without requiring secrets.

## Scans

- **SAST — CodeQL default setup:** GitHub's repository-level CodeQL default setup analyzes C# code. This workflow intentionally does not upload a second CodeQL analysis.
- **SCA — NuGet Audit:** restores the solution with NuGet auditing enabled and escalates `NU1900` through `NU1904` to errors. This covers direct and transitive NuGet dependencies. `NU1900` is included so inability to reach the advisory source fails the job instead of silently skipping the scan.
- **SCA — Dependency Review:** on pull requests, checks dependency changes against known advisories and fails on newly introduced high or critical severity vulnerabilities.

## Permissions and trust boundaries

- Workflow-level permissions default to `contents: read`.
- CodeQL default setup is managed by GitHub and is not granted permissions by this workflow.
- Dependency Review receives read-only pull-request access; PR comments are disabled.
- No secrets are exposed to pull-request code.
- Third-party actions in the workflow and .NET bootstrap composite action are pinned to full commit SHAs. Review and update pins intentionally through PRs.

## Configure on GitHub

1. Keep the repository's CodeQL default setup enabled, or disable it before adding a custom CodeQL advanced-setup workflow. Do not enable both; GitHub rejects SARIF uploads when default setup is already active.
2. Enable the dependency graph so Dependency Review has dependency metadata.
3. Enable Dependabot alerts and security updates to monitor existing dependencies and open update PRs. These are repository settings, separate from this workflow.
4. Run the workflow on a PR and confirm `NuGet vulnerability audit` and `Dependency review` appear as expected checks. Confirm the separate CodeQL default setup scan reports results in the repository's Security tab.
5. The provided `.github/rulesets/main-protection.json` requires the build, NuGet audit, and dependency review checks. Dependency Review is PR-only. Add the exact CodeQL status-check name only if GitHub exposes one for default setup and it has completed successfully at least once.

## Limitations

- GitHub code scanning availability can depend on repository settings and GitHub's current public-repository eligibility.
- Dependency Review can only assess dependencies it can resolve from manifests/lock files and the enabled dependency graph ecosystem support.
- NuGet Audit uses configured NuGet sources and advisory metadata; the scan intentionally fails if the vulnerability service cannot be reached.
- These checks are not a substitute for manual security review, secret scanning, or runtime security testing.
