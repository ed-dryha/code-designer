"""Blast radius: model edges plus grep dependents, unverified classification."""
import json
import os
from pathlib import Path

import pytest

from conftest import run_py

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_blast.py"


def _extract(repo_root, grammar_cache, src_dir, tmp_path):
    out = tmp_path / "m.json"
    r = run_py(repo_root / "src" / "extractor" / "cd_extract.py", src_dir,
               "--cache-dir", grammar_cache, "--allow-download", "--out", out)
    assert r.returncode == 0, r.stderr
    return out


def _blast(script, model, root, *extra):
    r = run_py(script, "--model", model, "--root", root, *extra)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def _sym(i, name, kind, file, s, e, parent=None, supertypes=None):
    return {"id": i, "kind": kind, "name": name, "parent": parent, "file": file,
            "span": {"startLine": s, "endLine": e}, "supertypes": supertypes or [],
            "provenance": "tree-sitter", "inferred": False}


def _repo(tmp_path, files, symbols, unavailable=None, errors=()):
    root = tmp_path / "repo"
    root.mkdir()
    for name, text in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    model = {"schemaVersion": 1, "symbols": symbols,
             "coverage": {"files": [{"path": n, "language": "python", "parsed": True,
                                     "hasErrors": n in errors} for n in files],
                          "unavailable": unavailable or []}}
    mp = tmp_path / "model.json"
    mp.write_text(json.dumps(model))
    return root, mp


def test_go_cross_file_children(script, repo_root, grammar_cache, tmp_path):
    m = _extract(repo_root, grammar_cache, FIX / "go", tmp_path)
    out = _blast(script, m, FIX / "go", "--symbol", "shapes.go#Circle")
    mod = {(d["file"], d.get("symbol")): d for d in out["model"]}
    d = mod[("shapes_methods.go", "shapes_methods.go#Circle.Perimeter")]
    assert d["tag"] == "model" and d["via"] == "children"
    assert ("shapes.go", "shapes.go#Circle.Scale") in mod


def test_go_grep_hits_exclude_own_span(script, repo_root, grammar_cache, tmp_path):
    m = _extract(repo_root, grammar_cache, FIX / "go", tmp_path)
    out = _blast(script, m, FIX / "go", "--symbol", "shapes.go#Circle")
    assert out["grep"], out
    assert all(h["tag"] == "grep" and h["quote"] == h["quote"].strip() for h in out["grep"])
    lines = {(h["file"], h["line"]) for h in out["grep"]}
    assert ("shapes.go", 21) in lines  # NewCircle body
    assert not any(h["file"] == "shapes.go" and h["line"] in (8, 9, 10) for h in out["grep"])


def test_ts_implementer(script, repo_root, grammar_cache, tmp_path):
    m = _extract(repo_root, grammar_cache, FIX / "typescript", tmp_path)
    out = _blast(script, m, FIX / "typescript", "--symbol", "animals.ts#Walker")
    dog = [d for d in out["model"] if d.get("symbol") == "animals.ts#Dog"]
    assert dog and dog[0]["tag"] == "model" and dog[0]["via"] == "implements"


def test_common_name_unverified(script, tmp_path):
    files = {"a.py": "class Ab:\n    pass\n", "b.py": "x = Ab()\n"}
    syms = [_sym("a.py#Ab", "Ab", "class", "a.py", 1, 2)]
    root, mp = _repo(tmp_path, files, syms)
    out = _blast(script, mp, root, "--symbol", "a.py#Ab")
    assert any(u["reason"] == "common-name" for u in out["unverified"])
    assert out["grep"] == []

    many = {f"f{i}.py": "x = Widget()\n" for i in range(4)}
    many["w.py"] = "class Widget:\n    pass\n"
    syms = [_sym("w.py#Widget", "Widget", "class", "w.py", 1, 2)]
    tmp2 = tmp_path / "two"
    tmp2.mkdir()
    root, mp = _repo(tmp2, many, syms)
    out = _blast(script, mp, root, "--symbol", "w.py#Widget", "--max-files", "2")
    assert any(u["reason"] == "common-name" for u in out["unverified"])


def test_unverified_rules(script, tmp_path):
    files = {
        "a.py": "class Order:\n    pass\n",
        "b.py": "o = getattr(mod, 'Order')\n",
        "c.go": "package c\nfunc (o Order) Total() int { return 1 }\n",
        "d.py": "class Order:\n    pass\n",
        "e.py": "class Sub(Order):\n    pass\n",
    }
    syms = [
        _sym("a.py#Order", "Order", "class", "a.py", 1, 2),
        _sym("d.py#Order", "Order", "class", "d.py", 1, 2),
        _sym("c.go#Order.Total", "Total", "method", "c.go", 2, 2, parent=None),
        _sym("e.py#Sub", "Sub", "class", "e.py", 1, 2,
             supertypes=[{"relation": "extends", "name": "Order"}]),
    ]
    root, mp = _repo(tmp_path, files, syms)
    out = _blast(script, mp, root, "--symbol", "a.py#Order", "--symbol", "c.go#Order.Total")
    reasons = {u["reason"] for u in out["unverified"]}
    assert "dynamic-dispatch" in reasons
    assert "go-unparented-method" in reasons
    assert "ambiguous-name" in reasons
    assert not [d for d in out["model"] if d.get("symbol") == "e.py#Sub"]


def test_unavailable_and_parse_errors(script, tmp_path):
    files = {"a.py": "class Order:\n    pass\n", "b.py": "Order = 1\n"}
    syms = [_sym("a.py#Order", "Order", "class", "a.py", 1, 2)]
    un = [{"language": "cobol", "files": 3, "reason": "no grammar"},
          {"language": "zig", "files": 1, "reason": "no grammar"}]
    root, mp = _repo(tmp_path, files, syms, unavailable=un, errors=("b.py",))
    out = _blast(script, mp, root, "--symbol", "a.py#Order")
    un_entries = [u for u in out["unverified"] if u["reason"] == "unavailable-language"]
    assert len(un_entries) == 2
    assert any(u["reason"] == "parse-errors" and u["file"] == "b.py" for u in out["unverified"])


def test_symlink_escape_skipped(script, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("secret = Order()\n")
    files = {"a.py": "class Order:\n    pass\n", "link.py": "x = 1\n"}
    syms = [_sym("a.py#Order", "Order", "class", "a.py", 1, 2)]
    root, mp = _repo(tmp_path, files, syms)
    (root / "link.py").unlink()
    os.symlink(outside, root / "link.py")
    out = _blast(script, mp, root, "--symbol", "a.py#Order")
    assert not any(h["file"] == "link.py" for h in out["grep"] + out["model"])
    assert "secret" not in json.dumps(out)


def test_output_shape(script, tmp_path):
    files = {"a.py": "class Order:\n    pass\n", "b.py": "o = Order()\n"}
    syms = [_sym("a.py#Order", "Order", "class", "a.py", 1, 2)]
    root, mp = _repo(tmp_path, files, syms)
    out = _blast(script, mp, root, "--symbol", "a.py#Order")
    assert {"model", "grep", "unverified", "scope"} <= set(out)
    assert "no call/import edges in model" in json.dumps(out["scope"])
    assert out["scope"]["files"] == 2 and "python" in out["scope"]["languages"]
    assert out["grep"][0]["file"] == "b.py" and out["grep"][0]["line"] == 1


def test_usage_error(script):
    assert run_py(script).returncode == 2


S1 = FIX / "triage" / "s1-single-instance"


def _unav_repo(tmp_path, files, language="swift"):
    root = tmp_path / "repo"
    root.mkdir()
    for name, text in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    model = {"schemaVersion": 1, "symbols": [],
             "coverage": {"files": [], "unavailable": [
                 {"language": language, "files": list(files), "reason": "no-grammar"}]}}
    mp = tmp_path / "model.json"
    mp.write_text(json.dumps(model))
    return root, mp


def test_name_mode_finds_string_literal_hit(script):
    out = _blast(script, S1 / "model.json", S1, "--name", "RegionPack")
    hit = [h for h in out["grep"] if 'forResource: "RegionPack"' in h["quote"]]
    assert len(hit) == 1
    assert hit[0]["file"] == "Molfar/App/AppState.swift" and hit[0]["line"] == 11
    assert hit[0]["quote"].startswith("if let url = Bundle.main.url(forResource")
    assert any(h["file"] == "Tests/RegionPackTests.swift" for h in out["grep"])


def test_name_mode_without_symbols_and_usage(script, tmp_path):
    root, mp = _repo(tmp_path, {"a.py": "x = Widget()\n"}, [])
    out = _blast(script, mp, root, "--name", "Widget")
    assert [h["file"] for h in out["grep"]] == ["a.py"]
    assert run_py(script, "--model", mp, "--root", root).returncode == 2


def test_name_mode_common_name_suppressed(script, tmp_path):
    files = {f"f{i}.py": "x = Widget()\n" for i in range(4)}
    root, mp = _repo(tmp_path, files, [])
    out = _blast(script, mp, root, "--name", "Widget", "--max-files", "2")
    assert out["grep"] == []
    assert any(u["reason"] == "common-name" for u in out["unverified"])


def test_checklist_resource_lookup_and_single_instance(script):
    out = _blast(script, S1 / "model.json", S1, "--name", "RegionPack")
    cl = out["checklist"]
    res = [c for c in cl if c["category"] == "resource-lookup"]
    assert res and res[0]["file"] == "Molfar/App/AppState.swift" and res[0]["line"] == 11
    assert set(res[0]) >= {"file", "line", "category", "via", "tag", "quote"}
    assert res[0]["via"] == "checklist:resource-lookup" and res[0]["tag"] == "grep"
    sia = [c for c in cl if c["category"] == "single-instance-accessor"]
    assert sia and any(".bundled()" in c["quote"] for c in sia)


def test_checklist_keys_and_empty_without_unavailable(script, tmp_path):
    files = {"a.py": "class Order:\n    pass\n", "b.py": "o = Order()\n"}
    root, mp = _repo(tmp_path, files, [_sym("a.py#Order", "Order", "class", "a.py", 1, 2)])
    out = _blast(script, mp, root, "--symbol", "a.py#Order")
    assert {"model", "grep", "unverified", "scope", "checklist"} <= set(out)
    assert out["checklist"] == []


def test_checklist_caps(script, tmp_path):
    root, mp = _unav_repo(tmp_path, {"A.swift": "let a = Bundle.main.url(x)\n" * 40})
    out = _blast(script, mp, root, "--name", "zzzzzz")
    res = [c for c in out["checklist"] if c["category"] == "resource-lookup"]
    assert len(res) == 15
    assert len(out["checklist"]) <= 60
    assert any(u["reason"] == "truncated" for u in out["unverified"])


def test_checklist_total_cap(script, tmp_path):
    text = ("let a = Bundle.main.x\nlet b = v.shared\nlet c = d ?? e\n"
            "let f = \"k.json\"\nlet g = defaults.forKey(\"zz\")\n") * 20
    root, mp = _unav_repo(tmp_path, {"A.swift": text})
    out = _blast(script, mp, root, "--name", "zzzzzz")
    assert len(out["checklist"]) <= 60


def test_checklist_symlink_escape_skipped(script, tmp_path):
    outside = tmp_path / "outside.swift"
    outside.write_text("let s = Bundle.main.secret\n")
    root, mp = _unav_repo(tmp_path, {"link.swift": "x\n"})
    (root / "link.swift").unlink()
    os.symlink(outside, root / "link.swift")
    out = _blast(script, mp, root, "--name", "secret")
    assert out["checklist"] == [] and "secret" not in json.dumps(out["grep"])


def test_checklist_long_line_skipped(script, tmp_path):
    long = "let a = Bundle.main.url(" + "x" * 450 + ")\n"
    root, mp = _unav_repo(tmp_path, {"A.swift": long + "let b = Bundle.main.url(y)\n"})
    out = _blast(script, mp, root, "--name", "zzzzzz")
    assert {c["line"] for c in out["checklist"]} == {2}
