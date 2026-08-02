"""`harness corpus` — the whole-corpus reconciliation gates.

Two actions, and an action lands here only if it gates the corpus as a whole
rather than belonging to one store: `normalize` walks every store, `figures`
holds `gt/fig/` geometry and `data/readings.md` captions against each other.
Not a miscellaneous bin.
"""
from __future__ import annotations

from pathlib import Path

from ..normalize import convert, scan
from ._common import add_all, out


def register(sub, common):
    g = sub.add_parser("corpus", help="whole-corpus gates — encoding and spacing "
                       "conformance, and the figure-track reconciliation")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    p = add("normalize", help="NFD conformance, §2.9 spacing, and the lookalike "
            "census across every corpus store. Reports by default and exits 1 on "
            "drift; --commit writes the fixes")
    # **A mixed positional list: a `PP-NNN` ref, or a path.** A ref's shape is
    # closed (`context.parse_ref`), so the two never collide, and a required file
    # argument spelled as a flag was the smell that prompted the whole plural
    # pass. Naming a page scopes to that page's files across the corpus globs —
    # its ALTO, its decision, and its proposal.
    p.add_argument("target", metavar="REF|PATH", nargs="*",
                   help="a page ref (PP-NNN), scoping to that page's files, or a "
                        "file or directory path. Several may be given, and they "
                        "may be mixed: `1-052 data/readings.md` scopes to both. "
                        "For checking or converting one just-authored file "
                        "without touching the other 280+")
    add_all(p, "every file the corpus globs reach")
    p.add_argument("--commit", action="store_true",
                   help="write the fixes. Required to touch any file — there is "
                        "no bare-form write, scoped or not")
    p.set_defaults(func=run_normalize)

    p = add("figures", help="reconcile the figure track — gt/fig/ zone geometry "
            "against data/readings.md caption text, in both directions. "
            "`missing` (a zone whose caption was never read) and `orphan` (a "
            "reading whose zone is gone) must both be empty; a total that merely "
            "matches is not coverage, which is how two absent pages once went "
            "unnoticed by cancelling against two zone-only ones")
    p.set_defaults(func=run_figures)


def _targets(a) -> list[Path] | None:
    """The scope: `None` for the whole corpus, else the paths the targets name.

    A token matching `PP-NNN` expands to that page's files; anything else is a
    path. **A relative path is taken against `--root`, not the cwd**, which is a
    change from the `--path` flag it replaces and the only coherent reading of a
    mixed list: a ref means "this page of this corpus" and is root-relative by
    construction, so having `1-052` and `data/readings.md` resolve against
    different bases in one argument list would be a trap. The two agree wherever
    `--root` is left at its default, which is everywhere outside the tests.

    **A named ref covers its own `proposal.json`**, which
    the corpus sweep deliberately does not (`normalize.PATH_ONLY_GLOBS`): naming
    a page is the same explicit act `--path review/PP-NNN/proposal.json` was, so
    the mid-pass protection that exists for a proposal being authored survives,
    and a finished page's dead apostrophe hits still stay out of the gate.
    """
    from ..context import norm_ref, parse_ref

    # The same two rules `page_refs` holds for a ref positional, written out here
    # because the targets are not all refs: exactly one way of saying what to work
    # on, and never nothing. A bare `corpus normalize` used to walk the corpus,
    # which is the sweep-by-omission this pass removed everywhere else.
    if a.target and a.all:
        raise ValueError("targets and --all: name one or the other, not both")
    if not a.target and not a.all:
        raise ValueError("nothing named: give one or more PP-NNN refs or paths, "
                         "or --all for every file the corpus globs reach")
    if not a.target:
        return None
    paths: list[Path] = []
    for t in a.target:
        try:
            parse_ref(t)
        except ValueError:
            p = Path(t)
            paths.append(p if p.is_absolute() else a.root / p)
            continue
        ref = norm_ref(t)
        paths += [a.root / "gt" / d / f"chukchi-{ref}.xml"
                  for d in ("ocr", "seg", "fig")]
        paths += [a.root / "tei" / f"chukchi-{ref}.xml",
                  a.root / "review" / ref / "decision.json",
                  a.root / "review" / ref / "proposal.json"]
    return paths


def run_normalize(a) -> int:
    paths = _targets(a)
    if a.commit:
        out(a, convert(a.root, paths=paths))
        return 0

    rep = scan(a.root, paths=paths)
    # The census, then what a --commit would actually rewrite. Two tables,
    # because they are two witnesses and not one: `scan` classifies characters,
    # `convert` applies the transform and reports the files it changes, and they
    # are separate code paths. Folding the second into the first — or dropping it
    # as redundant — would leave the preview agreeing with itself, which is the
    # comparison-with-one-witness fault this project keeps meeting.
    out(a, rep)
    would = convert(a.root, dry_run=True, paths=paths)
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
