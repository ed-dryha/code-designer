"""cd_setup: status, detect, offline, venv bootstrap (network stubbed)."""
import os
import sys
from pathlib import Path

import pytest
import tree_sitter_language_pack as tslp

from conftest import run_py

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "extractor"))
import cd_setup  # noqa: E402
import cd_pack  # noqa: E402


@pytest.fixture()
def fake_pack(monkeypatch):
    """Stub the pack layer: downloads 'succeed' by recording, offline set raises."""
    state = {"downloaded": set(), "offline": set(), "calls": []}

    def fake_open(cache, allow_download=False):
        return object()

    def fake_prefetch(pack, lang):
        state["calls"].append(lang)
        if lang in state["offline"]:
            raise cd_pack.GrammarUnavailable(lang, "download-failed", "offline")
        state["downloaded"].add(lang)

    monkeypatch.setattr(cd_pack, "open_pack", fake_open)
    monkeypatch.setattr(cd_setup, "prefetch_one", fake_prefetch)
    monkeypatch.setattr(tslp, "downloaded_languages", lambda: sorted(state["downloaded"]))
    return state


def test_status_empty_cache_exit0(repo_root, tmp_path):
    r = run_py(repo_root / "src/extractor/cd_setup.py", "--status", "--cache-dir", tmp_path / "c")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""


def test_detect_maps_extensions_and_ignores(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n")
    (tmp_path / "b.ts").write_text("")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "c.go").write_text("")
    assert cd_setup.detect_languages(str(tmp_path)) == ["python", "typescript"]


def test_detect_prefetches_only_needed(fake_pack, tmp_path, capsys):
    (tmp_path / "a.py").write_text("x=1\n")
    rc = cd_setup.main(["--cache-dir", str(tmp_path / "c"), "--detect", str(tmp_path)])
    assert rc == 0
    assert fake_pack["calls"] == ["python"]
    out = capsys.readouterr().out
    assert "ok python" in out and "cache size" in out


def test_idempotent_skips_cached(fake_pack, tmp_path):
    fake_pack["downloaded"].add("python")
    rc = cd_setup.main(["--cache-dir", str(tmp_path / "c"), "--langs", "python"])
    assert rc == 0
    assert fake_pack["calls"] == []


def test_tier1_covers_eleven(fake_pack, tmp_path):
    assert cd_setup.main(["--cache-dir", str(tmp_path / "c"), "--tier1"]) == 0
    assert len(fake_pack["calls"]) == 11


def test_offline_exit3_names_failed(fake_pack, tmp_path, capsys):
    fake_pack["offline"].add("go")
    rc = cd_setup.main(["--cache-dir", str(tmp_path / "c"), "--langs", "python,go"])
    assert rc == 3
    err = capsys.readouterr().err
    assert "go" in err and "failed languages" in err


def test_checksum_mismatch_is_hard_error(fake_pack, monkeypatch, tmp_path, capsys):
    def boom(pack, lang):
        raise tslp.ChecksumMismatchError("bad sum")
    monkeypatch.setattr(cd_setup, "prefetch_one", boom)
    rc = cd_setup.main(["--cache-dir", str(tmp_path / "c"), "--langs", "python"])
    assert rc == 2
    assert "checksum mismatch" in capsys.readouterr().err


def test_missing_cache_dir_exit2(repo_root, monkeypatch):
    monkeypatch.delenv("CODE_DESIGNER_CACHE", raising=False)
    env = {k: v for k, v in os.environ.items() if k != "CODE_DESIGNER_CACHE"}
    import subprocess
    r = subprocess.run([sys.executable, str(repo_root / "src/extractor/cd_setup.py"), "--status"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 2


def test_bootstrap_venv_stubbed(tmp_path, capsys):
    calls = []

    def runner(cmd, check=True):
        calls.append(list(cmd))

    rc = cd_setup.main(["--cache-dir", str(tmp_path / "c"), "--bootstrap-venv"], run=runner)
    assert rc == 0
    assert calls[0][1:3] == ["-m", "venv"]
    pip = calls[1]
    assert pip[-2:] == [cd_setup.PACK_SPEC, cd_setup.TS_SPEC]
    assert "venv python:" in capsys.readouterr().out


@pytest.mark.skipif(os.environ.get("CD_LIVE") != "1", reason="network test")
def test_live_prefetch_python(repo_root, tmp_path):
    r = run_py(repo_root / "src/extractor/cd_setup.py", "--langs", "python", "--cache-dir", tmp_path / "c")
    assert r.returncode == 0, r.stderr
