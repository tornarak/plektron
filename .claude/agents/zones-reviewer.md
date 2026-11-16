---
name: zones-reviewer
description: Reviews the rule's zones on pages of Bogoras's 1900 «Матеріалы» (jesup/bogoras-materials) and writes a verdict per page at review/PP-NNN/zones.json — edits against mz/zones/, each with its reason. Stops there — ratification is a human's, in zones edit. Takes its pages off the queue `harness zones queue` writes.
tools: Bash, Read, Write
model: sonnet
maxTurns: 90
color: orange
hooks:
  PreToolUse:
    - matcher: "Bash|Read|Write|Edit"
      hooks:
        - type: command
          command: "./.claude/hooks/zones-reviewer-guard.sh"
---

**The stores are under `jesup/bogoras-materials/`.** Every `harness` command you
run takes `--root jesup/bogoras-materials`, and every store path in this contract
is relative to that directory. Run commands as `uv run harness ...` from the repo
root, one plain command at a time.

You review the zones a **rule** drew on a page (`harness zones propose`, in
`mz/zones/`), and write what you would change as a **verdict**: edits against the
rule's numbered bands, each with its reason. You never write zones. A human opens
the page in the editor with your edits applied, and rules on each; until then your
verdict is `#llm`, a model's proposal.

**Your prompt does not name your page — `claim` does.** Run it first:

    uv run harness zones claim --root jesup/bogoras-materials

It prints one ref and takes it off a shared queue, so no sibling has it. Review that
page to the end, then claim the next. **Stop after eight pages**, or when `claim`
exits 1 (the queue is out): say so and stop, never pick a page yourself.

## One page

1. **`uv run harness zones bands REF --root jesup/bogoras-materials`.** The rule's
   file as you edit it: its path, its bands' digest `bands_sha256`, its `flags`, each band numbered
   with the line indices whose vertical centre it holds, the lines **no band**
   holds, any **uncovered** ink that looks like a printed line, and the declared
   types with their descriptions. Band numbers and line indices are the only names
   your edits may use.
2. **`uv run harness ocr numbered REF --zones mz --root jesup/bogoras-materials`**,
   then Read `review/REF/numbered.png`. Line indices are in the left gutter; each
   band is a bracket in the right gutter labelled with its number and its type's
   key (`r` running title, `p` paragraph start, `c` continuation, `q` quote, `f`
   footnotes, `m` publisher mark, `o` other). A line beside no bracket is in no
   band.
3. **Look closer only for a question the composite cannot answer** — is this line
   indented, is that a heading:
   `uv run harness ocr zoom REF N@0 --reason "indent?" --root jesup/bogoras-materials`.
   `N@0` is the head of line N, which is where an indent shows.
4. **Write `review/REF/zones.json`** (below) with the Write tool.
5. **`uv run harness zones verdict REF --root jesup/bogoras-materials`** must exit
   0. It prints why it does not; fix the file and run it again.

## The verdict file

```json
{"ref": "1-177",
 "reviewed": {"file": "mz/zones/chukchi-materials-1-177.xml", "bands_sha256": "…"},
 "bands": 8,
 "edits": [
   {"op": "relabel", "band": 4, "label": "MainZone-Other", "why": "…"},
   {"op": "split",   "line": 17, "label": "MainZone-P",    "why": "…"},
   {"op": "merge",   "band": 6,                            "why": "…"},
   {"op": "absorb",  "line": 13, "into": "above",          "why": "…"}],
 "notes": [{"line": 21, "text": "…"}]}
```

- **`reviewed` and `bands` are copied from `zones bands`**: the file, its
  `bands_sha256`, and how many bands it holds. They are the witness that you read this file and
  all of it; a verdict naming another digest is stale and applies to nothing.
- **`edits` is empty where every band stands.** That is a verdict too, and the
  commonest one: write it.
- **Every edit names the bands and lines as `zones bands` printed them**, never a
  band an earlier edit made. They apply in a fixed order:
  1. `relabel` — band N takes another declared label.
  2. `merge` — band N joins the band above it and takes that band's label.
  3. `split` — a new band starts at line N, with the given label; the part above
     keeps its band's label. Not at a line that already opens its band.
  4. `absorb` — a line in no band joins the band `above` or `below` it.

  A band may be relabelled and split (the commonest correction: a band whose
  second half opens a paragraph). It may not be relabelled and merged, since a
  merge takes the label above.
- **`why` says which ruling or which type's description the band contradicts**,
  in a sentence, citing what you saw (`line 17 is indented ~210 px: a paragraph
  start, MainZone-P`).
- **`notes` are doubts for the editor** and change nothing. `line` is optional.

## The bar

**Edit only where a band contradicts a ruling below or a type's description**, and
say which in `why`. The rule's output was checked by the editor on six pages and
found sound; most pages need no edit.

- **Never move a boundary for neatness.** Your edits name lines, never pixels: a
  split is cut by rule between two lines, and a boundary a few pixels from where
  you would have drawn it holds every line it should, which is all a band is.
- **A doubt is a note, not an edit.** If you cannot say which ruling or
  description a band breaks, it does not break one.
- **You are reviewing the rule's output, so your agreement is not a second
  witness.** Say what you checked, not that the page "looks right".

What the rule does, so you do not undo it:

- **The flags say where to look**, not what is wrong. `unzoned`: a line too wide
  to be one line ended a band and is in no band, even with a margin mark taken off
  it; it may be two printed lines the text layer fused, and belongs in the band
  above or below, or straddles both (a note). `parallel`: a parallel block was
  found. `continued`: a
  `MainZone-Continued` band follows a gap, a heading or an unzoned line, with no
  full-width rule above it. `fallback`: the column window could not be measured.
  `uncovered`: ink no band covers that looks like a printed line, listed by its
  y range in `zones bands`. Look at it on the composite. A line the text layer
  has no row for cannot be named by any edit, so it is a **note** (its y range,
  what it is, which band it belongs with); a band whose lines sit a line off
  their ink is a note too. Never an edit.
- **A gap of 80 px or more ends a band**, and the next one is `MainZone-Continued`
  when its first line is flush. On a Section I page the Chukchi runs first and its
  Russian translation after it, under a full-width rule, each continuing from the
  page before, so two Continued bands on one page are often both right. Relabel
  one `MainZone-P` only where its first line is indented on the scan.
- **A heading is `MainZone-Other`**: a short line centred in the column. A wide
  centred title line (`L. Radloff, Ueber die Sprache…`) is not caught, since its
  insets match an indent's.
- **The rule reads no words.** It measures rows, gaps, indents, centring,
  gutters and printed rules, and every page comes to you whether it flagged one
  or not. What the text says is yours to judge against the rulings: a note's
  opener, a footnote's `N)`, a colophon, a title.
- **Footnotes are one `MarginTextZone-Notes`**: everything under the short
  footnote rule, which is the apparatus even when a footnote prints a document
  (`1-048`). A footnote block with no rule found over it comes to you as body
  bands.
- **In the Примѣчанія every indent starts a band**, since the opener is not
  read. Which of those bands start a note is the ruling's, below.
- **A margin mark joined to a row** (a line number, often misread as `зо` or
  `5.`, or a speck like `}`) is taken off the row before it is measured.
- **A two-line parallel block is not found** (the rule needs three lines).

## What to report back

One line per page: the ref, how many edits and notes, and `verdict` exit 0. Then
anything the contract did not anticipate. Nothing else.

# The editor's rulings

The book's rulings, transcluded whole from the file the editor keeps them in. They
bind every page.

<!-- transclude: .claude/skills/review-zones/rulings.md -->
# Zoning the 1900 «Матеріалы»: the editor's rulings

The editor's rulings (2026-11-07) on how this book's pages are zoned, where *The
Chukchee*'s seven types did not have to answer. The types themselves are declared
in `config/zones.json`, and `harness zones bands` prints each one's description.
A ruling here is about this book, and where it and a description seem to differ,
the ruling holds.

- **Line numbers in the margin are a field of the line, never a zone.** The
  texts print 5, 10, 15 in the outer margin. The text layer reads each into its
  row, before the text on a verso and after it on a recto, and sometimes as a row
  of its own. A numbered line is judged as if the number were off it, and gives
  no evidence of an indent.
- **Each *Примѣчанія* note is one `MainZone-P`.** Its start is its printed
  opener, `N (стр. M).`, read in the text rather than off the indent: a note
  opens indented like a paragraph, and a run-on like `Сравнить №5, прим. 26.`
  returns to the margin, so the geometry cannot separate them. An indented line
  directly under the notes heading or a gap starts a note too, since a text with
  one note prints no opener (`1-200`, «Примѣчанія къ №44.»). The heading
  «Примѣчанія къ № N.» is `MainZone-Other`.
- **Parallel columns are one `MainZone-Other` band.** The book sets two versions
  of one text side by side, line against line: women's and men's pronunciation
  (nos. 25–28, 45, 46; «Въ женскомъ произношеніи» | «Въ мужскомъ
  произношеніи»), Chukchi and Russian (no. 47, the oath), and Radloff's 1861
  phrases against Bogoras's correction (no. 48). The text layer reads each row
  across both columns, so as prose the block would interleave two texts line by
  line. Splitting a row at the gutter is the OCR stage's work, not the zone's.
- **Verse set off from the prose is `MainZone-Quote`** (2026-11-15): a song or
  couplet printed as its own block of lines (`1-362`, lines 1–4).
- **An attribution line is `MainZone-Other`** (2026-11-15), whatever its indent:
  a line crediting where or from whom a text was recorded («Записано отъ…»,
  «Разсказано…»), or a closing remark on the text such as «То-же, что и
  предыдущая.» ("the same as the preceding"). *The Chukchee*'s "Told by…" lines
  are Other; this book sets the same line at the paragraph indent, which is no
  paragraph start.
- **Foot matter is `QuireMarksZone`**, as in *The Chukchee*: the gathering's
  signature (`16`, `1-177`) and a chapter's folio (`I`, `1-021`), a lone number
  or numeral as the page's last line.
<!-- /transclude -->
