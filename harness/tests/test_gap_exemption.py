"""A band the zoning pass ruled not type carries that ruling into `ocr gaps`.

`gt/zones/_ink_exempt.json` is where a human records a band as a smudge, a gutter
blob or offset from the facing page. For most of its life that ruling reached
`zones check --ink` and the zone editor and stopped there: `lines.line_gaps` never
read the file, so a reader on the OCR side got the band bare and re-adjudicated it
from the raster. Three pages of the `1-031`..`1-036` batch were marked during
zoning and re-argued from scratch by readers who never saw the mark — one of them
built an argument for leaving printed text unkeyed on top of it.

That is the firewall's own failure mode running backwards: rank rises by a human
act, and a band returned unmarked invites a lesser witness to re-originate the
call. The two properties under test are therefore *carried* and *not suppressed* —
an exempted band must still report, because a `gaps` that hid one would be the one
place a wrong call could hide, taking the next real dropped line on that page with
it.

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


def _exempt(tmp_path: Path, y0: int, y1: int, note: str = "scanner artifact",
            ref: str = "1-048") -> None:
    d = tmp_path / "gt" / "zones"
    d.mkdir(parents=True, exist_ok=True)
    (d / "_ink_exempt.json").write_text(
        json.dumps({ref: [{"y0": y0, "y1": y1, "note": note}]}),
        encoding="utf-8")


@pytest.fixture
def page(tmp_path):
    return tmp_path, _page(tmp_path)


def test_an_unexempted_band_reports_the_columns_unset(page):
    """The fields are always present, so a caller never has to distinguish
    "not exempted" from "this build does not know about exemptions"."""
    tmp_path, _ = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert band["exempted"] is False
    assert band["note"] == ""


def test_a_ruled_band_carries_the_ruling_and_its_note(page):
    tmp_path, _ = page
    band = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    _exempt(tmp_path, band["vpos"] - 5, band["vpos"] + band["height"] + 5)

    ruled = line_gaps("1-048", "gt/ocr", tmp_path)[0]
    assert ruled["exempted"] is True
    assert ruled["note"] == "scanner artifact"


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
