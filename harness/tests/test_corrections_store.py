"""`gt/lines/` — a human's geometry over ink the segmenter left unboxed.

The store exists because `ocr adopt-gap` could not do this job at the scale the
census found. That verb wrote into `gt/ocr/` explicitly, so it was unrunnable on
the ~690 pages that have only machine output — and a dropped folio matters most
exactly there, since the folio is what `tei context` turns into the page's `<pb
n>` witness and nothing infers a page number.

Two properties carry the weight here.

**The `String` is empty by construction.** The editor draws boxes and never keys,
so nothing in this writer can originate a reading; text arrives later from
`restore`, out of an adjudicated decision. That was `adopt_gaps`' legitimacy
argument too, and it is inherited intact.

**Text already stored is carried by id, not by the caller.** A human who nudges a
box after `restore` has written its text must not lose the text — but the editor
must not be handed the reading to round-trip through a browser either. So the
store carries it forward itself.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from lxml import etree

from harness import corrections as corr


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A page with a raster, which is all `save_lines` needs to measure."""
    from PIL import Image
    (tmp_path / "scans").mkdir()
    Image.new("RGB", (600, 800), "white").save(
        tmp_path / "scans" / "chukchi-1-048.png")
    (tmp_path / "data").mkdir()
    shutil.copy(Path("data") / "zones_config.json", tmp_path / "data")
    return tmp_path


BOX = {"x0": 50, "y0": 400, "x1": 550, "y1": 430}


def test_no_file_means_no_human_has_drawn_here(root):
    """Absence is the record, as it is in `gt/zones/`. There is no "looked and
    found nothing" to express: a zoning partitions the page and can be legitimately
    empty, a correction store cannot."""
    assert corr.load_lines("1-048", root) == []
    assert not corr.lines_path("1-048", root).exists()


def test_a_saved_box_round_trips_in_raster_coordinates(root):
    corr.save_lines("1-048", [BOX], root)
    got = corr.load_lines("1-048", root)
    assert len(got) == 1
    assert (got[0]["x0"], got[0]["y0"], got[0]["x1"], got[0]["y1"]) == (
        50, 400, 550, 430)
    assert (got[0]["page_w"], got[0]["page_h"]) == (600, 800)


def test_the_page_is_the_rasters_own_size(root):
    """Raster coordinates, measured here rather than taken from the client: the
    fold scales into whichever ALTO answers for the page, and it needs the space
    these numbers are in to be a fact rather than a claim."""
    corr.save_lines("1-048", [BOX], root)
    page = etree.parse(str(corr.lines_path("1-048", root))).find(".//{*}Page")
    assert (page.get("WIDTH"), page.get("HEIGHT")) == ("600", "800")


def test_the_string_is_empty_by_construction(root):
    """The whole legitimacy of a second writer over these stores. The editor
    draws; it never keys."""
    corr.save_lines("1-048", [dict(BOX)], root)
    strings = list(etree.parse(str(corr.lines_path("1-048", root)))
                   .iter("{*}String"))
    assert len(strings) == 1
    assert strings[0].get("CONTENT") == ""


def test_the_id_carries_its_provenance_and_where_it_was_found(root):
    corr.save_lines("1-048", [BOX], root)
    assert corr.load_lines("1-048", root)[0]["id"] == "corr_1-048-400"


def test_a_line_has_exactly_one_string(root):
    """`restore` refuses a TextLine with any other count, and it will be joining
    on these — a fragment it cannot write into is worse than no fragment."""
    corr.save_lines("1-048", [BOX], root)
    for tl in etree.parse(str(corr.lines_path("1-048", root))).iter("{*}TextLine"):
        assert len(tl.findall("{*}String")) == 1


def test_stored_text_survives_a_geometry_edit(root):
    """A human nudging a box after `restore` wrote its text must not lose it —
    and must not have to hand the reading back through the browser to keep it."""
    corr.save_lines("1-048", [BOX], root)
    p = corr.lines_path("1-048", root)
    tree = etree.parse(str(p))
    next(tree.iter("{*}String")).set("CONTENT", "17")
    tree.write(str(p), xml_declaration=True, encoding="UTF-8")

    moved = dict(BOX, id="corr_1-048-400", y0=402, y1=432)
    corr.save_lines("1-048", [moved], root)

    got = corr.load_lines("1-048", root)
    assert got[0]["text"] == "17", "an adjudicated reading was dropped by a nudge"
    assert got[0]["y0"] == 402
    assert got[0]["id"] == "corr_1-048-400", "the id moved with the box"


def test_a_new_box_never_inherits_a_neighbours_text(root):
    """Carrying forward is by id and only by id. Position is not identity: two
    boxes can trade places, and a text that followed geometry would follow them."""
    corr.save_lines("1-048", [BOX], root)
    p = corr.lines_path("1-048", root)
    tree = etree.parse(str(p))
    next(tree.iter("{*}String")).set("CONTENT", "17")
    tree.write(str(p), xml_declaration=True, encoding="UTF-8")

    corr.save_lines("1-048", [{"x0": 50, "y0": 600, "x1": 550, "y1": 630}], root)
    got = corr.load_lines("1-048", root)
    assert len(got) == 1
    assert got[0]["text"] == ""


def test_an_empty_save_removes_the_file(root):
    """The opposite of `save_zones`' rule, for the same underlying reason. There,
    an empty page and an unvisited page are byte-identical, so an empty save
    erases the difference between judging and not. Here the file's existence *is*
    the record, so a file holding nothing would claim a human drew something when
    they withdrew everything."""
    corr.save_lines("1-048", [BOX], root)
    res = corr.save_lines("1-048", [], root)
    assert res["removed"] is True
    assert not corr.lines_path("1-048", root).exists()
    assert corr.load_lines("1-048", root) == []


def test_a_withdrawal_is_recoverable_for_one_save(root):
    """`.prev` beside the file, as everywhere else in the authored stores — the
    deletion is the one act with nothing else to fall back on."""
    corr.save_lines("1-048", [BOX], root)
    corr.save_lines("1-048", [], root)
    prev = corr.lines_path("1-048", root).with_suffix(".xml.prev")
    assert prev.exists()
    assert b"corr_1-048-400" in prev.read_bytes()


def test_saving_over_nothing_is_not_a_removal(root):
    """Reported honestly rather than as a no-op that looks like a deletion."""
    assert corr.save_lines("1-048", [], root)["removed"] is False


def test_the_writer_names_no_store(root):
    """`save_zones`' property: there is no argument in which to name somewhere
    else, so no caller can put a human's geometry into a machine store by passing
    the wrong string."""
    import inspect
    params = set(inspect.signature(corr.save_lines).parameters)
    assert params == {"ref", "boxes", "root"}
