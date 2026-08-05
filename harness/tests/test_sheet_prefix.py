"""A sheet is named for what is on it, so overlapping calls agree instead of clash.

`ocr zoom` and `ocr sheets` numbered their output `<prefix>-001.png` upward into one
directory per page. `-001` therefore meant "the first sheet of whatever was asked for
last": a second `--only` selection silently replaced the first's images, while the
first call's *returned index* — which names those files and the lines on them — went
on describing pictures that were no longer there. A reader that issued three
selections in parallel got one selection's images and three reports of them, with
nothing to tell it apart.

That is the shape this repo keeps meeting: a claim whose referent was replaced
underneath it, no error raised. It earns a test rather than a comment because the
failure is invisible in either call's own output — only a third party comparing them
can see it, and at run time there is no third party.

Naming by the *selection* would have stopped the clobber and missed the other half:
sheets would still be numbered within a call, so lines 11-12 would land on different
filenames depending on what else was selected alongside them. The property wanted is
two-sided, and both sides are tested here — different content never shares a name,
identical content always does.
"""

import itertools

import pytest

from harness.figures import compose_sheets
from harness.lines import (
    compact_runs,
    parse_selection,
    parse_spans,
    sheet_namer,
)


def names_for(base, chunks, **kw):
    """The names `compose_sheets` would give these chunks, without drawing anything."""
    namer, used, out = sheet_namer(base, **kw), {}, []
    for labels in chunks:
        stem = namer(labels)
        k = used.get(stem, 0)
        used[stem] = k + 1
        out.append(stem if k == 0 else f"{stem}-{chr(ord('b') + k - 1)}")
    return out


def test_compact_runs_is_canonical_over_the_set():
    assert compact_runs([11, 12, 13, 15]) == "11-13_15"
    assert compact_runs([15, 13, 11, 12]) == "11-13_15"
    assert compact_runs([13, 11, 12, 11]) == "11-13"


def test_the_same_lines_get_the_same_name_whatever_else_was_asked_for():
    """The half that sequential numbering could never give.

    A call for 11-16 and a call for 11-16 plus 44 both pack 11 and 12 onto a sheet.
    Under `-001` numbering those were the same filename with the same contents only
    by luck of ordering; here it is by construction.
    """
    a = names_for("zoom2", [["11.0", "11.1", "12.0"], ["12.1", "13.0"]])
    b = names_for("zoom2", [["11.0", "11.1", "12.0"], ["12.1", "13.0"], ["44.0"]])
    assert a == b[:2]
    assert b[2] == "zoom2-44"


def test_different_contents_never_share_a_name():
    chunks = [["11.0", "12.0"], ["13.0"], ["26.0", "27.0", "28.0"],
              ["32.0"], ["42.0", "43.0"], ["44.0"]]
    names = names_for("zoom2", chunks)
    assert len(set(names)) == len(names)
    assert names[0] == "zoom2-11-12" and names[2] == "zoom2-26-28"


def test_a_spec_typed_two_ways_is_one_request():
    assert parse_selection("11,12,13") == parse_selection("11-13")


@pytest.mark.parametrize("base", ["zoom2", "zoom4", "lines"])
def test_pixel_changing_flags_are_in_the_name(base):
    """`--margins` and `--smooth` change what the image shows, not which lines.

    Without them in the name, a margins run and a plain run over the same lines are
    one filename holding two different pictures — the original bug with the lines
    held constant instead of the selection.
    """
    variants = {names_for(base, [["11.0"]], margins=m, smooth=s)[0]
                for m, s in itertools.product((False, True), repeat=2)}
    assert len(variants) == 4


def test_zoom_level_separates_names():
    assert names_for("zoom2", [["11.0"]]) != names_for("zoom4", [["11.0"]])


def test_a_line_split_across_sheets_is_disambiguated_in_order():
    """Deterministic packing, so a positional suffix is stable across identical calls.

    A line's strips can straddle a sheet boundary, which is the one way two sheets in
    a single call can hold the same line set. They must not collide with each other,
    and the same call run twice must produce the same two names.
    """
    chunks = [["12.0", "12.1"], ["12.2", "12.3"]]
    assert names_for("zoom4", chunks) == ["zoom4-12", "zoom4-12-b"]
    assert names_for("zoom4", chunks) == names_for("zoom4", chunks)


def test_a_wide_sheet_degrades_to_a_digest_of_the_same_canonical_form():
    """A full-page contact sheet can hold too many lines to spell out.

    The fallback has to hash the *canonical* rendering, or both properties above stop
    holding at exactly the sizes nobody checks by hand.
    """
    wide = [str(i) for i in range(1, 60, 2)]
    name = names_for("lines", [wide])[0]
    assert name.startswith("lines-n") and len(name) < 24
    assert name == names_for("lines", [list(reversed(wide))])[0]
    assert name != names_for("lines", [wide[:-1]])[0]


def test_spans_parse_and_default_to_the_whole_line():
    assert parse_spans("7,20,22-23") == {7: (0, 100), 20: (0, 100),
                                         22: (0, 100), 23: (0, 100)}
    assert parse_spans("42-43@0-25") == {42: (0, 25), 43: (0, 25)}
    assert parse_spans("12,15@50-85") == {12: (0, 100), 15: (50, 85)}
    assert parse_selection("42-43@0-25") == {42, 43}


@pytest.mark.parametrize("spec", [
    "12@", "12@50-", "12@-50",                   # not a LO-HI pair nor a point
    "12@85-50", "12@50-50", "12@-5-50", "12@0-101",  # not an ordered percentage
    "20-11", "", "12@a-b",
])
def test_a_span_that_is_not_a_span_is_refused(spec):
    """Rejects rather than skips, as the line grammar always has.

    A selection is a claim about what was looked at; a token quietly dropped or
    silently widened is a region reported as examined that was never rendered.
    """
    with pytest.raises(ValueError):
        parse_spans(spec)


def test_a_point_is_a_span_the_renderer_centres():
    """`@P` is the form a reader can actually supply, and it parses to a degenerate
    span the existing widening centres on — the same code path that already fills
    an under-wide range, so a point costs no new geometry.

    A range asks for two numbers about a word whose extent the caller cannot see;
    the second is the one that goes wrong. `1-041`'s reader spent `23@45-65`,
    `23@70-90` and `23@60-75` framing one word that `23@60` renders in one call.
    """
    assert parse_spans("23@60") == {23: (60, 60)}
    assert parse_spans("11@70,13@40") == {11: (70, 70), 13: (40, 40)}
    with pytest.raises(ValueError, match="0 <= P <= 100"):
        parse_spans("23@101")


def test_one_line_given_two_spans_is_an_error_not_a_merge():
    """Unioning them would hand back the whole-line render spans exist to avoid."""
    with pytest.raises(ValueError, match="two different spans"):
        parse_spans("12@0-25,12@50-75")
    parse_spans("12@0-25,12@0-25")  # the same span twice is just the one request


def test_two_spans_of_one_line_are_two_pictures_and_two_names():
    a = names_for("zoom2", [["12.0:0-25"]])[0]
    b = names_for("zoom2", [["12.0:50-75"]])[0]
    whole = names_for("zoom2", [["12.0"]])[0]
    assert len({a, b, whole}) == 3
    assert a == "zoom2-12p0-25"


def bars(spans, width=400, height=20):
    """A synthetic line: black bars at `spans`, white between them."""
    from PIL import Image, ImageDraw
    im = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(im)
    for a, b in spans:
        d.rectangle([a, 0, b, height], fill=0)
    return im


def test_snap_extends_an_edge_that_lands_mid_glyph_out_to_white():
    """The failure that costs a re-call, and the raster already knows the answer.

    A span edge inside a letter clips it; whitespace between words is the one
    boundary the bitonal crop supplies exactly, with no segmentation needed.
    """
    from harness.lines import _snap_to_white
    im = bars([(100, 180), (220, 300)])          # two words, gap at 180..220
    assert _snap_to_white(im, 140, 260, budget=60) == (99, 302)


def test_snap_leaves_an_edge_already_on_white_alone():
    from harness.lines import _snap_to_white
    im = bars([(100, 180), (220, 300)])
    assert _snap_to_white(im, 200, 210, budget=60) == (200, 210)


def test_snap_gives_up_inside_a_long_unbroken_word():
    """Bounded per side: a span with no gap to find must not creep to the measure.

    Staying put is no worse than the behaviour before snapping existed, where
    every edge stayed put.
    """
    from harness.lines import _snap_to_white
    im = bars([(0, 400)])
    assert _snap_to_white(im, 150, 250, budget=20) == (150, 250)


def test_snap_never_returns_an_empty_or_inverted_range():
    from harness.lines import _snap_to_white
    im = bars([(0, 400)])
    lo, hi = _snap_to_white(im, 399, 400, budget=0)
    assert lo < hi


def test_compose_sheets_uses_the_namer(tmp_path):
    """End to end, against the real composer rather than a reimplementation of it."""
    from PIL import Image
    items = [(str(i), Image.new("L", (200, 60), 255)) for i in (11, 12, 30)]
    _, index = compose_sheets(items, tmp_path, per_sheet=2, sheet_w=400,
                              name_for=sheet_namer("zoom2"))
    assert [e["sheet"] for e in index] == ["zoom2-11-12.png", "zoom2-30.png"]


def test_numbering_still_available_for_callers_that_want_it(tmp_path):
    """`figures`' own caption sheets have one writer per directory and no selection."""
    from PIL import Image
    items = [(str(i), Image.new("L", (200, 60), 255)) for i in range(3)]
    _, index = compose_sheets(items, tmp_path, per_sheet=2, sheet_w=400,
                              prefix="sheet")
    assert [e["sheet"] for e in index] == ["sheet-001.png", "sheet-002.png"]


# --- the magnification ceiling ---------------------------------------------

def test_zoom_above_the_ceiling_is_refused_by_the_parser():
    """The rule was prose for months and got broken anyway, so it is a range now.

    At 300 dpi a character stands ~30 px, so by 4x every ink pixel is already a
    4x4 block: past it a magnifier returns the resampler's opinion, not the
    paper's. `2-245` spent ten calls at 6x on a shape question, and the first
    reader dispatched under the queue/claim contract went to 6x nine times and
    settled a laryngeal identity on one of them — a confident answer at a
    magnification carrying no more information than the one below it, which is
    worse than an unresolved one because nothing downstream re-opens it.

    Exit 2, not 1: an out-of-range flag is a usage error, and the parser owns
    argument validation (VERBS.md, Conventions).
    """
    from click.testing import CliRunner

    from harness.cli import build_parser

    r = CliRunner().invoke(build_parser(),
                           ["ocr", "zoom", "1-038", "--only", "16",
                            "--reason", "x", "--zoom", "6"])
    assert r.exit_code == 2
    assert "'6' is not one of" in r.output


@pytest.mark.parametrize("bad", ["1", "3"])
def test_the_middle_rungs_are_gone(bad):
    """Two steps, not a range — the ceiling alone did not hold.

    Measured over one six-page batch: 236 crops taken, **none at the default 2x**.
    Every call overrode it, 226 to 4x and 10 to 3x, and 3x was reached for as a
    compromise between a look and a decision that is neither. 1x is what a contact
    sheet already gives. Two of those six pages were never finished — their readers
    spent 80 turns at two turns a crop and had none left to write with.
    """
    from click.testing import CliRunner

    from harness.cli import build_parser

    r = CliRunner().invoke(build_parser(),
                           ["ocr", "zoom", "1-038", "--only", "16",
                            "--reason", "x", "--zoom", bad])
    assert r.exit_code == 2
    assert f"'{bad}' is not one of" in r.output


def test_a_zoom_needs_a_stated_reason():
    """Required of a model, not of a person: no single crop in the failing batch
    looked wasteful, and the waste was visible only as a count after the page had
    already failed. A reason makes the sequence legible in `agents transcript`."""
    from click.testing import CliRunner

    from harness.cli import build_parser

    r = CliRunner().invoke(build_parser(),
                           ["ocr", "zoom", "1-038", "--only", "16"])
    assert r.exit_code == 2
    assert "--reason" in r.output


def test_capacity_counts_the_padded_strip_and_the_snapped_crop():
    """Both columns were first written from the obvious guess, and both were wrong.

    A point looks like one window by construction — but `_snap_to_white` extends
    each edge out to whitespace so no glyph is cut, and the crop lands on two
    strips. A strip looks like the ALTO box — but `line_crops` adds PAD_TOP and
    PAD_BOTTOM, and using the bare height claimed 13 points per sheet where the
    composer fits 4. Both errors overstate what a call buys, which is the direction
    that costs a re-call: a reader told it can batch thirteen doubts and getting
    four sheets back stops believing the table.

    Measured against a real render of `1-043` (1770 px median measure): 3 strips
    for a whole line at 2x and 7 at 4x, 2 strips for a point at either, 4 points
    to a sheet at 2x and 2 at 4x.
    """
    from harness.lines import PAD_BOTTOM, PAD_TOP, ZOOM_SHEET_H, zoom_capacity

    widths, heights = [1770] * 9, [61] * 9
    at = {c["zoom"]: c for c in zoom_capacity(widths, heights)}
    assert (at[2]["full_strips"], at[4]["full_strips"]) == (3, 7)
    assert (at[2]["point_strips"], at[4]["point_strips"]) == (2, 2)
    assert (at[2]["points_per_sheet"], at[4]["points_per_sheet"]) == (4, 2)
    assert (at[2]["covers_pct"], at[4]["covers_pct"]) == (38, 19)
    # The padding is the whole of the second correction: drop it and 2x claims 13.
    bare = ZOOM_SHEET_H // (61 * 2) // at[2]["point_strips"]
    assert bare > at[2]["points_per_sheet"]
    assert PAD_TOP + PAD_BOTTOM == 28


def test_the_ceiling_itself_is_allowed():
    """4x is the escalation the pass doc sends a reader to for one named doubt;
    refusing it would make the ceiling unreachable rather than enforced."""
    from harness.cli import build_parser
    from harness.lines import ZOOM, ZOOM_MAX, ZOOM_STEPS

    assert ZOOM < ZOOM_MAX == 4
    assert ZOOM_STEPS == (ZOOM, ZOOM_MAX)
    zoom = build_parser().commands["ocr"].commands["zoom"]
    kind = next(p.type for p in zoom.params if "--zoom" in getattr(p, "opts", []))
    assert list(kind.choices) == [2, 4]
