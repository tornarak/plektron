---
name: train-zones
description: Train, evaluate and install the page-segmentation model from gt/zones/, and run the diagnostics over it. Use when retraining the segmenter, judging whether a checkpoint is worth installing, reading a train/eval gap, deciding whether a class is too rare to keep, or auditing paragraph boundaries and line detection. Not the zone keying itself — a human does that in the browser editor.
---

# Train the zone segmenter (gt/zones/ → a checkpoint → models/bogoras-seg/)

Four commands, in order. Everything that used to be a rule you had to remember is
now a refusal, so this file is mostly about the judgement the tooling cannot make.

    uv run harness zones assemble           lay out train/bogoras-seg/, report the command
    <the reported ketos invocation>         the only slow step; runs in the user's terminal
    uv run harness zones install CKPT       preview: scores it, refuses a permuted map
    uv run harness zones install CKPT --commit

`zones assemble` computes the base model and whether `--resize` is needed, and
reports the invocation to run. **Run what it prints.** It is not a fixed template:
it picks `models/bogoras-seg/zones-seg.safetensors` over stock blla once one is
installed, it omits `--resize` when the class sets already match, it allocates a
fresh `run-N` output directory, and it fills in this machine's device and worker
count so the command runs as printed. It once did not, and the run that followed
used kraken's default **single** loader worker.

`zones assemble --scratch` trains from random init instead — no `-i`, kraken's
default spec. That is the one configuration in which the class-map permutation
cannot arise even in principle, because `--resize` is what renumbers an existing
output layer and there is no existing output layer.

`zones install` scores the checkpoint in memory against `gt/zones/`, **refuses a
permuted class map**, and copies the split beside the weights. Preview first;
`--commit` writes.

## Where things stand

**The store is complete** — 832 pages keyed, 717 of them text pages carrying 4598
zones, and 115 ruled leaves rather than text at all (44 `plate`, 42 `blank`,
21 `apparatus`, 7 `cover`, 1 `map`). Splits **580 train / 137 eval**. Every one of
those numbers is `zones check --all`'s summary, which now counts the kinds beside
the `exempt` total; read it there rather than from this paragraph, which has gone
stale twice. Class distribution is in
`zones check --all`'s `labels` summary; read it there rather than from any table,
which goes stale. (`--all` is the corpus form of every sweeping verb now — the
bare invocation that used to sweep is a usage error, so that a 832-page walk is
never something you did by leaving an argument off.)

The installed model is run 3: trained on 211 pages, held out on 60, and its
manifest records **95.2% recall / 80.1% precision on eval** at `>=30px` with the
raw decode. The same weights score **94.7 / 90.8** under the segmental DP decode
plus the paragraph split — different decoder, not a different model. Always
say which decode a number came from; the three differ by more than any retrain has.

**`MainZone-Quote` is withdrawn and the store holds none.** It sat at 25 instances
across two successive keying passes while everything else doubled, was folded for
training, and in the whole-book pass an editor retyped every remaining instance to
`MainZone-Other` — the distinction not being worth drawing. So `train_merges`'
entry for it is now a **no-op**, and the live consequence is good: the store's
class set is exactly the six the installed model carries, so `assemble` reports
`resize: (none needed)` and the permutation lottery is off by construction.

## What the tooling refuses, so you need not check

- **A permuted class map cannot be installed.** `--resize` renumbers the output
  layer and Python randomises string hashing per process, so a run can emit a model
  whose stored names do not match what its channels learned. The first one did: 0.2%
  agreement on its own training data, far below the ~14% of guessing among seven
  classes. `zones remap --commit` repairs it; `zones install` will not accept it
  otherwise.
- **A model cannot be installed without its split.** The `train.lst`/`eval.lst` it
  trained on are copied beside the weights, so `zones score --model X` reads *X's*
  split and cannot be handed whatever was last laid out.
- **`zones score` refuses when there is no split at all** (exit 2) rather than
  falling back to the live `gt/zones/` lists, which move as pages are keyed.
- **A ruled leaf is never scored.** A plate has no correct segmentation, so every
  region drawn on one is spurious and nothing can offset it. Seven plates ruled
  mid-session once took a split's precision from 79% to 53%, which reads as
  the model degrading when what changed was the denominator.
- **`train/bogoras-seg/` is scratch.** Nothing reads it after training. Clobber
  freely. `models/bogoras-seg/` is the tracked half and holds the artifacts.
- **`zones score` says when the corpus moved** under a model, rather than silently
  comparing against a reference that has changed.

## Read `split_from` before you read the numbers

**A bare `zones score` — no `--model` — takes its split from
`train/bogoras-seg/*.lst`, and `assemble` rewrites those whenever the next run is
prepared.** So after an assemble, the splits it labels its rows with are the *next*
run's, while `mz/zones/` still holds the *installed* model's predictions. Nothing
refuses this; the report names its source in `split_from` and that is the whole
mechanism.

It is not hypothetical — it is the current state of this repo. With the retrain
assembled, a bare score reports:

    trained-on   577 pages   98.9 recall / 97.0 precision
    eval         138 pages   97.5 recall / 92.4 precision

against an installed model that trained on 211 pages and held out 60. Roughly 366
of those "trained-on" pages it never saw, and the "eval" row contains pages it did
train on. The numbers are real measurements of nothing anyone asked about.

**So: `zones score --model models/bogoras-seg/zones-seg.safetensors` whenever you
want a figure about the installed model.** A manifest cannot be mis-attributed; a
working directory can. The bare form is for scoring the store's predictions as a
store, and its rows mean whatever `split_from` says they mean.

## The eval set, and why the current one can be believed

The split rows are:

    trained-on   the model saw these pages; agreement is the editor's judgement read back
    eval         the honest figure
    unseen       neither — and it is now empty, the whole book being split

**`unseen` was never held-out evidence, and it read exactly like it is.** After the
whole-book pass it reported 435 pages at 99.1 / 96.5 — better than the pages the
model trained on, which is not a thing a held-out set does. Most of those pages
were **adopted from `mz/`**: the editor's promote loop is how the book was keyed,
so gt on them *is* the model's own output with corrections, and a comparison
between them has one witness. The tell inside `score` was the median boundary
error, 0 px against 6 px on both other splits — independent keying cannot land on
the model's edges exactly.

That row is now 0 pages, so the trap is closed by arithmetic. But the same fault
reached the eval set itself, and the way it was fixed is what makes the current
number worth more than the old one:

- The first contamination check asked only whether a page's gt **differed** from
  `mz/`. A 5 px nudge satisfies that exactly as a redrawn page does, so it counted
  98 tidy-ups as independent judgements and pronounced the set 0% contaminated when
  about half of it was the segmenter's output with the edges pulled straight.
- Similarity cannot settle provenance, so the split was rebuilt **from git**: 310
  pages are byte-identical to their pre-adoption state, 237 of them not exempt, and
  the eval set is drawn only from those. Every eval page's labels predate the
  segmenter.
- Holding out all 237 starved part 1 down to 60 training pages, so its clean pool
  was sampled evenly to 100. Eval is **100 / 26 / 12 by part** — part 1's share is
  high on purpose, it being by far the densest in figures and irregular setting, so
  overrepresentation there is what a fair test of the hard cases looks like rather
  than a skew to correct.

**Nothing in a `gt/zones/` ALTO records whether a human drew the page or ratified a
proposal.** That is why provenance had to come from git, and it is the standing
limit: `score` cannot detect the collapse on its own.

## What else is yours to judge

**Read the train/eval gap, not the headline.** `val_mean_iu` in the ketos log is a
macro average over the region classes *plus two aux separator channels that are
permanently zero*, because `gt/zones/` carries no baselines at all. With six
classes it is hard-capped at 6/8 = 0.75 however perfect the regions are, and it is
**not comparable across runs whose class count differs** — run 2's 0.6204 and run
3's 0.6336 have different denominators. `val_accuracy` ~0.99 is meaningless: the
page is overwhelmingly background.

A small gap (a few points) is ordinary generalisation. A large one is memorisation.

**Expect diminishing returns from more of the same pages.** Run 3 added 121 pages
over run 2 and moved like-for-like eval by 0.2 points. `gt/seg`'s original 122 were
chosen for heterogeneity; a contiguous run of ordinary prose adds volume, not
variety. If a run is flat, the question is what kind of page is missing, not how
many.

**A class that never grows is a candidate for `train_merges`** — but check whether
the book has already answered before folding. `MainZone-Quote` is the worked
example in both directions: folding it into `MainZone-Other` raised held-out
precision 61.3% → 78.2%, and then the editor concluded the distinction was not
worth drawing at all and retyped the store. A fold is a claim about a model's
capacity; retyping is a claim about the book. Record the measurement in
`data/zones_config.json`'s `train_merges`, which is where a fold has to be
arguable, and note that a fold is applied by `assemble` when it writes the training
copies and **nowhere else** — `gt/zones/` keeps the distinction, because a human
drew it and it is evidence.

**Growing the eval set costs comparability.** It went 34 → 60 → 138, and each move
made the previous headline incomparable. Every one of those was a deliberate trade
for a better estimate. If you want a series, leave it alone; if you want a number,
grow it and say so.

## Reading a bad result

The failure modes are distinguishable and the tooling separates them:

| symptom | what it is |
|---|---|
| agreement *below chance* on training data | permuted class map — `zones remap` |
| `score` permutation `bijective`, not identity, holds out | same; the geometry was learned |
| high recall, low precision | over-segmentation — try `--decode dp` |
| low recall on eval, high on train | memorisation |
| flat across a retrain | the new pages add no variety |
| a split's precision collapses between runs | check `exempt_skipped` before the model |
| eval beats trained-on | check `split_from` — the rows may not be this model's |

**The decode matters more than the model has.** On identical weights: blob
vectorisation 61.3% precision, the segmental DP 80.1%, DP plus the paragraph split
90.8%. Two of those three gains cost no training at all. **`--decode` now defaults
to `dp`**; it defaulted to `raw` while this paragraph said to prefer `dp`, which
made the 30-point decode the thing you got by leaving an argument off — the hazard
`--all` exists to prevent, in the other direction. It cost a corpus sweep before
anyone noticed, because a `raw` file recorded nothing about its decoder and so was
indistinguishable from a `dp` one. Both arms name themselves in
`processingStepDescription` now, so ask a store rather than assuming it.

A healthy permutation block reads `bijective: true`, `is_identity: true`, and a
high `holds_out` — that is a correct map confirming itself, not a fault.

## Diagnosing a permuted class map

The invariant: a `class_mapping` that has been through `--resize` is not
trustworthy. This is how the first one was caught and repaired.

**0.2% agreement on its own training data** is the signature. Guessing among seven
classes gives ~14%, so far *below* chance is a wrong mapping, not a weak model — no
amount of undertraining does that. It was a 3-cycle and two swaps:

    MainZone-P → MarginTextZone-Notes → RunningTitleZone → MainZone-P
    MainZone-Continued ↔ MainZone-Other
    MainZone-Quote     ↔ QuireMarksZone

**Establish it rather than assume it.** `zones score` derives a 1-1 map on the
*training* pages and tests it on the *held-out* ones — 93.9% there, on zones it was
never fitted to. A permutation read off a set and scored on the same set agrees
with itself by construction, so deriving and testing on one split would prove
nothing.

`zones remap` inverts it: `new[T] = old[perm[T]]`, since a region truly of class
`T` surfaces on the channel currently named `perm[T]`, so that channel *means* `T`.
It refuses unless the map is bijective, holds out above 80%, and covers every
declared class; the original is kept as `.bak`. Note the identity is bijective and
holds out perfectly on a *correct* model, so `is_identity` is what separates them —
without it a fixed model reports its own correctness as the fault it just had.

**Fine-tuning from a permuted checkpoint is the dangerous move.** `--resize new`
deletes channels by *name*: with the map permuted, deleting `MainZone-Quote`
removed the detector that had actually learned `QuireMarksZone`. Run 3 was clean
only because `MainZone-Quote` happened to be the highest index, so removing it
renumbered nothing.

## The paragraph rule, and how it was got wrong

`docs/segmentation.md` states the structural fact: adjacent same-label zones are
42% of all boundaries and no model can produce them, so the ink has to. The rule is "a
paragraph's first line is indented", `indent_px: 40`. What follows is the
debugging, because every one of these was wrong first and each looked plausible.

- **Read the figure-blotted raster, not `scans/`.** A row counts as inked if any
  pixel is dark, so a figure welds every line it touches into one run — 722, 954,
  1556 px against a 49 px median. Recall 90.1% → 95.3%.
- **Clip the measuring window to the side the text wraps on.** Blotting paints the
  *declared* box and the declared box is not the whole illustration; a surviving
  rule spans the figure's width and reads as a 400 px indent. That, not the wrapped
  text, was 523 false positives.
- **Measure indent against the margin the page's body sets** — not the column edge,
  not the figure's bbox. A figure's box does not touch the type beside it, so
  measuring from it read the gutter as an indent on *every* wrapped line: `1-146`
  gave 41,42,42,42,41,41,41 on eight consecutive lines. A constant offset across a
  run is a margin; an indent happens on one line. This also makes the check
  independent of the column anchor, known to be 68 px out on `1-137`.
- **Pool that margin over the page, not the zone.** A zone whose head is flush left
  is its own minimum, so the head measured 0 against itself — 61 boundaries
  vanished and recall read 88.4% where it was 95.3%.
- **Take a low percentile of the strip's lefts, not their minimum** (`margin_pct`,
  25). The minimum is the one statistic a lone outlier owns outright, and a page
  reaches it with one speck: `1-160` sets prose beside a figure and scatters a
  dozen flecks down the gutter, 4-10 px each. `min_line_w_px` cannot see one, since
  the run it shares rows with is a whole line wide. The leftmost became the margin,
  every clean line read 40-47 px against the 40 px floor, and `tei generate` cut 20
  paragraphs into a page keyed as 3. **118 false positives → 25, at a cost of two
  boundaries.** The curve has a knee and the value sits in it — FP 118/46/33/28/25
  at pct 0/10/15/20/25 and flat thereafter (25, 24, 22 at 33/40/50), against FN
  53/55/55/55/55 then 56/58/62. Two refinements measured *worse* and are not in the
  code: a **rolling** margin tracking drift down the page (nothing at a 21-line
  window, recall lost at 11 — this book drifts between pages, not within one), and
  restricting the statistic to lines **justified to the measure** (18 more
  boundaries lost at the median, nothing at the quarter — a paragraph's last line
  is short and flush left, so it is one of the best witnesses to a left margin
  there is).

**A line's bounds are the union of its rows', and four ways of measuring them more
carefully were swept and all lost.** Worth the space because every one of them is a
reasonable idea, and because the failure has a single cause. A run's rows disagree
about where the line begins *bimodally*, not noisily: of a 50 px band ~22 rows are
x-height and start at the true left, ~14 are ascender rows starting at the first
tall letter, ~12 descender rows at the first descender, both often hundreds of px
in. Which side holds the majority moves with the letters each line opens with, and
that variance dwarfs the 40 px being looked for. Against the union's **25 false
positives at 96.8% recall**:

| bounds | recall | FN | FP | pages |
|---|---|---|---|---|
| union of rows | 96.8% | 55 | **25** | 23 |
| bucketed mode over rows | **99.5%** | **9** | 259 | 174 |
| median over rows | 99.6% | 6 | 1219 | 536 |
| mean over rows | 98.5% | 25 | 8375 | 682 |
| discount a leading run narrower than the gap after it | 98.7% | 22 | 340 | 257 |

The mode is the statistic the bimodality calls for and behaves accordingly — it
finds all but 9 boundaries in the corpus, the best recall of anything measured. It
is not in the code because the collation path spends false positives, not misses:
a spurious cut lands in a generated page. **If the decoder path is ever scored on
its own, the mode is where to start.**

**A minimum ink per row** (proposed as the anti-weld fix, and it is one) breaks the
welds the audit reports — 113 suspected merges → 9, `line_h_max` 586 px → 212 — and
lifts recall to 97.7%, because a weld hides the opening under it. It is also a
line-length filter, since a paragraph's short last line carries little ink per row
and drops out whole, and it took false positives 25 → 785. Raising it far enough to
clip the descender rows (128-256 px) does tame the mode/median, but by then recall
has fallen to 92-97%. Not in the code; the welds remain a known defect.

The threshold curve is flat from 30 to 80, so the residue is a separate population
rather than a tuning artifact. The **ragged right margin was measured and
rejected**: paragraphs that end flush make its p10 (24 px) overlap the mid-line p90
(21 px).

**Measure the page the rule produces, not where it fires.** Counting firings, 68
looked like errors; after consolidation 34 of 47 flagged pages came out
byte-identical to the keying because the cut folded straight back. The audit merges
each same-label run before the rule sees it, since that is the page a segmenter can
hand you — reproducing a boundary the input already contains would measure nothing.

**This check gates `gt/zones/` and nothing downstream of it.** `tei generate` used
to run it too — first cutting keyed bands, then commenting on them — and both put
a raster measurement into a file that is downstream of the zone store. Every
finding is answered *here*: a real one by splitting the band in `zones edit`, which
fixes the generated page and the segmenter's training data in one act, and the rest
by a ruling in `gt/zones/_para_exempt.json`. A ruled start still reports,
`kind: ruled` with its note, and is counted by `ruled` rather than
`false_positives`. Six are ruled so far, at 87-1262 px of indent on 279-1085 px ink
runs against a ~1740 px measure — none of them a paragraph, all of them worth
seeing.

**A line still at the zone's head is not a start inside it.** The first-line
exemption counts lines, and a sub-line of ink defeats it: on `1-075` the band opens
on 6 px of descender from the paragraph above, which takes the exemption as line 1
and leaves the paragraph's real opening line reporting as internal at the book's
own 107-110 px indent. That was **19 of 29 findings** over the corpus, and the tell
is that a page does not open two paragraphs sixteen pixels apart. A start within
`min_zone_h_px` of its zone's top is now skipped.

Over the complete store — 717 text pages, 1702 asserted boundaries — the rule
recovers **96.8%**, with 55 false negatives, 16 false positives on 14 pages, and 6
ruled.
The false negatives come pre-triaged and the three kinds want different fixes:
**37 flush left** (the book set no indent — nothing to find, and a line sitting
*left* of the margin is in here too), **13 slight indent** (under threshold, and
moving the threshold is what the flat curve says not to do), **5 no line detected
at all**. `false_positive` remains a **worklist, not a rate**:
gt cannot arbitrate a rule that corrects it, and of the first twenty found, fifteen
were keying slips and were fixed.

**Slivers consolidate, same label only.** A cut lands at the top of the opening
line, so leading whitespace is left as its own band. `consolidate: "down"` folds it
into the paragraph below. Within one zone's split every piece shares a label so the
rule costs nothing — which is why it is explicit: applied to decoder output, where
adjacent bands differ, an unguarded merge would retype a strip of page.

## Reading the line detector

`zones check REF --lines` dumps a page's lines of type — **one page only**, and it
refuses a second ref rather than picking one; the sweep does not offer it either.
A line here is a run of inked rows bounded by a blank one,
so **nothing accumulates** — but `h` is the tell for the two ways it fails, against
a 49 px median (p90 52):

- **~6-11 px** — a speck or a rule that passed `min_line_h_px`. Also caught by
  `min_line_w_px`, since five early false hits were 4-21 px wide.
- **~100 px and up** — two or three lines a descender welded. Corpus-wide this is
  113 suspects out of 28,807 lines, worst case 586 px; before blotting it was 173
  on a fraction of the pages.

A miss reported with **`h: -1`** means no line was detected there at all, which is a
different failure from "seen, under threshold" and wants a different fix. Read `h`
and not `indent` for this: both are -1 when nothing was found, but since the margin
became a percentile a real line can measure a *negative* indent by sitting left of
it — `1-160`'s fleck line reads -36 — and that is a page whose line detector is
working perfectly.

## Do not

- **Do not launch the training run yourself.** `assemble` reports a command; hand
  it to the user complete and let them run it in their own terminal. It is the only
  slow step and it holds the GPU for hours.
- **Do not fine-tune from a checkpoint in `train/`.** Use the installed model, or
  stock blla, or `--scratch`. A raw checkpoint's class map is unverified, and
  `--resize` deleting the wrong channel is how you lose a class you meant to keep.
- **Do not add `--resize` when `assemble` says none is needed.** That is what took
  the permutation lottery off the table for run 3, and the store's class set now
  matches the installed model's exactly, so it should stay unneeded.
- **Do not train on plates.** `assemble` already excludes every page carrying a
  leaf kind; a plate is neither an example of the layout nor a fair test of it.
- **Do not read a bare `score` as a statement about the installed model.** Pass
  `--model`, or read `split_from` and know what you are looking at.
