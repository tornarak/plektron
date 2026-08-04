"""Pairing a picture with its caption, and resolving a page-local figure handle.

`GraphicZone`↔`GraphicZone-FigDesc` pairing is not in the data. It used to be
re-derived by whichever consumer needed it, and the collation pass was handed
both zones flat and left to work it out — which produced, on `1-151`, a correct
anchor followed by a comment calling the caption zone an unreferenced orphan.
A FigDesc is unreferenced by construction, so that comment was waiting on all
252 figure pages.

The geometry here is taken from real pages and the numbers are the store's.
"""
from __future__ import annotations

from pathlib import Path

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _fig_alto(tmp_path: Path, ref: str, blocks) -> Path:
    """A figure-track ALTO. `blocks` is (id, label, x, y, w, h)."""
    p = tmp_path / "gt" / "fig" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<TextBlock ID="{i}" TAGREFS="{"BT77" if lab.endswith("FigDesc") else "BT78"}"'
        f' HPOS="{x}.0" VPOS="{y}.0" WIDTH="{w}.0" HEIGHT="{h}.0"/>'
        for i, lab, x, y, w, h in blocks)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>{body}'
        "</PrintSpace></Page></Layout><Tags>"
        '<OtherTag ID="BT77" TYPE="type" LABEL="GraphicZone-FigDesc"/>'
        '<OtherTag ID="BT78" TYPE="type" LABEL="GraphicZone"/>'
        "</Tags></alto>", encoding="utf-8")
    return p


def _tei(tmp_path: Path, ref: str, body: str) -> Path:
    p = tmp_path / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader/><text><body><p>{body}</p>'
        "</body></text></TEI>", encoding="utf-8")
    return p


def _readings(tmp_path: Path, blocks: dict[str, str]) -> None:
    tmp_path.joinpath("data").mkdir(parents=True, exist_ok=True)
    tmp_path.joinpath("data", "readings.md").write_text(
        "".join(f"## {k}\n{v}\n\n" for k, v in blocks.items()), encoding="utf-8")


def test_text_figure_caption_is_below_its_picture(tmp_path):
    """`1-151`: one picture, one landscape caption 12 px under it."""
    from harness.figures import paired
    _fig_alto(tmp_path, "1-151", [
        ("eSc_textblock_d2082379", "GraphicZone-FigDesc", 1556, 2859, 610, 96),
        ("eSc_textblock_78034cff", "GraphicZone", 1550, 2167, 570, 680)])
    _readings(tmp_path, {"1-151|d2082379": "Fig. 30, a. Iron Harpoon-Heads."})

    got = paired("1-151", tmp_path)
    assert got["unpaired_captions"] == []
    assert [(f["index"], f["zone_id"], f["caption"]) for f in got["figures"]] == [
        (1, "eSc_textblock_78034cff", "Fig. 30, a. Iron Harpoon-Heads.")]


def test_a_rotated_plate_caption_is_beside_its_picture(tmp_path):
    """`1-049`: three plate captions, each rotated and set to the picture's right.

    The rule that finds a text figure's caption — below, overlapping horizontally
    — leaves every one of these unclaimed, which is what it did: 19 orphans over
    14 pages, all plates. The discriminator is the caption box's own shape.
    """
    from harness.figures import paired
    _fig_alto(tmp_path, "1-049", [
        ("eSc_textblock_4b921bb2", "GraphicZone-FigDesc", 1296, 1790, 86, 457),
        ("eSc_textblock_286e499a", "GraphicZone-FigDesc", 2452, 2511, 92, 506),
        ("eSc_textblock_fb5fac70", "GraphicZone-FigDesc", 2452, 930, 82, 636),
        ("eSc_textblock_fabb8525", "GraphicZone", 154, 874, 1130, 2279),
        ("eSc_textblock_fa556653", "GraphicZone", 1480, 544, 962, 1372),
        ("eSc_textblock_a2f47a6a", "GraphicZone", 1470, 2049, 980, 1374)])
    _readings(tmp_path, {"1-049|4b921bb2": "left", "1-049|286e499a": "lower right",
                         "1-049|fb5fac70": "upper right"})

    got = paired("1-049", tmp_path)
    assert got["unpaired_captions"] == []
    assert {f["zone_id"]: f["caption"] for f in got["figures"]} == {
        "eSc_textblock_fabb8525": "left",
        "eSc_textblock_fa556653": "upper right",
        "eSc_textblock_a2f47a6a": "lower right"}


def test_a_rotated_caption_belongs_to_the_picture_on_its_left(tmp_path):
    """`1-273`: two plates tie at 30 px, and only direction breaks the tie.

    The top-right picture is equidistant from the caption on its own right and
    the one belonging to the picture on its left. Without "after, in the
    caption's own reading direction", document order decides — and decides wrong,
    leaving the right-hand caption an orphan.
    """
    from harness.figures import paired
    _fig_alto(tmp_path, "1-273", [
        ("eSc_textblock_eef207cb", "GraphicZone-FigDesc", 1350, 846, 98, 736),
        ("eSc_textblock_f353918d", "GraphicZone-FigDesc", 2514, 942, 70, 562),
        ("eSc_textblock_9d015eb7", "GraphicZone", 376, 518, 974, 1390),
        ("eSc_textblock_e8bbfd0c", "GraphicZone", 1478, 502, 1006, 1410)])
    _readings(tmp_path, {"1-273|eef207cb": "left", "1-273|f353918d": "right"})

    got = paired("1-273", tmp_path)
    assert got["unpaired_captions"] == []
    assert {f["zone_id"]: f["caption"] for f in got["figures"]} == {
        "eSc_textblock_9d015eb7": "left", "eSc_textblock_e8bbfd0c": "right"}


def test_several_pictures_may_share_one_caption(tmp_path):
    """`2-085`: fig. 253 *a, b* — two pictures, one printed caption.

    Pairing is one-way on purpose. 17 pages are not 1:1 and nothing will make
    them so; a caption is never split between pictures.
    """
    from harness.figures import paired
    _fig_alto(tmp_path, "2-085", [
        ("eSc_textblock_caf7f738", "GraphicZone-FigDesc", 1036, 2491, 1046, 102),
        ("eSc_textblock_1d4dcdbc", "GraphicZone", 1864, 908, 304, 1581),
        ("eSc_textblock_38899688", "GraphicZone", 966, 1322, 886, 1163)])
    _readings(tmp_path, {"2-085|caf7f738": "Fig. 253, a, b."})

    got = paired("2-085", tmp_path)
    assert got["unpaired_captions"] == []
    assert [f["caption"] for f in got["figures"]] == ["Fig. 253, a, b."] * 2


def test_a_speck_of_a_zone_does_not_claim_a_caption(tmp_path):
    """The same page's 14x38 `GraphicZone`, which is not a figure.

    Overlap on the perpendicular axis is required rather than preferred, so the
    speck stays captionless instead of absorbing fig. 253's caption. A defect
    that shows beats a defect a rule swallowed.
    """
    from harness.figures import paired
    _fig_alto(tmp_path, "2-085", [
        ("eSc_textblock_caf7f738", "GraphicZone-FigDesc", 1036, 2491, 1046, 102),
        ("eSc_textblock_b90f8626", "GraphicZone", 414, 500, 14, 38),
        ("eSc_textblock_38899688", "GraphicZone", 966, 1322, 886, 1163)])
    _readings(tmp_path, {"2-085|caf7f738": "Fig. 253, a, b."})

    got = {f["zone_id"]: f["caption"] for f in paired("2-085", tmp_path)["figures"]}
    assert got["eSc_textblock_b90f8626"] == ""
    assert got["eSc_textblock_38899688"] == "Fig. 253, a, b."


def test_artwork_with_no_caption_is_a_figure_with_an_empty_one(tmp_path):
    """`3-006`: a `GraphicZone` the book captions nowhere.

    Empty means this now, rather than meaning every picture zone — which is what
    it meant while the payload listed pictures and captions as sibling rows, a
    caption being keyed to the FigDesc's id and never to the picture's.
    """
    from harness.figures import paired
    _fig_alto(tmp_path, "3-006", [
        ("eSc_textblock_4fe42976", "GraphicZone", 376, 2146, 1701, 1008)])
    _readings(tmp_path, {})

    got = paired("3-006", tmp_path)
    assert [f["caption"] for f in got["figures"]] == [""]
    assert got["unpaired_captions"] == []


def test_a_caption_no_picture_claims_is_reported(tmp_path):
    """`2-068`: figs. 239 and 240 stacked below two side-by-side pictures.

    Both captions span the full measure, so geometry cannot say which is whose —
    only caption reading order can, and that is an inference. The honest output
    is one unpaired caption, which `reconcile` surfaces.
    """
    from harness.figures import paired
    _fig_alto(tmp_path, "2-068", [
        ("eSc_textblock_580750c2", "GraphicZone-FigDesc", 382, 2738, 763, 77),
        ("eSc_textblock_44f33841", "GraphicZone-FigDesc", 383, 2803, 767, 96),
        ("eSc_textblock_1f4d5553", "GraphicZone", 884, 1238, 218, 1425),
        ("eSc_textblock_f126f10d", "GraphicZone", 496, 1680, 294, 959)])
    _readings(tmp_path, {"2-068|580750c2": "Fig. 239.", "2-068|44f33841": "Fig. 240."})

    assert paired("2-068", tmp_path)["unpaired_captions"] == [
        "eSc_textblock_44f33841"]


def test_the_model_sees_the_printed_number_and_the_caption(tmp_path):
    """The payload's whole surface — and `n` is the *book's* identity.

    Not a zone id (an opaque string a model cannot check) and not a page-local
    ordinal over pictures either: the zone count is not the figure count in
    either direction, so an ordinal would misreport how many figures a page has.
    """
    from harness.context import _figures_on_page
    _fig_alto(tmp_path, "1-151", [
        ("eSc_textblock_d2082379", "GraphicZone-FigDesc", 1556, 2859, 610, 96),
        ("eSc_textblock_78034cff", "GraphicZone", 1550, 2167, 570, 680)])
    _readings(tmp_path, {"1-151|d2082379": "Fig. 30, a."})

    assert _figures_on_page("1-151", tmp_path) == [
        {"n": "30", "caption": "Fig. 30, a."}]


def test_pictures_sharing_a_caption_are_one_printed_figure(tmp_path):
    """`2-085`: two boxes, one caption, one `Fig. 253` — so one row.

    A row per *box* would tell the model this page has two figures where the
    book prints one. `1-207` is the same fault the other way round: fig. 87
    *a, b, c* in two boxes, `a` and `b` sharing one.
    """
    from harness.context import _figures_on_page
    _fig_alto(tmp_path, "2-085", [
        ("eSc_textblock_caf7f738", "GraphicZone-FigDesc", 1036, 2491, 1046, 102),
        ("eSc_textblock_1d4dcdbc", "GraphicZone", 1864, 908, 304, 1581),
        ("eSc_textblock_38899688", "GraphicZone", 966, 1322, 886, 1163)])
    _readings(tmp_path, {"2-085|caf7f738": "Fig. 253, a, b. Combs."})

    assert _figures_on_page("2-085", tmp_path) == [
        {"n": "253", "caption": "Fig. 253, a, b. Combs."}]


def test_the_number_stops_at_the_figure_number(tmp_path):
    """`1-207` opens `Fig. 87, a (??/????), b …`, and the answer is 87.

    The catalogue numbers, the letters and the dimensions after it are not the
    number of anything.
    """
    from harness.context import figure_number
    assert figure_number("Fig. 87, a (??/????), b (??/????). Designs. 1/9 nat.") == "87"
    assert figure_number("Figs. 2, 3. Drums.") == "2"
    assert figure_number("") is None
    assert figure_number("Plate XI.") is None


def test_a_figure_must_name_a_number_this_page_prints(tmp_path):
    """The check with a real second witness: the page's own captions.

    A figure anchored on the wrong page is the error worth catching, and no set
    of zone ids handed over by the context can see it — only the book's numbering
    can. `1-151`'s textual `(Fig. 31)` resolves to nothing on that page, which is
    a real state and why the pass comments rather than anchors.
    """
    from harness.validate import validate
    p = _tei(tmp_path, "1-151", '<figure n="31"/>')
    ctx = {"page_ref": "1-151", "root": str(tmp_path), "ocr_lines": [],
           "toc_window": [], "figures_on_page": [{"n": "30", "caption": "Fig. 30."}]}

    assert any("no caption on this page prints" in e for e in validate(p, ctx).errors)


def test_a_figure_may_not_carry_a_zone_id(tmp_path):
    """Placing a figure is the build's join through `data/readings.md`, not the
    collator's — its competence is finding where the prose refers to one."""
    from harness.validate import validate
    p = _tei(tmp_path, "1-151", '<figure n="30" facs="#eSc_textblock_78034cff"/>')
    ctx = {"page_ref": "1-151", "root": str(tmp_path), "ocr_lines": [],
           "toc_window": [], "figures_on_page": [{"n": "30", "caption": "Fig. 30."}]}

    assert any("the build resolves the zones" in e for e in validate(p, ctx).errors)


