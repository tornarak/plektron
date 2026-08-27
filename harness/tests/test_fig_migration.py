"""Reducing `gt/fig/` to the boxes every reader was already taking.

The eScriptorium export wrote a `Shape/Polygon` beside each block's bbox, and 395
of the store's 809 polygons are skewed quads or 5-to-9-gons that disagree with
that bbox. **Nothing has ever read them**: every consumer goes through
`figures.read_blocks`, which takes `HPOS/VPOS/WIDTH/HEIGHT` through `_bbox`. So
the migration writes down what was already being read, and the geometry check is
a check of that claim rather than an aspiration — a page whose numbers move means
the claim was wrong, and the whole run refuses.

It had a second half, and the tests for it are gone with the store they covered.
Block ids are re-minted `fig_PP-NNN_NNN`, and a separate markdown file keyed the
395 hand-read captions by a block id's last field, so the two moved together or
neither did. That file was retired — the ratified caption now lives on the FigDesc
block it keys — so there is no second file to keep in step, and the id remap is
checked here against the store alone.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_scan

from harness import figures as F

# One page in the shape the export left behind: float attributes, ids that carry
# no ordinal, a caption whose polygon slopes six pixels across its foot, and the
# caption sorting *above* the picture so the re-mint has to reorder them.
EXPORT = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Description><sourceImageInformation><fileName>chukchi-1-037.png</fileName>
  </sourceImageInformation></Description>
  <Tags>
    <OtherTag ID="BT77" LABEL="GraphicZone-FigDesc"/>
    <OtherTag ID="BT78" LABEL="GraphicZone"/>
  </Tags>
  <Layout><Page WIDTH="2824" HEIGHT="3897"><PrintSpace>
    <TextBlock HPOS="782.0" VPOS="2541.0" WIDTH="1044.0" HEIGHT="98.0"
               ID="eSc_textblock_ca04178c" TAGREFS="BT77">
      <Shape><Polygon POINTS="1826 2639 1826 2541 782 2541 782 2633"/></Shape>
    </TextBlock>
    <TextBlock HPOS="458.0" VPOS="938.0" WIDTH="1754.0" HEIGHT="1605.0"
               ID="eSc_textblock_4be4b120" TAGREFS="BT78">
      <Shape><Polygon POINTS="458 938 458 2543 2212 2543 2212 938"/></Shape>
    </TextBlock>
  </PrintSpace></Page></Layout>
</alto>
"""

@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_scan(tmp_path, "1-037", size=(2824, 3897))
    (tmp_path / "gt/fig").mkdir(parents=True)
    (tmp_path / "gt/fig/chukchi-1-037.xml").write_text(EXPORT, encoding="utf-8")
    return tmp_path


# --- the page ----------------------------------------------------------------

def test_the_bbox_is_what_the_reader_already_computed(root):
    """Float attributes and a sloped polygon in; the same numbers `read_blocks`
    was already returning out."""
    m = F.migrate_page("1-037", root)
    assert m["before"] == m["after"]
    assert m["after"] == sorted([
        ("GraphicZone", 458, 938, 1754, 1605),
        ("GraphicZone-FigDesc", 782, 2541, 1044, 98),
    ])


def test_ids_are_reminted_in_geometric_order(root):
    m = F.migrate_page("1-037", root)
    assert [(b["id"], b["label"]) for b in m["blocks"]] == [
        ("fig_1-037_001", "GraphicZone"),
        ("fig_1-037_002", "GraphicZone-FigDesc"),
    ]


def test_the_remap_covers_captions_only(root):
    """Only FigDesc suffixes ever keyed a caption, so only they can move a key."""
    assert F.migrate_page("1-037", root)["remap"] == {"ca04178c": "002"}


# --- the run -----------------------------------------------------------------

def test_a_dry_run_writes_nothing(root):
    before = (root / "gt/fig/chukchi-1-037.xml").read_bytes()
    out = F.migrate_store(root)
    assert out["committed"] is False
    assert (root / "gt/fig/chukchi-1-037.xml").read_bytes() == before


def test_a_commit_rewrites_the_store(root):
    out = F.migrate_store(root, commit=True)
    assert out["committed"] is True
    assert out["captions"] == 1

    blocks = F.read_blocks(F.alto_for("1-037", root), with_points=True)
    assert [b["id"] for b in blocks] == ["fig_1-037_001", "fig_1-037_002"]
    # The polygon now agrees with the bbox, which is what `validate_fig_page`'s
    # `not-a-rectangle` error was firing on across the whole un-migrated store.
    cap = next(b for b in blocks if b["label"] == F.FIGDESC)
    assert cap["points"] == "782 2541 1826 2541 1826 2639 782 2639"


def test_the_page_reconciles_after(root):
    """`missing` alone now, and it is not empty — which is the honest result.

    `orphan` meant "a reading whose zone is gone" and cannot happen once the
    caption lives on the block: `readings()` reads the very blocks it would be
    compared against, so `have ⊆ ids` by construction. It is gone rather than
    reporting an empty list forever.

    What is left is `1-037|002`, the migrated FigDesc, carrying no text — because
    this fixture supplies no caption text at all and the migration moves *keys*,
    never text into the store. `fig restore` is what fills
    a block, and a page that has not had it is exactly what `missing` is for.
    """
    F.migrate_store(root, commit=True)
    rec = F.reconcile(root)
    assert "orphan" not in rec
    assert rec["missing"] == ["1-037|002"]


def test_geometry_drift_refuses_the_whole_run(root):
    """A page whose numbers move falsifies the premise, so nothing is written —
    not that page, and not the 251 that were fine."""
    before = (root / "gt/fig/chukchi-1-037.xml").read_bytes()

    def drifted(ref, r=root, store=F.FIGDIR):
        m = _real(ref, r, store)
        m["after"] = [("GraphicZone", 0, 0, 1, 1)]
        return m

    _real = F.migrate_page
    F.migrate_page = drifted
    try:
        out = F.migrate_store(root)
    finally:
        F.migrate_page = _real
    assert out["geometry_drift"] == ["1-037"]
    assert out["committed"] is False
    assert (root / "gt/fig/chukchi-1-037.xml").read_bytes() == before
