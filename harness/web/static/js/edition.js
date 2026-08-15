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
  /* Middle-click closes it, anywhere on the card. A stack five deep is read by
     discarding, and reaching for a 12px × each time is the wrong gesture for
     the commonest act. `mousedown` is where the autoscroll cursor would
     otherwise appear, so it is refused there and acted on at `auxclick`. */
  el.addEventListener('mousedown', ev => { if (ev.button === 1) ev.preventDefault(); });
  el.addEventListener('auxclick', ev => {
    if (ev.button !== 1) return;
    ev.preventDefault();
    el.remove(); savePins(); clampIdx();
  });
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
  /* On a run the card holds every leaf of the span, in binding order. The page
     is one document and its scans are several, so "consult the scan" has to
     mean all of them — a card showing only the first would be answering about
     the head leaf a reader may not be anywhere near. A crop keeps the single
     path: `key` names one picture on one page. */
  const refs = (!key && STATE.leaves && STATE.leaves.length) ? STATE.leaves
                                                            : [STATE.ref];
  const body = refs.map(r =>
    `<div class="crop" style="${c ? c.outer : 'aspect-ratio:'+STATE.size[0]+'/'+STATE.size[1]}">
        <a href="${B}/page/${r}.png" target="_blank">
        <img src="${B}/page/${r}.png" style="${c ? c.inner : 'width:100%;left:0;top:0'}">
        </a>
     </div>`).join('');
  push(id, () => card(id, label || (refs.length > 1 ? 'The leaves' : 'The page'),
                      refs.join(' '), body));
}

/* A figure in the stack, which everywhere else in this edition is the wrong
   place for one.

   The rule below is that a picture goes to the lightbox because it is *already
   on the page* and the only thing wanted from it is to see it bigger. On the
   List of Illustrations that reason inverts: the picture is not on the page,
   the page is a catalogue naming it, and pulling one out to read beside the
   list is exactly what the stack is for. Same rule, opposite answer, because
   the premise is different.

   **The card is rebuildable from its own id** — `fig:1-112/001,1-113/003` — so
   a pinned figure survives a reload without the id having to carry a label. The
   label and caption are decoration when they are there and absent when they are
   not, which is what the restore path passes. */
function openFigure(pairs, label, caption) {
  pairs = pairs.filter(Boolean);
  if (!pairs.length) return;
  const id = 'fig:' + pairs.join(',');
  push(id, () => card(id, label || pairs.join(', '), caption || '',
    pairs.map(p => `<div class="crop-fig"><img src="${B}/fig/${p}.png"
      alt="${label || p}"></div>`).join('')));
}

/* The lightbox, which holds a *set* of pictures and not one.

   A figure card can carry several — `1-276`'s fig. 140 is two boxes, Plate I is
   three — and opening the third of them used to lose the other two. So the
   group travels with the picture: whatever images sit in the same card, plate
   block or figure, in the order they are on the page, and the arrows walk them.

   **It shadows the arrow keys whether or not there is anything to walk to**,
   and that is deliberate. The same keys turn the page underneath, and a reader
   pressing → at a single-picture lightbox means "next picture, if any" — never
   "leave this page". Silently navigating away because the group happened to
   have one member is the kind of surprise that teaches people not to use the
   keys at all. */
let lightbox = null;
let lightbox_img = null;
let lightbox_bar = null;
let lb_items = [];
let lb_i = 0;

function lightboxOpen() {
    return !!lightbox && !lightbox.style.visibility;
}

function setLightbox(src, group) {
    if (!lightbox) {
        lightbox_img = document.createElement('img');
        lightbox_bar = document.createElement('div');
        lightbox_bar.id = 'lightbox-bar';
        let lightbox_container = document.createElement('div');
        lightbox_container.id = 'lightbox-image';
        lightbox = document.createElement('div');
        lightbox.id = 'lightbox';
        lightbox_container.append(lightbox_img);
        lightbox.append(lightbox_container, lightbox_bar);
        document.body.append(lightbox);
    }
    lb_items = (group && group.length) ? group : [{src, caption: ''}];
    lb_i = Math.max(0, lb_items.findIndex(it => it.src == src));
    lightbox.style.removeProperty('visibility');
    paintLightbox();
}

function paintLightbox() {
    const it = lb_items[lb_i];
    lightbox_img.src = it.src;
    lightbox_img.alt = it.caption || '';
    /* **The caption is a link to the file**, which is the one thing a lightbox
       cannot do for you: see it at its own size, save it, put it in a tab. With
       no caption the bare file name stands in — `chukchi-1-049-002.png` names
       the leaf and the zone, so even the fallback tells a reader where they are.
       The arrows appear only when there is somewhere to go; a bar reading
       "1 / 1" with two dead buttons is furniture. */
    const many = lb_items.length > 1;
    lightbox_bar.innerHTML = `
      <a class="cap" href="${it.src}" target="_blank" rel="noopener"
         >${it.caption || it.src.split('/').pop()}</a>
      ${many ? `<div class="nav">
          <button data-lb="prev" title="previous (←)">‹</button>
          <span class="count">${lb_i + 1} / ${lb_items.length}</span>
          <button data-lb="next" title="next (→)">›</button>
        </div>` : ''}`;
}

function stepLightbox(d) {
    if (lb_items.length < 2) return;
    lb_i = (lb_i + d + lb_items.length) % lb_items.length;
    paintLightbox();
}

function closeLightbox() {
    if (lightbox) lightbox.style.visibility = 'hidden';
}

/* What a picture is called, from whichever of its neighbours says so.

   **The card is asked before the `alt`**, and that is the whole of the second
   fix: a figure card's images carry `alt="Fig. 5"`, which is the label and not
   the caption, so the lightbox announced a picture of a lasso as "Fig. 5". The
   card knows both — its heading is the label and its meta line the caption —
   and the two together are what the printed list says. */
function captionOf(img) {
    const cap = img.closest('figure')?.querySelector('figcaption');
    if (cap?.textContent.trim()) return cap.textContent.trim();
    const card = img.closest('.card');
    if (card) {
        const h = card.querySelector('.body h4')?.textContent.trim() || '';
        const m = card.querySelector('.body .meta')?.textContent.trim() || '';
        const both = [h, m].filter(Boolean).join(' — ');
        if (both) return both;
    }
    return img.alt?.trim() || '';
}

/* Every picture the one clicked belongs with, in page order.

   **A page of figures is one group, not one group per figure.** The container
   is what a reader would call "these pictures": a card is its own, a plate
   block is its own, and in running prose it is *the page* — six figures down a
   chapter opening are six pictures a reader walks, and stopping the arrows at
   the boundary of whichever `<figure>` happened to be clicked is an accident of
   markup rather than anything they would recognise. */
function lightboxGroup(img) {
    const box = img.closest('.card .body') || img.closest('.plates');
    if (box) return lbItems([...box.querySelectorAll('img')]);
    if (img.closest('.figure')) {
        const page = img.closest('#primary') || document;
        return lbItems([...page.querySelectorAll('.figure img')]);
    }
    return lbItems([img]);
}

function lbItems(imgs) {
    return imgs.map(i => ({src: i.src, caption: captionOf(i)}));
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
    /* **`toggle: false`, and that is the whole difference between the text and
       the tree.** Taking a place *off* the map is a thing you do to the map, in
       the tree, where you can see what is on it. In the running prose a second
       click on a name that is already up meant "and now take it away" — the
       reader is reading, not editing a selection, and what they want on the
       second ask is the entry. So the map keeps what it has and answers
       `'card'`. */
    if (window.MAP) window.MAP.click(ref, {toggle: false})
                              .then(w => { if (w == 'card') openEntity(ref); });
    else openEntity(ref);
    return;
  }
  const x = ev.target.closest('a.lex');
  if (x) { ev.preventDefault(); openLexicon(x.dataset.key); return; }
  /* The List of Illustrations' own links — see `openFigure` for why a picture
     goes to the stack there and to the lightbox everywhere else. The `href` is
     a real crop URL, so this works with no JS and a middle-click still opens
     the picture; the handler is the enhancement rather than the mechanism. */
  const g = ev.target.closest('a.fig');
  if (g) {
    ev.preventDefault();
    openFigure((g.dataset.fig || '').split(','), g.dataset.label,
               g.dataset.caption || '');
    return;
  }
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
     figures, the plates on an exempt page, the whole leaf on one with no figure
     boxes, and a figure already pulled into a card: the card got it out of a
     catalogue, and the only thing left to want from it is size. */
  /* The lightbox closes on a click anywhere in it, image included: it is one
     surface showing one thing. The bar at the foot is the exception, and has to
     be — its buttons and its link are the only things in there to aim at. */
  if (lightboxOpen() && ev.target.closest('#lightbox')) {
    const step = ev.target.closest('#lightbox-bar button[data-lb]');
    if (step) {
      ev.preventDefault();
      stepLightbox(step.dataset.lb == 'next' ? 1 : -1);
      return;
    }
    if (ev.target.closest('#lightbox-bar a')) return;   // to the file, in a tab
    ev.preventDefault(); closeLightbox(); return;
  }
  const pic = ev.target.closest(
    '.figure img, .plates img, .whole-scan img, .crop-fig img');
  if (pic) { ev.preventDefault(); setLightbox(pic.src, lightboxGroup(pic)); return; }
  const l = ev.target.closest('.crop a');
  if (l) {
    ev.preventDefault();
    const i = l.querySelector("img");
    if (i && i.src) setLightbox(i.src, lightboxGroup(i));
  }
});

/* By class and not by id: the neighbour block is rendered at both ends of the
   page, so there are two of each. `querySelector` takes the first, and both
   carry the same href — which one it finds cannot matter. */
let prev = document.querySelector("a.page-prev");
let next = document.querySelector("a.page-next");

document.addEventListener('keydown', ev => {
    if (ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey) return false;
    /* **The lightbox takes the arrows first and unconditionally** — see
       `setLightbox`. It is the frontmost thing on screen, so it owns the keys
       while it is up, and turning the page out from under it would be the
       surprise. Escape and the arrows are the whole of its keyboard. */
    if (lightboxOpen()) {
        if (ev.key == "Escape") { ev.preventDefault(); closeLightbox(); }
        if (ev.key == "ArrowLeft") { ev.preventDefault(); stepLightbox(-1); }
        if (ev.key == "ArrowRight") { ev.preventDefault(); stepLightbox(1); }
        return;
    }
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
  else if (id.startsWith('fig:')) openFigure(id.slice(4).split(','), '', '');
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

/* ------------------------------------------------- figure cross-references

   The prose points at pictures constantly — `(Plate XXVII, Fig. 3)`, `Fig. 87
   represents a knife` — and every one of those is a picture the figure store
   holds. `STATE.figrefs` is one entry per reference in document order, resolved
   server-side against `gt/fig/` and the List of Illustrations; the markup
   carries only the number the page prints, for the same reason `<figure>`
   carries no geometry.

   A resolved reference becomes `a.fig`, which is the List of Illustrations'
   own class, so the existing click handler opens it in the stack and nothing
   about the behaviour is written twice. **The stack and not the lightbox**, and
   for `openFigure`'s reason inverted: the picture is *not* on this page — the
   reader is being sent to it — so it wants a card that stays open beside the
   sentence that sent for it.

   An unresolved one is left as plain text with its reason on hover: a bare
   `Fig. 1` that no text page carries, a plate figure `gt/fig/` has not boxed,
   or another author's plate. Never a link to the nearest candidate — on a page
   of near-identical harnesses a wrong picture reads as a right one. */
for (const [i, r] of (STATE.figrefs || []).entries()) {
  const el = document.querySelector(`a.figref[data-fr="${i}"]`);
  if (!el) continue;
  if (!r.pairs || !r.pairs.length) {
    el.classList.add('unresolved');
    el.removeAttribute('tabindex');
    el.title = r.why || 'no picture for this reference';
    continue;
  }
  el.classList.add('fig');
  el.href = r.url;
  el.dataset.fig = r.pairs.join(',');
  el.dataset.label = r.label;
  el.title = r.label + (r.pairs.length > 1 ? ` — ${r.pairs.length} pictures` : '');
}
