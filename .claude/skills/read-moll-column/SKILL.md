---
name: read-moll-column
description: Read one column crop of Moll & Inenlikej 1957 into a Markdown table of headword/gloss entries under scratch/chukchi/moll-entries/. Use when extracting the Chukchi–Russian dictionary, dispatching parallel readers over moll-cols/, or on /read-moll-column FILE. Carries the page anatomy, the character rules and the output contract. Not a Bogoras corpus pass — nothing it produces may enter gt/ or tei/.
---

# Read one dictionary column (column crop → headword table)

You are one of several readers working the same book in parallel. You read one
image and write one file. You never see another crop, and you never need to —
nothing on your crop depends on anything on any other.

You do not check your own work. A separate pass audits every file this skill
produces, against the page layout and against the book's own alphabet. Do not
try to make your output look consistent; try to make it match the paper.

**This skill reads no other document.** The sibling skills in this repo open by
sending you to `keying_spec.md` and `CLAUDE.md`; this one does not, deliberately.
Everything you need is below. Do not go looking for project context, and do not
apply rules you remember from elsewhere in this repo — this is a different book,
in a different script, in a scratch side quest.

## The call

    Read   scratch/chukchi/moll-cols/moll-NNN-{L,R}.png   # your crop
    Write  scratch/chukchi/moll-entries/moll-NNN-{L,R}.md # your output

Same stem, `.md` for `.png`. One file in, one file out. If
`scratch/chukchi/moll-entries/` does not exist, create it.

## What is on the crop

The crop is **one column of a two-column dictionary page**, cut with a 50 px
overlap so that nothing could be clipped. That overlap is why three things
appear on your crop that are not yours to read.

- **Above the horizontal rule** sit the running head and the page number. The
  page number is centred on the page, and the cut runs through it, so **it
  appears as a fragment on both crops** — a stray `— 3` or `9 —`. It is not an
  entry and not part of one. Neither is the running head.
- **The vertical rule is the column boundary.** In an `-R` crop, everything to
  the left of that rule belongs to the other column; in an `-L` crop, everything
  to the right of it does. The overlap means you will see the line-end hyphens
  and final letters of the neighbouring column along that edge. **They are not
  yours.** Read only your side of the rule.
- **A large centred capital** appearing part-way down is a letter-section
  heading — the book starting а, or к', or ю. It is also split by the cut, so
  you may be looking at half of one. It is not an entry and has no gloss.

## What is an entry

An entry begins with a **bold headword set flush to the left margin**. Every
line below it that is **indented** continues it. The next flush-left bold word
begins the next entry.

Record entries in printed order, top to bottom.

**Your crop may open in the middle of a definition.** A definition wraps from
one column into the next, so the block at the top of your crop can be indented
with no bold headword above it — the headword is in the previous column, which
you cannot see and must not guess at. When that happens, **say so and do not
give it a row**:

```markdown
<!-- continues: indented text at the top, no headword on this crop -->
```

The last entry may likewise break off mid-word. Record what is on your crop and
nothing else; do not complete it.

**A section heading splits your column in two.** Where a large centred capital
appears, the type stops well above it and resumes well below, and the two runs
are read in the usual top-to-bottom order — but be aware that the book reads
*across* at that point: the run above the heading in the left column is
continued by the run above it in the right column, not by the run below it.
That is the joiner's problem, not yours. Read your crop straight down.

## What you are told before you start

You are given a context block for your crop — its folio and column, which
initials the folio can carry, how many entries begin on it, whether its first
block is a continuation, and where any section headings fall. It is produced by

    uv run python scratch/chukchi/entry_bounds.py --split-l 209 --split-r 31 \
        --context moll-042-R

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
<!-- source: moll-042-R.png -->
<!-- note: -->

| headword | gloss | note |
|---|---|---|
| ан'к'ы | (мн. ан'к'ат) море | |
| ан'энмэтыкэн | * заветный | |
| ан'ъаломом | зной (си?ьная, угнетающая жара) | 3rd char of сильная not resolvable |
```

- **`source`** — the filename you read, echoed. Nothing else: no page, folio or
  column. Those live in `moll-cols/manifest.csv`, which is authoritative, and a
  field you derive is a field you can derive wrongly.
- **`note:` comment** — anything about the crop as a whole, such as a section
  capital you skipped or a badly printed patch. Leave it empty if there is
  nothing; do not fill it with what was true of every crop, like the page header.
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
crops. One crop, one file, one table.

## Self-check before writing

- Is every `headword` a word I saw flush-left and in bold? *(Always yes.)*
- Did I record the page-number fragment, the running head, or a section capital
  as an entry? *(Always no.)*
- Did I read anything on the far side of the vertical rule? *(Always no.)*
- Did I put any English anywhere in the file? *(Always no — this pass does not
  translate.)*
- Does every `к'` and `н'` in my output still have its apostrophe? *(Always yes.)*
- Did I reorder, merge or drop an entry to make the sequence look right?
  *(Always no.)*
- Is the block at the very top of my crop indented with no bold headword above
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
- **Read the neighbouring column**, or any crop other than the one you were given.
- **Write anywhere but `scratch/chukchi/moll-entries/`.** Nothing this pass
  produces may be written into `gt/`, `tei/`, `ocr/`, or any corpus store. This
  is a machine reading of a reference work in a scratch area; it has no standing
  as ground truth anywhere in this repo.
