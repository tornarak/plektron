"""Placing a figure in the reading view: the column, the match, and the caption.

Three things are held here.

**The caption reaches the reader.** `el_figure` used to build a `[fig. N]` chip
and never call `inline`, so the `<figDesc>` the generator had gone to
`data/readings.md` to fetch was dropped on the floor of every page.

**No geometry goes into the rendered HTML.** `stores.render` is cached on the
TEI file's bytes alone, so a box baked into that HTML would let a corrected
`gt/fig/` serve stale placement out of the cache with nothing to signal it. The
pictures are joined at the route instead, off a key that names the figure
stores.

**A figure that cannot be resolved shows as a gap, never as a picture.** Falling
back to the next unused crop would put a wrong picture under a right caption,
which reads as correct and is invisible.
"""
from __future__ import annotations

from pathlib import Path

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
    tmp_path.joinpath("data").mkdir(parents=True, exist_ok=True)
    tmp_path.joinpath("data", "readings.md").write_text(
        "".join(f"## {k}\n{v}\n\n" for k, v in blocks.items()), encoding="utf-8")


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
    real = json.loads(Path("data/zones_config.json").read_text(encoding="utf-8"))
    real["figures"] = {**real["figures"], **figures}
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "zones_config.json").write_text(json.dumps(real), encoding="utf-8")


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
