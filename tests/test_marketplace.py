"""Root marketplace manifests: generation, checking, committed state, CI coverage."""
import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import run_py

CC = ".claude-plugin/marketplace.json"
CX = ".agents/plugins/marketplace.json"


def build(repo_root, *args):
    return run_py(repo_root / "scripts" / "build.py", *args)


@pytest.fixture()
def built(repo_root, tmp_path):
    out, mk = tmp_path / "dist", tmp_path / "root"
    r = build(repo_root, "--out", out, "--market-out", mk)
    assert r.returncode == 0, r.stderr
    return out, mk


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_manifests_generated(built):
    _, mk = built
    cc, cx = load(mk / CC), load(mk / CX)
    assert cc["name"] and cc["owner"]["name"]
    p = cc["plugins"][0]
    assert p["name"] == "code-designer" and p["source"] == "./dist/claude-code"
    assert p["description"] and p["category"]
    assert cx["name"] and cx["interface"]["displayName"]
    q = cx["plugins"][0]
    assert q["source"] == {"source": "local", "path": "./dist/codex"}
    assert q["policy"]["installation"] == "AVAILABLE"
    assert q["policy"]["authentication"] == "ON_INSTALL"
    assert q["category"]
    assert "version" not in p and "version" not in q


def test_paths_safe_and_names_match_hosts(repo_root, built):
    _, mk = built
    cc, cx = load(mk / CC), load(mk / CX)
    src_cc = cc["plugins"][0]["source"]
    src_cx = cx["plugins"][0]["source"]["path"]
    for s in (src_cc, src_cx):
        assert s.startswith("./") and ".." not in s
    hn_cc = load(repo_root / "hosts/claude-code/.claude-plugin/plugin.json")["name"]
    hn_cx = load(repo_root / "hosts/codex/.codex-plugin/plugin.json")["name"]
    assert cc["plugins"][0]["name"] == hn_cc
    assert cx["plugins"][0]["name"] == hn_cx


def test_deterministic_lf(repo_root, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for m in (a, b):
        assert build(repo_root, "--out", tmp_path / "d", "--market-out", m).returncode == 0
    for rel in (CC, CX):
        da, db = (a / rel).read_bytes(), (b / rel).read_bytes()
        assert da == db and da.endswith(b"\n") and not da.endswith(b"\n\n")
        assert b"\r" not in da


def test_default_skips_manifests(repo_root, tmp_path):
    before = {rel: (repo_root / rel).read_bytes() for rel in (CC, CX)}
    r = build(repo_root, "--out", tmp_path / "dist")
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / ".claude-plugin").exists()
    assert not (tmp_path / ".agents").exists()
    assert not list(tmp_path.rglob("marketplace.json"))
    assert {rel: (repo_root / rel).read_bytes() for rel in (CC, CX)} == before


def test_check_coverage(repo_root, built):
    out, mk = built
    args = ("--check", "--out", out, "--market-out", mk)
    assert build(repo_root, *args).returncode == 0
    f = mk / CC
    orig = f.read_bytes()
    f.write_bytes(orig + b" ")
    r = build(repo_root, *args)
    assert r.returncode == 1 and "differs" in r.stdout
    f.write_bytes(orig)
    f.unlink()
    r = build(repo_root, *args)
    assert r.returncode == 1 and "missing" in r.stdout
    f.write_bytes(orig)
    (mk / ".agents/plugins/extra.json").write_text("{}")
    r = build(repo_root, *args)
    assert r.returncode == 1 and "extra" in r.stdout


def test_committed_state(repo_root):
    assert build(repo_root, "--check").returncode == 0
    cc, cx = load(repo_root / CC), load(repo_root / CX)
    d1 = repo_root / cc["plugins"][0]["source"]
    d2 = repo_root / cx["plugins"][0]["source"]["path"]
    assert (d1 / ".claude-plugin/plugin.json").is_file()
    assert (d2 / ".codex-plugin/plugin.json").is_file()
    for rel in (CC, CX):
        assert '"version"' not in (repo_root / rel).read_text()


def test_config_keys(repo_root):
    cfg = load(repo_root / "marketplace.config.json")
    assert cfg["ownerName"] and cfg["githubRepo"]
    repo = cfg["githubRepo"]
    assert repo == "TODO-OWNER/TODO-REPO" or re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", repo)


def test_missing_config_key_exits_2(repo_root, tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"githubRepo": "a/b"}))
    r = build(repo_root, "--out", tmp_path / "d", "--market-out", tmp_path / "m",
              "--config", cfg)
    assert r.returncode == 2 and "ownerName" in r.stderr


def test_plain_build_has_only_host_dirs(repo_root, tmp_path):
    out = tmp_path / "dist"
    assert build(repo_root, "--out", out).returncode == 0
    assert sorted(p.name for p in out.iterdir()) == ["claude-code", "codex"]


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_claude_validate(repo_root):
    import subprocess
    r = subprocess.run(["claude", "plugin", "validate", str(repo_root)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_ci_covers_root_manifests(repo_root):
    text = (repo_root / ".github/workflows/ci.yml").read_text()
    step = text.split("Rebuild and verify committed dist is current")[1].split("- name:")[0]
    assert ".claude-plugin/" in step and ".agents/" in step
    assert "claude plugin validate ." in text
