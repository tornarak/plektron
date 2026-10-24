/* The sidebar: its two fringes, which show and hide the column, and its TOC
   switch, which lays the contents over the cards.

   Its own file rather than a section of `edition.js`, because the views that
   need it are not the views that load that one: `edition.js` looks up
   `#scan-btn` unconditionally at load and throws without one — which is why
   `run.html` and `exempt.html` carry a button they have no use for — and
   `card.html` does not load it at all. Controls that only worked on three of
   the four pages carrying them would be worse than none.

   Everything here degrades: the panels are server-rendered, the TOC switch and
   the fringes are a checkbox and two radios the stylesheet reads, the
   `<details>` open themselves, and the header's ToC link keeps an href. What
   the script adds is the memory of the switch and the fringes for the sitting,
   the header link and the margin as ways to the contents, waking the column
   when something arrives in it, and putting the mark where you can see it. */
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
window.addEventListener('load', () => { loaded = true; });

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

/* For `edition.js`: a link that opens a card or puts a place on the map is
   asking for the panel that shows it, and the contents laid over it would hide
   the very thing the click produced. */
window.SIDEBAR = {show: showPanel};

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
