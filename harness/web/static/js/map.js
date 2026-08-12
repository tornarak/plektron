/* The map pane, and the highlight that makes it answer questions.
 *
 * **One map per sitting, not one card per map.** A map used to be a card like
 * any other: two of them could sit in the stack at once saying different things
 * about where you are, and the next three cards could push both out of sight.
 * There is only ever one *here*, so there is one pane, it stays above the stack,
 * and clicking a place moves it rather than adding to it.
 *
 * **Every path on that map says whose it is** (`geomap.owned`), which is what
 * lets a name anywhere on the page light up its shape: a `contains` row, a node
 * in the atlas tree, an entity in the running text. Nothing about a path's
 * geometry leads back to a record — a drawn member is the nearest descendant
 * *with* a shape, found by descending through those without, and two entities
 * may share one polygon — so the identity has to travel with the path.
 *
 * **What is drawn is what gets prefetched.** The pane is the authority on which
 * records are in play, and it already lists them: after it loads, every
 * `[data-ent]` on it has its card fetched into `hover.js`'s memo. So the parents
 * and children of wherever you are open with nothing to wait for, and there is
 * no second list of "related entities" to keep in step with the drawing.
 */
(function () {
  const B = STATE.base;
  const pane = () => document.getElementById('map-pane');

  /* Prefetch is best-effort and silent: it is a saving, and a failed one is
     just the click paying what it would have paid anyway. */
  function warm(root) {
    if (!window.CARDS) return;
    /* Two sources, and they are not the same set. `data-ent` is what can be
       highlighted — what is actually drawn. `.warm` is every ancestor and
       descendant at any depth, which the fragment states because the drawing
       cannot: `member_shapes` stops at the nearest descendant *with* a shape, so
       the Chukchee Peninsula is on no layer of the Russian Far East's map and is
       still one click from it. */
    const ids = new Set();
    for (const el of root.querySelectorAll('[data-ent]')) ids.add(el.dataset.ent);
    for (const el of root.querySelectorAll('.warm[data-warm]'))
      for (const id of el.dataset.warm.split(/\s+/)) ids.add(id);
    ids.delete('');
    for (const id of ids)
      window.CARDS.get(B + '/entity/' + encodeURIComponent(id) + '?partial=1')
                  .catch(() => {});
  }

  /* Dismissal is "not this one", not a setting — see `_pane.html`. Nothing is
     written down, so `show` needs no permission to reopen. */
  async function show(ref) {
    const p = pane();
    if (!p) return;
    const r = await fetch(B + '/map/' + encodeURIComponent(ref) + '?partial=1');
    if (!r.ok) return;
    const html = await r.text();
    /* **An entity the atlas cannot draw leaves the pane alone.** Chuvan, Kerek,
       Siberian Yupik and Tundra Yukaghir have no shape, no point and no located
       descendant; swapping a map you were reading for a sentence about an
       absence loses more than it says, and the card's own `_props` rows say it
       anyway. The fragment identifies itself — no `svg.map`, no map. */
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    if (!tmp.querySelector('svg.map')) return;
    p.querySelector('.body').innerHTML = html;
    p.hidden = false;
    warm(p);
  }

  document.addEventListener('click', ev => {
    const b = ev.target.closest('#map-pane .dismiss');
    if (b) { pane().hidden = true; return; }
    /* `a.mapref` is "put this one in the pane", and it means that on every page:
       in the stack, where `edition.js` would otherwise have opened a card, and on
       an entity's own page, where the anchor would otherwise navigate away to a
       map with none of the entry beside it. */
    const m = ev.target.closest('a.mapref[data-ref]');
    if (m) { ev.preventDefault(); show(m.dataset.ref); }
  });

  /* Highlight follows the pointer over any entity link, and simply finds nothing
     when that entity is not on the current map — which is most of them, and is
     why this needs no notion of what the subject is. */
  let lit = [];
  function light(ref) {
    for (const el of lit) el.classList.remove('hi');
    lit = [];
    const p = pane();
    if (!p || p.hidden || !ref) return;
    lit = [...p.querySelectorAll(`[data-ent="${CSS.escape(ref)}"]`)];
    for (const el of lit) el.classList.add('hi');
  }

  /* Any anchor naming an entity, not `a.ent` alone: the atlas tree's node links
     are `a.node`, and they are the thing a pointer is actually on there. */
  document.addEventListener('mouseover', ev => {
    const a = ev.target.closest('a[data-ref]');
    light(a && !a.closest('.card.preview') ? a.dataset.ref : '');
  });

  /* A pane the server rendered has never been through `show`, so it warms here.
     This is also the whole of "an entry preloads its ancestors and descendants
     on page load": they are exactly what is drawn. */
  const p = pane();
  if (p && !p.hidden) warm(p);

  /* `edition.js` hands the click on an entity link over rather than reaching in,
     so this file owns the pane and that one owns the stack. */
  window.MAP = {show};
})();
