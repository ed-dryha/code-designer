#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["tree-sitter-language-pack==1.22.1", "tree-sitter>=0.23,<0.27"]
# ///
"""Extract a versioned structure model (schemaVersion 1) using tree-sitter.

Exit codes: 0 complete, 2 usage/IO error, 3 grammars unavailable (JSON still written).
"""
import argparse
import datetime
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402
from cd_common import IGNORE_DIRS, MAX_BYTES  # noqa: E402
from languages import language_for  # noqa: E402

GENERATOR_VERSION = "0.1.0"
PACK_VERSION = "1.22.1"
HERE = os.path.dirname(os.path.abspath(__file__))
TYPE_SKIP = {"name", "supers"}
VISIBILITY = ("public", "protected", "private", "internal", "package")


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Extract structure model")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--cache-dir")
    ap.add_argument("--allow-download", action="store_true")
    ap.add_argument("--out")
    return ap.parse_args(argv)


def walk_files(root):
    files, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        keep = []
        for d in sorted(dirnames):
            if d in IGNORE_DIRS:
                skipped.append({"path": os.path.relpath(os.path.join(dirpath, d), root), "reason": "ignored"})
            else:
                keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            lang = language_for(f)
            if lang is None:
                continue
            real = os.path.realpath(full)
            if real != root and not real.startswith(root + os.sep):
                skipped.append({"path": rel, "reason": "symlink-outside-root"})
                continue
            if os.path.getsize(full) > MAX_BYTES:
                skipped.append({"path": rel, "reason": "too-large"})
                continue
            files.append((rel, full, lang))
    return files, skipped


def load_queries(lang):
    p = os.path.join(HERE, "queries", lang + ".scm")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def load_hook(lang):
    if not os.path.isfile(os.path.join(HERE, "lang_hooks", lang + ".py")):
        return None
    return importlib.import_module("lang_hooks." + lang)


def node_text(node):
    return node.text.decode("utf-8", errors="replace")


def has_errors(root):
    return bool(root.has_error)


def collect(matches):
    """Adapt query matches to raw symbol dicts per the capture contract."""
    out, seen = [], set()
    for _idx, caps in matches:
        for key, nodes in caps.items():
            if key.startswith("type.") and key.split(".", 1)[1] not in TYPE_SKIP:
                kind, name_key = key.split(".", 1)[1], "type.name"
            elif key in ("method", "constructor", "function", "field"):
                kind, name_key = key, key + ".name"
            else:
                continue
            node = nodes[0]
            if name_key not in caps or (kind, node.start_byte, node.end_byte) in seen:
                continue
            seen.add((kind, node.start_byte, node.end_byte))
            sym = {"kind": kind, "name": node_text(caps[name_key][0]), "node": node}
            if "type.supers" in caps and key.startswith("type."):
                sym["supers"] = [node_text(c) for c in caps["type.supers"][0].named_children]
            if "field.type" in caps and key == "field":
                sym["typeText"] = node_text(caps["field.type"][0])
            if "modifiers" in caps:
                sym["modifiers"] = node_text(caps["modifiers"][0])
            out.append(sym)
    return out


def signature_of(node):
    text = node.text.decode("utf-8", errors="replace")
    body = node.child_by_field_name("body")
    if body is not None and body.start_byte > node.start_byte:
        head = node.text[: body.start_byte - node.start_byte].decode("utf-8", errors="replace")
    else:
        head = text.split("\n", 1)[0]
    return " ".join(head.split()).rstrip(":{ ").strip() or None


def params_of(sig):
    if sig and "(" in sig and ")" in sig:
        return "".join(sig[sig.index("(") + 1: sig.rindex(")")].split())
    return ""


TYPE_KINDS = {"class", "interface", "enum", "struct", "trait", "record", "object"}


def build_symbols(raw, relpath, source):
    raw.sort(key=lambda s: (s["node"].start_byte, -s["node"].end_byte))
    types = [s for s in raw if s["kind"] in TYPE_KINDS]
    for s in raw:
        best = None
        for t in types:
            if t is s:
                continue
            if t["node"].start_byte <= s["node"].start_byte and s["node"].end_byte <= t["node"].end_byte \
                    and (t["node"].start_byte, t["node"].end_byte) != (s["node"].start_byte, s["node"].end_byte):
                if best is None or t["node"].start_byte >= best["node"].start_byte:
                    best = t
        if s.get("parent_override") is not None:  # hook-supplied parent (e.g. Go receiver methods)
            best = s["parent_override"]
        s["_parent"] = best

    def qual_of(s):
        if "_qual" not in s:
            p = s["_parent"]
            s["_qual"] = (qual_of(p) + "." if p else "") + s["name"]
        return s["_qual"]

    for s in raw:
        qual_of(s)
    # overload / collision disambiguation
    groups = {}
    for s in raw:
        groups.setdefault(s["_qual"], []).append(s)
    for qual, grp in groups.items():
        if len(grp) == 1:
            s = grp[0]
            s["_id"] = f"{relpath}#{qual}"
            continue
        used = {}
        for s in grp:
            sig = signature_of(s["node"])
            cand = f"{relpath}#{qual}({params_of(sig)})" if s["kind"] in ("method", "constructor", "function") else f"{relpath}#{qual}"
            n = used.get(cand, 0) + 1
            used[cand] = n
            s["_id"] = cand if n == 1 else f"{cand}~{n}"
    symbols = []
    for s in raw:
        node = s["node"]
        mods = (s.get("modifiers") or "").split()
        vis = next((m for m in mods if m in VISIBILITY), None)
        sym = {
            "id": s["_id"],
            "kind": s["kind"],
            "name": s["name"],
            "parent": s["_parent"]["_id"] if s["_parent"] else None,
            "file": relpath,
            "span": {"startLine": node.start_point[0] + 1, "endLine": node.end_point[0] + 1},
            "signature": signature_of(node),
            "visibility": vis,
            "static": "static" in mods,
            "supertypes": [{"relation": "extends", "name": n} for n in s.get("supers", [])],
            "typeText": s.get("typeText"),
            "provenance": "tree-sitter",
            "inferred": False,
            "hash": cd_common.symbol_hash(node_text(node)),
        }
        if s.get("heuristic"):
            sym["heuristic"] = True
        symbols.append(sym)
    return symbols


def extract_file(parser, language, queries, hook, source, relpath):
    from tree_sitter import Query, QueryCursor
    tree = parser.parse(source)
    root = tree.root_node
    raw = collect(QueryCursor(Query(language, queries)).matches(root))
    if hook is not None:
        hook.post_process(raw, root, source)
    return build_symbols(raw, relpath, source), has_errors(root)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    cache = args.cache_dir or os.environ.get("CODE_DESIGNER_CACHE")
    if not cache:
        print("error: --cache-dir or CODE_DESIGNER_CACHE required", file=sys.stderr)
        return 2
    root = os.path.realpath(args.path)
    if not os.path.isdir(root):
        print(f"error: not a directory: {args.path}", file=sys.stderr)
        return 2

    from cd_pack import open_pack, GrammarUnavailable
    pack = open_pack(os.path.abspath(cache), args.allow_download)

    files, skipped = walk_files(root)
    by_lang = {}
    for rel, full, lang in files:
        by_lang.setdefault(lang, []).append((rel, full))

    cov_files, symbols, unavailable = [], [], []
    for lang in sorted(by_lang):
        queries = load_queries(lang)
        try:
            if queries is None:
                raise GrammarUnavailable(lang, "no-grammar", "no queries for language")
            parser, language = pack.load(lang)
        except GrammarUnavailable as e:
            unavailable.append({"language": lang, "files": sorted(r for r, _ in by_lang[lang]), "reason": e.reason})
            continue
        hook = load_hook(lang)
        for rel, full in sorted(by_lang[lang]):
            try:
                with open(full, "rb") as fh:
                    source = fh.read()
            except OSError as e:
                print(f"error: cannot read {rel}: {e}", file=sys.stderr)
                return 2
            syms, errs = extract_file(parser, language, queries, hook, source, rel)
            symbols.extend(syms)
            cov_files.append({"path": rel, "language": lang, "parsed": True, "symbols": len(syms),
                              "hasErrors": errs, "sha256": cd_common.file_sha256(source),
                              "provenance": "tree-sitter"})

    symbols.sort(key=lambda s: (s["file"], s["span"]["startLine"], s["id"]))
    cov_files.sort(key=lambda f: f["path"])
    skipped.sort(key=lambda s: s["path"])
    if unavailable:
        status = "partial" if cov_files else "unavailable"
    else:
        status = "complete"
    model = {
        "schemaVersion": 1,
        "generator": {"name": "cd-extract", "version": GENERATOR_VERSION, "pack": PACK_VERSION,
                      "source": "tree-sitter"},
        "root": ".",
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "coverage": {"files": cov_files, "unavailable": unavailable, "skipped": skipped},
        "symbols": symbols,
    }
    text = json.dumps(model, indent=2, sort_keys=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 3 if unavailable else 0


if __name__ == "__main__":
    sys.exit(main())
