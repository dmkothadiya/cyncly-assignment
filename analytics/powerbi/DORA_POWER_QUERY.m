// DORA medallion queries for Power BI Desktop
// Paste each section into a blank query (Home > Transform data > Advanced Editor),
// or create one blank query per name below. Set pGoldFolder first.
//
// Folder parameter is created as a Power Query parameter named pGoldFolder,
// for example: C:\workspace\cyncly-assignment\analytics\gold

// ---------------------------------------------------------------- parameter
// Name: pGoldFolder   Type: Text
"C:\workspace\cyncly-assignment\analytics\gold"

// ---------------------------------------------------------------- DimProject
// Name: DimProject
let
    Source = Csv.Document(
        File.Contents(pGoldFolder & "\dim_project.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"project_sk", type text},
            {"project_name", type text},
            {"is_mapped", type logical}
        }
    )
in
    Typed

// ------------------------------------------------------------ FactDeployment
// Name: FactDeployment
let
    Source = Csv.Document(
        File.Contents(pGoldFolder & "\fact_deployment.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"deployment_id", type text},
            {"project_sk", type text},
            {"component_name", type text},
            {"pipeline_id", type text},
            {"pipeline_start_time", type datetimezone},
            {"pipeline_end_time", type datetimezone},
            {"duration_minutes", type number},
            {"deployment_date", type date},
            {"reporting_month", type text},
            {"project_name", type text}
        }
    )
in
    Typed

// ------------------------------------------------------------- FactCommitLink
// Name: FactCommitLink
let
    Source = Csv.Document(
        File.Contents(pGoldFolder & "\fact_commit_link.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"commit_id", type text},
            {"deployment_id", type text},
            {"project_sk", type text},
            {"author_date", type datetimezone},
            {"deployed_at", type datetimezone},
            {"lead_time_hours", type number},
            {"is_linkable", type logical},
            {"is_valid_lead_time", type logical},
            {"grain", type text}
        }
    )
in
    Typed

// --------------------------------------------------------------- FactIncident
// Name: FactIncident
let
    Source = Csv.Document(
        File.Contents(pGoldFolder & "\fact_incident.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"workitem_id", type text},
            {"project_sk", type text},
            {"project_name", type text},
            {"caused_by_deployment", Int64.Type},
            {"started_at", type datetimezone},
            {"resolved_at", type datetimezone},
            {"restore_hours", type number},
            {"reporting_month", type text}
        }
    )
in
    Typed

// ------------------------------------------------------------ DoraServiceMonth
// Name: DoraServiceMonth  (published grain: project_sk x reporting_month)
let
    Source = Csv.Document(
        File.Contents(pGoldFolder & "\dora_service_month.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"project_sk", type text},
            {"project_name", type text},
            {"reporting_month", type text},
            {"grain", type text},
            {"days_in_month", Int64.Type},
            {"deployment_count", Int64.Type},
            {"deployment_frequency_per_day", type number},
            {"lead_time_median_hours", type number},
            {"lead_time_sample_size", Int64.Type},
            {"lead_time_available", type logical},
            {"failed_deployments", Int64.Type},
            {"change_failure_rate_pct", type number},
            {"mttr_median_hours", type number},
            {"mttr_sample_size", Int64.Type},
            {"mttr_available", type logical},
            {"median_build_minutes", type number},
            {"data_quality_status", type text},
            {"notes", type text}
        }
    ),
    WithDate = Table.AddColumn(
        Typed,
        "month_start",
        each Date.FromText([reporting_month] & "-01"),
        type date
    )
in
    WithDate

// ------------------------------------------------------------------ DimDate
// Name: DimDate  (calculated table, no source file)
let
    StartDate = #date(2024, 1, 1),
    EndDate = #date(2025, 12, 31),
    DayCount = Duration.Days(EndDate - StartDate) + 1,
    DateList = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),
    ToTable = Table.FromList(DateList, Splitter.SplitByNothing(), {"Date"}),
    TypedDate = Table.TransformColumnTypes(ToTable, {{"Date", type date}}),
    WithParts = Table.AddColumn(TypedDate, "Year", each Date.Year([Date]), Int64.Type),
    WithMonth = Table.AddColumn(WithParts, "Month Number", each Date.Month([Date]), Int64.Type),
    WithMonthName = Table.AddColumn(WithMonth, "Month", each Date.ToText([Date], "MMM"), type text),
    WithMonthKey = Table.AddColumn(WithMonthName, "Month Key", each Date.ToText([Date], "yyyy-MM"), type text),
    WithQuarter = Table.AddColumn(WithMonthKey, "Quarter", each "Q" & Number.ToText(Date.QuarterOfYear([Date])), type text)
in
    WithQuarter
