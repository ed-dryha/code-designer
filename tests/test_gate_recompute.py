"""Gate schema 2: recompute at the base commit, binding verdicts, per-verdict checks (D-07..D-14)."""
import json
import re
import shutil
import subprocess

import pytest

import cd_edits
import cd_triage
import cd_verify
from conftest import run_py

SPEC = "# Feature\n- first item\n- second item\n- third item\n"
CUE_SPEC = "# Feature\n- first item\n- load the catalog instead of the bundled one\n- third item\n"

COVER = ("\n## Spec Coverage\n\n| Spec lines | Requirement | Maps to |\n|---|---|---|\n"
         "| 2 | item | no design change: additive only |\n")
BLAST = ("\n## Blast Radius\n\nScope: grep over model-covered files (python); the model has no call/import edges, "
         "so dependents come from model parent/child links and grep.\n\n"
         "- pay/lone.py:1 [model] `class Lone:` owner of the new member\n\n"
         "## Unverified / Possible\n\n- pay/lone.py:1 reason: nothing else known\n")
RECORD = '''
## Decision Records

### DR-01 Add extra

```yaml
id: DR-01
decision: How to add extra to Base
evidence:
  - file: pay/base.py
    startLine: 1
    endLine: 2
    quote: |
      class Base:
          x = 1
candidate: none
alternatives:
  - option: do-nothing
    cost: none
verdict: no-pattern
reason: "A plain member is simplest."
change_safety: "One class touched."
```
'''
COVER_DR = COVER.replace("no design change: additive only", "DR-01")

FILES = {
    "pay/base.py": "class Base:\n    x = 1\n",
    "pay/a.py": "from pay.base import Base\n\n\nclass A(Base):\n    pass\n",
    "pay/b.py": "from pay.base import Base\n\n\nclass B(Base):\n    pass\n",
    "pay/lone.py": "class Lone:\n    y = 1\n",
    "pay/svc.py": "class Svc:\n    def resolve(self, x):\n        return x\n",
    "pay/c0.py": "def u0(svc):\n    return svc.resolve(0)\n",
    "pay/c1.py": "def u1(svc):\n    return svc.resolve(1)\n",
    "pay/c2.py": "def u2(svc):\n    return svc.resolve(2)\n",
    "pay/c3.py": "def u3(svc):\n    return svc.resolve(3)\n",
    "pay/c4.py": "def u4(svc):\n    return svc.resolve(4)\n",
}


def git(repo, *a):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(repo), *a],
                   check=True, capture_output=True)


class Env:
    def __init__(self, tmp_path, repo_root, cache, spec=SPEC, use_git=True):
        self.repo_root, self.cache = repo_root, cache
        self.repo = tmp_path / "repo"
        self.work = tmp_path / "work"
        self.work.mkdir()
        for rel, body in FILES.items():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(body)
        (self.repo / "spec.md").write_text(spec)
        if use_git:
            git(self.repo, "init", "-q")
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-q", "-m", "base")
        self.model = self.extract("model.json")

    def extract(self, name):
        out = self.work / name
        r = run_py(self.repo_root / "src" / "extractor" / "cd_extract.py", self.repo, "--out", out, cache=self.cache)
        assert r.returncode in (0, 3), r.stderr
        return out

    def triage(self, *edits, extra=()):
        args = ["--root", self.repo, "--model", self.model, "--spec", self.repo / "spec.md"]
        for e in edits:
            args += ["--edit", e]
        r = run_py(self.repo_root / "src" / "extractor" / "cd_triage.py", *args, *extra)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    def gate(self, text, model=None, *more):
        doc = self.work / "doc.md"
        doc.write_text(text)
        return run_py(self.repo_root / "src" / "extractor" / "cd_gate.py", doc, "--root", self.repo,
                      "--model", model or self.model, "--kb", self.repo_root / "src" / "knowledge",
                      *more, cache=self.cache)


@pytest.fixture()
def env(tmp_path, repo_root, grammar_cache):
    return Env(tmp_path, repo_root, grammar_cache)


def doc_of(out, tail=""):
    return "# Design: x\n\nSpec: spec.md\n\n" + out["render"] + "\n" + tail


def statuses(r):
    return [x["status"] for x in json.loads(r.stdout)]


def row(r, status):
    return next(x for x in json.loads(r.stdout) if x["status"] == status)


def refix(text, mutate):
    """Edit the JSON block of a doc and re-fix signalsSha so only the recompute can notice."""
    m = re.search(r"```json\n(.*?)\n```", text, re.S)
    sig = json.loads(m.group(1))
    mutate(sig)
    sig["signalsSha"] = cd_triage.signals_sha(sig)
    return text[:m.start(1)] + json.dumps(sig, indent=2, sort_keys=True) + text[m.end(1):]


# ---------------------------------------------------------------- Task 1

def test_valid_skip_passes(env):
    out = env.triage("add-member:Lone=extra")
    assert out["recommended"] == "skip"
    r = env.gate(doc_of(out, COVER))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "triage-verdict-mismatch" not in statuses(r)


def test_edited_verdict_fails_mismatch(env):
    out = env.triage("add-member:Lone=extra")
    text = doc_of(out, COVER).replace("Verdict: skip", "Verdict: full")
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-verdict-mismatch" in statuses(r)


def test_forced_full_with_phrase_passes(env):
    out = env.triage("add-member:Lone=extra", extra=["--force", "full", "--force-phrase", "owner wants a full design"])
    assert "Verdict: full" in out["render"] and "Override: forced-by-developer" in out["render"]
    r = env.gate(doc_of(out, RECORD + BLAST + COVER_DR))
    assert r.returncode == 0, r.stdout + r.stderr


def test_forced_phrase_removed_from_override_fails(env):
    out = env.triage("add-member:Lone=extra", extra=["--force", "full", "--force-phrase", "owner wants a full design"])
    text = doc_of(out, RECORD + BLAST + COVER_DR).replace(
        'Override: forced-by-developer: "owner wants a full design"', 'Override: forced-by-developer: "other"')
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-verdict-mismatch" in statuses(r)


def test_override_line_without_recorded_force_fails(env):
    out = env.triage("add-member:Lone=extra")
    text = doc_of(out, COVER).replace("Override: none", 'Override: forced-by-developer: "sneaky"')
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-verdict-mismatch" in statuses(r)


def test_edit_list_inconsistent_with_signals_fails_mismatch(env):
    out = env.triage("add-member:Lone=extra")
    text = refix(doc_of(out, COVER), lambda s: s["inputs"].__setitem__("edits", ["add-member:Base=extra"]))
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-signals-mismatch" in statuses(r)
    assert "triggers" in row(r, "triage-signals-mismatch")["detail"]


def test_edited_json_without_refix_is_tampered(env):
    out = env.triage("add-member:Lone=extra")
    text = doc_of(out, COVER).replace('"verdict": "skip"', '"verdict": "full"')
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-signals-tampered" in statuses(r)


def test_unanswered_cue_fails(tmp_path, repo_root, grammar_cache):
    e = Env(tmp_path, repo_root, grammar_cache, spec=CUE_SPEC)
    out = e.triage("add-member:Lone=extra")
    r = e.gate(doc_of(out, COVER))
    assert r.returncode == 1
    assert "triage-cue-unanswered" in statuses(r)


def test_dismissed_cue_passes(tmp_path, repo_root, grammar_cache):
    e = Env(tmp_path, repo_root, grammar_cache, spec=CUE_SPEC)
    out = e.triage("add-member:Lone=extra", extra=["--dismiss", "3:not a behavior change, wording only"])
    r = e.gate(doc_of(out, COVER))
    assert r.returncode == 0, r.stdout + r.stderr


def test_light_with_one_record_fails(env):
    out = env.triage("change-contract:Svc.resolve@spec:2")
    assert out["recommended"] == "light", out["reasons"]
    r = env.gate(doc_of(out, RECORD + BLAST + COVER_DR))
    assert r.returncode == 1
    assert "triage-light-too-many-records" in statuses(r)


def test_light_without_records_passes(env):
    out = env.triage("change-contract:Svc.resolve@spec:2")
    r = env.gate(doc_of(out, BLAST + COVER))
    assert r.returncode == 0, r.stdout + r.stderr


def test_full_verdict_recomputed_and_passes(env):
    out = env.triage("add-member:Base=extra")
    assert out["recommended"] == "full"
    r = env.gate(doc_of(out, RECORD + BLAST + COVER_DR))
    assert r.returncode == 0, r.stdout + r.stderr


def test_full_downgraded_to_light_fails(env):
    out = env.triage("add-member:Base=extra")
    text = doc_of(out, BLAST + COVER).replace("Verdict: full", "Verdict: light")
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-verdict-mismatch" in statuses(r)


def test_base_unavailable_fails_closed(env):
    out = env.triage("add-member:Lone=extra")
    text = refix(doc_of(out, COVER), lambda s: s["inputs"].__setitem__("base", "a" * 40))
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-base-unavailable" in statuses(r)


def test_base_not_hex_fails_closed(env):
    out = env.triage("add-member:Lone=extra")
    text = refix(doc_of(out, COVER), lambda s: s["inputs"].__setitem__("base", "--output=/tmp/x"))
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-base-unavailable" in statuses(r)


def test_spec_changed_fails(env):
    out = env.triage("add-member:Lone=extra")
    (env.repo / "spec.md").write_text(SPEC + "- a fourth item\n")
    r = env.gate(doc_of(out, COVER))
    assert r.returncode == 1
    assert "triage-spec-changed" in statuses(r)


def test_spec_missing_fails(env):
    out = env.triage("add-member:Lone=extra")
    text = doc_of(out, COVER).replace("Spec: spec.md", "Spec: none")
    r = env.gate(text)
    assert r.returncode == 1
    assert "triage-spec-missing" in statuses(r)


def _implement(env):
    (env.repo / "pay" / "lone.py").write_text("class Lone:\n    y = 1\n\n    def extra(self):\n        return 2\n")
    (env.repo / "pay" / "new.py").write_text("class New:\n    pass\n")
    git(env.repo, "add", "-A")
    git(env.repo, "commit", "-q", "-m", "implement")


def test_post_implementation_regate_passes(env):
    out = env.triage("add-member:Lone=extra")
    text = doc_of(out, COVER)
    assert env.gate(text).returncode == 0
    _implement(env)
    model2 = env.extract("model2.json")
    r = env.gate(text, model2)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "triage-signals-mismatch" not in statuses(r)
    tvb = [x for x in json.loads(r.stdout) if x["check"] == "tree-vs-base"]
    assert len(tvb) == 1 and "1 commit(s)" in tvb[0]["detail"]
    assert "differ from base" in tvb[0]["detail"] and "2 tracked file(s)" in tvb[0]["detail"]


def test_non_git_root_with_base_none_passes(tmp_path, repo_root, grammar_cache):
    e = Env(tmp_path, repo_root, grammar_cache, use_git=False)
    out = e.triage("add-member:Lone=extra")
    assert json.loads(out["render"].split("```json\n")[1].split("\n```")[0])["inputs"]["base"] == "none"
    r = e.gate(doc_of(out, COVER))
    assert r.returncode == 0, r.stdout + r.stderr
    assert any(x["check"] == "base" and "working tree" in x.get("detail", "") for x in json.loads(r.stdout))


# ---------------------------------------------------------------- Task 2

def test_v2_skip_stub_without_coverage_fails(env):
    out = env.triage("add-member:Lone=extra")
    r = env.gate(doc_of(out))
    assert r.returncode == 1
    assert "coverage-missing-section" in statuses(r)
    assert "no-records" not in statuses(r)


def test_v2_availability_required_without_row_fails(env):
    out = env.triage("add-member:Lone=extra+state")
    assert out["signals"]["availabilityRequired"]
    r = env.gate(doc_of(out, COVER))
    assert r.returncode == 1
    assert "availability-missing-section" in statuses(r)
    other = ("\n## Availability\n\n| Name | Populated when | Readable when |\n|---|---|---|\n"
             "| unrelated | at boot | always |\n")
    r = env.gate(doc_of(out, other + COVER))
    assert r.returncode == 1
    assert "availability-missing-row" in statuses(r)


def test_v2_availability_required_with_row_passes(env):
    out = env.triage("add-member:Lone=extra+state")
    avail = ("\n## Availability\n\n| Name | Populated when | Readable when |\n|---|---|---|\n"
             "| extra | after Lone.build runs | after load; nil before |\n")
    r = env.gate(doc_of(out, avail + COVER))
    assert r.returncode == 0, r.stdout + r.stderr


def test_light_missing_blast_fails(env):
    out = env.triage("change-contract:Svc.resolve@spec:2")
    r = env.gate(doc_of(out, COVER))
    assert r.returncode == 1
    assert "blast-missing-section" in statuses(r)


def test_drift_regate_passes(env):
    out = env.triage("add-member:Base=extra")
    text = doc_of(out, RECORD + BLAST + COVER_DR)
    assert env.gate(text).returncode == 0
    # lines shift above the cited quote after the base commit
    (env.repo / "pay" / "base.py").write_text("# header\n# header\n# header\nclass Base:\n    x = 1\n")
    git(env.repo, "add", "-A")
    git(env.repo, "commit", "-q", "-m", "shift")
    # the scenario is real: a working-tree check of the same citation fails
    st, _ = cd_verify.check(str(env.repo.resolve()), {"file": "pay/base.py", "startLine": 1, "endLine": 2,
                                                      "quote": "class Base:\n    x = 1"}, None, 0)
    assert st != "pass"
    model2 = env.extract("model2.json")
    r = env.gate(text, model2)
    assert r.returncode == 0, r.stdout + r.stderr
    tvb = [x for x in json.loads(r.stdout) if x["check"] == "tree-vs-base"]
    assert len(tvb) == 1 and "1 commit(s)" in tvb[0]["detail"]


def test_v1_skip_stub_exemption_unchanged(repo_root, tmp_path):
    fix = repo_root / "tests" / "fixtures" / "design"
    repo = tmp_path / "repo"
    shutil.copytree(fix / "pay", repo / "pay")
    r = run_py(repo_root / "src" / "extractor" / "cd_gate.py", fix / "good-skip-stub.md", "--root", repo,
               "--model", fix / "model.json", "--kb", repo_root / "src" / "knowledge")
    assert r.returncode == 0, r.stdout + r.stderr
