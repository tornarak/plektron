"""Routes for the page-segmentation editor, `harness zones edit`.

The geometry, the stores and the writes stay in `harness/zones_ui.py`. What moved
here is the routing, and what moved beside this file is the markup — plus **68 KB
of JavaScript**, which was interpolated into every page on the one editor here
that is navigated page-to-page with the arrow keys.

This was the last editor off the stdlib shell, and that module went with it.
"""
from __future__ import annotations

import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import zones as zn
from .. import zones_config as zc
from .. import zones_ui as ui
from ..context import norm_ref
from . import Editor, register, templates
from .errors import fetched
from .files import send_file

BASE = "/zones"
PORT = 8732
router = APIRouter()

# **The resident segmenter, behind a lock.** Loading it costs ~5 s, so it is kept
# between calls — a bulk run that paid that per page is the clunkiness the
# in-browser loop replaces. The lock is new: under the old thread-per-connection
# handler two concurrent `/predict` posts could both find the slot empty and load
# it twice, which is ~10 s and two copies on a GPU with one card.
_SEGMENTER: list = [None]
_SEG_LOCK = threading.Lock()


def _root(request: Request) -> Path:
    return Path(request.app.state.root)


def _session(request: Request) -> dict:
    return request.app.state.sessions.get("zones")


def _cfg(request: Request) -> dict:
    return zc.load_config(_root(request))


def _ref(raw: str) -> str:
    try:
        return norm_ref(raw)
    except ValueError:
        raise HTTPException(404, f"{raw!r} is not a PP-NNN ref") from None


@router.get("/")
def page(request: Request, ref: str = "", nudge: int = 0, store: str = "zones"):
    s = _session(request)
    ctx = ui.page_context(_ref(ref or s.get("start", "")), _root(request),
                          _cfg(request), nudge,
                          s.get("itinerary") or [], s.get("itinerary_name") or "",
                          store, base=BASE)
    return templates.TemplateResponse(request, "zones/page.html", ctx)


@router.get("/list")
def worklist(request: Request, ref: str = "", scope: str = "stores"):
    s = _session(request)
    ctx = ui.list_context(_root(request), _cfg(request),
                          s.get("itinerary"), s.get("itinerary_name") or "",
                          ref, scope, base=BASE)
    return templates.TemplateResponse(request, "zones/list.html", ctx)


@router.get("/ink")
@fetched
def ink(request: Request, ref: str = ""):
    """One page's uncovered-ink verdict. Marked `fetched`: the list drives this
    from JS and parses the body as JSON, so a failure has to arrive as JSON."""
    return ui.ink_state(_ref(ref), _root(request), _cfg(request))


@router.get("/page/{ref}.png")
def scan(request: Request, ref: str):
    return send_file(request, zn.scan_for(_ref(ref), _root(request)),
                     missing="scans/ is derived and not in git")


class Save(BaseModel):
    """One sitting's output, named as the editor sends it.

    **Every field here is a claim about what `static/js/zones.js` posts**, and the
    version this replaced was written from memory rather than from that file: it
    declared `exempt` a bool where the client sends the list of exempted order
    rules (a flat 422, so `Enter` saved nothing), `anchor` where the client sends
    `nudge`, and `figures` where it sends `figs`. Pydantic drops unknown fields
    silently, so the last two would not have raised — a save that appeared to work
    and quietly discarded the column nudge and the whole figure track.

    **`figs` defaults to `None`, and that is load-bearing.** `save_payload` treats
    the *presence* of the key as "the figure track was touched": no key means the
    figure store is not read, not rewritten, not stamped, because `zones blot` keys
    its rasters off `gt/fig/`'s mtimes and rewriting 252 identical files during
    ordinary zone keying would stale every training raster. A `list[dict] = []`
    default would put the key in every dump — and on a figure-less page the store's
    own refusal ("an empty file would say the opposite") would then block the save
    outright. `exclude_unset=True` at the call site is the other half.
    """

    ref: str
    zones: list[dict] = []
    split: str = ""
    exempt: list[str] = []
    nudge: int = 0
    ink_exempt: list[dict] = []
    # --- the figure track, sent only when it was edited ----------------------
    figs: list[dict] | None = None
    fig_ids: str = ""
    fig_exempt: list[str] = []


class Predict(BaseModel):
    ref: str
    force: bool = False
    single: bool = False


class Delete(BaseModel):
    ref: str


@router.post("/save")
@fetched
def save(request: Request, body: Save):
    # `exclude_unset`, so a field the client did not send does not arrive as a
    # default that means something else. `save_payload` asks `"figs" not in
    # payload` to decide whether the figure store is touched at all, and every
    # other field it reads is a `.get` with its own fallback — so what the editor
    # sent is exactly what it sees.
    res = ui.save_payload(body.model_dump(exclude_unset=True),
                          _root(request), _cfg(request))
    note = f" · {len(res['errors'])} error(s)" if res["errors"] else ""
    print(f"saved {res['path']}: {res['zones']} zones "
          f"[{res['labels'] or 'none'}] {res['split']}{note}")
    return res


@router.post("/predict")
@fetched
def predict(request: Request, body: Predict):
    """One page per call, the model resident between them. The client drives the
    loop so it can show progress, exactly as the ink runner does."""
    root = _root(request)
    r = _ref(body.ref)
    # The same rule the CLI sweep uses, asked here so a bulk run through the
    # browser and one through the terminal cannot disagree about what they left
    # alone.
    why = zn.predict_skip(r, root, body.force, single=body.single)
    if why:
        return {"ref": r, "skipped": why}
    with _SEG_LOCK:
        if _SEGMENTER[0] is None:
            _SEGMENTER[0] = zn.load_segmenter(zn.DEFAULT_MODEL, root)
    net, sha = _SEGMENTER[0]
    res = zn.predict_dp(r, root, net=net, sha=sha,
                        model_path=zn.DEFAULT_MODEL, cfg=_cfg(request))
    print(f"segmented {res['ref']}: {res['zones']} zones -> mz/zones/")
    return res


@router.post("/delete")
@fetched
def delete(request: Request, body: Delete):
    """The only route that removes keyed work. Confirmed on the page and
    journalled here; `.prev` keeps it one deep either way."""
    res = zn.delete_zones(body.ref, _root(request), commit=True)
    print(f"deleted {res['path']}: was {res['zones']} zones "
          f"[{res['split'] or 'unmarked'}]")
    return res


@router.post("/done")
def done(request: Request):
    server = request.app.state.server
    if server is not None:
        server.should_exit = True
    return {}


register(Editor(name="zones", port=PORT, home="/", router=router))
