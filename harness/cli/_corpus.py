"""`harness corpus` — the whole-corpus reconciliation gates.

Two actions, and an action lands here only if it gates the corpus as a whole
rather than belonging to one store: `normalize` walks every store, `figures`
holds `gt/fig/` geometry and `data/readings.md` captions against each other.
Not a miscellaneous bin.
"""
from __future__ import annotations

from pathlib import Path

from ..normalize import convert, scan
from ._common import out


def register(sub, common):
    g = sub.add_parser("corpus", help="whole-corpus gates — encoding and spacing "
                       "conformance, and the figure-track reconciliation")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    p = add("normalize", help="NFD conformance, §2.9 spacing, and the lookalike "
            "census across every corpus store. Reports by default and exits 1 on "
            "drift; --commit writes the fixes")
    p.add_argument("--commit", action="store_true",
                   help="write the fixes. Required to touch any file — there is "
                        "no bare-form write, scoped or not")
    p.add_argument("--path", type=Path, action="append", default=None,
                   help="scope to this file or directory instead of the whole "
                        "corpus (repeatable) — for checking or converting one "
                        "just-authored file, e.g. a proposal, or a whole page "
                        "directory like review/1-052, without touching the "
                        "other 280+ corpus files")
    p.set_defaults(func=run_normalize)

    p = add("figures", help="reconcile the figure track — gt/fig/ zone geometry "
            "against data/readings.md caption text, in both directions. "
            "`missing` (a zone whose caption was never read) and `orphan` (a "
            "reading whose zone is gone) must both be empty; a total that merely "
            "matches is not coverage, which is how two absent pages once went "
            "unnoticed by cancelling against two zone-only ones")
    p.set_defaults(func=run_figures)


def run_normalize(a) -> int:
    if a.commit:
        out(a, convert(a.root, paths=a.path))
        return 0

    rep = scan(a.root, paths=a.path)
    # The census, then what a --commit would actually rewrite. Two tables,
    # because they are two witnesses and not one: `scan` classifies characters,
    # `convert` applies the transform and reports the files it changes, and they
    # are separate code paths. Folding the second into the first — or dropping it
    # as redundant — would leave the preview agreeing with itself, which is the
    # comparison-with-one-witness fault this project keeps meeting.
    out(a, rep)
    would = convert(a.root, dry_run=True, paths=a.path)
    out(a, {"would_write": len(would["changed"]),
            "files": " ".join(c["path"] for c in would["changed"]) or None})
    # NFD drift, an unlicensed mark, and §2.9 spacing drift all block: each is an
    # error with no reading to adjudicate. The lookalike census does not — it is
    # a to-key worklist needing a human ruling on what the page prints, which is
    # firewalled, same contract as validate's WORKLIST.
    return 1 if (rep["nfd_offenders"] or rep["unlicensed_marks"]
                 or rep["spacing_offenders"]) else 0


def run_figures(a) -> int:
    from ..figures import reconcile
    rep = reconcile(a.root)
    out(a, rep)
    # Exit non-zero on a real reconciliation failure, so this can gate. The
    # counts alone never decide it: 250 pages was once the expected total *and*
    # wrong in two compensating directions at the same time.
    return 1 if (rep["missing"] or rep["orphan"]) else 0
