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

In the TEI this is `@resp`, naming one of the four provenance levels README.md
defines, on every Tier-1 `xml:lang` and every entity reference: `#ed` a human's
own act, `#llm` a model's work awaiting ratification, `#gt` machine output a
human ratified against the artifact (transcluded from its store), `#mz`
mechanical rule output. The last two assert nothing on their own —
**re-derived from their store on every run**, so they fail rather than go stale,
which is the whole of what admits a rank no human wrote directly.
The ranks are declared once, in the corpus teiHeader, never in a page file. The
collation pass may emit `#llm` and nothing else; `harness tei validate` errors on a
higher claim and on a missing `@resp` equally, because an unmarked span is
indistinguishable from a ratified one to anything that does not check.

**An `mz/` file names what produced it, machine-readably** — one writer,
`harness/provenance.py`, censused by `corpus provenance`. Provenance that cannot
be read back counts as none. `kind` is load-bearing: a **rule**'s output and a
**model**'s guess are both `#mz` and neither outranks a human, but they are not
the same witness.

**A comparison whose witnesses may be one witness must say so.** The hazard
recurs wherever a check's two inputs can turn out to be the same file, and keeps
being found in new places; `docs/decisions.md` records the instances.

**LLM remit.** Models read, triage, propose, restructure. A glyph they read is a
proposal until ratified; no index entry is minted unreviewed.

# Environment

- `uv` project, **Python 3.14.3**; torch 2.12.0+cu130, `cuda.is_available()`
  True in the env. `uv.lock` committed. A doc still saying 3.13 is stale.
- `kraken` 7.0.3, pinned. **The CLI was reorganized across the 3→5→6→7 majors and
  nearly every tutorial online is 4.x-era.** Verify flags against `kraken --help` /
  `ketos --help` rather than trusting remembered or documented syntax, including
  anything asserted in this file.
- eScriptorium is **out of the loop** — keying is `zones edit`/`ocr edit` in the
  browser. The ALTO stores keep its shape and `corpus mets` still exports any
  of them for it.
- GPU: Turing card, ~100× over CPU.

# Encoding

**NFD, corpus-wide** (`keying_spec.md` §1). `harness corpus normalize` is the
gate; `--convert` writes the fixes.

**Never NFKC.** It has compatibility decompositions for two inventory glyphs and
destroys them: `ᵋ` U+1D4B → plain U+025B, `˙` U+02D9 → space + combining dot.
Any `normalize()` call must name its form.

**The ASCII policy is scoped to Tier-1** (`keying_spec.md` §1). Inside the eight
Tier-1 codes, U+0027 and U+002D are the only apostrophe and hyphen; English prose
reproduces the print, **curly quotes included**. The lookalike tables differ by
scope and **must not be merged** — `test_lookalike_scope.py` holds them apart.

# Source rasters

**`scans/` is derived, not source** — `harness scans extract` **cuts** it from the
PDFs' own layers, a bitonal master per page plus its photographs, never rendered.
`docs/rasters.md` has the geometry, the coordinate migration, and what a rebuild
must swap whole.

**Page refs are `PP-NNN`** — part, and scan index within that part (`1-048`).
A page file is `<stem>-PP-NNN.*`: one kebab-case stem per text (`chukchi`,
`chukchi-mythology`, `koryak`), declared in `project.json`. NNN is a *scan
index*, not a printed folio. Part 1 runs 001–362, part 2 001–268, part 3
001–202; the printed folio runs continuously 1–732 across the volume, with
plates and front matter unpaginated. **Neither is derivable from the other**, so
a bare page number names no page and the harness rejects one. The folio is known
only where a transcribed page recorded one, and propagates via the seam ledger
(`harness/state.py`): the page says what page it is, and nothing infers it.

# Where things stand

Layout of a text, `jesup/bogoras-chukchi/` (`project.json` marks one):

    scans/  the 832 rasters, 300 dpi, bitonal but for the 236 with a photograph. Derived; not in git. The farms over it (w-figs/, w-ocr/, w-figs-blotted/,
            fig-crops/, and one per leaf kind) are derived too and point into it: a clone gets dangling links.
    gt/     the artifact reproduced or annotated, human-checked **whatever share
            a machine proposed first**: ocr/, fig/ (boxes for pictures and
            captions; no lines), zones/ (the segmentation, and the split that
            says a leaf is a plate/blank/cover/map/apparatus rather
            than a text page at all — **and such a leaf holds no zone file in
            either store: the mark is the record**), lines/ (corrections), and
            every page exemption beside them. Tracked. Caller invariants in
            `harness/README.md`.
    mz/     not-yet-human: zones/, ocr/ and fig/ as the models emitted them,
            tei/ as the rules built it, and page-img/ as a leaf is *served*: two
            layers built from the tracked master. Derived; ignored. **No view over
            any pair**: every read names `gt/` or `mz/`, and the `ocr/` and
            `zones/` symlink views that once blended them are gone.
    tei/    the collated pages, plus corpus-header.xml — the corpus teiHeader,
            a fragment gated by `harness tei header`. The header is tracked; the
            pages are **temporarily ignored** while the generator is rewritten,
            for the reason and the expiry in .gitignore.
    edition/  what is served to a reader, and nothing else — a **layer**, not a
            rank: `#ed` lives in `@resp` and also covers rulings no reader sees.
            Tracked; no rule writes here but the two tools below. `docs/edition.md`.
            toc/loi/authorities/alphabet/runs/figure_numbers.json — the book's
              apparatus, amended, which is why none of it is `gt/`.
            entities/  the encyclopedia, one file per entity under its class
              (person/, place/ …). An identity is `class:slug`, which is what
              every `@ref` holds; `entity check` gates it.
            lexicon/  one file per Tier-1 form an editor has noted; the identity
              is the form, the rest of the card is derived. `lexicon check`
              gates it. Declared and still empty.
            annotations/  the editor's own voice — notice/ renders above what it
              attaches to, supplement/ below; each attaches to pages, ToC
              sections or entities. `annotation check` gates it.
            fig-img/, page-img/  the touch-ups. An improvement on the page is
              what `gt/` may not be (`docs/apparatus.md`).
            geo/  the atlas — watersheds, language areas, named features,
              coastline. **Derived but tracked**: its sources are outside
              the repo, so a clone cannot rebuild it.
              tools/build_geo.py builds, SOURCES.md records provenance,
              `geo list` is the census.
            entity-images.json  the picture ledger, derived but tracked for
              geo/'s reason; tools/entity_images.py writes it.
    config/ what a pass is tuned by, validated at load — zones.json
            lines.json marks.json — and the editor's rulings over
            one: marks_exempt.json lexicon_extra.txt, `#ed` **rank** but no part
            of the edition, which is why they sit here and not in it.
    data/   nothing authored: pdf_images.json _migrated.json are machine
            receipts, tei_all.rng the vendored TEI schema.
    review/ one directory per page: proposal.json (a reading, not truth) and
            decision.json (adjudicated) are tracked; the images are derived and
            ignored. See harness/paths.py.
    models/ the recognizers and segmenters, this project's zones-seg included.
            fig-seg is declared but not yet trained.
    pdfs/   symlinks to the three AMNH source PDFs, outside the repo.
    train/  training working dirs, pure scratch. Ignored; artifacts go to models/.
    harness/  tools/  docs/  concordance.md  keying_spec.md — the tests live in
            harness/tests/, beside the package they cover.

Counts deliberately absent — they go stale in a file nothing regenerates.
**`harness corpus state` answers**, across every store at once as no store's own
verb can; `--stage`/`--refs`/`--limit` make it a worklist, and a page is ready to
collate when it puts one at `ocr-gt`.

## Page segmentation, second attempt

Seven declared types, fixed-width bands of a per-page-measured column, in its
own store — the first attempt's `gt/seg/` is deleted, nothing having trained
coherently on it. The design and its reasoning are
`docs/segmentation.md`; the training loop is `.claude/skills/train-zones/`;
the code-facing internals load from `.claude/rules/zones.md` when the zones
modules are open.

# Harness

`harness/` is a console script; every path resolves against the text's
directory: `--root`, else the one the cwd is in.

**Two tiers: a group, then an action** — `tei`, `ocr`, `proposal`, `zones`, `fig`,
`scans`, `views`, `train`, `lexicon`, `entity`, `annotation`, `geo`, `edition`,
`find`, `corpus`, `agents`, `verbs`. The group names what it touches; the
action what it does.

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
| `.claude/agents/collator.md` | the TEI review contract, whole — a collator's system prompt, spec transcluded |
| `.claude/skills/transcribe-page/` | dispatching a batch of collators, and the seam afterwards |
| `.claude/agents/groundtruth-reader.md` | the raster→ALTO reading contract, whole — a reader's system prompt, spec transcluded |
| `.claude/skills/rebuild-groundtruth/` | dispatching and adjudicating a batch of readers |
| `.claude/skills/read-captions/` | the figure-caption re-read, whole — contact sheets, and the blindness the comparison needs |
| `.claude/skills/train-zones/` | the zone segmenter's train→score→install loop, its measured state, and the judgement in it |
| `.claude/skills/train-figures/` | the same for the figure segmenter — trains on raw scans, and why its negatives had to be witnessed |
| `.claude/skills/train-ocr/` | the recognizer fine-tune off `gt/ocr/` — why the split unit is the page, and what the stock model is narrowly bad at |
| `.claude/rules/zones.md` | code-facing zones/raster internals; loads itself when those modules are open |
| `harness/VERBS.md` | the CLI surface: every action, its reads, writes, exit contract and flags. Gated by `test_cli_surface.py` |
| `harness/README.md` | the package: module responsibilities, stores, caller invariants |
| `concordance.md` | the evidence set behind the spec — aligned pairs, flag register, per-glyph attestation |
| `docs/segmentation.md` | the second segmentation attempt: the design and why each piece is shaped as it is |
| `docs/pipeline.md` | the pipeline stage by stage, and the design reasoning behind the built stages |
| `docs/apparatus.md` | the figure track and its editor, the List of Illustrations and Authorities Quoted stores |
| `docs/edition.md` | the entity, lexicon and annotation stores, the rule that links a form, `#mz`, and the reading view |
| `.claude/skills/curate-entities/` | writing an entry: whether it is earned, its class, its alias modes, its gloss |
| `docs/rasters.md` | the source rasters, the derived trees and the `tools/` scripts |
| `docs/decisions.md` | what was settled the hard way, intact — the reasoning behind the rules |
| `docs/open-questions.md` | what is deliberately unresolved |
| `README.md` | the four provenance levels, and the edition for a reader |
| `.claude/skills/read-moll-page/` | the Moll & Inenlikej 1957 pass, whole. Not a Bogoras corpus track; nothing it produces enters `gt/` or `tei/` |

Two passes: the ground-truth loop (raster → ALTO, `gt/ocr/`) and collation
(generated TEI → `tei/`). Both dispatch one agent per page off a queue, contract in
the agent body. Ground truth ends the first and is a **precondition** of the second.

What crosses a page boundary crosses through the **committed TEI**, folded by
`harness tei ledger`. The seam is the coordinator's, after the batch: a page
records only `<!-- opens: … -->`, the witness nobody else saw.

# Current pipeline

`zones predict` → editor → `gt/zones/`; `ocr predict` → `/rebuild-groundtruth` →
`gt/ocr/` (bare lines — a line's zone is derived by containment on every read,
never stored in the ALTO) → **`tei generate` → `mz/tei/`** (by rule: the keyed
zone labels are the paragraph boundaries) → collation (an LLM reviews that page
against the scan, gated by `tei validate`) → `tei/` → `harness edition serve`,
the reading view. Stage by stage, with the reasoning: `docs/pipeline.md`.

**The reading view renders `mz/tei/` too, under `--drafts`**, so the edition reads
from ground truth alone and collation is enrichment over a readable text rather than
the gate in front of one. It has contracted as each rung above took work off it, and
the corpus is being read end to end *before* it runs; what now stands between the
store and a usable edition is the encyclopedic work, not this stage.
`docs/pipeline.md` §4 carries what moved and why.

# Collation

**A model never authors structure a store already holds.** It judges what no rule
can — a heading from a table, where a note anchors, what language a form is — and
`tei diff` is its edits against the baseline. Rules are
`.claude/agents/collator.md`'s, dispatch is `/transcribe-page`; here, the detector
formula and the measurements that shaped the tools.

**Transcription Detection** (speculative, mechanical, no judgement): inventory-glyph
match ∪ word-medial `[AEIL]` ∪ dot-above-g ∪ apostrophe-adjacency ∪ **English-lexicon
miss**. A **floor**: unmarked ASCII inventory members (`c` = English *sh*, plain `s`,
`j`, `x`) are undetectable by construction, and a hit is never a verdict — an
inventory mark fires on ordinary German too. A floor is not licence for noise above
it: the entity store's names and `config/lexicon_extra.txt`'s coinages both
**suppress `lexicon_miss` and nothing else**.

**Density, measured** on the two densest pages: inventory glyphs are **3.3% of
characters** but fall in **43.8% of lines** — the expensive act is re-orienting to a
new line, not reading one already open, so **review is line-based**.

**Entities**, the **lexicon**, and the reading view are `docs/edition.md`'s.

**Assembly is still unsettled**; the corpus teiHeader is not, and is
`tei/corpus-header.xml`. Every encoding rule is the collator's in full.

