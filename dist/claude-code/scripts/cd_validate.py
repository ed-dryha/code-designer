#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema==4.26.0"]
# ///
"""Validate a structure model: JSON Schema (2020-12) plus semantic checks.

Exit codes: 0 clean, 1 violations (one per line `<json-path>: <rule-id>: <message>`), 2 usage.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402

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


def _span_ok(sp):
    return isinstance(sp, dict) and isinstance(sp.get("startLine"), int) and isinstance(sp.get("endLine"), int)


def semantic_errors(model):
    """Return (json-path, rule-id, message) tuples."""
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
            errs.append((f"$.symbols[{i}].id", "duplicate-id", f"duplicate id {sid!r} (first at index {ids[sid]})"))
        else:
            ids[sid] = i
    for i, s in enumerate(symbols):
        if not isinstance(s, dict):
            continue
        par = s.get("parent")
        sp = s.get("span")
        if par is not None:
            if par not in ids:
                errs.append((f"$.symbols[{i}].parent", "parent-unresolved", f"parent {par!r} does not resolve"))
            else:
                ps = symbols[ids[par]]
                psp = ps.get("span") if isinstance(ps, dict) else None
                if (_span_ok(sp) and _span_ok(psp) and ps.get("file") == s.get("file")
                        and (sp["startLine"] < psp["startLine"] or sp["endLine"] > psp["endLine"])):
                    errs.append((f"$.symbols[{i}].span", "span-outside-parent",
                                 f"span {sp['startLine']}-{sp['endLine']} outside parent {par!r} "
                                 f"{psp['startLine']}-{psp['endLine']}"))
        if _span_ok(sp) and sp["endLine"] < sp["startLine"]:
            errs.append((f"$.symbols[{i}].span", "span-order", "endLine < startLine"))
        if "inferred" in s and "provenance" in s and s["inferred"] != (s["provenance"] == "agent"):
            errs.append((f"$.symbols[{i}].inferred", "inferred-provenance",
                         "inferred must be true iff provenance is agent"))
        if s.get("hash") is None and s.get("provenance") == "tree-sitter":
            errs.append((f"$.symbols[{i}].hash", "hash-null", "hash may be null only for agent provenance"))
        sid, fl = s.get("id"), s.get("file")
        if isinstance(sid, str) and isinstance(fl, str) and not sid.startswith(fl + "#"):
            errs.append((f"$.symbols[{i}].id", "id-prefix", f"id does not start with file prefix {fl + '#'!r}"))
    return errs


def coverage_errors(model, root=None):
    errs = []
    cov = model.get("coverage")
    if not isinstance(cov, dict):
        return errs
    where = {}
    for i, f in enumerate(cov.get("files") or []):
        if isinstance(f, dict) and isinstance(f.get("path"), str):
            where.setdefault(f["path"], []).append(f"files[{i}]")
    for i, u in enumerate(cov.get("unavailable") or []):
        if isinstance(u, dict):
            for p in u.get("files") or []:
                where.setdefault(p, []).append(f"unavailable[{i}]")
    skipped = []
    for i, sk in enumerate(cov.get("skipped") or []):
        if isinstance(sk, dict) and isinstance(sk.get("path"), str):
            where.setdefault(sk["path"], []).append(f"skipped[{i}]")
            skipped.append(sk["path"])
    for p, locs in sorted(where.items()):
        if len(locs) > 1:
            errs.append((f"$.coverage.{locs[0]}", "coverage-conflict",
                         f"{p!r} listed in multiple places: {', '.join(locs)}"))
    if root:
        import languages
        for dirpath, dirs, fnames in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in cd_common.IGNORE_DIRS)
            for fn in sorted(fnames):
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
                if languages.language_for(rel) is None or rel in where:
                    continue
                if any(rel.startswith(sp.rstrip("/") + "/") for sp in skipped):
                    continue
                errs.append(("$.coverage", "coverage-missing",
                             f"source file {rel!r} is in none of files/unavailable/skipped"))
    return errs


def validate(model, schema, root=None):
    from jsonschema import Draft202012Validator
    errs = [(jpath(e), "schema", e.message) for e in Draft202012Validator(schema).iter_errors(model)]
    if isinstance(model, dict):
        errs.extend(semantic_errors(model))
        errs.extend(coverage_errors(model, root))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate structure model")
    ap.add_argument("model")
    ap.add_argument("--schema")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", help="enable coverage-completeness check against this directory")
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
    errs = validate(model, schema, args.root)
    if args.json:
        print(json.dumps([{"path": p, "rule": r, "message": m} for p, r, m in errs], indent=2))
    else:
        for p, r, m in errs:
            print(f"{p}: {r}: {m}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
