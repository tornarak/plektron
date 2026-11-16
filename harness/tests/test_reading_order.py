"""`harness ocr order`: the greedy step, on hand-built pages."""
from __future__ import annotations

from collections import Counter

from harness.reading_order import greedy


def test_the_page_whose_forms_recur_most_elsewhere_comes_first():
    pages = {"1-010": Counter({"a": 1}),            # a recurs twice elsewhere
             "1-011": Counter({"a": 1, "b": 1}),
             "1-012": Counter({"a": 1, "c": 5}),    # c is all on this page
             "1-013": Counter({"b": 1})}
    rows = greedy(pages, set())
    assert rows[0]["ref"] == "1-011"              # a (2 elsewhere) + b (1)
    assert rows[0]["buys"] == 3
    # Once a and b are seen nothing else buys anything; ties go to book order.
    assert [r["ref"] for r in rows[1:]] == ["1-010", "1-012", "1-013"]
    assert [r["buys"] for r in rows[1:]] == [0, 0, 0]


def test_forms_already_ratified_buy_nothing():
    pages = {"1-010": Counter({"a": 1}), "1-011": Counter({"a": 1, "b": 1}),
             "1-012": Counter({"b": 1})}
    rows = greedy(pages, {"a"})
    assert rows[0]["buys"] == 1 and rows[0]["new"] == 1


def test_a_word_broken_across_a_line_end_is_one_form(tmp_path):
    """`А́й-` / `ђынто` is one form, without the compositor's hyphen — the cut
    `joined_words` marks — so it meets `А́јђынто` set mid-line, not two forms."""
    from harness.detectors import joined_words
    texts, cuts = joined_words([{"text": "вернулся А́й-", "zone": "MainZone-P"},
                                {"text": "ђынто и привезъ", "zone": "MainZone-P"}])
    whole = "".join(c for k, c in enumerate(texts[0]) if k not in set(cuts[0]))
    assert whole.split()[-1] == "А́йђынто" and texts[1] == "и привезъ"
