"""The line-correction editor: `harness ocr edit`.

`zones edit`'s sibling, one stage down. That editor partitions a page into
regions; this one finds the lines a segmenter dropped *inside* those regions and
gives them a box, so that a reader or the review pass has something to point at.

**It draws and never keys.** The text of a recovered line is adjudicated in `ocr
review` like any other line's and written by `restore` — duplicating that
machinery here would be a second place a reading could be originated, and the
whole store exists on the argument that this writer cannot originate one. What a
human does here is say *there is a line here*, or *that ink is not a line*.

**Two verdicts, one sitting.** A `gaps` band is either a line the segmenter
missed or something that is not type at all — a printed rule, a footnote
separator, a smudge the zoning happens to cover. Both are recorded from the same
view of the same page, because deciding between them is one act and splitting it
across two tools is how bands get left unruled.

**A box in no zone is refused, loudly.** Ink that no region covers is a defect in
the *zoning*, not a line this editor can adopt: it means the segmentation missed
a region, and the honest response is to say so and send the human to `zones edit`
rather than to quietly paper over it one line at a time. That refusal is also
what keeps the two ink checks disjoint — see `harness/corrections.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import corrections as corr
from . import webui
from . import zones as zn
from .context import norm_ref
from .lines import DEFAULT_ALTO_DIR, alto_for_lines, line_gaps, page_lines

PORT = 8733

# Where the blotted view is rendered for the toggle. Under `scans/`, which is
# ignored whole, and per-editor rather than sharing `scans/w-blotted/`: that
# directory is the corpus sweep's output and is deliberately painted *without*
# exemptions, so writing this variant into it would corrupt the one view that
# answers independently of anybody's rulings.
BLOT_CACHE = "w-blotted-edit"


def page_state(ref: str, root: Path = Path("."),
               alto_dir: str = DEFAULT_ALTO_DIR) -> dict:
    """Everything the page needs, resolved server-side.

    The client re-derives nothing: it is handed raster-space geometry for every
    layer and draws it. Same rule as the zones editor, and for the same reason —
    a browser that recomputed which store answers, or which layer settles a band,
    could disagree with the server about what it is showing.
    """
    ref = norm_ref(ref)
    w, h = zn.raster_size(ref, root)
    alto = alto_for_lines(ref, alto_dir, root)

    lines, corrected = [], []
    if alto.exists():
        # Raster space, so every layer on the page shares one coordinate system.
        page = None
        from lxml import etree
        page = etree.parse(str(alto)).find(".//{*}Page")
        aw = float(page.get("WIDTH") or w) if page is not None else w
        ah = float(page.get("HEIGHT") or h) if page is not None else h
        sx, sy = (w / aw if aw else 1.0), (h / ah if ah else 1.0)
        for r in page_lines(alto, root, ref=ref):
            if r.get("hpos") is None or r.get("vpos") is None:
                continue
            box = {"x0": round(r["hpos"] * sx), "y0": round(r["vpos"] * sy),
                   "x1": round((r["hpos"] + r["width"]) * sx),
                   "y1": round((r["vpos"] + r["height"]) * sy),
                   "index": r["index"], "zone": r["zone"]}
            (corrected if r["src"] == "corr" else lines).append(box)

    # The fragment is the authority on a correction's geometry — `page_lines`
    # scales into the ALTO's space and back would lose a pixel either way.
    stored = {c["id"]: c for c in corr.load_lines(ref, root)}
    for box, rec in zip(corrected, sorted(stored.values(),
                                          key=lambda r: (r["y0"], r["x0"])),
                        strict=False):
        box.update({k: rec[k] for k in ("id", "x0", "y0", "x1", "y1", "text")})

    zones = zn.read_zones(ref, root)
    bands = line_gaps(ref, alto_dir, root) if alto.exists() else []
    return {
        "ref": ref, "w": w, "h": h,
        "has_zones": zn.has_zones(ref, root),
        "lines": lines,
        "corr": corrected,
        "zones": [{"label": z["label"], "x0": z["x0"], "y0": z["y0"],
                   "x1": z["x1"], "y1": z["y1"]} for z in zones],
        "bands": bands,
        # Both layers travel to the client: this editor writes only the line
        # layer, but a human ruling a band needs to see that the zoning side has
        # already spoken about that strip of paper.
        "line_exempt": corr.load_ink_exempt(root).get(ref, []),
        "zone_exempt": zn.load_ink_exempt(root).get(ref, []),
    }


def _zone_of(box: dict, zones: list[dict]) -> str:
    from .lines import _band_zone
    return _band_zone({"hpos": box["x0"], "vpos": box["y0"],
                       "width": box["x1"] - box["x0"],
                       "height": box["y1"] - box["y0"]}, zones)


def save_payload(payload: dict, root: Path = Path("."),
                 alto_dir: str = DEFAULT_ALTO_DIR) -> dict:
    """Write one page's corrections and its line-level rulings.

    Both stores or neither: they are two halves of one sitting, and a save that
    landed one would leave the page in a state no single view describes.

    **Refuses a box in no zone before writing anything.** The message names the
    zone editor because that is where the fault actually is — a line this editor
    cannot place is ink the *zoning* does not cover, and adopting it here would
    record a line inside no region while leaving the region missing.
    """
    ref = norm_ref(payload.get("ref") or "")
    boxes = payload.get("lines") or []
    if not zn.has_zones(ref, root):
        raise ValueError(
            f"{ref} has no zoning. Line correction comes after it: this editor "
            "finds lines dropped *inside* declared regions, and with no regions "
            f"there is nothing to be inside. Key it in `harness zones edit {ref}`")

    zones = zn.read_zones(ref, root)
    stray = [b for b in boxes if not _zone_of(b, zones)]
    if stray:
        where = ", ".join(f"y={b['y0']}-{b['y1']}" for b in stray[:6])
        raise ValueError(
            f"{ref}: {len(stray)} box(es) lie in no zone ({where}). That is a "
            "defect in the zoning, not a line this editor can adopt — ink no "
            "region covers means the segmentation missed a region, and recording "
            "a line inside no region would leave the region missing. Draw the "
            f"zone in `harness zones edit {ref}` first, or rule the band not type "
            "if it is not printing.")

    res = corr.save_lines(ref, boxes, root)
    corr.set_ink_exempt(ref, payload.get("ink_exempt") or [], root)
    # Re-measured after the write, so the page reports what is *left* rather than
    # what the client believed before it saved — and through the same store the
    # page was opened against, or a `--store gt` session would save and then
    # report a tally measured somewhere else.
    bands = line_gaps(ref, alto_dir, root)
    return {**res,
            "live_bands": [b for b in bands if not b["exempted"]],
            "bands": len(bands)}


JS = r"""
const S = STATE;
let corr = S.corr.map(c => ({...c})), exempt = S.line_exempt.map(e => ({...e}));
let sel = null, dirty = false, blot = false, drag = null;

const $ = s => document.querySelector(s);
const stage = $('#stage'), ov = $('#ov'), img = $('#img');

function fit() {
  // The stage is a window onto the page; width follows the viewport so the
  // whole measure is legible without horizontal scrolling.
  const w = Math.min(window.innerWidth - 290, 1100);
  stage.style.width = w + 'px';
  stage.style.height = (w * S.h / S.w) + 'px';
  img.style.width = w + 'px';
  ov.setAttribute('viewBox', `0 0 ${S.w} ${S.h}`);
}

function at(e) {
  const r = ov.getBoundingClientRect();
  return {x: Math.round((e.clientX - r.left) / r.width * S.w),
          y: Math.round((e.clientY - r.top) / r.height * S.h)};
}

function inZone(b) {
  // Mirrors the server's rule so the refusal is visible before the save, never
  // instead of it: the server refuses again regardless.
  let best = 0;
  const area = Math.max(1, (b.x1 - b.x0) * (b.y1 - b.y0));
  for (const z of S.zones) {
    const ox = Math.max(0, Math.min(b.x1, z.x1) - Math.max(b.x0, z.x0));
    const oy = Math.max(0, Math.min(b.y1, z.y1) - Math.max(b.y0, z.y0));
    best = Math.max(best, ox * oy / area);
  }
  return best >= 0.5;
}

function rect(b, cls, title) {
  return `<rect x="${b.x0}" y="${b.y0}" width="${b.x1 - b.x0}" `
       + `height="${b.y1 - b.y0}" class="${cls}">`
       + (title ? `<title>${title}</title>` : '') + '</rect>';
}

function draw() {
  let s = '';
  for (const z of S.zones) s += rect(z, 'z', z.label);
  for (const l of S.lines) s += rect(l, 'l');
  for (const e of S.zone_exempt)
    s += `<rect x="0" y="${e.y0}" width="${S.w}" height="${e.y1 - e.y0}" `
       + `class="xz"><title>zone layer: ${e.note}</title></rect>`;
  for (const e of exempt)
    s += `<rect x="0" y="${e.y0}" width="${S.w}" height="${e.y1 - e.y0}" `
       + `class="xl"><title>not type: ${e.note}</title></rect>`;
  for (const b of S.bands) {
    if (b.exempted) continue;
    if (corr.some(c => c.y0 < b.vpos + b.height && b.vpos < c.y1)) continue;
    s += `<rect x="${b.hpos}" y="${b.vpos}" width="${b.width}" `
       + `height="${b.height}" class="b${b.zone ? '' : ' nz'}" `
       + `data-v="${b.vpos}"><title>${b.zone || 'in no zone'}</title></rect>`;
  }
  corr.forEach((c, i) => {
    s += `<rect x="${c.x0}" y="${c.y0}" width="${c.x1 - c.x0}" `
       + `height="${c.y1 - c.y0}" class="c${i === sel ? ' sel' : ''}`
       + `${inZone(c) ? '' : ' nz'}" data-i="${i}"></rect>`;
  });
  if (drag) s += rect(drag, 'drag');
  ov.innerHTML = s;
  $('#nc').textContent = corr.length;
  $('#nb').textContent = S.bands.filter(b => !b.exempted).length;
  $('#nx').textContent = exempt.length;
  $('#dirty').style.visibility = dirty ? 'visible' : 'hidden';
}

function adopt(v) {
  const b = S.bands.find(x => x.vpos === v);
  if (!b) return;
  if (!b.zone) {
    say('that band lies in no zone — it is a gap in the zoning, not a line. '
        + 'Draw the region in `zones edit`, or rule it not type with x.', 'bad');
    return;
  }
  corr.push({x0: b.hpos, y0: b.vpos, x1: b.hpos + b.width,
             y1: b.vpos + b.height, text: ''});
  sel = corr.length - 1; dirty = true; draw();
}

function ruleBand(v) {
  const b = S.bands.find(x => x.vpos === v);
  if (!b) return;
  const note = prompt('Why is this not a line? (a reason is required)');
  if (!note || !note.trim()) return;
  exempt.push({y0: b.vpos - 4, y1: b.vpos + b.height + 4, note: note.trim()});
  dirty = true; draw();
}

function say(m, cls) { const e = $('#msg'); e.textContent = m; e.className = cls || ''; }

ov.addEventListener('mousedown', e => {
  const t = e.target;
  if (t.dataset.i !== undefined) { sel = +t.dataset.i; draw(); return; }
  if (t.dataset.v !== undefined) {
    (e.shiftKey ? ruleBand : adopt)(+t.dataset.v);
    return;
  }
  const p = at(e);
  drag = {x0: p.x, y0: p.y, x1: p.x, y1: p.y, _ax: p.x, _ay: p.y};
});
ov.addEventListener('mousemove', e => {
  if (!drag) return;
  const p = at(e);
  drag.x0 = Math.min(drag._ax, p.x); drag.x1 = Math.max(drag._ax, p.x);
  drag.y0 = Math.min(drag._ay, p.y); drag.y1 = Math.max(drag._ay, p.y);
  draw();
});
window.addEventListener('mouseup', () => {
  if (!drag) return;
  const d = drag; drag = null;
  if (d.x1 - d.x0 > 8 && d.y1 - d.y0 > 6) {
    corr.push({x0: d.x0, y0: d.y0, x1: d.x1, y1: d.y1, text: ''});
    sel = corr.length - 1; dirty = true;
    if (!inZone(d)) say('drawn outside every zone — the save will refuse it', 'bad');
  }
  draw();
});

async function post(path, body) {
  const r = await fetch(path, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

async function save() {
  try {
    const r = await post('/save', {ref: S.ref, lines: corr, ink_exempt: exempt});
    dirty = false;
    S.bands = r.live_bands;
    say(`saved · ${r.lines} correction(s) · ${r.live_bands.length} band(s) left`, 'ok');
    img.src = (blot ? '/blot/' : '/page/') + S.ref + '.png?t=' + Date.now();
    draw();
  } catch (err) { say(String(err.message || err), 'bad'); }
}

function go(ref) {
  if (dirty && !confirm('Unsaved corrections on this page. Leave anyway?')) return;
  location.href = '/?ref=' + ref;
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 's' || (e.key === 's' && e.ctrlKey)) { e.preventDefault(); save(); }
  else if (e.key === 'b') {
    blot = !blot;
    img.src = (blot ? '/blot/' : '/page/') + S.ref + '.png?t=' + Date.now();
    $('#bp').className = 'pill' + (blot ? ' on' : '');
  }
  else if (e.key === 'Delete' || e.key === 'Backspace') {
    if (sel !== null) { corr.splice(sel, 1); sel = null; dirty = true; draw(); }
  }
  else if (e.key === 'x' && sel === null) {
    const b = S.bands.filter(x => !x.exempted)[0];
    if (b) ruleBand(b.vpos);
  }
  else if (e.key === 'ArrowLeft' && S.prev) go(S.prev);
  else if (e.key === 'ArrowRight' && S.next) go(S.next);
  else if (e.key === 'Escape') { sel = null; draw(); }
});

window.addEventListener('beforeunload', e => { if (dirty) e.preventDefault(); });
window.addEventListener('resize', () => { fit(); draw(); });
$('#save').onclick = save;
$('#done').onclick = async () => { await post('/done', {}); say('server stopped'); };
fit(); draw();
"""

EXTRA_CSS = """
#ov rect{vector-effect:non-scaling-stroke}
/* Zones sit behind everything as context; they are not this editor's subject. */
#ov .z{fill:none;stroke:var(--dim);stroke-width:1;stroke-dasharray:6 5;opacity:.5}
/* Lines the store already has: dim, uneditable, present so a band can be judged
   against what is around it. */
#ov .l{fill:rgba(120,120,120,.14);stroke:rgba(120,120,120,.5);stroke-width:1}
/* A live gap band — the thing to decide about. */
#ov .b{fill:rgba(200,120,0,.20);stroke:#c87800;stroke-width:2;cursor:pointer}
#ov .b:hover{fill:rgba(200,120,0,.35)}
/* In no zone: a finding about the zoning, drawn as a refusal rather than an
   invitation. */
#ov .nz{stroke:var(--err);stroke-dasharray:5 4}
#ov .c{fill:rgba(46,134,171,.22);stroke:#2e86ab;stroke-width:2;cursor:pointer}
#ov .c.sel{stroke-width:3;fill:rgba(46,134,171,.36)}
#ov .drag{fill:rgba(46,134,171,.18);stroke:#2e86ab;stroke-width:2;
          stroke-dasharray:4 3}
/* The two ruling layers, each in its own hand: this editor writes the line
   layer and only shows the zone layer. */
#ov .xl{fill:rgba(255,200,90,.30)}
#ov .xz{fill:rgba(150,150,150,.20)}
#tally{display:flex;gap:14px;color:var(--dim)}
#tally b{color:var(--fg)}
#dirty{color:var(--warn);font-weight:600}
"""


def render_html(ref: str, root: Path = Path("."),
                alto_dir: str = DEFAULT_ALTO_DIR,
                itinerary: list[str] | None = None,
                itinerary_name: str = "") -> str:
    st = page_state(ref, root, alto_dir)
    it = itinerary or []
    i = it.index(st["ref"]) if st["ref"] in it else -1
    st["prev"] = it[i - 1] if i > 0 else ""
    st["next"] = it[i + 1] if 0 <= i < len(it) - 1 else ""
    live = [b for b in st["bands"] if not b["exempted"]]
    nz = [b for b in live if not b["zone"]]
    warn = ("" if st["has_zones"] else
            '<div class="iss e">This page has no zoning. Line correction comes '
            'after it — key the regions in <code>zones edit</code> first.</div>')
    if nz:
        warn += (f'<div class="iss w">{len(nz)} band(s) lie in no zone. That is a '
                 'gap in the zoning, not a line to adopt here: draw the region in '
                 '<code>zones edit</code>, or rule the band not type.</div>')
    return f"""<!doctype html><meta charset=utf-8>
<title>lines {st['ref']}</title>
<style>{webui.CHROME_CSS}{EXTRA_CSS}</style>
<div id=bar>
  <b>lines</b><span id=cur>{st['ref']}</span>
  <span class=pill id=bp>b · blot</span>
  <span id=tally>
    <span>corrections <b id=nc>0</b></span>
    <span>bands left <b id=nb>0</b></span>
    <span>ruled <b id=nx>0</b></span>
  </span>
  <span id=dirty>unsaved</span>
  <span id=msg></span>
  <button id=save>save</button><button id=done>done</button>
</div>
<div id=wrap><div id=stage><img id=img src="/page/{st['ref']}.png">
<svg id=ov xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none"></svg>
</div></div>
<div id=panel>
  <h4>what to do</h4>
  <div class=key><span>adopt a band</span><kbd>click</kbd></div>
  <div class=key><span>rule it not type</span><kbd>shift-click</kbd></div>
  <div class=key><span>draw a box</span><kbd>drag</kbd></div>
  <div class=key><span>delete selected</span><kbd>del</kbd></div>
  <div class=key><span>blotted view</span><kbd>b</kbd></div>
  <div class=key><span>save</span><kbd>s</kbd></div>
  <div class=key><span>page</span><kbd>← →</kbd></div>
  <h4>this editor draws</h4>
  <div id=flags>It never keys. The text of a recovered line is adjudicated in
  <code>ocr review</code> and written by <code>restore</code>, like any other
  line's.</div>
  <h4>itinerary</h4>
  <div id=flags>{itinerary_name or '—'}
  {f'· {i + 1} of {len(it)}' if i >= 0 else ''}</div>
</div>
<div id=issues>{warn}</div>
<script>const STATE = {json.dumps(st, ensure_ascii=False)};</script>
<script>{JS}</script>
"""


def serve(ref: str, root: Path = Path("."), port: int = PORT,
          alto_dir: str = DEFAULT_ALTO_DIR,
          itinerary: list[str] | None = None,
          itinerary_name: str = "") -> None:
    """Serve the line editor on 127.0.0.1. The shell is `webui`'s."""
    from urllib.parse import parse_qs, urlparse

    from .lines import write_blot

    root = Path(root)
    start = norm_ref(ref)

    class Handler(webui.EditorHandler):
        editor = "lines"

        def get(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                r = (parse_qs(u.query).get("ref") or [start])[0]
                self.send_html(render_html(r, root, alto_dir, itinerary,
                                           itinerary_name))
                return
            if u.path.startswith("/page/") and u.path.endswith(".png"):
                try:
                    r = norm_ref(u.path[len("/page/"):-len(".png")])
                except ValueError:
                    self.send_error(404)
                    return
                self.send_png(zn.scan_for(r, root))
                return
            if u.path.startswith("/blot/") and u.path.endswith(".png"):
                # Rendered on demand, with both ruling layers painted: this is
                # the "what is left unsettled" view, which is exactly what the
                # corpus sweep's blot must *not* be.
                try:
                    r = norm_ref(u.path[len("/blot/"):-len(".png")])
                except ValueError:
                    self.send_error(404)
                    return
                dest = root / "scans" / BLOT_CACHE
                res = write_blot(r, dest, alto_dir, root, exemptions=True)
                self.send_png(Path(res["path"]))
                return
            self.send_error(404)

        def post(self):
            if self.path == "/done":
                self.send_json({})
                self.stop_from_page()
                return
            if self.path != "/save":
                self.send_error(404)
                return
            res = save_payload(self.body_json(), root, alto_dir)
            print(f"saved {res['path']}: {res['lines']} correction(s), "
                  f"{len(res['live_bands'])} band(s) left")
            self.send_json(res)

    url = f"http://127.0.0.1:{port}/?ref={start}"
    banner = [f"lines {start} -> {url}   (Done button on the page, or ctrl-c)"]
    if itinerary:
        banner.append(f"itinerary {itinerary_name}: {len(itinerary)} pages")
    banner.append(f"store -> {corr.lines_dir(root)}")
    webui.run(Handler, port, url, banner)
