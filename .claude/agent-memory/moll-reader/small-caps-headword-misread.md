---
name: small-caps-headword-misread
description: short entries in a smaller bold face crowd и/н/т/ъ together; 4x does NOT settle them, so key a `?` and let the witness pass decide
metadata:
  type: project
---

On moll-042, a run of one-line entries near the foot of the left column
(entries 21-24) is set in a visibly smaller bold face than the rest of the page.
Short words there lose the letter separation that makes 2x adequate elsewhere,
and `и`, `н` and `т` differ by one horizontal stroke that thickens into a
crossbar when the face is bold.

**This note previously said the run's last entry reads `иитъэ` and that 4x
settles it. Both halves were wrong.** The entry is `ииъэ` — four glyphs, no `t`.
A reader keyed `иитъэ`, an adjudicating model then confirmed it *at 4x*, and a
human reading the raster found the consonant was never there. tesseract had it
right the whole time and was dismissed.

**Why:** magnification cannot add information the bitonal scan does not carry.
`CATALOG.md`'s register records the same class in the medial-stem appendix — 29
of 40 contradictions one и/н flip apart, three readers unable to settle it, "at
4x the letterform genuinely does not decide." Going to 4x and *feeling* certain
is the failure mode, not the remedy: it converts an unresolved letterform into a
confident wrong answer, which is the one outcome nothing downstream can catch.

**How to apply:** when a short headword sits in a noticeably smaller bold face
and the doubt is between `и`, `н` and `т`, zoom once to see *that* the doubt
exists, then **key what you see and mark the row `?`**. Do not resolve it by
magnifying again, and do not settle it on which word looks more plausible — a
well-formed wrong word passes every check this project has. A `?` costs an
adjudicator thirty seconds; a confident guess survives to the end. The witness
pass and the collation check are what actually catch this class: here the entry
also tripped an out-of-order warning, which was the real signal.

See [[hyphen-line-wrap]] for the other case where the page's typography, not the
language, is what makes a headword ambiguous.
