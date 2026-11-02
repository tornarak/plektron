"""`harness site` — the public site: every published text, and the page above them.

Its own group, and a repo-level one, because it has no single text to be run
inside: `edition` is one text's reading view, and this is what stands over all of
them.
"""
from __future__ import annotations

import sys

from ..render import progress
from ._common import JOBS_HELP_CRAWL, action, add_jobs, arg, group, opt, out


def register(cli):
    g = group(cli, "site",
              "the public site: every text a `project.json` declares published, "
              "under the landing page",
              section="Whole-corpus")

    p = action(g, "build", run_build,
               help="write the public site to OUT: `index.html`, the landing page, "
               "and each text whose `project.json` says `publish` at "
               "OUT/<workspace>/<text>/, as `edition build` writes it. OUT itself "
               "is never cleared. A text is rebuilt only if something upstream of "
               "it is newer than its last clean build, and a text no longer "
               "published is taken down. Exit 1 if any text's build refused "
               "anything: do not upload that")
    arg(p, "out", metavar="OUT")
    opt(p, "--force", is_flag=True,
        help="rebuild every published text, whatever the timestamps say")
    add_jobs(p, processes=True, help=JOBS_HELP_CRAWL)


def run_build(a) -> int:
    from pathlib import Path

    from ..web.site import build_site

    with progress("building") as tick:
        rep = build_site(a.root, Path(a.out), force=a.force, jobs=a.jobs, tick=tick)
    out(a, rep.rows, name="texts")
    if rep.refused:
        out(a, [{"text": r["text"], "url": r["url"], "why": r["why"],
                 "from": " ".join(r["from"])} for r in rep.refused],
            name="refused", heading=True)
    # stderr, so `--json` stays one document.
    print(f"{sum(r['state'] == 'built' for r in rep.rows)} built, "
          f"{sum(r['state'] == 'fresh' for r in rep.rows)} fresh, "
          f"{len(rep.refused)} refused, in {a.out}", file=sys.stderr)
    for log in rep.worker_logs:
        print(f"{log['text']}: the workers wrote {log['stderr_lines']} line(s) to "
              f"stderr: {log['stderr_log']}", file=sys.stderr)
    return 1 if rep.refused else 0
