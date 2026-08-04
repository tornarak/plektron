---
name: margins-zoom-percent-mapping-is-loose
description: --only LINE@LO-HI percentages don't map cleanly to a margins-widened crop, so a folio/apparatus mark can take several re-aims to land on; stop repeating the same zoom level once one clear read is in hand
metadata:
  type: feedback
---

When a line's own ALTO box is tiny (e.g. a folio-slot TextLine with an empty
`String` and width ~20px, as on `1-033` line 1), `ocr zoom --only N@LO-HI
--margins` widens the crop to the full PrintSpace, and the LO-HI percentage is
of *that* widened width, not the line's own narrow box. A percentage guessed
from the numbered-page composite (as for a normal mid-line mark) is even
looser here than usual, and it's easy to spend several calls at both 3x and 4x
re-aiming at the same two glyphs without learning anything new after the
first clear one.

**Why:** the composite thumbnail gives no real sense of where a mark sits
relative to the *margin-widened* crop's width, since that width isn't the
line's own and isn't obviously derivable by eye.

**How to apply:** for an apparatus mark in a near-empty line box, get one
`--margins` zoom at a modest zoom (2x-3x) across a generous span first, read
whatever comes back carefully, and treat that as the answer — don't re-zoom
at a higher multiplier chasing more certainty about the same pixels. If the
first pass is genuinely ambiguous (e.g. a visible gap between two digits with
no ink at all), that ambiguity is the finding; write it up and flag it, don't
keep reshooting.
