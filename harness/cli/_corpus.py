"""`harness corpus` — the whole-corpus gates, and the census across every store.

An action lands here only if its subject is the corpus as a whole rather than one
store: `normalize` walks every store, `figures` holds `gt/fig/` geometry and
`data/readings.md` captions against each other, `state` reports where each page
has got to across all of them. Not a miscellaneous bin.

`state` is the one that does not gate, and it belongs here for the same reason
the other two do — no single store can answer it. Every store's own verb already
reports its own presence honestly and is blind to the rest, which is precisely
what left "which pages are ready to collate" with no command behind it.
"""
from __future__ import annotations

from pathlib import Path

from ..normalize import convert, scan
from ..pipeline import STAGES
from ._common import (
    action,
    add_all,
    arg,
    group,
    opt,
    out,
    page_refs,
    refs_arg,
    verdict,
)


def register(cli):
    g = group(cli, "corpus", "whole-corpus gates — encoding and spacing "
              "conformance, and the figure-track reconciliation",
              section="Whole-corpus")

    p = action(g, "normalize", run_normalize,
               help="NFD conformance, §2.9 spacing, and the lookalike "
               "census across every corpus store. Reports by default and exits 1 on "
               "drift; --commit writes the fixes")
    # **A mixed positional list: a `PP-NNN` ref, or a path.** A ref's shape is
    # closed (`context.parse_ref`), so the two never collide, and a required file
    # argument spelled as a flag was the smell that prompted the whole plural
    # pass. Naming a page scopes to that page's files across the corpus globs —
    # its ALTO, its decision, and its proposal.
    arg(p, "target", metavar="REF|PATH", nargs=-1, required=False)
    p.help += ("\n\nREF|PATH: a page ref (PP-NNN), scoping to that page's files, "
               "or a file or directory path. Several may be given, and they may "
               "be mixed: `1-052 data/readings.md` scopes to both. For checking "
               "or converting one just-authored file without touching the "
               "other 280+.")
    add_all(p, "every file the corpus globs reach")
    opt(p, "--commit", is_flag=True,
        help="write the fixes. Required to touch any file — there is "
             "no bare-form write, scoped or not")

    p = action(g, "state", run_state,
               help="where each page has got to, across every store at once — "
               "scanned, zoned (mz/gt), OCR'd (mz/gt), proposed, decided, "
               "collated. `stage` is the furthest rung reached and `skipped` the "
               "rungs below it that are not, so a page that took a route the "
               "pipeline no longer offers is visible rather than summarised away")
    refs_arg(p, all_="every scan in scans/, whether or not any store holds it")
    opt(p, "--context", metavar="SPEC",
        help="also report the pages around the ones named, by scan index within "
             "the same part: N each way, +N ahead, -N behind, -N+M both. Counts "
             "are inclusive and neighbours come from scans/, so a gap in the "
             "sequence is stepped over and a window never runs past a part's "
             "end or across into the next one. Ignored with --all, which is "
             "already every page")
    opt(p, "--stage", "stage", multiple=True, metavar="NAME",
        help="only pages at this rung (repeatable). One of: absent, "
             + ", ".join(STAGES))
    opt(p, "--skipped", is_flag=True,
        help="only pages that missed a rung below the one they reached")
    opt(p, "--tally", is_flag=True,
        help="counts per rung instead of the rows. Every rung is listed, "
             "including the empty ones — a rung nothing has reached and one "
             "everything has passed are different facts")
    opt(p, "--refs", is_flag=True,
        help="the bare ref list instead of the rows, in scan order — a "
             "worklist to hand a dispatch loop. Refused with --tally, which "
             "reports no refs to list")
    opt(p, "--limit", type=int, default=None, metavar="N",
        help="report at most N rows, taken from the front of the scan order. "
             "The truncation is the caller's, named at the call site, so it is "
             "not the silent kind. Refused with --tally, where a truncated "
             "census would be a false one")

    action(g, "figures", run_figures,
           help="reconcile the figure track — gt/fig/ zone geometry "
           "against data/readings.md caption text, in both directions. "
           "`missing` (a zone whose caption was never read) and `orphan` (a "
           "reading whose zone is gone) must both be empty; a total that merely "
           "matches is not coverage, which is how two absent pages once went "
           "unnoticed by cancelling against two zone-only ones")


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
                  for d in ("ocr", "fig")]
        paths += [a.root / "tei" / f"chukchi-{ref}.xml",
                  a.root / "review" / ref / "decision.json",
                  a.root / "review" / ref / "proposal.json"]
    return paths


def run_state(a) -> int:
    """The census. Never gates — it reports where pages are, not whether they pass.

    `--all` enumerates **`scans/`** and not any store, which is the one choice
    here worth stating: a page no store holds is the most interesting row this
    verb has, and enumerating a store would have hidden exactly those. It is also
    why `absent` is a stage rather than an omission.

    **`--refs` and `--limit` are the worklist pair**, and both are refused with
    `--tally` rather than quietly ignored: a tally has no refs to list, and a
    count taken over a truncated row set is a census that is simply wrong while
    looking exactly like one that is right. `--limit` truncating is not the
    silent truncation this project forbids — the caller named the number, so the
    bound is at the call site, which is where every other cost here sits.
    """
    from ..context import all_scans, with_context
    from ..pipeline import survey, tally

    refs = page_refs(a)
    # `--all` is already every page, so a window over it is a no-op rather than an
    # error: the flags answer different questions and neither contradicts the other.
    if refs and getattr(a, "context", None):
        refs = with_context(refs, a.context, a.root)
    rows = survey(refs or all_scans(a.root), a.root)
    if a.stage:
        allowed = set(a.stage)
        unknown = allowed - {"absent", *STAGES}
        if unknown:
            raise ValueError(f"--stage {sorted(unknown)}: not a rung. "
                             f"One of: absent, {', '.join(STAGES)}")
        rows = [r for r in rows if r["stage"] in allowed]
    if a.skipped:
        rows = [r for r in rows if r["skipped"]]
    if a.tally and (a.refs or a.limit is not None):
        raise ValueError("--tally with --refs or --limit: a tally lists no refs, "
                         "and a count over a truncated row set is a false census")
    if a.limit is not None:
        if a.limit < 1:
            raise ValueError(f"--limit {a.limit}: a row count, so at least 1")
        rows = rows[:a.limit]
    if a.tally:
        out(a, tally(rows))
    elif a.refs:
        out(a, [r["ref"] for r in rows])
    else:
        out(a, rows)
    return 0


def run_normalize(a) -> int:
    paths = _targets(a)
    if a.commit:
        rep = convert(a.root, paths=paths)
        out(a, rep)
        n = len(rep["changed"])
        return verdict(a, 0, f"wrote {n} file(s)" if n else "nothing to write")

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
            "files": " ".join(c["path"] for c in would["changed"]) or None},
        "would_convert")
    # NFD drift, an unlicensed mark, and §2.9 spacing drift all block: each is an
    # error with no reading to adjudicate. The lookalike census does not — it is
    # a to-key worklist needing a human ruling on what the page prints, which is
    # firewalled, same contract as validate's WORKLIST.
    blocking = (rep["nfd_offenders"] or rep["unlicensed_marks"]
                or rep["spacing_offenders"])
    if blocking:
        means = ("NFD drift, an unlicensed mark or §2.9 spacing — each an error "
                 "with no reading to adjudicate. --commit rewrites what it can")
    elif would["changed"]:
        means = (f"no blocking drift; --commit would rewrite "
                 f"{len(would['changed'])} file(s)")
    else:
        means = "clean — nothing to fix, nothing to write"
    return verdict(a, 1 if blocking else 0, means)


def run_figures(a) -> int:
    from ..figures import reconcile
    rep = reconcile(a.root)
    out(a, rep)
    # Exit non-zero on a real reconciliation failure, so this can gate. The
    # counts alone never decide it: 250 pages was once the expected total *and*
    # wrong in two compensating directions at the same time.
    return 1 if (rep["missing"] or rep["orphan"]) else 0
