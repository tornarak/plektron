"""`zones.validate_page`: what is an error, what is a warning, and why the line falls there.

The split is the whole design. An **error** is something that cannot be true of a
page keyed in this tool — a width the measure does not allow, two zones on top of
each other, a label nobody declared. A **warning** is a page that does not look like
most pages, which is a description and never a verdict; only errors set the exit
code. Every ordering assumption is a warning by construction, because the book
breaks its own conventions and a tool that refused those pages would be teaching its
operator to key a lie.

The width check and the position check are deliberately separate. The **measure** is
a property of the book and is knowable from the config alone, so the corpus sweep
tests it over every page for nothing. The **position** drifts up to 236 px inside a
single part and can only be had by reading the raster, so it waits for `--ink`. The
cheap half is the one that catches a hand-sized zone, which is what the fixed-measure
design exists to exclude.

Two checks here have already cost this repo something in their other incarnations.
Overlap is tested on **both axes**: a y-only test reports every row of a two-column
page as a collision, which is the mirror of the bug that made `lines` read 14 body
lines of `1-151` as caption. And `uncovered-ink` is the partition check — the
segmenter that dropped whole printed lines from `1-053` and `1-048` will drop whole
zones, and no check that reads only the ALTO can see it, because the file agrees
with itself perfectly.
"""
from __future__ import annotations
from pathlib import Path

import pytest
from lxml import etree

from harness import zones as zn
from harness import zones_config as zc

REPO = Path(__file__).resolve().parent.parent

# The synthetic page's ink runs here, so the anchor has something real to measure.
# Corrected by the config's calibration pads, it yields the column below.
INK0, INK1 = 739, 2489
V0 = INK0 - 17          # ink_pad_left
V1 = V0 + 1778          # part 1's measure
# A page of body lines through the anchor band, so a page is anchorable by default.
BODY = [(y, y + 32) for y in range(600, 3300, 60)]


def cfg_for(_tmp_path: Path = None) -> dict:
    """The shipped config, so these tests bind the numbers actually in use."""
    return zc.load_config(REPO)


def make_scan(tmp_path: Path, ref: str = "1-048",
              size: tuple[int, int] = (2824, 3897), ink=BODY):
    """A page of black bars standing in for lines of type.

    Real ink rather than a blank sheet, because the column is now measured off the
    page: a blank fixture would exercise only the fallback and never the path every
    real page takes.
    """
    from PIL import Image, ImageDraw
    d = tmp_path / "scans"
    d.mkdir(parents=True, exist_ok=True)
    im = Image.new("L", size, 255)
    dr = ImageDraw.Draw(im)
    for y0, y1 in ink:
        dr.rectangle([INK0, y0, INK1, y1], fill=0)
    im.save(d / f"chukchi-{ref}.png")


def zone(label, y0, y1, x0=V0, x1=V1):
    return {"label": label, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def covering():
    """Zones that account for every bar `make_scan` drew."""
    return [zone("RunningTitleZone", 400, 460),
            zone("MainZone-Continued", 560, 1500),
            zone("MainZone-P", 1500, 3340)]


def rules(items):
    return sorted({i["rule"] for i in items})


# ------------------------------------------------------------- the anchor

def test_the_column_is_measured_off_the_page(tmp_path):
    """The finding the design turns on: the measure is configured, the position
    is read from the page. A per-part constant was ~104 px out on 1-048."""
    make_scan(tmp_path)
    m = zn.measure_columns("1-048", tmp_path, cfg_for())
    assert m["measured"] is True and m["source"] == "ink"
    assert m["columns"] == [{"x0": V0, "x1": V1}]


def test_the_same_page_shifted_anchors_to_where_it_moved(tmp_path):
    """Scan registration drifts up to 236 px inside one part; the anchor has to
    follow it rather than average over it."""
    from PIL import Image, ImageDraw
    d = tmp_path / "scans"; d.mkdir(parents=True, exist_ok=True)
    im = Image.new("L", (2824, 3897), 255)
    dr = ImageDraw.Draw(im)
    for y0, y1 in BODY:
        dr.rectangle([INK0 + 200, y0, INK1 + 200, y1], fill=0)
    im.save(d / "chukchi-1-048.png")
    assert zn.measure_columns("1-048", tmp_path, cfg_for())["columns"][0]["x0"] \
        == V0 + 200


def test_a_margin_mark_does_not_move_the_anchor(tmp_path):
    """`1-033`'s left margin carries a long stroke whose densest column holds 774
    inked rows — more than any column of type on that page — and thresholding on
    density took it for the edge of the measure and put the column 52 px out.
    Width is what tells them apart: the mark is a narrow run, the text block a
    wide one."""
    from PIL import Image, ImageDraw
    d = tmp_path / "scans"; d.mkdir(parents=True, exist_ok=True)
    im = Image.new("L", (2824, 3897), 255)
    dr = ImageDraw.Draw(im)
    for y0, y1 in BODY:
        dr.rectangle([INK0, y0, INK1, y1], fill=0)
    # A dense mark, far denser than any text column, well left of the measure.
    dr.rectangle([INK0 - 340, 700, INK0 - 330, 3200], fill=0)
    im.save(d / "chukchi-1-048.png")
    m = zn.measure_frame("1-048", tmp_path, cfg_for())
    assert m["columns"] == [{"x0": V0, "x1": V1}]
    assert m["runs_rejected"] == 1


def test_a_sparse_page_anchors_on_its_span_not_one_run(tmp_path):
    """`1-022` is a chapter opening: nine runs, widest 863 px against a 1778 px
    measure. Demanding a single run as wide as the measure sent it to the
    fallback with the column 245 px out — but its span *is* the measure."""
    from PIL import Image, ImageDraw
    d = tmp_path / "scans"; d.mkdir(parents=True, exist_ok=True)
    im = Image.new("L", (2824, 3897), 255)
    dr = ImageDraw.Draw(im)
    # Three short, widely separated blocks spanning the measure — no one of them
    # is wide enough on its own.
    for x0, x1 in ((INK0, INK0 + 300), (INK0 + 700, INK0 + 1100), (INK1 - 200, INK1)):
        for y0, y1 in BODY[:12]:
            dr.rectangle([x0, y0, x1, y1], fill=0)
    im.save(d / "chukchi-1-048.png")
    m = zn.measure_frame("1-048", tmp_path, cfg_for())
    assert m["measured"] is True and m["source"] == "ink"
    assert m["columns"] == [{"x0": V0, "x1": V1}]


def test_too_little_ink_falls_back_and_says_so(tmp_path):
    """1-330's widest ink run is 80 px against a 1778 px measure. Refusing and
    reporting beats drawing a guide somewhere plausible."""
    make_scan(tmp_path, ink=[(1500, 1540)])
    from PIL import Image, ImageDraw
    im = Image.new("L", (2824, 3897), 255)
    ImageDraw.Draw(im).rectangle([1400, 1500, 1480, 1540], fill=0)
    im.save(tmp_path / "scans" / "chukchi-1-048.png")
    m = zn.measure_columns("1-048", tmp_path, cfg_for())
    assert m["measured"] is False and m["source"] == "fallback"
    assert m["columns"][0]["x0"] == 500


def test_a_blank_page_falls_back_rather_than_raising(tmp_path):
    make_scan(tmp_path, ink=[])
    assert zn.measure_columns("1-048", tmp_path, cfg_for())["measured"] is False


def test_the_content_band_crops_the_blank_margins(tmp_path):
    """What takes an ordinary leaf from three screens to two: the top and bottom
    of a scan are blank paper, and scrolling through them is time on nothing."""
    make_scan(tmp_path)
    c = zn.measure_frame("1-048", tmp_path, cfg_for())["content"]
    pad = cfg_for()["view"]["content_pad_px"]
    assert c["y0"] == BODY[0][0] - pad
    assert c["y1"] == BODY[-1][1] + pad
    assert c["y1"] - c["y0"] < 3897


def test_the_content_band_is_clamped_to_the_leaf(tmp_path):
    """Padding must not produce a band the page cannot contain."""
    make_scan(tmp_path, ink=[(0, 3896)])
    c = zn.measure_frame("1-048", tmp_path, cfg_for())["content"]
    assert c["y0"] == 0 and c["y1"] == 3897


def test_a_speck_in_the_margin_does_not_stretch_the_band(tmp_path):
    """A run of consecutive inked rows is required, so scanner dirt cannot drag
    the crop across half a page of blank paper."""
    from PIL import Image, ImageDraw
    d = tmp_path / "scans"; d.mkdir(parents=True, exist_ok=True)
    im = Image.new("L", (2824, 3897), 255)
    dr = ImageDraw.Draw(im)
    dr.rectangle([1400, 200, 1600, 201], fill=0)      # one-row speck, high up
    for y0, y1 in BODY:
        dr.rectangle([INK0, y0, INK1, y1], fill=0)
    im.save(d / "chukchi-1-048.png")
    c = zn.measure_frame("1-048", tmp_path, cfg_for())["content"]
    assert c["y0"] > 400


def test_a_blank_page_keeps_the_whole_leaf(tmp_path):
    make_scan(tmp_path, ink=[])
    c = zn.measure_frame("1-048", tmp_path, cfg_for())["content"]
    assert (c["y0"], c["y1"]) == (0, 3897)


def test_an_override_replaces_the_measurement_entirely(tmp_path):
    make_scan(tmp_path, "3-005", (2481, 3508))
    cfg = cfg_for()
    cfg["columns"]["overrides"]["3-005"] = {
        "columns": [{"x0": 310, "x1": 1180}, {"x0": 1240, "x1": 2109}]}
    m = zn.measure_columns("3-005", tmp_path, cfg)
    assert m["source"] == "override" and len(m["columns"]) == 2


# ------------------------------------------------------------- clean pages

def test_a_well_formed_page_is_clean(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for())
    assert r["errors"] == [] and r["warnings"] == []
    assert r["zones"] == 3 and r["split"] == "train"


def test_a_page_never_keyed_reports_nothing_and_says_so(tmp_path):
    make_scan(tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for())
    assert r["keyed"] is False and r["zones"] == 0
    assert r["errors"] == [] and r["warnings"] == []


def test_an_exempt_empty_page_is_keyed_and_clean(tmp_path):
    """A plate has no text column; zero zones is its correct segmentation, and the
    `exempt` mark is what makes that a statement rather than an absence."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [], tmp_path, split="exempt")
    r = zn.validate_page("1-048", tmp_path, cfg_for())
    assert r["keyed"] is True and r["errors"] == [] and r["warnings"] == []


def test_an_empty_text_page_cannot_be_saved(tmp_path):
    """It would count as keyed everywhere while recording nothing — the one defect
    that makes a page look *finished*."""
    make_scan(tmp_path)
    with pytest.raises(ValueError, match="no zones"):
        zn.save_zones("1-048", [], tmp_path)
    assert zn.has_zones("1-048", tmp_path) is False


def test_clearing_a_kept_page_is_refused_too(tmp_path):
    """Saving zero over a page that had zones is the same erasure, arrived at from
    the other side — and it would take the previous state with it."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    with pytest.raises(ValueError, match="no zones"):
        zn.save_zones("1-048", [], tmp_path)
    assert len(zn.read_zones("1-048", tmp_path)) == 3


def test_marking_it_exempt_is_how_an_empty_page_is_saved(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", [], tmp_path, split="exempt")
    assert zn.load_splits(tmp_path) == {"1-048": "exempt"}


def test_an_empty_page_already_in_the_store_is_an_error(tmp_path):
    """The refusal only guards new writes; a page can predate it or arrive by
    hand, and that page is invisible to every other check."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [], tmp_path, split="exempt")
    zn.set_split("1-048", "train", tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)
    assert "empty-page" in rules(r["errors"])


# ------------------------------------------------------------------- errors

def test_wrong_width_is_caught_without_reading_the_raster(tmp_path):
    """The cheap half: the measure is knowable from the config, so the corpus
    sweep tests it over every page for nothing."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 600, 900, x0=100, x1=1200)], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)
    assert rules(r["errors"]) == ["column-width"]


def test_right_width_in_the_wrong_place_needs_the_raster(tmp_path):
    """A correctly-sized zone 300 px off the column passes the cheap check and is
    caught by the measured one — which is exactly the division of labour."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 600, 900, x0=V0+300, x1=V1+300)],
                  tmp_path)
    assert zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)["errors"] == []
    assert "column-position" in rules(
        zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)["errors"])


def test_width_within_tolerance_is_accepted(tmp_path):
    make_scan(tmp_path)
    cfg = cfg_for()
    off = cfg["width_tolerance_px"] - 1
    zn.save_zones("1-048", [zone("MainZone-P", 600, 900, x0=V0, x1=V1 + off)],
                  tmp_path)
    assert zn.validate_page("1-048", tmp_path, cfg, ink=False)["errors"] == []


def test_too_short_a_zone_is_an_error(tmp_path):
    """A stray double-click makes a few-pixel band; nothing else does."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 600, 605)], tmp_path)
    assert "min-height" in rules(
        zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)["errors"])


def test_overlapping_zones_are_an_error(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 600, 900),
                            zone("MainZone-Continued", 850, 1400)], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)
    assert rules(r["errors"]) == ["overlap"]
    assert "50 px" in r["errors"][0]["detail"]


def test_shared_boundaries_are_not_an_overlap(tmp_path):
    """Chain mode makes the next zone's top exactly the last one's bottom, which
    is what a vertical partition looks like and must never report."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 600, 900),
                            zone("MainZone-Continued", 900, 1400)], tmp_path)
    assert zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)["errors"] == []


def test_side_by_side_columns_do_not_overlap(tmp_path):
    """The both-axes test. A y-only one would report every row of a two-column
    page as a collision."""
    make_scan(tmp_path, "3-005", (2481, 3508))
    cfg = cfg_for()
    cfg["columns"]["overrides"]["3-005"] = {
        "columns": [{"x0": 310, "x1": 1180}, {"x0": 1240, "x1": 2109}]}
    zn.save_zones("3-005", [zone("MainZone-P", 600, 3000, x0=310, x1=1180),
                            zone("MainZone-P", 600, 3000, x0=1240, x1=2109)],
                  tmp_path)
    assert zn.validate_page("3-005", tmp_path, cfg, ink=False)["errors"] == []


def test_an_override_column_is_not_measured_against_the_part_measure(tmp_path):
    """A two-column page's columns are ~870 px against a 1778 px measure, so the
    width check has to defer to the override rather than condemn it."""
    make_scan(tmp_path, "3-005", (2481, 3508))
    cfg = cfg_for()
    cfg["columns"]["overrides"]["3-005"] = {
        "columns": [{"x0": 310, "x1": 1180}, {"x0": 1240, "x1": 2109}]}
    zn.save_zones("3-005", [zone("MainZone-P", 600, 3000, x0=310, x1=1180)], tmp_path)
    assert "column-width" not in rules(
        zn.validate_page("3-005", tmp_path, cfg, ink=False)["errors"])


def test_undeclared_label_is_an_error_not_a_warning(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-Invented", 600, 900)], tmp_path)
    assert "unknown-label" in rules(
        zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)["errors"])


def test_zone_running_off_the_page_is_an_error(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 3000, 4200)], tmp_path)
    assert "off-page" in rules(
        zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)["errors"])


def test_a_non_rectangular_polygon_is_an_error(tmp_path):
    """Guards what this tool does not write: a hand edit, or an eScriptorium
    round trip where a zone can be dragged into any shape at all."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 600, 900)], tmp_path)
    p = zn.alto_for("1-048", tmp_path)
    tree = etree.parse(str(p))
    tree.find(".//{*}Polygon").set("POINTS", f"{V0} 600 {V1} 620 {V1} 900 {V0} 880")
    tree.write(str(p), xml_declaration=True, encoding="UTF-8")
    assert "not-a-rectangle" in rules(
        zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)["errors"])


# ----------------------------------------------------------------- warnings

def test_an_exempt_page_is_not_judged_by_text_page_rules(tmp_path):
    """A plate has no running title and no body. Every layout warning describes
    how a *text* page is arranged, so on this one they are permanent known-false
    noise — which is exactly what buries real signal."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MarginTextZone-Notes", 600, 900),
                            zone("RunningTitleZone", 1000, 1090)],
                  tmp_path, split="exempt")
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    assert r["split"] == "exempt"
    assert r["warnings"] == [] and r["uncovered"] == []


def test_an_exempt_page_still_reports_mechanical_errors(tmp_path):
    """Otherwise the mark would hide a mistake rather than describe a plate."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-P", 600, 900, x0=100, x1=1200)],
                  tmp_path, split="exempt")
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)
    assert rules(r["errors"]) == ["column-width"]


def test_order_violation_is_a_warning_never_an_error(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("RunningTitleZone", 400, 460),
                            zone("MarginTextZone-Notes", 560, 900),
                            zone("MainZone-P", 1000, 3340)], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)
    assert r["errors"] == []
    assert "rank-monotone" in rules(r["warnings"])


def test_exempted_warning_is_flagged_not_hidden(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("RunningTitleZone", 400, 460),
                            zone("MarginTextZone-Notes", 560, 900),
                            zone("MainZone-P", 1000, 3340)], tmp_path,
                  exempt=["rank-monotone"])
    got = [w for w in zn.validate_page("1-048", tmp_path, cfg_for(),
                                       ink=False)["warnings"]
           if w["rule"] == "rank-monotone"]
    assert len(got) == 1 and got[0]["exempted"] is True


def test_stale_exemption_is_reported(tmp_path):
    """The page was fixed; the exemption outliving it would hide the next one."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path, exempt=["rank-monotone"])
    assert "stale-exemption" in rules(
        zn.validate_page("1-048", tmp_path, cfg_for())["warnings"])


def test_unimplemented_rule_id_in_config_is_reported(tmp_path):
    """order_warnings ignores a rule it does not implement so one typo cannot
    disable the rest; this is where the typo becomes visible again."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    cfg = cfg_for()
    cfg["order_rules"] = cfg["order_rules"] + [{"id": "titl-first", "severity": "warn"}]
    r = zn.validate_page("1-048", tmp_path, cfg)
    assert "unknown-rule" in rules(r["warnings"]) and r["errors"] == []


# -------------------------------------------------------------- uncovered ink

def test_ink_no_zone_covers_is_warned(tmp_path):
    """The partition check, and the only one that consults the page. A dropped
    zone is invisible to everything that reads only the file."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-Continued", 560, 1500)], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    assert "uncovered-ink" in rules(r["warnings"]) and r["uncovered"]


def test_ink_a_zone_covers_is_silent(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    assert "uncovered-ink" not in rules(r["warnings"])


def test_lines_of_one_missing_region_merge_into_one_finding(tmp_path):
    """An under-segmented 1-048 reported 38 bands, one per line of body text, for
    a single missing region. That is a count, not a finding, and 38 lines of
    correct output is how a real signal gets buried."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-Continued", 560, 1500)], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    assert len(r["uncovered"]) == 1
    assert r["uncovered"][0]["bands"] > 5
    assert "rows of ink" in r["warnings"][0]["detail"]


def test_a_lone_band_between_covered_zones_stays_its_own_finding(tmp_path):
    """The case that must never be merged away: `3-005`'s centred `AFFINITY.` is
    23 px of ink, the smallest confirmed dropped line in the corpus."""
    make_scan(tmp_path, ink=[(600, 632), (1500, 1532), (2600, 2624), (3200, 3232)])
    zn.save_zones("1-048", [zone("MainZone-P", 560, 1400),
                            zone("MainZone-Continued", 1700, 2500),
                            zone("MainZone-Other", 3100, 3300)], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    assert len(r["uncovered"]) == 2
    assert all(b["bands"] == 1 for b in r["uncovered"])


def test_a_band_can_be_ruled_not_type_with_a_reason(tmp_path):
    """This scan set is full of smudges, gutter blobs and offset from the facing
    page. All are real, none are printing, and there has to be somewhere to say
    so that is not "turn the check off"."""
    make_scan(tmp_path, ink=BODY + [(3500, 3560)])
    zn.save_zones("1-048", [zone("MainZone-P", 560, 3340)], tmp_path)
    b = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)["uncovered"][0]
    zn.set_ink_exempt("1-048", [{"y0": b["vpos"], "y1": b["vpos"] + b["height"],
                                 "note": "scanner smudge"}], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    w = [x for x in r["warnings"] if x["rule"] == "uncovered-ink"][0]
    assert w["exempted"] is True and "scanner smudge" in w["detail"]
    # Listed, never hidden — as with an exempted order rule.
    assert len(r["uncovered"]) == 1 and r["uncovered"][0]["note"] == "scanner smudge"


def test_a_ruling_without_a_reason_is_refused(tmp_path):
    """The reason is the record. Without it the entry is indistinguishable from a
    hidden mistake, and this is the only check that can see a dropped zone."""
    with pytest.raises(ValueError, match="no reason"):
        zn.set_ink_exempt("1-048", [{"y0": 10, "y1": 20, "note": "   "}], tmp_path)


def test_a_ruling_covers_its_own_band_and_not_the_page(tmp_path):
    """Exempting a whole page's ink check would hide the next dropped zone on it."""
    make_scan(tmp_path, ink=BODY + [(3480, 3520), (3600, 3640)])
    zn.save_zones("1-048", [zone("MainZone-P", 560, 3340)], tmp_path)
    zn.set_ink_exempt("1-048", [{"y0": 3470, "y1": 3530, "note": "gutter blob"}],
                      tmp_path)
    got = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)["uncovered"]
    assert [b["exempted"] for b in got] == [True, False]


def test_a_ruling_that_matches_nothing_is_reported(tmp_path):
    """The page was re-keyed or the band moved; the note now describes nothing."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    zn.set_ink_exempt("1-048", [{"y0": 10, "y1": 20, "note": "gone"}], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    assert "stale-ink-exemption" in rules(r["warnings"])


def test_rulings_round_trip_and_clear(tmp_path):
    zn.set_ink_exempt("1-048", [{"y0": 30, "y1": 10, "note": "offset"}], tmp_path)
    got = zn.load_ink_exempt(tmp_path)["1-048"][0]
    assert (got["y0"], got["y1"]) == (10, 30)      # normalized
    zn.set_ink_exempt("1-048", [], tmp_path)
    assert zn.load_ink_exempt(tmp_path) == {}


def test_ink_check_can_be_skipped(tmp_path):
    """0.27 s a page against ~1 ms for the file-level checks, so the sweep opts out."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-Continued", 560, 1500)], tmp_path)
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=False)
    assert r["ink_checked"] is False and r["uncovered"] == []


# ------------------------------------------------------------------ corpus

def test_corpus_rows_have_one_fixed_key_set(tmp_path):
    """TOON degrades to the verbose nested form the moment the keys go ragged."""
    for ref in ("1-048", "1-151"):
        make_scan(tmp_path, ref)
        zn.save_zones(ref, covering(), tmp_path)
    summary, rows = zn.validate_corpus(tmp_path, cfg_for())
    assert len(rows) == 2
    assert len({frozenset(r) for r in rows}) == 1
    assert all(isinstance(v, (str, int)) for r in rows for v in r.values())
    assert summary["pages"] == 2 and summary["train"] == 2 and summary["errors"] == 0


def test_corpus_reports_a_ref_in_both_lists(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    (zn.zone_dir(tmp_path) / zn.EVAL_LST).write_text("chukchi-1-048.xml\n")
    summary, _ = zn.validate_corpus(tmp_path, cfg_for())
    assert summary["in_both_lists"] == "chukchi-1-048.xml"


# --------------------------------------------------------- the ink verdict
#
# `record_ink` reduces the full finding to the four states the page list draws,
# and caches it — the check is the only one that opens a raster, so it is written
# down by whoever ran it rather than run again by whoever wants to look. The
# distinction that has to survive the reduction is ruled-not-type against clean:
# a page whose bands are all excused must still say so, or `_ink_exempt.json`
# becomes the one place a wrong call is invisible.

def verdict(tmp_path):
    r = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)
    return zn.record_ink("1-048", r, tmp_path)


def test_a_page_with_unaccounted_ink_reads_as_ink(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-Continued", 560, 1500)], tmp_path)
    r = verdict(tmp_path)
    assert r["state"] == "ink" and r["bands"] >= 1 and "y=" in r["note"]


def test_a_covered_page_reads_as_clean(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    r = verdict(tmp_path)
    assert r["state"] == "clean" and r["bands"] == 0


def test_a_ruled_band_reads_as_ruled_and_keeps_its_reason(tmp_path):
    """Not `clean`. The row has to stay distinguishable from a page where nothing
    was ever found, since that difference is the whole record."""
    make_scan(tmp_path, ink=BODY + [(3500, 3560)])
    zn.save_zones("1-048", [zone("MainZone-P", 560, 3340)], tmp_path)
    b = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)["uncovered"][0]
    zn.set_ink_exempt("1-048", [{"y0": b["vpos"], "y1": b["vpos"] + b["height"],
                                 "note": "gutter blob"}], tmp_path)
    r = verdict(tmp_path)
    assert r["state"] == "ruled" and r["ruled"] == 1 and r["bands"] == 0
    assert "gutter blob" in r["note"]


def test_an_unkeyed_page_is_skipped_rather_than_called_clean(tmp_path):
    make_scan(tmp_path)
    assert verdict(tmp_path)["state"] == "skip"


def test_a_page_ruled_not_a_text_page_is_skipped(tmp_path):
    """`exempt` says a human ruled this a plate. Uncovered ink on a plate is the
    plate."""
    make_scan(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-Other", 560, 1500)], tmp_path)
    zn.set_split("1-048", "exempt", tmp_path)
    assert verdict(tmp_path)["state"] == "skip"


def test_an_exemption_matching_nothing_is_reported_as_stale(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    zn.set_ink_exempt("1-048", [{"y0": 3500, "y1": 3560, "note": "smudge"}],
                      tmp_path)
    r = verdict(tmp_path)
    assert r["stale"] == 1 and r["state"] == "clean"


# ------------------------------------------------------------- the cache

def test_a_recorded_verdict_is_read_back(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    verdict(tmp_path)
    assert zn.cached_ink("1-048", tmp_path)["state"] == "clean"


def test_a_page_never_checked_has_no_verdict(tmp_path):
    """None, and the list draws that as `?`. A page nothing has read is not a
    clean page."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    assert zn.cached_ink("1-048", tmp_path) is None


def test_rekeying_the_page_discards_the_verdict(tmp_path):
    """The whole hazard the cache introduces: a verdict about the page as it was,
    rendered in the same column as a live one, is fluent nonsense."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    verdict(tmp_path)
    zn.save_zones("1-048", [zone("MainZone-Continued", 560, 1500)], tmp_path,
                  stamp="later")
    assert zn.cached_ink("1-048", tmp_path) is None


def test_ruling_a_band_discards_the_verdict_too(tmp_path):
    """`_ink_exempt.json` is written without touching the ALTO, so its mtime has
    to be part of what the verdict is stamped against."""
    make_scan(tmp_path, ink=BODY + [(3500, 3560)])
    zn.save_zones("1-048", [zone("MainZone-P", 560, 3340)], tmp_path)
    verdict(tmp_path)
    b = zn.validate_page("1-048", tmp_path, cfg_for(), ink=True)["uncovered"][0]
    zn.set_ink_exempt("1-048", [{"y0": b["vpos"], "y1": b["vpos"] + b["height"],
                                 "note": "smudge"}], tmp_path)
    assert zn.cached_ink("1-048", tmp_path) is None


def test_the_ink_sweep_fills_the_cache(tmp_path):
    """122 rasters read and nothing kept would make the list ask for the same
    work over again."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    zn.validate_corpus(tmp_path, cfg_for(), ink=True)
    assert zn.cached_ink("1-048", tmp_path)["state"] == "clean"


def test_a_sweep_without_the_raster_records_nothing(tmp_path):
    """It did not look at the page, so it has nothing to say about its ink."""
    make_scan(tmp_path)
    zn.save_zones("1-048", covering(), tmp_path)
    zn.validate_corpus(tmp_path, cfg_for(), ink=False)
    assert zn.cached_ink("1-048", tmp_path) is None
