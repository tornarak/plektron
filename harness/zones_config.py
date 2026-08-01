"""`data/zones_config.json`: the seven zone types and the columns they are drawn in.

One file, two consumers, and that is the whole reason it is a file rather than a
table of module constants. `zones.py` validates against it; the browser UI receives
it verbatim as a JS literal and draws, binds keys and raises order warnings from the
same numbers. A type added here appears in the UI with its key and colour and in the
validator's rules without either being edited, which is what the brief asked for:
the domain-knowledge assumptions are configurable and exemptible, not hardcoded.

**Every rule in it is a warning.** `order_rules` carries a `severity` field and the
only value it takes is `"warn"` — the shipped config has no rule that can refuse a
save. That is deliberate and it is the house position: a page whose layout breaks
the expected order is the interesting page, and a tool that refuses it teaches its
operator to key a lie. Refusal is reserved for the mechanical impossibilities in
`zones.validate_page` (a zone of negative height, a label nobody declared).

**Side is not persisted anywhere.** `parity_hint` below is what the UI starts a
fresh session on, and nothing more: the editor flips it with `v`, it alternates
across next/prev, and it never reaches the ALTO. Only part 1's parity mapping is
anchored to a printed folio at all (see the file's own `_provenance`), so treating
it as a fact rather than a starting guess would be inventing evidence.
"""
from __future__ import annotations
import json
from pathlib import Path

from .context import norm_ref, parse_ref

CONFIG = "data/zones_config.json"


class ConfigError(ValueError):
    """A malformed config, raised at load rather than met halfway through a session.

    Everything `load_config` checks is something that would otherwise surface as a
    UI that silently drops a type, or a keystroke that quietly does two things.
    Both are worse than a refusal to start.
    """


def config_path(root: Path = Path(".")) -> Path:
    return root / CONFIG


def load_config(root: Path = Path(".")) -> dict:
    """Read and check `data/zones_config.json`.

    Checks the properties the rest of the package then assumes: labels and keys
    unique, `auto_select` naming types that exist, every part carrying both sides
    with at least one ordered window, tolerances positive. Unique keys in
    particular cannot be left to chance — a duplicate would bind one keystroke to
    two types and the loser would simply never be reachable, which is invisible
    from the page.
    """
    p = config_path(root)
    if not p.exists():
        raise ConfigError(f"no zone config at {p} — expected {CONFIG}")
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{p}: {e}") from e

    types = cfg.get("types")
    if not isinstance(types, list) or not types:
        raise ConfigError(f"{p}: 'types' must be a non-empty list")
    seen_label, seen_key = set(), set()
    for t in types:
        for field in ("label", "key"):
            if not t.get(field):
                raise ConfigError(f"{p}: a type is missing '{field}': {t!r}")
        if t["label"] in seen_label:
            raise ConfigError(f"{p}: duplicate type label {t['label']!r}")
        if t["key"] in seen_key:
            raise ConfigError(
                f"{p}: key {t['key']!r} is bound to two types — one of them would "
                "be unreachable from the keyboard and nothing would say so")
        # Navigation and column cycling live on non-letter keys precisely so that
        # this space stays free for types; a multi-character key would collide with
        # the UI's single-keystroke model.
        if len(t["key"]) != 1:
            raise ConfigError(f"{p}: type key {t['key']!r} must be one character")
        seen_label.add(t["label"])
        seen_key.add(t["key"])
        rank = t.get("rank")
        if rank is not None and not isinstance(rank, int):
            raise ConfigError(f"{p}: rank of {t['label']!r} must be an integer or null")
        dh = t.get("default_height")
        if dh is not None and (not isinstance(dh, int) or dh <= 0):
            raise ConfigError(
                f"{p}: default_height of {t['label']!r} must be a positive integer "
                "or null — a zero-height default would place an invisible zone on "
                "one click and report nothing")
        ga = t.get("gap_after")
        if ga is not None and not isinstance(ga, int):
            raise ConfigError(f"{p}: gap_after of {t['label']!r} must be an integer")
        ca = t.get("chain_after")
        if ca is not None and not isinstance(ca, bool):
            raise ConfigError(
                f"{p}: chain_after of {t['label']!r} must be true or false — a "
                "number here would read as a gap and silently do nothing")

    # Actions share the keyboard with types, so they share the collision check.
    # A key bound to both "paragraph start" and "undo" would fire exactly one of
    # them, consistently, and look like a broken shortcut rather than a bad config.
    actions = {k: v for k, v in (cfg.get("actions") or {}).items()
               if not k.startswith("_")}
    seen_action: dict[str, str] = {}
    for name, key in actions.items():
        if not isinstance(key, str) or not key:
            raise ConfigError(f"{p}: action {name!r} has no key")
        # Shift is expressed by the character for a printable key — `X` against `x`,
        # which is how `delete_page` and `save` already sit next to each other. A
        # named key has no case to carry it, so it takes a prefix instead. Refused on
        # a printable one because `Shift+a` names an event that never arrives:
        # KeyboardEvent.key for that press is `A`, and the binding would be dead.
        if key.startswith("Shift+"):
            bare = key[len("Shift+"):]
            if len(bare) < 2:
                raise ConfigError(
                    f"{p}: action {name!r} binds {key!r}, but the shift of a "
                    f"printable key is already in the character — write "
                    f"{bare.upper()!r}")
        if key in seen_key:
            raise ConfigError(
                f"{p}: key {key!r} is bound to both a type and the {name!r} action")
        if key in seen_action:
            raise ConfigError(
                f"{p}: key {key!r} is bound to two actions, {seen_action[key]!r} "
                f"and {name!r}")
        seen_action[key] = name

    auto = cfg.get("auto_select") or {}
    fresh = auto.get("fresh_page")
    if fresh and fresh not in seen_label:
        raise ConfigError(f"{p}: auto_select.fresh_page {fresh!r} is not a declared type")
    for before, after in (auto.get("after") or {}).items():
        for lab in (before, after):
            if lab not in seen_label:
                raise ConfigError(f"{p}: auto_select.after names undeclared type {lab!r}")

    parts = ((cfg.get("columns") or {}).get("parts")) or {}
    if not parts:
        raise ConfigError(f"{p}: columns.parts is empty — nothing to draw against")
    for part, spec in parts.items():
        for field in ("measure", "fallback_x0"):
            v = spec.get(field)
            if not isinstance(v, (int, float)) or v <= 0:
                raise ConfigError(f"{p}: part {part} needs a positive {field}")
    anchor = (cfg.get("columns") or {}).get("anchor") or {}
    for field in ("band_top", "band_bottom", "ink_row_share", "max_run_gap_px",
                  "min_run_px", "min_run_share", "ink_pad_left", "ink_pad_right"):
        if not isinstance(anchor.get(field), (int, float)):
            raise ConfigError(f"{p}: columns.anchor.{field} must be a number")
    if not 0 <= anchor["band_top"] < anchor["band_bottom"] <= 1:
        raise ConfigError(f"{p}: columns.anchor band must satisfy 0 <= top < bottom <= 1")
    for ref, spec in ((cfg.get("columns") or {}).get("overrides") or {}).items():
        if ref.startswith("_"):
            continue
        wins = spec.get("columns") if isinstance(spec, dict) else None
        if not isinstance(wins, list) or not wins:
            raise ConfigError(f"{p}: override {ref} needs a non-empty 'columns' list")
        for w in wins:
            if not isinstance(w.get("x0"), (int, float)) or \
               not isinstance(w.get("x1"), (int, float)):
                raise ConfigError(f"{p}: override {ref} window {w!r} needs x0 and x1")
            if w["x1"] <= w["x0"]:
                raise ConfigError(f"{p}: override {ref} window {w!r} is not left-to-right")

    for field in ("width_tolerance_px", "min_zone_h_px", "max_overlap_px"):
        v = cfg.get(field)
        if not isinstance(v, (int, float)) or v < 0:
            raise ConfigError(f"{p}: {field} must be a non-negative number")
    return cfg


def types_by_key(cfg: dict) -> dict[str, dict]:
    return {t["key"]: t for t in cfg["types"]}


def types_by_label(cfg: dict) -> dict[str, dict]:
    return {t["label"]: t for t in cfg["types"]}


def rank_of(cfg: dict, label: str) -> int | None:
    t = types_by_label(cfg).get(label)
    return None if t is None else t.get("rank")


def train_merges(cfg: dict) -> dict[str, str]:
    """`{label: label it is folded into}` for training, empty if none declared.

    **Training only.** The editor offers every declared type, `gt/zones/` stores
    what was keyed, and every check reads the keyed label — a distinction a human
    drew is evidence, and it is not destroyed because a model finds it hard. This
    only ever narrows what `harness zones --assemble` asks the segmenter to learn.
    """
    raw = cfg.get("train_merges") or {}
    return {k: v["into"] for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, dict) and "into" in v}


def part_spec(cfg: dict, ref: str) -> dict:
    part, _ = parse_ref(ref)
    spec = ((cfg.get("columns") or {}).get("parts") or {}).get(str(part))
    if spec is None:
        raise ValueError(f"no column config for part {part} (ref {norm_ref(ref)})")
    return spec


def override_windows(cfg: dict, ref: str) -> list[dict] | None:
    """Hand-set columns for one page, or None to measure it.

    An override **replaces** the measured column rather than adding to it: a
    two-column page's body does not also occupy the one-column measure, and
    offering both would let the wrong one be picked by a keystroke.
    """
    spec = ((cfg.get("columns") or {}).get("overrides") or {}).get(norm_ref(ref))
    if not isinstance(spec, dict) or not spec.get("columns"):
        return None
    return [{"x0": w["x0"], "x1": w["x1"]} for w in spec["columns"]]


def order_warnings(cfg: dict, zones: list[dict],
                   exempt: tuple[str, ...] | list[str] = ()) -> list[dict]:
    """Evaluate the declarative order rules over one page's zones.

    Pure: takes the config and a list of `{label, y0}` and returns records, so both
    the validator and the UI's client-side check can be held to it by a test rather
    than by two implementations agreeing today.

    An exempted rule still returns its warnings, flagged `exempted`. Suppressing
    them outright would make an exemption indistinguishable from a clean page, and
    the exemption file is exactly where a wrong call would go to hide.

    Rules whose id is not implemented here are ignored rather than errored: the
    config is meant to be edited, and a typo in a rule id that silently disabled
    validation would be worse than one that does nothing. `zones.validate_page`
    reports unknown rule ids separately so the typo is still visible.
    """
    exempt = set(exempt or ())
    ranks = {t["label"]: t.get("rank") for t in cfg["types"]}
    enabled = {r["id"] for r in (cfg.get("order_rules") or [])}
    ordered = sorted(zones, key=lambda z: (z.get("y0", 0), z.get("y1", 0)))
    out: list[dict] = []

    def warn(rule: str, detail: str):
        out.append({"rule": rule, "detail": detail, "exempted": rule in exempt})

    if "title-first" in enabled:
        titles = [i for i, z in enumerate(ordered) if ranks.get(z["label"]) == 0]
        if titles and titles[0] != 0:
            above = ordered[0]
            warn("title-first",
                 f"{ordered[titles[0]]['label']} at y={ordered[titles[0]].get('y0')} "
                 f"is below {above['label']} at y={above.get('y0')}")

    if "rank-monotone" in enabled:
        ranked = [z for z in ordered if ranks.get(z["label"]) is not None]
        for a, b in zip(ranked, ranked[1:]):
            if ranks[b["label"]] < ranks[a["label"]]:
                warn("rank-monotone",
                     f"{b['label']} (rank {ranks[b['label']]}) at y={b.get('y0')} "
                     f"follows {a['label']} (rank {ranks[a['label']]}) "
                     f"at y={a.get('y0')}")

    if "max-per-page" in enabled:
        for t in cfg["types"]:
            cap = t.get("max_per_page")
            if not cap:
                continue
            n = sum(1 for z in ordered if z["label"] == t["label"])
            if n > cap:
                warn("max-per-page",
                     f"{t['label']} occurs {n} times, max_per_page is {cap}")

    # An undeclared label is not handled here. It is an *error*, not a warning
    # about arrangement, and `zones.validate_page` raises it as one — a zone whose
    # type nobody declared has no rank, so every rule above simply skipped it, and
    # a page of nothing but undeclared labels would otherwise come back clean.
    return out
