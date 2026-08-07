"""The figure section of `data/zones_config.json`, and the keyboard it shares.

One editor, two tracks, one set of keystrokes. The zone types, the figure types
and the actions are three namespaces drawing on the same keyboard, and a key
bound in two of them fires exactly one of its jobs, consistently, looking like a
broken shortcut rather than a bad config. The loader refuses all three collisions
for that reason, and these hold it to it — the check is worth a test precisely
because a duplicate is invisible from the page it breaks.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import zones_config as zc
from harness.zones_config import ConfigError

REPO = Path(__file__).resolve().parent.parent.parent


def _write(root: Path, mutate) -> Path:
    cfg = json.loads((REPO / zc.CONFIG).read_text(encoding="utf-8"))
    mutate(cfg)
    p = root / zc.CONFIG
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return root


def test_the_shipped_config_declares_both_figure_types():
    cfg = zc.load_config(REPO)
    assert [t["label"] for t in zc.fig_types(cfg)] == [
        "GraphicZone", "GraphicZone-FigDesc"]


def test_a_figure_key_colliding_with_a_zone_type_is_refused(tmp_path):
    root = _write(tmp_path, lambda c: c["figures"]["types"][0].__setitem__(
        "key", c["types"][0]["key"]))
    with pytest.raises(ConfigError, match="two types"):
        zc.load_config(root)


def test_a_figure_key_colliding_with_an_action_is_refused(tmp_path):
    root = _write(tmp_path, lambda c: c["figures"]["types"][0].__setitem__(
        "key", c["actions"]["undo"]))
    with pytest.raises(ConfigError, match="two types|type and the"):
        zc.load_config(root)


def test_a_figure_action_colliding_with_a_zone_action_is_refused(tmp_path):
    root = _write(tmp_path, lambda c: c["figures"]["actions"].__setitem__(
        "toggle_track", c["actions"]["undo"]))
    with pytest.raises(ConfigError, match="two actions"):
        zc.load_config(root)


def test_a_figure_action_colliding_with_a_zone_type_is_refused(tmp_path):
    root = _write(tmp_path, lambda c: c["figures"]["actions"].__setitem__(
        "toggle_track", c["types"][0]["key"]))
    with pytest.raises(ConfigError, match="type and the"):
        zc.load_config(root)


def test_a_label_shared_with_the_zone_track_is_refused(tmp_path):
    """The two stores would claim one label and nothing in an ALTO says which
    store wrote it — the missing internal witness that cost `gt/seg/`."""
    root = _write(tmp_path, lambda c: c["figures"]["types"][0].__setitem__(
        "label", c["types"][0]["label"]))
    with pytest.raises(ConfigError, match="both a zone type and a figure type"):
        zc.load_config(root)


def test_auto_place_must_name_a_type_to_follow(tmp_path):
    root = _write(tmp_path, lambda c: c["figures"]["types"][1]["auto_place"].pop(
        "after"))
    with pytest.raises(ConfigError, match="names no 'after'"):
        zc.load_config(root)


def test_a_zero_height_preview_is_refused(tmp_path):
    """It would arm an invisible caption box on every picture and report nothing."""
    root = _write(tmp_path, lambda c: c["figures"]["types"][1][
        "auto_place"].__setitem__("height_px", 0))
    with pytest.raises(ConfigError, match="positive integer"):
        zc.load_config(root)


def test_a_figures_section_with_no_types_is_refused(tmp_path):
    root = _write(tmp_path, lambda c: c["figures"].__setitem__("types", []))
    with pytest.raises(ConfigError, match="declares no types"):
        zc.load_config(root)


def test_a_config_with_no_figures_section_still_loads(tmp_path):
    """The section is this book's; a corpus with no figure track omits it and the
    zone editor must not care."""
    root = _write(tmp_path, lambda c: c.pop("figures"))
    cfg = zc.load_config(root)
    assert zc.fig_types(cfg) == []
    assert zc.fig_warnings(cfg, [{"label": "GraphicZone-FigDesc"}]) == []
