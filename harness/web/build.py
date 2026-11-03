"""`edition build` — the reading view written to disk as a static site.

**The build is the served output, not a second renderer.** It drives the same
router `edition serve` mounts, through a `TestClient`, and writes each response
where a static host will find it. A renderer of its own would be a second answer
to "what does this page look like", free to drift from the first.

**It crawls from `/`; the stores do not seed it.** Every page a reader can reach
is reached by following what the pages themselves link to — the hrefs, and the
URLs the scripts build out of `data-` attributes, which this file states rule by
rule in `_derived`. The stores are read only afterwards, to ask what was *not*
reached: an entity, an annotation or a run that exists and that nothing links to
is an orphan, and a site seeded from the stores would publish it and hide that
nobody can find it. **The one thing the stores add is the retired addresses**
(`_retired`), and they are not pages: each is fetched only to be written as the
stub that forwards from it, and refused if it answers with anything else.

What gates — exit 1, one row each:

  * a URL the pages link to that answers with no page (a 404 that is not a
    refusal page, a 400, a query string a host cannot serve);
  * two URLs that would land on one file — compared case-folded **only where
    the disk being written to folds case**. The lexicon's handle keys tell
    `Ke'let` from `KE'LET` on purpose, and the hosts a site goes to are
    case-sensitive; what a folding disk does is overwrite one with the other in
    silence, and that is the case worth refusing;
  * an orphan.

A 3xx is written as a stub that forwards, fragment and all. A locator's refusal
(`/folio/N` that no witness places) is an HTML page answered with 404 or 300,
and is the ordinary answer there: it is written as the page it is.

Deterministic by construction — the crawl is breadth-first over sorted links, and
nothing written carries a time — so two builds of one tree are byte-identical,
which is what lets a later refactor be checked by rebuilding and diffing.
"""
from __future__ import annotations

import json
import multiprocessing
import shutil
import tempfile
import threading
from collections import deque
from collections.abc import Set as AbstractSet
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from html import escape
from itertools import chain
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote, unquote, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from lxml import html as LH

from .. import apparatus, chapters, parallel
from ..state import load_toc
from . import STATIC, cache, stores

#: What marks a directory as a build's own to clear. Fixed text, so two builds of
#: one tree are still the same bytes.
OUT_MARK = ".edition-build"

#: What `encodeURIComponent` leaves alone beyond what `quote` always does, so a
#: URL derived here is the one the script builds, character for character.
_JS_SAFE = "!~*'()"



def norm_base(base: str) -> str:
    """`/bogoras/` → `/bogoras`, `/` → `` — a prefix every path is appended to."""
    b = "/" + base.strip("/")
    return "" if b == "/" else b


def site_app(root: Path, base: str, drafts: bool = False,
             home: str | None = None) -> FastAPI:
    """The reading view alone, mounted at `base`, rendering for a static host.

    Not `create_app`: that is one server for four tools, and its port middleware
    reads the first path segment as an editor's name. A site has one tool and
    may sit at the host's root. `home` is the landing page above this text, where
    there is one (`web/site.py`); a site built alone has nothing above it to link.
    """
    from . import edition

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.root = Path(root)
    app.state.base = base
    app.state.assets = f"{base}/static"
    app.state.static = True
    app.state.drafts = drafts
    app.state.home = home
    app.include_router(edition.router, prefix=base)
    return app


@dataclass
class Site:
    """What a build wrote and what it refused, keyed by URL path."""

    out: Path
    base: str
    #: URL path → the file written for it, relative to `out`.
    files: dict[str, str] = field(default_factory=dict)
    #: URL path → the pages that link to it, for a row to name its referrer.
    linked_from: dict[str, set[str]] = field(default_factory=dict)
    rows: list[dict] = field(default_factory=list)
    #: `parallel.worker_output` of a pooled build: what its workers wrote to
    #: stderr, which a pool must not let reach the terminal while it draws.
    worker_log: dict = field(default_factory=dict)

    def refuse(self, url: str, why: str) -> None:
        self.rows.append({"url": url, "why": why,
                          "from": sorted(self.linked_from.get(url, ()))[:3]})


def _enc(s: str) -> str:
    return quote(s, safe=_JS_SAFE)


def _derived(tree, base: str) -> list[str]:
    """The URLs the scripts build out of a page, rule by rule.

    Each rule is the script's own, restated: a change to one of them has to land
    here too or the gate reports the URL the script now asks for as missing,
    which is the direction a drift should fail in.
    """
    out = []
    for el in tree.iter():
        a = el.attrib
        cls = f" {a.get('class', '')} "
        if "data-ref" in a:
            # `edition.js` `urlFor`, `edition.js` `openEntity`, `map.js` `click`.
            out.append(f"{base}/partial/entity/{_enc(a['data-ref'])}")
        if "data-atlas" in a:                                   # `map.js` `paint`
            out.append(a["data-atlas"])
        if " lex " in cls and "data-key" in a:
            out.append(f"{base}/partial/lexicon/{_enc(a['data-key'])}")
        if "data-ent" in a and a["data-ent"]:
            out.append(f"{base}/partial/entity/{_enc(a['data-ent'])}")   # `map.js` `warm`
        if " warm " in cls and "data-warm" in a:
            out += [f"{base}/partial/entity/{_enc(i)}" for i in a["data-warm"].split()]
        if "data-fig" in a:                                     # `edition.js` `openFigure`
            out += [f"{base}/fig/{p}.png" for p in a["data-fig"].split(",") if p]
        if "data-ipa" in a:                                     # `edition.js`
            out.append(f"{base}/tts/{_enc(a['data-ipa'])}.wav")
        if "data-full" in a:                                    # the lightbox
            out.append(a["data-full"])
        if "data-lightbox" in a:                                # `edition.js`, the same
            out.append(a["data-lightbox"])
        if "data-lightbox-under" in a:
            out.append(a["data-lightbox-under"])
        if "data-modal" in a:                                   # `edition.js` `openModal`
            out.append(a["data-modal"])
        if "data-scan" in a:                                    # `edition.js` `openScan`
            out.append(f"{base}/page/{a['data-scan']}.png")
    return out


def _shapes(atlas: dict, base: str) -> list[str]:
    """Every shape `geomap.js` can ask for: the coastline and lakes the store
    has, and each shape an entity names or draws beneath it. Kin and a holder's
    outline are some other entity's own shapes, so they are in here already."""
    sids = set(atlas["base"])
    for e in atlas["entities"].values():
        sids.update(e["shapes"])
        sids.update(sid for _ent, sid in e["members"])
    return [f"{base}/geo/shape/{_enc(s)}.json" for s in sids]


def _links(text: str, base: str) -> list[str]:
    tree = LH.fromstring(text)
    found = [link for _el, _attr, link, _pos in tree.iterlinks()]
    return found + _derived(tree, base)


def _canon(path: str) -> str:
    """One spelling per path. The renderer quotes with Python's `quote` and the
    scripts with `encodeURIComponent`, which differ on `'` and four others; the
    host decodes both to one file, so they are one URL here too."""
    p, q, query = path.partition("?")
    return quote(unquote(p), safe="/") + q + query


def _internal(link: str, base: str) -> str | None:
    """The path a link names on this site, or None for one that leaves it."""
    parts = urlsplit(link)
    if parts.scheme or parts.netloc or not parts.path.startswith("/"):
        return None
    if base and not (parts.path == base or parts.path.startswith(base + "/")):
        return None
    return _canon(parts.path + (f"?{parts.query}" if parts.query else ""))


def _disk(path: str, base: str, html: bool) -> str:
    """Where a URL path is written: a page becomes `index.html` in a directory
    of its own name, so `/leaf/1-361` and `/leaf/1-361/colour.jpg` could both be
    pages and files at once; anything else keeps its name."""
    rel = unquote(path)[len(base):].lstrip("/")
    if html:
        return (rel.rstrip("/") + "/index.html").lstrip("/")
    return rel


def _stub(target: str) -> str:
    """A redirect a static host can serve. The target's own fragment wins, as it
    does on a 302; where it has none, the one the reader arrived with survives."""
    t = escape(target, quote=True)
    return ("<!doctype html>\n<meta charset='utf-8'>\n<title>Redirecting</title>\n"
            f"<meta http-equiv='refresh' content='0; url={t}'>\n"
            f"<link rel='canonical' href='{t}'>\n"
            f"<script>const t = {json.dumps(target)};\n"
            "location.replace(t.includes('#') ? t : t + location.hash);</script>\n"
            f"<p><a href='{t}'>{t}</a></p>\n")


def _folds(d: Path) -> bool:
    """Whether the filesystem under `d` treats `A` and `a` as one name."""
    probe = d / ".Case-Probe"
    probe.write_text("")
    try:
        return (d / ".case-probe").exists()
    finally:
        probe.unlink()


def _expected(root: Path, base: str) -> set[str]:
    """What the stores say exists and a reader should be able to reach, as the
    URL each is served at. The orphan check is against this."""
    from . import edition

    out = {f"{base}/", f"{base}/atlas", f"{base}/entities",
           f"{base}/annotations", f"{base}/lexicon"}
    out |= {base + apparatus.run_url(r) for r in stores.runs(root) if r.get("id")}
    out |= {f"{base}/entity/{_enc(i)}" for i in stores.load(root)}
    out |= {f"{base}/annotation/{_enc(i)}" for i in stores.annotations(root)}
    # Addressed as the lexicon index addresses them: the key, else the form.
    out |= {f"{base}/lexicon/{_enc(r['key'] or r['form'])}"
            for r in edition._forms(root)}
    return {_canon(u) for u in out}


def _retired(root: Path, base: str) -> set[str]:
    """Addresses a page was once served at and now forwards from, each of which
    the build must write as a stub — **must**, because nothing links to them any
    more, so the crawl alone would never reach them and a published link would
    404.

    This is not the stores seeding the crawl. That rule is against publishing a
    *page* nobody can reach, which would hide that it is an orphan; a retired
    address is not a page, and is fetched only to be refused unless it forwards.

    A chapter's: `/run/{id}`, its address before it had a name, and
    `/chapter/{ROMAN}`, which forwarded there. And `/chapter/{roman}`, the
    chapter by number, which no page links either. Only a derived chapter's,
    since those are the ones that were pages; an underived chapter's roman
    answers as it always did, and the chaprefs still reach it.

    **A disk that folds case cannot hold both romans**, and the build refuses
    the second as it refuses any two addresses landing on one file. The hosts
    a site goes to are case-sensitive.
    """
    by_id = {e.get("id"): e for e in load_toc(root)}
    out = set()
    for r in stores.runs(root):
        if r.get("kind") != chapters.KIND:
            continue
        out.add(f"{base}/run/{r['id']}")
        roman = (by_id.get(r.get("toc_id")) or {}).get("chapter")
        if roman:
            out |= {f"{base}/chapter/{roman}", f"{base}/chapter/{roman.lower()}"}
    return {_canon(u) for u in out}


class _Fetched(NamedTuple):
    """One response, reduced to what the crawl acts on. Plain data, so a worker
    process can hand it back."""

    html: bool
    ctype: str
    body: bytes
    links: list[str]
    #: Why the crawl refuses this URL, or "" for a response it writes.
    refused: str = ""
    #: The response was a 3xx, and `body` is the stub that forwards.
    redirect: bool = False


def _fetch(client: TestClient, url: str, base: str) -> _Fetched:
    """Ask the router for one URL. Everything here is a function of the URL and
    the snapshot, which is what lets it run in any process in any order."""
    r = client.get(url, follow_redirects=False)
    ctype = r.headers.get("content-type", "")
    html = ctype.startswith("text/html")
    if r.is_redirect:
        target = r.headers["location"]
        return _Fetched(True, ctype, _stub(target).encode(), [target], redirect=True)
    if r.status_code == 200 or (html and r.status_code in (300, 404)):
        links = (_links(r.text, base) if html
                 else _shapes(r.json(), base) if url == f"{base}/geo/atlas.json"
                 else [])
        return _Fetched(html, ctype, r.content, links)
    return _Fetched(html, ctype, b"", [],
                    f"HTTP {r.status_code}: {r.text.strip()[:160]}")


def _clearable(root: Path, out: Path) -> None:
    """Refuse an `out` this build did not write, before anything is deleted.

    **The mark and not a guess at what a site looks like**: `static/` and an
    `index.html` are what any web project holds, and `gt/` holds neither and is
    just as lost. Absent or empty is fine, and so is an earlier build, however
    far it got, since the mark goes down first.
    """
    if out.resolve() == Path(root).resolve() or out.resolve() in Path(root).resolve().parents:
        raise ValueError(f"{out} holds the text's own stores: refusing to clear it. "
                         "Name a directory of its own for the site")
    if (out.exists() and any(out.iterdir()) and not (out / OUT_MARK).is_file()):
        raise ValueError(f"{out} is not empty and holds no {OUT_MARK}, so no build "
                         "wrote it: refusing to clear it. Name a directory of its "
                         "own, or delete this one yourself if it is an older site")


def build(root: Path, out: Path, base: str = "", drafts: bool = False,
          jobs: int | None = 1, tick=None, home: str | None = None) -> Site:
    """Write the site under `out` and say what failed. `out` is cleared first:
    a file left over from an earlier build would be served as though this one
    had written it. `_clearable` says what may be cleared. `jobs=None` sizes the
    pool to the cores, as `--jobs` does when it is not given; the default here is
    the serial crawl."""
    base = norm_base(base)
    out = Path(out)
    _clearable(root, out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / OUT_MARK).write_text("written by `harness edition build`, which clears "
                                "this directory\n", encoding="utf-8")
    fold = str.casefold if _folds(out) else str
    shutil.copytree(STATIC, out / "static")
    site = Site(out=out, base=base)
    # One snapshot of the stores for the whole crawl: `cache.frozen`'s contract.
    with cache.frozen():
        n = parallel.cpu_workers(jobs, MAX_LEVEL)
        retired = _retired(root, base)
        if n == 1:
            # The control arm: no pool at all, one client, today's crawl.
            with TestClient(site_app(root, base, drafts, home)) as client:
                seen = _crawl(lambda urls: (_fetch(client, u, base) for u in urls),
                              site, fold, tick, retired)
        else:
            seen = _pooled(root, base, drafts, home, n, site, fold, tick, retired)
        # Not reached, as distinct from reached and refused: that row is written.
        for url in sorted(_expected(root, base) - seen):
            site.refuse(url, "nothing links to it")
    return site


# ------------------------------------------------------------------ the pool
#
# **Processes, because the work is the renderer's own Python**: jinja, lxml and
# the stores' joins, none of which lets go of the GIL for long. **Byte-identical
# by construction**: the crawl goes a breadth-first level at a time, each level's
# URLs go out in queue order, and the parent takes the answers back in that same
# order and does everything that touches `seen` itself. A FIFO queue finishes
# level L before it starts L+1 anyway, so the parent follows, refuses and writes
# in exactly the serial crawl's sequence; only who rendered each page differs.
#
# **Forked after warming, so no worker pays the warm-up.** The corpus-wide joins
# cost ~15 s on the first request that needs them (`occurrences` 4.7 s, `native`
# 3.8 s, `midline` 3.6 s, …), per process. Built once in the parent and inherited
# copy-on-write, they are paid once. Fork is only safe in a process with one
# thread, so the parent warms through `stores` directly rather than through a
# client — whose portal is a thread — and falls back to a cold `forkserver` pool
# if anything else has started one.
#
# **The workers' client is unentered.** An entered `TestClient` keeps a portal
# thread alive, and a pool worker joins its threads on the way out, which is a
# shutdown that never comes; an unentered one opens a portal per request, which
# measured as noise.

#: `cpu_workers` sizes against the work, and a level's size is not known until
#: the crawl reaches it; the cores and `MAX_WORKERS` are the real bound.
MAX_LEVEL = 1 << 20

_WORKER: tuple | None = None


def _warm(root: Path) -> None:
    """Build the corpus-wide caches in this process, before it forks.

    Only an optimisation: every one of them is keyed on contents, so one left
    off this list is built by the first worker that needs it, and one that fails
    here fails again, with its own traceback, on the request that needs it."""
    for fn in (stores.load, stores.annotations, stores.lexicon_store, stores.runs,
               stores.heads, stores.folio_index, stores.folio_by_ref,
               stores.heading_urls, stores.midline, stores.native,
               stores.occurrences, stores.atlas, stores.readable,
               stores.collated, stores.exempt, stores.leaf_kinds):
        try:
            fn(root)
        except Exception:      # noqa: BLE001 — see the docstring; not swallowed
            pass


def _worker_init(root: str, base: str, drafts: bool, home: str | None,
                 log_dir: str) -> None:
    global _WORKER
    parallel.capture_stderr(log_dir)
    # Joins the snapshot a fork inherited; starts one in a `forkserver` worker.
    snapshot = cache.frozen()
    snapshot.__enter__()
    _WORKER = (TestClient(site_app(Path(root), base, drafts, home)), base, snapshot)


def _work(urls: list[str]) -> list[_Fetched]:
    assert _WORKER is not None
    client, base, _ = _WORKER
    return [_fetch(client, u, base) for u in urls]


def _pooled(root: Path, base: str, drafts: bool, home: str | None, n: int, site: Site,
            fold, tick, retired: AbstractSet[str] = frozenset()) -> set[str]:
    _warm(Path(root))
    method = "fork" if threading.active_count() == 1 else "forkserver"
    log_dir = tempfile.mkdtemp(prefix="edition-build-")
    with ProcessPoolExecutor(n, mp_context=multiprocessing.get_context(method),
                             initializer=_worker_init,
                             initargs=(str(root), base, drafts, home, log_dir)) as pool:
        def fetch(urls: list[str]):
            # Chunks several times the worker count, so a slow page does not
            # own a level's tail; `buffersize` bounds the bodies held unread.
            size = max(1, min(32, len(urls) // (n * 4)))
            chunks = [urls[i:i + size] for i in range(0, len(urls), size)]
            return chain.from_iterable(pool.map(_work, chunks, buffersize=2 * n))
        seen = _crawl(fetch, site, fold, tick, retired)
    site.worker_log = parallel.worker_output(log_dir)
    return seen


def _crawl(fetch, site: Site, fold, tick,
           retired: AbstractSet[str] = frozenset()) -> set[str]:
    """Breadth-first from the index over sorted links, writing as it goes.
    `fetch` maps a level's URLs to their `_Fetched`, lazily and in order.
    Returns every URL it reached.

    `retired` (`_retired`) is fetched once the links run out, those the crawl
    did not already reach, as one more level; each, reached or not, must
    forward, and one that answers with a page is refused."""
    out, base = site.out, site.base
    assets = f"{base}/static/"

    start = f"{base}/"
    queue, seen = deque([start]), {start}
    by_disk: dict[str, str] = {}

    def follow(src: str, links) -> None:
        for link in sorted(set(links)):
            path = _internal(link, base)
            if path is None:
                continue
            site.linked_from.setdefault(path, set()).add(src)
            if path.startswith(assets):
                if not (out / unquote(path)[len(base):].lstrip("/")).is_file():
                    if path not in seen:
                        seen.add(path)
                        site.refuse(path, "no such static file")
                continue
            if path not in seen:
                seen.add(path)
                queue.append(path)

    done = 0
    late = sorted(retired)
    while True:
        while queue:
            level = list(queue)
            queue.clear()
            fetched = iter(fetch([u for u in level if "?" not in u]))
            for url in level:
                done += 1
                if tick:
                    tick(url, done, len(seen))
                if "?" in url:
                    site.refuse(url, "a query string, which a static host ignores")
                    continue
                f = next(fetched)
                if f.refused:
                    site.refuse(url, f.refused)
                    continue
                if url in retired and not f.redirect:
                    site.refuse(url, "a retired address, which must forward, "
                                     "answers with a page")
                    continue
                follow(url, f.links)
                _write(site, url, f, by_disk, fold)
        unreached = [u for u in late if u not in seen]
        late = []
        if not unreached:
            return seen
        seen.update(unreached)
        queue.extend(unreached)


def _write(site: Site, url: str, f: _Fetched, by_disk: dict[str, str], fold) -> None:
    rel = _disk(url, site.base, f.html)
    if not f.html and not Path(rel).suffix:
        site.refuse(url, f"{f.ctype} at an address with no extension")
        return
    clash = by_disk.get(fold(rel))
    if clash is not None:
        site.refuse(url, f"lands on {rel}, which {clash} already holds")
        return
    by_disk[fold(rel)] = url
    dest = site.out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(f.body)
    site.files[url] = rel
