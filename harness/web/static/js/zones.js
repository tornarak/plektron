// Every URL below is relative to the mount prefix — the four editors share
// one server, and this file is a cached static asset served from one place,
// so the prefix is the server's fact to state rather than the script's to
// assume.
const B = ST.base;
const T = {}, KEY = {};
CFG.types.forEach(t => { T[t.label] = t; KEY[t.key] = t.label; });
const ACT = {};
for (const [name, k] of Object.entries(CFG.actions || {}))
  if (!name.startsWith('_')) ACT[k] = name;
// The figure track's actions join the same map — one keyboard, and the config
// loader has already refused any key bound in two of the three namespaces.
for (const [name, k] of Object.entries((CFG.figures || {}).actions || {}))
  if (!name.startsWith('_')) ACT[k] = name;
const FKEY = {};
((CFG.figures || {}).types || []).forEach(t => { FKEY[t.key] = t.label; });

let S = {
  zones: ST.zones.map(z => ({...z})),
  cur: null, col: 0, pending: null, hoverY: null, inside: false,
  hover: -1, sel: -1, nearEdge: null,
  // A machine proposal opens **clean**, and that is load-bearing rather than
  // incidental. Navigation saves whatever is dirty on the way out, so a proposal
  // marked dirty on arrival would let the arrow keys walk an itinerary promoting
  // predictions into ground truth unread — the one thing the two stores exist to
  // stop. Clean means passing through a page writes nothing; promoting it takes an
  // edit or an explicit save, which is a human act either way.
  chain: true, dirty: false, split: ST.split, exempt: ST.exempt.slice(),
  issues: [], drag: null, nudge: ST.anchor.nudge || 0,
  ink: (ST.uncovered || []).map(b => ({...b})),
  inkEx: (ST.ink_exempt || []).map(r => ({...r})),
  // ---- the figure track, parallel to everything above --------------------
  // `figTrack` switches what the pointer does, never what is drawn: the layer
  // renders either way, dimmed when it is not the one being edited, because a
  // picture you cannot see is a picture you will draw a zone over.
  // `figsDirty` is separate from `dirty` so that a pure zone edit sends no
  // `figs` key at all — `zones blot` reads `gt/fig/`'s mtimes, so rewriting the
  // figure store during ordinary keying would stale every training raster.
  figTrack: false, figs: (ST.figs || []).map(f => ({...f})),
  figCur: null, figSel: -1, figHover: -1, figDrag: null, figsDirty: false,
  figExempt: Object.assign({}, ST.fig_exempt || {}), figPending: null, capBeside: false,
  figResize: null, figMove: null, figGrab: null,
  hoverX: null,
};
const FT = {};
((CFG.figures || {}).types || []).forEach(t => { FT[t.label] = t; });
const FIG_ACTIONS = (CFG.figures || {}).actions || {};
let zoom = parseFloat(localStorage.getItem('zonesZoom') || '0') || 0;

const img = document.getElementById('img'), ov = document.getElementById('ov');
const stage = document.getElementById('stage'), wrap = document.getElementById('wrap');
const VIEW = Object.assign({column_margin: 0.10, edge_band_px: 80,
                            edge_overlap_px: 140}, CFG.view || {});
// How far the track you are *not* editing recedes. Two numbers rather than one
// because the two layers are not equally in the way: a keyed page carries eight
// or ten body zones against two or three figure boxes, so the zone layer has to
// go much quieter under the figure track than the other way round.
const FIGV = Object.assign({dim_zones: 0.14, dim_figs: 0.45},
                           (CFG.figures || {}).view || {});

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
// The figure track's pointer, and the reason it is a *pair* where the zone
// track's is a scalar. There is no `xAt` above because a zone has no x to take
// from the pointer; here the pointer is the only thing that knows.
function ptAt(ev) {
  const r = img.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(ST.page.w,
       Math.round((ev.clientX - r.left) * (ST.page.w / r.width)))),
    y: yAt(ev),
  };
}
// Topmost box under a point, searched back to front so the one drawn last — the
// one a human sees on top — is the one that answers.
function figHit(p) {
  for (let i = S.figs.length - 1; i >= 0; i--) {
    const f = S.figs[i];
    if (p.x >= f.x0 && p.x <= f.x1 && p.y >= f.y0 && p.y <= f.y1) return i;
  }
  return -1;
}
// Arm the next box's **first corner** off the one just committed. This is
// `resume()` in two dimensions, and it hands over exactly as much: the zone
// chain gives the next zone its top edge and asks the human for the bottom, so
// this gives the next box one corner and asks for the opposite one.
//
// It armed a whole finished rectangle once — the picture's width, an assumed
// height — and that was wrong twice over. The height was a guess, and captions
// in this book run from one line to five; and a box that arrives complete has
// no handle, so correcting it meant deleting it and drawing it again. A corner
// imputes nothing and still saves the placement, which is the part that is
// actually predictable.
//
// The caption's corner is the picture's **bottom-left** — where the reading
// continues, the same edge `resume()` returns. `caption_beside` re-arms at the
// top-right for the captions set vertically alongside.
function armCaption(fig) {
  const cap = ((CFG.figures || {}).types || [])
    .find(t => t.auto_place && t.auto_place.after === fig.label);
  if (!cap) { S.figPending = null; return; }
  S.figPending = S.capBeside
    ? {label: cap.label, x: fig.x1, y: fig.y0, from: fig}
    : {label: cap.label, x: fig.x0, y: fig.y1, from: fig};
  S.figCur = cap.label;
}
function addFig(box) {
  S.figs.push(box);
  S.figsDirty = true; S.figSel = -1;
  if (box.label === 'GraphicZone') armCaption(box); else S.figPending = null;
}
// ---- resizing a committed box
//
// The zone track has had edge handles and `Shift+Arrow` since it existed, and a
// figure box could only be deleted and drawn again. Eight handles rather than
// four corners: a caption's *height* is the commonest adjustment by a distance —
// the box is drawn round the wrong number of printed lines — and that wants an
// edge, not a corner.
//
// Handles are drawn only on the hovered or selected box, and grabbing one is
// therefore always grabbing something visible. That is what lets a plain drag
// keep meaning "draw a new box" everywhere else: the two gestures never compete
// for the same pixels, because the handle is not there until you are on the box.
const HANDLES = [['nw', 0, 0], ['n', .5, 0], ['ne', 1, 0],
                 ['w', 0, .5], ['e', 1, .5],
                 ['sw', 0, 1], ['s', .5, 1], ['se', 1, 1]];

function grabPx() {
  // In page coordinates, and scaled by the zoom so the grab area stays the same
  // size under the hand however far in the view is.
  const r = img.getBoundingClientRect();
  const scale = r.width ? ST.page.w / r.width : 1;
  return Math.max(12, ((CFG.figures || {}).handle_px || 14) * scale);
}

function figTarget() {
  return S.figSel >= 0 ? S.figSel : S.figHover;
}

function handleAt(p) {
  const i = figTarget();
  if (i < 0) return null;
  const f = S.figs[i], g = grabPx();
  for (const [name, fx, fy] of HANDLES) {
    const hx = f.x0 + (f.x1 - f.x0) * fx, hy = f.y0 + (f.y1 - f.y0) * fy;
    if (Math.abs(p.x - hx) <= g && Math.abs(p.y - hy) <= g)
      return {i, name};
  }
  return null;
}

// Apply a handle drag. Each letter moves the edges it names and nothing else, so
// `n` changes the height alone — the whole reason the edge handles are here.
function resizeTo(f, name, p) {
  if (name.includes('n')) f.y0 = p.y;
  if (name.includes('s')) f.y1 = p.y;
  if (name.includes('w')) f.x0 = p.x;
  if (name.includes('e')) f.x1 = p.x;
  // Dragging an edge past its opposite inverts the box. Normalising here rather
  // than clamping lets the gesture carry on through the flip, which is what a
  // hand actually does when it overshoots a short caption.
  if (f.x0 > f.x1) { const t = f.x0; f.x0 = f.x1; f.x1 = t; }
  if (f.y0 > f.y1) { const t = f.y0; f.y0 = f.y1; f.y1 = t; }
}

// The rectangle an armed corner and the cursor describe between them.
function pendingRect() {
  if (!S.figPending || S.hoverX === null || S.hoverY === null) return null;
  const p = S.figPending;
  return {label: p.label,
          x0: Math.min(p.x, S.hoverX), x1: Math.max(p.x, S.hoverX),
          y0: Math.min(p.y, S.hoverY), y1: Math.max(p.y, S.hoverY)};
}
// ---- the caption-count rule, transcribed from zones_config.fig_warnings.
// Held to that function by harness/tests/test_zones_ui.py, the same way
// test_zones_order.py holds `orderWarnings` — two copies of one vocabulary, and
// the gate points at the copy that would otherwise drift silently.
function figWarnings() {
  const on = new Set(((CFG.figures || {}).rules || []).map(r => r.id));
  const out = [];
  if (on.has('captions-lte-figures')) {
    const nf = S.figs.filter(f => f.label === 'GraphicZone').length;
    const nc = S.figs.filter(f => f.label === 'GraphicZone-FigDesc').length;
    if (nc > nf)
      out.push({rule: 'captions-lte-figures',
                detail: `${nc} captions to ${nf} ${nf === 1 ? 'picture'
                        : 'pictures'} — this book never sets more`,
                exempted: 'captions-lte-figures' in S.figExempt});
  }
  return out;
}

// ---- the order rules, transcribed from zones_config.order_warnings.
// Held to that function by harness/tests/test_zones_order.py, which reads this
// file and compares the rule sets both ways; a rule added there has to be added
// here, and the shapes are the same so the banner reads identically whether it
// came from the browser or from the save. (That gate was named here before it
// existed — the test file contained no reference to this one. It does now.)
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
  // ---- how loud the *other* track is ------------------------------------
  // The inactive track stays on the page and stops competing for the eye. A
  // keyed page carries eight or ten body zones, and at full strength they bury
  // the two or three boxes being drawn over them; hiding them outright is worse,
  // because where the text sits is how you judge where a picture ends.
  //
  // The ink bands are deliberately **not** dimmed with them. On the figure track
  // an unaccounted band is the most useful mark on the page — very often it *is*
  // the undeclared picture you are about to draw, which is exactly how `1-191`
  // surfaced — so it is the one piece of zone-track furniture that gets louder
  // by comparison rather than quieter.
  const zoneDim = S.figTrack ? (FIGV.dim_zones ?? 0.14) : 1;
  // the live column guide, so the measure a click will use is never a surprise
  const w = win();
  parts.push(`<rect x="${w.x0}" y="${C.y0}" width="${w.x1 - w.x0}"
     height="${C.y1 - C.y0}" fill="none" stroke="var(--accent)" stroke-width="2"
     stroke-dasharray="14 10" opacity="${.38 * zoneDim}"/>`);
  parts.push(`<g opacity="${zoneDim}">`);
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
  parts.push('</g>');
  // Ink the zones do not account for. Drawn under the preview so it never hides
  // what is being placed, and hatched rather than filled so it reads as a question
  // about the page rather than as another zone. **Outside the dimming group**: see
  // `zoneDim` above — on the figure track this is the mark worth following.
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

  // ---- the figure layer ---------------------------------------------------
  // Always drawn, dimmed when the pointer is not on this track. Free rectangles:
  // x comes from the box, never from `win()`, which is the whole difference
  // between this track and the one above.
  S.figs.forEach((f, i) => {
    const t = FT[f.label], c = t ? t.color : '#999';
    const on = S.figTrack && (i === S.figSel || i === S.figHover);
    const dim = S.figTrack ? 1 : (FIGV.dim_figs ?? 0.45);
    parts.push(`<rect x="${f.x0}" y="${f.y0}" width="${f.x1 - f.x0}"
       height="${f.y1 - f.y0}" fill="${c}" fill-opacity="${on ? .26 : .12}"
       stroke="${c}" stroke-width="${on ? 6 : 3}" opacity="${dim}"
       ${ST.fig_proposal ? 'stroke-dasharray="18 10"' : ''}/>`);
    parts.push(`<text x="${f.x0 + 10}" y="${f.y0 + 42}" font-size="34"
       fill="${c}" opacity="${dim}" font-family="ui-sans-serif,sans-serif"
       >${t ? t.name : f.label}${ST.fig_proposal ? ' (proposed)' : ''}</text>`);
    // Grab handles, on the hovered or selected box only. Eight, not four: a
    // caption's height is the commonest correction — the box was drawn round the
    // wrong number of printed lines — and an edge handle is what changes height
    // alone. Drawn last so they sit above the box and above its neighbours.
    if (on) {
      const g = grabPx() * 0.8;
      for (const [name, fx, fy] of HANDLES) {
        const hx = f.x0 + (f.x1 - f.x0) * fx, hy = f.y0 + (f.y1 - f.y0) * fy;
        const live = S.figGrab && S.figGrab.i === i && S.figGrab.name === name;
        parts.push(`<rect x="${hx - g}" y="${hy - g}" width="${g * 2}"
           height="${g * 2}" rx="4" fill="${live ? 'var(--fg)' : c}"
           stroke="var(--bg)" stroke-width="3"/>`);
      }
    }
  });
  // The armed corner, and the box it and the cursor describe. Nothing is
  // committed until a click; the corner is drawn whether or not the pointer is
  // on the page, because it is the thing that stays true when the cursor wanders.
  if (S.figPending) {
    const p = S.figPending;
    const c = FT[p.label] ? FT[p.label].color : 'var(--accent)';
    const pr = pendingRect();
    if (pr)
      parts.push(`<rect x="${pr.x0}" y="${pr.y0}" width="${pr.x1 - pr.x0}"
         height="${pr.y1 - pr.y0}" fill="${c}" fill-opacity=".18" stroke="${c}"
         stroke-width="4" stroke-dasharray="14 9"/>`);
    // The corner itself. Deliberately direction-neutral — a mark implying which
    // way the box grows would be wrong, since the opposite corner may be put
    // anywhere. A ring so it reads against both a white margin and a halftone.
    parts.push(`<circle cx="${p.x}" cy="${p.y}" r="15" fill="${c}"
       stroke="var(--bg)" stroke-width="5"/>`);
  }
  if (S.figDrag) {
    const d = S.figDrag, c = S.figCur && FT[S.figCur] ? FT[S.figCur].color
                                                     : 'var(--accent)';
    parts.push(`<rect x="${d.x0}" y="${d.y0}" width="${d.x1 - d.x0}"
       height="${d.y1 - d.y0}" fill="${c}" fill-opacity=".22" stroke="${c}"
       stroke-width="4"/>`);
  }

  const pv = preview();
  if (pv && !S.figTrack) {
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
  //
  // **A crosshair on the figure track, a single rule on the zone track**, and the
  // difference is the point rather than decoration: a zone takes only a y, so a
  // vertical line there would promise a freedom the page does not have. Toggling
  // the track used to look like the editor freezing — the zone preview correctly
  // stops following the cursor and nothing took its place — so the pointer now
  // says which of the two it is doing.
  if (S.inside && S.hoverY !== null) {
    const c = S.figTrack && S.figCur && FT[S.figCur]
            ? FT[S.figCur].color : 'var(--accent)';
    parts.push(`<line x1="0" y1="${S.hoverY}" x2="${P.w}" y2="${S.hoverY}"
       stroke="${c}" stroke-width="2" opacity=".8"/>`);
    if (S.figTrack && S.hoverX !== null)
      parts.push(`<line x1="${S.hoverX}" y1="${C.y0}" x2="${S.hoverX}"
         y2="${C.y1}" stroke="${c}" stroke-width="2" opacity=".8"/>`);
  }
  parts.push('</svg>');
  ov.innerHTML = parts.join('');
  bar();
  trackChips();
  issues();
}

function bar() {
  // The track pill, and the swatch reads off whichever track is live. Before
  // this the bar went on describing zone state while the pointer was drawing
  // figures, so the one control that had changed was the one thing unmentioned.
  const tp = document.getElementById('track');
  const figT = S.figTrack ? FT[S.figCur] : null;
  tp.textContent = S.figTrack ? 'FIGURES' : 'zones';
  tp.className = 'pill' + (S.figTrack ? ' on' : '');
  tp.title = `${CFG.actions.toggle_track || (FIG_ACTIONS.toggle_track || 'b')}`
           + ' switches track';
  if (S.figTrack) tp.style.background = figT ? figT.color : '';
  else tp.style.background = '';

  const t = S.figTrack ? figT : (S.cur ? T[S.cur] : null);
  document.getElementById('swatch').style.background = t ? t.color : 'transparent';
  document.getElementById('cur').textContent =
    t ? t.name : (S.figTrack ? '(no figure type)' : '(no type)');
  const anc = document.getElementById('anchor');
  anc.textContent = (ST.anchor.measured ? 'anchored' : ST.anchor.source) +
    (S.nudge ? ` ${S.nudge > 0 ? '+' : ''}${S.nudge}` : '');
  anc.className = 'pill' + (ST.anchor.measured ? '' : ' on');
  const w = windows();
  document.getElementById('col').textContent =
    w.length > 1 ? `col ${S.col + 1}/${w.length}` : '1 col';
  const sp = document.getElementById('split');
  // The kind reads as itself and says what it means. `train`/`eval` are bookkeeping
  // about a text page and need no gloss; a leaf kind is a ruling and gets one, so
  // the pill never shows a bare word a reader has to remember the weight of.
  const leaf = (CFG.leaf_kinds || []).some(x => x.kind === S.split);
  sp.textContent = leaf ? `${S.split} — not a text page` : S.split;
  sp.className = 'pill' + (S.split === 'train' ? '' :
                           S.split === 'eval' ? ' on' : ' off');
  const ch = document.getElementById('chain');
  ch.textContent = 'chain'; ch.className = 'pill' + (S.chain ? ' on' : '');
  document.getElementById('count').textContent = S.figTrack
    ? (S.figs.length + ' box' + (S.figs.length === 1 ? '' : 'es') +
       (S.figsDirty ? ' •' : ''))
    : (S.zones.length + ' zone' + (S.zones.length === 1 ? '' : 's') +
       (S.dirty ? ' •' : ''));
  // Say what is under the cursor and what can be done to it. These operations
  // existed before this line did, and were undiscoverable for want of it.
  const tgt = document.getElementById('target');
  if (S.figTrack) {
    // The figure track has no measure and no chain, so the zone affordances
    // below are all false here. Saying what *is* available is the whole fix: the
    // track draws on a drag, and a drag leaves nothing on screen until it starts.
    const j = S.figSel >= 0 ? S.figSel : S.figHover;
    if (S.figPending)
      tgt.textContent = 'corner set at the picture’s '
        + (S.capBeside ? 'top-right' : 'foot')
        + ' · click the opposite corner · '
        + (FIG_ACTIONS.caption_beside || 'B') + ' moves it beside · '
        + 'right-click drops it';
    else if (j >= 0) {
      const f = S.figs[j], ft = FT[f.label];
      tgt.textContent = `${ft ? ft.name : f.label} · `
        + (S.figGrab ? 'drag the handle to resize'
           : 'drag a handle to resize · shift-drag to move')
        + (S.figSel === j ? ' · a figure key retypes it · Esc deselects' : '')
        + ' · x deletes';
    } else {
      tgt.textContent = figT
        ? `drag to draw a ${figT.name}`
        : 'pick a figure type first';
    }
    tgt.className = S.figSel >= 0 ? 'sel' : '';
    document.querySelectorAll('.tk').forEach(el =>
      el.classList.toggle('sel', el.dataset.track === 'fig'
                                 && el.dataset.label === S.figCur));
    return;
  }
  const i = target();
  // The boundary case first, because on a partition it is the commonest one and it
  // now *overrides* selecting. Saying so is what keeps the override from reading as
  // the editor ignoring the click.
  if (S.nearEdge !== null && S.pending === null) {
    tgt.textContent = `edge at ${S.nearEdge} · click starts a zone here`;
    tgt.className = 'sel';
  } else if (i >= 0) {
    const z = S.zones[i], t = T[z.label];
    tgt.textContent = `#${i + 1} ${t ? t.name : z.label} · ` +
      (S.sel === i ? 'press a type key to change it · Esc deselects'
                   : 'click to select · shift+key retypes') +
      ' · x deletes';
    tgt.className = S.sel === i ? 'sel' : '';
  } else { tgt.textContent = ''; tgt.className = ''; }
  document.querySelectorAll('.tk').forEach(el =>
    el.classList.toggle('sel', el.dataset.track !== 'fig'
                               && el.dataset.label === S.cur));
}

// The chips of the track you are not on go quiet, so the panel says which half
// of the keyboard is live. Pressing `p` on the figure track does nothing, and a
// chip that still looks armed is the panel promising otherwise.
function trackChips() {
  document.querySelectorAll('.tk').forEach(el => {
    const mine = (el.dataset.track === 'fig') === S.figTrack;
    el.style.opacity = mine ? '1' : String(FIGV.dim_figs ?? 0.45);
  });
}

function issues() {
  const all = S.issues.length ? S.issues : orderWarnings().map(w => ({...w, kind: 'w'}));
  document.getElementById('issues').innerHTML = all.map(w =>
    `<div class="iss ${w.kind === 'e' ? 'e' : 'w'}${w.exempted ? ' x' : ''}">` +
    `${w.rule}: ${w.detail}${w.exempted ? ' — exempted' : ''}</div>`).join('');
}

/* The message bar at the foot. `textContent = ''` removes the child node rather
   than leaving an empty one, which is what lets `#msg:empty` hide the bar —
   assigning `' '` or leaving markup in the template would keep it on screen for
   good. `--msgh` carries the bar's measured height to `#issues`, which is fixed
   to the same corner: the issue strip is the standing finding and rides above
   the passing remark rather than under it. */
function say(m, cls) {
  const el = document.getElementById('msg');
  el.textContent = m || '';
  el.className = m ? (cls || '') : '';
  document.body.style.setProperty('--msgh', m ? el.offsetHeight + 'px' : '0px');
}
// Click to dismiss. A refusal stays until it is read and let go, rather than
// being timed out from under whoever is halfway through it.
document.getElementById('msg').addEventListener('click', () => say(''));

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
// The exact y of an existing boundary within grabbing distance, or null.
//
// Separate from `edgesAt` and deliberately stingier. That one collects every edge
// on a boundary so a shift-drag moves both sides together; this one answers "is the
// click *on* a boundary", and it has to leave a zone's middle clickable or a zone
// becomes impossible to select. Hence the per-zone cap: the grab band is never more
// than a third of the zone's height, so even at `min_zone_h_px` the middle third
// still selects. Returns the boundary's own coordinate, not the click's, so a new
// zone starts flush against the old one and the partition stays a partition.
function anchorAt(y) {
  const snap = 10 * pxPerScreen();
  let best = null;
  S.zones.forEach(z => {
    const band = Math.min(snap, (z.y1 - z.y0) / 3);
    for (const e of [z.y0, z.y1])
      if (Math.abs(y - e) <= band &&
          (best === null || Math.abs(e - y) < Math.abs(best - y))) best = e;
  });
  return best;
}
// What an edit acts on: the zone clicked, or failing that the one under the
// cursor. One rule, so `x`, the nudges and a retype never disagree about their
// subject — and a selection survives the pointer wandering off the zone.
function target() { return S.sel >= 0 ? S.sel : S.hover; }

// ---- keyboard selection
//
// `S.zones` is in the order the zones were drawn, which on a revised page is not
// the order they sit in. Everything the arrows do is in **reading order**, since
// that is the only order visible on screen; the array index is an identity, as it
// is everywhere else in this project.
function byY() {
  return S.zones.map((z, i) => i).sort((a, b) => S.zones[a].y0 - S.zones[b].y0);
}
function below(i) {
  const o = byY(), k = o.indexOf(i);
  return k >= 0 && k < o.length - 1 ? o[k + 1] : -1;
}
// Clamped at both ends rather than wrapped. Wrapping would throw the view a whole
// leaf on a keypress that looks like a step, and the stop is the tell that you are
// at the end — the same reason the page arrows do not wrap round the corpus.
function stepSel(d) {
  if (!S.zones.length) return;
  const o = byY(), cur = target();
  // **From no selection, either arrow starts at the top.** A page arrives with
  // nothing selected, and the direction of the first keypress is not a statement
  // about where to begin — walking a page always begins at its head, so `ArrowUp`
  // on arrival must not land on the footnotes. The selection is not carried across
  // a page: `nav` is a real navigation and the state is rebuilt from the server,
  // so this *is* the reset, applied where it is observable rather than as a flag
  // set on load. Setting `S.sel` at load time instead would break keying — a type
  // key retypes the selected zone, so a page would open with `p` meaning "relabel
  // the running title" rather than "the next zone is a paragraph".
  if (cur < 0) { S.sel = o[0]; }
  else {
    const k = o.indexOf(cur);
    S.sel = o[Math.min(o.length - 1, Math.max(0, k + d))];
  }
  S.hover = -1;
  revealZone(S.sel);
}
// Page-wise, like the edge hover, and for the same reason: at this zoom the leaf is
// about two screens, so the movement wanted is "show me the other half", and a
// smooth scroll would be a thing to wait for. Steps until the zone is on screen —
// bounded, since a zone taller than the viewport can never satisfy the test, and
// then its top edge is the one to show.
function revealZone(i) {
  const z = S.zones[i];
  if (!z) return;
  const step = Math.max(80, wrap.clientHeight - VIEW.edge_overlap_px);
  const pad = VIEW.edge_overlap_px / 2;
  for (let n = 0; n < 40; n++) {
    // Re-read every pass: both rects are live, so a scroll above is already in
    // them, and the loop is over "is it on screen yet" rather than over arithmetic
    // predicting where it landed.
    const r = img.getBoundingClientRect(), w = wrap.getBoundingClientRect();
    if (!r.height) return;
    const s = r.height / ST.page.h;
    const top = r.top + z.y0 * s, bot = r.top + z.y1 * s;
    const was = wrap.scrollTop;
    if (top < w.top + pad) wrap.scrollTop -= step;
    else if (bot > w.bottom - pad && top > w.top + pad) wrap.scrollTop += step;
    else break;
    if (wrap.scrollTop === was) break;   // hit an end; nothing more to show
  }
}

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
// The edges that *are* this boundary, rather than the ones near enough to grab.
//
// `edgesAt`'s window answers "which boundary did the pointer mean", and is
// generous on purpose — 10 screen pixels, so tens of page pixels at working zoom.
// The keyboard already knows which edge it holds, so reusing that window there
// swept up the neighbour across a small gap and carried it along: nearly half the
// boundaries in this store leave a gap of a few pixels, so a resize translated the
// pair and the gap survived every keypress, which is not what "resize" means.
//
// Coincident edges still move together, and must: they are one boundary, and moving
// only one side of it opens an overlap in a store whose partition check refuses one.
function edgesSharing(y) {
  const out = [];
  S.zones.forEach((z, i) => {
    if (Math.abs(y - z.y0) <= 1) out.push({i, edge: 'y0'});
    if (Math.abs(y - z.y1) <= 1) out.push({i, edge: 'y1'});
  });
  return out;
}

ov.addEventListener('mousemove', e => {
  if (S.figTrack) {
    const p = ptAt(e);
    S.hoverY = p.y; S.hoverX = p.x; S.inside = true;
    if (S.figResize) {
      resizeTo(S.figs[S.figResize.i], S.figResize.name, p);
      S.figsDirty = true;
    } else if (S.figMove) {
      const f = S.figs[S.figMove.i], w = f.x1 - f.x0, h = f.y1 - f.y0;
      f.x0 = p.x - S.figMove.dx; f.y0 = p.y - S.figMove.dy;
      f.x1 = f.x0 + w; f.y1 = f.y0 + h;
      S.figsDirty = true;
    } else if (S.figDrag) {
      S.figDrag.x0 = Math.min(S.figDrag._ax, p.x);
      S.figDrag.x1 = Math.max(S.figDrag._ax, p.x);
      S.figDrag.y0 = Math.min(S.figDrag._ay, p.y);
      S.figDrag.y1 = Math.max(S.figDrag._ay, p.y);
    } else {
      // Hover is frozen mid-gesture: losing the box under the pointer would take
      // its handles off screen halfway through dragging one of them.
      S.figHover = figHit(p);
      // **Never while a corner is armed.** The armed corner owns the next click,
      // and a live handle would swallow it — the caption would refuse to finish
      // wherever its opposite corner happened to fall near an existing box.
      S.figGrab = S.figPending ? null : handleAt(p);
    }
    edgeScroll(e.clientY);
    render();
    return;
  }
  S.hoverY = yAt(e);
  S.inside = true;
  S.hover = hit(S.hoverY);
  // Holds the boundary's coordinate rather than a boolean: the status line names
  // it, and a click will anchor there exactly. It was a bool that nothing read.
  S.nearEdge = S.drag ? S.nearEdge : anchorAt(S.hoverY);
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
  S.inside = false; S.hover = -1; S.nearEdge = null;
  edgeStop(); render();
});
// Right-click cancels a half-placed zone and breaks the chain. Chaining is right
// for the common case — a partition shares its boundaries — but a page has plenty
// of whitespace where the next zone does not start at the last one's foot, and
// reaching for Escape mid-click is a hand off the mouse every time.
ov.addEventListener('contextmenu', e => {
  e.preventDefault();
  if (S.figTrack) { S.figPending = null; S.figSel = -1; render(); return; }
  S.pending = null;
  S.sel = -1;
  render();
});
ov.addEventListener('mousedown', e => {
  // On the figure track a plain drag *is* the placement gesture — the idiom is
  // `lines_ui.py`'s, which has drawn free rectangles over this same raster for
  // as long as the line editor has existed. Nothing here is shift-modified,
  // because unlike a zone edge there is no second thing a drag could mean.
  if (S.figTrack) {
    const pt = ptAt(e);
    // A handle takes the drag before anything else. Handles are drawn only on
    // the hovered or selected box, so grabbing one is always grabbing something
    // visible — which is what lets a plain drag keep meaning "draw a new box"
    // everywhere else. The two gestures never compete for the same pixels.
    const grab = S.figPending ? null : handleAt(pt);
    if (grab) {
      e.preventDefault();
      S.figResize = grab; S.figSel = grab.i; S.figPending = null;
      render();
      return;
    }
    // Shift-drag moves the whole box, which is this editor's existing modifier
    // for adjusting geometry that is already there rather than making more.
    if (e.shiftKey) {
      const i = figTarget();
      if (i < 0) return;
      e.preventDefault();
      const f = S.figs[i];
      S.figMove = {i, dx: pt.x - f.x0, dy: pt.y - f.y0};
      S.figSel = i;
      render();
      return;
    }
    // With a corner armed the gesture is click-to-finish, not drag: starting a
    // fresh rectangle here would silently discard the hand-off. Right-click or
    // Esc drops the corner, after which dragging works as usual.
    if (!S.figCur || S.figPending) return;
    e.preventDefault();
    const p = pt;
    S.figDrag = {_ax: p.x, _ay: p.y, x0: p.x, y0: p.y, x1: p.x, y1: p.y};
    return;
  }
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
  if (S.figResize || S.figMove) {
    // A resize can be dragged below the floor the same way a fresh box can, and
    // the answer has to differ: the box already exists and was already accepted,
    // so refusing to shrink it would leave the hand stuck. It is reported by
    // `fig check`'s `tiny-picture` instead, which is a warning and survives.
    const i = (S.figResize || S.figMove).i;
    const f = S.figs[i];
    f.x0 = Math.round(f.x0); f.y0 = Math.round(f.y0);
    f.x1 = Math.round(f.x1); f.y1 = Math.round(f.y1);
    S.figResize = null; S.figMove = null;
    render();
    return;
  }
  if (S.figDrag) {
    const d = S.figDrag;
    S.figDrag = null;
    // Below the floor it was a click, not a drag, and a click is how an armed
    // caption is adopted. Committing a 3 px box instead would be the editor
    // taking a slip of the hand as a claim about the page.
    const min = ((CFG.figures || {}).min_size_px) || 24;
    if (d.x1 - d.x0 >= min && d.y1 - d.y0 >= min)
      addFig({label: S.figCur, x0: d.x0, y0: d.y0, x1: d.x1, y1: d.y1});
    render();
    return;
  }
  if (S.drag) { S.drag = null; render(); }
});
ov.addEventListener('click', e => {
  if (S.figTrack) {
    if (e.shiftKey) return;
    // The click that ends a resize or a move must not also select or complete —
    // mouseup has already cleared the gesture, so `figGrab` is what remembers
    // that the pointer was on a handle when this began.
    if (S.figGrab) { render(); return; }
    // Mid-placement a click always finishes the box, exactly as it does on the
    // zone track — only an idle click can mean "select", or landing on the
    // picture you just drew would select it instead of completing its caption.
    const pr = pendingRect();
    if (pr) {
      const min = ((CFG.figures || {}).min_size_px) || 24;
      if (pr.x1 - pr.x0 >= min && pr.y1 - pr.y0 >= min) {
        S.figPending = null;
        addFig(pr);
      } else {
        say('too small — the opposite corner has to clear min_size_px', 'bad');
      }
    } else {
      S.figSel = figHit(ptAt(e));
    }
    render();
    return;
  }
  if (e.shiftKey) return;
  const y = yAt(e);
  // Mid-placement, a click always finishes the zone. Only an idle click can mean
  // "select", so the primary flow is never interrupted by landing on a zone —
  // and with chain mode a click lands on an existing boundary constantly.
  if (S.pending === null) {
    // **A click on an existing boundary starts a zone there, it does not select.**
    // `hit` is inclusive of both edges, so before this the commonest act on a
    // partition — carry on from where the last zone stopped — landed inside the
    // zone above and selected it, and the anchor had to be placed by eye just below
    // the line instead. Anchoring on the boundary's own coordinate also means the
    // new zone butts exactly against the old one rather than a pixel or two off.
    const at = anchorAt(y);
    if (at !== null) {
      S.sel = -1;
      const ah = autoH();
      if (ah) { place(at, at + ah); return; }
      S.pending = at; render(); return;
    }
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
  // Parsed defensively: a failure carries JSON only from an endpoint marked
  // `@fetched`, and anything else — a 404 from another editor's port, say —
  // answers in HTML, where `.json()` threw a parse error over the real message.
  if (!r.ok) {
    let why = r.statusText;
    try { why = (await r.json()).error || why; } catch (e) { /* not JSON */ }
    throw new Error(why);
  }
  return r.json();
}
// Writing `gt/zones/` from a view that is not `gt` is an **adoption**, not a save,
// and it asks. Without this, `s` while looking at a machine proposal silently turned
// the model's word into ground truth with the same keystroke that saves your own
// work — indistinguishable acts, one of which is the thing the two stores exist to
// keep apart. Once adopted the page has gt of its own, so it never asks again.
function confirmAdoption() {
  if (!ST.proposal && ST.shown !== 'paras') return true;
  const src = ST.proposal ? 'the segmenter' : 'the paragraph rule';
  return confirm(
    `Adopt ${S.zones.length} zones proposed by ${src} as ground truth for `
    + `${ST.ref}?\n\nThis writes gt/zones/, which is the tracked record of what a `
    + `human has been through. Nothing else writes there.`);
}

async function save() {
  // Caught here rather than as a 500 from the server, because the remedy is a
  // choice between three different statements and the page is where they are made.
  // Reachable in one obvious way: key a page, then delete every zone on it.
  if (!S.zones.length && !(CFG.leaf_kinds || []).some(x => x.kind === S.split)) {
    say('no zones: press ' + (CFG.actions.leaf_kind || 'K')
        + ' to say what this leaf is, or ' + (CFG.actions.delete_page || 'X')
        + ' to un-key the page', 'bad');
    return;
  }
  if (!confirmAdoption()) { say('not adopted', 'bad'); return; }
  const body = {
    ref: ST.ref, split: S.split, exempt: S.exempt, nudge: S.nudge,
    ink_exempt: S.inkEx,
    zones: S.zones.map(z => ({label: z.label, y0: z.y0, y1: z.y1,
                              column: z.column, x0: z.x0, x1: z.x1})),
  };
  // **The `figs` key goes only when the figure track was actually touched.**
  // `zones blot` keys the segmenter's training rasters off `gt/fig/`'s mtimes,
  // so sending an unchanged figure list on every ordinary zone save would stale
  // all 252 blots and, through them, everything the zone model learns from.
  if (S.figsDirty) {
    body.fig_ids = ST.fig_ids;
    body.fig_exempt = S.figExempt;
    body.figs = S.figs.map(f => ({id: f.id, label: f.label,
                                  x0: f.x0, y0: f.y0, x1: f.x1, y1: f.y1}));
  }
  const res = await post(B+'/save', body);
  if (res.fig_error) { say(res.fig_error, 'bad'); return res; }
  // The bands are re-measured against what was just written, so what is on screen
  // is always the finding for the zones as they now stand.
  S.ink = (res.uncovered || []).map(b => ({...b}));
  S.dirty = false;
  S.issues = res.errors.map(e => ({...e, kind: 'e', exempted: false}))
             .concat(res.warnings.map(w => ({...w, kind: 'w'})));
  // What is on screen is now ground truth, and the topbar has to say so. Before
  // this, adopting a proposal left the selector reading `gt —` and the banner still
  // claiming a machine proposal, so the one act the store split exists to make
  // visible was the one act with no visible outcome — and pressing `s` again
  // re-asked to adopt something already adopted.
  ST.keyed = true;
  ST.proposal = '';
  ST.shown = 'gt';
  if (ST.present) ST.present.gt = res.zones;
  ST.paras_zones = res.paras_zones;
  renderStores();
  let extra = '';
  if (S.figsDirty) {
    S.figsDirty = false;
    ST.fig_proposal = ''; ST.fig_ids = 'gt';
    if (ST.fig_present) ST.fig_present.gt = res.figs_saved;
    extra = ` · ${res.figs_saved} figure box(es)`;
    // The one thing a human has to leave the editor to finish. Said now, naming
    // the block, rather than left for `corpus figures` to find as an orphan.
    if ((res.readings_missing || []).length)
      extra += ` · key ${res.readings_missing.join(', ')} in data/readings.md`;
    S.issues = S.issues
      .concat((res.fig_errors || []).map(e => ({...e, kind: 'e', exempted: false})))
      .concat((res.fig_warnings || []).map(w => ({...w, kind: 'w'})));
  }
  say(`saved ${res.zones} zones to gt` + extra +
      (res.errors.length ? ` · ${res.errors.length} error(s)` : ''),
      res.errors.length ? 'bad' : 'ok');
  render();
  return res;
}

// The selector, redrawn from `ST` after a write. Server-rendered on load; this is
// the same rule applied to the one thing that can change without a navigation.
function renderStores() {
  const n = {
    gt: ST.present && ST.present.gt != null ? String(ST.present.gt) : '—',
    mz: ST.present && ST.present.mz != null ? String(ST.present.mz) : '—',
    zones: ST.keyed ? '→gt' : (ST.present && ST.present.mz != null ? '→mz' : '—'),
    paras: ST.paras_zones == null ? '—' : String(ST.paras_zones),
  };
  for (const k in n) {
    const el = document.querySelector('#store-' + k + ' .n');
    if (el) el.textContent = n[k];
  }
  const p = document.getElementById('proposal');
  if (p && !ST.proposal) p.remove();
}
async function nav(ref) {
  if (!ref) return;
  // Dirty only. An unconditional save would mint an empty zone file for every
  // page skimmed past, and an empty file is a claim: "looked at, holds nothing".
  if (S.dirty || S.figsDirty) { try { await save(); } catch (err) {
    say('not saved: ' + err.message, 'bad'); return; } }
  // The nudge rides along: a page needing one usually has neighbours that do too,
  // and the next page re-measures its own anchor regardless.
  // `${B}`, not a bare `/`. The four editors share one app and this one is mounted
  // at `/zones`, so a bare root is the shell's front door — the arrow keys landed
  // there and looked like dead keys.
  location = `${B}/?ref=${ref}` + (S.nudge ? `&nudge=${S.nudge}` : '') +
    (ST.store !== 'zones' ? `&store=${ST.store}` : '');
}

// Switching store is a navigation, not a client-side toggle: the zones, the
// proposal snapping and the presence counts are all resolved server-side, and
// re-deriving any of them here would be a second implementation of the store rule.
// It saves first for the same reason `nav` does — and a proposal is never dirty on
// arrival, so cycling away from one still writes nothing.
async function navStore(name) {
  if (S.dirty || S.figsDirty) { try { await save(); } catch (err) {
    say('not saved: ' + err.message, 'bad'); return; } }
  location = `${B}/?ref=${ST.ref}` + (S.nudge ? `&nudge=${S.nudge}` : '') +
    (name !== 'zones' ? `&store=${name}` : '');
}

// ---- keys
window.addEventListener('keydown', async e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  // **The kind picker eats the next key, ahead of everything.** It is armed by
  // `leaf_kind` and its letters collide with the zone type keys on purpose — `p`
  // is both `plate` here and a paragraph band there — so it has to be answered
  // before the type map is consulted, exactly as the armed caption corner wins
  // over a resize handle on the figure track. Escape leaves the ruling alone.
  if (S.pendingKind) {
    S.pendingKind = false;
    if (k === 'Escape') { say('leaf unchanged'); e.preventDefault(); return; }
    const hit = (CFG.leaf_kinds || []).find(x => x.key === k.toLowerCase());
    if (!hit) { say(`${k} names no leaf kind`, 'bad'); e.preventDefault(); return; }
    S.split = hit.kind; S.dirty = true; S.issues = [];
    say(`ruled ${hit.kind} — not a text page`, 'ok');
    render(); e.preventDefault(); return;
  }
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
  // On the figure track the type keys select a figure type and the zone types are
  // out of reach — one keyboard, but the track decides which half of it is live,
  // so `p` cannot place a paragraph band while somebody is drawing pictures.
  if (S.figTrack && FKEY[k]) {
    if (S.figSel >= 0) { S.figs[S.figSel].label = FKEY[k]; S.figsDirty = true; }
    else { S.figCur = FKEY[k]; S.figPending = null; }
    render(); e.preventDefault(); return;
  }
  if (!S.figTrack && KEY[k]) {
    S.cur = KEY[k]; S.issues = []; render(); e.preventDefault(); return;
  }
  // A named key carries its shift as a prefix, since it has no case to carry it in.
  // Looked up before the bare name, so `Shift+ArrowUp` cannot fall through to
  // whatever plain `ArrowUp` does — the two are a selection and a resize.
  const a = (e.shiftKey && k.length > 1 && ACT['Shift+' + k])
          || ACT[k] || ACT[k.toLowerCase()];
  if (!a) return;
  e.preventDefault();
  switch (a) {
    case 'toggle_track': {
      S.figTrack = !S.figTrack;
      // Each track drops whatever it had half-placed. Carrying an armed anchor
      // across the switch would fire it on a click meant for the other track.
      S.pending = null; S.sel = -1; S.figPending = null; S.figSel = -1;
      if (S.figTrack && !S.figCur) S.figCur = 'GraphicZone';
      // Announced, because the visible consequence of the switch is that
      // something *stops*: the zone preview no longer follows the cursor. Silence
      // there reads as a freeze rather than a mode.
      const ft = S.figTrack && FT[S.figCur];
      say(S.figTrack
          ? `figure track — drag to draw a ${ft ? ft.name : 'box'}`
          : 'zone track — click a top, then a bottom', 'ok');
      break; }
    case 'caption_beside':
      // Moves the armed corner to the picture's top-right, for the ~19 plate
      // captions this book sets vertically beside their picture rather than
      // under it. Only ever re-poses the corner; it commits nothing.
      S.capBeside = !S.capBeside;
      if (S.figPending && S.figPending.from) armCaption(S.figPending.from);
      break;
    case 'cancel': S.pending = null; S.sel = -1; S.figPending = null; break;
    case 'undo':
      if (S.zones.length) {
        S.zones.pop(); S.dirty = true; S.issues = []; S.sel = -1;
        const last = S.zones[S.zones.length - 1];
        S.pending = S.chain && last ? resume(last.label, last.y1) : null;
      }
      break;
    case 'delete': {
      if (S.figTrack) {
        const j = S.figSel >= 0 ? S.figSel : S.figHover;
        if (j < 0) break;
        S.figs.splice(j, 1);
        S.figSel = -1; S.figHover = -1; S.figPending = null; S.figsDirty = true;
        break;
      }
      const i = target();
      if (i < 0) break;
      S.zones.splice(i, 1);
      // Both cleared: every index above the removed one has shifted, so keeping
      // either would point at a different zone than the one that was targeted.
      S.sel = -1; S.hover = -1; S.dirty = true; S.issues = [];
      break; }
    // Absorb the zone below into this one. The commonest correction on a machine
    // page by a long way — 42% of gt boundaries are same-label, so the paragraph
    // rule and the decoder both over-split, and re-drawing the pair by hand is four
    // clicks for a boundary that just needs to go.
    //
    // **The surviving label is this zone's**, always, including where the two
    // differ. The alternative is to refuse a mixed merge, which would be the tool
    // declining exactly the case worth having it for — `MainZone-P` swallowing the
    // `MainZone-Continued` under it is a paragraph the decoder split in two.
    case 'merge_down': {
      const i = target();
      if (i < 0) { say('nothing selected to merge', 'bad'); break; }
      const j = below(i);
      if (j < 0) { say('nothing below this zone', 'bad'); break; }
      const a1 = S.zones[i], b1 = S.zones[j];
      // Across columns the union is not a band of anything: on a two-column page
      // the zone below in reading order can be the head of the other column, and
      // merging them would produce geometry that means nothing on the paper.
      if (a1.column !== b1.column) {
        say('the zone below is in another column', 'bad'); break;
      }
      const label = a1.label;
      a1.y0 = Math.min(a1.y0, b1.y0); a1.y1 = Math.max(a1.y1, b1.y1);
      S.zones.splice(j, 1);
      // The array shifted under the selection if the absorbed zone sat earlier in
      // it — the drawing order and the reading order are not the same list.
      S.sel = j < i ? i - 1 : i;
      S.hover = -1; S.dirty = true; S.issues = [];
      say(b1.label === label ? 'merged' : `merged as ${label}`, 'ok');
      break; }
    case 'sel_up': stepSel(-1); break;
    case 'sel_down': stepSel(1); break;
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
      // train <-> eval, and nothing else. This used to walk on to `exempt`, back
      // when that was one value; the kinds are a different question and get their
      // own key. Two states here because this is the every-page act and a cycle
      // you have to press four times to get through is not a toggle.
      //
      // A leaf comes back into the tracks through this key too: cycling from a
      // kind lands on `train`, which is the only way to say "I was wrong, it is
      // prose after all".
      const order = CFG.text_splits;
      const i = order.indexOf(S.split);
      S.split = order[(i + 1) % order.length];
      S.dirty = true; S.issues = [];
      break; }
    case 'leaf_kind': {
      // **A picker, not a cycle.** Ruling what a leaf is happens once per leaf and
      // there are five answers; stepping through them would make the common case
      // (already ruled, just looking) cost four keystrokes to get back where it
      // started. The vocabulary comes from the server — see `zones_ui.state`.
      const kinds = CFG.leaf_kinds;
      say('what is this leaf? ' +
          kinds.map(k => `${k.key} ${k.kind}`).join('  ') +
          '  ·  Esc to cancel');
      S.pendingKind = true;
      break; }
    case 'toggle_chain': S.chain = !S.chain; break;
    case 'segment_page': {
      // Asks, for two reasons. It is shift+s, one key from `save`, and the two do
      // opposite things — one writes what you keyed into gt, the other replaces
      // this page's machine prediction. And it overwrites: any existing mz for the
      // page goes, including one you may have been comparing against.
      const had = ST.present && ST.present.mz;
      if (!confirm(
        `Run the segmenter on ${ST.ref}?\n\n`
        + `Writes mz/zones/`
        + (had ? `, replacing the ${had} zones already predicted for it` : '')
        + `. gt/zones/ is untouched.`)) { say('not segmented', 'bad'); break; }
      say('segmenting…');
      let res;
      // `single` and `force` both: the dialog above already said it replaces what
      // is there, and asking for this one page is what excuses a page ruled exempt.
      try { res = await post(B+'/predict',
                             {ref: ST.ref, force: true, single: true}); }
      catch (err) { say('segmenter: ' + err.message, 'bad'); break; }
      // Reload so the prediction is on screen, since the whole point was to look at
      // it. Writes `mz/zones/`; `gt` is untouched until you adopt.
      //
      // **Staying put where the view already answers `mz`.** On an unkeyed page the
      // view falls through to the machine store by its own rule, so pinning `mz`
      // adds nothing and costs the thing the view is for: navigate on to a keyed
      // neighbour with `mz` pinned and it opens blank, or worse, on that page's
      // prediction instead of the work already done. Pin only from a store that
      // would otherwise keep showing something else.
      say(`segmented: ${res.zones} zones`, 'ok');
      await navStore(ST.store === 'zones' && !ST.keyed ? 'zones' : 'mz');
      return;
    }
    case 'delete_page': {
      if (!ST.keyed) { say('nothing keyed for this page', 'bad'); break; }
      // Typed, not pressed. The other destructive key here (`x`) removes one zone
      // and is undoable in the session; this removes the page from the tracked
      // store along with its split and every exemption, so it asks for the ref
      // itself rather than a click that a mis-hit could supply.
      const t = prompt(
        `Un-key ${ST.ref}? This deletes it from gt/zones/ and drops its split and `
        + `exemptions. Type the ref to confirm:`);
      if (t !== ST.ref) { say('not deleted', 'bad'); break; }
      const res = await post(B+'/delete', {ref: ST.ref});
      say(`deleted ${ST.ref} (was ${res.zones} zones)`, 'ok');
      // `ST` is the page as it was served; the file is gone now, so the flag has to
      // follow or a second `X` would ask to delete what is not there, and `save`
      // would think there was something to overwrite.
      ST.keyed = false;
      if (ST.present) ST.present.gt = null;
      ST.paras_zones = null;
      renderStores();
      S.zones = []; S.dirty = false; S.issues = []; S.split = 'train';
      break;
    }
    // Forward on `/`, back on `?`. One direction only meant that comparing two
    // stores — the thing the selector exists for — cost a full lap through the
    // third every time you wanted the previous one back.
    case 'cycle_store':
    case 'cycle_store_back': {
      const order = ['zones', 'gt', 'mz', 'paras'];
      const i = order.indexOf(ST.store);
      const step = a === 'cycle_store' ? 1 : order.length - 1;
      await navStore(order[(i + step) % order.length]);
      return;
    }
    // Renamed from `exempt`. That word named two unrelated things in one keymap —
    // this, which silences one *order rule* on one page, and the page's split,
    // which said the leaf was not text at all. The split half is now a leaf kind,
    // so the collision is worth closing rather than leaving one word doing both.
    case 'rule_exempt': {
      if (S.figTrack) {
        const g = figWarnings().find(w => !w.exempted);
        if (g) {
          /* **The reason is asked for, and no reason means no exemption.** The
             store keeps `{rule: ruling}` and `set_rule_exempt` refuses a blank
             one, on `zones.set_ink_exempt`'s rule that "a reason is required and
             is the point of the file". A bare id records that somebody silenced a
             warning and nothing about why, which a later reader cannot tell from
             a considered judgement. Cancelling leaves the warning standing. */
          const why = (window.prompt(`Ruling for ${g.rule} — why is this all
right on this page?`) || '').trim();
          if (!why) { say('not exempted: a ruling is required', 'warn'); break; }
          S.figExempt[g.rule] = why; S.figsDirty = true;
          say(`ruled ${g.rule}`, 'ok');
        }
        else if (Object.keys(S.figExempt).length) {
          S.figExempt = {}; S.figsDirty = true;
          say('figure exemptions cleared', 'ok');
        }
        break;
      }
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
      // A shared boundary moves whole, so the partition never opens an overlap —
      // but only edges that genuinely coincide are shared. A neighbour across a gap
      // stays put, which is what lets a nudge close one. With a zone selected but
      // the cursor elsewhere, the bottom edge is the one meant.
      const edge = S.hoverY === null || S.hover !== i
                 ? 'y1' : nearestEdge(i, S.hoverY);
      const at = S.zones[i][edge];
      for (const g of edgesSharing(at)) {
        const z = S.zones[g.i];
        if (g.edge === 'y0') z.y0 = Math.min(z.y0 + d, z.y1 - 4);
        else z.y1 = Math.max(z.y1 + d, z.y0 + 4);
      }
      S.dirty = true; S.issues = [];
      break; }
    case 'page_list':
      // Save first: the list reports what is on disk, so walking to it with
      // unsaved work would show this page as it was before the last few zones.
      if (S.dirty || S.figsDirty) { try { await save(); } catch (err) {
        say('not saved: ' + err.message, 'bad'); return; } }
      location = `${B}/list?ref=${ST.ref}`;
      return;
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
  try { if (S.dirty || S.figsDirty) await save(); } catch (err) {
    say('not saved — not stopping: ' + err.message, 'bad'); return; }
  await post(B+'/done', {});
  say('server stopped — you can close this tab', 'ok');
}

img.addEventListener('load', centreColumn);
document.querySelectorAll('.tk').forEach(el =>
  el.addEventListener('click', () => { S.cur = el.dataset.label; render(); }));
document.getElementById('btnsave').addEventListener('click',
  () => save().catch(err => say(err.message, 'bad')));
document.getElementById('btndone').addEventListener('click', done);
document.querySelectorAll('.pill.store').forEach(el =>
  el.addEventListener('click', () => navStore(el.dataset.store)));
window.addEventListener('resize', render);
window.addEventListener('beforeunload', e => {
  if (S.dirty || S.figsDirty) { e.preventDefault(); e.returnValue = ''; }
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
