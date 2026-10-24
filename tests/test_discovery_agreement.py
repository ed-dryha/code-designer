"""Extractor discovery and validator completeness (cd_validate --root) must agree."""
import json
import os
import subprocess

from conftest import run_py


def _run(repo_root, path, cache, tmp_path):
    out = tmp_path / "m.json"
    r = run_py(repo_root / "src/extractor/cd_extract.py", path, "--cache-dir", cache, "--allow-download", "--out", out)
    assert r.returncode == 0, r.stderr
    v = run_py(repo_root / "src/extractor/cd_validate.py", out, "--root", path)
    assert v.returncode == 0, v.stdout + v.stderr
    return json.loads(out.read_text())


def test_git_repo_agreement(repo_root, grammar_cache, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / ".gitignore").write_text("ignored.py\n")
    (repo / "a.py").write_text("def a():\n    pass\n")
    (repo / "ignored.py").write_text("def i():\n    pass\n")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "n.py").write_text("def n():\n    pass\n")
    m = _run(repo_root, repo, grammar_cache, tmp_path)
    assert {"path": "ignored.py", "reason": "ignored"} in m["coverage"]["skipped"]


def test_non_git_agreement(repo_root, grammar_cache, tmp_path):
    d = tmp_path / "plain"
    (d / "node_modules").mkdir(parents=True)
    (d / "node_modules" / "n.py").write_text("def n():\n    pass\n")
    (d / "a.py").write_text("def a():\n    pass\n")
    _run(repo_root, d, grammar_cache, tmp_path)
