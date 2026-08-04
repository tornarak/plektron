---
paths: harness/zones.py, harness/lines.py, harness/parallel.py, harness/recognize.py
---

# Zones and raster internals

Code-facing facts for the modules this rule is scoped to. The design
reasoning is `docs/segmentation.md`; the training loop is
`.claude/skills/train-zones/SKILL.md`.

**The page list (`l` in the editor) carries the ink verdict, and it is cached rather
than recomputed.** Every other column costs ~1 ms and is read straight off the files;
this one opens the raster and costs ~0.20 s, which over a 122-page itinerary is most
of a minute before the table appears. But the editor **already runs the check** on every
page it opens and every page it saves, and so does `harness zones check --ink` — the answer
was being computed and thrown away. It now lands in `gt/zones/_ink_cache.json`
(derived, gitignored), stamped with the mtimes of the page's ALTO and of
`_ink_exempt.json`, the two files that can change it.

Two properties follow, and the second is the point. An entry whose stamp no longer
matches is **unknown, not stale-but-usable** — a verdict about the page as it was two
saves ago, drawn in the same column as a live one, is exactly the fluent nonsense
this project is organised against. And a page nobody has checked reads `?`, never
blank: blank is indistinguishable from clean. Going and getting the missing ones is
an explicit button, because it is the only slow thing the list can do.

**What the raster check actually costs is the PNG decode**, and that is worth writing
down because it is not where the work looks like it is. Measuring — the column
anchor's ink profile, the row bands, the merge — is ~0.02 s. Inflating a 2824×3897
RGB PNG is ~0.16 s, eight times the rest put together. Two consequences, both taken:
`validate_page` decodes **once** and hands the same boolean ink mask to the anchor and
to the band detector, where it used to read the file twice; and `lines.ink_bands` is
vectorised, since a Python loop over 11 M pixels was the only thing that had ever made
the measuring itself visible. Together, ~0.58 s → ~0.20 s a page, with every verdict
over the keyed corpus unchanged and the 20 ground-truth pages still reporting zero
gaps. The sampling in `ink_bands` — every other column — is kept for exactly that
reason: vectorising made it free to drop, but dropping it would move a threshold
calibrated against the sampled count.

**That remaining 0.16 s was the format, not the check, and the format has been
changed** — `scans/` is greyscale now (see Source rasters), so the decode is ~0.03 s
and a page validates in ~0.05 s. This entry stood for a long time saying the change
was "recorded here rather than done"; it is done, and the numbers below are what it
was worth.

**The raster sweeps also run on a thread pool** (`harness/parallel.py`, `--jobs N`).
PNG inflate releases the GIL, so threads get most of the win without an interpreter
per worker — which is the trade that matters on the 4-core machines this has to run
on. `--jobs 1` builds no pool at all and is the control arm: every one of these was
diffed both ways and is byte-identical, `_ink_cache.json` included.

    zones check --all --ink   103.0 s -> 11.2 s     4 cores: 15.9 s
    zones blot --all          114.4 s ->  6.2 s
    zones paragraphs --all     87.9 s -> 10.9 s
    ocr gaps --all              4.2 s ->  0.7 s

**Two of those three gains were not the pool**, and that is the lesson worth
carrying: profiling first found `unlicensed_marks` asking a one-entry dict about
every character in the corpus (57% of `corpus normalize`, now 23× faster) and
`validate_page` re-reading all three split lists twice a page. The second was also
the GIL-bound share capping the pool's own speedup. `harness/parallel.py` records
this, along with the trap that cProfile's per-call overhead badly overstates
call-heavy code — it put that split-list read at 19% where the wall clock said 3%.

Three things about kraken 7.0.3 that cost time and will cost it again after an
upgrade, all recorded in `zones.load_segmenter`:
`TorchVGSLModel.load_model` is **CoreML-only** and fails a safetensors file inside
protobuf with `Wire format was corrupt`, which reads as a damaged model rather than
the wrong reader; its deprecation notice names `kraken.registry.load_model`, which
**does not exist in this version**; and `ketos segtrain` does not write the
`hyper_params` key that `blla.segment` then reads unguarded, so every model this
project trains raises `KeyError: 'hyper_params'` on its first inference —
`models/plates-seg-best.safetensors` is missing it identically. The working path is
`kraken.models.loaders.load_models`, plus setting that key empty to restore the
`padding = (0, 0)` the guarded branch would have given.

A fourth, on the recognition side: `rpred.rpred` is **deprecated and removed in
kraken 8**, and recognition now goes through `kraken.tasks.RecognitionTaskModel`
with a `RecognitionInferenceConfig` (`recognize.load_recognizer`). Two things
that cost time there. The config's `device` is **Lightning Fabric's**, not
torch's — it is handed straight to `Fabric(devices=...)`, so `"cuda:0"` fails
with `invalid literal for int() with base 10: 'cuda:0'`, naming neither the
field nor the model; `recognize._fabric_placement` translates. And
`no_legacy_polygons` was an argument to `rpred` and is a config field here, with
the default flipped between them — left unset, the slow polygon path silently
returns.

**Recognition is not where `ocr predict` spends its time, and the measurement is
worth keeping because it inverts the obvious fix.** A page is ~17 s:
`blla.segment` is ~15 s of it and recognition ~1.5 s. Nor is the segmenter's time
GPU work — profiled, it is scipy `correlate1d` (6.1 s), shapely `intersection`
(2.2 s) and kraken's own `boundary_tracing`/`moore_neighborhood` (3.2 s), i.e.
**baseline vectorization on one core**. That is what the ~4.5% mean GPU
utilization is: a brief forward pass, then a quarter of a minute of CPU. So
`batch_size` buys almost nothing — 17.4 s/page at 1 against 16.8 at 32.

**The GPU was never the constraint, so this sweep wants cores.** `ocr predict`
takes `--jobs`, and it is the one place in the harness where that means
**processes** rather than threads. Measured over 8 pages: 14.16 s/page serial,
7.89 with 4 threads, 5.14 with 4 processes — threads plateau at 4 and 8 is no
better, which is what a ~55% GIL-free workload does, the cost being scipy and
shapely with a lot of Python between them rather than one long C call. Through
the CLI, four pages went 75.3 s → 32.9 s including four model loads, output
byte-identical.

Two things that follow. `spawn`, not fork — a forked child inherits a CUDA
context it cannot use. And the default worker count is capped by **free VRAM as
well as cores**, since a worker holds ~1.4 GB of CUDA context (the recognizer's
weights are 22 MiB; almost none of it is the model). That cap is read off the card
at run time rather than written down, for the same reason the column measure is
derived: a constant here would be wrong on the next machine. A `--jobs` a human
types wins outright, including one that will not fit.
