"""The entity record and the rectangle pair, held to their declared key sets.

Companion to `test_line_record.py`, and the two records are here rather than
there because they are the *opposite* trade and saying so is the point.

**The line record is TOON-flat and must stay so**: one ragged record
de-tabularizes the whole table for a collating model. An **entity** record holds
three lists and is rendered as a document, never a row — so raggedness costs it
nothing, and the constraint worth stating is a different one: that `parse` and
`load` return genuinely different shapes, and code holding the first must not
reach for the second's keys.

The **rect pair** is a third case again. ALTO stores a box as origin-plus-extent
because the store is the record; every geometric consumer wants corners, because
overlap and containment are comparisons of edges. Both spellings are correct and
`to_rect` is the conversion — which existed three times, written out identically,
and whose underlying arithmetic appears at eighteen sites in all.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.entities import (
    ALIAS_FIELDS,
    ENTITY_FIELDS,
    LOAD_FIELDS,
    PARSE_FIELDS,
    load,
    parse,
)
from harness.figures import BLOCK_FIELDS, RECT_FIELDS, read_blocks, to_rect

REPO = Path(__file__).resolve().parent.parent.parent
PROJECT = REPO / "jesup" / "bogoras-chukchi"


# ------------------------------------------------------------------ entities

@pytest.fixture(scope="module")
def store() -> dict:
    s = load(PROJECT)
    if not s:
        pytest.skip("edition/entities/ is empty in this checkout")
    return s


def test_the_two_halves_make_the_whole():
    assert PARSE_FIELDS + LOAD_FIELDS == ENTITY_FIELDS
    assert not set(PARSE_FIELDS) & set(LOAD_FIELDS), "a key in both halves"


def test_every_loaded_record_has_the_full_key_set(store):
    for ident, rec in store.items():
        assert tuple(rec) == ENTITY_FIELDS, f"{ident} has keys {tuple(rec)}"


def test_a_parsed_record_has_only_its_own_half(store):
    """**The distinction the split exists for.** `parse` reads one file's text and
    knows nothing about where that file sits; `load` adds the three facts only
    the walk can supply. So a `parse` result has no `path`, and
    `cli/_entity.py` binds one at two sites — today neither subscripts `path`,
    which is luck rather than design. This is what makes it a stated rule."""
    rec = next(iter(store.values()))
    got = parse(Path(rec["path"]).read_text(encoding="utf-8"), where=rec["path"])
    assert tuple(got) == PARSE_FIELDS
    for k in LOAD_FIELDS:
        assert k not in got, f"parse() leaked {k!r}, which only load() can know"
    with pytest.raises(KeyError):
        got["path"]


def test_alias_rows_keep_their_own_closed_set(store):
    """One level down, and this one *is* emitted as a table by `entity show`."""
    rows = [t for rec in store.values() for t in rec["aliases"]]
    assert rows, "no alias rows in the store"
    for t in rows:
        assert tuple(t) == ALIAS_FIELDS, f"alias row has keys {tuple(t)}"


def test_an_unstated_language_is_empty_never_absent(store):
    """`lang: ""` is a claim the store makes on purpose — most of the table is
    the book's own English, where saying so adds nothing. Absent would be a
    different statement, and a ragged row besides."""
    rows = [t for rec in store.values() for t in rec["aliases"]]
    assert any(t["lang"] == "" for t in rows), "no unstated languages at all?"
    assert all(isinstance(t["lang"], str) for t in rows)


# --------------------------------------------------------------- rectangles

def test_a_block_and_its_rect_are_two_spellings_of_one_box():
    b = {"id": "z1", "label": "MainZone-P",
         "hpos": 10, "vpos": 20, "width": 100, "height": 50}
    r = to_rect(b)
    assert tuple(r) == RECT_FIELDS
    assert (r["x0"], r["y0"], r["x1"], r["y1"]) == (10, 20, 110, 70)
    assert r["x1"] - r["x0"] == b["width"]
    assert r["y1"] - r["y0"] == b["height"]


def test_points_ride_along_only_when_asked():
    b = {"id": "z1", "label": "L", "hpos": 0, "vpos": 0, "width": 1, "height": 1,
         "points": "0 0 1 1"}
    assert "points" not in to_rect(b)
    assert to_rect(b, with_points=True)["points"] == "0 0 1 1"


def test_a_block_without_points_still_converts_when_asked():
    """`NotRequired` rather than stamped `None`: the key is genuinely optional
    here, because these records are not emitted as a TOON table and a ragged set
    costs nothing. Copying `LineRec`'s stamping into a place with no encoder
    behind it would be cargo-culting a constraint."""
    b = {"id": "z1", "label": "L", "hpos": 0, "vpos": 0, "width": 1, "height": 1}
    assert to_rect(b, with_points=True)["points"] is None


def test_read_blocks_returns_the_declared_shape():
    src = sorted((PROJECT / "gt" / "fig").glob("chukchi-*.xml"))
    if not src:
        pytest.skip("gt/fig/ is empty in this checkout")
    blocks = read_blocks(src[0])
    assert blocks, "the ALTO produced no blocks"
    for b in blocks:
        assert tuple(b) == BLOCK_FIELDS


def test_read_zones_goes_through_the_one_conversion():
    """`zones.read_zones` built this dict literally and identically to two other
    sites. It routes through `to_rect` now, so the three cannot drift — which is
    `crop_name`'s rule: one function where several callers must agree exactly."""
    from harness import zones

    # The first *keyed* page, not the first file: a plate or a blank is a real
    # leaf with no zones at all, and picking one would test nothing.
    ref = got = None
    for p in sorted((PROJECT / "gt" / "zones").glob("chukchi-*.xml"))[:40]:
        ref = p.stem.replace("chukchi-", "")
        if (got := zones.read_zones(ref, PROJECT)):
            break
    if not got:
        pytest.skip("no keyed page among the first 40 in gt/zones/")
    assert tuple(got[0]) == RECT_FIELDS
    assert tuple(zones.read_zones(ref, PROJECT, with_points=True)[0]) == \
        RECT_FIELDS + ("points",)
