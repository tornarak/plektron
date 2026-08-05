"""`data/lines_config.json`: what the line editor draws, and what every key does.

`zones_config.py`'s sibling, and deliberately the same shape — the editor loads
it, hands it to the browser verbatim as a JS literal, and draws and binds from
it, so a colour or a keystroke changes in the config and nowhere else.

**Validated at load, never met halfway through a session.** A malformed config
that surfaced as a dead key or an invisible layer three pages into a sitting
would be indistinguishable from a broken editor, and the human would go looking
in the wrong place. Everything checkable is checked here and refused by name.
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG = "data/lines_config.json"

# The layers the editor actually paints. Held here rather than taken from
# whatever the file happens to list, because a renamed layer would otherwise
# vanish from the page in silence — the drawing code asks for these by name.
REQUIRED_LAYERS = (
    "zone", "line", "line_pick", "band", "band_no_zone", "correction",
    "correction_selected", "drag", "ruling_line", "ruling_covered",
    "ruling_zone")

# Likewise: an action the code dispatches on. A config missing one is a key that
# does nothing, which reads as a broken editor rather than a bad config.
REQUIRED_ACTIONS = (
    "save", "delete", "rule_band", "cover_band", "withdraw_ruling", "blot",
    "list", "zoom_in", "zoom_out", "zoom_fit", "frame_band",
    "prev_page", "next_page", "cancel")

REQUIRED_VIEW = (
    "zoom_step", "zoom_min", "zoom_max", "frame_zoom",
    "min_draw_w", "min_draw_h", "ruling_pad_px")


class ConfigError(Exception):
    """A malformed config, raised at load rather than met halfway through."""


def config_path(root: Path = Path(".")) -> Path:
    return Path(root) / CONFIG


def load_config(root: Path = Path(".")) -> dict:
    """Parse, validate and return the config. Raises `ConfigError` on anything
    the editor could not honour."""
    p = config_path(root)
    if not p.exists():
        raise ConfigError(f"no line config at {p} — expected {CONFIG}")
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{p}: {e}") from e

    layers = cfg.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ConfigError(f"{p}: 'layers' must be a non-empty list")
    seen: set[str] = set()
    for lay in layers:
        name = lay.get("name")
        if not name:
            raise ConfigError(f"{p}: a layer is missing 'name': {lay!r}")
        if name in seen:
            raise ConfigError(f"{p}: duplicate layer {name!r}")
        seen.add(name)
        if "fill" not in lay and "stroke" not in lay:
            raise ConfigError(
                f"{p}: layer {name!r} sets neither 'fill' nor 'stroke' — it would "
                "be painted invisibly, which is worse than not painted at all")
    missing = [n for n in REQUIRED_LAYERS if n not in seen]
    if missing:
        raise ConfigError(
            f"{p}: no layer named {', '.join(missing)} — the editor paints these "
            "by name, so an absent one is a layer that silently stops drawing")

    actions = {k: v for k, v in (cfg.get("actions") or {}).items()
               if not k.startswith("_")}
    bound: dict[str, str] = {}
    for name, key in actions.items():
        # **An action may be bound to nothing, and that is a real setting.**
        # `null` or `""` clears the shortcut and leaves the action reachable by
        # clicking its row in the panel — every row there is a control, not a
        # legend. Refusing an empty key would make "I do not want this on the
        # keyboard" unexpressible, and the only way to say it would be deleting
        # the action, which is how a control disappears from the tool entirely.
        if key is None or key == "":
            continue
        if not isinstance(key, str):
            raise ConfigError(
                f"{p}: action {name!r} has key {key!r} — expected a "
                "KeyboardEvent.key string, or null to bind no key at all")
        # Shift is expressed by the character for a printable key — `R` against
        # `r`. A named key has no case to carry it and takes a prefix instead;
        # refused on a printable one because `Shift+r` names an event that never
        # arrives (KeyboardEvent.key for that press is `R`), so the binding would
        # be dead. Same rule as the zone editor's, for the same reason.
        if key.startswith("Shift+"):
            bare = key[len("Shift+"):]
            if len(bare) < 2:
                raise ConfigError(
                    f"{p}: action {name!r} binds {key!r}, but the shift of a "
                    f"printable key is already in the character — write "
                    f"{bare.upper()!r}")
        if key in bound:
            raise ConfigError(
                f"{p}: key {key!r} is bound to two actions, {bound[key]!r} and "
                f"{name!r} — one of them would silently never fire")
        bound[key] = name
    absent = [a for a in REQUIRED_ACTIONS if a not in actions]
    if absent:
        raise ConfigError(
            f"{p}: no entry for {', '.join(absent)} — the editor dispatches these "
            "by name and lists them as controls, so a missing one is a control "
            "that vanishes from the tool. To take a shortcut off the keyboard "
            "while keeping the action, set its key to null rather than deleting "
            "the entry")

    view = cfg.get("view") or {}
    for field in REQUIRED_VIEW:
        if not isinstance(view.get(field), int | float):
            raise ConfigError(f"{p}: view.{field} must be a number")
    if view["zoom_step"] <= 1:
        raise ConfigError(
            f"{p}: view.zoom_step must be greater than 1 — at 1 every zoom key "
            "is a no-op, and below it they trade places")
    if view["zoom_min"] >= view["zoom_max"]:
        raise ConfigError(f"{p}: view.zoom_min must be below view.zoom_max")
    return cfg


def layers_by_name(cfg: dict) -> dict[str, dict]:
    return {lay["name"]: lay for lay in cfg["layers"]}


def layer_css(cfg: dict) -> str:
    """The overlay's stylesheet, generated from the config.

    Generated rather than written beside it: two places naming a colour is how
    one of them goes stale, and this editor's whole subject is a mark you have to
    be able to see.
    """
    out = []
    for lay in cfg["layers"]:
        sel = f'#ov .ly-{lay["name"]}'
        decl = [f'fill:{lay.get("fill", "none")}',
                f'stroke:{lay.get("stroke", "none")}',
                f'stroke-width:{lay.get("width", 1)}']
        if lay.get("dash"):
            decl.append(f'stroke-dasharray:{lay["dash"]}')
        if lay.get("opacity") is not None:
            decl.append(f'opacity:{lay["opacity"]}')
        out.append(sel + "{" + ";".join(decl) + "}")
        if lay.get("hover"):
            out.append(f'{sel}:hover{{fill:{lay["hover"]}}}')
    return "\n".join(out) + "\n"
