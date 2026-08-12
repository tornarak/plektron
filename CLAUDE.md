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

In the TEI this is `@resp`, on every Tier-1 `xml:lang` and every entity reference,
naming one of five ranks: `#ed` ratified (a human confirmed it against the page),
`#llm` proposed (a model read it), `#htr` unexamined (recognizer output), `#gt`
adopted (transcluded from adjudicated ground truth), `#mz` rule-applied (an entity
link from a human's alias table). The last two assert nothing on their own —
**re-derived from their store on every run**, so they fail rather than go stale,
which is the whole of what admits a rank no human wrote directly.
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
- eScriptorium is **out of the loop** — keying is `zones edit`/`ocr edit` in the
  browser. The ALTO stores keep its shape and `fig mets` still exports for it.
- GPU: Turing card, ~100× over CPU.

# Encoding

**NFD, corpus-wide** (`keying_spec.md` §1). `harness corpus normalize` is the
gate; `--convert` writes the fixes.

**Never NFKC.** It has compatibility decompositions for two inventory glyphs and
destroys them: `ᵋ` U+1D4B → plain U+025B, `˙` U+02D9 → space + combining dot.
Any `normalize()` call must name its form.

**The ASCII policy is scoped to Tier-1** (`keying_spec.md` §1). Inside the seven
Tier-1 codes, U+0027 and U+002D are the only apostrophe and hyphen; English prose
reproduces the print, **curly quotes included**. The lookalike tables differ by
scope and **must not be merged** — `test_lookalike_scope.py` holds them apart.

# Source rasters

**`scans/` is derived, not source** — `pdftoppm` over `pdfs/`, then
`tools/greyscale_scans.py --commit`, and a rebuild that skips the converter makes
every raster sweep cost three times what it should. `docs/rasters.md` has the
master's geometry, the conversion's safety argument and the dpi mapping rule.

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
    gt/     what a human has been through: ocr/, fig/ (bounding boxes for the
            pictures and their captions; no lines), zones/ (the current
            segmentation), lines/ (the corrections overlay). Tracked.
    mz/     not-yet-human: zones/, ocr/ and fig/ as the models emitted them, and
            tei/ as the rules built it. Derived; ignored. No view over fig or tei.
    ocr/  zones/  the read views over the paired stores — symlinks, the human
            file always winning. Derived; ignored. Never written through.
    tei/    the collated pages, plus corpus-header.xml — the corpus teiHeader,
            a fragment gated by `harness tei header`. The header is tracked; the
            pages are **temporarily ignored** while the generator is rewritten,
            for the reason and the expiry in .gitignore.
    entities/  the encyclopedia, one markdown file per entity under its class
            (person/, place/, event/ …). An identity is `class:slug`, which is
            what every `@ref` holds. Tracked; `entity check` gates it.
    lexicon/  one file per Tier-1 form an editor has written a note about; the
            identity is the form, and the rest of its card is derived. Tracked;
            `lexicon check` gates it.
    data/   readings.md  loi.json  toc.json  authorities.json  lexicon_extra.txt
            zones_config.json  lines_config.json  tei_all.rng (the schema).
    data/geo/  the atlas's shapes — watersheds, language areas, named
            features, coastline.
            **Derived but tracked**, the one store that is: its sources are
            outside the repo, so a clone cannot rebuild it. tools/build_geo.py
            builds, SOURCES.md records provenance, `geo list` is the census.
    review/ one directory per page: proposal.json (a reading, not truth) and
            decision.json (adjudicated) are tracked; the images are derived and
            ignored. See harness/paths.py.
    models/ the recognizers and segmenters, this project's zones-seg and
            fig-seg included.
    pdfs/   symlinks to the three AMNH source PDFs, outside the repo.
    train/  training working dirs, pure scratch. Ignored; artifacts go to models/.
    harness/  tools/  docs/  concordance.md  keying_spec.md — the tests live in
            harness/tests/, beside the package they cover.

Counts deliberately absent — they go stale in a file nothing regenerates.
**`harness corpus state` answers**, across every store at once as no store's own
verb can; `--stage`/`--refs`/`--limit` make it a worklist, and a page is ready to
collate when it puts one at `ocr-gt`.

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

**Two tiers: a group, then an action** — `tei`, `ocr`, `proposal`, `zones`, `fig`,
`views`, `lexicon`, `entity`, `edition`, `find`, `corpus`, `agents`. The group names
what the command touches; the action names what it does to it.

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
| `.claude/skills/train-zones/` | the zone segmenter's train→score→install loop, its measured state, and the judgement in it |
| `.claude/skills/train-figures/` | the same for the figure segmenter — trains on raw scans, and why its negatives had to be witnessed |
| `.claude/rules/zones.md` | code-facing zones/raster internals; loads itself when those modules are open |
| `harness/VERBS.md` | the CLI surface: every action, its reads, writes, exit contract and flags. Gated by `test_cli_surface.py` |
| `harness/README.md` | the package: module responsibilities, stores, caller invariants |
| `concordance.md` | the evidence set behind the spec — aligned pairs, flag register, per-glyph attestation |
| `docs/segmentation.md` | the second segmentation attempt: the design and why each piece is shaped as it is |
| `docs/pipeline.md` | the pipeline stage by stage, and the design reasoning behind the built stages |
| `docs/apparatus.md` | the figure track and its editor, the List of Illustrations and Authorities Quoted stores |
| `docs/edition.md` | the entity and lexicon stores, the rule that links a form, `#mz`, and the reading view |
| `docs/rasters.md` | the source rasters, the derived trees and the `tools/` scripts |
| `docs/decisions.md` | what was settled the hard way, intact — the reasoning behind the rules |
| `docs/open-questions.md` | what is deliberately unresolved |

Two passes: the ground-truth loop (raster → ALTO, `gt/ocr/`) and collation
(generated TEI → `tei/`). Both dispatch one agent per page off a queue, contract in
the agent body. Ground truth ends the first and is a **precondition** of the second.

What crosses a page boundary crosses through the **committed TEI**, folded by
`harness tei ledger`. The seam is the coordinator's, after the batch: a page
records only `<!-- opens: … -->`, the witness nobody else saw.

# Current pipeline

`zones predict` → editor → `gt/zones/` → `ocr predict` → `/rebuild-groundtruth` →
`gt/ocr/` → **`tei generate` → `mz/tei/`** (by rule: the keyed zone labels are the
paragraph boundaries) → collation (an LLM reviews that page against the scan, gated
by `tei validate`) → `tei/` → `harness edition serve`, the reading view. Stage by
stage, with the reasoning: `docs/pipeline.md`.

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
it: the entity store's names and `data/lexicon_extra.txt`'s coinages both
**suppress `lexicon_miss` and nothing else**.

**Density, measured** on the two densest pages: inventory glyphs are **3.3% of
characters** but fall in **43.8% of lines** — the expensive act is re-orienting to a
new line, not reading one already open, so **review is line-based**.

**Entities**, the **lexicon**, and the reading view are `docs/edition.md`'s.

**Assembly is still unsettled**; the corpus teiHeader is not, and is
`tei/corpus-header.xml`. Every encoding rule is the collator's in full.

