"""One review server over several pages, and the properties that keep them apart.

`ocr review` grew a queue because the reading half of the ground-truth pass fans
out to an agent per page while the adjudicating half stays one human — so standing
a server up and tearing it down per page made the human wait on the tooling between
pages.

What is tested here is mostly the *separation*, not the convenience. A session over
several refs is one server, but it is never one document: each page's fields, saves
and decisions belong to exactly one ref, and the payload says which. The failure
being designed against is this file's oldest one — 1-073's text arriving in 1-151's
fields — and a shared server is a new way to reach it, since now a single process
holds two pages' worth of state at once.

The other property under test is that **adjudicated-ness lives on disk**, not in the
serving process. `decision.json` existing is the whole definition, which is what lets
a reload, a second tab or a re-run of the command agree with each other.
"""
from __future__ import annotations

import json
import socket
import threading
import urllib.request
from pathlib import Path

import pytest

from harness.review import decisions_path, render_queue_html, serve
from harness.tests.conftest import write_scan

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _page(root: Path, ref: str, n: int = 2) -> None:
    """A predicted page plus a proposal — the least that renders a review."""
    write_scan(root, ref)
    lines = "".join(
        f'<TextLine ID="mz_{ref}_l{i}" HPOS="700" VPOS="{600 + i * 80}" '
        f'WIDTH="1400" HEIGHT="60" '
        f'BASELINE="700 {655 + i * 80} 2100 {655 + i * 80}">'
        f'<Shape><Polygon POINTS="700 {600 + i * 80} 2100 {660 + i * 80}"/></Shape>'
        f'<String CONTENT="machine {ref} {i}" HPOS="700" VPOS="{600 + i * 80}" '
        f'WIDTH="1400" HEIGHT="60"/></TextLine>'
        for i in range(1, n + 1))
    p = root / "mz" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout>'
        # WIDTH/HEIGHT are not decoration: the crop scaler takes the raster:ALTO
        # ratio per axis off them, because 300 dpi is not a clean x2 of 150 on any
        # page in this corpus.
        f'<Page WIDTH="2824" HEIGHT="3897">'
        f'<PrintSpace HPOS="400" VPOS="400" WIDTH="2000" HEIGHT="3000">'
        f'<TextBlock ID="mz_{ref}_r1" TAGREFS="T1">{lines}</TextBlock>'
        "</PrintSpace></Page></Layout>"
        '<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags></alto>',
        encoding="utf-8")
    prop = root / "review" / ref / "proposal.json"
    prop.parent.mkdir(parents=True, exist_ok=True)
    prop.write_text(json.dumps({
        "ref": ref,
        "lines": {str(i): {"text": f"human {ref} {i}"} for i in range(n)},
    }), encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Session:
    """A served session, driven over real HTTP.

    Real requests rather than calling the handler directly: the routing, the
    payload shape and the shutdown-on-last-page are the contract, and all three
    live in the wiring rather than in a function that could be called in isolation.
    """

    def __init__(self, refs, root):
        self.refs, self.root = list(dict.fromkeys(refs)), root
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(
            target=serve, args=(refs, "mz/ocr", root, self.port), daemon=True)

    def __enter__(self):
        self.thread.start()
        for _ in range(200):  # bind is not instantaneous; poll rather than sleep
            try:
                self.get("/")
                return self
            except Exception:
                threading.Event().wait(0.02)
        raise RuntimeError("server never came up")

    def __exit__(self, *exc):
        # Stop it the way the page does, rather than abandoning the thread and
        # waiting out a join timeout: mark everything adjudicated on disk, then one
        # Done finds nothing left and shuts down. Leaving daemon threads holding
        # ports across a suite is how a later test fails for an unrelated reason.
        if self.thread.is_alive():
            try:
                for r in self.refs:
                    p = decisions_path(r, self.root)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    if not p.exists():
                        p.write_text(json.dumps({"lines": {}}), encoding="utf-8")
                self.post("/done", {"ref": self.refs[-1]})
            except Exception:
                pass
        self.thread.join(timeout=5)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return r.read().decode("utf-8")

    def post(self, path, payload):
        req = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read() or b"{}")


@pytest.fixture(autouse=True)
def _no_browser(monkeypatch):
    """`serve` opens a browser. A test suite must not."""
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: True)


@pytest.fixture
def two(tmp_path):
    _page(tmp_path, "2-046")
    _page(tmp_path, "2-047")
    return tmp_path


# --- the page itself -------------------------------------------------------

def test_one_page_renders_no_strip(tmp_path):
    """A queue of one is not a queue.

    The single-page render is the overwhelmingly common case and it must be
    untouched by this feature — a nav bar over one page is furniture announcing
    somewhere else to be when there is nowhere.
    """
    _page(tmp_path, "2-046")
    html = render_queue_html("2-046", "mz/ocr", tmp_path)
    assert "class=q>" not in html
    assert "this session:" not in html
    # And passing a one-entry queue is the same thing, not a different thing.
    one = render_queue_html("2-046", "mz/ocr", tmp_path,
                            queue=[{"ref": "2-046", "done": False}])
    assert "this session:" not in one


def test_the_strip_marks_current_and_done_distinctly(two):
    """Three states, three renderings — current, done, waiting.

    `done` is drawn differently from `waiting` because the reviewer's question at
    the strip is "what is left", and a queue that showed both the same would
    answer it wrong in the direction of doing work twice.
    """
    html = render_queue_html("2-046", "mz/ocr", two, queue=[
        {"ref": "2-046", "done": False}, {"ref": "2-047", "done": True}])
    assert "<span class=cur>2-046</span>" in html
    assert "href='/p/2-047'" in html
    assert "class='done'" in html
    assert "1/2 adjudicated" in html


def test_the_done_button_says_whether_it_ends_the_session(two):
    """"Finish this page" and "finish the session" stop being the same act."""
    more = render_queue_html("2-046", "mz/ocr", two, queue=[
        {"ref": "2-046", "done": False}, {"ref": "2-047", "done": False}])
    assert "Done → next (1 left)" in more

    last = render_queue_html("2-046", "mz/ocr", two, queue=[
        {"ref": "2-046", "done": False}, {"ref": "2-047", "done": True}])
    assert "Done → next" not in last
    assert ">Done</button>" in last


def test_the_page_carries_its_own_ref_for_every_write(two):
    """`REF` is embedded so saves name their page instead of relying on the
    server holding a 'current page' the browser could contradict."""
    html = render_queue_html("2-046", "mz/ocr", two)
    assert 'REF="2-046"' in html
    assert "{ref:REF,lines:collect()}" in html


# --- the session -----------------------------------------------------------

def test_bare_root_opens_the_first_unadjudicated_page(two):
    """`/` means "wherever this session is up to"."""
    decisions_path("2-046", two).parent.mkdir(parents=True, exist_ok=True)
    decisions_path("2-046", two).write_text(
        json.dumps({"lines": {}}), encoding="utf-8")
    with Session(["2-046", "2-047"], two) as s:
        assert "<h1>2-047" in s.get("/")


def test_a_ref_outside_the_session_is_not_servable(two):
    """Not a security boundary — it is loopback — but a page nobody queued would
    render a review whose Done button belongs to some other session."""
    with Session(["2-046"], two) as s:
        with pytest.raises(Exception) as e:
            s.get("/p/2-047")
        assert "404" in str(e.value)


def test_a_save_writes_the_page_it_names_and_no_other(two):
    """The separation that matters. Two pages are live in one process; a save for
    2-047 must not be able to land in 2-046's file, whatever order things happen
    in — this is the session-restore incident's shape, arriving by a new route."""
    with Session(["2-046", "2-047"], two) as s:
        s.get("/p/2-047")
        s.post("/save", {"ref": "2-047",
                         "lines": {"0": {"text": "keyed into 2-047"}}})
        assert decisions_path("2-047", two).exists()
        assert not decisions_path("2-046", two).exists(), \
            "a save named 2-047 and touched 2-046"
        got = json.loads(decisions_path("2-047", two).read_text())
        assert got["lines"]["0"]["text"] == "keyed into 2-047"


def test_a_save_naming_no_page_is_refused_rather_than_guessed(two):
    """There is deliberately no fallback to a 'current page'. A payload that does
    not say which page it is about is the exact input a guess would corrupt."""
    with Session(["2-046", "2-047"], two) as s:
        with pytest.raises(Exception) as e:
            s.post("/save", {"lines": {"0": {"text": "nowhere"}}})
        assert "500" in str(e.value)
        assert not decisions_path("2-046", two).exists()
        assert not decisions_path("2-047", two).exists()


def test_done_advances_and_only_the_last_one_stops_the_server(two):
    """The chaining, end to end: Done on a page with work left hands back the next
    ref and leaves the server up; Done on the last returns none and stops it."""
    with Session(["2-046", "2-047"], two) as s:
        s.post("/save", {"ref": "2-046", "lines": {"0": {"text": "a"}}})
        assert s.post("/done", {"ref": "2-046"})["next"] == "2-047"
        assert s.thread.is_alive(), "a session with a page left must stay up"
        # Still serving, and now showing 2-046 as done.
        assert "class='done'" in s.get("/p/2-047")

        s.post("/save", {"ref": "2-047", "lines": {"0": {"text": "b"}}})
        assert s.post("/done", {"ref": "2-047"})["next"] is None
        s.thread.join(timeout=5)
        assert not s.thread.is_alive(), "the last Done must stop the server"


def test_adjudicatedness_comes_from_the_disk_not_the_process(two):
    """A decision file written by something other than this server still counts.

    That is the point of not tracking finished refs in memory: the disk is the one
    account of what has been adjudicated that a reload, a second tab, or a
    re-run of the command all agree with.
    """
    with Session(["2-046", "2-047"], two) as s:
        assert "0/2 adjudicated" in s.get("/p/2-046")
        decisions_path("2-047", two).write_text(
            json.dumps({"lines": {}}), encoding="utf-8")
        assert "1/2 adjudicated" in s.get("/p/2-046")
        # ...so Done on 2-046 ends the session: nothing is left wanting one.
        s.post("/save", {"ref": "2-046", "lines": {"0": {"text": "a"}}})
        assert s.post("/done", {"ref": "2-046"})["next"] is None


def test_a_repeated_ref_is_queued_once(two):
    """`review 2-046 2-046` is a typo, and a strip that showed it twice would make
    its own "n/2 adjudicated" count a lie."""
    with Session(["2-046", "2-046", "2-047"], two) as s:
        assert "0/2 adjudicated" in s.get("/")
