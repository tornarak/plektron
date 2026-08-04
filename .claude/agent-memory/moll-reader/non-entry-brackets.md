---
name: non-entry-brackets
description: Not every numbered bracket that isn't a digit-and-dash quire mark is a real entry either -- an all-caps two-token fragment with no gloss is also not a headword
metadata:
  type: project
---

On moll-036 (folio 35), the tool numbered a bracket (3, between real entries 2
and 4, mid-column, not at the foot) whose ink reads only "ГЫТ ТЫ" -- two
all-caps tokens, no gloss line, no lowercase bold headword. Every genuine
headword on this book's pages is set in lowercase bold; nothing else on the
page is rendered in full caps. Read at 2x from the original raster (not the
inverted marked crop) the ink is unambiguous -- it really does say "ГЫТ ТЫ" --
but it still is not a dictionary entry: no gloss follows it, and the running
head above the page already abbreviates the first/last headwords as "гыр" /
"гыт", so this may be some kind of duplicated stem-block header. Whatever it
is, it doesn't have the shape of an entry, so it got no row.

Separately, the same page also carried an ordinary foot-of-column quire mark
(bracket 20, "3*"/"З*", no Cyrillic) -- see [[quire-marks]]. Both were dropped
from the same page, so the total came out 41 rows against a 43-entry
prediction, a 2-row gap explained entirely by these two non-entries.

**Why:** the skill doc's "quire mark got a number" case is specifically
digits + dash. This was a different shape (all-caps Cyrillic, two tokens,
zero digits) that still failed the same underlying test -- "does this bracket
actually contain a flush-left bold headword with a gloss?" -- and had to be
caught by looking at the ink and the entry's internal structure, not by
pattern-matching the quire-mark example literally.

**How to apply:** don't restrict the "check what each bracket contains" rule
to the quire-mark's specific digit-dash shape. Any bracket lacking a lowercase
bold headword + gloss is suspect, whatever its surface form -- all caps, no
gloss, or any other outlier relative to the rest of the page's entries.
