// Every URL here is relative to the mount prefix: the four editors share one
// server, so a bare '/save' would post to whichever tool owned the root — and
// this file is a cached static asset, so the prefix is the server's fact to
// state, not the script's to assume.
const B = REF_BASE;
const st=document.getElementById('st'), sv=document.getElementById('sv');
const dn=document.getElementById('dn');
const kb=document.getElementById('kb');
let kbdOn=false, last=null;
function setKbd(v){kbdOn=v;kb.textContent='kbd '+(v?'ON':'off');
  kb.className=v?'on':'';document.body.classList.toggle('kbdon',v);syncPal()}
function insert(el,s){
  const a=el.selectionStart,b=el.selectionEnd;
  el.setRangeText(s,a,b,'end');
  el.dispatchEvent(new Event('input',{bubbles:true}));
}
// Click-to-insert targets whichever field was last focused, so the palette works
// without stealing the caret.
document.addEventListener('mousedown',e=>{
  if(e.target.closest('#pal')) e.preventDefault();
});
for(const b of document.querySelectorAll('.pk')){
  b.addEventListener('click',()=>{ if(last) insert(last,b.dataset.ins) });
}
kb.addEventListener('click',()=>setKbd(!kbdOn));
// Retract the glyph grid except while it's actually wanted: kbd mode is on, or
// the reviewer pinned it open (alt-p) to browse without keeping a caret in a
// field. Visibility is a pure function of those two toggles — SOLELY the
// shortcuts (ctrl-space, alt-p) — and never of focus. It used to also require
// a focused textarea, on the theory that plain typing in an ordinary English
// line shouldn't pop the grid; in practice that made the panel jump open the
// instant a field was focused whenever kbd mode was already on, which is the
// opposite of "no keyboard until you asked for it", and no different from a
// docked-vs-undocked distinction if a focus event overrides it either way. So
// focus no longer participates at all: turn kbd mode on and the panel is
// open, everywhere, until you turn it off. #pctl (status/save/hint) is
// unaffected — see the CSS.
//
// palOverride is a tri-state, not a bool ORed with kbdOn: null means "follow
// kbdOn", true/false means alt-p has said otherwise and wins regardless of
// kbdOn. The OR version couldn't represent "kbd mode on, panel hidden" at
// all — kbdOn=true forced the OR to true no matter what alt-p did, which is
// exactly the state a reviewer wants when they know the mode they're in and
// don't need the grid on screen to use it. alt-p flips whatever is currently
// showing, so it always does something visible, and the override sticks
// until alt-p is pressed again — toggling kbd mode itself doesn't clear it.
let palOverride=null;
const syncPal=()=>document.body.classList.toggle(
  'palopen', palOverride===null?kbdOn:palOverride);
document.addEventListener('focusin',e=>{
  // The panel occupying 16rem when kbd mode is on can cover the very field
  // just focused, if it was near the bottom of the page. scrollIntoView
  // (nearest, not goT1's center) nudges just enough to clear it without
  // recentering on an ordinary tab/click. Scroll-only now — it no longer
  // toggles the panel itself, since that depends only on kbdOn/palOverride.
  if(e.target.tagName==='TEXTAREA'&&kbdOn){
    e.target.scrollIntoView({block:'nearest',behavior:'smooth'});
  }
});
addEventListener('keydown',e=>{
  if(e.altKey&&!e.ctrlKey&&!e.metaKey&&e.key==='p'){
    e.preventDefault();
    const shown=palOverride===null?kbdOn:palOverride;
    palOverride=!shown;syncPal();
  }
});
addEventListener('keydown',e=>{
  if(e.ctrlKey&&e.code==='Space'){e.preventDefault();setKbd(!kbdOn);return}
  if(!kbdOn||!last||document.activeElement!==last) return;
  if(e.ctrlKey||e.altKey||e.metaKey) return;
  const g=Object.prototype.hasOwnProperty.call(GL,e.key)?GL[e.key]
        :(Object.prototype.hasOwnProperty.call(MK,e.key)?MK[e.key]:null);
  if(g===null) return;
  e.preventDefault(); insert(last,g);
});
let dirty=false, timer=null;
const grow=t=>{t.style.height='auto';t.style.height=t.scrollHeight+'px'};

// TYPE CONTROLS. The two CSS variables the entry boxes are sized from, moved
// live and remembered per browser. The server flags set the starting values and
// stay the reset target, so `reset` means "back to what this server was started
// with" rather than to a constant compiled in here — otherwise a coordinator who
// passed --font-size would find the button undoing their flag.
const TYPE={fs:{min:11,max:34,unit:'px'},bl:{min:1,max:8,unit:''}};
const typeStart={};
for(const k in TYPE) typeStart[k]=parseFloat(
  getComputedStyle(document.documentElement).getPropertyValue('--'+k));
function typeSet(k,v){
  v=Math.min(TYPE[k].max,Math.max(TYPE[k].min,v));
  document.documentElement.style.setProperty('--'+k,v+TYPE[k].unit);
  const lab=document.getElementById('tv'+k);
  if(lab) lab.textContent=(k==='fs'?v+'px':v+(v===1?' line':' lines'));
  try{localStorage.setItem('review.'+k,v)}catch(e){}
  // Every box was sized against the old metrics, so re-grow them all: a box left
  // at its previous pixel height after a size change is the one thing that would
  // make this look broken.
  for(const t of document.querySelectorAll('textarea')) grow(t);
}
for(const k in TYPE){
  let v=typeStart[k];
  try{const s=localStorage.getItem('review.'+k); if(s!==null) v=parseFloat(s)}catch(e){}
  typeSet(k,v);
}
for(const b of document.querySelectorAll('button.tb[data-var]')){
  b.addEventListener('click',()=>{
    const k=b.dataset.var;
    typeSet(k,parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--'+k))+parseFloat(b.dataset.by));
  });
}
{const r=document.getElementById('treset');
 if(r) r.addEventListener('click',()=>{for(const k in TYPE) typeSet(k,typeStart[k])});}
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
for(const b of document.querySelectorAll('button.hnb')){
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
