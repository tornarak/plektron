"""`harness views` — the derived trees git does not carry.

An action lands here only if it is about a **whole derived tree** rather than about
the pages inside one: `check` reports every farm's state, `build` rebuilds them.

**This is the only spelling.** `ocr link` and `zones link` used to say the same
thing from inside those groups, calling the same functions this group calls with
the same argument — kept for a while as the natural phrasing while working
there, and retired as duplicate surface. `views build ocr` names the farm, so a
single view can still be relinked without the corpus-wide sweep.

The group is named for what most of its members are, and the exception is worth
knowing: `scans/w-figs-blotted/` is painted pixels, not a view over stores. What all
seven share is the property that decides this group's membership — derived,
gitignored, and absent on a fresh clone.
"""
from __future__ import annotations

import click

from .. import farms as F
from ..render import progress
from ._common import action, add_all, add_jobs, arg, group, out


def register(cli):
    g = group(cli, "views", "the derived trees git does not carry — the "
              "read views over the paired stores, the scan farms, and "
              "the segmenter's blotted rasters: what state each is in, "
              "and one command to rebuild them",
              section="Whole-corpus")

    p = action(g, "check", run_check,
               help="one row per named derived tree: whether it exists, "
               "whether its membership still matches the stores that decide it, "
               "and how deep that comparison went. Exits 1 on anything absent or "
               "stale — the defect is mechanical and the fix is one command")
    _farm_arg(p, F.NAMES)

    p = action(g, "build", run_build,
               help="rebuild the named derived trees. Writes on invocation "
               "like every other derived output, since there the write is the "
               "action; a farm whose source tree is absent is skipped with a row "
               "rather than attempted")
    _farm_arg(p, F.BUILDABLE)
    # The raster farms here are pooled already — `workers(None)` is `min(cores, 8)`
    # — so this adds the **control arm** rather than the concurrency: `--jobs 1`
    # is the serial run a pooled one has to be diffable against.
    add_jobs(p)


def _farm_arg(p, pool):
    """The farm selector, identical on both actions.

    A **positional**, and `--only` is why: that flag already means "line indices"
    throughout `ocr` (`ocr zoom --only 7,20`), and the harness holds to one meaning
    per flag name. A second `--only` selecting farms would have been the first
    place that rule broke, in the group whose whole subject is telling two similar
    things apart.

    "Everything" is `--all` and must be *said*, never implied by a bare
    invocation, and it is required on both actions for one reason each. On `build`
    it is cost: repainting the blot tree is 252 page composites, and nothing about
    a bare `views build` says so. On `check` it is symmetry — a selector that meant
    "everything" on one action and had to be spelled on the other is a difference
    a caller has to remember, and the two actions are otherwise typed one after
    the other.

    That argument is unchanged; only its spelling is. `all` used to be a *choice*
    of the positional, which made this the one place in the CLI where "everything"
    was not `--all`.
    """
    arg(p, "farm", nargs=-1, required=False, metavar="FARM",
        type=click.Choice(pool))
    p.help = (f"{p.help}\n\nFARM: which trees, space-separated. "
              f"One or more of: {', '.join(pool)}.")
    add_all(p, "every farm this action handles")


def _farms(a) -> list[str]:
    """The farms named, or every one under `--all`. The same two rules every ref
    positional keeps: one way of saying what to work on, and never nothing."""
    if a.farm and a.all:
        raise ValueError("farms and --all: name one or the other, not both")
    if not a.farm and not a.all:
        raise ValueError("nothing named: give one or more farms, or --all")
    return a.farm or [F.ALL]


def run_check(a) -> int:
    wanted = F.select(_farms(a))
    with progress("surveying farms") as tick:
        rows = [r for r in F.survey(a.root, tick) if r["farm"] in wanted]
    out(a, rows)
    # A gate, not measurement — but **only over the farms `build` can actually
    # fix**. `scans/` and `train/bogoras-seg/data/` are reported and never built here,
    # so gating on them would fail a fresh clone for lacking rasters that
    # `views build` has no way to produce: an exit code demanding a fix that the
    # named command does not perform, which teaches the reader to ignore it. Their
    # rows still print their state, and the `builder` column still says what would
    # make them — the report keeps the information, the gate keeps its meaning.
    #
    # `?` is not a failure either. It says no verdict was available, which is a
    # report about the check's reach rather than about the tree.
    return 1 if any(r["state"] in ("absent", "stale")
                    for r in rows if r["farm"] in F.BUILDABLE) else 0


def run_build(a) -> int:
    # One bar per farm, not one across all of them: each has its own denominator
    # and they run in registry order, so a single bar would be counting two
    # different things under one total.
    rows = []
    for n in F.select(_farms(a), buildable_only=True):
        with progress(f"building {n}") as tick:
            rows.append(F.build(n, a.root, a.jobs, tick))
    out(a, rows)
    # Always 0. On a machine with no `scans/`, building what can be built *is* the
    # success case; `views check` remains the verb that says what is still missing.
    return 0
