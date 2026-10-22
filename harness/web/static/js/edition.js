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
        /* The column's scrolling part, which is not the column: the TOC
           switch is fixed beneath it. `PANE` where a view has no such part. */
        const scroller = document.getElementById('side-body') || PANE;
        if (idx == -1) scroller.scroll(0, 0);
        else scroller.scroll(0, 100_000);
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
  fill('ent:' + ref, B + '/partial/entity/' + encodeURIComponent(ref), ref);

/* The stack, for `map.js` to reach when a click turns out to want a card. That
   file owns the pane and this one owns the stack, and neither reaches into the
   other's DOM — the atlas loads `map.js` without this file at all, and falls
   back to navigating, which is why the hand-off is a named function and not an
   assumption that a stack exists. */
window.EDITION = {openEntity: ref => openEntity(ref)};

/* A recording, played where it is cited. **The one outbound address the stack
   holds in place**: a supplement whose subject *is* the recording should not
   send a reader out of the edition to hear it, and a card is already how this
   view keeps what you consulted.

   Built here rather than fetched: the embed is a fixed address made from an id
   the server already validated against a YouTube URL, so there is nothing for a
   round trip to add. `youtube-nocookie.com` for the same reason `a.out` carries
   `noreferrer` — the edition does not hand a reader's visit to a third party
   for free.

   Titled with the link's own text, so the card says what the reader clicked and
   not what the video calls itself. */
const openYouTube = (embed, title) =>
  push('yt:' + embed, () => card(
    'yt:' + embed, title || 'Recording', '',
    `<div class="embed"><iframe src="https://www.youtube-nocookie.com/embed/${embed}"
       title="${title || 'Recording'}" loading="lazy" allowfullscreen
       referrerpolicy="strict-origin-when-cross-origin"
       allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"
       frameborder="0"></iframe></div>`));

const openLexicon = key =>
  fill('lex:' + key, B + '/partial/lexicon/' + encodeURIComponent(key), key);

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
        <a class="pic" href="${B}/page/${r}.png" target="_blank" rel="noopener">
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
    pairs.map(p => `<div class="crop-fig"><a class="pic" href="${B}/fig/${p}.png"
      target="_blank" rel="noopener"><img src="${B}/fig/${p}.png"
      alt="${label || p}"></a></div>`).join('')));
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
let lightbox_under = null;
let lightbox_stack = null;
let lightbox_bar = null;
let lb_items = [];
let lb_i = 0;

/* Zoom, on the pictures rather than on the page.

   A plate is scanned at 300 dpi and shown at whatever the viewport allows, so
   "fit" is the only view the lightbox used to offer and the detail a reader
   opened it *for* was the part it threw away. `1-361`'s map is the extreme case
   — its village names are 6 pt on a foldout — but a lasso diagram at fit is no
   better.

   Scale 1 means fit, which is what `object-fit:contain` already does, so the
   transform is identity until somebody asks for more and nothing changes for a
   reader who never touches it. Panning is in transformed space and clamped
   nowhere: a picture zoomed past the viewport should be draggable off-centre,
   because the interesting corner of a map usually is. */
let z_scale = 1, z_x = 0, z_y = 0, z_drag = null, z_panned = false, z_rot = 0;
const Z_MAX = 12;

function zoomReset() {
    z_rot = 0;
    zoomResetView();
}

/* Scale and pan, without the rotation.

   **A turn survives a step through the group**, because it is a fact about how
   the pictures were bound and not about how this one is being looked at: the
   three leaves of a foldout plate are all on their sides, and a reader who
   turned the first upright meant the plate, not the leaf. Zoom and pan do not
   survive, because they name a place *inside* one picture that the next one has
   no counterpart for. Opening the lightbox afresh starts square — `setLightbox`
   zeroes the angle, so a rotation never outlives the set it was made in. */
function zoomResetView() {
    z_scale = 1; z_x = 0; z_y = 0;
    zoomPaint();
}

/* Rotating a fitted picture a quarter turn swaps the footprint it needs, so a
   landscape plate turned upright is suddenly taller than the window. The
   scroller is `overflow:hidden` — the transform is what moves the picture now —
   so an unfitted rotation would simply hide the ends of it. This is the factor
   that makes the turned picture fit again, and it is 1 at 0 and 180 where
   nothing changed. */
function rotFit() {
    if (z_rot % 180 === 0 || !lightbox_img) return 1;
    const w = lightbox_img.clientWidth, h = lightbox_img.clientHeight;
    const box = lightbox_stack?.parentElement;
    if (!w || !h || !box) return 1;
    const cs = getComputedStyle(box);
    const cw = box.clientWidth - parseFloat(cs.paddingLeft)
        - parseFloat(cs.paddingRight);
    const ch = box.clientHeight - parseFloat(cs.paddingTop)
        - parseFloat(cs.paddingBottom);
    return Math.min(cw / h, ch / w, 1);
}

function zoomPaint() {
    if (!lightbox_stack) return;
    /* Read right to left: the picture turns, then scales, then moves. Rotating
       last would spin the pan offset with it and send a dragged detail off in an
       arc, which is not what a reader means by "turn it". */
    lightbox_stack.style.transform =
        `translate(${z_x}px, ${z_y}px) scale(${z_scale * rotFit()}) `
        + `rotate(${z_rot}deg)`;
    lightbox_stack.classList.toggle('zoomed', z_scale > 1);
    const pct = lightbox_bar?.querySelector('.zoomlevel');
    if (pct) pct.textContent = Math.round(z_scale * 100) + '%';
}

/* Quarter turns only. A free angle is a photo-editor control, and nothing in a
   printed book is set at 37 degrees — every rotated thing here is a caption or a
   plate the binder turned, all of them square to the page. */
function rotate(d) {
    z_rot = (z_rot + d * 90 + 360) % 360;
    z_x = 0; z_y = 0;
    zoomPaint();
}

/* Zoom about the cursor, so the thing under the pointer stays under it. */
function zoomAt(factor, cx, cy) {
    const box = lightbox_stack.getBoundingClientRect();
    const ns = Math.min(Z_MAX, Math.max(1, z_scale * factor));
    if (ns === z_scale) return;
    const ox = cx - (box.left + box.width / 2);
    const oy = cy - (box.top + box.height / 2);
    z_x -= ox * (ns / z_scale - 1);
    z_y -= oy * (ns / z_scale - 1);
    z_scale = ns;
    if (z_scale === 1) { z_x = 0; z_y = 0; }
    zoomPaint();
}

function lightboxOpen() {
    return !!lightbox && !lightbox.style.visibility;
}

function setLightbox(src, group) {
    if (!lightbox) {
        lightbox_img = document.createElement('img');
        lightbox_img.className = 'top';
        lightbox_img.draggable = false;
        /* `rotFit` measures the *rendered* picture, and a swapped `src` keeps
           the outgoing one's dimensions until the new file decodes. With the
           angle now carried across a step, the first paint of the next picture
           would scale a landscape leaf by the portrait one's factor and hang it
           off the edge; this repaints once it is real. */
        lightbox_img.addEventListener('load', zoomPaint);
        lightbox_under = document.createElement('img');
        lightbox_under.className = 'under';
        lightbox_under.alt = '';
        lightbox_under.draggable = false;
        lightbox_under.hidden = true;
        /* The two layers go in a wrapper and the *wrapper* is what transforms,
           so one scale moves both and they cannot drift apart at any zoom. */
        lightbox_stack = document.createElement('div');
        lightbox_stack.id = 'lightbox-stack';
        lightbox_stack.append(lightbox_under, lightbox_img);
        lightbox_bar = document.createElement('div');
        lightbox_bar.id = 'lightbox-bar';
        let lightbox_container = document.createElement('div');
        lightbox_container.id = 'lightbox-image';
        lightbox = document.createElement('div');
        lightbox.id = 'lightbox';
        lightbox_container.append(lightbox_stack);
        lightbox.append(lightbox_container, lightbox_bar);
        document.body.append(lightbox);
        bindZoom(lightbox_container);
    }
    lb_items = (group && group.length) ? group : [{src, caption: ''}];
    lb_i = Math.max(0, lb_items.findIndex(it => it.src == src));
    z_rot = 0;
    lightbox.style.removeProperty('visibility');
    paintLightbox();
}

function paintLightbox() {
    const it = lb_items[lb_i];
    lightbox_img.referrerPolicy = it.referrer || '';
    lightbox_img.src = it.src;
    lightbox_img.alt = it.caption || '';
    /* A leaf delivered as a Mixed Raster pair is *one* picture in two files, so
       the lightbox stacks it exactly as the page does rather than showing one
       layer. Without this the map opens as either a colour smear with no names
       or an outline with no ethnic areas — both of which render happily and look
       like the map, which is the whole reason `edition_ui.leaf_layers` refuses a
       half pair on the server side too. */
    lightbox_under.hidden = !it.under;
    if (it.under) lightbox_under.src = it.under;
    zoomResetView();
    /* **The caption is a link to the file**, which is the one thing a lightbox
       cannot do for you: see it at its own size, save it, put it in a tab. With
       no caption the bare file name stands in — `chukchi-1-049-002.png` names
       the leaf and the zone, so even the fallback tells a reader where they are.
       The arrows appear only when there is somewhere to go; a bar reading
       "1 / 1" with two dead buttons is furniture. */
    const many = lb_items.length > 1;
    lightbox_bar.innerHTML = `
      <a class="cap" href="${it.full || it.src}" target="_blank" rel="noopener"
         >${it.caption || (it.full || it.src).split('/').pop()}</a>
      <div class="nav">
        <button data-lb="rotl" title="rotate left (shift R)">↺</button>
        <button data-lb="rotr" title="rotate right (R)">↻</button>
        <button data-lb="zout" title="zoom out (−)">−</button>
        <span class="count zoomlevel">100%</span>
        <button data-lb="zin" title="zoom in (+)">+</button>
        ${many ? `<button data-lb="prev" title="previous (←)">‹</button>
          <span class="count">${lb_i + 1} / ${lb_items.length}</span>
          <button data-lb="next" title="next (→)">›</button>` : ''}
      </div>`;
    zoomPaint();
}

/* Wheel to zoom, drag to pan, double-click to toggle. The wheel is captured
   only inside the lightbox and only with `preventDefault`, so the page beneath
   never scrolls out from under an open picture. */
function bindZoom(container) {
    container.addEventListener('wheel', e => {
        e.preventDefault();
        zoomAt(Math.exp(-e.deltaY * 0.0016), e.clientX, e.clientY);
    }, {passive: false});

    container.addEventListener('dblclick', e => {
        e.preventDefault();
        /* The view only: double-click toggles the zoom, and dropping the
           reader's rotation on the way back out is not what the gesture says.
           `0` is the control that undoes everything, and stays that. */
        if (z_scale > 1) zoomResetView();
        else zoomAt(3, e.clientX, e.clientY);
    });

    container.addEventListener('pointerdown', e => {
        /* A click on the backdrop still closes; only a drag *on the picture*
           pans, and only when there is somewhere to pan to. */
        if (z_scale <= 1 || !e.target.closest('#lightbox-stack')) return;
        z_drag = {x: e.clientX, y: e.clientY};
        container.setPointerCapture(e.pointerId);
        container.classList.add('panning');
    });
    container.addEventListener('pointermove', e => {
        if (!z_drag) return;
        const dx = e.clientX - z_drag.x, dy = e.clientY - z_drag.y;
        if (dx || dy) z_panned = true;
        z_x += dx; z_y += dy;
        z_drag = {x: e.clientX, y: e.clientY};
        zoomPaint();
    });
    const drop = e => {
        if (!z_drag) return;
        z_drag = null;
        container.classList.remove('panning');
        try { container.releasePointerCapture(e.pointerId); } catch {}
    };
    container.addEventListener('pointerup', drop);
    container.addEventListener('pointercancel', drop);
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
    /* A Mixed Raster leaf is one picture whose two files both sit in the same
       block, so the generic "every img in the container" rule would make it a
       two-member group a reader could arrow between — half a map each. It is
       one item carrying both. */
    const mrc = img.closest('.leaf-mrc');
    if (mrc) return lbItems([mrc.querySelector('img:last-child')]);
    /* **A member is an `a.pic`, never a bare `img`.** A card's body holds the
       Wikipedia and Wikidata marks beside its picture, and "every img in the
       box" walked the reader through the logos. The anchor is what makes an
       image a picture here, so it is what the group counts. */
    const box = img.closest('.card .body') || img.closest('.plates');
    if (box) return lbItems(pics(box));
    if (img.closest('.figure')) {
        const page = img.closest('#primary') || document;
        return lbItems(pics(page, '.figure '));
    }
    return lbItems([img]);
}

function pics(root, within = '') {
    return [...root.querySelectorAll(within + 'a.pic')]
        .map(a => a.querySelector('img:last-child')).filter(Boolean);
}

function lbItems(imgs) {
    return imgs.map(i => {
        const mrc = i.closest('.leaf-mrc');
        const under = mrc?.querySelector('img:first-child');
        return {
            /* An entity's picture is a Commons thumbnail on the card and a
               larger rendition here; `data-full` is that one's address. */
            src: i.dataset.full || i.src,
            under: under && under !== i ? under.src : null,
            /* Where "open the file" should go: the picture's own anchor, so the
               lightbox's link and the page's cannot disagree. That is the master
               for a layered leaf, not the half on top, and a Commons picture's
               file page, where the licence the caption names is stated. */
            full: i.closest('a.pic')?.href || null,
            caption: captionOf(i),
            /* The card hotlinks without a referrer, and so does this. */
            referrer: i.referrerPolicy || '',
        };
    });
}

document.addEventListener('click', ev => {
  /* An outbound link is a real navigation and keeps it — the stack is for what
     this edition holds, not for the open web. */
  if (ev.target.closest('a.out')) return;
  /* Whatever it opens lands in the entities panel, so that is the panel to show:
     the contents laid over it would hide what the click produced. Not on a
     ctrl/meta click, which is the browser's new tab and puts nothing here. */
  if (ev.target.closest('a.ent, a.lex, a.yt, a.fig') && !ev.ctrlKey && !ev.metaKey
      && window.SIDEBAR) window.SIDEBAR.show('entities');
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
  /* Before the `a.out` guard would matter: a `yt` link is outbound by `href`
     and inbound by intent. `preventDefault` keeps the navigation from happening
     while leaving the href real for middle-click and no-JS. */
  const y = ev.target.closest('a.yt');
  if (y) {
    ev.preventDefault();
    openYouTube(y.dataset.embed, y.textContent.trim());
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

     Bound to the picture's `a.pic` and not to the <figure>, so a click on the
     caption selects its text the way a click on any other text does. Every
     picture has one — inline figures, plates, a whole leaf, a card's crop or
     scan, an entity's photograph — and its href is the original, so a
     modified click is left to the browser and opens that in a tab. */
  /* The lightbox closes on a click anywhere in it, image included: it is one
     surface showing one thing. The bar at the foot is the exception, and has to
     be — its buttons and its link are the only things in there to aim at. */
  if (lightboxOpen() && ev.target.closest('#lightbox')) {
    const step = ev.target.closest('#lightbox-bar button[data-lb]');
    if (step) {
      ev.preventDefault();
      const what = step.dataset.lb;
      if (what == 'zin' || what == 'zout') {
        const r = lightbox_stack.getBoundingClientRect();
        zoomAt(what == 'zin' ? 1.6 : 1 / 1.6,
               r.left + r.width / 2, r.top + r.height / 2);
      } else if (what == 'rotl' || what == 'rotr') {
        rotate(what == 'rotr' ? 1 : -1);
      } else stepLightbox(what == 'next' ? 1 : -1);
      return;
    }
    if (ev.target.closest('#lightbox-bar a')) return;   // to the file, in a tab
    /* A pan ends in a click, and closing on it would make a zoomed picture
       impossible to drag. The drag swallows exactly one click and no more, so
       a plain click on the backdrop still closes as it always did. */
    if (z_panned) { z_panned = false; ev.preventDefault(); return; }
    /* Zoomed in, a click on the picture is aiming at the picture. The backdrop
       around it still closes, which is the gesture a reader already knows. */
    if (z_scale > 1 && ev.target.closest('#lightbox-stack')) return;
    ev.preventDefault(); closeLightbox(); return;
  }
  const pic = ev.target.closest('a.pic')?.querySelector('img:last-child');
  if (pic && !(ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey)) {
    ev.preventDefault();
    setLightbox(pic.dataset.full || pic.src, lightboxGroup(pic));
  }
});

/* By class and not by id: the neighbour block is rendered at both ends of the
   page, so there are two of each. `querySelector` takes the first, and both
   carry the same href — which one it finds cannot matter. */
let prev = document.querySelector("a.page-prev");
let next = document.querySelector("a.page-next");

document.addEventListener('keydown', ev => {
    /* **The lightbox takes the keys first and unconditionally** — see
       `setLightbox`. It is the frontmost thing on screen, so it owns the keys
       while it is up, and turning the page out from under it would be the
       surprise.

       Ahead of the modifier guard, not after it, because shift is part of one of
       these bindings: shift-R turns the other way. A guard that dropped every
       modified key before the lightbox saw it would make that binding
       unreachable and look, from outside, like a broken button. */
    if (lightboxOpen()) {
        if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
        const k = ev.key.toLowerCase();
        if (ev.key == "Escape") { ev.preventDefault(); closeLightbox(); }
        else if (ev.key == "ArrowLeft") { ev.preventDefault(); stepLightbox(-1); }
        else if (ev.key == "ArrowRight") { ev.preventDefault(); stepLightbox(1); }
        else if (k == "r") { ev.preventDefault(); rotate(ev.shiftKey ? -1 : 1); }
        else if (k == "0") { ev.preventDefault(); zoomReset(); }
        return;
    }
    if (ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey) return false;
    /* **Not while focus is on the sidebar's own controls.** This binding takes
       Tab away from the browser to put it into the stack, which is the right
       trade in the text; on the TOC switch and the fringe it is a trap — you can
       reach them and then not leave. */
    if (ev.key == "Tab" && STACK.childNodes.length
        && !ev.target.closest('#toc-toggle, #side-hide, #side-show')) { ev.preventDefault(); toggleStack(); }
    if (ev.key == "ArrowLeft" && !selected_stack && prev && prev.href) { ev.preventDefault(); window.location = prev.href; }
    if (ev.key == "ArrowRight" && !selected_stack && next && next.href) { ev.preventDefault(); window.location = next.href; }
    if (selected_stack) {
        if (ev.key == "ArrowUp") { ev.preventDefault(); selectIdx(null, -1); }
        if (ev.key == "ArrowDown") { ev.preventDefault(); selectIdx(null, 1); }
    }
    if (ev.key == "Enter" && selected_stack) { ev.preventDefault(); surfaceSelection(); }
    if (ev.key == "Backspace" && selected_stack) { ev.preventDefault(); deleteSelection(); }
})

let scan_btn = document.getElementById('scan-btn')
if (scan_btn) scan_btn.addEventListener('click', () => openScan());

// Reader view: applied to <html> so it can be set before first paint (see the
// inline script in the head) and never flashes the apparatus on load.
let reader_btn = document.getElementById('reader-btn');
if (reader_btn) reader_btn.addEventListener('click', () => {
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

   **Nothing here builds a figure any more, and that is the point.** The pictures
   and the cross-reference links used to be assembled on this side, off a
   `STATE.figs` / `STATE.figrefs` payload, which made the join over `gt/fig/` the
   one part of the edition a reader with no script never saw: an adjudicated
   caption over a blank space, and a reference that was a dotted underline
   pointing nowhere. The reason for it was only ever `stores.render`'s cache key,
   and that is answered by splicing per request instead — `web/edition
   ._hang_pictures`, off `edition/_figure.html`.

   What is left on this side is what a script is actually for: `openFigure`
   opening a picture in the lightbox, and `a.fig` opening a card in the stack.
   Both bind to markup that is already on the page, so both are enrichment over
   something a reader can already see and follow. */
