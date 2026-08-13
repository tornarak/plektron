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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from .. import edition_ui as ui
from .. import entities, geo, ipa, langs, lexicon, speech, tei_html
from .. import figures as F
from ..entities import ENTITY_CLASSES, alias_index, split_id
from . import Editor, register, stores, templates
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
        _ctx(request, refs=refs, signed=signed, drafts=_drafts(request), here=here),
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
    `gt/fig-img/` wins over the machine crop** — one resolver, shared with every
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


def _figure_state(ref: str, root, doc: dict, size) -> dict:
    """`figs` and `crops` for one page: which pictures hang on which `<figure>`.

    **This is the join the renderer refuses to do**, and it is here because here
    is where both keys are in hand — the TEI's bytes, which `stores.render` is
    cached on, and the three figure stores, which `stores.fig_layout` is cached
    on. A `<figure>` in the HTML says only what the page says; the boxes arrive
    beside it and are re-derived whenever their stores move.

    `figs` drives the inline picture: the built crops out of `scans/fig-crops/`,
    plus the float side and width the box implies. Several crops per figure is
    the ordinary case, not an edge one — the store spells `1-276`'s fig. 140 in
    two boxes, and they stack under its one caption.

    **A figure opens in the lightbox, not in the stack**, so nothing here builds
    a `crop_style` for one. The stack is for what a reader has to fetch and then
    read beside the text; a picture is already on the page and the only thing
    wanted from it is size. `crops` stays in the payload for the scan card, which
    is a different feature and still keys into it.
    """
    lay = stores.fig_layout(ref, root)
    rows = F.resolve_figures(doc.get("figures") or [], lay["figures"])
    figs = []
    for r in rows:
        f = r["figure"]
        if f is None:
            figs.append({"i": r["i"], "n": r["n"], "why": r["why"], "crops": []})
            continue
        figs.append({
            "i": r["i"], "n": r["n"], "why": "",
            "crops": [f"{BASE}/fig/{ref}/{k}.png"
                      for k in (F.zone_suffix(z) for z in f["zone_ids"])],
            "side": f.get("side", "full"),
            "width": f.get("width_frac", 1.0),
        })
    return {"figs": figs, "crops": {}}


def _exempt_page(request: Request, ref: str, root):
    """A page a human ruled not a text page, shown as what it actually is.

    Two shapes and one rule to pick between them: **if the figure store has boxes
    on this page, show those pictures in succession; if it has none, show the
    whole scan.** That is the entire classification, and deliberately so. Sorting
    these pages into plates, foldouts, maps, half-titles and blanks would mean
    deciding what a page *is* from evidence no store carries — on this book the
    plate/text-figure split is recoverable only from prose in a `@note`, and on
    the next book it may not be recoverable at all. Whether a human drew figure
    boxes here is a fact, and it is the only one this needs.

    A page with no boxes therefore shows the scan rather than nothing, which is
    also the honest answer for a blank leaf: the reader sees the leaf and can see
    that it is blank. Nothing here asserts that it is.
    """
    figs = [f for f in stores.fig_layout(ref, root)["figures"]
            if f["box"] is not None]
    plates = [{
        "n": f["n"],
        "caption": f["caption"],
        "crops": [f"{BASE}/fig/{ref}/{F.zone_suffix(z)}.png"
                  for z in f["zone_ids"]],
    } for f in F.in_printed_order(figs)]

    refs = _listing(request)
    i = refs.index(ref) if ref in refs else -1
    here = f"scan {ref} · " + (f"{len(plates)} figure(s)" if plates
                               else "not a text page")
    return templates.TemplateResponse(
        request,
        "edition/exempt.html",
        _ctx(
            request,
            ref=ref,
            plates=plates,
            here=here,
            state={"base": BASE, "ref": ref,
                   "size": ui._raster_size(ref, root), "figs": [], "crops": {}},
            prev=refs[i - 1] if i > 0 else "",
            next=refs[i + 1] if 0 <= i < len(refs) - 1 else "",
        ),
    )


@router.get("/page/{ref}")
def page(request: Request, ref: str):
    root = _root(request)
    if not ui.REF_OK.match(ref):
        raise HTTPException(404, f"{ref!r} is not a PP-NNN ref")
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
    doc = stores.render(path)
    refs = _listing(request)
    i = refs.index(ref) if ref in refs else -1
    here = f"scan {ref}" + (f" · folio {doc['folio']}" if doc.get("folio") else "")
    size = ui._raster_size(ref, root)
    state = {"base": BASE, "ref": ref, "size": size,
             **_figure_state(ref, root, doc, size)}
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
            prev=refs[i - 1] if i > 0 else "",
            next=refs[i + 1] if 0 <= i < len(refs) - 1 else "",
        ),
    )


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
    return {"rows": rows[:MENTIONS], "pages": len(rows),
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
        "contested": [{"id": c, "canonical": store[c]["canonical"]} for c in contested],
        "located": bool(geo.located(ident, store, root)),
        "props": ui.property_rows(rec, store, root),
        "mentions": _mentions(ident, refs, root),
    }


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
    return templates.TemplateResponse(
        request,
        "edition/card.html",
        _ctx(
            request,
            partial="edition/_entity.html",
            card_title=rec["canonical"] if rec else ident,
            **ctx,
        ),
    )


@router.get("/lexicon")
def lexicon_index(request: Request):
    """Every attested Tier-1 form, grouped by the language a collator assigned.

    **Grouped by language, and mostly *unassigned*, which is the honest
    picture.** A form's language is a judgement made during collation, and
    collation has reached one page — so 18 forms carry a code and the rest of
    the corpus sits in the last branch. Showing it that way makes the index
    double as the collation worklist, where a tree over only the assigned forms
    would show an encouraging empty list.

    Every one of the seven codes appears whether or not it holds anything, for
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
    committed TEI where a collator has judged one, the note from `lexicon/`
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
    return templates.TemplateResponse(
        request,
        "edition/card.html",
        _ctx(request, partial="edition/_lexicon.html", card_title=form or key, **ctx),
    )


def _all_forms(native: dict) -> set[str]:
    return {lexicon.norm_form(f["form"]) for f in _attested_forms(native)}


def _printed_lines(native: dict, form: str) -> list[dict]:
    """The lines `gt/ocr/` printed this form on, at most a handful.

    `lexicon lookup`'s reasoning, and the reason a card is worth reading before
    anybody has written a word about the form: `Kuluˊči` alone is a string,
    "south of Kuluˊči Bay" is a place.
    """
    for f in _attested_forms(native):
        if lexicon.norm_form(f["form"]) == form:
            return f["lines"][:8]
    return []


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


def _map_ctx(ident: str, root: Path, store: dict | None = None) -> dict:
    """`map_context` with the server's cached readers handed in.

    One map resolves six or more shapes out of `data/geo/`, and every one
    of them was a fresh read and JSON decode of a file that had not changed.
    """
    return ui.map_context(
        ident,
        root,
        BASE,
        store=store if store is not None else stores.load(root),
        shape=lambda i: stores.shape(i, root),
    )


# ------------------------------------------------------------------- the map


@router.get("/map/{ident:path}")
def map_view(request: Request, ident: str, partial: str = ""):
    ctx = _map_ctx(_ident(ident), _root(request))
    if partial:
        return templates.TemplateResponse(request, "edition/_map.html", ctx)
    return templates.TemplateResponse(
        request,
        "edition/card.html",
        _ctx(request, partial="edition/_map.html", card_title=f"{ident} — map", **ctx),
    )


@router.get("/atlas")
def atlas(request: Request, at: str = ""):
    root = _root(request)
    store = stores.load(root)
    kids = geo.children(store)
    roots = sorted(
        r["id"]
        for r in store.values()
        if not r["within"] and geo.located(r["id"], store, root)
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
            "mark": "shape" if rec["area"] else "point" if rec["geo"] else "framed",
            "selected": ident == at,
            "children": [
                node(k) for k in kids.get(ident, []) if geo.located(k, store, root)
            ],
        }

    # **Grouped by class, because two different relations were sharing one
    # level.** `place` and `water` nest — a tributary inside its trunk, a
    # village inside its basin — and that containment forest is what the atlas
    # was built to walk. A people or a language nests in neither: it has an
    # extent and no parent, so once every ethnicity carried its sprachraum all
    # nine of each landed flat at the top, beside the one `place` root and above
    # the rivers. Worse, they landed in pairs drawing the same polygon —
    # `people:koryak` and `language:koryak` both point at `langarea:kory1246`,
    # which the store allows on purpose and which reads as a duplicate when the
    # two sit adjacent with nothing saying why.
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
    kids = entities.children(store)

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
        tops = [i for i in here
                if not store[i]["within"]
                or store[store[i]["within"]]["class"] != cls]
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
            doc = stores.render(path)
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
def ratify(request: Request, body: Ratify):
    return ui._ratify(body.id, _root(request))


@router.post("/entity/new")
def new_entity(request: Request, body: NewEntity):
    return ui._new(body.model_dump(), _root(request))


@router.get("/static/{name}")
def site_mark(name: str):
    """The site marks the old `/static/` route served. Kept as a redirect rather
    than dropped: `entities/` records and any bookmark still name the old path,
    and a 404 here would show as a missing icon nobody would trace."""
    return RedirectResponse(f"/static/site/{name}", status_code=308)


register(Editor(name="edition", port=ui.PORT, home="/", router=router))
