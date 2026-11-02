/* The reading view's one script: every page of every edition loads this file and
   no other of its own, and it acts on the markup it finds.

   **The contract is declarative.** A template says what a thing does with an
   attribute, and a page without that attribute costs nothing:

       data-lightbox, -under, data-full, data-caption    a link opens a picture
       data-lightbox-group                               the links inside are one set
       data-modal                                        a link opens a fragment
       data-toggle-class, data-toggle-store              a button toggles <html>
       data-theme-toggle                                 a button flips the theme
       data-scan='PP-NNN'                                a link or button opens that scan
       data-atlas                                        the map pane; loads `map.js`
       data-ref, data-key on a link                      an entity or lexicon card
       data-ipa on a button                              says a form

   `build._derived` restates every one that asks for a URL, so a new one fails the
   static build until it is written down there too. A link keeps a real href: all
   of this is enrichment, and a page with no script still goes where it says.

   **The map is the one thing kept out, and loads only where a pane is.** It is as
   large as everything here put together and most pages have none. It is an ES
   module beside this file, so it finds `geomap.js` for itself.

   Each section is its own function scope, because two of them have a `hide`; what
   one gives another is named below or published for `map.js` on `window`. */
const MAP_READY = document.querySelector('[data-atlas]')
  ? import(new URL('map.js', document.currentScript.src).href)
      .catch(e => { console.error(e); })
  : Promise.resolve();

/* ------------------------------------------------------------ the sidebar

   Its two fringes, which show and hide the column, and its TOC switch, which lays
   the contents over the cards. Everything here degrades: the panels are
   server-rendered, the TOC switch and the fringes are a checkbox and two radios
   the stylesheet reads, the `<details>` open themselves, and the header's ToC link
   keeps an href. What the script adds is the memory of the switch and the fringes
   for the sitting, the header link and the margin as ways to the contents, waking
   the column when something arrives in it, and putting the mark where you can see
   it. Nothing here assumes a column: a page with none finds nothing to bind. */
const SIDEBAR = (() => {
const ROOT = document.documentElement;
const SECONDARY = document.getElementById('secondary');
const PANELS = {
  entities: document.getElementById('panel-entities'),
  contents: document.getElementById('panel-contents'),
};
const SWITCH = document.getElementById('toc-switch');

/* Per sitting, not remembered: `map.js`'s rule, and for its reason — a Contents
   you opened to find your place, or a column you put away to read, is not a
   setting you chose. The classes live on `<html>` because the stylesheet tests
   them there, and because the head script sets them before first paint. */
const SIDE_KEY = 'edition-side';
const SHOWN_KEY = 'edition-sidebar';

/* ---------------------------------------------------------- the column */

/* **The column starts where the header ends, which moves.** The header scrolls
   with the page and the column is sticky, so `--bar-gap` follows the header's
   bottom edge down to 0 rather than holding a gap the header has left. Read on
   the next frame, once per frame however many scroll events arrive. */
const BAR = document.getElementById('bar');
let gapQueued = false;
function barGap() {
  gapQueued = false;
  const gap = BAR ? Math.max(0, BAR.getBoundingClientRect().bottom) : 0;
  ROOT.style.setProperty('--bar-gap', gap + 'px');
}
function queueGap() {
  if (gapQueued) return;
  gapQueued = true;
  requestAnimationFrame(barGap);
}
addEventListener('scroll', queueGap, {passive: true});
addEventListener('resize', queueGap);
barGap();

/* `#side-on` holds the column open however empty it is; `#side-off` hides it
   whatever it holds. One radio group, so exactly one or neither: neither is the
   column deciding for itself, open with cards or a map in it and collapsed
   without. The fringes are their labels, so a click on one is the stylesheet's
   to answer; what is here is the memory, and waking the column for the
   contents and the cards. The classes say the same thing for first paint,
   before this script has set the radios from them. */
const SIDE_ON = document.getElementById('side-on');
const SIDE_OFF = document.getElementById('side-off');

function rememberSidebar() {
  const open = !!(SIDE_ON && SIDE_ON.checked), shut = !!(SIDE_OFF && SIDE_OFF.checked);
  ROOT.classList.toggle('side-open', open);
  ROOT.classList.toggle('side-dismissed', shut);
  try {
    if (open || shut) sessionStorage.setItem(SHOWN_KEY, open ? 'open' : 'closed');
    else sessionStorage.removeItem(SHOWN_KEY);
  } catch (e) {}
}

function setSidebar(open) {
  if (SIDE_ON) SIDE_ON.checked = open;
  if (SIDE_OFF) SIDE_OFF.checked = !open;
  rememberSidebar();
}

/* **Neither, and nothing remembered**: the column back to deciding for itself,
   which with nothing in it is collapsed. */
function letSidebarIdle() {
  if (SIDE_ON) SIDE_ON.checked = false;
  if (SIDE_OFF) SIDE_OFF.checked = false;
  rememberSidebar();
}

const sidebarShowing = () =>
  SECONDARY && getComputedStyle(SECONDARY).display !== 'none';

if (SIDE_ON) SIDE_ON.checked = ROOT.classList.contains('side-open');
if (SIDE_OFF) SIDE_OFF.checked = ROOT.classList.contains('side-dismissed');
[SIDE_ON, SIDE_OFF].forEach(r => r && r.addEventListener('change', rememberSidebar));

/* **Empty** is the idle rule's own condition — no card, the pane shut — asked
   of the DOM the way the stylesheet asks it, so the two cannot disagree about
   when the switch is hidden and the contents are all there is to show. */
const STACK_EL = document.getElementById('stack');
const PANE_EL = document.getElementById('map-pane');
const empty = () => !(STACK_EL && STACK_EL.querySelector('.card'))
  && !(PANE_EL && !PANE_EL.hidden);

/* A card or a map arriving shows the column again: a reader who clicks a name
   wants the card they clicked, not a column they put away a page ago. **And the
   last one leaving puts it away**: an emptied entities panel is not a thing
   anyone asked to look at. Not when the contents were asked for — those stay,
   and only their switch goes, there being nothing left to switch back to.
   **Woken and emptied only from `load` on**, because `edition.js` restores the
   pinned cards as it starts, and a column put away and remembered as away must
   not be reopened by its own furniture coming back. The panel follows from the
   start, so restored cards are what a remembered entities panel shows. */
let loaded = false;
let wasEmpty = empty();
function onContentsChange() {
  const now = empty();
  if (loaded && !SECONDARY.hasAttribute('data-fixed')) {
    if (wasEmpty && !now && ROOT.classList.contains('side-dismissed')) setSidebar(true);
    if (!wasEmpty && now && !asked()) letSidebarIdle();
  }
  wasEmpty = now;
  render();
}
if (STACK_EL) new MutationObserver(onContentsChange).observe(STACK_EL, {childList: true});
if (PANE_EL) new MutationObserver(onContentsChange)
  .observe(PANE_EL, {attributes: true, attributeFilter: ['hidden']});
/* **And not until the map is back.** It repaints the sitting's selection after a
   fetch, which is always after `load`, and that is furniture as much as a pinned
   card is: reading it as a place arriving reopened a column the reader had put away,
   on every page, for as long as anything was on the map. */
Promise.all([new Promise(r => window.addEventListener('load', r)),
             MAP_READY.then(() => window.MAP?.restored)])
  .then(() => { loaded = true; });

/* ---------------------------------------------------------- the panels */

/* **Which panel shows is the stylesheet's**, off `#toc-switch`: the contents
   when the box is checked or the column is empty, the entities otherwise. What
   is left here is what CSS cannot do — remember the choice for the sitting,
   answer the header link and the margin, open a put-away column when the
   contents are asked for, and bring the mark into view. */
const asked = () => !!(SWITCH && SWITCH.checked);
const contentsShowing = () =>
  !!PANELS.contents && PANELS.contents.getClientRects().length > 0;

/* The box and the head script's class say one thing, and the store remembers
   it: the class is what first paint reads, before this script has set the box. */
function remember() {
  ROOT.classList.toggle('side-contents', asked());
  try { sessionStorage.setItem(SIDE_KEY, asked() ? 'contents' : 'entities'); } catch (e) {}
}

/* The mark, brought to where it can be seen. A chapter twenty rows down an
   unscrolled column is a chapter you have to go and find, which is the whole of
   what this panel exists to save you. `nearest` rather than `center`: it moves
   the column only when the mark is actually off it, so a panel that was already
   showing the right place does not jump. Only on the panel coming into view. */
let wasShowing = false;
function render() {
  const now = contentsShowing();
  if (now && !wasShowing) {
    const here = PANELS.contents.querySelector('.here');
    if (here) here.scrollIntoView({block: 'nearest'});
  }
  wasShowing = now;
}

function showPanel(name) {
  if (!SWITCH) return;
  /* The contents asked for is the column asked for. */
  if (name === 'contents' && ROOT.classList.contains('side-dismissed')) setSidebar(true);
  SWITCH.checked = name === 'contents';
  remember();
  render();
}

/* The header link. On an empty column the contents are all it shows, so there
   is nothing to flip to: the link opens the column onto them, or puts it away. */
function flip() {
  if (!sidebarShowing()) return showPanel('contents');
  if (empty()) { showPanel('entities'); return letSidebarIdle(); }
  showPanel(asked() ? 'entities' : 'contents');
}

if (SWITCH) SWITCH.addEventListener('change', () => { remember(); render(); });

/* The header link toggles the same way. `preventDefault` only where there is a
   panel to open — on a view with no sidebar, and on one whose route sent no
   contents, the link is still the way to the printed Contents and must keep
   working. */
const TOC_LINK = document.getElementById('toc-link');
if (TOC_LINK && PANELS.contents) {
  TOC_LINK.addEventListener('click', ev => { ev.preventDefault(); flip(); });
}

/* **The page's left margin opens the contents** — the empty paper left of the
   text. Only a click that lands on nothing else: a link, a control, a picture
   or the column itself keeps its own meaning, and a click in the text is
   reading.

   **And only a click on the page.** The test is a position, and an overlay
   over the page has positions too: a click on the lightbox's backdrop closed
   it and then, landing left of the text, opened the contents. Anything laid
   over `<main>` is appended to the body, so asking for `main` excludes every
   overlay there is and every one added later. */
const PRIMARY = document.getElementById('primary');
if (PRIMARY && PANELS.contents) {
  document.addEventListener('click', ev => {
    if (!ev.target.closest('main')) return;
    if (ev.target.closest('a, button, input, select, textarea, label, img, '
                          + 'figure, #secondary, #bar, .card, .notepop')) return;
    const r = PRIMARY.getBoundingClientRect();
    const textLeft = r.left + parseFloat(getComputedStyle(PRIMARY).paddingLeft);
    if (ev.clientX < textLeft && ev.clientY > r.top) showPanel('contents');
  });
}

/* **The section being read is marked as it is read.** The server marks the
   division a view *is* — a chapter — and stops there: every section of it is
   on the page, and marking by folio lit all of them at once. Which one you are
   in is a question about the scroll, so it is answered here, off the headings
   the text carries (`id='chI.3'`) and the rows that name them (`data-toc`).

   A heading counts once it has risen past the top third of the window: by
   then its section is what fills the screen. The row is marked with what holds
   it, and only marks this added are ever taken off, so the server's own stay. */
const SIDE_BODY = document.getElementById('side-body');
const TRACKED = PANELS.contents && PRIMARY
  ? [...PANELS.contents.querySelectorAll('li[data-toc]')]
      .map(li => [li, document.getElementById(li.dataset.toc)])
      .filter(([, h]) => h && PRIMARY.contains(h))
  : [];
const SERVED = new Set(PANELS.contents ? PANELS.contents.querySelectorAll('.here') : []);
let reading = [], trackQueued = false;

function track() {
  trackQueued = false;
  const line = innerHeight / 3;
  let cur = null, best = -Infinity;
  for (const [li, h] of TRACKED) {
    const top = h.getBoundingClientRect().top;
    if (top <= line && top > best) { best = top; cur = li; }
  }
  const path = [];
  for (let li = cur; li && PANELS.contents.contains(li); li = li.parentElement.closest('li'))
    path.push(li);
  if (path.length === reading.length && path.every((li, i) => li === reading[i])) return;
  for (const li of reading) if (!SERVED.has(li)) li.classList.remove('here');
  for (const li of path) li.classList.add('here');
  reading = path;
  /* Kept in view in the column, and the column alone: `scrollIntoView` would
     move the page too, under the reader's own scroll. */
  if (cur && SIDE_BODY && contentsShowing()) {
    const r = cur.getBoundingClientRect(), b = SIDE_BODY.getBoundingClientRect();
    if (r.top < b.top) SIDE_BODY.scrollTop -= b.top - r.top;
    else if (r.bottom > b.bottom) SIDE_BODY.scrollTop += r.bottom - b.bottom;
  }
}

if (TRACKED.length) {
  addEventListener('scroll', () => {
    if (trackQueued) return;
    trackQueued = true;
    requestAnimationFrame(track);
  }, {passive: true});
  track();
}

/* The head script has already put the class on `<html>`, so the column and its
   panel were right before anything painted; this sets the box to agree, after
   which the box is what the stylesheet reads. Reading the class rather than the
   store, so the two can never say different things. */
if (SWITCH) SWITCH.checked = ROOT.classList.contains('side-contents');
render();
/* A link that opens a card or puts a place on the map is asking for the panel that
   shows it, and the contents laid over it would hide what the click produced. */
/* **And for a column put away, it is asking for the column.** With a card or a map
   already in it nothing arrives into an empty column, so `onContentsChange` has no
   reason to wake it, and the click would land out of sight. */
return {show(name) {
  if (ROOT.classList.contains('side-dismissed')) setSidebar(true);
  showPanel(name);
}};
})();

/* ------------------------------------------------------------ the preview */
/* Prefetch, and a preview while you decide.
 *
 * Two behaviours over one fetch. Resting on a link warms the card so the click
 * costs nothing; resting a little longer floats the card itself beside the
 * link. Both render the *same* `/partial/` fragment the stack renders — there
 * is one template per kind of card and this adds no second one.
 *
 * **Why this does not undo the stack.** The stack exists because a reader
 * consulting an entity should not lose their place, and a tooltip that vanishes
 * is the thing it was built instead of. The preview does not compete with it:
 * it never replaces the click on the link, and it holds nothing the card would
 * not. It answers "is this the one I mean?", which is the question you have
 * before you click, and the stack answers everything after.
 *
 * **It can be reached.** A card's own links are the first thing a reader wants
 * from it, and a look that dies the instant the pointer heads for it offers
 * them and takes them back. So leaving the link only starts a grace period,
 * entering the preview cancels it, and a click inside it lands on what was
 * clicked. A link inside a preview opens no preview of its own: one float at a
 * time, and the stack is where a second one goes. On touch, where nothing
 * hovers, the first tap on a link is the hover and the second is the click.
 *
 * **Nothing here is page-specific**, which is the point of it being its own
 * file: the encyclopedia, the atlas and a card on its own page all want this.
 */
(function () {
  const B = STATE.base;
  const FETCH_MS = 120;   // pointer crossing a dense line must not fetch a dozen
  const DWELL_MS = 400;   // both timers run from the same mouseover, not in sequence
  const GRACE_MS = 300;   // the pointer's crossing from the link into the preview

  /* **Keyed by the URL**, which is the one string this file and `edition.js`
     both already hold. Keying by the ref would mean two vocabularies for one
     identity — `place:markova` here and `ent:place:markova` there — and the
     memo would silently become two memos that never hit. It also makes
     `/partial/` part of the key rather than an assumption about it. */
  const MEMO = new Map();

  function get(url) {
    let p = MEMO.get(url);
    if (!p) {
      p = fetch(url).then(r => {
        if (!r.ok) throw new Error(url + ': HTTP ' + r.status);
        return r.text();
      });
      MEMO.set(url, p);
    }
    return p;
  }
  window.CARDS = {get, place, GRACE_MS};

  /* The same URLs `edition.js` builds, character for character. */
  function urlFor(a) {
    if (a.classList.contains('lex'))
      return B + '/partial/lexicon/' + encodeURIComponent(a.dataset.key);
    return B + '/partial/entity/' + encodeURIComponent(a.dataset.ref);
  }

  /* Not the map's own tree: those names sit directly under the map, so a
     preview opens on top of the thing the hover was asking about — and the
     hover already answers it, by lighting the shape. Not a `map` link either:
     its answer is the pane, composed in the page, and there is no fragment of
     it to fetch. */
  function unpreviewed(a) {
    return !!a.closest('.map-tree') || a.classList.contains('mapref');
  }

  /* `link` is the one the pointer is asking about, `owner` the one the box on
     screen belongs to. They differ while the next preview is in flight. */
  let box = null, owner = null, link = null, tFetch = 0, tShow = 0, tHide = 0;

  function hide() {
    clearTimeout(tFetch); clearTimeout(tShow); clearTimeout(tHide);
    tHide = 0;
    link = owner = null;
    if (box) { box.remove(); box = null; }
  }

  /* Off the link: whatever was pending is dropped, and what is showing waits
     out the grace period in case the pointer is on its way into it. */
  function linger() {
    clearTimeout(tFetch); clearTimeout(tShow);
    link = owner;
    if (box && !tHide) tHide = setTimeout(hide, GRACE_MS);
  }

  function keep() { clearTimeout(tHide); tHide = 0; }

  /* Below the link, or above it where below would run off the bottom, and never
     off either side. Takes its target as an argument rather than closing over
     `box`, because the notes section floats a second thing beside a link in this same
     text and a second copy of this arithmetic is a second thing to get wrong —
     it is published on `window.CARDS` for that.

     **Never over the link.** Where neither side had room — a link mid-screen
     and a tall card — "above" was clamped to the window's top and the card sat
     on the very name being asked about. So the card takes the roomier side and
     is capped to it, scrolling inside rather than spilling over. Above, it is
     pinned by its *bottom* edge, so a picture loading late grows it upward and
     away from the link instead of down onto it.

     A link the line broke is two boxes: the card sits under the last of them or
     over the first, starting where that fragment does. */
  function place(a, el) {
    const rs = a.getClientRects();
    const first = rs[0] || a.getBoundingClientRect(), last = rs[rs.length - 1] || first;
    el.style.maxHeight = '';
    el.style.top = el.style.bottom = '';
    const b = el.getBoundingClientRect();
    const cap = getComputedStyle(el).maxHeight;   // the stylesheet's own limit
    const below = innerHeight - last.bottom - 16, above = first.top - 16;
    const down = b.height <= below || below >= above;
    const r = down ? last : first;
    const room = (down ? below : above) + 'px';
    el.style.maxHeight = cap === 'none' ? room : `min(${cap}, ${room})`;
    if (down) el.style.top = (r.bottom + 8) + 'px';
    else el.style.bottom = (innerHeight - r.top + 8) + 'px';
    el.style.left = Math.max(8, Math.min(r.left, innerWidth - b.width - 8)) + 'px';
  }

  function show(a, html) {
    if (link !== a) return;   // the pointer moved on while the fetch was in flight
    keep();
    owner = a;
    if (!box) {
      box = document.createElement('div');
      box.className = 'card preview';
      document.body.append(box);
    }
    box.innerHTML = '<div class="body">' + html + '</div>';
    place(a, box);
  }

  /* **On a touch screen the first tap is the hover.** There is no resting on a
     link, so a tap on one that is not already previewed shows the preview and
     is swallowed; a second tap on the same link goes through to whatever it
     does. Decided per tap from the pointer's own type, not from a media query,
     because a laptop with a touch screen has both. Capture on `window`, so this
     runs before every document-level click handler and stopping it stops them. */
  let touch = false;
  window.addEventListener('pointerdown', ev => { touch = ev.pointerType === 'touch'; }, true);
  window.addEventListener('click', ev => {
    if (!touch) return;
    if (box && box.contains(ev.target)) return;
    const a = ev.target.closest('a[data-ref], a.lex[data-key]');
    if (!a || unpreviewed(a)) return;
    if (a === owner) return;   // previewed already: the tap is the click
    ev.preventDefault(); ev.stopPropagation();
    hide();
    link = a;
    get(urlFor(a)).then(h => show(a, h)).catch(() => {});
  }, true);

  document.addEventListener('mouseover', ev => {
    /* A tap fires an emulated `mouseover` too; the tap handler above has it. */
    if (touch) return;
    /* Inside the preview, its links included: it stays, and whatever the
       pointer crossed on the way here is no longer being asked about. */
    if (box && box.contains(ev.target)) {
      keep(); clearTimeout(tFetch); clearTimeout(tShow);
      link = owner;
      return;
    }
    /* `a[data-ref]` and not `a.ent` — the atlas tree's node links are `a.node`,
       and a hundred entity names in a column is where a preview earns most. */
    const a = ev.target.closest('a[data-ref], a.lex[data-key]');
    if (!a || unpreviewed(a)) { linger(); return; }
    /* An entity link's body routinely holds an `<em>` or a `.flag`, and
       `mouseover` fires again on each. Restarting the timers there would mean
       the preview never appears on exactly the links most worth previewing. */
    if (a === link) { keep(); return; }
    /* A new link. The box on screen is not torn down here but left on the same
       grace as leaving a link: the way into a preview often crosses another
       name, and the next preview replaces this one when it arrives. */
    linger();
    link = a;
    const url = urlFor(a);
    tFetch = setTimeout(() => get(url).catch(() => {}), FETCH_MS);
    tShow = setTimeout(() => get(url).then(h => show(a, h)).catch(() => {}), DWELL_MS);
  });

  /* Capture, because a scroll inside `#secondary` does not bubble to the
     document — and a preview left behind by a scrolled-away link points at
     nothing. Not a scroll of the preview's own body, which is reading it. */
  document.addEventListener('scroll', ev => {
    if (!(box && box.contains(ev.target))) hide();
  }, true);
  /* A click in the preview that is not on a link — selecting a form to copy
     it — is reading it too. A link goes where it goes, and the look goes. */
  document.addEventListener('click', ev => {
    if (box && box.contains(ev.target) && !ev.target.closest('a')) return;
    hide();
  });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') hide(); });
})();

/* ------------------------------------------------------------ the notes */
/* A footnote read where it is referenced.
 *
 * The note is already on the page — `page.html` renders every one of them into
 * `#foot`, server-side, from `doc.notes`. So this fetches nothing and invents
 * nothing: it floats the note's own rendered body beside the marker that cites
 * it, and the foot stays exactly what it was, which is where the note lives and
 * what a printed page's reader is looking for.
 *
 * **The marker toggles; the jump is in the note:**
 *
 *   hover a marker            a look, gone when the pointer leaves
 *   click it                  the same thing, kept
 *   click it again            gone — the marker is a switch
 *   click anywhere else       gone
 *   `jump ↓`, in a kept note  down to the foot, where the note lives
 *
 * **The jump moved into the popup, and that is why the marker may swallow every
 * click.** `.noteref` is an `<a href="#note-N">` and always has been: with no
 * script it jumps, which is the behaviour this degrades to. With one, the marker
 * becomes a switch — which is only honest if what it took away is still on
 * offer, so the note carries the jump at its own foot, under a rule. A marker
 * that opened on one click and travelled on the next was two acts on one target
 * distinguished by nothing the reader can see.
 *
 * **The jump row is part of the note, and is there whether the note is kept or
 * merely hovered.** Rendering it on the click alone made the popup grow under
 * the pointer — the same note, two shapes, the second arriving as a jolt at the
 * moment of clicking. A reader is looking at the note, not at a widget that
 * reconfigures itself; the row belongs to the note's foot the way the rule above
 * it does, and it says the note continues down there even in the look that
 * cannot reach it.
 *
 * **A kept note is a place.** It is something you read, and a note routinely
 * holds an entity link and a figure reference of its own, so the price is the
 * guard in the outside-click handler.
 */
(function () {
  const FOOT = document.getElementById('foot');
  if (!FOOT) return;          // a page with no notes has nothing to float

  const DWELL_MS = 180;       // a marker is 7px wide; crossing one must not flash

  let box = null, link = null, pinned = false, tShow = 0, tHide = 0;

  function hide() {
    clearTimeout(tShow); clearTimeout(tHide);
    tHide = 0;
    if (box) { box.remove(); box = null; }
    if (link) link.classList.remove('open');
    link = null;
    pinned = false;
  }

  /* The note's own body, cloned out of the foot.
   *
   * **The backlink does not come with it.** In the foot, `<a href="#ref-N">N</a>`
   * is how a reader gets back to the sentence they left; in a popup anchored to
   * that very sentence it is a link to where you already are. The numeral stays,
   * because it is what says which note this is. */
  /* Found by the id the marker links to, not by `data-n`: a chapter's foot holds
     every leaf's notes, each numbered from 1 as printed, and only the id —
     scoped to the leaf by `_scope_notes` — says which note 1 this marker means. */
  function bodyOf(a) {
    const li = FOOT.querySelector(
      `li[id="${CSS.escape(a.getAttribute('href').slice(1))}"]`);
    if (!li) return null;
    const frag = li.cloneNode(true);
    const back = frag.querySelector('a[href^="#ref-"]');
    if (back) {
      const num = document.createElement('span');
      num.className = 'note-n';
      num.textContent = back.textContent;
      back.replaceWith(num);
    }
    return frag.innerHTML;
  }

  function show(a) {
    const html = bodyOf(a);
    if (html == null) return false;
    if (!box) {
      box = document.createElement('div');
      box.className = 'card notepop';
      document.body.append(box);
    }
    /* The href is the anchor's own, read off the marker rather than rebuilt from
       `data-note`: one spelling of the address, and `tei_html` owns it. */
    const jump = '<a class="note-jump" href="' + a.getAttribute('href')
      + '">jump \u2193</a>';
    box.innerHTML = '<div class="body">' + html + jump + '</div>';
    link = a;
    a.classList.add('open');
    /* the preview section's, so the two things that float beside a link in this text are
       placed by one piece of arithmetic. It is loaded before this file. */
    window.CARDS.place(a, box);
    return true;
  }

  /* A hovered note can be reached, as the preview can and for its reason: it
     holds links. Leaving the marker starts the preview section's grace period, and the
     pointer arriving in the note cancels it. */
  function keep() { clearTimeout(tHide); tHide = 0; }
  function linger() {
    clearTimeout(tShow);
    if (box && !tHide) tHide = setTimeout(hide, window.CARDS.GRACE_MS);
  }

  document.addEventListener('mouseover', ev => {
    /* A kept note is not disturbed by the pointer. That is what keeping it
       means: hovering the next marker along must not throw away the note you
       clicked to hold on to. */
    if (pinned) return;
    /* A preview floated off one of the note's own links counts as the note:
       reading it must not take away the thing it was opened from. */
    if (box && (box.contains(ev.target) || ev.target.closest('.card.preview'))) {
      keep(); clearTimeout(tShow); return;
    }
    const a = ev.target.closest('a.noteref');
    if (!a) { linger(); return; }
    if (a === link) { keep(); return; }
    hide();
    tShow = setTimeout(() => show(a), DWELL_MS);
  });

  /* Capture, so this runs before the preview section's own `click → hide` and before the
     anchor's default. Four cases, in the order they have to be tested. */
  document.addEventListener('click', ev => {
    /* The jump, first: it is inside the popup, so the outside-click case below
       would not fire — but leaving the note floating over the foot you have just
       travelled to would be the note on screen twice. The default is allowed
       through, which is what performs the jump. */
    if (ev.target.closest('.note-jump')) { hide(); return; }
    const a = ev.target.closest('a.noteref');
    if (a) {
      /* **The marker is a switch, so every click on it is swallowed.** The jump
         it used to perform is in the note now, under its own rule. */
      ev.preventDefault();
      const same = a === link && pinned;
      hide();
      if (!same && show(a)) pinned = true;
      return;
    }
    /* Anywhere else — but not inside the popup itself, which is a place and not
       a look: a click on an entity link in a kept note must reach that link. */
    if (box && !ev.target.closest('.notepop')) hide();
  }, true);

  /* Capture, because a scroll inside `#secondary` does not bubble to the
     document. A look goes; a kept note follows its marker, since it is
     `position:fixed` and the text moves out from under it. Once the marker has
     left the window there is nothing for it to be beside, and `place` would peg
     it to an edge pointing at nothing — so it goes then too. */
  document.addEventListener('scroll', ev => {
    if (box && box.contains(ev.target)) return;   // reading a long note
    if (!pinned) { hide(); return; }
    const r = link.getBoundingClientRect();
    if (r.bottom < 0 || r.top > innerHeight) hide();
    else window.CARDS.place(link, box);
  }, true);
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') hide(); });
})();

/* ------------------------------------------------------------ the stack, the lightbox, the modal */
(() => {
const B = STATE.base;
// The cards. The stack was the whole column until the map pane moved in above
// it, and the pane stays outside it: everything here indexes
// `STACK.children` as cards, and a pane among them would be pinned and closed
// like one.
const STACK = document.getElementById('stack');
const KEY = 'edition-pins-' + STATE.base + '-' + STATE.ref;

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
    if (b.dataset.act === 'close') { el.remove(); savePins(); }
    if (b.dataset.act === 'pin') {
      el.classList.toggle('pinned');
      b.textContent = el.classList.contains('pinned') ? 'unpin' : 'pin';
      if (el.classList.contains('pinned')) STACK.prepend(el);
      savePins();
    }
  });
  return el;
}

/* Through the preview section's memo, so a card rested on before it was clicked is
   already fetched and the `loading…` state never paints. */
async function fill(id, url, title) {
  const c = push(id, () => card(id, title, 'loading…', ''));
  const html = await window.CARDS.get(url);
  c.querySelector('.body').innerHTML = html;
  return c;
}

function togglePin(c) {
  let pinned = c.classList.toggle('pinned');
  c.querySelector('[data-act=pin]').textContent = pinned ? 'unpin' : 'pin';
  savePins();
  return pinned;
}

const openEntity = ref =>
  fill('ent:' + ref, B + '/partial/entity/' + encodeURIComponent(ref), ref);

/* The stack, for `map.js` to reach when a click turns out to want a card. That
   file owns the pane and this one owns the stack, and neither reaches into the
   other's DOM, which is why the hand-off is a named function. */
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

/* One leaf's scan, named by whatever carries `data-scan`, so a run's leaves each
   open their own and two of them can sit in the stack side by side. */
function openScan(ref) {
  const id = 'scan:' + ref;
  push(id, () => card(id, 'The scan', ref,
    `<div class="crop"><a class="pic" href="${B}/page/${ref}.png" target="_blank"
        rel="noopener"><img src="${B}/page/${ref}.png" style="position:static;width:100%"
        alt="scan ${ref}"></a></div>`));
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
  /* These open cards, and where there is no stack the link's own href still goes
     to the same thing. This file loads on every page; not every page has one. */
  if (!STACK && ev.target.closest('a.ent, a.lex, a.yt, a.fig')) return;
  /* Whatever it opens lands in the entities panel, so that is the panel to show:
     the contents laid over it would hide what the click produced. Not on a
     ctrl/meta click, which is the browser's new tab and puts nothing here. */
  if (ev.target.closest('a.ent, a.lex, a.yt, a.fig') && !ev.ctrlKey && !ev.metaKey)
    SIDEBAR.show('entities');
  /* A modified click on a scan link is the browser's: the raster, in a tab. */
  const scan = ev.target.closest('[data-scan]');
  if (scan && !(ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey)) {
    ev.preventDefault();
    SIDEBAR.show('entities');
    openScan(scan.dataset.scan);
    return;
  }
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
    MAP_READY.then(() => window.MAP ? window.MAP.click(ref, {toggle: false}) : 'card')
             .then(w => { if (w == 'card') openEntity(ref); });
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
  if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
  /* Declared on any link, whose href is what a reader without this script gets:
     `data-lightbox` is the picture, `data-lightbox-under` a Mixed Raster pair's
     lower layer, `data-full` the file, `data-caption` what it is called. Links
     inside a `data-lightbox-group` are one set, and the arrows walk it. */
  const shown = ev.target.closest('a[data-lightbox]');
  if (shown) {
    ev.preventDefault();
    const set = shown.closest('[data-lightbox-group]');
    setLightbox(shown.dataset.lightbox,
      (set ? [...set.querySelectorAll('a[data-lightbox]')] : [shown]).map(({dataset: d}) => (
        {src: d.lightbox, under: d.lightboxUnder || null, full: d.full || null,
         caption: d.caption || '', referrer: ''})));
    return;
  }
  /* `data-modal` is a fragment to show over the page. */
  const modalLink = ev.target.closest('a[data-modal]');
  if (modalLink) { ev.preventDefault(); openModal(modalLink); return; }
  const pic = ev.target.closest('a.pic')?.querySelector('img:last-child');
  if (pic) {
    ev.preventDefault();
    setLightbox(pic.dataset.full || pic.src, lightboxGroup(pic));
  }
});

/* One `<dialog>`, for whatever a `data-modal` link names. The element brings Esc,
   the focus trap and the backdrop. A fragment that will not load sends the reader
   to the link's own page, which says the same thing. */
let modal = null;
async function openModal(link) {
  let html;
  try {
    const r = await fetch(link.dataset.modal);
    if (!r.ok) throw new Error(r.status);
    html = await r.text();
  } catch {
    window.location = link.href;
    return;
  }
  if (!modal) {
    modal = document.createElement('dialog');
    modal.id = 'modal';
    modal.innerHTML = `<button class="modal-close" title="close (Esc)"
      aria-label="close">×</button><div class="modal-body"></div>`;
    /* The dialog has no padding of its own, so a click whose target is the dialog
       itself landed on the backdrop. */
    modal.addEventListener('click', ev => {
      if (ev.target === modal || ev.target.closest('.modal-close')) modal.close();
    });
    document.body.append(modal);
  }
  modal.querySelector('.modal-body').innerHTML = html;
  modal.showModal();
  modal.scrollTop = 0;
}

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
    /* A modal is over the page too, and the page does not turn under it. */
    if (modal?.open) return;
    if (ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey) return false;
    /* **Tab is the browser's**: taken for the stack, it trapped focus wherever
       a card was open. The cards' own buttons pin and close them. */
    if (ev.key == "ArrowLeft" && prev && prev.href) { ev.preventDefault(); window.location = prev.href; }
    if (ev.key == "ArrowRight" && next && next.href) { ev.preventDefault(); window.location = next.href; }
})

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
  else if (id.startsWith('scan:') && id != 'scan:page') openScan(id.slice(5));
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
})();

/* ------------------------------------------------------------ small declared acts */

document.addEventListener('click', ev => {
  const say = ev.target.closest('button.speak');
  if (say) {
    ev.preventDefault();
    const a = new Audio(STATE.base + '/tts/' + encodeURIComponent(say.dataset.ipa) + '.wav');
    a.play().catch(() => {
      say.disabled = true;
      say.title = 'no audio — espeak-ng is not installed on the host';
    });
    return;
  }
  /* A class on <html>, so it can be set before first paint (see the inline script
     in the head) and never flashes; the store is what that script reads. */
  const toggle = ev.target.closest('[data-toggle-class]');
  if (toggle) {
    const on = document.documentElement.classList.toggle(toggle.dataset.toggleClass);
    localStorage.setItem(toggle.dataset.toggleStore, on ? '1' : '');
    return;
  }
  /* Flips whatever is on screen, which is not the same as flipping a stored value:
     until the toggle is first pressed there is no stored value and the page is
     showing the system's theme, so the current state has to be *read* rather than
     assumed. Reading it from the attribute when there is one and from `matchMedia`
     when there is not means the first press always does the visible thing. */
  if (ev.target.closest('[data-theme-toggle]')) {
    const root = document.documentElement;
    const dark = root.dataset.theme
      ? root.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    localStorage.setItem('edition-theme', root.dataset.theme);
  }
});

/* **A passage copied across a page turn comes out as the sentence.** `user-select`
   keeps the mark's words out of the clipboard, but a mark is positioned out of the
   line, and a browser still writes a line break for one, mid-sentence. So only a
   selection that crosses a mark has its text read with the marks out of layout for
   that instant. Anything else copies as the browser would, formatting included. */
document.addEventListener('copy', ev => {
  const sel = getSelection();
  if (!sel.rangeCount) return;
  const range = sel.getRangeAt(0);
  const crosses = [...document.querySelectorAll('.leaf-at')]
    .some(m => range.intersectsNode(m));
  if (!crosses) return;
  const root = document.documentElement;
  root.classList.add('copying');
  const text = sel.toString();
  root.classList.remove('copying');
  ev.clipboardData.setData('text/plain', text);
  ev.preventDefault();
});
