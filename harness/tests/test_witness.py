"""A witness copy is set beside the master by text, never by index.

The pairing and the alignment are the two places a fixed offset would silently
compare a line with its neighbour, so each is tested against the case that
breaks an offset: a page scanned twice, and a line one copy has and the other
does not.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_project

from harness import witness
from harness.layout import ProjectError, project


def test_lines_are_aligned_by_text_not_by_index():
    a = ["первая строка текста", "вторая строка", "третья строка здѣсь"]
    b = ["первая строка текста", "лишняя", "вторая строка", "третья строка здѣсь"]
    got = witness.align(a, b)
    assert [(i, j) for i, j, _ in got] == [(0, 0), (None, 1), (1, 2), (2, 3)]


def test_two_different_lines_are_never_one_line_read_badly():
    got = witness.align(["абвгд"], ["эюяшщ"])
    assert {(i, j) for i, j, _ in got} == {(0, None), (None, 0)}


def test_a_line_the_witness_lacks_is_alone():
    got = witness.align(["одна строка", "другая строка"], ["одна строка"])
    assert (1, None, 0.0) in got


def _text(tmp_path: Path, wmap: dict | None = None) -> Path:
    t = write_project(tmp_path / "t")
    rec = json.loads((t / "project.json").read_text(encoding="utf-8"))
    w = {"id": "b", "pdf": "pdfs/witness/b.pdf", "label": "copy B"}
    if wmap is not None:
        w["map"] = wmap
    rec["witnesses"] = [w]
    (t / "project.json").write_text(json.dumps(rec), encoding="utf-8")
    return t


def test_a_ruled_pairing_is_a_ref_to_a_page(tmp_path):
    t = _text(tmp_path, {"1-058": 60})
    assert project(t)["witnesses"][0]["map"] == {"1-058": 60}


@pytest.mark.parametrize("bad", [{"58": 60}, {"1-058": "60"}, {"1-058": 0},
                                 {"1-058": True}, ["1-058"]])
def test_a_malformed_ruling_is_refused(tmp_path, bad):
    t = _text(tmp_path, bad)
    with pytest.raises(ProjectError):
        project(t)


def test_an_unpaired_page_is_refused_with_its_reason(tmp_path):
    t = _text(tmp_path)
    (t / "data").mkdir(exist_ok=True)
    (t / "data/witness-b.json").write_text(json.dumps(
        {"map": {"1-012": 12}, "ambiguous": {"1-058": []}, "unmatched": [],
         "empty": ["1-004"]}), encoding="utf-8")
    assert witness.page_of("1-012", t, "b") == 12
    with pytest.raises(witness.WitnessError, match="rule it"):
        witness.page_of("1-058", t, "b")
    with pytest.raises(witness.WitnessError, match="empty"):
        witness.page_of("1-004", t, "b")


def test_the_margin_refuses_the_doubly_scanned_page():
    """Measured on the real copies: 1-058 scores 0.774 against one scan of its page
    and 0.709 against the other. The margin must be wider than that gap, and
    narrower than the gap between a true pair (≥ 0.55) and a neighbour (≤ 0.16)."""
    assert 0.774 - 0.709 < witness.MARGIN < 0.55 - 0.16
