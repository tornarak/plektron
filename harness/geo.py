"""The shape store — `data/geo/`, read-only, and the checks over it.

Compiled by `tools/build_geo.py` from sources that live outside the repository
and **tracked** for that reason; `data/geo/SOURCES.md` is the provenance record
and carries the one licence condition (Asher 2007 is CC BY 4.0).

Nothing here writes, and nothing here imports a geometry library: the store is
plain GeoJSON with its longitudes already normalized into one continuous
window, so what is left is arithmetic. The heavy work — clipping, welding a
shape its publisher cut at the antimeridian, simplification — happened once, at
build time, where a library was available.

**A shape kind is not an entity class**, and `entities.parse` refuses one that
is. `langarea:chuk1273`, never `language:chuk1273`: an entity file carries
`within: place:chukotka` two lines from `area: langarea:chuk1273`, and a reader
who cannot tell the two apart by looking is one keystroke from an `area:` that
resolves as an entity reference.

THE TWO CHECKS, AND WHY NEITHER GATES. `verify` compares an authored `within:`
against containment, and an authored `geo:` point against its own shape. Both
report. A basin delineated from a tributary's outlet is contained in its
trunk's by construction, so containment is a real check — but a disagreement
says *one of two authored facts is wrong* and the geometry cannot say which, so
the row names the pair rather than a culprit. And a river's natural point is
its mouth, which sits **on** the boundary the basin was delineated from, so a
gate on point-in-shape would false-positive by construction; the report carries
the distance instead, and a boundary-hugging point is not a finding.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

GEODIR = "data/geo"

#: Longitudes in the store live in [LON_BASE, LON_BASE+360); anything above 180
#: is west of the antimeridian. Written by the build into `index.json`, read
#: from there rather than restated — this is the fallback for a store built
#: before the field existed.
LON_BASE = 60.0

#: How far outside its own shape a `geo:` point may sit before `verify` says
#: anything, in degrees. A river's point is its mouth and the mouth is *on* the
#: watershed boundary, so the tolerance is not slack — it is the width of the
#: thing being measured against.
POINT_SLACK = 0.05


def geodir(root: Path = Path(".")) -> Path:
    return root / GEODIR


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
    """One shape's FeatureCollection, or `{}`."""
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
    """Point in a collection's outer rings, holes honoured by parity.

    Parity across every ring rather than an outer/hole distinction: GeoJSON
    winding order is advisory and the sources here do not follow it
    consistently, so counting crossings is the reading that does not depend on
    a convention nobody enforced.
    """
    hits = sum(1 for r in rings(doc) if in_ring(pt, r))
    return hits % 2 == 1


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

#: Half-width of the box a lone `geo:` point is given, in degrees. A point has
#: no extent, and a frame computed from one is a division by zero dressed up as
#: infinite zoom. Half a degree is roughly a day's travel here, which is about
#: the scale at which a village is worth looking at.
POINT_BOX = 0.5


def children(store: dict) -> dict[str, list[str]]:
    """`within:` inverted — parent id to the ids directly under it."""
    kids: dict[str, list[str]] = {}
    for rec in store.values():
        if rec["within"]:
            kids.setdefault(rec["within"], []).append(rec["id"])
    for v in kids.values():
        v.sort()
    return kids


def relatives(ent_id: str, store: dict) -> list[str]:
    """Every ancestor and every descendant, at any depth.

    **Not the same set as what a map draws**, and that is the point of it
    existing. `member_shapes` stops at the nearest descendant *with* a shape, so
    Chukotka is skipped on the Russian Far East's map and the Chukchee Peninsula
    below it never appears at all — yet both are one click from where a reader
    is standing, and both are what the pane exists to make cheap to reach.

    Cycle-safe by the same `seen` discipline as `extent_of`: `entity check`
    gates acyclicity, but this runs inside a page render, where a hang is worse
    than a wrong answer.
    """
    kids = children(store)
    out, seen = [], {ent_id}

    def down(ident: str) -> None:
        for k in kids.get(ident, []):
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
            down(k)

    down(ent_id)
    up = store.get(ent_id, {}).get("within") or ""
    while up and up not in seen:
        seen.add(up)
        out.append(up)
        up = store.get(up, {}).get("within") or ""
    return sorted(out)


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
            if not rec["area"] and not rec["geo"]:
                box = extent_of(k, store, root)
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
    Two entities may also share one shape (`people:chukchee` and
    `language:chukchee` both point at the one Asher polygon), so the shape
    cannot identify the member even in principle.
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
        if rec["area"]:
            out.append((kid, rec["area"]))
        else:
            out += member_shapes(kid, store, seen)
    return out


def extent_of(ent_id: str, store: dict, root: Path = Path("."),
              _seen=None) -> tuple | None:
    """What to frame a map of this entity on, in store longitudes.

    Three sources, in order: its own shape, its own point, or **the union of
    what lies beneath it**. The third is what makes the tree navigable at all —
    no source holds a polygon for Chukotka or the Russian Far East, and none
    should: they are tree structure, not shapes. A frame is a viewport and not
    a claim, which is why computing one is legal where inferring a *boundary*
    for Chukotka would not be. The view says so in as many words.

    Cycle-guarded even though `entity check` gates acyclicity, because this
    runs inside a page render where a hang is worse than a wrong answer.
    """
    rec = store.get(ent_id)
    if rec is None:
        return None
    seen = _seen or set()
    if ent_id in seen:
        return None
    seen = seen | {ent_id}

    boxes = []
    if rec["area"]:
        boxes.append(bounds(shape(rec["area"], root)))
    elif rec["geo"]:
        lat, lon = rec["geo"]
        lon = _shifted(lon, index(root))
        boxes.append((lon - POINT_BOX, lat - POINT_BOX,
                      lon + POINT_BOX, lat + POINT_BOX))
    # **Always union the children in, even when the entity has an extent of its
    # own.** Stopping at the first source found meant a parent with a `geo:`
    # point framed on that point alone, and Uelen — inside the Chukchee
    # Peninsula by the store's own `within:` — fell outside its parent's map.
    # A parent that cannot show its own children is the one thing the tree is
    # for.
    boxes += [extent_of(k, store, root, seen)
              for k in children(store).get(ent_id, [])]

    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def located(ent_id: str, store: dict, root: Path = Path(".")) -> bool:
    """Whether this entity has anywhere to put on a map, itself or below it."""
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
    """
    idx = index(root)
    kids = children(store)
    out = []

    def walk(ident: str, d: int):
        rec = store.get(ident)
        if rec is None:
            return
        if rec["geo"]:
            lat, lon = rec["geo"]
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
    claims: dict[str, list[str]] = {}
    for rec in store.values():
        if rec["area"]:
            claims.setdefault(rec["area"], []).append(rec["id"])

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
    absent = [{"what": k, "why": v} for k, v in sorted(idx["absent"].items())]
    return {
        "scope": [{"shapes": len(rows),
                   "claimed": sum(1 for r in rows if r["claimed_by"]),
                   "window": " ".join(f"{v:.1f}" for v in idx["window"]),
                   "absent": len(absent)}],
        "shapes": rows,
        "absent": absent,
    }


def verify(root: Path = Path(".")) -> dict:
    """The geometry against what a human authored. Reports; never gates.

    Three findings, and the wording of each is load-bearing:

    - **containment**, where a child and its `within:` parent both have a
      shape. Named as a *pair*: the geometry says the two authored facts
      disagree and cannot say which of them is wrong.
    - **a `geo:` point away from its own shape**, with the distance, because a
      river's point is its mouth and the mouth is on the boundary.
    - **a shape two entities claim**, which is legal — `people:chukchee` and
      `language:chukchee` may both point at the one Asher polygon, and forcing
      a choice would be this edition deciding something the source does not.
    """
    from .entities import load

    idx = index(root)
    store = load(root)
    docs: dict[str, dict] = {}

    def doc_for(ident: str) -> dict:
        if ident not in docs:
            docs[ident] = shape(ident, root)
        return docs[ident]

    containment, points, shared = [], [], []
    claims: dict[str, list[str]] = {}
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        if rec["area"]:
            claims.setdefault(rec["area"], []).append(rec["id"])

        parent = store.get(rec["within"]) if rec["within"] else None
        if rec["area"] and parent and parent["area"]:
            frac = contains(doc_for(parent["area"]), doc_for(rec["area"]))
            coarse = [i for i in (rec["area"], parent["area"])
                      if idx["shapes"].get(i, {}).get("precision") == "low"]
            containment.append({
                "child": rec["id"], "child_area": rec["area"],
                "parent": parent["id"], "parent_area": parent["area"],
                "inside": round(frac, 3),
                "coarse": " ".join(coarse),
                "reading": _reading(frac, bool(coarse)),
            })

        if rec["geo"] and rec["area"]:
            lat, lon = rec["geo"]
            d = distance_to((_shifted(lon, idx), lat), doc_for(rec["area"]))
            if d > POINT_SLACK:
                points.append({"id": rec["id"], "area": rec["area"],
                               "degrees_out": round(d, 3),
                               "reading": "outside its own shape"})

    for ident, ids in sorted(claims.items()):
        if len(ids) > 1:
            shared.append({"shape": ident, "claimed_by": " ".join(ids)})

    unclaimed = sorted(i for i, s in idx["shapes"].items()
                       if s.get("kind") != "base" and i not in claims)
    return {
        "scope": [{"pairs_checked": len(containment),
                   "disagree": sum(1 for c in containment
                                   if c["reading"] == "disagrees"),
                   "points_out": len(points),
                   "shared": len(shared),
                   "unclaimed": len(unclaimed)}],
        "containment": containment,
        "points": points,
        "shared": shared,
        "unclaimed": [{"shape": i} for i in unclaimed],
    }


#: Where a pair of high-precision delineations must land to read as contained.
#: A shared divide is a shared *line*, so a child's vertices sit on it and land
#: either side by rounding; a couple of percent is that, not a disagreement.
EXACT = 0.98
#: The floor below which even two coarse delineations are saying different
#: things. The five true river relations in the store measure 0.70-0.87 with a
#: coarse member; a `within:` row naming the wrong river measures far lower,
#: because the two basins then barely overlap at all.
COARSE_FLOOR = 0.6


def _reading(frac: float, coarse: bool) -> str:
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
    """
    if frac >= EXACT:
        return "contained"
    if coarse:
        return "consistent with a coarse delineation" if frac >= COARSE_FLOOR \
            else "disagrees"
    return "disagrees"


def _shifted(lon: float, idx: dict) -> float:
    base = idx.get("lon_base", LON_BASE)
    return lon + 360.0 if lon < base else lon
