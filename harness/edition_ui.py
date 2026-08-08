"""The reading view — collated TEI, the encyclopedia, and the scan, in a browser.

**The first surface in this project aimed at a reader**, and the second thing it
is for is auditing, which is why both live in one page behind a toggle rather
than in two renderers that could drift.

The layout is two columns: the text, and a **stack** of cards beside it. A click
on an entity link, a footnote marker or the scan button pushes a card to the top
of the stack; the stack keeps what you have opened, in the order you opened it,
and a pinned card stays above the rest. That is the whole interaction, and it is
what makes an annotated edition readable at all — the alternative is a tooltip
that vanishes, or a footnote that costs you your place.

**It writes to `entities/`, and the click is the human act.** That is the
`zones edit` precedent, not a new licence: a loopback server, a tracked store, and
git as the witness. Ratifying an entry here is the same act as
`harness entity ratify --commit`, done where the evidence is — the entry beside
its attestations and the pages it was read from. Every write runs `entity check`
on the result first and refuses one that would leave the store incoherent.

Committed `tei/` only. `mz/tei/` is a generated baseline nobody has read, and an
end-user preview is the last place it belongs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import tei_html, webui
from .cli._entity import TEMPLATE
from .context import norm_ref
from .entities import check, load, path_for, split_id, trigger_index

PORT = 8734
REF_OK = re.compile(r"^\d+-\d+$")


def scan_for(ref: str, root: Path) -> Path:
    return root / "scans" / f"chukchi-{norm_ref(ref)}.png"


# --------------------------------------------------------------- the page

CSS = """
:root {
  --bg:#fbfaf7; --fg:#1c1a17; --dim:#6b6560; --rule:#ddd8d0; --card:#fff;
  --accent:#7a4b28; --mark:#b8860b; --pin:#1a6b5a;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#161513; --fg:#e6e2db; --dim:#948d84; --rule:#332f2a; --card:#1e1c19;
  --accent:#d99a63; --mark:#d4a63c; --pin:#5fbfa6;
} }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.65 Charter,Georgia,"Times New Roman",serif; }
a { color:var(--accent) }
#bar { position:sticky; top:0; z-index:9; display:flex; gap:.75rem;
  align-items:center; padding:.5rem .9rem; background:var(--bg);
  border-bottom:1px solid var(--rule); font-family:system-ui,sans-serif;
  font-size:.85rem; }
#bar .grow { flex:1 }
#bar a { text-decoration:none }
button, .btn { font:inherit; font-family:system-ui,sans-serif; font-size:.8rem;
  padding:.25rem .6rem; border:1px solid var(--rule); border-radius:.3rem;
  background:var(--card); color:var(--fg); cursor:pointer; }
button:hover { border-color:var(--accent) }
main.cols { display:flex; gap:1.5rem; align-items:flex-start;
  max-width:80rem; margin:0 auto; padding:1.2rem .9rem 4rem; }
.primary { flex:1 1 auto; min-width:0; max-width:44rem }
.secondary { flex:0 0 clamp(20rem,32%,26rem); position:sticky; top:3rem;
  max-height:calc(100vh - 4rem); overflow-y:auto; }
@media (max-width:880px) {
  main.cols { display:block }
  .secondary { position:static; max-height:none; margin-top:2rem;
    border-top:1px solid var(--rule); padding-top:1rem }
}
/* --- the text --- */
.primary p { margin:0 0 .35rem; text-indent:1.4rem }
.primary p:first-of-type { text-indent:0 }
blockquote { margin:.8rem 0 .8rem 1.5rem; color:var(--dim) }
h2.milestone { font-size:1.05rem; letter-spacing:.06em; text-transform:uppercase;
  margin:1.6rem 0 .6rem }
h3 { font-size:1rem; margin:1.2rem 0 .4rem }
table { border-collapse:collapse; margin:.8rem 0 }
td,th { border:1px solid var(--rule); padding:.2rem .5rem; text-align:left }
.folio { float:right; color:var(--dim); font-size:.75rem;
  font-family:system-ui,sans-serif; }
.tier1 { font-style:italic }
.unclear { border-bottom:1px dotted var(--mark) }
.supplied { color:var(--dim) }
.noteref { vertical-align:super; font-size:.7em; text-decoration:none;
  padding:0 .1em }
.ent { text-decoration:none; border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent) }
.ent:hover { border-bottom-color:var(--accent); background:color-mix(in srgb,var(--accent) 8%,transparent) }
.figure-anchor { color:var(--dim); font-size:.85em; cursor:pointer }
#foot { margin-top:2rem; padding-top:.8rem; border-top:1px solid var(--rule);
  font-size:.85rem; color:var(--dim) }
#foot li { margin-bottom:.3rem }
/* --- apparatus, hidden in reader view --- */
.flag { font-family:system-ui,sans-serif; font-size:.7rem; color:var(--mark);
  border:1px solid var(--mark); border-radius:.25rem; padding:0 .25em;
  cursor:help; margin:0 .15em; vertical-align:super }
.flag.question { background:color-mix(in srgb,var(--mark) 15%,transparent) }
.unsettled { background:color-mix(in srgb,var(--mark) 12%,transparent);
  border-bottom:1px dashed var(--mark) }
html.reader .flag { display:none }
html.reader .unsettled { background:none; border-bottom-style:solid }
/* --- the stack --- */
.card { background:var(--card); border:1px solid var(--rule);
  border-radius:.4rem; padding:.6rem .75rem; margin-bottom:.6rem;
  font-family:system-ui,sans-serif; font-size:.85rem; line-height:1.5 }
.card.pinned { border-color:var(--pin) }
.card h4 { margin:0 0 .3rem; font-size:.9rem; font-family:inherit }
.card .meta { color:var(--dim); font-size:.75rem; margin-bottom:.4rem }
.card .tools { float:right; display:flex; gap:.25rem }
.card .tools button { padding:.05rem .35rem; font-size:.7rem; line-height:1.4 }
.card .gloss { white-space:pre-wrap }
.card table { font-size:.75rem; margin:.4rem 0 0 }
.crop { position:relative; overflow:hidden; width:100%;
  border:1px solid var(--rule); border-radius:.3rem; margin-top:.4rem;
  background:var(--bg) }
.crop img { position:absolute; max-width:none }
html[data-theme="dark"] .crop img, .dark-raster .crop img { filter:none }
#empty { color:var(--dim); font-size:.85rem; font-family:system-ui,sans-serif }
.pill { display:inline-block; font-size:.7rem; padding:0 .35em; border-radius:.25rem;
  border:1px solid var(--rule); color:var(--dim); margin-left:.3rem }
.pill.proposed { border-color:var(--mark); color:var(--mark) }
"""

JS = r"""
const STACK = document.getElementById('stack');
const KEY = 'edition-pins-' + STATE.ref;

// Pins survive a reload because a pinned card is a deliberate act — you put it
// there to keep it while you read — and losing it to a refresh would teach you
// not to bother. Everything else is per-visit and deliberately not stored.
let pins = [];
try { pins = JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) {}

function savePins() {
  const ids = [...STACK.children].filter(c => c.classList.contains('pinned'))
                                 .map(c => c.dataset.id);
  localStorage.setItem(KEY, JSON.stringify(ids));
}

function empty() {
  const e = document.getElementById('empty');
  if (e) e.style.display = STACK.children.length ? 'none' : '';
}

/* A card already open is raised rather than duplicated: the stack is a set in
   most-recent order, not a log. Raising stops below the pinned block, so a pin
   actually holds its place. */
function push(id, build) {
  let card = STACK.querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (!card) { card = build(); card.dataset.id = id; }
  const firstLoose = [...STACK.children].find(c => !c.classList.contains('pinned'));
  if (card.classList.contains('pinned')) STACK.prepend(card);
  else STACK.insertBefore(card, firstLoose === card ? card.nextSibling : firstLoose);
  empty();
  card.scrollIntoView({block:'nearest'});
  return card;
}

function card(id, title, meta, html, extra) {
  const el = document.createElement('div');
  el.className = 'card';
  el.dataset.id = id;
  el.innerHTML = `<div class="tools">
      <button data-act="pin" title="keep this above the rest">pin</button>
      <button data-act="close" title="remove">×</button></div>
    <h4>${title}</h4>${meta ? `<div class="meta">${meta}</div>` : ''}${html}`;
  if (extra) extra(el);
  el.addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    if (b.dataset.act === 'close') { el.remove(); savePins(); empty(); }
    if (b.dataset.act === 'pin') {
      el.classList.toggle('pinned');
      b.textContent = el.classList.contains('pinned') ? 'unpin' : 'pin';
      if (el.classList.contains('pinned')) STACK.prepend(el);
      savePins();
    }
  });
  return el;
}

async function openEntity(ref) {
  const c = push('ent:' + ref, () => card('ent:' + ref, ref, 'loading…', ''));
  const r = await fetch('/entity/' + encodeURIComponent(ref) + '?partial=1');
  const h = await r.text();
  c.querySelector('h4').outerHTML = h;   // server sends <h4>…</h4> + body
  return c;
}

function openNote(i) {
  const src = document.getElementById('note-' + i);
  if (!src) return;
  push('note:' + i, () => card('note:' + i, 'Note ' + src.dataset.n, '',
                               `<div>${src.innerHTML}</div>`));
}

function openScan(box, label) {
  const id = 'scan:' + (box ? box.join(',') : 'page');
  push(id, () => card(id, label || 'The page', STATE.ref,
    `<div class="crop" style="${STATE.crops[id] ? STATE.crops[id].outer : 'aspect-ratio:'+STATE.size[0]+'/'+STATE.size[1]}">
       <img src="/page/${STATE.ref}.png" style="${STATE.crops[id] ? STATE.crops[id].inner : 'width:100%;left:0;top:0'}">
     </div>
     <div class="meta" style="margin-top:.4rem">
       <a href="/page/${STATE.ref}.png" target="_blank">open the full raster</a></div>`));
}

document.addEventListener('click', ev => {
  const a = ev.target.closest('a.ent');
  if (a) { ev.preventDefault(); openEntity(a.dataset.ref); return; }
  const n = ev.target.closest('a.noteref');
  if (n) { ev.preventDefault(); openNote(n.dataset.note); return; }
  const f = ev.target.closest('.figure-anchor');
  if (f) { openScan(null, 'Figure ' + f.dataset.figure); return; }
});

document.getElementById('scan-btn').addEventListener('click', () => openScan());

// Reader view: applied to <html> so it can be set before first paint (see the
// inline script in the head) and never flashes the apparatus on load.
document.getElementById('reader-btn').addEventListener('click', () => {
  const on = document.documentElement.classList.toggle('reader');
  localStorage.setItem('edition-reader', on ? '1' : '');
});

for (const id of pins) {
  if (id.startsWith('ent:')) openEntity(id.slice(4)).then(c => {
    c.classList.add('pinned');
    c.querySelector('[data-act=pin]').textContent = 'unpin';
    STACK.prepend(c);
  });
  else if (id.startsWith('note:')) openNote(id.slice(5));
}
empty();
"""


def _head(title: str, extra_css: str = "") -> str:
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title>"
        # Before the stylesheet, so a reader-view session does not flash its
        # apparatus on every page load. The Moll reader's lesson.
        "<script>try{if(localStorage.getItem('edition-reader'))"
        "document.documentElement.classList.add('reader')}catch(e){}</script>"
        f"<style>{CSS}{extra_css}</style>"
    )


def _bar(here: str = "") -> str:
    return (
        "<div id='bar'>"
        "<a href='/'><b>The Chukchee</b></a>"
        f"<span class='grow'>{here}</span>"
        "<a href='/entities'>encyclopedia</a>"
        "<form action='/search' style='display:inline'>"
        "<input name='q' placeholder='search' style='font:inherit;padding:.2rem .4rem;"
        "border:1px solid var(--rule);border-radius:.3rem;background:var(--card);"
        "color:var(--fg)'></form>"
        "</div>"
    )


def render_page(ref: str, root: Path) -> str:
    doc = tei_html.render(tei_html.page_path(ref, root))
    if not doc["ok"]:
        return (_head(ref) + _bar()
                + f"<main class='cols'><div class='primary'><p>This page will not "
                  f"render: {doc['why']}</p></div></main>")
    refs = collated_neighbours(ref, root)
    notes = "".join(
        f"<li id='note-{n['i']}' data-n='{n['n']}'><a href='#ref-{n['i']}'>"
        f"{n['n']}</a> {n['html']}</li>" for n in doc["notes"])
    size = _raster_size(ref, root)
    state = {"ref": ref, "size": size, "crops": {}}
    return (
        _head(f"{ref} — The Chukchee")
        + _bar(f"scan {ref}" + (f" · folio {doc['folio']}" if doc["folio"] else ""))
        + "<main class='cols'><div class='primary'>"
        + refs
        + f"<article>{doc['html']}</article>"
        + (f"<div id='foot'><ol>{notes}</ol></div>" if notes else "")
        + "</div><aside class='secondary'><div id='bar2' style='display:flex;"
          "gap:.4rem;margin-bottom:.6rem'>"
          "<button id='scan-btn'>consult the scan</button>"
          "<button id='reader-btn'>reader view</button></div>"
          "<div id='stack'></div>"
          "<div id='empty'>Click an entity, a footnote marker or "
          "<em>consult the scan</em>, and it collects here.</div>"
          "</aside></main>"
        + f"<script>const STATE={json.dumps(state)};</script><script>{JS}</script>"
    )


def collated_neighbours(ref: str, root: Path) -> str:
    """Previous/next among *collated* pages, which is what the reader can reach."""
    refs = tei_html.collated(root)
    if ref not in refs:
        return ""
    i = refs.index(ref)
    prev = f"<a href='/page/{refs[i-1]}'>← {refs[i-1]}</a>" if i else ""
    nxt = f"<a href='/page/{refs[i+1]}'>{refs[i+1]} →</a>" if i + 1 < len(refs) else ""
    return (f"<div style='display:flex;justify-content:space-between;"
            f"font-family:system-ui,sans-serif;font-size:.8rem;margin-bottom:1rem'>"
            f"<span>{prev}</span><span>{nxt}</span></div>")


def _raster_size(ref: str, root: Path) -> tuple[int, int]:
    """The scan's pixel size, or a plausible default if it is not on disk.

    `scans/` is derived and absent in a fresh clone, and the reading view should
    still render the text — the scan card simply has nothing to show. A default
    keeps the aspect ratio sane instead of collapsing the frame to zero.
    """
    try:
        from PIL import Image
        with Image.open(scan_for(ref, root)) as im:
            return im.size
    except Exception:
        return (2550, 3300)


# ------------------------------------------------------------- the entities

def entity_card(ent_id: str, root: Path, partial: bool) -> str:
    store = load(root)
    rec = store.get(ent_id)
    if rec is None:
        body = f"<p>No entry for <code>{ent_id}</code>.</p>"
        return body if partial else _head(ent_id) + _bar() + \
            f"<main class='cols'><div class='primary'>{body}</div></main>"
    idx = trigger_index(store)
    pill = (f"<span class='pill {rec['status']}'>{rec['status']}</span>")
    rows = "".join(
        f"<tr><td>{t['form']}</td><td>{'auto' if t['auto'] else 'suggest'}</td>"
        f"<td>{t['note']}</td></tr>" for t in rec["triggers"])
    contested = sorted({c["id"] for t in rec["triggers"]
                        for c in idx.get(t["form"], []) if c["id"] != ent_id})
    also = ("<div class='meta'>shares a form with "
            + ", ".join(f"<a class='ent' data-ref='{c}' href='/entity/{c}'>{c}</a>"
                        for c in contested) + "</div>") if contested else ""
    links = "".join(f"<div class='meta'>{ln}</div>" for ln in rec["links"])
    ratify = ("" if rec["status"] == "ratified" else
              f"<div style='margin-top:.5rem'><button onclick=\"ratify('{ent_id}')\">"
              f"ratify — a rule may then link its forms</button></div>")
    head = (f"<h4>{rec['canonical']}{pill}</h4>"
            f"<div class='meta'><code>{ent_id}</code> · first read on "
            f"<a href='/page/{rec['since']}'>{rec['since']}</a></div>")
    body = (f"{also}<div class='gloss'>{rec['gloss']}</div>{links}"
            + (f"<table><tr><th>form</th><th></th><th></th></tr>{rows}</table>"
               if rows else "")
            + ratify)
    if partial:
        return head + body
    return (_head(f"{rec['canonical']} — The Chukchee") + _bar()
            + f"<main class='cols'><div class='primary'><div class='card'>"
              f"{head}{body}</div></div></main>"
            + "<script>" + _RATIFY_JS + "</script>")


_RATIFY_JS = """
async function ratify(id) {
  const r = await fetch('/ratify', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})});
  const j = await r.json();
  if (j.error) { alert(j.error); return; }
  location.reload();
}
"""


def entity_index(root: Path) -> str:
    store = load(root)
    rep = check(root)
    rows = sorted(store.values(),
                  key=lambda r: (r["status"] != "proposed", r["id"]))
    trs = "".join(
        f"<tr><td><a href='/entity/{r['id']}'>{r['canonical']}</a></td>"
        f"<td><code>{r['id']}</code></td>"
        f"<td><span class='pill {r['status']}'>{r['status']}</span></td>"
        f"<td>{len(r['triggers'])}</td>"
        f"<td><a href='/page/{r['since']}'>{r['since']}</a></td></tr>"
        for r in rows)
    problems = "".join(f"<li>{e}</li>" for e in rep["errors"])
    return (
        _head("Encyclopedia — The Chukchee")
        + _bar(f"{rep['entities']} entries · {rep['proposed']} awaiting audit")
        + "<main class='cols'><div class='primary' style='max-width:60rem'>"
        + (f"<div class='card'><h4>the store does not check out</h4>"
           f"<ul>{problems}</ul></div>" if problems else "")
        + "<table style='width:100%'><tr><th>name</th><th>id</th><th>status</th>"
          "<th>triggers</th><th>since</th></tr>"
        + trs + "</table>"
        + "<p class='meta' style='font-family:system-ui,sans-serif;font-size:.8rem'>"
          "Proposed entries come first: nothing links them by rule until a human "
          "has read one against the page it was proposed from.</p>"
        + "</div></main>" + f"<script>{_RATIFY_JS}</script>")


def index(root: Path) -> str:
    refs = tei_html.collated(root)
    if not refs:
        body = ("<p>No page is collated yet. The reading view shows committed "
                "<code>tei/</code> only — a generated baseline in "
                "<code>mz/tei/</code> is a draft nobody has read, and this is "
                "the one place it must not appear.</p>")
    else:
        body = "<ul>" + "".join(
            f"<li><a href='/page/{r}'>{r}</a></li>" for r in refs) + "</ul>"
    return (_head("The Chukchee") + _bar(f"{len(refs)} page(s) collated")
            + f"<main class='cols'><div class='primary'><h3>The edition</h3>"
              f"{body}</div></main>")


def search(q: str, root: Path) -> str:
    """Text over committed pages, plus entity names and trigger forms.

    Two tables rather than one ranked list: a hit in the text and a hit in the
    encyclopedia answer different questions, and merging them would need a
    relevance score this has no basis for inventing.
    """
    hits, ents = [], []
    if q:
        store = load(root)
        for ident, rec in sorted(store.items()):
            hay = [rec["canonical"], ident, rec["gloss"]] + \
                  [t["form"] for t in rec["triggers"]]
            if any(q.lower() in h.lower() for h in hay):
                ents.append(rec)
        for ref in tei_html.collated(root):
            doc = tei_html.render(tei_html.page_path(ref, root))
            if not doc["ok"]:
                continue
            text = re.sub("<[^>]+>", "", doc["html"])
            for m in re.finditer(re.escape(q), text, re.I):
                a, b = max(0, m.start() - 60), m.end() + 60
                hits.append((ref, text[a:m.start()], m.group(), text[m.end():b]))
                if len(hits) > 200:
                    break
    rows = "".join(
        f"<tr><td><a href='/page/{r}'>{r}</a></td><td style='text-align:right'>"
        f"…{a}</td><td><mark>{m}</mark></td><td>{b}…</td></tr>"
        for r, a, m, b in hits)
    erows = "".join(
        f"<li><a href='/entity/{r['id']}'>{r['canonical']}</a> "
        f"<code>{r['id']}</code> <span class='pill {r['status']}'>{r['status']}"
        f"</span></li>" for r in ents)
    return (_head(f"{q} — search") + _bar(f"{len(hits)} in the text, "
                                          f"{len(ents)} in the encyclopedia")
            + "<main class='cols'><div class='primary' style='max-width:70rem'>"
            + (f"<h3>Encyclopedia</h3><ul>{erows}</ul>" if erows else "")
            + (f"<h3>The text</h3><table style='width:100%;font-size:.85rem'>"
               f"{rows}</table>" if rows else "")
            + ("" if hits or ents else "<p>Nothing found.</p>")
            + "</div></main>")


# ---------------------------------------------------------------- the server

def serve(root: Path = Path("."), port: int = PORT,
          open_browser: bool = True) -> None:
    class Handler(webui.EditorHandler):
        editor = "edition"

        def get(self) -> None:
            path, _, query = self.path.partition("?")
            args = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            from urllib.parse import unquote_plus
            args = {k: unquote_plus(v) for k, v in args.items()}

            if path == "/":
                return self.send_html(index(root))
            if path == "/entities":
                return self.send_html(entity_index(root))
            if path == "/search":
                return self.send_html(search(args.get("q", ""), root))
            if path.startswith("/entity/"):
                ident = unquote_plus(path[len("/entity/"):])
                try:
                    split_id(ident)
                except ValueError as e:
                    return self.send_html(f"<p>{e}</p>", 400)
                return self.send_html(
                    entity_card(ident, root, partial="partial" in args))
            if path.startswith("/page/"):
                ref = path[len("/page/"):]
                png = ref.endswith(".png")
                ref = ref[:-4] if png else ref
                # The traversal guard, in the shape `zones_ui` uses: the ref is
                # matched against its own form rather than sanitized, so nothing
                # depends on having thought of every escape.
                if not REF_OK.match(ref):
                    return self.send_error(404)
                if png:
                    return self.send_png(scan_for(ref, root),
                                         f"no raster for {ref} — scans/ is "
                                         f"derived and not in git")
                if not tei_html.page_path(ref, root).exists():
                    return self.send_html(
                        _head(ref) + _bar()
                        + f"<main class='cols'><div class='primary'><p>{ref} is "
                          f"not collated. The reading view shows committed "
                          f"<code>tei/</code> only.</p></div></main>", 404)
                return self.send_html(render_page(ref, root))
            self.send_error(404)

        def post(self) -> None:
            if self.path == "/stop":
                self.send_json({"ok": True})
                return self.stop_from_page()
            body = self.body_json()
            if self.path == "/ratify":
                return self.send_json(_ratify(body.get("id", ""), root))
            if self.path == "/entity/new":
                return self.send_json(_new(body, root))
            self.send_error(404)

    webui.run(Handler, port, f"http://127.0.0.1:{port}/",
              [f"edition: http://127.0.0.1:{port}/",
               f"  {len(tei_html.collated(root))} page(s) collated, "
               f"{len(load(root))} entities",
               "  ctrl-c to stop"],
              open_browser=open_browser)


def _guarded(root: Path, write) -> dict:
    """Run a write, then refuse it if the store no longer checks out.

    The browser is a human acting, not a pass proposing, so it does not need
    `--commit` — the click is the act, and git is the witness. What it does need
    is to be unable to leave the store in a state `entity check` rejects, because
    every `@ref` in the corpus resolves against it and a broken store breaks
    pages nobody is looking at.
    """
    undo = write()
    rep = check(root)
    if not rep["ok"]:
        undo()
        return {"error": "refused — the store would not check out: "
                         + "; ".join(rep["errors"][:3])}
    return {"ok": True}


def _ratify(ent_id: str, root: Path) -> dict:
    try:
        split_id(ent_id)
    except ValueError as e:
        return {"error": str(e)}
    p = path_for(ent_id, root)
    if not p.exists():
        return {"error": f"no entry at {p}"}
    before = p.read_text(encoding="utf-8")
    if "- status: proposed" not in before:
        return {"error": "not a proposed entry"}

    def write():
        p.write_text(before.replace("- status: proposed", "- status: ratified", 1),
                     encoding="utf-8")
        return lambda: p.write_text(before, encoding="utf-8")

    return _guarded(root, write)


def _new(body: dict, root: Path) -> dict:
    ident = (body.get("id") or "").strip()
    try:
        split_id(ident)
    except ValueError as e:
        return {"error": str(e)}
    p = path_for(ident, root)
    if p.exists():
        return {"error": f"{ident} already exists"}
    rows = "\n".join(f"| {t.strip()} | no | |"
                     for t in (body.get("triggers") or []) if t.strip())
    text = TEMPLATE.format(ident=ident, canonical=body.get("canonical") or ident,
                           since=body.get("since") or "",
                           rows=rows or "| | no | |")

    def write():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return lambda: p.unlink(missing_ok=True)

    return _guarded(root, write)
