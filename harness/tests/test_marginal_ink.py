"""Ink beside an accounted-for line, not only ink below one.

`ocr blot` paints every line's **box** and calls itself "the inverse of
`line_gaps`". It was not. `line_gaps` masked whole image **rows**, so anything
sharing rows with a segmented line was hidden by that line across the full width
of the page — and the class that lives there is the marginal apparatus: a folio
beside a running title, a list number outside its line's polygon, a stranded
catchword. `1-073` strands its folio outside every box on the page, `1-074`
prints `5.` and `9.` outside theirs, and on `1-037` a reader recovered the folio
with `--margins`, found no line index to hold it, and concatenated it into the
running title's text — which would have restored ground truth asserting that the
title's box contains a "17" sitting 500 px to its right.

Nothing reported that, because nothing could. These tests are the box-masking
made permanent, and the second one pins the threshold half of the same bug: a
row fraction is a fraction *of the strip being searched*, so searching a wider
strip must not make a small mark harder to find.
"""

from pathlib import Path

import pytest

from harness.lines import MIN_BAND_H, line_gaps

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _page(tmp_path: Path, ref: str = "1-048", *, mark: tuple | None = None) -> Path:
    """A page whose one declared line shares its rows with an unaccounted mark.

    `mark` is `(x0, x1, y0, y1)` of extra ink to paint. The declared line covers
    x 50–550 of a 1200 px page, so a mark to the right of it is beside the line
    rather than below it — the case a row mask cannot express.
    """
    from PIL import Image

    gt = tmp_path / "gt" / "ocr"
    gt.mkdir(parents=True)
    (tmp_path / "scans").mkdir()
    (tmp_path / "gt" / "fig").mkdir(parents=True)
    import shutil
    (tmp_path / "data").mkdir()
    shutil.copy(Path("data") / "zones_config.json", tmp_path / "data")

    w, h = 1200, 800
    img = Image.new("RGB", (w, h), "white")
    for y in range(100, 140):
        for x in range(50, 550):
            img.putpixel((x, y), (0, 0, 0))
    if mark:
        mx0, mx1, my0, my1 = mark
        for y in range(my0, my1):
            for x in range(mx0, mx1):
                img.putpixel((x, y), (0, 0, 0))
    img.save(tmp_path / "scans" / f"chukchi-{ref}.png")

    alto = f"""<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="{ALTO_NS}">
  <Description><sourceImageInformation><fileName>chukchi-{ref}.png</fileName>
  </sourceImageInformation></Description>
  <Layout><Page ID="p1" WIDTH="{w}" HEIGHT="{h}" PHYSICAL_IMG_NR="1">
    <PrintSpace HPOS="0" VPOS="0" WIDTH="{w}" HEIGHT="{h}">
      <TextBlock ID="b1" HPOS="50" VPOS="100" WIDTH="500" HEIGHT="40">
        <TextLine ID="l1" HPOS="50" VPOS="100" WIDTH="500" HEIGHT="40"
                  BASELINE="50 140 550 140">
          <String CONTENT="covered" HPOS="50" VPOS="100" WIDTH="500" HEIGHT="40"/>
        </TextLine>
      </TextBlock>
    </PrintSpace>
  </Page></Layout>
</alto>
"""
    (gt / f"chukchi-{ref}.xml").write_text(alto, encoding="utf-8")
    return tmp_path


def test_a_line_still_masks_its_own_ink(tmp_path):
    """The control. Box-masking must not start reporting the very line it covers."""
    root = _page(tmp_path)
    assert line_gaps("1-048", root, "gt/ocr") == []


def test_ink_beside_a_covered_line_is_found(tmp_path):
    """The whole point: same rows as the declared line, well outside its box.

    A row mask reports nothing here, which is what shipped for the life of the
    detector.
    """
    root = _page(tmp_path, mark=(700, 900, 100, 140))
    bands = line_gaps("1-048", root, "gt/ocr")
    assert len(bands) == 1, f"expected the mark beside the line, got {bands}"
    b = bands[0]
    assert 690 <= b["hpos"] <= 710, b
    assert b["width"] >= 190
    # Reported with its own extent, which is what a repair needs — not the extent
    # of the window it was found in.
    assert b["height"] >= MIN_BAND_H


@pytest.mark.parametrize("x0,x1", [(700, 900), (1000, 1180)])
def test_the_strip_is_measured_against_its_own_width(tmp_path, x0, x1):
    """A fraction of *what*? `ROW_INK_FRACTION` is a share of the strip searched.

    Applied to one page-wide window it silently becomes the wrong question:
    widening the search raises the absolute bar, so the marks that only a wider
    search can see are exactly the ones it then cannot reach. On `1-037` the
    column is 1,778 px (bar: 8 ink columns) and the whole page 2,824 (bar: 14),
    against a folio 43 px wide. Searching wider must not detect less.
    """
    root = _page(tmp_path, mark=(x0, x1, 100, 140))
    assert len(line_gaps("1-048", root, "gt/ocr")) == 1
