"""The reservation classes, and the gate holding them to the contract they read.

`reservations.CLASSES` is a second statement of a vocabulary the collation contract
already fixes: the contract says "comment exactly this", the classifier says "a
comment matching this is that class". Two copies, so a gate rather than a comment —
the repo's rule everywhere else, from `VERBS.md` against the click tree to the
corpus header against `RESP_RANKS`.

**The gate points one way on purpose.** A form added to the contract with no pattern
here lands in `other`, which shows up in the report as an unclassified row somebody
reads. A pattern matching nothing in the contract is dead surface that never fires
and that nothing would ever surface. Only the second can rot unseen, so that is the
direction checked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.reservations import CLASSES, classify, page_reservations

REPO = Path(__file__).resolve().parent.parent.parent
CONTRACT = REPO / ".claude" / "skills" / "transcribe-page" / "SKILL.md"

TEI_NS = "http://www.tei-c.org/ns/1.0"


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


def contract_comments() -> list[str]:
    """Every `<!-- … -->` form the contract states, flattened onto one line each.

    The contract wraps them across lines for its own margins, so the text is joined
    before matching — a pattern that only matched the unwrapped form would pass here
    and fail on every real page.
    """
    body = " ".join(CONTRACT.read_text(encoding="utf-8").split())
    out, rest = [], body
    while "<!--" in rest:
        _, _, rest = rest.partition("<!--")
        text, _, rest = rest.partition("-->")
        out.append(text.strip())
    return out


@pytest.mark.parametrize("name,pat", CLASSES, ids=[n for n, _ in CLASSES])
def test_every_class_matches_a_form_the_contract_states(name, pat):
    """Dead surface is the failure this catches: a pattern for a comment nobody was
    ever told to write classifies nothing, forever, and no report would show it."""
    hits = [c for c in contract_comments() if pat.search(c)]
    assert hits, (
        f"{name} matches no comment form in {CONTRACT.name}. Either the contract "
        f"stopped asking for it — delete the pattern — or the wording drifted and "
        f"the pattern is now silently classifying nothing.")


def test_an_unknown_comment_is_other_rather_than_dropped():
    """The visible half of the asymmetry. A collator writing prose the classifier
    does not know still gets a row, because the point is to read the batch."""
    assert classify("this page is upside down and I am confused") == "other"


def test_the_witness_is_not_a_reservation(tmp_path):
    """It is on every page by construction, so pooling it would bury the real rows
    under itself — and it records an answer, not a question."""
    page(tmp_path, "1-075",
         '<pb n="53"/><!-- opens: flush to the measure --><p>x</p>')
    assert page_reservations("1-075", tmp_path) == []


def test_comments_are_pooled_with_their_ref_and_class(tmp_path):
    page(tmp_path, "1-075",
         '<pb n="53"/><!-- opens: indented -->'
         '<!-- printed folio 53 disagrees with expected 52 (predicted from '
         '1-074): check ToC alignment --><p>x</p>'
         '<!-- footnote continuation, no marker on this page: the note it '
         'continues is unresolved -->')
    got = page_reservations("1-075", tmp_path)
    assert [(r["ref"], r["class"]) for r in got] == [
        ("1-075", "folio_disagrees"), ("1-075", "footnote_orphan")]


def test_the_two_heading_causes_are_different_classes():
    """"The ToC has no such entry" is a finding about the book; "the check could not
    run" is a finding about this page's inputs. Reporting the second as the first is
    the fluent-nonsense failure in miniature, so they are never one row."""
    a = classify("heading-shaped text, no ToC match, no list/table follows: "
                 "needs a human call on where this attaches")
    b = classify("heading-shaped text, no folio to centre the ToC window: "
                 "match unchecked")
    assert a == "heading_unmatched" and b == "heading_unchecked" and a != b


def test_an_uncollated_page_yields_nothing_rather_than_raising(tmp_path):
    assert page_reservations("1-075", tmp_path) == []


def test_a_malformed_page_is_a_row_not_an_exception(tmp_path):
    """A measurement verb that raised on one bad page would take the whole batch's
    report down with it, which is the opposite of what pooling is for. `tei validate`
    is the gate; this says where to look."""
    d = tmp_path / "tei"
    d.mkdir(parents=True)
    (d / "chukchi-1-075.xml").write_text("<TEI><body>", encoding="utf-8")
    got = page_reservations("1-075", tmp_path)
    assert len(got) == 1 and got[0]["class"] == "unreadable"
