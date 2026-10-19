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
    /* `hover.js`'s, so the two things that float beside a link in this text are
       placed by one piece of arithmetic. It is loaded before this file. */
    window.CARDS.place(a, box);
    return true;
  }

  /* A hovered note can be reached, as the preview can and for its reason: it
     holds links. Leaving the marker starts `hover.js`'s grace period, and the
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

  /* Capture, so this runs before `hover.js`'s own `click → hide` and before the
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
