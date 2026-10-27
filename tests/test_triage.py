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


def test_cli_old_flags_rejected_with_edit_hint(script, tmp_path):
    root = copy_fix(tmp_path, "s0-additive")
    for flag in ("--modify", "--additive"):
        r = triage(script, root, flag, "Kind")
        assert r.returncode == 2
        assert "--edit" in r.stderr


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
                   "--spec", "--name", "--edit", "TRIAGE.md", "data"):
        assert needle in text, needle
    assert re.search(r"^0\. ", text, re.M)
    assert re.search(r"quoted text|cited quotes", text)
    assert "at most 2" not in text
    assert "--modify" not in text and "--additive" not in text


def test_triage_md_content(repo_root):
    import re
    text = (repo_root / "src" / "skills" / "design" / "TRIAGE.md").read_text(encoding="utf-8")
    for needle in ("--edit", "@spec:N", "not a change:", "--dismiss", "--rerun-reason",
                   "pattern adoption is unavailable", "no decision records", "data",
                   "add-member", "add-case", "add-param", "add-variant", "body-new-inputs",
                   "change-contract", "change-assumption"):
        assert needle in text, needle
    toks = set(re.findall(r"\{\{(.*?)\}\}", text))
    assert toks <= {"PLUGIN_ROOT", "SCRIPTS", "KNOWLEDGE", "CACHE_DIR", "HOST"}
    assert "{{#" not in text


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
                   "no design change:", "not a change:", "no decision records"):
        assert needle in text, needle
    assert "at most 2" not in text
