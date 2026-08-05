---
name: asterisk-before-numeral
description: when a headword carries both a bold asterisk and a homonym numeral, the asterisk can print before the numeral — key the printed order, don't move the numeral to the end
metadata:
  type: project
---

moll-060, entry 38: the book prints `кэвкэв * II пече́нье, гале́ты; см. кавкав *`
— the bold asterisk sits *between* the base word and the roman numeral, not
after both. The spec's homonym-numeral rule ("the numeral, spaced, at the end
of the headword") describes the ordinary case where nothing else is bold
between the word and the numeral; it is not license to reorder what is
actually printed when an asterisk is also there.

**Why:** an asterisk set in bold with the headword stays with it per the
punctuation rule, and the numeral rule is about *not dropping* the numeral,
not about a canonical position. Moving the asterisk to keep "numeral always
last" would silently edit the page.

**How to apply:** key exactly what prints, left to right —
`headword * II`, not `headword II *` — when both occur. If the order is ever
ambiguous at print scale, zoom to confirm before choosing an order rather than
defaulting to "numeral last."
