---
name: gloss-side-faults
description: The Russian half of the row is the half no check looks at — dropped stress accents and un-joined line-end hyphens both live there, and neither produces any feeling of doubt
metadata:
  type: project
---

Almost everything that checks this pass looks at the headword: the collation
order, the suffix detectors, the OCR witness, the duplicate check. **The gloss
is nearly unwatched**, and it is correct-looking Russian either way, so its two
standing faults give you no internal signal at all.

## Stress accents are a whole-page habit

This book accents nearly every polysyllabic Russian word in a gloss. Folio 62
(moll-063) was read twice by readers blind to each other and **both dropped the
accents across the whole page** — one marked 1 row of 42, the other 0. The page
prints them normally (`шерохова́тость`, `ма́ленькая ча́йка`, `ключи́ца`,
`хру́пкий`). A human restored all 42 from the raster. Both readers had reported
the page clean.

Unlike every other error in this directory, this one produces **no feeling of
doubt**. You read the gloss, you understand the Russian, you key the Russian you
understood, and the accents were never part of what you were attending to.

It is also the one error a second reader does not catch, because a sibling
reader shares the disposition that causes it. **Do not treat "someone else will
notice" as covering this.**

Two things follow:

- **Make the accents their own pass.** When you zoom a batch to check `ъ`/`ь` or
  `-лын`/`-льын`, you are looking at the Chukchi headword. Go back over the same
  crop looking *only* at the Russian, word by word, confirming each polysyllable
  carries its mark. A page where most rows have no accent is a page you have got
  wrong, not a page that lacks them.
- **The Chukchi side is never accented.** The mark belongs to the Russian only —
  including Chukchi forms sitting inside a gloss, in `(мн. …)` or after `см.`,
  which stay bare. `ё` is inherently stressed and takes no acute.

Beware the tail specifically. On folio 60 a reader that ran out of turns kept its
row count and its headwords and quietly lost the accents from about row 30 on;
the page still cleared a page-wide check because its first half carried the
average.

## Line-end hyphens join

On moll-034 three entries split `оберега́ть` / `оберега́ющий` / `оберега́ться`
across a line break — the line ends `обе-` or `обере-` and the next opens
`рега́ть` / `га́ющий` / `га́ться`. These are ordinary typographic hyphens and
must be joined into one word with no hyphen. The trap is that both fragments
look individually well-formed, so keying each column line in isolation leaves
the break in.

**When a gloss line ends in a hyphen, always read the next line's opening
syllable before finalising the cell, and join without the hyphen.** See
[[what-settles-a-letterform]] for the case where the letter at such a break is
itself ambiguous — the two faults compound at exactly the same spot.

## The opposite failure exists too: a phantom accent on a monosyllable

On moll-092, entry 24's gloss reads `за что́-то, во внутрь (чего́-л.)`. At page
scale `внутрь` looked accented — there is a stray mark near it in the
letterpress noise — but `внутрь` has one vowel and takes no stress mark, and a
2× zoom of the entry alone showed no acute over it at all. Having just read
the "accent nearly everywhere" rule, it is easy to overcorrect and add a mark
to a short word that never carried one, which is the mirror image of the
whole-page accent-dropping fault above. Before keying an accent on a
monosyllable, or on a word you are not certain has one, zoom that one word —
do not pattern-match "this book accents everything" onto every gloss token.
