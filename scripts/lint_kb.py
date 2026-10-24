#!/usr/bin/env python3
"""Lint the Code Designer knowledge base (structure and cross-links)."""
import argparse
import sys
from pathlib import Path

import yaml

SKIP = {"precedence.md", "README.md"}
COMMON = ["id", "type", "title", "links"]
EXTRA = {
    "smell": ["signals"],
    "principle": [],
    "pattern": ["signals", "required_evidence", "anti_signals", "precedence", "cost"],
}
LINK_KEYS = ["smells", "principles", "patterns"]


def load(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1]), text


def lint(kb, expect, allow_missing):
    kb = Path(kb)
    errs = []

    def err(f, rule, msg):
        errs.append(f"{f}: {rule}: {msg}")

    entries = {}
    texts = {}
    for path in sorted(kb.rglob("*.md")):
        if path.name in SKIP:
            continue
        rel = str(path.relative_to(kb))
        try:
            res = load(path)
        except yaml.YAMLError as e:
            err(rel, "frontmatter", f"invalid YAML: {e}")
            continue
        if res is None or not isinstance(res[0], dict):
            err(rel, "frontmatter", "missing YAML frontmatter")
            continue
        fm, text = res
        typ = fm.get("type")
        if typ not in EXTRA:
            err(rel, "missing-key", f"type must be one of {sorted(EXTRA)}")
            continue
        for k in COMMON + EXTRA[typ]:
            if k not in fm or fm[k] is None:
                err(rel, "missing-key", f"required key '{k}'")
        links = fm.get("links")
        if isinstance(links, dict):
            for k in LINK_KEYS:
                if not isinstance(links.get(k, []), list):
                    err(rel, "missing-key", f"links.{k} must be a list")
        elif "links" in fm:
            err(rel, "missing-key", "links must be a mapping")
        if typ == "pattern":
            for k in ("required_evidence", "anti_signals"):
                if k in fm and not fm[k]:
                    err(rel, f"empty-{k}", f"{k} must be non-empty")
            prec = str(fm.get("precedence") or "")
            if Path(prec).name != "precedence.md" or "precedence.md" not in text:
                err(rel, "precedence-ref", "must reference precedence.md")
            elif not (path.parent / prec).resolve().exists():
                err(rel, "precedence-ref", f"{prec} does not exist")
        eid = fm.get("id")
        if eid is not None:
            if eid != path.stem:
                err(rel, "id-mismatch", f"id '{eid}' != file stem '{path.stem}'")
            if eid in entries:
                err(rel, "duplicate-id", f"id '{eid}' also in {entries[eid][1]}")
            else:
                entries[eid] = (fm, rel)

    def lk(fm, key):
        l = fm.get("links")
        return list(l.get(key) or []) if isinstance(l, dict) else []

    inbound = set()
    for eid, (fm, rel) in entries.items():
        for key in LINK_KEYS:
            for target in lk(fm, key):
                if target in entries:
                    if fm["type"] in ("smell", "principle") and key == "patterns":
                        inbound.add(target)
                    if fm["type"] == "pattern" and key in ("smells", "principles"):
                        inbound.add(eid)
                elif allow_missing and str(target).startswith("pattern-"):
                    continue
                else:
                    err(rel, "dangling-link", f"links.{key} -> '{target}' not found")
        if fm["type"] == "smell" and not any(
                p in entries and entries[p][0]["type"] == "principle"
                for p in lk(fm, "principles")):
            err(rel, "smell-no-principle", "smell must link to at least one principle")

    patterns = [e for e, (fm, _) in entries.items() if fm["type"] == "pattern"]
    for p in patterns:
        if p not in inbound:
            err(entries[p][1], "orphan-pattern",
                "pattern not linked to or from any smell/principle")
    if not (allow_missing and len(patterns) == 0):
        if len(patterns) != expect:
            err(str(kb), "pattern-count", f"expected {expect} patterns, found {len(patterns)}")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("kb_dir")
    ap.add_argument("--expect-patterns", type=int, default=23)
    ap.add_argument("--allow-missing-patterns", action="store_true",
                    help="dev only: tolerate unresolved pattern-* links before patterns exist")
    a = ap.parse_args(argv)
    errs = lint(a.kb_dir, a.expect_patterns, a.allow_missing_patterns)
    for e in errs:
        print(e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
