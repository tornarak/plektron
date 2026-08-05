---
name: gaps-band-can-be-ink-blot-not-dropped-line
description: an `ocr gaps` band with no figures on the page can be a real ink blot/smudge rather than a dropped printed line — read its `exempted` column first, then look at what is under it
metadata:
  type: feedback
---

On `1-035` (a figure-free page, so every `ocr gaps` band is nominally a "genuine
dropped-line candidate" per the survey), the one reported band (vpos 3324, height 22,
hpos 420, width 200) sat immediately below/within a real ink blot smudging the
left edge of the last two footnote lines (indices 42-43). Zooming with `--margins`
at the band's location showed nothing but the tail of the same blot already visible
inside lines 42/43's boxes — no additional printed text, no line the segmenter missed.

**Why:** a `gaps` band is "ink the segmenter's TextLines don't cover," and dense ink
from a smudge/blot satisfies that definition just as well as a genuinely dropped
printed line does. The absence of figure zones on a page rules out *one* false-positive
class (masked figure ink) but not this one.

**How to apply:** **read the band's `exempted` column first.** `ocr gaps` now carries
the zoning pass's ruling: `exempted: true` means a human already ruled this band not
type, and the `note` says why — read it and spend no image. That was not so when this
note was written, which is why this page cost zoom calls it should not have.

If the band is unexempted, zoom into it with `--margins` and look at what is actually
there. If it is continuous with ink already inside a neighbouring line's box (a blot
bleeding past the box edge) rather than a new run of glyphs, it is page damage, not a
missed line. Either way you **report it and never repair it** — creating a line is a
later step and not the reading pass's; it happens in `harness ocr edit`, a browser
editor that is not on your Bash surface, where a human decides between the two.
