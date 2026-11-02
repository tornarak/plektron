/* A selection of places, composed into one map — in the page, for any host.
 *
 * **The composition lives here and nowhere else; the facts do not.** Everything
 * a map is made of that the store can answer about one entity on its own — how
 * big it is, what lies beneath it with a shape, what holds it, how well founded
 * its outline is — arrives precomputed in `atlas.json`
 * (`edition_ui.atlas_data`), each from the Python function that owns the rule.
 * What is done here is only what depends on the *selection*: which members
 * join it, the frame and the sheet, the layers, the pins, the tree and the
 * picture. It used to be the server's (`map_context`), which meant a static
 * host could show one pre-drawn place at a time and nothing else.
 *
 * Shapes are asked for by id through `shape(sid)`, synchronously, and a shape
 * not yet in hand reads as empty — so a caller runs `compose` once to learn
 * what it asks for, fetches that, and runs it again. One walk, with no second
 * copy of "which shapes does this map need" to fall out of step with the first.
 *
 * Numbers are written exactly as the Python that this replaced wrote them
 * (`fixed`), so a map is the same bytes whichever side drew it.
 */

/* --- the projection ---
 *
 * **Equidistant cylindrical, standard parallel per map.** x is longitude scaled
 * by cos of the frame's mid-latitude, y is latitude, so a lat/lon box is a
 * rectangle — the property the whole frame mechanism rests on. It replaced a
 * Lambert azimuthal projection under which the west bound of the Northeast
 * Siberia box projected twice as far out at its southern end as at its northern
 * one; `docs/decisions.md` has the trade. */

/* Layer order, back to front. `extents` last because only the highlight paints
   it, and a highlight under the shapes it picks out would be no highlight. */
export const LAYERS = ['land', 'lakes', 'kin', 'members', 'parent', 'subject',
                       'rivers', 'extents'];
/* Padding round the framed extent, as a fraction of the larger dimension. */
export const PAD = 0.06;
/* Below this many projected units a frame is widened: a point has no extent. */
export const MIN_SPAN = 0.02;
/* Pin and label sizes as fractions of the **view's** longer side, so a marker
   keeps its size whatever the frame. They travel on the root element
   (`data-pin`) for `map.js`, which redoes the label placement on a re-frame. */
export const PIN = {r: 0.012, dx: 1.4, dy: 0.5, font: 2.2, flip: 0.72};
/* Every viewBox is this many units on its longer side, so one decimal place is
   right at every zoom. */
export const SPAN = 1000.0;
/* Half a viewBox of margin before a ring is culled as off-frame: a ring whose
   vertices all sit outside can still cross it. */
export const CULL = 1.0;

/* `x * DEG`, not `x * PI / 180`: CPython's `math.radians` multiplies by the
   one constant, and the two round differently in the last place. */
const DEG = Math.PI / 180;

/* Python's float `%`: the sign of the divisor. */
function pymod(a, b) {
  const m = a % b;
  return m !== 0 && (m < 0) !== (b < 0) ? m + b : m;
}

export function project(lon, lat, lon0, lat0) {
  /* Wrapped into (−180, 180] so the antimeridian has no seam: a cylindrical
     projection is linear in longitude, and Chukotka crosses 180. */
  const dl = pymod(lon - lon0 + 180.0, 360.0) - 180.0;
  return [dl * DEG * Math.cos(lat0 * DEG), -(lat * DEG)];
}

export function unionBox(boxes) {
  const bs = boxes.filter(Boolean);
  if (!bs.length) return null;
  return [Math.min(...bs.map(b => b[0])), Math.min(...bs.map(b => b[1])),
          Math.max(...bs.map(b => b[2])), Math.max(...bs.map(b => b[3]))];
}

/* `f"{v:.{d}f}"`. `toFixed` agrees except on an exact tie, where Python rounds
   half to even and `toFixed` rounds away from zero — and `x.25` is a tie that
   real coordinates hit. The tie is found on the exact expansion of the double,
   which `toFixed` gives to any length, never on `v * 10`, which rounds. */
export function fixed(v, d) {
  const exact = Math.abs(v).toFixed(60);
  const dot = exact.indexOf('.');
  const tail = exact.slice(dot + 1 + d);
  if (!(tail[0] === '5' && /^0*$/.test(tail.slice(1)))) return v.toFixed(d);
  const digits = (exact.slice(0, dot) + exact.slice(dot + 1, dot + 1 + d))
      .replace(/^0+(?=\d)/, '');
  let n = BigInt(digits);
  if (n % 2n) n += 1n;
  let s = n.toString().padStart(d + 1, '0');
  if (d) s = s.slice(0, -d) + '.' + s.slice(-d);
  return (v < 0 ? '-' : '') + s;
}

/* One decimal, trailing zeros dropped, and never `-0`, which is what a frame's
   own left edge rounds to and which is legible nowhere. */
export function fmt(v) {
  let s = fixed(v, 1);
  if (s.includes('.')) s = s.replace(/0+$/, '').replace(/\.$/, '');
  return s === '-0' || s === '' ? '0' : s;
}

function pathD(points, close) {
  if (!points.length) return '';
  return 'M' + points.map(([x, y]) => `${fmt(x)},${fmt(y)}`).join(' L')
      + (close ? 'Z' : '');
}

/* `geo.rings` and `geo.lines`: Polygon and MultiPolygon flattened together;
   rivers are the `rivers` layer's lines with their Strahler order. */
export function rings(doc) {
  const out = [];
  for (const f of (doc && doc.features) || []) {
    const g = f.geometry;
    const polys = g.type === 'Polygon' ? [g.coordinates]
        : g.type === 'MultiPolygon' ? g.coordinates : [];
    for (const poly of polys) for (const ring of poly) out.push(ring);
  }
  return out;
}

function lines(doc) {
  const out = [];
  for (const f of (doc && doc.features) || []) {
    if ((f.properties || {}).layer !== 'rivers') continue;
    const g = f.geometry;
    const parts = g.type === 'LineString' ? [g.coordinates]
        : g.type === 'MultiLineString' ? g.coordinates : [];
    for (const part of parts) out.push([part, f.properties.sorder || 0]);
  }
  return out;
}

const STEPS = 24;

/* A lon/lat box walked along its edges. The corners alone under-report a
   curved edge: at these latitudes the top of a wide box bows past them. */
function edges(box) {
  const [w, s, e, n] = box, out = [];
  for (let i = 0; i <= STEPS; i++) {
    const t = i / STEPS;
    out.push([w + (e - w) * t, s], [w + (e - w) * t, n],
             [w, s + (n - s) * t], [e, s + (n - s) * t]);
  }
  return out;
}

/* A projection centre plus the projected extent it draws into — the *sheet*
   when the caller is drawing one, wider than the view it opens on. */
export class Frame {
  constructor(box) {
    this.box = box;
    this.lon0 = (box[0] + box[2]) / 2.0;
    this.lat0 = (box[1] + box[3]) / 2.0;
    const ps = edges(box).map(([lon, lat]) => project(lon, lat, this.lon0, this.lat0));
    const xs = ps.map(p => p[0]), ys = ps.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);
    /* The viewBox takes the frame's own aspect and the scale its longer side:
       a square box padded a wide frame with empty sea above and below. */
    const wp = Math.max(x1 - x0, MIN_SPAN) * (1 + 2 * PAD);
    const hp = Math.max(y1 - y0, MIN_SPAN) * (1 + 2 * PAD);
    this.scale = SPAN / Math.max(wp, hp);
    this.width = wp * this.scale;
    this.height = hp * this.scale;
    this.cx = (x0 + x1) / 2;
    this.cy = (y0 + y1) / 2;
    this.viewbox = `0 0 ${fmt(this.width)} ${fmt(this.height)}`;
  }

  at(lon, lat) {
    const [x, y] = project(lon, lat, this.lon0, this.lat0);
    return [this.width / 2 + (x - this.cx) * this.scale,
            this.height / 2 + (y - this.cy) * this.scale];
  }

  /* One ring's points, or null if it cannot touch the frame. The cull is the
     difference between a 130 KB map and an 8 KB one. Per axis, since the
     viewBox is not square. */
  ring(ring) {
    const pts = ring.map(c => this.at(c[0], c[1]));
    if (!pts.length) return null;
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    if (Math.max(...xs) < -CULL * this.width
        || Math.min(...xs) > (1 + CULL) * this.width
        || Math.max(...ys) < -CULL * this.height
        || Math.min(...ys) > (1 + CULL) * this.height) return null;
    return pts;
  }

  paths(doc) {
    const out = [];
    for (const r of rings(doc)) {
      const pts = this.ring(r), d = pts && pathD(pts, true);
      if (d) out.push(d);
    }
    return out;
  }

  rivers(doc) {
    const out = [];
    for (const [line, order] of lines(doc)) {
      const pts = this.ring(line), d = pts && pathD(pts, false);
      if (d) out.push([d, order]);
    }
    return out;
  }

  /* A lon/lat box as a closed ring — an extent, drawn. */
  viewport(box) {
    const [w, s, e, n] = box, edge = [];
    for (let i = 0; i <= STEPS; i++) edge.push([w + (e - w) * i / STEPS, s]);
    for (let i = 1; i <= STEPS; i++) edge.push([e, s + (n - s) * i / STEPS]);
    for (let i = 1; i <= STEPS; i++) edge.push([e - (e - w) * i / STEPS, n]);
    for (let i = 1; i <= STEPS; i++) edge.push([w, n - (n - s) * i / STEPS]);
    const pts = this.ring(edge);
    return pts ? pathD(pts, true) : '';
  }

  point(lon, lat) { return this.at(lon, lat); }

  /* A lon/lat box as `[x, y, w, h]` in this frame's units, padded per axis as
     the sheet is — so the sheet's own box is the whole viewBox. What lets
     `map.js` re-frame by writing a `viewBox` and projecting nothing. */
  rect(box) {
    const pts = edges(box).map(([lon, lat]) => this.at(lon, lat));
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);
    const dx = Math.max(x1 - x0, MIN_SPAN * this.scale) * PAD;
    const dy = Math.max(y1 - y0, MIN_SPAN * this.scale) * PAD;
    return [x0 - dx, y0 - dy, (x1 - x0) + 2 * dx, (y1 - y0) + 2 * dy];
  }
}

const rectStr = r => r ? r.map(v => fixed(v, 1)).join(' ') : '';

/* `html.escape`, quotes included — every string that reaches markup. */
export function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
}

/* `Frame.paths` output tagged with the entity it belongs to and the *shape's*
   kind — whether a boundary is a drainage divide, open water or a speaker area
   is a fact about where the polygon came from, and the entity class cannot
   say it. The empty string is honest for the coastline, which no record owns. */
export const owned = (paths, ent = '', kind = '') => paths.map(d => [d, ent, kind]);

/* One map. **Every path says whose it is**, which is what makes the map
   answerable: nothing about a path's geometry leads back to a record. Rivers
   arrive as `[d, order]` so the trunk can be drawn heavier. `view` is the
   rectangle to open on in sheet units; `data-sheet` is the widest frame the
   drawing supports. `mark` is the caller's to set — inferring a basin from the
   shape of a ring is the guess this project refuses. */
export function render(frame, layers, pins = [], mark = '', view = null) {
  const of = (ent, kind = '') => (ent ? ` data-ent='${esc(ent)}'` : '')
      + (kind ? ` data-kind='${esc(kind)}'` : '');
  const parts = [];
  for (const name of LAYERS) {
    const got = layers[name];
    if (!got || !got.length) continue;
    if (name === 'rivers') {
      const top = Math.max(...got.map(([, s]) => s));
      parts.push("<g class='rivers'>" + got.map(([d, s]) => s >= top - 1
          ? `<path d='${d}' style='stroke-width:${fixed(0.10 + 0.10 * (s - top + 2), 2)}%'/>`
          : `<path d='${d}'/>`).join('') + '</g>');
    } else {
      parts.push(`<g class='${name}'>`
          + got.map(([d, e, k]) => `<path d='${d}'${of(e, k)}/>`).join('') + '</g>');
    }
  }
  const [vx, vy, vw, vh] = view || [0.0, 0.0, frame.width, frame.height];
  const r = Math.max(vw, vh) * PIN.r;
  for (const [x, y, label, ent] of pins) {
    parts.push(`<circle class='pin'${of(ent)} cx='${fmt(x)}' cy='${fmt(y)}' r='${fixed(r, 1)}'/>`);
    if (!label) continue;
    /* Turned inward near the right edge of the *view*: a truncated place name
       reads as a data problem. `data-x`/`data-y` let `map.js` redo this one
       decision after a re-frame. */
    const flip = x > vx + vw * PIN.flip;
    parts.push(`<text class='pin-label' data-x='${fmt(x)}' data-y='${fmt(y)}' `
        + `x='${fmt(x + (flip ? -r * PIN.dx : r * PIN.dx))}' `
        + `y='${fmt(y + r * PIN.dy)}' `
        + `text-anchor='${flip ? 'end' : 'start'}' `
        + `font-size='${fixed(r * PIN.font, 1)}'>${esc(label)}</text>`);
  }
  /* Spelled as Python's `json.dumps` spelled it, so the bytes do not depend on
     which side drew the map. */
  const pin = JSON.stringify(PIN).replace(/([:,])/g, '$1 ');
  return `<svg class='map${mark ? ' ' + esc(mark) : ''}' `
      + `viewBox='${fmt(vx)} ${fmt(vy)} ${fmt(vw)} ${fmt(vh)}' `
      + `data-sheet='${frame.viewbox}' data-pin='${esc(pin)}' `
      + "preserveAspectRatio='xMidYMid meet' role='img'>" + parts.join('') + '</svg>';
}

/* --- composition --- */

const uniq = xs => [...new Set(xs)];
const kindOf = sid => sid.split(':')[0];
const hasDoc = d => !!d && Object.keys(d).length > 0;
/* Python's ordering of `(bool, str, str)` tuples: False first, then by code
   point. Plain `<` on strings is by UTF-16 unit, which is the same order for
   everything outside the astral planes, and no name here is in them. */
function cmp(a, b) {
  for (let i = 0; i < a.length; i++) {
    if (a[i] < b[i]) return -1;
    if (a[i] > b[i]) return 1;
  }
  return 0;
}

/* **A legend for the map: every record it drew, and what holds them** — from
   the first common ancestor of the selection down through the branches that
   reach everything drawn, plus the direct children of a chosen node whether
   drawn or not, which is the drill-down. What is on the map is open, what is
   merely on offer is folded; a node carrying a selection and a
   non-geographical child are never folded. Hidden nodes stay, so a click can
   undo the hiding. */
function mapTree(atlas, sel, hidden, order, onMap) {
  const E = atlas.entities, GEO = new Set(atlas.geo_classes);
  const offered = sel.flatMap(i => E[i].children).filter(k => k in E);
  const stop = order[0] || '';
  const nodes = new Set([...sel, ...onMap, ...offered].filter(i => i in E));
  for (const i of [...nodes]) {
    let chain = E[i].ancestors;
    if (stop) {
      /* A node that *is* the root climbs no further, and one not under the
         root is its own root. */
      if (i === stop || !chain.includes(stop)) continue;
      chain = chain.slice(0, chain.indexOf(stop) + 1);
    }
    for (const a of chain) nodes.add(a);
  }
  const kids = {};
  for (const n of nodes) {
    const up = E[n].parent;
    if (nodes.has(up)) (kids[up] = kids[up] || []).push(n);
  }
  /* Non-geographical rows first — a people is an overlay on the containment
     tree, not another rung of it — then by the name a reader sees. */
  const rank = id => [GEO.has(E[id].cls), E[id].canonical, id];
  const byName = ids => [...ids].sort((a, b) => cmp(rank(a), rank(b)));
  const shown = c => [GEO.has(c.cls), !c.selected, c.canonical];
  const build = id => {
    const rec = E[id], chosen = sel.includes(id);
    const below = byName(kids[id] || []).map(build);
    const open = [], folded = [];
    for (const c of below)
      (c.carries || c.drawn || !GEO.has(c.cls) ? open : folded).push(c);
    open.sort((a, b) => cmp(shown(a), shown(b)));
    return {id, canonical: rec.canonical, cls: rec.cls, selected: chosen,
            hidden: hidden.has(id), drawn: onMap.has(id),
            carries: chosen || below.some(c => c.carries),
            children: open, folded};
  };
  const built = byName([...nodes].filter(n => !nodes.has(E[n].parent))).map(build);
  return built.sort((a, b) => cmp(shown(a), shown(b)));
}

/* What contains every one of these, strictly and nearest first — over the
   first one's chain, so "the first common ancestor" is one node. */
function commonAncestors(atlas, ids) {
  if (!ids.length) return [];
  const E = atlas.entities;
  const chains = ids.slice(1).map(i => new Set(E[i].ancestors));
  return E[ids[0]].ancestors.filter(a => chains.every(c => c.has(a)));
}

/* A selection on one map, with the tree that frames it.
 *
 * `sel` is what the reader chose, `hidden` what they asked not to be painted
 * (drawn, and not framed on), `dropped` what they took off that a rule would
 * otherwise put back. */
export function compose(atlas, shape, sel, hidden = new Set(), dropped = new Set()) {
  const E = atlas.entities;
  sel = uniq(sel);
  const out = {ident: sel[0] || '', rec: null, svg: '', parent: null, basis: {},
               absent_note: '', warm: [], subjects: [], drawn: [], tree: [],
               frames: {order: [], box: {}, own: {}}};
  let known = sel.filter(i => i in E);
  if (!known.length) return out;
  /* **A `geo:` member joins the selection, unless it was dropped.** The map of
     a people that names its villages *is* those villages, so they are subjects:
     pinned, named in the tree as chosen, and each can be taken off again —
     which is why dismissal has to be said out loud, or this rule re-derives
     over it. One level, not transitively. */
  known = uniq([...known, ...known.flatMap(i => E[i].refs)
                                  .filter(m => m in E && !dropped.has(m))]);
  /* A hidden node is drawn and not painted: `hidden` changes the framing
     here and nothing else. */
  const live = known.filter(i => !hidden.has(i));
  const boxes = Object.fromEntries(known.map(i => [i, E[i].own]));
  out.drawn = known.filter(i => boxes[i]);
  /* Everything one step from here, not everything drawn: the map is the
     authority on what can be highlighted, not on what a reader is about to
     open. A `geo:` member is drawn and clickable, so it is warmed too. */
  const warm = new Set(known.flatMap(i => [...E[i].relatives, ...E[i].refs]));
  out.warm = [...warm].filter(w => !known.includes(w)).sort();

  const solo = known.length === 1 ? known[0] : '';
  const rec = solo ? {id: solo, ...E[solo]} : null;
  out.rec = rec;
  out.subjects = known.map(i => ({id: i, rec: {id: i, ...E[i]}, hidden: hidden.has(i),
                                  drawn: !!boxes[i], basis: E[i].basis}));
  if (rec) out.basis = rec.basis;
  const order = commonAncestors(atlas, known).filter(a => a in E);

  if (!known.some(i => boxes[i])) {
    /* The tree is built anyway: it is the only way back to a node. */
    out.tree = mapTree(atlas, known, hidden, order, new Set());
    if (rec) out.absent_note = rec.absent;
    return out;
  }

  /* **The frame is the box that holds what is selected, and nothing else** —
     context is selected, not assumed. A declared `frame:` on the one selected
     entity still wins: that field says "look at this box" about this map. */
  const cand = solo && E[solo].frame ? [solo] : [];
  let frameBox = cand.filter(a => !hidden.has(a)).map(a => E[a].frame)[0] || null;
  if (!frameBox)
    frameBox = unionBox(live.map(i => boxes[i])) || unionBox(Object.values(boxes));
  /* The sheet: every frame the reader can reach without asking again. */
  const sheet = unionBox([frameBox, ...Object.values(boxes), ...cand.map(a => E[a].frame)]);
  const frame = new Frame(sheet);
  const view = frame.rect(frameBox);
  out.frames = {
    order: [...cand],
    box: Object.fromEntries(cand.map(a => [a, rectStr(frame.rect(E[a].frame))])),
    own: Object.fromEntries(Object.entries(boxes).filter(([, b]) => b)
                                  .map(([i, b]) => [i, rectStr(frame.rect(b))])),
  };

  /* **Every record the map draws, collected as it is drawn** — the tree is a
     legend for this picture, so it is built from it and not from a second walk. */
  const onMap = new Set();
  const own = (paths, ent = '', kind = '') => {
    if (ent) onMap.add(ent);
    return owned(paths, ent, kind);
  };
  const drawShapes = id => E[id].shapes.flatMap(
      sid => own(frame.paths(shape(sid)), id, kindOf(sid)));

  const layers = {};
  for (const [name, id] of [['land', 'base:land'], ['lakes', 'base:lakes']]) {
    if (!(atlas.base || []).includes(id)) continue;
    const doc = shape(id);
    if (hasDoc(doc)) layers[name] = own(frame.paths(doc));
  }
  /* Siblings before the parent outline before the subject — and only for a
     single subject: once several are on the map the selection is the context. */
  const up = solo ? E[solo].parent : '';
  const kin = up && E[up] ? E[up].children.filter(k => k !== solo && E[k].shapes.length) : [];
  if (kin.length) layers.kin = kin.flatMap(k => drawShapes(k));
  /* The tree's root, dashed, as pure context; skipped when hidden. */
  const holder = order.slice(0, 1).find(a => !hidden.has(a)) || '';
  if (holder && E[holder].shapes.length) {
    layers.parent = drawShapes(holder);
    out.parent = {id: holder, ...E[holder]};
  }
  /* **An inherited extent is drawn as what it is: someone else's outline,
     dashed.** A subgroup with no shape and no village — the Reindeer Chukchi,
     the Kavraˊlɪt — is framed on its people's extent (`_basis` says
     `inherited`), and that people is reached by `part-of:`, which the holder
     above never sees: it climbs `within:`. So the map framed the right box and
     drew nothing in it, under a caption naming an extent that was not there.
     Context and not subject, because it bounds the subgroup without being a
     boundary anybody claimed for it. */
  const lent = new Set(live.map(i => E[i].basis).filter(b => b.kind === 'inherited')
                           .map(b => b.id)
                           .filter(id => id in E && id !== holder && !known.includes(id)));
  for (const id of lent) layers.parent = [...(layers.parent || []), ...drawShapes(id)];
  /* A place drawn twice is drawn once, as the subject. */
  const drawn = new Set(), subject = [];
  for (const i of known)
    for (const sid of E[i].shapes) {
      subject.push(...own(frame.paths(shape(sid)), i, kindOf(sid)));
      drawn.add(i);
    }
  if (subject.length) layers.subject = subject;
  /* What lies beneath, drawn: for a node with no boundary of its own this is
     the whole map. */
  const members = [];
  for (const i of known)
    for (const [ent, sid] of E[i].members) {
      if (drawn.has(ent)) continue;
      drawn.add(ent);
      members.push(...own(frame.paths(shape(sid)), ent, kindOf(sid)));
    }
  if (members.length) layers.members = members;
  /* The subjects' own drainage, or — when not one has a shape — the holder's. */
  if (known.some(i => E[i].shapes.length)) {
    const rivers = known.flatMap(i => E[i].shapes.flatMap(sid => frame.rivers(shape(sid))));
    if (rivers.length) layers.rivers = rivers;
  } else if (holder && E[holder].shapes.length) {
    layers.rivers = E[holder].shapes.flatMap(sid => frame.rivers(shape(sid)));
  }
  /* Every descendant no other layer identifies, as an extent — transparent
     until the highlight paints it. */
  const extents = [], seen = new Set();
  for (const i of known)
    for (const [ent, box] of E[i].extents) {
      if (drawn.has(ent) || seen.has(ent)) continue;
      seen.add(ent);
      const d = frame.viewport(box);
      if (d) extents.push(...own([d], ent));
    }
  layers.extents = extents;
  /* **A pin for a place that was chosen, and for no other.** */
  const pins = [], plotted = new Set();
  for (const i of known)
    for (const [lon, lat] of E[i].points) {
      if (plotted.has(i)) continue;
      plotted.add(i);
      const [x, y] = frame.point(lon, lat);
      pins.push([x, y, E[i].canonical, i]);
      onMap.add(i);
    }

  out.tree = mapTree(atlas, known, hidden, order, onMap);
  /* `basin` off the shape's type, for every live subject — and `every` on an
     empty list is true, so emptiness is tested first. */
  const shapes = live.flatMap(i => E[i].shapes);
  const mark = shapes.length && shapes.every(s => s.startsWith('watershed:')) ? 'basin' : '';
  out.svg = render(frame, layers, pins, mark, view);
  return out;
}

/* --- the pane --- */

/* What `edition/_map.html` was. Every interpolation goes through `esc`, and the
   SVG is the one piece that is markup by design. */
export function paneHtml(ctx, base) {
  const ref = id => `${base}/entity/${encodeURI(id)}`;
  let h = '';
  /* Who to fetch, which is not the set of `data-ent`s below: those are what can
     be highlighted. */
  if (ctx.warm.length) h += `<span hidden class='warm' data-warm='${esc(ctx.warm.join(' '))}'></span>`;
  /* What the map accepted, which is not what was asked for: the click falls
     back to the card when its place is not in here. */
  h += `<span hidden class='drawn' data-drawn='${esc(ctx.drawn.join(' '))}' `
     + `data-sel='${esc(ctx.subjects.map(s => s.id).join(' '))}'></span>`;
  if (!ctx.subjects.length) return h + `<p>No entry for <code>${esc(ctx.ident)}</code>.</p>`;
  const rec = ctx.rec;
  h += rec ? `<h4>${esc(rec.canonical)}</h4>` : `<h4>${ctx.subjects.length} places</h4>`;
  if (!ctx.svg) {
    h += "<p class='meta'>" + (rec
        ? 'Nothing to draw: no location is recorded for this or for anything beneath it.'
          + (ctx.absent_note ? ' ' + esc(ctx.absent_note) : '')
        : 'Nothing to draw: everything on this map is hidden, or has no location recorded.')
        + '</p>';
  } else {
    if (rec) h += `<div class='meta'>${basisHtml(ctx.basis)}${ctx.parent
        ? ` · inside <a class='ent' data-ref='${esc(ctx.parent.id)}' href='${esc(ref(ctx.parent.id))}'>`
          + `${esc(ctx.parent.canonical)}</a>` : ''}</div>`;
    h += ctx.svg;
  }
  /* **The name toggles, the `¶` reads, the `●` paints.** A fold is a
     `<details>`, which opens with no script; `data-fold` is what `map.js`
     reopens it by after a repaint. */
  const node = n => {
    const id = esc(n.id), href = esc(ref(n.id));
    let li = `<li class='${n.selected ? 'sel' : ''} ${n.hidden ? 'off' : ''}'>`
        + `<a class='entry' data-ref='${id}' href='${href}' title='the entry'
            aria-label='the entry'>&para;</a>`
        + `<button class='hide' data-ref='${id}' title='${n.hidden ? 'paint this again'
            : 'do not paint this'}' aria-label='${n.hidden ? 'paint this again'
            : 'do not paint this'}'>${n.hidden ? '◌' : '●'}</button>`
        + `<a class='node' data-ref='${id}' href='${href}'>${esc(n.canonical)}</a> `
        + `<span class='pill cls' data-ref='${id}'>${esc(n.cls)}</span>`;
    if (n.children.length || n.folded.length) {
      li += '<ul>' + n.children.map(node).join('');
      if (n.folded.length)
        li += `<li class='more'><details data-fold='${id}'><summary>${n.folded.length} more`
            + `</summary><ul>${n.folded.map(node).join('')}</ul></details></li>`;
      li += '</ul>';
    }
    return li + '</li>';
  };
  /* `data-frames` is the frame rule's answer — candidates in order plus each
     subject's own box, all in sheet units — so hiding is a `viewBox` rewrite. */
  if (ctx.tree.length)
    h += `<div class='ent-tree map-tree' data-frames='${esc(JSON.stringify(ctx.frames))}'>`
       + `<ul>${ctx.tree.map(node).join('')}</ul></div>`;
  return h;
}

/* The caption says how well founded the outline is, and the last branch tests
   its kind rather than assuming it: a caption that asserts on behalf of kinds
   it has never heard of renders a lie with no error. */
function basisHtml(b) {
  const more = b.more ? ` and ${b.more} more` : '';
  switch (b.kind) {
    case 'shape':
      return `${esc(b.name || 'outline')}${b.km2 ? ` · ${esc(b.km2)} km²` : ''} · `
          + `${esc(b.source)}${b.more ? ` · and ${b.more} more` : ''}`;
    case 'point':
      return `a point at ${esc(b.lat)}, ${esc(b.lon)} — no source draws a boundary for it`;
    case 'transcluded':
      return `shown at the extent of ${esc(b.name)}${more} — the boundary drawn is `
          + 'theirs and not one claimed for this';
    case 'inherited':
      return `shown at the extent of ${esc(b.name)} — a subgroup lives inside `
          + "its people's area, so this bounds it without drawing a boundary anybody "
          + 'has claimed';
    case 'framed':
      return 'framed by what lies beneath it — no source draws a boundary for this';
    default:
      return '';
  }
}
