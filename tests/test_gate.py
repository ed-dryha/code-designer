"""Design-doc evidence gate: passing docs and every defect class."""
import json
import shutil
from pathlib import Path

import pytest

from conftest import run_py

FIX = Path(__file__).parent / "fixtures" / "design"


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_gate.py"


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(FIX / "pay", root / "pay")
    return root


def _gate(script, repo_root, repo, doc, model=FIX / "model.json"):
    return run_py(script, doc, "--root", repo, "--model", model, "--kb", repo_root / "src" / "knowledge")


def _statuses(r):
    return [x["status"] for x in json.loads(r.stdout)]


def test_good_adopt_passes(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "good-adopt.md")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out and all({"record", "check", "status"} <= set(x) for x in out)
    assert "checks pass" in r.stderr


def test_good_no_pattern_passes(script, repo_root, repo):
    text = (FIX / "good-no-pattern.md").read_text()
    assert "verdict: no-pattern" in text and "verdict: adopt" not in text
    r = _gate(script, repo_root, repo, FIX / "good-no-pattern.md")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("doc,status", [
    ("bad-no-do-nothing.md", "no-do-nothing"),
    ("bad-adopt-no-evidence.md", "no-evidence"),
    ("bad-agent-only.md", "no-tree-sitter-evidence"),
    ("bad-drifted-quote.md", "quote-mismatch"),
    ("bad-unknown-kb.md", "unknown-kb-id"),
    ("bad-smell-not-linked.md", "smell-not-linked"),
    ("bad-empty-reason.md", "empty-reason"),
    ("bad-verdict.md", "bad-verdict"),
    ("bad-yaml.md", "yaml-error"),
    ("bad-missing-field.md", "missing-field"),
    ("bad-no-records.md", "no-records"),
    ("bad-path-escape.md", "path-escape"),
    ("bad-blast-no-section.md", "blast-missing-section"),
    ("bad-blast-no-unverified.md", "blast-missing-section"),
    ("bad-blast-untagged.md", "blast-untagged"),
    ("bad-blast-bad-citation.md", "blast-bad-citation"),
    ("bad-blast-no-scope.md", "blast-no-scope"),
])
def test_bad_docs_fail(script, repo_root, repo, doc, status):
    r = _gate(script, repo_root, repo, FIX / doc)
    assert r.returncode == 1, r.stdout + r.stderr
    assert status in _statuses(r)


def test_yaml_error_has_line(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "bad-yaml.md")
    err = [x for x in json.loads(r.stdout) if x["status"] == "yaml-error"][0]
    assert "line" in json.dumps(err)


def test_usage_errors(script, repo_root, repo, tmp_path):
    assert run_py(script).returncode == 2
    r = _gate(script, repo_root, repo, tmp_path / "missing.md")
    assert r.returncode == 2
    r = _gate(script, repo_root, repo, FIX / "good-adopt.md", model=tmp_path / "nope.json")
    assert r.returncode == 2


def test_oversize_doc_rejected(script, repo_root, repo, tmp_path):
    big = tmp_path / "big.md"
    big.write_text("x" * (1024 * 1024 + 1))
    assert _gate(script, repo_root, repo, big).returncode == 2


def test_blast_good_docs_have_blast_checks(script, repo_root, repo):
    out = json.loads(_gate(script, repo_root, repo, FIX / "good-adopt.md").stdout)
    assert [x for x in out if x["check"].startswith("blast")]


def test_unverified_item_needs_reason(script, repo_root, repo, tmp_path):
    doc = tmp_path / "d.md"
    doc.write_text((FIX / "good-no-pattern.md").read_text().replace(" reason: common-name", " common-name"))
    r = _gate(script, repo_root, repo, doc)
    assert r.returncode == 1 and "unverified-no-reason" in _statuses(r)


def test_unverified_none_found_passes(script, repo_root, repo, tmp_path):
    doc = tmp_path / "d.md"
    text = (FIX / "good-no-pattern.md").read_text()
    head = text[:text.index("## Unverified / Possible")]
    doc.write_text(head + "## Unverified / Possible\n\nNone found\n")
    r = _gate(script, repo_root, repo, doc)
    assert r.returncode == 0, r.stdout


BACKLOG = FIX / "backlog.md"


def _gate_bl(script, repo_root, repo, doc, backlog=BACKLOG):
    args = [script, doc, "--root", repo, "--model", FIX / "model.json", "--kb", repo_root / "src" / "knowledge"]
    if backlog is not None:
        args += ["--backlog", backlog]
    return run_py(*args)


def test_finding_evidence_passes(script, repo_root, repo):
    r = _gate_bl(script, repo_root, repo, FIX / "good-with-finding.md")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("doc,status", [
    ("bad-finding-unknown.md", "unknown-finding"),
    ("bad-finding-resolved.md", "resolved-finding"),
    ("bad-finding-only.md", "finding-without-citation"),
    ("bad-touched-unknown.md", "unknown-finding"),
])
def test_bad_finding_docs_fail(script, repo_root, repo, doc, status):
    r = _gate_bl(script, repo_root, repo, FIX / doc)
    assert r.returncode == 1, r.stdout + r.stderr
    assert status in _statuses(r)


def test_finding_without_backlog_file_fails(script, repo_root, repo):
    r = _gate_bl(script, repo_root, repo, FIX / "good-with-finding.md", backlog=None)
    assert r.returncode == 1 and "unknown-finding" in _statuses(r)


def test_no_finding_refs_pass_with_or_without_backlog(script, repo_root, repo):
    assert _gate_bl(script, repo_root, repo, FIX / "good-adopt.md").returncode == 0
    assert _gate_bl(script, repo_root, repo, FIX / "good-adopt.md", backlog=None).returncode == 0
    assert _gate_bl(script, repo_root, repo, FIX / "good-touched-none.md").returncode == 0
