/* Prefetch, and a preview while you decide.
 *
 * Two behaviours over one fetch. Resting on a link warms the card so the click
 * costs nothing; resting a little longer floats the card itself beside the
 * link. Both render the *same* `?partial=1` fragment the stack renders — there
 * is one template per kind of card and this adds no second one.
 *
 * **Why this does not undo the stack.** The stack exists because a reader
 * consulting an entity should not lose their place, and a tooltip that vanishes
 * is the thing it was built instead of. The preview does not compete with it:
 * it never replaces the click, it is `pointer-events:none` so nothing can be
 * *done* in it, and it holds nothing the card would not. It answers "is this the
 * one I mean?", which is the question you have before you click, and the stack
 * answers everything after.
 *
 * **Nothing here is page-specific**, which is the point of it being its own
 * file: `edition.js` cannot load outside `page.html` because it binds
 * `#scan-btn` and `#reader-btn` unconditionally, and the encyclopedia, the atlas
 * and a card on its own page all want this.
 */
(function () {
  const B = STATE.base;
  const FETCH_MS = 120;   // pointer crossing a dense line must not fetch a dozen
  const DWELL_MS = 400;   // both timers run from the same mouseover, not in sequence

  /* **Keyed by the URL**, which is the one string this file and `edition.js`
     both already hold. Keying by the ref would mean two vocabularies for one
     identity — `place:markova` here and `ent:place:markova` there — and the
     memo would silently become two memos that never hit. It also makes
     `?partial=1` part of the key rather than an assumption about it. */
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
  window.CARDS = {get};

  /* The same three URLs `edition.js` builds, character for character. */
  function urlFor(a) {
    if (a.classList.contains('lex'))
      return B + '/lexicon/' + encodeURIComponent(a.dataset.key) + '?partial=1';
    if (a.classList.contains('mapref'))
      return B + '/map/' + encodeURIComponent(a.dataset.ref) + '?partial=1';
    return B + '/entity/' + encodeURIComponent(a.dataset.ref) + '?partial=1';
  }

  let box = null, link = null, tFetch = 0, tShow = 0;

  function hide() {
    clearTimeout(tFetch); clearTimeout(tShow);
    link = null;
    if (box) { box.remove(); box = null; }
  }

  function place(a) {
    const r = a.getBoundingClientRect(), b = box.getBoundingClientRect();
    let y = r.bottom + 8;
    if (y + b.height > innerHeight - 8) y = Math.max(8, r.top - b.height - 8);
    const x = Math.max(8, Math.min(r.left, innerWidth - b.width - 8));
    box.style.left = x + 'px';
    box.style.top = y + 'px';
  }

  function show(a, html) {
    if (link !== a) return;   // the pointer moved on while the fetch was in flight
    if (!box) {
      box = document.createElement('div');
      box.className = 'card preview';
      document.body.append(box);
    }
    box.innerHTML = '<div class="body">' + html + '</div>';
    place(a);
  }

  document.addEventListener('mouseover', ev => {
    /* `a[data-ref]` and not `a.ent` — the atlas tree's node links are `a.node`,
       and a hundred entity names in a column is where a preview earns most. */
    const a = ev.target.closest('a[data-ref], a.lex[data-key]');
    if (!a) { hide(); return; }
    /* Unreachable while the preview is `pointer-events:none`, and here for the
       day it is not: without it a preview could open a preview. */
    if (a.closest('.card.preview')) return;
    /* Not in the map's own tree. Those names sit directly under the map, so a
       preview opens on top of the thing the hover was asking about — and the
       hover already answers it, by lighting the shape. */
    if (a.closest('.map-tree')) { hide(); return; }
    /* An entity link's body routinely holds an `<em>` or a `.flag`, and
       `mouseover` fires again on each. Restarting the timers there would mean
       the preview never appears on exactly the links most worth previewing. */
    if (a === link) return;
    hide();
    link = a;
    const url = urlFor(a);
    tFetch = setTimeout(() => get(url).catch(() => {}), FETCH_MS);
    tShow = setTimeout(() => get(url).then(h => show(a, h)).catch(() => {}), DWELL_MS);
  });

  /* Capture, because a scroll inside `#secondary` does not bubble to the
     document — and a preview left behind by a scrolled-away link points at
     nothing. */
  document.addEventListener('scroll', hide, true);
  document.addEventListener('click', hide);
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') hide(); });
})();
