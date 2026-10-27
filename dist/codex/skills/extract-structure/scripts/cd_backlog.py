#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Stable-ID refactor backlog: id, merge, lint, touching.

docs/design/backlog.md is a stream of `---` delimited YAML documents: a header
(`schema: 1`) followed by one document per finding. IDs are produced only here.
Exit codes: 0 ok, 1 findings rejected / lint problems, 2 usage or confinement.
"""
import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_verify  # noqa: E402

PRIORITIES = ("High", "Medium", "Low")
STATUSES = ("open", "resolved")
HEADER = {"schema": 1, "kind": "code-designer-backlog"}
KEYS = ("id", "smell", "principle", "symbol", "evidence", "impact", "suggestion",
        "priority", "rationale", "status", "firstSeen", "lastSeen", "resolvedOn", "notes")
TOP_COMMENT = ("# Code Designer refactor backlog. Human-editable: change priority, rationale and\n"
               "# notes freely; re-runs keep your edits. IDs are script-generated, do not edit.\n")


def _digest(smell, symbol, n=6):
    return hashlib.sha1(f"{smell}|{symbol}".encode("utf-8")).hexdigest()[:n]


def finding_id(smell, symbol, n=6):
    base = smell[len("smell-"):] if smell.startswith("smell-") else smell
    return f"F-{base}-{_digest(smell, symbol, n)}"


class _Dumper(yaml.SafeDumper):
    pass


def _str_rep(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_rep)


def _dump(doc):
    return yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000)


def _order(f):
    return (0 if f.get("status") == "open" else 1,
            PRIORITIES.index(f["priority"]) if f.get("priority") in PRIORITIES else 9,
            f.get("id", ""))


def render(findings):
    out = [TOP_COMMENT]
    out.append("---\n" + _dump(HEADER))
    for f in sorted(findings, key=_order):
        ordered = {k: f[k] for k in KEYS if k in f}
        for k in f:
            if k not in ordered:
                ordered[k] = f[k]
        out.append(f"---\n# {f['id']}\n" + _dump(ordered))
    return "".join(out)


def load(path):
    with open(path, encoding="utf-8") as fh:
        docs = [d for d in yaml.safe_load_all(fh) if d is not None]
    return docs


def _one_line(v):
    return isinstance(v, str) and v.strip() != "" and "\n" not in v.strip()


def _file_of(symbol):
    return symbol.split("#", 1)[0] if isinstance(symbol, str) else ""


def cmd_id(a):
    print(finding_id(a.smell, a.symbol))
    return 0


def cmd_merge(a):
    root = os.path.realpath(a.root)
    design = os.path.realpath(os.path.join(root, "docs", "design"))
    target = a.backlog or os.path.join(design, "backlog.md")
    if not os.path.isabs(target):
        target = os.path.join(root, target)
    target = os.path.realpath(target)
    if not target.startswith(design + os.sep):
        print("error: --backlog must be inside <root>/docs/design/", file=sys.stderr)
        return 2
    try:
        with open(a.findings, encoding="utf-8") as fh:
            incoming = json.load(fh)
        with open(a.model, encoding="utf-8") as fh:
            symbols = {x["id"]: x for x in json.load(fh)["symbols"]}
    except (OSError, ValueError, KeyError, TypeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    if not isinstance(incoming, list) or not os.path.isdir(root):
        print("error: findings must be a JSON list and root a directory", file=sys.stderr)
        return 2
    date = a.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    rejected = []
    for f in incoming:
        problems = []
        if not isinstance(f, dict):
            rejected.append({"finding": f, "problems": ["not-an-object"]})
            continue
        if "id" in f:
            problems.append("id-not-allowed")
        if f.get("priority") not in PRIORITIES:
            problems.append("bad-priority")
        if not _one_line(f.get("rationale")):
            problems.append("bad-rationale")
        if not f.get("smell") or not f.get("symbol"):
            problems.append("missing-smell-or-symbol")
        ev = f.get("evidence")
        if not isinstance(ev, list) or not ev:
            problems.append("no-evidence")
            ev = []
        statuses = []
        for c in ev:
            if isinstance(c, dict):
                st, _ = cd_verify.check(root, c, symbols)
            else:
                st = "out-of-range"
            if st != "pass":
                statuses.append({"citation": c, "status": st})
        if problems or statuses:
            rejected.append({"smell": f.get("smell"), "symbol": f.get("symbol"),
                             "problems": problems, "evidence": statuses})
    if rejected:
        print(json.dumps({"rejected": rejected}, indent=2))
        print(f"{len(rejected)} finding(s) rejected; nothing written", file=sys.stderr)
        return 1

    existing = {}
    if os.path.isfile(target):
        try:
            for d in load(target)[1:]:
                existing[d["id"]] = d
        except (yaml.YAMLError, KeyError, TypeError) as ex:
            print(f"error: unreadable backlog: {ex}", file=sys.stderr)
            return 2

    # ids, with collision extension for different (smell, symbol) pairs
    pairs = {}
    new_ids = []
    for f in incoming:
        fid = finding_id(f["smell"], f["symbol"])
        key = (f["smell"], f["symbol"])
        if fid in pairs and pairs[fid] != key:
            fid = finding_id(f["smell"], f["symbol"], 8)
            print(f"note: id collision extended to {fid}", file=sys.stderr)
        pairs[fid] = key
        new_ids.append((fid, f))

    counts = {"added": [], "updated": [], "resolved": [], "reopened": [], "untouched": []}
    seen = set()
    for fid, f in new_ids:
        seen.add(fid)
        cur = existing.get(fid)
        if cur is None:
            existing[fid] = {
                "id": fid, "smell": f["smell"], "principle": f.get("principle"),
                "symbol": f["symbol"], "evidence": f["evidence"],
                "impact": f.get("impact", ""), "suggestion": f.get("suggestion", ""),
                "priority": f["priority"], "rationale": f["rationale"].strip(),
                "status": "open", "firstSeen": date, "lastSeen": date,
            }
            counts["added"].append(fid)
            continue
        cur.update(principle=f.get("principle", cur.get("principle")), evidence=f["evidence"],
                   impact=f.get("impact", ""), suggestion=f.get("suggestion", ""), lastSeen=date)
        if cur.get("status") == "resolved":
            cur["status"] = "open"
            cur.pop("resolvedOn", None)
            counts["reopened"].append(fid)
        else:
            counts["updated"].append(fid)

    scopes = a.scope or ["**"]
    for fid, cur in existing.items():
        if fid in seen:
            continue
        in_scope = any(fnmatch.fnmatchcase(_file_of(cur.get("symbol")), s) for s in scopes)
        if cur.get("status") == "open" and in_scope:
            cur["status"] = "resolved"
            cur["resolvedOn"] = date
            counts["resolved"].append(fid)
        else:
            counts["untouched"].append(fid)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(list(existing.values())))
    os.replace(tmp, target)
    print(json.dumps({k: sorted(v) for k, v in counts.items()}, indent=2))
    print(f"backlog: {len(existing)} finding(s)", file=sys.stderr)
    return 0


def cmd_lint(a):
    try:
        docs = load(a.path)
    except (OSError, yaml.YAMLError) as ex:
        print(json.dumps([{"id": None, "problem": f"unreadable: {ex}"}]))
        return 1
    probs = []
    if not docs or not isinstance(docs[0], dict) or docs[0].get("schema") != 1:
        probs.append({"id": None, "problem": "missing header with schema: 1"})
    seen = set()
    for d in docs[1:]:
        if not isinstance(d, dict):
            probs.append({"id": None, "problem": "finding is not a mapping"})
            continue
        fid = d.get("id")
        if fid in seen:
            probs.append({"id": fid, "problem": "duplicate id"})
        seen.add(fid)
        smell, sym = d.get("smell"), d.get("symbol")
        if not (isinstance(smell, str) and isinstance(sym, str)):
            probs.append({"id": fid, "problem": "smell and symbol must be strings"})
        elif fid not in (finding_id(smell, sym), finding_id(smell, sym, 8)):
            probs.append({"id": fid, "problem": "id does not match smell|symbol"})
        if d.get("priority") not in PRIORITIES:
            probs.append({"id": fid, "problem": f"priority must be High|Medium|Low, got {d.get('priority')!r}"})
        if not _one_line(d.get("rationale")):
            probs.append({"id": fid, "problem": "rationale must be one non-empty line"})
        if d.get("status") not in STATUSES:
            probs.append({"id": fid, "problem": "status must be open|resolved"})
    print(json.dumps(probs, indent=2))
    print(f"{len(probs)} problem(s)", file=sys.stderr)
    return 1 if probs else 0


def touching(docs, syms, files):
    """Open findings whose symbol is in syms or whose evidence/symbol file is in files."""
    syms, files = set(syms or []), set(files or [])
    out = []
    for d in docs[1:]:
        if not isinstance(d, dict) or d.get("status") != "open":
            continue
        efiles = sorted({c.get("file") for c in d.get("evidence") or [] if isinstance(c, dict) and c.get("file")})
        if d.get("symbol") in syms or files & (set(efiles) | {_file_of(d.get("symbol"))}):
            out.append({"id": d["id"], "symbol": d.get("symbol"), "priority": d.get("priority"),
                        "rationale": d.get("rationale"), "files": efiles})
    return out


def cmd_touching(a):
    try:
        docs = load(a.backlog)
    except (OSError, yaml.YAMLError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    print(json.dumps(touching(docs, a.symbols, a.files), indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Refactor backlog tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("id")
    p.add_argument("--smell", required=True)
    p.add_argument("--symbol", required=True)
    p = sub.add_parser("merge")
    p.add_argument("--root", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--findings", required=True)
    p.add_argument("--backlog")
    p.add_argument("--scope", action="append")
    p.add_argument("--date")
    p = sub.add_parser("lint")
    p.add_argument("path")
    p = sub.add_parser("touching")
    p.add_argument("--backlog", required=True)
    p.add_argument("--symbols", nargs="*")
    p.add_argument("--files", nargs="*")
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2
    return {"id": cmd_id, "merge": cmd_merge, "lint": cmd_lint, "touching": cmd_touching}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
