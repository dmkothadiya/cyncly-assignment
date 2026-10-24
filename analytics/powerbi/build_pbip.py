"""Generate a Power BI Project (PBIP) for the DORA baseline report.

PBIP is unsigned plain text, so it can be generated outside Power BI Desktop - unlike
a .pbix, whose package signature is invalidated by any external edit.

Output:
    analytics/powerbi/DORA_Project/
        DORA.pbip
        DORA.Report/            (PBIR report definition)
        DORA.SemanticModel/     (TMDL model, copied from DORA.SemanticModel)

Usage:
    python analytics/powerbi/build_pbip.py            # full report
    python analytics/powerbi/build_pbip.py --no-visuals
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POWERBI = Path(__file__).resolve().parent
MODEL_SOURCE = POWERBI / "DORA.SemanticModel"
TARGET = POWERBI / "DORA_Project"

NAVY = "#16324F"
TEAL = "#1F6F78"
AMBER = "#8A5A00"
GREY = "#4A5568"
LIGHT = "#F2F5F8"

PAGE = "doraBaselinePage0001"
PAGES = [
    (PAGE, "DORA baseline"),
    ("doraGovernancePage0002", "Grain, lineage & quality"),
]
NAMESPACE = uuid.UUID("2f5b1a10-4c33-4d0a-9c1e-7a1b2c3d4e5f")


def read_gold(name: str) -> list[dict[str, str]]:
    with (ROOT / "analytics" / "gold" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def headline() -> tuple[str, str]:
    """Header and footer text taken from Gold, so a refresh cannot leave them stale."""
    summary = read_gold("dora_period_summary.csv")[0]
    checks = read_gold("dq_check_results.csv")
    passed = sum(1 for row in checks if row["status"] == "PASS")
    subtitle = (
        f"{summary['projects']} projects  |  {summary['total_deployments']} completed builds  |  "
        f"{summary['period_start']} to {summary['period_end']}  |  "
        "deployment proxy, not a release event"
    )
    footer = (
        f"Built from the Gold layer  |  {passed}/{len(checks)} data-quality checks passed  |  "
        f"{summary['lead_time_sample_size']} lead-time observations, "
        f"{summary['mttr_sample_size']} MTTR observations"
    )
    return subtitle, footer

SCHEMA = {
    "pbip": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    "pbir": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "version": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    "report": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
    "pages": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "page": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
    "visual": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json",
}


def schema_version(key: str) -> str:
    """Version segment of a schema URL, e.g. .../report/3.3.0/schema.json -> 3.3.0."""
    return SCHEMA[key].rsplit("/", 2)[-2]


def vid(label: str) -> str:
    return uuid.uuid5(NAMESPACE, label).hex[:20]


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def column(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure(entity: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def projection(field: dict, query_ref: str, display: str | None = None) -> dict:
    item = {"field": field, "queryRef": query_ref, "nativeQueryRef": query_ref.split(".")[-1]}
    if display:
        item["displayName"] = display
    return item


def sort_by(*fields: tuple[str, str, str]) -> dict:
    """Sort clause for a visual query; without it a table renders in load order."""
    return {
        "sortDefinition": {
            "sort": [
                {"field": column(entity, name), "direction": direction}
                for entity, name, direction in fields
            ]
        }
    }


def container(name, x, y, w, h, z, visual) -> dict:    return {
        "$schema": SCHEMA["visual"],
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": visual,
    }


def run(text: str, size: str, color: str, bold: bool = False) -> dict:
    style = {"fontSize": size, "color": color, "fontFamily": "Segoe UI"}
    if bold:
        style["fontWeight"] = "bold"
    return {"value": text, "textStyle": style}


def textbox(name, x, y, w, h, z, runs, background=None) -> dict:
    visual = {
        "visualType": "textbox",
        "objects": {"general": [{"properties": {"paragraphs": [
            {"textRuns": runs, "horizontalTextAlignment": "left"}
        ]}}]},
    }
    if background:
        visual["visualContainerObjects"] = {
            "background": [{"properties": {
                "show": literal("true"),
                "color": {"solid": {"color": literal(f"'{background}'")}},
                "transparency": literal("0D"),
            }}],
            "border": [{"properties": {"show": literal("false")}}],
        }
    return container(name, x, y, w, h, z, visual)


def card(name, x, y, w, h, z, title, accent) -> dict:
    return container(name, x, y, w, h, z, {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [
            projection(measure("DoraServiceMonth", title), f"DoraServiceMonth.{title}")
        ]}}},
        "objects": {
            "labels": [{"properties": {
                "color": {"solid": {"color": literal(f"'{NAVY}'")}},
                "fontSize": literal("28D"),
            }}],
            "categoryLabels": [{"properties": {
                "show": literal("true"),
                "color": {"solid": {"color": literal(f"'{GREY}'")}},
                "fontSize": literal("9D"),
            }}],
        },
        "visualContainerObjects": {
            "background": [{"properties": {
                "show": literal("true"),
                "color": {"solid": {"color": literal(f"'{LIGHT}'")}},
                "transparency": literal("0D"),
            }}],
            "border": [{"properties": {
                "show": literal("true"),
                "color": {"solid": {"color": literal(f"'{accent}'")}},
            }}],
            "title": [{"properties": {"show": literal("false")}}],
        },
    })


def build_baseline_visuals() -> list[dict]:
    visuals: list[dict] = []
    subtitle, footer = headline()

    visuals.append(textbox(vid("header"), 0, 0, 1920, 105, 0,
                           [run(" ", "8pt", NAVY)], background=NAVY))
    visuals.append(textbox(vid("title"), 30, 16, 1350, 46, 1,
                           [run("DORA baseline  |  July - December 2024", "20pt", "#FFFFFF", True)]))
    visuals.append(textbox(vid("subtitle"), 30, 62, 1860, 34, 2,
                           [run(subtitle, "10pt", "#C9D6E3")]))

    kpis = [
        ("Deployment Frequency (per project-month)", 30, TEAL),
        ("Lead Time for Changes (median h)", 489, TEAL),
        ("Change Failure Rate %", 948, AMBER),
        ("MTTR (median h)", 1407, AMBER),
    ]
    for index, (title, x, accent) in enumerate(kpis):
        visuals.append(card(vid(f"kpi{index}"), x, 123, 453, 144, 10 + index, title, accent))

    visuals.append(container(vid("trend"), 30, 288, 1050, 288, 20, {
        "visualType": "lineChart",
        "query": {"queryState": {
            "Category": {"projections": [projection(
                column("DoraServiceMonth", "month_start"), "DoraServiceMonth.month_start")]},
            "Y": {"projections": [projection(
                measure("DoraServiceMonth", "Deployments"), "DoraServiceMonth.Deployments")]},
            "Series": {"projections": [projection(
                column("DoraServiceMonth", "project_name"), "DoraServiceMonth.project_name")]},
        }},
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal("true"), "text": literal(
                "'Deployment volume by project and month'")}}],
        },
    }))

    visuals.append(container(vid("leadtime"), 1104, 288, 786, 288, 21, {
        "visualType": "columnChart",
        "query": {"queryState": {
            # The axis comes from the fact table itself: DoraServiceMonth[reporting_month]
            # has no filter path to FactCommitLink, so it made every bar repeat the
            # period-wide median instead of showing each month.
            "Category": {"projections": [projection(
                column("FactCommitLink", "reporting_month"),
                "FactCommitLink.reporting_month")]},
            "Y": {"projections": [projection(
                measure("DoraServiceMonth", "Lead Time for Changes (median h)"),
                "DoraServiceMonth.Lead Time for Changes (median h)")]},
        }},
        "objects": {
            "dataPoint": [{"properties": {
                "fill": {"solid": {"color": literal(f"'{TEAL}'")}}}}],
        },
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal("true"), "text": literal(
                "'Lead time, median hours (where observed)'")}}],
        },
    }))

    table_fields = [
        ("project_name", "Project"),
        ("reporting_month", "Month"),
        ("deployment_count", "Builds"),
        ("lead_time_median_hours", "Lead h"),
        ("lead_time_sample_size", "Lead n"),
        ("change_failure_rate_pct", "CFR %"),
        ("mttr_median_hours", "MTTR h"),
        ("mttr_sample_size", "MTTR n"),
        ("data_quality_status", "Status"),
    ]
    visuals.append(container(vid("grain"), 30, 597, 1050, 294, 22, {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": [
            projection(column("DoraServiceMonth", name), f"DoraServiceMonth.{name}", header)
            for name, header in table_fields
        ]}}},
        # 8 pt keeps all nine grain rows visible without scrolling.
        "objects": {
            "values": [{"properties": {"fontSize": literal("8D")}}],
            "columnHeaders": [{"properties": {"fontSize": literal("8D")}}],
        },
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal("true"), "text": literal(
                "'Published grain: project x month (page 2 has every column)'")}}],
        },
    }))

    caveat_runs = [run("READ BEFORE QUOTING", "9pt", AMBER, True)]
    for line in (
        "- Builds are a deployment proxy - no release or environment event exists in the source.",
        "- Change failure rate matches incidents to the project-month, not to a specific deployment.",
        "- MTTR rests on 3 incidents; treat as indicative.",
        "- Blank means not observed. It is never zero.",
        "- 'minimal' means only deployments and failure rate could be computed. Page 2 says why, per row.",
    ):
        caveat_runs.append({"value": "\n" + line,
                            "textStyle": {"fontSize": "8pt", "color": "#1A202C"}})
    visuals.append(textbox(vid("caveats"), 1104, 597, 786, 294, 23, caveat_runs,
                           background=LIGHT))

    visuals.append(textbox(vid("footer"), 30, 909, 1860, 40, 24,
                           [run(footer, "8pt", GREY)]))
    return visuals


def build_governance_visuals() -> list[dict]:
    """Page 2: every published column, plus the Bronze -> Silver -> Gold trail."""
    visuals: list[dict] = []
    subtitle, footer = headline()

    visuals.append(textbox(vid("govHeader"), 0, 0, 1920, 105, 0,
                           [run(" ", "8pt", NAVY)], background=NAVY))
    visuals.append(textbox(vid("govTitle"), 30, 16, 1500, 46, 1,
                           [run("Metric grain, lineage and data quality", "20pt", "#FFFFFF", True)]))
    visuals.append(textbox(vid("govSubtitle"), 30, 62, 1860, 34, 2,
                           [run(subtitle, "10pt", "#C9D6E3")]))

    lineage_fields = [
        ("layer", "Layer"),
        ("table_name", "Table"),
        ("rows_in", "In"),
        ("rows_out", "Out"),
        ("rows_dropped", "Dropped"),
        ("rule", "Rule applied"),
    ]
    visuals.append(container(vid("lineageTable"), 30, 123, 1120, 400, 10, {
        "visualType": "tableEx",
        "query": {
            "queryState": {"Values": {"projections": [
                projection(column("PipelineLineage", name), f"PipelineLineage.{name}", header)
                for name, header in lineage_fields
            ]}},
            **sort_by(("PipelineLineage", "layer", "Ascending")),
        },
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal("true"), "text": literal(
                "'Bronze -> Silver -> Gold: what each layer kept and what it removed'")}}],
        },
    }))

    dq_fields = [
        ("check_id", "ID"),
        ("name", "Check"),
        ("status", "Status"),
        ("detail", "Evidence"),
    ]
    visuals.append(container(vid("dqTable"), 1170, 123, 720, 400, 11, {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": [
            projection(column("DqCheckResult", name), f"DqCheckResult.{name}", header)
            for name, header in dq_fields
        ]}}},
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal("true"), "text": literal(
                "'Executable data-quality gate'")}}],
        },
    }))

    full_grain = [
        ("project_name", "Project"),
        ("reporting_month", "Month"),
        ("deployment_count", "Builds"),
        ("deployment_frequency_per_day", "DF / day"),
        ("lead_time_median_hours", "Lead h"),
        ("lead_time_sample_size", "Lead n"),
        ("lead_time_status", "Lead status"),
        ("failed_deployments", "Failed"),
        ("change_failure_rate_pct", "CFR %"),
        ("mttr_median_hours", "MTTR h"),
        ("mttr_sample_size", "MTTR n"),
        ("mttr_status", "MTTR status"),
        ("mttr_all_incidents_hours", "All-cause h"),
        ("mttr_all_incidents_sample", "All-cause n"),
        ("median_build_minutes", "Build min"),
        ("metrics_observed", "Observed"),
        ("data_quality_status", "Status"),
        ("status_reason", "What is missing, and why"),
    ]
    visuals.append(container(vid("fullGrain"), 30, 543, 1860, 350, 20, {
        "visualType": "tableEx",
        "query": {
            "queryState": {"Values": {"projections": [
                projection(column("DoraServiceMonth", name), f"DoraServiceMonth.{name}", header)
                for name, header in full_grain
            ]}},
            **sort_by(
                ("DoraServiceMonth", "project_name", "Ascending"),
                ("DoraServiceMonth", "reporting_month", "Ascending"),
            ),
        },
        "objects": {
            "values": [{"properties": {"fontSize": literal("7D")}}],
            "columnHeaders": [{"properties": {"fontSize": literal("7D")}}],
        },
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal("true"), "text": literal(
                "'dora_service_month: every published column at project x month grain'")}}],
        },
    }))

    visuals.append(textbox(vid("govFooter"), 30, 909, 1860, 40, 24,
                           [run(footer, "8pt", GREY)]))
    return visuals


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-visuals", action="store_true",
                        help="emit the project with an empty page (scaffolding test)")
    args = parser.parse_args()

    if TARGET.exists():
        shutil.rmtree(TARGET)
    report_dir = TARGET / "DORA.Report"
    model_dir = TARGET / "DORA.SemanticModel"

    shutil.copytree(MODEL_SOURCE, model_dir)

    write_json(TARGET / "DORA.pbip", {
        "$schema": SCHEMA["pbip"],
        "version": "1.0",
        "artifacts": [{"report": {"path": "DORA.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })

    write_json(report_dir / "definition.pbir", {
        "$schema": SCHEMA["pbir"],
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../DORA.SemanticModel"}},
    })
    write_json(report_dir / "definition" / "version.json", {
        "$schema": SCHEMA["version"],
        "version": "2.0.0",
    })
    write_json(report_dir / "definition" / "report.json", {
        "$schema": SCHEMA["report"],
        "themeCollection": {
            "baseTheme": {
                "name": "Fluent2-CY26SU10",
                "reportVersionAtImport": {
                    "page": schema_version("page"),
                    "report": schema_version("report"),
                    "visual": schema_version("visual"),
                },
                "type": "SharedResources",
            }
        },
    })
    write_json(report_dir / "definition" / "pages" / "pages.json", {
        "$schema": SCHEMA["pages"],
        "pageOrder": [name for name, _ in PAGES],
        "activePageName": PAGE,
    })

    builders = {
        PAGE: build_baseline_visuals,
        "doraGovernancePage0002": build_governance_visuals,
    }
    total = 0
    for page_name, display_name in PAGES:
        write_json(report_dir / "definition" / "pages" / page_name / "page.json", {
            "$schema": SCHEMA["page"],
            "name": page_name,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "height": 1080,
            "width": 1920,
        })
        visuals = [] if args.no_visuals else builders[page_name]()
        total += len(visuals)
        for visual in visuals:
            write_json(
                report_dir / "definition" / "pages" / page_name / "visuals"
                / visual["name"] / "visual.json",
                visual,
            )

    print(f"Wrote {TARGET.relative_to(ROOT)}")
    print(f"  model    : {len(list((model_dir / 'definition' / 'tables').glob('*.tmdl')))} TMDL tables")
    print(f"  report   : {len(PAGES)} page(s) 1920x1080 -> "
          f"{', '.join(name for _, name in PAGES)}")
    print(f"  visuals  : {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
