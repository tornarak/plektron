"""A page's lines are the store's plus `gt/lines/`'s, and `page_lines` decides it.

A correction nobody downstream can point at is not a correction, it is a note. So
the merge happens in the one function every consumer already goes through — the
reader's sheets and crops, the review server, `proposal check`, `ocr gaps`, `tei
context` — rather than in each of them, which is the failure this module's own §1
records for reading order.

Two invariants make the overlay safe rather than merely convenient.

**`index` is identity and is never reassigned.** A correction takes a number after
the ALTO's last, so every `proposal.json` and `decision.json` already keyed
against the page still names the line it always named. `reading_order` then puts
the correction in its true place on the page without touching any identity — which
is exactly the split between `index` and `y_rank` that already exists.

**The ref must be passed where the path cannot supply it.** `restore` compares
`page_lines(src)` with `page_lines(tmp)` to verify its own write, and `tmp` is
`chukchi-PP-NNN.xml.tmp`, whose stem parses as no ref. Left to the derivation, one
side folds and the other does not, and restore reports "the write lost or gained
lines" on every corrected page.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from harness import corrections as corr
from harness.lines import page_lines

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
ZONE_LABEL = "RunningTitleZone"


def _ocr_alto(root: Path, ref: str, n: int, page_w: int, page_h: int) -> Path:
    lines = "".join(
        f'<TextLine ID="l{i}" HPOS="100" VPOS="{1000 + i * 100}" WIDTH="800" '
        f'HEIGHT="60"><String CONTENT="line {i}" HPOS="100" '
        f'VPOS="{1000 + i * 100}" WIDTH="800" HEIGHT="60"/></TextLine>'
        for i in range(n))
    p = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><alto xmlns="{ALTO_NS}"><Layout>'
        f'<Page WIDTH="{page_w}" HEIGHT="{page_h}"><PrintSpace HPOS="0" VPOS="0" '
        f'WIDTH="{page_w}" HEIGHT="{page_h}"><TextBlock ID="b1">{lines}'
        "</TextBlock></PrintSpace></Page></Layout></alto>", encoding="utf-8")
    return p


def _zones(root: Path, ref: str, y0: int, y1: int) -> None:
    d = root / "gt" / "zones"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"chukchi-{ref}.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><alto xmlns="{ALTO_NS}"><Layout>'
        f'<Page WIDTH="1200" HEIGHT="1600"><PrintSpace HPOS="0" VPOS="0" '
        f'WIDTH="1200" HEIGHT="1600">'
        f'<TextBlock ID="z1" TAGREFS="BT1" HPOS="80" VPOS="{y0}" WIDTH="1040" '
        f'HEIGHT="{y1 - y0}"/></PrintSpace></Page></Layout>'
        f'<Tags><OtherTag ID="BT1" TYPE="type" LABEL="{ZONE_LABEL}"/></Tags>'
        "</alto>", encoding="utf-8")


@pytest.fixture
def page(tmp_path: Path):
    """Four ALTO lines, a 1200x1600 raster, and one correction near the top."""
    (tmp_path / "scans").mkdir()
    Image.new("RGB", (1200, 1600), "white").save(
        tmp_path / "scans" / "chukchi-1-048.png")
    (tmp_path / "config").mkdir()
    shutil.copy(Path("config") / "zones_config.json", tmp_path / "config")
    alto = _ocr_alto(tmp_path, "1-048", 4, 1200, 1600)
    return tmp_path, alto


@pytest.fixture
def corrected(page):
    tmp_path, alto = page
    # Above every ALTO line on the page, so reading order must place it first
    # while its index lands last.
    corr.save_lines("1-048", [{"x0": 900, "y0": 300, "x1": 990, "y1": 340}],
                    tmp_path)
    return tmp_path, alto


def test_without_a_fragment_nothing_changes(page):
    tmp_path, alto = page
    recs = page_lines(alto, tmp_path)
    assert len(recs) == 4
    assert {r["src"] for r in recs} == {"alto"}


def test_src_is_on_every_record_even_with_no_corrections(page):
    """A fixed key set. A caller must never have to tell "this came from the
    ALTO" from "this build does not know about corrections"."""
    tmp_path, alto = page
    assert all("src" in r for r in page_lines(alto, tmp_path))


def test_a_correction_takes_an_index_after_the_altos_last(corrected):
    tmp_path, alto = corrected
    recs = page_lines(alto, tmp_path)
    assert len(recs) == 5
    added = [r for r in recs if r["src"] == "corr"]
    assert len(added) == 1
    assert added[0]["index"] == 4
    assert added[0]["line_id"] == "corr_1-048-300"


def test_no_existing_identity_moves(corrected):
    """The whole reason the overlay is safe: every decision keyed against this
    page before the correction existed still names the line it named."""
    tmp_path, alto = corrected
    before = {r["line_id"]: r["index"]
              for r in page_lines(alto, tmp_path) if r["src"] == "alto"}
    assert before == {"l0": 0, "l1": 1, "l2": 2, "l3": 3}


def test_reading_order_places_it_while_the_index_does_not(corrected):
    """`index` is identity, `y_rank` is position — and a correction is the
    sharpest case, since it is appended last and usually belongs first."""
    tmp_path, alto = corrected
    recs = page_lines(alto, tmp_path)
    added = next(r for r in recs if r["src"] == "corr")
    assert added["y_rank"] == 0, "a line above every other did not read first"
    assert added["index"] == 4
    assert recs[0]["line_id"] == "corr_1-048-300"


def test_the_zone_comes_from_containment(corrected):
    """The fragment stores no label — stored, it would go stale the moment the
    page was re-zoned. This is what hands a recovered folio the
    `RunningTitleZone` that makes it a folio to `tei context`."""
    tmp_path, alto = corrected
    _zones(tmp_path, "1-048", 280, 360)
    added = next(r for r in page_lines(alto, tmp_path) if r["src"] == "corr")
    assert added["zone"] == ZONE_LABEL


def test_a_correction_stranded_by_rezoning_resolves_to_no_zone(corrected):
    """How a stranded correction announces itself: the zones moved out from under
    it and it now belongs to no region, which `ocr gaps` reports."""
    tmp_path, alto = corrected
    _zones(tmp_path, "1-048", 1200, 1400)
    added = next(r for r in page_lines(alto, tmp_path) if r["src"] == "corr")
    assert added["zone"] == ""


def test_geometry_is_scaled_into_the_altos_space(page):
    """The fragment is raster-space and the ALTO need not be. Taken per axis and
    derived, never assumed: a silently mis-scaled box reads as a segmentation
    error rather than a units one."""
    tmp_path, _ = page
    half = _ocr_alto(tmp_path, "1-048", 4, 600, 800)   # raster is 1200x1600
    corr.save_lines("1-048", [{"x0": 900, "y0": 300, "x1": 990, "y1": 340}],
                    tmp_path)
    added = next(r for r in page_lines(half, tmp_path) if r["src"] == "corr")
    assert (added["hpos"], added["vpos"]) == (450, 150)
    assert (added["width"], added["height"]) == (45, 20)


def test_an_underivable_path_folds_nothing_but_still_stamps_src(corrected):
    """`restore` writes to `chukchi-PP-NNN.xml.tmp`, whose stem parses as no ref.
    Degrade quietly — but keep the key set fixed."""
    tmp_path, alto = corrected
    tmp_copy = alto.with_suffix(".xml.tmp")
    tmp_copy.write_bytes(alto.read_bytes())

    recs = page_lines(tmp_copy, tmp_path)
    assert len(recs) == 4, "a path that names no ref folded corrections anyway"
    assert {r["src"] for r in recs} == {"alto"}


def test_an_explicit_ref_folds_where_the_path_cannot(corrected):
    """**The failure the parameter exists to prevent.** Without it, restore's two
    `page_lines` calls disagree by exactly the corrections, and its own length
    guard reports the write as having lost lines."""
    tmp_path, alto = corrected
    tmp_copy = alto.with_suffix(".xml.tmp")
    tmp_copy.write_bytes(alto.read_bytes())

    a = page_lines(alto, tmp_path, ref="1-048")
    b = page_lines(tmp_copy, tmp_path, ref="1-048")
    assert len(a) == len(b) == 5
    assert [r["line_id"] for r in a] == [r["line_id"] for r in b]
    assert [r["index"] for r in a] == [r["index"] for r in b]
