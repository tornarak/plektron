const B = STATE.base;
// The scrolling column, and the cards inside it. They were the same element
// until the map pane moved in above the stack: everything here indexes
// `STACK.childNodes` as cards, and a pane among them would be selected,
// surfaced, pinned and deleted like one.
const PANE = document.getElementById('secondary');
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

/* A card already open is raised rather than duplicated: the stack is a set in
   most-recent order, not a log. Raising stops below the pinned block, so a pin
   actually holds its place. */
function push(id, build) {
  let card = STACK.querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (!card) { card = build(); card.dataset.id = id; }
  const firstLoose = [...STACK.children].find(c => !c.classList.contains('pinned'));
  if (card.classList.contains('pinned')) STACK.prepend(card);
  else STACK.insertBefore(card, firstLoose === card ? card.nextSibling : firstLoose);
  card.scrollIntoView({block:'nearest'});
  return card;
}

/* The tools stay put and everything else lives in .body, so filling a card is
   one assignment. Replacing the <h4> alone used to leave the placeholder meta
   line behind it — a card that had finished loading still said "loading…". */
function card(id, title, meta, html, extra) {
  const el = document.createElement('div');
  el.className = 'card';
  el.dataset.id = id;
  el.innerHTML = `<div class="tools">
      <button data-act="pin" title="keep this above the rest">pin</button>
      <button data-act="close" title="remove">×</button></div>
    <div class="body"><h4>${title}</h4>${
      meta ? `<div class="meta">${meta}</div>` : ''}${html}</div>`;
  if (extra) extra(el);
  el.addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
      if (b.dataset.act === 'close') { el.remove(); savePins(); clampIdx(); }
    if (b.dataset.act === 'pin') {
      el.classList.toggle('pinned');
      b.textContent = el.classList.contains('pinned') ? 'unpin' : 'pin';
      if (el.classList.contains('pinned')) { STACK.prepend(el); clampIdx(); }
      savePins();
    }
  });
  return el;
}

/* Through `hover.js`'s memo when it is there, so a card rested on before it was
   clicked is already fetched and the `loading…` state never paints. The direct
   fetch is the fallback rather than the norm: it keeps this file working if that
   one did not load, which is cheaper than making the load order load-bearing. */
async function fill(id, url, title) {
  const c = push(id, () => card(id, title, 'loading…', ''));
  const html = window.CARDS ? await window.CARDS.get(url)
                            : await fetch(url).then(r => r.text());
  c.querySelector('.body').innerHTML = html;
  return c;
}

let selected_stack = false;
let selected_card_idx = -1;
let selected_card = null;

function togglePin(c) {
  let pinned = c.classList.toggle('pinned');
  c.querySelector('[data-act=pin]').textContent = pinned ? 'unpin' : 'pin';
  savePins();
  return pinned;
}

function toggleStack() {
    selected_stack = !selected_stack;
    PANE.classList.toggle('selected');

    if (selected_stack) {
        if (selected_card_idx == -1) selectIdx(0);
        else clampIdx();
    }
}

function clamp(v, min, max) {
    return Math.min(Math.max(min, v), max);
}

function clamped_idx(idx) {
    return clamp(idx, -1, STACK.childNodes.length - 1);
}

function clampIdx() {
    let clamped = clamped_idx(selected_card_idx);
    if (!selectIdx(clamped) && selected_stack) toggleStack();
}

function selectIdx(idx = null, rel = 0) {
    idx = (idx == null) ? selected_card_idx : idx;
    if (rel) idx += rel;
    if (idx == -2) idx = STACK.childNodes.length - 1;

    if (idx == -1 || idx == STACK.childNodes.length) {
        selected_card_idx = -1;
        if (selected_card) { selected_card.classList.remove("selected"); }
        selected_card = null;
        if (idx == -1) PANE.scroll(0, 0);
        else PANE.scroll(0, 100_000);
    } else {
        if (idx != selected_card_idx) {
            let clamped = clamped_idx(idx);

            if (clamped != idx) { return selectIdx(clamped); }
            else { selected_card_idx = idx; }
        }
        let next_sel = STACK.childNodes[selected_card_idx];
        if (selected_card && selected_card != next_sel) { selected_card.classList.remove("selected"); }
        selected_card = next_sel;
    }

    if (selected_card) { selected_card.classList.add("selected"); selected_card.scrollIntoView({block:'nearest'}); }
    return selected_card;
}

function countPins(lst = null) {
    let first_non_pin = Array.from(lst || STACK.childNodes).findIndex((p) => !p.classList.contains("pinned"));
    return (first_non_pin == -1) ? STACK.childNodes.length : first_non_pin;
}

function deleteSelection() {
    STACK.removeChild(selected_card);
    savePins();
    clampIdx();
}

function surfaceSelection() {
    let pin_count = countPins();
    if (selected_card_idx <= pin_count) {
        let pinned = togglePin(selected_card);
        if (!pinned) {
            let after = Array.from(STACK.childNodes).slice(selected_card_idx + 1);
            let offset = countPins(after);
            if (offset) STACK.insertBefore(selected_card, (offset < after.length) ? STACK.childNodes[selected_card_idx + offset + 1] : null);
            selectIdx(null, offset);
        }
    } else {
        STACK.insertBefore(selected_card, STACK.childNodes[pin_count]);
        selectIdx(pin_count);
    }
}

new MutationObserver((list, _) => {
    for (const m of list) if (m.type == "childList") clampIdx();
}).observe(STACK, { childList: true });

let article = document.querySelector("#primary");
let selected_tab_idx = -1;

const openEntity = ref =>
  fill('ent:' + ref, B + '/entity/' + encodeURIComponent(ref) + '?partial=1', ref);

/* The stack, for `map.js` to reach when a click turns out to want a card. That
   file owns the pane and this one owns the stack, and neither reaches into the
   other's DOM — the atlas loads `map.js` without this file at all, and falls
   back to navigating, which is why the hand-off is a named function and not an
   assumption that a stack exists. */
window.EDITION = {openEntity: ref => openEntity(ref)};

const openLexicon = key =>
  fill('lex:' + key, B + '/lexicon/' + encodeURIComponent(key) + '?partial=1', key);

/* `key` names an entry in STATE.crops, or is falsy for the whole page. It used
   to be the box itself, joined into the id — which meant the server had to know
   how this function spells an id in order to key a crop for it. */
function openScan(key, label) {
  const id = 'scan:' + (key || 'page');
  const c = key ? STATE.crops[key] : null;
  push(id, () => card(id, label || 'The page', STATE.ref,
    `<div class="crop" style="${c ? c.outer : 'aspect-ratio:'+STATE.size[0]+'/'+STATE.size[1]}">
        <a href="${B}/page/${STATE.ref}.png" target="_blank">
        <img src="${B}/page/${STATE.ref}.png" style="${c ? c.inner : 'width:100%;left:0;top:0'}">
        </a>
     </div>`));
}

let lightbox = null;
let lightbox_img = null;

function setLightbox(src) {
    if (!lightbox) {
        lightbox_img = document.createElement('img');
        let lightbox_container = document.createElement('div');
        lightbox_container.id = 'lightbox-image';
        lightbox = document.createElement('div');
        lightbox.id = 'lightbox';
        lightbox_container.append(lightbox_img);
        lightbox.append(lightbox_container);
        document.body.append(lightbox);
    } else {
        if (lightbox.style.visibility) {
            lightbox.style.removeProperty('visibility')
        } else {
            lightbox.style.visibility = 'hidden';
        }
    }

    lightbox_img.src = src;
}

document.addEventListener('click', ev => {
  /* An outbound link is a real navigation and keeps it — the stack is for what
     this edition holds, not for the open web. */
  if (ev.target.closest('a.out')) return;
  const a = ev.target.closest('a.ent');
  /* **The map first, and the card only when the map cannot take it.** A click
     used to do both, which meant every name in the text cost a card whether or
     not the reader wanted to read one — and with the map now accumulating, the
     second click on a place has an obvious other job. So `map.js` answers what
     the click meant: `'map'` when it put the place on the map, `'card'` when the
     map is already showing it (the reader has asked twice, and the entry is what
     is left to give) or when the atlas cannot draw it at all. Only that file can
     answer it, because only the store knows which entities have somewhere to go.

     No `await` in the handler: `preventDefault` has to run synchronously, and
     everything after it is the promise's. */
  if (a) {
    ev.preventDefault();
    const ref = a.dataset.ref;
    if (window.MAP) window.MAP.click(ref).then(w => { if (w == 'card') openEntity(ref); });
    else openEntity(ref);
    return;
  }
  const x = ev.target.closest('a.lex');
  if (x) { ev.preventDefault(); openLexicon(x.dataset.key); return; }
  /* `a.mapref` is `map.js`'s — it drives the pane on every page, not just this
     one, and intercepting it here would have been the same rule written twice. */
  /* A footnote marker is deliberately NOT intercepted: it keeps its href and
     jumps to the note at the foot of the page, where the note already is. A card
     in the stack was a third place to read one — beside the foot and the page
     itself — and the stack is for what a reader has to go and fetch: an entity,
     a lexicon form, a map, the raster. A note is already on the page. */
  /* A picture goes to the lightbox, and for the same reason a note does not go
     to the stack: the stack is for what a reader has to fetch and then read
     *beside* the text. A figure is already on the page, and the only thing
     wanted from it is to see it bigger — which is what the lightbox is for.

     Bound to the image and not to the <figure>, so a click on the caption
     selects its text the way a click on any other text does. Covers the inline
     figures, the plates on an exempt page, and the whole leaf on one with no
     figure boxes. */
  const pic = ev.target.closest('.figure img, .plates img, .whole-scan img');
  if (pic) { ev.preventDefault(); setLightbox(pic.src); return; }
  const l = ev.target.closest('.crop a, #lightbox-image');
  if (l) { ev.preventDefault(); let i = l.querySelector("img"); if (i && i.src) setLightbox(i.src); }
});

/* By class and not by id: the neighbour block is rendered at both ends of the
   page, so there are two of each. `querySelector` takes the first, and both
   carry the same href — which one it finds cannot matter. */
let prev = document.querySelector("a.page-prev");
let next = document.querySelector("a.page-next");

document.addEventListener('keydown', ev => {
    if (ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey) return false;
    if (ev.key == "Tab" && STACK.childNodes.length) { ev.preventDefault(); toggleStack(); }
    if (ev.key == "ArrowLeft" && !selected_stack && prev && prev.href) { ev.preventDefault(); window.location = prev.href; }
    if (ev.key == "ArrowRight" && !selected_stack && next && next.href) { ev.preventDefault(); window.location = next.href; }
    if (selected_stack) {
        if (ev.key == "ArrowUp") { ev.preventDefault(); selectIdx(null, -1); }
        if (ev.key == "ArrowDown") { ev.preventDefault(); selectIdx(null, 1); }
    }
    if (ev.key == "Enter" && selected_stack) { ev.preventDefault(); surfaceSelection(); }
    if (ev.key == "Backspace" && selected_stack) { ev.preventDefault(); deleteSelection(); }
})

document.getElementById('scan-btn').addEventListener('click', () => openScan());

// Reader view: applied to <html> so it can be set before first paint (see the
// inline script in the head) and never flashes the apparatus on load.
document.getElementById('reader-btn').addEventListener('click', () => {
  const on = document.documentElement.classList.toggle('reader');
  localStorage.setItem('edition-reader', on ? '1' : '');
});

function repin(c) {
  STACK.prepend(c);
  togglePin(c);
}
for (const id of pins) {
  if (id.startsWith('ent:')) openEntity(id.slice(4)).then(repin);
  else if (id.startsWith('lex:')) openLexicon(id.slice(4)).then(repin);
  /* No `note:` branch, and no `map:` branch any more — notes are read at the
     foot and a map is the pane's, neither of them a card. A pin saved before
     either changed names a card nothing opens now, and is ignored rather than
     special-cased: it costs an unrestored pin once. */
  else if (id == 'scan:page') openScan();
}

/* ---------------------------------------------------------------- figures

   The server sends `STATE.figs`, one entry per <figure> in document order,
   already matched to the store by printed number (or, for the ten figures whose
   caption prints none, by that order). The markup carries no geometry — see
   `stores.render`'s note — so the pictures are hung here.

   A figure can have several pictures: the store spells 1-276's fig. 140 in two
   boxes and the book letters them a and b inside its one caption, so they stack
   above the single <figcaption>.

   Progressive enhancement, and not only as a courtesy: with no script the
   caption still reads, which is the half that comes from an adjudicated store.
   The float is marked `data-float-basis="geometry"` because it reproduces where
   the box sat, which is evidence for how the print wrapped and not a record of
   it — zones are always the full measure, so nothing witnesses the wrap. */
for (const f of (STATE.figs || [])) {
  const el = document.querySelector(`.figure[data-i="${f.i}"]`);
  if (!el) continue;
  if (!f.crops.length) {
    /* Unresolved: say so, and never fall back to the next unused crop. A wrong
       picture under a right caption reads as correct and is the failure this
       edition is organised against. */
    const p = document.createElement('p');
    p.className = 'figure-missing';
    p.textContent = f.why || 'no picture for this figure';
    el.prepend(p);
    continue;
  }
  const holder = document.createElement('div');
  holder.className = 'figure-plates';
  for (const c of f.crops) {
    const img = document.createElement('img');
    img.src = c.url;
    img.alt = f.n ? 'Figure ' + f.n : 'Figure';
    img.loading = 'lazy';
    /* **Each picture at its own width, relative to the group's.** A lettered
       figure is several boxes under one caption and each is cut separately, so
       sizing them all by the group would stretch the narrow ones — 24 of 32
       parts in this store, worst x3.95. `f.width` is the block's share of the
       measure, so a part's share of the *block* is the ratio of the two. */
    if (f.width > 0 && c.width < f.width) {
      img.style.width = Math.round((c.width / f.width) * 100) + '%';
    }
    holder.append(img);
  }
  el.prepend(holder);
  if (f.side && f.side != 'full') {
    el.dataset.float = f.side;
    el.dataset.floatBasis = 'geometry';
    el.style.width = Math.round(f.width * 100) + '%';
  }
}
