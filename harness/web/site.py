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

**`web/static/` is on that list, because a stylesheet's edit changes no page.** Its
files are served as they are and no render reads them, so a fresh text just takes
a new copy of them each run, as the landing page does. The exception is a file
that has gone: a page may still link it, and only a crawl would say so, so that
rebuilds.

**Directories count as well as files.** A deleted entity changes no file that is
left, only its parent directory's mtime.

What this cannot see: a file put back with an old mtime (`cp -p`, `rsync -t`; `git
checkout` stamps the present, so it is seen), a site directory copied without its
mtimes, and `espeak-ng` on the host. `--force` is the answer to all three.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Iterator
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from urllib.parse import quote

from .. import layout, tei_html
from . import STATIC, meta, stores, templates
from .build import OUT_MARK, build

#: What marks a directory as a site's own. A site's root is never cleared, but a
#: withdrawal deletes under it, so it has to be one this verb wrote.
SITE_MARK = ".edition-site"
#: A clean build's receipt, in the text's folder beside `OUT_MARK`.
STAMP = ".edition-built"
#: The authored prose above the generated list, relative to the repo.
LANDING_PROSE = Path("site") / "landing.html"
#: What a host leaves out of an upload, in gitignore syntax: the verb's own marks,
#: and the note on the third-party logos, which is for this repo's reader.
ASSETS_IGNORE = ".edition-*\nREADME.md\n"
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
    yield from _walk(code / "harness", frozenset({"tests", STATIC.name}))
    yield code / "uv.lock"


def _static_gone(dest: Path) -> Path | None:
    """A static file this text's folder holds and the source no longer does."""
    have = dest / "static"
    for p in sorted(have.rglob("*")):
        if p.is_file() and not (STATIC / p.relative_to(have)).exists():
            return p.relative_to(dest)
    return None


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
    if (gone := _static_gone(dest)) is not None:
        return f"{gone} is gone from the source"
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


#: How much of a page's head is read to tell a page from a stub or a refusal.
#: `_meta.html` puts the robots tag before the JSON-LD, well inside this.
_HEAD_BYTES = 8192
_NOINDEX = re.compile(r"""<meta name=["']robots["'] content=["']noindex["']""")


def _indexable(page: Path) -> bool:
    """Whether a written page is one a search engine should list: not a redirect
    stub (`build._stub`), and not a page whose own head says `noindex`."""
    with page.open("rb") as f:
        head = f.read(_HEAD_BYTES).decode("utf-8", "replace")
    return ("<title>Redirecting</title>" not in head
            and not _NOINDEX.search(head))


def sitemap_urls(dest: Path, origin: str, base: str) -> list[str]:
    """Every page a text's folder holds that a reader would land on, absolute.

    **From what is on disk, not from the crawl's own record.** A text left fresh
    by `site build` is not crawled again, and its sitemap must still be whole;
    the folder is the one record that is right for both. Fragments (`/partial/`)
    are documents a script fetches into a page, not pages."""
    out = []
    for page in sorted(dest.rglob("index.html")):
        rel = page.parent.relative_to(dest).as_posix()
        if rel.startswith("partial/") or rel == "partial" or not _indexable(page):
            continue
        path = f"{base}/{rel}" if rel != "." else f"{base}/"
        out.append(origin + quote(path, safe="/"))
    return out


def _sitemaps(out: Path, published: list[Path]) -> None:
    """`<base>/sitemap.xml` per text and a root `sitemap.xml` indexing them, and
    `robots.txt` naming the index. A text whose header gives no `<ptr>` has no
    address to state, so it has no sitemap; and with none at all, no robots.txt."""
    maps, partials = [], []
    for root in published:
        origin, base = stores.work(root)["origin"], layout.site_base(root)
        dest = out / base.lstrip("/")
        if not origin or not dest.is_dir():
            continue
        urls = sitemap_urls(dest, origin, base)
        body = "".join(f"<url><loc>{escape(u)}</loc></url>\n" for u in urls)
        (dest / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}</urlset>\n", encoding="utf-8")
        maps.append(f"{origin}{base}/sitemap.xml")
        partials.append(f"{base}/partial/")
    for name in ("sitemap.xml", "robots.txt"):
        (out / name).unlink(missing_ok=True)
    if not maps:
        return
    origins = {m.split("/", 3)[2] for m in maps}
    body = "".join(f"<sitemap><loc>{escape(m)}</loc></sitemap>\n" for m in maps)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}</sitemapindex>\n", encoding="utf-8")
    # One host per robots.txt: an index naming two would be a site this verb did
    # not build, and saying so is better than a file that half-answers.
    if len(origins) != 1:
        raise ValueError(f"the published texts' headers name {len(origins)} hosts "
                         f"({', '.join(sorted(origins))}); one site has one")
    root_url = maps[0].split("/", 3)
    (out / "robots.txt").write_text(
        "User-agent: *\n" + "".join(f"Disallow: {p}\n" for p in partials)
        + f"\nSitemap: {root_url[0]}//{root_url[2]}/sitemap.xml\n", encoding="utf-8")


def _landing(repo: Path, out: Path, published: list[Path]) -> None:
    """Rewritten every run: it is cheap, it holds no time, and the counts on it
    change without any text needing a rebuild.

    A text's picture is the one its own build wrote, at `<base>/cover-640.jpg`
    (`edition.cover`), which its index shows too: one image, served once."""
    from .edition import COVER_WIDTHS, cover_url

    prose = Path(repo) / LANDING_PROSE
    if not prose.is_file():
        raise ValueError(f"{prose}: the landing page's prose is not there")
    # Where the landing kept its own copies before the texts served theirs. The
    # site root is never cleared, so a folder left here would go on being uploaded.
    shutil.rmtree(out / "static" / "covers", ignore_errors=True)
    groups: dict[Path, dict] = {}
    for root in published:
        ws = layout.workspace_root(root)
        assert ws is not None             # `build_site` refused any other
        read = tei_html.readable(root)
        collated = tei_html.collated(root)
        drafts = layout.publish(root) == "drafts"
        image = None
        if declared := layout.image(root):
            image = {"src": cover_url(root, layout.site_base(root), COVER_WIDTHS[0]),
                     "caption": declared["caption"]}
        groups.setdefault(ws, {"title": _workspace_title(ws), "texts": []})["texts"].append({
            "image": image,
            "url": layout.site_base(root) + "/",
            "work": stores.work(root),
            "collated": len(collated),
            "drafts": len(read) - len(collated) if drafts else 0,
        })
    text = prose.read_text(encoding="utf-8")
    # The site's address, where every published text's header agrees on one.
    origins = {stores.work(r)["origin"] for r in published} - {""}
    origin = origins.pop() if len(origins) == 1 else ""
    pictured = next((r for r in published if layout.image(r)), None)
    site_meta = {
        "description": meta.clip(meta.first_paragraph(text)),
        "canonical": f"{origin}/" if origin else "",
        "image": (f"{origin}{cover_url(pictured, layout.site_base(pictured), COVER_WIDTHS[-1])}"
                  if origin and pictured else ""),
        "image_alt": layout.image(pictured)["caption"] if pictured else "",
        "site_name": meta.SITE_NAME,
    }
    html = templates.env.get_template("site/index.html").render(
        prose=text, meta=site_meta,
        workspaces=[groups[ws] for ws in sorted(groups)])
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "404.html").write_text(templates.env.get_template("site/404.html").render(),
                                  encoding="utf-8")
    _sitemaps(out, published)
    (out / ".assetsignore").write_text(ASSETS_IGNORE, encoding="utf-8")
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
    # Before any text builds: a minute's crawl should not end in this.
    from .edition import cover_source

    for root in published:
        if (declared := layout.image(root)) and not cover_source(root).is_file():
            raise ValueError(f"{root}: `image` names {declared['fig']}, which has no crop: "
                             "`harness fig crops --all` builds them")

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
            shutil.copytree(STATIC, dest / "static", dirs_exist_ok=True)
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
