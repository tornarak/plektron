---
name: read-captions
description: Read all 395 Bogoras figure captions off contact sheets into review/captions/proposal.json, blind to the caption already in gt/fig/, so the two can be compared. Use when re-reading the caption store, running the caption pass, or on /read-captions. Not the page-line ground-truth pass — that is rebuild-groundtruth.
---

# Read the figure captions off the sheets

**This is both the contract and the procedure.** Nothing is dispatched: there is
no agent, no queue, no claim. One session reads 33 sheets and writes one file.

## Why this pass exists, which decides how you must run it

`gt/fig/` already holds a ratified reading of all 395 captions, on the FigDesc
block that carries each one's geometry. This pass exists to produce a **second,
independent** one, so the two can be compared and a correction made on the
strength of the comparison rather than on trust.

`docs/decisions.md` records what a second witness is worth when it is not really
second: `gt/ocr/` and the caption text once agreed on three commas the machine
had invented, because both descended from the same recognizer pass,
and *only a fresh raster read separated them*. Nothing in either file recorded
the shared ancestor.

So: **a reading taken with the old file in view is not a witness, and the
comparison against it means nothing.** There is no hook enforcing this — a skill
has no `PreToolUse` guard the way an agent does. It is on you, and it is declared
in the file you write.

### Do not open, for any reason, before you have written the proposal

| file | why it is a witness |
|---|---|
| `gt/fig/` | the ratified caption you are being compared against. **Do not open it** |
| `docs/apparatus.md` | quotes the hard adjudications verbatim — the `seated`/`sealed` misprint, `1-049`'s dotted `g̣` |
| `data/loi.json` | the List of Illustrations. Book-internal apparatus **binds the adjudicator, not the reader**: completing an illegible word from it makes your proposal a paraphrase, and the List's captions are abbreviated anyway |
| `mz/tei/`, `tei/` | `<figDesc>` transcludes every caption into 205 generated pages |
| `review/<ref>/proposal.json`, `review/<ref>/decision.json` | the line pass's reading of the same pages, same shared ancestor |

Also out: `harness tei context` (prints captions), `harness zones edit`,
`harness edition serve`, `harness corpus figures`.

**If you have already opened any of them in this session, stop and say so.** The
pass needs a session that has not. That is not a formality — a contaminated read
produces a table that looks exactly like a clean one.

## The procedure

0. **Read `keying_spec.md`.** It is the character inventory and it binds this
   pass. Read it once, up front — it is not reproduced here, because a second
   copy of a spec is a copy that goes stale.

1. **Build the sheets.**

       uv run harness fig sheets --all

   33 sheets into `review/captions/sheets/`, ~12 strips apiece, plus
   `manifest.json` keyed `<ref>|<zone-suffix>` — the block-id suffix the store
   files each caption under, which is what lets the two be joined later.

2. **Read each sheet with `Read`.** Every strip carries its key in the left
   margin and two faint rules marking the **declared box edge**. The padding
   above and below is deliberate: the commonest defect in this store is a box
   drawn round the wrong number of printed lines, and a strip cut at the edge
   could not show you a line the box missed.

   - Text **between the rules** is the caption. Transcribe it.
   - Text **outside the rules** is context — body prose, the picture, a
     neighbouring column. Do not transcribe it. But if a line outside the rules
     is plainly part of the caption, that is a **segmentation defect**: record
     the caption as printed and note `ZONE TOO SMALL`.

3. **Write the file, once.**

   Accumulate every strip as you go and make a **single `Write`** of
   `review/captions/proposal.json` at the end. Do not `proposal set` a key at a
   time — that is 395 tool calls for a file you can compose in memory.

   ```json
   {"blind": true,
    "lines": {
      "1-151|002": {"text": "Fig. 30, a (60/3887 b), b (60/3889).  Iron\nHarpoon-Heads.  Length, 7 cm., 10.5 cm."},
      "1-049|004": {"text": "Fig. 1. Village Uñiˊsak.",
                    "resolved": "U+0303 combining tilde on n; U+02CA stress",
                    "note": "…", "class": "doubt"}
    }}
   ```

   - `blind: true` is your declaration that you kept the table above. Set it
     `false` if you did not, and say why in your report. `harness fig witness`
     prints it, so a contaminated run is visibly contaminated rather than
     silently indistinguishable.
   - **`text` keeps the printed line breaks as `\n`**, and keeps printed
     hyphenation at a break. Hyphens are load-bearing in this notation; joining
     is a rendering decision made downstream, not here.
   - **`resolved` is required on any caption carrying notation** — spell out the
     codepoints you meant. A combining mark that fails to render looks identical
     to its absence, and hand-typing one is easy to fumble into a lookalike; the
     field catches your own typing, because it and the characters can disagree.
     Only ~34 captions need it, and they are the ones worth the care.
   - `note` is free text; `class` is one of `doubt`, `semantic`, `print`,
     `draft`, `layout`, `artifact`.
   - **Write it indented — one field per physical line** (`json.dumps(…,
     indent=1)`'s shape, which is what every other store here uses). Not
     cosmetic: `corpus normalize` exempts the `note` and `resolved` fields from
     the §2.9/§2.10 spacing rules *by matching the shape of their line*, and it is
     allowed to do that only because these files put one field per line. Compact
     JSON puts a note on the same line as its reading, so a note that quotes a
     footnote marker or a doubled space is read as corpus drift — and `--convert`
     would rewrite your prose to match a rule about print.
   - **Do not indent a caption's continuation lines.** Where a printed line sits
     is the compositor's business; `save_decisions` strips it anyway, but the
     store should not need the fold.

4. **Gate it.** Two verbs, and they do different things — `captions` is the
   target's name, exactly as `1-151` names a page's:

       uv run harness corpus normalize review/captions/proposal.json --convert
       uv run harness proposal check captions

   **`corpus normalize` is what folds to NFD**, and `--convert` writes the fold.
   `proposal fix` does **not** fold the file: it applies one narrow correction —
   a single mark `resolved` names that `text` lacks, swapped for the single mark
   `text` has that `resolved` does not — and touches nothing else. Run it when
   `check` reports that mismatch, not as a normalisation pass.

   `check` verifies every key names a real `GraphicZone-FigDesc` in `gt/fig/`,
   cross-checks `resolved` against `text`, and runs the apostrophe and mark
   rules. Exit 1 means defects you must fix; advisories alone do not gate.

   `harness proposal codepoints captions` names every non-ASCII character you
   wrote, per key — a useful last look over the Tier-1 ones.

## Reading rules

**R1. Read what is on the sheet, not what a caption of this kind usually says.**
The book is not uniform: `1-037` prints its figure number *below* the title
rather than before it, plate figures restart at `Fig. 1.` on every plate, and ten
figures print no number at all. None of those is an error to be tidied.

**R2. Catalogue numbers: read them if you can see them.** The old store recorded
every AMNH number as `(??/????)` on the grounds that the denominators were
illegible at this resolution. **On these sheets they frequently are legible** —
`1-164`'s fig. 42 reads `60/3800` and `60/3801` plainly. Read what you can see.
Use `(??/????)` only where the digits genuinely are not resolvable, and note it.
Do not carry the old file's limitation into a reading meant to test it.

**R2a. Zoom only for a Tier-1 glyph, and only with `harness fig zoom`.**

    uv run harness fig zoom '1-049|006' --reason "the g in Nu?nligren — dot below?"

**Never `convert`, `magick`, PIL or a one-off crop script.** Hand-typed pixel
bounds name a region nobody can check and the wrong one the moment a coordinate
is fat-fingered; the verb magnifies the same block the sheet showed you.

The stipulation is a rule you keep, not a check that stops you: **34 of the 395
captions carry a Tier-1 glyph at all.** The other 361 are ordinary English at a
66-character median and are settled at 1× on the contact sheet — magnifying one
spends an image to re-read what you have already read. If the question is "is
that `g` dotted", zoom. If it is "does that say Harpoon-Heads", it does.

2× is the default and 4× the ceiling. At 300 dpi a character is ~30 px and every
ink pixel is already a 4×4 block, so past 4× a magnifier returns the resampler
rather than the page. Nothing sharpens or denoises: isolation is the benefit, and
filtering would manufacture evidence.

**R3. Never invent a codepoint.** The inventory is `keying_spec.md` — **read it
before you start**; it is one file and it binds this pass. If a glyph is not in
it, that is a finding: write what you see, describe it in `note`, and say so in
your report. Do not reach for a plausible Unicode character that is not
catalogued.

**R4. Apostrophes are stress marks** (`ˊ` U+02CA) in Tier-1 forms, ~99% of the
time. A dotted `g̣` is `g` + U+0323 COMBINING DOT **BELOW** — U+0121, the
precomposed dot-*above*, is a trap and is never right here. 34 of the 395
captions carry a Tier-1 glyph at all; those are the only ones where this matters,
and they are worth slowing down for.

**R5. English prose reproduces the print, curly quotes included.** The ASCII
policy is scoped to Tier-1 forms only.

**R6. Uncertain is a legitimate answer.** Prefer a `note` saying what you could
not resolve over a confident guess. Fluent nonsense is the failure this whole
project is organised against.

**R7. A strip that is empty, sideways, or plainly not type is a defect, not a
caption.** Record it with `ZONE MISPLACED` and move on. Do not transcribe the
picture.

## Adjudication keywords

A `note` may open with one of these, in caps. They are the closed set
`harness/captions.py` validates against. Two are terminal — the question is
closed and nothing downstream reopens it:

- `VERBATIM` — re-examined, reads exactly as recorded; what looked like a defect
  is what the printer set. Do not normalise.
- `MISPRINT` — re-examined, the reading stands, but the printed form is an error
  of the book's own. Recorded as printed, flagged as wrong.

The rest mark work outstanding: `KEYING REQUIRED`, `ZONE TOO SMALL`,
`ZONE MISPLACED`, `CONFLICT WITH THE LIST OF ILLUSTRATIONS`.

As a reader you may propose any of these in `note`. **Only a human ratifies one**
— your proposal is `#llm` until then, and it is the adjudicator in
`harness fig review` who makes it a ruling.

## What to report when you finish

- sheets read, captions written, and **whether you stayed blind**;
- every `ZONE TOO SMALL` / `ZONE MISPLACED` — these are segmentation defects and
  somebody has to fix a box;
- every glyph you could not resolve, and every case where you wanted a codepoint
  the inventory does not have;
- anything the book does that the rules above did not anticipate.

Do **not** run `harness fig witness` yourself and do not open `gt/fig/`
afterwards to see how you did. The comparison is a separate act.

