"""`harness agents` — what a dispatched batch paid, read off the transcripts.

The group names what it touches, and this one does not touch a corpus store: it
reads Claude Code's own task transcripts. It is here rather than in `tools/`
because the two dispatch loops in this repo (`ocr queue`/`claim`, and the moll
pass's `entry_bounds.py queue`/`claim`) both fan out over pages, and both are
worth measuring the same way — a script with no reference entry and no surface test is
how the last set of undocumented flags accumulated.

Two actions. `usage` answers the question a coordinator can act on — did the
siblings share a prefix, and did the ones after the first read it. `transcript`
is what to open when the answer is no, or when a total looks wrong: it walks one
agent request by request and shows what each one added.
"""
from __future__ import annotations

from ..usage import (
    batch,
    cohorts,
    elsewhere,
    find_transcripts,
    preamble,
    project,
    rows,
    transcript,
    warmth,
)
from ._common import action, add_all, arg, exclusive, group, opt, out


def register(cli):
    g = group(cli, "agents", "cache telemetry over a dispatched batch — "
              "whether the siblings shared a prefix, and what the fan-out "
              "actually paid for it",
              section="Apparatus and reports")

    p = action(g, "usage", run_usage,
               help="per-agent cache reads and writes for the most recent "
               "session's batch, plus the derived verdict. **The opening total "
               "is the diagnostic**: read+write on an agent's first request is "
               "what its context cost to establish whatever the cache did, so "
               "siblings dispatched with identical prompts must open at the "
               "same number. Openings that disagree mean a byte varies ahead "
               "of the shared block, which no launch order fixes. A large "
               "tail write is ordinary by contrast — content behind the prefix "
               "was going to be written anyway. Reports; never gates",
               constraints=(exclusive("all", "session"),))
    opt(p, "--session", default=None,
        help="one session, by slug or id prefix — what tells two concurrent "
             "sessions apart when both are dispatching")
    add_all(p, "session this project has transcripts for, not just the newest")
    opt(p, "--since", default=None,
        help="only agents whose first request sorts at or after this "
             "(ISO date or stamp) [no window]")
    opt(p, "--tasks", type=str, default=None,
        help="the task-transcript directory [the newest session for --root's "
             "project that has any]")

    p = action(g, "transcript", run_transcript,
               help="one named agent's requests, and what each one added to "
               "its context. **`added` is the column**: a request's whole "
               "context is `in + read + write`, so the difference between "
               "consecutive requests is what arrived between them — a tool "
               "result, a raster, a message. Reading down it catches a "
               "duplicated block, which no per-agent total can: a contract "
               "re-injected on resume showed up as +14,916 on request 2 of "
               "three separate readers, identical to the token. Request 1 has "
               "no predecessor, so its `added` is the opening itself. Reports; "
               "never gates"
               "\n\nAGENT: an agent id, or the leading characters of one — "
               "what the `usage` table prints.")
    arg(p, "agents", nargs=-1, required=True, metavar="AGENT")
    opt(p, "--tasks", type=str, default=None,
        help="the task-transcript directory [the newest session for --root's "
             "project that has any]")


def run_transcript(a) -> int:
    from pathlib import Path
    paths = find_transcripts(a.root, list(a.agents),
                             Path(a.tasks) if a.tasks else None)
    out(a, [t for p in paths for t in transcript(p)], name="transcript")
    return 0


def run_usage(a) -> int:
    from pathlib import Path
    dirs, agents = batch(a.root, Path(a.tasks) if a.tasks else None,
                         session=a.session, since=a.since, all_=a.all)
    # **Name the sessions, do not count the directories.** `sessions` used to be
    # `len(dirs)`, which is how many were *searched* — under `--session` that is
    # every session the project has, while the report covers one. A scope row
    # that cannot be read back to "which batch is this" is the one thing this
    # section is for.
    named = sorted({x["session"] for x in agents})
    out(a, [{"project": project(a.root).name,
             "session": ", ".join(named) or "—",
             "sessions": len(named),
             "types": ", ".join(sorted({x["type"] for x in agents if x["type"]})) or "—",
             "agents": len(agents)}], name="scope")
    if others := elsewhere(a.root, dirs, Path(a.tasks) if a.tasks else None):
        out(a, others, name="also_dispatching", heading=True)
    out(a, rows(agents), name="agents", heading=True)
    out(a, preamble(agents), name="preamble", heading=True)
    out(a, cohorts(agents), name="cohorts", heading=True)
    out(a, warmth(agents), name="warmth", heading=True)
    return 0
