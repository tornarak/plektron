"""The ASGI shell, and the behaviours a port is most likely to drop silently.

The stdlib shell these replaced recorded six of them, each with a reason it
was written down.
None is visible in a page that renders, which is exactly why they get named
tests rather than being left implied by whatever the editors happen to exercise:
a port that lost the loopback bind, or that answered a `fetch` with an HTML
traceback, would look entirely fine from a browser.

These run against a `TestClient` rather than a real server on a real port. The
fixtures being replaced stood a thread up on port 8799 and polled `/` up to two
hundred times waiting for it to answer; that is not a stricter test, only a
slower one. The two invariants that are genuinely about a socket — the loopback
bind, and refusing a held port — are tested against `bind()` directly, since
that is where they live.
"""
from __future__ import annotations

import socket

import pytest
from fastapi import APIRouter
from starlette.testclient import TestClient

from harness.web import Editor, Sessions, create_app, errors, load_editors, serve

BANG = "the specific thing that broke"


@pytest.fixture
def editor(monkeypatch):
    """A registered editor with one navigated route and one fetched route.

    Registered into a *copy* of the registry: `EDITORS` is module state that the
    real editors populate at import, and a test that appended to it would leak
    into every later test in the session.

    **The real registry is filled first, and that is not belt-and-braces.**
    `register()` mutates whatever `EDITORS` names *when it runs*, and the editor
    modules register on first import — so if the session's first `create_app`
    happens under the patch, all four register into this throwaway dict and the
    real one is left permanently empty when monkeypatch reverts. It made
    `pytest harness/tests/test_web_shell.py` fail on its own two registry tests
    while passing in the full suite, where some earlier file imports the editors
    unpatched. Order-dependent, and invisible until this file is run alone.
    """
    load_editors()
    router = APIRouter()

    @router.get("/")
    def home():
        return {"home": True}

    @router.get("/boom")
    def boom():
        raise RuntimeError(BANG)

    @router.get("/row")
    @errors.fetched
    def row():
        raise RuntimeError(BANG)

    ed = Editor(name="probe", port=8799, home="/", router=router)
    monkeypatch.setattr("harness.web.EDITORS", {"probe": ed}, raising=False)
    monkeypatch.setattr("harness.web.shell.EDITORS", {"probe": ed}, raising=False)
    monkeypatch.setattr("harness.web.serve.EDITORS", {"probe": ed}, raising=False)
    return ed


@pytest.fixture
def client(editor, tmp_path):
    # `raise_server_exceptions=False` so the exception handler runs and we see the
    # response a browser would get. Left on, the client re-raises instead, and the
    # whole point here is the *shape of the reply*.
    return TestClient(create_app(tmp_path, Sessions(root=tmp_path), editor="probe"),
                      raise_server_exceptions=False)


def test_a_navigated_failure_renders_its_traceback(client):
    """Not a reset connection and not a tidy apology.

    These are started backgrounded with stdout redirected, so a failure that only
    reaches stderr sends the human to a file they have to be told about first.
    """
    r = client.get("/probe/boom")
    assert r.status_code == 500
    assert "text/html" in r.headers["content-type"]
    assert BANG in r.text
    assert "RuntimeError" in r.text


def test_a_fetched_failure_answers_json(client):
    """The split that regresses silently: both arms return 500, so a wrong one
    still looks like a failure being reported. The symptom is a reason that never
    reaches the human — `fetch(...).json()` raising on an HTML body, and the page
    showing the parse error instead of what actually broke."""
    r = client.get("/probe/row")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"error": BANG}


def test_the_mark_travels_with_the_endpoint_not_the_path(client):
    """The old shell compared `self.path` against a tuple of literal strings, so
    re-pathing a route silently changed its error shape. The mark is on the
    function now."""
    from harness.web.shell import router as shell_router

    assert getattr(shell_router.routes[0].endpoint, "__web_fetched__", False) is False
    r = client.get("/probe/row")
    assert r.json()["error"] == BANG


def test_nothing_unrouted_answers(client):
    assert client.get("/nope").status_code == 404
    assert client.get("/probe/nope").status_code == 404


def test_a_bare_port_lands_on_the_editor_that_owns_it(client, editor):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"] == "/probe/"


def test_a_bare_root_still_lands_under_a_port_override(client, editor):
    """Found by running it. The front door mapped the receiving socket's port to
    a *registered* port, so `--port 8794` gave a 404 at `/` — a door that works
    only at the default. `serve()` records the ports it actually bound, and the
    editor the process was started for is the fallback under a test client,
    which has no meaningful port at all."""
    client.app.state.ports = {"probe": 9999}
    assert client.get("/", follow_redirects=False).headers["location"] == "/probe/"
    client.app.state.ports = {}
    client.app.state.editor = "probe"
    assert client.get("/", follow_redirects=False).headers["location"] == "/probe/"


def test_stop_answers_before_it_stops(client):
    """The response has to go out first, so the page can say so. `should_exit` is
    a flag uvicorn notices on its next pass, not a blocking shutdown — the old
    shell had to spawn a thread here to avoid deadlocking on its own serve loop."""

    class FakeServer:
        should_exit = False

    client.app.state.server = FakeServer()
    r = client.post("/stop")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert client.app.state.server.should_exit is True


def test_a_session_can_be_handed_to_a_running_server(client):
    """The route that keeps two editors usable at once now that one process owns
    both their ports."""
    r = client.post("/session/probe", json={"session": {"itinerary": ["1-042"]}})
    assert r.status_code == 200
    assert r.json()["open"] == "/probe/"
    assert client.app.state.sessions.get("probe") == {"itinerary": ["1-042"]}


def test_an_unknown_editor_is_named_not_guessed(client):
    r = client.post("/session/zones", json={"session": {}})
    assert r.status_code == 404
    assert "probe" in r.json()["detail"]


def test_a_malformed_session_is_rejected_at_the_boundary(client):
    """422 naming the field, rather than a KeyError three frames in. This is what
    the typed body buys over `json.loads` and `.get`."""
    r = client.post("/session/probe", json={"session": "not a mapping"})
    assert r.status_code == 422
    assert any("session" in str(d.get("loc", "")) for d in r.json()["detail"])


def test_the_registry_is_populated_before_anything_reads_it():
    """Found by running the editor rather than by a test, which is why there is
    one now. `EDITORS` is empty until the editor modules are imported, and an
    empty registry does not fail loudly: `handoff` reads it, finds no such
    editor, and reports "nothing is listening" — so every invocation would start
    its own server and none would ever join another. A silent wrong answer,
    produced by a missing import."""
    from harness.web import load_editors

    assert "lines" in load_editors()
    assert serve.url_for("lines").startswith("http://127.0.0.1:")


def test_a_port_override_reaches_the_url_that_is_printed():
    """Also found by running it: `--port` moved which socket was bound but not
    the URL in the banner, so it named a port nothing was listening on — and the
    banner is the one line the caller is waiting for."""
    assert ":8790/" in serve.url_for("lines", "/?ref=1-048", port=8790)


def test_the_socket_binds_loopback_only():
    """These serve unpublished editorial work and have no business being
    reachable. It is the shell's property, not any editor's, so a fifth editor
    cannot forget it."""
    s = serve.bind(0)
    try:
        assert s.getsockname()[0] == "127.0.0.1"
    finally:
        s.close()


def test_a_held_port_is_refused_rather_than_shared():
    """Not `SO_REUSEPORT`: two servers silently sharing a port would answer
    alternate requests from different stores, which is the worst available
    failure — indistinguishable from one server behaving erratically."""
    first = serve.bind(0)
    port = first.getsockname()[1]
    try:
        with pytest.raises(OSError):
            serve.bind(port)
    finally:
        first.close()


def test_handoff_reports_nothing_listening_rather_than_raising(editor):
    """None means "start the process yourself", and it has to be distinguishable
    from a successful handoff without an exception in the ordinary path — a
    closed port is the *normal* case for the first invocation."""
    free = socket.socket()
    free.bind(("127.0.0.1", 0))
    port = free.getsockname()[1]
    free.close()
    object.__setattr__(editor, "port", port)
    assert serve.handoff("probe", {"itinerary": []}) is None


def test_static_files_are_served_with_a_validator(client):
    """The whole point of moving CSS out of Python: `zones edit` shipped 68 KB of
    JS inside every page, on an editor whose pages are navigated with the arrow
    keys. A static file carries a validator, so the second request is a 304."""
    r = client.get("/static/css/editor.css")
    assert r.status_code == 200
    assert "--bg" in r.text
    etag = r.headers.get("etag")
    assert etag, "no validator — the asset would be re-sent on every navigation"
    again = client.get("/static/css/editor.css", headers={"If-None-Match": etag})
    assert again.status_code == 304


# --- each port answers for one editor -----------------------------------------
#
# Every route used to answer on every port: `:8732` served `/lines/save` exactly
# as `:8733` did, so a stale tab or a mistyped path could write through a tool
# nobody had opened. The routers are still all mounted — one app is what lets the
# four share a Sessions, a store cache and the handoff — so the isolation is
# enforced per request, off the socket the request arrived on.


def _two_editors(monkeypatch):
    """Two registered editors, so "another editor's prefix" is a thing that
    exists. The single-editor fixture above cannot express this case.

    `load_editors()` first, for the reason that fixture's docstring gives: the
    editor modules register into whatever `EDITORS` names when they are first
    imported, and under a patch that is this dict."""
    load_editors()
    a = APIRouter()

    @a.get("/save")
    def a_save():
        return {"wrote": "alpha"}

    b = APIRouter()

    @b.get("/save")
    def b_save():
        return {"wrote": "beta"}

    eds = {"alpha": Editor(name="alpha", port=8801, home="/", router=a),
           "beta": Editor(name="beta", port=8802, home="/", router=b)}
    monkeypatch.setattr("harness.web.EDITORS", eds, raising=False)
    monkeypatch.setattr("harness.web.shell.EDITORS", eds, raising=False)
    return eds


def test_a_port_serves_only_its_own_editor(tmp_path, monkeypatch):
    """The property the four ports did not have. A write reaching the wrong tool
    is the shape that deleted a page's corrections through a save nobody made.

    Driven by the **port**, not by `state.editor`: `base_url` puts the address in
    `scope["server"]`, which is where uvicorn puts the receiving socket, so this
    exercises the mechanism rather than the fallback. One app, two doors."""
    _two_editors(monkeypatch)
    app = create_app(tmp_path, Sessions(root=tmp_path), editor="alpha")
    app.state.ports = {"alpha": 8801, "beta": 8802}

    on_alpha = TestClient(app, base_url="http://127.0.0.1:8801")
    on_beta = TestClient(app, base_url="http://127.0.0.1:8802")

    assert on_alpha.get("/alpha/save").json() == {"wrote": "alpha"}
    assert on_beta.get("/beta/save").json() == {"wrote": "beta"}

    # …and neither reaches the other, though both routers are mounted here.
    bad = on_alpha.get("/beta/save")
    assert bad.status_code == 404
    assert "beta is served on port 8802" in bad.json()["error"]
    assert on_beta.get("/alpha/save").status_code == 404


def test_the_port_wins_over_the_editor_the_process_was_started_for(tmp_path,
                                                                   monkeypatch):
    """`state.editor` names the verb that started the process, and one process
    serves all four. It is the fallback for a request with no port, never the
    answer when there is one — otherwise a `zones edit` process would refuse the
    lines editor on its own port, and the handoff that shares the process would
    have nothing to hand to."""
    _two_editors(monkeypatch)
    app = create_app(tmp_path, Sessions(root=tmp_path), editor="alpha")
    app.state.ports = {"alpha": 8801, "beta": 8802}
    on_beta = TestClient(app, base_url="http://127.0.0.1:8802")
    assert on_beta.get("/beta/save").json() == {"wrote": "beta"}


def test_a_moved_port_moves_the_ownership_with_it(tmp_path, monkeypatch):
    """`--port` binds one editor's socket somewhere else, and `state.ports` is
    the record of what was actually bound. Reading the registered default instead
    would refuse the editor on the very port it was told to use."""
    _two_editors(monkeypatch)
    app = create_app(tmp_path, Sessions(root=tmp_path), editor="alpha")
    app.state.ports = {"alpha": 9901, "beta": 8802}
    moved = TestClient(app, base_url="http://127.0.0.1:9901")
    assert moved.get("/alpha/save").json() == {"wrote": "alpha"}
    assert moved.get("/beta/save").status_code == 404


def test_the_shared_routes_answer_whatever_the_port(tmp_path, monkeypatch):
    """`/static` and the shell's three belong to the process, not to a page.
    `handoff` posts `/session/{editor}` to the *target* editor's port, so
    refusing it there would leave a second invocation unable to join — the
    regression the shell router exists to prevent."""
    _two_editors(monkeypatch)
    app = create_app(tmp_path, Sessions(root=tmp_path), editor="alpha")
    app.state.ports = {"alpha": 8801, "beta": 8802}
    c = TestClient(app)

    r = c.post("/session/beta", json={"session": {"q": 1}, "open_at": ""})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert app.state.sessions.get("beta") == {"q": 1}
    assert c.get("/static/css/editor.css").status_code == 200
    assert c.post("/stop").status_code == 200


def test_an_app_that_can_name_no_editor_lets_everything_through(tmp_path,
                                                                monkeypatch):
    """Falls open rather than closed when there is no port *and* no editor. The
    isolation is about real sockets; refusing here would break every suite that
    builds an app to exercise one route, to guard against a request that cannot
    arrive."""
    _two_editors(monkeypatch)
    app = create_app(tmp_path, Sessions(root=tmp_path))   # editor defaults
    c = TestClient(app)
    assert c.get("/alpha/save").status_code == 200
    assert c.get("/beta/save").status_code == 200


def test_an_unrouted_path_still_404s_normally(tmp_path, monkeypatch):
    """The middleware must not turn "no such route" into "wrong port" — the two
    send a reader somewhere different."""
    _two_editors(monkeypatch)
    app = create_app(tmp_path, Sessions(root=tmp_path), editor="alpha")
    c = TestClient(app)
    r = c.get("/nope")
    assert r.status_code == 404 and "served on port" not in r.text
