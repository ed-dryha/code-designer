#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Future-plans engine: id, propose, apply, lint, show, stale.

docs/design/future-plans.md is a stream of `---` delimited YAML documents: a header
(`schema: 1`, `kind: code-designer-futures`) followed by one document per plan.
IDs, merges, diffs and staleness are computed here, never by the model.
Exit codes: 0 ok, 1 rejected / lint problems / stale-diff, 2 usage or confinement.
`stale` never exits non-zero: it must not block design.
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_verify  # noqa: E402

STATUSES = ("inferred", "confirmed", "done", "dropped")
CONFIDENCES = ("high", "medium", "low")
CAND_SOURCES = ("commit", "todo", "doc", "model")
VERIFIED_SOURCES = ("commit", "todo", "doc")
MAX_CANDIDATES = 4
MAX_BYTES = 1024 * 1024
HEADER = {"schema": 1, "kind": "code-designer-futures"}
KEYS = ("id", "title", "status", "confidence", "source", "affected", "lastConfirmed",
        "lastConfirmedCommit", "notes")
ID_RE = re.compile(r"^P-[a-z0-9-]+-[0-9a-f]{6,8}$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PATH_RE = re.compile(r"^[A-Za-z0-9_./*@+-]+$")
TOP_COMMENT = ("# Code Designer future plans. Human-editable: change title, confidence, affected\n"
               "# and notes freely; re-runs keep your edits. IDs are script-generated, do not edit.\n")
GIT_TIMEOUT = 20


class PlansError(Exception):
    pass


# ---------------------------------------------------------------- ids / yaml

def _norm_title(t):
    return " ".join(str(t).lower().split())


def plan_id(title, n=6):
    norm = _norm_title(title)
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")[:30].strip("-") or "plan"
    return f"P-{slug}-{hashlib.sha1(norm.encode('utf-8')).hexdigest()[:n]}"


class _Dumper(yaml.SafeDumper):
    pass


def _str_rep(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_rep)


def _dump(doc):
    return yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000)


def render(plans):
    out = [TOP_COMMENT, "---\n" + _dump(HEADER)]
    for p in plans:
        ordered = {k: p[k] for k in KEYS if k in p}
        for k in p:
            if k not in ordered:
                ordered[k] = p[k]
        out.append(f"---\n# {p['id']}\n" + _dump(ordered))
    return "".join(out)


def read_text(path):
    """Return file text, or '' when absent. Raises PlansError on size cap."""
    if not os.path.isfile(path):
        return ""
    if os.path.getsize(path) > MAX_BYTES:
        raise PlansError("file-too-large")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_text(text):
    return [d for d in yaml.safe_load_all(text) if d is not None]


def load(path):
    return load_text(read_text(path))


def _dstr(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.strftime("%Y-%m-%d")
    return v if isinstance(v, str) else ""


def _one_line(s, cap=300):
    return " ".join(str(s).split())[:cap]


def _safe_pathspec(p):
    """Return the normalized plain pathspec, or None when unsafe."""
    if not isinstance(p, str):
        return None
    p = p.split("#", 1)[0]
    if (not p or p.startswith(("-", ":", "/")) or "\x00" in p or "\n" in p
            or not PATH_RE.match(p) or ".." in p.split("/")):
        return None
    return p


# ---------------------------------------------------------------- git helpers

def _git(root, *args):
    """Run git with an argv list; return (rc, stdout). rc is None if git unusable."""
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                           timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return r.returncode, r.stdout


def head_sha(root):
    rc, out = _git(root, "rev-parse", "HEAD")
    return out.strip() if rc == 0 else ""


def commit_exists(root, ref):
    if not SHA_RE.match(ref):
        return False
    rc, _ = _git(root, "cat-file", "-e", ref + "^{commit}")
    return rc == 0


# ---------------------------------------------------------------- paths

def resolve_paths(a):
    root = os.path.realpath(a.root)
    design = os.path.realpath(os.path.join(root, "docs", "design"))
    target = a.plans or os.path.join(design, "future-plans.md")
    if not os.path.isabs(target):
        target = os.path.join(root, target)
    target = os.path.realpath(target)
    if not target.startswith(design + os.sep):
        raise PlansError("confinement")
    return root, target


# ---------------------------------------------------------------- validation

def _validate_affected(aff):
    if not isinstance(aff, list) or not aff:
        return None, "empty-affected"
    out = []
    for x in aff:
        s = _safe_pathspec(x)
        if s is None:
            return None, f"unsafe-affected:{x!r}"
        out.append(s)
    return out, None


def _validate_source(root, src, symbols, model_given):
    """Return (clean source or None, problem or None, verified bool)."""
    if not isinstance(src, dict) or src.get("type") not in CAND_SOURCES:
        return None, "bad-source-type", False
    t, ref = src["type"], src.get("ref")
    quote = _one_line(src.get("quote", ""))
    if not isinstance(ref, str) or not ref:
        return None, f"{t}-missing-ref", False
    clean = {"type": t, "ref": ref}
    if quote:
        clean["quote"] = quote
    if t == "commit":
        if not commit_exists(root, ref):
            return None, f"unverifiable-commit:{ref}", False
        return clean, None, True
    if t == "model":
        if model_given and ref not in symbols:
            return None, f"unknown-symbol:{ref}", False
        return clean, None, False
    m = re.match(r"^(.+):(\d+)$", ref)
    if not m:
        return None, f"bad-citation:{ref}", False
    line = int(m.group(2))
    cit = {"file": m.group(1), "startLine": line, "endLine": line}
    if quote:
        cit["quote"] = quote
    st, _ = cd_verify.check(root, cit, symbols)
    if st != "pass":
        return None, f"citation-{st}:{ref}", False
    return clean, None, True


def validate_candidate(root, c, symbols, model_given):
    problems = []
    if not isinstance(c, dict):
        return None, ["not-an-object"]
    if "id" in c:
        problems.append("id-not-allowed")
    if "status" in c:
        problems.append("status-not-allowed")
    title = c.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("bad-title")
    if c.get("confidence") not in CONFIDENCES:
        problems.append("bad-confidence")
    aff, p = _validate_affected(c.get("affected"))
    if p:
        problems.append(p)
    srcs = c.get("source")
    clean, verified = [], 0
    if not isinstance(srcs, list) or not srcs:
        problems.append("no-source")
    else:
        for s in srcs:
            cs, p, v = _validate_source(root, s, symbols, model_given)
            if p:
                problems.append(p)
            else:
                clean.append(cs)
                verified += v
        if not problems and not verified:
            problems.append("no-verified-source")
    if problems:
        return None, problems
    return {"title": title.strip(), "confidence": c["confidence"], "source": clean,
            "affected": aff}, []


# ---------------------------------------------------------------- compute

def _assign_ids(items):
    """items: list of (title, ...); return ids with collision extension."""
    seen, ids = {}, []
    for it in items:
        norm = _norm_title(it)
        pid = plan_id(it)
        if pid in seen and seen[pid] != norm:
            pid = plan_id(it, 8)
        seen[pid] = norm
        ids.append(pid)
    return ids


def compute(root, plans_path, inputs, date, symbols=None, model_given=False):
    """Pure: return (old_text, new_text, counts) or raise PlansError([problems])."""
    old_text = read_text(plans_path)
    docs = load_text(old_text) if old_text else []
    if docs:
        if not isinstance(docs[0], dict) or docs[0].get("schema") != 1 \
                or docs[0].get("kind") != HEADER["kind"]:
            raise PlansError("bad-header")
        docs = docs[1:]
    existing, order = {}, []
    for d in docs:
        if not isinstance(d, dict) or not isinstance(d.get("id"), str):
            raise PlansError("plan-without-id")
        existing[d["id"]] = d
        order.append(d["id"])
    for d in existing.values():
        for k in ("lastConfirmed",):
            if k in d:
                d[k] = _dstr(d[k])

    symbols = symbols or {}
    rejected = []
    cands_in = inputs.get("candidates") or []
    decisions = inputs.get("decisions") or []
    devs = inputs.get("developerPlans") or []
    if not (isinstance(cands_in, list) and isinstance(decisions, list) and isinstance(devs, list)):
        raise PlansError("bad-input")
    if len(cands_in) > MAX_CANDIDATES:
        rejected.append({"problems": ["too-many-candidates"]})
        cands_in = []
    cands = []
    for c in cands_in:
        clean, probs = validate_candidate(root, c, symbols, model_given)
        if probs:
            rejected.append({"title": c.get("title") if isinstance(c, dict) else None,
                             "problems": probs})
        else:
            cands.append(clean)
    for dec in decisions:
        probs = []
        if not isinstance(dec, dict):
            probs.append("not-an-object")
        else:
            if dec.get("id") not in existing:
                probs.append("unknown-id")
            if dec.get("action") not in ("confirm", "edit", "drop"):
                probs.append("bad-action")
            if dec.get("action") == "edit":
                if "confidence" in dec and dec["confidence"] not in CONFIDENCES:
                    probs.append("bad-confidence")
                if "affected" in dec and _validate_affected(dec["affected"])[1]:
                    probs.append("bad-affected")
                if "title" in dec and not (isinstance(dec["title"], str) and dec["title"].strip()):
                    probs.append("bad-title")
        if probs:
            rejected.append({"id": dec.get("id") if isinstance(dec, dict) else None, "problems": probs})
    dev_clean = []
    for dp in devs:
        probs = []
        if not isinstance(dp, dict):
            rejected.append({"problems": ["not-an-object"]})
            continue
        if not (isinstance(dp.get("title"), str) and dp["title"].strip()):
            probs.append("bad-title")
        if dp.get("confidence") not in CONFIDENCES:
            probs.append("bad-confidence")
        aff, p = _validate_affected(dp.get("affected"))
        if p:
            probs.append(p)
        if probs:
            rejected.append({"title": dp.get("title"), "problems": probs})
        else:
            dev_clean.append((dp, aff))
    if rejected:
        raise PlansError(rejected)

    counts = {"added": 0, "updated": 0, "confirmed": 0, "dropped": 0, "untouched": 0}
    snapshot = {k: json.dumps(v, sort_keys=True, default=str) for k, v in existing.items()}
    touched = set()

    for pid, c in zip(_assign_ids([c["title"] for c in cands]), cands):
        cur = existing.get(pid)
        if cur is None:
            existing[pid] = {"id": pid, "title": c["title"], "status": "inferred",
                             "confidence": c["confidence"], "source": c["source"],
                             "affected": c["affected"], "notes": ""}
            order.append(pid)
            counts["added"] += 1
        elif cur.get("status") == "inferred":
            cur["source"], cur["affected"] = c["source"], c["affected"]
            touched.add(pid)

    head = head_sha(root)
    for dec in decisions:
        cur = existing[dec["id"]]
        answer = str(dec.get("answer", "")).strip()
        if dec["action"] == "drop":
            cur["status"] = "dropped"
        else:
            if dec["action"] == "edit":
                for k in ("title", "confidence", "affected"):
                    if k in dec:
                        cur[k] = _validate_affected(dec[k])[0] if k == "affected" else dec[k]
            cur["status"] = "confirmed"
            cur["lastConfirmed"] = date
            cur["lastConfirmedCommit"] = head
        if answer and answer not in (cur.get("notes") or ""):
            cur["notes"] = (cur.get("notes") + "\n" if cur.get("notes") else "") + answer
        touched.add(dec["id"])
        counts["dropped" if dec["action"] == "drop" else "confirmed"] += 1

    dev_ids = _assign_ids([dp["title"] for dp, _ in dev_clean])
    for pid, (dp, aff) in zip(dev_ids, dev_clean):
        answer = str(dp.get("answer", "")).strip()
        src = [{"type": "developer", "ref": "developer", "quote": _one_line(answer)}]
        cur = existing.get(pid)
        if cur is None:
            cur = existing[pid] = {"id": pid, "title": dp["title"].strip(), "notes": ""}
            order.append(pid)
            counts["added"] += 1
        cur.update(status="confirmed", confidence=dp["confidence"], source=src,
                   affected=aff, lastConfirmed=date, lastConfirmedCommit=head)
        if answer and answer not in (cur.get("notes") or ""):
            cur["notes"] = (cur.get("notes") + "\n" if cur.get("notes") else "") + answer
        touched.add(pid)
        counts["confirmed"] += 1

    for pid in touched:
        if pid in snapshot and json.dumps(existing[pid], sort_keys=True, default=str) != snapshot[pid]:
            counts["updated"] += 1
    counts["untouched"] = sum(1 for pid in snapshot if pid not in touched)

    new_text = render([existing[p] for p in order])
    return old_text, new_text, counts


# ---------------------------------------------------------------- commands

def cmd_id(a):
    print(plan_id(a.title))
    return 0


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _prepare(a):
    try:
        root, target = resolve_paths(a)
    except PlansError:
        print("error: --plans must be inside <root>/docs/design/", file=sys.stderr)
        return None
    try:
        with open(a.input, encoding="utf-8") as fh:
            inputs = json.load(fh)
        symbols, given = {}, False
        if a.model:
            with open(a.model, encoding="utf-8") as fh:
                symbols = {x["id"]: x for x in json.load(fh)["symbols"]}
            given = True
    except (OSError, ValueError, KeyError, TypeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return None
    if not isinstance(inputs, dict) or not os.path.isdir(root):
        print("error: input must be a JSON object and root a directory", file=sys.stderr)
        return None
    date = a.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    return root, target, inputs, date, symbols, given


def _compute(a):
    prep = _prepare(a)
    if prep is None:
        return 2, None
    root, target, inputs, date, symbols, given = prep
    try:
        return 0, (target, compute(root, target, inputs, date, symbols, given))
    except PlansError as ex:
        arg = ex.args[0]
        if isinstance(arg, list):
            print(json.dumps({"rejected": arg}, indent=2))
            print(f"{len(arg)} item(s) rejected; nothing written", file=sys.stderr)
            return 1, None
        print(f"error: {arg}", file=sys.stderr)
        return 2, None
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as ex:
        print(f"error: unreadable plans file: {ex}", file=sys.stderr)
        return 2, None


def cmd_propose(a):
    rc, res = _compute(a)
    if res is None:
        return rc
    _, (old, new, _counts) = res
    if old == new:
        print("no-change")
    else:
        sys.stdout.writelines(difflib.unified_diff(
            old.splitlines(True), new.splitlines(True), "future-plans.md", "future-plans.md (proposed)"))
    print(f"expect-sha: {_sha(old)}")
    return 0


def cmd_apply(a):
    rc, res = _compute(a)
    if res is None:
        return rc
    target, (old, new, counts) = res
    if _sha(old) != a.expect_sha:
        print("stale-diff: plans file changed since propose; re-run propose", file=sys.stderr)
        print(json.dumps({"error": "stale-diff"}))
        return 1
    if new != old:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new)
        os.replace(tmp, target)
    print(json.dumps(counts))
    return 0


def lint_problems(path):
    try:
        docs = load(path)
    except PlansError as ex:
        return [{"id": None, "problem": str(ex)}]
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as ex:
        return [{"id": None, "problem": f"unreadable: {ex}"}]
    probs = []
    if not docs or not isinstance(docs[0], dict) or docs[0].get("schema") != 1 \
            or docs[0].get("kind") != HEADER["kind"]:
        probs.append({"id": None, "problem": "bad header: need schema: 1 and kind: code-designer-futures"})
    seen = set()
    for d in docs[1:]:
        if not isinstance(d, dict):
            probs.append({"id": None, "problem": "plan is not a mapping"})
            continue
        pid = d.get("id")
        if pid in seen:
            probs.append({"id": pid, "problem": "duplicate id"})
        seen.add(pid)
        if not (isinstance(pid, str) and ID_RE.match(pid)):
            probs.append({"id": pid, "problem": "id must match ^P-[a-z0-9-]+-[0-9a-f]{6,8}$"})
        if d.get("status") not in STATUSES:
            probs.append({"id": pid, "problem": f"status must be one of {'|'.join(STATUSES)}"})
        if d.get("confidence") not in CONFIDENCES:
            probs.append({"id": pid, "problem": f"confidence must be one of {'|'.join(CONFIDENCES)}"})
        if d.get("status") == "confirmed" and not _dstr(d.get("lastConfirmed")):
            probs.append({"id": pid, "problem": "confirmed plan needs lastConfirmed"})
        aff = d.get("affected")
        if not isinstance(aff, list) or not aff:
            probs.append({"id": pid, "problem": "affected must be a non-empty list"})
        elif any(_safe_pathspec(x) is None for x in aff):
            probs.append({"id": pid, "problem": "affected contains an unsafe pathspec"})
    return probs


def cmd_lint(a):
    target = os.path.realpath(a.path)
    if a.root:
        root = os.path.realpath(a.root)
        design = os.path.realpath(os.path.join(root, "docs", "design"))
        if not os.path.isabs(a.path):
            target = os.path.realpath(os.path.join(root, a.path))
        if not target.startswith(design + os.sep):
            print("error: path must be inside <root>/docs/design/", file=sys.stderr)
            return 2
    probs = lint_problems(target)
    print(json.dumps(probs, indent=2))
    print(f"{len(probs)} problem(s)", file=sys.stderr)
    return 1 if probs else 0


def cmd_show(a):
    try:
        _, target = resolve_paths(a)
    except PlansError:
        print("error: --plans must be inside <root>/docs/design/", file=sys.stderr)
        return 2
    if not os.path.isfile(target):
        print(json.dumps({"exists": False}))
        return 0
    try:
        docs = load(target)
    except (PlansError, OSError, yaml.YAMLError, UnicodeDecodeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    plans = [d for d in docs[1:] if isinstance(d, dict)]
    for p in plans:
        if "lastConfirmed" in p:
            p["lastConfirmed"] = _dstr(p["lastConfirmed"])
    print(json.dumps({"exists": True, "plans": plans}, indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Future plans tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("id")
    p.add_argument("--title", required=True)
    for name in ("propose", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--root", required=True)
        p.add_argument("--plans")
        p.add_argument("--input", required=True)
        p.add_argument("--model")
        p.add_argument("--date")
        if name == "apply":
            p.add_argument("--expect-sha", required=True)
    p = sub.add_parser("lint")
    p.add_argument("path")
    p.add_argument("--root")
    p = sub.add_parser("show")
    p.add_argument("--root", required=True)
    p.add_argument("--plans")
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2
    return {"id": cmd_id, "propose": cmd_propose, "apply": cmd_apply,
            "lint": cmd_lint, "show": cmd_show}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
