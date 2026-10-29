"""cd_reach: target resolution, member callers, enum case sites, assumption reach."""
import json
import os

import pytest

import cd_reach
from cd_edits import EditError


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return rel


def model_for(files):
    return {"schemaVersion": 1, "symbols": [],
            "coverage": {"files": [], "unavailable": [
                {"language": "swift", "files": sorted(files), "reason": "no-grammar"}]}}


APPSTATE = """final class AppState {
    var placeResolver: Int = 0
    var mapCoverage: Bool = false
    func load() {}
}
"""
VIEW = "func show(s: AppState) { s.placeResolver = 1 }\n"


@pytest.fixture()
def hub(tmp_path):
    files = [
        write(tmp_path, "App/AppState.swift", APPSTATE),
    ]
    for i in range(10):
        files.append(write(tmp_path, "App/V%d.swift" % i, "func show%d(s: AppState) { s.placeResolver = %d }\n" % (i, i)))
    return tmp_path, model_for(files)


# ---------------------------------------------------------------- resolve

def test_resolve_member(hub):
    root, model = hub
    r = cd_reach.resolve_target(model, root, "AppState.mapCoverage")
    assert r["owner"] == "AppState" and r["member"] == "mapCoverage"
    assert r["files"] == ["App/AppState.swift"]
    assert r["decl_lines"] == [("App/AppState.swift", 3)]


def test_resolve_member_past_walk_cap_in_long_owner(tmp_path):
    body = "".join("    var f%d: Int = 0\n" % i for i in range(600))
    src = "final class Owner {\n" + body + "    func lateMember() {}\n}\n"
    late = src.splitlines().index("    func lateMember() {}") + 1
    assert late > cd_reach.MAX_WALK + 8
    f = write(tmp_path, "Owner.swift", src)
    r = cd_reach.resolve_target(model_for([f]), tmp_path, "Owner.lateMember")
    assert r["decl_lines"] == [("Owner.swift", late)]
    assert r["blocks"][0][2] >= late


def test_resolve_bare_type_and_free_member(tmp_path):
    f1 = write(tmp_path, "a.swift", "struct Place { var name = 1 }\nfunc makeThing() {}\n")
    model = model_for([f1])
    t = cd_reach.resolve_target(model, tmp_path, "Place")
    assert t["owner"] == "Place" and t["member"] is None
    m = cd_reach.resolve_target(model, tmp_path, "makeThing")
    assert m["owner"] is None and m["member"] == "makeThing"


def test_unknown_owner_raises(hub):
    root, model = hub
    with pytest.raises(EditError, match="unknown target"):
        cd_reach.resolve_target(model, root, "Nothing.mapCoverage")


def test_unknown_member_raises(hub):
    root, model = hub
    with pytest.raises(EditError, match="unknown target"):
        cd_reach.resolve_target(model, root, "AppState.nopeNope")


def test_unknown_bare_raises(hub):
    root, model = hub
    with pytest.raises(EditError, match="unknown target"):
        cd_reach.resolve_target(model, root, "Missing")


def test_short_name_raises_with_hint(hub):
    root, model = hub
    with pytest.raises(EditError, match="symbol id"):
        cd_reach.resolve_target(model, root, "AppState.ab")


def test_bad_text_raises(hub):
    root, model = hub
    with pytest.raises(EditError):
        cd_reach.resolve_target(model, root, "x;rm -rf")


def test_resolve_enum_case(tmp_path):
    f = write(tmp_path, "P.swift", "enum Kind: String { case peak, hut }\n")
    r = cd_reach.resolve_target(model_for([f]), tmp_path, "Kind.peak")
    assert r["decl_lines"] == [("P.swift", 1)]


def test_resolve_via_model_symbol_id(tmp_path):
    f = write(tmp_path, "m.py", "class Foo:\n    def barBaz(self):\n        pass\n")
    model = {"symbols": [
        {"id": "m.py#Foo", "name": "Foo", "kind": "class", "file": "m.py", "span": {"startLine": 1, "endLine": 3}},
        {"id": "m.py#Foo.barBaz", "name": "barBaz", "kind": "method", "file": "m.py", "parent": "m.py#Foo",
         "span": {"startLine": 2, "endLine": 3}}],
        "coverage": {"files": [{"path": f, "language": "python", "parsed": True}], "unavailable": []}}
    r = cd_reach.resolve_target(model, tmp_path, "m.py#Foo.barBaz")
    assert r["owner"] == "Foo" and r["member"] == "barBaz"
    assert r["model_symbol"] == "m.py#Foo.barBaz"


# ---------------------------------------------------------------- callers

def test_hub_type_unrelated_member_has_no_callers(hub):
    root, model = hub
    r = cd_reach.resolve_target(model, root, "AppState.mapCoverage")
    c = cd_reach.member_callers(model, root, r)
    assert c["nonTest"] == 0 and c["files"] == [] and c["heuristic"] is True
    type_level = cd_reach.member_callers(model, root, cd_reach.resolve_target(model, root, "AppState"))
    assert type_level["nonTest"] > 4


def test_member_callers_counts_member_users(hub):
    root, model = hub
    r = cd_reach.resolve_target(model, root, "AppState.placeResolver")
    c = cd_reach.member_callers(model, root, r)
    assert c["nonTest"] == 10 and c["total"] == 10
    assert "App/AppState.swift" not in c["files"]
    assert c["files"] == sorted(c["files"])


def test_same_file_call_site_counts_declaration_does_not(tmp_path):
    f = write(tmp_path, "S.swift", "struct Thing {\n    var widget = 1\n}\nlet t = Thing()\nlet x = t.widget\n")
    model = model_for([f])
    r = cd_reach.resolve_target(model, tmp_path, "Thing.widget")
    assert cd_reach.member_callers(model, tmp_path, r)["nonTest"] == 1
    f2 = write(tmp_path, "T.swift", "struct Other {\n    var widget = 1\n}\n")
    r2 = cd_reach.resolve_target(model_for([f2]), tmp_path, "Other.widget")
    assert cd_reach.member_callers(model_for([f2]), tmp_path, r2)["nonTest"] == 0


def test_test_files_counted_in_total_only(tmp_path):
    files = [write(tmp_path, "A.swift", "struct Box {\n    func openLid() {}\n}\n"),
             write(tmp_path, "B.swift", "func f(b: Box) { b.openLid() }\n"),
             write(tmp_path, "Tests/BoxTests.swift", "func t(b: Box) { b.openLid() }\n"),
             write(tmp_path, "tests/test_box.py", "b.openLid()\n")]
    model = model_for(files)
    c = cd_reach.member_callers(model, tmp_path, cd_reach.resolve_target(model, tmp_path, "Box.openLid"))
    assert c["total"] == 3 and c["nonTest"] == 1 and c["files"] == ["B.swift"]


def test_short_member_name_needs_owner_mention(tmp_path):
    files = [write(tmp_path, "A.swift", "struct Box {\n    func load() {}\n}\n"),
             write(tmp_path, "B.swift", "func f(b: Box) { b.load() }\n"),
             write(tmp_path, "C.swift", "func g(x: Other) { x.load() }\n")]
    model = model_for(files)
    c = cd_reach.member_callers(model, tmp_path, cd_reach.resolve_target(model, tmp_path, "Box.load"))
    assert c["files"] == ["B.swift"]


def test_symlink_escaping_root_is_ignored(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.swift").write_text("func z(b: Box) { b.openLid() }\n")
    root = tmp_path / "root"
    files = [write(root, "A.swift", "struct Box {\n    func openLid() {}\n}\n")]
    os.symlink(outside / "leak.swift", root / "L.swift")
    files.append("L.swift")
    model = model_for(files)
    c = cd_reach.member_callers(model, root, cd_reach.resolve_target(model, root, "Box.openLid"))
    assert c["total"] == 0


# ---------------------------------------------------------------- case sites

SWIFT_ENUM = "enum Kind: String { case peak, hut, camp }\n"


def swift_switch(var, label_a, label_b, default):
    d = "    default: break\n" if default else ""
    return ("func f(v: %s) {\n    switch v {\n    case %s: print(1)\n    case %s: print(2)\n%s    }\n}\n"
            % (var, label_a, label_b, d))


def case_setup(tmp_path, files):
    write(tmp_path, "Kind.swift", SWIFT_ENUM)
    for rel, text in files.items():
        write(tmp_path, rel, text)
    model = model_for(["Kind.swift", *files])
    return model, cd_reach.resolve_target(model, tmp_path, "Kind")


def test_swift_default_switch_counted_exhaustive_not(tmp_path):
    model, res = case_setup(tmp_path, {
        "A.swift": swift_switch("Kind", ".peak", ".hut", True),
        "B.swift": swift_switch("Kind", ".peak, .hut", ".camp", False)})
    out = cd_reach.case_sites(tmp_path, res, [("A.swift", 2), ("B.swift", 2)], model=model)
    assert [s["file"] for s in out["sites"]] == ["A.swift"]
    assert out["sites"][0]["catchAll"] == "default:" and out["heuristic"] is True
    assert out["unverified"] == []


def test_unrelated_kind_switch_not_counted(tmp_path):
    model, res = case_setup(tmp_path, {"A.swift": swift_switch("Shape", ".circle", ".square", True)})
    assert cd_reach.case_sites(tmp_path, res, [("A.swift", 1)], model=model)["sites"] == []


def test_swift_unknown_default_is_flagged_by_compiler(tmp_path):
    src = "func f(v: Kind) {\n    switch v {\n    case .peak: break\n    @unknown default: break\n    }\n}\n"
    model, res = case_setup(tmp_path, {"A.swift": src})
    assert cd_reach.case_sites(tmp_path, res, [("A.swift", 1)], model=model)["sites"] == []


def test_kotlin_else_and_rust_underscore(tmp_path):
    write(tmp_path, "K.kt", "enum class Kind { PEAK, HUT }\n")
    write(tmp_path, "u.kt", "fun f(k: Kind) = when (k) {\n    Kind.PEAK -> 1\n    else -> 2\n}\n"
          "fun g(k: Kind) = when (k) {\n    Kind.PEAK -> 1\n    Kind.HUT -> 2\n}\n")
    write(tmp_path, "r.rs", "enum Kind { Peak, Hut }\nfn f(k: Kind) {\n    match k {\n        Kind::Peak => 1,\n        _ => 2,\n    }\n}\n")
    model = model_for(["K.kt", "u.kt", "r.rs"])
    kt = cd_reach.resolve_target(model, tmp_path, "Kind")
    out = cd_reach.case_sites(tmp_path, kt, [("u.kt", 1), ("r.rs", 3)], model=model)
    got = {(s["file"], s["line"], s["catchAll"]) for s in out["sites"]}
    assert ("u.kt", 1, "else ->") in got and ("r.rs", 3, "_ =>") in got
    assert not any(s["file"] == "u.kt" and s["line"] == 5 for s in out["sites"])


def test_python_match_counted_without_catch_all(tmp_path):
    write(tmp_path, "k.py", "from enum import Enum\nclass Kind(Enum):\n    PEAK = 1\n    HUT = 2\n")
    write(tmp_path, "u.py", "def f(k):\n    match k:\n        case Kind.PEAK:\n            return 1\n")
    model = {"symbols": [], "coverage": {"files": [{"path": "k.py", "language": "python", "parsed": True},
                                                   {"path": "u.py", "language": "python", "parsed": True}],
                                         "unavailable": []}}
    res = cd_reach.resolve_target(model, tmp_path, "Kind")
    out = cd_reach.case_sites(tmp_path, res, [("u.py", 3)], model=model)
    assert out["sites"] == [{"file": "u.py", "line": 2, "catchAll": None}]


def test_tuple_switch_goes_to_unverified_with_reason(tmp_path):
    src = "func f(a: Kind, b: Int) {\n    switch (a, b) {\n    case (.peak, _): break\n    default: break\n    }\n}\n"
    model, res = case_setup(tmp_path, {"A.swift": src})
    out = cd_reach.case_sites(tmp_path, res, [("A.swift", 3)], model=model)
    assert out["sites"] == []
    assert out["unverified"] and out["unverified"][0]["reason"]


def test_unbalanced_braces_goes_to_unverified(tmp_path):
    src = "func f(v: Kind) {\n    switch v {\n    case .peak: break\n"
    model, res = case_setup(tmp_path, {"A.swift": src})
    out = cd_reach.case_sites(tmp_path, res, [("A.swift", 2)], model=model)
    assert out["sites"] == [] and out["unverified"][0]["reason"]


def test_non_exhaustive_language_counts_every_switch(tmp_path):
    write(tmp_path, "K.java", "enum Kind { PEAK, HUT }\n")
    write(tmp_path, "U.java", "class U {\n  void f(Kind k) {\n    switch (k) {\n      case PEAK: break;\n    }\n  }\n}\n")
    model = model_for(["K.java", "U.java"])
    res = cd_reach.resolve_target(model, tmp_path, "Kind")
    out = cd_reach.case_sites(tmp_path, res, [("U.java", 4)], model=model)
    assert out["sites"] == [{"file": "U.java", "line": 3, "catchAll": None}]


def test_case_sites_deterministic(tmp_path):
    model, res = case_setup(tmp_path, {
        "B.swift": swift_switch("Kind", ".peak", ".hut", True),
        "A.swift": swift_switch("Kind", ".peak", ".hut", True)})
    deps = [("B.swift", 2), ("A.swift", 2)]
    a = cd_reach.case_sites(tmp_path, res, deps, model=model)
    b = cd_reach.case_sites(tmp_path, res, list(reversed(deps)), model=model)
    assert json.dumps(a) == json.dumps(b)
    assert [s["file"] for s in a["sites"]] == ["A.swift", "B.swift"]


def test_case_sites_ignore_symlink_outside_root(tmp_path):
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / "x.swift").write_text(swift_switch("Kind", ".peak", ".hut", True))
    root = tmp_path / "root"
    write(root, "Kind.swift", SWIFT_ENUM)
    os.symlink(outside / "x.swift", root / "L.swift")
    model = model_for(["Kind.swift", "L.swift"])
    res = cd_reach.resolve_target(model, root, "Kind")
    assert cd_reach.case_sites(root, res, [("L.swift", 2)], model=model)["sites"] == []


# ---------------------------------------------------------------- assumption reach

def test_assumption_readers_and_checklist(tmp_path):
    files = [write(tmp_path, "Pack.swift", "struct Pack {\n    static var bundled = 1\n}\n"),
             write(tmp_path, "A.swift", "let p = Pack.bundled\nlet r = Bundle.main.path(forResource: \"x\")\n"),
             write(tmp_path, "B.swift", "let q = Pack.bundled\nlet z = 2\nlet w = 3\n")]
    model = model_for(files)
    out = cd_reach.assumption_reach(model, tmp_path, "bundled")
    assert [(r["file"], r["line"]) for r in out["readers"]] == [("A.swift", 1), ("B.swift", 1)]
    assert out["files"] == ["A.swift", "B.swift"]
    cats = {(c["file"], c["line"], c["category"]) for c in out["checklist"]}
    assert ("A.swift", 1, "single-instance-accessor") in cats
    assert ("A.swift", 2, "resource-lookup") in cats    # neighbouring line
    assert not any(c["file"] == "B.swift" and c["line"] == 3 for c in out["checklist"])


def test_assumption_zero_readers_allowed_short_name_raises(tmp_path):
    f = write(tmp_path, "a.swift", "let nothing = 1\n")
    model = model_for([f])
    out = cd_reach.assumption_reach(model, tmp_path, "lonelyName")
    assert out["readers"] == [] and out["checklist"] == [] and out["files"] == []
    with pytest.raises(EditError):
        cd_reach.assumption_reach(model, tmp_path, "abc")


def test_assumption_skips_overlong_lines(tmp_path):
    f = write(tmp_path, "a.swift", "let x = bundled" + " " * 500 + "\n")
    out = cd_reach.assumption_reach(model_for([f]), tmp_path, "bundled")
    assert out["readers"] == []


def test_assumption_deterministic(tmp_path):
    files = [write(tmp_path, "B.swift", "x.bundled\n"), write(tmp_path, "A.swift", "y.bundled\n")]
    m = model_for(files)
    assert cd_reach.assumption_reach(m, tmp_path, "bundled") == cd_reach.assumption_reach(m, tmp_path, "bundled")
