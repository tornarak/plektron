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


CHROME_CSS = """
:root{--bg:#f6f5f3;--fg:#1c1b19;--dim:#6b675f;--line:#d8d4cc;--accent:#2e86ab;
      --warn:#a8620a;--warnbg:rgba(0.9, 0.4, 0.4, 0.4);--err:#a4232b;--errbg:#fbeceb}
@media(prefers-color-scheme:dark){:root{--bg:#16161a;--fg:#e8e6e1;--dim:#9a958c;
      --line:#33323a;--accent:#6ab6d8;--warn:#e0a250;--warnbg:#2f2517;
      --err:#e08b8b;--errbg:#2e1a1a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:13px/1.45 ui-sans-serif,system-ui,sans-serif}
#bar{position:fixed;top:0;left:0;right:0;height:38px;display:flex;gap:14px;
     align-items:center;padding:0 12px;background:var(--bg);
     border-bottom:1px solid var(--line);z-index:20;white-space:nowrap;
     overflow-x:auto}
#bar b{font-weight:600}
.pill{padding:1px 8px;border-radius:10px;border:1px solid var(--line);
      font-size:12px}
.pill.on{background:var(--accent);border-color:var(--accent);color:#fff}
.pill.off{background:var(--warn);border-color:var(--warn);color:#fff}
/* The store selector reads as one control: three adjacent pills, clickable, the
   selected one lit. `—` means that store holds nothing for this page, which is an
   answer and is why the pill still draws rather than being hidden. */
.pill.store{cursor:pointer;font-variant-numeric:tabular-nums}
.pill.store+.pill.store{margin-left:-1px}
#cur{font-weight:600}
#swatch{display:inline-block;width:11px;height:11px;border-radius:2px;
        vertical-align:-1px;margin-right:5px}
#target{color:var(--dim);font-size:12px}
#target.sel{color:var(--fg);font-weight:600}
#msg{margin-left:auto;color:var(--dim)}
#msg.bad{color:var(--err);font-weight:600}
#msg.ok{color:var(--accent)}
/* One scroll container for both axes: the edge-hover autoscroll needs a single
   element whose scrollTop it can drive, and the page is now sized to the text
   column rather than to the leaf, so it is routinely taller than the view. */
#wrap{position:fixed;top:38px;left:0;right:250px;bottom:0;overflow:auto;padding:10px}
/* The stage is a window onto the page's inked band, not the whole leaf: the top
   and bottom of a scan are blank paper, and scrolling through them is time spent
   on nothing. The image is positioned inside it and clipped. */
#stage{position:relative;line-height:0;margin:0 auto;overflow:hidden;
       box-shadow:0 1px 8px rgba(0,0,0,.18)}
#stage img{position:absolute;left:0;display:block;width:100%;height:auto;
           image-rendering:-webkit-optimize-contrast}
@media(prefers-color-scheme:dark){#stage img{filter:invert(1) hue-rotate(180deg)}}
#ov{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}
#panel{position:fixed;right:0;top:38px;width:250px;bottom:0;overflow-y:auto;
       border-left:1px solid var(--line);background:var(--bg);padding:10px 12px;
       z-index:15}
#panel h4{margin:14px 0 6px;font-size:11px;letter-spacing:.06em;
          text-transform:uppercase;color:var(--dim);font-weight:600}
#panel h4:first-child{margin-top:0}
.key{display:flex;justify-content:space-between;gap:8px;padding:1px 0;
     font-size:12px}
.key kbd{font:11px ui-monospace,monospace;background:var(--line);
         border-radius:3px;padding:0 5px}
.tk{display:flex;align-items:center;gap:6px;padding:2px 4px;border-radius:4px;
    cursor:pointer}
.tk:hover{background:var(--line)}
.tk.sel{background:var(--line);font-weight:600}
.tk i{width:11px;height:11px;border-radius:2px;flex:none}
.tk span{flex:1;font-style:normal}
.tk em{font-style:normal;font-size:10px;color:var(--dim);border:1px solid var(--line);
       border-radius:3px;padding:0 4px;cursor:help}
#flags{padding:6px 0;font-size:12px;color:var(--dim)}
#issues{position:fixed;left:0;bottom:0;max-width:calc(100% - 250px);z-index:18}
.iss{padding:6px 12px;border-top:1px solid var(--line);font-size:12px}
.iss.w{background:var(--warnbg);color:var(--warn)}
.iss.e{background:var(--errbg);color:var(--err);font-weight:600}
.iss.x{opacity:.62;font-style:italic}
button{font:inherit;padding:2px 10px;border:1px solid var(--line);border-radius:5px;
       background:var(--bg);color:var(--fg);cursor:pointer}
button:hover{background:var(--line)}
"""
"""The chrome both editors wear.

Shared so that a human moving between `zones edit` and `ocr edit` is looking at
the same tool with a different subject, rather than at two tools. Everything here
is about a page under a cursor — the top bar and its pills, the scrolling stage
with the raster positioned inside it, the SVG overlay, the right-hand panel, the
issue strip along the bottom — and none of it knows what is being drawn.

Two rules it encodes that are easy to lose by writing a second sheet from
scratch. The stage is **one scroll container for both axes**, because the
edge-hover autoscroll needs a single element whose scrollTop it can drive. And
the raster is inverted under `prefers-color-scheme: dark` rather than left glaring
white, which is the only way a long sitting is bearable.
"""


LIST_CSS = """
table{border-collapse:collapse;width:100%;font-size:13px}
th{position:sticky;top:0;background:var(--bg);text-align:left;font-weight:600;
   font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);
   padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:5px 10px;border-bottom:1px solid var(--line)}
tr:hover td{background:var(--line)}
tr.here td{background:var(--line);font-weight:600}
td.ref a{color:var(--fg);text-decoration:none;font-weight:600}
td.ref a:hover{text-decoration:underline}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;
     margin-right:7px;vertical-align:-1px}
.s-todo{background:transparent;border:1px solid var(--dim)}
/* Hollow like `todo`, because it is one — nothing is keyed here. Coloured, because
   work waiting on a decision is different work from a blank page. */
.s-proposed{background:transparent;border:1px solid var(--warn)}
.s-ok{background:#3f8f5f}
.s-warn{background:var(--warn)}
.s-err{background:var(--err)}
td.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--dim)}
th.num{text-align:right}
/* A machine count reads as the fainter of a pair on purpose: the two columns are
   not equals, one being a tracked human ruling and the other a proposal. */
td.num.dim{opacity:.6}
td.detail{color:var(--dim);font-size:12px}
td.pick,th.pick{width:1%;padding-right:0}
td.pick input,th.pick input{cursor:pointer;margin:0}
#filters{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{display:flex;align-items:center;gap:6px;padding:2px 9px;border-radius:11px;
      border:1px solid var(--line);font-size:12px;cursor:pointer;user-select:none}
.chip:hover{background:var(--line)}
.chip.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.chip i{display:inline-block;width:9px;height:9px;border-radius:2px}
.chip.on i{outline:1px solid var(--bg)}
#shown{color:var(--dim);font-size:12px;margin-left:4px}
#head{position:sticky;top:0;background:var(--bg);padding:14px 16px 10px;
      border-bottom:1px solid var(--line);z-index:5}
#head h1{margin:0 0 4px;font-size:15px;display:flex;align-items:center;gap:10px}
#head p{margin:0;color:var(--dim);font-size:12px}
#wrapl{padding:0 16px 40px}
"""
"""The list view both editors wear.

A sweep's question is *which page*, never how many, so each editor can reach a
table of its work-list in one keystroke and leave it in one click. The states are
deliberately the same four dots in both — `todo`, `proposed`, `warn`, `err` — so
a colour means one thing across the pass rather than one thing per tool.

**`unknown` is a state and looks like one.** A blank cell reads as "clean" where
it means "nothing has measured this page since it changed", and that is the same
silence every detector here exists to break. Each editor draws `?` and makes
going to get the answer an explicit button, because it is the only slow thing a
list can do.
"""


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
