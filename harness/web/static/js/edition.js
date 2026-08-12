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

/* **Indexed by position in the list, not by the value of `tabindex`.** The two
   agree only when every index from 1 to the count is actually on the page, and
   they did not: the neighbour block held 1 and 2, and a page with only one
   neighbour — the first and the last of any listing — left a gap. `count` then
   fell one short of the highest live index and the last link in the text could
   not be reached at all, while one keystroke early in the walk focused nothing.
   `tei_html` still numbers the anchors, and that numbering is what puts them in
   reading order here; nothing on this side needs to know what the numbers are,
   which is also what let the neighbours stop claiming two of them. */
function selectTabIdx(idx = null, inc = 0) {
    let links = [...article.querySelectorAll("a[tabindex]")];
    if (!links.length) return;
    idx = (idx == null) ? selected_tab_idx : idx;
    if (inc) idx += inc;
    if (idx < 0) idx = links.length - 1;
    else if (idx >= links.length) idx = 0;
    selected_tab_idx = idx;
    links[idx].focus();
}

const openEntity = ref =>
  fill('ent:' + ref, B + '/entity/' + encodeURIComponent(ref) + '?partial=1', ref);

const openLexicon = key =>
  fill('lex:' + key, B + '/lexicon/' + encodeURIComponent(key) + '?partial=1', key);

function openScan(box, label) {
  const id = 'scan:' + (box ? box.join(',') : 'page');
  push(id, () => card(id, label || 'The page', STATE.ref,
    `<div class="crop" style="${STATE.crops[id] ? STATE.crops[id].outer : 'aspect-ratio:'+STATE.size[0]+'/'+STATE.size[1]}">
        <a href="${B}/page/${STATE.ref}.png" target="_blank">
        <img src="${B}/page/${STATE.ref}.png" style="${STATE.crops[id] ? STATE.crops[id].inner : 'width:100%;left:0;top:0'}">
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
  /* Both, and in that order: the card says what it is, the pane says where. A
     click on something with nothing to draw leaves the pane on whatever it was
     showing — `map.js` decides that, because only the fetched fragment knows. */
  if (a) {
    ev.preventDefault();
    openEntity(a.dataset.ref);
    if (window.MAP) window.MAP.show(a.dataset.ref);
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
  const f = ev.target.closest('.figure-anchor');
  if (f) { openScan(null, 'Figure ' + f.dataset.figure); return; }
  const l = ev.target.closest('.crop a, #lightbox-image');
  if (l) { ev.preventDefault(); let i = l.querySelector("img"); if (i && i.src) setLightbox(i.src); }
});

/* By class and not by id: the neighbour block is rendered at both ends of the
   page, so there are two of each. `querySelector` takes the first, and both
   carry the same href — which one it finds cannot matter. */
let prev = document.querySelector("a.page-prev");
let next = document.querySelector("a.page-next");

document.addEventListener('keydown', ev => {
    if (ev.key == "Tab" && STACK.childNodes.length) { ev.preventDefault(); toggleStack(); }
    if (ev.key == "ArrowLeft" && !selected_stack && prev && prev.href) { ev.preventDefault(); window.location = prev.href; }
    if (ev.key == "ArrowRight" && !selected_stack && next && next.href) { ev.preventDefault(); window.location = next.href; }
    if (selected_stack) {
        if (ev.key == "ArrowUp") { ev.preventDefault(); selectIdx(null, -1); }
        if (ev.key == "ArrowDown") { ev.preventDefault(); selectIdx(null, 1); }
    } else {
        if (ev.key == "ArrowUp") { ev.preventDefault(); selectTabIdx(null, -1); }
        if (ev.key == "ArrowDown") { ev.preventDefault(); selectTabIdx(null, 1); }
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
