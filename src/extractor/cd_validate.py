#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema==4.26.0"]
# ///
"""Validate a structure model: JSON Schema (2020-12) plus semantic checks.

Exit codes: 0 clean, 1 violations (one per line `<json-path>: <message>`), 2 usage.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402,F401  (shared helpers live there)

SCHEMA_NAME = "structure-model.schema.json"


def find_schema(explicit):
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, SCHEMA_NAME), os.path.join(here, "..", "schema", SCHEMA_NAME)):
        if os.path.isfile(cand):
            return cand
    return None


def jpath(err):
    parts = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in err.absolute_path)
    return "$" + parts


def semantic_errors(model):
    errs = []
    symbols = model.get("symbols")
    if not isinstance(symbols, list):
        return errs
    ids = {}
    for i, s in enumerate(symbols):
        if not isinstance(s, dict):
            continue
        sid = s.get("id")
        if sid in ids:
            errs.append((f"$.symbols[{i}].id", f"duplicate id {sid!r} (first at index {ids[sid]})"))
        else:
            ids[sid] = i
    for i, s in enumerate(symbols):
        if not isinstance(s, dict):
            continue
        par = s.get("parent")
        if par is not None and par not in ids:
            errs.append((f"$.symbols[{i}].parent", f"parent {par!r} does not resolve"))
        sp = s.get("span")
        if isinstance(sp, dict) and isinstance(sp.get("startLine"), int) and isinstance(sp.get("endLine"), int):
            if sp["endLine"] < sp["startLine"]:
                errs.append((f"$.symbols[{i}].span", "endLine < startLine"))
        if "inferred" in s and "provenance" in s and s["inferred"] != (s["provenance"] == "agent"):
            errs.append((f"$.symbols[{i}].inferred", "inferred must be true iff provenance is agent"))
        if s.get("hash") is None and s.get("provenance") == "tree-sitter":
            errs.append((f"$.symbols[{i}].hash", "hash may be null only for agent provenance"))
        fid, fl = s.get("id"), s.get("file")
        if isinstance(fid, str) and isinstance(fl, str) and not fid.startswith(fl + "#"):
            errs.append((f"$.symbols[{i}].id", f"id does not start with file prefix {fl + '#'!r}"))
    return errs


def validate(model, schema):
    from jsonschema import Draft202012Validator
    errs = [(jpath(e), e.message) for e in Draft202012Validator(schema).iter_errors(model)]
    errs.extend(semantic_errors(model))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate structure model")
    ap.add_argument("model")
    ap.add_argument("--schema")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    schema_path = find_schema(args.schema)
    if not schema_path or not os.path.isfile(schema_path):
        print("error: schema not found", file=sys.stderr)
        return 2
    try:
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        with open(args.model, encoding="utf-8") as fh:
            model = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    errs = validate(model, schema)
    if args.json:
        print(json.dumps([{"path": p, "message": m} for p, m in errs], indent=2))
    else:
        for p, m in errs:
            print(f"{p}: {m}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
