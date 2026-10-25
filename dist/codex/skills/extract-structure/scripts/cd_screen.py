#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Model-count smell pre-screen.

Reads ONLY the structure-model JSON (never source files) and prints candidate
smells as JSON. Output is a list of candidates, never a decision: the agent
must read the flagged span before reporting anything.
Exit codes: 0 ok, 2 usage / unreadable model.
Supertype matching is by name and therefore approximate.
"""
import argparse
import fnmatch
import json
import sys

# Thresholds mirror the signals in the knowledge-base smell files.
GOD_METHODS = 20      # src/knowledge/smells/smell-god-class.md: "more than 20 methods"
GOD_FIELDS = 15       # src/knowledge/smells/smell-god-class.md: very large number of fields
FAT_MEMBERS = 8       # src/knowledge/smells/smell-fat-interface.md: "interface with many methods"
EXPLOSION_SUBTYPES = 5  # src/knowledge/smells/smell-class-explosion.md: subclass per combination
# src/knowledge/smells/smell-speculative-generality.md: single implementation / no second user

CONCRETE_KINDS = ("class", "struct")
ABSTRACT_KINDS = ("interface", "trait", "protocol")
TYPE_KINDS = CONCRETE_KINDS + ABSTRACT_KINDS + ("enum",)
NOTE = ("Counts are model facts only; read the body before deciding "
        "(a candidate is not a finding).")


def _short(name):
    return str(name).replace("::", ".").split(".")[-1].split("<")[0].strip()


def _total(counts):
    return sum(v if isinstance(v, int) else len(v) for v in counts.values())


def screen(model, scope, thr):
    syms = [s for s in model.get("symbols", []) if isinstance(s, dict)]
    types = [s for s in syms if s.get("kind") in TYPE_KINDS]
    children = {}
    for s in syms:
        if s.get("parent"):
            children.setdefault(s["parent"], []).append(s)
    subs = {}
    for t in types:
        for st in t.get("supertypes") or []:
            subs.setdefault(_short(st.get("name", "")), []).append(t["id"])

    def in_scope(f):
        return not scope or any(fnmatch.fnmatch(f, g) for g in scope)

    out = []

    def add(t, smell, counts, signal, reason=None):
        c = {"smell": smell, "symbol": t["id"], "file": t["file"], "counts": counts,
             "signal": signal, "inferred": bool(t.get("inferred")), "note": NOTE}
        if reason:
            c["reason"] = reason
        out.append(c)

    for t in types:
        if not in_scope(t.get("file", "")):
            continue
        kids = children.get(t["id"], [])
        methods = sum(1 for k in kids if k.get("kind") in ("method", "constructor"))
        fields = sum(1 for k in kids if k.get("kind") == "field")
        kind = t.get("kind")
        if kind in CONCRETE_KINDS and (methods > thr["god_methods"] or fields > thr["god_fields"]):
            add(t, "smell-god-class", {"methods": methods, "fields": fields},
                f"{methods} methods and {fields} fields (thresholds {thr['god_methods']}/{thr['god_fields']})")
        if kind in ABSTRACT_KINDS and methods > thr["fat_members"]:
            add(t, "smell-fat-interface", {"members": methods},
                f"{methods} members (threshold {thr['fat_members']})")
        direct = sorted(subs.get(_short(t.get("name", "")), []))
        direct = [d for d in direct if d != t["id"]]
        if len(direct) > thr["explosion_subtypes"]:
            add(t, "smell-class-explosion", {"subtypes": direct},
                f"{len(direct)} direct subtypes (threshold {thr['explosion_subtypes']})")
        if kind in ABSTRACT_KINDS and len(direct) <= 1:
            if len(direct) == 1:
                add(t, "smell-speculative-generality", {"implementers": direct},
                    "abstraction with one implementation", "single implementer in the model")
            else:
                add(t, "smell-speculative-generality", {"implementers": []},
                    "abstraction with no second user", "no implementers in the model")
    out.sort(key=lambda c: (c["smell"], -_total(c["counts"]), c["symbol"]))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--scope", action="append", default=[])
    p.add_argument("--max", type=int, default=None)
    p.add_argument("--god-methods", type=int, default=GOD_METHODS)
    p.add_argument("--god-fields", type=int, default=GOD_FIELDS)
    p.add_argument("--fat-members", type=int, default=FAT_MEMBERS)
    p.add_argument("--explosion-subtypes", type=int, default=EXPLOSION_SUBTYPES)
    try:
        a = p.parse_args(argv)
    except SystemExit:
        return 2
    try:
        with open(a.model, encoding="utf-8") as fh:
            model = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"cannot read model: {e}", file=sys.stderr)
        return 2
    thr = {"god_methods": a.god_methods, "god_fields": a.god_fields,
           "fat_members": a.fat_members, "explosion_subtypes": a.explosion_subtypes}
    cands = screen(model, a.scope, thr)
    if a.max is not None:
        cands = cands[:max(0, a.max)]
    json.dump({"candidates": cands, "thresholds": thr}, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
