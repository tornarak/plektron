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
  const j = await r.json();
  if (j.error) { alert(j.error); return; }
  location.reload();
});
