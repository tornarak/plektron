"""`edition informants`: the informant ledger's gate holds each parse to its line.

Each test builds the smallest store that can be wrong in one way. The point of
the gate is that `printed` is the record, so most cases are a field that says
something its own line does not.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness import informants

LINE = "Записано отъ чукчанки Кутјэ́ўт на р. Молондѣ въ 1895 г."


def _toc(root: Path) -> None:
    (root / "edition").mkdir(parents=True, exist_ok=True)
    (root / "edition/toc.json").write_text(json.dumps({"entries": [
        {"level": 1, "chapter": "II", "id": "secII", "page_start": 157},
        {"level": 2, "chapter": "II", "number": "52", "id": "n52", "page_start": 163},
        {"level": 2, "chapter": "II", "number": "53", "id": "n53", "page_start": 164},
        {"level": 2, "chapter": "II", "number": "54", "id": "n54", "page_start": 165},
    ]}, ensure_ascii=False), encoding="utf-8")


def _record(**kw) -> dict:
    rec = {"item": "n52", "ref": "1-220", "on_leaf": 1, "folio": 164, "printed": LINE,
           "narrator": "kutjeut", "form": "Кутјэ́ўт",
           "where": {"printed": "на р. Молондѣ", "place": "the Molonda", "entity": None},
           "season": None, "year": 1895}
    rec.update(kw)
    return rec


def _store(root: Path, records=None, narrators=None, unattributed=None) -> None:
    _toc(root)
    doc = {"source": {"read_from": "scans", "resp": {"form": "#llm"}},
           "narrators": narrators if narrators is not None else
           [{"id": "kutjeut", "name": "Кутјэ́ўт", "sex": "f"}],
           "records": records if records is not None else [_record()],
           "unattributed": unattributed or {"items": ["n53", "n54"]}}
    (root / "edition/informants.json").write_text(json.dumps(doc, ensure_ascii=False),
                                                  encoding="utf-8")


def _whats(rep, key="errors") -> list[str]:
    return [e["what"] for e in rep[key]]


def test_a_clean_store_passes_and_is_censused(tmp_path):
    _store(tmp_path)
    rep = informants.check(tmp_path)
    assert rep["errors"] == [] and rep["warnings"] == []
    row, = rep["census"]
    assert (row["id"], row["items"], row["places"], row["years"]) == (
        "kutjeut", 1, "the Molonda", "1895")


def test_a_text_without_a_ledger_has_nothing_to_say(tmp_path):
    rep = informants.check(tmp_path)
    assert rep == {"census": [], "errors": [], "warnings": [], "records": 0, "narrators": 0}


def test_a_form_its_own_line_does_not_print_is_refused(tmp_path):
    # The same narrator is printed several ways; the record keeps its own leaf's.
    _store(tmp_path, records=[_record(form="Кутјәўт")])
    assert any("does not occur in the printed line" in w for w in _whats(informants.check(tmp_path)))


def test_a_place_or_year_the_line_does_not_print_is_refused(tmp_path):
    _store(tmp_path, records=[_record(year=1896,
                                      where={"printed": "на р. Олоѣ", "place": "the Oloi"})])
    whats = _whats(informants.check(tmp_path))
    assert any("year 1896" in w for w in whats)
    assert any("на р. Олоѣ" in w for w in whats)


def test_an_undeclared_narrator_and_a_narrator_nobody_names_both_fail(tmp_path):
    _store(tmp_path, records=[_record(narrator="parkal")])
    whats = _whats(informants.check(tmp_path))
    assert "narrator 'parkal' is not declared" in whats
    assert "no record names this narrator" in whats


def test_identical_lines_at_two_positions_are_two_records(tmp_path):
    # Two items closing on one leaf with the same narrator and place.
    _store(tmp_path, records=[_record(), _record(item="n53", on_leaf=2)],
           unattributed={"items": ["n54"]})
    assert informants.check(tmp_path)["errors"] == []


def test_two_records_at_one_position_are_one_too_many(tmp_path):
    _store(tmp_path, records=[_record(), _record(item="n53")],
           unattributed={"items": ["n54"]})
    assert any("a second record at position 1" in w for w in _whats(informants.check(tmp_path)))


def test_an_item_or_entity_the_text_lacks_is_refused(tmp_path):
    _store(tmp_path, records=[_record(item="n999", where={
        "printed": "на р. Молондѣ", "place": "the Molonda", "entity": "river:molonda"})])
    whats = _whats(informants.check(tmp_path))
    assert "item 'n999' is not a ToC entry" in whats
    assert "entity 'river:molonda' is not in the encyclopedia" in whats


def test_a_record_outside_its_items_span_is_reported_not_fatal(tmp_path):
    # How no. 121's misprinted Contents folio was found.
    _store(tmp_path, records=[_record(folio=170)])
    rep = informants.check(tmp_path)
    assert rep["errors"] == []
    assert any("outside the item's span 163–164" in w for w in _whats(rep, "warnings"))


def test_silence_must_be_declared_and_a_declaration_must_be_true(tmp_path):
    _store(tmp_path, unattributed={"items": ["n52", "n53"]})
    rep = informants.check(tmp_path)
    assert "declared unattributed but has a record" in _whats(rep)
    assert any(w["where"] == "item n54" for w in rep["warnings"])


def test_a_whole_section_can_be_declared_unattributed(tmp_path):
    _store(tmp_path, unattributed={"items": [], "sections": ["II"]})
    assert informants.check(tmp_path)["warnings"] == []


def test_a_rank_the_store_cannot_hold_is_refused(tmp_path):
    _store(tmp_path, narrators=[{"id": "kutjeut", "name": "Кутјэ́ўт",
                                 "jesup": {"form": "Kutyeut", "resp": "#gt"}}])
    assert any("resp '#gt'" in w for w in _whats(informants.check(tmp_path)))
