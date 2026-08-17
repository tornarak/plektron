"""The cross-reference mark: written by rule, re-derived by the gate, rendered as
a handle.

A figure reference is the second thing in this corpus a rule may write, and it is
admitted on the terms the first one was: `#mz` says a rule read printed text and
applied a store a human keyed, and the claim is **re-derived on every validation
run** rather than stamped once. These tests are mostly about that re-derivation,
for `test_entity_links.py`'s reason — a rank that quietly stopped being checked
would look exactly like one that was.

It lived in the renderer until then, which is the other half of what is pinned
here. A link found while serving the page exists only in the HTML: the collator
reviewing the file never meets one, the gate has nothing to say about it, and the
failure it produces is not a dead link but a **working link to the wrong
picture** — the book restarts its figure numbering at 1 on every plate.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness import figrefs, tei_html
from harness.validate import validate

TEI_NS = "http://www.tei-c.org/ns/1.0"


def page(root: Path, body: str, store: str = "tei") -> Path:
    p = root / store / "chukchi-1-021.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>t</title>'
        f"</titleStmt><publicationStmt><p>p</p></publicationStmt>"
        f"<sourceDesc><p>s</p></sourceDesc></fileDesc></teiHeader>"
        f'<text><body><pb n="1"/><!-- opens: indented -->{body}</body></text>'
        f"</TEI>", encoding="utf-8")
    return p


def _report(root: Path, body: str):
    return validate(page(root, body),
                    ctx={"root": str(root), "page_ref": "1-021",
                         "expected_folio": None, "folio_basis": ""})


def errors(root: Path, body: str) -> list[str]:
    return [e for e in _report(root, body).errors if "<ref" in e]


def worklist(root: Path, body: str) -> list[str]:
    return [w for w in _report(root, body).worklist if "<ref>" in w]


def render(root: Path, body: str) -> dict:
    return tei_html.render(page(root, body, store="mz/tei"))


# ------------------------------------------------------------- the mark itself

def test_a_mark_round_trips():
    """`mark` and `unmark` are one spelling read two ways, and both directions are
    used — the generator writes, the renderer and the gate read."""
    span = {"kind": "figure", "number": "3", "plate": "XXVII"}
    assert figrefs.mark(span) == ' type="figure" n="3" cRef="Plate XXVII"'
    assert figrefs.unmark("figure", "3", "Plate XXVII") == span


def test_a_bare_figure_carries_no_scope():
    assert figrefs.mark({"kind": "figure", "number": "87", "plate": ""}) == \
        ' type="figure" n="87"'
    assert figrefs.unmark("figure", "87", None) == \
        {"kind": "figure", "number": "87", "plate": ""}


def test_attributes_that_do_not_spell_a_reference_read_as_none():
    """`None` rather than a best effort, and every caller treats it as an error:
    a mark nobody can read is indistinguishable from one nobody checked."""
    assert figrefs.unmark("picture", "3", None) is None      # not a kind
    assert figrefs.unmark("figure", None, None) is None      # no number
    assert figrefs.unmark("figure", "3", "XXVII") is None    # cRef unparseable
    assert figrefs.unmark("plate", "XIV", "Plate XXI") is None  # scoped plate


# ------------------------------------------------- re-derivation, both directions

def test_a_mark_the_page_still_prints_is_accepted(tmp_path):
    assert not errors(tmp_path, '<p>as shown in Fig. '
                                '<ref type="figure" n="87" resp="#mz">87</ref></p>')


def test_a_mark_whose_text_was_edited_away_fails(tmp_path):
    """**The whole licence of `#mz`.** Nothing about this mark changed; the prose
    under it did, and the claim it makes stopped being true. A stamp written once
    would still be here saying the page prints a reference it does not."""
    bad = errors(tmp_path, '<p>the paddle '
                           '<ref type="figure" n="87" resp="#mz">87</ref></p>')
    assert bad and "no longer derives" in bad[0]


def test_a_mark_that_disagrees_with_the_rule_fails(tmp_path):
    """The page prints an unscoped `Fig. 3` and the mark claims Plate XXVII's
    third picture — a real leaf, whose caption reads correctly under the wrong
    picture. It is the failure the scope exists to prevent, so it is an error and
    not a warning."""
    bad = errors(tmp_path, '<p>see Fig. <ref type="figure" n="3" '
                           'cRef="Plate XXVII" resp="#mz">3</ref></p>')
    assert bad and "disagrees with the rule" in bad[0]


def test_a_scope_the_page_does_print_is_accepted(tmp_path):
    assert not errors(tmp_path, '<p>(see Plate '
                                '<ref type="plate" n="XXVII" resp="#mz">XXVII</ref>'
                                ', Fig. <ref type="figure" n="3" '
                                'cRef="Plate XXVII" resp="#mz">3</ref>)</p>')


def test_a_malformed_mark_is_an_error(tmp_path):
    bad = errors(tmp_path, '<p>see Fig. <ref type="picture" n="87">87</ref></p>')
    assert bad and "not a cross-reference this corpus can read" in bad[0]


def test_a_printed_reference_with_no_mark_is_a_worklist_line(tmp_path):
    """Not an error, and the asymmetry is deliberate: deleting a mark the sentence
    does not support is exactly what the collator is shown it for, and a page
    collated before the rule widened shows here too."""
    assert not errors(tmp_path, "<p>as shown in Fig. 87 above</p>")
    assert worklist(tmp_path, "<p>as shown in Fig. 87 above</p>")


def test_a_caption_is_not_asked_for_a_mark(tmp_path):
    """`Fig. 45. Paddle` is the picture's own name, not a pointer at it. The
    generator marks no caption and the renderer linked none, so a gate that asked
    for one here would demand a mark nothing may write."""
    assert not worklist(tmp_path, '<figure n="45"><figDesc>Fig. 45. Paddle of '
                                  'Skin Boat.</figDesc></figure>')


def test_a_mark_the_gate_cannot_reach_is_an_error(tmp_path):
    """An unchecked `#mz` is indistinguishable from a checked one to anything
    that does not check, so a mark somewhere the scan never goes — a caption, or
    loose in the body — is refused rather than passed over in silence."""
    bad = errors(tmp_path, '<figure n="45"><figDesc>Fig. <ref type="figure" '
                           'n="45" resp="#mz">45</ref>. Paddle.</figDesc></figure>')
    assert bad and "stands outside every block this gate scans" in bad[0]


def test_a_collators_own_mark_answers_the_other_direction(tmp_path):
    """`#llm` is a reading and nothing re-derives a reading — but the page is
    marked, so it is not also reported as printing a reference nobody marked."""
    body = ('<p>as shown in Fig. '
            '<ref type="figure" n="87" resp="#llm">87</ref></p>')
    assert not errors(tmp_path, body)
    assert not worklist(tmp_path, body)


def test_a_note_is_scanned_as_its_own_block(tmp_path):
    """An anchored note sits inside the paragraph it hangs in, and the generator
    scanned the two apart. Flattening the paragraph over the note would splice a
    footnote's first word onto a sentence's last and read a reference out of the
    join — or lose one across it."""
    assert not errors(tmp_path, '<p>The frame resembles Nelson\'s'
                                '<note n="1" place="bottom">Nelson, Fig. '
                                '<ref type="figure" n="38" resp="#mz">38</ref>.'
                                '</note> except that</p>')


def test_an_anchored_note_puts_its_printed_marker_back(tmp_path):
    """`1-143` sets "illustrated by Nelson.¹ Fig. 22, b", and the generator
    scanned that paragraph *before* `_place_notes` swapped the superscript for the
    element. Read without it, the text says `Nelson.` immediately in front of a
    reference to this page's own figure, and the authority guard refuses a mark
    the rule correctly wrote — three pages of the corpus, all this shape.

    One character out and one character back, which also keeps the offsets equal
    to the ones the generator scanned at.
    """
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "authorities.json").write_text(json.dumps({
        "source": {"refs": ["1-023"]},
        "authorities": [{"key": "nelson1899", "ref": "1-023", "folio": "3",
                         "cited_as": [{"name": "Nelson"}],
                         "printed": [{"ref": "1-023", "text": "NELSON."}]}]}),
        encoding="utf-8")
    (tmp_path / "data" / "runs.json").write_text(json.dumps({"runs": [
        {"id": "authorities", "kind": "authorities",
         "title": "Authorities Quoted", "refs": ["1-023"],
         "source": "data/authorities.json"}]}), encoding="utf-8")
    body = ('<p>which is illustrated by Nelson.<note n="1" place="bottom">'
            'Nelson, Plate LXXVI, Fig. 1, p. 208.</note>\nFig. '
            '<ref type="figure" n="22" resp="#mz">22</ref>, b, shows a sled</p>')
    assert not errors(tmp_path, body)


def test_another_authors_plate_is_not_expected_and_may_not_be_marked(tmp_path):
    """`Sauer, Plate XIV` is Sauer's and this book has a Plate XIV. The guard is
    the generator's, and the gate re-derives it: an unmarked citation is not a
    worklist line, and a marked one does not derive."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "authorities.json").write_text(json.dumps({
        "source": {"refs": ["1-023"]},
        "authorities": [{"key": "sauer1802", "ref": "1-023", "folio": "3",
                         "cited_as": [{"name": "Sauer"}],
                         "printed": [{"ref": "1-023", "text": "SAUER."}]}]}),
        encoding="utf-8")
    (tmp_path / "data" / "runs.json").write_text(json.dumps({"runs": [
        {"id": "authorities", "kind": "authorities",
         "title": "Authorities Quoted", "refs": ["1-023"],
         "source": "data/authorities.json"}]}), encoding="utf-8")
    assert not worklist(tmp_path, "<p>compare Sauer, Plate XIV, p. 321</p>")
    bad = errors(tmp_path, '<p>compare Sauer, Plate <ref type="plate" n="XIV" '
                           'resp="#mz">XIV</ref>, p. 321</p>')
    assert bad and "no longer derives" in bad[0]


# ----------------------------------------------------------------- the renderer

def test_a_mark_renders_as_a_handle_the_route_resolves(tmp_path):
    """**Handles, not answers.** Which picture a number names is a join over
    `gt/fig/`, which moves; `stores.render` caches on the TEI's bytes alone, so
    resolving here would go on serving a link to a box somebody has since moved.
    """
    got = render(tmp_path, '<p>see Fig. <ref type="figure" n="3" '
                           'cRef="Plate XXVII" resp="#mz">3</ref></p>')
    assert got["ok"]
    assert '<a class="figref" data-fr="0" tabindex="0">3</a>' in got["html"]
    assert got["figrefs"] == [{"kind": "figure", "number": "3", "plate": "XXVII",
                              "before": "see Fig. "}]


def test_the_prose_in_front_of_a_reference_rides_with_it(tmp_path):
    """The authority guard reads what stands before a reference, and the name is
    routinely in an element of its own. Taken before the numeral is rendered, or
    the number itself would be the last thing the guard sees."""
    got = render(tmp_path, '<p><bibl>Sauer</bibl>, Plate '
                           '<ref type="plate" n="XIV">XIV</ref></p>')
    assert got["figrefs"][0]["before"].endswith("Sauer, Plate ")


def test_an_unreadable_mark_renders_as_text(tmp_path):
    """The gate refuses it, so it reaches no collated page; a draft showing it
    flat is the honest rendering of a mark nothing can read."""
    got = render(tmp_path, '<p>see Fig. <ref type="picture" n="3">3</ref></p>')
    assert got["ok"] and "figref" not in got["html"] and "3" in got["html"]


def test_a_reference_inside_an_entity_link_renders_flat(tmp_path):
    """An anchor inside an anchor is not markup HTML has, and the entity link is
    the one that survives — `_referring`'s rule, unchanged."""
    (tmp_path / "entities" / "place").mkdir(parents=True, exist_ok=True)
    (tmp_path / "entities" / "place" / "markova.md").write_text(
        "# place:markova — Markova\n\n- status: ratified\n\n## aliases\n\n"
        "| form | lang | auto | note |\n|---|---|---|---|\n"
        "| Markova | | yes | |\n\n## gloss\n\nA fair.\n", encoding="utf-8")
    got = render(tmp_path, '<p><rs ref="place:markova">Markova, Fig. '
                           '<ref type="figure" n="87">87</ref></rs></p>')
    assert got["ok"] and "figref" not in got["html"]
