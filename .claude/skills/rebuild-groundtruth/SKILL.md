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

    uv run harness ocr gaps PP-NNN                   did the segmenter drop a line?
    uv run harness ocr adopt-gap PP-NNN VPOS         only if it did; see below
    uv run harness ocr sheets PP-NNN                 contact sheets, one call
    uv run harness ocr zoom  PP-NNN --only 7,20,22-26        the closer look
    (author review/PP-NNN/proposal.json)                 your reading
    uv run harness proposal fix PP-NNN                   catch a mistyped mark
    uv run harness corpus normalize --commit --path review/PP-NNN/proposal.json
    uv run harness corpus normalize --path review/PP-NNN/proposal.json
    uv run harness ocr review PP-NNN --serve                 human adjudicates
    uv run harness corpus normalize --path review/PP-NNN/decision.json   same gate, post-adjudication
    uv run harness ocr restore PP-NNN --force                preview: edits, drift, mismatch
    uv run harness ocr restore PP-NNN --force --commit        -> gt/ocr/

`--force` is in both lines because every page now holds text; see "Review and
restore" below. The ALTO verbs read `ocr/` by default — the read view over every OCR
store — so no `--from` is needed to reach a page's current geometry.

Everything the pass reads or writes lives in **`review/PP-NNN/`** — `proposal.json`,
`decision.json`, and the derived `sheets/ crops/ zoom/`. No verb needs telling where;
`--out` is for a one-off outside the pass. When a page is done, the images go with
`uv run harness ocr clean PP-NNN`, leaving the two authored files.

0. **`uv run harness ocr gaps PP-NNN` before anything else.** It reports ink on
   the raster that no `TextLine` covers — i.e. lines the segmenter dropped. This is
   the one defect class no later step can catch: whatever text is present is
   correct, so nothing disagrees with anything, and the page is simply short. Three
   of the 20 restored pages turned out to be missing a line, and all three were
   found this way or by accident, never by review. Costs 0.27 s.

   Expect a false positive on a page whose figure zones are not in `gt/fig/`, and
   read a hit as "look here", not "a line is missing" — a band is measured, its
   meaning is not. Running heads, folios and figure labels are all legitimately
   uncovered ink.

   **If a band is a real dropped line**, it cannot be fixed by keying alone:
   `restore` only writes `CONTENT` into lines that already exist, so the line has
   to be created first.

       uv run harness ocr adopt-gap PP-NNN 3018,3076

   appends an empty `TextLine` per named band, taking its geometry from the
   measurement. Then key those indices in the proposal exactly like any other line
   and run the loop out normally. Four things to know:

   - it writes **geometry only** — the `String` is empty, and text still arrives
     through `decision.json` → `restore`. Do not be tempted to put text here;
   - **the `VPOS` must be a measured band.** A hand-entered number is refused, and
     so is a band overlapping an existing line;
   - the new lines get a **`gap_` id prefix** and take the **highest indices**, so
     nothing is renumbered and the recovery stays visible in the ALTO. They still
     *display* in reading position;
   - **which bands are real lines is your call, and it is the only judgement in
     the step.** Name them one at a time and say why in the proposal's
     `segmenter_missed` block, which carries the measured geometry and the band it
     came from, parallel to `lines`.

   Between adopting and adjudicating, `restore` refuses the page ("N lines have no
   decision"). That is correct — a partial restore is ground truth with invisible
   holes — but it does mean a repair is one uninterrupted sequence, not two
   sessions.
1. **Read the whole page image first** (`scans/chukchi-PP-NNN.png`) for orientation:
   where the running title, folio, footnotes and any figure sit. ALTO order is not
   reading order — a running title often lands mid-sequence, which is why `harness
   lines` now emits in reading order while keeping the segmenter's index as the
   label. **Line labels are therefore not consecutive**, and that is the tell that
   the index is an identity: it is what `proposal.json` and `decision.json` are
   keyed by, and what `restore` joins on.
2. **`uv run harness ocr lines PP-NNN`** for the line table, then `ocr sheets
   PP-NNN` for the crops. The table's `index` is the key for everything downstream. **Read every
   sheet in full before zooming into anything.** The sheets are cheap and the plain
   read is what tells you which lines actually hold a doubt; zooming ahead of that
   either wastes a call on a line that turns out to be fine or, worse, anchors a
   reading before you've seen the word in its plain context.
3. **`uv run harness ocr zoom`** only for what the plain sheets left open, once you've
   read all of them. Select every line you mean to look at in **one call**; running
   it once per doubt costs more than the look is worth. **`--zoom 2` (the tool's own
   default) is the ordinary case** — not a call per line, and not an escalating
   series at several multipliers on the same lines. Escalate to `--zoom 4` only for
   one specific, nameable doubt the 2× pass left open (does this `g` carry a dot
   below; caron or breve; which small-cap; `a` or `ä`) — never as the default first
   call. If a doubt survives a 4× look, that *is* the answer: write it in `note` for
   the human. There is no tool above 4×, and there must never be an ad-hoc one —
   see "The instrument" below.

   `--only` takes the `index` column from `harness ocr lines`, not the printed
   item/number in the running text — conflating them wastes a call (`1-101`: zoomed
   ALTO index 19 meaning to inspect printed item "19.", a different line entirely).

   **Do NOT zoom by a factor of more than 4.** The smallest characters in the
   typeset are about 100 pixels tall by that point. There's no "detail"
   to be gleaned in higher levels, just increasing amounts of interpolation noise.

   **A page-wide reflex to zoom every Tier-1 line is still over-zooming**, even
   selected in one call. `1-053` (43 lines, dense gazetteer) got a 2× pass over
   nearly every notated line and read cleanly off the *sheets* alone before that —
   the 2× pass mostly confirmed what a careful sheet read already settled. `1-101`
   repeated this at larger scale (a dozen calls across five zoom levels over a
   59-line page) and it produced no benefit: every one of that page's real errors
   (see `keying_spec.md` §5) survived anyway, because the calls mostly
   re-confirmed already-legible text rather than targeting the classes that
   actually bite. Zoom earns its cost on a specific, nameable doubt (does this g
   carry a dot below; is this a caron or a breve; which small-cap is this; is this
   `a` or `ä`), not as a blanket second pass over every line merely because it has
   a mark.

   **`keying_spec.md` §5's classes are checklist items, not background awareness**
   — its own closing note names the actual lesson: a class named once and ranked
   "check hardest" has still been missed again on a later page, because naming it
   is not the same as checking every line for it. Run §5 as a checklist against
   every Tier-1 line, zoomed or not; zooming is for a doubt that checklist reading
   leaves open, not a substitute for it.
4. **Author the proposal.** One entry per line index, every line present.
5. **Start the review server yourself** and hand the human a URL — don't ask them to
   run a command. It serves on loopback only and blocks, so run it in the background:

       uv run harness ocr review PP-NNN --serve        (run_in_background: true)

   Then tell them `http://127.0.0.1:8731/` and report what you flagged and why. Use
   `--port` if 8731 is taken.

   **Do not manage the server's lifetime by hand.** The page has a **Done** button:
   it always saves first — including when nothing was edited, because "I changed
   nothing" is an adjudication and not the absence of one — refuses to stop if that
   save fails (the server is the only thing holding the decisions at that moment),
   stops the server, and replaces the page with a confirmation. So the background task **exiting is the
   signal that the review is finished** — you get the completion notification, and
   `restore` follows from it without asking "have you saved yet?".

   Never `pkill` it. Reaching for that means the human has to be interrupted to
   confirm a kill, and it was how this loop used to leave a server bound to a page
   that had since been restored — which is how a later save lands on stale text.
   Foreground is not an option either: a review can easily outlast the maximum
   command timeout, so background plus the Done button is the whole mechanism.
6. **`uv run harness ocr restore PP-NNN`** once they have saved — and **run it; a save is
   not the end of the pass.** `--adopt-gap` and the review server both leave the ALTO
   holding geometry with no text, so a page can sit adjudicated-but-unwritten and look
   finished from the outside: `harness corpus normalize` will keep reporting it, correctly,
   and the ground truth is simply not there yet. Saving is the human's step; writing
   it is yours. The server exiting (step 5) is the cue.

   `review/PP-NNN/decision.json`
   appearing (or changing) is the signal; the server prints one line per save, naming
   the actual edited/changed line numbers, not just a count. **When told a save
   happened, read that file** rather than re-deriving your own view of what went
   wrong — it already holds the adjudicated answer. Bare `restore` only previews —
   `edits` (the proposal-vs-decision diff, so no ad-hoc script needed),
   `geometry_drift`, `text_mismatch` — and writes nothing; re-run with `--commit`
   once the preview looks right to actually write `gt/ocr/`.
   Read that line: it reports lines edited *and* lines changed, and a large `changed` after
   light editing means a bulk overwrite, not work — see the browser warning below.

   **Read `edits` as the page's error profile, not only as a save-check.** It is the
   full proposal-vs-decision diff, which means it names exactly which class from
   `keying_spec.md` §5 (if any) each miss belonged to. A recurring class is the
   signal to strengthen that checklist further — §5's own text is itself the
   record of past diffs doing exactly that.

## The instrument

`harness ocr zoom` exists so that magnifying a line is never an ad-hoc crop script.
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
from halves. Escalate to 4× for one specific question and take the wrapping there —
4× is the ceiling stated above, not a soft default; there is no higher tier to
escalate to. `2-245` treated this line as license for repeated 6× calls (39 wrapped
strips) chasing a shape question further zooming could never answer — past 4× there
is no more source detail to buy, only interpolation. A doubt that survives one 4×
look is the proposal's answer: flag it in `note` for the human, don't spend more
calls on it.

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

## Error classes

**The checklist itself now lives in `keying_spec.md` §5** — moved there because it
governs the same misreading classes the collation pass hits keying Tier-1 spans off
the raster, not just this one. Read it in full alongside the rest of the spec before
a page's first line, and run it as a **per-line pass over every Tier-1 line**, zoomed
or not: a class named once is not the same as checked for on every line, and more
than one of §5's classes has been re-stated as "the one to watch" and then missed
again on a later page regardless. The `--margins` polygon-exclusion issue above is
the one class that stays here rather than in the spec — it's an ALTO segmentation
artifact of this pass's per-line crops, not a glyph-reading question, and has no
collation-side analogue since collation works from the full page image.

## The proposal file

`review/PP-NNN/proposal.json`. Every line index present, `text` mandatory:

```json
{"lines": {"22": {"text": "2. Čačanloˊrg̣ɪn (“cold udder [month]”).",
                  "resolved": "Č = C+U+030C … rg̣ɪn = r, g+U+0323, U+026A, n",
                  "note": "…"}}}
```

- **Don't reproduce a line's dot-leader typography** (`Term . . . . . . . Gloss`-style
  list filler). It carries no semantic content and isn't worth matching dot-for-dot —
  key the actual word and drop the separator run. `3-005`, a dense kinship-terms table,
  is the page that raised this.
- **`resolved` spells the codepoints out** for any line with notation. Write it as you
  read, not afterwards: a combining mark that fails to render looks exactly like its
  absence, and that is how a U+0323 was mis-keyed once already. It also catches your
  own typing, since the field and the character can disagree.
- **Run `uv run harness proposal fix PP-NNN` right after authoring.** It
  cross-checks every line's `text` against the codepoints its own `resolved` field
  names, and fixes the one unambiguous case — a single mark in `text` that `resolved`
  doesn't mention, paired with a single codepoint `resolved` names that `text` doesn't
  contain. This is exactly the ring-below-for-dot-below, diaeresis-for-caron class of
  typo that hand-typing a combining sequence produces, caught mechanically instead of
  by re-reading your own output and hoping to notice. Whatever it can't resolve
  unambiguously it still reports — read those by hand, since a guess there is exactly
  what the firewall's reasoning forbids. Re-run without `--fix` afterward: zero output
  is the signal you're done.
- **`uv run harness proposal codepoints PP-NNN LINE` names every non-ASCII
  character in one line's field** (`--field text|resolved|note`, default `text`) —
  glyph, codepoint, Unicode name. Use it to settle a doubt about what you actually
  typed, before `resolved` even exists to cross-check against. This is what a
  hand-rolled `python3 -c "...ord(ch)..."` loop was standing in for; it existed
  because this exact doubt — "is this really U+026A or did I type U+0131" — comes up
  on essentially every notated line, which is the definition of a recurring op that
  belongs in the tool rather than in a fresh one-liner each time.
- **`uv run harness proposal check PP-NNN --set LINE --field FIELD [--value TEXT]`
  writes one line's field**, value from `--value` or stdin, NFD-normalizing on write.
  Reach for this instead of `Edit` when a targeted text replacement in
  `proposal.json` keeps silently failing to match: the file has already been through
  `corpus normalize --commit` and holds NFD (`ñ` as `n`+U+0303), and a character you type
  by hand in an `Edit` call is ordinary NFC (`ñ` as one codepoint) — the two compare
  unequal even though they render identically, so the edit's `old_string` never
  matches and the tool reports a mismatch with no visible cause. `--set` sidesteps
  the whole class by construction, the same way `normalize.py` has one conversion
  point rather than trusting every writer to remember it.
- **`uv run harness proposal check PP-NNN --replace LINE --old X --new Y [--field
  FIELD] [--which all|first|last|N|N:M]`** swaps one or more occurrences of one
  string for another inside a single field, instead of retyping the whole thing.
  Reach for this over `--set` once a line is already written and only a character
  or two turns out wrong (an apostrophe that should have been U+02CA, say) —
  `--set` requires resending the entire field, and resending a 70-character line
  by hand to fix one glyph is exactly the situation that produces the *second*,
  unrelated slip while fixing the first, on a page that is otherwise clean.
  `--which` is 1-based, left to right: `all` (default) touches every occurrence,
  `first`/`last` the obvious ones, a bare number one specific occurrence, `N:M`
  an inclusive run. NFD both ends, same as `--set`, and refuses (rather than
  silently doing less than asked) if `--old` doesn't occur or `--which` names an
  occurrence that doesn't exist.
- **`note`** for anything an adjudicator would otherwise have to rediscover: material
  outside a polygon, a small-cap flattening, a speck you decided was not ink.
- A **`contamination`** block, always. Say whether the page is blind.
- **Footnote markers are keyed as the actual Unicode superscript digit** — `¹`
  U+00B9, `²` U+00B2, `³` U+00B3, `⁴`–`⁹` U+2074–U+2079 — never the plain ASCII
  digit. `2-244` line 1 got this wrong: `funeral.1` proposed, `funeral.¹`
  adjudicated. A plain digit reads as correct (it's the right number) so nothing
  mechanical catches it; only a raster comparison or a human pass does.
- **Run `uv run harness corpus normalize --commit --path review/PP-NNN/proposal.json`
  before serving the proposal, always — never skip it and never substitute a
  manual fix.** This is not only NFD/§2.9 spacing cleanup (composed input, French-
  spacing artifacts copied from the OCR text). It exists because your own output is
  probabilistic: the exact mistake `proposal fix` and `corpus normalize` catch
  mechanically — a wrong-but-visually-identical codepoint (`ı` U+0131 typed where
  the licensed `ɪ` U+026A was meant, a precomposed accented letter where NFD wants
  it decomposed) — is a mistake *you* are equally likely to make again if you "fix"
  it by hand or with an ad-hoc script, since it is the same generative process
  producing the same slip. A tool that mechanically re-derives the correct form
  cannot repeat that class of error; a re-read or a hand edit can, and has (`2-244`
  needed the same `ı`-for-`ɪ` swap corrected on 33 occurrences across nine words,
  by a single scoped substitution, not by hand-fixing each). Follow with the same
  command minus `--convert` (or `--check`), which exits 1 on drift. Scope to the
  one file with `--path` — a per-page step has no business touching the rest of
  the corpus, and `normalize` never writes at all unless `--convert` is given.
- **Run the same `normalize --path` check against `decision.json` too, once it
  exists** (after the human's review pass, before `restore`/`--commit`). The
  adjudicator can introduce the identical drift classes typing corrections in the
  browser — composed accents, French spacing, a stray lookalike — and `decision.json`,
  not `proposal.json`, is what `restore` actually writes to `gt/ocr/`. Cheap
  insurance for the file that becomes ground truth.

Once adjudicated, **do not rewrite a proposal's `text` fields** without recording the
original error count somewhere explicit. `edited` is computed against the proposal, so
revising it retroactively erases the measurement — which is how `1-074`'s was spent.

## Review and restore

The human's pass runs at `uv run harness ocr review PP-NNN --serve`. Lines carrying
notation are flagged conspicuously and walkable with alt-j/alt-k; that flag is a
**floor, not a census**, since `c` (English *sh*), plain `s`, `j` and `x` are inventory
members in unmarked ASCII. An unflagged line means nothing was detected.

`restore` refuses rather than guesses: a target already holding text (without
`--force`), any line lacking a decision, a line without exactly one `String`, or any
unlicensed mark in the adjudicated text. The last catches what a human pass *missed*
rather than what it never saw — on `1-073` review corrected two of three identical
errors and left the third, and the page read as done.

**This is now a revision pass, and `restore` says so.** Every page in `gt/ocr/` holds
text, so the rebuild it was written for is finished and the first refusal above fires
every time; `--force` is how a revision states its intent, and is required for one.
The report's `mode` field distinguishes the two cases: `restoration` when the
geometry came from some other store, `revision` when the source resolves to the
target — which under the default store it does, `ocr/<ref>` being a symlink onto
`gt/ocr/<ref>`. Reading a file you are about to write is safe here (the tree is
parsed whole before any write, and the write goes to a `.tmp` sibling), but it is a
different act from reconstruction and the report names which one ran.

Verify the report: `geometry_drift` and `text_mismatch` must both be empty.

## What you never do

- Write `gt/ocr/` or `ocr/` yourself **as a shortcut for the proposal → review →
  restore pipeline**. `ocr/*.xml` are symlinks into `gt/ocr/`, one store under two
  names, and an unconfirmed write into it destroyed 18 pages once. This is not a
  blanket ban on ever touching an already-restored file: `1-048` and `2-030` (the
  two pages that predate the pipeline entirely) got a direct, surgical
  straight-quote/content fix this way, each character raster-verified first via
  `harness ocr zoom` and each edit a targeted substring replace, never a hand-retyped
  line (retyping risks an NFD-vs-precomposed mismatch that silently passes a
  `repr()` eyeball check — verify with an in-string `.replace()`, not by comparing
  to a literal you typed).

  `--adopt-gap` is the one *tool* besides `restore` that writes there, and it is
  not an exception to this rule: it writes **geometry only, never `CONTENT`**, so
  text still reaches ground truth by exactly one path. If you ever find yourself
  wanting it to write text, that is the rule catching you, not a limitation.
- Normalize a Tier-1 form toward a plausible shape, harmonize it against a
  neighbouring page, or propose a sort the inventory has never attested.
- Take CATMuS as a witness to any glyph. It reads 0% of the inventory. It is evidence
  about line geometry and about English, and nothing else.
- Join crops through `detector_flags` line numbers. `context._lines_from_alto` drops
  empty lines, so its index is not the ALTO's; join through `harness ocr lines`.
- Trust the browser for the text in its own fields — see the session-restore guards in
  `harness/review.py`. If a save reports many lines changed after one keystroke, stop
  and recover from `.json.prev` or `<ref>.jsonl`.
- Commit a page without running `uv run harness corpus normalize`.
- Reach for a hand-rolled crop (a `python3 -c "...PIL..."` one-liner, or any script
  outside the harness) to re-check a glyph. `harness ocr zoom --zoom 4` already delivers
  every pixel of source detail there is — past it there is only interpolation, so an
  ad-hoc crop cannot see more than the tool already showed. Doing it anyway is a tell
  that you're fretting past the point of a real doubt: stop, and if the doubt is
  real, write it in `note` instead. If a genuine gap in the tool's coverage forces
  this, the fix belongs in `harness ocr zoom` itself (an option, e.g.), not a one-off
  script and not a workaround repeated next session.
- Write a `python3 -c "..."` one-liner to inspect or edit `proposal.json`/
  `decision.json` — `proposal codepoints LINE` names a line's non-ASCII
  characters, `proposal set LINE --field FIELD` writes one, and both exist
  precisely because the hand-rolled versions were written more than once in the same
  session (`3-003`: an `ord(ch)` loop to catch a typed `ı` where `ɪ` was meant, then
  a second `ord()` dump trying to work out why a hand-typed `Edit` kept failing to
  match — the cause was NFC-vs-NFD, invisible to eye and to `Edit`'s diff both).
  Two different failure modes, same root cause: a one-off script standing in for a
  question the harness should already answer. Note what this does *not* license:
  the `ı`-for-`ɪ` class is already caught by bare `corpus normalize` (report-only, same
  as every lookalike — see keying_spec.md §3), so seeing it there is not licence to
  write a bulk auto-replace tool for it, and a stress-mark-vs-apostrophe mixup is
  *never* a candidate for automation at all — which mark is meant depends on the
  licensing environment around each occurrence (§2.1), a reading judgement no script
  should make.
