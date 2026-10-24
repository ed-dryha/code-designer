#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Verify citations {file, startLine, endLine, quote?, symbol?} against real files.

Exit codes: 0 all pass, 1 any fail, 2 usage. Prints a JSON array of {citation, status}.
Statuses: pass, missing-file, out-of-range, quote-mismatch, path-escape.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402


def check(root, c):
    f = c.get("file")
    s, e = c.get("startLine"), c.get("endLine")
    if not isinstance(f, str) or not f or os.path.isabs(f):
        return "path-escape"
    full = os.path.realpath(os.path.join(root, f))
    if full != root and not full.startswith(root + os.sep):
        return "path-escape"
    if not os.path.isfile(full):
        return "missing-file"
    with open(full, "rb") as fh:
        text = fh.read().decode("utf-8", errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not (isinstance(s, int) and isinstance(e, int)) or not (1 <= s <= e <= len(lines)):
        return "out-of-range"
    quote = c.get("quote")
    if quote:
        region = cd_common.normalize_lines("\n".join(lines[s - 1:e]))
        if cd_common.normalize_lines(quote) not in region:
            return "quote-mismatch"
    return "pass"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify citations")
    ap.add_argument("--root", required=True)
    ap.add_argument("--citations", required=True)
    ap.add_argument("--model")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    root = os.path.realpath(args.root)
    try:
        with open(args.citations, encoding="utf-8") as fh:
            cits = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not isinstance(cits, list) or not os.path.isdir(root):
        print("error: citations must be a JSON list and root a directory", file=sys.stderr)
        return 2
    results = [{"citation": c, "status": check(root, c) if isinstance(c, dict) else "out-of-range"} for c in cits]
    print(json.dumps(results, indent=2))
    return 0 if all(r["status"] == "pass" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
