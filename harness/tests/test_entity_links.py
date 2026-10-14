"""Entity references in committed TEI, and the rank that lets a rule write one.

`#mz` is the second rank admitted on the terms `#gt` was: the responsible human
act happened one artifact upstream, and the claim is **re-derived on every
validation run** rather than stamped once. These tests are mostly about that
re-derivation, because a rank that quietly stopped being checked would look
exactly like one that was.

The other half is referential integrity. `@ref` was refused outright until there
was a store to resolve it against — a pointer to nothing is worse than no
pointer, since it reads as resolved.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from test_entities import entry

from harness.validate import RESP_RANKS, validate

TEI_NS = "http://www.tei-c.org/ns/1.0"


def page(root: Path, ref: str, body: str) -> Path:
    p = root / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>t</title>'
        f"</titleStmt><publicationStmt><p>p</p></publicationStmt>"
        f"<sourceDesc><p>s</p></sourceDesc></fileDesc></teiHeader>"
        f"<text><body>{body}</body></text></TEI>", encoding="utf-8")
    return p


def gate(root: Path, ref: str = "1-021", body: str = "") -> list[str]:
    p = page(root, ref, f'<pb n="1"/><!-- opens: indented -->{body}')
    return validate(p, ctx={"root": str(root), "page_ref": ref,
                            "expected_folio": None, "folio_basis": ""}).errors


def worklist(root: Path, body: str) -> list[str]:
    p = page(root, "1-021", f'<pb n="1"/><!-- opens: indented -->{body}')
    return validate(p, ctx={"root": str(root), "page_ref": "1-021",
                            "expected_folio": None, "folio_basis": ""}).worklist


def seeded(root: Path, *, status="ratified", auto=True, form="Markova"):
    entry(root, "place:markova", status=status, aliases=[(form, auto)])


# ------------------------------------------------------- referential integrity

def test_a_ref_that_resolves_is_accepted(tmp_path):
    seeded(tmp_path)
    assert not gate(tmp_path, body='<p>At <name type="toponym" '
                                   'ref="place:markova">Markova</name>.</p>')


def test_a_ref_to_nothing_is_refused(tmp_path):
    """The check that made lifting the old blanket refusal safe."""
    seeded(tmp_path)
    assert any("resolves to nothing" in e for e in
               gate(tmp_path, body='<p><rs ref="place:nowhere">x</rs></p>'))


def test_a_type_that_contradicts_the_class_is_refused(tmp_path):
    """Two witnesses to one fact — the type a reader saw on the page, the class the
    store holds — compared rather than one overwriting the other."""
    seeded(tmp_path)
    assert any("is about the wrong entity" in e for e in
               gate(tmp_path, body='<p><name type="event" '
                                   'ref="place:markova">Markova</name></p>'))


def test_an_untyped_name_may_still_carry_a_ref(tmp_path):
    """Untyped is a designed state — "type only what's evidenced" — and the class
    does not fill it in: only a reader of the page can say the page marked a proper
    noun and what kind."""
    seeded(tmp_path)
    assert not gate(tmp_path, body='<p><name ref="place:markova">M</name></p>')


def test_an_rs_needs_a_ref(tmp_path):
    """`rs` is this corpus's entity reference and nothing else, so one with no
    referent marks nothing at all."""
    seeded(tmp_path)
    assert any("carries no @ref" in e for e in
               gate(tmp_path, body="<p><rs>Markova</rs></p>"))


def test_an_rs_carries_no_type(tmp_path):
    """The class is the ref's prefix, so a second copy of it can only disagree."""
    seeded(tmp_path)
    assert any("carries no @type here" in e for e in
               gate(tmp_path, body='<p><rs type="toponym" '
                                   'ref="place:markova">M</rs></p>'))


def test_a_ruled_name_is_admitted_at_a_geographic_class(tmp_path):
    """What a rule link is written as for the four classes whose aliases are
    named things by construction. The `@type` is the store's, so it also has to
    survive the comparison against the class two lines further down."""
    seeded(tmp_path)
    assert not gate(tmp_path, body='<p><name type="toponym" '
                                   'ref="place:markova" resp="#mz">Markova'
                                   "</name></p>")


def test_a_ruled_name_is_refused_outside_the_geographic_classes(tmp_path):
    """The whole scope of the promotion. `<name>` asserts the page marked a
    proper noun; outside geography an alias can be a common noun — *the
    Expedition*, *the Reindeer people* — and a rule stamping `<name>` on one
    invents an entity the book does not have. `<rs>` is what a rule may say
    there, and it says only that the string refers to the entity."""
    entry(tmp_path, "people:chukchi", status="ratified",
          aliases=[("Reindeer people", True)])
    assert any("not a geographic class" in e for e in
               gate(tmp_path, body='<p><name type="ethnonym" '
                                   'ref="people:chukchi" resp="#mz">Reindeer '
                                   "people</name></p>"))


def test_a_human_may_still_mark_a_name_outside_geography(tmp_path):
    """The refusal is about the *rank*, not the tag: a reader who saw a proper
    noun on the page says so at `#llm`, in any class. Refusing that too would
    have made the gate a rule about what the book may contain."""
    entry(tmp_path, "people:chukchi", status="ratified",
          aliases=[("Reindeer people", True)])
    assert not gate(tmp_path, body='<p><name type="ethnonym" '
                                   'ref="people:chukchi" resp="#llm">Reindeer '
                                   "people</name></p>")


def test_a_ruled_name_re_derives_like_any_other_ruled_link(tmp_path):
    """The promotion must not carry the link out of the re-derivation loop —
    that loop is `#mz`'s entire licence, and a rank checked in one tag but not
    the other would be a stale stamp with a longer name."""
    seeded(tmp_path, form="Markovo")
    assert any("no longer derives" in e for e in
               gate(tmp_path, body='<p><name type="toponym" '
                                   'ref="place:markova" resp="#mz">Markova'
                                   "</name></p>"))


def test_a_link_to_a_proposed_entry_is_a_worklist_line_not_an_error(tmp_path):
    """Resolvable, but nobody has audited it — which is a queue, not a defect. This
    is what makes a collator's own proposal linkable on the page that proposed it."""
    seeded(tmp_path, status="proposed")
    assert any("proposed entry" in w for w in
               worklist(tmp_path, '<p><rs ref="place:markova" '
                                  'resp="#llm">Markova</rs></p>'))


# ------------------------------------------------ #mz, re-derived every run

def test_the_rank_is_declared(tmp_path):
    assert "#mz" in RESP_RANKS


def test_a_ruled_link_the_store_still_supports_passes(tmp_path):
    seeded(tmp_path)
    assert not gate(tmp_path, body='<p><rs ref="place:markova" '
                                   'resp="#mz">Markova</rs></p>')


def test_a_ruled_link_fails_when_the_alias_is_removed(tmp_path):
    """The whole licence of the rank. An attribute written once and never rechecked
    would go stale in silence; this fails instead."""
    seeded(tmp_path, form="Markovo")
    assert any("no longer derives" in e for e in
               gate(tmp_path, body='<p><rs ref="place:markova" '
                                   'resp="#mz">Markova</rs></p>'))


def test_a_ruled_link_fails_when_the_entry_is_no_longer_ratified(tmp_path):
    seeded(tmp_path, status="proposed")
    assert any("may only apply a ratified entry" in e for e in
               gate(tmp_path, body='<p><rs ref="place:markova" '
                                   'resp="#mz">Markova</rs></p>'))


def test_a_ruled_link_fails_when_the_form_becomes_ambiguous(tmp_path):
    """A second entity claiming the form makes it ambiguous by construction, and
    every rule-applied link resting on it stops deriving — including the ones
    written before the second entity existed."""
    seeded(tmp_path)
    entry(tmp_path, "water:markova", aliases=[("Markova", True)])
    assert any("ambiguous" in e for e in
               gate(tmp_path, body='<p><rs ref="place:markova" '
                                   'resp="#mz">Markova</rs></p>'))


def test_a_ruled_link_fails_when_the_form_is_only_a_suggestion(tmp_path):
    seeded(tmp_path, auto=False)
    assert any("needs a reader, not a rule" in e for e in
               gate(tmp_path, body='<p><rs ref="place:markova" '
                                   'resp="#mz">Markova</rs></p>'))


def test_a_ruled_link_fails_when_its_text_no_longer_matches(tmp_path):
    """An editor who changed the span's text without touching the attribute would
    otherwise leave a link claiming a derivation that no longer holds."""
    seeded(tmp_path)
    assert any("no longer derives" in e for e in
               gate(tmp_path, body='<p><rs ref="place:markova" '
                                   'resp="#mz">Anadyr</rs></p>'))


def test_a_ruled_link_fails_when_the_store_resolves_the_form_elsewhere(tmp_path):
    seeded(tmp_path)
    entry(tmp_path, "water:anadyr", aliases=[("Anadyr", True)])
    assert any("the store now resolves" in e for e in
               gate(tmp_path, body='<p><rs ref="place:markova" '
                                   'resp="#mz">Anadyr</rs></p>'))


def test_an_already_linked_span_is_not_also_counted_as_unlinked():
    """`entity occurrences` counted every link twice — once linked, once unlinked —
    which inverts what the second column is for. An unlinked hit means work
    outstanding, so a page where every instance was linked must not report the same
    number as one where none was."""
    from lxml import etree

    from harness.entities import _unlinked_text
    body = etree.fromstring(
        '<body><p>At <rs ref="place:markova">Markova</rs> and at Markova.</p></body>')
    assert "Markova" in _unlinked_text(body)
    assert _unlinked_text(body).count("Markova") == 1


@pytest.mark.parametrize("ratified", [False, True])
def test_no_tier1_span_may_claim_the_rule_applied_rank(tmp_path, ratified):
    """A rule may say what a string refers to. It may never originate a reading of
    a glyph, and a Tier-1 span is the one place nothing mechanical may speak at
    all. Checked in both modes: unratified it would have fallen through to the
    "this pass may only emit #llm" branch, but under `--ratified` it would have
    been a mere worklist line."""
    seeded(tmp_path)
    p = page(tmp_path, "1-021",
             '<pb n="1"/><!-- opens: indented -->'
             '<p><foreign xml:lang="ckt" resp="#mz">a</foreign></p>')
    rep = validate(p, ctx={"root": str(tmp_path), "page_ref": "1-021",
                           "expected_folio": None, "folio_basis": ""},
                   ratified=ratified)
    assert any("confined to @ref" in e for e in rep.errors)


# ---------------------------------------- the compositor's hyphen and the word's

def _idx(root: Path):
    from harness.entities import alias_index, load
    return alias_index(load(root))


def test_a_break_hyphen_is_read_off_its_position(tmp_path):
    """`join_broken_words` keeps the hyphen it rejoined across, and for a long time
    the generator called that undecidable — "nothing can tell that hyphen from the
    word's own". Nothing had looked at *where* it was. The compositor's hyphen is
    the last thing before the measure ran out; the word's own is anywhere else."""
    from harness.entities import match
    seeded(tmp_path, form="Chukchee")
    idx = _idx(tmp_path)

    broke, = match("among the Chuk-chee\nof the coast", idx)
    assert (broke["form"], broke["broken"], broke["hyphenated"]) == (
        "Chukchee", True, False)

    mid, = match("among the Chuk-chee of the coast", idx)
    assert (mid["form"], mid["broken"], mid["hyphenated"]) == (
        "Chukchee", False, True)


def test_trailing_punctuation_does_not_move_the_hyphen_off_the_line_end(tmp_path):
    """The join takes the *token*, so the rejoined word arrives with whatever the
    next line began with — `chee,` and `chee.` are the ordinary case, and every one
    of the corpus's 54 instances ended a line this way."""
    from harness.entities import match
    seeded(tmp_path, form="Chukchee")
    idx = _idx(tmp_path)
    for tail in (",", ".", ".”", ";"):
        hit, = match(f"among the Chuk-chee{tail}\nThe coast", idx)
        assert hit["broken"] is True, tail


def test_a_form_the_store_hyphenates_never_reaches_the_test(tmp_path):
    """`Sredne-` / `Kolymsk` is the genuinely undecidable case — a word carrying its
    own hyphen that also broke there. It never arises: the join puts the word back
    as the store spells it, so the exact form matches and `dehyphenated` is never
    consulted."""
    from harness.entities import match
    seeded(tmp_path, form="Sredne-Kolymsk")
    hit, = match("at Sredne-Kolymsk\nand beyond", _idx(tmp_path))
    assert (hit["hyphenated"], hit["broken"]) == (False, False)


def test_a_break_hyphen_no_longer_withholds_the_rule_s_link(tmp_path):
    """The whole point. A hyphen the position accounts for is not a question, so
    the link a ratified `auto` alias earns everywhere else is written here too."""
    from harness.entities import auto_forms, match, rule_links
    seeded(tmp_path, form="Chukchee")
    idx = _idx(tmp_path)
    hits = match("among the Chuk-chee\nof the coast", idx)
    assert [h["form"] for h in rule_links(hits, auto_forms(idx))] == ["Chukchee"]


def test_a_caller_that_flattens_the_page_gets_the_conservative_answer(tmp_path):
    """The evidence is the caller's to preserve, and losing it must cost a question
    rather than produce a wrong link. Pinned because `occurrences` did exactly this
    and agreed with itself about it."""
    from harness.entities import match
    seeded(tmp_path, form="Chukchee")
    hit, = match("among the Chuk-chee of the coast", _idx(tmp_path))
    assert hit["hyphenated"] is True and hit["auto"] is False


def test_occurrences_reads_the_same_page_the_generator_did(tmp_path):
    """The placer and the re-deriver must not disagree about which hyphens are
    questions. `occurrences` collapsed the page to one line before matching, so a
    word the generator linked came back as an unlinked hyphenated candidate."""
    from harness.entities import load, occurrences
    seeded(tmp_path, form="Chukchee")
    p = page(tmp_path, "1-021",
             '<pb n="1"/><p>among the Chuk-chee\nof the coast</p>')
    assert p.exists()
    got = occurrences(["place:markova"], ["1-021"], load(tmp_path), tmp_path)
    assert [r["hyphenated"] for r in got["place:markova"]["unlinked"]] == [False]


# ------------------------------------------------------------- the case ladder

def test_a_row_is_reached_by_every_case_above_it(tmp_path):
    """The point of the ladder. `sables` is what the store spells and `Sables` is
    where a sentence happened to start, and before this the second was *present and
    invisible* — the store's answer was a second row recording the compositor's
    line breaks as though they were vocabulary."""
    from harness.entities import match
    seeded(tmp_path, form="sables")
    idx = _idx(tmp_path)
    for page_text in ("counted sables by doublescores",
                      "Sables were counted by doublescores",
                      "SABLES WERE COUNTED"):
        hit, = match(page_text, idx)
        assert (hit["form"], hit["auto"]) == ("sables", True), page_text


def test_the_ladder_never_descends(tmp_path):
    """A row spelled capitalized is a proper name, and reaching a lower-case page
    from it would edit a ratified identity by a keystroke nobody reviewed —
    `lookup._resolve_cased`'s reason, and the same rule."""
    from harness.entities import match
    seeded(tmp_path, form="Chukchee")
    assert match("the chukchee of the coast", _idx(tmp_path)) == []


def test_a_shape_the_ladder_cannot_rank_is_reached_only_as_itself(tmp_path):
    """`Brown Bear` at 1-184 is the river Keiˊñu-weˊem and not the animal. It is
    neither the capitalization of `brown bear` nor its uppercase, so `_case_rank`
    returns None and the row cannot reach it — which is why `taxon:ursus-arctos`
    can still say "never Brown Bear" and be right."""
    from harness.entities import match
    seeded(tmp_path, form="brown bear")
    idx = _idx(tmp_path)
    assert [h["text"] for h in match("a brown bear on the shore", idx)] == [
        "brown bear"]
    assert [h["text"] for h in match("Brown bear tracks", idx)] == ["Brown bear"]
    assert match("up the Brown Bear to its head", idx) == []


def test_sentence_initial_is_ambiguous_where_a_capitalized_row_exists(tmp_path):
    """The bird `raven` and the personage `Raven` both reach the `Raven` that opens
    a sentence, and the capital there is the compositor's — it says nothing about
    which was meant. Letting the exact row win would adjudicate at exactly the
    position where the evidence runs out, which is this project's failure mode
    with the answer written in. Two claimants, no automatic link, and a reader
    settles it."""
    from harness.entities import match
    entry(tmp_path, "taxon:corvus-corax", aliases=[("raven", True)])
    entry(tmp_path, "being:raven", aliases=[("Raven", True)])
    idx = _idx(tmp_path)

    opening, = match("Raven first made the world", idx)
    assert opening["auto"] is False
    assert sorted(opening["ids"]) == ["being:raven", "taxon:corvus-corax"]

    # Mid-sentence the question never arises: only one spelling is present.
    medial, = match("a raven flew over", idx)
    assert (medial["ids"], medial["auto"]) == (["taxon:corvus-corax"], True)


def test_two_rows_raising_to_one_variant_leave_it_contested(tmp_path):
    """The same rule where neither row is the page's spelling — an all-caps heading
    over a store holding `sable` and `Sable` on different entities."""
    from harness.entities import match
    entry(tmp_path, "place:markova", aliases=[("sable", True)])
    entry(tmp_path, "taxon:sable", aliases=[("Sable", True)])
    hit, = match("SABLE was counted", _idx(tmp_path))
    assert hit["auto"] is False
    assert sorted(hit["ids"]) == ["place:markova", "taxon:sable"]


def test_one_entity_reaching_a_spelling_twice_is_one_claimant(tmp_path):
    """`brown bears` and `Brown bears` were two rows of one entity, and the union
    that makes two *entities* ambiguous must not make this one so — an entity is
    not in doubt about itself. The row spelled at the page's case carries the
    licence, which is why the exact form is ordered first rather than dropped."""
    from harness.entities import match
    entry(tmp_path, "taxon:ursus-arctos",
          aliases=[("brown bears", True), ("Brown bears", "once")])
    hit, = match("Brown bears are met on the seashore", _idx(tmp_path))
    assert (hit["ids"], hit["auto"], hit["form"]) == (
        ["taxon:ursus-arctos"], True, "Brown bears")
    assert hit["scope"] == "first"


def test_a_tier1_form_is_not_raised_into_a_glyph_nobody_set(tmp_path):
    """`_raise_case` refuses a non-ASCII letter because `ɪ` U+026A uppercases to a
    letter the keying spec does not contain, and nothing here knows what the
    compositor set for a small-cap inside an all-caps heading. The rung it can
    reach it takes — capitalizing touches only the leading `v` — and the rung it
    cannot is dropped rather than approximated, so no variant of this form exists
    that the book was never asked about."""
    from harness.lookup import case_variants
    assert case_variants("vaˊɪrgɪt") == ["vaˊɪrgɪt", "Vaˊɪrgɪt"]
    assert case_variants("markova") == ["markova", "Markova", "MARKOVA"]
