"""`harness views` — the derived trees git does not carry.

An action lands here only if it is about a **whole derived tree** rather than about
the pages inside one: `check` reports every farm's state, `build` rebuilds them. The
per-domain spellings stay — `ocr link` and `zones link` are the natural way to say
"relink that view" while working in those groups, and both call the same functions
this group does. Two spellings, one implementation.

The group is named for what most of its members are, and the exception is worth
knowing: `scans/w-figs-blotted/` is painted pixels, not a view over stores. What all
seven share is the property that decides this group's membership — derived,
gitignored, and absent on a fresh clone.
"""
from __future__ import annotations

from ._common import out
from .. import farms as F


def register(sub, common):
    g = sub.add_parser("views", help="the derived trees git does not carry — the "
                       "read views over the paired stores, the scan farms, and "
                       "the segmenter's blotted rasters: what state each is in, "
                       "and one command to rebuild them")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    p = add("check", help="one row per derived tree: whether it exists, whether "
            "its membership still matches the stores that decide it, and how "
            "deep that comparison went. Exits 1 on anything absent or stale — "
            "the defect is mechanical and the fix is one command")
    p.set_defaults(func=run_check)

    p = add("build", help="rebuild the derived trees. Writes on invocation like "
            "every other derived output, since there the write is the action; a "
            "farm whose source tree is absent is skipped with a row rather than "
            "attempted")
    p.add_argument("--only", action="append", choices=F.BUILDABLE, default=None,
                   metavar="FARM",
                   help=f"rebuild just this one (repeatable). "
                        f"One of: {', '.join(F.BUILDABLE)}")
    p.set_defaults(func=run_build)


def run_check(a) -> int:
    rows = F.survey(a.root)
    out(a, rows)
    # A gate, not measurement — but **only over the farms `build` can actually
    # fix**. `scans/` and `train/bogoras-seg/` are reported and never built here,
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
    names = a.only or list(F.BUILDABLE)
    out(a, [F.build(n, a.root) for n in names])
    # Always 0. On a machine with no `scans/`, building what can be built *is* the
    # success case; `views check` remains the verb that says what is still missing.
    return 0
