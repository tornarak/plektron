"""The declarative order rules over a page's zones.

`order_warnings` is evaluated twice for every page — once in the browser, from the
injected config, so a violation shows the instant a type is chosen, and once on the
server when the save lands. Two implementations of one rule set is how they drift,
so the browser's copy is a transcription of this function and these tests are what
hold the pair together: any rule added here has to be added there, and the
round-trip test at the end is what fails if the shapes stop matching.

Every rule is a *warning*. The book breaks its own layout conventions — a page that
is all footnotes, a chapter opening with no running title — and a tool that refused
those would be teaching its operator to key a lie. Exemption is therefore about
silencing a known-good page in a report, never about permitting an edit.
"""
from __future__ import annotations

from harness.zones_config import order_warnings

CFG = {
    "types": [
        {"label": "RunningTitleZone", "key": "r", "rank": 0, "max_per_page": 1},
        {"label": "MainZone-P", "key": "p", "rank": 10, "max_per_page": None},
        {"label": "MainZone-Continued", "key": "c", "rank": 10, "max_per_page": None},
        {"label": "MarginTextZone-Notes", "key": "f", "rank": 20, "max_per_page": 1},
        {"label": "QuireMarksZone", "key": "m", "rank": 30, "max_per_page": 1},
        {"label": "MainZone-Other", "key": "o", "rank": None, "max_per_page": None},
    ],
    "order_rules": [{"id": "title-first", "severity": "warn"},
                    {"id": "rank-monotone", "severity": "warn"},
                    {"id": "max-per-page", "severity": "warn"}],
}


def z(label, y0, y1=None):
    return {"label": label, "y0": y0, "y1": y1 if y1 is not None else y0 + 100}


def rules(warnings):
    return [w["rule"] for w in warnings]


def test_an_ordinary_page_is_silent():
    """Running title, body, footnotes, signature — the shape most pages have."""
    page = [z("RunningTitleZone", 200), z("MainZone-Continued", 320),
            z("MainZone-P", 900), z("MarginTextZone-Notes", 2900),
            z("QuireMarksZone", 3300)]
    assert order_warnings(CFG, page) == []


def test_input_order_does_not_matter_only_geometry_does():
    """Zones arrive in click order, which is not reading order after an insert."""
    page = [z("MarginTextZone-Notes", 2900), z("RunningTitleZone", 200),
            z("MainZone-P", 900)]
    assert order_warnings(CFG, page) == []


def test_footnotes_above_body_warns():
    page = [z("RunningTitleZone", 200), z("MarginTextZone-Notes", 400),
            z("MainZone-P", 1200)]
    assert rules(order_warnings(CFG, page)) == ["rank-monotone"]


def test_title_below_a_body_zone_warns_both_rules():
    """Two rules genuinely fire: the title is not topmost, and rank 0 follows 10."""
    page = [z("MainZone-P", 200), z("RunningTitleZone", 900)]
    assert set(rules(order_warnings(CFG, page))) == {"title-first", "rank-monotone"}


def test_no_title_at_all_is_silent():
    """A chapter opening carries no running title; that is not a violation."""
    page = [z("MainZone-P", 400), z("MarginTextZone-Notes", 2900)]
    assert order_warnings(CFG, page) == []


def test_null_rank_type_is_unordered_anywhere():
    """MainZone-Other is the catch-all; ordering it would warn constantly."""
    for y in (100, 1500, 3400):
        page = [z("RunningTitleZone", 200), z("MainZone-Other", y),
                z("MainZone-P", 900), z("MarginTextZone-Notes", 2900)]
        got = [w for w in order_warnings(CFG, page) if w["rule"] == "rank-monotone"]
        assert got == [], f"MainZone-Other at y={y} should not affect rank order"


def test_equal_ranks_do_not_warn():
    """Paragraph start and continuation interleave freely — both are rank 10."""
    page = [z("MainZone-P", 300), z("MainZone-Continued", 700),
            z("MainZone-P", 1100), z("MainZone-Continued", 1500)]
    assert order_warnings(CFG, page) == []


def test_max_per_page_counts():
    page = [z("RunningTitleZone", 200), z("RunningTitleZone", 260),
            z("MainZone-P", 900)]
    got = [w for w in order_warnings(CFG, page) if w["rule"] == "max-per-page"]
    assert len(got) == 1 and "2 times" in got[0]["detail"]


def test_unlimited_types_never_hit_the_cap():
    page = [z("MainZone-P", 100 * i) for i in range(3, 20)]
    assert [w for w in order_warnings(CFG, page) if w["rule"] == "max-per-page"] == []


def test_exemption_flags_but_never_hides():
    """An exempted rule still returns its warnings — silence would make the
    exemption file the one place a wrong call could go to hide."""
    page = [z("RunningTitleZone", 200), z("MarginTextZone-Notes", 400),
            z("MainZone-P", 1200)]
    got = order_warnings(CFG, page, exempt=["rank-monotone"])
    assert len(got) == 1
    assert got[0]["rule"] == "rank-monotone" and got[0]["exempted"] is True


def test_exemption_is_per_rule_not_per_page():
    page = [z("MainZone-P", 200), z("RunningTitleZone", 900)]
    got = order_warnings(CFG, page, exempt=["title-first"])
    by_rule = {w["rule"]: w["exempted"] for w in got}
    assert by_rule == {"title-first": True, "rank-monotone": False}


def test_disabling_a_rule_in_config_disables_it():
    """The rules are configurable: dropping one from order_rules stops it firing."""
    cfg = dict(CFG, order_rules=[{"id": "title-first", "severity": "warn"}])
    page = [z("RunningTitleZone", 200), z("MarginTextZone-Notes", 400),
            z("MainZone-P", 1200)]
    assert order_warnings(cfg, page) == []


def test_unknown_rule_id_is_ignored_not_fatal():
    """A typo in a rule id must not take the other rules down with it."""
    cfg = dict(CFG, order_rules=CFG["order_rules"] + [{"id": "titl-first"}])
    page = [z("MainZone-P", 200), z("RunningTitleZone", 900)]
    assert set(rules(order_warnings(cfg, page))) == {"title-first", "rank-monotone"}


def test_undeclared_label_is_not_an_order_warning():
    """It is an error, raised by validate_page — see that module's own test. Here
    the point is only that it does not masquerade as an arrangement problem."""
    page = [z("MainZone-Invented", 200)]
    assert order_warnings(CFG, page) == []


def test_empty_page_is_silent():
    """Plates and blanks carry no zones at all and that is a legitimate record."""
    assert order_warnings(CFG, []) == []


def test_warning_records_have_one_fixed_key_set():
    """TOON collapses a uniform record list to a table and silently degrades to
    the nested form if the keys go ragged — the harness's binding output rule."""
    page = [z("MainZone-P", 200), z("RunningTitleZone", 900),
            z("RunningTitleZone", 950)]
    got = order_warnings(CFG, page)
    assert len(got) >= 3
    assert {frozenset(w) for w in got} == {frozenset({"rule", "detail", "exempted"})}
