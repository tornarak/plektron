"""`harness edition` — the reading view over collated TEI and the encyclopedia.

Its own group rather than an action under `tei` or `entity`, because it is over
neither one: the page, the entities it links, and the raster it was read from are
three stores, and the whole point of the view is that they are in one place.
"""
from __future__ import annotations

from .. import edition_ui
from ._common import action, group, opt


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
               "entry here writes `entities/` without `--commit`, as the other "
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
