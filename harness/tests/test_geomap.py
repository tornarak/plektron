"""The shape store, the projection, and the map.

The store is compiled and tracked, so most of these run against the real
`data/geo/` — that is the thing the reading view draws, and a fixture would
test a shape nobody looks at. What is *not* asserted anywhere here is that a
delineation is correct: the sources say what they say, and `geo verify`
reports the disagreements rather than this suite pretending to adjudicate them.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from harness import edition_ui, entities, geo, geomap

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
    """**This is what makes one `geo:` field able to hold three kinds of member.**
    A member is a point if it is two numbers, a shape if its kind is not an
    entity class, and an entity if it is — decidable by prefix alone, with no
    flag and no wrong guess available, and only because the two vocabularies are
    held apart. An entity file carries `within: land:chukotka` two lines from
    `geo: langarea:chuk1273`, and a kind that was also a class would make the
    second readable as the first."""
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


def _entity_text(*members: str) -> str:
    lines = "".join(f"- geo: {m}\n" for m in members)
    return ("# place:x — X\n\n- status: proposed\n- since: 1-021\n"
            f"{lines}\n## aliases\n\n| form | lang | auto | note |\n"
            "|---|---|---|---|\n\n## gloss\n\nx\n")


def test_a_member_whose_kind_is_an_entity_class_is_read_as_a_reference():
    """**The inversion at the centre of the change.** `area: place:chukchee`
    used to be refused, because a shape id whose kind was an entity class parsed
    as a well-formed shape and resolved to nothing, in a file whose next field
    was a genuine entity reference. It *is* a reference now: the same
    disjointness that made the collision worth refusing is what makes the
    reading unambiguous, and the field takes all three kinds because of it."""
    rec = entities.parse(_entity_text("place:chukchee"))
    assert entities.geo_refs(rec) == ["place:chukchee"]
    assert entities.geo_shapes(rec) == []


def test_a_member_of_each_kind_parses_and_is_carried():
    """One field, three readings, told apart by the member's own spelling."""
    rec = entities.parse(_entity_text(
        "watershed:anadyr", "66.05 -169.6", "place:uelen"))
    assert entities.geo_shapes(rec) == ["watershed:anadyr"]
    assert entities.geo_points(rec) == [(66.05, -169.6)]
    assert entities.geo_refs(rec) == ["place:uelen"]
    # And back out as authored, which is what the CLI reports and a migration
    # diffs — no caller has to know how a point is spelled to print one.
    assert entities.spell_geo(rec) == [
        "watershed:anadyr", "66.05 -169.6", "place:uelen"]


def test_several_members_are_kept_apart_and_in_the_order_authored():
    """Where a composite `area:` sorted its members into one canonical string so
    the union could not exist under two spellings, a repeatable field has no
    union to name: the members are separate lines and stay in the order somebody
    wrote them."""
    rec = entities.parse(_entity_text("watershed:anadyr", "langarea:chuk1273"))
    assert entities.geo_shapes(rec) == ["watershed:anadyr", "langarea:chuk1273"]


def test_every_member_is_held_to_the_same_rule():
    """Per member, not on the first one, and the message names the member. A
    member that is neither two degrees nor a `kind:slug` is refused outright:
    the three forms are exhaustive, so anything else is a typo rather than a
    fourth kind nobody has implemented yet."""
    with pytest.raises(entities.Malformed, match="three things"):
        entities.parse(_entity_text("watershed:anadyr", "bare-slug"))
    with pytest.raises(entities.Malformed, match="not two WGS84"):
        entities.parse(_entity_text("66.05 north"))


# ------------------------------------- several shapes on one entity

def test_a_union_is_reported_under_a_key_that_ignores_the_order_typed():
    """`composite_claims` is the last of the composite machinery, and it is a
    *report*: two entities that named the same pair in either order belong on
    one row. Nothing resolves the key — it was an identity when a union had to
    be a lookupable id, and is a grouping now."""
    store = {
        "place:a": {"id": "place:a", "geo": [
            {"kind": "shape", "id": "langarea:b"},
            {"kind": "shape", "id": "langarea:a"}]},
        "place:b": {"id": "place:b", "geo": [
            {"kind": "shape", "id": "langarea:a"},
            {"kind": "shape", "id": "langarea:b"}]},
    }
    assert geo.composite_claims(store) == {
        "langarea:a,langarea:b": ["place:a", "place:b"]}


@built
def test_a_union_is_not_a_row_in_the_store():
    """**The census is what the build wrote.** A union some entity happened to
    author is a fact about `entities/`, and minting a row for it would make the
    atlas claim a shape no source drew. It used to *resolve* through `.get()`
    while staying out of iteration, which took a dict subclass to arrange; the
    members are named separately now, so there is nothing to resolve and the
    index is a plain dict."""
    idx = geo.index(ROOT)["shapes"]
    spec = "base:chukotka-east-of-meridian,langarea:chuk1273"
    assert spec not in idx and idx.get(spec) is None
    for m in spec.split(","):
        assert m in idx


@built
def test_a_composite_naming_a_shape_that_does_not_exist_is_absent():
    """So `entity check` still refuses it, and can name the member that failed
    rather than the whole field."""
    idx = geo.index(ROOT)["shapes"]
    assert "langarea:chuk1273,watershed:nonesuch" not in idx
    assert idx.get("langarea:chuk1273,watershed:nonesuch") is None


@built
def test_the_members_of_a_union_are_drawn_one_by_one():
    """`geo.shape` takes one id and reads one file. It used to accept a
    composite and concatenate its members' features, because every caller passed
    a whole `area:` through; a caller that wants several asks for several now.

    The pair is still the case that matters — the Asher polygon stops dead at
    the antimeridian and the Natural Earth land east of it is what carries the
    drawing past, which is the whole of item 7."""
    members = ["base:chukotka-east-of-meridian", "langarea:chuk1273"]
    docs = [geo.shape(m, ROOT) for m in members]
    assert all(d.get("features") for d in docs)
    assert max(x for d in docs for r in geo.rings(d) for x, _ in r) > 180.0
    assert max(x for r in geo.rings(geo.shape("langarea:chuk1273", ROOT))
               for x, _ in r) == 180.0


@built
def test_the_asher_polygon_is_left_exactly_as_its_publisher_drew_it():
    """The join is a composite on an entity, never a redrawn `langarea:`.
    Extending a speaker area past where its publisher drew it would be
    inventing evidence in the one place a reader would never check."""
    doc = geo.shape("langarea:chuk1273", ROOT)
    assert any(abs(x - 180.0) < 1e-9 for r in geo.rings(doc) for x, _ in r)
    assert geo.index(ROOT)["shapes"]["langarea:chuk1273"]["source"] == "asher2007"


@built
def test_the_land_east_of_the_meridian_is_land_and_claims_nothing_else():
    """`base:`, from Natural Earth, by a declared clip — it says nothing about
    who speaks what. The claim lives in the entity file that composes it."""
    row = geo.index(ROOT)["shapes"]["base:chukotka-east-of-meridian"]
    assert row["kind"] == "base" and row["source"] == "naturalearth-50m"
    w, s, e, n = row["bounds"]
    assert w >= 180.0                      # nothing west of the meridian
    assert e < 194.0                       # and nothing as far east as Alaska
    assert s > 63.9                        # nor as far south as St Lawrence I.


# ------------------------------------------------------------ containment

def _square(x0, y0, x1, y1) -> list:
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


def _collection(*polys) -> dict:
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"layer": "test"},
                          "geometry": {"type": "Polygon", "coordinates": p}}
                         for p in polys]}


def test_two_overlapping_polygons_do_not_cancel_each_other_out():
    """The parity count is **per polygon**, OR'd — not across the collection.

    Across a whole collection the arithmetic is the same only while no two
    polygons overlap. Where they do, a point inside both crosses an even number
    of rings and reads as *outside*: a hole punched exactly where two shapes
    agree, which is the last place anyone would look for one. Written against a
    fixture rather than the store because the store has no overlapping pair to
    catch it with, which is precisely why this went unnoticed.
    """
    doc = _collection(_square(0, 0, 10, 10), _square(5, 0, 15, 10))
    assert geo.in_shape((7, 5), doc)      # in both — the regression
    assert geo.in_shape((2, 5), doc)      # in the first only
    assert geo.in_shape((12, 5), doc)     # in the second only
    assert not geo.in_shape((20, 5), doc)


def test_a_hole_is_still_a_hole():
    """The fix must not cost what parity was there for. An inner ring is a hole
    in *its own* polygon, and winding order is advisory in these sources, so
    counting crossings within the polygon is still the reading that does not
    depend on a convention nobody enforced."""
    ring = _square(0, 0, 10, 10)[0]
    hole = _square(4, 4, 6, 6)[0]
    doc = _collection([ring, hole])
    assert geo.in_shape((1, 1), doc)
    assert not geo.in_shape((5, 5), doc)


def test_polygons_groups_the_rings_that_rings_flattens():
    """Both views over one collection, and the difference between them is the
    whole of the fix."""
    doc = _collection([_square(0, 0, 10, 10)[0], _square(4, 4, 6, 6)[0]],
                      _square(20, 0, 30, 10))
    assert len(list(geo.rings(doc))) == 3
    assert [len(p) for p in geo.polygons(doc)] == [2, 1]


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
    assert set(r) == {"scope", "nesting", "meridian", "containment", "shared",
                      "unclaimed", "unlocated"}
    assert all("reading" in row for row in r["containment"])


@built
def test_a_composite_counts_as_a_claim_on_each_of_its_members():
    """Otherwise the members read as unclaimed *and* the union reads as a shape
    `data/geo/` does not hold — two wrong answers from one right field.

    Written when several shapes were one comma-joined `area:`, and still the
    rule: a record may name as many shapes as it likes, and each is a claim.
    What changed is that the members no longer have to be recovered from a
    spelling — the field holds them apart already."""
    store = {"place:x": {"id": "place:x", "geo": [
        {"kind": "shape", "id": "langarea:chuk1273"},
        {"kind": "shape", "id": "watershed:anadyr"}]}}
    claims = geo.member_claims(store)
    assert claims["langarea:chuk1273"] == ["place:x"]
    assert claims["watershed:anadyr"] == ["place:x"]


def test_unlocated_is_scoped_by_the_tree_and_not_by_class(tmp_path):
    """The inverse of `unclaimed`, and the worklist `entity locate` answers.

    Scoped so that a person or a source — unlocated forever, and rightly — is
    not in it. What earns a row is sitting under something the atlas can draw:
    `place:kid` does, `person:someone` does not, and `place:top` is framed by
    its members rather than wanting a boundary of its own.
    """
    _store(tmp_path,
           ("place:top", ""),
           ("place:kid", "- within: place:top\n- geo: 66.0 170.0\n"),
           ("place:bare", "- within: place:top\n"),
           ("person:someone", ""))
    rows = {r["id"]: r for r in geo.unlocated(entities.load(tmp_path), tmp_path)}
    assert "place:bare" in rows and rows["place:bare"]["wants"] == "a geo:"
    assert rows["place:top"]["wants"] == "framed by its members"
    assert "place:kid" not in rows          # it has a point
    assert "person:someone" not in rows     # nothing above or below it is drawn


@built
def test_a_shape_two_entities_claim_is_reported_and_not_refused():
    """Legal, because forcing a choice would be this edition deciding something
    the source does not — a people and a subgroup inside it may both name one
    Asher polygon.

    **The store currently shares nothing, and that is itself the assertion.**
    Every one of the nine shared claims was a `language:` entry pointing at the
    very polygon its `people:` counterpart already held; retiring that class
    left the report empty. What `shared` guards now is the other direction — a
    duplicate claim reappearing unremarked — so the row is checked to exist and
    to be empty rather than deleted along with its examples."""
    assert entities.check(ROOT)["ok"]
    assert geo.verify(ROOT)["shared"] == []


# ------------------------------------------------------------ the extent

def _store(tmp_path, *recs):
    for ident, extra in recs:
        cls, slug = ident.split(":")
        p = tmp_path / "entities" / cls / f"{slug}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {ident} — {slug}\n\n- status: ratified\n- since: 1-021\n"
                     f"{extra}\n## aliases\n\n| form | lang | auto | note |\n|---|---|---|---|\n"
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
    """185 and −175 are the same meridian, and a projection that disagreed would
    tear every shape in Chukotka in half. The azimuthal projection got this from
    going through `sin`/`cos` of longitude; the cylindrical one that replaced it
    is linear in longitude and so has to wrap the difference itself."""
    a = geomap.project(185.0, 66.0, 176.0, 65.0)
    b = geomap.project(-175.0, 66.0, 176.0, 65.0)
    assert a == pytest.approx(b)


def test_a_latlon_box_projects_to_a_rectangle():
    """**The property the whole `frame:` mechanism rests on**, and the reason the
    projection changed. Under Lambert azimuthal equal-area, centred on the frame,
    meridians converge toward the pole: on the box declared for Northeast Siberia
    the west bound projected twice as far out at its southern end as at its
    northern one, the viewBox had to be fitted to the bounding box of that curved
    trapezoid, and a reader who declared the Yana to Cape Prince of Wales got
    Manchuria and most of Alaska. No frame a human could write would have fixed
    it, because the box was not what got drawn."""
    box = (128.0, 50.9, 192.0, 71.7)
    f = geomap.Frame(box)
    w, s, e, n = box
    sw, se, nw, ne = (f._at(w, s), f._at(e, s), f._at(w, n), f._at(e, n))
    assert sw[0] == pytest.approx(nw[0])      # the west bound is one vertical
    assert se[0] == pytest.approx(ne[0])
    assert sw[1] == pytest.approx(se[1])      # the south bound is one horizontal
    assert nw[1] == pytest.approx(ne[1])


def test_a_frame_takes_the_aspect_of_what_it_frames():
    """`SPAN` is the longer side, whatever the frame's shape, so one decimal
    place is still enough at every zoom and no map carries a size in pixels.

    It used to be both sides. A square viewBox meant a wide frame was scaled to
    its *width* and then padded with empty sea: measured on the Northeast Siberia
    box, the content filled 89% of the square horizontally and 42% vertically, so
    well over half the picture was margin. `svg.map` is `width:100%; height:auto`,
    so a viewBox that follows the frame is simply a shorter map."""
    wide, tall, square = ((100.0, 60.0, 200.0, 70.0), (176.0, 50.0, 178.0, 75.0),
                          (176.0, 65.0, 176.2, 65.2))
    assert geomap.Frame(wide).viewbox.split()[2] == "1000"      # "0 0 W H"
    assert float(geomap.Frame(wide).viewbox.split()[3]) < geomap.SPAN
    assert geomap.Frame(wide).width == geomap.SPAN
    assert geomap.Frame(tall).height == geomap.SPAN
    assert geomap.Frame(tall).width < geomap.SPAN
    # Whatever the aspect, what was asked for is inside what is drawn.
    for box in (wide, tall, square):
        f = geomap.Frame(box)
        w, s, e, n = box
        for lon, lat in ((w, s), (e, n), (w, n), (e, s)):
            x, y = f._at(lon, lat)
            assert 0 <= x <= f.width and 0 <= y <= f.height


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
    f = geomap.Frame(geo.bounds(geo.shape("watershed:keperveyem-or-wolverine", ROOT)))
    land = geo.shape("base:land", ROOT)
    assert len(f.paths(land)) < len(list(geo.rings(land)))


@built
def test_a_map_is_svg_with_no_pixel_dimension_on_it():
    f = geomap.Frame(geo.bounds(geo.shape("watershed:anadyr", ROOT)))
    doc = geo.shape("watershed:anadyr", ROOT)
    svg = geomap.render(f, {"subject": geomap.owned(f.paths(doc), "river:anadyr",
                                                    "watershed")})
    assert svg.startswith("<svg") and f"viewBox='{f.viewbox}'" in svg
    assert "px" not in svg and "width=" not in svg


def test_a_path_carries_the_kind_of_shape_it_is():
    """One accent for every boundary made a wide frame unreadable — the Northeast
    Siberia map draws fourteen watersheds, five land regions and three stretches
    of open water at once, and in one hue they are a field of overlapping
    outlines. The kind is declared in `data/geo/` and travels on the path, so the
    stylesheet looks it up rather than guessing from the geometry."""
    f = geomap.Frame((150.0, 60.0, 200.0, 72.0))
    doc = geo.shape("watershed:anadyr", ROOT)
    svg = geomap.render(f, {"members": geomap.owned(f.paths(doc), "river:anadyr",
                                                    "watershed")})
    assert "data-kind='watershed'" in svg
    # Absent rather than empty where there is none: the coastline is `base:land`,
    # which no entity claims and no rule should colour.
    assert "data-kind" not in geomap.render(f, {"land": geomap.owned(f.paths(doc))})


def test_a_mark_joins_the_root_class_and_is_absent_by_default():
    """`render` is told what the subject *is*; it cannot read it off the paths.
    Inferring a drainage basin from the shape of a ring is exactly the guess this
    project refuses, so the caller decides and this only carries it."""
    f = geomap.Frame((150.0, 60.0, 200.0, 72.0))
    assert "class='map'" in geomap.render(f, {})
    assert "class='map basin'" in geomap.render(f, {}, mark="basin")


@built
def test_the_subject_is_marked_a_basin_only_when_its_shape_is_a_watershed():
    """Read off the shape's *type* — `area:` is typed, and `watershed:anadyr`
    says where the polygon came from. Every watershed in the store happens to sit
    on a `water:` entity today, so the entity's class would give the same answer;
    it is a different question, and only this one says why the outline must not be
    drawn in the colour of the rivers inside it."""
    store = entities.load(ROOT)
    basin = edition_ui.map_context("river:anadyr", ROOT, "/edition", store=store)
    assert "class='map basin'" in basin["svg"]
    assert basin["basis"]["id"] == "watershed:anadyr"

    plain = edition_ui.map_context("place:markovo", ROOT, "/edition", store=store)
    assert plain["svg"] and "basin" not in plain["svg"]


def test_every_drawn_record_says_which_record_it_is():
    """What the highlight rests on. Nothing about a path's geometry leads back to
    an entity: a member is the nearest descendant *with* a shape, found by
    descending through those without, so the drawn thing is not reliably the
    child whose name a reader is resting on. The coastline claims nothing,
    because no record owns it."""
    f = geomap.Frame((150.0, 60.0, 200.0, 72.0))
    svg = geomap.render(f, {
        "land": geomap.owned(["M0 0L1 1"]),
        "subject": geomap.owned(["M0 0L1 1"], "river:kolyma"),
        "members": geomap.owned(["M0 0L1 1"], "river:maliy-anyuy"),
    })
    assert "data-ent='river:kolyma'" in svg
    assert "data-ent='river:maliy-anyuy'" in svg
    assert svg.count("data-ent") == 2   # the land carries none


@built
def test_a_framed_place_is_drawn_to_itself_and_not_to_its_parent():
    """Chukotka and the Russian Far East came out pixel for pixel identical.
    Framing on the parent is right for a *shape* — the Small Anui says where it
    is only with the Kolyma around it — but a node with neither shape nor point
    *is* its extent, and the RFE has no parent, so both fell back to the RFE's."""
    store = entities.load(ROOT)
    rfe = edition_ui.map_context("land:russian-far-east", ROOT, "/e", store=store)
    chu = edition_ui.map_context("land:chukotka", ROOT, "/e", store=store)
    assert rfe["basis"]["kind"] == chu["basis"]["kind"] == "framed"
    assert rfe["svg"] and rfe["svg"] != chu["svg"]


@built
def test_a_framed_descendant_is_on_the_map_and_nothing_else_is():
    """`member_shapes` descends *through* a shapeless node to the basins below,
    so Chukotka appears on no layer of its parent's map and its name lit up
    nothing. Its extent is what there is to offer. A descendant that has a shape
    or a point is already drawn and gets no box — a rectangle over every one of
    them at once is a field of rectangles over the thing you were reading."""
    store = entities.load(ROOT)
    got = dict(geo.member_extents("land:russian-far-east", store, ROOT))
    assert "land:chukotka" in got
    assert not any(store[e]["geo"] for e in got)
    layer = re.search(r"<g class='extents'>.*?</g>",
                      edition_ui.map_context("land:russian-far-east", ROOT,
                                             "/e", store=store)["svg"], re.S)
    assert layer and "data-ent='land:chukotka'" in layer.group()


@built
def test_what_is_warmed_is_wider_than_what_is_drawn():
    """The map is the authority on what can be highlighted, never on what a
    reader is about to open. The Omolon has a shape of its own and is still on no
    layer of the Russian Far East's map: `member_shapes` stopped at the Kolyma
    above it. Markovo is a point three levels down, past `pins_under`'s depth.
    Both are a click or two from where the reader is standing."""
    store = entities.load(ROOT)
    ctx = edition_ui.map_context("land:russian-far-east", ROOT, "/e", store=store)
    drawn = set(re.findall(r"data-ent='([^']*)'", ctx["svg"]))
    assert {"river:omolon", "place:markovo"} <= set(ctx["warm"])
    assert not ({"river:omolon", "place:markovo"} & drawn)
    assert "land:russian-far-east" not in ctx["warm"]   # never itself


@built
def test_a_member_is_named_by_its_entity_and_not_by_its_shape():
    """Two entities may share one polygon — a people and a subgroup inside it
    may both point at one Asher shape — so the shape cannot identify the member
    even in principle."""
    store = entities.load(ROOT)
    pairs = geo.member_shapes("river:kolyma", store)
    assert pairs and all(e in store and s.startswith("watershed:") for e, s in pairs)


def test_a_pin_label_is_escaped_and_turns_inward_at_the_edge():
    f = geomap.Frame((150.0, 60.0, 200.0, 72.0))
    svg = geomap.render(f, {}, pins=[(950.0, 500.0, "<script>", "place:x"),
                                     (100.0, 500.0, "Markovo", "place:markovo")])
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


@built
def test_an_entity_with_no_extent_gets_a_note_rather_than_a_traceback():
    """`data/geo/`'s `absent` block holds records — `sought`, `source`, `why` —
    and `map_context` read them as strings, so `.lower()` raised on every entry
    with neither `area:` nor `geo:` nor a located descendant. It stayed hidden
    while almost every entry had an extent; a batch of bays and capes carrying
    neither made it the ordinary path. `geo.absent_row` is the one flattener.

    **"No extent" has to mean no frame either.** A declared `frame:` is a box to
    draw to even though `extent_of` ignores it — that function answers how big a
    thing is, which a parent sizes itself on, and a viewport is not that. So the
    set here is the entities with genuinely nothing to look at, which is what the
    note is for."""
    store = entities.load(ROOT)
    absent = [i for i in store
              if geo.extent_of(i, store, ROOT) is None and not store[i]["frame"]]
    assert absent, "the fixture store has an extent for everything"
    for i in absent:
        ctx = edition_ui.map_context(i, ROOT, "/edition", store=store)
        assert ctx["svg"] == ""
        assert isinstance(ctx["absent_note"], str)


# ------------------------------------------------------ the ontology's own check

def _nest(tmp_path, *pairs) -> list[dict]:
    """A store made of nothing but `within:` — `nesting` reads no geometry, so
    the shapes a real store carries would only be scenery here."""
    from harness.tests.test_entities import entry

    for ident, parent in pairs:
        entry(tmp_path, ident,
              extra=f"- within: {parent}\n" if parent else "")
    return geo.nesting(entities.load(tmp_path))


def test_a_point_is_reported_as_containing_nothing(tmp_path):
    """The finding the four-class split was made to make possible. While
    `place:` held a village and a peninsula alike, "X is inside Y" was untestable
    — every parent might have been a region. Now a `place:` is a point, and a
    point holds nothing whatever its child is."""
    got = _nest(tmp_path, ("place:uelen", ""), ("land:chukotka", "place:uelen"))
    assert [(r["child"], r["parent"]) for r in got] == \
        [("land:chukotka", "place:uelen")]
    assert "point contains nothing" in got[0]["reading"]


def test_a_settlement_or_a_basin_inside_open_water_is_reported(tmp_path):
    """Kamenskoye was filed under Penzhina Bay and stands on the river above it.
    A drainage basin is dry ground however wet the thing it drains into, so it
    is the same finding and not a second one."""
    got = _nest(tmp_path,
                ("water:penzhina-bay", ""),
                ("place:kamenskoye", "water:penzhina-bay"),
                ("river:penzhina", "water:penzhina-bay"))
    assert {r["child"] for r in got} == {"place:kamenskoye", "river:penzhina"}


def test_an_island_inside_a_strait_is_not_a_finding(tmp_path):
    """The rule was wider once and said this, about the Diomedes and about St.
    Lawrence Island — which are islands, which is what land inside water *is*,
    and which have nowhere else to go: `within:` is the store's only relation and
    an island 60 km offshore belongs to no land region. Two true rows in three is
    how a report stops being read, so `land:` came out of the list."""
    assert _nest(tmp_path,
                 ("water:bering-strait", ""),
                 ("land:diomede-islands", "water:bering-strait")) == []


def test_a_river_holding_a_town_and_a_sea_holding_a_bay_are_both_silent(tmp_path):
    """The ordinary shapes, stated so a widening of `NESTING` has to break
    something. A `river:` is a watershed and holds the settlements in it; a
    `water:` holds the water inside it."""
    assert _nest(tmp_path,
                 ("river:anadyr", ""), ("place:markovo", "river:anadyr"),
                 ("water:okhotsk-sea", ""),
                 ("water:penzhina-bay", "water:okhotsk-sea")) == []


@built
def test_the_committed_store_nests_coherently():
    """The migration's own witness. Every `within:` in the store, not the twelve
    pairs both of whose members somebody drew — which is the whole reason this
    check needs no geometry."""
    assert geo.nesting(entities.load(ROOT)) == []


def test_a_declared_frame_counts_as_located_and_extent_of_still_ignores_it(tmp_path):
    """Two different questions, and the split is the point. `extent_of` answers
    "how big is this thing", which is what a *parent* sizes itself on — and a
    frame is a viewport, usually wider than its subject, so unioning one into an
    ancestor's box would inflate it with padding chosen for a different map. But
    "can the atlas draw this" is answered yes by a frame alone: the frame *is*
    the viewBox.

    `land:russian-far-east` and `water:bering-strait` were reading as unlocated
    and as framed-by-their-members, and neither is true of either — their frames
    were authored precisely because the derived box was wrong."""
    from harness.tests.test_entities import entry

    entry(tmp_path, "land:rfe", extra="- frame: 108.0 45.0 190.0 75.0\n")
    store = entities.load(tmp_path)
    assert geo.located("land:rfe", store, tmp_path)
    assert geo.extent_of("land:rfe", store, tmp_path) is None
    assert [r["id"] for r in geo.unlocated(store, tmp_path)] == []


def test_a_container_with_neither_is_still_a_worklist_row(tmp_path):
    """The other direction, so the rule above cannot quietly empty the report:
    a shapeless container whose children are drawn still wants a frame, and says
    which of the two would settle it."""
    from harness.tests.test_entities import entry

    entry(tmp_path, "land:chukotka")
    entry(tmp_path, "place:uelen", extra="- within: land:chukotka\n"
                                         "- geo: 66.16 -169.81\n")
    rows = {r["id"]: r for r in geo.unlocated(entities.load(tmp_path), tmp_path)}
    assert rows["land:chukotka"]["wants"] == "framed by its members"


def test_a_people_with_no_shape_falls_back_to_its_parents_extent(tmp_path):
    """The one class where the fallback is not a guess: a subgroup of an
    ethnicity lives inside that ethnicity's area by what the word means, so the
    parent's box bounds the child truthfully even where no source has drawn the
    child. The Reindeer and Maritime Chukchi, the Kavraˊlɪt and the Chuvans are
    otherwise invisible in an atlas largely about them.

    A bound, not a boundary — the card says the extent is the parent's."""
    from harness.tests.test_entities import entry

    entry(tmp_path, "people:chukchi", extra="- geo: 66.0 -175.0\n")
    entry(tmp_path, "people:kavralit", extra="- within: people:chukchi\n")
    store = entities.load(tmp_path)
    assert geo.extent_of("people:kavralit", store, tmp_path) == \
        geo.extent_of("people:chukchi", store, tmp_path)
    assert geo.located("people:kavralit", store, tmp_path)


def test_the_fallback_is_scoped_to_peoples_and_terminates(tmp_path):
    """Any other class would make every entity in the store located, which is
    the report saying nothing. And the parent unions its children back in, so
    the recursion has to be guarded — it is, by `seen`."""
    from harness.tests.test_entities import entry

    entry(tmp_path, "land:kamchatka", extra="- geo: 56.0 159.0\n")
    entry(tmp_path, "place:golyghina", extra="- within: land:kamchatka\n")
    store = entities.load(tmp_path)
    assert geo.extent_of("place:golyghina", store, tmp_path) is None

    entry(tmp_path, "people:a", extra="- within: people:b\n")
    entry(tmp_path, "people:b", extra="- within: people:a\n")
    assert geo.extent_of("people:a", entities.load(tmp_path), tmp_path) is None


def test_a_marine_parent_is_reported_as_not_measurable():
    """Natural Earth's marine polygons *tile* the ocean. Karaginskiy Gulf abuts
    the Bering Sea rather than sitting inside it and measures 0.068 against it —
    worse than against the Kamchatka peninsula it is not part of. They are also
    drawn around land, so an island in a gulf reads 0.625 while being exactly
    where it says it is.

    Both authored facts are true and this geometry witnesses neither, so the row
    says that rather than calling a source wrong for never having claimed to
    nest. Same argument as `coarse`, one source over."""
    assert geo._reading(0.068, False, True).startswith("not measurable")
    assert geo._reading(0.999, False, True).startswith("not measurable")
    # And it changes nothing where the parent is a real container.
    assert geo._reading(0.999, False, False) == "contained"
    assert geo._reading(0.5, False, False) == "disagrees"
    assert geo._reading(0.8, True, False).startswith("consistent")


@built
def test_a_framed_entity_with_nothing_else_still_draws():
    """`land:parapolsky-dol` has a `frame:` and no shape and no point, and
    appeared on no map at all — its own said "nothing to draw" about a box
    `geo bounds` had measured from the two bays that define it, and its
    parent's did not show it either.

    Two different questions again. `extent_of` says how big a thing is and a
    parent sizes itself on that, so it must go on ignoring viewports; "what
    should this page look at" and "what box stands in for a node with nothing
    else" are both answered by the frame.

    **The leaf is built rather than borrowed.** Both the `extent_of` and the
    `member_extents` assertion read the frame case off the live store, where it
    held only while nothing was filed under the Dol — an editorial act away
    from failing, and both failed the day `place:chukchee-fair` arrived. Neither
    was measuring the frame: they were measuring a census. Dropping the
    descendants states the case the frame was added for, and the live store then
    pins the other half of the same rule — that a derived extent wins where
    there is one."""
    store = entities.load(ROOT)
    rec = store.get("land:parapolsky-dol")
    assert rec and rec["frame"] and not rec["geo"]
    ctx = edition_ui.map_context("land:parapolsky-dol", ROOT, "/e", store=store)
    assert ctx["svg"], "a framed entity should have a map of its own"

    leaf = {k: v for k, v in store.items()
            if v.get("within") != "land:parapolsky-dol"}
    assert geo.extent_of("land:parapolsky-dol", leaf, ROOT) is None
    assert edition_ui.map_context("land:parapolsky-dol", ROOT, "/e",
                                  store=leaf)["svg"]

    # And it stands in for itself on the parent's map, where `member_extents`
    # supplies the boxes for nodes no other layer can identify. The frame is
    # the *fallback* there — `extent_of` first, wherever there is anything to
    # derive from.
    boxes = dict(geo.member_extents(rec["within"], leaf, ROOT))
    assert boxes.get("land:parapolsky-dol") == rec["frame"]

    # The other half of the rule needs a framed entity that *has* something to
    # derive from, and this used to read it off `parapolsky-dol` in the live
    # store — which worked only while `chukchee-fair` hung from it. The fair
    # moved (it sits 2.6° east of the Dol's own frame, and the Dol carried no
    # geometry to test the containment against), leaving the Dol childless, so
    # the live store and the leaf store now say the same thing about it and the
    # assertion tested nothing. A fixture whose two halves have quietly become
    # one is the hazard this repo names elsewhere; `land:chukotka` is framed and
    # densely populated, so the two halves stay two.
    framed_parent = store["land:chukotka"]
    assert framed_parent["frame"] and not geo.geo_shapes(framed_parent)
    live = dict(geo.member_extents(framed_parent["within"], store, ROOT))
    derived = geo.extent_of("land:chukotka", store, ROOT)
    assert derived is not None, "the fixture must have something to derive from"
    assert live.get("land:chukotka") == derived


# ------------------------------------------------- the seam nothing could see

def _geo_store(tmp_path, ident, polys):
    """A one-shape store. `polys` is a list of outer rings, each (lon, lat)."""
    d = tmp_path / "data" / "geo"
    (d / "region").mkdir(parents=True, exist_ok=True)
    (d / "region" / "x.json").write_text(json.dumps({
        "type": "FeatureCollection", "properties": {},
        "features": [{"type": "Feature", "properties": {},
                      "geometry": {"type": "MultiPolygon",
                                   "coordinates": [[p] for p in polys]}}]}))
    (d / "index.json").write_text(json.dumps({
        "window": [79.5, 39.7, 216.9, 76.6], "lon_base": 60.0, "absent": {},
        "shapes": [{"id": ident, "kind": "region", "file": "region/x.json",
                    "source": "test"}]}))
    return tmp_path


def test_a_shape_cut_at_the_meridian_is_reported(tmp_path):
    """The defect a reader found by looking at the atlas, because nothing
    measured it. Natural Earth's 10m Wrangel Island arrived as two halves 0.011°
    apart, `build_geo.prepare` had nothing to weld, and `geomap.paths` emits one
    stroked path per ring — so a line ran down the middle of every shape that
    straddled 180, on every map that drew one."""
    _geo_store(tmp_path, "region:w", [
        [(178.6, 71.0), (180.0, 71.0), (180.0, 71.5), (178.6, 71.5), (178.6, 71.0)],
        [(180.0, 71.1), (182.5, 71.1), (182.5, 71.4), (180.0, 71.4), (180.0, 71.1)],
    ])
    rows = geo.meridian(tmp_path)
    assert [r["shape"] for r in rows] == ["region:w"]
    assert rows[0]["pieces"] == 2


def test_a_ring_that_crosses_the_meridian_is_the_healthy_case(tmp_path):
    """Welded is one ring spanning 180, which is what the 50m coastline draws
    and what the store now holds. Reporting it would make the check fire on
    every shape it was written to vindicate."""
    _geo_store(tmp_path, "region:w", [
        [(178.6, 71.0), (182.5, 71.0), (182.5, 71.5), (178.6, 71.5), (178.6, 71.0)],
    ])
    assert geo.meridian(tmp_path) == []


def test_one_piece_stopping_at_the_meridian_is_not_a_seam(tmp_path):
    """`langarea:chuk1273` stops dead at 180 because that is where Asher drew
    it, with nothing on the far side to weld to. The build already says so as a
    note; a row here would be a permanent complaint about a source's honest
    limit, which is how a report stops being read."""
    _geo_store(tmp_path, "langarea:c", [
        [(170.0, 66.0), (180.0, 66.0), (180.0, 68.0), (170.0, 68.0), (170.0, 66.0)],
    ])
    assert geo.meridian(tmp_path) == []


@built
def test_the_committed_store_draws_no_seam():
    """The store's own witness, and the reason the check is worth having: it
    passes now and did not before `MERIDIAN_SNAP` and the Wrangel override."""
    assert geo.meridian(ROOT) == []


# ---------------------------------------------------- a selection, not a subject

def _sel(*idents, hidden=(), store=None):
    return edition_ui.map_context(list(idents), ROOT, "/e",
                                  store=store or entities.load(ROOT),
                                  hidden=set(hidden))


@built
def test_the_tree_names_everything_the_map_drew():
    """**The tree is a legend, so it is built from the picture.** Putting a
    parent on the map draws its members, and for a while it drew nine basins and
    thirty-four villages inside Chukotka against a tree holding one name — a
    shape a reader can see and cannot ask about.

    `on_map` is collected by the layer building itself, so this is not two walks
    of the store agreeing today; there is one walk, and the tree is its record.
    The converse does not hold and should not: the containing nodes are in the
    tree without being drawn, which is what the tree is *for*.
    """
    ctx = _sel("land:chukotka")
    drawn = set(re.findall(r"data-ent='([^']*)'", ctx["svg"]))
    named = set()

    def walk(ns):
        for n in ns:
            named.add(n["id"])
            # Both, because folding is a rule about how much of the tree is open
            # on arrival and not about what is in it.
            walk(n["children"] + n["folded"])

    walk(ctx["tree"])
    assert drawn, "the fixture draws nothing"
    assert drawn <= named


@built
def test_the_tree_ends_at_the_first_common_ancestor():
    """Two villages in different basins are one picture only because something
    holds them both, and that node is where the map is framed. Above it is not on
    the map, so it is not in the tree — a tree that ran to the top of the store
    would be the atlas with the map's own contents buried in it."""
    ctx = _sel("place:uelen", "place:markovo")
    roots = [n["id"] for n in ctx["tree"]]
    store = entities.load(ROOT)
    assert roots == geo.common_ancestors(["place:uelen", "place:markovo"],
                                         store)[:1]
    assert roots and store[roots[0]]["within"], "the fixture root has no parent"


def _find(nodes, ident: str) -> dict:
    """The node for `ident`, wherever the fold put it."""
    for n in nodes:
        if n["id"] == ident:
            return n
        if got := _find(n["children"] + n["folded"], ident):
            return got
    return {}


def _view(ctx) -> list[float]:
    return [float(v) for v in
            re.search(r"viewBox='([^']*)'", ctx["svg"]).group(1).split()]


@built
def test_a_place_is_framed_on_itself_and_not_on_what_contains_it():
    """**Context is selected, not assumed.** Framing on the first common ancestor
    meant every map of a village was a map of the peninsula with a dot on it —
    most of the picture spent answering a question nobody had asked, and no way
    to ask the tighter one at all.

    The argument that a shape shown inside its container says where it *is* has
    not gone anywhere; the selection now carries it. Putting the container on the
    map is one click, it shows in the tree, and the frame widens to hold both —
    which is the same picture as before, arrived at on purpose.
    """
    store = entities.load(ROOT)
    alone = _sel("place:uelen", store=store)
    with_parent = _sel("place:uelen", "land:chukchi-peninsula", store=store)
    assert _view(alone)[2] < _view(with_parent)[2]
    # And what it is framed on is its own extent: the degree box around the
    # point, not the peninsula's — which is a couple of hundred times the area.
    box = geo.extent_of("place:uelen", store, ROOT)
    big = geo.extent_of("land:chukchi-peninsula", store, ROOT)
    assert box and big and (box[2] - box[0]) < (big[2] - big[0]) / 4


@built
def test_hiding_a_selection_tightens_the_frame_and_asks_nothing():
    """The frame is the union of what is selected, so taking one out of the union
    can only tighten it — and each selection's own box travels already projected
    into the sheet's units, which is what lets the browser re-frame without
    asking again. The sheet is that same union, so nothing it can re-frame to was
    culled as off-sheet."""
    both = ["place:uelen", "place:markovo"]
    wide = _sel(*both)
    tight = _sel(*both, hidden=["place:markovo"])
    assert set(wide["frames"]["own"]) == set(both)
    assert _view(tight)[2] < _view(wide)[2]
    sheet = [float(v) for v in
             re.search(r"data-sheet='([^']*)'", wide["svg"]).group(1).split()]
    x, y, w, h = _view(tight)
    assert x >= -0.05 and y >= -0.05
    assert x + w <= sheet[2] + 0.05 and y + h <= sheet[3] + 0.05


@built
def test_a_hidden_node_is_still_drawn_and_still_in_the_tree():
    """Hiding is a rule about paint and about what the frame may sit on, applied
    in the browser — so showing a node again costs nothing. If the server dropped
    it from the drawing, undoing would be a round trip, and if it dropped it from
    the tree there would be nothing left to click."""
    ctx = _sel("place:uelen", "place:markovo", hidden=["place:uelen"])
    assert "place:uelen" in ctx["drawn"]
    assert "data-ent='place:uelen'" in ctx["svg"]
    named = []

    def walk(ns):
        for n in ns:
            named.append((n["id"], n["hidden"]))
            walk(n["children"] + n["folded"])

    walk(ctx["tree"])
    assert ("place:uelen", True) in named


@built
def test_a_map_nobody_has_re_framed_opens_on_the_whole_of_what_was_drawn():
    """`viewBox` is where the reader is looking and `data-sheet` is what was
    drawn, and with one subject and nothing hidden they are one rectangle: the
    frame is the selection's extent and so is the sheet. Only hiding moves them
    apart, and only inward.

    A subject whose extent is smaller than `MIN_SPAN` is excluded rather than
    special-cased — the sheet is widened to that floor and the view is not, which
    is a real difference and not this test's subject. A village is that case."""
    ctx = _sel("river:anadyr")
    svg = ctx["svg"]
    assert re.search(r"viewBox='([^']*)'", svg).group(1) == \
        re.search(r"data-sheet='([^']*)'", svg).group(1)


@built
def test_a_place_the_atlas_cannot_draw_is_reported_rather_than_dropped():
    """The click that put it here has to fall back to opening the card, and only
    `drawn` says so. Silence would leave the reader with a click that did
    nothing at all."""
    store = entities.load(ROOT)
    absent = [i for i in store
              if geo.extent_of(i, store, ROOT) is None and not store[i]["frame"]]
    assert absent, "the fixture store has an extent for everything"
    ctx = _sel(absent[0], store=store)
    assert ctx["drawn"] == []
    assert ctx["svg"] == ""
    assert ctx["tree"], "and there is still a node to click"


def test_a_common_ancestor_is_strict_and_nearest_first(tmp_path):
    """Strict, because a selection is never its own frame: the argument that a
    shape shown inside its container says where it *is* does not stop applying
    because the container was selected too. Nearest first, because "the first
    common ancestor" has to name one node."""
    from harness.entities import common_ancestors
    from harness.tests.test_entities import entry

    for ident, parent in (("place:top", ""), ("place:mid", "place:top"),
                          ("place:a", "place:mid"), ("place:b", "place:mid")):
        entry(tmp_path, ident, extra=f"- within: {parent}\n" if parent else "")
    store = entities.load(tmp_path)
    assert common_ancestors(["place:a", "place:b"], store) == \
        ["place:mid", "place:top"]
    assert common_ancestors(["place:mid", "place:a"], store) == ["place:top"]
    assert common_ancestors(["place:top"], store) == []


@built
def test_only_a_chosen_place_gets_a_pin():
    """Selecting the Chukchee Peninsula put thirty-four village dots and
    thirty-four labels over the outline, and named all thirty-four in the tree
    below it — `pins_under` plots two levels down and none of them had been asked
    for. The framing rule's argument, applied to the markers: context is
    selected, not assumed.

    Member *shapes* are deliberately still drawn. A region with nothing inside it
    is an empty outline, and the basins under a land region are the picture the
    hierarchy was authored for."""
    store = entities.load(ROOT)
    region = "land:chukchi-peninsula"
    assert len(geo.pins_under(region, store, ROOT)) > 5, "the fixture has no kids"
    ctx = _sel(region, store=store)
    assert "<circle class='pin'" not in ctx["svg"]
    assert "<g class='members'>" in ctx["svg"]
    # And the village itself, chosen, is a pin — one, not its neighbours'.
    one = _sel("place:uelen", store=store)
    assert one["svg"].count("<circle class='pin'") == 1


@built
def test_the_open_rows_are_the_legend_and_the_fold_is_the_offer():
    """A flat list makes the pane taller than the map it explains — you scroll
    past the names to reach the picture. But the names have to be *there*: a pin
    is drawn only for a chosen place, so the villages of a selected region are on
    no layer, and a tree holding only what was drawn left nowhere to find one.

    Keying the fold on drawn-ness rather than on whose child it is answers both.
    Open is what is on the picture; folded is what is on offer."""
    ctx = _sel("land:chukchi-peninsula")
    peninsula = _find(ctx["tree"], "land:chukchi-peninsula")
    assert peninsula["selected"]
    assert all(c["drawn"] or c["carries"] for c in peninsula["children"])
    assert peninsula["folded"], "its villages are on offer and on no layer"
    assert not any(c["drawn"] or c["carries"] for c in peninsula["folded"])


@built
def test_a_selected_region_offers_its_children_even_though_none_are_drawn():
    """Select a town, then the peninsula holding it, and the peninsula's other
    towns vanished from the tree — they were there only as pins, and a pin is now
    drawn for a chosen place alone. The drill-down is the fix: a chosen node
    lists what is directly inside it, whether or not the map drew any of it."""
    store = entities.load(ROOT)
    ctx = _sel("place:uelen", "land:chukchi-peninsula", store=store)
    peninsula = _find(ctx["tree"], "land:chukchi-peninsula")
    named = {c["id"] for c in peninsula["children"] + peninsula["folded"]}
    assert named == set(geo.children(store)["land:chukchi-peninsula"])
    assert len(named) > 5, "the fixture peninsula holds nothing"


@built
def test_the_tree_root_is_the_common_ancestor_and_climbs_no_further():
    """Walking up and breaking on the root never breaks for the root *itself* —
    its own ancestors are all above it. A map of one village draws its parent's
    outline, that parent is the root, and the chain ran from there to the top of
    the store: a two-node tree came out four levels deep under the Russian Far
    East."""
    store = entities.load(ROOT)
    ctx = _sel("place:uelen", store=store)
    roots = [n["id"] for n in ctx["tree"]]
    assert roots == ["land:chukchi-peninsula"] == \
        geo.common_ancestors(["place:uelen"], store)[:1]


@built
def test_chosen_places_sort_above_the_rest():
    """The names a reader put there are the ones they are looking for."""
    ctx = _sel("place:uelen", "land:chukchi-peninsula")
    peninsula = ctx["tree"][0]["children"][0]
    assert peninsula["id"] == "land:chukchi-peninsula"
    kids = peninsula["children"]
    assert kids and kids[0]["id"] == "place:uelen" and kids[0]["selected"]
    assert not kids[-1]["selected"]


@built
def test_a_keyed_point_is_boxed_square_on_the_ground():
    """A degree of longitude is `cos(lat)` of a degree of latitude, and this book
    is at 66°N where that is 0.41 — so ±0.5° in both coordinates was a box 110 km
    tall and 45 km wide, and every village framed on its own extent came out a
    tall thin sliver with the settlement lost in the middle of it.

    Asserted after projecting, because that is the claim: the two sides are the
    same distance on the ground, not the same number of degrees."""
    store = entities.load(ROOT)
    for ident in ("place:uelen", "place:markovo"):
        rec = store[ident]
        assert entities.geo_points(rec) and not entities.geo_shapes(rec), \
            f"{ident} is not a bare point"
        w, s, e, n = geo.extent_of(ident, store, ROOT)
        lat0 = (s + n) / 2
        x0, y0 = geomap.project(w, s, w, lat0)
        x1, y1 = geomap.project(e, n, w, lat0)
        assert abs((x1 - x0) / (y0 - y1) - 1.0) < 0.01


def test_the_widening_stops_short_of_the_pole():
    """`1/cos` runs away at 90°, and a runaway box is a map of the Arctic with a
    village somewhere in it. Nothing in this store is near the clamp — Wrangel is
    the northernmost record at about 71° — so this guards the arithmetic rather
    than a live case."""
    w, s, e, n = geo.point_box(89.9, 170.0)
    assert n - s == 2 * geo.POINT_BOX
    assert (e - w) / 2 == pytest.approx(
        geo.POINT_BOX / math.cos(math.radians(geo.POINT_BOX_MAX_LAT)))


# ------------------------------------- a `geo:` member on the map


def _peopled(tmp_path):
    """A people whose whole geography is two villages it names."""
    return _store(
        tmp_path,
        ("land:coast", ""),
        ("place:one", "- within: land:coast\n- geo: 66.0 -170.0\n"),
        ("place:two", "- within: land:coast\n- geo: 65.0 -172.0\n"),
        ("people:folk", "- geo: place:one\n- geo: place:two\n"),
    )


def test_a_named_member_is_a_subject_and_not_context(tmp_path):
    """**The map of a people that names its villages is those villages.** They
    frame it and they are pinned, so they are subjects: `map_context` expands a
    `geo:` member into the selection rather than drawing it as something the
    reader did not ask for.

    That expansion is also what makes the tree honest. A row rendered selected
    while the client's selection does not hold it cannot be clicked off — the
    click reads the selection and the highlight read something else — so the two
    are one fact here, and `subjects` is what the page hands back to the browser.
    """
    store = _peopled(tmp_path)
    ctx = edition_ui.map_context("people:folk", tmp_path, "/e", store=store)
    ids = [s["id"] for s in ctx["subjects"]]
    assert ids == ["people:folk", "place:one", "place:two"]
    assert ctx["svg"].count("<circle") == 2

    def rows(ns):
        for n in ns:
            yield n
            yield from rows(n["children"])
            yield from rows(n["folded"])

    chosen = {n["id"] for n in rows(ctx["tree"]) if n["selected"]}
    assert {"place:one", "place:two"} <= chosen


def test_a_dropped_member_stays_off_the_map(tmp_path):
    """**Absence is not a dismissal, so the dismissal has to be said.**

    `map_context` is asked afresh on every interaction and cannot remember, so
    "not in the selection" means both "never added" and "just taken off" — and
    the expansion above acts on the first reading. Without `dropped` a reader who
    clicked a village away got it back on the next render, for ever.

    The pin has to go with it, which is why `pins_under` no longer follows a
    member of its own accord: a walk that re-derived the member saw a selection
    and never a dismissal, and put the dot back under a tree row that had gone.
    """
    store = _peopled(tmp_path)
    ctx = edition_ui.map_context("people:folk", tmp_path, "/e", store=store,
                                 dropped={"place:two"})
    assert [s["id"] for s in ctx["subjects"]] == ["people:folk", "place:one"]
    assert ctx["svg"].count("<circle") == 1
    assert "place:two" not in ctx["svg"]


def test_a_non_geographical_child_sorts_first_and_is_never_folded(tmp_path):
    """A people or a language is not another rung of the containment tree but an
    overlay on it, and there are always few of them against many villages.
    Sorted in among the settlements they cover they read as two more places, and
    the fold — sized against the thirty-four villages of the Chukchee Peninsula —
    put the divisions behind a summary on a map whose subject is the division.
    """
    store = _store(
        tmp_path,
        ("land:coast", ""),
        ("place:vil", "- within: land:coast\n- geo: 66.0 -170.0\n"),
        ("people:folk", "- geo: place:vil\n"),
        ("people:sub", "- part-of: people:folk\n"),
    )
    ctx = edition_ui.map_context("people:folk", tmp_path, "/e", store=store)
    top = next(n for n in ctx["tree"] if n["id"] == "people:folk")
    assert [k["id"] for k in top["children"]] == ["people:sub"]
    assert not top["folded"], "a division is not an offer to be folded away"
