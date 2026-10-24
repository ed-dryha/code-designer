#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Verify citations {file, startLine, endLine, quote?, symbol?} against real files.

Exit codes: 0 all pass, 1 any fail, 2 usage. Prints a JSON array of
{citation, status[, actual]} to stdout and a summary line to stderr.
Statuses: pass, missing-file, out-of-range, quote-mismatch, drifted, stale,
unknown-symbol, path-escape. Agent-provenance symbols get identical checks.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402


def _read_lines(full):
    with open(full, "rb") as fh:
        text = fh.read().decode("utf-8", errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _find_quote(lines, quote):
    """Return 1-based start lines of every window of the file containing the quote."""
    nq = cd_common.normalize_lines(quote).strip("\n")
    k = max(1, nq.count("\n") + 1)
    norm = [cd_common.normalize_lines(ln) for ln in lines]
    hits = []
    for i in range(0, len(norm) - k + 1):
        if nq in "\n".join(norm[i:i + k]):
            hits.append(i + 1)
    return hits, k


def check(root, c, symbols=None, tolerance=0):
    """Return (status, extra-dict)."""
    f = c.get("file")
    s, e = c.get("startLine"), c.get("endLine")
    if (not isinstance(f, str) or not f or os.path.isabs(f) or "\x00" in f
            or ".." in f.replace("\\", "/").split("/")):
        return "path-escape", {}
    full = os.path.realpath(os.path.join(root, f))
    if full != root and not full.startswith(root + os.sep):
        return "path-escape", {}
    if not os.path.isfile(full):
        return "missing-file", {}
    lines = _read_lines(full)
    if not (isinstance(s, int) and isinstance(e, int)) or not (1 <= s <= e <= len(lines)):
        return "out-of-range", {}
    sym_id = c.get("symbol")
    if sym_id:
        sym = (symbols or {}).get(sym_id)
        if sym is None or sym.get("file") != f:
            return "unknown-symbol", {}
        ss, se = sym["span"]["startLine"], sym["span"]["endLine"]
        if not (ss <= s and e <= se):
            return "out-of-range", {"symbolSpan": [ss, se]}
        h = sym.get("hash")
        if h is not None and (se > len(lines) or cd_common.symbol_hash("\n".join(lines[ss - 1:se])) != h):
            return "stale", {}
    quote = c.get("quote")
    if quote:
        region = cd_common.normalize_lines("\n".join(lines[s - 1:e]))
        if cd_common.normalize_lines(quote).strip("\n") in region:
            return "pass", {}
        hits, k = _find_quote(lines, quote)
        if not hits:
            return "quote-mismatch", {}
        best = min(hits, key=lambda h: abs(h - s))
        if abs(best - s) <= tolerance:
            return "pass", {}
        return "drifted", {"actual": [best, best + k - 1]}
    return "pass", {}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify citations")
    ap.add_argument("--root", required=True)
    ap.add_argument("--citations", required=True)
    ap.add_argument("--model")
    ap.add_argument("--tolerance", type=int, default=0, help="accept quotes drifted by up to N lines")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    root = os.path.realpath(args.root)
    symbols = {}
    try:
        with open(args.citations, encoding="utf-8") as fh:
            cits = json.load(fh)
        if args.model:
            with open(args.model, encoding="utf-8") as fh:
                symbols = {x["id"]: x for x in json.load(fh)["symbols"]}
    except (OSError, ValueError, KeyError, TypeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    if not isinstance(cits, list) or not os.path.isdir(root) or args.tolerance < 0:
        print("error: citations must be a JSON list, root a directory, tolerance >= 0", file=sys.stderr)
        return 2
    results = []
    for c in cits:
        if isinstance(c, dict):
            st, extra = check(root, c, symbols, args.tolerance)
        else:
            st, extra = "out-of-range", {}
        results.append({"citation": c, "status": st, **extra})
    print(json.dumps(results, indent=2))
    bad = sum(1 for r in results if r["status"] != "pass")
    print(f"{len(results) - bad}/{len(results)} citations pass", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
