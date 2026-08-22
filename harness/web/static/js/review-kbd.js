// Every URL here is relative to the mount prefix: the four editors share one
// server, so a bare '/save' would post to whichever tool owned the root — and
// this file is a cached static asset, so the prefix is the server's fact to
// state, not the script's to assume.
const B = REF_BASE;
const st=document.getElementById('st'), sv=document.getElementById('sv');
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
//
// It also survives navigation, remembered per browser like the type controls
// below: Done loads the next page as a fresh document, and a batch is a dozen
// of them, so an override that reset on every load had to be re-pressed once
// per page — which is the same "asked for it once" the shortcut exists to
// honour. Stored as three values because the state is tri, not bi: absent
// means "follow kbdOn", and that is not the same fact as an explicit false.
let palOverride=null;
try{const s=localStorage.getItem('review.pal');
    if(s==='1') palOverride=true; else if(s==='0') palOverride=false;}catch(e){}
const syncPal=()=>document.body.classList.toggle(
  'palopen', palOverride===null?kbdOn:palOverride);
// Nothing else calls this before the first keypress, and the class is JS's
// alone — the server renders no `palopen` — so a restored override needs
// applying here or it would be remembered and never shown.
syncPal();
document.addEventListener('focusin',e=>{
  if(e.target.tagName!=='TEXTAREA') return;
  // **`last` is tracked here because it is this file's variable.** It used to be
  // assigned only in review.js, the per-page editor's script — so on any page
  // that loads review-kbd.js *without* it, `last` stayed null and both consumers
  // below died silently: the keydown handler returns early on `!last`, and a
  // palette click inserts into nothing. That is every keystroke and every button
  // of the virtual keyboard, on a page where the panel still renders and still
  // says `kbd ON`, which is the worst way for it to fail. The issues page has
  // loaded review-issues.js since it existed and was affected the whole time; the
  // caption page inherited it on day one. Owning it here means a third page
  // cannot reintroduce it by shipping a different companion script.
  last=e.target;
  // The panel occupying 16rem when kbd mode is on can cover the very field
  // just focused, if it was near the bottom of the page. scrollIntoView
  // (nearest, not goT1's center) nudges just enough to clear it without
  // recentering on an ordinary tab/click. Scroll-only now — it no longer
  // toggles the panel itself, since that depends only on kbdOn/palOverride.
  if(kbdOn) e.target.scrollIntoView({block:'nearest',behavior:'smooth'});
});
addEventListener('keydown',e=>{
  if(e.altKey&&!e.ctrlKey&&!e.metaKey&&e.key==='p'){
    e.preventDefault();
    const shown=palOverride===null?kbdOn:palOverride;
    palOverride=!shown;
    try{localStorage.setItem('review.pal',palOverride?'1':'0')}catch(e){}
    syncPal();
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

// QUICK VERDICTS. Two rulings recur often enough across a batch to be worth a
// click instead of a sentence — `speck` is what most stray-mark flags resolve to,
// and `fine` is what most of the rest do.
//
// The textarea is found by **proximity**, not by an attribute lookup, and that is
// what lets one handler serve both review pages: the single-ref page keys its
// note by line index, while the issue list has to key by ref *and* line, since
// two pages in one document can share an index. Neither keying is visible from
// here, and neither needs to be.
//
// Firing `input` afterwards rather than updating any counter directly: each page
// already listens for it, and one of them autosaves on it. A quick verdict is an
// edit made by a button, and it should be indistinguishable from a typed one
// everywhere downstream.
for(const b of document.querySelectorAll('button.qn')){
  b.addEventListener('click',()=>{
    const box=b.closest('.hn,.rule');
    const t=box&&box.querySelector('textarea');
    if(!t) return;
    t.value=b.dataset.note;
    t.hidden=false;
    // The plain `+ note` button hands over to the field; a quick verdict does the
    // same handover, so the control does not end up showing both faces at once.
    const plus=box.querySelector('button.hnb:not(.qn)');
    if(plus) plus.hidden=true;
    grow(t); last=t;
    t.dispatchEvent(new Event('input',{bubbles:true}));
  });
}
