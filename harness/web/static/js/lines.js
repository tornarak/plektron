const S = STATE, VIEW = CFG.view;
// Every URL below is relative to this. The four editors share one server now and
// each is mounted under its own prefix, so a bare '/save' would post to whichever
// tool happened to own the root — a wrong answer that looks like a working one.
// The server puts the prefix in the state blob rather than the file hardcoding
// it, because this file is a cached static asset and the prefix is the server's
// fact, not the script's.
const B = S.base;
let corr = S.corr.map(c => ({...c})), exempt = S.line_exempt.map(e => ({...e}));
let sel = null, dirty = false, blot = false, drag = null;
// The vpos of a band armed for the covered-by pick, or null. A mode, and the only
// one this editor has — held for exactly one click and cancelled by Escape, since
// a mode a human can forget they are in is how a drag becomes a ruling.
let covering = null;

const $ = s => document.querySelector(s);
const stage = $('#stage'), ov = $('#ov'), img = $('#img');

// **Zoom is not a convenience here, it is the instrument.** The thing being
// judged is a band of ink 43x36 px on a 2824x3897 leaf; fitted to the viewport
// that arrives about 17 px wide, which is too small to tell a numeral from a
// printed rule from a smudge — the one decision this editor exists to support.
// Steps of 1.25 from fit, persisted, and the same keys `zones edit` uses so the
// hand does not have to learn two tools.
let zoom = parseFloat(localStorage.getItem('linesZoom') || '0') || 0;

function fit() {
  const wrap = $('#wrap');
  const base = (wrap.clientWidth - 24) / S.w;
  const s = zoom ? base * Math.pow(VIEW.zoom_step, zoom) : base;
  const w = Math.max(120, Math.round(S.w * s));
  stage.style.width = w + 'px';
  stage.style.height = Math.round(S.h * s) + 'px';
  img.style.width = w + 'px';
  ov.setAttribute('viewBox', `0 0 ${S.w} ${S.h}`);
  $('#zl').textContent = (zoom ? Math.pow(VIEW.zoom_step, zoom) : 1).toFixed(2) + '×';
  return s;
}

// Keep whatever is selected — or the first band left to decide — in view after a
// zoom step, rather than dumping the human at the top of a page they were
// working the middle of.
function keepInView() {
  const wrap = $('#wrap');
  const t = (sel !== null && corr[sel])
    || S.bands.filter(b => !b.exempted)[0];
  if (!t) return;
  const y = (t.y0 !== undefined ? t.y0 : t.vpos), h = (t.y1 - t.y0) || t.height;
  const s = stage.clientHeight / S.h;
  wrap.scrollTop = Math.max(0, (y + h / 2) * s - wrap.clientHeight / 2);
  const x = (t.x0 !== undefined ? t.x0 : t.hpos), w = (t.x1 - t.x0) || t.width;
  wrap.scrollLeft = Math.max(0, (x + w / 2) * (stage.clientWidth / S.w)
                             - wrap.clientWidth / 2);
}

function setZoom(z) {
  zoom = Math.max(VIEW.zoom_min, Math.min(VIEW.zoom_max, z));
  localStorage.setItem('linesZoom', zoom);
  fit(); draw(); requestAnimationFrame(keepInView);
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

function rect(b, layer, title, attrs) {
  return `<rect x="${b.x0}" y="${b.y0}" width="${b.x1 - b.x0}" `
       + `height="${b.y1 - b.y0}" class="ly-${layer}" ${attrs || ''}>`
       + (title ? `<title>${esc(title)}</title>` : '') + '</rect>';
}
function band_(y0, y1, layer, title) {
  return `<rect x="0" y="${y0}" width="${S.w}" height="${y1 - y0}" `
       + `class="ly-${layer}"><title>${esc(title)}</title></rect>`;
}
function esc(s) {
  return String(s).replace(/[<>&"]/g, c =>
    ({'<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;'}[c]));
}

function draw() {
  let s = '';
  for (const z of S.zones) s += rect(z, 'zone', z.label);
  // While a band is armed for the covered-by pick, the store's lines stop being
  // context and become the control being operated: lit, hoverable, and carrying
  // the index and text that are the only way to tell which one is right.
  for (const l of S.lines)
    s += (covering === null
      ? rect(l, 'line')
      : rect(l, 'line_pick', 'line ' + l.index + ': ' + (l.text || '(empty)'),
             `data-l="${l.index}"`));
  for (const e of S.zone_exempt)
    s += band_(e.y0, e.y1, 'ruling_zone', 'zoning ruled this: ' + e.note);
  exempt.forEach(e => {
    s += (e.covered_by === undefined
      ? band_(e.y0, e.y1, 'ruling_line', 'not a line: ' + e.note)
      : band_(e.y0, e.y1, 'ruling_covered',
              'keyed in line ' + e.covered_by + ': ' + e.note));
  });
  for (const b of S.bands) {
    if (b.exempted) continue;
    if (ruled(b)) continue;
    if (corr.some(c => c.y0 < b.vpos + b.height && b.vpos < c.y1)) continue;
    const box = {x0: b.hpos, y0: b.vpos, x1: b.hpos + b.width,
                 y1: b.vpos + b.height};
    s += rect(box, b.zone ? 'band' : 'band_no_zone',
              b.zone || 'in no zone — a gap in the zoning, not a line',
              `data-v="${b.vpos}"`);
  }
  corr.forEach((c, i) => {
    s += rect(c, i === sel ? 'correction_selected'
                           : (inZone(c) ? 'correction' : 'band_no_zone'),
              inZone(c) ? '' : 'outside every zone — the save will refuse it',
              `data-i="${i}"`);
  });
  if (drag) s += rect(drag, 'drag');
  ov.innerHTML = s;
  $('#nc').textContent = corr.length;
  $('#nb').textContent = S.bands.filter(b => !b.exempted && !ruled(b)).length;
  $('#nx').textContent = exempt.length;
  $('#dirty').style.visibility = dirty ? 'visible' : 'hidden';
  drawRulings();
  if (window.syncControls) syncControls();
}

// A ruling this session has made over that band, if any. Local, because `exempt`
// is unsaved until the save lands — the page must show what it is about to write,
// not what it last read.
// **Any band, in a zone or not** — this layer is the last stage of accounting for
// the page's ink, so nothing on the leaf is out of its reach. Matches the server's
// rule exactly, and it has to: the page briefly disagreed with `/list` here, which
// is how `1-034` came to read "bands left: 0, ruled: 2" beside a list saying two
// were live.
function ruled(b) {
  const mid = b.vpos + b.height / 2;
  return exempt.find(e => e.y0 <= mid && mid <= e.y1);
}

// A ruling this session holds that settles no band on the page — stale geometry,
// or a band that stopped being one. Still listed, still withdrawable, and now said
// out loud rather than counted as if it had done something.
function dead(e) {
  return !S.bands.some(b => e.y0 <= b.vpos + b.height / 2
                         && b.vpos + b.height / 2 <= e.y1);
}

// **The rulings are listed, not only painted.** A note recorded once through a
// prompt and never shown again is a record nobody can check: the whole argument
// for requiring a reason is that a year from now it is the only thing separating
// a ruled artifact from a hidden mistake. So each is on the page with its reason
// and a way to take it back.
function drawRulings() {
  const el = $('#rulings');
  if (!exempt.length) {
    el.innerHTML = '<li class=none>none on this page</li>';
    return;
  }
  // The disposition is shown, not only the note. Two rulings suppress the same
  // band for opposite reasons — "this is not print" and "this is print, keyed in
  // line N" — and a list that renders them identically is the ambiguity that put
  // `half of undersized folio line` under a heading reading `not a line`.
  el.innerHTML = exempt.map((e, i) =>
    `<li><span class=y>y ${e.y0}–${e.y1}</span>`
    + `<button data-w="${i}" title="withdraw this ruling">×</button><br>`
    + (e.covered_by === undefined
        ? '<b>not type</b> — '
        : `<b>covered by line ${e.covered_by}</b> — `)
    + esc(e.note)
    // Said out loud, because the alternative is what already happened: a ruling
    // that settles nothing looked identical to one that does, and the page
    // reported the band as handled while every other view called it live.
    + (dead(e) ? '<br><span class=bad>settles no band on this page — nothing is '
                 + 'measured where it sits, so this record is inert.</span>' : '')
    + '</li>').join('');
  el.querySelectorAll('button[data-w]').forEach(b => {
    b.onclick = () => { exempt.splice(+b.dataset.w, 1); dirty = true; draw(); };
  });
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
  const pad = VIEW.ruling_pad_px;
  exempt.push({y0: b.vpos - pad, y1: b.vpos + b.height + pad,
               note: note.trim()});
  dirty = true; draw();
}

// **The other disposition: the ink is type, and it is already keyed.** A folio
// whose box strangled it leaves the rest of the number as a band, and ruling that
// "not a line" is true only by accident — it is not a *separate* line, which is a
// different claim, and the note people actually write ("half of undersized folio
// line") says the opposite of the disposition it was filed under. Naming the line
// that covers it records what was meant and makes the ruling checkable: `ocr gaps`
// reports a covered_by whose line is missing or empty as a fault.
//
// **The line is clicked, never typed.** This overlay draws no line numbers, so an
// index typed into a prompt is a number a human has no way to read off the page —
// they would be guessing, and a guessed index is precisely the silent wrong
// reference the field exists to make checkable. So `c` arms the pick, every store
// line lights up and carries its index and text on hover, and the click settles
// it.
function coverBand(v) {
  const b = S.bands.find(x => x.vpos === v);
  if (!b) return;
  if (!S.lines.length) {
    say('this page’s store has no lines to cover the band', 'bad');
    return;
  }
  covering = v;
  say('click the line that already keys this ink — hover shows what each holds. '
      + 'Escape to cancel.');
  draw();
}

// The second half of the pick: a store line was clicked while a band was armed.
function coverWith(idx) {
  const b = S.bands.find(x => x.vpos === covering);
  const line = S.lines.find(l => l.index === idx);
  if (!b || !line) { covering = null; draw(); return; }
  const note = prompt('Why is this ink part of the line reading “'
                      + (line.text || '(empty)') + '”? (a reason is required)');
  if (!note || !note.trim()) { covering = null; draw(); return; }
  const pad = VIEW.ruling_pad_px;
  exempt.push({y0: b.vpos - pad, y1: b.vpos + b.height + pad,
               note: note.trim(), covered_by: idx});
  covering = null; dirty = true;
  say('ruled covered by the line reading “' + (line.text || '(empty)') + '”');
  draw();
}

function say(m, cls) { const e = $('#msg'); e.textContent = m; e.className = cls || ''; }

ov.addEventListener('mousedown', e => {
  const t = e.target;
  // The armed pick takes the click before anything else, and swallows a click on
  // nothing rather than starting a drag: while a mode is on, the page is a
  // question waiting for one answer.
  if (covering !== null) {
    if (t.dataset.l !== undefined) coverWith(+t.dataset.l);
    else say('click a line, or Escape to cancel', 'bad');
    return;
  }
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
  if (d.x1 - d.x0 > VIEW.min_draw_w && d.y1 - d.y0 > VIEW.min_draw_h) {
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
    const r = await post(B + '/save', {ref: S.ref, lines: corr, ink_exempt: exempt});
    dirty = false;
    S.bands = r.live_bands;
    say(`saved · ${r.lines} correction(s) · ${r.live_bands.length} band(s) left`, 'ok');
    img.src = B + (blot ? '/blot/' : '/page/') + S.ref + '.png?t=' + Date.now();
    draw();
  } catch (err) { say(String(err.message || err), 'bad'); }
}

function go(ref) {
  if (dirty && !confirm('Unsaved corrections on this page. Leave anyway?')) return;
  location.href = B + '/?ref=' + ref;
}

// **Dispatched by action name, bound in the config.** The keys live in
// `data/lines_config.json` beside the colours, so rebinding one is an edit to a
// file rather than to a source string — and the loader refuses a config that
// binds a key twice, which would otherwise present as a broken shortcut.
// An action bound to null or "" is deliberately off the keyboard and reachable
// only by its row in the panel, so it must not land in this table under an empty
// key — every keystroke would match it.
const ACT = Object.fromEntries(
  Object.entries(CFG.actions).filter(([k, v]) => !k.startsWith('_') && v)
        .map(([name, key]) => [key, name]));

function first_undecided() {
  return S.bands.filter(x => !x.exempted && !ruled(x))[0];
}

const DO = {
  save: () => save(),
  blot: () => {
    blot = !blot;
    img.src = B + (blot ? '/blot/' : '/page/') + S.ref + '.png?t=' + Date.now();
    $('#bp').className = 'pill' + (blot ? ' on' : '');
  },
  delete: () => {
    if (sel !== null) { corr.splice(sel, 1); sel = null; dirty = true; draw(); }
  },
  rule_band: () => { const b = first_undecided(); if (b) ruleBand(b.vpos); },
  cover_band: () => { const b = first_undecided(); if (b) coverBand(b.vpos); },
  // The withdrawal is the second half of the ruling, exactly as in `zones edit`:
  // a call made once and uncorrectable is worse than no call, and a note nobody
  // can take back is a claim the page cannot argue with.
  withdraw_ruling: () => {
    const b = S.bands.filter(x => ruled(x))[0];
    // A dead ruling is still withdrawable, and by the same key — it is the one
    // most likely to want withdrawing. Reachable through the panel's × either
    // way; without this the keyboard would report "nothing to withdraw" beside a
    // list showing two, which is the shape of inconsistency this whole fix is
    // about.
    const e = (b && ruled(b)) || exempt.find(dead);
    if (!e) { say('no ruling of this layer to withdraw', 'bad'); return; }
    exempt.splice(exempt.indexOf(e), 1);
    dirty = true;
    say('ruling withdrawn (' + (e.covered_by === undefined
        ? 'not type' : 'covered by line ' + e.covered_by) + '): ' + e.note);
    draw();
  },
  list: () => {
    if (dirty && !confirm('Unsaved corrections. Leave anyway?')) return;
    location.href = B + '/list?ref=' + S.ref;
  },
  zoom_in: () => setZoom(zoom + 1),
  zoom_out: () => setZoom(zoom - 1),
  zoom_fit: () => setZoom(0),
  // Straight to the work: frame the first undecided band at a zoom where its
  // glyphs are legible, rather than making the human hunt for a 40-pixel mark
  // and then zoom in on it by hand.
  frame_band: () => {
    if (first_undecided()) { sel = null; setZoom(Math.max(zoom, VIEW.frame_zoom)); }
  },
  prev_page: () => { if (S.prev) go(S.prev); },
  next_page: () => { if (S.next) go(S.next); },
  // Cancel drops the pick before the selection: the mode is the more surprising
  // state to be left in, and Escape is what a human reaches for to get out of it.
  cancel: () => {
    if (covering !== null) { covering = null; say(''); draw(); return; }
    sel = null; draw();
  },
};

// **What each action needs before it can do anything.** Only the ones that act
// on a selection or a position have an entry; everything else is always live.
// This drives both the dimming and the click, so a row that looks inert is inert
// — a control that looks available and silently does nothing is worse than one
// that says it cannot.
const READY = {
  delete: () => sel !== null,
  cancel: () => sel !== null || covering !== null,
  rule_band: () => !!first_undecided(),
  cover_band: () => !!first_undecided() && S.lines.length > 0,
  frame_band: () => !!first_undecided(),
  withdraw_ruling: () => S.bands.some(b => ruled(b)) || exempt.some(dead),
  prev_page: () => !!S.prev,
  next_page: () => !!S.next,
  zoom_in: () => zoom < VIEW.zoom_max,
  zoom_out: () => zoom > VIEW.zoom_min,
  zoom_fit: () => zoom !== 0,
};
function ready(name) { return READY[name] ? READY[name]() : true; }

// On `window` so `draw` can reach it: `draw` is defined above this block and
// runs once before it, and a bare reference would throw on that first pass.
window.syncControls = function syncControls() {
  document.querySelectorAll('.key[data-act]').forEach(el => {
    el.classList.toggle('off', !ready(el.dataset.act));
  });
};

document.querySelectorAll('.key[data-act]').forEach(el => {
  el.onclick = () => {
    const name = el.dataset.act;
    if (!ready(name) || !DO[name]) return;
    DO[name]();
    syncControls();
  };
});

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  // `Delete`/`Backspace` are the platform's own, and stay bound alongside
  // whatever the config gives `delete`.
  let name = ACT[e.key];
  if (!name && (e.key === 'Delete' || e.key === 'Backspace')) name = 'delete';
  if (!name && (e.key === '=' || e.key === '_')) {
    name = e.key === '=' ? 'zoom_in' : 'zoom_out';   // unshifted +/- on most rows
  }
  if (!name || !DO[name]) return;
  e.preventDefault();
  if (!ready(name)) { syncControls(); return; }
  DO[name]();
  syncControls();
});

window.addEventListener('beforeunload', e => { if (dirty) e.preventDefault(); });
window.addEventListener('resize', () => { fit(); draw(); });
$('#save').onclick = save;
$('#done').onclick = async () => { await post(B + '/done', {}); say('server stopped'); };
fit(); draw(); syncControls();
