"""The `PP-NNN` contract.

Every verb that names a page goes through `parse_ref`/`norm_ref`, so the rejection
of a bare integer is not a nicety — it is the thing standing between a caller and
silently addressing the wrong page. The printed folio and the scan index are not
derivable from each other (CLAUDE.md, "Source rasters"), so `"48"` names nothing.
"""
from pathlib import Path

import pytest
from conftest import write_project

from harness.layout import ProjectError, page_files, project, ref_of, stem_for
from harness.refs import norm_ref, parse_ref


@pytest.mark.parametrize("given,expected", [
    ("1-048", (1, 48)),
    ("1-48", (1, 48)),          # lenient about zero-padding: it is typed by hand
    ("  2-030  ", (2, 30)),     # trimmed
    ("3-202", (3, 202)),
])
def test_parse_ref_accepts(given, expected):
    assert parse_ref(given) == expected


@pytest.mark.parametrize("given", [
    "48",        # the whole point: a bare integer is not a page identifier
    "048",
    "1",
    "",
    "1-",
    "-48",
    "1_048",
    "part1-048",
    "1-048-2",
    None,
])
def test_parse_ref_rejects(given):
    with pytest.raises(ValueError):
        parse_ref(given)


def test_bare_integer_error_explains_why():
    """The message has to teach, since this is where a wrong mental model surfaces."""
    with pytest.raises(ValueError, match="not derivable"):
        parse_ref("48")


@pytest.mark.parametrize("given,expected", [
    ("1-48", "1-048"),
    ("1-048", "1-048"),
    ("3-202", "3-202"),
])
def test_norm_ref_canonicalizes(given, expected):
    assert norm_ref(given) == expected


def test_norm_ref_is_idempotent():
    assert norm_ref(norm_ref("1-48")) == norm_ref("1-48")


def test_stem_matches_the_filenames(tmp_path):
    assert stem_for("1-48", tmp_path) == "chukchi-1-048"


def test_another_texts_stem_is_not_this_texts_page(tmp_path):
    """`koryak-1-048` must not read as this book's 1-048, and neither `parse_ref`,
    which has no root to ask, nor `ref_of`, which does, lets it through."""
    assert ref_of("chukchi-1-048", tmp_path) == "1-048"
    assert ref_of("1-48", tmp_path) == "1-048"
    with pytest.raises(ValueError):
        parse_ref("chukchi-1-048")
    with pytest.raises(ValueError):
        ref_of("koryak-1-048", tmp_path)
    with pytest.raises(ValueError):
        ref_of("chukchi-mythology-1-048", tmp_path)


def test_page_files_keeps_out_what_a_glob_lets_in(tmp_path):
    """Crops and another text's pages both match `chukchi-*.png`."""
    for name in ("chukchi-1-100.png", "chukchi-1-048.png",
                 "chukchi-1-048-a.png", "chukchi-mythology-1-048.png"):
        (tmp_path / name).touch()
    assert [p.name for p in page_files(tmp_path, ".png", tmp_path)] == [
        "chukchi-1-048.png", "chukchi-1-100.png"]
    assert page_files(tmp_path / "absent", ".png", tmp_path) == []


@pytest.mark.parametrize("stem", ["Chukchi", "chukchi_", "-x", "a--b", "1a", ""])
def test_a_stem_that_is_not_kebab_case_is_refused(tmp_path, stem):
    write_project(tmp_path, stem)
    with pytest.raises(ProjectError):
        project(tmp_path)


@pytest.mark.parametrize("spec,expected", [
    ("5", (5, 5)),
    ("+5", (0, 5)),
    ("-5", (5, 0)),
    ("-5+3", (5, 3)),
    ("+3", (0, 3)),
    ("0", (0, 0)),
])
def test_parse_context_reads_each_form(spec, expected):
    """A bare count is both ways, which is what "context" ordinarily means; the
    signed forms are for a one-sided question — what a seam ran into, or what a
    batch is about to reach."""
    from harness.refs import parse_context
    assert parse_context(spec) == expected


@pytest.mark.parametrize("spec", ["5+3", "-5-3", "+", "-", "", "3-5", "five", "+-2"])
def test_parse_context_refuses_a_mixed_or_empty_spec(spec):
    """`5+3` is refused rather than guessed at: with a sign already present, a
    reader of the command should not have to know whether the bare number binds
    left, right or both. `3-5` looks like a range and is not one."""
    from harness.refs import parse_context
    with pytest.raises(ValueError, match="--context"):
        parse_context(spec)


def test_with_context_windows_over_the_scans_not_over_arithmetic(tmp_path):
    """The window is applied to the observed index list, so it clamps at a part's
    end, steps over a gap instead of counting it as a page, and never crosses into
    the next part — `1-362` and `2-001` are neighbours in the binding and nowhere
    else, and a context spanning them would assert a continuity the scan index does
    not carry.
    """
    from harness.paths import with_context
    scans = tmp_path / "scans"
    scans.mkdir()
    # A deliberate hole at 1-003, and a second part starting over at 001.
    for ref in ["1-001", "1-002", "1-004", "1-005", "2-001", "2-002"]:
        (scans / f"chukchi-{ref}.png").write_bytes(b"")
    # The hole is stepped over, not counted: one behind 1-004 is 1-002.
    assert with_context(["1-004"], "-1", tmp_path) == ["1-002", "1-004"]
    # A count is in *pages*, not in index units — three ahead of 1-001 reaches
    # 1-005 by stepping over the hole, and clamps at the part's end rather than
    # running off it.
    assert with_context(["1-001"], "3", tmp_path) == ["1-001", "1-002", "1-004",
                                                      "1-005"]
    # And part 2 does not reach back into part 1.
    assert with_context(["2-001"], "-5", tmp_path) == ["2-001"]
    # Zero is the identity, and the named ref survives even with no neighbours.
    assert with_context(["1-004"], "0", tmp_path) == ["1-004"]


def test_with_context_merges_overlapping_windows_in_page_order():
    """Two refs a few apart must give one ordered run, not two lists with a
    duplicate where they meet."""
    from harness.paths import with_context
    got = with_context(["1-045", "1-047"], "1", Path("."))
    assert got == ["1-044", "1-045", "1-046", "1-047", "1-048"]
    assert len(got) == len(set(got))
