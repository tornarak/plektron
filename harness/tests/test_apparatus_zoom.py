"""A folio may not be zoomed — the most structured text on the page, and its most expensive.

The folio is two or three ASCII digits, set in the same type as the running title
beside it, in a zone the segmenter labels. Nothing a 4x crop can say about it was
not already legible on the numbered composite. It has nonetheless been this pass's
steadiest drain and, once, its outright error:

  - four pages across two batches spent **42,620 tokens** hunting one at the
    ceiling (`1-051` 13,140 · `1-045` 11,261 · `1-054` 10,505 · `1-047` 7,714);
  - `1-051`'s reader was sent hunting by a crop that cut the number in half, which
    is what `PAD_X` was raised to fix;
  - `1-063` keyed `141` for a folio reading `41`.

The standing brief has told readers not to do this since the second batch and they
kept doing it, so it is refused rather than discouraged — the difference between a
rule and a suggestion. The refusal is **zone-scoped**, not line-scoped: which of
`FOLIO_ZONES` a given page's folio landed in is exactly what a reader cannot know
in advance, and a rule keyed to "line 1" would miss the pages where it is not.

What is deliberately NOT claimed here: that this prevents a misread folio. `1-063`
never zoomed — it read the composite and keyed the wrong digits. This rule ends the
spending, and the correctness question is a separate instrument.
"""
from __future__ import annotations

from harness.cli._ocr import apparatus_hits
from harness.context import FOLIO_ZONES
from harness.lines import parse_spans


def page(*zones) -> list[dict]:
    """A page as `page_lines` yields it: index and zone are all this decides on."""
    return [{"index": i, "zone": z} for i, z in enumerate(zones)]


ORDINARY = page("RunningTitleZone", "RunningTitleZone", "MainZone-P", "MainZone-P")


def test_a_folio_line_is_refused():
    assert apparatus_hits(ORDINARY, parse_spans("1@50")) == [1]


def test_the_running_title_is_refused_too():
    """Not only the number. The head line is the printer's text as much as the
    folio is, and a reader zooming it is reading something it does not key."""
    assert apparatus_hits(ORDINARY, parse_spans("0@0")) == [0]


def test_body_lines_are_untouched():
    assert apparatus_hits(ORDINARY, parse_spans("2@40,3@60")) == []


def test_one_apparatus_line_in_a_batch_refuses_the_whole_call():
    """The call is one image, so it cannot be partly served. Refusing names the
    offending line and asks for a re-run, rather than silently dropping it and
    returning a crop the caller did not ask for."""
    assert apparatus_hits(ORDINARY, parse_spans("1@50,2@40")) == [1]


def test_every_folio_zone_counts_not_just_the_running_title():
    """Which zone the folio landed in is what a reader cannot know in advance —
    it sits in the head line on an ordinary page and in the signature line at the
    foot of a gathering."""
    for zone in FOLIO_ZONES:
        assert apparatus_hits(page("MainZone-P", zone), parse_spans("1@0")) == [1]


def test_hits_come_back_in_index_order():
    """The message lists them, and a list out of order reads as a second finding."""
    p = page("RunningTitleZone", "MainZone-P", "QuireMarksZone")
    assert apparatus_hits(p, parse_spans("2@10,0@90")) == [0, 2]


def test_a_line_the_page_does_not_have_is_not_apparatus():
    """A nonexistent index is a different error with a different message, and
    answering it here would answer the wrong question."""
    assert apparatus_hits(ORDINARY, parse_spans("99@50")) == []


def test_a_zone_the_page_does_not_label_is_not_apparatus():
    """An unlabelled line is a segmentation gap, not a licence and not a folio."""
    assert apparatus_hits([{"index": 0, "zone": None}], parse_spans("0@0")) == []
