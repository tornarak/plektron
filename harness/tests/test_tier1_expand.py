"""Transcluding a ratified Tier-1 form into a collated page.

Where `gt/ocr/` holds the page, every mark on it has been adjudicated at the
raster. A collation pass that retypes `ɪᵋplɪˊlᴇ` character by character puts §5's
two residual classes back on the table — a dropped U+0323, an `ɪ` read as `i` —
and both are unfalsifiable downstream: the form still looks like a form, no
lexicon knows it, no second reader exists, and CATMuS reads 0% of the inventory.

So the pass names the token and `tei expand` writes the glyphs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _tei(tmp_path: Path, ref: str, body: str) -> Path:
    p = tmp_path / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader/><text><body><p>{body}</p>'
        "</body></text></TEI>", encoding="utf-8")
    return p


def _gt_page(tmp_path: Path, ref: str = "1-151") -> Path:
    """Ground truth carrying two Tier-1 forms and one English line."""
    p = tmp_path / "gt" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
        '<TextBlock ID="r1" TAGREFS="T1"><TextLine ID="l1">'
        '<String CONTENT="the ringed seal is called kełiˊlın here"/>'
        "</TextLine>"
        '<TextLine ID="l2"><String CONTENT="and the bearded seal uˊᵋnel"/>'
        "</TextLine></TextBlock>"
        "</PrintSpace></Page></Layout>"
        f'<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags>'
        "</alto>", encoding="utf-8")
    return p


def test_the_list_holds_the_marked_tokens_with_their_line(tmp_path):
    from harness.context import tier1_terms
    _gt_page(tmp_path)
    got = tier1_terms("1-151", tmp_path)
    assert [(t["index"], t["line"]) for t in got] == [(1, 0), (2, 1)]
    assert [t["text"] for t in got] == ["kełiˊlın", "uˊᵋnel"]


def test_a_page_with_no_ground_truth_gets_no_list(tmp_path):
    """802 of 832 pages. Not an oversight and not fillable from `mz/ocr/`:
    CATMuS reads 0% of the inventory, so that list would be garbled forms offered
    to be copied verbatim — this failure inverted rather than avoided."""
    from harness.context import tier1_terms
    assert tier1_terms("1-283", tmp_path) == []


def test_expand_writes_the_ratified_form_in(tmp_path):
    """The model chooses which token; the glyphs are never its to originate."""
    from harness.expand import expand_page
    _gt_page(tmp_path)
    p = _tei(tmp_path, "1-151",
             'the seal <foreign xml:lang="ckt" resp="#llm" index="2"/> is taken')

    got = expand_page("1-151", tmp_path, commit=True)
    assert [(r["index"], r["text"]) for r in got["resolved"]] == [
        ("2", "uˊᵋnel")]
    written = p.read_text(encoding="utf-8")
    assert ">uˊᵋnel</foreign>" in written
    assert "index=" not in written


def test_expand_writes_nothing_without_commit(tmp_path):
    from harness.expand import expand_page
    _gt_page(tmp_path)
    p = _tei(tmp_path, "1-151", '<foreign xml:lang="ckt" index="1"/>')

    assert len(expand_page("1-151", tmp_path)["resolved"]) == 1
    assert 'index="1"' in p.read_text(encoding="utf-8")


def test_an_unresolvable_handle_is_left_exactly_as_it_is(tmp_path):
    """Not dropped and not guessed at. `validate` errors on a surviving
    `@index`, so leaving it keeps the fault where a reader will meet it; removing
    it would leave a Tier-1 element holding whatever the pass typed,
    indistinguishable from one that never asked."""
    from harness.expand import expand_page
    _gt_page(tmp_path)
    p = _tei(tmp_path, "1-151", '<foreign xml:lang="ckt" index="9"/>')

    got = expand_page("1-151", tmp_path, commit=True)
    assert got["resolved"] == []
    assert "no term 9 on this page" in got["unresolved"][0]["reason"]
    assert 'index="9"' in p.read_text(encoding="utf-8")


def test_a_handle_on_an_element_holding_text_is_a_conflict(tmp_path):
    """Two claims about the same glyphs. Ranking them silently is the thing this
    whole mechanism exists to avoid, so it reports and writes neither."""
    from harness.expand import expand_page
    _gt_page(tmp_path)
    p = _tei(tmp_path, "1-151",
             '<foreign xml:lang="ckt" index="1">kelilin</foreign>')

    got = expand_page("1-151", tmp_path, commit=True)
    assert got["resolved"] == []
    assert "already holds text" in got["unresolved"][0]["reason"]
    assert "kelilin" in p.read_text(encoding="utf-8")


def test_a_handle_outside_a_tier1_element_is_refused(tmp_path):
    """The list is ratified *Tier-1* readings. English is not transcluded — the
    pass can type that, and a handle here would be reaching for the wrong thing."""
    from harness.expand import expand_page
    _gt_page(tmp_path)
    _tei(tmp_path, "1-151", '<term index="1"/>')

    got = expand_page("1-151", tmp_path, commit=True)
    assert got["resolved"] == []
    assert "no Tier-1 xml:lang" in got["unresolved"][0]["reason"]


def test_a_page_with_no_handles_is_not_an_error(tmp_path):
    """Every page collated before this existed, and every page with no native
    forms on it."""
    from harness.expand import expand_page
    _gt_page(tmp_path)
    _tei(tmp_path, "1-151", "ordinary prose")

    got = expand_page("1-151", tmp_path)
    assert got == {"ref": "1-151", "resolved": [], "unresolved": [],
                   "committed": False}


def test_expand_records_the_fourth_rank(tmp_path):
    """`#llm` is *false* about a span whose glyphs no model chose, and `#ed` is
    false too, since no human read this document. The responsible act happened
    one artifact upstream and `#gt` is where that is recorded."""
    from harness.expand import expand_page
    _gt_page(tmp_path)
    p = _tei(tmp_path, "1-151", '<foreign xml:lang="ckt" resp="#llm" index="1"/>')

    got = expand_page("1-151", tmp_path, commit=True)
    assert got["resolved"][0]["resp_was"] == "#llm"
    assert 'resp="#gt"' in p.read_text(encoding="utf-8")


def test_the_adopted_rank_is_verified_not_accepted(tmp_path):
    """A rank nothing checks is a claim, and this project's whole subject is
    claims that carry no error signal. Membership in the page's ratified token
    set is the check, and it is whole-token by construction."""
    from harness.validate import validate
    _gt_page(tmp_path)
    ctx = {"page_ref": "1-151", "root": str(tmp_path), "figures_on_page": [],
           "ocr_lines": [], "toc_window": []}

    ok = _tei(tmp_path, "1-151", '<foreign xml:lang="ckt" resp="#gt">uˊᵋnel</foreign>')
    assert not [e for e in validate(ok, ctx).errors if "PROVENANCE" in e]

    lie = _tei(tmp_path, "1-101", '<foreign xml:lang="ckt" resp="#gt">invented</foreign>')
    assert any("is not a token in this page's ground truth" in e
               for e in validate(lie, ctx).errors)


def test_a_dropped_final_mark_does_not_pass_as_adopted(tmp_path):
    """The reason the check is set membership and not a substring test.

    `Qeˊñ` is a substring of `Qeˊñu`, so a substring firewall passes a span that
    dropped its final mark — which is §5's residual class exactly. Whole tokens
    are the only granularity at which this check protects the boundary.
    """
    from harness.validate import validate
    _gt_page(tmp_path)
    ctx = {"page_ref": "1-151", "root": str(tmp_path), "figures_on_page": [],
           "ocr_lines": [], "toc_window": []}
    p = _tei(tmp_path, "1-151", '<foreign xml:lang="ckt" resp="#gt">uˊᵋne</foreign>')

    assert any("is not a token in this page's ground truth" in e
               for e in validate(p, ctx).errors)


def test_the_claim_fails_rather_than_going_stale(tmp_path):
    """The property a written-once attribute could not have. Correct the ground
    truth under an adopted span and the rank stops being true, loudly — where a
    stamp applied at expansion time would go on asserting the old reading."""
    from harness.validate import validate
    gt = _gt_page(tmp_path)
    ctx = {"page_ref": "1-151", "root": str(tmp_path), "figures_on_page": [],
           "ocr_lines": [], "toc_window": []}
    p = _tei(tmp_path, "1-151", '<foreign xml:lang="ckt" resp="#gt">uˊᵋnel</foreign>')
    assert not [e for e in validate(p, ctx).errors if "PROVENANCE" in e]

    gt.write_text(gt.read_text(encoding="utf-8").replace("uˊᵋnel", "uˊᵋnelh"),
                  encoding="utf-8")
    assert any("is not a token in this page's ground truth" in e
               for e in validate(p, ctx).errors)


def test_a_page_with_no_ground_truth_can_adopt_nothing(tmp_path):
    """802 of 832 pages. The message says which of the two failures it is —
    the token is wrong, or there is no ratified witness at all."""
    from harness.validate import validate
    ctx = {"page_ref": "2-200", "root": str(tmp_path), "figures_on_page": [],
           "ocr_lines": [], "toc_window": []}
    p = _tei(tmp_path, "2-200", '<foreign xml:lang="ckt" resp="#gt">x</foreign>')

    assert any("gt/ocr/ does not hold this page" in e
               for e in validate(p, ctx).errors)


def test_the_rank_is_declared_where_pages_point_at_it():
    """Two files, one fact. `tei header` holds `RESP_RANKS` and the corpus header
    to each other, because a page fragment never resolves `@resp` locally — so
    either could be renamed and every page would go on passing."""
    from harness.validate import ADOPTED, RESP_RANKS, check_corpus_header
    root = Path(__file__).resolve().parents[2]
    if not (root / "tei" / "corpus-header.xml").exists():
        pytest.skip("no corpus header")
    assert ADOPTED in RESP_RANKS
    assert check_corpus_header(root).ok


def test_validate_names_the_missing_step(tmp_path):
    """An unexpanded page is a workflow fault, not a bad reference, and `@index`
    is not a TEI attribute — so the state is detectable, not merely suspected."""
    from harness.validate import validate
    p = _tei(tmp_path, "1-151",
             '<foreign xml:lang="ckt" resp="#llm" index="1"/>')
    ctx = {"page_ref": "1-151", "root": str(tmp_path), "figures_on_page": [],
           "ocr_lines": [], "toc_window": []}

    assert any("never expanded" in e for e in validate(p, ctx).errors)
