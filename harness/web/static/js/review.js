// The page-specific half. `review-kbd.js` loads first and owns the palette, the
// kbd mode, `insert`, `grow` and the type controls — everything a second review
// page (the issue list) needs identically. What is left here is what is true only
// of a one-ref adjudication: the line collect, the save, Done, and the tier-1 walk.
const dn=document.getElementById('dn');
// `[data-line]` throughout, never a bare `textarea`: the note boxes are textareas
// too, and an unscoped selector would post them as if they were line readings.
function collect(){const o={};
  for(const t of document.querySelectorAll('textarea[data-line]')){
    const n=document.querySelector(`textarea[data-note='${t.dataset.line}']`);
    o[t.dataset.line]={text:t.value,note:n?n.value:''};}
  return o}
// Live edited-flag, kept in sync with typing rather than only with the last save,
// so a line that was reverted back to its proposed text stops claiming "edited"
// before the next save round-trips. `ef{idx}` is the same span the server rendered.
function refreshEditFlag(t){
  const ef=document.getElementById('ef'+t.dataset.line);
  if(ef) ef.style.display=(t.value!==t.dataset.proposed)?'inline':'none';
}
function rebuildEditJump(){
  const idxs=[...document.querySelectorAll('textarea[data-line]')]
    .filter(t=>t.value!==t.dataset.proposed)
    .map(t=>parseInt(t.dataset.line,10)).sort((a,b)=>a-b);
  document.getElementById('editjump').innerHTML=idxs.length
    ? '<b>Edited lines:</b> '+idxs.map(i=>`<a href='#l${i}'>${i}</a>`).join(' ')
    : '<b>Edited lines:</b> none yet';
}
async function save(){
  st.textContent='saving…';
  try{
    const r=await fetch(B+'/save',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ref:REF,lines:collect()})});
    if(!r.ok) throw new Error(await r.text());
    const j=await r.json();
    dirty=false;
    const editedTxt=j.edited_lines.length?` (lines ${j.edited_lines.join(',')})`:'';
    const changedTxt=j.changed_lines.length?` (lines ${j.changed_lines.join(',')})`:'';
    st.textContent=`saved · ${j.edited}/${j.lines} edited${editedTxt} · `+
                   `${j.changed} changed${changedTxt}`;
    // A save that moved many lines at once is the only visible sign of a bulk
    // overwrite — a browser session-restore looks like ordinary work otherwise.
    if(j.changed>3) st.className='bad';
    rebuildEditJump();
    // Flash exactly the textboxes this save touched — the status line names them
    // too, but the field itself changing color is what actually catches the eye,
    // rather than something you have to go read.
    for(const i of j.changed_lines){
      const box=document.querySelector(`textarea[data-line='${i}']`);
      if(!box) continue;
      box.classList.add('justsaved');
      setTimeout(()=>box.classList.remove('justsaved'),2500);
    }
  }catch(e){ st.textContent='SAVE FAILED: '+e.message; st.className='bad'; }
}
// Finish the session from the page. **Always saves**, and refuses to stop if that
// save fails — the server is the only thing holding the decisions, so stopping on
// a failed save would discard them silently.
//
// Unconditional, not gated on `dirty`, and that distinction is the whole point:
// "I changed nothing" is an adjudication, not an absence of one. It means every
// proposed line was read and accepted, and `save_decisions` stores every line's
// full text for exactly that reason. Gating on `dirty` was the first version of
// this button and it silently did nothing on a page reviewed without edits —
// including one whose ALTO had just gained a recovered line, so `decision.json`
// stayed a line short and `restore` would have refused it forever.
async function done(){
  await save();
  if(st.className==='bad'){
    st.textContent='NOT stopping — save failed, your work is still here';
    return;
  }
  // The server decides what happens next, not the page. It knows which refs are
  // still unadjudicated *on disk*, which is the only account of that fact that
  // survives a reload, a second tab, or a page opened out of order.
  let next=null;
  try{
    const r=await fetch(B+'/done',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ref:REF})});
    if(r.ok) next=(await r.json()).next;
  }catch(e){}
  dirty=false;
  if(next){ location.href=B+'/p/'+next; return; }
  document.body.innerHTML='<div style="font:15px var(--f);padding:2rem">'+
    '<b>Review server stopped.</b><br>Decisions are saved. '+
    'You can close this tab.</div>';
}
// SESSION-RESTORE GUARD. Firefox restores textarea values across a crash-and-reopen,
// and it restores them BY POSITION, so reopening this page after a crash refilled
// 1-073's fields with 1-151's text — then one keystroke made the debounce save all 47
// of them, and the file said 38 lines edited. Nothing in the page or the server could
// tell that from real work: the payload was well-formed and the text was real
// transcription, just of a different page.
//
// So the server-rendered text is authoritative and is assigned here, after any restore
// has happened. `autocomplete=off` alone is advisory; this is not. Values are compared
// before overwriting only to keep `dirty` honest — an assignment is not an edit.
// Deliberately unscoped: the note boxes are restored by position too, and a note
// that silently belonged to another page would be worse than a misplaced reading,
// since a note is read as a human's ruling and nothing checks it against the scan.
for(const t of document.querySelectorAll('textarea')){
  const want=t.dataset.text;
  if(t.value!==want) t.value=want;
  grow(t);
  t.addEventListener('focus',()=>{last=t});
  // An empty note is stored as nothing, so an empty *field* is a control asserting
  // a state the file does not have. Emptied and left, it folds back to the button
  // and the line reads exactly as it would after a reload.
  if(t.dataset.note!==undefined) t.addEventListener('blur',()=>{
    if(t.value.trim()) return;
    t.hidden=true;
    const b=document.querySelector(`button.hnb[data-line='${t.dataset.note}']`);
    if(b) b.hidden=false;});
  t.addEventListener('input',()=>{grow(t);dirty=true;st.className='';
    st.textContent='unsaved…';
    // Only a reading has an edited-flag; a note is never "edited from proposed",
    // there being nothing proposed to differ from.
    if(t.dataset.line){refreshEditFlag(t);rebuildEditJump();}
    clearTimeout(timer);timer=setTimeout(save,1200)});
}
// Opt-in notes: the button hands over to the field, and the blur handler above
// hands back whenever the field is left empty, so the two are one control with
// two faces rather than a door that only opens.
// `:not(.qn)` — the quick verdicts share `.hnb` for its appearance and carry
// their own handler in `review-kbd.js`; without the exclusion both would fire and
// this one would overwrite the verdict with an empty reveal.
for(const b of document.querySelectorAll('button.hnb:not(.qn)')){
  b.addEventListener('click',()=>{
    const t=document.querySelector(`textarea[data-note='${b.dataset.line}']`);
    if(!t) return;
    t.hidden=false; b.hidden=true; grow(t); t.focus(); last=t;});
}
sv.addEventListener('click',save);
dn.addEventListener('click',done);
// Tier-1 traversal. Focuses the field rather than only scrolling: the point of
// arriving at the line is to key it.
const T1=[...document.querySelectorAll('.ln[data-t1]')];
let t1i=-1;
function goT1(d){
  if(!T1.length) return;
  t1i=(t1i+d+T1.length*2)%T1.length;
  const el=T1[t1i];
  el.scrollIntoView({block:'center',behavior:'smooth'});
  const t=el.querySelector('textarea[data-line]'); if(t){t.focus();last=t}
}
document.getElementById('t1n').addEventListener('click',()=>goT1(1));
document.getElementById('t1p').addEventListener('click',()=>goT1(-1));
addEventListener('keydown',e=>{
  if(!e.altKey||e.ctrlKey||e.metaKey) return;
  if(e.key==='j'){e.preventDefault();goT1(1)}
  else if(e.key==='k'){e.preventDefault();goT1(-1)}
});
addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
