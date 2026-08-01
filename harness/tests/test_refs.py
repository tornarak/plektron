"""The `PP-NNN` contract.

Every verb that names a page goes through `parse_ref`/`norm_ref`, so the rejection
of a bare integer is not a nicety — it is the thing standing between a caller and
silently addressing the wrong page. The printed folio and the scan index are not
derivable from each other (CLAUDE.md, "Source rasters"), so `"48"` names nothing.
"""
import pytest

from harness.context import norm_ref, parse_ref, stem_for


@pytest.mark.parametrize("given,expected", [
    ("1-048", (1, 48)),
    ("1-48", (1, 48)),          # lenient about zero-padding: it is typed by hand
    ("chukchi-1-048", (1, 48)),  # a filename stem is a legal spelling
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
    ("chukchi-2-30", "2-030"),
    ("3-202", "3-202"),
])
def test_norm_ref_canonicalizes(given, expected):
    assert norm_ref(given) == expected


def test_norm_ref_is_idempotent():
    assert norm_ref(norm_ref("1-48")) == norm_ref("1-48")


def test_stem_matches_the_filenames():
    assert stem_for("1-48") == "chukchi-1-048"
