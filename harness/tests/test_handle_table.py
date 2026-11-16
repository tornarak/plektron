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


def test_the_chukchee_keeps_its_table_and_its_collisions():
    t = marks.handle_table(CHUKCHEE)
    assert not t.injective and t.passthrough == "ascii"
    assert marks.handle_key(nfd("Kuluˊči"), t) == "Kulu'c^i"
    with pytest.raises(marks.HandleTableError, match="not injective"):
        marks.form_from_key("Kulu'c^i", t)


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
    with pytest.raises(marks.HandleTableError, match="letter token"):
        marks.handle_table(root)


def test_a_case_pair_must_differ_in_case_alone(tmp_path):
    root = _table(tmp_path, tokens={"ӄ": "k_1", "Ӄ": "Q_1"})
    with pytest.raises(marks.HandleTableError, match="case pair"):
        marks.handle_table(root)


def test_an_injective_table_cannot_pass_ascii_through(tmp_path):
    root = _table(tmp_path, passthrough="ascii", tokens={"а": "a"})
    with pytest.raises(marks.HandleTableError, match="cannot pass every ASCII"):
        marks.handle_table(root)


def test_the_materials_table_keys_every_letter_its_own_inventory_adds():
    """The loader refuses otherwise; this pins that the live table passes it."""
    t = marks.handle_table(MATERIALS)
    for ch in "ӄӈђһѵðłӃӇЂҺѴÐŁ̧́̀":
        assert ch in t.tokens, f"U+{ord(ch):04X}"
