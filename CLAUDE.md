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

**A comparison whose witnesses may be one witness must say so.** The hazard
recurs wherever a check's two inputs can turn out to be the same file —
`harness ocr review`'s span diff refuses rather than reporting a clean 40/40
when the store it is pointed at resolves to the ground truth the proposal
produced, and the same collapse has been found in four places (the history is
`docs/decisions.md`, "What the firewall is not").

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

**`scans/` is derived, not source** — `pdftoppm` over `pdfs/`, then
`tools/greyscale_scans.py --commit`, and a rebuild that skips the converter
makes every raster sweep cost three times what it should. The master's
geometry, the greyscale conversion's safety argument and the 150↔300 dpi
mapping rule are `docs/rasters.md`.

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

- **eScriptorium holds nothing right now** — the projects were exported and
  deleted. The repo is the system of record; re-import when keying resumes.
  `tools/make_mets.py gt/fig` rebuilds the manifest first.

**The frontier is collation.** The apparatus stores are done and reconciled —
`loi.json`, `toc.json`, `authorities.json`, `readings.md`, and the pilot
ground-truth pages — so what is left is the pass that consumes them. Counts
come from the harness (`harness ocr pages`, `harness zones check`), never from
a doc; the state of each track, and what building it settled, is under `docs/`.

## The ground-truth loss

An archive extraction once replaced 17 of 20 hand-keyed pages with export
shells, because a file's role lived only in its directory name. The whole
lesson, and the rule the store layout still obeys: **`gt/` is what a human has
been through, the views are only views, and nothing writes through a view.**
The full story is `docs/decisions.md`; the line invariants it produced are
`harness/README.md`'s caller invariants.

## Page segmentation, second attempt

Seven declared types, fixed-width bands of a per-page-measured column, a
separate store from `gt/seg/` permanently. The design and its reasoning are
`docs/segmentation.md`; the training loop is `.claude/skills/train-zones/`;
the code-facing internals load from `.claude/rules/zones.md` when the zones
modules are open.

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

Zoning (`zones predict` → editor → `gt/zones/`) → lines + recognition in one
pass (`ocr predict` → `mz/ocr/`, zones replacing blla's regions) → collation
(LLM over scan + draft + precomputed context, gated by `tei validate`) →
annotation (TBD) → compilation (TBD). The stage-by-stage detail and the design
reasoning are `docs/pipeline.md`.

# Collation

Process and rules: `.claude/skills/transcribe-page/SKILL.md`, which carries both —
it has no separate harness doc, the same shape as `rebuild-groundtruth`. Loop:
`/transcribe-page PP-NNN`.

The correction licence (European-language spelling yes, Tier-1 never), its
boundaries and the keying rules are the skill's; what stays here is the
detector formula and the two measurements that shaped the tools.


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


## Annotation passes

TBD

## Open

The standing record of what is deliberately unresolved is `docs/open-questions.md` —
an entry leaves it by being settled, and says so when it goes.
