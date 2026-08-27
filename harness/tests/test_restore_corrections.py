"""`restore` writes each line's text into the store that line came from.

A page's lines are now the ALTO's plus `gt/lines/`'s, so the one writer of
ground-truth *text* has two files to write. The join to the fragment is by `corr_`
id rather than by position, because the fragment is ordered by geometry and a
human may have nudged a box since; the id is minted once and travels with it.

**The sharp edge is the verification, not the write.** `restore` proves its own
write by comparing `page_lines(src)` against `page_lines(tmp)`, and `tmp` is
`chukchi-PP-NNN.xml.tmp` — a stem that parses as no ref. Left to that derivation
one side folds the corrections and the other does not, and the failure surfaces as
this function reporting that its own write lost lines: a guard that exists to catch
a real fault, firing on a page where nothing is wrong. Hence the explicit `ref` on
both calls, and hence these tests, which would fail loudly rather than subtly.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from lxml import etree
from PIL import Image

from harness import corrections as corr
from harness.review import restore

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
BOX = {"x0": 900, "y0": 300, "x1": 990, "y1": 340}


def _decisions(root: Path, ref: str, texts: dict[int, str]) -> None:
    """Decisions, and the proposal they were adjudicated from.

    `restore` reads both — its `edits` table names what the adjudicator changed,
    which is the only record of what readers actually get wrong.
    """
    p = root / "review" / ref
    p.mkdir(parents=True, exist_ok=True)
    (p / "decision.json").write_text(json.dumps(
        {"lines": {str(k): {"text": v} for k, v in texts.items()}}),
        encoding="utf-8")
    (p / "proposal.json").write_text(json.dumps(
        {"lines": {str(k): {"text": v} for k, v in texts.items()}}),
        encoding="utf-8")


@pytest.fixture
def page(tmp_path: Path):
    """Two ground-truth lines, one correction, and a decision for all three."""
    (tmp_path / "scans").mkdir()
    Image.new("RGB", (1200, 1600), "white").save(
        tmp_path / "scans" / "chukchi-1-048.png")
    (tmp_path / "config").mkdir()
    shutil.copy(Path("config") / "zones_config.json", tmp_path / "config")

    lines = "".join(
        f'<TextLine ID="l{i}" HPOS="100" VPOS="{1000 + i * 100}" WIDTH="800" '
        f'HEIGHT="60"><String CONTENT="" HPOS="100" VPOS="{1000 + i * 100}" '
        f'WIDTH="800" HEIGHT="60"/></TextLine>' for i in range(2))
    alto = tmp_path / "gt" / "ocr" / "chukchi-1-048.xml"
    alto.parent.mkdir(parents=True)
    alto.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><alto xmlns="{ALTO_NS}"><Layout>'
        f'<Page WIDTH="1200" HEIGHT="1600"><PrintSpace HPOS="0" VPOS="0" '
        f'WIDTH="1200" HEIGHT="1600"><TextBlock ID="b1">{lines}'
        "</TextBlock></PrintSpace></Page></Layout></alto>", encoding="utf-8")

    corr.save_lines("1-048", [BOX], tmp_path)
    return tmp_path, alto


def _restore(root, **kw):
    return restore("1-048", root, "gt/ocr", **kw)


def test_a_page_with_a_correction_restores_at_all(page):
    """The regression this file exists for. With the fold applied to one side of
    the verification only, this raises "the write lost or gained lines"."""
    tmp_path, _ = page
    _decisions(tmp_path, "1-048", {0: "first", 1: "second", 2: "17"})
    rep = _restore(tmp_path, commit=True)
    assert rep["lines"] == 3
    assert rep["corrections"] == 1
    assert rep["geometry_drift"] == []
    assert rep["text_mismatch"] == []


def test_the_correction_text_lands_in_the_fragment(page):
    tmp_path, _ = page
    _decisions(tmp_path, "1-048", {0: "first", 1: "second", 2: "17"})
    _restore(tmp_path, commit=True)
    assert [r["text"] for r in corr.load_lines("1-048", tmp_path)] == ["17"]


def test_the_altos_own_lines_land_in_gt_ocr(page):
    tmp_path, alto = page
    _decisions(tmp_path, "1-048", {0: "first", 1: "second", 2: "17"})
    _restore(tmp_path, commit=True)
    got = [s.get("CONTENT")
           for s in etree.parse(str(alto)).getroot().iter("{*}String")]
    assert got == ["first", "second"]


def test_gt_ocr_never_gains_the_corrected_line(page):
    """The fragment is where it lives. A second copy in `gt/ocr/` would be two
    records of one line, free to disagree — and `page_lines` would merge it in
    twice."""
    tmp_path, alto = page
    _decisions(tmp_path, "1-048", {0: "first", 1: "second", 2: "17"})
    _restore(tmp_path, commit=True)
    ids = [tl.get("ID")
           for tl in etree.parse(str(alto)).getroot().iter("{*}TextLine")]
    assert ids == ["l0", "l1"]


def test_a_correction_without_a_decision_is_a_partial_restore(page):
    """A corrected line with no decision is a hole in ground truth exactly as an
    unadjudicated ALTO line is — the merged index space is what makes the existing
    guard see it at all."""
    tmp_path, _ = page
    _decisions(tmp_path, "1-048", {0: "first", 1: "second"})
    with pytest.raises(ValueError, match="no decision"):
        _restore(tmp_path, commit=True)


def test_the_preview_writes_neither_store(page):
    tmp_path, alto = page
    _decisions(tmp_path, "1-048", {0: "first", 1: "second", 2: "17"})
    before_alto = alto.read_bytes()
    before_frag = corr.lines_path("1-048", tmp_path).read_bytes()

    rep = _restore(tmp_path, commit=False)
    assert rep["commit"] is False
    assert alto.read_bytes() == before_alto
    assert corr.lines_path("1-048", tmp_path).read_bytes() == before_frag


def test_text_already_in_the_fragment_needs_force(page):
    """The overwrite guard counts the fragment too. A corrected line's reading
    lives there and nowhere else, so a guard reading only `gt/ocr/` would wave
    through the overwrite of the one text with no second copy."""
    tmp_path, _ = page
    _decisions(tmp_path, "1-048", {0: "", 1: "", 2: "17"})
    _restore(tmp_path, commit=True)
    with pytest.raises(ValueError, match="already holds"):
        _restore(tmp_path, commit=True)
    _restore(tmp_path, commit=True, force=True)   # force is how you say you meant it


def test_the_report_has_one_key_set_either_way(page):
    """The rule the report already followed, extended to the new field."""
    tmp_path, _ = page
    _decisions(tmp_path, "1-048", {0: "first", 1: "second", 2: "17"})
    preview = _restore(tmp_path, commit=False)
    committed = _restore(tmp_path, commit=True)
    assert set(preview) == set(committed)
    assert "corrections" in preview
