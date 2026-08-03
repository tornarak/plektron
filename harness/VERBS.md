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

**Refs are plural.** `REF [REF ...]` everywhere, so a batch is one invocation
rather than a shell loop. Four actions are singular and say why in their entry:
`ocr adopt-gap` (its `VPOS` is measured on that page's raster), `tei context`
(the payload is one page's collation prompt), `proposal set` and `proposal
replace` (their flags name one entry of one proposal). A flag that names
something only one page has — `ocr zoom --only`, `--out`, `zones check --lines`,
`proposal --path` — refuses a second ref rather than picking one.

**One ref emits what it always did; several pool.** The records gain `ref` as
their first field and land in one table, which is the shape `emit.py` argues
for. An action emitting two tables emits two pooled tables; a list-valued field
becomes its own ref-keyed table, since a nested list degrades the whole outer
table to the verbose form. `tei validate` is the exception and prints one
rendered report per ref, `# REF` separated, because prose does not pool. The
aggregating actions — `ocr corrections`, `proposal marks`, `zones diff`, `zones
paragraphs`, `corpus normalize` — take refs as a *scope* and return one report
however many were named. **Exit is the worst across refs**, and every ref is
parsed before any work is done, so a typo in the fifth cannot leave four pages
written.

**A corpus run is `--all`, never an omission.** Where an action has a
corpus-wide form, the flag says so and its help names *what it enumerates* —
"every page" is four different sets here. Naming nothing is a usage error.
`--all`, refs and `--itinerary` are three ways of naming a work-list and exactly
one may be used. Six actions are plural but deliberately have no `--all`, each
saying why: `ocr crops`, `ocr sheets`, `ocr zoom`, `zones delete`, `tei state`,
`tei seam`. **`--all` does not clobber prior work without `--force`** — `ocr
predict` and `zones predict` skip what a store already holds, `ocr restore`
skips a page whose ground truth is newer than its decision, `ocr blot` a page
whose blot is newer than its ALTO. `zones blot` deliberately has no such test:
freshness there is *uncheckable*, so an mtime comparison would report success
over the one failure it exists to catch.

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

**One meaning per flag name.** `--store gt|mz` names one of a group's two real
stores. A closed set of two, **never a free path and never the read view** — the
view is not a store, and naming it would blend a ratified page and an unratified
one under one exit code, which is the whole reason the set is closed. Omitting
the flag is how a caller asks for the view, i.e. "whatever is current for this
page". It appears in `zones` and in `ocr`; `ocr review` is the only action with a
store *default* (`mz`), because its bare diff needs an independent witness and
the view stops being one as soon as the page has ground truth. `--force`
overwrites existing output. `--out` redirects a
write. `--commit` writes. An action name reused across groups means the same
kind of act: `ocr blot` and `zones blot` both paint a page's raster, and the
group carries which recipe.

**Three output modes, and the default is whether stdout is a terminal.** Down a
pipe it is **TOON** — the compact tabular encoding, and what every example in
this file and in the skills shows. At a **terminal** it is an aligned table,
with columns of numbers right-justified, section rules between a verb's several
tables, and nothing ever truncated: the console is built at the table's own
natural width and output too wide for the screen goes to the pager rather than
losing a character. **`--toon` forces TOON at a terminal**, which is how a human
reproduces exactly what a skill's model saw. `--json` gives indented JSON.

`--json` and `--toon` are mutually exclusive, and both are on every action
alongside `--root` and `--no-pager`; the four share the trailing
`--root --json --toon --no-pager` line of each fence below rather than being
restated per entry.

**Long sweeps draw a progress bar on stderr.** The pooled raster sweeps (`zones
check --ink`, `zones paragraphs`, `zones blot`, `ocr gaps`, `ocr blot`) and the
slow serial ones (`ocr predict`, `zones predict`, `ocr crops`/`sheets`/`zoom`)
report the page they are on, how many are done and how long it has taken. It
appears only when stderr is a terminal and only once the work has run for about
half a second, so a short run stays silent and a redirected one is byte-identical
to a run with no bar at all. stdout is untouched: `harness … > file` holds exactly
the payload.

**The pager is `$PAGER`, default `less -SRFX`, and only in table mode.** It is
always started there and `-F` decides whether it shows — content that already
fits one screen is printed and the pager exits, so there is no length threshold
to get wrong. `-S` chops rather than wraps, which is what makes a table wider
than the screen readable: columns stay aligned and you scroll sideways.
`--no-pager` prints straight to the terminal. A pipe never pages, so nothing
downstream is affected. **`zones edit` and `ocr review` never page**: they print
a URL and block on a server, and a URL inside a pager on a command that does not
return is a URL nobody reads.

**`--json` swaps the serializer, not the payload** — except on `tei validate`
and `tei header`, where it swaps a rendered human report for the structured
verdict. Both are marked below. Several actions print two tables rather than
one, because TOON collapses a uniform record list and degrades on a ragged key
set, so two key sets must be two tables.

**`--json` is always exactly one document.** Where an action prints one table it
is that table, bare. Where it prints several they become one object keyed by
section — the first taking the action's own name, the rest their own:
`zones check REF --json` is `{"check": {…}, "zones": [...]}`, `corpus normalize`
is `{"normalize": {…}, "would_convert": {…}}`, `tei validate` with several refs
keys each report on its ref. It used to emit N documents on one stream with `#`
comment lines between them, which `json.load` rejects — 15 of 58 measured
invocations — on the one flag whose purpose is being parseable. TOON output is
unchanged either way, including those `#` lines.

Two things to know before consuming it. **The key set follows which sections had
content**, so an action whose second table is empty this run omits its key: use
`.get()`. And the object is emitted **whatever the exit code is** — `views
check` and `tei validate` legitimately return 1 with a full payload.

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
**Note** **one of the four singular actions.** The payload is one page's collation prompt, built to be handed to one model for one page; a merged stream of them is not consumable by the thing it exists for.
```
--root --json --toon --no-pager
```

### tei validate [REF ...]
**Does** the gate on a page's TEI — output contract, `@facs` resolution, a
`@resp` rank on every Tier-1 span.
**Reads** `tei/`, plus everything `context` reads.
**Writes** —
**Exit** 1 on FAIL — the worst across refs, so one failing page fails the batch.
**Note** `--json` swaps the rendered report for `{ok, errors, warnings, worklist, metrics}`.
**Note** **the one action that does not pool.** Its payload is a rendered report and prose does not tabulate, so several refs print several reports under `# REF` lines. One ref prints exactly what it always did, with no header.
```
--all       every collated page in tei/
--ratified  expect '#ed' instead of '#llm'; a remaining '#llm' becomes a worklist line [off]
--root --json --toon --no-pager
```

### tei state REF [REF ...]
**Does** one page's seam record — predicted folio, what it rests on, headings believed open.
**Reads** committed `tei/`.
**Writes** —
**Exit** always 0.
**Note** **no `--all`** — `tei ledger` *is* the corpus form of this, and a second spelling of one report is how two answers to one question start to drift.
```
--root --json --toon --no-pager
```

### tei ids [REF ...]
**Does** checks structural ids against `{kind}-{PP-NNN}-{ordinal}`.
**Reads** `tei/` (the page and its neighbours).
**Writes** `tei/` — the page and any neighbour whose `@prev`/`@next` needs repair, under `--commit`.
**Exit** always 0.
**Note** with more than one ref and `--commit`, every page is previewed before any is written — the same up-front rule `ocr restore` keeps.
```
--all     every collated page in tei/
--commit  write the canonical ids and neighbours' pointers [off — reports what would change]
--root --json --toon --no-pager
```

### tei pair [REF ...]
**Does** links each `<gloss>` to its `<term>` where containment decides; reports and writes nothing where it does not.
**Reads** `tei/`.
**Writes** `tei/` under `--commit`.
**Exit** always 0.
```
--all     every collated page in tei/
--commit  write the gloss->term links [off]
--root --json --toon --no-pager
```

### tei seam REF [REF ...]
**Does** records whether an element runs across the gap *before* this page, writing `@part` on both sides.
**Reads** `tei/` — this page and its predecessor.
**Writes** `tei/` — two files, under `--commit`.
**Exit** always 0; exit 2 if the predecessor is not collated.
**Note** **no `--all`**: `--continues`/`--fresh` is an assertion about *this* seam, and a corpus-wide "everything continues" is not a claim anyone could mean. Several refs each get their own seam, the flag applying to each.
```
--continues  an element carries across: this page opens mid-element   } required,
--fresh      clean break; clears the claim on both sides              } exclusive
--commit     write both files [off]
--root --json --toon --no-pager
```

### tei ledger
**Does** the seam table across every scan — folio, heading fold, boundary state.
**Reads** committed `tei/`.
**Writes** —
**Exit** always 0.
```
--part N        restrict to one part [all]
--untranscribed refs with no committed TEI: bare lines, or a JSON array under --json [off]
--root --json --toon --no-pager
```

### tei header
**Does** the gate on `tei/corpus-header.xml` — that the ranks it declares are exactly the ones `tei validate` enforces.
**Reads** `tei/corpus-header.xml`.
**Writes** —
**Exit** 1 on FAIL.
**Note** `--json` swaps the rendered report for the structured verdict.
```
--root --json --toon --no-pager
```

---

## ocr

The ALTO stores and the correction loop. Reads resolve through `ocr/`, the read
view over every OCR store. Exactly two actions write `gt/ocr/` — `restore`
(text into lines that exist) and `adopt-gap` (geometry, never text) — and both
require `--commit`.

### ocr pages
**Does** every ref with OCR present — i.e. workable now.
**Reads** the `--store` store, or the view.
**Writes** —
**Exit** always 0.
**Note** through the view by default, so a page only the recognizer has read counts. That is deliberate: a machine-read page *is* workable. It was sparse by construction while `gt/ocr/` was the only store under the view and is not any more, so narrow it when the question is narrower.
**Note** `--show-store` turns the bare list into `{ref, gt, mz, view}`. `--store` still picks the rows; the flag adds the columns. **`view` is read off the farm, not derived** from `gt`/`mz` — derived it would restate the rule and could never disagree with itself, whereas `ocr/` is derived output that nothing rebuilds automatically, so a page restored into `gt/ocr/` since the last `ocr link` shows `view: mz` and says so. `""` is no live link; `?` is a link resolving outside both stores.
```
--store {gt,mz}  which store to read [omit: the ocr/ view, which resolves per page
                 to the human file where there is one]
--show-store     a row per ref — which stores hold it, which the view reaches [off]
--root --json --toon --no-pager
```

### ocr lines [REF ...]
**Does** per-line id, geometry and text, in reading order, empties kept. `index` is an identity, not a position.
**Reads** the `--store` store, or the view.
**Writes** —
**Exit** always 0.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds
--full      include baseline and polygon points [off]
--root --json --toon --no-pager
```

### ocr gaps [REF ...]
**Does** bands of ink no TextLine covers — the dropped-line detector. A band is a place to look, not a verdict.
**Reads** the `--store` store, or the view, `scans/`, `gt/fig/`.
**Writes** —
**Exit** always 0.
**Note** `--all` is the corpus dropped-line sweep, at a raster read per page. It reads through the view unless `--store` narrows it, which is `ocr pages`' rule — a machine-read page is workable, and this verb neither gates nor publishes a rate.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds
--jobs N    worker threads; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --no-pager
```

### ocr adopt-gap REF VPOS[,VPOS...]
**Does** materializes measured `gaps` bands as empty TextLines so a dropped line can be keyed. Geometry only, never CONTENT. Refuses an unmeasured vpos and a band overlapping an existing line.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `gt/ocr/` under `--commit`, resolved explicitly and never through the view.
**Exit** always 0; exit 2 on an unmeasured vpos or an overlap.
**Note** **one of the four singular actions**: `VPOS` is a band measured on *that* page's raster, so a ref list would carry a band list belonging to one of them. `test_cli_surface.py` holds the exemption by name.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--commit    actually write gt/ocr/ [off — reports the lines it would create]
--root --json --toon --no-pager
```

### ocr crops REF [REF ...]
**Does** one PNG per line.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/crops/` (derived), or `--out`.
**Exit** always 0; exit 2 for `--out` with more than one ref, since one destination cannot hold two pages' images without the second overwriting the first.
**Note** **no `--all`, deliberately.** Crops are expensive in time and disk and are written per page by a pass that is working on that page; a corpus form would be a great many bytes nobody asked for. `zones delete` and `ocr sheets` carry the same declared absence, and `test_cli_surface.py` holds all six by name.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--margins   widen to the PrintSpace margins [off]
--out PATH  write elsewhere; also suppresses the page.png link [review/PP-NNN/crops]
--root --json --toon --no-pager
```

### ocr sheets REF [REF ...]
**Does** labelled contact sheets, index in the margin, nothing downscaled. Emits the sheet/lines map, not the line table.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/sheets/` (derived), or `--out`.
**Exit** always 0; exit 2 for `--out` with more than one ref.
**Note** no `--all`, for `crops`' reason.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--per-sheet N lines per sheet, upper bound only [40]
--height N    max sheet height in px [2000]
--margins     widen to the PrintSpace margins [off]
--out PATH    write elsewhere [review/PP-NNN/sheets]
--root --json --toon --no-pager
```

### ocr zoom REF [REF ...]
**Does** magnified lines — overlapping strips at an integer scale, packed into as few sheets as the height budget allows.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/zoom/` (derived), or `--out`.
**Exit** always 0; exit 2 for `--only` or `--out` with more than one ref.
**Note** no `--all`. `--only` is the sharper of the two per-page flags: a line index is an *identity*, not a position, so the same numbers name unrelated lines on the next page.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--only SPEC   line indices, e.g. 7,20,22-26 [every line]
--zoom N      display px per source px, as delivered [2]
--window N    source px per strip [derived from --zoom; overriding upward breaks the scale]
--client-w N  px the reading client shows per image [1450]
--overlap N   px shared by consecutive strips [60]
--height N    max sheet height in px [1600]
--margins     widen to the PrintSpace margins [off]
--smooth      Lanczos instead of nearest-neighbour [off]
--out PATH    write elsewhere [review/PP-NNN/zoom]
--root --json --toon --no-pager
```

### ocr blot [REF ...]
**Does** the page with every line box and figure zone painted out, so what remains is uncovered by construction. The visual counterpart to `gaps`. See `zones blot` for the other recipe.
**Reads** the `--store` store, or the view, `scans/`, `gt/fig/`.
**Writes** `scans/w-blotted/` (derived), or `--out`.
**Exit** always 0; exit 2 for `--out` with more than one ref.
**Note** `--all` skips a page whose blot is already newer than its ALTO, and `--force` repaints it; naming a page always repaints it, since naming it is the request. **The mtime test is honest here in a way `zones blot`'s could not be**: this paints boxes read out of the ALTO, so an ALTO newer than the blot is exactly the change that matters — where a figure ALTO corrected after a `zones blot` leaves a raster whose staleness nothing can see, which is why that verb has no such test at all.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds
--force     repaint pages whose blot is newer than their ALTO [off — only --all skips]
--out PATH  output directory [scans/w-blotted/ — corpus-level, unlike the other image actions]
--jobs N    worker threads; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --no-pager
```

### ocr review [REF ...]
**Does** adjudicate reading proposals in the browser (`--serve`); bare, a span-level diff of each against a second witness.
**Reads** the `--store` store, or the view, `review/PP-NNN/proposal.json`, `scans/`.
**Writes** `review/PP-NNN/decision.json` under `--serve`; `review/PP-NNN/review.html` under `--html`. Bare mode writes nothing.
**Exit** 1 if any ref's bare diff source resolves to the ground truth that proposal produced — a comparison whose two witnesses are one file refuses rather than reporting a clean 40/40. Checked over every ref before the first table prints, so the refusal cannot arrive after pages of reassuring output.
**Note** the **first action to take more than one ref**, for a reason the rest of the CLI has since caught up with: its cost is a human's attention rather than a process's. `--all` is the pending-adjudication queue — every page holding a proposal and no decision. The bare span diff pools across refs into two tables rather than printing a `# REF`-separated pair per ref, which is what it did while it stood alone: a pooled table parses as one document, and the separated form parsed as nothing. `--serve` runs one server over the whole batch, one page on screen at a time, reached by navigation — never several pages merged into one document, since a field belonging to a page other than the one you think you are keying is this pass's oldest failure. **Adjudicated-ness is read off the disk** (`decision.json` exists), never held in the process, so a reload, a second tab or a restart cannot contradict it; a re-run therefore resumes the batch rather than restarting it, and a page that already carried decisions shows done and stays reachable from the strip. `Done` advances to the next unadjudicated page and stops the server only on the last one. A single ref renders and behaves exactly as before — no strip, no navigation.

Each line carries a **`+ note` button** and, once asked for, a note field: the adjudicator's own record, saved into `decision.json` as `note` beside `text`. **Opt-in in both places** — a field on all 45 lines would be 45 empty boxes competing with the 45 that matter, and an empty `note` written on every line would make "which lines were remarked on" unfindable, the key existing being the only way anyone asks. Distinct from `proposal.json`'s `note`, which is the reader's account of its own work; these live in different files so a human ruling is never mistaken for a model's. A note is not an edit, so a page saved with only notes reports `0/N edited` and `restore` is a no-op on it.

The header links to the **full page scan**, new tab — the crops say what a line sets and cannot say what is around it, which is what settling a speck or a dropped line needs. Served from `/scan/<ref>`, scoped to the session's refs like `/p/`; `--html` writes a relative path to `scans/` instead, since a browser will not follow `file://` from an http origin.
```
--serve   serve on 127.0.0.1, accept saves  }
--html    write review.html per ref         } mutually exclusive
--spans   bare diff: every span, ungrouped  }
--all     every page with a proposal and no decision
--port N  port for --serve [8731]
--store {gt,mz}  which store to read [mz — the bare diff needs an independent
                 witness, and the view is not one once the page has ground truth]
--root --json --toon --no-pager
```

### ocr restore [REF ...]
**Does** writes adjudicated decisions into `gt/ocr/`, keeping the source geometry. Reports `mode=restoration` or `mode=revision`.
**Reads** `review/PP-NNN/decision.json`, the `--store` store, or the view.
**Writes** `gt/ocr/` under `--commit`, **and relinks that page in `ocr/`** — the promotion is the write plus the relink, the same pairing `ocr predict` has for what it writes into `mz/ocr/`. The `view` field reports which store the view now names, `""` on a preview.
**Exit** 0 when it runs — `geometry_drift` and `text_mismatch` are reported, not gated. It **refuses** (exit 2) in four cases, none of them a judgement to weigh: no decisions at all; **any line without one**; a line without exactly one `String`; an unlicensed mark in the adjudicated text (§2.6).

**A revision is a whole-page act, and the second refusal is why.** `decision.json` must cover every line, so there is no path that edits one word of a finished page: revising `gt/ocr/` means a `proposal.json` for the whole page, adjudicated, then `restore --force`. That is deliberate — a partial write is ground truth with invisible holes — but it means a page carrying ground truth and **no proposal** cannot enter the loop at all. `2-030` was in that state, adjudicated by the eScriptorium route before this pass existed, until it was read through in 2026-08; every page in `gt/ocr/` has a proposal now. The constraint stands whether or not anything is currently caught by it.
**Note** the view is the right default here rather than a convenience: it resolves to `gt/ocr/` for a keyed page (source is the target — a `revision`, which needs `--force`) and to `mz/ocr/` for a predicted one (source ≠ target, target absent — a `restoration`, which does not). That is the correct source in both cases without the caller choosing, and `mode` reports which ran.

**`--all` is every page holding a `decision.json`, and it asks a sharper question than `--force` does.** Every page in `gt/ocr/` holds text, so the bare guard would refuse the whole store and a sweep that refuses everything is not a sweep. So it skips a page whose ground truth is **already newer than its decision** — that page has been restored since it was adjudicated and there is nothing to write — and restores the rest, carrying `force` on the adjudicator's behalf: the timestamps establish the same intent the flag does. `--force` under `--all` means the other half, *ignore the mtime test*, which is the same "do it anyway" the flag always meant. A skipped page is named in a `skipped` table, never silently. Deliberately not keyed on the *proposal*'s mtime: a proposal is a reading, not an adjudication, and re-authoring one licenses no write.

With more than one ref and `--commit`, **every page is checked before any page is written** — a dry pass runs the whole refusal set first, so an unadjudicated line on the fourth page cannot arrive with three pages of ground truth already replaced.

Two tables describe what the human did, and they are separate because a note is not an edit. `edits[]{line,proposal,decision}` is the text that changed; `notes[]{line,note}` is every line the adjudicator remarked on, **edited or not** — the commonest note sits on a line whose text nobody touched (`2-036`'s speck, ruled "ink smudge" and left empty), so a list keyed on `edited` showed it nowhere and the ruling appeared in no report about the page. Neither table gates, and the note never reaches the ALTO: `decision.json` is its record.
```
--store {gt,mz}  which store supplies the line geometry [omit: the ocr/ view,
                 which is gt for a keyed page and mz for a predicted one]
--all       every page holding a decision.json, skipping those whose ground
            truth is already newer than it
--force     overwrite a target that already holds text; every page does, so a revision needs it [off].
            Under --all it carries the same intent one step further: ignore the mtime skip too
--commit    actually write gt/ocr/ [off — previews the report]
--root --json --toon --no-pager
```

### ocr corrections [REF ...]
**Does** aggregates the character-level `proposal.json` → `decision.json` corrections across every adjudicated page — what readers actually get wrong, ranked.
**Reads** every `review/*/` holding both files.
**Writes** —
**Exit** always 0 — measurement.
**Note** **an aggregate**: refs *scope* it and do not multiply it, so there is one report whether one page was named or forty, and `--all` is every page with both files. Its ref used to be a repeatable `--ref` flag, the one place in the CLI where naming a page was not a positional. It sits in this group rather than under `proposal` because it reads *both* files, and `review`/`restore` own the other one. `restore` computes this same diff per page (`edits`) and discards it, so the pass's own error profile was the one thing in the loop with no record.

Opcodes come from difflib over **NFD** text, so a dropped combining mark ranks as an insert of the mark itself rather than as a replacement of its whole word — which is what makes the ranking legible: 37 dropped dots-below across eight pages collapse to one row instead of scattering over 37 nothing can match. An edit of 12 characters or more on either side reports as `<Nch> -> <Mch>`, since a whole-line retype would otherwise mint a row nothing will ever match again.

**The store spans this project's own history, so an unscoped run is not an error profile.** The leading class — 117 `'`→`ˊ` — is two pages keyed before a bare apostrophe became its own unconditional error, and cannot recur in that form; `--since 2026-07-31` leaves `i`→`ɪ` as the only recurring class, four times on three pages, which is the live picture and matches what CLAUDE.md claims about the residual. A page whose `decision.json` carries no `saved_at` is **excluded under `--since` and named in `skipped_unstamped`** rather than dropped, since a missing verdict must not draw in the same column as a clean one.

**It undercounts by construction**: `proposal set`/`replace` overwrite the proposal in place, so a reader error a coordinator repaired *before* adjudication leaves no diff at all (`2-033`'s four bare `g` went that way). It measures what reached the adjudicator, never what the reader first wrote — and the earlier the loop catches a slip, the less of it appears here, which is the intended direction rather than a gap to close.
```
--all         every review/ page holding both files
--since DATE  only pages whose saved_at sorts at or after this
--min N       drop changes seen fewer than N times [1]
--root --json --toon --no-pager
```

### ocr clean [REF ...]
**Does** removes a page's derived working files, leaving `proposal.json` and `decision.json` and the `page.png` link.
**Reads** `review/PP-NNN/`.
**Writes** deletes `crops/`, `sheets/`, `zoom/`, `review.html`.
**Exit** always 0.
**Note** no `--commit`, `--all` included: it removes only derived, regenerable output, which is the same reason `crops` writes without one. The verb that deletes an *authored* file is `zones delete`, and that one has no `--all` at all.
```
--all       every review/ page
--root --json --toon --no-pager
```

### ocr predict [REF ...]
**Does** zones to text in one pass — baseline segmentation, then recognition, structured by the zones the `zones/` view supplies. `blla`'s own regions are discarded and the seven declared zone types replace them, so a line arrives knowing whether it sits in a running title, a paragraph, a footnote or a signature line. `--all` sweeps every page with zones and is resumable.
**Reads** `scans/w-figs-blotted/`, `zones/`, the two models, the split marks. A page with no blot is refused.
**Writes** `mz/ocr/` (derived), and relinks that page in `ocr/`. **Never `gt/ocr/`.** One `<String CONTENT>` per `TextLine`, the shape `gt/ocr/` has — the two stores sit under one view and a consumer reads either without asking which.
**Exit** always 0 — a skipped page is reported, not a failure.
**Note** the input is the blotted raster, as `zones predict`'s is, so artwork raises no baselines. Nothing is lost to it: the blot fills the *declared* figure box and not a pixel more — the pad was rejected precisely because body text sits hard against an inset figure on pages like `1-283` — so the type survives and only the pictures go. Captions go too and should: they live in `data/readings.md`. A line whose baseline still falls in no zone is **kept, assigned to no region, and counted as `lines_outside_zones`** rather than dropped, because a hole in a page is invisible and junk is not.
**Note** the zone label reaches the ALTO as `OtherTag/@LABEL` via `TAGREFS`, and `harness ocr lines` surfaces it as `zone`. That is what lets `tei context` drop the running head and the signature line from the collation draft while the store keeps every line the page sets — including the folio, which shares the running-title zone.
**Note** stock CATMuS reads ~91% of the ASCII and **0% of the transcription inventory**. This store is a witness to line geometry and to English, and to nothing else.
**Note** **several named refs go through the sweep, not a loop over the single-page form** — both models load once, which is most of the cost (~25 s standalone against ~17 s each in one process), and that is the whole reason to name them together. The single-page override travels with them: a named ref means *that page* even where a human ruled it exempt, so a named plate is refused loudly rather than dropped in silence by the command that named it. `--all` is the other case and there the exempt ruling holds.
```
--all            every page with zones
--force          re-run over pages already in mz/ocr/ [off] — the file records both
                 models' sha256, the store's only witness to what produced it
--itinerary LST  recognize over a work-list [every page with zones]
--seg-model PATH baseline segmentation model [models/blla.mlmodel]
--rec-model PATH recognition model [models/catmus-print-fondue-large.mlmodel]
--device DEV     torch device [auto]
--jobs N         worker **processes**; 1 keeps the single-process path [cores, capped by free VRAM]
--root --json --toon --no-pager
```

### ocr link
**Does** rebuilds `ocr/`, the read view over `gt/ocr/` and `mz/ocr/`, the human file winning wherever it exists. `zones link`'s twin — the same shape over the same three-store layout.
**Reads** `gt/ocr/`, `mz/ocr/`.
**Writes** `ocr/` (derived). Relative links; a link whose target has gone is removed and counted rather than left to dangle.
**Exit** always 0.
**Note** `from_gt`/`from_mz` is the number worth reading: how much of the corpus is still only the machines' word.
```
--root --json --toon --no-pager
```

---

## proposal

`review/PP-NNN/proposal.json`. The four editors exist so that inspecting or
patching a proposal never needs ad-hoc Python: a hand-typed `Edit` can silently
fail to match this file's own NFD form. They write without `--commit` — a
proposal is a working file of a live pass, not an authored store.

### proposal marks REF [REF ...]
**Does** asks whether a batch's character distribution is plausible, before a human opens it — three arms over the Tier-1 tokens of each page's proposal.
**Reads** `review/PP-NNN/proposal.json` (or `decision.json` under `--decisions`), `gt/ocr/` for the prior, `data/marks_config.json`.
**Writes** —
**Exit** always 0 — measurement. An outlier is a page to re-read, never a page to correct by ratio. Refuses (exit 2) only when a named ref has no source file.
**Note** takes several refs, like `ocr review`, and "batch" means only that — the refs you pass. Most pages of this book carry a handful of Tier-1 terms, so a coordinator hands it every ref of a pass at once and gets a sample worth holding against the corpus. `dispatch.md` used to prescribe eyeballing `lexicon marks` here; this is that comparison computed, and `lexicon marks` could not do it — corpus-wide only, and grouped by base letter, so it cannot express `ɪ`/`i`, which is not a mark on a base.

**The three arms are not equally strong.** `rare[]{ref,form,count,lines,position,corpus_pct,corpus_n,spec}` lists every occurrence of a form whose confusable the corpus almost never sets — bare `g` at 6.1% of Tier-1 `g`, 8 occurrences on 4 pages. Deterministic, no statistics. **One row per (ref, form) carrying a count**, because a keyer repeats a slip along a page (13 dropped dots on `2-040`, 14 on `3-004`, then a tail of 1–3): four bare `g` on a page is one finding of weight four, not four independent hits. Which contrasts can reach this arm is **derived from the prior at run time**, not declared — plain `i` at ~34% of its axis never qualifies and does not need to.

`conflict[]{fold,batch_forms,store_forms,refs,in_batch}` finds one word spelled two ways. Fold collapses every contrast axis then casefolds; a bucket whose **casefolded** spellings differ is a hit. That suppresses `äˊmmê`/`Äˊmmê` while catching `Iᵋplɪˊlɪ`/`ɪᵋplɪˊlɪ`, because `casefold("I")` is `"i"` but `casefold("ɪ")` is `"ɪ"` — U+026A has no case mapping. Scoped to folds the batch touches: the store carries 3 standing `i`/`ɪ` inconsistencies of its own (`2-030` ×2, `3-028` ×1) and re-reporting them every run would bury the batch's news. `in_batch` separates the batch disagreeing with itself from the batch disagreeing with ground truth.

`ratio[]{scope,contrast,position,types,expected_pct,prior_pct,gt_min_pct,gt_max_pct,band_n,outside}` points and never decides. **Types, not tokens** — the marks are lexical, not independent, and a per-character binomial flags 19 page-base cells over 29 already-adjudicated pages (`2-036`'s 10% `ɪ`-share is `Pehiˊttin` ×4). `outside` is a rank against the band, never a p-value.

**`scope: ALL` is the refs you passed, pooled — nothing more**, and it is emitted only when you passed more than one. Most pages of this book carry a handful of Tier-1 terms, so one page is rarely a sample worth a verdict; pooling a coordinator's returned jobs gives a body of native text large enough to hold against the ground-truth corpus. Over a single ref it would restate that ref's own row, so it is absent, and that ref's rows are shown however thin they are — a table that is silently empty says nothing and looks clean.

**Read the per-ref rows against `ALL`, and `ALL` against `prior_pct`.** They answer different questions. One job adrift while the others sit on the prior is that reader, on that page. *Every* job leaning the same way, so that `ALL` itself parts from the prior, is **systemic** — the prompt or the keying spec, not anyone's reading. That second finding is the one nothing else in the loop can see, and it is why the pooled row exists.

The band is the **per-page** spread over ground-truth pages clearing `--min-types`, and it is a fixed property of the store: it does not move with how many refs you passed. It is the right reference for a per-ref row and a conservative one for `ALL`, since a pooled share is a weighted mean of its members and varies less than any of them — `ALL` outside it is a strong signal, not a marginal one. `band_n` says how many pages it came from, which is not always many: the `g` axis clears `min_types` on 6 pages of the store. A band of fewer than two is no band, and `outside` reads `?` — as it does under `--min-types`, and never blank, since an uncomputed verdict must not draw in the same column as a computed one.

`prior_pct` is the whole prior pooled, by the same type-level rule as `expected_pct` so the two columns are in one unit. `rare`'s `corpus_pct` is deliberately *occurrence*-level: "how often does the corpus set a bare `g`" is a different question, and 6.1% is the figure `keying_spec.md` §5.1 publishes.

**`position` is why the small caps are split into two contrasts each.** Word-medially an ASCII cap is essentially never right — 2 in the store against 509 medial small caps — and `detectors.MEDIAL_CAPS` already says so with a sharper claim than a share could. Word-initially both are ordinary: 63 ASCII caps (`Alaˊyon`, `Ilhiˊnin`) against 55 small caps (`ɪnp-luˊwleñ-yiˊᵋlhɪn`, `ᴇnmɪtaˊhɪn`), and frequency is the only handle. So `smallcap-i` (lowercase) counts everywhere and `smallcap-I` (uppercase) counts word-initial only.

**The prior is leave-one-out and density-selected**, and `prior_note` says the second half in every report. Leave-one-out unconditionally: after `restore` a page's ground truth *is* the adjudicated descendant of its own proposal, so a prior containing the page under test compares a proposal against its own output — the two-witnesses-that-are-one failure in a fourth place. Density-selected: `gt/ocr/`'s pages were chosen for Tier-1 density (median 13 types, range 2–56), so it is a prior about dense pages, not a population estimate.

**A page whose reading degraded to ASCII contributes no tokens and every arm goes silent on it**, which is why `pages[]{ref,source,tokens,types}` carries one row per ref whether or not anything was found. `types: 0` beside a page whose zones promise Tier-1 content is itself the finding.
**`--all` says less than a batch does**, which is the one place in this CLI where the corpus form is the *weaker* reading. The prior is leave-one-out over `gt/ocr/`, so pooling every proposal in the repo drives the sample towards its own prior and the `ratio` arm goes quiet. It is there for the `rare` and `conflict` arms, which are deterministic and gain from breadth.
```
--all            every review/ page with a proposal
--decisions      read decision.json instead of proposal.json — the last state
                 before restore writes [off]
--min-types N    types a scope needs before ratio judges it [data/marks_config.json]
--rare-max PCT   a confusable at or below this share of its axis is rare enough
                 to list every occurrence [data/marks_config.json]
--root --json --toon --no-pager
```

### proposal check [REF ...]
**Does** cross-checks `resolved` against the codepoints `text` actually contains; flags a straight apostrophe, a dot-prone bare suffix, and — via `marks` — a rare form or a word spelled two ways against the store.
**Reads** `review/PP-NNN/proposal.json`, plus `gt/ocr/` and `data/marks_config.json` for the two corpus arms.
**Writes** —
**Exit** 1 on any mismatch, on any ref — one dirty page fails the batch, which is the contract a gate must have or a batch would launder a failure.
**Note** the corpus arms are `proposal marks`'s two **deterministic** ones, run over the single page so a reader catches its own slip before writing its report. `ratio` is deliberately not among them: one page is a poor sample and it is the arm that cannot decide, so folding it into a per-page gate would assert exactly what `marks` refuses to. A repeated form is one issue naming its other lines, not one issue per occurrence — a keyer's single habit is one fault. The prior is leave-one-out here too, so a revision is not checked against its own descendant. Where `data/marks_config.json` is absent (a fresh clone), the arms are skipped and the rest still runs.

**Overlap with the suffix check is wanted, not deduplicated**: a bare `-gɪn` yields both a `bare suffix` and a `rare form` issue on the same line. They reach one defect from different directions — a measured shape and a corpus share — and a second witness this cheap is what the governing principle asks for.

**Every issue is one record shape — `line, issue, token, context, detail` — whatever detector raised it** (`proposal_check.ISSUE_FIELDS`, and the `issue()` constructor is the only way one is built). `line` is `-` for a page-level finding; `token` is the flagged string where there is one; `context` is where it sits on the line; `detail` carries anything else as text, including the codepoint sets both `resolved` arms report and the footnote arm's `explained:` note. The six detectors each used to name their own fields, which made the list ragged, and a ragged list of records is not a table — TOON silently degrades it to the nested form, so a corpus sweep printed 265 findings as 51 KB of indented blocks and pooling two refs tripped the emitter's list guard. **No field holds a list.**
```
--all        every review/ page with a proposal
--path FILE  proposal file, one ref only [review/PP-NNN/proposal.json]
--root --json --toon --no-pager
```

### proposal fix [REF ...]
**Does** applies the one unambiguous correction — a single mark `resolved` names that `text` lacks, swapped for the single mark `text` has that `resolved` lacks.
**Reads** the proposal.
**Writes** the proposal, in place.
**Exit** always 0.
**Note** nothing to clobber under `--all`: it repairs only what is already wrong, so a page with nothing to fix is untouched.
```
--all        every review/ page with a proposal
--path FILE  proposal file, one ref only [review/PP-NNN/proposal.json]
--root --json --toon --no-pager
```

### proposal codepoints [REF ...]
**Does** names every non-ASCII character in a line's field, or in every line of the page.
**Reads** the proposal.
**Writes** —
**Exit** always 0.
**Note** **`LINE` is `--line` here and a positional on `set`/`replace`**, and the split is not arbitrary: a plural ref cannot sit beside a positional index, argparse having no way to tell the index from another ref. This action is the reader of the three, so it is the one that wanted the plural; the two editors are singular anyway, a line index being an identity that belongs to exactly one page. Omitting `--line` names every line, which is the more useful default besides — asking what a proposal actually contains rather than confirming one line at a time.
```
--all        every review/ page with a proposal
--line LINE  one line's index [every line on the page]
--field {text,resolved,note}  which field [text]
--path FILE                   proposal file, one ref only [review/PP-NNN/proposal.json]
--root --json --toon --no-pager
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
--root --json --toon --no-pager
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
--root --json --toon --no-pager
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

### zones check [REF ...]
**Does** the gate. Named pages in full; `--all` sweeps every keyed page.
**Reads** the `--store` store, `data/zones_config.json`, the `gt/` sidecars, and `scans/` when ink runs.
**Writes** `gt/zones/_ink_cache.json` (derived) when it reads a raster.
**Exit** 1 if any named page has errors and `--store gt`; **always 0 under `--store mz`**, which is measurement.
**Note** **named pages always ink-check, however many.** `--ink` is a sweep economy — ~0.20 s a page against ~1 ms for the file-level checks — and naming two pages must not quietly buy a weaker check than naming one, since this is the only check that can see a *missing* zone. Pooled, `errors`/`warnings`/`uncovered` become counts in the row and each gets its own ref-keyed table; one ref prints the report exactly as it always did.
```
--store {gt,mz}  which store [gt]
--all            every page the store holds
--itinerary LST  scope the sweep to a work-list [whole store]
--ink            SWEEP ONLY: read every raster for ink no zone accounts for [off; always on for named pages]
--lines          SINGLE PAGE ONLY: every zone's lines of type [off; costs a second raster decode]
--jobs N         worker threads; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --no-pager
```

### zones edit [REF ...]
**Does** the segmentation editor on 127.0.0.1, arrow keys walking the corpus. `/` and `?` cycle the store shown; a machine page opens as an unsaved proposal.
**Reads** all three stores, `data/zones_config.json`, `scans/`.
**Writes** `gt/zones/` on save — no `--commit`, the save click is the human act.
**Exit** 2 if nothing supplies a start page. This is the one argument check argparse cannot express.
**Note** **several refs *are* an itinerary**: the session opens at the first and walks the list, which is the same work-list an `.lst` supplies, spelled for the two-page case that would otherwise want a scratch file. One ref is a page to start at, not the only page reachable. `--all` walks the book.
```
--all            every scan, in order
--itinerary LST  walk this work-list; name no ref to resume at its first unkeyed page
--port N         port [8732; ocr review --serve holds 8731]
--root --json --toon --no-pager
```

### zones predict [REF ...]
**Does** runs the trained segmenter into `mz/zones/`. Input is always the blotted raster, since that is what the model was trained on.
**Reads** `models/bogoras-seg/`, `scans/w-figs-blotted/`, the split marks.
**Writes** `mz/zones/` (derived) — never `gt/`.
**Exit** 1 if any swept page lacked a blot. A single ref exits 0.
**Note** an exempt mark does not stop a named ref — naming a page is the request — but an existing prediction does, unless `--force`: the mz file's sha256 is the store's only witness to which model wrote it. **Several named refs go through the sweep** so the model loads once, carrying that override with them; without it a named plate would be dropped in silence by the command that named it. Under `--all` the exempt ruling holds, which is what it is for.
```
--all            every page with a blotted raster
--force          re-run over pages that already have a prediction [off]
--itinerary LST  predict over a work-list [every page with a blot, minus exempt]
--model PATH     the segmentation model [models/bogoras-seg/zones-seg.safetensors]
--decode {raw,dp} blob vectorisation, or the segmental DP over the page [raw]
--device DEV     torch device [auto]
--root --json --toon --no-pager
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
--root --json --toon --no-pager
```

### zones assemble
**Does** lays out `train/bogoras-seg/` from the split marks and reports the ketos invocation. Runs nothing.
**Reads** `gt/zones/`, `scans/w-figs-blotted/`, the split lists.
**Writes** `train/bogoras-seg/` — pure scratch, clobbered freely, because the split a model trained on travels in that model's own manifest.
**Exit** 1 if any listed page has no blotted raster.
```
--scratch  train from random init: no -i, kraken's default spec — the one configuration
           in which the class-map permutation cannot arise [off]
--root --json --toon --no-pager
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
--root --json --toon --no-pager
```

### zones remap
**Does** puts the learned names back on the model's output channels, when `score` shows a consistent relabelling rather than a weak model. Derives the map on the training pages and refuses unless it is 1-1 and holds out. Prints two tables.
**Reads** the model, `gt/zones/`.
**Writes** the model's class map under `--commit`, keeping the original as `.bak`.
**Exit** always 0.
```
--model PATH  [models/bogoras-seg/zones-seg.safetensors]
--commit      rewrite the class map [off — previews]
--root --json --toon --no-pager
```

### zones remark-eval FRACTION
**Does** moves a fraction of train into eval — stratified per part, independent pages first, spread rather than taken off the front. Additive: a page a human already marked is never touched.
**Reads** `gt/zones/`, the split lists.
**Writes** the split lists under `--commit`.
**Exit** always 0.
```
--commit  write the split marks [off — reports]
--root --json --toon --no-pager
```

### zones delete REF [REF ...]
**Does** un-keys a page — removes its file and every mark that referred to it. The one thing the store could not express, `save_zones` refusing an empty save.
**Reads** `gt/zones/` and its sidecars.
**Writes** `gt/zones/` under `--commit`, keeping `.prev` and journalling the act.
**Exit** always 0.
**Note** **no `--all`, and here the absence is a safety property rather than a cost.** "Un-key the whole ground-truth store" must not be one flag away from a command someone types. `ocr clean` has `--all` precisely because it deletes only derived output; this deletes authored work.
```
--commit  actually remove [off — previews]
--root --json --toon --no-pager
```

### zones diff [REF ...]
**Does** what differs between the two stores, paired by vertical overlap: `only_in_gt`, `only_in_mz`, `label`, `edge`. Prints a summary then the rows.
**Reads** both stores, `data/zones_config.json`.
**Writes** —
**Exit** always 0 — measurement.
**Note** an aggregate: refs scope the summary rather than multiplying it, and the rows already carry `ref`.
```
--all     every page present in both stores
--root --json --toon --no-pager
```

### zones paragraphs [REF ...]
**Does** audits the paragraph-boundary rule both ways. `false_negative` is a recall figure; `false_positive` is a **worklist, not a precision figure**, since gt cannot arbitrate a rule that corrects it.
**Reads** `gt/zones/`, `scans/w-figs-blotted/`, `data/zones_config.json`.
**Writes** —
**Exit** always 0 — measurement.
**Note** an aggregate, like `zones diff`.
```
--all            every keyed page
--itinerary LST  scope to a work-list [whole corpus]
--jobs N         worker threads; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --no-pager
```

### zones link
**Does** rebuilds `zones/`, the read view over both stores, the human file winning. Reports the split, which is how much of the corpus is still the machine's word.
**Reads** both stores.
**Writes** `zones/` (derived) — relative symlinks; stale ones are removed and counted.
**Exit** always 0.
```
--root --json --toon --no-pager
```

### zones blot [REF ...]
**Does** the figure-blotted training raster — `gt/fig/` zones painted **white**, the declared box and not a pixel more. Distinct from `ocr blot`, which paints in conspicuous colours for a human; this one has to look like blank paper.
**Reads** `scans/`, `gt/fig/`.
**Writes** `scans/w-figs-blotted/` (derived).
**Exit** always 0.
**Note** **`--all` carries no mtime skip, and the reason is cost rather than impossibility.** Repainting 252 composites takes seconds, so an incremental path would add a way to be wrong for very little. It is worth saying plainly because this repo asserted the stronger claim for a long time — that a figure ALTO corrected after the blot could not be detected — and that was simply false: a corrected ALTO is *newer* than the blot, so a test against both inputs catches it. What no mtime test can see is a **deleted** figure ALTO, absence having no timestamp; that is a membership question, and it is why `views check` verifies this farm by membership and its `state: ok` may not be read as "up to date". `ocr blot` does carry the skip, its inputs being an ALTO it compares against directly.
```
--all     all 832 scans
--jobs N  worker threads for the pages that paint; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --no-pager
```

---

## lexicon

Frequency reports over the native corpus in restored `gt/ocr/`, plus the gloss
dictionary, which reads committed TEI instead. All report-only, all exit 0.

### lexicon misses
**Does** frequency-ranked `lexicon_miss` tokens, for bulk approval into `data/lexicon_extra.txt` — which suppresses `lexicon_miss` and nothing else.
**Reads** `gt/ocr/`, `data/lexicon_extra.txt`. **Named, not the view**: every recognizer error in `mz/ocr/` is a token no dictionary carries, i.e. a `lexicon_miss`, and this list feeds a committed human-edited file that suppresses the detector meant to catch them.
**Writes** — **Exit** 0.
```
--root --json --toon --no-pager
```

### lexicon native
**Does** the most frequent native (Tier-1) word forms, for spotting a likely misspelling by comparison rather than by dictionary.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --no-pager
```

### lexicon marks
**Does** bare-vs-marked frequency per base letter — is a bare `g` or a dotted `g̣` the likelier reading, prior to the raster.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --no-pager
```

### lexicon suffixes
**Does** weighted suffix frequency (length 2–8), marks stripped before counting.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --no-pager
```

### lexicon digraphs
**Does** weighted digraph/trigraph frequency, marks and the corpus's own top suffixes stripped first.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --no-pager
```

### lexicon glosses
**Does** the term↔gloss dictionary from committed TEI. Pairs come from `@target`, never from containment, so terms nobody linked are a count rather than a guess. `scope` is the frame the gloss list supplies once, resolved back through `@prev` across a seam.
**Reads** committed `tei/`. **Writes** — **Exit** 0.
```
--root --json --toon --no-pager
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
--root --json --toon --no-pager
```

### find folio N
**Does** ToC entries near a *known* folio — for once the printed folio has been read, not a substitute for `toc_window`'s prediction.
**Reads** `data/toc.json`. **Writes** — **Exit** 0.
```
--span N  folios either side [4]
--root --json --toon --no-pager
```

### find authority [QUERY]
**Does** works matching a citation read in the body — siglum, bare name in prose, title, or a string off the printed entry. Every match returned and ranked by which field caught it: 51 sigla share 34 names, so a single answer would be manufactured. A footnote form (`Dall, I, p. 375.`) goes in whole; the lifted volume is echoed on stderr, because a silently rewritten query is an unexplainable miss.
**Reads** `data/authorities.json`. **Writes** — **Exit** 0.
```
--volume V    volume the citation names (II or 2); excludes on contradiction, not absence
--sigla       the resolution table instead: one row per cited_as, so collisions show
--key KEY     one record in full, printed blocks included
--unlocated   only works with neither doi nor url — the worklist
--root --json --toon --no-pager
```

---

## corpus

Whole-corpus gates. An action lands here only if it gates the corpus as a whole
rather than belonging to one store.

### corpus normalize REF|PATH [REF|PATH ...]
**Does** NFD conformance, §2.9 spacing, and the lookalike census across every store. It prints the census **and** what a `--commit` would rewrite — two tables, because they are two code paths and a preview agreeing with itself is no preview.
**Reads** every corpus store, deduped by real path (`ocr/` and `gt/ocr/` are two names over one inode).
**Writes** corpus files in place under `--commit` — raw source, never a parsed tree, so element and attribute order cannot move.
**Exit** 1 on NFD drift, an unlicensed mark, or spacing drift. The lookalike census does **not** gate: it is a worklist needing a human ruling on what the page prints. `--commit` always exits 0. Exit 2 for nothing named, or for targets together with `--all`.
**Note** **the scope is a mixed positional list**, a `PP-NNN` ref or a path, and the two never collide because a ref's shape is closed. `harness corpus normalize 1-052 data/readings.md` scopes to both. It was `--path`, repeatable — a required file argument spelled as a flag, which is the smell the whole plural pass came out of.
**Note** **a named ref covers its own `proposal.json` where `--all` does not.** The corpus sweep excludes proposals on purpose (`normalize.PATH_ONLY_GLOBS`): a proposal for an already-restored page accumulates apostrophe hits that can never be resolved, so it would be permanent noise in a corpus-wide gate. Naming the page is the same explicit act `--path review/PP-NNN/proposal.json` was, so the mid-pass protection survives the change.
```
--all        every file the corpus globs reach
--commit     write the fixes; required to touch any file, scoped or not [off]
--root --json --toon --no-pager
```

### corpus figures
**Does** reconciles `gt/fig/` zone geometry against `data/readings.md` captions, in both directions.
**Reads** `gt/fig/`, `data/readings.md`, `data/loi.json`.
**Writes** —
**Exit** 1 if `missing` or `orphan` is non-empty. The counts alone never decide it: 250 pages was once the expected total *and* wrong in two compensating directions at once.
```
--root --json --toon --no-pager
```

---

## views

The derived trees git does not carry: the read views over the paired stores
(`ocr/`, `zones/`), the scan farms (`scans/w-figs/`, `scans/w-ocr/`), and the
segmenter's blotted rasters (`scans/w-figs-blotted/`). A fresh clone has none of
them.

`ocr link` and `zones link` are the same act said from inside those groups, and
call the same functions. Two spellings, one implementation.

### views check [FARM ...]
**Does** one row per **named** derived tree: whether it exists, whether its membership still matches whatever decides it, and **how deep that comparison went**.
**Reads** the named farms' directories, plus the stores that decide each one's membership. Tests directories itself rather than going through a guarded enumerator — the verb that reports absence has to be callable in its presence.
**Writes** —
**Exit** 1 if any *named* farm is `absent` or `stale`; 0 otherwise. A gate rather than measurement: each is a real defect in this working copy with a one-command fix. Scoping the selection scopes the gate — asking about `ocr` and getting exit 1 for a blot tree nobody mentioned would make the code unreadable. Exit 2 for nothing named, or for farms together with `--all`.
```
FARM...       which trees, space-separated: ocr, zones, w-figs-blotted, w-figs,
              w-ocr, scans, train
--all         every farm this action handles
--root --json --toon --no-pager
```
**Note** the selector is a **positional, not `--only`**, because `--only` already means "line indices" throughout `ocr` and the harness holds to one meaning per flag name. "Everything" must be *said* rather than implied, for symmetry with `build`, where the cost is real — a selector meaning "everything" on one action and needing to be spelled on the other is a difference the caller has to carry between two commands usually typed in sequence. It used to be spelled `all`, a *value* of the positional, which made this the one place in the CLI where everything was not `--all`; the old form is caught by the rename trap.
**Note** four states, and the fourth is the point. `absent` is the directory not existing; `stale` is membership disagreeing with the criterion, or a link pointing nowhere; `ok` is neither; **`?` is no verdict available** — `scans/` and `train/bogoras-seg/` have no criterion the harness can compute, and reporting `ok` there would be a clean bill of health nobody issued. `?` does not gate: it describes the check's reach, not the tree.
**Note** `verified` says how deep the comparison went, and `membership` is not a hedge — but it is a statement about *this verb*, not about what is knowable. Nothing here opens pixel data or the timestamps behind it, so `state: ok` must not be read as "up to date". This entry used to justify the column by calling the blot tree's freshness *uncheckable*, which was false: see `zones blot`. What genuinely escapes any timestamp is a **deleted** figure ALTO, and that is a membership question anyway.
**Note** `dangling` counts links whose target has gone. On a machine without `scans/` the two selection farms report their whole membership as dangling, which is correct and deliberate — see `views build`.

### views build [FARM ...]
**Does** rebuilds the **named** derived trees, in dependency order (`w-ocr` links into the `ocr/` view, so it follows it) — registry order, never the order they were typed.
**Reads** the stores that decide each named farm's membership; `scans/` and `gt/fig/` for the blot.
**Writes** the named farms among `ocr/`, `zones/`, `scans/w-figs-blotted/`, `scans/w-figs/`, `scans/w-ocr/` — all derived. Writes on invocation with no `--commit`, like every other derived output: there the write *is* the action, and no authored store is touched.
**Exit** always 0 — a bare invocation naming no farm is a usage error (2), not a build of everything.
```
FARM...       which trees, space-separated: ocr, zones, w-figs-blotted, w-figs,
              w-ocr
--all         every farm this action handles
--root --json --toon --no-pager
```
**Note** **`--all` must be said, and this verb is why.** Rebuilding `scans/w-figs-blotted/` repaints 252 page composites and is by a wide margin the most expensive thing in the harness — a cost entirely invisible at the call site, since nothing about `harness views build` suggests a corpus-wide raster pass. The caller who wanted one view relinked after a `restore` was the one paying it. **Prefer the per-domain spelling in a per-page loop**: `ocr link` and `zones link` relink one view and are what a page-level pass wants; `views build --all` is for a deliberate corpus-level sweep, the way `corpus normalize --all` is against naming the page.
**Note** **a farm whose builder must *read* an absent tree is skipped with a row**, never attempted and never silently dropped. The distinction is between what a builder opens and what its links merely point at: the blot builder reads pixels out of `scans/`, so with no `scans/` it cannot run; `w-figs` and `w-ocr` need only their tracked membership sources and build fine, leaving raster links that dangle — this repo's stated disposition for a link into an ignored tree. Hence exit 0 on a clone: building what can be built is the success case, and `views check` is what says what is still missing.
**Note** `scans/` and `train/bogoras-seg/` are reported by `check` and built by neither. `scans/` is `pdftoppm` over `pdfs/`, whose entries are symlinks pointing outside the repo, so on a clone the rasters cannot be regenerated at all; `train/` is scratch that `zones assemble` clobbers by design.
