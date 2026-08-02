"""The editor's server side: what it hands the page, and what it accepts back.

The browser half is not tested here — there is no harness for it in this repo, and
`review.py`'s page has none either. What *is* tested is the contract across the
wire, which is where the design guarantees actually live:

**The client cannot save a zone of the wrong width.** It sends a column index;
`save_payload` re-measures the page and resolves the x-pair itself. There is no
field in which to put a hand-sized zone, so the fixed-measure claim holds by
construction rather than by an editor's care. The one exception is a zone that
matched no column when the page was opened — passed through untouched, because
rewriting geometry the tool did not understand would repair the symptom and lose
the finding.

**The column is measured off each page, not configured per part.** The measure is
stable across the book (~1780 px) but its position drifts up to 236 px inside a
single part, so a constant was ~104 px out on `1-048`. The manual nudge is the
escape hatch for a page the anchor cannot read; like everything else about the
editor's view, it reaches no file — nothing in `gt/zones/` records it.
"""

from __future__ import annotations
from pathlib import Path

import pytest
from PIL import Image

from harness import zones as zn
from harness import zones_config as zc
from harness import zones_ui as ui

from conftest import write_scan

REPO = Path(__file__).resolve().parent.parent.parent

# The synthetic page's ink, and the column the anchor derives from it.
INK0, INK1 = 739, 2489
V0 = INK0 - 17  # ink_pad_left
V1 = V0 + 1778  # part 1's measure
BODY = [(y, y + 32) for y in range(600, 3300, 60)]


def cfg():
    return zc.load_config(REPO)


def make_scan(tmp_path: Path, ref: str = "1-048", size=(2824, 3897), shift=0):
    """A page with real ink, because the column is measured off the page now."""
    from PIL import ImageDraw

    d = tmp_path / "scans"
    d.mkdir(parents=True, exist_ok=True)
    write_scan(tmp_path, ref, size,
               ink=tuple((INK0 + shift, y0, INK1 + shift, y1) for y0, y1 in BODY))


def scans(tmp_path: Path, *refs):
    for r in refs:
        make_scan(tmp_path, r)


# ------------------------------------------------------------- page_state


def test_state_of_a_fresh_page(tmp_path):
    scans(tmp_path, "1-048")
    st = ui.page_state("1-048", tmp_path, cfg())
    assert st["zones"] == [] and st["keyed"] is False
    assert st["split"] == "train" and st["exempt"] == []
    assert st["page"] == {"w": 2824, "h": 3897}


def test_state_carries_neighbours_for_navigation(tmp_path):
    scans(tmp_path, "1-047", "1-048", "1-049")
    st = ui.page_state("1-048", tmp_path, cfg())
    assert (st["prev"], st["next"]) == ("1-047", "1-049")
    assert (st["index"], st["total"]) == (2, 3)


def test_first_and_last_scan_have_no_neighbour(tmp_path):
    scans(tmp_path, "1-048", "1-049")
    assert ui.page_state("1-048", tmp_path, cfg())["prev"] is None
    assert ui.page_state("1-049", tmp_path, cfg())["next"] is None


def test_the_column_is_measured_and_reported(tmp_path):
    """The editor draws against this page's own ink, not a per-part constant."""
    scans(tmp_path, "1-048")
    st = ui.page_state("1-048", tmp_path, cfg())
    assert st["columns"] == [{"x0": V0, "x1": V1}]
    assert st["anchor"] == {"measured": True, "source": "ink", "nudge": 0}


def test_the_state_carries_the_vertical_crop(tmp_path):
    """The editor frames to the inked band, not the leaf — one hover-jump saved
    on every page. A view concern only: nothing validates against it."""
    scans(tmp_path, "1-048")
    st = ui.page_state("1-048", tmp_path, cfg())
    c = st["content"]
    assert 0 < c["y0"] < BODY[0][0]
    assert BODY[-1][1] < c["y1"] < st["page"]["h"]


def test_a_shifted_page_gets_a_shifted_column(tmp_path):
    make_scan(tmp_path, "1-048", shift=200)
    st = ui.page_state("1-048", tmp_path, cfg())
    assert st["columns"] == [{"x0": V0 + 200, "x1": V1 + 200}]


def test_the_nudge_shifts_the_column_and_is_reported(tmp_path):
    """The escape hatch for a page the anchor cannot read. UI state — it rides
    the URL across navigation and reaches no file."""
    scans(tmp_path, "1-048")
    st = ui.page_state("1-048", tmp_path, cfg(), nudge=-12)
    assert st["columns"] == [{"x0": V0 - 12, "x1": V1 - 12}]
    assert st["anchor"]["nudge"] == -12


def test_stored_zones_resolve_back_to_a_column(tmp_path):
    """So that a reopened page follows a nudge instead of staying put."""
    scans(tmp_path, "1-048")
    zn.save_zones(
        "1-048",
        [{"label": "MainZone-P", "x0": V0, "y0": 600, "x1": V1, "y1": 900}],
        tmp_path,
    )
    assert ui.page_state("1-048", tmp_path, cfg())["zones"][0]["column"] == 0


def test_an_off_measure_zone_is_flagged_not_snapped(tmp_path):
    """Guessing here would repair the symptom and lose the finding — the
    validator has already raised against this zone."""
    scans(tmp_path, "1-048")
    zn.save_zones(
        "1-048",
        [{"label": "MainZone-P", "x0": 100, "y0": 600, "x1": 1200, "y1": 900}],
        tmp_path,
    )
    z = ui.page_state("1-048", tmp_path, cfg())["zones"][0]
    assert z["column"] is None and (z["x0"], z["x1"]) == (100, 1200)


# ------------------------------------------------------------ save_payload


def test_the_server_supplies_x_the_client_only_supplies_y(tmp_path):
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "split": "train",
            "exempt": [],
            "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900, "column": 0}],
        },
        tmp_path,
        cfg(),
    )
    z = zn.read_zones("1-048", tmp_path)[0]
    assert (z["x0"], z["x1"]) == (V0, V1)


def test_a_bogus_client_x_is_ignored_entirely(tmp_path):
    """There is no field in which to put a hand-sized zone: an x sent alongside
    a column index is simply not read."""
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "zones": [
                {
                    "label": "MainZone-P",
                    "y0": 600,
                    "y1": 900,
                    "column": 0,
                    "x0": 5,
                    "x1": 2800,
                }
            ],
        },
        tmp_path,
        cfg(),
    )
    z = zn.read_zones("1-048", tmp_path)[0]
    assert (z["x0"], z["x1"]) == (V0, V1)


def test_a_null_column_zone_passes_its_stored_x_through(tmp_path):
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "zones": [
                {
                    "label": "MainZone-P",
                    "y0": 600,
                    "y1": 900,
                    "column": None,
                    "x0": 100,
                    "x1": 1200,
                }
            ],
        },
        tmp_path,
        cfg(),
    )
    z = zn.read_zones("1-048", tmp_path)[0]
    assert (z["x0"], z["x1"]) == (100, 1200)


def test_the_nudge_is_applied_by_the_server_not_trusted_from_a_client_x(tmp_path):
    """A single bounded number the server can apply, not an arbitrary rectangle."""
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "nudge": -12,
            "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900, "column": 0}],
        },
        tmp_path,
        cfg(),
    )
    z = zn.read_zones("1-048", tmp_path)[0]
    assert (z["x0"], z["x1"]) == (V0 - 12, V1 - 12)


def test_no_ui_state_is_recorded_in_the_store(tmp_path):
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "nudge": 8,
            "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900, "column": 0}],
        },
        tmp_path,
        cfg(),
    )
    raw = zn.alto_for("1-048", tmp_path).read_text()
    assert "nudge" not in raw and "verso" not in raw and "recto" not in raw


def test_inverted_clicks_are_normalized(tmp_path):
    """Clicking bottom-then-top is the same zone; the editor should not care."""
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "zones": [{"label": "MainZone-P", "y0": 900, "y1": 600, "column": 0}],
        },
        tmp_path,
        cfg(),
    )
    z = zn.read_zones("1-048", tmp_path)[0]
    assert (z["y0"], z["y1"]) == (600, 900)


def test_column_index_past_the_end_clamps(tmp_path):
    """A stale column index after a flip must not throw away the save."""
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900, "column": 7}],
        },
        tmp_path,
        cfg(),
    )
    assert zn.read_zones("1-048", tmp_path)[0]["x0"] == V0


def test_save_returns_the_validation_of_what_it_just_wrote(tmp_path):
    scans(tmp_path, "1-048")
    res = ui.save_payload(
        {
            "ref": "1-048",
            "zones": [{"label": "MainZone-P", "y0": 600, "y1": 610, "column": 0}],
        },
        tmp_path,
        cfg(),
    )
    assert [e["rule"] for e in res["errors"]] == ["min-height"]


def test_save_carries_split_and_exemptions_through(tmp_path):
    scans(tmp_path, "1-048")
    ui.save_payload(
        {
            "ref": "1-048",
            "split": "eval",
            "exempt": ["rank-monotone"],
            "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900, "column": 0}],
        },
        tmp_path,
        cfg(),
    )
    assert zn.load_splits(tmp_path) == {"1-048": "eval"}
    assert zn.load_exempt(tmp_path) == {"1-048": ["rank-monotone"]}


def test_saving_no_zones_writes_the_empty_record_when_exempt(tmp_path):
    """A plate saves as zero zones — but only once a human has marked it one."""
    scans(tmp_path, "1-001")
    ui.save_payload({"ref": "1-001", "zones": [], "split": "exempt"}, tmp_path, cfg())
    assert zn.has_zones("1-001", tmp_path) and zn.read_zones("1-001", tmp_path) == []


def test_saving_no_zones_on_a_text_page_is_refused(tmp_path):
    """The editor gets the message back and shows it, rather than writing a page
    that reads as finished and holds nothing."""
    scans(tmp_path, "1-001")
    with pytest.raises(ValueError, match="no zones"):
        ui.save_payload({"ref": "1-001", "zones": []}, tmp_path, cfg())
    assert zn.has_zones("1-001", tmp_path) is False


def test_save_reports_the_counts_the_topbar_redraws_itself_from(tmp_path):
    """The selector is server-rendered on load, so a save has to hand back what
    changed or the pills go on reading `gt —` over a page that now has ground
    truth — the one act the store split exists to make visible, invisible."""
    scans(tmp_path, "1-048")
    res = ui.save_payload(
        {
            "ref": "1-048",
            "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900, "column": 0}],
        },
        tmp_path,
        cfg(),
    )
    assert res["zones"] == 1
    # Derived from gt, so it moves when gt moves and cannot be left as served.
    assert isinstance(res["paras_zones"], int)


def test_the_new_editor_actions_are_bound_and_documented(tmp_path):
    """A key in the config that no `case` handles is a key that does nothing, and
    the help would still list it."""
    scans(tmp_path, "1-048")
    c = cfg()
    html = ui.render_html("1-048", tmp_path, c)
    for act in ("merge_down", "sel_up", "sel_down"):
        assert act in c["actions"], act
        assert f"case '{act}':" in html, act
        assert f"<kbd>{c['actions'][act]}</kbd>" in html, act


def test_every_store_pill_carries_a_count_the_client_can_replace(tmp_path):
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    for name in ui.STORES:
        assert f"id='store-{name}'" in html
    # `split` is the train/eval/exempt mark and nothing else in this UI.
    assert "data-store='paras'" in html and "data-store='split'" not in html


def test_a_full_page_round_trips_through_state_and_back(tmp_path):
    """Open, save, reopen: the geometry the editor gets back is what it sent."""
    scans(tmp_path, "1-048")
    sent = [
        {"label": "RunningTitleZone", "y0": 400, "y1": 460, "column": 0},
        {"label": "MainZone-Continued", "y0": 560, "y1": 900, "column": 0},
        {"label": "MarginTextZone-Notes", "y0": 2900, "y1": 3200, "column": 0},
    ]
    ui.save_payload({"ref": "1-048", "zones": sent}, tmp_path, cfg())
    back = ui.page_state("1-048", tmp_path, cfg())["zones"]
    assert [(z["label"], z["y0"], z["y1"], z["column"]) for z in back] == [
        (z["label"], z["y0"], z["y1"], 0) for z in sent
    ]


# -------------------------------------------------------------- the markup


def test_html_embeds_the_config_and_the_state(tmp_path):
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    assert "const CFG=" in html and "const ST=" in html
    assert "/page/1-048.png" in html


def test_html_lists_every_type_with_its_key(tmp_path):
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    for t in cfg()["types"]:
        assert t["name"] in html and f"<kbd>{t['key']}</kbd>" in html


def test_html_does_not_inline_the_raster(tmp_path):
    """A 2824x3897 page as base64 is ~10 MB of markup per render."""
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    assert "data:image" not in html
    assert len(html) < 200_000
