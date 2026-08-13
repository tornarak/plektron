#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["shapely>=2.0"]
# ///
"""Compile `data/geo/` from sources that live outside the repository.

`scratch/` is gitignored and `scratch/languages.geojson` is a symlink into
`~/Downloads`, so **the compiled store has to be tracked** — a clone cannot
rebuild it. That is the same split `scans/` has: a `tools/` script builds from
something only this machine holds, and the harness reads what is committed.
`data/geo/SOURCES.md` is the provenance record and is authored by hand.

`shapely` is declared inline (PEP 723) rather than added to the project:
`edition serve` reads plain JSON and imports nothing new, so the geometry
library is a build-time cost only. Simplification is `.simplify()` rather than
a hand-rolled Douglas-Peucker, which is a one-off reimplementation of something
a library does.

THE ANTIMERIDIAN IS A BUILD PROBLEM BEFORE IT IS A RENDERING PROBLEM. Chukotka
spans 180 degrees, where a ring stepping 179.9 -> -179.9 is a self-crossing
horror in any planar library, and this one is planar. Two shapes of the hazard,
both handled by the same recipe:

  - a *regional* shape cut at the meridian into two half-polygons (RFC 7946
    says to do this), which would otherwise render as two halves at opposite
    edges of the map;
  - a *global* base layer whose Eurasia polygon runs from -10 to 190 degrees,
    which a naive "add 360 to the negatives" pass would tear in half.

So: clip in NATIVE coordinates against two boxes, one either side of the
meridian; shift the western box's result by +360; union the two. A cut shape's
halves meet at exactly 180 and the union welds them; a global polygon is
clipped before anything is shifted, so nothing tears. Everything downstream
lives in one continuous longitude window and the renderer never sees a seam.

WHAT IT REFUSES TO DO QUIETLY. A shape whose simplification produces an invalid
ring keeps its unsimplified geometry and is reported. Nothing is `.buffer(0)`'d
— buffer(0) silently changes what a shape claims, which on a watershed is a
claim about where water goes. And a shape that touches the meridian with no
counterpart on the other side is reported as clipped rather than closed up:
Asher's Chukchi polygon stops dead at 180 and East Cape is simply not in the
source, which is a fact about the source and not a defect to repair.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parent.parent
WATERSHEDS = REPO / "scratch" / "watersheds"
LANGUAGES = REPO / "scratch" / "languages.geojson"
NATURALEARTH = REPO / "scratch" / "naturalearth"
OUT = REPO / "data" / "geo"

#: The Natural Earth **10m** gazetteer layers, and the named features this
#: edition takes from them. 10m rather than the 50m used for the coastline
#: because these are *subjects* — a reader opens the page to look at Chaun Bay —
#: where the coastline is context; the size argument in `TOLERANCE` runs the
#: other way for a shape somebody is looking at.
#:
#: **Selected by a declared table, never by keyword.** The same rule `LANGAREAS`
#: obeys, and for the same reason: a search for "Chukchi" in this file returns a
#: sea, a range and a peninsula, and picking one of them is a human's act. The
#: NE name is on the left exactly as the source spells it, capitals and
#: abbreviation included, so a source that re-spells one fails loudly here
#: rather than silently matching nothing.
NE_GAZETTEER = {
    "ne_10m_geography_regions_polys.geojson": {
        "CHUKCHI PENINSULA": ("region:chukchi-peninsula", "Chukchi Peninsula"),
        "St. Lawrence I.": ("region:st-lawrence-island", "St. Lawrence Island"),
        "KAMCHATKA PENINSULA": ("region:kamchatka", "Kamchatka Peninsula"),
        "Wrangel I.": ("region:wrangel-island", "Wrangel Island"),
        "Karaginskiy I.": ("region:karagha-island", "Karaginskiy Island"),
        "Bear Is.": ("region:bear-islands", "Bear Islands"),
    },
    "ne_10m_geography_marine_polys.geojson": {
        "Chaun Bay": ("marine:chaun-bay", "Chaun Bay"),
        "Bering Sea": ("marine:bering-sea", "Bering Sea"),
        "Sea of Okhotsk": ("marine:okhotsk-sea", "Sea of Okhotsk"),
        "Gulf of Anadyr'": ("marine:anadyr-bay", "Gulf of Anadyr"),
        "Karaginskiy Gulf": ("marine:karagha-bay", "Karaginskiy Gulf"),
    },
}

#: `Smith Sound` is in the marine layer and is **not** taken: it is in Greenland,
#: outside this edition's window, and the build would report it as both "falls
#: outside the region" and "the source may have re-spelled it". Bogoras names it
#: once, comparatively, quoting Kroeber. A comparandum is not a subject.

#: **The two oceans are deliberately not taken.** `Arctic Ocean` and `North
#: Pacific Ocean` are both in the marine layer and both would build, but a
#: world-spanning polygon clipped to this edition's window is a rectangle: it
#: tells a reader nothing they did not already know from the frame, and it costs
#: the store its two largest shapes to say it. `water:arctic-ocean` and
#: `water:pacific-ocean` stay unlocated, which is the honest state — the book
#: uses both as directions rather than as places.

#: The name field differs between the two layers — the regions layer capitalizes
#: its keys, the marine layer does not — so both are tried rather than one being
#: assumed. A feature matching neither is not a candidate.
NE_NAME_KEYS = ("NAME", "name")

#: The land east of the antimeridian, cut from Natural Earth by a declared rule
#: and emitted as an ordinary `base:` shape. **It asserts nothing about speech.**
#:
#: `langarea:chuk1273` stops dead at 180 because that is where Asher drew it,
#: and `SOURCES.md` argues at length that closing it up here would be inventing
#: evidence in the one place a reader would never check. So the build does not
#: close it up. What it does instead is emit the *land* — sourced, mechanical,
#: no claim in it — and leave the join to a human, who makes it by writing
#: `area: langarea:chuk1273, base:chukotka-east-of-meridian` onto the entity
#: with `harness entity locate`. The inference then lives in the entity file
#: under a `status:` and a name, where a reader can see whose it is.
#:
#: THE SELECTION RULE, AND WHY IT IS NOT A LONGITUDE BOX. "Asia east of 180" is
#: not expressible as a window: in the shifted frame East Cape sits at 190.4,
#: St. Lawrence Island at 190 and the Seward Peninsula at 195, so any box wide
#: enough for Chukotka's tip contains Alaska. The rule is instead topological —
#: **the land component that touches the Asher polygon**, which is the Asian
#: mainland by construction — intersected with the half-plane east of 180.
#: Alaska is a different component and the islands are components of their own,
#: so neither can enter however the longitudes fall.
EAST_OF_MERIDIAN = "base:chukotka-east-of-meridian"
EAST_SEED = "langarea:chuk1273"

#: Longitudes are normalized into [LON_BASE, LON_BASE+360). 60 degrees East is
#: chosen because it is far west of anything this edition touches — the
#: westernmost source shape starts at 81E — so the wrap point never falls
#: inside a shape that survives the clip.
LON_BASE = 60.0

#: Outer bounds the computed window may not exceed. The window itself is the
#: padded union extent of every shape the store declares — **including the
#: language areas**, not the watersheds alone. Deriving it from the basins only
#: put its eastern edge at 189E and silently dropped all four American language
#: areas, one of which (`ipk`) is a Tier-1 code this edition keys: a clip
#: window computed from one layer is a window that decides what the other
#: layers may contain.
#:
#: This is a *clip* window and not a viewport. Each map computes its own frame
#: from its subject, so a generous window costs only the size of the base
#: layer, while a tight one loses data that cannot be got back without a
#: rebuild.
REGION_MAX = (60.0, 35.0, 240.0, 80.0)   # west, south, east(shifted), north

#: Simplification tolerance in degrees, per layer. A degree of latitude is
#: ~111 km, so 0.01 is ~1 km — below the width of the line a browser draws for
#: a basin at any width this edition renders at. Applied in degrees rather than
#: in projected metres: the error that matters is visual, the renderer's own
#: projection is what maps degrees to the page, and a projected tolerance would
#: have to be recomputed for every viewport.
# The base layers are simplified an order harder than the subjects. They are
# *context* — a coastline that says which way the sea is — and they are always
# drawn at whole-region scale because that is what a coastline is for; carrying
# them at subject resolution put 70 KB of Eurasia into a card showing a 2,800
# km² basin. Culling cannot help there: land is one ring spanning the store, so
# it is never wholly off-frame and is serialized in full every time.
TOLERANCE = {"watershed": 0.01, "rivers": 0.01, "langarea": 0.02, "base": 0.08}

#: Coordinate precision in the compiled file. 3 decimals is ~100 m, an order of
#: magnitude finer than the simplification above, so it costs nothing the
#: simplify has not already spent.
PRECISION = 3

#: The Asher 2007 polygons this edition draws, by glottocode — the id the
#: source itself carries, and the only stable one.
#:
#: **The Tier-1 codes are what selected them**, and four of the seven have no
#: polygon here at all: `ypk` (the book's "Asiatic Eskimo" — Siberian Yupik is
#: absent, and the Alaskan varieties below are its comparanda, not it), `xcv`
#: (Chuvan), and Tundra Yukaghir; Kerek likewise. Confirmed against the full
#: title list of every Asher feature reaching north of 50 degrees, not against
#: a keyword guess. `index.json` carries the absences as rows so the atlas can
#: say the source has no polygon rather than render a blank frame.
LANGAREAS = {
    "chuk1273": ("Chukchi", "ckt"),
    "kory1246": ("Koryak", "kpy"),
    "itel1242": ("West Itelmen", "itl"),
    "even1260": ("Even (Lamut)", "eve"),
    "even1259": ("Evenki", ""),
    "yaku1245": ("Sakha (Yakut)", ""),
    "sout2750": ("Southern Yukaghir", ""),
    "cent2127": ("Central Alaskan Yupik", ""),
    "paci1278": ("Pacific Gulf Yupik", ""),
    "nort2943": ("North Alaskan Inupiatun", "ipk"),
    "nort2945": ("Seward Alaska Inupiatun", "ipk"),
    "aleu1260": ("Aleut", ""),
}

#: What this edition looked for and no source in hand draws. Recorded so
#: `index.json` is a census rather than a list of what happened to be found:
#: an entity pointing at nothing and an entity nobody has got to yet look
#: identical from outside, and only one of them is finished.
#:
#: **The block holds two kinds of absence now, and a row says which.** It began
#: as "a Tier-1 code Asher 2007 draws no polygon for" — four of the seven — and
#: a marine feature no gazetteer carries at all is a different thing entirely:
#: the first is a statement about one atlas's coverage of languages, the second
#: about every source in hand. Read as the first, the second would say Asher
#: omitted a strait, which Asher was never asked about. So each row carries
#: `sought` (what was looked for) and `source` (where), and `why` is left to say
#: only what is particular to it.
ABSENT = {
    "ypk": {
        "sought": "Siberian Yupik speaker area",
        "source": "asher2007",
        "why": "The book's “Asiatic Eskimo”. Asher 2007 draws the Alaskan "
               "Yupik varieties and no Asian one; they are its comparanda, "
               "not substitutes for it.",
    },
    "xcv": {"sought": "Chuvan speaker area", "source": "asher2007",
            "why": "No polygon in Asher 2007."},
    "kerek": {"sought": "Kerek speaker area", "source": "asher2007",
              "why": "No polygon in Asher 2007."},
    "yukaghir-tundra": {
        "sought": "Tundra (Northern) Yukaghir speaker area",
        "source": "asher2007",
        "why": "Asher 2007 draws Southern Yukaghir only.",
    },
    "bering-strait": {
        "sought": "Bering Strait, as an area",
        "source": "naturalearth-10m marine and regions",
        "why": "Neither layer carries it: the marine gazetteer names 32 "
               "straits worldwide and not this one, and hydrographic sources "
               "generally draw a strait as a line between two capes rather "
               "than as an extent. `water:bering-strait` therefore carries a "
               "`geo:` point and no `area:`, which locates it without "
               "claiming a boundary nothing in hand draws.",
    },
}


def slug(text: str) -> str:
    """A filename-safe id from a source's own name.

    NFD like everything else here, then reduced — these are ASCII already, and
    the normalize is the corpus rule rather than a defence against anything.
    """
    text = unicodedata.normalize("NFD", text).lower()
    return "".join(c if c.isalnum() else "-" for c in text).strip("-")


# ------------------------------------------------------------ the meridian

def prepare(geom, window):
    """Clip to the region and land in one continuous longitude window.

    The order is the whole trick. Clipping happens in NATIVE coordinates
    against two boxes, so a global polygon is cut down before any arithmetic
    touches it; only the western piece is then shifted. A shape cut at the
    meridian by its own publisher arrives as two halves that meet exactly at
    180, and the union at the end welds them back into one.
    """
    w, s, e, n = window
    east = geom.intersection(box(w, s, min(e, 180.0), n))
    parts = [east] if not east.is_empty else []
    if e > 180.0:
        west = geom.intersection(box(-180.0, s, e - 360.0, n))
        if not west.is_empty:
            from shapely.affinity import translate
            parts.append(translate(west, xoff=360.0))
    if not parts:
        return None
    out = unary_union(parts) if len(parts) > 1 else parts[0]
    return None if out.is_empty else out


def polygonal(geom):
    """The polygonal parts of a geometry, or `None` if it has none.

    Clipping a polygon against a box returns a GeometryCollection wherever the
    boundary merely *grazes* the cut: the coast touches 180 at a point and
    follows it for a stretch, and shapely hands back that point and that line
    beside the areas. They are artifacts of the cut and not part of the land —
    a stray LineString in an area shape would draw as a hairline off the coast
    and count toward nothing.

    Filtering rather than `.buffer(0)`, which is this file's standing rule:
    buffer(0) would also silently repair anything genuinely broken, and a
    repair nobody was told about is the failure this store is arranged against.
    """
    parts = [g for g in getattr(geom, "geoms", [geom])
             if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty]
    if not parts:
        return None
    return unary_union(parts) if len(parts) > 1 else parts[0]


def touches_meridian(geom) -> bool:
    """True where a shape has a vertex sitting on 180 exactly.

    A vertex *on* the meridian is what a publisher's cut leaves behind. After
    `prepare` has welded any counterpart, one that still touches is a shape the
    source truncated there — Asher's Chukchi, whose eastern half does not exist
    — and the report says so rather than the map implying the coast ends.
    """
    for x, _y in coords(mapping(geom)):
        if abs(x - 180.0) < 1e-9:
            return True
    return False


def coords(geo):
    """Every (x, y) in a GeoJSON geometry mapping, whatever its nesting."""
    def walk(c):
        if c and isinstance(c[0], (int, float)):
            yield (c[0], c[1])          # a third (z) ordinate is dropped
        else:
            for part in c:
                yield from walk(part)
    yield from walk(geo["coordinates"])


def round_geo(geo, precision=PRECISION):
    def walk(c):
        if c and isinstance(c[0], (int, float)):
            return [round(c[0], precision), round(c[1], precision)]
        return [walk(part) for part in c]
    return {"type": geo["type"], "coordinates": walk(geo["coordinates"])}


def reduce(geom, tol: float, label: str, notes: list[str]):
    """Simplify, and keep the original where simplifying broke it."""
    small = geom.simplify(tol, preserve_topology=True)
    if small.is_empty:
        notes.append(f"{label}: simplification emptied it — kept unsimplified")
        return geom
    if not small.is_valid:
        notes.append(f"{label}: simplification produced an invalid ring — "
                     f"kept unsimplified (not buffer(0)'d: that would change "
                     f"what the shape claims)")
        return geom
    return small


# ------------------------------------------------------------ the sources

def read_watersheds(window, notes):
    """One basin per file: the watershed polygon, plus the top two Strahler
    orders of its river network.

    Dropping the lower orders is the ruling and is not a quality judgement —
    every order is real. It is a legibility one: the Anadyr's full network is
    589 segments in a card 20 rem wide.
    """
    out = {}
    for path in sorted(WATERSHEDS.glob("*.geojson")):
        doc = json.loads(path.read_text())
        name = doc["properties"]["name"]
        ident = f"watershed:{slug(path.stem)}"
        feats = doc["features"]
        sheds = [f for f in feats if f["properties"]["layer"] == "watershed"]
        rivers = [f for f in feats if f["properties"]["layer"] == "rivers"]
        orders = sorted({f["properties"]["sorder"] for f in rivers})
        floor = orders[-2] if len(orders) > 1 else (orders[0] if orders else 0)
        keep = [f for f in rivers if f["properties"]["sorder"] >= floor]

        shed = prepare(unary_union([shape(f["geometry"]) for f in sheds]), window)
        if shed is None:
            notes.append(f"{ident}: falls outside the region — skipped")
            continue
        shed = reduce(shed, TOLERANCE["watershed"], ident, notes)

        lines = []
        for f in keep:
            g = prepare(shape(f["geometry"]), window)
            if g is None or g.is_empty:
                continue
            lines.append((reduce(g, TOLERANCE["rivers"], ident, notes),
                          f["properties"]["sorder"]))

        area = float(str(doc["properties"].get("area_km2", "0")).replace(",", ""))
        # **The service says when it fell back**, and it matters more than
        # anything else it reports. Above 50,000 km² it reverts to a coarse DEM
        # and says so in `message`; the Indigirka fell back for a different
        # reason (its outlet is outside the high-resolution extent). Every
        # containment disagreement measured so far involves a basin flagged
        # here, so a store that dropped this line would turn "the source is
        # coarse" into "the hierarchy is wrong".
        message = doc["properties"].get("message", "")
        out[ident] = {
            "id": ident, "kind": "watershed", "name": name.replace("_", " "),
            "area_km2": area, "source": "mghydro",
            "precision": "low" if ("low-precision" in message
                                   or "high-re" in message) else "high",
            "message": message,
            "wid": doc["properties"].get("wid", ""),
            "retrieved": doc["properties"].get("retrieved", ""),
            "rivers_kept": len(lines), "rivers_total": len(rivers),
            "sorder_floor": floor,
            "_shape": shed, "_lines": lines,
        }
    return out


def read_langareas(window, notes):
    doc = json.loads(LANGUAGES.read_text())
    found = {}
    for f in doc["features"]:
        code = f["properties"].get("cldf:languageReference")
        if code not in LANGAREAS:
            continue
        title, tier1 = LANGAREAS[code]
        ident = f"langarea:{code}"
        g = prepare(shape(f["geometry"]), window)
        if g is None:
            notes.append(f"{ident}: falls outside the region — skipped")
            continue
        if touches_meridian(g):
            notes.append(f"{ident}: clipped at the antimeridian in the source, "
                         f"with no counterpart to weld — the area east of 180 "
                         f"is absent from Asher 2007, not lost here")
        found[ident] = {
            "id": ident, "kind": "langarea", "name": title,
            "family": f["properties"].get("family", ""),
            "glottocode": code, "tier1": tier1, "source": "asher2007",
            "_shape": reduce(g, TOLERANCE["langarea"], ident, notes),
            "_lines": [],
        }
    for code, (title, _t) in LANGAREAS.items():
        if f"langarea:{code}" not in found:
            notes.append(f"langarea:{code} ({title}): declared but not in the "
                         f"source — the glottocode may have moved")
    return found


def read_base(window, notes):
    """Natural Earth land and lakes, as one backdrop shape each.

    Returns the records and, beside them, the **unsimplified** prepared land —
    `east_of_meridian` cuts from that rather than from what is written out.
    Simplifying the whole northern hemisphere at 0.08 degrees and then clipping
    a 400 km sliver out of the result would give the sliver nine kilometres of
    error along a coast that is the entire subject.
    """
    out, raw_land = {}, None
    for layer, fname in (("land", "ne_50m_land.geojson"),
                         ("lakes", "ne_50m_lakes.geojson")):
        path = NATURALEARTH / fname
        if not path.exists():
            notes.append(f"base:{layer}: {path} is missing — see SOURCES.md "
                         f"for where it comes from")
            continue
        doc = json.loads(path.read_text())
        g = prepare(unary_union([shape(f["geometry"]) for f in doc["features"]]),
                    window)
        if g is None:
            continue
        if layer == "land":
            raw_land = g
        ident = f"base:{layer}"
        out[ident] = {"id": ident, "kind": "base", "name": layer,
                      "source": "naturalearth-50m",
                      "_shape": reduce(g, TOLERANCE["base"], ident, notes),
                      "_lines": []}
    return out, raw_land


def east_of_meridian(land, seed, window, notes):
    """The Asian mainland east of 180, cut from Natural Earth by the declared rule.

    `land` is the prepared, unsimplified backdrop; `seed` is the Asher Chukchi
    polygon, used only to *identify* which land component is Asia. Nothing of
    the seed's geometry survives into the result — this is Natural Earth land
    and nothing else, which is what lets it sit under `base:` and claim nothing
    about who speaks what.

    Returns `None`, with a note, wherever the rule cannot be applied: a missing
    seed, a land layer that did not build, or a component that turns out to have
    nothing east of the meridian. A silent empty shape here would be the worst
    outcome available — the map would simply stop at 180 again, and look exactly
    like the thing this was written to distinguish itself from.
    """
    if land is None or seed is None:
        notes.append(f"{EAST_OF_MERIDIAN}: needs both base:land and "
                     f"{EAST_SEED}; one of them did not build — not emitted")
        return None
    parts = list(getattr(land, "geoms", [land]))
    touching = sorted((p for p in parts if p.intersects(seed)),
                      key=lambda g: g.area, reverse=True)
    if not touching:
        notes.append(f"{EAST_OF_MERIDIAN}: no land component touches "
                     f"{EAST_SEED}, so the Asian mainland cannot be identified "
                     f"— not emitted")
        return None
    # **The largest, not the union.** The Asher polygon reaches the coast, so it
    # also touches the offshore islands inside it — Ayon, in Chaun Bay, is the
    # standing case. They are not the mainland, and unioning them in would make
    # "the Asian continent" mean "Asia and whatever it happens to abut". The
    # discarded ones are reported so the choice is visible rather than assumed;
    # a run where a second component is large is a run where the coastline broke.
    mainland, rest = touching[0], touching[1:]
    if rest:
        notes.append(
            f"{EAST_OF_MERIDIAN}: {len(rest)} smaller land component(s) also "
            f"touch {EAST_SEED} (largest {max(p.area for p in rest):.3f} deg² "
            f"against the mainland's {mainland.area:.0f}) — islands inside the "
            f"speaker area, not the continent; excluded")
    east = polygonal(mainland.intersection(
        box(180.0, window[1], window[2], window[3])))
    if east is None or east.is_empty:
        notes.append(f"{EAST_OF_MERIDIAN}: the mainland component has nothing "
                     f"east of 180 — not emitted")
        return None
    return {
        "id": EAST_OF_MERIDIAN, "kind": "base",
        "name": "Chukotka east of the antimeridian",
        "source": "naturalearth-50m",
        "rule": f"the land component intersecting {EAST_SEED}, clipped to "
                f"longitudes east of 180. Natural Earth land only — it says "
                f"nothing about who speaks what",
        "_shape": reduce(east, TOLERANCE["langarea"], EAST_OF_MERIDIAN, notes),
        "_lines": [],
    }


def read_gazetteer(window, notes):
    """The named Natural Earth 10m features this edition declares.

    Two layers, one table, and a feature is taken only if the table names it —
    `LANGAREAS`'s rule. A declared name the layer does not carry is a **note**
    rather than a silence: the source may have re-spelled it, and a table that
    quietly matched nothing would leave an entity pointing at a shape that was
    never built.
    """
    out = {}
    for fname, wanted in NE_GAZETTEER.items():
        path = NATURALEARTH / fname
        if not path.exists():
            notes.append(f"{fname} is missing — see SOURCES.md for where it "
                         f"comes from; {len(wanted)} shape(s) not built")
            continue
        doc = json.loads(path.read_text())
        seen = set()
        for f in doc["features"]:
            props = f["properties"]
            name = next((props[k] for k in NE_NAME_KEYS if props.get(k)), None)
            if name not in wanted:
                continue
            ident, title = wanted[name]
            g = prepare(shape(f["geometry"]), window)
            if g is None:
                notes.append(f"{ident}: falls outside the region — skipped")
                continue
            seen.add(name)
            kind = ident.partition(":")[0]
            out[ident] = {
                "id": ident, "kind": kind, "name": title,
                "ne_name": name, "featurecla": props.get("FEATURECLA")
                or props.get("featurecla") or "",
                "wikidata": props.get("WIKIDATAID") or props.get("wikidataid")
                or "",
                "source": "naturalearth-10m",
                "_shape": reduce(g, TOLERANCE["langarea"], ident, notes),
                "_lines": [],
            }
        for name, (ident, _t) in wanted.items():
            if name not in seen:
                notes.append(f"{ident}: {fname} has no feature named "
                             f"{name!r} — the source may have re-spelled it")
    return out


# ------------------------------------------------------------ the emitter

def collection(rec) -> dict:
    """One shape as a minimal FeatureCollection.

    The shared properties are hoisted to the collection — the source repeats
    `name`, `wid`, `area_km2` and `retrieved` on all 589 features of a basin —
    and a feature keeps only what varies across the file.
    """
    props = {k: v for k, v in rec.items()
             if not k.startswith("_") and k not in ("_shape", "_lines")}
    feats = [{"type": "Feature", "properties": {"layer": rec["kind"]},
              "geometry": round_geo(mapping(rec["_shape"]))}]
    for geom, sorder in rec["_lines"]:
        feats.append({"type": "Feature",
                      "properties": {"layer": "rivers", "sorder": sorder},
                      "geometry": round_geo(mapping(geom))})
    return {"type": "FeatureCollection", "properties": props, "features": feats}


def relpath(ident: str) -> str:
    kind, _, name = ident.partition(":")
    return f"{kind}/{name}.json"


def compute_window():
    """The clip window: every declared shape's extent, padded and clamped.

    Computed from the raw sources before anything is clipped, so the window can
    never be the reason a declared shape is missing — which is exactly what
    deriving it from the watersheds alone did.
    """
    bounds = []
    for path in sorted(WATERSHEDS.glob("*.geojson")):
        doc = json.loads(path.read_text())
        f = next(f for f in doc["features"]
                 if f["properties"]["layer"] == "watershed")
        bounds.append(extent(f["geometry"]))
    doc = json.loads(LANGUAGES.read_text())
    for f in doc["features"]:
        if f["properties"].get("cldf:languageReference") in LANGAREAS:
            bounds.append(extent(f["geometry"]))
    pad = 2.0
    return (max(REGION_MAX[0], min(b[0] for b in bounds) - pad),
            max(REGION_MAX[1], min(b[1] for b in bounds) - pad),
            min(REGION_MAX[2], max(b[2] for b in bounds) + pad),
            min(REGION_MAX[3], max(b[3] for b in bounds) + pad))


def extent(geo):
    """A geometry's bbox in the normalized longitude frame.

    **Every** longitude below `LON_BASE` is shifted, not only those in a shape
    that spans the meridian. Shifting conditionally looked right and was not:
    Alaska sits wholly west of 180 and never triggers the condition, so its raw
    −166 went into the window computation unshifted and dragged the western
    edge 100 degrees past anything real — which the outer clamp then absorbed,
    so the window looked deliberate rather than broken. The unconditional
    version is also the one that matches what the store holds.
    """
    pts = list(coords(geo))
    xs = [x if x >= LON_BASE else x + 360.0 for x, _ in pts]
    ys = [y for _, y in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit", action="store_true",
                    help="write data/geo/; without it, report and write nothing")
    a = ap.parse_args(argv)

    notes: list[str] = []

    window = compute_window()
    print(f"region  {window[0]:.1f}E {window[1]:.1f}N .. "
          f"{window[2]:.1f}E {window[3]:.1f}N  (longitudes normalized into "
          f"[{LON_BASE:.0f}, {LON_BASE + 360:.0f}); >180 is west of the "
          f"antimeridian)\n")

    shapes = {}
    base, raw_land = read_base(window, notes)
    shapes.update(base)
    shapes.update(read_watersheds(window, notes))
    langareas = read_langareas(window, notes)
    shapes.update(langareas)
    shapes.update(read_gazetteer(window, notes))
    # After the language areas, because the rule reads one of them to identify
    # which land component is Asia — and reads nothing else from it.
    seed = langareas.get(EAST_SEED, {}).get("_shape")
    east = east_of_meridian(raw_land, seed, window, notes)
    if east:
        shapes[EAST_OF_MERIDIAN] = east

    index = {"window": list(window), "lon_base": LON_BASE,
             "absent": ABSENT, "shapes": []}
    total = 0
    print(f"{'id':34} {'pts':>7} {'bytes':>8}  detail")
    for ident, rec in sorted(shapes.items()):
        doc = collection(rec)
        text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
        pts = sum(len(list(coords(f["geometry"]))) for f in doc["features"])
        total += len(text.encode())
        row = dict(doc["properties"])
        row["file"] = relpath(ident)
        row["points"] = pts
        row["bounds"] = [round(v, 3) for v in rec["_shape"].bounds]
        index["shapes"].append(row)
        detail = (f"{rec['rivers_kept']}/{rec['rivers_total']} rivers "
                  f"(sorder>={rec['sorder_floor']})" if rec["kind"] == "watershed"
                  else rec.get("family", "") or rec["name"])
        print(f"{ident:34} {pts:>7} {len(text.encode()):>8}  {detail}")
        if a.commit:
            p = OUT / relpath(ident)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text + "\n", encoding="utf-8")

    idx = json.dumps(index, indent=1, ensure_ascii=False)
    print(f"\n{len(shapes)} shapes, {total / 1024:.0f} KB "
          f"+ {len(idx.encode()) / 1024:.0f} KB index")
    if a.commit:
        (OUT / "index.json").write_text(idx + "\n", encoding="utf-8")

    if notes:
        print("\nnotes:")
        for n in notes:
            print(f"  {n}")
    print("\nwrote data/geo/" if a.commit else "\nreport only; --commit writes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
