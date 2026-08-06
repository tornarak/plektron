"""`harness agents` — what a dispatched batch paid, read off the transcripts.

The group names what it touches, and this one does not touch a corpus store: it
reads Claude Code's own task transcripts. It is here rather than in `tools/`
because the two dispatch loops in this repo (`ocr queue`/`claim`, and the moll
pass's `entry_bounds.py queue`/`claim`) both fan out over pages, and both are
worth measuring the same way — a script with no reference entry and no surface test is
how the last set of undocumented flags accumulated.

`usage` answers the question a coordinator can act on — did the siblings share a
prefix, and did the ones after the first read it. `transcript` is what to open
when the answer is no, or when a total looks wrong: it walks one agent request by
request and shows what each one added. `sync` is the odd one out and touches the
contract rather than a measurement: it refills the reader's transcluded blocks
from their sources.
"""
from __future__ import annotations

from ..dispatch import sync_all
from ..usage import (
    batch,
    classes,
    cohort_classes,
    cohorts,
    elsewhere,
    find_transcripts,
    in_cohort,
    preamble,
    project,
    rows,
    transcript,
    warmth,
)
from ._common import (
    action,
    add_all,
    arg,
    exclusive,
    group,
    opt,
    out,
    require_exactly_one,
)


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

    p = action(g, "sync", run_sync,
               help="refill the groundtruth-reader's transcluded blocks from "
               "the files they name. The reader's whole contract has to sit in "
               "its system prompt and `keying_spec.md` has to stay one file, so "
               "the spec is copied in and `test_transclusion.py` fails on a "
               "copy that disagrees with its source. **Edit the source, then "
               "run this** — `ocr queue` does it too, but on the way out of a "
               "dispatch, which is no help to a spec edit made between batches. "
               "Bare form names the stale blocks and writes nothing")
    opt(p, "--commit", is_flag=True,
        help="actually rewrite the agent file — bare form only reports which "
             "sources its blocks have drifted from")

    p = action(g, "transcript", run_transcript,
               help="one named agent's requests, and what each one added to "
               "its context. **`added` is the column**: a request's whole "
               "context is `in + read + write`, so the difference between "
               "consecutive requests is what arrived between them — a tool "
               "result, a raster, a message. Reading down it catches a "
               "duplicated block, which no per-agent total can: a contract "
               "re-injected on resume showed up as +14,916 on request 2 of "
               "three separate readers, identical to the token. Request 1 has "
               "no predecessor, so its `added` is the opening itself. **`added` "
               "splits into `reply` and `result`** — the agent's own output, "
               "which stays in context, and what its tool actually returned — "
               "and a `classes` breakdown follows the requests, so the same "
               "decomposition can be read whole. Reports; never gates"
               "\n\nAGENT: an agent id, or the leading characters of one — "
               "what the `usage` table prints. `--cohort` takes a whole batch "
               "instead, by the id `usage` numbers it with.",
               constraints=(require_exactly_one("agents", "cohort"),))
    arg(p, "agents", nargs=-1, required=False, metavar="AGENT")
    opt(p, "--cohort", default=None, metavar="ID",
        help="every agent of one cohort — a batch, as `usage` groups it (c1, "
             "c2, …). The way to ask a question about a fan-out rather than "
             "about one of its readers")
    opt(p, "--session", default=None,
        help="one session, by slug or id prefix — scopes --cohort, whose ids "
             "are relative to the agents in view")
    add_all(p, "session this project has transcripts for, not just the newest — "
               "scopes --cohort")
    opt(p, "--tasks", type=str, default=None,
        help="the task-transcript directory [the newest session for --root's "
             "project that has any]")


def run_sync(a) -> int:
    out(a, [{"agent": r["agent"],
             # A missing agent file is not zero stale blocks — it is no contract at
             # all, and a row reading `0 —` would say the opposite of what is true.
             "stale": "ABSENT" if not r["exists"] else len(r["updated"]),
             "sources": ", ".join(r["updated"]) or "—",
             "commit": bool(a.commit)}
            for r in sync_all(a.root, commit=a.commit)], name="transclusions")
    return 0


def run_transcript(a) -> int:
    from pathlib import Path
    tasks = Path(a.tasks) if a.tasks else None
    if a.cohort:
        # **The walk is the one already taken, not a second one.** `batch` has
        # decomposed every request to group the agents at all, so re-reading the
        # transcripts here would be two paths to one number with two chances to
        # disagree — and the whole grouping this flag names lives on that side.
        _, agents = batch(a.root, tasks, session=a.session, all_=a.all)
        walk = [r for m in in_cohort(agents, a.cohort) for r in m["walk"]]
    else:
        paths = find_transcripts(a.root, list(a.agents), tasks)
        walk = [t for p in paths for t in transcript(p)]
    out(a, walk, name="transcript")
    out(a, classes(walk), name="classes", heading=True)
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
    out(a, cohort_classes(agents), name="classes", heading=True)
    out(a, warmth(agents), name="warmth", heading=True)
    return 0
