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

/* `.side-open` holds the column open however empty it is; `.side-dismissed`
   hides it whatever it holds. Exactly one or neither: neither is the column
   deciding for itself, open with cards or a map in it and collapsed without. */
function setSidebar(open) {
  ROOT.classList.toggle('side-open', open);
  ROOT.classList.toggle('side-dismissed', !open);
  try { sessionStorage.setItem(SHOWN_KEY, open ? 'open' : 'closed'); } catch (e) {}
}

const sidebarShowing = () =>
  SECONDARY && getComputedStyle(SECONDARY).display !== 'none';

['side-hide', 'side-show'].forEach(fringe => {
  const b = document.getElementById(fringe);
  if (b) b.addEventListener('click', () => setSidebar(!sidebarShowing()));
});

/* A card or a map arriving shows the column again: a reader who clicks a name
   wants the card they clicked, not a column they put away a page ago.
   **Watched only from `load` on**, because `edition.js` restores the pinned
   cards as it starts, and a column put away and remembered as away must not be
   reopened by its own furniture coming back. */
window.addEventListener('load', () => {
  const wake = () => { if (ROOT.classList.contains('side-dismissed')) setSidebar(true); };
  const stack = document.getElementById('stack');
  if (stack) new MutationObserver(wake).observe(stack, {childList: true});
  const pane = document.getElementById('map-pane');
  if (pane) new MutationObserver(() => { if (!pane.hidden) wake(); })
    .observe(pane, {attributes: true, attributeFilter: ['hidden']});
});

/* ---------------------------------------------------------- the panels */

let shown = null;

function showPanel(name) {
  if (!PANELS.contents) name = 'entities';   // no contents on this view
  /* The contents asked for is the column asked for. */
  if (name === 'contents' && ROOT.classList.contains('side-dismissed')) setSidebar(true);
  if (name === shown) return;
  shown = name;
  for (const [key, el] of Object.entries(PANELS)) {
    if (el) el.hidden = key !== name;
  }
  ROOT.classList.toggle('side-contents', name === 'contents');
  /* "TOC" opens, "cancel" puts back: one control, and its label says what
     pressing it will do rather than what is showing. */
  if (TOGGLE) {
    TOGGLE.textContent = name === 'contents' ? 'cancel' : 'TOC';
    TOGGLE.setAttribute('aria-expanded', String(name === 'contents'));
  }
  try { sessionStorage.setItem(SIDE_KEY, name); } catch (e) {}
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

const flip = () => showPanel(shown === 'contents' ? 'entities' : 'contents');

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
