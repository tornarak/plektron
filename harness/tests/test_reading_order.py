"""Reading order, and the identity that must not move with it.

`index` is assigned by the segmenter and is the join key for `proposal.json`,
`decision.json` and `restore`. Output order is a *presentation* concern. Measured
over the 20 restored pages, 18 change order under a reading-order sort (524
positions; `1-101` moves all 59), so conflating the two would silently mis-map
every adjudicated page — the ground-truth-loss failure shape.

The banding tests are the load-bearing ones. A plain `sort(key=(vpos, hpos))`
looks obviously right and is wrong precisely on two-column tables, which are the
layouts this exists for.
"""
from pathlib import Path

from harness.lines import _overlap_fraction, reading_order


def rec(index, hpos, vpos, width=100, height=44, text=""):
    return {"index": index, "hpos": hpos, "vpos": vpos, "width": width,
            "height": height, "text": text, "line_id": f"l{index}"}


def test_index_is_preserved_not_reassigned():
    """The whole safety property in one assertion."""
    recs = [rec(0, 100, 900), rec(1, 100, 100), rec(2, 100, 500)]
    out = reading_order(recs)
    assert [r["index"] for r in out] == [1, 2, 0]
    assert [r["y_rank"] for r in out] == [0, 1, 2]


def test_two_column_row_with_baseline_wobble():
    """`3-005`'s AFFINITY table, reduced.

    A strict `(vpos, hpos)` sort emits the right column first whenever the row's
    two lines differ by a few px — which they do on 4 of that page's 6 rows, e.g.
    `Mother-in-law.` at vpos 2378 ahead of `Ñaw-mataˊlɪn` at 2382. Banding must
    put the headword first.
    """
    recs = [
        rec(0, 526, 2334, text="Mataˊlɪn"),        # row 1 left
        rec(1, 1419, 2334, text="Father-in-law."),  # row 1 right, exact tie
        rec(2, 1419, 2378, text="Mother-in-law."),  # row 2 right, 4px HIGHER
        rec(3, 570, 2382, text="Ñaw-mataˊlɪn"),     # row 2 left
        rec(4, 1419, 2420, text="Son-in-law."),     # row 3 right, 2px higher
        rec(5, 528, 2422, text="ɪntuˊulpᴇrⁱ"),      # row 3 left
    ]
    out = [r["text"] for r in reading_order(recs)]
    assert out == ["Mataˊlɪn", "Father-in-law.",
                   "Ñaw-mataˊlɪn", "Mother-in-law.",
                   "ɪntuˊulpᴇrⁱ", "Son-in-law."]


def test_consecutive_rows_are_not_merged():
    """The tolerance must separate real rows. Row pitch ~44 against a half-median
    tolerance of ~22, so two rows may never band together."""
    recs = [rec(0, 1400, 100, text="r1-right"), rec(1, 400, 100, text="r1-left"),
            rec(2, 1400, 144, text="r2-right"), rec(3, 400, 144, text="r2-left")]
    out = [r["text"] for r in reading_order(recs)]
    assert out == ["r1-left", "r1-right", "r2-left", "r2-right"]


def test_skew_does_not_accumulate_across_a_band():
    """Each line is compared against the *band's first* vpos, never the previous
    line's — and this test can tell the two apart.

    Six lines in an 8 px staircase, against a tolerance of 22 (half the 44 px
    median height). No single step exceeds the tolerance, so comparing against the
    *previous* line would chain all six into one band; comparing against the
    band's first correctly breaks after c2 (124 - 100 = 24 > 22).

    `hpos` descends, so the two readings give different output: two bands sort
    within themselves (c2 c1 c0 | c5 c4 c3), one band sorts globally
    (c5 c4 c3 c2 c1 c0).
    """
    recs = [rec(i, 600 - i * 100, 100 + i * 8, text=f"c{i}") for i in range(6)]
    out = [r["text"] for r in reading_order(recs)]
    assert out == ["c2", "c1", "c0", "c5", "c4", "c3"], (
        "expected two bands; a single band would have sorted all six by hpos")


def test_records_without_geometry_sort_last_in_index_order():
    """They cannot be placed, and inventing a position would be worse."""
    recs = [rec(0, 100, 500), {"index": 1, "hpos": None, "vpos": None,
                               "width": None, "height": None, "text": "", "line_id": "l1"},
            rec(2, 100, 100)]
    out = reading_order(recs)
    assert [r["index"] for r in out] == [2, 0, 1]


def test_empty_input():
    assert reading_order([]) == []


# --- figure overlap ---------------------------------------------------------

def zone(zid, label, hpos, vpos, width, height):
    return {"id": zid, "label": label, "hpos": hpos, "vpos": vpos,
            "width": width, "height": height}


def test_overlap_is_two_dimensional(monkeypatch):
    """A Y-only test called `1-151`'s whole left text column "inside" the figure
    sitting beside it in the right margin — 14 body lines misread as caption."""
    body = rec(0, 388, 2200, width=1160, height=54)      # left column
    fig = zone("z", "GraphicZone", 1550, 2167, 570, 680)  # right margin
    assert _overlap_fraction(body, fig) == 0.0


def test_caption_line_marked_and_heading_in_graphic_is_not(monkeypatch):
    """The `3-006` counterexample: a heading wholly inside a caption-less
    GraphicZone is flagged, never treated as a caption."""
    import harness.lines as L
    zs = [zone("fd", "GraphicZone-FigDesc", 1556, 2859, 610, 96),
          zone("gz", "GraphicZone", 376, 2146, 1701, 1008)]
    monkeypatch.setattr("harness.figures.zones", lambda ref, root=Path("."): zs)
    recs = [rec(0, 1576, 2865, width=578, height=52, text="Fig. 30, a ..."),
            rec(1, 500, 2400, width=300, height=40, text="CONSANGUINITY."),
            rec(2, 380, 800, width=1700, height=44, text="ordinary body text")]
    L.mark_figure_overlap(recs, "3-006", Path("."))
    assert recs[0]["in_figdesc"] == "fd"
    assert recs[1]["in_figdesc"] is None and recs[1]["in_graphic"] == "gz"
    assert recs[2]["in_figdesc"] is None and recs[2]["in_graphic"] is None


def test_every_record_carries_every_key(monkeypatch):
    """A ragged key set silently degrades the TOON table to its verbose nested
    form, so absent must still be present."""
    import harness.lines as L
    monkeypatch.setattr("harness.figures.zones", lambda ref, root=Path("."): [])
    recs = [rec(0, 100, 100), rec(1, 100, 200)]
    L.mark_figure_overlap(recs, "1-048", Path("."))
    for r in recs:
        assert {"in_figdesc", "in_graphic", "figdesc_straddle"} <= set(r)


def test_straddle_is_a_partial_overlap(monkeypatch):
    """One TextLine spanning a wrapped caption and the body below it."""
    import harness.lines as L
    zs = [zone("fd", "GraphicZone-FigDesc", 300, 1000, 1400, 60)]
    monkeypatch.setattr("harness.figures.zones", lambda ref, root=Path("."): zs)
    straddler = rec(0, 300, 1030, width=1400, height=60)   # half in, half below
    L.mark_figure_overlap([straddler], "1-001", Path("."))
    assert straddler["in_figdesc"] is None
    assert straddler["figdesc_straddle"] == "fd"


def test_a_detector_flag_names_the_alto_index_not_a_draft_position():
    """The flag's number has to be the one every other file is keyed by.

    `catmus_draft` is a filtered view — apparatus zones and figdesc lines are
    dropped — so its positions do not join `ocr_lines`, and on `1-151` the draft's
    37 entries sit against 39 with position 6 naming ALTO index 4. A pass reading
    a flag and reaching for `ocr zoom --only` therefore got a different line of the
    same page, with nothing raised. `line` was replaced rather than supplemented:
    a second number whose only correct use is "none" is a worse bug than one.
    """
    from harness.detectors import detect_all

    lines = ["plain english here", "keliˊlɪn", "more english"]
    flags = detect_all(lines, Path("."), indices=["0", "9", "4"])["tokens"]
    hit = [f for f in flags if f["token"] == "keliˊlɪn"]
    assert hit, "the notated token is flagged"
    assert hit[0]["index"] == "9", "the index it was given, not its position (2)"
    assert "line" not in hit[0], "the position is gone, not carried alongside"


def test_a_flag_index_is_null_rather_than_misaligned():
    """Wrong-length indices misalign every flag, so they are refused wholesale.

    Null is a legible "not available"; an off-by-one index is a citation to the
    wrong line that reads exactly like a citation to the right one.
    """
    from harness.detectors import detect_all

    for indices in (None, ["0"]):
        flags = detect_all(["keliˊlɪn", "x", "y"], Path("."), indices=indices)["tokens"]
        assert flags and all(f["index"] is None for f in flags)
