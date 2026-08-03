---
name: read-moll-page
description: Read one whole page of Moll & Inenlikej 1957 into a Markdown table of headword/gloss entries under scratch/chukchi/moll-scans/entries/. Use when extracting the Chukchi–Russian dictionary, dispatching parallel readers over moll-scans/marked/, or on /read-moll-page moll-NNN. Carries the page anatomy, the character rules and the output contract. Not a Bogoras corpus pass — nothing it produces may enter gt/ or tei/.
---

# Read one dictionary page (marked page → headword table)

You are one of several readers working the same book in parallel. You read one
image and write one file. You never see another page, and you never need to —
nothing on your page depends on anything on any other except at its top and
bottom edges, and those are handled below.

**The unit is the whole page. The old column crops are gone** — an earlier pass
cut each page in two and named the halves `moll-NNN-L` / `moll-NNN-R`. If you
have seen that convention anywhere, or are asked for a column, it is stale:
there is one image and one output file per page.

You do not check your own work. A separate pass audits every file this skill
produces, against the page layout and against the book's own alphabet. Do not
try to make your output look consistent; try to make it match the paper.

**This skill reads no other document.** The sibling skills in this repo open by
sending you to `keying_spec.md` and `CLAUDE.md`; this one does not, deliberately.
Everything you need is below. Do not go looking for project context, and do not
apply rules you remember from elsewhere in this repo — this is a different book,
in a different script, in a scratch side quest.

## The call

    Read   scratch/chukchi/moll-scans/marked/moll-NNN.png    # your page
    Write  scratch/chukchi/moll-scans/entries/moll-NNN.md    # your output

Same stem, `.md` for `.png`. One file in, one file out. If
`scratch/chukchi/moll-scans/entries/` does not exist, create it.

**This skill covers the dictionary body, folios 9–163 (files `moll-010` …
`moll-164`).** The volume also carries front matter and three appendices, and
they are *not* this job — the row shape differs, there is no Russian to gloss,
and the checks here would fire on every line. The medial-stem appendix (folios
187–194, files `moll-188` … `moll-195`) is already keyed, into
`moll-scans/stems/` under its own three-column contract; that pass and what it
found are written up in `scratch/chukchi/moll-infixes.md`. If you are handed an
appendix page, read that first and do not use the contract below.

## What is on the page

The page is **two columns of a dictionary, separated by a printed vertical
rule**, plus a running head above a horizontal rule.

**Reading order is left column, then right column** — but only within a *band*.
See the next section, which is the one thing about this layout that is not
obvious.

- **Above the horizontal rule** sit the running head (the first and last
  headwords of the page, abbreviated) and the centred page number. Neither is
  an entry. Do not read them, and in particular do not read the running head's
  abbreviations as headwords: they are cut short (`вэт`, `гал`) and are not
  words.
- **A large centred capital** part-way down is a letter-section heading — the
  book starting а, or к', or ю. It spans the gutter, sits in a wide band of
  white, is marked `§`, and is not an entry and has no gloss.
- **A quire mark** — a signature number like `10-561` — sits at the foot of a
  few pages, flush left and set apart from the type above it. It is a
  printer's mark and **not a headword**, however much it looks like one when
  numbered. Nothing detects these: they are left to you deliberately, because
  the alternative is another rule in an already brittle geometric detector,
  and a Cyrillic-free run of digits and a hyphen is exactly the call a reader
  can make and a threshold cannot. Give it no row and mention it in `note:`.

## What is an entry

An entry begins with a **bold headword set flush to the left margin**. Every
line below it that is **indented** continues it. The next flush-left bold word
begins the next entry.

Record entries in the order the page is numbered — which is reading order.

**Reading order is BAND-MAJOR, and this is the one trap in the layout.** A
section heading interrupts *both* columns at the same height, cutting the page
into horizontal bands. Within a band you read the left column down, then the
right column down. Then the next band. So on a page with one heading the order
is: left-above, right-above, `§`, left-below, right-below — **not** the whole
left column and then the whole right.

You do not have to work this out. The entries are numbered on your image in
reading order, 1..N. **Follow the numbers** — but see "when a bracket is not an
entry" below, because they are drawn from the ink and the ink is not always an
entry. They are also what the context block counts and what any later pass will
join on.

**A definition wrapping from the left column into the right is ONE entry,
drawn twice under one number**, the second bracket marked `←`. Give it one row,
with the two halves of its gloss joined. This is why the page replaced the
column crops: that wrap used to fall across two files and had to be joined
afterwards from a marker.

**The page may open in the middle of a definition** carried over from the
*previous page*. That block is tinted pink and marked `c` rather than numbered,
because its headword is on a page you cannot see and must not guess at. Give it
**no row** and say so:

```markdown
<!-- continues: indented text at the top, no headword on this page -->
```

The last entry may likewise break off mid-word at the foot of the right column.
Record what is on your page and nothing else; do not complete it.

### When a bracket is not an entry

The brackets are measured off the ink, so a numbered bracket is a claim that
*something starts here*, not that a headword does. Four ways it has been wrong,
all found by readers and all confirmed:

- **A quire mark got a number.** `2—561` at the foot of a column, all digits and
  a dash, no Cyrillic. No row; say so in `note:`. (See the page anatomy above.)
- **One bracket held two complete entries** — two flush-left bold headwords,
  each with its own gloss, no `←` marker between them. Two rows.
- **A bracket was a cut-off sense marker.** A page ended after setting a bare
  `2)` for the previous entry's second sense, with no gloss text following. That
  belongs in the previous entry's gloss, not in a row of its own.
- **An entry opened with no number at all**, at the foot of a column, and was
  cut off mid-word.

**A row count that matches the prediction does not mean the brackets were
right.** On one page a quire mark numbered as an entry and a two-entry bracket
cancelled *exactly*, so 41 brackets yielded 41 rows and both faults were
invisible in the total. That reader caught them by looking; nothing else would
have. So check what each bracket contains rather than checking the sum — and
when you find one of these, write `disagrees:` even though your count agrees.
That case is explicitly not a stale comment and is not reported as one.

## What you are told before you start

You are given a context block for your page — its folio, which initials the
folio can carry, how many entries it holds, whether it opens mid-definition,
which definitions wrap across the gutter, and where any section headings fall.
It is produced by

    uv run python scratch/chukchi/entry_bounds.py context moll-042

Your image comes from **`moll-scans/marked/`**, which is the page with the
measurement drawn on it: alternating entries **inverted** (white on black),
each numbered in a white strip inserted before its own column, an opening
continuation in pink and marked `c`, a section heading in amber and marked `§`,
and the second half of a wrapped definition repeating its number with `←`. The
numbering matches the context block and `moll-bounds.md`.

The right column is shifted right to make room for its numbers, so the marked
page is a little wider than the scan. That is a transcriber's aid, not a
facsimile; `zoom` crops from the original raster.

Two things follow. **Read the inverted bands exactly as carefully as the
upright ones** — inversion changes no letterform, and an entry is not less
important for being one of the black ones. And **the bands are the tool's
opinion of where the entries divide, not the page's.** If a boundary falls in
the wrong place — a headword swallowed into the band above it, or one entry
drawn as two — record what the page shows and write it up in `disagrees:`.
Still echo the *original* filename in `source:`, not the marked one.

**It is measured off the ink and has read no character.** That is what makes it
worth having: it cannot have made the same mistake you are about to make, so
where it and you agree, two unrelated methods agree. Use it as a prior — it
tells you how many headwords to expect and warns you about a heading you might
otherwise read as an entry.

**It is a prediction, not an instruction, and the page outranks it.** If you
count 22 entries where it says 23, do not go looking for a 23rd until you are
convinced, and do not merge two rows to reach 23. Record what the page shows
and write down the disagreement:

```markdown
<!-- disagrees: 22 not 23 — the block at y1400 is indented under the entry
     above it, not a headword; it is set in the same bold but sits at the
     continuation margin -->
```

A `disagrees:` comment demotes the mismatch from a warning to a flagged line
carrying your reason, which is then read by a human. Its cost is the reason it
exists: **a reader that silently conformed to the expected count and a reader
that read the page are indistinguishable afterwards**, and this is the only
thing that separates them. So state a real reason from the page in front of
you. "The tool said 23" is not one, and neither is a reason invented to justify
a number — if you cannot say what you saw, you have not looked hard enough yet.

Do not write `disagrees:` when you agree. But note that "agree" means the page
matched, **not** that the number came out: the check behind this compares only
your row total and the opening-continuation flag, so if you found a bracket
fault that cancelled against another one, your total agrees and your
disagreement is still real. Write it. The report says as much when it prints
such a comment, and does not count it against you.

### The warnings, and the two that mean your numbering may be out

The context block may end with `**warning** <name>: …` lines. These are the
measurement telling you where it knows it might be wrong. They are not errors
and most pages have none — 17 of the book's 155 pages carry one. Two of them ask
you to check something specific, and both describe the same fault: **a run-over
line that measured flush, which is character-for-character what a headword looks
like.**

- **`flush-wrap`** — the left column's last line runs to the margin and the
  right column opens flush. Read the end of the left column and the start of
  the right. If the left ends on a hyphen (`… рыболо́вный крю-`) then the right
  column's first line finishes that word (`чо́к; 2) …`) and **the two are one
  entry**: one row, hyphen joined, and every number after it on the page is one
  too high.
- **`flush-runover`** — a flush line carrying almost no ink follows a line at
  full measure, mid-column. Same thing one axis over: `непоня́тли-` / `вый`.
  One entry, not two.

Both are the case where the numbering on your marked image is genuinely wrong,
so they are the one place you should expect to write `disagrees:` and be right.
Neither is auto-corrected, because the geometry cannot tell a real wrap from a
definition that merely happened to end at the margin — **only reading the words
settles it, which is why it is asked of you and not of the tool.**

A warning is a place to look, not a verdict. If you look and the page is fine,
say so in `note:` and keep the tool's numbering.

## Looking closer at the image

The page is ~1760×2480 and holds ~45 entries, so a single mark is very small at
full-page scale. **Magnify by entry label, not by pixel box, and ask for every
entry you want in one call:**

    uv run python scratch/chukchi/entry_bounds.py zoom moll-030:17
    uv run python scratch/chukchi/entry_bounds.py zoom moll-030:17,23,41

The label is the number drawn beside that entry on the marked page, so
`:17` means entry 17 — and `:c` the opening continuation, `:§` a section
heading. It crops to the entry's **own column**, so you get the useful
magnification rather than half a page of the column beside it. A wrapped
definition has two halves under one number and writes both, `-a` and `-b` in
reading order.

**Never loop this in the shell.** `for n in 1 2 3; do ... zoom $n; done`
and `zoom moll-030:{1..40}` both re-measure the whole page once per
entry; the comma form measures it once. If you find yourself writing a loop
around any command here, the command takes several arguments — check `--help`.

### How much to zoom, and how much is too much

**The magnification is capped at 4× and defaults to 2×.** Higher is refused by
the tool, and the refusal is the finding rather than a preference. These scans
are ~300 dpi bitonal: a character is ~30 px tall, so 4× already renders every
real pixel of ink as a 4×4 block. Past that the resampler is inventing values —
the picture gets bigger and strictly less informative, and interpolation
ringing around a speck looks exactly like a faint diacritic. That is the one
call zooming exists to make, so it is the one call zooming must not fabricate.

**The benefit is isolation, not size.** What makes an entry legible is being
cropped away from the other forty, and `zoom` does that at any scale.
2× is enough for almost everything. Reach for 4× when a specific mark is
genuinely in doubt — an apostrophe against a speck, `ё` against `е`, a stress
you cannot place — and not as a default posture.

**Do not "enhance" a zoom.** No `-sharpen`, `-contrast`, `-threshold`,
`-normalize`, no second resample, no re-cropping the crop. A mark that appears
only after processing is not evidence about the paper; it is evidence about the
filter. If a glyph is undecidable at 4× off the original, **it is undecidable**
— write it with `?` per the rules below and say so in `note:`. That is a useful
answer. A confident answer extracted by turning up the contrast is not.

**Before you zoom, ask what would settle the question.** There are three
answers and only one of them is a crop:

- **The letterform decides** → zoom. `ь` against `ъ`, `ё` against `е`, an
  apostrophe against a speck, whether a line ends on a hyphen. Both readings are
  legal, the ink is the only arbiter, and 2–4× is exactly the instrument.
- **The language already decided** → do not zoom, and do not be talked round by
  what you think you see. A stress accent over a Chukchi vowel is the standing
  case: Chukchi does not mark stress, so the mark is a blot however clean it
  looks, and magnifying it can only produce a confident wrong answer. Going to
  the raster to check something the orthography rules out is not diligence, it
  is manufacturing a reading.
- **Nothing decides** → `?` and a `note`. Not every mark on a 1957 letterpress
  page is a character.

Sorting a doubt into the right bucket *before* cropping is most of what keeps
the zoom count sane, and it is the difference between a reader who is resolving
doubt and one who is re-reading the page expensively.

**A budget, so the shape is clear:** a normal page needs somewhere between zero
and a handful of zooms. Three readers on the first three pages took **100**,
many at 8×, several then sharpened in place — for pages whose readings were
almost all decidable at 1×. If you are zooming most of your entries, you are
not resolving doubt, you are reading the page a second time at greater expense;
read it once, properly, at full scale and zoom the genuine hard cases.

It writes to `scratch/chukchi/moll-scans/zoom/` and prints the path; read that
with the Read tool. It crops from the *original*, not the marked version,
because half the marked bands are inverted and that is the wrong ground for
deciding whether a mark is a diacritic or a smudge.

Addressing by label matters. The bounds are already measured, so turning "the
mark over the last letter of entry 14" into a crop rectangle is you
re-deriving what the tool already knows, and every such translation is a chance
to magnify the wrong block and then report confidently about it.

**Do not write a Python/PIL script to crop or size an image.** It is slower to
write than the command, it needs an approval you may not get, and it is a tell
that a verb is missing or is being routed around. If `zoom` genuinely
does not cover what you need, this box has **ImageMagick 6** — `identify` for
dimensions, `convert IN.png -crop WxH+X+Y +repage OUT.png` for an arbitrary
box. There is no `magick`. Write output to your scratchpad, never into
`moll-scans/marked/` or `moll-scans/`.

That escape hatch is for **cropping and nothing else**, and it does not reopen
the scale cap: `-resize` above 4× and every enhancement operator are out by the
same reasoning that put them out of `zoom`. Cropping selects evidence;
filtering manufactures it.

## The characters

The Chukchi is Cyrillic, with two letters that will be lost if you are not
watching for them.

- **The apostrophe in `к'` and `н'` is part of the letter.** `к'` and `к` are as
  different as `к` and `л`; so are `н'` and `н`. Never drop it, never render it
  as a different mark (`ʼ ’ ‘ ´ '` are not interchangeable here — write the
  plain ASCII apostrophe `'`), and never separate it from its letter with a
  space. A dropped apostrophe silently merges two distinct letters and produces
  a word that looks perfectly well-formed.
- **The apostrophe also stands on its own, after a vowel** — `апаа'кэ`,
  `а'ныт`, `ы'мак'ын`. It is a letter in its own right there, not a stray
  `к'`/`н'` that has drifted, so **do not "repair" it by moving it onto the
  following consonant**: `апаа'кэ` is not `апаак'э`. Both uses occur in one
  word (`ы'мак'ын`), which is the case to watch. Write what the line prints and
  where it prints it; if you cannot tell which letter the mark belongs to, zoom
  the entry, and if it is still undecidable say so in `note`.
- **`ъ` and `ь` are both live and distinct.** `ъ` is a consonant here, not the
  Russian hard sign's silent role. Neither ever begins a word.

  **This is the most common reading error on this book, by a wide margin**, and
  it has two shapes. The first is dropping a `ь` entirely: `-льын` is an
  extremely productive participial ending here (`ванляльын`, `атк'авыльын`,
  `вагылкалельын`, `гаглыльын`), and a reader keying `-лын` produces a word
  that looks perfectly well-formed, sorts within one position of the truth, and
  passes every check. One page carried **five** of them. **If you have keyed a
  headword ending `-лын`, go back and look at it** — the ending is `-льын` far
  more often than not.

  The second is confusing the two signs with each other, in both directions:
  `витъывит` keyed `витьывит`, `вэчьым` keyed `вэчым`. At print size they differ
  only in whether the upper-left stroke is there. This is worth a zoom, unlike
  the accent question above — here the letterform really does decide, and both
  readings are legal words.
- **`ё` is distinct from `е`.** The book prints the diaeresis; keep it.
- **`и` and `н` differ by one horizontal stroke, and the headword is set in
  bold.** In this face the `и` diagonal thickens until it reads as a crossbar,
  and a ~300 dpi bitonal scan drops or adds the stroke in both directions. This
  was measured on the medial-stem appendix (folios 187–194), whose rows print
  each stem twice — once bold, once inside a roman participle — so the two
  spellings can be compared directly: **40 contradictions in 379 rows, 29 of them
  a single и/н flip apart.** Roughly one row in ten.

  **A dictionary page has no such second copy.** The headword is bold and the
  gloss is Russian, so nothing on the line restates it, and an `и`/`н` slip
  produces a well-formed Chukchi word that sorts almost correctly and passes
  every rule here. Only the OCR store can see it.

  **Do not try to settle it by zooming past the cap.** Three readers on three
  different appendix pages each went to 4× and each concluded, correctly, that
  the letterform does not decide. Read at 2×, and if the stroke is genuinely
  ambiguous say so in `note` rather than picking — a flagged row is recoverable
  and a confidently wrong one is not.
- **Do not double a consonant that is not doubled.** `тг` read as `тт` has now
  happened four times — `армалтатгыргын`, `аратгыргын`, `гаргатгыргын` — always
  in the `-тгыргын` nominalizing suffix, which is everywhere in this book. The
  two sort identically, so nothing downstream can catch it. When you key a
  headword containing `-тгыргын`, that is the suffix; `-ттыргын` is almost
  certainly a misreading of it.
- **Keep the Russian stress accents, and expect them nearly everywhere.** The
  gloss side marks stress — `цара́пина`, `зно́й`, `ожида́ние` — and the book
  prints it, so it is transcription and not decoration. You know Russian; that
  knowledge is one of the few real advantages you bring to this page, and this
  is where to spend it.

  **The book accents essentially every polysyllabic Russian word.** Across the
  pages keyed so far, 68–97% of gloss *rows* carry at least one, and the rows
  carrying none are the ones whose gloss is a bare `см.` cross-reference or a
  single monosyllable. **A page that comes back with no accents at all is
  wrong.** Two readers have produced exactly that — 0 of 43 rows, 0 of 46 — and
  both pages had to be read again from scratch. Nothing else in the loop can see
  it: the audit compares headwords, and headwords carry no accent at all; the
  collation rules never look at the gloss; and the gloss is still perfectly good
  Russian without them.

  **Chukchi does not mark stress. Never put an accent on a Chukchi form** —
  not on the headword, not on a `(мн. …)` plural, not on a `см.` target. There
  is no exception, so a mark you think you see over a Chukchi vowel is an
  inkblot on a 1957 bitonal scan, or your Russian reflex firing on a word that
  is not Russian. **Do not zoom to settle it**: at 4× a blot and an acute are
  not separable, and the language decides this, not the crop. Two such marks
  reached the store and were stripped; a normalizer now removes them from the
  headword silently.

  **Write the Cyrillic vowel followed by U+0301 COMBINING ACUTE. Never reach
  for a precomposed accented vowel.** Unicode has no precomposed *Cyrillic*
  accented vowels at all, so anything you type as `á é ó ý` is a **Latin**
  letter wearing an accent, and it lands in the middle of a Cyrillic word
  where it is invisible on screen and wrong in the file. Three readers did
  exactly this on their first pass — 66 Latin letters across three crops — and
  a later one did it in 15 rows of 38 while keying the other 23 correctly, so it
  is not even reliably a page-wide habit you could spot-check for.
  Worse, `и` has no Latin lookalike to borrow, so the same reflex produced
  `очевúдно` with a Latin `u`: not merely the wrong script but the wrong
  letter, in a word whose stressed vowel is `и`. Build every accented vowel
  as base + U+0301 and the problem cannot arise.

  **But do not spend zooms on the encoding, and do not re-read your own file
  hunting for it.** A normalizer folds every Latin letter inside a Cyrillic word
  to its Cyrillic counterpart before anything else sees your output. Emitting
  one specific awkward codepoint is a probabilistic thing to ask of you and the
  repair is mechanical and total, so it is not held against the reading. Aim for
  base + U+0301 and move on. What is **not** recoverable is an accent you never
  keyed: nothing in the file records where it should have gone.
- **No Latin lookalikes.** `а е о р с у х` and their capitals must be Cyrillic
  throughout, in both the Chukchi and the Russian.

## Hyphens

- **A hyphen at the end of a line is typographic.** Join the word: `анн'ат-` /
  `ытвыт` is one word, `анн'атытвыт`. Do this in the Russian gloss and in the
  Chukchi alike.
- **A hyphen anywhere else is data.** Keep it exactly. **In the Chukchi**, say
  so in that row's `note`: that orthography is not known to use word-internal
  hyphens, so one is either a reading error or something worth a human's
  attention, and both want flagging.
- **Do not note hyphens in ordinary Russian.** `по-друго́му`, `что́-л.`,
  `чего́-л.`, `из-за`, `кто́-нибудь` are standard orthography and carry no
  signal. The rule above is scoped to the Chukchi because that is where a
  hyphen is unexpected; applied to the Russian it would put a note on a large
  share of every page, and a flag that fires on the ordinary case buries the
  one that matters.

## When you cannot read it

Mark it. Never guess.

A wrong reading that looks like a word carries no error signal — it passes every
check downstream, because nothing downstream has the page. An entry marked
unresolved is a valid deliverable and costs someone thirty seconds at the raster.
An invented one is a defect that survives to the end.

**A mark that is not a known letter or diacritic is usually a smudge**, and
that is a finding rather than a failure: this is a 1957 letterpress printing on
cheap paper and the scan carries its blots. Zoom the entry before ruling
(`zoom STEM:N`), and if it resolves to a blob rather than a stroke, keep the
headword as read and say so in `note` — do not invent a character for it and do
not silently drop it. What you must never do is treat it as evidence for a
letter you would not otherwise have read.

So: if a character, a word, or a whole line will not resolve, transcribe what you
can, put `?` in place of what you cannot, and say in the row's `note` column what
you could not read. The `?` is the marker — there is no separate flag to set, and
a row carrying no `?` is a row you are claiming to have read. Do not reason from
what the word "should" be, from the neighbouring entries, or from what would make
the alphabetical order come out.

### Where to look again: the endings this book actually makes

Chukchi is agglutinative and this dictionary's headwords are overwhelmingly a
stem plus one of a small set of very productive endings. Measured over the
headwords keyed so far:

    -ын 325   -ык 157   -гын 155   -льын 109   -ргын 96   -ыргын 94
    -тык 93   -гыргын 84   -лгын 48   -атык 42   -тгыргын 30

**What this is for: deciding where to look harder.** A final syllable is the
hardest part of a headword to read — it is where the ink is lightest, where a
line break falls, and where every word on the page looks like every other. The
list tells you which distinctions are *real questions* on this book. `-лын`
against `-льын` is a real question and you should go back and settle it.
`-тгыргын` against `-ттыргын` is a real question. A reading that lands on none
of these shapes is worth one more look before you commit it.

**What this is emphatically NOT for: writing an ending you did not read.** The
prohibition elsewhere in this skill stands unchanged and outranks everything
here — *do not reason from what the word "should" be.* A frequency list is a
prior about the book, not evidence about your page, and the failure it invites
is precisely the one that carries no error signal: an ending that is common,
plausible, well-formed, and not what is printed. This is the same rule as the
context block's counts and the `flush-wrap` warnings. **A prior is a place to
look. It is never a verdict, and it never fills a gap.** If the page will not
resolve after you have looked again, write `?` and say so — that is the correct
outcome and it is not a failure.

### The gloss is a free second look at your own headword

This dictionary glosses into Russian, and Russian marks morphologically much of
what Chukchi marks. So the gloss you are already transcribing often corroborates
the ending you just read, at no cost and without opening a crop:

| ending | the gloss tends to be |
|---|---|
| `-льын` | a present active participle — торопя́щийся, свистя́щий, вдева́ющий — or an adjective, or a person |
| `-гыргын` | an abstract noun — хромота́, ране́ние, зло́ба, ожида́ние |
| `-к` / `-ык` | a Russian infinitive — хрома́ть, пря́таться, гнать |
| `-лгын` | a concrete common noun — но́готь, губа́, реме́нь |
| `-кэн` / `-кин` | a relational adjective — ле́тний, вече́рний, дома́шний |

So a headword you read as ending `-лын` whose gloss is `торопли́вый` is worth
another look at that one letter; the two halves of your own row are telling you
different things.

**This is corroboration, never evidence about a letterform, and the page still
outranks it.** The gloss cannot see the ink. If the two genuinely disagree after
you have gone back and looked, **write what the page prints** and put the
disagreement in that row's `note` — the book contains printing errors and
irregular forms, and a headword quietly adjusted to match its own translation is
indistinguishable afterwards from one that was read. Never edit a headword to
fit this table.

**The order on the page is not always alphabetical, and you must not fix it.**
The book contains printing errors. If two entries appear out of sequence,
that is the record, and correcting it destroys the only evidence of the defect.

## Output contract

Two comment lines, then one Markdown table, one row per entry, in printed order:

```markdown
<!-- source: moll-042.png -->
<!-- note: -->

| headword | gloss | note |
|---|---|---|
| ан'к'ы | (мн. ан'к'ат) море | |
| ан'энмэтыкэн | * заветный | |
| ан'ъаломом | зной (си?ьная, угнетающая жара) | 3rd char of сильная not resolvable |
```

Rows go in the numbered reading order, so row *n* is entry *n* on your image.
Do not restart or renumber at the column break, and do not give a wrapped
definition two rows.

- **`source`** — the filename you read, echoed, and the **original** name, not
  `marked/`. Nothing else: no page or folio. The folio is a fact about the scan
  set (`moll-NNN.png` holds folio NNN−1) and a field you derive is a field you
  can derive wrongly.
- **`note:` comment** — anything about the page as a whole, such as a section
  capital you skipped or a badly printed patch. Leave it empty if there is
  nothing; do not fill it with what was true of every page, like the running head.
- **`headword`** — the Chukchi form alone, character-exact. Not the parenthesised
  plural, not the asterisk. This one column carries
  every check that will be run on your work, so it is the one to slow down for.

  **The homonym numeral is the one thing that stays.** Where the book prints two
  entries under the same form and separates them `I` / `II`, write
  `аквын' I` and `аквын' II` — the numeral, spaced, at the end of the headword.
  It is the only thing distinguishing the two rows, so a checker seeing them
  without it cannot tell a real homonym pair from the same entry keyed twice,
  and reports an error on correct work. Collation ignores the numeral; the
  duplicate check does not. Put it in the headword, not at the head of the
  gloss.

  **The book sometimes prints the same entry twice, and you record it twice.**
  Folio 23 sets `въаймагны (мн. въаймагтэ) стог (се́на)` at two different
  brackets, identical in every character. That is not a homonym pair — the book
  numbers those `I`/`II` — and it is not your error. Give it a row each time it
  appears, exactly as printed. Do not merge them, do not add a numeral to tell
  them apart, and do not drop the second. A repeated headword is flagged by the
  audit, which is correct: the ordinary cause *is* a transcription fault, and a
  human rules the rare real case.

  **Variant pairs stay together in this cell.** The book routinely opens an
  entry with two bold forms separated by a comma — `аалёмка, авалёмка`,
  `айватлён, айватрон` — sharing one gloss. Write both, comma and space, in the
  order printed: `аалёмка, авалёмка`. They are one printed entry and get one
  row, so splitting them into two rows would put your count one above the
  page's; dropping the second would lose a headword; pushing it into `gloss`
  would file a Chukchi form as Russian. The **first** form is the one the book
  alphabetizes on, which is why order matters and why it must not be tidied.

  **Punctuation set in bold with the headword stays with it** — `ага-га!`,
  `айылго:`. It is part of what the entry prints, and the list of things to
  strip above is exhaustive: numeral, plural, asterisk, nothing else.

  **A multi-word headword is one headword** — `алва рылек` is a single form,
  distinct from the entry `алва` elsewhere on the page. Keep the space.

  **A colon ends the headword, even when bold text follows it.** The book has a
  standing form for a word that is only used in a set phrase: headword, colon,
  then the phrase repeated in bold with the translation — `вэнну: вэнну лын'ык
  завидовать кому-л.`, `айылго: айылго лын'ык`, `алымалявка: алымалявка итык`.
  The **headword is the word before the colon**; the colon and everything after
  it are the gloss. Do not pull the phrase into the headword cell, and do not
  join its words — `алымалявка итык` is two words, and a line break between
  them with **no hyphen** is a word boundary, not a split word. The book states
  this form in its own front matter, so it is a convention and not a one-off.
- **`gloss`** — the entire rest of the entry, verbatim, Russian and all. Leave the
  notation exactly as printed and unexpanded: `*`, `(2)`, Roman numerals, `1)`
  `2)` `3)`, bold `1.` `2.`, `(мн. …)`, `(ед. …)`, `см. …`. Something later parses
  these; your job is to carry them across unaltered.
- **`note`** — empty for almost every row. Use it to say what a `?` stands for.
- **A literal `|` inside any cell must be written `\|`**, or it ends the cell and
  silently shifts every column after it. Nothing else needs escaping.

Do not sort the rows, do not add a totals line, do not merge the tables of two
pages. One page, one file, one table.

## Self-check before writing

- Is every `headword` a word I saw flush-left and in bold? *(Always yes.)*
- Did I record the page-number fragment, the running head, or a section capital
  as an entry? *(Always no.)*
- Did I follow the numbered reading order across the gutter, rather than
  restarting at the right column? *(Always yes.)*
- Did I give a wrapped definition — one number, two brackets, the second marked
  `←` — a single row with its gloss joined? *(Always yes.)*
- Did I put any English anywhere in the file? *(Always no — this pass does not
  translate.)*
- Does every `к'` and `н'` in my output still have its apostrophe? *(Always yes.)*
- Does every polysyllabic Russian word in my glosses carry its stress accent?
  *(Very nearly always yes. If my file has none at all, I have not done the
  job and must go back over the page.)*
- Did I put a stress accent on any Chukchi form? *(Always no — Chukchi does not
  mark stress, whatever I think I saw.)*
- For every headword I keyed ending `-лын`: did I look again to check it is not
  `-льын`? And for every one containing `-ттыргын`: is it not `-тгыргын`?
  *(These two are the errors this book actually produces.)*
- Did every numbered bracket I gave a row to actually contain a flush-left bold
  headword — rather than a quire mark, a bare sense number, or two entries?
  *(Checked one by one, not by the total.)*
- For every `и` and every `н` in a headword: is that stroke really there?
  *(Bold `и` and `н` are one horizontal stroke apart in this face, and the
  headword has no second copy of itself on the line to check against.)*
- Where a letterform genuinely did not resolve at 2×, did I write `?` and a
  note — rather than pick the likelier letter? *(Always the former. A flagged
  row is recoverable; a confident wrong one is indistinguishable from a right
  one forever.)*
- Did I reorder, merge or drop an entry to make the sequence look right?
  *(Always no.)*
- Is the block at the very top of my page indented with no bold headword above
  it? If so, did I write the `continues:` line and leave it out of the table?
  And if the top block *does* begin with a bold flush-left headword, did I leave
  the `continues:` line out?
- Does my row count match the context block? If not, did I write `disagrees:`
  with a reason taken **from the page** — and did I resist changing what I read
  to make the number come out? *(The second is the one that matters.)*

## What you never do

- **Translate.** Not the gloss, not the headword, not into the `notes`. English
  glossing is a separate pass over this output and is not your job.
- **Correct.** Not a Russian spelling, not a Chukchi form, not the alphabetical
  order, not an apparent typo. Record the page.
- **Normalise.** No case changes, no swapping one apostrophe or dash for another,
  no expanding `см.` or `мн.`, no converting `ё` to `е`.
- **Reorder, merge, or split** entries — including to make a count come out.
  In particular, do not renumber at the column break: reading order is the
  numbering on your image and it runs straight through the gutter.
- **Read any page other than the one you were given**, including to resolve a
  definition that runs off your top or bottom edge. Mark it and move on.
- **Write anywhere but `scratch/chukchi/moll-scans/entries/`.** Nothing this pass
  produces may be written into `gt/`, `tei/`, `ocr/`, or any corpus store. This
  is a machine reading of a reference work in a scratch area; it has no standing
  as ground truth anywhere in this repo.
