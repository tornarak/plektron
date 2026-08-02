"""`ocr adopt-gap` previews unless `--commit`.

`adopt_gaps` is one of exactly two writers into `gt/ocr/`, and until the CLI
reorganization it was the only one with no gate at all: `restore` beside it has
always required `--commit`, while this wrote the moment it was invoked. That
asymmetry was not a decision anyone recorded — it was what happens when four
different write-enable idioms coexist and nothing states which applies where.

The property under test is the one that matters for a ground-truth store: after
a preview the file on disk is **byte-identical**. Not "no lines were added" —
byte-identical, because a rewrite that happened to preserve the line count would
still have reserialized the tree, and this store's whole design rests on a file
only changing when a human said so.

Fixtures are synthetic and live in `tmp_path`, per the suite's rule. The band
geometry is contrived to be found by `line_gaps`: a page whose ink sits where no
TextLine covers it.
"""
from __future__ import annotations
from pathlib import Path

import pytest

from harness.lines import adopt_gaps

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _page(tmp_path: Path, ref: str = "1-048") -> Path:
    """A minimal ALTO with one line, plus the raster `line_gaps` measures against.

    The raster carries a black bar well below the single declared line, so the
    detector finds exactly one uncovered band and `adopt_gaps` has something real
    to adopt.
    """
    from PIL import Image

    gt = tmp_path / "gt" / "ocr"
    gt.mkdir(parents=True)
    (tmp_path / "scans").mkdir()
    (tmp_path / "gt" / "fig").mkdir(parents=True)

    w, h = 600, 800
    img = Image.new("RGB", (w, h), "white")
    for y in range(100, 130):            # the covered line
        for x in range(50, 550):
            img.putpixel((x, y), (0, 0, 0))
    for y in range(400, 430):            # the uncovered band
        for x in range(50, 550):
            img.putpixel((x, y), (0, 0, 0))
    img.save(tmp_path / "scans" / f"chukchi-{ref}.png")

    alto = f"""<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="{ALTO_NS}">
  <Description><sourceImageInformation><fileName>chukchi-{ref}.png</fileName>
  </sourceImageInformation></Description>
  <Layout><Page ID="p1" WIDTH="{w}" HEIGHT="{h}" PHYSICAL_IMG_NR="1">
    <PrintSpace HPOS="0" VPOS="0" WIDTH="{w}" HEIGHT="{h}">
      <TextBlock ID="b1" HPOS="50" VPOS="100" WIDTH="500" HEIGHT="30">
        <TextLine ID="l1" HPOS="50" VPOS="100" WIDTH="500" HEIGHT="30"
                  BASELINE="50 130 550 130">
          <String CONTENT="covered" HPOS="50" VPOS="100" WIDTH="500" HEIGHT="30"/>
        </TextLine>
      </TextBlock>
    </PrintSpace>
  </Page></Layout>
</alto>
"""
    p = gt / f"chukchi-{ref}.xml"
    p.write_text(alto, encoding="utf-8")
    return p


@pytest.fixture
def page(tmp_path):
    return tmp_path, _page(tmp_path)


def _band(tmp_path, ref="1-048"):
    from harness.lines import line_gaps
    bands = line_gaps(ref, "gt/ocr", tmp_path)
    assert bands, "fixture produced no uncovered band; the detector moved"
    return bands[0]["vpos"]


def test_preview_leaves_the_file_byte_identical(page):
    tmp_path, alto = page
    before = alto.read_bytes()
    rep = adopt_gaps("1-048", [_band(tmp_path)], "gt/ocr", tmp_path)
    assert rep["committed"] is False
    assert alto.read_bytes() == before, (
        "a preview rewrote the ground-truth file")


def test_preview_still_reports_what_it_would_do(page):
    """A gate that reports nothing is a gate nobody can act on."""
    tmp_path, _ = page
    rep = adopt_gaps("1-048", [_band(tmp_path)], "gt/ocr", tmp_path)
    assert len(rep["added"]) == 1
    assert rep["lines_before"] == 1 and rep["lines_after"] == 2
    # Not guessed: an index is assigned by document order in a file that does
    # not exist yet, and inventing one would be a number to key against that
    # nothing produced.
    assert rep["new_indices"] is None


def test_commit_writes_and_reports_real_indices(page):
    tmp_path, alto = page
    before = alto.read_bytes()
    rep = adopt_gaps("1-048", [_band(tmp_path)], "gt/ocr", tmp_path, commit=True)
    assert rep["committed"] is True
    assert alto.read_bytes() != before
    assert rep["lines_after"] == 2
    assert rep["new_indices"] and len(rep["new_indices"]) == 1


def test_the_new_line_carries_no_text(page):
    """The whole legitimacy of this second writer rests on it: geometry only,
    never CONTENT. Text arrives solely through decision.json -> restore."""
    from lxml import etree
    tmp_path, alto = page
    adopt_gaps("1-048", [_band(tmp_path)], "gt/ocr", tmp_path, commit=True)
    tree = etree.parse(str(alto))
    new = [s for s in tree.iter(f"{{{ALTO_NS}}}String")
           if (s.getparent().get("ID") or "").startswith("gap_")]
    assert new, "no gap_-prefixed line was created"
    assert all(s.get("CONTENT") == "" for s in new)


def test_an_unmeasured_band_is_refused_before_any_write(page):
    """The refusals must precede the write in both modes, or a preview is a
    cheaper check rather than a rehearsal of the real one."""
    tmp_path, alto = page
    before = alto.read_bytes()
    with pytest.raises(ValueError, match="no measured gap band"):
        adopt_gaps("1-048", [99999], "gt/ocr", tmp_path, commit=True)
    assert alto.read_bytes() == before


def test_default_is_preview(page):
    """The signature's default is what a forgotten keyword lands on, and this
    writer's default used to be `write`."""
    import inspect
    assert inspect.signature(adopt_gaps).parameters["commit"].default is False
