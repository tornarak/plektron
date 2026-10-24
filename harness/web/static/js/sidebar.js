/* The sidebar: its two fringes, which show and hide the column, and its TOC
   switch, which lays the contents over the cards.

   Its own file rather than a section of `edition.js`, because the views that
   need it are not the views that load that one: `edition.js` looks up
   `#scan-btn` unconditionally at load and throws without one — which is why
   `run.html` and `exempt.html` carry a button they have no use for — and
   `card.html` does not load it at all. Controls that only worked on three of
   the four pages carrying them would be worse than none.

   Everything here degrades: the entities panel is server-rendered, the
   `<details>` open themselves, and the header's ToC link keeps an href. What the
   script adds is the two switches, the memory of them, the contents' outline
   (fetched, see `loadContents`; the panel is `hidden` without the script
   anyway), and putting the mark where you can see it. */
const ROOT = document.documentElement;
const SECONDARY = document.getElementById('secondary');
const PANELS = {
  entities: document.getElementById('panel-entities'),
  contents: document.getElementById('panel-contents'),
};
const TOGGLE = document.getElementById('toc-toggle');

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

/* `.side-open` holds the column open however empty it is; `.side-dismissed`
   hides it whatever it holds. Exactly one or neither: neither is the column
   deciding for itself, open with cards or a map in it and collapsed without. */
function setSidebar(open) {
  ROOT.classList.toggle('side-open', open);
  ROOT.classList.toggle('side-dismissed', !open);
  try { sessionStorage.setItem(SHOWN_KEY, open ? 'open' : 'closed'); } catch (e) {}
}

/* **Neither class, and nothing remembered**: the column back to deciding for
   itself, which with nothing in it is collapsed. */
function letSidebarIdle() {
  ROOT.classList.remove('side-open', 'side-dismissed');
  try { sessionStorage.removeItem(SHOWN_KEY); } catch (e) {}
}

const sidebarShowing = () =>
  SECONDARY && getComputedStyle(SECONDARY).display !== 'none';

['side-hide', 'side-show'].forEach(fringe => {
  const b = document.getElementById(fringe);
  if (b) b.addEventListener('click', () => setSidebar(!sidebarShowing()));
});

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
    if (!wasEmpty && now && wanted !== 'contents') letSidebarIdle();
  }
  wasEmpty = now;
  render();
}
if (STACK_EL) new MutationObserver(onContentsChange).observe(STACK_EL, {childList: true});
if (PANE_EL) new MutationObserver(onContentsChange)
  .observe(PANE_EL, {attributes: true, attributeFilter: ['hidden']});
window.addEventListener('load', () => { loaded = true; });

/* ---------------------------------------------------------- the panels */

/* `wanted` is the panel asked for; what shows is that, **unless the column is
   empty, when it is the contents** — a column opened onto nothing opens onto
   the book's outline, with no switch between it and a panel with nothing in
   it. The switch itself is hidden by the stylesheet on the same condition. */
let wanted = 'entities';
let shown = null;

function render() {
  const name = !PANELS.contents ? 'entities'   // no contents on this view
    : empty() ? 'contents' : wanted;
  if (name === shown) return;
  shown = name;
  for (const [key, el] of Object.entries(PANELS)) {
    if (el) el.hidden = key !== name;
  }
  /* "TOC" opens, "cancel" puts back: one control, and its label says what
     pressing it will do rather than what is showing. */
  if (TOGGLE) {
    TOGGLE.textContent = name === 'contents' ? 'cancel' : 'TOC';
    TOGGLE.setAttribute('aria-expanded', String(name === 'contents'));
  }
  /* The mark, brought to where it can be seen. A chapter twenty rows down an
     unscrolled column is a chapter you have to go and find, which is the whole
     of what this panel exists to save you. `nearest` rather than `center`: it
     moves the column only when the mark is actually off it, so a panel that was
     already showing the right place does not jump. */
  if (name === 'contents') loadContents().then(showMark);
}

function showMark() {
  if (PANELS.contents.hidden) return;
  const here = PANELS.contents.querySelector('.here');
  if (here) here.scrollIntoView({block: 'nearest'});
}

/* ---------------------------------------------------------- the outline */

/* **The outline is fetched; the page ships only its marks.** It is the same on
   every page and was ~77 KB of each, so the route serves it once
   (`/partial/toc`) and the page carries `data-marks`: the rows marked, the
   disclosures open, the counts — all decided by `_toc_panel`, which is where
   the rule lives. This only puts them where they name.

   Fetched the first time the panel is shown, and otherwise once the browser is
   idle after load, so the switch does not wait on the network; a host caches it
   across pages. One request per page however often it is asked for, and a
   failure is said in the panel and tried again on the next showing. */
let outline = null;
function loadContents() {
  const panel = PANELS.contents;
  if (!panel) return Promise.resolve();
  if (outline) return outline;
  outline = fetch(panel.dataset.tocSrc)
    .then(r => r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`)))
    .then(html => {
      const t = document.createElement('template');
      t.innerHTML = html;
      panel.querySelector('.load-failed')?.remove();
      panel.prepend(t.content);
      applyMarks(panel, JSON.parse(panel.dataset.marks || '{}'));
      startTracking();
    })
    .catch(err => {
      outline = null;
      if (!panel.querySelector('.load-failed')) {
        const p = document.createElement('p');
        p.className = 'meta panel-note load-failed';
        p.textContent = `The contents could not be loaded (${err.message}).`;
        panel.prepend(p);
      }
    });
  return outline;
}

function applyMarks(panel, {here = [], open = [], hits = {}}) {
  const rows = new Map([...panel.querySelectorAll('li[data-toc]')]
    .map(li => [li.dataset.toc, li]));
  for (const id of here) rows.get(id)?.classList.add('here');
  for (const id of open) {
    const d = rows.get(id)?.querySelector(':scope > details');
    if (d) d.open = true;
  }
  for (const [id, n] of Object.entries(hits)) {
    const title = rows.get(id)?.querySelector('.toc-title');
    if (!title) continue;
    const s = document.createElement('span');
    s.className = 'hits';
    s.title = `${n} mention(s)`;
    s.textContent = n;
    title.after(' ', s);
  }
}

window.addEventListener('load', () => {
  if (PANELS.contents) (window.requestIdleCallback || setTimeout)(loadContents);
});

function showPanel(name) {
  if (!PANELS.contents) name = 'entities';
  /* The contents asked for is the column asked for. */
  if (name === 'contents' && ROOT.classList.contains('side-dismissed')) setSidebar(true);
  wanted = name;
  ROOT.classList.toggle('side-contents', name === 'contents');
  try { sessionStorage.setItem(SIDE_KEY, name); } catch (e) {}
  render();
}

/* The header link and the switch. On an empty column the contents are all it
   shows, so there is nothing to flip to: the link opens the column onto them,
   or puts it away. */
function flip() {
  if (!sidebarShowing()) return showPanel('contents');
  if (empty()) { showPanel('entities'); return letSidebarIdle(); }
  showPanel(wanted === 'contents' ? 'entities' : 'contents');
}

/* For `edition.js`: a link that opens a card or puts a place on the map is
   asking for the panel that shows it, and the contents laid over it would hide
   the very thing the click produced. */
window.SIDEBAR = {show: showPanel};

if (TOGGLE) TOGGLE.addEventListener('click', flip);

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
   it, and only marks this added are ever taken off, so the server's own stay.
   Started once the outline is in (`loadContents`), since the rows are its. */
const SIDE_BODY = document.getElementById('side-body');
let TRACKED = [], SERVED = new Set();
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
  if (cur && SIDE_BODY && !PANELS.contents.hidden) {
    const r = cur.getBoundingClientRect(), b = SIDE_BODY.getBoundingClientRect();
    if (r.top < b.top) SIDE_BODY.scrollTop -= b.top - r.top;
    else if (r.bottom > b.bottom) SIDE_BODY.scrollTop += r.bottom - b.bottom;
  }
}

function startTracking() {
  if (!PRIMARY) return;
  TRACKED = [...PANELS.contents.querySelectorAll('li[data-toc]')]
    .map(li => [li, document.getElementById(li.dataset.toc)])
    .filter(([, h]) => h && PRIMARY.contains(h));
  SERVED = new Set(PANELS.contents.querySelectorAll('.here'));
  if (!TRACKED.length) return;
  addEventListener('scroll', () => {
    if (trackQueued) return;
    trackQueued = true;
    requestAnimationFrame(track);
  }, {passive: true});
  track();
}

/* The head script has already put the classes on `<html>`, so the column is the
   right width before anything painted; this is what makes the *panels* agree
   with it. Reading the class rather than the store, so the two can never say
   different things. */
showPanel(ROOT.classList.contains('side-contents') ? 'contents' : 'entities');
