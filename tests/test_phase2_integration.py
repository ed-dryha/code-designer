"""Whole-phase-2 acceptance over the BUILT dist trees."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import run_py

ROOT = Path(__file__).parent
FIX = ROOT / "fixtures"

TREES = {
    "claude-code": "scripts",
    "codex": "skills/extract-structure/scripts",
}
SCRIPT_NAMES = ["cd_gate.py", "cd_blast.py", "cd_screen.py", "cd_backlog.py"]


@pytest.fixture(params=sorted(TREES))
def tree(request, repo_root):
    return request.param, repo_root / "dist" / request.param


def test_skills_scripts_and_no_tokens(tree):
    name, base = tree
    for skill in ("design", "assessment"):
        assert (base / "skills" / skill / "SKILL.md").is_file()
    sdir = base / TREES[name]
    for s in SCRIPT_NAMES:
        assert (sdir / s).is_file(), s
    assert (base / "knowledge").is_dir()
    for f in base.rglob("*"):
        if f.is_file() and f.suffix in {".md", ".json", ".sh", ".py", ".scm"}:
            assert "{{" not in f.read_text(encoding="utf-8", errors="ignore"), f


def test_hooks_only_in_claude_code(repo_root):
    cc = repo_root / "dist" / "claude-code" / "hooks"
    assert (cc / "hooks.json").is_file() and (cc / "nudge.sh").is_file()
    assert not (repo_root / "dist" / "codex" / "hooks").exists()
    env = {k: v for k, v in os.environ.items() if k != "CODE_DESIGNER_NUDGE"}
    silent = subprocess.run(["bash", str(cc / "nudge.sh")], capture_output=True, text=True, env=env)
    assert silent.returncode == 0 and silent.stdout == ""
    env["CODE_DESIGNER_NUDGE"] = "1"
    loud = subprocess.run(["bash", str(cc / "nudge.sh")], capture_output=True, text=True, env=env)
    assert loud.returncode == 0
    assert json.loads(loud.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_script_references_resolve(tree):
    name, base = tree
    for skill in ("design", "assessment"):
        skill_dir = base / "skills" / skill
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        if name == "codex":
            refs = re.findall(r"\$SKILL_DIR/(\.\./extract-structure/scripts/[\w.\-]+)", text)
            assert refs
            for r in refs:
                assert (skill_dir / r).resolve().is_file(), r
        else:
            refs = re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/(scripts/[\w.\-]+)", text)
            assert refs
            for r in refs:
                assert (base / r).is_file(), r


def test_build_check(repo_root):
    r = run_py(repo_root / "scripts" / "build.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_end_to_end_with_built_scripts(tree, grammar_cache, tmp_path):
    name, base = tree
    s = base / TREES[name]
    kb = base / "knowledge"

    # extract + validate + blast on the go fixture
    model = tmp_path / "m.json"
    r = run_py(s / "cd_extract.py", FIX / "go", "--cache-dir", grammar_cache,
               "--allow-download", "--out", model)
    assert r.returncode == 0, r.stderr
    assert run_py(s / "cd_validate.py", model).returncode == 0
    syms = json.loads(model.read_text())["symbols"]
    struct = next(x["id"] for x in syms if x["kind"] == "struct")
    r = run_py(s / "cd_blast.py", "--model", model, "--root", FIX / "go", "--symbol", struct)
    assert r.returncode == 0, r.stdout + r.stderr
    json.loads(r.stdout)

    # gate a prepared no-pattern doc against its repo
    repo = tmp_path / "repo"
    shutil.copytree(FIX / "design" / "pay", repo / "pay")
    dm = FIX / "design" / "model.json"
    r = run_py(s / "cd_gate.py", FIX / "design" / "good-no-pattern.md", "--root", repo,
               "--model", dm, "--kb", kb)
    assert r.returncode == 0, r.stdout + r.stderr

    # screen, backlog merge, lint
    r = run_py(s / "cd_screen.py", "--model", FIX / "screen" / "model.json")
    assert r.returncode == 0, r.stderr
    cands = json.loads(r.stdout)["candidates"]
    assert cands
    broot = tmp_path / "brepo"
    shutil.copytree(FIX / "backlog" / "repo", broot)
    r = run_py(s / "cd_backlog.py", "merge", "--root", broot, "--model", FIX / "backlog" / "model.json",
               "--findings", FIX / "backlog" / "findings.json", "--date", "2026-01-01")
    assert r.returncode == 0, r.stdout + r.stderr
    bl = broot / "docs" / "design" / "backlog.md"
    assert run_py(s / "cd_backlog.py", "lint", bl).returncode == 0

    # design gate with a finding reference and backlog
    r = run_py(s / "cd_gate.py", FIX / "design" / "good-with-finding.md", "--root", repo,
               "--model", dm, "--kb", kb, "--backlog", FIX / "design" / "backlog.md")
    assert r.returncode == 0, r.stdout + r.stderr
