"""Page seams — @part written from the page after the gap, onto both sides.

The fact a seam records is one bit: does an element carry across this gap. It
lands on two elements, one per page, and only the following page holds both
witnesses (the predecessor's tail, its own opening text, its own first-line
indent). So that page writes both ends.

The tests that matter are the ones about *order independence*. `@part` is two
bits — begins-before, runs-past — and each seam sets exactly one of them on each
side. Get that wrong and the second seam touching an element silently overwrites
what the first recorded, which is invisible in a single-page view and produces a
corpus where long elements lose one of their two ends.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from lxml import etree

from harness import seam
from harness.validate import OPENS, validate

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def page(tmp_path: Path, ref: str, body: str, opens: str | None = "indented") -> Path:
    """A page fixture; `opens` supplies the seam witness the gate requires.

    Note what it is *not*: `@part`, which these tests are about, is the verdict, and
    `seam` writes it from both ends of the gap. This comment is the evidence the
    collator had and the coordinator does not — the first line's indent, which lives
    only on the raster. The two coexist on a page without restating each other.
    """
    if opens is not None:
        body = re.sub(r"(<pb\b[^>]*/>)", rf"\1<!-- opens: {opens} -->", body, count=1)
    d = tmp_path / "tei"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"chukchi-{ref}.xml"
    p.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>t</title>'
        f'</titleStmt><publicationStmt><p>p</p></publicationStmt>'
        f'<sourceDesc><p>s</p></sourceDesc></fileDesc></teiHeader>'
        f'<text><body>{body}</body></text></TEI>\n', encoding="utf-8")
    return p


def part_of(tmp_path: Path, ref: str, which: int) -> str | None:
    tree = etree.parse(str(tmp_path / "tei" / f"chukchi-{ref}.xml"))
    return seam.body_elements(tree.getroot())[which].get("part")


def two_pages(tmp_path, first='<pb n="1"/><p>a</p><p>b</p>',
              second='<pb n="2"/><p>c</p><p>d</p>'):
    page(tmp_path, "1-010", first)
    page(tmp_path, "1-011", second)


# ------------------------------------------------------------- the basic write

def test_continues_marks_both_sides(tmp_path):
    two_pages(tmp_path)
    seam.set_seam("1-011", True, tmp_path, commit=True)
    assert part_of(tmp_path, "1-010", -1) == "I"   # begins there, runs past
    assert part_of(tmp_path, "1-011", 0) == "F"    # began earlier, ends here


def test_untouched_elements_stay_untouched(tmp_path):
    two_pages(tmp_path)
    seam.set_seam("1-011", True, tmp_path, commit=True)
    assert part_of(tmp_path, "1-010", 0) is None
    assert part_of(tmp_path, "1-011", -1) is None


def test_preview_writes_nothing(tmp_path):
    two_pages(tmp_path)
    out = seam.set_seam("1-011", True, tmp_path)
    assert [c["to"] for c in out["changes"]] == ["I", "F"]
    assert part_of(tmp_path, "1-010", -1) is None
    assert part_of(tmp_path, "1-011", 0) is None


# --------------------------------------------- order independence, the real one

def test_an_element_open_at_both_ends_becomes_M(tmp_path):
    """1-011 holds a single paragraph spanning the whole page: it is continued
    from 1-010 and continues into 1-012. Whichever seam is declared second must
    add its bit rather than overwrite the first one's."""
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p>')
    page(tmp_path, "1-011", '<pb n="2"/><p>b</p>')
    page(tmp_path, "1-012", '<pb n="3"/><p>c</p>')
    seam.set_seam("1-011", True, tmp_path, commit=True)   # gap 10|11
    assert part_of(tmp_path, "1-011", 0) == "F"
    seam.set_seam("1-012", True, tmp_path, commit=True)   # gap 11|12
    assert part_of(tmp_path, "1-011", 0) == "M"           # not overwritten to I


def test_declaring_the_seams_in_the_other_order_gives_the_same_result(tmp_path):
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p>')
    page(tmp_path, "1-011", '<pb n="2"/><p>b</p>')
    page(tmp_path, "1-012", '<pb n="3"/><p>c</p>')
    seam.set_seam("1-012", True, tmp_path, commit=True)
    seam.set_seam("1-011", True, tmp_path, commit=True)
    assert part_of(tmp_path, "1-011", 0) == "M"


def test_repeating_a_seam_is_idempotent(tmp_path):
    two_pages(tmp_path)
    for _ in range(3):
        seam.set_seam("1-011", True, tmp_path, commit=True)
    assert (part_of(tmp_path, "1-010", -1), part_of(tmp_path, "1-011", 0)) == ("I", "F")


# ------------------------------------------------------------- reversing a call

def test_fresh_clears_both_sides(tmp_path):
    two_pages(tmp_path)
    seam.set_seam("1-011", True, tmp_path, commit=True)
    seam.set_seam("1-011", False, tmp_path, commit=True)
    assert part_of(tmp_path, "1-010", -1) is None
    assert part_of(tmp_path, "1-011", 0) is None


def test_fresh_leaves_the_other_gap_alone(tmp_path):
    """A corrected verdict returns the element to exactly the state the *other*
    seam left it in — M drops to I, not to nothing."""
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p>')
    page(tmp_path, "1-011", '<pb n="2"/><p>b</p>')
    page(tmp_path, "1-012", '<pb n="3"/><p>c</p>')
    seam.set_seam("1-011", True, tmp_path, commit=True)
    seam.set_seam("1-012", True, tmp_path, commit=True)
    assert part_of(tmp_path, "1-011", 0) == "M"
    seam.set_seam("1-011", False, tmp_path, commit=True)  # 10|11 was wrong
    assert part_of(tmp_path, "1-011", 0) == "I"           # still runs into 1-012


# ------------------------------------------------------------------- refusals

def test_a_run_on_list_is_linked_rather_than_parted(tmp_path):
    """TEI's att.fragmentable omits <list>, so the same fact is spelled as a
    @prev/@next pair. Ids are minted from the canonical position, never invented."""
    page(tmp_path, "1-010", '<pb n="1"/><list><item>x</item></list>')
    page(tmp_path, "1-011", '<pb n="2"/><list><item>y</item></list>')
    seam.set_seam("1-011", True, tmp_path, commit=True)
    a = etree.parse(str(tmp_path / "tei" / "chukchi-1-010.xml")).getroot()
    b = etree.parse(str(tmp_path / "tei" / "chukchi-1-011.xml")).getroot()
    ea, eb = seam.body_elements(a)[-1], seam.body_elements(b)[0]
    assert ea.get(XML_ID) == "list-1-010-1" and eb.get(XML_ID) == "list-1-011-1"
    assert ea.get("next") == "#list-1-011-1"
    assert eb.get("prev") == "#list-1-010-1"
    assert ea.get("part") is None and eb.get("part") is None


def test_mixed_kinds_are_refused_on_continues(tmp_path):
    """A <p> ending one page and a <list> opening the next are two elements, not
    one carrying across. Refuse naming both rather than parting the half that
    happens to be fragmentable — a half-written seam is worse than none."""
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p>')
    page(tmp_path, "1-011", '<pb n="2"/><list><item>y</item></list>')
    out = seam.set_seam("1-011", True, tmp_path, commit=True)
    assert out["changes"] == []
    assert len(out["refused"]) == 1
    assert "cannot be one element carrying across" in out["refused"][0]["why"]
    assert part_of(tmp_path, "1-010", -1) is None


def test_mixed_kinds_are_fine_on_fresh(tmp_path):
    """The ordinary clean break: a page ends with a list, the next opens with a
    paragraph. Refusing here would fire on normal pages."""
    page(tmp_path, "1-010", '<pb n="1"/><list><item>x</item></list>')
    page(tmp_path, "1-011", '<pb n="2"/><p>b</p>')
    out = seam.set_seam("1-011", False, tmp_path, commit=True)
    assert out["refused"] == [] or all(
        "cannot be one element" not in r["why"] for r in out["refused"])


def test_an_uncollated_predecessor_is_refused(tmp_path):
    page(tmp_path, "1-011", '<pb n="2"/><p>c</p>')
    with pytest.raises(ValueError, match="work in scan order"):
        seam.set_seam("1-011", True, tmp_path)


def test_the_first_scan_of_a_part_has_no_gap_before_it(tmp_path):
    page(tmp_path, "1-001", '<pb n="1"/><p>a</p>')
    with pytest.raises(ValueError, match="no gap before it"):
        seam.set_seam("1-001", True, tmp_path)


def test_pb_and_milestone_are_never_the_spanning_element(tmp_path):
    """They are points in the text, not containers; nothing spans a gap as one."""
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p>')
    page(tmp_path, "1-011", '<pb n="2"/><milestone unit="chapter" n="chI"/><p>c</p>')
    seam.set_seam("1-011", True, tmp_path, commit=True)
    assert part_of(tmp_path, "1-011", 0) == "F"


# -------------------------------------------------------------- the gate agrees

def gate(tmp_path, ref):
    return validate(tmp_path / "tei" / f"chukchi-{ref}.xml", None)


def test_the_gate_accepts_part_where_seam_puts_it(tmp_path):
    two_pages(tmp_path)
    seam.set_seam("1-011", True, tmp_path, commit=True)
    assert not [e for e in gate(tmp_path, "1-011").errors if "@part" in e]
    assert not [e for e in gate(tmp_path, "1-010").errors if "@part" in e]


def test_the_gate_rejects_part_in_the_middle_of_a_page(tmp_path):
    """Nothing between the first and last element can span either gap."""
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p><p part="F">b</p><p>c</p>')
    assert any("neither the first nor the last" in e
               for e in gate(tmp_path, "1-010").errors)


def test_the_gate_rejects_a_value_tei_does_not_define(tmp_path):
    page(tmp_path, "1-010", '<pb n="1"/><p part="Y">a</p>')
    assert any("TEI allows I, M or F" in e for e in gate(tmp_path, "1-010").errors)


# ------------------------------------------------------- the previous page's tail

def test_tail_reports_the_last_element_and_its_end(tmp_path):
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p><p>and so they went on</p>')
    t = seam.tail("1-011", tmp_path)
    assert t["ref"] == "1-010" and t["element"] == "p"
    assert t["xml"].endswith("and so they went on</p>")
    assert t["ends_sentence"] is False


def test_a_predecessor_still_being_collated_does_not_crash_its_neighbour(tmp_path):
    """**Found by a live collator in a dispatched batch.** `1-032` could not run
    `tei context` at all: `1-031` was mid-collation, its body still ended with the
    generator's unanchored `<note place="bottom">`, and stripping notes out of an
    element that *is* a note dereferenced a null parent.

    A body-level note is a validate error on a finished page and the ordinary
    state of an unfinished one, so under a batch this is the common case rather
    than the odd one — which is exactly the condition dispatching the pass was
    supposed to make survivable."""
    page(tmp_path, "1-010",
         '<pb n="1"/><p>the prose runs on</p>'
         '<note place="bottom">Resin, p. 156.</note>')
    t = seam.tail("1-011", tmp_path)
    assert t is not None


def test_the_tail_is_the_prose_and_not_the_footnote_apparatus(tmp_path):
    """A footnote is anchored in the running text and is not part of it, so it
    cannot be what the next page's opening continues. Answering the seam question
    with a note would give a confident wrong answer — the note usually ends on a
    full stop while the prose above it does not."""
    page(tmp_path, "1-010",
         '<pb n="1"/><p>the prose runs on</p>'
         '<note place="bottom">Resin, p. 156.</note>')
    t = seam.tail("1-011", tmp_path)
    assert t["element"] == "p" and t["ends_sentence"] is False


def test_the_tail_is_markup_and_keeps_the_numbering(tmp_path):
    """The live case for why this is a subtree and not a text excerpt: whether
    the list resuming at 15 on the next page is the same list is settled by
    @n on the last item, which a flattened tail throws away."""
    page(tmp_path, "1-010",
         '<pb n="1"/><list type="gloss"><item n="13">a</item>'
         '<item n="14"><term xml:lang="ckt" resp="#llm">x</term></item></list>')
    x = seam.tail("1-011", tmp_path)["xml"]
    assert 'n="14"' in x and 'type="gloss"' in x
    assert 'xml:lang="ckt"' in x and 'resp="#llm"' in x


def test_the_tail_fragment_parses(tmp_path):
    page(tmp_path, "1-010",
         '<pb n="1"/><list>' + "".join(
             f'<item n="{i}">item number {i} with some gloss text</item>'
             for i in range(1, 40)) + '</list>')
    t = seam.tail("1-011", tmp_path)
    assert t["elided_children"] > 0
    frag = etree.fromstring(t["xml"].encode())      # well-formed, not a slice
    kept = [c.get("n") for c in frag if isinstance(c.tag, str)]
    assert kept[-1] == "39"                         # the end is what is kept


def test_elision_is_stated_not_implied(tmp_path):
    page(tmp_path, "1-010",
         '<pb n="1"/><list>' + "".join(
             f'<item n="{i}">item number {i} with some gloss text</item>'
             for i in range(1, 40)) + '</list>')
    assert "elided" in seam.tail("1-011", tmp_path)["xml"]


def test_a_short_element_is_not_trimmed_at_all(tmp_path):
    page(tmp_path, "1-010", '<pb n="1"/><p>short</p>')
    t = seam.tail("1-011", tmp_path)
    assert t["elided_children"] == 0 and "elided" not in t["xml"]


def test_tail_is_null_when_the_predecessor_is_not_collated(tmp_path):
    """Null, not a shape with empty fields — an absent predecessor is not an
    observation about the seam, and `harness seam` refuses the same case."""
    page(tmp_path, "1-011", '<pb n="2"/><p>c</p>')
    assert seam.tail("1-011", tmp_path) is None
    assert seam.tail("1-001", tmp_path) is None


def test_a_footnote_stays_in_the_markup_but_does_not_decide_the_sentence(tmp_path):
    """The two fields answer different questions. `xml` is the page's markup and
    the note belongs to it; `ends_sentence` is about the *running* text, and a
    note's closing sentence must not stand in for the paragraph's."""
    page(tmp_path, "1-010",
         '<pb n="1"/><p>the herd moved<note n="1" place="bottom">Not in winter.'
         '</note> north</p>')
    t = seam.tail("1-011", tmp_path)
    assert "Not in winter" in t["xml"]
    assert t["ends_sentence"] is False


def test_removing_a_note_keeps_the_text_after_it(tmp_path):
    """lxml's remove() takes the element's tail with it, and a note is anchored
    mid-paragraph far more often than at the end — so this silently truncated the
    paragraph at the marker, and `ends_sentence` then described the wrong
    sentence. Caught by a test, not by reading the output."""
    page(tmp_path, "1-010",
         '<pb n="1"/><p>the herd moved<note n="1" place="bottom">Not in winter.'
         '</note> north and stopped.</p>')
    assert seam.tail("1-011", tmp_path)["ends_sentence"] is True


def test_tail_sees_a_terminal_stop_through_a_closing_quote(tmp_path):
    page(tmp_path, "1-010", '<pb n="1"/><p>he said “no.”</p>')
    assert seam.tail("1-011", tmp_path)["ends_sentence"] is True


def test_tail_carries_any_verdict_already_recorded(tmp_path):
    """So a re-run can see the gap was already decided rather than re-deciding."""
    two_pages(tmp_path)
    seam.set_seam("1-011", True, tmp_path, commit=True)
    assert seam.tail("1-011", tmp_path)["part"] == "I"


def test_a_terminal_stop_does_not_settle_the_seam(tmp_path):
    """The live case: 1-100 ends a numbered list at item 14 with a full stop and
    1-101 resumes it at 15. Absence of a stop is positive evidence; presence of
    one is only the lack of it, so the field is a hint and never a verdict."""
    page(tmp_path, "1-010", '<pb n="1"/><list><item n="14">last.</item></list>')
    t = seam.tail("1-011", tmp_path)
    assert t["ends_sentence"] is True and t["element"] == "list"


def test_part_and_next_together_are_refused(tmp_path):
    """One gap, two spellings. A fragmentable element is parted, a linkable one
    is linked, never both — otherwise the same fact can disagree with itself."""
    page(tmp_path, "1-010",
         '<pb n="1"/><list xml:id="list-1-010-1" part="I" next="#list-1-011-1">'
         '<item>x</item></list>')
    assert any("one gap, two" in e for e in gate(tmp_path, "1-010").errors)


def test_prev_next_in_the_middle_of_a_page_is_refused(tmp_path):
    page(tmp_path, "1-010",
         '<pb n="1"/><p>a</p><list next="#x"><item>y</item></list><p>c</p>')
    assert any("neither the first nor the last" in e
               for e in gate(tmp_path, "1-010").errors)


def test_a_neighbours_gloss_travels_with_its_term(tmp_path):
    """`foreign_terms_nearby` read only <foreign>, so every headword in a
    neighbouring gloss list was invisible to it — which is most of what a page
    like 1-100 contains. Still read-only reference: the gloss says what the
    neighbour's editor understood the form to mean, which is what makes a variant
    spelling worth a second look, and is exactly as unlicensed to copy as the term."""
    from harness.state import foreign_terms_nearby
    scans(tmp_path, "1-010", "1-011")
    page(tmp_path, "1-010",
         '<pb n="1"/><list><item n="1">'
         '<term xml:id="term-1-010-1" xml:lang="ckt" resp="#llm">qoˊra</term>'
         ' (<gloss target="#term-1-010-1">“reindeer”</gloss>).</item></list>')
    got = foreign_terms_nearby("1-011", tmp_path)
    assert got == [{"term": "qoˊra", "lang": "ckt", "gloss": "“reindeer”",
                    "scope": "", "ref": "1-010"}]


def test_an_unglossed_foreign_span_still_appears(tmp_path):
    """One fixed key set across the list, or TOON degrades to the nested form."""
    from harness.state import foreign_terms_nearby
    scans(tmp_path, "1-010", "1-011")
    page(tmp_path, "1-010",
         '<pb n="1"/><p><foreign xml:lang="ckt" resp="#llm">qoˊra</foreign></p>')
    assert foreign_terms_nearby("1-011", tmp_path)[0]["gloss"] == ""


# ------------------------------------------------- the ledger's boundary column

def scans(tmp_path: Path, *refs):
    """`build_ledger` walks physical scan order, so the rasters must exist."""
    d = tmp_path / "scans"
    d.mkdir(parents=True, exist_ok=True)
    for r in refs:
        (d / f"chukchi-{r}.png").write_bytes(b"")


def boundary(tmp_path: Path, ref: str) -> str:
    from harness.state import build_ledger
    return build_ledger(tmp_path)[ref]["boundary"]


def test_a_marked_part_reads_open(tmp_path):
    scans(tmp_path, "1-010", "1-011")
    two_pages(tmp_path)
    seam.set_seam("1-011", True, tmp_path, commit=True)
    assert boundary(tmp_path, "1-010") == "open"


def test_a_linked_list_reads_open_though_it_carries_no_part(tmp_path):
    """The half of the derivation that is easy to omit. TEI's att.fragmentable
    excludes <list>, so a run-on list is spelled with @next and a derivation
    testing only @part would call this a clean break — which is precisely what
    1-100 is not."""
    scans(tmp_path, "1-010", "1-011")
    page(tmp_path, "1-010",
         '<pb n="1"/><list next="#list-1-011-1"><item>a</item></list>')
    page(tmp_path, "1-011", '<pb n="2"/><list><item>b</item></list>')
    assert boundary(tmp_path, "1-010") == "open"


def test_both_pages_collated_and_unmarked_reads_closed(tmp_path):
    scans(tmp_path, "1-010", "1-011")
    two_pages(tmp_path)
    assert boundary(tmp_path, "1-010") == "closed"


def test_an_uncollated_successor_reads_unknown_not_closed(tmp_path):
    """`seam` refuses unless both pages exist, so nothing could have adjudicated
    this gap. Reporting "closed" would put a verdict nobody made in the ledger —
    the same defect as a zone page saved empty."""
    scans(tmp_path, "1-010", "1-011")
    page(tmp_path, "1-010", '<pb n="1"/><p>a</p>')
    assert boundary(tmp_path, "1-010") == "unknown"


def test_an_uncollated_page_reads_unknown(tmp_path):
    scans(tmp_path, "1-010", "1-011")
    page(tmp_path, "1-011", '<pb n="2"/><p>b</p>')
    assert boundary(tmp_path, "1-010") == "unknown"


def test_the_last_scan_of_a_part_has_no_gap_after_it(tmp_path):
    scans(tmp_path, "1-010", "1-011")
    two_pages(tmp_path)
    assert boundary(tmp_path, "1-011") == "unknown"


def test_entry_state_no_longer_carries_boundary_in(tmp_path):
    """It duplicated `prev_tail["part"]` — same fact, same file, two names."""
    from harness.state import entry_state
    scans(tmp_path, "1-010", "1-011")
    two_pages(tmp_path)
    assert "boundary_in" not in entry_state("1-011", tmp_path)


# ------------------------------------------------------ no space before a <note>

def test_a_space_before_a_note_is_an_error(tmp_path):
    """The print sets a thin space before the raised digit ("[albino] ¹)"), which
    is typesetting exactly as the French spacing at keying spec 2.9 is, and it
    leaves a stray space in the reading text of anything that strips the marker."""
    page(tmp_path, "1-010",
         '<pb n="1"/><p>[albino] <note n="1" place="bottom">Pink eyes.</note>)</p>')
    assert any("space before <note" in e for e in gate(tmp_path, "1-010").errors)


def test_a_tight_note_passes(tmp_path):
    page(tmp_path, "1-010",
         '<pb n="1"/><p>[albino]<note n="1" place="bottom">Pink eyes.</note>)</p>')
    assert not [e for e in gate(tmp_path, "1-010").errors if "<note" in e]


def test_the_space_is_seen_after_an_intervening_element(tmp_path):
    """The text before a <note> is its previous sibling's tail, not the parent's,
    wherever any inline markup sits between them."""
    page(tmp_path, "1-010",
         '<pb n="1"/><p><term xml:lang="ckt" resp="#llm">x</term> '
         '<note n="1" place="bottom">Pink eyes.</note></p>')
    assert any("space before <note" in e for e in gate(tmp_path, "1-010").errors)


def test_a_note_opening_its_parent_has_nothing_before_it(tmp_path):
    """No preceding text at all is not a space. Guards against reading None as
    whitespace and reporting every note that opens an element."""
    page(tmp_path, "1-010",
         '<pb n="1"/><p><note n="1" place="bottom">Pink eyes.</note> after</p>')
    assert not [e for e in gate(tmp_path, "1-010").errors if "<note" in e]


# ------------------------------------------------------- the opening witness
#
# `@part` above is the verdict and `seam` writes it from both ends of the gap. This
# is the evidence for it, and the evidence had nowhere to live: of the three
# witnesses the collation rules name, the previous page's tail and this page's
# opening text both survive into the TEI, and the first line's indent — the positive
# one — exists only on the raster. Under a dispatched batch the collator has the
# image and the coordinator writing @part does not, so the comment is the whole of
# what crosses between them.

def test_a_page_with_no_opening_witness_is_refused(tmp_path):
    page(tmp_path, "1-010", '<pb n="1"/><p>text</p>', opens=None)
    assert any("no <!-- opens:" in e for e in gate(tmp_path, "1-010").errors)


@pytest.mark.parametrize("value", sorted(OPENS))
def test_each_of_the_three_passes(tmp_path, value):
    """`no witness` is in the set rather than expressed by the comment's absence: a
    heading or a plate has no measure to judge against, and that is an answer. Left
    to absence it would be indistinguishable from a collator that did not look."""
    page(tmp_path, "1-010", '<pb n="1"/><p>text</p>', opens=value)
    assert not [e for e in gate(tmp_path, "1-010").errors if "opens:" in e]


def test_a_witness_off_the_set_is_refused(tmp_path):
    """Closed because the coordinator batches `seam --continues/--fresh` off these.
    Free text would have to be read one page at a time, which is the cost that
    dispatching the pass exists to remove."""
    page(tmp_path, "1-010", '<pb n="1"/><p>text</p>',
         opens="slightly indented, hard to tell")
    assert any("is not one of the three" in e for e in gate(tmp_path, "1-010").errors)


def test_the_witness_must_lead_the_comments_after_pb(tmp_path):
    """Not "be the first node" — the folio-disagreement comment also sits right after
    <pb>, and two comments cannot both be immediate. The order is fixed instead, so
    the gate never fires on which one the author happened to write first."""
    page(tmp_path, "1-010",
         '<pb n="1"/><!-- printed folio 1 disagrees with expected 2 -->'
         '<p>text</p>', opens=None)
    assert any("no <!-- opens:" in e for e in gate(tmp_path, "1-010").errors)
    page(tmp_path, "1-011",
         '<pb n="1"/><!-- opens: indented -->'
         '<!-- printed folio 1 disagrees with expected 2 --><p>text</p>',
         opens=None)
    assert not [e for e in gate(tmp_path, "1-011").errors if "opens:" in e]


def test_the_witness_sits_after_pb_and_not_before_it(tmp_path):
    """A comment is not an element, so the "pb is the first element" check steps
    straight over one placed before it and reports nothing. If this check started at
    the first node rather than at `<pb>`, both positions would validate — a fixed
    form quietly becoming two nobody chose between."""
    page(tmp_path, "1-010",
         '<!-- opens: indented --><pb n="1"/><p>text</p>', opens=None)
    rep = gate(tmp_path, "1-010")
    assert not [e for e in rep.errors if "first element" in e], (
        "pb really is the first *element* here; that check is not the one that bites")
    assert any("no <!-- opens:" in e for e in rep.errors)


# --- the two witnesses to how a page opens -----------------------------------

def _opened(tmp_path, opens: str, zone_opens: str) -> str:
    """A page carrying both comments, and the `witnesses` string `seam` reports."""
    from harness.seam import _witnesses
    p = tmp_path / "tei" / "chukchi-1-076.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        f'<pb n="1"/><!-- opens: {opens} --><!-- zone-opens: {zone_opens} '
        '(from the zone label) --><p>x</p></body></text></TEI>',
        encoding="utf-8")
    return _witnesses(p)


def test_the_two_opening_witnesses_are_compared(tmp_path):
    """An indented first line means a paragraph begins here; a first body zone
    labelled `MainZone-P` means the same thing, and the two were established by
    different acts months apart — a measurement of ink against a human's
    segmentation. Agreement is worth reporting precisely because it was not
    guaranteed."""
    assert _opened(tmp_path, "indented", "fresh").startswith("agree")
    assert _opened(tmp_path, "flush to the measure", "continued").startswith("agree")


def test_a_disagreement_is_reported_and_not_refused(tmp_path):
    """Both witnesses are human-rank, so neither loses to the other by rule. This
    is an editorial question about the page and `seam` has no standing to decide
    it — the refusals in this module are about *shape*, where one side is wrong by
    construction."""
    w = _opened(tmp_path, "indented", "continued")
    assert w.startswith("DISAGREE") and "read the page" in w


def test_no_witness_is_a_third_answer_and_not_a_missing_one(tmp_path):
    """A page opening on a heading has no measure to judge, so `opens: no witness`
    is a statement rather than a gap. Comparing it against the zone label would
    manufacture a disagreement out of a page that said so honestly."""
    assert "not comparable" in _opened(tmp_path, "no witness", "fresh")


def test_one_witness_alone_is_reported_as_nothing(tmp_path):
    """The comparison this project keeps meeting in new costumes. A page generated
    before the zone-opens comment existed, or one whose reader left no `opens:`,
    has one statement — and one statement compared with itself is the collapse, not
    a cheap second check."""
    from harness.seam import _witnesses
    p = tmp_path / "tei" / "chukchi-1-077.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<pb n="1"/><!-- opens: indented --><p>x</p></body></text></TEI>',
        encoding="utf-8")
    assert _witnesses(p) == ""
