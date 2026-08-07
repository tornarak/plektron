"""The editor's server side: what it hands the page, and what it accepts back.

The browser half is not tested here — there is no harness for it in this repo, and
`review.py`'s page has none either. What *is* tested is the contract across the
wire, which is where the design guarantees actually live:

**The client cannot save a *zone* of the wrong width.** It sends a column index;
`save_payload` re-measures the page and resolves the x-pair itself. There is no
field in which to put a hand-sized zone, so the fixed-measure claim holds by
construction rather than by an editor's care. The one exception is a zone that
matched no column when the page was opened — passed through untouched, because
rewriting geometry the tool did not understand would repair the symptom and lose
the finding.

**That guarantee is about zones and does not generalise.** The figure track,
sharing this editor, inverts it on purpose: a picture's edges are a property of
that picture, so the client's rectangle is taken as given and bounded only to the
page. Read "the server supplies x" with its subject attached, or the figure path
looks like a hole in a rule it was never inside. The two are held apart at the
bottom of this file.

**The column is measured off each page, not configured per part.** The measure is
stable across the book (~1780 px) but its position drifts up to 236 px inside a
single part, so a constant was ~104 px out on `1-048`. The manual nudge is the
escape hatch for a page the anchor cannot read; like everything else about the
editor's view, it reaches no file — nothing in `gt/zones/` records it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_scan

from harness import zones as zn
from harness import zones_config as zc
from harness import zones_ui as ui

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
    the help would still list it.

    **Every configured action, not a chosen few.** This walked a hardcoded tuple
    of three while the config grew past it, which is the shape of gate that stops
    catching things — the figure track added two actions in a second namespace and
    the tuple would not have noticed either. Both namespaces are swept now, since
    they share one keyboard and one `switch`.
    """
    scans(tmp_path, "1-048")
    c = cfg()
    html = ui.render_html("1-048", tmp_path, c)
    acts = {k: v for k, v in c["actions"].items() if not k.startswith("_")}
    acts.update({k: v for k, v in
                 ((c.get("figures") or {}).get("actions") or {}).items()
                 if not k.startswith("_")})
    assert {"merge_down", "toggle_track", "caption_beside"} <= set(acts)
    for act, key in acts.items():
        assert f"case '{act}':" in html, act
        assert f"<kbd>{key}</kbd>" in html, act


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


# ------------------------------------------------------- the figure track
#
# One editor, two tracks, and the seam between them is where this can go wrong.
# The zone half's central guarantee is that **the client cannot supply an x** —
# tested above, three ways. The figure half inverts it deliberately: a picture's
# edges are a property of that picture and only the person looking can say where
# they are. So the invariant is not "the server supplies x", it is "the server
# supplies x *for a zone*", and these hold the two apart.

from harness import figures as fg  # noqa: E402

G, D = fg.GRAPHIC, fg.FIGDESC


def _fig(label, x0, y0, x1, y1, **kw):
    return {"label": label, "x0": x0, "y0": y0, "x1": x1, "y1": y1, **kw}


def _zone():
    return {"label": "MainZone-P", "y0": 600, "y1": 900, "column": 0}


def _save(tmp_path, **extra):
    payload = {"ref": "1-048", "split": "train", "exempt": [],
               "zones": [_zone()], **extra}
    return ui.save_payload(payload, tmp_path, cfg())


def test_a_page_with_no_figures_carries_an_empty_layer(tmp_path):
    scans(tmp_path, "1-048")
    st = ui.page_state("1-048", tmp_path, cfg())
    assert st["figs"] == [] and st["fig_proposal"] == ""
    assert st["fig_present"] == {"gt": None, "mz": None}


def test_the_figure_layer_is_not_mixed_into_the_zone_layer(tmp_path):
    """Two stores, two lists. Nothing derives one from the other, and a reader of
    `zones` must never be handed a picture."""
    scans(tmp_path, "1-048")
    fg.save_figs("1-048", [_fig(G, 400, 900, 2200, 2500)], tmp_path)
    zn.save_zones("1-048", [{"label": "MainZone-P", "x0": V0, "y0": 600,
                             "x1": V1, "y1": 900}], tmp_path)
    st = ui.page_state("1-048", tmp_path, cfg())
    assert len(st["zones"]) == 1 and len(st["figs"]) == 1
    assert st["zones"][0]["label"] == "MainZone-P"
    assert st["figs"][0]["label"] == G


def test_the_client_supplies_x_for_a_figure(tmp_path):
    """The deliberate inverse of `test_the_server_supplies_x_the_client_only_
    supplies_y`. Both are true; neither generalises to the other track."""
    scans(tmp_path, "1-048")
    _save(tmp_path, figs=[_fig(G, 431, 902, 2203, 2501)])
    b = fg.zones("1-048", tmp_path)[0]
    assert (b["hpos"], b["width"]) == (431, 2203 - 431)
    # …and the zone saved in the same request still got its x from the server.
    assert zn.read_zones("1-048", tmp_path)[0]["x0"] == V0


def test_a_figure_is_bounded_to_the_page(tmp_path):
    """The server's only claim over a rectangle: it must describe part of a page
    that exists. Everything inside that is the human's."""
    scans(tmp_path, "1-048")
    _save(tmp_path, figs=[_fig(G, -50, -10, 99999, 99999)])
    b = fg.zones("1-048", tmp_path)[0]
    assert (b["hpos"], b["vpos"]) == (0, 0)
    assert b["hpos"] + b["width"] == 2824 and b["vpos"] + b["height"] == 3897


def test_no_figs_key_leaves_the_figure_store_untouched(tmp_path):
    """**The mtime guarantee.** `zones blot` keys the zone segmenter's training
    rasters off `gt/fig/`'s mtimes, so an ordinary zone save that rewrote all 252
    figure files would stale every raster the model learns from. Absence of the
    key, not an equality check, is what prevents it."""
    scans(tmp_path, "1-048")
    fg.save_figs("1-048", [_fig(G, 400, 900, 2200, 2500)], tmp_path)
    p = fg.alto_for("1-048", tmp_path)
    before = p.stat().st_mtime_ns
    res = _save(tmp_path)
    assert p.stat().st_mtime_ns == before
    assert "figs_saved" not in res and "blot_stale" not in res


def test_a_figure_save_says_the_blot_is_stale(tmp_path):
    scans(tmp_path, "1-048")
    res = _save(tmp_path, figs=[_fig(G, 400, 900, 2200, 2500)])
    assert res["blot_stale"] is True and res["figs_saved"] == 1


def test_gt_ids_round_trip_and_machine_ids_do_not(tmp_path):
    """An `mz` proposal's ids are the segmenter's and key nothing in
    `data/readings.md`; carrying one into a save would put a string shaped like a
    caption key into the store with no reading behind it."""
    scans(tmp_path, "1-048")
    fg.save_figs("1-048", [_fig(G, 400, 900, 2200, 2500)], tmp_path)
    kept = _save(tmp_path, fig_ids="gt",
                 figs=[_fig(G, 400, 900, 2200, 2500, id="fig_1-048_001"),
                       _fig(D, 400, 2530, 2200, 2640)])
    assert kept["figs_saved"] == 2
    assert {b["id"] for b in fg.zones("1-048", tmp_path)} == {
        "fig_1-048_001", "fig_1-048_002"}

    _save(tmp_path, fig_ids="", figs=[_fig(G, 400, 900, 2200, 2500, id="mz_x_9")])
    assert [b["id"] for b in fg.zones("1-048", tmp_path)] == ["fig_1-048_003"]


def test_a_caption_with_no_reading_is_named_back_to_the_editor(tmp_path):
    """The one thing a human leaves the editor to finish. Not an error — the box
    is drawn before the text is keyed, by design — but said at once, naming the
    block, rather than surfacing later as an orphan in `corpus figures`."""
    scans(tmp_path, "1-048")
    res = _save(tmp_path, figs=[_fig(G, 400, 900, 2200, 2500),
                                _fig(D, 400, 2530, 2200, 2640)])
    assert res["readings_missing"] == ["1-048|002"]


def test_emptying_the_layer_is_refused_and_routes_to_fig_delete(tmp_path):
    """Absence of the file is how this store says 'no figures here', so an empty
    one would assert the opposite. A human who deleted the last box has an intent
    and the editor must name the verb for it rather than relay a stack trace."""
    scans(tmp_path, "1-048")
    fg.save_figs("1-048", [_fig(G, 400, 900, 2200, 2500)], tmp_path)
    res = _save(tmp_path, figs=[])
    assert "fig delete 1-048" in res["fig_error"]
    assert fg.alto_for("1-048", tmp_path).exists()


def test_an_mz_proposal_shows_only_where_gt_is_absent(tmp_path):
    """The store rule, and here it is not merely symmetry with the zone half: a
    machine figure box adopted unread would be painted white by `zones blot` into
    the rasters the *zone* segmenter trains on. A wrong one teaches."""
    scans(tmp_path, "1-048")
    (tmp_path / "mz/fig").mkdir(parents=True)
    fg.save_figs("1-048", [_fig(G, 100, 100, 900, 900)], tmp_path)
    mz = fg.alto_for("1-048", tmp_path, fg.MZFIGDIR)
    mz.write_bytes(fg.alto_for("1-048", tmp_path).read_bytes())

    st = ui.page_state("1-048", tmp_path, cfg())
    assert st["fig_proposal"] == "" and st["fig_ids"] == "gt"

    fg.delete_figs("1-048", tmp_path, commit=True)
    st = ui.page_state("1-048", tmp_path, cfg())
    assert st["fig_proposal"] == "mz" and st["fig_ids"] == ""


def test_the_figure_rules_are_transcribed_faithfully_into_the_js(tmp_path):
    """The two-copies gate, `test_zones_order.py`'s shape.

    `zones_config.fig_warnings` and the page's `figWarnings()` are one vocabulary
    written twice — the server evaluates it on save, the browser on every
    keystroke — so a rule added to the config has to reach both. A rule the JS
    cannot see would be a banner that appears only after a save, which is the
    surface a human is not looking at by then.
    """
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    for rule in (cfg().get("figures") or {}).get("rules") or []:
        # Only the rules the *editor* can evaluate live client-side: the count
        # rule is about the boxes on screen. The geometry rules are the server's,
        # and are reported from the save rather than predicted.
        if rule["id"] == "captions-lte-figures":
            assert f"'{rule['id']}'" in html, rule["id"]


def test_the_inactive_track_dims_by_two_configured_amounts(tmp_path):
    """Not one number: a keyed page carries eight or ten body zones against two
    or three figure boxes, so the zone layer has to go much quieter under the
    figure track than the figure layer does under the zone track."""
    view = (cfg().get("figures") or {}).get("view") or {}
    assert 0 < view["dim_zones"] < view["dim_figs"] < 1
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    assert "dim_zones" in html and "dim_figs" in html


def test_the_page_says_which_track_the_pointer_is_on(tmp_path):
    """The toggle's visible consequence is that something *stops* — the zone
    preview no longer follows the cursor — so without a mode readout pressing it
    reads as the editor freezing. Four independent tells, because one that a
    later edit removes leaves the same confusion.
    """
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    assert "id='track'" in html                 # a pill in the topbar
    assert "figure track — drag" in html        # narrated on the switch
    assert "trackChips" in html                 # the inactive half dims
    assert "S.hoverX" in html                   # a crosshair, not a single rule
    # …and the chips declare which keyboard they belong to, or the panel cannot
    # say which half is live.
    assert "data-track='zone'" in html and "data-track='fig'" in html


def test_a_committed_figure_box_can_be_resized_and_moved(tmp_path):
    """The one place the figure track was worse than the zone track: a box could
    only be deleted and drawn again, where a zone has had edge handles and
    `Shift+Arrow` since it existed.

    Eight handles rather than four corners, and that is the substantive choice —
    a caption's *height* is the commonest correction, because the box was drawn
    round the wrong number of printed lines, and only an edge handle changes
    height alone.
    """
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    assert "HANDLES" in html and "resizeTo" in html
    assert "'nw'" in html and "'n'" in html and "'se'" in html
    assert "S.figMove" in html                  # shift-drag translates
    assert "drag a handle to resize" in html    # and the status line says so


def test_an_armed_corner_owns_the_next_click(tmp_path):
    """Handles and the armed corner both want the click, so one has to yield.

    The corner wins: it is mid-gesture and the handle is not. Without this a
    caption whose opposite corner fell near an existing box would refuse to
    finish, and nothing on screen would explain why.
    """
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    assert "S.figGrab = S.figPending ? null : handleAt(p);" in html
    assert "S.figPending ? null : handleAt(pt)" in html


def test_the_unaccounted_ink_stays_outside_the_dimming(tmp_path):
    """The one piece of zone-track furniture that must not fade on the figure
    track: a band no zone accounts for is very often the undeclared picture you
    are about to draw, which is exactly how `1-191` surfaced. Held by source
    order, since the dimming is an SVG group and the hatching has to close it
    first — a `</g>` moved below the bands would dim them with everything else,
    and nothing else in this repo would notice.
    """
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    opened = html.index("<g opacity=")
    closed = html.index("parts.push('</g>')")
    hatch = html.index('id="hatch"')
    assert opened < closed < hatch
    assert html.count("<g opacity=") == html.count("parts.push('</g>')") == 1


def test_the_figure_types_are_listed_with_their_keys(tmp_path):
    scans(tmp_path, "1-048")
    html = ui.render_html("1-048", tmp_path, cfg())
    for t in (cfg().get("figures") or {})["types"]:
        assert f"<kbd>{t['key']}</kbd>" in html
        assert t["label"] in html
