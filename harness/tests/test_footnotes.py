"""Footnote-marker consistency: the two counting invariants, and the hole they leave.

A footnote marker is printed twice — at the reference in the body and again
opening the note at the foot — and numbering restarts on every page. That makes
two invariants checkable with no reading at all: the values form a continuous
run from 1, and each occurs at least twice.

Why this detector exists at all: a marker keyed as a plain ASCII digit is the
*right number*, so it reads as correct in every downstream view, and no
lookalike grep, lexicon check or mark licence can see it. It was found on
`1-048` only by eye. Counting is the only mechanical witness.

The tests below pin the failure modes AND the two known false-positive shapes,
because the point of the detector is that it fires on real defects and stays
quiet on ordinary text — a detector firing on the ordinary case buries the
real hits (CLAUDE.md, "Transcription Detection").
"""
import json

from harness.detectors import footnote_report
from harness.proposal_check import check


def test_clean_page_passes():
    """Three markers, each twice, continuous — the ordinary case (`1-048` revised)."""
    rep = footnote_report([
        "also accurate.¹",
        "the Anadyr River.² The Russians subsequently founded",
        "narrow island Mɪˊs˙qᴀn, ³ in Holy Cross Bay; and",
        "¹ In his statistics, Krause gives for the large village",
        "² On the Middle Anadyr live about ten Chukchee families",
        "³ Long, narrow islands or spits, consisting of sand",
    ])
    assert rep["counts"] == {1: 2, 2: 2, 3: 2}
    assert rep["gaps"] == []
    assert rep["singletons"] == []
    assert rep["ascii_openers"] == []


def test_page_with_no_footnotes_is_not_an_issue():
    rep = footnote_report(["ordinary prose", "more prose"])
    assert rep == {"counts": {}, "gaps": [], "singletons": [], "ascii_openers": []}


def test_gap_in_the_run_is_reported():
    """Markers 1 and 3 with no 2: a marker was dropped or misread."""
    rep = footnote_report(["a.¹", "¹ note", "b.³", "³ note"])
    assert rep["gaps"] == [2]


def test_singleton_marker_is_reported():
    """`2-034`'s real defect: body reference keyed ¹, note opener keyed ASCII 1."""
    rep = footnote_report(["ceremonial dances.¹ The woman", "1 See Chapter XIV."])
    assert rep["singletons"] == [1]
    assert [o["digit"] for o in rep["ascii_openers"]] == [1]


def test_more_than_two_occurrences_is_fine():
    """`3-005` prints ⁶ three times. The rule is "at least two", not "exactly"."""
    rep = footnote_report(["a.⁶", "⁶ note", "and again ⁶ here"])
    assert rep["singletons"] == []
    assert rep["gaps"] == list(range(1, 6))  # 1..5 genuinely missing here


def test_half_open_pairing_is_what_ascii_openers_catches():
    """One marker keyed as a superscript, the next as a plain digit.

    The superscript is what proves the page's own convention, so against it a bare
    digit is an inconsistency rather than a guess. `2-034` exactly: body reference
    `dances.¹`, opener `1 See Chapter XIV.`
    """
    rep = footnote_report(["ceremonial dances.¹ The woman", "1 See Chapter XIV."])
    assert [o["digit"] for o in rep["ascii_openers"]] == [1]


def test_an_all_ascii_page_is_a_known_limit_not_a_catch():
    """Stated because it is not obvious, and because an earlier version of this
    check claimed the opposite.

    With no superscript anywhere there is nothing to prove a convention against:
    no gaps, no singletons, and no opener flagged. That was `1-073` and `1-151`
    before repair, and it is what a freshly recognized page looks like, since
    CATMuS emits plain digits. Catching it needs a witness this function has not
    got — do not "fix" it by dropping the prior-superscript condition, which would
    fire on ordinary prose (see the next test).
    """
    rep = footnote_report(["also accurate.1", "1 Compare Melikoff, p. 136."])
    assert rep["gaps"] == [] and rep["singletons"] == []
    assert rep["ascii_openers"] == []


def test_numbered_list_items_do_not_collide():
    """The book sets list items as digit + PERIOD; 27 such lines in the restored
    corpus and not one is a footnote. Matching them would swamp the real hits."""
    rep = footnote_report([
        "1. ɪnp-luˊwleñ-yiˊᵋlhɪn (“old-buck month”), from about the 20th",
        "2. Čačanloˊrg̣ɪn (“cold udder [month]”).",
        "5. Imlɪˊrɪlɪn (“water [month]”).",
    ])
    assert rep["ascii_openers"] == []


def test_wrapped_body_line_beginning_with_a_numeral_is_not_flagged():
    """`1-053`'s "2 houses)." — the continuation of "...Nordquist, / 2 houses)."
    wrapped onto its own line, mid-gazetteer, on a page that prints no footnote 2
    at all. Ordinary prose, and the reason the prior-superscript condition exists:
    without it this reported forever, and a permanent known-false hit is precisely
    the noise that buries real signal."""
    assert footnote_report(["2 houses)."])["ascii_openers"] == []


def test_a_bare_digit_before_the_first_superscript_is_not_flagged():
    """Order matters, not just presence. `1-053`'s false hit sits at vpos 1152 and
    its real opener at 3155, so the bare digit comes first in reading order and
    nothing has yet established the page's convention.

    Position on the page is deliberately NOT the test — some pages are half
    footnotes, and the scan does not support that kind of geometric judgement."""
    rep = footnote_report(["2 houses).", "¹ Besides these, there are about 400"])
    assert rep["ascii_openers"] == []


def _proposal(tmp_path, lines, footnotes=None):
    doc = {"lines": {str(i): {"text": t} for i, t in enumerate(lines)}}
    if footnotes is not None:
        doc["footnotes"] = footnotes
    p = tmp_path / "proposal.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


def test_check_reports_a_page_level_issue(tmp_path):
    issues = check(_proposal(tmp_path, ["dances.¹ The woman", "1 See Chapter XIV."]))
    fn = [i for i in issues if i["issue"] == "footnote markers"]
    assert len(fn) == 1
    assert fn[0]["line"] == "-"          # page-level, not pinned to a line
    assert fn[0]["explained"] == ""
    assert "occur once" in fn[0]["detail"]


def test_an_explanation_downgrades_but_does_not_delete(tmp_path):
    """A page seam legitimately breaks the pairing. The reason must still reach
    the adjudicator rather than vanishing into a silent pass."""
    path = _proposal(tmp_path, ["dances.¹ The woman"],
                     footnotes={"note": "note text runs onto 2-035; opener is there"})
    fn = [i for i in check(path) if i["issue"] == "footnote markers"]
    assert len(fn) == 1
    assert "2-035" in fn[0]["explained"]


def test_explanation_accepts_a_bare_string_too(tmp_path):
    path = _proposal(tmp_path, ["dances.¹"], footnotes="seam case")
    fn = [i for i in check(path) if i["issue"] == "footnote markers"]
    assert fn[0]["explained"] == "seam case"


def test_clean_page_emits_no_footnote_issue(tmp_path):
    path = _proposal(tmp_path, ["a.¹", "¹ note"])
    assert [i for i in check(path) if i["issue"] == "footnote markers"] == []


# --- the normalize bucket: scoping, and the report-only tier -----------------

def test_normalize_scopes_the_check_to_stores_holding_running_text(tmp_path):
    """`gt/fig/` carries no TextLine at all and `gt/seg/` is geometry, so a
    footnote check over them can only ever return nothing — and `data/*.json`
    holds citations, where a digit is a volume or a page, not a note anchor.
    Firing there would be pure noise in a bucket meant to be read."""
    from harness.normalize import _footnote_hits
    for rel in ("gt/fig/chukchi-1-123.xml", "gt/seg/chukchi-1-123.xml",
                "data/authorities.json", "data/readings.md"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("1 See Chapter XIV.", encoding="utf-8")
        assert _footnote_hits(p, tmp_path) == [], rel


def test_normalize_reads_ocr_alto_in_document_order(tmp_path):
    """The real shape: one String per TextLine, CONTENT carrying the text."""
    from harness.normalize import _footnote_hits
    # `gt/ocr/`, not the `ocr/` view: since `ocr predict` gave the view a second
    # real store to resolve into, the corpus sweep names the stores rather than the
    # view (normalize.SCOPE_GLOBS). That is the right home for this fixture anyway
    # — a page keying its marker as a superscript is by definition human-keyed, and
    # CATMuS emits plain digits, so this check never had a machine page to run on.
    p = tmp_path / "gt" / "ocr" / "chukchi-2-034.xml"
    p.parent.mkdir(parents=True)
    p.write_text(
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout><Page>'
        '<TextLine ID="l0"><String CONTENT="ceremonial dances.¹ The woman"/></TextLine>'
        '<TextLine ID="l1"><String CONTENT="1 See Chapter XIV."/></TextLine>'
        "</Page></Layout></alto>", encoding="utf-8")
    hits = _footnote_hits(p, tmp_path)
    traps = {h["trap"] for h in hits}
    assert "marker printed twice, keyed once" in traps
    assert "bare ASCII digit where a superscript was meant" in traps


def test_footnote_markers_do_not_gate_the_exit_code(tmp_path):
    """Report-only, sitting with `lookalikes` rather than nfd/marks/spacing.
    Both invariants break legitimately at a page seam, where a note's reference
    and its text land on different pages — so this reports and never refuses."""
    from harness import normalize as N
    # `gt/ocr/`, not the `ocr/` view: since `ocr predict` gave the view a second
    # real store to resolve into, the corpus sweep names the stores rather than the
    # view (normalize.SCOPE_GLOBS). That is the right home for this fixture anyway
    # — a page keying its marker as a superscript is by definition human-keyed, and
    # CATMuS emits plain digits, so this check never had a machine page to run on.
    p = tmp_path / "gt" / "ocr" / "chukchi-2-034.xml"
    p.parent.mkdir(parents=True)
    p.write_text(
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout><Page>'
        '<TextLine ID="l0"><String CONTENT="ceremonial dances.¹ The woman"/></TextLine>'
        '<TextLine ID="l1"><String CONTENT="1 See Chapter XIV."/></TextLine>'
        "</Page></Layout></alto>", encoding="utf-8")
    rep = N.scan(tmp_path)
    assert rep["footnote_markers"], "the defect must be reported"
    assert not rep["nfd_offenders"]
    assert not rep["unlicensed_marks"]
    assert not rep["spacing_offenders"]


# --- the editors must not reformat a file they do not own -------------------

def test_replace_preserves_the_files_own_indentation(tmp_path):
    """`review.save_decisions` writes decision.json at indent=1; this module
    authors proposal.json at indent=2. `--path` lets the editors target either,
    and imposing one format on the other turned a 10-line correction across four
    pages into a 716-line diff — reformatting that buries the change under noise
    nobody can review. Measured from the file, not assumed."""
    import json as _j

    from harness.proposal_check import replace_in_field

    for indent in (1, 2, 4):
        p = tmp_path / f"decision-{indent}.json"
        p.write_text(_j.dumps({"lines": {"43": {"text": "1 See Chapter XIV."}}},
                              ensure_ascii=False, indent=indent), encoding="utf-8")
        replace_in_field(p, "43", "text", "1 ", "¹ ", which="first")
        after = p.read_text(encoding="utf-8")
        assert _j.loads(after)["lines"]["43"]["text"] == "¹ See Chapter XIV."
        body = [ln for ln in after.splitlines()[1:] if ln.strip()]
        assert body[0].startswith(" " * indent), f"indent={indent} not preserved"
        assert not body[0].startswith(" " * (indent + 1)), f"indent={indent} widened"
