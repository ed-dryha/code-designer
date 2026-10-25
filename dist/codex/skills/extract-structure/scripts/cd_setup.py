#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["tree-sitter-language-pack==1.22.1", "tree-sitter>=0.23,<0.27"]
# ///
"""Prefetch tree-sitter grammars into a cache dir (setup stage, D-02).

Exit codes: 0 all ok, 2 usage / hard failure (incl. checksum mismatch), 3 any language failed (offline).
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402
from languages import EXT_TO_LANG  # noqa: E402

PACK_SPEC = "tree-sitter-language-pack==1.22.1"
TS_SPEC = "tree-sitter==0.26.0"
NOTICE = ("notice: grammars are third-party native binaries downloaded from GitHub releases; "
          "pack version is pinned (1.22.1) and checksums are verified by the pack.")


def tier1():
    return sorted(set(EXT_TO_LANG.values()))


def detect_languages(path):
    """Map file extensions under path (shared ignore list) to pack grammar names."""
    found = set()
    for _dirpath, dirs, fnames in os.walk(path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in cd_common.IGNORE_DIRS)
        for fn in fnames:
            lang = EXT_TO_LANG.get(os.path.splitext(fn)[1].lower())
            if lang:
                found.add(lang)
    return sorted(found)


def dir_size(path):
    total = 0
    for dp, _d, fns in os.walk(path):
        for fn in fns:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return total


def venv_python(venv):
    sub = "Scripts" if os.name == "nt" else "bin"
    return os.path.join(venv, sub, "python.exe" if os.name == "nt" else "python")


def bootstrap_venv(cache, run=subprocess.run):
    """Create <cache>/venv and pip install only the two pinned packages (T-07-05)."""
    venv = os.path.join(cache, "venv")
    run([sys.executable, "-m", "venv", venv], check=True)
    py = venv_python(venv)
    run([py, "-m", "pip", "install", "--disable-pip-version-check", PACK_SPEC, TS_SPEC], check=True)
    return py


def prefetch_one(pack, lang):
    """Download one grammar via the shared pack helper. Raises GrammarUnavailable on offline failure."""
    pack.load(lang)


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Prefetch tree-sitter grammars")
    ap.add_argument("--cache-dir")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--detect", metavar="PATH", help="prefetch grammars for languages found under PATH")
    g.add_argument("--tier1", action="store_true", help="prefetch all tier-1 languages")
    g.add_argument("--langs", help="comma-separated explicit grammar names")
    g.add_argument("--status", action="store_true", help="list downloaded grammars")
    ap.add_argument("--bootstrap-venv", action="store_true", help="create <cache>/venv with pinned packages")
    ap.add_argument("--no-uv", action="store_true", help="behave as if uv is absent")
    return ap.parse_args(argv)


def main(argv=None, run=subprocess.run):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    cache = args.cache_dir or os.environ.get("CODE_DESIGNER_CACHE")
    if not cache:
        print("error: --cache-dir or CODE_DESIGNER_CACHE required", file=sys.stderr)
        return 2
    cache = os.path.abspath(cache)
    os.makedirs(cache, exist_ok=True)

    no_uv = args.no_uv or shutil.which("uv") is None
    if args.bootstrap_venv or (no_uv and not args.status and _pack_missing()):
        try:
            py = bootstrap_venv(cache, run)
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"error: venv bootstrap failed: {e}", file=sys.stderr)
            return 2
        print(f"venv python: {py}")
        print("re-run cd_setup.py / cd_extract.py with that interpreter")
        return 0

    from cd_pack import open_pack, GrammarUnavailable
    import tree_sitter_language_pack as tslp
    pack = open_pack(cache, allow_download=True)

    if args.status:
        langs = sorted(tslp.downloaded_languages())
        for lang in langs:
            print(lang)
        return 0

    if args.langs:
        langs = sorted({x.strip() for x in args.langs.split(",") if x.strip()})
    elif args.tier1:
        langs = tier1()
    else:
        langs = detect_languages(args.detect or ".")
    print(NOTICE)
    have = set(tslp.downloaded_languages())
    failed = []
    for lang in langs:
        if lang in have:
            print(f"ok {lang} (cached)")
            continue
        try:
            prefetch_one(pack, lang)
            print(f"ok {lang}")
        except GrammarUnavailable as e:
            print(f"failed {lang}: {e.reason}", file=sys.stderr)
            failed.append(lang)
        except tslp.ChecksumMismatchError as e:
            print(f"error: checksum mismatch for {lang}: {e}", file=sys.stderr)
            return 2
    print(f"cache size: {dir_size(cache)} bytes")
    if failed:
        print("failed languages: " + ", ".join(failed), file=sys.stderr)
        return 3
    return 0


def _pack_missing():
    try:
        import tree_sitter_language_pack  # noqa: F401
        return False
    except ImportError:
        return True


if __name__ == "__main__":
    sys.exit(main())
