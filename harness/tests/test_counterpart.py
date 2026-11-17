"""A Materials native form's counterpart in *The Chukchee*, by the text's table.

Against the real `config/counterpart.json` and hand-made *Chukchee* forms, so the
cases are the pilot batch's own (`docs/multitext.md`, "Counterparts in *The
Chukchee*"). The match is a witness against a misreading: exact where a derived
spelling is ratified there, near where only a mark, an obscure vowel, an ending
or a compound's part separates them.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from harness import counterpart as cp

MATERIALS = Path(__file__).resolve().parents[2] / "jesup" / "bogoras-materials"
CHUKCHEE = ["Kuˊrkɪl", "vaˊɪrg̣ɪn", "Kaˊmak", "Aiñanwaˊt", "Taˊn˙ñɪn",
            "Taˊn˙ñɪn-wêˊthaw", "qor-êmtêˊ-qaˊa-raˊmkɪt", "Meeˊmhɪn", "Kaitakaˊlhɪn",
            "Emeˊmqut"]


def nfd(s):
    return unicodedata.normalize("NFD", s)


@pytest.fixture(scope="module")
def t():
    return cp.table(MATERIALS)


@pytest.fixture(scope="module")
def oidx(t):
    return cp.index_forms({nfd(f): {"form": nfd(f), "refs": {"1-001"},
                                    "lines": [{"ref": "1-001", "line": "3",
                                               "text": f"the {f} line"}]}
                           for f in CHUKCHEE}, t)


@pytest.mark.parametrize("form, status, other", [
    ("Ку́ркыl", "exact", "Kuˊrkɪl"),
    ("ва́ырђын", "exact", "vaˊɪrg̣ɪn"),             # ђ is g̣
    ("кајтака́lђын", "exact", "Kaitakaˊlhɪn"),      # and h, ј is i
    ("кама́к", "near", "Kaˊmak"),                   # the stress on another vowel
    ("Ајӈан̀ва́т", "near", "Aiñanwaˊt"),              # a grave The Chukchee lacks
    ("та́н̀ӈен", "near", "Taˊn˙ñɪn"),                 # е for the obscure ɪ
    ("Мээ́мђына", "near", "Meeˊmhɪn"),               # a Russian ending
    ("wе́т̀һаw", "near", "Taˊn˙ñɪn-wêˊthaw"),         # a part of their compound
    ("ӄор-емте́", "near", "qor-êmtêˊ-qaˊa-raˊmkɪt"),  # our compound, part of theirs
    ("Эмэмку́т", "near", "Emeˊmqut"),               # к for q (allophones); stress elsewhere
    ("терк-арм", "none", None),
])
def test_match(t, oidx, form, status, other):
    m = cp.match(nfd(form), MATERIALS, t, oidx)
    assert m["status"] == status
    if other:
        assert nfd(other) in [r["form"] for r in m["matches"]]
        assert m["matches"][0]["line"].startswith("1-001 l3: ")


def test_the_obscure_vowel_is_never_exact(t, oidx):
    """`е` against *ɪ* may be a vowel each book wrote its own way or an ending that
    differs, so it is a near miss for the editor to judge, never agreement."""
    assert cp.match(nfd("та́н̀ӈен"), MATERIALS, t, oidx)["status"] == "near"


def test_every_pair_carries_its_attestation(tmp_path):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config/counterpart.json").write_text(
        '{"text": "x", "pairs": {"а": "a"}, "_why": {}}', encoding="utf-8")
    with pytest.raises(cp.CounterpartError, match="_why"):
        cp.table(tmp_path)


def test_a_text_without_a_table_has_no_counterparts():
    assert cp.table(MATERIALS.parent / "bogoras-chukchi") is None


def test_what_a_reader_was_shown_is_the_verbs_record(tmp_path):
    """The review page marks a form whose counterpart the reader saw; the record
    is the verb's, appended, never the reader's own statement."""
    from conftest import write_project
    root = write_project(tmp_path / "t")
    cp.record_shown("1-031", root, [{"form": "кама́к", "matches": [{"form": "Kaˊmak"}]}])
    cp.record_shown("1-031", root, [{"form": "ва́ырђын", "matches": []}])
    assert cp.shown("1-031", root) == {"Kaˊmak"}
    assert cp.shown("1-032", root) == set()


def test_an_editors_short_element_is_matched_and_glossed(t):
    """`ӄор` and `lые` are three letters, under MIN_LETTERS, so their compounds'
    parts were never tried; the editor glossed them (2026-11-17), and a listed
    element is matched marks aside, near only, and carries its gloss."""
    oidx = cp.index_forms({nfd(f): {"form": nfd(f), "refs": {"1-001"}, "lines": []}
                           for f in ["Lɪˊê-taˊn˙ñɪt", "waˊwa-qor", "pɪˊñɪl"]}, t)
    m = cp.match(nfd("lые-кука́төlӄај"), MATERIALS, t, oidx)
    assert m["status"] == "near"
    assert [r["form"] for r in m["matches"]] == [nfd("Lɪˊê-taˊn˙ñɪt")]
    assert m["glosses"] == [{"element": nfd("lые"), "gloss": "true, genuine"}]
    assert nfd("waˊwa-qor") in [r["form"] for r in
                                cp.match(nfd("ӄор-емте́"), MATERIALS, t, oidx)["matches"]]
    # An unlisted three-letter part is still skipped: `пыӈ` reaches nothing.
    assert cp.match(nfd("пыӈ-кука́"), MATERIALS, t, oidx)["status"] == "none"


def test_an_element_carries_its_gloss_and_why(tmp_path):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config/counterpart.json").write_text(
        '{"text": "x", "pairs": {"а": "a"}, "_why": {"а": "w"},'
        ' "elements": {"ӄор": {"gloss": "reindeer"}}}', encoding="utf-8")
    with pytest.raises(cp.CounterpartError):
        cp.table(tmp_path)
