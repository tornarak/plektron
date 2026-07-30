---
name: rebuild-groundtruth
description: Read one page of Bogoras off the raster into a line-keyed reading proposal, then adjudicate and restore it as ALTO ground truth in gt/ocr/. Use for the ground-truth rebuild, the correction/review workflow, or /rebuild-groundtruth PP-NNN. Not the TEI collation pass — that is transcribe-page.
---

# Rebuild ground truth for one page (raster → proposal → adjudicated ALTO)

You produce a **proposal**: your reading of every line, keyed by ALTO line index.
A human adjudicates it in the browser and `restore` writes `gt/ocr/`. You never
write ground truth directly.

`keying_spec.md` governs what the characters are. **Read the whole file with the Read
tool before your first page of a session — not `grep`.** It is short enough to read
whole, and it is dense enough that a grep for a term you already suspect will find
that term and miss the rest of the inventory next to it: the mark you didn't know to
search for, the licensing note that would have overridden your first guess, the
changelog entry recording that someone already made your mistake. A page keyed
against a partial reading of the spec is not different in kind from a page keyed
against no spec at all.

**The deliverable is the workflow, not the page count.** Recognition fine-tuning is
off the table and gloss review runs off TEI provenance, so these ALTOs train nothing.
What the exercise yields is the correction loop and the error profile. Judge a session
by whether the loop got better.

## Loop, per page ref PP-NNN

Refs are part + scan index (`1-073`), never a bare page number. Every step is
stateless, so a fresh session resumes wherever the last one stopped.

    uv run harness lines PP-NNN --sheets                 contact sheets, one call
    uv run harness zoom  PP-NNN --only 7,20,22-26        the closer look
    (author review/PP-NNN/proposal.json)                 your reading
    uv run harness proposal-check PP-NNN --fix           catch a mistyped mark
    uv run harness normalize --path review/PP-NNN/proposal.json
    uv run harness normalize --check --path review/PP-NNN/proposal.json
    uv run harness review PP-NNN --serve                 human adjudicates
    uv run harness restore PP-NNN                        -> gt/ocr/

Everything the pass reads or writes lives in **`review/PP-NNN/`** — `proposal.json`,
`decision.json`, and the derived `sheets/ crops/ zoom/`. No verb needs telling where;
`--out` is for a one-off outside the pass. When a page is done, the images go with
`rm -r review/PP-NNN/{crops,sheets,zoom}`, leaving the two authored files.

1. **Read the whole page image first** (`scans/chukchi-PP-NNN.png`) for orientation:
   where the running title, folio, footnotes and any figure sit. ALTO order is not
   reading order — a running title often lands mid-sequence.
2. **`uv run harness lines PP-NNN`** for the line table, then `--sheets` for the
   crops. The table's `index` is the key for everything downstream. **Read every
   sheet in full before zooming into anything.** The sheets are cheap and the plain
   read is what tells you which lines actually hold a doubt; zooming ahead of that
   either wastes a call on a line that turns out to be fine or, worse, anchors a
   reading before you've seen the word in its plain context.
3. **`uv run harness zoom`** only for what the plain sheets left open, once you've
   read all of them. Select every line you mean to look at in **one call**; running
   it once per doubt costs more than the look is worth.
4. **Author the proposal.** One entry per line index, every line present.
5. **Start the review server yourself** and hand the human a URL — don't ask them to
   run a command. It serves on loopback only and blocks, so run it in the background:

       uv run harness review PP-NNN --serve        (run_in_background: true)

   Then tell them `http://127.0.0.1:8731/` and report what you flagged and why. Use
   `--port` if 8731 is taken. Stop it when the pass is done; leaving a server bound to
   a page you have already restored is how a later save lands on stale text.
6. **`uv run harness restore PP-NNN`** once they have saved. `review/PP-NNN/decision.json`
   appearing (or changing) is the signal; the server prints one line per save. **When
   told a save happened, read that file** rather than re-deriving your own view of
   what went wrong — it already holds the adjudicated answer.
   Read that line: it reports lines edited *and* lines changed, and a large `changed` after
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
6. **Word stress (U+02CA ˊ) keyed as apostrophe (U+0027 ').** These are visually
   **distinct** printed symbols, not a shape call — read which one is actually on the
   page, the same as any other glyph. What makes this class worth naming: **every
   multisyllabic Chukchi/Eskimo/Koryak word carries a stress mark** (culminative, ≤1
   per word), so a native word of more than one syllable almost certainly has one
   somewhere, and a raised mark you're about to key as a plain apostrophe out of habit
   is far more likely the stress mark. On `1-052`, essentially every native word on
   the page (~40) was keyed `'` without this expectation in mind, and the actual
   symbol printed throughout was the stress mark.

## The proposal file

`review/PP-NNN/proposal.json`. Every line index present, `text` mandatory:

```json
{"lines": {"22": {"text": "2. Čačanloˊrg̣ɪn (“cold udder [month]”).",
                  "resolved": "Č = C+U+030C … rg̣ɪn = r, g+U+0323, U+026A, n",
                  "note": "…"}}}
```

- **`resolved` spells the codepoints out** for any line with notation. Write it as you
  read, not afterwards: a combining mark that fails to render looks exactly like its
  absence, and that is how a U+0323 was mis-keyed once already. It also catches your
  own typing, since the field and the character can disagree.
- **Run `uv run harness proposal-check PP-NNN --fix` right after authoring.** It
  cross-checks every line's `text` against the codepoints its own `resolved` field
  names, and fixes the one unambiguous case — a single mark in `text` that `resolved`
  doesn't mention, paired with a single codepoint `resolved` names that `text` doesn't
  contain. This is exactly the ring-below-for-dot-below, diaeresis-for-caron class of
  typo that hand-typing a combining sequence produces, caught mechanically instead of
  by re-reading your own output and hoping to notice. Whatever it can't resolve
  unambiguously it still reports — read those by hand, since a guess there is exactly
  what the firewall's reasoning forbids. Re-run without `--fix` afterward: zero output
  is the signal you're done.
- **`note`** for anything an adjudicator would otherwise have to rediscover: material
  outside a polygon, a small-cap flattening, a speck you decided was not ink.
- A **`contamination`** block, always. Say whether the page is blind.
- **NFD.** Your output will likely be composed, so run
  `uv run harness normalize --path review/PP-NNN/proposal.json`, then the same with
  `--check`, which exits 1 on NFD drift and on an unlicensed mark. Scope to the one
  file with `--path` — bare `normalize` walks and rewrites the whole corpus, which is
  the wrong blast radius for a single page's proposal.

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
