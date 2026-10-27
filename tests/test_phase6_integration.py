"""Phase 6 end-to-end flows driven through the BUILT dist scripts of both hosts."""
import json
import shutil

import pytest

from conftest import run_py
from test_gate_recompute import (BLAST, COVER, COVER_DR, FILES, RECORD, SPEC, doc_of, git, statuses)
from triage_v2_fixtures import make_fixture

TREES = {"claude-code": "scripts", "codex": "skills/extract-structure/scripts"}
AVAIL = ("\n## Availability\n\n| Name | Populated when | Readable when |\n|---|---|---|\n"
         "| extra | after Lone.build runs | after load; nil before |\n")


@pytest.fixture(params=sorted(TREES))
def dist(request, repo_root):
    base = repo_root / "dist" / request.param
    return base, base / TREES[request.param]


class DistEnv:
    def __init__(self, dist, tmp_path, cache):
        self.base, self.s = dist
        self.cache = cache
        self.repo = tmp_path / "repo"
        self.work = tmp_path / "work"
        self.work.mkdir()
        for rel, body in FILES.items():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(body)
        (self.repo / "spec.md").write_text(SPEC)
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.model = self.extract("model.json")

    def extract(self, name):
        out = self.work / name
        r = run_py(self.s / "cd_extract.py", self.repo, "--out", out, cache=self.cache)
        assert r.returncode in (0, 3), r.stderr
        return out

    def triage(self, *edits, extra=()):
        args = ["--root", self.repo, "--model", self.model, "--spec", self.repo / "spec.md"]
        for e in edits:
            args += ["--edit", e]
        r = run_py(self.s / "cd_triage.py", *args, *extra)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    def gate(self, text, model=None, root=None, spec=None):
        doc = self.work / "doc.md"
        doc.write_text(text)
        return run_py(self.s / "cd_gate.py", doc, "--root", root or self.repo, "--model", model or self.model,
                      "--kb", self.base / "knowledge", "--require-triage",
                      "--spec", spec or self.repo / "spec.md", "--cache-dir", self.cache, cache=self.cache)


@pytest.fixture()
def env(dist, tmp_path, grammar_cache):
    return DistEnv(dist, tmp_path, grammar_cache)


def test_a_skip_flow(env):
    out = env.triage("add-member:Lone=extra+state")
    assert out["recommended"] == "skip"
    r = env.gate(doc_of(out, AVAIL + COVER))
    assert r.returncode == 0, r.stdout + r.stderr


def test_b_light_flow(env):
    out = env.triage("change-contract:Svc.resolve@spec:2")
    assert out["recommended"] == "light", out["reasons"]
    r = env.gate(doc_of(out, BLAST + COVER))
    assert r.returncode == 0, r.stdout + r.stderr
    r = env.gate(doc_of(out, RECORD + BLAST + COVER_DR))
    assert r.returncode == 1
    assert "triage-light-too-many-records" in statuses(r)


def test_c_full_flow_py_triggers(env):
    out = env.triage("add-member:Base=extra")
    assert out["recommended"] == "full"
    r = env.gate(doc_of(out, RECORD + BLAST + COVER_DR))
    assert r.returncode == 0, r.stdout + r.stderr


def test_d_cap_flow(dist, tmp_path):
    base, s = dist
    root = make_fixture(tmp_path, "change-assumption")
    r = run_py(s / "cd_triage.py", "--root", root, "--model", root / "model.json", "--spec", root / "spec.md",
               "--edit", "change-assumption:bundled@spec:2")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["verdictUncapped"] == "full" and out["recommended"] == "light"
    assert "cap" in out["render"].lower() or "grammar" in out["render"].lower()
    blast = ("\n## Blast Radius\n\nScope: grep over files without grammar (swift); the model has no call/import edges.\n\n"
             "- Sources/R0.swift:1 [grep] `func read0() -> Int { return Catalog.bundled() }` caller\n\n"
             "## Unverified / Possible\n\n- Sources/R1.swift:1 reason: not read\n")
    doc = root / "doc.md"
    doc.write_text(doc_of(out, blast + COVER))
    r = run_py(s / "cd_gate.py", doc, "--root", root, "--model", root / "model.json", "--kb", base / "knowledge",
               "--require-triage", "--spec", root / "spec.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_e_regate_after_line_shift(env):
    out = env.triage("add-member:Base=extra")
    text = doc_of(out, RECORD + BLAST + COVER_DR)
    assert env.gate(text).returncode == 0
    (env.repo / "pay" / "base.py").write_text("# h\n# h\n# h\nclass Base:\n    x = 1\n")
    git(env.repo, "add", "-A")
    git(env.repo, "commit", "-q", "-m", "shift")
    r = env.gate(text, env.extract("model2.json"))
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("doc", ["good-skip-stub.md", "good-light.md"])
def test_f_020_docs_still_pass(dist, repo_root, tmp_path, doc):
    base, s = dist
    fix = repo_root / "tests" / "fixtures" / "design"
    repo = tmp_path / "repo"
    shutil.copytree(fix / "pay", repo / "pay")
    r = run_py(s / "cd_gate.py", fix / doc, "--root", repo, "--model", fix / "model.json",
               "--kb", base / "knowledge")
    assert r.returncode == 0, r.stdout + r.stderr


def test_g_audit_returns_json(env):
    out = env.triage("add-member:Lone=extra")
    doc = env.repo / "design.md"
    doc.write_text(doc_of(out, COVER))
    (env.repo / "pay" / "lone.py").write_text("class Lone:\n    y = 1\n    extra = 2\n")
    git(env.repo, "add", "-A")
    git(env.repo, "commit", "-q", "-m", "impl")
    r = run_py(env.s / "cd_triage.py", "audit", "--root", env.repo, "--doc", doc)
    assert r.returncode in (0, 1), r.stderr
    assert isinstance(json.loads(r.stdout), (dict, list))
