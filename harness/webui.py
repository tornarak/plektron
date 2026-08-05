"""The HTTP shell the browser editors share.

Three editors now stand up a local server over the same page rasters — `ocr
review` (adjudicate a reading), `zones edit` (region geometry), `ocr edit` (line
geometry) — and all three want the same half-dozen behaviours: bind loopback
only, say nothing per request, answer a failure on the page instead of resetting
the connection, hand a PNG straight off disk, and stop when the page says it is
finished. Two copies of that were a coincidence; the third is a module.

**Loopback only, and 404 on anything unrouted.** These serve unpublished
editorial work and have no business being reachable. That is a property of the
shell rather than of any one editor, which is the point of putting it here: a
fourth editor cannot forget it.

**A failed request renders its own traceback.** The alternative — letting it
reach `socketserver` — prints to stderr and resets the connection, so the human
gets a browser error naming nothing and the reason lives in a file they have to
be told about, since these are always started backgrounded. This is a loopback
tool with one user, so the traceback goes on the page. `_sent` is what
distinguishes "nothing went out, render a page" from "we are mid-response and
the only honest thing left is to drop the connection".

What stays with each editor is its HTML, its routes and what a save means. The
shell knows nothing about zones, lines or decisions.
"""
from __future__ import annotations

import html as _html
import json as _json
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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


class EditorHandler(BaseHTTPRequestHandler):
    """Base handler: subclass and implement `get` and `post`.

    Both default to 404, so an editor that routes nothing serves nothing rather
    than inheriting somebody else's endpoints.
    """

    # Named in the error page's title and in the traceback line on stderr.
    editor = "editor"

    # GET paths the page **fetches** rather than navigates to. Their failures are
    # reported as `{"error": …}` with a 500, because the client parses the body as
    # JSON and an HTML traceback would raise inside the `fetch` — throwing away the
    # very reason the page was trying to show. Navigated routes get the traceback
    # page instead, which is what a human staring at a blank tab needs.
    fetched: tuple[str, ...] = ()

    def log_message(self, format: str, *args) -> None:
        """Silence the per-request log — one line per save is enough, GETs are
        noise. The signature matches the base class rather than `*a`: an override
        that narrows is a real incompatibility even when the body ignores
        everything."""

    def send_response(self, *a, **kw):
        # Track that a status line went out; `do_GET`'s error path reads it.
        self._sent = True
        super().send_response(*a, **kw)

    # --- sending ----------------------------------------------------------

    def send_bytes(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, body: str, code: int = 200) -> None:
        self.send_bytes(code, "text/html; charset=utf-8", body.encode("utf-8"))

    def send_json(self, obj, code: int = 200) -> None:
        self.send_bytes(code, "application/json",
                        _json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def send_png(self, path: Path, missing: str = "") -> None:
        """A raster straight off disk.

        Not a data URI like the line crops: a 2824x3897 sheet base64'd into every
        render costs megabytes on a page that gets reloaded constantly, to carry
        something opened occasionally and in another tab.
        """
        try:
            body = Path(path).read_bytes()
        except FileNotFoundError:
            # `scans/` is derived and gitignored, so absence is the ordinary state
            # of a fresh clone rather than a broken link. Say which.
            self.send_error(404, missing or f"no image at {path}")
            return
        self.send_bytes(200, "image/png", body)

    # --- reading ----------------------------------------------------------

    def body_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return _json.loads(self.rfile.read(n) or b"{}") or {}

    # --- lifecycle --------------------------------------------------------

    def stop_from_page(self) -> None:
        """Shut down from another thread: `shutdown()` blocks until the serve loop
        exits, and the serve loop is what is running this handler, so calling it
        inline would deadlock."""
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    # --- dispatch ---------------------------------------------------------

    def do_GET(self):
        self._sent = False
        try:
            self.get()
        except Exception as e:
            if getattr(self, "_sent", False):
                raise  # mid-response; a second status line would be worse
            tb = traceback.format_exc()
            print(f"500 {self.path}\n{tb}", file=sys.stderr)
            if self.path.split("?")[0] in self.fetched:
                self.send_json({"error": str(e)}, 500)
            else:
                self.send_html(error_html(self.editor, self.path, tb), 500)

    def do_POST(self):
        # A POST is a `fetch` whose response the page displays, so a failure is
        # reported as JSON rather than as a traceback page — the shape the client
        # already knows how to show. Never a blank failure either way.
        self._sent = False
        try:
            self.post()
        except Exception as e:
            if getattr(self, "_sent", False):
                raise
            print(f"500 {self.path}\n{traceback.format_exc()}", file=sys.stderr)
            self.send_json({"error": str(e)}, 500)

    def get(self) -> None:
        self.send_error(404)

    def post(self) -> None:
        self.send_error(404)


def run(handler_cls: type, port: int, url: str, banner: list[str],
        open_browser: bool = True) -> None:
    """Bind, announce, serve until the page or a ctrl-c says stop.

    **`banner` is printed line-buffered**, and that is not cosmetic: `serve` is
    long-running and almost always backgrounded with stdout redirected to a file,
    where Python block-buffers — so the URL, the one line the caller is waiting
    for, sat in an 8 KB buffer until the process exited. A server that has not
    printed its address is indistinguishable from one that failed to start, and
    these never exit on their own.
    """
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):  # not a real stream (captured in tests)
        pass
    for line in banner:
        print(line)
    if open_browser:
        webbrowser.open(url)
    try:
        # 0.1 rather than the 0.5 default: `shutdown()` blocks until the loop next
        # wakes, so the default is a flat half-second between the Done button and
        # the process exiting — and the process exiting is the signal that the
        # sitting is finished. It is also the whole per-test cost of the session
        # suite, which stands up and tears down a real server per test.
        srv.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print("\nstopped")
    else:
        print("done — server stopped from the page")
    finally:
        srv.server_close()
