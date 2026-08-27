"""`harness geo` — the shape store, and the geometry against what a human wrote.

Two actions, and **neither writes and neither gates**. The store is compiled by
`tools/build_geo.py` from sources outside the repository, and the one *gate* on
it — that an entity's `area:` names a shape that exists — belongs to
`entity check`, which is where every other "this identity resolves" claim
already lives.

What is here instead is measurement, and the split is the project's usual one:
resolution is a fact about names and gates; containment is a fact about
geometry and reports. `verify` cannot say which of two authored facts is wrong
when they disagree, so it names the pair and stops.
"""
from __future__ import annotations

from ..geo import boxes, listing, verify
from ..render import progress
from ._common import action, arg, group, opt, out


def register(cli):
    g = group(cli, "geo",
              "the compiled shape store in edition/geo/ — watersheds, language "
              "areas and the coastline the atlas draws — and the geometry "
              "checked against the hierarchy a human authored",
              section="Apparatus and reports")

    action(g, "list", run_list,
           help="every shape in the store, with the entity that claims it — and "
           "a composite `area:` counts as a claim on each of its members, since "
           "a union is a fact about `entities/` and this census is a fact about "
           "`edition/geo/`. The unions themselves are listed after, separately. "
           "**Also the absences**: four speaker areas this edition sought in "
           "Asher 2007 have no polygon there — Siberian Yupik, Chuvan, Kerek "
           "and Tundra Yukaghir, two of them (`ypk`, `xcv`) Tier-1 codes — "
           "and they are rows here rather than silences, "
           "because an entity pointing at nothing and an entity nobody has got "
           "to yet look identical from outside. A row says what was `sought` "
           "and in which `source`, because the block also holds a feature no "
           "gazetteer in hand carries at all, which is a different absence. "
           "Reports; never gates")

    action(g, "verify", run_verify,
           help="the geometry against the authored hierarchy. Where a child "
           "and its `within:` parent both carry an `area:`, the child's shape "
           "should lie inside the parent's — a basin delineated from a "
           "tributary's outlet is contained in its trunk's by construction, so "
           "this is a real second witness on the river chain. **It names the "
           "pair, never a culprit**: a disagreement says one of two authored "
           "facts is wrong and the geometry cannot say which. Also reports a "
           "`geo:` point sitting away from its own shape (with the distance — "
           "a river's point is its mouth, which is *on* the basin boundary, so "
           "this is not a defect by itself), a shape two entities claim (legal: "
           "a people and a subgroup inside it may share the one Asher "
           "polygon), and shapes nothing claims. **And the inverse of that "
           "last one** — entities inside a subtree the atlas can draw that "
           "carry neither `geo:` nor `area:`, which is the worklist a human "
           "supplying coordinates actually wants; `entity locate` answers a "
           "row of it. Scoped by the tree rather than by class, because every "
           "person and source in the store is unlocated and always will be. "
           "Reports; never gates")


    p = action(g, "bounds", run_bounds,
               help="the bounding box of one or more regions, and their union "
               "— **the measurement a `frame:` is written from**, which was "
               "otherwise a `python -c` around `geo.extent_of`. Takes entity "
               "ids and shape ids in one list, told apart by their prefix: "
               "that is decidable only because a shape kind may never be an "
               "entity class, so it needs no flag and can make no wrong guess. "
               "An entity's box is its shape, else its point, else the union of "
               "everything beneath it — the same three sources the atlas frames "
               "on — and a shape's is the polygon's own. Longitudes are the "
               "store's shifted window, the one `--frame` also takes, so the "
               "printed `frame` field pastes straight into `entity locate`. "
               "Reports; never writes"
               "\n\nID: `class:slug` or `kind:slug`, e.g. `place:kamchatka` or "
               "`watershed:anadyr`. Several are unioned")
    arg(p, "idents", metavar="ID", nargs=-1, required=True)
    opt(p, "--margin", type=float, default=0.0, metavar="DEG",
        help="degrees added on all four sides of the union. **Content, not "
             "breathing room** — `geomap.Frame` already pads a drawn map on "
             "every side, so this is the different question of how much more "
             "of the world to show. Degrees rather than a percentage, because "
             "a percentage of a box 60° wide and 20° tall is two distances and "
             "the caller would have to know which")


def run_bounds(a) -> int:
    r = boxes(a.idents, a.root, margin=a.margin)
    out(a, r["rows"], name="bounds")
    out(a, r["union"], name="union", heading=True)
    return 0


def run_list(a) -> int:
    r = listing(a.root)
    out(a, r["scope"], name="scope")
    out(a, r["shapes"], name="shapes", heading=True)
    out(a, r["composites"], name="composites", heading=True)
    out(a, r["absent"], name="absent", heading=True)
    return 0


def run_verify(a) -> int:
    with progress("verifying shapes") as tick:
        r = verify(a.root, tick=tick)
    out(a, r["scope"], name="scope")
    # First, because it is the only section that needs no shape: it speaks about
    # every `within:` in the store, where containment can only speak about the
    # dozen pairs both of whose members somebody drew.
    out(a, r["nesting"], name="nesting", heading=True)
    out(a, r["meridian"], name="meridian", heading=True)
    out(a, r["containment"], name="containment", heading=True)
    out(a, r["shared"], name="shared", heading=True)
    out(a, r["unclaimed"], name="unclaimed", heading=True)
    out(a, r["unlocated"], name="unlocated", heading=True)
    return 0
