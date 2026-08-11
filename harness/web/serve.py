"""Binding, announcing, and joining a server that is already up.

Two entry points. `serve()` is what a verb calls when it is the one starting the
process; `handoff()` is what it calls *first*, to find out whether it needs to.
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from . import Sessions, create_app, load_editors

HOST = "127.0.0.1"


def bind(port: int) -> socket.socket:
    """One listening socket on loopback.

    **Loopback only, and it is the shell's job rather than any editor's** —
    these serve unpublished editorial work and have no business being reachable.
    Put here so a fifth editor cannot forget it.

    `SO_REUSEADDR` so a restart inside the TIME_WAIT window is not refused;
    deliberately *not* `SO_REUSEPORT`, which would let two servers silently share
    a port and answer alternate requests from different stores.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, port))
    s.listen(128)
    s.set_inheritable(True)
    return s


def url_for(editor: str, path: str = "", port: int | None = None) -> str:
    """`port` overrides the registered default.

    It has to be overridable, and the reason is a bug this shape already had: a
    `--port` on the command line changed which socket was bound but not the URL
    printed and opened, so the banner named a port nothing was listening on.
    """
    ed = load_editors()[editor]
    return f"http://{HOST}:{port or ed.port}/{ed.name}{path or ed.home}"


def handoff(editor: str, session: dict, open_at: str = "",
            port: int | None = None) -> str | None:
    """Give a running server this invocation's work; return the URL, or None.

    Returns None when nothing is listening, which is the caller's signal to start
    the process itself. Anything else — a connection that opens but does not
    answer, an answer that is not ours — returns None too and lets the bind
    fail with a real error, because a port held by something unknown is not a
    server we should be handing sessions to.
    """
    ed = load_editors().get(editor)
    if ed is None:
        return None
    # The port actually asked for, not the registered default — a `--port` that
    # moved the bind but not the probe would look for the running server in the
    # wrong place and always conclude there wasn't one.
    at = port or ed.port
    body = json.dumps({"session": session, "open_at": open_at}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{HOST}:{at}/session/{editor}", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            got = json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if not got.get("ok"):
        return None
    return f"http://{HOST}:{at}{got.get('open') or ''}"


def serve(editor: str, root: Path = Path("."), sessions: Sessions | None = None,
          banner: list[str] | None = None, open_browser: bool = True,
          open_at: str = "", ports: dict[str, int] | None = None,
          drafts: bool = False) -> None:
    """Bind every registered editor's port and serve them all from one process.

    **`banner` is printed line-buffered**, and that is not cosmetic: these are
    long-running and almost always backgrounded with stdout redirected to a
    file, where Python block-buffers — so the URL, the one line the caller is
    waiting for, sat in a buffer until the process exited. A server that has not
    printed its address is indistinguishable from one that failed to start, and
    these never exit on their own.
    """
    sessions = sessions or Sessions(root=Path(root))
    app = create_app(root, sessions, editor=editor, drafts=drafts)

    # The registered editors' ports, which is all four now that every editor is
    # here. Derived from the registry rather than written as a literal, so a port
    # we do not serve is never grabbed — the property that let the four move over
    # one at a time.
    want = {name: (ports or {}).get(name, ed.port)
            for name, ed in load_editors().items()}
    socks = []
    try:
        for name, port in sorted(want.items(), key=lambda kv: kv[1]):
            try:
                socks.append(bind(port))
            except OSError as e:
                for s in socks:
                    s.close()
                raise OSError(f"port {port} ({name}) is in use — another sitting "
                              f"may already be running: {e}") from None

        try:
            sys.stdout.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):  # not a real stream (captured in tests)
            pass
        app.state.ports = dict(want)
        here = url_for(editor, open_at, port=want.get(editor))
        for line in banner or [f"{editor}: {here}"]:
            print(line)

        config = uvicorn.Config(app, log_level="warning", access_log=False,
                                lifespan="on")
        server = uvicorn.Server(config)
        # `POST /stop` reaches for this to set `should_exit`.
        app.state.server = server

        if open_browser:
            webbrowser.open(here)
        try:
            server.run(sockets=socks)
        except KeyboardInterrupt:
            print("\nstopped")
        else:
            print("done — server stopped from the page")
    finally:
        for s in socks:
            s.close()
