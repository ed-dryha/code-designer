"""Lint every source skill: frontmatter, size, tokens; sandbox build succeeds."""
import re
from pathlib import Path

import pytest

from conftest import run_py

SRC = Path(__file__).resolve().parent.parent / "src" / "skills"
SKILLS = sorted(p for p in SRC.glob("*/SKILL.md"))
ALLOWED = {"PLUGIN_ROOT", "SCRIPTS", "KNOWLEDGE", "CACHE_DIR", "HOST"}


def _frontmatter(text):
    assert text.startswith("---\n")
    end = text.index("\n---", 4)
    fm = {}
    for ln in text[4:end].split("\n"):
        k, _, v = ln.partition(":")
        fm[k.strip()] = v.strip()
    return fm


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_lint(path):
    text = path.read_text()
    fm = _frontmatter(text)
    assert fm.get("name") == path.parent.name
    assert fm.get("description")
    assert len(text.splitlines()) < 150
    assert "{{#" not in text
    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", text)) <= ALLOWED
    assert not re.findall(r"\{\{(?![A-Z_]+\}\})", text)


def test_design_skill_description():
    fm = _frontmatter((SRC / "design" / "SKILL.md").read_text())
    assert fm["description"].startswith("Use after the brainstorming spec is approved")


def test_sandbox_build_includes_skills(repo_root, tmp_path):
    out = tmp_path / "dist"
    r = run_py(repo_root / "scripts" / "build.py", "--out", out)
    assert r.returncode == 0, r.stderr
    for host in ("claude-code", "codex"):
        for name in ("design",):
            assert (out / host / "skills" / name / "SKILL.md").is_file()
            assert (out / host / "skills" / name / "RECORD-FORMAT.md").is_file()


CD_SETUP_SKILLS = [SRC / n / "SKILL.md" for n in ("design", "assessment", "extract-structure")]


@pytest.mark.parametrize("path", CD_SETUP_SKILLS, ids=lambda p: p.parent.name)
def test_cd_setup_runs_under_uv(path):
    text = path.read_text()
    assert re.search(r"^\s*uv run --script \{\{SCRIPTS\}\}/cd_setup\.py", text, re.M)
    for ln in text.splitlines():
        if re.search(r"python3 \S*cd_setup\.py", ln):
            assert "--bootstrap-venv" in ln, ln
    assert "--bootstrap-venv" in text
