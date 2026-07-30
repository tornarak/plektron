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

**Firewall.** No non-English glyph identification may originate from a model's reading
of a scan, or from inference about what Bogoras's system "should" contain. Book-internal apparatus (the p. 10 key, the List of Illustrations, the printed TOC) is *not* subject to this —
it is evidence, and it binds.

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

# Source rasters

AMNH Digital Library PDFs (`M11Pt01–03`).

**`scans/` is derived, not source.** It is exactly `pdftoppm -r <dpi>` over
`pdfs/` — verified pixel-identical — so it is regenerable and stays out of git.
The PDFs carry a **bitonal JBIG2 text master at ~300 dpi** (part 1 2781×3866 at
295.5 dpi, part 2 2550×3525 at 300, part 3 2550×3525 at 308.4 against an A4 page
box; the covers `1-001`/`1-002` and the foldout `1-361` have no master and are
RGB at 150). The figure *photographs* are separate embedded JPEGs already at
150 dpi, so nothing is recoverable there — only the text gains.

Rendering at 300 dpi is **not** a clean ×2 of the old 150 dpi rasters: across
the 832 pages, 205 come out one pixel short on width, 627 one pixel short on
height, and **none is exactly double**. Anything mapping between the two spaces
must take the ratio from the two rasters, per page and per axis. Do not compute
it as `ceil(pt/72*dpi)` either — that predicts 2782 for the covers where poppler
renders 2781, because `667.44/72*300` is `2781.0000000000005`.

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
    fig/    252 figure-track ALTOs + METS.xml. Geometry only.
    ocr/    20 ALTOs — the pilot selection. **Symlinks into gt/ocr/**, not copies.
    gt/     ocr/ (the 20 real files), seg/ (train, eval, .lst manifests).
    tei/    1 page.
    data/   readings.md  loi.json  toc.json  lexicon_extra.txt
    models/ blla, CATMuS print (large + tiny), LADaS medium, orli, plates-seg.
    pdfs/   the three AMNH source PDFs.
    harness/  tools/
    scans-w-figs/  scans-w-ocr/   symlinks into scans/, for eyeballing a subset.

- `ocr/` **20 pages** — the pilot selection, scattered across all three parts
  (`harness pages` lists them). **These are hand-keyed and verified: ground
  truth, not recognizer output.** Nothing regenerates them.
  **`ocr/*.xml` are symlinks into `gt/ocr/`** — one store under two names, so the
  two can never disagree, and a tool walking both sees each file twice. Anything
  iterating the corpus must dedupe by real path: without it a writer processes the
  file under the first name, meets it again under the second, finds it already done
  and skips silently, so the report undercounts exactly what it touched.
  `harness/normalize.py:scoped_files` does this and says why.
  `tei/` holds **one** page, `1-151` — collated, uncommitted, with two open comments.
  It does **not** currently validate; see the caveat under Recognition below.
- **Figure captions live in `data/readings.md`, not in `fig/`.** All **395** are
  read by hand off the 300 dpi scans, one block per FigDesc zone, keyed
  `<ref>|<zone-id suffix>`. `fig/` carries **no `TextLine` at all** — the lines
  were stripped, because the exported line segmentation dropped whole printed
  lines and a line-level witness in the ALTO would then disagree silently with
  the readings. There is no keyed/unkeyed boundary any more; the old
  `KEYED_COUNT = 50` marker is gone from `harness/figures.py`.
  **Consequence for code**: reading `String/@CONTENT` out of `fig/` returns `""`
  for every zone on every page. Not an error — nothing, which is worse. Go
  through `figures.readings()`, and check the two stores agree with
  `figures.reconcile()` (invariant: `missing` and `orphan` both empty).
- **eScriptorium holds nothing right now** — the projects were exported and
  deleted. The repo is the system of record; re-import when keying resumes.
  `tools/make_mets.py fig` rebuilds the manifest first.
- The repo has **no commits yet**. Everything is untracked.

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
    uv run harness lexicon            frequent lexicon misses, to whitelist

Output is **TOON**, not JSON — a tabular encoding that collapses uniform record
lists to a header row plus data rows (the ledger went 127 KB → 34 KB, the page
context 8.0 KB → 3.6 KB). `--json` on any verb restores indented JSON for
anything that needs to parse the output as a contract. Anything emitting a list
of records keeps one fixed key set across them, because a ragged list silently
degrades to the verbose nested form.

Every verb that names a page takes a `PP-NNN` ref and rejects a bare integer,
`state` included.

**Doc precedence.** This file is authoritative on the project. Below it:
`transcriber_harness.md` (repo root) is the normative rule set for the collation
pass itself — the output contract, the firewall rules, the per-element
specifications — and `.claude/skills/transcribe-page/SKILL.md` only sequences the
work. `keying_spec.md` governs the human keying track.
# Current pipeline

## Pages

1. **Segmentation** — LADaS D-FINE (medium). These regions have **no semantic value** and are only used to impose a reasonable reading order and make the OCR plaintext more coherent. Semantic "segmentins" are the preserve of the **Collation** stage.
2. **Recognition** — CATMuS, fine-tuned on the selection of pages densest with Americanist notation. **Caveat**: the 20 pages in `ocr/` are hand-keyed and verified rather than recognizer output, and `models/` currently holds only stock CATMuS (large + tiny) — the fine-tune is not in the repo. Establish which model actually produced a given page before drawing conclusions from it.

   **Second caveat, and the load-bearing one right now: 18 of those 20 ALTOs contain
   no text at all.** Only `1-048` (48 lines) and `2-030` (32 lines) carry
   `TextLine`/`String`; the rest are ~1977-byte export shells — `alto`,
   `Description`, 15 `OtherTag`s, `Layout`, `Page`, `PrintSpace`, and nothing else.
   All 18 share the mtime `2026-07-29 22:42:18.000000000`, whole-second and identical,
   which is an archive extraction rather than anything a script here did.

   Two consequences worth stating because both read as success. A detector census over
   "the 20 GT pages" is really a census over two — the other 18 report zero flags
   because there is nothing to flag, not because they are clean. And `harness validate
   1-151` **FAILS** with four FIREWALL errors: the TEI's Tier-1 spans cannot be
   verbatim substrings of an empty draft. That is the firewall working correctly on a
   missing witness, not a defect in the TEI.
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

The 252 pages with figures have been segmented to isolate `GraphicZone`s and `GraphicZone-FigDesc`s — **414 zones and 395 captions** as of the current export in `fig/`, one `data/readings.md` block per caption, reconciled in both directions. Figure images will be auto-generated by the build. Specifics TBD

The count was 250 pages until `1-301` (fig. 168) and `2-262` (fig. 301) turned up
missing. It is worth knowing why that went unnoticed: 250 also happened to be the
page count the List of Illustrations implies (215 distinct text-figure folios + 35
plate leaves), so the two absences cancelled exactly against `3-006`/`3-007`, which
carry a zone and no caption and are therefore not LoI pages at all. **A total that
matches is not coverage.** The check that would have caught it is the per-entry
one, and it now passes: every LoI text-figure **1–302** has a reading, no reading
cites a figure number outside the LoI, and all **35 plates I–XXXV** are located.
91 LoI plate segments map to 93 caption blocks, and all four deviations are known
— Plate II (the LoI makes the shared "Anui Fair" its own segment where the page
prints it twice) and Plates XXXII/XXXIII/XXXIV (four printed figures against three
segments, two figures sharing a caption on each).

Figure images are cropped from `scans/`. Note that the ~300 dpi master is the
*text* layer only — the photographs are embedded JPEGs already at their native
150 dpi, so re-rendering the page at 300 dpi upsamples them and adds no detail.
Their bboxes matched the embedded JPEG dimensions exactly at 150 dpi (`1-116`'s
zones were 418×233 and 508×640, and the page carries JPEGs of exactly those
sizes), which is a free check on the segmentation if ever needed.

**GraphicZone↔FigDesc pairing is not in the data.** Pair by geometry and record
the result; never re-derive it per consumer. **17 of the 252 pages are not 1:1,
and every one of them is zone-heavy** — max on a page is 4 zones / 4 captions:

    1-123 1-141 1-189 1-207 1-208 1-237 1-254 1-276 1-323 1-334
    2-085 2-100 2-122 2-198 2-205 3-006 3-007

Zone-heavy is structural and permanent: one caption covers several images, either
lettered (`1-276` fig. 138 *a, b, c*; `2-085` fig. 253 *a, b*) or numbered
(`1-237` "Figs. 2, 3"), and `3-006`/`3-007` carry a zone with no caption at all.
Nothing will make these 1:1 and nothing should try.

**Caption-heavy is now empty, and that is a result, not a given.** It was 5
pages. All five were the segmenter finding captions that do not exist — clipped
slivers of body text on `2-122`, an unlabelled graphic on `1-235`, and on `2-094`
the short parallel strokes of the *cheek line-work* in fig. 260's facial-painting
drawing, which at zone level look like a short line of type. Those boxes were
deleted from `fig/` and their `data/readings.md` entries with them. So a
caption-heavy page appearing in future means a new segmentation fault, not a
feature of the book — which is exactly the signal it should be, and was not while
noise was sitting in the same bucket.

Encoding confirmed against real exports: eScriptorium writes zone types as
`OtherTag/@LABEL` referenced by `TAGREFS`, labels exactly `GraphicZone` and
`GraphicZone-FigDesc`. **Resolve by label, never by tag ID** — the IDs are
assigned per export (`BT55`/`BT56` in one, `BT68`/`BT69` in the next), so code
that hardcodes them fails silently rather than loudly.

`harness context` surfaces these as `figures_on_page` — zone id, type, bbox, and
the caption `text` pulled from `data/readings.md`. The collation pass anchors
`<figure facs>` against those zone ids and the validator rejects any that match
no supplied zone. Only 3 of the 20 OCR'd pilot pages also have figure ALTOs —
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

**The dot is encoded *below*, and the naming used to say otherwise.** The canonical
form is `g` + U+0323 COMBINING DOT BELOW — 35 occurrences, it is what
`detectors.INVENTORY_CHARS` carries, and `validate.py` declares the precomposed
U+0121 (dot *above*) a trap for it. So `DOT_ABOVE_G` and the `dot_above_g` flag name
the **lookalike**, not the glyph; they are trap detectors and correctly matched. Text
here previously called the inventory glyph "dot-above g" while its own example
encoded U+0323, which cost a session's worth of chasing the wrong codepoint.

Two things still want a human, and both are firewalled. Whether the U+0323
canonicalization was made against the printed p. 10 key or inherited from whatever
the recognizer emitted — if the latter, the OCR chose the orthography and the
validator has been enforcing it. And `data/readings.md` line 1267 (`2-030`) carries
the corpus's one dot-*above* g in `tñaˊɪrġɪn`; that block holds both a human key and
a machine attempt, so which witness typed it decides whether the trap caught a
model reaching for a lookalike. `harness normalize --check` reports it.

# Collation

Process and rules: `transcriber_harness.md`. Loop: `/transcribe-page PP-NNN`.

**The LLM has the authority to:**

- Correct **English and Russian (and other European languages, where they show up) misspellings and orthographic mistakes**. OCR has persistent trouble with quotes, brackets, and numeric superscripts in this text.
- Join hyphenated words (in **European languages** - hyphens are load-bearing in Americanist notation).
- Resolve basic textual features like small-caps and footnotes.

**[Mis]transcriptions of Chukchi, Koryak, and "Eskimo" (Yupik) words** should be **reproduced verbatim** and enclosed in appropriate `xml:lang` tags.

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

**Outstanding:** the density count — fraction of lines containing non-English spans,
by stratum, extrapolated to 730 pp. It no longer chooses the architecture; it sizes
the human keying budget, which is worth knowing before the pilot rather than during.

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

- **Nothing is committed.** An initial commit before the pilot would be worth
  having, if only so the collation loop's per-page commits have a baseline.
- The continuation pass (`boundaries.json` from ALTO geometry) is specified but
  unwritten; `boundary_in` is `"unknown"` for every page until it exists.
- One page (`1-151`) has been through the loop and passes, so the validator's
  rules have met real model output exactly once. The pilot protocol — 3 keyed
  pages first, measuring first-pass failure modes, firewall trips, `<unclear>`
  false positives and question rate — is still the intended next move, and is
  not written down anywhere yet.
- The 20 OCR'd pages are scattered across all three parts, so most have no
  transcribed neighbour and will start with `expected_folio: null`.
