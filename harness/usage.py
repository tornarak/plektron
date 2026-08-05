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
            if '"cache_read_input_tokens"' not in line and '"role":"user"' not in line:
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


def _requests(path: Path) -> list[dict]:
    return _read(path)[0]


def _agent(path: Path) -> dict | None:
    reqs, meta = _read(path)
    if not reqs:
        return None
    first = reqs[0]
    return {
        "session": meta.get("session", ""),
        "agent": path.stem[:8],
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
    dirs = find_tasks(root, tasks)
    if not all_ and tasks is None and session is None:
        dirs = dirs[-1:]
    # Ordered by when each agent OPENED, not when it finished: launch order is
    # what decides which one wrote the shared prefix, and `last` sorted a reader
    # that opened first and ran long below one dispatched minutes later.
    agents = sorted((a for d in dirs for f in sorted(d.glob("*.output"))
                     if (a := _agent(f))), key=lambda a: a["first"])
    if session:
        agents = [a for a in agents if a["session"].startswith(session)]
    if since:
        cut = since_stamp(since)
        agents = [a for a in agents if not a["first"] or a["first"] >= cut]
    return dirs, agents


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
        for f in d.glob("*.output"):
            for ident in idents:
                if f.stem.startswith(ident):
                    found[f.stem] = f
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
    out, prev_ctx, prev = [], 0, None
    for i, r in enumerate(reqs, 1):
        ctx = r["in"] + r["read"] + r["write"]
        note, detail = _arrival(prev)
        out.append({
            "agent": path.stem[:8],
            "type": meta.get("type", ""),
            "req": i,
            # Whether that growth was PAID FOR or free. A request that wrote
            # nothing had its whole context served from cache; one that wrote
            # is the only kind that costs, and the amount is the `write`.
            "via": "read" if not r["write"] else "write",
            "read": r["read"],
            "write": r["write"],
            "ctx": ctx,
            "added": ctx if i == 1 else ctx - prev_ctx,
            "out": r["out"],
            "note": note,
            "detail": detail,
        })
        prev_ctx, prev = ctx, r
    return out


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
    return [{k: v for k, v in a.items() if k not in ("pre", "ctxs")} for a in agents]


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
        return [{"type": "", "model": "", "opening": 0, "own": 0, "agents": 0, "sessions": 0, "warm": 0,
                 "saved": 0, "missed": 0, "originated": 0, "if_all_cold": 0, "saved_pct": "n/a", "asymptote": "n/a", "note": "no agents in scope"}]
    # **Keyed on agent type as well as model and opening.** Opening alone very
    # nearly decides it — two agent types have different system prompts and so
    # cannot open at the same total — but "very nearly" is not a grouping rule,
    # and the type is what a reader of this table wants to see anyway. Reporting
    # the model while grouping on something the model does not determine was the
    # kind of half-stated key this repo treats as a defect.
    keyed: dict[tuple[str, str, int], list[dict]] = {}
    for a in agents:
        keyed.setdefault((a["type"], a["model"], a["opening"]), []).append(a)
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
