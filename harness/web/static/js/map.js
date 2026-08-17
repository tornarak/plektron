/* The map pane — a selection of places, the tree that frames them, and the
 * highlight that makes the whole thing answer questions.
 *
 * **One map per sitting, and the sitting accumulates.** A map used to be a card
 * like any other: two of them could sit in the stack at once saying different
 * things about where you are, and the next three cards could push both out of
 * sight. There is only ever one *here*, so there is one pane and it stays above
 * the stack. What changed is what a second click means: it used to *replace* the
 * subject, and now it adds one, because the question a reader has after looking
 * up two villages is where they are with respect to each other, and a map that
 * can only hold one place cannot be asked it.
 *
 * **A click on a place is a map act until the map is already showing it.** Only
 * then does it open the card. So the first click puts a place on the map, the
 * second opens its entry — and the entry, which is the expensive thing to read,
 * is never in the way of the cheap thing. An entity the atlas cannot draw is not
 * on the map and never will be, so its click opens the card at once; the server
 * says which is which (`data-drawn`), because only the store knows.
 *
 * **The frame moves without anything being re-drawn.** The server draws into a
 * *sheet* — the widest extent the tree can reach — and hands over the candidate
 * rectangles already in sheet units (`data-frames`). Hiding a node is then
 * choosing one of them and writing it into the `viewBox`: no fetch, no
 * projection out here, and no second copy of the framing rule, which stays in
 * `edition_ui.map_context` where the store is. Adding and dismissing do go back
 * to the server, because they change what is drawn and not only what is seen.
 *
 * **Every path on that map says whose it is** (`geomap.owned`), which is what
 * lets a name anywhere on the page light up its shape: a `contains` row, a node
 * in the tree, an entity in the running text. Nothing about a path's geometry
 * leads back to a record — a drawn member is the nearest descendant *with* a
 * shape, found by descending through those without, and two entities may share
 * one polygon — so the identity has to travel with the path.
 *
 * **What is drawn is what gets prefetched.** The pane is the authority on which
 * records are in play, and it already lists them: after it loads, every
 * `[data-ent]` on it has its card fetched into `hover.js`'s memo.
 */
(function () {
  const B = STATE.base;
  const pane = () => document.getElementById('map-pane');

  /* Per tab, not per page and not for ever. "One map per sitting" is what
     `sessionStorage` means exactly — the selection survives paging through the
     book, which is the whole point of being able to accumulate one, and dies
     with the tab rather than greeting you tomorrow with yesterday's map. Pins
     are `localStorage` for the opposite reason: a pinned card is a deliberate
     act you expect to find again. */
  const KEY = 'edition-map';
  let sel = [], hidden = new Set(), dropped = new Set();
  try {
    const got = JSON.parse(sessionStorage.getItem(KEY) || '{}');
    sel = got.sel || [];
    hidden = new Set(got.hidden || []);
    dropped = new Set(got.dropped || []);
  } catch (e) {}
  const save = () => sessionStorage.setItem(
      KEY, JSON.stringify({sel, hidden: [...hidden], dropped: [...dropped]}));

  const url = () => B + '/map?partial=1'
      + sel.map(r => '&at=' + encodeURIComponent(r)).join('')
      + [...hidden].map(r => '&hide=' + encodeURIComponent(r)).join('')
      + [...dropped].map(r => '&drop=' + encodeURIComponent(r)).join('');

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

  /* --- the frame, chosen out here ---
   *
   * The rule is the server's and this re-runs its answer: the candidates in the
   * order Python tried them, then the box that holds what is selected. That last
   * clause is what "or, if there is none" means — the reader has hidden the one
   * thing that contained them all, or there never was one because the places sit
   * in unrelated trees.
   */
  function reframe() {
    const p = pane();
    const tree = p && p.querySelector('.map-tree');
    const svg = p && p.querySelector('svg.map');
    if (!tree || !svg) return;
    let f;
    try { f = JSON.parse(tree.dataset.frames); } catch (e) { return; }
    let box = (f.order || []).filter(id => !hidden.has(id)).map(id => f.box[id])
                             .find(Boolean);
    if (!box) {
      const rects = Object.entries(f.own || {})
          .filter(([id]) => !hidden.has(id))
          .map(([, v]) => v.split(' ').map(Number));
      if (rects.length) {
        const x0 = Math.min(...rects.map(r => r[0]));
        const y0 = Math.min(...rects.map(r => r[1]));
        const x1 = Math.max(...rects.map(r => r[0] + r[2]));
        const y1 = Math.max(...rects.map(r => r[1] + r[3]));
        box = [x0, y0, x1 - x0, y1 - y0].join(' ');
      }
    }
    /* Nothing left to frame on — every node hidden. The sheet is the honest
       answer: it is what was drawn, so the map shows all of it rather than
       collapsing to a zero-width viewBox. */
    if (!box) box = svg.dataset.sheet;
    svg.setAttribute('viewBox', box);

    /* A pin is sized against the *view*, so it keeps its size on the page
       whatever the frame — and the frame just moved. The constants come off the
       element (`geomap.PIN`) rather than being written down again here; what is
       genuinely out here is the answer to "would this label run off the right
       edge", which is a question about where the right edge is. */
    const [vx, , vw, vh] = box.split(' ').map(Number);
    let pin;
    try { pin = JSON.parse(svg.dataset.pin); } catch (e) { return; }
    const r = Math.max(vw, vh) * pin.r;
    for (const c of svg.querySelectorAll('circle.pin')) c.setAttribute('r', r.toFixed(1));
    for (const t of svg.querySelectorAll('text.pin-label')) {
      const x = Number(t.dataset.x), y = Number(t.dataset.y);
      const flip = x > vx + vw * pin.flip;
      t.setAttribute('x', (x + (flip ? -1 : 1) * r * pin.dx).toFixed(1));
      t.setAttribute('y', (y + r * pin.dy).toFixed(1));
      t.setAttribute('text-anchor', flip ? 'end' : 'start');
      t.setAttribute('font-size', (r * pin.font).toFixed(1));
    }

    /* Hiding is "do not paint this", and out here that is a rule rather than a
       re-render. Scoped to the pane's own style element so it is replaced whole
       and never accumulates. The node stays in the tree: hiding you cannot undo
       is dismissing, and that is the other button. */
    let css = document.getElementById('map-hidden');
    if (!css) {
      css = document.createElement('style');
      css.id = 'map-hidden';
      document.head.append(css);
    }
    css.textContent = [...hidden].map(
        id => `svg.map [data-ent="${CSS.escape(id)}"]{display:none}`).join('');
    /* `li.more` is the fold and holds no node of its own, so the lookup has to
       be allowed to come back empty. */
    for (const li of tree.querySelectorAll('li')) {
      const a = li.querySelector('a.node');
      if (a) li.classList.toggle('off', hidden.has(a.dataset.ref));
    }
  }

  /* Which folds the reader has opened, by the node each hangs under. Held here
     rather than persisted: it is where you are in a list, not a decision, and it
     should not outlive the page any more than a scroll position does. What it
     must outlive is a repaint — choosing a place from inside a fold rebuilds the
     tree from the server, where every `<details>` is shut, so picking three
     villages out of one list meant opening it three times. */
  let folds = new Set();

  function keepFolds(p) {
    for (const d of p.querySelectorAll('.map-tree details'))
      if (folds.has(d.dataset.fold)) d.open = true;
  }

  /* Dismissal is "not this one", not a setting — see `_pane.html`. Nothing is
     written down, so `paint` needs no permission to reopen. */
  async function paint() {
    const p = pane();
    if (!p) return false;
    const r = await fetch(url());
    if (!r.ok) return false;
    p.querySelector('.body').innerHTML = await r.text();
    p.hidden = false;
    keepFolds(p);
    warm(p);
    reframe();
    return true;
  }

  /* `toggle` fires after the element has settled, so this records what is open
     rather than what is about to be. Delegated with `true` because it does not
     bubble. */
  document.addEventListener('toggle', ev => {
    const d = ev.target.closest && ev.target.closest('.map-tree details[data-fold]');
    if (!d) return;
    if (d.open) folds.add(d.dataset.fold); else folds.delete(d.dataset.fold);
  }, true);

  const served = () => {
    const p = pane(), el = p && p.querySelector('.drawn');
    return el ? {
      sel: (el.dataset.sel || '').split(/\s+/).filter(Boolean),
      drawn: (el.dataset.drawn || '').split(/\s+/).filter(Boolean),
    } : {sel: [], drawn: []};
  };

  /* **A click on a place toggles it.** On, then off, wherever the name is: in
     the running text, in the tree, or on the shape itself. One gesture with one
     meaning, and no separate control to learn — which is what retired the `×`
     that used to sit on every tree row.

     `'card'` is the caller's cue to open the entry instead, and it now means
     only one thing: the atlas cannot draw this, so there was never a map act to
     perform. Reading a place's entry is the `¶` beside its name in the tree,
     the way the atlas has always spelled it — a separate mark for a separate
     act, rather than a second meaning loaded onto the same click. */
  /* Every id under a tree node: its own children, or everything below it.
     Read off the rendered tree rather than fetched, because the tree the reader
     is looking at is the tree they mean — a folded "12 more" is still a child
     and is still in the DOM, so it comes along. */
  function under(ref, deep) {
    const p = pane();
    const a = p && p.querySelector(`.map-tree a.node[data-ref="${CSS.escape(ref)}"]`);
    const ul = a && a.closest('li').querySelector(':scope > ul');
    if (!ul) return [];
    const sel = deep ? 'a.node[data-ref]'
                     : ':scope > li > a.node[data-ref], '
                       + ':scope > li.more > details > ul > li > a.node[data-ref]';
    return [...ul.querySelectorAll(sel)].map(n => n.dataset.ref);
  }

  /* Several at once, painted once. **The clicked node decides the direction for
     all of them** — if it is on the map the whole subtree comes off, otherwise
     the whole subtree goes on — because a per-node toggle over a mixed subtree
     inverts it, which is never what anybody means by shift-clicking a heading. */
  async function clickMany(refs) {
    if (!pane() || !refs.length) return 'card';
    const off = sel.includes(refs[0]);
    for (const r of refs) {
      if (off) { sel = sel.filter(x => x != r); hidden.delete(r); dropped.add(r); }
      else { if (!sel.includes(r)) sel.push(r); hidden.delete(r); dropped.delete(r); }
    }
    save();
    if (sel.length) await paint(); else { pane().hidden = true; clearHidden(); }
    return 'map';
  }

  /* One entry point for "this node, and what the modifiers say goes with it".
     Shift is the node and its children, shift+ctrl the node and everything under
     it; anything else is the plain single click it always was. */
  function subtreeClick(ev, ref) {
    if (!ev.shiftKey) return click(ref);
    const kin = under(ref, ev.ctrlKey || ev.metaKey);
    return clickMany([ref, ...kin]);
  }

  async function click(ref, opts) {
    /* No pane on this page — an exempt leaf has no apparatus column. There is
       nothing to put a place on, so the entry is the whole of the answer. */
    if (!pane()) return 'card';
    /* `toggle: false` is the running prose's — see `edition.js`. A name already
       on the map is not asking to come off; it is asking for its entry. */
    if (sel.includes(ref) && opts && opts.toggle === false) return 'card';
    if (sel.includes(ref)) {
      sel = sel.filter(r => r != ref);
      /* Or its id would sit in `hidden` for ever, and the set is what every
         later frame is filtered against — a place put back on the map later
         would arrive unpainted, with the reason two interactions ago. */
      hidden.delete(ref);
      /* **Dismissal is recorded, because dropping out of `sel` is not a
         signal.** A `geo:` member joins the selection server-side by rule, so
         the next request would put it straight back: leaving it out of `at`
         says "not yet added", which is what the rule acts on. Saying `drop`
         is how a click outranks a rule. Harmless for everything else — an id
         nothing brings along is one nothing re-adds. */
      dropped.add(ref);
      save();
      if (sel.length) await paint(); else { pane().hidden = true; clearHidden(); }
      return 'map';
    }
    sel.push(ref);
    hidden.delete(ref);
    dropped.delete(ref);
    save();
    await paint();
    if (served().drawn.includes(ref)) return 'map';
    /* **An entity the atlas cannot draw leaves the pane alone.** Chuvan, Kerek,
       Siberian Yupik and Tundra Yukaghir have no shape, no point and no located
       descendant; swapping a map you were reading for a sentence about an
       absence loses more than it says, and the card's own `_props` rows say it
       anyway. */
    sel.pop();
    save();
    if (sel.length) await paint(); else pane().hidden = true;
    return 'card';
  }

  function clearHidden() {
    hidden.clear();
    dropped.clear();
    folds = new Set();
    save();
    const css = document.getElementById('map-hidden');
    if (css) css.textContent = '';
  }

  document.addEventListener('click', ev => {
    const p = pane();
    if (p && ev.target.closest('#map-pane .dismiss')) {
      /* The × is "clear the map", which is what dismissing one pane holding one
         subject always was. The selection goes with it — a hidden pane still
         holding six places would come back on the next click as a surprise. */
      sel = [];
      clearHidden();
      save();
      p.hidden = true;
      return;
    }
    const hide = ev.target.closest('.map-tree button.hide');
    if (hide) {
      const id = hide.dataset.ref;
      if (hidden.has(id)) hidden.delete(id); else hidden.add(id);
      save();
      hide.textContent = hidden.has(id) ? '◌' : '●';
      reframe();
      return;
    }
    /* The entry, which is now the only thing that opens a card from the tree —
       a click on the *name* is a map act. On a page with a stack it goes there;
       on the atlas, which has none, the anchor's own href is right and nothing
       needs preventing. */
    const doc = ev.target.closest('.map-tree a.entry[data-ref]');
    if (doc && window.EDITION) {
      ev.preventDefault();
      window.EDITION.openEntity(doc.dataset.ref);
      return;
    }
    if (doc) return;
    /* `a.mapref` is "put this one on the map", and it means that on every page:
       in the stack, where `edition.js` would otherwise have opened a card, and on
       an entity's own page, where the anchor would otherwise navigate away to a
       map with none of the entry beside it. */
    const m = ev.target.closest('a.mapref[data-ref]');
    if (m) { ev.preventDefault(); subtreeClick(ev, m.dataset.ref); return; }
    /* The tree's own names, and the shapes themselves. A click on a member
       polygon promotes it to a subject, which is how a reader walks *down* into
       a map they are already looking at. `window.EDITION` is the reading view's
       stack; without it — the atlas has no stack — the anchor's own href is the
       right fallback, so the navigation is simply not prevented. */
    const n = ev.target.closest('.map-tree a.node[data-ref], svg.map [data-ent]');
    if (n) {
      const ref = n.dataset.ref || n.dataset.ent;
      if (!ref) return;
      ev.preventDefault();
      const href = n.href || (B + '/entity/' + encodeURIComponent(ref));
      /* **Shift takes the children with it, shift+ctrl the whole subtree.** A
         node in this tree is usually a container — a district, a river, a
         language area — and putting its dozen villages on the map one at a time
         was the commonest thing anybody did here. The plain click is unchanged,
         so the shortcut costs the reader who does not know it nothing. */
      subtreeClick(ev, ref).then(what => {
        if (what != 'card') return;
        if (window.EDITION) window.EDITION.openEntity(ref);
        else window.location = href;
      });
    }
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

  /* Any anchor naming an entity, not `a.ent` alone: the tree's node links are
     `a.node`, and they are the thing a pointer is actually on there. */
  document.addEventListener('mouseover', ev => {
    const a = ev.target.closest('a[data-ref]');
    light(a && !a.closest('.card.preview') ? a.dataset.ref : '');
  });

  /* **The page's own subject joins the sitting's map; it does not replace it.**
     Arriving at an entity's page, or at `/atlas?at=`, is the same act as
     clicking the name would have been, so it adds. If the stored selection is
     already exactly what the server drew there is nothing to do and no request
     to make — which is the ordinary case, and why paging through the book with a
     map open costs nothing. */
  const p = pane();
  if (p) {
    const here = served();
    /* **What the reader dropped does not come back on the next page.** The
       pane the server put in this page was rendered without the sitting's
       `drop` — it cannot read `sessionStorage` — so a village taken off the
       map would arrive in `data-sel` again and be adopted straight back. The
       filter is what makes the dismissal outlive a page turn; the comparison
       below then differs from `here.sel` and repaints without it. */
    const want = [...new Set([...sel, ...here.sel.filter(r => !dropped.has(r))])];
    if (want.length && (want.length != here.sel.length
                        || want.some((r, i) => r != here.sel[i]))) {
      sel = want;
      save();
      paint();
    } else {
      sel = want;
      save();
      if (!p.hidden) { warm(p); reframe(); }
    }
  }

  /* `edition.js` hands the click on an entity link over rather than reaching in,
     so this file owns the pane and that one owns the stack. */
  window.MAP = {click, paint};
})();
