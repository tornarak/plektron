"""`config/zones.json` and its loader.

The config is the single place the zone vocabulary lives — the UI binds its keys
from it and the validator draws its rules from it — so a malformed one is not a
file problem, it is a session where a type is silently unreachable. Everything
`load_config` refuses is something that would otherwise be invisible from the page:
a duplicate key binds one keystroke to two types and the second never fires; an
`auto_select` naming a type that no longer exists leaves the editor on no type at
all after a commit.

The shipped config is tested too, not just synthetic ones. It is data under version
control that two modules trust, and nothing else would notice a stray comma.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.zones_config import (
    ConfigError,
    load_config,
    override_windows,
    part_spec,
    rank_of,
    types_by_key,
    types_by_label,
)

REPO = Path(__file__).resolve().parent.parent.parent
PROJECT = REPO / "jesup" / "bogoras-chukchi"


def base_cfg() -> dict:
    """A minimal well-formed config: two types, one part, a measured column."""
    return {
        "types": [
            {"label": "RunningTitleZone", "key": "r", "rank": 0, "max_per_page": 1},
            {"label": "MainZone-P", "key": "p", "rank": 10, "max_per_page": None},
        ],
        "order_rules": [
            {"id": "title-first", "severity": "warn"},
            {"id": "rank-monotone", "severity": "warn"},
            {"id": "max-per-page", "severity": "warn"},
        ],
        "auto_select": {"fresh_page": "RunningTitleZone", "after": {}},
        "columns": {
            "parts": {"1": {"measure": 1778, "fallback_x0": 500}},
            "anchor": {
                "band_top": 0.12,
                "band_bottom": 0.88,
                "ink_row_share": 0.02,
                "max_run_gap_px": 30,
                "min_run_px": 40,
                "min_run_share": 0.6,
                "ink_pad_left": 17,
                "ink_pad_right": 11,
            },
            "overrides": {},
        },
        "width_tolerance_px": 24,
        "min_zone_h_px": 30,
        "max_overlap_px": 8,
    }


def write(tmp_path: Path, cfg: dict) -> Path:
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "zones.json").write_text(
        json.dumps(cfg), encoding="utf-8"
    )
    return tmp_path


def test_shipped_config_loads():
    """The file actually in the repo passes every check the loader makes."""
    cfg = load_config(PROJECT)
    assert len(cfg["types"]) == 7
    assert {t["key"] for t in cfg["types"]} == set("rpcqfmo")


def test_shipped_config_covers_all_three_parts():
    """Each part declares a measure and a fallback; the position is measured off
    the page, so there is deliberately no per-part column position to check."""
    cfg = load_config(PROJECT)
    for part in ("1", "2", "3"):
        spec = cfg["columns"]["parts"][part]
        assert 1700 < spec["measure"] < 1850
        assert spec["fallback_x0"] > 0


def test_missing_config_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="no zone config"):
        load_config(tmp_path)


def test_duplicate_key_refused(tmp_path):
    """The whole point of the check: the loser of a key collision never fires."""
    cfg = base_cfg()
    cfg["types"][1]["key"] = "r"
    with pytest.raises(ConfigError, match="bound to two types"):
        load_config(write(tmp_path, cfg))


def test_duplicate_label_refused(tmp_path):
    cfg = base_cfg()
    cfg["types"][1]["label"] = "RunningTitleZone"
    with pytest.raises(ConfigError, match="duplicate type label"):
        load_config(write(tmp_path, cfg))


def test_multi_character_key_refused(tmp_path):
    cfg = base_cfg()
    cfg["types"][1]["key"] = "pp"
    with pytest.raises(ConfigError, match="one character"):
        load_config(write(tmp_path, cfg))


def test_auto_select_naming_absent_type_refused(tmp_path):
    cfg = base_cfg()
    cfg["auto_select"]["fresh_page"] = "MainZone-Gone"
    with pytest.raises(ConfigError, match="not a declared type"):
        load_config(write(tmp_path, cfg))


def test_auto_select_after_naming_absent_type_refused(tmp_path):
    cfg = base_cfg()
    cfg["auto_select"]["after"] = {"RunningTitleZone": "MainZone-Gone"}
    with pytest.raises(ConfigError, match="undeclared type"):
        load_config(write(tmp_path, cfg))


def test_backwards_override_window_refused(tmp_path):
    cfg = base_cfg()
    cfg["columns"]["overrides"]["1-048"] = {"columns": [{"x0": 2410, "x1": 618}]}
    with pytest.raises(ConfigError, match="not left-to-right"):
        load_config(write(tmp_path, cfg))


def test_empty_override_refused(tmp_path):
    """An override that lists no columns silently reverts to the measured one,
    which is the opposite of what writing it down was meant to achieve."""
    cfg = base_cfg()
    cfg["columns"]["overrides"]["1-048"] = {"columns": []}
    with pytest.raises(ConfigError, match="non-empty 'columns' list"):
        load_config(write(tmp_path, cfg))


def test_missing_measure_refused(tmp_path):
    cfg = base_cfg()
    del cfg["columns"]["parts"]["1"]["measure"]
    with pytest.raises(ConfigError, match="positive measure"):
        load_config(write(tmp_path, cfg))


def test_missing_anchor_field_refused(tmp_path):
    cfg = base_cfg()
    del cfg["columns"]["anchor"]["ink_pad_left"]
    with pytest.raises(ConfigError, match="ink_pad_left"):
        load_config(write(tmp_path, cfg))


def test_inverted_anchor_band_refused(tmp_path):
    cfg = base_cfg()
    cfg["columns"]["anchor"]["band_top"] = 0.9
    with pytest.raises(ConfigError, match="top < bottom"):
        load_config(write(tmp_path, cfg))


def test_negative_tolerance_refused(tmp_path):
    cfg = base_cfg()
    cfg["min_zone_h_px"] = -1
    with pytest.raises(ConfigError, match="non-negative"):
        load_config(write(tmp_path, cfg))


def test_action_key_colliding_with_a_type_key_refused(tmp_path):
    """One keystroke bound twice fires exactly one of its jobs, consistently —
    which reads as a broken shortcut rather than as a bad config."""
    cfg = base_cfg()
    cfg["actions"] = {"undo": "p"}
    with pytest.raises(ConfigError, match="both a type and"):
        load_config(write(tmp_path, cfg))


def test_two_actions_on_one_key_refused(tmp_path):
    cfg = base_cfg()
    cfg["actions"] = {"undo": "u", "delete": "u"}
    with pytest.raises(ConfigError, match="two actions"):
        load_config(write(tmp_path, cfg))


def test_a_named_key_may_carry_a_shift_prefix(tmp_path):
    """`Shift+ArrowUp` is to `ArrowUp` what `X` is to `x` — and the two are a
    different action here, so the modifier has to be expressible."""
    cfg = base_cfg()
    cfg["actions"] = {"sel_up": "ArrowUp", "nudge_back": "Shift+ArrowUp"}
    assert load_config(write(tmp_path, cfg))["actions"]["nudge_back"] == "Shift+ArrowUp"


def test_shift_on_a_printable_key_refused(tmp_path):
    """KeyboardEvent.key for that press is `A`, so the binding would be dead —
    a shortcut that silently never fires, which is what the collision check
    exists to keep out of this file."""
    cfg = base_cfg()
    cfg["actions"] = {"undo": "Shift+a"}
    with pytest.raises(ConfigError, match="already in the character"):
        load_config(write(tmp_path, cfg))


def test_the_shipped_auto_select_chain_keys_an_ordinary_page():
    """Title, then the paragraph carried over from the previous page, then
    paragraph starts for as many as the page holds. A continuation can only be
    closed once, so it must not be sticky — the commonest page is keyed with
    three type keys pressed in total."""
    a = load_config(PROJECT)["auto_select"]
    cur, seq = a["fresh_page"], []
    for _ in range(4):
        seq.append(cur)
        cur = a["after"].get(cur, cur)
    assert seq == ["RunningTitleZone", "MainZone-Continued", "MainZone-P", "MainZone-P"]


def test_running_title_is_a_one_click_type():
    """Editor-measured: the head is a single line of fixed size and the drop to
    the text proper is the same on every ordinary page, so its height is not in
    question and the chain should resume where the body starts.

    The *shape* is asserted, not the two numbers. They are measured off the page
    and expected to be tuned as keying proceeds; a test that failed whenever the
    editor adjusted one would be a test everyone learns to ignore — the same
    reason fixtures here live in `tmp_path` rather than over the live corpus.
    """
    t = types_by_label(load_config(PROJECT))["RunningTitleZone"]
    assert 40 <= t["default_height"] <= 200
    assert 0 <= t["gap_after"] <= 200


def test_the_chain_stops_after_the_types_that_end_a_column():
    """Footnotes and the signature line are the last thing in the column, and
    `other` is a catch-all whose neighbours are unpredictable by definition.
    Carrying a top into any of them guesses wrong more often than right, and a
    wrong guess costs a right-click every single time."""
    by = types_by_label(load_config(PROJECT))
    for label in ("MarginTextZone-Notes", "QuireMarksZone", "MainZone-Other"):
        assert by[label]["chain_after"] is False, label


def test_the_chain_continues_after_the_title_and_body_types():
    """Absent means true — the common case needs no declaration."""
    by = types_by_label(load_config(PROJECT))
    for label in (
        "RunningTitleZone",
        "MainZone-P",
        "MainZone-Continued",
        "MainZone-Quote",
    ):
        assert by[label].get("chain_after", True) is True, label


def test_non_boolean_chain_after_refused(tmp_path):
    """A number here would read as a gap and silently do nothing."""
    cfg = base_cfg()
    cfg["types"][0]["chain_after"] = 0
    with pytest.raises(ConfigError, match="chain_after"):
        load_config(write(tmp_path, cfg))


def test_body_types_declare_no_fixed_shape():
    """A default height on a paragraph would be a guess about the page, and the
    editor would place it on one click without anyone having judged it."""
    by = types_by_label(load_config(PROJECT))
    for label in (
        "MainZone-P",
        "MainZone-Continued",
        "MainZone-Quote",
        "MarginTextZone-Notes",
        "MainZone-Other",
    ):
        assert not by[label].get("default_height"), label


def test_zero_default_height_refused(tmp_path):
    """It would place an invisible zone on one click and report nothing."""
    cfg = base_cfg()
    cfg["types"][0]["default_height"] = 0
    with pytest.raises(ConfigError, match="default_height"):
        load_config(write(tmp_path, cfg))


def test_negative_default_height_refused(tmp_path):
    cfg = base_cfg()
    cfg["types"][0]["default_height"] = -90
    with pytest.raises(ConfigError, match="default_height"):
        load_config(write(tmp_path, cfg))


def test_non_integer_gap_after_refused(tmp_path):
    cfg = base_cfg()
    cfg["types"][0]["gap_after"] = "40"
    with pytest.raises(ConfigError, match="gap_after"):
        load_config(write(tmp_path, cfg))


def test_shape_fields_are_optional(tmp_path):
    """Most types declare neither; absence must not be an error."""
    cfg = base_cfg()
    for t in cfg["types"]:
        t.pop("default_height", None)
        t.pop("gap_after", None)
    load_config(write(tmp_path, cfg))


def test_shipped_view_settings_are_sane():
    v = load_config(PROJECT)["view"]
    assert 0 < v["column_margin"] < 0.5
    assert v["edge_band_px"] > 0
    # The overlap has to leave a real jump behind it; an overlap at or above a
    # screen height would page backwards or stand still.
    assert 0 < v["edge_overlap_px"] < 400


def test_shipped_actions_do_not_collide_with_shipped_types():
    cfg = load_config(PROJECT)
    keys = {t["key"] for t in cfg["types"]}
    acts = {v for k, v in cfg["actions"].items() if not k.startswith("_")}
    assert keys.isdisjoint(acts)
    assert "cancel" in cfg["actions"] and "undo" in cfg["actions"]


def test_action_underscore_keys_are_documentation_not_bindings(tmp_path):
    cfg = base_cfg()
    cfg["actions"] = {"_about": "p", "undo": "u"}
    load_config(write(tmp_path, cfg))  # the "_about" value must not collide


def test_part_spec_resolves_by_part():
    cfg = base_cfg()
    assert part_spec(cfg, "1-048")["measure"] == 1778


def test_part_spec_refuses_an_unconfigured_part():
    with pytest.raises(ValueError, match="no column config for part 9"):
        part_spec(base_cfg(), "9-001")


def test_no_override_means_measure_the_page():
    """None is the ordinary answer — almost every page is anchored off its own
    ink, and an override is the exception written down for a named ref."""
    assert override_windows(base_cfg(), "1-048") is None


def test_override_replaces_the_measured_column():
    """A two-column page's body does not also occupy the one-column measure,
    and offering both would let the wrong one be picked by a keystroke."""
    cfg = base_cfg()
    cfg["columns"]["overrides"]["3-005"] = {
        "columns": [{"x0": 300, "x1": 1200}, {"x0": 1300, "x1": 2200}]
    }
    assert override_windows(cfg, "3-005") == [
        {"x0": 300, "x1": 1200},
        {"x0": 1300, "x1": 2200},
    ]


def test_override_is_looked_up_by_normalized_ref():
    cfg = base_cfg()
    cfg["columns"]["overrides"]["3-005"] = {"columns": [{"x0": 1, "x1": 2}]}
    assert override_windows(cfg, "3-5") == [{"x0": 1, "x1": 2}]


def test_lookup_helpers():
    cfg = base_cfg()
    assert types_by_key(cfg)["r"]["label"] == "RunningTitleZone"
    assert types_by_label(cfg)["MainZone-P"]["key"] == "p"
    assert rank_of(cfg, "MainZone-P") == 10
    assert rank_of(cfg, "MainZone-Nonexistent") is None
