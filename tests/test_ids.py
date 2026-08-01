"""Structural ids: `{kind}-{PP-NNN}-{ordinal}`, checked rather than prohibited.

The rule that replaced a blanket ban has to be worth more than the ban was, and
what makes it so is that an id is a *total function of the tree*: kind, page ref,
and position among same-kind elements in document order. So the gate recomputes
what every id must be and compares, and nothing depends on the writing pass having
been careful.

The tests that matter are the ones about position-not-counter and about pointers
that leave the file. Both are cases where a wrong answer is well-formed XML that
resolves to nothing, which is this project's defining failure shape.
"""
from __future__ import annotations
from pathlib import Path

import pytest
from lxml import etree

from harness import ids, seam
from harness.validate import validate

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def page(tmp_path: Path, ref: str, body: str) -> Path:
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


def tree(tmp_path: Path, ref: str):
    return etree.parse(str(tmp_path / "tei" / f"chukchi-{ref}.xml")).getroot()


def gate(tmp_path: Path, ref: str):
    return validate(tmp_path / "tei" / f"chukchi-{ref}.xml",
                    {"page_ref": ref, "root": str(tmp_path)})


# --------------------------------------------------------------- the shape

def test_the_scheme_parses_back_apart():
    assert ids.parse_id("term-1-100-4") == {
        "kind": "term", "ref": "1-100", "ordinal": 4}


def test_a_bare_ref_is_not_a_legal_id():
    """An XML Name cannot begin with a digit, which is why the kind prefix is
    required rather than decorative."""
    assert ids.parse_id("1-100-4") is None


def test_the_scan_index_must_be_zero_padded():
    """Without fixed width the hyphenated form cannot be split back apart."""
    assert ids.parse_id("term-1-1-4") is None
    assert ids.parse_id("term-1-001-4") is not None


def test_gloss_and_note_are_not_kinds():
    """The kind set is exactly what something can point *at*. Nothing references
    a gloss, and a note running across a seam is not attested — a kind no referrer
    can name is dead surface in the gate."""
    assert ids.parse_id("gloss-1-100-1") is None
    assert ids.parse_id("note-1-100-1") is None


# ------------------------------------------------ the ordinal is a position

def test_the_ordinal_counts_elements_not_ids(tmp_path):
    """`1-100`'s item 4 holds two terms, so item 5's term is term-...-6. The
    ordinal is the element's place in the tree, not a tally of ids minted."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list>'
         '<item n="4"><term>a</term><term>b</term></item>'
         '<item n="5"><term>c</term></item></list>')
    got = ids.canonical_map(tree(tmp_path, "1-100"), "1-100")
    assert sorted(got.values()) == [
        "list-1-100-1", "term-1-100-1", "term-1-100-2", "term-1-100-3"]


def test_ids_may_be_sparse(tmp_path):
    """Only referenced elements carry one, so the numbering has holes by design."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term>a</term></item>'
         '<item><term xml:id="term-1-100-2">b</term>'
         '<gloss target="#term-1-100-2">g</gloss></item></list>')
    assert not [e for e in gate(tmp_path, "1-100").errors if "xml:id" in e]


def test_a_wrong_ordinal_is_caught(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term>a</term></item>'
         '<item><term xml:id="term-1-100-1">b</term>'
         '<gloss target="#term-1-100-1">g</gloss></item></list>')
    assert any('should be "term-1-100-2"' in e
               for e in gate(tmp_path, "1-100").errors)


# ----------------------------------------------------- ids name their page

def test_an_id_from_another_page_is_refused(tmp_path):
    """The check that matters most now that `prev_tail` hands the pass the
    previous page's markup with its ids in it: a copy-paste would otherwise
    import a foreign id in silence."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-099-1">a</term>'
         '<gloss target="#term-1-099-1">g</gloss></item></list>')
    assert any("embeds ref 1-099" in e for e in gate(tmp_path, "1-100").errors)


def test_an_id_off_the_scheme_is_refused(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="myterm">a</term>'
         '<gloss target="#myterm">g</gloss></item></list>')
    assert any("is not of the scheme" in e for e in gate(tmp_path, "1-100").errors)


# ------------------------------------------------- no id without a referrer

def test_an_unreferenced_id_is_refused(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term></item></list>')
    assert any("has no referrer" in e for e in gate(tmp_path, "1-100").errors)


def test_a_dangling_target_is_refused(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term>a</term>'
         '<gloss target="#term-1-100-9">g</gloss></item></list>')
    assert any("resolves to nothing" in e for e in gate(tmp_path, "1-100").errors)


def test_a_referrer_in_a_neighbour_counts(tmp_path):
    """A linked list's id is named from the next page, not from its own file."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list xml:id="list-1-100-1" next="#list-1-101-1">'
         '<item>a</item></list>')
    page(tmp_path, "1-101",
         '<pb n="2"/><list xml:id="list-1-101-1" prev="#list-1-100-1">'
         '<item>b</item></list>')
    assert not [e for e in gate(tmp_path, "1-100").errors if "no referrer" in e]


# ---------------------------------------------------- cross-page pointers

def test_prev_must_name_the_previous_page(tmp_path):
    page(tmp_path, "1-100", '<pb n="1"/><list><item>a</item></list>')
    page(tmp_path, "1-101",
         '<pb n="2"/><list xml:id="list-1-101-1" prev="#list-1-050-1">'
         '<item>b</item></list>')
    assert any("must name 1-100" in e for e in gate(tmp_path, "1-101").errors)


def test_a_pointer_into_an_uncollated_page_warns_rather_than_errors(tmp_path):
    """Honest null, the same shape as `prev_tail`: unresolvable is not wrong."""
    page(tmp_path, "1-101",
         '<pb n="2"/><list xml:id="list-1-101-1" prev="#list-1-100-1">'
         '<item>b</item></list>')
    rep = gate(tmp_path, "1-101")
    assert any("not collated yet" in w for w in rep.warnings)
    assert not [e for e in rep.errors if "prev" in e]


def test_a_pointer_matching_no_id_in_a_collated_neighbour_errors(tmp_path):
    page(tmp_path, "1-100", '<pb n="1"/><list><item>a</item></list>')
    page(tmp_path, "1-101",
         '<pb n="2"/><list xml:id="list-1-101-1" prev="#list-1-100-1">'
         '<item>b</item></list>')
    assert any("matches no xml:id in 1-100" in e
               for e in gate(tmp_path, "1-101").errors)


# ------------------------------------------------------------------- --fix

def test_fix_moves_pointer_and_target_together(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term>a</term></item>'
         '<item><term xml:id="term-1-100-9">b</term>'
         '<gloss target="#term-1-100-9">g</gloss></item></list>')
    ids.fix_page("1-100", tmp_path, commit=True)
    root = tree(tmp_path, "1-100")
    assert ids.ids_in(root).keys() == {"term-1-100-2"}
    assert root.find(f".//{{{TEI_NS}}}gloss").get("target") == "#term-1-100-2"


def test_fix_repairs_an_inbound_pointer_from_a_neighbour(tmp_path):
    """Renumbering is a within-file operation, but the referrer may not be in the
    file. Leaving it behind is a dangling pointer with no error signal."""
    page(tmp_path, "1-100",
         '<pb n="1"/><p>x</p><list xml:id="list-1-100-9" next="#list-1-101-1">'
         '<item>a</item></list>')
    page(tmp_path, "1-101",
         '<pb n="2"/><list xml:id="list-1-101-1" prev="#list-1-100-9">'
         '<item>b</item></list>')
    out = ids.fix_page("1-100", tmp_path, commit=True)
    assert out["neighbours"] == [{"ref": "1-101", "pointers": 1}]
    assert tree(tmp_path, "1-101").find(
        f".//{{{TEI_NS}}}list").get("prev") == "#list-1-100-1"


def test_fix_is_a_preview_without_commit(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term>a</term></item>'
         '<item><term xml:id="term-1-100-9">b</term>'
         '<gloss target="#term-1-100-9">g</gloss></item></list>')
    ids.fix_page("1-100", tmp_path)
    assert "term-1-100-9" in ids.ids_in(tree(tmp_path, "1-100"))


# ------------------------------------------------------------------ --pair

def test_pair_links_a_gloss_to_its_term_where_containment_decides(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item n="1"><term>a</term><gloss>g</gloss></item>'
         '<item n="2"><term>b</term><gloss>h</gloss></item></list>')
    out = ids.pair_glosses("1-100", tmp_path, commit=True)
    assert [p["id"] for p in out["paired"]] == ["term-1-100-1", "term-1-100-2"]
    assert not gate(tmp_path, "1-100").errors


def test_pair_refuses_where_containment_does_not_decide(tmp_path):
    """Two pairs in one item: choosing which gloss belongs to which term would be
    inference, which is the move this project refuses. Report, write nothing."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item n="4"><term>a</term><gloss>g</gloss>'
         '<term>b</term><gloss>h</gloss></item></list>')
    out = ids.pair_glosses("1-100", tmp_path, commit=True)
    assert out["paired"] == []
    assert out["ambiguous"][0]["n"] == "4"
    assert ids.ids_in(tree(tmp_path, "1-100")) == {}


def test_pair_does_not_collapse_containers(tmp_path):
    """lxml frees element proxies, so `id(element)` is reused and a set of them
    silently merges distinct nodes. The first version of this loop paired 5 of
    14 items on the live page and reported success."""
    items = "".join(f'<item n="{i}"><term>t{i}</term><gloss>g{i}</gloss></item>'
                    for i in range(1, 15))
    page(tmp_path, "1-100", f'<pb n="1"/><list>{items}</list>')
    out = ids.pair_glosses("1-100", tmp_path, commit=True)
    assert len(out["paired"]) == 14


# ------------------------------------------------------- supplied glosses

def test_a_supplied_gloss_must_say_who_wrote_it(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '<gloss type="supplied" target="#term-1-100-1">g</gloss></item></list>')
    assert any("without @resp" in e for e in gate(tmp_path, "1-100").errors)


def test_a_printed_gloss_carries_no_rank(tmp_path):
    """Both states are marked by a *present* attribute, so neither is reachable by
    omission."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '<gloss resp="#llm" target="#term-1-100-1">g</gloss></item></list>')
    assert any("carries no rank" in e for e in gate(tmp_path, "1-100").errors)


def test_a_supplied_gloss_with_a_rank_passes(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '<gloss type="supplied" resp="#llm" target="#term-1-100-1">g</gloss>'
         '</item></list>')
    assert not gate(tmp_path, "1-100").errors


# ------------------------------------------------------------ the glossary

def glossed(tmp_path, ref="1-100", extra=""):
    page(tmp_path, ref,
         '<pb n="1"/><list><item n="1">'
         '<term xml:id="term-1-100-1" xml:lang="ckt" resp="#llm">a</term>'
         f' (<gloss target="#term-1-100-1">“g”{extra}</gloss>).</item></list>')


def test_the_glossary_resolves_a_pair(tmp_path):
    glossed(tmp_path)
    got = ids.glossary(tmp_path)
    assert got["pairs"] == [{"term": "a", "lang": "ckt", "gloss": "“g”",
                             "supplied": False, "scope": "",
                             "scope_supplied": False, "ref": "1-100"}]


def test_a_gloss_is_read_through_its_trailing_text(tmp_path):
    """Every <gloss> in a gloss list is followed by `).`, so serializing with the
    tail attached and re-parsing fails as "extra content" — the normal case on a
    real page and the absent one in a hand-written fixture, which is how it
    reached the live corpus with the tests green."""
    glossed(tmp_path)
    assert ids.glossary(tmp_path)["pairs"][0]["gloss"] == "“g”"


def test_a_footnote_inside_a_gloss_is_not_the_definition(tmp_path):
    """1-100 anchors a note inside the gloss for Ilhɪ-lileˊ. Read naively, the
    whole note on albino reindeer becomes the dictionary entry."""
    glossed(tmp_path, extra='<note n="1" place="bottom">Albinos have pink '
                            'eyes.</note>')
    assert ids.glossary(tmp_path)["pairs"][0]["gloss"] == "“g”"


def test_text_after_a_note_survives(tmp_path):
    glossed(tmp_path, extra='<note n="1" place="bottom">N.</note> and more')
    assert ids.glossary(tmp_path)["pairs"][0]["gloss"] == "“g” and more"


def test_the_glossary_never_pairs_by_containment(tmp_path):
    """Falling back to containment would re-introduce the inference `--pair`
    refuses, silently, in a report someone would read as the dictionary."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item n="1"><term>a</term><gloss>g</gloss></item></list>')
    got = ids.glossary(tmp_path)
    assert got["pairs"] == [] and got["unlinked_terms"] == 1


def test_an_undeclared_gloss_type_is_refused(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '<gloss type="editorial" target="#term-1-100-1">g</gloss></item></list>')
    assert any("only declared value" in e for e in gate(tmp_path, "1-100").errors)


# ------------------------------------------------------------- the list scope

# A gloss list whose entries share a frame states it once, on the list, and the
# glosses do not repeat it. These pin the resolution — including across a seam,
# which is the only place in the harness that *traverses* @prev rather than
# checking one hop of it.

HEAD = '<head><supplied reason="context" resp="#llm">of a reindeer</supplied></head>'


def scoped(tmp_path, ref="1-100", head=HEAD, attrs="", body=None):
    page(tmp_path, ref,
         f'<pb n="1"/><list{attrs}>{head}' + (body or
         f'<item n="1"><term xml:id="term-{ref}-1" xml:lang="ckt" resp="#llm">a</term>'
         f' (<gloss target="#term-{ref}-1">“g”</gloss>).</item>') + '</list>')


def only(tmp_path, ref="1-100"):
    return ids.page_glossary(tree(tmp_path, ref), ref, tmp_path)["pairs"][0]


def test_a_list_head_scopes_its_own_glosses(tmp_path):
    scoped(tmp_path)
    got = only(tmp_path)
    assert got["scope"] == "of a reindeer" and got["scope_supplied"] is True


def test_a_list_with_no_head_has_no_scope(tmp_path):
    """The ordinary case: a self-sufficient list frames nothing."""
    scoped(tmp_path, head="")
    got = only(tmp_path)
    assert got["scope"] == "" and got["scope_supplied"] is False


def test_a_printed_head_scopes_but_is_not_supplied(tmp_path):
    """`scope_supplied` is constant-true across the corpus today because no gloss
    list carries a printed head. It is a column rather than a worklist line
    precisely so that the day one appears, it starts varying by itself."""
    scoped(tmp_path, head="<head>COLORS OF REINDEER</head>")
    got = only(tmp_path)
    assert got["scope"] == "COLORS OF REINDEER"
    assert got["scope_supplied"] is False


def test_a_part_supplied_head_is_not_wholly_supplied(tmp_path):
    """Loose text beside the <supplied> means part of the head is something else.
    Checked through the children's tails, not just their tags — reporting this as
    wholly supplied would misstate provenance in the field that exists to state it."""
    scoped(tmp_path,
           head='<head><supplied reason="context" resp="#llm">of a reindeer'
                "</supplied>, roughly</head>")
    got = only(tmp_path)
    assert got["scope"] == "of a reindeer, roughly"
    assert got["scope_supplied"] is False


def test_a_sub_entry_list_inherits_its_parents_scope(tmp_path):
    """A nested sub-entry list carries no head of its own."""
    scoped(tmp_path, body=
           '<item n="1"><list><item n="1a">'
           '<term xml:id="term-1-100-1" xml:lang="ckt" resp="#llm">a</term>'
           ' (<gloss target="#term-1-100-1">“g”</gloss>).</item></list></item>')
    assert only(tmp_path)["scope"] == "of a reindeer"


def test_an_inner_head_wins_over_the_outer_one(tmp_path):
    scoped(tmp_path, body=
           '<item n="1"><list><head><supplied reason="context" resp="#llm">'
           'by age</supplied></head><item n="1a">'
           '<term xml:id="term-1-100-1" xml:lang="ckt" resp="#llm">a</term>'
           ' (<gloss target="#term-1-100-1">“g”</gloss>).</item></list></item>')
    assert only(tmp_path)["scope"] == "by age"


def test_a_continuation_list_inherits_across_the_seam(tmp_path):
    """1-100 ends a gloss list, 1-101 resumes it. The frame is on the first page
    only — restating it on the second would be the duplication this avoids."""
    scoped(tmp_path, "1-100",
           attrs=' xml:id="list-1-100-1" next="#list-1-101-1"')
    scoped(tmp_path, "1-101", head="",
           attrs=' xml:id="list-1-101-1" prev="#list-1-100-1"')
    got = only(tmp_path, "1-101")
    assert got["scope"] == "of a reindeer" and got["scope_supplied"] is True


def test_the_scope_travels_the_whole_chain(tmp_path):
    """Three pages: the middle list carries the link and no head."""
    scoped(tmp_path, "1-100", attrs=' xml:id="list-1-100-1" next="#list-1-101-1"')
    scoped(tmp_path, "1-101", head="",
           attrs=' xml:id="list-1-101-1" prev="#list-1-100-1" next="#list-1-102-1"')
    scoped(tmp_path, "1-102", head="",
           attrs=' xml:id="list-1-102-1" prev="#list-1-101-1"')
    assert only(tmp_path, "1-102")["scope"] == "of a reindeer"


def test_a_pointer_into_an_uncollated_page_yields_no_scope(tmp_path):
    """Honest null, the same shape `prev_tail` and the ledger use."""
    scoped(tmp_path, "1-101", head="",
           attrs=' xml:id="list-1-101-1" prev="#list-1-100-1"')
    assert only(tmp_path, "1-101")["scope"] == ""


def test_a_cycle_terminates(tmp_path):
    """validate checks one hop of @prev, so it cannot see a cycle. Nothing else
    traverses these pointers, which makes this the one place that could hang."""
    scoped(tmp_path, "1-100", head="",
           attrs=' xml:id="list-1-100-1" prev="#list-1-101-1"')
    scoped(tmp_path, "1-101", head="",
           attrs=' xml:id="list-1-101-1" prev="#list-1-100-1"')
    assert only(tmp_path, "1-101")["scope"] == ""


# ------------------------------------------------------------- <supplied>

def supplied(tmp_path, attrs):
    page(tmp_path, "1-100",
         f'<pb n="1"/><list><head><supplied {attrs}>of a reindeer</supplied></head>'
         '<item><term xml:id="term-1-100-1">a</term>'
         '<gloss target="#term-1-100-1">g</gloss></item></list>')
    return gate(tmp_path, "1-100").errors


def test_supplied_text_must_say_who_wrote_it(tmp_path):
    assert any("without @resp" in e for e in supplied(tmp_path, 'reason="context"'))


def test_supplied_text_must_say_why(tmp_path):
    assert any("without @reason" in e for e in supplied(tmp_path, 'resp="#llm"'))


def test_an_undeclared_supplied_rank_is_refused(tmp_path):
    assert any("not a declared rank" in e for e in
               supplied(tmp_path, 'reason="context" resp="#editor"'))


def test_an_undeclared_supplied_reason_is_refused(tmp_path):
    """A required attribute with a free value guarantees a string, not a
    distinction, and drifts on the first typo."""
    assert any("not a declared reason" in e for e in
               supplied(tmp_path, 'reason="frame" resp="#llm"'))


def test_a_human_may_ratify_supplied_english(tmp_path):
    """The #llm-only rule does NOT extend here. It exists because this pass may not
    promote a *glyph identity*, and supplied English contains none."""
    assert not supplied(tmp_path, 'reason="context" resp="#ed"')


def test_an_undeclared_gloss_rank_is_refused(tmp_path):
    """Asking who and never checking the answer parses is half the rule — this
    branch was missing while the type/resp pairing above has long existed."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '<gloss type="supplied" resp="#editor" target="#term-1-100-1">g</gloss>'
         '</item></list>')
    assert any("not a declared rank" in e for e in gate(tmp_path, "1-100").errors)
