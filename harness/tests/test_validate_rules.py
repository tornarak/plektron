"""`validate()`'s rules are named, and the name list matches the code.

The function is 800-odd lines and, until the banners went in, **nobody knew how
many rules it held**. A review counted 22 by counting col-4 comment blocks. That
was wrong twice over: several blocks are notes *inside* a rule, and one of them
was a 29-line explanation of two rules that had been **deleted**, sitting
directly above a live check about `<lb>` and `<div>` that had nothing to do with
it. Its heading read "No whitespace immediately before a `<note>`" and it
described no code in the file.

That is the specific hazard this file exists against. The next thing anyone does
to this function is extract its rules into separate functions, and a mechanical
read — which is what extraction amounts to — would have carried that comment
onto the check below it and produced a rule named for notes that checks neither
notes nor whitespace. A wrong name on a validation rule is worse than no name:
it is what a reader trusts when deciding whether a failure matters.

So the docstring carries the list, the body carries `── rule: name ──` banners,
and these hold the two to each other in both directions.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "validate.py").read_text("utf-8")

BANNER = re.compile(r"^    # ── rule: ([a-z0-9-]+) ─+$", re.M)
#: The docstring block, which is indented four spaces and sits between the
#: heading and the couplings paragraph that follows it.
LISTED = re.compile(r"^        ([a-z0-9-]+) {2,}\S", re.M)


def banners() -> list[str]:
    return BANNER.findall(SRC)


def listed() -> list[str]:
    head = SRC.split("**The rules, in the order they run.**", 1)[1]
    return LISTED.findall(head.split("**Three couplings**", 1)[0])


def test_the_banners_and_the_docstring_agree():
    """Both directions and in order. A rule renamed in one place and not the
    other is the two-parsers-of-one-thing defect this repo keeps finding, at the
    smallest possible scale."""
    assert banners() == listed(), (
        f"banners {banners()}\nlisted   {listed()}\n"
        "The `── rule: ── ` markers in the body and the list in validate()'s "
        "docstring have diverged. They are one fact written twice on purpose, "
        "so that a rule cannot be added, renamed or removed silently."
    )


def test_every_rule_is_named_once():
    assert len(set(banners())) == len(banners()), "a rule name is used twice"
    assert banners(), "no rule banners found — the pattern has stopped matching"


def test_schema_runs_last():
    """Not a style preference. A conformance failure is a different kind of
    statement from a project-rule failure, and a reader meeting "not conformant
    TEI" among the edition's own rules would take it for one of them. The
    extraction must preserve this whatever else it reorders."""
    assert banners()[-1] == "schema"


def test_metrics_runs_after_every_rule_that_feeds_it():
    """`r.metrics` is **assigned** wholesale from locals set across the whole
    body, not updated — so it cannot move earlier, and every extracted rule will
    have to hand its counters back rather than keep them."""
    names = banners()
    assert names[-2] == "metrics", "metrics must sit immediately before schema"
    assert "r.metrics = {" in SRC


def test_the_deleted_rules_comment_is_not_attached_to_a_live_check():
    """The specific trap. The `<lb>`/`<div>` check must carry its own banner and
    its own explanation; the history of the two removed `<note>` rules must be
    marked as history and must not be the last thing a reader sees before that
    check."""
    assert "── rule: line-and-division ─" in SRC
    hist = SRC.index("Two rules were removed from this spot")
    rule = SRC.index("── rule: line-and-division ─")
    assert hist < rule, "the history must precede the banner, not sit inside it"
    between = SRC[rule:SRC.index('"<lb/> present')]
    assert "<note>" not in between, (
        "the `<lb>`/`<div>` rule's own comment mentions <note> again — that is "
        "how the two got confused in the first place"
    )


def test_the_tier1_counters_are_credited_to_the_rule_that_sets_them():
    """**The enumeration commit got this wrong and this is why it exists.**
    `tier1_spans` and `tier1_adopted` are set in `lang-and-glyphs`, whose name
    does not suggest counting, while `provenance` — which does — counts nothing.
    The two are adjacent, and the first pass credited the wrong one.

    Checked against the code rather than against the prose: find where the
    counters are assigned, and assert that position falls inside the rule the
    docstring names."""
    banners = [(m.start(), m.group(1)) for m in BANNER.finditer(SRC)]
    setter = SRC.index("    tier1_spans = 0")
    owner = [name for pos, name in banners if pos < setter][-1]
    assert owner == "lang-and-glyphs", (
        f"`tier1_spans` is now initialised inside {owner!r}. Update the coupling "
        "note in validate()'s docstring and the comment on provenance-summary — "
        "both name the rule that sets it."
    )
    assert "**`lang-and-glyphs`**" in SRC, (
        "the docstring no longer credits lang-and-glyphs with the counters"
    )


def test_the_couplings_are_documented():
    """Three, and they are the whole design problem of extracting this. A
    docstring that stopped naming them would let someone extract the rules into
    an order-independent list, which they are not."""
    head = SRC.split("**Three couplings**", 1)[1][:800]
    for name in ("provenance-summary", "relink-missing", "metrics"):
        assert name in head, f"{name} is no longer named as a coupling"
