// The zones work-list's behaviour. `LIST` carries the mount prefix and the
// ref to go back to — this file is a cached static asset served from one
// place, so neither can be baked into it.
const B = LIST.base;
  '#filters .chip[data-state], #filters .chip[data-ink], #filters .chip[data-label]')];
const on = new Set();

// Any-of, not all-of: the question a filter answers here is "which pages have a
// block quote", not "which have every type I clicked". Selecting two widens the
// set, which is what the chips look like they do.
function apply() {
  let shown = 0;
  for (const tr of rows) {
    const labels = new Set((tr.dataset.labels || '').split(' ').filter(Boolean));
    const hit = !on.size || [...on].some(k =>
      k.startsWith('state:') ? tr.dataset.state === k.slice(6) :
      k.startsWith('ink:') ? tr.dataset.ink === k.slice(4) : labels.has(k));
    tr.style.display = hit ? '' : 'none';
    if (hit) shown++;
  }
  document.getElementById('shown').textContent =
    on.size ? ` · showing ${shown} of ${rows.length}` : '';
}
for (const c of chips) {
  const key = c.dataset.state ? 'state:' + c.dataset.state
            : c.dataset.ink ? 'ink:' + c.dataset.ink : c.dataset.label;
  c.addEventListener('click', () => {
    on.has(key) ? on.delete(key) : on.add(key);
    c.classList.toggle('on', on.has(key));
    apply();
  });
}
// ---- selection, and the segmenter over it
//
// Shift-click extends from the last box touched, over the rows *as filtered* — so a
// range means what it looks like on screen rather than what the unfiltered table
// would have given. `anchor` is the last plain click; shift without one behaves as a
// plain click, which is what every list in every file manager does.
const boxes = () => [...document.querySelectorAll("tbody tr:not([hidden]) td.pick input")];
let anchor = null;
document.querySelector('tbody').addEventListener('click', e => {
  const box = e.target.closest("td.pick input");
  if (!box) return;
  const all = boxes();
  if (e.shiftKey && anchor && all.includes(anchor)) {
    const [a, b] = [all.indexOf(anchor), all.indexOf(box)].sort((x, y) => x - y);
    for (let i = a; i <= b; i++) all[i].checked = box.checked;
  }
  anchor = box;
  countPicked();
});
const pickall = document.getElementById('pickall');
if (pickall) pickall.addEventListener('change', () => {
  boxes().forEach(b => { b.checked = pickall.checked; });
  anchor = null; countPicked();
});
const segrun = document.getElementById('segrun');
function picked() { return boxes().filter(b => b.checked); }
function countPicked() {
  const n = picked().length;
  if (segrun) segrun.textContent = n ? `segment ${n} selected` : 'segment selected';
}

// Sequential, and for the same reason as the ink pass below: this is GPU work in
// the process serving the editor. The model is loaded once server-side and stays
// resident, which is what makes a bulk run worth doing at all — paying the ~5 s load
// per page is the friction this replaces.
if (segrun) segrun.addEventListener('click', async () => {
  if (segrun.dataset.busy) return;
  const todo = picked();
  if (!todo.length) { segrun.textContent = 'nothing selected'; return; }
  // Asks once, before any of it. A whole-book run is a quarter of an hour of GPU
  // and 832 files, and the count is the only thing that distinguishes it from the
  // three-page run this button was built for.
  const force = !!(document.getElementById('forcebox') || {}).checked;
  const over = todo.filter(b => b.closest('tr').dataset.mz === 'y').length;
  if (todo.length > 20 && !confirm(
      `Segment ${todo.length} pages?\n\n`
      + (force
         ? `${over} of them already have a prediction and it will be replaced.\n\n`
         : over ? `${over} already have one and will be skipped.\n\n` : '')
      + `Writes mz/zones/. gt/zones/ is untouched. The tab has to stay open.`)) {
    segrun.textContent = 'not run'; return;
  }
  segrun.dataset.busy = '1'; segrun.classList.add('on');
  let done = 0, failed = 0, skipped = 0;
  for (const box of todo) {
    try {
      const r = await (await fetch(B+'/predict', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ref: box.dataset.ref, force})})).json();
      if (r.error) throw new Error(r.error);
      const row = box.closest('tr');
      // The server decides what to skip, so the reason comes back rather than being
      // re-derived here — a client that decided for itself would be a second copy of
      // the rule, and the CLI sweep uses the first one.
      if (r.skipped) {
        skipped++;
        row.title = 'skipped: ' + r.skipped;
        box.checked = false;
      } else {
      row.title = `segmenter: ${r.zones} zones`;
      // The count is in hand, so the column it belongs in is filled now rather than
      // left for a reload. An unkeyed row also stops being `todo` — that state is
      // "nobody and nothing has touched this", and something just has.
      const cell = row.querySelector('td.mz');
      if (cell) { cell.textContent = r.zones; row.dataset.mz = 'y'; }
      if (row.dataset.state === 'todo') {
        row.dataset.state = 'proposed';
        const st = row.children[2];
        if (st) st.innerHTML = "<i class='dot s-proposed'></i>proposed";
      }
      box.checked = false;
      }
    } catch (e) { failed++; box.closest('tr').title = 'segmenter: ' + e.message; }
    segrun.textContent = `segmenting · ${++done}/${todo.length}`
                       + (skipped ? ` · ${skipped} skipped` : '')
                       + (failed ? ` · ${failed} failed` : '');
  }
  segrun.classList.remove('on');
  delete segrun.dataset.busy;
  segrun.textContent = `segmented ${done - failed - skipped}`
                     + (skipped ? ` · ${skipped} skipped` : '')
                     + (failed ? ` · ${failed} failed` : '');
});

// The ink pass, on demand and one page at a time. Sequential rather than parallel:
// it is CPU-bound raster work in the same process that serves the editor, and a
// burst of it would make the next page open slowly. Only the pages whose verdict
// is not on hand are asked — everything else was answered when it was keyed.
const runner = document.getElementById('inkrun');
const prog = document.getElementById('inkprog');
if (runner) runner.addEventListener('click', async () => {
  if (runner.dataset.busy) return;
  runner.dataset.busy = '1';
  runner.classList.add('on');
  const todo = [...document.querySelectorAll("td.ink[data-ink='unknown']")];
  let done = 0;
  for (const td of todo) {
    let r;
    try {
      r = await (await fetch(B+'/ink?ref=' + td.dataset.ref)).json();
    } catch (e) {
      td.textContent = '!'; td.title = String(e); continue;
    }
    td.dataset.ink = r.state;
    td.parentElement.dataset.ink = r.state;
    td.textContent = r.state === 'ink' ? r.bands + (r.bands === 1 ? ' band' : ' bands')
                   : r.state === 'ruled' ? r.ruled + ' ruled'
                   : ({clean: '—', skip: '·'})[r.state] || r.state;
    if (r.stale) td.textContent += ' · stale';
    td.title = r.note || '';
    runner.textContent = `checking ink · ${++done}/${todo.length}`;
    apply();
  }
  const n = document.querySelectorAll("tr[data-ink='ink']").length;
  prog.textContent = `${n} with uncovered ink, 0 unchecked`;
  runner.remove();
});

addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    // Esc clears a filter first, and only leaves the list once it is unfiltered —
    // otherwise the one keystroke both discards the filter and the page.
    if (on.size) { on.clear(); chips.forEach(c => c.classList.remove('on')); apply(); }
    else location = LIST.back;
  }
});
