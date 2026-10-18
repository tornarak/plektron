"""`harness agents usage` — the cohort arithmetic and the transcript reader.

The verb's whole value is that it refuses to report a shared prefix nobody had,
so that refusal is what these test hardest: a session holding several fan-outs
must not average into one, and a lone agent must not have its opening promoted
to a shared number.
"""
from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime, timedelta

import pytest

from harness import usage
from harness.usage import (
    TTL,
    TTLS,
    _agent,
    _requests,
    _slug,
    classes,
    cohort_classes,
    cohort_ids,
    cohorts,
    cost,
    find_transcripts,
    in_cohort,
    preamble,
    project,
    rows,
    since_stamp,
    transcript,
    warmth,
)


def _line(read: int, write: int, out: int = 5, at: str = "2026-08-04T12:00:00.000Z",
          model: str = "claude-sonnet-5") -> str:
    return json.dumps({
        "type": "assistant", "timestamp": at, "model": model,
        "message": {"role": "assistant", "usage": {
            "input_tokens": 1, "cache_creation_input_tokens": write,
            "cache_read_input_tokens": read, "output_tokens": out}},
    })


def _transcript(tmp_path, name: str, reqs) -> None:
    (tmp_path / f"{name}.output").write_text(
        "\n".join([json.dumps({"type": "user", "message": {"content": "hi"}})]
                  + [_line(*r) for r in reqs]) + "\n")


def _made(model="sonnet-5", opening=35798, opened="warm", last="2026-08-04T12:00:00Z",
          ttl="5m", session="s1", pre=None, ctx=None, atype="moll-reader",
          ctxs=None, walk=None, billed_in=0, out=0, read=0):
    return {"model": model, "opening": opening, "opened": opened, "last": last,
            "type": atype, "ctxs": ctxs if ctxs is not None else [opening],
            "ttl": ttl, "session": session, "pre": pre or [],
            "walk": walk or [], "ctx": opening if ctx is None else ctx,
            "billed_in": billed_in, "out": out, "read": read}


def _walked(klass: str, result: int, reply: int = 0) -> dict:
    """One already-decomposed request, for the aggregations that take a walk."""
    return {"class": klass, "result": result, "reply": reply,
            "added": result + reply}


# --- the transcript reader ------------------------------------------------

def test_requests_skips_non_usage_lines(tmp_path):
    _transcript(tmp_path, "a1", [(0, 100), (100, 20)])
    assert [r["read"] for r in _requests(tmp_path / "a1.output")] == [0, 100]


def test_requests_survives_a_truncated_line(tmp_path):
    """A transcript being appended to while it is read must not take the verb
    down: a half-written final line is ordinary, not a corrupt file."""
    p = tmp_path / "a1.output"
    p.write_text(_line(0, 100) + "\n" + _line(100, 20)[:40])
    assert len(_requests(p)) == 1


def test_agent_opening_is_first_request_read_plus_write(tmp_path):
    _transcript(tmp_path, "abcdef0123", [(0, 35798), (35798, 16031), (51829, 400)])
    a = _agent(tmp_path / "abcdef0123.output")
    assert a["opening"] == 35798        # not 51829: the first request only
    assert a["opened"] == "COLD"        # wrote it rather than read it
    assert a["tail"] == 16431           # writes after the opening
    assert a["agent"] == "abcdef01"


def test_agent_warm_when_first_request_read_and_wrote_nothing(tmp_path):
    _transcript(tmp_path, "b1", [(35798, 0), (35798, 900)])
    assert _agent(tmp_path / "b1.output")["opened"] == "warm"


def test_agent_of_an_empty_transcript_is_none(tmp_path):
    (tmp_path / "c1.output").write_text("")
    assert _agent(tmp_path / "c1.output") is None


def test_a_workflow_run_directory_is_read_under_its_own_name(tmp_path):
    """A Workflow leaves `agent-<id>.jsonl` and no `tasks/` link. Globbing only
    `*.output` reported such a batch as no agents at all, and the id must lose
    the prefix or every row would read `agent-ab`."""
    (tmp_path / "agent-abcdef0123.jsonl").write_text(_line(0, 35798) + "\n")
    _, agents = usage.batch(tmp_path, tmp_path)
    assert [a["agent"] for a in agents] == ["abcdef01"]
    assert find_transcripts(tmp_path, ["abcd"], tmp_path) == [
        tmp_path / "agent-abcdef0123.jsonl"]


# --- transcript -----------------------------------------------------------

def _tool_line(read, write, tool, detail, out=5, rid="r"):
    return json.dumps({
        "type": "assistant", "timestamp": "2026-08-04T12:00:00.000Z",
        "model": "claude-sonnet-5", "requestId": rid,
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": tool, "input": detail}],
            "usage": {"input_tokens": 2, "cache_creation_input_tokens": write,
                      "cache_read_input_tokens": read, "output_tokens": out}},
    })


def test_transcript_attributes_growth_to_the_previous_tool(tmp_path):
    """The growth between two requests is the result of what the earlier one
    asked for, so that is where the note comes from."""
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 35300, "Bash", {"command": "entry_bounds.py claim"}, rid="a"),
        _tool_line(35300, 4270, "Read", {"file_path": "/x/moll-046.png"}, rid="b"),
        _tool_line(39570, 300, "Write", {"file_path": "/x/moll-046.md"}, rid="c"),
    ]) + "\n")
    rows = transcript(p)
    assert rows[0]["note"] == "system prompt + preamble"
    assert (rows[1]["note"], rows[1]["detail"]) == ("ran command",
                                                    "entry_bounds.py claim")
    assert (rows[2]["note"], rows[2]["detail"]) == ("read raster", "moll-046.png")


def test_transcript_added_is_the_context_delta(tmp_path):
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 35300, "Bash", {"command": "x"}, rid="a"),
        _tool_line(35300, 4270, "Read", {"file_path": "/x/p.png"}, rid="b"),
    ]) + "\n")
    rows = transcript(p)
    assert rows[0]["added"] == 35302        # in + read + write, no predecessor
    assert rows[1]["added"] == 4270


def test_via_says_whether_the_growth_was_paid_for(tmp_path):
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(35300, 0, "Bash", {"command": "x"}, rid="a"),
        _tool_line(35300, 475, "Bash", {"command": "y"}, rid="b"),
    ]) + "\n")
    rows = transcript(p)
    assert [r["via"] for r in rows] == ["read", "write"]


def test_a_text_read_is_not_called_a_raster(tmp_path):
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 100, "Read", {"file_path": "/x/notes.md"}, rid="a"),
        _tool_line(100, 50, "Bash", {"command": "z"}, rid="b"),
    ]) + "\n")
    assert transcript(p)[1]["note"] == "read text"


# --- the reply/result split -----------------------------------------------

def _result_line(payload, rid="x") -> str:
    """A tool result coming back, as the runtime records it.

    A refusal and a non-zero exit arrive as bare strings; anything that worked
    is a dict carrying `stdout`, which is what tells the three apart.
    """
    return json.dumps({"type": "user", "requestId": rid,
                       "toolUseResult": payload,
                       "message": {"role": "user", "content": "result"}})


def test_added_splits_into_the_reply_and_what_the_tool_returned(tmp_path):
    """The measurement the whole breakdown rests on.

    A request's growth is the agent's own reply plus its tool's result, and the
    reply is recorded, so the result is a subtraction rather than a share-out.
    Here a 900-token reply precedes a 1,000-token growth: 100 of it is the tool's.
    """
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 500, "Bash", {"command": "x"}, out=900, rid="a"),
        _tool_line(500, 1000, "Bash", {"command": "y"}, out=7, rid="b"),
    ]) + "\n")
    row = transcript(p)[1]
    assert (row["added"], row["reply"], row["result"]) == (1000, 900, 100)


def test_result_is_left_signed(tmp_path):
    """A negative means the decomposition does not hold there, and that is the
    one case worth seeing — clamping it to zero would hide it."""
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 500, "Bash", {"command": "x"}, out=900, rid="a"),
        _tool_line(500, 100, "Bash", {"command": "y"}, out=7, rid="b"),
    ]) + "\n")
    assert transcript(p)[1]["result"] == -800


def test_the_first_request_is_all_opening_and_owes_no_reply(tmp_path):
    p = tmp_path / "abcdef01.output"
    p.write_text(_tool_line(0, 35300, "Bash", {"command": "x"}, rid="a") + "\n")
    row = transcript(p)[0]
    assert (row["class"], row["reply"], row["result"]) == ("opening", 0, 35302)


def test_a_refused_call_is_not_counted_as_a_command(tmp_path):
    """The finding this class exists for: a guard-blocked call never ran, so
    every token it cost bought nothing, and pooling it with the commands that
    did run is what made a batch's waste invisible."""
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 500, "Bash", {"command": "ls review/"}, rid="a"),
        _result_line("Error: PreToolUse:Bash hook error: [guard.sh]: Blocked: no"),
        _tool_line(500, 138, "Bash", {"command": "ocr lines 1-057"}, rid="b"),
    ]) + "\n")
    assert transcript(p)[1]["class"] == "refused"


def test_a_gate_exiting_nonzero_is_failed_and_not_refused(tmp_path):
    """`proposal check` reporting an advisory is a gate doing its job. It is a
    different fact from a call the guard stopped, and the two must not pool."""
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 500, "Bash", {"command": "proposal check 1-057"}, rid="a"),
        _result_line("Error: Exit code 1\n[1]{line,issue}:\n  12,advisory"),
        _tool_line(500, 90, "Bash", {"command": "x"}, rid="b"),
    ]) + "\n")
    assert transcript(p)[1]["class"] == "failed"


def test_a_command_that_worked_is_an_ordinary_command(tmp_path):
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 500, "Bash", {"command": "ocr gaps 1-057"}, rid="a"),
        _result_line({"stdout": "[0]:", "stderr": "", "interrupted": False}),
        _tool_line(500, 90, "Bash", {"command": "x"}, rid="b"),
    ]) + "\n")
    assert transcript(p)[1]["class"] == "command"


def test_a_fate_does_not_leak_onto_the_next_request(tmp_path):
    """A result is filed against the call that asked for it, so the request
    after a refusal is classified by its own tool."""
    p = tmp_path / "abcdef01.output"
    p.write_text("\n".join([
        _tool_line(0, 500, "Bash", {"command": "ls"}, rid="a"),
        _result_line("Error: PreToolUse:Bash hook error: Blocked"),
        _tool_line(500, 138, "Read", {"file_path": "/x/p.png"}, rid="b"),
        _result_line({"type": "image"}),
        _tool_line(638, 4026, "Bash", {"command": "x"}, rid="c"),
    ]) + "\n")
    assert [r["class"] for r in transcript(p)] == ["opening", "refused", "raster"]


# --- the class breakdown ---------------------------------------------------

def test_classes_sum_to_the_context_and_say_so(tmp_path):
    """`pct` is a share of something real: every request's growth belongs to
    exactly one class, and the `ALL` row carries the total they are taken against."""
    walk = [_walked("opening", 50000), _walked("raster", 4000),
            _walked("raster", 6000), _walked("command", 400)]
    table = {r["class"]: r for r in classes(walk)}
    assert table["ALL"]["tokens"] == 60400
    assert table["raster"]["calls"] == 2
    assert table["raster"]["tokens"] == 10000
    assert table["ALL"]["pct"] == "100.0%"


def test_classes_separate_a_big_class_from_a_frequent_one(tmp_path):
    """`mean` and `max` are why the table is not just counts: a class large
    because one call was expensive reads differently from one large because it
    recurred, and the fix for each is a different instruction."""
    table = {r["class"]: r for r in classes(
        [_walked("raster", 7000), _walked("raster", 1000),
         _walked("command", 500), _walked("command", 500)])}
    assert (table["raster"]["mean"], table["raster"]["max"]) == (4000, 7000)
    assert (table["command"]["mean"], table["command"]["max"]) == (500, 500)


def test_reply_is_a_column_and_never_a_class(tmp_path):
    """It belongs to no tool — every request has one — so folding it into a
    class would put the agent's own thinking under whatever it called next."""
    table = {r["class"]: r for r in classes(
        [_walked("command", 100, reply=900), _walked("raster", 4000, reply=50)])}
    assert "reply" not in table
    assert table["ALL"]["reply"] == 950
    assert table["ALL"]["tokens"] == 4100        # results only


def test_classes_of_nothing_is_empty_rather_than_a_zero_row(tmp_path):
    assert classes([]) == []


# --- cohorts as batches ----------------------------------------------------

def test_cohorts_are_numbered_oldest_batch_first():
    agents = [_made(opening=100, last="2026-08-04T12:00:00Z"),
              _made(opening=100, last="2026-08-04T12:00:09Z"),
              _made(opening=200, last="2026-08-04T09:00:00Z")]
    ids = cohort_ids(agents)
    assert ids[("moll-reader", "sonnet-5", 200)] == "c1"   # finished first
    assert ids[("moll-reader", "sonnet-5", 100)] == "c2"


def test_every_agent_row_carries_its_cohort():
    """Which reader belongs to which fan-out, without matching openings by eye."""
    agents = [_made(opening=100), _made(opening=200)]
    assert {r["cohort"] for r in rows(agents)} == {"c1", "c2"}


def test_the_agents_and_cohorts_tables_agree_on_the_ids():
    agents = [_made(opening=100, last="2026-08-04T12:00:00Z"),
              _made(opening=200, last="2026-08-04T09:00:00Z")]
    by_opening = {r["opening"]: r["cohort"] for r in rows(agents)}
    for c in cohorts(agents):
        assert by_opening[c["opening"]] == c["cohort"]


def test_a_cohort_breakdown_pools_its_members_walks():
    """The question a fan-out raises is about the batch, so the members' walks
    are concatenated rather than reported one reader at a time."""
    agents = [_made(opening=100, walk=[_walked("raster", 4000)]),
              _made(opening=100, walk=[_walked("raster", 2000),
                                       _walked("refused", 138)])]
    table = {(r["scope"], r["class"]): r for r in cohort_classes(agents)}
    assert table[("c1", "raster")]["tokens"] == 6000
    assert table[("c1", "raster")]["calls"] == 2
    assert table[("c1", "refused")]["tokens"] == 138


def test_credits_follow_the_published_formula():
    """`ceil(input x rate_in + output x rate_out)`, Sonnet at 6/15 and 30/15.

    Spelled out from the numerators rather than from 0.4/2.0, so the assertion
    fails if the denominator moves and the table is left behind."""
    agents = [_made(billed_in=1000, out=100)]
    row = cost(agents)[0]
    assert row["credits"] == math.ceil(1000 * 6 / 15 + 100 * 30 / 15)
    assert row["credits"] == 600


def test_the_bill_excludes_cache_reads():
    """The one thing about subscription billing worth encoding: reads are free.
    Two agents identical but for a mountain of reads must cost the same."""
    plain = cost([_made(billed_in=1000, out=100, read=0)])[0]
    heavy = cost([_made(billed_in=1000, out=100, read=99_000_000)])[0]
    assert plain["credits"] == heavy["credits"]
    assert heavy["free_read"] == 99_000_000
    assert heavy["read_ratio"] > plain["read_ratio"]


def test_an_unpriced_model_is_not_costed_at_a_neighbours_rate():
    """The rates differ by more than 2x between tiers, so a guess is not a small
    error — and nothing downstream would ever re-open it."""
    row = cost([_made(model="quasar-9", billed_in=1000, out=100)])[0]
    assert row["credits"] is None
    assert row["per_agent"] is None
    assert "no published rate" in row["note"]


def test_a_successor_carrying_its_family_is_still_priced():
    """The other half of the same rule, and the reason matching is on the family
    substring: a model this table has not been updated for but which is plainly
    a Sonnet costs like one, rather than falling into the unpriced bucket and
    quietly dropping a whole batch out of the total."""
    row = cost([_made(model="sonnet-6-ultra-turbo", billed_in=1000, out=100)])[0]
    assert row["credits"] == 600
    assert row["note"] == ""


def test_a_partly_priced_scope_says_what_its_total_leaves_out():
    """A total over a scope it could only half cost is the fabricated measurement
    this module exists to catch — so the `ALL` row names the shortfall."""
    agents = [_made(opening=100, billed_in=1000, out=100),
              _made(opening=200, model="quasar-9", billed_in=5000, out=500)]
    total = cost(agents)[-1]
    assert total["cohort"] == "ALL"
    assert total["credits"] == 600           # the priced cohort alone
    assert total["per_agent"] == 600         # divided by 1 agent, not by 2
    assert "1 of 2 agents on an unpriced model" in total["note"]


def test_a_mixed_model_scope_still_totals():
    """Summed from the cohort rows rather than re-costed over the pooled agents:
    one rate cannot be applied to two models, and the earlier version answered
    that by reporting null for a scope every row of which was priced."""
    agents = [_made(opening=100, model="sonnet-5", billed_in=1000, out=100),
              _made(opening=200, model="haiku-4-5-20251001", billed_in=1000, out=100)]
    total = cost(agents)[-1]
    assert total["model"] == "mixed"
    assert total["credits"] == 600 + math.ceil(1000 * 2 / 15 + 100 * 10 / 15)
    assert total["note"] == ""


def test_plan_columns_are_absent_until_a_plan_is_named():
    """Money is arithmetic on a published table, not a measurement, so it does
    not appear beside the credits unless it was asked for."""
    bare = cost([_made(billed_in=1000, out=100)])[0]
    assert "usd" not in bare and "pct_week" not in bare
    priced = cost([_made(billed_in=1000, out=100)], "max20")[0]
    assert priced["pct_week"] == round(600 / 83_333_300 * 100, 2)
    # A week is a month at 12/52, not a quarter — the two differ by 8%.
    assert priced["usd"] == round(600 / 83_333_300 * 200 * 12 / 52, 2)


def test_two_batches_do_not_pool_into_one_breakdown():
    """The same refusal in two different fan-outs is two findings, and averaging
    them describes a batch nobody dispatched — the failure `cohorts` exists for."""
    agents = [_made(opening=100, walk=[_walked("refused", 100)]),
              _made(opening=200, walk=[_walked("refused", 900)])]
    scopes = {r["scope"] for r in cohort_classes(agents)}
    assert scopes == {"c1", "c2"}


def test_in_cohort_selects_a_whole_batch():
    """The timestamps differ on purpose: `c1` is defined as the *oldest* batch,
    so a fixture whose cohorts last spoke at the same moment asserts nothing
    about the numbering it claims to check."""
    a, b, c = (_made(opening=100, last="2026-08-04T13:00:00Z"),
               _made(opening=100, last="2026-08-04T13:00:00Z"),
               _made(opening=200, last="2026-08-04T12:00:00Z"))
    assert in_cohort([a, b, c], "c2") == [a, b]
    assert in_cohort([a, b, c], "c1") == [c]


def test_cohort_numbering_does_not_move_when_two_batches_tie():
    """Two cohorts sharing a last-spoke timestamp used to be ordered by a `set`,
    whose iteration order for string tuples moves with the hash seed — so the
    same transcripts could number the same batches either way round between runs,
    and a `--cohort c2` copied out of one report would select the other batch.

    Run repeatedly within one process this could not catch it; what it pins is
    that the order is a function of the keys, which is the property that makes it
    reproducible across processes.
    """
    tie = "2026-08-04T12:00:00Z"
    agents = [_made(opening=100, last=tie), _made(opening=200, last=tie)]
    ids = cohort_ids(agents)
    assert ids == cohort_ids(list(reversed(agents)))
    assert sorted(ids.values()) == ["c1", "c2"]


def test_an_unknown_cohort_raises_and_names_the_ones_in_scope():
    """An empty table cannot be told from a batch that ran nothing, and only one
    of those is the caller's to fix."""
    with pytest.raises(ValueError, match=r"c1"):
        in_cohort([_made(opening=100)], "c9")


def test_an_unmatched_agent_raises_rather_than_reporting_nothing(tmp_path):
    (tmp_path / "abcdef01.output").write_text(
        _tool_line(0, 10, "Bash", {"command": "x"}) + "\n")
    with pytest.raises(ValueError, match="no transcript for"):
        find_transcripts(tmp_path, ["deadbeef"], tasks=tmp_path)


def test_an_agent_is_matched_on_its_leading_characters(tmp_path):
    (tmp_path / "abcdef0123456.output").write_text(
        _tool_line(0, 10, "Bash", {"command": "x"}) + "\n")
    assert len(find_transcripts(tmp_path, ["abcdef01"], tasks=tmp_path)) == 1


# --- cohorts --------------------------------------------------------------

def test_identical_openings_form_one_cohort():
    rows = cohorts([_made(opened="COLD"), _made(), _made()])
    assert len(rows) == 1
    assert rows[0]["agents"] == 3 and rows[0]["warm"] == 2
    assert rows[0]["missed"] == 0        # (3 - 1 - 2) x opening


def test_differing_openings_do_not_pool():
    """The failure this verb exists for: per-page prompts put every reader in
    its own cohort, and averaging them would invent a prefix none of them had."""
    rows = cohorts([_made(opening=34744, opened="COLD"),
                    _made(opening=34693, opened="COLD"),
                    _made(opening=35032, opened="COLD")])
    assert len(rows) == 3
    assert all(r["agents"] == 1 for r in rows)
    assert all("singleton" in r["note"] for r in rows)


def test_a_different_model_is_a_different_cohort():
    rows = cohorts([_made(), _made(model="opus-5")])
    assert len(rows) == 2


def test_a_different_agent_type_is_a_different_cohort():
    """Two types have different standing instructions and so were never
    candidates to share a prefix; pooling them reports a saving nobody made."""
    rows = cohorts([_made(), _made(atype="groundtruth-reader")])
    assert len(rows) == 2


def test_preamble_does_not_pool_across_agent_types():
    rows = preamble([_made(pre=[_turn(7, "aa")]),
                     _made(atype="groundtruth-reader", pre=[_turn(2300, "bb")])])
    assert len(rows) == 2
    assert all(r["variants"] == 1 for r in rows)


def test_missed_counts_only_prefixes_a_sibling_had_already_written():
    """Four agents, all cold: one had to write it, three did so needlessly."""
    rows = cohorts([_made(opened="COLD") for _ in range(4)])
    assert rows[0]["missed"] == 3 * 35798


def test_singleton_claims_no_saving():
    rows = cohorts([_made(opened="COLD")])
    assert rows[0]["missed"] == 0 and rows[0]["note"].startswith("singleton")


def test_no_agents_reports_rather_than_raising():
    assert cohorts([])[0]["agents"] == 0


def test_savings_are_the_prefix_the_warm_siblings_did_not_write():
    rows = cohorts([_made(opened="COLD", ctx=70000), _made(ctx=70000),
                    _made(ctx=70000)])
    own = 3 * (70000 - 35798)
    assert rows[0]["saved"] == 2 * 35798
    assert rows[0]["originated"] == 35798 + own
    assert rows[0]["if_all_cold"] == 3 * 35798 + own


def test_the_asymptote_is_the_prefix_share_of_one_agents_cost():
    """(N-1)P / (N(P+W)) tends to P/(P+W), so a batch whose prefix equals its
    per-item work approaches halving and one with a thin prefix never does."""
    rows = cohorts([_made(opening=100, ctx=200)] * 4)      # P == W
    assert rows[0]["asymptote"] == "50.0%"
    rows = cohorts([_made(opening=100, ctx=1100)] * 4)     # W is 10x P
    assert rows[0]["asymptote"] == "9.1%"                  # 100/1100, not 1/10


def test_a_singleton_claims_no_asymptote():
    row = cohorts([_made(opened="COLD", ctx=70000)])[0]
    assert row["asymptote"] == "n/a" and row["saved_pct"] == "n/a"


def test_saved_pct_is_measured_and_the_asymptote_is_never_reached():
    """The gap between them is the cost of the batch being small: one member
    always writes the prefix, so with three that is a third of them.

    And it is an asymptote, not a ceiling — (N-1)/N is never 1, so no batch of
    any size attains it. A perfectly-run batch still reports a shortfall, which
    is arithmetic rather than a defect to chase.
    """
    row = cohorts([_made(opening=100, ctx=200, opened="COLD"),
                   _made(opening=100, ctx=200), _made(opening=100, ctx=200)])[0]
    assert row["saved_pct"] == "33.3%"     # 200 saved of 600 all-cold
    assert row["asymptote"] == "50.0%"     # P/(P+W), approached, never reached
    # Every sibling warm, and it still falls short of the asymptote.
    big = cohorts([_made(opening=100, ctx=200, opened="COLD")]
                  + [_made(opening=100, ctx=200)] * 99)[0]
    assert big["saved_pct"] == "49.5%" and big["asymptote"] == "50.0%"


# --- warmth ---------------------------------------------------------------

def _ago(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


def test_warm_inside_the_ttl():
    assert warmth([_made(last=_ago(30))])[0]["state"] == "warm"


def test_expired_outside_the_ttl():
    assert warmth([_made(last=_ago(TTL + 30))])[0]["state"] == "EXPIRED"


def test_warmth_measures_the_most_recent_agent():
    rows = warmth([_made(last=_ago(TTL + 600)), _made(last=_ago(10))])
    assert rows[0]["state"] == "warm"


def test_warmth_of_an_unparseable_stamp_says_nothing():
    """No row rather than a guessed one — the same rule as a singleton cohort."""
    assert warmth([_made(last="not a timestamp")]) == []


def test_warmth_reads_the_tier_off_the_record():
    """`TTL` is a fallback, not the answer: an hour-tier write is warm at a
    point where the five-minute assumption would have called it expired."""
    rows = warmth([_made(last=_ago(TTLS["5m"] + 60), ttl="1h")])
    assert rows[0]["ttl_s"] == TTLS["1h"] and rows[0]["state"] == "warm"


def test_mixed_tiers_take_the_shortest():
    """A prefix is warm only while every witness to it still is; the optimistic
    reading would dispatch a batch at a cold cache."""
    rows = warmth([_made(last=_ago(30), ttl="1h"), _made(last=_ago(30), ttl="5m")])
    assert rows[0]["ttl_s"] == TTLS["5m"]


def test_unrecorded_tier_falls_back_and_says_so():
    rows = warmth([_made(last=_ago(30), ttl="")])
    assert rows[0]["ttl_s"] == TTL and "assuming" in rows[0]["tier"]


# --- preamble -------------------------------------------------------------

def _turn(chars: int, h: str, label: str = "x", after: int = 0):
    """`after` is how many requests had been sent when the message arrived; 0
    means it is in the opening block, where nothing separates it."""
    return {"chars": chars, "hash": h, "label": label, "after": after}


def test_preamble_names_the_turn_that_breaks_the_prefix():
    """Turn 1 varying is fatal however identical turn 2 is — a prefix ends at
    the first differing byte, so this is the whole diagnostic."""
    rows = preamble([_made(pre=[_turn(2324, "aa"), _turn(41195, "zz")]),
                     _made(pre=[_turn(2401, "bb"), _turn(41195, "zz")])])
    assert rows[0]["variants"] == 2 and rows[0]["shared"] == "NO"
    assert rows[1]["variants"] == 1 and rows[1]["shared"] == "yes"


def test_preamble_shared_when_every_turn_agrees():
    rows = preamble([_made(pre=[_turn(1050, "aa"), _turn(41195, "zz")])] * 2)
    assert [r["shared"] for r in rows] == ["yes", "yes"]


def test_preamble_of_one_agent_claims_nothing():
    assert preamble([_made(pre=[_turn(1050, "aa")])])[0]["shared"] == "n/a"


def test_a_message_sharing_its_request_has_no_separable_size():
    """The opening block always does — the system prompt is in it — so its
    turns report `-` rather than a number nothing in the record supports."""
    rows = preamble([_made(pre=[_turn(7, "aa"), _turn(41195, "zz")],
                           ctxs=[35952, 51000])])
    assert [r["tokens"] for r in rows] == ["-", "-"]


def test_a_message_that_arrives_alone_is_measured():
    """One message between two requests: the growth is its own."""
    rows = preamble([_made(pre=[_turn(7, "aa"), _turn(600, "bb", after=1)],
                           ctxs=[35952, 36600])])
    assert rows[0]["tokens"] == "-"
    assert rows[1]["tokens"] == "+648"


def test_a_measured_message_reports_its_spread_across_agents():
    rows = preamble([_made(pre=[_turn(7, "a"), _turn(600, "b", after=1)],
                           ctxs=[35952, 36600]),
                     _made(pre=[_turn(7, "a"), _turn(620, "c", after=1)],
                           ctxs=[35952, 36700])])
    assert rows[1]["tokens"] == "+648..+748"


def test_preamble_tolerates_uneven_depth():
    """An agent resumed by SendMessage has more turns than one that was not;
    a turn nobody else has must still report, over the agents that have it."""
    rows = preamble([_made(pre=[_turn(1, "a")]), _made(pre=[_turn(1, "a"), _turn(2, "b")])])
    assert len(rows) == 2 and rows[1]["agents"] == 1


def test_no_agents_has_no_preamble():
    assert preamble([]) == []


def test_no_agents_has_no_warmth():
    assert warmth([]) == []


# --- --since --------------------------------------------------------------

def test_relative_since_resolves_to_a_stamp_in_the_past():
    cut = since_stamp("5m")
    assert cut < datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    assert since_stamp("1d") < cut


def test_every_unit_is_accepted():
    assert len({since_stamp(f"1{u}") for u in "smhd"}) == 4


def test_iso_forms_pass_through():
    assert since_stamp("2026-08-04").startswith("2026-08-04")
    assert since_stamp("2026-08-04T21:45Z").startswith("2026-08-04T21:45")


def test_an_unparseable_since_raises_rather_than_matching_nothing():
    """`5m` sorts AFTER every ISO stamp, so the old code answered it with an
    empty table at exit 0 — a wrong answer shaped like a right one."""
    with pytest.raises(ValueError, match="neither a duration nor a date"):
        since_stamp("yesterday")


def test_a_bare_number_is_not_a_duration():
    with pytest.raises(ValueError):
        since_stamp("5")


def test_the_cut_carries_no_trailing_z():
    """Transcript stamps have fractional seconds, and `…:00Z` sorts after
    `…:00.5Z` because `Z` > `.`, which would drop a record inside the window."""
    cut = since_stamp("0s")
    assert not cut.endswith("Z")
    assert cut < cut + ".500Z"


# --- session discovery ----------------------------------------------------

def test_project_climbs_to_the_repository(tmp_path):
    """Transcripts are filed by project, so a run from a subdirectory must find
    the same session a run from the top does."""
    (tmp_path / ".git").mkdir()
    deep = tmp_path / "scratch" / "chukchi"
    deep.mkdir(parents=True)
    assert project(deep) == tmp_path.resolve()


def test_project_outside_a_repository_is_the_root_itself(tmp_path):
    assert project(tmp_path) == tmp_path.resolve()


def test_slug_folds_both_separators(tmp_path):
    """Claude Code slugs `/` and `_` alike, so a directory named with an
    underscore becomes hyphenated and a slug built from `/` alone would
    find nothing."""
    d = tmp_path / "Projects" / "some_project"
    d.mkdir(parents=True)
    assert _slug(d).endswith("-Projects-some-project")
    assert "_" not in _slug(d)


# --- concurrent sessions --------------------------------------------------

def _session(root, name: str, agent: str, age_s: float = 0):
    """A task-transcript directory shaped like the real one, aged by mtime."""
    d = root / "claude-1000" / "-proj" / name / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    _transcript(d, agent, [(0, 100)])
    when = datetime.now(UTC).timestamp() - age_s
    os.utime(d / f"{agent}.output", (when, when))
    return d


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    """Discovery pointed at `tmp_path` instead of `/tmp/claude-*`.

    `elsewhere` finds the project's transcript directories itself — that is the
    point of it, since the whole question is what the default scope left out —
    so the seam to fake is the discovery, not the filesystem.
    """
    monkeypatch.setattr(usage, "find_tasks", lambda root, tasks=None: sorted(
        (tmp_path / "claude-1000" / "-proj").glob("*/tasks")))
    return tmp_path


def test_a_second_live_session_is_named_rather_than_silently_excluded(sessions):
    """The default scope is "the newest session", and two batches out at once
    make that a coin flip that can land differently between two runs.

    Both passes here fan out over pages — the Bogoras readers and the Moll ones
    — from different sessions, so this is the ordinary case rather than an edge
    one. Every column of a report that quietly picked the other batch would be
    right, about a batch nobody asked after.
    """
    mine = _session(sessions, "aaaaaaaa-1111", "a1", age_s=0)
    _session(sessions, "bbbbbbbb-2222", "b1", age_s=3)
    others = usage.elsewhere(sessions, [mine], None, 300)
    # The id, and by its leading characters — which is what `--session` matches.
    assert [o["session"] for o in others] == ["bbbbbbbb"]
    assert others[0]["quiet_for_s"] <= 5


def test_a_session_quiet_longer_than_the_ttl_is_history_not_competition(sessions):
    """The window is the subagent cache TTL, because that is the horizon on which
    "is another batch running" has consequences."""
    mine = _session(sessions, "aaaaaaaa-1111", "a1", age_s=0)
    _session(sessions, "cccccccc-3333", "c1", age_s=9000)
    assert usage.elsewhere(sessions, [mine], None, TTLS["5m"]) == []


def test_the_scoped_session_does_not_report_itself(sessions):
    mine = _session(sessions, "aaaaaaaa-1111", "a1", age_s=0)
    assert usage.elsewhere(sessions, [mine], None, 300) == []


def test_an_explicit_tasks_dir_claims_no_other_session(sessions):
    """`--tasks` names a directory outright, so there was no default scope to
    have chosen badly and nothing to warn about."""
    mine = _session(sessions, "aaaaaaaa-1111", "a1", age_s=0)
    _session(sessions, "bbbbbbbb-2222", "b1", age_s=1)
    assert usage.elsewhere(sessions, [mine], mine, 300) == []
