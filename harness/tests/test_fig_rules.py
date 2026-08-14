"""What the figure track refuses, and what it merely doubts.

The division is `zones.validate_page`'s and carries the same argument. An
**error** is mechanical: it needs no reading of the page, no domain knowledge, and
no configuration could sensibly permit it — a label the store does not declare, a
polygon that is not the rectangle its own bbox claims. A **warning** is a claim
about *this book*, and it is configured, exemptable, and never gates.

`captions-lte-figures` is the whole reason that second category exists here. It is
true of Bogoras and false of printing: 414 pictures against 395 captions over 252
pages, and every caption-heavy page this store ever held turned out to be a
segmentation fault rather than a compositor's choice. A book that sets two
captions under one composite plate turns the rule off and loses nothing.

The JS transcription of this rule is gated in `test_zones_ui.py`, beside the
editor it lives in — two copies of one vocabulary, held together the way
`test_zones_order.py` holds the zone track's.
"""
from __future__ import annotations

from pathlib import Path

from conftest import write_scan

from harness import figures as F
from harness import zones_config as zc

REPO = Path(__file__).resolve().parent.parent.parent
CFG = zc.load_config(REPO)

G, D = F.GRAPHIC, F.FIGDESC


def _page(root: Path, blocks: list[dict], ref: str = "1-191") -> dict:
    write_scan(root, ref, size=(2824, 3897))
    F.save_figs(ref, blocks, root)
    return F.validate_fig_page(ref, root, CFG)


def _box(label, x0, y0, x1, y1, **kw):
    return {"label": label, "x0": x0, "y0": y0, "x1": x1, "y1": y1, **kw}


# --- the count rule ----------------------------------------------------------
#
# `fig_warnings` reads `read_blocks` records, so these carry real geometry: a
# stub with no size trips `tiny-picture`, which is itself the check working.

def _blk(label, n=0):
    """One well-formed block, stacked so no two ever overlap."""
    return {"id": f"fig_1-037_{n:03d}", "label": label,
            "hpos": 400, "vpos": 500 + n * 700, "width": 1600, "height": 600}


def test_a_caption_for_every_picture_is_silent():
    assert zc.fig_warnings(CFG, [_blk(G, 1), _blk(D, 2)]) == []


def test_more_pictures_than_captions_is_silent():
    """Ordinary and common — 19 pictures over this book carry no caption at all."""
    assert zc.fig_warnings(CFG, [_blk(G, 1), _blk(G, 2), _blk(D, 3)]) == []


def test_more_captions_than_pictures_warns():
    out = zc.fig_warnings(CFG, [_blk(G, 1), _blk(D, 2), _blk(D, 3)])
    assert [w["rule"] for w in out] == ["captions-lte-figures"]
    assert "2 captions to 1 picture" in out[0]["detail"]


def test_an_exempted_rule_still_reports_flagged():
    """Suppressing it outright would make an exemption indistinguishable from a
    clean page, and the exemption file is exactly where a wrong call would hide."""
    out = zc.fig_warnings(CFG, [_blk(D, 1)], ["captions-lte-figures"])
    assert len(out) == 1 and out[0]["exempted"] is True


def test_a_rule_the_config_does_not_enable_does_not_fire():
    cfg = {**CFG, "figures": {**CFG["figures"], "rules": []}}
    assert zc.fig_warnings(cfg, [{"label": D}, {"label": D}]) == []


# --- the mechanical errors ---------------------------------------------------

def test_a_clean_page_gates_open(tmp_path):
    out = _page(tmp_path, [_box(G, 400, 900, 2200, 2500),
                           _box(D, 400, 2530, 2200, 2640)])
    assert out["errors"] == [] and out["warnings"] == []
    assert (out["figures"], out["captions"]) == (1, 1)


def test_a_box_off_the_raster_is_an_error(tmp_path):
    out = _page(tmp_path, [_box(G, 400, 900, 3000, 2500)])
    assert "off-raster" in [e["rule"] for e in out["errors"]]


def test_a_tiny_box_warns_rather_than_gating(tmp_path):
    """Nothing forbids a small picture; at this size the likelier explanation is
    dirt the segmenter boxed. `2-085`'s 14×38 px block was the one live instance
    and has since been keyed out, so the corpus now has none — which is the rule
    working rather than the rule going unused: it was a warning, somebody looked,
    and the box turned out to be dirt."""
    out = _page(tmp_path, [_box(G, 400, 900, 414, 938)])
    assert out["errors"] == []
    assert [w["rule"] for w in out["warnings"]] == ["tiny-picture"]


def test_two_overlapping_pictures_warn_rather_than_gating(tmp_path):
    """The rule this store must *not* borrow from the zone track. Zones partition
    the page and form a chain, so an overlap there is unrepresentable and can be
    refused. Figures are freely placed: an inset sits inside the frame it insets
    and two pictures on a plate may abut. `1-189` and `1-334` are the live cases,
    both marginal grazes, and neither is a thing the store must refuse to hold."""
    out = _page(tmp_path, [_box(G, 400, 900, 2200, 2500),
                           _box(G, 500, 1000, 2100, 2400)])
    assert out["errors"] == []
    assert [w["rule"] for w in out["warnings"]] == ["picture-overlap"]


def test_a_caption_overlapping_its_picture_is_not_even_a_warning(tmp_path):
    """An ordinary arrangement in this book — several captions are set within the
    picture's own frame — so overlap is looked for between pictures only."""
    out = _page(tmp_path, [_box(G, 400, 900, 2200, 2500),
                           _box(D, 500, 2300, 2100, 2450)])
    assert out["errors"] == [] and out["warnings"] == []


def test_a_non_rectangular_polygon_is_an_error(tmp_path):
    """The store carries boxes and every reader takes the bbox, so a polygon that
    disagrees with its own bbox is a claim nothing will ever read. This is the
    error the un-migrated eScriptorium store raises on 395 of its 809 blocks."""
    write_scan(tmp_path, "1-191", size=(2824, 3897))
    F.save_figs("1-191", [_box(G, 400, 900, 2200, 2500)], tmp_path)
    p = F.alto_for("1-191", tmp_path)
    p.write_text(p.read_text().replace(
        "400 900 2200 900 2200 2500 400 2500",
        "400 900 2200 890 2200 2500 400 2490"), encoding="utf-8")
    out = F.validate_fig_page("1-191", tmp_path, CFG)
    assert [e["rule"] for e in out["errors"]] == ["not-a-rectangle"]


def test_an_exemption_naming_no_rule_is_an_error(tmp_path):
    """A typo in an exemption id would otherwise excuse nothing, silently, while
    reading as a considered human judgement."""
    write_scan(tmp_path, "1-191", size=(2824, 3897))
    F.save_figs("1-191", [_box(G, 400, 900, 2200, 2500)], tmp_path,
                rules={"captions-lte-figure": "a typo for the real rule id"})
    out = F.validate_fig_page("1-191", tmp_path, CFG)
    assert [e["rule"] for e in out["errors"]] == ["unknown-exemption"]


def test_an_unkeyed_page_is_reported_not_errored(tmp_path):
    """580 of 832 pages have no figure ALTO and that is information, not a fault."""
    write_scan(tmp_path, "1-048", size=(2824, 3897))
    out = F.validate_fig_page("1-048", tmp_path, CFG)
    assert out["keyed"] is False and out["errors"] == [] and out["blocks"] == 0
