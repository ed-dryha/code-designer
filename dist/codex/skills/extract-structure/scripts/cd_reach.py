#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Per-shape reach heuristics for design triage (pure functions, no CLI, no subprocess).

resolve_target   edit target -> owner type, member, files, declaration lines (raises EditError)
member_callers   distinct files that call the MEMBER (not its type)
case_sites       switches over an enum that the compiler will not flag when a case is added
assumption_reach every reader of an assumption name plus cd_blast.CHECKLIST hits next to them

Every result is a heuristic over text (tagged "heuristic": true); anything uncertain goes
to an `unverified` list with a reason. Output is deterministic: sorted, root-relative paths,
no timestamps. cd_triage imports this module, so it must not import cd_triage.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cd_blast  # noqa: E402
import cd_common  # noqa: E402,F401
import cd_edits  # noqa: E402
import languages  # noqa: E402

EditError = cd_edits.EditError

MAX_FILES = 5000          # files scanned per call
MAX_WALK = 400            # lines walked from a block start
WINDOW = 6                # lines above a site searched for a switch keyword
READER_CAP = 500
MIN_NAME = 4
SHORT_NAME = 6            # member names shorter than this must be tied to the owner type

TYPE_KW = "class|struct|enum|extension|protocol|actor|interface|trait|object|impl|record|type"
SWITCH_RE = re.compile(r"\b(switch|when|match)\b")
TEST_DIR_RE = re.compile(r"(^|/)(tests?|specs?|__tests__|[A-Za-z]*Tests?)(/|\.|$)")
TEST_FILE_RE = re.compile(
    r"(Tests?\.[A-Za-z0-9]+$|_tests?\.[A-Za-z0-9]+$|\.(spec|test)\.[A-Za-z0-9]+$|(^|/)test_[^/]*$)")
_TARGET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_MODS = (r"(?:(?:public|private|protected|internal|fileprivate|open|static|final|readonly|override|"
         r"lazy|abstract|export|data|const|async)\s+)")

# ASSUMPTION A7 (LOW confidence, calibration input, not fact): these compilers reject a switch
# that misses a case unless it has a catch-all; the other languages silently fall through.
EXHAUSTIVE_LANGS = frozenset({"swift", "kotlin", "rust"})
EXT_FALLBACK = {".swift": "swift"}
CATCH_ALL = {
    "swift": (re.compile(r"(?<!@unknown )\bdefault\s*:"), "default:"),
    "kotlin": (re.compile(r"\belse\s*->"), "else ->"),
    "rust": (re.compile(r"(?<![A-Za-z0-9_])_\s*=>"), "_ =>"),
    "csharp": (re.compile(r"\bdefault\s*:|(?<![A-Za-z0-9_])_\s*=>"), "default:"),
    "python": (re.compile(r"^\s*case\s+_\s*:"), "case _:"),
    "ruby": (re.compile(r"^\s*else\b"), "else"),
}
_DEFAULT = (re.compile(r"\bdefault\s*:"), "default:")   # java, ts, js, go, php, c-like
INDENT_LANGS = frozenset({"python", "ruby"})


def is_test_path(path):
    return bool(TEST_DIR_RE.search(path) or TEST_FILE_RE.search(path))


# ------------------------------------------------------------------ file access

def _word(name):
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")


def _files(model):
    """Root-relative paths named by the model (symbols, coverage, unavailable), sorted."""
    out = set()
    for s in model.get("symbols") or []:
        if isinstance(s, dict) and isinstance(s.get("file"), str):
            out.add(s["file"])
    cov = model.get("coverage") or {}
    for f in cov.get("files") or []:
        if isinstance(f, dict) and isinstance(f.get("path"), str):
            out.add(f["path"])
    for u in cov.get("unavailable") or []:
        if isinstance(u, dict) and isinstance(u.get("files"), list):
            out.update(x for x in u["files"] if isinstance(x, str))
    safe = [p for p in out if p and not os.path.isabs(p) and ".." not in p.replace("\\", "/").split("/")]
    return sorted(safe)[:MAX_FILES]


def _lines(root, rel, cache):
    return cd_blast._read_lines(root, rel, cache)


def _lang(path):
    ext = os.path.splitext(path)[1].lower()
    return languages.language_for(path) or EXT_FALLBACK.get(ext)


_STR_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def _code(text):
    """Line with string literals and trailing // comments removed (for brace counting)."""
    t = _STR_RE.sub('""', text)
    i = t.find("//")
    return t[:i] if i >= 0 else t


def _indent(text):
    return len(text) - len(text.lstrip())


def _block_end(lines, i, cap=MAX_WALK, indent_lang=False):
    """(end_index, ok) of the block opened on lines[i]. ok False when braces never balanced."""
    n = len(lines)
    first = _code(lines[i]) if len(lines[i]) <= cd_blast.MAX_LINE else ""
    if "{" not in first and (indent_lang or first.rstrip().endswith(":")):
        base = _indent(lines[i])
        end = i
        for j in range(i + 1, min(n, i + cap + 1)):
            if not lines[j].strip():
                continue
            if _indent(lines[j]) <= base:
                if indent_lang and lines[j].strip() == "end" and _indent(lines[j]) == base:
                    return j, True
                return end, True
            end = j
        return end, True
    depth, opened = 0, False
    for j in range(i, min(n, i + cap + 1)):
        t = _code(lines[j]) if len(lines[j]) <= cd_blast.MAX_LINE else ""
        for ch in t:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            return j, True
        if not opened and j > i + 1:
            return i, True          # declaration without a body
    return min(n - 1, i + cap), False


# ------------------------------------------------------------------ declarations

def _type_decl(name):
    return re.compile(r"\b(?:%s)\s+%s(?![A-Za-z0-9_])" % (TYPE_KW, re.escape(name)))


def _is_member_decl(text, name):
    """True when `text` declares a member called `name` (heuristic, many languages)."""
    if len(text) > cd_blast.MAX_LINE:
        return False
    nm = re.escape(name)
    if name == "init":
        return bool(re.search(r"\binit\s*[(?!<]", text))
    if re.search(r"\b(?:var|let|func|val|const|def|fn|property|fun|typealias)\s+%s(?![A-Za-z0-9_])" % nm, text):
        return True
    m = re.search(r"\bcase\s+(.*)$", text)
    if m and not text.rstrip().endswith(":") and "->" not in text and "=>" not in text:
        for part in m.group(1).split(","):
            if re.match(r"\s*%s(?![A-Za-z0-9_])" % nm, part) and not part.lstrip().startswith("."):
                return True
    if re.match(r"^\s*(?:%s)*(?:[\w<>\[\]?.,]+\s+)?%s\s*[:=;]" % (_MODS, nm), text):
        return True
    if re.search(r"\bself\.%s\s*=" % nm, text):
        return True
    if re.match(r"^\s*%s+[\w<>\[\]?.,]+\s+%s\s*\(" % (_MODS, nm), text):
        return True
    return bool(re.match(r"^\s*(?:async\s+)?%s\s*\([^)]*\)\s*(?::\s*[\w<>\[\]?.]+\s*)?\{" % nm, text))


def _owner_blocks(model, root, owner, files, cache):
    """[(file, start_line, end_line)] 1-based blocks declaring type `owner`."""
    blocks = []
    seen = set()
    for s in model.get("symbols") or []:
        if s.get("name") == owner and s.get("kind") in cd_blast.TYPE_KINDS and isinstance(s.get("span"), dict):
            key = (s["file"], s["span"]["startLine"])
            if key not in seen:
                seen.add(key)
                blocks.append((s["file"], s["span"]["startLine"], s["span"]["endLine"]))
    rx = _type_decl(owner)
    for rel in files:
        ls = _lines(root, rel, cache)
        if not ls:
            continue
        il = _lang(rel) in INDENT_LANGS
        for i, t in enumerate(ls):
            if len(t) <= cd_blast.MAX_LINE and rx.search(t) and (rel, i + 1) not in seen:
                seen.add((rel, i + 1))
                end, _ok = _block_end(ls, i, indent_lang=il)
                blocks.append((rel, i + 1, end + 1))
    return sorted(blocks)


def resolve_target(model, root, target):
    """Resolve "Owner.member", a bare type/member name or a model symbol id.

    Returns {owner, member, files, decl_lines, model_symbol, blocks}. Raises EditError for
    anything that cannot be found, so a typo never turns into an empty reach.
    """
    root = os.path.realpath(root)
    symbols = [s for s in model.get("symbols") or [] if isinstance(s, dict)]
    by_id = {s.get("id"): s for s in symbols}
    cache = {}
    files = _files(model)
    sym = by_id.get(target) if isinstance(target, str) else None
    owner = member = None
    if sym is not None:
        if sym.get("kind") in cd_blast.TYPE_KINDS:
            owner = sym["name"]
        else:
            member = sym["name"]
            par = by_id.get(sym.get("parent"))
            owner = par["name"] if par else None
    else:
        if not isinstance(target, str) or "#" in target or "/" in target or not _TARGET_RE.match(target):
            raise EditError("unknown target: %r" % (target,))
        parts = target.split(".")
        if len(parts) == 1:
            owner = member = None
            bare = parts[0]
        else:
            owner, member = parts[-2], parts[-1]
            bare = member
        if len(bare) < MIN_NAME:
            raise EditError("target name too short to search reliably, use a symbol id: %s" % target)
    if sym is None and member is None and owner is None:
        # bare name: a type first, otherwise a free member
        blocks = _owner_blocks(model, root, bare, files, cache)
        if blocks:
            owner = bare
        else:
            member = bare
    if owner is not None:
        blocks = _owner_blocks(model, root, owner, files, cache)
        if not blocks:
            raise EditError("unknown target: owner %s not found (%s)" % (owner, target))
        decl = []
        if member is not None:
            for s in symbols:
                par = by_id.get(s.get("parent"))
                if s.get("name") == member and par and par.get("name") == owner and isinstance(s.get("span"), dict):
                    decl.append((s["file"], s["span"]["startLine"]))
            for rel, a, b in blocks:
                ls = _lines(root, rel, cache) or []
                for n in range(a, min(b, len(ls)) + 1):
                    if _is_member_decl(ls[n - 1], member):
                        decl.append((rel, n))
            if not decl:
                raise EditError("unknown target: member %s not found in %s" % (member, owner))
        else:
            decl = [(rel, a) for rel, a, _b in blocks]
        ofiles = sorted({rel for rel, _a, _b in blocks})
        msym = None
        for s in symbols:
            par = by_id.get(s.get("parent"))
            if member and s.get("name") == member and par and par.get("name") == owner:
                msym = s["id"]
                break
            if not member and s.get("name") == owner and s.get("kind") in cd_blast.TYPE_KINDS:
                msym = s["id"]
                break
        return {"owner": owner, "member": member, "files": ofiles,
                "decl_lines": sorted(set(decl)), "model_symbol": msym,
                "blocks": [list(b) for b in blocks]}
    # free member
    decl = []
    for rel in files:
        ls = _lines(root, rel, cache)
        for n, t in enumerate(ls or [], 1):
            if _is_member_decl(t, member):
                decl.append((rel, n))
    msym = next((s["id"] for s in symbols if s.get("name") == member and s.get("kind") not in cd_blast.TYPE_KINDS), None)
    if not decl and msym is None:
        raise EditError("unknown target: %s" % target)
    return {"owner": None, "member": member, "files": sorted({r for r, _ in decl}),
            "decl_lines": sorted(set(decl)), "model_symbol": msym, "blocks": []}


# ------------------------------------------------------------------ member callers

def member_callers(model, root, resolved):
    """Distinct files that call the member (or reference the type when member is None)."""
    root = os.path.realpath(root)
    cache = {}
    name = resolved.get("member") or resolved.get("owner")
    owner = resolved.get("owner")
    member = resolved.get("member")
    decl = {(f, n) for f, n in resolved.get("decl_lines") or []}
    ofiles = set(resolved.get("files") or [])
    word = _word(name)
    call = re.compile(r"\.%s(?![A-Za-z0-9_])|(?<![A-Za-z0-9_.])%s\s*\(" % (re.escape(name), re.escape(name)))
    owner_rx = _word(owner) if owner and member else None
    tie_owner = bool(owner_rx and len(name) < SHORT_NAME)
    matched = []
    for rel in _files(model):
        ls = _lines(root, rel, cache)
        if not ls:
            continue
        rx = word if (rel in ofiles or not member) else call
        hit = False
        for n, t in enumerate(ls, 1):
            if len(t) > cd_blast.MAX_LINE or (rel, n) in decl:
                continue
            if rx.search(t):
                hit = True
                break
        if not hit:
            continue
        if tie_owner and rel not in ofiles and not any(owner_rx.search(t) for t in ls if len(t) <= cd_blast.MAX_LINE):
            continue
        matched.append(rel)
    non_test = sorted(f for f in matched if not is_test_path(f))
    return {"total": len(matched), "nonTest": len(non_test), "files": non_test, "heuristic": True}


# ------------------------------------------------------------------ case sites

def _enum_cases(root, resolved, cache):
    names = set()
    for rel, a, b in resolved.get("blocks") or []:
        ls = _lines(root, rel, cache) or []
        for n in range(a, min(b, len(ls)) + 1):
            t = ls[n - 1]
            if len(t) > cd_blast.MAX_LINE:
                continue
            m = re.search(r"\bcase\s+(.*)$", t)
            if n == a and "{" in t and _lang(rel) not in (None, "swift", "python"):
                inner = t.split("{", 1)[1].split("}", 1)[0]       # one-line enum body
                for part in inner.split(","):
                    mm = re.match(r"\s*([A-Z][A-Za-z0-9_]*)\s*(?:\(.*\))?\s*;?\s*$", part)
                    if mm:
                        names.add(mm.group(1))
            if m and not t.rstrip().endswith(":") and "->" not in t:
                for part in m.group(1).split(","):
                    mm = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", part)
                    if mm and not part.lstrip().startswith("."):
                        names.add(mm.group(1))
            elif _lang(rel) in ("kotlin", "rust", "java", "csharp") and n > a:
                mm = re.match(r"^\s*([A-Z][A-Za-z0-9_]*)\s*(?:\(.*\))?\s*[,;]?\s*$", t)
                if mm:
                    names.add(mm.group(1))
    return sorted(names)


def _site_pairs(dependents):
    out = set()
    for d in dependents or []:
        if isinstance(d, dict) and isinstance(d.get("file"), str):
            out.add((d["file"], d.get("line")))
        elif isinstance(d, (tuple, list)) and len(d) >= 2 and isinstance(d[0], str):
            out.add((d[0], d[1]))
        elif isinstance(d, str):
            out.add((d, None))
    return out


def case_sites(root, resolved, dependents=None, model=None):
    """Switches over the enum that carry a catch-all (or any switch where the compiler does not
    check exhaustiveness). Uncertain switches go to `unverified`, never dropped."""
    root = os.path.realpath(root)
    cache = {}
    enum_name = resolved.get("owner") or resolved.get("member")
    names = [enum_name] + _enum_cases(root, resolved, cache)
    name_rx = [_word(n) for n in names if n and len(n) >= 2]
    files = set(resolved.get("files") or [])
    files |= {f for f, _ln in _site_pairs(dependents)}
    if dependents is None and model is not None:
        files |= set(_files(model))
    sites, unverified, seen = [], [], set()
    for rel in sorted(files):
        if is_test_path(rel):
            continue
        ls = _lines(root, rel, cache)
        if not ls:
            continue
        lang = _lang(rel)
        indent_lang = lang in INDENT_LANGS
        rx, label = CATCH_ALL.get(lang, _DEFAULT)
        for i, t in enumerate(ls):
            if len(t) > cd_blast.MAX_LINE or not SWITCH_RE.search(_code(t)) or (rel, i + 1) in seen:
                continue
            seen.add((rel, i + 1))
            code = _code(t)
            expr = code[SWITCH_RE.search(code).end():]
            end, ok = _block_end(ls, i, indent_lang=indent_lang)
            if lang == "python" and not expr.rstrip().endswith(":"):
                continue            # not a match statement
            body = ls[i + 1:end + 1]
            labels = []
            depth = 1
            for bt in body:
                if len(bt) > cd_blast.MAX_LINE:
                    continue
                if indent_lang or depth == 1:
                    labels.append(bt)
                if not indent_lang:
                    ct = _code(bt)
                    depth += ct.count("{") - ct.count("}")
            tied = any(r.search(expr) for r in name_rx) or any(r.search(x) for x in labels for r in name_rx)
            if not tied:
                continue
            tuple_sw = bool(re.match(r"\s*\(.*,.*\)\s*\{?\s*$", expr)) or (indent_lang and "," in expr)
            if tuple_sw:
                unverified.append({"file": rel, "line": i + 1, "reason": "tuple switch: cannot tie cases to the enum"})
                continue
            if not ok:
                unverified.append({"file": rel, "line": i + 1,
                                   "reason": "block end not found within %d lines" % MAX_WALK})
                continue
            found = None
            for x in labels:
                if rx.search(_code(x) if not indent_lang else x):
                    found = label
                    break
            if found or lang not in EXHAUSTIVE_LANGS:
                sites.append({"file": rel, "line": i + 1, "catchAll": found})
    sites.sort(key=lambda s: (s["file"], s["line"]))
    unverified.sort(key=lambda s: (s["file"], s["line"], s["reason"]))
    return {"sites": sites, "unverified": unverified, "heuristic": True}


# ------------------------------------------------------------------ assumption reach

def assumption_reach(model, root, name):
    """Every reader of the assumption name plus checklist idioms on or next to those lines."""
    root = os.path.realpath(root)
    if isinstance(name, dict):
        name = name.get("member") or name.get("owner")
    if not isinstance(name, str) or not _TARGET_RE.match(name):
        raise EditError("unknown target: %r" % (name,))
    name = name.split(".")[-1]
    if len(name) < MIN_NAME:
        raise EditError("name too short to search reliably, use a symbol id: %s" % name)
    word, tdecl = _word(name), _type_decl(name)
    cache = {}
    readers, truncated = [], False
    for rel in _files(model):
        ls = _lines(root, rel, cache)
        for n, t in enumerate(ls or [], 1):
            if len(t) > cd_blast.MAX_LINE or not word.search(t):
                continue
            if _is_member_decl(t, name) or tdecl.search(t):
                continue
            if len(readers) >= READER_CAP:
                truncated = True
                continue
            readers.append({"file": rel, "line": n})
    checks = set()
    for r in readers:
        ls = _lines(root, r["file"], cache)
        for n in (r["line"] - 1, r["line"], r["line"] + 1):
            if not (1 <= n <= len(ls)) or len(ls[n - 1]) > cd_blast.MAX_LINE:
                continue
            for cat, crx in cd_blast.CHECKLIST:
                if crx.search(ls[n - 1]):
                    checks.add((r["file"], n, cat))
    readers.sort(key=lambda d: (d["file"], d["line"]))
    return {"readers": readers,
            "checklist": [{"file": f, "line": n, "category": c} for f, n, c in sorted(checks)],
            "files": sorted({r["file"] for r in readers}),
            "truncated": truncated, "heuristic": True}
