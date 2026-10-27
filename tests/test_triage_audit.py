"""cd_audit: shape derivation from a real git diff and declarations-vs-diff audit."""
import json
import subprocess

import pytest

import cd_audit
import cd_edits
from conftest import run_py

BASE_FILES = {
    "Place.swift": (
        "struct Place {\n"
        "    enum Kind: String { case peak, hut }\n"
        "    var name: String\n"
        "    func label(prefix: String) -> String {\n"
        "        return prefix + name\n"
        "    }\n"
        "}\n"
    ),
    "PickerRow.swift": (
        "struct PickerRow {\n"
        "    func icon(_ k: Place.Kind) -> String {\n"
        "        switch k {\n"
        "        case .peak: return \"a\"\n"
        "        case .hut: return \"b\"\n"
        "        }\n"
        "    }\n"
        "}\n"
    ),
    "Color.swift": (
        "enum Color {\n"
        "    case red\n"
        "}\n"
    ),
    "README.md": "hello\n",
    "PlaceTests.swift": "// t\n",
}

HEAD_FILES = dict(BASE_FILES)
HEAD_FILES.update({
    "Place.swift": (
        "struct Place {\n"
        "    enum Kind: String { case peak, hut, mapPoint }\n"
        "    var name: String\n"
        "    var note: String\n"
        "    func label(prefix: String, suffix: String = \"\") -> String {\n"
        "        return prefix + name\n"
        "    }\n"
        "}\n"
    ),
    "PickerRow.swift": (
        "struct PickerRow {\n"
        "    func icon(_ k: Place.Kind) -> String {\n"
        "        switch k {\n"
        "        case .peak: return \"a\"\n"
        "        case .hut: return \"b\"\n"
        "        case .mapPoint: return \"c\"\n"
        "        case .other: return \"d\"\n"
        "        }\n"
        "    }\n"
        "}\n"
    ),
    "Color.swift": (
        "enum Color {\n"
        "    case red\n"
        "    case green, blue\n"
        "}\n"
    ),
    "Fresh.swift": "struct Fresh {}\n",
    "FreshTests.swift": "// t\n",
    "README.md": "hello world\n",
    "PlaceTests.swift": "// t2\n",
})


def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)


def sha(root, rev):
    return subprocess.run(["git", "-C", str(root), "rev-parse", rev], check=True,
                          capture_output=True, text=True).stdout.strip()


def write_all(root, files):
    for n, t in files.items():
        (root / n).write_text(t)


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q")
    write_all(r, BASE_FILES)
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    base = sha(r, "HEAD")
    write_all(r, HEAD_FILES)
    git(r, "add", "-A")
    git(r, "commit", "-qm", "head")
    return r, base, sha(r, "HEAD")


def find(shapes, kind, **kw):
    return [s for s in shapes if s["kind"] == kind and all(s.get(k) == v for k, v in kw.items())]


def test_derive_new_file_and_exclusions(repo):
    r, b, h = repo
    d = cd_audit.derive_shapes(r, b, h)
    assert find(d["shapes"], "new-file", file="Fresh.swift")
    paths = {f["path"] for f in d["files"]}
    assert "README.md" not in paths and "PlaceTests.swift" not in paths
    assert "FreshTests.swift" not in paths
    assert "no grammar: member attribution is indentation based" in d["limits"]


def test_derive_add_member(repo):
    r, b, h = repo
    d = cd_audit.derive_shapes(r, b, h)
    assert find(d["shapes"], "add-member", owner="Place", member="note")


def test_derive_add_case_single_line_enum(repo):
    r, b, h = repo
    d = cd_audit.derive_shapes(r, b, h)
    assert find(d["shapes"], "add-case", owner="Kind", member="mapPoint")
    assert not find(d["shapes"], "add-case", owner="Kind", member="peak")


def test_derive_add_case_multiline_enum(repo):
    r, b, h = repo
    d = cd_audit.derive_shapes(r, b, h)
    got = {s["member"] for s in find(d["shapes"], "add-case", owner="Color")}
    assert got == {"green", "blue"}


def test_derive_add_param_defaulted(repo):
    r, b, h = repo
    d = cd_audit.derive_shapes(r, b, h)
    s = find(d["shapes"], "add-param", member="label")
    assert s and s[0]["new"] == "suffix" and s[0]["owner"] == "Place"


def test_derive_body_changed_is_judgment(repo):
    r, b, h = repo
    d = cd_audit.derive_shapes(r, b, h)
    bc = find(d["shapes"], "body-changed", file="PickerRow.swift")
    assert bc and all(s["confidence"] == "judgment" for s in bc)
    assert bc[0]["owner"] == "PickerRow" and bc[0]["member"] == "icon"


def test_derive_rejects_option_like_sha(repo):
    r, b, h = repo
    with pytest.raises(cd_edits.EditError):
        cd_audit.derive_shapes(r, "--output=x", h)
    with pytest.raises(cd_edits.EditError):
        cd_audit.derive_shapes(r, b, "--output=x")


def doc(edits, base, new_paths=(), schema=2, extra=None):
    inputs = {"edits": edits, "newPaths": list(new_paths), "base": base}
    sig = {"schema": schema, "inputs": inputs}
    if schema == 1:
        sig = {"schema": 1, "inputs": {"modify": ["Place"], "additive": [], "base": base}}
    sig.update(extra or {})
    return ("# Design\n\n## Triage\n\nVerdict: light\n\n```json\n%s\n```\n\n## Other\n"
            % json.dumps(sig))


def ed(shape, target, new=None, ref=None):
    return {"shape": shape, "target": target, "new": new, "state": None, "ref": ref}


GOOD = [ed("add-case", "Place.Kind", "mapPoint"), ed("add-member", "Place", "note"),
        ed("add-param", "Place.label", "suffix"), ed("add-case", "Color", "green"),
        ed("body-new-inputs", "PickerRow.icon", None, "mapPoint")]


def classes(res, cls):
    return [m for m in res["mismatches"] if m["class"] == cls]


def test_audit_undeclared_edit_f1_like(repo):
    r, b, h = repo
    res = cd_audit.audit(r, doc(GOOD[:4], b, ["Fresh.swift"]))
    ue = classes(res, "undeclared-edit")
    assert len(ue) == 1 and ue[0]["file"] == "PickerRow.swift"
    assert not classes(res, "declared-no-diff")
    assert not classes(res, "new-path-mismatch")


def test_audit_all_declared_has_judgment_not_mismatch(repo):
    r, b, h = repo
    res = cd_audit.audit(r, doc(GOOD, b, ["Fresh.swift"]))
    assert res["status"] == "ok" and res["mismatches"] == []
    assert any(j["file"] == "PickerRow.swift" for j in res["needsJudgment"])


def test_audit_declared_no_diff(repo):
    r, b, h = repo
    res = cd_audit.audit(r, doc(GOOD + [ed("add-member", "Zebra", "stripes")], b, ["Fresh.swift"]))
    dn = classes(res, "declared-no-diff")
    assert len(dn) == 1 and dn[0]["target"] == "Zebra"


def test_audit_shape_mismatch_removed_body_line(repo):
    r, b, h = repo
    # declared add-member on Place but a body line was removed in label: shape-mismatch
    res = cd_audit.audit(r, doc(GOOD + [ed("add-member", "PickerRow", "extra")], b, ["Fresh.swift"]))
    assert not classes(res, "shape-mismatch")  # PickerRow only added lines
    # body-new-inputs naming an identifier absent from added lines
    res = cd_audit.audit(r, doc(GOOD[:4] + [ed("body-new-inputs", "PickerRow.icon", None, "ghost")],
                                b, ["Fresh.swift"]))
    sm = classes(res, "shape_mismatch".replace("_", "-"))
    assert len(sm) == 1 and "ghost" in sm[0]["detail"]


def test_audit_shape_mismatch_modified_member(tmp_path):
    r = tmp_path / "s"
    r.mkdir()
    git(r, "init", "-q")
    (r / "A.swift").write_text("struct A {\n    func f() {\n        run(1)\n    }\n}\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "b")
    b = sha(r, "HEAD")
    (r / "A.swift").write_text("struct A {\n    var x = 1\n    func f() {\n        run(2)\n    }\n}\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "h")
    res = cd_audit.audit(r, doc([ed("add-member", "A", "x")], b))
    assert len(classes(res, "shape-mismatch")) == 1


def test_audit_new_path_mismatch_both_directions(repo):
    r, b, h = repo
    res = cd_audit.audit(r, doc(GOOD, b, ["Ghost.swift"]))
    paths = {(m["path"], m["detail"]) for m in classes(res, "new-path-mismatch")}
    assert ("Ghost.swift", "declared but not added") in paths
    assert ("Fresh.swift", "added but not declared") in paths


def test_audit_unsupported_schema(repo):
    r, b, h = repo
    res = cd_audit.audit(r, doc([], b, schema=1))
    assert res["status"] == "unsupported_schema".replace("_", "-")
    assert res["mismatches"] == []


def test_audit_no_base_and_no_triage(repo):
    r, b, h = repo
    assert cd_audit.audit(r, doc(GOOD, "none"))["status"] == "no-base"
    assert cd_audit.audit(r, "# nothing\n")["status"] == "no-triage"


def test_cli_roundtrip_and_confinement(repo, tmp_path, repo_root):
    r, b, h = repo
    script = repo_root / "src" / "extractor" / "cd_audit.py"
    (r / "design.md").write_text(doc(GOOD, b, ["Fresh.swift"]))
    ok = run_py(script, "audit", "--root", r, "--doc", "design.md")
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["status"] == "ok"
    outside = tmp_path / "out.md"
    outside.write_text(doc(GOOD, b))
    bad = run_py(script, "audit", "--root", r, "--doc", outside)
    assert bad.returncode == 2 and "error:" in bad.stderr
    bad = run_py(script, "audit", "--root", r, "--doc", "../out.md")
    assert bad.returncode == 2
    bad = run_py(script, "audit", "--root", r, "--doc", "design.md", "--head", "--output=x")
    assert bad.returncode == 2
