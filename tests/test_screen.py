"""Model-count smell pre-screen."""
import json
from pathlib import Path

import pytest

from conftest import run_py

MODEL = Path(__file__).parent / "fixtures" / "screen" / "model.json"


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_screen.py"


def _run(script, *extra):
    r = run_py(script, "--model", MODEL, *extra)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _find(out, smell):
    return [c for c in out["candidates"] if c["smell"] == smell]


def test_god_class(script):
    out = _run(script)
    g = _find(out, "smell-god-class")
    assert [c["symbol"] for c in g] == ["pkg_a/big.py#Big"]
    assert g[0]["counts"]["methods"] == 25 and g[0]["file"] == "pkg_a/big.py"
    assert g[0]["signal"]


def test_fat_interface(script):
    g = _find(_run(script), "smell-fat-interface")
    assert [c["symbol"] for c in g] == ["pkg_b/fat.py#Fat"]


def test_class_explosion(script):
    g = _find(_run(script), "smell-class-explosion")
    assert [c["symbol"] for c in g] == ["pkg_b/base.py#Base"]
    assert len(g[0]["counts"]["subtypes"]) == 6
    assert "pkg_b/sub0.py#Sub0" in g[0]["counts"]["subtypes"]


def test_speculative_generality(script):
    g = _find(_run(script), "smell-speculative-generality")
    syms = {c["symbol"]: c for c in g}
    assert "pkg_a/one.py#Lonely" in syms and "single implementer" in syms["pkg_a/one.py#Lonely"]["reason"]
    assert "pkg_a/unused.py#Orphan" in syms and "no implementers" in syms["pkg_a/unused.py#Orphan"]["reason"]
    assert "pkg_b/fat.py#Fat" in syms  # zero implementers
    assert "pkg_b/thin.py#Thin" in syms


def test_scope(script):
    out = _run(script, "--scope", "pkg_a/**")
    assert out["candidates"] and all(c["file"].startswith("pkg_a/") for c in out["candidates"])
    assert not _find(out, "smell-fat-interface")


def test_deterministic_sorted_and_max(script):
    a = _run(script)
    assert a == _run(script)
    assert "thresholds" in a and a["thresholds"]["god_methods"] == 20
    keys = [(c["smell"], -sum(v if isinstance(v, int) else len(v) for v in c["counts"].values()), c["symbol"]) for c in a["candidates"]]
    assert [c["smell"] for c in a["candidates"]] == sorted(c["smell"] for c in a["candidates"])
    assert keys == sorted(keys)
    assert len(_run(script, "--max", "2")["candidates"]) == 2


def test_note_and_inferred(script):
    out = _run(script)
    assert all("model facts" in c["note"] for c in out["candidates"])
    orphan = [c for c in out["candidates"] if c["symbol"] == "pkg_a/unused.py#Orphan"][0]
    assert orphan["inferred"] is True
    assert [c for c in out["candidates"] if c["symbol"] == "pkg_a/big.py#Big"][0]["inferred"] is False


def test_usage_error(script, tmp_path):
    r = run_py(script, "--model", tmp_path / "missing.json")
    assert r.returncode == 2
