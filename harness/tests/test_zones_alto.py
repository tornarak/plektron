"""`gt/zones/` store I/O: the ALTO round trip, the split lists, the exemptions.

The properties tested here are the ones a later reader will assume without
checking. Two matter more than the rest.

**Labels resolve through TAGREFS, never through the tag ID.** The ids are assigned
per export, and hardcoding them cost a migration once — one that "quietly became a
no-op and reported success" (`git log -- tools/strip_graphiczone_lines.py`).
`test_labels_survive_renumbered_tag_ids` perturbs every id in a written file and
demands the labels still come back, which is the only form of that test that would
have failed then.

**A file with no blocks is a record, not an absence.** A plate has no text column,
so its correct segmentation is zero zones; a page nobody opened is also zero zones.
Only the file's existence separates them, which is why `has_zones` asks about the
file and why the UI never writes one on navigation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_scan
from lxml import etree

from harness import zones as zn


def make_scan(tmp_path: Path, ref: str = "1-048",
              size: tuple[int, int] = (2824, 3897)) -> Path:
    """A raster of the right dimensions. Page dims are read from it, not assumed."""
    return write_scan(tmp_path, ref, size)


def sample() -> list[dict]:
    return [
        {"label": "RunningTitleZone", "x0": 618, "y0": 214, "x1": 2410, "y1": 268},
        {"label": "MainZone-Continued", "x0": 618, "y0": 320, "x1": 2410, "y1": 900},
        {"label": "MainZone-P", "x0": 618, "y0": 900, "x1": 2410, "y1": 2800},
        {"label": "MarginTextZone-Notes", "x0": 618, "y0": 2900, "x1": 2410, "y1": 3200},
    ]


def test_round_trip_preserves_labels_and_geometry(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    got = zn.read_zones("1-048", tmp_path)
    assert [(z["label"], z["y0"], z["y1"]) for z in got] == [
        ("RunningTitleZone", 214, 268), ("MainZone-Continued", 320, 900),
        ("MainZone-P", 900, 2800), ("MarginTextZone-Notes", 2900, 3200)]
    assert all(z["x0"] == 618 and z["x1"] == 2410 for z in got)


def test_labels_survive_renumbered_tag_ids(tmp_path):
    """The invariant that has already failed once in this repo, tested the only
    way that would have caught it: rewrite every tag id and re-read."""
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    p = zn.alto_for("1-048", tmp_path)
    tree = etree.parse(str(p))
    remap = {}
    for i, tag in enumerate(tree.iter("{*}OtherTag")):
        old = tag.get("ID")
        remap[old] = f"BT{90 + i}"
        tag.set("ID", remap[old])
    for blk in tree.iter("{*}TextBlock"):
        blk.set("TAGREFS", remap[blk.get("TAGREFS")])
    tree.write(str(p), xml_declaration=True, encoding="UTF-8")
    got = zn.read_zones("1-048", tmp_path)
    assert [z["label"] for z in got] == [
        "RunningTitleZone", "MainZone-Continued", "MainZone-P",
        "MarginTextZone-Notes"]


def test_page_dims_come_from_the_raster(tmp_path):
    """Not from a per-part table. Part 3's pages are 2481x3508 and part 1's are
    not, and a wrong Page box silently rescales every coordinate downstream."""
    make_scan(tmp_path, "3-005", (2481, 3508))
    zn.save_zones("3-005", [{"label": "MainZone-P", "x0": 310, "y0": 400,
                             "x1": 2109, "y1": 1200}], tmp_path)
    page = etree.parse(str(zn.alto_for("3-005", tmp_path))).find(".//{*}Page")
    assert (page.get("WIDTH"), page.get("HEIGHT")) == ("2481", "3508")
    ps = page.find("{*}PrintSpace")
    assert (ps.get("WIDTH"), ps.get("HEIGHT")) == ("2481", "3508")


def test_blocks_carry_the_provenance_prefix(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    ids = [z["id"] for z in zn.read_zones("1-048", tmp_path)]
    assert all(i.startswith(zn.ID_PREFIX) for i in ids)
    assert len(set(ids)) == len(ids)


def test_no_textlines_are_written(tmp_path):
    """These are regions. A line-level witness would be a second claim about the
    page that nothing here verified — the reason gt/fig/ carries none either."""
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    tree = etree.parse(str(zn.alto_for("1-048", tmp_path)))
    assert list(tree.iter("{*}TextLine")) == []
    assert list(tree.iter("{*}String")) == []


def test_only_used_labels_are_declared(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample()[:2], tmp_path)
    tree = etree.parse(str(zn.alto_for("1-048", tmp_path)))
    assert sorted(t.get("LABEL") for t in tree.iter("{*}OtherTag")) == [
        "MainZone-Continued", "RunningTitleZone"]


def test_zones_are_written_in_reading_order(tmp_path):
    """Input arrives in click order, which is not top-to-bottom after an insert."""
    make_scan(tmp_path)
    zn.save_zones("1-048", list(reversed(sample())), tmp_path)
    got = zn.read_zones("1-048", tmp_path)
    assert [z["y0"] for z in got] == sorted(z["y0"] for z in got)


def test_ruling_a_leaf_records_the_mark_and_no_file(tmp_path):
    """**`exempt => no zones`**, and the mark is the whole record.

    This asserted the opposite until the leaf kinds settled what an exempt page
    is: an empty ALTO used to be how "a plate's correct segmentation is zero
    zones" was said, and `has_zones` was how a caller asked whether a human had
    been through. Both jobs moved to the split mark, and the file became one fact
    stated twice with the weaker spelling surviving a `cp -r`. `keyed` is the
    predicate for "settled" now; `has_zones` is only ever about the file."""
    make_scan(tmp_path, "1-001")
    assert zn.keyed("1-001", tmp_path) is False
    zn.save_zones("1-001", [], tmp_path, split="plate")
    assert zn.has_zones("1-001", tmp_path) is False
    assert zn.keyed("1-001", tmp_path) is True
    assert zn.read_zones("1-001", tmp_path) == []


def test_unkeyed_page_reads_empty_without_a_file(tmp_path):
    assert zn.read_zones("2-100", tmp_path) == []
    assert zn.has_zones("2-100", tmp_path) is False


def test_resave_keeps_the_previous_version(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    zn.save_zones("1-048", sample()[:1], tmp_path)
    prev = zn.alto_for("1-048", tmp_path).with_suffix(".xml.prev")
    assert prev.exists()
    assert len(list(etree.parse(str(prev)).iter("{*}TextBlock"))) == 4
    assert len(zn.read_zones("1-048", tmp_path)) == 1


def test_every_save_appends_to_the_journal(tmp_path):
    """`.prev` is one deep; two saves in a row destroy it. Nothing destroys this."""
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path, stamp="2026-07-31T10:00:00+0000")
    zn.save_zones("1-048", sample()[:2], tmp_path, stamp="2026-07-31T10:01:00+0000")
    lines = [json.loads(ln) for ln in
             (zn.zone_dir(tmp_path) / zn.JOURNAL).read_text().splitlines()]
    assert [e["zones"] for e in lines] == [4, 2]
    assert lines[0]["labels"]["MainZone-P"] == 1


def test_no_tmp_file_survives_a_save(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    assert list(zn.zone_dir(tmp_path).glob("*.tmp")) == []


def test_missing_raster_refuses_rather_than_guessing_dimensions(tmp_path):
    with pytest.raises(FileNotFoundError, match="no raster"):
        zn.save_zones("1-048", sample(), tmp_path)


# ------------------------------------------------------------------- the split

def test_a_saved_page_defaults_to_train(tmp_path):
    """Held out has to be deliberate — a default of eval would quietly shrink
    the training set as keying proceeds."""
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    assert zn.load_splits(tmp_path) == {"1-048": "train"}


def test_split_marking_never_leaves_a_ref_in_both_lists(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    zn.set_split("1-048", "eval", tmp_path)
    zn.set_split("1-048", "train", tmp_path)
    zn.set_split("1-048", "eval", tmp_path)
    train = (zn.zone_dir(tmp_path) / zn.TRAIN_LST).read_text().split()
    ev = (zn.zone_dir(tmp_path) / zn.EVAL_LST).read_text().split()
    assert train == [] and ev == ["chukchi-1-048.xml"]
    assert zn.load_splits(tmp_path) == {"1-048": "eval"}


def test_resaving_does_not_reset_an_existing_mark(tmp_path):
    """Keying a page again must not silently pull it back into training."""
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    zn.set_split("1-048", "eval", tmp_path)
    zn.save_zones("1-048", sample()[:2], tmp_path)
    assert zn.load_splits(tmp_path) == {"1-048": "eval"}


def test_lists_use_the_gt_seg_filename_format(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    assert (zn.zone_dir(tmp_path) / zn.TRAIN_LST).read_text() == "chukchi-1-048.xml\n"


def test_lists_stay_in_page_order(tmp_path):
    for ref in ("2-100", "1-048", "1-151"):
        make_scan(tmp_path, ref)
        zn.save_zones(ref, sample(), tmp_path)
    assert (zn.zone_dir(tmp_path) / zn.TRAIN_LST).read_text().split() == [
        "chukchi-1-048.xml", "chukchi-1-151.xml", "chukchi-2-100.xml"]


def test_a_ref_in_both_lists_resolves_to_eval(tmp_path):
    """The safe reading of a contradiction is the one that honours the exclusion."""
    zn.zone_dir(tmp_path).mkdir(parents=True)
    (zn.zone_dir(tmp_path) / zn.TRAIN_LST).write_text("chukchi-1-048.xml\n")
    (zn.zone_dir(tmp_path) / zn.EVAL_LST).write_text("chukchi-1-048.xml\n")
    assert zn.load_splits(tmp_path) == {"1-048": "eval"}


def test_a_leaf_kind_wins_over_every_other_list(tmp_path):
    """Most exclusionary wins. Every one of these lists exists to keep pages out
    of something, so a contradiction resolves to the exclusion — never to
    training on a plate."""
    zn.zone_dir(tmp_path).mkdir(parents=True)
    for lst in (zn.TRAIN_LST, zn.EVAL_LST, "_plate.lst"):
        (zn.zone_dir(tmp_path) / lst).write_text("chukchi-1-049.xml\n")
    assert zn.load_splits(tmp_path) == {"1-049": "plate"}


def test_is_exempt_answers_for_a_page_nobody_has_marked(tmp_path):
    """Three states, and the predicate must not collapse the third into the first.

    Unmarked is *not reached yet*; `train`/`eval` are text pages; a leaf kind is a
    ruling. `is_exempt` answers False for the first two and True only for the
    third — so an unkeyed page can never be mistaken for one a human ruled out,
    which is the distinction the three lists exist to keep.
    """
    zn.zone_dir(tmp_path).mkdir(parents=True)
    assert zn.is_exempt("1-048", tmp_path) is False      # nobody has looked
    (zn.zone_dir(tmp_path) / zn.TRAIN_LST).write_text("chukchi-1-048.xml\n")
    assert zn.is_exempt("1-048", tmp_path) is False
    zn.set_split("1-048", "blank", tmp_path)
    assert zn.is_exempt("1-048", tmp_path) is True
    # The splits a caller already holds are the same answer, not a cheaper one.
    assert zn.is_exempt("1-048", tmp_path,
                        splits=zn.load_splits(tmp_path)) is True


@pytest.mark.parametrize("kind", zn.LEAF_KINDS)
def test_a_page_can_be_ruled_any_leaf_kind(tmp_path, kind):
    """Looked at, ruled out, and *said what it is*. A different statement from
    'keyed and holds nothing', and a very different one from 'not reached yet'.

    Over the whole vocabulary rather than one member, because the list a kind
    lands in is derived from its name — so a kind whose file the store could not
    write would be silently unreachable rather than raising."""
    make_scan(tmp_path, "1-049")
    zn.save_zones("1-049", [], tmp_path, split=kind)
    assert zn.load_splits(tmp_path) == {"1-049": kind}
    assert zn.is_exempt("1-049", tmp_path) is True
    # Settled, and holding nothing: the ruling is the record and the store is empty.
    assert zn.keyed("1-049", tmp_path) is True
    assert zn.has_zones("1-049", tmp_path) is False
    assert (zn.zone_dir(tmp_path) / f"_{kind}.lst").read_text() \
        == "chukchi-1-049.xml\n"
    assert (zn.zone_dir(tmp_path) / zn.TRAIN_LST).read_text() == ""


def test_ruling_a_leaf_removes_it_from_training(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path)
    assert zn.load_splits(tmp_path) == {"1-048": "train"}
    zn.set_split("1-048", "plate", tmp_path)
    assert (zn.zone_dir(tmp_path) / zn.TRAIN_LST).read_text() == ""
    assert zn.load_splits(tmp_path) == {"1-048": "plate"}


def test_re_ruling_a_leaf_leaves_no_member_behind(tmp_path):
    """`set_split` sweeps every list, not the pair it is moving between — so a
    leaf re-ruled from `plate` to `blank` is in exactly one. Two kinds share a
    rank, so a leaf left in both would resolve by `SPLITS` order rather than by
    the human's last act, and would keep resolving that way silently."""
    make_scan(tmp_path, "1-049")
    zn.save_zones("1-049", [], tmp_path, split="plate")
    zn.set_split("1-049", "blank", tmp_path)
    assert (zn.zone_dir(tmp_path) / "_plate.lst").read_text() == ""
    assert zn.load_splits(tmp_path) == {"1-049": "blank"}


def test_bad_split_name_refused(tmp_path):
    with pytest.raises(ValueError, match="train"):
        zn.set_split("1-048", "holdout", tmp_path)


# -------------------------------------------------------------------- exempt

def test_exemptions_round_trip(tmp_path):
    zn.set_exempt("1-048", ["rank-monotone"], tmp_path)
    assert zn.load_exempt(tmp_path) == {"1-048": ["rank-monotone"]}


def test_clearing_an_exemption_removes_the_ref(tmp_path):
    zn.set_exempt("1-048", ["rank-monotone"], tmp_path)
    zn.set_exempt("1-048", [], tmp_path)
    assert zn.load_exempt(tmp_path) == {}


def test_exempt_file_about_key_is_not_a_ref(tmp_path):
    """The file explains itself in-band; that note must not read back as a page."""
    zn.set_exempt("1-048", ["title-first"], tmp_path)
    raw = json.loads((zn.zone_dir(tmp_path) / zn.RULE_EXEMPT_JSON).read_text())
    assert "_about" in raw
    assert "_about" not in zn.load_exempt(tmp_path)


def test_save_can_set_split_and_exempt_together(tmp_path):
    make_scan(tmp_path)
    zn.save_zones("1-048", sample(), tmp_path, split="eval",
                  exempt=["rank-monotone"])
    assert zn.load_splits(tmp_path) == {"1-048": "eval"}
    assert zn.load_exempt(tmp_path) == {"1-048": ["rank-monotone"]}


def test_zone_refs_lists_keyed_pages_in_page_order(tmp_path):
    """**Keyed text pages, which is what the store holds a file for.** These were
    ruled plates and so held an empty ALTO apiece; under `exempt => no zones` a
    ruled leaf holds nothing, so the pages have to carry real zones for this to
    be a test of the ordering rather than of the exemption."""
    for ref in ("3-005", "1-048", "1-151"):
        make_scan(tmp_path, ref, (2481, 3508) if ref.startswith("3") else (2824, 3897))
        zn.save_zones(ref, sample()[:1], tmp_path)
    assert zn.zone_refs(tmp_path) == ["1-048", "1-151", "3-005"]
