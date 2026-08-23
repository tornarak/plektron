"""Grouping printed figures, and cutting them out of the raster.

Two things are held here, and they are the two that went wrong while this was
being built.

**The grouping and the crop unit are not the same unit.** A printed figure is
what a caption names — `1-276`'s fig. 140 is one figure set in two boxes,
lettered *a* and *b* inside its single caption — so `figure_boxes` folds on the
caption. A *crop* is one declared `GraphicZone` and never a union of several,
because a bounding box over boxes a human drew separately is a region no human
drew. On fig. 140 that region is six lines of body prose: the two boxes are
stacked at different widths, so their bounding rectangle spans the text column
beside the upper one. The area cost looked negligible (1.75× the parts, the
corpus worst) right up until someone looked at the picture.

**The generator's figure placement must not move.** `_figures_with_geometry` was
a second copy of the caption fold, and folding it onto `figure_boxes` is only
safe if `y` keeps its exact old definition — `min` over the first member's
*picture and caption* zones, not over the union that `box` reports.
"""
from __future__ import annotations

from pathlib import Path

from conftest import write_captions

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _fig_alto(tmp_path: Path, ref: str, blocks) -> Path:
    """A figure-track ALTO. `blocks` is (id, label, x, y, w, h)."""
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


def _readings(tmp_path: Path, blocks: dict[str, str]) -> None:
    write_captions(tmp_path, blocks)


def _raster(tmp_path: Path, ref: str, size=(2824, 3897)):
    """A blank page raster, so a crop has something to come out of."""
    from PIL import Image
    p = tmp_path / "scans" / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", size, 255).save(p)
    return p


# `1-276` as the store holds it: fig. 138 (one box), fig. 139 (one box), and
# fig. 140 in two boxes stacked at different widths — the shape that refuted the
# union crop. Coordinates are the real ones.
_1_276 = [
    ("fig_1-276_001", "GraphicZone", 732, 868, 652, 724),
    ("fig_1-276_002", "GraphicZone-FigDesc", 726, 1606, 664, 148),
    ("fig_1-276_003", "GraphicZone", 726, 1784, 680, 177),
    ("fig_1-276_004", "GraphicZone-FigDesc", 730, 1985, 656, 96),
    ("fig_1-276_005", "GraphicZone", 746, 2149, 616, 300),
    ("fig_1-276_006", "GraphicZone", 726, 2510, 782, 507),
    ("fig_1-276_007", "GraphicZone-FigDesc", 722, 3060, 692, 148),
]
_1_276_CAPS = {
    "1-276|002": "Fig. 138, a, b, c. Implements for drilling Eye-Holes.",
    "1-276|004": "Fig. 139. Wooden Tongs. Length, 11.5 cm.",
    "1-276|007": "Fig. 140, a, b. Woman's Knives. 1/3 nat. size.",
}


def test_a_shared_caption_makes_one_figure_over_several_boxes(tmp_path):
    """Fig. 140 is one printed figure, and the store spells it in two boxes."""
    from harness.figures import figure_boxes
    _fig_alto(tmp_path, "1-276", _1_276)
    _readings(tmp_path, _1_276_CAPS)

    got = figure_boxes("1-276", tmp_path)
    assert [f["n"] for f in got] == ["138", "139", "140"], (
        "three printed figures, in page order")
    by_n = {f["n"]: f for f in got}
    assert by_n["140"]["zone_ids"] == ["fig_1-276_005", "fig_1-276_006"]
    assert by_n["138"]["zone_ids"] == ["fig_1-276_001"]


def test_the_group_box_is_the_union_of_pictures_and_excludes_the_caption(tmp_path):
    """`box` covers every picture and stops there.

    The caption is carried as text and, on a plate, is set rotated beside the
    picture — including it would widen the box by a line of type on its side.
    """
    from harness.figures import figure_boxes
    _fig_alto(tmp_path, "1-276", _1_276)
    _readings(tmp_path, _1_276_CAPS)

    f = {x["n"]: x for x in figure_boxes("1-276", tmp_path)}["140"]
    assert f["box"] == (726, 2149, 1508, 3017)
    # The caption zone sits at y 3060–3208, below the box's own bottom edge.
    assert f["box"][3] < 3060


def test_a_crop_is_one_declared_box_and_never_a_union(tmp_path):
    """The bug this file exists for.

    Fig. 140's union spans x 726–1508 across y 2149–3017, and the upper box is
    only 616 wide — so a union crop takes in the text column to its right. Two
    crops, each its own box, take in nothing that was not drawn.
    """
    from harness.figures import write_crops
    _fig_alto(tmp_path, "1-276", _1_276)
    _readings(tmp_path, _1_276_CAPS)
    _raster(tmp_path, "1-276")

    recs = write_crops("1-276", tmp_path / "out", tmp_path)
    assert len(recs) == 4, "four boxes on the page, four crops"
    assert [r["name"] for r in recs] == [
        "chukchi-1-276-001.png", "chukchi-1-276-003.png",
        "chukchi-1-276-005.png", "chukchi-1-276-006.png"]

    from PIL import Image
    with Image.open(tmp_path / "out" / "chukchi-1-276-005.png") as im:
        assert im.size == (616, 300), "the box as drawn, not the group's union"


def test_every_part_carries_the_figure_it_belongs_to(tmp_path):
    """A crop knows its printed number and its group, so nothing re-derives them."""
    from harness.figures import write_crops
    _fig_alto(tmp_path, "1-276", _1_276)
    _readings(tmp_path, _1_276_CAPS)
    _raster(tmp_path, "1-276")

    by_key = {r["key"]: r for r in write_crops("1-276", tmp_path / "out", tmp_path)}
    assert by_key["005"]["n"] == by_key["006"]["n"] == "140"
    assert by_key["005"]["group"] == by_key["006"]["group"] == "005", (
        "both parts point at the group's key, which is its topmost box")


def test_a_fresh_crop_is_left_alone_but_force_recuts_it(tmp_path):
    """Re-saving unconditionally would give every crop a new ETag on every build."""
    from harness.figures import write_crops
    _fig_alto(tmp_path, "1-276", _1_276)
    _readings(tmp_path, _1_276_CAPS)
    _raster(tmp_path, "1-276")
    out = tmp_path / "out"

    assert all(r["written"] for r in write_crops("1-276", out, tmp_path))
    again = write_crops("1-276", out, tmp_path)
    assert not any(r["written"] for r in again)
    assert {r["why"] for r in again} == {"fresh"}
    assert all(r["written"] for r in write_crops("1-276", out, tmp_path, force=True))


def test_a_captionless_picture_is_its_own_figure(tmp_path):
    """`3-006` and `3-007`: artwork the book captions nowhere.

    An empty caption is not evidence that two such pictures are one figure, so
    they must not fold together the way a shared caption does.
    """
    from harness.figures import figure_boxes
    _fig_alto(tmp_path, "3-006", [
        ("fig_3-006_001", "GraphicZone", 376, 2146, 1701, 1008),
        ("fig_3-006_002", "GraphicZone", 376, 400, 1701, 500)])
    _readings(tmp_path, {})

    got = figure_boxes("3-006", tmp_path)
    assert len(got) == 2, "two captionless pictures are two figures, not one"
    assert [f["n"] for f in got] == [None, None]
    assert [f["caption"] for f in got] == ["", ""]


def test_the_group_y_keeps_the_generators_old_definition(tmp_path):
    """`y` is over the first member's picture *and caption*; `box` is not.

    The two agree on all 398 figures in the corpus today — a caption is never set
    above its picture — and `y` is defined this way anyway, so that folding
    `generate._figures_with_geometry` onto this function cannot move a figure in
    `mz/tei/`. A caption placed above its picture is what would separate them.
    """
    from harness.figures import figure_boxes
    # A picture with its caption *above* it. Contrived: `_gap` will not pair them,
    # so this asserts the definition rather than a page.
    _fig_alto(tmp_path, "1-999", [
        ("fig_1-999_001", "GraphicZone", 700, 2000, 600, 400),
        ("fig_1-999_002", "GraphicZone-FigDesc", 700, 2450, 600, 90)])
    _readings(tmp_path, {"1-999|002": "Fig. 7. A thing."})

    f = figure_boxes("1-999", tmp_path)[0]
    assert f["caption_zone"] == "fig_1-999_002", "paired below, as usual"
    assert f["y"] == 2000 == f["box"][1], "picture first, so the two agree"


def test_membership_matches_what_the_writer_writes(tmp_path):
    """The farm and the writer must enumerate one set, or the farm drifts forever."""
    from harness.figures import crops_wanted, write_crops
    _fig_alto(tmp_path, "1-276", _1_276)
    _readings(tmp_path, _1_276_CAPS)
    _raster(tmp_path, "1-276")

    written = {r["name"] for r in write_crops("1-276", tmp_path / "out", tmp_path)}
    assert set(crops_wanted(tmp_path)) == written


def test_a_box_off_the_raster_is_a_row_not_a_crash(tmp_path):
    """One bad page must not stop a corpus sweep; `fig check` is where this gates."""
    from harness.figures import write_crops
    _fig_alto(tmp_path, "1-998", [
        ("fig_1-998_001", "GraphicZone", 9000, 9000, 600, 400)])
    _readings(tmp_path, {})
    _raster(tmp_path, "1-998")

    recs = write_crops("1-998", tmp_path / "out", tmp_path)
    assert [r["why"] for r in recs] == ["off-raster"]
    assert not any(r["written"] for r in recs)


def test_a_human_touched_up_picture_survives_a_forced_rebuild(tmp_path):
    """The property `gt/fig-img/` exists for.

    `scans/fig-crops/` is derived and gitignored: a picture enhanced in place
    there is destroyed by the next `--force` with no copy anywhere, which is this
    repository's one catastrophic failure re-enacted. So the human's version goes
    in a tracked store the cropper never writes to, and `crop_source` resolves it
    first.
    """
    from harness.figures import FIG_IMG, crop_name, crop_source, write_crops
    _fig_alto(tmp_path, "1-276", _1_276)
    _readings(tmp_path, _1_276_CAPS)
    _raster(tmp_path, "1-276")
    out = tmp_path / "out"
    write_crops("1-276", out, tmp_path)

    human = tmp_path / FIG_IMG / crop_name("1-276", "005")
    human.parent.mkdir(parents=True, exist_ok=True)
    human.write_bytes(b"a person's enhanced version")

    recs = write_crops("1-276", out, tmp_path, force=True)
    assert human.read_bytes() == b"a person's enhanced version", (
        "a forced rebuild must not touch the human store")
    assert [r["human"] for r in recs if r["key"] == "005"] == [True], (
        "and it must say the human version is there, or the work looks lost")

    path, rank = crop_source("1-276", "005", tmp_path)
    assert (path, rank) == (human, "ed"), "the human file is what a reader gets"
    assert crop_source("1-276", "006", tmp_path)[1] == "mz"


def test_nothing_enhances_a_crop(tmp_path):
    """Enhancement is manual by design: a crop is the raster's own pixels.

    Asserted against a gradient, where any resample, sharpen or contrast pass
    would show up as a changed pixel.
    """
    from PIL import Image

    from harness.figures import write_crops
    _fig_alto(tmp_path, "1-999", [
        ("fig_1-999_001", "GraphicZone", 100, 200, 64, 32)])
    _readings(tmp_path, {})
    src = tmp_path / "scans" / "chukchi-1-999.png"
    src.parent.mkdir(parents=True, exist_ok=True)
    page = Image.new("L", (2824, 3897))
    page.putdata([(x * 7 + y * 13) % 256
                  for y in range(3897) for x in range(2824)])
    page.save(src)

    write_crops("1-999", tmp_path / "out", tmp_path)
    with Image.open(tmp_path / "out" / "chukchi-1-999-001.png") as got:
        assert got.size == (64, 32)
        assert list(got.get_flattened_data()) == list(
            page.crop((100, 200, 164, 232)).get_flattened_data()), (
            "the crop must be the raster's pixels, unmodified")
