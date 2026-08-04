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


def test_validate_names_the_missing_step(tmp_path):
    """An unexpanded page is a workflow fault, not a bad reference, and `@index`
    is not a TEI attribute — so the state is detectable, not merely suspected."""
    from harness.validate import validate
    p = _tei(tmp_path, "1-151",
             '<foreign xml:lang="ckt" resp="#llm" index="1"/>')
    ctx = {"page_ref": "1-151", "root": str(tmp_path), "figures_on_page": [],
           "ocr_lines": [], "toc_window": []}

    assert any("never expanded" in e for e in validate(p, ctx).errors)
