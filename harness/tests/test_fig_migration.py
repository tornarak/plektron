"""Reducing `gt/fig/` to the boxes every reader was already taking.

The eScriptorium export wrote a `Shape/Polygon` beside each block's bbox, and 395
of the store's 809 polygons are skewed quads or 5-to-9-gons that disagree with
that bbox. **Nothing has ever read them**: every consumer goes through
`figures.read_blocks`, which takes `HPOS/VPOS/WIDTH/HEIGHT` through `_bbox`. So
the migration writes down what was already being read, and the geometry check is
a check of that claim rather than an aspiration — a page whose numbers move means
the claim was wrong, and the whole run refuses.

The other half is the readings key. Block ids are re-minted `fig_PP-NNN_NNN`, and
`data/readings.md` keys 395 hand-read captions by a block id's last field, so the
two files move together or neither does. The store and the readings are one fact
in two files; a rewrite of either alone reconciles to nothing.
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

READINGS = """# Figure-caption readings

## 1-037|ca04178c
Fig. 21.—Drum of the Reindeer Chukchee.
@note: VERBATIM

## 2-068|44f33841
Fig. 239.—Wooden vessel.
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_scan(tmp_path, "1-037", size=(2824, 3897))
    (tmp_path / "gt/fig").mkdir(parents=True)
    (tmp_path / "gt/fig/chukchi-1-037.xml").write_text(EXPORT, encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/readings.md").write_text(READINGS, encoding="utf-8")
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
    """Only FigDesc suffixes key `readings.md`, so only they can move a key."""
    assert F.migrate_page("1-037", root)["remap"] == {"ca04178c": "002"}


# --- the readings key --------------------------------------------------------

def test_headers_are_rewritten_and_counted(root):
    text, n = F.remap_readings(READINGS, {"1-037": {"ca04178c": "002"}})
    assert "## 1-037|002" in text and n == 1
    assert "## 2-068|44f33841" in text          # no map for it, left alone


def test_only_headers_move_never_the_caption_text(root):
    """A caption may legitimately print something shaped like a key, so a global
    substitution is the one implementation that must not be used."""
    text = "## 1-037|ca04178c\nSee ca04178c in the plate.\n"
    out, n = F.remap_readings(text, {"1-037": {"ca04178c": "002"}})
    assert out == "## 1-037|002\nSee ca04178c in the plate.\n"
    assert n == 1


# --- the run -----------------------------------------------------------------

def test_a_dry_run_writes_nothing(root):
    before = (root / "gt/fig/chukchi-1-037.xml").read_bytes()
    out = F.migrate_store(root)
    assert out["committed"] is False
    assert (root / "gt/fig/chukchi-1-037.xml").read_bytes() == before
    assert (root / "data/readings.md").read_text() == READINGS


def test_a_commit_moves_both_files_together(root):
    out = F.migrate_store(root, commit=True)
    assert out["committed"] is True
    assert (out["captions"], out["headers_rewritten"]) == (1, 1)

    blocks = F.read_blocks(F.alto_for("1-037", root), with_points=True)
    assert [b["id"] for b in blocks] == ["fig_1-037_001", "fig_1-037_002"]
    # The polygon now agrees with the bbox, which is what `validate_fig_page`'s
    # `not-a-rectangle` error was firing on across the whole un-migrated store.
    cap = next(b for b in blocks if b["label"] == F.FIGDESC)
    assert cap["points"] == "782 2541 1826 2541 1826 2639 782 2639"
    assert "## 1-037|002" in (root / "data/readings.md").read_text()


def test_the_page_reconciles_after(root):
    F.migrate_store(root, commit=True)
    rec = F.reconcile(root)
    assert rec["missing"] == [] and rec["orphan"] == ["2-068|44f33841"]


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


def test_a_reading_naming_no_zone_survives_untouched_for_reconcile_to_name(root):
    """An orphan reading is **not** this pass's to catch, and it does not stop it.

    Its header maps to nothing, so it is left exactly as written and the counts
    still agree — the migration only ever claims that the headers it *could* move
    it did move. Naming orphans is `reconcile`'s job, it already does it in both
    directions, and duplicating that check here would put one fact in two places
    while making the migration refuse over a condition it did not create.
    """
    (root / "data/readings.md").write_text(
        READINGS + "\n## 1-037|deadbeef\nA caption for nothing.\n",
        encoding="utf-8")
    out = F.migrate_store(root, commit=True)
    assert out["committed"] is True
    assert out["headers_rewritten"] == out["captions"] == 1
    assert "## 1-037|deadbeef" in (root / "data/readings.md").read_text()
    assert F.reconcile(root)["orphan"] == ["1-037|deadbeef", "2-068|44f33841"]
