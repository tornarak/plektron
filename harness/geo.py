"""The shape store — `data/geo/`, read-only, and the checks over it.

Compiled by `tools/build_geo.py` from sources that live outside the repository
and **tracked** for that reason; `data/geo/SOURCES.md` is the provenance record
and carries the one licence condition (Asher 2007 is CC BY 4.0).

Nothing here writes, and nothing here imports a geometry library: the store is
plain GeoJSON with its longitudes already normalized into one continuous
window, so what is left is arithmetic. The heavy work — clipping, welding a
shape its publisher cut at the antimeridian, simplification — happened once, at
build time, where a library was available.

**A SHAPE KIND IS NOT AN ENTITY CLASS**, and this is now load-bearing rather
than merely tidy. `langarea:chuk1273`, never `people:chuk1273` — the two
vocabularies are held disjoint so that a reader looking at an entity file cannot
mistake one for the other. (The example used to be `language:`, which was an
entity class until the class was retired for saying nothing `people:` did not;
that it is now a *legal* shape kind is the invariant working, not failing —
nothing is disjoint from a set it has left.) That disjointness is what lets one
field hold both: a `geo:` member
is a point if it is two numbers, a shape if its kind is not an entity class, and
an entity if it is. No flag, and no wrong guess available. `geo bounds` has told
them apart this way since it was written; `entities._geo_member` is the same
rule one store lower down.

**`area:` was a second location field and is retired.** It named a shape while
`geo:` held a point, and a record was forbidden to carry both — a rule against
two fields contradicting each other, which is a rule two fields should not have
needed. `geo:` repeats now and the field is the union of its members, so an
entity drawn as two polygons names two, and the whole comma-joined composite
apparatus that let a single-valued field hold a union is gone with it.
`index()["shapes"]` is a plain dict of exactly what the build wrote, and every
member is looked up in it directly.

**A union still gets a row of its own in `listing`**, after the store's rows and
never among them: two polygons being one speaker area is a human's assertion
about `entities/`, not a shape `data/geo/` holds. It is synthesized for display
and claims nothing. Two entities may name the same pair — a people and the
subgroup inside it are the standing case — so the label names every claimant
rather than picking one.

THE CHECKS HERE REPORT AND DO NOT GATE. `verify` compares an authored `within:`
against containment: a basin delineated from a tributary's outlet is contained
in its trunk's by construction, so it is a real check — but a disagreement says
*one of two authored facts is wrong* and the geometry cannot say which, so the
row names the pair rather than a culprit. Where either end names several shapes
it emits a row per pair; the best pair would launder the disagreement.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from .parallel import ptrack

GEODIR = "data/geo"

#: Longitudes in the store live in [LON_BASE, LON_BASE+360); anything above 180
#: is west of the antimeridian. Written by the build into `index.json`, read
#: from there rather than restated — this is the fallback for a store built
#: before the field existed.
LON_BASE = 60.0

#: How far outside its own shape a `geo:` point may sit before anything says so,
#: in degrees. **Nothing measures this any more** — `entities.parse` refuses a
#: record carrying both a point and a shape, so the case cannot arise. Kept
#: because it is the one number that records what the tolerance *was for*: a
#: river's point is its mouth and the mouth is *on* the watershed boundary, so
#: this was never slack, it was the width of the thing being measured against.
POINT_SLACK = 0.05


#: How an `area:` names more than one shape. A comma, because the field is
#: authored by hand in a markdown list item and a comma is what a human writes
#: there. Whitespace around it is insignificant.
AREA_SEP = ","


def geodir(root: Path = Path(".")) -> Path:
    return root / GEODIR


# **The composite is gone, and it was a way of spelling.** `area:` held one
# value, so an entity drawn as two shapes had to name them in one string —
# comma-joined, sorted into a canonical order so the same union could not exist
# under two spellings, resolved back into members by `split_area` at every call
# site, and synthesized into an index row that did not exist in the store. All
# of that machinery served one purpose: letting a single-valued field hold two
# things. `geo:` repeats, so it holds them, and each member is an ordinary
# shape id that `index()["shapes"]` either has or has not.
#
# What is kept is the *reporting*: `composite_claims` still names an entity that
# draws several shapes, because "these two polygons are one speaker area" is
# still a human's assertion and still worth a row of its own.


def _composite_row(members: list[str], rows: list[dict]) -> dict:
    """One synthesized index row for a union of `members`.

    It carries the keys a real row does — the reading view reads `name`,
    `area_km2`, `source` and `precision` off it without knowing the difference —
    plus `members`, so anything printing it can say what it is made of.

    **`precision` takes the worst member's.** A union is no better delineated
    than its coarsest part, and rounding it up would let `verify` read a coarse
    pair as an exact one, which is the one direction that turns a limitation the
    source declared into a disagreement it did not.
    """
    bs = [r.get("bounds") for r in rows if r.get("bounds")]
    kinds = sorted({r.get("kind", "") for r in rows})
    return {
        "id": AREA_SEP.join(members),
        "kind": kinds[0] if len(kinds) == 1 else "composite",
        "name": " + ".join(r.get("name", "") for r in rows),
        "members": " ".join(members),
        "composite": True,
        "points": sum(r.get("points", 0) or 0 for r in rows),
        "area_km2": sum(float(r.get("area_km2") or 0) for r in rows),
        "source": " + ".join(dict.fromkeys(r.get("source", "") for r in rows)),
        "precision": "low" if any(r.get("precision") == "low" for r in rows)
                     else ("high" if any(r.get("precision") for r in rows) else ""),
        "bounds": ([min(b[0] for b in bs), min(b[1] for b in bs),
                    max(b[2] for b in bs), max(b[3] for b in bs)] if bs else []),
    }


@lru_cache(maxsize=8)
def _index_cached(path: str, mtime: float) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"window": doc.get("window", []),
            "lon_base": doc.get("lon_base", LON_BASE),
            "absent": doc.get("absent", {}),
            "shapes": {s["id"]: s for s in doc.get("shapes", [])}}


def index(root: Path = Path(".")) -> dict:
    """The census. Absence is an empty index, not an exception.

    A repository whose `data/geo/` has not been built yet must still run every
    other verb, so this is the `readings`/`load` pattern: `{}` rather than a
    raise, and the caller decides whether emptiness matters. `entity check`
    decides it does, for an `area:` that names something.

    Keyed on mtime so an edit during a long-lived `edition serve` is picked up
    without a restart — the store is small and the parse is cheap, but a server
    that had to be restarted to see a rebuilt shape would teach people to
    rebuild less.
    """
    p = geodir(root) / "index.json"
    try:
        return _index_cached(str(p), p.stat().st_mtime)
    except OSError:
        return {"window": [], "lon_base": LON_BASE, "absent": {}, "shapes": {}}


def shape(ident: str, root: Path = Path(".")) -> dict:
    """One shape's FeatureCollection, or `{}`.

    **One id, one row, one file.** It used to accept a composite as well and
    concatenate its members' features, because `area:` could name several shapes
    in one string and every caller passed that string through whole. A caller
    that wants several now asks for several — `geo_shapes(rec)` is the list —
    and each call is this, which is a dictionary lookup and a file read.
    """
    row = index(root)["shapes"].get(ident)
    if not row:
        return {}
    try:
        return json.loads((geodir(root) / row["file"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ------------------------------------------------------------ geometry

def rings(doc: dict, layer: str | None = None):
    """Every closed ring in a collection, as lists of (lon, lat).

    Polygon and MultiPolygon flattened together: for containment and extent
    nothing downstream cares which it was, and a caller that treated only one
    of the two would work on the Anadyr and fail on the Aleutians.
    """
    for f in doc.get("features", []):
        if layer and f["properties"].get("layer") != layer:
            continue
        g = f["geometry"]
        if g["type"] == "Polygon":
            polys = [g["coordinates"]]
        elif g["type"] == "MultiPolygon":
            polys = g["coordinates"]
        else:
            continue
        for poly in polys:
            for ring in poly:
                yield [(c[0], c[1]) for c in ring]


def polygons(doc: dict, layer: str | None = None):
    """The same rings, **grouped by polygon** — outer ring first, then its holes.

    This is the grouping GeoJSON actually declares, and `in_shape` needs it:
    parity counted across every ring in a collection makes two *overlapping*
    polygons cancel, so a point inside both reads as outside. A single source's
    MultiPolygon does not overlap itself, which is why the flat count survived
    this long, but nothing enforced that and nothing announced it.
    """
    for f in doc.get("features", []):
        if layer and f["properties"].get("layer") != layer:
            continue
        g = f["geometry"]
        if g["type"] == "Polygon":
            polys = [g["coordinates"]]
        elif g["type"] == "MultiPolygon":
            polys = g["coordinates"]
        else:
            continue
        for poly in polys:
            yield [[(c[0], c[1]) for c in ring] for ring in poly]


def lines(doc: dict, layer: str = "rivers"):
    for f in doc.get("features", []):
        if f["properties"].get("layer") != layer:
            continue
        g = f["geometry"]
        parts = ([g["coordinates"]] if g["type"] == "LineString"
                 else g["coordinates"] if g["type"] == "MultiLineString" else [])
        for part in parts:
            yield [(c[0], c[1]) for c in part], f["properties"].get("sorder", 0)


def bounds(doc: dict):
    """(west, south, east, north) over every coordinate in the collection."""
    xs, ys = [], []
    for f in doc.get("features", []):
        def walk(c):
            if c and isinstance(c[0], (int, float)):
                xs.append(c[0])
                ys.append(c[1])
            else:
                for part in c:
                    walk(part)
        walk(f["geometry"]["coordinates"])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def in_ring(pt, ring) -> bool:
    """Ray casting. The store's longitudes are already continuous, so a ring
    spanning the antimeridian is an ordinary ring here and needs no special
    case — which is the whole return on doing the shift at build time."""
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xc = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < xc:
                inside = not inside
    return inside


def in_shape(pt, doc: dict) -> bool:
    """Point inside any one of a collection's polygons, holes honoured by parity.

    Parity **within a polygon** rather than an outer/hole distinction: GeoJSON
    winding order is advisory and the sources here do not follow it
    consistently, so counting crossings is the reading that does not depend on
    a convention nobody enforced.

    **But the count is per polygon and the polygons are OR'd.** Parity across
    the whole collection is the same arithmetic only while no two polygons
    overlap: where they do, a point inside both crosses an even number of rings
    and reads as outside — a hole punched exactly where two shapes agree, which
    is the last place anyone would look for one. Nothing in the store overlaps
    itself today, so this was latent rather than visible; it is a correctness
    fix to the primitive `contains` and `verify` are built on, not a
    consequence of anything above it.
    """
    return any(sum(1 for r in poly if in_ring(pt, r)) % 2 == 1
               for poly in polygons(doc))


def distance_to(pt, doc: dict) -> float:
    """Degrees from a point to the nearest vertex of a shape. 0 inside it.

    A vertex distance and not a true point-to-segment distance, and that is
    enough for what it is for: saying whether a river's `geo:` point sits *on*
    its basin's boundary or somewhere else entirely. Named as approximate here
    so nobody later reads a number off it as a measurement.
    """
    if in_shape(pt, doc):
        return 0.0
    x, y = pt
    best = math.inf
    for ring in rings(doc):
        for rx, ry in ring:
            # Longitude degrees narrow with latitude; without the cosine a
            # point 1 degree east at 70N reads as further away than one 1
            # degree south, which is backwards.
            d = math.hypot((rx - x) * math.cos(math.radians(y)), ry - y)
            best = min(best, d)
    return best


def contains(outer: dict, inner: dict, sample: int = 200) -> float:
    """Fraction of `inner`'s vertices lying inside `outer`.

    Sampled rather than exhaustive: the Lena's outline is 6,000 points and the
    answer is the same. A fraction rather than a boolean because that is what
    the disagreement looks like — a tributary basin 98% inside its trunk is a
    delineation that rounded a ridge differently, and one 4% inside is a
    `within:` row naming the wrong river.
    """
    pts = [p for ring in rings(inner) for p in ring]
    if not pts:
        return 0.0
    step = max(1, len(pts) // sample)
    pts = pts[::step]
    return sum(in_shape(p, outer) for p in pts) / len(pts)


# ------------------------------------------------- an entity's own extent

#: Half-height of the box a lone `geo:` point is given, in degrees of latitude.
#: A point has no extent, and a frame computed from one is a division by zero
#: dressed up as infinite zoom. Half a degree is roughly a day's travel here,
#: which is about the scale at which a village is worth looking at.
POINT_BOX = 0.5

#: How far north `point_box` will still trust `1/cos`. Beyond it the widening
#: runs away, and the store's northernmost record is Wrangel at about 71°.
POINT_BOX_MAX_LAT = 80.0


def point_box(lat: float, lon: float) -> tuple[float, float, float, float]:
    """A box around a keyed point that is **square on the ground, not in degrees**.

    A degree of longitude is `cos(lat)` of a degree of latitude, and this book is
    at 66°N, where that is 0.41. So ±0.5° in both coordinates is a box 110 km
    tall and 45 km wide, and every village framed on its own extent came out a
    tall thin sliver with the settlement lost in the middle of it. Widening the
    longitude by `1/cos` makes the two sides the same distance on the ground,
    which is what "half a degree around the village" was always meant to say.

    It is a better *extent* as well as a better frame, which is why it is here
    rather than in the framing: an ancestor unions this box in, and the old one
    under-reported how far a coastal village reached along its coast.
    """
    span = POINT_BOX / max(math.cos(math.radians(
        min(abs(lat), POINT_BOX_MAX_LAT))), 1e-6)
    return (lon - span, lat - POINT_BOX, lon + span, lat + POINT_BOX)


def children(store: dict) -> dict[str, list[str]]:
    """`within:` inverted. **`entities.children`**, re-exported.

    It lived here while the tree was the atlas's alone, and it reads no
    geometry — it walks a field of the entity record and nothing else. Two of
    the store's chains are already `people` inside `people`, so a caller
    wanting the tree over a non-geographic class had to import the geography to
    get it. Imported lazily because `entities` imports this module at the top.
    """
    from .entities import children as _children
    return _children(store)


def geo_points(rec: dict) -> list[tuple[float, float]]:
    """`geo:`'s point members. **`entities.geo_points`**, re-exported."""
    from .entities import geo_points as _f
    return _f(rec)


def geo_shapes(rec: dict) -> list[str]:
    """`geo:`'s shape members. **`entities.geo_shapes`**, re-exported."""
    from .entities import geo_shapes as _f
    return _f(rec)


def geo_refs(rec: dict) -> list[str]:
    """`geo:`'s entity members. **`entities.geo_refs`**, re-exported."""
    from .entities import geo_refs as _f
    return _f(rec)


def relatives(ent_id: str, store: dict) -> list[str]:
    """Every ancestor and descendant. **`entities.relatives`**, re-exported."""
    from .entities import relatives as _relatives
    return _relatives(ent_id, store)


def common_ancestors(idents, store: dict) -> list[str]:
    """What contains all of these, nearest first. **`entities.common_ancestors`**.

    Re-exported for the same reason `children` is: it reads `within:` and no
    geometry, so it belongs beside the field, and the map is its heaviest caller.
    """
    from .entities import common_ancestors as _common
    return _common(idents, store)


def member_extents(ent_id: str, store: dict,
                   root: Path = Path(".")) -> list[tuple[str, tuple]]:
    """Descendants no other layer of a map can identify, with their extents.

    **The complement of what gets drawn.** A descendant with a shape is a
    member; one with a point is a pin; and a descendant with neither is skipped
    entirely by `member_shapes`, which descends *through* it to whatever lies
    below. Chukotka is the standing case — it appears nowhere on the Russian Far
    East's map, and its name lights up nothing, while every basin under it does.

    An extent is all there is to offer for such a node, and it is legal to offer
    where a *boundary* would not be: it is computed from what lies beneath, it is
    a rectangle, and nothing mistakes a rectangle for a coastline. What makes it
    tolerable on the page is that the caller draws it invisible — see
    `edition_ui.map_context`.
    """
    kids = children(store)
    out, seen = [], {ent_id}

    def walk(ident: str) -> None:
        for k in kids.get(ident, []):
            if k in seen:
                continue
            seen.add(k)
            rec = store.get(k)
            if rec is None:
                continue
            if not rec["geo"]:
                # **A declared `frame:` is the extent here, though `extent_of`
                # ignores it.** That function answers "how big is this thing",
                # which a parent must not size itself on — a viewport carries
                # padding somebody chose for another map. This layer asks a
                # different question: what box can stand in for a node that has
                # nothing else to draw. `land:parapolsky-dol` has a frame, no
                # shape, no point and no children, so it appeared on no map at
                # all — not its parent's, and not its own, which reported
                # "nothing to draw" about an entity whose extent the store knew.
                box = extent_of(k, store, root) or rec["frame"]
                if box:
                    out.append((k, box))
            walk(k)

    walk(ent_id)
    return out


def member_shapes(ent_id: str, store: dict, _seen=None) -> list[tuple[str, str]]:
    """The nearest descendants that have a shape, as `(entity, shape)`.

    One level down is right where the children are shapes — the Kolyma showing
    its tributaries. It is wrong at the top of the tree, where the children are
    *structure*: the Russian Far East's children are Chukotka and Kamchatka,
    neither of which any source draws, so a one-level rule left the map showing
    only the basins that happened to hang off the root directly. Descending
    until a shape turns up is what makes a structural node draw the country
    under it rather than an arbitrary half of it.

    **Pairs, and the entity is the half that is not obvious.** It used to return
    shape ids alone, which is all a renderer needs to draw them — but a reader
    hovering a child's name wants that child lit up on the map, and the descent
    above is exactly what makes the drawn member *not* reliably a direct child.
    Two entities may also share one shape — a people and a subgroup inside it
    may both name the one Asher polygon — so the shape cannot identify the
    member even in principle.
    """
    seen = _seen or set()
    if ent_id in seen:
        return []
    seen = seen | {ent_id}
    out = []
    for kid in children(store).get(ent_id, []):
        rec = store.get(kid)
        if rec is None:
            continue
        # **One pair per shape**, where this used to append the whole `area:`
        # field as a single id and lean on `geo.shape` to resolve a composite
        # back into members. A record may name several shapes, and a caller that
        # draws them draws each; the composite was only ever a way of spelling
        # that in a field that held one value.
        shapes = geo_shapes(rec)
        if shapes:
            out += [(kid, sid) for sid in shapes]
        else:
            out += member_shapes(kid, store, seen)
    return out


def extent_of(ent_id: str, store: dict, root: Path = Path("."),
              _seen=None) -> tuple | None:
    """What to frame a map of this entity on, in store longitudes.

    Four sources, unioned: its `geo:` shapes, its `geo:` points, the extents of
    the entities its `geo:` names, and **the union of what lies beneath it**.
    The last is what makes the tree navigable at all —
    no source holds a polygon for Chukotka or the Russian Far East, and none
    should: they are tree structure, not shapes. A frame is a viewport and not
    a claim, which is why computing one is legal where inferring a *boundary*
    for Chukotka would not be. The view says so in as many words.

    Cycle-guarded even though `entity check` gates acyclicity, because this
    runs inside a page render where a hang is worse than a wrong answer.

    **`seen` is a path guard and not a visited set**, which is what lets it
    cover two edge kinds at once without a second mechanism: it is threaded down
    each branch functionally (`seen | {ent_id}`), so `geo:` members and tree
    children share one discipline and a cycle mixing the two — `A geo: B`,
    `B within: A` — terminates on the same rule `within:` alone always did. A
    diamond is *not* pruned, and should not be: two peoples naming one village
    both take its box, and a box unioned twice is the same box.
    """
    rec = store.get(ent_id)
    if rec is None:
        return None
    seen = _seen or set()
    if ent_id in seen:
        return None
    seen = seen | {ent_id}

    # **Four sources, unioned, never a first-one-wins chain.** Three of them are
    # the record's own `geo:` read three ways — its shapes, its points, and the
    # entities it names — and the fourth is the tree beneath it. The chain used
    # to be `area:` *else* `geo:`, which was only ever expressible because the
    # two were separate fields and a record was forbidden to carry both; one
    # field of members has nothing to prefer.
    boxes = [bounds(shape(sid, root)) for sid in geo_shapes(rec)]
    boxes += [point_box(lat, _shifted(lon, index(root)))
              for lat, lon in geo_points(rec)]
    # **A named entity's extent is transcluded, and that is a different relation
    # from containment.** `people:naukans` is not *inside* Naukan — it is the
    # people of three villages, and its extent is theirs. Saying that with
    # `within:` bought the right box by asserting an ethnicity was a place.
    boxes += [extent_of(m, store, root, seen) for m in geo_refs(rec)]
    # **Always union the children in, even when the entity has an extent of its
    # own.** Stopping at the first source found meant a parent with a `geo:`
    # point framed on that point alone, and Uelen — inside the Chukchee
    # Peninsula by the store's own `within:` — fell outside its parent's map.
    # A parent that cannot show its own children is the one thing the tree is
    # for.
    boxes += [extent_of(k, store, root, seen)
              for k in children(store).get(ent_id, [])]

    boxes = [b for b in boxes if b]
    # **A people with nothing of its own falls back to its parent's extent.**
    # Scoped to `people:` and to nothing else, because it is the one class where
    # the fallback is not a guess: a subgroup of an ethnicity lives inside that
    # ethnicity's area by what the word means, so the parent's box is a true
    # bound on the child even where no source has drawn the child at all. The
    # Reindeer and Maritime Chukchi, the Kavraˊlɪt and the Chuvans are otherwise
    # invisible in an atlas that is largely about them.
    #
    # **A bound, not a boundary**, which is the same distinction `frame:` makes:
    # the map shows where to look, and the card says the extent is the parent's.
    # `geo verify` goes on listing them, because a real shape would still be
    # better and two of the four might one day get one.
    #
    # The cycle guard makes this terminate: the parent unions its children back
    # in, this child is already in `seen`, and so contributes nothing.
    #
    # **`within:` first, then `part-of:`** — where it *is*, before what it
    # belongs to — and having both is what stopped this being a choice between
    # two wrong answers. The Naukans are a Yupik people who lived in one
    # village: under the single old field, `within: people:yupik` inherited the
    # whole Central-plus-Pacific Yupik language area for one settlement, and
    # `within: place:naukan` bought the extent by dropping the fact that they
    # are Yupik. Now the village supplies the box and `part-of:` keeps the
    # ethnicity, and neither reader has to be wrong. The Reindeer and Maritime
    # Chukchi, the Kavraˊlɪt and the Chuvans have no village to name and fall
    # through to the second, which is the case this fallback was written for
    # and remains true for: a subgroup lives inside its ethnicity's area by
    # what the word means.
    # Scoped to `people:` and to nothing else, as it always was: `place:pitlekai`
    # has a `within:` and no coordinate, and inheriting Chukotka's box would
    # report it located when the worklist should be asking somebody to place it.
    # An ethnic subgroup is the one case where the parent's box is a true bound
    # rather than a guess.
    if not boxes and rec["class"] == "people":
        # Lazy: `entities` imports this module at the top, as `children` below.
        from .entities import tree_parent

        up = tree_parent(rec)
        if up:
            return extent_of(up, store, root, seen)
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def located(ent_id: str, store: dict, root: Path = Path(".")) -> bool:
    """Whether this entity has anywhere to put on a map, itself or below it.

    **A declared `frame:` counts, and `extent_of` still ignores it.** Those are
    two different questions and the split is deliberate. `extent_of` answers
    "how big is this thing", which is what a *parent* sizes itself on, and a
    frame is a viewport — usually wider than its subject — so unioning one into
    an ancestor's box would inflate it with padding somebody chose for a
    different map. But "can the atlas draw this" is answered yes by a frame
    alone: the frame *is* the viewBox.

    Without this, `land:russian-far-east` and `water:bering-strait` counted as
    unlocated and as framed-by-their-members, and neither is true of either —
    their frames were authored precisely because the derived box was wrong.
    """
    rec = store.get(ent_id)
    if rec is not None and rec["frame"]:
        return True
    return extent_of(ent_id, store, root) is not None


def pins_under(ent_id: str, store: dict, root: Path = Path("."),
               depth: int = 2) -> list[tuple[float, float, str, str]]:
    """`geo:` points at and below an entity, as (lon, lat, label, entity).

    Bounded by depth rather than by count: a map of the Russian Far East that
    plotted every village in the store would be a field of dots, and the two
    levels below the subject are the ones whose position the subject explains.

    The entity rides along for the same reason it does on a member shape: an
    entity whose only geography is a point is highlighted by lighting its pin,
    and the label is a canonical name, which is not an identity.

    **"Below" is the containment tree, and a `geo:` member is not below.** It is
    what the record *is* — `people:maritime-chukchi` does not contain its
    villages, it is the people of them — so following one here was tried and
    taken out. `edition_ui.map_context` expands a member into the selection
    instead, which makes it a subject in its own right: it gets its own pin from
    its own turn through this walk, it is named in the tree as chosen, and a
    reader can take it off again. Followed from *here* it could not be taken off,
    because this walk sees a selection and not a dismissal, and put the pin back
    on every render.

    The `seen` guard stays. It is no longer load-bearing — `entity check` gates
    the containment chain acyclic — but it costs one set and this runs inside a
    page render, where the wrong shape of loop is a hang rather than a wrong
    picture.
    """
    idx = index(root)
    kids = children(store)
    out, seen = [], set()

    def walk(ident: str, d: int):
        if ident in seen:
            return
        seen.add(ident)
        rec = store.get(ident)
        if rec is None:
            return
        for lat, lon in geo_points(rec):
            out.append((_shifted(lon, idx), lat, rec["canonical"], ident))
        if d > 0:
            for k in kids.get(ident, []):
                walk(k, d - 1)

    walk(ent_id, depth)
    return out


# ------------------------------------------------------------ the reports

def listing(root: Path = Path(".")) -> dict:
    """The census, with the entity that claims each shape."""
    from .entities import load

    idx = index(root)
    store = load(root)
    claims = member_claims(store)

    rows = []
    for ident, s in sorted(idx["shapes"].items()):
        rows.append({
            "id": ident,
            "kind": s.get("kind", ""),
            "name": s.get("name", ""),
            "points": s.get("points", 0),
            "area_km2": int(s.get("area_km2") or 0),
            "claimed_by": " ".join(sorted(claims.get(ident, []))),
            "source": s.get("source", ""),
        })
    absent = [absent_row(k, v) for k, v in sorted(idx["absent"].items())]
    # The unions some entity has authored, listed after the store's own rows and
    # never among them: a union is a fact about `entities/` and the census above
    # is a fact about `data/geo/`. **Synthesized here rather than looked up**,
    # since a composite stopped being a resolvable id the day `geo:` began
    # holding its members apart — and the row was only ever built for display.
    comp = []
    for spec, ids in sorted(composite_claims(store).items()):
        rows_for = [idx["shapes"].get(m) for m in spec.split(AREA_SEP)]
        if all(rows_for):
            row = _composite_row(spec.split(AREA_SEP), rows_for)
            comp.append({"id": spec, "name": row["name"],
                         "members": row["members"],
                         "claimed_by": " ".join(ids)})
    return {
        "scope": [{"shapes": len(rows),
                   "claimed": sum(1 for r in rows if r["claimed_by"]),
                   "window": " ".join(f"{v:.1f}" for v in idx["window"]),
                   "absent": len(absent),
                   "composites": len(comp)}],
        "shapes": rows,
        "composites": comp,
        "absent": absent,
    }


def absent_row(what: str, why) -> dict:
    """One `absent` entry, flattened. Tolerates the old string form.

    The block began as "a Tier-1 code Asher draws no polygon for" and now also
    holds a feature **no gazetteer in hand carries at all**, which is a
    different absence and would be a misreading of the first if it arrived
    wearing its shape. So a row says what was `sought` and in which `source` it
    was looked for. A plain string is read as the `why` of the original kind,
    so a store built before the widening still lists.
    """
    if isinstance(why, dict):
        return {"what": what, "sought": why.get("sought", ""),
                "source": why.get("source", ""), "why": why.get("why", "")}
    return {"what": what, "sought": "", "source": "asher2007", "why": why}


def member_claims(store: dict) -> dict[str, list[str]]:
    """`{shape id: [entity ids]}` — every shape member of every `geo:`.

    **A claim is one hop.** An entity that reaches a shape only through another
    entity's `geo:` does not claim it: `people:naukans` names `place:naukan`,
    and counting that as a claim on whatever the village claims would make
    `unclaimed` go quiet about shapes nobody has actually pointed at.

    It used to have to split a composite back into members to say this at all,
    which is where the argument in its old docstring came from — that an entity
    claiming a union must count against each of its parts, or the members read
    as unclaimed *and* the union read as a shape `data/geo/` does not hold. The
    field holds them apart now, so the rule needs no recovery step.
    """
    claims: dict[str, list[str]] = {}
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        for m in geo_shapes(rec):
            claims.setdefault(m, []).append(rec["id"])
    return claims


def composite_claims(store: dict) -> dict[str, list[str]]:
    """`{shapes joined: [entity ids]}` for every `geo:` naming more than one.

    **Sorted, which is all that is left of the canonical spelling.** It used to
    be the composite's *identity* — an id that had to be resolvable, so two
    orderings of one union could not exist and report the same member as claimed
    and unclaimed at once. Nothing resolves it now; it is a grouping key for a
    report, and sorting it is what keeps two entities that named the same pair
    in either order on one row.
    """
    out: dict[str, list[str]] = {}
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        shapes = geo_shapes(rec)
        if len(shapes) > 1:
            key = AREA_SEP.join(sorted(dict.fromkeys(shapes)))
            out.setdefault(key, []).append(rec["id"])
    return out


#: What a `within:` parent of each geographical class can hold, and why not.
#: Keyed by the *parent*'s class; the value is the set of child classes that are
#: a finding under it, with the reading.
#:
#: **This is the check the four-class split was for.** While `place:` held a
#: village and a peninsula alike, "X is inside Y" said nothing a rule could
#: test: every parent might be a region. Now a class states the shape of the
#: thing, and two impossibilities fall straight out of it — a *point* holds
#: nothing at all, and a *body of open water* holds no ground.
#:
#: **`land:` is deliberately not a finding under `water:`.** It was, on the
#: reading that a body of open water holds no ground, and the first run said so
#: about the Diomedes and St. Lawrence Island — which are islands, which is what
#: land inside water *is*, and which have nowhere else to go: `within:` is the
#: only relation the store has, and an island 60 km offshore belongs to no land
#: region. Two true rows in three is how a report stops being read. What is left
#: is what cannot be true at any scale: a settlement adrift in open water, and a
#: drainage basin — dry ground by definition, whatever it drains into — inside
#: the bay it empties to.
#:
#: Reports and never gates, like everything else `verify` returns.
NESTING = {
    "place": (("place", "land", "water", "river"),
              "a point contains nothing"),
    "water": (("place", "river"),
              "a settlement or a drainage basin inside open water"),
}


def nesting(store: dict) -> list[dict]:
    """Every `within:` whose two classes cannot both be true. No geometry.

    Deliberately separate from `verify`'s containment rows, which compare two
    *shapes* and can only ever speak about the pairs where both were drawn. This
    speaks about every pair in the store, including the ones nothing locates,
    which is most of them — and it is the half a shape could never supply, since
    a point and a region look identical to a polygon test the moment one of them
    is missing.
    """
    out = []
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        parent = store.get(rec["within"]) if rec["within"] else None
        if not parent:
            continue
        bad, why = NESTING.get(parent["class"], ((), ""))
        if rec["class"] in bad:
            out.append({"child": rec["id"], "parent": parent["id"],
                        "reading": why})
    return out


#: How far from 180 an outer ring's edge may sit and still count as *on* the cut.
#: Wider than `build_geo.MERIDIAN_SNAP` on purpose: that one decides whether to
#: move a vertex, and this one only decides whether to say something.
MERIDIAN_EPS = 0.05


def meridian(root: Path = Path(".")) -> list[dict]:
    """Shapes drawn as more than one piece cut at the antimeridian.

    **The seam nothing could see.** A publisher cutting a shape at 180 leaves two
    halves, and `build_geo.prepare` welds them — when they meet. Natural Earth's
    10m Wrangel Island left its halves 0.011° apart and its Bering Sea flush but
    unmerged, so the store held two rings where the world has one thing, and
    `geomap.paths` emits one stroked path per ring: a line down the middle of
    every such shape, on every map that drew it. No gate said anything. It was
    found by a reader looking at the atlas, which is the one way a rendering
    defect gets found when nothing measures it.

    A ring that *crosses* 180 is welded and is the healthy case. What this counts
    is an outer ring whose boundary **ends at** the meridian without crossing it,
    and a shape with more than one of those is a shape cut into pieces.

    **One is not reported and that is deliberate.** `langarea:chuk1273` stops
    dead at 180 because that is where Asher drew it, with nothing on the far side
    to weld to — the build already says so as a note, and repeating it here would
    be a permanent row about a source's honest limit.

    **Composites are not walked either.** `people:chukchi` draws Asher's polygon
    beside `base:chukotka-east-of-meridian`, two shapes abutting at 180 by
    design, and the seam between them is the visible trace of an editorial
    decision recorded in `SOURCES.md`. A row would fire every run about something
    nobody intends to change, which is how a report stops being read.
    """
    idx = index(root)
    out = []
    for ident, row in sorted(idx["shapes"].items()):
        doc = shape(ident, root)
        cut = 0
        for poly in polygons(doc):
            xs = [x for x, _ in poly[0]]
            lo, hi = min(xs), max(xs)
            if lo < 180.0 - MERIDIAN_EPS and hi > 180.0 + MERIDIAN_EPS:
                continue                      # crosses the meridian: welded
            if abs(hi - 180.0) <= MERIDIAN_EPS or abs(lo - 180.0) <= MERIDIAN_EPS:
                cut += 1
        if cut > 1:
            out.append({
                "shape": ident, "pieces": cut, "source": row.get("source", ""),
                "reading": "cut at the antimeridian and not welded — every ring "
                           "is stroked, so this draws a seam"})
    return out


def verify(root: Path = Path("."), tick: Callable | None = None) -> dict:
    """The geometry against what a human authored. Reports; never gates.

    Findings, and the wording of each is load-bearing:

    - **nesting**, where the two classes of a `within:` pair contradict each
      other — a child under a `place:`, which is a point, or dry ground under a
      `water:`, which is open water. `NESTING` carries the argument.
    - **containment**, where a child and its `within:` parent both have a
      shape. Named as a *pair*: the geometry says the two authored facts
      disagree and cannot say which of them is wrong.
    - **a shape two entities claim**, which is legal — a people and a subgroup
      inside it may both point at the one Asher polygon, and forcing a choice
      would be this edition deciding something the source does not.
    - **a shape nothing claims**, and its inverse, **an entity nothing locates**.

    The last pair is the store's two-sided worklist. `unclaimed` has always
    answered "what has the atlas got that nobody has pointed an entity at";
    `unlocated` answers the question a human providing coordinates actually has
    — which entities inside a subtree the atlas *can* draw carry neither `geo:`
    nor `area:`, so they ride on their parent's frame and put nothing on it.
    Scoped to located subtrees deliberately: every person and source in the
    store is unlocated and always will be, and a worklist that listed them
    would list nothing worth doing among a great deal that is not.
    """
    from .entities import load

    idx = index(root)
    store = load(root)
    docs: dict[str, dict] = {}

    def doc_for(ident: str) -> dict:
        if ident not in docs:
            docs[ident] = shape(ident, root)
        return docs[ident]

    containment, shared = [], []
    claims = member_claims(store)
    for rec in ptrack(sorted(store.values(), key=lambda r: r["id"]), tick):
        parent = store.get(rec["within"]) if rec["within"] else None
        if not parent:
            continue
        # **One row per (child shape, parent shape) pair**, where a composite
        # used to be measured whole. Taking the best pair, or the union, would
        # launder exactly the disagreement this report exists to show: a basin
        # 90% inside one half of a two-shape parent and 0% inside the other is
        # two facts, and only one of them is reassuring.
        for child_id in geo_shapes(rec):
            for parent_id in geo_shapes(parent):
                frac = contains(doc_for(parent_id), doc_for(child_id))
                coarse = [i for i in (child_id, parent_id)
                          if idx["shapes"].get(i, {}).get("precision") == "low"]
                containment.append({
                    "child": rec["id"], "child_area": child_id,
                    "parent": parent["id"], "parent_area": parent_id,
                    "inside": round(frac, 3),
                    "coarse": " ".join(coarse),
                    "reading": _reading(
                        frac, bool(coarse),
                        parent_id.startswith("marine:")),
                })

    for ident, ids in sorted(claims.items()):
        if len(ids) > 1:
            shared.append({"shape": ident, "claimed_by": " ".join(ids)})

    unclaimed = sorted(i for i, s in idx["shapes"].items()
                       if s.get("kind") != "base" and i not in claims)
    open_rows = unlocated(store, root)
    nested = nesting(store)
    seams = meridian(root)
    return {
        "scope": [{"pairs_checked": len(containment),
                   "disagree": sum(1 for c in containment
                                   if c["reading"] == "disagrees"),
                   "nesting": len(nested),
                   "seams": len(seams),
                   "shared": len(shared),
                   "unclaimed": len(unclaimed),
                   "unlocated": len(open_rows)}],
        "nesting": nested,
        "meridian": seams,
        "containment": containment,
        "shared": shared,
        "unclaimed": [{"shape": i} for i in unclaimed],
        "unlocated": open_rows,
    }


def unlocated(store: dict, root: Path = Path(".")) -> list[dict]:
    """Entities inside a locatable subtree that carry no `geo:`, `area:` or `frame:`.

    The inverse of `unclaimed`, and the half of the atlas's worklist that faces
    a human rather than the store: these are the rows an editor is looking for
    when they sit down to supply coordinates. `entity locate` is what answers one.

    **Scoped by the tree, not by class.** An entity counts if it is `within:`
    something the atlas can draw or has anything drawable beneath it — the same
    `located` test `/atlas` uses to pick its roots. Without that scope every
    person and source in the store is unlocated forever, and a worklist mostly
    made of rows nobody will ever act on is one nobody reads.

    `wants` says which of the two would settle it: a thing with children that
    are drawn needs no shape of its own, and asking for one would be asking a
    human to invent a boundary for Chukotka.

    **A `frame:` settles a row as surely as a shape does.** It is an authored
    statement of where the map should look, and it is written in exactly the
    cases where the derived box was wrong — `land:russian-far-east` and
    `water:bering-strait` are not framed by their members in any useful sense,
    which is why somebody framed them by hand. Listing them as wanting a
    coordinate asks for work that has already been done.
    """
    from .entities import tree_parent

    kids = children(store)
    rows = []
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        # **A shape, a point or a frame settles the row; a pointer does not.**
        # An entity whose `geo:` holds only other entities has said where to look
        # without anybody yet having said where *they* are, so the row survives
        # until `extent_of` can actually resolve it. Reading "has a `geo:`" as
        # settled would have taken `people:siberian-yupik` off the worklist by
        # naming six villages, three of which might be unplaced.
        if geo_shapes(rec) or geo_points(rec) or rec["frame"]:
            continue
        if geo_refs(rec) and extent_of(rec["id"], store, root) is not None:
            continue
        # `tree_parent`, not `rec["within"]`: the four ethnic subgroups hang
        # from `part-of:` and have no `within:` at all, and reading the raw
        # field dropped every one of them out of this worklist — off the tree
        # the scope is measured against, and so silently invisible. That is the
        # blind spot this function's own docstring warns about, reached by a
        # field split rather than by a missing `within:`.
        up = tree_parent(rec)
        parent = store.get(up) if up else None
        under = bool(parent) and located(parent["id"], store, root)
        # `located`, not `member_shapes`: a child's `geo:` point frames its
        # parent exactly as a child's polygon does, and `extent_of` has said so
        # since the day a parent stopped framing on its own point alone. Asking
        # `member_shapes` here would have told the Russian Far East it wanted a
        # boundary of its own because its descendants were pins rather than
        # shapes — the one thing this atlas refuses to invent.
        beneath = located(rec["id"], store, root)
        if not under and not beneath:
            continue
        rows.append({
            "id": rec["id"],
            "canonical": rec["canonical"],
            # The tree edge, whichever field carried it — a row reading blank
            # while the entity plainly hangs somewhere would send a reader to
            # the wrong file.
            "within": up,
            "wants": ("its members located, then transcluded"
                      if geo_refs(rec)
                      else "its parent's extent, inherited"
                      if rec["class"] == "people" and not kids.get(rec["id"])
                      else "framed by its members" if beneath
                      else "a geo:"),
            "children": len(kids.get(rec["id"], [])),
        })
    return rows


#: Where a pair of high-precision delineations must land to read as contained.
#: A shared divide is a shared *line*, so a child's vertices sit on it and land
#: either side by rounding; a couple of percent is that, not a disagreement.
EXACT = 0.98
#: The floor below which even two coarse delineations are saying different
#: things. The five true river relations in the store measure 0.70-0.87 with a
#: coarse member; a `within:` row naming the wrong river measures far lower,
#: because the two basins then barely overlap at all.
COARSE_FLOOR = 0.6


def _reading(frac: float, coarse: bool, marine_parent: bool = False) -> str:
    """What a containment fraction is allowed to be read as.

    **The service declares its own precision and this respects it.** Above
    50,000 km² the delineator reverts to a coarse DEM and says so; a coarse
    parent's boundary wanders by tens of kilometres, and a tributary basin
    measured against it lands at 0.70-0.87 while being perfectly real. Reading
    that as "disagrees" would make the check a machine for rejecting true rows —
    the second witness declaring the first wrong on the strength of a limitation
    it announced in advance.

    So the bar moves with the evidence, and the row names the coarse member so
    the number is never read as better than what produced it.

    **A `marine:` parent is not a container at all**, and that is the same
    argument again. Natural Earth's marine polygons *tile* the ocean: Karaginskiy
    Gulf abuts the Bering Sea rather than sitting inside it, and it measured 0.068
    against it — worse than against the Kamchatka peninsula it is not part of.
    They are also drawn around land, so an island in a gulf reads 0.625 while
    being exactly where it says it is. Both authored facts are true and this
    geometry cannot witness either, so the row says so instead of saying
    "disagrees" about a source that never claimed to nest.
    """
    if marine_parent:
        return "not measurable — marine shapes tile rather than nest"
    if frac >= EXACT:
        return "contained"
    if coarse:
        return "consistent with a coarse delineation" if frac >= COARSE_FLOOR \
            else "disagrees"
    return "disagrees"


def _shifted(lon: float, idx: dict) -> float:
    base = idx.get("lon_base", LON_BASE)
    return lon + 360.0 if lon < base else lon


def boxes(idents, root: Path = Path("."), margin: float = 0.0) -> dict:
    """A box per id and their union — what a human writing a `frame:` needs.

    **Entity ids and shape ids in one list**, told apart by their prefix. That
    is only decidable because the two vocabularies are held disjoint — a shape
    kind may never be an entity class, the rule `entities.parse` enforces so
    that a member spelt `kind:slug` cannot quietly read as an entity reference — so
    this needs no flag and can make no wrong guess.

    An entity's box is `extent_of`: its shape, else its point, else the union of
    everything beneath it. A shape's is the polygon's own. Longitudes are the
    store's shifted window, which is what `frame:` and `--frame` also take, so
    the printed `frame` field is paste-ready.

    **`margin` is content, not breathing room.** `geomap.Frame` already pads a
    map by `PAD` on every side; a margin here says *show this much more of the
    world*, which is a different question and the one a person asking for a
    frame is usually asking. Degrees, applied to all four sides — deliberately
    not a percentage, because a percentage of a box 60° wide and 20° tall is
    two different distances and the caller would have to know which.
    """
    from .entities import ENTITY_CLASSES, load

    store = load(root)
    rows, got = [], []
    for i in idents:
        kind = str(i).partition(":")[0]
        if kind in ENTITY_CLASSES:
            box = extent_of(str(i), store, root)
            what = "entity" if str(i) in store else "unknown entity"
        else:
            doc = shape(str(i), root)
            box = bounds(doc) if doc else None
            what = "shape" if doc else "unknown shape"
        rows.append({"id": str(i), "kind": what,
                     "west": round(box[0], 4) if box else None,
                     "south": round(box[1], 4) if box else None,
                     "east": round(box[2], 4) if box else None,
                     "north": round(box[3], 4) if box else None})
        if box:
            got.append(box)

    if not got:
        return {"rows": rows, "union": []}
    w = min(b[0] for b in got) - margin
    s = min(b[1] for b in got) - margin
    e = max(b[2] for b in got) + margin
    n = max(b[3] for b in got) + margin
    return {
        "rows": rows,
        "union": [{
            "west": round(w, 4), "south": round(s, 4),
            "east": round(e, 4), "north": round(n, 4),
            "span_lon": round(e - w, 4), "span_lat": round(n - s, 4),
            "margin": margin,
            # The exact string `entity locate --frame` takes, so the answer is
            # pasted rather than retyped from four columns.
            "frame": f"{w:g} {s:g} {e:g} {n:g}",
        }],
    }
