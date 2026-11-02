"""What holds the public site's look to its decisions: the sheets stay square and
serif, the grain stays small and single, every text colour stays legible on the
ground it is set on, and a page's status is described as what it is."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "web"
SHEETS = [WEB / "static" / "css" / n for n in ("edition.css", "landing.css", "geomap.css")]
EDITION = SHEETS[0].read_text("utf-8")

#: Decoded bytes. A tile is on every page of the site, inside the sheet.
GRAIN_LIMIT = 4096

#: WCAG AAA. Not AA's 4.5, which this sheet was tuned to just clear and which read
#: as washed out nearly everywhere: a floor gets treated as the target.
MIN_CONTRAST = 7.0

#: Text colour → the grounds it is set on. Grain is ignored: it is capped faint.
TEXT_ON = {
    **dict.fromkeys(
        ("fg", "dim", "accent", "mark", "pin", "water", "flora", "abstract",
         "lex", "warn", "info", "sel"),
        ("bg", "card")),
    "on-board": ("board", "card"),      # the bar's text, and its buttons' faces
    "on-block": ("block",),
}


def _block(selector: str) -> dict[str, str]:
    start = EDITION.index(selector)
    body = EDITION[EDITION.index("{", start) + 1:EDITION.index("}", start)]
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6})\b", body))


LIGHT = _block(":root {")
DARK = _block(':root[data-theme="dark"]')


def _luminance(colour: str) -> float:
    def channel(i: int) -> float:
        c = int(colour[i:i + 2], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("sheet", SHEETS, ids=lambda p: p.name)
def test_the_sheets_hold_no_rounded_corner_and_no_system_sans(sheet):
    text = sheet.read_text("utf-8")
    assert "border-radius" not in text
    assert "system-ui" not in text


@pytest.mark.parametrize("theme,tokens", [("light", LIGHT), ("dark", DARK)])
def test_every_text_colour_is_legible_on_its_ground(theme, tokens):
    failing = {
        f"{text} on {ground}": round(_contrast(tokens[text], tokens[ground]), 2)
        for text, grounds in TEXT_ON.items() for ground in grounds
        if _contrast(tokens[text], tokens[ground]) < MIN_CONTRAST
    }
    assert not failing, f"{theme}: under {MIN_CONTRAST}:1: {failing}"


def test_the_two_dark_blocks_say_the_same_thing():
    """CSS cannot union a media query with an attribute selector, so the block is
    written twice, and nothing else would hold the copies together."""
    system = _block('@media (prefers-color-scheme: dark) { :root:not([data-theme="light"])')
    assert system == DARK
    assert DARK


@pytest.mark.parametrize("name", ["light", "dark", "board"])
def test_a_grain_is_a_small_png_declared_once(name):
    found = re.findall(rf"--grain-{name}:url\(data:image/png;base64,([^)]+)\)", EDITION)
    assert len(found) == 1
    png = base64.b64decode(found[0])
    assert png.startswith(b"\x89PNG")
    assert len(png) <= GRAIN_LIMIT
    # No copy under another name: the dark blocks name a tile, they do not hold one.
    assert EDITION.count(found[0]) == 1


def test_a_map_trees_controls_lead_the_row_and_stay_on_what_is_selected():
    """At the end of the row they landed wherever the name happened to stop."""
    row = (WEB / "static" / "js" / "geomap.js").read_text("utf-8")
    assert row.index("<a class='entry'") < row.index("<button class='hide'") < row.index("<a class='node'")
    css = (WEB / "static" / "css" / "geomap.css").read_text("utf-8")
    for held in (".map-tree li.sel > button", ".map-tree li.sel > a.entry",
                 ".map-tree li.off > button", ".map-tree li.off > a.entry"):
        assert held in css
    assert "visibility:hidden" not in css


def test_a_copied_passage_leaves_the_page_marks_behind():
    """Selecting across a page turn must give the sentence, not `[338] uncollated`
    in the middle of it."""
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", EDITION, flags=re.S))
    unselectable = " ".join(sel for sel, body in rules if "user-select:none" in body)
    assert ".leaf-at" in unselectable and ".flag" in unselectable


def test_small_capitals_stay_off_what_can_hold_the_books_text():
    """Capital against small capital is a distinction in the notation, so a case
    fold over a Tier-1 form would misprint it."""
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", EDITION, flags=re.S))
    capped = " ".join(sel for sel, body in rules if "small-caps" in body)
    assert "draft-tag" in capped          # the search below is looking in the right place
    for holder in (".location", "#panel-contents", ".card", ".hits", ".tier1", ".lex"):
        assert holder not in capped
