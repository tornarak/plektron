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
of four ranks: `#ed` ratified (a human keyed or confirmed it against the page), `#llm`
proposed (a model read it), `#htr` unexamined (recognizer output), and `#gt` adopted
(transcluded whole out of adjudicated ground truth by `harness tei expand`, and re-checked
against it on every run — see "A Tier-1 span the pass did not key"). The ranks are declared
once in the corpus teiHeader and never in a page file — `@resp` is a pointer resolved
against the assembled document, and a page file is a fragment that already defers title,
publication and source the same way. The collation pass may emit `#llm` and nothing else;
`harness tei validate` errors on a higher claim and on a missing `@resp` equally, because an
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
two inputs can turn out to be the same file. `harness ocr review`'s span diff now refuses
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
glyph and exact comparison between stores silently failed. `harness corpus normalize`
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
not be merged** — `harness/tests/test_lookalike_scope.py` holds them apart, and exists
because a consolidation was nearly carried out on the strength of an audit that
mistook the difference for drift.

# Source rasters

AMNH Digital Library PDFs (`M11Pt01–03`).

**`scans/` is derived, not source.** It is `pdftoppm -r <dpi>` over `pdfs/` —
verified pixel-identical — **then `tools/greyscale_scans.py --commit`**, so it is
regenerable and stays out of git. The PDFs carry a **bitonal JBIG2 text master at
~300 dpi** (part 1 2781×3866 at 295.5 dpi, part 2 2550×3525 at 300, part 3
2550×3525 at 308.4 against an A4 page box; the covers `1-001`/`1-002` and the
foldout `1-361` have no master and are RGB at 150). The figure *photographs* are
separate embedded JPEGs already at 150 dpi, so nothing is recoverable there —
only the text gains.

**The rasters are greyscale, and the three that are not are named.** poppler
writes RGB, but `pdfimages -list` over the three PDFs reports exactly three
non-gray embedded images in the whole volume — `1-001`, `1-002` and `1-361`,
the covers and part 1's appended foldout map. Every other page's source is
`gray 1 1 jbig2`, i.e. one grey value written three times, so converting is
lossless by arithmetic (PIL's luma weights sum to 1, so R=G=B=v gives L=v) and
was checked per page against the ink mask besides. **829 converted, 3 kept,
0 skipped.** 913 MB → 604 MB, and a page decodes in ~0.03 s where it took ~0.11 s.
All three colour pages are `exempt`, so the segmenter still sees a uniform corpus.

Converted **in place rather than re-rendered**, and that is the safety argument:
`Image.convert("L")` cannot change dimensions, where a re-render that came back a
pixel different would silently invalidate every coordinate in `gt/zones/`,
`gt/ocr/` and `gt/fig/` — which is the cost `tools/migrate_coords.py` exists to
record. A rebuild from `pdfs/` must run the converter afterwards or every raster
sweep quietly goes back to costing three times what it should.

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
seam ledger (`harness/state.py`, `harness tei ledger`) — which is exactly the
book-internal-evidence rule applied to pagination: the page says what page it is,
and nothing infers it.

# Where things stand

Layout, all at the repo root:

    scans/  832 rasters, all three parts, 300 dpi. Derived; not in git.
    scans/w-figs-blotted/  the same pages with figure zones painted white, the
            segmenter's training input. Derived; the 580 figure-less pages are
            symlinks into scans/, so a clone gets dangling links. Ignored.
    ocr/    the read view over both OCR stores — symlinks, the human file always
            winning. The harness's default --from. Derived; ignored, since half
            its links point into the ignored mz/. Never written through.
    gt/     what a human has been through. ocr/ (30 pages of ground truth),
            fig/ (252 figure ALTOs + METS, geometry only), seg/ (the first
            segmentation attempt, 122 pages, kept read-only), zones/ (the
            current one — seven types, fixed-width bands; 181 pages, 969 zones).
    mz/     what the models emitted, raw. zones/ (the segmenter) and ocr/ (lines
            and text). Derived; ignored.
    zones/  the read view over both zone stores — symlinks, the human file
            always winning. Derived; ignored. Never written through.
    tei/    1 page, plus corpus-header.xml — the corpus teiHeader, gated by
            `harness tei header`. Not a valid TEI document on its own: a bare
            <teiHeader>, a fragment like the page files, spliced in by an
            assembly step that does not exist yet.
    data/   readings.md  loi.json  toc.json  authorities.json  lexicon_extra.txt
            zones_config.json  tei_all.rng (TEI P5 4.12.0, the conformance gate's
            schema — committed so the gate does not move under an upstream release)
    review/ one directory per page, PP-NNN/. proposal.json (a reading, not truth)
            and decision.json (adjudicated) are tracked; crops/ sheets/ zoom/ and
            review.html are derived and ignored. See harness/paths.py.
    models/ blla, CATMuS print (large + tiny), LADaS medium, orli, plates-seg,
            zones-seg (this project's own, trained on gt/zones/).
    pdfs/   symlinks to the three AMNH source PDFs, outside the repo.
    train/  every training working dir, and pure scratch: bogoras-seg/ (the
            segmenter's symlink farm, .lst files and checkpoints), bogoras-rec/
            (recognition runs) and log/. Ignored; only trained models are kept,
            and those live in models/.
    scans/w-figs/  scans/w-ocr/   symlink farms over scans/ — the pages with a
            figure ALTO, and the raster beside its ALTO for every page a human
            has been through. Derived, and ignored: they point *into* an ignored
            tree, so a clone gets dangling links. `harness views build w-figs`.
    harness/  tools/  concordance.md  keying_spec.md — the tests live in
            harness/tests/, beside the package they cover.

- **The ground-truth rebuild is finished, and the store has outgrown it.** All 20
  pilot pages carry text, and `gt/ocr/` now holds **30** — the balance restored
  from `mz/ocr/` predictions rather than from eScriptorium shells, which is the
  standing route now that the shells are gone. **The reading half now fans out to
  a subagent per page** (`.claude/skills/rebuild-groundtruth/dispatch.md`), each
  stopping at a normalized `proposal.json`, with one `harness ocr review` server
  over the whole batch; `2-045`–`2-047` and `2-031`–`2-036` went that way.
  **`2-030` was the one page with ground truth and no `proposal.json`**, and is
  not any more — it was adjudicated by the eScriptorium route before the review
  loop existed, which left it unrevisable: `restore` refuses a decision set that
  does not cover every line, so there was no patch path and the whole of its text
  predated every detector now in the loop. It was also the densest Tier-1 page in
  the pilot set (fig. 213's 27-line gloss list), i.e. the worst page to have
  unexamined. Read through in 2026-08 and corrected in six places. **Every page in
  `gt/ocr/` now has a proposal**, so the state is closed rather than merely rare —
  but the shape that produced it is not, and a `gt`-with-no-proposal page is
  invisible to `ocr pages`, which reports the store rather than the review
  directory.
  What that page settled is worth more than its six corrections: **`gt/ocr/` and
  `data/readings.md` are not independent witnesses on a figure page.** This
  ground truth was hand-corrected from CATMuS and the caption block descends from
  the same recognizer pass, so three commas the machine invented sat in both files
  corroborating each other, and only a fresh raster read separated them. Nothing
  in either file records the shared ancestor. Same fault as the verbatim firewall,
  `review`'s span diff and `zones score`'s `unseen` row — two inputs that turn out
  to be one — arriving through provenance nobody wrote down.
  What that measured is worth carrying: **the residual error classes are §5.1's
  dropped `g̣` and §5.2's `ɪ`-as-`i`, they survive readers who explicitly report
  checking them, and the only safeguard that does not depend on a reader
  remembering anything is distributional** — `harness lexicon marks` puts `g̣` at
  93.9% of Tier-1 `g` and `ɪ` at nearly 2:1 over `i`, so a page against the grain
  is visible without opening a scan.
  **That claim is now measured rather than asserted, and computed rather than
  eyeballed.** `harness ocr corrections` aggregates what adjudicators actually
  changed across all 29 reviewed pages: scoped past 2026-07-31 the only class
  recurring across pages is `i`→`ɪ`. And `harness proposal marks` runs the
  comparison `dispatch.md` used to ask a coordinator to do by eye — pass a whole
  pass's refs, since most pages carry a handful of Tier-1 terms and one page is
  rarely a sample worth a verdict. Its `scope: ALL` row against the per-ref rows
  is what separates **one reader's slip from a lean every job shares**, and the
  second is the dispatch prompt or the keying spec rather than anybody's reading
  — the one finding nothing else in the loop can reach.
  Two of its three arms are deterministic and also run inside `harness proposal
  check`, so a reader meets them on its own page. Its prior is leave-one-out
  (after `restore` a page's gt **is** the adjudicated descendant of its own
  proposal, so including it would be the two-witnesses-that-are-one collapse in
  a fourth place) and drawn from density-selected pages, which every report
  states in `prior_note`.
  `harness ocr pages` lists the store;
  the pending-work list is the pages with a prediction and no ground truth, which
  is `--store mz --show-store` filtered on `view: mz`. `tei/` holds **three**
  pages — `1-151`, and the adjacent pair `1-100`/`1-101`, which is the corpus's
  only collated seam.
- **eScriptorium holds nothing right now** — the projects were exported and
  deleted. The repo is the system of record; re-import when keying resumes.
  `tools/make_mets.py gt/fig` rebuilds the manifest first.
- `tools/` holds five scripts, none of them part of a loop. `make_mets.py <dir>`
  is live — it rebuilds a METS manifest before an eScriptorium import.
  `greyscale_scans.py` is live but **only after a re-render**: it converts `scans/`
  to greyscale, is idempotent (a page already in mode `L` is left alone), and has
  to run whenever poppler has written the tree afresh.
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

The three line invariants that came out of the rebuild — `_lines_from_alto` drops
empty lines, a line polygon can exclude printed text, and `index` is an identity
rather than a position — bind anything touching lines and are stated in full in
`harness/README.md`'s caller invariants.

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

## Dropped lines

**The segmenter drops whole printed lines, and nothing text-level can see it.**
Whatever text is present is correct, so no lookalike grep, lexicon miss, mark
licence or CER figure disagrees with anything — the page simply has less on it than
the paper does. `1-053` reached restored ground truth missing a two-line closing
paragraph, found only because the footnote-marker check reported a marker whose
body reference did not exist.

`harness ocr gaps PP-NNN` is the detector: row-wise ink off the raster, masked
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

Repairing one is `harness ocr adopt-gap` — the one tool besides `restore` that
writes into `gt/ocr/`, geometry only, never `CONTENT`; its full contract and the
image-cost ladder are `.claude/skills/rebuild-groundtruth/`'s (`SKILL.md` and
`dispatch.md`).

# The derived trees

Seven directories are **derived**: git carries none of them and a fresh clone has
none of them. `harness/farms.py` is the one declaration — `harness views check`
reports them, `harness views build` rebuilds them. **Both name their farms and
neither has a default**: `views build --all` is a corpus-level sweep costing 252
repainted page composites, and nothing at the call site said so, so the caller
who wanted one view relinked after a `restore` was the one paying for it. In a
per-page loop reach for the per-domain spelling — `ocr link`, `zones link` —
the same way a per-page normalize names its page rather than sweeping the corpus.
(That "everything" was spelled `all`, a *value* of the FARM positional, until the
CLI settled on `--all` for every corpus form; the old spelling is trapped.)

    ocr/  zones/                 the read views over the paired stores
    scans/w-figs-blotted/        the segmenter's training rasters
    scans/w-figs/  scans/w-ocr/  selections over scans/, by criterion
    scans/                       reported, never built here: pdftoppm over pdfs/
                                 (symlinks outside the repo), then
                                 tools/greyscale_scans.py --commit
    train/bogoras-seg/           reported, never built here: assemble's scratch

Three things this settled, each of which had been true and unnoticed:

- **Two of them had no builder at all.** `scans/w-figs/` and `scans/w-ocr/` were
  made by hand, and this file said so. A hand-made farm drifts, and had: `w-ocr`
  was missing `1-060` the day it was restored. **`w-ocr`'s membership is `gt/ocr/`,
  not the `ocr/` view** — the farm itself settled that, holding the gt pages and
  none of the mz-only ones. View membership would also self-destruct, since after a
  corpus `ocr predict` every page has OCR and the selection becomes all 832.
- **Nothing relinks a view automatically** after `restore` or `save_zones`, so
  `views check` reporting `stale` is the normal way to find that out.
- **`.gitkeep` was considered and is wrong**, which is worth recording because it is
  the obvious fix. A tracked placeholder makes a directory *exist and be empty*,
  converting a loud absence into a silent one — the worse of the two states, and
  exactly what `exempt` exists to prevent in `gt/zones/`.

**An absent derived tree refuses; an absent store does not.** This is the fresh-clone
rule and the line matters. `Path.glob()` on a missing directory returns empty
silently, so `harness ocr pages` on a clone used to print an empty table and exit 0.
Now `context._refs_under` asks the registry: a **farm** that was never built raises,
naming the command that builds it; a **store** that holds nothing stays a silent
empty, because "nothing has been predicted" is a true statement about the corpus and
the ordinary state of a clone. `harness ocr pages --store mz` on a clone still
answers `[0]`, exit 0. The two halves are pinned together over one function in
`test_farms.py`, since read alone either looks like an inconsistency worth tidying.

**`views check` says how deep it looked, and that is the `verified` column.** For
`scans/w-figs-blotted/` it reads `membership`, because nothing there opens pixel data
or the timestamps behind it — so `state: ok` may not be read as "up to date".

**That column used to be justified by a claim that was simply false**, and the
correction is worth keeping because the false version had been restated in four
places and read as rigour. It said content freshness there was not merely unchecked
but *uncheckable*, on the grounds that a figure ALTO corrected after the blot leaves
a raster still showing the figure and an mtime test would pass it. It would not: a
corrected ALTO is **newer** than the blot, so a test against both its inputs —
`scans/` and `gt/fig/` — catches exactly that case. (Against the scan alone it would
be blind, the scan never changing; that is an argument for naming the right inputs.)
What no mtime test can see is a **deleted** figure ALTO — a page whose zones were
withdrawn should go back to being a link, and the stale painted PNG is still newer
than the scan, absence having no timestamp. That is a membership question, not a
content one. So `zones blot` repaints unconditionally **because skip policy here is
undecided** — it belongs with the dependency graph, which is a sprint of its own and
has not run — and not because freshness is unknowable. `membership` remains the
honest word for what `views check` actually did.

Worth naming, because this entry has now been wrong twice in the same shape: the
first version said freshness was *uncheckable*, and the correction replaced it with
*cost* — "252 composites take seconds, an incremental path would add a way to be
wrong for very little". That reads as a design decision taken, where the truth is a
decision deferred. A confident reason standing in for an open question is the same
failure as a confident reading standing in for an unread glyph.

The fourth state `?`
means no verdict was available at all (`scans/`, `train/`), and does not gate; nor
does the gate cover farms `build` cannot fix, since an exit code demanding a repair
the named command does not perform teaches a reader to ignore it.

# Harness

The collation loop runs in Claude Code. `harness/` is a small package exposed as
a console script, run from the repo root — all paths resolve relative to the cwd
unless `--root` says otherwise. `uv run python -m harness <group> <action>` is
equivalent if you ever need it.

**Two tiers: a group, then an action.** The group names what the command
touches; the action names what it does to it.

    tei       context validate ids pair seam state ledger header
    ocr       pages lines gaps adopt-gap crops numbered sheets zoom blot review
              restore corrections clean predict link
    proposal  check marks fix codepoints set replace
    zones     check edit predict score assemble install remap remark-eval
              delete diff paragraphs link blot
    views     check build
    lexicon   misses native marks suffixes digraphs glosses
    find      toc folio authority
    corpus    normalize figures

**`harness/VERBS.md` is the reference** — one entry per action: what it does,
what it reads, what it writes, what its exit code means, and every flag with
its default. Its Conventions section carries the rules that hold across every
group. Neither is duplicated here, and the reference cannot go stale unnoticed:
`harness/tests/test_cli_surface.py` walks the click command tree and fails on any
action or flag present in one and not the other, in both directions.

The conventions in one paragraph, because an agent that reads nothing else can
still violate them: **report by default, `--commit` writes**, and it gates exactly
the authored stores; **exit 0 clean / 1 gate failed / 2 usage error**, and
measurement never gates; **refs are plural** and every ref is `PP-NNN`, never a
bare integer; **a corpus run is `--all`, never an omission**; one meaning per
flag name; argument validation is the parser's.

**No ad-hoc Python for anything the harness already does.** Not `python3 -c
"...ord(ch)..."` to check a character's codepoint (`harness proposal
codepoints`), not a crop script to magnify a glyph (`harness ocr zoom` — see
`rebuild-groundtruth`'s SKILL.md on why 4× is already the ceiling and a
hand-rolled crop cannot see past it), not a heredoc to patch one field of a
JSON file (`harness proposal set` — a hand-typed `Edit` can silently fail to
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
| `harness/VERBS.md` | the CLI surface: every action, what it reads and writes, its exit contract, its flags. Gated against the parser by `test_cli_surface.py` |
| `harness/README.md` | the package: module responsibilities, stores, caller invariants |
| `concordance.md` | the evidence set behind the spec — aligned pairs, flag register, per-glyph attestation |

Two passes, and they are not the same job: collation (OCR → TEI, output `tei/`) and
the ground-truth loop (raster → ALTO, output `gt/ocr/`). The latter is now a
*revision* pass rather than a rebuild, every page having been restored.

# Current pipeline

## Pages

1. **Zoning** — this project's own segmenter (`harness zones predict` →
   `mz/zones/`), corrected in the editor into `gt/zones/`, read through `zones/`.
   **These regions carry semantic value**, which is the difference from the old
   pipeline: seven declared types, a vertical partition of a measured column. The
   LADaS regions they replaced had none and existed only to impose a reading order.
2. **Lines + recognition, one pass** — `harness ocr predict` → `mz/ocr/`, linked
   into `ocr/`. `blla` finds baselines off `scans/w-figs-blotted/`, the same raster
   `zones predict` reads, so artwork raises no baselines; **its regions are
   discarded and the zones replace them**, so a line arrives already knowing
   whether it sits in a running title, a paragraph, a footnote or a signature
   line, and the collation pass gets that structure instead of re-deriving it.
   The label travels in the ALTO as `OtherTag/@LABEL` via `TAGREFS` and surfaces
   as `zone` in `harness ocr lines`. Reading order is zone order, then down the
   page — so in this store, unlike `gt/ocr/`, document order *is* reading order.

   **Nothing is lost to the blot**, and that is a property of how it paints rather
   than a cost accepted: it fills the *declared* figure box and not a pixel more,
   the pad having been rejected precisely because body text sits hard against an
   inset figure on `1-283`. Figure captions do go, and should — they live in
   `data/readings.md` and are not body text.

   **A store keeps every line the page sets; a consumer filters by zone label.**
   That rule has now been derived three times from scratch — for `mz/ocr/`, for
   `catmus_draft`/`ocr_lines`, and for the reading proposal — so it is stated here
   once. **Which side a thing is on is decided by what it writes, not by what it
   looks like**: the proposal → `decision.json` → `restore` chain *writes*
   `gt/ocr/`, so it is a store path and keys the apparatus like everything else.
   The 20 restored pages carry **49 apparatus lines and all 49 are keyed**; a
   proposal that omitted them could not restore anyway, since `restore` refuses a
   partial rather than admit ground truth with invisible holes.

   So `context.APPARATUS_ZONES` — running title, quire marks, and the old
   vocabulary's numbering zone — leave the **collation draft, not the store**. The
   filter sits at the consumer rather than at `ocr predict` because those zones
   **carry the printed folio**, and the folio is where page numbering enters the
   project; dropping it at write time would take the OCR's only record of it and
   cost a re-run of the page. An *unlabelled* block is kept, since a store may
   label none and treating blank as apparatus would empty the draft for every page
   of it.

   They leave **`ocr_lines`** as well, and for a sharper reason than the draft's:
   that list is the set of `@facs` pointer targets, and a running head, a folio or
   a signature line is never in the TEI body, so citing one is a mistake by
   construction. A **caption** is different and stays — it is dropped from the
   draft only, because the project already holds a human reading of it in
   `data/readings.md`, and it remains legitimately citable.

   **They leave the draft and arrive as `running_title`**, a `tei context` field
   carrying `{text, folio, folio_from, bracketed, lines}` — restructured rather
   than discarded. That folio is the **second witness** to `expected_folio`, which
   is a prediction from the preceding transcribed page and knows nothing about this
   one; the two disagreeing is the signal, and a second witness this cheap is what
   the governing principle asks for.

   **The book prints the number in three places and the corpus spells them in two
   vocabularies**, so it is looked for in order of confidence: the head line of an
   ordinary page; then a **bracketed** number at the *foot* of a chapter opening,
   which is `QuireMarksZone` in the current scheme (`1-151` reads `[115]` at vpos
   3231 of a 3897 px page, and its collated TEI gives `<pb n="115"/>`); then
   `NumberingZone`, the full-SegmOnto zone `gt/ocr/` descends from, last because it
   names a store's spelling rather than a place on the page — it appears at the
   head on `1-048` and at the foot on `1-151`. `folio_from` records which answered.
   Nothing is repaired: `2S` for `28` leaves `folio` null and stays in `text`.

   Recognition is stock CATMuS — a witness to line geometry and English and to
   nothing else (it reads 0% of the inventory; the measurement and its
   substitution table live with the passes that use it). The `Processing` block
   names both models and both sha256s.

   **A line `blla` finds outside every zone is kept, not dropped**, assigned to no
   region and counted as `lines_outside_zones`. Artwork produces these and they are
   visible junk; a dropped line is invisible, and that asymmetry is the whole
   reason for the rule. A high count on an ordinary text page means the artwork was
   mis-zoned or a zone is missing — the same finding `zones check --ink` reaches
   from the other side.

   **Consequence worth stating because it reads as success: a detector census over
   "the 20 GT pages" was really a census over two.** At the start of the rebuild, 17
   of the 20 were empty shells (11 still are), so they reported zero flags because
   there was nothing to flag, not because they were clean. Any baseline taken before
   a page's own rebuild is worthless for the same reason — `1-074` went from 0 flags
   to 15 `inventory_glyph` the moment it was restored.
3. **Collation** — An LLM (usually Sonnet-class) receives 1) the image of the original scan, 2) the OCR plaintext for that page, and 3) a machine-generated summary with useful contextual data (relevant TOC entries, list of page figures, etc.). It outputs TEI for that page. Built by `harness tei context`; gated by `harness tei validate`. Everything the model receives is deterministic and precomputed — it never re-derives ToC ids, figure zones, or detector flags.
4. **Annotation** — TBD
5. **Compilation** — TBD

## Final Product

1. **Original Scan Page** - `scans/chukchi-PP-NNN.png`
2. **Figure geometry** - `gt/fig/chukchi-PP-NNN.xml`. ALTO containing only `GraphicZone` and `GraphicZone-FigDesc` blocks. No lines, no text.
3. **Figure captions** - `data/readings.md`, keyed `1-123|<zone-id suffix>`. The only caption store.
4. **OCR transcript** - `ocr/chukchi-PP-NNN.xml`, the view: `gt/ocr/` where a human
   has been through the page, `mz/ocr/` otherwise. ALTO carrying the zones as
   regions and the lines within them, dumped to plain text for the collation pass.
   The regions are no longer useless — they are the seven declared types.
5. **TEI** - `tei/chukchi-PP-NNN.xml`. Also the system of record for seam state:
   its `<pb>` is where the printed folio enters the project, and `harness tei ledger`
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

**Pairing a picture with its caption is `figures.paired`, done once and recorded**
— the rule CLAUDE.md has always stated and nothing implemented. It branches on
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

# Collation

Process and rules: `.claude/skills/transcribe-page/SKILL.md`, which carries both —
it has no separate harness doc, the same shape as `rebuild-groundtruth`. Loop:
`/transcribe-page PP-NNN`.

The correction licence (European-language spelling yes, Tier-1 never), its
boundaries and the keying rules are the skill's; what stays here is the
detector formula and the two measurements that shaped the tools.

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
  `harness lexicon misses`) holds the Latin binomials, ethnonyms and coinages no general
  dictionary carries. **It suppresses `lexicon_miss` and nothing else** — and it
  cannot do otherwise, since `lexicon_miss` only ever tests ASCII components, so a
  Tier-1 form listed there is inert by construction rather than by discipline.

  **The cut is shared and happens once, at the tokenizer.** `detect_all` used to
  publish the raw whitespace-delimited token and strip `EDGE_PUNCT` only inside
  the one check that needed it, so a flag reached the collation payload as
  `"mêˊmêl),"` — the printer's parentheses glommed onto a Tier-1 form in the one
  field a reader acts on. It sent `proposal codepoints` and a raster look after
  characters that are not in the word, and it meant the string did not compare
  equal to the *same form* in `tier1_terms`, which is what let one page's evidence
  reach the pass twice in two spellings. U+0027 survives the cut deliberately: it
  is the spirant mark, not punctuation.

  **`tei context` then suppresses a flag on a token that page has already
  ratified**, on the `(line, token)` pair rather than the token alone, so
  `detector_flags` is the *residue* — Tier-1 material with no adjudicated reading
  behind it, plus the ordinary English triage. `1-151` goes 4 flags → 0. What
  survives on a ground-truth page is the floor's own blind spot, which is the
  right thing for a triage list to hold.

  **That exposed `apostrophe_adjacency` as almost pure noise**, and the fix is the
  shape of every filter here. With Tier-1 forms no longer flagged, all 31 surviving
  hits over the ground-truth corpus were ordinary English possessives — `wife’s`,
  `Krause’s`, `reindeer’s`. But **position cannot decide it**: `keˊlet` mis-keyed as
  `ke’let` puts U+2019 between two lowercase ASCII letters, exactly where a
  possessive sits. So `english_genitive` requires the shape *and* a stem the lexicon
  **positively knows** — not `not _unknown_word(...)`, which passes anything under
  four characters and would clear `ke’let` and `kun’s` alike. It fails closed with
  no lexicon, and it declines the possessive on an unknown proper noun rather than
  guessing. The corpus now reports **one** such flag, `2-045`'s `kun’s`, the tail of
  a broken `Kereˊtkun’s` — a Tier-1 stem taking an English genitive, which is
  precisely what a shape-only rule would have thrown away.

  **The payload's flags now read the joined text**, which both `lexicon` arms have
  done since 2026-08-03; this arm builds its own draft and was simply never
  included, so it went on reporting `Chuk`/`chee`, `Penin`/`sula`, `direc`/`tions`
  as words no dictionary knows — 82 flags → 44 over the ground-truth corpus. **The
  draft itself stays line-per-line**: the model reads the raster beside it, and a
  draft that silently reflowed would stop being checkable against the page. Safe
  only because `index` is carried alongside rather than being a position in either
  list. Emptied lines drop with their index, which also keeps `_balance` seeing one
  paragraph per page.

  **And that surfaced a live hazard in `tier1_terms`: a half of a broken word was
  being offered as a form.** `1-101` prints `Torwaˊwaq` as `(Tor-` / `waˊwaq)`, so
  the list held `waˊwaq` — a whole token on its line, ratified, and half the word.
  A pass naming it gets a truncated form filled in and stamped `#gt`, and every
  guard passes, because it really is a token in this page's ground truth: the same
  boundary the whole-token check protects at one end (`Qeˊñ` ⊂ `Qeˊñu`), broken at
  the other by the compositor's measure. A term is now offered only if it survives
  the join as a whole token. **The rejoined form is not offered in its place** —
  `Tor-waˊwaq` is a string no line holds, and whether that hyphen is the word's or
  the printer's is the ambiguity the join preserves rather than decides. So a
  broken form gets no handle and arrives as a flag on the joined text, which is
  the correct answer: read the page. Eight forms across the store are in this
  state.

**Density, measured** on `1-048` and `2-030` — the two densest pages, so a ceiling
and not an average. Inventory glyphs are **3.3% of characters** but fall in **43.8%
of lines**.

That asymmetry decides tool shape, and it was got wrong once. The 3.3% argues for
reviewing spans; the 44% says those lines get opened anyway, and once a line is open
reading the rest of it is nearly free — the expensive act is re-orienting to a
different line, not reading characters in one already in front of you. **So review
is line-based**, and the span diff survives only as measurement.

## Cross-page state

The collation pass is strictly per-page — one page per task, fresh read, no
impressions carried in the model's head. What legitimately crosses a page
boundary crosses through the **committed TEI**, folded forward by `harness tei
ledger`; the ledger's fields, `prev_tail` and the seam machinery are the
collation skill's.

## TEI

TBD beyond the per-page output contract in the collation skill (`<pb>` first, no
`<div>`, no `<lb/>`, minimal teiHeader, footnotes anchored at their markers,
figures anchored to supplied zones). **Assembly is still unsettled**; the
corpus teiHeader is not, and is `tei/corpus-header.xml`.

The encoding rules — gloss kinds, `<supplied>`, proper-name categories, the id
scheme, the header fragment — are the collation skill's in full.

**Licence: two, because this is not one work.** The transcribed text is **CC0** —
a faithful transcription of a 1904 book carries no fresh copyright (EU DSM Art. 14;
US law has never protected slavish reproduction), so licensing it CC BY would assert
a right the edition does not hold, which is the provenance overclaim pointed at the
law instead of at the glyphs. The apparatus — `loi.json`, `toc.json`,
`authorities.json` and their research, the TEI structure, the adjudications, the
annotation layer — is original editorial work and is **CC BY 4.0**. Scopes are
stated on each `<licence>`; where a reuse cannot separate them, treat it as CC BY.
`harness tei header` errors on a settled `@status` granting no `<licence>` at all, that
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
- **The TEI is validated against TEI**, and the entry that stood here saying
  otherwise wanted "a committed schema and an assembly step". It needed the first
  and not the second. `data/tei_all.rng` is P5 4.12.0 (1.1 MB, committed so the
  gate means the same thing on a fresh clone and after an upstream release), and
  `harness tei validate`/`tei header` run it by default. All nine of the
  previously-unchecked attribute usages are conformant, and a test pins them so
  that stays true while the encoding churns.
  **A page file validates standalone** — the old entry said it would not, which is
  true of `tei/corpus-header.xml` (a bare `<teiHeader>`, wrapped in a minimal
  `<TEI>` *in memory* to be checkable at all) and false of every page, which has a
  real `<TEI>` root. So no assembly step was needed to get here.
  It found one defect immediately: `version="stock"` on `<application>`, where
  `teidata.versionNumber` is a pattern that does not match it, in a file read by
  hand more than once. That is the class this catches and a reader does not.
  **The two gates are complementary and neither shrinks the other**: every project
  rule is expressible in conformant TEI, so the schema is silent on all of them,
  and a file can satisfy all of them while using an attribute TEI never defined.
  `tei_all` and not `tei_lite` — the smaller customizations are strict *subsets*,
  so one would reject markup this project legitimately writes, and a gate that
  fails correct input teaches a reader to ignore it. The cost is the compile
  (~17 s, identical under `xmllint`, so it is the schema's size and not lxml)
  against ~0.3 ms a page, so it is cached per process, a sweep pays it once, and
  the *library* functions default it off or the test suite would pay it on every
  call. Run it after `tei expand`: `index=` is not a TEI attribute, which is what
  makes an unexpanded page detectable, so it fails here too.
- **`data/toc.json` (315 entries) records no provenance.** `loi.json` and
  `authorities.json` both name the scans they were read from; this one does not,
  and the printed ToC's scan range is not recoverable from the file. Someone who
  knows should write it down — every other apparatus store is auditable back to a
  page and this one is not.
- **The span diff's second witness is back, and it is `mz/ocr/`.** `end-of-eval/`
  was the recognizer store, it was deleted, and the diff refused rather than
  compare a proposal against the ground truth it produced. This entry used to say
  "if a second witness is ever wanted again, it links into `ocr/` from its own
  store" — which is exactly what `ocr predict` built. `harness ocr review REF
  --spans --store mz` is an independent witness by inode, where the bare view
  stops being one the moment the page has ground truth and the view points at it.
  Name the store, not the view: the refusal catches the collapse, but only after
  you have typed the wrong thing.
- **The segmenter's open questions live with its skill.** The measured state, the
  `unseen`-row collapse and its recurrence condition, `split_from`, the decode
  gains, part 1's deliberate overrepresentation, the unproven `--resize`
  mechanism and the hand-corrected `class_mapping` on the installed model are all
  `.claude/skills/train-zones/SKILL.md`'s — they are training-loop state, and two
  copies of a number is how one goes stale.
