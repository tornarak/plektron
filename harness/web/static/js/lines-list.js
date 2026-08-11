const B = LIST.base;

// One row at a time, and only when asked: each is a raster read. The button says
// so rather than the page quietly spending a minute before showing anything.
const note = document.querySelector('#shownum');
document.querySelector('#go').onclick = async () => {
  const rows = [...document.querySelectorAll('tr[data-ref]')];
  let live = 0;
  for (let i = 0; i < rows.length; i++) {
    const tr = rows[i];
    note.textContent = `measuring ${i + 1} / ${rows.length}`;
    try {
      const r = await (await fetch(B + '/row?ref=' + tr.dataset.ref)).json();
      tr.querySelector('[data-live]').textContent = r.live;
      tr.querySelector('[data-ruled]').textContent = r.ruled;
      tr.querySelector('[data-corr]').textContent = r.corrections;
      // The dot carries the state, as it does in the zone editor's list, so a
      // colour means one thing across the pass rather than one thing per tool.
      tr.dataset.state = r.live ? 'live' : 'done';
      tr.querySelector('.dot').className =
        'dot ' + (r.live ? 's-warn' : 's-ok');
      live += r.live ? 1 : 0;
    } catch (e) { note.textContent = String(e); return; }
  }
  note.textContent = `${live} of ${rows.length} still carrying a band`;
};

// Filters hide rows, they never re-order them: the walk's order is the order the
// editor steps through, and a list that disagreed with the arrow keys would be
// worse than no list.
let filter = '';
document.querySelectorAll('.chip[data-filter]').forEach(c => {
  c.onclick = () => {
    filter = (filter === c.dataset.filter) ? '' : c.dataset.filter;
    document.querySelectorAll('.chip[data-filter]').forEach(
      o => o.classList.toggle('on', o.dataset.filter === filter));
    let n = 0;
    document.querySelectorAll('tr[data-ref]').forEach(tr => {
      const show = !filter || tr.dataset.state === filter;
      tr.style.display = show ? '' : 'none';
      n += show ? 1 : 0;
    });
    document.querySelector('#shown').textContent =
      filter ? ` · showing ${n}` : '';
  };
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') location.href = B + '/?ref=' + LIST.back;
});
