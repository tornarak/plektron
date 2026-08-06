"""`proposal set` without a LINE writes many lines in one call.

**This is a budget fix, not a convenience.** A reader issues a command and reads
its result as two separate turns, so every single-line write costs two of
`maxTurns: 80`. `1-101` — a two-column numbered list of native names, where
nearly every line wants Tier-1 keying — spent 23 `proposal set`, 3 `proposal
replace` and 14 `Edit` calls over 21 distinct lines, hit the cap exactly at 80
requests, and was cut off mid-correction with the page still open. Only one line
was touched more than once, so it was not thrash: it was forty corrections
arriving one per turn on a page that needed forty corrections. `1-100`, the
other structured page in the corpus, reached 73 turns the same way.

The class of page this fails on is the vocabulary list — the densest Tier-1
material in the book, and the material the whole pass exists for.

`--values` carries the object rather than stdin because the reader's guard
refuses any unquoted operator: `<` and `|` are both unavailable to it, so stdin
cannot be reached from inside a reading pass at all. Stdin still works for a
human or the coordinator, the same pairing the single form has.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from harness.proposal_check import set_fields


def _proposal(tmp_path: Path, lines: dict) -> Path:
    p = tmp_path / "proposal.json"
    p.write_text(json.dumps({"lines": lines}, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return p


def _lines(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))["lines"]


def test_many_lines_land_in_one_write(tmp_path):
    p = _proposal(tmp_path, {"1": {"text": "a"}, "2": {"text": "b"},
                             "3": {"text": "c"}})
    r = set_fields(p, {"1": "one", "3": "three"}, "text")
    assert r["set"] == 2
    assert _lines(p) == {"1": {"text": "one"}, "2": {"text": "b"},
                         "3": {"text": "three"}}


def test_it_says_which_lines_actually_changed(tmp_path):
    """A bulk write that reports only "ok" is a bulk write nobody can check —
    and re-sending a whole page's text, most of which was already right, is the
    ordinary way this gets used."""
    p = _proposal(tmp_path, {"1": {"text": "one"}, "2": {"text": "b"}})
    r = set_fields(p, {"1": "one", "2": "two"}, "text")
    assert r["changed"] == "2"
    assert r["unchanged"] == "1"


def test_a_new_line_index_is_created_like_the_single_form(tmp_path):
    p = _proposal(tmp_path, {"1": {"text": "a"}})
    set_fields(p, {"7": "seven"}, "text")
    assert _lines(p)["7"] == {"text": "seven"}


def test_every_value_is_normalized_on_the_way_in(tmp_path):
    """The reason the editors exist at all: a hand-typed precomposed character is
    invisible to exact-match against the file's own NFD. One value going in
    unnormalized would reintroduce that per line, at forty lines a call."""
    p = _proposal(tmp_path, {"1": {"text": ""}, "2": {"text": ""}})
    set_fields(p, {"1": unicodedata.normalize("NFC", "ê"),
                   "2": unicodedata.normalize("NFC", "ñ")}, "text")
    got = _lines(p)
    assert got["1"]["text"] == "ê"
    assert got["2"]["text"] == "ñ"


def test_other_fields_on_a_touched_line_survive(tmp_path):
    """It sets one field, like the singular form — a `note` or `resolved` already
    on the line is not collateral."""
    p = _proposal(tmp_path, {"1": {"text": "a", "note": "speck", "class": "artifact"}})
    set_fields(p, {"1": "b"}, "text")
    assert _lines(p)["1"] == {"text": "b", "note": "speck", "class": "artifact"}


def test_the_file_keeps_its_own_indentation(tmp_path):
    """`--path` reaches `decision.json` too, which review writes at indent 1;
    imposing this module's indent turned a 10-line correction into a 716-line
    diff once already."""
    p = tmp_path / "decision.json"
    p.write_text(json.dumps({"lines": {"1": {"text": "a"}}}, indent=1) + "\n",
                 encoding="utf-8")
    set_fields(p, {"1": "b"}, "text")
    body = p.read_text(encoding="utf-8")
    assert body.splitlines()[1].startswith(' "')
    assert body.endswith("\n")


# --- the CLI's own refusals ------------------------------------------------

def _run(tmp_path, argv: list[str], stdin: str = ""):
    import io
    import sys

    from harness.cli import build_parser

    p = _proposal(tmp_path, {"1": {"text": "a"}})
    old = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        return build_parser().main(
            ["proposal", "set", "1-048", "--path", str(p), *argv],
            standalone_mode=False)
    finally:
        sys.stdin = old


def test_value_without_a_line_is_refused(tmp_path):
    """`--value` is the singular channel and names no line on its own — silently
    treating it as a bulk payload would write the string to nothing."""
    with pytest.raises(ValueError, match="needs a LINE"):
        _run(tmp_path, ["--value", "x"])


@pytest.mark.parametrize("payload,match", [
    ("not json", "not JSON"),
    ('["a"]', "non-empty"),
    ("{}", "non-empty"),
    ('{"x": "a"}', "every key is a line index"),
    ('{"1": 2}', "every key is a line index"),
])
def test_a_malformed_payload_is_refused_rather_than_guessed(tmp_path, payload, match):
    with pytest.raises(ValueError, match=match):
        _run(tmp_path, ["--values", payload])


def test_neither_a_line_nor_values_nor_stdin_is_a_usage_error(tmp_path):
    with pytest.raises(ValueError, match="no LINE and no values"):
        _run(tmp_path, [])
