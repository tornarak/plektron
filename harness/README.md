# `harness/` — the tooling, module by module

The console script (`harness`, `[project.scripts]`) run from the repo root; every
path resolves against the cwd unless `--root` says otherwise. `uv run python -m
harness <verb>` is the same thing.

This file covers **structure**: what each module owns, which stores it touches, and
the invariants that bind a caller. For what a verb *does*, `harness <verb> --help`
is the source of record and is deliberately verbose. For the project's rules,
`CLAUDE.md` governs; for the character inventory, `keying_spec.md`.

## Stores, and which are writable

| path | what | written by |
|---|---|---|
| `scans/` | 832 rasters at 300 dpi. **Derived** from `pdfs/`, not in git | `pdftoppm` |
| `ocr/` | the **read view** over every OCR store — symlinks, currently all into `gt/ocr/` | nothing |
| `gt/ocr/` | 20 pages of human ground truth | `restore --commit` |
| `gt/fig/` | 252 figure ALTOs, geometry only, **no `TextLine` at all** | by hand, via eScriptorium |
| `gt/seg/` | the **first** segmentation attempt: 122 pages, full SegmOnto vocabulary, free polygons. Kept, read-only | by hand, via eScriptorium |
| `gt/zones/` | the **current** segmentation: seven types, fixed-width bands, `+ _train.lst _eval.lst _exempt.lst _rule_exempt.json _ink_exempt.json` | `zones --serve` |
| `tei/` | the collation output, and the system of record for seam state | the collation pass |
| `data/` | `readings.md` `loi.json` `toc.json` `authorities.json` `lexicon_extra.txt` `zones_config.json` | by hand |
| `review/<ref>/` | `proposal.json` + `decision.json` authored; crops/sheets/zoom/html derived | `review --serve`, `lines`, `zoom` |
| `scans-fig-blotted/` | training rasters: figures painted **white**. Derived, ignored; the 580 figure-less pages are symlinks | `zones --blot` |
| `bogoras-seg/` | symlink farm pairing each zone ALTO with its blotted raster for `ketos segtrain`. Derived, ignored | `zones --assemble` |

**`gt/seg/` and `gt/zones/` are two schemes, not one store in two states.** The label
sets differ and so does the geometry regime — free polygons drawn around ink against
fixed-width bands of a configured column — and *nothing in an ALTO says which scheme
produced it*. That is the same absence of an internal witness that lost 18 pages of
transcription when a file's role lived only in the directory holding it, so the role
lives in the directory again and the two do not alias. Blocks written by `zones`
also carry an `mz_` id prefix, so a file identifies itself even out of context.

**Reads may resolve through `ocr/`; writes may not.** `ocr/*.xml` are symlinks, so
naming them on a write hides which real store is being touched — and a write landing
in a store nobody meant to touch is how this repo lost its ground truth once. Reading
is the opposite case: resolving a page to its current OCR is the entire purpose of a
union view. `lines.DEFAULT_ALTO_DIR` is that default; `restore` names `gt/ocr/`.

## Modules

**`cli.py`** — argparse, and the dispatch chain. The module docstring is the parser
`description`, so it reaches `--help`; keep it current. Verb help is prose, not
labels, because these verbs encode judgements a one-word gloss cannot carry.

**`context.py`** — the `PP-NNN` contract (`parse_ref`, `norm_ref`, `stem_for`) and
`build_context`, the per-page input the collation pass consumes. Everything in it is
deterministic and precomputed: a pass that re-derived any of it could disagree with
the validator that checks it.

**`state.py`** — derived seam state. Folio comes from a committed TEI's `<pb n>` and
propagates forward; `expected_folio` is null wherever the chain breaks, and null is
the answer, not a failure. Also `toc_window`/`toc_search`/`toc_near`.

**`validate.py`** — the gate. One 240-line `validate()` plus `Report`. Exit 1 on FAIL.
`RESP_RANKS` is the operative definition of the three provenance ranks until the
corpus teiHeader exists.

**`detectors.py`** — two jobs, deliberately: (a) speculative triage, `detect_all`,
whose output is a flag meaning "worth a look"; (b) the corpus-frequency mining behind
`lexicon`'s five modes. Plus `unlicensed_marks`/`MARK_LICENSE`, which is **not**
triage — it answers "impossible", is reported as an error, and is the one check here
that can block a write.

**`normalize.py`** — corpus normal form: NFD (never NFKC), §2.9 spacing, and the
lookalike census. Bare form and `--check` are the same thing; `--convert` writes.
NFD and spacing are mechanical so they may be written unattended; every lookalike is
report-only, because it is a human ruling.

**`lines.py`** — line identity as the addressable unit, plus the crop/sheet/zoom
writers. Best-documented module; read it before touching geometry.

**`review.py`** — the largest, and it does four things: span diffing, decision
persistence (temp-then-rename, a `.prev`, and an append-only `.jsonl` journal),
`restore`, and a ~450-line embedded browser app in `render_queue_html`.

**`figures.py`** — the figure track: `gt/fig/` geometry against `data/readings.md`
text, reconciled by `reconcile()` (the `figures` verb). Also the generic sheet
compositor `lines.py` reuses, and `read_blocks` — **the one reader of the
`OtherTag/@LABEL` + `TAGREFS` zone encoding**, store-agnostic, with `zones()` and
`zones.read_zones` as its two bindings.

**`zones_config.py`** — loads and checks `data/zones_config.json`: the seven types
with their keys and colours, the per-part text measure and anchor calibration, the
declarative order rules. `order_warnings` is pure and is transcribed into the
editor's JS, with `tests/test_zones_order.py` holding the two together. Every rule
here is a *warning* — nothing in this config can refuse a save.

**`zones.py`** — the `gt/zones/` store: the ALTO writer (eScriptorium dialect, no
`TextLine`, `mz_` ids, atomic with a `.prev` and a journal), the split lists, the
exemptions, `validate_page`/`validate_corpus`, the blot sweep and the segtrain
assembly. **Errors are mechanical and set the exit code; the ordering assumptions
are warnings.**

Two exemption sidecars, and they answer different questions. `_rule_exempt.json`
says a page arranges itself unusually and the order rules may stop saying so.
`_ink_exempt.json` says a particular *band* of ink is not type — a smudge, a gutter
blob, offset from the facing page — and carries the reason as a required field. The
second is scoped to a band and never to a page, because the ink check is the only
thing that can see a dropped zone and a page-wide suppression would hide the next
one. Both keep reporting what they excuse, flagged.

**`zones_ui.py`** — the segmentation editor. Same server shape as `review.serve`,
with a `GET /page/<ref>.png` route because a full page as a data URI is ~10 MB of
markup. The client sends a column index and never an x — the geometry is re-measured
server-side on save, so a zone of the wrong measure has no field to travel in.

**`authorities.py`** — search over the book's own 73-work bibliography. Returns every
hit ranked and resolves nothing: 51 sigla share 34 names, so one answer would be
manufactured, and no hit at all is legitimate because the list is explicitly open.

**`paths.py`** — the `review/<ref>/` layout authority, and `DERIVED`.
**`proposal_check.py`** — a proposal's `resolved` field against its `text`, plus the
field-editing verbs. **`codepoints.py`**, **`emit.py`** — one job each.

## Invariants that bind callers

- **Dedupe by real path when walking stores.** `ocr/*.xml` are symlinks into
  `gt/ocr/`, so a naive walk sees each file twice, and a writer meets it again under
  the second name, finds it already done, and skips silently — the report then
  undercounts exactly what it touched. `normalize.scoped_files` does this.
- **`context._lines_from_alto` drops empty lines and discards `@ID`**, so its index
  is *not* the ALTO's, and `detector_flags`' line numbers inherit that offset. Join
  through `lines.page_lines`, never through a detector flag's line number.
- **A line polygon can exclude printed text.** `1-074` prints `5.` and `9.` outside
  their boxes; `1-073` puts its `5.` and its folio outside *every* box on the page.
  The omission is horizontal, so vertical padding never reaches it — `--margins`
  widens to the PrintSpace, which is where the excluded material sits.
- **Reading `String/@CONTENT` out of `gt/fig/` returns `""` for every zone.** Not an
  error — nothing, which is worse. Caption text comes from `figures.readings()`.
- **The three lookalike tables differ by scope and must not be merged.** See
  `tests/test_lookalike_scope.py`, which exists because a consolidation was very
  nearly carried out on the strength of an audit that called the difference drift.
- **Keep one fixed key set across a list of records.** The TOON encoder collapses a
  uniform list to a header plus rows; one ragged record de-tabularizes the whole
  table into the verbose nested form.
- **Resolve a zone's type by `OtherTag/@LABEL`, never by tag ID.** eScriptorium
  assigns those per export (`BT55`/`BT56` in one, `BT68`/`BT69` in the next), so
  hardcoding them fails silently rather than loudly — see
  `tools/strip_graphiczone_lines.py`, where it "quietly became a no-op that
  reported success". `figures.read_blocks` is the only place that does this.
- **An empty zone file is a claim, not an absence.** A plate has no text column, so
  zero zones is its correct segmentation; a page nobody opened is also zero zones.
  Only the file's existence separates them (`zones.has_zones`), which is why the
  editor never writes one on navigation and only an explicit save can make one.
- **Overlap tests need both axes.** Two-column pages put zones side by side at the
  same height on purpose. A y-only test reports every row of `3-005` as a
  collision, which is the mirror of the bug that made `lines` read 14 body lines of
  `1-151` as caption.
- **The text measure is constant; its position on the raster is not.** The column
  is ~1780 px wide everywhere, but its left edge drifts up to 236 px inside a
  single part — scan registration, not typography. Anything drawing or checking a
  column must anchor per page (`zones.measure_columns`), never from a per-part
  constant, and never from scan-index parity: parity explains only part of the
  drift, which is why verso/recto is not a concept in this code.

## Tests

`uv run pytest`. Fixtures live in `tmp_path`, not the live corpus — a test asserting
over `gt/ocr/` or `data/` fails the day the corpus legitimately changes, which trains
everyone to ignore it. The exceptions are explicit and are facts about the printed
book or about committed configuration rather than about any code: the
citation-resolution tests, the `DERIVED`-versus-`.gitignore` check, and the
`data/zones_config.json` checks — that file is data two modules trust, and nothing
else would notice a stray comma in it.

## No ad-hoc Python

If a one-off script is the answer, a verb is missing or an existing one is being
under-used. `proposal-check --codepoints` instead of `python3 -c "...ord(ch)..."`;
`harness zoom` instead of a crop script; `proposal-check --set` instead of a heredoc
patching one JSON field — a hand-typed `Edit` can silently fail to match the file's
own NFD form. This has been stated and not followed more than once here.
