"""Citation verifier: real, fabricated, drifted, stale, reformatted, escaping."""
import json
import os
import shutil
from pathlib import Path

import pytest

from conftest import run_py

FIX = Path(__file__).parent / "fixtures" / "verify"


@pytest.fixture()
def script(repo_root):
    return repo_root / "src" / "extractor" / "cd_verify.py"


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copy(FIX / "sample.py", root / "sample.py")
    return root


def _model(root, provenance="tree-sitter"):
    from importlib import util
    spec = util.spec_from_file_location("cd_common", Path(__file__).parent.parent / "src/extractor/cd_common.py")
    cc = util.module_from_spec(spec)
    spec.loader.exec_module(cc)
    lines = (root / "sample.py").read_text().split("\n")
    h = cc.symbol_hash("\n".join(lines[17:19])) if provenance == "tree-sitter" else cc.symbol_hash("\n".join(lines[17:19]))
    sym = {"id": "sample.py#make_circle", "file": "sample.py", "span": {"startLine": 18, "endLine": 19}, "hash": h}
    return {"symbols": [sym]}


def _run(script, tmp_path, root, cits, *extra, model=None):
    cf = tmp_path / "c.json"
    cf.write_text(json.dumps(cits))
    args = ["--root", root, "--citations", cf, *extra]
    if model is not None:
        mf = tmp_path / "m.json"
        mf.write_text(json.dumps(model))
        args += ["--model", mf]
    r = run_py(script, *args)
    out = json.loads(r.stdout) if r.stdout.strip() else []
    return r, [x["status"] for x in out], out


REAL = {"file": "sample.py", "startLine": 18, "endLine": 18, "quote": "def make_circle(r):"}


def test_real_passes(script, tmp_path, repo):
    r, st, _ = _run(script, tmp_path, repo, [REAL])
    assert r.returncode == 0 and st == ["pass"]


def test_off_by_one_fails(script, tmp_path, repo):
    c = dict(REAL, startLine=19, endLine=19)
    r, st, _ = _run(script, tmp_path, repo, [c])
    assert r.returncode == 1 and st[0] in ("quote-mismatch", "drifted")


def test_missing_and_out_of_range(script, tmp_path, repo):
    r, st, _ = _run(script, tmp_path, repo, [dict(REAL, file="nope.py"), dict(REAL, startLine=99, endLine=99)])
    assert st == ["missing-file", "out-of-range"]


def test_fabricated_quote(script, tmp_path, repo):
    r, st, _ = _run(script, tmp_path, repo, [dict(REAL, quote="def not_there(x):")])
    assert st == ["quote-mismatch"]


def test_reformat_passes(script, tmp_path, repo):
    (repo / "sample.py").write_bytes(
        (FIX / "sample.py").read_bytes().replace(b"def make_circle(r):", b"def   make_circle(r):  ").replace(b"\n", b"\r\n"))
    r, st, _ = _run(script, tmp_path, repo, [REAL])
    assert r.returncode == 0 and st == ["pass"]


def test_moved_quote_drifted_then_tolerance(script, tmp_path, repo):
    (repo / "sample.py").write_text("# a\n# b\n# c\n" + (FIX / "sample.py").read_text())
    r, st, out = _run(script, tmp_path, repo, [REAL])
    assert st == ["drifted"] and out[0]["actual"] == [21, 21]
    r, st, _ = _run(script, tmp_path, repo, [REAL], "--tolerance", "3")
    assert r.returncode == 0 and st == ["pass"]


@pytest.mark.parametrize("prov", ["tree-sitter", "agent"])
def test_symbol_pass_stale_unknown(script, tmp_path, repo, prov):
    model = _model(repo, prov)
    cit = dict(REAL, symbol="sample.py#make_circle", startLine=18, endLine=19, quote="return Circle(r)")
    r, st, _ = _run(script, tmp_path, repo, [cit], model=model)
    assert st == ["pass"]
    r, st, _ = _run(script, tmp_path, repo, [dict(cit, symbol="sample.py#ghost")], model=model)
    assert st == ["unknown-symbol"]
    (repo / "sample.py").write_text((FIX / "sample.py").read_text().replace("return Circle(r)", "return Circle(r * 2)"))
    r, st, _ = _run(script, tmp_path, repo, [cit], model=model)
    assert r.returncode == 1 and st == ["stale"]


def test_cited_span_outside_symbol(script, tmp_path, repo):
    cit = dict(REAL, symbol="sample.py#make_circle", startLine=1, endLine=2, quote=None)
    r, st, _ = _run(script, tmp_path, repo, [cit], model=_model(repo))
    assert r.returncode == 1 and st == ["out-of-range"]


def test_path_escape_variants(script, tmp_path, repo):
    outside = tmp_path / "secret.py"
    outside.write_text("x = 1\n")
    os.symlink(outside, repo / "link.py")
    cits = [dict(REAL, file="link.py", startLine=1, endLine=1, quote=None),
            dict(REAL, file="../secret.py"), dict(REAL, file=str(outside))]
    r, st, _ = _run(script, tmp_path, repo, cits)
    assert st == ["path-escape"] * 3


def test_mixed_exit_code(script, tmp_path, repo):
    r, st, _ = _run(script, tmp_path, repo, [REAL, dict(REAL, quote="nope()")])
    assert r.returncode == 1 and st == ["pass", "quote-mismatch"]


def test_range_only_citation(script, tmp_path, repo):
    r, st, _ = _run(script, tmp_path, repo, [{"file": "sample.py", "startLine": 1, "endLine": 3}])
    assert st == ["pass"]
