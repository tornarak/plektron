"""`config/lines.json` — the line editor's colours and keys, validated at load.

`zones_config.py`'s sibling and deliberately the same shape: a human moving
between the two editors should be configuring one tool with two subjects, not
learning a second format.

Everything here is about a failure that would otherwise present as a *broken
editor* rather than a bad config. A key bound twice fires one of its two jobs,
consistently, and reads as a shortcut that does the wrong thing. A layer the
drawing code asks for by name and the config does not declare simply stops being
painted — on an editor whose whole subject is a mark you have to be able to see.
Both are refused at load, by name, where the human is still looking at the file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import lines_config as lc

REAL = json.loads((Path("config") / "lines.json").read_text(encoding="utf-8"))


def _write(tmp_path: Path, cfg: dict) -> Path:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "lines.json").write_text(
        json.dumps(cfg), encoding="utf-8")
    return tmp_path


def _page(tmp_path: Path, cfg: dict, ref: str = "1-048") -> str:
    """The editor page under a config, rendered through the app.

    Goes through a request rather than calling a renderer, because the page is
    now a template plus a state blob plus a mount prefix and only the response
    holds all three. Everything before the request is the fixture the old
    renderer needed anyway — a config, a zones config, and a raster to size the
    stage against.
    """
    import shutil

    from PIL import Image
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    root = _write(tmp_path, cfg)
    shutil.copy(Path("config") / "zones.json", root / "config")
    (root / "scans").mkdir(exist_ok=True)
    Image.new("RGB", (600, 800), "white").save(
        root / "scans" / f"chukchi-{ref}.png")

    session = {"start": ref, "store": "gt/ocr", "itinerary": [ref],
               "itinerary_name": ""}
    app = create_app(root, Sessions(root=root, by_editor={"lines": session}),
                     editor="lines")
    return TestClient(app).get(f"/lines/?ref={ref}").text


def test_the_shipped_config_loads():
    cfg = lc.load_config()
    assert {lay["name"] for lay in cfg["layers"]} >= set(lc.REQUIRED_LAYERS)
    assert set(lc.REQUIRED_ACTIONS) <= set(cfg["actions"])


def test_every_layer_the_editor_paints_is_declared():
    """The list is held in code, not taken from whatever the file happens to
    name: a renamed layer would otherwise vanish from the page in silence."""
    names = {lay["name"] for lay in REAL["layers"]}
    assert set(lc.REQUIRED_LAYERS) <= names


def test_a_missing_layer_is_refused_by_name(tmp_path):
    cfg = json.loads(json.dumps(REAL))
    cfg["layers"] = [lay for lay in cfg["layers"] if lay["name"] != "band"]
    with pytest.raises(lc.ConfigError, match="band"):
        lc.load_config(_write(tmp_path, cfg))


def test_a_layer_that_would_paint_nothing_is_refused(tmp_path):
    """Invisible is worse than absent: absent is caught by the check above, and
    invisible looks like the editor failing to find anything."""
    cfg = json.loads(json.dumps(REAL))
    cfg["layers"].append({"name": "ghost"})
    with pytest.raises(lc.ConfigError, match="neither"):
        lc.load_config(_write(tmp_path, cfg))


def test_one_key_bound_twice_is_refused(tmp_path):
    """The failure this check exists for: it would fire exactly one of the two,
    consistently, and read as a broken shortcut rather than a bad config."""
    cfg = json.loads(json.dumps(REAL))
    cfg["actions"]["blot"] = cfg["actions"]["save"]
    with pytest.raises(lc.ConfigError, match="two actions"):
        lc.load_config(_write(tmp_path, cfg))


def test_shift_on_a_printable_key_is_refused(tmp_path):
    """`Shift+r` names an event that never arrives — the key of that press is
    `R` — so the binding would be dead. The same rule the zone editor holds."""
    cfg = json.loads(json.dumps(REAL))
    cfg["actions"]["withdraw_ruling"] = "Shift+r"
    with pytest.raises(lc.ConfigError, match="already in the character"):
        lc.load_config(_write(tmp_path, cfg))


def test_an_unbound_action_is_refused(tmp_path):
    cfg = json.loads(json.dumps(REAL))
    del cfg["actions"]["save"]
    with pytest.raises(lc.ConfigError, match="save"):
        lc.load_config(_write(tmp_path, cfg))


def test_a_zoom_step_of_one_is_refused(tmp_path):
    """At 1 every zoom key is a no-op and the editor looks unresponsive."""
    cfg = json.loads(json.dumps(REAL))
    cfg["view"]["zoom_step"] = 1
    with pytest.raises(lc.ConfigError, match="zoom_step"):
        lc.load_config(_write(tmp_path, cfg))


def test_the_css_names_every_layer(tmp_path):
    """Generated from the config rather than written beside it: two places naming
    a colour is how one of them goes stale."""
    css = lc.layer_css(REAL)
    for name in lc.REQUIRED_LAYERS:
        assert f".ly-{name}{{" in css


def test_a_colour_change_reaches_the_stylesheet(tmp_path):
    cfg = json.loads(json.dumps(REAL))
    for lay in cfg["layers"]:
        if lay["name"] == "band":
            lay["stroke"] = "#123456"
    assert "#123456" in lc.layer_css(cfg)


def test_the_editor_binds_what_the_config_says(tmp_path):
    """The page's dispatch table and its help panel are both generated from the
    bindings, so a rebound key moves in one place and the panel cannot lie."""
    cfg = json.loads(json.dumps(REAL))
    cfg["actions"]["blot"] = "B"
    html = _page(tmp_path, cfg)
    assert '"blot": "B"' in html or '"blot":"B"' in html
    assert "<kbd>B</kbd>" in html


def test_an_action_may_be_bound_to_nothing(tmp_path):
    """"I do not want this on the keyboard" is a real setting, and the only other
    way to say it would be deleting the entry — which is how a control vanishes
    from the tool entirely. Cleared, the action stays listed and stays clickable."""
    cfg = json.loads(json.dumps(REAL))
    cfg["actions"]["blot"] = None
    loaded = lc.load_config(_write(tmp_path, cfg))
    assert loaded["actions"]["blot"] is None


def test_two_cleared_bindings_do_not_collide(tmp_path):
    """The duplicate check is about keys, and `null` is not a key. Two unbound
    actions are two unbound actions, not a conflict."""
    cfg = json.loads(json.dumps(REAL))
    cfg["actions"]["blot"] = None
    cfg["actions"]["list"] = ""
    lc.load_config(_write(tmp_path, cfg))


def test_a_cleared_action_still_renders_as_a_control(tmp_path):
    """The row is the control; the key is a shortcut for the row. Unbound, the
    row is still there with a dash where its key would be."""
    cfg = json.loads(json.dumps(REAL))
    cfg["actions"]["blot"] = None
    html = _page(tmp_path, cfg)
    assert 'data-act="blot"' in html
    assert "kbd class=none" in html
