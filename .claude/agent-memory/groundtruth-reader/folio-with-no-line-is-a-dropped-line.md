---
name: folio-with-no-line-is-a-dropped-line
description: printed text with no ALTO line to hold it is a dropped line — report it in segmenter_missed and stop; never key it into a neighbouring line's text, however close that line sits
metadata:
  type: feedback
---

On `1-037` the `RunningTitleZone` held exactly one ALTO line — the title,
hpos 1017–1643 — and the folio's ink sits at hpos 2157–2200, some 500 px to its
right, in the same rows and inside no box on the page. The reader recovered it
with `--margins`, found no index to put it in, and appended it to the title
line's `text`: `"BOGORAS, THE CHUKCHEE. 17"`.

**Why that is a defect and not a workaround.** Ground truth is a correspondence
between a box and the text inside it. `restore` writes a line's `text` into the
`String` of the `TextLine` with that index, so this would have asserted that a
626 px box contains a number 500 px outside it. Nothing downstream re-opens that:
the text is right, the geometry is right, and only their pairing is false — which
is the same shape as a dropped line, invisible to every text-level check because
nothing disagrees with anything.

**This note exists because the previous advice said to do it.** An earlier memory
file said to key the folio "into whichever line's widened crop actually shows it",
and the reader followed it exactly. Both notes are corrected now. Treat this as
the standing case: **a reading that has nowhere legitimate to go is a finding, not
a placement problem.**

**How to apply.** When `--margins` (or the whole-page image) shows printed text
that no line index covers:

1. Put it in the proposal's `segmenter_missed` block — what you saw, where, and
   why you think it is type. `harness ocr gaps` reports the band with its measured
   geometry; quote that if it is there.
2. Leave every existing line's `text` describing only its own box.
3. Stop. A human gives the band a box in `harness ocr edit` — a browser editor,
   not on your permitted surface — or rules that it is not a line at all. Once
   that box exists the line arrives through the view like any other, with its own
   index and crop, and keying it is then an ordinary part of the reading pass.

`ocr gaps` could not see this class until the detector was changed to mask line
**boxes** rather than whole image rows (it now reports `1-037` as
`vpos 673, height 36, hpos 2157, width 43, where: column`). So on an older page
the band may be absent from `gaps` output while the ink is plainly there in the
image — report it anyway, and say `gaps` was silent.

Related: [[folio-can-sit-on-own-thin-alto-line]], where a box *does* exist and the
folio is keyed into it normally.
