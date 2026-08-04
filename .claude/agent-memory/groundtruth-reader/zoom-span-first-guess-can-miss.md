---
name: zoom-span-first-guess-can-miss
description: A guessed --only LINE@LO-HI percentage span for a small mid-line mark (like a footnote superscript) can miss the mark entirely; check the strip and re-aim once rather than treating it as settled
metadata:
  type: feedback
---

When zooming to confirm a small mark's exact position mid-line (e.g. a footnote
superscript sitting after a comma partway through a body line, as on 2-070 line 15:
"...as I have said before,² the dog..."), a first-guess percentage span based on
eyeballing the numbered-page composite can land past the mark rather than on it —
the composite is downscaled enough that word position doesn't translate precisely
to a line-relative percentage. `ocr zoom --only 15@60-90` caught "its image is
suppo[sed]" and missed the superscript entirely; `15@45-65` caught it.

**Why:** `ocr zoom --only` spans are a percentage of *that line's* width, and the
downscaled numbered.png doesn't give a precise enough visual estimate of where a
short mark sits relative to the line's start.

**How to apply:** if a zoom strip doesn't show the mark you meant to check, don't
call it inconclusive — widen or shift the span and re-zoom once. This is a normal
part of aiming, not a doubt about the mark's existence. Two zoom calls to nail one
footnote marker's position is cheap and expected, not a sign of over-zooming.
