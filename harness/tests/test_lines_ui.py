"""`ocr edit` — what it refuses, and what one save leaves behind.

The editor's own subject is small: draw a box, or rule a band not type. What is
worth testing is the boundary it enforces, because that boundary is the thing the
two-layer split rests on.

**A box in no zone is refused.** Ink that no region covers is a defect in the
*zoning*: the segmentation missed a region. Adopting it here would record a line
inside no region while leaving the region missing — the fault papered over one
line at a time, in the tool least able to see the whole page. So it stops, and it
names `zones edit`, because that is where the fault actually is.

The client checks the same rule before saving. That is for the human's benefit and
is not the guard: the server refuses regardless, which is what these tests hold.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from harness import corrections as corr
from harness import zones as zn
from harness.lines_ui import page_state, render_html, save_payload

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
IN_ZONE = {"x0": 300, "y0": 620, "x1": 420, "y1": 660}
OUT_OF_ZONE = {"x0": 300, "y0": 1400, "x1": 420, "y1": 1440}


def _zones(root: Path, ref: str = "1-048") -> None:
    d = root / "gt" / "zones"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"chukchi-{ref}.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><alto xmlns="{ALTO_NS}"><Layout>'
        '<Page WIDTH="1200" HEIGHT="1600"><PrintSpace HPOS="0" VPOS="0" '
        'WIDTH="1200" HEIGHT="1600">'
        '<TextBlock ID="z1" TAGREFS="BT1" HPOS="80" VPOS="600" WIDTH="1040" '
        'HEIGHT="120"/></PrintSpace></Page></Layout>'
        '<Tags><OtherTag ID="BT1" TYPE="type" LABEL="RunningTitleZone"/></Tags>'
        "</alto>", encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "scans").mkdir()
    Image.new("RGB", (1200, 1600), "white").save(
        tmp_path / "scans" / "chukchi-1-048.png")
    (tmp_path / "data").mkdir()
    shutil.copy(Path("data") / "zones_config.json", tmp_path / "data")
    alto = tmp_path / "gt" / "ocr" / "chukchi-1-048.xml"
    alto.parent.mkdir(parents=True)
    alto.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><alto xmlns="{ALTO_NS}"><Layout>'
        '<Page WIDTH="1200" HEIGHT="1600"><PrintSpace HPOS="0" VPOS="0" '
        'WIDTH="1200" HEIGHT="1600"><TextBlock ID="b1">'
        '<TextLine ID="l0" HPOS="100" VPOS="900" WIDTH="800" HEIGHT="60">'
        '<String CONTENT="x" HPOS="100" VPOS="900" WIDTH="800" HEIGHT="60"/>'
        "</TextLine></TextBlock></PrintSpace></Page></Layout></alto>",
        encoding="utf-8")
    return tmp_path


def _save(root, lines=(), ink=()):
    # `gt/ocr` rather than the view: the fixture has no symlink farm, and the
    # store the editor was opened against is the one it must re-measure through.
    return save_payload({"ref": "1-048", "lines": list(lines),
                         "ink_exempt": list(ink)}, root, "gt/ocr")


def test_a_page_with_no_zoning_is_refused_outright(root):
    """Line correction comes after zoning: this editor finds lines dropped
    *inside* declared regions, and with no regions there is nothing to be
    inside. A stage-order invariant, not a claim about this corpus."""
    with pytest.raises(ValueError) as e:
        _save(root, [IN_ZONE])
    assert "zones edit" in str(e.value)
    assert not corr.lines_path("1-048", root).exists()


def test_a_box_in_no_zone_is_refused_and_names_the_zone_editor(root):
    """The stink. Not a mistake to swallow — a finding about the zoning."""
    _zones(root)
    with pytest.raises(ValueError) as e:
        _save(root, [OUT_OF_ZONE])
    msg = str(e.value)
    assert "no zone" in msg
    assert "zones edit" in msg
    assert "missed a region" in msg


def test_nothing_is_written_when_one_box_is_refused(root):
    """Both stores or neither. A save that landed the good boxes and dropped the
    refused one would leave the page in a state no single view describes."""
    _zones(root)
    with pytest.raises(ValueError):
        _save(root, [IN_ZONE, OUT_OF_ZONE])
    assert corr.load_lines("1-048", root) == []


def test_a_box_inside_a_zone_saves(root):
    _zones(root)
    res = _save(root, [IN_ZONE])
    assert res["lines"] == 1
    assert [c["y0"] for c in corr.load_lines("1-048", root)] == [620]


def test_a_ruling_needs_a_reason(root):
    """Enforced by the store for both layers — the note is the whole record."""
    _zones(root)
    with pytest.raises(ValueError, match="no reason"):
        _save(root, [IN_ZONE], [{"y0": 1000, "y1": 1040, "note": "  "}])


def test_a_ruling_lands_in_the_line_layer_only(root):
    """This editor writes its own file. The zone layer is shown, never written —
    a claim about what the zoning need not cover is not this tool's to make."""
    _zones(root)
    _save(root, [IN_ZONE], [{"y0": 1000, "y1": 1040, "note": "printed rule"}])
    assert corr.load_ink_exempt(root).get("1-048")
    assert zn.load_ink_exempt(root) == {}


def test_the_save_reports_what_is_left_not_what_was_sent(root):
    """Re-measured after the write, so the page's tally is the store's answer
    rather than the client's belief about it."""
    _zones(root)
    res = _save(root, [IN_ZONE])
    assert "live_bands" in res and isinstance(res["bands"], int)


def test_the_state_carries_both_ruling_layers(root):
    """The editor shows the zone layer so a human can see that the neighbouring
    check has already spoken about that strip of paper."""
    _zones(root)
    zn.set_ink_exempt("1-048", [{"y0": 1500, "y1": 1540, "note": "smudge"}], root)
    _save(root, [IN_ZONE], [{"y0": 1000, "y1": 1040, "note": "printed rule"}])

    st = page_state("1-048", root, "gt/ocr")
    assert [e["note"] for e in st["zone_exempt"]] == ["smudge"]
    assert [e["note"] for e in st["line_exempt"]] == ["printed rule"]


def test_a_correction_reaches_the_state_as_its_own_layer(root):
    _zones(root)
    _save(root, [IN_ZONE])
    st = page_state("1-048", root, "gt/ocr")
    assert len(st["corr"]) == 1
    assert st["corr"][0]["y0"] == 620
    assert [line["y0"] for line in st["lines"]] == [900]


def test_the_page_says_when_it_has_no_zoning(root):
    html = render_html("1-048", root, "gt/ocr")
    assert "no zoning" in html
    assert "zones edit" in html
