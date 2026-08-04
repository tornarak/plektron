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
import urllib.error
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


def test_the_page_links_to_its_own_full_scan(two):
    """The crops say what a line sets; only the sheet says what is around it.

    A reviewer settling a speck, a dropped line or a run-in heading needs the whole
    page, and hunting for it by hand — in a gitignored `scans/` that is nowhere
    near the review — was the alternative.
    """
    with Session(["2-046", "2-047"], two) as s:
        html = s.get("/p/2-046")
        assert "href='/scan/2-046'" in html
        assert "target=_blank" in html


def test_the_scan_route_serves_the_raster_and_only_for_queued_refs(two):
    """A route rather than a data URI, because the sheet is megabytes and the
    review page is reloaded constantly to carry something opened occasionally."""
    with Session(["2-046"], two) as s:
        with urllib.request.urlopen(s.base + "/scan/2-046", timeout=5) as r:
            assert r.headers["Content-Type"] == "image/png"
            assert r.read()[:8] == b"\x89PNG\r\n\x1a\n"
        # Same containment rule the page route has: a ref nobody queued is not
        # reachable, so one session cannot be used to browse the corpus.
        with pytest.raises(Exception) as e:
            s.get("/scan/2-047")
        assert "404" in str(e.value)


def test_the_static_render_points_at_the_file_on_disk(tmp_path):
    """`--html` is opened off the filesystem, where `/scan/…` means nothing — and
    a browser will not follow file:// from an http origin, so the two cases cannot
    share one href. The relative path is computed, never spelled."""
    _page(tmp_path, "2-046")
    html = render_queue_html("2-046", "mz/ocr", tmp_path)
    assert "/scan/2-046" not in html
    assert "../../scans/chukchi-2-046.png" in html


def test_a_human_note_is_opt_in_and_absent_until_written(two):
    """A note field on every line is 45 empty boxes competing with the 45 that
    matter, so the affordance is a button and the field arrives when asked for."""
    html = render_queue_html("2-046", "mz/ocr", two)
    assert "class=hnb" in html, "no button to open a note"
    # Present in the markup but not shown: opening one must not cost a round trip.
    assert "data-note='0'" in html
    assert html.count("hidden></textarea>") >= 2, "note fields should start hidden"


def test_an_empty_note_is_not_stored(two):
    """`note` existing is the only way anyone finds the lines that were remarked
    on, so an empty one on every line would make that search useless — the same
    noise in the file that a textarea on every line is on screen."""
    with Session(["2-046"], two) as s:
        s.post("/save", {"ref": "2-046",
                         "lines": {"0": {"text": "a", "note": "   "},
                                   "1": {"text": "b", "note": "speck, not type"}}})
        got = json.loads(decisions_path("2-046", two).read_text())
        assert "note" not in got["lines"]["0"]
        assert got["lines"]["1"]["note"] == "speck, not type"


def test_a_saved_note_renders_open(two):
    """A note nobody can see is not a record. One already written comes back
    visible, with its button gone rather than offering to create a second."""
    with Session(["2-046"], two) as s:
        s.post("/save", {"ref": "2-046",
                         "lines": {"1": {"text": "b", "note": "scanner smudge"}}})
        html = s.get("/p/2-046")
        assert "scanner smudge" in html
        assert "class=hnb data-line='1' hidden" in html


def test_an_emptied_note_folds_back_to_the_button(two):
    """The control has two faces, not a door that only opens.

    Asserted on the wiring rather than by driving a browser: the blur handler is
    scoped to note fields (`data-note`), and reverting is conditional on the field
    being blank, so a note with content is never closed out from under the typist.
    """
    html = render_queue_html("2-046", "mz/ocr", two)
    assert "t.dataset.note!==undefined" in html, "blur handler not scoped to notes"
    assert "addEventListener('blur'" in html
    assert "if(t.value.trim()) return;" in html


def test_restore_reports_a_note_on_a_line_nobody_edited(two):
    """The report that says what the human did must show the ruling they wrote.

    `edits` is keyed on text differing from the proposal, and the commonest note
    sits on a line whose text nobody changed — so before `notes` existed, an
    adjudicator's ruling lived in decision.json and appeared in no report at all.
    """
    from harness.review import restore
    with Session(["2-046"], two) as s:
        s.post("/save", {"ref": "2-046",
                         "lines": {"0": {"text": "human 2-046 0"},        # unchanged
                                   "1": {"text": "human 2-046 1",
                                         "note": "speck, not type"}}})
    rep = restore("2-046", "mz/ocr", two)
    assert rep["edited_by_human"] == 0, "no text was changed"
    assert rep["edits"] == []
    assert rep["noted"] == 1
    assert rep["notes"] == [{"line": 1, "note": "speck, not type"}]


def test_notes_are_not_posted_as_line_readings(two):
    """The note boxes are textareas too. Every selector that means "a line's
    reading" is scoped to [data-line] for this reason — an unscoped one would
    collect them and post a note as if it were the text of some line."""
    html = render_queue_html("2-046", "mz/ocr", two)
    assert "querySelectorAll('textarea[data-line]')" in html
    assert "for(const t of document.querySelectorAll('textarea'))\n" not in html


def test_a_repeated_ref_is_queued_once(two):
    """`review 2-046 2-046` is a typo, and a strip that showed it twice would make
    its own "n/2 adjudicated" count a lie."""
    with Session(["2-046", "2-046", "2-047"], two) as s:
        assert "0/2 adjudicated" in s.get("/")


# --- failure is reported where it happened ---------------------------------

def test_a_store_that_cannot_answer_refuses_before_the_socket_is_bound(two):
    """Naming the wrong `--store` is a fact about the invocation, so it is
    reported by the invocation.

    `review` reads `--store mz` by default, and a page restored before `ocr
    predict` existed has ground truth and no prediction. That used to bind the
    port, print the URL and three reassuring `decisions -> …` lines, and then
    fail on navigation — the traceback reaching only the server's stderr, which
    under `--serve` is always a background log. `serve` resolves every ref's
    geometry first, the same rule `page_refs` applies to ref parsing.
    """
    (two / "mz" / "ocr" / "chukchi-2-047.xml").unlink()
    with pytest.raises(FileNotFoundError) as e:
        serve(["2-046", "2-047"], "mz/ocr", two, _free_port())
    msg = str(e.value)
    assert "2-047" in msg and "2-046" not in msg, "names the pages that are missing"
    assert "--store gt" in msg, "names the store that would answer"


def test_a_failed_request_renders_the_reason_instead_of_resetting(two, monkeypatch):
    """An unhandled exception is a page, not a dropped connection.

    Left to socketserver it prints a traceback to stderr and resets, so the
    reviewer gets a browser error naming nothing while the reason sits in a log
    they have to be told about. The server stays up: this is a report, not a
    shutdown.
    """
    import harness.lines as L
    with Session(["2-046"], two) as s:
        def boom(*a, **kw):
            raise RuntimeError("the crop scaler fell over")
        monkeypatch.setattr(L, "write_line_crops", boom)
        with pytest.raises(urllib.error.HTTPError) as e:
            s.get("/p/2-046")
        assert e.value.code == 500
        body = e.value.read().decode("utf-8")
        assert "the crop scaler fell over" in body, "the cause is on the page"
        assert "RuntimeError" in body and "Traceback" in body
        assert "/p/2-046" in body, "and the request that raised"
        monkeypatch.undo()
        assert "2-046" in s.get("/p/2-046"), "the server survived it"
