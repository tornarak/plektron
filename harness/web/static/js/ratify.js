const B = STATE.base;

// Delegated, like the speaker button, so it works on a card the stack injected
// as well as on a page of its own. It was an inline `onclick` with the id
// interpolated into an attribute — which meant the id had to survive being
// written into a quoted JS string inside an HTML attribute, and nothing checked
// that it did.
document.addEventListener('click', async ev => {
  const b = ev.target.closest('button.ratify');
  if (!b) return;
  ev.preventDefault();
  const r = await fetch(B + '/ratify', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id: b.dataset.id})});
  // Status first, `lines.js:316`'s form and for its reason. `_ratify` *returns*
  // `{"error": …}` for a refusal, which this read fine; anything that raises
  // inside it answers with a page, and parsing that threw a parse error over
  // the top of the real one — so the button did nothing and said nothing.
  if (!r.ok) {
    let why = r.statusText;
    try { why = (await r.json()).error || why; } catch (e) { /* not JSON */ }
    alert(why);
    return;
  }
  const j = await r.json();
  if (j.error) { alert(j.error); return; }
  /* **Say what it did before reloading.** Ratifying is also what applies the
     entry's links to every collated page, and a silent reload left "it linked
     nothing" looking exactly like "it did not run". Nothing is the ordinary
     answer, too: the corpus holds one collated page and every other mention is
     in `mz/tei/`, which `tei generate` links on its next run. */
  /* Two numbers, because "linked: 0" alone was accurate and useless: `relink`
     runs over committed `tei/`, which is one page, so an entry that page does
     not print links nothing however often the book prints it. The drafts are
     where a reader with `--drafts` is actually reading, and they are counted
     separately because they were *regenerated* rather than relinked. */
  const n = (j.linked || []).length, d = (j.drafts || []).length;
  b.disabled = true;
  b.textContent = [
    n ? `ratified — ${n} link(s) in ${(j.pages || []).join(', ')}`
      : 'ratified — no collated page prints its forms',
    d ? `${d} draft page(s) regenerated` : '',
  ].filter(Boolean).join(' · ');
  setTimeout(() => location.reload(), d || n ? 2600 : 1600);
});
