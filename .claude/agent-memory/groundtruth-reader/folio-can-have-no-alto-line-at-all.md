---
name: folio-can-have-no-alto-line-at-all
description: a RunningTitleZone can hold only a single ALTO line (the title), with the folio entirely outside every box on the page rather than on its own sliver line — check with --margins on the title line itself
metadata:
  type: feedback
---

On `1-037`, `ocr lines --store mz` reported exactly one line (index 0) in the
RunningTitleZone, containing only "BOGORAS, THE CHUKCHEE." — no second, near-empty
line for the folio at all (contrast [[folio-can-sit-on-own-thin-alto-line]], where
a second sliver line exists but reads empty). The folio "17" was invisible in the
title line's own plain crop and only appeared once `ocr zoom --only 0 --margins`
widened the crop to the full PrintSpace, landing just past the title line's own box
(hpos 1017–1643) with room to spare before the page's right margin.

**Why:** the segmenter doesn't always draw a box (however narrow) around the
folio — sometimes it's simply outside every TextLine polygon on the page, and the
zone's line count is genuinely 1, not 2.

**How to apply:** on any RunningTitleZone with only one reported ALTO line, don't
conclude the folio is absent or unreadable — run `ocr zoom --only <that index>
--margins` before deciding.

**If the folio turns up in the widened crop, it is a dropped line: report it in
`segmenter_missed` and key nothing.** See
[[folio-with-no-line-is-a-dropped-line]].

The first version of this note ended "key it into that same line's text
(space-separated after the title) since there's no other line index to hold it",
and that is what was done on `1-037` — producing a proposal in which the title's
626 px box claims a number 500 px outside it. The premise was also false: `ocr
adopt-gap` makes the missing index from the band's measured geometry, and `ocr
gaps` now reports that band (`vpos 673, height 36, hpos 2157, width 43`) because
the detector masks line boxes rather than whole image rows. It reported nothing
when this page was read, which is why the reader believed it had no option.

Recording the correction rather than quietly editing it: this note was written
from a page whose reading was wrong, and the next reader would otherwise have
found only a confident instruction with no sign it had ever been disputed.
