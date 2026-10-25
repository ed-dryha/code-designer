"""Guards for the design-stage trigger strength (plan 02-12, D-13/D-14/D-15)."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from conftest import run_py

ALLOWED = {"PLUGIN_ROOT", "SCRIPTS", "KNOWLEDGE", "CACHE_DIR", "HOST"}


def _fm(text):
    assert text.startswith("---\n")
    end = text.index("\n---", 4)
    fm = {}
    for ln in text[4:end].split("\n"):
        k, _, v = ln.partition(":")
        fm[k.strip()] = v.strip()
    return fm


def _norm(s):
    return re.sub(r"\s+", " ", s)


def _nudge(root, **env_over):
    env = {k: v for k, v in os.environ.items() if k != "CODE_DESIGNER_NUDGE"}
    env.update(env_over)
    return subprocess.run(["bash", str(root / "hosts/claude-code/hooks/nudge.sh")],
                          capture_output=True, text=True, env=env)


def _nudge_ctx(root):
    r = _nudge(root, CODE_DESIGNER_NUDGE="1")
    assert r.returncode == 0
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def _first_block(root):
    text = (root / "src/skills/design/NUDGE-SNIPPET.md").read_text()
    m = re.search(r"```[^\n]*\n(.*?)```", text, re.S)
    assert m, "no fenced block in NUDGE-SNIPPET.md"
    return _norm(m.group(1))


def test_design_description_is_imperative(repo_root):
    d = _fm((repo_root / "src/skills/design/SKILL.md").read_text())["description"]
    assert d.startswith("Use after the brainstorming spec is approved")
    assert "MUST" in d
    assert "even when" in d and "next step" in d
    assert d.count("writing-plans") >= 2
    assert len(d) <= 1024
    assert ": " not in d
    assert "standalone" in d


def test_nudge_wording(repo_root):
    ctx = _nudge_ctx(repo_root)
    low = ctx.lower()
    assert "code-designer:design" in ctx and "superpowers:writing-plans" in ctx
    assert "do not" in low and "even though" in low
    assert "Spec" in ctx
    assert len(ctx) < 1000


def test_nudge_still_opt_in(repo_root):
    for env in ({}, {"CODE_DESIGNER_NUDGE": "0"}):
        r = _nudge(repo_root, **env)
        assert r.returncode == 0 and r.stdout == ""


def test_hooks_json_only_sessionstart(repo_root):
    data = json.loads((repo_root / "hosts/claude-code/hooks/hooks.json").read_text())
    assert list(data["hooks"].keys()) == ["SessionStart"]
    entries = data["hooks"]["SessionStart"]
    assert len(entries) == 1 and len(entries[0]["hooks"]) == 1
    assert entries[0]["hooks"][0]["command"] == 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/nudge.sh"'


def test_snippet_doc(repo_root):
    text = (repo_root / "src/skills/design/NUDGE-SNIPPET.md").read_text()
    block = _first_block(repo_root).lower()
    assert "do not" in block
    assert "code-designer:design" in block and "superpowers:writing-plans" in block
    assert '"CODE_DESIGNER_NUDGE": "1"' in text
    assert "unverified" not in text.lower()
    assert "trigger-setup" in text


def test_snippet_nudge_consistency(repo_root):
    key = "invoke code-designer:design"
    assert key in _nudge_ctx(repo_root).lower()
    assert key in _first_block(repo_root).lower()


def test_trigger_setup_skill(repo_root):
    path = repo_root / "src/skills/trigger-setup/SKILL.md"
    assert path.is_file()
    text = path.read_text()
    fm = _fm(text)
    assert fm["name"] == "trigger-setup"
    assert fm.get("disable-model-invocation") == "true"
    for needle in ("CLAUDE.md", "AGENTS.md", "NUDGE-SNIPPET.md",
                   "code-designer:trigger", "confirm"):
        assert needle in text, needle
    assert re.search(r"never[^.\n]*superpowers", text, re.I)
    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", text)) <= ALLOWED
    assert not re.findall(r"\{\{(?![A-Z_]+\}\})", text)
    assert len(text.splitlines()) < 150


def test_built_output(repo_root, tmp_path):
    out = tmp_path / "dist"
    r = run_py(repo_root / "scripts" / "build.py", "--out", out)
    assert r.returncode == 0, r.stderr
    for host in ("claude-code", "codex"):
        ts = out / host / "skills/trigger-setup/SKILL.md"
        assert ts.is_file()
        assert (out / host / "skills/design/NUDGE-SNIPPET.md").is_file()
        t = ts.read_text()
        assert "NUDGE-SNIPPET.md" in t and "{{" not in t
    assert (out / "codex/skills/trigger-setup/agents/openai.yaml").is_file()
    assert not list((out / "codex").rglob("hooks.json"))
    assert not list((out / "codex").rglob("nudge.sh"))
