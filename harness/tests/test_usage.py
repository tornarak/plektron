"""`harness agents usage` — the cohort arithmetic and the transcript reader.

The verb's whole value is that it refuses to report a shared prefix nobody had,
so that refusal is what these test hardest: a session holding several fan-outs
must not average into one, and a lone agent must not have its opening promoted
to a shared number.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from harness.usage import (
    TTL,
    TTLS,
    _agent,
    _requests,
    _slug,
    cohorts,
    preamble,
    project,
    since_stamp,
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
          ttl="5m", session="s1", pre=None, ctx=None, atype="moll-reader"):
    return {"model": model, "opening": opening, "opened": opened, "last": last,
            "type": atype,
            "ttl": ttl, "session": session, "pre": pre or [],
            "ctx": opening if ctx is None else ctx}


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


def test_the_ceiling_is_the_prefix_share_of_one_agents_cost():
    """(N-1)P / (N(P+W)) tends to P/(P+W), so a batch whose prefix equals its
    per-item work approaches halving and one with a thin prefix never does."""
    rows = cohorts([_made(opening=100, ctx=200)] * 4)      # P == W
    assert rows[0]["ceiling"] == "50.0%"
    rows = cohorts([_made(opening=100, ctx=1100)] * 4)     # W is 10x P
    assert rows[0]["ceiling"] == "9.1%"                    # 100/1100, not 1/10


def test_a_singleton_claims_no_ceiling():
    assert cohorts([_made(opened="COLD", ctx=70000)])[0]["ceiling"] == "n/a"


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

def _turn(chars: int, h: str, label: str = "x"):
    return {"chars": chars, "hash": h, "label": label}


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


def test_preamble_reports_the_size_spread():
    rows = preamble([_made(pre=[_turn(2324, "aa")]), _made(pre=[_turn(2401, "bb")])])
    assert rows[0]["chars"] == "2324..2401"


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
    """Claude Code slugs `/` and `_` alike, so machine_press becomes
    machine-press and a slug built from `/` alone would find nothing."""
    d = tmp_path / "Projects" / "machine_press"
    d.mkdir(parents=True)
    assert _slug(d).endswith("-Projects-machine-press")
    assert "_" not in _slug(d)
