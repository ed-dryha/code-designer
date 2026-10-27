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


FUTURES = FIX / "future-plans.md"
CONFIRMED = "P-add-provider-aaaaaa"


def _gate_fp(script, repo_root, repo, doc, futures=FUTURES, *extra):
    args = [script, doc, "--root", repo, "--model", FIX / "model.json", "--kb", repo_root / "src" / "knowledge",
            "--backlog", BACKLOG]
    if futures is not None:
        args += ["--futures", futures]
    return run_py(*args, *extra)


def test_plan_evidence_passes(script, repo_root, repo):
    r = _gate_fp(script, repo_root, repo, FIX / "good-with-plan.md")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("doc,status", [
    ("bad-plan-inferred.md", "plan-not-confirmed"),
    ("bad-plan-done.md", "plan-not-confirmed"),
    ("bad-plan-dropped.md", "plan-not-confirmed"),
    ("bad-plan-unknown.md", "unknown-plan"),
    ("bad-plan-only.md", "plan-without-citation"),
    ("bad-plans-used-unknown.md", "unknown-plan"),
    ("bad-plans-used-inferred.md", "plan-not-confirmed"),
])
def test_bad_plan_docs_fail(script, repo_root, repo, doc, status):
    r = _gate_fp(script, repo_root, repo, FIX / doc)
    assert r.returncode == 1, r.stdout + r.stderr
    assert status in _statuses(r)


def test_not_confirmed_detail_names_id_and_status(script, repo_root, repo):
    r = _gate_fp(script, repo_root, repo, FIX / "bad-plan-inferred.md")
    d = [x for x in json.loads(r.stdout) if x["status"] == "plan-not-confirmed"][0]["detail"]
    assert "P-inferred-bbbbbb" in d and "inferred" in d


def test_plan_excluded_stale(script, repo_root, repo):
    r = _gate_fp(script, repo_root, repo, FIX / "good-with-plan.md", FUTURES, "--exclude-plan", CONFIRMED)
    assert r.returncode == 1 and "plan-excluded-stale" in _statuses(r)


def test_bad_exclude_id_is_usage_error(script, repo_root, repo):
    r = _gate_fp(script, repo_root, repo, FIX / "good-with-plan.md", FUTURES, "--exclude-plan", "nope")
    assert r.returncode == 2


@pytest.fixture(params=["missing", "dir", "big", "garbled"])
def broken_futures(request, tmp_path):
    p = tmp_path / "fp.md"
    if request.param == "missing":
        return tmp_path / "nope.md"
    if request.param == "dir":
        p.mkdir()
    elif request.param == "big":
        p.write_text("# " + "x" * (1024 * 1024 + 1))
    else:
        p.write_text("---\nid: [unclosed\n")
    return p


def test_broken_futures_fail_closed(script, repo_root, repo, broken_futures):
    r = _gate_fp(script, repo_root, repo, FIX / "good-with-plan.md", broken_futures)
    assert r.returncode == 1 and "unknown-plan" in _statuses(r)


def test_broken_futures_ignored_without_plan_refs(script, repo_root, repo, broken_futures):
    assert _gate_fp(script, repo_root, repo, FIX / "good-adopt.md", broken_futures).returncode == 0


def test_default_futures_discovery(script, repo_root, repo):
    (repo / "docs" / "design").mkdir(parents=True)
    shutil.copy(FUTURES, repo / "docs" / "design" / "future-plans.md")
    r = run_py(script, FIX / "good-with-plan.md", "--root", repo, "--model", FIX / "model.json",
               "--kb", repo_root / "src" / "knowledge", "--backlog", BACKLOG)
    assert r.returncode == 0, r.stdout + r.stderr


def test_plans_used_section_optional(script, repo_root, repo):
    assert _gate_fp(script, repo_root, repo, FIX / "good-plans-used.md").returncode == 0
    assert _gate_fp(script, repo_root, repo, FIX / "good-plans-none.md").returncode == 0
    assert _gate_fp(script, repo_root, repo, FIX / "good-adopt.md").returncode == 0


def test_plans_used_excluded_stale(script, repo_root, repo):
    r = _gate_fp(script, repo_root, repo, FIX / "good-plans-used.md", FUTURES, "--exclude-plan", CONFIRMED)
    assert "plan-excluded-stale" in _statuses(r)
    assert any(x["check"] == "used-plan" and x["status"] == "plan-excluded-stale" for x in json.loads(r.stdout))


# ---- triage verdicts (TRIA-02) ----

def _no_blast_or_records(r):
    st = _statuses(r)
    return "no-records" not in st and "blast-missing-section" not in st


def test_triage_skip_stub_passes_without_records(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "good-skip-stub.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _no_blast_or_records(r)
    assert "checks pass" in r.stderr


def test_triage_skip_forced_override_passes(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "good-skip-forced.md")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("doc,status", [
    ("bad-skip-no-reasons.md", "triage-no-reasons"),
    ("bad-skip-tampered.md", "triage-signals-tampered"),
    ("bad-skip-contradicts.md", "skip-contradicts-signals"),
    ("bad-skip-bad-json.md", "triage-bad-signals"),
    ("bad-verdict-value.md", "triage-bad-verdict"),
    ("bad-override.md", "triage-bad-override"),
    ("bad-light-3-records.md", "light-too-many-records"),
    ("bad-light-contradicts.md", "verdict-contradicts-signals"),
])
def test_triage_bad_docs_fail_with_status(script, repo_root, repo, doc, status):
    r = _gate(script, repo_root, repo, FIX / doc)
    assert r.returncode == 1, r.stdout + r.stderr
    assert status in _statuses(r)


def test_triage_good_light_passes(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "good-light.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_triage_good_full_checked_as_before(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "good-full-triage.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_triage_full_zero_records_still_fails(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "bad-full-no-records.md")
    assert r.returncode == 1
    assert "no-records" in _statuses(r)


def test_triage_absent_unchanged_without_flag(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "good-no-pattern.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "triage-missing" not in _statuses(r)


def test_triage_require_flag_fails_when_missing(script, repo_root, repo):
    r = run_py(script, FIX / "good-no-pattern.md", "--root", repo, "--model", FIX / "model.json",
               "--kb", repo_root / "src" / "knowledge", "--require-triage")
    assert r.returncode == 1
    assert "triage-missing" in _statuses(r)


def test_triage_require_flag_passes_with_section(script, repo_root, repo):
    r = run_py(script, FIX / "good-skip-stub.md", "--root", repo, "--model", FIX / "model.json",
               "--kb", repo_root / "src" / "knowledge", "--require-triage")
    assert r.returncode == 0, r.stdout + r.stderr


# --- Availability and Spec Coverage (05-04) ---

SPEC = FIX / "spec.md"


@pytest.fixture()
def repo_spec(repo):
    shutil.copy(SPEC, repo / "spec.md")
    return repo


def _rows(r):
    return json.loads(r.stdout)


def test_availability_good_passes(script, repo_root, repo_spec):
    r = _gate(script, repo_root, repo_spec, FIX / "good-availability.md")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("doc,status", [
    ("bad-availability-missing-row.md", "availability-missing-row"),
    ("bad-availability-no-section.md", "availability-missing-section"),
    ("bad-availability-empty.md", "availability-empty"),
])
def test_availability_bad_docs_fail(script, repo_root, repo_spec, doc, status):
    r = _gate(script, repo_root, repo_spec, FIX / doc)
    assert r.returncode == 1
    assert status in _statuses(r)


def test_availability_missing_row_names_field(script, repo_root, repo_spec):
    r = _gate(script, repo_root, repo_spec, FIX / "bad-availability-missing-row.md")
    bad = [x for x in _rows(r) if x["status"] == "availability-missing-row"]
    assert "regionCoverage" in bad[0]["detail"]


@pytest.mark.parametrize("doc", ["good-availability-class-only.md", "good-availability-modified.md"])
def test_availability_not_required(script, repo_root, repo_spec, doc):
    r = _gate(script, repo_root, repo_spec, FIX / doc)
    assert r.returncode == 0, r.stdout + r.stderr


def test_availability_no_chosen_design_unaffected(script, repo_root, repo):
    r = _gate(script, repo_root, repo, FIX / "good-no-pattern.md")
    assert r.returncode == 0
    assert not [s for s in _statuses(r) if s.startswith("availability")]


def test_spec_coverage_good_passes(script, repo_root, repo_spec):
    r = _gate(script, repo_root, repo_spec, FIX / "good-spec-coverage.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_spec_coverage_via_spec_flag(script, repo_root, repo):
    shutil.copy(SPEC, repo / "other-spec.md")
    text = (FIX / "good-spec-coverage.md").read_text().replace("Spec: spec.md", "Spec: none")
    doc = repo / "doc.md"
    doc.write_text(text)
    r = run_py(script, doc, "--root", repo, "--model", FIX / "model.json",
               "--kb", repo_root / "src" / "knowledge", "--spec", "other-spec.md")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("doc,status", [
    ("bad-coverage-line-range.md", "coverage-bad-line"),
    ("bad-coverage-blank-line.md", "coverage-bad-line"),
    ("bad-coverage-unknown-dr.md", "coverage-unknown-dr"),
    ("bad-coverage-unmapped.md", "coverage-unmapped"),
    ("bad-coverage-no-reason.md", "coverage-no-reason"),
    ("bad-coverage-quote.md", "coverage-quote-mismatch"),
    ("bad-coverage-no-section.md", "coverage-missing-section"),
])
def test_spec_coverage_bad_docs_fail(script, repo_root, repo_spec, doc, status):
    r = _gate(script, repo_root, repo_spec, FIX / doc)
    assert r.returncode == 1
    assert status in _statuses(r)


def test_spec_coverage_unlisted_lines_do_not_fail(script, repo_root, repo_spec):
    r = _gate(script, repo_root, repo_spec, FIX / "good-spec-coverage.md")
    assert r.returncode == 0  # lines 7-12 of the spec are not listed


@pytest.mark.parametrize("doc", ["good-coverage-spec-none.md", "good-coverage-spec-missing.md"])
def test_spec_coverage_skipped_without_spec(script, repo_root, repo_spec, doc):
    r = _gate(script, repo_root, repo_spec, FIX / doc)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not [s for s in _statuses(r) if s.startswith("coverage")]


def test_spec_coverage_dotdot_path_rejected(script, repo_root, repo_spec):
    r = _gate(script, repo_root, repo_spec, FIX / "bad-coverage-path-escape.md")
    assert r.returncode == 1
    bad = [x for x in _rows(r) if x["status"] == "coverage-bad-line"]
    assert bad and bad[0]["detail"] == "path-escape"


def test_spec_coverage_symlink_escape_rejected(script, repo_root, repo, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text(SPEC.read_text())
    (repo / "spec.md").symlink_to(outside)
    r = _gate(script, repo_root, repo, FIX / "good-spec-coverage.md")
    assert r.returncode == 1
    bad = [x for x in _rows(r) if x["status"] == "coverage-bad-line"]
    assert bad and bad[0]["detail"] == "path-escape"


def test_spec_coverage_skip_stub_exempt(script, repo_root, repo_spec):
    r = _gate(script, repo_root, repo_spec, FIX / "good-skip-stub.md")
    assert r.returncode == 0
    assert not [s for s in _statuses(r) if s.startswith("coverage")]


def test_spec_coverage_quote_normalizes_whitespace(script, repo_root, repo_spec):
    # fixture row quotes "quick  brown fox" (double space) against "quick brown fox"
    r = _gate(script, repo_root, repo_spec, FIX / "good-spec-coverage.md")
    assert "coverage-quote-mismatch" not in _statuses(r)
