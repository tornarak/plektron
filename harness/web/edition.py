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
from .. import geo, ipa, speech, tei_html
from ..entities import ENTITY_CLASSES, split_id, trigger_index
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
    root = _root(request)
    return stores.readable(root) if _drafts(request) else stores.collated(root)


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


@router.get("/page/{ref}")
def page(request: Request, ref: str):
    root = _root(request)
    if not ui.REF_OK.match(ref):
        raise HTTPException(404, f"{ref!r} is not a PP-NNN ref")
    path, rank = tei_html.page_source(ref, root)
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
    state = {"base": BASE, "ref": ref, "size": ui._raster_size(ref, root), "crops": {}}
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


def _entity_ctx(ident: str, root: Path) -> dict:
    store = stores.load(root)
    rec = store.get(ident)
    if rec is None:
        return {"rec": None, "ident": ident, "base": BASE}
    idx = trigger_index(store)
    contested = sorted(
        {
            c["id"]
            for t in rec["triggers"]
            for c in idx.get(t["form"], [])
            if c["id"] != ident
        }
    )
    triggers = [
        {**t, "note_html": ui.inline_html(t["note"], store)} for t in rec["triggers"]
    ]
    return {
        "rec": {**rec, "triggers": triggers},
        "ident": ident,
        "base": BASE,
        "gloss": ui.gloss_html(rec["gloss"], store),
        "links": [ui.link_html(ln) for ln in rec["links"]],
        "contested": [{"id": c, "canonical": store[c]["canonical"]} for c in contested],
        "located": bool(geo.located(ident, store, root)),
        "props": ui.property_rows(rec, store, root),
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
    ctx = _entity_ctx(_ident(ident), root)
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


@router.get("/lexicon/{key:path}")
def lexicon(request: Request, key: str, partial: str = ""):
    lang, _, form = key.partition(":")
    root = _root(request)
    ctx: dict = {
        "key": key,
        "lang": lang,
        "form": form,
        "base": BASE,
        "lang_name": ui.LANG_NAMES.get(lang) if form else None,
        "pages": [],
        "ipa": None,
    }
    if ctx["lang_name"]:
        ctx["pages"] = ui._attestations(lang, form, root)
        ctx["ipa"] = _ipa_ctx(form)
    if partial:
        return templates.TemplateResponse(request, "edition/_lexicon.html", ctx)
    return templates.TemplateResponse(
        request,
        "edition/card.html",
        _ctx(request, partial="edition/_lexicon.html", card_title=form or key, **ctx),
    )


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
            "mark": "shape" if rec["area"] else "point" if rec["geo"] else "framed",
            "selected": ident == at,
            "children": [
                node(k) for k in kids.get(ident, []) if geo.located(k, store, root)
            ],
        }

    ctx = _map_ctx(at, root, store=store) if at in store else {}
    return templates.TemplateResponse(
        request,
        "edition/atlas.html",
        _ctx(
            request,
            tree=[node(r) for r in roots],
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
    """The encyclopedia, grouped by class.

    **Two levels and no deeper.** `within:` exists and the atlas draws the forest
    over it, but it is the *geography* tree — nothing yet makes a people a child
    of a people — so this groups by class and stops rather than pretending to a
    hierarchy the store does not hold.

    **Classes in `ENTITY_CLASSES` order, and every class whether or not it holds
    anything.** The order is authored (person, people, place, water, … ) and says
    something alphabetical order would not; and four of the eleven are empty
    today, so a list of only the populated ones would quietly show half the
    vocabulary. That is the silence the atlas's `absent` rows exist to break.

    Proposed-first is preserved from the flat listing, now within each class:
    nothing links an unaudited entry by rule, so it is what wants reading first.
    """
    root = _root(request)
    store = stores.load(root)
    rep = stores.check(root)
    groups = [
        {
            "cls": cls,
            "rows": sorted(
                (r for r in store.values() if r["class"] == cls),
                key=lambda r: (r["status"] != "proposed", r["id"]),
            ),
        }
        for cls in ENTITY_CLASSES
    ]
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
                t["form"] for t in rec["triggers"]
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
    """The four fields `edition_ui._new` reads. `triggers` and `since` were absent
    and are not cosmetic: Pydantic drops what it does not declare, so an entry
    created with either would have been written with the placeholder trigger row
    and no `since:` — the record would exist, look complete, and assert nothing."""

    id: str = ""
    canonical: str = ""
    triggers: list[str] = []
    since: str = ""
    gloss: str = ""
    since: str = ""
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
