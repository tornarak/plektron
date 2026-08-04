# Page segmentation, second attempt

Moved out of `CLAUDE.md` whole; headings kept verbatim so citations resolve.
The train→score→install loop and its judgement live in
`.claude/skills/train-zones/SKILL.md`; the code-facing internals (ink cache,
raster costs, kraken traps, `--jobs`) load on demand from
`.claude/rules/zones.md` when the relevant modules are open.

**The first attempt is `gt/seg/` and it is not being extended.** 122 pages under the
full SegmOnto vocabulary, free polygons drawn around ink — and the faults recorded
throughout this file are its faults: whole printed lines dropped, captions found
where none exist, line polygons excluding their own text. The regions were only ever
used to impose a reading order, and CLAUDE.md has always said they carry no semantic
value.

The second attempt narrows the claim until it is checkable. Three things change:

- **Seven types, not fifteen** — running title / page number, paragraph start,
  paragraph continuation, block quote, footnotes section, publisher mark, other.
- **Zones are fixed-width bands of the text column, forming a vertical partition.**
  The measure is a property of the book — 1774–1797 px over the 20 line-precise
  pages in `gt/ocr/`, all three parts — so an editor supplies a top and a bottom
  and never an x. A whole class of error becomes unrepresentable rather than merely
  rare.

  **Where that column sits is *not* stable, and this is the finding the design
  turns on.** Measured off the rasters, the text's left edge drifts 399–760 px
  within part 1, 342–462 within part 2 and 310–546 within part 3 — up to 236 px
  inside one part, and up to 170 px between pages of the same scan-index parity.
  That is scan registration, not typography: the width barely moves while the
  position wanders. A per-part constant column was therefore wrong by ~104 px on
  `1-048` (it predicted 618..2410 where the page sets 722..2498), and verso/recto
  could not rescue it because parity explains only part of the drift. **The column
  is anchored per page off the raster's own ink profile** (`zones.measure_frame`).
  That removes the verso/recto distinction entirely — there was nothing left for it
  to do — and leaves a manual ±4 px nudge as the escape hatch for a page too blank
  to measure, plus per-ref `overrides` for two-column settings.

  **The anchor reads runs of inked columns, never the outermost inked column, and
  both halves of that were learned the hard way.** Density cannot find the edge:
  `1-033` carries a long stroke in its left margin whose densest column holds 774
  inked rows, *more than any column of type on the same page*, and a density
  threshold duly took it for the measure and put the column 52 px out. Width can —
  the stroke is a 10 px run against the block's 1746. But the surviving runs must
  then be **spanned, not picked from**: `1-022` is a chapter opening that fragments
  into nine runs whose widest is 863 px against a 1778 px measure, and demanding one
  run as wide as the measure sent it to the fallback 245 px out. So: drop runs under
  `min_run_px` as specks, take the span of the rest, believe it if it reaches
  `min_run_share` of the measure. Calibrated against **both** witnesses — 7 px
  worst-case over the 20 line-precise `gt/ocr` pages, 11 px over the 45 keyed by
  hand — because either alone would have missed one of the two failures.
- **Training runs on figure-blotted rasters** (`harness zones blot`,
  `scans/w-figs-blotted/`, painted **white** — `lines --blot`'s conspicuous pink and
  blue are for a human and would be a feature the model could key on). Whether a
  paragraph wraps around an illustration is a fact about the ink and not about the
  coding, so the figures come out before the segmenter ever sees the page. The
  declared box is painted and **not a pixel more**: 24 pages in a 40-page sample
  keep ink just outside a zone, but that ink is a few pixels of photograph edge on
  a plate like `1-167`.

Store is `gt/zones/`, ALTO in the eScriptorium dialect so it goes straight into
`ketos segtrain` and back into the GUI if ever wanted — the import/export loop being
the friction this replaces. It is **a separate store from `gt/seg/`, permanently**:
the label sets and the geometry regimes differ and nothing in an ALTO says which
scheme produced it, which is the same missing internal witness that cost 18 pages of
transcription. Blocks carry an `mz_` id prefix for the same reason.

**Every domain-knowledge assumption is a warning, and configurable.** `title-first`,
`rank-monotone` (running title → body → footnotes → signature line) and
`max-per-page` live in `data/zones_config.json` as declarative ranks, are exemptible
per page in `gt/zones/_rule_exempt.json`, and an exempted rule still reports — flagged,
never hidden, since the exemption file is exactly where a wrong call would hide.
Nothing in that config can refuse a save. What *can* is mechanical only: a width no
configured column offers, a zone shorter than a mis-click, two zones overlapping in
both axes, a label nobody declared, a polygon that is not its own bounding box.

**The two column checks are split by what they cost.** The **width** is knowable
from the config alone, so the corpus sweep tests it over every page for nothing and
it is what catches a hand-sized zone. The **position** needs the raster, so it waits
for `--ink` — and it is skipped where a per-ref override supplies its own columns,
since a two-column page's ~870 px columns are not the part measure and condemning
them would be the check misreading its own exception.

**The partition check is the one that reads the page.** `uncovered-ink` measures ink
no zone and no figure accounts for, through the same `lines.ink_bands` the
dropped-line detector uses, and it exists because a missing *zone* is invisible to
everything that reads only the file — exactly as a dropped *line* was. Adjacent
bands merge: an under-segmented `1-048` reported 38 of them, one per line of body
text, for a single missing region, and 38 lines of correct output is how a real
signal gets buried. It costs a raster read, so a single page always runs it and the
corpus sweep needs `--ink`.

**Three splits, not two.** `_train.lst`, `_eval.lst` and `_exempt.lst`, marked in the
editor and defaulting to train. `exempt` is the plates, maps, foldouts and blanks —
pages a human has ruled *not a text page*, which is a different statement from
"keyed and holds nothing" and a very different one from "not reached yet". They are
kept out of training and eval alike: a plate is neither an example of the layout nor
a fair test of it, and one in eval would report a model wrong about a page that has
no right answer. On a contradiction the most exclusionary list wins. An exempt page
is also not judged by the layout warnings, which describe a text page and would be
permanent known-false noise on a plate — but its mechanical errors still stand, or
the mark would hide a mistake rather than describe a plate.

**The training selection is `gt/seg/`'s 122 pages plus the first two chapters.** The
old attempt's page set was chosen for heterogeneity and that choice is still good
even though its labels are not, so `harness zones edit --itinerary gt/seg` walks
it. **That itinerary is now walked** — see below; together with the two chapters it
is the sample the first training run was meant to have. An itinerary is a
**work-list, not a filter**: a page not on it still opens and
still saves, it simply has no neighbours, and a scoped sweep reports the unkeyed
entries as rows so "how much is left" has an answer.

**The store is complete: all 832 pages keyed.** The counts, the splits, the
git-based eval rebuild and the withdrawal of `MainZone-Quote` are the training
loop's facts and live in `.claude/skills/train-zones/SKILL.md`; the class
distribution is `harness zones check`'s `labels` summary, never a table in a doc.

What the findings are worth, read against the scans:

- All three `uncovered-ink` bands — `1-033`, `1-035`, `1-036` — are **artifacts**: a
  margin smudge, the tail of an ink stain below a footnote zone, and a gutter blob.
  Binarization noise, not type. Report-only earns its keep here; any of them as an
  error would have blocked a correctly keyed page. All three are now ruled in
  `_ink_exempt.json` and still report, flagged and carrying their reason. `1-033`'s
  is now **stale** — the band no longer occurs since the anchor was rebuilt — and
  says so, which is the other half of that mechanism working.
- `1-033`'s four `column-position` errors were **the anchor's fault, not the
  zones'**, and fixing them rebuilt the anchor. See below.
- `1-137` is the anchor's fault too, and is **left standing**. Its column is 68 px
  out because fig. 21's photographic background extends left of the measure and sits
  near enough the block that `max_run_gap_px` bridges it into one 1817 px run —
  wider than the 1778 px measure, which is the tell nothing currently reads. Masking
  `gt/fig/` zones out of the anchor band fixes this page and breaks others: over the
  148 keyed pages, 5 better, **21 worse**, and `1-153` ceases to be measurable. A
  per-ref `overrides` entry would silence it, at the cost of switching off the width
  check on the one page whose column is known wrong. So it reports.

A caution recorded because it was nearly acted on: reading `1-035`'s band off a
downscaled crop, this assistant concluded the footnotes zone had clipped a second
footnote line and proposed extending it. The zone was correct — both notes sat
inside it and the band below was the stain's tail. **A band's reported width is the
bbox of ink across its rows and can span the measure while containing almost
nothing**, so it reads as a line of type in a thumbnail. Judge these at full
resolution against the zone edges, or not at all.

**Ink a human has ruled is not type goes in `gt/zones/_ink_exempt.json`**, scoped to
a band and carrying its reason (`{y0, y1, note}`) — `i` over the band in the editor.
Scoped rather than per-page because exempting a page's ink check would hide the next
genuinely dropped zone on it, and that check is the only thing that can see one. The
reason is required and is the record: this is where "the tool complained and I made
it stop" would otherwise be indistinguishable from a ruling. A matched band still
reports, flagged and carrying its note; a region that matches nothing any more
reports as `stale-ink-exemption`.

### The model exists, and so does a second store

`ketos segtrain` has run, three times. The installed model is
`models/bogoras-seg/zones-seg.safetensors`; the accuracy stays out of the filename,
since a default path that changes every retrain is a default nobody can use.
`harness zones predict` runs it.

**Two directories, and the split between them is the point.** `train/bogoras-seg/`
is scratch — the symlink farm, the two `.lst` files, each run's checkpoints — and
**nothing reads it once training ends**, so `zones assemble` may clobber it freely.
`models/bogoras-seg/` is tracked and holds the artifacts: the weights, the split
they saw as `<model>.train.lst`/`.eval.lst`, and a small `<model>.json` for the few
facts that are not lists. They used to be one directory, and the `.lst` files were
both the *next* run's input and the only record of what a *past* run consumed —
so preparing a run destroyed the ability to interpret the model already installed,
and `zones score` would read whichever lists happened to be lying there regardless of
which model it was scoring. Nothing detected that.

**Its output does not go in `gt/zones/`, and this is the store rule rather than a
preference.** Three directories, and the third is a view:

    gt/zones/     what a human has been through. Tracked.
    mz/zones/     what the model emitted. Derived, ignored.
    zones/        the read view over both, the human file always winning.
                  Derived, ignored.

Exactly the shape `ocr/` has over `gt/ocr/`, and for the reason that layout was
adopted: a file's role must not live only in the directory holding it, so the two
real stores never alias and the view is the only thing that joins them. **Reads may
resolve through `zones/`; writes name `gt/zones/`.** `save_zones` takes no store
argument at all — there is no parameter in which a caller could name somewhere else.

Four properties worth knowing before touching any of it:

- **`mz/` holds raw kraken output** — free polygons at whatever x the model drew, its
  own ids, its own ALTO dialect. Snapping to a configured band is a human act and
  happens in the editor. A store that normalised its own contents could no longer
  tell you what the model did, which is the only question it exists to answer.
- **A prediction is measured, never gated.** `harness zones check --store mz` runs the same
  checks and always exits 0; `--from gt` (the default) is unchanged and still gates.
  A raw polygon fails the fixed-measure width check by construction, so gating there
  would be permanent known-false noise — and a machine store could then block a build
  that has nothing to do with it. `--from` takes a closed set of two and deliberately
  **not** a free directory path, unlike `lines`/`zoom`/`review`/`restore`: a free path
  is how a check ends up compared against its own input, and checking through the
  view would blend ratified and unratified pages under one verdict.
- **The editor is the only route from one store to the other.** `/` and `?` cycle a
  store selector — `zones` (the view, default), `gt`, `mz`, and `paras` (gt with the
  paragraph rule applied, computed on open and stored nowhere) — **orthogonal to the
  itinerary**: the itinerary picks the pages, the selector picks whose reading of
  them you see. A pinned store holding nothing reports **nothing shown** rather than
  falling back, because "the model produced nothing here" and "nobody has keyed this"
  are both answers and a selector that silently redirected would merge them. `mz`
  shows as an *unsaved proposal*, opening clean so navigating past it writes nothing;
  promoting it takes an edit or an explicit save, and the save goes to `gt/zones/`
  whichever store was on screen — the shape `proposal.json` → `decision.json` →
  `restore` already has.
- **A prediction never satisfies `has_zones` on the default store.** Otherwise
  `zones predict` over an itinerary would mark the whole list keyed in one command and
  leave the next session with nowhere to resume.

**The sidecars stay `gt/`-only** — the three split lists, `_rule_exempt.json`,
`_ink_exempt.json`, `_ink_cache.json`. They record judgements about *pages*, not
about a store's files: an ink exemption rules that some mark on the paper is not
type, which is true whoever's zones are being measured against it, and there is no
such thing as the machine store's opinion of which pages are held out. The cache is
the sharper case — keyed by ref alone, so a machine verdict landing in it would sit
in the page list's column indistinguishable from one about work a human has done.

### Two structural facts about this store

**A page is a chain, and that licenses exact search.** Over the keyed corpus a page
is at most 13 bands, 545 boundaries abut exactly, 482 leave a small gap, and **2
overlap in the whole corpus**. So the decode is a dynamic program rather than
blob-wise thresholding, and the mechanical rules are built into it rather than
checked afterwards — an overlap and a sliver become unrepresentable. That also
settles the RL question: over a chain both the argmax and the normaliser are exactly
computable, so learning structure here would be a semi-Markov CRF, never policy
gradient.

**But the order rules are deliberately *not* built in.** `rank-monotone`,
`title-first` and `max-per-page` are warnings because the book breaks its own
conventions, and a decoder that could not violate them would make the warning
unfalsifiable — silently normalising exactly the pages it exists to surface. The line
is this file's own error/warning split: **a decoder may enforce what `validate_page`
calls an error, never what it calls a warning.** A test asserts it.

**Adjacent same-label zones are 42% of all boundaries** and no model trained on
this store can produce them — the paragraph-split mechanism, its calibration and
its `false_positive`-as-worklist rule are `.claude/skills/train-zones/SKILL.md`'s.
