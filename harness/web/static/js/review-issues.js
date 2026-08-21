// The distributed page's half. `review-kbd.js` loads first and owns the palette,
// the kbd mode, `insert`, `grow` and the type controls.
//
// What is different here, and why: every field on this page belongs to a
// different file, so there is no "current page" to save against and no Done to
// advance. There is one button, it posts every field at once, and the server
// refuses anything short of the whole list.
//
// **The required field is the ruling, not the reading.** The text arrives
// pre-filled and most flagged lines will not need it changed — a flag is a
// question, and "looked, it is fine" answers it. So the completeness rule is
// about notes, and the two quick buttons are the two answers that recur.
//
// **`B` is `review-kbd.js`'s and is not re-declared here.** These are classic
// scripts sharing one global scope, so a second `const B` is a SyntaxError that
// kills this entire file before its first statement — and the symptom is not an
// obviously broken page: the markup renders, every `data-text` is present and
// correct, and not one box gets filled, which reads as a server-side bug and
// sends you looking in the wrong half.

const boxes = () => [...document.querySelectorAll('textarea[data-line]')];
const ruleFor = f => document.querySelector(`textarea[data-ruling='${CSS.escape(f)}']`);

// `data-prior` is the text the server sent for this field. It is NOT the field's
// value — that is `data-text`, assigned below — and the difference is the guard:
// a browser that restores textareas by position after a crash moves `value` and
// leaves the attributes where the server rendered them, so a refill shows up as a
// prior that no longer matches the box beside it. Sent verbatim; the server
// compares against the store and refuses on a mismatch rather than writing.
function collect(){
  return boxes().map(t=>{
    const r=ruleFor(t.dataset.ref+':'+t.dataset.line);
    return {ref:t.dataset.ref, index:parseInt(t.dataset.line,10),
            text:t.value, prior:t.dataset.prior, note:r?r.value:''};
  });
}

function status(){
  const all=collect();
  const unruled=all.filter(e=>!e.note.trim()).length;
  const changed=all.filter(e=>e.text!==e.prior).length;
  for(const t of boxes()){
    const r=ruleFor(t.dataset.ref+':'+t.dataset.line);
    t.closest('.iss').classList.toggle('unruled', !(r && r.value.trim()));
    t.classList.toggle('edited', t.value!==t.dataset.prior);
  }
  st.className = unruled ? '' : 'ok';
  st.textContent = unruled
    ? unruled+' of '+all.length+' still unruled'
    : all.length+' ruled · '+changed+' text change'+(changed===1?'':'s');
  return unruled;
}

let saving=false;
async function save(){
  if(saving) return;
  // Checked here as well as on the server, because an unruled line is something
  // the reviewer can see and fix in place — round-tripping it to be told so is
  // worse than scrolling them to it. The server still refuses: this is
  // convenience, not the guard.
  if(status()>0){
    const first=document.querySelector('.iss.unruled');
    if(first){first.scrollIntoView({block:'center'});
      const r=first.querySelector('textarea[data-ruling]'); if(r) r.focus();}
    st.className='err';
    st.textContent='every flagged line needs a ruling — nothing sent';
    return;
  }
  saving=true; sv.disabled=true; st.className=''; st.textContent='saving…';
  try{
    const r=await fetch(B+'/issues/save',{method:'POST',
      headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},
      body:JSON.stringify({edits:collect()})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok){
      // The refusals are the point of this page, so they are shown in full and
      // left on screen. Nothing was written when one of these arrives.
      st.className='err';
      st.textContent=(j.detail||('save refused ('+r.status+')'));
      return;
    }
    // Adopt the new priors, so a second save in the same session is checked
    // against what is now on disk rather than against what was there at load.
    for(const t of boxes()){t.dataset.prior=t.value; t.classList.remove('edited');}
    const n=(j.saved||[]).reduce((a,s)=>a+s.changed,0);
    st.className='ok';
    st.textContent='saved '+(j.saved||[]).length+' page'
      +((j.saved||[]).length===1?'':'s')+' · '+n+' line'+(n===1?'':'s')+' changed';
  }catch(e){
    st.className='err'; st.textContent='save failed: '+e;
  }finally{
    saving=false; sv.disabled=false;
  }
}

for(const t of document.querySelectorAll('textarea[data-line],textarea[data-ruling]')){
  // Assigned by script rather than written as element content, for the reason
  // the single-ref page does it: `autocomplete=off` asks the browser not to
  // restore a value, and this assignment is what guarantees it.
  t.value=t.dataset.text||'';
  grow(t);
  t.addEventListener('input',()=>{grow(t); status();});
}
// A quick verdict fills the box rather than replacing the act of writing one, so
// it can be edited afterwards and reads in the file exactly as a typed note does.
for(const b of document.querySelectorAll('button.qn')){
  b.addEventListener('click',()=>{
    const r=b.closest('.rule').querySelector('textarea[data-ruling]');
    r.value=b.dataset.note; grow(r); status();
  });
}
sv.addEventListener('click',save);
status();

// No ctrl-s. A save here is all-or-nothing across several files, and a reflex
// keystroke is the wrong way to reach an act with that blast radius.
