"""A Tier-1 span a reader can do nothing with.

The book prints a native word three ways, and only one of them is a defect:

* glossed in place — `Elveˊek ("one hind-leg in white stocking")` — where the
  collating pass links the printed gloss to its term with `@target`;
* marked as a name — `Tor-waˊwaq`, `Poˊñolɪn` — where being a proper noun *is*
  the answer to "what does this say";
* bare, in a gloss list whose other twenty items are glossed, which is where the
  pairing was simply not written.

Only the third is worth a reader's time, and no rule can tell it from the first
two without asking both questions. So the gate asks both, and warns rather than
errors: the book genuinely leaves forms bare, and a model may not write a gloss
the page does not carry.

The negatives below are the load-bearing half. A gate that fired on a correct
page would be the noise `names_untyped` was deliberately kept off the worklist
to avoid.
"""
from __future__ import annotations

from pathlib import Path

from test_entities import entry
from test_entity_links import page

from harness.validate import validate

CKT = 'xml:lang="ckt" resp="#llm"'


def warns(root: Path, body: str) -> list[str]:
    p = page(root, "1-021", f'<pb n="1"/><!-- opens: indented -->{body}')
    return validate(p, ctx={"root": str(root), "page_ref": "1-021",
                            "expected_folio": None, "folio_basis": ""}).warnings


def unglossed(root: Path, body: str) -> int:
    p = page(root, "1-021", f'<pb n="1"/><!-- opens: indented -->{body}')
    return validate(p, ctx={"root": str(root), "page_ref": "1-021",
                            "expected_folio": None,
                            "folio_basis": ""}).metrics["tier1_unglossed"]


def test_a_bare_form_with_nowhere_to_go_warns(tmp_path):
    got = warns(tmp_path, f"<p>the seal <foreign {CKT}>kełiˊlın</foreign></p>")
    assert any("neither glossed nor identified" in w for w in got)
    assert unglossed(tmp_path,
                     f"<p>the seal <foreign {CKT}>kełiˊlın</foreign></p>") == 1


def test_a_glossed_term_does_not_warn(tmp_path):
    """`@target` and nothing else. The gloss sits beside the term here, but
    containment is not what resolves it — that inference is refused in writing
    in `ids.pair_glosses`, and this gate does not reintroduce it."""
    body = (f'<p><term {CKT} xml:id="term-1-021-1">Elveˊek</term> '
            '(<gloss target="#term-1-021-1">"one hind-leg in white stocking"'
            "</gloss>)</p>")
    assert not any("neither glossed" in w for w in warns(tmp_path, body))


def test_a_term_beside_an_unlinked_gloss_still_warns(tmp_path):
    """The same page with the `@target` left off. This is the case the gate
    exists for, and the one containment would hide."""
    body = (f'<p><term {CKT} xml:id="term-1-021-1">Elveˊek</term> '
            '(<gloss>"one hind-leg in white stocking"</gloss>)</p>')
    assert any("neither glossed" in w for w in warns(tmp_path, body))


def test_a_name_with_an_approved_type_does_not_warn(tmp_path):
    """Being a proper noun is the answer. `<term>` wrapping `<name>` is the
    shape the collator's own worked example uses for a glossed name, so the
    outer element must find the inner one."""
    for body in (f'<p><name {CKT} type="toponym">Uweˊlen</name></p>',
                 f'<p><term {CKT}><name type="toponym">Uweˊlen</name>'
                 "</term></p>"):
        assert not any("neither glossed" in w for w in warns(tmp_path, body))


def test_an_untyped_name_still_warns(tmp_path):
    """A bar deliberately higher than `names_untyped`'s, and scoped to justify
    it. That argument is about the page's names at large — mostly English prose,
    typed only where the page evidences a category. A Tier-1 span is a handful
    per page, and "it is a name of some kind" places a native word nowhere."""
    body = f"<p><name {CKT}>Uweˊlen</name></p>"
    assert any("neither glossed" in w for w in warns(tmp_path, body))


def test_an_entity_ref_over_the_span_does_not_warn(tmp_path):
    """A rule-applied link is an `<rs>`, which carries no `@type` at all — the
    class is the ref's own prefix — so a gate keyed on `@type` alone would fire
    on every form `tei generate` had just linked."""
    entry(tmp_path, "place:uelen", triggers=[("Uweˊlen", True)])
    body = ('<p><rs ref="place:uelen" resp="#mz">'
            f"<foreign {CKT}>Uweˊlen</foreign></rs></p>")
    assert not any("neither glossed" in w for w in warns(tmp_path, body))


def test_a_re_mention_of_a_glossed_form_does_not_warn(tmp_path):
    """`1-101` glosses `qeˊñu` in one item and uses it inside another item's
    gloss. Demanding a second gloss there asks for the same fact twice."""
    body = (f'<p><term {CKT} xml:id="term-1-021-1">qeˊñu</term> '
            '(<gloss target="#term-1-021-1">"brown"</gloss>). '
            f'<term {CKT} xml:id="term-1-021-2">Meiˊñɪ-qeˊñu</term> '
            '(<gloss target="#term-1-021-2">"very much '
            f"<foreign {CKT}>qeˊñu</foreign>\"</gloss>)</p>")
    assert not any("neither glossed" in w for w in warns(tmp_path, body))


def test_the_relief_is_case_sensitive(tmp_path):
    """Folding here would import `marks.fold`'s judgement that two settings are
    one word. That judgement is real and is `lexicon lookup`'s to make; a gate
    that borrowed it would be answering a question nobody asked it."""
    body = (f'<p><term {CKT} xml:id="term-1-021-1">qeˊñu</term> '
            '(<gloss target="#term-1-021-1">"brown"</gloss>). '
            f"<foreign {CKT}>Qeˊñu</foreign></p>")
    assert any("neither glossed" in w for w in warns(tmp_path, body))


def test_a_lexicon_entry_does_not_satisfy_the_gate(tmp_path):
    """**The load-bearing negative.** The gate is deliberately independent of
    the lexicon store: what it asks is whether *this page* says anything about
    the form, and an entry written elsewhere is not that. It also keeps the gate
    from going quiet as the store fills, which is the direction a coupled gate
    would fail in."""
    (tmp_path / "lexicon").mkdir()
    (tmp_path / "lexicon" / "kelilin.md").write_text(
        "# kełiˊlın\n\n- status: proposed\n- since: 1-021\n\n"
        "## editor's note\n\nThe ringed seal.\n", encoding="utf-8")
    got = warns(tmp_path, f"<p>the seal <foreign {CKT}>kełiˊlın</foreign></p>")
    assert any("neither glossed nor identified" in w for w in got)


def test_the_warning_never_becomes_an_error(tmp_path):
    """A page of bare forms is a worklist, not a broken file. The book prints
    `Tor-waˊwaq` with its English beside it and no gloss element in sight, and a
    gate that blocked on that would be asking a collator to invent one."""
    p = page(tmp_path, "1-021",
             f'<pb n="1"/><!-- opens: indented --><p><foreign {CKT}>'
             f"kełiˊlın</foreign> <foreign {CKT}>uˊᵋnel</foreign></p>")
    rep = validate(p, ctx={"root": str(tmp_path), "page_ref": "1-021",
                           "expected_folio": None, "folio_basis": ""})
    assert rep.metrics["tier1_unglossed"] == 2
    assert not any("neither glossed" in e for e in rep.errors)
