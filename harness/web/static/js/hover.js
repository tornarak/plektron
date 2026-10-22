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
 * file: `edition.js` cannot load outside `page.html` because it binds
 * `#scan-btn` and `#reader-btn` unconditionally, and the encyclopedia, the atlas
 * and a card on its own page all want this.
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
  window.CARDS = {get, place, GRACE_MS};

  /* The same three URLs `edition.js` builds, character for character. */
  function urlFor(a) {
    if (a.classList.contains('lex'))
      return B + '/lexicon/' + encodeURIComponent(a.dataset.key) + '?partial=1';
    if (a.classList.contains('mapref'))
      return B + '/map/' + encodeURIComponent(a.dataset.ref) + '?partial=1';
    return B + '/entity/' + encodeURIComponent(a.dataset.ref) + '?partial=1';
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
     `box`, because `notes.js` floats a second thing beside a link in this same
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
    if (!a || a.closest('.map-tree')) return;
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
    /* Not in the map's own tree. Those names sit directly under the map, so a
       preview opens on top of the thing the hover was asking about — and the
       hover already answers it, by lighting the shape. */
    if (!a || a.closest('.map-tree')) { linger(); return; }
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
