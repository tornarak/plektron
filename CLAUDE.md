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
against it on every run — the collator's "A Tier-1 span the pass did not key").
The ranks are declared once, in the corpus teiHeader, never in a page file. The
collation pass may emit `#llm` and nothing else; `harness tei validate` errors on a
higher claim and on a missing `@resp` equally, because an unmarked span is
indistinguishable from a ratified one to anything that does not check.

**A comparison whose witnesses may be one witness must say so.** The hazard
recurs wherever a check's two inputs can turn out to be the same file, and has
been found in four places (`docs/decisions.md`, "What the firewall is not").

**LLM remit.** Models triage, propose, and restructure. They never originate a glyph
identity and never mint an index entry unreviewed.

# Environment

- `uv` project, **Python 3.14.3**; torch 2.12.0+cu130, `cuda.is_available()`
  True in the env. `uv.lock` committed. A doc still saying 3.13 is stale.
- `kraken` 7.0.3, pinned. **The CLI was reorganized across the 3→5→6→7 majors and
  nearly every tutorial online is 4.x-era.** Verify flags against `kraken --help` /
  `ketos --help` rather than trusting remembered or documented syntax, including
  anything asserted in this file.
- eScriptorium via `docker compose`, local. The annotation GUI, **not** the
  system of record: export ALTO and commit every session.
- GPU: Turing card, ~100× over CPU.

# Encoding

**NFD, corpus-wide** (`keying_spec.md` §1). `harness corpus normalize` is the
gate; `--convert` writes the fixes.

**Never NFKC.** It has compatibility decompositions for two inventory glyphs and
destroys them: `ᵋ` U+1D4B → plain U+025B, `˙` U+02D9 → space + combining dot.
Any `normalize()` call must name its form.

**The ASCII policy is scoped to Tier-1** (`keying_spec.md` §1). Inside
the five Tier-1 codes, U+0027 and U+002D are the only apostrophe and hyphen; English
prose reproduces the print, **curly quotes included**. The lookalike tables
differ by scope and **must not be merged** — `harness/README.md` states the
rule, `test_lookalike_scope.py` holds them apart.

# Source rasters

**`scans/` is derived, not source** — `pdftoppm` over `pdfs/`, then
`tools/greyscale_scans.py --commit`, and a rebuild that skips the converter
makes every raster sweep cost three times what it should. The master's
geometry, the greyscale conversion's safety argument and the 150↔300 dpi
mapping rule are `docs/rasters.md`.

**Page refs are `PP-NNN`** — part, and scan index within that part (`1-048`) —
everywhere: filenames, CLI, commit messages. NNN is a *scan
index*, not a printed folio. Part 1 runs 001–362, part 2 001–268, part 3
001–202; the printed folio runs continuously 1–732 across the volume, with
plates and front matter unpaginated. **Neither is derivable from the other**, so
a bare page number names no page and the harness rejects one. The folio is known
only where a transcribed page recorded one, and propagates via the seam ledger
(`harness/state.py`): the page says what page it is, and nothing infers it.

# Where things stand

Layout, all at the repo root:

    scans/  the 832 rasters, 300 dpi greyscale. Derived; not in git. Selection farms over it (w-figs/, w-ocr/, w-figs-blotted/)
            are derived too and point into it: a clone gets dangling links.
    gt/     what a human has been through: ocr/, fig/ (geometry only, no
            lines), zones/ (the current segmentation), lines/ (the corrections
            overlay). Tracked.
    mz/     what the models emitted, raw: zones/ and ocr/. Derived; ignored.
    ocr/  zones/  the read views over the paired stores — symlinks, the human
            file always winning. Derived; ignored. Never written through.
    tei/    the collated pages, plus corpus-header.xml — the corpus teiHeader,
            a fragment gated by `harness tei header`.
    data/   readings.md  loi.json  toc.json  authorities.json  lexicon_extra.txt
            zones_config.json  lines_config.json  tei_all.rng (the schema).
    review/ one directory per page: proposal.json (a reading, not truth) and
            decision.json (adjudicated) are tracked; the images are derived and
            ignored. See harness/paths.py.
    models/ the recognizers and segmenters, this project's zones-seg included.
    pdfs/   symlinks to the three AMNH source PDFs, outside the repo.
    train/  training working dirs, pure scratch. Ignored; artifacts go to models/.
    harness/  tools/  docs/  concordance.md  keying_spec.md — the tests live in
            harness/tests/, beside the package they cover.

Counts deliberately absent — they go stale in a file nothing regenerates;
`harness ocr pages`, `harness zones check` and `harness views check` answer.

**The frontier is collation.** The apparatus stores are done and reconciled, so
what is left is the pass that consumes them.

## The ground-truth loss

An archive extraction once replaced 17 of 20 hand-keyed pages with export
shells, because a file's role lived only in its directory name. The whole
lesson, and the rule the store layout still obeys: **`gt/` is what a human has
been through, the views are only views, and nothing writes through a view.**
The full story is `docs/decisions.md`; the line invariants it produced are
`harness/README.md`'s caller invariants.

## Page segmentation, second attempt

Seven declared types, fixed-width bands of a per-page-measured column, in its
own store — the first attempt's `gt/seg/` is deleted, nothing having trained
coherently on it. The design and its reasoning are
`docs/segmentation.md`; the training loop is `.claude/skills/train-zones/`;
the code-facing internals load from `.claude/rules/zones.md` when the zones
modules are open.

# Harness

`harness/` is a small package exposed as a console script, run from the repo
root — all paths resolve relative to the cwd unless `--root` says otherwise.

**Two tiers: a group, then an action** — `tei`, `ocr`, `proposal`, `zones`,
`views`, `lexicon`, `find`, `corpus`, `agents`. The group names what the command
touches; the action names what it does to it.

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

**No ad-hoc Python for anything the harness already does** — not `python3 -c`
for a codepoint (`proposal codepoints`), not a crop script (`ocr zoom`), not a
heredoc onto a JSON field (`proposal set`). A one-off script is a tell that a
tool is missing or under-used; reach for the verb, or extend it, never route
around it. The cases are in the `groundtruth-reader` agent.

**Doc precedence.** This file is authoritative on the project's invariants and
is the router to everything else. It is deliberately **not** the place for how
a pass is run, for a track's record, or for any number a command can answer —
each has exactly one home below, and a fact stated twice is a defect.
`test_doc_budget.py` holds the size and the routing; every subagent pays for
every byte of this file on every page.

| document | owns |
|---|---|
| `CLAUDE.md` | project invariants, the store layout, and this table |
| `keying_spec.md` | the character inventory. Binds both passes and the human keying track |
| `.claude/agents/collator.md` | the OCR→TEI collation contract, whole — a collator's system prompt, spec transcluded |
| `.claude/skills/transcribe-page/` | dispatching a batch of collators, and the seam afterwards |
| `.claude/agents/groundtruth-reader.md` | the raster→ALTO reading contract, whole — a reader's system prompt, spec transcluded |
| `.claude/skills/rebuild-groundtruth/` | dispatching and adjudicating a batch of readers |
| `.claude/skills/train-zones/` | the segmenter's train→score→install loop, its measured state, and the judgement in it |
| `.claude/rules/zones.md` | code-facing zones/raster internals; loads itself when those modules are open |
| `harness/VERBS.md` | the CLI surface: every action, its reads, writes, exit contract and flags. Gated by `test_cli_surface.py` |
| `harness/README.md` | the package: module responsibilities, stores, caller invariants |
| `concordance.md` | the evidence set behind the spec — aligned pairs, flag register, per-glyph attestation |
| `docs/segmentation.md` | the second segmentation attempt: the design and why each piece is shaped as it is |
| `docs/pipeline.md` | the pipeline stage by stage, and the design reasoning behind the built stages |
| `docs/apparatus.md` | the figure track, the List of Illustrations and Authorities Quoted stores |
| `docs/rasters.md` | the source rasters, the derived trees and the `tools/` scripts |
| `docs/decisions.md` | what was settled the hard way, intact — the reasoning behind the rules |
| `docs/open-questions.md` | what is deliberately unresolved |

Two passes, not one job: collation (OCR → TEI, `tei/`) and the ground-truth loop
(raster → ALTO, `gt/ocr/`). Both dispatch one agent per page off a queue, contract
in the agent body. Ground truth disqualifies a page from the second and improves
it for the first.

# Current pipeline

Zoning (`zones predict` → editor → `gt/zones/`) → lines + recognition in one
pass (`ocr predict` → `mz/ocr/`, zones replacing blla's regions) → collation
(LLM over scan + draft + precomputed context, gated by `tei validate`) →
annotation (TBD) → compilation (TBD). The stage-by-stage detail and the design
reasoning are `docs/pipeline.md`.

# Collation

Rules are `.claude/agents/collator.md`'s, dispatch is `/transcribe-page`. What
stays here is the detector formula and the measurements that shaped the tools.

**Transcription Detection** (speculative, mechanical, no judgement): inventory-glyph match ∪ word-medial
  `[AEIL]` ∪ dot-above-g ∪ apostrophe-adjacency ∪ **English-lexicon miss**. The
  numerator is a floor — unmarked ASCII inventory members (`c` = English *sh*, plain
  `s`, `j`, `x`) are undetectable by construction, which is itself an argument for
  route-all over per-glyph triage.

  A floor is not licence for noise above it: a detector firing on ordinary
  English buries the real hits. `data/lexicon_extra.txt` (committed, seeded via
  `harness lexicon misses`) holds the binomials, ethnonyms and coinages no
  dictionary carries, and **suppresses `lexicon_miss` and nothing else**.

**Density, measured** on `1-048` and `2-030`, the two densest pages: inventory
glyphs are **3.3% of characters** but fall in **43.8% of lines**. That
asymmetry decides tool shape — the expensive act is re-orienting to a
different line, not reading one already open — **so review is line-based**,
and the span diff survives only as measurement.

## Cross-page state

Collation is per-page, dispatched a batch at a time. What crosses a page
boundary crosses through the **committed TEI**, folded by `harness tei ledger`.
The seam is the coordinator's: a page records `<!-- opens: … -->`, the witness
only it saw; `tei seam` writes the verdict after the batch.

## TEI

**Assembly is still unsettled**; the corpus teiHeader is not, and is
`tei/corpus-header.xml`. The output contract and every encoding rule are the
collator's in full. The annotation passes beyond it are TBD.

## Open

An entry leaves `docs/open-questions.md` by being settled, and says so when it goes.
