# `harness` — every verb, every action

The complete surface. `harness/tests/test_cli_surface.py` holds this file and
the click command tree together: an action or a flag in one and not the other fails
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
whose blot is newer than its ALTO. `zones blot` repaints unconditionally: skip
policy there waits on the dependency graph, which is a sprint of its own.

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
natural width and a line too wide for the screen runs off the edge rather than
losing a character (`--pager` is how you read the rest of it). **`--toon` forces
TOON at a terminal**, which is how a human reproduces exactly what a skill's
model saw. `--json` gives indented JSON.

**Colour is by type, not by verdict**, and the palette is rich's own `repr.*`
theme rather than one invented here: a null is dim, the two booleans take rich's
green and red, numbers are cyan, headers bold. The renderer knows a cell's type
and nothing about its meaning — it cannot tell `keyed: false` (an unread page)
from `ok: false` (a gate failed) — so a scheme claiming to say which would be a
judgement the display layer is not entitled to make. The exception is `tei
validate`/`tei header`, whose reports print `RESULT: PASS`/`FAIL` themselves;
painting those asserts nothing the text does not already say. `NO_COLOR` beats
`FORCE_COLOR` beats the TTY test.

`--json` and `--toon` are mutually exclusive, and both are on every action
alongside `--root` and `--pager`; the four share the trailing
`--root --json --toon --pager` line of each fence below rather than being
restated per entry.

**Long sweeps draw a progress bar on stderr.** The pooled raster sweeps (`zones
check --ink`, `zones paragraphs`, `zones blot`, `ocr gaps`, `ocr blot`) and the
slow serial ones (`ocr predict`, `zones predict`, `ocr crops`/`sheets`/`zoom`)
report the page they are on, how many are done and how long it has taken. It
appears only when stderr is a terminal and only once the work has run for about
half a second, so a short run stays silent and a redirected one is byte-identical
to a run with no bar at all. stdout is untouched: `harness … > file` holds exactly
the payload.

**The pager is opt-in: `--pager`, `$PAGER`, default `less -SRFX`.** It was on by
default in table mode on git's reasoning — `-F` prints and exits when the content
already fits, so short output was supposed to pass straight through — and the
default is now off because the cost falls on the ordinary case: a table that fits
went through a subprocess and a pipe to arrive looking the same, and one that did
not took the terminal from someone who had not asked. `-S` chops rather than
wraps, which is what makes a wide table readable at all — columns stay aligned
and you scroll sideways — and `-R` carries the colour through. Table mode only,
so a pipe is unaffected. **`zones edit` and `ocr review` refuse it**: they print
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

**Argument validation is the parser's.** Constrained values carry a closed
choice set or a validator; a conditionally-required flag is required. Where two
flags are contradictory the command **refuses** rather than preferring one —
`--json` with `--toon`, `tei seam --continues` with `--fresh` — because
precedence standing in for rejection is what the one-tier CLI was retired for.
A flag whose scope is narrower than its action says so in its entry here:
`zones check --ink` is a sweep flag, `--lines` a single-page one.

**Shell completion.** The parser is click (with `cloup`), so completion comes off
the tree itself — every group, action, flag and closed choice set. Add to your
shell rc:

    eval "$(_HARNESS_COMPLETE=zsh_source harness)"     # or bash_source / fish_source

**`--help` is Markdown, rendered.** These entries and the `--help` text are the
same prose; `**bold**` and backticks are shown as emphasis rather than printed.
Actions are grouped into sections (`harness zones --help` splits the store from
the segmenter), and the four globals sit in their own block below an action's own
flags. `NO_COLOR` turns the colour off; a pipe does too.

**`harness tui`** exists when `trogon` is installed — a form-filling terminal UI
over the whole tree, built by introspecting it. Not a declared dependency (it
pulls `textual`, and has had no release since 2024-10), so
`uv run --with trogon harness tui` is the whole cost of trying it.

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
**Note** `figures_on_page` is `{n, caption}` — one record per **printed figure**, `n` being the number the caption itself prints. **Placing a figure is not the collator's competence**; finding where the prose says "(Fig. 87, a)" is. So the pass writes `<figure n="87"/>` and the *build* joins that to zones through `data/readings.md`, and nothing about geometry reaches the model. Two earlier shapes failed the same way: raw `zone_id`s (an opaque string a model cannot check, with the `GraphicZone`/FigDesc pairing left to it — on `1-151` that produced a correct anchor plus a permanent known-false orphan comment about the caption zone), then a page-local ordinal over pictures, which is worse than it looks because **the zone count is not the figure count in either direction** — `1-207` sets fig. 87 *a, b, c* in two boxes with `a` and `b` sharing one, and several boxes routinely tile one irregularly-shaped figure. `n` is null where the caption prints no number and where a figure has no caption at all (`3-006`, `3-007`); neither is an error and neither is referenced from the text. `bbox` went because nothing read it — the collation output carries no geometry.
**Note** `tier1_terms` is `{index, line, text}` — the Tier-1 tokens on this page a human has already keyed, from `gt/ocr/` and never from `mz/` or the view. The pass names one by `index` rather than retyping it; `tei expand` writes the ratified string in. Empty on the 802 pages with no ground truth. What counts as Tier-1 here is `detectors.NON_ENGLISH_HITS` (an inventory glyph or a straight apostrophe), not `INVENTORY_CHARS` alone, which omits U+0027 — the spirant and pause mark, one keystroke from the U+2019 in `LOOKALIKES`. The list is a **floor**: an unmarked ASCII inventory member (`c`, `s`, `j`, `x`) is undetectable and has to be typed, which costs little for a structural reason — what makes a token undetectable is having no marks, and what makes it dangerous to retype is having marks. One token per handle; all 30 spans in committed TEI are single tokens, so a range is built against a real instance rather than guessed at.
**Note** `ocr_lines` is `{index, text}`, and **`index` is what `@facs` cites**. It carried the ALTO `@ID` as `line_id`, a currency no harness verb accepts: `ocr zoom --only` has always taken the index, so acting on a citation meant translating it by hand first. Neither form resolves as a TEI URI today — there is no `<facsimile>` in the corpus — so nothing conformant was given up.
**Note** the three zones that can carry a folio (`context.APPARATUS_ZONES`) are dropped from **both** `catmus_draft` and `ocr_lines` — they leave the draft and arrive as `running_title` instead, so the information is restructured rather than discarded. Out of `ocr_lines` for a sharper reason than the draft's: that list is the set of `@facs` pointer targets, and a running head, a folio or a signature line is never in the TEI body, so citing one would be a mistake by construction. A **caption** line is dropped from the draft only, since it stays citable.
**Note** **one of the four singular actions.** The payload is one page's collation prompt, built to be handed to one model for one page; a merged stream of them is not consumable by the thing it exists for.
```
--root --json --toon --pager
```

### tei validate [REF ...]
**Does** the gate on a page's TEI — output contract, `@facs` resolution, a
`@resp` rank on every Tier-1 span.
**Reads** `tei/`, plus everything `context` reads.
**Writes** —
**Exit** 1 on FAIL — the worst across refs, so one failing page fails the batch.
**Note** `--json` swaps the rendered report for `{ok, errors, warnings, worklist, metrics}`.
**Note** **the one action that does not pool.** Its payload is a rendered report and prose does not tabulate, so several refs print several reports under `# REF` lines. One ref prints exactly what it always did, with no header.
**Note** `--schema` adds the **conformance** check — is this actually TEI — against the committed `data/tei_all.rng` (P5 4.12.0). It catches what no project rule can: an invented attribute, a value of the wrong datatype. The two are complementary and neither subsumes the other — every project rule is expressible in conformant TEI, so the schema is silent on all of them, and a file can satisfy all of them while using an attribute TEI never defined. **On by default** here, off in the library function `validate()`, because compiling `tei_all` costs ~17 s once per process and the test suite calls that function hundreds of times; validating a page afterwards is ~0.3 ms, so a corpus sweep pays the compile once. `tei_all` and not `tei_lite`: the smaller customizations are strict subsets, so one would reject markup this project legitimately writes, and a gate that fails correct input teaches a reader to ignore it. Run it **after `tei expand`** — `index=` is not a TEI attribute, which is what makes an unexpanded page detectable, so it fails here too.
```
--all        every collated page in tei/
--ratified   expect '#ed' instead of '#llm'; a remaining '#llm' becomes a worklist line [off]
--schema     also check the file is conformant TEI, against data/tei_all.rng [on]
--no-schema  skip conformance — the escape for a tight loop, the compile being ~17 s
--root --json --toon --pager
```

### tei expand [REF ...]
**Does** writes ratified Tier-1 forms into a collated page, resolving `index=` handles on Tier-1 elements against `tier1_terms`.
**Reads** `tei/`, `gt/ocr/`.
**Writes** `tei/`, under `--commit`.
**Exit** always 0.
**Note** the collation pass names a native term by its handle — `<foreign xml:lang="ckt" index="7"/>` — instead of retyping it, and this fills in the string a human adjudicated at the raster. **The model's judgement is which token; the glyphs are never its to originate.** Retyping `ɪᵋplɪˊlᴇ` character by character puts §5's two residual classes back on the table (a dropped U+0323, an `ɪ` read as `i`), and both are unfalsifiable downstream — the form still looks like a form, no lexicon knows it, no second reader exists, and CATMuS reads 0% of the inventory.
**Note** **`gt/ocr/` only.** `tier1_terms` is empty on the 802 pages with no ground truth, so there is nothing to expand there and that is correct: a list built from `mz/ocr/` would be garbled forms offered to be copied verbatim, which is this failure inverted rather than avoided. On those pages the pass reads the raster, writes its best attempt and flags the line.
**Note** a handle naming no term is left **exactly as it is** — not dropped, not guessed at. `tei validate` errors on a surviving `@index` and names the missing step rather than a dangling reference, `@index` not being a TEI attribute. Removing it would leave a Tier-1 element holding whatever the pass typed, indistinguishable from one that never asked.
**Note** a handle on an element that **already holds text** is a conflict, not an override: two claims about the same glyphs, reported with neither written. Same for a handle on an element with no Tier-1 `xml:lang` — English is not transcluded.
**Note** an expanded span is written **`resp="#gt"`**, the fourth rank — *adopted*, transcluded whole out of adjudicated ground truth. `#llm` is false about it (no model chose those characters) and `#ed` is false too (no human read this document); the responsible act happened one artifact upstream and this records where. It is **not a promotion**: the human act the firewall requires did happen, at the raster. `#gt` is not a fourth point on the `#htr < #llm < #ed` order — its authority over glyph identity is an editor's, so it does not sit below `#ed`, and its subject is a different artifact, so it is not `#ed`.
**Note** the rank is **verified, not accepted.** `tei validate` checks every `#gt` span for membership in the page's `tier1_terms` — whole-token by construction, so a dropped final mark cannot pass the way it would past a substring test (`Qeˊñ` is a substring of `Qeˊñu`). Two consequences: a `#gt` claim on a page with no ground truth fails and says so, and correcting the ground truth under an adopted span makes it fail rather than go stale, which is the property a written-once attribute could not have.
**Note** a page with no handles reports `resolved: []` and is not an error — every page collated before this existed, and every page with no native forms.
**Note** with more than one ref and `--commit`, every page is previewed before any is written — the same up-front rule `ocr restore` and `tei ids` keep.
```
--all     every collated page in tei/
--commit  write the ratified forms [off — reports what would change]
--root --json --toon --pager
```

### tei state REF [REF ...]
**Does** one page's seam record — predicted folio, what it rests on, headings believed open.
**Reads** committed `tei/`.
**Writes** —
**Exit** always 0.
**Note** **no `--all`** — `tei ledger` *is* the corpus form of this, and a second spelling of one report is how two answers to one question start to drift.
```
--root --json --toon --pager
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
--root --json --toon --pager
```

### tei pair [REF ...]
**Does** links each `<gloss>` to its `<term>` where containment decides; reports and writes nothing where it does not.
**Reads** `tei/`.
**Writes** `tei/` under `--commit`.
**Exit** always 0.
```
--all     every collated page in tei/
--commit  write the gloss->term links [off]
--root --json --toon --pager
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
--root --json --toon --pager
```

### tei ledger
**Does** the seam table across every scan — folio, heading fold, boundary state.
**Reads** committed `tei/`.
**Writes** —
**Exit** always 0.
```
--part N        restrict to one part [all]
--untranscribed refs with no committed TEI: bare lines, or a JSON array under --json [off]
--root --json --toon --pager
```

### tei header
**Does** the gate on `tei/corpus-header.xml` — that the ranks it declares are exactly the ones `tei validate` enforces.
**Reads** `tei/corpus-header.xml`.
**Writes** —
**Exit** 1 on FAIL.
**Note** `--json` swaps the rendered report for the structured verdict.
**Note** `--schema` checks conformance too, as on `tei validate` and on by default. The header is a bare `<teiHeader>` and `teiCorpus` requires a `TEI` child, so there is no conformant container for it — it is wrapped in a minimal `<TEI>` **in memory** to be checkable, never on disk, since inventing a container there would settle the assembly scheme by accident. This found the first defect on its first run: `version="stock"` on `<application>`, where `teidata.versionNumber` is a pattern that does not match it, in a file read by hand more than once.
```
--schema     also check the header is conformant TEI, wrapped in memory [on]
--no-schema  skip conformance — the compile is ~17 s
--root --json --toon --pager
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
--root --json --toon --pager
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
--root --json --toon --pager
```

### ocr gaps [REF ...]
**Does** bands of ink no TextLine covers — the dropped-line detector. A band is a place to look, not a verdict.
**Reads** the `--store` store, or the view, `scans/`, `gt/fig/`, `gt/zones/_ink_exempt.json`.
**Writes** —
**Exit** always 0.
**Note** `--all` is the corpus dropped-line sweep, at a raster read per page. It reads through the view unless `--store` narrows it, which is `ocr pages`' rule — a machine-read page is workable, and this verb neither gates nor publishes a rate.
**Note** a band the zoning pass ruled not type carries that ruling: `exempted` true and the `note` that made the call, matched on the band's midpoint by the same `_ink_excuse` `zones check --ink` uses. **Flagged, never suppressed** — an exempted band still reports, because dropping it would make this the one place a wrong call could hide. Without this the ruling reached the zone editor and stopped, and an OCR-side reader re-adjudicated from the raster a band a human had already settled.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds
--jobs N    worker threads; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --pager
```

### ocr adopt-gap REF VPOS[,VPOS...]
**Does** materializes measured `gaps` bands as empty TextLines so a dropped line can be keyed. Geometry only, never CONTENT. Refuses an unmeasured vpos, a band overlapping an existing line, and a band ruled not type in `gt/zones/_ink_exempt.json`.
**Reads** the `--store` store, or the view, `scans/`, `gt/zones/_ink_exempt.json`.
**Writes** `gt/ocr/` under `--commit`, resolved explicitly and never through the view.
**Exit** always 0; exit 2 on an unmeasured vpos, an overlap, or an exempted band.
**Note** the exemption refusal is fail-closed on purpose: the zoning pass's ruling is the ratified witness, and overturning it from the OCR side would be a model undoing a human call silently. Disagreeing means dropping the exemption in `zones edit` — itself a human act. **Also unrunnable on a restoration**, since it resolves its target to `gt/ocr/` explicitly and a page with no ground truth has none; a dropped line found on a fresh page is reported, not adopted, until `restore` has written the page once.
**Note** **one of the four singular actions**: `VPOS` is a band measured on *that* page's raster, so a ref list would carry a band list belonging to one of them. `test_cli_surface.py` holds the exemption by name.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--commit    actually write gt/ocr/ [off — reports the lines it would create]
--root --json --toon --pager
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
--root --json --toon --pager
```

### ocr queue REF [REF ...]
**Does** validates a batch of pages, writes it to the claim queue, and prints the **one prompt every reader of the batch gets** — the block between `<!-- claim:begin -->` and `<!-- claim:end -->` in `.claude/skills/rebuild-groundtruth/dispatch.md`. That prompt names no page and carries no substitution: each reader takes its own ref with `ocr claim`.
**Reads** `dispatch.md`, `gt/zones/` (and `_exempt.lst`), `gt/fig/`, `gt/ocr/`, `mz/ocr/`.
**Writes** `review/_queue.txt`, and clears `review/_claims/`. Prompt to stdout as plain text, everything operational to stderr, so a pipe carries the prompt and nothing else.
**Exit** 0 with a prompt; 1 when any page in the batch is not a dispatch candidate, and the message names the remedy.
**Note** **send it unedited and identical to every reader.** Identity of the first turn is what caches: three readers dispatched with `moll-043`/`044`/`045` in their prompts all opened COLD at the same total — the totals matching because three refs of the same byte length cost the same — while a batch of byte-identical prompts shared. A ref in the prompt costs every sibling the whole shared context, however few characters it is, which is why the ref arrives from a tool call instead. **Stagger the first launch about ten seconds** so it writes the context the rest read; `agents usage` reports what that bought as `missed`.

**Never assemble either text by hand.** It was done twice in one session and the second time five clauses reached the agent that existed nowhere in `dispatch.md`, so the doc described a prompt nobody sent and the run measured something unwritten. Same fault as writing a glyph into a note instead of citing its codepoint.

Every page is checked before any is queued, and its block is rendered and thrown away — a page whose survey raises fails here, where the fix is still a command. Five refusals, four of them `dispatch.md`'s survey made mechanical rather than eyeballed: a ref named twice (one page, two readers, who overwrite each other); no `gt/zones/` entry (not a keyed text page); marked in `_exempt.lst` (a human ruled it not a text page); **`gt/ocr/` already present** — the sharp one, since a reader sent at a keyed page reads the human text through every ALTO verb and its proposal stops being an independent witness, and a named range contains such a page sooner or later (`2-031`–`2-035` contained `2-034`); nothing in `mz/ocr/`, naming `ocr predict`.
```
--note TEXT  a sentence appended to the branch paragraph of every page block in
             this batch; per-page notes want separate queue calls
--root --json --toon --pager
```

### ocr claim
**Does** takes the next unclaimed ref off `review/_queue.txt` and prints that page's block — the ref, and what the four-store survey found (line and zone counts, and which of the two things a `gaps` band means on this page), from between `<!-- prompt:begin -->` and `<!-- prompt:end -->`.
**Reads** `review/_queue.txt`, `review/_claims/`, `dispatch.md`, the four stores.
**Writes** `review/_claims/PP-NNN`, stamped with the local time. Block to stdout as plain text.
**Exit** 0 with a block; 1 when the queue is empty or every ref on it is taken.
**Note** **takes no ref, and that is the point** — the page arrives from a tool result rather than from a prompt that would then differ between siblings. `O_CREAT|O_EXCL` is the whole lock: the kernel decides which of several readers created the marker first, so there is no window between the check and the take. Readers are dispatched simultaneously and cannot see each other, so a lock resting on politeness rests on nothing; eight concurrent claimers over a three-ref queue return three distinct refs.

**A claim is never released.** A reader that dies holding one leaves its page unread and its claim standing, which is the honest state rather than a silent retry — `reconcile` names the ref, and re-queueing it is a decision somebody makes. Exit 1 on an empty queue rather than an empty success: a reader handed silence at exit 0 has been told nothing, and picking a page for itself is exactly what a silence invites.
```
--root --json --toon --pager
```

### ocr reconcile REF [REF ...]
**Does** what the batch came back with — each named ref `keyed` (a proposal exists), `CLAIMED, no proposal` (a reader took it and did not come back), or `unclaimed` (nobody took it).
**Reads** `review/_claims/`, `review/PP-NNN/proposal.json`.
**Writes** nothing.
**Exit** 0 when every named ref is keyed; 1 naming those that produced nothing.
**Note** three states rather than two, because "no proposal" has two causes at scale and they want different answers: the queue outran the readers (or they were never sent), against a reader that died or ran out of turns. Only the second is worth chasing, and the claim stamp is there for that question alone. A page dealt twice or not at all is a *valid* ref and fails silently everywhere else.
```
--root --json --toon --pager
```

### ocr numbered REF [REF ...]
**Does** the whole page with each line's ALTO `index` drawn in an added left gutter. The reading pass's first image, and its only one on a page that raises no doubt.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/numbered.png` (derived), or `--out`.
**Exit** always 0; exit 2 for `--out` with more than one ref.
**Note** no `--all`, for `crops`' reason. The label is the **index**, the identity `sheets`, `zoom --only`, `proposal.json` and `restore` all join on — so the numbers are legitimately not consecutive down the page, and that is the tell `harness/README.md`'s caller invariants describe rather than a fault here. A page composite is delivered to a reader at about 0.64× whatever is sent, whatever its size, which is why `--font` is large and why this rung cannot answer a question about one mark: escalate to `sheets --only`, then `zoom --only`.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--gutter N    px added left of the page for the labels [160]
--font N      label px in the written image [64]
--out PATH    write elsewhere [review/PP-NNN/numbered.png]
--root --json --toon --pager
```

### ocr sheets REF [REF ...]
**Does** labelled contact sheets, index in the margin, nothing downscaled. Emits the sheet/lines map, not the line table.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/sheets/` (derived), or `--out`.
**Exit** always 0; exit 2 for `--only` or `--out` with more than one ref.
**Note** no `--all`, for `crops`' reason. `--only` is what makes this the middle rung rather than an all-or-nothing first read, and it carries `zoom --only`'s rule: a line index is an *identity*, not a position, so the same numbers name unrelated lines on the next page. Sheets are named for the lines on them (`lines-11-14.png`, `linesm-` under `--margins`), so two selections over one page cannot overwrite each other and an overlapping one reuses what it agrees with.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--only SPEC   line indices, e.g. 7,20,22-26 [every line]
--per-sheet N lines per sheet, upper bound only [40]
--height N    max sheet height in px [1960 — the tallest a ~1900px-wide sheet can
              be and still fit the 4784-visual-token ceiling without being
              resampled on delivery]
--margins     widen to the PrintSpace margins [off]
--out PATH    write elsewhere [review/PP-NNN/sheets]
--root --json --toon --pager
```

### ocr zoom REF [REF ...]
**Does** magnified lines — overlapping strips at an integer scale, packed into as few sheets as the height budget allows.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/zoom/` (derived), or `--out`.
**Exit** always 0; exit 2 for `--only` or `--out` with more than one ref.
**Note** no `--all`. `--only` is the sharper of the two per-page flags: a line index is an *identity*, not a position, so the same numbers name unrelated lines on the next page.

**A span is widened, never obeyed literally, and that is deliberate.** A strip is a fixed `window` of source pixels and the sheet is padded to `--client-w` regardless, so a span narrower than one strip renders inside white space you have already paid for. It is therefore expanded symmetrically to fill the window — sliding rather than shrinking at a line edge — and then both edges snap outward to the nearest blank pixel column, bounded, so **no glyph is ever cut**. The rendered span, not the requested one, is what the label and filename record: two requests that widen onto the same region are one picture and must share one file.

This exists because clipping does not cost a bad image, it costs a *re-call*. `2-134` took ten zoom invocations, most of them the same doubt re-aimed after the previous span cut the word in half. Widening absorbs a few points of aiming error for free; it cannot absorb twenty, and a doubt that needs *locating* rather than resolving belongs at `ocr sheets --only`.

**`@LO-HI` names a percentage of the line's width, and it is where the saving at this rung is.** A doubt is about a mark, not a line, and a mark is a few percent of a full measure — `3-063`'s footnote openers sat in the first characters of their lines, so `42-43` rendered four strips apiece of which three bore on nothing, where `42-43@0-25` renders one each. Percentages, not pixels: the caller is reading a report, not measuring a raster, and a pixel span would mean something different under `--margins`. One line given two different spans is an error rather than a merge, since the hull is the whole-line render the span existed to avoid. `ocr sheets` refuses a span outright — it shows whole lines and has nowhere to honour one.

Each sheet is named for the lines it holds and the settings that drew them — `zoom2m-26-27.png` is lines 26–27 at `--zoom 2 --margins`, `s` marks `--smooth`, and a line whose strips straddle two sheets takes a `-b` suffix. **Two selections over one page therefore cannot overwrite each other**, and an overlapping selection reuses the sheet it already agrees with. They could: sheets were numbered `-001` upward per call, so a second `--only` replaced the first's images while the first's returned index went on naming them — three parallel calls yielded one call's pictures and three reports of them. Finer overrides (`--window`, `--overlap`, `--client-w`, `--height`) are *not* in the name and do reuse it.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--only SPEC   lines, e.g. 7,20,22-26; append @LO-HI for a percentage of a line's
              width, e.g. 42-43@0-25 [every line, whole]
--zoom N      display px per source px, as delivered [2]
--window N    source px per strip [derived from --zoom; overriding upward breaks the scale]
--client-w N  px the reading client shows per image [1450]
--overlap N   px shared by consecutive strips [60]
--height N    max sheet height in px [1600]
--margins     widen to the PrintSpace margins [off]
--smooth      Lanczos instead of nearest-neighbour [off]
--out PATH    write elsewhere [review/PP-NNN/zoom]
--root --json --toon --pager
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
--root --json --toon --pager
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
--root --json --toon --pager
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
--root --json --toon --pager
```

### ocr corrections [REF ...]
**Does** aggregates the character-level `proposal.json` → `decision.json` corrections across every adjudicated page — what readers actually get wrong, ranked.
**Reads** every `review/*/` holding both files.
**Writes** —
**Exit** always 0 — measurement.
**Note** **an aggregate**: refs *scope* it and do not multiply it, so there is one report whether one page was named or forty, and `--all` is every page with both files. Its ref used to be a repeatable `--ref` flag, the one place in the CLI where naming a page was not a positional. It sits in this group rather than under `proposal` because it reads *both* files, and `review`/`restore` own the other one. `restore` computes this same diff per page (`edits`) and discards it, so the pass's own error profile was the one thing in the loop with no record.

Opcodes come from difflib over **NFD** text, so a dropped combining mark ranks as an insert of the mark itself rather than as a replacement of its whole word — which is what makes the ranking legible: 37 dropped dots-below across eight pages collapse to one row instead of scattering over 37 nothing can match. An edit of 12 characters or more on either side reports as `<Nch> -> <Mch>`, since a whole-line retype would otherwise mint a row nothing will ever match again.

**The store spans this project's own history, so an unscoped run is not an error profile.** The leading class — 117 `'`→`ˊ` — is two pages keyed before a bare apostrophe became its own unconditional error, and cannot recur in that form; `--since 2026-07-31` leaves `i`→`ɪ` as the only recurring class, four times on three pages, which is the live picture and matches what `docs/decisions.md` claims about the residual. A page whose `decision.json` carries no `saved_at` is **excluded under `--since` and named in `skipped_unstamped`** rather than dropped, since a missing verdict must not draw in the same column as a clean one.

**It undercounts by construction**: `proposal set`/`replace` overwrite the proposal in place, so a reader error a coordinator repaired *before* adjudication leaves no diff at all (`2-033`'s four bare `g` went that way). It measures what reached the adjudicator, never what the reader first wrote — and the earlier the loop catches a slip, the less of it appears here, which is the intended direction rather than a gap to close.
```
--all         every review/ page holding both files
--since T     only pages whose saved_at sorts at or after this: a duration back
              from now (30s, 5m, 2h, 1d, resolved in local time to match
              `saved_at`) or an ISO date. Unparseable is exit 2, never an empty
              report
--min N       drop changes seen fewer than N times [1]
--root --json --toon --pager
```

### ocr clean [REF ...]
**Does** removes a page's derived working files, leaving `proposal.json` and `decision.json` and the `page.png` link.
**Reads** `review/PP-NNN/`.
**Writes** deletes `crops/`, `sheets/`, `zoom/`, `review.html`.
**Exit** always 0.
**Note** no `--commit`, `--all` included: it removes only derived, regenerable output, which is the same reason `crops` writes without one. The verb that deletes an *authored* file is `zones delete`, and that one has no `--all` at all.
```
--all       every review/ page
--root --json --toon --pager
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
--root --json --toon --pager
```

### ocr link
**Does** rebuilds `ocr/`, the read view over `gt/ocr/` and `mz/ocr/`, the human file winning wherever it exists. `zones link`'s twin — the same shape over the same three-store layout.
**Reads** `gt/ocr/`, `mz/ocr/`.
**Writes** `ocr/` (derived). Relative links; a link whose target has gone is removed and counted rather than left to dangle.
**Exit** always 0.
**Note** `from_gt`/`from_mz` is the number worth reading: how much of the corpus is still only the machines' word.
```
--root --json --toon --pager
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

`conflict[]{fold,form,source,ref,lines,count,in_batch}` finds one word spelled two ways. Fold collapses every contrast axis then casefolds; a bucket whose **casefolded** spellings differ is a hit. That suppresses `äˊmmê`/`Äˊmmê` while catching `Iᵋplɪˊlɪ`/`ɪᵋplɪˊlɪ`, because `casefold("I")` is `"i"` but `casefold("ɪ")` is `"ɪ"` — U+026A has no case mapping. Scoped to folds the batch touches: the store carries standing `i`/`ɪ` inconsistencies of its own and re-reporting them every run would bury the batch's news. `in_batch` separates the batch disagreeing with itself from the batch disagreeing with ground truth.

**One row per (fold, form, page), carrying `lines`** — so two rows sharing a fold *are* the conflict, and each says where to go. The row used to be one per fold with the spellings packed into `batch_forms`/`store_forms` and no line numbers at all, which told an adjudicator a word was keyed two ways and left them to grep for it. `source` is `batch` or `store`; a `store` row has no `lines`, because the prior is `(ref, token)` off the ALTO and carries no line — look it up with `harness ocr lines`, and none is invented. `proposal check` still raises **one issue per fold**, since a word keyed two ways is one fault however many places it surfaces.

**No exemption applies here.** A conflict in a proposal is a *reader's* disagreement and `proposal.json` is the record of what they wrote — never rewritten after adjudication, because `edited` is computed against it. Silencing one would delete the measurement. `data/marks_exempt.json` rules on ground truth and is read only by `lexicon conflicts`.

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
--root --json --toon --pager
```

### proposal check [REF ...]
**Does** cross-checks `resolved` against the codepoints `text` actually contains; flags a straight apostrophe, a dot-prone bare suffix, and — via `marks` — a rare form or a word spelled two ways against the store.
**Reads** `review/PP-NNN/proposal.json`, plus `gt/ocr/` and `data/marks_config.json` for the two corpus arms.
**Writes** —
**Exit** 1 on a **defect**, on any ref — one dirty page fails the batch, which is the contract a gate must have or a batch would launder a failure. Never on an advisory alone, unless `--strict`.
**Note** the corpus arms are `proposal marks`'s two **deterministic** ones, run over the single page so a reader catches its own slip before writing its report. `ratio` is deliberately not among them: one page is a poor sample and it is the arm that cannot decide, so folding it into a per-page gate would assert exactly what `marks` refuses to. A repeated form is one issue naming its other lines, not one issue per occurrence — a keyer's single habit is one fault. The prior is leave-one-out here too, so a revision is not checked against its own descendant. Where `data/marks_config.json` is absent (a fresh clone), the arms are skipped and the rest still runs.

**Overlap with the suffix check is wanted, not deduplicated**: a bare `-gɪn` yields both a `bare suffix` and a `rare form` issue on the same line. They reach one defect from different directions — a measured shape and a corpus share — and a second witness this cheap is what the governing principle asks for.

**Two severities, and only one of them gates.** A **defect** claims something *is* wrong and is the reader's to fix: `resolved` naming codepoints the text lacks, notation with no `resolved` at all, a straight apostrophe, an unpaired footnote marker. An **advisory** is measurement — a corpus share saying "go look": a rare form, a dot-prone bare suffix, a word spelled two ways. The rule is that **a gate must be satisfiable by the actor it gates**, and an advisory is not: a rare-but-correct form cannot be made common, and the second witness in a spelling conflict is another page, which the firewall forbids a reader to open. It gated anyway until the severity split, and eight of eighteen failing proposals failed on advisories alone — so `check` exiting 1 stopped distinguishing a mistyped mark from a rare surname, and the reading brief had been rewritten to teach readers that exit 1 is sometimes fine. An advisory still prints, at the same volume, in the same table; it just stops claiming to be a gate. `--strict` gates on both, for a sweep meant to chase every prompt.

**Every issue is one record shape — `line, issue, severity, token, context, detail` — whatever detector raised it** (`proposal_check.ISSUE_FIELDS`, and the `issue()` constructor is the only way one is built). `line` is `-` for a page-level finding; `token` is the flagged string where there is one; `context` is where it sits on the line; `detail` carries anything else as text, including the codepoint sets both `resolved` arms report and the footnote arm's `explained:` note. The six detectors each used to name their own fields, which made the list ragged, and a ragged list of records is not a table — TOON silently degrades it to the nested form, so a corpus sweep printed 265 findings as 51 KB of indented blocks and pooling two refs tripped the emitter's list guard. **No field holds a list.**
```
--all        every review/ page with a proposal
--path FILE  proposal file, one ref only [review/PP-NNN/proposal.json]
--strict     gate on advisories too — for a sweep meant to chase every prompt,
             not for a page pass, where a rare form that is simply rare would
             make the gate unpassable [off]
--root --json --toon --pager
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
--root --json --toon --pager
```

### proposal codepoints [REF ...]
**Does** names every non-ASCII character in a line's field, or in every line of the page.
**Reads** the proposal.
**Writes** —
**Exit** always 0.
**Note** **`LINE` is `--line` here and a positional on `set`/`replace`**, and the split is not arbitrary: a plural ref cannot sit beside a positional index, a variadic positional having no way to tell the index from another ref. This action is the reader of the three, so it is the one that wanted the plural; the two editors are singular anyway, a line index being an identity that belongs to exactly one page. Omitting `--line` names every line, which is the more useful default besides — asking what a proposal actually contains rather than confirming one line at a time.
```
--all        every review/ page with a proposal
--line LINE  one line's index [every line on the page]
--field {text,resolved,note}  which field [text]
--path FILE                   proposal file, one ref only [review/PP-NNN/proposal.json]
--root --json --toon --pager
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
--root --json --toon --pager
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
--root --json --toon --pager
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
--root --json --toon --pager
```

### zones edit [REF ...]
**Does** the segmentation editor on 127.0.0.1, arrow keys walking the corpus. `/` and `?` cycle the store shown; a machine page opens as an unsaved proposal.
**Reads** all three stores, `data/zones_config.json`, `scans/`.
**Writes** `gt/zones/` on save — no `--commit`, the save click is the human act.
**Exit** 2 if nothing supplies a start page. This is the one argument check the parser cannot express.
**Note** **several refs *are* an itinerary**: the session opens at the first and walks the list, which is the same work-list an `.lst` supplies, spelled for the two-page case that would otherwise want a scratch file. One ref is a page to start at, not the only page reachable. `--all` walks the book.
```
--all            every scan, in order
--itinerary LST  walk this work-list; name no ref to resume at its first unkeyed page
--port N         port [8732; ocr review --serve holds 8731]
--root --json --toon --pager
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
--root --json --toon --pager
```

### zones score
**Does** compares predictions against `gt/zones/` — recall and precision per split, never blended, plus the confusion matrix, a held-out permutation test, and an **`independence`** table: what each split is *made of*, on `page_departure`'s scale. Prints three tables, and a stderr warning when the permutation says relabelling rather than a weak model.
**Reads** `gt/zones/`, `mz/zones/` or `--model`, the frozen split lists.
**Writes** —
**Exit** always 0 — measurement. Exit 2 if the frozen split lists are gone: without them the training pages cannot be told from the rest, and a comparison whose witnesses may be one witness must refuse.
**Note** **read the `independence` row before the recall figure above it.** A held-out set half of which is the model's own segmentation with the edges pulled straight measures how well the model agrees with itself, and the number cannot say so. `_independent` has been the rule `remark-eval` selects on since the set was drawn and nothing reported it afterwards; as of 2026-08-04 the frozen eval set is **64 independent of 138** (77 `geometry only`, 4 `identical`), i.e. the quota was filled past the independent pool. `no_prediction` reads 0 without `--model`, since the scored set is then the intersection of the two stores; with `--model` every keyed page is a candidate and the column is live.
```
--model PATH     segment this checkpoint in memory instead of reading mz/zones/ [read mz/]
--decode {raw,dp} [raw]
--device DEV     torch device [auto]
--root --json --toon --pager
```

### zones assemble
**Does** lays out `train/bogoras-seg/` from the split marks and reports the ketos invocation. Runs nothing.
**Reads** `gt/zones/`, `scans/w-figs-blotted/`, the split lists.
**Writes** `train/bogoras-seg/` — pure scratch, clobbered freely, because the split a model trained on travels in that model's own manifest.
**Exit** 1 if any listed page has no blotted raster.
```
--scratch  train from random init: no -i, kraken's default spec — the one configuration
           in which the class-map permutation cannot arise [off]
--root --json --toon --pager
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
--root --json --toon --pager
```

### zones remap
**Does** puts the learned names back on the model's output channels, when `score` shows a consistent relabelling rather than a weak model. Derives the map on the training pages and refuses unless it is 1-1 and holds out. Prints two tables.
**Reads** the model, `gt/zones/`.
**Writes** the model's class map under `--commit`, keeping the original as `.bak`.
**Exit** always 0.
```
--model PATH  [models/bogoras-seg/zones-seg.safetensors]
--commit      rewrite the class map [off — previews]
--root --json --toon --pager
```

### zones remark-eval FRACTION
**Does** moves a fraction of train into eval — stratified per part, independent pages first, spread rather than taken off the front. Additive: a page a human already marked is never touched.
**Reads** `gt/zones/`, the split lists.
**Writes** the split lists under `--commit`.
**Exit** always 0.
```
--commit  write the split marks [off — reports]
--root --json --toon --pager
```

### zones delete REF [REF ...]
**Does** un-keys a page — removes its file and every mark that referred to it. The one thing the store could not express, `save_zones` refusing an empty save.
**Reads** `gt/zones/` and its sidecars.
**Writes** `gt/zones/` under `--commit`, keeping `.prev` and journalling the act.
**Exit** always 0.
**Note** **no `--all`, and here the absence is a safety property rather than a cost.** "Un-key the whole ground-truth store" must not be one flag away from a command someone types. `ocr clean` has `--all` precisely because it deletes only derived output; this deletes authored work.
```
--commit  actually remove [off — previews]
--root --json --toon --pager
```

### zones diff [REF ...]
**Does** what differs between the two stores, paired by vertical overlap: `only_in_gt`, `only_in_mz`, `label`, `edge`. Prints a summary, then the rows, then a per-page **`departure`** table — a different question from the rows: not *what* differs but **how far the human went beyond the model**, on the scale `--remark-eval` selects held-out pages by (`identical` < `geometry only` < `a label differs` < `zone count differs` < `no prediction`, plus `exempt`, which is off the scale).
**Reads** both stores, `data/zones_config.json`, the split lists.
**Writes** —
**Exit** always 0 — measurement.
**Note** an aggregate: refs scope the summary rather than multiplying it, and the rows already carry `ref`.
**Note** **the `departure` section is scoped to `gt/zones/`, not to the intersection the rows above use**, so its page count is higher by exactly the pages nothing predicted. That is deliberate: `no prediction` is the strongest independence claim in the table, and a report visiting only pages that *have* a prediction can never emit it — a column advertising coverage it does not have.
**Note** **two thresholds meet in this output and they are not the same number.** `edge` fires above `min_zone_h_px` (30 px) and asks *is this a different segmentation*; `NUDGE_PX` (20 px) asks *did the human go beyond straightening edges*. So a page can report zero differences and still count independent — `1-052` does, at 22 px. Not a contradiction, but the looser question currently has the tighter bar, and moving either constant moves the eval set.
```
--all     every page present in both stores
--root --json --toon --pager
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
--root --json --toon --pager
```

### zones link
**Does** rebuilds `zones/`, the read view over both stores, the human file winning. Reports the split, which is how much of the corpus is still the machine's word.
**Reads** both stores.
**Writes** `zones/` (derived) — relative symlinks; stale ones are removed and counted.
**Exit** always 0.
```
--root --json --toon --pager
```

### zones blot [REF ...]
**Does** the figure-blotted training raster — `gt/fig/` zones painted **white**, the declared box and not a pixel more. Distinct from `ocr blot`, which paints in conspicuous colours for a human; this one has to look like blank paper.
**Reads** `scans/`, `gt/fig/`.
**Writes** `scans/w-figs-blotted/` (derived).
**Exit** always 0.
**Note** **`--all` carries no mtime skip, because skip policy here is undecided** — it belongs with the dependency graph, a sprint of its own that has not run. Not because a stale blot is undetectable: a corrected figure ALTO is *newer* than the blot, so a test against both inputs would catch it. What no mtime test can see is a **deleted** figure ALTO, absence having no timestamp; that is a membership question, and it is why `views check` verifies this farm by membership and its `state: ok` may not be read as "up to date". `ocr blot` does carry a skip, its inputs being an ALTO it compares against directly.
```
--all     all 832 scans
--jobs N  worker threads for the pages that paint; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --pager
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
--root --json --toon --pager
```

### lexicon native
**Does** the most frequent native (Tier-1) word forms, for spotting a likely misspelling by comparison rather than by dictionary.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --pager
```

### lexicon marks
**Does** bare-vs-marked frequency per base letter — is a bare `g` or a dotted `g̣` the likelier reading, prior to the raster.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --pager
```

### lexicon suffixes
**Does** weighted suffix frequency (length 2–8), marks stripped before counting.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --pager
```

### lexicon digraphs
**Does** weighted digraph/trigraph frequency, marks and the corpus's own top suffixes stripped first.
**Reads** `gt/ocr/`. **Writes** — **Exit** 0.
```
--root --json --toon --pager
```

### lexicon conflicts
**Does** one word spelled two ways across ground truth — the corpus-wide, store-side arm of `proposal marks`' `conflict`.
**Reads** `gt/ocr/`, `data/marks_config.json`, `data/marks_exempt.json`. **Writes** — **Exit** 0.
```
--root --json --toon --pager
```
**Note** rows are **one per (fold, form, page)** and carry `lines`, so a fold is a worklist rather than a notification: the fold is the word with every contrast axis collapsed, and two rows sharing one mean the corpus spells it two ways. `gt/ocr/` and not the `ocr/` view, on the rule that anything publishing a corpus-wide number names the store — through the view every predicted page would contribute, and CATMuS reads 0% of the inventory, so each of its Tier-1 tokens would be a spelling nobody keyed.

**Where the book itself sets a word two ways, the ruling lives in `data/marks_exempt.json`** — a list of `{fold, refs, note}`, and all three are required. Scoped to a fold **and** the pages it was ruled on, never a fold alone: the same word mis-keyed on a page nobody has examined is exactly what this arm is for, and a fold-wide entry would silence it. That is `gt/zones/_ink_exempt.json`'s reasoning — an exemption narrow enough that it cannot hide the next real finding. `note` is required because without one "the tool complained and I made it stop" is indistinguishable from a judgement, and this file is precisely where a wrong call would hide.

An exempt row is **kept and flagged** (`exempt: true`, carrying its `note`), never dropped; an entry whose conflict no longer occurs on a page that *was* read reports under `stale_exemptions`. Both halves are the mechanism `zones check` uses for ink bands.

**`proposal marks` consults none of this, deliberately.** A conflict in a proposal is a *reader's* disagreement, and `proposal.json` is a record of what someone wrote — never rewritten after adjudication, because `edited` is computed against it. There is nothing there to silence: the conflict is the measurement. Only a conflict in ground truth is a claim about the corpus, and only that can be ruled on.

### lexicon glosses
**Does** the term↔gloss dictionary from committed TEI. Pairs come from `@target`, never from containment, so terms nobody linked are a count rather than a guess. `scope` is the frame the gloss list supplies once, resolved back through `@prev` across a seam.
**Reads** committed `tei/`. **Writes** — **Exit** 0.
```
--root --json --toon --pager
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
--root --json --toon --pager
```

### find folio N
**Does** ToC entries near a *known* folio — for once the printed folio has been read, not a substitute for `toc_window`'s prediction.
**Reads** `data/toc.json`. **Writes** — **Exit** 0.
```
--span N  folios either side [4]
--root --json --toon --pager
```

### find authority [QUERY]
**Does** works matching a citation read in the body — siglum, bare name in prose, title, or a string off the printed entry. Every match returned and ranked by which field caught it: 51 sigla share 34 names, so a single answer would be manufactured. A footnote form (`Dall, I, p. 375.`) goes in whole; the lifted volume is echoed on stderr, because a silently rewritten query is an unexplainable miss.
**Reads** `data/authorities.json`. **Writes** — **Exit** 0.
```
--volume V    volume the citation names (II or 2); excludes on contradiction, not absence
--sigla       the resolution table instead: one row per cited_as, so collisions show
--key KEY     one record in full, printed blocks included
--unlocated   only works with neither doi nor url — the worklist
--root --json --toon --pager
```

---

## corpus

Whole-corpus gates, and the census across every store. An action lands here only
if its subject is the corpus as a whole rather than one store. `state` is the one
that does not gate, and it belongs for the same reason the other two do: no
single store can answer it.

### corpus state PP-NNN [PP-NNN ...]
**Does** reports where each page has got to across every store at once, on one ladder: `scanned` → `zoned-mz` → `zoned-gt` → `ocr-mz` → `proposed` → `decided` → `ocr-gt` → `collated`. `stage` is the furthest rung reached; `skipped` names the rungs below it that are **not**, so a page that took a route the pipeline no longer offers stays visible instead of being summarised away.
**Reads** the presence of paths only — `scans/`, `gt/zones/` + `mz/zones/` + the split lists, `gt/ocr/` + `mz/ocr/`, `gt/fig/`, `review/PP-NNN/`, `tei/`. Never a file's contents, which is what makes it ~0.4 s over 832 pages and also why it cannot say whether a page's zoning is any *good*: that is `zones check`, and it costs a raster.
**Writes** —
**Exit** always 0. A census is measurement, not a gate.
**Note** **`--all` enumerates `scans/`, not any store.** A page no store holds is the most interesting row this verb has, and enumerating a store would hide exactly those — which is also why `absent` is a stage rather than an omission.
**Note** **`skipped` is the point of the ladder.** `2-030` reached `gt/ocr/` by the eScriptorium route before the review loop existed; 18 pages carry `gt/ocr/` with no prediction behind them, the eScriptorium-shell cohort; `1-359` carries human zones with no `mz/zones/`. Each is a provenance fact no single store's verb could see. **A rung a route legitimately omits is not a skip**: `zoned-mz` first counted against every exempt page, which put 83 plates in the report and left `1-359` indistinguishable among them — 84 rows saying nothing where 1 says something.
**Note** the same row, minus `ref`, is `page_state` in `harness tei context` — so a collation pass is never left inferring the rank of its own input. An empty `tier1_terms` means "no ground truth" on 802 pages and "ground truth with no marked forms" on `3-063`, and those call for opposite behaviour.
```
--all         every scan in scans/, whether or not any store holds it
--stage NAME  only pages at this rung; repeatable. absent, scanned, zoned-mz,
              zoned-gt, ocr-mz, proposed, decided, ocr-gt, collated
--skipped     only pages that missed a rung below the one they reached
--tally       counts per rung instead of the rows; every rung listed, empty ones
              included — nothing-has-reached-it and everything-has-passed-it are
              different facts
--root --json --toon --pager
```

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
--root --json --toon --pager
```

### corpus figures
**Does** reconciles `gt/fig/` zone geometry against `data/readings.md` captions, in both directions.
**Reads** `gt/fig/`, `data/readings.md`, `data/loi.json`.
**Writes** —
**Exit** 1 if `missing` or `orphan` is non-empty. The counts alone never decide it: 250 pages was once the expected total *and* wrong in two compensating directions at once.
```
--root --json --toon --pager
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
--root --json --toon --pager
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
--root --json --toon --pager
```
**Note** **`--all` must be said, and this verb is why.** Rebuilding `scans/w-figs-blotted/` repaints 252 page composites and is by a wide margin the most expensive thing in the harness — a cost entirely invisible at the call site, since nothing about `harness views build` suggests a corpus-wide raster pass. The caller who wanted one view relinked after a `restore` was the one paying it. **Prefer the per-domain spelling in a per-page loop**: `ocr link` and `zones link` relink one view and are what a page-level pass wants; `views build --all` is for a deliberate corpus-level sweep, the way `corpus normalize --all` is against naming the page.
**Note** **a farm whose builder must *read* an absent tree is skipped with a row**, never attempted and never silently dropped. The distinction is between what a builder opens and what its links merely point at: the blot builder reads pixels out of `scans/`, so with no `scans/` it cannot run; `w-figs` and `w-ocr` need only their tracked membership sources and build fine, leaving raster links that dangle — this repo's stated disposition for a link into an ignored tree. Hence exit 0 on a clone: building what can be built is the success case, and `views check` is what says what is still missing.
**Note** `scans/` and `train/bogoras-seg/` are reported by `check` and built by neither. `scans/` is `pdftoppm` over `pdfs/`, whose entries are symlinks pointing outside the repo, so on a clone the rasters cannot be regenerated at all; `train/` is scratch that `zones assemble` clobbers by design.

## agents

Cache telemetry over a dispatched batch. The only group that touches no corpus
store: it reads Claude Code's task transcripts. Reports; nothing here gates.

### agents usage
**Does** per-agent cache reads and writes for one session's dispatched agents, then groups them into cohorts. **The opening total is the diagnostic** — `read + write` on an agent's first request is what its context cost to establish, whatever the cache did with it, so siblings dispatched with identical prompts must open at the same number. Two agents join one cohort when they agree on model *and* opening, which is exactly the condition under which they could have shared a cached prefix. Six readers dispatched together should appear as one cohort of six; appearing as six singletons means a byte varies ahead of the shared block, and the openings say how much. A large `tail` write is ordinary by contrast: content behind the prefix was going to be written anyway.
**Reads** `/tmp/claude-*/<project-slug>/*/tasks/*.output`. **Writes** — **Exit** always 0.
```
--session S  one session, by slug or id prefix — what tells two concurrent
             sessions apart when both are dispatching
--all        every session this project has transcripts for, not just the newest
--since T    only agents whose first request sorts at or after this: a duration
             back from now (30s, 5m, 2h, 1d) or an ISO date or stamp [no window]
--tasks DIR  the task-transcript directory [the newest session for --root's
             project that has any]
--root --json --toon --pager
```
**Emits** five sections: `scope`, `agents` (one row each — type off `attributionAgent`, model, effort, TTL tier, `opening`, the `tail` written after it, terminal context `ctx`, `saved`, and the agent's `first` and `last` request stamps), `preamble`, `cohorts`, `warmth`.
**Note** **requests are counted per `requestId`, not per record.** A request emits several usage records as it streams and the early ones carry a partial `output_tokens`; counting records ran `reqs` two to four times high and every sum with it.
**Note** **cohorts and preambles group by agent type**, not by model alone. Opening very nearly decides it — two types have different system prompts and so cannot open at the same total — but "very nearly" is not a grouping rule, and pooling two types' turn-1s reports a variant count for a batch that was fine.
**Note** the saving columns: `saved` is the prefix the warm siblings read instead of writing, `originated` what the batch made once, `if_all_cold` what it would have cost with no sharing, and `asymptote` the limit `(N-1)P / (N(P+W))` tends to, which is `P/(P+W)`. **An asymptote and not a ceiling, because it is never reached** — `(N-1)/N` is never 1, so even a batch where every sibling after the first opened warm reports a shortfall against it, and that shortfall is arithmetic rather than a defect to chase. `own` — the mean per-agent work beyond the prefix — sits beside it so the ratio is checkable rather than asserted: an asymptote near 50% means `opening` and `own` are near equal, which is a fact about the pass being measured and not a property of the arithmetic.
**Note** `ctx` is the agent's terminal context, which is the *shape* of the per-agent figure the harness itself reports — a terminal measure, not a sum, since an agent's context is re-sent every request — and lands within ~0.6% of it. It is **not** claimed as a reproduction; the exact composition is not established.
**Note** **`chars` is the one column not in tokens, and is signed because it is what a turn adds.** No per-message token count is recorded anywhere: `opening` covers the system prompt and the whole preamble undivided, and every preamble turn arrives before the first request, so there is no earlier measurement to diff against. A per-turn token figure would be a `chars/4` estimate beside nine measured counts, or a controlled experiment nobody has run — two agents of one type whose preambles differ in exactly one known way, with no memory write in between. That control matters: between two real batches the prompt shrank by 1,043 characters and the opening rose 154 tokens, because a reader had written a memory file and the memory index is in the system prompt.
**Note** **`preamble` is where a broken prefix is actually visible.** It is one row per user turn ahead of the first reply — the whole of what a launch order can affect — carrying that turn's label, its size, and how many *distinct* variants the agents in scope had of it. A cohort table says openings disagree; this says which turn disagrees, and since a prefix ends at the first differing byte, the first turn with more than one variant costs everything after it. A preloaded skill labels itself (`skill: read-moll-page`), so the question "what is the 21k?" is answered without opening a transcript.
**Note** **the rows are ordered by `first`, not `last`.** Launch order is what the table is read for — one member of a cohort writes the shared prefix and the rest read it, so who opened first is who paid, and a stagger is a claim about `first` alone. Ordering by `last` let duration talk over launch order: an agent that opened first and ran long sorted below one dispatched minutes after it. Both stamps are in the row, so the gap between them is the agent's own span.
**Note** **the TTL is read, not assumed.** A request records which tier its write bought under `usage.cache_creation`, so `warmth` reports the measured clock rather than a constant taken from the documentation. Where agents in scope disagree the shortest wins: a prefix is warm only while every witness to it still is, and the optimistic reading would send a batch at a cold cache. `TTL` survives only as the fallback for a scope that wrote nothing, and says so in the row.
**Note** the system prompt is **not** in a transcript. It is inferred as `opening - preamble` and never reported as though it had been read, which is why `opening` is the figure this verb leads with.
**Note** **a cohort of one claims nothing.** A lone agent had nobody to share with, so its opening is reported as `singleton — nothing to share` rather than as a shared prefix. Calling one agent's opening a shared prefix is the fabricated measurement this verb exists to catch, and it would be a poor thing for the verb to commit itself.
**Note** `missed` is `(agents - 1 - warm) x opening`: one member of a cohort must always write the prefix, so `agents - 1` reads is the ceiling. The gap is what staggering the first launch buys, and it is zero when every sibling after the first read what the first wrote.
**Note** **`warmth` is the only pre-flight signal there is.** The cache cannot be queried, so the age of the last request against the five-minute subagent TTL is the whole of what can be said — subagents cache on that clock even where the parent session holds a longer one.
**Note** **an unparseable `--since` is a usage error, not an empty result.** Comparison is lexicographic, so `5m` sorts *after* every ISO stamp there will ever be: before the relative form was supported, passing it filtered every agent out and printed an empty table at exit 0 — a wrong answer wearing the shape of a right one. The stamp is also truncated before comparison rather than carrying a `Z`, since transcript stamps have fractional seconds and `…:00Z` sorts after `…:00.5Z`.
**Note** the session is discovered from `--root`, whose path Claude Code slugs into the transcript directory name; the newest session *that has transcripts* wins, since a session that dispatched nothing has a `tasks/` directory too and picking it would report the empty batch as the batch.

### agents transcript AGENT [AGENT ...]
**Does** one named agent's requests in order, with what each one added to its context and where that came from. **`added` is the column**: a request's whole context is `in + read + write`, so the difference between consecutive requests is what arrived between them. Reading down it catches a duplicated block, which no per-agent total can — a contract re-injected on resume showed up as +14,916 on request 2 of three separate readers, identical to the token, and was invisible in every summary. `note` and `detail` name the arrival from the tool the *previous* request called, since its result is what the growth is made of: `read raster moll-046.png`, `ran command … zoom moll-046:15,33`, `write file`. `via` says whether that growth was paid for — `read` is a context served whole from cache, `write` is the only kind that costs.
**Reads** `/tmp/claude-*/<project-slug>/*/tasks/*.output`. **Writes** — **Exit** always 0; 2 if no transcript matches an AGENT.
```
AGENT...     agent id, or its leading characters — what `usage` prints
--tasks DIR  the task-transcript directory [the newest session for --root's
             project that has any]
--root --json --toon --pager
```
**Note** an AGENT matching nothing is a usage error, not an empty table: a mistyped id and an agent that never ran are different facts and only one of them is the caller's to fix.
**Note** request 1 has no predecessor, so its `added` is the opening itself — the system prompt and the whole preamble in one sum, undivided because nothing in the record divides them.
