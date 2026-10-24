"""Shared pytest fixtures for code-designer."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def grammar_cache(repo_root) -> Path:
    env = os.environ.get("CODE_DESIGNER_CACHE")
    path = Path(env) if env else repo_root / ".cd-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_py(script, *args, cache=None):
    """Run a Python script with sys.executable (argv list, no shell)."""
    env = os.environ.copy()
    if cache is not None:
        env["CODE_DESIGNER_CACHE"] = str(cache)
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
    )
