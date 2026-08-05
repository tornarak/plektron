---
name: printed-text-no-line-covers
description: where the folio hides when the segmenter misses it, and the one rule that governs every case — a reading with nowhere legitimate to go is a finding, not a placement problem
metadata:
  type: feedback
---

Three arrangements, all seen, all on running-title rows:

1. **The folio has its own sliver line** (`1-035`): a ~19px box beside the title,
   predicted text empty, easy to dismiss as the printed divider rule. Key the folio
   into *that* index.
2. **The zone holds one line and the folio is in no box at all** (`1-037`): its ink
   sits 500px right of the title's box, inside nothing.
3. **A human has already drawn the box** (`1-039`): a correction line arrives with
   empty `CONTENT`, waiting to be keyed like any other line.

**The rule that decides all three: nothing you key may describe ink outside the
line you are keying.** Ground truth is a correspondence between a box and the text
in it, and `restore` writes a line's `text` into the `TextLine` with that index. So
case 2 has no legitimate home: report it, key nothing, stop. A human gives the band
a box in `harness ocr edit` — not your surface — and it then arrives as an ordinary
line.

**This note exists because the advice used to say the opposite.** An earlier version
told readers to key the folio "into whichever line's widened crop shows it", and
`1-037`'s reader followed it exactly, producing a proposal where a 626px box claimed
a number 500px outside it. Text right, geometry right, only the pairing false — the
one defect no text-level check can see, because nothing disagrees with anything.

**How to apply:** the whole-page composite you already opened for orientation shows
the folio in the ordinary case, and costs nothing. A contact sheet of that line is
the fallback — crops run well past the box, so a strangled folio comes back whole
and there is no flag to reach for. Beyond that, `ocr gaps` reports the band with
measured geometry — quote it if it is there, and say `gaps` was silent if it is not.

Distrust digits recovered from a crop of a near-empty box: that is exactly where a
rule, a speck or a bleed reads as type. `1-035`'s note once claimed a folio of
`115` in a run whose neighbours read 12–16.
