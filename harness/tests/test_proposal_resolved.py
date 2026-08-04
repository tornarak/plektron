"""`resolved` may name more than combining marks; the gate must not punish that.

The two directions of the resolved/text comparison are not symmetric, and they were
being computed as if they were. `_notation_codepoints` is deliberately narrow — the
things a `resolved` field is *obliged* to name — so `stated - present` flagged any
codepoint a reader spelled out that merely was not a combining mark, even when it
sits plainly in the text.

`2-042` failed on exactly that: it documented the hyphen of `Čiñeiˊ-ñew` and the
superscript of `Peruˊten³`. A hyphen is load-bearing in Americanist notation and the
superscript is the whole subject of §2.10, so both are what a careful reader writes
down — and the gate refused the page for writing them.

Worth a test rather than a comment because the failure mode is inverted: a gate that
fires on correct, thorough work teaches its readers to be less thorough, and the
symptom (a red gate) looks like the gate working. The direction that matters is the
other one — `resolved` describing a decision the text does not exhibit — and it is
pinned here too, since a fix that quieted the noise by dropping the check would look
identical on the page that prompted it.
"""

import json

import pytest

from harness.proposal_check import check, fix

TIER1 = "sometimes called Čiñeiˊ-ñew. They live on the sea-bottom"
RESOLVED = ("Čiñeiˊ-ñew = C+U+030C COMBINING CARON, i, n+U+0303 COMBINING TILDE, "
            "e, i, U+02CA MODIFIER LETTER ACUTE ACCENT, hyphen U+002D, "
            "n+U+0303 COMBINING TILDE, e, w")


def write(tmp_path, lines):
    p = tmp_path / "proposal.json"
    p.write_text(json.dumps({"lines": lines}), encoding="utf-8")
    return p


def issues(tmp_path, lines):
    return [i for i in check(write(tmp_path, lines))
            if "resolved" in i["issue"]]


def test_a_hyphen_spelled_out_in_resolved_is_not_a_mismatch(tmp_path):
    """The `2-042` case: an ASCII character that is genuinely in the text."""
    assert issues(tmp_path, {"26": {"text": TIER1, "resolved": RESOLVED}}) == []


def test_a_superscript_spelled_out_in_resolved_is_not_a_mismatch(tmp_path):
    """The other half of `2-042` — §2.10's subject, category No rather than Mn."""
    assert issues(tmp_path, {"30": {
        "text": "called Peruˊten³ (“one",
        "resolved": "Peruˊten = P, e, r, u, U+02CA; ³ = U+00B3 SUPERSCRIPT THREE",
    }}) == []


def test_resolved_naming_a_character_absent_from_the_text_still_fails(tmp_path):
    """The direction that matters, and the reason this cannot just be deleted.

    A `resolved` describing a keying decision the text does not exhibit argues an
    adjudicator into undoing correct work — CLAUDE.md's own framing, and the defect
    this arm exists for.
    """
    found = issues(tmp_path, {"7": {
        "text": "Kereˊtkun is sometimes",
        "resolved": "Kereˊtkun = K, e, r, e, U+02CA, t, k, u, n, U+0323 DOT BELOW",
    }})
    assert len(found) == 1
    assert "U+0323" in found[0]["detail"]


def test_notation_in_the_text_that_resolved_omits_still_fails(tmp_path):
    """Unchanged by the fix: the obligation to name marks is what the field is for."""
    found = issues(tmp_path, {"7": {
        "text": "keˊlet and g̣iˊrgol",
        "resolved": "keˊlet = k, e, U+02CA, l, e, t",
    }})
    assert len(found) == 1
    assert "in text not resolved" in found[0]["detail"]


@pytest.mark.parametrize("field", ["resolved", "text"])
def test_fix_does_not_pair_a_spelled_out_ascii_against_a_real_dangling_mark(
        tmp_path, field):
    """`fix()` shared the flaw, and there it could rewrite the wrong character.

    Its auto-swap fires on exactly one dangling item per side. A spurious entry —
    a documented hyphen — supplies a phantom partner for a genuine dangling mark,
    which is the same false-1-for-1 the medial-caps note in `_notation_codepoints`
    describes, arriving from the other direction. Nothing here is ambiguous, so
    nothing should be rewritten.
    """
    lines = {"26": {"text": TIER1, "resolved": RESOLVED}}
    p = write(tmp_path, lines)
    before = json.loads(p.read_text(encoding="utf-8"))["lines"]["26"][field]
    fix(p)
    after = json.loads(p.read_text(encoding="utf-8"))["lines"]["26"][field]
    assert after == before
