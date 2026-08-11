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

from ..geo import listing, verify
from ._common import action, group, out


def register(cli):
    g = group(cli, "geo",
              "the compiled shape store in data/geo/ — watersheds, language "
              "areas and the coastline the atlas draws — and the geometry "
              "checked against the hierarchy a human authored",
              section="Apparatus and reports")

    action(g, "list", run_list,
           help="every shape in the store, with the entity that claims it. "
           "**Also the absences**: four of this edition's seven Tier-1 codes "
           "have no polygon in Asher 2007 — Siberian Yupik, Chuvan, Kerek and "
           "Tundra Yukaghir — and they are rows here rather than silences, "
           "because an entity pointing at nothing and an entity nobody has got "
           "to yet look identical from outside. Reports; never gates")

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
           "`people:chukchee` and `language:chukchee` may share the one Asher "
           "polygon), and shapes nothing claims. Reports; never gates")


def run_list(a) -> int:
    r = listing(a.root)
    out(a, r["scope"], name="scope")
    out(a, r["shapes"], name="shapes", heading=True)
    out(a, r["absent"], name="absent", heading=True)
    return 0


def run_verify(a) -> int:
    r = verify(a.root)
    out(a, r["scope"], name="scope")
    out(a, r["containment"], name="containment", heading=True)
    out(a, r["points"], name="points", heading=True)
    out(a, r["shared"], name="shared", heading=True)
    out(a, r["unclaimed"], name="unclaimed", heading=True)
    return 0
