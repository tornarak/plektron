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
    _lexicon,
    detect_all,
    english_genitive,
    join_broken_words,
    lexicon_miss,
    native_corpus_lines,
    suggest_lexicon,
)
from harness.tests.test_entities import entry

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
    tokens = {r["token"] for r in suggest_lexicon(tmp_path)["tokens"]}
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


# --- the English possessive, which is not a mis-keyed stress mark -------------
#
# `apostrophe_adjacency` fires on U+2019 because a curly apostrophe standing in
# for U+02CA is a real and invisible defect. Once ratified Tier-1 forms stopped
# being flagged, **every surviving hit on the ground-truth corpus was an ordinary
# English possessive** — 31 of 31, `wife’s` through `Krause’s`.

LEX = {"reindeer", "wife", "raven", "beak", "daughter", "in", "law", "let"}


def test_a_possessive_on_a_word_english_knows_is_not_a_hit():
    assert english_genitive("wife’s", LEX)
    assert english_genitive("Raven’s-Beak", LEX)
    assert english_genitive("daughter-in-law’s", LEX)


def test_a_curly_apostrophe_where_the_stress_mark_belongs_still_is():
    """The load-bearing negative, and why position alone cannot decide it:
    `keˊlet` mis-keyed as `ke’let` puts U+2019 between two lowercase ASCII
    letters, which is exactly where a possessive sits. The stem is what
    separates them — and it must be *positively* known, since `ke` is under the
    four-character floor `_unknown_word` never reports on."""
    assert not english_genitive("ke’let", LEX)
    assert any(f["type"] == "apostrophe_adjacency"
               for f in detect_all(["called ke’let here"])["tokens"])


def test_a_genitive_on_a_native_stem_is_still_a_hit():
    """`2-045` prints `Kereˊtkun’s`, broken so the token reads `kun’s`. A Tier-1
    stem taking an English possessive is attested, and is exactly the case a
    shape-only rule would clear."""
    assert not english_genitive("kun’s", LEX)


def test_a_second_lookalike_in_the_token_defeats_the_explanation():
    """U+2019 alone has an innocent reading; beside another lookalike the form is
    not ordinary English whatever the apostrophe is doing."""
    assert any(f["type"] == "apostrophe_adjacency"
               for f in detect_all([nfd("the raven´s’ beak")])["tokens"])


def test_without_a_lexicon_nothing_is_suppressed():
    """Fails closed: no dictionary, no claim about what English knows."""
    assert not english_genitive("reindeer’s", set())


# --- the entity store as the corpus's proper-noun dictionary ------------------
#
# The proper nouns used to be listed twice: once in `data/lexicon_extra.txt` and
# once as an entity's canonical or alias. `detectors.entity_forms` made the
# second the only one. What these hold is the direction of the move — a name
# filed in `entities/` stops being a miss — and the structural fact that keeps it
# from becoming a hole: the detector cannot see a marked form either way.


def _extra(root: Path, *terms: str) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "lexicon_extra.txt").write_text(
        "\n".join(terms) + "\n", encoding="utf-8")


def test_an_alias_form_is_not_a_miss(tmp_path):
    _extra(tmp_path, "placeholder")
    entry(tmp_path, "person:gondatti", canonical="Nikolai Gondatti",
          aliases=[("Gondatti", False)])
    assert not lexicon_miss("Gondatti", _lexicon(tmp_path))


def test_a_canonical_is_split_into_its_components(tmp_path):
    """`Bering Strait` is filed as one canonical and reaches `_unknown_word` as
    two components, so an entry contributing only the joined string would leave
    both of them missing. Hyphen too: `Sredne-Kolymsk` splits the way
    `lexicon_miss` splits it."""
    _extra(tmp_path, "placeholder")
    entry(tmp_path, "water:bering-strait", canonical="Bering Strait")
    entry(tmp_path, "place:sredne-kolymsk", canonical="Sredne-Kolymsk")
    lex = _lexicon(tmp_path)
    assert not lexicon_miss("Bering", lex)
    assert not lexicon_miss("Strait", lex)
    assert not lexicon_miss("Sredne", lex)
    assert not lexicon_miss("Kolymsk", lex)


def test_a_native_alias_reaches_the_dictionary_and_changes_nothing(tmp_path):
    """**The structural guard, and the one a refactor breaks silently.** An
    entity may carry a native alias as an alias — `place:anadyr` carries `Veᵋñ`
    — and that form does land in this dictionary. It is inert there: a marked
    form is not ASCII, and `_unknown_word` reports only on ASCII components. So
    the alias table cannot blind `lexicon_miss`, which is the only detector
    that could catch an unmarked romanized form.

    Asserted as an equality between two dictionaries rather than as a property
    of the form, because what must hold is that adding the alias changed the
    *answer* nowhere, not merely that this one token still misses."""
    _extra(tmp_path, "placeholder")
    entry(tmp_path, "place:anadyr", canonical="Anadyr")
    before = _lexicon(tmp_path)
    verdicts = {t: lexicon_miss(t, before)
                for t in ("Anadyr", nfd("Veᵋñ"), "Ulakhpen", "reindeer")}
    entry(tmp_path, "place:anadyr", canonical="Anadyr",
          aliases=[(nfd("Veᵋñ"), True)])
    after = _lexicon(tmp_path)
    assert {t: lexicon_miss(t, after) for t in verdicts} == verdicts


def test_an_entity_filed_after_the_first_call_is_seen(tmp_path):
    """The dictionary is cached per root, and `entities/` changes *inside* a
    process — `edition_ui._guarded` writes it on a browser click. Keyed on the
    store's stamp, so the cache follows the store rather than outliving it."""
    _extra(tmp_path, "placeholder")
    assert lexicon_miss("Gondatti", _lexicon(tmp_path))
    entry(tmp_path, "person:gondatti", canonical="Nikolai Gondatti")
    assert not lexicon_miss("Gondatti", _lexicon(tmp_path))


def test_what_the_entity_store_suppressed_is_reported(tmp_path):
    """A second source could absorb a name silently. `misses` detects against
    the dictionary and `lexicon_extra.txt` alone and re-tests each hit against
    the store, so a token the store accounts for moves to `suppressed` rather
    than off the report."""
    _extra(tmp_path, "placeholder")
    entry(tmp_path, "person:gondatti", canonical="Nikolai Gondatti",
          aliases=[("Gondatti", False)])
    _gt_page(tmp_path, "1-002", [
        ("Gondatti reports the Ulakhpen", 400, 1774),
    ])
    got = suggest_lexicon(tmp_path)
    assert "Gondatti" in {r["token"] for r in got["suppressed"]}
    assert "Gondatti" not in {r["token"] for r in got["tokens"]}
    assert "Ulakhpen" in {r["token"] for r in got["tokens"]}


# --- one selection of "what is Tier-1", not two -------------------------------

def test_the_two_tier1_selections_agree_on_russian():
    """`native_corpus` excludes Cyrillic and `tier1_terms` did not, so the
    generator wrapped `Чукотскій` as a Tier-1 handle while every frequency table
    over the same store excluded it.

    Invisible from either side: the corpus arm looked correct because the word
    was absent, and the generator arm looked correct because the word really did
    carry an inventory glyph — `й` is и + U+0306 under NFD. It surfaced only in
    the reading view, where the handle became a link into a lexicon that
    correctly held nothing for it. Russian is Tier-2; the ASCII policy does not
    reach it and no Cyrillic string is evidence about Bogoras's notation.
    """
    from harness.detectors import cyrillic
    assert cyrillic(nfd("Чукотскій")) and not cyrillic(nfd("kełiˊlın"))


def test_a_russian_word_gets_no_tier1_handle(tmp_path):
    """The generator's arm, against the page the class was found on."""
    from harness.context import tier1_terms
    _gt_page(tmp_path, "1-031", [
        ("instead of Tchukotski (Чукотскій),", 400, 1774),
        ("and the čauˊču beside it", 400, 1774),
    ])
    got = [t["text"] for t in tier1_terms("1-031", tmp_path)]
    assert nfd("čauˊču") in got
    assert not any("Ѐ" <= c <= "ӿ" for t in got for c in t)
