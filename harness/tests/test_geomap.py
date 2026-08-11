"""The shape store, the projection, and the map.

The store is compiled and tracked, so most of these run against the real
`data/geo/` — that is the thing the reading view draws, and a fixture would
test a shape nobody looks at. What is *not* asserted anywhere here is that a
delineation is correct: the sources say what they say, and `geo verify`
reports the disagreements rather than this suite pretending to adjudicate them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import entities, geo, geomap

ROOT = Path(__file__).resolve().parent.parent.parent
built = pytest.mark.skipif(
    not (ROOT / "data" / "geo" / "index.json").exists(),
    reason="data/geo/ has not been built — see tools/build_geo.py")


# ------------------------------------------------------------ the store

def test_an_unbuilt_store_is_empty_rather_than_an_error(tmp_path):
    """Every other verb has to keep working in a tree where the atlas has not
    been compiled, so absence is `{}` — the `readings`/`load` pattern."""
    assert geo.index(tmp_path)["shapes"] == {}
    assert geo.shape("watershed:anadyr", tmp_path) == {}


@built
def test_the_shape_kinds_are_disjoint_from_the_entity_classes():
    """`langarea:`, never `language:`. An entity file carries `within:
    place:chukotka` two lines from `area: langarea:chuk1273`, and a kind that
    was also a class would make the second readable as the first."""
    kinds = {i.split(":")[0] for i in geo.index(ROOT)["shapes"]}
    assert kinds and not (kinds & set(entities.ENTITY_CLASSES))


@built
def test_the_absences_are_rows_and_not_silences():
    """A people the sources do not draw has to be *in* the census. An entity
    pointing at nothing and an entity nobody has got to yet look identical from
    outside, and only one of them is finished."""
    absent = geo.index(ROOT)["absent"]
    assert {"ypk", "xcv"} <= set(absent)
    assert all(absent.values())


@built
def test_longitudes_are_continuous_across_the_antimeridian():
    """Chukotka runs past 180 rather than wrapping to −180. This is what lets
    every planar operation downstream — containment, extents, culling — treat a
    shape spanning the meridian as an ordinary one."""
    doc = geo.shape("watershed:anadyr", ROOT)
    xs = [x for ring in geo.rings(doc) for x, _ in ring]
    assert max(xs) > 178
    assert min(xs) > 0


def test_an_area_naming_an_entity_class_is_refused():
    """The collision this guards is silent: `area: language:chukchee` parses as
    a well-formed id and resolves to nothing, in a file whose next field is a
    genuine entity reference."""
    text = ("# place:x — X\n\n- status: proposed\n- since: 1-021\n"
            "- area: language:chukchee\n\n## triggers\n\n| form | auto | note |\n"
            "|---|---|---|\n\n## gloss\n\nx\n")
    with pytest.raises(entities.Malformed, match="entity class"):
        entities.parse(text)


def test_a_wellformed_area_parses_and_is_carried():
    text = ("# place:x — X\n\n- status: proposed\n- since: 1-021\n"
            "- area: watershed:anadyr\n\n## triggers\n\n| form | auto | note |\n"
            "|---|---|---|\n\n## gloss\n\nx\n")
    assert entities.parse(text)["area"] == "watershed:anadyr"


# ------------------------------------------------------------ containment

@built
def test_containment_separates_a_true_relation_from_a_false_one():
    """The check has to be able to fail, or its passing says nothing.

    Measured on the real store: relations the book and the map both support
    land at 0.68–0.82, and a river paired with a basin it has nothing to do
    with lands at 0.00–0.11. The floor sits in the gap, not near either.
    """
    true = geo.contains(geo.shape("watershed:kolyma", ROOT),
                        geo.shape("watershed:omolon", ROOT))
    false = geo.contains(geo.shape("watershed:anadyr", ROOT),
                         geo.shape("watershed:omolon", ROOT))
    assert true > geo.COARSE_FLOOR > false


def test_a_coarse_delineation_is_not_read_as_a_disagreement():
    """The delineator reverts to a coarse DEM above 50,000 km² and says so, and
    every containment pair in this store has a member it said that about. A
    reading that ignored the declaration would reject true rows on the strength
    of a limitation the source announced in advance."""
    assert geo._reading(0.75, coarse=True) != "disagrees"
    assert geo._reading(0.75, coarse=False) == "disagrees"
    assert geo._reading(0.05, coarse=True) == "disagrees"


@built
def test_verify_reports_and_never_gates():
    r = geo.verify(ROOT)
    assert set(r) == {"scope", "containment", "points", "shared", "unclaimed"}
    assert all("reading" in row for row in r["containment"])


@built
def test_two_entities_may_share_one_shape():
    """`people:chukchee` and `language:chukchee` both point at the one Asher
    polygon. Forcing a choice would be this edition deciding something the
    source does not — so it is reported, not refused."""
    assert entities.check(ROOT)["ok"]
    assert any(row["shape"] == "langarea:chuk1273"
               for row in geo.verify(ROOT)["shared"])


# ------------------------------------------------------------ the extent

def _store(tmp_path, *recs):
    for ident, extra in recs:
        cls, slug = ident.split(":")
        p = tmp_path / "entities" / cls / f"{slug}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {ident} — {slug}\n\n- status: ratified\n- since: 1-021\n"
                     f"{extra}\n## triggers\n\n| form | auto | note |\n|---|---|---|\n"
                     f"\n## gloss\n\nx\n", encoding="utf-8")
    return entities.load(tmp_path)


def test_a_parent_with_its_own_point_still_frames_its_children(tmp_path):
    """The bug this pins was invisible in every number and obvious on the map:
    a parent that stopped at its own `geo:` framed on that point alone, and its
    children fell outside their own parent's map."""
    store = _store(tmp_path,
                   ("place:p", "- geo: 66.0 170.0\n"),
                   ("place:c", "- within: place:p\n- geo: 60.0 178.0\n"))
    box = geo.extent_of("place:p", store, tmp_path)
    assert box[1] < 60.5 and box[2] > 177.5


def test_an_entity_with_nothing_beneath_it_has_no_extent(tmp_path):
    store = _store(tmp_path, ("place:p", ""))
    assert geo.extent_of("place:p", store, tmp_path) is None
    assert not geo.located("place:p", store, tmp_path)


def test_a_within_cycle_does_not_hang_the_extent_walk(tmp_path):
    """`entity check` gates acyclicity, but this runs inside a page render,
    where a hang is worse than a wrong answer."""
    store = _store(tmp_path, ("place:a", "- within: place:b\n"),
                   ("place:b", "- within: place:a\n"))
    assert geo.extent_of("place:a", store, tmp_path) is None


# ------------------------------------------------------------ the map

def test_the_projection_has_no_seam_at_the_antimeridian():
    """The reason it is azimuthal. 185 and −175 are the same meridian, and a
    projection that disagreed would tear every shape in Chukotka in half."""
    a = geomap.project(185.0, 66.0, 176.0, 65.0)
    b = geomap.project(-175.0, 66.0, 176.0, 65.0)
    assert a == pytest.approx(b)


def test_the_projection_is_undefined_at_the_antipode_and_says_so():
    assert geomap.project(-4.0, -65.0, 176.0, 65.0) is None


def test_a_frame_is_a_unit_box_whatever_it_frames():
    """One viewBox for every map, so one decimal place is enough at every zoom
    — and so no map carries a size in pixels."""
    boxes = [(100.0, 40.0, 200.0, 75.0), (176.0, 65.0, 176.2, 65.2)]
    frames = [geomap.Frame(b) for b in boxes]
    assert {f.viewbox for f in frames} == {"0 0 1000 1000"}
    # Not "the projection centre lands at 500,500": at 70°N the projected
    # extent of a box is not symmetric about its own centre, and a frame that
    # forced it to be would have to crop one edge to do it. What must hold is
    # that what was asked for is inside what is drawn.
    for f, (w, s, e, n) in zip(frames, boxes, strict=True):
        for lon, lat in ((w, s), (e, n), (w, n), (e, s)):
            x, y = f._at(lon, lat)
            assert 0 <= x <= 1000 and 0 <= y <= 1000


def test_the_frame_measures_along_its_edges_and_not_at_its_corners():
    """At 70°N the top edge of a wide box bows well past its own corners, so a
    frame taken from four points clips the shape it was computed for."""
    box = (150.0, 60.0, 200.0, 72.0)
    f = geomap.Frame(box)
    for lon in (150.0, 165.0, 175.0, 185.0, 200.0):
        for lat in (60.0, 66.0, 72.0):
            x, y = f._at(lon, lat)
            assert -1 <= x <= 1001 and -1 <= y <= 1001, (lon, lat, x, y)


@built
def test_a_ring_that_cannot_touch_the_frame_is_dropped():
    """The cull is the difference between a 130 KB card and an 18 KB one."""
    f = geomap.Frame(geo.bounds(geo.shape("watershed:wolverine-or-keperveyem", ROOT)))
    land = geo.shape("base:land", ROOT)
    assert len(f.paths(land)) < len(list(geo.rings(land)))


@built
def test_a_map_is_svg_with_no_pixel_dimension_on_it():
    f = geomap.Frame(geo.bounds(geo.shape("watershed:anadyr", ROOT)))
    svg = geomap.render(f, {"subject": f.paths(geo.shape("watershed:anadyr", ROOT))})
    assert svg.startswith("<svg") and "viewBox='0 0 1000 1000'" in svg
    assert "px" not in svg and "width=" not in svg


def test_a_pin_label_is_escaped_and_turns_inward_at_the_edge():
    f = geomap.Frame((150.0, 60.0, 200.0, 72.0))
    svg = geomap.render(f, {}, pins=[(950.0, 500.0, "<script>"),
                                     (100.0, 500.0, "Markova")])
    assert "<script>" not in svg and "&lt;script&gt;" in svg
    assert svg.count("text-anchor='end'") == 1
    assert svg.count("text-anchor='start'") == 1


@built
def test_the_index_is_reread_when_the_store_changes(tmp_path):
    """`edition serve` is long-lived and the cache is keyed on mtime, so a
    rebuild is picked up without a restart — a server that had to be restarted
    would teach people to rebuild less."""
    d = tmp_path / "data" / "geo"
    d.mkdir(parents=True)
    p = d / "index.json"
    p.write_text(json.dumps({"shapes": [{"id": "watershed:a", "file": "x.json"}]}))
    assert set(geo.index(tmp_path)["shapes"]) == {"watershed:a"}
    p.write_text(json.dumps({"shapes": [{"id": "watershed:b", "file": "x.json"}]}))
    import os
    os.utime(p, (0, 0))
    assert set(geo.index(tmp_path)["shapes"]) == {"watershed:b"}
