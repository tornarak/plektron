---
name: literal-question-mark-in-headword
description: some headwords (interrogatives) print a literal "?" as part of the word and its plural — do not mistake it for the unresolved-reading marker
metadata:
  type: project
---

On moll-113 (folio 112), entry 12 prints `ръэнут? (мн. ръэнутэт?) что?` — the
headword itself, its bracketed plural, and the gloss all carry a printed `?`.
This is the book's interrogative pronoun ("what?") and the question mark is
part of the typeset word, not a sign that the character underneath is
undecidable.

**Why:** the output contract uses `?` as the unresolved-reading marker in the
same cell, so a literal printed `?` in a headword is a genuine collision — a
reader (or a downstream check) could misread it as "this reader couldn't
resolve a letter here."

**How to apply:** when a headword or its plural ends in a printed `?`, key it
verbatim (it is real ink, confirmed by zooming — the mark is a full glyph, not
a speck) and add a `note` on that row saying the `?` is printed on the page,
not an unresolved marker. Do not strip it, and do not read it as your own
doubt.
