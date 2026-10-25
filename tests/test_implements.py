"""D-07 implements relation: TS/TSX class implements clauses and Rust trait impls."""
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


def _by_id(m):
    return {s["id"]: s for s in m["symbols"]}


def _sup(sym):
    return {(t["relation"], t["name"]) for t in sym["supertypes"]}


def test_ts_class_implements(repo_root, grammar_cache, tmp_path):
    m, _ = _extract(repo_root, grammar_cache, ROOT / "fixtures" / "typescript", tmp_path)
    sup = _sup(_by_id(m)["animals.ts#Dog"])
    assert ("extends", "Animal") in sup
    assert ("implements", "Walker") in sup
    assert ("implements", "Namer") in sup


def test_ts_interface_extends_stays_extends(repo_root, grammar_cache, tmp_path):
    m, _ = _extract(repo_root, grammar_cache, ROOT / "fixtures" / "typescript", tmp_path)
    assert ("extends", "Namer") in _sup(_by_id(m)["animals.ts#Pet"])


def test_rust_trait_impl_is_implements(repo_root, grammar_cache, tmp_path):
    m, _ = _extract(repo_root, grammar_cache, ROOT / "fixtures" / "rust", tmp_path)
    assert ("implements", "Shape") in _sup(_by_id(m)["shapes.rs#Circle"])


def test_validate_ts_and_rust(repo_root, grammar_cache, tmp_path):
    for lang in ("typescript", "rust"):
        d = tmp_path / lang
        d.mkdir()
        _, path = _extract(repo_root, grammar_cache, ROOT / "fixtures" / lang, d)
        r = run_py(repo_root / "src" / "extractor" / "cd_validate.py", path)
        assert r.returncode == 0, r.stdout + r.stderr
