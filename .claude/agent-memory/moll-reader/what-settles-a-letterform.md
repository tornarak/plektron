---
name: what-settles-a-letterform
description: Magnification adds no information the scan does not carry — for each class of doubt, know whether more zoom, a tighter crop, the lexicon, or a `?` is the thing that decides it
metadata:
  type: project
---

**Zooming does not add information; it only removes distraction.** The scan is
bitonal and fixed, so 4× cannot recover a stroke the paper never recorded. What
decides a doubt therefore depends on *why* the letters are ambiguous, and the
four cases this pass has met answer differently. Going to 4× and *feeling*
certain is itself a failure mode — it converts an unresolved letterform into a
confident wrong answer, the one outcome nothing downstream can catch.

| doubt | seen on | what actually decides it |
|---|---|---|
| `ъ` against apostrophe-consonant (`ръ` as `рт'`, `нъ` as `н'`) | moll-059, moll-063 | **4× — this one does resolve** |
| accent fused with a letter (italic `о́` reading as a second `б`) | moll-044 | a **tighter crop at the same scale**, not more magnification |
| italic `о` at a line break reading as `с` (`по-` as `пс-`) | moll-046 | the **lexicon** — one reading is a real Russian word, the other is not |
| `и`/`н`/`т` in a small bold face | moll-042 | **nothing you can do at the raster: key a `?`** |

**The one that resolves at 4×.** The hard sign against the `к'`/`н'` apostrophe
is a difference in structure, not in surviving ink: the apostrophe is a small
raised comma clear of the letter, the hard sign a taller stroke with a foot on
the baseline, part of the letter row. Both directions occur, sometimes on
adjacent entries of the same page (moll-059's `кытчынъёк` beside
`кытчын'авык`), so do not assume consistency between neighbours — the page
prints both. Zoom the entries alone at 4× and compare height and foot.

**The one that resolves at the same scale.** On moll-044 an accented italic `о`
fused with its acute into a `б`-like loop, making `пробо́ину` read as
`проббину`. Cropping the three or four characters out of the *existing* zoom
output settled it; upscaling further did not. When a repeated consonant appears
where an accented vowel would also fit grammatically, isolate rather than
magnify.

**The one the language resolves.** On moll-046 `по-`/`стромка` printed with
enough ink loss on the `о` to read as `пс-` at 2× and at 4× alike. The
ambiguity is in the ink, so no crop settles it — but `постромка` is a standard
harness term corroborated by a gloss about reindeer harness, and `псстромка` is
nothing. Key the real word, note the ambiguity, do not leave a `?` when the
lexicon and the context genuinely decide. The gloss's own Russian is a witness.

**The one that resolves nowhere.** Short entries in a smaller bold face crowd
`и`, `н` and `т`, which differ by one horizontal stroke that thickens into a
crossbar. This note once said moll-042's entry reads `иитъэ` and that 4×
settles it; **both halves were wrong**. It is `ииъэ`. A reader keyed the extra
consonant, an adjudicating model confirmed it *at 4×*, and a human at the
raster found the letter was never there — tesseract had it right and was
dismissed. `CATALOG.md` records the same class across 29 of 40 contradictions
one и/н flip apart, three readers unable to settle it.

So: zoom **once** to establish that the doubt exists, then **key what you see
and mark the row `?`**. Do not magnify again, and do not settle it on which
word looks more plausible — a well-formed wrong word passes every check this
project has. A `?` costs an adjudicator thirty seconds; a confident guess
survives to the end. The witness pass and the collation check are what catch
this class; on moll-042 the entry also tripped an out-of-order warning, which
was the real signal.
