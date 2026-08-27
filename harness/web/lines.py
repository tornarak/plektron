"""Routes for the line-correction editor, `harness ocr edit`.

The judgement, the geometry and the writes are still `harness/lines_ui.py`'s —
`page_state`, `page_row`, `save_payload`. What moved here is the part that was
never about lines: which URL means what, and what a response looks like.

Mounted at `/lines`, so every URL below is relative to that. The client is told
the prefix through the state blob rather than the script hardcoding it, because
`lines.js` is a cached static file served from one place and the mount point is
the server's fact.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import lines_config
from .. import lines_ui as ui
from .. import zones as zn
from ..lines import write_blot
from ..refs import norm_ref
from . import Editor, register, templates
from .errors import fetched
from .files import send_file

BASE = "/lines"
router = APIRouter()


def _ref(raw: str) -> str:
    """A ref, or a 404. Matched against its own form rather than sanitized, so
    nothing here depends on having thought of every escape — the same guard the
    old handler used, and the reason `/page/{ref}.png` cannot walk out of
    `scans/`."""
    try:
        return norm_ref(raw)
    except ValueError:
        raise HTTPException(404, f"{raw!r} is not a PP-NNN ref") from None


def _session(request: Request) -> dict:
    return request.app.state.sessions.get("lines")


def _root(request: Request) -> Path:
    return Path(request.app.state.root)


def _store(request: Request) -> str:
    """The store this session was opened on. `run_edit` always sets it; a session
    without one is a server bug, and reading `""` in its place would build a path
    into the repo root and blame the page."""
    store = _session(request).get("store")
    if not store:
        raise HTTPException(500, "no store in this session — a lines session is "
                                 "opened on gt/ocr or mz/ocr by `harness ocr edit`")
    return store


class Save(BaseModel):
    """One sitting's output: boxes drawn, and bands ruled not-type.

    Declared rather than dug out of a dict, so a payload missing `ref` is a 422
    naming the field instead of a `ValueError` three frames into the store
    writer. `lines` and `ink_exempt` stay open-shaped — their members are
    geometry the store validates, and restating that here would be a second
    place the shape lives.
    """

    ref: str
    lines: list[dict] = Field(default_factory=list)
    ink_exempt: list[dict] = Field(default_factory=list)
    #: "I mean to delete this page's corrections", sent only after the editor has
    #: asked. An empty `lines` alone is refused by the store, because that is what
    #: an absent key and a stray payload also look like — one of them destroyed
    #: `1-097`'s only record of its folio.
    withdraw: bool = False


@router.get("/")
def page(request: Request, ref: str = ""):
    s = _session(request)
    r = _ref(ref or s.get("start", ""))
    root = _root(request)
    store = _store(request)
    cfg = lines_config.load_config(root)
    st = ui.page_state(r, root, store)

    it = s.get("itinerary") or []
    i = it.index(st["ref"]) if st["ref"] in it else -1
    st["prev"] = it[i - 1] if i > 0 else ""
    st["next"] = it[i + 1] if 0 <= i < len(it) - 1 else ""
    st["base"] = BASE

    live = [b for b in st["bands"] if not b["exempted"]]
    return templates.TemplateResponse(request, "lines/page.html", {
        "st": st,
        "cfg": {k: v for k, v in cfg.items() if not k.startswith("_")},
        "keys": key_rows(cfg),
        "no_zone": sum(1 for b in live if not b["zone"]),
        "itinerary_name": s.get("itinerary_name") or "",
        "position": f"{i + 1} of {len(it)}" if i >= 0 else "",
        "base": BASE,
    })


# What each bound action is called on the page. Held beside the dispatch rather
# than in the config: the config says which key, this says what to call it, and a
# human rebinding a key should not have to restate its name in English.
ACTION_NAMES = ui.ACTION_NAMES


def key_rows(cfg: dict) -> list[dict]:
    """The panel's rows, as data.

    Generated from the bindings, because written out by hand it was a second
    place the keys lived, free to disagree with what the editor actually binds —
    a help panel that lies about the tool is worse than none. Data rather than
    markup so the template owns the markup and this owns the pairing.
    """
    keys = {k: v for k, v in cfg["actions"].items() if not k.startswith("_")}
    shown = {"ArrowLeft": "←", "ArrowRight": "→"}
    return [{"name": name, "label": label,
             "key": shown.get(keys.get(name), keys.get(name, ""))}
            for name, label in ACTION_NAMES.items()]


@router.get("/list")
def worklist(request: Request, ref: str = ""):
    s = _session(request)
    walk = s.get("itinerary") or [s.get("start", "")]
    cur = ref or ""
    return templates.TemplateResponse(request, "lines/list.html", {
        "walk": walk, "label": s.get("itinerary_name") or "", "cur": cur,
        "back": cur or (walk[0] if walk else ""), "base": BASE,
    })


@router.get("/row")
@fetched
def row(request: Request, ref: str = ""):
    """One page's counts. Marked `fetched`: the list drives this from JS and
    parses the body as JSON, so a failure has to arrive as JSON too — an HTML
    traceback would raise inside the `fetch` and throw away the reason."""
    return ui.page_row(_ref(ref), _root(request), _store(request))


@router.get("/layers.css")
def layers_css(request: Request):
    """The layer colours, generated from `data/lines_config.json`.

    A route rather than a static file because it is derived from a config the
    human edits, and a route rather than an inline `<style>` because it is still
    an asset — it gets a validator like any other, keyed on the config's own
    contents so an edit invalidates it and nothing else does.
    """
    root = _root(request)
    cfg = lines_config.load_config(root)
    css = lines_config.layer_css(cfg)
    from .cache import digest

    etag = f'"{digest(css.encode("utf-8")).hex()}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(css, media_type="text/css", headers={"ETag": etag})


@router.get("/page/{ref}.png")
def scan(request: Request, ref: str):
    """The raster, straight off disk.

    `FileResponse` rather than reading it into memory: it streams, and it sets
    the validators that make the second navigation to a page free. `scans/` is
    derived and gitignored, so absence is the ordinary state of a fresh clone
    rather than a broken link — say which.
    """
    return send_file(request, zn.scan_for(_ref(ref), _root(request)),
                     missing="scans/ is derived and not in git")


@router.get("/blot/{ref}.png")
def blot(request: Request, ref: str):
    """The blotted view, rendered on demand with both ruling layers painted.

    This is the "what is left unsettled" view, which is exactly what the corpus
    sweep's blot must *not* be — hence its own cache directory rather than
    sharing `scans/w-blotted/`.
    """
    root = _root(request)
    res = write_blot(_ref(ref), root / "scans" / ui.BLOT_CACHE,
                     root, _store(request), exemptions=True)
    return send_file(request, Path(res["path"]))


@router.post("/save")
@fetched
def save(request: Request, body: Save):
    # `exclude_unset`, so a key the client did not send does not arrive as a
    # default the store reads as an instruction — `save_payload` asks
    # `"ink_exempt" in payload` for exactly that reason.
    res = ui.save_payload(body.model_dump(exclude_unset=True), _root(request),
                          _store(request))
    print(f"saved {res['path']}: {res['lines']} correction(s), "
          f"{len(res['live_bands'])} band(s) left")
    return res


@router.post("/done")
@fetched
def done(request: Request):
    server = request.app.state.server
    if server is not None:
        server.should_exit = True
    return {}


register(Editor(name="lines", port=ui.PORT, home="/", router=router))
