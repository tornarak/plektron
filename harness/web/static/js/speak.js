const SPEAK_BASE = STATE.base;
document.addEventListener('click', ev => {
  const b = ev.target.closest('button.speak');
  if (!b) return;
  ev.preventDefault();
  const a = new Audio(SPEAK_BASE + '/tts/' + encodeURIComponent(b.dataset.ipa));
  a.play().catch(() => {
    b.disabled = true;
    b.title = 'no audio — espeak-ng is not installed on the host';
  });
});
