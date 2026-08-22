"""Mark–base licensing (keying_spec.md §2.6) — the one check that blocks a write.

Unlike every other detector this answers "impossible", not "worth a look", so a
false negative here lets an uncatalogued sequence into ground truth. `restore`
refuses on it.

The Cyrillic cases are a regression guard. `й` is `и` + U+0306 by *canonical*
decomposition, so corpus-wide NFD turns every ordinary Russian word into a
base+mark sequence, and `unlicensed_marks` reported all 72 in `data/authorities.json`
as errors — `MARK_LICENSE` was written for the Tier-1 Latin notation but runs over
every character in the corpus. The fix was an allow-list entry, and nothing tested it.
"""
import unicodedata

import pytest

from harness.detectors import MARK_LICENSE, unlicensed_marks

BREVE = "̆"


def nfd(s):
    return unicodedata.normalize("NFD", s)


@pytest.mark.parametrize("base", ["u", "i"])
def test_breve_licensed_on_the_latin_bases(base):
    assert unlicensed_marks(base + BREVE) == []


@pytest.mark.parametrize("base", ["и", "И"])
def test_breve_licensed_on_cyrillic_short_i(base):
    """`й`/`Й` — NFD-decomposed Russian, not notation. Regression: see module docstring."""
    assert unlicensed_marks(base + BREVE) == []


def test_real_russian_word_is_clean_under_nfd():
    """`Русскаго` … `й` in situ. The whole-corpus case that broke."""
    assert unlicensed_marks(nfd("Императорскій")) == []


@pytest.mark.parametrize("base", ["ɪ", "ᴀ", "ᴇ", "ä", "a", "e"])
def test_breve_unlicensed_on_the_obscure_vowel_series_and_others(base):
    """§2.6: the breve sits on `u`/`i`, never on `ᴀ ᴇ ɪ ä`.

    This is the constraint that makes `1-074`'s `Am-g̣roˊkĭ` readable at all — `i`
    drops its dot under an above-diacritic, so printed `ĭ` and a hypothetical `ɪ̆`
    are the same letterform and only the licence separates them.
    """
    hits = unlicensed_marks(base + BREVE)
    assert len(hits) == 1
    assert "U+0306" in hits[0]["mark"]


def test_mark_in_initial_position_has_no_base():
    hits = unlicensed_marks(BREVE + "u")
    assert len(hits) == 1
    assert "initial position" in hits[0]["base"]


def test_hit_carries_what_a_human_needs_to_adjudicate():
    (hit,) = unlicensed_marks("x" + BREVE)
    assert set(hit) == {"mark", "base", "licensed_on", "context"}
    assert "u" in hit["licensed_on"] and "i" in hit["licensed_on"]


def test_licence_is_a_closed_allow_list_per_mark():
    """Closed, not a deny-list: a deny-list silently admits every base nobody
    thought of, and the spec says licensing is by attestation only."""
    for mark, allowed in MARK_LICENSE.items():
        assert isinstance(allowed, set) and allowed


def test_input_need_not_be_pre_normalized():
    """Precomposed `ĭ` (U+012D) decomposes to a licensed pair; the caller should
    not have to know that."""
    assert unlicensed_marks("ĭ") == []


# ------------------------------------------- selecting Tier-1 tokens


@pytest.mark.parametrize("token", [
    "Nordenskiöld", "Müller", "Lütke", "für", "Völker", "Maïn", "Über",
])
def test_a_european_name_is_not_a_native_token(token):
    """U+0308 is an inventory member and also the commonest diacritic in German
    and Swedish, so a character-level membership test read these as Chukchi —
    43 occurrences over 12 types in gt/ocr, entering the frequency tables
    keying_spec.md §5.1 cites."""
    from harness.detectors import bears_inventory
    assert not bears_inventory(nfd(token))


@pytest.mark.parametrize("token", ["Черкасскій", "Чукотскій", "Край", "Ушканій"])
def test_pre_reform_russian_is_not_a_native_token(token):
    """й is и + U+0306, an inventory member meant as a length mark. Same class
    as the diaeresis above and the reason `cyrillic` exists."""
    from harness.detectors import bears_inventory
    assert not bears_inventory(nfd(token))


@pytest.mark.parametrize("token", ["vaˊɪrg̣ɪt", "ačaiˊkᴇlat", "kŭmɪˊñɪn",
                                   "Geëk", "vaˊlwɪjŋ-ä"])
def test_the_inventory_itself_still_selects(token):
    """The discount is per base, not per mark. `ä`/`ë` are §2.3 sorts and
    `ŭ`/`ĭ` are §2.2/§2.6 sorts — an exception keyed on the mark alone would
    have taken the inventory with it."""
    from harness.detectors import bears_inventory
    assert bears_inventory(nfd(token))


def test_a_mark_on_an_unnamed_base_still_selects():
    """`ORTHOGRAPHIC_BASES` is an exclusion list, so a base nobody has ruled on
    stays loud rather than being skipped."""
    from harness.detectors import bears_inventory
    assert bears_inventory(nfd("ÿ"))


def test_both_halves_of_the_comparison_select_the_same_way():
    """`proposal marks` compares a batch against a prior, and the two were built
    by different rules: only the prior excluded Cyrillic, so a Russian token
    counted on one side and not the other. A before/after is not a measurement
    unless both sides were made the same way."""
    import inspect

    from harness import detectors, marks
    prior = inspect.getsource(detectors.native_corpus_context)
    batch = inspect.getsource(marks.page_tokens)
    for src in (prior, batch):
        assert "bears_inventory(tok)" in src
        assert "cyrillic(tok)" in src
