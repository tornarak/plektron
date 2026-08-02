# `harness/` — the tooling, module by module

The console script (`harness`, `[project.scripts]`) run from the repo root; every
path resolves against the cwd unless `--root` says otherwise. `uv run python -m
harness <group> <action>` is the same thing.

This file covers **structure**: what each module owns, which stores it touches, and
the invariants that bind a caller. For what an action *does* — what it reads, what
it writes, what its exit code means — **`harness/VERBS.md` is the source of record**,
held against the argparse tree by `harness/tests/test_cli_surface.py`; `harness <group>
<action> --help` carries the same contract per flag and is deliberately verbose. For
the project's rules, `CLAUDE.md` governs; for the character inventory,
`keying_spec.md`.

## Stores, and which are writable

| path | what | written by |
|---|---|---|
| `scans/` | 832 rasters at 300 dpi. **Derived** from `pdfs/`, not in git | `pdftoppm` |
| `ocr/` | the **read view** over both OCR stores — symlinks, the human file always winning. Derived, ignored; nothing rebuilds it automatically, so `ocr pages --show-store` reports what each link *actually* reaches | `ocr link`, and `ocr predict` for the page it wrote |
| `gt/ocr/` | 21 pages of human ground truth | `ocr restore --commit`, `ocr adopt-gap --commit` (geometry only) |
| `mz/ocr/` | what the models emitted: lines from `blla`, text from CATMuS, structured by the zones. Derived, ignored | `ocr predict` |
| `gt/fig/` | 252 figure ALTOs, geometry only, **no `TextLine` at all** | by hand, via eScriptorium |
| `gt/seg/` | the **first** segmentation attempt: 122 pages, full SegmOnto vocabulary, free polygons. Kept, read-only | by hand, via eScriptorium |
| `gt/zones/` | the **current** segmentation: seven types, fixed-width bands, `+ _train.lst _eval.lst _exempt.lst _rule_exempt.json _ink_exempt.json` | `zones edit` |
| `mz/zones/` | what the trained segmenter emitted: raw kraken ALTO, free polygons, kraken's ids. Derived, ignored | `zones predict` |
| `zones/` | the **read view** over both zone stores — symlinks, the human file always winning. Derived, ignored | `zones link` |
| `tei/` | the collation output, and the system of record for seam state — including `corpus-header.xml`, which is a fragment, not a page | the collation pass, `tei seam --commit` |
| `data/` | `readings.md` `loi.json` `toc.json` `authorities.json` `lexicon_extra.txt` `zones_config.json` | by hand |
| `review/<ref>/` | `proposal.json` + `decision.json` authored; crops/sheets/zoom/html derived | `ocr review --serve`, `ocr crops`, `ocr zoom` |
| `scans/w-figs-blotted/` | training rasters: figures painted **white**. Derived, ignored; the 580 figure-less pages are symlinks | `zones blot`, `views build w-figs-blotted` |
| `scans/w-figs/` | the raster of every page carrying a `gt/fig/` ALTO — a selection, not a view. Derived, ignored | `views build w-figs` |
| `scans/w-ocr/` | raster beside ALTO for every page a human has been through. Membership is `gt/ocr/`; the ALTO link points at the `ocr/` **view**, so promoting a page needs no rebuild. Derived, ignored | `views build w-ocr` |
| `train/bogoras-seg/` | training scratch: the symlink farm, its two `.lst` files, and each run's checkpoints. Derived, ignored, **read by nothing once training ends** | `zones assemble`, `ketos segtrain` |
| `models/bogoras-seg/` | the models this project trains — **tracked**, each with the split it saw as `<model>.train.lst`/`.eval.lst` and a small `<model>.json` | `zones install --commit` |
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

**`cli/`** — the two-tier parser, one module per group: `_tei _ocr _proposal _zones
_lexicon _find _corpus _views`, each exposing `register(subparsers, common)` and one
`run_*` handler per action, which returns the exit code. `__init__.py` holds
`main`, `build_parser` (separate so the surface test can walk the tree without
running anything), and the rename trap. `_common.py` holds the `--root`/`--json`
parent, the `out` printer, the two walkers, the three rename tables, and the
multi-ref machinery:

| helper | what it is for |
|---|---|
| `refs_arg(p, all_=…)` | the `PP-NNN [PP-NNN ...]` positional. `nargs` is `+`, or `*` with a `--all` whose help must name *what it enumerates* — "every page" is four different sets here |
| `page_refs(a)` | the refs named, `[]` for `--all`. **Parses every one before the caller does any work**, and holds the three-way exclusion between refs, `--all` and `--itinerary` |
| `one_page_only(a, …)` | refuses a per-page flag given several refs. `--out` is why it exists: nothing errored before, the second page overwrote the first's images |
| `out_per_ref(a, pairs)` | one ref emits what it always did; several pool with `ref` first. **Refuses a list-valued field** rather than degrading the whole table |
| `out_report_per_ref` | the same for a report *with* list fields: counts in the row, each list its own ref-keyed table |
| `walk_positionals` | `walk_surface` sees only `option_strings`, so it cannot see a positional at all; the plural gate needs this second walk |

Four things about it that are load-bearing rather than stylistic. **The globals
parent attaches to every *action* parser**, not to the group parsers: with two tiers
the last parser to run is the action's, so a group-tier registration would make
`harness zones predict --json` a parse error. **The rename trap consults the
parser's own action names** before matching a retired flag, because `--ink` is both
a retired `zones` flag and a live `zones check` flag, and a positional trap would
reject the correct new spelling. **A retired positional *value* needs its own
table** (`RENAMED_VALUES`), the flag scan only looking at tokens that begin with
`-`. And **`build_parser` takes no side effects**, so the gate test can build it
in-process.

**`out_per_ref`'s one-pair shortcut is correct at the top level and wrong in a
sub-table**, which is worth knowing before reusing it. At the top level the count
decides the shape because the caller named one page. Inside `out_report_per_ref`
the caller named several and the rows are a *subset* of them, so dropping the `ref`
column would leave a table whose rows belong to a page it does not name. `_pool`
is the unconditional form and is what the sub-tables use.

It was one module and a 1,000-line `main` until the reorganization, with `zones`
alone accounting for 38% of the dispatch. The module docstring is still the parser
`description`, so it reaches `--help`; keep it current. Action help is prose, not
labels, because these encode judgements a one-word gloss cannot carry.

**`farms.py`** — the derived trees as a declared set. `FARMS` names each one once
(path, kind, what its builder must read, what builds it, how deep a check can look);
`relink`/`rebuild` are the linking every builder shares, replacing five verbatim
copies of the same three lines and collapsing `recognize.link_view` and
`zones.link_view`, which were identical and each called the other its twin in a
docstring. `survey` is what `views check` prints.

Two things a caller must know. **`relink(resolve=False)` is a bug class with a
name**: resolving a target that is itself a symlink follows it to the far end, which
is what once sent `zones assemble`'s .lst paths back into `gt/zones/` so the blot
links were never read. `scans/w-ocr/` needs the unresolved form for the same reason,
and a test for it must assert on `readlink` — resolved, the link opens the same bytes
and any content-based check passes.

And **`require` is the scope of the absence rule, not a general guard.** It raises
only for a registered farm path. A store that holds nothing is a record that is
empty, which is a true statement about the corpus and the ordinary state of a fresh
clone; a farm that does not exist is a question nobody asked. `context._refs_under`
routes both through this, which is why `harness ocr pages` refuses on a clone while
`--store mz` still answers `[0]`.

**`context.py`** — the `PP-NNN` contract (`parse_ref`, `norm_ref`, `stem_for`) and
`build_context`, the per-page input the collation pass consumes. Everything in it is
deterministic and precomputed: a pass that re-derived any of it could disagree with
the validator that checks it.

Also `_running_title`, the page's own folio, read from the three zones a number can
print in — `FOLIO_ZONES`, in order of confidence — and the second witness to
`state.py`'s prediction. `APPARATUS_ZONES` is the same three, kept out of
`catmus_draft`; the exclusion lives in `build_context` and **not** in
`_lines_from_alto`, which also feeds the lexicon frequency tables that
`keying_spec.md` §5.1 cites. Same reader, two consumers, one exclusion.

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
`check_corpus_header()`, behind `harness tei header`, which holds `RESP_RANKS` and
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

**`recognize.py`** — zones to text: `blla` baselines, CATMuS recognition, the whole
thing structured by the zones the `zones/` view supplies, written to `mz/ocr/`.
Also `link_view`/`link_one`, the `ocr/` farm — `zones.link_view`'s twin, and
deliberately the same shape, since the argument for the layout is that a file's
role must not live only in the directory holding it.

Three caller invariants. **It cannot name `gt/ocr/`** — there is no `store`, `out`
or `alto_dir` parameter, the property `save_zones` has and for the reason this
project lost 18 pages. **`tags` on a `Region` is `{key: [{"type": label}]}`, never
`{key: label}`** — `serialize` builds its typology with `for t in v if 'type' in t`,
so a bare string iterates characters, matches none, and writes `TAGREFS=""` against
a lone `OtherTag LABEL="default"`: geometry, ids and reading order all correct, and
the labels — the one thing the pass exists to add — silently absent. And **what
gets serialized is the `ocr_record` list from `rpred`, never the lines with `text`
set on them**: `serialization.serialize` reads `record.prediction` and nothing else,
so the obvious spelling writes `CONTENT=""` on every line, a well-formed page with
no words on it, which is the `gt/fig/` failure exactly.

Third, **`serialize`'s `sub_line_segmentation` defaults to `True`** and must be
turned off: handed `ocr_record`s it emits a `<String>` per word, an `<SP>` per space
and a `<Glyph>` per character, which is 3375 glyphs and a 1.4 MB file where
`gt/ocr/` holds 49 strings in 30 KB. The size is the symptom; the rule is that the
two stores sit under one view, so they must be the same shape. They read alike
either way — `page_lines` concatenates a line's `String`s — which is how the
divergence survives until something reads `String/@CONTENT` expecting a line.

All three were found by reading a written page back rather than by trusting what
the writer reported about itself; none raised an error, and the file looked right
from the outside in every case.

**`review.py`** — the largest, and it does five things: span diffing, decision
persistence (temp-then-rename, a `.prev`, and an append-only `.jsonl` journal),
`restore`, `corrections`, and a ~450-line embedded browser app in
`render_queue_html`. `corrections` lives here rather than in `proposal_check`
because it reads *both* `proposal.json` and `decision.json`, and only this module
owns both — it is the pass's own error profile, which `restore` had been computing
per page and discarding.

**`restore_skip` is `predict_skip`'s shape and exists for the same reason**: one
rule in one place, with two callers (`--all` and the multi-ref loop) that would
otherwise each grow a copy of it. It answers a sharper question than `restore`'s
own `force` guard can, and has to — every page in `gt/ocr/` holds text, so that
guard would refuse the whole store and a sweep refusing everything is not a sweep.
The question is *is this decision newer than the ground truth it produced*: if not,
the page was restored since it was adjudicated; if so, that adjudication is the
human's own latest act and the sweep carries `force` on its behalf, the timestamps
establishing the intent the flag would. Deliberately not keyed on the *proposal*'s
mtime — a proposal is a reading, not an adjudication, and re-authoring one licenses
no write.

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

**`marks.py`** — is a reading's character distribution plausible, before a human
opens it. Three arms of unequal strength: `rare` (a form whose character the corpus
almost never sets), `conflict` (one word spelled two ways against the store), and
`ratio`, which points and never decides. Two properties bind callers. The prior is
**leave-one-out unconditionally** — after `restore` a page's gt *is* the adjudicated
descendant of its own proposal, so including it is the two-witnesses-that-are-one
collapse — and it is drawn from **density-selected** pages, which every report states
in `prior_note`. `is_medial` generalises `detectors.MEDIAL_CAPS` to the small caps
rather than copying its lookbehind class; the two agree on every live position and a
test holds them together.

**`paths.py`** — the `review/<ref>/` layout authority, and `DERIVED`.
**`proposal_check.py`** — a proposal's `resolved` field against its `text`, plus the
field-editing verbs; `check` also runs `marks`' two deterministic arms when given a
ref. **`codepoints.py`**, **`emit.py`** — one job each.

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

`uv run pytest`, which also runs `ruff check` (`test_lint.py`). Fixtures live in `tmp_path`, not the live corpus — a test asserting
over `gt/ocr/` or `data/` fails the day the corpus legitimately changes, which trains
everyone to ignore it. The exceptions are explicit and are facts about the printed
book or about committed configuration rather than about any code: the
citation-resolution tests, the `DERIVED`-versus-`.gitignore` check, and the
`data/zones_config.json` checks — that file is data two modules trust, and nothing
else would notice a stray comma in it.

`test_cli_surface.py` is the other exception and is the newest: it builds the real
parser and holds it against `VERBS.md` in both directions. Until it existed **nothing
tested the CLI at all** — every other test imports module functions directly, so a
verb could be renamed or a documented mode could vanish with a green suite
throughout. That is not a hypothetical: it is how the surface this file describes
drifted into needing a reorganization.

## No ad-hoc Python

If a one-off script is the answer, an action is missing or an existing one is being
under-used. `harness proposal codepoints` instead of `python3 -c "...ord(ch)..."`;
`harness ocr zoom` instead of a crop script; `harness proposal set` instead of a
heredoc patching one JSON field — a hand-typed `Edit` can silently fail to match the
file's own NFD form. This has been stated and not followed more than once here, and
part of why is that the surface was hard to search: 21 verbs, most carrying several
unnamed modes. `harness/VERBS.md` is the answer to "is there already a verb for
this", and it is one file to scan.


## Lint and types

`ruff` gates; `ty` does not. Both are dev dependencies and both are configured in
`pyproject.toml`, where the reasoning lives beside the settings.

Ruff's **rule set is pinned, never inherited** — its default selection is documented
as `E4,E7,E9,F` and is not; 0.16.1 also turns on flake8-bandit, implicit-str-concat
and much of RUF, reporting 161 findings here against the pinned set's zero — most of
them things this codebase does on purpose. A gate whose
meaning changes when a dev dependency is upgraded is one nobody can act on, the same
argument that makes `zones score` demand `--model` rather than read whichever `.lst`
files are lying around.

What it earned on the first run, which is the case for keeping it: `B905` found
`restore`'s post-write verification comparing source against written page with a bare
`zip`, so a write that **dropped a line** would have been checked over the common
prefix and reported clean — the repo's cardinal failure inside the function meant to
catch it. And `F821` caught two undefined names introduced while fixing other ruff
findings in the same sitting.

`RUF001`–`003` are off by name and `test_lint.py` asserts they stay off. They flag
characters resembling ASCII, which here describes the inventory: `ˊ` U+02CA, `ɪ`
U+026A, `ᵋ` U+1D4B. 152 hits, all on glyphs the project exists to transcribe. The
scoped detector in `normalize.py`/`validate.py` is the real one, and burying it under
an unscoped duplicate is the noise-over-signal failure CLAUDE.md opens with.

`ty check harness/` reports 71 diagnostics, down from 91 after one pass. The best
thing it found is not a type error at all: **`numpy` and `pillow` were imported
directly at twenty-odd sites and declared as dependencies nowhere**, reaching the
harness only through kraken — so a kraken release that dropped either would have
broken it with an ImportError naming neither this project nor the reason. It also
found `@prev` on the first scan of a part reporting `must name None`, a parameter
rebound to a type its annotation forbade, and the legacy `Image.LANCZOS` aliases.

What remains is mostly not about this code: `lxml` ships no stubs (22), and the
rest is `dict[str, str | int]` records whose values ty cannot narrow (`-r["n"]`
where `n` is always an int) plus tests subscripting an `X | None` return. Fixing
those means TypedDicts through the record-passing layer — a design change, not a
lint fix. `lxml-stubs` was tried and removed: it trades 22 low-information warnings
for ~30 `_Element | None` complaints, every sampled one already guarded in a way ty
cannot see.

So it stays a hand tool. Gating would mean permanent known-false failures or a
suppression list long enough to hide a real finding. Revisit at `ty` 1.0.
