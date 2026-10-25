"""Regression: --out parent directories are created (found by Codex smoke, 01-11)."""
import shutil

from conftest import run_py


def test_out_parent_dir_created(repo_root, grammar_cache, tmp_path):
    src = tmp_path / "proj"
    src.mkdir()
    shutil.copy(repo_root / "tests/fixtures/python/shapes.py", src / "shapes.py")
    out = tmp_path / "nested" / "new" / "dir" / "model.json"
    r = run_py(repo_root / "src/extractor/cd_extract.py", src,
               "--cache-dir", grammar_cache, "--out", out)
    assert r.returncode == 0, r.stderr
    assert out.exists()
    v = run_py(repo_root / "src/extractor/cd_validate.py", out)
    assert v.returncode == 0, v.stdout + v.stderr


def test_out_dir_created_on_unavailable_path(repo_root, tmp_path):
    src = tmp_path / "proj"
    src.mkdir()
    shutil.copy(repo_root / "tests/fixtures/python/shapes.py", src / "shapes.py")
    empty = tmp_path / "emptycache"
    empty.mkdir()
    out = tmp_path / "a" / "b" / "model.json"
    r = run_py(repo_root / "src/extractor/cd_extract.py", src,
               "--cache-dir", empty, "--out", out)
    assert r.returncode == 3, r.stderr
    assert out.exists()
