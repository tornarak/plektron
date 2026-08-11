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

**One process, several ports.** `uvicorn.Server.serve(sockets=[...])` takes a
list of pre-bound sockets, and ASGI puts the receiving port in
`scope["server"]`, so the four editors' ports are four doors into one app rather
than four servers. That is what lets them share a template tree, a stylesheet
and a store cache, and lets a page in one link to a page in another. The ports
are unchanged from when they were separate servers, so nothing at the command
line moved.

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

    errors.install(app, editor)
    return app
