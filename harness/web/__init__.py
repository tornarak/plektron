"""The web layer: one app, one process, one socket per editor.

Four browser tools live here — the reading view (`edition serve`) and the three
editors (`zones edit`, `ocr edit`, `ocr review`). They were four hand-rolled
`http.server` handlers with their HTML in f-strings and their CSS and JS in
Python string constants; they are one FastAPI app with templates, static files
and declared request bodies.

**Endpoints are declared `def`, not `async def`.** Every handler body here
blocks: lxml parses a page, PIL opens a raster, the zones segmenter runs a torch
forward pass. Starlette runs a *sync* endpoint in the anyio worker threadpool,
which is the same thread-per-request behaviour the old `ThreadingHTTPServer`
gave — so the bodies came across unchanged. Declaring one `async def` and then
doing any of that inside it stalls the event loop for the whole process, every
editor at once. `async def` is for something genuinely awaiting, and there is
almost nothing here that is.

**One process, several ports, and each port answers for one editor only.**
`uvicorn.Server.serve(sockets=[...])` takes a list of pre-bound sockets, so the
four editors run in one app rather than four servers — which is what lets them
share a template tree, a stylesheet, a store cache and a `Sessions`, and what
lets a second invocation hand its work to the process already running.

ASGI puts the *receiving* socket in `scope["server"]`, and `_port_editor` reads
it: a request for another editor's prefix is refused, naming the port that owns
it. That was not true for most of this layer's life — every route answered on
every port, so `:8732` served `/lines/save` exactly as `:8733` did, and a stray
request or a stale tab could write through a tool nobody had opened. The ports
carried no meaning; now they do.

What stays reachable everywhere is what belongs to the process rather than to a
page: `/static`, and the shell's `/`, `/session/{editor}` and `/stop`. Handoff
posts to the *target* editor's port and would break without that, which is why
the shell router is mounted unprefixed and exempt.

The ports are unchanged from when they were separate servers, so nothing at the
command line moved.

`EDITORS` is the registry, and `serve()` binds exactly the ports of the editors
registered in it. That was load-bearing while the port was in progress — a
half-ported tree ran both halves side by side — and it stays because it is also
what makes a single-editor test app possible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import errors

HERE = Path(__file__).parent
STATIC = HERE / "static"
TEMPLATES = HERE / "templates"

# `autoescape` is on by default for `.html`, and it is the reason this layer is
# safer than the strings it replaces: escaping stopped being a discipline the
# author has to remember at each interpolation. The old code escaped
# `canonical` in one function and interpolated it raw in the next.
templates = Jinja2Templates(directory=str(TEMPLATES))


@dataclass(frozen=True)
class Editor:
    """One tool: its port, where its bare `/` should land, and its routes."""

    name: str
    port: int
    home: str
    router: Any = None


# Registered as each editor ports. The ports are the ones the separate servers
# used, so muscle memory and any bookmark still work:
#   8731 review · 8732 zones · 8733 lines (ocr edit) · 8734 edition
EDITORS: dict[str, Editor] = {}


def register(editor: Editor) -> Editor:
    EDITORS[editor.name] = editor
    return editor


def load_editors() -> dict[str, Editor]:
    """Import the editor modules, which is what fills `EDITORS`.

    **Everything that reads the registry has to call this first**, and that is
    not a style point: `EDITORS` is empty until the modules are imported, and an
    empty registry does not fail — `handoff` reads it, finds no such editor, and
    returns "nothing is listening", so every invocation would start its own
    server and none would ever join another. A silent wrong answer, from a
    missing import.

    Imported here rather than at module scope because each editor module imports
    this one for `register` and `templates`. Repeat calls are free; Python caches
    the module.
    """
    from . import edition, lines, review, zones  # noqa: F401 — registration

    return EDITORS


#: Paths that belong to the process rather than to any one editor, and so answer
#: on every port. `/static` because each editor needs its assets whichever door
#: it was reached through; the shell's three because `handoff` posts
#: `/session/{editor}` to the *target* editor's port — refusing it there would
#: leave a second invocation unable to join, which is the regression the shell
#: router was written to prevent.
SHARED_PREFIXES = ("/static", "/session", "/stop")


def port_editor(app, port: int | None) -> str | None:
    """Which editor owns the port a request arrived on, or None.

    One resolution, two callers: `shell.home` sends a bare `/` to the right front
    door, and the middleware refuses everything that is not that editor's. They
    were one function's worth of logic in one place and are now read by two, so
    they are written once — two copies would drift, and the failure would be a
    port that homes to one tool and serves another.

    `app.state.ports` first, because it holds what was actually bound: `--port`
    moves one editor's socket and the registered default then names the wrong
    door. The registry is the fallback for an app nobody called `serve()` on.

    Returns None rather than guessing. The callers want different things from
    that — `home` falls back to the editor the process was started for, the
    middleware falls back to letting the request through — and neither should be
    decided here.
    """
    if port is not None:
        bound = getattr(app.state, "ports", None) or {}
        for name, at in bound.items():
            if at == port and name in EDITORS:
                return name
        for ed in EDITORS.values():
            if ed.port == port:
                return ed.name
    return None


@dataclass
class Sessions:
    """Per-invocation state, the part that is not a store.

    `zones edit` is started with an itinerary, `ocr review` with a queue, `ocr
    edit` with a walk. Under one server these cannot be closure variables of four
    separate `serve()` calls, so they live here, one slot per editor, and a
    second invocation can hand its own over to the process already running.
    """

    root: Path = field(default_factory=lambda: Path("."))
    by_editor: dict[str, dict] = field(default_factory=dict)

    def get(self, name: str) -> dict:
        return self.by_editor.get(name, {})

    def set(self, name: str, session: dict) -> None:
        self.by_editor[name] = session


def create_app(root: Path = Path("."), sessions: Sessions | None = None,
               editor: str = "harness", drafts: bool = False) -> FastAPI:
    """The whole app. `editor` only names the tool on the error page.

    `drafts` opens the reading view onto `mz/tei/` as well as `tei/`. Off by
    default and passed in rather than read from the store, because whether an
    unread page belongs in front of a reader is the operator's call and not a
    fact about the repo — the same server is a proof reader's workstation with it
    on and an end-user preview with it off.
    """
    app = FastAPI(
        title="machine-press",
        # No docs endpoints: this is a loopback editorial tool, not an API with
        # consumers, and `/docs` would be one more unrouted-looking path that
        # answers.
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    app.state.root = Path(root)
    app.state.sessions = sessions or Sessions(root=Path(root))
    app.state.server = None  # set by serve(), read by POST /stop
    # Which editor this process was started for, and which ports it actually
    # bound. `GET /` needs both to send a bare root to the right front door.
    app.state.editor = editor
    app.state.ports = {}
    app.state.drafts = drafts

    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    load_editors()
    from .shell import router as shell_router

    app.include_router(shell_router)
    for ed in EDITORS.values():
        if ed.router is not None:
            app.include_router(ed.router, prefix=f"/{ed.name}")

    _install_port_scope(app)
    errors.install(app, editor)
    return app


def _install_port_scope(app: FastAPI) -> None:
    """Refuse a request for an editor that does not own the port it arrived on.

    **The routers are all mounted and that is deliberate.** One app is what lets
    the four share a `Sessions`, a store cache and a template tree, and what lets
    `handoff` reach a running process on another editor's port; four apps would
    mean four `uvicorn.Server`s and lose all of it. So the isolation is enforced
    per request, where the receiving socket is known, rather than by mounting
    less.

    **Falls open when the port names no editor**, and that is the one judgement
    here worth stating. A `TestClient` has no meaningful port, and so does any
    caller that built an app without `serve()`; refusing those would break every
    suite in the tree to guard against a request that cannot arrive, since the
    isolation only means anything once real sockets are bound. `state.editor` is
    consulted first — a single-editor app knows what it is for even without a
    port — and only a process that can name neither lets everything through.
    """
    @app.middleware("http")
    async def _scope(request, call_next):
        path = request.url.path
        if not path.startswith("/") or path == "/" \
                or any(path == p or path.startswith(p + "/")
                       for p in SHARED_PREFIXES):
            return await call_next(request)

        first = path.split("/", 2)[1]
        if first not in EDITORS:
            return await call_next(request)      # unrouted; let 404 handle it

        port = (request.scope.get("server") or (None, None))[1]
        owner = port_editor(app, port) or getattr(app.state, "editor", "")
        if owner not in EDITORS or owner == first:
            return await call_next(request)

        ed = EDITORS[first]
        at = (getattr(app.state, "ports", None) or {}).get(first, ed.port)
        return JSONResponse(
            {"error": f"{first} is served on port {at}, not {port}. Every editor "
                      f"answers on its own port only — this one is {owner}'s."},
            status_code=404)
