"""Whole-phase-5 acceptance over the BUILT dist trees."""
import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import run_py

ROOT = Path(__file__).parent
FIX = ROOT / "fixtures"

TREES = {
    "claude-code": "scripts",
    "codex": "skills/extract-structure/scripts",
}


@pytest.fixture(params=sorted(TREES))
def tree(request, repo_root):
    return request.param, repo_root / "dist" / request.param


def _copy(tmp_path, name):
    r = tmp_path / name
    shutil.copytree(FIX / "triage" / name, r, symlinks=True)
    return r


def test_built_tree_scripts_resolve(tree):
    name, base = tree
    assert (base / TREES[name] / "cd_triage.py").is_file()
    skill_dir = base / "skills" / "design"
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "cd_triage.py" in text and "--require-triage" in text
    if name == "codex":
        refs = re.findall(r"\$SKILL_DIR/(\.\./extract-structure/scripts/[\w.\-]+)", text)
        assert refs
        for r in refs:
            assert (skill_dir / r).resolve().is_file(), r
        assert any(r.endswith("cd_triage.py") for r in refs)
    else:
        refs = re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/(scripts/[\w.\-]+)", text)
        assert refs
        for r in refs:
            assert (base / r).is_file(), r
        assert "scripts/cd_triage.py" in refs
    for f in base.rglob("*"):
        if f.is_file() and f.suffix in {".md", ".json", ".py"}:
            assert "{{" not in f.read_text(encoding="utf-8", errors="ignore"), f


def test_skip_flow_triage_stub_gate(tree, tmp_path):
    name, base = tree
    s = base / TREES[name]
    root = _copy(tmp_path, "s0-additive")
    r = run_py(s / "cd_triage.py", "--root", root, "--model", root / "model.json",
               "--spec", root / "spec.md", "--edit", "add-case:Kind=point",
               "--new-path", "Sources/New.swift")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["recommended"] == "skip"
    doc = root / "stub.md"
    doc.write_text(
        "# Design: add point kind\n\nFeature: add point kind\nDate: 2026-10-27\nSpec: spec.md\n"
        "Model generatedAt: 2026-10-27\nCoverage: partial; unavailable languages: swift\n"
        "Triage: see below\n\n" + out["render"] + "\n## Spec Coverage\n\n| Spec lines | Requirement | Maps to |\n|---|---|---|\n"
        "| 1 | feature | no design change: additive only |\n\n## Handoff\n\nSkip stub; no design records.\n",
        encoding="utf-8")
    r = run_py(s / "cd_gate.py", doc, "--root", root, "--model", root / "model.json",
               "--kb", base / "knowledge", "--require-triage", "--spec", root / "spec.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_single_instance_is_full_with_checklist(tree, tmp_path):
    name, base = tree
    s = base / TREES[name]
    root = _copy(tmp_path, "s1-single-instance")
    r = run_py(s / "cd_triage.py", "--root", root, "--model", root / "model.json",
               "--spec", root / "spec.md", "--edit", "change-assumption:RegionPack@spec:3")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["verdictUncapped"] == "full" and out["recommended"] == "light"
    assert any(h["category"] == "resource-lookup" and h["file"].endswith("AppState.swift") and h["line"] == 11
               for h in out["signals"]["reach"]["assumptionHits"])
    b = run_py(s / "cd_blast.py", "--model", root / "model.json", "--root", root, "--name", "RegionPack")
    assert b.returncode == 0, b.stderr
    blast = json.loads(b.stdout)
    assert any("Bundle.main" in h["quote"] and h["via"].startswith("checklist:") for h in blast["checklist"])


@pytest.fixture()
def design_repo(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(FIX / "design" / "pay", root / "pay")
    shutil.copy(FIX / "design" / "spec.md", root / "spec.md")
    return root


@pytest.mark.parametrize("doc,status", [
    ("bad-full-no-records.md", "no-records"),
    ("bad-availability-missing-row.md", "availability-missing-row"),
    ("bad-coverage-unknown-dr.md", "coverage-unknown-dr"),
])
def test_gate_rejects_bad_docs(tree, design_repo, doc, status):
    name, base = tree
    s = base / TREES[name]
    r = run_py(s / "cd_gate.py", FIX / "design" / doc, "--root", design_repo,
               "--model", FIX / "design" / "model.json", "--kb", base / "knowledge",
               "--require-triage", "--spec", design_repo / "spec.md")
    assert r.returncode == 1, r.stdout + r.stderr
    assert status in [x["status"] for x in json.loads(r.stdout)]


def test_readme_names_phase5_features(repo_root):
    text = (repo_root / "README.md").read_text(encoding="utf-8").lower()
    for needle in ("triage", "skip", "light", "full", "checklist", "availability", "spec coverage",
                   "swift", "phase 4"):
        assert needle in text, needle
