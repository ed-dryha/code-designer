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
import cd_audit  # noqa: E402
import cd_blast  # noqa: E402
import cd_common  # noqa: E402
import cd_edits  # noqa: E402
import cd_futures  # noqa: E402
import cd_reach  # noqa: E402

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


# ------------------------------------------------------------ schema 2

# Starting values, calibrated in 06-CALIBRATION.md.
BLAST_CALLERS = 4         # change-contract: member with at least this many non-test caller files
ADD_CASE_SITES = 3        # add-case: at least this many unflagged switch sites

_CITED_RE = re.compile(r"^(spec|backlog|plan):(\S+)$")


def _norm(text, cap=200):
    return " ".join(str(text).split())[:cap]


def _read_lines_of(root, rel, cache):
    return cd_blast._read_lines(root, rel, cache) or []


def _resolve_edit(model, root, e):
    """Resolve an edit target; add-case prefers the enum type named by the last segment."""
    t = e["target"]
    if e["shape"] == "add-case" and "." in t and "#" not in t:
        try:
            r = cd_reach.resolve_target(model, root, t.split(".")[-1])
            if r.get("owner") and r.get("member") is None:
                return r
        except cd_edits.EditError:
            pass
    return cd_reach.resolve_target(model, root, t)


def _check_new_absent(e, res, root, cache):
    new = e.get("new")
    if not new or e["shape"] not in ("add-member", "add-case", "add-param"):
        return
    if e["shape"] == "add-param":
        rx = re.compile(r"(?<![A-Za-z0-9_])%s\s*:" % re.escape(new))
        for rel, n in res.get("decl_lines") or []:
            ls = _read_lines_of(root, rel, cache)
            if 1 <= n <= len(ls) and rx.search(ls[n - 1]):
                raise UsageError("=%s already exists as a parameter of %s" % (new, e["target"]))
        return
    for rel, a, b in res.get("blocks") or []:
        ls = _read_lines_of(root, rel, cache)
        for n in range(a, min(b, len(ls)) + 1):
            if cd_reach._is_member_decl(ls[n - 1], new):
                raise UsageError("=%s already exists in %s (%s:%d)" % (new, res.get("owner") or e["target"], rel, n))


def _verify_cited(cited, n_spec, backlog_docs, plan_docs):
    out = []
    for raw in cited:
        m = _CITED_RE.match(raw if isinstance(raw, str) else "")
        if not m:
            raise UsageError("bad --trigger %r, expected spec:N, backlog:ID or plan:ID" % (raw,))
        kind, ref = m.groups()
        if kind == "spec":
            if not ref.isdigit() or not 1 <= int(ref) <= n_spec:
                raise UsageError("--trigger spec:%s is outside the spec (%d lines)" % (ref[:20], n_spec))
            out.append({"class": "pattern", "kind": "cited-spec", "ref": "spec:%d" % int(ref)})
        elif kind == "backlog":
            ok = any(isinstance(d, dict) and d.get("id") == ref and d.get("status") == "open"
                     for d in (backlog_docs or [])[1:])
            if not ok:
                raise UsageError("--trigger backlog:%s is not an open finding in the backlog" % ref[:60])
            out.append({"class": "pattern", "kind": "cited-backlog", "ref": ref})
        else:
            ok = any(isinstance(d, dict) and d.get("id") == ref and d.get("status") == "confirmed"
                     for d in (plan_docs or [])[1:])
            if not ok:
                raise UsageError("--trigger plan:%s is not a confirmed plan" % ref[:60])
            out.append({"class": "pattern", "kind": "cited-plan", "ref": ref})
    return out


def collect2(model, root, edits, new_paths, backlog_docs, plan_docs, spec_lines, dismissals,
             cited_triggers, base, rerun, spec_sha, forced=None):
    """Compute (inputs, signals) for schema 2 from per-edit declarations. Reads stay under root."""
    root = os.path.realpath(root)
    texts = sorted(set(edits or []))
    parsed = [cd_edits.parse_edit(t) for t in texts]
    cd_edits.validate_edits(parsed, len(spec_lines), spec_lines)
    fresh = sorted(set(new_paths or []))
    for p in fresh:
        if os.path.exists(os.path.join(root, p)):
            raise UsageError("--new-path %s exists; declare edits to its members with --edit" % p)

    symbols = [s for s in model.get("symbols") or [] if isinstance(s, dict)]
    cov = model.get("coverage") or {}
    cov_files = [f for f in cov.get("files") or [] if isinstance(f, dict) and isinstance(f.get("path"), str)]
    unav_files = {x for u in cov.get("unavailable") or [] if isinstance(u, dict)
                  for x in (u.get("files") or []) if isinstance(x, str)}
    parsed_langs = {f.get("language") for f in cov_files if f.get("parsed") and f.get("language")}
    lang_by_path = {f["path"]: f.get("language") for f in cov_files}
    cache = {}

    callers, case_sites, readers, hits, unverified = [], [], [], [], []
    triggers, avail = set(), set()
    touched = set(fresh)
    owner_type_ids = set()
    for text, e in zip(texts, parsed):
        res = _resolve_edit(model, root, e)
        _check_new_absent(e, res, root, cache)
        touched |= set(res.get("files") or [])
        shape, owner = e["shape"], res.get("owner")
        if shape in cd_edits.ADDITIONS and owner:
            owner_type_ids |= {s["id"] for s in symbols
                               if s.get("name") == owner and s.get("kind") in cd_blast.TYPE_KINDS}
        if shape == "add-member" and e.get("state"):
            avail.add((owner or e["target"], e["new"]))
        elif shape == "add-param":
            avail.add((owner or e["target"], e["new"]))
        if shape == "add-case":
            cs = cd_reach.case_sites(root, res, None, model)
            case_sites.append({"target": e["target"], "count": len(cs["sites"]), "sites": cs["sites"]})
            unverified += [dict(u, target=e["target"]) for u in cs["unverified"]]
            if len(cs["sites"]) >= ADD_CASE_SITES:
                triggers.add(("blast", "case-sites", e["target"]))
        elif shape == "change-contract":
            mc = cd_reach.member_callers(model, root, res)
            callers.append({"target": e["target"], "total": mc["total"], "nonTest": mc["nonTest"],
                            "files": mc["files"]})
            if mc["nonTest"] >= BLAST_CALLERS:
                triggers.add(("blast", "callers", e["target"]))
        elif shape == "change-assumption":
            ar = cd_reach.assumption_reach(model, root, res.get("member") or res.get("owner"))
            readers.append({"target": e["target"], "count": len(ar["readers"]), "files": ar["files"],
                            "truncated": bool(ar.get("truncated"))})
            hits += [dict(h, target=e["target"]) for h in ar["checklist"]]
            triggers.add(("pattern", "assumption", e["ref"]))
        elif shape == "add-variant":
            triggers.add(("pattern", "variant", e["ref"]))
        if shape in ("add-member", "add-case", "add-param", "change-contract") and owner:
            types = [s for s in symbols if s.get("name") == owner and s.get("kind") in cd_blast.TYPE_KINDS]
            if len(types) == 1:
                subs = [c for c in symbols
                        if any(isinstance(st, dict) and st.get("name") == owner
                               for st in c.get("supertypes") or [])]
                if len(subs) >= 2:
                    triggers.add(("pattern", "variation", types[0]["id"]))

    if backlog_docs and owner_type_ids:
        for f in cd_backlog.touching(backlog_docs, sorted(owner_type_ids), []):
            triggers.add(("pattern", "backlog", f["id"]))
    for p in (plan_docs or [])[1:]:
        if not isinstance(p, dict) or p.get("status") != "confirmed":
            continue
        pats = [x for x in p.get("affected") or [] if isinstance(x, str)]
        if any(_glob_match(x, f) for x in pats for f in touched):
            triggers.add(("pattern", "plan", p.get("id")))
    cited = _verify_cited(cited_triggers or [], len(spec_lines), backlog_docs, plan_docs)
    for c in cited:
        triggers.add((c["class"], c["kind"], c["ref"]))

    def lang_ok(path):
        lang = lang_by_path.get(path) or cd_reach._lang(path)
        return bool(lang) and lang in parsed_langs and path not in unav_files
    no_grammar = sorted({(lang_by_path.get(p) or cd_reach._lang(p)) for p in touched
                         if not lang_ok(p)} - {None})

    # dismissals and cues
    cues = cd_edits.find_cues(spec_lines)
    cue_lines = {c["line"] for c in cues}
    dis = []
    for d in dismissals or []:
        if d.get("line") not in cue_lines:
            raise UsageError("--dismiss %s: not a spec cue line" % d.get("line"))
        if not cd_edits._real_reason(d.get("reason")):
            raise UsageError("--dismiss %s needs a real reason" % d.get("line"))
        dis.append({"line": d["line"], "reason": _norm(d["reason"])})
    dis.sort(key=lambda d: (d["line"], d["reason"]))
    edit_lines = {int(e["ref"].split(":")[1]) for e in parsed
                  if e["shape"] in cd_edits.CITING and e.get("ref")}
    dis_lines = {d["line"] for d in dis}
    cue_out = [{"line": c["line"], "phrase": c["phrase"], "text": c["text"],
                "answered": "edit" if c["line"] in edit_lines else "dismissed" if c["line"] in dis_lines else None}
               for c in cues]

    inputs = {"edits": texts, "newPaths": fresh, "base": base, "specSha256": spec_sha,
              "dismissals": dis, "rerun": rerun, "forced": forced, "citedTriggers": sorted(cited_triggers or [])}
    callers.sort(key=lambda d: d["target"])
    case_sites.sort(key=lambda d: d["target"])
    readers.sort(key=lambda d: d["target"])
    hits = sorted(hits, key=lambda h: (h["target"], h["file"], h["line"], h["category"]))[:HIT_CAP]
    unverified.sort(key=lambda u: (u["target"], u["file"], u["line"], u["reason"]))
    signals = {
        "schema": 2,
        "inputs": inputs,
        "reach": {"callers": callers, "caseSites": case_sites, "readers": readers,
                  "assumptionHits": hits, "unverified": unverified},
        "cues": cue_out,
        "triggers": [{"class": c, "kind": k, "ref": r} for c, k, r in sorted(triggers)],
        "availabilityRequired": [{"name": n, "owner": o} for o, n in sorted(avail)],
        "patternAdoptionAvailable": any(lang_ok(p) for p in touched),
        "noGrammarLanguages": no_grammar,
        "modelSchema": {"modelSchemaVersion": model.get("schemaVersion"),
                        "extractorVersion": (model.get("generator") or {}).get("version")
                        or model.get("extractorVersion")},
    }
    unc, ver, _ = decide2(signals)
    signals["verdictUncapped"], signals["verdict"] = unc, ver
    return inputs, signals


def decide2(signals):
    """Return (verdictUncapped, verdict, reasons): pattern trigger -> full, blast -> light, else skip.

    A full verdict with no tree-sitter coverage on the touched files is capped at light; the
    uncapped verdict is always returned so it can be compared (D-10, D-18)."""
    s = signals or {}
    trig = [t for t in s.get("triggers") or [] if isinstance(t, dict)]
    pattern = [t for t in trig if t.get("class") == "pattern"]
    blast = [t for t in trig if t.get("class") == "blast"]
    reasons = ["pattern trigger %s (%s)" % (t.get("kind"), t.get("ref")) for t in pattern]
    reasons += ["blast trigger %s (%s)" % (t.get("kind"), t.get("ref")) for t in blast]
    if pattern:
        uncapped = "full"
    elif blast:
        uncapped = "light"
    else:
        uncapped = "skip"
        reasons = ["no trigger fired: additions and changes reached only by new inputs"]
    verdict = uncapped
    if uncapped == "full" and not s.get("patternAdoptionAvailable"):
        verdict = "light"
        t = pattern[0]
        langs = ", ".join(s.get("noGrammarLanguages") or []) or "any touched file"
        reasons.append("pattern trigger %s (%s) fired but no tree-sitter coverage for %s: pattern "
                       "adoption is unavailable; blast radius runs through the grep checklist"
                       % (t.get("kind"), t.get("ref"), langs))
    return uncapped, verdict, reasons


def cue_reasons(signals):
    out = []
    for c in (signals or {}).get("cues") or []:
        ans = c.get("answered")
        out.append("spec cue line %s (%s): %s" % (c.get("line"), c.get("phrase"),
                                                  "answered by %s" % ans if ans else "UNANSWERED"))
    return out


def render_section2(verdict, forced, reasons, signals, sha):
    lines = ["## Triage", "Verdict: " + (forced["verdict"] if forced else verdict)]
    lines.append('Override: forced-by-developer: "%s"' % forced["phrase"] if forced else "Override: none")
    lines.append("Reasons:")
    lines += ["- " + r for r in reasons]
    if forced:
        lines.append("- script recommended %s; developer forced %s" % (verdict, forced["verdict"]))
    body = dict(signals, signalsSha=sha)
    lines += ["Signals:", "```json", json.dumps(body, indent=2, sort_keys=True), "```", ""]
    return "\n".join(lines)


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
