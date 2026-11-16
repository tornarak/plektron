"""The review keyboard is a text's, read from `config/keyboard.json`."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from harness.review import KeyboardError, kbd_context, keyboard

JESUP = Path(__file__).resolve().parents[2] / "jesup"


def test_the_chukchee_types_the_layout_it_always_had():
    """Moved out of the code key for key: the bindings the editor learned survive."""
    keys = keyboard(JESUP / "bogoras-chukchi")["keys"]
    assert keys["a"] == "ᴀ" and keys["'"] == "ˊ" and keys["R"] == "ř"
    assert keys["."] == "̣" and keys["="] == "̆"
    assert all(unicodedata.normalize("NFD", g) == g for g in keys.values())


def test_the_materials_type_cyrillic_and_the_notation():
    kb = keyboard(JESUP / "bogoras-materials")
    keys = kb["keys"]
    assert keys["a"] == "а" and keys["A"] == "А" and keys["1"] == "ӄ"
    assert keys["'"] == "́"
    # Every letter this book's notation adds is reachable from a key (its inventory
    # also inherits the workspace's Latin letters, which it does not print).
    from harness import keying
    rules = keying.rules(JESUP / "bogoras-materials")
    letters = {p[1] for p, tier in rules.origin.items()
               if p[0] == "inventory" and tier.startswith("text")
               and not unicodedata.category(p[1]).startswith("M")}
    assert len(letters) == 14
    assert letters <= set(keys.values())
    # ...and every letter of its Russian, the pre-1918 ones among them.
    alphabet = set(rules.prose_alphabet["Cyrl"])
    shown = {g for _, gs in kb["palette"] for g in gs}
    assert alphabet <= shown


def test_a_texts_keyboard_replaces_its_workspaces_whole(tmp_path):
    (tmp_path / "config" / "keyboard.json").write_text(json.dumps(
        {"keys": {"q": "я"}, "palette": [{"label": "one", "glyphs": ["я"]}]}))
    ctx = kbd_context(tmp_path)
    assert ctx["kbd_keys"] == {"q": "я"}
    assert [k["key"] for g in ctx["palette"] for k in g["glyphs"]] == ["q"]


def test_a_bound_glyph_with_no_button_is_refused(tmp_path):
    (tmp_path / "config" / "keyboard.json").write_text(json.dumps(
        {"keys": {"q": "я"}, "palette": [{"label": "one", "glyphs": ["ю"]}]}))
    with pytest.raises(KeyboardError, match="no palette button"):
        keyboard(tmp_path)


def test_no_keyboard_is_refused_rather_than_defaulted(tmp_path):
    (tmp_path / "config" / "keyboard.json").unlink()
    with pytest.raises(KeyboardError, match="never a default"):
        keyboard(tmp_path)


def test_a_key_is_one_printable_character(tmp_path):
    (tmp_path / "config" / "keyboard.json").write_text(json.dumps(
        {"keys": {"ctrl-q": "я"}, "palette": [{"label": "one", "glyphs": ["я"]}]}))
    with pytest.raises(KeyboardError, match="one printable"):
        keyboard(tmp_path)
