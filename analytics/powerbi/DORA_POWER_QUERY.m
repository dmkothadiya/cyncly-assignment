let
    Source = Csv.Document(
        File.Contents("C:\path\to\repository\analytics\gold\dora_metrics.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(
        PromotedHeaders,
        {
            {"project_sk", type text},
            {"reporting_month", type text},
            {"deployment_count", Int64.Type},
            {"project_name", type text},
            {"total_incidents", Int64.Type},
            {"deployment_related_incidents", Int64.Type},
            {"change_failure_rate", Percentage.Type},
            {"mean_time_to_restore_hours", type number},
            {"lead_time_for_changes_hours", type number},
            {"data_quality_status", type text},
            {"metric_notes", type text}
        },
        "en-US"
    )
in
    ChangedTypes
