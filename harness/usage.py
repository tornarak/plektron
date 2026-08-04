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
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path

# **Read, not assumed.** A request records which TTL its write bought, under
# `usage.cache_creation`, so the expiry clock is a measurement rather than a
# constant taken from the docs. The two named tiers:
TTLS = {"5m": 300, "1h": 3600}
TTL = TTLS["5m"]  # the fallback when a scope wrote nothing and so named no tier


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
    reqs, meta = [], {"pre": []}
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
            if rec.get("type") == "user" and not reqs:
                text = _text(rec)
                meta["pre"].append({"chars": len(text), "label": _label(rec),
                                    "hash": sha1(text.encode()).hexdigest()[:8]})
                if "task" not in meta:
                    meta["task"] = meta["pre"][0]["label"]
            u = (rec.get("message") or {}).get("usage")
            if not u:
                continue
            tiers = u.get("cache_creation") or {}
            reqs.append({
                "read": u.get("cache_read_input_tokens", 0),
                "write": u.get("cache_creation_input_tokens", 0),
                "tier": ("1h" if tiers.get("ephemeral_1h_input_tokens")
                         else "5m" if tiers.get("ephemeral_5m_input_tokens") else ""),
                "out": u.get("output_tokens", 0),
                "model": rec.get("model") or (rec.get("message") or {}).get("model", ""),
                "at": rec.get("timestamp", ""),
            })
    return reqs, meta


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
        "out": sum(r["out"] for r in reqs),
        "first": min(r["at"] for r in reqs),
        "last": max(r["at"] for r in reqs),
    }


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
    agents = sorted((a for d in dirs for f in sorted(d.glob("*.output"))
                     if (a := _agent(f))), key=lambda a: a["last"])
    if session:
        agents = [a for a in agents if a["session"].startswith(session)]
    if since:
        agents = [a for a in agents if not a["first"] or a["first"] >= since]
    return dirs, agents


def rows(agents: list[dict]) -> list[dict]:
    """The per-agent table. `pre` is dropped: a list-valued field degrades TOON
    to the verbose nested form, and it has its own section."""
    return [{k: v for k, v in a.items() if k not in ("pre", "first")} for a in agents]


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
    depth = max(len(a["pre"]) for a in agents)
    out_rows = []
    for i in range(depth):
        turns = [a["pre"][i] for a in agents if len(a["pre"]) > i]
        variants = {t["hash"] for t in turns}
        sizes = sorted({t["chars"] for t in turns})
        out_rows.append({
            "turn": i + 1,
            "label": turns[0]["label"],
            "agents": len(turns),
            "variants": len(variants),
            "chars": str(sizes[0]) if len(sizes) == 1 else f"{sizes[0]}..{sizes[-1]}",
            "shared": "yes" if len(variants) == 1 and len(turns) > 1
                      else "n/a" if len(turns) == 1 else "NO",
        })
    return out_rows


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
        return [{"model": "", "opening": 0, "agents": 0, "sessions": 0, "warm": 0,
                 "shared": "no agents in scope", "missed": 0}]
    keyed: dict[tuple[str, int], list[dict]] = {}
    for a in agents:
        keyed.setdefault((a["model"], a["opening"]), []).append(a)
    rows = []
    for (model, opening), members in sorted(keyed.items(),
                                            key=lambda kv: max(a["last"] for a in kv[1])):
        warm = sum(1 for a in members if a["opened"] == "warm")
        # One member must always write the prefix; (n-1) reads is the ceiling,
        # and the gap between that and what happened is what a stagger buys.
        missed = (len(members) - 1 - warm) * opening
        rows.append({
            "model": model,
            "opening": opening,
            "agents": len(members),
            # Cross-session, deliberately. The cache is content-addressed, so two
            # sessions opening at the same prefix genuinely do share it — a cohort
            # spanning sessions is a real one, not a grouping artifact.
            "sessions": len({a["session"] for a in members}),
            "warm": warm,
            "shared": f"{warm * opening:,} read"
                      if len(members) > 1 else "singleton — nothing to share",
            "missed": missed,
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
