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
from . import lines_config, webui
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
            # `text` travels for the covered-by pick: the overlay draws no line
            # numbers, so the line is chosen by clicking it and the only thing
            # that confirms the right one was clicked is what it keys.
            box = {"x0": round(r["hpos"] * sx), "y0": round(r["vpos"] * sy),
                   "x1": round((r["hpos"] + r["width"]) * sx),
                   "y1": round((r["vpos"] + r["height"]) * sy),
                   "index": r["index"], "zone": r["zone"],
                   "text": r.get("text") or ""}
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


def page_row(ref: str, root: Path = Path("."),
             alto_dir: str = DEFAULT_ALTO_DIR) -> dict:
    """One page's state for the list — the slow column measured, the rest read.

    `bands` is the raster read (~0.2 s) and everything else is a file test, which
    is why the list draws the cheap columns immediately and fetches this per row.
    """
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    bands = line_gaps(ref, alto_dir, root) if alto.exists() else []
    return {"ref": ref, "live": sum(1 for b in bands if not b["exempted"]),
            "ruled": sum(1 for b in bands if b["exempted"]),
            "corrections": len(corr.load_lines(ref, root))}


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
const S = STATE, VIEW = CFG.view;
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
    img.src = (blot ? '/blot/' : '/page/') + S.ref + '.png?t=' + Date.now();
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
    location.href = '/list?ref=' + S.ref;
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
$('#done').onclick = async () => { await post('/done', {}); say('server stopped'); };
fit(); draw(); syncControls();
"""

# Structure only. Every colour is `lines_config.layer_css`'s, generated from
# `data/lines_config.json`, because two places naming a colour is how one of them
# goes stale — and this editor's whole subject is a mark you have to be able to
# see.
EXTRA_CSS = """
#ov rect{vector-effect:non-scaling-stroke}
#ov .ly-band,#ov .ly-band_no_zone,#ov .ly-correction,
#ov .ly-correction_selected{cursor:pointer}
#tally{display:flex;gap:14px;color:var(--dim)}
#tally b{color:var(--fg)}
#dirty{color:var(--warn);font-weight:600}
#rulings{font-size:12px}
#rulings li{list-style:none;margin:0 0 5px;padding-left:10px;
            border-left:2px solid var(--warn)}
#rulings .y{color:var(--dim);font-variant-numeric:tabular-nums}
#rulings button{padding:0 6px;font-size:11px;margin-left:4px}
#rulings .none{color:var(--dim);font-style:italic}
/* The key rows are controls: clicking one does the thing, so an action is
   reachable without knowing (or having kept) its shortcut. */
.key[data-act]{cursor:pointer;border-radius:4px;padding:1px 4px;margin:0 -4px}
.key[data-act]:hover{background:var(--line)}
.key.off{opacity:.38;cursor:default}
.key.off:hover{background:none}
kbd.none{opacity:.45}
"""


# What each bound action is called on the page. Held beside the dispatch rather
# than in the config: the config says which key, this says what to call it, and a
# human rebinding a key should not have to restate its name in English.
ACTION_NAMES = {
    "rule_band": "rule a band not type",
    "withdraw_ruling": "withdraw a ruling",
    "delete": "delete selected",
    "zoom_in": "zoom in",
    "zoom_out": "zoom out",
    "zoom_fit": "fit the page",
    "frame_band": "frame the next band",
    "blot": "blotted view",
    "save": "save",
    "list": "the walk, measured",
    "prev_page": "previous page",
    "next_page": "next page",
    "cancel": "deselect",
}


def _keys_html(cfg: dict) -> str:
    """The panel: every action, clickable, with its key if it has one.

    Generated from the bindings, because written out by hand it was a second
    place the keys lived, free to disagree with what the editor actually binds —
    a help panel that lies about the tool is worse than none.

    **Every row is a control, not a legend.** An action reachable only by a
    keystroke is unreachable to anyone who has rebound it away or has not learnt
    it yet, and this is a tool a human meets a few dozen times a book. So the row
    does the thing, and the key is a shortcut for the row rather than the only way
    in. Actions with nothing to act on — delete with no selection, withdraw with
    no ruling — draw dimmed rather than disappearing, since a control that comes
    and goes is harder to learn than one that is visibly not applicable.
    """
    rows = ['<div class=key><span>adopt a band</span><kbd>click</kbd></div>',
            '<div class=key><span>draw a box</span><kbd>drag</kbd></div>']
    keys = {k: v for k, v in cfg["actions"].items() if not k.startswith("_")}
    for name, label in ACTION_NAMES.items():
        shown = {"ArrowLeft": "←", "ArrowRight": "→"}.get(
            keys.get(name), keys.get(name, ""))
        rows.append(
            f'<div class=key data-act="{name}" title="{label}">'
            f'<span>{label}</span>'
            + (f"<kbd>{shown}</kbd>" if shown else "<kbd class=none>—</kbd>")
            + "</div>")
    return "\n  ".join(rows)


def render_html(ref: str, root: Path = Path("."),
                alto_dir: str = DEFAULT_ALTO_DIR,
                itinerary: list[str] | None = None,
                itinerary_name: str = "") -> str:
    cfg = lines_config.load_config(root)
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
<style>{webui.CHROME_CSS}{EXTRA_CSS}{lines_config.layer_css(cfg)}</style>
<div id=bar>
  <b>lines</b><span id=cur>{st['ref']}</span>
  <span class=pill id=bp>b · blot</span>
  <span class=pill id=zl>1.00×</span>
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
  {_keys_html(cfg)}
  <h4>ruled not a line</h4>
  <ul id=rulings></ul>
  <h4>this editor draws</h4>
  <div id=flags>It never keys. The text of a recovered line is adjudicated in
  <code>ocr review</code> and written by <code>restore</code>, like any other
  line's.</div>
  <h4>the walk</h4>
  <div id=flags>{itinerary_name or '—'}
  {f'· {i + 1} of {len(it)}' if i >= 0 else ''}<br>
  <a href="/list?ref={st['ref']}">list, with live counts</a></div>
</div>
<div id=issues>{warn}</div>
<script>const STATE = {json.dumps(st, ensure_ascii=False)};
const CFG = {json.dumps({k: v for k, v in cfg.items() if not k.startswith('_')},
                        ensure_ascii=False)};</script>
<script>{JS}</script>
"""


def render_list_html(walk: list[str], label: str, root: Path,
                     cur: str = "") -> str:
    """The walk as a table, with the live counts fetched per row.

    **A view over what is being walked, not a saved work-list.** The obvious
    itinerary for this editor is "the pages that still carry a band", and writing
    that to a file would freeze it: every page worked makes the file wrong, and
    nothing would ever check it. So the list measures when asked and says so —
    `?` until a row has been fetched, never blank, because blank is
    indistinguishable from none.
    """
    rows = "".join(
        f'<tr{" class=here" if r == cur else ""} data-ref="{r}" data-state="todo">'
        f'<td class=ref><span class="dot s-todo"></span>'
        f'<a href="/?ref={r}">{r}</a></td>'
        f'<td class=num data-live>?</td>'
        f'<td class="num dim" data-ruled>?</td>'
        f'<td class=num data-corr>?</td></tr>' for r in walk)
    back = cur or (walk[0] if walk else "")
    return f"""<!doctype html><meta charset=utf-8><title>lines · {label or 'walk'}</title>
<style>{webui.CHROME_CSS}{webui.LIST_CSS}{EXTRA_CSS}</style>
<div id=head>
  <h1>{label or 'the walk'} — {len(walk)} pages
    <a class=chip href="/?ref={back}">back to the page</a></h1>
  <p><span id=shownum>unmeasured</span> — a live count is a raster read a page,
  so it is a button rather than something this page spends a minute on before
  showing you anything. <kbd>Esc</kbd> or a ref goes back.<span id=shown></span></p>
  <div id=filters>
    <span class=chip id=go>measure every row</span>
    <span class=chip data-filter=live><i class=s-warn></i> still live</span>
    <span class=chip data-filter=done><i class=s-ok></i> settled</span>
  </div>
</div>
<div id=wrapl>
<table><tr><th>page</th><th class=num>live</th><th class=num>ruled</th>
<th class=num>corrections</th></tr>
{rows}</table></div>
<script>
// One row at a time, and only when asked: each is a raster read. The button says
// so rather than the page quietly spending a minute before showing anything.
const note = document.querySelector('#shownum');
document.querySelector('#go').onclick = async () => {{
  const rows = [...document.querySelectorAll('tr[data-ref]')];
  let live = 0;
  for (let i = 0; i < rows.length; i++) {{
    const tr = rows[i];
    note.textContent = `measuring ${{i + 1}} / ${{rows.length}}`;
    try {{
      const r = await (await fetch('/row?ref=' + tr.dataset.ref)).json();
      tr.querySelector('[data-live]').textContent = r.live;
      tr.querySelector('[data-ruled]').textContent = r.ruled;
      tr.querySelector('[data-corr]').textContent = r.corrections;
      // The dot carries the state, as it does in the zone editor's list, so a
      // colour means one thing across the pass rather than one thing per tool.
      tr.dataset.state = r.live ? 'live' : 'done';
      tr.querySelector('.dot').className =
        'dot ' + (r.live ? 's-warn' : 's-ok');
      live += r.live ? 1 : 0;
    }} catch (e) {{ note.textContent = String(e); return; }}
  }}
  note.textContent = `${{live}} of ${{rows.length}} still carrying a band`;
}};

// Filters hide rows, they never re-order them: the walk's order is the order the
// editor steps through, and a list that disagreed with the arrow keys would be
// worse than no list.
let filter = '';
document.querySelectorAll('.chip[data-filter]').forEach(c => {{
  c.onclick = () => {{
    filter = (filter === c.dataset.filter) ? '' : c.dataset.filter;
    document.querySelectorAll('.chip[data-filter]').forEach(
      o => o.classList.toggle('on', o.dataset.filter === filter));
    let n = 0;
    document.querySelectorAll('tr[data-ref]').forEach(tr => {{
      const show = !filter || tr.dataset.state === filter;
      tr.style.display = show ? '' : 'none';
      n += show ? 1 : 0;
    }});
    document.querySelector('#shown').textContent =
      filter ? ` · showing ${{n}}` : '';
  }};
}});

document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') location.href = '/?ref={back}';
}});
</script>
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
        fetched = ("/row",)   # the list drives this from JS and parses JSON

        def get(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                r = (parse_qs(u.query).get("ref") or [start])[0]
                self.send_html(render_html(r, root, alto_dir, itinerary,
                                           itinerary_name))
                return
            if u.path == "/list":
                cur = (parse_qs(u.query).get("ref") or [""])[0]
                self.send_html(render_list_html(itinerary or [start],
                                                itinerary_name, root, cur))
                return
            if u.path == "/row":
                try:
                    r = norm_ref((parse_qs(u.query).get("ref") or [""])[0])
                except ValueError:
                    self.send_error(404)
                    return
                self.send_json(page_row(r, root, alto_dir))
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
