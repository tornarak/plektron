"""`harness scans sheet`: whole leaves on a contact sheet, labelled with their ruling."""
from __future__ import annotations

from pathlib import Path

from conftest import write_project, write_scan
from PIL import Image

from harness import provenance, scans


def _text(tmp_path: Path) -> Path:
    root = write_project(tmp_path)
    for ref in ("1-001", "1-002"):
        write_scan(root, ref, size=(600, 860))
    (root / "gt" / "zones").mkdir(parents=True)
    (root / "gt" / "zones" / "_cover.lst").write_text("chukchi-1-001.xml\n",
                                                      encoding="utf-8")
    return root


def test_a_sheet_counts_its_rulings_and_says_what_made_it(tmp_path):
    root = _text(tmp_path)
    rows = scans.leaf_sheets(["1-001", "1-002", "1-003"], root)
    assert len(rows) == 1
    row = rows[0]
    assert Path(row["sheet"]).name == "leaves-1-001_1-003.png"
    assert (row["leaves"], row["ruled"]) == (3, 1)
    (p,) = provenance.read_producers(row["sheet"])
    assert p.step == "harness scans sheet"
    assert (p.inputs["first"], p.inputs["last"], p.inputs["n"]) == ("1-001", "1-003", "3")


def test_a_missing_raster_holds_its_tile(tmp_path):
    """`1-003` has no raster. Dropping it would put every later leaf under the
    wrong label's neighbour, so its tile is drawn and says so: the sheet is one
    row of three tiles, not two."""
    root = _text(tmp_path)
    (row,) = scans.leaf_sheets(["1-001", "1-002", "1-003"], root)
    with Image.open(row["sheet"]) as im:
        w = im.width
    assert w == scans.SHEET_COLS * (scans.TILE_W + scans.TILE_GAP) + scans.TILE_GAP


def test_sheets_split_at_the_tile_count_and_are_named_for_their_span(tmp_path):
    root = _text(tmp_path)
    per = scans.SHEET_COLS * scans.SHEET_ROWS
    refs = [f"1-{i:03d}" for i in range(1, per + 3)]
    rows = scans.leaf_sheets(refs, root)
    assert [(r["first"], r["last"], r["leaves"]) for r in rows] == [
        ("1-001", refs[per - 1], per), (refs[per], refs[-1], 2)]
