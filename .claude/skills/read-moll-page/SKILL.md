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
reading order, 1..N. **Follow the numbers.** They are also what the context
block counts and what any later pass will join on.

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

## What you are told before you start

You are given a context block for your page — its folio, which initials the
folio can carry, how many entries it holds, whether it opens mid-definition,
which definitions wrap across the gutter, and where any section headings fall.
It is produced by

    uv run python scratch/chukchi/entry_bounds.py --page-context moll-042

Your image comes from **`moll-scans/marked/`**, which is the page with the
measurement drawn on it: alternating entries **inverted** (white on black),
each numbered in a white strip inserted before its own column, an opening
continuation in pink and marked `c`, a section heading in amber and marked `§`,
and the second half of a wrapped definition repeating its number with `←`. The
numbering matches the context block and `moll-bounds.md`.

The right column is shifted right to make room for its numbers, so the marked
page is a little wider than the scan. That is a transcriber's aid, not a
facsimile; `--zoom-page` crops from the original raster.

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

Do not write `disagrees:` when you agree; a comment with nothing to disagree
with is reported too.

## Looking closer at the image

The page is ~1760×2480 and holds ~45 entries, so a single mark is very small at
full-page scale. **Magnify by entry label, not by pixel box:**

    uv run python scratch/chukchi/entry_bounds.py --zoom-page moll-030:17
    uv run python scratch/chukchi/entry_bounds.py --zoom-page moll-030:17 --scale 5

The label is the number drawn beside that entry on the marked page, so
`:17` means entry 17 — and `:c` the opening continuation, `:§` a section
heading. It crops to the entry's **own column**, so you get the useful
magnification rather than half a page of the column beside it. A wrapped
definition has two halves under one number and writes both, `-a` and `-b` in
reading order.

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
that a verb is missing or is being routed around. If `--zoom-page` genuinely
does not cover what you need, this box has **ImageMagick 6** — `identify` for
dimensions, `convert IN.png -crop WxH+X+Y +repage OUT.png` for an arbitrary
box. There is no `magick`. Write output to your scratchpad, never into
`moll-scans/marked/` or `moll-scans/`.

## The characters

The Chukchi is Cyrillic, with two letters that will be lost if you are not
watching for them.

- **The apostrophe in `к'` and `н'` is part of the letter.** `к'` and `к` are as
  different as `к` and `л`; so are `н'` and `н`. Never drop it, never render it
  as a different mark (`ʼ ’ ‘ ´ '` are not interchangeable here — write the
  plain ASCII apostrophe `'`), and never separate it from its letter with a
  space. A dropped apostrophe silently merges two distinct letters and produces
  a word that looks perfectly well-formed.
- **`ъ` and `ь` are both live and distinct.** `ъ` is a consonant here, not the
  Russian hard sign's silent role. Neither ever begins a word.
- **`ё` is distinct from `е`.** The book prints the diaeresis; keep it.
- **Keep the Russian stress accents.** The gloss side marks stress —
  `цара́пина`, `зно́й`, `ожида́ние` — and the book prints it, so it is
  transcription and not decoration. They appear only on vowels, and only in
  the Russian.

  **Write the Cyrillic vowel followed by U+0301 COMBINING ACUTE. Never reach
  for a precomposed accented vowel.** Unicode has no precomposed *Cyrillic*
  accented vowels at all, so anything you type as `á é ó ý` is a **Latin**
  letter wearing an accent, and it lands in the middle of a Cyrillic word
  where it is invisible on screen and wrong in the file. Three readers did
  exactly this on their first pass — 66 Latin letters across three crops.
  Worse, `и` has no Latin lookalike to borrow, so the same reflex produced
  `очевúдно` with a Latin `u`: not merely the wrong script but the wrong
  letter, in a word whose stressed vowel is `и`. Build every accented vowel
  as base + U+0301 and the problem cannot arise.
- **No Latin lookalikes.** `а е о р с у х` and their capitals must be Cyrillic
  throughout, in both the Chukchi and the Russian.

## Hyphens

- **A hyphen at the end of a line is typographic.** Join the word: `анн'ат-` /
  `ытвыт` is one word, `анн'атытвыт`. Do this in the Russian gloss and in the
  Chukchi alike.
- **A hyphen anywhere else is data.** Keep it exactly, and say so in that row's
  `note`. This orthography is not known to use word-internal
  hyphens, so one is either a reading error or something worth a human's
  attention, and both want flagging.

## When you cannot read it

Mark it. Never guess.

A wrong reading that looks like a word carries no error signal — it passes every
check downstream, because nothing downstream has the page. An entry marked
unresolved is a valid deliverable and costs someone thirty seconds at the raster.
An invented one is a defect that survives to the end.

**A mark that is not a known letter or diacritic is usually a smudge**, and
that is a finding rather than a failure: this is a 1957 letterpress printing on
cheap paper and the scan carries its blots. Zoom the entry before ruling
(`--zoom STEM:N`), and if it resolves to a blob rather than a stroke, keep the
headword as read and say so in `note` — do not invent a character for it and do
not silently drop it. What you must never do is treat it as evidence for a
letter you would not otherwise have read.

So: if a character, a word, or a whole line will not resolve, transcribe what you
can, put `?` in place of what you cannot, and say in the row's `note` column what
you could not read. The `?` is the marker — there is no separate flag to set, and
a row carrying no `?` is a row you are claiming to have read. Do not reason from
what the word "should" be, from the neighbouring entries, or from what would make
the alphabetical order come out.

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
- **`headword`** — the Chukchi form alone, character-exact. Not the homonym
  numeral, not the parenthesised plural, not the asterisk. This one column carries
  every check that will be run on your work, so it is the one to slow down for.
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
