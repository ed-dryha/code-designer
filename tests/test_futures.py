"""cd_futures: ids, diff-first propose/apply, no-downgrade merge, lint, confinement, stale."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import run_py

FIX = Path(__file__).parent / "fixtures" / "futures"
DATE = "2026-01-01"
GENV = {
    "GIT_AUTHOR_DATE": "2026-01-01T10:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T10:00:00+00:00",
}


def git(root, *args, date=None):
    env = os.environ.copy()
    env.update(GENV)
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(root), *args],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_futures.py"


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "repo"
    shutil.copytree(FIX / "repo", r)
    git(r, "init", "-q")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "init: seed repo")
    return r


def head(root):
    return git(root, "rev-parse", "HEAD")


def plans(root):
    return root / "docs" / "design" / "future-plans.md"


def cand(root, title="Support multiple currencies", **kw):
    c = {"title": title, "confidence": "medium",
         "source": [{"type": "commit", "ref": head(root), "quote": "init"}],
         "affected": ["src/a.py"]}
    c.update(kw)
    return c


def write_in(tmp_path, data):
    p = tmp_path / "in.json"
    p.write_text(json.dumps(data))
    return p


def propose(script, root, tmp_path, data, *extra):
    return run_py(script, "propose", "--root", root, "--input", write_in(tmp_path, data), *extra)


def sha_of(out):
    return re.search(r"^expect-sha: (\w*)$", out, re.M).group(1)


def apply(script, root, tmp_path, data, sha=None, *extra, date=DATE):
    if sha is None:
        sha = sha_of(propose(script, root, tmp_path, data).stdout)
    return run_py(script, "apply", "--root", root, "--input", write_in(tmp_path, data),
                  "--expect-sha", sha, "--date", date, *extra)


def docs(root):
    return list(yaml.safe_load_all(plans(root).read_text()))


def mk_id(title):
    n = " ".join(title.lower().split())
    slug = re.sub(r"[^a-z0-9]+", "-", n).strip("-")[:30].strip("-")
    return f"P-{slug}-{hashlib.sha1(n.encode()).hexdigest()[:6]}"


CID = mk_id("Support multiple currencies")


def test_id(script):
    r = run_py(script, "id", "--title", "Support multiple currencies")
    assert r.returncode == 0 and r.stdout.strip() == CID
    assert run_py(script, "id", "--title", "Support multiple currencies").stdout.strip() == CID
    long = run_py(script, "id", "--title", "A Very, Long Title!! with many many many words inside").stdout.strip()
    assert re.fullmatch(r"P-[a-z0-9-]{1,30}-[0-9a-f]{6}", long)


def test_propose_no_write(script, root, tmp_path):
    r = propose(script, root, tmp_path, {"candidates": [cand(root)]})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--- future-plans.md" in r.stdout and "+++ future-plans.md (proposed)" in r.stdout
    assert re.search(r"^expect-sha: \w+$", r.stdout, re.M)
    assert not plans(root).exists()


def test_apply_roundtrip(script, root, tmp_path):
    data = {"candidates": [cand(root)]}
    r = apply(script, root, tmp_path, data)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["added"] == 1
    d = docs(root)
    assert d[0] == {"schema": 1, "kind": "code-designer-futures"}
    assert d[1]["id"] == CID and d[1]["status"] == "inferred"
    assert run_py(script, "lint", plans(root), "--root", root).returncode == 0
    shown = json.loads(run_py(script, "show", "--root", root).stdout)
    assert shown["exists"] and shown["plans"][0]["id"] == CID
    again = propose(script, root, tmp_path, data)
    assert "no-change" in again.stdout
    assert not [l for l in again.stdout.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")]


def test_second_apply_noop(script, root, tmp_path):
    data = {"candidates": [cand(root)]}
    apply(script, root, tmp_path, data)
    before = plans(root).read_bytes()
    r = apply(script, root, tmp_path, data)
    assert r.returncode == 0 and plans(root).read_bytes() == before


def test_apply_sha_guard(script, root, tmp_path):
    data = {"candidates": [cand(root)]}
    sha = sha_of(propose(script, root, tmp_path, data).stdout)
    plans(root).parent.mkdir(parents=True)
    plans(root).write_text("# hand edit\n")
    r = apply(script, root, tmp_path, data, sha)
    assert r.returncode == 1 and "stale-diff" in r.stdout + r.stderr
    assert plans(root).read_text() == "# hand edit\n"


@pytest.mark.parametrize("status", ["confirmed", "done", "dropped"])
def test_no_downgrade(script, root, tmp_path, status):
    apply(script, root, tmp_path, {"candidates": [cand(root)]})
    d = docs(root)
    d[1].update(status=status, title="Hand edited", notes="mine", affected=["src/b.py"],
                confidence="high", lastConfirmed=DATE)
    plans(root).write_text("---\n" + "---\n".join(yaml.safe_dump(x) for x in d))
    snap = docs(root)[1]
    other = cand(root, affected=["pkg/x/y.py"], confidence="low")
    r = apply(script, root, tmp_path, {"candidates": [other]})
    assert r.returncode == 0, r.stdout + r.stderr
    assert docs(root)[1]["status"] == status
    for k in ("title", "notes", "affected", "confidence"):
        assert docs(root)[1][k] == snap[k]


def test_refresh_inferred(script, root, tmp_path):
    apply(script, root, tmp_path, {"candidates": [cand(root)]})
    r = apply(script, root, tmp_path, {"candidates": [cand(root, affected=["pkg/x/y.py"])]})
    assert r.returncode == 0
    p = docs(root)[1]
    assert p["id"] == CID and p["affected"] == ["pkg/x/y.py"] and p["status"] == "inferred"


def test_decisions(script, root, tmp_path):
    apply(script, root, tmp_path, {"candidates": [cand(root), cand(root, "Other idea")]})
    oid = mk_id("Other idea")
    data = {"decisions": [
        {"id": CID, "action": "confirm", "answer": "yes, next quarter"},
        {"id": oid, "action": "drop", "answer": "no"}],
        "developerPlans": [{"title": "Add audit log", "confidence": "high",
                            "affected": ["src/b.py"], "answer": "we need it"}]}
    r = apply(script, root, tmp_path, data, date="2026-02-02")
    assert r.returncode == 0, r.stdout + r.stderr
    by = {d["id"]: d for d in docs(root)[1:]}
    c = by[CID]
    assert c["status"] == "confirmed" and c["lastConfirmed"] == "2026-02-02"
    assert c["lastConfirmedCommit"] == head(root) and "yes, next quarter" in c["notes"]
    assert by[oid]["status"] == "dropped"
    dev = by[mk_id("Add audit log")]
    assert dev["status"] == "confirmed" and dev["source"][0]["type"] == "developer"
    # edit keeps id
    r = apply(script, root, tmp_path, {"decisions": [
        {"id": CID, "action": "edit", "answer": "x", "title": "Renamed", "confidence": "low",
         "affected": ["pkg/**"]}]})
    assert r.returncode == 0, r.stdout
    e = {d["id"]: d for d in docs(root)[1:]}[CID]
    assert e["title"] == "Renamed" and e["confidence"] == "low" and e["affected"] == ["pkg/**"]
    assert e["status"] == "confirmed"


def test_commit_hash_blank_outside_git(script, tmp_path):
    r = tmp_path / "plain"
    shutil.copytree(FIX / "repo", r)
    data = {"developerPlans": [{"title": "T one", "confidence": "low", "affected": ["src/a.py"], "answer": "a"}]}
    out = apply(script, r, tmp_path, data)
    assert out.returncode == 0, out.stdout + out.stderr
    assert docs(r)[1]["lastConfirmedCommit"] == ""


def rejected(r):
    assert r.returncode == 1, r.stdout + r.stderr
    return json.loads(r.stdout)["rejected"]


@pytest.mark.parametrize("mut", [
    {"id": "P-x-abcdef"},
    {"status": "confirmed"},
    {"affected": []},
    {"affected": ["../x"]},
    {"affected": ["/etc/passwd"]},
    {"affected": ["-rf"]},
    {"affected": [":(top)x"]},
    {"affected": ["--output=/tmp/x"]},
    {"source": [{"type": "commit", "ref": "deadbeefdeadbeef", "quote": "q"}]},
    {"source": [{"type": "todo", "ref": "src/a.py:2", "quote": "no such text"}]},
    {"source": [{"type": "model", "ref": "src/a.py#pay"}]},
])
def test_rejections(script, root, tmp_path, mut):
    c = cand(root)
    c.update(mut)
    r = propose(script, root, tmp_path, {"candidates": [c]})
    assert rejected(r)
    assert not plans(root).exists()


def test_todo_source_ok(script, root, tmp_path):
    c = cand(root, source=[{"type": "todo", "ref": "src/a.py:2", "quote": "TODO: support multiple"}])
    assert propose(script, root, tmp_path, {"candidates": [c]}).returncode == 0


def test_too_many_candidates(script, root, tmp_path):
    cs = [cand(root, f"Idea {i}") for i in range(5)]
    assert rejected(propose(script, root, tmp_path, {"candidates": cs}))
    assert propose(script, root, tmp_path, {"candidates": cs[:4]}).returncode == 0


def test_unknown_decision_id(script, root, tmp_path):
    r = propose(script, root, tmp_path, {"decisions": [{"id": "P-nope-abcdef", "action": "confirm", "answer": "y"}]})
    assert rejected(r)


def test_confinement(script, root, tmp_path):
    data = {"candidates": [cand(root)]}
    outside = tmp_path / "out.md"
    r = run_py(script, "propose", "--root", root, "--input", write_in(tmp_path, data), "--plans", outside)
    assert r.returncode == 2
    (root / "docs" / "design").mkdir(parents=True)
    link = root / "docs" / "design" / "link.md"
    link.symlink_to(outside)
    r = run_py(script, "propose", "--root", root, "--input", write_in(tmp_path, data), "--plans", link)
    assert r.returncode == 2
    assert run_py(script, "lint", outside, "--root", root).returncode == 2


GOOD = {"schema": 1, "kind": "code-designer-futures"}


def plan(**kw):
    p = {"id": mk_id("Thing"), "title": "Thing", "status": "inferred", "confidence": "low",
         "source": [], "affected": ["src/a.py"]}
    p.update(kw)
    return p


def write_plans(root, header, ps):
    plans(root).parent.mkdir(parents=True, exist_ok=True)
    plans(root).write_text("---\n" + "---\n".join(yaml.safe_dump(x) for x in [header, *ps]))


@pytest.mark.parametrize("hdr,ps,needle", [
    (GOOD, [plan(), plan()], "duplicate"),
    (GOOD, [plan(id="P-Bad_ID")], "id"),
    (GOOD, [plan(status="weird")], "status"),
    (GOOD, [plan(confidence="huge")], "confidence"),
    (GOOD, [plan(status="confirmed")], "lastConfirmed"),
    (GOOD, [plan(affected=[])], "affected"),
    ({"schema": 2, "kind": "x"}, [], "header"),
])
def test_lint_problems(script, root, hdr, ps, needle):
    write_plans(root, hdr, ps)
    r = run_py(script, "lint", plans(root), "--root", root)
    assert r.returncode == 1
    probs = json.loads(r.stdout)
    assert any(needle in p["problem"] for p in probs), probs


def test_lint_yaml_error_and_missing_show(script, root):
    plans(root).parent.mkdir(parents=True)
    shutil.copy(FIX / "plans" / "malformed.md", plans(root))
    assert run_py(script, "lint", plans(root), "--root", root).returncode == 1
    plans(root).unlink()
    r = run_py(script, "show", "--root", root)
    assert r.returncode == 0 and json.loads(r.stdout) == {"exists": False}


def test_size_cap(script, root):
    plans(root).parent.mkdir(parents=True)
    plans(root).write_text("# " + "x" * (1024 * 1024 + 10))
    r = run_py(script, "lint", plans(root), "--root", root)
    assert r.returncode == 1 and "file-too-large" in r.stdout


def test_no_verified_source(script, root, tmp_path):
    sy = tmp_path / "model.json"
    sy.write_text(json.dumps({"symbols": [{"id": "src/a.py#pay", "file": "src/a.py",
                                           "span": {"startLine": 1, "endLine": 3}}]}))
    c = cand(root, source=[{"type": "model", "ref": "src/a.py#pay"}])
    r = propose(script, root, tmp_path, {"candidates": [c]}, "--model", sy)
    assert "no-verified-source" in json.dumps(rejected(r))
