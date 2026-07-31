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
