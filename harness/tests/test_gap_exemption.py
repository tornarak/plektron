"""A band a human ruled carries that ruling into `ocr gaps` — from *its own layer*.

Two ink checks run over these pages and they ask different questions. `zones check
--ink` asks whether ink is inside any zone; ink outside every region is a defect in
the zoning. `ocr gaps` asks whether in-zone ink is inside any line; ink a zone
covers but no `TextLine` does is a dropped line. Each has an exemption file, and
each band is settled only by the layer whose question it belongs to.

**Both halves of that have been wrong, in opposite directions, and both are under
test here.**

For most of its life `lines.line_gaps` read no exemption file at all, so a reader
on the OCR side got a ruled band bare and re-adjudicated it from the raster. Three
pages of the `1-031`..`1-036` batch were marked during zoning and re-argued from
scratch by readers who never saw the mark — one built an argument for leaving
printed text unkeyed on top of it. That is the firewall's failure mode running
backwards: rank rises by a human act, and an unmarked band invites a lesser witness
to re-originate the call.

The fix over-corrected into one file serving both checks, so a band ruled "scanner
smudge" while zoning — a claim about what the *zoning* need not cover — also
stopped the line check from ever reporting that strip of paper again. A folio the
segmenter dropped inside a `RunningTitleZone` is exactly the case that must survive
a zone-level ruling elsewhere on the page.

So three properties: *carried*, *not suppressed*, and *not borrowed from the other
layer*. Not suppressed matters most — a `gaps` that hid a band would be the one
place a wrong call could hide, taking the next real dropped line with it.

Fixtures are synthetic and live in `tmp_path`, per the suite's rule; the geometry
is the `test_adopt_gap_gate` page, whose single uncovered band is contrived to be
found by the detector.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_adopt_gap_gate import _page

from harness.lines import adopt_gaps, line_gaps

ZONE_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _exempt(tmp_path: Path, y0: int, y1: int, note: str = "scanner artifact",
            ref: str = "1-048", layer: str = "zones") -> None:
    """A ruling in one layer's file. `layer` is the whole point of the argument."""
    d = tmp_path / "gt" / ("lines" if layer == "lines" else "zones")
    d.mkdir(parents=True, exist_ok=True)
    (d / "_ink_exempt.json").write_text(
        json.dumps({ref: [{"y0": y0, "y1": y1, "note": note}]}),
        encoding="utf-8")


def _zoned(tmp_path: Path, y0: int, y1: int, label: str = "RunningTitleZone",
           ref: str = "1-048") -> None:
    """Put the fixture's band inside a declared zone.

    Without this the page has no zoning at all and every band reads out-of-zone,
    which is a legitimate state — and the reason these tests have to be explicit
    about which side of the boundary each band sits on. A file that only ever
    tested the unzoned page would silently stop covering the line layer.
    """
    d = tmp_path / "gt" / "zones"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"chukchi-{ref}.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<alto xmlns="{ZONE_NS}"><Layout>'
        f'<Page WIDTH="600" HEIGHT="800"><PrintSpace HPOS="0" VPOS="0" '
        f'WIDTH="600" HEIGHT="800">'
        f'<TextBlock ID="b1" TAGREFS="BT1" HPOS="40" VPOS="{y0}" WIDTH="520" '
        f'HEIGHT="{y1 - y0}"><Shape><Polygon POINTS="40 {y0} 560 {y0} 560 {y1} '
        f'40 {y1}"/></Shape></TextBlock>'
        f'</PrintSpace></Page></Layout>'
        f'<Tags><OtherTag ID="BT1" TYPE="type" LABEL="{label}" '
        f'DESCRIPTION="block type {label}"/></Tags></alto>',
        encoding="utf-8")


@pytest.fixture
def page(tmp_path):
    return tmp_path, _page(tmp_path)


@pytest.fixture
def in_zone(tmp_path):
    """The same page, with its uncovered band inside a declared zone."""
    alto = _page(tmp_path)
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    _zoned(tmp_path, band["vpos"] - 20, band["vpos"] + band["height"] + 20)
    return tmp_path, alto, band


def test_an_unexempted_band_reports_the_columns_unset(page):
    """The fields are always present, so a caller never has to distinguish
    "not exempted" from "this build does not know about exemptions"."""
    tmp_path, _ = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert band["exempted"] is False
    assert band["note"] == ""
    assert band["layer"] == ""


def test_an_unzoned_band_is_the_zone_layers_to_settle(page):
    """No zoning, so nothing says this ink belongs inside a region — which is the
    zoning's question, and its ruling answers it."""
    tmp_path, _ = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert band["zone"] == ""
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5)

    ruled = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert ruled["exempted"] is True
    assert ruled["note"] == "scanner artifact"
    assert ruled["layer"] == "zones"


def test_an_exempted_band_still_reports(page):
    """Flagged, never suppressed. A `gaps` that dropped the band would hide a
    wrong ruling forever, and the next dropped line on the page with it."""
    tmp_path, _ = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5)

    after = line_gaps("1-048", "gt/ocr", tmp_path)
    assert len(after) == 1
    assert after[0]["vpos"] == band["vpos"]


def test_a_region_matching_nothing_leaves_the_band_alone(page):
    """Matching is on the band's midpoint, the same rule `zones check --ink`
    uses — an exemption recorded elsewhere on the page must not bleed onto it."""
    tmp_path, _ = page
    _exempt(tmp_path, 0, 40)
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert band["exempted"] is False
    assert band["note"] == ""


# --- the two layers, and the boundary between them -------------------------

def test_a_band_inside_a_zone_names_it(in_zone):
    """Containment is what decides whose question the band is, so it is reported
    rather than left implicit — and it is what hands a recovered folio the
    `RunningTitleZone` that makes it a folio downstream."""
    tmp_path, _alto, _band = in_zone
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert band["zone"] == "RunningTitleZone"


def test_a_zone_ruling_does_not_settle_a_band_inside_a_zone(in_zone):
    """**The fix this split exists for.** One file served both checks, so a band
    ruled "scanner smudge" during zoning — a claim about what the zoning need not
    cover — also stopped the line check from reporting that strip forever. A
    dropped folio inside a `RunningTitleZone` is exactly what that hid.
    """
    tmp_path, _alto, band = in_zone
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5,
            layer="zones")

    after = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert after["zone"] == "RunningTitleZone"
    assert after["exempted"] is False, "a zone-level ruling settled a line-level band"
    assert after["layer"] == ""


def test_a_line_ruling_settles_a_band_inside_a_zone(in_zone):
    """The line layer's own file does settle it — a printed rule or a footnote
    separator the zoning covers is not a dropped line, and that is this layer's
    call to make."""
    tmp_path, _alto, band = in_zone
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5,
            note="printed rule", layer="lines")

    after = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert after["exempted"] is True
    assert after["note"] == "printed rule"
    assert after["layer"] == "lines"


def test_a_line_ruling_does_not_settle_a_band_outside_every_zone(page):
    """The mirror, and it keeps the boundary honest in both directions: ink no
    region covers is the zoning's defect, and the line editor must not be able to
    rule it away from over here."""
    tmp_path, _ = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5,
            layer="lines")

    after = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert after["zone"] == ""
    assert after["exempted"] is False
    assert after["layer"] == ""


def test_adopting_a_ruled_band_is_refused_before_any_write(page):
    """Adopting is the OCR side overturning the zoning side's call. Refused
    rather than warned: the exemption is the ratified witness, and the way to
    disagree with it is to drop it in the editor, which is a human act."""
    tmp_path, alto = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5)
    before = alto.read_bytes()

    with pytest.raises(ValueError, match="ruled not type"):
        adopt_gaps("1-048", [band["vpos"]], "gt/ocr", tmp_path, commit=True)
    assert alto.read_bytes() == before, "a refused adoption rewrote the store"


def test_the_refusal_names_the_note_and_the_way_out(page):
    """An error a reader cannot act on sends them looking for a workaround."""
    tmp_path, _ = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5,
            note="offset from the facing page")

    with pytest.raises(ValueError) as exc:
        adopt_gaps("1-048", [band["vpos"]], "gt/ocr", tmp_path, commit=True)
    msg = str(exc.value)
    assert "offset from the facing page" in msg
    assert "_ink_exempt.json" in msg and "zones edit" in msg
