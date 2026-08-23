---
name: train-figures
description: Train, evaluate and install the figure/caption segmentation model from gt/fig/, and judge what it produces. Use when training the figure segmenter for the first time or retraining it, reading its per-class scores, deciding whether its negatives are trustworthy, or applying it to a book whose figures are only half annotated. Not the figure keying itself — a human does that in the browser editor's figure track.
---

# Train the figure segmenter (gt/fig/ → a checkpoint → models/bogoras-fig/)

Five commands. `train-zones` is the sibling and most of its judgement carries;
what follows is only what differs, and the differences are not cosmetic.

    uv run harness fig remark-eval --commit   mint or extend the split
    uv run harness fig assemble               lay out train/bogoras-fig/data/, report the command
    <the reported ketos invocation>           the only slow step; runs in the user's terminal
    uv run harness fig install CKPT           preview: scores it, refuses a swapped map
    uv run harness fig install CKPT --commit
    uv run harness fig predict --all          then `fig score`

**Never launch the training yourself.** `assemble` reports a complete, runnable
command with this machine's device and worker count already in it; hand it over
and let the user run it. It holds the GPU for hours.

**CKPT is `best_<score>.safetensors` in the run's own directory**, exactly as on
the zone track — `segtrain` names the file with the checkpoint's own accuracy, so
it is not knowable until the run ends. See `train-zones` for why that makes the
per-run directory load-bearing rather than tidy.

## Where things stand

**Not trained.** The store is complete and the training set is laid out — that is
the whole of the state. `gt/fig/` holds 252 pages, 415 pictures and 395 captions;
`remark-eval` has marked 606 train / 152 eval over 758 pages, of which 252 are
positives and 506 are witnessed negatives. `fig check --all` is clean at 0 errors
and 3 warnings.

When the first run happens, record its numbers in `docs/apparatus.md` — that file
owns this track's record, and this one owns the loop.

## The two things that are not the zone track's

**It trains on the raw `scans/`, and that is why it is a separate model rather
than more classes on `zones-seg`.** `zones assemble` links
`scans/w-figs-blotted/` so the zone segmenter cannot learn figure-shaped body
zones. The blot paints *this* model's target white. Two models reading two
rasters; neither can be folded into the other, and a copy-paste that linked the
blot here would train a network to find something that has been erased from its
input — which would look like a model that simply never learns, with nothing
pointing at the cause.

**Its negatives are derived, and they had to be witnessed.** A segmenter that
only ever sees pages with figures learns that every page has one, and two thirds
of this corpus has none — but "no figures here" is recorded nowhere. Absence of
the file *is* the record, and every reader takes an existing file as "this page
has figures", so `gt/fig/` never holds an empty ALTO. `assemble` synthesizes the
empty region sets into `train/` and nowhere else.

> **A negative is a keyed *text* page whose ink verdict is `clean`, with no
> `gt/fig/` file.** The ink check is the witness: every band of ink accounted for
> by text zones alone, so there is nothing left for a figure to be.

Both qualifiers are load-bearing, and both have live instances here:

- **A ruled leaf is never a negative.** The ink check never ran over one, and
  they are plates — exactly where figures live. 44 of the 252 positives are
  ruled leaves. Counting the rest as empty would teach the model that plates are
  blank. (The ruling disqualifies a page from being a *negative* only; a plate
  carrying figures is an ordinary positive and trains.) Asked through
  `zones.is_exempt`, so the whole leaf vocabulary is covered rather than one
  value — a `map` or a `cover` is no more a witness of emptiness than a plate is.
- **An excused band makes the page unknown, not clean.** A band ruled "not type"
  in `gt/zones/_ink_exempt.json` makes the check read clean while hiding exactly
  the ink a figure would be. Those pages read `ruled` rather than `clean` and are
  held out of both lists. The live cases are `1-033`, `1-035`, `1-036`, all
  "scanner artifact".

## Read the `unknown` count before the numbers

`remark-eval` reports three buckets and the third is the one to look at first.
The verdicts come from `gt/zones/_ink_cache.json`, which is **derived and
gitignored**, and a stale or absent entry reads *unknown* rather than clean.

**On a fresh clone that is every page in the corpus**, and the split would come
back tiny with nothing obviously wrong — a run that quietly trained on whatever
negatives it happened to find looks exactly like a run on a small corpus. If
`unknown` is large, the cache is cold: run `harness zones check --all --ink`,
then `remark-eval` again. Today it is 3.

## What the tooling refuses, so you need not check

- **`fig install` refuses a swapped class map.** With two classes the permutation
  test degenerates to a swap test, and it is still worth running: `--resize new`
  renumbers the output layer, and a model that learned "caption" on the channel it
  calls "picture" scores plausibly on counts while being wrong about every box.
- **`fig install` refuses if `train/bogoras-fig/data/*.lst` are gone.** The split a run
  consumed is frozen beside the model, or its scores belong to a division nobody
  kept.
- **`fig assemble` names its base model in the report.** With no blla and nothing
  installed it emits a from-scratch command, and says so — fine-tuning and random
  init are different experiments, and the one that arrives by a missing file is
  the one nobody chose.
- **`fig predict` will not overwrite without `--force`**: an `mz/fig/` file's
  processing step is the store's only witness to which model wrote it.

## Reading `fig score`

**Per split, never blended**, for `zones score`'s reason: agreement on the
trained-on pages is the editor's own judgement read back.

**Pictures and captions are scored apart.** They differ by an order of magnitude
in area, so one blended figure recall would be carried by whichever class is
commoner and would hide a model that finds every picture and no caption — the
likelier of the two failures, since a caption is a thin band of type and looks
more like body text than like a picture.

**Matched by area overlap, not by y.** The zone track pairs on vertical overlap
because zones are bands; that would call two side-by-side pictures one match.

**The negatives are their own bucket, and read it.** `spurious_on_empty` counts
boxes predicted on pages witnessed to have none. It is two thirds of the eval set,
so a model that hallucinates there while scoring well on the positives is both
possible and useless — the whole point of the negatives is that this number exists.

## Applying it to a book that is only half annotated

This is what the track is *for*; Bogoras's figures were already complete when it
was built, so the loop below has not been run in anger.

1. Key figures by hand in the editor's figure track until there are enough
   positives to train on, spread across the book rather than taken from the front.
2. `zones check --all --ink` first, so the negatives are real (see above).
3. `remark-eval --commit`, `assemble`, train, `install --commit`.
4. `fig predict --all`, then **open the pages in the editor**, where an `mz/fig/`
   page shows as a dashed proposal and promoting it is an explicit save.

**A prediction must not reach `gt/fig/` unread**, and the reason is sharper here
than on the zone track: `zones blot` paints `gt/fig/` boxes white into the rasters
the *zone* segmenter trains on. A wrong figure box does not merely sit there being
wrong — it teaches. That is also why there is no read view over `gt/fig/` and
`mz/fig/` the way `zones/` covers the zone stores.

## Do not

- Do not run the training command yourself.
- Do not link the blotted rasters into `train/bogoras-fig/data/`.
- Do not write an empty ALTO into `gt/fig/` to mean "no figures" — that is what
  `harness fig delete` is for, and what `assemble` synthesizes.
- Do not treat a page with unaccounted or excused ink as a negative.
- Do not read a clean `fig score` on the positives as a working model until
  `spurious_on_empty` has been read too.
