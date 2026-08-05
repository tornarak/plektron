"""`harness verbs` — `VERBS.md` addressed by verb instead of read whole.

One action, deliberately. This is a lookup into a file that already exists and is
already gated; anything more would be a second interface to the same text.

The measurement behind it: a reader mid-page wanted to know the surface of its own
commands, `Read` the reference twice, and spent 33,251 tokens doing it — a fifth of
that page's whole context, more than every folio hunt on it combined. `verbs zoom`
is under a thousand.
"""
from __future__ import annotations

from ..verbs import lookup
from ._common import action, arg, group, out


def register(cli):
    g = group(cli, "verbs", "the CLI's own reference, one entry at a time — "
              "what an action does, reads, writes, and what its exit code means",
              section="Apparatus and reports")

    p = action(g, "show", run_show,
               help="one action's entry from VERBS.md (`verbs show ocr zoom`), a "
               "whole group's plus the Conventions that bind every action "
               "(`verbs show ocr`), or — with nothing named — the list of every "
               "action there is. Reach for this instead of reading the reference: "
               "it is ~100 KB and answering one question with all of it has cost a "
               "single reading pass a fifth of its context")
    arg(p, "query", nargs=-1, metavar="[GROUP [ACTION]]")


def run_show(a) -> int:
    q = " ".join(a.query or ())
    rec = lookup(q, a.root)
    # The prose goes to stdout as prose. `out()` would wrap it in a table, which
    # is the one shape a reference entry must not arrive in — it is written to be
    # read, and the tables in it are part of the text.
    if rec["text"]:
        print(rec["text"])
    else:
        out(a, [{"action": n} for n in rec["actions"]], name="actions")
    return 0
