#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Blast radius: what depends on the changed symbols (model edges plus grep).

Usage: cd_blast.py --model PATH --root DIR (--symbol ID ... | --file PATH ... | --name NAME ...)
                   [--max-files N] [--max-hits N]
Prints JSON {model, grep, unverified, scope, checklist} to stdout. Exit 0 on success, 2 usage/IO.
`checklist` greps files of languages without a grammar (model coverage.unavailable) for
language-agnostic risk idioms; `--name` greps a bare name with no model symbol needed.

The structure model has no call or import edges, so model dependents are limited to
parent, children, overloads and subtypes/implementers; grep over the files the model
covers carries most of the weight. Uncertain results go to `unverified` with a reason.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402,F401  (shared walk rules and limits)

TYPE_KINDS = ("class", "interface", "struct", "trait", "enum", "type", "record", "protocol")
DYNAMIC = ("getattr(", "reflect.", "__import__", "setattr(", "importlib", "Class.forName")
NO_EDGES = "no call/import edges in model"
MAX_LINE = 400
CAT_CAP, TOTAL_CAP = 15, 60
# Simple alternations only (no nested quantifiers) so scanning stays linear.
CHECKLIST = [
    ("resource-lookup", re.compile(
        r"Bundle\.(main|module|allBundles)|forResource:|NSBundle|getResource(AsStream)?\(|"
        r"AssetManager|assets\.open|Resources\.Load|include_(str|bytes)!|importlib\.resources|"
        r"__dirname|__FILE__")),
    ("hard-coded-resource-name", re.compile(
        r"[\"'][\w./-]+\.(json|xml|plist|sqlite3?|db|csv|ya?ml|png|jpg|xcstrings|strings|ttf|bin|pack)[\"']")),
    ("string-key", re.compile(
        r"(forKey|forName|getenv|environ|process\.env|UserDefaults|SharedPreferences|localStorage|"
        r"sessionStorage)\b[^\"']*[\"'][^\"']+[\"']|\[\s*[\"'][A-Za-z_][\w.-]*[\"']\s*\]")),
    ("default-fallback", re.compile(
        r"\?\?\s|\?:\s|\|\|\s*[\"'\w]|getOrDefault|orElse\(|unwrap_or|value_or|"
        r"\b(fallback|defaultValue|DEFAULT_[A-Z_]+)\b")),
    ("single-instance-accessor", re.compile(
        r"\.(shared|default|current|bundled|main|instance|standard|singleton)\b(\(\))?")),
]


def _read_lines(root, rel, cache):
    """Return lines of a file under root, or None if missing or escaping root."""
    if rel in cache:
        return cache[rel]
    lines = None
    full = os.path.realpath(os.path.join(root, rel))
    if (full == root or full.startswith(root + os.sep)) and os.path.isfile(full):
        try:
            if os.path.getsize(full) <= cd_common.MAX_BYTES:
                with open(full, "rb") as fh:
                    text = fh.read().decode("utf-8", errors="replace")
                lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        except OSError:
            lines = None
    cache[rel] = lines
    return lines


def _quote(root, rel, line, cache):
    lines = _read_lines(root, rel, cache)
    if lines is None or not (1 <= line <= len(lines)):
        return None
    return lines[line - 1].strip()


def checklist(root, files, cache, add_unv):
    """Grep no-grammar files for risk idioms; capped per category and in total."""
    out, per = [], {}
    dropped = 0
    for rel in files:
        lines = _read_lines(root, rel, cache)
        if lines is None:
            continue
        for n, text in enumerate(lines, 1):
            if len(text) > MAX_LINE:
                continue
            for cat, rx in CHECKLIST:
                if not rx.search(text):
                    continue
                if per.get(cat, 0) >= CAT_CAP or len(out) >= TOTAL_CAP:
                    dropped += 1
                    continue
                per[cat] = per.get(cat, 0) + 1
                out.append({"file": rel, "line": n, "category": cat, "via": "checklist:" + cat,
                            "tag": "grep", "quote": text.strip()})
    if dropped:
        add_unv("truncated", detail="%d more checklist hits not listed (cap %d per category, %d total)"
                % (dropped, CAT_CAP, TOTAL_CAP))
    out.sort(key=lambda d: (d["category"], d["file"], d["line"]))
    return out


def blast(model, root, targets, max_files, max_hits, names=()):
    symbols = model.get("symbols", [])
    by_id = {s["id"]: s for s in symbols}
    cov = model.get("coverage") or {}
    cfiles = cov.get("files")
    if not isinstance(cfiles, list):
        cfiles = [{"path": f, "language": "unknown", "parsed": True, "hasErrors": False}
                  for f in sorted({s["file"] for s in symbols})]
    cache = {}
    model_deps, grep_deps, unverified = {}, {}, []
    unav_files = []
    for u in cov.get("unavailable") or []:
        if isinstance(u.get("files"), list):
            unav_files += [x for x in u["files"] if isinstance(x, str)]

    def add_model(sym, via):
        line = sym["span"]["startLine"]
        q = _quote(root, sym["file"], line, cache)
        if q is None:
            return
        model_deps.setdefault((sym["file"], line, sym["id"]), {
            "file": sym["file"], "line": line, "symbol": sym["id"], "via": via,
            "tag": "model", "quote": q})

    def add_unv(reason, **kw):
        e = {"reason": reason, **kw}
        if e not in unverified:
            unverified.append(e)

    def grep_name(name, sid, sym):
        """Word-boundary grep of name over covered and unavailable files."""
        if len(name) < 4:
            add_unv("common-name", symbol=sid, detail="name shorter than 4 characters; grep skipped")
            return
        rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")
        hits, files = [], set()
        paths = [f.get("path") for f in cfiles] + unav_files
        for rel in dict.fromkeys(paths):
            if not isinstance(rel, str):
                continue
            lines = _read_lines(root, rel, cache)
            if lines is None:
                continue
            for n, text in enumerate(lines, 1):
                if not rx.search(text):
                    continue
                if (sym and rel == sym["file"]
                        and sym["span"]["startLine"] <= n <= sym["span"]["endLine"]):
                    continue
                hits.append((rel, n, text.strip()))
                files.add(rel)
        if len(files) > max_files:
            add_unv("common-name", symbol=sid, detail="%d files match; grep results suppressed" % len(files))
            return
        for k, (rel, n, q) in enumerate(hits):
            if k >= max_hits:
                add_unv("truncated", symbol=sid, detail="%d more hits not listed" % (len(hits) - max_hits))
                break
            if any(d in q for d in DYNAMIC):
                add_unv("dynamic-dispatch", file=rel, line=n, symbol=sid, quote=q)
                continue
            grep_deps.setdefault((rel, n), {"file": rel, "line": n, "via": "grep:" + name,
                                            "tag": "grep", "quote": q})

    changed = [by_id[t] for t in targets if t in by_id]
    for sym in changed:
        sid, name = sym["id"], sym["name"]
        par = by_id.get(sym.get("parent"))
        if par:
            add_model(par, "parent")
        for c in symbols:
            if c.get("parent") == sid:
                add_model(c, "children")
            elif (c["id"] != sid and c["file"] == sym["file"] and c["name"] == name
                  and c.get("parent") == sym.get("parent") and c["kind"] == sym["kind"]):
                add_model(c, "overload")
        if sym["kind"] in TYPE_KINDS:
            same = [s for s in symbols if s["name"] == name and s["kind"] in TYPE_KINDS]
            for c in symbols:
                for st in c.get("supertypes") or []:
                    if st.get("name") != name:
                        continue
                    if len(same) > 1:
                        add_unv("ambiguous-name", file=c["file"], line=c["span"]["startLine"],
                                symbol=c["id"], detail="supertype name %s matches %d types" % (name, len(same)))
                    else:
                        add_model(c, st.get("relation", "extends"))
        grep_name(name, sid, sym)

    for nm in names:
        grep_name(nm, nm, None)

    # go methods whose receiver type was not resolved
    deps_syms = [by_id[k[2]] for k in model_deps if k[2] in by_id]
    for s in changed + deps_syms:
        if s["file"].endswith(".go") and s["kind"] == "method" and s.get("parent") is None:
            add_unv("go-unparented-method", file=s["file"], line=s["span"]["startLine"], symbol=s["id"])

    for u in cov.get("unavailable") or []:
        add_unv("unavailable-language", language=u.get("language"),
                detail="%s files not parsed; dependents there are unknown"
                % (len(u["files"]) if isinstance(u.get("files"), list) else u.get("files", "?")))
    for f in cfiles:
        if f.get("hasErrors"):
            add_unv("parse-errors", file=f.get("path"), detail="tree-sitter reported errors; symbols may be missing")

    mdeps = sorted(model_deps.values(), key=lambda d: (d["file"], d["line"]))
    taken = {(d["file"], d["line"]) for d in mdeps}
    gdeps = sorted((d for k, d in grep_deps.items() if k not in taken), key=lambda d: (d["file"], d["line"]))
    langs = sorted({f.get("language") for f in cfiles if f.get("parsed", True) and f.get("language")})
    unverified.sort(key=lambda u: (u["reason"], u.get("file") or "", u.get("line") or 0, u.get("symbol") or ""))
    scope = {"files": len(cfiles), "languages": langs, "note": NO_EDGES,
             "description": "grep over %d model-covered files (%s); %s" % (len(cfiles), ", ".join(langs), NO_EDGES)}
    cl = checklist(root, list(dict.fromkeys(unav_files)), cache, add_unv) if unav_files else []
    unverified.sort(key=lambda u: (u["reason"], u.get("file") or "", u.get("line") or 0, u.get("symbol") or ""))
    return {"model": mdeps, "grep": gdeps, "unverified": unverified, "scope": scope, "checklist": cl}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Blast radius of changed symbols")
    ap.add_argument("--model", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--symbol", action="append", default=[])
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--max-files", type=int, default=8)
    ap.add_argument("--max-hits", type=int, default=50)
    try:
        args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as ex:
        return 2 if ex.code else 0
    root = os.path.realpath(args.root)
    try:
        with open(args.model, encoding="utf-8") as fh:
            model = json.load(fh)
        model["symbols"]
    except (OSError, ValueError, KeyError, TypeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    if (not os.path.isdir(root) or not (args.symbol or args.file or args.name)
            or args.max_files < 1 or args.max_hits < 1):
        print("error: need a root directory and --symbol, --file or --name", file=sys.stderr)
        return 2
    ids = {s["id"] for s in model["symbols"]}
    targets = list(args.symbol)
    for f in args.file:
        targets += [s["id"] for s in model["symbols"] if s["file"] == f]
    unknown = [t for t in args.symbol if t not in ids]
    if unknown:
        print("error: unknown symbol: %s" % ", ".join(unknown), file=sys.stderr)
        return 2
    print(json.dumps(blast(model, root, targets, args.max_files, args.max_hits, args.name), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
