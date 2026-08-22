# Apparatus stores: figures, List of Illustrations, Authorities

Moved out of `CLAUDE.md` whole; headings kept verbatim so citations resolve.
The pass-facing rules (figure anchoring, `tier1_terms`, `#gt`) are the
collation skill's; this file is the stores themselves and what building
them settled.

# Figure track

The 252 pages with figures have been segmented to isolate `GraphicZone`s and
`GraphicZone-FigDesc`s — **414 zones and 395 captions** in `gt/fig/`, one
`data/readings.md` block per caption, reconciled in both directions by `harness
corpus figures`. The images are cut by `harness fig crops` into `scans/fig-crops/`,
a derived tree — see "Cutting the pictures out" below.

## The store is boxes, and it says so

It was hand-annotated in eScriptorium with `models/plates-seg-best.safetensors`,
and every block carried a `Shape`/`Polygon` beside its `HPOS`/`VPOS`/`WIDTH`/`HEIGHT`
bbox. **395 of the 809 polygons were skewed quads or 5-to-9-gons that disagreed
with their own bbox, and nothing had ever read one**: every consumer of this store
goes through `figures.read_blocks`, which takes the bbox. So they were a claim
with no reader, and the migration (`tools/migrate_fig_bboxes.py`) wrote down what
was already being read. It refuses the whole run if any page's numbers move, and
none did.

Ids became `fig_PP-NNN_NNN` in geometric order, replacing eScriptorium's
`eSc_textblock_ca04178c`, and `data/readings.md`'s 395 keys moved with them in one
commit. **A block id's last field is a foreign key**, which is why `figures.
save_figs` preserves ids where `zones.save_zones` re-mints them by position:
inserting a picture above an existing one would otherwise renumber every block
below it and re-point every caption on the page at the wrong picture — silently,
since the file stays well-formed and `corpus figures` compares *sets* of suffixes,
which are unchanged. Only the pairing moves, and the pairing is what a caption is.

The reduction was verified behaviour-neutral three ways: `corpus figures`
identical either side, `corpus normalize` clean, and `zones check --all --ink`
over 832 pages **byte-identical** to its pre-migration capture — the figure boxes
feed that check's masks, so identical output over the whole corpus is the change
being invisible to the thing most able to see it.

## Writing it: the editor's figure track

`harness zones edit` carries a second layer, toggled with `b`. Figures and
captions are **freely-placed rectangles**, not the zone track's fixed-width bands,
and the difference is the whole reason they are a separate store: a zone's width
is a property of the book, so a hand-drawn one is a small lie the trainer learns,
while a picture's edges are a property of that picture and only the person looking
can supply them. The zone half's guarantee — *the client never sends an x* — is
therefore inverted here on purpose. Both are true; neither generalises.

Captions run on the way paragraphs do, and hand over exactly as much. The zone
chain gives the next zone its *top edge* and asks the human for the bottom; so
committing a picture arms the caption's **first corner** — the picture's
bottom-left, where the reading continues — and one further click puts the
opposite corner. `B` moves the corner to the top-right instead, for the ~19 plate
captions this book sets vertically beside their picture.

It armed a whole finished rectangle first, the picture's width and an assumed
height, and that was wrong twice over: captions here run from one line to five, so
the height was a guess; and a box that arrives complete has no handle, so
correcting it meant deleting it and drawing it again. A corner imputes nothing and
still saves the placement, which is the part that is actually predictable.

A committed box resizes by **eight handles**, not four corners, and that is the
substantive choice: a caption's height is the commonest correction — the box gets
drawn round the wrong number of printed lines — and only an edge handle changes
height alone. Handles are drawn on the hovered or selected box only, which is what
lets a plain drag keep meaning "draw a new box" everywhere else; the two gestures
never compete for the same pixels because the handle is not there until you are on
the box. Shift-drag moves the whole box. Dragging an edge past its opposite
normalises rather than clamps, so the gesture carries through the flip.

**Two ordering conflicts were resolved by rule rather than left to chance**, both
invisible when wrong. An armed caption corner and a resize handle both want the
next click, and the corner wins — it is mid-gesture and the handle is not; without
that, a caption whose opposite corner fell near an existing box would silently
refuse to finish. And a resize is *not* held to `min_size_px` the way a fresh box
is: the box already exists and was already accepted, so refusing to shrink it
would leave the hand stuck. `fig check` reports it as `tiny-picture` instead.

**Two tracks on one page had to stop competing.** A keyed page carries eight or
ten body zones against two or three figure boxes, so at equal strength the figure
track was unusable on any page with text on it. The inactive track recedes — two
configured amounts, since the layers are not equally in the way — and neither goes
to zero: where the text sits is how you judge where a picture ends, and a figure
you cannot see is a figure you will draw a zone over. **The unaccounted-ink
hatching is exempt and stays at full strength**, because on the figure track a
band no zone accounts for is very often the undeclared picture you are about to
draw. It is how `1-191` surfaced, and a test holds it outside the dimming group.

The mode itself needed saying four ways, and the reason is worth recording: the
visible consequence of switching tracks is that something *stops* — the zone
preview no longer follows the cursor — so silence read as the editor freezing.
There is a track pill in the topbar, the switch is narrated, the other track's
chips dim, and the pointer draws a **crosshair** rather than a single rule. That
last is not decoration: a zone takes only a y, so a vertical guide on the zone
track would advertise a freedom the page does not have.

A save sends the figure list **only when that layer was touched** — `zones blot`
keys the zone segmenter's training rasters off `gt/fig/` mtimes, so rewriting the
store during ordinary zone keying would stale everything that model learns from.

**`1-191` is what the track was built for.** Its photograph (y≈953–1379) sat as
unaccounted ink in both `zones check --ink` and `ocr gaps` with no tool able to
declare it a figure — the page already had four blocks, so it was incompletely
annotated rather than absent. Declaring it silenced both detectors **with no
change to either**, since both already masked through `gt/fig/`; corpus-wide the
ink sweep moved by exactly that one line. It also exercised the id rule on live
data: the photograph sorts above all four existing blocks and took `fig_1-191_005`,
so both captions still key to `003` and `004`.

## What the checks say, and what they refuse to

`harness fig check` splits **three mechanical errors** — a label the store does
not declare, a polygon that is not the rectangle its own bbox claims, a box off
the raster — from configured, exemptable warnings.

`picture-overlap` and `tiny-picture` were written as errors first, on the zone
track's model, and that was **importing a rule from a geometry regime that does
not apply**. A zone store partitions the page and its zones form a chain, so an
overlap there is unrepresentable and can be refused. Figures are freely placed: an
inset sits inside the frame it insets, two pictures on a plate may abut, and a
14×38 px box is suspicious rather than impossible. Over the migrated store the two
produced exactly three findings — `1-189` and `1-334` (marginal grazes, 1244×14 and
12×782 px) and `2-085`'s 14×38 px block — every one a real thing to look at, and
not one a thing the store must refuse to hold. A gate a human cannot honestly
clear is a gate that gets widened until it says nothing.

**`2-085`'s speck has since been keyed out**, so `tiny-picture` now has no live
instance and `fig check --all` reports the two overlaps alone. That is the
argument above finishing rather than being overturned: the warning was looked at,
the box turned out to be dirt the segmenter had boxed, and it was withdrawn by a
human. Had it been an error the page would have been ungateable until someone
did that — which is the same act, extracted under duress and at the wrong moment.

### `data/figure_numbers.json`: where a printer beat the derivation

Two rules stand between a picture and its printed number. `refs.figure_number`
reads the number off the caption, and the pairing decides from the page's geometry
which picture a caption belongs to. Three figures in this corpus defeat one or the
other, and **the answer is not to widen the rule**: a derivation loosened to admit
one odd leaf mis-fires on the several hundred ordinary ones, and it does so
silently, which is exactly the failure this project is built against. So they are
keyed by hand instead, one entry per number, each naming the leaf and the picture
zones it is and recording in `why` what the rule saw.

- **fig. 1** on `1-037`, the distribution map, whose printer set the number after
  the title and the attribution — `… by W. Bogoras and W. Jochelson. Fig. 1.` —
  so the caption parses no number at all.
- **figs. 239 and 240** on `2-068`, two pictures standing side by side above two
  stacked captions. The pairing read both pictures as one two-box figure under the
  upper caption, which left 239 holding a picture that is not it and 240 the
  corpus's one caption with no picture. Which is which was settled from the
  pictures: 004 is the carved wooden figure with the bead and fur tassel, 002 the
  long hatched strap with thongs and beads — the leather ornament.

`figures.by_number` applies the table after the fold, and a patch **replaces** its
number's derived entries rather than joining them; otherwise correcting 240 would
have made 239 ambiguous by leaving the swallowed picture on it. `fig check` gates
the table against `gt/fig/` on every run, for the reason `#gt` and `#mz` are
re-derived: the patch's whole licence is that a human looked at that leaf, so it
must fail rather than go stale when the leaf is re-boxed.

### The source's own segmentation, which is a fourth kind of evidence

The scans are MRC-layered — a bitonal master plus separate embedded JPEGs — so the
scanner recorded, when the book was digitised, which pixels it took for photograph
and which for type. `tools/extract_scans.py` writes those rects to
`data/pdf_images.json`, and **that is a witness neither a person nor a model
produced**. `figures.fig_ink` compares it against `gt/fig/` on the model of the
zone track's uncovered ink, with two departures each worth its line.

**Accounted for means overlapped, never contained**, and the measurement forced it.
Of 371 photographs, 255 merely *partially* overlap their best-matching keyed box,
86 are contained by it and 17 contain it: the rect stands a pixel or three proud of
what a hand drew. A containment rule reports **131 findings on a store that is
complete**. Overlap reports the truth, which is **0 unaccounted photographs and 0
pages carrying one with no figure ALTO at all**. That number is the strongest single
statement this track can make about itself, and it was got by choosing the right
comparison rather than by keying anything.

**It computes live and caches nothing.** `zones.cached_ink` exists because uncovered
ink is "the one check that reads the raster"; this one reads a small tracked JSON,
so a cache could only go stale.

A companion warning, `picture-outside-boxes`, reports how much of a rect falls
outside every keyed box, and **never gates**, because a large share means one of two
things and neither is a fault in the keying. It is a figure the book letters *a, b,
c*, whose one photograph spans several part-boxes with gutters belonging to no box —
14 of them. Or the rect is not a boundary at all: on `1-287` it runs to x=2190
across a rotated caption sitting at 2098..2206, because the scanner swept the
caption into the photo layer. Growing the box onto that would pull the caption
inside the picture, so the page is ruled rather than fixed.

**Which is why the exemptions now carry their reasons.** `gt/fig/_rule_exempt.json`
held bare rule ids until this pass — a record that somebody silenced a warning and
nothing about why, which no later reader can tell from a keystroke. It is
`{ref: {rule: ruling}}` now, `set_rule_exempt` refuses a blank one on
`zones.set_ink_exempt`'s rule that "a reason is required and is the point of the
file", the editor prompts and declines to exempt without an answer, and the ruling
prints *with* the finding rather than in a file you would have to go and open. A
legacy noteless entry still loads and still excuses — the human did rule — but
reports `unruled-exemption` so the gap is visible rather than inherited.

### `fig extend`: growing a box onto its photograph

Where a box stops inside its photograph, the blot used to paint around an
antialiased rim of halftone. `harness fig extend` closes that by growing the box to
the union with the rect — **union only, never intersection**, because some figures
carry line work *outside* the JPEG (rules, lettering, a plate border, all living in
the master) and contracting would uncover them. 85 of the 371 boxes were already
larger than their photograph, which is that rule earning itself 85 times.

**1:1 correspondences only, and that is the verb's scope rather than a stage of
it.** For the 14 lettered figures there is no correct mechanical answer — unioning
each part with the spanning rect makes them duplicates and destroys the grouping
`figure_boxes` folds on, while apportioning it invents boundaries the source does
not draw. They report `out_of_scope` and stay there.

**`--max-growth` has no default and `--commit` without it is a usage error.** The
ceiling is a judgement about how far a mechanical rule may move a rectangle a person
drew; a default would make that judgement silently and then let it read as the
operator's. A report run prints what every box would gain and the distribution it
falls in — p50 +0.59 %, p90 +1.74 %, max +9.81 % over the 272 that moved.

The guard is a **caption-assignment diff**, and the shape of it is the lesson.
`_gap` pairs a picture to a caption by *direction* first — a landscape caption must
sit below its picture, a rotated one to its right — and distance second, so a
caption between two plates can only ever be claimed by the one before it. That is
what makes growth safe. But the first version compared whole `paired` rows, which
carry a top-to-bottom `index`, and refused `1-167`, `1-227` and `1-325`: three
plates where every picture kept its own caption and two boats merely swapped
ordinals after a 12 px growth. **Compare the assignment, not the ordering** — a box
that now starts higher genuinely does start higher.

## The segmenter, and why its negatives had to be witnessed

`harness fig` carries the zone track's quartet — `remark-eval`, `assemble`,
`predict`, `score`, `install` — so a future book can be annotated by hand for a
while and finished by a model. It is a **second model rather than four classes on
`zones-seg`** because the two read different rasters: zones-seg trains on
`scans/w-figs-blotted/` so it cannot learn figure-shaped body zones, and the blot
paints *this* model's target white.

A segmenter that only ever sees pages with figures learns that every page has one,
and two thirds of this corpus has none — but "no figures here" is recorded
nowhere. Absence of the file *is* the record, and every reader takes an existing
file as "this page has figures", so an empty ALTO would assert the opposite of
what it means. Negatives are therefore derived, and they need a witness:

> **A negative is a keyed *text* page whose ink verdict is `clean`, with no
> `gt/fig/` file.** The ink check is the witness — every band of ink accounted for
> by text zones alone, leaving nothing for a figure to be.

Two clauses are load-bearing and both have live instances. **Ruled leaves are
excluded** because the ink check never ran over them and because they are plates,
exactly where figures live: 44 of the 252 positives are ruled leaves, and counting
the rest as empty would teach the model that plates are blank. (The ruling
disqualifies a page from being a *negative* only; a plate carrying figures
is an ordinary positive and trains.) The test is `zones.is_exempt`, so the whole
leaf vocabulary counts — a `map` or a `cover` witnesses emptiness no better than
a plate does. And a page whose ink was **excused** reads
`ruled`, not `clean`, and is *unknown* rather than negative — an exemption makes
the check read clean while hiding exactly the ink a figure would be. The three
live cases are `1-033`, `1-035` and `1-036`, all "scanner artifact".

Measured: **252 positives, 506 negatives, 3 unknown.** The unknown count is always
reported, because the verdicts come from the derived, gitignored
`gt/zones/_ink_cache.json` where a stale entry reads unknown — on a cold cache
that is every page, and a run that quietly trained on whatever it found would look
exactly like a run on a small corpus.

The empty-page question was checked against kraken 7.0.3 rather than assumed: an
empty-region ALTO parses to a `baselines` container with no regions, and
`BaselineSet.add` accepts it as a page with none.

`score` matches by **area overlap, not by y** — zones pair on vertical overlap
because they are bands, and that would call two side-by-side pictures one match.
Pictures and captions are scored apart, since an order of magnitude in area
between them would let one carry a blended figure recall; and pages witnessed
empty are their own bucket, so a model that hallucinates on them cannot hide
behind the pages that have figures.

**Not yet trained.** The store is laid out (606 train / 152 eval) and the command
is `harness fig assemble`'s to report; the run itself, and the scores it earns,
belong here when it has happened.

**A total that matches is not coverage**, and this track is where that was learned:
the count sat at 250 pages while two were missing, because 250 was also what the
List of Illustrations implies, and the two absences cancelled exactly against
`3-006`/`3-007`, which carry a zone and no caption and are not LoI pages at all.
Only the per-entry check catches that. **It is a check somebody ran by hand and
no code performs** — `figures.reconcile` opens `gt/fig/` and `data/readings.md`
and never `data/loi.json`, so nothing re-runs this and nothing would notice it
ceasing to hold. Writing it waits on chapter assembly, because an LoI entry
places a figure by *folio*; `docs/open-questions.md` carries the reasoning.

What that hand check found, as a record of one moment rather than a live
result: every LoI text-figure
**1–302** has a reading, no reading cites a figure number outside the LoI, and all
**35 plates I–XXXV** are located. 91 LoI plate segments map to 93 caption blocks,
and all four deviations are known — Plate II (the LoI makes the shared "Anui Fair"
its own segment where the page prints it twice) and Plates XXXII/XXXIII/XXXIV (four
printed figures against three segments, two sharing a caption on each).

## Cutting the pictures out

`harness fig crops` writes one PNG per `GraphicZone` into `scans/fig-crops/`,
named `chukchi-PP-NNN-KKK.png` after the zone's own id suffix. 414 files, a
registered farm (`views check fig-crops`), derived and gitignored.

**Cropped from `scans/` at 300 dpi, and a photograph's crop is still a 2× of a
150 ppi original** — the master is the *type* layer and the photographs are
separate embedded JPEGs at their own resolution. What changed with the raster
rebuild is that the doubling is now **nearest at an integral scale** rather than
poppler's resample, so every native JPEG sample survives as an exact 2×2 block and
the crop and the embedded original are the same pixels at two sizes. Nothing is
recoverable by cutting from the JPEG instead: side by side at 1:1 there is nothing
in one that is not in the other, and the difference was always interpolation blur
rather than detail.

The tree is **72 MB over 414 files**, halved by the rebuild because a line-art crop
is now bitonal. Worth stating plainly, since it was 142 MB and the temptation is to
blame the source: for `1-037`, the crop is 1027 KB as PNG, 409 KB as JPEG q88 at
the same pixels, 140 KB downsampled to 150 ppi, and 107 KB as the embedded original.
**Most of that spread is the encoder, not the source.**

Their bboxes matching the embedded JPEG dimensions was once noted here as a free
check that stayed available. It is no longer merely available — see
`unaccounted-picture` above, which is that check, run.

**Cutting from the embedded JPEG instead was designed and not built**, and the
reason it was dropped is worth more than the option: once the composite pastes each
photograph nearest at its integral scale, a native crop and a composite crop are the
*same samples* at two sizes. A `--source native` flag would therefore buy file size
and nothing else — and the encoder comparison above shows the size is mostly the
encoder anyway. A second source path through `crop_source`, with its own fallback
for the pictures the PDF never separated out, is not worth a saving that re-encoding
would get for free.

**Named by zone suffix, not by figure number.** Plate figures restart at 1 on
every plate and collide with the text-figure series; 10 figures print no number
at all; and a number is a *reading* of the caption where a zone id is the store's
own foreign key — the one `figures.save_figs` preserves where `zones.save_zones`
re-mints. Not a page-local ordinal either, which this file already records
failing twice.

**One crop per box, never a union of the boxes under one caption — and this was
got wrong first.** The book calls `1-276`'s fig. 140 *one* figure and letters its
parts *a* and *b* inside a single caption, so cropping the group as a unit looked
right, and the measurement agreed: 16 figures corpus-wide are multi-box and the
worst union is only **1.75× the area of its parts**. The output refuted it. Fig.
140's two boxes are stacked at different widths, so their bounding rectangle
spans the text column beside the upper one, and the crop came out with six lines
of body prose in it. **1.75× of *area* was 1.75× of *page*, and the page there is
text.** A bounding box over boxes a human drew separately is a region no human
drew, which is the whole reason this store holds rectangles rather than one box
per figure. Holding a figure's parts together is presentation: `figures.
figure_boxes` groups them under their one caption and every crop carries its
`group`, so a reader stacks them under a single caption without re-deriving
anything. The lesson generalises past figures — **an area ratio is not a content
check, and neither is any aggregate**; the only thing that caught this was
looking at the picture.

**Pad 0**, the blot's rule and for its reason (`docs/pipeline.md`): the pad was
rejected because body text sits hard against an inset figure on `1-283`. The
opposite choice from `lines.line_box`, which pads `PAD_X = 56` on purpose, a line
crop being for a human to read *in context*. A crop newer than both its inputs is
left alone, `lines.write_line_crops`' rule, so a rebuild does not hand every file
a new `ETag`.

## Enhancement is manual, and has a tracked home

Nothing in the crop path sharpens, denoises, upscales or otherwise improves a
picture — a crop is the raster's own pixels inside a box a human drew, and a test
asserts it against a gradient where any resample would show. An enhanced figure
is a **new artefact somebody made and vouches for**, which is a different kind of
thing from a mechanical derivative and gets a different kind of home.

That home is **`gt/fig-img/chukchi-PP-NNN-KKK.png`, tracked**, and
`figures.crop_source` resolves it ahead of the machine crop for every consumer.
The split is the whole safety property: `harness fig crops` rewrites everything
in `scans/fig-crops/` and nothing in `gt/fig-img/`, and it reports a `human`
count so a rebuild can never quietly shadow the work.

**Touching up a file in `scans/fig-crops/` instead would destroy it** at the next
`--force`, in a tree git does not carry — this repository's one catastrophic
failure exactly, where a file's role lived only in the name of the directory
holding it. `gt/` is what a human has been through; that is what the directory
means and it means it here too. Named `fig-img/` rather than `figs/` because the
latter sits one character from the `gt/fig/` geometry store, the same near-miss
`_exempt.lst`/`_exempt.json` was renamed to avoid. That pair is gone now — the
split lists are named for the kinds (`_plate.lst`, `_blank.lst`, …) and the order
rulings are `_rule_exempt.json` — but the lesson outlived both names.

**A whole leaf gets the same treatment, one level up.** `gt/page-img/chukchi-PP-NNN.{svg,png,jpg}`,
**tracked**, resolved by `edition_ui.leaf_source` with the rank travelling as
`crop_source`'s does. Two boundaries beyond the crop store's: it is **reading
view only**, never `zones.scan_for`, because a sharpened leaf is manufactured
evidence and must not reach anything that measures ink; and it is **exempt pages
only**, a file for a page the pipeline still owns being reported rather than
quietly honoured. `docs/edition.md` has the rest.

### A leaf is delivered as two layers, and neither is the artefact

`1-361`, part 1's foldout ethnographic map, is the leaf the store was built for.
`tools/extract_scans.py` writes it as one of three masterless RGB leaves — a
single 150 ppi photograph at its own size, 1833x1994, which is thin for a sheet
carrying several hundred toponyms in 6 pt. The master in `gt/page-img/` is a 2x
ChaiNNer upscale of it, hand-repaired afterwards where `2_MangaScaleV3`
hallucinated halftone into the legend swatches and turned the Yukaghir key
orange. Nothing here rebuilds that, which is the whole reason it is in git: a
vouched-for artefact a clone does not get is not vouched for, `data/geo/`'s
argument exactly.

It is also 21 MB, which is not a thing to hand a browser, so
`tools/build_leaf_layers.py` splits it into **Mixed Raster Content** — the
decomposition DjVu and JBIG2-in-PDF make, arrived at here independently and then
recognised. It works because the sheet's two kinds of information have opposite
statistics: linework is high-frequency and one bit deep, colour is low-frequency
and needs no edges at all. An anti-aliased linework PNG over a colour JPEG at a
third scale is ~1.6 MB, and every village name in both insets survives, because
the lettering never has to survive downsampling — only a brightness threshold,
which it does trivially.

**Vectorizing the linework was tried and abandoned, and the reason is not the
one it looks like.** A first trace came out 2.6 MB of pixel-staircase polygons,
and the obvious diagnosis — wrong tool for a halftone — was wrong, the linework
having been correctly isolated to binary first. The real limit is that **on this
sheet the village names are the same size as the grain**: every speckle filter
that removes the paper texture removes the lettering with it, measurably —
at `-f 8`, `Nuté-pínmin` traced as `Nu é p m n` and `Kuluči Pilhin` as `Ox`.
They are not separable by size, so the work would have to happen upstream in the
threshold, and the raster does the job today.

**What the split knowingly drops** are the coloured underlines marking
town-sized ethnic enclaves. They are thin by construction, which is the one thing
a closing is defined to remove. Accepted deliberately: those groups' areas of
settlement are discontinuous, so the value is nearly always inferable from
context, and the master is one click from the page. Recorded here rather than
left for somebody to discover while assuming the derivation was lossless.

**The reading view shows the pair and links all three addresses** — what is
shown, the master it was built from, and the raw scan neither may change.
`edition_ui.leaf_layers` returns **both layers or neither**: half a pair still
renders and still looks like the map, colour alone being a smear with no names
and linework alone an outline with every ethnic area gone, and a confident wrong
picture of an ethnographic map is this project's own failure mode.

**"Opp. page" is what the List of Illustrations heads its plate column, and the
number is not the plate's folio.** A plate is an inserted leaf with no folio of
its own; `loi.json`'s `opposite_folio` is a faithful transcription of that
column and is not to be "corrected" against where the plates were bound.
Measured over the 31 plates whose facing page has been keyed: 13 sit exactly
opposite the stated folio, 9 sit just after it — and those nine are precisely
the ones whose stated folio is *even*, a parity convention in the printed list
rather than an offset. The remaining 9 differ by more and cluster where several
plates share one gap (VII and VIII are both bound between folios 106 and 107),
which is a binding-versus-list discrepancy in the volume and not in the store.

**`figures.by_plate` is what locates a plate**, since nothing on its leaf names
it: the list's abbreviated caption against the keyed under-figure caption, every
segment required and exactly one leaf permitted. All 35 resolve; `edition runs`
reports the count and does not gate on it.

**Computing the leaf from the stated folio was considered and is worse on every
axis**, which is worth recording because it looks like the simpler option. The
parity rule above is real but it is an empirical property of *this* volume,
where the caption match knows nothing about any book — so the arithmetic is the
overfit of the two, not the general one. Scored over the 35: parity gets **21
right, 8 wrong, 6 unresolved** against the match's 35. The 8 wrong are the
dangerous kind — Plate VI onto `1-123`, which is Plate V's leaf; Plate VII onto
`1-129`, which is Plate VI's — a confident answer under the wrong caption. And
the 6 unresolved include every plate in parts 2 and 3, because arithmetic on a
folio needs the folio index and no page has yet witnessed theirs, while a
caption needs nothing. The match also carries no book-specific token at all: it
stripped a leading `Fig. N.` at first, which is this book's convention and
another book's mistake, and the strip turned out to be unnecessary.

**The List of Illustrations and Authorities Quoted are served as runs.** Both are
spans of exempt front matter whose content this repository already holds parsed,
and `docs/edition.md` owns how a run is declared, anchored and resolved. The
figure link needs `figures.by_number`, a corpus-wide fold of `figure_boxes`;
**it is not the per-entry reconciliation this file describes** — it links where a
printed number resolves to one zone and gates nothing.

**GraphicZone↔FigDesc pairing is not in the data.** Pair by geometry and record
the result; never re-derive it per consumer. **18 of the 252 pages are not 1:1,
and every one of them is zone-heavy** — max on a page is 4 zones / 4 captions:

    1-123 1-141 1-189 1-191 1-207 1-208 1-237 1-254 1-276 1-323 1-334
    2-085 2-100 2-122 2-198 2-205 3-006 3-007

(`1-191` — 3 zones, 2 captions — was missing from this list while the sentence
said seventeen. The list is the authoritative record by the rule stated above,
so a consumer trusting it treated a zone-heavy page as balanced.)

Zone-heavy is structural and permanent: one caption covers several images, either
lettered (`1-276` fig. 138 *a, b, c*; `2-085` fig. 253 *a, b*) or numbered
(`1-237` "Figs. 2, 3"), and `3-006`/`3-007` carry a zone with no caption at all.
Nothing will make these 1:1 and nothing should try.

**Caption-heavy is now empty, and that is a result, not a given.** All 5 such pages
were the segmenter finding captions that do not exist — clipped slivers of body
text, an unlabelled graphic, and on `2-094` the parallel strokes of the cheek
line-work in fig. 260, which at zone level look like a short line of type. Those
boxes and their readings were deleted. So **a caption-heavy page appearing in
future means a new segmentation fault, not a feature of the book** — which is
exactly the signal it should be, and was not while noise sat in the same bucket.

Encoding confirmed against real exports: eScriptorium writes zone types as
`OtherTag/@LABEL` referenced by `TAGREFS`, labels exactly `GraphicZone` and
`GraphicZone-FigDesc`. **Resolve by label, never by tag ID** — the IDs are
assigned per export (`BT55`/`BT56` in one, `BT68`/`BT69` in the next), so code
that hardcodes them fails silently rather than loudly.

**Pairing a picture with its caption is `figures.paired`, done once and recorded**
— the rule this record had always stated and nothing implemented. It branches on
the **caption's own shape**: a text figure sets its caption below the picture
(`1-151`'s is 610×96), a plate sets it rotated *beside* it, reading bottom-to-top
(`1-049`'s three are 86×457, 92×506, 82×636). A below-only rule leaves every
plate caption unclaimed, which is what it did — 19 over 14 pages. So landscape
looks below, portrait looks right, each requiring overlap on the other axis, and
the discriminator is `width >= height` rather than a prior classification of the
page. Over the whole store **one caption is unpaired** and it is a real
ambiguity: `2-068` stacks figs. 239 and 240 below two side-by-side pictures, both
spanning the full measure, so only caption reading order could decide and that is
an inference. `harness corpus figures` reports it.

Two earlier shapes failed the same way and both are worth remembering. Raw zone
ids in the payload made the model do the pairing, and `1-151`'s TEI shows the
cost — a correct anchor plus an orphan comment about the caption zone, which is
unreferenced *by construction*, i.e. a permanent known-false remark on all 252
figure pages. A page-local ordinal over pictures replaced it and was worse:
**the zone count is not the figure count in either direction.** `1-207` sets
fig. 87 *a, b, c* in two boxes with `a` and `b` sharing one, and several boxes
routinely tile one irregularly-shaped figure — so an ordinal would have reported
"2 figures" on a page the book calls one figure with three parts. The evidence
that settles it is prose inside the caption, which is why no geometric handle
could.

**The generated TEI now carries the figures themselves**, `<figure n><figDesc>`
with the caption from `data/readings.md`, one per printed figure on the same
dedupe as `_figures_on_page` — 197 of them over 131 pages. They are positioned
where their boxes physically sit, and that placement is final. It used to carry a
comment saying move me to the first textual reference; that spent the one
positional fact measured off the page to restate something `<ref type="figure">`
now records, and the prose first naming a figure is routinely on another page, so
the instruction could not be followed where it was stated most confidently. Two
figures carry a comment now, both asking whether the caption store missed a
printed number. A figure whose box falls inside a paragraph is emitted at
the **head** of that paragraph rather than splitting it, since splitting would
undo what `MainZone-Continued` records.

**The head and not the foot, which is a change.** Both ends are a boundary and
neither is the anchor, so the only question is which makes the better draft, and
the top wins twice: a picture the text wraps around begins level with the
paragraph's first lines, so the head is the nearer edge to where the page has
it, and a reader meets the figure before the prose discussing it rather than
after. Over the 197 generated figures, those immediately followed by a paragraph
rose from **141 to 167** and those stranded at the foot of a page, with nothing
below them to belong to, fell from **27 to 3**. The three that remain sit
genuinely below the last paragraph on their page (`1-187`, `1-210`, `1-278`).

**A figure inside the *last* paragraph was the case that broke it**, and it is
worth recording because the rule looked right and was wrong on a seventh of the
corpus. The flush at each paragraph's close tested figures against the top of
whatever band came next — which is the next paragraph's start, and works for
every paragraph that has one. The last paragraph on a page has none: it is
closed after the loop with that variable still holding its *own* first band's
y0, so a figure inside it failed the test, fell through to the final flush and
was appended at the very foot of the page. `1-157` sets fig. 36 at y 1602 inside
a band running 1393–3249 and put it after the paragraph that wraps it. The fix
is to measure against the paragraph's own bottom, which is the same number for
every other paragraph and the right one for the last.

That the *generator* reads geometry while `_figures_on_page` withholds it from the
model is not an inconsistency but the same rule twice. Handing a model coordinates
invites it to place a figure by eye instead of finding the sentence — the failure
the two earlier payload shapes above both produced. A rule cannot be persuaded by
what it sees, so it may use what a model may not.

Only 3 of the 20 OCR'd pilot pages also have figure ALTOs —
`1-151`, `2-030`, `3-006` — so the figure path is thinly exercised, and thinner
than that for captions: `3-006` is one of the two zone-with-no-caption pages, and
`2-030` is fig. 213's 27-line Chukchee gloss list, i.e. the least typical caption
in the volume. `1-151` is the only ordinary case in the pilot set.

## List of Illustrations

`data/loi.json` — the whole volume's figure list, read from scans `1-014`…`1-019`
(part 1 front matter, printed folios xii–xvii): **text-figures 1–302** and
**plates I–XXXV**, with folios. Complete run, no gaps or duplicates.

Two things it is not. First, LoI captions are **abbreviated** — they drop
catalogue numbers, dimensions and provenance notes ("from a photograph") that the
printed under-figure caption carries. They bind the caption *core*, not the full
text. Second, the two witnesses **disagree**, and neither automatically wins.
Where they do, `data/readings.md` records the reading as printed and adjudicates in
the `@note` — `MISPRINT` when the printed form is the book's own error (fig. 302's
caption reads "Envelope officially **seated**", verified at magnification, against
the LoI's "**sealed**"; the LoI misprints fig. 234's folio as "39" for 329),
`VERBATIM` when what looked like a defect is what the printer set. Either way the
reading is never normalised — the correction belongs in an editorial apparatus.

**Plate figures restart numbering at 1 on every plate**, colliding with the
text-figure series. `1-167` reads `Fig. 1.`–`Fig. 4.` and those are Plate XI's
four segments, not text-figures 1–4. A plate's figures match the
semicolon-separated segments of its LoI entry — and not always one-to-one: Plates
XXXII, XXXIII and XXXIV each carry four figures against three LoI segments,
because two figures share a caption. Classify a page as text-figure or plate
*before* matching any number against the LoI.

Native forms in the LoI (`Uñiˊsak`, `Nuˊnligren`, `Kereˊtkun`, `Valkaˊʟᴇn`) are
flagged `tier1` and are **proposals for keying, not adopted glyph identities** —
the firewall's subject is rank, a proposal rises only by a human act, and the
LoI is only reachable by reading a scan. The same applies to the Tier-1 forms in
`data/readings.md`, which are flagged in their `@note`. One is worth knowing about:
`1-049`'s Plate I caption prints `Nuˊnlig̣ren` with a **dotted g** where the LoI
sets `Nuˊnligren` plain. Recorded as printed, not adjudicated.

**The dot is encoded *below*.** The canonical form is `g` + U+0323 COMBINING DOT
BELOW; the precomposed U+0121 (dot *above*) is a **trap** for it. So `DOT_ABOVE_G`
and the `dot_above_g` flag name the lookalike, not the glyph — they are trap
detectors and correctly matched. Documentation here once called the inventory glyph
"dot-above g" while its own example encoded U+0323, which cost a session's worth of
chasing the wrong codepoint; hence the emphasis.

One thing still wants a human, and it is firewalled: whether the U+0323
canonicalization was made against the printed p. 10 key or inherited from whatever
the recognizer emitted. If the latter, the OCR chose the orthography and the
validator has been enforcing it.

# Authorities Quoted

`data/authorities.json` — the book's own bibliography, read from scans `1-023`…`1-029`
(printed folios 3–9, ToC `front.authorities-quoted`): **73 works**, one record each,
keyed with a BibTeX-style moniker (`bogoras1900`, `krause1882`, `nordquist1882a`). The
third apparatus store alongside `loi.json` and `toc.json`, and apparatus for the same
reason — reachable without parsing TEI, and the annotation pass is its consumer.

**73 is the printed count, not the record count.** The store holds **95**, the
extras being the twenty-two `source.unprinted` records the provision below
admits — `jochelson1905`, plus all twenty-one of the chapter XXIII footnote
bibliography. Which number a sentence wants turns on whether it is about folios
3–9 or about what a reader returns: `source.count` is 73 and `read_from` is true
of those alone, while `find authority` bare lists 95. The two have been conflated
in this file and in `authorities.py` before.

`harness find authority` is the reader. It searches `cited_as`, then `author`, then the
titles, then the printed blocks, reports which of those caught each hit, and
**returns all of them** — 67 sigla over 42 names means a single answer would be
manufactured, and no hit at all is a legitimate outcome on an open list. It
resolves nothing; a human reads the candidates.

**Collation is now a second consumer, and it writes nothing back.** The pass wraps a
citation in `<bibl>` and marks the author inside it, so the *extent* of a reference —
the part no string match recovers, since the book cites by bare surname — is recorded
per page. Which work it names is not: `find authority` is read while collating to
settle the reading, and its answer never reaches the file, `harness tei validate`
refusing `@corresp`, `@ref`, `@key` and `@sameAs` on `<bibl>` to make that mechanical.
The annotation pass remains the only thing that keys a citation, because it resolves
with the whole corpus in view rather than one page at a time — and because this list
is open, so a per-page pass keying what it could would leave the store part-resolved
by accident of which pages ran first.

**The payload is `cited_as`.** The book cites in short form and this list is the only
witness to what those resolve to. It is **structured — `{name, volume, short_title}` —
not a string**, because the surface form in the body is not the form printed here:

- **The small caps are the bibliography page's setting and do not survive into the
  text.** The entry prints `DALL, I`; the footnote reads `Dall, I, p. 375.` `name`
  holds the upper-and-lower form. Match case-insensitively regardless.
- **The comma before the volume is not reliable.** `Maydell I, p. 331.` against
  `Krasheninnikoff, II, p. 49.` in the same apparatus, so the comma carries no
  information: `authorities.parse_citation` splits on commas and whitespace alike and
  asks the same question of every token. Hence `volume` as its own field, and hence a
  siglum printed over several volumes splits into one entry per volume — 42 printed
  sigla, 67 `cited_as` entries.
- **Most references are not sigla at all.** They are indirect prose — "Krause reports
  that…" — carrying the name alone, no volume, no short title, no footnote. A resolver
  keyed on the footnote form misses the majority. `name` is what reaches them, and it
  is ambiguous by construction wherever two works share it, which is most of the list.

**`printed` is the record; the parsed fields are convenience** and lose to it on
disagreement. Three properties of the print any consumer must know:

- **Most Russian entries are printed twice** — the original, then Bogoras's own English
  rendering in brackets. One work, two `printed` blocks (`entry` and `translation`),
  and the two **disagree** often enough to matter: `anon1894` sets № 14 against No. 4
  for the same issue; `maydell1871` drops Географическаго from the society name the
  English spells out. Both recorded, unadjudicated, per the `readings.md` habit.
- **Repeated authors print as a long rule.** The rule is not reproduced in `text`;
  `author_printed` is `"named"` or `"rule"` and `author` carries the inherited name.
- **Order is the print's and is not chronological.** `murdoch1884` follows
  `murdoch1888` because the rule binds it to its author; `maydell1871` sits among the
  1893 entries. Sorting by year does not reproduce the page.

**The list is explicitly open** — the sharpest difference from `loi.json`. Folio 9
closes with an asterism and "For other authorities see references in the text", so a
body citation with no entry here is expected and is *not* a reconciliation failure,
where a figure outside LoI 1–302 would be a defect.

**And the store may hold a work the list does not print, on that provision alone.**
`source.count` stays **73** — a fact about folios 3–9 that no later addition may
edit — and `source.unprinted` names every record keyed from the body instead, so
`records = count + len(unprinted)` and `read_from` remains true of the 73 and of
nothing else. Such a record carries `ref: null`, `folio: null`, `printed: []`, and
its `note` says why it is there; `apparatus.entries_for` filters on `ref`, so it
renders on no leaf.

**Null `ref` records the absence of a printed block, and nothing else.** It used
to do double duty: the span gate ran in both directions, so *any* record naming a
leaf outside the `authorities` run failed `edition runs`, and dropping `ref` was
the only way to admit one. That made a record about rendering rather than about
the print, and it could not express the case that actually arrived — a work
printed in the book but not in folios 3–9. The gate now runs **one way**: a run
demands every leaf it names be witnessed, and the store may hold more. So a
body-printed work keeps its `ref`, its `folio` and its `printed` block, and stays
off the leaf for the reason it always should have — `entries_for` resolves the
leaf to a run first, and no run covers it. The worked case is the **chapter XXIII
footnote on `3-146`/`3-147`** (folios 680–681): twenty-one numbered works, most
set twice as the front list is, closing with the very sentence folio 9 closes
with. It is what the asterism points at, and it is a text page rather than an
apparatus leaf, so it reaches the edition through `gt/ocr` → TEI; a run over it
would render the bibliography a second time.

The first unprinted record is **`jochelson1905`**, *The Koryak* — Jesup Vol. VI, cited 36 times in parts
2 and 3 and impossible in part 1's list, which went to press the year before the
work appeared. It exists so that `Vol. VI, Jochelson, The Koryak, p. 117.`
resolves when those parts are collated, and it asserts nothing about the print.
Note where the volume sits: **before the name**, so `cited_as.volume` is null and
the short title is what discriminates this Jochelson from the other four —
`citations._fits` reads only what follows the name. Its `url` is also the
store's first `#ed` located copy: the editor handed the AMNH Digital Library
link over directly, which is exactly the human act every `#llm` one is waiting
for. Its `doi` stays null, none having been looked up.

**Pre-1918 Russian orthography is not a misspelling** — `ъ ѣ і ѳ`, the `-аго/-яго`
genitives. The collation licence to correct European-language spelling does not reach
it, and neither does it reach the print's own errors, recorded as printed and
adjudicated in `note`: `sarytcheff1802`'s *Сѣверо-Востооной* and *ывшей*,
`kjellmann1882`'s *hushallväxter*, `nordquist1882c`'s *kännedomen on*.

**`doi` and `url` are filled where a copy was located, and carry provenance.** Both
hold `{url, provenance}` rather than a bare string, `#llm` on every one of them,
because a model proposed every match — the same rank the corpus uses for a model's
reading of a scan, and for the same reason: a plausible-but-wrong DOI is fluent
nonsense with no error signal. Ratifying one means a human opening the link.

Coverage, from a sweep of Crossref and the Internet Archive over all 74: **13 DOIs
and 32 scans, 38 records touched**, 36 with nothing located. Nine of the 13 DOIs are
BHL title DOIs (`10.5962/bhl.title.*`); the rest are AnthroSource (`murdoch1888`,
`bogoras1902`), USGS (`dall1877`) and Brill (`adler1901`).

Three properties of that number:

- **A miss is not an absence from the web.** The 36 are overwhelmingly Russian and
  German journal articles plus four Smithsonian annual-report chapters, living on
  prlib.ru, elib.rgo.ru, MDZ and DigiZeitschriften — none with an open search API,
  so they are hand work against library catalogues, not another sweep.
- **A resolving identifier is not a match: compare the title, year *and* volume it
  returns.** Three near-misses were caught only this way and all three would have
  looked right sitting in the field — `lutke1834` (the scan is a different 1835
  section), `schrenck1899` (Vol. II, and only I and III are scanned),
  `sarytcheff1802` (the top Crossref hit is the 1806 English translation).
- **Two recorded matches are a different imprint of the same text**, deliberately:
  `nordquist1882b`'s DOI is the 1880 separate printing, `murdoch1884`'s scan the
  1890 separate issue. Modern facsimile reprints, by contrast, are **not** recorded
  — a Cambridge Library Collection DOI names a 2013–14 edition, not Bogoras's source.

**The chapter XXIII twenty-one were identified separately, and by hand.** No sweep
reaches them: they are Russian books and journal runs living on prlib.ru,
elib.tomsk.ru and Commons — the hand work against library catalogues the first
property above describes. **Twenty of the twenty-one now carry an identification** in
`note`, `#llm` and unratified like every other, and **eight a located scan**;
`anon1856` is *searched and not found* and stays so, an anonymous article in a
`Вѣстникъ ИРГО` volume whose contents are not online, where the one 1856 Chukchee
item that does surface is a different title under a named author.

Two of the identifications **changed how a printed fact reads**, which is the return
on doing them at all: `baramygin1855`'s bare `57`, set by both witnesses, is the
publication year 1857 and not a volume — the work is in `Записки Сибирскаго отдѣла`
кн. IV, 1857 — and its `1855`, which the English witness alone supplies, is the year
of the *journey*, printed in the work's own title. `pilgrim1887`'s English `(monthly)`
is wrong about a weekly, so a merge of the two blocks would have carried the error
into the record silently. One near-miss of the second kind above was caught and is
recorded rather than filed: `muller1750`'s title resolves on prlib to the **1787**
second edition.

One reading is unresolved and flagged in the file: `melikoff1896`'s Russian quoted
title closes with a mark whose form is not separable at this magnification. That is
a **tooling gap** as much as a reading one — these pages have no ALTO, so `harness
zoom` and `harness ocr lines` cannot reach them, and no verb magnifies an arbitrary
region of a page outside the pilot 20.

**Cyrillic `й` is `и` + U+0306 by canonical decomposition**, so corpus-wide NFD turns
every Russian word into base+mark sequences and `unlicensed_marks` once reported all
72 as errors — `MARK_LICENSE` is written for the Tier-1 Latin notation but runs over
every character in the corpus. `и`/`И` are licensed breve bases, as allow-list
entries and deliberately **not** as a "consult the table only for Latin bases" script
test: that states the scope more honestly but decides it by inference, and each
unbounded corner case would be a silent skip in place of a loud error. Note `ё` =
`е` + U+0308 needs no entry only because U+0308 has no licensing table yet; give it
one and this recurs. Regression test: `harness/tests/test_marks.py`.
