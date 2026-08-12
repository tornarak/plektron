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

**AN `area:` MAY NAME SEVERAL SHAPES, COMMA-SEPARATED**, and the result is a
*composite* whose identity is the canonical comma-joined member list. A
composite is deliberately **not a row in the store**: it is synthesized at
lookup from members that are, so it is re-derived on every run and fails rather
than goes stale, exactly as `#gt` and `#mz` do in the TEI. `index()["shapes"]`
therefore still enumerates precisely what the build wrote — `geo list` and
`verify`'s `unclaimed` census the store and not the entity files — while
`.get()` and `in` resolve a composite all of whose members exist, and refuse one
whose members do not. Nothing downstream had to learn a second kind of identity.

**A composite exists only by being named**, so it always has at least one
claimant and is displayed under that entity's canonical name. Two entities may
name the same one, as `people:chukchi` and `language:chukchi` already share
`langarea:chuk1273`, so the label names every claimant rather than picking one.

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


#: How an `area:` names more than one shape. A comma, because the field is
#: authored by hand in a markdown list item and a comma is what a human writes
#: there. Whitespace around it is insignificant.
AREA_SEP = ","


def geodir(root: Path = Path(".")) -> Path:
    return root / GEODIR


def split_area(spec: str) -> list[str]:
    """`"langarea:a, langarea:b"` → `["langarea:a", "langarea:b"]`.

    Order as authored, duplicates and empties dropped. A single id round-trips
    unchanged, which is what keeps every existing caller honest.
    """
    out: list[str] = []
    for part in str(spec).split(AREA_SEP):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


def canonical_area(spec) -> str:
    """The lookup key for an `area:` — members sorted, comma-joined, no spaces.

    Sorted so `a, b` and `b,a` are one composite and not two. An ordering
    carries no meaning a reader could have intended, and a store where the same
    union had two spellings would report the same member shape as claimed and
    unclaimed at once.
    """
    ids = split_area(spec) if isinstance(spec, str) else list(spec)
    return AREA_SEP.join(sorted(dict.fromkeys(ids)))


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


class Shapes(dict):
    """The rows the build wrote, plus the composites an `area:` may compose.

    Iteration, `len` and `keys()` are the plain dict's — **the census is what
    the store holds**, and a union some entity happens to have authored is not a
    shape the atlas has. Only `.get()` and `in` resolve a composite, and only
    when every member is a real row; a composite naming a shape that does not
    exist is simply absent, so `entity check` still refuses it and its message
    can name the member that failed.
    """

    def __contains__(self, key) -> bool:
        return self.get(key) is not None

    def get(self, key, default=None):
        row = dict.get(self, key)
        if row is not None:
            return row
        if not isinstance(key, str) or AREA_SEP not in key:
            return default
        members = sorted(split_area(key))
        rows = [dict.get(self, m) for m in members]
        if not members or any(r is None for r in rows):
            return default
        return _composite_row(members, rows)


@lru_cache(maxsize=8)
def _index_cached(path: str, mtime: float) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"window": doc.get("window", []),
            "lon_base": doc.get("lon_base", LON_BASE),
            "absent": doc.get("absent", {}),
            "shapes": Shapes((s["id"], s) for s in doc.get("shapes", []))}


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
        return {"window": [], "lon_base": LON_BASE, "absent": {}, "shapes": Shapes()}


def shape(ident: str, root: Path = Path(".")) -> dict:
    """One shape's FeatureCollection, or `{}`.

    A composite id returns its members' features **concatenated**, not
    geometrically unioned: this module imports no geometry library on purpose,
    and every operation downstream — drawing, bounds, `in_shape` — is already
    per-polygon, so a two-polygon collection reads exactly as a MultiPolygon
    does. What the concatenation must not do is make an overlap disappear, and
    since the parity fix it does not.
    """
    row = index(root)["shapes"].get(ident)
    if not row:
        return {}
    if row.get("composite"):
        feats, props = [], []
        for m in row["members"].split():
            doc = shape(m, root)
            feats += doc.get("features", [])
            props.append(doc.get("properties", {}))
        merged = _composite_row(row["members"].split(), props or [{}])
        merged["id"] = row["id"]
        return {"type": "FeatureCollection", "properties": merged,
                "features": feats}
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

#: Half-width of the box a lone `geo:` point is given, in degrees. A point has
#: no extent, and a frame computed from one is a division by zero dressed up as
#: infinite zoom. Half a degree is roughly a day's travel here, which is about
#: the scale at which a village is worth looking at.
POINT_BOX = 0.5


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


def relatives(ent_id: str, store: dict) -> list[str]:
    """Every ancestor and descendant. **`entities.relatives`**, re-exported."""
    from .entities import relatives as _relatives
    return _relatives(ent_id, store)


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
    Two entities may also share one shape (`people:chukchi` and
    `language:chukchi` both point at the one Asher polygon), so the shape
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
    # The composites some entity has authored, listed after the store's own
    # rows and never among them: a union is a fact about `entities/` and the
    # census above is a fact about `data/geo/`.
    comp = []
    for spec, ids in sorted(composite_claims(store).items()):
        row = idx["shapes"].get(spec)
        if row:
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
    """`{shape id: [entity ids]}`, a composite `area:` counted against **each of
    its members**.

    A union is not a thing the store holds, so an entity claiming one has to
    count as a claim on the shapes it is made of — otherwise the members read as
    unclaimed *and* the union reads as a shape `data/geo/` does not contain,
    which is two wrong answers out of one right authored field.
    """
    claims: dict[str, list[str]] = {}
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        for m in split_area(rec["area"]) if rec["area"] else []:
            claims.setdefault(m, []).append(rec["id"])
    return claims


def composite_claims(store: dict) -> dict[str, list[str]]:
    """`{composite id: [entity ids]}` for every `area:` naming more than one."""
    out: dict[str, list[str]] = {}
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        if rec["area"] and len(split_area(rec["area"])) > 1:
            out.setdefault(rec["area"], []).append(rec["id"])
    return out


def verify(root: Path = Path(".")) -> dict:
    """The geometry against what a human authored. Reports; never gates.

    Findings, and the wording of each is load-bearing:

    - **containment**, where a child and its `within:` parent both have a
      shape. Named as a *pair*: the geometry says the two authored facts
      disagree and cannot say which of them is wrong.
    - **a `geo:` point away from its own shape**, with the distance, because a
      river's point is its mouth and the mouth is on the boundary.
    - **a shape two entities claim**, which is legal — `people:chukchi` and
      `language:chukchi` may both point at the one Asher polygon, and forcing
      a choice would be this edition deciding something the source does not.
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

    containment, points, shared = [], [], []
    claims = member_claims(store)
    for rec in sorted(store.values(), key=lambda r: r["id"]):
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
    open_rows = unlocated(store, root)
    return {
        "scope": [{"pairs_checked": len(containment),
                   "disagree": sum(1 for c in containment
                                   if c["reading"] == "disagrees"),
                   "points_out": len(points),
                   "shared": len(shared),
                   "unclaimed": len(unclaimed),
                   "unlocated": len(open_rows)}],
        "containment": containment,
        "points": points,
        "shared": shared,
        "unclaimed": [{"shape": i} for i in unclaimed],
        "unlocated": open_rows,
    }


def unlocated(store: dict, root: Path = Path(".")) -> list[dict]:
    """Entities inside a locatable subtree that carry neither `geo:` nor `area:`.

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
    """
    kids = children(store)
    rows = []
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        if rec["area"] or rec["geo"]:
            continue
        parent = store.get(rec["within"]) if rec["within"] else None
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
            "within": rec["within"],
            "wants": "framed by its members" if beneath else "geo: or area:",
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
