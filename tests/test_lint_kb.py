import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LINT = ROOT / "scripts" / "lint_kb.py"
GOOD = ROOT / "tests" / "fixtures" / "kb" / "good"


def run(kb, *args):
    p = subprocess.run([sys.executable, str(LINT), str(kb), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


@pytest.fixture
def kb(tmp_path):
    dst = tmp_path / "kb"
    shutil.copytree(GOOD, dst)
    return dst


def edit(path, old, new):
    t = path.read_text()
    assert old in t
    path.write_text(t.replace(old, new))


def test_good(kb):
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 0, out


def test_missing_key(kb):
    edit(kb / "patterns/pattern-y.md", "cost: low\n", "")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "missing-key" in out


def test_empty_required_evidence(kb):
    edit(kb / "patterns/pattern-y.md",
         "required_evidence:\n  - a switch over a type field in a cited method\n",
         "required_evidence: []\n")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "empty-required_evidence" in out


def test_empty_anti_signals(kb):
    edit(kb / "patterns/pattern-y.md",
         "anti_signals:\n  - only one variant exists\n", "anti_signals: []\n")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "empty-anti_signals" in out


def test_dangling_link(kb):
    edit(kb / "smells/smell-x.md", "patterns: [pattern-y]", "patterns: [pattern-nope]")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "dangling-link" in out


def test_smell_no_principle(kb):
    edit(kb / "smells/smell-x.md", "principles: [principle-kiss]", "principles: []")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "smell-no-principle" in out


def test_orphan_pattern(kb):
    edit(kb / "smells/smell-x.md", "patterns: [pattern-y]", "patterns: []")
    edit(kb / "patterns/pattern-y.md", "smells: [smell-x]", "smells: []")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "orphan-pattern" in out


def test_pattern_reachable_via_smell_only(kb):
    edit(kb / "patterns/pattern-y.md", "smells: [smell-x]", "smells: []")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 0, out


def test_duplicate_id(kb):
    shutil.copy(kb / "smells/smell-x.md", kb / "smells/smell-z.md")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "duplicate-id" in out


def test_precedence_reference(kb):
    edit(kb / "patterns/pattern-y.md", "precedence: ../precedence.md", "precedence: ../other.md")
    edit(kb / "patterns/pattern-y.md", "See ../precedence.md first.", "")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 1 and "precedence-ref" in out


def test_pattern_count(kb):
    code, out = run(kb, "--expect-patterns", "2")
    assert code == 1 and "pattern-count" in out


def test_default_expects_23(kb):
    code, out = run(kb)
    assert code == 1 and "pattern-count" in out


def test_skips_precedence_and_readme(kb):
    (kb / "README.md").write_text("# no frontmatter\n")
    code, out = run(kb, "--expect-patterns", "1")
    assert code == 0, out


def test_allow_missing_patterns(kb):
    (kb / "patterns/pattern-y.md").unlink()
    code, out = run(kb, "--expect-patterns", "0", "--allow-missing-patterns")
    assert code == 0, out
    code, out = run(kb, "--expect-patterns", "0")
    assert code == 1 and "dangling-link" in out
