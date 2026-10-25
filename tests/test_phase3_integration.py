"""Whole-phase-3 acceptance over the BUILT dist trees."""
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
GENV = {
    "GIT_AUTHOR_DATE": "2026-01-01T10:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T10:00:00+00:00",
}
TITLE = "Add a second payment provider"


def git(root, *args, date=None):
    env = os.environ.copy()
    env.update(GENV)
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(root), *args],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture(params=sorted(TREES))
def tree(request, repo_root):
    return request.param, repo_root / "dist" / request.param


def test_built_trees_have_futures(tree):
    name, base = tree
    for skill in ("futures", "design"):
        assert (base / "skills" / skill / "SKILL.md").is_file()
    assert (base / "skills" / "futures" / "FUTURES-FORMAT.md").is_file()
    sdir = base / TREES[name]
    assert (sdir / "cd_futures.py").is_file()
    for f in base.rglob("*"):
        if f.is_file() and f.suffix in {".md", ".json", ".sh", ".py", ".scm"}:
            assert "{{" not in f.read_text(encoding="utf-8", errors="ignore"), f
    for skill in ("futures", "design"):
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


def test_futures_to_gate_end_to_end(tree, tmp_path):
    name, base = tree
    s = base / TREES[name]
    kb = base / "knowledge"
    repo = tmp_path / "repo"
    shutil.copytree(FIX / "design" / "pay", repo / "pay")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init: seed repo")
    head = git(repo, "rev-parse", "HEAD")
    model = FIX / "design" / "model.json"

    pid = run_py(s / "cd_futures.py", "id", "--title", TITLE).stdout.strip()
    assert pid.startswith("P-")

    def write(data):
        p = tmp_path / "in.json"
        p.write_text(json.dumps(data))
        return p

    cands = {"candidates": [{
        "title": TITLE, "confidence": "medium", "affected": ["pay/service.py"],
        "source": [{"type": "commit", "ref": head, "quote": "init"}]}]}
    plans = repo / "docs" / "design" / "future-plans.md"

    r = run_py(s / "cd_futures.py", "propose", "--root", repo, "--input", write(cands))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "+++ future-plans.md (proposed)" in r.stdout
    assert not plans.exists()
    sha = re.search(r"^expect-sha: (\w*)$", r.stdout, re.M).group(1)

    r = run_py(s / "cd_futures.py", "apply", "--root", repo, "--input", write(cands),
               "--expect-sha", sha, "--date", "2026-01-01")
    assert r.returncode == 0, r.stdout + r.stderr
    assert plans.is_file()
    assert run_py(s / "cd_futures.py", "lint", plans, "--root", repo).returncode == 0

    doc_text = (FIX / "design" / "good-with-plan.md").read_text(encoding="utf-8")
    doc_text = doc_text.replace("P-add-provider-aaaaaa", pid)
    doc = tmp_path / "doc.md"
    doc.write_text(doc_text, encoding="utf-8")

    def gate(*extra):
        return run_py(s / "cd_gate.py", doc, "--root", repo, "--model", model, "--kb", kb,
                      "--futures", plans, *extra)

    r = gate()
    assert r.returncode == 1 and "plan-not-confirmed" in r.stdout + r.stderr

    decide = {"decisions": [{"id": pid, "action": "confirm", "answer": "yes"}]}
    r = run_py(s / "cd_futures.py", "propose", "--root", repo, "--input", write(decide))
    sha = re.search(r"^expect-sha: (\w*)$", r.stdout, re.M).group(1)
    r = run_py(s / "cd_futures.py", "apply", "--root", repo, "--input", write(decide),
               "--expect-sha", sha, "--date", "2026-01-02")
    assert r.returncode == 0, r.stdout + r.stderr

    r = gate()
    assert r.returncode == 0, r.stdout + r.stderr
    r = gate("--exclude-plan", pid)
    assert r.returncode == 1 and "plan-excluded-stale" in r.stdout + r.stderr

    f = repo / "pay" / "service.py"
    f.write_text(f.read_text() + "\n# touched\n")
    git(repo, "add", "pay/service.py")
    git(repo, "commit", "-q", "-m", "rework service", date="2026-03-01T10:00:00+00:00")
    out = json.loads(run_py(s / "cd_futures.py", "stale", "--root", repo).stdout)
    assert [x["id"] for x in out["stale"]] == [pid]


def test_build_check(repo_root):
    r = run_py(repo_root / "scripts" / "build.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_success_criteria_trace(repo_root):
    def has(rel, *needles):
        text = (repo_root / rel).read_text(encoding="utf-8")
        return all(n in text for n in needles)

    checks = {
        1: has("src/skills/futures/SKILL.md", "future-plans.md", "propose", "apply"),
        2: has("src/extractor/cd_futures.py", "propose", "apply", "expect-sha"),
        3: has("src/extractor/cd_gate.py", "plan-not-confirmed", "plan-excluded-stale"),
        4: has("src/skills/design/SKILL.md", "cd_futures.py", "stale", "--exclude-plan"),
        5: (repo_root / ".claude-plugin" / "marketplace.json").is_file()
        and (repo_root / ".agents" / "plugins" / "marketplace.json").is_file(),
    }
    for n, ok in checks.items():
        assert ok, f"Phase 3 success criterion {n} has no implementing artifact"
