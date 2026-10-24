"""Cross-check every field reference in the PBIR visuals against the TMDL semantic model.

Power BI reports "Missing_References" at render time when a visual points at a table,
column or measure that the model does not expose. That error is opaque, so this script
resolves all references offline and prints the ones that cannot be satisfied.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent / "DORA_Project"


def read_tables(model_dir: pathlib.Path) -> dict[str, dict[str, set[str]]]:
    tables: dict[str, dict[str, set[str]]] = {}
    for path in sorted((model_dir / "tables").glob("*.tmdl")):
        current = None
        buckets = {"columns": set(), "measures": set(), "hierarchies": set()}
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("table "):
                current = raw[len("table ") :].strip()
                continue
            line = raw.strip()
            if line.startswith("column "):
                buckets["columns"].add(line[len("column ") :].strip().strip("'"))
            elif line.startswith("measure "):
                text = line[len("measure ") :]
                name = text.split("=")[0].strip().strip("'")
                buckets["measures"].add(name)
            elif line.startswith("hierarchy "):
                name = line[len("hierarchy ") :].split("=")[0].strip().strip("'")
                buckets["hierarchies"].add(name)
        if current:
            tables[current] = buckets
    return tables


def iter_visuals(report_dir: pathlib.Path):
    for path in sorted(report_dir.glob("pages/*/visuals/*/visual.json")):
        yield path, json.loads(path.read_text(encoding="utf-8"))


def walk_refs(node, found: list[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        if "Column" in node and isinstance(node["Column"], dict):
            col = node["Column"]
            if "Expression" in col and "Property" in col:
                found.append((_entity(col["Expression"]), f"column:{col['Property']}"))
        if "Measure" in node and isinstance(node["Measure"], dict):
            meas = node["Measure"]
            if "Expression" in meas and "Property" in meas:
                found.append((_entity(meas["Expression"]), f"measure:{meas['Property']}"))
        if "Hierarchy" in node and isinstance(node["Hierarchy"], dict):
            hier = node["Hierarchy"]
            if "Expression" in hier and "Property" in hier:
                found.append((_entity(hier["Expression"]), f"hierarchy:{hier['Property']}"))
        if node.get("SourceRef") and isinstance(node["SourceRef"], dict):
            entity = node["SourceRef"].get("Entity")
            prop = node.get("Property")
            kind = node.get("Active", {})
            if entity and prop and isinstance(kind, dict):
                bucket = "measure" if "Measure" in kind else "column"
                found.append((entity, f"{bucket}:{prop}"))
        for value in node.values():
            walk_refs(value, found)
    elif isinstance(node, list):
        for value in node:
            walk_refs(value, found)


def _entity(expression) -> str:
    if isinstance(expression, dict):
        source = expression.get("SourceRef", {})
        if isinstance(source, dict) and source.get("Entity"):
            return str(source["Entity"])
        return "?"
    return "?"


def main(project: pathlib.Path | str | None = None) -> int:
    root = pathlib.Path(project) if project else ROOT
    tables = read_tables(root / "DORA.SemanticModel" / "definition")
    problems: list[str] = []
    for path, document in iter_visuals(root / "DORA.Report" / "definition"):
        refs: list[tuple[str, str]] = []
        walk_refs(document, refs)
        seen = set()
        for entity, ref in refs:
            if (entity, ref) in seen:
                continue
            seen.add((entity, ref))
            kind, _, name = ref.partition(":")
            if entity not in tables:
                problems.append(f"{path.parent.name}: unknown table {entity!r}")
                continue
            bucket = {"column": "columns", "measure": "measures", "hierarchy": "hierarchies"}[kind]
            if name not in tables[entity][bucket]:
                problems.append(
                    f"{path.parent.name}: {entity}.{name} ({kind}) not found; "
                    f"available {kind}s: {sorted(tables[entity][bucket])}"
                )

    print(f"model tables: {sorted(tables)}")
    for table, buckets in tables.items():
        print(f"  {table}: {len(buckets['columns'])} columns, {len(buckets['measures'])} measures")
    if problems:
        print("\nUNRESOLVED REFERENCES")
        for line in problems:
            print("  " + line)
        return 1
    print("\nall visual field references resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
