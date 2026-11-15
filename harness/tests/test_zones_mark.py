"""`harness zones mark`: many rulings at once, each the editor's own act."""
from __future__ import annotations

from conftest import write_project, write_scan

from harness import zones


def _text(tmp_path):
    root = write_project(tmp_path)
    for ref in ("1-001", "1-002", "1-003"):
        write_scan(root, ref)
    return root


def test_a_preview_writes_nothing_and_says_what_would_move(tmp_path):
    root = _text(tmp_path)
    zones.set_split("1-001", "train", root)
    rows = zones.mark(["1-001", "1-002"], "blank", root)
    assert [(r["ref"], r["was"], r["now"]) for r in rows] == [
        ("1-001", "train", "blank"), ("1-002", "", "blank")]
    assert zones.load_splits(root) == {"1-001": "train"}


def test_a_leaf_kind_is_a_ruling_and_a_text_split_is_not(tmp_path):
    root = _text(tmp_path)
    zones.mark(["1-001"], "cover", root, commit=True)
    zones.mark(["1-002", "1-003"], "eval", root, commit=True)
    s = zones.load_splits(root)
    assert s == {"1-001": "cover", "1-002": "eval", "1-003": "eval"}
    assert zones.settled_refs(root) == ["1-001"]


def test_ruling_a_keyed_page_drops_its_zones_and_keeps_prev(tmp_path):
    root = _text(tmp_path)
    p = zones.alto_for("1-001", root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("<alto/>", encoding="utf-8")
    zones.mark(["1-001"], "plate", root, commit=True)
    assert not p.exists()
    assert p.with_suffix(".xml.prev").exists()
    assert zones.load_splits(root)["1-001"] == "plate"
