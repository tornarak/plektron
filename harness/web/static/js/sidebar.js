/* The sidebar: its two fringes, which show and hide the column, and its TOC
   switch, which lays the contents over the cards.

   Its own file rather than a section of `edition.js`, because the views that
   need it are not the views that load that one: `edition.js` looks up
   `#scan-btn` unconditionally at load and throws without one — which is why
   `run.html` and `exempt.html` carry a button they have no use for — and
   `card.html` does not load it at all. Controls that only worked on three of
   the four pages carrying them would be worse than none.

   Everything here degrades: the panels are server-rendered, the `<details>`
   open themselves, and the header's ToC link keeps an href. What the script
   adds is the two switches, the memory of them, and putting the mark where you
   can see it. */
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
  if (name === 'contents') {
    const here = PANELS.contents.querySelector('.here');
    if (here) here.scrollIntoView({block: 'nearest'});
  }
}

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
   reading. */
const PRIMARY = document.getElementById('primary');
if (PRIMARY && PANELS.contents) {
  document.addEventListener('click', ev => {
    if (ev.target.closest('a, button, input, select, textarea, label, img, '
                          + 'figure, #secondary, #bar, .card, .notepop')) return;
    const r = PRIMARY.getBoundingClientRect();
    const textLeft = r.left + parseFloat(getComputedStyle(PRIMARY).paddingLeft);
    if (ev.clientX < textLeft && ev.clientY > r.top) showPanel('contents');
  });
}

/* The head script has already put the classes on `<html>`, so the column is the
   right width before anything painted; this is what makes the *panels* agree
   with it. Reading the class rather than the store, so the two can never say
   different things. */
showPanel(ROOT.classList.contains('side-contents') ? 'contents' : 'entities');
