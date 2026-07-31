"""The segmentation editor: one local page, two clicks a zone.

`review.py --serve` is the template — stdlib `ThreadingHTTPServer` on loopback, the
page built as a Python string, no static files, a Done button that stops the server
so nobody manages the process by hand. What differs is why it exists. The review
queue replaced a text editor; this replaces eScriptorium, whose import/export loop
is the friction the whole store layout was designed around.

**The interaction is the specification.** A zone's left and right edges come from
`data/zones_config.json`; the pointer supplies only a top and a bottom. So the
editor cannot express a zone of the wrong width, and the fixed-measure claim the
training set rests on is true by construction rather than by care. Chain mode then
makes the bottom of one zone the top of the next, which is what a vertical
partition *is* — so an ordinary page of prose costs one type key and one click per
zone, and the ten-second page is arithmetic rather than aspiration.

**The session is the server, not the page.** `review --serve` binds one ref because
a review is one page's worth of work; keying segmentation is a sweep, so the arrow
keys walk `all_scans` and the ref in the URL is only where the sweep started.

Three decisions worth naming because their opposites are the obvious choice:

- **Navigation saves only if something changed.** An unconditional autosave would
  mint an empty zone file for every page merely skimmed past, and an empty file is
  a *claim* here — "looked at, holds nothing", which is what a plate legitimately
  is. Only an explicit save may make one.
- **The column is measured per page, not configured per part.** The measure is
  stable across the book (~1780 px) but its position drifts up to 236 px inside a
  single part, so a constant was ~104 px out on `1-048`. That measurement took the
  verso/recto distinction with it — parity explained only part of the drift — and
  what is left is a manual ±4 px nudge, which is UI state and reaches no file.
- **Order rules warn in the browser and again on the server.** The client copy is
  what makes a violation visible at the keystroke rather than at the save; the
  server's `zones.validate_page` is the one that counts, and its result replaces
  the client's on every save. `tests/test_zones_order.py` is what holds the two
  transcriptions together.
"""
from __future__ import annotations
import json
from pathlib import Path

from . import zones as zn
from . import zones_config as zc
from .context import all_scans, norm_ref, parse_ref

PORT = 8732


def _resolve_column(z: dict, windows: list[dict], tol: float) -> int | None:
    """Which of the page's columns a stored zone sits in, if any.

    Needed only so that a reopened page's zones follow a column nudge instead of
    staying where they were. A zone matching nothing keeps its stored x and is
    reported `column: null` — the editor leaves it alone rather than snapping it
    somewhere plausible, and `validate_page` has already raised against it.
    Guessing here would repair the symptom and lose the finding.
    """
    best, best_off = None, None
    for i, w in enumerate(windows):
        off = max(abs(z["x0"] - w["x0"]), abs(z["x1"] - w["x1"]))
        if best_off is None or off < best_off:
            best, best_off = i, off
    return best if best is not None and best_off <= tol else None


def page_state(ref: str, root: Path, cfg: dict, nudge: int = 0) -> dict:
    """Everything the editor needs for one page, resolved server-side.

    The columns come from `zones.measure_frame` — read off this page's own ink
    rather than from a per-part constant, because the measure is stable across the
    book while its position drifts up to 236 px inside a single part. `nudge`
    carries a manual correction across navigation for the rare page the anchor
    cannot read; it is UI state and reaches no file.
    """
    ref = norm_ref(ref)
    scans = all_scans(root)
    try:
        i = scans.index(ref)
    except ValueError:
        i = -1
    m = zn.measure_frame(ref, root, cfg)
    windows = [{"x0": w["x0"] + nudge, "x1": w["x1"] + nudge} for w in m["columns"]]
    tol = cfg["width_tolerance_px"]
    zones = []
    for z in zn.read_zones(ref, root):
        zones.append({"label": z["label"], "y0": z["y0"], "y1": z["y1"],
                      "column": _resolve_column(z, windows, tol),
                      "x0": z["x0"], "x1": z["x1"]})
    w, h = zn.raster_size(ref, root)
    return {
        "ref": ref,
        "page": {"w": w, "h": h},
        "columns": windows,
        # The vertical crop. A view concern only — nothing validates against it,
        # and a zone drawn outside the ink is already an error the ink check finds.
        "content": m["content"],
        "anchor": {"measured": m["measured"], "source": m["source"], "nudge": nudge},
        "zones": zones,
        "keyed": zn.has_zones(ref, root),
        "split": zn.load_splits(root).get(ref, zn.DEFAULT_SPLIT),
        "exempt": zn.load_exempt(root).get(ref, []),
        # Ink no zone accounts for, shown as the page is keyed rather than only
        # after a save. Skipped on a page with no zones, where every mark on the
        # leaf is uncovered and the answer would be noise.
        "uncovered": (zn.validate_page(ref, root, cfg, ink=True)["uncovered"]
                      if zones else []),
        "ink_exempt": zn.load_ink_exempt(root).get(ref, []),
        "prev": scans[i - 1] if i > 0 else None,
        "next": scans[i + 1] if 0 <= i < len(scans) - 1 else None,
        "index": i + 1, "total": len(scans),
    }


def save_payload(payload: dict, root: Path, cfg: dict) -> dict:
    """Turn the editor's y-pairs into stored zones, resolving x from the config.

    **The client never supplies an x for a zone it drew.** It sends a column index;
    the geometry is re-measured here from the page itself. That is the whole
    guarantee — an editor cannot save a hand-sized zone because there is no field in
    which to put one. The exception is a zone whose stored x matched no column when
    the page was opened (`column: null`), which is passed through untouched so that
    reopening a page cannot silently rewrite geometry it did not understand.

    The nudge is applied here rather than trusted from the client's x for the same
    reason: it is a single number the server can bound, not an arbitrary rectangle.
    """
    ref = norm_ref(payload["ref"])
    nudge = int(payload.get("nudge") or 0)
    wins = [{"x0": w["x0"] + nudge, "x1": w["x1"] + nudge}
            for w in zn.page_windows(ref, root, cfg)]
    out = []
    for z in payload.get("zones") or []:
        y0, y1 = sorted((int(round(z["y0"])), int(round(z["y1"]))))
        if z.get("column") is None and z.get("x0") is not None:
            x0, x1 = int(z["x0"]), int(z["x1"])
        else:
            w = wins[min(int(z.get("column") or 0), len(wins) - 1)]
            x0, x1 = int(w["x0"]), int(w["x1"])
        out.append({"label": z["label"], "x0": x0, "y0": y0, "x1": x1, "y1": y1})

    res = zn.save_zones(ref, out, root,
                        split=payload.get("split"),
                        exempt=payload.get("exempt") or [])
    zn.set_ink_exempt(ref, payload.get("ink_exempt") or [], root)
    check = zn.validate_page(ref, root, cfg, ink=True)
    res["errors"] = check["errors"]
    res["warnings"] = check["warnings"]
    res["uncovered"] = check["uncovered"]
    return res


# ------------------------------------------------------------------ the page

CSS = """
:root{--bg:#f6f5f3;--fg:#1c1b19;--dim:#6b675f;--line:#d8d4cc;--accent:#2e86ab;
      --warn:#a8620a;--warnbg:#fdf3e2;--err:#a4232b;--errbg:#fbeceb}
@media(prefers-color-scheme:dark){:root{--bg:#16161a;--fg:#e8e6e1;--dim:#9a958c;
      --line:#33323a;--accent:#6ab6d8;--warn:#e0a250;--warnbg:#2f2517;
      --err:#e08b8b;--errbg:#2e1a1a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:13px/1.45 ui-sans-serif,system-ui,sans-serif}
#bar{position:fixed;top:0;left:0;right:0;height:38px;display:flex;gap:14px;
     align-items:center;padding:0 12px;background:var(--bg);
     border-bottom:1px solid var(--line);z-index:20;white-space:nowrap;
     overflow-x:auto}
#bar b{font-weight:600}
.pill{padding:1px 8px;border-radius:10px;border:1px solid var(--line);
      font-size:12px}
.pill.on{background:var(--accent);border-color:var(--accent);color:#fff}
.pill.off{background:var(--warn);border-color:var(--warn);color:#fff}
#cur{font-weight:600}
#swatch{display:inline-block;width:11px;height:11px;border-radius:2px;
        vertical-align:-1px;margin-right:5px}
#target{color:var(--dim);font-size:12px}
#target.sel{color:var(--fg);font-weight:600}
#msg{margin-left:auto;color:var(--dim)}
#msg.bad{color:var(--err);font-weight:600}
#msg.ok{color:var(--accent)}
/* One scroll container for both axes: the edge-hover autoscroll needs a single
   element whose scrollTop it can drive, and the page is now sized to the text
   column rather than to the leaf, so it is routinely taller than the view. */
#wrap{position:fixed;top:38px;left:0;right:250px;bottom:0;overflow:auto;padding:10px}
/* The stage is a window onto the page's inked band, not the whole leaf: the top
   and bottom of a scan are blank paper, and scrolling through them is time spent
   on nothing. The image is positioned inside it and clipped. */
#stage{position:relative;line-height:0;margin:0 auto;overflow:hidden;
       box-shadow:0 1px 8px rgba(0,0,0,.18)}
#stage img{position:absolute;left:0;display:block;width:100%;height:auto;
           image-rendering:-webkit-optimize-contrast}
@media(prefers-color-scheme:dark){#stage img{filter:invert(1) hue-rotate(180deg)}}
#ov{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}
#panel{position:fixed;right:0;top:38px;width:250px;bottom:0;overflow-y:auto;
       border-left:1px solid var(--line);background:var(--bg);padding:10px 12px;
       z-index:15}
#panel h4{margin:14px 0 6px;font-size:11px;letter-spacing:.06em;
          text-transform:uppercase;color:var(--dim);font-weight:600}
#panel h4:first-child{margin-top:0}
.key{display:flex;justify-content:space-between;gap:8px;padding:1px 0;
     font-size:12px}
.key kbd{font:11px ui-monospace,monospace;background:var(--line);
         border-radius:3px;padding:0 5px}
.tk{display:flex;align-items:center;gap:6px;padding:2px 4px;border-radius:4px;
    cursor:pointer}
.tk:hover{background:var(--line)}
.tk.sel{background:var(--line);font-weight:600}
.tk i{width:11px;height:11px;border-radius:2px;flex:none}
.tk span{flex:1;font-style:normal}
.tk em{font-style:normal;font-size:10px;color:var(--dim);border:1px solid var(--line);
       border-radius:3px;padding:0 4px;cursor:help}
#flags{padding:6px 0;font-size:12px;color:var(--dim)}
#issues{position:fixed;left:0;bottom:0;max-width:calc(100% - 250px);z-index:18}
.iss{padding:6px 12px;border-top:1px solid var(--line);font-size:12px}
.iss.w{background:var(--warnbg);color:var(--warn)}
.iss.e{background:var(--errbg);color:var(--err);font-weight:600}
.iss.x{opacity:.62;font-style:italic}
button{font:inherit;padding:2px 10px;border:1px solid var(--line);border-radius:5px;
       background:var(--bg);color:var(--fg);cursor:pointer}
button:hover{background:var(--line)}
"""

JS = r"""
const T = {}, KEY = {};
CFG.types.forEach(t => { T[t.label] = t; KEY[t.key] = t.label; });
const ACT = {};
for (const [name, k] of Object.entries(CFG.actions || {}))
  if (!name.startsWith('_')) ACT[k] = name;

let S = {
  zones: ST.zones.map(z => ({...z})),
  cur: null, col: 0, pending: null, hoverY: null, inside: false,
  hover: -1, sel: -1, nearEdge: false,
  chain: true, dirty: false, split: ST.split, exempt: ST.exempt.slice(),
  issues: [], drag: null, nudge: ST.anchor.nudge || 0,
  ink: (ST.uncovered || []).map(b => ({...b})),
  inkEx: (ST.ink_exempt || []).map(r => ({...r})),
};
let zoom = parseFloat(localStorage.getItem('zonesZoom') || '0') || 0;

const img = document.getElementById('img'), ov = document.getElementById('ov');
const stage = document.getElementById('stage'), wrap = document.getElementById('wrap');
const VIEW = Object.assign({column_margin: 0.10, edge_band_px: 80,
                            edge_overlap_px: 140}, CFG.view || {});

// ---- column geometry: measured on the server off this page's own ink, then
// shifted by the manual nudge. Not computed here from a per-part constant — the
// measure is stable across the book but its position drifts up to 236 px inside
// one part, so there is no constant to compute from.
function windows() {
  return ST.columns.map(w => ({x0: w.x0 - (ST.anchor.nudge || 0) + S.nudge,
                               x1: w.x1 - (ST.anchor.nudge || 0) + S.nudge}));
}
function win() {
  const w = windows();
  return w[Math.min(S.col, w.length - 1)];
}
function zoneX(z) {
  if (z.column === null || z.column === undefined) return {x0: z.x0, x1: z.x1};
  const w = windows();
  return w[Math.min(z.column, w.length - 1)];
}

// ---- fit: default is the whole page in the viewport, zoom steps from there
function applyZoom() {
  // Fit the **text column** to the view, not the leaf. The column is what is being
  // judged and what every click lands in; the margins carry nothing, and fitting
  // the whole page spent most of the screen on paper. A modest margin either side
  // keeps the column's edges visible so a bad anchor is obvious.
  const w = win();
  const colW = (w.x1 - w.x0) * (1 + 2 * VIEW.column_margin);
  const fit = (wrap.clientWidth - 20) / colW;
  const s = zoom ? fit * Math.pow(1.25, zoom) : fit;
  const px = Math.round(ST.page.w * s) + 'px';
  const hpx = Math.round((ST.content.y1 - ST.content.y0) * s) + 'px';
  // Only re-lay-out when the size actually changed. Doing it every render would
  // fight the editor's own horizontal scrolling on every mouse move.
  if (stage.style.width !== px || stage.style.height !== hpx) {
    stage.style.width = px;
    stage.style.height = hpx;
    // The image keeps its full height and is slid up behind the clip, so
    // `img.getBoundingClientRect()` still describes the whole page — which is
    // what `yAt` reads, and why cropping the view changes no coordinate maths.
    img.style.top = Math.round(-ST.content.y0 * s) + 'px';
    requestAnimationFrame(centreColumn);
  }
  return s;
}

// Centre the column horizontally rather than the page: on a leaf whose text sits
// well off-centre — and they do, by up to 236 px — centring the paper puts the
// column off to one side.
function centreColumn() {
  const r = img.getBoundingClientRect();
  if (!r.width) return;
  const w = win(), s = r.width / ST.page.w;
  const mid = (w.x0 + w.x1) / 2 * s;
  wrap.scrollLeft = Math.max(0, mid - wrap.clientWidth / 2 + 10);
}

// ---- hover the top or bottom edge to jump a screen, instantly
//
// A jump, not a scroll. At this zoom the leaf is about two screens tall, so the
// movement actually wanted is "show me the other half" — and a continuous scroll
// makes that a thing to wait for and steer, when it should be one flick of the
// wrist. `edge_overlap_px` of the old view is kept so the join is readable and a
// zone boundary never lands in the seam.
//
// Armed once per entry into the band: after a jump the cursor is still inside it,
// so without this it would page again on the next mouse move and run off the leaf.
let edgeArmed = true;
function edgeScroll(clientY) {
  const r = wrap.getBoundingClientRect(), band = VIEW.edge_band_px;
  const inTop = clientY - r.top < band, inBot = r.bottom - clientY < band;
  if (!inTop && !inBot) { edgeArmed = true; return; }
  if (!edgeArmed) return;
  edgeArmed = false;
  const step = Math.max(80, wrap.clientHeight - VIEW.edge_overlap_px);
  wrap.scrollTop += inTop ? -step : step;
}
function edgeStop() { edgeArmed = true; }
function yAt(ev) {
  const r = img.getBoundingClientRect();
  return Math.max(0, Math.min(ST.page.h,
    Math.round((ev.clientY - r.top) * (ST.page.h / r.height))));
}

// ---- the order rules, transcribed from zones_config.order_warnings.
// Held to that function by tests/test_zones_order.py; a rule added there has to
// be added here, and the shapes are the same so the banner reads identically
// whether it came from the browser or from the save.
function orderWarnings() {
  const on = new Set((CFG.order_rules || []).map(r => r.id));
  const rank = l => (T[l] ? T[l].rank : null);
  const zs = S.zones.slice().sort((a, b) => a.y0 - b.y0);
  const out = [];
  const warn = (rule, detail) =>
    out.push({rule, detail, exempted: S.exempt.includes(rule)});
  if (on.has('title-first')) {
    const i = zs.findIndex(z => rank(z.label) === 0);
    if (i > 0) warn('title-first',
      `${zs[i].label} at y=${zs[i].y0} is below ${zs[0].label} at y=${zs[0].y0}`);
  }
  if (on.has('rank-monotone')) {
    const r = zs.filter(z => rank(z.label) !== null && rank(z.label) !== undefined);
    for (let i = 1; i < r.length; i++)
      if (rank(r[i].label) < rank(r[i - 1].label))
        warn('rank-monotone',
          `${r[i].label} (rank ${rank(r[i].label)}) at y=${r[i].y0} follows ` +
          `${r[i-1].label} (rank ${rank(r[i-1].label)}) at y=${r[i-1].y0}`);
  }
  if (on.has('max-per-page'))
    for (const t of CFG.types) {
      if (!t.max_per_page) continue;
      const n = zs.filter(z => z.label === t.label).length;
      if (n > t.max_per_page)
        warn('max-per-page',
          `${t.label} occurs ${n} times, max_per_page is ${t.max_per_page}`);
    }
  return out;
}

// ---- render
function render() {
  applyZoom();
  const P = ST.page, C = ST.content, parts = [];
  // The viewBox is the cropped band, so everything below still draws in page
  // coordinates and nothing else in this file has to know the view is cropped.
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg"
    viewBox="0 ${C.y0} ${P.w} ${C.y1 - C.y0}"
    preserveAspectRatio="none" width="100%" height="100%">`);
  // the live column guide, so the measure a click will use is never a surprise
  const w = win();
  parts.push(`<rect x="${w.x0}" y="${C.y0}" width="${w.x1 - w.x0}"
     height="${C.y1 - C.y0}" fill="none" stroke="var(--accent)" stroke-width="2"
     stroke-dasharray="14 10" opacity=".38"/>`);
  const dragging = new Set((S.drag || []).map(g => g.i));
  S.zones.forEach((z, i) => {
    const g = zoneX(z), t = T[z.label], c = t ? t.color : '#999';
    const bad = z.column === null || z.column === undefined;
    const picked = i === S.sel;
    const on = picked || i === S.hover || dragging.has(i);
    parts.push(`<rect x="${g.x0}" y="${z.y0}" width="${g.x1 - g.x0}"
       height="${z.y1 - z.y0}" fill="${c}" fill-opacity="${on ? .30 : .17}"
       stroke="${c}" stroke-width="${bad ? 6 : (on ? 6 : 3)}"
       ${bad ? 'stroke-dasharray="12 8"' : ''}/>`);
    // A selection outlives the pointer, so it needs a mark the pointer is not
    // supplying: a second rule inset from the first, in the page's own ink colour.
    if (picked)
      parts.push(`<rect x="${g.x0 + 10}" y="${z.y0 + 10}"
         width="${g.x1 - g.x0 - 20}" height="${z.y1 - z.y0 - 20}" fill="none"
         stroke="var(--fg)" stroke-width="3" stroke-dasharray="16 10"/>`);
    parts.push(`<rect x="${g.x0}" y="${z.y0}" width="${g.x1 - g.x0}" height="4"
       fill="${c}"/>`);
    parts.push(`<text x="${g.x0 + 10}" y="${z.y0 + 42}" font-size="34"
       fill="${c}" font-family="ui-sans-serif,sans-serif">${i + 1}. ${
       t ? t.name : z.label}${bad ? ' [off-measure]' : ''}</text>`);
    // Grab handles on the zone under the cursor. Shift-drag was already here and
    // was invisible, which is the same as not being here.
    if (on) {
      const hw = 46, hh = 14;
      for (const y of [z.y0, z.y1])
        parts.push(`<rect x="${(g.x0 + g.x1) / 2 - hw}" y="${y - hh / 2}"
           width="${hw * 2}" height="${hh}" rx="6" fill="${c}"
           fill-opacity=".9"/>`);
    }
  });
  // Ink the zones do not account for. Drawn under the preview so it never hides
  // what is being placed, and hatched rather than filled so it reads as a question
  // about the page rather than as another zone.
  parts.push(`<defs><pattern id="hatch" width="18" height="18"
     patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
     <rect width="18" height="18" fill="var(--warn)" fill-opacity=".12"/>
     <line x1="0" y1="0" x2="0" y2="18" stroke="var(--warn)" stroke-width="6"
       stroke-opacity=".5"/></pattern></defs>`);
  S.ink.forEach(b => {
    const ex = inkExcuse(b);
    parts.push(`<rect x="${w.x0 - 40}" y="${b.vpos}" width="${w.x1 - w.x0 + 80}"
       height="${b.height}" fill="url(#hatch)" stroke="var(--warn)"
       stroke-width="${ex ? 2 : 4}" stroke-dasharray="${ex ? '10 8' : ''}"
       opacity="${ex ? .5 : 1}"/>`);
    parts.push(`<text x="${w.x1 + 50}" y="${b.vpos + b.height / 2 + 12}"
       font-size="32" fill="var(--warn)" font-family="ui-sans-serif,sans-serif"
       opacity="${ex ? .6 : 1}">${ex ? '✓ ' + esc(ex.note)
       : 'unaccounted ink — i'}</text>`);
  });

  const pv = preview();
  if (pv) {
    const c = S.cur && T[S.cur] ? T[S.cur].color : 'var(--accent)';
    parts.push(`<rect x="${w.x0}" y="${pv[0]}" width="${w.x1 - w.x0}"
       height="${pv[1] - pv[0]}" fill="${c}" fill-opacity=".22" stroke="${c}"
       stroke-width="3"/>`);
  }
  if (S.pending !== null) {
    // The anchor. Drawn last so it sits on top of its own band and of any zone
    // it overlaps, and drawn whether or not the pointer is on the page — it is
    // the thing that is still true when the cursor has wandered off.
    const c = S.cur && T[S.cur] ? T[S.cur].color : 'var(--accent)';
    parts.push(`<line x1="0" y1="${S.pending}" x2="${P.w}" y2="${S.pending}"
       stroke="${c}" stroke-width="4"/>`);
  }
  // The cursor guide, which is the one thing that genuinely has no meaning once
  // the pointer is off the page.
  if (S.inside && S.hoverY !== null)
    parts.push(`<line x1="0" y1="${S.hoverY}" x2="${P.w}" y2="${S.hoverY}"
       stroke="var(--accent)" stroke-width="2" opacity=".8"/>`);
  parts.push('</svg>');
  ov.innerHTML = parts.join('');
  bar();
  issues();
}

function bar() {
  const t = S.cur ? T[S.cur] : null;
  document.getElementById('swatch').style.background = t ? t.color : 'transparent';
  document.getElementById('cur').textContent = t ? t.name : '(no type)';
  const anc = document.getElementById('anchor');
  anc.textContent = (ST.anchor.measured ? 'anchored' : ST.anchor.source) +
    (S.nudge ? ` ${S.nudge > 0 ? '+' : ''}${S.nudge}` : '');
  anc.className = 'pill' + (ST.anchor.measured ? '' : ' on');
  const w = windows();
  document.getElementById('col').textContent =
    w.length > 1 ? `col ${S.col + 1}/${w.length}` : '1 col';
  const sp = document.getElementById('split');
  sp.textContent = S.split === 'exempt' ? 'exempt — not a text page' : S.split;
  sp.className = 'pill' + (S.split === 'train' ? '' :
                           S.split === 'eval' ? ' on' : ' off');
  const ch = document.getElementById('chain');
  ch.textContent = 'chain'; ch.className = 'pill' + (S.chain ? ' on' : '');
  document.getElementById('count').textContent =
    S.zones.length + ' zone' + (S.zones.length === 1 ? '' : 's') +
    (S.dirty ? ' •' : '');
  // Say what is under the cursor and what can be done to it. These operations
  // existed before this line did, and were undiscoverable for want of it.
  const tgt = document.getElementById('target');
  const i = target();
  if (i >= 0) {
    const z = S.zones[i], t = T[z.label];
    tgt.textContent = `#${i + 1} ${t ? t.name : z.label} · ` +
      (S.sel === i ? 'press a type key to change it · Esc deselects'
                   : 'click to select · shift+key retypes') +
      ' · x deletes';
    tgt.className = S.sel === i ? 'sel' : '';
  } else { tgt.textContent = ''; tgt.className = ''; }
  document.querySelectorAll('.tk').forEach(el =>
    el.classList.toggle('sel', el.dataset.label === S.cur));
}

function issues() {
  const all = S.issues.length ? S.issues : orderWarnings().map(w => ({...w, kind: 'w'}));
  document.getElementById('issues').innerHTML = all.map(w =>
    `<div class="iss ${w.kind === 'e' ? 'e' : 'w'}${w.exempted ? ' x' : ''}">` +
    `${w.rule}: ${w.detail}${w.exempted ? ' — exempted' : ''}</div>`).join('');
}

function say(m, cls) {
  const el = document.getElementById('msg');
  el.textContent = m; el.className = cls || '';
}

// ---- editing
// A type may declare its own height, for a shape the book repeats at one size —
// the running title is a single line of fixed size, so only its top is ever in
// question and it costs one click rather than two.
function autoH() {
  const t = T[S.cur];
  return (t && t.default_height) || 0;
}
function gapAfter(label) {
  const t = T[label];
  return (t && t.gap_after) || 0;
}
// Whether the chain carries on past this type at all. Default true; off for the
// types that end the column (footnotes, the signature line) and for the catch-all,
// whose neighbours are by definition unpredictable. Guessing a top that is usually
// wrong costs a right-click every time, which is worse than not guessing.
function chainAfter(label) {
  const t = T[label];
  return !t || t.chain_after !== false;
}
// Where the chain resumes after a zone of this type: its foot, plus whatever dead
// space the page predictably leaves below it. Null when the type ends the chain.
function resume(label, y1) {
  return chainAfter(label) ? y1 + gapAfter(label) : null;
}

function place(y0, y1) {
  if (!S.cur) { say('pick a type first', 'bad'); return; }
  S.zones.push({label: S.cur, y0, y1, column: S.col});
  S.pending = S.chain ? resume(S.cur, y1) : null;
  S.sel = -1; S.dirty = true; S.issues = [];
  const nxt = (CFG.auto_select.after || {})[S.cur];
  if (nxt) S.cur = nxt;
  render();
}

// The band a click would commit right now, or null. Drawn as the preview, so what
// a one-click type is about to place is never a guess.
function preview() {
  const h = autoH();
  if (S.pending !== null) {
    if (h) return [S.pending, S.pending + h];
    if (S.hoverY === null) return null;
    return [Math.min(S.pending, S.hoverY), Math.max(S.pending, S.hoverY)];
  }
  // With no anchor set there is nothing tentative to preserve, so a fixed-height
  // band only tracks a pointer that is actually on the page.
  if (h && S.inside && S.hoverY !== null) return [S.hoverY, S.hoverY + h];
  return null;
}
function hit(y) {
  for (let i = S.zones.length - 1; i >= 0; i--)
    if (y >= S.zones[i].y0 && y <= S.zones[i].y1) return i;
  return -1;
}
function nearestEdge(i, y) {
  const z = S.zones[i];
  return Math.abs(y - z.y0) <= Math.abs(y - z.y1) ? 'y0' : 'y1';
}
// What an edit acts on: the zone clicked, or failing that the one under the
// cursor. One rule, so `x`, the nudges and a retype never disagree about their
// subject — and a selection survives the pointer wandering off the zone.
function target() { return S.sel >= 0 ? S.sel : S.hover; }

function esc(s) {
  return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}
// Matched on the band's midpoint, as the server does — the band is re-measured
// from the raster each run and its edges move by a pixel or two, so an edge test
// would silently stop matching.
function inkExcuse(b) {
  const mid = b.vpos + b.height / 2;
  return S.inkEx.find(r => r.y0 <= mid && mid <= r.y1) || null;
}
function inkAt(y) {
  return S.ink.find(b => y >= b.vpos - 20 && y <= b.vpos + b.height + 20) || null;
}

// Page pixels per screen pixel, so a grab tolerance stays the same size under the
// hand at any zoom.
function pxPerScreen() {
  const r = img.getBoundingClientRect();
  return r.width ? ST.page.w / r.width : 1;
}

// Every zone edge within grabbing distance of y. A vertical partition shares its
// boundaries — chain mode makes the next zone's top exactly the last one's bottom —
// so dragging one boundary has to move both sides of it, or the drag opens a gap
// or an overlap that the editor then has to repair by hand.
function edgesAt(y) {
  const snap = 10 * pxPerScreen();
  const out = [];
  S.zones.forEach((z, i) => {
    if (Math.abs(y - z.y0) <= snap) out.push({i, edge: 'y0'});
    if (Math.abs(y - z.y1) <= snap) out.push({i, edge: 'y1'});
  });
  return out;
}

ov.addEventListener('mousemove', e => {
  S.hoverY = yAt(e);
  S.inside = true;
  S.hover = hit(S.hoverY);
  S.nearEdge = S.drag ? S.nearEdge : edgesAt(S.hoverY).length > 0;
  edgeScroll(e.clientY);
  if (S.drag) {
    // Move every edge that was on this boundary, together, so the partition
    // stays a partition. Each is clamped so a zone cannot be dragged inside out.
    for (const g of S.drag) {
      const z = S.zones[g.i];
      if (g.edge === 'y0') z.y0 = Math.min(S.hoverY, z.y1 - 4);
      else z.y1 = Math.max(S.hoverY, z.y0 + 4);
    }
    S.dirty = true; S.issues = [];
  }
  render();
});
// The page range actually on screen right now, in page coordinates. Scroll
// position decides it, so when the view is scrolled to an extreme this is the
// extreme of the printed content — which is what makes overshooting resolve to
// "the top of the text" rather than to some arbitrary row.
function visibleBand() {
  const r = img.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
  const sc = ST.page.h / r.height;
  const top = (Math.max(wr.top, r.top) - r.top) * sc;
  const bot = (Math.min(wr.bottom, r.bottom) - r.top) * sc;
  return [Math.max(top, ST.content.y0), Math.min(bot, ST.content.y1)];
}

ov.addEventListener('mouseleave', e => {
  // Overshooting the top or bottom resolves to that edge rather than being
  // discarded. Running a zone to the first or last line of the page is the
  // commonest thing a partition has to do, and pixel-hunting the boundary for it
  // is the one part of the flow that cannot be done by feel. Leaving *sideways* —
  // for the panel — keeps the last position instead: no edge was aimed at.
  //
  // `hoverY` is kept either way. Blanking it read as "cancelled" when the anchor
  // is in fact still set and the next click still commits.
  const r = img.getBoundingClientRect();
  const raw = (e.clientY - r.top) * (ST.page.h / r.height);
  const [vt, vb] = visibleBand();
  if (raw < vt) S.hoverY = Math.round(vt);
  else if (raw > vb) S.hoverY = Math.round(vb);
  S.inside = false; S.hover = -1; S.nearEdge = false;
  edgeStop(); render();
});
// Right-click cancels a half-placed zone and breaks the chain. Chaining is right
// for the common case — a partition shares its boundaries — but a page has plenty
// of whitespace where the next zone does not start at the last one's foot, and
// reaching for Escape mid-click is a hand off the mouse every time.
ov.addEventListener('contextmenu', e => {
  e.preventDefault();
  S.pending = null;
  S.sel = -1;
  render();
});
ov.addEventListener('mousedown', e => {
  // Shift makes a drag an edge adjustment. Plain clicks stay unambiguous — the
  // primary flow must never have to wonder whether it was a click or a grab, and
  // chain mode puts the cursor on an existing edge constantly.
  if (!e.shiftKey) return;
  const g = edgesAt(yAt(e));
  if (!g.length) return;
  e.preventDefault();
  S.drag = g;
});
window.addEventListener('mouseup', () => {
  edgeStop();
  if (S.drag) { S.drag = null; render(); }
});
ov.addEventListener('click', e => {
  if (e.shiftKey) return;
  const y = yAt(e);
  // Mid-placement, a click always finishes the zone. Only an idle click can mean
  // "select", so the primary flow is never interrupted by landing on a zone —
  // and with chain mode a click lands on an existing boundary constantly.
  if (S.pending === null) {
    const i = hit(y);
    if (i >= 0) { S.sel = (S.sel === i ? -1 : i); render(); return; }
    S.sel = -1;
  }
  const h = autoH();
  if (h) {
    // Height is known, so the click settles the whole zone. When the chain is
    // already holding a top, that top wins and the click is the confirmation —
    // which is what the preview has been showing all along.
    const top = S.pending !== null ? S.pending : y;
    place(top, top + h);
    return;
  }
  if (S.pending === null) { S.pending = y; render(); return; }
  place(Math.min(S.pending, y), Math.max(S.pending, y));
});

// ---- server
async function post(path, body) {
  const r = await fetch(path, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!r.ok) throw new Error((await r.json()).error || r.statusText);
  return r.json();
}
async function save() {
  const res = await post('/save', {
    ref: ST.ref, split: S.split, exempt: S.exempt, nudge: S.nudge,
    ink_exempt: S.inkEx,
    zones: S.zones.map(z => ({label: z.label, y0: z.y0, y1: z.y1,
                              column: z.column, x0: z.x0, x1: z.x1})),
  });
  // The bands are re-measured against what was just written, so what is on screen
  // is always the finding for the zones as they now stand.
  S.ink = (res.uncovered || []).map(b => ({...b}));
  S.dirty = false;
  S.issues = res.errors.map(e => ({...e, kind: 'e', exempted: false}))
             .concat(res.warnings.map(w => ({...w, kind: 'w'})));
  say(`saved ${res.zones} zones` +
      (res.errors.length ? ` · ${res.errors.length} error(s)` : ''),
      res.errors.length ? 'bad' : 'ok');
  render();
  return res;
}
async function nav(ref) {
  if (!ref) return;
  // Dirty only. An unconditional save would mint an empty zone file for every
  // page skimmed past, and an empty file is a claim: "looked at, holds nothing".
  if (S.dirty) { try { await save(); } catch (err) {
    say('not saved: ' + err.message, 'bad'); return; } }
  // The nudge rides along: a page needing one usually has neighbours that do too,
  // and the next page re-measures its own anchor regardless.
  location = `/?ref=${ref}` + (S.nudge ? `&nudge=${S.nudge}` : '');
}

// ---- keys
window.addEventListener('keydown', async e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  // A type key retypes the **selected** zone, and only otherwise sets what the
  // next one will be. Selecting is an explicit act — a click on an idle canvas —
  // so this cannot surprise anyone who has not just performed it, and misreading
  // a paragraph start for a continuation is the likeliest mistake on the page.
  // Shift does the same to the merely hovered zone, without the click.
  const retype = (e.shiftKey && S.hover >= 0) ? S.hover
               : (!e.shiftKey && S.sel >= 0 && KEY[k]) ? S.sel : -1;
  if (retype >= 0 && KEY[k.toLowerCase()]) {
    S.zones[retype].label = KEY[k.toLowerCase()];
    S.dirty = true; S.issues = [];
    render(); e.preventDefault(); return;
  }
  if (KEY[k]) { S.cur = KEY[k]; S.issues = []; render(); e.preventDefault(); return; }
  const a = ACT[k] || ACT[k.toLowerCase()];
  if (!a) return;
  e.preventDefault();
  switch (a) {
    case 'cancel': S.pending = null; S.sel = -1; break;
    case 'undo':
      if (S.zones.length) {
        S.zones.pop(); S.dirty = true; S.issues = []; S.sel = -1;
        const last = S.zones[S.zones.length - 1];
        S.pending = S.chain && last ? resume(last.label, last.y1) : null;
      }
      break;
    case 'delete': {
      const i = target();
      if (i < 0) break;
      S.zones.splice(i, 1);
      // Both cleared: every index above the removed one has shifted, so keeping
      // either would point at a different zone than the one that was targeted.
      S.sel = -1; S.hover = -1; S.dirty = true; S.issues = [];
      break; }
    case 'ink_exempt': {
      if (S.hoverY === null) break;
      const b = inkAt(S.hoverY);
      if (!b) { say('no unaccounted ink under the cursor', 'bad'); break; }
      const had = inkExcuse(b);
      if (had) {   // second press takes the ruling back
        S.inkEx = S.inkEx.filter(r => r !== had);
        S.dirty = true; say('ruling withdrawn'); break;
      }
      // The reason is required, and is the whole point of the record: this is the
      // only check that can see a dropped zone, so every suppression of it is a
      // claim that something on the paper is not printing.
      const note = (window.prompt(
        'Why is this ink not type? (e.g. "scanner smudge", "gutter blob", '
        + '"offset from facing page")') || '').trim();
      if (!note) { say('not ruled — a reason is required', 'bad'); break; }
      S.inkEx.push({y0: b.vpos, y1: b.vpos + b.height, note});
      S.dirty = true; say('ruled not type: ' + note, 'ok');
      break; }
    case 'anchor_left': S.nudge -= 4; S.dirty = true; S.issues = []; break;
    case 'anchor_right': S.nudge += 4; S.dirty = true; S.issues = []; break;
    case 'anchor_reset': S.nudge = 0; S.dirty = true; S.issues = []; break;
    case 'cycle_column':
      S.col = (S.col + 1) % windows(S.side).length; break;
    case 'toggle_split': {
      // train -> eval -> exempt -> train. `exempt` is the plates, maps, foldouts
      // and blanks: not text pages at all, so in neither the training nor the
      // eval set, and not judged by layout rules written for a text page.
      const order = ['train', 'eval', 'exempt'];
      S.split = order[(order.indexOf(S.split) + 1) % order.length];
      S.dirty = true; S.issues = [];
      break; }
    case 'toggle_chain': S.chain = !S.chain; break;
    case 'exempt': {
      const f = orderWarnings().find(w => !w.exempted);
      if (f) { S.exempt.push(f.rule); S.dirty = true;
               say(`exempted ${f.rule}`, 'ok'); }
      else if (S.exempt.length) { S.exempt = []; S.dirty = true;
                                  say('exemptions cleared', 'ok'); }
      break; }
    case 'nudge_back': case 'nudge_forward': {
      const i = target();
      if (i < 0) break;
      const d = a === 'nudge_back' ? -2 : 2;
      // Nudge the whole shared boundary, exactly as a drag does, so keyboard and
      // mouse cannot leave the partition in two different states. With a zone
      // selected but the cursor elsewhere, the bottom edge is the one meant.
      const edge = S.hoverY === null || S.hover !== i
                 ? 'y1' : nearestEdge(i, S.hoverY);
      const at = S.zones[i][edge];
      for (const g of edgesAt(at)) {
        const z = S.zones[g.i];
        if (g.edge === 'y0') z.y0 = Math.min(z.y0 + d, z.y1 - 4);
        else z.y1 = Math.max(z.y1 + d, z.y0 + 4);
      }
      S.dirty = true; S.issues = [];
      break; }
    case 'zoom_in': zoom += 1; localStorage.setItem('zonesZoom', zoom); break;
    case 'zoom_out': zoom -= 1; localStorage.setItem('zonesZoom', zoom); break;
    case 'save': try { await save(); } catch (err) { say(err.message, 'bad'); } return;
    case 'prev_page': await nav(ST.prev); return;
    case 'next_page': await nav(ST.next); return;
    case 'done': await done(); return;
  }
  render();
});

async function done() {
  try { if (S.dirty) await save(); } catch (err) {
    say('not saved — not stopping: ' + err.message, 'bad'); return; }
  await post('/done', {});
  say('server stopped — you can close this tab', 'ok');
}

img.addEventListener('load', centreColumn);
document.querySelectorAll('.tk').forEach(el =>
  el.addEventListener('click', () => { S.cur = el.dataset.label; render(); }));
document.getElementById('btnsave').addEventListener('click',
  () => save().catch(err => say(err.message, 'bad')));
document.getElementById('btndone').addEventListener('click', done);
window.addEventListener('resize', render);
window.addEventListener('beforeunload', e => {
  if (S.dirty) { e.preventDefault(); e.returnValue = ''; }
});

// Auto-select on load is the same rule as after a commit, applied to whatever the
// page already ends with: a fresh page starts on `fresh_page` (the running title),
// and a page being revised picks up after its own last zone.
if (!S.zones.length) {
  S.cur = CFG.auto_select.fresh_page || CFG.types[0].label;
} else {
  const last = S.zones.slice().sort((a, b) => a.y0 - b.y0).pop();
  S.cur = (CFG.auto_select.after || {})[last.label] || last.label;
}
render();
requestAnimationFrame(centreColumn);
"""


def render_html(ref: str, root: Path, cfg: dict, nudge: int = 0) -> str:
    """The whole editor, as one string. No static files, as in `review.py`."""
    st = page_state(ref, root, cfg, nudge)
    acts = {k: v for k, v in (cfg.get("actions") or {}).items()
            if not k.startswith("_")}
    pretty = {"cancel": "cancel / break chain", "undo": "undo last zone",
              "delete": "delete zone under cursor",
              "anchor_left": "nudge column left 4 px",
              "anchor_right": "nudge column right 4 px",
              "anchor_reset": "reset to measured anchor",
              "cycle_column": "cycle column", "toggle_split": "train / eval / exempt",
              "toggle_chain": "chain mode", "exempt": "exempt the order warning",
              "ink_exempt": "rule ink under cursor not type",
              "save": "save", "done": "save and stop server",
              "prev_page": "previous page", "next_page": "next page",
              "nudge_back": "nudge edge up", "nudge_forward": "nudge edge down",
              "zoom_in": "zoom in", "zoom_out": "zoom out"}

    h = ["<!doctype html><html><head><meta charset='utf-8'>",
         f"<title>zones {st['ref']}</title><style>{CSS}</style></head><body>"]

    h.append("<div id='bar'>")
    h.append(f"<b>{st['ref']}</b>")
    h.append(f"<span class='pill'>{st['index']}/{st['total']}</span>")
    h.append("<span><i id='swatch'></i><span id='cur'></span></span>")
    h.append("<span class='pill' id='anchor'></span>")
    h.append("<span class='pill' id='col'></span>")
    h.append("<span class='pill' id='split'></span>")
    h.append("<span class='pill' id='chain'></span>")
    h.append("<span id='count'></span>")
    h.append("<span id='target'></span>")
    h.append("<span id='msg'></span>")
    h.append("<button id='btnsave'>save</button><button id='btndone'>Done</button>")
    h.append("</div>")

    h.append("<div id='wrap'><div id='stage'>")
    h.append(f"<img id='img' src='/page/{st['ref']}.png' alt='page {st['ref']}'>")
    h.append("<div id='ov'></div>")
    h.append("</div></div>")

    h.append("<div id='panel'><h4>types</h4>")
    for t in cfg["types"]:
        # A one-click type is worth flagging in the list: its height is not being
        # judged, so its behaviour under the pointer differs from every other type.
        note = ""
        if t.get("default_height"):
            note = (f"<em title='fixed {t['default_height']} px, one click"
                    + (f", chain resumes {t['gap_after']} px below"
                       if t.get("gap_after") else "") + "'>1&#8203;click</em>")
        if t.get("chain_after") is False:
            note += ("<em title='the chain stops here — the next top is left "
                     "unset rather than guessed'>ends</em>")
        h.append(f"<div class='tk' data-label=\"{t['label']}\">"
                 f"<i style='background:{t.get('color', '#999')}'></i>"
                 f"<span>{t.get('name', t['label'])}</span>{note}"
                 f"<kbd>{t['key']}</kbd></div>")
    h.append("<h4>actions</h4>")
    for name, key in acts.items():
        h.append(f"<div class='key'><span>{pretty.get(name, name)}</span>"
                 f"<kbd>{key}</kbd></div>")
    h.append("<h4>drawing</h4>")
    h.append("<div class='key'><span>set top, then bottom</span><kbd>click ×2</kbd></div>")
    h.append("<div class='key'><span>cancel / break chain</span><kbd>right-click</kbd></div>")
    h.append("<h4>existing zones</h4>")
    h.append("<div class='key'><span>select one</span><kbd>click it</kbd></div>")
    h.append("<div class='key'><span>then change its type</span><kbd>type key</kbd></div>")
    h.append("<div class='key'><span>retype without selecting</span>"
             "<kbd>shift + type key</kbd></div>")
    h.append("<div class='key'><span>move a boundary</span><kbd>shift-drag</kbd></div>")
    h.append("<div class='key'><span>jump a screen</span>"
             "<kbd>hover top / bottom</kbd></div>")
    h.append("<div id='flags'>Chain mode carries the last bottom edge into the next "
             "zone, so a run of prose is one key and one click each; right-click "
             "breaks it where the page leaves whitespace. The dashed guide is the "
             "column a click will use. Zones share their boundaries, so dragging "
             "one moves both sides of it and the partition stays whole.</div>")
    h.append("</div>")

    h.append("<div id='issues'></div>")
    h.append("<script>const CFG=" + json.dumps(cfg, ensure_ascii=False)
             + ";const ST=" + json.dumps(st, ensure_ascii=False) + ";</script>")
    h.append("<script>" + JS + "</script></body></html>")
    return "\n".join(h)


# ---------------------------------------------------------------- the server

def serve(ref: str, root: Path = Path("."), port: int = PORT) -> None:
    """Serve the editor on 127.0.0.1 and accept saves.

    Loopback only and 404 on anything unrouted, as `review.serve` is: this holds
    unpublished editorial work and has no business being reachable. The one route
    beyond the two `review` needs is the raster — a 2824x3897 page as a base64 data
    URI is some 10 MB of markup per render, where `review`'s line crops are small
    enough that inlining them was the cheaper trick.
    """
    import json as _json
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    root = Path(root)
    cfg = zc.load_config(root)
    start = norm_ref(ref)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):    # one line per save is enough
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                q = parse_qs(u.query)
                r = (q.get("ref") or [start])[0]
                try:
                    nudge = int((q.get("nudge") or ["0"])[0])
                except ValueError:
                    nudge = 0
                try:
                    body = render_html(r, root, cfg, nudge).encode("utf-8")
                except Exception as e:
                    self._send(500, "text/plain; charset=utf-8",
                               str(e).encode("utf-8"))
                    return
                self._send(200, "text/html; charset=utf-8", body)
                return
            if u.path.startswith("/page/") and u.path.endswith(".png"):
                # Through norm_ref, so the path cannot name a file outside `scans/`.
                try:
                    r = norm_ref(u.path[len("/page/"):-len(".png")])
                except ValueError:
                    self.send_error(404)
                    return
                p = zn.scan_for(r, root)
                if not p.exists():
                    self.send_error(404)
                    return
                self._send(200, "image/png", p.read_bytes())
                return
            self.send_error(404)

        def do_POST(self):
            if self.path == "/done":
                self._send(200, "application/json", b"{}")
                # From another thread: `shutdown()` blocks until the serve loop
                # exits, and the serve loop is what is running this handler.
                threading.Thread(target=srv.shutdown, daemon=True).start()
                return
            if self.path != "/save":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = _json.loads(self.rfile.read(n) or b"{}")
                res = save_payload(payload, root, cfg)
            except Exception as e:      # report it to the page, never a blank failure
                self._send(500, "application/json",
                           _json.dumps({"error": str(e)}).encode("utf-8"))
                return
            note = f" · {len(res['errors'])} error(s)" if res["errors"] else ""
            print(f"saved {res['path']}: {res['zones']} zones "
                  f"[{res['labels'] or 'none'}] {res['split']}{note}")
            self._send(200, "application/json",
                       _json.dumps(res, ensure_ascii=False).encode("utf-8"))

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/?ref={start}"
    print(f"zones {start} -> {url}   (Done button on the page, or ctrl-c)")
    print(f"store -> {zn.zone_dir(root)}")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    else:
        print("done — server stopped from the page")
    finally:
        srv.server_close()
