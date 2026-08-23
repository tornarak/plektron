---
name: train-ocr
description: Fine-tune, evaluate and install the text recognizer from gt/ocr/, and judge what it produces. Use when training a Brill-specific OCR model for the first time or retraining it, reading its CER against the stock recognizer, or deciding whether a keyed store is ready to train on. Not the keying itself — that is /rebuild-groundtruth, and this track consumes what that one ratifies.
---

# Train the recognizer (gt/ocr/ → a checkpoint → models/bogoras-ocr/)

    uv run harness ocr remark-eval --commit   mint or extend the split
    uv run harness ocr assemble               lay out train/bogoras-ocr/data/, report five commands
    <the five reported invocations>           compile ×2, train, test ×2; the user's terminal
    <copy the checkpoint into models/>        `ocr install` does not exist yet — see below

`train-zones` is the eldest sibling and most of its judgement carries. What
follows is what differs, and none of the differences are cosmetic — this is the
first track that fits a **recognizer** rather than a segmenter.

**Never launch the training yourself.** `assemble` reports complete, runnable
commands with this machine's device and worker count already in them; hand them
over. A run holds the GPU for hours.

## Where things stand

**Not trained.** The store is complete — 717 keyed pages, `ocr-mz: 0` — and the
training set is laid out. That is the whole of the state.

    645 train pages / 26 965 lines / 1 716 430 characters
     72 eval pages  /  3 073 lines /   197 709 characters
     22 ratified lines excluded (they live in gt/lines/, not in the ALTO)

The eval set is 26 / 26 / 20 pages across the three parts. When the first run
happens, record its numbers in `docs/pipeline.md`, which owns this track's
record; this file owns the loop.

## Why this track exists at all

The stock recognizer is not bad — it is **narrowly** bad, in four ways, all of
them systematic and all of them things a fine-tune fixes.

A 3-page smoke test against `catmus-print-fondue-large` (91 lines, 6 024
characters — **not** the baseline; that is reported command 5, over the whole
eval set) came back at 97.92% character accuracy, and its confusion table is the
argument for the whole track:

    13  ” → "         curly quotes straightened — §1 has English prose reproduce the print
    13  ɪ → i     ┐
     7  ˊ → '     │
     6  ˊ → /     ├─ the transcription inventory, read as the nearest ASCII sort
     6  ˊ → ’     │
     4  ◌̣ → (nothing) ┘
     3  Ч → H     ┐
     3  у → y     ├─ §2.7 pre-reform Russian, transliterated by shape
     2  к → R     ┘
     2  ¹ → 1         §2.10 superscript footnote markers, flattened

Two of those four are *not* accuracy problems in the usual sense. `ˊ → '` and
`” → "` produce text that reads correctly and is wrong at exactly the codepoint
this project's firewall is built around — fluent nonsense with the error signal
removed. `harness proposal marks`' `traps` arm exists because a human made that
same substitution twice, two hundred pages apart, and neither was findable.

## The three things that are not a segmenter's

**Line-level ground truth is enough, and this is why the track is possible.**
CTC aligns a variable-length output to a variable-length transcription by
itself; nothing here needs character boxes or word boxes. `gt/ocr/` was built as
a corrected reading store and is *already* a recognizer training set — an ALTO
whose every `TextLine` carries a polygon and a ratified `CONTENT` is a line
image paired with its text.

**The split unit is the page, and a line-level split is the one mistake that
would invalidate every number this track produces.** kraken's `--partition`
divides the pooled *line* set and every recipe online uses it. Lines off one
leaf share its ink weight, its wear, its bleed-through and the compositor's own
stick, so a model that has seen forty lines of a page has seen the conditions
under which the other ten were printed. The held-out figure then measures
memorising a page rather than reading a new one — **and measures it high**,
which is the direction nobody goes looking. `remark-eval` marks whole pages and
`assemble` always passes `-t`/`-e`, which is what turns `--partition` off
(kraken sets it to 1 when an evaluation set is named).

**It trains on `scans/w-figs-blotted/`, the exact mirror of `train-figures`.**
That track links the raw scan because the blot paints its target white; this one
links the blot because the blot is what `ocr predict` reads. Same rule, opposite
conclusions: a model is trained on the raster it will be asked to read. A line
polygon that runs up against an inset figure — `1-283` is the standing case — is
dewarped with that figure's ink in it on the raw page and with white in it on
the blot. `assemble` refuses a page with no blot rather than falling back.

## The store is the target, and two spec sections decide what that means

**§2.14 is load-bearing and must not be "fixed".** The store keys printer's
errors as printed, so a broken sort, a turned letter and a wrong fount are each
paired with the ink that actually produced them. Repairing one in `gt/ocr/` to
make the text "correct" would hand the model a picture of one glyph labelled as
another. This is the standing rule for the store anyway; here it also happens to
be what makes the store trainable.

**§2.15 is the one place the target deliberately differs from the ink**, and it
is small enough to leave alone. Diacritics are stripped from naturalised English
loanwords, so the model is shown `créole` and told `creole`. Measured over the
store: 47 `creole`, 11 `seance`, 11 `role`, 4 `naive` — 73 occurrences against
30 038 lines, under a quarter of one percent. Left as is, deliberately: §2.15
*defines the target output*, so training to it is training to the spec, whereas
a §2.14-style repair would contradict a rule the store is built on. If the first
run shows the model dropping acutes it should keep, this is the first place to
look — but do not pre-emptively carve it out.

## Two silent shrinks, and both have to be checked by hand

Neither fails. Both train on less than you think, which looks exactly like a
model that underperforms.

- **kraken drops a bad manifest entry with a log warning and nothing else.**
  `_validate_manifests` reads `-F`/`-t`/`-e` line by line, keeps what
  `os.path.isfile` accepts and logs the rest. A `.lst` written with the wrong
  relative prefix compiles a smaller dataset and exits 0. **Compare the line
  count `ketos compile` prints against `assemble`'s `train_lines`/`eval_lines`.**
  They should differ by nothing: `assemble` already excludes the empty lines
  that `--skip-empty-lines` would drop.
- **22 ratified lines are not in the ALTO.** A `gt/lines/` correction is a box a
  human drew over ink the segmenter left unboxed; `lines.page_lines` appends it
  at read time, so every other consumer in the harness sees it and
  `ketos compile -f alto` cannot. `assemble` counts them apart as
  `corrections_excluded` rather than folding them into a total — this is the one
  place in the harness where taking the merged view would overstate the set, by
  exactly the lines somebody went out of their way to add.

## The flags, and why they are not what you remember

All verified against `ketos --help` **and** kraken 7.0.3's own source in this
environment. Re-verify after any upgrade; the CLI was reorganized across the
3→5→6→7 majors and nearly every tutorial online is 4.x-era.

- **`-u NFD`, said out loud.** The corpus is NFD corpus-wide and `ketos` applies
  no normalization unless told to, so omitting this happens to work — until a
  store drifts, at which point two spellings of one glyph become two codec
  entries and the model learns both badly. **Never `NFKC`/`NFKD`:** they destroy
  `ᵋ` U+1D4B and `˙` U+02D9, two glyphs this model exists to learn.
- **`--resize union`, not `new`.** The default is `fail` and it would: CATMuS's
  codec has none of the inventory. `union` keeps every codepoint the base model
  reads and appends ours; `new` refits the output layer to this corpus alone and
  throws away the English competence that is the reason to fine-tune rather than
  start from scratch. kraken's installed `vgsl.py` trainer implements exactly `fail`, `union`
  and `new` — **the help advertises `add` and `both`, and `recognition.py`'s own
  mismatch error suggests `add`. Both crash**, the same trap `zones.assemble`
  records for `segtrain`.
- **`-s`, `-d` and `--workers` are group-level**, before the subcommand. On
  `ketos train`, `-s` means `--spec`, a network architecture. The device and
  worker count are read off this machine so the command runs as printed — the
  zone track's was once handed over without them and duly trained on kraken's
  default single loader worker.
- **`-e` takes a manifest, not a dataset.** Hence `data/eval.mft`, one line
  naming `eval.arrow`. The training set goes in as the positional argument and
  needs no wrapper.
- **Compiled to binary first.** `-f alto` trains directly and re-extracts and
  dewarps 30 000 line polygons every epoch. `ketos compile` pays that once.
- **`-B 8` is a starting point, not a measurement**, and is the first thing to
  lower if the run runs out of VRAM.
- **The trained model's filename carries its own score**, so command 4 names it
  with a glob: `ketos train` converts its best checkpoint to
  `best_{val_metric}.safetensors` and the name is not knowable until the run
  ends. Inside a fresh per-run directory the glob matches exactly one file —
  which is the other half of why each run gets its own directory. `ketos test`
  loads it through its non-`.ckpt` branch, which takes safetensors and
  `.mlmodel` alike.

## Reading the result

**The baseline is reported with the run and is not optional.** `assemble` emits
a `ketos test` for the fine-tune *and* one for `catmus-print-fondue-large`, over
the same eval manifest by the same command. A CER for a new model is not a
result on its own; it is a result against what the corpus is read with today,
taken the same way. Do not compare against the 97.92% above — that is three
pages.

**Read the confusion table, not just the headline.** A recognizer can gain a
point of character accuracy while getting worse at the four classes in "Why this
track exists": they are a small share of characters and the aggregate will not
show it. The question this model is being trained to answer is whether `ˊ`, `ɪ`,
`◌̣`, the Cyrillic and the superscript markers come back — check those rows
directly.

**Do not promote a prediction into `gt/ocr/` because a new model made it.** The
firewall is about provenance, not about accuracy: a model reading better is
still a model, and `#gt` is a human's ratification against the artifact. A
better recognizer makes `/rebuild-groundtruth` cheaper; it does not shorten it.

## `ocr install` does not exist yet

The sibling tracks install through a verb that scores a checkpoint, refuses it,
and writes a manifest recording the split, a corpus digest and the score. This
track has no equivalent, and it waits on the first run: nothing has been trained,
so there is no checkpoint to score and no evidence about what an install ought to
refuse. The segmenters' own refusal — a permuted class map — cannot arise here,
since a recognizer's codec maps codepoints rather than named channels.

Until then: copy the checkpoint into `models/bogoras-ocr/` by hand, **copy
`train/bogoras-ocr/data/*.lst` beside it** (or nothing can say later which pages
the model saw), and point `ocr predict --rec-model` at it. `train/` is pure
scratch and `assemble` clears it on every run.

## Do not

- Do not run the training commands yourself.
- Do not split by line, and do not use `--partition`.
- Do not link the raw `scans/` into `train/bogoras-ocr/data/` — that is the
  figure track's raster, and this one reads the blot.
- Do not repair a printer's error in `gt/ocr/` to improve the training text.
- Do not use `--resize new`, `add` or `both`.
- Do not read a headline character accuracy as success before the four failure
  classes have been checked in the confusion table.
- Do not let a better recognizer's output into `gt/ocr/` unratified.
