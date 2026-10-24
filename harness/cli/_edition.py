"""`harness edition` — the reading view over collated TEI and the encyclopedia.

Its own group rather than an action under `tei` or `entity`, because it is over
neither one: the page, the entities it links, and the raster it was read from are
three stores, and the whole point of the view is that they are in one place.
"""
from __future__ import annotations

import sys

from .. import edition_ui
from ..render import progress
from ._common import (
    JOBS_HELP_CRAWL,
    action,
    add_jobs,
    arg,
    group,
    opt,
    out,
    page_refs,
    refs_arg,
)


def register(cli):
    g = group(cli, "edition",
              "the reading view: collated TEI in two columns with a stack of "
              "entity, note and scan cards beside it, plus the encyclopedia and "
              "its audit queue",
              # "Whole-corpus" and not "The passes": this is not a pass over
              # pages but a view over everything at once — the index, the search
              # and the encyclopedia all span the corpus, and a page is reached
              # through them rather than the other way round.
              section="Whole-corpus")

    p = action(g, "serve", run_serve, pageable=False,
               help="open the reading view in a browser. Shows committed `tei/` "
               "only unless `--drafts` says otherwise — a generated baseline is "
               "a draft nobody has read, and an end-user preview is the last "
               "place it belongs. Ratifying an "
               "entry here writes `edition/entities/` without `--commit`, as the other "
               "editors write their stores: the click is the human act, the "
               "store is tracked, and git is the witness. Every write is "
               "refused if `entity check` would fail on the result. Blocks "
               "until the page or ctrl-c stops it")
    opt(p, "--port", type=int, default=edition_ui.PORT, metavar="N",
        help=f"the port to bind on 127.0.0.1 [{edition_ui.PORT}]")
    opt(p, "--no-open", is_flag=True,
        help="do not open a browser; print the URL and wait. For a headless "
             "run, and for the tests")
    opt(p, "--drafts", is_flag=True,
        help="also show `mz/tei/` — the pages `tei generate` built and nobody "
             "has read. Every one is marked as a draft, in the listing, on the "
             "page and in search results. Read-only: this is a window onto the "
             "generator's output while it is being fixed, not a way to collate")


    p = action(g, "build", run_build,
               help="write the reading view to OUT as a static site — every "
               "page a reader can reach from the index, the bare fragments the "
               "stack and the previews fetch, the scans, crops and speech they "
               "load, and a stub that forwards for every redirect. Rendered by "
               "the same routes `edition serve` mounts, so the site is the "
               "served output and not a second rendering of it. Search and the "
               "ratify button are left out: a host serves files. OUT is "
               "cleared first. Exit 1 on a link that answers with no page, two "
               "addresses landing on one file, or a store entry nothing links "
               "to")
    arg(p, "out", metavar="OUT")
    opt(p, "--base", default="/", metavar="PATH",
        help="the path the site will be served under, which every link "
             "names [/]")
    opt(p, "--drafts", is_flag=True,
        help="also publish `mz/tei/`, marked as drafts as `edition serve "
             "--drafts` marks them")
    add_jobs(p, processes=True, help=JOBS_HELP_CRAWL)

    p = action(g, "runs", run_runs, pageable=False,
               help="the page-runs the reading view serves as one document "
               "instead of a leaf at a time — the printed Contents, List of "
               "Illustrations and Authorities Quoted, and each chapter, its span "
               "derived from the milestones — plus a census of what "
               "every leaf outside the transcription tracks was ruled, and "
               "everything wrong with the declarations. Reads and writes "
               "nothing; exit 1 on a declaration that cannot be true, which is a "
               "run over a leaf not ruled `apparatus`, a leaf ruled `apparatus` "
               "that no run names, a span its own store contradicts, a kind "
               "with no renderer, two pages claiming one folio at one rank, or "
               "an editor's leaf that is a different leaf. A folio two witnesses "
               "of *different* rank disagree on is reported, not fatal: rank "
               "resolves it, and the disagreement is usually a misread running "
               "title worth seeing")


    p = action(g, "figrefs", run_figrefs,
               help="every cross-reference the pages print at a picture — "
               "`(Plate XXVII, Fig. 3)`, `Fig. 87 represents a knife` — and what "
               "became of each: the crop it points at, or which of the three "
               "things stopped it. **The states are not equally interesting.** "
               "`a store declined` is the figure track's worklist — a plate "
               "`gt/fig/` has not boxed yet — and clears as the keying "
               "proceeds. The other two are the guards working: `another "
               "author's` is a plate of Nelson's or Schrenck's that "
               "`Authorities Quoted` named, and `outside the book's numbers` is "
               "a number the printed List of Illustrations does not carry, this "
               "book stopping at Plate XXXV and Fig. 302. "
               "**A refusal is the safe outcome and a link is the one to "
               "doubt**: a reference pointed at the wrong picture reads as "
               "correct, which is why this exists — seven of them were servable "
               "until a sweep counted them. Goes through the same join the "
               "reading view serves, so it cannot report one thing and show "
               "another. Reads and writes nothing; reports, never gates")
    refs_arg(p, all_="every page the reading view can show, collated and draft "
             "alike")
    opt(p, "--refused", is_flag=True,
        help="only the marks that do not link. The counts are over everything "
             "either way, so a filtered listing still says what it is a part of")
    opt(p, "--limit", type=int, default=0, metavar="N",
        help="stop the listing after N rows; the counts are unaffected [all]")


def run_build(a) -> int:
    from pathlib import Path

    from ..web.build import build

    with progress("building") as tick:
        site = build(a.root, Path(a.out), base=a.base, drafts=a.drafts,
                     jobs=a.jobs, tick=tick)
    sections: dict[str, int] = {}
    for rel in site.files.values():
        top = rel.split("/")[0] if "/" in rel else "/"
        if top == "partial":
            top = "/".join(rel.split("/")[:2])
        sections[top] = sections.get(top, 0) + 1
    out(a, [{"section": k, "files": n} for k, n in sorted(sections.items())],
        name="written")
    if site.rows:
        out(a, [{"url": r["url"], "why": r["why"], "from": " ".join(r["from"])}
                for r in site.rows], name="refused", heading=True)
    # stderr, so `--json` stays one document.
    print(f"{len(site.files)} file(s) written to {a.out} under "
          f"{site.base or '/'}, {len(site.rows)} refused", file=sys.stderr)
    if site.worker_log.get("stderr_lines"):
        print(f"the workers wrote {site.worker_log['stderr_lines']} line(s) to "
              f"stderr: {site.worker_log['stderr_log']}", file=sys.stderr)
    return 1 if site.rows else 0


def run_figrefs(a) -> int:
    from ..web import stores
    from ..web.edition import figref_census

    refs = page_refs(a) or stores.in_reading_order(a.root, True)
    with progress("censusing") as tick:
        rep = figref_census(a.root, refs, tick=tick)
    rows = rep["rows"]
    shown = [r for r in rows if not a.refused or r["state"] != "link"]
    if a.limit > 0:
        shown = shown[:a.limit]
    if shown:
        out(a, shown, name="figrefs")
    # **The counts are over every mark, not over what was listed.** A `--refused`
    # listing is a worklist and a worklist that reported its own length as the
    # census would say the corpus is nothing but its defects.
    out(a, rep["counts"], name="counts", heading=True)
    print(f"{len(rows)} mark(s) on {rep['pages']} page(s)"
          + (f", {len(shown)} shown" if len(shown) != len(rows) else ""))
    return 0


def run_runs(a) -> int:
    from .. import apparatus

    rep = apparatus.check(a.root)
    out(a, rep["runs"], name="runs")
    # The census first, because it is the frame the rest is read in: a run is a
    # span of `apparatus` leaves, and how many leaves of each kind exist is what
    # says whether the runs cover what they should. Measurement, never a gate.
    out(a, rep["leaf_kinds"], name="leaf_kinds", heading=True)
    if rep["leaves"]:
        out(a, rep["leaves"], name="leaves", heading=True)
    if rep["editor_leaves"]:
        out(a, rep["editor_leaves"], name="editor_leaves", heading=True)
    if rep["warnings"]:
        out(a, rep["warnings"], name="warnings", heading=True)
    if rep["errors"]:
        out(a, rep["errors"], name="errors", heading=True)
    # The folio count is the one number that says how much of the book the
    # locator can reach at all, and it belongs with the runs rather than in a
    # separate verb: every folio link a run renders goes through it.
    leaves = sum(r["leaves"] for r in rep["leaf_kinds"])
    print(f"{len(rep['runs'])} run(s), {leaves} leaf/leaves ruled, "
          f"{rep['folios']} folio(s) witnessed, "
          f"{len(rep['errors'])} error(s), {len(rep['warnings'])} warning(s)")
    return 1 if rep["errors"] else 0


def run_serve(a) -> int:
    from .. import speech, tei_html
    from ..entities import load
    from ..web import Sessions
    from ..web import serve as web

    # The four tools share a process, so if one is already up this hands it the
    # session and opens a tab rather than failing on a held port.
    joined = web.handoff("edition", {}, port=a.port)
    if joined:
        print(f"edition -> {joined}   (joined the running server)")
        if not a.no_open:
            import webbrowser

            webbrowser.open(joined)
        return 0

    n_collated = len(tei_html.collated(a.root))
    counts = f"  {n_collated} page(s) collated"
    if a.drafts:
        # Named separately rather than summed: the banner is the one place the
        # operator learns what this sitting is showing, and one total would hide
        # that almost all of it is unread.
        counts += (f", {len(tei_html.readable(a.root)) - n_collated} machine "
                   f"draft(s) shown (--drafts)")
    banner = [f"edition: {web.url_for('edition', port=a.port)}",
              f"{counts}, {len(load(a.root))} entities",
              # Probed once at startup, so a host without espeak-ng says so here
              # rather than the first time someone presses a speaker.
              f"  speech: {speech.probe()}",
              "  ctrl-c to stop"]
    web.serve("edition", a.root, Sessions(root=a.root), banner=banner,
              open_browser=not a.no_open, drafts=a.drafts,
              ports={"edition": a.port} if a.port else None)
    return 0
