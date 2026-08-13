"""`harness geo bounds` — the measurement a `frame:` is written from.

It exists because writing the two frames in the store meant a `python -c`
around `geo.extent_of` twice, which is the tell CLAUDE.md names: a one-off
script means a tool is missing or under-used.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness import entities, geo

ROOT = Path(__file__).resolve().parent.parent.parent
built = pytest.mark.skipif(
    not (ROOT / "data" / "geo" / "index.json").exists(),
    reason="data/geo/ is not built in this checkout")


@built
def test_an_entity_and_a_shape_are_told_apart_by_their_prefix():
    """Decidable only because a shape kind may never be an entity class — the
    rule `entities.parse` enforces so `area: language:x` cannot read as an
    entity reference. So this needs no flag and can make no wrong guess."""
    got = geo.boxes(["land:kamchatka", "region:kamchatka"], ROOT)
    assert [r["kind"] for r in got["rows"]] == ["entity", "shape"]


@built
def test_an_entitys_box_is_wider_than_its_own_shape_when_children_lie_outside():
    """An entity's extent is its shape, else its point, else what lies beneath —
    and children are unioned in even where it has a shape of its own, or a
    parent could not show them. `land:kamchatka` draws `region:kamchatka` and
    holds `river:opuka`, which the peninsula polygon does not contain."""
    ent = geo.boxes(["land:kamchatka"], ROOT)["rows"][0]
    shp = geo.boxes(["region:kamchatka"], ROOT)["rows"][0]
    assert ent["east"] > shp["east"]


@built
def test_the_union_is_the_frame_string_entity_locate_takes():
    """Paste-ready, in the store's shifted longitudes — the same window
    `--frame` reads — so the answer is not retyped out of four columns."""
    got = geo.boxes(["river:yana", "land:wrangel-island"], ROOT)
    u = got["union"][0]
    assert u["frame"] == f"{u['west']:g} {u['south']:g} {u['east']:g} {u['north']:g}"
    store = entities.load(ROOT)
    for i in ("river:yana", "land:wrangel-island"):
        w, s, e, n = geo.extent_of(i, store, ROOT)
        assert u["west"] <= w and u["south"] <= s
        assert u["east"] >= e and u["north"] >= n


@built
def test_margin_is_degrees_on_all_four_sides():
    plain = geo.boxes(["region:kamchatka"], ROOT)["union"][0]
    wide = geo.boxes(["region:kamchatka"], ROOT, margin=2.0)["union"][0]
    assert wide["west"] == pytest.approx(plain["west"] - 2.0)
    assert wide["north"] == pytest.approx(plain["north"] + 2.0)


@built
def test_an_id_with_no_extent_is_a_row_and_not_a_silence():
    """`place:cape-prince-of-wales` is named by the book and located by nothing,
    and it is the east edge of `land:northeast-siberia`'s frame — which had to
    be estimated by hand. A tool that dropped it from the list would have made
    that estimate look like a measurement."""
    got = geo.boxes(["place:cape-prince-of-wales", "river:yana"], ROOT)
    rows = {r["id"]: r for r in got["rows"]}
    assert rows["place:cape-prince-of-wales"]["west"] is None
    # And it does not drag the union anywhere.
    assert got["union"][0]["west"] == rows["river:yana"]["west"]


@built
def test_an_unknown_id_says_which_vocabulary_it_was_looked_for_in():
    got = geo.boxes(["place:nowhere", "marine:nope"], ROOT)
    assert [r["kind"] for r in got["rows"]] == ["unknown entity", "unknown shape"]
    assert got["union"] == []
