# Architecture and Technology Design

## Overview

This repository demonstrates a simplified but credible enterprise architecture for a DevOps analytics transformation. It balances a small, reproducible local implementation with an enterprise-ready target design.

## Platform engineering design

### Local implementation

- .NET 8 class library containing reusable DORA calculation logic
- xUnit test suite covering normal, edge, and failure conditions
- GitHub Actions pull request workflow with minimal permissions
- Composite action for .NET setup, restore, and package caching

### Enterprise target design

- GitHub Enterprise as the source control and developer experience layer
- Azure Boards retained for work-item traceability and program planning
- GitHub Actions as the main CI/CD validation layer
- Self-hosted runners for legacy workloads or tools not compatible with hosted runners
- Artifact feeds and security scanning integrated with the repo lifecycle

## Data engineering design

### Bronze layer

- Preserve raw workbook tables in their source form
- Capture ingestion metadata such as source file, sheet name, row count, and timestamp
- Retain original identifiers and values without transformation

### Silver layer

- Normalize timestamps and schedule environment variables
- Validate required keys and data completeness
- Remove or quarantine duplicates
- Keep rejected records as a quality-output artifact for review instead of silently dropping them

### Gold layer

- Aggregate project-level monthly DORA metrics
- Distinguish between validated and limited data based on quality checks
- Keep metrics traceable to the source workbook and the transformation steps

## Security and governance boundaries

- Repository permissions are explicitly scoped to `contents: read` in the sample workflow.
- No secrets are required for the sample implementation.
- Production environments should use GitHub Environments, OIDC, and least-privilege secrets.
- Branch protection and policy enforcement are proposed and not assumed to be active.

## Known limitations

- The Gold dataset is prepared for local Power BI Desktop report authoring; the `.pbix` file must be created and validated in the installed desktop application.
- Publishing and sharing reports through the Power BI service depend on tenant configuration and licensing.
- The source workbook lacks a reliable commit-to-deployment join, so lead-time metrics are flagged as unavailable rather than estimated.
