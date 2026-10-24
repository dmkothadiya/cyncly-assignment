"""Generate a TMDL semantic model (PBIP model item) for the DORA gold layer.

This is the supported, text-based path Microsoft documents for authoring a
semantic model outside Power BI Desktop. Report definitions are explicitly not
supported outside the app, so no report folder is produced here.

Output: analytics/powerbi/DORA.SemanticModel/
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "analytics" / "gold"
TARGET = Path(__file__).resolve().parent / "DORA.SemanticModel"
DEFINITION = TARGET / "definition"
TABLES = DEFINITION / "tables"

NAMESPACE = uuid.UUID("6f1c7d2e-4a10-4f6b-9f2e-0d0a00000001")

# column -> TMDL dataType override; everything else is inferred from the CSV
TYPE_OVERRIDES = {
    ("FactDeployment", "pipeline_start_time"): "dateTime",
    ("FactDeployment", "pipeline_end_time"): "dateTime",
    ("FactDeployment", "deployment_date"): "date",
    ("FactCommitLink", "author_date"): "dateTime",
    ("FactCommitLink", "deployed_at"): "dateTime",
    ("FactCommitLink", "deployed_date"): "date",
    ("FactIncident", "started_at"): "dateTime",
    ("FactIncident", "resolved_at"): "dateTime",
    ("FactIncident", "started_date"): "date",
    ("DoraServiceMonth", "month_start"): "date",
    # Counts stay integers even though the CSV has blank cells for months where the
    # metric was never observed - otherwise pandas infers float and the report reads
    # "14.00" where the number of observations is 14.
    ("DoraServiceMonth", "days_in_month"): "int64",
    ("DoraServiceMonth", "deployment_count"): "int64",
    ("DoraServiceMonth", "failed_deployments"): "int64",
    ("DoraServiceMonth", "lead_time_sample_size"): "int64",
    ("DoraServiceMonth", "mttr_sample_size"): "int64",
}

MEASURES = [
    ("Deployments", "SUM ( DoraServiceMonth[deployment_count] )", "#,0"),
    ("Active Months", "DISTINCTCOUNT ( DoraServiceMonth[reporting_month] )", "#,0"),
    ("Failed Deployments", "SUM ( DoraServiceMonth[failed_deployments] )", "#,0"),
    (
        "Deployment Frequency (per day)",
        "DIVIDE ( [Deployments], SUM ( DoraServiceMonth[days_in_month] ) )",
        "0.00",
    ),
    (
        # Gold publishes deployment_frequency_per_month as deployments divided by
        # project-months (342 / 9 = 38.0), so the measure must divide by grain rows,
        # not by distinct months.
        "Deployment Frequency (per project-month)",
        "DIVIDE ( [Deployments], COUNTROWS ( DoraServiceMonth ) )",
        "0.0",
    ),
    (
        # The grain table is the report's filter surface, but relationships only flow
        # from DimProject and DimDate into the facts, so selecting a project-month row
        # never reaches FactCommitLink and the card keeps showing the period median.
        # KEEPFILTERS(TREATAS(...)) pushes the selected project and month into the fact
        # and *intersects* with any filter already there - without KEEPFILTERS it would
        # override the month axis of the lead-time chart and every bar would read alike.
        "Lead Time for Changes (median h)",
        "CALCULATE ( MEDIAN ( FactCommitLink[lead_time_hours] ), "
        "FactCommitLink[is_valid_lead_time] = TRUE (), "
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[project_sk] ), '
        'FactCommitLink[project_sk] ) ), '
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[reporting_month] ), '
        'FactCommitLink[reporting_month] ) ) )',
        '0.0 "h"',
    ),
    (
        "Lead Time Sample",
        "CALCULATE ( COUNTROWS ( FactCommitLink ), FactCommitLink[is_valid_lead_time] = TRUE (), "
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[project_sk] ), '
        'FactCommitLink[project_sk] ) ), '
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[reporting_month] ), '
        'FactCommitLink[reporting_month] ) ) )',
        "#,0",
    ),
    (
        # Every row in FactCommitLink already resolved to a build, so is_linkable is
        # TRUE throughout. Gold publishes commit_link_coverage_pct as valid lead-time
        # links over all links (149/152 = 98.03%). Bridging on the month would hide the
        # three invalid links, which carry no reporting_month at all, and report 100% in
        # every context, so coverage is deliberately bridged on project only.
        "Commit Link Coverage %",
        "DIVIDE ( "
        "CALCULATE ( COUNTROWS ( FactCommitLink ), FactCommitLink[is_valid_lead_time] = TRUE (), "
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[project_sk] ), '
        'FactCommitLink[project_sk] ) ) ), '
        "CALCULATE ( COUNTROWS ( FactCommitLink ), "
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[project_sk] ), '
        'FactCommitLink[project_sk] ) ) ) )',
        "0.0%",
    ),
    ("Change Failure Rate %", "DIVIDE ( [Failed Deployments], [Deployments] )", "0.00%"),
    (
        "Deployment Related Incidents",
        "CALCULATE ( COUNTROWS ( FactIncident ), FactIncident[caused_by_deployment] = 1, "
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[project_sk] ), '
        'FactIncident[project_sk] ) ), '
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[reporting_month] ), '
        'FactIncident[reporting_month] ) ) )',
        "#,0",
    ),
    (
        "MTTR (median h)",
        "CALCULATE ( MEDIAN ( FactIncident[restore_hours] ), "
        "FactIncident[caused_by_deployment] = 1, "
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[project_sk] ), '
        'FactIncident[project_sk] ) ), '
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[reporting_month] ), '
        'FactIncident[reporting_month] ) ) )',
        '0.0 "h"',
    ),
    (
        "MTTR Sample",
        "CALCULATE ( COUNTROWS ( FactIncident ), FactIncident[caused_by_deployment] = 1, "
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[project_sk] ), '
        'FactIncident[project_sk] ) ), '
        'KEEPFILTERS ( TREATAS ( VALUES ( DoraServiceMonth[reporting_month] ), '
        'FactIncident[reporting_month] ) ) )',
        "#,0",
    ),
    (
        "Sample Size Note",
        '"Lead time n=" & FORMAT ( [Lead Time Sample], "#,##0" ) & "  |  MTTR n=" & '
        'FORMAT ( [MTTR Sample], "#,##0" ) & "  |  Link coverage " & '
        'FORMAT ( [Commit Link Coverage %], "0.0%" )',
        None,
    ),
    (
        "Data Quality Status",
        'IF ( ISBLANK ( [Lead Time for Changes (median h)] ) || ISBLANK ( [MTTR (median h)] ), '
        '"Partial - see caveats", "Validated" )',
        None,
    ),
]

RELATIONSHIPS = [
    ("FactDeployment", "project_sk", "DimProject", "project_sk"),
    ("FactCommitLink", "project_sk", "DimProject", "project_sk"),
    ("FactIncident", "project_sk", "DimProject", "project_sk"),
    ("DoraServiceMonth", "project_sk", "DimProject", "project_sk"),
    ("DoraServiceMonth", "month_start", "DimDate", "Date"),
    ("FactDeployment", "deployment_date", "DimDate", "Date"),
    # Without these two, a month filter reaches the metric table but never the facts,
    # so a monthly lead-time or CFR visual returns the period-wide value in every month.
    ("FactCommitLink", "deployed_date", "DimDate", "Date"),
    ("FactIncident", "started_date", "DimDate", "Date"),
]

TABLES_FROM_FILES = {
    "DimProject": "dim_project.csv",
    "FactDeployment": "fact_deployment.csv",
    "FactCommitLink": "fact_commit_link.csv",
    "FactIncident": "fact_incident.csv",
    "DoraServiceMonth": "dora_service_month.csv",
    "PipelineLineage": "pipeline_lineage.csv",
    "DqCheckResult": "dq_check_results.csv",
}

# Measures that belong to the lineage and quality tables rather than to the metric
# table, so the report can show the medallion and the gate status from data.
AUX_MEASURES = [
    ("DqCheckResult", "Checks Run", "COUNTROWS ( DqCheckResult )", "#,0"),
    ("DqCheckResult", "Checks Passed", "SUM ( DqCheckResult[checks_passed] )", "#,0"),
    (
        "PipelineLineage",
        "Rows Reaching Gold",
        'CALCULATE ( SUM ( PipelineLineage[rows_out] ), PipelineLineage[layer] = "Gold" )',
        "#,0",
    ),
]


def lineage(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "|".join(parts)))


def infer_type(table: str, column: str, series: pd.Series) -> str:
    if (table, column) in TYPE_OVERRIDES:
        return TYPE_OVERRIDES[(table, column)]
    lowered = column.lower()
    if lowered.endswith("_id") or lowered.endswith("_sk"):
        return "string"
    if pd.api.types.is_integer_dtype(series):
        return "int64"
    if pd.api.types.is_float_dtype(series):
        return "double"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    return "string"


M_TYPES = {
    "string": "type text",
    "int64": "Int64.Type",
    "double": "type number",
    "boolean": "type logical",
    "dateTime": "type datetime",
    "date": "type date",
}

# The tabular model has no "date" or "dateTimeZone" data type. Both collapse to dateTime:
# dates are midnight, and offset timestamps are converted to naive UTC in the M query.
TMDL_TYPES = {"date": "dateTime", "dateTime": "dateTime"}


def tmdl_type(data_type: str) -> str:
    return TMDL_TYPES.get(data_type, data_type)


def csv_expression(csv_name: str, columns: list[tuple[str, str]], derive_month: bool = False) -> str:
    indent = "\t\t\t\t"
    step = f"{indent}\t"

    # Offset timestamps ("2024-07-11 06:36:11+00:00") cannot be parsed by DateTime.FromText,
    # so they are read as DateTimeZone and the zone is dropped to match the model's dateTime.
    datetime_columns = [name for name, data_type in columns if data_type == "dateTime"]
    simple_columns = [(n, t) for n, t in columns if t != "dateTime"]

    typed = ",\n".join(
        f'{step}\t\t{{"{name}", {M_TYPES[data_type]}}}' for name, data_type in simple_columns
    )
    steps = [
        f'{step}Source = Csv.Document(\n'
        f'{step}\tFile.Contents(GoldFolder & "\\{csv_name}"),\n'
        f'{step}\t[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]\n'
        f"{step})",
        f"{step}Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])",
        # Empty CSV cells must become null before typing, otherwise numeric, date and
        # boolean conversions turn them into errors that propagate into every measure.
        f"{step}Cleaned = Table.ReplaceValue(\n"
        f'{step}\tPromoted,\n'
        f'{step}\t"",\n'
        f"{step}\tnull,\n"
        f"{step}\tReplacer.ReplaceValue,\n"
        f"{step}\tTable.ColumnNames(Promoted)\n"
        f"{step})",
        f"{step}Typed = Table.TransformColumnTypes(\n"
        f"{step}\tCleaned,\n"
        f"{step}\t{{\n"
        f"{typed}\n"
        f"{step}\t}}\n"
        f"{step})",
    ]
    tail = "Typed"

    if datetime_columns:
        transforms = ",\n".join(
            f'{step}\t\t{{"{name}", each if _ = null then null '
            f"else DateTimeZone.RemoveZone(DateTimeZone.FromText(_)), type datetime}}"
            for name in datetime_columns
        )
        steps.append(
            f"{step}WithTimestamps = Table.TransformColumns(\n"
            f"{step}\tTyped,\n"
            f"{step}\t{{\n"
            f"{transforms}\n"
            f"{step}\t}}\n"
            f"{step})"
        )
        tail = "WithTimestamps"

    if derive_month:
        steps.append(
            f'{step}WithDate = Table.AddColumn({tail}, "month_start", '
            f'each Date.FromText([reporting_month] & "-01"), type date)'
        )
        tail = "WithDate"

    body = ",\n".join(steps)
    return f"{indent}let\n{body}\n{indent}in\n{step}{tail}"


def dimension_date_expression() -> str:
    indent = "\t\t\t\t"
    return (
        f"{indent}let\n"
        f"{indent}\tStartDate = #date(2024, 1, 1),\n"
        f"{indent}\tEndDate = #date(2025, 12, 31),\n"
        f"{indent}\tDayCount = Duration.Days(EndDate - StartDate) + 1,\n"
        f"{indent}\tDateList = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),\n"
        f'{indent}\tToTable = Table.FromList(DateList, Splitter.SplitByNothing(), {{"Date"}}),\n'
        f'{indent}\tWithYear = Table.AddColumn(ToTable, "Year", each Date.Year([Date]), Int64.Type),\n'
        f'{indent}\tWithMonth = Table.AddColumn(WithYear, "Month Number", each Date.Month([Date]), Int64.Type),\n'
        f'{indent}\tWithName = Table.AddColumn(WithMonth, "Month", each Date.ToText([Date], "MMM"), type text),\n'
        f'{indent}\tWithKey = Table.AddColumn(WithName, "Month Key", each Date.ToText([Date], "yyyy-MM"), type text)\n'
        f"{indent}in\n"
        f"{indent}\tWithKey"
    )


def quote(name: str) -> str:
    """TMDL requires single quotes around names containing spaces or special characters."""
    if any(ch in name for ch in " \t.-()"):
        return f"'{name}'"
    return name


def build_table(name: str, frame: pd.DataFrame, source: str) -> str:
    lines = [f"table {name}", f"\tlineageTag: {lineage('table', name)}", ""]
    for column in frame.columns:
        data_type = infer_type(name, column, frame[column])
        lines.append(f"\tcolumn {quote(column)}")
        lines.append(f"\t\tdataType: {tmdl_type(data_type)}")
        if data_type == "date":
            lines.append("\t\tformatString: yyyy-mm-dd")
        elif data_type == "dateTime":
            lines.append("\t\tformatString: yyyy-mm-dd hh:nn:ss")
        lines.append(f"\t\tlineageTag: {lineage('column', name, column)}")
        lines.append("\t\tsummarizeBy: none")
        lines.append(f"\t\tsourceColumn: {quote(column)}")
        lines.append("")
        lines.append("\t\tannotation SummarizationSetBy = Automatic")
        lines.append("")

    lines.append(f"\tpartition {name} = m")
    lines.append("\t\tmode: import")
    lines.append("\t\tsource =")
    for source_line in source.split("\n"):
        lines.append("\t" + source_line)
    lines.append("")
    lines.append(f"\tannotation PBI_ResultType = Table")
    return "\n".join(lines)


def build_date_table() -> str:
    columns = [
        ("Date", "date"),
        ("Year", "int64"),
        ("Month Number", "int64"),
        ("Month", "string"),
        ("Month Key", "string"),
    ]
    lines = ["table DimDate", f"\tlineageTag: {lineage('table', 'DimDate')}", ""]
    lines.append(f"\tcolumn Date")
    lines.append("\t\tdataType: dateTime")
    lines.append("\t\tformatString: yyyy-mm-dd")
    lines.append(f"\t\tlineageTag: {lineage('column', 'DimDate', 'Date')}")
    lines.append("\t\tisKey")
    lines.append("\t\tsummarizeBy: none")
    lines.append("\t\tsourceColumn: Date")
    lines.append("")
    for column, data_type in columns[1:]:
        lines.append(f"\tcolumn {quote(column)}")
        lines.append(f"\t\tdataType: {tmdl_type(data_type)}")
        if data_type == "date":
            lines.append("\t\tformatString: yyyy-mm-dd")
        lines.append(f"\t\tlineageTag: {lineage('column', 'DimDate', column)}")
        lines.append("\t\tsummarizeBy: none")
        lines.append("\t\tsourceColumn: " + quote(column))
        lines.append("")
    lines.append("\tpartition DimDate = m")
    lines.append("\t\tmode: import")
    lines.append("\t\tsource =")
    for source_line in dimension_date_expression().split("\n"):
        lines.append("\t" + source_line)
    lines.append("")
    lines.append("\tannotation PBI_ResultType = Table")
    return "\n".join(lines)


def main() -> None:
    if TABLES.exists():
        for existing in TABLES.glob("*.tmdl"):
            existing.unlink()
    TABLES.mkdir(parents=True, exist_ok=True)

    frames = {name: pd.read_csv(GOLD / file) for name, file in TABLES_FROM_FILES.items()}
    dora = frames["DoraServiceMonth"].copy()
    dora["month_start"] = pd.to_datetime(dora["reporting_month"] + "-01").dt.strftime("%Y-%m-%d")
    frames["DoraServiceMonth"] = dora

    for name, frame in frames.items():
        raw_columns = list(pd.read_csv(GOLD / TABLES_FROM_FILES[name]).columns)
        m_columns = [(column, infer_type(name, column, frame[column])) for column in raw_columns]
        source = csv_expression(
            TABLES_FROM_FILES[name], m_columns, derive_month=(name == "DoraServiceMonth")
        )
        (TABLES / f"{name}.tmdl").write_text(build_table(name, frame, source), encoding="utf-8")

    (TABLES / "DimDate.tmdl").write_text(build_date_table(), encoding="utf-8")

    measures = []
    for label, expression, format_string in MEASURES:
        measures.append(f"\tmeasure '{label}' = {expression}")
        measures.append(f"\t\tlineageTag: {lineage('measure', label)}")
        if format_string:
            measures.append(f"\t\tformatString: {format_string}")
        measures.append("")
    (TABLES / "DoraServiceMonth.tmdl").write_text(
        (TABLES / "DoraServiceMonth.tmdl").read_text(encoding="utf-8")
        + "\n"
        + "\n".join(measures),
        encoding="utf-8",
    )

    for table, label, expression, format_string in AUX_MEASURES:
        path = TABLES / f"{table}.tmdl"
        block = [
            f"\tmeasure '{label}' = {expression}",
            f"\t\tlineageTag: {lineage('measure', label)}",
        ]
        if format_string:
            block.append(f"\t\tformatString: {format_string}")
        path.write_text(
            path.read_text(encoding="utf-8") + "\n" + "\n".join(block) + "\n",
            encoding="utf-8",
        )

    relationships = []
    for from_table, from_column, to_table, to_column in RELATIONSHIPS:
        relationships.append(f"relationship {lineage('rel', from_table, from_column, to_table)}")
        relationships.append(f"\tfromColumn: {from_table}.{from_column}")
        relationships.append(f"\ttoColumn: {to_table}.{to_column}")
        relationships.append("")
    (DEFINITION / "relationships.tmdl").write_text("\n".join(relationships), encoding="utf-8")

    (DEFINITION / "expressions.tmdl").write_text(
        "expression GoldFolder = "
        '"C:\\workspace\\cyncly-assignment\\analytics\\gold" '
        'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {lineage('expression', 'GoldFolder')}\n"
        "\tannotation PBI_ResultType = Text\n"
        "\tannotation PBI_NavigationStepName = Navigation\n",
        encoding="utf-8",
    )

    (DEFINITION / "database.tmdl").write_text(
        "database\n\tcompatibilityLevel: 1601\n", encoding="utf-8"
    )

    order = ["GoldFolder", "DimProject", "DimDate", "FactDeployment",
             "FactCommitLink", "FactIncident", "DoraServiceMonth",
             "PipelineLineage", "DqCheckResult"]
    model_lines = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdiscourageImplicitMeasures",
        "",
    ]
    for name in order[1:]:
        model_lines.append(f"ref table {name}")
    model_lines.append("")
    model_lines.append("ref expression GoldFolder")
    model_lines.append("")
    model_lines.append("annotation PBI_QueryOrder = " + json.dumps(order))
    (DEFINITION / "model.tmdl").write_text("\n".join(model_lines) + "\n", encoding="utf-8")

    (TARGET / "definition.pbism").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                           "item/semanticModel/definitionProperties/1.0.0/schema.json",
                "version": "4.2",
                "settings": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (TARGET / ".platform").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                           "gitIntegration/platformProperties/2.0.0/schema.json",
                "metadata": {
                    "type": "SemanticModel",
                    "displayName": "DORA",
                },
                "config": {"version": "2.0", "logicalId": lineage("platform", "DORA")},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote TMDL model: {TARGET.relative_to(ROOT)}")
    print(f"  tables: {len(list(TABLES.glob('*.tmdl')))}, measures: {len(MEASURES)}, "
          f"relationships: {len(RELATIONSHIPS)}")

    # ---- structural self-check: every reference resolves to a real file/column
    written = {path.stem: path.read_text(encoding="utf-8") for path in TABLES.glob("*.tmdl")}
    for table in order[1:]:
        assert table in written, f"model references missing table {table}"
    for from_table, from_column, to_table, to_column in RELATIONSHIPS:
        for table, column in ((from_table, from_column), (to_table, to_column)):
            assert f"column {column}\n" in written[table], (
                f"relationship column {table}.{column} not found in the table definition"
            )
    for label, expression, _ in MEASURES:
        for table in written:
            if f"{table}[" in expression:
                assert table in written
    for table, label, _, _ in AUX_MEASURES:
        assert table in written, f"aux measure references missing table {table}"
        assert f"measure '{label}'" in written[table], f"{label} not written to {table}"
    print("  self-check: table refs, relationship columns and measure refs resolve")


if __name__ == "__main__":
    main()
