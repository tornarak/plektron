"""Routes for the reading view, `harness edition serve`.

The judgement stays in `harness/edition_ui.py`: what a gloss's little markup
means, what an imputed pronunciation is allowed to claim, which fields of a
record must reach the page, and the two guarded writes. What moved here is the
routing and the shape of each response, and what moved to the templates beside
this file is every piece of markup that used to be an f-string.

**The escaping is the reason this was worth doing.** Jinja autoescapes, so a
value reaches the page as text unless something says otherwise — where before it
was escaped if whoever wrote that line remembered. `entity_card` escaped
`canonical`; `entity_index` interpolated the same field raw two functions later.
Three things are marked `| safe` in the whole templates directory, each a
renderer that escapes its own inputs: `tei_html`'s page HTML, `geomap`'s SVG,
and the gloss markup built by `edition_ui.gloss_html`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from lxml import html as LH
from pydantic import BaseModel

# `annots`, not `annotations`: `from __future__ import annotations` above already
# binds that name at module scope, and the shadowing would be silent until
# something called a method on the feature object.
from .. import annotations as annots
from .. import (
    apparatus,
    chapters,
    entities,
    figrefs,
    geo,
    ipa,
    langs,
    lexicon,
    pictures,
    speech,
    tei_html,
)
from .. import edition_ui as ui
from .. import figures as F
from ..detectors import resolve_break_hyphens
from ..entities import ENTITY_CLASSES, alias_index, split_id
from ..state import MILESTONE_UNITS, load_toc, toc_containing
from . import Editor, register, stores, templates
from .errors import fetched
from .files import send_file

BASE = "/edition"
router = APIRouter()


def _root(request: Request) -> Path:
    return Path(request.app.state.root)


def _drafts(request: Request) -> bool:
    """Whether this sitting shows generated pages. `getattr` because an app built
    by a test or an older caller has no such attribute, and the safe reading of
    its absence is the reader's view rather than the workstation's."""
    return bool(getattr(request.app.state, "drafts", False))


def _listing(request: Request) -> list[str]:
    """Every page the edition shows, prose and plates in one scan-ordered run."""
    return stores.in_reading_order(_root(request), _drafts(request))


def _ident(raw: str) -> str:
    try:
        split_id(raw)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return raw


def _ctx(request: Request, **kw) -> dict:
    """The keys `edition/base.html` needs on every page.

    `state` carries the mount prefix because the scripts are cached static files
    served from one place and cannot hold it themselves.
    """
    base = {"base": BASE, "here": "", "state": {"base": BASE}}
    base.update(kw)
    return base


# ------------------------------------------------------------------ the text


@router.get("/")
def index(request: Request):
    root = _root(request)
    refs = _listing(request)
    signed = set(stores.collated(root))
    # The count says both numbers when both are on show: "42 page(s)" over a list
    # that is nine-tenths unread would be a claim about the edition's progress
    # that the edition cannot support.
    here = (f"{len(refs)} page(s): {len(signed)} collated, "
            f"{len(refs) - len(signed)} machine draft"
            if _drafts(request) else f"{len(refs)} page(s) collated")
    return templates.TemplateResponse(
        request,
        "edition/index.html",
        _ctx(request, refs=refs, signed=signed, drafts=_drafts(request), here=here,
             run_titles={ui.norm_ref((r.get("refs") or [""])[0]): r.get("title", "")
                         for r in stores.runs(root) if r.get("refs")},
             # **The listing says what a leaf is.** A run already announced itself
             # by title; the other 94 stood in this list as bare scan numbers, so
             # the map, the plates and 42 blanks were indistinguishable from each
             # other and from a page nobody had collated. One word each, off the
             # ruling — nothing here derives a kind.
             leaf_kinds=stores.leaf_kinds(root)),
    )


@router.get("/page/{ref}.png")
def raster(request: Request, ref: str):
    if not ui.REF_OK.match(ref):
        raise HTTPException(404, f"{ref!r} is not a PP-NNN ref")
    return send_file(
        request,
        ui.scan_for(ref, _root(request)),
        missing=f"no raster for {ref} — scans/ is derived and not " "in git",
    )


@router.get("/fig/{ref}/{key}.png")
def figure_crop(request: Request, ref: str, key: str):
    """One cut-out picture. Named by the zone's own id suffix, as the store is.

    A separate tree from `/page/{ref}.png` because these are different artefacts
    for different jobs: this is the picture inline in the prose and the thing an
    epub will embed, where the page raster behind the scan card shows a figure
    where it sits. `missing=` names the verb rather than the path, as the raster
    route does — a derived tree that has not been built is a command away, and
    saying which command is the whole difference between a 404 and a fix.

    **Resolved through `figures.crop_source`, so a human's touched-up version in
    `edition/fig-img/` wins over the machine crop** — one resolver, shared with every
    other consumer, rather than a second opinion about which file is current.
    """
    if not ui.REF_OK.match(ref) or not key.isalnum():
        raise HTTPException(404, f"{ref!r}/{key!r} is not a figure crop")
    path, _rank = F.crop_source(ref, key, _root(request))
    return send_file(
        request, path,
        missing=f"no crop for {ref}|{key} — scans/fig-crops/ is derived; "
                "build it with `harness fig crops --all`",
    )


def _figures(ref: str, root, doc: dict) -> list[dict]:
    """Which pictures hang on which `<figure>`, one row per figure the page has.

    **This is the join the renderer refuses to do**, and it is here because here
    is where both keys are in hand — the page, which `stores.render` is cached on,
    and the three figure stores, which `stores.fig_layout` is cached on. A `<figure>` in the HTML says only what the page says; the boxes arrive
    beside it and are re-derived whenever their stores move.

    A row carries the built crops out of `scans/fig-crops/` plus the float side
    and width the box implies, and `_hang_pictures` renders it into the page.
    Several crops per figure is the ordinary case, not an edge one — the store
    spells `1-276`'s fig. 140 in two boxes, and they stack under its one caption.

    **A figure opens in the lightbox, not in the stack**, so nothing here builds
    a `crop_style` for one. The stack is for what a reader has to fetch and then
    read beside the text; a picture is already on the page and the only thing
    wanted from it is size.
    """
    lay = stores.fig_layout(ref, root)
    rows = F.resolve_figures(doc.get("figures") or [], lay["figures"])
    figs = []
    for r in rows:
        f = r["figure"]
        if f is None:
            figs.append({"i": r["i"], "n": r["n"], "why": r["why"], "crops": []})
            continue
        # **One width per crop, taken from that crop's own box.** `side` is the
        # figure's — it floats as one block — but the pictures inside it keep their
        # own sizes. Handing the group's `width_frac` to every crop is what drew
        # `2-085`'s 304 px part at 1202 px; see `figures.layout`.
        parts = {p["zone_id"]: p for p in f.get("parts") or []}
        figs.append({
            "i": r["i"], "n": r["n"], "why": "",
            "crops": [{"url": f"{BASE}/fig/{ref}/{F.zone_suffix(z)}.png",
                       "width": (parts.get(z) or f).get("width_frac", 1.0)}
                      for z in f["zone_ids"]],
            "side": f.get("side", "full"),
            "width": f.get("width_frac", 1.0),
        })
    return figs


#: What became of one cross-reference, in the order a reader meets the states:
#: it points at a picture, or one of the three things that stopped it.
FIGREF_STATES = ("link", "another author's", "outside the book's numbers",
                 "a store declined")


def figref_census(root, refs: list[str], tick=None) -> dict:
    """Every cross-reference on the named pages, and what became of it.

    **It goes through `figref_rows`, which is the point.** The join it censuses
    is the one the reading view serves, over three stores and two guards, and a
    census that re-implemented it would be a second answer to the same question —
    free to disagree with the page and to go on disagreeing unnoticed, which is
    what a census is supposed to prevent. So this walks pages and shapes rows;
    every judgement in it is the view's own.

    It was written after a hand sweep found seven references linking to this
    book's pictures under Nelson's, Hough's and Teit's numbers. That sweep was
    five throwaway scripts, none of which agreed on what to count, and the defect
    had been servable for as long as the marks existed because nothing counted
    them at all. `docs/decisions.md`.

    Reports; never gates. A refused reference is the guard working, and the one
    number here that could look like a defect — `a store declined` — is the
    figure track's worklist rather than an error.
    """
    from .. import tei_html
    from ..parallel import ptrack

    # Serial rather than pooled, and ticked all the same: the work per page is a
    # cached render plus a join, so a pool would buy little, and a corpus sweep
    # is 800 pages of it and would otherwise sit silent.
    rows, pages = [], 0
    for ref in ptrack(refs, tick):
        path, rank = tei_html.page_source(ref, root)
        if path is None:
            continue
        doc = stores.render(path, root)
        # `figref_rows` is positional to the page's handles and empty where it
        # prints none, so it is the whole of what this needs — the handles are
        # not read here at all, which is what keeps the two from drifting apart.
        here = figref_rows(doc, root)
        if not here:
            continue
        pages += 1
        for r in here:
            rows.append({
                "ref": ref,
                "rank": rank,
                "prints": r["label"],
                "state": ("link" if r["pairs"] else
                          "another author's" if r["why"].endswith(
                              "not this book's") else
                          "outside the book's numbers" if r["why"].startswith(
                              "this book prints no") else
                          "a store declined"),
                # The handle, not a URL: it is what `openFigure` is given and what
                # `fig crops` writes, so a row can be chased into either store.
                "points_at": " ".join(r["pairs"]),
                "why": r["why"],
            })
    return {"rows": rows, "pages": pages,
            "counts": [{"state": s,
                        "marks": sum(1 for r in rows if r["state"] == s)}
                       for s in FIGREF_STATES]}


def figref_rows(doc: dict, root) -> list[dict]:
    """Where each cross-reference in the prose points — the join the renderer
    refuses to do, for `_figure_state`'s reason and in its manner.

    One row per handle, positional to `doc["figrefs"]`, carrying what the anchor
    is built from: `pairs` (`ref/key`, the id a card is built from), `url` (a real
    crop, so the anchor is a working link before any script and middle-clicks),
    the label the card is titled with, the `caption` it reads under, and `why`
    where nothing resolved.

    **An unresolved reference is left as text, and says so on hover.** 58 of the
    corpus's 659 refuse — a plate whose figure `gt/fig/` has not boxed, a bare
    `Fig. 1` no text page carries — and each names the store that declined. The
    alternative is linking to the nearest candidate, which on a page of
    near-identical harnesses and lamps is invisible when wrong.

    **Another author's plate is not a link at all.** Bogoras cites Nelson,
    Schrenck, Murdoch and Sauer by plate number in his footnotes, in the same
    words he uses for his own, and `Sauer, Plate XIV` collides with this book's
    Plate XIV outright. `tei generate` refuses to *mark* one, so a generated page
    reaches here carrying none; the guard stays because a mark a collator wrote
    by hand is not bound by what the generator would have done, and pointing it
    at this book's leaf is the failure it exists to prevent either way.
    """
    handles = doc.get("figrefs") or []
    if not handles:
        return []
    names = stores.authority_names(root)
    loi = stores.loi_run(root)
    by_plate = stores.by_plate(root, loi)
    by_number = stores.by_number(root)
    # **A plate's caption is the printed list's, and a figure's is the one under
    # the picture.** `resolve` reads the second off `gt/fig/` and leaves the first
    # empty on purpose: a plate is several pictures under several captions and
    # none of them is the plate's own, which only the List of Illustrations sets.
    # So the same caption reaches the card whichever end a reader clicked from —
    # the list, or the sentence that sent them to it — and a card pinned from one
    # is the card pinned from the other, `openFigure`'s id being the pictures.
    plate_captions = {str(e.get("number")): e.get("caption") or ""
                      for e in stores.run_store(root, loi)["entries"]
                      if e.get("kind") == "plate"} if loi else {}
    plates, figs = stores.printed_numbers(root)
    out = []
    for h in handles:
        # **Computed before the guards, so every row carries it.** A refused row
        # used to have an empty label, which the page could afford — its anchor
        # shows the printed numeral and its reason, not a label — and a census
        # cannot: `figrefs` has to be able to print what the page prints beside
        # what became of it, and a blank there would name no reference at all.
        label = (f"Plate {h['number']}" if h["kind"] == "plate" else
                 f"Plate {h['plate']}, Fig. {h['number']}" if h["plate"] else
                 f"Fig. {h['number']}")
        who = figrefs.foreign_citation(h.get("before") or "", names)
        if who:
            # **The reason names what the reader is looking at.** This said
            # "plate" whatever the reference was, which was tolerable while the
            # guard mostly caught plates and is not now that it catches a run of
            # figures — `Teit's plate` under a sentence printing `Fig. 128` sends
            # the reader looking for a plate that is not there. `Ibid.` stands
            # where a name would and cannot take a possessive.
            what = "plate" if h["kind"] == "plate" else "figure"
            out.append({"pairs": [], "url": "", "label": label, "caption": "",
                        "why": ("the work last cited, not this book's"
                                if who == "Ibid." else
                                f"{who}'s {what}, not this book's")})
            continue
        # **The second witness, and it is asked even where the first said
        # nothing.** `foreign_citation` reads the prose in front of the numeral
        # and can only refuse what its furniture has been taught; this asks
        # whether the book prints such a picture at all, which no sentence can
        # confuse. Both must pass before a reference is treated as this book's.
        off = figrefs.outside_the_book(h, plates, figs)
        if off:
            out.append({"pairs": [], "url": "", "label": label, "caption": "",
                        "why": off})
            continue
        r = figrefs.resolve(h, by_number, by_plate,
                            lambda leaf: stores.figure_boxes(leaf, root),
                            lambda leaf: stores.captions_on(leaf, root))
        caption = r["caption"] or (plate_captions.get(h["number"], "")
                                   if h["kind"] == "plate" else "")
        first = r["pairs"][0].split("/") if r["pairs"] else None
        out.append({
            "pairs": r["pairs"],
            "url": f"{BASE}/fig/{first[0]}/{first[1]}.png" if first else "",
            "label": label,
            "caption": caption,
            "why": r["why"],
        })
    return out


#: What each leaf kind tells the reader they are looking at. One sentence, and it
#: says only what the ruling says — the store holds "a human ruled this a blank",
#: never a measurement of the paper, so the wording is about the ruling and not
#: about the leaf. A kind with no entry falls back to the bare "not a text page",
#: which is what every one of these pages said before there were kinds.
LEAF_NOTES = {
    "plate": "a plate — a leaf given over to pictures, printed outside the "
             "text's own pagination.",
    "blank": "a blank leaf. Usually the back of a plate; the book prints "
             "nothing here.",
    "cover": "a title or wrapper leaf — the volume's own front matter, not "
             "part of the text.",
    "map": "a map, printed as a folding leaf.",
    "apparatus": "one of the book's own lists. Its content is held parsed and "
                 "is served as a run rather than as this scan.",
}


def _plates(ref: str, root) -> list[dict]:
    """The pictures `gt/fig/` boxes on an exempt leaf, in printed order."""
    figs = [f for f in stores.fig_layout(ref, root)["figures"]
            if f["box"] is not None]
    return [{
        "n": f["n"],
        "caption": f["caption"],
        "crops": [f"{BASE}/fig/{ref}/{F.zone_suffix(z)}.png"
                  for z in f["zone_ids"]],
    } for f in F.in_printed_order(figs)]


def _exempt_page(request: Request, ref: str, root):
    """A page a human ruled not a text page, shown as what it actually is.

    **The kind is read, never inferred** — `zones.LEAF_KINDS`, written by a human
    in `zones edit` at the raster. This picked between two shapes on whether the
    figure store had boxes here, which was the only fact available and is a fact
    about a *different store*: under it a blank verso and the volume's folding map
    were one case, because neither had boxes, and the page could say no more than
    "a human ruled scan 1-361 out of the transcription tracks".

    What the kind may decide is presentation. It does not decide the *pictures*:
    `gt/fig/` still says which crops exist and `in_printed_order` still sorts them,
    so a plate with no boxes drawn yet shows its leaf rather than an empty frame.
    The kind chooses how the leaf is framed and what the page tells the reader it
    is looking at; it never manufactures content the stores do not hold.
    """
    kind = tei_html.leaf_kind(ref, root)
    plates = _plates(ref, root)

    refs = _listing(request)
    i = refs.index(ref) if ref in refs else -1
    # No folio: an exempt page has no TEI and so no `<pb>` that recorded one, and
    # these are the pages that print none anyway.
    here = ref
    return templates.TemplateResponse(
        request,
        "edition/exempt.html",
        _ctx(
            request,
            ref=ref,
            kind=kind,
            kind_note=LEAF_NOTES.get(kind, ""),
            plates=plates,
            here=here,
            # An exempt leaf has no `<pb>` and prints no folio of its own, so the
            # panel is asked what the index says about the leaf and nothing else.
            # Usually that is nothing, and the Contents renders unmarked.
            toc_panel=_toc_panel(root, [stores.folio_by_ref(root).get(ref)]),
            editor_leaf=ui.leaf_source(ref, root)[1] == "ed",
            leaf_layers=ui.leaf_layers(ref, root) is not None,
            state={"base": BASE, "ref": ref,
                   "size": ui._raster_size(ref, root), "crops": {}},
            prev=refs[i - 1] if i > 0 else "",
            next=refs[i + 1] if 0 <= i < len(refs) - 1 else "",
        ),
    )


def _neighbours(request: Request, ref: str) -> tuple[str, str]:
    """Prev and next in the collapsed listing. A run stands in it as its first
    leaf, so this is also what a run page's own neighbours are computed from."""
    refs = _listing(request)
    i = refs.index(ref) if ref in refs else -1
    return (refs[i - 1] if i > 0 else "",
            refs[i + 1] if 0 <= i < len(refs) - 1 else "")


def _run_leaves(run: dict, root: Path) -> list[dict]:
    """`(leaves, tail)` — one record per leaf of the run, then the entries the
    store records as printed on a leaf the run does not cover.

    Each record carries its anchors, its folio if anything witnesses one, and its
    entries decorated for display.

    **Every leaf gets a record, including one the store says nothing about.** The
    anchor is what a redirect lands on, and a leaf with no anchor is a redirect
    into an empty fragment — the reader arrives at the top of a long list with no
    sign of why.
    """
    index = stores.folio_index(root)
    kind = run.get("kind")
    # One pass over the encyclopedia for the whole run rather than one per entry.
    # The link is the record's own `authority` field and never a match on the
    # printed name: 52 sigla over 34 names, so a name match would be a guess.
    by_authority = {rec["authority"]: ident
                    for ident, rec in (stores.load(root) or {}).items()
                    if rec.get("authority")}
    store = stores.run_store(root, run)
    # Where each plate actually is. Derived — a plate carries no number on its
    # own leaf — so it is computed once for the run and handed down, never
    # recomputed per entry in a template.
    by_plate = (stores.by_plate(root, run) if kind == "loi" else {})
    entries_by_ref: dict[str, list] = {}
    for e in store["entries"]:
        if e.get("ref"):
            entries_by_ref.setdefault(ui.norm_ref(e["ref"]), []).append(e)

    # **The printed folio for display comes from the store, the indexable one
    # from the index, and they are not the same field.** The front matter is
    # numbered in roman — the Contents runs v-xi, the List of Illustrations
    # xii-xvii — which is what the leaf carries and what a reader recognises,
    # and which is *not* a key into a folio index the ToC's own `page_start`
    # values are arabic. `source.printed_folios` is positional against
    # `source.refs`, so it is read by position and only where the two agree in
    # length; a mismatch means the store has been edited on one side and the
    # right answer is to fall back rather than to pair them off anyway.
    printed = store["source"].get("printed_folios") or []
    src_refs = store["source"].get("refs") or []
    by_ref = (dict(zip([ui.norm_ref(r) for r in src_refs], printed, strict=True))
              if len(printed) == len(src_refs) else {})

    refs = [ui.norm_ref(r) for r in run.get("refs") or []]

    def _leaf(ref: str) -> dict:
        folio = apparatus.folio_of(ref, index)
        return {
            "ref": ref,
            "anchor": apparatus.anchor("leaf", ref),
            "folio": folio,
            "printed_folio": by_ref.get(ref, ""),
            "folio_anchor": apparatus.anchor("folio", folio) if folio else "",
            "editor": ui.leaf_source(ref, root)[1] == "ed",
            "entries": [_decorate(e, kind, root, index, by_authority, by_plate)
                        for e in entries_by_ref.get(ref, [])],
        }

    # **The tail is what the printed list's own closing note points at.** An open
    # list defers — folio 9 ends Authorities Quoted with "For other authorities
    # see references in the text" — and the store may hold a work printed
    # somewhere the run does not cover. Those entries have a `ref`, so they are
    # not the `jochelson1905` case (no printed block at all, `ref: null`, and
    # nothing to render); they are printed, just not on a leaf of this list.
    #
    # They are kept OUT of `leaves` deliberately. `leaves` is the run's span —
    # it drives the scan viewer and the page's own "over N leaves (A–B)" line —
    # and folding a folio-680 entry into it would make the run claim a leaf the
    # printed list does not contain. The template renders the tail under its own
    # heading for the same reason: appended silently, the page would assert that
    # folios 3–9 hold 77 works, undoing the distinction `source.count` keeps.
    tail = [_leaf(ref) for ref in sorted(entries_by_ref) if ref not in refs]
    return [_leaf(ref) for ref in refs], tail


def _run_items(leaves: list[dict]) -> list[dict]:
    """The run's leaves flattened into one stream of list items.

    **The printed list is one list and is rendered as one**, rather than as one
    list per scan: a `<ul>` closed and reopened at every leaf boundary breaks the
    numbering, the indentation and the reader's eye at seven arbitrary places
    that are facts about the binding rather than about the list. So a leaf break
    becomes a *mark inside* the flow — `first` on the item it opens, and its own
    item where the leaf carries no entry at all, since the anchor must exist
    either way for the redirect to land on.
    """
    items = []
    for leaf in leaves:
        if not leaf["entries"]:
            items.append({"leaf": leaf, "entry": None})
            continue
        for i, entry in enumerate(leaf["entries"]):
            items.append({"leaf": leaf if i == 0 else None, "entry": entry})
    return items


def _folio_url(folio, index: dict) -> str:
    """A link to a folio, but only where something witnesses it. A dead link to
    the refusal page would train a reader to stop following them."""
    f = apparatus._as_folio(folio)
    return f"{BASE}/folio/{f}" if f is not None and f in index else ""


def _decorate(entry: dict, kind: str, root: Path, index: dict,
              by_authority: dict, by_plate: dict) -> dict:
    """One apparatus entry, plus the links the other stores can supply for it.

    Every link here is a store answering a question the printed list poses, and
    each is omitted rather than guessed where the store cannot answer.
    """
    e = dict(entry)
    # **A plate's number is not its folio and must not be drawn as one.** The
    # printed list heads that column "Opp. page": a plate is an inserted leaf
    # carrying no folio of its own, and the number is the page it faces. This
    # flattened `opposite_folio` into `folio`, so a plate's row showed a bare
    # number in the same column as a figure's own folio and linked it to the
    # facing page as though the plate were on it.
    e["opposite"] = bool(e.get("opposite_folio") and not e.get("folio"))
    if e["opposite"]:
        e["folio"] = e["opposite_folio"]
    e["folio_url"] = _folio_url(e.get("folio"), index)

    if kind == "toc":
        e["anchor"] = apparatus.anchor("toc", e["id"]) if e.get("id") else ""
        e["folio_url"] = _folio_url(e.get("page_start"), index)
        # **The heading's own anchor, appended to the folio link.** `tei_html`
        # gives every `<milestone>` the ToC id as its `@id`, so the fragment is
        # the id and nothing has to be looked up — the row already knows which
        # folio opens it and which entry it is. A fragment survives the
        # `/folio/{n}` redirect, the target carrying none of its own.
        #
        # Level 0 is skipped because it is skipped everywhere: front matter never
        # produces a milestone, so there would be no such anchor to land on, and a
        # link that cannot resolve is worse than a link to the top of the page.
        # A page that has one but is not collated yet degrades the same way — to
        # the head of the page, which is where the folio link went anyway.
        if e["folio_url"] and e.get("id") and (e.get("level") or 0) in MILESTONE_UNITS:
            e["folio_url"] += f"#{e['id']}"
    elif kind == "loi":
        # **One link per printed number, not per entry.** Two entries name
        # several figures at once ("Figs. 214, 215, 216"), and each numeral is a
        # different picture; a single link for the entry would have to pick one.
        #
        # A number resolving to exactly one zone links; anything else prints
        # plain — **and the plate leaves come out of the pool first**, exactly as
        # `figrefs.resolve` takes them out for a reference in prose. Plate figures
        # restart at 1 on every plate, so 31 pictures print `Fig. 1`; none of them
        # is a text figure, and none of them is listed here, because this list
        # enumerates the text series and the plates as wholes. The plate scopes
        # its own numbers, so leaving them in the pool made 1-4 collide with a
        # series they are not in and the first four entries dead.
        #
        # Which leaves are plates is `by_plate`'s answer and not a guess; a plate
        # that fails to locate stays in the pool and its numbers go back to
        # printing plain, which is the safe direction. Measured: all 302 of the
        # LoI's numbers now resolve — the three the rules cannot reach are
        # hand-keyed in `edition/figure_numbers.json`, which `by_number` applies.
        # `pair` is comma-joined because **a figure is not a box**: 16 of them
        # are drawn in two, lettered a and b under one caption, and naming only
        # `key` drew the first and dropped the rest. `figures.crop_keys` is the
        # rule, and `openFigure` splits on the comma exactly as it does for a
        # plate's several pictures.
        idx = stores.by_number(root)
        on_plates = {h["ref"] for h in by_plate.values() if h.get("ref")}
        e["nums"] = [
            {"n": n,
             "pair": (",".join(f"{hits[0]['ref']}/{k}" for k in hits[0]["keys"])
                      if len(hits := [h for h in idx.get(str(n)) or []
                                      if h["ref"] not in on_plates]) == 1 else ""),
             "url": (f"{BASE}/fig/{hits[0]['ref']}/{hits[0]['keys'][0]}.png"
                     if len(hits) == 1 else "")}
            for n in (e.get("numbers") or [])]
        # `pair` is `ref/key`, which is what a stack card's id is built from so
        # that a pinned figure survives a reload without the id carrying a
        # label. Only the numbers that resolved: a picture under a caption is a
        # stronger claim than a link, and the wrong one is the kind of confident
        # wrongness a bare number at least admits to.
        e["pairs"] = [n["pair"] for n in e["nums"] if n["pair"]]
        e["thumbs"] = [n["url"] for n in e["nums"] if n["url"]]
        # A plate has no figure number to resolve through, so it comes the other
        # way: `by_plate` matched its printed caption to a keyed one and named
        # the leaf. Same payload as a figure's, so the template links both the
        # same way and the card is built the same way.
        if e.get("kind") == "plate":
            hit = by_plate.get(str(e.get("number"))) or {}
            e["pairs"] = [f"{hit['ref']}/{k}" for k in hit.get("keys", ())]
            e["thumbs"] = [f"{BASE}/fig/{hit['ref']}/{k}.png"
                           for k in hit.get("keys", ())]
            e["plate_ref"] = hit.get("ref", "")
    elif kind == "authorities":
        ident = by_authority.get(e.get("key"))
        e["entity"] = f"{BASE}/entity/{ident}" if ident else ""
    return e


def _toc_tree(toc: list[dict], root: Path, index: dict) -> list[dict]:
    """The printed list as the tree its levels describe, all five deep.

    Level 0 nests as level 1: front matter emits no milestone and so is absent
    from `MILESTONE_UNITS`, but it is a top-level division of the printed list all
    the same, and at its own depth it would swallow every chapter after it.

    Rows come through `_decorate` like every other apparatus row, so the link rule
    is written once: live only where the folio index places `page_start`, and
    where it does not, the title is not a link either.
    """
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []
    for e in toc:
        node = {**_decorate(e, "toc", root, index, {}, {}),
                "depth": max(e.get("level") or 0, 1), "children": []}
        while stack and stack[-1][0] >= node["depth"]:
            stack.pop()
        (stack[-1][1]["children"] if stack else roots).append(node)
        stack.append((node["depth"], node))
    return roots


def _mark_tree(nodes: list[dict], here: set[str], tally: dict[str, int]) -> bool:
    """Mark the tree in place; answer whether anything under `nodes` is marked.

    Two things are decided here, and they are not the same thing:

      * `here` and `hits` are the *marks* — the entries this view is at, and the
        counts an entity's mentions put on them.
      * `open` is what a `<details>` does about them, which is: open along the way
        to every mark, and closed everywhere else. The whole outline is served —
        collapsed, so it is a locator and not a wall — and what stands open is the
        path to where you are.

    Unrolling the *whole* division you are in is `_toc_panel`'s, one level up,
    because only the caller knows which node is that division.
    """
    any_marked = False
    for n in nodes:
        below = _mark_tree(n["children"], here, tally)
        n["here"] = bool(n.get("id")) and n["id"] in here
        n["hits"] = tally.get(n.get("id"), 0)
        n["open"] = below or n["here"] or bool(n["hits"])
        any_marked = any_marked or n["open"]
    return any_marked


def _unroll(nodes: list[dict]) -> None:
    """Open every `<details>` under here. What "the division you are in" means:
    its sections, their subsections, and the siblings of the one you are at — a
    chapter opened to the single row that matched shows you the row you already
    had and hides the rest of the chapter, which is the opposite of a locator."""
    for n in nodes:
        n["open"] = True
        _unroll(n["children"])


def _toc_panel(root: Path, folios: list,
               hits: dict[int, int] | None = None, absent: str = "") -> dict:
    """The printed Contents as a locator: the whole outline, and what is marked.

    `folios` are the printed folios this view *is* — one for a page, several for
    a run. They arrive as whatever store the caller read them from, which for a
    page is the raw `<pb n>`, so `_as_folio` is what says which of them are
    arabic folios this index can speak about; the front matter's romans drop out
    here rather than at every call site. `hits` is `{folio: mentions}` for an
    entity's page, and each count is added to every entry containing that folio,
    so a division's number is the sum of everything beneath it without anything
    having to roll it up.

    **Two kinds of mark, because a folio can be two places at once.** The
    containing chain is where the page *is*; the entries whose `page_start` is
    this folio are the heads the page actually *prints*, and a page can print
    several — 1-249 sets both "Animal Food" and "Methods of Cooking". The chain
    keeps one entry per level by construction, so it names the last of them and
    the reader is told they are in one section of two. Both sets are marked.

    **Marks nothing where nothing witnesses the folio.** `toc_containing` refuses
    an unknown folio, and most of the book has one; a panel that guessed the
    nearest chapter would be indistinguishable, on screen, from one that knew.
    """
    toc = load_toc(root)
    index = stores.folio_index(root)
    seen = [f for f in (apparatus._as_folio(f) for f in folios) if f is not None]
    here = {tid for f in seen for tid in toc_containing(toc, f)}
    here |= {e["id"] for e in toc
             if e.get("id") and e.get("page_start") in seen}
    tally: dict[str, int] = {}
    for folio, n in (hits or {}).items():
        for tid in toc_containing(toc, folio):
            tally[tid] = tally.get(tid, 0) + n

    tree = _toc_tree(toc, root, index)
    _mark_tree(tree, here, tally)
    # **The division you are in is unrolled whole.** Only where the page has a
    # position, and not for an entity's mentions: those are spread over twenty
    # chapters, and unrolling all of them would serve the outline open, which is
    # the wall this panel is folded to avoid.
    for node in tree:
        if node["open"] and here:
            _unroll(node["children"])

    marked = bool(here or tally)
    # **The empty answer is said out loud, and the caller says it.** A panel
    # nobody asked to place anything reports nothing rather than failing to
    # answer a question that was not put — and what was asked differs by view:
    # a leaf has a position, an entry has mentions, a form has attestations, and
    # one sentence covering all three would name none of them. `absent` is the
    # caller's, for the `hits` case; the leaf's is the same wherever it is asked.
    note = ""
    if not marked and hits is not None:
        note = absent
    elif not marked and folios:
        note = "Nothing places this leaf in the printed Contents."
    return {"tree": tree, "marked": marked, "note": note}


def _by_folio(counts: dict[str, int], root: Path) -> dict[int, int]:
    """Page refs tallied onto the folios the index places them at.

    A ref the index cannot place drops out, which is the rule the marks follow
    everywhere else: the panel speaks about witnessed folios and refuses the
    rest. `stores.folio_by_ref` inverts the index once, because
    `apparatus.folio_of` walks the whole of it per ref and these lists run to
    hundreds.
    """
    folios = stores.folio_by_ref(root)
    out: dict[int, int] = {}
    for ref, n in counts.items():
        f = folios.get(ref)
        if f is not None:
            out[f] = out.get(f, 0) + n
    return out


@router.get("/run/{run_id}")
def run_page(request: Request, run_id: str):
    """One printed list, served whole.

    Six scans of List of Illustrations are one document, and paging through them
    a leaf at a time is reading the binding rather than the book. Every leaf keeps
    its anchor and its own raster link, so the physical page is never lost — what
    goes is the pretence that it is six documents.
    """
    root = _root(request)
    run = next((r for r in stores.runs(root) if r.get("id") == run_id), None)
    if run is None:
        raise HTTPException(404, f"no run {run_id!r} in edition/runs.json "
                                 "or among the chapters the text opens")
    if run.get("kind") == chapters.KIND:
        return _chapter_page(request, run, root)
    head = ui.norm_ref((run.get("refs") or [""])[0])
    prev, next_ = _neighbours(request, head)
    leaves, tail = _run_leaves(run, root)
    # The alphabet run is the one whose page is not a list. Its store holds
    # grids as well as entries, and the chart joins them to `ipa.RULES`,
    # `ipa.MODERN` and the corpus's own attestation counts — four witnesses
    # that have never been in one room. `stores.alphabet` caches the join.
    return templates.TemplateResponse(
        request,
        "edition/run.html",
        _ctx(request, run=run, leaves=leaves, items=_run_items(leaves),
             tail_items=_run_items(tail),
             chart=stores.alphabet_chart(root) if run.get("kind") == "alphabet" else None,
             here=run["title"],
             # Every leaf of the run, since a run is one document over several
             # leaves and the reader is at all of them at once.
             toc_panel=_toc_panel(root, [leaf["folio"] for leaf in leaves]),
             # `leaves` is what makes the scan button show the whole span: the
             # run is one document and its scans are several.
             state={"base": BASE, "ref": head,
                    "leaves": [leaf["ref"] for leaf in leaves],
                    "size": ui._raster_size(head, root), "crops": {}},
             prev=prev, next=next_),
    )


#: A footnote marker as `tei_html` writes it: `<a class="noteref" id="ref-1"
#: href="#note-1" …>` on a note's first reference, without the id on any later one.
_NOTEREF = re.compile(r'<a class="noteref"(?: id="ref-([^"]*)")? href="#note-([^"]*)"')


def _scope_notes(html: str, ref: str) -> str:
    """Give one leaf's footnote ids the leaf's ref, so twenty leaves can share a
    document. Every page numbers its notes from 1, and a chapter page holding two
    `note-1`s sends every marker to the first. Rewritten on the markup the
    renderer emitted rather than by teaching `tei_html` about chapters: the page
    is the TEI's unit, and the chapter is this route's. `chapter.html` writes the
    foot's ids to match."""
    def sub(m: re.Match) -> str:
        back = f' id="ref-{ref}-{m.group(1)}"' if m.group(1) is not None else ""
        return f'<a class="noteref"{back} href="#note-{ref}-{m.group(2)}"'
    return _NOTEREF.sub(sub, html)


def _split_at(html: str, anchor_id: str) -> tuple[str, str] | None:
    """`html` cut at the element carrying `id=anchor_id`, or None.

    A milestone renders at the body's top level (`el_milestone`), so cutting
    immediately before its opening tag leaves both halves balanced."""
    m = re.search(rf'<\w+[^>]*\bid="{re.escape(anchor_id)}"', html)
    return (html[:m.start()], html[m.start():]) if m else None


def _chapter_leaves(request: Request, run: dict, root: Path) -> list[dict]:
    """One record per leaf of a chapter, in binding order.

    `kind` is one of three, and each is what the stores say and nothing more:

        text     the leaf's TEI, rendered as `/page/{ref}` renders it
        exempt   a leaf a human ruled not text — a plate, a blank — with its
                 pictures, since the binding put it here
        gap      a leaf the edition holds no readable text for in this sitting.
                 Said in place, with the scan a click away: a chapter that
                 refused to render over one missing leaf would hide a hundred
                 good ones, and one that closed the gap silently would read as
                 continuous text that is not.

    On a leaf the chapter shares with a neighbour, `other` is the part that
    belongs to the neighbour, kept to be greyed and linked rather than cut: the
    reader sees where the page they are on came from or goes to.
    """
    refs = [ui.norm_ref(r) for r in run["refs"]]
    every = stores.runs(root)
    chs = [r for r in every if r.get("kind") == chapters.KIND]
    at = next(i for i, r in enumerate(chs) if r["id"] == run["id"])
    prev_ch = chs[at - 1] if run.get("head_shared") and at > 0 else None
    next_ch = chs[at + 1] if run.get("tail_shared") and at + 1 < len(chs) else None
    index = stores.folio_index(root)
    exempt = set(stores.exempt(root))
    out = []
    for k, ref in enumerate(refs):
        rec = {"ref": ref, "anchor": apparatus.anchor("leaf", ref),
               "scan": f"{BASE}/page/{ref}.png", "page_url": f"{BASE}/page/{ref}",
               "rank": ""}
        path, rank = tei_html.page_source(ref, root)
        if path is not None and (rank == "collated" or _drafts(request)):
            leaf = _leaf_doc(path, ref, root, place=False)
            doc = dict(leaf["doc"])
            doc["html"] = _scope_notes(doc["html"], ref)
            rec.update(kind="text", rank=rank, **{**leaf, "doc": doc})
            folio = apparatus._as_folio(doc.get("folio")) or apparatus.folio_of(ref, index)
            rec["before"] = rec["after"] = rec["other_url"] = rec["other_title"] = ""
            if k == 0 and prev_ch is not None:
                cut = _split_at(doc["html"], run["toc_id"])
                if cut:
                    rec["before"], doc["html"] = cut
                    rec["other_url"] = f"{BASE}/run/{prev_ch['id']}#{rec['anchor']}"
                    rec["other_title"] = prev_ch["title"]
            if k == len(refs) - 1 and next_ch is not None:
                cut = _split_at(doc["html"], next_ch["toc_id"])
                if cut:
                    doc["html"], rec["after"] = cut
                    rec["other_url"] = f"{BASE}/run/{next_ch['id']}#{next_ch['toc_id']}"
                    rec["other_title"] = next_ch["title"]
        elif path is None and ref in exempt:
            rec.update(kind="exempt", leaf_kind=tei_html.leaf_kind(ref, root),
                       plates=_plates(ref, root))
            folio = apparatus.folio_of(ref, index)
        else:
            rec.update(kind="gap", why=(
                "a machine draft, which this sitting does not show — "
                "`edition serve --drafts` does" if rank == "draft"
                else "no transcription yet"))
            folio = apparatus.folio_of(ref, index)
        rec["folio"] = folio
        rec["folio_anchor"] = apparatus.anchor("folio", folio) if folio else ""
        out.append(rec)
    return out


def _chapter_macro():
    """The chapter's piece macros, reached as a module for `_ann_macro`'s reason."""
    return templates.env.get_template("edition/_chapter.html").module


#: Top-level blocks that may stand between the two halves of a paragraph the leaf
#: break cut: a figure, an editorial flag, an annotation. Anything else there — a
#: heading, a quotation, a table — is a break of its own, and nothing is joined.
_FLOAT_TAGS = {"figure", "aside"}


def _is_float(el) -> bool:
    return (el.tag in _FLOAT_TAGS
            or (el.tag == "span" and "flag" in (el.get("class") or "").split()))


def _blocks(html: str) -> list:
    """A rendered leaf's top-level elements. Its leading whitespace goes; a page
    never opens on bare text, `tei_html` wrapping everything it emits."""
    root = LH.fragment_fromstring(html or "<div></div>", create_parent="div")
    return list(root)


#: The end of a leaf's last paragraph when its last word is cut, and the start of
#: the next leaf's first, as plain text: the stem with its hyphen, and the rest.
_CUT_END = re.compile(r"(\S+)-\s*$")
_CUT_START = re.compile(r"\S+")


def _turn_word(open_p, first, ref: str, idx: dict) -> bool:
    """Close or keep a word the page turn cut, by the line-end rule; True if done.

    **The same rule as a line end inside a page** (`resolve_break_hyphens`): the
    joined word is offered to the corpus as it stands and with the cut closed, and
    the spelling ground truth sets mid-line elsewhere wins — `consider-|able`
    closes, `birth-|water` keeps its hyphen, and a word with both or neither keeps
    it too, as the generator does before asking. A word bearing the notation is
    refused outright, for the firewall's reason. Either way the word is set whole
    and the page mark goes after it, so the mark never splits a word.

    Only where both halves are plain text — the stem the tail of the paragraph's
    last node, the rest the head of the next paragraph's text. A half inside an
    element (an entity link) is left as it was, hyphen and space and all: moving
    text across element boundaries to close a word is a restructuring no rule here
    has the standing to do.
    """
    holder = open_p[-1] if len(open_p) else open_p
    left = (holder.tail if len(open_p) else holder.text) or ""
    lm, rm = _CUT_END.search(left), _CUT_START.match(first.text or "")
    if lm is None or rm is None:
        return False
    stem, rest = lm.group(1), rm.group()
    whole, verdicts = resolve_break_hyphens(f"{stem}-{rest}", [len(stem)], ref, idx)
    if not verdicts:
        return False
    new = left[:lm.start()] + whole
    if len(open_p):
        holder.tail = new
    else:
        holder.text = new
    first.text = first.text[rm.end():]
    return True


def _chapter_body(leaves: list[dict], idx: dict | None = None) -> str:
    """The chapter's text as one HTML string, with the leaf breaks closed.

    **A paragraph the leaf break cut is one paragraph again.** Whether the next
    leaf continues it is what that leaf already says — `tei_html.page_opens`,
    off `@part` where the seam is written, else the collator's `opens:`, else
    the keyed zone label — and is carried as `opens-continued` on its first
    paragraph. That is the whole test; nothing here judges a sentence end.

    **Where the two halves are joined, the page mark goes inside the paragraph**,
    exactly where the leaf turned, and the stylesheet draws it in the margin:
    Project Gutenberg's convention, and the reason the body is built here rather
    than looped over in the template.

    **What stood between the halves moves to the top of the joined paragraph** —
    a figure, a flag, a plate on a leaf of its own. That is `tei generate`'s rule
    for a figure the prose runs past, for its reasons, applied one level up. A
    gap leaf never joins: nothing says what its text would have done.
    """
    m = _chapter_macro()
    items: list = []          # lxml elements, or strings for macro output
    #: The previous text leaf's last paragraph, while it may still be continued:
    #: only floats and plates have been appended since.
    open_p = None
    for leaf in leaves:
        mark = str(m.leafmark(leaf))
        if leaf["kind"] == "exempt":
            items.append(str(m.exempt(leaf)))
            continue
        if leaf["kind"] == "gap":
            items.append(str(m.gap(leaf)))
            open_p = None
            continue
        if not leaf["doc"].get("ok"):
            items.append(str(m.broken(leaf)))
            open_p = None
            continue
        if leaf.get("before"):
            items.append(str(m.other(leaf["before"], leaf, "before")))
        blocks = _blocks(leaf["doc"]["html"])
        lead = 0
        while lead < len(blocks) and _is_float(blocks[lead]):
            lead += 1
        first = blocks[lead] if lead < len(blocks) else None
        continues = (open_p is not None and first is not None and first.tag == "p"
                     and "opens-continued" in (first.get("class") or "").split())
        if continues:
            # The floats at the head of this leaf join everything else that came
            # between, above the paragraph: out of `items` and back in after it.
            at = items.index(open_p)
            between = items[at + 1:]
            del items[at:]
            items.extend(between)
            items.extend(blocks[:lead])
            # A word the turn cut is set whole first, so the mark lands after it
            # rather than between its halves; otherwise the turn is a space.
            cut = idx is not None and _turn_word(open_p, first, leaf["ref"], idx)
            marked = LH.fragment_fromstring(mark)
            marked.tail = ("" if cut else " ") + (first.text or "")
            open_p.append(marked)
            for child in list(first):
                open_p.append(child)
            items.append(open_p)
            rest = blocks[lead + 1:]
        else:
            items.append(mark)
            rest = blocks
        items.extend(rest)
        last = next((i for i in range(len(items) - 1, -1, -1)
                     if not (not isinstance(items[i], str) and _is_float(items[i]))),
                    None)
        open_p = (items[last] if last is not None and not isinstance(items[last], str)
                  and items[last].tag == "p" else None)
        if leaf.get("after"):
            items.append(str(m.other(leaf["after"], leaf, "after")))
            open_p = None
    return "".join(i if isinstance(i, str) else LH.tostring(i, encoding="unicode")
                   for i in items)


def _pooled(per_leaf) -> list[dict]:
    """One list of annotation blocks out of many leaves', each block once.

    A notice attached to a ToC section attaches to every leaf in it, so twenty
    leaves of one section hand over the same block twenty times; the chapter
    shows it once, where the first leaf carrying it put it in the order."""
    seen, out = set(), []
    for blocks in per_leaf:
        for b in blocks:
            if b["id"] not in seen:
                seen.add(b["id"])
                out.append(b)
    return out


def _pooled_notes(leaves: list[dict]) -> list[dict]:
    """The chapter's footnotes, one group per leaf that has any, in binding order.

    **Grouped and not renumbered.** The marker in the text is the printed
    superscript itself — inventory the ground-truth pass adjudicated — and the
    book numbers its notes from 1 on every page. A running number would either
    rewrite that glyph or have the text say ¹ while the list says 14. So the
    group carries the page the reader cites, the printed folio where one is
    known and the scan ref where not, and the note keeps the number it was
    printed with; the leaf-scoped ids (`_scope_notes`) keep two note 1s apart.
    """
    return [{"ref": leaf["ref"], "folio": leaf["folio"], "notes": leaf["doc"]["notes"]}
            for leaf in leaves if leaf["doc"].get("notes")]


def _chapter_page(request: Request, run: dict, root: Path):
    """A chapter, served whole: its leaves in binding order, each as it renders
    alone, with the leaf break kept as a mark in the margin. The listing and the
    neighbours treat it as the leaf it opens on, as they do every run."""
    leaves = _chapter_leaves(request, run, root)
    head = leaves[0]["ref"]
    prev, next_ = _neighbours(request, head)
    drafts = sum(1 for leaf in leaves if leaf.get("rank") == "draft")
    gaps = sum(1 for leaf in leaves if leaf["kind"] == "gap")
    text = [leaf for leaf in leaves if leaf["kind"] == "text" and leaf["doc"].get("ok")]
    return templates.TemplateResponse(
        request,
        "edition/chapter.html",
        _ctx(request, run=run, leaves=leaves, drafts=drafts, gaps=gaps,
             body=_chapter_body(leaves, stores.midline(root)),
             notices=_pooled(leaf["notices"] for leaf in text),
             supplements=_pooled(leaf["supplements"] for leaf in text),
             notes=_pooled_notes(text),
             placed=all(leaf["placed"] for leaf in text),
             store_has_toc=any(leaf["store_has_toc"] for leaf in text),
             here=run["title"], pane=True,
             toc_panel=_toc_panel(root, [leaf["folio"] for leaf in leaves]),
             state={"base": BASE, "ref": head,
                    "leaves": [leaf["ref"] for leaf in leaves],
                    "size": ui._raster_size(head, root), "crops": {}},
             prev=prev, next=next_),
    )


def _located(root: Path) -> dict:
    """The cached runs and heading index `apparatus.locate` would otherwise derive
    per call — and a refusal places every row of its `nearest` list."""
    return {"among": stores.runs(root), "heads": stores.heads(root)}


def _resolved(out: dict) -> RedirectResponse | None:
    url = out.get("url")
    if not url:
        return None
    return RedirectResponse(url + (f"#{out['anchor']}" if out["anchor"] else ""),
                            status_code=302)


def _refusal(request: Request, out: dict, asked: str):
    """What a locator that could not resolve says, as a page.

    **This is the ordinary answer, not an error**, and it has to read like one:
    280 of the book's 732 folios have a witness today, so a reader following a
    ToC link will land here more often than not. It names what is nearby and
    never interpolates — a redirect is a resolution, and a guessed one would be
    indistinguishable from a witnessed one at the URL.
    """
    return templates.TemplateResponse(
        request, "edition/folio.html",
        _ctx(request, asked=asked, here=asked,
             nearest=out.get("nearest") or [],
             candidates=out.get("candidates") or [],
             why=out.get("why", "")),
        status_code=404 if not out.get("candidates") else 300)


@router.get("/folio/{n}")
def folio(request: Request, n: int):
    """A printed folio, resolved to wherever the corpus says it is."""
    root = _root(request)
    out = apparatus.locate(root, folio=n, index=stores.folio_index(root),
                           **_located(root))
    return _resolved(out) or _refusal(request, out, f"folio {n}")


@router.get("/chapter/{roman}")
def chapter(request: Request, roman: str):
    """A chapter, by the roman the prose prints — `See Chapter XII.`

    **The id is looked up, never built.** `chXII` is `edition/toc.json`'s own
    spelling and concatenating `ch` with the roman would be this route asserting
    the store's key scheme from outside it; the entry whose `chapter` is this
    roman *and* whose level is the chapter level is what the store says. A roman
    the ToC does not hold refuses here rather than at scan time, which is the
    answer `figrefs.resolve` already gives for a plate with no leaf: the
    reference is a fact about the printed page, and where it points is a fact
    about a store that can be incomplete.
    """
    root = _root(request)
    entry = next((e for e in load_toc(root)
                  if e.get("chapter") == roman and e.get("level") == 1
                  and e.get("id")), None)
    if entry is None:
        return _refusal(request, {"nearest": []}, f"Chapter {roman}")
    out = apparatus.locate(root, toc_id=entry["id"],
                           index=stores.folio_index(root), **_located(root))
    return _resolved(out) or _refusal(request, out, f"Chapter {roman}")


@router.get("/toc/{toc_id}")
def toc_entry(request: Request, toc_id: str):
    """A heading, by its `edition/toc.json` id, through its opening folio.

    The precursor property, and the reason the locator was built before the
    renderers: this resolves *today* wherever a witness places the chapter's
    first folio, and it will keep resolving unchanged the day that chapter
    becomes a run with a page of its own.
    """
    root = _root(request)
    out = apparatus.locate(root, toc_id=toc_id, index=stores.folio_index(root),
                           **_located(root))
    return _resolved(out) or _refusal(request, out, f"heading {toc_id}")


@router.get("/leaf/{ref}")
def leaf(request: Request, ref: str):
    """An editor's own version of a whole leaf, where one exists.

    A route of its own rather than an override on `/page/{ref}.png`, so the raw
    scan stays reachable at its own address: this is a made artefact and the
    scan is the evidence, and a reader must be able to get at both.
    """
    if not ui.REF_OK.match(ref):
        raise HTTPException(404, f"{ref!r} is not a PP-NNN ref")
    path, rank = ui.leaf_source(ref, _root(request))
    if path is None:
        raise HTTPException(
            404, f"no editor's leaf for {ref} in {ui.PAGE_IMG}/ — the scan is at "
                 f"{BASE}/page/{ref}.png")
    return send_file(request, path, media_type=ui.LEAF_MEDIA[path.suffix],
                     missing=f"no editor's leaf for {ref}")


@router.get("/leaf/{ref}/{layer}")
def leaf_layer(request: Request, ref: str, layer: str):
    """One half of an editor's leaf, split for delivery.

    The master is 21 MB and the pair is under two, so this is what the page
    actually loads; `/leaf/{ref}` above stays the authored file's own address,
    reachable and unchanged. Both are the same artefact and the split is
    `tools/build_leaf_layers.py`'s.
    """
    if not ui.REF_OK.match(ref):
        raise HTTPException(404, f"{ref!r} is not a PP-NNN ref")
    if layer not in ui.LEAF_LAYERS:
        raise HTTPException(
            404, f"{layer!r} is not a leaf layer — "
                 f"{', '.join(sorted(ui.LEAF_LAYERS))}")
    layers = ui.leaf_layers(ref, _root(request))
    if layers is None:
        raise HTTPException(
            404, f"no built layers for {ref} — the master is at "
                 f"{BASE}/leaf/{ref}; `uv run --script "
                 f"tools/build_leaf_layers.py {ref}` writes them")
    path = layers[layer]
    return send_file(request, path, media_type=ui.LEAF_MEDIA[path.suffix],
                     missing=f"no {layer} layer for {ref}")


@router.get("/page/{ref}")
def page(request: Request, ref: str):
    root = _root(request)
    if not ui.REF_OK.match(ref):
        raise HTTPException(404, f"{ref!r} is not a PP-NNN ref")
    # A leaf inside a run is served by its run, at its own anchor — every leaf,
    # the first included, so a run has one canonical URL rather than a head that
    # renders and interior leaves that bounce.
    run = stores.run_for(root, ref)
    if run is not None:
        return RedirectResponse(
            f"{BASE}/run/{run['id']}#{apparatus.anchor('leaf', ref)}",
            status_code=302)
    path, rank = tei_html.page_source(ref, root)
    if path is None and ref in stores.exempt(root):
        return _exempt_page(request, ref, root)
    if path is None or (rank == "draft" and not _drafts(request)):
        raise HTTPException(
            404,
            f"{ref} is not collated. The reading view shows committed tei/ only"
            + ("; a generated draft exists — `edition serve --drafts` shows it."
               if rank == "draft" else "."),
        )
    leaf = _leaf_doc(path, ref, root)
    doc = leaf["doc"]
    refs = _listing(request)
    i = refs.index(ref) if ref in refs else -1
    # `PP-NNN (folio)`, both systems at once, because neither is derivable from
    # the other (CLAUDE.md, Page refs). No folio prints none rather than a dash:
    # plates and front matter genuinely print none, and this is not the place to
    # make that look like missing data.
    here = ref + (f" ({doc['folio']})" if doc.get("folio") else "")
    size = ui._raster_size(ref, root)
    # `crops` is the scan card's and stays; the figure join is no longer part of
    # the payload at all, because nothing on the client reads it any more.
    state = {"base": BASE, "ref": ref, "size": size, "crops": {}}
    return templates.TemplateResponse(
        request,
        "edition/page.html",
        _ctx(
            request,
            ref=ref,
            doc=doc,
            here=here,
            state=state,
            rank=rank,
            pane=True,
            notices=leaf["notices"],
            supplements=leaf["supplements"],
            placed=leaf["placed"],
            store_has_toc=leaf["store_has_toc"],
            toc_panel=_toc_panel(root, [doc.get("folio")]),
            prev=refs[i - 1] if i > 0 else "",
            next=refs[i + 1] if 0 <= i < len(refs) - 1 else "",
        ),
    )


def _leaf_doc(path: Path, ref: str, root: Path, place: bool = True) -> dict:
    """One text leaf, rendered and joined: what `/page/{ref}` shows, and what a
    chapter shows for each of its text leaves — one function, so the two cannot
    drift into showing one page two ways.

    Returns `{doc, notices, supplements, placed, store_has_toc}`. `place=False`
    leaves every notice in `notices` rather than splicing a section's under its
    marker: a chapter pools them at its head instead.
    """
    doc = stores.render(path, root)
    doc = _hang_pictures(doc, _figures(ref, root, doc), figref_rows(doc, root))
    # **The folio is resolved here and handed down**, never looked up inside
    # `annotations.for_page`. Placing a leaf in a section runs `ref → folio →
    # toc ids` and the middle step can refuse; if the chain lived in the
    # resolver, an empty list would mean both "nothing attaches here" and "we
    # cannot say whether anything does". Only this frame holds the folio, so
    # only this frame can tell the template which happened.
    # `doc["folio"]` is the raw `<pb n>`, so it is a string and may be a roman
    # numeral from the front matter. `_as_folio` is what says which of those are
    # arabic folios this index can speak about — the same coercion `_toc_panel`
    # makes, and the same refusal: a roman folio is not unplaced by accident, it
    # is a leaf the arabic index has nothing to say about.
    folio = apparatus._as_folio(doc.get("folio"))
    ann_store = stores.annotations(root)
    anns = annots.for_page(ann_store, ref, toc_containing(load_toc(root), folio))
    store = stores.load(root)
    notices = ui.annotation_blocks(anns["top"], store)
    if place:
        doc, notices = _place_notices(doc, notices)
    return {"doc": doc, "notices": notices,
            "supplements": ui.annotation_blocks(anns["bottom"], store),
            "placed": folio is not None,
            "store_has_toc": annots.has_toc_attachments(ann_store)}


# -------------------------------------------------------------- the entities


#: How many pages a card's mention list names. A card is for sizing an entry up,
#: not for reading the corpus through; `entity occurrences` is the whole list.
MENTIONS = 8


def _mentions(ident: str, refs: list[str], root: Path) -> dict:
    """One entity's mentions, out of the cached whole-store sweep, **by page**.

    **One row per page and not per occurrence.** "Where does this appear" is a
    page question, and the per-occurrence list answered it badly: `place:markovo`
    is linked four times on 1-045 alone, so the first eight rows were four pages
    with the same word in them and the reader learned nothing a count would not
    have told them in a quarter of the space.

    **Filtered to `refs`, which is the page list the view is serving.** Without
    `--drafts` a generated page 404s by design, so a row naming one would send a
    reader nowhere; the sweep is over everything and the narrowing happens here.

    The snippet prefers an *unlinked* hit, which carries the prose either side —
    a linked one's text is the form itself, and a row saying "Markova: Markova"
    is a row that has said nothing. `swept` is on the card because a bare zero
    cannot be told from "never mentioned", and today it usually means one of two
    other things: collation has reached one page, so the default corpus is that
    page, or `mz/tei/` was never generated and `--drafts` has nothing to add.
    """
    got = stores.occurrences(root).get(ident) or {"linked": [], "unlinked": []}
    keep = set(refs)
    pages: dict[str, dict] = {}
    for kind in ("linked", "unlinked"):
        for r in got[kind]:
            if r["ref"] not in keep:
                continue
            row = pages.setdefault(r["ref"], {
                "ref": r["ref"], "rank": r["rank"], "linked": 0, "unlinked": 0,
                "before": "", "match": "", "after": "", "text": ""})
            row[kind] += 1
            if kind == "unlinked" and not row["before"]:
                row |= {k: r[k] for k in ("before", "match", "after")}
            elif kind == "linked" and not row["text"]:
                row["text"] = r["text"]
    rows = sorted(pages.values(), key=lambda r: r["ref"])
    # **`by_ref` is every page, and `rows` is the eight the card shows.** The
    # contents panel marks chapters, and a chapter is not reached by the first
    # eight pages of an entity that appears on forty — truncating before the fold
    # would leave whole chapters unmarked and look, on screen, exactly like an
    # entity that is not mentioned in them.
    return {"rows": rows[:MENTIONS], "pages": len(rows),
            "by_ref": {r["ref"]: r["linked"] + r["unlinked"] for r in rows},
            "total": sum(r["linked"] + r["unlinked"] for r in rows),
            "swept": len(refs)}


def _entity_ctx(ident: str, refs: list[str], root: Path) -> dict:
    store = stores.load(root)
    rec = store.get(ident)
    if rec is None:
        return {"rec": None, "ident": ident, "base": BASE}
    idx = alias_index(store)
    contested = sorted(
        {
            c["id"]
            for t in rec["aliases"]
            for c in idx.get(t["form"], [])
            if c["id"] != ident
        }
    )
    # **A Tier-1 alias links to its lexicon card.** In the page text the entity
    # link wins, since an anchor inside an anchor is not markup — so the card is
    # where the form's own entry has to be reachable, and this row is the place:
    # it is the one spot that says "this entity is called that, in Chukchi".
    aliases = [
        {**t, "note_html": ui.inline_html(t["note"], store),
         "lang_name": langs.name(t["lang"]) if t["lang"] else "",
         "lex": t["form"] if t["lang"] in langs.TIER1 else ""}
        for t in rec["aliases"]
    ]
    return {
        "rec": {**rec, "aliases": aliases},
        "ident": ident,
        "base": BASE,
        "gloss": ui.gloss_html(rec["gloss"], store),
        "links": [ui.link_html(ln) for ln in rec["links"]],
        "image": pictures.resolve(rec, stores.picture_ledger(root)),
        "contested": [{"id": c, "canonical": store[c]["canonical"]} for c in contested],
        "located": bool(geo.located(ident, store, root)),
        "props": ui.property_rows(rec, store, root),
        # Where the entry sits in its own class. Not the atlas's tree — a located
        # entry has that in the map pane beside it, and the two hierarchies are
        # kept apart on purpose (`entities.kin_parent`).
        "kin_nodes": ui.kin_tree(ident, store),
        "mentions": _mentions(ident, refs, root),
        # No folio is in play here, so there is no refusal to state: an entity
        # attachment names the entry outright.
        **_ann_ctx(annots.for_entity(stores.annotations(root), ident), store),
    }


def _ann_ctx(anns: dict, store: dict) -> dict:
    return {"notices": ui.annotation_blocks(anns["top"], store),
            "supplements": ui.annotation_blocks(anns["bottom"], store)}


@router.get("/entity/{ident:path}")
def entity(request: Request, ident: str, partial: str = ""):
    """The entry, and — on a page of its own — its map beside it.

    **`?partial=1` deliberately carries no map.** That fragment is what the stack
    injects and what a hover preview floats, and both of those are read *while*
    the pane is showing the geography already; a second copy of it inside the
    card would answer a question nothing was asking and cost a map render per
    hover. The pane is the one place a map is.
    """
    root = _root(request)
    ctx = _entity_ctx(_ident(ident), _listing(request), root)
    if partial:
        return templates.TemplateResponse(request, "edition/_entity.html", ctx)
    rec = ctx.get("rec")
    if ctx.get("located"):
        ctx = {**_map_ctx(ident, root), **ctx, "map": True}
    # Where the entry is mentioned, said in the book's own divisions rather than
    # as a page list: a reader sizing an entry up wants to know it is a chapter's
    # subject and a passing name in two others, and forty refs sorted by scan
    # number do not say that.
    #
    # `None` and not an empty dict where the store holds no such entry: the panel
    # reports a failure to place what it was *asked* to place, and an id nothing
    # answers to was never asked about. That page has its own refusal to make.
    by_folio = (None if rec is None
                else _by_folio(ctx["mentions"]["by_ref"], root))
    return templates.TemplateResponse(
        request,
        "edition/card.html",
        _ctx(
            request,
            partial="edition/_entity.html",
            card_title=rec["canonical"] if rec else ident,
            toc_panel=_toc_panel(
                root, [], by_folio,
                # Only where there were pages to place, on `_mentions`' own
                # reasoning: a bare zero cannot be told from "never mentioned",
                # and an entry the corpus does not mention has not failed to be
                # placed in the Contents. The card's mention rows say that
                # already, with `swept` beside them.
                absent=("No mention of this entry is placed in the printed "
                        "Contents."
                        if rec is not None and ctx["mentions"]["by_ref"]
                        else "")),
            **ctx,
        ),
    )


def _place_notices(doc: dict, blocks: list[dict]) -> tuple[dict, list[dict]]:
    """Move a section's notice down to sit under the marker a reader lands on.

    **A notice above `<article>` is above the anchor the contents panel links
    to.** `tei_html` emits `id="chII.1"` inside the article, so following
    "Appearance" from the panel scrolls past a notice rendered at the top of the
    page and leaves it off-screen — present, and easy to miss at exactly the
    moment it was written for. Where the page marks a section the notice is keyed
    to, the block goes directly after that marker instead.

    A page-attached notice, and a section-attached one on a page that does *not*
    print the marker, both stay at the top: there is no better place, and the
    reader arrived at the page rather than at a point inside it.

    Returns a **copy** of `doc`. `stores.render` is `lru_cache`d, so writing the
    spliced HTML back into the record it handed out would serve one page's
    notices on every later render of it.
    """
    html, stay = doc["html"], []
    for b in blocks:
        for anchor_id in b["toc"]:
            spliced = ui.insert_after_anchor(
                html, anchor_id, str(_ann_macro().blocks([b])))
            if spliced is not None:
                html = spliced
                break
        else:
            stay.append(b)
    return ({**doc, "html": html}, stay) if html != doc["html"] else (doc, stay)


def _hang_pictures(doc: dict, figs: list[dict], refs: list[dict]) -> dict:
    """Put the figure join into the served HTML: the pictures, and the links.

    **The join stays out of `stores.render`'s cache and reaches the reader
    anyway.** `tei_html` emits a `<figure>` carrying only what the page says and
    an inert `<a class="figref">`, for the cache reason `el_figure` sets out; this
    runs per request, off `_figures` and `figref_rows`, whose own keys name the
    stores that can move a box. What changes is where the markup is assembled:
    it used to be `edition.js`, off a `STATE.figs`/`STATE.figrefs` payload, so a
    reader with no script got an adjudicated caption over a blank space and a
    cross-reference that was a dotted underline and nothing else.

    A figure the join has no row for is left as the renderer wrote it, which is
    `edition.js`'s old `if (!el) continue` read from the other end: the records
    are positional to the renderer's handles, and a mismatch means one of the two
    is stale, never that some other figure's picture will do.

    Returns a **copy** of `doc`. `stores.render` is `lru_cache`d, and writing the
    spliced HTML back into the record it handed out is exactly how the stale
    placement this whole arrangement exists to prevent would get cached after all.
    """
    m = _fig_macro()
    by_i = {f["i"]: f for f in figs}

    def splice(html: str) -> str:
        html = ui.hang_figures(
            html, lambda i, n: str(m.head(by_i[i], n, i)) if i in by_i else "")
        return ui.link_figrefs(
            html, lambda i, body: str(m.ref(refs[i], body)) if i < len(refs) else "")

    # **The notes are the page's other stream of rendered HTML, and they carry
    # references.** `el_note` holds a footnote's words aside for the template to
    # set at the foot, so a `(Plate XXXVI, Fig. 2)` inside one never appears in
    # `doc["html"]` — `1-132` prints two and neither is in the body. The script
    # this replaced queried the whole document and so reached them without ever
    # having to know that; a splice over one string does not, and 36 references
    # corpus-wide were left inert until this ran over both. The handle index runs
    # across body and notes together, which is what lets one `refs` serve both.
    out = {**doc, "html": splice(doc["html"]),
           "notes": [{**n, "html": splice(n["html"])} for n in doc["notes"]]}
    return doc if out["html"] == doc["html"] and out["notes"] == doc["notes"] else out


def _fig_macro():
    """The figure macros, reached as a module for `_ann_macro`'s reason."""
    return templates.env.get_template("edition/_figure.html").module


def _ann_macro():
    """The block macro, reached as a module so one renderer serves both places.

    The template is the only definition of what an annotation looks like; a
    second copy built as a Python string here would drift from it the first time
    either changed.
    """
    return templates.env.get_template("edition/_annotations.html").module


@router.get("/annotations")
def annotations_index(request: Request):
    """Every annotation, so the store is reachable without knowing a slug."""
    root = _root(request)
    store = stores.annotations(root)
    rows = [{"id": k, "title": v["title"], "class": v["class"],
             "status": v["status"], "placement": v["placement"],
             "attaches": len(v["attaches"]),
             "url": f"{BASE}/annotation/{k}"}
            for k, v in sorted(store.items())]
    return templates.TemplateResponse(
        request, "edition/annotations.html",
        _ctx(request, rows=rows, card_title="Notices and supplements"))


def _attached_rows(rec: dict, root: Path) -> list[dict]:
    """What this annotation is attached to, each as a link where one resolves.

    A `toc:` target is the one that can refuse: `apparatus.locate` answers from
    the folio index, and a section whose opening folio nothing witnesses has no
    leaf to send a reader to. **Said as a sentence rather than rendered as dead
    text** — the same ruling the contents panel makes.
    """
    store = stores.load(root)
    toc = {e["id"]: e for e in load_toc(root)}
    rows = []
    for t in rec["attaches"]:
        if t["kind"] == "page":
            rows.append({"label": t["value"], "why": "page",
                         "url": f"{BASE}/page/{t['value']}"})
        elif t["kind"] == "entity":
            ent = store.get(t["value"])
            rows.append({"label": ent["canonical"] if ent else t["value"],
                         "why": t["value"],
                         "url": f"{BASE}/entity/{t['value']}"})
        else:
            entry = toc.get(t["value"])
            label = entry["title"] if entry else t["value"]
            try:
                where = apparatus.locate(root, toc_id=t["value"], **_located(root))
            except Exception:
                where = None
            ref = (where or {}).get("ref")
            rows.append({
                "label": f"{label} ({t['value']})",
                "url": f"{BASE}/page/{ref}" if ref else "",
                "why": "" if ref else
                       "no leaf is witnessed at this section's opening folio",
            })
    return rows


@router.get("/annotation/{ident:path}")
def annotation_card(request: Request, ident: str, partial: str = ""):
    """One annotation's own page.

    **Served whatever its status**, unlike the blocks it puts on a page. A
    `proposed` annotation attaches to nothing, and this is where a reviewer reads
    it before ratifying — a store whose unratified entries were unreachable would
    have no review step at all.
    """
    root = _root(request)
    try:
        annots.split_id(ident)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    rec = stores.annotations(root).get(ident)
    if rec is not None:
        # The raw parse record has no `video`; `annotation_blocks` is what adds
        # it, and this page does not go through that. Same call, one place.
        rec = rec | {"links": [r | {"embed": ui.youtube_embed(r["url"])}
                               for r in rec["links"]]}
    store = stores.load(root)
    ctx = {"rec": rec, "ident": ident, "base": BASE,
           "summary_html": ui.gloss_html(
               annots.expand_links(rec["summary"], rec["links"]), store)
           if rec else "",
           "full_html": ui.annotation_full_html(rec, store) if rec else "",
           "attached": _attached_rows(rec, root) if rec else []}
    if partial:
        return templates.TemplateResponse(request, "edition/_annotation.html", ctx)
    return templates.TemplateResponse(
        request, "edition/card.html",
        _ctx(request, partial="edition/_annotation.html",
             card_title=rec["title"] if rec else ident, **ctx))


@router.get("/lexicon")
def lexicon_index(request: Request):
    """Every attested Tier-1 form, grouped by the language a collator assigned.

    **Grouped by language, and mostly *unassigned*, which is the honest
    picture.** A form's language is a judgement made during collation, and
    collation has reached one page — so 18 forms carry a code and the rest of
    the corpus sits in the last branch. Showing it that way makes the index
    double as the collation worklist, where a tree over only the assigned forms
    would show an encouraging empty list.

    Every one of the Tier-1 codes appears whether or not it holds anything, for
    the reason the class tree shows its empty classes: a vocabulary that lists
    only its populated half quietly misrepresents its own size.
    """
    root = _root(request)
    forms = _forms(root)
    groups = [{"lang": lang,
               # The empty branch is labelled rather than left blank: it is the
               # collation worklist and by far the largest, and a heading with
               # no text would read as a rendering fault.
               "name": langs.TIER1_NAMES.get(lang) or "unassigned",
               "rows": [r for r in forms if r["lang"] == lang]}
              for lang in [*langs.TIER1_NAMES, ""]]
    written = sum(1 for r in forms if r["note"])
    return templates.TemplateResponse(
        request,
        "edition/lexicon.html",
        _ctx(request, groups=groups,
             here=f"{len(forms)} forms · {written} with an editor's note"),
    )


def _forms(root: Path) -> list[dict]:
    """The lexicon's population: every form `gt/ocr/` attests, in one list.

    Assembled from three stores and owned by none of them — the forms and their
    counts from adjudicated ground truth, the language and attesting pages from
    committed TEI where a collator has judged one, the note from `edition/lexicon/`
    where an editor has written one. A form with no entry is not missing from
    this list; it is a form nobody has written about, which is most of them.
    """
    attested = stores.attestations(root)
    store = stores.lexicon_store(root)
    out = []
    for f in _attested_forms(stores.native(root)):
        form = lexicon.norm_form(f["form"])
        langs = sorted({lang for _ref, lang in attested.get(form, [])})
        rec = store.get(form)
        out.append({
            "form": form,
            "key": f["key"] or "",
            "count": f["count"],
            # Blank rather than a guess where collation has not reached the
            # form, and the *first* of several rather than a silent pick
            # where it has read one string as two languages — the row says
            # `langs` too, so the grouping never hides the disagreement.
            "lang": langs[0] if len(langs) == 1 else "",
            "langs": langs,
            "note": bool(rec and rec["note"]),
            "status": rec["status"] if rec else "",
        })
    # By the key where there is one, by the form where there is not — and the
    # keyless sort last within their letter rather than first, so a group of
    # them cannot look like the head of the list.
    out.sort(key=lambda r: ((r["key"] or r["form"]).lower(), not r["key"],
                            r["form"]))
    return out


def _attested_forms(native: dict) -> list[dict]:
    """Every Tier-1 form `gt/ocr/` attests, addressable or not.

    **The union is the point.** `lookup.index` buckets only what `handle_key`
    can spell and files the rest under `unkeyable` — right for an instrument
    whose product *is* the key, wrong for a lexicon, whose question is what the
    corpus contains. Three forms are in that position today: `□ña`, whose first
    character is a reader's mark for an unread glyph, and `Kereˊt-kun’s` /
    `Kereˊtkun’s`, a Tier-1 stem taking an English possessive in U+2019. All
    three are real Tier-1 forms and every one was invisible here.

    A form with no key is reachable by its exact spelling and by nothing else.
    That is a real limitation of the address, not of the entry, and the index
    says so in the row rather than leaving the column blank.
    """
    return [f for b in native["buckets"].values() for f in b["forms"].values()] \
        + list(native["unkeyable"].values())


@router.get("/lexicon/{key:path}")
def lexicon_card(request: Request, key: str, partial: str = ""):
    """One form's card. The key arrives three ways and all three are real.

    The canonical one is the **handle key** — `/lexicon/Kulu'c^i` — because it is
    ASCII, short and legible where the form itself percent-encodes to twice the
    length. The **exact form** works because that is what `data-key` holds and
    what the reading view's own links send. And `lang:form` works because it is
    what those links used to hold, and a URL somebody has already written down
    should not stop resolving.

    An ambiguous handle key **refuses and names the candidates**. `handle_key`
    is non-injective by design — `marks.py` says the classes collide on purpose
    — so picking one of two forms would be the corpus's own ambiguity resolved
    by an accident of iteration order.
    """
    root = _root(request)
    native = stores.native(root)
    store = stores.lexicon_store(root)

    lang, sep, rest = key.partition(":")
    form = lexicon.norm_form(rest if sep and lang in langs.TIER1 else key)
    if not sep or lang not in langs.TIER1:
        lang = ""

    candidates: list[str] = []
    if form not in store and form not in _all_forms(native):
        # Scanned across every bucket rather than through `by_key`, which holds
        # one bucket per key and so drops the second silently when two buckets
        # share one. That is not hypothetical: `ᵋ` U+1D4B and `ᵉ` U+1D49 both
        # key to `e^` — `marks.py` says the marker classes collide on purpose —
        # and the two need not fold together.
        matched = sorted({lexicon.norm_form(f["form"])
                          for b in native["buckets"].values()
                          for f in b["forms"].values()
                          if f["key"] in (form, key)})
        if len(matched) == 1:
            form = matched[0]
        elif len(matched) > 1:
            candidates = matched

    rec = store.get(form)
    attested = stores.attestations(root).get(form, [])
    # The key's own language counts as one of the readings. It came off a
    # collated page's link, where a collator wrote it; dropping it and reporting
    # "unjudged" would be the card contradicting the URL that opened it.
    # Named `assigned`, not `langs`: this function imports the `langs` module,
    # and a local of that name shadows it three lines later — the same shadow
    # that once hid the `lexicon` module from this file.
    assigned = sorted({la for _r, la in attested} | ({lang} if lang else set()))
    ctx: dict = {
        "key": key,
        "form": form,
        "base": BASE,
        "candidates": candidates,
        # **Known, and the two key shapes are known differently.** A
        # `lang:form` key carries an assertion with it — it is what a collated
        # page's own link holds, and the language in it is a judgement somebody
        # made — so it renders on its own authority, as it always has. A bare
        # form or handle key asserts nothing, so it has to be corroborated by
        # the corpus or the store; rendering an arbitrary string as a headword
        # with an imputed pronunciation under it would be inventing a word.
        "known": bool(lang or rec or attested or form in _all_forms(native)),
        "lang": lang or (assigned[0] if len(assigned) == 1 else ""),
        "langs": [{"code": la, "name": langs.name(la)} for la in assigned],
        "lang_name": langs.name(lang) if lang else None,
        "pages": sorted({r for r, _la in attested}),
        "lines": _printed_lines(native, form),
        "ipa": _ipa_ctx(form) if form else None,
        "rec": rec,
        "note": ui.gloss_html(rec["note"], stores.load(root)) if rec else "",
        "seen_by": sorted(f for f, r in store.items() if r["see"] == form),
    }
    if partial:
        return templates.TemplateResponse(request, "edition/_lexicon.html", ctx)
    # **Where the form shows up, by division** — the same mark an entity's
    # mentions make, and it needs no more warrant here than there: the lexicon's
    # identity *is* the form, so no alias table stands between the word and the
    # pages. There is nothing to be wrong about, and the numbers move only when a
    # page they were read off is corrected.
    #
    # **Out of `gt/ocr/`, and `tei/` only in addition.** This card does not wait
    # on collation and neither may its marks: `attestations` sweeps committed TEI,
    # which is 0 pages today and would have put "nothing places this form" on
    # every card in the lexicon — the store's state reported as the Contents'
    # failure. The keyed corpus is the witness that exists: 1562 forms, each
    # carrying the refs a human keyed it on. The union rather than a choice,
    # because both answer the same question and a collated page that `gt/ocr/`
    # has not reached is a page the form is on all the same.
    #
    # **A count of pages, not of occurrences.** `f["count"]` is per corpus and
    # `refs` is the set of leaves, so a folio contributes 1 and a division's
    # number is how many attested pages lie under it. That is what these stores
    # know: which pages carry the form. `f["count"]` would say how often, over a
    # corpus, which is not a fact about any division.
    rec = _native_form(native, form)
    refs = set(ctx["pages"]) | set(rec["refs"] if rec else ())
    by_folio = _by_folio(dict.fromkeys(refs, 1), root)
    return templates.TemplateResponse(
        request,
        "edition/card.html",
        _ctx(request, partial="edition/_lexicon.html", card_title=form or key,
             toc_panel=_toc_panel(
                 root, [], by_folio,
                 # Only where there were pages to place. A form the corpus does
                 # not attest has not failed to be placed in the Contents — it is
                 # simply not there, which the card's own rows already say, and
                 # blaming the Contents for it would name the wrong cause.
                 absent=("No attestation of this form is placed in the printed "
                         "Contents." if refs else "")),
             **ctx),
    )


def _all_forms(native: dict) -> set[str]:
    return {lexicon.norm_form(f["form"]) for f in _attested_forms(native)}


def _native_form(native: dict, form: str) -> dict | None:
    """This form's record in `gt/ocr/`, by its normalised spelling. `None` where
    the keyed corpus does not attest it."""
    return next((f for f in _attested_forms(native)
                 if lexicon.norm_form(f["form"]) == form), None)


def _printed_lines(native: dict, form: str) -> list[dict]:
    """The lines `gt/ocr/` printed this form on, at most a handful.

    `lexicon lookup`'s reasoning, and the reason a card is worth reading before
    anybody has written a word about the form: `Kuluˊči` alone is a string,
    "south of Kuluˊči Bay" is a place.
    """
    rec = _native_form(native, form)
    return rec["lines"][:8] if rec else []


def _ipa_ctx(form: str) -> dict | None:
    """The imputed pronunciation as data, so the template can escape it.

    `speakable` is decided here because it depends on whether espeak-ng has
    phonemes for the string, which is a question about the host rather than
    about the form.
    """
    r = ipa.impute(form)
    if not r.ipa:
        return None
    phonemes, _dropped = speech.to_espeak(r.ipa)
    return {
        "value": r.ipa,
        "speakable": bool(phonemes),
        "complete": r.complete,
        "unresolved": list(r.unresolved),
        "hedged": list(r.hedged),
    }


def _map_ctx(idents, root: Path, store: dict | None = None, hidden=(),
             dropped=()) -> dict:
    """`map_context` with the server's cached readers handed in.

    One map resolves six or more shapes out of `edition/geo/`, and every one
    of them was a fresh read and JSON decode of a file that had not changed.
    """
    return ui.map_context(
        idents,
        root,
        BASE,
        store=store if store is not None else stores.load(root),
        shape=lambda i: stores.shape(i, root),
        hidden=hidden,
        dropped=dropped,
    )


# ------------------------------------------------------------------- the map


@router.get("/map")
def map_pane(request: Request,
             at: Annotated[list[str], Query()] = (),
             hide: Annotated[list[str], Query()] = (),
             drop: Annotated[list[str], Query()] = (),
             partial: str = ""):
    """The map as a *selection*, which is the shape the pane actually has.

    Repeated `at` rather than one path segment, because adding a place to the
    map is the ordinary act here and the request has to be able to say what is
    already on it. `hide` is the reader's "not this one" — it changes what is
    painted and what the frame may sit on, and it is deliberately not stored:
    nothing about it is written down, so there is nothing to undo but a click.

    `drop` is the reader's "not this one *either*", and it exists because this
    request is answered afresh every time. A `geo:` member joins the selection
    by rule, so leaving it out of `at` says only "it is not here yet" — which the
    rule then acts on, putting a village back the instant somebody clicked it
    away. Dismissal has to be said out loud, exactly as `hide` is.

    `/map/{ident}` stays beside this as the one-place spelling — a permalink and
    what `a.mapref` points at — and goes through the same context.
    """
    refs = [_ident(i) for i in at if i]
    ctx = _map_ctx(refs, _root(request),
                   hidden={_ident(h) for h in hide if h},
                   dropped={_ident(d) for d in drop if d})
    if partial:
        return templates.TemplateResponse(request, "edition/_map.html", ctx)
    title = refs[0] if len(refs) == 1 else f"{len(refs)} place(s)"
    return templates.TemplateResponse(
        request,
        "edition/card.html",
        _ctx(request, partial="edition/_map.html", card_title=f"{title} — map",
             toc_panel=_toc_panel(_root(request), []), **ctx),
    )


@router.get("/map/{ident:path}")
def map_view(request: Request, ident: str, partial: str = ""):
    return map_pane(request, at=[ident], hide=[], drop=[], partial=partial)


@router.get("/atlas")
def atlas(request: Request, at: str = ""):
    root = _root(request)
    store = stores.load(root)
    kids = geo.children(store)
    roots = sorted(
        r["id"]
        for r in store.values()
        if not entities.tree_parent(r) and geo.located(r["id"], store, root)
    )

    def node(ident: str) -> dict:
        rec = store[ident]
        return {
            "id": ident,
            "canonical": rec["canonical"],
            # **The class on every node, not only on the root it hangs under.**
            # The tree nests across classes — a river inside a land region, a
            # village inside a river's basin — so the heading says what the root
            # is and nothing said what any of the hundred names below it were.
            # Read against `mark`, which is a different question: `cls` is what
            # the thing *is*, `mark` is how the atlas knows where it is.
            "cls": rec["class"],
            # Four, since `geo:` absorbed `area:`: a node whose only members are
            # other entities is located by transclusion, and reading it as
            # "framed" would say the atlas computed a box from what lies beneath
            # when in fact somebody wrote down where to look.
            "mark": ("shape" if geo.geo_shapes(rec)
                     else "point" if geo.geo_points(rec)
                     else "transcluded" if geo.geo_refs(rec)
                     else "framed"),
            "selected": ident == at,
            "children": [
                node(k) for k in kids.get(ident, []) if geo.located(k, store, root)
            ],
        }

    # **Grouped by class, because two different relations were sharing one
    # level.** `place` and `water` nest — a tributary inside its trunk, a
    # village inside its basin — and that containment forest is what the atlas
    # was built to walk. A people nests in neither: it has an extent and no
    # parent, so once every ethnicity carried its sprachraum they all landed
    # flat at the top, beside the one `place` root and above the rivers. Worse,
    # a `language:` class then held a second entry per people drawing the very
    # same polygon, which reads as a duplicate when the two sit adjacent with
    # nothing saying why. That class is retired; the flattening it made obvious
    # was never its fault and is still here.
    #
    # So the class is the heading and the containment tree lives under it. The
    # encyclopedia index does the same thing for the same reason; what differs
    # is that this one is still scoped to located subtrees.
    groups = [{"cls": cls,
               "tree": [node(r) for r in roots if store[r]["class"] == cls]}
              for cls in ENTITY_CLASSES]
    ctx = _map_ctx(at, root, store=store) if at in store else {}
    return templates.TemplateResponse(
        request,
        "edition/atlas.html",
        _ctx(
            request,
            groups=[g for g in groups if g["tree"]],
            selected=at in store,
            map=at in store,
            gaps=[v for _k, v in sorted(geo.index(root)["absent"].items())],
            here=f"{len(roots)} root(s) · {len(store)} entities",
            **ctx,
        ),
    )


# ---------------------------------------------------------------- the rest


@router.get("/entities")
def entity_index(request: Request):
    """The encyclopedia, grouped by class and then by containment.

    **`within:` is containment in general, not the geography's.** This page used
    to stop at two levels on the ground that nothing made a people a child of a
    people — which was already false when it was written: `people:maritime-chukchi`
    and `people:reindeer-chukchi` sit under `people:chukchi`, and the fact was
    visible only on the atlas, which will not draw a people. So a class's entries
    nest under their parent where the parent is in the same class.

    **Same class only, and that is the honest cut.** `water:anadyr` is inside
    `place:chukotka`, so following the field across classes would file half the
    rivers under *place* and leave the *water* branch a list of orphans. A child
    whose parent is elsewhere sits at its own class's top level and its card
    names the parent, which is where a cross-class chain is legible.

    **Classes in `ENTITY_CLASSES` order, and every class whether or not it holds
    anything.** The order is authored (person, people, place, water, … ) and says
    something alphabetical order would not; and four of the eleven are empty
    today, so a list of only the populated ones would quietly show half the
    vocabulary. That is the silence the atlas's `absent` rows exist to break.

    Proposed-first is preserved from the flat listing, now within each level:
    nothing links an unaudited entry by rule, so it is what wants reading first.
    """
    root = _root(request)
    store = stores.load(root)
    rep = stores.check(root)
    # **`kin_parent`, not the atlas's edge**: this page asks what a thing
    # belongs to, so `part-of:` leads. `people:naukans` is `within: place:naukan`
    # and `part-of: people:yupik`; under the atlas's edge it hangs from a
    # village, which is correct on a map and leaves `people:yupik` showing no
    # subgroups at all on a page about peoples.
    kids = entities.kin_children(store)

    def rank(ident: str) -> tuple:
        return (store[ident]["status"] != "proposed", ident)

    def node(ident: str, cls: str) -> dict:
        return {"rec": store[ident],
                "kids": [node(k, cls) for k in sorted(kids.get(ident, []), key=rank)
                         if store[k]["class"] == cls]}

    groups = []
    for cls in ENTITY_CLASSES:
        here = [r["id"] for r in store.values() if r["class"] == cls]
        # A parent in another class does not nest, so it is a top-level row of
        # its own class rather than one this page silently drops.
        tops = [i for i in here if not entities.kin_parent(store[i], store)]
        groups.append({"cls": cls, "count": len(here),
                       "nodes": [node(i, cls) for i in sorted(tops, key=rank)]})
    return templates.TemplateResponse(
        request,
        "edition/entities.html",
        _ctx(
            request,
            groups=groups,
            problems=rep["errors"],
            here=f"{rep['entities']} entries · {rep['proposed']} awaiting audit",
        ),
    )


@router.get("/search")
def search(request: Request, q: str = ""):
    root = _root(request)
    hits, ents = [], []
    if q:
        store = stores.load(root)
        for ident, rec in sorted(store.items()):
            hay = [rec["canonical"], ident, rec["gloss"]] + [
                t["form"] for t in rec["aliases"]
            ]
            if any(q.lower() in h.lower() for h in hay):
                ents.append(rec)
        # Whatever this sitting can read, it can find: a page reachable at its own
        # URL and invisible to search is a worse lie than an unread page in the
        # results, and each hit carries its rank.
        for ref in _listing(request):
            path, rank = tei_html.page_source(ref, root)
            if path is None:
                continue
            doc = stores.render(path, root)
            if not doc["ok"]:
                continue
            # Tags stripped from already-escaped HTML, so what comes out carries
            # `&amp;` where the page had `&`. It is unescaped once here rather
            # than re-emitted as markup, which is what the old version did.
            text = ui.strip_markup(doc["html"])
            for m in re.finditer(re.escape(q), text, re.I):
                a, b = max(0, m.start() - 60), m.end() + 60
                hits.append(
                    {
                        "ref": ref,
                        "rank": rank,
                        "before": text[a : m.start()],
                        "match": m.group(),
                        "after": text[m.end() : b],
                    }
                )
                if len(hits) > 200:
                    break
    return templates.TemplateResponse(
        request,
        "edition/search.html",
        _ctx(
            request,
            q=q,
            hits=hits,
            ents=ents,
            here=f"{len(hits)} in the text, {len(ents)} in the encyclopedia",
        ),
    )


@router.get("/tts/{spoken:path}")
def tts(spoken: str):
    """A pure function of the string in the URL, which is what makes it cacheable
    on the string alone. It deliberately does not check that the IPA is one this
    edition imputed — there is nothing to protect, since `to_espeak` builds the
    command from its own table and nothing from here reaches a shell."""
    try:
        wav = speech.wav_for(spoken)
    except speech.Unspeakable as e:
        return Response(str(e), status_code=400, media_type="text/plain")
    return Response(wav, media_type="audio/wav")


class Ratify(BaseModel):
    id: str


class NewEntity(BaseModel):
    """The fields `edition_ui._new` reads. `aliases` was absent once and that is
    not cosmetic: Pydantic drops what it does not declare, so an entry created
    without it went in carrying the placeholder alias row — a record that exists,
    looks complete and asserts nothing."""

    id: str = ""
    canonical: str = ""
    aliases: list[str] = []
    gloss: str = ""
    form: str = ""


@router.post("/ratify")
@fetched
def ratify(request: Request, body: Ratify):
    """`fetched`, like every other editor's writes. `_ratify` *returns*
    `{"error": …}` for a domain refusal, which worked unmarked; what did not is
    anything that **raises** inside it — a `relink` failure, an `OSError`, a
    `Malformed` from the reload — which came back as an HTML traceback that
    `ratify.js` then tried to parse."""
    return ui._ratify(body.id, _root(request))


@router.post("/entity/new")
@fetched
def new_entity(request: Request, body: NewEntity):
    return ui._new(body.model_dump(), _root(request))


@router.get("/static/{name}")
def site_mark(name: str):
    """The site marks the old `/static/` route served. Kept as a redirect rather
    than dropped: `edition/entities/` records and any bookmark still name the old path,
    and a 404 here would show as a missing icon nobody would trace."""
    return RedirectResponse(f"/static/site/{name}", status_code=308)


register(Editor(name="edition", port=ui.PORT, home="/", router=router))
