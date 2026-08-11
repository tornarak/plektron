const B = STATE.base;
const PANE = document.getElementById('secondary');
const STACK = document.getElementById('secondary');
const KEY = 'edition-pins-' + STATE.ref;

const TABINDEX_OFFSET = 2;

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

async function fill(id, url, title) {
  const c = push(id, () => card(id, title, 'loading…', ''));
  const r = await fetch(url);
  c.querySelector('.body').innerHTML = await r.text();
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
let selected_tab_idx = TABINDEX_OFFSET;

function selectTabIdx(idx = null, inc = 0) {
    idx = (idx == null) ? selected_tab_idx : idx;
    if (inc) idx += inc;
    let count = article.querySelectorAll("a[tabindex]").length;
    if (idx == -1) idx = count;
    else if (idx > count) idx = 1;

    selected_tab_idx = clamp(idx, 1, count);
    let sel = article.querySelector(`a[tabindex="${selected_tab_idx}"]`);
    if (sel) sel.focus();
}

const openEntity = ref =>
  fill('ent:' + ref, B + '/entity/' + encodeURIComponent(ref) + '?partial=1', ref);

const openLexicon = key =>
  fill('lex:' + key, B + '/lexicon/' + encodeURIComponent(key) + '?partial=1', key);

const openMap = ref =>
  fill('map:' + ref, B + '/map/' + encodeURIComponent(ref) + '?partial=1', ref);

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
  if (a) { ev.preventDefault(); openEntity(a.dataset.ref); return; }
  const x = ev.target.closest('a.lex');
  if (x) { ev.preventDefault(); openLexicon(x.dataset.key); return; }
  const m = ev.target.closest('a.mapref');
  if (m) { ev.preventDefault(); openMap(m.dataset.ref); return; }
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

let prev = document.getElementById("prev-page");
let next = document.getElementById("next-page");

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
  else if (id.startsWith('map:')) openMap(id.slice(4)).then(repin);
  /* No `note:` branch — notes are read at the foot, not in the stack. A pin
     saved before that changed names a card nothing opens now, and is ignored
     rather than special-cased: it costs an unrestored pin once. */
  else if (id == 'scan:page') openScan();
}
