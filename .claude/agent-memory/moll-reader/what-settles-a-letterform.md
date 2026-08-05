---
name: what-settles-a-letterform
description: Magnification adds no information the scan does not carry — for each class of doubt, know whether more zoom, a tighter crop, the lexicon, or a `?` is the thing that decides it
metadata:
  type: project
---

**Zooming does not add information; it only removes distraction.** The scan is
bitonal and fixed, so 4× cannot recover a stroke the paper never recorded. What
decides a doubt therefore depends on *why* the letters are ambiguous, and the
cases this pass has met answer differently. Going to 4× and *feeling*
certain is itself a failure mode — it converts an unresolved letterform into a
confident wrong answer, the one outcome nothing downstream can catch.

| doubt | seen on | what actually decides it |
|---|---|---|
| `ъ` against apostrophe-consonant (`ръ` as `рт'`, `нъ` as `н'`) | moll-059, moll-063 | **4× — this one does resolve** |
| accent fused with a letter (italic `о́` reading as a second `б`) | moll-044 | a **tighter crop at the same scale**, not more magnification |
| a letter with its bowls broken away (`о` as `с`, `в` as `е`) | moll-046, moll-104 | the **lexicon** — one reading is a real Russian word, the other is not |
| two headwords a few rows apart that look identical at 1× | moll-073 | **crop the pair into one frame** and compare them against each other |
| a headword disagreeing with its own `(мн. …)` stem | moll-070 | **the plural — it is a witness, and it is usually right** |
| `и`/`н`/`т` in a small bold face | moll-042 | **nothing you can do at the raster: key a `?`** |

**The one that resolves by comparison.** On moll-073, entries 14 and 17 both
read `к'эютэкичгын` at page scale. Cropped into one frame at 2×, entry 17 has
an extra `у` — `к'эюутэкичгын`, "fawn meat", matching the `к'эюу-` family two
rows above it, against entry 14's `к'эютэкичгын`, "poor-quality meat". Neither
letterform was doubtful on its own; only the pair was. This is not the repeated
entry of [[bracket-faults]], which is the same headword *and* gloss set twice —
so when two headwords within a few rows look alike, crop them together before
keying either. If every character and every gloss word does match, that is the
repeated entry: key it twice, unaltered, and do not merge.

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

**It happened a second time, to the adjudicator.** On moll-088 the reader keyed
`нымлилык'ин` and the OCR store agreed; adjudication zoomed it to 4×, read
`нымлилилык'ин` — one whole `л-и` pair more — and was certain enough to write
the disagreement into the row. A human at the raster confirmed the reader:
`нымлилык'ин`. So the failure mode is not "readers are careless at 1× and
adjudicators are careful at 4×". **A repeating `л-и-л-ы` run does not become
countable by being made larger**, because what is ambiguous is where one stroke
ends and the next begins, and magnifying an ambiguity magnifies both readings
equally. The two-witness rule is what saved the row: the keyed form stood
because two independent sources agreed, and the third opinion — however
confident, however zoomed — was recorded as a doubt rather than applied as a
correction. Do the same. Count strokes if you must, but treat a count you had
to work for as a `?`, not as a finding.

**A third time, and the tally is now the point.** On moll-104 a reader read a
gloss as `выеетривания`, zoomed to 4×, satisfied itself that the third and
fourth characters were both plain `е`, and wrote that into a page note *and* a
row note as a compositor error kept verbatim. It is `выве́тривания` — a `в` with
its bowls broken away. So across `ииъэ`, `нымлилык'ин` and this, **4× has
produced a more confident wrong reading three times and a correction none**, and
each time the right answer was already available from something cheaper: a
second witness, a real word, an acute sitting exactly where Russian puts the
stress. That is not an argument against zooming. It is an argument that
magnification settles only the class it settles — the `ъ`/apostrophe row of the
table above, and nothing else in it — and that "I looked closer and became
sure" is the specific feeling to distrust.

**Beware the shape "an apparent misprint, kept verbatim."** It sounds like
restraint and it is the opposite: it takes an unresolved reading and files it as
adjudicated, in the one place a later reader will treat as settled. Before
writing it, check that the thing you are preserving is a word, and check whether
the accent falls where the real word would take it.

So: zoom **once** to establish that the doubt exists, then **key what you see
and mark the row `?`**. Do not magnify again, and do not settle it on which
word looks more plausible — a well-formed wrong word passes every check this
project has. A `?` costs an adjudicator thirty seconds; a confident guess
survives to the end. The witness pass and the collation check are what catch
this class; on moll-042 the entry also tripped an out-of-order warning, which
was the real signal.

**A fifth case: a headword that disagrees with its own `(мн. …)` stem. The
plural is a witness. Believe it.** On moll-070 a reader keyed entry 37 as
`к'эв (мн. к'эевыт) и́ней`, noticed the plural carried an `е` the headword did
not, and talked itself out of restoring it — then wrote that reasoning here as
a rule saying *don't* restore. The print reads `к'эев`. All three entries were
misread the same way: 37, 38 and 39 are `к'эев`, `к'эевэтык`, `к'эевэтыльын`.

**The corroboration was circular, and that is the transferable part.** The
reader cited entries 38–39 as independent support for the short stem, but it
had keyed 38 and 39 itself, minutes earlier, with the same blind spot. Two of
your own readings are one reading. Neighbouring entries corroborate only when
something other than you produced them — the `(мн. …)` printed *inside* the
entry is such a witness, because the compositor set it, and here it was
pointing at the right answer the whole time.

So: when a headword and its own plural disagree about a letter, that is a
signal to go back to the raster, not a curiosity to explain away. Zoom the
headword and the plural together, and let the ink decide. If it still
disagrees after that, key what you see and mark the row `?` — but the moll-070
case was legible at 2×, and the disagreement was the reader's, not the book's.
