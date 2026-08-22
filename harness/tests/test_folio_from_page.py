"""The folio the page itself states, and where it is looked for.

`expected_folio` is a prediction from the preceding transcribed page and knows
nothing about this one. This is the second witness — the page's own statement —
and the two disagreeing is the signal the pair exists to raise.

The three zones are tested separately because the book prints the number in three
places and the corpus spells them in two vocabularies. Verified against the three
collated pages: `1-100`/`1-101` extract 74/75 and `1-151` extracts 115 through its
brackets, each matching the `<pb n>` a human wrote.
"""
from __future__ import annotations

import pytest

from harness.context import _running_title
from harness.refs import FOLIO_ZONES, _folio_in, _window_folio
from harness.state import toc_window


def _line(text, zone, hpos=0, vpos=0, height=50):
    return {"text": text, "zone": zone, "hpos": hpos, "vpos": vpos,
            "height": height}


def test_the_ordinary_page_reads_its_head_line(tmp_path):
    recs = [_line("BOGORAS, THE CHUKCHEE.", "RunningTitleZone", hpos=1305),
            _line("223", "RunningTitleZone", hpos=2044),
            _line("Scissors used throughout", "MainZone-P", vpos=700)]
    rep = _running_title(recs, "1-283", tmp_path)
    assert rep["folio"] == "223"
    assert rep["folio_from"] == "RunningTitleZone"
    assert rep["bracketed"] is False
    assert rep["text"] == "BOGORAS, THE CHUKCHEE.", "the folio leaves the title"


def test_a_chapter_opening_reads_its_bracketed_quire_mark(tmp_path):
    """`1-151`: no running title at all, the number set at the foot in brackets,
    and the collated TEI reads `<pb n="115"/>`. `text` is empty and `folio` is
    not — the two are independent."""
    recs = [_line("[115]", "QuireMarksZone", vpos=3231)]
    rep = _running_title(recs, "1-151", tmp_path)
    assert rep["folio"] == "115"
    assert rep["folio_from"] == "QuireMarksZone"
    assert rep["bracketed"] is True
    assert rep["text"] == ""


def test_the_old_vocabulary_is_read_too(tmp_path):
    """`gt/ocr/` descends from the full-SegmOnto scheme, which split the folio out
    as `NumberingZone`. That store is where the collation frontier is, so a rule
    knowing only the current spelling would find the head and never the number."""
    recs = [_line("28", "NumberingZone", hpos=726),
            _line("BOGORAS, THE CHUKCHEE.", "RunningTitleZone", hpos=1308)]
    rep = _running_title(recs, "1-048", tmp_path)
    assert rep["folio"] == "28"
    assert rep["folio_from"] == "NumberingZone"
    assert rep["text"] == "BOGORAS, THE CHUKCHEE."


def test_the_running_title_wins_over_the_other_two(tmp_path):
    """Precedence is confidence, not frequency. A page offering a number in more
    than one place is answered from the head line."""
    recs = [_line("223", "RunningTitleZone", hpos=2044),
            _line("[9]", "QuireMarksZone", vpos=3231),
            _line("7", "NumberingZone", hpos=100)]
    rep = _running_title(recs, "1-283", tmp_path)
    assert (rep["folio"], rep["folio_from"]) == ("223", "RunningTitleZone")
    assert FOLIO_ZONES[0] == "RunningTitleZone"


def test_an_unparseable_number_yields_null_and_keeps_the_line(tmp_path):
    """A recognizer's `2S` for `28` must not become a page number. Null, and the
    text stays where a human can read it — the `expected_folio` contract."""
    recs = [_line("BOGORAS, THE CHUKCHEE.", "RunningTitleZone", hpos=1305),
            _line("2S", "RunningTitleZone", hpos=2044)]
    rep = _running_title(recs, "1-283", tmp_path)
    assert rep["folio"] is None and rep["folio_from"] is None
    assert "2S" in rep["text"], "an unread number is not silently dropped"


def test_a_number_inside_a_line_is_not_a_folio(tmp_path):
    """Only a line that is *nothing but* a number counts. The signature line
    `9-JESUP NORTH PACIFIC EXPED.` opens with a digit and is not a folio."""
    assert _folio_in([_line("9-JESUP NORTH PACIFIC EXPED.", "QuireMarksZone")]) is None
    assert _folio_in([_line("Fig. 151, c", "MainZone-P")]) is None


def test_roman_numerals_parse():
    """Part 1's front matter is printed xii-xvii."""
    assert _folio_in([_line("xiv", "RunningTitleZone")]) == ("xiv", False)
    assert _folio_in([_line("XIV", "RunningTitleZone")]) == ("XIV", False)


def test_a_half_open_bracket_does_not_parse():
    """`[115` is a recognizer dropping a character, not a page number."""
    assert _folio_in([_line("[115", "QuireMarksZone")]) is None
    assert _folio_in([_line("115]", "QuireMarksZone")]) is None


def test_a_page_with_none_of_the_three_zones_is_null(tmp_path):
    """A plate carries no folio anywhere, and that is a real state rather than a
    failure to find one."""
    assert _running_title([_line("body", "MainZone-P")], "1-167", tmp_path) is None


# --- what a @facs pointer may cite -----------------------------------------

def test_ocr_lines_omits_what_no_facs_could_point_at(tmp_path):
    """`ocr_lines` is the set of pointer targets offered to the collation pass.

    The running head, the folio and the signature line are never in the TEI body,
    so a `@facs` citing one would be a mistake by construction — a stronger reason
    than the draft's, which drops them merely as the printer's text.

    Asserted through the real reader over a real file, because the filter reads
    `zone`, which only exists once the ALTO carries labels.
    """
    from harness.context import _ocr_lines
    ns = "http://www.loc.gov/standards/alto/ns-v4#"
    p = tmp_path / "ocr" / "chukchi-1-283.xml"
    p.parent.mkdir(parents=True)
    p.write_text(
        f'<alto xmlns="{ns}"><Layout><Page><PrintSpace>'
        '<TextBlock ID="r1" TAGREFS="T1"><TextLine ID="l1">'
        '<String CONTENT="BOGORAS, THE CHUKCHEE."/></TextLine>'
        '<TextLine ID="l2"><String CONTENT="223"/></TextLine></TextBlock>'
        '<TextBlock ID="r2" TAGREFS="T2"><TextLine ID="l3">'
        '<String CONTENT="Scissors used throughout"/></TextLine></TextBlock>'
        '<TextBlock ID="r3" TAGREFS="T3"><TextLine ID="l4">'
        '<String CONTENT="9-JESUP NORTH PACIFIC EXPED."/></TextLine></TextBlock>'
        "</PrintSpace></Page></Layout>"
        f'<Tags><OtherTag ID="T1" TYPE="type" LABEL="RunningTitleZone"/>'
        '<OtherTag ID="T2" TYPE="type" LABEL="MainZone-P"/>'
        '<OtherTag ID="T3" TYPE="type" LABEL="QuireMarksZone"/></Tags>'
        "</alto>", encoding="utf-8")

    got = _ocr_lines(p)
    assert [r["text"] for r in got] == ["Scissors used throughout"]
    # `index` is an identity from ALTO document order, not a position in this
    # list, so dropping records must not renumber the survivor.
    assert got[0]["index"] == 2
    # And it is the *only* handle offered. `line_id` was the ALTO `@ID`, which no
    # harness verb accepts — `ocr zoom --only` has always taken the index — so a
    # citation written in it had to be translated by hand before anyone could act
    # on it. Nothing may reintroduce a second currency here.
    assert set(got[0]) == {"index", "text"}


# The window the folio centres, and the cold start that left it empty.
#
# `toc_window` filters ToC entries by distance from `expected_folio`, which is a
# prediction from the preceding *collated* page — so at the front of any run it is
# null, the distance test never fires, and the window falls back to `believed_open`,
# itself a fold over collated pages and likewise empty. Every heading on that page
# then matches no entry and becomes an unresolved comment. Serially that was one
# page; under a dispatched batch it is all of them.

def test_the_window_falls_back_to_the_page_s_own_folio():
    """The running title is the better witness anyway — the page saying what page
    it is, against a neighbour's arithmetic."""
    assert _window_folio(None, {"folio": "53"}) == (53, "running_title")
    toc = [{"id": "chIII", "level": 1, "title": "Trade", "page_start": 53},
           {"id": "chIV", "level": 1, "title": "War", "page_start": 90}]
    assert toc_window(toc, None, []) == [], "the state this fixes"
    got = toc_window(toc, 53, [])
    assert [e["id"] for e in got] == ["chIII"] and got[0]["starts_here"]


def test_a_prediction_wins_where_there_is_one():
    """The fallback is for the absence, not a preference. Where both witnesses exist
    the window keeps centring on the prediction, so the two stay independent and the
    disagreement between them remains the signal it was built to be."""
    assert _window_folio(74, {"folio": "75"}) == (74, "expected_folio")


def test_both_witnesses_absent_is_a_state_the_payload_names():
    """`running_title.folio` is transcribed content, so a string, and not always an
    integer — a number that did not read cleanly stays in `text` with `folio` null.
    An empty window alone cannot say whether nothing was near this folio or there was
    no folio to be near, so the witness says which."""
    for bad in (None, "", "5]", "liii", "1-075"):
        assert _window_folio(None, {"folio": bad}) == (None, "none"), bad
    assert _window_folio(None, None) == (None, "none"), "no running title at all"


def test_the_prediction_is_never_filled_from_the_page_itself():
    """The whole point of the pair, asserted on the live page rather than in the
    abstract. `1-075` opens the trade chapter with nothing collated before it, so the
    prediction is genuinely absent. `expected_folio` must stay null — arriving with
    this page's own folio in it would leave `<pb>` checked against itself, a
    comparison whose witnesses are one witness — while the window still centres on 53
    and both of the page's headings become reachable."""
    from pathlib import Path

    from harness.context import build_context
    repo = Path(__file__).resolve().parent.parent.parent
    if not (repo / "ocr" / "chukchi-1-075.xml").exists():
        pytest.skip("1-075 has no OCR in this checkout")
    ctx = build_context("1-075", repo)
    assert ctx["expected_folio"] is None, "the prediction stays absent"
    assert ctx["toc_window_folio"] == {"folio": 53, "witness": "running_title"}
    starts = {e["id"] for e in ctx["toc_window"] if e["starts_here"]}
    assert starts == {"chIII", "chIII.1"}, (
        "III. — TRADE. and ANCIENT TRADE., the two headings 1-075 prints; with the "
        "empty window they matched nothing and became unresolved comments")
