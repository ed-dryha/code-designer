#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Shared pure helpers for schema-2 triage, the gate and the audit.

Edit grammar (one --edit string): SHAPE:TARGET[=NEW][+state|+dependency][@REF]
  shapes: add-member, add-case, add-param (additions, no citation),
          body-new-inputs (needs @IDENT naming the new input that reaches it),
          change-contract, change-assumption, add-variant (need @spec:N).

Schema-2 triage signals JSON keys other plans rely on:
  schema (2), inputs{edits, newPaths, base, specSha256, dismissals, rerun,
  forced}, reach, cues, triggers, availabilityRequired,
  patternAdoptionAvailable, noGrammarLanguages, verdictUncapped, verdict,
  signalsSha.

Everything taken from specs, docs or agent strings is data: it is never put in
a subprocess argument except a validated 40-hex sha, and never run in a shell.
"""
import json
import os
import re
import subprocess
import tarfile

SHAPES = ("add-member", "add-case", "add-param", "body-new-inputs",
          "change-contract", "change-assumption", "add-variant")
ADDITIONS = frozenset({"add-member", "add-case", "add-param"})
CITING = frozenset({"change-contract", "change-assumption", "add-variant"})

GRAMMAR = "SHAPE:TARGET[=NEW][+state|+dependency][@REF]"
_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_EDIT_RE = re.compile(
    r"^(?P<target>[A-Za-z0-9_.#/\-]+)"
    r"(?:=(?P<new>" + _IDENT + r"))?"
    r"(?:\+(?P<state>state|dependency))?"
    r"(?:@(?P<ref>spec:[0-9]+|" + _IDENT + r"))?$")
_IDENT_RE = re.compile("^" + _IDENT + "$")
_SPEC_REF = re.compile(r"^spec:([0-9]+)$")


class EditError(ValueError):
    pass


def _bad(msg):
    return EditError("%s (grammar: %s)" % (msg, GRAMMAR))


def parse_edit(text):
    """Parse one --edit string into a dict or raise EditError."""
    if not isinstance(text, str) or not text:
        raise _bad("empty edit")
    if "\x00" in text or re.search(r"\s", text):
        raise _bad("edit must not contain whitespace or NUL")
    shape, sep, rest = text.partition(":")
    if not sep:
        raise _bad("missing ':' after shape")
    if shape not in SHAPES:
        raise _bad("unknown shape %r, expected one of %s" % (shape[:40], ", ".join(SHAPES)))
    m = _EDIT_RE.match(rest)
    if not m:
        raise _bad("bad target, NEW, state or ref in %r" % text[:80])
    e = {"shape": shape, "target": m.group("target"), "new": m.group("new"),
         "state": m.group("state"), "ref": m.group("ref")}
    if e["state"] and shape != "add-member":
        raise _bad("+state/+dependency applies only to add-member")
    if shape in ("add-param", "add-case") and not e["new"]:
        raise _bad("%s requires =NEW" % shape)
    if shape == "add-member" and e["state"] and not e["new"]:
        raise _bad("add-member with +%s requires =NEW" % e["state"])
    if shape not in ADDITIONS and e["new"] and shape != "add-variant":
        raise _bad("=NEW applies only to additions and add-variant")
    ref = e["ref"]
    if shape in ADDITIONS:
        if ref:
            raise _bad("%s takes no @ref" % shape)
    elif shape == "body-new-inputs":
        if not ref or _SPEC_REF.match(ref):
            raise _bad("body-new-inputs requires @NAME of the new input (not @spec:N)")
    else:
        mm = _SPEC_REF.match(ref or "")
        if not mm:
            raise _bad("%s requires @spec:N" % shape)
        if int(mm.group(1)) < 1:
            raise _bad("@spec:N must be a positive line number")
    return e


def _word_in(name, line):
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", line) is not None


def validate_edits(edits, n_spec_lines, spec_lines=None):
    """Check spec citations are in range and body-new-inputs refs are grounded."""
    declared = {e["new"] for e in edits if e["shape"] in ADDITIONS and e.get("new")}
    for e in edits:
        ref = e.get("ref")
        mm = _SPEC_REF.match(ref or "")
        if mm:
            n = int(mm.group(1))
            if n < 1 or n > n_spec_lines:
                raise EditError("@spec:%d is outside the spec (%d lines)" % (n, n_spec_lines))
        if e["shape"] == "body-new-inputs":
            if ref in declared:
                continue
            if spec_lines is not None and any(_word_in(ref, ln) for ln in spec_lines):
                continue
            raise EditError("body-new-inputs @%s names no declared =NEW and does not appear in the "
                            "spec; declare the new case/parameter or fix the name" % ref)


def spec_lines(text):
    """Number spec lines the same way for triage, gate and audit (CRLF safe)."""
    ls = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if ls and ls[-1] == "":
        ls.pop()
    return ls


# ---- spec cues --------------------------------------------------------------

CUE_PHRASES = (
    "instead of", "no longer", "falls back", "another", "injectable", "previously",
    "замість", "більше не", "повертається до", "інший",
)
CUE_RE = re.compile(r"(?<!\w)(" + "|".join(re.escape(p).replace("\\ ", r"\s+") for p in CUE_PHRASES) + r")(?!\w)",
                    re.IGNORECASE)
MAX_CUE_LINE = 400
_HEADING = re.compile(r"^#+\s")
_OOS_HEADING = re.compile(r"^#+\s*out of scope", re.IGNORECASE)
_OOS_LINE = re.compile(r"^\s*[-*]\s*out of scope", re.IGNORECASE)


def find_cues(lines):
    """Return [{line, phrase, text}] for change-wording lines outside Out of scope."""
    out = []
    skipping = False
    for n, ln in enumerate(lines, 1):
        if _HEADING.match(ln):
            skipping = bool(_OOS_HEADING.match(ln))
            continue
        if skipping or _OOS_LINE.match(ln) or len(ln) > MAX_CUE_LINE:
            continue
        m = CUE_RE.search(ln)
        if m:
            out.append({"line": n, "phrase": " ".join(m.group(1).lower().split()),
                        "text": " ".join(ln.split())[:200]})
    return out


_PLACEHOLDERS = {"todo", "tbd", "n/a", "na", "none", "-", "--", "...", "fixme", "xxx",
                 "placeholder", "?", "later", "x"}


def _real_reason(reason):
    if not isinstance(reason, str):
        return False
    r = reason.strip()
    for pre in ("not a change:",):
        if r.lower().startswith(pre):
            r = r[len(pre):].strip()
    return bool(r) and r.lower().strip(" .") not in _PLACEHOLDERS


def unanswered_cues(cues, edits, dismissals):
    """Cues neither cited by a change edit via @spec:N nor dismissed with a real reason."""
    answered = set()
    for e in edits or []:
        if e.get("shape") in CITING:
            mm = _SPEC_REF.match(e.get("ref") or "")
            if mm:
                answered.add(int(mm.group(1)))
    for d in dismissals or []:
        if isinstance(d, dict) and isinstance(d.get("line"), int) and _real_reason(d.get("reason")):
            answered.add(d["line"])
    return [c for c in cues if c["line"] not in answered]


# ---- git base helpers -------------------------------------------------------

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def valid_sha(sha):
    return isinstance(sha, str) and _SHA_RE.match(sha) is not None


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def head_sha(root):
    try:
        r = _git(root, "rev-parse", "HEAD")
    except OSError:
        return None
    s = r.stdout.strip()
    return s if r.returncode == 0 and valid_sha(s) else None


def tracked_dirty(root):
    """Modified tracked files outside docs/ and .code-designer/ ([] when not a git tree)."""
    try:
        r = _git(root, "status", "--porcelain=v1", "-uno")
    except OSError:
        return []
    if r.returncode != 0:
        return []
    out = []
    for ln in r.stdout.splitlines():
        path = ln[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if path.startswith("docs/") or path.startswith(".code-designer/"):
            continue
        out.append(path)
    return out


def extract_base(root, sha, dest):
    """Extract `git archive sha` into dest: files and dirs only, no links/devices/abs/.. members."""
    if not valid_sha(sha):
        raise EditError("base commit must be 40 lowercase hex characters")
    try:
        v = _git(root, "rev-parse", "--verify", sha + "^{commit}")
    except OSError as ex:
        raise EditError("git unavailable: %s" % ex)
    if v.returncode != 0:
        raise EditError("base commit %s is not in the repository" % sha)
    dest = os.path.realpath(str(dest))
    proc = subprocess.Popen(["git", "-C", str(root), "archive", "--format=tar", sha],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
            for m in tf:
                name = m.name
                if name.startswith("/") or "\x00" in name:
                    continue
                parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
                if not parts or ".." in parts:
                    continue
                if not (m.isfile() or m.isdir()):
                    continue
                target = os.path.realpath(os.path.join(dest, *parts))
                if target != dest and not target.startswith(dest + os.sep):
                    continue
                if m.isdir():
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                src = tf.extractfile(m)
                with open(target, "wb") as fh:
                    while True:
                        chunk = src.read(1 << 16)
                        if not chunk:
                            break
                        fh.write(chunk)
    except (tarfile.TarError, OSError) as ex:
        proc.kill()
        raise EditError("could not extract base commit: %s" % ex)
    finally:
        proc.stdout.close()
        err = proc.stderr.read()
        proc.stderr.close()
        proc.wait()
    if proc.returncode != 0:
        raise EditError("git archive failed: %s" % err.decode("utf-8", "replace")[:200])


# ---- Triage section parser --------------------------------------------------

_TRIAGE_H = re.compile(r"^##\s+Triage\s*$")
_H2 = re.compile(r"^##\s+\S")
_VERDICT = re.compile(r"^Verdict:\s*(skip|light|full)\s*$")


def parse_triage_section(text):
    """Return (verdict, signals dict) from the `## Triage` section, or (None, None)."""
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if _TRIAGE_H.match(ln):
            start = i + 1
            break
    if start is None:
        return None, None
    body = []
    for ln in lines[start:]:
        if _H2.match(ln):
            break
        body.append(ln)
    verdict = None
    for ln in body:
        m = _VERDICT.match(ln)
        if m:
            verdict = m.group(1)
            break
    if verdict is None:
        return None, None
    buf = []
    in_json = False
    for ln in body:
        if not in_json and re.match(r"^```\s*json\s*$", ln):
            in_json = True
        elif in_json and ln.startswith("```"):
            break
        elif in_json:
            buf.append(ln)
    try:
        signals = json.loads("\n".join(buf))
    except ValueError:
        return verdict, None
    return verdict, signals if isinstance(signals, dict) else None
