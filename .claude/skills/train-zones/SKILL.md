---
name: train-zones
description: Train, evaluate and install the page-segmentation model from gt/zones/, and run the diagnostics over it. Use when retraining the segmenter, judging whether a checkpoint is worth installing, reading a train/eval gap, deciding whether a class is too rare to keep, or auditing paragraph boundaries and line detection. Not the zone keying itself — a human does that in the browser editor.
---

# Train the zone segmenter (gt/zones/ → a checkpoint → models/bogoras-seg/)

Four commands, in order. Everything that used to be a rule you had to remember is
now a refusal, so this file is mostly about the judgement the tooling cannot make.

    uv run harness zones assemble          lay out train/bogoras-seg/, report the command
    <the reported ketos invocation>          the only slow step
    uv run harness zones install CKPT      preview: scores it, refuses a permuted map
    uv run harness zones install CKPT --commit

`--assemble` computes the base model and whether `--resize` is needed, and reports
the invocation to run. **Run what it prints.** It is not a fixed template: it picks
`models/bogoras-seg/zones-seg.safetensors` over stock blla once one is installed, it
omits `--resize` when the class sets already match, and it allocates a fresh
`run-N` output directory.

`--install` scores the checkpoint in memory against `gt/zones/`, **refuses a permuted
class map**, and copies the split beside the weights. Preview first; `--commit`
writes.

## What the tooling now refuses, so you need not check

- **A permuted class map cannot be installed.** `--resize` renumbers the output layer
  and Python randomises string hashing per process, so a run can emit a model whose
  stored names do not match what its channels learned. The first one did: 0.2%
  agreement on its own training data, far below the ~14% of guessing among seven
  classes. `--remap-model --commit` repairs it; `--install` will not accept it
  otherwise.
- **A model cannot be installed without its split.** The `train.lst`/`eval.lst` it
  trained on are copied beside the weights, so `--score --model X` reads *X's* split
  and cannot be handed whatever was last laid out.
- **`train/bogoras-seg/` is scratch.** Nothing reads it after training. Clobber freely.
- **`--score` says when the corpus moved** under a model, rather than silently
  comparing against a reference that has changed.

## What is yours to judge

**Read the train/eval gap, not the headline.** `val_mean_iu` in the ketos log is a
macro average over the region classes *plus two aux separator channels that are
permanently zero*, because `gt/zones/` carries no baselines at all. With six classes
it is hard-capped at 6/8 = 0.75 however perfect the regions are, and it is **not
comparable across runs whose class count differs** — run 2's 0.6204 and run 3's
0.6336 have different denominators. `val_accuracy` ~0.99 is meaningless: the page is
overwhelmingly background.

The number that means something is `harness zones score`, per split:

    trained-on   the model saw these pages; agreement is the editor's judgement read back
    eval         the honest figure
    unseen       pages keyed since the run — the best evidence there is

A small gap (a few points) is ordinary generalisation. A large one is memorisation.
Run 3 measured 96.8/94.1 recall and 92.4/87.8 precision across train and eval, which
is the former.

**Expect diminishing returns from more of the same pages.** Run 3 added 121 pages
over run 2 and moved like-for-like eval by 0.2 points. `gt/seg`'s original 122 were
chosen for heterogeneity; a contiguous run of ordinary prose adds volume, not
variety. If a run is flat, the question is what kind of page is missing, not how many.

**A class that never grows is a candidate for `train_merges`.** `MainZone-Quote` sat
at 25 instances at 181 keyed pages and 25 at 345, while everything else doubled.
Folding it into `MainZone-Other` raised held-out precision 61.3% → 78.2%. The fold is
applied by `--assemble` when it writes the training copies and **nowhere else** —
`gt/zones/` keeps the distinction, because a human drew it and it is evidence. The
fold is a claim about a model's capacity, not about the book. Record the measurement
in `data/zones_config.json`'s `train_merges`, which is where a fold has to be
arguable.

**Growing the eval set costs comparability.** It was grown 34 → 60 during run 3, so
run 3's headline is not run 2's. That was a deliberate trade for a better final
estimate. If you want a series, leave it alone; if you want a number, grow it and say
so.

## Reading a bad result

The failure modes are distinguishable and the tooling separates them:

| symptom | what it is |
|---|---|
| agreement *below chance* on training data | permuted class map — `--remap-model` |
| `--score` permutation `bijective`, not identity, holds out | same; the geometry was learned |
| high recall, low precision | over-segmentation — try `--decode dp` |
| low recall on eval, high on train | memorisation |
| flat across a retrain | the new pages add no variety |

`--decode dp` decodes the page as a chain of bands rather than vectorising heatmap
blobs, and takes held-out precision 61.3% → 87.8% on the same weights. Prefer it.

## Diagnosing a permuted class map

CLAUDE.md states the invariant: a `class_mapping` that has been through `--resize`
is not trustworthy. This is how the first one was caught and repaired.

**0.2% agreement on its own training data** is the signature. Guessing among seven
classes gives ~14%, so far *below* chance is a wrong mapping, not a weak model — no
amount of undertraining does that. It was a 3-cycle and two swaps:

    MainZone-P → MarginTextZone-Notes → RunningTitleZone → MainZone-P
    MainZone-Continued ↔ MainZone-Other
    MainZone-Quote     ↔ QuireMarksZone

**Establish it rather than assume it.** `--score` derives a 1-1 map on the *training*
pages and tests it on the *held-out* ones — 93.9% there, on zones it was never fitted
to. A permutation read off a set and scored on the same set agrees with itself by
construction, so deriving and testing on one split would prove nothing.

`--remap-model` inverts it: `new[T] = old[perm[T]]`, since a region truly of class
`T` surfaces on the channel currently named `perm[T]`, so that channel *means* `T`.
It refuses unless the map is bijective, holds out above 80%, and covers every
declared class; the original is kept as `.bak`. Note the identity is bijective and
holds out perfectly on a *correct* model, so `is_identity` is what separates them —
without it a fixed model reports its own correctness as the fault it just had.

**Fine-tuning from a permuted checkpoint is the dangerous move.** `--resize new`
deletes channels by *name*: with the map permuted, deleting `MainZone-Quote` removed
the detector that had actually learned `QuireMarksZone`. Run 3 was clean only
because `MainZone-Quote` happened to be the highest index, so removing it renumbered
nothing.

## The paragraph rule, and how it was got wrong

CLAUDE.md states the structural fact: adjacent same-label zones are 42% of all
boundaries and no model can produce them, so the ink has to. The rule is "a
paragraph's first line is indented", `indent_px: 40`. What follows is the debugging,
because every one of these was wrong first and each looked plausible.

- **Read the figure-blotted raster, not `scans/`.** A row counts as inked if any
  pixel is dark, so a figure welds every line it touches into one run — 722, 954,
  1556 px against a 49 px median. Recall 90.1% → 95.3%.
- **Clip the measuring window to the side the text wraps on.** Blotting paints the
  *declared* box and the declared box is not the whole illustration; a surviving rule
  spans the figure's width and reads as a 400 px indent. That, not the wrapped text,
  was 523 false positives.
- **Measure indent against the margin the page's body sets** — not the column edge,
  not the figure's bbox. A figure's box does not touch the type beside it, so
  measuring from it read the gutter as an indent on *every* wrapped line: `1-146`
  gave 41,42,42,42,41,41,41 on eight consecutive lines. A constant offset across a
  run is a margin; an indent happens on one line. This also makes the check
  independent of the column anchor, known to be 68 px out on `1-137`.
- **Pool that margin over the page, not the zone.** A zone whose head is flush left
  is its own minimum, so the head measured 0 against itself — 61 boundaries vanished
  and recall read 88.4% where it was 95.3%.

The threshold curve is flat from 30 to 80, so the residue is a separate population
rather than a tuning artifact. The **ragged right margin was measured and rejected**:
paragraphs that end flush make its p10 (24 px) overlap the mid-line p90 (21 px).

**Measure the page the rule produces, not where it fires.** Counting firings, 68
looked like errors; after consolidation 34 of 47 flagged pages came out
byte-identical to the keying because the cut folded straight back. The audit merges
each same-label run before the rule sees it, since that is the page a segmenter can
hand you — reproducing a boundary the input already contains would measure nothing.
Current: 95.0% recall, 579 boundaries, 50 spurious on 13 pages of 271.

**Slivers consolidate, same label only.** A cut lands at the top of the opening line,
so leading whitespace is left as its own band. `consolidate: "down"` folds it into
the paragraph below. Within one zone's split every piece shares a label so the rule
costs nothing — which is why it is explicit: applied to decoder output, where
adjacent bands differ, an unguarded merge would retype a strip of page.

## Reading the line detector

`--lines` dumps a page's lines of type. A line here is a run of inked rows bounded by
a blank one, so **nothing accumulates** — but `h` is the tell for the two ways it
fails, against a ~49 px median:

- **~6-11 px** — a speck or a rule that passed `min_line_h_px`. Also caught by
  `min_line_w_px`, since five early false hits were 4-21 px wide.
- **~100-240 px** — two or three lines a descender welded. After blotting this is
  ~25 lines corpus-wide, down from 173.

A miss reported with `indent: -1` means no line was detected there at all, which is a
different failure from "seen, under threshold" and wants a different fix.

## Do not

- **Do not fine-tune from a checkpoint in `train/`.** Use the installed model, or
  stock blla. A raw checkpoint's class map is unverified, and `--resize` deleting the
  wrong channel is how you lose a class you meant to keep: with a permuted map,
  deleting `MainZone-Quote` removed the detector that had actually learned
  `QuireMarksZone`.
- **Do not add `--resize` when `--assemble` says none is needed.** That is what took
  the permutation lottery off the table for run 3.
- **Do not train on plates.** `--assemble` already excludes pages marked `exempt`; a
  plate is neither an example of the layout nor a fair test of it.
- **Do not read `bogoras-seg/`** — it moved to `train/bogoras-seg/`.
