"""Extractor discovery safety and unavailable-language contract."""
import json
import os
import subprocess

import pytest

from conftest import run_py


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def _extract(repo_root, path, cache, *extra, out=None):
    out = out or (path.parent / (path.name + ".model.json"))
    r = run_py(repo_root / "src/extractor/cd_extract.py", path, "--cache-dir", cache, "--out", out, *extra)
    model = json.loads(out.read_text()) if out.exists() else None
    return r, model


@pytest.fixture()
def empty_cache(tmp_path):
    d = tmp_path / "emptycache"
    d.mkdir()
    return d


def _skipped(model):
    return {(s["path"], s["reason"]) for s in model["coverage"]["skipped"]}


def test_git_ignored_files_skipped(repo_root, grammar_cache, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / ".gitignore").write_text("gen.py\n")
    (repo / "a.py").write_text("def a():\n    pass\n")
    (repo / "gen.py").write_text("def g():\n    pass\n")
    r, m = _extract(repo_root, repo, grammar_cache, "--allow-download")
    assert r.returncode == 0, r.stderr
    assert ("gen.py", "ignored") in _skipped(m)
    assert [f["path"] for f in m["coverage"]["files"]] == ["a.py"]


def test_non_git_ignore_list(repo_root, grammar_cache, tmp_path):
    d = tmp_path / "plain"
    (d / "node_modules").mkdir(parents=True)
    (d / "node_modules" / "x.py").write_text("def x(): pass\n")
    (d / "a.py").write_text("def a():\n    pass\n")
    r, m = _extract(repo_root, d, grammar_cache, "--allow-download")
    assert r.returncode == 0, r.stderr
    assert ("node_modules", "ignored") in _skipped(m)
    assert [f["path"] for f in m["coverage"]["files"]] == ["a.py"]


def test_too_large_skipped(repo_root, grammar_cache, tmp_path):
    d = tmp_path / "big"
    d.mkdir()
    (d / "a.py").write_text("def a():\n    pass\n")
    (d / "big.py").write_text("x = 1\n" * 10)
    r, m = _extract(repo_root, d, grammar_cache, "--allow-download", "--max-bytes", "20")
    assert ("big.py", "too-large") in _skipped(m)
    assert [f["path"] for f in m["coverage"]["files"]] == ["a.py"]


def test_default_cap_is_one_mb(repo_root, grammar_cache, tmp_path):
    d = tmp_path / "big2"
    d.mkdir()
    (d / "huge.py").write_text("# " + "x" * 1048576 + "\n")
    r, m = _extract(repo_root, d, grammar_cache, "--allow-download")
    assert ("huge.py", "too-large") in _skipped(m)


@pytest.mark.parametrize("use_git", [False, True])
def test_symlink_escape(repo_root, grammar_cache, tmp_path, use_git):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("def secret():\n    pass\n")
    (outside / "sub").mkdir()
    (outside / "sub" / "deep.py").write_text("def deep():\n    pass\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def a():\n    pass\n")
    os.symlink(outside / "secret.py", repo / "link.py")
    os.symlink(outside / "sub", repo / "linkdir")
    if use_git:
        _git(repo, "init", "-q")
    r, m = _extract(repo_root, repo, grammar_cache, "--allow-download")
    assert r.returncode == 0, r.stderr
    sk = _skipped(m)
    assert ("link.py", "symlink-escape") in sk
    assert ("linkdir", "symlink-escape") in sk
    assert all("secret" not in s["id"] and "deep" not in s["id"] for s in m["symbols"])
    assert [f["path"] for f in m["coverage"]["files"]] == ["a.py"]


def test_unsupported_language_listed(repo_root, grammar_cache, tmp_path):
    d = tmp_path / "ex"
    d.mkdir()
    (d / "a.py").write_text("def a():\n    pass\n")
    (d / "m.ex").write_text("defmodule M do\nend\n")
    (d / "s.swift").write_text("class S {}\n")
    r, m = _extract(repo_root, d, grammar_cache, "--allow-download")
    assert r.returncode == 3
    assert m["status"] == "partial"
    un = {u["language"]: u for u in m["coverage"]["unavailable"]}
    assert un["elixir"]["files"] == ["m.ex"] and un["elixir"]["reason"] == "no-grammar"
    assert un["swift"]["files"] == ["s.swift"]


def test_empty_cache_exit3_unavailable(repo_root, empty_cache, tmp_path):
    d = tmp_path / "py"
    d.mkdir()
    (d / "a.py").write_text("def a():\n    pass\n")
    r, m = _extract(repo_root, d, empty_cache)
    assert r.returncode == 3
    assert m["status"] == "unavailable"
    assert m["coverage"]["unavailable"] == [{"language": "python", "files": ["a.py"], "reason": "no-grammar"}]
    assert m["symbols"] == []
    v = run_py(repo_root / "src/extractor/cd_validate.py", tmp_path / "py.model.json", "--root", d)
    assert v.returncode == 0, v.stdout


def test_partial_when_some_languages_parsed(repo_root, grammar_cache, empty_cache, tmp_path):
    # python available (shared cache), go requested but cache lacks it -> only valid if go absent from cache
    d = tmp_path / "mix"
    d.mkdir()
    (d / "a.py").write_text("def a():\n    pass\n")
    (d / "m.ex").write_text("x\n")
    r, m = _extract(repo_root, d, grammar_cache, "--allow-download")
    assert m["status"] == "partial" and r.returncode == 3
    assert m["coverage"]["files"] and m["coverage"]["unavailable"]


def test_has_errors_flag(repo_root, grammar_cache, tmp_path):
    d = tmp_path / "bad"
    d.mkdir()
    (d / "b.py").write_text("def broken(:\n    class\n")
    r, m = _extract(repo_root, d, grammar_cache, "--allow-download")
    assert r.returncode == 0, r.stderr
    assert m["coverage"]["files"][0]["hasErrors"] is True
