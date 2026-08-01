"""Footnote-form citation parsing, and occurrence selection for `--replace`.

`parse_citation` is the only parsing done to an `authority` query, and it is
deliberately shallow. The hard fact it exists for: the comma before a volume is
*not* reliable in this book — `Maydell I, p. 331.` sits in the same apparatus as
`Krasheninnikoff, II, p. 49.` — which is why the volume is its own field rather
than part of a string.
"""
from pathlib import Path

import pytest

from harness.authorities import load, parse_citation, search
from harness.proposal_check import _parse_which


class TestParseCitation:
    def test_footnote_form_splits_into_text_and_volume(self):
        assert parse_citation("Dall, I, p. 375.") == ("Dall", 1)

    def test_volume_without_a_comma(self):
        """`Maydell I, p. 331.` — the print sets the volume both with and without a
        comma, in the same apparatus, so the comma carries no information and both
        forms must yield the same parse."""
        assert parse_citation("Maydell I, p. 331.") == ("Maydell", 1)

    def test_the_comma_is_a_separator_not_signal(self):
        """The whole point: identical results whichever way the print set it."""
        assert (parse_citation("Nordquist, II, p. 5.")
                == parse_citation("Nordquist II p. 5."))

    def test_page_number_is_not_read_as_a_volume(self):
        """The locator has to be removed *before* tokenizing, or `p. 375` leaves a
        bare `375` that looks exactly like a volume."""
        assert parse_citation("Dall, p. 375.") == ("Dall", None)

    def test_a_year_is_not_read_as_a_volume(self):
        """`Bogoras 1902` is a plausible query; the book runs to three volumes."""
        text, vol = parse_citation("Bogoras 1902")
        assert vol is None
        assert "1902" in text

    def test_multi_page_locator(self):
        assert parse_citation("Schrenck, III, pp. 1, 2, 3.") == ("Schrenck", 3)

    def test_volume_with_a_comma(self):
        assert parse_citation("Krasheninnikoff, II, p. 49.") == ("Krasheninnikoff", 2)

    @pytest.mark.parametrize("roman,n", [
        ("I", 1), ("II", 2), ("III", 3), ("IV", 4), ("V", 5), ("X", 10),
    ])
    def test_roman_numerals(self, roman, n):
        assert parse_citation(f"Nordquist, {roman}, p. 1.") == ("Nordquist", n)

    def test_bare_name_has_no_volume(self):
        """Most references are indirect prose — "Krause reports that…" — carrying
        the name alone. A resolver keyed on the footnote form misses the majority."""
        assert parse_citation("Krause") == ("Krause", None)

    def test_page_locators_are_dropped(self):
        text, vol = parse_citation("Dall, I, pp. 375-380.")
        assert "375" not in text and "pp" not in text
        assert vol == 1

    def test_short_title_siglum_survives_untouched(self):
        """`Hough, Lamp` — neither segment is a numeral or a page locator."""
        text, vol = parse_citation("Hough, Lamp")
        assert vol is None
        assert "Hough" in text and "Lamp" in text

    def test_empty_query(self):
        assert parse_citation("") == ("", None)


@pytest.fixture(scope="module")
def works():
    return load(Path(__file__).resolve().parent.parent.parent)


class TestCitationResolution:
    """The contract that matters: a citation copied out of the body finds its record.

    Corpus-facing on purpose — these two forms are facts about the printed
    bibliography, not about any parser, and a test over a fixture would prove
    nothing about them.
    """

    @pytest.mark.parametrize("citation,expected_key", [
        ("Krasheninnikoff, II, p. 49.", "krasheninnikoff1819"),  # comma before volume
        ("Maydell I, p. 331.", "maydell1893"),                   # none, same apparatus
    ])
    def test_both_printed_volume_forms_resolve(self, works, citation, expected_key):
        text, vol = parse_citation(citation)
        hits = search(works, text, vol)
        assert expected_key in {h["key"] for h in hits}

    def test_a_bare_name_returns_every_candidate_not_one(self, works):
        """51 sigla over 34 names, so a single answer would be manufactured. The
        caller is a human reading candidates."""
        hits = search(works, "Bogoras", None)
        assert len(hits) > 1

    def test_no_hit_is_a_legitimate_outcome(self, works):
        """Folio 9 closes with "For other authorities see references in the text",
        so the list is explicitly open and a miss is not a reconciliation failure."""
        assert search(works, "Malinowski", None) == []


class TestParseWhich:
    """`--which` for `proposal-check --replace`: 1-based on the way in, 0-based out."""

    def test_all(self):
        assert _parse_which("all", 4) == [0, 1, 2, 3]

    def test_first_and_last(self):
        assert _parse_which("first", 4) == [0]
        assert _parse_which("last", 4) == [3]

    def test_first_and_last_on_empty(self):
        assert _parse_which("first", 0) == []
        assert _parse_which("last", 0) == []

    def test_single_index_is_one_based(self):
        assert _parse_which("1", 4) == [0]
        assert _parse_which("3", 4) == [2]

    def test_range_is_inclusive_and_one_based(self):
        assert _parse_which("2:4", 5) == [1, 2, 3]

    def test_single_element_range(self):
        assert _parse_which("2:2", 5) == [1]

    def test_all_on_empty(self):
        assert _parse_which("all", 0) == []
