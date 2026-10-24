"""Render a layout reference for the Power BI DORA baseline page.

Not Power BI output: this draws the intended page with the real Gold numbers so
the report can be reviewed without the desktop tool. Drawn with Pillow so the
solution has no heavy plotting dependency.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "analytics" / "gold"
DQ = ROOT / "analytics" / "quality-checks" / "dq_results.json"
OUTPUT = ROOT / "analytics" / "dashboard" / "dora_baseline_dashboard.png"

W, H, S = 1600, 900, 2
NAVY = (22, 50, 79)
TEAL = (31, 111, 120)
AMBER = (138, 90, 0)
INK = (26, 32, 44)
GREY = (74, 85, 104)
RULE = (203, 213, 224)
LIGHT = (242, 245, 248)
WHITE = (255, 255, 255)

FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"
FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_LIGHT = r"C:\Windows\Fonts\segoeuil.ttf"


def px(value: float) -> int:
    return int(round(value * S))


def font(size: float, bold: bool = False, light: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else (FONT_LIGHT if light else FONT_REG)
    return ImageFont.truetype(path, px(size))


class Canvas:
    def __init__(self) -> None:
        self.image = Image.new("RGB", (px(W), px(H)), WHITE)
        self.draw = ImageDraw.Draw(self.image)

    def rect(self, box, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = box
        self.draw.rectangle([px(x0), px(y0), px(x1), px(y1)], fill=fill,
                            outline=outline, width=max(1, px(width) - 1))

    def text(self, x, y, value, size=12, color=INK, bold=False, light=False, anchor="la"):
        self.draw.text((px(x), px(y)), str(value), font=font(size, bold, light),
                       fill=color, anchor=anchor)

    def line(self, points, color=RULE, width=1.0):
        self.draw.line([(px(x), px(y)) for x, y in points], fill=color, width=max(1, px(width)))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(path, "PNG")


def main() -> None:
    dora = pd.read_csv(GOLD / "dora_service_month.csv")
    summary = pd.read_csv(GOLD / "dora_period_summary.csv").iloc[0]
    dora = dora.sort_values(["reporting_month", "project_name"]).reset_index(drop=True)

    dq_text = "quality checks not run"
    if DQ.exists():
        payload = json.loads(DQ.read_text(encoding="utf-8"))
        dq_text = (f"{payload['checks_run'] - payload['checks_failed']}/"
                   f"{payload['checks_run']} data-quality checks passed")

    c = Canvas()

    # header ---------------------------------------------------------------
    c.rect((0, 0, W, 88), fill=NAVY)
    c.text(28, 20, "DORA baseline  |  July - December 2024", 26, WHITE, bold=True)
    c.text(28, 58,
           "2 projects   |   342 completed builds   |   deployment proxy, not a release event",
           11.5, (201, 214, 227))

    # kpi cards ------------------------------------------------------------
    cards = [
        ("DEPLOYMENT FREQUENCY", f"{summary['deployment_frequency_per_month']:.0f}",
         f"builds per project-month  ({int(summary['total_deployments'])} total)", TEAL),
        ("LEAD TIME FOR CHANGES",
         "n/a" if pd.isna(summary["lead_time_median_hours"]) else f"{summary['lead_time_median_hours']:.1f} h",
         f"median  |  n={int(summary['lead_time_sample_size'])}  |  link coverage {summary['commit_link_coverage_pct']:.0f}%", TEAL),
        ("CHANGE FAILURE RATE", f"{summary['change_failure_rate_pct']:.2f}%",
         f"{int(summary['deployment_related_incidents'])} deployment-caused incidents", AMBER),
        ("MEAN TIME TO RESTORE",
         "n/a" if pd.isna(summary["mttr_median_hours"]) else f"{summary['mttr_median_hours']:.1f} h",
         f"median  |  n={int(summary['mttr_sample_size'])}  |  indicative only", AMBER),
    ]
    card_w, gap, left = 371, 16, 28
    for index, (label, value, sub, accent) in enumerate(cards):
        x0 = left + index * (card_w + gap)
        c.rect((x0, 108, x0 + card_w, 222), fill=LIGHT)
        c.rect((x0, 108, x0 + 4, 222), fill=accent)
        c.text(x0 + 20, 122, label, 10.5, GREY, bold=True)
        c.text(x0 + 20, 148, value, 40, NAVY, bold=True)
        c.text(x0 + 20, 198, sub, 9.5, accent)

    # trend chart ----------------------------------------------------------
    chart = (70, 268, 900, 520)
    c.text(60, 238, "Deployment volume by project and month", 14, NAVY, bold=True)
    months = sorted(dora["reporting_month"].unique())
    projects = sorted(dora["project_name"].unique())
    max_val = float(dora["deployment_count"].max())

    c.line([(chart[0], chart[3]), (chart[2], chart[3])], RULE, 1)
    c.line([(chart[0], chart[1]), (chart[0], chart[3])], RULE, 1)
    for step in range(0, 5):
        value = max_val * step / 4
        y = chart[3] - (chart[3] - chart[1]) * (value / max_val)
        c.line([(chart[0], y), (chart[2], y)], (235, 239, 243), 1)
        c.text(chart[0] - 10, y, f"{value:.0f}", 9, GREY, anchor="rm")

    palette = [TEAL, (122, 92, 160)]
    plot_w = chart[2] - chart[0]
    step_x = plot_w / max(1, len(months) - 1)
    for index, project in enumerate(projects):
        frame = dora[dora["project_name"] == project].set_index("reporting_month")
        points = []
        for position, month in enumerate(months):
            if month in frame.index:
                value = float(frame.loc[month, "deployment_count"])
                x = chart[0] + position * step_x
                y = chart[3] - (chart[3] - chart[1]) * (value / max_val)
                points.append((x, y))
        if len(points) > 1:
            c.line(points, palette[index % len(palette)], 2.4)
        for x, y in points:
            c.draw.ellipse([px(x - 4), px(y - 4), px(x + 4), px(y + 4)],
                           fill=palette[index % len(palette)])
        legend_x = chart[0] + 400 + index * 140
        legend_y = chart[1] + 14
        c.rect((legend_x, legend_y, legend_x + 11, legend_y + 8), fill=palette[index % len(palette)])
        c.text(legend_x + 18, legend_y - 2, project, 9.5, GREY)

    for position, month in enumerate(months):
        x = chart[0] + position * step_x
        c.text(x, chart[3] + 8, pd.Timestamp(month + "-01").strftime("%b"), 9.5, GREY, anchor="ma")


    # lead time bars -------------------------------------------------------
    bars = (960, 268, 1560, 520)
    c.text(960, 238, "Lead time, median hours (where observed)", 14, NAVY, bold=True)
    observed = dora.dropna(subset=["lead_time_median_hours"])
    c.line([(bars[0], bars[3]), (bars[2], bars[3])], RULE, 1)
    c.line([(bars[0], bars[1]), (bars[0], bars[3])], RULE, 1)
    if not observed.empty:
        peak = float(observed["lead_time_median_hours"].max()) * 1.15
        slot = (bars[2] - bars[0]) / len(observed)
        for position, (_, row) in enumerate(observed.iterrows()):
            height = (bars[3] - bars[1]) * (row["lead_time_median_hours"] / peak)
            x0 = bars[0] + position * slot + slot * 0.22
            x1 = x0 + slot * 0.56
            c.rect((x0, bars[3] - height, x1, bars[3]), fill=TEAL)
            c.text((x0 + x1) / 2, bars[3] - height - 14,
                   f"{row['lead_time_median_hours']:.1f}", 9, NAVY, bold=True, anchor="ma")
            c.text((x0 + x1) / 2, bars[3] + 8,
                   f"{row['project_name'][-1]} {pd.Timestamp(row['reporting_month'] + '-01').strftime('%b')}",
                   8.5, GREY, anchor="ma")
    c.text(960, 546, "Project letter and month; blank months have no linked commit.", 8.5, GREY)

    # grain table ----------------------------------------------------------
    c.text(60, 584, "Published grain: project x month", 13, NAVY, bold=True)
    columns = ["Project", "Month", "Builds", "Lead h", "n", "CFR %", "MTTR h", "Status"]
    widths = [96, 84, 74, 76, 52, 76, 78, 128]
    x_positions = [60]
    for width in widths[:-1]:
        x_positions.append(x_positions[-1] + width)

    header_y = 600
    c.rect((60, header_y, 60 + sum(widths), header_y + 26), fill=NAVY)
    for x, name in zip(x_positions, columns):
        c.text(x + 8, header_y + 6, name, 9.5, WHITE, bold=True)

    row_y = header_y + 25
    for index, row in dora.iterrows():
        if index % 2:
            c.rect((60, row_y, 60 + sum(widths), row_y + 20), fill=LIGHT)
        values = [
            row["project_name"],
            row["reporting_month"],
            f"{int(row['deployment_count'])}",
            "-" if pd.isna(row["lead_time_median_hours"]) else f"{row['lead_time_median_hours']:.1f}",
            "-" if pd.isna(row["lead_time_sample_size"]) else f"{int(row['lead_time_sample_size'])}",
            f"{row['change_failure_rate_pct']:.1f}",
            "-" if pd.isna(row["mttr_median_hours"]) else f"{row['mttr_median_hours']:.1f}",
            str(row["data_quality_status"]),
        ]
        for x, value in zip(x_positions, values):
            c.text(x + 8, row_y + 6, value, 9.5, INK)
        row_y += 24
    c.line([(60, row_y), (60 + sum(widths), row_y)], RULE, 1)

    # caveat panel ---------------------------------------------------------
    panel = (960, 584, 1560, 818)
    c.rect(panel, fill=LIGHT)
    c.rect((panel[0], panel[1], panel[0] + 4, panel[3]), fill=AMBER)
    c.text(panel[0] + 20, panel[1] + 14, "READ BEFORE QUOTING", 10, AMBER, bold=True)
    caveats = [
        "Builds are a deployment proxy - no release or",
        "environment event exists in the source.",
        "",
        "Change failure rate matches incidents to the",
        "project-month, not to a specific deployment.",
        "",
        "MTTR rests on 3 incidents; treat as indicative.",
        "",
        "Blank means not observed. It is never zero.",
    ]
    y = panel[1] + 40
    for entry in caveats:
        c.text(panel[0] + 20, y, entry, 10, INK)
        y += 18

    # footer ---------------------------------------------------------------
    c.line([(28, 840), (W - 28, 840)], RULE, 1)
    c.text(28, 852,
           f"Layout reference rendered from the Gold layer - not a Power BI screenshot.  {dq_text}.",
           9, GREY)
    c.text(W - 28, 852, "Source: Case Study - DORA Metrics Data.xlsx", 9, GREY, anchor="ra")

    c.save(OUTPUT)
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
