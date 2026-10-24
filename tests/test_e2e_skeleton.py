"""Walking skeleton: extract -> validate -> verify on the Python fixture."""
import json
import shutil
from pathlib import Path

import pytest

from conftest import run_py

FIXTURE = Path(__file__).parent / "fixtures" / "python"


def _script(repo_root, name):
    return repo_root / "src" / "extractor" / name


@pytest.fixture()
def model_path(repo_root, grammar_cache, tmp_path):
    out = tmp_path / "model.json"
    r = run_py(_script(repo_root, "cd_extract.py"), FIXTURE, "--cache-dir", grammar_cache,
               "--allow-download", "--out", out)
    assert r.returncode == 0, r.stderr
    return out


def test_extract_validates(repo_root, model_path):
    r = run_py(_script(repo_root, "cd_validate.py"), model_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_symbols_and_spans(model_path):
    syms = {s["id"]: s for s in json.loads(model_path.read_text())["symbols"]}
    assert syms["shapes.py#Shape"]["span"]["startLine"] == 1
    assert syms["shapes.py#Shape.area"]["span"]["startLine"] == 2
    assert syms["shapes.py#Circle"]["span"]["startLine"] == 6
    assert syms["shapes.py#Circle.radius"]["kind"] == "field"
    assert syms["shapes.py#Circle.radius"]["span"]["startLine"] == 7
    assert syms["shapes.py#make_circle"]["kind"] == "function"
    assert syms["shapes.py#make_circle"]["span"]["startLine"] == 18


def _citation(model_path):
    syms = {s["id"]: s for s in json.loads(model_path.read_text())["symbols"]}
    s = syms["shapes.py#make_circle"]
    return {"file": s["file"], "startLine": s["span"]["startLine"],
            "endLine": s["span"]["startLine"], "quote": "def make_circle(r):"}


def test_verify_pass_and_off_by_one(repo_root, model_path, tmp_path):
    cit = _citation(model_path)
    good = tmp_path / "good.json"
    good.write_text(json.dumps([cit]))
    v = _script(repo_root, "cd_verify.py")
    r = run_py(v, "--root", FIXTURE, "--citations", good)
    assert r.returncode == 0, r.stdout + r.stderr
    bad = dict(cit, startLine=cit["startLine"] + 1, endLine=cit["endLine"] + 1)
    badf = tmp_path / "bad.json"
    badf.write_text(json.dumps([bad]))
    r = run_py(v, "--root", FIXTURE, "--citations", badf)
    assert r.returncode == 1


def test_verify_path_escape(repo_root, tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps([{"file": "../../etc/passwd", "startLine": 1, "endLine": 1}]))
    r = run_py(_script(repo_root, "cd_verify.py"), "--root", FIXTURE, "--citations", f)
    assert r.returncode == 1
    assert "path-escape" in r.stdout


def test_validator_rejects_corrupted(repo_root, model_path, tmp_path):
    m = json.loads(model_path.read_text())
    del m["symbols"]
    bad = tmp_path / "bad_model.json"
    bad.write_text(json.dumps(m))
    r = run_py(_script(repo_root, "cd_validate.py"), bad)
    assert r.returncode == 1
    assert r.stdout.strip()


def test_unavailable_exit_3(repo_root, tmp_path):
    cache = tmp_path / "empty-cache"
    cache.mkdir()
    out = tmp_path / "m.json"
    r = run_py(_script(repo_root, "cd_extract.py"), FIXTURE, "--cache-dir", cache, "--out", out)
    assert r.returncode == 3, r.stderr
    m = json.loads(out.read_text())
    assert m["status"] == "unavailable"
    assert m["coverage"]["unavailable"][0]["language"] == "python"
    assert m["coverage"]["files"] == []
