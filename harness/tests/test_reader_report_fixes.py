"""What the chapter-by-chapter read of the edition found, held down.

Each of these is a page a reader met: `3-146`'s chapter title set as a run-in,
`3-148`'s WARS centred above its own run-in, `2-068`'s Fig. 240 missing, `1-098`'s
notes folded into one, and words left broken in the middle of a sentence.
"""
from __future__ import annotations

from pathlib import Path

from harness import tei_html
from harness.detectors import resolve_break_hyphens
from harness.generate import _split_notes
from harness.web.edition import _pooled_notes

TITLES = {
    "chXXIII": {"number": "XXIII", "title": "Contact"},
    "chXXIII.2": {"number": "", "title": "Wars"},
    "chXXIII.3": {"number": "", "title": "Seventeenth Century Wars"},
    "chVI": {"number": "VI", "title": "Hunting"},
    "chVI.1": {"number": "", "title": "Hunting and fishing"},
    "chVI.2": {"number": "", "title": "Seal-Hunting"},
}


def _render(tmp_path: Path, body: str) -> str:
    p = tmp_path / "tei" / "chukchi-3-148.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><pb n="682"/>{body}'
                 '</body></text></TEI>', encoding="utf-8")
    return tei_html.render(p, TITLES)["html"]


def test_two_milestones_and_two_labels_are_both_run_in(tmp_path):
    got = _render(tmp_path,
                  '<milestone unit="section" n="chXXIII.2"/>'
                  '<milestone unit="subsection" n="chXXIII.3"/>'
                  '<p><label>WARS.</label> <label>Seventeenth Century Wars.</label>'
                  ' — Soon after</p>')
    assert "<h2" not in got
    assert '<span class="milestone anchor section" id="chXXIII.2"></span>' in got
    assert '<span class="milestone anchor subsection" id="chXXIII.3"></span>' in got


def test_one_label_answers_only_the_last_of_three_milestones(tmp_path):
    got = _render(tmp_path,
                  '<milestone unit="chapter" n="chVI"/>'
                  '<milestone unit="section" n="chVI.1"/>'
                  '<milestone unit="subsection" n="chVI.2"/>'
                  '<p><label>SEAL-HUNTING.</label> — The Maritime Chukchee</p>')
    assert '<h2 class="milestone chapter" id="chVI">' in got
    assert '<h2 class="milestone section" id="chVI.1">' in got
    assert '<span class="milestone anchor subsection" id="chVI.2"></span>' in got


def test_a_head_with_nothing_but_its_note_marker_is_a_head(tmp_path):
    got = _render(tmp_path,
                  '<milestone unit="chapter" n="chXXIII"/>'
                  '<p><label>XXIII. — CONTACT.</label><ref type="note" n="1">¹</ref></p>'
                  '<p>The first information</p>'
                  '<note n="1" place="bottom">The sketch.</note>')
    assert 'class="runin"' not in got
    assert '<h2 class="milestone chapter">' in got
    assert 'id="chXXIII"' in got
    assert '<span class="milestone-t">Contact' in got and 'CONTACT.' not in got
    assert 'href="#note-1"' in got


def test_a_minor_head_is_italic_by_its_own_case(tmp_path):
    got = _render(tmp_path,
                  '<milestone unit="subsection" n="chXXIII.3"/>'
                  '<p><label>Wars in the Eighteenth Century.</label> — In 1701</p>'
                  '<p><label>CHIEF <foreign>Kaˊcak</foreign>.</label> — A</p>')
    assert '<span class="runin runin-title">Wars in the' in got
    assert '<span class="runin">CHIEF' in got


def test_notes_a_keyed_line_runs_on_without_a_space_are_cut():
    rows = [(1, "¹ Krasheninnikoff, II, p. 204.² Bogoras, p. 352.³ Ibid., p. 342.")]
    assert [m for m, _ in _split_notes(rows)] == ["¹", "²", "³"]


def test_a_figure_locant_is_not_a_note():
    rows = [(1, "¹ See the thimble (Fig. 155, d² ) and the rest.")]
    assert [m for m, _ in _split_notes(rows)] == ["¹"]


def test_the_lexicon_decides_only_where_the_corpus_is_silent():
    def closed(tok, cuts, idx):
        return resolve_break_hyphens(tok, cuts, "1-001", idx, {"complexion", "sealskin",
                                                                "reindeer"})
    assert closed("com-plexion", [3], {})[0] == "complexion"
    assert closed("com-plexion", [3], {})[1][0]["verdict"] == "lexicon"
    witnessed = {"seal-skin": (81, frozenset({"1-002", "1-003"}))}
    assert closed("seal-skin", [4], witnessed)[0] == "seal-skin"
    assert closed("powder-meat", [6], {})[1][0]["verdict"] == "open"
    assert closed("rein-deer-hunts", [4], {})[0] == "reindeer-hunts"


def test_a_note_the_turn_cut_is_one_note_in_the_chapter():
    leaves = [
        {"ref": "3-044", "folio": 578, "doc": {"notes": [
            {"n": "4", "i": 1, "html": "hands were too sinful to take"}]}},
        {"ref": "3-045", "folio": 579, "doc": {"notes": [
            {"n": "", "i": 1, "html": "part in the holy act"},
            {"n": "1", "i": 2, "html": "Another."}]}},
    ]
    got = _pooled_notes(leaves)
    assert got[0]["notes"][0]["html"] == "hands were too sinful to take part in the holy act"
    assert [n["n"] for n in got[1]["notes"]] == ["1"]
    assert leaves[0]["doc"]["notes"][0]["html"] == "hands were too sinful to take"
