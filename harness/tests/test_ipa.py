"""The Bogoras -> IPA rule table.

Nothing here asserts that a value is phonetically right — that is the source's
claim, not the code's. What is pinned is the *mechanics*: that the table
reaches NFD text, that a form which did not fully resolve says so, and that the
handful of context rules do what they say.
"""
from __future__ import annotations

import unicodedata

import pytest

from harness import ipa


def test_the_table_matches_the_decomposed_corpus():
    """`č` is c + U+030C everywhere in this corpus and composes in a source
    file. A table that matched only the composed form would resolve nothing and
    report every marked form partial."""
    r = ipa.impute("Kuluˊči")
    assert r.complete
    assert r.ipa == "kuːluːt͡ʃiː"


def test_a_composed_form_reaches_the_same_answer():
    """The CLI takes a form off a human's keyboard, which may be NFC."""
    nfc = unicodedata.normalize("NFC", "Kuluˊči")
    assert ipa.impute(nfc).ipa == ipa.impute("Kuluˊči").ipa


def test_case_is_folded():
    """An initial capital is orthography. `Uweˊlen` mid-sentence is the same
    word said the same way."""
    assert ipa.impute("Uweˊlen").ipa == ipa.impute("uweˊlen").ipa


def test_the_stress_mark_is_dropped_and_not_placed():
    """U+02CA follows the stressed vowel; IPA's ˈ precedes the stressed
    syllable. Placing it needs syllabification, so it is dropped rather than
    guessed — and dropping it is not a fall-through."""
    r = ipa.impute("Uweˊlen")
    assert r.complete and not r.unresolved
    assert "ˈ" not in r.ipa and ipa.STRESS not in r.ipa


def test_the_stress_mark_separates_a_diphthong_from_a_hiatus():
    """`au` is one diphthong and `aˊu` is two vowels, because the print puts
    the mark on the vowel it belongs to. The table gets this for free from
    longest-match, and it is worth pinning: it is the one place the dropped
    stress mark still does work."""
    assert ipa.impute("kau").ipa == "kau̯"
    assert ipa.impute("kaˊu").ipa == "kaːuː"


def test_a_breve_takes_the_length_off_rather_than_stacking_on_it():
    """The plain vowels are long in this notation, so extra-shortness over one
    is a contradiction on the page's own terms, not a stack. `ĭ` is a short i.
    """
    assert ipa.impute("ĭ").ipa == "i" + ipa.SHORT
    assert "ː" not in ipa.impute("ĭ").ipa


def test_a_macron_gives_the_extra_length_it_names():
    assert ipa.impute("ā").ipa == "aːː"


def test_the_dedicated_breve_sort_beats_the_generic_mark():
    """`ŭ` is its own sort with its own value, not `u` plus a length mark.

    **Unmarked, and the breve stays with the mark.** Both sources distinguish
    "short" — which is what this sort is — from "very short", which is what a
    breve written over a vowel means. Spending the breve on the sort left the
    mark nothing to say; the contrast is carried instead by the length the
    plain vowels get and this one does not.
    """
    assert ipa.impute("ŭ").ipa == "ʉ"
    assert ipa.SHORT not in ipa.impute("ŭ").ipa


def test_the_obscure_series_is_one_vowel():
    """ᴀ ᴇ ɪ are glossed jointly as "obscure vowels (short)" and nothing in
    either source tells them apart. They were rendered three ways — ə̆, ə̆ ~ ɛ̆
    and ɪ̆ — which read `ɪ` as its own IPA value and invented a distinction the
    page does not make. Modern Chukchi's pervasive epenthetic schwa is the same
    distribution."""
    assert {ipa.impute(c).ipa for c in ("ᴀ", "ᴇ", "ɪ")} == {"ə"}


def test_the_rising_diphthong_keeps_its_laryngeal_either_way():
    """"It always has a laryngeal intonation, ᵉiᵋ" — so the bare spelling is
    not a plain diphthong, and the two spellings are one thing."""
    assert ipa.impute("ᵉi").ipa == ipa.impute("ᵉiᵋ").ipa
    assert ipa.impute("ᵉi").ipa.endswith("ˀ")


def test_the_rising_diphthong_is_prominent_on_its_closing_element():
    """"A diphtong with an accent on *i*", and `keying_spec.md` §2.5's
    "prominence on the closing element, opening element cast superscript".
    `ei̯` marks the *i* non-syllabic, which is the other diphthong."""
    assert ipa.impute("ᵉi").ipa.startswith("e" + "̯")


def test_o_is_read_the_same_way_alone_and_in_its_diphthong():
    """`oi` was `oi̯` while `o` was `ɔ`, in adjacent rows of one table. The
    gloss is "like *oi* in *choice*"."""
    assert ipa.impute("o").ipa == "ɔ"
    assert ipa.impute("oi").ipa.startswith("ɔ")


def test_aspiration_attaches_to_what_precedes_it():
    """`h` is a-semantic aspiration, not a segment: Mythology has it "used
    after č, t, l" and modern Chukchi has no /h/ at all. Word-initially there
    is nothing to attach to, and p. 10's plain "as in English" answers."""
    assert ipa.impute("alha").ipa == "aːlʰaː"
    assert ipa.impute("ha").ipa == "haː"


@pytest.mark.parametrize("form,char", [
    ("Ṛɪˊṛak", "̣"),      # ṛ, no row by design
    ("nɪˊmɪḷu", "̣"),     # ḷ, likewise
    ("Poša", "̌"),        # š, likewise
    ("Kereˊtkun’s", "’"),  # a curly apostrophe, which Tier-1 forbids outright
])
def test_a_sort_with_no_row_comes_back_partial_and_named(form, char):
    """Four sorts have a *gloss* in the p. 10 key and no IPA value, and
    turning a gloss into a symbol is a judgement. They fall through, and the
    character is named so the row is a worklist entry rather than a shrug.

    Plain `g` used to be a fifth entry here, on the reasoning that "the source
    table gives g̣ and not g" — which was true of Mythology and false of the
    p. 10 key, where `g` is glossed "like *g* in *good*". It has a row now."""
    r = ipa.impute(form)
    assert not r.complete
    assert char in r.unresolved


def test_the_undecidable_apostrophe_is_refused_rather_than_read():
    """U+0027 has no licensed position inside a Tier-1 form (`keying_spec.md`
    §2.1): a form still carrying one is a keying error awaiting repair, not a
    sound, so it is not resolved for the sake of a complete-looking answer."""
    r = ipa.impute("ka'ta")
    assert not r.complete
    assert "'" in r.unresolved


def test_a_hedged_row_is_reported_as_hedged_and_still_emitted():
    """`ʟ` is ɬʲ ≈ ɬ. The first value is emitted and the row is named, rather
    than the form being withheld or the choice being made by which value
    looked better."""
    r = ipa.impute("ʟa")
    assert r.complete
    assert r.ipa.startswith("ɬʲ")
    assert "ʟ" in [unicodedata.normalize("NFC", h) for h in r.hedged]


def test_the_velar_g_is_no_longer_hedged_against_a_voiced_stop():
    """`g̣` was ɣ ~ ɡ. Modern Chukchi has no native voiced stops — "these are
    only found in loanwords" — so ɡ was never available for it; and ɡ is the
    value that belongs to plain `g`, which had no row while this one was
    offering its value away."""
    r = ipa.impute("g̣ag")
    assert r.complete and not r.hedged
    assert r.ipa == "ɣaːɡ"


def test_every_row_has_a_modern_correspondence():
    """`MODERN` is the reconciliation against current descriptions of the
    language, kept beside the table rather than folded into it — what `impute`
    emits is Bogoras's account of his own notation, and the two disagree
    systematically. A row with no entry is a row nobody has looked at."""
    have = {unicodedata.normalize("NFD", k) for k in ipa.MODERN}
    assert {unicodedata.normalize("NFD", s) for s, _, _, _ in ipa.RULES} == have


def test_the_grades_of_the_rows_a_form_used_are_reported():
    """`Ciˊṛluk` needs the p. 10 key for its `c` and the mythology front
    matter for the rest, and the card has to be able to say so."""
    assert ipa.impute("čaˊuču").grades == {ipa.MYTH}
    assert ipa.KEY in ipa.impute("ciˊluk").grades


def test_rows_pad_to_a_uniform_key_set():
    """Several forms pool into one table, and a row that dropped its empty
    columns would collapse the whole thing into the nested rendering."""
    rows = ipa.rows(["Uweˊlen", "Poša"])
    assert {tuple(r) for r in rows} == {tuple(rows[0])}
