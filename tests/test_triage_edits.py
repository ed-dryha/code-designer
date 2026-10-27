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


# ---------------------------------------------------------------- CLI

import hashlib  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

from conftest import run_py  # noqa: E402

FIXD = Path(__file__).parent / "fixtures" / "triage"
SCRIPT = Path(__file__).resolve().parent.parent / "src" / "extractor" / "cd_triage.py"

F1_FLAGS = ["--edit", "add-case:Place.Kind=mapPoint", "--edit", "add-member:Place",
            "--edit", "add-member:ViewpointPicker",
            "--edit", "add-member:AppState=mapCoverage+state",
            "--edit", "body-new-inputs:AppState.placeResolver@mapPoint",
            "--new-path", "Sources/MapPicker.swift", "--new-path", "Sources/MapCoverage.swift"]


def cp(tmp_path, name):
    r = tmp_path / name
    shutil.copytree(FIXD / name, r, symlinks=True)
    return r


def cli(root, *extra, spec="spec.md"):
    return run_py(SCRIPT, "--root", root, "--model", root / "model.json", "--spec", root / spec, *extra)


def cli_json(root, *extra, **kw):
    r = cli(root, *extra, **kw)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_cli_f1_like_skip_with_availability(tmp_path):
    root = cp(tmp_path, "f1-like")
    out = cli_json(root, *F1_FLAGS)
    assert out["schema"] == 2 and out["recommended"] == "skip"
    s = out["signals"]
    assert s["availabilityRequired"] == [{"name": "mapCoverage", "owner": "AppState"}]
    assert not [t for t in s["triggers"] if t["class"] == "pattern"]
    assert s["verdictUncapped"] == "skip"
    unanswered = [c for c in out["cues"] if c["answered"] is None]
    assert len(unanswered) == 1 and unanswered[0]["line"] == 3
    assert "UNANSWERED" in "\n".join(out["reasons"])
    out2 = cli_json(root, *F1_FLAGS, "--dismiss", "3:not a change: wording only")
    assert [c["answered"] for c in out2["cues"]] == ["dismissed"]
    assert out2["inputs"]["dismissals"] == [{"line": 3, "reason": "not a change: wording only"}]


def test_cli_f1_flag_pin_availability_nonempty(tmp_path):
    out = cli_json(cp(tmp_path, "f1-like"), *F1_FLAGS)
    assert out["signals"]["availabilityRequired"]


def test_cli_body_new_input_grounded_in_spec_or_rejected(tmp_path):
    root = cp(tmp_path, "f1-like")
    flags = ["--edit", "body-new-inputs:AppState.placeResolver@mapPoint"]
    assert cli(root, *flags).returncode == 0          # mapPoint appears only in the spec text
    (root / "spec.md").write_text("# Map\n- Tapping the map picks a viewpoint.\n", encoding="utf-8")
    r = cli(root, *flags)
    assert r.returncode == 2
    assert "names no declared =NEW and does not appear in the spec" in r.stderr


def test_cli_f2_like_uncapped_full_capped_light(tmp_path):
    root = cp(tmp_path, "f2-like")
    out = cli_json(root, "--edit", "change-assumption:bundled@spec:2")
    assert out["verdictUncapped"] == "full" and out["recommended"] == "light"
    assert any("no tree-sitter coverage for swift" in r and "assumption" in r for r in out["reasons"])
    reach = out["signals"]["reach"]
    assert reach["readers"][0]["count"] >= 5
    assert any(h["category"] == "resource-lookup" and h["file"] == "Molfar/Core/Loader.swift"
               for h in reach["assumptionHits"])
    assert [c["answered"] for c in out["cues"]] == ["edit"]
    assert "Verdict: light" in out["render"]


def test_cli_py_triggers(tmp_path):
    root = cp(tmp_path, "py-triggers")
    out = cli_json(root, "--edit", "add-member:Base=extra")
    assert out["recommended"] == "full" and out["signals"]["patternAdoptionAvailable"] is True
    assert [t["kind"] for t in out["signals"]["triggers"]] == ["variation"]
    out = cli_json(root, "--edit", "add-member:Widget=extra", "--backlog", root / "backlog.md")
    assert [t["kind"] for t in out["signals"]["triggers"]] == ["backlog"] and out["recommended"] == "full"
    out = cli_json(root, "--edit", "add-member:Solo=extra", "--futures", root / "futures.md")
    assert [t["kind"] for t in out["signals"]["triggers"]] == ["plan"] and out["recommended"] == "full"
    out = cli_json(root, "--edit", "add-member:Solo=extra", "--trigger", "spec:2")
    assert [t["kind"] for t in out["signals"]["triggers"]] == ["cited-spec"]
    assert out["inputs"]["citedTriggers"] == ["spec:2"]
    out = cli_json(root, "--edit", "add-member:Widget=extra", "--backlog", root / "backlog.md",
                   "--trigger", "backlog:F-god-class-abcdef")
    assert {t["kind"] for t in out["signals"]["triggers"]} == {"backlog", "cited-backlog"}


def test_cli_inputs_recorded_in_signals_and_sha(tmp_path):
    root = cp(tmp_path, "f2-like")
    out = cli_json(root, "--edit", "change-assumption:bundled@spec:2", "--rerun-reason", "spec changed",
                   "--force", "full", "--force-phrase", "need the pattern session")
    s = out["signals"]
    assert s["inputs"]["rerun"] == "spec changed" and s["inputs"]["base"] == "none"
    assert s["inputs"]["specSha256"] == hashlib.sha256((root / "spec.md").read_bytes()).hexdigest()
    assert s["inputs"]["forced"] == {"verdict": "full", "phrase": "need the pattern session"}
    assert out["recommended"] == "light" and "Verdict: full" in out["render"]
    assert 'Override: forced-by-developer: "need the pattern session"' in out["render"]
    assert out["signalsSha"] == __import__("cd_triage").signals_sha(s)
    assert out["signalsSha"] in out["render"]
    lines = out["render"].split("\n")
    assert lines[0] == "## Triage" and lines[1].startswith("Verdict:") and lines[2].startswith("Override:")
    assert lines[3] == "Reasons:" and "Signals:" in lines
    assert cli_json(root, "--edit", "change-assumption:bundled@spec:2")["signals"]["inputs"]["rerun"] is None


def test_cli_no_edits_is_skip_with_cues(tmp_path):
    root = cp(tmp_path, "f1-like")
    out = cli_json(root)
    assert out["recommended"] == "skip" and out["signals"]["inputs"]["edits"] == []
    assert len(out["cues"]) == 1


def test_cli_rejections(tmp_path):
    root = cp(tmp_path, "f1-like")
    for flag in ("--modify", "--additive"):
        r = cli(root, flag, "Place")
        assert r.returncode == 2 and "--edit" in r.stderr
    assert cli(root, "--edit", "add-member:Plac3=abcd").returncode == 2            # typo target
    assert cli(root, "--edit", "add-member:AppState=load").returncode == 2         # =NEW exists in owner
    assert cli(root, "--edit", "change-contract:AppState.load@spec:99").returncode == 2
    assert cli(root, "--edit", "bogus:AppState").returncode == 2
    assert cli(root, "--dismiss", "2:not a change: x").returncode == 2             # not a cue line
    assert cli(root, "--dismiss", "3:todo").returncode == 2
    assert cli(root, "--trigger", "spec:99").returncode == 2
    assert cli(root, "--new-path", "../x").returncode == 2
    assert cli(root, "--new-path", "/etc/x").returncode == 2
    assert cli(root, "--new-path", "Sources/Place.swift").returncode == 2          # existing file
    r = cli(root, "--force", "skip")
    assert r.returncode == 2
    outside = tmp_path / "outside.md"
    outside.write_text("- x\n")
    r = run_py(SCRIPT, "--root", root, "--model", root / "model.json", "--spec", outside)
    assert r.returncode == 2
    link = root / "esc"
    os.symlink(tmp_path, link)
    assert cli(root, "--new-path", "esc/x.swift").returncode == 2


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True)


def test_cli_base_sha_and_dirty_tree(tmp_path):
    root = cp(tmp_path, "f1-like")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert cli_json(root)["inputs"]["base"] == sha
    (root / "Sources" / "Place.swift").write_text("struct Place {}\n", encoding="utf-8")
    r = cli(root)
    assert r.returncode == 2
    assert "commit or stash tracked source changes before triage" in r.stderr


def test_cli_deterministic_and_no_writes(tmp_path):
    root = cp(tmp_path, "f1-like")
    before = sorted(str(p) for p in root.rglob("*"))
    a = cli(root, *F1_FLAGS).stdout
    b = cli(root, *F1_FLAGS).stdout
    assert a == b and a
    assert sorted(str(p) for p in root.rglob("*")) == before


def test_cli_audit_dispatch(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    doc = root / "doc.md"
    doc.write_text("# Design\n\n## Triage\nVerdict: skip\nOverride: none\nReasons:\n- r\nSignals:\n```json\n"
                   + json.dumps({"schema": 2, "inputs": {"edits": [], "newPaths": [], "base": "none"}})
                   + "\n```\n", encoding="utf-8")
    r = run_py(SCRIPT, "audit", "--root", root, "--doc", doc)
    assert r.returncode == 0, r.stderr
    assert "mismatches" in json.loads(r.stdout)
