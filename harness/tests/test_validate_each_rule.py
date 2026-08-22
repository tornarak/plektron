"""One test per `validate` rule, exercised on its own.

Before the extraction this was impossible: every rule lived inside an 800-line
function, so the only way to reach one was to build a page that happened to
trigger it and assert on a substring of the report. **Nineteen of the twenty
rules were named in no test at all** — a rule could have been deleted outright
and, unless some fixture elsewhere happened to depend on it, nothing would have
said so. That is what these close.

**Two things are asserted per rule, and the second is the one that bites.** That
a defect is caught, and that a *clean* page is silent. A rule which fires on
everything passes the first test and is worthless; on a corpus where most pages
are ordinary, a check that cannot stay quiet buries the ones that cannot.

**Messages are matched on a short, distinctive fragment**, never in full. Roughly
seventy assertions across nine other files already match `validate`'s messages by
substring, so the wording is load-bearing in a way that is easy to forget; these
add no new hostages to a comma. Where a rule's identity *is* its wording — the
provenance ranks — the fragment is the rank constant itself, which is a name the
project already treats as fixed.

`schema` and `metrics` are not per-rule tested here. `metrics` is an assembly of
what the others returned and is covered by asserting each rule's return value;
`schema` compiles `tei_all.rng` at ~17s a process and has its own file.
"""
from __future__ import annotations

from lxml import etree

from harness.validate import (
    ADOPTED,
    PROPOSED,
    RULED,
    TEI_NS,
    Report,
    _rule_bibl_extent,
    _rule_figures,
    _rule_folio,
    _rule_foreign_lang,
    _rule_line_and_division,
    _rule_measures,
    _rule_milestones,
    _rule_notes,
    _rule_provenance,
    _rule_provenance_summary,
    _rule_seam_shape,
    _rule_tier1_facs,
    _rule_tier1_unglossed,
    _rule_unexpanded_handle,
)

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def q(t: str) -> str:
    return f"{{{TEI_NS}}}{t}"


def page(body: str):
    """A parsed page. `<pb/>` first unless the test is about its absence."""
    return etree.fromstring(
        f'<TEI xmlns="{TEI_NS}"><teiHeader/><text><body>{body}</body></text>'
        "</TEI>".encode())


def body_of(root):
    return root.find(f".//{q('body')}")


def only(r: Report) -> str:
    """The single error, asserted to be single. A rule that reports the right
    defect twice is a rule a reader learns to skim."""
    assert len(r.errors) == 1, f"expected exactly one error, got {r.errors}"
    return r.errors[0]


# --------------------------------------------------------------- structure

class TestLineAndDivision:
    def test_lb_is_refused(self):
        r = Report()
        _rule_line_and_division(page("<p>a<lb/>b</p>"), q, None, r)
        assert "ALTO holds the line record" in only(r)

    def test_div_is_refused(self):
        r = Report()
        _rule_line_and_division(page("<div><p>a</p></div>"), q, None, r)
        assert "div-less" in only(r)

    def test_an_ordinary_page_is_silent(self):
        r = Report()
        _rule_line_and_division(page("<pb n='7'/><p>ordinary prose.</p>"), q, None, r)
        assert not r.errors and not r.warnings


#: The seam witness `_opening_witness` requires immediately after `<pb>` — the
#: one thing about a page's opening that exists only on the raster, and which a
#: coordinator writing `@part` cannot recover from the text. `_rule_folio` runs
#: that check too, so every fixture here carries it; omitting it would put a
#: second, unrelated error in every assertion.
OPENS = "<!-- opens: indented -->"


class TestFolio:
    def test_pb_must_be_first(self):
        r = Report()
        _rule_folio(body_of(page(f"<p>a</p><pb n='7'/>{OPENS}")), q, None, r)
        assert "not the first element" in r.errors[0]

    def test_a_non_integer_folio_is_an_error(self):
        r = Report()
        _rule_folio(body_of(page(f"<pb n='vii'/>{OPENS}<p>a</p>")), q, None, r)
        assert "not an integer folio" in only(r)

    def test_no_n_is_a_warning_not_an_error(self):
        """`<pb/>` with no @n **asserts** the page carries no printed folio — a
        plate, a blank, a part title. Load-bearing downstream (it tells the seam
        ledger not to advance), so it is surfaced rather than accepted silently,
        but it is a legitimate state and must not gate."""
        r = Report()
        _rule_folio(body_of(page(f"<pb/>{OPENS}<p>a</p>")), q, None, r)
        assert not r.errors
        assert "carries no printed folio" in r.warnings[0]

    def test_a_folio_disagreeing_with_the_prediction_warns(self):
        """The prediction is only a prediction: the page's own folio wins, and
        the disagreement is reported for a human rather than resolved."""
        r = Report()
        ctx = {"expected_folio": 8, "folio_basis": {"basis_ref": "1-050",
                                                    "basis_folio": 7}}
        _rule_folio(body_of(page(f"<pb n='7'/>{OPENS}<p>a</p>")), q, ctx, r)
        assert not r.errors
        assert "!= expected 8" in r.warnings[0]

    def test_the_agreeing_case_is_silent(self):
        r = Report()
        _rule_folio(body_of(page(f"<pb n='8'/>{OPENS}<p>a</p>")), q,
                    {"expected_folio": 8}, r)
        assert not r.errors and not r.warnings


class TestSeamShape:
    def test_an_illegal_part_value_is_refused(self):
        r = Report()
        _rule_seam_shape(page("<pb n='1'/><p part='X'>a</p>"), q, None, r)
        assert "TEI allows I, M or F" in r.errors[0]

    def test_part_in_the_middle_is_refused(self):
        """Nothing in the middle of a page spans either gap."""
        r = Report()
        _rule_seam_shape(
            page("<pb n='1'/><p>a</p><p part='M'>b</p><p>c</p>"), q, None, r)
        assert any("neither the first nor the last" in e for e in r.errors)

    def test_part_at_the_edge_is_allowed(self):
        r = Report()
        _rule_seam_shape(page("<pb n='1'/><p part='F'>a</p><p>b</p>"), q, None, r)
        assert not r.errors

    def test_part_and_prev_together_are_refused(self):
        """One gap, two spellings: a fragmentable element is parted, a linkable
        one is linked, never both."""
        r = Report()
        _rule_seam_shape(page("<pb n='1'/><p part='F' prev='#x'>a</p>"), q, None, r)
        assert any("one gap, two" in e for e in r.errors)


# ------------------------------------------------------------------- notes

class TestNotes:
    def test_a_note_must_sit_at_the_foot(self):
        r = Report()
        _rule_notes(page("<pb n='1'/><p>a<note n='1'>x</note></p>"), q, None, r)
        assert any("place='bottom'" in e for e in r.errors)

    def test_a_non_integer_marker_warns(self):
        r = Report()
        _rule_notes(page("<pb n='1'/><note place='bottom' n='a'>x</note>"),
                    q, None, r)
        assert not r.errors
        assert "non-integer marker" in r.warnings[0]

    def test_a_numbered_note_at_the_foot_is_silent(self):
        r = Report()
        _rule_notes(page("<pb n='1'/><note place='bottom' n='1'>x</note>"),
                    q, None, r)
        assert not r.errors and not r.warnings


# ---------------------------------------------------------------- Tier-1

class TestForeignLang:
    def test_a_foreign_without_lang_is_refused(self):
        """The one element where an untyped state records nothing: `<foreign>`
        means "not the surrounding language", so without naming one it asserts a
        negative about an unnamed positive."""
        r = Report()
        _rule_foreign_lang(page("<pb n='1'/><p><foreign>keliˊlın</foreign></p>"),
                           q, None, r)
        assert "carries no xml:lang" in only(r)

    def test_a_lang_bearing_foreign_is_silent(self):
        r = Report()
        _rule_foreign_lang(
            page('<pb n="1"/><p><foreign xml:lang="ckt">keliˊlın</foreign></p>'),
            q, None, r)
        assert not r.errors


class TestUnexpandedHandle:
    def test_a_surviving_index_on_a_tier1_span_is_refused(self):
        r = Report()
        _rule_unexpanded_handle(
            page('<pb n="1"/><p><foreign xml:lang="ckt" index="7"/></p>'),
            q, None, r)
        assert "never expanded" in only(r)

    def test_it_is_silent_where_the_element_is_not_tier1(self):
        """`expand` refuses a handle whose element is not a Tier-1 span, so
        naming it here would send a reviewer to a verb that cannot help. Every
        generated page arrives with one handle per ratified token; a detector
        firing on the ordinary case buries the one that is not."""
        r = Report()
        _rule_unexpanded_handle(
            page('<pb n="1"/><p><name index="7">Bogoras</name></p>'), q, None, r)
        assert not r.errors


class TestTier1Facs:
    def test_a_facs_naming_no_supplied_line_is_refused(self):
        r = Report()
        ctx = {"ocr_lines": [{"index": 3}]}
        _rule_tier1_facs(
            page('<pb n="1"/><p><foreign xml:lang="ckt" facs="#9">x</foreign></p>'),
            q, ctx, r)
        assert "matches no" in only(r)

    def test_a_facs_naming_a_supplied_line_is_silent(self):
        r = Report()
        ctx = {"ocr_lines": [{"index": 3}]}
        _rule_tier1_facs(
            page('<pb n="1"/><p><foreign xml:lang="ckt" facs="#3">x</foreign></p>'),
            q, ctx, r)
        assert not r.errors

    def test_no_context_means_no_opinion(self):
        """Without `ctx` there is no supplied line set to check against, and a
        rule with no evidence must be silent rather than assume the worst."""
        r = Report()
        _rule_tier1_facs(
            page('<pb n="1"/><p><foreign xml:lang="ckt" facs="#9">x</foreign></p>'),
            q, None, r)
        assert not r.errors


class TestTier1Unglossed:
    def test_a_bare_tier1_span_warns_and_counts(self):
        r = Report()
        n = _rule_tier1_unglossed(
            page('<pb n="1"/><p><foreign xml:lang="ckt">keliˊlın</foreign></p>'),
            q, None, r)
        assert n == 1
        assert not r.errors, "a bare form is the book's doing, never an error"
        assert "neither glossed nor identified" in r.warnings[0]

    def test_an_entity_ref_over_it_is_enough(self):
        r = Report()
        n = _rule_tier1_unglossed(
            page('<pb n="1"/><p><rs ref="place:x">'
                 '<foreign xml:lang="ckt">keliˊlın</foreign></rs></p>'), q, None, r)
        assert n == 0 and not r.warnings


# ------------------------------------------------------------- provenance

class TestProvenance:
    def test_a_tier1_span_without_resp_is_refused(self):
        """The more dangerous of the two failures: an unmarked span is
        indistinguishable from a ratified one to every consumer that does not
        check, so silence here would launder a model reading into an adopted
        glyph identity."""
        r = Report()
        _rule_provenance(
            page('<pb n="1"/><p><foreign xml:lang="ckt">x</foreign></p>'),
            q, None, r)
        assert "carries no @resp" in only(r)

    def test_an_undeclared_rank_is_refused(self):
        r = Report()
        _rule_provenance(
            page('<pb n="1"/><p><foreign xml:lang="ckt" resp="#who">x</foreign></p>'),
            q, None, r)
        assert "is not a declared rank" in only(r)

    def test_the_mechanical_rank_is_refused_on_a_glyph(self):
        """`#mz` is confined to `@ref` on `<rs>`. No rule may originate a Tier-1
        reading, and this is refused in **both** modes — ratified, it would
        otherwise have been a worklist line rather than the firewall breach it is.
        """
        for ratified in (False, True):
            r = Report()
            _rule_provenance(
                page(f'<pb n="1"/><p><foreign xml:lang="ckt" resp="{RULED}">'
                     "x</foreign></p>"), q, None, r, ratified)
            assert "No rule may originate" in only(r), f"ratified={ratified}"

    def test_the_pass_may_not_claim_a_human_rank(self):
        r = Report()
        _rule_provenance(
            page('<pb n="1"/><p><foreign xml:lang="ckt" resp="#ed">x</foreign></p>'),
            q, None, r)
        assert "rank rises by a human act" in only(r)

    def test_proposed_is_what_the_pass_may_emit(self):
        r = Report()
        _rule_provenance(
            page(f'<pb n="1"/><p><foreign xml:lang="ckt" resp="{PROPOSED}">'
                 "x</foreign></p>"), q, None, r)
        assert not r.errors

    def test_ratified_mode_turns_a_remaining_proposal_into_a_worklist_line(self):
        """`ratified` selects branches; it never gates the rule. The one flag
        with almost no coverage before these tests."""
        r = Report()
        _rule_provenance(
            page(f'<pb n="1"/><p><foreign xml:lang="ckt" resp="{PROPOSED}">'
                 "x</foreign></p>"), q, None, r, ratified=True)
        assert not r.errors
        assert "unratified:" in r.worklist[0]

    def test_adopted_without_ground_truth_is_refused(self):
        """`#gt` is checked against `gt/ocr/`, never accepted. With no context
        there is no ratified token set, so the claim cannot be true of anything.
        """
        r = Report()
        _rule_provenance(
            page(f'<pb n="1"/><p><foreign xml:lang="ckt" resp="{ADOPTED}">'
                 "x</foreign></p>"), q, {"page_ref": "1-001", "root": "."}, r)
        assert "is not a token in this page's ground truth" in only(r)


class TestProvenanceSummary:
    def test_proposals_are_reported_when_unratified(self):
        r = Report()
        _rule_provenance_summary(3, 0, False, r)
        assert PROPOSED in r.worklist[0] and "3 Tier-1" in r.worklist[0]

    def test_proposals_are_not_reported_in_ratified_mode(self):
        """There the remaining proposals are `provenance`'s worklist line, one
        per span, and saying it twice in different words reads as two jobs."""
        r = Report()
        _rule_provenance_summary(3, 0, True, r)
        assert not any(PROPOSED in w for w in r.worklist)

    def test_adopted_spans_are_reported_as_wanting_no_reading(self):
        """The split exists because the summary was written when there were
        three ranks: it called every Tier-1 span a proposal "needing a human
        reading against the page", which after `tei expand` is false about
        exactly the spans `#gt` describes — that reading happened one artifact
        upstream. A worklist line naming work that must not be done is worse
        than no line."""
        r = Report()
        _rule_provenance_summary(3, 2, False, r)
        line = next(w for w in r.worklist if ADOPTED in w)
        assert "want no" in line and "2 Tier-1" in line

    def test_a_page_with_no_tier1_says_nothing(self):
        r = Report()
        _rule_provenance_summary(0, 0, False, r)
        assert not r.worklist


# ----------------------------------------------------------------- counts

class TestBiblExtent:
    def test_it_counts_and_stays_silent(self):
        """A page citing nothing is the ordinary page, so presence is counted
        rather than gated."""
        r = Report()
        assert _rule_bibl_extent(page("<pb n='1'/><p><bibl>Nelson</bibl></p>"),
                                 q, None, r) == 1
        assert not r.errors

    def test_naming_which_work_is_refused(self):
        """`find authority` is read while collating and its answer is not written
        down — the key is the annotation pass's, over finished TEI."""
        r = Report()
        _rule_bibl_extent(page("<pb n='1'/><p><bibl ref='x'>N</bibl></p>"),
                          q, None, r)
        assert "which work is cited" in only(r)


class TestMeasures:
    def test_an_untyped_measure_is_refused(self):
        r = Report()
        _rule_measures(page("<pb n='1'/><p><measure>30 kopeks</measure></p>"),
                       q, None, r)
        assert "carries no @type" in only(r)

    def test_an_undeclared_type_is_refused(self):
        r = Report()
        _rule_measures(
            page("<pb n='1'/><p><measure type='zzz'>30</measure></p>"), q, None, r)
        assert "not a declared type" in only(r)

    def test_an_empty_group_records_nothing(self):
        r = Report()
        _rule_measures(page("<pb n='1'/><p><measureGrp/></p>"), q, None, r)
        assert "holds no <measure>" in only(r)

    def test_it_returns_both_counts(self):
        r = Report()
        m, g = _rule_measures(
            page("<pb n='1'/><p><measureGrp><measure type='currency'>30 k"
                 "</measure></measureGrp></p>"), q, None, r)
        assert (m, g) == (1, 1) and not r.errors


class TestMilestones:
    def test_an_undeclared_unit_is_refused(self):
        r = Report()
        _rule_milestones(
            page("<pb n='1'/><milestone unit='part' n='x'/>"), q, None, r)
        assert any("not in the level map" in e for e in r.errors)

    def test_an_extra_attribute_is_refused(self):
        r = Report()
        _rule_milestones(
            page("<pb n='1'/><milestone unit='chapter' n='x' rend='b'/>"),
            q, None, r)
        assert any("extra attributes" in e for e in r.errors)

    def test_only_the_mechanical_rank_or_none_is_allowed(self):
        """A milestone is either a rule's join against `data/toc.json` or a
        reading with no @resp at all — no other rank has anything to assert about
        a structural boundary."""
        r = Report()
        _rule_milestones(
            page("<pb n='1'/><milestone unit='chapter' n='x' resp='#ed'/>"),
            q, None, r)
        assert any("no other rank" in e for e in r.errors)


class TestFigures:
    def test_a_figure_without_a_number_is_refused(self):
        r = Report()
        _rule_figures(page("<pb n='1'/><figure/>"), q,
                      {"figures_on_page": [{"n": "87"}]}, r)
        assert "without n=" in only(r)

    def test_a_number_this_page_does_not_print_is_refused(self):
        """The page's own captions are the witness: a figure anchored on the
        wrong page is the error worth catching, and only the book's own
        numbering can see it."""
        r = Report()
        _rule_figures(page("<pb n='1'/><figure n='12'/>"), q,
                      {"figures_on_page": [{"n": "87"}]}, r)
        assert "no caption on this page prints that" in only(r)

    def test_geometry_is_the_builds_join_not_the_passs(self):
        r = Report()
        _rule_figures(page("<pb n='1'/><figure n='87' facs='#z1'/>"), q,
                      {"figures_on_page": [{"n": "87"}]}, r)
        assert "anchored" in only(r)

    def test_a_figure_the_page_prints_is_silent(self):
        r = Report()
        _rule_figures(page("<pb n='1'/><figure n='87'/>"), q,
                      {"figures_on_page": [{"n": "87"}]}, r)
        assert not r.errors


def test_every_rule_has_a_test_here():
    """The gate on the file. Nineteen of the twenty rules were named in no test
    before this existed, and a rule added later would quietly join them."""
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "validate.py"
    rules = re.findall(r"# ── rule: ([a-z0-9-]+) ─", src.read_text("utf-8"))
    mine = Path(__file__).read_text("utf-8")
    # `metrics` assembles what the others returned; `schema` compiles a 17s
    # grammar and has `test_tei_schema.py`; `figrefs`, `entities` and
    # `relink-missing` need a store or a file on disk and are covered against
    # the whole `validate` in `test_entity_links.py` / `test_figref_marks.py`.
    exempt = {"metrics", "schema", "figrefs", "entities", "relink-missing",
              "lang-and-glyphs"}
    missing = [r for r in rules
               if r not in exempt and f"_rule_{r.replace('-', '_')}" not in mine]
    assert not missing, f"rules with no direct test: {missing}"
