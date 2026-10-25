"""Opt-in SessionStart nudge hook (Claude Code only)."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from conftest import run_py


def hook_dir(root):
    return root / "hosts" / "claude-code" / "hooks"


def run_nudge(root, **env_over):
    env = {k: v for k, v in os.environ.items() if k != "CODE_DESIGNER_NUDGE"}
    env.update(env_over)
    return subprocess.run(["bash", str(hook_dir(root) / "nudge.sh")],
                          capture_output=True, text=True, env=env)


def test_silent_by_default(repo_root):
    r = run_nudge(repo_root)
    assert r.returncode == 0 and r.stdout == ""


def test_zero_silent_and_one_emits(repo_root):
    r0 = run_nudge(repo_root, CODE_DESIGNER_NUDGE="0")
    assert r0.returncode == 0 and r0.stdout == ""
    r1 = run_nudge(repo_root, CODE_DESIGNER_NUDGE="1")
    assert r1.returncode == 0
    out = json.loads(r1.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    ctx = out["additionalContext"]
    assert "code-designer:design" in ctx and "superpowers:writing-plans" in ctx
    assert len(ctx) < 1000


def test_hooks_json(repo_root):
    data = json.loads((hook_dir(repo_root) / "hooks.json").read_text())
    entry = data["hooks"]["SessionStart"][0]
    assert "startup" in entry["matcher"]
    assert entry["hooks"][0]["command"] == 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/nudge.sh"'


def test_build_ships_claude_code_only(repo_root, tmp_path):
    out = tmp_path / "dist"
    r = run_py(repo_root / "scripts" / "build.py", "--out", out)
    assert r.returncode == 0, r.stderr
    assert (out / "claude-code/hooks/hooks.json").is_file()
    assert (out / "claude-code/hooks/nudge.sh").is_file()
    assert not list((out / "codex").rglob("nudge.sh"))
    assert not list((out / "codex").rglob("hooks.json"))


def test_static_output(repo_root):
    text = (hook_dir(repo_root) / "nudge.sh").read_text()
    assert "jq" not in text
    body = [l for l in text.splitlines() if "additionalContext" in l]
    assert body and all("$" not in l for l in body)
