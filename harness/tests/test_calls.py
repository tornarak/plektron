"""The ledger's own claims, and the two places it does not yet keep them.

`calls.py` exists because a reader's self-reported tally came out flattering every
time — the count has to be written by the tool at the moment of the call, not
recalled at the end. That makes two properties load-bearing, and they pull against
each other: the ledger must record what actually happened, and it must never be
able to abort the pass it is measuring. A ledger that raises turns bookkeeping into
a precondition for reading a page; a ledger that silently drops a call is the
flattering tally again, only now with the tool's authority behind it.

So these test the *failure* directions rather than the happy path, and four of
them were written against behaviour that was wrong at the time and has since
been fixed. Each keeps its account of the old behaviour, because that is what
says why the property is worth a test at all:

  - `images=0` and `zoom=0` were deleted by a falsy filter (`0 == False` in
    Python), so the ledger dropped the smallest count there is;
  - a non-serialisable `detail` escaped `except OSError` as a `TypeError` and
    killed the reading the ledger was recording;
  - `call_summary` indexed `c["action"]` unguarded, so a valid JSON line without
    that key crashed the summary the tolerant reader existed to protect;
  - an interrupted append cost two records rather than one, the torn line eating
    the good one written onto it.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness import calls


def test_a_reaimed_crop_shows_as_the_same_line_twice(tmp_path):
    """The re-aim signature is the whole point of `repeats`: a reader that opens
    line 4 again after already having it did not know what it was looking for.
    Two calls naming three tokens between them, one of which collides, is one
    repeat over two distinct lines — not three calls' worth of anything."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="3,4@2")
    calls.log_call("3-004", "zoom", root=tmp_path, only="4")
    s = calls.call_summary("3-004", root=tmp_path)
    assert s["repeats"] == 1
    assert s["lines_opened"] == 2
    assert s["calls"] == 2


def test_the_scale_suffix_is_not_part_of_the_line_identity(tmp_path):
    """`4` and `4@4` are the same line at two magnifications, which is exactly
    the re-aim the count is meant to catch — partitioning on `@` is what makes
    the second call a repeat rather than a new doubt."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="4@2")
    calls.log_call("3-004", "zoom", root=tmp_path, only="4@4")
    s = calls.call_summary("3-004", root=tmp_path)
    assert s["lines_opened"] == 1
    assert s["repeats"] == 1


def test_whitespace_in_the_spec_does_not_mint_a_second_line(tmp_path):
    """`only` is typed by hand at the call site, so `3, 4` has to mean `3,4`."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="3, 4")
    calls.log_call("3-004", "zoom", root=tmp_path, only="4")
    assert calls.call_summary("3-004", root=tmp_path)["repeats"] == 1


def test_a_call_that_named_no_line_still_counts_as_a_call(tmp_path):
    """A whole-page composite is an image call — it costs the same to produce and
    it belongs in the series — but it opened no particular line, so it must not
    inflate `lines_opened` or collide with the next one."""
    calls.log_call("3-004", "page", root=tmp_path)
    calls.log_call("3-004", "page", root=tmp_path)
    s = calls.call_summary("3-004", root=tmp_path)
    assert s["calls"] == 2
    assert s["lines_opened"] == 0
    assert s["repeats"] == 0


def test_an_empty_page_summarises_rather_than_failing(tmp_path):
    """`ocr calls` runs over pages nobody has opened yet; absence is a count of
    zero, not an error, and the ref still has to come back normalised."""
    s = calls.call_summary("3-4", root=tmp_path)
    assert s == {"ref": "3-004", "calls": 0, "zooms": 0, "at_4x": 0,
                 "lines_opened": 0, "repeats": 0, "no_reason": 0}


def test_only_zooms_are_asked_for_a_reason(tmp_path):
    """`--reason` is the field that survives the after-the-fact rewrite, so an
    unexplained zoom is the thing worth counting. A composite needs no defence."""
    calls.log_call("3-004", "page", root=tmp_path)
    calls.log_call("3-004", "zoom", root=tmp_path, only="3", zoom=4)
    calls.log_call("3-004", "zoom", root=tmp_path, only="5", zoom=4,
                   reason="digit shapes")
    s = calls.call_summary("3-004", root=tmp_path)
    assert s["zooms"] == 2
    assert s["at_4x"] == 2
    assert s["no_reason"] == 1


def test_the_series_keeps_the_order_it_was_written_in(tmp_path):
    """The adjudicator reads the series, not the summary: a miss re-aimed three
    calls later reads differently from one re-aimed immediately."""
    for line in ("3", "7", "3"):
        calls.log_call("3-004", "zoom", root=tmp_path, only=line)
    assert [c["only"] for c in calls.read_calls("3-004", root=tmp_path)] == \
        ["3", "7", "3"]


def test_the_ledger_is_append_only_across_calls(tmp_path):
    """Nothing here rewrites a line — a ledger the measured party can edit is not
    a ledger, and the writer must therefore never truncate the file."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="1")
    calls.log_call("3-004", "zoom", root=tmp_path, only="2")
    text = calls.calls_path("3-004", tmp_path).read_text(encoding="utf-8")
    assert text.count("\n") == 2


def test_a_half_written_line_costs_that_line_and_nothing_else(tmp_path):
    """A truncated record must not cost the page's whole record. Refusing to read
    the file at all would lose forty crops' worth of series over one bad line, so
    the broken line is dropped and everything around it still reports."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="1")
    p = calls.calls_path("3-004", tmp_path)
    with p.open("a", encoding="utf-8") as fh:
        fh.write('{"action": "zoom", "only": "2\n')
    calls.log_call("3-004", "zoom", root=tmp_path, only="3")
    got = calls.read_calls("3-004", root=tmp_path)
    assert [c["only"] for c in got] == ["1", "3"]
    assert calls.call_summary("3-004", root=tmp_path)["lines_opened"] == 2


def test_an_unterminated_tail_costs_one_record_not_two(tmp_path):
    """A pass killed mid-append leaves a last line with no newline. Opening in
    `a` used to write the next record straight onto it, so one interrupted crop
    cost **two** records — the torn one and the good one that landed on it. The
    writer now starts a fresh line when the file does not end in one, so the
    damage stops at the record that was actually interrupted.

    The case is ordinary rather than theoretical: the pass this records is ended
    by a reader running out of turns."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="1")
    p = calls.calls_path("3-004", tmp_path)
    with p.open("a", encoding="utf-8") as fh:
        fh.write('{"action": "zoom", "only": "2')  # crash: no newline
    calls.log_call("3-004", "zoom", root=tmp_path, only="3")
    got = calls.read_calls("3-004", root=tmp_path)
    assert [c["only"] for c in got] == ["1", "3"], "the torn line ate a good one"
    assert calls.call_summary("3-004", root=tmp_path)["calls"] == 2


def test_blank_lines_are_not_records(tmp_path):
    p = calls.calls_path("3-004", tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text('\n{"action": "page"}\n\n', encoding="utf-8")
    assert calls.read_calls("3-004", root=tmp_path) == [{"action": "page"}]


def test_an_unwritable_ledger_does_not_stop_the_page(tmp_path):
    """The docstring's promise, in the shape it will actually arrive: a read-only
    or occupied `review/` must cost the record, not the reading. Here the
    directory the ledger needs is already a file, so `mkdir` raises."""
    (tmp_path / "review").write_text("not a directory", encoding="utf-8")
    calls.log_call("3-004", "zoom", root=tmp_path, only="3")  # must not raise
    assert calls.read_calls("3-004", root=tmp_path) == []


def test_a_missing_action_key_does_not_crash_the_summary(tmp_path):
    """`read_calls` tolerates a malformed *line*, and `call_summary` used to
    index `c["action"]` unguarded — so a line that is valid JSON without that
    key, an older schema or a hand-edited file, took down the summary the
    tolerant reader existed to protect. A guard that only half exists.

    The record still counts as a call and still contributes its `only` spec; it
    is simply not a zoom, which is what the file says about it."""
    p = calls.calls_path("3-004", tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text('{"only": "3"}\n', encoding="utf-8")
    assert calls.read_calls("3-004", root=tmp_path) == [{"only": "3"}]
    s = calls.call_summary("3-004", root=tmp_path)
    assert s["calls"] == 1 and s["zooms"] == 0 and s["lines_opened"] == 1


def test_a_non_serialisable_detail_does_not_abort_the_pass(tmp_path):
    """The promise is unconditional — measurement never breaks a pass — and a
    detail value is whatever the call site passed, which is exactly the argument
    nobody validates. The catch was `OSError` alone, so a `Path`, a `set` or a
    numpy scalar raised `TypeError` out of `json.dumps` and killed the reading.
    """
    calls.log_call("3-004", "zoom", root=tmp_path, only="3", span=object())
    assert calls.read_calls("3-004", root=tmp_path), "the record was lost"


def test_a_non_serialisable_detail_is_rendered_rather_than_refused(tmp_path):
    """`default=str` rather than dropping the key: an entry saying
    `"span": "<object object at 0x…>"` is worth more than no entry, and the
    broadened catch is the backstop under it rather than the mechanism."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="3", span=Path("/tmp/x"))
    rec = calls.read_calls("3-004", root=tmp_path)[0]
    assert "/tmp/x" in rec["span"]


def test_a_zero_valued_detail_is_kept(tmp_path):
    """A ledger whose justification is that self-reported counts come out
    flattering must not itself delete the smallest count there is. `images=0` is
    a claim about the page; absence is a claim about the record.

    The old filter was `v not in (None, "", False)`, and `0 == False` in Python,
    so a membership test could not tell a count from an unset flag. Stated here
    rather than asserted: `0 is not False` is the fix and also a thing neither
    ruff nor CPython will let a test say — the linter rewrites it to `!=`, which
    inverts it, and the interpreter warns. So the property is pinned by what the
    writer *does*, which nothing can rewrite, and the language fact stays prose.
    """
    calls.log_call("3-004", "page", root=tmp_path, images=0, zoom=0)
    assert calls.read_calls("3-004", root=tmp_path)[0] == \
        {"action": "page", "images": 0, "zoom": 0}


def test_the_unset_optionals_are_still_dropped(tmp_path):
    """The control: keeping zero must not turn the filter off. `None` and `""`
    are what it was for — an argument the call site did not supply."""
    calls.log_call("3-004", "page", root=tmp_path, images=0, only=None, note="")
    assert calls.read_calls("3-004", root=tmp_path)[0] == \
        {"action": "page", "images": 0}


def test_a_nonzero_detail_of_the_same_kind_survives(tmp_path):
    """The control for the test above: the values are dropped for being zero,
    not for being named `images` or `zoom`."""
    calls.log_call("3-004", "page", root=tmp_path, images=1, zoom=4)
    assert calls.read_calls("3-004", root=tmp_path)[0] == \
        {"action": "page", "images": 1, "zoom": 4}


def test_a_zoom_recorded_as_zero_is_countable_afterwards(tmp_path):
    """What the dropped zero used to cost downstream: `at_4x` and every other
    per-call figure read the field back off the line, and the line no longer had
    it — so "zoomed at 0" and "named no scale" were the same record."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="3", zoom=0)
    assert calls.read_calls("3-004", root=tmp_path)[0]["zoom"] == 0


def test_a_reason_is_kept_even_though_the_filter_would_not_see_it(tmp_path):
    """`reason` is added after the filter runs, which is why an empty one is
    dropped by its own explicit check and a real one always survives."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="3", reason="")
    calls.log_call("3-004", "zoom", root=tmp_path, only="4", reason="0")
    a, b = calls.read_calls("3-004", root=tmp_path)
    assert "reason" not in a
    assert b["reason"] == "0"


def test_the_ledger_lands_under_the_page_it_measures(tmp_path):
    """Written where the page's working files live, and named by the canonical
    ref, so `ocr calls` finds it without a second index to keep in step."""
    calls.log_call("3-4", "page", root=tmp_path)
    p = tmp_path / "review" / "3-004" / "calls.jsonl"
    assert p.exists()
    assert calls.calls_path("3-004", tmp_path) == p


def test_a_unicode_reason_is_not_escaped(tmp_path):
    """`ensure_ascii=False`: the corpus is NFD and full of inventory glyphs, and
    a reason a human reads should not arrive as escapes."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="3", reason="ᵋ vs ˙")
    line = calls.calls_path("3-004", tmp_path).read_text(encoding="utf-8")
    assert "ᵋ vs ˙" in line
    assert calls.read_calls("3-004", root=tmp_path)[0]["reason"] == "ᵋ vs ˙"


def test_one_record_per_line(tmp_path):
    """JSONL is what makes a truncated tail cost one call rather than the page,
    so no record may contain a raw newline of its own."""
    calls.log_call("3-004", "zoom", root=tmp_path, only="3", reason="a\nb")
    lines = calls.calls_path("3-004", tmp_path).read_text(
        encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["reason"] == "a\nb"
