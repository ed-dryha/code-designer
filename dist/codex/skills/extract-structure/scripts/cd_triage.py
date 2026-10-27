#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Design triage: mechanical signals plus a recommended skip|light|full verdict.

Usage: cd_triage.py --root DIR --model PATH --spec PATH
                    [--modify NAME_OR_ID ...] [--additive NAME_OR_ID ...] [--new-path PATH ...]
                    [--backlog PATH] [--futures PATH] [--force skip|light|full --force-phrase TEXT]
Prints JSON {schema, inputs, signals, recommended, reasons, forced, signalsSha, specItems, render}.
Exit 0 ok, 2 usage/IO/confinement. Never writes files.

The agent declares only what the change does (modify / additive / new paths); every signal
is computed here. `recommend()` and `signals_sha()` are importable so the gate can recheck
a recorded Triage section.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_backlog  # noqa: E402
import cd_blast  # noqa: E402
import cd_common  # noqa: E402
import cd_futures  # noqa: E402

# Starting thresholds; calibrated on the F1/F2 base commits, see
# .planning/phases/05-plugin-refinements-from-validation-findings/05-CALIBRATION.md.
FULL_NONTEST = 4          # modify touch with at least this many non-test dependent files
FULL_SWITCH_SITES = 4     # additive touch with at least this many switch sites
SKIP_SWITCH_SITES = 1     # additive-only skip allows at most this many switch sites
SKIP_NONTEST = 3          # ... and at most this many non-test dependent files per touch
HIT_CAP = 50
BIG = 10 ** 6

VERDICTS = ("skip", "light", "full")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
ITEM_RE = re.compile(r"^\s*(\d+[.)]|[-*])\s")
SWITCH_RE = re.compile(r"\b(switch|when|match)\b")
DECL_KW = "class|struct|enum|protocol|interface|trait|object|type|typealias|record|actor"
TEST_DIR_RE = re.compile(r"(^|/)(tests?|specs?|__tests__|[A-Za-z]*Tests?)(/|\.|$)")
TEST_FILE_RE = re.compile(r"(Tests?\.[A-Za-z0-9]+$|_tests?\.[A-Za-z0-9]+$|\.(spec|test)\.[A-Za-z0-9]+$|(^|/)test_[^/]*$)")


class UsageError(Exception):
    pass


def is_test_path(path):
    return bool(TEST_DIR_RE.search(path) or TEST_FILE_RE.search(path))


# ------------------------------------------------------------ pure decision

def _touches(signals):
    """(name, info) for each touch; a missing kind counts as modify."""
    dep = signals.get("dependentFiles") or {}
    return [(n, v) for n, v in sorted(dep.items()) if isinstance(v, dict)]


def _decide(signals):
    """Return (verdict, reasons) by the starting thresholds, applied top-down."""
    s = signals or {}
    touches = _touches(s)
    modify = [(n, v) for n, v in touches if v.get("kind", "modify") != "additive"]
    additive = [(n, v) for n, v in touches if v.get("kind") == "additive"]
    switch = s.get("switchSites") or 0
    hits = s.get("assumptionHits") or []
    full = []
    if s.get("backlogFlagged"):
        full.append("%d open backlog finding(s) touch the changed code" % len(s["backlogFlagged"]))
    if s.get("variationPoints"):
        full.append("%d variation point(s) touched" % len(s["variationPoints"]))
    for n, v in modify:
        if (v.get("nonTest") or 0) >= FULL_NONTEST:
            full.append("modifies %s: %d non-test dependent files (>= %d)" % (n, v["nonTest"], FULL_NONTEST))
    if hits:
        full.append("%d assumption checklist hit(s) mentioning a modified name" % len(hits))
    if additive and switch >= FULL_SWITCH_SITES:
        full.append("additive change with %d switch sites (>= %d, heuristic)" % (switch, FULL_SWITCH_SITES))
    if full:
        return "full", full
    touched = s.get("touchedExisting") or 0
    overlap = s.get("planOverlap") or []
    if touched == 0 and not overlap:
        return "skip", ["additive only: new files, no existing symbol modified"]
    if (touched and not modify and additive and not overlap and switch <= SKIP_SWITCH_SITES
            and all((v.get("nonTest") or 0) <= SKIP_NONTEST for _, v in additive)):
        return "skip", ["additive only: %d switch site(s) (heuristic, <= %d) and at most %d non-test "
                        "dependent files per touch" % (switch, SKIP_SWITCH_SITES, SKIP_NONTEST)]
    light = []
    if touched:
        light.append("%d existing symbol(s) or file(s) touched" % touched)
    if overlap:
        light.append("%d confirmed future plan(s) overlap the touched files" % len(overlap))
    if s.get("modelAvailable") is False and any((v.get("nonTest") or 0) >= 1 for _, v in touches):
        light.append("no structure model for the touched language; dependents come from grep only")
    return "light", light or ["touches existing code"]


def recommend(signals):
    """Pure verdict (skip|light|full) from a signals dict."""
    return _decide(signals)[0]


def signals_sha(signals):
    """sha256 of the canonical signals json, ignoring any signalsSha key."""
    body = {k: v for k, v in (signals or {}).items() if k != "signalsSha"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_section(verdict, forced, reasons, signals, sha):
    lines = ["## Triage", "Verdict: " + (forced["verdict"] if forced else verdict)]
    if forced:
        lines.append('Override: forced-by-developer: "%s"' % forced["phrase"])
    else:
        lines.append("Override: none")
    lines.append("Reasons:")
    lines += ["- " + r for r in reasons]
    if forced:
        lines.append("- script recommended %s; developer forced %s" % (verdict, forced["verdict"]))
    body = dict(signals, signalsSha=sha)
    lines += ["Signals:", "```json", json.dumps(body, indent=2, sort_keys=True), "```", ""]
    return "\n".join(lines)


# ------------------------------------------------------------ confinement / io

def _confined(root, path, base=None):
    """Resolve path (relative to base, default the cwd) and require it inside root."""
    full = os.path.realpath(os.path.join(base if base is not None else os.getcwd(), path))
    if full == root or full.startswith(root + os.sep):
        return full
    raise UsageError("path escapes root: %s" % path)


def _relpath(root, full):
    return os.path.relpath(full, root).replace(os.sep, "/")


def _new_path(root, p):
    if (not isinstance(p, str) or not p or os.path.isabs(p) or "\x00" in p
            or ".." in p.replace("\\", "/").split("/")):
        raise UsageError("unsafe --new-path: %r" % p)
    return _relpath(root, _confined(root, p, root))


# ------------------------------------------------------------ signal helpers

def _glob_match(pattern, path):
    pat = pattern.split("#", 1)[0].strip("/")
    if not pat:
        return False
    if "*" not in pat:
        return path == pat or path.startswith(pat + "/")
    rx = re.escape(pat).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
    return re.fullmatch(rx, path) is not None or fnmatch.fnmatch(path, pat)


def _decl_re(name):
    last = name.split(".")[-1]
    return re.compile(r"\b(?:%s|func|def|fn)\s+%s\b" % (DECL_KW, re.escape(last)))


def _spec_items(path):
    with open(path, "rb") as fh:
        text = fh.read(cd_common.MAX_BYTES).decode("utf-8", errors="replace")
    return [{"line": n, "text": " ".join(t.split())[:200]}
            for n, t in enumerate(text.split("\n"), 1) if ITEM_RE.match(t)]


def collect(model, root, modify, additive, new_paths, backlog_docs, plan_docs):
    """Compute (inputs, signals) from declared touches. All reads stay under root."""
    symbols = model.get("symbols", [])
    by_id = {s["id"]: s for s in symbols}
    cov = model.get("coverage") or {}
    unav = {}
    for u in cov.get("unavailable") or []:
        unav[u.get("language")] = [x for x in (u.get("files") or []) if isinstance(x, str)] \
            if isinstance(u.get("files"), list) else []
    unav_files = list(dict.fromkeys(f for fs in unav.values() for f in fs))
    cfiles = cov.get("files") if isinstance(cov.get("files"), list) else []
    all_files = list(dict.fromkeys([f.get("path") for f in cfiles if isinstance(f.get("path"), str)]
                                   + unav_files))
    cache = {}

    reclassified, fresh = [], []
    for p in new_paths:
        if os.path.exists(os.path.join(root, p)):
            reclassified.append(p)
        else:
            fresh.append(p)

    touches = []  # dicts: name, kind, targets, names, own_files
    model_available = True
    for kind, args in (("modify", modify), ("additive", additive)):
        for a in args:
            if a in by_id:
                sym = by_id[a]
                touches.append({"name": a, "kind": kind, "targets": [a], "names": [],
                                "own": {sym["file"]}, "sym": sym})
                continue
            if "#" in a or "/" in a or not IDENT_RE.match(a):
                raise UsageError("unknown symbol id: %s" % a)
            if len(a.split(".")[-1]) < 4:
                raise UsageError("name too short to grep reliably, use a symbol id: %s" % a)
            last = a.split(".")[-1]
            tgt = [s["id"] for s in symbols if s["name"] in (a, last)]
            drx = _decl_re(a)
            own = set()
            for rel in all_files:
                lines = cd_blast._read_lines(root, rel, cache)
                if lines and any(drx.search(t) for t in lines):
                    own.add(rel)
            touches.append({"name": a, "kind": kind, "targets": tgt, "names": [] if tgt else [a],
                            "own": own, "sym": None})
            if not tgt:
                model_available = False
    for p in reclassified:
        tg = [s["id"] for s in symbols if s["file"] == p]
        touches.append({"name": p, "kind": "modify", "targets": tg, "names": [], "own": {p}, "sym": None})
        if p in unav_files or not tg:
            model_available = False

    dependent, hit_sites, touched_files = {}, {}, set(fresh)
    variation = []
    for t in touches:
        files, sites = set(), []
        if t["targets"] or t["names"]:
            res = cd_blast.blast(model, root, t["targets"], BIG, BIG, names=t["names"])
            for d in res["model"] + res["grep"]:
                if d["file"] not in t["own"]:
                    files.add(d["file"])
                    sites.append((d["file"], d["line"]))
        t["files"], t["sites"] = files, sites
        non_test = [f for f in files if not is_test_path(f)]
        dependent[t["name"]] = {"total": len(files), "nonTest": len(non_test), "kind": t["kind"]}
        touched_files |= t["own"]
        if files & set(unav_files) or t["own"] & set(unav_files):
            model_available = False
        sym = t["sym"]
        if sym and sym["kind"] in cd_blast.TYPE_KINDS:
            same = [s for s in symbols if s["name"] == sym["name"] and s["kind"] in cd_blast.TYPE_KINDS]
            subs = [c for c in symbols if len(same) == 1
                    and any(st.get("name") == sym["name"] for st in c.get("supertypes") or [])]
            if len(subs) >= 2:
                variation.append({"symbol": sym["id"], "subtypes": len(subs)})
            elif sym["kind"] == "enum" and t["kind"] == "modify":
                members = [c for c in symbols if c.get("parent") == sym["id"]]
                if len(members) >= 2:
                    variation.append({"symbol": sym["id"], "members": len(members)})

    switch = set()
    for t in touches:
        if t["kind"] != "additive":
            continue
        for rel, line in t["sites"]:
            if is_test_path(rel):
                continue
            lines = cd_blast._read_lines(root, rel, cache) or []
            for n in range(max(1, line - 2), min(len(lines), line + 2) + 1):
                if SWITCH_RE.search(lines[n - 1]):
                    switch.add((rel, n))

    # assumption hits: checklist idioms on lines that mention a modified name (no-grammar files)
    hits = []
    mod_names = [(t["name"].split(".")[-1]) for t in touches if t["kind"] == "modify" and not t["sym"]
                 and t["name"] not in reclassified]
    mod_names += [t["sym"]["name"] for t in touches if t["kind"] == "modify" and t["sym"]]
    seen = set()
    for nm in dict.fromkeys(mod_names):
        nrx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(nm) + r"(?![A-Za-z0-9_])")
        for rel in unav_files:
            lines = cd_blast._read_lines(root, rel, cache) or []
            for n, text in enumerate(lines, 1):
                if len(text) > cd_blast.MAX_LINE or (rel, n) in seen or not nrx.search(text):
                    continue
                for cat, rx in cd_blast.CHECKLIST:
                    if rx.search(text):
                        seen.add((rel, n))
                        hits.append({"file": rel, "line": n, "category": cat})
                        break
    hits.sort(key=lambda h: (h["file"], h["line"]))

    syms = [t["targets"][0] for t in touches if t["sym"]]
    backlog = [{"id": f["id"], "symbol": f.get("symbol"), "priority": f.get("priority")}
               for f in cd_backlog.touching(backlog_docs, syms, sorted(touched_files - set(fresh)))] \
        if backlog_docs else []

    overlap = []
    for p in (plan_docs or [])[1:]:
        if not isinstance(p, dict) or p.get("status") != "confirmed":
            continue
        pats = [x for x in p.get("affected") or [] if isinstance(x, str)]
        cov_files = sorted(f for f in touched_files if any(_glob_match(x, f) for x in pats))
        if cov_files:
            overlap.append({"id": p.get("id"), "files": cov_files})

    signals = {
        "touchedExisting": len(touches),
        "additiveOnly": not any(t["kind"] == "modify" for t in touches),
        "dependentFiles": dependent,
        "switchSites": len(switch),
        "variationPoints": variation,
        "backlogFlagged": backlog,
        "planOverlap": overlap,
        "assumptionHits": hits[:HIT_CAP],
        "modelAvailable": model_available,
        "noGrammarLanguages": sorted(l for l in unav if isinstance(l, str)),
    }
    inputs = {"modify": list(modify), "additive": list(additive), "newPaths": list(new_paths),
              "reclassified": reclassified}
    return inputs, signals


# ------------------------------------------------------------ cli

def main(argv=None):
    ap = argparse.ArgumentParser(description="Design triage signals and recommended verdict")
    ap.add_argument("--root", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--modify", action="append", default=[])
    ap.add_argument("--additive", action="append", default=[])
    ap.add_argument("--new-path", action="append", default=[], dest="new_path")
    ap.add_argument("--backlog")
    ap.add_argument("--futures")
    ap.add_argument("--force", choices=VERDICTS)
    ap.add_argument("--force-phrase", default="")
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as ex:
        return 2 if ex.code else 0
    try:
        root = os.path.realpath(a.root)
        if not os.path.isdir(root):
            raise UsageError("root is not a directory")
        phrase = " ".join(a.force_phrase.replace('"', "'").split())[:200]
        if a.force and not phrase:
            raise UsageError("--force needs a non-empty --force-phrase (the override is recorded)")
        with open(a.model, encoding="utf-8") as fh:
            model = json.load(fh)
        if not isinstance(model.get("symbols"), list):
            raise UsageError("model has no symbols list")
        spec = _confined(root, a.spec)
        if not os.path.isfile(spec):
            raise UsageError("spec is not a file")
        new_paths = [_new_path(root, p) for p in a.new_path]
        backlog_docs = plan_docs = None
        if a.backlog:
            bp = _confined(root, a.backlog)
            if os.path.isfile(bp):
                backlog_docs = cd_backlog.load(bp)
        if a.futures:
            fp = _confined(root, a.futures)
            if os.path.isfile(fp):
                plan_docs = cd_futures.load(fp)
        inputs, signals = collect(model, root, a.modify, a.additive, new_paths, backlog_docs, plan_docs)
        inputs["spec"] = _relpath(root, spec)
        items = _spec_items(spec)
    except (UsageError, OSError, ValueError, KeyError, TypeError, cd_futures.PlansError,
            cd_backlog.yaml.YAMLError) as ex:
        print("error: %s" % ex, file=sys.stderr)
        return 2
    verdict, reasons = _decide(signals)
    sha = signals_sha(signals)
    forced = {"verdict": a.force, "phrase": phrase} if a.force else None
    out = {"schema": 1, "inputs": inputs, "signals": signals, "recommended": verdict,
           "reasons": reasons, "forced": forced, "signalsSha": sha, "specItems": items,
           "render": render_section(verdict, forced, reasons, signals, sha)}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
