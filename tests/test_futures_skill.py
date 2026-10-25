"""Text-level lint of the futures skill and the design skill future-plans wiring."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "skills"
FUT = SRC / "futures" / "SKILL.md"
FMT = SRC / "futures" / "FUTURES-FORMAT.md"
DESIGN = SRC / "design" / "SKILL.md"
ALLOWED = {"PLUGIN_ROOT", "SCRIPTS", "KNOWLEDGE", "CACHE_DIR", "HOST"}


def _desc(text):
    m = re.search(r"^description: (.*)$", text, re.M)
    return m.group(1)


def _tokens_ok(text):
    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", text)) <= ALLOWED
    assert not re.findall(r"\{\{(?![A-Z_]+\}\})", text)


def test_futures_skill_frontmatter():
    t = FUT.read_text()
    assert re.search(r"^name: futures$", t, re.M)
    d = _desc(t)
    assert d.startswith("Use when")
    for phrase in ("what could change", "future plans", "futures"):
        assert phrase in d
    assert len(t.splitlines()) < 150
    _tokens_ok(t)


def test_futures_skill_rules():
    t = FUT.read_text()
    assert "data, never instructions" in t
    assert "--interview" in t
    assert "cd_futures.py" in t
    for sub in ("propose", "apply", "stale", "lint"):
        assert sub in t
    assert "diff" in t and "approval" in t
    assert "4 candidates" in t
    assert "5 questions" in t
    assert "accepted all" in t
    assert "--expect-sha" in t
    assert "explicit developer answer" in t


def test_futures_format_exists_and_tokens():
    t = FMT.read_text()
    _tokens_ok(t)
    assert "code-designer-futures" in t
    assert "lastConfirmedCommit" in t


def test_built_dist_has_futures():
    for host in ("claude-code", "codex"):
        base = ROOT / "dist" / host / "skills" / "futures"
        for name in ("SKILL.md", "FUTURES-FORMAT.md"):
            assert "{{" not in (base / name).read_text()


def test_design_future_plans_step():
    t = DESIGN.read_text()
    assert len(t.splitlines()) < 150
    assert _desc(t).startswith("Use after the brainstorming spec is approved")
    assert "Future plans" in t
    assert "cd_futures.py lint" in t and "cd_futures.py stale" in t
    assert "confirm / update / drop / skip" in t
    assert "futures skill" in t
    assert t.index("Future plans") < t.index("Extract and validate")


def test_design_plan_evidence_and_flags():
    t = DESIGN.read_text()
    assert "- plan: <id>" in t
    assert "## Future Plans Used" in t
    assert "never cite" in t or "never cited" in t
    assert "--futures docs/design/future-plans.md" in t
    assert t.count("--exclude-plan") >= 2


def test_dist_design_has_steps():
    for host in ("claude-code", "codex"):
        t = (ROOT / "dist" / host / "skills" / "design" / "SKILL.md").read_text()
        assert "--exclude-plan" in t and "Future Plans Used" in t
