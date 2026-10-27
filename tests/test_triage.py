"""Triage script: signals, recommend(), signalsSha, render, confinement."""
import json
import os
import shutil
from pathlib import Path

import pytest

import cd_triage
from conftest import run_py

FIX = Path(__file__).parent / "fixtures" / "triage"


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_triage.py"


def copy_fix(tmp_path, name):
    r = tmp_path / name
    shutil.copytree(FIX / name, r, symlinks=True)
    return r


def triage(script, root, *extra, spec="spec.md"):
    return run_py(script, "--root", root, "--model", root / "model.json",
                  "--spec", root / spec, *extra)


def sig(**kw):
    base = {"touchedExisting": 0, "additiveOnly": True, "dependentFiles": {}, "switchSites": 0,
            "variationPoints": [], "backlogFlagged": [], "planOverlap": [], "assumptionHits": [],
            "modelAvailable": True, "noGrammarLanguages": []}
    base.update(kw)
    return base


def dep(total, non_test, kind="modify"):
    return {"total": total, "nonTest": non_test, "kind": kind}


def test_importable_names():
    assert callable(cd_triage.recommend) and callable(cd_triage.signals_sha)


def test_recommend_backlog_full():
    assert cd_triage.recommend(sig(backlogFlagged=[{"id": "F-x"}], touchedExisting=1)) == "full"


def test_recommend_variation_full():
    assert cd_triage.recommend(sig(variationPoints=[{"symbol": "a#B"}], touchedExisting=1)) == "full"


def test_recommend_assumption_full():
    s = sig(assumptionHits=[{"file": "a", "line": 1, "category": "resource-lookup"}], touchedExisting=1)
    assert cd_triage.recommend(s) == "full"


def test_recommend_nontest_full():
    s = sig(touchedExisting=1, additiveOnly=False, dependentFiles={"A": dep(6, 5)})
    assert cd_triage.recommend(s) == "full"


def test_recommend_additive_switch_full():
    s = sig(touchedExisting=1, dependentFiles={"K": dep(2, 2, "additive")}, switchSites=4)
    assert cd_triage.recommend(s) == "full"


def test_recommend_plan_overlap_light():
    s = sig(planOverlap=[{"id": "P-x"}])
    assert cd_triage.recommend(s) == "light"


def test_recommend_modify_light():
    s = sig(touchedExisting=1, additiveOnly=False, dependentFiles={"A": dep(2, 2)})
    assert cd_triage.recommend(s) == "light"


def test_recommend_no_model_light():
    s = sig(touchedExisting=1, additiveOnly=False, modelAvailable=False, dependentFiles={"A": dep(1, 1)})
    assert cd_triage.recommend(s) == "light"


def test_recommend_additive_small_skip():
    s = sig(touchedExisting=1, modelAvailable=False, dependentFiles={"K": dep(2, 2, "additive")},
            switchSites=1)
    assert cd_triage.recommend(s) == "skip"


def test_recommend_new_files_skip_and_empty():
    assert cd_triage.recommend(sig()) == "skip"
    assert cd_triage.recommend({}) == "skip"
    s = sig()
    assert cd_triage.recommend(s) == cd_triage.recommend(dict(reversed(list(s.items()))))


def test_signals_sha_stable():
    a = sig(switchSites=2)
    b = dict(reversed(list(a.items())))
    assert cd_triage.signals_sha(a) == cd_triage.signals_sha(b)
    assert cd_triage.signals_sha(dict(a, signalsSha="zzz")) == cd_triage.signals_sha(a)
    assert cd_triage.signals_sha(dict(a, switchSites=3)) != cd_triage.signals_sha(a)


def test_cli_f2_mirror_full(script):
    root = FIX / "s1-single-instance"
    r = triage(script, root, "--modify", "RegionPack")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["recommended"] == "full" and out["schema"] == 1
    s = out["signals"]
    assert s["dependentFiles"]["RegionPack"]["nonTest"] >= 4
    assert s["modelAvailable"] is False and "swift" in s["noGrammarLanguages"]
    assert any(h["file"].endswith("AppState.swift") and h["line"] == 11 for h in s["assumptionHits"])
    assert out["signalsSha"] == cd_triage.signals_sha(s)


def test_cli_additive_skip_and_reclassify(script, tmp_path):
    root = copy_fix(tmp_path, "s0-additive")
    r = triage(script, root, "--additive", "Kind", "--new-path", "Sources/New.swift")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["recommended"] == "skip", out["reasons"]
    assert out["signals"]["switchSites"] == 1
    r = triage(script, root, "--additive", "Kind", "--new-path", "Sources/Describe.swift")
    out = json.loads(r.stdout)
    assert out["inputs"]["reclassified"] == ["Sources/Describe.swift"]
    assert out["signals"]["touchedExisting"] == 2
    assert out["recommended"] == "light"


def test_cli_force_recorded(script):
    root = FIX / "s1-single-instance"
    r = triage(script, root, "--modify", "RegionPack", "--force", "skip", "--force-phrase", "skip design")
    out = json.loads(r.stdout)
    assert out["recommended"] == "full"
    assert out["forced"] == {"verdict": "skip", "phrase": "skip design"}
    assert 'Override: forced-by-developer: "skip design"' in out["render"]
    assert out["render"].count("Verdict: skip") == 1
    assert triage(script, root, "--modify", "RegionPack", "--force", "skip").returncode == 2


def test_cli_rejects(script, tmp_path):
    root = copy_fix(tmp_path, "s0-additive")
    assert triage(script, root, "--modify", "dir/x.py#Nope").returncode == 2
    assert triage(script, root, "--modify", "bad name!").returncode == 2
    assert triage(script, root, "--additive", "Kind", "--new-path", "../x").returncode == 2
    assert triage(script, root, "--additive", "Kind", "--new-path", "/etc/x").returncode == 2
    outside = tmp_path / "outside.md"
    outside.write_text("1. x\n")
    r = run_py(script, "--root", root, "--model", root / "model.json", "--spec", outside,
               "--additive", "Kind")
    assert r.returncode == 2
    link = root / "esc"
    os.symlink(tmp_path, link)
    assert triage(script, root, "--additive", "Kind", "--new-path", "esc/x.swift").returncode == 2
    r = run_py(script, "--root", root, "--model", root / "model.json", "--spec", link / "outside.md",
               "--additive", "Kind")
    assert r.returncode == 2


def test_cli_backlog_flag_full(script, tmp_path):
    root = copy_fix(tmp_path, "s0-additive")
    bl = root / "backlog.md"
    bl.write_text(
        "schema: 1\nkind: code-designer-backlog\n---\nid: F-god-class-abcdef\n"
        "symbol: Sources/Kind.swift#Kind\nstatus: open\npriority: High\nrationale: r\n"
        "evidence:\n- file: Sources/Kind.swift\n  startLine: 1\n  endLine: 1\n  quote: q\n")
    r = triage(script, root, "--modify", "Kind", "--backlog", bl)
    out = json.loads(r.stdout)
    assert out["signals"]["backlogFlagged"][0]["id"] == "F-god-class-abcdef"
    assert out["recommended"] == "full"


def test_cli_plan_overlap(script, tmp_path):
    root = copy_fix(tmp_path, "s0-additive")
    fp = root / "future-plans.md"
    fp.write_text(
        "schema: 1\nkind: code-designer-futures\n---\nid: P-views-abcdef\ntitle: Views\n"
        "status: confirmed\naffected:\n- Sources/**\n")
    r = triage(script, root, "--additive", "Kind", "--futures", fp)
    out = json.loads(r.stdout)
    assert out["signals"]["planOverlap"][0]["id"] == "P-views-abcdef"
    assert out["recommended"] in ("light", "full")


def test_render_and_spec_items_and_no_writes(script, tmp_path):
    root = copy_fix(tmp_path, "s0-additive")
    before = sorted(str(p) for p in root.rglob("*"))
    out = json.loads(triage(script, root, "--additive", "Kind").stdout)
    assert sorted(str(p) for p in root.rglob("*")) == before
    for token in ("## Triage", "Verdict:", "Override:", "Reasons:", "```json", out["signalsSha"]):
        assert token in out["render"]
    assert [i["line"] for i in out["specItems"]] == [3, 4, 5]


# --- Skill/doc text pins (05-05) ---

DESIGN_DESCRIPTION = (
    "description: Use after the brainstorming spec is approved and before superpowers:writing-plans, "
    "for any change to existing code. It MUST be invoked at that moment even when brainstorming or the "
    "user says the next step is writing-plans, because brainstorming does not know about this stage and "
    "skipping it yields a plan with no evidence-gated design. Run it first, then give its docs/design "
    "file to superpowers:writing-plans as the Spec. Also usable standalone; produces an evidence-gated "
    "design doc in docs/design/ made of decision records."
)


def _skill(repo_root):
    return (repo_root / "src" / "skills" / "design" / "SKILL.md").read_text(encoding="utf-8")


def test_skill_has_triage_step(repo_root):
    import re
    text = _skill(repo_root)
    for needle in ("cd_triage.py", "skip", "light", "full", "--force", "--require-triage",
                   "--spec", "--name", "at most 2", "data"):
        assert needle in text, needle
    assert re.search(r"^0\. ", text, re.M)
    assert re.search(r"quoted text|cited quotes", text)


def test_skill_description_unchanged_and_size(repo_root):
    import re
    text = _skill(repo_root)
    assert DESIGN_DESCRIPTION in text.splitlines()
    assert len(text.splitlines()) < 150
    toks = set(re.findall(r"\{\{(.*?)\}\}", text))
    assert toks <= {"PLUGIN_ROOT", "SCRIPTS", "KNOWLEDGE", "CACHE_DIR", "HOST"}
    assert "{{#" not in text


def test_record_format_documents_phase5_sections(repo_root):
    text = (repo_root / "src" / "skills" / "design" / "RECORD-FORMAT.md").read_text(encoding="utf-8")
    for needle in ("## Triage", "## Availability", "## Spec Coverage", "Populated when",
                   "no design change:"):
        assert needle in text, needle
