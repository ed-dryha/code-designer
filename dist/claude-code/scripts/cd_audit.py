#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Declarations-vs-diff audit for a recorded schema-2 Triage section.

Usage: cd_audit.py [audit] --root DIR --doc DOC [--base SHA] [--head REV]
Prints JSON {status, base, head, declared, derived, mismatches, needsJudgment, limits}.
Exit 0 whenever analysis succeeds, 2 on usage/IO errors. Never writes files.

Shapes are derived from `git diff` text without a grammar: member attribution is
indentation based, so body changes are listed under needsJudgment, never scored as errors
unless no declaration names their owner, member or file (undeclared-edit).
derive_shapes() is reused by the replay harness for oracle drafts.
cd_triage imports this module, so it must not import cd_triage.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_common  # noqa: E402
import cd_edits  # noqa: E402
import cd_reach  # noqa: E402

EditError = cd_edits.EditError

TIMEOUT = 60
LIMIT_NOTE = "no grammar: member attribution is indentation based"
EXCLUDED_EXT = frozenset({".md", ".json", ".plist", ".xcstrings", ".yml", ".yaml", ".txt"})
MAX_DIFF = cd_common.MAX_BYTES * 8

_MODS = (r"(?:(?:public|private|internal|fileprivate|open|static|final|override|async|pub|export|"
         r"abstract|protected|mutating|lazy|default|const|@\w+(?:\([^)]*\))?)\s+)*")
DECL_RE = re.compile(r"^\s*" + _MODS + r"(func|var|let|init|subscript|def|fn|val|const|class|struct|"
                     r"enum|protocol)\b\s*([A-Za-z_]\w*)?")
TYPE_RE = re.compile(r"^\s*" + _MODS + r"(class|struct|enum|extension|protocol|actor|impl|object)\b"
                     r"\s*([A-Za-z_]\w*)?")
FUNC_KINDS = frozenset({"func", "def", "fn", "init", "subscript"})
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
CASE_RE = re.compile(r"^\s*case\s+(.+?)\s*$")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ------------------------------------------------------------------ git access

def _git(root, *args):
    """Run git with an argv list (never a shell); returns stdout text or raises EditError."""
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as ex:
        raise EditError("git failed: %s" % ex)
    out = r.stdout[:MAX_DIFF].decode("utf-8", "replace")
    if r.returncode != 0:
        raise EditError("git %s failed: %s" % (args[0], r.stderr.decode("utf-8", "replace")[:200].strip()))
    return out


def _safe_path(p):
    return (isinstance(p, str) and p and "\x00" not in p and not p.startswith("-")
            and ".." not in p.replace("\\", "/").split("/"))


def _resolve_rev(root, rev):
    """Resolve a revision to a 40-hex sha; rejects option-looking and malformed input."""
    if not isinstance(rev, str) or not rev or rev.startswith("-") or "\x00" in rev or "\n" in rev:
        raise EditError("unsafe revision: %r" % (rev if isinstance(rev, str) else rev))
    sha = _git(root, "rev-parse", "--verify", "--end-of-options", rev + "^{commit}").strip()
    if not cd_edits.valid_sha(sha):
        raise EditError("revision does not resolve to a commit: %s" % rev[:60])
    return sha


# ------------------------------------------------------------------ line helpers

def _indent(line):
    return len(line) - len(line.lstrip(" \t"))


def _enclosing(lines, idx, indent):
    """Chain of less-indented declarations above 0-based idx: [(kind, name, is_type)] nearest first."""
    chain = []
    thr = indent
    for i in range(min(idx, len(lines)) - 1, -1, -1):
        ln = lines[i]
        if not ln.strip() or thr <= 0:
            if thr <= 0:
                break
            continue
        ind = _indent(ln)
        if ind >= thr:
            continue
        thr = ind
        t = TYPE_RE.match(ln)
        if t:
            chain.append((t.group(1), t.group(2) or "", True))
            continue
        d = DECL_RE.match(ln)
        if d:
            kind, name = d.group(1), d.group(2) or ("init" if d.group(1) == "init" else "")
            chain.append((kind, name, kind in ("class", "struct", "enum", "protocol")))
        else:
            chain.append(("block", "", False))
    return chain


def _owner(chain):
    for kind, name, is_type in chain:
        if is_type or kind == "extension":
            return name
    return None


def _member_of(chain):
    for kind, name, _ in chain:
        if kind in FUNC_KINDS:
            return name
    return None


def _case_idents(text):
    """Case identifiers in `case a, b(Int), c = 1` style text (enum cases)."""
    out = []
    for part in re.split(r"\bcase\b", text):
        part = re.split(r"[;}]", part)[0]
        depth, cur, items = 0, "", []
        for ch in part:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            if ch == "," and depth == 0:
                items.append(cur)
                cur = ""
            else:
                cur += ch
        items.append(cur)
        for it in items:
            m = IDENT_RE.match(it.strip())
            if m:
                out.append(m.group(0))
    return out


def _params(line, name):
    """Top-level parameter strings of the first `name(...)` on the line, or None."""
    m = re.search(r"\b" + re.escape(name) + r"\s*\(", line)
    if not m:
        return None
    depth, cur, items = 1, "", []
    for ch in line[m.end():]:
        if ch in "([<":
            depth += 1
        elif ch in ")]>":
            depth -= 1
            if depth == 0:
                break
        if ch == "," and depth == 1:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    else:
        return None
    if cur.strip():
        items.append(cur.strip())
    return items


def _param_name(p):
    head = re.split(r"[:=]", p, 1)[0].split()
    return head[-1] if head else p


# ------------------------------------------------------------------ diff parsing

def _parse_name_status(text):
    out = []
    for ln in text.splitlines():
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        st = parts[0][:1]
        out.append((st, parts[-1], parts[1] if st == "R" else None))
    return out


def _parse_diff(text):
    """{path: [hunk]} with hunk = {new_start, new_len, removed:[str], added:[(lineno,str)]}."""
    files, cur, hunk = {}, None, None
    for ln in text.split("\n"):
        if ln.startswith("diff --git "):
            cur, hunk = None, None
        elif ln.startswith("+++ "):
            p = ln[4:].split("\t")[0]
            cur = p[2:] if p.startswith("b/") else None
            if cur is not None:
                files.setdefault(cur, [])
        elif cur is not None and ln.startswith("@@"):
            m = HUNK_RE.match(ln)
            if m:
                hunk = {"new_start": int(m.group(3)),
                        "new_len": int(m.group(4)) if m.group(4) is not None else 1,
                        "removed": [], "added": []}
                files[cur].append(hunk)
        elif hunk is not None and ln.startswith("-") and not ln.startswith("---"):
            hunk["removed"].append(ln[1:])
        elif hunk is not None and ln.startswith("+") and not ln.startswith("+++"):
            hunk["added"].append((hunk["new_start"] + len(hunk["added"]), ln[1:]))
    return files


def _skippable(line):
    s = line.strip()
    return not s or s.startswith("//") or s.startswith("*") or s.startswith("/*")


def _hunk_shapes(path, head_lines, hunk, add):
    """Classify one hunk's lines; calls add(kind, owner, member, confidence, **extra)."""
    removed, added = hunk["removed"], hunk["added"]
    consumed_a, consumed_r = set(), set()
    rem_decl = {}
    for i, ln in enumerate(removed):
        d = DECL_RE.match(ln)
        if d:
            rem_decl.setdefault(d.group(2) or d.group(1), i)

    def ctx(lineno, text):
        idx = lineno - 1
        return _enclosing(head_lines, idx, _indent(text))

    # single-line enum rewrite
    for ai, (lineno, text) in enumerate(added):
        m = re.search(r"\benum\s+([A-Za-z_]\w*)", text)
        if not m or "case" not in text:
            continue
        for ri, rtext in enumerate(removed):
            rm = re.search(r"\benum\s+([A-Za-z_]\w*)", rtext)
            if ri in consumed_r or not rm or rm.group(1) != m.group(1):
                continue
            old, new = set(_case_idents(rtext)), _case_idents(text)
            if old <= set(new) and set(new) - old:
                for ident in new:
                    if ident not in old:
                        add("add-case", m.group(1), ident, "mechanical", file=path)
                consumed_a.add(ai)
                consumed_r.add(ri)
                break

    # defaulted parameter additions
    for ai, (lineno, text) in enumerate(added):
        d = DECL_RE.match(text)
        if ai in consumed_a or not d or d.group(1) not in FUNC_KINDS:
            continue
        name = d.group(2) or "init"
        ri = rem_decl.get(name)
        if ri is None or ri in consumed_r:
            continue
        op, np = _params(removed[ri], name), _params(text, name)
        if op is None or np is None:
            continue
        extra = [p for p in np if p not in op]
        if all(p in np for p in op) and extra and all("=" in p for p in extra):
            owner = _owner(ctx(lineno, text))
            for p in extra:
                add("add-param", owner, name, "mechanical", file=path, new=_param_name(p))
            consumed_a.add(ai)
            consumed_r.add(ri)

    for ai, (lineno, text) in enumerate(added):
        if ai in consumed_a or _skippable(text):
            continue
        chain = ctx(lineno, text)
        parent = chain[0] if chain else None
        cm = CASE_RE.match(text)
        d = DECL_RE.match(text)
        if cm and not text.rstrip().endswith(":") and parent and parent[0] == "enum":
            for ident in _case_idents(text):
                add("add-case", parent[1], ident, "mechanical", file=path)
        elif d and (parent is None or parent[2] or parent[0] == "extension") \
                and (d.group(2) or d.group(1)) not in rem_decl:
            add("add-member", _owner(chain), d.group(2) or d.group(1), "mechanical", file=path)
        else:
            add("body-changed", _owner(chain), _member_of(chain), "judgment", file=path, removed=0)

    for ri, text in enumerate(removed):
        if ri in consumed_r or _skippable(text):
            continue
        anchor = hunk["new_start"] if not hunk["added"] else hunk["added"][0][0]
        chain = _enclosing(head_lines, anchor, _indent(text))
        add("body-changed", _owner(chain), _member_of(chain), "judgment", file=path, removed=1)


def derive_shapes(root, base, head):
    """Mechanical + judgment shapes of `git diff base head` (both must be 40-hex shas)."""
    for s in (base, head):
        if not cd_edits.valid_sha(s):
            raise EditError("commit must be 40 lowercase hex characters")
    ns = _parse_name_status(_git(root, "diff", "--no-color", "-M", "--name-status", base, head))
    shapes, files, new_files, touched, added_ids = {}, [], [], set(), set()
    limits = [LIMIT_NOTE]

    def keep(path):
        ext = os.path.splitext(path)[1].lower()
        return _safe_path(path) and ext not in EXCLUDED_EXT and not cd_reach.is_test_path(path)

    paths = []
    for st, path, _old in ns:
        if st == "A":
            new_files.append(path)
        if not keep(path):
            continue
        files.append({"path": path, "status": st})
        if st == "A":
            shapes[("new-file", path, None, None, None)] = {
                "kind": "new-file", "file": path, "owner": None, "member": None,
                "confidence": "mechanical"}
            touched.add(os.path.splitext(os.path.basename(path))[0])
        elif st in ("M", "R"):
            paths.append(path)
    if paths:
        diff = _git(root, "diff", "--no-color", "--unified=0", "-M", base, head, "--", *paths)
        if len(diff) >= MAX_DIFF:
            limits.append("diff truncated at %d bytes" % MAX_DIFF)
        parsed = _parse_diff(diff)
        for path in sorted(parsed):
            if path not in paths:
                continue
            touched.add(os.path.splitext(os.path.basename(path))[0])
            try:
                head_lines = _git(root, "show", "%s:%s" % (head, path)).split("\n")
            except EditError:
                head_lines = []

            def add(kind, owner, member, conf, file=path, **extra):
                key = (kind, file, owner, member, extra.get("new"))
                cur = shapes.get(key)
                if cur is None:
                    cur = {"kind": kind, "file": file, "owner": owner, "member": member,
                           "confidence": conf}
                    if "new" in extra:
                        cur["new"] = extra["new"]
                    if kind == "body-changed":
                        cur["removed"] = 0
                    shapes[key] = cur
                if kind == "body-changed" and extra.get("removed"):
                    cur["removed"] += 1

            for hunk in parsed[path]:
                for _lineno, text in hunk["added"]:
                    added_ids.update(IDENT_RE.findall(text))
                for text in hunk["removed"] + [t for _n, t in hunk["added"]]:
                    touched.update(IDENT_RE.findall(text))
                _hunk_shapes(path, head_lines, hunk, add)
    for s in shapes.values():
        for k in ("owner", "member"):
            if s.get(k):
                touched.add(s[k])
    out = sorted(shapes.values(), key=lambda s: (s["file"], s["kind"], s["owner"] or "",
                                                  s["member"] or "", s.get("new") or ""))
    return {"files": sorted(files, key=lambda f: f["path"]), "shapes": out, "limits": limits,
            "newFiles": sorted(new_files), "touched": sorted(touched)[:5000],
            "added": sorted(added_ids)[:5000]}


# ------------------------------------------------------------------ audit

def _names(edit):
    parts = set(p for p in re.split(r"[./#]", edit.get("target") or "") if p)
    if edit.get("new"):
        parts.add(edit["new"])
    return parts


def _norm(p):
    p = str(p).replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def audit(root, doc_text, base=None, head="HEAD"):
    result = {"status": "ok", "base": None, "head": None, "declared": [], "derived": [],
              "mismatches": [], "needsJudgment": [], "limits": []}
    verdict, signals = cd_edits.parse_triage_section(doc_text)
    if signals is None:
        result["status"] = "no-triage"
        return result
    inputs = signals.get("inputs") if isinstance(signals.get("inputs"), dict) else {}
    if signals.get("schema") != 2 or not isinstance(inputs.get("edits"), list):
        result["status"] = "unsupported-schema"
        result["limits"].append("only schema-2 Triage sections can be audited")
        return result
    base = base or inputs.get("base")
    if not base or base == "none":
        result["status"] = "no-base"
        return result
    base_sha = base if cd_edits.valid_sha(base) else None
    if base_sha is None:
        raise EditError("base commit must be 40 lowercase hex characters")
    base_sha = _resolve_rev(root, base_sha)
    head_sha = _resolve_rev(root, head)
    result["base"], result["head"] = base_sha, head_sha
    edits = [e for e in inputs["edits"] if isinstance(e, dict)]
    result["declared"] = edits
    d = derive_shapes(root, base_sha, head_sha)
    result["derived"] = d["shapes"]
    result["limits"] = d["limits"]
    mism = result["mismatches"]
    names = [_names(e) for e in edits]
    covered_names = set().union(*names) if names else set()

    def covered(s):
        stem = os.path.splitext(os.path.basename(s["file"]))[0]
        return bool(({s["owner"], s["member"], stem} - {None}) & covered_names)

    for s in d["shapes"]:
        if s["kind"] == "new-file":
            continue
        if s["kind"] == "body-changed" and covered(s):
            result["needsJudgment"].append({"file": s["file"], "owner": s["owner"],
                                            "member": s["member"]})
        elif not covered(s):
            mism.append({"class": "undeclared-edit", "file": s["file"], "owner": s["owner"],
                         "member": s["member"], "kind": s["kind"]})
    touched = set(d["touched"])
    added = set(d["added"])
    for e, nm in zip(edits, names):
        comps = [p for p in re.split(r"[./#]", e.get("target") or "") if p]
        last = comps[-1] if comps else None
        probe = {last, e.get("new")} - {None}
        if not (probe & touched or (nm & touched)):
            mism.append({"class": "declared-no-diff", "target": e.get("target"),
                         "shape": e.get("shape")})
            continue
        if e.get("shape") in cd_edits.ADDITIONS:
            for s in d["shapes"]:
                if (s["kind"] == "body-changed" and s.get("removed")
                        and (s["owner"] in comps or s["member"] in comps)):
                    mism.append({"class": "shape-mismatch", "target": e.get("target"),
                                 "shape": e.get("shape"), "file": s["file"],
                                 "detail": "body line removed or modified in the declared member"})
                    break
        elif e.get("shape") == "body-new-inputs" and e.get("ref") not in added:
            mism.append({"class": "shape-mismatch", "target": e.get("target"),
                         "shape": "body-new-inputs",
                         "detail": "@%s does not appear in added lines" % e.get("ref")})
    declared_new = {_norm(p) for p in (inputs.get("newPaths") or []) if isinstance(p, str)}
    actual_new = {_norm(p) for p in d["newFiles"]}
    for p in sorted(declared_new - actual_new):
        if not cd_reach.is_test_path(p):
            mism.append({"class": "new-path-mismatch", "path": p, "detail": "declared but not added"})
    for p in sorted(actual_new - declared_new):
        if keep_source(p):
            mism.append({"class": "new-path-mismatch", "path": p, "detail": "added but not declared"})
    result["needsJudgment"].sort(key=lambda x: (x["file"], x["owner"] or "", x["member"] or ""))
    mism.sort(key=lambda m: json.dumps(m, sort_keys=True))
    return result


def keep_source(path):
    ext = os.path.splitext(path)[1].lower()
    return _safe_path(path) and ext not in EXCLUDED_EXT and not cd_reach.is_test_path(path)


# ------------------------------------------------------------------ cli

def _read_doc(root, doc):
    full = os.path.realpath(doc if os.path.isabs(doc) else os.path.join(root, doc))
    if full != root and not full.startswith(root + os.sep):
        raise EditError("--doc escapes root: %s" % doc)
    with open(full, "rb") as fh:
        return fh.read(cd_common.MAX_BYTES).decode("utf-8", "replace")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "audit":
        argv = argv[1:]
    ap = argparse.ArgumentParser(prog="cd_audit.py", description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--base")
    ap.add_argument("--head", default="HEAD")
    a = ap.parse_args(argv)
    try:
        root = os.path.realpath(a.root)
        if not os.path.isdir(root):
            raise EditError("--root is not a directory: %s" % a.root)
        text = _read_doc(root, a.doc)
        out = audit(root, text, base=a.base, head=a.head)
    except (EditError, OSError, ValueError) as ex:
        print("error: %s" % ex, file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
