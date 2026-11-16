"""Under a text's `prose_stands` ruling, plain prose reaches `gt/ocr/` on the reading.

The editor ruled it for the 1900 *Materials* (2026-11-07): Russian prose with no
native form in it may stand on a model's reading, and only the native forms and
the doubts wait on a human. The cases that matter are the edges of "plain":
a listed native form, a doubt, a letter outside the prose alphabet, and a human
decision, which must always win.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest
from conftest import JESUP_KEYING
from test_mz_to_gt import _mz_page

from harness import keying
from harness.review import restore, restore_skip, save_decisions, standing

JESUP = JESUP_KEYING.parents[1]
RU = "абвгдежзиклмнопрстуфхцчшщъыьэюяіѣѳАБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯІѢѲ"


def _text(root: Path, ruling: str | None = "the editor's ruling, in words") -> Path:
    """A text whose prose is Russian, with or without the ruling."""
    rec = json.loads((root / "project.json").read_text(encoding="utf-8"))
    rec["lang"] = "ru"
    if ruling is not None:
        rec["prose_stands"] = ruling
    (root / "project.json").write_text(json.dumps(rec), encoding="utf-8")
    rules = json.loads(JESUP_KEYING.read_text(encoding="utf-8"))
    rules["tier2_scripts"] = {}
    rules["prose_alphabet"] = {"Cyrl": RU}
    (root / "config/keying.json").write_text(json.dumps(rules, ensure_ascii=False),
                                             encoding="utf-8")
    return root


def _read(root: Path, lines: dict[int, dict], ref: str = "1-060") -> None:
    _mz_page(root, ref, texts=tuple(f"layer {i}" for i in lines))
    p = root / "review" / ref / "proposal.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ref": ref, "lines": {
        str(i): {k: unicodedata.normalize("NFD", v) for k, v in rec.items()}
        for i, rec in lines.items()}}, ensure_ascii=False), encoding="utf-8")


PAGE = {0: {"text": "II В. Г. БОГОРАЗЪ,"},
        1: {"text": "Съ января 1896 г., послѣ встрѣчи съ чукчей"},
        2: {"text": "Ајңанват’омъ и при", "native": "Ајңанват’омъ"}}


def test_prose_stands_and_a_native_form_waits(tmp_path):
    _read(_text(tmp_path), PAGE)
    assert sorted(standing("1-060", tmp_path)) == [0, 1]
    with pytest.raises(ValueError, match=r"1 of 3 lines have no decision \(indices \[2\]"):
        restore("1-060", tmp_path, "mz/ocr")


def test_the_editor_decides_the_rest_and_the_report_says_what_stood(tmp_path):
    _read(_text(tmp_path), PAGE)
    save_decisions("1-060", {2: {"text": "Ајңан̀ва́т’омъ и при"}}, tmp_path)
    rep = restore("1-060", tmp_path, "mz/ocr", commit=True)
    assert rep["stood"] == [0, 1] and rep["text_mismatch"] == []


def test_a_decision_overrules_a_line_that_would_stand(tmp_path):
    _read(_text(tmp_path), PAGE)
    save_decisions("1-060", {1: {"text": "Съ января 1896 г."},
                             2: {"text": "Ајңанват’омъ и при"}}, tmp_path)
    rep = restore("1-060", tmp_path, "mz/ocr")
    assert rep["stood"] == [0]
    assert {e["line"] for e in rep["edits"]} == {1}


@pytest.mark.parametrize("rec", [
    {"text": "Тоже въ обоихъ", "class": "doubt", "note": "Тоже or Тоже?"},
    {"text": "Tоже въ обоихъ"},                # a Latin T: an OCR slip, not prose
    {"text": "Commissionaires de l'Académie"},  # French is not this text's prose
    {"text": "мэlэ́ въ обоихъ"},              # the tall l and an acute
])
def test_what_is_not_plain_prose_waits(tmp_path, rec):
    _read(_text(tmp_path), {0: rec})
    assert standing("1-060", tmp_path) == {}


def test_without_the_ruling_nothing_stands(tmp_path):
    _read(_text(tmp_path, ruling=None), PAGE)
    assert standing("1-060", tmp_path) == {}
    assert restore_skip("1-060", tmp_path) == "no decisions"


def test_a_sweep_takes_a_page_whose_every_line_stands(tmp_path):
    _read(_text(tmp_path), {0: PAGE[0], 1: PAGE[1]})
    assert restore_skip("1-060", tmp_path) == ""
    _read(tmp_path, PAGE)
    assert "1 line(s) do not stand" in restore_skip("1-060", tmp_path)


def test_an_empty_ruling_is_refused(tmp_path):
    from harness.layout import ProjectError, project
    _text(tmp_path, ruling=" ")
    with pytest.raises(ProjectError, match="prose_stands"):
        project(tmp_path)


def test_the_1900_text_carries_the_ruling_and_the_chukchee_does_not():
    from harness.layout import prose_stands
    assert prose_stands(JESUP / "bogoras-materials")
    assert prose_stands(JESUP / "bogoras-chukchi") is None


@pytest.mark.parametrize("line,prose", [
    ("горія Чаина), которые, говоря по чукотски съ полной бѣглостью,", True),
    ("I,1. МАТЕРІАЛЫ ПО ИЗУЧЕНІЮ ЧУКОТСКАГО ЯЗЫКА", True),
    ("Чукотскій миѳологическаго", True),         # й is и + an orthographic breve
    ("Продается у коммиссіонеровЪ", False),      # a capital mid-word is a slip
    ("изъ частей Сѣверо-Тихоокеанской", True),   # a hyphen starts a new word half
    ("Сѣверо-ТихоокеанскоЙ", False),
    ("Нагорный, Анадырь", True),
    ("терк-арм", True),           # no glyph marks it: why `native` is listed by hand
    ("Ӄаават-ешӄан, кырңат-ешӄан", False),
    ("ораwеďат", False),
    ("Кутјэ́ўт", False),
])
def test_prose_only_admits_the_alphabet_and_nothing_else(line, prose):
    from harness.detectors import prose_only
    b = keying.rules(JESUP / "bogoras-materials")
    assert prose_only(unicodedata.normalize("NFD", line), b) is prose
    assert prose_only(line, keying.rules(JESUP / "bogoras-chukchi")) is False


def test_the_review_row_spells_out_only_what_the_prose_alphabet_lacks():
    from harness.review import notable
    b = keying.rules(JESUP / "bogoras-materials")
    nfd = lambda s: unicodedata.normalize("NFD", s)  # noqa: E731
    assert notable(nfd("Группа II: составляющей «одну» — № 5"), b) == []
    assert notable(nfd("Кутјэ́ўт пы́ӈыlте"), b) == \
        ["ј", "́", "̆", "́", "ӈ", "l"]
    # The Chukchee's prose is ASCII, so all its non-ASCII is shown, as before.
    assert notable("Kuvár", keying.rules(JESUP / "bogoras-chukchi")) == ["́"]
