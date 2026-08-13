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

> **A negative is a keyed, non-exempt page whose ink verdict is `clean`, with no
> `gt/fig/` file.** The ink check is the witness — every band of ink accounted for
> by text zones alone, leaving nothing for a figure to be.

Two clauses are load-bearing and both have live instances. **Exempt pages are
excluded** because the ink check never ran over them and because they are plates,
exactly where figures live: 44 of the 252 positives are exempt pages, and counting
the rest as empty would teach the model that plates are blank. (Exemption
disqualifies a page from being a *negative* only; an exempt plate carrying figures
is an ordinary positive and trains.) And a page whose ink was **excused** reads
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

**Cropped from `scans/` at 300 dpi as it stands, and the cost is accepted rather
than unnoticed.** The ~300 dpi master is the *text* layer only — the photographs
are embedded JPEGs already at their native 150 dpi, so a photo crop is a 2×
upsample carrying no detail the original had not. One raster tree and one code
path is worth that. Their bboxes matched the embedded JPEG dimensions exactly at
150 dpi, which stays available as a free check on the segmentation, and as the
diagnostic if a crop ever looks wrong.

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
`_exempt.lst`/`_exempt.json` was renamed to avoid.

**GraphicZone↔FigDesc pairing is not in the data.** Pair by geometry and record
the result; never re-derive it per consumer. **17 of the 252 pages are not 1:1,
and every one of them is zone-heavy** — max on a page is 4 zones / 4 captions:

    1-123 1-141 1-189 1-207 1-208 1-237 1-254 1-276 1-323 1-334
    2-085 2-100 2-122 2-198 2-205 3-006 3-007

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
where their boxes physically sit, which is deliberately not where they belong: the
anchor is the first textual reference and that is a reading, so each carries a
comment saying move me. A figure whose box falls inside a paragraph is emitted at
the **head** of that paragraph rather than splitting it, since splitting would
undo what `MainZone-Continued` records.

**The head and not the foot, which is a change.** Both ends are a boundary and
neither is the anchor, so the only question is which makes the better draft, and
the top wins twice: a picture the text wraps around begins level with the
paragraph's first lines, so the head is the nearer edge to where the page has
it, and a reader meets the figure before the prose discussing it rather than
after. Measured when the rule changed — of 197 figures **189 moved earlier and
none moved later**, and figures stranded past the last paragraph of a page, with
nothing to belong to, fell from 29 to 5.

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
the firewall's subject is a model's reading of a scan, and the LoI is only
reachable by reading one. The same applies to the Tier-1 forms in
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

`harness find authority` is the reader. It searches `cited_as`, then `author`, then the
titles, then the printed blocks, reports which of those caught each hit, and
**returns all of them** — 51 sigla over 34 names means a single answer would be
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
  siglum printed over several volumes splits into one entry per volume — 47 printed
  sigla, 51 `cited_as` entries.
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

Coverage, from a sweep of Crossref and the Internet Archive over all 73: **13 DOIs
and 31 scans, 37 records touched**, 36 with nothing located. Nine of the 13 DOIs are
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
