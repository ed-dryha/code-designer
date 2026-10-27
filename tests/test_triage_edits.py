"""Schema-2 triage: fixtures, collect2/decide2, CLI."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from triage_v2_fixtures import CASES, make_fixture

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "src" / "schema"
                     / "structure-model.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(CASES))
def test_fixture_builds_and_validates(tmp_path, name):
    root = make_fixture(tmp_path, name)
    assert (root / "spec.md").is_file()
    model = json.loads((root / "model.json").read_text(encoding="utf-8"))
    Draft202012Validator(SCHEMA).validate(model)
    assert len(CASES) == 13


def test_fixture_is_deterministic(tmp_path):
    a = make_fixture(tmp_path / "a", "variation-2-subtypes")
    b = make_fixture(tmp_path / "b", "variation-2-subtypes")
    assert (a / "model.json").read_text() == (b / "model.json").read_text()


# ---------------------------------------------------------------- collect2 / decide2

import cd_backlog  # noqa: E402
import cd_futures  # noqa: E402
import cd_edits  # noqa: E402
import cd_triage  # noqa: E402


def run_collect(root, name, edits=None, new_paths=None, **kw):
    case = CASES[name]
    model = json.loads((root / "model.json").read_text(encoding="utf-8"))
    spec_lines = cd_edits.spec_lines((root / "spec.md").read_text(encoding="utf-8"))
    bl = cd_backlog.load(root / case["backlog"]) if case.get("backlog") else None
    fp = cd_futures.load(root / case["futures"]) if case.get("futures") else None
    return cd_triage.collect2(
        model, root, case["edits"] if edits is None else edits,
        case["new_paths"] if new_paths is None else new_paths, bl, fp, spec_lines,
        kw.get("dismissals", []), kw.get("cited", []), "none", None, "0" * 64)


def tsig(triggers, avail=True, langs=()):
    return {"triggers": triggers, "patternAdoptionAvailable": avail, "noGrammarLanguages": list(langs)}


def T(cls, kind, ref="x"):
    return {"class": cls, "kind": kind, "ref": ref}


def test_decide2_truth_table():
    assert cd_triage.decide2(tsig([]))[:2] == ("skip", "skip")
    assert cd_triage.decide2({})[:2] == ("skip", "skip")
    assert cd_triage.decide2(tsig([T("blast", "callers")]))[:2] == ("light", "light")
    assert cd_triage.decide2(tsig([T("pattern", "variant")]))[:2] == ("full", "full")
    assert cd_triage.decide2(tsig([T("blast", "callers"), T("pattern", "variant")]))[:2] == ("full", "full")
    unc, ver, reasons = cd_triage.decide2(tsig([T("pattern", "assumption", "spec:2")], False, ["swift"]))
    assert (unc, ver) == ("full", "light")
    assert any("no tree-sitter coverage for swift" in r and "assumption" in r and "spec:2" in r
               for r in reasons)
    # a blast-only light is not touched by the cap
    assert cd_triage.decide2(tsig([T("blast", "callers")], False, ["swift"]))[:2] == ("light", "light")


@pytest.mark.parametrize("name", sorted(CASES))
def test_collect2_routes_each_fixture(tmp_path, name):
    root = make_fixture(tmp_path, name)
    inputs, s = run_collect(root, name)
    assert (s["verdictUncapped"], s["verdict"]) == (CASES[name]["uncapped"], CASES[name]["verdict"]), s["triggers"]
    assert s["schema"] == 2 and s["inputs"] is inputs
    assert cd_triage.decide2(s)[:2] == (s["verdictUncapped"], s["verdict"])
    assert s["modelSchema"]["modelSchemaVersion"] == 1


def test_collect2_triggers_and_cap_values(tmp_path):
    def trig(name):
        return {(t["class"], t["kind"]) for t in run_collect(make_fixture(tmp_path, name), name)[1]["triggers"]}
    assert trig("add-case-default") == {("blast", "case-sites")}
    assert trig("change-contract-hot") == {("blast", "callers")}
    assert trig("change-assumption") == {("pattern", "assumption")}
    assert trig("add-variant") == {("pattern", "variant")}
    assert trig("variation-2-subtypes") == {("pattern", "variation")}
    assert trig("backlog-hit") == {("pattern", "backlog")}
    assert trig("plan-overlap") == {("pattern", "plan")}
    assert trig("add-member") == set() and trig("none") == set()

    _, s = run_collect(make_fixture(tmp_path, "change-assumption"), "change-assumption")
    assert s["patternAdoptionAvailable"] is False and s["noGrammarLanguages"] == ["swift"]
    assert s["reach"]["readers"][0]["count"] >= 4
    _, s = run_collect(make_fixture(tmp_path, "add-variant"), "add-variant")
    assert s["patternAdoptionAvailable"] is True and s["noGrammarLanguages"] == []
    _, s = run_collect(make_fixture(tmp_path, "add-member"), "add-member")
    assert s["availabilityRequired"] == [{"name": "extraFlag", "owner": "AppState"}]
    _, s = run_collect(make_fixture(tmp_path, "add-param"), "add-param")
    assert s["availabilityRequired"] == [{"name": "force", "owner": "AppState"}]
    _, s = run_collect(make_fixture(tmp_path, "add-case-default"), "add-case-default")
    assert s["reach"]["caseSites"][0]["count"] == 3
    _, s = run_collect(make_fixture(tmp_path, "change-contract-hot"), "change-contract-hot")
    assert s["reach"]["callers"][0]["nonTest"] == 5


def test_collect2_swift_assumption_reason_line(tmp_path):
    root = make_fixture(tmp_path, "change-assumption")
    _, s = run_collect(root, "change-assumption")
    assert (s["verdictUncapped"], s["verdict"]) == ("full", "light")
    reasons = cd_triage.decide2(s)[2]
    assert any("no tree-sitter coverage for swift" in r for r in reasons)


def test_collect2_existing_new_path_is_usage_error(tmp_path):
    root = make_fixture(tmp_path, "none")
    with pytest.raises(cd_triage.UsageError):
        run_collect(root, "none", new_paths=["App/AppState.swift"])


def test_collect2_unknown_and_short_targets(tmp_path):
    root = make_fixture(tmp_path, "add-member")
    with pytest.raises(cd_edits.EditError):
        run_collect(root, "add-member", edits=["add-member:Nonexistent=abcd"])
    with pytest.raises(cd_edits.EditError, match="symbol id"):
        run_collect(root, "add-member", edits=["change-contract:Foo.ab@spec:2"])


def test_collect2_new_member_already_exists(tmp_path):
    root = make_fixture(tmp_path, "body-new-inputs")
    with pytest.raises(cd_triage.UsageError, match="already exists"):
        run_collect(root, "body-new-inputs", edits=["add-member:AppState=mapCoverage+state"])


def test_collect2_cited_triggers_verified(tmp_path):
    root = make_fixture(tmp_path, "add-member")
    _, s = run_collect(root, "add-member", cited=["spec:2"])
    assert {"class": "pattern", "kind": "cited-spec", "ref": "spec:2"} in s["triggers"]
    assert s["verdictUncapped"] == "full" and s["verdict"] == "light"
    for bad in ("spec:99", "backlog:F-nope", "plan:P-nope", "oops"):
        with pytest.raises(cd_triage.UsageError):
            run_collect(root, "add-member", cited=[bad])


def test_collect2_deterministic_and_relative(tmp_path):
    root = make_fixture(tmp_path, "add-case-default")
    a = run_collect(root, "add-case-default")[1]
    b = run_collect(root, "add-case-default")[1]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert str(tmp_path) not in json.dumps(a)
