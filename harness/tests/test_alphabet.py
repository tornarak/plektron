"""The alphabet key as a chart: the store, its join, and the two-witness gate.

Scan 1-030 is the p. 10 key — fifty lines of "as in English" in no order, with
the structure of the system nowhere on it. `edition/alphabet.json` transcribes both
printed accounts and Mythology's arrangement of them; `alphabet.chart` joins that
to `ipa.RULES`, `ipa.MODERN` and the corpus's own counts.

**Two properties are load-bearing here and the rest is plumbing.** The store and
`keying_spec.md` state every codepoint twice, deliberately, and `check` compares
them rather than merging — the spec owns the inventory and the store has to be
machine-readable, so the duplication is the price and the comparison is what
makes it safe. And the join must be total in both directions: a rule row with no
store entry would leave a sort off the chart, and a store entry claiming an IPA
value the table does not have would print one that is not there.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from harness import alphabet

REPO = Path(__file__).resolve().parent.parent.parent


def n(x):
    """NFD, on whatever shape. The corpus and the store are decomposed and a
    literal in a source file is whatever the keyboard emitted — `ä` typed here
    is one codepoint and `ä` in the store is two, so an un-normalized comparison
    silently fails on exactly the sorts these tests are about."""
    if isinstance(x, str):
        return unicodedata.normalize("NFD", x)
    return type(x)(n(i) for i in x)


# ------------------------------------------------------- the real store


def test_the_store_and_the_rule_table_cover_each_other():
    """Total in both directions. A rule row with no entry drops a sort off the
    chart; an entry claiming a value the table lacks prints one that is not
    there."""
    rep = alphabet.check(REPO)
    assert rep["errors"] == []
    assert rep["sorts"] == 64


def test_the_codepoints_agree_with_keying_spec():
    """The second witness, and the reason the duplication is allowed.
    `keying_spec.md` owns the inventory (CLAUDE.md's precedence table) and this
    store has to be machine-readable; neither is derived from the other, so the
    only thing that keeps them honest is this comparison."""
    rep = alphabet.check(REPO)
    assert rep["spec_checked"] >= 18, "the spec parse found fewer sorts than it did"
    assert not [e for e in rep["errors"] if e["rule"] == "codepoint-disagreement"]


def test_the_spec_parse_reads_the_right_tables():
    """Header-driven and section-scoped, because two tables in that file have
    the same shape and opposite meanings: §3's rows are a forbidden lookalike
    beside the codepoint that should have been keyed instead, and sniffing for
    something codepoint-shaped picks them up as if they were sorts."""
    spec = alphabet.spec_codepoints(REPO)
    assert spec[n("ä")] == "a + U+0308"    # §2.2, whose codepoint column is NFD
    assert spec["ʟ"] == "U+029F"           # §2.3, whose column is Codepoint
    assert "´" not in spec and "·" not in spec, "§3's lookalikes leaked in"


def test_every_grid_cell_is_a_sort_the_store_lists():
    """A chart drawn from a grid naming a sort with no entry has a hole in it
    where a glyph should be, and nothing else would report that."""
    store = alphabet.load(REPO)
    listed = {s["sort"] for s in store["sorts"]}
    for name, grid in store["grids"].items():
        cells = {c for row in grid["rows"] for c in row["cells"] if c}
        assert cells <= listed, f"{name} grid names sorts the store does not list"


def test_the_vowel_grid_is_the_arrangement_and_not_an_alphabet():
    """Mythology's rows are the analysis, which is the reason to reproduce them:
    ä sits over a as its long counterpart, and ŭ sits *under* u with the obscure
    short series rather than beside it. p. 10's flat list shows neither."""
    rows = alphabet.load(REPO)["grids"]["vowels"]["rows"]
    assert [r["cells"][2] for r in rows] == n(["ä", "a", "ᴀ"])
    assert rows[1]["cells"][4] == "u" and rows[2]["cells"][4] == n("ŭ")


def test_the_consonant_grid_records_his_place_names_not_ours():
    """`k` and `ñ` on his Palatal row and `q`, `g̣`, `h` on his Velar row — so
    his "velar" is modern uvular and his "palatal" modern velar. Reading that
    row label as a place claim is what made an earlier audit argue `g̣` was
    uvular, which the modern inventory does not support."""
    rows = {r["label"]: [c for c in r["cells"] if c]
            for r in alphabet.load(REPO)["grids"]["consonants"]["rows"]}
    assert set(rows["Velar"]) == n({"g̣", "h", "q"})
    assert set(rows["Palatal"]) == n({"k", "ñ"})


def test_the_four_gaps_are_entries_and_not_omissions():
    """ë, ḷ, ṛ and š have a gloss in the key and no IPA value, because turning
    a gloss into a symbol is a judgement. They are on the chart *as* sorts with
    no value — an omission would read as the key not having them."""
    chart = alphabet.chart(REPO)
    gaps = {r["sort"] for r in chart["sorts"] if not r["ipa"]}
    assert n({"ë", "ḷ", "ṛ", "š"}) <= gaps
    for r in chart["sorts"]:
        if not r["ipa"]:
            assert r["why"], f"{r['sort']} is blank with no reason given"


def test_the_chart_carries_both_readings_side_by_side():
    """`ipa` is Bogoras's own account and `modern` is a current description's,
    and they part systematically. A row showing one of them has answered a
    question the reader did not ask."""
    by = alphabet.chart(REPO)["by_sort"]
    assert by["a"]["ipa"] == "aː" and by["a"]["modern"] == "a"
    # length: his, not modern's
    assert by["a"]["ipa"].endswith("ː") and "ː" not in by["a"]["modern"]
    # a sort with no modern counterpart says so rather than going blank
    assert by["g"]["ipa"] == "ɡ" and not by["g"]["modern"]
    assert "loanword" in by["g"]["modern_note"]


def test_a_sorts_attestation_counts_forms_and_not_occurrences():
    """"How much of the book does this sort unlock" is a question about forms.
    Counted over the keyed corpus only, which is why a zero is not a claim that
    the book does not print it."""
    chart = alphabet.chart(REPO)
    assert chart["attested_forms"] > 500
    assert chart["by_sort"]["g̣"]["forms"] > 50
    assert all(r["forms"] <= chart["attested_forms"] for r in chart["sorts"])


def test_anchors_are_positional_rather_than_the_sort_itself():
    """A fragment holding a combining sequence is legal and unusable, and `ʟ̣`
    and `ʟ` would differ in a URL by an invisible character."""
    anchors = [r["anchor"] for r in alphabet.chart(REPO)["sorts"]]
    assert len(set(anchors)) == len(anchors)
    assert all(a.isascii() for a in anchors)


# ------------------------------------------------------------ the gate


def _store(tmp_path: Path, doc) -> Path:
    tmp_path.joinpath("edition").mkdir(parents=True, exist_ok=True)
    tmp_path.joinpath("edition", "alphabet.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_a_stale_ipa_flag_fails(tmp_path: Path):
    """The flag is the store's claim about the rule table, and a stale one is
    worse than none: it decides whether the chart prints a value or a dash."""
    _store(tmp_path, {"sorts": [{"sort": "a", "codepoint": "U+0061",
                                 "ipa": False, "glosses": []}], "grids": {}})
    rules = {e["rule"] for e in alphabet.check(tmp_path)["errors"]}
    assert "ipa-flag-stale" in rules


def test_a_grid_cell_with_no_entry_fails(tmp_path: Path):
    _store(tmp_path, {
        "sorts": [{"sort": "a", "codepoint": "U+0061", "ipa": True, "glosses": []}],
        "grids": {"vowels": {"rows": [{"label": "", "cells": ["a", "ø"]}]}}})
    errs = alphabet.check(tmp_path)["errors"]
    assert any(e["rule"] == "grid-cell-unknown" for e in errs)


def test_a_codepoint_disagreement_fails(tmp_path: Path):
    """The whole point of holding the fact twice."""
    (tmp_path / "keying_spec.md").write_text(
        "### 2.3 Letters\n\n| Glyph | Codepoint |\n|---|---|\n| ʟ | U+029F |\n",
        encoding="utf-8")
    _store(tmp_path, {"sorts": [{"sort": "ʟ", "codepoint": "U+FFFF",
                                 "ipa": True, "glosses": []}], "grids": {}})
    errs = alphabet.check(tmp_path)["errors"]
    assert any(e["rule"] == "codepoint-disagreement" for e in errs)


def test_a_missing_store_is_empty_rather_than_an_error(tmp_path: Path):
    """A store, so absence is emptiness — the fresh-clone rule."""
    assert alphabet.load(tmp_path)["sorts"] == []
    assert alphabet.chart(tmp_path)["sorts"] == []


@pytest.mark.parametrize("spelling", ["a + U+0308", "a+U+0308", "a  +  U+0308"])
def test_codepoint_spellings_compare_equal(tmp_path: Path, spelling: str):
    (tmp_path / "keying_spec.md").write_text(
        "### 2.2 Letters\n\n| Sort | Key gloss | NFD |\n|---|---|---|\n"
        "| ä | obscure vowel | a + U+0308 |\n", encoding="utf-8")
    _store(tmp_path, {"sorts": [{"sort": "ä", "codepoint": spelling,
                                 "ipa": True, "glosses": []}], "grids": {}})
    assert not [e for e in alphabet.check(tmp_path)["errors"]
                if e["rule"] == "codepoint-disagreement"]
