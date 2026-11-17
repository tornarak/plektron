"""The lexicon key table is a text's, and the *Materials*' is one-to-one."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from harness import marks

REPO = Path(__file__).resolve().parents[2]
MATERIALS = REPO / "jesup" / "bogoras-materials"
CHUKCHEE = REPO / "jesup" / "bogoras-chukchi"


def nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


CHUKCHEE_FORMS = {"Kuluˊči": "Kulu'c^i", "Kavraˊlɪt": "Kavra'li_t",
                  "Notaˊs˙qa-vaˊɪrg̣ɪn": "Nota's*qa-va'i_rg.i_n",
                  "Aˊmčê": "A'mc^e+", "Aivaˊʟaᵋt": "Aiva'l_ae_1t",
                  "keᵉinet": "kee_2inet", "Ñɪroˊn": "N~i_ro'n"}


@pytest.mark.parametrize("form", CHUKCHEE_FORMS)
def test_a_chukchee_key_round_trips_both_ways(form):
    t = marks.handle_table(CHUKCHEE)
    assert t.injective
    f = nfd(form)
    assert marks.handle_key(f, t) == CHUKCHEE_FORMS[form]
    assert marks.form_from_key(CHUKCHEE_FORMS[form], t) == f


def test_the_pairs_the_old_chukchee_table_merged_are_kept_apart():
    """`˙` and the dot below were both `.`, the caron and circumflex both `^`, and
    `ᵋ`, `ᵉ` and `ê` all `e^` — the last pair attested, though the table said its
    collisions were not."""
    t = marks.handle_table(CHUKCHEE)
    for a, b in [("s˙", "ṣ"), ("č", "ĉ"), ("ᵋ", "ᵉ"), ("ᵋ", "ê")]:
        assert marks.handle_key(nfd(a), t) != marks.handle_key(nfd(b), t), (a, b)


def test_a_straight_apostrophe_in_a_chukchee_form_is_unkeyable():
    """`'` in a key is the stress marker; U+0027 in a form is a Tier-1 trap for it
    (keying_spec.md §3) and must not key as the stressed form it imitates."""
    with pytest.raises(ValueError, match="U\\+0027"):
        marks.handle_key("Ke'rek", marks.handle_table(CHUKCHEE))


MATERIALS_FORMS = ["Ајӈан̀ва́т", "терк-арм", "Ӄаðе", "Кэlílђу", "500-ӈаӄ-тынӄоӄ",
                   "-ора́wеðат", "Мцѐ-мцáнlыӈын", "ӄытó-kalélų"]


@pytest.mark.parametrize("form", MATERIALS_FORMS)
def test_a_materials_key_round_trips_both_ways(form):
    t = marks.handle_table(MATERIALS)
    f = nfd(form)
    key = marks.handle_key(f, t)
    assert key.isascii()
    assert marks.form_from_key(key, t) == f
    assert marks.handle_key(marks.form_from_key(key, t), t) == key


def test_a_latin_l_and_a_cyrillic_el_never_share_a_key():
    """The tall `l` is keyed Latin, `л` is Cyrillic; one shape, two letters."""
    t = marks.handle_table(MATERIALS)
    assert marks.handle_key("lыӈ", t) != marks.handle_key("лыӈ", t)
    assert marks.handle_key("a", t) != marks.handle_key("а", t)


@pytest.mark.parametrize("key", ["k_", "_1", "q_7", "k_x", "w", "a«"])
def test_a_key_the_table_did_not_produce_is_refused(key):
    with pytest.raises(ValueError):
        marks.form_from_key(key, marks.handle_table(MATERIALS))


def _table(tmp_path, **doc):
    (tmp_path / "config" / "handle.json").write_text(json.dumps(
        {"injective": True, "passthrough": "-", **doc}))
    return tmp_path


def test_two_codepoints_on_one_token_are_refused(tmp_path):
    root = _table(tmp_path, tokens={"а": "a", "a": "a"})
    with pytest.raises(marks.HandleTableError, match="both key to"):
        marks.handle_table(root)


def test_a_token_outside_the_grammar_is_refused(tmp_path):
    root = _table(tmp_path, tokens={"ж": "zh"})
    with pytest.raises(marks.HandleTableError, match="not a letter or mark token"):
        marks.handle_table(root)


def test_a_case_pair_must_differ_in_case_alone(tmp_path):
    root = _table(tmp_path, tokens={"ӄ": "k_1", "Ӄ": "Q_1"})
    with pytest.raises(marks.HandleTableError, match="case pair"):
        marks.handle_table(root)


def _check(tokens, passthrough="-"):
    """The grammar alone, without a text's inventory to satisfy."""
    return marks._check_injective(tokens, passthrough, "t", frozenset())


def test_a_letter_passes_through_only_when_no_token_is_that_bare_letter():
    with pytest.raises(marks.HandleTableError, match="passthrough holds"):
        _check({"а": "a"}, "a-")
    t = marks.HandleTable(tokens={"ɪ": "i_"}, passthrough="ai-", injective=True,
                          inverse=_check({"ɪ": "i_"}, "ai-"))
    assert marks.form_from_key("ai_a", t) == "aɪa"


def test_a_digit_passes_through_only_when_no_token_ends_in_a_bare_underscore():
    with pytest.raises(marks.HandleTableError, match="passthrough holds"):
        _check({"ɪ": "i_"}, "i1")
    assert _check({"ɪ": "i_1"}, "i1") == {"i_1": "ɪ"}


def test_a_spacing_mark_may_take_a_mark_token_and_a_combining_one_must():
    assert _check({"ˊ": "'"}) == {"'": "ˊ"}
    with pytest.raises(marks.HandleTableError, match="not a mark token"):
        _check({"̣": "d_"})


def test_an_injective_table_cannot_pass_ascii_through(tmp_path):
    root = _table(tmp_path, passthrough="ascii", tokens={"а": "a"})
    with pytest.raises(marks.HandleTableError, match="cannot pass every ASCII"):
        marks.handle_table(root)


def test_the_materials_table_keys_every_letter_its_own_inventory_adds():
    """The loader refuses otherwise; this pins that the live table passes it."""
    t = marks.handle_table(MATERIALS)
    for ch in "ӄӈђһѵðłӃӇЂҺѴÐŁ̧́̀":
        assert ch in t.tokens, f"U+{ord(ch):04X}"
