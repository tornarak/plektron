# `harness` — every verb, every action

The complete surface. `harness/tests/test_cli_surface.py` holds this file and
the argparse tree together: an action or a flag in one and not the other fails
the suite, in both directions. That gate exists because for most of this
project's life nothing pinned the CLI at all — no test touched it — so the
surface drifted silently into 21 top-level verbs whose flags formed subcommands
nobody had named.

Read `--help` for the reasoning behind a flag; read this for what an action
touches and what its exit code means.

## Conventions

**Two tiers.** A *group* names what the command touches; an *action* names what
it does to it. Every action that names a page takes a `PP-NNN` ref — part, and
scan index within that part — and rejects a bare integer, because the printed
folio is not derivable from the scan index.

**Report by default; `--commit` writes.** It is the only write-enable, and it
gates exactly the authored stores: `gt/`, `tei/`, `models/`, and the split and
exemption sidecars. Derived output writes on invocation — crops, sheets, zoom,
blots, `mz/` predictions, the `zones/` view, `review.html`, the assemble scratch
— because there the write *is* the action and the same command rebuilds it.
`proposal.json` is a working file of a live pass, kept with a `.prev` and a
journal, and its editors write directly. The two interactive editors (`zones
edit`, `ocr review --serve`) save without `--commit` too: the save click in the
browser is the human act the flag exists to demand, and a flag typed before the
page was ever seen would attest nothing.

**Exit codes.** `0` clean · `1` a documented gate failed · `2` usage error or a
caught exception. Measurement never gates: `zones check --store mz`, `zones
score`, `zones diff`, `zones paragraphs`, and everything under `find` and
`lexicon` always exit 0.

**One meaning per flag name.** `--from DIR` is a source ALTO directory and
appears only in `ocr`. `--store gt|mz` is a closed set of two and appears only
in `zones` — closed *because* it gates, and the `zones/` view is deliberately
not offered, since checking through it would blend ratified and unratified pages
under one exit code. `--force` overwrites existing output. `--out` redirects a
write. `--commit` writes. An action name reused across groups means the same
kind of act: `ocr blot` and `zones blot` both paint a page's raster, and the
group carries which recipe.

**`--json` swaps the serializer, not the payload** — except on `tei validate`
and `tei header`, where it swaps a rendered human report for the structured
verdict. Both are marked below. Output is otherwise TOON; several actions print
two tables rather than one, because TOON collapses a uniform record list and
degrades on a ragged key set, so two key sets must be two tables.

**Argument validation is argparse's.** Mutually exclusive modes are declared,
not resolved by precedence; conditionally-required flags are `required=True`;
constrained values carry `choices=` or a validator. A flag whose scope is
narrower than its action says so in its entry here — `zones check --ink` is a
sweep flag, `--lines` a single-page one.

---

## tei

The TEI store, its structural ids, and the seam state folded out of the
committed files. There is no `boundaries.json`: the files are the record.

### tei context REF
**Does** the whole per-page input contract for the collation pass.
**Reads** `tei/`, `ocr/`, `zones/`, `gt/fig/`, `data/*.json`, `data/readings.md`.
**Writes** —
**Exit** always 0.
**Note** `running_title` is the page's own statement of what page it is — `{text, folio, folio_from, bracketed, lines}` — and it is the **second witness** to `expected_folio`, which is a prediction from the preceding transcribed page and knows nothing about this one. The two disagreeing is the signal. The folio is looked for in the head line, then in a bracketed number at the foot of a chapter opening (`QuireMarksZone`), then in the old vocabulary's `NumberingZone`; `folio_from` says which answered. Nothing is repaired: a number that does not parse cleanly leaves `folio` null and stays in `text`, on the same "null means go and look" contract `expected_folio` keeps.
**Note** the three zones that can carry a folio (`context.APPARATUS_ZONES`) are dropped from **both** `catmus_draft` and `ocr_lines` — they leave the draft and arrive as `running_title` instead, so the information is restructured rather than discarded. Out of `ocr_lines` for a sharper reason than the draft's: that list is the set of `@facs` pointer targets, and a running head, a folio or a signature line is never in the TEI body, so citing one would be a mistake by construction. A **caption** line is dropped from the draft only, since it stays citable.
```
--root --json
```

### tei validate REF
**Does** the gate on one page's TEI — output contract, `@facs` resolution, a
`@resp` rank on every Tier-1 span.
**Reads** `tei/`, plus everything `context` reads.
**Writes** —
**Exit** 1 on FAIL.
**Note** `--json` swaps the rendered report for `{ok, errors, warnings, worklist, metrics}`.
```
--ratified  expect '#ed' instead of '#llm'; a remaining '#llm' becomes a worklist line [off]
--root --json
```

### tei state REF
**Does** one page's seam record — predicted folio, what it rests on, headings believed open.
**Reads** committed `tei/`.
**Writes** —
**Exit** always 0.
```
--root --json
```

### tei ids REF
**Does** checks structural ids against `{kind}-{PP-NNN}-{ordinal}`.
**Reads** `tei/` (the page and its neighbours).
**Writes** `tei/` — the page and any neighbour whose `@prev`/`@next` needs repair, under `--commit`.
**Exit** always 0.
```
--commit  write the canonical ids and neighbours' pointers [off — reports what would change]
--root --json
```

### tei pair REF
**Does** links each `<gloss>` to its `<term>` where containment decides; reports and writes nothing where it does not.
**Reads** `tei/`.
**Writes** `tei/` under `--commit`.
**Exit** always 0.
```
--commit  write the gloss->term links [off]
--root --json
```

### tei seam REF
**Does** records whether an element runs across the gap *before* this page, writing `@part` on both sides.
**Reads** `tei/` — this page and its predecessor.
**Writes** `tei/` — two files, under `--commit`.
**Exit** always 0; exit 2 if the predecessor is not collated.
```
--continues  an element carries across: this page opens mid-element   } required,
--fresh      clean break; clears the claim on both sides              } exclusive
--commit     write both files [off]
--root --json
```

### tei ledger
**Does** the seam table across every scan — folio, heading fold, boundary state.
**Reads** committed `tei/`.
**Writes** —
**Exit** always 0.
```
--part N        restrict to one part [all]
--untranscribed refs with no committed TEI: bare lines, or a JSON array under --json [off]
--root --json
```

### tei header
**Does** the gate on `tei/corpus-header.xml` — that the ranks it declares are exactly the ones `tei validate` enforces.
**Reads** `tei/corpus-header.xml`.
**Writes** —
**Exit** 1 on FAIL.
**Note** `--json` swaps the rendered report for the structured verdict.
```
--root --json
```

---

## ocr

The ALTO stores and the correction loop. Reads resolve through `ocr/`, the read
view over every OCR store. Exactly two actions write `gt/ocr/` — `restore`
(text into lines that exist) and `adopt-gap` (geometry, never text) — and both
require `--commit`.

### ocr pages
**Does** every ref with OCR present. Sparse by construction.
**Reads** `ocr/`.
**Writes** —
**Exit** always 0.
```
--root --json
```

### ocr lines REF
**Does** per-line id, geometry and text, in reading order, empties kept. `index` is an identity, not a position.
**Reads** the `--from` store.
**Writes** —
**Exit** always 0.
```
--from DIR  ALTO directory [ocr]
--full      include baseline and polygon points [off]
--root --json
```

### ocr gaps REF
**Does** bands of ink no TextLine covers — the dropped-line detector. A band is a place to look, not a verdict.
**Reads** the `--from` store, `scans/`, `gt/fig/`.
**Writes** —
**Exit** always 0.
```
--from DIR  ALTO directory [ocr]
--root --json
```

### ocr adopt-gap REF VPOS[,VPOS...]
**Does** materializes measured `gaps` bands as empty TextLines so a dropped line can be keyed. Geometry only, never CONTENT. Refuses an unmeasured vpos and a band overlapping an existing line.
**Reads** the `--from` store, `scans/`.
**Writes** `gt/ocr/` under `--commit`, resolved explicitly and never through the view.
**Exit** always 0; exit 2 on an unmeasured vpos or an overlap.
```
--from DIR  ALTO directory [ocr]
--commit    actually write gt/ocr/ [off — reports the lines it would create]
--root --json
```

### ocr crops REF
**Does** one PNG per line.
**Reads** the `--from` store, `scans/`.
**Writes** `review/PP-NNN/crops/` (derived), or `--out`.
**Exit** always 0.
```
--from DIR  ALTO directory [ocr]
--margins   widen to the PrintSpace margins [off]
--out PATH  write elsewhere; also suppresses the page.png link [review/PP-NNN/crops]
--root --json
```

### ocr sheets REF
**Does** labelled contact sheets, index in the margin, nothing downscaled. Emits the sheet/lines map, not the line table.
**Reads** the `--from` store, `scans/`.
**Writes** `review/PP-NNN/sheets/` (derived), or `--out`.
**Exit** always 0.
```
--from DIR    ALTO directory [ocr]
--per-sheet N lines per sheet, upper bound only [40]
--height N    max sheet height in px [2000]
--margins     widen to the PrintSpace margins [off]
--out PATH    write elsewhere [review/PP-NNN/sheets]
--root --json
```

### ocr zoom REF
**Does** magnified lines — overlapping strips at an integer scale, packed into as few sheets as the height budget allows.
**Reads** the `--from` store, `scans/`.
**Writes** `review/PP-NNN/zoom/` (derived), or `--out`.
**Exit** always 0.
```
--from DIR    ALTO directory [ocr]
--only SPEC   line indices, e.g. 7,20,22-26 [every line]
--zoom N      display px per source px, as delivered [2]
--window N    source px per strip [derived from --zoom; overriding upward breaks the scale]
--client-w N  px the reading client shows per image [1450]
--overlap N   px shared by consecutive strips [60]
--height N    max sheet height in px [1600]
--margins     widen to the PrintSpace margins [off]
--smooth      Lanczos instead of nearest-neighbour [off]
--out PATH    write elsewhere [review/PP-NNN/zoom]
--root --json
```

### ocr blot REF
**Does** the page with every line box and figure zone painted out, so what remains is uncovered by construction. The visual counterpart to `gaps`. See `zones blot` for the other recipe.
**Reads** the `--from` store, `scans/`, `gt/fig/`.
**Writes** `scans-blotted/` (derived), or `--out`.
**Exit** always 0.
```
--from DIR  ALTO directory [ocr]
--out PATH  output directory [scans-blotted/ — corpus-level, unlike the other image actions]
--root --json
```

### ocr review REF
**Does** adjudicate a reading proposal in the browser (`--serve`); bare, a span-level diff against a second witness.
**Reads** the `--from` store, `review/PP-NNN/proposal.json`, `scans/`.
**Writes** `review/PP-NNN/decision.json` under `--serve`; `review/PP-NNN/review.html` under `--html`. Bare mode writes nothing.
**Exit** 1 if the bare diff's `--from` resolves to the ground truth the proposal produced — a comparison whose two witnesses are one file refuses rather than reporting a clean 40/40.
```
--serve   serve on 127.0.0.1, accept saves  }
--html    write review.html                 } mutually exclusive
--spans   bare diff: every span, ungrouped  }
--port N  port for --serve [8731]
--from DIR  ALTO directory; for the bare diff this must name a genuine second witness [ocr]
--root --json
```

### ocr restore REF
**Does** writes adjudicated decisions into `gt/ocr/`, keeping the source geometry. Reports `mode=restoration` or `mode=revision`.
**Reads** `review/PP-NNN/decision.json`, the `--from` store.
**Writes** `gt/ocr/` under `--commit`.
**Exit** always 0 — `geometry_drift` and `text_mismatch` are reported, not gated.
```
--from DIR  ALTO providing the line geometry [ocr]
--force     overwrite a target that already holds text; every page does, so a revision needs it [off]
--commit    actually write gt/ocr/ [off — previews the report]
--root --json
```

### ocr clean REF
**Does** removes a page's derived working files, leaving `proposal.json` and `decision.json` and the `page.png` link.
**Reads** `review/PP-NNN/`.
**Writes** deletes `crops/`, `sheets/`, `zoom/`, `review.html`.
**Exit** always 0.
```
--root --json
```

### ocr predict [REF]
**Does** zones to text in one pass — baseline segmentation, then recognition, structured by the zones the `zones/` view supplies. `blla`'s own regions are discarded and the seven declared zone types replace them, so a line arrives knowing whether it sits in a running title, a paragraph, a footnote or a signature line. Bare, it sweeps every page with zones and is resumable.
**Reads** `scans-fig-blotted/`, `zones/`, the two models, the split marks. A page with no blot is refused.
**Writes** `mz/ocr/` (derived), and relinks that page in `ocr/`. **Never `gt/ocr/`.** One `<String CONTENT>` per `TextLine`, the shape `gt/ocr/` has — the two stores sit under one view and a consumer reads either without asking which.
**Exit** always 0 — a skipped page is reported, not a failure.
**Note** the input is the blotted raster, as `zones predict`'s is, so artwork raises no baselines. Nothing is lost to it: the blot fills the *declared* figure box and not a pixel more — the pad was rejected precisely because body text sits hard against an inset figure on pages like `1-283` — so the type survives and only the pictures go. Captions go too and should: they live in `data/readings.md`. A line whose baseline still falls in no zone is **kept, assigned to no region, and counted as `lines_outside_zones`** rather than dropped, because a hole in a page is invisible and junk is not.
**Note** the zone label reaches the ALTO as `OtherTag/@LABEL` via `TAGREFS`, and `harness ocr lines` surfaces it as `zone`. That is what lets `tei context` drop the running head and the signature line from the collation draft while the store keeps every line the page sets — including the folio, which shares the running-title zone.
**Note** stock CATMuS reads ~91% of the ASCII and **0% of the transcription inventory**. This store is a witness to line geometry and to English, and to nothing else.
```
--force          re-run over pages already in mz/ocr/ [off] — the file records both
                 models' sha256, the store's only witness to what produced it
--itinerary LST  recognize over a work-list [every page with zones]
--seg-model PATH baseline segmentation model [models/blla.mlmodel]
--rec-model PATH recognition model [models/catmus-print-fondue-large.mlmodel]
--device DEV     torch device [auto]
--root --json
```

### ocr link
**Does** rebuilds `ocr/`, the read view over `gt/ocr/` and `mz/ocr/`, the human file winning wherever it exists. `zones link`'s twin — the same shape over the same three-store layout.
**Reads** `gt/ocr/`, `mz/ocr/`.
**Writes** `ocr/` (derived). Relative links; a link whose target has gone is removed and counted rather than left to dangle.
**Exit** always 0.
**Note** `from_gt`/`from_mz` is the number worth reading: how much of the corpus is still only the machines' word.
```
--root --json
```

---

## proposal

`review/PP-NNN/proposal.json`. The four editors exist so that inspecting or
patching a proposal never needs ad-hoc Python: a hand-typed `Edit` can silently
fail to match this file's own NFD form. They write without `--commit` — a
proposal is a working file of a live pass, not an authored store.

### proposal check REF
**Does** cross-checks `resolved` against the codepoints `text` actually contains; flags a straight apostrophe and a dot-prone bare suffix.
**Reads** `review/PP-NNN/proposal.json`.
**Writes** —
**Exit** 1 on any mismatch.
```
--path FILE  proposal file [review/PP-NNN/proposal.json]
--root --json
```

### proposal fix REF
**Does** applies the one unambiguous correction — a single mark `resolved` names that `text` lacks, swapped for the single mark `text` has that `resolved` lacks.
**Reads** the proposal.
**Writes** the proposal, in place.
**Exit** always 0.
```
--path FILE  proposal file [review/PP-NNN/proposal.json]
--root --json
```

### proposal codepoints REF LINE
**Does** names every non-ASCII character in one line's field.
**Reads** the proposal.
**Writes** —
**Exit** always 0.
```
--field {text,resolved,note}  which field [text]
--path FILE                   proposal file [review/PP-NNN/proposal.json]
--root --json
```

### proposal set REF LINE
**Does** sets one line's field. NFD-normalized on write.
**Reads** the proposal, and stdin when `--value` is absent.
**Writes** the proposal, in place.
**Exit** always 0.
```
--field {text,resolved,note}  which field [text]
--value TEXT                  the replacement; omit to read stdin [stdin]
--path FILE                   proposal file [review/PP-NNN/proposal.json]
--root --json
```

### proposal replace REF LINE
**Does** replaces occurrences of `--old` with `--new` in one line's field — the surgical alternative to `set`, which retypes the whole field.
**Reads** the proposal.
**Writes** the proposal, in place.
**Exit** always 0.
```
--old TEXT   text to find [required]
--new TEXT   text to substitute [required]
--field {text,resolved,note}  which field [text]
--which SPEC all | first | last | an occurrence number (3) | an inclusive range (2:4), 1-based [all]
--path FILE  proposal file [review/PP-NNN/proposal.json]
--root --json
```

---

## zones

Three stores — `gt/zones/` (human, tracked), `mz/zones/` (machine, derived),
`zones/` (the view, gt winning) — and the segmenter trained on the first.
`save_zones` takes no store argument at all, so writes cannot name anywhere but
`gt/zones/`. The only route from `mz/` to `gt/` is a human in the editor.

The sidecars are `gt/`-only and take no store: the three split lists,
`_rule_exempt.json`, `_ink_exempt.json`, `_ink_cache.json`. They record
judgements about *pages*, and there is no such thing as the machine store's
opinion of which pages are held out.

### zones check [REF]
**Does** the gate. With a ref, that page in full; bare, a sweep of every keyed page.
**Reads** the `--store` store, `data/zones_config.json`, the `gt/` sidecars, and `scans/` when ink runs.
**Writes** `gt/zones/_ink_cache.json` (derived) when it reads a raster.
**Exit** 1 if errors and `--store gt`; **always 0 under `--store mz`**, which is measurement.
```
--store {gt,mz}  which store [gt]
--itinerary LST  scope the sweep to a work-list [whole store]
--ink            SWEEP ONLY: read every raster for ink no zone accounts for [off; always on for a single page]
--lines          SINGLE PAGE ONLY: every zone's lines of type [off; costs a second raster decode]
--root --json
```

### zones edit [REF]
**Does** the segmentation editor on 127.0.0.1, arrow keys walking the corpus. `/` and `?` cycle the store shown; a machine page opens as an unsaved proposal.
**Reads** all three stores, `data/zones_config.json`, `scans/`.
**Writes** `gt/zones/` on save — no `--commit`, the save click is the human act.
**Exit** 2 if neither a ref nor an itinerary supplies a start page. This is the one argument check argparse cannot express.
```
--itinerary LST  walk this work-list; omit REF to resume at its first unkeyed page
--port N         port [8732; ocr review --serve holds 8731]
--root --json
```

### zones predict [REF]
**Does** runs the trained segmenter into `mz/zones/`. Input is always the blotted raster, since that is what the model was trained on.
**Reads** `models/bogoras-seg/`, `scans-fig-blotted/`, the split marks.
**Writes** `mz/zones/` (derived) — never `gt/`.
**Exit** 1 if any swept page lacked a blot. A single ref exits 0.
**Note** an exempt mark does not stop a named ref — naming a page is the request — but an existing prediction does, unless `--force`: the mz file's sha256 is the store's only witness to which model wrote it.
```
--force          re-run over pages that already have a prediction [off]
--itinerary LST  predict over a work-list [every page with a blot, minus exempt]
--model PATH     the segmentation model [models/bogoras-seg/zones-seg.safetensors]
--decode {raw,dp} blob vectorisation, or the segmental DP over the page [raw]
--device DEV     torch device [auto]
--root --json
```

### zones score
**Does** compares predictions against `gt/zones/` — recall and precision per split, never blended, plus the confusion matrix and a held-out permutation test. Prints two tables, and a stderr warning when the permutation says relabelling rather than a weak model.
**Reads** `gt/zones/`, `mz/zones/` or `--model`, the frozen split lists.
**Writes** —
**Exit** always 0 — measurement. Exit 2 if the frozen split lists are gone: without them the training pages cannot be told from the rest, and a comparison whose witnesses may be one witness must refuse.
```
--model PATH     segment this checkpoint in memory instead of reading mz/zones/ [read mz/]
--decode {raw,dp} [raw]
--device DEV     torch device [auto]
--root --json
```

### zones assemble
**Does** lays out `train/bogoras-seg/` from the split marks and reports the ketos invocation. Runs nothing.
**Reads** `gt/zones/`, `scans-fig-blotted/`, the split lists.
**Writes** `train/bogoras-seg/` — pure scratch, clobbered freely, because the split a model trained on travels in that model's own manifest.
**Exit** 1 if any listed page has no blotted raster.
```
--scratch  train from random init: no -i, kraken's default spec — the one configuration
           in which the class-map permutation cannot arise [off]
--root --json
```

### zones install CHECKPOINT
**Does** installs a trained checkpoint into `models/bogoras-seg/` with a manifest. Scores it in memory first and **refuses a permuted class map**.
**Reads** the checkpoint, `gt/zones/`, the split lists.
**Writes** `models/bogoras-seg/` under `--commit`.
**Exit** always 0; refuses a permuted map with an error.
```
--name NAME  installed model name; the accuracy stays out of it [zones-seg]
--device DEV torch device [auto]
--commit     copy the checkpoint and its split [off — previews]
--root --json
```

### zones remap
**Does** puts the learned names back on the model's output channels, when `score` shows a consistent relabelling rather than a weak model. Derives the map on the training pages and refuses unless it is 1-1 and holds out. Prints two tables.
**Reads** the model, `gt/zones/`.
**Writes** the model's class map under `--commit`, keeping the original as `.bak`.
**Exit** always 0.
```
--model PATH  [models/bogoras-seg/zones-seg.safetensors]
--commit      rewrite the class map [off — previews]
--root --json
```

### zones remark-eval FRACTION
**Does** moves a fraction of train into eval — stratified per part, independent pages first, spread rather than taken off the front. Additive: a page a human already marked is never touched.
**Reads** `gt/zones/`, the split lists.
**Writes** the split lists under `--commit`.
**Exit** always 0.
```
--commit  write the split marks [off — reports]
--root --json
```

### zones delete REF
**Does** un-keys a page — removes its file and every mark that referred to it. The one thing the store could not express, `save_zones` refusing an empty save.
**Reads** `gt/zones/` and its sidecars.
**Writes** `gt/zones/` under `--commit`, keeping `.prev` and journalling the act.
**Exit** always 0.
```
--commit  actually remove [off — previews]
--root --json
```

### zones diff [REF]
**Does** what differs between the two stores, paired by vertical overlap: `only_in_gt`, `only_in_mz`, `label`, `edge`. Prints a summary then the rows.
**Reads** both stores, `data/zones_config.json`.
**Writes** —
**Exit** always 0 — measurement.
```
--root --json
```

### zones paragraphs [REF]
**Does** audits the paragraph-boundary rule both ways. `false_negative` is a recall figure; `false_positive` is a **worklist, not a precision figure**, since gt cannot arbitrate a rule that corrects it.
**Reads** `gt/zones/`, `scans-fig-blotted/`, `data/zones_config.json`.
**Writes** —
**Exit** always 0 — measurement.
```
--itinerary LST  scope to a work-list [whole corpus]
--root --json
```

### zones link
**Does** rebuilds `zones/`, the read view over both stores, the human file winning. Reports the split, which is how much of the corpus is still the machine's word.
**Reads** both stores.
**Writes** `zones/` (derived) — relative symlinks; stale ones are removed and counted.
**Exit** always 0.
```
--root --json
```

### zones blot [REF]
**Does** the figure-blotted training raster — `gt/fig/` zones painted **white**, the declared box and not a pixel more. Distinct from `ocr blot`, which paints in conspicuous colours for a human; this one has to look like blank paper.
**Reads** `scans/`, `gt/fig/`.
**Writes** `scans-fig-blotted/` (derived).
**Exit** always 0.
```
--root --json
```

---

## lexicon

Frequency reports over the native corpus in restored `gt/ocr/`, plus the gloss
dictionary, which reads committed TEI instead. All report-only, all exit 0.

### lexicon misses
**Does** frequency-ranked `lexicon_miss` tokens, for bulk approval into `data/lexicon_extra.txt` — which suppresses `lexicon_miss` and nothing else.
**Reads** `ocr/`, `data/lexicon_extra.txt`.
**Writes** — **Exit** 0.
```
--root --json
```

### lexicon native
**Does** the most frequent native (Tier-1) word forms, for spotting a likely misspelling by comparison rather than by dictionary.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json
```

### lexicon marks
**Does** bare-vs-marked frequency per base letter — is a bare `g` or a dotted `g̣` the likelier reading, prior to the raster.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json
```

### lexicon suffixes
**Does** weighted suffix frequency (length 2–8), marks stripped before counting.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json
```

### lexicon digraphs
**Does** weighted digraph/trigraph frequency, marks and the corpus's own top suffixes stripped first.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json
```

### lexicon glosses
**Does** the term↔gloss dictionary from committed TEI. Pairs come from `@target`, never from containment, so terms nobody linked are a count rather than a guess. `scope` is the frame the gloss list supplies once, resolved back through `@prev` across a seam.
**Reads** committed `tei/`. **Writes** — **Exit** 0.
```
--root --json
```

---

## find

Apparatus lookups. Every one returns candidates a human then reads; none
resolves anything, and no hit is a legitimate outcome.

### find toc QUERY
**Does** ToC entries whose title matches a heading read off the page (word-set match).
**Reads** `data/toc.json`. **Writes** — **Exit** 0.
```
--folio N  sort matches near this folio first [unsorted]
--root --json
```

### find folio N
**Does** ToC entries near a *known* folio — for once the printed folio has been read, not a substitute for `toc_window`'s prediction.
**Reads** `data/toc.json`. **Writes** — **Exit** 0.
```
--span N  folios either side [4]
--root --json
```

### find authority [QUERY]
**Does** works matching a citation read in the body — siglum, bare name in prose, title, or a string off the printed entry. Every match returned and ranked by which field caught it: 51 sigla share 34 names, so a single answer would be manufactured. A footnote form (`Dall, I, p. 375.`) goes in whole; the lifted volume is echoed on stderr, because a silently rewritten query is an unexplainable miss.
**Reads** `data/authorities.json`. **Writes** — **Exit** 0.
```
--volume V    volume the citation names (II or 2); excludes on contradiction, not absence
--sigla       the resolution table instead: one row per cited_as, so collisions show
--key KEY     one record in full, printed blocks included
--unlocated   only works with neither doi nor url — the worklist
--root --json
```

---

## corpus

Whole-corpus gates. An action lands here only if it gates the corpus as a whole
rather than belonging to one store.

### corpus normalize
**Does** NFD conformance, §2.9 spacing, and the lookalike census across every store. Bare, it prints the census **and** what a `--commit` would rewrite — two tables, because they are two code paths and a preview agreeing with itself is no preview.
**Reads** every corpus store, deduped by real path (`ocr/` and `gt/ocr/` are two names over one inode).
**Writes** corpus files in place under `--commit` — raw source, never a parsed tree, so element and attribute order cannot move.
**Exit** 1 on NFD drift, an unlicensed mark, or spacing drift. The lookalike census does **not** gate: it is a worklist needing a human ruling on what the page prints. `--commit` always exits 0.
```
--commit     write the fixes; required to touch any file, scoped or not [off]
--path PATH  scope to a file or directory, repeatable [whole corpus]
--root --json
```

### corpus figures
**Does** reconciles `gt/fig/` zone geometry against `data/readings.md` captions, in both directions.
**Reads** `gt/fig/`, `data/readings.md`, `data/loi.json`.
**Writes** —
**Exit** 1 if `missing` or `orphan` is non-empty. The counts alone never decide it: 250 pages was once the expected total *and* wrong in two compensating directions at once.
```
--root --json
```
