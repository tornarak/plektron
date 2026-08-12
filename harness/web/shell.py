"""The routes that belong to no editor: stop, session handoff, port homing.

Small on purpose. Everything here is about the *process* rather than about any
page — which of the four tools a port belongs to, how a second invocation hands
its work to the server already running, and how the page says it is finished.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from . import EDITORS, port_editor

router = APIRouter()


class Session(BaseModel):
    """What one invocation of an editor verb knows that the stores do not.

    Deliberately open-shaped (`dict`): an itinerary, a queue and a walk have
    nothing in common, and inventing a union of them here would put every
    editor's vocabulary in a file that is supposed to know about none of them.
    What is declared is the envelope, which is the part this route is
    responsible for.
    """

    session: dict = Field(default_factory=dict)
    open_at: str = ""


@router.post("/session/{editor}")
def set_session(editor: str, body: Session, request: Request) -> dict:
    """Hand a running server the work a second invocation was started for.

    This is what keeps two editors usable at once now that one process owns all
    their ports. Before this route, `zones edit` and `edition serve` were two
    processes on two ports and simply coexisted; a single process binding both
    would have made the second invocation fail on a held port — a regression on
    a workflow that works today, which is why this landed with the shell rather
    than after it.
    """
    if editor not in EDITORS:
        # Naming the known set, because the failure is almost always a typo or a
        # verb whose editor has not been ported yet, and both are answered by the
        # list.
        raise HTTPException(404, f"no editor {editor!r} — have "
                                 f"{', '.join(sorted(EDITORS)) or '(none)'}")
    request.app.state.sessions.set(editor, body.session)
    ed = EDITORS[editor]
    # `open_at` is editor-relative, as it is in `url_for` — the prefix is added
    # here rather than by the caller so there is one place that knows it. Sent
    # back unprefixed, a handoff opened the bare root and lost its ref.
    return {"ok": True, "editor": editor, "port": ed.port,
            "open": f"/{ed.name}{body.open_at or ed.home}"}


@router.post("/stop")
def stop(request: Request) -> dict:
    """Shut the server down from the page.

    `should_exit` rather than anything blocking: uvicorn's loop notices the flag
    on its next pass and unwinds itself, so the response goes out first. The old
    shell had to spawn a thread here, because the call that stopped the server
    blocked until the loop it was running in had exited.
    """
    server = request.app.state.server
    if server is not None:
        server.should_exit = True
    return {"ok": True}


@router.get("/")
def home(request: Request) -> RedirectResponse:
    """Send a bare `/` to whichever editor owns the port it arrived on.

    ASGI records the receiving socket in `scope["server"]`, so one app can tell
    `:8732/` from `:8734/` and land each on its own tool. That resolution is
    `port_editor`'s, shared with the middleware that refuses another editor's
    routes on this port — this decides only where the front door opens, and the
    two must agree about which door that is.
    """
    port = (request.scope.get("server") or (None, None))[1]
    owner = port_editor(request.app, port)
    if owner is not None:
        return RedirectResponse(f"/{owner}{EDITORS[owner].home}")

    # Nothing matched the port: fall back to the editor this process was started
    # for. It is the honest answer rather than a guess — the verb named one, and
    # a test client has no meaningful port at all.
    started_for = getattr(request.app.state, "editor", "")
    if started_for in EDITORS:
        return RedirectResponse(f"/{started_for}{EDITORS[started_for].home}")
    if len(EDITORS) == 1:
        ed = next(iter(EDITORS.values()))
        return RedirectResponse(f"/{ed.name}{ed.home}")
    raise HTTPException(404, f"port {port} belongs to no editor — try one of "
                             + ", ".join(f"/{n}" for n in sorted(EDITORS)))
