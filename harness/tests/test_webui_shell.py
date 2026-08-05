"""The shell three editors share, and the one decision in it that can go wrong.

`harness/webui.py` is mostly moved code — `review.serve` and `zones_ui.serve`
were near-identical, and `test_review_session.py` still exercises the moved parts
end to end over a real server. What is *new* is the split between a route the
page **navigates** to and one it **fetches**, and that split is the kind of thing
that regresses silently: both arms return 500, so a wrong one still looks like a
failure being reported. It shows up only as a reason that never reaches the human
— `fetch(...).json()` raising on an HTML body, and the page displaying the parse
error instead of what actually broke.

So the assertion worth making is not "it returns 500" but **which shape**.
"""
from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from harness import webui

BANG = "the specific thing that broke"


class Handler(webui.EditorHandler):
    editor = "test"
    fetched = ("/fetched",)

    def get(self):
        if self.path in ("/boom", "/fetched"):
            raise ValueError(BANG)
        if self.path == "/ok":
            self.send_html("<p>fine")
            return
        self.send_error(404)

    def post(self):
        if self.path == "/stop":
            self.send_json({})
            self.stop_from_page()
            return
        raise ValueError(BANG)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(monkeypatch):
    """A live shell on a loopback port, stopped the way the page stops it."""
    monkeypatch.setattr(webui.webbrowser, "open", lambda *a, **k: None)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=webui.run, args=(Handler, port, base, []),
                         daemon=True)
    t.start()
    for _ in range(200):  # bind is not instantaneous; poll rather than sleep
        try:
            urllib.request.urlopen(base + "/ok", timeout=5).read()
            break
        except Exception:
            threading.Event().wait(0.02)
    else:
        raise RuntimeError("server never came up")
    yield base
    if t.is_alive():
        try:
            req = urllib.request.Request(base + "/stop", data=b"{}",
                                         method="POST")
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass
    t.join(timeout=5)


def _fails(url: str) -> urllib.error.HTTPError:
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(url, timeout=5)
    assert e.value.code == 500
    return e.value


def test_a_navigated_route_renders_its_traceback(server):
    """A human staring at a blank tab needs the reason on the page — the
    alternative sends them to a stderr log they have to be told about first."""
    err = _fails(server + "/boom")
    body = err.read().decode("utf-8")
    assert "text/html" in err.headers["Content-Type"]
    assert BANG in body
    assert "Traceback" in body


def test_a_fetched_route_fails_as_json(server):
    """The page parses this body. An HTML traceback would raise inside the
    `fetch`, and the page would show the parse error rather than the cause."""
    err = _fails(server + "/fetched")
    assert "application/json" in err.headers["Content-Type"]
    assert json.loads(err.read())["error"] == BANG


def test_a_failed_post_is_json_whatever_the_route(server):
    """Every POST is a `fetch` by construction, so there is nothing to split on
    and no route needs to opt in."""
    req = urllib.request.Request(server + "/anything", data=b"{}", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 500
    assert json.loads(e.value.read())["error"] == BANG


def test_an_unrouted_path_is_404_not_a_traceback(server):
    """`send_error` is not an exception: a route that does not exist is an answer,
    not a failure, and must not be dressed up as one."""
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(server + "/nope", timeout=5)
    assert e.value.code == 404


def test_the_default_handler_serves_nothing(server):
    """An editor that routes nothing inherits no endpoints — `get`/`post` default
    to 404 rather than to somebody else's routes."""
    assert webui.EditorHandler.fetched == ()
    for verb in ("get", "post"):
        assert getattr(webui.EditorHandler, verb).__qualname__.startswith(
            "EditorHandler")
