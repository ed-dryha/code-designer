"""EXTR-05: an agent-provenance model validates and its spans are verifiable."""
import hashlib
import json
from pathlib import Path

from conftest import run_py

FIXTURE = Path(__file__).parent / "fixtures" / "python"
VALID_AGENT = Path(__file__).parent / "fixtures" / "models" / "valid_agent.json"


def _sym(sid, kind, name, parent, s, e, sig):
    return {"id": f"shapes.py#{sid}", "kind": kind, "name": name,
            "parent": f"shapes.py#{parent}" if parent else None, "file": "shapes.py",
            "span": {"startLine": s, "endLine": e}, "signature": sig, "visibility": None,
            "static": False, "supertypes": [], "typeText": None, "provenance": "agent",
            "inferred": True, "hash": None}


def _model():
    data = (FIXTURE / "shapes.py").read_bytes()
    return {
        "schemaVersion": 1,
        "generator": {"name": "cd-extract", "version": "0.1.0", "pack": None, "source": "agent"},
        "root": ".", "generatedAt": "2026-10-24T00:00:00Z", "status": "complete",
        "coverage": {"files": [{"path": "shapes.py", "language": "python", "parsed": True, "symbols": 3,
                                "hasErrors": False, "sha256": hashlib.sha256(data).hexdigest(),
                                "provenance": "agent"}],
                     "unavailable": [], "skipped": []},
        "symbols": [_sym("Shape", "class", "Shape", None, 1, 3, "class Shape"),
                    _sym("Shape.area", "method", "area", "Shape", 2, 3, "def area(self)"),
                    _sym("make_circle", "function", "make_circle", None, 18, 19, "def make_circle(r)")],
    }


def test_agent_model_validates(repo_root, tmp_path):
    m = tmp_path / "agent.json"
    m.write_text(json.dumps(_model()))
    r = run_py(repo_root / "src/extractor/cd_validate.py", m, "--root", FIXTURE)
    assert r.returncode == 0, r.stdout + r.stderr


def test_checked_in_agent_fixture_validates(repo_root):
    r = run_py(repo_root / "src/extractor/cd_validate.py", VALID_AGENT)
    assert r.returncode == 0, r.stdout


def test_agent_inferred_false_rejected(repo_root, tmp_path):
    m = _model()
    m["symbols"][0]["inferred"] = False
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(m))
    r = run_py(repo_root / "src/extractor/cd_validate.py", p)
    assert r.returncode == 1


def _verify(repo_root, tmp_path, model, cit):
    mp, cp = tmp_path / "m.json", tmp_path / "c.json"
    mp.write_text(json.dumps(model))
    cp.write_text(json.dumps([cit]))
    return run_py(repo_root / "src/extractor/cd_verify.py", "--root", FIXTURE,
                  "--citations", cp, "--model", mp)


def test_verify_real_span_passes_and_off_by_one_fails(repo_root, tmp_path):
    model = _model()
    good = {"file": "shapes.py", "startLine": 18, "endLine": 18, "quote": "def make_circle(r):",
            "symbol": "shapes.py#make_circle"}
    assert _verify(repo_root, tmp_path, model, good).returncode == 0
    bad = dict(good, startLine=19, endLine=19)
    r = _verify(repo_root, tmp_path, model, bad)
    assert r.returncode == 1
    assert "quote-mismatch" in r.stdout or "drifted" in r.stdout
