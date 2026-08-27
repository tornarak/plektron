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

import re
from pathlib import Path

import pytest
from lxml import etree

from harness import ids
from harness.validate import MEASURE_TYPES, NAME_TYPES, validate

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def page(tmp_path: Path, ref: str, body: str, opens: str | None = "indented") -> Path:
    """A page fixture. `opens` supplies the seam witness every page must carry.

    Defaulted rather than written into each body: it is required on every page, and
    these fixtures are about other rules — a hundred copies of one comment would say
    nothing except that the gate exists. `opens=None` omits it, for the tests that
    are about the witness itself.
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

def test_a_printed_gloss_carries_no_rank(tmp_path):
    """Provenance left @type when the literal/sense distinction needed it. A gloss
    reproducing the print is transcription; authored text goes in <supplied>, which
    already forces @resp and @reason."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '<gloss resp="#llm" target="#term-1-100-1">g</gloss></item></list>')
    assert any("carries no rank" in e for e in gate(tmp_path, "1-100").errors)


def test_a_supplied_gloss_is_one_holding_supplied_text(tmp_path):
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '<gloss target="#term-1-100-1"><supplied reason="context" resp="#llm">g'
         '</supplied></gloss></item></list>')
    rep = gate(tmp_path, "1-100")
    assert not rep.errors
    assert ids.glossary(tmp_path)["pairs"][0]["supplied"] is True


def test_a_literal_gloss_says_so(tmp_path):
    """The book cues it: `[literally, “whetting-stone”]` beside the sense gloss.
    A term routinely carries both, and the distinction is printed, not inferred."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term>'
         '(<gloss target="#term-1-100-1">“file”</gloss>'
         ' [<gloss type="literal" target="#term-1-100-1">“whetting-stone”</gloss>])'
         '</item></list>')
    assert not gate(tmp_path, "1-100").errors
    assert sorted(g["type"] for g in ids.glossary(tmp_path)["pairs"]) == [
        "", "literal"]


def test_one_gloss_may_reach_two_terms(tmp_path):
    """TEI's @target is a URI *list*, and one printed span routinely glosses both
    forms in an entry — 1-101 sets "from one to two years old" once for the male
    and female. Reading the attribute whole dropped every such gloss."""
    page(tmp_path, "1-100",
         '<pb n="1"/><list><item><term xml:id="term-1-100-1">a</term> and '
         '<term xml:id="term-1-100-2">b</term>, '
         '<gloss target="#term-1-100-1 #term-1-100-2">young</gloss>.</item></list>')
    assert [g["term"] for g in ids.glossary(tmp_path)["pairs"]] == ["a", "b"]


# ------------------------------------------------------------ the glossary

def glossed(tmp_path, ref="1-100", extra=""):
    page(tmp_path, ref,
         '<pb n="1"/><list><item n="1">'
         '<term xml:id="term-1-100-1" xml:lang="ckt" resp="#llm">a</term>'
         f' (<gloss target="#term-1-100-1">“g”{extra}</gloss>).</item></list>')


def test_the_glossary_resolves_a_pair(tmp_path):
    glossed(tmp_path)
    got = ids.glossary(tmp_path)
    assert got["pairs"] == [{"term": "a", "kind": "term", "lang": "ckt",
                             "gloss": "“g”", "type": "", "supplied": False,
                             "scope": "", "scope_supplied": False,
                             "ref": "1-100"}]


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
    assert any("not a declared kind" in e for e in gate(tmp_path, "1-100").errors)


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


def test_the_declared_gloss_kinds_are_what_the_book_cues(tmp_path):
    """`literal` is cued by the word "literally"; `etymon` by "from". Provenance is
    deliberately absent — it lives in <supplied>, so @type carries one axis."""
    from harness.validate import GLOSS_TYPES
    assert GLOSS_TYPES == {"literal", "etymon"}


# ------------------------------------------------------------- proper names

# The pass marks *category* and never identity. Scoped to Tier-1 names, because a
# Chukchee form glossed "a village" is a fact only a reader of the page can record,
# while an English ethnonym or a Latin binomial is a string match anything can find
# over finished TEI.

def named(tmp_path, span):
    page(tmp_path, "1-101", f'<pb n="1"/><p>They went to {span}.</p>')
    return gate(tmp_path, "1-101")


def test_a_name_is_a_kind_something_can_point_at(tmp_path):
    """`name` joined KINDS the same way the others earned it — by acquiring a
    referrer. A glossed proper noun is a <gloss target> away from a <name>."""
    assert ids.parse_id("name-1-101-1") == {
        "kind": "name", "ref": "1-101", "ordinal": 1}


def test_a_glossed_name_reaches_the_dictionary_as_a_name(tmp_path):
    """1-101's `Young-Lamut-Reindeer (Tor-waˊwaq)`. `kind` is what separates a
    proper noun from a common one without re-parsing the TEI — an index of
    toponyms is that column filtered."""
    page(tmp_path, "1-101",
         '<pb n="1"/><p>e. g., <gloss target="#name-1-101-1">Mushroom-Eater</gloss>'
         ' (<name xml:id="name-1-101-1" xml:lang="ckt" resp="#llm">a</name>).</p>')
    got = ids.glossary(tmp_path)["pairs"][0]
    assert got["kind"] == "name" and got["gloss"] == "Mushroom-Eater"


def test_an_unglossed_name_is_not_an_unlinked_term(tmp_path):
    """Most proper nouns are never glossed, so counting them as dictionary gaps
    would make the gap count meaningless."""
    page(tmp_path, "1-101", '<pb n="1"/><p>To <name>Karagha</name>.</p>')
    assert ids.glossary(tmp_path)["unlinked_terms"] == 0


def test_an_untyped_name_passes(tmp_path):
    """"Mark all, type only what's evidenced" — untyped is the designed outcome
    where the page does not say what the name is, not an unfinished state."""
    assert not named(tmp_path, "<name>Karagha</name>").errors


def test_an_undeclared_name_type_is_refused(tmp_path):
    assert any("not a declared type" in e for e in
               named(tmp_path, '<name type="village">Karagha</name>').errors)


def test_the_declared_types_are_the_seven(tmp_path):
    """`zoonym` because a herding people names its reindeer; `mythonym` rather than
    `theonym` because the book names supernatural beings that are not gods; `event`
    because an expedition is neither a person nor a place, and calling one after the
    man it was named for is what `1-021` did with nothing better on offer."""
    assert NAME_TYPES == {"anthroponym", "ethnonym", "toponym", "hydronym",
                          "zoonym", "mythonym", "event"}


def test_taxon_is_not_a_declared_type(tmp_path):
    """Binomials are Latin in English prose and out of this pass's scope: they are
    a more regular pattern than ethnonyms, and lexicon_extra.txt already holds the
    genus and species lists an automated pass would need. A type nothing writes is
    dead surface in the gate."""
    assert "taxon" not in NAME_TYPES


@pytest.mark.parametrize("attr", ["key", "nymRef"])
def test_identity_has_one_spelling_and_these_are_not_it(tmp_path, attr):
    """`@ref` resolves against `entities/` now; these two stay refused, and not as
    leftovers of the old blanket deferral.

    One spelling for one fact. Three attributes meaning "which entity" would make
    "is this name linked" a question with three places to look, and the
    referential-integrity check would be a gate that misses two thirds of what it
    is for. `@key` is TEI's *unresolved* identifier — a bare string with no
    scheme — which is exactly what the `class:slug` prefix replaces.
    """
    rep = named(tmp_path, f'<name {attr}="x">Karagha</name>')
    assert any("spells identity a way this corpus does not" in e
               for e in rep.errors)


def test_a_ref_that_resolves_to_nothing_is_an_error(tmp_path):
    """A pointer to nothing is worse than no pointer: it reads as resolved. This is
    the check that made lifting the refusal safe — the store is what the gate
    consults, and it consults it on every run rather than once when the link was
    written."""
    rep = named(tmp_path, '<name ref="person:nobody">Karagha</name>')
    assert any("resolves to nothing" in e for e in rep.errors)


def test_a_bare_slug_is_not_an_identity(tmp_path):
    """`person:jochelson` and `source:jochelson` are different entities, so a bare
    slug names neither."""
    rep = named(tmp_path, '<name ref="jochelson">Karagha</name>')
    assert any("an identity is `class:slug`" in e for e in rep.errors)


def test_a_tier1_name_needs_its_rank_like_any_other_span(tmp_path):
    """No new provenance code: validate identifies a Tier-1 span by xml:lang on any
    element, so <name> lands on the existing rule."""
    rep = named(tmp_path, '<name xml:lang="ckt">Karagha</name>')
    assert any("carries no @resp" in e for e in rep.errors)


def test_names_are_counted_and_never_put_on_the_worklist(tmp_path):
    """Under "type only what's evidenced" an untyped name is the normal outcome, so
    a worklist line would be permanently non-empty — the noise that buries signal."""
    rep = named(tmp_path, '<name>Karagha</name> and <name type="hydronym">Anui</name>')
    assert rep.metrics["names"] == 2 and rep.metrics["names_untyped"] == 1
    assert not [w for w in rep.worklist if "name" in w.lower()]


def test_an_english_person_is_a_name_like_a_tier1_one(tmp_path):
    """`anthroponym` is the one type not scoped to Tier-1. A bare `Steller` is a man,
    a work or a jay and the string carries none of the three, so the automatable
    coverage that justifies leaving `Chukchee` and `Phoca hispida` bare does not
    exist here. No xml:lang, so no @resp: the firewall is about glyph identity, and
    nobody needs a model's authority to have read a Latin-alphabet surname."""
    assert not named(tmp_path, '<name type="anthroponym">Pavlutsky</name>').errors


def test_an_event_is_a_name_at_any_tier(tmp_path):
    """The second unscoped type, and for the same reason `anthroponym` is: every
    attested case is English, so a Tier-1 scope would exclude all of them. The span's
    extent is the judgement — that these five words are one name — which is exactly
    what no match over finished TEI recovers."""
    assert not named(
        tmp_path,
        '<name type="event">Jesup North Pacific Expedition</name>').errors


# `<bibl>` marks that a work is cited. Which work is `find authority`'s answer, read
# while collating and deliberately not written down — the same deferral as `<name>`,
# spelled in the attributes TEI uses for bibliographic identity.

def test_a_citation_carries_no_key(tmp_path):
    """Every one of these would point the citation at a edition/authorities.json entry.
    The printed list is open — "For other authorities see references in the text" —
    so a per-page pass resolving what it could would key the store by accident of
    which pages ran first."""
    for attr in ("corresp", "ref", "key", "sameAs"):
        rep = named(tmp_path, f'<bibl {attr}="steller1774">Steller, p. 42.</bibl>')
        assert any("names which work is cited" in e for e in rep.errors), attr


def test_a_measure_must_say_which_regime_of_value(tmp_path):
    """Required, where a <name>'s @type is not. An untyped name is a real state — the
    page marked a proper noun and did not say what kind. A measure has no such state:
    which regime of value it belongs to is the entire reason to mark it."""
    rep = named(tmp_path, "<measure>30 kopeks</measure>")
    assert any("carries no @type" in e for e in rep.errors)


def test_the_measure_types_are_the_books_own_three(tmp_path):
    """`currency` is not the superset, because 1-093 refuses to let it be: "Money is
    quite unknown ... the unit of value in Russian trade remains a bundle of tobacco".
    `weight` is in because the pud and the Russian pound are as recondite as the
    barter units and denominate half the chapter's prices."""
    assert MEASURE_TYPES == {"currency", "barter", "weight"}
    assert not named(
        tmp_path, '<measure type="barter">a bundle of tobacco</measure>').errors
    assert any("not a declared type" in e for e in
               named(tmp_path, '<measure type="money">30 kopeks</measure>').errors)


@pytest.mark.parametrize("attr", ["unit", "quantity", "commodity"])
def test_a_measure_may_not_normalize_its_value(tmp_path, attr):
    """The same deferral as <name @ref>, one axis over. @quantity additionally cannot
    hold what the chapter prints — "$2.50 to $3.50", "10 to 15 fawn-skins", "6¼
    pounds" — and a range is where a per-page pass would start inventing conventions.
    """
    rep = named(tmp_path, f'<measure type="weight" {attr}="pud">one pud</measure>')
    assert any("normalizes the value" in e for e in rep.errors)


def test_a_measure_group_holding_no_measure_records_nothing(tmp_path):
    rep = named(tmp_path, "<measureGrp>a hide of a large ground-seal</measureGrp>")
    assert any("holds no <measure>" in e for e in rep.errors)


def test_a_group_gathers_one_priced_thing_and_not_things_that_are_equal(tmp_path):
    """1-094 prices a bundle of tobacco seven ways in one sentence, and the seven are
    pointedly not equal. Under an equality reading the subject would sit in seven
    groups at once, which no tree expresses; under TEI's own "relate to the same
    object" it is one group, and the print's ellipsis ("in Yakutsk, 60 kopeks") is
    resolved by the reader who has the paragraph open."""
    rep = named(tmp_path,
                '<measureGrp><measure type="barter">a bundle of tobacco</measure>'
                ' was worth about <measure type="currency">30 kopeks</measure>;'
                ' in Yakutsk, <measure type="currency">60 kopeks</measure>;'
                ' at the Anui fair, <measure type="currency">2.40 rubles</measure>'
                ' or <measure type="barter">3 black fawn-skins</measure>'
                '</measureGrp>')
    assert not rep.errors
    assert rep.metrics["measures"] == 5 and rep.metrics["measure_groups"] == 1


def test_a_group_needs_no_measure_for_the_thing_it_prices(tmp_path):
    """"for a hide of a large ground-seal, from 10 to 15 fawn-skins of larger size" —
    the hide is the commodity, not a unit of value, so it carries no <measure> and the
    group spans from it through its price. Requiring two would refuse the commonest
    shape in 1-094's inland-trade list."""
    rep = named(tmp_path,
                '<measureGrp>for a hide of a large ground-seal, <measure '
                'type="barter">from 10 to 15 fawn-skins of larger size</measure>'
                '</measureGrp>')
    assert not rep.errors and rep.metrics["measure_groups"] == 1


def test_a_bare_citation_passes_and_is_counted(tmp_path):
    """The extent is the deliverable: the reader decided this run of text is a
    reference to a work, which is what no string match recovers."""
    rep = named(tmp_path,
                '<bibl><name type="anthroponym">Steller</name>, p. 42.</bibl>')
    assert not rep.errors
    assert rep.metrics["bibls"] == 1 and rep.metrics["names"] == 1
