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
from harness.lines_ui import page_state, save_payload


def client(root, walk=None, cur="1-048"):
    """The editor over a `TestClient`, with a session as a verb would set one.

    The rendered assertions below used to call `render_html` and grep the string
    it returned. They go through the app now because that is where the markup is
    assembled — the template, the state blob and the mount prefix are three
    separate things and only the response has all three.
    """
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    session = {"start": cur, "alto_dir": "gt/ocr",
               "itinerary": walk or [cur], "itinerary_name": "unsettled"}
    app = create_app(root, Sessions(root=root, by_editor={"lines": session}),
                     editor="lines")
    return TestClient(app)

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
    shutil.copy(Path("data") / "lines_config.json", tmp_path / "data")
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


def _save(root, lines=(), ink=(), **extra):
    # `gt/ocr` rather than the view: the fixture has no symlink farm, and the
    # store the editor was opened against is the one it must re-measure through.
    return save_payload({"ref": "1-048", "lines": list(lines),
                         "ink_exempt": list(ink), **extra}, root, "gt/ocr")


def _save_bare(root, payload):
    """A payload with only the keys named, so a test can leave one out. The
    difference between an absent key and an empty one is the whole subject of
    two tests below, and `_save`'s defaults would erase it."""
    return save_payload({"ref": "1-048", **payload}, root, "gt/ocr")


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


def test_a_correction_carries_its_own_geometry_whatever_the_store_order(root):
    """The overlay joins fragments to boxes **by id**, not by position.

    It was `zip(corrected, sorted(stored, key=(y0, x0)), strict=False)` — two
    independently-derived orderings — so any divergence stapled one correction's
    id, geometry and text onto another's box, and a length mismatch truncated in
    silence. The box's `text` is the only thing that confirms the right line was
    clicked, so a crossed join corrupts exactly the field the overlay exists for.

    Order is varied at the source rather than guessed at: reading order and
    `(y0, x0)` happen to agree for most fixtures, which is why a positional join
    survived. Reversing what the store hands back is the cheapest way to make
    them disagree, and the result must not move.
    """
    _zones(root)
    _save(root, [{"x0": 300, "y0": 620, "x1": 420, "y1": 660},
                 {"x0": 500, "y0": 640, "x1": 620, "y1": 680}])

    forward = page_state("1-048", root, "gt/ocr")["corr"]
    assert len(forward) == 2

    real = corr.load_lines
    try:
        corr.load_lines = lambda ref, r: list(reversed(real(ref, r)))
        reversed_ = page_state("1-048", root, "gt/ocr")["corr"]
    finally:
        corr.load_lines = real

    by_id = {c["id"]: (c["y0"], c["x0"], c["text"]) for c in forward}
    assert by_id == {c["id"]: (c["y0"], c["x0"], c["text"]) for c in reversed_}, \
        "a fragment's geometry followed its position rather than its id"


def test_the_overlay_box_does_not_leak_its_join_key(root):
    """`line_id` is carried only to join on and is popped; the client's box
    shape is what it was."""
    _zones(root)
    _save(root, [IN_ZONE])
    st = page_state("1-048", root, "gt/ocr")
    assert all("line_id" not in b for b in st["corr"] + st["lines"])


def test_the_page_says_when_it_has_no_zoning(root):
    html = client(root).get("/lines/?ref=1-048").text
    assert "no zoning" in html
    assert "zones edit" in html


def test_every_bound_action_has_a_row_and_a_handler(root):
    """The help panel is generated from the bindings so it cannot lie about the
    tool — but now the rows are in a template and the dispatch is in a static
    file, so the check has to read both. That is the cost of the split, and it is
    worth paying: a keystroke listed in the panel and bound to nothing is exactly
    the kind of quiet wrongness a help panel should not be able to have.
    """
    import re
    from pathlib import Path as P

    from harness.lines_ui import ACTION_NAMES

    html = client(root).get("/lines/?ref=1-048").text
    js = P("harness/web/static/js/lines.js").read_text(encoding="utf-8")
    # The dispatch table is an object literal, so an action is a bare key rather
    # than a quoted string — `rule_band: () => …`.
    dispatched = set(re.findall(r"^\s{2}(\w+):", js, re.M))
    for name in ACTION_NAMES:
        assert f'data-act="{name}"' in html, f"{name} has no row in the panel"
        assert name in dispatched, f"{name} is listed but nothing dispatches it"


def test_the_script_and_styles_are_linked_not_inlined(root):
    """The whole point of the port for this editor: it is navigated page-to-page
    with the arrow keys, and 19 KB of JS plus three stylesheets were re-sent on
    every one of those."""
    html = client(root).get("/lines/?ref=1-048").text
    assert '<script src="/static/js/lines.js"></script>' in html
    assert "/static/css/editor.css" in html
    assert "<style>" not in html


def test_the_mount_prefix_reaches_the_client(root):
    """`lines.js` is one cached file served from one place, so it cannot hold the
    prefix itself — a bare '/save' would post to whichever editor owned the root.
    The server puts it in the state blob."""
    html = client(root).get("/lines/?ref=1-048").text
    assert '"base": "/lines"' in html or '"base":"/lines"' in html


def test_the_generated_layer_css_carries_a_validator(root):
    """It is derived from `data/lines_config.json`, so it cannot be a static
    file — but it is still an asset, and it gets an ETag keyed on the config's
    own contents so an edit invalidates it and nothing else does."""
    c = client(root)
    r = c.get("/lines/layers.css")
    assert r.status_code == 200 and "ly-zone" in r.text
    etag = r.headers["etag"]
    assert c.get("/lines/layers.css",
                 headers={"If-None-Match": etag}).status_code == 304


# --- the walk is measured, never saved -------------------------------------

def test_a_rows_counts_are_measured_not_remembered(root):
    """The list's slow column, and the reason there is no `.lst` anywhere near
    this editor: a work-list freezes at the moment it is written, and every page
    worked afterwards makes it wrong with nothing to check it. This is asked when
    it is needed, so the answer is true when it is used."""
    from harness.lines_ui import page_row
    _zones(root)
    before = page_row("1-048", root, "gt/ocr")
    assert before["corrections"] == 0

    _save(root, [IN_ZONE])
    after = page_row("1-048", root, "gt/ocr")
    assert after["corrections"] == 1
    assert after["live"] <= before["live"], "a correction did not settle its band"


def test_the_list_draws_unknown_rather_than_blank(root):
    """`?` until a row is fetched. Blank would be indistinguishable from none,
    which is the same silence this whole detector exists to break."""
    html = client(root, walk=["1-048", "1-049"]).get("/lines/list?ref=1-048").text
    assert html.count("?") >= 6      # three unknown columns per row
    assert "1-049" in html
    assert "measure" in html         # and it says the cost is on request


# --- an empty payload is not an instruction ----------------------------------
#
# A `POST /lines/save` carrying `{"ref": "1-097", "lines": []}` deleted that
# page's only record of its folio — a box a human drew over ink the segmenter
# missed. Two separate collapses made it possible and both are tested here: the
# store could not tell a withdrawal from an accident, and the route turned a key
# the client never sent into an instruction to clear.


def test_emptying_the_page_is_refused_unless_it_is_stated(root):
    """The editor asks before it sends this; nothing else may send it by
    accident. The refusal names what it would have destroyed, because the number
    is the thing that makes a stray save recognisable as one."""
    _zones(root)
    _save(root, [IN_ZONE])
    with pytest.raises(ValueError) as e:
        _save(root, [])
    assert "refusing to delete 1 correction" in str(e.value)
    assert len(corr.load_lines("1-048", root)) == 1


def test_a_stated_withdrawal_goes_through(root):
    """The other half — otherwise the guard is indistinguishable from having
    broken withdrawal, and the editor would have no way to empty a page."""
    _zones(root)
    _save(root, [IN_ZONE])
    res = _save(root, [], withdraw=True)
    assert res["removed"] is True
    assert corr.load_lines("1-048", root) == []


def test_an_absent_ink_exempt_key_leaves_the_rulings_standing(root):
    """**Absent is not empty.** `set_ink_exempt` pops the page's entry and
    rewrites the file with no `.prev` and no journal, so a route that read
    silence as "clear it" would destroy a human's band rulings with nothing to
    fall back on. The zone save already sends `exclude_unset`; that is undone if
    this end collapses the two back together."""
    _zones(root)
    _save(root, [IN_ZONE], ink=[{"y0": 700, "y1": 740, "note": "printed rule"}])
    assert corr.load_ink_exempt(root).get("1-048")

    _save_bare(root, {"lines": [IN_ZONE]})          # no ink_exempt key at all
    assert corr.load_ink_exempt(root).get("1-048")


def test_an_explicit_empty_ink_exempt_still_clears(root):
    """Clearing a page's rulings is a real act and stays available — an exemption
    can be re-asserted by making it again, which is why this layer needs the route
    to stop manufacturing the instruction rather than a flag of its own."""
    _zones(root)
    _save(root, [IN_ZONE], ink=[{"y0": 700, "y1": 740, "note": "printed rule"}])
    _save_bare(root, {"lines": [IN_ZONE], "ink_exempt": []})
    assert not corr.load_ink_exempt(root).get("1-048")
