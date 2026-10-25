"""Backlog script: stable ids, idempotent non-destructive merge, lint, touching."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from conftest import run_py

FIX = Path(__file__).parent / "fixtures" / "backlog"
DATE = "2026-01-01"
GOD = "F-god-class-" + hashlib.sha1(b"smell-god-class|pkg_a/a.py#Big").hexdigest()[:6]


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_backlog.py"


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "repo"
    shutil.copytree(FIX / "repo", r)
    return r


@pytest.fixture()
def findings():
    return json.loads((FIX / "findings.json").read_text())


def merge(script, root, tmp_path, findings, *extra, date=DATE):
    ff = tmp_path / "f.json"
    ff.write_text(json.dumps(findings))
    return run_py(script, "merge", "--root", root, "--model", FIX / "model.json",
                  "--findings", ff, "--date", date, *extra)


def bl(root):
    return root / "docs" / "design" / "backlog.md"


def docs(root):
    return list(yaml.safe_load_all(bl(root).read_text()))


def test_id(script):
    r = run_py(script, "id", "--smell", "smell-god-class", "--symbol", "a.py#Big")
    exp = "F-god-class-" + hashlib.sha1(b"smell-god-class|a.py#Big").hexdigest()[:6]
    assert r.returncode == 0 and r.stdout.strip() == exp
    assert run_py(script, "id", "--smell", "smell-god-class", "--symbol", "a.py#Big").stdout.strip() == exp


def test_merge_new_sorted(script, root, tmp_path, findings):
    r = merge(script, root, tmp_path, findings)
    assert r.returncode == 0, r.stdout + r.stderr
    d = docs(root)
    assert d[0]["schema"] == 1
    assert [x["priority"] for x in d[1:]] == ["High", "Medium", "Low"]
    assert d[1]["id"] == GOD and d[1]["status"] == "open"
    assert d[1]["firstSeen"] == DATE


def test_idempotent(script, root, tmp_path, findings):
    merge(script, root, tmp_path, findings)
    a = bl(root).read_bytes()
    r = merge(script, root, tmp_path, findings)
    assert r.returncode == 0
    assert bl(root).read_bytes() == a


def test_preserve_human_edits(script, root, tmp_path, findings):
    merge(script, root, tmp_path, findings)
    d = docs(root)
    for x in d[1:]:
        if x["id"] == GOD:
            x["priority"] = "Low"
            x["notes"] = "keep"
            x["impact"] = "OLD"
    bl(root).write_text("---\n" + "---\n".join(yaml.safe_dump(x, sort_keys=False) for x in d))
    merge(script, root, tmp_path, findings, date="2026-02-02")
    g = [x for x in docs(root) if x.get("id") == GOD][0]
    assert g["priority"] == "Low" and g["notes"] == "keep"
    assert g["impact"] != "OLD" and g["lastSeen"] == "2026-02-02"


def test_resolved_and_reopen(script, root, tmp_path, findings):
    merge(script, root, tmp_path, findings)
    fewer = [f for f in findings if f["smell"] != "smell-long-method"]
    merge(script, root, tmp_path, fewer, date="2026-02-02")
    res = [x for x in docs(root)[1:] if x["status"] == "resolved"]
    assert len(res) == 1 and res[0]["resolvedOn"] == "2026-02-02"
    rid = res[0]["id"]
    merge(script, root, tmp_path, findings, date="2026-03-03")
    again = [x for x in docs(root)[1:] if x["id"] == rid][0]
    assert again["status"] == "open" and "resolvedOn" not in again


def test_scope_untouched(script, root, tmp_path, findings):
    merge(script, root, tmp_path, findings)
    a_only = [f for f in findings if f["symbol"].startswith("pkg_a/")]
    r = merge(script, root, tmp_path, a_only, "--scope", "pkg_a/**", date="2026-02-02")
    assert r.returncode == 0
    b = [x for x in docs(root)[1:] if x["symbol"].startswith("pkg_b/")][0]
    assert b["status"] == "open" and b["lastSeen"] == DATE


def test_verify_rejects(script, root, tmp_path, findings):
    bad = copy.deepcopy(findings)
    bad[0]["evidence"][0].update(startLine=1, endLine=1, quote="return 2")
    r = merge(script, root, tmp_path, bad)
    assert r.returncode == 1
    assert "rejected" in r.stdout and "drifted" in r.stdout
    assert not bl(root).exists()


def test_lint(script, root, tmp_path, findings):
    merge(script, root, tmp_path, findings)
    assert run_py(script, "lint", bl(root)).returncode == 0
    good = bl(root).read_text()
    for old, new in [(GOD, "F-god-class-000000"), ("priority: High", "priority: 7"),
                     ("priority: High", "priority: Urgent"),
                     ("rationale: Central class touched by many changes.",
                      "rationale: |\n  line one\n  line two")]:
        assert old in good
        bl(root).write_text(good.replace(old, new))
        r = run_py(script, "lint", bl(root))
        assert r.returncode == 1, new
        assert json.loads(r.stdout)
    bl(root).write_text(good)


def test_touching(script, root, tmp_path, findings):
    merge(script, root, tmp_path, findings)
    r = run_py(script, "touching", "--backlog", bl(root), "--symbols", "pkg_a/a.py#Big")
    assert [x["id"] for x in json.loads(r.stdout)] == [GOD]
    r = run_py(script, "touching", "--backlog", bl(root), "--files", "pkg_b/b.py")
    assert [x["symbol"] for x in json.loads(r.stdout)] == ["pkg_b/b.py#Helper"]
    merge(script, root, tmp_path, [f for f in findings if f["smell"] != "smell-god-class"], date="2026-02-02")
    r = run_py(script, "touching", "--backlog", bl(root), "--symbols", "pkg_a/a.py#Big")
    assert json.loads(r.stdout) == []


def test_confinement(script, root, tmp_path, findings):
    for p in ("../outside.md", str(tmp_path / "outside.md")):
        r = merge(script, root, tmp_path, findings, "--backlog", p)
        assert r.returncode == 2
    assert not (tmp_path / "outside.md").exists()
