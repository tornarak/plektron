"""Corpus normal form: NFD, and the §2.9 spacing ruling.

Both are mechanical rather than judgement calls, which is why `--convert` may write
them unattended while every lookalike stays report-only. NFKC is the trap: it has
compatibility decompositions for two inventory glyphs and destroys them, so any
`normalize()` call in this codebase must name its form.
"""
import unicodedata

import pytest

from harness.normalize import _fix_spacing, _lookalikes, _spacing_hits


class TestSpacing:
    """§2.9 — the book sets French spacing (thin space before `;` and `:`); the
    edition keys English spacing. Editor's ruling, so it is auto-fixable."""

    @pytest.mark.parametrize("given,expected", [
        ("purpose ; but", "purpose; but"),
        ("purpose : but", "purpose: but"),
        ("one , two", "one, two"),
        ("two  spaces", "two spaces"),
        ("many     spaces", "many spaces"),
        ("a ;  b", "a; b"),
    ])
    def test_collapses(self, given, expected):
        assert _fix_spacing(given) == expected

    @pytest.mark.parametrize("given", [
        "already correct; fine",
        "  leading indent is not sentence spacing",
        "trailing spaces   ",
        "",
        "a\n\nb",
    ])
    def test_leaves_alone(self, given):
        assert _fix_spacing(given) == given

    def test_comment_lines_are_skipped(self):
        """`lexicon_extra.txt` documents itself with `#` lines whose multi-space
        indentation is code formatting, not sentence spacing."""
        src = "#   usage:  harness lexicon\nreal  text"
        assert _fix_spacing(src) == "#   usage:  harness lexicon\nreal text"

    def test_hits_are_located_not_tallied(self):
        hits = _spacing_hits("one  two\nthree ; four")
        assert len(hits) == 2
        assert {h["line"] for h in hits} == {1, 2}

    def test_no_hits_on_clean_text(self):
        assert _spacing_hits("clean; text\nhere") == []

    def test_fix_is_idempotent(self):
        once = _fix_spacing("a  ;  b")
        assert _fix_spacing(once) == once

    # --- §2.9 is a rule about print, so it stops at the keyed text ------------
    #
    # `1-194`'s decision note read "Woke Nonsense  Line", which reported as corpus
    # drift and which `--commit` would have rewritten. An adjudicator's sentence is
    # not a line of Bogoras: there is no printed spacing for it to drift from, and
    # the flag sent a human to look at a page where nothing was wrong.

    COMMENTARY = ('  "12": {\n'
                  '   "text": "runners made from the outer  layer of the larch",\n'
                  '   "note": "Woke Nonsense  Line. i think it triggered on a speck",\n'
                  '   "resolved": "крень = к, р, е, н, ь  (soft sign, §2.7)"\n'
                  '  }')

    def test_commentary_fields_are_not_print(self):
        hits = _spacing_hits(self.COMMENTARY, commentary=True)
        assert [h["line"] for h in hits] == [2]      # the `text` line, nothing else

    def test_the_keyed_text_is_still_checked_beside_them(self):
        """The scoping must not become a blanket exemption for the whole file —
        `text` on the same record still reports, or a real drift hides behind a
        note that happens to sit next to it."""
        assert "outer" in _spacing_hits(self.COMMENTARY, commentary=True)[0]["token"]

    def test_the_writer_agrees_with_the_reporter(self):
        """Report and write are two walks over the same raw source, and a fix that
        rewrote what no report mentioned would be the worse half of this bug:
        silent, and on a human's prose."""
        out = _fix_spacing(self.COMMENTARY, commentary=True)
        assert "Nonsense  Line" in out and "н, ь  (soft" in out
        assert "outer layer" in out

    def test_commentary_scoping_is_off_by_default(self):
        """Every non-JSON caller keeps the old behaviour: `readings.md` prose and
        `lexicon_extra.txt` have no such fields, and a default that skipped
        anything quoted would be a silent widening."""
        assert [h["line"] for h in _spacing_hits(self.COMMENTARY)] == [2, 3, 4]


class TestNFD:
    """NFD corpus-wide, and never NFKC."""

    def test_nfkc_would_destroy_two_inventory_glyphs(self):
        """U+1D4B -> U+025B and U+02D9 -> space + combining dot. This is why the
        form must always be named at the call site."""
        assert unicodedata.normalize("NFKC", "ᵋ") != "ᵋ"
        assert unicodedata.normalize("NFKC", "˙") != "˙"

    def test_nfd_preserves_them(self):
        for ch in "ᵋ˙ɪᴀᴇʟɵˊ":
            assert unicodedata.normalize("NFD", ch) == ch

    def test_nfd_decomposes_the_marked_letters(self):
        assert unicodedata.normalize("NFD", "ê") == "ê"
        assert unicodedata.normalize("NFD", "ñ") == "ñ"

    def test_precomposed_and_decomposed_are_invisible_to_each_other(self):
        """The reason `proposal-check --set` normalizes on write: a hand-typed
        precomposed ñ and the file's own n+U+0303 do not compare equal."""
        assert "ñ" != "ñ"
        assert unicodedata.normalize("NFD", "ñ") == "ñ"


class TestLookalikeCensus:
    def test_reports_one_record_per_occurrence(self):
        hits = _lookalikes("a´b and another ´ here")
        assert len(hits) == 2

    def test_clean_text_yields_nothing(self):
        assert _lookalikes("ordinary English prose, with a semicolon; fine") == []

    def test_curly_quotes_are_not_flagged_corpus_wide(self):
        """English prose reproduces the print. See tests/test_lookalike_scope.py."""
        assert _lookalikes("he said “yes” and ‘no’") == []

    def test_hit_names_what_it_traps(self):
        (hit,) = _lookalikes("x´y")
        assert "U+02CA" in hit["trap"]
        assert hit["token"] == "x´y"  # located to a token, not just a line
