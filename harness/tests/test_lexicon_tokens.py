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
- **U+0027 is not stripped** in this corpus. Inside a form it is a mistyped
  stress mark (keying_spec §2.1) — the error the apostrophe check exists to
  catch — and stripping it off a token's edge would hide it from every report;
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
    joined_words,
    lexicon_miss,
    midline_forms,
    native_corpus_lines,
    resolve_break_hyphens,
    suggest_lexicon,
)
from harness.tests.test_entities import entry

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def rec(text: str, hpos: int = 400, width: int = 1774) -> dict:
    """A line record. The geometry is carried for the other readers of these
    fixtures; `join_broken_words` reads `text` and the order alone."""
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


def test_geometry_never_decides_which_line_continues_a_word():
    """The continuation is the next non-empty line, whatever the boxes say.

    `1-314`: text set narrow beside a figure (hpos 1536) resumes the full
    measure once the figure ends (hpos 596), 940 px to the *left* of the stem.
    A geometric guard read that as a column break, skipped the real
    continuation and took the first word of the line after — so `mz/tei/`
    published `The Chuk-their` and the sentence lost `their` outright. Two such
    guards were tried and each corrupted an order of magnitude more joins than
    it fixed; `join_broken_words`'s docstring has the measurement. A page whose
    lines do not read in order is a `gt/zones/` defect and is fixed there.
    """
    out = join_broken_words([
        rec("with legs spread apart. The Chuk-", 1536, 833),
        rec("chee retaliate by saying that the Lamut girls are chained", 596, 1776),
        rec("their aprons are decorated with iron chains", 1159, 1213),
    ])
    assert out[0].endswith("The Chuk-chee")
    assert out[2].startswith("their aprons")


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
    """U+0027 inside a form is a keying error that must stay visible (§2.1)."""
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
    a straight apostrophe survives, and the token still cites the line it began on."""
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
    """`suggest_lexicon` end to end. `config/lexicon_extra.txt` supplies the
    lexicon, so the assertion does not depend on the machine's dictionary."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "lexicon_extra.txt").write_text(
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
# The proper nouns used to be listed twice: once in `config/lexicon_extra.txt` and
# once as an entity's canonical or alias. `detectors.entity_forms` made the
# second the only one. What these hold is the direction of the move — a name
# filed in `edition/entities/` stops being a miss — and the structural fact that keeps it
# from becoming a hole: the detector cannot see a marked form either way.


def _extra(root: Path, *terms: str) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "lexicon_extra.txt").write_text(
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
    """The dictionary is cached per root, and `edition/entities/` changes *inside* a
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


# --- the other question: every token, less the commonest ----------------------
#
# `--common N` exists because the dictionary arm above has a floor it cannot see
# past. A proper noun English happens to spell the same way as a word — `Wolf`,
# `Frost`, `Bering` — is accounted for by the dictionary and therefore never
# reaches the miss list, which is exactly the class of entity candidate the
# report is for. These hold the swap: the lexicon changes, the shape floor does
# not, and the stoplist is auditable rather than imported.

def _common(root: Path, n: int) -> dict:
    return suggest_lexicon(root, common=n)


def test_a_name_the_dictionary_spells_is_invisible_until_the_common_arm(tmp_path):
    """The motivating case, both arms over one page.

    `Wolf` is a headman here and a dictionary word everywhere, so the default
    arm accounts for it and reports nothing. Nothing about the token changed;
    what changed is which lexicon is allowed to account for it.
    """
    _extra(tmp_path, "wolf", "shaman", "answered")
    _gt_page(tmp_path, "1-001", [
        ("shaman answered shaman answered", 400, 1774),
        ("shaman answered Wolf", 400, 1774),
    ])
    assert "Wolf" not in {r["token"] for r in suggest_lexicon(tmp_path)["tokens"]}
    assert "Wolf" in {r["token"] for r in _common(tmp_path, 2)["tokens"]}


def test_the_common_arm_reports_only_the_shape_the_dictionary_arm_would(tmp_path):
    """One axis of change, not two. `of` and `sun` are under the floor and
    `1904` is not alphabetic, so none of them appears however the lexicon is
    asked — the flag widens what counts as *accounted for*, never what counts
    as a word."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("of the sun 1904 Ulakhpen", 400, 1774)])
    got = _common(tmp_path, 0)
    assert {r["token"] for r in got["tokens"]} == {"Ulakhpen"}


def test_the_cut_lands_on_a_frequency_boundary_and_says_so(tmp_path):
    """A tie at the Nth place is not split by alphabet.

    `sable` and `walrus` occur three times each; asking for the one commonest
    word cuts both, because deciding between them would be deciding on nothing
    but sort order. `scope.cut` reports the real number against the request.
    """
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [
        ("sable walrus sable walrus", 400, 1774),
        ("sable walrus Ulakhpen", 400, 1774),
    ])
    got = _common(tmp_path, 1)
    assert got["scope"][0]["asked"] == 1
    assert got["scope"][0]["cut"] == 2
    assert got["scope"][0]["floor"] == 3
    assert {r["token"] for r in got["tokens"]} == {"Ulakhpen"}


def test_the_stoplist_folds_case_where_the_rows_do_not(tmp_path):
    """`The` at a sentence head and `the` are one word for a stoplist; `Frost`
    and `frost` are two findings, one of which may be a person.

    Discriminating, not decorative: folded, `frost` totals four and is the
    single commonest form, so both spellings leave. Unfolded it would total
    three, tie with `sable`, and `Frost` would be reported as a candidate on
    the strength of its own capital — which is the opposite of the answer.
    """
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [
        ("frost sable frost sable", 400, 1774),
        ("frost sable Frost", 400, 1774),
    ])
    got = _common(tmp_path, 1)
    reported = {r["token"] for r in got["tokens"]}
    assert "Frost" not in reported and "frost" not in reported
    assert "sable" in reported


def test_ranking_ignores_what_the_shape_floor_already_hides(tmp_path):
    """N is spent on words that could have been reported, not on `the`.

    `the` is printed five times and is never reportable at any N, so ranking
    over raw tokens would spend the whole of a one-word request on a word that
    was already invisible and report both of the real ones.
    """
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [
        ("the the the the the", 400, 1774),
        ("walrus walrus walrus sable sable", 400, 1774),
    ])
    got = _common(tmp_path, 1)
    assert got["scope"][0]["cut"] == 1
    assert {r["token"] for r in got["tokens"]} == {"sable"}


def test_the_entity_store_is_the_only_suppressor_under_the_common_arm(tmp_path):
    """`lexicon_extra.txt` stops accounting for anything here — that is the
    whole of the swap — and the entity store keeps its named list, so what it
    absorbs is still visible rather than gone."""
    _extra(tmp_path, "Ulakhpen")
    entry(tmp_path, "person:gondatti", canonical="Nikolai Gondatti",
          aliases=[("Gondatti", False)])
    _gt_page(tmp_path, "1-001", [
        ("shaman shaman shaman shaman", 400, 1774),
        ("Gondatti reports the Ulakhpen", 400, 1774),
    ])
    got = _common(tmp_path, 1)
    assert "Ulakhpen" in {r["token"] for r in got["tokens"]}
    assert "Gondatti" in {r["token"] for r in got["suppressed"]}
    assert "Gondatti" not in {r["token"] for r in got["tokens"]}


def test_the_boundary_window_is_the_tail_of_the_cut(tmp_path):
    """A stoplist nobody can see is the defect this group refuses in a
    whitelist. The head is a count; the tail — the least frequent forms N
    swallowed — is printed, because that is the part that says whether N was
    well chosen."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [
        ("sable sable sable walrus walrus", 400, 1774),
        ("marten Ulakhpen", 400, 1774),
    ])
    got = _common(tmp_path, 2)
    assert [b["form"] for b in got["boundary"]] == ["sable", "walrus"]
    assert got["boundary"][-1]["count"] == got["scope"][0]["floor"]
    assert "marten" in {r["token"] for r in got["tokens"]}


def test_asking_for_more_words_than_the_corpus_has_reports_nothing(tmp_path):
    """The honest answer to the question as asked. Reporting everything instead
    would read as a full worklist on a corpus too small to have made a stoplist
    of, which is the misleading direction."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("sable walrus marten", 400, 1774)])
    got = _common(tmp_path, 1000)
    assert got["scope"][0]["cut"] == got["scope"][0]["forms"] == 3
    assert got["tokens"] == [] and got["suppressed"] == []


def test_the_default_arm_keeps_its_shape(tmp_path):
    """No `scope` and no `boundary` without the flag: the report a skill or a
    script already reads is unchanged by the flag existing."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("the Ulakhpen", 400, 1774)])
    assert set(suggest_lexicon(tmp_path)) == {"tokens", "suppressed"}


# --- what dropping the dictionary exposed -------------------------------------
#
# Both of these were invisible while the dictionary did the filtering, and both
# turn one name into two findings or into a hundred.

def test_a_possessive_counts_as_the_name_it_is_made_from(tmp_path):
    """`EDGE_PUNCT` cannot reach the apostrophe — the token ends in `s`, so the
    strip stops before it — and a name the book mostly sets possessively ranks
    twice and reads as two candidates."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [
        ("Ulakhpen went and Ulakhpen’s sledge and Ulakhpen's dog", 400, 1774)])
    rows = {r["token"]: r["count"] for r in _common(tmp_path, 0)["tokens"]}
    assert rows == {"Ulakhpen": 3, "sledge": 1, "went": 1}


def test_an_apostrophe_inside_a_compound_survives(tmp_path):
    """`Raven’s-Beak` and `cat’s-cradle` are the corpus's own forms and the
    apostrophe is not a trailing possessive. Only the ending folds."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("the Raven’s-Beak constellation", 400, 1774)])
    assert "Raven’s-Beak" in {r["token"] for r in _common(tmp_path, 0)["tokens"]}


def test_the_possessive_fold_does_not_reach_a_tier1_apostrophe(tmp_path):
    """**The trap this fold is one line away from.** `detect_all`'s tokenizer
    keeps U+0027 deliberately so the apostrophe check can see it inside a form
    (§2.1: a keying error there); a possessive fold applied there would hide
    it from every flag in the corpus. The question here is about English word
    forms, and only this branch asks it."""
    from harness.detectors import detect_all
    got = detect_all(["the form kelet's here"], tmp_path)
    assert any(t["token"] == "kelet's" for t in got["tokens"])


def test_a_capital_the_printer_put_there_is_named_and_not_reported(tmp_path):
    """Every occurrence opens a sentence, and the dictionary carries the word.
    Both, so the row moves to `sentence_heads` — where it is still visible,
    because a filter nobody can see is a filter nobody can correct."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [
        ("He went. Nevertheless he stayed. Nevertheless she left.", 400, 1774)])
    got = _common(tmp_path, 0)
    assert "Nevertheless" not in {r["token"] for r in got["tokens"]}
    row, = [r for r in got["sentence_heads"] if r["token"] == "Nevertheless"]
    assert row["count"] == row["initial"] == 2


def test_one_occurrence_is_not_evidence_of_anything(tmp_path):
    """**The floor the other two conditions need.** "Every occurrence opens a
    sentence" is a coin that came up heads once, and the cut without this held
    back `Birch`, `Goose`, `Ross`, `Peters`, `Rudolf`, `Walruses`, `Ptarmigans`
    and `Hildebrand` — every one a real candidate seen exactly once, and the
    dictionary carries them all, `allen` and `parry` included."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("The man spoke. Birch stood there.", 400, 1774)])
    got = _common(tmp_path, 0)
    row, = [r for r in got["tokens"] if r["token"] == "Birch"]
    assert row["count"] == row["initial"] == 1
    assert got["sentence_heads"] == []


def test_a_name_that_never_falls_mid_sentence_is_still_reported(tmp_path):
    """**Why the drop takes two conditions and not one.** On position alone a
    toponym that happens always to open its sentence would vanish silently,
    which is the failure this whole report exists to prevent."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("Ulakhpen is cold. Ulakhpen is far.", 400, 1774)])
    got = _common(tmp_path, 0)
    row, = [r for r in got["tokens"] if r["token"] == "Ulakhpen"]
    assert row["count"] == row["initial"] == 2


def test_a_dictionary_word_off_the_sentence_head_is_still_reported(tmp_path):
    """The other half of the conjunction. `Frost` mid-sentence is a name the
    dictionary happens to spell, which is exactly what `--common` is for."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("Frost came. The man Frost spoke.", 400, 1774)])
    row, = [r for r in _common(tmp_path, 0)["tokens"] if r["token"] == "Frost"]
    assert row["count"] == 2 and row["initial"] == 1


def test_a_line_break_is_not_a_sentence_break(tmp_path):
    """The ALTO holds one printed line per record and a sentence runs across as
    many as the compositor needed. Asking "first token of its line" would call
    every line's opening word a sentence head, which is most of the page."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("the man saw", 400, 1774),
                                 ("Ulakhpen there", 400, 1830)])
    row, = [r for r in _common(tmp_path, 0)["tokens"] if r["token"] == "Ulakhpen"]
    assert row["initial"] == 0


def test_a_closing_quote_does_not_hide_the_full_stop(tmp_path):
    """`…said so.” Nevertheless` is a sentence head, and a scan that stopped at
    the quote would not see it."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [('he said so.” Ulakhpen went', 400, 1774)])
    row, = [r for r in _common(tmp_path, 0)["tokens"] if r["token"] == "Ulakhpen"]
    assert row["initial"] == 1


# --- the two shape floors, held apart -----------------------------------------
#
# `lexicon_miss` is both a detector and `--common`'s shape floor, and the ASCII
# half of it means two different things in the two roles. As a detector it says
# "an English dictionary cannot judge this token", which is a reason to decline;
# as a worklist floor it silently said "this is not a word", which is false of
# `Œstrus`. These tests hold the difference, in both directions.

def test_the_detector_still_declines_a_ligature(tmp_path):
    """The default is unchanged and must stay so: `lexicon_miss` is one arm of
    the transcription detector, where a non-ASCII token is the *inventory*
    branch's business and this branch's silence is deliberate."""
    assert not lexicon_miss("Œstrus", frozenset())
    assert not lexicon_miss("Salmonidæ", frozenset())


def test_the_worklist_floor_admits_a_ligature(tmp_path):
    """`Coregonidæ` is printed once, at 1-188, and names a fish family. Under
    the shared floor it reached no report at all."""
    assert lexicon_miss("Œstrus", frozenset(), admit_foreign=True)
    assert lexicon_miss("Coregonidæ", frozenset(), admit_foreign=True)
    assert lexicon_miss("Grønland", frozenset(), admit_foreign=True)


def test_the_worklist_floor_still_refuses_a_romanization(tmp_path):
    """The floor widens on one axis — no inventory mark — and not on script.
    Dropping `isascii` outright took `forms` from 9,367 to 9,860, some five
    hundred of them the corpus's own Tier-1 forms, which are not English words
    and are what the floor exists to keep out."""
    for form in ("Pehiˊttin", "Uñiˊin", "Kavraˊlɪn", "mêˊmêl"):
        assert not lexicon_miss(form, frozenset(), admit_foreign=True), form


def test_the_worklist_floor_admits_russian(tmp_path):
    """Cyrillic passes, and should: this list feeds the entity and lexicon
    stores and both hold Russian. `нерпа` and `ларга` are 1-151's seal glosses,
    beside the `акипка` the store already carries as an alias."""
    assert lexicon_miss("нерпа", frozenset(), admit_foreign=True)
    assert lexicon_miss("Вахня", frozenset(), admit_foreign=True)


def test_a_ligature_row_is_not_reported_as_suppressed(tmp_path):
    """The `tokens`/`suppressed` split has to ask under the same floor the rows
    were gathered under. Under the default one every ligature row answers *no
    component is a miss* and lands in `suppressed`, reading as "the entity store
    accounts for this" when the store has never seen it."""
    _extra(tmp_path, "placeholder")
    _gt_page(tmp_path, "1-001", [("shoals of Salmonidæ resort here", 400, 1774)])
    got = _common(tmp_path, 0)
    assert "Salmonidæ" in {r["token"] for r in got["tokens"]}
    assert "Salmonidæ" not in {r["token"] for r in got["suppressed"]}


# --- the compositor's hyphen, closed against the corpus's own witness ---------

def test_the_join_reports_where_it_cut():
    """The offset is the whole of what separates `Chuk-chee` from `so-called`,
    and it exists for exactly as long as the join keeps it. `join_broken_words`
    throws it away because its six callers want the token intact; the arm that
    sets prose takes it."""
    texts, cuts = joined_words([rec("of the Chuk-"), rec("chee people")])
    assert texts == ["of the Chuk-chee", "people"]
    assert cuts == [[11], []]
    assert texts[0][cuts[0][0]] == "-"


def test_a_word_broken_twice_carries_both_cuts():
    """Both hyphens in `trans-for-mations` are the printer's, and the second was
    put there by a splice that happened before the first. The offsets follow the
    text through both, which is why they are absolute in the line."""
    texts, cuts = joined_words([rec("trans-"), rec("for-"), rec("mations here")])
    assert texts[0] == "trans-for-mations"
    assert [texts[0][c] for c in cuts[0]] == ["-", "-"]
    assert cuts[0] == [5, 9]


def test_a_donor_line_keeps_its_own_cuts_when_it_loses_its_head():
    """A line can be both stem and donor. `bbb-ccc` was joined on line 1 and
    line 0 then took `aaa` off its head, so line 1's remaining cut has to move
    back by what it lost — a cut that stayed put would name a letter."""
    texts, cuts = joined_words([rec("trans-"), rec("aaa bbb-"), rec("ccc")])
    assert texts == ["trans-aaa", "bbb-ccc", ""]
    assert [texts[i][c] for i, cs in enumerate(cuts) for c in cs] == ["-", "-"]


def test_a_token_carrying_a_cut_is_not_a_witness_to_its_own_spelling(tmp_path):
    """The one thing this index has to get right. A page that broke `Chuk-chee`
    would otherwise attest `Chuk-chee` mid-line and confirm every break in it,
    which is the same-file hazard in the shape it takes here."""
    _gt_page(tmp_path, "1-001", [("of the Chuk-", 400, 1774),
                                 ("chee people", 400, 1774)])
    assert midline_forms(tmp_path) == {"of": (1, frozenset({"1-001"})),
                                       "the": (1, frozenset({"1-001"})),
                                       "people": (1, frozenset({"1-001"}))}


def test_the_corpus_closes_a_hyphen_it_accounts_for(tmp_path):
    """`Chuk-chee` against 1 mid-line `Chukchee` on another page. The dictionary
    could not have answered this one — no wordlist of English carries it — and
    the corpus answers it 2,931 times."""
    idx = {"chukchee": (2931, frozenset({"1-002", "1-003"}))}
    text, verdicts = resolve_break_hyphens("of the Chuk-chee", [11], "1-001", idx)
    assert text == "of the Chukchee"
    assert verdicts == [{"token": "Chuk-chee", "resolved": "Chukchee",
                         "verdict": "joined", "joined": 2931, "hyphenated": 0}]


def test_the_corpus_keeps_a_hyphen_the_book_sets(tmp_path):
    """`new-born` is the case the dictionary rule got wrong: `newborn` is a word
    of modern English and not one of this book's, which sets the hyphen 10 times
    away from any line end. Nothing is written, and that is the point."""
    idx = {"new-born": (10, frozenset({"1-002", "1-003"}))}
    text, verdicts = resolve_break_hyphens("a new-born calf", [5], "1-001", idx)
    assert text == "a new-born calf"
    assert verdicts[0]["verdict"] == "kept"
    assert (verdicts[0]["hyphenated"], verdicts[0]["joined"]) == (10, 0)


def test_a_tie_and_a_silence_are_both_left_open(tmp_path):
    """Two different silences and neither is a verdict. `spring-time` 6 against
    `springtime` 6 is a page the reader settles; a form the book sets once, here,
    has no witness at all. Both keep the hyphen and both get a comment."""
    tie = {"spring-time": (6, frozenset({"1-002", "1-003"})),
           "springtime": (6, frozenset({"1-004", "1-005"}))}
    text, vs = resolve_break_hyphens("in spring-time here", [9], "1-001", tie)
    assert text == "in spring-time here" and vs[0]["verdict"] == "open"
    text, vs = resolve_break_hyphens("a nose-plumage", [6], "1-001", {})
    assert text == "a nose-plumage" and vs[0]["verdict"] == "open"


def test_the_page_being_resolved_is_not_its_own_witness(tmp_path):
    """A form attested only on the page whose hyphen is in question decides
    nothing. `_attested` is the guard, and two refs are kept per form because two
    is what answers *some other page*."""
    only_here = {"chukchee": (40, frozenset({"1-001"}))}
    text, vs = resolve_break_hyphens("the Chuk-chee", [8], "1-001", only_here)
    assert text == "the Chuk-chee", "40 hits, all of them this page, decide nothing"
    assert vs[0]["verdict"] == "open"
    elsewhere = {"chukchee": (40, frozenset({"1-001", "1-002"}))}
    text, _ = resolve_break_hyphens("the Chuk-chee", [8], "1-001", elsewhere)
    assert text == "the Chukchee"


def test_a_tier1_form_is_refused_before_any_count_is_consulted(tmp_path):
    """The firewall, and the one place in this rule it reaches. Inside the
    notation U+002D is a licensed sort, so closing one edits an inventory
    character — and an index saying `Torwaˊwaq` 90 times would not make that a
    reading a rule may originate."""
    idx = {"torwaˊwaq": (90, frozenset({"1-002", "1-003"}))}
    form = nfd("(Tor-waˊwaq)")
    text, vs = resolve_break_hyphens(form, [4], "1-001", idx)
    assert text == form
    assert vs[0]["verdict"] == "tier1"
    assert (vs[0]["joined"], vs[0]["hyphenated"]) == (0, 0), \
        "refused, not outvoted — no count was read"
