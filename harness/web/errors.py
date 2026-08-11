"""What a failed request looks like, and why it has two shapes.

**A failed request renders its own traceback.** The alternative — letting it
reach the server — resets the connection, so the human gets a browser error
naming nothing and the reason lives in a file they have to be told about, since
these are always started backgrounded. This is a loopback tool with one user, so
the traceback goes on the page.

**A route the page *fetches* gets `{"error": …}` instead**, because the client
parses the body as JSON and an HTML traceback would raise inside the `fetch` —
throwing away the very reason the page was trying to show. This split is the
kind of thing that regresses silently: both arms return 500, so the wrong one
still *looks* like a failure being reported, and the only symptom is a reason
that never reaches the human.

The old shell compared `self.path` against a tuple of strings. Here the mark
sits on the endpoint function, and the handler reads it off the route that
actually matched — so a route renamed or re-pathed cannot drift away from its
own error shape.
"""
from __future__ import annotations

import html as _html
import sys
import traceback

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

_MARK = "__web_fetched__"


def fetched[F](fn: F) -> F:
    """Mark an endpoint as one the page `fetch`es rather than navigates to."""
    setattr(fn, _MARK, True)
    return fn


def is_fetched(request: Request) -> bool:
    return bool(getattr(request.scope.get("endpoint"), _MARK, False))


def error_html(title: str, path: str, tb: str) -> str:
    """The page a failed request renders, traceback included.

    Someone meeting this is looking at a tool that stopped working mid-pass, and
    the only useful thing it can say is what broke. Withholding the traceback
    behind a tidy apology would send them to the server's stderr, which is a file
    they have to be told about first.
    """
    return (
        f"<!doctype html><meta charset=utf-8><title>{_html.escape(title)}: error</title>"
        "<style>body{font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;"
        "max-width:60rem;margin:3rem auto;padding:0 1.5rem;color:#333}"
        "h1{font-size:1.1rem;color:#a3121a}"
        "pre{background:#fbf7f7;border:1px solid #e6cdcd;border-left:3px solid #a3121a;"
        "padding:.8rem 1rem;overflow-x:auto;font-size:12px;line-height:1.45}"
        "p{color:#555}code{background:#f2f2f2;padding:.1rem .3rem;border-radius:2px}"
        "</style>"
        f"<h1>{_html.escape(title)} failed on <code>{_html.escape(path)}</code></h1>"
        "<p>This request raised. Nothing was written — the server is still up, so a "
        "reload after fixing the cause will work. The same traceback is on the "
        "server's stderr.</p>"
        f"<pre>{_html.escape(tb)}</pre>")


def install(app, editor: str = "harness") -> None:
    """Register the handler. `editor` names the tool in the page's title."""

    async def on_error(request: Request, exc: Exception):
        tb = "".join(traceback.format_exception(exc))
        # Still printed to stderr as well as rendered: the page is for whoever is
        # looking, the log is for whoever comes back to a server left running.
        print(f"500 {request.url.path}\n{tb}", file=sys.stderr)
        if is_fetched(request):
            return JSONResponse({"error": str(exc)}, status_code=500)
        return HTMLResponse(error_html(editor, request.url.path, tb), status_code=500)

    # Registered against `Exception` rather than a status code, so it catches what
    # an endpoint raised rather than what Starlette turned that into.
    app.add_exception_handler(Exception, on_error)
