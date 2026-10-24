"""Validator: one positive per provenance and one negative per rule."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from conftest import run_py

FIX = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden" / "python.json"


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_validate.py"


@pytest.fixture()
def good():
    m = json.loads(GOLDEN.read_text())
    m["generatedAt"] = "2026-10-24T00:00:00Z"
    m["generator"]["version"] = "0.1.0"
    return m


def _run(script, tmp_path, model, *extra):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(model))
    return run_py(script, p, *extra)


def test_clean_tree_sitter_passes(script, tmp_path, good):
    r = _run(script, tmp_path, good)
    assert r.returncode == 0, r.stdout


def test_clean_agent_passes(script):
    r = run_py(script, FIX / "models" / "valid_agent.json")
    assert r.returncode == 0, r.stdout


def test_dup_id_fixture(script):
    r = run_py(script, FIX / "models" / "bad_dup_ids.json")
    assert r.returncode == 1
    assert "duplicate-id" in r.stdout


def test_dup_id_mutation(script, tmp_path, good):
    good["symbols"][1]["id"] = good["symbols"][0]["id"]
    r = _run(script, tmp_path, good)
    assert r.returncode == 1 and "duplicate-id" in r.stdout


def test_parent_missing(script, tmp_path, good):
    good["symbols"][1]["parent"] = "shapes.py#Nope"
    r = _run(script, tmp_path, good)
    assert r.returncode == 1 and "parent-unresolved" in r.stdout


def test_child_span_outside_parent(script, tmp_path, good):
    good["symbols"][1]["span"]["endLine"] = 99
    r = _run(script, tmp_path, good)
    assert r.returncode == 1 and "span-outside-parent" in r.stdout


def test_id_prefix_mismatch(script, tmp_path, good):
    good["symbols"][0]["id"] = "other.py#Shape"
    r = _run(script, tmp_path, good)
    assert r.returncode == 1 and "id-prefix" in r.stdout


def test_inferred_with_tree_sitter(script, tmp_path, good):
    good["symbols"][0]["inferred"] = True
    r = _run(script, tmp_path, good)
    assert r.returncode == 1 and "inferred-provenance" in r.stdout


def test_file_in_files_and_unavailable(script, tmp_path, good):
    good["coverage"]["unavailable"] = [{"language": "python", "files": ["shapes.py"], "reason": "no-grammar"}]
    r = _run(script, tmp_path, good)
    assert r.returncode == 1 and "coverage-conflict" in r.stdout


def test_schema_error_reported_with_path(script, tmp_path, good):
    del good["symbols"][0]["kind"]
    r = _run(script, tmp_path, good)
    assert r.returncode == 1 and "$.symbols[0]: schema:" in r.stdout


def test_source_file_missing_from_coverage(script, tmp_path, good):
    root = tmp_path / "repo"
    shutil.copytree(FIX / "python", root)
    (root / "extra.py").write_text("x = 1\n")
    r = _run(script, tmp_path, good, "--root", root)
    assert r.returncode == 1
    assert "coverage-missing" in r.stdout and "extra.py" in r.stdout


def test_coverage_complete_with_root(script, tmp_path, good):
    root = tmp_path / "repo"
    shutil.copytree(FIX / "python", root)
    r = _run(script, tmp_path, good, "--root", root)
    assert r.returncode == 0, r.stdout


def test_usage_error_exit_2(script, tmp_path):
    r = run_py(script, tmp_path / "missing.json")
    assert r.returncode == 2
