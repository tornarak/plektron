"""`harness find` — the apparatus lookups: the ToC and the bibliography.

Every action here is a *search over a store a human then reads*. None resolves
anything: `authority` returns every match ranked by which field caught it,
because 51 sigla share 34 names and a single answer would be manufactured, and
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
              "or by folio, and the works in data/authorities.json a "
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
               help="works in data/authorities.json matching a citation "
               "read in the body — the siglum (Dall, I), a bare name in prose "
               "(Krause reports…), a title, or any string off the printed entry. "
               "Every match is returned and ranked, never resolved to one"
               "\n\nQUERY: a citation or a name as read off the page, not a "
               "sentence: matching is word-set containment, so 'Krause' finds the "
               "prose reference and 'Krause reports' finds nothing. A footnote "
               "form ('Dall, I, p. 375.') is accepted whole — the volume and page "
               "locator are lifted out and the lift is echoed on stderr. Omit to "
               "list all 73.")
    arg(p, "query", required=False, default="")
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
    if a.key:
        out(a, authority_record(works, a.key))
        return 0
    if a.sigla:
        out(a, sigla(works, a.query or None))
        return 0
    # A footnote-form query carries a volume and a page locator that are not
    # searchable text; parse_citation lifts them out. Echoed on stderr rather
    # than folded into the payload, so stdout stays the same bare table every
    # other action emits — but echoed at all, because a silently rewritten query
    # is an unexplainable miss.
    q, vol = authority_parse(a.query)
    if a.volume is None and vol is not None:
        print(f"note: read volume {vol} out of the query; searching {q!r}",
              file=sys.stderr)
    out(a, authority_search(works, q, volume=a.volume or vol,
                            unlocated=a.unlocated))
    return 0
