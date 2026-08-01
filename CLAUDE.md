# Bogoras, *The Chukchee* — annotated digital edition

Memoirs of the AMNH XI / Jesup North Pacific Expedition VII, Parts 1–3
(Brill 1904/1907/1909), ~730 pp. Public domain.

Proof-of-concept for an open ethnographic-atlas effort: web and epub editions of
public-domain ethnographies with annotated entities, indices for toponyms, species
and transcribed forms, and linkage to D-PLACE. Bogoras first because the text is
public domain, in English (no translation layer in the PoC), and dense with
idiosyncratic phonetic transcription, obsolete binomials and vanished toponyms.

# Governing principle

**The failure mode that matters is fluent nonsense** — plausible output carrying no
error signal. Every design decision below follows from it. Prefer mechanical,
auditable rules over judgement; prefer "unresolved" over a confident guess; prefer
two independent witnesses to one confident one wherever a second is cheap.

**Firewall.** A rule about **hierarchies of provenance**, not about agreement with any
upstream file. No non-English glyph identity may be *adopted* on a model's authority: a
model may read a scan and propose, but the reading carries its rank with it and rank rises
only by a human act. Nothing may promote a proposal, and nothing may infer a glyph from
what Bogoras's system "should" contain, from a neighbouring page, or from any corpus-wide
pattern. Book-internal apparatus (the p. 10 key, the List of Illustrations, the printed
TOC) is *not* subject to this — it is evidence, and it binds.

In the TEI this is `@resp` on every element bearing a Tier-1 `xml:lang`, pointing at one
of three ranks: `#ed` ratified (a human keyed or confirmed it against the page), `#llm`
proposed (a model read it), `#htr` unexamined (recognizer output). The ranks are declared
once in the corpus teiHeader and never in a page file — `@resp` is a pointer resolved
against the assembled document, and a page file is a fragment that already defers title,
publication and source the same way. The collation pass may emit `#llm` and nothing else;
`harness validate` errors on a higher claim and on a missing `@resp` equally, because an
unmarked span is indistinguishable from a ratified one to anything that does not check.
`--ratified` switches the expectation for a page a human has been through.

**What the firewall is not** — stated because it was stated the other way for most of
this project's life: it is *not* "reproduce the draft verbatim". That version enforced
the canonicity of whatever `ocr/` happened to hold, and so was **unsatisfiable** over
real recognizer output (CATMuS emits 0% of the inventory, so every correct TEI failed)
and a **tautology** over a model's own reading, comparing a file against its own source
and rendering the result as a verified PASS. Removed from `validate.py`,
`validate.py` and the collation skill; the comment at the old check's site records why.

That tautology is a live hazard, not a closed one, and it recurs wherever a check's
two inputs can turn out to be the same file. `harness review`'s span diff now refuses
rather than reporting a clean 40/40 when the store it is pointed at resolves to the
ground truth the proposal produced. **A comparison whose witnesses may be one witness
must say so.**

**LLM remit.** Models triage, propose, and restructure. They never originate a glyph
identity and never mint an index entry unreviewed.

# Environment

- `uv` project, **Python 3.14.3** (`requires-python = ">=3.14"`). PyTorch supports
  it now — torch 2.12.0+cu130, `cuda.is_available()` True in the env. The old
  3.13 pin is gone; if a doc still says 3.13, the doc is stale. `uv.lock` committed.
- `kraken` 7.0.3, pinned. **The CLI was reorganized across the 3→5→6→7 majors and
  nearly every tutorial online is 4.x-era.** Verify flags against `kraken --help` /
  `ketos --help` rather than trusting remembered or documented syntax, including
  anything asserted in this file.
- eScriptorium via `docker compose`, local, from `gitlab.com/scripta/escriptorium`.
  It is the annotation GUI, **not** the system of record. Export ALTO and commit
  every session.
- GPU: Turing card, ~100× over CPU. Torch CUDA build verified in the uv env.

# Encoding

**NFD, corpus-wide** (`keying_spec.md` §1). Declared long before anything enforced
it, so the corpus had drifted — `data/readings.md` held both encodings of the same
glyph and exact comparison between stores silently failed. `harness normalize`
(bare, or `--check`) is the gate; `--convert` writes the fixes. It reports a file
count, and the count moves as stores are added, so read it rather than a number
written down here.

**Never NFKC.** It has compatibility decompositions for two inventory glyphs and
destroys them: `ᵋ` U+1D4B → plain U+025B (113 occurrences), `˙` U+02D9 → space +
combining dot. Any `normalize()` call must name its form.

**The ASCII policy is scoped to Tier-1**, amended from corpus-wide (`keying_spec.md`
§1). Inside `ckt`/`kpy`/`ypk`, U+0027 and U+002D are the only apostrophe and hyphen.
English prose reproduces the print, **curly quotes included** — the book sets them,
and conflation with a true apostrophe is a hazard only where apostrophes are
phonetically load-bearing. `validate.LOOKALIKE_GREPS` is applied only inside Tier-1
spans for exactly this reason, and `normalize.LOOKALIKE_CHARS` deliberately omits
the curly quotes because it runs over whole files. **The two are not copies and must
not be merged** — `tests/test_lookalike_scope.py` holds them apart, and exists
because a consolidation was nearly carried out on the strength of an audit that
mistook the difference for drift.

Note U+0027 is *itself* the spirant and pause mark, not merely a lookalike for
U+02CA. That is why the review page's notation keyboard is a toggled mode rather
than a remap, and why its palette carries a dedicated curly-quote pair.

**Two more corpus-wide lookalike traps** live in `normalize.py` alongside `ġ`:
`U+0131` (plain dotless ı) traps `U+026A`, the only licensed dotless small-cap
(§2.3 — U+0131 has no legitimate reading anywhere here), and `U+0022` traps curly
`“ ”` in `text` fields and non-`@note` prose. Both report-only, like every
lookalike — a human ruling, not an auto-fix. `normalize` **checks by default**;
`--convert` is required to write anything, and the `spacing` rule (§2.9: collapse
runs of 2+ spaces, strip space before `;`/`:`/`,`) blocks like NFD does, since
neither is a judgement call.

`keying_spec.md` §2.6 records **mark–base licensing**, editor-supplied: the breve
U+0306 sits on `u` and `i`, never on the obscure-vowel series `ᴀ ᴇ ɪ ä`, since the
p. 10 key already glosses that series as short. It exists because `i` **drops its
dot under an above-diacritic**, so printed `ĭ` and a hypothetical `ɪ̆` are the same
letterform at any magnification and only the constraint separates them (`1-074`'s
`Am-g̣roˊkĭ`). Consequence: `ɪ` + U+0306 anywhere is an error, not a reading. This
is the one detector that blocks a write rather than raising a flag.

# Source rasters

AMNH Digital Library PDFs (`M11Pt01–03`).

**`scans/` is derived, not source.** It is exactly `pdftoppm -r <dpi>` over
`pdfs/` — verified pixel-identical — so it is regenerable and stays out of git.
The PDFs carry a **bitonal JBIG2 text master at ~300 dpi** (part 1 2781×3866 at
295.5 dpi, part 2 2550×3525 at 300, part 3 2550×3525 at 308.4 against an A4 page
box; the covers `1-001`/`1-002` and the foldout `1-361` have no master and are
RGB at 150). The figure *photographs* are separate embedded JPEGs already at
150 dpi, so nothing is recoverable there — only the text gains.

Rendering at 300 dpi is **not** a clean ×2 of the old 150 dpi rasters — across the
832 pages, **none** is exactly double, and most are a pixel short on one axis. So
anything mapping between the two spaces must **take the ratio from the two rasters,
per page and per axis**. Computing it as `ceil(pt/72*dpi)` fails too, on float
error: it predicts 2782 for the covers where poppler renders 2781.

**Page refs are `PP-NNN`** — part, and scan index within that part (`1-048`) —
everywhere: filenames, CLI, `boundaries.json`, commit messages. NNN is a *scan
index*, not a printed folio. Part 1 runs 001–362, part 2 001–268, part 3
001–202; the printed folio runs continuously 1–732 across the volume, with
plates and front matter unpaginated. **Neither is derivable from the other**, so
a bare page number names no page and the harness rejects one. The folio is known
only where a transcribed page recorded one, and propagates from there via the
seam ledger (`harness/state.py`, `harness ledger`) — which is exactly the
book-internal-evidence rule applied to pagination: the page says what page it is,
and nothing infers it.

# Where things stand

Layout, all at the repo root:

    scans/  832 rasters, all three parts, 300 dpi. Derived; not in git.
    scans-fig-blotted/  the same pages with figure zones painted white, the
            segmenter's training input. Derived; the 580 figure-less pages are
            symlinks into scans/, so a clone gets dangling links. Ignored.
    ocr/    the read view over every OCR store — symlinks, currently all into
            gt/ocr/. The harness's default --from. Never written through.
    gt/     what a human has been through. ocr/ (20 pages of ground truth),
            fig/ (252 figure ALTOs + METS, geometry only), seg/ (the first
            segmentation attempt, 122 pages, kept read-only), zones/ (the
            current one — seven types, fixed-width bands; 181 pages, 969 zones).
    mz/zones/  what the trained segmenter emitted, raw. Derived; ignored.
    zones/  the read view over both zone stores — symlinks, the human file
            always winning. Derived; ignored, unlike ocr/, because half its
            links point into the ignored mz/. Never written through.
    tei/    1 page, plus corpus-header.xml — the corpus teiHeader, gated by
            `harness header`. Not a valid TEI document on its own: a bare
            <teiHeader>, a fragment like the page files, spliced in by an
            assembly step that does not exist yet.
    data/   readings.md  loi.json  toc.json  authorities.json  lexicon_extra.txt
            zones_config.json
    review/ one directory per page, PP-NNN/. proposal.json (a reading, not truth)
            and decision.json (adjudicated) are tracked; crops/ sheets/ zoom/ and
            review.html are derived and ignored. See harness/paths.py.
    models/ blla, CATMuS print (large + tiny), LADaS medium, orli, plates-seg,
            zones-seg (this project's own, trained on gt/zones/).
    pdfs/   symlinks to the three AMNH source PDFs, outside the repo.
    bogoras-rec/  working dir for recognition runs. Ignored; only trained models
            are kept, and those live in models/.
    scans-w-figs/  scans-w-ocr/   symlinks into scans/. Derived, and ignored:
            they point *into* an ignored tree, so a clone gets dangling links.
    harness/  tools/  tests/  concordance.md  keying_spec.md

- **The ground-truth rebuild is finished.** All **20** pilot pages in `gt/ocr/`
  carry text — the pilot selection is scattered across all three parts, and
  `harness pages` lists it. `tei/` holds **three** pages — `1-151`, and the
  adjacent pair `1-100`/`1-101`, which is the corpus's only collated seam.
- **`ocr/*.xml` are symlinks into `gt/ocr/`**, and `ocr/` is a *view*, not a
  store: the stable name a page's current OCR is reached by, whatever produced
  it, and the harness's default `--from`. Raw recognizer output, if any is
  produced again, links in beside the ground truth from its own real store, so a
  file's rank stays readable from where its link points. **Reads may resolve
  through `ocr/`; writes never do** — `restore` names `gt/ocr/`.
  Two names over one inode means a tool walking both sees each file twice, so
  anything iterating the corpus must **dedupe by real path**: without it a writer
  processes the file under the first name, meets it again under the second, finds
  it already done and skips silently, so the report undercounts exactly what it
  touched. `harness/normalize.py:scoped_files` does this and says why.
- **Figure captions live in `data/readings.md`, not in `gt/fig/`.** All **395**
  are read by hand off the 300 dpi scans, one block per FigDesc zone, keyed
  `<ref>|<zone-id suffix>`. `gt/fig/` carries **no `TextLine` at all** — the lines
  were stripped, because the exported line segmentation dropped whole printed
  lines and a line-level witness in the ALTO would then disagree silently with
  the readings. **Consequence for code**: reading `String/@CONTENT` out of
  `gt/fig/` returns `""` for every zone on every page. Not an error — nothing,
  which is worse. Go through `figures.readings()`, and check the two stores agree
  with `harness figures` (invariant: `missing` and `orphan` both empty; it exits
  1 if either is not).
- **eScriptorium holds nothing right now** — the projects were exported and
  deleted. The repo is the system of record; re-import when keying resumes.
  `tools/make_mets.py gt/fig` rebuilds the manifest first.
- **The harness has tests**: `uv run pytest`, over the pure logic — ref parsing,
  the mark licence, the spacing and NFD rules, the folio fold, the layout lists,
  citation parsing, and the lookalike *scopes*. Fixtures live in `tmp_path`, not
  the live corpus. See `harness/README.md`.
- `tools/` holds four scripts, none of them part of a loop. `make_mets.py <dir>`
  is live — it rebuilds a METS manifest before an eScriptorium import.
  `migrate_coords.py` (150→300 dpi) and the two `strip_*_lines.py` (which produced
  the line-free `gt/fig/`) are **spent one-shot migrations**, kept for the
  reasoning in their docstrings; re-running either would corrupt what it already
  converted, and both say so at the top.

**The frontier is collation.** `tei/` holds 3 pages of 832. The apparatus stores are
done and reconciled — `loi.json`, `toc.json`, `authorities.json`, `readings.md`,
and the 20 pilot ground-truth pages — so what is left is the pass that consumes
them.

`1-100`/`1-101` are the corpus's only **adjacent** pair, and adjacency is what makes
them worth more than two pages. The seam between them is a live run-on: `1-100` ends
`<item n="14">`, `1-101` opens at 15, and a `<list>` is not fragmentable, so `harness
seam --continues` linked `list-1-100-1` ↔ `list-1-101-1` rather than writing `@part`.
That is also the first time the ledger's `boundary` column has held a value other
than `unknown` — and it reads `open` off `@next`, which is exactly what a
`@part`-only derivation would have missed.

## The ground-truth loss

Rebuilt and closed, but the design fault it exposed still governs the store layout.
An archive extraction over `gt/ocr/` replaced 17 of the 20 hand-keyed pages with
~1977-byte export shells, and there was no copy anywhere in the repo. **The cause
was that a file's role — machine output or human ground truth — lived only in the
directory name**, while `ocr/` symlinks into `gt/ocr/`, so anything written into
one wrote through to the other. Nothing in an ALTO says which it is: the
`Description` block of a hand-keyed page and of an empty shell are byte-identical.

Hence the current rule, which is the whole lesson: **`gt/` is what a human has been
through, `ocr/` is only a view over it, and nothing writes through a view.**

The rebuild ran as `/rebuild-groundtruth PP-NNN` and its skill remains normative
for the pass — which is now a *revision* loop rather than a restoration one, since
every page has text. `restore` reports which of the two it did.

Three invariants from that work bind anything touching lines, not just that pass.
`context._lines_from_alto` **drops empty lines**, so its index is not the ALTO's —
join through `harness lines`, never through `detector_flags`' line numbers. And **a
line polygon can exclude printed text**: `1-074` prints `5.` and `9.` outside their
boxes, `1-073` the same with its `5.` and its folio `51` outside *every* box on the
page. The omission is horizontal, so no vertical padding reaches it; `--margins`
widens to the PrintSpace, which is where the excluded material sits.

Third, and newest: **line output is in reading order, but `index` is an identity,
not a position.** `page_lines` returns banded rows left-to-right while `index`
stays what ALTO document order assigned — and the two genuinely diverge, on 18 of
the 20 restored pages, 524 positions in all (`1-101` reorders all 59). Since
`proposal.json`, `decision.json` and `restore` all join on `index`, anything that
renumbers to match the display would silently mis-map every adjudicated page. The
visible consequence is that line labels are *not* consecutive in any listing, sheet
or review queue; that is the tell, not a bug. Sorting is banded rather than a plain
`(vpos, hpos)` because baselines wobble a few pixels across a row: a strict sort
puts the gloss before its headword on four of `3-005`'s six two-column rows, i.e.
it fails worst on the layout it exists for.

## Page segmentation, second attempt

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
- **Training runs on figure-blotted rasters** (`harness zones --blot`,
  `scans-fig-blotted/`, painted **white** — `lines --blot`'s conspicuous pink and
  blue are for a human and would be a feature the model could key on). Whether a
  paragraph wraps around an illustration is a fact about the ink and not about the
  coding, so the figures come out before the segmenter ever sees the page. The
  declared box is painted and **not a pixel more**: 24 pages in a 40-page sample
  keep ink just outside a zone, but that ink is a few pixels of photograph edge on
  a plate like `1-167` and **body text set hard against an inset figure** on
  `1-283`, so a pad would erase text on every page of the second kind to tidy a
  sliver on the first.

Store is `gt/zones/`, ALTO in the eScriptorium dialect so it goes straight into
`ketos segtrain` and back into the GUI if ever wanted — the import/export loop being
the friction this replaces. It is **a separate store from `gt/seg/`, permanently**:
the label sets and the geometry regimes differ and nothing in an ALTO says which
scheme produced it, which is the same missing internal witness that cost 18 pages of
transcription. Blocks carry an `mz_` id prefix for the same reason.

**An empty page saves only if it is marked `exempt`**, and this is the three-split
distinction enforced rather than merely declared. In the store a text page with no
zones and a page nobody has reached are byte-identical — `zone_refs` finds both, the
sweep counts both as keyed, the list draws both as done — so an empty save does not
record a judgement, it erases the difference between having made one and not.
`exempt` is how a human says "I looked at this and it is not a text page"; that is a
statement and it saves. "Nothing here" is not, and `save_zones` refuses it, including
when it arrives as zero zones over a page that had some. The refusal only guards
writes, so `validate_page` also reports an `empty-page` **error** for a page already
in that state — it is the one defect that makes a page look *finished*, and every
other check is silent on it by construction. `1-075` was found this way: an ordinary
text page, chapter opening `III. — TRADE.`, saved with nothing on it.

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
even though its labels are not, so `harness zones --serve --itinerary gt/seg` walks
it. **That itinerary is now walked** — see below; together with the two chapters it
is the sample the first training run was meant to have. An itinerary is a
**work-list, not a filter**: a page not on it still opens and
still saves, it simply has no neighbours, and a scoped sweep reports the unkeyed
entries as rows so "how much is left" has an answer.

**Where it stands: 345 pages keyed** — `gt/seg`'s heterogeneous 122, then part 1
straight through to `1-359`. **271 text pages carrying 1692 zones**, 74 marked
exempt, weighted heavily to part 1 (274 pages, against 31 and 40). The splits are
**211 train / 60 eval**; the eval set was grown from 34 during the third training
run, which breaks comparability with the first two runs' headline figures and was a
deliberate trade for a better final estimate.

Read the class distribution against the earlier one below: `MainZone-Quote` has not
moved at all — **25 instances at 181 pages and 25 at 345** — while everything else
roughly doubled. That is the fact behind `train_merges`.

    MainZone-P            884    MainZone-Other         60
    RunningTitleZone      261    QuireMarksZone         47
    MainZone-Continued    250    MainZone-Quote         25
    MarginTextZone-Notes  165

The class distribution is the thing to read here, because it settles a question this
design was open on:

    MainZone-P            494    MainZone-Other         54
    RunningTitleZone      141    QuireMarksZone         26
    MainZone-Continued    124    MainZone-Quote         25
    MarginTextZone-Notes  105

`MainZone-Quote` was **zero** at 75 pages, and a class with no instances cannot be in
a class map — the open question was whether to fold it into `MainZone-Other` before
training. It now sits level with `QuireMarksZone`, so it stays. The book answered;
nothing was decided.

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

**The page list (`l` in the editor) carries the ink verdict, and it is cached rather
than recomputed.** Every other column costs ~1 ms and is read straight off the files;
this one opens the raster and costs ~0.20 s, which over a 122-page itinerary is most
of a minute before the table appears. But the editor **already runs the check** on every
page it opens and every page it saves, and so does `harness zones --ink` — the answer
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

The remaining 0.16 s is inherent to the format, not to the check. `scans/` is
`pdftoppm`'s RGB output while the pages' channels are identical everywhere tested;
regenerating it as greyscale would cut the decode to ~0.05 s and the tree to a third
of its size. That is a corpus-wide change to a derived store with several consumers,
so it is recorded here rather than done.

### The model exists, and so does a second store

`ketos segtrain` has run, three times. The installed model is
`models/bogoras-seg/zones-seg.safetensors`; the accuracy stays out of the filename,
since a default path that changes every retrain is a default nobody can use.
`harness zones --predict` runs it.

**Two directories, and the split between them is the point.** `train/bogoras-seg/`
is scratch — the symlink farm, the two `.lst` files, each run's checkpoints — and
**nothing reads it once training ends**, so `--assemble` may clobber it freely.
`models/bogoras-seg/` is tracked and holds the artifacts: the weights, the split
they saw as `<model>.train.lst`/`.eval.lst`, and a small `<model>.json` for the few
facts that are not lists. They used to be one directory, and the `.lst` files were
both the *next* run's input and the only record of what a *past* run consumed —
so preparing a run destroyed the ability to interpret the model already installed,
and `--score` would read whichever lists happened to be lying there regardless of
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
- **A prediction is measured, never gated.** `harness zones --from mz` runs the same
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
  `--predict` over an itinerary would mark the whole list keyed in one command and
  leave the next session with nowhere to resume.

**The sidecars stay `gt/`-only** — the three split lists, `_rule_exempt.json`,
`_ink_exempt.json`, `_ink_cache.json`. They record judgements about *pages*, not
about a store's files: an ink exemption rules that some mark on the paper is not
type, which is true whoever's zones are being measured against it, and there is no
such thing as the machine store's opinion of which pages are held out. The cache is
the sharper case — keyed by ref alone, so a machine verdict landing in it would sit
in the page list's column indistinguishable from one about work a human has done.

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

### A `class_mapping` that has been through `--resize` is not trustworthy

The first trained model **scored 0.2% label agreement on its own training data** —
below the ~14% of guessing among seven classes, which is the signature of a wrong
mapping rather than a weak model. The geometry was right throughout; every name was
wrong, a clean permutation. Nothing else could see it: the ALTO is well-formed, the
boxes are right, and the editor draws confident coloured bands with the wrong names
on them. Fluent nonsense arriving in the one place nothing was checking.

The invariants that follow, mechanism aside:

- **`--install` refuses a permuted map**, so the check is a precondition of the
  artifact existing rather than something to remember; `--remap-model` repairs one.
- **The repair is a rename, not a retrain.** Both `--resize` branches assign class
  indices by iterating a `set`, and Python randomises string hashing per process, so
  a retrain is a lottery — `union` is not the fix it looks like.
- **Omitting `--resize` is the only reliable escape**, which `--assemble` now derives:
  when the data's class set already matches the model's, nothing is renumbered.
- **The mechanism is unproven.** The set iteration is a real hazard sitting in the
  code but has not been shown to be the cause. What is proven is the permutation,
  its bijectivity, and that it holds out on pages it was not derived from.

The diagnosis, the cycle it formed, and how `--remap-model` inverts it are in the
skill.

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

**Adjacent same-label zones are 42% of all boundaries** — 596 of 1405, 561 abutting,
568 paragraph-to-paragraph — and **no model trained on this store can produce them**:
two abutting `MainZone-P` rectangles rasterize into one continuous target, so the
boundary is destroyed before the network sees it. Recovering it is therefore a
separate mechanism reading the ink, not something a better model would fix. `harness
zones --paragraphs`; the calibration and the failure modes are in the skill.

That check's `false_positive` count is a **worklist, not a rate**, and the reason is
the firewall's: gt cannot arbitrate, being the thing the rule corrects. Of the first
twenty found, fifteen were keying slips and were fixed. A precision computed against
a reference the tool is repairing is the comparison-with-one-witness problem again.

## Footnote markers

**In TEI, no whitespace immediately before a `<note>`.** The element stands in for
the printed marker, and the book sets a thin space before the raised digit
(`1-100`: `[albino] ¹)`). That is the same class of thing as the French spacing
before `;`/`:` that §2.9 already overrides — a typesetting convention with no
lexical content, which survives nowhere in the book's meaning and which leaves a
stray space in the reading text of every consumer that strips the marker. Key it
tight. `harness validate` errors on it; it is a question about where an element
sits rather than about a character sequence, so `normalize` — which runs over whole
files as text and cannot see that the space precedes a `<note>` rather than a word
— is the wrong place for it.

**The book anchors footnotes with a raised digit; the corpus keys the Unicode
superscript, never the plain ASCII one** (`keying_spec.md` §2.10). A marker keyed
`1` for `¹` is the *right number*, so it reads as correct everywhere and no
lookalike grep, lexicon lookup or mark licence can see it. Five of the 20 restored
pages carried the defect; 16 markers were corrected.

Counting is the only mechanical witness, and numbering restarts every page, so two
invariants hold with no reading required: the markers form a **continuous run from
1**, and each occurs **at least twice** (body reference + note opener). A third
check catches the **half-open pairing** — a line opening with a bare digit, *but
only once a superscript has appeared earlier in reading order*. The superscript is
what establishes the page's own convention; against it a bare digit is an
inconsistency rather than a guess. Without that condition the rule fires on
ordinary prose (`1-053` wraps "…Nordquist, / 2 houses)." mid-gazetteer on a page
with no footnote 2 at all), and a permanent known-false hit is exactly the noise
that buries real signal. Position on the page is deliberately **not** used: some
pages are half footnotes and the scan will not carry that judgement.

Report-only, in `normalize`'s `footnote_markers` bucket at the `lookalikes` tier —
both counting invariants break legitimately at a page seam, where a note's
reference and its text land on different pages with nothing miskeyed.

**Known limit**: a page keying *every* marker as ASCII has no superscript to
establish a convention, so it passes clean. That is what a freshly recognized page
looks like, since CATMuS emits plain digits — so this is a consistency gate on
human-keyed text, not a net for machine output.

## Dropped lines

**The segmenter drops whole printed lines, and nothing text-level can see it.**
Whatever text is present is correct, so no lookalike grep, lexicon miss, mark
licence or CER figure disagrees with anything — the page simply has less on it than
the paper does. `1-053` reached restored ground truth missing a two-line closing
paragraph, found only because the footnote-marker check reported a marker whose
body reference did not exist.

`harness lines PP-NNN --gaps` is the detector: row-wise ink off the raster, masked
by the existing line boxes *and* by `gt/fig/` zones, contiguous bands reported with
measured geometry. It found **three** of the 20 restored pages and was silent on
the other seventeen. All three are now repaired and the corpus reports **zero**:

- `1-053` — two body lines, a whole closing paragraph. Its `¹` body reference was
  on one of them, which is why the footnote check saw an unpaired marker;
- `1-048` — the centred `CHUKCHEE.` heading, on a page that had been revised and
  restored the same day without anyone noticing;
- `3-005` — the centred `AFFINITY.` heading, 23 px of ink and the smallest
  confirmed dropped line in the corpus.

**The two headings are a class, not accidents** — short, centred, small-caps
section headings — so expect the same across the remaining 812 pages. Figure zones
must be masked or every illustrated page reports its own artwork (`3-006` gave 12
bands, `2-030` two; both go to zero). It is report-only and deliberately **not**
folded into `normalize`: reading rasters costs ~0.19 s/page against that gate's
0.83 s for the whole corpus, so it belongs in the per-page loop and in deliberate
sweeps. `--blot` is the visual counterpart — the page with every line box and zone
painted out, so what remains is uncovered by construction and no threshold can
hide it.

**Repair needs a second writer into `gt/ocr/`, and that is worth stating plainly.**
`restore` only writes `CONTENT` into lines that already exist, so a dropped line
has to be *created* before it can be keyed. `harness lines PP-NNN --adopt-gap VPOS`
does that, and it is the one tool besides `restore` that writes into the ground
truth store. What keeps it inside the rule rather than an exception to it:

- **geometry only, never `CONTENT`** — every `String` it creates is empty, and text
  still arrives solely through `decision.json` → `restore`;
- the target is resolved to `gt/ocr/` **explicitly**, never through the `ocr/` view;
- a `VPOS` that is not a measured band is refused, so geometry can never be
  hand-entered; and a band overlapping an existing line is refused rather than
  duplicated;
- the new `TextBlock`/`TextLine` carry a **`gap_` id prefix**, so a recovered line
  is identifiable from the ALTO alone — provenance travelling with the data, as
  everywhere else here;
- it appends at the end of `PrintSpace`, so the new line takes the highest index
  and nothing is renumbered. Output is in reading order anyway, so it still
  *displays* in its right place.

Between `--adopt-gap` and adjudication the page holds geometry with no text, and
`restore` refuses it ("N lines have no decision"). That is correct — a partial
restore is ground truth with invisible holes — but it means a repair is one
uninterrupted sequence, and that **a save is not the end of it**: the page can sit
adjudicated-but-unwritten, looking finished from outside, with `normalize`
correctly continuing to report it.

**The page count was never the point.** Recognition fine-tuning is off the table, so
no model waits to train on these, and gloss review runs off TEI provenance rather
than ALTO ground truth. The deliverable was the *correction workflow* — the crops,
the review page, the keyboard, the decision log and the error profile it yields.

# Harness

The collation loop runs in Claude Code. `harness/` is a small package exposed as
a console script, run from the repo root — all paths resolve relative to the cwd
unless `--root` says otherwise. `uv run python -m harness <verb>` is equivalent
if you ever need it.

    uv run harness pages              refs with OCR present
    uv run harness context PP-NNN     the input contract, on stdout
    uv run harness validate PP-NNN    the gate; exit 1 on FAIL
    uv run harness header             the gate on tei/corpus-header.xml — that the
                                      ranks it declares are exactly the ones
                                      validate enforces. Two files hold one fact and
                                      a page never resolves @resp locally, so
                                      without this they drift silently. Exit 1 on FAIL
    uv run harness ids PP-NNN         structural ids against the scheme
                                      {kind}-{PP-NNN}-{ordinal}, the ordinal being
                                      the element's *position* among same-kind
                                      elements — so every id is recomputable from
                                      the tree. --pair links each <gloss> to its
                                      <term> where containment decides and refuses
                                      where it does not; --fix renumbers, repairing
                                      a neighbour's inbound @prev/@next too
    uv run harness seam PP-NNN        --continues / --fresh: does an element run
                                      across the gap BEFORE this page. Writes
                                      @part on this page's first top-level element
                                      and the previous page's last. The page after
                                      the gap writes both ends, being the only one
                                      holding both witnesses; --commit to write
    uv run harness state PP-NNN       one page's seam record
    uv run harness ledger             the whole seam table; --part N to scope,
                                      --untranscribed for bare refs to work on
    uv run harness toc-search TEXT    ToC entries matching a heading you've read
    uv run harness toc-near FOLIO     ToC entries around a folio you now know
    uv run harness authority TEXT     works in data/authorities.json matching a
                                      citation read in the body — the siglum, a
                                      bare name in prose, a title, or a string
                                      off the printed entry, ranked by which of
                                      those caught it and never collapsed to one.
                                      A footnote form ("Dall, I, p. 375.") goes
                                      in whole. --sigla is the resolution table
                                      (one row per cited_as, so the collisions
                                      show), --key one record in full, --unlocated
                                      the 36 with no copy located
    uv run harness lexicon            frequent lexicon misses, to whitelist;
                                      --native --marks --suffixes --digraphs
                                      invert it into corpus-frequency reports
                                      over restored ground truth; --glosses is
                                      the term↔gloss dictionary from committed
                                      TEI, resolved through @target and never
                                      through containment — terms nobody linked
                                      are a count, not a guess. Each pair also
                                      carries the `scope` its gloss list frames
                                      it with, followed across a seam via @prev
    uv run harness lines PP-NNN       per-line id + geometry + text, **reading
                                      order**, empties kept; --crops and --sheets
                                      write PNGs and labelled contact sheets into
                                      the page's own review/PP-NNN/ (both are flags,
                                      not paths — `--out` is the one-off escape),
                                      --from DIR picks the store, --full adds
                                      baseline/polygon, --margins widens to the
                                      PrintSpace, --gaps reports ink no TextLine
                                      covers (the dropped-line detector),
                                      --adopt-gap VPOS materializes a measured band
                                      as an empty TextLine so it can be keyed,
                                      --blot writes the page with lines and figure
                                      zones painted out into scans-blotted/
    uv run harness zoom PP-NNN        magnified lines: --only 7,20,22-26 selects,
                                      --zoom N scales (default 2), overlapping
                                      strips packed into as few sheets as fit.
                                      The window is derived from --zoom, so it
                                      never needs setting; --margins here too
    uv run harness review PP-NNN      span diff of a proposal against the
                                      recognizer, as *measurement*; --serve runs
                                      the line-based browser review on 127.0.0.1
                                      and saves to review/PP-NNN/decision.json
    uv run harness restore PP-NNN     preview only (edits, drift, mismatch);
                                      --commit required to write gt/ocr/
    uv run harness clean PP-NNN       rm review/PP-NNN/{crops,sheets,zoom} —
                                      the regenerable images, once restored
    uv run harness normalize          NFD + §2.9 spacing + lookalike + footnote-
                                      marker gate; exit 1
                                      on drift; --path FILE scopes to one file
                                      instead of the whole corpus (repeatable).
                                      Report only — bare form and --check are the
                                      same thing; --convert is required to write,
                                      scoped or not.
    uv run harness proposal-check PP-NNN   a proposal's `resolved` field against
                                      the codepoints its `text` actually has.
                                      Also the field editors — --codepoints,
                                      --set, --replace/--which — which exist so
                                      that inspecting or patching a proposal
                                      never needs ad-hoc Python. `--help` for
                                      the full contract
    uv run harness figures            reconcile gt/fig/ zone geometry against
                                      data/readings.md captions, both ways;
                                      exit 1 if `missing` or `orphan` is non-empty
    uv run harness zones              the seven-type page segmentation in
                                      gt/zones/. Bare, it sweeps every keyed page
                                      (add --ink to read the rasters too); with a
                                      ref, that page's errors and warnings in
                                      full. Exit 1 on an error, never on a
                                      warning. --serve opens the editor at that
                                      ref and keeps serving, the arrow keys
                                      walking the corpus from there.
                                      --itinerary LST replaces scan order with a
                                      work-list — an .lst in gt/seg's format, or
                                      a directory meaning every page in it — and
                                      with --serve resumes at its first unkeyed
                                      page. --blot writes the figure-blotted
                                      training rasters; --assemble lays out
                                      train/bogoras-seg/ for ketos and reports the
                                      invocation, omitting --resize when the class
                                      sets already match; --install CHECKPOINT
                                      scores a run, refuses a permuted class map,
                                      and writes it to models/bogoras-seg/ with the
                                      split it saw beside it.
                                      --predict runs the trained segmenter into
                                      mz/zones/ (--model, --device); --link
                                      rebuilds zones/, the view over both stores;
                                      --from gt|mz picks which store is checked —
                                      gt gates, mz is measurement and exits 0.
                                      --score compares against gt per split, never
                                      blended, with the confusion matrix and a
                                      held-out permutation test; with --model it
                                      segments in memory and writes nothing, which
                                      is how a checkpoint is measured before it is
                                      installed. --remap-model (--commit) renames
                                      the output channels when that test says the
                                      labels are shuffled rather than the model
                                      weak. --decode dp swaps blob vectorisation
                                      for a segmental DP over the page.
                                      --paragraphs audits the paragraph rule both
                                      ways; --diff reports gt against mz; --lines
                                      dumps a page's lines of type. A page's zones
                                      now print by default

Output is **TOON**, not JSON — a tabular encoding that collapses uniform record
lists to a header row plus data rows (the ledger went 127 KB → 34 KB, the page
context 8.0 KB → 3.6 KB). `--json` on any verb restores indented JSON for
anything that needs to parse the output as a contract. Anything emitting a list
of records keeps one fixed key set across them, because a ragged list silently
degrades to the verbose nested form.

Every verb that names a page takes a `PP-NNN` ref and rejects a bare integer,
`state` included.

**No ad-hoc Python for anything the harness already does.** Not `python3 -c
"...ord(ch)..."` to check a character's codepoint (`proposal-check
--codepoints`), not a crop script to magnify a glyph (`harness zoom` — see
`rebuild-groundtruth`'s SKILL.md on why 4× is already the ceiling and a
hand-rolled crop cannot see past it), not a heredoc to patch one field of a
JSON file (`proposal-check --set` — a hand-typed `Edit` can silently fail to
match this file's own NFD form). A one-off script is a tell that a tool is
missing or that an existing one is being under-used; the fix is to reach for
the verb, or extend it, not to route around it. This has been stated and not
followed more than once in this project's own history — see
`rebuild-groundtruth`'s SKILL.md for the concrete cases.

**Doc precedence.** This file is authoritative on the project — the invariants, the
data layout, what is settled and what is open. It is deliberately **not** the place
for how a pass is run; that belongs to the skill for that pass, and detail that
accumulated here has been moved out rather than duplicated.

| document | owns |
|---|---|
| `CLAUDE.md` | project invariants, data layout, what is settled and what is open |
| `keying_spec.md` | the character inventory. Binds both passes and the human keying track |
| `.claude/skills/transcribe-page/` | the OCR→TEI collation loop, rules included — it has no separate harness doc |
| `.claude/skills/rebuild-groundtruth/` | the raster→ALTO reading loop, rules included — it has no separate harness doc |
| `.claude/skills/train-zones/` | the segmenter's train→score→install loop, and the judgement in it: reading a train/eval gap, when a class is too rare to keep, why the ketos metric is not the number |
| `harness/README.md` | the package: module responsibilities, stores, caller invariants |
| `concordance.md` | the evidence set behind the spec — aligned pairs, flag register, per-glyph attestation |

Two passes, and they are not the same job: collation (OCR → TEI, output `tei/`) and
the ground-truth loop (raster → ALTO, output `gt/ocr/`). The latter is now a
*revision* pass rather than a rebuild, every page having been restored.

# Current pipeline

## Pages

1. **Segmentation** — LADaS D-FINE (medium). These regions have **no semantic value** and are only used to impose a reasonable reading order and make the OCR plaintext more coherent. Semantic "segmentins" are the preserve of the **Collation** stage.
2. **Recognition** — CATMuS. `models/` holds only stock CATMuS (large + tiny); the fine-tune referred to in earlier drafts is not in the repo. Establish which model actually produced a given page before drawing conclusions from it — and note the fine-tune is no longer the plan: measured against a human key it reads **0% of the inventory** (see Collation), and its competence ceiling would be the same 20 pages it trained on, so agreement with it would be the editor's own judgement laundered through a checkpoint. Stock CATMuS is retained as a cheap second witness to geometry and English.

   **Consequence worth stating because it reads as success: a detector census over
   "the 20 GT pages" was really a census over two.** At the start of the rebuild, 17
   of the 20 were empty shells (11 still are), so they reported zero flags because
   there was nothing to flag, not because they were clean. Any baseline taken before
   a page's own rebuild is worthless for the same reason — `1-074` went from 0 flags
   to 15 `inventory_glyph` the moment it was restored.
3. **Collation** — An LLM (usually Sonnet-class) receives 1) the image of the original scan, 2) the OCR plaintext for that page, and 3) a machine-generated summary with useful contextual data (relevant TOC entries, list of page figures, etc.). It outputs TEI for that page. Built by `harness context`; gated by `harness validate`. Everything the model receives is deterministic and precomputed — it never re-derives ToC ids, figure zones, or detector flags.
4. **Annotation** — TBD
5. **Compilation** — TBD

## Final Product

1. **Original Scan Page** - `scans/chukchi-PP-NNN.png`
2. **Figure geometry** - `gt/fig/chukchi-PP-NNN.xml`. ALTO containing only `GraphicZone` and `GraphicZone-FigDesc` blocks. No lines, no text.
3. **Figure captions** - `data/readings.md`, keyed `1-123|<zone-id suffix>`. The only caption store.
4. **OCR transcript** - `ocr/chukchi-PP-NNN.xml`. ALTO XML files containing (useless) segments and text lines, which will be dumted to plain text
5. **TEI** - `tei/chukchi-PP-NNN.xml`. Also the system of record for seam state:
   its `<pb>` is where the printed folio enters the project, and `harness ledger`
   folds the committed files into the per-ref ledger the next page is built from.
6. ???
7. PROFIT!

# Figure track

The 252 pages with figures have been segmented to isolate `GraphicZone`s and
`GraphicZone-FigDesc`s — **414 zones and 395 captions** in `gt/fig/`, one
`data/readings.md` block per caption, reconciled in both directions by `harness
figures`. Figure images will be auto-generated by the build. Specifics TBD.

**A total that matches is not coverage**, and this track is where that was learned:
the count sat at 250 pages while two were missing, because 250 was also what the
List of Illustrations implies, and the two absences cancelled exactly against
`3-006`/`3-007`, which carry a zone and no caption and are not LoI pages at all.
Only the per-entry check catches that. It now passes: every LoI text-figure
**1–302** has a reading, no reading cites a figure number outside the LoI, and all
**35 plates I–XXXV** are located. 91 LoI plate segments map to 93 caption blocks,
and all four deviations are known — Plate II (the LoI makes the shared "Anui Fair"
its own segment where the page prints it twice) and Plates XXXII/XXXIII/XXXIV (four
printed figures against three segments, two sharing a caption on each).

Figure images are cropped from `scans/`. Note that the ~300 dpi master is the
*text* layer only — the photographs are embedded JPEGs already at their native
150 dpi, so re-rendering the page at 300 dpi upsamples them and adds no detail.
Their bboxes matched the embedded JPEG dimensions exactly at 150 dpi, which is a
free check on the segmentation if ever needed.

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

`harness context` surfaces these as `figures_on_page` — zone id, type, bbox, and
the caption `text` pulled from `data/readings.md`. The collation pass anchors
`<figure facs>` against those zone ids and the validator rejects any that match
no supplied zone. A Tier-1 span may optionally also carry `@facs` pointing at
the OCR line(s) it was read from (`harness context`'s `ocr_lines` field
supplies the ids, sourced from `ocr/` — resolve one with `harness zoom PP-NNN
--only <index> --from gt/ocr`, not zoom's default store); `validate.py` checks
it resolves the same way it checks `<figure facs>`. See the collation skill's
"`@facs` — flagging a span worth a second look" for the full rule. Only 3 of the 20 OCR'd pilot pages also have figure ALTOs —
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

`harness authority` is the reader. It searches `cited_as`, then `author`, then the
titles, then the printed blocks, reports which of those caught each hit, and
**returns all of them** — 51 sigla over 34 names means a single answer would be
manufactured, and no hit at all is a legitimate outcome on an open list. It
resolves nothing; a human reads the candidates.

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
zoom` and `harness lines` cannot reach them, and no verb magnifies an arbitrary
region of a page outside the pilot 20.

**Cyrillic `й` is `и` + U+0306 by canonical decomposition**, so corpus-wide NFD turns
every Russian word into base+mark sequences and `unlicensed_marks` once reported all
72 as errors — `MARK_LICENSE` is written for the Tier-1 Latin notation but runs over
every character in the corpus. `и`/`И` are licensed breve bases, as allow-list
entries and deliberately **not** as a "consult the table only for Latin bases" script
test: that states the scope more honestly but decides it by inference, and each
unbounded corner case would be a silent skip in place of a loud error. Note `ё` =
`е` + U+0308 needs no entry only because U+0308 has no licensing table yet; give it
one and this recurs. Regression test: `tests/test_marks.py`.

# Collation

Process and rules: `.claude/skills/transcribe-page/SKILL.md`, which carries both —
it has no separate harness doc, the same shape as `rebuild-groundtruth`. Loop:
`/transcribe-page PP-NNN`.

**The LLM has the authority to:**

- Correct **English and Russian (and other European languages, where they show up) misspellings and orthographic mistakes**. OCR has persistent trouble with quotes, brackets, and numeric superscripts in this text.
- Join hyphenated words (in **European languages** - hyphens are load-bearing in Americanist notation).
- Resolve basic textual features like small-caps and footnotes.

**Chukchi, Koryak and "Eskimo" (Yupik) forms are keyed character by character from the
page**, enclosed in the appropriate `xml:lang` tag with a `@resp` rank. Every mark is
read and accounted for; where the letterform does not decide, `<unclear>` says so.

The prohibition on correcting these forms is **not** a lowered bar. It raises it, and the
repair pass is the reason rather than the exception. `@resp` exists so that every
unratified span is *findable* — a query over the corpus returns exactly the Tier-1 forms
awaiting a human, which is the whole design. What it cannot do is tell that human which
character is wrong. Repair means one editor back at the raster at magnification, with no
second witness available: CATMuS reads 0% of the inventory, there is no dictionary and no
competent second reader for these forms. So the pass is single-witness and paid for in the
scarcest resource here, and its input quality sets its cost.

The error class that survives review is the one with no internal signal. A dropped mark
inside an otherwise plausible form reads as correct in the TEI, so nothing flags it and
only re-collation against the page finds it. `1-074` is the measurement: two dropped U+0323
under a `g`, neither caught by my own re-read, both caught by the editor. "Don't normalize"
therefore means *read harder*, not *worry less* — an unexpected form sends you back to the
raster to settle what is on the paper, never to file the oddity as authorial and move on.

**Transcription Detection** (speculative, mechanical, no judgement): inventory-glyph match ∪ word-medial
  `[AEIL]` ∪ dot-above-g ∪ apostrophe-adjacency ∪ **English-lexicon miss**. The
  numerator is a floor — unmarked ASCII inventory members (`c` = English *sh*, plain
  `s`, `j`, `x`) are undetectable by construction, which is itself an argument for
  route-all over per-glyph triage.

  A floor is not licence for noise above it: a detector firing on ordinary English
  buries the real hits, and where a hit suppresses a later check it masks them.
  `data/lexicon_extra.txt` (committed, human-editable, seeded from real counts via
  `harness lexicon`) holds the Latin binomials, ethnonyms and coinages no general
  dictionary carries. **It suppresses `lexicon_miss` and nothing else** — and it
  cannot do otherwise, since `lexicon_miss` only ever tests ASCII components, so a
  Tier-1 form listed there is inert by construction rather than by discipline.

**Density, measured** on `1-048` and `2-030` — the two densest pages, so a ceiling
and not an average. Inventory glyphs are **3.3% of characters** but fall in **43.8%
of lines**.

That asymmetry decides tool shape, and it was got wrong once. The 3.3% argues for
reviewing spans; the 44% says those lines get opened anyway, and once a line is open
reading the rest of it is nearly free — the expensive act is re-orienting to a
different line, not reading characters in one already in front of you. **So review
is line-based**, and the span diff survives only as measurement.

**What CATMuS can and cannot read**, measured against the human-collated
`tei/chukchi-1-151.xml`: aggregate CER 8.6%, but that blends two unrelated things.
Its ASCII is ~91% right and **its inventory is 0% right** — of the human text's 41
non-ASCII characters it produced 13, not one an inventory glyph, losing all the
Cyrillic, all 5 × U+02CA, all 3 × `ɪ` and the single `ᵋ`. So it is a witness to line
geometry and to English and to nothing else. That 0% is what killed the old
verbatim-substring firewall: all four Tier-1 spans in that TEI failed it, on a page
whose readings are correct. Its substitutions are worth knowing when adjudicating:
`'` `’` `/` for `ˊ`, `i` `I` **`r`** for `ɪ`, `f` for `ᵋ`, dropped combining tildes,
and one U+0301 — the corpus's only combining acute, and a pair `LOOKALIKE_GREPS`
does not trap.

## Cross-page state

The collation pass is strictly per-page — one page per task, fresh read, no
impressions carried in the model's head. What legitimately crosses a page
boundary crosses through the **committed TEI**, folded forward by
`harness ledger` into a per-ref table (`harness state PP-NNN` for one page's
entry into it):

- **folio** — from the page's `<pb n>`. `<pb/>` with no `@n` asserts the page
  carries no printed number (plate, blank, chapter opening), so it doesn't
  advance the count.
- **open headings** — the fold over committed `<milestone>`s; resets at each part.
- **boundary** — whether an element carries across the gap, recorded as `@part` on
  the two elements it lands on, one per page. `harness seam PP-NNN --continues`
  writes both. **There is no `boundaries.json`** — the committed TEI is the record,
  not a materialization of a sidecar, and the I/M/F arithmetic reads back out of
  the files it wrote to. See below.

`harness context` supplies **`prev_tail`** — the previous page's last top-level
element, as **markup, not a text excerpt**. The markup is where the witnesses are:
`<item n="14">` is what settles whether the list resuming at 15 on the next page is
the same list, and a flattened tail throws it away along with every `xml:lang`/
`@resp` in play at the seam. Trimmed by dropping whole leading children so the
fragment always parses, with the elision stated rather than implied. `null` when
the predecessor is not collated — the same case `harness seam` refuses.

`ends_sentence` rides along as a **hint, never a verdict**, and the live seam says
why: `1-100` closes its numbered list at item 14 with a full stop and `1-101`
resumes it at 15. Absence of a terminal stop is positive evidence; presence of one
is only the lack of it.

The next page's context is built from that ledger. `expected_folio` is the last
numbered predecessor's folio plus one and is **null wherever the chain breaks** —
an untranscribed predecessor, the first scan of a part. Null is the correct
answer, not a defect: it means read the folio off the page. Likewise `toc_window`
is a *neighbourhood* of ToC entries marked `open`/`starts_here`/`distance`, not a
resolved set — the marks are keyed to a predicted folio and inherit its errors,
so they say where to look and the page decides. Errors here don't cascade: the
next legible folio re-anchors the chain.

Practical consequence: working in scan order gives live folio predictions;
jumping around gives nulls until gaps fill. Both are fine.

## TEI

TBD beyond the per-page output contract in the collation skill (`<pb>` first, no
`<div>`, no `<lb/>`, minimal teiHeader, footnotes anchored at their markers,
figures anchored to supplied zones). **Assembly is still unsettled**; the
corpus teiHeader is not, and is `tei/corpus-header.xml`.

**A gloss list's shared frame lives on the list, once.** The prose introducing a
gloss list routinely supplies a frame the entries never repeat — `1-100` announces
"the following colors of reindeer-skin", and `Qeˊñu` is then glossed `“white mixed
with brown”`, which in a dictionary says nothing about what is white. That frame is
written as a **supplied `<head>`** on the list (`<supplied reason="context"
resp="#llm">`), never copied into the glosses, and `harness lexicon --glosses`
resolves it into a `scope` column beside every entry.

A continuation list carries no head of its own: the scope resolves back through the
`@prev` the seam wrote, which makes `ids.list_scope` **the only thing in the harness
that traverses those pointers** rather than checking one hop. `validate` cannot see
a cycle in them for the same reason, so the walk is capped.

**`@type` on `<gloss>` says what kind of gloss the book printed, not who wrote it.**
A term routinely carries a sense gloss *and* a literal one and the page cues which
— `1-039`: `Pnauˊkulɪt (“file-mongers,” from pnauˊkun, “file” [literally,
“whetting-stone”])`. Two declared kinds, `literal` (cued by *literally*) and
`etymon` (cued by *from*, holding the source form together with whatever
translation the print runs into it, because the instances are too varied to split
those apart without inventing structure). Unmarked is the ordinary sense gloss.

Provenance moved off that attribute to make room: **a gloss nobody printed is
`<supplied>` inside the gloss**, which is the TEI idiom and the same mechanism the
scope above uses, so one attribute carries one axis. A `<gloss>` never carries
`@resp`. Two related rules the pages taught: a gloss spans its **full printed
extent** rather than stopping at the quotation marks (`Ñireqäˊulɪn ([“one of the
second time”] male) … from four to five years old` is three glosses, not one), and
`@target` is a **URI list**, since the age range there is printed once for the male
and female forms — `page_glossary` read the attribute whole and silently dropped
every such gloss until this was fixed.

`<supplied>` is gated for the reason the old rule existed — unmarked, authored text
is indistinguishable from transcription — with two deliberate differences. `@reason`
is required from a closed set (`context`, `ellipsis`), because a required attribute
with a free value guarantees a string rather than a distinction. And the
`#llm`-only rule does **not** extend to it: that exists because a pass may not
promote a *glyph identity*, and supplied English contains none, so a human writing
one and marking it `#ed` is legitimate.

Two consequences worth knowing. The head is the list's first child and TEI orders it
before the items, so it is the first thing `seam._fragment` elides from `prev_tail`
— the next page's pass meets the frame through `foreign_terms_nearby`'s `scope`
instead. And `<head>` on a `<list>` means the list's *heading*, which "of a
reindeer" is not; it is the only conformant slot (`<desc>` is not permitted there,
and `<note>` is already claimed by footnotes), so **a renderer must check for
`<supplied>` before printing a list head as a caption**.

**Proper names are marked by category, never by identity, and only in Tier-1.** A
Chukchee form the page identifies as a name gets `<name>` in place of `<foreign>`,
keeping its `xml:lang` and `@resp` so the existing provenance and lookalike checks
reach it unchanged. `@type` is written only where the page says — a closed set
`anthroponym ethnonym toponym hydronym zoonym mythonym`, usually evidenced by the
gloss or the sentence around it — and **untyped is a real state rather than an
unfinished one**, findable by one XPath. `zoonym` is there because a herding people
names its reindeer and `1-101` is a whole paragraph about the practice; `mythonym`
rather than `theonym` because the book names supernatural beings that are not gods.

Two things the gate cannot check and the pass has to hold to. **A generic noun is
not a name**: `keˊlᴇ`/`keˊlet` and `reˊkkeñ` are *kinds* of evil spirit, hence common
nouns and `<term>`, and being Tier-1, capitalized and otherworldly makes a form none
of a proper noun. That distinction outranks the type, since a wrong `@type` is a
mislabel where a spurious `<name>` invents an entity. And **a type comes from the
page, never from the form** — among one otherworldly-looking group of spans, one is
a god, one a village, one a person and the rest common nouns, with nothing in the
shape of the words to separate them. `tier1_spans` flags keying risk and carries no
class information, so it cannot be mined for this.

The scope is the decision worth recording. English and Latin proper nouns —
`Chukchee`, `Anadyr`, `Phoca hispida` — are **not** marked here. They are a string
match anything can find over finished TEI, and `data/lexicon_extra.txt` already
holds the seed lists (ethnonyms, toponyms sub-typed by comment heading, genus and
species, and `Pallas` under a `## Authorities` heading distinguishing the describing
authority from the name). Hand-marking them per page would buy automatable coverage
with thousands of judgements and the errors in them. **The binomials are the natural
first target for that automated pass**, being a more regular pattern than the
ethnonyms; its two wrinkles are trinomials and abbreviated genus (`P. hispida`),
both easier with a whole page in view than a line.

Hence no `taxon` in the type set: a declared type nothing writes is dead surface in
the gate. TEI has no biological-nomenclature element at all — checked against the
element index; `<taxonomy>`/`<category>` classify *texts* — so `<name type="taxon">`
is what that pass would use if it ever wants one.

**`@ref`, `@key` and `@nymRef` are gate errors.** Identity resolution is the
annotation pass's, over finished TEI with the whole corpus in view, and this makes
the deferral checkable rather than a line in a skill's never-do list.

**`name` is a fourth id kind**, alongside `term`, `list` and `table`, earning its
place the same way they did — by acquiring a referrer. `1-101` glosses two reindeer
names in running prose (`Mushroom-Eater (Poˊñolɪn)`), and containment decides that
pairing no better than it decides a term's. `harness lexicon --glosses` carries a
`kind` column so a proper name is separable from a common noun without re-parsing:
an index of toponyms is that column filtered.

**The id scheme is settled and is `harness/ids.py`** — `{kind}-{PP-NNN}-{ordinal}`,
where the ordinal is the element's *position* among same-kind elements in document
order rather than a tally of ids minted. That distinction is the whole design: ids
are sparse (only where something points at one), every id is a total function of
the tree and so recomputable without reference to any other file, and adding a
referrer to one element never renumbers another. The blanket ban it replaced was a
real concern about *arbitrary* ids generalised into a prohibition, and it gated
three unrelated things at once; what replaces it is a check, because **a checkable
rule beats a prohibition — it does not depend on the pass behaving.**

Two consequences worth knowing before writing one. The ordinal is **not** the
printed item number: `1-100`'s item 4 holds two `<term>`s, so item 5's term is
`term-1-100-6`. And an id names the page it lives on — checked, because `prev_tail`
now hands the pass the previous page's markup with its ids in it, and a copy-paste
would otherwise import a foreign id in silence.

**The header is a fragment, like the page files.** A bare `<teiHeader>` in the TEI
namespace, not a valid TEI document standalone — `teiCorpus` requires at least one
`TEI` child, so there is no conformant container for a header alone and inventing
one would mean settling the assembly scheme by accident. `harness header` gates it,
and what it checks is the *correspondence* with `validate.RESP_RANKS` rather than
the prose: exactly those three ranks, declared as `respStmt/@xml:id`, no more and
no fewer. Two files held one fact and nothing linked them — per-page validation
deliberately never resolves `@resp` locally, so either could have been renamed and
every page would have gone on passing.

**Licence: two, because this is not one work.** The transcribed text is **CC0** —
a faithful transcription of a 1904 book carries no fresh copyright (EU DSM Art. 14;
US law has never protected slavish reproduction), so licensing it CC BY would assert
a right the edition does not hold, which is the provenance overclaim pointed at the
law instead of at the glyphs. The apparatus — `loi.json`, `toc.json`,
`authorities.json` and their research, the TEI structure, the adjudications, the
annotation layer — is original editorial work and is **CC BY 4.0**. Scopes are
stated on each `<licence>`; where a reuse cannot separate them, treat it as CC BY.
`harness header` errors on a settled `@status` granting no `<licence>` at all, that
being the one licence state that reads as finished while saying nothing.

**Bibliographic detail in the header was read off the rasters, and the witnesses
disagree.** The title page (`1-005`) gives the Jesup series as Volume VII and names
no Memoirs volume; "Volume XI" comes off the parts' archival sheets and off the AMNH
catalogue. Both series statements are recorded, since dropping either makes a
citation in it unresolvable. `@source` in the header points at the catalogue record,
`@resp` only ever at a model's reading of a raster — the rank machinery is about
reading pages and says nothing about a catalogue's authority.

## Annotation passes

TBD

## Open

- **No part is named by a part title page** — the surrogate has none. Parts II and III
  are named by librarian typescript over an archival sheet that contradicts itself
  (typed 1907/1909 against a printed 1904 imprint), and part I only by the AMNH
  catalogue record, which is its single witness. The catalogue corroborates II and III,
  so those are settled; part I is not, and a copy with part title pages would beat all
  of it. See the teiHeader's `listBibl`, where `@source` points at the catalogue and
  `@resp` is reserved for the model's reading of the rasters.
- **The AMNH catalogue record independently corroborates two apparatus stores**, having
  been consulted for neither: `"Authorities quoted": p. 3-9` against
  `data/authorities.json`'s folios 3–9, and `35 pl.` against `data/loi.json`'s plates
  I–XXXV. Cheap second witnesses, and both agree.
- **The ratified build does not exist.** The `--ratified` mode of `validate` reports an
  unratified span as a worklist line, which is the right shape for a page in progress
  but is not a gate: nothing yet *refuses* to publish a `#llm` span. Until it does,
  provenance is recorded and inspectable but not enforced downstream.
- **The skill's page-edge prohibition is still untested, and `1-101` did not test
  it.** The English-correction licence used to permit completing a sentence or
  capitalising a first word at a page edge, which destroys the seam's own text
  witness invisibly. It is now forbidden in prose, and prose is all it is: unlike
  the provenance rank, nothing mechanical can see a page whose opening word was
  quietly capitalised. `1-101` opens on a numbered list item resuming at 15, so
  nothing there tempts a completion — the rule was written for a page opening
  lowercase mid-sentence, which is what `1-100` does, and `1-100` was collated
  before the rule existed. **A page opening mid-sentence, collated after it, is
  the evidence still wanted.** 69.8% of text pages qualify, so the next one in
  scan order will probably do.
- **A note running across a page seam has no markup.** `<note>` is nested rather
  than a top-level body element, so `seam`'s two-sided-edge machinery does not
  reach it, and the pilot set has no attested instance — so it is deliberately
  unresolved rather than built for. The orphan-foot-text comment names no pass.
- **Corpus-stable identity is not settled**, and the id scheme deliberately does
  not provide it: ordinals move when content is inserted, so a pointer held
  outside the page would break silently. These ids are stable within a page file's
  current version and nothing outside the corpus may cite one. The annotation
  passes need their own scheme, over finished TEI. What has changed is the *scope*
  of what is deferred: a Tier-1 name's **category** is now recorded by the
  collation pass, because only a reader of the page can see it, and only the
  **identity** waits — `@ref`/`@key` are gate errors until that scheme exists.
- **Nothing validates the TEI against the TEI schema.** `harness validate` checks
  *project* rules; there is no RELAX NG, no `tei_all`, no schema anywhere in the
  repo. That now covers nine attribute usages nobody checks for conformance —
  `@part`, `xml:id`, `@target` (including its list-valued form), `@prev`, `@next`,
  `@type` on `<gloss>`, `@reason`/`@resp` on `<supplied>`, and `@type` on `<name>`. It
  needs no new dependency (`lxml` has `etree.RelaxNG`); what it needs is a
  committed schema and an assembly step, since a page file is a fragment and will
  not validate standalone.
- **`data/toc.json` (315 entries) records no provenance.** `loi.json` and
  `authorities.json` both name the scans they were read from; this one does not,
  and the printed ToC's scan range is not recoverable from the file. Someone who
  knows should write it down — every other apparatus store is auditable back to a
  page and this one is not.
- **`harness review`'s bare span diff has no second witness left.** `end-of-eval/`
  was the recognizer store and is deleted, so the diff now refuses rather than
  compare a proposal against the ground truth it produced. The `--serve` review
  page is unaffected and remains the correction loop. If a second witness is ever
  wanted again, it links into `ocr/` from its own store.
- **The segmenter is measured, and this is where it stands.** Run 3 —
  `models/bogoras-seg/zones-seg.safetensors`, 211 train / 60 eval — scores **94.7%
  recall and 90.8% precision on held-out pages**, median boundary error 6 px, with
  the segmental DP decode and the paragraph split. Trained-on is 97.0 / 94.2, so the
  gap is ~2 points either way: ordinary generalisation. Strip the 25 `MainZone-Quote`
  rows (the fold working as designed) and the residual is **30 zones of 1692**,
  two-thirds of it `MainZone-P` ↔ `MainZone-Continued` — whether a paragraph opens or
  resumes, which is an indent question no structural change reaches.
  **`unseen` is now zero pages**: everything keyed is in the frozen split, so eval is
  the only held-out evidence until more is keyed.
- **The decode matters more than the model did.** Same weights: blob vectorisation
  gave 61.3% precision, the segmental DP 80.1%, and the DP plus the paragraph split
  90.8%. Two of those three gains cost no training at all.
- **The 271-page corpus is heavily part 1** — 274 of 345 keyed pages, and the last
  121 were a contiguous run of ordinary prose that moved like-for-like eval by 0.2
  points. Parts 2 and 3 have 31 and 40 keyed pages between them. If a future run is
  flat, the question is which *kind* of page is missing, not how many.
- **Why `--resize` shuffled the class names is not established.** The permutation is
  measured, bijective and corrected; the *mechanism* is not proven. Both branches
  assign new class indices by iterating a `set` difference and Python randomises
  string hashing per process, which would do it — but the tail of the `new` branch
  stores the mapping from the same dict the dataset was backfilled with, which
  should be self-consistent. Until someone reads it properly, the standing rule is
  the empirical one: **`--score` after every training run**, and never trust a
  `class_mapping` that has been through `--resize`. See "`--resize` shuffled the
  class names".
- **`models/bogoras-seg/zones-seg.safetensors` carries a hand-corrected
  `class_mapping`.** The
  weights are `ketos segtrain`'s; the names on the output channels were rewritten by
  `--remap-model` from a permutation measured against `gt/zones/`. `.bak` holds the
  original. Anything retrained from this checkpoint inherits the corrected map, which
  is the intent — but a future run under `--resize` can permute it again, and only
  `--score` will say so.
