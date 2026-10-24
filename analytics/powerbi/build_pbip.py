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
NAMESPACE = uuid.UUID("2f5b1a10-4c33-4d0a-9c1e-7a1b2c3d4e5f")

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


def container(name, x, y, w, h, z, visual) -> dict:
    return {
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


def build_visuals() -> list[dict]:
    visuals: list[dict] = []

    visuals.append(textbox(vid("header"), 0, 0, 1920, 105, 0,
                           [run(" ", "8pt", NAVY)], background=NAVY))
    visuals.append(textbox(vid("title"), 30, 16, 1350, 46, 1,
                           [run("DORA baseline  |  July - December 2024", "20pt", "#FFFFFF", True)]))
    visuals.append(textbox(vid("subtitle"), 30, 62, 1500, 34, 2,
                           [run("2 projects  |  342 completed builds  |  deployment proxy, "
                                "not a release event", "10pt", "#C9D6E3")]))

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
            "Category": {"projections": [projection(
                column("DoraServiceMonth", "reporting_month"),
                "DoraServiceMonth.reporting_month")]},
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
        ("lead_time_sample_size", "n"),
        ("change_failure_rate_pct", "CFR %"),
        ("mttr_median_hours", "MTTR h"),
        ("data_quality_status", "Status"),
    ]
    visuals.append(container(vid("grain"), 30, 597, 1050, 294, 22, {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": [
            projection(column("DoraServiceMonth", name), f"DoraServiceMonth.{name}", header)
            for name, header in table_fields
        ]}}},
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal("true"), "text": literal(
                "'Published grain: project x month'")}}],
        },
    }))

    caveat_runs = [run("READ BEFORE QUOTING", "9pt", AMBER, True)]
    for line in (
        "- Builds are a deployment proxy - no release or environment event exists in the source.",
        "- Change failure rate matches incidents to the project-month, not to a specific deployment.",
        "- MTTR rests on 3 incidents; treat as indicative.",
        "- Blank means not observed. It is never zero.",
    ):
        caveat_runs.append({"value": "\n" + line,
                            "textStyle": {"fontSize": "8pt", "color": "#1A202C"}})
    visuals.append(textbox(vid("caveats"), 1104, 597, 786, 294, 23, caveat_runs,
                           background=LIGHT))

    visuals.append(textbox(vid("footer"), 30, 909, 1860, 40, 24,
                           [run("Built from the Gold layer. Data quality: 3/3 "
                                "data-quality checks passed.", "8pt", GREY)]))
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
        "pageOrder": [PAGE],
        "activePageName": PAGE,
    })
    write_json(report_dir / "definition" / "pages" / PAGE / "page.json", {
        "$schema": SCHEMA["page"],
        "name": PAGE,
        "displayName": "DORA baseline",
        "displayOption": "FitToPage",
        "height": 1080,
        "width": 1920,
    })

    visuals = [] if args.no_visuals else build_visuals()
    for visual in visuals:
        write_json(
            report_dir / "definition" / "pages" / PAGE / "visuals" / visual["name"] / "visual.json",
            visual,
        )

    print(f"Wrote {TARGET.relative_to(ROOT)}")
    print(f"  model    : {len(list((model_dir / 'definition' / 'tables').glob('*.tmdl')))} TMDL tables")
    print(f"  report   : page '{PAGE}' 1920x1080")
    print(f"  visuals  : {len(visuals)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
