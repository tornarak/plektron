"""The figure store's writes, and the one thing that makes it not the zone store.

`gt/fig/` and `gt/zones/` look like the same store twice: region-only ALTO, a
split list, a rule-exemption file, an atomic save with a `.prev` and a journal.
They differ in exactly one place, and it is the place a copy-paste would land
wrong — **a figure block's id is a foreign key**. `data/readings.md` files 395
hand-read captions under the last field of a block id, so `save_figs` preserves
ids where `save_zones` re-mints them positionally.

That difference cannot be caught downstream. Re-minting produces a well-formed
file with the same block count, the same geometry and the same *set* of id
suffixes, so `harness corpus figures` still reconciles: it compares sets, and the
set is unchanged. Only the pairing moves, and the pairing is what a caption is.
The live case is `1-191`, whose undeclared photograph sorts above all four of its
existing blocks — the acceptance test for the editor track is also this
regression's test, which is why the geometry below is that page's.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_scan

from harness import figures as F

# `1-191` as the migration will leave it: two of its four blocks, ids minted in
# geometric order, and the photograph at y953 that nobody has declared yet.
EXISTING = [
    {"id": "fig_1-191_001", "label": F.GRAPHIC,
     "x0": 1800, "y0": 1420, "x1": 2146, "y1": 2885},
    {"id": "fig_1-191_002", "label": F.FIGDESC,
     "x0": 400, "y0": 1680, "x1": 900, "y1": 1732},
]
PHOTOGRAPH = {"label": F.GRAPHIC, "x0": 530, "y0": 953, "x1": 2020, "y1": 1379}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_scan(tmp_path, "1-191", size=(2824, 3897))
    return tmp_path


def _by_id(root: Path, ref: str = "1-191") -> dict[str, dict]:
    return {b["id"]: b for b in F.read_blocks(F.alto_for(ref, root))}


# --- the foreign key ---------------------------------------------------------

def test_an_inserted_block_does_not_renumber_the_ones_below_it(root):
    """The regression, whole. Insert above everything; ids below must not move."""
    F.save_figs("1-191", EXISTING, root)
    F.save_figs("1-191", [*EXISTING, PHOTOGRAPH], root)

    blocks = _by_id(root)
    assert blocks["fig_1-191_001"]["vpos"] == 1420
    assert blocks["fig_1-191_002"]["vpos"] == 1680
    # The newcomer sorts first on the page and last in the numbering.
    assert blocks["fig_1-191_003"]["vpos"] == 953


def test_the_caption_still_keys_to_the_same_reading(root):
    """What the renumbering would actually cost, stated in the store's own terms."""
    F.save_figs("1-191", EXISTING, root)
    before = {F.zone_suffix(b["id"]) for b in F.read_blocks(F.alto_for("1-191", root))
              if b["label"] == F.FIGDESC}
    F.save_figs("1-191", [*EXISTING, PHOTOGRAPH], root)
    after = {F.zone_suffix(b["id"]) for b in F.read_blocks(F.alto_for("1-191", root))
             if b["label"] == F.FIGDESC}
    assert before == after == {"002"}


def test_a_fresh_page_mints_from_one(root):
    F.save_figs("1-191", [dict(PHOTOGRAPH)], root)
    assert set(_by_id(root)) == {"fig_1-191_001"}


def test_the_mint_floor_comes_from_disk_not_from_the_batch(root):
    """A caller that drops an id must not thereby free the number for reuse.

    The batch alone cannot answer this: `[001, {no id}]` looks like a page whose
    highest ordinal is 1, and minting from it would hand the newcomer `002` — a
    number a caption reading may still name. The floor is the union of what
    arrived and what is already on disk.
    """
    F.save_figs("1-191", [*EXISTING, PHOTOGRAPH], root)      # photograph -> 003
    # Re-save dropping the caption *and* the photograph's id, as a careless
    # caller would.
    F.save_figs("1-191", [EXISTING[0], dict(PHOTOGRAPH)], root)
    ids = set(_by_id(root))
    assert "fig_1-191_002" not in ids       # freed, and stays freed
    assert "fig_1-191_004" in ids           # the newcomer minted past the mark


def test_removing_the_highest_block_does_not_free_its_number(root):
    """The same floor, exercised from the other side: this save is what removes
    the top ordinal, so only the on-disk read still knows about it."""
    F.save_figs("1-191", [*EXISTING, PHOTOGRAPH], root)      # 001 002 003
    F.save_figs("1-191", [EXISTING[0], EXISTING[1],
                          {"label": F.FIGDESC,
                           "x0": 600, "y0": 3000, "x1": 1200, "y1": 3100}], root)
    assert "fig_1-191_004" in set(_by_id(root))


def test_a_mixed_page_mints_past_the_highest_supplied(root):
    """Legacy ids read as ordinal 0, so a fresh mint cannot collide with hex."""
    F.save_figs("1-191", [
        {"id": "eSc_textblock_ca04178c", "label": F.GRAPHIC,
         "x0": 458, "y0": 938, "x1": 2212, "y1": 2543},
        dict(PHOTOGRAPH),
    ], root)
    ids = set(_by_id(root))
    assert "eSc_textblock_ca04178c" in ids
    assert "fig_1-191_001" in ids


# --- durability --------------------------------------------------------------

def test_a_save_leaves_a_prev_and_a_journal_line(root):
    F.save_figs("1-191", EXISTING, root, stamp="2026-08-07T00:00:00+0000")
    assert not (root / "gt/fig/chukchi-1-191.xml.prev").exists()
    F.save_figs("1-191", [*EXISTING, PHOTOGRAPH], root,
                stamp="2026-08-07T00:00:01+0000")
    assert (root / "gt/fig/chukchi-1-191.xml.prev").exists()
    assert not (root / "gt/fig/chukchi-1-191.xml.tmp").exists()

    lines = [json.loads(ln) for ln in
             (root / "gt/fig" / F.JOURNAL).read_text().splitlines()]
    assert [ln["blocks"] for ln in lines] == [2, 3]
    assert lines[0]["labels"] == {F.GRAPHIC: 1, F.FIGDESC: 1}


def test_the_page_lands_in_train_unless_told_otherwise(root):
    F.save_figs("1-191", EXISTING, root)
    assert F.load_splits(root) == {"1-191": "train"}
    F.save_figs("1-191", EXISTING, root, split="eval")
    assert F.load_splits(root) == {"1-191": "eval"}


def test_a_split_mark_is_not_moved_by_a_later_save(root):
    """Re-saving a held-out page must not quietly return it to training."""
    F.save_figs("1-191", EXISTING, root, split="eval")
    F.save_figs("1-191", [*EXISTING, PHOTOGRAPH], root)
    assert F.load_splits(root) == {"1-191": "eval"}


# --- the refusals ------------------------------------------------------------

def test_an_empty_page_is_refused_and_names_the_way_out(root):
    """No `exempt` escape here: absence of the file already means 'no figures',
    so an empty ALTO would assert the opposite of what it records."""
    F.save_figs("1-191", EXISTING, root)
    with pytest.raises(ValueError) as e:
        F.save_figs("1-191", [], root)
    assert "fig delete" in str(e.value)


def test_a_body_zone_label_is_refused(root):
    with pytest.raises(ValueError) as e:
        F.save_figs("1-191", [{"label": "MainZone-P",
                               "x0": 300, "y0": 100, "x1": 2000, "y1": 400}], root)
    assert "gt/zones/" in str(e.value)


# --- withdrawal --------------------------------------------------------------

def test_delete_previews_before_it_commits(root):
    F.save_figs("1-191", EXISTING, root)
    out = F.delete_figs("1-191", root)
    assert out["committed"] is False
    assert F.alto_for("1-191", root).exists()
    assert out["captions_orphaned"] == 1


def test_delete_removes_the_file_and_every_mark(root):
    F.save_figs("1-191", EXISTING, root, split="eval",
                rules={"captions-lte-figures": "two captions to one plate here"})
    F.delete_figs("1-191", root, commit=True)
    assert not F.alto_for("1-191", root).exists()
    assert F.load_splits(root) == {}
    assert F.load_rule_exempt(root) == {}
    assert (root / "gt/fig/chukchi-1-191.xml.prev").exists()


def test_deleting_what_is_not_there_says_so_rather_than_raising(root):
    out = F.delete_figs("1-191", root, commit=True)
    assert out["note"] == "nothing to delete"


def test_delete_reports_the_readings_it_orphans_rather_than_touching_them(root):
    """Geometry withdrawal must not cascade into hand-read text. The count is the
    warning; `harness corpus figures` is where the orphans then surface."""
    F.save_figs("1-191", [*EXISTING, PHOTOGRAPH], root)
    out = F.delete_figs("1-191", root, commit=True)
    assert out["captions_orphaned"] == 1
    assert not (root / "data").exists()


# --- the sidecars are this store's own ---------------------------------------

def test_the_splits_live_under_gt_fig_not_gt_zones(root):
    F.save_figs("1-191", EXISTING, root, split="eval")
    assert (root / "gt/fig/_eval.lst").exists()
    assert not (root / "gt/zones/_eval.lst").exists()


def test_a_listed_ref_need_not_name_an_existing_file(root):
    """The lists carry negatives — pages with no figures on them — and a negative
    is exactly a ref with no ALTO. `assemble` synthesizes the empty region set;
    the store never holds one."""
    F.set_split("1-048", "train", root)
    assert F.load_splits(root) == {"1-048": "train"}
    assert not F.alto_for("1-048", root).exists()


def test_eval_wins_a_contradiction(root):
    (root / "gt/fig").mkdir(parents=True, exist_ok=True)
    (root / "gt/fig/_train.lst").write_text("chukchi-1-191.xml\n")
    (root / "gt/fig/_eval.lst").write_text("chukchi-1-191.xml\n")
    assert F.load_splits(root) == {"1-191": "eval"}


def test_there_is_no_exempt_split(root):
    """Plates are where figures live; holding them out would hold out the corpus."""
    assert F.FIG_SPLITS == ("train", "eval")
    with pytest.raises(ValueError):
        F.set_split("1-191", "exempt", root)
