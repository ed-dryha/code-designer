"""Build script: token expansion, determinism, stale check, version sync."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import run_py

FIXTURE = Path(__file__).parent / "fixtures" / "python"
HOSTS = ("claude-code", "codex")


def build(repo_root, *args):
    return run_py(repo_root / "scripts" / "build.py", *args)


@pytest.fixture()
def sandbox(repo_root, tmp_path):
    """Copy of src/ and hosts/ that tests may mutate."""
    shutil.copytree(repo_root / "src", tmp_path / "src",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(repo_root / "hosts", tmp_path / "hosts")
    return tmp_path


def tree_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_build_expands_tokens(repo_root, tmp_path):
    out = tmp_path / "dist"
    r = build(repo_root, "--out", out)
    assert r.returncode == 0, r.stderr
    for host in HOSTS:
        skill = out / host / "skills" / "extract-structure" / "SKILL.md"
        assert skill.is_file()
        assert "{{" not in skill.read_text()


def test_host_specific_values(repo_root, tmp_path):
    out = tmp_path / "dist"
    assert build(repo_root, "--out", out).returncode == 0
    cc = (out / "claude-code/skills/extract-structure/SKILL.md").read_text()
    cx = (out / "codex/skills/extract-structure/SKILL.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/scripts" in cc and "${CLAUDE_PLUGIN_DATA}" in cc
    assert "$SKILL_DIR/scripts" in cx and "~/.cache/code-designer" in cx
    assert (out / "claude-code/scripts/cd_extract.py").is_file()
    assert (out / "claude-code/scripts/structure-model.schema.json").is_file()
    assert (out / "codex/skills/extract-structure/scripts/cd_extract.py").is_file()
    assert (out / "claude-code/knowledge/precedence.md").is_file()
    assert (out / "codex/knowledge/precedence.md").is_file()
    assert not list(out.rglob("__pycache__"))


def test_unknown_token_fails(repo_root, sandbox):
    md = sandbox / "src/skills/extract-structure/SKILL.md"
    md.write_text(md.read_text() + "\n{{NOPE}}\n")
    r = build(repo_root, "--src", sandbox / "src", "--hosts", sandbox / "hosts",
              "--out", sandbox / "dist")
    assert r.returncode != 0
    assert "NOPE" in r.stderr


def test_conditional_fails(repo_root, sandbox):
    md = sandbox / "src/skills/extract-structure/SKILL.md"
    md.write_text(md.read_text() + "\n{{#if x}}a{{/if}}\n")
    r = build(repo_root, "--src", sandbox / "src", "--hosts", sandbox / "hosts",
              "--out", sandbox / "dist")
    assert r.returncode != 0


def test_claude_env_vars_survive(repo_root, sandbox):
    md = sandbox / "src/skills/extract-structure/SKILL.md"
    md.write_text(md.read_text() + "\nLiteral ${CLAUDE_PLUGIN_ROOT}/x here\n")
    out = sandbox / "dist"
    r = build(repo_root, "--src", sandbox / "src", "--hosts", sandbox / "hosts", "--out", out)
    assert r.returncode == 0, r.stderr
    assert "Literal ${CLAUDE_PLUGIN_ROOT}/x here" in (
        out / "claude-code/skills/extract-structure/SKILL.md").read_text()


def test_deterministic_and_check(repo_root, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert build(repo_root, "--out", a).returncode == 0
    assert build(repo_root, "--out", b).returncode == 0
    assert tree_bytes(a) == tree_bytes(b)
    assert build(repo_root, "--check", "--out", a).returncode == 0
    victim = a / "codex/skills/extract-structure/SKILL.md"
    victim.write_text(victim.read_text() + "tampered\n")
    r = build(repo_root, "--check", "--out", a)
    assert r.returncode == 1
    assert "SKILL.md" in r.stdout + r.stderr


def test_check_detects_extra_and_missing(repo_root, tmp_path):
    out = tmp_path / "d"
    assert build(repo_root, "--out", out).returncode == 0
    (out / "claude-code/extra.txt").write_text("x")
    assert build(repo_root, "--check", "--out", out).returncode == 1
    (out / "claude-code/extra.txt").unlink()
    (out / "claude-code/scripts/cd_extract.py").unlink()
    assert build(repo_root, "--check", "--out", out).returncode == 1


def test_bump_version(repo_root, sandbox):
    shutil.copy(repo_root / "VERSION", sandbox / "VERSION")
    shutil.copy(repo_root / ".version-bump.json", sandbox / ".version-bump.json")
    (sandbox / "VERSION").write_text("0.2.7\n")
    r = run_py(repo_root / "scripts" / "bump_version.py", "--root", sandbox)
    assert r.returncode == 0, r.stderr
    for rel in ("hosts/claude-code/.claude-plugin/plugin.json",
                "hosts/codex/.codex-plugin/plugin.json"):
        assert json.loads((sandbox / rel).read_text())["version"] == "0.2.7"


def test_committed_manifests_in_sync(repo_root):
    v = (repo_root / "VERSION").read_text().strip()
    for rel in ("hosts/claude-code/.claude-plugin/plugin.json",
                "hosts/codex/.codex-plugin/plugin.json"):
        d = json.loads((repo_root / rel).read_text())
        assert d["version"] == v and d["name"] == "code-designer"


@pytest.mark.parametrize("rel", ["claude-code/scripts", "codex/skills/extract-structure/scripts"])
def test_built_extractor_runs(repo_root, grammar_cache, tmp_path, rel):
    out = tmp_path / "dist"
    assert build(repo_root, "--out", out).returncode == 0
    scripts = out / rel
    model = tmp_path / "model.json"
    r = run_py(scripts / "cd_extract.py", FIXTURE, "--cache-dir", grammar_cache,
               "--allow-download", "--out", model)
    assert r.returncode == 0, r.stderr
    v = run_py(scripts / "cd_validate.py", model)
    assert v.returncode == 0, v.stdout + v.stderr
    assert any(s["id"] == "shapes.py#Circle" for s in json.loads(model.read_text())["symbols"])
