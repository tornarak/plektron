---
name: rebuild-groundtruth
description: Read one page of Bogoras off the raster into a line-keyed reading proposal, then adjudicate and restore it as ALTO ground truth in gt/ocr/. Use for the ground-truth rebuild, the correction/review workflow, or /rebuild-groundtruth PP-NNN. Not the TEI collation pass — that is transcribe-page.
---

# Rebuild ground truth for one page (raster → proposal → adjudicated ALTO)

You produce a **proposal**: your reading of every line, keyed by ALTO line index.
A human adjudicates it in the browser and `restore` writes `gt/ocr/`. You never
write ground truth directly.

`keying_spec.md` governs what the characters are. Read §2 before your first page of
a session; it is the inventory, and §2.6's mark–base licensing decides cases the
raster cannot.

**The deliverable is the workflow, not the page count.** Recognition fine-tuning is
off the table and gloss review runs off TEI provenance, so these ALTOs train nothing.
What the exercise yields is the correction loop and the error profile. Judge a session
by whether the loop got better.

## Loop, per page ref PP-NNN

Refs are part + scan index (`1-073`), never a bare page number. Every step is
stateless, so a fresh session resumes wherever the last one stopped.

    uv run harness lines PP-NNN --sheets review/sheets   contact sheets, one call
    uv run harness zoom  PP-NNN --only 7,20,22-26        the closer look
    (author review/proposals/PP-NNN.json)                your reading
    uv run harness review PP-NNN --serve                 human adjudicates
    uv run harness restore PP-NNN                        -> gt/ocr/

1. **Read the whole page image first** (`scans/chukchi-PP-NNN.png`) for orientation:
   where the running title, folio, footnotes and any figure sit. ALTO order is not
   reading order — a running title often lands mid-sequence.
2. **`uv run harness lines PP-NNN`** for the line table, then `--sheets` for the
   crops. The table's `index` is the key for everything downstream.
3. **`uv run harness zoom`** for whatever the sheets leave open. Select every line you
   mean to look at in **one call**; running it once per doubt costs more than the look
   is worth.
4. **Author the proposal.** One entry per line index, every line present.
5. **Start the review server yourself** and hand the human a URL — don't ask them to
   run a command. It serves on loopback only and blocks, so run it in the background:

       uv run harness review PP-NNN --serve        (run_in_background: true)

   Then tell them `http://127.0.0.1:8731/` and report what you flagged and why. Use
   `--port` if 8731 is taken. Stop it when the pass is done; leaving a server bound to
   a page you have already restored is how a later save lands on stale text.
6. **`uv run harness restore PP-NNN`** once they have saved. `review/decisions/PP-NNN.json`
   appearing (or changing) is the signal; the server prints one line per save. Read
   that line: it reports lines edited *and* lines changed, and a large `changed` after
   light editing means a bulk overwrite, not work — see the browser warning below.

## The instrument

`harness zoom` exists so that magnifying a line is never an ad-hoc crop script.
Hand-typed pixel bounds are unauditable and name the wrong region the moment a digit
is mistyped; the verb takes its box from the same `line_box` the crops and the review
page use, so a zoom is the *same* region enlarged.

**`--zoom N` means N display px per source px, delivered.** A client shows ~1450 px
per image whatever you send it, so *source px per image × display px per source px is
a constant*: zoom picks a point on that curve and cannot buy detail. Every sheet is
padded to `ZOOM_CLIENT_W` so nothing is fitted on arrival and the number stays true.
To wrap **less**, lower the zoom (`--zoom 1` puts nearly any line in one strip). At
the 2× default a list line is one strip and a full-measure line three.

Wrapping is the cost that matters: a form seen only in halves is a reading assembled
from halves. Escalate to 6× for one specific question and take the wrapping there.

**`--margins` widens a crop to the PrintSpace, and it belongs on every page.** A line
polygon can exclude printed text belonging to the line, and what it excludes sits in
the margin, where vertical padding cannot reach because the omission is horizontal.
Attested: `1-074` prints `5.` and `9.` outside their boxes; `1-073` does the same with
its `5.` and strands the folio `51` outside *every* box on the page. Key that material
from the page and note that it was outside the polygon.

Crops are padded 10 px top / 18 px bottom. Not symmetric, and not adjustable per
page: a below-mark sits under the descender, further outside the box than an
above-mark sits over the ascender, and this padding was 4 px when `1-074` lost two
dots to it. It still clips anything two-deck — a stacked catalogue fraction — so go
to the raster there. See `keying_spec.md` §2.8; those are keyed `(??/????)` anyway.

## Error classes, in the order they actually bite

1. **Inference, not resolution.** The one measured error on a blind page was a mark
   read as a breve because it looked rounder than the page's `č`. The observation was
   real; the conclusion — that the notation contains both sorts — did not follow. More
   magnification cannot settle a question that is not optical, and examining it at 6×
   twice only made the wrong answer more confident. **If your reading contradicts
   `keying_spec.md`, say so plainly and prefer the spec.** A detailed, self-consistent
   note citing its own magnification is what a confident guess looks like. Citing the
   firewall to justify a novel sort inverts it: the firewall forbids *adopting* a glyph
   on a model's authority, and book-internal apparatus binds.
2. **Dropped marks below the baseline.** `g̣` / `G̣` (g + U+0323) is the class to check
   hardest; it cost `1-074` both its errors. Check every `g` in a Tier-1 form.
3. **`ɪ` (U+026A) vs `i`.** Dotless and x-height versus dotted. Both occur inside one
   word — `Imlɪˊrɪlɪn` is all `ɪ`, `yuˊᵋtir` is `i`.
4. **Old-style figures.** The numeral 1 is x-height and dotless and is easily taken
   for `ɪ`; zero is small and round. CATMuS reads `20th` as `zoth`.
5. **Text outside the polygons** — see `--margins` above.

## The proposal file

`review/proposals/PP-NNN.json`. Every line index present, `text` mandatory:

```json
{"lines": {"22": {"text": "2. Čačanloˊrg̣ɪn (“cold udder [month]”).",
                  "resolved": "Č = C+U+030C … rg̣ɪn = r, g+U+0323, U+026A, n",
                  "note": "…"}}}
```

- **`resolved` spells the codepoints out** for any line with notation. Write it as you
  read, not afterwards: a combining mark that fails to render looks exactly like its
  absence, and that is how a U+0323 was mis-keyed once already. It also catches your
  own typing, since the field and the character can disagree.
- **`note`** for anything an adjudicator would otherwise have to rediscover: material
  outside a polygon, a small-cap flattening, a speck you decided was not ink.
- A **`contamination`** block, always. Say whether the page is blind. Five refs are
  spent — `1-048`, `1-052`, `2-030`, `1-151`, and `1-074` (amended in place) — because
  their transcriptions were read openly, so agreement there measures nothing. On a
  clean ref, read into the proposal *before* opening any existing transcription of it.
- Flag rather than resolve. Where the letterform does not decide, say so and let the
  human rule.
- **NFD.** Your output will likely be composed, so run `uv run harness normalize`
  after writing, then `--check`, which exits 1 on NFD drift and on an unlicensed mark.

Once adjudicated, **do not rewrite a proposal's `text` fields** without recording the
original error count somewhere explicit. `edited` is computed against the proposal, so
revising it retroactively erases the measurement — which is how `1-074`'s was spent.

## Review and restore

The human's pass runs at `uv run harness review PP-NNN --serve`. Lines carrying
notation are flagged conspicuously and walkable with alt-j/alt-k; that flag is a
**floor, not a census**, since `c` (English *sh*), plain `s`, `j` and `x` are inventory
members in unmarked ASCII. An unflagged line means nothing was detected.

`restore` refuses rather than guesses: a target already holding text (without
`--force`), any line lacking a decision, a line without exactly one `String`, or any
unlicensed mark in the adjudicated text. The last catches what a human pass *missed*
rather than what it never saw — on `1-073` review corrected two of three identical
errors and left the third, and the page read as done.

Verify the report: `geometry_drift` and `text_mismatch` must both be empty.

## What you never do

- Write `gt/ocr/` or `ocr/` yourself. `ocr/*.xml` are symlinks into `gt/ocr/`, one
  store under two names, and an unconfirmed write into it destroyed 18 pages once.
- Normalize a Tier-1 form toward a plausible shape, harmonize it against a
  neighbouring page, or propose a sort the inventory has never attested.
- Take CATMuS as a witness to any glyph. It reads 0% of the inventory. It is evidence
  about line geometry and about English, and nothing else.
- Join crops through `detector_flags` line numbers. `context._lines_from_alto` drops
  empty lines, so its index is not the ALTO's; join through `harness lines`.
- Trust the browser for the text in its own fields — see the session-restore guards in
  `harness/review.py`. If a save reports many lines changed after one keystroke, stop
  and recover from `.json.prev` or `<ref>.jsonl`.
- Commit a page without running `uv run harness normalize --check`.
