"""Whole-phase acceptance (ROADMAP Phase 1 criteria 1-5) over the BUILT dist trees."""
import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import run_py

ROOT = Path(__file__).parent
FIXTURE_LANGS = sorted(p.name for p in (ROOT / "fixtures").iterdir()
                       if p.is_dir() and (p / "expected.json").exists())
FIXTURE = ROOT / "fixtures" / "python"

TREES = {
    "claude-code": "scripts",
    "codex": "skills/extract-structure/scripts",
}


@pytest.fixture(params=sorted(TREES))
def scripts(request, repo_root):
    d = repo_root / "dist" / request.param / TREES[request.param]
    assert d.is_dir(), d
    return d


def _extract(scripts, cache, lang, out):
    return run_py(scripts / "cd_extract.py", ROOT / "fixtures" / lang,
                  "--cache-dir", cache, "--allow-download", "--out", out)


@pytest.mark.parametrize("lang", FIXTURE_LANGS)
def test_criterion_1_extract_all_languages(scripts, grammar_cache, tmp_path, lang):
    out = tmp_path / "m.json"
    r = _extract(scripts, grammar_cache, lang, out)
    assert r.returncode == 0, r.stderr
    got = {(s["id"], s["kind"]) for s in json.loads(out.read_text())["symbols"]}
    expected = json.loads((ROOT / "fixtures" / lang / "expected.json").read_text())
    for e in expected:
        assert (e["id"], e["kind"]) in got
    kinds = {k for _, k in got}
    assert "method" in kinds and "field" in kinds
    assert kinds & {"class", "interface", "struct", "trait"}
    # criterion 2 in the same pass: validator accepts every produced model
    v = run_py(scripts / "cd_validate.py", out)
    assert v.returncode == 0, v.stdout + v.stderr


def test_criterion_2_validator_rejects_corrupted(scripts, grammar_cache, tmp_path):
    out = tmp_path / "m.json"
    assert _extract(scripts, grammar_cache, "python", out).returncode == 0
    m = json.loads(out.read_text())
    del m["symbols"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(m))
    r = run_py(scripts / "cd_validate.py", bad)
    assert r.returncode == 1


def test_criterion_3_offline_exit_3_and_fallback(scripts, repo_root, tmp_path):
    empty = tmp_path / "empty-cache"
    empty.mkdir()
    out = tmp_path / "m.json"
    r = run_py(scripts / "cd_extract.py", FIXTURE, "--cache-dir", empty, "--out", out)
    assert r.returncode == 3, r.stderr
    assert json.loads(out.read_text())["status"] == "unavailable"
    # agent-provenance model validates; off-by-one citation fails verification
    from test_fallback_contract import _model
    model = _model()
    mp = tmp_path / "agent.json"
    mp.write_text(json.dumps(model))
    assert run_py(scripts / "cd_validate.py", mp, "--root", FIXTURE).returncode == 0
    cit = {"file": "shapes.py", "startLine": 18, "endLine": 18, "quote": "def make_circle(r):"}
    good, bad = tmp_path / "g.json", tmp_path / "b.json"
    good.write_text(json.dumps([cit]))
    bad.write_text(json.dumps([dict(cit, startLine=19, endLine=19)]))
    assert run_py(scripts / "cd_verify.py", "--root", FIXTURE, "--citations", good).returncode == 0
    assert run_py(scripts / "cd_verify.py", "--root", FIXTURE, "--citations", bad).returncode == 1


def test_criterion_4_verify_real_and_fabricated(scripts):
    # real quote at the right line passes; fabricated quote fails
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        real = Path(d) / "real.json"
        fake = Path(d) / "fake.json"
        real.write_text(json.dumps([{"file": "shapes.py", "startLine": 18, "endLine": 18,
                                     "quote": "def make_circle(r):"}]))
        fake.write_text(json.dumps([{"file": "shapes.py", "startLine": 18, "endLine": 18,
                                     "quote": "def totally_made_up():"}]))
        assert run_py(scripts / "cd_verify.py", "--root", FIXTURE, "--citations", real).returncode == 0
        assert run_py(scripts / "cd_verify.py", "--root", FIXTURE, "--citations", fake).returncode == 1


@pytest.mark.parametrize("tree", sorted(TREES))
def test_criterion_5_tree_contents(repo_root, tree):
    base = repo_root / "dist" / tree
    assert (base / "knowledge" / "precedence.md").is_file()
    assert len(list((base / "knowledge" / "patterns").rglob("pattern-*.md"))) == 23
    assert len(list((base / "knowledge" / "principles").rglob("*.md"))) >= 7
    assert len(list((base / "knowledge" / "smells").rglob("*.md"))) >= 20
    assert (base / TREES[tree] / "cd_extract.py").is_file()
    for md in base.rglob("*.md"):
        assert not re.search(r"\{\{[A-Z#]", md.read_text(encoding="utf-8")), md


def test_criterion_5_build_check_and_no_conditionals_in_src(repo_root):
    r = run_py(repo_root / "scripts" / "build.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    for p in (repo_root / "src").rglob("*"):
        if p.is_file() and p.suffix in {".md", ".scm", ".py", ".json"}:
            assert "{{#" not in p.read_text(encoding="utf-8", errors="ignore"), p


@pytest.mark.parametrize("tree", sorted(TREES))
def test_skill_out_into_nonexistent_nested_dir(repo_root, grammar_cache, tmp_path, tree):
    """Regression for the Codex smoke bug: --out parent dir must be created."""
    scripts = repo_root / "dist" / tree / TREES[tree]
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copy(FIXTURE / "shapes.py", proj / "shapes.py")
    out = tmp_path / "proj" / ".code-designer" / "deeper" / "structure-model.json"
    r = run_py(scripts / "cd_extract.py", proj, "--cache-dir", grammar_cache,
               "--allow-download", "--out", out)
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    assert run_py(scripts / "cd_validate.py", out).returncode == 0
