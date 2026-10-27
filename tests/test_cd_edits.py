"""cd_edits: edit grammar, spec lines, cue scan, git base helpers, Triage parser."""
import json
import os
import subprocess

import pytest

import cd_edits
import cd_gate
from cd_edits import EditError


def git(root, *a):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a],
        capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    (r / "a.txt").write_text("hello\n")
    (r / "src").mkdir()
    (r / "src" / "m.py").write_text("x = 1\n")
    try:
        os.symlink("a.txt", r / "link")
        has_link = True
    except (OSError, NotImplementedError):
        has_link = False
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    r.has_link = has_link
    return r


# ---- parse_edit -------------------------------------------------------------

def test_parse_add_case():
    e = cd_edits.parse_edit("add-case:Place.Kind=mapPoint")
    assert e == {"shape": "add-case", "target": "Place.Kind", "new": "mapPoint", "state": None, "ref": None}


@pytest.mark.parametrize("state", ["state", "dependency"])
def test_parse_add_member_state(state):
    e = cd_edits.parse_edit("add-member:AppState=mapCoverage+" + state)
    assert e["state"] == state and e["new"] == "mapCoverage"


def test_parse_body_new_inputs_ref():
    e = cd_edits.parse_edit("body-new-inputs:placeResolver@mapPoint")
    assert e["ref"] == "mapPoint" and e["new"] is None


@pytest.mark.parametrize("bad", [
    "add-case:Place.Kind+state=x",
    "change-contract:Foo+state@spec:3",
    "add-param:Foo.bar",
    "add-member:AppState+state",
    "body-new-inputs:placeResolver",
    "body-new-inputs:placeResolver@spec:3",
    "change-contract:Foo",
    "change-contract:Foo@mapPoint",
    "change-assumption:Foo@bar",
    "add-variant:Foo@bar",
    "add-case:Place.Kind=x@spec:2",
    "add-member:Foo=x@spec:2",
    "change-contract:Foo@spec:0",
    "change-contract:Foo@spec:x",
    "bogus:Foo",
    "add-member:",
    "add-member",
    "add-member:Foo Bar",
    "add-member:Foo\x00",
    "add-member:Foo;rm",
    "add-member:Foo|x",
    "add-member:Foo`x`",
    "add-member:Foo$x",
    "",
])
def test_parse_edit_rejects(bad):
    with pytest.raises(EditError) as ei:
        cd_edits.parse_edit(bad)
    assert "SHAPE:TARGET" in str(ei.value) or "shape" in str(ei.value) or "requires" in str(ei.value) or "only" in str(ei.value) or "ref" in str(ei.value)


def test_parse_citing_edit():
    e = cd_edits.parse_edit("change-contract:Foo.bar@spec:4")
    assert e["ref"] == "spec:4"


def test_editerror_is_valueerror():
    assert issubclass(EditError, ValueError)


# ---- validate_edits ---------------------------------------------------------

def test_validate_spec_range():
    ok = cd_edits.parse_edit("change-contract:Foo@spec:3")
    cd_edits.validate_edits([ok], 3)
    with pytest.raises(EditError):
        cd_edits.validate_edits([ok], 2)


def test_validate_ref_declared_new():
    es = [cd_edits.parse_edit("add-case:Place.Kind=mapPoint"),
          cd_edits.parse_edit("body-new-inputs:placeResolver@mapPoint")]
    cd_edits.validate_edits(es, 0)


def test_validate_ref_from_spec():
    es = [cd_edits.parse_edit("body-new-inputs:placeResolver@mapPoint")]
    cd_edits.validate_edits(es, 2, spec_lines=["a mapPoint place", "b"])
    with pytest.raises(EditError) as ei:
        cd_edits.validate_edits(es, 2, spec_lines=["a mapPointer place", "b"])
    assert "names no declared =NEW and does not appear in the spec" in str(ei.value)
    with pytest.raises(EditError):
        cd_edits.validate_edits(es, 0)


# ---- spec_lines -------------------------------------------------------------

def test_spec_lines_crlf():
    assert cd_edits.spec_lines("a\r\nb\r\n") == ["a", "b"]
    assert cd_edits.spec_lines("a\rb") == ["a", "b"]


def test_spec_lines_trailing():
    assert cd_edits.spec_lines("a\n\n") == ["a", ""]
    assert cd_edits.spec_lines("") == []


def test_gate_resolve_spec_uses_shared(tmp_path):
    (tmp_path / "s.md").write_bytes(b"x\r\ny\r\n")
    ls, err = cd_gate.resolve_spec("", str(tmp_path.resolve()), "s.md")
    assert err is None and ls == ["x", "y"]


# ---- cues -------------------------------------------------------------------

@pytest.mark.parametrize("line,phrase", [
    ("Use the resolver instead of the cache", "instead of"),
    ("It no longer validates anything", "no longer"),
    ("The reader falls back to bundled", "falls back"),
    ("Allow another source", "another"),
    ("Make it injectable", "injectable"),
    ("Previously it was fixed", "previously"),
    ("Замість кешу", "замість"),
    ("Це більше не працює", "більше не"),
    ("Повертається до старого", "повертається до"),
    ("Інший режим", "інший"),
])
def test_cue_phrases(line, phrase):
    cs = cd_edits.find_cues(["intro", line])
    assert len(cs) == 1 and cs[0]["line"] == 2 and cs[0]["phrase"].lower() == phrase


def test_not_cues():
    assert cd_edits.find_cues(["Add two places", "changes to the map"]) == []


def test_cue_out_of_scope_skipped():
    lines = ["# Spec", "## Out of scope", "- instead of x", "- no longer y", "## Next", "- instead of z",
             "- Out of scope: another thing", "- Out of Scope: no longer"]
    cs = cd_edits.find_cues(lines)
    assert [c["line"] for c in cs] == [6]


def test_cue_text_normalized_and_capped():
    cs = cd_edits.find_cues(["no   longer\t" + "x" * 300])
    assert cs[0]["text"].startswith("no longer x") and len(cs[0]["text"]) <= 200


def test_cue_long_line_skipped():
    assert cd_edits.find_cues(["instead of " + "x" * 400]) == []


def test_cue_real_phrase_once():
    cs = cd_edits.find_cues(["Search no longer validates the pack as today."])
    assert len(cs) == 1 and cs[0]["phrase"] == "no longer"


def test_unanswered_cues():
    cues = [{"line": 1, "phrase": "x", "text": "t"}, {"line": 2, "phrase": "x", "text": "t"},
            {"line": 3, "phrase": "x", "text": "t"}, {"line": 4, "phrase": "x", "text": "t"},
            {"line": 5, "phrase": "x", "text": "t"}]
    edits = [cd_edits.parse_edit("change-contract:Foo@spec:1"),
             cd_edits.parse_edit("add-case:Foo.Bar=baz")]
    dism = [{"line": 2, "reason": "not a change: copy"}, {"line": 3, "reason": "TODO"},
            {"line": 4, "reason": ""}]
    out = cd_edits.unanswered_cues(cues, edits, dism)
    assert [c["line"] for c in out] == [3, 4, 5]


def test_unanswered_ref_on_addition_not_counted():
    cues = [{"line": 1, "phrase": "x", "text": "t"}]
    e = {"shape": "add-member", "target": "A", "new": None, "state": None, "ref": "spec:1"}
    assert cd_edits.unanswered_cues(cues, [e], []) == cues


# ---- git helpers ------------------------------------------------------------

def test_valid_sha():
    assert cd_edits.valid_sha("a" * 40)
    assert not cd_edits.valid_sha("abc")
    assert not cd_edits.valid_sha("A" * 40)
    assert not cd_edits.valid_sha("--output=x")
    assert not cd_edits.valid_sha("a" * 41)
    assert not cd_edits.valid_sha(None)


def test_head_sha(repo, tmp_path):
    h = cd_edits.head_sha(repo)
    assert h == git(repo, "rev-parse", "HEAD") and cd_edits.valid_sha(h)
    nongit = tmp_path / "ng"
    nongit.mkdir()
    assert cd_edits.head_sha(nongit) is None


def test_tracked_dirty(repo, tmp_path):
    assert cd_edits.tracked_dirty(repo) == []
    (repo / "src" / "m.py").write_text("x = 2\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "d.md").write_text("d\n")
    git(repo, "add", "docs/d.md")
    git(repo, "commit", "-q", "-m", "d")
    (repo / "docs" / "d.md").write_text("e\n")
    (repo / "untracked.py").write_text("u\n")
    assert cd_edits.tracked_dirty(repo) == ["src/m.py"]
    nongit = tmp_path / "ng"
    nongit.mkdir()
    assert cd_edits.tracked_dirty(nongit) == []


def test_extract_base(repo, tmp_path):
    sha = git(repo, "rev-parse", "HEAD")
    dest = tmp_path / "out"
    dest.mkdir()
    cd_edits.extract_base(repo, sha, dest)
    assert (dest / "a.txt").read_text() == "hello\n"
    assert (dest / "src" / "m.py").read_text() == "x = 1\n"
    if repo.has_link:
        assert not os.path.lexists(dest / "link")


def test_extract_base_bad(repo, tmp_path):
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(EditError):
        cd_edits.extract_base(repo, "--output=x", dest)
    with pytest.raises(EditError):
        cd_edits.extract_base(repo, "b" * 40, dest)


# ---- Triage section ---------------------------------------------------------

def test_parse_triage_section():
    sig = {"schema": 2, "signalsSha": "x"}
    doc = "# D\n\n## Triage\nVerdict: light\nOverride: none\nSignals:\n```json\n" + json.dumps(sig) + "\n```\n\n## Next\n"
    assert cd_edits.parse_triage_section(doc) == ("light", sig)
    assert cd_edits.parse_triage_section("# D\n## Other\n") == (None, None)
