#!/usr/bin/env python3
"""Build dist/<host>/ plugin trees from src/ and hosts/<host>/.

Usage: build.py [--check] [--src DIR] [--hosts DIR] [--out DIR]

Host differences are expressed only through {{TOKEN}} substitution in *.md
files (D-05). Unknown tokens, unexpanded braces and {{# conditionals fail the
build. Output is deterministic: sorted traversal, LF newlines, no timestamps.
"""
import argparse
import filecmp
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_NAMES = ("PLUGIN_ROOT", "SCRIPTS", "KNOWLEDGE", "CACHE_DIR", "HOST")
TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIX = (".pyc",)


class BuildError(Exception):
    pass


def iter_files(base):
    """Yield (relative posix path, absolute path) in sorted order."""
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(SKIP_SUFFIX):
                continue
            ab = os.path.join(dirpath, name)
            yield os.path.relpath(ab, base).replace(os.sep, "/"), ab


def expand(text, tokens, label):
    if "{{#" in text:
        raise BuildError(f"{label}: '{{{{#' conditionals are forbidden (D-05)")

    def sub(m):
        name = m.group(1)
        if name not in tokens:
            raise BuildError(f"{label}: unknown token {{{{{name}}}}}")
        return tokens[name]

    out = TOKEN_RE.sub(sub, text)
    if "{{" in out:
        raise BuildError(f"{label}: unexpanded '{{{{' remains")
    return out


def emit(dest, rel, ab, tokens, files):
    target = rel.replace(os.sep, "/")
    if target in files:
        raise BuildError(f"duplicate output path {target}")
    with open(ab, "rb") as fh:
        data = fh.read()
    if rel.endswith(".md"):
        text = data.decode("utf-8").replace("\r\n", "\n")
        data = expand(text, tokens, f"{rel}").encode("utf-8")
    files[target] = data


def collect(src, host, host_dir):
    """Return {relative path: bytes} for one host."""
    with open(os.path.join(host_dir, "tokens.json"), encoding="utf-8") as fh:
        tokens = json.load(fh)
    missing = [t for t in TOKEN_NAMES if t not in tokens]
    if missing:
        raise BuildError(f"{host}/tokens.json missing {missing}")
    files = {}

    def add(prefix, base):
        if not os.path.isdir(base):
            return
        for rel, ab in iter_files(base):
            emit(None, f"{prefix}{rel}", ab, tokens, files)

    # Host overlay (manifests); tokens.json itself is build input, not output.
    for rel, ab in iter_files(host_dir):
        if rel == "tokens.json":
            continue
        emit(None, rel, ab, tokens, files)

    add("skills/", os.path.join(src, "skills"))
    add("knowledge/", os.path.join(src, "knowledge"))
    if host == "codex":
        runtime = "skills/extract-structure/scripts/"
    else:
        runtime = "scripts/"
    add(runtime, os.path.join(src, "extractor"))
    schema = os.path.join(src, "schema")
    add(runtime, schema)
    return files


def build_all(src, hosts, out):
    results = {}
    for host in sorted(os.listdir(hosts)):
        host_dir = os.path.join(hosts, host)
        if os.path.isfile(os.path.join(host_dir, "tokens.json")):
            results[host] = collect(src, host, host_dir)
    if not results:
        raise BuildError(f"no hosts found in {hosts}")
    for host, files in results.items():
        target = os.path.join(out, host)
        shutil.rmtree(target, ignore_errors=True)
        for rel in sorted(files):
            path = os.path.join(target, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(files[rel])
    return sorted(results)


def snapshot(base):
    if not os.path.isdir(base):
        return {}
    return {rel: ab for rel, ab in iter_files(base)}


def check(src, hosts, out):
    diffs = []
    with tempfile.TemporaryDirectory() as tmp:
        names = build_all(src, hosts, tmp)
        for host in names:
            fresh, committed = snapshot(os.path.join(tmp, host)), snapshot(os.path.join(out, host))
            for rel in sorted(set(fresh) | set(committed)):
                if rel not in committed:
                    diffs.append(f"missing: {host}/{rel}")
                elif rel not in fresh:
                    diffs.append(f"extra: {host}/{rel}")
                elif not filecmp.cmp(fresh[rel], committed[rel], shallow=False):
                    diffs.append(f"differs: {host}/{rel}")
        # committed host dirs that no longer have a source host
        if os.path.isdir(out):
            for d in sorted(os.listdir(out)):
                if d not in names and os.path.isdir(os.path.join(out, d)):
                    diffs.append(f"extra: {d}/")
    return diffs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if committed dist differs")
    ap.add_argument("--src", default=os.path.join(ROOT, "src"))
    ap.add_argument("--hosts", default=os.path.join(ROOT, "hosts"))
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = ap.parse_args(argv)
    try:
        if args.check:
            diffs = check(args.src, args.hosts, args.out)
            for d in diffs:
                print(d)
            if diffs:
                print(f"dist is stale: {len(diffs)} difference(s); run scripts/build.py", file=sys.stderr)
                return 1
            print("dist is up to date")
            return 0
        names = build_all(args.src, args.hosts, args.out)
        print("built: " + ", ".join(names))
        return 0
    except BuildError as exc:
        print(f"build error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
