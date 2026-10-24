"""Per-language golden + expected-symbol checks, parametrized by fixture dir."""
import json
from pathlib import Path

import pytest

from conftest import run_py

ROOT = Path(__file__).parent
LANGS = sorted(p.stem for p in (ROOT / "golden").glob("*.json")) if (ROOT / "golden").is_dir() else []
FIXTURE_LANGS = sorted(p.name for p in (ROOT / "fixtures").iterdir() if p.is_dir())


def _extract(repo_root, grammar_cache, tmp_path, lang):
    out = tmp_path / "m.json"
    r = run_py(repo_root / "src" / "extractor" / "cd_extract.py", ROOT / "fixtures" / lang,
               "--cache-dir", grammar_cache, "--allow-download", "--out", out)
    assert r.returncode == 0, r.stderr
    m = json.loads(out.read_text())
    m.pop("generatedAt", None)
    m["generator"].pop("version", None)
    return m


@pytest.mark.parametrize("lang", FIXTURE_LANGS)
def test_expected_symbols(repo_root, grammar_cache, tmp_path, lang):
    exp = ROOT / "fixtures" / lang / "expected.json"
    if not exp.exists():
        pytest.skip("no expected.json")
    m = _extract(repo_root, grammar_cache, tmp_path, lang)
    got = {(s["id"], s["kind"]) for s in m["symbols"]}
    for e in json.loads(exp.read_text()):
        assert (e["id"], e["kind"]) in got


@pytest.mark.parametrize("lang", LANGS)
def test_golden(repo_root, grammar_cache, tmp_path, lang):
    m = _extract(repo_root, grammar_cache, tmp_path, lang)
    golden = json.loads((ROOT / "golden" / f"{lang}.json").read_text())
    assert m == golden
