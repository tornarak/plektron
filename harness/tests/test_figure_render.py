"""Placing a figure in the reading view: the column, the match, and the caption.

Four things are held here.

**The caption reaches the reader.** `el_figure` used to build a `[fig. N]` chip
and never call `inline`, so the `<figDesc>` the generator had gone to
the caption store to fetch was dropped on the floor of every page.

**No geometry goes into the rendered HTML.** `stores.render` is cached on the
TEI file's bytes alone, so a box baked into that HTML would let a corrected
`gt/fig/` serve stale placement out of the cache with nothing to signal it. The
pictures are joined at the route instead, off a key that names the figure
stores.

**A figure that cannot be resolved shows as a gap, never as a picture.** Falling
back to the next unused crop would put a wrong picture under a right caption,
which reads as correct and is invisible.

**And the join reaches the reader in the served bytes.** It was assembled by
`edition.js` once, off a `STATE.figs` payload, which turned the cache argument
above into a no-script one: the pictures were the single part of the edition a
reader without JavaScript never saw.
"""
from __future__ import annotations

from pathlib import Path

from conftest import write_captions

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _fig_alto(tmp_path: Path, ref: str, blocks) -> Path:
    p = tmp_path / "gt" / "fig" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<TextBlock ID="{i}" TAGREFS="{"BT77" if lab.endswith("FigDesc") else "BT78"}"'
        f' HPOS="{x}.0" VPOS="{y}.0" WIDTH="{w}.0" HEIGHT="{h}.0"/>'
        for i, lab, x, y, w, h in blocks)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
        f"<PrintSpace>{body}</PrintSpace></Page></Layout><Tags>"
        '<OtherTag ID="BT77" TYPE="type" LABEL="GraphicZone-FigDesc"/>'
        '<OtherTag ID="BT78" TYPE="type" LABEL="GraphicZone"/>'
        "</Tags></alto>", encoding="utf-8")
    return p


def _zones_alto(tmp_path: Path, ref: str, x0: int, x1: int) -> Path:
    """A zone ALTO whose bands all share one x-pair, as every keyed page does."""
    p = tmp_path / "gt" / "zones" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    bands = "".join(
        f'<TextBlock ID="mz_{ref}_{i:03d}" TAGREFS="BT1" HPOS="{x0}.0"'
        f' VPOS="{600 + i * 400}.0" WIDTH="{x1 - x0}.0" HEIGHT="380.0"/>'
        for i in (1, 2, 3))
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
        f"<PrintSpace>{bands}</PrintSpace></Page></Layout><Tags>"
        '<OtherTag ID="BT1" TYPE="type" LABEL="MainZone-P"/>'
        "</Tags></alto>", encoding="utf-8")
    return p


def _readings(tmp_path: Path, blocks: dict[str, str]) -> None:
    write_captions(tmp_path, blocks)


def _tei(tmp_path: Path, ref: str, body: str) -> Path:
    p = tmp_path / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader/><text><body><pb/>{body}'
        "</body></text></TEI>", encoding="utf-8")
    return p


# -- the caption --------------------------------------------------------------

def test_the_caption_reaches_the_reader(tmp_path):
    from harness.tei_html import render
    p = _tei(tmp_path, "1-086",
             '<figure n="2"><figDesc>Fig. 2. Bundle of Leaf-Tobacco.</figDesc>'
             "</figure>")
    html = render(p)["html"]
    assert "<figcaption>Fig. 2. Bundle of Leaf-Tobacco.</figcaption>" in html
    assert 'data-figure="2"' in html and 'data-i="0"' in html


def test_a_captionless_figure_renders_without_an_empty_figcaption(tmp_path):
    """`3-006`: an empty `<figcaption>` would assert a caption exists and is lost."""
    from harness.tei_html import render
    html = render(_tei(tmp_path, "3-006", "<figure/>"))["html"]
    assert "<figure" in html and "figcaption" not in html


def test_the_rendered_html_carries_no_geometry(tmp_path):
    """The cache argument, asserted rather than trusted.

    `stores.render` keys on the TEI bytes, so anything positional in here would
    outlive a correction to `gt/fig/`.
    """
    from harness.tei_html import render
    p = _tei(tmp_path, "1-086",
             '<figure n="2"><figDesc>Fig. 2. A thing.</figDesc></figure>')
    html = render(p)["html"]
    for leak in ("aspect-ratio", "HPOS", "left:", "top:", "width:"):
        assert leak not in html, f"{leak!r} is geometry and belongs at the route"


def test_render_reports_a_handle_per_figure(tmp_path):
    from harness.tei_html import render
    p = _tei(tmp_path, "1-207",
             '<figure n="87"><figDesc>Fig. 87.</figDesc></figure>'
             "<figure/>")
    assert render(p)["figures"] == [{"n": "87", "i": 0}, {"n": "", "i": 1}]


# -- the column ---------------------------------------------------------------

def test_the_column_comes_from_the_zones_and_opens_no_raster(tmp_path, monkeypatch):
    """719 keyed pages share one x-pair per page, so no ink has to be measured."""
    import PIL.Image

    from harness.figures import layout

    def boom(*a, **k):
        raise AssertionError("layout must not open a raster")

    monkeypatch.setattr(PIL.Image, "open", boom)

    _fig_alto(tmp_path, "1-086", [
        ("fig_1-086_001", "GraphicZone", 866, 1352, 580, 1327),
        ("fig_1-086_002", "GraphicZone-FigDesc", 860, 2700, 600, 96)])
    _zones_alto(tmp_path, "1-086", 836, 2614)
    _readings(tmp_path, {"1-086|002": "Fig. 2. Bundle of Leaf-Tobacco."})

    got = layout("1-086", tmp_path)
    assert got["source"] == "zones"
    assert got["column"] == {"x0": 836, "x1": 2614, "measure": 1778}
    f = got["figures"][0]
    assert f["side"] == "left", "the box sits in the left third of the measure"
    assert 0.32 < f["width_frac"] < 0.33


def test_a_page_with_no_zones_gets_no_side(tmp_path):
    """A plate has no prose to wrap, and the rule keys on zones, not plate-hood."""
    from harness.figures import layout
    _fig_alto(tmp_path, "1-049", [
        ("fig_1-049_001", "GraphicZone", 400, 500, 1800, 1200)])
    _readings(tmp_path, {})

    got = layout("1-049", tmp_path)
    assert got["source"] == "none" and got["column"] is None
    assert "side" not in got["figures"][0]


def test_a_box_overrunning_the_column_is_clamped_and_flagged(tmp_path):
    """22 boxes corpus-wide run outside the measure. A negative gutter would
    otherwise read as hugging the opposite side."""
    from harness.figures import layout
    _fig_alto(tmp_path, "1-999", [
        ("fig_1-999_001", "GraphicZone", 700, 900, 2000, 600)])
    _zones_alto(tmp_path, "1-999", 836, 2614)
    _readings(tmp_path, {})

    f = layout("1-999", tmp_path)["figures"][0]
    assert f["overflows"] is True
    assert f["width_frac"] <= 1.0
    assert f["side"] == "full"


def test_each_picture_of_a_group_keeps_its_own_width(tmp_path):
    """Written from `2-085`'s fig. 253: a 304 px part beside a 1002 px one under a
    single caption.

    `figure_boxes` folds them into one group whose `box` is their union, and
    `write_crops` cuts one image per box — so a renderer taking its size from the
    group draws the narrow part at the union's width. Measured over this store that
    is 24 of the 32 parts in 16 multi-part groups, worst x3.95 here. The union is
    still the group's own `width_frac`, because the figure floats as one block; it
    is just not any part's size.
    """
    from harness.figures import layout
    _fig_alto(tmp_path, "1-085", [
        ("fig_1-085_001", "GraphicZone", 500, 600, 304, 400),
        ("fig_1-085_002", "GraphicZone", 900, 600, 1002, 400),
        ("fig_1-085_003", "GraphicZone-FigDesc", 500, 1100, 1402, 80)])
    _zones_alto(tmp_path, "1-085", 400, 2178)
    _readings(tmp_path, {"1-085|003": "Fig. 253. — a, b."})

    f = layout("1-085", tmp_path)["figures"][0]
    parts = {p["zone_id"]: p["width_frac"] for p in f["parts"]}
    assert len(parts) == 2
    assert parts["fig_1-085_001"] < parts["fig_1-085_002"] < f["width_frac"]
    # The narrow part is not drawn at the group's width, which is the whole point.
    assert round(f["width_frac"] / parts["fig_1-085_001"], 2) > 3.0


def test_a_single_picture_figure_has_one_part_matching_the_group(tmp_path):
    """The ordinary case must not have moved: 382 of 414 pictures stand alone, and
    for them the group's box *is* the part's box."""
    from harness.figures import layout
    _fig_alto(tmp_path, "1-086", [
        ("fig_1-086_001", "GraphicZone", 836, 600, 900, 400),
        ("fig_1-086_002", "GraphicZone-FigDesc", 836, 1020, 900, 80)])
    _zones_alto(tmp_path, "1-086", 836, 2614)
    _readings(tmp_path, {"1-086|002": "Fig. 87. — A drum."})

    f = layout("1-086", tmp_path)["figures"][0]
    assert [p["width_frac"] for p in f["parts"]] == [f["width_frac"]]


# -- the match ----------------------------------------------------------------

def _fig(n, key="001"):
    return {"key": key, "n": n, "zone_ids": [f"fig_1-000_{key}"],
            "caption_zone": "", "caption": "", "box": (0, 0, 10, 10), "y": 0}


def test_a_figure_matches_on_its_printed_number(tmp_path):
    from harness.figures import resolve_figures
    got = resolve_figures([{"n": "87", "i": 0}], [_fig("86"), _fig("87", "003")])
    assert got[0]["figure"]["key"] == "003"


def test_an_unnumbered_figure_matches_by_document_order(tmp_path):
    """Ten figures print no number; the generator gives those no attribute."""
    from harness.figures import resolve_figures
    figs = [_fig("87", "001"), _fig(None, "002")]
    got = resolve_figures([{"n": "87", "i": 0}, {"n": "", "i": 1}], figs)
    assert got[0]["figure"]["key"] == "001"
    assert got[1]["figure"]["key"] == "002"


def test_an_unmatched_figure_resolves_to_nothing_and_says_why(tmp_path):
    """Never the next unused crop: a wrong picture under a right caption reads
    as correct, which is the one failure that cannot be seen."""
    from harness.figures import resolve_figures
    got = resolve_figures([{"n": "99", "i": 0}], [_fig("87")])
    assert got[0]["figure"] is None
    assert "no figure with this number" in got[0]["why"]


def test_a_duplicated_number_refuses_rather_than_breaking_the_tie(tmp_path):
    """No page has two figures with one number today. If one ever does, that is
    a store defect and picking the first would hide it."""
    from harness.figures import resolve_figures
    got = resolve_figures([{"n": "87", "i": 0}],
                          [_fig("87", "001"), _fig("87", "002")])
    assert got[0]["figure"] is None
    assert "share n=87" in got[0]["why"]


def test_every_picture_of_a_shared_caption_is_offered(tmp_path):
    """Fig. 87's parts a,b and c are two boxes under one caption; both show."""
    from harness.figures import resolve_figures
    f = _fig("87")
    f["zone_ids"] = ["fig_1-207_001", "fig_1-207_002"]
    got = resolve_figures([{"n": "87", "i": 0}], [f])
    assert len(got[0]["figure"]["zone_ids"]) == 2


def test_two_unnumbered_figures_refuse_rather_than_pair_off_in_order(tmp_path):
    """Document order is not page order once a figure has been moved.

    The collation contract asks a collator to move each figure to the sentence
    that refers to it, so the order of `<figure>` in the file stops matching the
    order of boxes down the page. With one numberless figure that cannot bite;
    with two, pairing them off by position is a guess wearing the clothes of a
    rule. This book never has two — another might, which is the point.
    """
    from harness.figures import resolve_figures
    figs = [_fig(None, "001"), _fig(None, "002")]
    got = resolve_figures([{"n": "", "i": 0}, {"n": "", "i": 1}], figs)
    assert [r["figure"] for r in got] == [None, None]
    assert "print no number" in got[0]["why"]


def _config(tmp_path: Path, **figures) -> None:
    """The real config with `figures` overridden.

    Built from the shipped file rather than from a stub, because `load_config`
    validates the whole document — a minimal `{"figures": …}` raises
    `ConfigError`, and since that subclasses `ValueError` a stub would be
    swallowed by the fallback and the test would pass while proving nothing.
    """
    import json
    real = json.loads(Path("config/zones.json").read_text(encoding="utf-8"))
    real["figures"] = {**real["figures"], **figures}
    d = tmp_path / "config"
    d.mkdir(parents=True, exist_ok=True)
    (d / "zones.json").write_text(json.dumps(real), encoding="utf-8")


def test_the_float_threshold_comes_from_the_book_config(tmp_path):
    """It is a fact about how one book sets its pictures, not about pictures.

    This pipeline is meant for more than one book, so a number tuned on Bogoras
    belongs in that book's config and not in the module.
    """
    from harness.figures import layout
    _fig_alto(tmp_path, "1-086", [
        ("fig_1-086_001", "GraphicZone", 866, 1352, 580, 1327)])
    _zones_alto(tmp_path, "1-086", 836, 2614)
    _readings(tmp_path, {})

    # A third of the measure left over, so the 580 px box floats.
    _config(tmp_path, float_min_residual=0.33)
    assert layout("1-086", tmp_path)["figures"][0]["side"] == "left"

    # A book that never wraps prose round a picture sets the threshold past 1.
    _config(tmp_path, float_min_residual=1.01)
    assert layout("1-086", tmp_path)["figures"][0]["side"] == "full"

    # And one that wraps round almost anything sets it near 0.
    _config(tmp_path, float_min_residual=0.01)
    assert layout("1-086", tmp_path)["figures"][0]["side"] == "left"


# -- the served page ----------------------------------------------------------
#
# **The join reaches the reader in the served bytes, not in a script.** The
# pictures and the cross-reference links were once assembled by `edition.js` off
# a `STATE.figs` / `STATE.figrefs` payload, which made them the one part of the
# edition a reader with no script never saw: an adjudicated caption over a blank
# space, and a reference that was a dotted underline pointing nowhere. The cache
# argument the renderer's silence rests on is untouched — `stores.render` still
# keys on the TEI bytes alone, and the splice below happens per request.

def _serve(html: str, figs=(), refs=(), notes=()) -> dict:
    from harness.web.edition import _hang_pictures
    return _hang_pictures(
        {"html": html, "notes": [{"n": str(i + 1), "i": i + 1, "html": h}
                                 for i, h in enumerate(notes)]},
        list(figs), list(refs))


def _served(html: str, figs=(), refs=()) -> str:
    return _serve(html, figs, refs)["html"]


def _fig_row(i=0, n="2", crops=(("001", 1.0),), side="full", width=1.0):
    return {"i": i, "n": n, "why": "",
            "crops": [{"url": f"/edition/fig/1-086/{k}.png", "width": w}
                      for k, w in crops],
            "side": side, "width": width}


def _rendered(n="2", i=0) -> str:
    """What `el_figure` writes, which is what the splice has to find."""
    return (f'<figure class="figure" data-figure="{n}" data-i="{i}">'
            "<figcaption>Fig. 2. A thing.</figcaption></figure>")


def test_the_picture_is_in_the_served_html(tmp_path):
    got = _served(_rendered(), [_fig_row()])
    assert 'src=\'/edition/fig/1-086/001.png\'' in got
    assert "figure-plates" in got
    # The caption is still the renderer's, and still after the picture.
    assert got.index("001.png") < got.index("<figcaption>")


def test_the_float_is_served_too(tmp_path):
    """Placement is half the join. A picture that arrives full-width and is moved
    by a script is a picture the no-script reader sees in the wrong place."""
    got = _served(_rendered(), [_fig_row(side="left", width=0.32)])
    assert "data-float='left'" in got
    assert "data-float-basis='geometry'" in got
    assert "width:32%" in got


def test_each_picture_of_a_group_is_served_at_its_own_width(tmp_path):
    """`2-085`'s fig. 253, through the renderer: the narrow part must not be
    stretched to the union's width."""
    got = _served(_rendered(), [
        _fig_row(crops=(("001", 0.17), ("002", 0.56)), width=0.79)])
    assert "width:22%" in got, "0.17/0.79 of the block"
    assert "width:71%" in got, "0.56/0.79 of the block"


def test_an_unresolved_figure_is_served_as_a_gap(tmp_path):
    """Never the next unused crop: a wrong picture under a right caption reads as
    correct and is the failure this edition is organised against."""
    got = _served(_rendered(), [
        {"i": 0, "n": "2", "why": "no box in gt/fig/", "crops": []}])
    assert "figure-missing" in got and "no box in gt/fig/" in got
    assert "<img" not in got


def test_a_figure_the_join_has_no_row_for_is_left_alone(tmp_path):
    """A mismatch means one of the two sides is stale, never that some other
    figure's picture will do."""
    assert _served(_rendered(), [_fig_row(i=7)]) == _rendered()


def test_the_handles_are_re_emitted_off_the_tag(tmp_path):
    """`data-figure` and `data-i` reach the page as the renderer set them, whatever
    the join says — they are the page's own facts and this is not their source."""
    got = _served(_rendered(n="87", i=3), [_fig_row(i=3, n="")])
    assert 'data-figure=\'87\'' in got and 'data-i=\'3\'' in got


def test_the_cached_record_is_not_written_through(tmp_path):
    """`stores.render` is `lru_cache`d: writing the spliced HTML back into the
    record it handed out is how the stale placement this arrangement exists to
    prevent would get cached after all."""
    from harness.web.edition import _hang_pictures
    doc = {"html": _rendered(), "notes": [{"n": "1", "i": 1, "html": _figref()}]}
    out = _hang_pictures(doc, [_fig_row()], [
        {"pairs": ["1-207/001"], "url": "/edition/fig/1-207/001.png",
         "label": "Fig. 87", "caption": "", "why": ""}])
    assert doc["html"] == _rendered() and out["html"] != doc["html"]
    assert doc["notes"][0]["html"] == _figref()
    assert out["notes"][0]["html"] != doc["notes"][0]["html"]


def _figref(body="3") -> str:
    return _figref_at(0, body)


def _figref_at(i: int, body: str) -> str:
    """What `el_figref` writes. `i` is the page's own handle count, which runs
    across the body and the notes together."""
    return f'<a class="figref" data-fr="{i}" tabindex="0">{body}</a>'


def test_a_resolved_reference_is_a_working_link_without_a_script(tmp_path):
    got = _served(_figref(), [], [
        {"pairs": ["1-207/001"], "url": "/edition/fig/1-207/001.png",
         "label": "Fig. 87", "caption": "Fig. 87. A knife.", "why": ""}])
    assert "href='/edition/fig/1-207/001.png'" in got
    # `fig` is the List of Illustrations' own class, so one handler serves both.
    assert "class='figref fig'" in got
    assert "data-caption='Fig. 87. A knife.'" in got
    assert ">3</a>" in got, "the words the printer set are passed through"


def test_an_unresolved_reference_is_not_a_link_at_all(tmp_path):
    got = _served(_figref(), [], [
        {"pairs": [], "url": "", "label": "", "caption": "",
         "why": "Sauer's plate, not this book's"}])
    assert "figref unresolved" in got and "href=" not in got
    assert "tabindex" not in got, "not a link, so not in the tab order"
    assert "Sauer&#39;s plate, not this book&#39;s" in got


def test_a_reference_inside_a_footnote_is_linked_too(tmp_path):
    """**The notes are the page's other stream of rendered HTML.**

    `el_note` holds a footnote's words aside for the template to set at the foot,
    so a reference printed inside one never appears in `doc["html"]` — `1-132`
    prints two and neither is in the body. The script this replaced queried the
    whole document and reached them without having to know that; a splice over
    one string does not, and 36 references corpus-wide were inert until the
    server ran over both.
    """
    got = _serve(_rendered(), [_fig_row()],
                 [{"pairs": [], "url": "", "label": "", "caption": "",
                   "why": "no box in gt/fig/"},
                  {"pairs": ["1-132/001"], "url": "/edition/fig/1-132/001.png",
                   "label": "Plate XXXVI, Fig. 2", "caption": "A drum.",
                   "why": ""}],
                 notes=[_figref("XXXVI") + _figref_at(1, "2")])
    note = got["notes"][0]["html"]
    assert 'class="figref"' not in note, "no handle may be left inert"
    assert "figref unresolved" in note and "no box in gt/fig/" in note
    assert "href='/edition/fig/1-132/001.png'" in note


def test_the_handle_index_runs_across_body_and_notes(tmp_path):
    """One `refs` serves both streams because `el_figref` counts once for the
    page. A per-stream index would point a note's reference at the body's crop —
    a working link to the wrong picture, which reads as right."""
    body = _figref("87")
    got = _serve(body, [], [
        {"pairs": ["1-207/001"], "url": "/edition/fig/1-207/001.png",
         "label": "Fig. 87", "caption": "", "why": ""},
        {"pairs": ["1-132/001"], "url": "/edition/fig/1-132/001.png",
         "label": "Fig. 88", "caption": "", "why": ""},
    ], notes=[_figref_at(1, "88")])
    assert "1-207/001.png" in got["html"] and "1-132" not in got["html"]
    assert "1-132/001.png" in got["notes"][0]["html"]
