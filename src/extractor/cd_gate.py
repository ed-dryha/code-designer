#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Hard evidence gate over a design doc (decision records).

Usage: cd_gate.py <doc.md> --root DIR --model PATH [--kb DIR] [--tolerance N]
Exit codes: 0 all pass, 1 any fail, 2 usage/IO. Prints a JSON array of
{record, check, status[, detail]} to stdout and "N/M checks pass" to stderr.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402

import cd_verify  # noqa: E402

MAX_DOC_BYTES = 1024 * 1024
REQUIRED = ("id", "decision", "evidence", "candidate", "alternatives", "verdict", "reason", "change_safety")
VERDICTS = ("adopt", "reject", "no-pattern")
HEADING = re.compile(r"^###\s+(DR-\S+)")
FENCE_OPEN = re.compile(r"^```\s*ya?ml\s*$")


def extract_records(text):
    """Return list of (heading_id, yaml_text, yaml_start_line)."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        m = HEADING.match(lines[i])
        if not m:
            i += 1
            continue
        hid = m.group(1)
        j = i + 1
        block = None
        while j < len(lines) and not HEADING.match(lines[j]):
            if FENCE_OPEN.match(lines[j]):
                k = j + 1
                body = []
                while k < len(lines) and not lines[k].startswith("```"):
                    body.append(lines[k])
                    k += 1
                block = ("\n".join(body), j + 2)
                break
            j += 1
        out.append((hid, block))
        i = j + 1 if block else j
    return out


def load_kb(kb):
    """Map KB id -> frontmatter dict."""
    ids = {}
    if not kb or not os.path.isdir(kb):
        return ids
    for dp, _dn, fns in os.walk(kb):
        for fn in sorted(fns):
            if not fn.endswith(".md"):
                continue
            try:
                with open(os.path.join(dp, fn), encoding="utf-8") as fh:
                    txt = fh.read()
            except OSError:
                continue
            if not txt.startswith("---"):
                continue
            end = txt.find("\n---", 3)
            if end < 0:
                continue
            try:
                fm = yaml.safe_load(txt[3:end])
            except yaml.YAMLError:
                continue
            if isinstance(fm, dict) and isinstance(fm.get("id"), str):
                ids[fm["id"]] = fm
    return ids


def gate_record(rid, rec, root, symbols, kb, tolerance):
    res = []

    def add(check, status, **extra):
        res.append({"record": rid, "check": check, "status": status, **extra})

    missing = [f for f in REQUIRED if f not in rec]
    if missing:
        add("fields", "missing-field", detail=missing)
        return res
    add("fields", "pass")

    verdict = rec["verdict"]
    add("verdict", "pass" if verdict in VERDICTS else "bad-verdict")
    reason = rec["reason"]
    add("reason", "pass" if isinstance(reason, str) and reason.strip() else "empty-reason")

    alts = rec["alternatives"]
    has_dn = isinstance(alts, list) and any(isinstance(a, dict) and a.get("option") == "do-nothing" for a in alts)
    add("do-nothing", "pass" if has_dn else "no-do-nothing")

    ev = rec["evidence"]
    cites = [e for e in ev if isinstance(e, dict) and e.get("file")] if isinstance(ev, list) else []
    add("evidence", "pass" if cites else "no-evidence")
    cited_syms = []
    for n, c in enumerate(cites):
        st, extra = cd_verify.check(root, c, symbols, tolerance)
        add("citation-%d" % (n + 1), st, **extra)
        if st == "pass" and c.get("symbol"):
            cited_syms.append(symbols.get(c["symbol"]))
        elif st == "pass":
            # symbol-less citation: match any model symbol whose span contains it
            for s in symbols.values():
                sp = s.get("span", {})
                if (s.get("file") == c.get("file") and isinstance(c.get("startLine"), int)
                        and sp.get("startLine", 0) <= c["startLine"] and c.get("endLine", 0) <= sp.get("endLine", -1)):
                    cited_syms.append(s)

    if verdict == "adopt" and rec["candidate"] not in (None, "none"):
        cand = rec["candidate"]
        meta = kb.get(cand)
        if meta is None:
            add("candidate", "unknown-kb-id", detail=cand)
        else:
            add("candidate", "pass")
            smell = rec.get("smell")
            vp = rec.get("variation_point")
            if not smell and not (isinstance(vp, str) and vp.strip()):
                add("justification", "no-smell-or-variation-point")
            elif smell:
                if smell not in kb:
                    add("smell", "unknown-kb-id", detail=smell)
                elif smell not in ((meta.get("links") or {}).get("smells") or []):
                    add("smell", "smell-not-linked", detail=smell)
                else:
                    add("smell", "pass")
            else:
                add("justification", "pass")
            ts = any(s and s.get("provenance") == "tree-sitter" for s in cited_syms)
            add("tree-sitter-evidence", "pass" if ts else "no-tree-sitter-evidence")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Evidence gate for design docs")
    ap.add_argument("doc")
    ap.add_argument("--root", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--kb")
    ap.add_argument("--tolerance", type=int, default=0)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    root = os.path.realpath(args.root)
    try:
        if os.path.getsize(args.doc) > MAX_DOC_BYTES:
            print("error: doc larger than 1 MB", file=sys.stderr)
            return 2
        with open(args.doc, encoding="utf-8") as fh:
            text = fh.read()
        with open(args.model, encoding="utf-8") as fh:
            symbols = {x["id"]: x for x in json.load(fh)["symbols"]}
    except (OSError, ValueError, KeyError, TypeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    if not os.path.isdir(root) or args.tolerance < 0:
        print("error: root must be a directory, tolerance >= 0", file=sys.stderr)
        return 2
    kb = load_kb(args.kb)

    results = []
    records = extract_records(text)
    if not records:
        results.append({"record": None, "check": "records", "status": "no-records"})
    for hid, block in records:
        if block is None:
            results.append({"record": hid, "check": "yaml", "status": "yaml-error", "detail": "no yaml block"})
            continue
        body, start = block
        try:
            rec = yaml.safe_load(body)
        except yaml.YAMLError as ex:
            mark = getattr(ex, "problem_mark", None)
            line = start + (mark.line if mark else 0)
            results.append({"record": hid, "check": "yaml", "status": "yaml-error", "line": line,
                            "detail": str(getattr(ex, "problem", ex))})
            continue
        if not isinstance(rec, dict):
            results.append({"record": hid, "check": "yaml", "status": "yaml-error", "line": start,
                            "detail": "record is not a mapping"})
            continue
        results.extend(gate_record(rec.get("id", hid), rec, root, symbols, kb, args.tolerance))

    print(json.dumps(results, indent=2))
    bad = sum(1 for r in results if r["status"] != "pass")
    print(f"{len(results) - bad}/{len(results)} checks pass", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
