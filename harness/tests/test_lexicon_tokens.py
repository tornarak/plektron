"""The cut — how a token is taken out of a line before either `lexicon` arm
classifies it. Two defects lived here and both reached `misses` and `native`
alike, because the cut is shared.

**A word broken across a printed line arrived as two words.** The ALTO stores one
line per printed line, so `Chuk-` / `chee` was two tokens no dictionary knows,
and the top of the miss list was fragments — `repre`, `Penin`, `sula`, `sents`.

**A curly quote arrived stuck to the token.** The print wraps glosses and quoted
speech, so `lexicon native` published `“G̣ɪk` and `“reˊkkeñ-spirits”` as forms,
and listed the quoted and unquoted spellings of one word as two rows.

The negative cases are the load-bearing half, and they are what a fix here can
break silently:

- a word-**internal** hyphen is Americanist notation and is never joined away;
- **U+0027 is not punctuation** in this corpus. It is the spirant and pause mark,
  an inventory character, and stripping it off a token's edge would delete a
  Tier-1 segment from every published form;
- reading order is not enough to join along. On a two-column page the banded
  order interleaves the columns, so the line after a broken word is the *other
  column's*, and joining to it glues two unrelated words together.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from harness.detectors import (
    EDGE_PUNCT,
    detect_all,
    join_broken_words,
    lexicon_miss,
    native_corpus_lines,
    suggest_lexicon,
)

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def rec(text: str, hpos: int = 400, width: int = 1774) -> dict:
    return {"text": text, "hpos": str(hpos), "width": str(width)}


def _gt_page(root: Path, ref: str, lines: list[tuple[str, int, int]]) -> Path:
    """A ground-truth ALTO: one `String` per line, with the geometry the column
    guard reads. `lines` is `(text, hpos, width)`, in document order."""
    p = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<TextLine ID="l{i}" HPOS="{h}" VPOS="{300 + i * 60}" WIDTH="{w}" '
        f'HEIGHT="50"><String CONTENT="{nfd(t)}"/></TextLine>'
        for i, (t, h, w) in enumerate(lines))
    p.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
        f'<TextBlock ID="b1">{body}</TextBlock>'
        "</PrintSpace></Page></Layout></alto>", encoding="utf-8")
    return p


# --- bug 1: the compositor's line-break hyphen --------------------------------

def test_a_word_broken_across_lines_is_rejoined():
    """`1-060`'s `Chuk-` / `chee`, which put both halves in the miss list."""
    out = join_broken_words([rec("of the Chuk-"), rec("chee people")])
    assert out == ["of the Chuk-chee", "people"]


def test_the_join_is_positional_so_no_line_moves():
    """Same length out as in — `native_corpus_lines` zips this against the
    records it came from and cites their `index`."""
    recs = [rec("Chuk-"), rec("chee"), rec("elsewhere")]
    assert len(join_broken_words(recs)) == len(recs)


def test_a_line_whose_only_token_continues_is_left_empty():
    assert join_broken_words([rec("Penin-"), rec("sula")]) == ["Penin-sula", ""]


def test_a_word_broken_twice_resolves_in_one_pass():
    """The backwards walk. A continuation that itself ends in a hyphen must be
    complete before the line above it takes its first token."""
    out = join_broken_words([rec("trans-"), rec("for-"), rec("mations here")])
    assert out == ["trans-for-mations", "", "here"]


def test_nothing_joins_past_the_last_line():
    """A page whose last line ends in a hyphen keeps it. The continuation is on
    the next page, which this function cannot see and must not invent."""
    assert join_broken_words([rec("body text"), rec("stock-")]) == \
        ["body text", "stock-"]


def test_only_a_letter_licenses_the_join():
    """A rule, a dash used as punctuation, a numeric range: not word breaks."""
    assert join_broken_words([rec("1900-"), rec("1901 was")])[0] == "1900-"
    assert join_broken_words([rec("aside --"), rec("then")])[0] == "aside --"


def test_the_join_does_not_cross_a_column_break():
    """`1-101`'s two-column gloss list, reduced.

    Reading order correctly interleaves the columns, so the line following
    `stock-` is the right column's, and its own continuation is the line after
    that. Joining to the next line in reading order produced `stock-23.` and left
    `ings”)` in the miss list as an unknown word.
    """
    out = join_broken_words([
        rec("16. Keˊmg̣ekem (“both hind-legs in white stock-", 402, 870),
        rec("23. Rew-ᵉiˊᵋtɪn (“ptarmigan-neck”", 1292, 878),
        rec("ings”).", 480, 132),
    ])
    assert out[0].endswith("stock-ings”).")
    assert out[1].startswith("23. Rew-")
    assert out[2] == ""


def test_missing_geometry_still_joins():
    """A store that writes no HPOS is the single-column ordinary case, and
    refusing there would leave the word split — the defect being fixed."""
    out = join_broken_words([{"text": "Chuk-"}, {"text": "chee"}])
    assert out == ["Chuk-chee", ""]


# --- bug 1, negative: an internal hyphen is Americanist notation --------------

def test_a_word_internal_tier1_hyphen_is_untouched():
    """`3-004`'s `ᴇʟaˊnaw-mêˊrg̣a` is one printed word and stays one token."""
    form = nfd("ᴇʟaˊnaw-mêˊrg̣a")
    out = join_broken_words([rec(f"{form} follows"), rec("the next line")])
    assert out == [f"{form} follows", "the next line"]


def test_a_broken_native_word_keeps_its_hyphen():
    """The join adds nothing and deletes nothing. U+002D is the licensed Tier-1
    hyphen, so dropping one inside a native compound would edit an inventory
    character on a guess about where the printer's measure ran out."""
    out = join_broken_words([rec(nfd("notaˊs˙qa-vaˊ-")), rec(nfd("ɪrg̣ɪn"))])
    assert out[0] == nfd("notaˊs˙qa-vaˊ-ɪrg̣ɪn")


# --- bug 2: curly quotes, and the apostrophe that is not punctuation ----------

def test_curly_quotes_are_edge_punctuation():
    for q in "“”‘’":
        assert q in EDGE_PUNCT
    assert nfd("“G̣ɪk”").strip(EDGE_PUNCT) == nfd("G̣ɪk")


def test_the_straight_apostrophe_is_never_stripped():
    """U+0027 is the spirant and pause mark, not punctuation (keying_spec §1)."""
    assert "'" not in EDGE_PUNCT
    assert "va'ɪrg̣ɪn'".strip(EDGE_PUNCT) == "va'ɪrg̣ɪn'"
    assert "“'ɪrkɪn”".strip(EDGE_PUNCT) == "'ɪrkɪn"


def test_the_stress_mark_is_never_stripped():
    """U+02CA likewise — a mark of the notation, not an edge quote."""
    assert "ˊ" not in EDGE_PUNCT
    assert nfd("“qeˊñuˊ”").strip(EDGE_PUNCT) == nfd("qeˊñuˊ")


# --- the two readings of a hyphenated token ----------------------------------

def test_a_rejoined_word_is_not_a_lexicon_miss():
    lex = {"chukchee", "peninsula"}
    assert not lexicon_miss("Chuk-chee", lex)
    assert not lexicon_miss("Penin-sula", lex)


def test_a_real_compound_is_not_a_lexicon_miss():
    """Both components known — the component pass already answered this, and the
    concatenation test must not be needed to."""
    assert not lexicon_miss("sea-mammals", {"sea", "mammals"})


def test_a_compound_unknown_both_ways_is_reported():
    """Neither reading is English, so the token stands as a candidate."""
    assert lexicon_miss("fore-goer", {"sea", "mammals"})


# --- both arms, over a store --------------------------------------------------

def test_native_forms_are_joined_dequoted_and_keep_their_line(tmp_path):
    """`native_corpus_lines` end to end: the form is whole, the quote is gone,
    the spirant survives, and the token still cites the line it began on."""
    _gt_page(tmp_path, "1-001", [
        (nfd("he said “reˊkkeñ-"), 400, 1774),
        (nfd("spirits” and va'ɪrg̣ɪn"), 400, 1774),
    ])
    got = {tok: idx for _, idx, tok in native_corpus_lines(tmp_path)}
    assert nfd("reˊkkeñ-spirits") in got
    assert got[nfd("reˊkkeñ-spirits")] == "0"
    assert nfd("va'ɪrg̣ɪn") in got
    assert not any(t.startswith("“") or t.endswith("”") for t in got)


def test_broken_english_words_leave_the_miss_list(tmp_path):
    """`suggest_lexicon` end to end. `data/lexicon_extra.txt` supplies the
    lexicon, so the assertion does not depend on the machine's dictionary."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "lexicon_extra.txt").write_text(
        "Chukchee\nreindeer\nherds\n", encoding="utf-8")
    _gt_page(tmp_path, "1-002", [
        ("the Chuk-", 400, 1774),
        ("chee reindeer-herds", 400, 1774),
    ])
    tokens = {r["token"] for r in suggest_lexicon(tmp_path)}
    assert "Chuk" not in tokens and "chee" not in tokens
    assert "Chuk-chee" not in tokens
    assert "reindeer-herds" not in tokens


# --- the cut reaches the flags too -------------------------------------------
#
# `detect_all` published the raw whitespace-delimited token and stripped only
# inside the one check that needed it, so `tei context`'s `detector_flags` handed
# a collation pass `"mêˊmêl),"` — the printer's parentheses and comma glommed
# onto a Tier-1 form, in the one field a reader acts on. Two consequences, and
# the second is why it sat unnoticed: `harness proposal codepoints` and a raster
# look get asked about characters that are not in the word; and the string did
# not compare equal to the *same form* in `tier1_terms`, which cuts. That
# inequality is what kept the payload carrying the same evidence twice.

def test_a_flag_publishes_the_token_without_the_printers_punctuation():
    flags = detect_all([nfd("Chukchee, mêˊmêl), Phoca")])["tokens"]
    assert nfd("mêˊmêl") in {f["token"] for f in flags}
    assert not any(f["token"].endswith(("),", ")", ",")) for f in flags)


def test_the_cut_does_not_reach_a_tier1_character():
    """The negative half, and the one a fix here breaks silently: U+0027 and
    U+02CA are segments of the notation, not edges of a token."""
    flags = detect_all([nfd("(va'ɪrg̣ɪn), “qeˊñu”")])["tokens"]
    tokens = {f["token"] for f in flags}
    assert nfd("va'ɪrg̣ɪn") in tokens
    assert nfd("qeˊñu") in tokens


def test_a_token_that_is_only_punctuation_raises_nothing():
    assert detect_all(["— ( ) ,"])["tokens"] == []
