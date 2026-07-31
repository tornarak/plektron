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
`transcriber_harness.md` and the skill; the comment at the old check's site records why.

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
            current one — seven types, fixed-width bands; empty so far).
    tei/    1 page.
    data/   readings.md  loi.json  toc.json  authorities.json  lexicon_extra.txt
            zones_config.json
    review/ one directory per page, PP-NNN/. proposal.json (a reading, not truth)
            and decision.json (adjudicated) are tracked; crops/ sheets/ zoom/ and
            review.html are derived and ignored. See harness/paths.py.
    models/ blla, CATMuS print (large + tiny), LADaS medium, orli, plates-seg.
    pdfs/   symlinks to the three AMNH source PDFs, outside the repo.
    bogoras-rec/  working dir for recognition runs. Ignored; only trained models
            are kept, and those live in models/.
    scans-w-figs/  scans-w-ocr/   symlinks into scans/. Derived, and ignored:
            they point *into* an ignored tree, so a clone gets dangling links.
    harness/  tools/  tests/  concordance.md  keying_spec.md  transcriber_harness.md

- **The ground-truth rebuild is finished.** All **20** pilot pages in `gt/ocr/`
  carry text — the pilot selection is scattered across all three parts, and
  `harness pages` lists it. `tei/` holds **one** page, `1-151` — collated,
  committed, validating, with two open comments.
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

**The frontier is collation.** `tei/` holds 1 page of 832. The apparatus stores are
done and reconciled — `loi.json`, `toc.json`, `authorities.json`, `readings.md`,
and the 20 pilot ground-truth pages — so what is left is the pass that consumes
them. The first page transcribed from here is also the first test of the provenance
rule (see Open), since `1-151` was retrofitted by hand rather than emitted by a pass
that had read it.

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
  is anchored per page off the raster's own ink profile** (`zones.measure_columns`),
  calibrated against those 20 ground-truth pages, where it lands within 15 px every
  time. That removes the verso/recto distinction entirely — there was nothing left
  for it to do — and leaves a manual ±4 px nudge as the escape hatch for a page too
  blank to measure, plus per-ref `overrides` for two-column settings.
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

**Where it stands: 75 pages, the first two chapters of part 1.** 45 text pages
carrying 282 zones, 30 marked exempt (the covers, front matter and plates of
`1-001`…`1-030`). `harness zones --ink` over the lot returns 4 errors and 3 warnings
on 3 pages, and reading them against the scans is instructive about what each check
is worth:

- All three `uncovered-ink` bands — `1-033`, `1-035`, `1-036` — are **artifacts**: a
  margin smudge, the tail of an ink stain below a footnote zone, and a gutter blob.
  Binarization noise, not type. Report-only earns its keep here; any of them as an
  error would have blocked a correctly keyed page. All three are now ruled in
  `_ink_exempt.json` and still report, flagged and carrying their reason.
- `1-033`'s four `column-position` errors — **the anchor is wrong, not the zones**.
  That page's margin smudge sits left of the text, so the ink profile measured the
  column 52 px too far left and the editor's own reading is the right one. The
  column anchor is currently vulnerable to any dense mark in the margin; a fix is
  open (see Open).

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

## Footnote markers

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
folded into `normalize`: reading rasters costs 0.27 s/page against that gate's
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
                                      over restored ground truth
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
                                      walking the corpus from there; --blot
                                      writes the figure-blotted training rasters;
                                      --assemble lays out bogoras-seg/ for ketos

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
| `transcriber_harness.md` | the collation rule set — output contract, firewall rules, per-element specs |
| `.claude/skills/transcribe-page/` | sequences collation; carries no rules of its own |
| `.claude/skills/rebuild-groundtruth/` | the raster→ALTO reading loop, rules included — it has no separate harness doc |
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

1. **Original Scan Page** - `scans/chukchi-1-123.png`
2. **Figure geometry** - `fig/chukchi-1-123.xml`. ALTO containing only `GraphicZone` and `GraphicZone-FigDesc` blocks. No lines, no text.
3. **Figure captions** - `data/readings.md`, keyed `1-123|<zone-id suffix>`. The only caption store.
4. **OCR transcript** - `ocr/chukchi-1-123.xml`. ALTO XML files containing (useless) segments and text lines, which will be dumted to plain text
5. **TEI** - `tei/chukchi-1-123.xml`. Also the system of record for seam state:
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
it resolves the same way it checks `<figure facs>`. See `transcriber_harness.md`
for the full rule. Only 3 of the 20 OCR'd pilot pages also have figure ALTOs —
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

Process and rules: `transcriber_harness.md`. Loop: `/transcribe-page PP-NNN`.

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
- **boundary** — which element is left open across the gap after this page.
  Geometry-derived from ALTO by a separate continuation pass, keyed by ref in
  `boundaries.json`, not yet built. The per-page pass never writes
  `@part`/`@prev`/`@next`.

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

TBD beyond the per-page output contract in `transcriber_harness.md` (`<pb>`
first, no `<div>`, no `<lb/>`, minimal teiHeader, footnotes anchored at their
markers, figures anchored to supplied zones). The corpus-level teiHeader,
assembly, and id-minting scheme are unsettled. No pass to date mints an
`xml:id` — the continuation and annotation passes will, deterministically.

## Annotation passes

TBD

## Open

- **The column anchor is fooled by ink in the margin.** `zones.measure_frame` takes
  the text column's left edge from the outermost inked column of the page, so any
  dense mark outside the measure moves it: `1-033`'s margin smudge dragged the
  anchor 52 px left and the validator then reported four `column-position` errors
  against zones that are correct. The measurement needs to require ink over a
  minimum *share of the band's rows* — a smudge is tall in pixels but short in rows,
  where a column's edge is inked down the whole page — and `columns.anchor.ink_fraction`
  is the knob. Any change is re-calibrated against the 20 `gt/ocr` pages, where the
  current settings land within 15 px on every one.
- **The corpus teiHeader does not exist**, and it is now load-bearing: it is where the
  three `respStmt` provenance ranks are declared, so every `@resp` in the corpus is a
  pointer with nothing yet to resolve against. Harmless while pages are validated
  individually (`validate` deliberately does not check local resolution), and a hard
  requirement before any assembly step. Ranks are `#ed` / `#llm` / `#htr`, defined in
  `validate.RESP_RANKS`, which is the operative definition until the header lands.
- **The ratified build does not exist.** The `--ratified` mode of `validate` reports an
  unratified span as a worklist line, which is the right shape for a page in progress
  but is not a gate: nothing yet *refuses* to publish a `#llm` span. Until it does,
  provenance is recorded and inspectable but not enforced downstream.
- **No page has been through the collation pass under the new rule.** `1-151` was
  retrofitted by hand — its four `resp="#llm"` attributes were added after the fact, not
  emitted by a pass reading the amended harness. So the instruction has not been tested
  on a model that only ever saw the provenance version, and the first page transcribed
  after this is also a test of whether the rule reads as intended.
- The continuation pass (`boundaries.json` from ALTO geometry) is specified but
  unwritten; `boundary_in` is `"unknown"` for every page until it exists. Note
  `transcriber_harness.md` still specifies it at length as though it were live,
  inside a document whose own scope statement excludes it.
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
