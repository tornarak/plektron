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
| `mz/zones/` | what the trained segmenter emitted: raw kraken ALTO, free polygons, kraken's ids. Derived, ignored | `zones --predict` |
| `zones/` | the **read view** over both zone stores — symlinks, the human file always winning. Derived, ignored | `zones --link` |
| `tei/` | the collation output, and the system of record for seam state — including `corpus-header.xml`, which is a fragment, not a page | the collation pass, `seam --commit` |
| `data/` | `readings.md` `loi.json` `toc.json` `authorities.json` `lexicon_extra.txt` `zones_config.json` | by hand |
| `review/<ref>/` | `proposal.json` + `decision.json` authored; crops/sheets/zoom/html derived | `review --serve`, `lines`, `zoom` |
| `scans-fig-blotted/` | training rasters: figures painted **white**. Derived, ignored; the 580 figure-less pages are symlinks | `zones --blot` |
| `train/bogoras-seg/` | training scratch: the symlink farm, its two `.lst` files, and each run's checkpoints. Derived, ignored, **read by nothing once training ends** | `zones --assemble`, `ketos segtrain` |
| `models/bogoras-seg/` | the models this project trains — **tracked**, each with the split it saw as `<model>.train.lst`/`.eval.lst` and a small `<model>.json` | `zones --install --commit` |
| `models/` (rest) | downloaded third-party weights, 675 MB, ignored | not authored here |

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

**The same rule, again, for zones: reads may resolve through `zones/`; writes name
`gt/zones/`.** `save_zones` takes no store parameter at all, which is the strongest
form of that — there is no argument in which a caller could name somewhere else. The
predictor writes `mz/zones/` through its own path and never touches `gt/`, and the
one route from one store to the other is a human in the editor: a page with no
ground truth of its own opens on the machine's reading as an *unsaved proposal*,
labelled as one, and saving it writes `gt/zones/` through the same `save_zones` every
other page uses. That is the shape `proposal.json` → `decision.json` → `restore`
already has on the OCR side.

`zones --from` deliberately offers `gt` and `mz` and **not** the view, and refuses a
free directory path where `lines`/`zoom`/`review`/`restore` accept one. Two reasons,
both about what an exit code means: a free path is how a check ends up compared
against its own input by typo, and checking through the view would blend ratified and
unratified pages under one verdict. Over `gt/` errors gate; over `mz/` the identical
report is measurement and always exits 0, because nothing there is ratified and a raw
predicted polygon fails the fixed-measure width check by construction.

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

**`ids.py`** — structural ids, `{kind}-{PP-NNN}-{ordinal}`. The ordinal is the
element's **position** among same-kind elements in document order, not a tally of
ids minted — so ids are sparse, every one is verifiable by counting the tree alone,
and adding a referrer to one element never renumbers another. Kinds are exactly
what something can point at (`term`, `list`, `table`); a kind no referrer can name
would be dead surface in the gate. `--pair` links a `<gloss>` to its `<term>` where
containment decides and **refuses where it does not** — two pairs in one item is an
editorial question, not a branch to pick. Note the trap the ordinal creates: it is
not the printed item number, since `1-100`'s item 4 holds two terms.

**`seam.py`** — page seams. A gap carries one fact — is an element open across it —
and that fact lands on two elements, one per page. The page *after* the gap writes
both, because it is the only place both witnesses exist: it holds the predecessor's
tail, its own opening text and its own first-line indent. `@part` is two independent
bits (begins-before, runs-past) spelled as nothing/`I`/`M`/`F`, and `set_seam` sets
one bit per side, which is what makes the operation order-independent and reversible.
**No sidecar**: the committed TEI is the record, and the I/M/F arithmetic reads back
out of the files it wrote to. Also `tail()`, which `context` surfaces as `prev_tail`
— the previous page's last element as *markup*, since a flattened excerpt loses the
`@n` and `xml:lang` that are the seam's actual witnesses.

**`validate.py`** — the gate. `validate()` plus `Report`; exit 1 on FAIL. Also
`check_corpus_header()`, behind `harness header`, which holds `RESP_RANKS` and
`tei/corpus-header.xml` to each other: two files carry one fact, and per-page
validation deliberately never resolves `@resp` locally, so nothing else could notice
them drifting apart.

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
editor's JS, with `harness/tests/test_zones_order.py` holding the two together. Every rule
here is a *warning* — nothing in this config can refuse a save.

**`zones.py`** — the zone stores: the ALTO writer (eScriptorium dialect, no
`TextLine`, `mz_` ids, atomic with a `.prev` and a journal), the split lists, the
exemptions, `validate_page`/`validate_corpus`, the blot sweep, the segtrain
assembly, the predictor and the view. **Errors are mechanical and set the exit code;
the ordering assumptions are warnings.**

`zone_dir`/`alto_for` take a `store`, defaulting to `gt/zones/`, and the **default is
the design**: every sidecar reader calls `zone_dir(root)` bare and so keeps resolving
to the human store without a line of change. That is not an accident to tidy up
later — a split, a rule exemption and an ink ruling are statements about a *page*, and
there is no such thing as the machine store's opinion of which pages are held out.
`_ink_cache.json` is gt-only for a sharper version of the same reason: it is keyed by
ref alone, so a machine verdict landing there would sit in the page list's column
indistinguishable from one about work a human has actually done.

Two things `mz/zones/` deliberately does not do. It is **not normalised** — free
polygons at whatever x kraken drew, kraken's own ids, kraken's own dialect — because
a store that tidied its contents could no longer tell you what the model did;
snapping to a configured band is a human act and happens in the editor. And its
blocks carry **no `mz_` prefix** despite the store's name, which is the near-collision
worth knowing about: `mz_` marks a band a human drew against a configured column, so
a predicted block keeping kraken's id is precisely what makes the two distinguishable
from the bytes alone.

`score` and `remap_model` exist because the first trained model scored **0.2% label
agreement on its own training data** — below the ~14% that guessing among seven
classes gives, which is the signature of a wrong mapping rather than a weak model.
`--resize` had permuted the class names while the geometry was learned correctly.
`score` establishes which of the two it is by deriving a 1-1 map on the training
pages and testing it on the held-out ones (93.9%, so: relabelling); `remap_model`
renames the output channels, refusing unless the map is bijective, holds out, and
covers every declared class. **Run `--score` after every training run** — nothing
else can see this fault, because the ALTO is well-formed and the boxes are right.

`load_segmenter` exists mostly to hold two findings about kraken 7.0.3 that cost time
to establish: `TorchVGSLModel.load_model` is CoreML-only and fails inside protobuf on
a safetensors file (`Wire format was corrupt`, which reads as a damaged model rather
than the wrong reader), its deprecation notice names a `kraken.registry.load_model`
that **does not exist in this version**, and `ketos segtrain` does not write the
`hyper_params` key that `blla.segment` then reads unguarded — so every model this
project trains raises `KeyError: 'hyper_params'` on its first inference. See the
docstring; re-verify after any kraken upgrade.

Two exemption sidecars, and they answer different questions. `_rule_exempt.json`
says a page arranges itself unusually and the order rules may stop saying so.
`_ink_exempt.json` says a particular *band* of ink is not type — a smudge, a gutter
blob, offset from the facing page — and carries the reason as a required field. The
second is scoped to a band and never to a page, because the ink check is the only
thing that can see a dropped zone and a page-wide suppression would hide the next
one. Both keep reporting what they excuse, flagged.

The editor's **store selector** (`/`, or the three HUD pills) is orthogonal to the
itinerary: the itinerary chooses the pages, the selector chooses whose reading of
them is drawn — `zones` (the view, default), `gt`, `mz`. `page_state(store=...)`
resolves it server-side, including the snapping and the presence counts, so the
client never re-derives the store rule. The `zones` pill reports what the *view*
resolves to, which is deliberately not an echo of the current selection: with `mz`
pinned on a page that has both, `shown` is `mz` while the view still answers `gt`.

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
  `harness/tests/test_lookalike_scope.py`, which exists because a consolidation was very
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
