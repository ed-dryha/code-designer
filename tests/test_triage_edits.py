"""Schema-2 triage: fixtures, collect2/decide2, CLI."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from triage_v2_fixtures import CASES, make_fixture

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "src" / "schema"
                     / "structure-model.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(CASES))
def test_fixture_builds_and_validates(tmp_path, name):
    root = make_fixture(tmp_path, name)
    assert (root / "spec.md").is_file()
    model = json.loads((root / "model.json").read_text(encoding="utf-8"))
    Draft202012Validator(SCHEMA).validate(model)
    assert len(CASES) == 13


def test_fixture_is_deterministic(tmp_path):
    a = make_fixture(tmp_path / "a", "variation-2-subtypes")
    b = make_fixture(tmp_path / "b", "variation-2-subtypes")
    assert (a / "model.json").read_text() == (b / "model.json").read_text()
