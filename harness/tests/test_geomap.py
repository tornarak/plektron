"""The shape store, and the facts a map is composed from.

The map itself — projection, frame, layers, tree — is `geomap.js`'s, tested
under bun in `harness/tests/js/`.

The store is compiled and tracked, so most of these run against the real
`edition/geo/` — that is the thing the reading view draws, and a fixture would
test a shape nobody looks at. What is *not* asserted anywhere here is that a
delineation is correct: the sources say what they say, and `geo verify`
reports the disagreements rather than this suite pretending to adjudicate them.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from harness import edition_ui, entities, geo

ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT = ROOT / "jesup" / "bogoras-chukchi"
WORKSPACE = PROJECT.parent
built = pytest.mark.skipif(
    not (WORKSPACE / "edition" / "geo" / "index.json").exists(),
    reason="edition/geo/ has not been built — see tools/build_geo.py")


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
    kinds = {i.split(":")[0] for i in geo.index(PROJECT)["shapes"]}
    assert kinds and not (kinds & set(entities.ENTITY_CLASSES))


@built
def test_the_absences_are_rows_and_not_silences():
    """A people the sources do not draw has to be *in* the census. An entity
    pointing at nothing and an entity nobody has got to yet look identical from
    outside, and only one of them is finished."""
    absent = geo.index(PROJECT)["absent"]
    assert {"ypk", "xcv"} <= set(absent)
    assert all(absent.values())


@built
def test_longitudes_are_continuous_across_the_antimeridian():
    """Chukotka runs past 180 rather than wrapping to −180. This is what lets
    every planar operation downstream — containment, extents, culling — treat a
    shape spanning the meridian as an ordinary one."""
    doc = geo.shape("watershed:anadyr", PROJECT)
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
    author is a fact about `edition/entities/`, and minting a row for it would make the
    atlas claim a shape no source drew. It used to *resolve* through `.get()`
    while staying out of iteration, which took a dict subclass to arrange; the
    members are named separately now, so there is nothing to resolve and the
    index is a plain dict."""
    idx = geo.index(PROJECT)["shapes"]
    spec = "base:chukotka-east-of-meridian,langarea:chuk1273"
    assert spec not in idx and idx.get(spec) is None
    for m in spec.split(","):
        assert m in idx


@built
def test_a_composite_naming_a_shape_that_does_not_exist_is_absent():
    """So `entity check` still refuses it, and can name the member that failed
    rather than the whole field."""
    idx = geo.index(PROJECT)["shapes"]
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
    docs = [geo.shape(m, PROJECT) for m in members]
    assert all(d.get("features") for d in docs)
    assert max(x for d in docs for r in geo.rings(d) for x, _ in r) > 180.0
    assert max(x for r in geo.rings(geo.shape("langarea:chuk1273", PROJECT))
               for x, _ in r) == 180.0


@built
def test_the_asher_polygon_is_left_exactly_as_its_publisher_drew_it():
    """The join is a composite on an entity, never a redrawn `langarea:`.
    Extending a speaker area past where its publisher drew it would be
    inventing evidence in the one place a reader would never check."""
    doc = geo.shape("langarea:chuk1273", PROJECT)
    assert any(abs(x - 180.0) < 1e-9 for r in geo.rings(doc) for x, _ in r)
    assert geo.index(PROJECT)["shapes"]["langarea:chuk1273"]["source"] == "asher2007"


@built
def test_the_land_east_of_the_meridian_is_land_and_claims_nothing_else():
    """`base:`, from Natural Earth, by a declared clip — it says nothing about
    who speaks what. The claim lives in the entity file that composes it."""
    row = geo.index(PROJECT)["shapes"]["base:chukotka-east-of-meridian"]
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
    true = geo.contains(geo.shape("watershed:kolyma", PROJECT),
                        geo.shape("watershed:omolon", PROJECT))
    false = geo.contains(geo.shape("watershed:anadyr", PROJECT),
                         geo.shape("watershed:omolon", PROJECT))
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
    r = geo.verify(PROJECT)
    assert set(r) == {"scope", "nesting", "meridian", "containment", "shared",
                      "unclaimed", "unlocated"}
    assert all("reading" in row for row in r["containment"])


@built
def test_a_composite_counts_as_a_claim_on_each_of_its_members():
    """Otherwise the members read as unclaimed *and* the union reads as a shape
    `edition/geo/` does not hold — two wrong answers from one right field.

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
    assert entities.check(PROJECT)["ok"]
    assert geo.verify(PROJECT)["shared"] == []


# ------------------------------------------------------------ the extent

def _store(tmp_path, *recs):
    for ident, extra in recs:
        cls, slug = ident.split(":")
        p = tmp_path / "edition" / "entities" / cls / f"{slug}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {ident} — {slug}\n\n- status: ratified chukchi\n- since: 1-021\n"
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


# ------------------------------------------------------------ the map's facts
#
# What a map is composed *from*. The composition is `geomap.js`'s and is tested
# under bun (`harness/tests/js/`); these are the store's answers it is handed.


@built
def test_a_framed_descendant_is_on_the_map_and_nothing_else_is():
    """`member_shapes` descends *through* a shapeless node to the basins below,
    so Chukotka appears on no layer of its parent's map and its name lit up
    nothing. Its extent is what there is to offer. A descendant that has a shape
    or a point is already drawn and gets no box — a rectangle over every one of
    them at once is a field of rectangles over the thing you were reading."""
    store = entities.load(PROJECT)
    got = dict(geo.member_extents("land:russian-far-east", store, PROJECT))
    assert "land:chukotka" in got
    assert not any(store[e]["geo"] for e in got)


@built
def test_a_member_is_named_by_its_entity_and_not_by_its_shape():
    """Two entities may share one polygon — a people and a subgroup inside it
    may both point at one Asher shape — so the shape cannot identify the member
    even in principle."""
    store = entities.load(PROJECT)
    pairs = geo.member_shapes("river:kolyma", store)
    assert pairs and all(e in store and s.startswith("watershed:") for e, s in pairs)


@built
def test_the_index_is_reread_when_the_store_changes(tmp_path):
    """`edition serve` is long-lived and the cache is keyed on mtime, so a
    rebuild is picked up without a restart — a server that had to be restarted
    would teach people to rebuild less."""
    d = tmp_path / "edition" / "geo"
    d.mkdir(parents=True)
    p = d / "index.json"
    p.write_text(json.dumps({"shapes": [{"id": "watershed:a", "file": "x.json"}]}))
    assert set(geo.index(tmp_path)["shapes"]) == {"watershed:a"}
    p.write_text(json.dumps({"shapes": [{"id": "watershed:b", "file": "x.json"}]}))
    import os
    os.utime(p, (0, 0))
    assert set(geo.index(tmp_path)["shapes"]) == {"watershed:b"}


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
    assert geo.nesting(entities.load(PROJECT)) == []


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
    store = entities.load(PROJECT)
    rec = store.get("land:parapolsky-dol")
    assert rec and rec["frame"] and not rec["geo"]
    # `own` is the box a map is composed on, and nothing is drawn without one.
    own = edition_ui.atlas_data(ROOT, store)["entities"]["land:parapolsky-dol"]["own"]
    assert own, "a framed entity should have a map of its own"

    leaf = {k: v for k, v in store.items()
            if v.get("within") != "land:parapolsky-dol"}
    assert geo.extent_of("land:parapolsky-dol", leaf, PROJECT) is None
    assert edition_ui.atlas_data(ROOT, leaf)["entities"]["land:parapolsky-dol"][
        "own"] == list(rec["frame"])

    # And it stands in for itself on the parent's map, where `member_extents`
    # supplies the boxes for nodes no other layer can identify. The frame is
    # the *fallback* there — `extent_of` first, wherever there is anything to
    # derive from.
    boxes = dict(geo.member_extents(rec["within"], leaf, PROJECT))
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
    live = dict(geo.member_extents(framed_parent["within"], store, PROJECT))
    derived = geo.extent_of("land:chukotka", store, PROJECT)
    assert derived is not None, "the fixture must have something to derive from"
    assert live.get("land:chukotka") == derived


# ------------------------------------------------- the seam nothing could see

def _geo_store(tmp_path, ident, polys):
    """A one-shape store. `polys` is a list of outer rings, each (lon, lat)."""
    d = tmp_path / "edition" / "geo"
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
    apart, `build_geo.prepare` had nothing to weld, and `geomap.js` draws one
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
    assert geo.meridian(PROJECT) == []


# ---------------------------------------------------- a selection, not a subject

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
def test_a_keyed_point_is_boxed_square_on_the_ground():
    """A degree of longitude is `cos(lat)` of a degree of latitude, and this book
    is at 66°N where that is 0.41 — so ±0.5° in both coordinates was a box 110 km
    tall and 45 km wide, and every village framed on its own extent came out a
    tall thin sliver with the settlement lost in the middle of it.

    Measured on the ground, because that is the claim: the two sides are the
    same distance, not the same number of degrees. A degree of longitude is
    `cos(lat)` of one of latitude at the box's mid-latitude, which is what the
    map's projection scales by too."""
    store = entities.load(PROJECT)
    for ident in ("place:uelen", "place:markovo"):
        rec = store[ident]
        assert entities.geo_points(rec) and not entities.geo_shapes(rec), \
            f"{ident} is not a bare point"
        w, s, e, n = geo.extent_of(ident, store, PROJECT)
        wide = (e - w) * math.cos(math.radians((s + n) / 2))
        assert abs(wide / (n - s) - 1.0) < 0.01


def test_the_widening_stops_short_of_the_pole():
    """`1/cos` runs away at 90°, and a runaway box is a map of the Arctic with a
    village somewhere in it. Nothing in this store is near the clamp — Wrangel is
    the northernmost record at about 71° — so this guards the arithmetic rather
    than a live case."""
    w, s, e, n = geo.point_box(89.9, 170.0)
    assert n - s == 2 * geo.POINT_BOX
    assert (e - w) / 2 == pytest.approx(
        geo.POINT_BOX / math.cos(math.radians(geo.POINT_BOX_MAX_LAT)))
