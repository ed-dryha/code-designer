"""D-07 Go model fixes: cross-file receiver parenting, multi-name fields, clean method ids."""
import json
from pathlib import Path

from conftest import run_py

ROOT = Path(__file__).parent


def _extract(repo_root, grammar_cache, src_dir, tmp_path):
    out = tmp_path / "m.json"
    r = run_py(repo_root / "src" / "extractor" / "cd_extract.py", src_dir,
               "--cache-dir", grammar_cache, "--allow-download", "--out", out)
    assert r.returncode == 0, r.stderr
    return json.loads(out.read_text()), out


def _validate(repo_root, model_path):
    r = run_py(repo_root / "src" / "extractor" / "cd_validate.py", model_path)
    assert r.returncode == 0, r.stdout + r.stderr


def _by_id(m):
    return {s["id"]: s for s in m["symbols"]}


def _write(base, files):
    for rel, text in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return base


def test_cross_file_method_parent(repo_root, grammar_cache, tmp_path):
    m, _ = _extract(repo_root, grammar_cache, ROOT / "fixtures" / "go", tmp_path)
    s = _by_id(m)["shapes_methods.go#Circle.Perimeter"]
    assert s["parent"] == "shapes.go#Circle"
    assert s["file"] == "shapes_methods.go"


def test_multi_name_fields(repo_root, grammar_cache, tmp_path):
    m, _ = _extract(repo_root, grammar_cache, ROOT / "fixtures" / "go", tmp_path)
    ids = _by_id(m)
    for n in ("X", "Y"):
        assert ids[f"shapes.go#Point.{n}"]["kind"] == "field"


def test_method_ids_have_no_receiver_fragment(repo_root, grammar_cache, tmp_path):
    src = _write(tmp_path / "repo", {
        "a.go": "package p\n\ntype A struct{}\n\ntype B struct{}\n",
        "b.go": "package p\n\nfunc (a A) Do() {}\n\nfunc (b *B) Do() {}\n",
        "f.go": "package p\n\ntype C struct{}\n\ntype D struct{}\n\n"
                "func (c C) Do() {}\n\nfunc (d D) Do() {}\n",
    })
    m, _ = _extract(repo_root, grammar_cache, src, tmp_path)
    ids = set(_by_id(m))
    assert {"b.go#A.Do", "b.go#B.Do", "f.go#C.Do", "f.go#D.Do"} <= ids
    for i in ids:
        assert "(" not in i, i


def test_same_name_type_in_other_directory_not_parent(repo_root, grammar_cache, tmp_path):
    src = _write(tmp_path / "repo", {
        "dir1/a.go": "package one\n\ntype T struct{}\n",
        "dir2/b.go": "package two\n\nfunc (t T) M() {}\n",
    })
    m, _ = _extract(repo_root, grammar_cache, src, tmp_path)
    s = _by_id(m)["dir2/b.go#M"]
    assert s["parent"] is None


def test_validate_passes(repo_root, grammar_cache, tmp_path):
    _, out = _extract(repo_root, grammar_cache, ROOT / "fixtures" / "go", tmp_path)
    _validate(repo_root, out)
    src = _write(tmp_path / "repo", {
        "a.go": "package p\n\ntype A struct{ X, Y int }\n",
        "b.go": "package p\n\nfunc (a A) Do() {}\n",
    })
    out2 = tmp_path / "m2.json"
    r = run_py(repo_root / "src" / "extractor" / "cd_extract.py", src,
               "--cache-dir", grammar_cache, "--allow-download", "--out", out2)
    assert r.returncode == 0, r.stderr
    _validate(repo_root, out2)
