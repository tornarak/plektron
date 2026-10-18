"""Cache telemetry over a dispatch batch — what the fan-out actually paid.

A batch of readers is worth dispatching only if the siblings share a prefix, and
whether they do is not visible from anything the agents say. It is visible in
their transcripts, which record `cache_read_input_tokens` and
`cache_creation_input_tokens` per request. This module reads those.

**The diagnostic is the opening total, not the saving.** Every agent's first
request costs `read + write` whatever the cache did, so two agents dispatched
with identical prompts *must* open at the same number. When the openings differ,
the prompts differed — some byte varies ahead of the shared block, and no launch
order will fix it. That check is the reason this exists: a batch can look
healthy (every agent finished, every page read) while quietly paying full price
per agent, and nothing else in the pipeline would say so.

The second number worth having is where the divergence sits. Content *behind*
the shared prefix is free to vary — an agent's own reply, its page block, its
rasters — because a prefix ends at the first differing byte and everything after
it was going to be written anyway. Content *ahead* of it costs the whole block,
per agent, every time. So a large tail write is ordinary and a disagreeing
opening is a defect, and the report separates them rather than summing to one
"tokens used" figure that hides which is which.

Nothing here gates. It is measurement, and measurement never gates.
"""
from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha1
from pathlib import Path

# **Read, not assumed.** A request records which TTL its write bought, under
# `usage.cache_creation`, so the expiry clock is a measurement rather than a
# constant taken from the docs. The two named tiers:
TTLS = {"5m": 300, "1h": 3600}
TTL = TTLS["5m"]  # the fallback when a scope wrote nothing and so named no tier

# **Every figure in this file is tokens, measured, except the preamble's
# per-turn size, which is characters and cannot be anything else.** The whole
# token vocabulary of a transcript is four per-request fields — `input_tokens`,
# `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` —
# and nothing counts a message. Every preamble turn arrives before the first
# request, so there is no earlier measurement to diff one against.
#
# It is obtainable, just not from data anyone has collected: two agents of one
# type whose preambles differ in exactly one known way, dispatched with no
# memory write between them, give that difference in tokens as the difference in
# their openings. The control is the whole difficulty. Between two real batches
# here the prompt shrank 1,043 characters while the opening ROSE 154 tokens,
# because a reader had written a memory file and the memory index sits in the
# system prompt — fewer tokens for more characters, so the two equations return
# a negative characters-per-token and the confound is larger than the signal.
# A divisor picked to paper over that would be a number with no witness.

#: Credits per token, as published at https://she-llac.com/claude-limits:
#: `credits = ceil(input x input_rate + output x output_rate)`, and on a
#: subscription **cache reads charge nothing while cache writes charge the
#: ordinary input rate**. That asymmetry is the whole reason this file's
#: `read`/`write` split is worth having: a batch's `read` column is free and its
#: `write` column is not, so a token total that adds them answers no question
#: anybody is asking.
#:
#: The published rates are all fifteenths, so the denominator is named once and
#: the table holds the numerators — a rate change is then a row to edit rather
#: than six decimals to re-derive, and no figure here is a rounded copy of one.
CREDIT_DENOM = 15
FAMILY_RATES: dict[str, tuple[int, int]] = {
    "haiku": (2, 10),
    "sonnet": (6, 30),
    "opus": (10, 50),
}

#: What a plan buys, same source. `usd` is the list price **per month**; a run's
#: money figure comes from its share of the *weekly* allowance, so the monthly
#: price is converted at 12/52 rather than 1/4 — the two differ by 8%, which is
#: larger than most of what this table is used to compare.
PLANS: dict[str, tuple[int, int, int]] = {
    #        5-hour,     weekly,     usd/month
    "pro":   (550_000, 5_000_000, 20),
    "max5":  (3_300_000, 41_666_700, 100),
    "max20": (11_000_000, 83_333_300, 200),
}


def rates(model: str) -> tuple[float, float] | None:
    """`(input, output)` credits per token for `model`, or None if unrecognised.

    **None rather than a default**, and the caller must carry the None through to
    the report. Every rate here differs from its neighbours by more than a factor
    of two, so guessing one is not a small error — and a batch run on a model this
    table has never heard of is exactly the case where a plausible number is worst,
    because nothing downstream would ever re-open it. The model string is whatever
    the transcript recorded with `claude-` stripped, so matching is on the family
    substring: `sonnet-5`, `haiku-4-5-20251001` and any successor name carrying its
    family still resolve, and a genuinely new family reports itself as unpriced.
    """
    for family, (rin, rout) in FAMILY_RATES.items():
        if family in model:
            return rin / CREDIT_DENOM, rout / CREDIT_DENOM
    return None


def project(root: Path) -> Path:
    """The repository `root` sits in, or `root` itself outside one.

    Transcripts are keyed on the *project* directory, not on the cwd, so a run
    from `harness/` or `scratch/chukchi/` must find the same session a run from
    the top does. Every other group resolves stores under `--root` and would be
    wrong to climb; this one is reading something filed by project, and matching
    the cwd instead would report "no transcripts" from a subdirectory of a
    project that has plenty.
    """
    root = root.resolve()
    for d in (root, *root.parents):
        if (d / ".git").exists():
            return d
    return root


def _slug(root: Path) -> str:
    """The session-directory name Claude Code derives from a project path.

    Derived rather than configured: it is a pure function of the root, and a
    hand-set default would be one more thing to get out of step with the cwd.
    """
    return re.sub(r"[/_]", "-", str(project(root)))


def find_tasks(root: Path, tasks: Path | None = None) -> list[Path]:
    """Every task-transcript directory for `root`'s project, newest last.

    Newest *by transcript*, not by directory mtime: a session that was opened
    and never dispatched anything has a `tasks/` dir too, and ranking it would
    let an empty session outrank the batch you meant.
    """
    if tasks is not None:
        if not tasks.is_dir():
            raise FileNotFoundError(f"no such directory: {tasks}")
        return [tasks]
    cands = [(max((f.stat().st_mtime for f in d.glob("*.output")), default=0), d)
             for d in Path("/tmp").glob(f"claude-*/{_slug(root)}/*/tasks")]
    live = sorted((m, d) for m, d in cands if m)
    if not live:
        raise FileNotFoundError(
            f"no task transcripts for {project(root)} — looked in "
            f"/tmp/claude-*/{_slug(root)}/*/tasks. Name one with --tasks.")
    return [d for _, d in live]


# **The classes a request's growth can belong to**, in the order the breakdown
# prints them when tokens tie. They are named for *what arrived*, not for which
# tool asked, because the question a coordinator has is "what is this context
# made of" and two tools can deliver the same kind of thing.
#
# `refused` and `failed` are separated from `command` deliberately, and they are
# not the same finding. A refused call never ran — the guard hook stopped it, and
# every token it cost bought nothing. A failed one ran and exited non-zero, which
# includes a gate doing exactly its job (`proposal check` reporting an advisory is
# a `failed` row and is not waste). Only `refused` is unambiguously spend with no
# return, which is why it gets its own row rather than being folded into either
# neighbour.
CLASSES = ("opening", "raster", "text", "command", "write", "refused", "failed",
           "message", "none")


def _outcome(result) -> str:
    """Whether the tool result that came back was refused, failed, or ordinary.

    A refusal arrives as a bare string — `Error: PreToolUse:Bash hook error: ...`
    — and a non-zero exit as `Error: Exit code N`, while anything that worked is a
    dict carrying `stdout`. So the shape of the field decides it before its text
    does, and the two error kinds are told apart by their prefix rather than by
    matching the guard's prose, which is edited far more often than this file.
    """
    if not isinstance(result, str) or not result.startswith("Error:"):
        return ""
    return "refused" if "PreToolUse" in result[:40] else "failed"


def _text(rec: dict) -> str:
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text")
    return str(content or "")


def _label(rec: dict) -> str:
    """A one-line description of the task, off its opening prompt.

    There is no field carrying the dispatcher's own `description`, so the first
    non-empty line of the prompt is the best available. It is what distinguishes
    two rows at a glance, and under the handshake it is *deliberately* identical
    across a cohort — two agents showing the same label is the shared prefix
    made legible rather than a collision.
    """
    text = _text(rec)
    # A preloaded skill arrives as a user turn opening with its own name, so the
    # turn that carries the bulk can say *which* skill it is rather than quoting
    # its first heading. This is the one label worth special-casing: it answers
    # "what is the 21k?" without anyone opening the transcript.
    if m := re.search(r"<command-name>([^<]+)</command-name>", text):
        return f"skill: {m.group(1)}"
    for line in text.splitlines():
        if line.strip():
            return re.sub(r"[`*]", "", line.strip())[:48]
    return ""


def _read(path: Path) -> tuple[list[dict], dict]:
    """One transcript's assistant requests, in order, plus its provenance.

    Read line by line and filtered before parsing: a transcript carries whole
    rasters as base64 and a batch of them will not fit anywhere useful at once.
    """
    # **Keyed by `requestId`, last event wins.** A request emits several usage
    # records as it streams, and the early ones carry a partial `output_tokens`.
    # Counting lines instead of requests inflated `reqs` two- to fourfold and
    # every sum with it — an agent that made 10 requests reported 22.
    by_id: dict[str, dict] = {}
    order: list[str] = []
    meta: dict = {"pre": []}
    with path.open() as fh:
        for line in fh:
            # **Three fields are worth parsing a line for**, and the filter names
            # each rather than standing on one that happens to co-occur: the
            # usage block, a user turn, and a tool result — whose fate decides
            # the class of the next request's growth. `toolUseResult` used to be
            # reached only via the `"role":"user"` test, which is a *formatting*
            # dependency (the runtime writes compact JSON, so the key and value
            # are adjacent) rather than a claim about content.
            if ('"cache_read_input_tokens"' not in line
                    and '"role":"user"' not in line
                    and '"toolUseResult"' not in line):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "session" not in meta:
                meta |= {"session": rec.get("slug") or rec.get("sessionId", "")[:8],
                         "branch": rec.get("gitBranch", "")}
            # `attributionAgent` names the agent type outright, which is what a
            # reader of this table actually wants to group by; it appears on
            # assistant records, so it is picked up wherever it first shows.
            for k, field in (("type", "attributionAgent"), ("effort", "effort")):
                if not meta.get(k) and rec.get(field):
                    meta[k] = rec[field]
            # **A tool result names the fate of the call that asked for it**, and
            # it is filed against the request that made the call rather than the
            # one that reads it: the next request's growth is this result, so the
            # class of that growth is decided here. `order[-1]` is that caller —
            # a request emits several usage records while it streams, but they
            # share one id and the tool result cannot arrive before the last of
            # them.
            if rec.get("type") == "user" and "toolUseResult" in rec:
                if order:
                    by_id[order[-1]]["outcome"] = _outcome(rec["toolUseResult"])
                continue
            # The preamble: every user turn ahead of the first assistant reply.
            # That is the whole of what a launch order can affect, and the only
            # part of the context this file can see — the system prompt is not
            # in the transcript, so it is inferred as `opening - preamble` and
            # never reported as though it had been read.
            # Messages sent *to* the agent, not results coming back to it: a
            # tool result is a user-role record too, and a page of them would
            # bury the handful of turns anyone dispatched.
            if (rec.get("type") == "user" and "toolUseResult" not in rec
                    and (text := _text(rec).strip())
                    and not text.startswith("[Image:")):
                # `after` is how many requests had already been sent when this
                # message arrived. Messages sharing a value share a request, and
                # a request is the only thing token-counted — so that value is
                # what decides whether this message's size is separable at all.
                meta["pre"].append({"chars": len(text), "label": _label(rec),
                                    "after": len(order),
                                    "hash": sha1(text.encode()).hexdigest()[:8]})
                if "task" not in meta:
                    meta["task"] = meta["pre"][0]["label"]
            u = (rec.get("message") or {}).get("usage")
            if not u:
                continue
            # The tool this request ASKED for. Its result arrives before the
            # next request, so it is what the next request's growth is made of
            # — which is the only way a bare token delta can be told from a
            # raster, a file read, or a message somebody sent.
            tool, detail = "", ""
            for blk in ((rec.get("message") or {}).get("content") or []):
                if isinstance(blk, dict) and blk.get("type") == "tool_use":
                    tool = blk.get("name", "")
                    inp = blk.get("input") or {}
                    detail = (Path(inp["file_path"]).name if inp.get("file_path")
                              else str(inp.get("command", ""))[:60])
            tiers = u.get("cache_creation") or {}
            rid = rec.get("requestId") or f"_{len(order)}"
            if rid not in by_id:
                order.append(rid)
            by_id[rid] = {
                "in": u.get("input_tokens", 0),
                "read": u.get("cache_read_input_tokens", 0),
                "write": u.get("cache_creation_input_tokens", 0),
                "tier": ("1h" if tiers.get("ephemeral_1h_input_tokens")
                         else "5m" if tiers.get("ephemeral_5m_input_tokens") else ""),
                "out": u.get("output_tokens", 0),
                "model": rec.get("model") or (rec.get("message") or {}).get("model", ""),
                "at": rec.get("timestamp", ""),
                "tool": tool,
                "detail": detail,
                # Carried across the several usage records one request emits, so
                # a late-streaming record cannot blank a fate already filed.
                "outcome": by_id.get(rid, {}).get("outcome", ""),
            }
    return [by_id[r] for r in order], meta


RASTER = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _arrival(prev: dict | None) -> tuple[str, str]:
    """What arrived between the previous request and this one, and from where.

    Named off the tool the previous request called, because that is what the
    growth *is*. A number alone cannot tell a page raster from a file read, and
    those are the two things worth telling apart here: one is irreducible and
    one is a choice.
    """
    if prev is None:
        return "system prompt + preamble", ""
    tool, detail = prev.get("tool", ""), prev.get("detail", "")
    if not tool:
        return "reply, no tool called", ""
    if tool == "Read":
        kind = "read raster" if detail.lower().endswith(RASTER) else "read text"
        return kind, detail
    if tool in ("Write", "Edit"):
        return f"{tool.lower()} file", detail
    if tool == "Bash":
        return "ran command", detail
    return tool.lower(), detail


def _klass(prev: dict | None) -> str:
    """Which class the growth after `prev` belongs to.

    Keyed on the *previous* request for the same reason `_arrival` is: the growth
    is that request's result. A fate — refused or failed — outranks the tool,
    because a call that never ran delivered nothing whatever it was going to be.
    """
    if prev is None:
        return "opening"
    if fate := prev.get("outcome"):
        return fate
    tool, detail = prev.get("tool", ""), prev.get("detail", "")
    if not tool:
        return "none"
    if tool == "Read":
        return "raster" if detail.lower().endswith(RASTER) else "text"
    if tool in ("Write", "Edit"):
        return "write"
    if tool == "Bash":
        return "command"
    return "message"


def _walk(reqs: list[dict], agent: str = "", atype: str = "") -> list[dict]:
    """One agent's requests with their growth decomposed into reply and result.

    **`added` is two things and the split is measured, not apportioned.** What
    arrives between two requests is the agent's own reply — which stays in context
    — plus whatever its tool returned. The reply's size is recorded (`output_tokens`
    on the earlier request), so subtracting it leaves the result exactly, and the
    subtraction is checkable rather than assumed: on this pass two readers were
    refused an identical `ls` after replies of 4,843 and 4,634 tokens, and both
    came out at **138** for the refusal. Two different agents, two different
    replies, the same block message, the same number to the token.

    That is the whole reason for the column. `added` alone made a reader that
    thought hard before a cheap call look like an expensive call: the blocked `ls`
    above shows as +4,981 in the raw delta and 138 of it is the tool's.

    `result` is left signed. A negative would mean the decomposition does not hold
    for that request, and clamping it to zero would hide exactly the case worth
    seeing.
    """
    out, prev_ctx, prev = [], 0, None
    for i, r in enumerate(reqs, 1):
        ctx = r["in"] + r["read"] + r["write"]
        note, detail = _arrival(prev)
        added = ctx if i == 1 else ctx - prev_ctx
        reply = prev["out"] if prev else 0
        out.append({
            "agent": agent,
            "type": atype,
            "req": i,
            # Whether that growth was PAID FOR or free. A request that wrote
            # nothing had its whole context served from cache; one that wrote
            # is the only kind that costs, and the amount is the `write`.
            "via": "read" if not r["write"] else "write",
            "read": r["read"],
            "write": r["write"],
            "ctx": ctx,
            "added": added,
            "reply": reply,
            "result": added - reply,
            "class": _klass(prev),
            "out": r["out"],
            "note": note,
            "detail": detail,
        })
        prev_ctx, prev = ctx, r
    return out


def _requests(path: Path) -> list[dict]:
    return _read(path)[0]


def _transcripts(d: Path) -> list[Path]:
    """The agent transcripts in one directory, under either name they go by.

    An Agent-tool dispatch leaves `tasks/<id>.output`, a symlink to
    `subagents/agent-<id>.jsonl`; a Workflow run leaves only the latter, under
    `subagents/workflows/<run>/`, with no link in `tasks/`. Same bytes, so the
    one parser reads both — a glob for one name made a workflow batch read as
    "no agents in scope", which is the empty table a measurement must not show.
    """
    return sorted([*d.glob("*.output"), *d.glob("agent-*.jsonl")])


def _ident(path: Path) -> str:
    return path.stem.removeprefix("agent-")


def _agent(path: Path) -> dict | None:
    reqs, meta = _read(path)
    if not reqs:
        return None
    first = reqs[0]
    return {
        "session": meta.get("session", ""),
        "agent": _ident(path)[:8],
        "type": meta.get("type", ""),
        "task": meta.get("task", "")[:32],
        "pre": meta["pre"],
        "model": first["model"].removeprefix("claude-"),
        "effort": meta.get("effort", ""),
        # The tier this agent's writes actually bought, off the record. Empty
        # when it wrote nothing at all, which is the warm case and names no tier.
        "ttl": next((r["tier"] for r in reqs if r["tier"]), ""),
        "reqs": len(reqs),
        # read+write on the first request: what the context cost to establish,
        # independent of what the cache did with it.
        "opening": first["read"] + first["write"],
        "opened": "warm" if first["read"] and not first["write"] else "COLD",
        "tail": sum(r["write"] for r in reqs[1:]),
        # What the agent carried at the end: its last request's whole input.
        # This is the figure the *harness* reports per agent (within ~0.6%, see
        # VERBS.md) and it is a terminal measure, not a sum — an agent's context
        # is re-sent every request, so summing requests counts it many times.
        "ctx": reqs[-1]["in"] + reqs[-1]["read"] + reqs[-1]["write"],
        # Every request's whole context, so `turns` can difference them.
        "ctxs": [r["in"] + r["read"] + r["write"] for r in reqs],
        # Tokens this agent read that it would have written had it gone first.
        # Zero for the cold one, which had to write them for the others.
        "saved": first["read"] if first["read"] and not first["write"] else 0,
        "out": sum(r["out"] for r in reqs),
        # **What the agent was actually charged input for.** `in` is the part of
        # a request that was neither cached nor served from cache — small, a
        # couple of tokens on most requests here — and `write` is the cache
        # creation, billed at the same input rate. They are summed because the
        # rate does not distinguish them; `read` is excluded because on a
        # subscription it is free, which is the one thing about this billing
        # worth encoding.
        "billed_in": sum(r["in"] + r["write"] for r in reqs),
        "read": sum(r["read"] for r in reqs),
        # The decomposed requests, kept so a cohort's breakdown is the
        # concatenation of its members' rather than a second walk over the same
        # files with a second chance to disagree with the first.
        "walk": _walk(reqs, _ident(path)[:8], meta.get("type", "")),
        "first": min(r["at"] for r in reqs),
        "last": max(r["at"] for r in reqs),
    }


RELATIVE = re.compile(r"^(\d+)([smhd])$")
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def since_stamp(spec: str, *, tz: timezone | None = UTC) -> str:
    """`--since` as a comparable stamp: `5m`/`2h`/`1d`, or an ISO date or time.

    **A relative form is the spelling this verb actually wants** — the question
    it answers is almost always "the batch I just ran", and an absolute stamp
    means doing date arithmetic by hand to ask it.

    An unparseable value raises rather than filtering. It has to: comparison is
    lexicographic, so `5m` sorts *after* every ISO stamp there will ever be, and
    the old code answered it with an empty table and exit 0 — a wrong answer
    wearing the shape of a right one. That is the failure this repo is
    organised against, and a `--since` nobody can parse must fail loudly.

    Returned without a trailing `Z` deliberately: transcript stamps carry
    fractional seconds, and `...:00Z` sorts *after* `...:00.5Z` because `Z` > `.`,
    which would drop a record inside the window. Truncated, the shorter string
    compares less and the boundary falls the right way.

    **`tz` names the clock the store being filtered writes in**, because the
    comparison downstream is on strings and the two stores disagree: a task
    transcript stamps UTC with a `Z`, and `decision.json` stamps local time with
    an offset (`2026-07-31T16:19:04-0400`). A duration resolved in the wrong one
    is silently off by the offset — four hours here — which would quietly move
    the window rather than fail. `tz=None` gives local wall-clock time. Absolute
    dates are passed through untouched either way, so no existing `--since DATE`
    changes meaning.
    """
    spec = spec.strip()
    if m := RELATIVE.match(spec):
        ago = timedelta(seconds=int(m.group(1)) * UNITS[m.group(2)])
        return (datetime.now(tz) - ago).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        return datetime.fromisoformat(spec.removesuffix("Z")).isoformat()
    except ValueError:
        raise ValueError(
            f"--since {spec!r} is neither a duration nor a date. Use a relative"
            " form (30s, 5m, 2h, 1d) or an ISO date or stamp"
            " (2026-08-04, 2026-08-04T21:45)") from None


def _age(stamp: str) -> float | None:
    try:
        return (datetime.now(UTC) - datetime.fromisoformat(stamp)).total_seconds()
    except ValueError:
        return None


def batch(root: Path, tasks: Path | None = None, *, session: str | None = None,
          since: str | None = None, all_: bool = False) -> tuple[list[Path], list[dict]]:
    """The agents to report on, newest last, with the directories they came from.

    Scope is the newest session by default, every session under `--all`, and one
    named session under `--session` — which matches the slug or the id, by
    prefix, because the slug is what a human reads off a plan file and the id is
    what a transcript carries.

    `--since` sorts ISO stamps lexicographically, as `ocr corrections` does. An
    agent whose stamps will not parse is **kept and flagged**, never dropped: a
    missing timestamp must not draw in the same column as one outside the window.
    """
    found = find_tasks(root, tasks)
    dirs = found
    if not all_ and tasks is None and session is None:
        dirs = dirs[-1:]
    # Ordered by when each agent OPENED, not when it finished: launch order is
    # what decides which one wrote the shared prefix, and `last` sorted a reader
    # that opened first and ran long below one dispatched minutes later.
    agents = sorted((a for d in dirs for f in _transcripts(d)
                     if (a := _agent(f))), key=lambda a: a["first"])
    if session:
        agents = [a for a in agents if a["session"].startswith(session)]
    if since:
        cut = since_stamp(since)
        agents = [a for a in agents if not a["first"] or a["first"] >= cut]
    return dirs, agents


def elsewhere(root: Path, dirs: list[Path], tasks: Path | None = None,
              window: int = TTLS["5m"]) -> list[dict]:
    """Sessions dispatching right now that the current scope does NOT cover.

    **The default scope is "the newest session", and with two batches out at
    once that is a coin flip which can land differently between two runs of this
    command.** Two passes in this repo fan out over pages — the Bogoras readers
    and the Moll ones — and they are dispatched from different sessions, so
    running both at once is ordinary rather than exotic. A report that silently
    picked one of them is worse than a slow one: every column would be right,
    about a batch the reader was not asking after.

    So the scope names what it excluded, while it is still plausibly live. The
    window is the subagent cache TTL, because that is the horizon on which "is
    another batch running" has consequences — a session quiet for longer than
    that is history, not competition.

    Reports; never gates. Naming the other session is what a human needs to type
    `--session`, and choosing for them is not this verb's business.
    """
    if tasks is not None:
        return []
    now = datetime.now(UTC).timestamp()
    scoped = {d.resolve() for d in dirs}
    out = []
    for d in find_tasks(root, None):
        if d.resolve() in scoped:
            continue
        age = now - max((f.stat().st_mtime for f in d.glob("*.output")), default=0)
        if age <= window:
            # `d.parent.name` is the session id, which is exactly what
            # `--session` matches on by prefix.
            out.append({"session": d.parent.name[:8], "quiet_for_s": int(age),
                        "agents": len(list(d.glob("*.output")))})
    return sorted(out, key=lambda r: r["quiet_for_s"])


def find_transcripts(root: Path, idents: list[str],
                     tasks: Path | None = None) -> list[Path]:
    """Transcripts whose agent id starts with one of `idents`.

    Prefixes, because the id a reader of the `agents` table has in front of it
    is the eight characters that table prints, not the full one. An ident that
    matches nothing raises rather than returning an empty report: a typo in an
    id and an agent that never ran are different facts, and only one of them is
    the caller's to fix.
    """
    found: dict[str, Path] = {}
    for d in find_tasks(root, tasks):
        for f in _transcripts(d):
            for ident in idents:
                if _ident(f).startswith(ident):
                    found[_ident(f)] = f
    if missing := [i for i in idents
                   if not any(s.startswith(i) for s in found)]:
        raise ValueError(f"no transcript for {', '.join(missing)} — "
                         "`agents usage` lists the ids this project has")
    return [found[k] for k in sorted(found)]


def transcript(path: Path) -> list[dict]:
    """One transcript, request by request, with what each one added.

    **The column that matters is `added`.** A request's `in + read + write` is
    its whole context, so the difference between consecutive requests is what
    arrived between them — a tool result, a raster, a message. Reading down it
    is how a duplicated block is caught: the preloaded contract showed up as
    +14,916 on request 2 of three separate readers, identical to the token,
    which no per-agent total would have separated from ordinary work.

    Request 1 has no predecessor, so its `added` is the opening itself: the
    system prompt and the whole preamble in one sum, undivided because nothing
    in the record divides them.
    """
    reqs, meta = _read(path)
    return _walk(reqs, _ident(path)[:8], meta.get("type", ""))


def classes(walk: list[dict], scope: str = "") -> list[dict]:
    """What a context is made of, by class, largest first, with an `ALL` row.

    **The denominator is the context itself.** Every request's growth belongs to
    exactly one class and the growths sum to the terminal context, so `pct` is a
    share of something real rather than of a total invented for the table. The
    `ALL` row carries that sum, so the shares are checkable against it instead of
    being taken on trust.

    `reply` is a column rather than a class, because it is orthogonal: every
    request has one and it belongs to no tool. Its column total on the `ALL` row
    is what the agent spent thinking and writing, as distinct from what it read.

    `calls` counts requests, not tool invocations. They are the same number for
    every class but `none`, and requests are what the turn budget is denominated
    in — which is the constraint a reader actually hits.
    """
    agg: dict[str, dict] = {}
    for r in walk:
        a = agg.setdefault(r["class"], {"calls": 0, "tokens": 0, "reply": 0, "max": 0})
        a["calls"] += 1
        a["tokens"] += r["result"]
        a["reply"] += r["reply"]
        a["max"] = max(a["max"], r["result"])
    total = sum(a["tokens"] for a in agg.values())
    rows_ = [{**({"scope": scope} if scope else {}),
              "class": k,
              "calls": a["calls"],
              "tokens": a["tokens"],
              "pct": f"{a['tokens'] / total:.1%}" if total else "n/a",
              "mean": a["tokens"] // a["calls"],
              "max": a["max"],
              "reply": a["reply"]}
             for k, a in agg.items()]
    rows_.sort(key=lambda r: (-r["tokens"], CLASSES.index(r["class"])
                              if r["class"] in CLASSES else 99))
    if rows_:
        rows_.append({**({"scope": scope} if scope else {}),
                      "class": "ALL", "calls": sum(r["calls"] for r in rows_),
                      "tokens": total, "pct": "100.0%",
                      "mean": total // max(1, sum(r["calls"] for r in rows_)),
                      "max": max(r["max"] for r in rows_),
                      "reply": sum(r["reply"] for r in rows_)})
    return rows_


def _cohort_key(a: dict) -> tuple[str, str, int]:
    """What decides two agents could have shared a prefix: type, model, opening."""
    return (a["type"], a["model"], a["opening"])


def cohort_ids(agents: list[dict]) -> dict[tuple[str, str, int], str]:
    """`c1`, `c2`, … over the cohorts in scope, oldest batch first.

    **A name is what makes a batch addressable.** `usage` has always grouped
    agents into cohorts — that grouping is the closest thing the transcripts hold
    to "the batch you dispatched" — but the grouping was internal to one table, so
    asking a follow-up question about one batch meant copying four agent ids out
    of the rows above. Numbering them costs a column and turns `cohorts` into an
    index the other actions can be pointed at.

    Ordered by when the cohort last spoke, which is the order `cohorts` already
    prints in, so `c1` is the oldest batch in scope and the newest has the highest
    number. Scope-relative by construction: the ids describe this invocation's
    grouping and are not identifiers anything should store.

    **The tie is broken on the key itself, not left to the set.** Two cohorts can
    share a last-spoke timestamp, and this sorted a `set`, whose iteration order
    for tuples of strings moves with the hash seed — so the same transcripts could
    number the same two batches `c1`/`c2` on one run and the other way round on
    the next, and a `--cohort c2` written down from one report would then point at
    the other batch. Sorting the key as a secondary makes the numbering a function
    of the data alone.
    """
    keys = sorted({_cohort_key(a) for a in agents},
                  key=lambda k: (max(a["last"] for a in agents
                                     if _cohort_key(a) == k), k))
    return {k: f"c{i}" for i, k in enumerate(keys, 1)}


def cohort_classes(agents: list[dict]) -> list[dict]:
    """The class breakdown per cohort — a whole batch's context, decomposed.

    Pooled over the cohort rather than reported per agent, because the question a
    fan-out raises is about the batch: four readers doing the same job differ in
    which page they drew, and a class that is 3% of one reading and 3% of the next
    is a property of the pass, not of either agent. The per-agent view is
    `transcript`, which prints the same breakdown for whatever it was given.
    """
    ids = cohort_ids(agents)
    out_rows = []
    for key, cid in sorted(ids.items(), key=lambda kv: kv[1]):
        members = [a for a in agents if _cohort_key(a) == key]
        out_rows += classes([r for a in members for r in a["walk"]], scope=cid)
    return out_rows


def in_cohort(agents: list[dict], want: str) -> list[dict]:
    """The agents of cohort `want`, or a usage error naming the ones there are.

    An id matching nothing raises for the same reason a mistyped agent id does:
    an empty table cannot be told from a batch that genuinely ran nothing, and
    only one of the two is the caller's to fix.
    """
    ids = cohort_ids(agents)
    members = [a for a in agents if ids[_cohort_key(a)] == want]
    if not members:
        raise ValueError(
            f"no cohort {want!r} in scope — `agents usage` numbers them "
            f"{', '.join(sorted(set(ids.values()))) or '(none)'}")
    return members


def rows(agents: list[dict]) -> list[dict]:
    """The per-agent table.

    `pre` and `ctxs` are dropped: a list-valued field degrades TOON to the
    verbose nested form, and both have their own section.

    **`first` and `last` are both here, and the table is ordered by `first`.**
    Launch order is the question this table is read for — one member of a cohort
    writes the prefix and the rest read it, so who opened first is who paid, and
    a stagger is a claim about `first` alone. Ordering by `last` sorted by when
    agents *finished*, which is duration talking over launch order: a reader that
    opened first and ran long sorted below one dispatched minutes later. With
    both columns the gap between them is the agent's own span, which is the other
    thing worth seeing beside `reqs`.
    """
    ids = cohort_ids(agents)
    return [{"cohort": ids[_cohort_key(a)],
             **{k: v for k, v in a.items() if k not in ("pre", "ctxs", "walk")}}
            for a in agents]


def preamble(agents: list[dict]) -> list[dict]:
    """The user turns ahead of the first reply, one row per turn position.

    **This is where a broken prefix is actually visible.** A cohort table says
    that openings disagree; this says *which turn* disagrees, and a prefix ends
    at the first differing byte, so the first turn with more than one variant is
    the one that costs everything after it. Six readers whose turn 1 has six
    variants are six readers who share nothing, however identical turn 2 is.

    `variants` counts distinct content, not distinct agents: one variant across
    six agents is the shared case, and it is the only shape that caches.
    """
    if not agents:
        return []
    # Grouped by agent type, for the same reason `cohorts` is: two types have
    # different standing instructions, so pooling their turn 1s compares things
    # that were never candidates to share a prefix and reports a spurious
    # "variants: 2" for a batch that was fine.
    out_rows = []
    for atype, members in _by_type(agents).items():
        for i in range(max(len(a["pre"]) for a in members)):
            turns = [a["pre"][i] for a in members if len(a["pre"]) > i]
            variants = {t["hash"] for t in turns}
            out_rows.append({
                "type": atype,
                "turn": i + 1,
                "label": turns[0]["label"],
                "agents": len(turns),
                "variants": len(variants),
                # **Characters, and the one figure here that is not tokens.**
                # No per-message token count is recorded anywhere: `opening`
                # covers the system prompt and the whole preamble undivided, so
                # a per-turn token number could only be a chars/4 estimate, and
                # an estimate sitting in a column beside measured token counts
                # is exactly the plausible-but-underived figure this project
                # refuses. The column is named for its unit for that reason.
                # **Tokens, measured, or a dash.** A request is the only thing
                # counted, so a message's size is knowable exactly when it is
                # the only one to arrive since the previous request: then the
                # context growth is its own. Messages that share a request with
                # another — the whole opening block, where the system prompt is
                # mixed in too — get `-`, because nothing recorded separates
                # them and a divided estimate would be a number with no witness.
                # The growth includes the preceding reply, which is why this is
                # "added since the last request" and not "this message".
                "tokens": _turn_tokens(members, i),
                "shared": "yes" if len(variants) == 1 and len(turns) > 1
                          else "n/a" if len(turns) == 1 else "NO",
            })
    return out_rows


def _turn_tokens(members: list[dict], i: int) -> str:
    """Turn `i`'s size in tokens across `members`, or `-` where it is not one.

    A request's `in + read + write` is its whole context, so the growth from one
    request to the next is what arrived between them. That growth belongs to a
    single message only when a single message arrived — otherwise it is a sum
    nothing in the record divides, and the first block always is one, since the
    system prompt is in it.
    """
    deltas = []
    for a in members:
        if len(a["pre"]) <= i:
            continue
        after = a["pre"][i]["after"]
        # Shares its request with another message, or is the opening block.
        if after == 0 or sum(1 for t in a["pre"] if t["after"] == after) > 1:
            return "-"
        if after >= len(a["ctxs"]):
            return "-"
        deltas.append(a["ctxs"][after] - a["ctxs"][after - 1])
    if not deltas:
        return "-"
    lo, hi = min(deltas), max(deltas)
    return f"{lo:+}" if lo == hi else f"{lo:+}..{hi:+}"


def _by_type(agents: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for a in agents:
        out.setdefault(a["type"], []).append(a)
    return out


def cohorts(agents: list[dict]) -> list[dict]:
    """Agents grouped by the context they opened with — one row per cohort.

    **Grouped rather than pooled, because a session is not a batch.** A day's
    transcripts hold several fan-outs plus whatever one-off agents were spawned
    between them, and averaging across those produces a "shared prefix" no
    dispatch ever had. Two agents belong to one cohort when they agree on model
    *and* on opening total, which is precisely the condition under which they
    could have shared a cached prefix.

    So the diagnostic is not a verdict this function reaches; it is the shape of
    the table. Six readers dispatched together should appear as one cohort of
    six. If they appear as two cohorts, something varied ahead of the shared
    block — and the two openings say how much, which no stagger will recover.

    A cohort of one is reported as such and claims nothing: a lone agent had
    nobody to share with, and calling its opening a shared prefix would be the
    fabrication this whole module exists to catch.
    """
    if not agents:
        return [{"cohort": "", "type": "", "model": "", "opening": 0, "own": 0, "agents": 0, "sessions": 0, "warm": 0,
                 "saved": 0, "missed": 0, "originated": 0, "if_all_cold": 0, "saved_pct": "n/a", "asymptote": "n/a", "note": "no agents in scope"}]
    # **Keyed on agent type as well as model and opening.** Opening alone very
    # nearly decides it — two agent types have different system prompts and so
    # cannot open at the same total — but "very nearly" is not a grouping rule,
    # and the type is what a reader of this table wants to see anyway. Reporting
    # the model while grouping on something the model does not determine was the
    # kind of half-stated key this repo treats as a defect.
    keyed: dict[tuple[str, str, int], list[dict]] = {}
    for a in agents:
        keyed.setdefault(_cohort_key(a), []).append(a)
    ids = cohort_ids(agents)
    rows = []
    for (atype, model, opening), members in sorted(
            keyed.items(), key=lambda kv: max(a["last"] for a in kv[1])):
        warm = sum(1 for a in members if a["opened"] == "warm")
        # One member must always write the prefix; (n-1) reads is the ceiling,
        # and the gap between that and what happened is what a stagger buys.
        missed = (len(members) - 1 - warm) * opening
        # What the batch originated once, versus what it would have cost with
        # every sibling cold. The ratio has a limit worth knowing: with N agents
        # the saving is (N-1)P / (N(P+W)), which TENDS TO P/(P+W) as the batch
        # grows — so a pass whose shared prefix dominates its per-item work
        # approaches halving, and one with a thin prefix never will. It is an
        # asymptote and not a ceiling: (N-1)/N is never 1, so no batch of any
        # size reaches it, and a report calling it a ceiling invites reading a
        # shortfall as a defect when it is arithmetic.
        own = sum(a["ctx"] - opening for a in members)
        per = own // len(members)
        rows.append({
            # The batch's name in this scope, so `transcript --cohort c4` can be
            # typed straight off the row rather than assembled from agent ids.
            "cohort": ids[(atype, model, opening)],
            "type": atype,
            "model": model,
            "opening": opening,
            # The prefix and the mean per-agent work beyond it, side by side,
            # because `asymptote` is just their ratio and a bare percentage is
            # not checkable. An asymptote near 50% means the two columns are
            # near equal, which is a fact about this pass and not a property of
            # the arithmetic — a fatter prefix or leaner per-item work moves it.
            "own": per,
            "agents": len(members),
            "originated": opening + own,
            "if_all_cold": len(members) * opening + own,
            # What this run actually saved, against what the same batch could
            # ever approach. `saved_pct` is measured; `asymptote` is the limit,
            # never attained, so the gap between them is the cost of the batch
            # being small — one member always writes the prefix, and with three
            # that is a third of them.
            "saved_pct": f"{warm * opening / (len(members) * opening + own):.1%}"
                         if len(members) > 1 and own else "n/a",
            "asymptote": f"{opening / (opening + per):.1%}"
                         if len(members) > 1 and own else "n/a",
            # Cross-session, deliberately. The cache is content-addressed, so two
            # sessions opening at the same prefix genuinely do share it — a cohort
            # spanning sessions is a real one, not a grouping artifact.
            "sessions": len({a["session"] for a in members}),
            "warm": warm,
            "saved": warm * opening,
            "missed": missed,
            "note": "" if len(members) > 1 else "singleton — nothing to share",
        })
    return rows


def cost(agents: list[dict], plan: str | None = None) -> list[dict]:
    """What each cohort was charged, in credits, plus an `ALL` row over the scope.

    **Credits and not tokens, because the two rank batches differently.** Output
    costs five times input at every tier, so a fan-out that reads a great deal and
    writes little is cheap in credits and expensive in tokens, and the token total
    that includes cache reads is cheapest of all to misread — reads are free on a
    subscription and routinely run thirty to a hundred times the billed volume.
    Three chapters of this project were first reported off a token column that
    summed reads, and the per-page figure was wrong by more than an order of
    magnitude in the flattering direction.

    `per_agent` is the column a dispatcher acts on, because an agent here is a
    page: it makes two batches of different sizes comparable, and it is what
    changes when the contract or the spec changes. The `ALL` row's `per_agent` is
    over every agent in scope, so a scope holding two unrelated fan-outs reports a
    mean across both — the cohort rows are what to read when that matters.

    **An unpriced model does not get a number.** `rates` returns None for a family
    this file has never been told about, and that cohort reports `credits` as None
    with the model named in `note`, rather than being silently costed at a
    neighbour's rate or dropped from the table. The `ALL` row then says how many
    agents it could not price, so a total is never quietly partial.

    With `plan`, three more columns: share of that plan's five-hour and weekly
    allowance, and the money that share is worth at list price. All three are
    arithmetic on `PLANS`, which carries its source; none is measured here.
    """
    if not agents:
        return []
    ids = cohort_ids(agents)
    keyed: dict[tuple[str, str, int], list[dict]] = {}
    for a in agents:
        keyed.setdefault(_cohort_key(a), []).append(a)
    allow = PLANS.get(plan or "")
    rows, unpriced = [], 0

    def row(name: str, model: str, members: list[dict]) -> dict:
        nonlocal unpriced
        billed_in = sum(a["billed_in"] for a in members)
        out_ = sum(a["out"] for a in members)
        read = sum(a["read"] for a in members)
        r = rates(model) if model else None
        # Ceiling once over the whole scope, as the published formula does it per
        # request — this is an imputation from aggregates either way, and rounding
        # each cohort up before summing would drift the total by a credit a row.
        credits = math.ceil(billed_in * r[0] + out_ * r[1]) if r else None
        if r is None:
            unpriced += len(members)
        d = {
            "cohort": name,
            "model": model or "mixed",
            "agents": len(members),
            "billed_in": billed_in,
            "out": out_,
            "free_read": read,
            # How much of the context was served free. The headline number of the
            # whole caching argument, and it belongs beside the bill rather than
            # in a saving column two sections up, because it is the ratio that
            # says whether the prefix discipline is still working.
            "read_ratio": (round(read / (billed_in + out_), 1)
                           if billed_in + out_ else 0),
            "credits": credits,
            "per_agent": round(credits / len(members)) if credits else None,
            # Output is the expensive half at every tier; this says by how much
            # for this batch, which is what a prompt change has to move.
            "out_pct": (round(out_ * r[1] / credits * 100, 1)
                        if credits else None),
        }
        if allow:
            five, week, usd_month = allow
            d["pct_5h"] = round(credits / five * 100, 2) if credits else None
            d["pct_week"] = round(credits / week * 100, 2) if credits else None
            # Monthly list price at 12/52, not a quarter: a week is not a month
            # over four, and the 8% gap is wider than most differences this
            # table gets read for.
            d["usd"] = (round(credits / week * usd_month * 12 / 52, 2)
                        if credits else None)
        d["note"] = "" if r else f"no published rate for {model!r} — not costed"
        return d

    for key, members in sorted(keyed.items(),
                               key=lambda kv: max(a["last"] for a in kv[1])):
        rows.append(row(ids[key], key[1], members))
    # **Summed from the cohort rows, never re-costed over the pooled agents.**
    # A scope can hold two models, and one rate cannot be applied to both — the
    # earlier version passed a blank model for that case and reported a total of
    # None, which is a table saying nothing about a batch that was fully priced
    # in every row above it. Summing also keeps `unpriced` counted once.
    priced = [r for r in rows if r["credits"] is not None]
    credits = sum(r["credits"] for r in priced) or None
    billed_in = sum(r["billed_in"] for r in rows)
    out_ = sum(r["out"] for r in rows)
    read = sum(r["free_read"] for r in rows)
    models = sorted({r["model"] for r in rows})
    total = {
        "cohort": "ALL",
        "model": models[0] if len(models) == 1 else "mixed",
        "agents": len(agents),
        "billed_in": billed_in,
        "out": out_,
        "free_read": read,
        "read_ratio": (round(read / (billed_in + out_), 1)
                       if billed_in + out_ else 0),
        "credits": credits,
        # Over the agents this total actually covers, so a partly-priced scope
        # does not divide its credits by a headcount it could not cost.
        "per_agent": (round(credits / sum(r["agents"] for r in priced))
                      if credits else None),
        "out_pct": (round(sum(r["out"] * (rates(r["model"]) or (0, 0))[1]
                              for r in priced) / credits * 100, 1)
                    if credits else None),
    }
    if allow:
        five, week, usd_month = allow
        total["pct_5h"] = round(credits / five * 100, 2) if credits else None
        total["pct_week"] = round(credits / week * 100, 2) if credits else None
        total["usd"] = (round(credits / week * usd_month * 12 / 52, 2)
                        if credits else None)
    total["note"] = (f"{unpriced} of {len(agents)} agents on an unpriced model — "
                     "this total covers the rest") if unpriced else ""
    rows.append(total)
    return rows


def warmth(agents: list[dict]) -> list[dict]:
    """Whether the most recent cohort's prefix is still cached, on the TTL clock.

    The only pre-flight signal available: the cache cannot be queried, so the
    age of the last request against `TTL` is the whole of what can be said.
    """
    if not agents:
        return []
    age = _age(max(a["last"] for a in agents))
    if age is None:
        return []
    # The tier is read off the agents in scope rather than assumed. Where they
    # disagree the shortest wins: a prefix is warm only while *every* witness to
    # it still is, and the optimistic reading would send a batch at a cold cache.
    tiers = {a["ttl"] for a in agents if a["ttl"]}
    ttl = min((TTLS[t] for t in tiers), default=TTL)
    return [{"since_last_request_s": round(age),
             "ttl_s": ttl,
             "tier": "/".join(sorted(tiers)) or "unrecorded — assuming 5m",
             "state": "warm" if age < ttl else "EXPIRED"}]
