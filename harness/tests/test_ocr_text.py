"""The two reading verbs over the ALTO stores' text — the dump and the search.

Both replace an idiom that was in daily use: `ocr lines REF | jq -r 'map(.text) |
join("\\n")'` and `ocr lines --all | rg PATTERN`. A second ad-hoc spelling of a
recurring operation is the tell that a verb is missing, so these are the verb —
and the reason it is worth testing rather than shrugging at is that both idioms
were **silently reading through the view**, which resolves to the recognizer's
reading on any page a human has not been through. The `scope` row is the fix, and
the first test below is the one that keeps it honest.

The NFD test is the sharper one. The corpus is NFD corpus-wide; a pattern typed
into a terminal or pasted out of a PDF may be NFC, and a composed `č` searched
against decomposed text matches nothing and **exits 0** — a clean corpus-wide
negative that is entirely an artefact of the keyboard. That is fluent nonsense in
its purest form: no error signal anywhere, and the answer reads like an answer.
"""

from __future__ import annotations

import json
import unicodedata

import pytest
from click.testing import CliRunner

from harness.cli import build_parser, main

# 1-042 and 1-043 are committed ground truth and hold the live fixture: `Kuluˊči`,
# the form `lexicon lookup`'s tests use, printed on both pages.
FORM = "Kuluˊči"


def run(*argv):
    r = CliRunner().invoke(build_parser(), list(argv))
    assert r.exit_code == 0, r.output
    return r.output


def payload(*argv):
    return json.loads(run(*argv, "--json"))


def test_the_scope_row_says_which_store_answered():
    """An empty result has two readings and only this row separates them.

    `--store gt --all` searches the pages a human has been through, not the book;
    the group's default, `mz`, searches what the recognizer read, at that
    reading's rank. A search that reported only its hits would let the second be
    mistaken for the first, which is the "two witnesses that may be one" hazard
    wearing a count. The row names the store directory, never a bare rank.
    """
    got = payload("ocr", "grep", "zzzznotthere", "1-042", "--store", "gt")
    assert got["matches"] == []
    (scope,) = got["scope"]
    assert scope["store"] == "gt/ocr"
    assert scope["pages"] == 1
    assert scope["lines"] > 0

    by_default = payload("ocr", "grep", "zzzznotthere", "1-042")
    assert by_default["scope"][0]["store"] == "mz/ocr"


def test_a_composed_pattern_finds_the_decomposed_text():
    """The failure this verb would otherwise have: exit 0, no matches, no signal."""
    composed = unicodedata.normalize("NFC", FORM)
    assert composed != FORM, "fixture is not testing what it claims"
    got = payload("ocr", "grep", composed, "1-042", "1-043", "--store", "gt")
    assert got["scope"][0]["hits"] >= 2
    assert all(FORM in row["text"] for row in got["matches"])


def test_case_is_significant_unless_folded():
    """Case carries information in a Tier-1 form, so the default is exact."""
    lowered = payload("ocr", "grep", FORM.lower(), "1-042", "--store", "gt")
    assert lowered["scope"][0]["hits"] == 0
    folded = payload("ocr", "grep", FORM.lower(), "1-042", "--store", "gt", "-i")
    assert folded["scope"][0]["hits"] > 0


def test_context_rows_are_marked_and_never_duplicated():
    """Two hits three lines apart, asked for two lines of context each.

    Their windows overlap, and a naive walk emits the shared lines twice — once
    per window — so a reader counting rows counts the corpus wrong. Rows are keyed
    by `(ref, index)` instead, and the tie goes to `hit`: a line that is both a hit
    and another hit's context is a hit.
    """
    got = payload("ocr", "grep", "reindeer", "1-042", "--store", "gt",
                  "--context", "2")
    seen = [(r["ref"], r["index"]) for r in got["matches"]]
    assert len(seen) == len(set(seen))
    hits = [r for r in got["matches"] if r["hit"]]
    assert len(hits) == got["scope"][0]["hits"]
    assert all("reindeer" in r["text"] for r in hits)
    assert any(not r["hit"] for r in got["matches"])


def test_a_hit_inside_another_hits_window_stays_a_hit():
    """The tie-break, stated on its own. `ocr grep` is measurement, and a hit
    demoted to context by the order the walk happened to reach it would be a row
    disagreeing with the count beside it."""
    got = payload("ocr", "grep", "the", "1-042", "--store", "gt", "--context", "3")
    hits = [r for r in got["matches"] if r["hit"]]
    assert len(hits) == got["scope"][0]["hits"]


def test_a_bad_pattern_is_a_usage_error(capsys):
    """Exit 2, not a traceback and not 1: argument validation is the parser's
    (VERBS.md, Conventions), and an unterminated character class is an argument
    that never named a search.

    Driven through `main` rather than `CliRunner`, because the mapping from a
    raised `ValueError` to exit 2 lives there — a runner invoking the command
    object directly measures the raise and not the contract.
    """
    assert main(["ocr", "grep", "[", "1-042"]) == 2
    assert "not a regular expression" in capsys.readouterr().err


def test_text_is_plain_lines_and_one_page_carries_no_heading():
    """The single-ref form is the page and nothing else — it is what anything
    downstream reads, and a heading in it would be one more thing to strip."""
    out = run("ocr", "text", "1-042", "--store", "gt")
    lines = out.splitlines()
    assert not any(line.startswith("# ") for line in lines)
    assert "BOGORAS, THE CHUKCHEE." in lines
    assert all(line.strip() for line in lines), "empties should be dropped"


def test_several_pages_each_carry_their_ref():
    out = run("ocr", "text", "1-042", "1-043", "--store", "gt")
    assert [ln for ln in out.splitlines() if ln.startswith("# ")] == ["# 1-042",
                                                                     "# 1-043"]


def test_the_dump_and_the_line_table_are_the_same_reading():
    """`ocr text` is `ocr lines` with the geometry taken off, and must not become
    a second reading of the page: two views of one store that can disagree are the
    hazard this repo keeps finding, and here it would be free to introduce."""
    dumped = run("ocr", "text", "1-042", "--store", "gt").splitlines()
    table = json.loads(run("ocr", "lines", "1-042", "--store", "gt", "--json"))
    kept = [rec["text"] for rec in table if rec["text"].strip()]
    assert dumped == kept


@pytest.mark.parametrize("argv", [("ocr", "text"), ("ocr", "grep", "x")])
def test_naming_no_page_is_an_error_rather_than_a_sweep(argv, capsys):
    """A corpus run is `--all`, never an omission — and these two are the verbs
    where an accidental sweep is cheapest to type and slowest to notice."""
    assert main(list(argv)) == 2
    assert "--all" in capsys.readouterr().err
