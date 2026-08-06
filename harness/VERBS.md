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
rather than a shell loop. Three actions are singular and say why in their entry:
`tei context` (the payload is one page's collation prompt), `proposal set` and
`proposal replace` (their flags name one entry of one proposal). A flag that names
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
**Note** **`toc_window_folio` names which witness centred the window**, `{folio, witness}` over `expected_folio` / `running_title` / `none`. `toc_window` filters ToC entries by distance from the folio, and `expected_folio` is a prediction from the preceding *collated* page — so at the front of any run it is null, the distance test never fires, and the window falls back to `believed_open`, itself a fold over collated pages and likewise empty. It came back empty, no heading could match an entry not in it, and the pass turns every unmatched heading into an unresolved comment: `1-075` opens the trade chapter with two headings and produced neither. The page's own running title now centres it instead — better evidence anyway, since the page saying what page it is outranks a neighbour's arithmetic. **`expected_folio` is deliberately not filled from it**: that is the prediction, and writing this page's folio into it would manufacture the second witness and leave `<pb>` checked against itself. `witness` is what separates an empty window meaning "nothing near this folio" from one meaning "no folio to be near".
**Note** `figures_on_page` is `{n, caption}` — one record per **printed figure**, `n` being the number the caption itself prints. **Placing a figure is not the collator's competence**; finding where the prose says "(Fig. 87, a)" is. So the pass writes `<figure n="87"/>` and the *build* joins that to zones through `data/readings.md`, and nothing about geometry reaches the model. Two earlier shapes failed the same way: raw `zone_id`s (an opaque string a model cannot check, with the `GraphicZone`/FigDesc pairing left to it — on `1-151` that produced a correct anchor plus a permanent known-false orphan comment about the caption zone), then a page-local ordinal over pictures, which is worse than it looks because **the zone count is not the figure count in either direction** — `1-207` sets fig. 87 *a, b, c* in two boxes with `a` and `b` sharing one, and several boxes routinely tile one irregularly-shaped figure. `n` is null where the caption prints no number and where a figure has no caption at all (`3-006`, `3-007`); neither is an error and neither is referenced from the text. `bbox` went because nothing read it — the collation output carries no geometry.
**Note** `tier1_terms` is `{index, line, text}` — the Tier-1 tokens on this page a human has already keyed, from `gt/ocr/` and never from `mz/` or the view. The pass names one by `index` rather than retyping it; `tei expand` writes the ratified string in. Empty on the 802 pages with no ground truth. What counts as Tier-1 here is `detectors.NON_ENGLISH_HITS` (an inventory glyph or a straight apostrophe), not `INVENTORY_CHARS` alone, which omits U+0027 — the spirant and pause mark, one keystroke from the U+2019 in `LOOKALIKES`. The list is a **floor**: an unmarked ASCII inventory member (`c`, `s`, `j`, `x`) is undetectable and has to be typed, which costs little for a structural reason — what makes a token undetectable is having no marks, and what makes it dangerous to retype is having marks. One token per handle; all 30 spans in committed TEI are single tokens, so a range is built against a real instance rather than guessed at.
**Note** `ocr_lines` is `{index, text}`, and **`index` is what `@facs` cites**. It carried the ALTO `@ID` as `line_id`, a currency no harness verb accepts: `ocr zoom --only` has always taken the index, so acting on a citation meant translating it by hand first. Neither form resolves as a TEI URI today — there is no `<facsimile>` in the corpus — so nothing conformant was given up.
**Note** the three zones that can carry a folio (`context.APPARATUS_ZONES`) are dropped from **both** `catmus_draft` and `ocr_lines` — they leave the draft and arrive as `running_title` instead, so the information is restructured rather than discarded. Out of `ocr_lines` for a sharper reason than the draft's: that list is the set of `@facs` pointer targets, and a running head, a folio or a signature line is never in the TEI body, so citing one would be a mistake by construction. A **caption** line is dropped from the draft only, since it stays citable.
**Note** **one of the three singular actions.** The payload is one page's collation prompt, built to be handed to one model for one page; a merged stream of them is not consumable by the thing it exists for.
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
**Note** **every page carries one `<!-- opens: … -->`**, immediately after `<pb>` and ahead of any other comment, from the closed set `indented` / `flush to the measure` / `no witness`. It is the seam's third witness — the first line's indent — and the only one that does not survive into the TEI: the previous page's tail is in its own file and this page's opening text is in this one, while the indent is on the raster. The collator has the image; the coordinator writing `@part` does not, and re-deriving it means reopening a page to answer a question already answered. **Witness, not verdict**: `@part` is the verdict and `tei seam` is the only thing that writes one, so the two are not one fact stated twice. Checked as the first *comment after* `<pb>` rather than the first node — a comment is not an element, so the "pb is first" rule steps over one placed before it, and starting the walk at `<pb>` is what keeps a fixed form from quietly becoming two. `no witness` is in the set because a heading or a plate has no measure to judge against, and left to the comment's absence that answer is indistinguishable from a collator that never looked.
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

### tei queue REF [REF ...]
**Does** validates a batch, writes it to the collation claim queue, and prints the **one prompt every collator of the batch gets** — the block between `<!-- claim:begin -->` and `<!-- claim:end -->` in `.claude/skills/transcribe-page/dispatch.md`. That prompt names no page: each agent takes its own ref with `tei claim`.
**Reads** `dispatch.md`, `.claude/agents/collator.md`, `ocr/`, `gt/ocr/`, `tei/`, `gt/zones/_exempt.lst`.
**Writes** `tei/_queue.txt`, and clears `tei/_claims/`. Prompt to stdout as plain text, everything operational to stderr.
**Exit** 0 with a prompt; 1 when any page in the batch is not a candidate, and the message names the remedy.
**Note** four refusals, every page checked before any is queued: a ref named twice; **`tei/chukchi-PP-NNN.xml` already present**, which would overwrite committed work and feed the pass's own "re-read your output once" the *previous* run's file; nothing at `ocr/chukchi-PP-NNN.xml`, naming `ocr predict`; and a page marked exempt. A missing `collator.md` is refused too — the agent body *is* the system prompt, so dispatching without one sends agents at pages with no rules.
**Note** **an uncollated predecessor is deliberately not a refusal**, and that is the whole design. It was an implicit one while the pass ran serially, because `tei seam` refuses without a predecessor; moving the seam to the coordinator is what lets a batch go out in any order. The price is `prev_tail` and `expected_folio` null on every page but the first — see `tei reservations`, which says so rather than letting a clean report imply otherwise.
**Note** **send it unedited and identical to every collator**, staggering the first launch about ten seconds. Identity of the first turn is what caches; a ref written into the prompt costs every sibling the shared context, which is why the ref arrives from a tool call instead.
```
--note TEXT  a sentence appended to every page block in this batch; per-page
             notes want separate queue calls
--root --json --toon --pager
```

### tei claim
**Does** takes the next unclaimed ref off `tei/_queue.txt` and prints that page's block — the ref, which store its draft comes from, and the instruction to run `tei context`.
**Reads** `tei/_queue.txt`, `tei/_claims/`, `dispatch.md`, `ocr/`, `gt/ocr/`, `tei/`.
**Writes** `tei/_claims/PP-NNN`, stamped with the local time. Block to stdout as plain text.
**Exit** 0 with a block; 1 when the queue is empty or every ref on it is taken.
**Note** **takes no ref, and that is the point** — the page arrives from a tool result rather than from a prompt that would then differ between siblings. `O_CREAT|O_EXCL` is the whole lock, shared with `ocr claim` rather than reimplemented: the kernel decides which of several agents created the marker first, so there is no window between the check and the take.
**Note** the block does not embed `tei context`. It names it, because `context` is built fresh per page and is the one action in the CLI whose payload is a single page's prompt; copying it into a claim would freeze it at queue time.
```
--root --json --toon --pager
```

### tei reconcile REF [REF ...]
**Does** what the batch came back with — each named ref `collated`, `CLAIMED, no TEI` (an agent took it and did not come back), or `unclaimed` (nobody took it).
**Reads** `tei/_claims/`, `tei/`.
**Writes** —
**Exit** 0 when every named ref is collated; 1 naming those that produced nothing.
**Note** three states rather than two, for the reason `ocr reconcile` gives: "no deliverable" has two causes at scale and only one is worth chasing. The state words are per-track rather than derived, so this pass existing did not rename the reading pass's report.
```
--root --json --toon --pager
```

### tei reservations [REF ...]
**Does** pools the open comments a batch left in its pages and classifies each — the collation analogue of `proposal marks`. Rows are `{ref, class, text}`.
**Reads** `tei/`.
**Writes** —
**Exit** always 0. Measurement never gates.
**Note** **read the rows against each other, not one at a time.** One page adrift is a page to re-read; all of them leaning the same way is the contract or the spec, not the collators. Reading twenty page files individually is twenty separate judgements, which is exactly what a per-page pass cannot do for itself.
**Note** **`opens:` is excluded.** It is on every page by construction, so pooling it would bury the real rows under itself, and it records an answer rather than a question. `tei seam` is what reads it.
**Note** **the report says what it could not check.** In a dispatched batch `expected_folio` is null on every page but the first, so `folio_disagrees` cannot fire — not because the folios agree but because nothing compared them. A silent clean report would be a confident output with the error signal removed, so the verb names the blind pages and points at `tei ledger`, which folds the whole run at once.
**Note** the classes come from the comment forms the collation contract fixes verbatim, and the two copies have a gate: `test_reservations.py` asserts every pattern matches a form the agent body states. It checks that direction because an unmatched *contract* form lands in `other` and is visible, while an unmatched *pattern* is dead surface nobody would see.
```
--all        every collated page in tei/
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
view over every OCR store, **and the `gt/lines/` overlay**: a page's lines are
the store's plus the boxes a human drew over ink the segmenter left unboxed.
`restore` is the only action that writes `gt/ocr/`, under `--commit`; `edit`
writes the overlay, and geometry only.

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
**Reads** the `--store` store, or the view, `gt/lines/_ink_exempt.json`.
**Writes** —
**Exit** always 0.
**Note** **`annexed` is the count of ruled bands a human has said this line's box is short of** — a `covered_by` ruling naming this index, non-zero meaning the line is *printed wider than its box*, so key the whole of what the paper prints there. `PAD_X` is sized to carry it: every crop runs past the box far enough to show a strangled folio whole, which is why there is no flag to ask for that and no aim to guess. It is on the line because that is where it is needed: the ruling lives on the band and reads off `ocr gaps`, but a reader keys from this table and crops from `sheets`/`zoom`, so the one view that mattered was the one that stayed silent. `1-073` line 1 is 11 px wide and holds `5` where the page prints `51`; its reader recovered the second digit from the under-30px strangulation heuristic alone, while the human ruling saying the same thing sat unread.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds
--full      include baseline and polygon points [off]
--root --json --toon --pager
```

### ocr gaps [REF ...]
**Does** bands of ink no TextLine covers — the dropped-line detector. A band is a place to look, not a verdict.
**Reads** the `--store` store, or the view, `scans/`, `gt/fig/`, `gt/zones/`, and both `_ink_exempt.json` layers.
**Writes** —
**Exit** always 0.
**Note** `--all` is the corpus dropped-line sweep, at a raster read per page. It reads through the view unless `--store` narrows it, which is `ocr pages`' rule — a machine-read page is workable, and this verb neither gates nor publishes a rate.
**Note** each band reports the `zone` containing it, or empty for none, resolved by overlap against `gt/zones/`. A page with no zoning yields no containment and every band reads out-of-zone — the honest degradation, not a gate; it is `ocr edit` that requires zoning, not this.
**Note** **authority runs downstream only, and `layer` names whichever ruled.** Zoning is the first stage of accounting for the page's ink and recognition is the last — `ocr blot` over a finished page should leave a blank leaf — so `gt/lines/_ink_exempt.json` settles any band, in a zone or not, while `gt/zones/_ink_exempt.json` settles only what is already outside every zone. The upstream direction stays shut: one file used to serve both, so a band ruled "scanner smudge" while zoning — a claim about what the *zoning* need not cover — also stopped this check from ever reporting that strip again, and a folio dropped inside a `RunningTitleZone` is what that hid. Routing *both* directions by zone was the opposite error and left bands no editor could reach, since the two checks do not see the same ink: `zones.uncovered_ink` masks coverage by row, this masks by box, so a band beside a zone rather than below it is visible only here. `1-034`'s two were ruled in `ocr edit` and sat inert with nothing saying so.
**Note** **Flagged, never suppressed** — an exempted band still reports, carrying `exempted`, its `note` and its `layer`, because dropping it would make this the one place a wrong call could hide. Earlier this verb read no ruling at all, and an OCR-side reader re-adjudicated from the raster a band a human had already settled.
**Note** a **corrected** band is the one thing that does drop out, since the box now covers the ink — so a `pages_corrected` table reports each correction with its zone, position, size and whether anything is keyed in it. Without it a page that has been worked and a page nobody has opened both report nothing, and silence is what this detector exists to break. **The row carries geometry because a count sends the reader hunting**: it reported `corrections: 1` and nothing more, so `1-039`'s reader knew a box existed but not where, and spent half its zooms crossing the page for a line the store could have named — reading the renderer's own index label as printed ink on the way. `keyed: ""` is a box waiting to be read; the zone usually says what it is, and a narrow correction in `RunningTitleZone` is a folio.
**Note** **a ruling carries which of two dispositions settled the band, in `reason`.** Without `covered_by` it is `not_type` — the ink is not printing. With it the reason is `covered` and `covered_by` names the line whose box strangled the ink, so the band is not a dropped line because it is not a *separate* line: a clipped folio is the standing case, its box being an identity and an anchor rather than a measurement. One disposition used to carry both claims, and the note people wrote said the opposite of the heading it was filed under — `1-051` still reads "half of undersized folio line" under a ruling meaning "not type". There is deliberately no way to resize a line instead: the extent is not what makes it that line.
**Note** **`covered_faults` is the half `not_type` could never have.** A ruling that ink is not printing rests on the paper alone and nothing here can weigh it; a ruling that ink is covered by line N names something the store can be asked about, so it is checked — `no_line` where the index is not in the store, `empty_line` where it is there and keys nothing, which means the reading really is missing and the exemption is hiding what it claims to account for. Reported after the bands, never gated, because measurement never gates. What it cannot check is whether N's text is the *right* text; that is a reading, and the strangulation rule in the reader contract covers it.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds
--jobs N    worker threads; 1 runs serially and builds no pool [cores, capped]
--root --json --toon --pager
```

### ocr edit [REF ...]
**Does** the line-correction editor in the browser — the human end of `gaps`, and `zones edit`'s sibling one stage down. Adopt a band as a line, rule it not type, or rule it already keyed by a line whose box strangled it; the verdicts in one sitting, because deciding between them is one act.
**Reads** the `--store` store, or the view, `scans/`, `gt/zones/` and `gt/lines/` with both `_ink_exempt.json` layers, `gt/fig/`, `data/zones_config.json`.
**Writes** `gt/lines/` and `gt/lines/_ink_exempt.json` on save. **No `--commit`** — the save click is the human act, the same contract `zones edit` and `ocr review --serve` have.
**Exit** 2 if nothing supplies a start page.
**Note** **it draws and never keys.** A recovered line's text is adjudicated in `ocr review` like any other line's and written by `restore`; duplicating that machinery here would be a second place a reading could be originated, and this store exists on the argument that its writer cannot originate one.
**Note** **a box in no zone is refused, and the refusal names `zones edit`.** Ink no region covers is a defect in the *zoning*, not a line this editor can adopt — recording a line inside no region would leave the region missing. It is also what keeps the two ink checks disjoint. A page with no zoning at all is refused outright: line correction comes after zoning, which is a stage-order invariant rather than a statement about this corpus.
**Note** `b` toggles the blotted view, rendered on demand with **both** ruling layers painted, so what is left is what nobody has settled. That is deliberately the opposite of `ocr blot`'s default, which stays an independent witness.
**Note** **every colour and every key is `data/lines_config.json`'s**, `data/zones_config.json`'s shape and validated the same way — a key bound twice, a layer the editor paints by name and the config does not declare, a `zoom_step` of 1, are each refused at load rather than met as a dead key three pages into a sitting. The overlay's stylesheet and the panel's key list are both *generated* from it, so a rebound key moves in one place and the help cannot lie about the tool.
**Note** **the panel is a control surface, not a legend**: every action's row does the thing when clicked, so it is reachable without knowing its shortcut or having kept one. A key may be set to `null` — the shortcut comes off the keyboard, the control stays. Rows whose action has nothing to act on (delete with no selection, withdraw with no ruling) draw dimmed and stay put, since a control that comes and goes is harder to learn than one that is visibly not applicable.
**Note** zoom is the instrument, not a convenience: the subject is a mark ~40 px wide on a 2824 px leaf, which at fit is some 17 screen pixels — too small to tell a numeral from a printed rule. `frame_band` jumps straight to the first undecided band at a legible step.
**Note** a ruling can be **withdrawn**, as in `zones edit`, and the page's rulings are listed with their reasons beside the keys — each showing *which* disposition it is, not only its note, since two rulings that silence the same band for opposite reasons must not render alike. A reason recorded once through a prompt and never shown again is a record nobody can check, and the whole argument for requiring one is that a year later it is all that separates a ruled artifact from a hidden mistake.
**Note** **`cover_band` picks the covering line by clicking it, never by typing an index.** The overlay draws no line numbers, so an index typed into a prompt is a number a human cannot read off the page — they would be guessing, and a guessed reference is the silent wrong answer the field exists to make checkable. So the key arms the pick, every store line lights up in `line_pick` carrying its index and its text on hover, and the click settles it; Escape cancels. It is the editor's only mode, held for exactly one click, because a mode a human can forget they are in is how a drag becomes a ruling.
**Note** several refs are the walk — `zones edit`'s rule: the session opens at the first and steps through the list, so one ref is a page to *start at* rather than the only page reachable. `--all` is the store's pages and **not every scan**: this corrects lines a segmentation missed, so a page with no ALTO has nothing to be missing from and would open an editor with nothing in it. A page the store cannot answer for is skipped by `--unsettled` rather than crashing it.
**Note** **`--unsettled` is a filter over `--all`, and deliberately not a saved work-list.** The obvious itinerary here is "the pages `gaps` still leaves live", and writing that to an `.lst` would freeze it: every page worked makes the file wrong, and a stale work-list is a claim about the corpus that nothing checks. It is measured when asked instead — a raster read per page, the same cost the census pays — so the answer is true when it is used. `l` in the editor opens the same view as a table, measured per row on request, with `?` until a row is fetched because blank is indistinguishable from none.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds — the editor walks them with the arrow keys
--unsettled  narrow --all to pages still carrying a band nobody has settled
--port N    port for the editor [8733]
--jobs N    worker threads for --unsettled; 1 runs serially [cores, capped]
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

### ocr sheets PP-NNN [LINES ...]
**Does** labelled contact sheets, index in the margin, nothing downscaled. Emits the sheet/lines map, not the line table.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/sheets/` (derived), or `--out`.
**Exit** always 0; exit 2 for a second ref, or `--out` with more than one ref.
**Note** no `--all`, for `crops`' reason. **The line selection is the argument, not a flag**: `ocr sheets 1-048 7,20,22-26` or `ocr sheets 1-048 7 20 22-26`, the whole page if none is named. It was `--only`, which read as a filter over a default of "the whole page" when the whole page is the thing nobody wants, and which invited the plural positional beside it — where the same indices name unrelated lines on the next page, since a line index is an *identity* and not a position. One ref, then the lines on it. A second token spelled like a canonical ref (`1-049`) is refused rather than read as the range 1–49. Sheets are named for the lines on them (`lines-11-14.png`), so two selections over one page cannot overwrite each other and an overlapping one reuses what it agrees with.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--per-sheet N lines per sheet, upper bound only [40]
--height N    max sheet height in px [1960 — the tallest a ~1900px-wide sheet can
              be and still fit the 4784-visual-token ceiling without being
              resampled on delivery]
--out PATH    write elsewhere [review/PP-NNN/sheets]
--root --json --toon --pager
```

### ocr calls REF [REF ...]
**Does** every image the page's reading has opened, in order, each zoom with its stated reason — plus the counts that make a raw total mean something.
**Reads** `review/PP-NNN/calls.jsonl`, appended by `numbered`, `sheets`, `crops` and `zoom` as they run.
**Writes** nothing.
**Exit** always 0. Reports; never gates.
**Note** **the tally cannot come from the reader, which is the whole reason this exists.** Every report in the batch that prompted it understated its own image ladder by two to five times, and none of them was lying: a report is written once the answer is known, and by then the search that produced it no longer feels like a search. `1-039`'s said the folio needed "no zoom beyond confirming the digit shapes" over a directory holding five crops of it, four margin-widened, two at 4×; `1-043`'s said "roughly 14 targeted zoom calls" over 32. A reason typed at the moment of the call survives that — a count recalled at the end does not.
**Note** `repeats` is the figure to read first, because a crop total alone is not interpretable: seven crops over seven lines is a careful page, seven over two is a reader that could not frame what it wanted. It counts calls naming a line an earlier call already named — the re-aim signature. `no_reason` should be 0, since `--reason` is required; a non-zero one means the ledger predates the flag.
**Note** the ledger is outside `paths.DERIVED`, so `ocr clean` takes the images and leaves the record of having opened them. Gitignored under `review/*/*.jsonl`. Append-only: a ledger the measured party can edit is not a ledger.
**Note** `--all` emits the per-page counts and **not** the series, which is the view that shows one reader as an outlier rather than as a number; pooling every call of every page into one table buries that in a few thousand rows. Name a ref to get its series.
```
--all         every page that has a ledger, counts only [omit: the refs named]
--root --json --toon --pager
```

### ocr zoom PP-NNN [PLACES ...]
**Does** magnified lines — overlapping strips at an integer scale, packed into as few sheets as the height budget allows.
**Reads** the `--store` store, or the view, `scans/`.
**Writes** `review/PP-NNN/zoom/` (derived), or `--out`.
**Exit** always 0; exit 2 for a second ref, for `--out` with more than one ref, for `--zoom` other than 2 or 4, for a missing `--reason`, and for any place naming a line in an apparatus zone.

**A line in `FOLIO_ZONES` may not be zoomed at all.** The running title, the folio and a signature mark are plain type in a labelled zone, and nothing a crop says about them was not already legible on `ocr numbered` — every other zoom on a page is a question about a letterform and this one never is. It has still been the pass's steadiest drain: four pages across two batches spent **42,620 tokens** hunting a folio at the ceiling (`1-051` 13,140 · `1-045` 11,261 · `1-054` 10,505 · `1-047` 7,714), one of them because a crop cut the number in half. The brief has told readers not to since the second batch and they kept doing it, which is the difference between a rule and a suggestion. **Zone-scoped, not line-scoped**: which of the three zones a page's folio landed in is exactly what a reader cannot know in advance, so a rule keyed to "line 1" would miss the pages where it is not. One apparatus place refuses the whole call rather than dropping it silently — the call is one image, so a partly-served request returns a crop nobody asked for. It does **not** claim to prevent a misread folio: `1-063` keyed `141` for a folio reading `41` without zooming at all.
**Note** no `--all`. **The places are the argument**: `ocr zoom 1-048 11@70 13@40 23@60` is one ref then the places on it, comma- or space-separated. It was `--only`, and a flag invited the plural positional beside it, where the same indices name unrelated lines on the next page — a line index is an *identity*, not a position. A second token spelled like a canonical ref is refused rather than read as a line range.

**`--zoom` offers two steps, not a range, and the first call on a page reports what each one costs there.** It reported on *every* call until the arithmetic moved into the claim block: at 600–2,000 tokens of stderr apiece that was, measured over eight readings, the largest avoidable line item after the fixed contract. What still prints per call is what is about that call — a span narrower than one crop, and the ceiling warning at 4×. A ceiling alone left 1 and 3 legal and readers used them as places to hesitate; measured over one six-page batch, **236 crops were taken and not one was at the default 2×** — every call overrode it, 226 to 4× and 10 to 3×. Two of those pages were never finished: their readers spent 80 turns at two turns a crop (issue, then read the image) and had none left to write with. So the middle rungs are gone, and what replaces the prose is arithmetic from the page's own median line: at 2× one crop returns ~38% of a line and four fit a sheet; at 4×, ~19% and two. A whole line is 3 strips at 2× and 7 across two sheets at 4×.

**`--reason` is required, and it is required of a model rather than of a person.** Nothing about any single crop in that batch looked wasteful; the waste was only visible as a count, after the page had failed. A reason makes the sequence legible in `agents transcript` — where re-aiming a miss reads differently from asking the same question louder — and asks the caller to have a question before it has an image.

**`--zoom` is capped at 4 by the parser, not by prose.** At 300 dpi a character stands about 30 px, so at 4× every ink pixel is already a 4×4 block and there is no source detail left: what a higher number returns is the resampler's opinion, not the paper's. That was a rule in the pass doc for months and was broken anyway — `2-245` spent ten calls at 6× on a shape question, and the first reader dispatched under `queue`/`claim` went to 6× nine times and settled a laryngeal identity on one of them. A confident answer at a magnification carrying no more information than the one below it is worse than an unresolved one, because nothing downstream re-opens it. A doubt that survives 4× **is** the finding: put it in `note`.

**A span is widened, never obeyed literally, and that is deliberate.** A strip is a fixed `window` of source pixels and the sheet is padded to `--client-w` regardless, so a span narrower than one strip renders inside white space you have already paid for. It is therefore expanded symmetrically to fill the window — sliding rather than shrinking at a line edge — and then both edges snap outward to the nearest blank pixel column, bounded, so **no glyph is ever cut**. The rendered span, not the requested one, is what the label and filename record: two requests that widen onto the same region are one picture and must share one file.

This exists because clipping does not cost a bad image, it costs a *re-call*. `2-134` took ten zoom invocations, most of them the same doubt re-aimed after the previous span cut the word in half. Widening absorbs a few points of aiming error for free; it cannot absorb twenty, and a doubt that needs *locating* rather than resolving belongs at `ocr sheets --only`.

**`@P` names one point and is the form to reach for; `@LO-HI` names a range.** A range asks for two numbers about a word whose extent the caller cannot see yet, and the second number is the one that goes wrong: a span too narrow is widened to the window anyway, and a span off-centre misses and costs a re-call. `1-041`'s reader spent three crops framing one word — `23@45-65`, then `23@70-90`, then `23@60-75` — where `23@60` is one. A point asks only where the word *is*, which is the part a reader can actually see from a composite, and the window is a fixed width of source pixels regardless. A range narrower than one crop is reported back as such, with the figure it was widened to.

**The edges are exact, and that retires the guess entirely for the two commonest doubts.** A span is slid rather than shrunk at a line boundary, so `N@0` is the head of the line and `N@100` its tail *whatever the line's length* — no estimate, no re-aim. A footnote reference marker is `@100`; its opener at the foot of the page, and a folio set hard against the left margin, are `@0`. These are the positions the pass returns to on nearly every page, and until they were written down readers were arriving at them by trial: `1-039`'s folio took five crops, four of them margin-widened, on a line whose number sits at one end of a 62px box.

**`@LO-HI` names a percentage of the line's width, and it is where the saving at this rung is.** A doubt is about a mark, not a line, and a mark is a few percent of a full measure — `3-063`'s footnote openers sat in the first characters of their lines, so `42-43` rendered four strips apiece of which three bore on nothing, where `42-43@0-25` renders one each. Percentages, not pixels: the caller is reading a report, not measuring a raster, and a pixel span would demand a measurement nobody has taken. **One line may be named at several places and renders one crop each** — `1@0 1@100` is a line's two ends, one call. That was refused for a while on the ground that unioning two spans returns the whole-line hull, which is true of a union and was the wrong conclusion: two places are two pictures, nothing is merged, and three readers in one batch each typed exactly this and were told to pick one and come back. A whole-line request absorbs the places on that line, since it already contains them. `ocr sheets` refuses a span outright — it shows whole lines and has nowhere to honour one.

Each sheet is named for the lines it holds and the settings that drew them — `zoom2-26-27.png` is lines 26–27 at `--zoom 2`, `s` marks `--smooth`, and a line whose strips straddle two sheets takes a `-b` suffix. **Two selections over one page therefore cannot overwrite each other**, and an overlapping selection reuses the sheet it already agrees with. They could: sheets were numbered `-001` upward per call, so a second `--only` replaced the first's images while the first's returned index went on naming them — three parallel calls yielded one call's pictures and three reports of them. Finer overrides (`--window`, `--overlap`, `--client-w`, `--height`) are *not* in the name and do reuse it.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--reason TEXT why this crop, in a few words (required)
--zoom N      display px per source px, as delivered: 2 or 4 only [2]
--window N    source px per strip [derived from --zoom; overriding upward breaks the scale]
--client-w N  px the reading client shows per image [1450]
--overlap N   px shared by consecutive strips [60]
--height N    max sheet height in px [1600]
--smooth      Lanczos instead of nearest-neighbour [off]
--out PATH    write elsewhere [review/PP-NNN/zoom]
--root --json --toon --pager
```

### ocr blot [REF ...]
**Does** the page with every line box and figure zone painted out, so what remains is uncovered by construction. The visual counterpart to `gaps`. See `zones blot` for the other recipe.
**Reads** the `--store` store, or the view, `scans/`, `gt/fig/`; both `_ink_exempt.json` layers under `--exemptions`.
**Writes** `scans/w-blotted/` (derived), or `--out`.
**Exit** always 0; exit 2 for `--out` with more than one ref.
**Note** `--all` skips a page whose blot is already newer than its ALTO, and `--force` repaints it; naming a page always repaints it, since naming it is the request. **The mtime test is honest here in a way `zones blot`'s could not be**: this paints boxes read out of the ALTO, so an ALTO newer than the blot is exactly the change that matters — where a figure ALTO corrected after a `zones blot` leaves a raster whose staleness nothing can see, which is why that verb has no such test at all.
**Note** **`--exemptions` is on by default, because the standard this measures against is a blank leaf.** Accounting for the page's ink is what the recognition stage is *for* — zoning is the first pass at it, this is the last — so a finished page has nothing left that is not a line, a figure or a ruling, and all three are painted. It was off for most of this verb's life on the argument that a bare page answers independently of anybody's judgement, which is true and is why `--no-exemptions` remains; but it argued for the wrong default, since a view whose success condition is "blank except for some things" cannot be read at a glance, and reading it at a glance was the whole point of a picture over a threshold. **Near-blank, not blank**: scanner speckle and the odd printed rule survive, the eye discounts both and a threshold cannot, which is why nothing here scores the leftovers. Ruled bands paint **full width**, which is exactly the reach a ruling has in the check this illustrates — it is a `y` band with no `x` extent, matched on the band's midpoint alone.
```
--store {gt,mz}  which store to read [omit: the ocr/ view]
--all       every page the store read holds
--force     repaint pages whose blot is newer than their ALTO [off — only --all skips]
--out PATH  output directory [scans/w-blotted/ — corpus-level, unlike the other image actions]
--exemptions  also paint the bands a human ruled, both layers, so a finished
              page blots near-blank [on]
--no-exemptions  the bare page: lines and figures only, so what remains is
              uncovered by construction and no ruling can hide ink here
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

**The entry boxes are set in Brill by default, and the type is a knob.** A review is an hour of comparing a crop against a box directly under it, so the face is an ergonomic parameter: the Memoirs are a Brill, and matching the entry to the printed face makes that comparison two renderings of one design rather than a translation between two. The fallback stays DejaVu Serif, which keeps its own argument — a single-storey `g` with a short descender, so a U+0323 under the bowl stays legible where a tighter face crowds it, which is the one thing Brill is worse at and worth knowing when a dot is the question. Nothing is fetched: the families are locally installed, and a remote webfont can substitute a face missing a glyph, which is the same failure as a box in a terminal — the text looks fine and is not what it says. `--font` is *prepended* to the fallbacks rather than replacing them, so an uninstalled name still renders.

**The three flags decide where a page starts; the page itself carries live steppers.** Size and box height move without a reload and persist per browser, because the right size for a face is something you find by looking at it beside a crop rather than by predicting it at a command line — and Brill runs small for its em, which is why a face change alone was not enough. `reset` returns to the values the server was started with, not to a constant, so it never quietly undoes a flag. `--box-lines` is a floor: the box still autogrows past it.

The header links to the **full page scan**, new tab — the crops say what a line sets and cannot say what is around it, which is what settling a speck or a dropped line needs. Served from `/scan/<ref>`, scoped to the session's refs like `/p/`; `--html` writes a relative path to `scans/` instead, since a browser will not follow `file://` from an http origin.
```
--serve   serve on 127.0.0.1, accept saves  }
--html    write review.html per ref         } mutually exclusive
--spans   bare diff: every span, ungrouped  }
--all     every page with a proposal and no decision
--port N  port for --serve [8731]
--font NAME     entry-box family, prepended to the fallbacks [Brill]
--font-size PX  entry text size [24]
--box-lines N   lines a box holds before it grows — a floor, not a cap [1]
--store {gt,mz}  which store to read [mz — the bare diff needs an independent
                 witness, and the view is not one once the page has ground truth]
--root --json --toon --pager
```

### ocr restore [REF ...]
**Does** writes adjudicated decisions into `gt/ocr/`, keeping the source geometry. Reports `mode=restoration` or `mode=revision`.
**Reads** `review/PP-NNN/decision.json`, the `--store` store, or the view, `gt/lines/`.
**Writes** `gt/ocr/` under `--commit`, **and relinks that page in `ocr/`** — the promotion is the write plus the relink, the same pairing `ocr predict` has for what it writes into `mz/ocr/`. The `view` field reports which store the view now names, `""` on a preview. Also `gt/lines/` for a page carrying corrections, which `corrections` counts.
**Note** **each line's text goes to the store that line came from.** A page's lines are the ALTO's plus `gt/lines/`'s, so this — still the only writer of ground-truth *text* — has two files to write: the ALTO's own lines by position, a correction by its `corr_` id, since the fragment is ordered by geometry and a box may have been nudged since. `gt/ocr/` never gains the corrected line; a second copy would be two records of one line, free to disagree. A correction with no decision is a partial restore exactly as an unadjudicated ALTO line is.
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
**Note** **a worker never writes to the terminal, and the summary says if it tried.** A `spawn`ed child inherits the parent's fd 2, and rich redirects `stderr` only for Python-level writes *in the parent* — so anything a worker emits lands between two frames of the progress bar, leaving rich's cursor accounting wrong and the count apparently frozen while `mz/ocr/` fills normally. It presented as two faults and was one. Each worker's fd 2 is now `dup2`'d to a file of its own before the models load (`dup2`, not `sys.stderr =`, because scipy, shapely and torch all have C in them), and the pool reads those files when it closes: `stderr_lines` and `stderr_log` in the summary, both empty on a quiet run, and the directory removed when nothing landed in it. Nothing is silenced — an empty capture is what makes a non-empty one worth reading.
**Note** **the recognizer runs under kraken's new polygon extractor, and every page in this store was produced that way.** `models/blla.mlmodel` predates it, so kraken warns "Enforcing use of the new polygon extractor for models trained with old version. Accuracy may be affected." once per worker process. Stated here because it is a property of the pinned model rather than of any page, and filtered in the workers by message — never by category — so the capture stays empty in the ordinary case while the next unseen warning still reaches it. `--jobs 1` raises it in-process, where rich catches it and prints it above the bar.
**Note** the sweep runs **4 workers by default**, not `MAX_WORKERS`: `min(process_cpu_count(), 4)`, then capped by free VRAM at ~1.4 GB a worker. A `--jobs` you type wins outright, including one that will not fit. Measured over 8 pages: 14.16 s/page serial, 5.14 with four processes.
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
**Does** cross-checks `resolved` against the codepoints `text` actually contains; flags a straight apostrophe, a dot-prone bare suffix, a note whose `class` is outside the closed set (doubt/semantic/print/layout/artifact) or absent, a line ending in sentence punctuation the draft does not end in, and — via `marks` — a rare form or a word spelled two ways against the store.
**Reads** `review/PP-NNN/proposal.json`, plus `gt/ocr/` and `data/marks_config.json` for the two corpus arms, and the `ocr/` view for the line indices.
**Note** **a line index the store does not have is a defect.** A proposal is keyed by the ALTO's indices and `restore` joins on them, so a key naming no `TextLine` is text with no box to land in — `restore` drops it, silently, and the reading is lost with nothing saying a reading was lost. It belongs in the reader's report and nowhere on disk: the line store is the upstream source of truth, a proposal is downstream of it, and nothing downstream may propose a line into existence. A human gives the band a box in `ocr edit`, and the index exists from then on. A top-level `segmenter_missed` block — the retired field that used to carry this inside the proposal — is itself a defect; an empty one `proposal fix` strips silently, a non-empty one a human must disposition. Resolved through the view **and the `gt/lines/` overlay**, so a page reads against `mz/ocr/` before a restore and `gt/ocr/` after, plus every correction already drawn — a keyed correction is therefore not an orphan, which is the whole point of giving the line a box. A page with no ALTO at all is skipped rather than condemned — absent is not wrong, and every line would fire on a clone whose view was never built. This cannot see the neighbouring fault, a stray reading appended to a *real* line's text (`1-037`'s folio); that one is the reader contract's.
**Writes** —
**Exit** 1 on a **defect**, on any ref — one dirty page fails the batch, which is the contract a gate must have or a batch would launder a failure. Never on an advisory alone, unless `--strict`.
**Note** **the exit code is also printed, as a closing `verdict` section** — `exit` and a `means` line naming why it is what it is. A groundtruth-reader is refused shell operators, so `$?` is a fact about its own work it cannot obtain, and it was spending turns on `proposal check REF; echo "EXIT: $?"` to get it — four such reaches across three readers in the `1-064`–`1-069` batch, a turn apiece against a budget of eighty. Relaxing the operator rule to admit one idiom would buy back one fact and give up the property that makes the surface auditable; printing the fact costs a row. And `means` carries what `$?` cannot: **the two exit-0 cases are not the same result** — nothing found, versus advisories found and deliberately not gated on — and only the second leaves the reader work to do, in the line's `note`. `corpus normalize` closes the same way, for the same reason and the same readers.
**Note** the corpus arms are `proposal marks`'s two **deterministic** ones, run over the single page so a reader catches its own slip before writing its report. `ratio` is deliberately not among them: one page is a poor sample and it is the arm that cannot decide, so folding it into a per-page gate would assert exactly what `marks` refuses to. A repeated form is one issue naming its other lines, not one issue per occurrence — a keyer's single habit is one fault. The prior is leave-one-out here too, so a revision is not checked against its own descendant. Where `data/marks_config.json` is absent (a fresh clone), the arms are skipped and the rest still runs.

**Overlap with the suffix check is wanted, not deduplicated**: a bare `-gɪn` yields both a `bare suffix` and a `rare form` issue on the same line. They reach one defect from different directions — a measured shape and a corpus share — and a second witness this cheap is what the governing principle asks for.

**Two severities, and only one of them gates.** A **defect** claims something *is* wrong and is the reader's to fix: `resolved` naming codepoints the text lacks, notation with no `resolved` at all, a straight apostrophe, an unpaired footnote marker, a note class outside the closed set or asserting nothing, an added line-final comma. **That last one gates only while the line says nothing about it** and drops to an advisory once the line carries a `note`: eleven instances across 93 proposals were on no page and in no draft, but a comma the recognizer genuinely dropped is a real correction, so the reader discharges it by looking and then either deleting the mark or saying what it saw. An **advisory** is measurement — a corpus share saying "go look": a rare form, a dot-prone bare suffix, a word spelled two ways. **A note with no class is the one advisory that is not measurement**, and it is an advisory anyway: the class only picks the badge, while the part that fixes the failure it exists for — a noted line is never dimmed in review, the way a Tier-1 line never was — happens without it. Gating there would make an observation the reader cannot confidently classify cost the note itself, and the reader who resolves that by writing nothing has been made worse by the check. The rule is that **a gate must be satisfiable by the actor it gates**, and an advisory is not: a rare-but-correct form cannot be made common, and the second witness in a spelling conflict is another page, which the firewall forbids a reader to open. It gated anyway until the severity split, and eight of eighteen failing proposals failed on advisories alone — so `check` exiting 1 stopped distinguishing a mistyped mark from a rare surname, and the reading brief had been rewritten to teach readers that exit 1 is sometimes fine. An advisory still prints, at the same volume, in the same table; it just stops claiming to be a gate. `--strict` gates on both, for a sweep meant to chase every prompt.

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

### proposal codepoints [REF ...] [LINE]
**Does** names every non-ASCII character in a line's field, or in every line of the page.
**Reads** the proposal.
**Writes** —
**Exit** always 0.
**Note** **`LINE` is a trailing bare number, and the plural refs stay.** This was a `--line` flag on the argument that a variadic positional cannot tell an index from another ref — which is not true here: a ref is `PP-NNN`, a bare number is refused as one corpus-wide with its own message, and the two token shapes are therefore disjoint. The flag cost more than it bought, because `set` and `replace` take their `LINE` positionally and a reader reaches for all three in the same breath; one of them did, guessed the positional, and lost two turns to a usage error. Omitting `LINE` names every line, which is the more useful default besides — asking what a proposal actually contains rather than confirming one line at a time.
```
--all        every review/ page with a proposal
--field {text,resolved,note}  which field [text]
--path FILE                   proposal file, one ref only [review/PP-NNN/proposal.json]
--root --json --toon --pager
```

### proposal set REF [LINE]
**Does** sets one line's field, or many lines' in one write when `LINE` is omitted. NFD-normalized on write, and `{key}` handles in a `text` value are expanded to the ratified forms `lexicon lookup` names.
**Reads** the proposal, `gt/ocr/` when a value carries a handle, and stdin when `--value`/`--values` is absent.
**Writes** the proposal, in place.
**Exit** 0; 2 if a handle does not resolve.
**Note** **a handle is expanded here, on write, and that is the whole reason the field exists.** `text` gets the ratified glyphs and `as_typed` keeps the line as the reader wrote it, so the proposal and the decision go on comparing like with like. Expanding when the review server *serves* the line would do the same job for the adjudicator's eye and wreck the measurement behind it: every handled line would differ from what it is measured against, `save_decisions` would record a human edit nobody made, and `ocr corrections` would grow classes the tooling manufactured — `'` → `ˊ` and `^` → U+030C among them, which is not merely noise but noise shaped like the corpus's real error classes.
**Note** **nothing half-expands, and a bulk write dry-runs every line before writing any.** One unresolvable handle refuses the whole call: a partly-expanded line records neither what was read nor what was meant, and a partly-authored page cannot be told from a finished one. Same rule as `tei expand` one stage later and as `ocr restore` across refs.
**Note** `as_typed` is **cleared** when a handled line is later keyed by hand, because a provenance record that outlives its provenance is worse than none — the review UI would badge a hand-read line as a corpus match for good. Only `text` is expanded; a note may mention a handle without meaning it.
**Note** **the bulk form is a budget fix, not a convenience.** A reader issues a command and reads its result as two separate turns, so a single-line write costs two of `maxTurns: 80`. `1-101` — a two-column numbered list of native names, nearly every line wanting Tier-1 keying — spent 23 `set`, 3 `replace` and 14 `Edit` calls over 21 distinct lines, hit the cap exactly, and was cut off mid-correction. One line was touched twice, so it was not thrash: forty corrections arriving one per turn on a page needing forty corrections. The class of page this fails on is the vocabulary list, which is the densest Tier-1 material in the book. It reports `changed` and `unchanged` per line, because re-sending a whole page most of which was already right is the ordinary use and a bulk write that says only "ok" cannot be checked.
**Note** **`--values` exists beside stdin because the reader cannot reach stdin.** Its guard refuses any unquoted operator, so `<` and `|` are both unavailable inside a reading pass. Same pairing as `--value` and stdin on the singular form, at a different scale.
```
--field {text,resolved,note}  which field [text]
--value TEXT                  the replacement; omit to read stdin [stdin]
--values TEXT                 a {"line": "text"} object, used instead of LINE [stdin]
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

### lexicon lookup QUERY...
**Does** finds a ratified native form by a typeable key and shows the lines it was printed on, so a form's sense is readable without opening the page — `Kuluˊči` alone is a string, "south of Kuluˊči Bay" is a place. The key is what a reader writes in braces for `proposal set` to expand. Match is a substring of the key, the fold, the form, or the key's bare reduction, so `kulu` reaches it.
**Reads** `gt/ocr/`, `data/marks_config.json`. **Writes** — **Exit** 0.
```
QUERY...       any substring; several are an OR
--min-pages N  withhold the key from a word attested on fewer pages than this
               [2]
--context N    lines of surrounding text per matched form [2]
--root --json --toon --pager
```
**Emits** `scope` (the queries, the floor, `forms_indexed`, the standing `floor` caveat, and how many forms could not be keyed), `matches` (one row per form: `key`, `form`, `count`, `pages`, `refs`, `ambiguous`, `why`), and `context`.
**Note** **the key is marked ASCII and deliberately not pretty** — `Kuluˊči` is `Kulu'c^i`, `Kavraˊlɪt` is `Kavra'li_t`. A plain-ASCII key would spell the second `kavralit` and teach an `i` that is not there, to a reader who will key it from memory on a later page: `fold` collapses exactly the axes this pass gets wrong most often, dropped U+0323 being the largest single correction class and `i`/`ɪ`/`I` the largest family. So every non-ASCII character leaves a visible marker and the key cannot be read back as a spelling. Case passes through — it is legible at any zoom, unlike the dot-below, and lowercasing collided on 11 of the 499 forms.
**Note** **a word the book spells more than one way yields no key at all**, and a ruling in `data/marks_exempt.json` does not restore it. That ruling says the ambiguity is *real* — the book setting one word two ways rather than a keyer slipping — which is the strongest possible reason to refuse to pick a side. `Čeˊwɪn` (1-042) and `Čeˊwin` (1-052) are the live instance, and 1-042's reader flagged the disagreement rather than harmonizing to the older page's ground truth; a lookup answering with one spelling is a machine for erasing that.
**Note** **the floor counts pages per fold, over all a word's spellings together, and ambiguity is judged before it applies.** Per-form would delete that same instance rather than refuse it — one page each, both below the default — so a floor could hide a conflict. It may withhold a handle from a form the corpus barely attests; it may never do the other thing.
**Note** the `floor` row is printed on every run because **an empty result is not a corpus-wide negative**: selection requires an inventory glyph, so a native token carrying no mark at all (a bare `c`, `s`, `j`, `x`, `h`) is invisible here by construction. `unkeyable` counts forms carrying something the marker table does not reach — two today, both English possessives on a native name.

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
**Note** **`--context` windows over `scans/`, not over arithmetic.** `PP-NNN` says nothing about how long its part is, so a window is applied to the observed index list rather than computed — which clamps it at each part's end for free, steps over a gap in the sequence instead of counting it as a page, and never crosses a part boundary. `1-362` and `2-001` are neighbours in the binding and nowhere else, and a context spanning them would assert a continuity the scan index does not carry.
```
--all           every scan in scans/, whether or not any store holds it
--context SPEC  also the pages around those named, by scan index within the same
                part: N each way, +N ahead, -N behind, -N+M both. Counts are
                inclusive; a sign binds only its own side, so 5+3 is refused
                rather than guessed at. No-op with --all
--stage NAME    only pages at this rung; repeatable. absent, scanned, zoned-mz,
                zoned-gt, ocr-mz, proposed, decided, ocr-gt, collated
--skipped       only pages that missed a rung below the one they reached
--tally         counts per rung instead of the rows; every rung listed, empty ones
                included — nothing-has-reached-it and everything-has-passed-it are
                different facts
--root --json --toon --pager
```

### corpus normalize REF|PATH [REF|PATH ...]
**Does** NFD conformance, §2.9 spacing, and the lookalike census across every store. It prints the census **and** what a `--commit` would rewrite — two tables, because they are two code paths and a preview agreeing with itself is no preview.
**Reads** every corpus store, deduped by real path (`ocr/` and `gt/ocr/` are two names over one inode).
**Writes** corpus files in place under `--commit` — raw source, never a parsed tree, so element and attribute order cannot move.
**Exit** 1 on NFD drift, an unlicensed mark, or spacing drift. The lookalike census does **not** gate: it is a worklist needing a human ruling on what the page prints. `--commit` always exits 0. Exit 2 for nothing named, or for targets together with `--all`. **Also printed, as a closing `verdict` section** — see `proposal check`; a clean scan and one whose findings do not block but which `--commit` would still rewrite are both exit 0 and are not the same result.
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

Cache telemetry over a dispatched batch, and the contract the batch is dispatched
with. The only group that touches no corpus store: it reads Claude Code's task
transcripts, and writes one tracked file under `.claude/`. Nothing here gates.

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
**Emits** six sections, plus `also_dispatching` when it applies: `scope` (project, the session **names** in view, the agent types in them, and the agent count), `agents` (one row each — its `cohort`, type off `attributionAgent`, model, effort, TTL tier, `opening`, the `tail` written after it, terminal context `ctx`, `saved`, and the agent's `first` and `last` request stamps), `preamble`, `cohorts`, `classes`, `warmth`.
**Note** **`classes` is the batch's context decomposed into what it is made of** — one row per class per cohort, largest first, plus an `ALL` row carrying the sum the shares are taken against. `opening` is the shared prefix; `raster` an image read; `text` a file read; `command` a tool's stdout; `write` a Write or Edit; `message` a turn someone sent; `none` a reply that called nothing. Every request's growth belongs to exactly one class and the growths sum to the terminal context, so `pct` is a share of something real rather than of a total invented for the table. `mean` and `max` are what separate a class that is large because it is expensive from one that is large because it recurs: a fan-out where `raster` has a high mean is reading big crops, one where it has a high count is reading many.
**Note** **`refused` and `failed` are split out of `command`, and they are not the same finding.** A refused call never ran — a guard hook stopped it — so every token it cost bought nothing. A failed one ran and exited non-zero, which includes a gate doing its job: `proposal check` reporting an advisory lands in `failed` and is not waste. Only `refused` is unambiguously spend with no return, and it is the column to read when asking whether a standing brief and a guard allowlist agree. On the first batch measured this way, four readers spent 10 requests and 2,679 tokens on refusals — three of them trying `ls`, two `cat`, three a shell operator.
**Note** **`reply` is a column and not a class**, because it is orthogonal: every request has one and it belongs to no tool. Its `ALL` total is what the batch spent thinking and writing, as against what it read.
**Note** **requests are counted per `requestId`, not per record.** A request emits several usage records as it streams and the early ones carry a partial `output_tokens`; counting records ran `reqs` two to four times high and every sum with it.
**Note** **cohorts and preambles group by agent type**, not by model alone. Opening very nearly decides it — two types have different system prompts and so cannot open at the same total — but "very nearly" is not a grouping rule, and pooling two types' turn-1s reports a variant count for a batch that was fine.
**Note** the saving columns: `saved` is the prefix the warm siblings read instead of writing, `originated` what the batch made once, `if_all_cold` what it would have cost with no sharing, and `asymptote` the limit `(N-1)P / (N(P+W))` tends to, which is `P/(P+W)`. **An asymptote and not a ceiling, because it is never reached** — `(N-1)/N` is never 1, so even a batch where every sibling after the first opened warm reports a shortfall against it, and that shortfall is arithmetic rather than a defect to chase. `own` — the mean per-agent work beyond the prefix — sits beside it so the ratio is checkable rather than asserted: an asymptote near 50% means `opening` and `own` are near equal, which is a fact about the pass being measured and not a property of the arithmetic.
**Note** `ctx` is the agent's terminal context, which is the *shape* of the per-agent figure the harness itself reports — a terminal measure, not a sum, since an agent's context is re-sent every request — and lands within ~0.6% of it. It is **not** claimed as a reproduction; the exact composition is not established.
**Note** **`chars` is the one column not in tokens, and is signed because it is what a turn adds.** No per-message token count is recorded anywhere: `opening` covers the system prompt and the whole preamble undivided, and every preamble turn arrives before the first request, so there is no earlier measurement to diff against. A per-turn token figure would be a `chars/4` estimate beside nine measured counts, or a controlled experiment nobody has run — two agents of one type whose preambles differ in exactly one known way, with no memory write in between. That control matters: between two real batches the prompt shrank by 1,043 characters and the opening rose 154 tokens, because a reader had written a memory file and the memory index is in the system prompt.
**Note** **`preamble` is where a broken prefix is actually visible.** It is one row per user turn ahead of the first reply — the whole of what a launch order can affect — carrying that turn's label, its size, and how many *distinct* variants the agents in scope had of it. A cohort table says openings disagree; this says which turn disagrees, and since a prefix ends at the first differing byte, the first turn with more than one variant costs everything after it. A preloaded skill labels itself (`skill: read-moll-page`), so the question "what is the 21k?" is answered without opening a transcript.
**Note** **the default scope is one session, and `also_dispatching` says when that was a choice.** Two passes here fan out over pages — the Bogoras readers and the Moll ones — from different sessions, so both being out at once is ordinary. Bare `agents usage` reports the *newest* session, which with two batches running is a coin flip that can land differently between two runs of the command; every column would be right, about a batch you were not asking after. So any other session that has written within the subagent cache TTL is listed by id and quiet-time, and `--session` takes that id by prefix. It reports and never chooses: `scope` names the sessions actually in view rather than counting the directories searched, which under `--session` was every session the project has.
**Note** **the rows are ordered by `first`, not `last`.** Launch order is what the table is read for — one member of a cohort writes the shared prefix and the rest read it, so who opened first is who paid, and a stagger is a claim about `first` alone. Ordering by `last` let duration talk over launch order: an agent that opened first and ran long sorted below one dispatched minutes after it. Both stamps are in the row, so the gap between them is the agent's own span.
**Note** **the TTL is read, not assumed.** A request records which tier its write bought under `usage.cache_creation`, so `warmth` reports the measured clock rather than a constant taken from the documentation. Where agents in scope disagree the shortest wins: a prefix is warm only while every witness to it still is, and the optimistic reading would send a batch at a cold cache. `TTL` survives only as the fallback for a scope that wrote nothing, and says so in the row.
**Note** the system prompt is **not** in a transcript. It is inferred as `opening - preamble` and never reported as though it had been read, which is why `opening` is the figure this verb leads with.
**Note** **the cohorts are numbered, and the number is how a batch is named.** `c1` is the oldest cohort in scope and the newest has the highest number, matching the order `cohorts` prints in; the id appears on every `agents` row too, so which reader belongs to which fan-out is readable without matching openings by eye. **Scope-relative by construction** — the ids describe this invocation's grouping, so `--since` or `--all` renumbers them and nothing should store one. `agents transcript --cohort c4` is what they are for: a question about the batch rather than about one of its readers.
**Note** **a cohort of one claims nothing.** A lone agent had nobody to share with, so its opening is reported as `singleton — nothing to share` rather than as a shared prefix. Calling one agent's opening a shared prefix is the fabricated measurement this verb exists to catch, and it would be a poor thing for the verb to commit itself.
**Note** `missed` is `(agents - 1 - warm) x opening`: one member of a cohort must always write the prefix, so `agents - 1` reads is the ceiling. The gap is what staggering the first launch buys, and it is zero when every sibling after the first read what the first wrote.
**Note** **`warmth` is the only pre-flight signal there is.** The cache cannot be queried, so the age of the last request against the five-minute subagent TTL is the whole of what can be said — subagents cache on that clock even where the parent session holds a longer one.
**Note** **an unparseable `--since` is a usage error, not an empty result.** Comparison is lexicographic, so `5m` sorts *after* every ISO stamp there will ever be: before the relative form was supported, passing it filtered every agent out and printed an empty table at exit 0 — a wrong answer wearing the shape of a right one. The stamp is also truncated before comparison rather than carrying a `Z`, since transcript stamps have fractional seconds and `…:00Z` sorts after `…:00.5Z`.
**Note** the session is discovered from `--root`, whose path Claude Code slugs into the transcript directory name; the newest session *that has transcripts* wins, since a session that dispatched nothing has a `tasks/` directory too and picking it would report the empty batch as the batch.

### agents sync
**Does** refills the groundtruth-reader's transcluded blocks from the files they name, so the copy in its system prompt agrees with the source. Bare form reports which blocks have drifted and writes nothing.
**Reads** `.claude/agents/groundtruth-reader.md` and each `<!-- transclude: SRC -->` it names. **Writes** `.claude/agents/groundtruth-reader.md`, under `--commit`. **Exit** always 0; 2 if a transcluded source does not exist.
```
--commit     actually rewrite the agent file — bare form only reports which
             sources its blocks have drifted from
--root --json --toon --pager
```
**Emits** one `transclusions` row: the agent file, the count of `stale` blocks, the `sources` they came from, and whether this run wrote.
**Note** **the reader's contract has to be in its system prompt, and `keying_spec.md` has to stay one file.** The spec binds the collation pass and the human keying track too, so it cannot move into an agent definition; but a `Read` of it costs ~15k tokens per reader per page, behind the turn that varies, where nothing can share it. So it is copied in mechanically and `test_transclusion.py` fails when the checked-in copy and its source disagree — two copies with a gate between them, which is what this repo already does for `VERBS.md` and the click tree. What it forbids is two copies with a *comment* between them.
**Note** **`ocr queue` syncs too, and this verb exists because that is the wrong moment.** A spec edit made between batches leaves the agent file stale until the next dispatch, so the gate fails on a commit that has nothing to do with dispatching and the fix is a command whose other effect is to deal out a queue. `queue` keeps its write regardless: a batch dispatched from a stale contract is exactly the failure the gate exists to prevent, and there is nobody to ask at that point.

### agents transcript [AGENT ...]
**Does** one named agent's requests in order — or a whole cohort's under `--cohort` — with what each one added to its context and where that came from. **`added` is the column**: a request's whole context is `in + read + write`, so the difference between consecutive requests is what arrived between them. Reading down it catches a duplicated block, which no per-agent total can — a contract re-injected on resume showed up as +14,916 on request 2 of three separate readers, identical to the token, and was invisible in every summary. `note` and `detail` name the arrival from the tool the *previous* request called, since its result is what the growth is made of: `read raster moll-046.png`, `ran command … zoom moll-046:15,33`, `write file`. `via` says whether that growth was paid for — `read` is a context served whole from cache, `write` is the only kind that costs.
**Reads** `/tmp/claude-*/<project-slug>/*/tasks/*.output`. **Writes** — **Exit** always 0; 2 if no transcript matches an AGENT, if no cohort matches `--cohort`, or if neither AGENT nor `--cohort` is given.
```
AGENT...     agent id, or its leading characters — what `usage` prints
--cohort ID  every agent of one cohort — a batch, as `usage` groups it (c1, c2,
             …); exactly one of AGENT or this
--session S  one session, by slug or id prefix — scopes --cohort, whose ids are
             relative to the agents in view
--all        every session this project has transcripts for, not just the newest
             — scopes --cohort
--tasks DIR  the task-transcript directory [the newest session for --root's
             project that has any]
--root --json --toon --pager
```
**Emits** `transcript`, then the same `classes` breakdown `usage` prints per cohort — over whatever was named, so `--cohort` gives the batch's and a list of ids gives those agents'.
**Note** **`added` splits into `reply` and `result`, and the split is measured rather than apportioned.** What arrives between two requests is the agent's own reply — which stays in context — plus what its tool returned, and the reply's size is recorded on the earlier request, so subtracting it leaves the result exactly. The subtraction is checkable, not assumed: two readers refused an identical `ls` after replies of 4,843 and 4,634 tokens both came out at **138** for the refusal. That is the reason for the column — in the raw delta that call reads as +4,981, and 138 of it was the tool's, so `added` alone makes a reader that thought hard before a cheap call look like an expensive call. `result` is left signed: a negative would mean the decomposition does not hold there, and clamping it to zero would hide the one case worth seeing.
**Note** an AGENT matching nothing is a usage error, not an empty table: a mistyped id and an agent that never ran are different facts and only one of them is the caller's to fix. `--cohort` refuses the same way, naming the ids that are in scope.
**Note** **`--cohort` reuses `usage`'s own grouping rather than re-deriving one.** The cohort is already what the transcripts hold that is closest to "the batch you dispatched", and the per-request decomposition is already taken to build it — so this flag reads that walk instead of a second pass over the same files, which would be two paths to one number with two chances to disagree.
**Note** request 1 has no predecessor, so its `added` is the opening itself — the system prompt and the whole preamble in one sum, undivided because nothing in the record divides them.

## verbs

This file, addressed by verb. The only group that documents the CLI rather than
touching the corpus, and the only one whose source is a document rather than a
store. Reports; nothing here gates.

### verbs show [GROUP [ACTION]]
**Does** prints one action's entry, or a whole group's plus the Conventions that bind every action, or — named with nothing — the list of every action there is.
**Reads** `harness/VERBS.md`.
**Writes** —
**Exit** 0; exit 2 for a name that matches no action, which reports the near misses rather than an empty table.
**Note** **it exists because reading the whole reference is expensive enough to distort a pass.** A `groundtruth-reader` mid-page wanted the surface of its own commands, `Read` this file twice — 22,517 tokens then 10,734 — and spent a fifth of that page's entire context on it, more than every folio hunt on the page put together. It was not misbehaving: its contract says the CLI is documented here, `--help` is thin in places, and nothing offered a way to consult one entry. `verbs show ocr zoom` is under a thousand.
**Note** it slices the committed file on the `### group action` headings the file already carries, so there is no second copy and nothing to drift. `test_cli_surface.py` still gates the file against the click tree in both directions.
```
--root --json --toon --pager
```
