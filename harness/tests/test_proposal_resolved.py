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
import unicodedata

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
    adjudicator into undoing correct work — the reading pass's own framing, and the defect
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


# --- a precomposed codepoint named in `resolved` ----------------------------

PRECOMPOSED = unicodedata.normalize("NFD", "êlh-aˊᵋttᴀm")
NAMES_EA = ("ê = U+00EA LATIN SMALL LETTER E WITH CIRCUMFLEX, l, h, hyphen, "
            "a, U+02CA MODIFIER LETTER ACUTE ACCENT, U+1D4B MODIFIER LETTER "
            "SMALL OPEN E, t, t, U+1D00 LATIN LETTER SMALL CAPITAL A, m")


def test_naming_a_precomposed_letter_is_not_a_mismatch(tmp_path):
    """U+00EA is how a reader refers to "ê", and the corpus stores it decomposed.

    Compared literally, the named codepoint is *always* absent from an NFD text and
    the combining mark actually present is *always* unaccounted for — one dangling
    item on each side, which is precisely the shape `fix()` treats as an
    unambiguous swap.
    """
    assert issues(tmp_path, {"38": {"text": PRECOMPOSED,
                                    "resolved": NAMES_EA}}) == []


def test_fix_does_not_graft_a_precomposed_letter_onto_its_own_base(tmp_path):
    """The corruption this caused on `1-039` line 38: `êlh-` became `eêlh-`.

    `fix` paired the combining circumflex against the named U+00EA and substituted
    the precomposed letter into the *mark's* slot, after the base `e` it was meant
    to have merged with. The reader found it with `codepoints` and worked around it
    by respelling every `resolved` field as decompositions — a human degrading
    their own notes to get past a parser.
    """
    p = write(tmp_path, {"38": {"text": PRECOMPOSED, "resolved": NAMES_EA}})
    assert fix(p)["changed"] == []
    after = json.loads(p.read_text(encoding="utf-8"))["lines"]["38"]["text"]
    assert after == PRECOMPOSED
    assert "ê" in after and "eê" not in after


def test_fix_writes_nfd_even_when_resolved_names_a_precomposed_target(tmp_path):
    """A genuine swap whose target is precomposed must not leak NFC into the store.

    The docstring claimed this ("composes the replacement back to NFC-free NFD")
    for as long as the code did the opposite; only `corpus normalize`, run later
    and separately, would have caught it.
    """
    text = unicodedata.normalize("NFD", "å" + "bc")   # a + ring above
    p = write(tmp_path, {"7": {"text": text,
                               "resolved": "U+00EA LATIN SMALL LETTER E WITH "
                                           "CIRCUMFLEX, b, c"}})
    fix(p)
    after = json.loads(p.read_text(encoding="utf-8"))["lines"]["7"]["text"]
    assert after == unicodedata.normalize("NFD", after)
