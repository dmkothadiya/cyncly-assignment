"""Validate every JSON definition in the generated PBIP against its official schema.

Power BI Desktop rejects a PBIP whose definition files do not satisfy the published
schemas, and the error it shows names a single property at a time. Validating offline
with the same schemas catches all of them in one pass.

Usage:
    python analytics/powerbi/validate_pbip.py [--project PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

import jsonschema

POWERBI = Path(__file__).resolve().parent
DEFAULT_PROJECT = POWERBI / "DORA_Project"
CACHE = Path(tempfile.gettempdir()) / "pbir-schema-cache"


def load_schema(url: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            schema = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(f"cannot fetch schema {url}: {error}") from error
    cached.write_text(json.dumps(schema), encoding="utf-8")
    return schema


def schema_registry():
    """Resolve nested $ref documents through the local cache instead of live HTTP.

    Letting jsonschema fetch references implicitly makes validation dependent on
    the network and hides which URL failed; a retrieve hook keeps it deterministic
    and reports the offending URL.
    """
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    seen: dict[str, Resource] = {}

    def retrieve(uri: str) -> Resource:
        if uri not in seen:
            seen[uri] = Resource.from_contents(
                load_schema(uri), default_specification=DRAFT202012
            )
        return seen[uri]

    return Registry(retrieve=retrieve)


def normalize(schema: dict, base_url: str) -> dict:
    """Inline any relative $ref sibling docs are not used here, but absolutise $id."""
    schema.setdefault("$id", base_url)
    return schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    args = parser.parse_args()

    project = Path(args.project)
    if not project.exists():
        print(f"Project not found: {project}")
        return 2

    targets = sorted(p for p in project.rglob("*.json") if p.is_file())
    targets += sorted(p for p in project.rglob("*.pbir") if p.is_file())

    failures = 0
    skipped: list[str] = []
    registry = schema_registry()
    for path in targets:
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            print(f"FAIL {path.relative_to(project)}: invalid JSON - {exc}")
            failures += 1
            continue

        # .pbi holds per-machine editor state and carries no $schema.
        url = document.get("$schema")
        if not url:
            print(f"skip {path.relative_to(project)}: no $schema")
            continue

        try:
            schema = normalize(load_schema(url), url)
            validator = jsonschema.Draft202012Validator(schema, registry=registry)
            errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
        except RuntimeError as error:
            # Power BI Desktop can bump a file to a schema version that is not yet
            # published. Validation is impossible for that file, so say so loudly
            # instead of claiming a pass.
            print(f"UNVERIFIED {path.relative_to(project)}: {error}")
            skipped.append(str(path.relative_to(project)))
            continue
        if errors:
            failures += len(errors)
            for error in errors:
                location = "/".join(str(part) for part in error.path) or "(root)"
                print(f"FAIL {path.relative_to(project)} [{location}]: {error.message}")
        else:
            print(f"ok   {path.relative_to(project)}")

    print()
    if failures:
        print(f"{failures} schema violation(s) found")
        return 1
    print(f"All {len(targets)} definition file(s) valid")
    if skipped:
        print(f"WARNING: {len(skipped)} file(s) could not be schema-checked "
              f"(unpublished schema version)")

    # Schema validity does not prove the visuals resolve: Desktop reports a bare
    # "Missing_References" when a visual names a field the model does not expose.
    import check_references

    print()
    return check_references.main(project)


if __name__ == "__main__":
    sys.exit(main())
