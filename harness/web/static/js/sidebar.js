/* The sidebar's two tabs.

   Its own file rather than a section of `edition.js`, because the views that
   need it are not the views that load that one: `edition.js` looks up
   `#scan-btn` unconditionally at load and throws without one — which is why
   `run.html` and `exempt.html` carry a button they have no use for — and
   `card.html` does not load it at all. A tab bar that only worked on three of
   the four pages carrying it would be worse than none.

   Everything here degrades: the panels are server-rendered, the `<details>`
   open themselves, and the ToC link keeps an href. What the script adds is the
   switch, the memory of it, and putting the mark where you can see it. */
const TABS = document.getElementById('side-tabs');
const PANELS = {
  entities: document.getElementById('panel-entities'),
  contents: document.getElementById('panel-contents'),
};

/* Per sitting, not remembered: `map.js`'s rule, and for its reason — a Contents
   you opened to find your place is not a setting you chose. The class lives on
   `<html>` because the stylesheet's idle rule tests it there, and because the
   head script has to be able to set it before first paint. */
const SIDE_KEY = 'edition-side';

let shown = null;

function showPanel(name) {
  if (!PANELS.contents) name = 'entities';   // no contents tab on this view
  if (name === shown) return;
  shown = name;
  for (const [key, el] of Object.entries(PANELS)) {
    if (el) el.hidden = key !== name;
  }
  for (const b of TABS.querySelectorAll('.tab')) {
    b.classList.toggle('on', b.dataset.panel === name);
  }
  document.documentElement.classList.toggle('side-contents', name === 'contents');
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

TABS.addEventListener('click', ev => {
  const b = ev.target.closest('.tab');
  if (b) showPanel(b.dataset.panel);
});

/* The header link, which **toggles**: it is one control over one panel, and a
   control that only opens leaves you reaching for the tab bar to undo what the
   header just did. Pressing it again puts the column back where it was, which on
   a page nobody has clicked anything in means gone.

   `preventDefault` only where there is a panel to open — on a view with no
   sidebar, and on one whose route sent no contents, the link is still the way to
   the printed Contents and must keep working. */
const TOC_LINK = document.getElementById('toc-link');
if (TOC_LINK && PANELS.contents) {
  TOC_LINK.addEventListener('click', ev => {
    ev.preventDefault();
    showPanel(shown === 'contents' ? 'entities' : 'contents');
  });
}

/* The head script has already put the class on `<html>`, so the column is the
   right width before anything painted; this is what makes the *panels* agree
   with it. Reading the class rather than the store, so the two can never say
   different things. */
showPanel(document.documentElement.classList.contains('side-contents')
          ? 'contents' : 'entities');
