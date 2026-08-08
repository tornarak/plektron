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
               "only — a generated baseline is a draft nobody has read, and an "
               "end-user preview is the last place it belongs. Ratifying an "
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


def run_serve(a) -> int:
    edition_ui.serve(a.root, a.port, open_browser=not a.no_open)
    return 0
