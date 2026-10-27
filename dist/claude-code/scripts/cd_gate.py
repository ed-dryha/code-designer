#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Hard evidence gate over a design doc (decision records).

Usage: cd_gate.py <doc.md> --root DIR --model PATH [--kb DIR] [--tolerance N]
[--backlog PATH] [--futures PATH] [--exclude-plan ID ...] [--require-triage]
[--spec PATH]
Exit codes: 0 all pass, 1 any fail, 2 usage/IO. Prints a JSON array of
{record, check, status[, detail]} to stdout and "N/M checks pass" to stderr.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402

import cd_common  # noqa: E402
import cd_backlog  # noqa: E402
import cd_edits  # noqa: E402
import cd_futures  # noqa: E402
import cd_triage  # noqa: E402
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


BLAST_H = re.compile(r"^##\s+Blast Radius\s*$")
UNV_H = re.compile(r"^##\s+Unverified / Possible\s*$")
H2 = re.compile(r"^##\s+\S")
ITEM = re.compile(r"^[-*]\s+(\S+?):(\d+)\s+\[(model|grep)\]\s+(.*)$")
ANY_ITEM = re.compile(r"^[-*]\s+")
TICK = re.compile(r"`([^`]+)`")


def _section(lines, head):
    """Return list of (line_no, text) in the first section matching head, or None."""
    for i, ln in enumerate(lines):
        if head.match(ln):
            out = []
            for j in range(i + 1, len(lines)):
                if H2.match(lines[j]):
                    break
                out.append((j + 1, lines[j]))
            return out
    return None


TRIAGE_H = re.compile(r"^##\s+Triage\s*$")
TRIAGE_ORDER = {"skip": 0, "light": 1, "full": 2}
OVERRIDE_FORCED = re.compile(r'^forced-by-developer:\s*"([^"]+)"\s*$')
MAX_LIGHT_RECORDS = 2
MAX_LIGHT_RECORDS_V2 = 0
SUBPROCESS_TIMEOUT = 300


def _gate_triage_v1(text, require):
    """Check the optional ## Triage section (schema 1). Returns (results, verdict or None)."""
    res = []

    def add(check, status, **extra):
        res.append({"record": "triage", "check": check, "status": status, **extra})

    sec = _section(text.split("\n"), TRIAGE_H)
    if sec is None:
        if require:
            add("triage-section", "triage-missing", detail="## Triage")
        return res, None
    body = [t for _n, t in sec]
    verdict = None
    override = None
    for t in body:
        if t.startswith("Verdict:") and verdict is None:
            verdict = t[len("Verdict:"):].strip()
        elif t.startswith("Override:") and override is None:
            override = t[len("Override:"):].strip()
    if verdict not in TRIAGE_ORDER:
        add("verdict", "triage-bad-verdict", detail=verdict)
        verdict = None
    else:
        add("verdict", "pass")
    forced = False
    if override == "none":
        add("override", "pass")
    elif override is not None and OVERRIDE_FORCED.match(override):
        forced = True
        add("override", "pass")
    else:
        add("override", "triage-bad-override", detail=override)
    reasons = []
    in_reasons = False
    for t in body:
        if t.startswith("Reasons:"):
            in_reasons = True
        elif in_reasons and ANY_ITEM.match(t):
            if t.lstrip("-* ").strip():
                reasons.append(t)
        elif in_reasons and t.strip():
            in_reasons = False
    if verdict == "skip":
        add("reasons", "pass" if reasons else "triage-no-reasons")
    signals = None
    in_json = False
    buf = []
    for t in body:
        if not in_json and re.match(r"^```\s*json\s*$", t):
            in_json = True
        elif in_json and t.startswith("```"):
            break
        elif in_json:
            buf.append(t)
    try:
        signals = json.loads("\n".join(buf))
        if not isinstance(signals, dict) or not isinstance(signals.get("signalsSha"), str):
            signals = None
    except ValueError:
        signals = None
    if signals is None:
        add("signals", "triage-bad-signals")
    elif signals["signalsSha"] != cd_triage.signals_sha(signals):
        add("signals", "triage-signals-tampered")
        signals = None
    else:
        add("signals", "pass")
    if signals is not None and verdict in ("skip", "light") and not forced:
        rec = cd_triage.recommend(signals)
        if TRIAGE_ORDER[rec] > TRIAGE_ORDER[verdict]:
            add("anti-downgrade", "skip-contradicts-signals" if verdict == "skip"
                else "verdict-contradicts-signals", detail="script recommends " + rec)
        else:
            add("anti-downgrade", "pass")
    if verdict == "light":
        n = sum(1 for ln in text.split("\n") if HEADING.match(ln))
        add("light-records", "pass" if n <= MAX_LIGHT_RECORDS else "light-too-many-records",
            **({} if n <= MAX_LIGHT_RECORDS else {"detail": "%d records (max %d)" % (n, MAX_LIGHT_RECORDS)}))
    return res, verdict


HERE = os.path.dirname(os.path.abspath(__file__))


def _git_out(root, *args):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                           timeout=SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _base_or_tree(path, root, base_root):
    """Prefer the file as tracked at the base archive, else the working tree copy."""
    if not path:
        return None
    full = os.path.realpath(path)
    if base_root and (full == root or full.startswith(root + os.sep)):
        cand = os.path.join(base_root, os.path.relpath(full, root))
        if os.path.isfile(cand):
            return cand
    return full if os.path.isfile(full) else None


def _norm_json(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _signal_diff(rec, new):
    keys = []
    for k in sorted(set(rec) | set(new)):
        if k == "signalsSha":
            continue
        if k == "inputs" and isinstance(rec.get(k), dict) and isinstance(new.get(k), dict):
            for ik in sorted(set(rec[k]) | set(new[k])):
                if _norm_json(rec[k].get(ik)) != _norm_json(new[k].get(ik)):
                    keys.append("inputs." + ik)
        elif _norm_json(rec.get(k)) != _norm_json(new.get(k)):
            keys.append(k)
    return keys


def gate_triage(text, require, ctx=None):
    """Dispatch on the Triage signals schema: 2 -> recompute at the base commit, else the 0.2.0 rule."""
    ctx = ctx if ctx is not None else {}
    _v, signals = cd_edits.parse_triage_section(text)
    if isinstance(signals, dict) and signals.get("schema") == 2:
        return _gate_triage_v2(text, ctx, signals)
    return _gate_triage_v1(text, require)


def _gate_triage_v2(text, ctx, signals):
    """Schema-2 triage: recompute signals at the recorded base commit and bind the verdict both ways."""
    res = []

    def add(check, status, **extra):
        res.append({"record": "triage", "check": check, "status": status, **extra})

    ctx["schema"] = 2
    root = ctx["root"]
    body = [t for _n, t in (_section(text.split("\n"), TRIAGE_H) or [])]
    verdict = override = None
    for t in body:
        if t.startswith("Verdict:") and verdict is None:
            verdict = t[len("Verdict:"):].strip()
        elif t.startswith("Override:") and override is None:
            override = t[len("Override:"):].strip()
    if verdict not in TRIAGE_ORDER:
        add("verdict", "triage-bad-verdict", detail=verdict)
        verdict = None
    else:
        add("verdict", "pass")
    forced_phrase = None
    if override == "none":
        add("override", "pass")
    else:
        m = OVERRIDE_FORCED.match(override or "")
        if m:
            forced_phrase = m.group(1)
            add("override", "pass")
        else:
            add("override", "triage-bad-override", detail=override)

    if signals.get("signalsSha") != cd_triage.signals_sha(signals):
        add("signals", "triage-signals-tampered")
        return res, verdict
    add("signals", "pass")
    ctx["availability_required"] = [
        (None, d["name"]) for d in signals.get("availabilityRequired") or []
        if isinstance(d, dict) and isinstance(d.get("name"), str) and d["name"].strip()]
    inputs = signals.get("inputs")
    if not isinstance(inputs, dict):
        add("signals", "triage-bad-signals", detail="signals.inputs missing")
        return res, verdict

    # developer force: needs the recorded phrase in the Override line and in signals
    forced = inputs.get("forced")
    forced_ok = False
    if forced is None:
        if forced_phrase is not None:
            add("forced", "triage-verdict-mismatch", detail="Override line forces a verdict but signals record no force")
    elif (isinstance(forced, dict) and isinstance(forced.get("phrase"), str) and forced["phrase"].strip()
          and forced.get("verdict") in TRIAGE_ORDER):
        if forced_phrase == forced["phrase"] and verdict == forced["verdict"]:
            forced_ok = True
            add("forced", "pass")
        else:
            add("forced", "triage-verdict-mismatch",
                detail="signals record a force of %s but Override/Verdict do not match it" % forced["verdict"])
    else:
        add("forced", "triage-bad-signals", detail="inputs.forced malformed")
        return res, verdict

    # base commit
    base = inputs.get("base")
    base_root = None
    if base == "none":
        add("base", "pass", detail="base none: recomputed against the working tree")
    elif not cd_edits.valid_sha(base):
        add("base", "triage-base-unavailable", detail="base is not a 40-hex commit")
        return res, verdict
    else:
        dest = os.path.join(ctx["tmp"], "base")
        try:
            os.makedirs(dest, exist_ok=True)
            cd_edits.extract_base(root, base, dest)
        except (cd_edits.EditError, OSError, subprocess.SubprocessError) as ex:
            add("base", "triage-base-unavailable", detail=str(ex)[:200])
            return res, verdict
        base_root = os.path.realpath(dest)
        add("base", "pass")

    # spec
    spec_path = ctx.get("spec_path")
    if not spec_path:
        add("spec", "triage-spec-missing", detail="schema-2 triage needs the spec to run Spec Coverage")
        return res, verdict
    try:
        with open(spec_path, "rb") as fh:
            raw = fh.read(cd_common.MAX_BYTES + 1)
    except OSError as ex:
        add("spec", "triage-spec-missing", detail=str(ex)[:120])
        return res, verdict
    spec_sha = hashlib.sha256(raw).hexdigest()
    if inputs.get("specSha256") != spec_sha:
        add("spec", "triage-spec-changed", detail="recorded %s, current %s" % (inputs.get("specSha256"), spec_sha))
        return res, verdict
    add("spec", "pass")

    # model at the base commit (never the gate's --model: it describes the working tree, D-14)
    if base_root:
        mpath = os.path.join(ctx["tmp"], "base-model.json")
        cmd = [sys.executable, os.path.join(HERE, "cd_extract.py"), base_root, "--out", mpath]
        if ctx.get("cache_dir"):
            cmd += ["--cache-dir", ctx["cache_dir"]]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
            if r.returncode not in (0, 3):
                raise ValueError("extractor exit %d: %s" % (r.returncode, r.stderr.strip()[-160:]))
            with open(mpath, encoding="utf-8") as fh:
                model = json.load(fh)
            base_symbols = {x["id"]: x for x in model["symbols"]}
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as ex:
            add("base-model", "triage-base-unavailable", detail="could not extract the model at base: %s" % str(ex)[:200])
            return res, verdict
        ctx["base_root"], ctx["base_symbols"] = base_root, base_symbols
        rroot = base_root
    else:
        model, rroot = ctx["model"], root

    try:
        bl_file = _base_or_tree(ctx.get("backlog_path"), root, base_root)
        backlog_docs = cd_backlog.load(bl_file) if bl_file else None
        fu_file = _base_or_tree(ctx.get("futures_path"), root, base_root)
        plan_docs = cd_futures.load(fu_file) if fu_file else None
        lines = cd_edits.spec_lines(raw.decode("utf-8", errors="replace"))
        _i, new = cd_triage.collect2(
            model, rroot, inputs.get("edits"), inputs.get("newPaths"), backlog_docs, plan_docs, lines,
            inputs.get("dismissals"), inputs.get("citedTriggers"), base, inputs.get("rerun"), spec_sha, forced)
        new["inputs"]["spec"] = os.path.relpath(spec_path, root).replace(os.sep, "/")
        new = json.loads(json.dumps(new))
    except Exception as ex:  # noqa: BLE001 - fail closed: any recompute failure is a gate failure
        add("recompute", "triage-signals-mismatch", detail="recompute failed: %s" % str(ex)[:200])
        return res, verdict

    diff = _signal_diff(signals, new)
    if diff:
        detail = "differs: " + ", ".join(diff)
        if "modelSchema" in diff:
            detail += " (modelSchema recorded %s, recomputed %s)" % (
                _norm_json(signals.get("modelSchema")), _norm_json(new.get("modelSchema")))
        add("signals-recompute", "triage-signals-mismatch", detail=detail)
    else:
        add("signals-recompute", "pass")

    _unc, script_verdict, _r = cd_triage.decide2(new)
    if signals.get("verdictUncapped") != new["verdictUncapped"]:
        add("verdict-uncapped", "triage-verdict-mismatch",
            detail="recorded uncapped %s, recomputed %s" % (signals.get("verdictUncapped"), new["verdictUncapped"]))
    expect = forced["verdict"] if forced_ok else script_verdict
    if verdict is not None:
        if verdict == expect:
            add("verdict-binding", "pass")
        else:
            add("verdict-binding", "triage-verdict-mismatch",
                detail="Verdict %s, recomputed %s%s" % (
                    verdict, script_verdict,
                    "; cap bypass needs a recorded force" if new["verdictUncapped"] == "full" and script_verdict == "light" and verdict == "full" else ""))

    for c in cd_edits.unanswered_cues(new.get("cues") or [], [cd_edits.parse_edit(t) for t in new["inputs"]["edits"]],
                                      new["inputs"]["dismissals"]):
        add("cue", "triage-cue-unanswered", line=c["line"], detail="%s: %s" % (c["phrase"], c["text"]))

    if verdict == "light":
        n = sum(1 for ln in text.split("\n") if HEADING.match(ln))
        add("light-records", "pass" if n <= MAX_LIGHT_RECORDS_V2 else "triage-light-too-many-records",
            **({} if n <= MAX_LIGHT_RECORDS_V2 else {"detail": "%d records (max %d)" % (n, MAX_LIGHT_RECORDS_V2)}))

    if base_root:
        head = cd_edits.head_sha(root)
        if head and head != base:
            cnt = (_git_out(root, "rev-list", "--count", base + "..HEAD") or "?").strip()
            changed = (_git_out(root, "diff", "--name-only", base) or "").split()
            dirty = cd_edits.tracked_dirty(root)
            add("tree-vs-base", "pass",
                detail="working tree is %s commit(s)%s past %s; %d tracked file(s) differ from base"
                       % (cnt, " / dirty" if dirty else "", base[:10], len(changed)))
        elif head and cd_edits.tracked_dirty(root):
            add("tree-vs-base", "pass", detail="working tree is dirty past %s" % base[:10])
    return res, verdict


CHOSEN_H = re.compile(r"^##\s+Chosen Design\s*$")
AVAIL_H = re.compile(r"^##\s+Availability\s*$")
COVER_H = re.compile(r"^##\s+Spec Coverage\s*$")
PLACEHOLDERS = ("", "-", "--", "n/a", "na", "tbd", "none", "?", "todo")
SEP_CELL = re.compile(r"^:?-{2,}:?$")
AVAIL_KINDS = ("field", "property", "dependency")
SPEC_CELL = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?\s*(?:`([^`]+)`)?\s*$")
DR_ID = re.compile(r"^DR-\S+$")
NO_CHANGE = re.compile(r"^no design change:(.*)$", re.I)


def _table(sec):
    """Return (header_cells, [(line_no, cells)]) of the first pipe table in a section, or None."""
    rows = []
    for n, t in sec or []:
        t = t.strip()
        if not t.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in t.strip("|").split("|")]
        if all(SEP_CELL.match(c) for c in cells if c):
            continue
        rows.append((n, cells))
    if not rows:
        return None
    return rows[0][1], rows[1:]


def _placeholder(cell):
    return cell.strip().strip("`").strip().lower() in PLACEHOLDERS


def _avail_names(ctx):
    """Names the recorded schema-2 signals say need an Availability row (availabilityRequired)."""
    return list(ctx.get("availability_required") or [])


def gate_availability(text, extra_names=()):
    """Added fields/properties/dependencies need an ## Availability row (D-08).

    extra_names: further (line|None, name) needs from schema-2 signals.availabilityRequired."""
    res = []
    lines = text.split("\n")
    need = list(extra_names)
    tab = _table(_section(lines, CHOSEN_H))
    if tab is not None:
        head = [h.lower() for h in tab[0]]
        try:
            ik, inm, ich = head.index("kind"), head.index("name"), head.index("change")
        except ValueError:
            ik = None
        if ik is not None:
            for n, c in tab[1]:
                if len(c) > max(ik, inm, ich) and c[ik].lower() in AVAIL_KINDS and c[ich].lower().startswith("added"):
                    need.append((n, c[inm]))
    if not need:
        return res

    def add(check, status, **extra):
        res.append({"record": "availability", "check": check, "status": status, **extra})

    sec = _section(lines, AVAIL_H)
    if sec is None:
        add("availability-section", "availability-missing-section", detail="## Availability")
        return res
    atab = _table(sec)
    arows = []
    if atab is not None:
        ah = [h.lower() for h in atab[0]]
        try:
            ia, ip, ir = ah.index("name"), ah.index("populated when"), ah.index("readable when")
            arows = [(c[ia], c[ip], c[ir]) for _n, c in atab[1] if len(c) > max(ia, ip, ir)]
        except ValueError:
            arows = []
    for n, name in need:
        key = name.strip("` ").lower()
        match = [r for r in arows if key and (key in r[0].strip("` ").lower() or r[0].strip("` ").lower() in key)
                 and r[0].strip("` ")]
        ln = {} if n is None else {"line": n}
        if not match:
            add("availability-row", "availability-missing-row", detail=name, **ln)
        elif any(_placeholder(r[1]) or _placeholder(r[2]) for r in match[:1]):
            add("availability-row", "availability-empty", detail=name, **ln)
        else:
            add("availability-row", "pass", **ln)
    return res


def _spec_file(text, root, flag):
    """Return (full path|None, error|None) of the spec named by the flag or the doc's Spec: header."""
    raw = flag
    if raw is None:
        for ln in text.split("\n"):
            m = re.match(r"^[-*]?\s*Spec:\s*(.+?)\s*$", ln)
            if m:
                raw = m.group(1).strip("`")
                break
    if raw is None or raw.lower() == "none":
        return None, None
    if "\x00" in raw or ".." in raw.replace("\\", "/").split("/"):
        return None, "path-escape"
    full = os.path.realpath(raw if os.path.isabs(raw) else os.path.join(root, raw))
    if full != root and not full.startswith(root + os.sep):
        return None, "path-escape"
    if not os.path.isfile(full):
        return None, None
    return full, None


def resolve_spec(text, root, flag):
    """Return (lines|None, error|None). None/None means the rule is skipped."""
    full, err = _spec_file(text, root, flag)
    if full is None:
        return None, err
    try:
        if os.path.getsize(full) > MAX_DOC_BYTES:
            return None, "spec-too-large"
        with open(full, "rb") as fh:
            body = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None, None
    return cd_edits.spec_lines(body), None


def gate_spec_coverage(text, spec_lines, record_ids, spec_error=None):
    """Every listed Spec Coverage row must cite real spec lines and map to a DR or a reason (D-09, D-10)."""
    res = []

    def add(check, status, **extra):
        res.append({"record": "coverage", "check": check, "status": status, **extra})

    if spec_error:
        add("spec-path", "coverage-bad-line", detail=spec_error)
        return res
    if spec_lines is None:
        return res
    sec = _section(text.split("\n"), COVER_H)
    tab = _table(sec) if sec is not None else None
    if tab is None:
        add("coverage-section", "coverage-missing-section", detail="## Spec Coverage")
        return res
    for n, c in tab[1]:
        cell = c[0] if c else ""
        m = SPEC_CELL.match(cell)
        if not m:
            add("coverage-line", "coverage-bad-line", line=n, detail=cell)
            continue
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if not (1 <= a <= b <= len(spec_lines)):
            add("coverage-line", "coverage-bad-line", line=n, detail="%d-%d out of range (1-%d)" % (a, b, len(spec_lines)))
            continue
        span = spec_lines[a - 1:b]
        if not any(x.strip() for x in span):
            add("coverage-line", "coverage-bad-line", line=n, detail="blank spec line")
            continue
        add("coverage-line", "pass", line=n)
        if m.group(3):
            nq = cd_common.normalize_lines(m.group(3)).strip("\n")
            body = "\n".join(cd_common.normalize_lines(x) for x in span)
            add("coverage-quote", "pass" if nq and nq in body else "coverage-quote-mismatch", line=n,
                **({} if nq and nq in body else {"detail": m.group(3)}))
        maps = c[2].strip().strip("`") if len(c) > 2 else ""
        nc = NO_CHANGE.match(maps)
        if nc:
            add("coverage-maps", "pass" if nc.group(1).strip() and not _placeholder(nc.group(1)) else "coverage-no-reason", line=n)
        elif DR_ID.match(maps):
            add("coverage-maps", "pass" if maps in record_ids else "coverage-unknown-dr", line=n,
                **({} if maps in record_ids else {"detail": maps}))
        else:
            add("coverage-maps", "coverage-unmapped", line=n, detail=maps)
    return res


def gate_blast(text, root, tolerance):
    """Check the Blast Radius and Unverified / Possible sections (D-05, D-06)."""
    res = []

    def add(check, status, **extra):
        res.append({"record": "blast", "check": check, "status": status, **extra})

    lines = text.split("\n")
    blast = _section(lines, BLAST_H)
    unv = _section(lines, UNV_H)
    if blast is None:
        add("blast-section", "blast-missing-section", detail="## Blast Radius")
    if unv is None:
        add("unverified-section", "blast-missing-section", detail="## Unverified / Possible")
    if blast is not None:
        scope = [t for _n, t in blast if t.startswith("Scope:")]
        low = scope[0].lower() if scope else ""
        ok = bool(scope) and "grep" in low and "no call/import edges" in low
        add("blast-scope", "pass" if ok else "blast-no-scope")
        for n, t in blast:
            if not ANY_ITEM.match(t):
                continue
            m = ITEM.match(t)
            if not m:
                add("blast-item", "blast-untagged", line=n)
                continue
            line = int(m.group(2))
            cit = {"file": m.group(1), "startLine": line, "endLine": line}
            q = TICK.search(m.group(4))
            if q:
                cit["quote"] = q.group(1)
            st, _extra = cd_verify.check(root, cit, None, tolerance)
            add("blast-citation", "pass" if st == "pass" else "blast-bad-citation", line=n,
                **({} if st == "pass" else {"detail": st}))
    if unv is not None:
        items = [(n, t) for n, t in unv if ANY_ITEM.match(t)]
        if not items:
            body = "\n".join(t for _n, t in unv)
            add("unverified-empty", "pass" if "None found" in body else "unverified-empty")
        for n, t in items:
            add("unverified-item", "pass" if "reason:" in t else "unverified-no-reason", line=n)
    return res


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


TOUCHED_H = re.compile(r"^##\s+Backlog Findings Touched\s*$")
FINDING_ID = re.compile(r"F-[A-Za-z0-9._-]+")


def load_backlog(path):
    """Map finding id -> status from a backlog.md (safe_load_all). Missing file -> None."""
    if not path or not os.path.isfile(path):
        return None
    ids = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for d in yaml.safe_load_all(fh.read()):
                if isinstance(d, dict) and isinstance(d.get("id"), str):
                    ids[d["id"]] = d.get("status")
    except (OSError, yaml.YAMLError):
        return {}
    return ids


def _finding_status(fid, backlog):
    if not backlog or fid not in backlog:
        return "unknown-finding"
    return "resolved-finding" if backlog[fid] == "resolved" else "pass"


PLAN_ID = re.compile(r"P-[a-z0-9-]+-[0-9a-f]{6,8}")
PLAN_ARG = re.compile(r"^P-[a-z0-9-]+-[0-9a-f]{6,8}$")
USED_H = re.compile(r"^##\s+Future Plans Used\s*$")


def load_plans(path):
    """Map plan id -> status from future-plans.md. Absent -> None; unreadable/malformed -> {} (fail closed)."""
    if not path or not os.path.exists(path):
        return None
    plans = {}
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_DOC_BYTES:
            return {}
        with open(path, encoding="utf-8") as fh:
            for d in yaml.safe_load_all(fh.read()):
                if isinstance(d, dict) and isinstance(d.get("id"), str):
                    plans[d["id"]] = d.get("status")
    except (OSError, ValueError, yaml.YAMLError):
        return {}
    return plans


def _plan_status(pid, plans, excluded):
    """Return (status, detail); only confirmed, non-excluded plans pass."""
    if pid in excluded:
        return "plan-excluded-stale", pid
    if not plans or pid not in plans:
        return "unknown-plan", pid
    if plans[pid] != "confirmed":
        return "plan-not-confirmed", "%s (%s)" % (pid, plans[pid])
    return "pass", pid


def gate_plans_used(text, plans, excluded):
    """Cross-check ids listed under the optional ## Future Plans Used."""
    sec = _section(text.split("\n"), USED_H)
    res = []
    for n, t in sec or []:
        if not ANY_ITEM.match(t):
            continue
        m = PLAN_ID.search(t)
        if not m:
            continue
        st, detail = _plan_status(m.group(0), plans, excluded)
        res.append({"record": "plans", "check": "used-plan", "status": st, "line": n,
                    **({} if st == "pass" else {"detail": detail})})
    return res


def gate_touched(text, backlog):
    """Cross-check ids listed under ## Backlog Findings Touched."""
    sec = _section(text.split("\n"), TOUCHED_H)
    res = []
    for n, t in sec or []:
        if not ANY_ITEM.match(t):
            continue
        m = FINDING_ID.search(t)
        if not m:
            continue
        st = _finding_status(m.group(0), backlog)
        res.append({"record": "backlog", "check": "touched-finding", "status": st, "line": n,
                    **({} if st == "pass" else {"detail": m.group(0)})})
    return res


def gate_record(rid, rec, root, symbols, kb, tolerance, backlog=None, plans=None, excluded=frozenset()):
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
    findings = [e["finding"] for e in ev if isinstance(e, dict) and isinstance(e.get("finding"), str)] \
        if isinstance(ev, list) else []
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

    ok_cite = any(r["status"] == "pass" and r["check"].startswith("citation-") for r in res)
    for fid in findings:
        st = _finding_status(fid, backlog)
        add("finding", st, **({} if st == "pass" else {"detail": fid}))
    if findings:
        add("finding-citation", "pass" if ok_cite else "finding-without-citation")

    plan_refs = [e["plan"] for e in ev if isinstance(e, dict) and isinstance(e.get("plan"), str)] \
        if isinstance(ev, list) else []
    for pid in plan_refs:
        st, detail = _plan_status(pid, plans, excluded)
        add("plan", st, **({} if st == "pass" else {"detail": detail}))
    if plan_refs:
        add("plan-citation", "pass" if ok_cite else "plan-without-citation")

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
    ap.add_argument("--backlog")
    ap.add_argument("--futures")
    ap.add_argument("--exclude-plan", action="append", default=[], dest="exclude_plan")
    ap.add_argument("--require-triage", action="store_true", dest="require_triage")
    ap.add_argument("--spec")
    ap.add_argument("--cache-dir", dest="cache_dir")
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
            model = json.load(fh)
        symbols = {x["id"]: x for x in model["symbols"]}
    except (OSError, ValueError, KeyError, TypeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    if not os.path.isdir(root) or args.tolerance < 0:
        print("error: root must be a directory, tolerance >= 0", file=sys.stderr)
        return 2
    if any(not PLAN_ARG.match(x) for x in args.exclude_plan):
        print("error: --exclude-plan needs a plan id (P-...-hex)", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="cd-gate-") as tmp:
        spec_path, _spec_err = _spec_file(text, root, args.spec)
        ctx = {"root": root, "model": model, "tmp": os.path.realpath(tmp), "spec_path": spec_path,
               "cache_dir": args.cache_dir,
               "backlog_path": args.backlog or os.path.join(root, "docs", "design", "backlog.md"),
               "futures_path": args.futures or os.path.join(root, "docs", "design", "future-plans.md")}
        return _run(args, root, text, symbols, ctx)


def _run(args, root, text, symbols, ctx):
    excluded = frozenset(args.exclude_plan)
    kb = load_kb(args.kb)
    backlog = load_backlog(ctx["backlog_path"])
    plans = load_plans(ctx["futures_path"])

    results, tverdict = gate_triage(text, args.require_triage, ctx)
    v2 = ctx.get("schema") == 2
    if tverdict == "skip" and not v2 and all(r["status"] == "pass" for r in results):
        print(json.dumps(results, indent=2))
        print(f"{len(results)}/{len(results)} checks pass", file=sys.stderr)
        return 0
    # schema 2: citations resolve against the base commit triage saw (D-14)
    croot = ctx.get("base_root") or root
    csyms = ctx.get("base_symbols") or symbols
    records = extract_records(text)
    skip2 = v2 and tverdict == "skip"
    if skip2:
        records = []
    elif not records and not (v2 and tverdict == "light"):
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
        results.extend(gate_record(rec.get("id", hid), rec, croot, csyms, kb, args.tolerance, backlog, plans, excluded))

    if not skip2:
        results.extend(gate_blast(text, croot, args.tolerance))
        results.extend(gate_touched(text, backlog))
        results.extend(gate_plans_used(text, plans, excluded))
    results.extend(gate_availability(text, _avail_names(ctx)))
    spec_lines, spec_err = resolve_spec(text, root, args.spec)
    results.extend(gate_spec_coverage(text, spec_lines, {h for h, _b in records}, spec_err))

    print(json.dumps(results, indent=2))
    bad = sum(1 for r in results if r["status"] != "pass")
    print(f"{len(results) - bad}/{len(results)} checks pass", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
