"""Two zone stores and the view over them: what each one is allowed to answer.

`gt/zones/` is what a human has been through; `mz/zones/` is what the trained
segmenter emitted; `zones/` is a symlink farm joining them under one set of names,
the human file always winning. The shape is `ocr/` over `gt/ocr/` and so is the
rule — **reads may resolve through the view, writes never do.**

What these tests hold is the set of distinctions that would be invisible if they
broke. A store parameter that leaked into the sidecars would let a machine sweep
answer questions about which pages are held out. A prediction that satisfied
`has_zones` would make an itinerary look finished and leave the next session with
nowhere to resume. An ink verdict about a machine file written into the gt cache
would be a claim about work nobody has done, drawn in the same column as one about
work someone has. Each of those fails silently and each looks like success — which
is the failure mode this repo is organised against, so it is the one worth testing.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from conftest import write_scan

from harness import zones as zn
from harness import zones_config as zc
from harness import zones_ui as ui


def _render(name, ctx):
    from harness.web import templates

    return templates.get_template(name).render(**ctx, request=None)


def render_html(*a, **kw):
    """The editor page, through the template the server uses.

    `render_html` returned a string; it is `page_context` plus a template now, so
    a test that wants the page takes the same two steps the server does.
    """
    return _render("zones/page.html", ui.page_context(*a, **kw))


def render_list_html(*a, **kw):
    return _render("zones/list.html", ui.list_context(*a, **kw))


#: The behaviour, which is a cached static file rather than a blob interpolated
#: into every page — 68 KB of it, on the editor navigated with the arrow keys.
JS = (Path(__file__).parent.parent / "web" / "static" / "js"
      / "zones.js").read_text(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent.parent

# The shipped config, so these tests bind the numbers actually in use —
# `min_zone_h_px` above all, which is what separates a zone from a sliver.
CFG = zc.load_config(REPO)

ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Tags><OtherTag ID="BT1" LABEL="{label}"/></Tags>
  <Layout><Page WIDTH="2824" HEIGHT="3897"><PrintSpace>
    <TextBlock ID="{bid}" HPOS="{x0}" VPOS="{y0}" WIDTH="{w}" HEIGHT="{h}"
               TAGREFS="BT1">
      <Shape><Polygon POINTS="{x0} {y0} {x1} {y0} {x1} {y1} {x0} {y1}"/></Shape>
    </TextBlock>
  </PrintSpace></Page></Layout>
</alto>
"""


def write_page(
    root: Path,
    ref: str,
    store: str,
    label="MainZone-P",
    bid="mz_x",
    x0=700,
    y0=600,
    x1=2478,
    y1=900,
):
    d = root / store
    d.mkdir(parents=True, exist_ok=True)
    (d / f"chukchi-{ref}.xml").write_text(
        ALTO.format(
            label=label, bid=bid, x0=x0, y0=y0, x1=x1, y1=y1, w=x1 - x0, h=y1 - y0
        ),
        encoding="utf-8",
    )


def make_scan(root: Path, ref: str):
    write_scan(root, ref,
               ink=tuple((739, y, 2489, y + 32) for y in range(600, 3300, 60)))


# ------------------------------------------------------- the store parameter


def test_each_store_answers_for_itself(tmp_path):
    """The bare minimum: the same ref in both stores reads back differently."""
    write_page(tmp_path, "1-048", zn.ZONEDIR, label="MainZone-P")
    write_page(tmp_path, "1-048", zn.MZDIR, label="RunningTitleZone")
    assert zn.read_zones("1-048", tmp_path)[0]["label"] == "MainZone-P"
    assert (
        zn.read_zones("1-048", tmp_path, store=zn.MZDIR)[0]["label"]
        == "RunningTitleZone"
    )
    assert zn.zone_refs(tmp_path) == ["1-048"]
    assert zn.zone_refs(tmp_path, zn.MZDIR) == ["1-048"]


def test_the_default_is_the_human_store(tmp_path):
    """Every existing caller passes no store and must keep meaning `gt/zones/`.

    Stated as a test because the whole safety of this change rests on it: the five
    sidecar readers reach the store through a bare `zone_dir(root)` and were not
    edited at all.
    """
    write_page(tmp_path, "1-048", zn.MZDIR)
    assert zn.zone_refs(tmp_path) == []
    assert zn.has_zones("1-048", tmp_path) is False
    assert zn.zone_dir(tmp_path) == tmp_path / "gt/zones"


def test_a_prediction_does_not_make_a_page_look_keyed(tmp_path):
    """`has_zones` on the default store is what the editor's resume and its
    unkeyed counts read. If a prediction satisfied it, `--predict` over an
    itinerary would mark the whole list done in one command."""
    write_page(tmp_path, "1-048", zn.MZDIR)
    assert zn.has_zones("1-048", tmp_path) is False
    assert zn.has_zones("1-048", tmp_path, zn.MZDIR) is True


def test_zone_refs_dedupes_by_real_path(tmp_path):
    """A symlink farm must not double-count. The README's invariant is
    unconditional and the store parameter is what first makes a farm reachable."""
    import os

    write_page(tmp_path, "1-048", zn.ZONEDIR)
    view = tmp_path / zn.VIEWDIR
    view.mkdir(parents=True)
    for name in ("chukchi-1-048.xml", "chukchi-1-049.xml"):
        (view / name).symlink_to(
            os.path.relpath(
                (tmp_path / zn.ZONEDIR / "chukchi-1-048.xml").resolve(), view.resolve()
            )
        )
    # Two names, one inode: one ref, not two.
    assert zn.zone_refs(tmp_path, zn.VIEWDIR) == ["1-048"]


def test_a_broken_link_is_skipped_not_raised(tmp_path):
    view = tmp_path / zn.VIEWDIR
    view.mkdir(parents=True)
    (view / "chukchi-1-048.xml").symlink_to("../gt/zones/gone.xml")
    assert zn.zone_refs(tmp_path, zn.VIEWDIR) == []


# --------------------------------------------------------------- the sidecars


def test_the_sidecars_take_no_store(tmp_path):
    """They record human judgements about *pages*, and there is no such thing as
    the machine store's opinion of which pages are held out. Enforced by signature
    rather than by convention, so nobody can parameterise them 'for symmetry'."""
    import inspect

    for fn in (
        zn.load_splits,
        zn.set_split,
        zn.load_exempt,
        zn.set_exempt,
        zn.load_ink_exempt,
        zn.set_ink_exempt,
        zn.ink_stamp,
        zn.load_ink_cache,
        zn.cached_ink,
        zn.record_ink,
        zn.save_zones,
    ):
        assert "store" not in inspect.signature(fn).parameters, fn.__name__


def test_a_split_marked_once_is_read_by_both_stores(tmp_path):
    """The corollary of the above, and the reason it is right: an exemption is a
    ruling about the page, true whoever's zones are being measured against it."""
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    write_page(tmp_path, "1-048", zn.MZDIR)
    zn.set_split("1-048", "exempt", tmp_path)
    make_scan(tmp_path, "1-048")
    cfg = zc.load_config(REPO)
    for store in (zn.ZONEDIR, zn.MZDIR):
        assert (
            zn.validate_page("1-048", tmp_path, cfg, ink=False, store=store)["split"]
            == "exempt"
        )


# ------------------------------------------------------------- the ink cache


def test_a_machine_sweep_never_writes_the_ink_cache(tmp_path):
    """The cache is keyed by ref alone and feeds the editor's page list, which
    lists ground truth. A verdict about a machine file landing there would be a
    claim about work nobody has done, in the same column as one about work someone
    has — and the stamp design exists precisely to stop that."""
    write_page(tmp_path, "1-048", zn.MZDIR)
    make_scan(tmp_path, "1-048")
    cfg = zc.load_config(REPO)
    zn.validate_corpus(tmp_path, cfg, ink=True, store=zn.MZDIR)
    assert not (tmp_path / zn.ZONEDIR / zn.INK_CACHE_JSON).exists()
    assert zn.load_ink_cache(tmp_path) == {}


def test_a_human_sweep_still_writes_it(tmp_path):
    """The other half — otherwise the test above would pass on a cache that had
    simply stopped working."""
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    make_scan(tmp_path, "1-048")
    zn.validate_corpus(tmp_path, zc.load_config(REPO), ink=True)
    assert zn.cached_ink("1-048", tmp_path) is not None


# ---------------------------------------------------------------- the view


def test_the_human_file_wins(tmp_path):
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    write_page(tmp_path, "1-048", zn.MZDIR)
    write_page(tmp_path, "1-102", zn.MZDIR)
    rep = zn.link_view(tmp_path)
    assert rep == {
        "dir": str(tmp_path / zn.VIEWDIR),
        "from_gt": 1,
        "from_mz": 1,
        "removed": 0,
    }
    view = tmp_path / zn.VIEWDIR
    assert (view / "chukchi-1-048.xml").resolve() == (
        tmp_path / zn.ZONEDIR / "chukchi-1-048.xml"
    ).resolve()
    assert (view / "chukchi-1-102.xml").resolve() == (
        tmp_path / zn.MZDIR / "chukchi-1-102.xml"
    ).resolve()


def test_the_links_are_relative(tmp_path):
    """So the farm survives a clone or a move, as `paths.ensure_page_link` and
    `assemble` already require of theirs."""
    import os

    write_page(tmp_path, "1-048", zn.ZONEDIR)
    zn.link_view(tmp_path)
    target = os.readlink(tmp_path / zn.VIEWDIR / "chukchi-1-048.xml")
    assert not Path(target).is_absolute()


def test_a_stale_link_is_removed_and_counted(tmp_path):
    """A dangling entry in the view would read as a missing page rather than as a
    link nobody cleaned up."""
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    write_page(tmp_path, "1-102", zn.MZDIR)
    zn.link_view(tmp_path)
    (tmp_path / zn.MZDIR / "chukchi-1-102.xml").unlink()
    rep = zn.link_view(tmp_path)
    assert rep["removed"] == 1 and rep["from_mz"] == 0
    assert not (tmp_path / zn.VIEWDIR / "chukchi-1-102.xml").exists()
    assert list((tmp_path / zn.VIEWDIR).glob("*.xml")) != []


def test_a_page_promoted_to_gt_reroutes_its_link(tmp_path):
    """The review loop's visible effect: once a human saves, the same name stops
    resolving to the machine's word."""
    write_page(tmp_path, "1-102", zn.MZDIR)
    zn.link_view(tmp_path)
    assert (tmp_path / zn.VIEWDIR / "chukchi-1-102.xml").resolve() == (
        tmp_path / zn.MZDIR / "chukchi-1-102.xml"
    ).resolve()
    write_page(tmp_path, "1-102", zn.ZONEDIR)
    zn.link_view(tmp_path)
    assert (tmp_path / zn.VIEWDIR / "chukchi-1-102.xml").resolve() == (
        tmp_path / zn.ZONEDIR / "chukchi-1-102.xml"
    ).resolve()


# ---------------------------------------------------------------- the predictor


def test_predict_refuses_a_page_with_no_blot(tmp_path):
    """Predicting off the plain scan asks the model a different question than the
    one it was trained on, and asks it on exactly the 252 pages where the
    difference exists. `assemble` refuses the same substitution."""
    make_scan(tmp_path, "1-048")
    with pytest.raises(FileNotFoundError, match="blotted"):
        zn.predict("1-048", tmp_path, net=object(), sha="x")


def test_predict_all_skips_exempt_pages(tmp_path):
    """A plate has no right answer, so a prediction there manufactures zones for a
    page a human has already ruled out. Counted, never silently dropped."""
    (tmp_path / zn.BLOTDIR).mkdir(parents=True)
    zn.set_split("1-048", "exempt", tmp_path)

    called = []

    def fake_predict(ref, root, **kw):
        called.append(ref)
        return {"ref": ref, "zones": 0}

    import harness.zones as mod

    real_predict, real_load = mod.predict, mod.load_segmenter
    mod.predict = fake_predict
    mod.load_segmenter = lambda *a, **k: (object(), "sha")
    try:
        rep = mod.predict_all(tmp_path, refs=["1-048", "1-102"])
    finally:
        mod.predict, mod.load_segmenter = real_predict, real_load

    assert called == []  # neither: 1-102 has no blot either
    assert rep["exempt_skipped"] == 1
    assert rep["skipped_no_blot"] == "1-102"


# ----------------------------------------------------------------- the editor


def test_a_page_with_no_ground_truth_opens_on_the_prediction(tmp_path):
    """And the bands it opens on are the configured column's, not kraken's. The
    model was never shown that the measure is fixed, so its x is not a claim about
    the column — where a *stored* zone matching no column is a finding worth
    keeping, a predicted one has nothing to lose by being snapped."""
    
    write_page(tmp_path, "1-102", zn.MZDIR, x0=812, y0=700, x1=2301, y1=980)
    make_scan(tmp_path, "1-102")
    st = ui.page_state("1-102", tmp_path, zc.load_config(REPO))
    assert st["keyed"] is False and st["proposal"] == "mz"
    z = st["zones"][0]
    assert (z["y0"], z["y1"]) == (700, 980)  # y is the model's
    assert (z["x0"], z["x1"]) == (
        st["columns"][0]["x0"],
        st["columns"][0]["x1"],
    )  # x is the page's


def test_ground_truth_wins_in_the_editor_too(tmp_path):
    """The precedence is the store rule, so it cannot hold in the view and not
    here — this is the surface that reads from both."""
    
    write_page(tmp_path, "1-048", zn.ZONEDIR, label="MainZone-P")
    write_page(tmp_path, "1-048", zn.MZDIR, label="RunningTitleZone")
    make_scan(tmp_path, "1-048")
    st = ui.page_state("1-048", tmp_path, zc.load_config(REPO))
    assert st["proposal"] == "" and st["zones"][0]["label"] == "MainZone-P"


def test_the_selector_shows_each_store_on_a_page_that_has_both(tmp_path):
    """The point of the selector: on a page with ground truth *and* a prediction,
    the view resolves to the human file but either can still be looked at. Without
    this, the machine's reading of the 117 pages that also have gt is unreachable
    from the one surface built for looking at zones."""
    
    cfg = zc.load_config(REPO)
    write_page(tmp_path, "1-048", zn.ZONEDIR, label="MainZone-P", y0=600, y1=900)
    write_page(tmp_path, "1-048", zn.MZDIR, label="RunningTitleZone", y0=610, y1=880)
    make_scan(tmp_path, "1-048")
    seen = {s: ui.page_state("1-048", tmp_path, cfg, store=s) for s in ui.STORES}
    assert seen["gt"]["shown"] == "gt"
    assert seen["mz"]["shown"] == "mz"
    assert seen["zones"]["shown"] == "gt"  # the view's own rule
    assert seen["gt"]["zones"][0]["label"] == "MainZone-P"
    assert seen["mz"]["zones"][0]["label"] == "RunningTitleZone"
    assert seen["mz"]["proposal"] == "mz" and seen["gt"]["proposal"] == ""
    # Presence is reported whichever store is selected, so the other one is visible
    # before you switch to it rather than discovered by switching.
    for st in seen.values():
        assert st["present"] == {"gt": 1, "mz": 1}
    # And the view's resolution is the *store rule*, not an echo of what is being
    # looked at: with `mz` pinned, `shown` is `mz` while the view still answers `gt`.
    for st in seen.values():
        assert st["view"] == "gt"


def test_an_empty_store_is_an_answer_not_an_error(tmp_path):
    """Pinning `mz` on a page nobody has predicted, or `gt` on one nobody has
    keyed, is a fair question. Both report nothing shown rather than falling back
    to the other store — a selector that silently redirected would make the two
    indistinguishable, which is the whole thing these stores are kept apart for."""
    
    cfg = zc.load_config(REPO)
    write_page(tmp_path, "1-102", zn.MZDIR)
    make_scan(tmp_path, "1-102")
    gt = ui.page_state("1-102", tmp_path, cfg, store="gt")
    assert gt["shown"] == "" and gt["zones"] == [] and gt["present"]["gt"] is None
    assert gt["present"]["mz"] == 1  # still says where to look
    assert ui.page_state("1-102", tmp_path, cfg, store="mz")["shown"] == "mz"


def test_an_unknown_store_is_refused(tmp_path):
    
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    make_scan(tmp_path, "1-048")
    with pytest.raises(ValueError, match="store must be one of"):
        ui.page_state("1-048", tmp_path, zc.load_config(REPO), store="gt/zones")


def test_the_selector_is_orthogonal_to_the_itinerary(tmp_path):
    """Two independent axes — the itinerary picks the pages, the store picks whose
    reading of them. Neighbours must not change when the store does."""
    
    cfg = zc.load_config(REPO)
    for r in ("1-048", "1-102", "1-103"):
        write_page(tmp_path, r, zn.MZDIR)
        make_scan(tmp_path, r)
    write_page(tmp_path, "1-102", zn.ZONEDIR)
    itin = ["1-048", "1-102", "1-103"]
    nav = {
        s: ui.page_state("1-102", tmp_path, cfg, itinerary=itin, store=s)
        for s in ui.STORES
    }
    for st in nav.values():
        assert (st["prev"], st["next"], st["index"], st["total"]) == (
            "1-048",
            "1-103",
            2,
            3,
        )


def test_an_undeclared_label_is_dropped_and_named(tmp_path):
    """Never mapped to something plausible: `validate_page` calls an undeclared
    label an error, so quietly renaming one would hide a model trained against a
    different class map behind a page that looks ordinary."""
    
    write_page(tmp_path, "1-102", zn.MZDIR, label="NoSuchZone")
    make_scan(tmp_path, "1-102")
    st = ui.page_state("1-102", tmp_path, zc.load_config(REPO))
    assert st["zones"] == [] and st["proposal_dropped"] == ["NoSuchZone"]


def test_the_banner_marks_a_proposal_and_only_a_proposal(tmp_path):
    """An unlabelled proposal on screen is indistinguishable from work someone had
    already done — the one confusion the two stores exist to prevent, arriving
    through the single surface that reads from both."""
    
    cfg = zc.load_config(REPO)
    write_page(tmp_path, "1-102", zn.MZDIR)
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    make_scan(tmp_path, "1-102")
    make_scan(tmp_path, "1-048")
    assert "id='proposal'" in render_html("1-102", tmp_path, cfg)
    assert "id='proposal'" not in render_html("1-048", tmp_path, cfg)


def test_the_page_list_separates_predicted_from_untouched(tmp_path):
    """Two kinds of "to do", and the difference is the whole review queue."""
    import re

    
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    write_page(tmp_path, "1-102", zn.MZDIR)
    for r in ("1-048", "1-102", "1-103"):
        make_scan(tmp_path, r)
    html = render_list_html(
        tmp_path, zc.load_config(REPO), itinerary=["1-048", "1-102", "1-103"]
    )
    states = {
        ref: re.search(
            rf'href="[^"]*\?ref={ref}".*?class="dot s-(\w+)"', html, re.S
        ).group(1)
        for ref in ("1-048", "1-102", "1-103")
    }
    assert states == {"1-048": "ok", "1-102": "proposed", "1-103": "todo"}


def test_the_page_list_counts_both_stores_per_page(tmp_path):
    """`proposed` only ever names a page with *no* ground truth, so without its own
    column a prediction sitting beside keyed work is invisible in the list — and
    "is there anything to compare against" is what sends you to a page."""
    import re

    
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    write_page(tmp_path, "1-048", zn.MZDIR)
    write_page(tmp_path, "1-102", zn.MZDIR)
    for r in ("1-048", "1-102", "1-103"):
        make_scan(tmp_path, r)
    html = render_list_html(
        tmp_path, zc.load_config(REPO), itinerary=["1-048", "1-102", "1-103"]
    )
    cells = {
        ref: re.search(
            rf'href="[^"]*\?ref={ref}".*?'
            rf"<td class='num'>(\d*)</td>\s*<td class='num dim mz'>(\d*)</td>",
            html,
            re.S,
        ).groups()
        for ref in ("1-048", "1-102", "1-103")
    }
    # gt keyed and predicted; predicted only; neither.
    assert cells["1-048"][0] and cells["1-048"][1]
    assert cells["1-102"] == ("", cells["1-048"][1])
    assert cells["1-103"] == ("", "")


def test_the_list_can_widen_to_every_scan(tmp_path):
    """The pages worth predicting are precisely the ones neither store has heard
    of, so the default view cannot show one."""
    
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    for r in ("1-048", "1-102", "1-103"):
        make_scan(tmp_path, r)
    cfg = zc.load_config(REPO)
    assert render_list_html(tmp_path, cfg).count("<tr ") == 1
    assert render_list_html(tmp_path, cfg, scope="all").count("<tr ") == 3


# ------------------------------------------------------- what a sweep leaves alone


def test_a_page_with_a_prediction_is_left_alone_unless_forced(tmp_path):
    """The mz file records the sha of the model that wrote it, and that is the
    store's only witness to which model spoke. Replacing it unasked after a retrain
    would leave nothing able to say the store had held two models' output."""
    make_scan(tmp_path, "1-048")
    write_page(tmp_path, "1-048", zn.MZDIR)
    zn.blot_dir(tmp_path).mkdir(parents=True, exist_ok=True)
    (zn.blot_dir(tmp_path) / "chukchi-1-048.png").write_bytes(b"")
    assert zn.predict_skip("1-048", tmp_path) == "already predicted"
    assert zn.predict_skip("1-048", tmp_path, force=True) == ""


def test_an_exempt_page_is_refused_even_under_force(tmp_path):
    """`force` says "replace what is there"; it does not say "this plate has a right
    answer after all". Only naming the page does that."""
    make_scan(tmp_path, "1-001")
    zn.blot_dir(tmp_path).mkdir(parents=True, exist_ok=True)
    (zn.blot_dir(tmp_path) / "chukchi-1-001.png").write_bytes(b"")
    zn.save_zones("1-001", [], tmp_path, split="exempt")
    assert zn.predict_skip("1-001", tmp_path) == "ruled not a text page"
    assert zn.predict_skip("1-001", tmp_path, force=True) == "ruled not a text page"
    assert zn.predict_skip("1-001", tmp_path, single=True) == ""


def test_a_sweep_reports_what_it_skipped_rather_than_omitting_it(tmp_path):
    make_scan(tmp_path, "1-048")
    write_page(tmp_path, "1-048", zn.MZDIR)
    assert zn.predict_skip("1-048", tmp_path) == "already predicted"
    # No blot, so even forced it is a gap in the run and says so.
    assert zn.predict_skip("1-048", tmp_path, force=True) == "no blotted raster"


# ----------------------------------------------------------------- the scoring


def frozen_split(root: Path, train: list[str], evl: list[str]):
    d = root / zn.WORKDIR
    d.mkdir(parents=True, exist_ok=True)
    for name, refs in (("train", train), ("eval", evl)):
        (d / f"{name}.lst").write_text(
            "".join(f"{zn.WORKDIR}/chukchi-{r}.xml\n" for r in refs), encoding="utf-8"
        )


def multi_page(root: Path, ref: str, store: str, zones: list[tuple[str, int, int]]):
    """A page with several zones, so a confusion matrix has something to count."""
    blocks, tags, seen = [], [], {}
    for i, (label, y0, y1) in enumerate(zones):
        if label not in seen:
            seen[label] = f"BT{len(seen) + 1}"
            tags.append(f'<OtherTag ID="{seen[label]}" LABEL="{label}"/>')
        blocks.append(
            f'<TextBlock ID="b{i}" HPOS="700" VPOS="{y0}" WIDTH="1778" '
            f'HEIGHT="{y1 - y0}" TAGREFS="{seen[label]}">'
            f'<Shape><Polygon POINTS="700 {y0} 2478 {y0} 2478 {y1} 700 {y1}"/>'
            f"</Shape></TextBlock>"
        )
    d = root / store
    d.mkdir(parents=True, exist_ok=True)
    (d / f"chukchi-{ref}.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">'
        f'<Tags>{"".join(tags)}</Tags><Layout>'
        f'<Page WIDTH="2824" HEIGHT="3897"><PrintSpace>{"".join(blocks)}'
        "</PrintSpace></Page></Layout></alto>",
        encoding="utf-8",
    )


PERM = {
    "MainZone-P": "MarginTextZone-Notes",
    "MarginTextZone-Notes": "RunningTitleZone",
    "RunningTitleZone": "MainZone-P",
}


def permuted_corpus(tmp_path: Path, refs: list[str]):
    """Ground truth, and a prediction of it with the labels consistently rotated —
    the fault the real run had, reproduced small."""
    truth = [
        ("RunningTitleZone", 600, 700),
        ("MainZone-P", 720, 1500),
        ("MarginTextZone-Notes", 1550, 2000),
    ]
    for r in refs:
        multi_page(tmp_path, r, zn.ZONEDIR, truth)
        multi_page(
            tmp_path, r, zn.MZDIR, [(PERM[lbl], y0, y1) for lbl, y0, y1 in truth]
        )


def test_score_refuses_without_the_frozen_split(tmp_path):
    """The live lists move as pages are keyed, so without the frozen ones the
    training pages cannot be told from the rest — and a blended number reads as
    better than it is. Refuse rather than substitute."""
    permuted_corpus(tmp_path, ["1-048"])
    with pytest.raises(FileNotFoundError, match="no split for this model"):
        zn.score(tmp_path, CFG)


def test_score_never_blends_the_splits(tmp_path):
    permuted_corpus(tmp_path, ["1-048", "1-052", "1-053"])
    frozen_split(tmp_path, ["1-048", "1-052"], ["1-053"])
    rep = zn.score(tmp_path, CFG)
    by = {(r["split"], r["counting"]): r for r in rep["splits"]}
    assert by[("trained-on", "as emitted")]["pages"] == 2
    assert by[("eval", "as emitted")]["pages"] == 1
    # Consistently permuted, so nothing agrees anywhere — and the permutation is
    # the same whether or not the slivers are counted, so both rows read zero.
    for counting in ("as emitted", f">={CFG['min_zone_h_px']}px"):
        assert by[("trained-on", counting)]["recall"] == 0.0
        assert by[("eval", counting)]["recall"] == 0.0


def test_an_exempt_page_is_not_scored(tmp_path):
    """A human ruled it not a text page, so it has no correct segmentation: every
    region the model draws there is spurious and nothing can offset it. Seven plates
    marked exempt mid-session put 240 predictions against zero ground truth into the
    unseen row and took its precision from 79% to 53% — which reads as the model
    degrading on new pages when what changed was the denominator."""
    multi_page(tmp_path, "1-048", zn.ZONEDIR, [("MainZone-P", 600, 900)])
    multi_page(tmp_path, "1-048", zn.MZDIR, [("MainZone-P", 600, 900)])
    # A plate: ruled exempt, so no zones — and the model covered it in guesses.
    multi_page(tmp_path, "1-083", zn.ZONEDIR, [])
    multi_page(
        tmp_path,
        "1-083",
        zn.MZDIR,
        [("MainZone-P", 100 * i, 100 * i + 80) for i in range(1, 9)],
    )
    zn.set_split("1-083", "exempt", tmp_path)
    frozen_split(tmp_path, ["1-048"], [])
    rep = zn.score(tmp_path, CFG)
    assert rep["exempt_skipped"] == "1-083"
    assert rep["pages_compared"] == 1
    by = {(r["split"], r["counting"]): r for r in rep["splits"]}
    row = by[("trained-on", f">={CFG['min_zone_h_px']}px")]
    assert row["spurious"] == 0 and row["precision"] == 100.0


def test_score_reports_both_directions(tmp_path):
    """`recall` alone cannot see over-segmentation: a model emitting every correct
    band plus fifty slivers scores identically on it, and the first model did
    exactly that — 2.5 predictions per human zone. `precision` is what falls, so
    both are reported, and the sliver-filtered row beside the raw one."""
    truth = [("RunningTitleZone", 600, 700), ("MainZone-P", 720, 1500)]
    multi_page(tmp_path, "1-048", zn.ZONEDIR, truth)
    multi_page(
        tmp_path,
        "1-048",
        zn.MZDIR,
        truth
        + [
            ("QuireMarksZone", 2000, 2007),  # a 7 px sliver
            ("QuireMarksZone", 2100, 2105),
        ],
    )  # and another
    frozen_split(tmp_path, ["1-048"], [])
    by = {(r["split"], r["counting"]): r for r in zn.score(tmp_path, CFG)["splits"]}
    raw = by[("trained-on", "as emitted")]
    kept = by[("trained-on", f">={CFG['min_zone_h_px']}px")]
    # Perfect recall either way; the slivers only ever cost precision.
    assert raw["recall"] == 100.0 and kept["recall"] == 100.0
    assert raw["pred_zones"] == 4 and kept["pred_zones"] == 2
    assert raw["precision"] == 50.0 and kept["precision"] == 100.0
    assert raw["spurious"] == 2 and kept["spurious"] == 0


def test_the_permutation_test_separates_relabelling_from_a_weak_model(tmp_path):
    """The finding that mattered: below-chance agreement plus a 1-1 map that holds
    out means the geometry was learned and only the names are wrong."""
    permuted_corpus(tmp_path, ["1-048", "1-052", "1-053"])
    frozen_split(tmp_path, ["1-048", "1-052"], ["1-053"])
    p = zn.score(tmp_path, CFG)["permutation"]
    assert p["bijective"] is True
    assert p["holds_out"] == 100.0  # derived on train, perfect on eval
    assert "MainZone-P->MarginTextZone-Notes" in p["map"]


def test_a_correct_model_is_not_reported_as_a_relabelling(tmp_path):
    """The identity is a bijection that holds out perfectly, so `bijective` alone
    cannot mean "shuffled" — without `is_identity` the *fixed* model reports its own
    correctness as the fault it just had, and `--remap-model` would happily rename
    every channel to itself."""
    truth = [("RunningTitleZone", 600, 700), ("MainZone-P", 720, 1500)]
    for r in ("1-048", "1-052"):
        multi_page(tmp_path, r, zn.ZONEDIR, truth)
        multi_page(tmp_path, r, zn.MZDIR, truth)
    frozen_split(tmp_path, ["1-048"], ["1-052"])
    p = zn.score(tmp_path, CFG)["permutation"]
    assert p["bijective"] is True and p["holds_out"] == 100.0
    assert p["is_identity"] is True
    with pytest.raises(ValueError, match="identity"):
        zn.remap_model(tmp_path, zn.DEFAULT_MODEL, commit=False, cfg=CFG)


def test_a_diffuse_error_is_not_reported_as_a_permutation(tmp_path):
    """The other half. A model that is merely wrong must not be dressed up as a
    relabelling, or `--remap-model` would rename channels on noise."""
    multi_page(
        tmp_path,
        "1-048",
        zn.ZONEDIR,
        [("MainZone-P", 600, 700), ("MainZone-P", 720, 900)],
    )
    multi_page(
        tmp_path,
        "1-048",
        zn.MZDIR,
        [("RunningTitleZone", 600, 700), ("MainZone-Other", 720, 900)],
    )
    multi_page(tmp_path, "1-052", zn.ZONEDIR, [("MainZone-P", 600, 700)])
    multi_page(tmp_path, "1-052", zn.MZDIR, [("QuireMarksZone", 600, 700)])
    frozen_split(tmp_path, ["1-048"], ["1-052"])
    p = zn.score(tmp_path, CFG)["permutation"]
    # One truth label, three different predictions: the map cannot hold out.
    assert p["holds_out"] < zn.MIN_HOLDOUT


def test_remap_refuses_when_the_evidence_is_thin(tmp_path):
    """`--remap-model` writes a model file, so its refusals are the safety. A
    non-bijective or poorly-holding map must not reach the weights."""
    multi_page(
        tmp_path,
        "1-048",
        zn.ZONEDIR,
        [("MainZone-P", 600, 700), ("RunningTitleZone", 720, 900)],
    )
    multi_page(
        tmp_path,
        "1-048",
        zn.MZDIR,
        [("MainZone-Other", 600, 700), ("MainZone-Other", 720, 900)],
    )
    frozen_split(tmp_path, ["1-048"], [])
    with pytest.raises(ValueError, match="refusing to rewrite"):
        zn.remap_model(tmp_path, zn.DEFAULT_MODEL, commit=False, cfg=CFG)


# ------------------------------------------------------------ un-keying a page


def test_a_page_keyed_then_emptied_can_only_be_withdrawn(tmp_path):
    """The corner case the store could not express. `save_zones` refuses an empty
    save, so keying a page and then deleting every zone on it left no way to say
    "this should not be here" — the only reachable states were "keyed and holds
    nothing", which already means something else, and marking it exempt, which
    claims it is a plate."""
    make_scan(tmp_path, "1-048")
    zn.save_zones(
        "1-048",
        [{"label": "MainZone-P", "x0": 700, "y0": 600, "x1": 2478, "y1": 900}],
        tmp_path,
    )
    assert zn.has_zones("1-048", tmp_path)
    with pytest.raises(ValueError, match="delete"):
        zn.save_zones("1-048", [], tmp_path)  # and the refusal names the way out
    rep = zn.delete_zones("1-048", tmp_path, commit=True)
    assert rep["zones"] == 1 and not zn.has_zones("1-048", tmp_path)


def test_deleting_takes_the_marks_with_it(tmp_path):
    """A ref left in `_train.lst` naming a file that no longer exists is a dangling
    claim of exactly the kind `harness figures` exists to catch elsewhere."""
    make_scan(tmp_path, "1-048")
    zn.save_zones(
        "1-048",
        [{"label": "MainZone-P", "x0": 700, "y0": 600, "x1": 2478, "y1": 900}],
        tmp_path,
        split="eval",
    )
    zn.set_exempt("1-048", ["title-first"], tmp_path)
    zn.set_ink_exempt("1-048", [{"y0": 10, "y1": 20, "note": "smudge"}], tmp_path)
    zn.delete_zones("1-048", tmp_path, commit=True)
    assert zn.load_splits(tmp_path).get("1-048") is None
    assert zn.load_exempt(tmp_path).get("1-048") in (None, [])
    assert zn.load_ink_exempt(tmp_path).get("1-048") in (None, [])


def test_deleting_is_previewed_journalled_and_recoverable(tmp_path):
    """Same durability shape as a save, because this is the more dangerous
    direction: `.prev` one deep, the journal permanent, `--commit` required."""
    make_scan(tmp_path, "1-048")
    zn.save_zones(
        "1-048",
        [{"label": "MainZone-P", "x0": 700, "y0": 600, "x1": 2478, "y1": 900}],
        tmp_path,
    )
    assert zn.delete_zones("1-048", tmp_path)["committed"] is False
    assert zn.has_zones("1-048", tmp_path)  # preview wrote nothing
    zn.delete_zones("1-048", tmp_path, commit=True)
    assert (tmp_path / zn.ZONEDIR / "chukchi-1-048.xml.prev").exists()
    log = (tmp_path / zn.ZONEDIR / zn.JOURNAL).read_text(encoding="utf-8")
    assert '"deleted_at"' in log and '"ref": "1-048"' in log
    # Deleting what is not there is a statement, not an error.
    assert zn.delete_zones("1-048", tmp_path, commit=True)["exists"] is False


# --------------------------------------------------------- paragraph splitting


def ruled_page(root: Path, ref: str, lines, w=2824, h=3897):
    """A raster of black bars standing in for lines of type.

    `lines` is `(y, indent, width)` in page coordinates relative to the column,
    so a test can put a paragraph opening exactly where it means to.
    """
    from PIL import Image, ImageDraw

    d = root / "scans"
    d.mkdir(parents=True, exist_ok=True)
    im = Image.new("L", (w, h), 255)
    dr = ImageDraw.Draw(im)
    for y, ind, wid in lines:
        dr.rectangle([700 + ind, y, 700 + ind + wid, y + 40], fill=0)
    im.save(d / f"chukchi-{ref}.png")


def test_an_indented_line_inside_a_zone_is_a_paragraph_start(tmp_path):
    """The check the segmenter cannot do: two abutting MainZone-P rectangles
    rasterize to one target, so the boundary is destroyed before the network sees
    it. 42% of gt boundaries are same-label, so this is nearly half of them."""
    ruled_page(
        tmp_path,
        "1-048",
        [
            (600, 120, 1600),  # the zone's own first line — never reported
            (700, 15, 1600),  # continuing
            (800, 122, 1600),  # a new paragraph
            (900, 15, 1600),
        ],
    )
    multi_page(tmp_path, "1-048", zn.ZONEDIR, [("MainZone-P", 580, 1000)])
    hits = zn.paragraph_starts("1-048", tmp_path, CFG)
    assert len(hits) == 1
    assert hits[0]["zone"] == 1 and hits[0]["index"] == 3  # both 1-based
    # `indent` is measured **against the margin the page's body sets**, not against
    # the column edge — so a line drawn 122 px in, over body lines at 15 px, reads
    # ~107 rather than 122. That is the unit, and it is what makes the check
    # independent of the column anchor and of the gutter beside a figure.
    assert hits[0]["y"] == 800
    assert 100 <= hits[0]["indent"] <= 115


def test_a_speck_in_the_margin_is_not_a_line(tmp_path):
    """Five of the first twenty hits were 4-21 px specks far to the right. A run
    that narrow is dirt, and `min_line_w_px` is why it no longer reports."""
    ruled_page(tmp_path, "1-048", [(600, 120, 1600), (700, 15, 1600), (800, 1400, 12)])
    multi_page(tmp_path, "1-048", zn.ZONEDIR, [("MainZone-P", 580, 900)])
    assert zn.paragraph_starts("1-048", tmp_path, CFG) == []


def test_only_the_configured_labels_are_examined(tmp_path):
    """An indent means something else inside a footnote or a running title."""
    ruled_page(tmp_path, "1-048", [(600, 120, 1600), (700, 15, 1600), (800, 122, 1600)])
    multi_page(tmp_path, "1-048", zn.ZONEDIR, [("MarginTextZone-Notes", 580, 900)])
    assert zn.paragraph_starts("1-048", tmp_path, CFG) == []


def test_splitting_cuts_at_the_opening_line(tmp_path):
    """The new zone begins where its first line begins — which is how the editor
    draws one, and how gt records its 561 abutting pairs."""
    ruled_page(tmp_path, "1-048", [(600, 120, 1600), (700, 15, 1600), (800, 122, 1600)])
    zones = [{"label": "MainZone-P", "x0": 700, "x1": 2478, "y0": 580, "y1": 900}]
    out = zn.split_at_paragraphs(zones, "1-048", tmp_path, CFG)
    assert [(z["y0"], z["y1"]) for z in out] == [(580, 800), (800, 900)]
    assert all(z["label"] == "MainZone-P" and z["x0"] == 700 for z in out)


def test_a_split_piece_carries_that_it_opens_a_paragraph(tmp_path):
    """**The piece's own witness, because the label is not one.** Every piece of a
    split zone inherits the parent's label, so the label says what the *zone* was
    and cannot say which pieces begin a paragraph. `paragraph_open` does, and it is
    true of exactly the pieces that begin at a measured cut.

    **It is belt-and-braces today, and that is worth stating plainly rather than
    dressed up.** `paragraph_split.labels` lists `MainZone-P` alone, so the only
    zones ever cut are ones whose label already opens a paragraph, and
    `tei generate` would reach the same answer from the label. What this buys is
    that it would keep reaching it if that list grew — a `MainZone-Continued`
    holding two paragraphs would otherwise be run together by a merge reading
    labels alone. The list is config a human edits, and the generator's
    correctness should not be a property of a value in a JSON file."""
    ruled_page(tmp_path, "1-048", [(600, 120, 1600), (700, 15, 1600), (800, 122, 1600)])
    zones = [{"label": "MainZone-P", "x0": 700, "x1": 2478, "y0": 580, "y1": 900}]
    out = zn.split_at_paragraphs(zones, "1-048", tmp_path, CFG)
    assert [z["paragraph_open"] for z in out] == [False, True]


def test_an_uncut_zone_makes_no_claim_either_way(tmp_path):
    """Returned as it came, so the key is absent rather than False. There was no
    measurement here, and a caller reading `.get("paragraph_open")` gets the same
    answer — the difference matters only to anyone tempted to read the key as "the
    raster says this is a continuation", which it never says."""
    ruled_page(tmp_path, "1-048", [(600, 120, 1600), (700, 15, 1600)])
    zones = [{"label": "MainZone-P", "x0": 700, "x1": 2478, "y0": 580, "y1": 800}]
    assert "paragraph_open" not in zn.split_at_paragraphs(
        zones, "1-048", tmp_path, CFG)[0]


def test_a_sliver_folds_into_a_neighbour_of_the_same_label(tmp_path):
    """A cut lands at the top of the opening line, so leading whitespace is left as
    its own band — invisible in the editor and a `min-height` error the moment it is
    saved. `down` gives it to the paragraph below."""
    segs = [[100, 118, "MainZone-P"], [118, 600, "MainZone-P"]]
    assert zn._consolidate(segs, 30, "down") == [[100, 600, "MainZone-P"]]
    segs = [[100, 580, "MainZone-P"], [580, 598, "MainZone-P"]]
    assert zn._consolidate(segs, 30, "up") == [[100, 598, "MainZone-P"]]


def test_a_sliver_never_folds_across_a_label(tmp_path):
    """Same label always. Within one zone's split it holds by construction, which is
    why it is asserted — applied to a decoder's output, where adjacent bands really
    do differ, merging a sliver sideways would silently retype a strip of page."""
    segs = [[100, 118, "MainZone-P"], [118, 600, "MarginTextZone-Notes"]]
    assert zn._consolidate(segs, 30, "down") == segs  # left standing, reported
    # With a match on the far side only, preference gives way to correctness.
    segs = [
        [100, 560, "MainZone-P"],
        [560, 578, "MainZone-P"],
        [578, 900, "MarginTextZone-Notes"],
    ]
    assert zn._consolidate(segs, 30, "down") == [
        [100, 578, "MainZone-P"],
        [578, 900, "MarginTextZone-Notes"],
    ]


def test_a_zone_with_one_paragraph_is_returned_unchanged(tmp_path):
    ruled_page(tmp_path, "1-048", [(600, 120, 1600), (700, 15, 1600)])
    zones = [{"label": "MainZone-P", "x0": 700, "x1": 2478, "y0": 580, "y1": 800}]
    assert zn.split_at_paragraphs(zones, "1-048", tmp_path, CFG) == zones


# ------------------------------------------------------------ the DP decoder


def test_the_decoder_cannot_emit_a_sliver_or_an_overlap(tmp_path):
    """The mechanical rules built in rather than checked afterwards. One label per
    row makes an overlap unrepresentable; the minimum duration makes a sliver
    unrepresentable. The blob decode produces both and has them filtered out."""
    import numpy as np

    n, k = 300, 3
    rows = np.full((n, k), 0.01)
    rows[0:100, 0] = 0.9  # a real band
    rows[100:104, 1] = 0.9  # a 4-row sliver: must not survive
    rows[104:300, 2] = 0.9  # another real band
    rows[50:60, 2] = 0.9  # class 2 also confident inside class 0's band
    segs = zn._segmental_decode(rows, min_len=20)
    labelled = [s for s in segs if s[2] is not None]
    assert all(j - i >= 20 for i, j, _ in labelled)  # no sliver
    # A partition: segments tile the page in order and never overlap.
    assert segs[0][0] == 0 and segs[-1][1] == n
    for a, b in pairwise(segs):
        assert a[1] == b[0]


def test_the_decoder_merges_a_fragmented_band(tmp_path):
    """Most of the residual precision gap is one true band arriving as two. Adjacent
    runs of one label are one band, so the DP needs no rule against splitting."""
    import numpy as np

    rows = np.full((200, 2), 0.01)
    rows[0:90, 0] = 0.9
    rows[90:95, 0] = 0.55  # a dip in confidence, not a boundary
    rows[95:200, 0] = 0.9
    segs = [s for s in zn._segmental_decode(rows, min_len=10) if s[2] is not None]
    assert len(segs) == 1 and segs[0] == (0, 200, 0)


def test_the_decoder_does_not_enforce_the_order_rules(tmp_path):
    """The line this design turns on. `rank-monotone` and friends are *warnings* —
    the book breaks its own conventions, and a page that breaks them is the
    interesting page. A decoder that could not emit one would make the warning
    unfalsifiable and silently normalise exactly what it exists to surface. So a
    footnotes-then-title page must still decode as what it is."""
    import numpy as np

    rows = np.full((200, 2), 0.01)
    rows[0:100, 1] = 0.9  # class 1 on top...
    rows[100:200, 0] = 0.9  # ...class 0 below, whatever their ranks
    segs = [s for s in zn._segmental_decode(rows, min_len=10) if s[2] is not None]
    assert [s[2] for s in segs] == [1, 0]


# ------------------------------------------------------------ the train merge


def test_a_train_merge_folds_the_training_copy_and_not_the_store(tmp_path):
    """`train_merges` narrows what the *segmenter* is asked to learn. The keyed
    file keeps the distinction, because a human drew it and it is evidence — the
    fold is a statement about a model's capacity, not about the book."""

    multi_page(
        tmp_path,
        "1-048",
        zn.ZONEDIR,
        [("MainZone-Quote", 600, 900), ("MainZone-P", 950, 1400)],
    )
    (tmp_path / zn.BLOTDIR).mkdir(parents=True, exist_ok=True)
    (tmp_path / zn.BLOTDIR / "chukchi-1-048.png").write_bytes(b"x")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    import json

    cfg = json.loads((REPO / "data/zones_config.json").read_text(encoding="utf-8"))
    (tmp_path / "data/zones_config.json").write_text(json.dumps(cfg), encoding="utf-8")

    rep = zn.assemble(tmp_path)
    assert rep["merged"] == "MainZone-Quote->MainZone-Other"
    assert rep["merged_pages"] == 1
    assert "MainZone-Quote" not in rep["classes"]

    # The training copy is folded...
    train = (tmp_path / zn.WORKDIR / "chukchi-1-048.xml").read_text(encoding="utf-8")
    assert "MainZone-Quote" not in train and "MainZone-Other" in train
    # ...and is a real file, never a link back into the store: writing through one
    # would edit the ground truth, which is the failure this repo already paid for.
    assert not (tmp_path / zn.WORKDIR / "chukchi-1-048.xml").is_symlink()
    # ...while the keyed file still says what the editor was told.
    assert zn.read_zones("1-048", tmp_path)[0]["label"] == "MainZone-Quote"


def test_no_merge_declared_keeps_assemble_on_symlinks(tmp_path):
    """The fold is opt-in. With none declared the training set stays the symlink
    farm it was, so the cheap path is not paid for by pages nobody folds."""
    import json

    multi_page(tmp_path, "1-048", zn.ZONEDIR, [("MainZone-P", 600, 900)])
    (tmp_path / zn.BLOTDIR).mkdir(parents=True, exist_ok=True)
    (tmp_path / zn.BLOTDIR / "chukchi-1-048.png").write_bytes(b"x")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    cfg = json.loads((REPO / "data/zones_config.json").read_text(encoding="utf-8"))
    cfg.pop("train_merges", None)
    (tmp_path / "data/zones_config.json").write_text(json.dumps(cfg), encoding="utf-8")
    rep = zn.assemble(tmp_path)
    assert rep["merged"] == "" and rep["merged_pages"] == 0
    assert (tmp_path / zn.WORKDIR / "chukchi-1-048.xml").is_symlink()


# --------------------------------------------------------------- the ignores


def test_the_derived_stores_are_ignored_and_gt_is_not():
    """The one that has to be a test rather than a reading of the file.

    `.gitignore`'s `zones/` needs its leading slash: unanchored, the pattern matches
    a directory of that name at any depth and silently swallows the **tracked**
    `gt/zones/`, so a newly keyed page would never be added and `git status` would
    say nothing about it. That is the same shape as the loss this repo has already
    paid for — a file's disposition decided somewhere other than where anyone looks.
    Asked of git rather than of the text, because only git knows what the pattern
    means.
    """
    import subprocess

    def ignored(p):
        return (
            subprocess.run(
                ["git", "check-ignore", "-q", p], cwd=REPO, capture_output=True
            ).returncode
            == 0
        )

    assert ignored("mz/zones/chukchi-1-048.xml")
    assert ignored("zones/chukchi-1-048.xml")
    assert not ignored("gt/zones/chukchi-9-999.xml")
    assert not ignored("gt/zones/_train.lst")


def test_predict_refuses_to_write_provenance_it_does_not_have(tmp_path):
    """A `sha256: ""` in the file is provenance that is present, well-formed and
    says nothing — which reads as recorded and is therefore worse than absent."""
    (tmp_path / zn.BLOTDIR).mkdir(parents=True)
    (tmp_path / zn.BLOTDIR / "chukchi-1-048.png").write_bytes(b"")
    with pytest.raises(ValueError, match="sha256"):
        zn.predict("1-048", tmp_path, net=object(), sha="")


def test_load_segmenter_names_the_default_when_it_is_absent(tmp_path):
    """The error a fresh clone gets. It has to name the path and the way to fill
    it, since nothing else in the repo produces that file."""
    with pytest.raises(FileNotFoundError, match="zones-seg"):
        zn.load_segmenter(zn.DEFAULT_MODEL, tmp_path)


# ------------------------------------------------------------ the eval re-mark


def _mk(root, ref, store, labels=("MainZone-P",), y=600):
    make_scan(root, ref)
    write_page(root, ref, store)
    return ref


def test_remark_eval_never_touches_a_human_marked_page(tmp_path):
    """A page a human put in the held-out set is a judgement. Re-deriving the whole
    split would overwrite every one of them silently — the fault `--assemble` was
    already stopped from committing against the frozen lists."""
    for r in ("1-001", "1-002", "1-003", "1-004"):
        make_scan(tmp_path, r)
        zn.save_zones(
            r,
            [{"label": "MainZone-P", "x0": 0, "y0": 600, "x1": 100, "y1": 900}],
            tmp_path,
            split="train",
        )
    zn.set_split("1-001", "eval", tmp_path)
    zn.set_split("1-002", "exempt", tmp_path)
    zn.remark_eval(tmp_path, 1.0, commit=True)
    s = zn.load_splits(tmp_path)
    assert s["1-001"] == "eval" and s["1-002"] == "exempt"
    # Everything that *was* train moved; nothing else did.
    assert s["1-003"] == "eval" and s["1-004"] == "eval"


def test_remark_eval_reports_without_writing_unless_committed(tmp_path):
    for r in ("1-001", "1-002"):
        make_scan(tmp_path, r)
        zn.save_zones(
            r,
            [{"label": "MainZone-P", "x0": 0, "y0": 600, "x1": 100, "y1": 900}],
            tmp_path,
            split="train",
        )
    rep = zn.remark_eval(tmp_path, 0.5)
    assert rep["moved"] == 1 and rep["committed"] is False
    assert all(v == "train" for v in zn.load_splits(tmp_path).values())


def test_remark_eval_quotas_are_per_part(tmp_path):
    """An eval set drawn globally lands where the pages are. By page count this
    corpus is three volumes keyed in very different ways, so a model measured on
    one of them says nothing about reuse on the others."""
    for part, n in (("1", 10), ("2", 10)):
        for i in range(1, n + 1):
            r = f"{part}-{i:03d}"
            make_scan(tmp_path, r)
            zn.save_zones(
                r,
                [{"label": "MainZone-P", "x0": 0, "y0": 600, "x1": 100, "y1": 900}],
                tmp_path,
                split="train",
            )
    rep = zn.remark_eval(tmp_path, 0.2)
    assert {p["part"]: p["quota"] for p in rep["parts"]} == {"1": 2, "2": 2}


def test_independent_compares_the_two_stores_not_one_of_them_twice(tmp_path):
    """`read_zones`'s third positional is `with_points`, so passing the store there
    reads gt both times and calls every page identical. The guard against the
    one-witness comparison had the one-witness comparison in it."""
    make_scan(tmp_path, "1-048")
    zn.save_zones(
        "1-048",
        [{"label": "MainZone-P", "x0": 0, "y0": 600, "x1": 100, "y1": 900}],
        tmp_path,
        split="train",
    )
    assert zn._independent("1-048", tmp_path) is True  # no prediction at all
    # Identical where it counts. x is not compared and must not be: both stores take
    # it from the same configured column, so a difference there is never a human's
    # ruling — the y-pair and the label are the whole content of a band.
    write_page(tmp_path, "1-048", zn.MZDIR, y0=600, y1=900)
    assert zn._independent("1-048", tmp_path) is False
    write_page(tmp_path, "1-048", zn.MZDIR, y0=600, y1=1500)
    assert zn._independent("1-048", tmp_path) is True


def test_spread_takes_a_sample_not_a_prefix(tmp_path):
    """Held-out pages off the front of a list are a contiguous run of the book, and
    a contiguous run is one chapter, one layout, one typesetter's habits."""
    got = zn._spread(list(range(100)), 4)
    assert got == [0, 25, 50, 75]
    assert zn._spread([1, 2], 5) == [1, 2] and zn._spread([1, 2], 0) == []
