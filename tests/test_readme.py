"""README accuracy: install lines must match the generated manifests and config."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Output paths the README documents that do not exist in this repo.
ALLOWED_OUTPUTS = {
    "docs/design/future-plans.md",
    "docs/design/backlog.md",
    "docs/design/",
    "docs/superpowers/specs/",
}


@pytest.fixture(scope="module")
def readme():
    p = ROOT / "README.md"
    assert p.is_file()
    return p.read_text(encoding="utf-8")


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_headings(readme):
    heads = [l.lstrip("# ").strip().lower() for l in readme.splitlines() if l.startswith("#")]
    for needle in ("install", "quickstart", "trigger setup", "skills", "requirements", "known limits"):
        assert any(needle in h for h in heads), needle


def test_install_lines_match_manifests(readme):
    cc = load(".claude-plugin/marketplace.json")
    cx = load(".agents/plugins/marketplace.json")
    cfg = load("marketplace.config.json")
    plugin = cc["plugins"][0]["name"]
    assert cx["plugins"][0]["name"] == plugin
    assert f"claude plugin install {plugin}@{cc['name']}" in readme
    assert "claude plugin marketplace add" in readme
    assert "codex plugin marketplace add" in readme
    assert f"codex plugin add {plugin}@{cx['name']}" in readme
    repo = cfg["githubRepo"]
    assert f"claude plugin marketplace add {repo}" in readme
    assert f"codex plugin marketplace add {repo}" in readme


def test_mentions(readme):
    for d in (ROOT / "src" / "skills").iterdir():
        if d.is_dir():
            assert d.name in readme, d.name
    for s in ("uv", "superpowers", "docs/design/future-plans.md", "docs/design/backlog.md",
              "CODE_DESIGNER_NUDGE", "--interview", "sandbox", "uv cache"):
        assert s in readme, s
    assert "--additive" not in readme and "at most 2" not in readme
    assert "codex plugin --help" in readme or "verified" in readme.lower()


def test_no_emoji_or_emdash_or_home_paths(readme):
    assert "—" not in readme
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", readme)
    assert "/Users/" not in readme and "/home/" not in readme


def test_paths_exist_or_allowed(readme):
    for m in re.findall(r"`((?:docs|src|dist)/[^`\s]*)`", readme):
        if "<" in m:
            continue
        assert m in ALLOWED_OUTPUTS or (ROOT / m).exists(), m


def test_phase5_readme_content(readme):
    low = readme.lower()
    for s in ("triage", "skip", "light", "full", "grep checklist", "availability", "spec coverage"):
        assert s in low, s
    assert "swift" in low and "grammar" in low
    for s in ("signalsSha", "--edit", "06-CALIBRATION.md"):
        assert s in readme, s
