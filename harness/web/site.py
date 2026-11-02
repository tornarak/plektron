"""`site build` — every published text, and the landing page above them.

`OUT/index.html` lists the texts; each sits at `OUT/<workspace>/<text>/`, the
prefix `layout.site_base` gives it, written by `build.build` unchanged. A text says
it is published in its own manifest (`layout.publish`), so the choice is tracked.

**A text is rebuilt only when something upstream is newer than its last clean
build.** Fresh means all of: a `.edition-built` stamp, which only a build with no
refused row leaves; a stamp recording this run's base and drafts; and no upstream
path as new as the folder's `.edition-build` mark.

**The mark is the reference time because it goes down before anything is read**,
so an edit landing mid-crawl counts as newer, and because the filesystem stamped it,
so no second clock is compared. A tie rebuilds: `cache.py` measured these mtimes as
coarse.

**Upstream is everything but what is shown to be unread.** The two errors are not
the same size: a false rebuild costs a minute, and a false skip publishes a stale
page that nothing marks. So it is the whole text, its workspace and the code that
renders, less a short list.

**Directories count as well as files.** A deleted entity changes no file that is
left, only its parent directory's mtime.

What this cannot see: a file put back with an old mtime (`cp -p`, `rsync -t`; `git
checkout` stamps the present, so it is seen), a site directory copied without its
mtimes, and `espeak-ng` on the host. `--force` is the answer to all three.
"""
from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .. import layout, tei_html
from . import STATIC, stores, templates
from .build import OUT_MARK, build

#: What marks a directory as a site's own. A site's root is never cleared, but a
#: withdrawal deletes under it, so it has to be one this verb wrote.
SITE_MARK = ".edition-site"
#: A clean build's receipt, in the text's folder beside `OUT_MARK`.
STAMP = ".edition-built"
#: The authored prose above the generated list, relative to the repo.
LANDING_PROSE = Path("site") / "landing.html"
#: A text's own folders that a render never opens.
_UNREAD = frozenset({"train", "pdfs"})


def _walk(top: Path, skip: frozenset[str] = frozenset()) -> Iterator[Path]:
    """`top`, and every path below it. Symlinks are themselves and never followed:
    a farm's link is a fact about the farm, and what it points at is walked as
    itself wherever it lives. A top that is not there yields nothing."""
    if not top.exists():
        return
    yield top
    for d, dirs, files in os.walk(top):
        dirs[:] = sorted(n for n in dirs if n != "__pycache__" and n not in skip)
        here = Path(d)
        yield from (here / n for n in dirs)
        yield from (here / n for n in sorted(files))


def upstream(root: Path) -> Iterator[Path]:
    """Every path a build of this text could have read."""
    root = Path(root).resolve()
    yield from _walk(root, _UNREAD)
    ws = layout.workspace_root(root)
    if ws is not None:
        siblings = {p.parent.name for p in ws.glob(f"*/{layout.PROJECT_JSON}")}
        yield from _walk(ws, frozenset({"models"}) | siblings)
    code = layout.repo_root()
    yield from _walk(code / "harness", frozenset({"tests"}))
    yield code / "uv.lock"


def _stamp_text(base: str, drafts: bool) -> str:
    return json.dumps({"base": base, "drafts": drafts}, sort_keys=True) + "\n"


def stale(root: Path, dest: Path, base: str, drafts: bool) -> str | None:
    """Why this text's folder cannot stand, or None if it can."""
    mark, receipt = dest / OUT_MARK, dest / STAMP
    if not mark.is_file():
        return "never built"
    if not receipt.is_file():
        return "its last build did not finish clean"
    if receipt.read_text(encoding="utf-8") != _stamp_text(base, drafts):
        return "built with a different base or drafts setting"
    since = mark.stat().st_mtime_ns
    newest, when = None, since - 1
    root = Path(root).resolve()
    for p in upstream(root):
        try:
            t = p.lstat().st_mtime_ns
        except OSError:                   # gone since the walk: its directory says so
            continue
        if t > when:
            newest, when = p, t
    if newest is None:
        return None
    for top in (root, layout.repo_root()):
        if newest.is_relative_to(top):
            newest = newest.relative_to(top)
            break
    return f"{newest} is newer"


@dataclass
class SiteReport:
    """What a run did with each text, and what the text's own build refused."""

    out: Path
    #: `{text, state, why}`, one per text and one per withdrawn folder.
    rows: list[dict] = field(default_factory=list)
    #: `{url, why, from}` from `build.Site.rows`, with the text they belong to.
    refused: list[dict] = field(default_factory=list)
    #: What pooled workers wrote to stderr: `{text, stderr_lines, stderr_log}`.
    worker_logs: list[dict] = field(default_factory=list)


def _refuse_out(repo: Path, out: Path, roots: list[Path]) -> None:
    """Nothing is deleted until `out` has been shown to be a site's own."""
    if out.exists() and any(out.iterdir()) and not (out / SITE_MARK).is_file():
        raise ValueError(f"{out} is not empty and holds no {SITE_MARK}, so no site "
                         "build wrote it: refusing to write there. Name a directory "
                         "of its own")
    r = out.resolve()
    for own in {*roots, *filter(None, map(layout.workspace_root, roots)),
                layout.repo_root() / "harness"}:
        if r == own.resolve() or own.resolve() in r.parents:
            raise ValueError(f"{out} is inside {own}, which a build reads: each build "
                             "would make the next one stale. Name a directory outside it")


def _withdraw(out: Path, keep: set[Path], rep: SiteReport) -> None:
    """Take down a built text that is no longer published. A folder with no build's
    mark is not this verb's to touch, whatever it is called."""
    for mark in sorted(out.glob(f"*/*/{OUT_MARK}")):
        d = mark.parent
        if d.resolve() in keep:
            continue
        shutil.rmtree(d)
        rep.rows.append({"text": str(d.relative_to(out)), "state": "withdrawn",
                         "why": "built here, and no text publishes it now"})
        # Only if that left it empty: rmdir refuses otherwise.
        try:
            d.parent.rmdir()
        except OSError:
            pass


def _workspace_title(ws: Path) -> str:
    rec = json.loads((ws / layout.WORKSPACE_JSON).read_text(encoding="utf-8"))
    return rec.get("title") or ws.name


def _landing(repo: Path, out: Path, published: list[Path]) -> None:
    """Rewritten every run: it is cheap, it holds no time, and the counts on it
    change without any text needing a rebuild."""
    prose = Path(repo) / LANDING_PROSE
    if not prose.is_file():
        raise ValueError(f"{prose}: the landing page's prose is not there")
    groups: dict[Path, dict] = {}
    for root in published:
        ws = layout.workspace_root(root)
        assert ws is not None             # `build_site` refused any other
        read = tei_html.readable(root)
        collated = tei_html.collated(root)
        drafts = layout.publish(root) == "drafts"
        groups.setdefault(ws, {"title": _workspace_title(ws), "texts": []})["texts"].append({
            "url": layout.site_base(root) + "/",
            "work": stores.work(root),
            "collated": len(collated),
            "drafts": len(read) - len(collated) if drafts else 0,
        })
    html = templates.env.get_template("site/index.html").render(
        prose=prose.read_text(encoding="utf-8"),
        workspaces=[groups[ws] for ws in sorted(groups)])
    (out / "index.html").write_text(html, encoding="utf-8")
    css = out / "static" / "css"
    css.mkdir(parents=True, exist_ok=True)
    # The reading view's own sheet, so the theme's tokens are stated once.
    for name in ("edition.css", "landing.css"):
        shutil.copyfile(STATIC / "css" / name, css / name)
    marks = out / "static" / "site"
    marks.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STATIC / "site" / "plektron.svg", marks / "plektron.svg")
    # At the root as well: a browser asks there whatever a page declares.
    shutil.copyfile(STATIC / "site" / "favicon.ico", out / "favicon.ico")


def build_site(repo: Path, out: Path, force: bool = False, jobs: int | None = None,
               tick=None) -> SiteReport:
    """Bring `out` up to date with every text under `repo`. `tick` is per text's
    crawl. See the module docstring for what makes a text fresh."""
    out = Path(out)
    roots = layout.texts(repo)
    _refuse_out(repo, out, roots)
    for root in roots:
        if layout.publish(root) and layout.workspace_root(root) is None:
            raise ValueError(f"{root} says `publish` and sits in no workspace, so the "
                             "landing page has nowhere to list it")
    published = [r for r in roots if layout.publish(r)]
    if not published:
        raise ValueError(f"no text under {repo} declares `publish` in its "
                         f"{layout.PROJECT_JSON}: nothing to build")

    out.mkdir(parents=True, exist_ok=True)
    (out / SITE_MARK).write_text("written by `harness site build`\n", encoding="utf-8")
    rep = SiteReport(out=out)
    dests = {r: out / layout.site_base(r).lstrip("/") for r in published}
    _withdraw(out, {d.resolve() for d in dests.values()}, rep)

    for root in roots:
        name = layout.site_base(root).lstrip("/")
        if root not in dests:
            rep.rows.append({"text": name, "state": "unpublished",
                             "why": f"no `publish` in its {layout.PROJECT_JSON}"})
            continue
        dest, base = dests[root], layout.site_base(root)
        drafts = layout.publish(root) == "drafts"
        why = "--force" if force else stale(root, dest, base, drafts)
        if why is None:
            rep.rows.append({"text": name, "state": "fresh", "why": ""})
            continue
        site = build(root, dest, base=base, drafts=drafts, jobs=jobs, tick=tick, home="/")
        if site.worker_log.get("stderr_lines"):
            rep.worker_logs.append({"text": name, **site.worker_log})
        if site.rows:
            # No stamp, so the next run takes this text again.
            rep.rows.append({"text": name, "state": "refused",
                             "why": f"{len(site.rows)} refused, after: {why}"})
            rep.refused += [{"text": name, **r} for r in site.rows]
            continue
        (dest / STAMP).write_text(_stamp_text(base, drafts), encoding="utf-8")
        rep.rows.append({"text": name, "state": "built", "why": why})

    _landing(repo, out, published)
    return rep
