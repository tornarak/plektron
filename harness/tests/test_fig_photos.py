"""The source PDF's own photograph placements, and the check built on them.

The scans are MRC-layered: a 1-bit master per page plus separate embedded JPEGs
for the photographs. `harness scans extract` writes those placements to
`data/pdf_images.json`, and `figures.fig_ink` compares them against `gt/fig/`.

**The rule is overlap, and the tests here exist mostly to keep it overlap.** It was
written as containment first, which is the intuitive reading of "the store accounts
for this photograph" and is wrong about this corpus: measured over its 371 rects,
255 merely partially overlap their best-matching keyed box, 86 are contained by it
and 17 contain it, because the rect sits proud of a hand-drawn box by 1-3 px at the
median. Containment reports 131 findings on a store that is complete; overlap
reports none. A test that only ever fed it concentric boxes would have agreed with
either.

The other thing held here is the **space** decision. Until the rasters are rebuilt
`gt/fig/` holds the legacy `pdftoppm` render's coordinates, which differ from the
master's by up to 35 px — enough to turn every correct box into a finding. So the
space is decided from the ALTO's own declared page box, and a box in neither known
space is `skip` with a note rather than a comparison between two coordinate systems
presented as a fact about figures.
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import write_scan

from harness import figures as F
from harness import zones_config as zc

REPO = Path(__file__).resolve().parent.parent.parent
PROJECT = REPO / "jesup" / "bogoras-chukchi"
CFG = zc.load_config(PROJECT)

G, D = F.GRAPHIC, F.FIGDESC

MASTER = (2781, 3866)
RENDER = (2824, 3897)
OFFSET = [21, 15]


def _manifest(root: Path, ref: str, rects: list[list[int]], *,
              master=MASTER, render=RENDER, offset=None) -> None:
    """Write a one-page `data/pdf_images.json`."""
    p = root / "data" / "pdf_images.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    doc[ref] = {
        "master": {"w": master[0], "h": master[1], "bpc": 1, "cs": "DeviceGray",
                   "xref": 1, "rendered": False},
        "offset": list(OFFSET if offset is None else offset),
        "render": list(render),
        "images": [{"xref": 2 + i, "w": 100, "h": 100, "bpc": 8,
                    "cs": "DeviceGray", "ppi": 150.0, "rect": r}
                   for i, r in enumerate(rects)],
    }
    p.write_text(json.dumps(doc), encoding="utf-8")


def _box(label, x0, y0, x1, y1):
    return {"label": label, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _keyed(root: Path, ref: str, boxes: list[dict], size=RENDER) -> None:
    write_scan(root, ref, size=size)
    F.save_figs(ref, boxes, root)


# --- the rule is overlap -----------------------------------------------------

def test_a_rect_proud_of_its_box_is_accounted_for(tmp_path):
    """The live shape: the photograph is slightly *larger* than what a human drew.

    This is the case containment gets wrong, and it is the common one — the median
    rect stands 1-3 px outside its box on each edge.
    """
    _keyed(tmp_path, "1-037", [_box(G, 458, 938, 2212, 2543)])
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    assert F.fig_ink("1-037", tmp_path)["state"] == "clean"


def test_a_rect_inside_its_box_is_accounted_for(tmp_path):
    """The other direction, which containment happens to get right."""
    _keyed(tmp_path, "1-037", [_box(G, 400, 900, 2300, 2600)])
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    assert F.fig_ink("1-037", tmp_path)["state"] == "clean"


def test_a_photograph_no_box_touches_is_unaccounted(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)])
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.fig_ink("1-037", tmp_path)
    assert rep["state"] == "unaccounted"
    assert rep["uncovered"] == [[435 + OFFSET[0], 907 + OFFSET[1],
                                 2188 + OFFSET[0], 2532 + OFFSET[1]]]


def test_one_rect_may_be_accounted_for_by_several_boxes(tmp_path):
    """A figure the book letters *a, b, c* is keyed as several pictures under one
    caption, and the PDF separates it as one image. 14 such figures in the corpus.
    """
    _keyed(tmp_path, "1-237", [_box(G, 428, 2121, 1408, 3279),
                               _box(G, 1498, 2123, 2474, 3303)])
    _manifest(tmp_path, "1-237", [[411, 2097, 2454, 3282]])
    assert F.fig_ink("1-237", tmp_path)["state"] == "clean"


# --- the loudest finding -----------------------------------------------------

def test_photographs_on_a_page_with_no_figure_alto_are_unaccounted(tmp_path):
    """Not `skip`. A photograph nobody keyed is the whole reason this exists, and
    filing it under "nothing to say" would lose exactly the case it is for.
    """
    write_scan(tmp_path, "1-037", size=RENDER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.fig_ink("1-037", tmp_path)
    assert rep["state"] == "unaccounted"
    assert "no figure ALTO" in rep["note"]


def test_a_page_with_no_photographs_is_skip_not_clean(tmp_path):
    """`clean` would be a claim. 16 keyed pages carry only line art."""
    _keyed(tmp_path, "1-021", [_box(G, 400, 900, 2300, 2600)])
    _manifest(tmp_path, "1-021", [])
    assert F.fig_ink("1-021", tmp_path)["state"] == "skip"


# --- which coordinate space the store is in ----------------------------------

def test_a_legacy_render_page_box_is_compared_through_the_offset(tmp_path):
    """`gt/fig/` is in render space until the rasters are rebuilt. The rect must be
    shifted by the manifest's offset before it is compared, or all 160 part 1 pages
    report findings that are really a 21 px translation.
    """
    _keyed(tmp_path, "1-037", [_box(G, 456, 922, 2209, 2547)], size=RENDER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.fig_ink("1-037", tmp_path)
    assert rep["space"] == "render"
    assert rep["state"] == "clean"


def test_a_master_space_page_box_is_compared_as_is(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 435, 907, 2188, 2532)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.fig_ink("1-037", tmp_path)
    assert rep["space"] == "master"
    assert rep["state"] == "clean"


def test_the_render_size_is_read_and_never_computed_from_the_offset(tmp_path):
    """Master plus offset is 2802x3881; the render is 2824x3897. The difference is
    the right-hand margin, and inferring it filed every part 1 page as an
    unrecognised space — reporting `skip`, which reads as "nothing to say" about
    176 pages that had plenty. So a page box matching the *inferred* size and not
    the recorded one must not be mistaken for the render.
    """
    inferred = (MASTER[0] + OFFSET[0], MASTER[1] + OFFSET[1])
    assert inferred != RENDER
    _keyed(tmp_path, "1-037", [_box(G, 456, 922, 2209, 2547)], size=inferred)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    assert F.fig_ink("1-037", tmp_path)["state"] == "skip"


def test_an_unknown_page_box_is_skip_with_a_note_never_a_guess(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)], size=(1000, 1400))
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.fig_ink("1-037", tmp_path)
    assert rep["state"] == "skip"
    assert "neither master" in rep["note"]


# --- how it reports ----------------------------------------------------------

def test_an_unaccounted_photograph_is_an_error_that_gates(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)])
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.validate_fig_page("1-037", tmp_path, CFG)
    assert [e["rule"] for e in rep["errors"]] == [F.UNACCOUNTED_RULE]


def test_an_excused_photograph_still_reports_flagged(tmp_path):
    """`set_rule_exempt`'s discipline: a finding that vanished when excused would
    leave no way to notice the excuse had outlived the page it was written for. The
    error channel has no exempted lane, so it moves to the flagged one rather than
    disappearing.
    """
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)])
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    F.set_rule_exempt("1-037", {F.UNACCOUNTED_RULE: "the plate is a foldout"},
                      tmp_path)
    rep = F.validate_fig_page("1-037", tmp_path, CFG)
    assert rep["errors"] == []
    assert [w["rule"] for w in rep["exempted"]] == [F.UNACCOUNTED_RULE]
    # The ruling travels with the finding: an excused warning shown without its
    # reason is indistinguishable from one nobody has looked at.
    assert "ruled: the plate is a foldout" in rep["exempted"][0]["detail"]


def test_an_exemption_with_no_reason_is_refused(tmp_path):
    """`zones.set_ink_exempt`'s rule, which this store lacked: "a reason is
    required and is the point of the file"."""
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)])
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    import pytest
    with pytest.raises(ValueError, match="no reason given"):
        F.set_rule_exempt("1-037", {F.UNACCOUNTED_RULE: "  "}, tmp_path)
    with pytest.raises(ValueError, match="no reason given"):
        F.set_rule_exempt("1-037", [F.UNACCOUNTED_RULE], tmp_path)


def test_a_legacy_noteless_exemption_loads_and_is_reported_as_unruled(tmp_path):
    """It still excuses — the human did rule — but the store cannot tell that from
    a keystroke, so the gap is surfaced rather than inherited silently."""
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)])
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    (tmp_path / "gt" / "fig" / "_rule_exempt.json").write_text(
        '{"1-037": ["unaccounted-picture"]}', encoding="utf-8")
    assert F.load_rule_exempt(tmp_path) == {"1-037": {"unaccounted-picture": ""}}
    rep = F.validate_fig_page("1-037", tmp_path, CFG)
    assert rep["errors"] == []
    assert "unruled-exemption" in [w["rule"] for w in rep["warnings"]]


def test_a_loose_box_warns_and_does_not_gate(tmp_path):
    """`1-287`'s shape: a clean pair whose box under-covers its photograph by 98 px
    on one edge. Real, worth saying, and not something the store must refuse.
    """
    _keyed(tmp_path, "1-287", [_box(G, 560, 604, 2092, 1912)])
    _manifest(tmp_path, "1-287", [[522, 563, 2169, 1899]])
    rep = F.validate_fig_page("1-287", tmp_path, CFG)
    assert rep["errors"] == []
    assert F.OUTSIDE_RULE in [w["rule"] for w in rep["warnings"]]


def test_no_manifest_at_all_says_nothing(tmp_path):
    """A clone that has never run the extractor must not have every page light up."""
    _keyed(tmp_path, "1-037", [_box(G, 458, 938, 2212, 2543)])
    assert F.pdf_images(tmp_path) == {}
    assert F.fig_ink("1-037", tmp_path)["state"] == "skip"
    assert F.validate_fig_page("1-037", tmp_path, CFG)["errors"] == []


# --- growing a box onto its photograph ---------------------------------------

def test_a_box_inside_its_photograph_grows_to_cover_it(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 460, 930, 2200, 2540)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.extend_to_rects("1-037", tmp_path, max_growth=0.2, commit=True)
    assert (rep["grew"], rep["wrote"]) == (1, True)
    b = [z for z in F.zones("1-037", tmp_path) if z["label"] == G][0]
    assert (b["hpos"], b["vpos"]) == (435, 907)
    assert (b["hpos"] + b["width"], b["vpos"] + b["height"]) == (2200, 2540)


def test_a_box_larger_than_its_photograph_is_never_contracted(tmp_path):
    """The bitonal-fringe case, and the one an intersection rule would ruin: some
    figures carry rules and lettering outside the JPEG, living in the master. 85 of
    this corpus's 371 boxes are already larger than their photograph.
    """
    _keyed(tmp_path, "1-037", [_box(G, 400, 880, 2250, 2570)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.extend_to_rects("1-037", tmp_path, max_growth=0.2, commit=True)
    assert (rep["grew"], rep["unchanged"]) == (0, 1)
    b = [z for z in F.zones("1-037", tmp_path) if z["label"] == G][0]
    assert (b["hpos"], b["vpos"], b["width"], b["height"]) == (400, 880, 1850, 1690)


def test_a_photograph_over_several_boxes_changes_neither(tmp_path):
    """Unioning each part with the whole rect would make them duplicates and lose
    the *a, b, c* structure `figure_boxes` folds on."""
    _keyed(tmp_path, "1-237", [_box(G, 428, 2121, 1408, 3279),
                               _box(G, 1498, 2123, 2474, 3303)], size=MASTER)
    _manifest(tmp_path, "1-237", [[411, 2097, 2454, 3282]])
    rep = F.extend_to_rects("1-237", tmp_path, max_growth=1.0, commit=True)
    assert (rep["grew"], rep["out_of_scope"], rep["wrote"]) == (0, 1, False)
    got = sorted((z["hpos"], z["width"])
                 for z in F.zones("1-237", tmp_path) if z["label"] == G)
    assert got == [(428, 980), (1498, 976)]


def test_block_ids_survive_the_growth(tmp_path):
    """The store keys 395 captions by the last field of a block id."""
    _keyed(tmp_path, "1-037", [_box(G, 460, 930, 2200, 2540),
                               _box(D, 460, 2600, 2200, 2700)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    before = [z["id"] for z in F.zones("1-037", tmp_path)]
    F.extend_to_rects("1-037", tmp_path, max_growth=0.2, commit=True)
    assert [z["id"] for z in F.zones("1-037", tmp_path)] == before


def test_report_mode_writes_nothing_and_says_what_it_would_gain(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 460, 930, 2200, 2540)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.extend_to_rects("1-037", tmp_path)
    assert (rep["grew"], rep["wrote"]) == (1, False)
    assert rep["growth"][0]["pct"] > 0
    b = [z for z in F.zones("1-037", tmp_path) if z["label"] == G][0]
    assert (b["hpos"], b["vpos"]) == (460, 930)


def test_no_margin_means_no_write_even_with_commit(tmp_path):
    """The ceiling is a judgement about how far a mechanical rule may move a
    rectangle a person drew. Defaulting it would make that judgement silently and
    then let it read as the operator's."""
    _keyed(tmp_path, "1-037", [_box(G, 460, 930, 2200, 2540)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.extend_to_rects("1-037", tmp_path, commit=True)
    assert rep["wrote"] is False
    b = [z for z in F.zones("1-037", tmp_path) if z["label"] == G][0]
    assert (b["hpos"], b["vpos"]) == (460, 930)


def test_a_box_growing_past_the_margin_is_refused_and_counted(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 1000, 1500, 1200, 1700)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.extend_to_rects("1-037", tmp_path, max_growth=0.10, commit=True)
    assert (rep["grew"], rep["over"], rep["wrote"]) == (0, 1, False)
    assert rep["growth"][0]["pct"] > 10
    b = [z for z in F.zones("1-037", tmp_path) if z["label"] == G][0]
    assert (b["hpos"], b["width"]) == (1000, 200)


def test_growth_that_would_move_a_caption_is_refused_and_rolled_back(tmp_path,
                                                                    monkeypatch):
    """`_gap` pairs a picture to a caption by distance, so growing a picture
    downward moves it toward one, and a fringe correction has no business deciding
    which caption belongs to which picture.

    **Forced, because it could not be provoked.** Growing a picture by 900 px — two
    orders above the ≤9.63 % this verb actually applies — still left `paired`
    unchanged, since `_gap` tolerates a caption sitting inside its picture. So the
    guard is defence in depth rather than a live hazard, and what is testable is
    the mechanism: when the pairing does differ, the page goes back exactly as it
    was and says why.
    """
    _keyed(tmp_path, "1-037", [_box(G, 460, 930, 2200, 2540),
                               _box(D, 460, 2600, 2200, 2700)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    before = [(z["id"], z["hpos"], z["vpos"], z["width"], z["height"])
              for z in F.zones("1-037", tmp_path)]

    calls = []
    real = F._assignment

    def fake(ref, root=Path(".")):
        calls.append(ref)
        return (("picture", f"caption-{len(calls)}"),), ()
    monkeypatch.setattr(F, "_assignment", fake)

    rep = F.extend_to_rects("1-037", tmp_path, max_growth=0.2, commit=True)
    assert rep["wrote"] is False
    assert "caption" in rep["note"]
    monkeypatch.setattr(F, "_assignment", real)
    assert [(z["id"], z["hpos"], z["vpos"], z["width"], z["height"])
            for z in F.zones("1-037", tmp_path)] == before


def test_two_pictures_swapping_order_is_not_a_changed_assignment(tmp_path):
    """`1-167`, `1-227` and `1-325` — three plates the guard wrongly refused.

    Growing a box upward can overtake its neighbour in the top-to-bottom sort, so
    `paired`'s rows come back in a different order while every picture keeps
    exactly its own caption. Comparing whole rows called that a changed pairing and
    rolled back a correct 1-2 % growth on all three pages. Direction is what `_gap`
    actually keys on — a caption must follow its picture down or across the page —
    so an ordinal swap is the store reporting geometry truthfully.
    """
    _keyed(tmp_path, "1-167", [
        _box(G, 370, 590, 1376, 1898), _box(D, 1390, 700, 1470, 1800),
        _box(G, 1518, 590, 2506, 1904), _box(D, 2520, 700, 2600, 1800),
    ], size=MASTER)
    # The right-hand picture grows 12 px upward; the left one only 5.
    _manifest(tmp_path, "1-167", [[369, 585, 1382, 1899], [1518, 578, 2512, 1904]])
    before = F._assignment("1-167", tmp_path)
    rep = F.extend_to_rects("1-167", tmp_path, max_growth=0.05, commit=True)
    assert (rep["grew"], rep["wrote"], rep["note"]) == (2, True, "")
    assert F._assignment("1-167", tmp_path) == before


def test_extend_is_a_no_op_where_the_space_is_unknown(tmp_path):
    _keyed(tmp_path, "1-037", [_box(G, 460, 930, 2200, 2540)], size=(1000, 1400))
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    rep = F.extend_to_rects("1-037", tmp_path, max_growth=0.2, commit=True)
    assert rep["grew"] == 0 and "neither known space" in rep["note"]


# --- proposals from the manifest ---------------------------------------------

def test_a_proposal_carries_pictures_and_never_a_caption(tmp_path):
    """The PDF says where a picture is and nothing about captions. Minting a
    FigDesc here would author a claim the source does not make."""
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    assert F.propose_from_pdf(["1-037"], tmp_path)[0]["figures"] == 1
    got = F.zones("1-037", tmp_path, F.MZFIGDIR)
    assert [z["label"] for z in got] == [G]
    assert (got[0]["hpos"], got[0]["vpos"]) == (435, 907)


def test_a_proposal_names_the_manifest_and_not_a_model(tmp_path):
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    F.propose_from_pdf(["1-037"], tmp_path)
    text = F.alto_for("1-037", tmp_path, F.MZFIGDIR).read_text(encoding="utf-8")
    assert F.PDF_IMAGES in text


def test_a_proposal_will_not_clobber_the_segmenter_without_force(tmp_path):
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    F.propose_from_pdf(["1-037"], tmp_path)
    again = F.propose_from_pdf(["1-037"], tmp_path)[0]
    assert again["wrote"] is False and "--force" in again["note"]
    assert F.propose_from_pdf(["1-037"], tmp_path, force=True)[0]["wrote"] is True


def test_the_human_store_still_outranks_a_proposal(tmp_path):
    """The discipline `mz/fig/` exists for: a machine box that reached `gt/fig/`
    would be painted white into the rasters the zone segmenter trains on."""
    from harness import zones_ui
    _keyed(tmp_path, "1-037", [_box(G, 460, 930, 2200, 2540)], size=MASTER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    F.propose_from_pdf(["1-037"], tmp_path)
    st = zones_ui._fig_state("1-037", tmp_path, CFG)
    assert st["fig_proposal"] == ""
    assert st["figs"][0]["x0"] == 460


# --- the editor --------------------------------------------------------------

def test_the_editor_gets_the_rects_in_its_own_coordinates(tmp_path):
    from harness import zones_ui
    _keyed(tmp_path, "1-037", [_box(G, 456, 922, 2209, 2547)], size=RENDER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    photos = zones_ui._fig_state("1-037", tmp_path, CFG)["fig_photos"]
    assert photos == [{"x0": 456, "y0": 922, "x1": 2209, "y1": 2547,
                       "covered": True}]


def test_the_editor_is_told_which_photograph_is_unaccounted(tmp_path):
    from harness import zones_ui
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)], size=RENDER)
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    photos = zones_ui._fig_state("1-037", tmp_path, CFG)["fig_photos"]
    assert [p["covered"] for p in photos] == [False]


def test_the_editor_draws_nothing_when_the_space_is_unknown(tmp_path):
    """It inherits `fig_ink`'s refusal to guess rather than drawing rects 21 px out
    of place, which would look like a keying error and is not one.
    """
    from harness import zones_ui
    _keyed(tmp_path, "1-037", [_box(G, 100, 100, 300, 300)], size=(1000, 1400))
    _manifest(tmp_path, "1-037", [[435, 907, 2188, 2532]])
    assert zones_ui._fig_state("1-037", tmp_path, CFG)["fig_photos"] == []
