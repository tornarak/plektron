---
name: footnote-marker-catmus-substitutes-vary
description: CATMuS renders a raised footnote-digit marker as whatever ASCII glyph is nearby its shape, not consistently — seen as '!' after a period, not just as a bare plain digit
metadata:
  type: feedback
---

On `1-037` line 4, the printed superscript footnote marker after "Wrangell." came
through the mz/CATMuS text as a bare `!` (i.e. `Wrangell.!`), not as a plain ASCII
digit `1`. The other three markers on the same page (footnote 1's opener, footnote
2's body reference and opener) all came through as ordinary digits. At 4x zoom all
four are the same small raised digit glyph in the print.

**Why:** the recognizer doesn't have one fixed failure mode for this class — a small
raised numeral sitting right after a period can get read as punctuation-shaped noise
(`!`) rather than digitized as a number at all. This is one more entry alongside
`ɪ`→`i`/`I`/`r` and stress-mark→`'`/`’`/`/` in the "CATMuS substitutes some ASCII
character near the mark's rough shape" family — keying_spec.md §2.10's own rule
already covers this (key the actual superscript sort at reference and opener alike,
never trust the machine's rendering), this note is just recording that the
substitute glyph is not predictable, so don't assume "digit" is the only shape a
garbled footnote marker will take in mz text.

**How to apply:** any line ending mid-sentence in a stray `!`, `/`, or single quote
right after a word/period, on a page that otherwise carries footnote markers, is
worth a 4x zoom check for a raised digit before accepting the punctuation at face
value.
