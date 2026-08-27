"""`harness find` — the apparatus lookups: the ToC and the bibliography.

Every action here is a *search over a store a human then reads*. None resolves
anything: `authority` returns every match ranked by which field caught it,
because 52 sigla share 34 names and a single answer would be manufactured, and
because folio 9's asterism makes the list explicitly open so no hit is a
legitimate outcome. All exit 0 — an empty result is an answer.

`toc` and `folio` are two actions rather than one with a mode flag. They ask
different questions — which entries match this heading, versus what surrounds
this folio — and merging them would need a runtime check that one of the two
was supplied, which is the opaque flag interaction this CLI was reorganized to
remove.
"""
from __future__ import annotations

import sys

from ..authorities import load as load_authorities
from ..authorities import parse_citation as authority_parse
from ..authorities import record as authority_record
from ..authorities import search as authority_search
from ..authorities import sigla
from ..state import WINDOW, load_toc, toc_search, toc_window
from ._common import action, arg, group, opt, out


def register(cli):
    g = group(cli, "find", "apparatus lookups — ToC entries by heading "
              "or by folio, and the works in edition/authorities.json a "
              "citation might name",
              section="Apparatus and reports")

    p = action(g, "toc", run_toc,
               help="ToC entries whose title matches a heading you've read "
               "off the page (word-set match) — for resolving a heading toc_window "
               "came back empty or thin on, against a folio you now know"
               "\n\nQUERY: heading text as read off the page.")
    arg(p, "query")
    opt(p, "--folio", type=int, default=None,
        help="sort matches near this folio first")

    p = action(g, "folio", run_folio,
               help="ToC entries near a *known* folio — use once the "
               "printed folio has been read off the page, not a substitute for "
               "toc_window's prediction"
               "\n\nFOLIO: the printed folio, as read.")
    arg(p, "folio", type=int)
    opt(p, "--span", type=int, default=WINDOW,
        help=f"folios either side of the target (default {WINDOW})")

    p = action(g, "authority", run_authority,
               help="works in edition/authorities.json matching a citation "
               "read in the body — the siglum (Dall, I), a bare name in prose "
               "(Krause reports…), a title, or any string off the printed entry. "
               "Every match is returned and ranked, never resolved to one"
               "\n\nQUERY: a citation or a name as read off the page, not a "
               "sentence: matching is word-set containment, so 'Krause' finds the "
               "prose reference and 'Krause reports' finds nothing. A footnote "
               "form ('Dall, I, p. 375.') is accepted whole — the volume and page "
               "locator are lifted out and the lift is echoed on stderr. Several "
               "queries are pooled into one table with a `query` column, which is "
               "the ordinary case — a page's footnotes name half a dozen works, "
               "and asking six times is six turns against a collator's budget. "
               "Omit to list all 74.")
    arg(p, "queries", nargs=-1, required=False, metavar="QUERY")
    opt(p, "--volume", default=None,
        help="volume the citation names (II or 2, either form); "
             "normally read out of the query itself. Excludes on "
             "contradiction, not absence — a work whose every siglum "
             "names a different volume drops out, one with no siglum "
             "or no recorded volume stays in")
    opt(p, "--sigla", is_flag=True,
        help="the resolution table instead: one row per cited_as entry "
             "rather than per work, so the collisions are visible at "
             "once; QUERY, if given, restricts to that name")
    opt(p, "--key", default=None,
        help="one work in full, printed blocks included — printed is "
             "the record and the parsed fields lose to it")
    opt(p, "--unlocated", is_flag=True,
        help="only works with neither doi nor url — the 36 with no "
             "copy located, i.e. the worklist")


def run_toc(a) -> int:
    out(a, toc_search(load_toc(a.root), a.query, folio=a.folio))
    return 0


def run_folio(a) -> int:
    out(a, toc_window(load_toc(a.root), a.folio, [], span=a.span))
    return 0


def run_authority(a) -> int:
    works = load_authorities(a.root)
    queries = [q for q in (a.queries or ()) if q]
    if a.key:
        out(a, authority_record(works, a.key))
        return 0
    if a.sigla:
        if len(queries) > 1:
            raise ValueError(
                "--sigla with several queries: the table is one row per cited_as "
                "and a pooled one could not say which query reached which row. "
                "Ask for the whole table and read it, or query one name")
        out(a, sigla(works, queries[0] if queries else None))
        return 0
    if not queries:
        out(a, authority_search(works, "", volume=a.volume,
                                unlocated=a.unlocated))
        return 0
    # **Pooled into one table**, with `query` first where there is more than one.
    # Several tables would each be uniform and the set of them ragged, which is
    # what degrades TOON's tabular collapse; and a reader comparing what six
    # citations resolved to wants them beside each other anyway. With a single
    # query the column is absent and the output is byte-identical to what it was.
    rows = []
    for raw in queries:
        # A footnote-form query carries a volume and a page locator that are not
        # searchable text; parse_citation lifts them out. Echoed on stderr rather
        # than folded into the payload, so stdout stays the same bare table every
        # other action emits — but echoed at all, because a silently rewritten
        # query is an unexplainable miss.
        q, vol = authority_parse(raw)
        if a.volume is None and vol is not None:
            print(f"note: read volume {vol} out of {raw!r}; searching {q!r}",
                  file=sys.stderr)
        got = authority_search(works, q, volume=a.volume or vol,
                               unlocated=a.unlocated)
        if len(queries) == 1:
            out(a, got)
            return 0
        # A query that matched nothing gets a row saying so. Dropping it would
        # make "no such work" indistinguishable from "I forgot to ask", which is
        # the distinction a pooled table exists to keep.
        rows.extend([{"query": raw, **r} for r in got]
                    or [{"query": raw, "matched": "(no match)"}])
    # **Every row carries every key**, filled with "" where a no-match row has
    # nothing to say. One short row degrades TOON's tabular collapse for the
    # whole table — the same reason `generate.skipped` is padded — and a pooled
    # table that renders as nested blocks is worse than the six calls it replaced.
    keys = list(dict.fromkeys(k for r in rows for k in r))
    out(a, [{k: r.get(k, "") for k in keys} for r in rows])
    return 0
