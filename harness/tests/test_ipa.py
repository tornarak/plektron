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
    """`ŭ` is its own sort with its own value, not `u` plus a length mark."""
    assert ipa.impute("ŭ").ipa == "ʉ̆"


@pytest.mark.parametrize("form,char", [
    ("Ṛɪˊṛak", "̣"),      # ṛ, no row by design
    ("nɪˊmɪḷu", "̣"),     # ḷ, likewise
    ("Poša", "̌"),        # š, likewise
    ("Kereˊtkun’s", "’"),  # a curly apostrophe, which Tier-1 forbids outright
    ("Egaˊč", "g"),        # plain g: the source table gives g̣ and not g
])
def test_a_sort_with_no_row_comes_back_partial_and_named(form, char):
    """Five sorts have a *gloss* in the p. 10 key and no IPA value, and
    turning a gloss into a symbol is a judgement. They fall through, and the
    character is named so the row is a worklist entry rather than a shrug."""
    r = ipa.impute(form)
    assert not r.complete
    assert char in r.unresolved


def test_the_undecidable_apostrophe_is_refused_rather_than_read():
    """U+0027 is both the spirant and the pause mark, disjoint by environment,
    and `keying_spec.md` says outright not to propose either. So it is not
    resolved in one direction for the sake of a complete-looking answer."""
    r = ipa.impute("ka'ta")
    assert not r.complete
    assert "'" in r.unresolved


def test_a_hedged_row_is_reported_as_hedged_and_still_emitted():
    """`g̣` is ɣ ~ ɡ in the source. The first value is emitted and the row is
    named, rather than the form being withheld or the choice being made by
    which value looked better."""
    r = ipa.impute("g̣a")
    assert r.complete
    assert r.ipa.startswith("ɣ")
    assert "g̣" in [unicodedata.normalize("NFC", h) for h in r.hedged]


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
