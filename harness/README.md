# `harness/` — the tooling, module by module

The console script (`harness`, `[project.scripts]`) run from the repo root; every
path resolves against the cwd unless `--root` says otherwise. `uv run python -m
harness <group> <action>` is the same thing.

This file covers **structure**: what each module owns, which stores it touches, and
the invariants that bind a caller. For what an action *does* — what it reads, what
it writes, what its exit code means — **`harness/VERBS.md` is the source of record**,
held against the click command tree by `harness/tests/test_cli_surface.py`; `harness <group>
<action> --help` carries the same contract per flag and is deliberately verbose. For
the project's rules, `CLAUDE.md` governs; for the character inventory,
`keying_spec.md`.

## Stores, and which are writable

| path | what | written by |
|---|---|---|
| `scans/` | 832 rasters at 300 dpi, bitonal where the page has no photograph. **Derived** from `pdfs/`, not in git | `tools/extract_scans.py` |
| `ocr/` | the **read view** over both OCR stores — symlinks, the human file always winning. Derived, ignored; nothing rebuilds it automatically, so `ocr pages --show-store` reports what each link *actually* reaches | `ocr link`, and `ocr predict` for the page it wrote |
| `gt/ocr/` | human ground truth — the pages a reader has been through and an adjudicator has signed | `ocr restore --commit` |
| `gt/lines/` | the **corrections overlay**: boxes a human drew over ink the segmenter left unboxed, per page, in raster coordinates, `+ _ink_exempt.json`. Folded into every page's lines by `lines.page_lines`, so a correction is reachable on the pages that have no ground truth at all | `ocr edit` (geometry), `ocr restore --commit` (text) |
| `mz/ocr/` | what the models emitted: lines from `blla`, text from CATMuS, structured by the zones. Derived, ignored | `ocr predict` |
| `gt/fig/` | 252 figure ALTOs, geometry only, **no `TextLine` at all** | by hand, via eScriptorium |
| `gt/zones/` | the **current** segmentation: seven types, fixed-width bands, `+ _train.lst _eval.lst _exempt.lst _rule_exempt.json _ink_exempt.json _para_exempt.json` | `zones edit` |
| `mz/zones/` | what the trained segmenter emitted: raw kraken ALTO, free polygons, kraken's ids. Derived, ignored | `zones predict` |
| `zones/` | the **read view** over both zone stores — symlinks, the human file always winning. Derived, ignored | `zones link` |
| `tei/` | the collation output, and the system of record for seam state — including `corpus-header.xml`, which is a fragment, not a page | the collation pass, `tei seam --commit` |
| `mz/tei/` | the generated first-draft page, by rule from `gt/zones/` + `gt/ocr/`. Derived, ignored; **no view over the tei pair**, since naming the two apart is the point | `tei generate` |
| `entities/` | the encyclopedia: one markdown record per entity under its class directory. The referent of every `@ref`, and the source of the alias vocabulary a rule links by | `entity new --commit`, `entity ratify --commit`, `edition serve` |
| `data/` | `readings.md` `loi.json` `toc.json` `authorities.json` `runs.json` `alphabet.json` `lexicon_extra.txt` `zones_config.json` `lines_config.json` | by hand |
| `gt/page-img/` | an editor's own version of a whole leaf, `gt/fig-img/`'s doctrine one level up. Resolved by `edition_ui.leaf_source`, **reading view only and exempt pages only**. **Derived but tracked**, `data/geo/`'s split: `1-361`'s master is ChaiNNer work no script here rebuilds | by hand |
| `mz/page-img/` | what a leaf is *delivered* as — an anti-aliased linework PNG over a colour JPEG at a third scale, Mixed Raster Content. Derived and gitignored, `mz/tei/`'s disposition; `edition_ui.leaf_layers` returns both or neither | `tools/build_leaf_layers.py` |
| `data/geo/` | the compiled shape store the atlas draws: watersheds, language areas, coastline, `+ index.json SOURCES.md`. **Derived but tracked** — its sources are outside the repository, so a clone cannot rebuild it | `tools/build_geo.py --commit` |
| `data/pdf_images.json` | the source PDFs' own embedded-image geometry: each page's master, the photographs on it, and the shift from the legacy render space. **Derived but tracked**, `data/geo/`'s split and for its reason. The one witness to a figure's place that no person and no model produced | `tools/extract_scans.py --commit` |
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

**`cli/`** — the two-tier command tree, **click**, one module per group: `_tei _ocr
_proposal _zones _lexicon _find _corpus _views`, each exposing `register(cli)` and
one `run_*` handler per action, which returns the exit code. `__init__.py` holds
`main`, `build_parser` (separate so the surface test can walk the tree without
running anything), and the rename trap. `_common.py` holds the declaration
helpers, the `out` printer, the two walkers, the three rename tables, and the
multi-ref machinery.

**The tree is built programmatically, not by decorator** — `group`/`action`/
`opt`/`arg` — because that is the shape the eight modules already had, and
because it keeps the **`run_*` functions untouched**: `action`'s callback packs
click's keywords into the one namespace object they have always read. The claim
worth being able to make about a parser migration is that only the declaration
changed, and rewriting 54 handlers is the one thing that could quietly falsify
it. Measured: across 142 captured invocations, every payload and every exit code
came out byte-identical; only error wording and `--help` layout moved.

What the move buys: **shell completion** off the tree itself
(`_HARNESS_COMPLETE=zsh_source harness`); the globals parse at **all three tiers**
rather than two, so `harness zones --json check` works where argparse made it an
error; and `harness tui` appears if `trogon` is installed, guarded rather than
depended on.

**Constraints and help sections are `cloup`'s**, and they are why it is here
rather than plain click. Click has no mutually-exclusive group at all, which for
a few hours meant hand-rolled checks in `_namespace` and in `run_seam` — the
convention's own anti-pattern ("argument validation is the parser's, not an
if-chain's") with better manners. `exclusive(...)` and `require_exactly_one(...)`
put it back at the declaration. Three are declared: `--json`/`--toon` on **every**
action, `tei seam --continues`/`--fresh` (argparse's one *required* exclusive
group), and `ocr review --serve`/`--html`/`--spans`. That last one is the reason
to be glad of the gate — the plain-click conversion had silently dropped it, and
`--html --spans` together went from exit 2 to running.

Two mechanical notes. Click's own paired-flag form (`--continues` with `--fresh` as its off switch) was tried
first and rejected: it makes giving *both* legal, last one wins, on a verb that
writes two pages on the answer. And a constraint names parameters, which cloup
resolves against `cmd.params` **at construction** — where these modules add params
afterwards, through `opt`/`arg`. So specs are stored on the command and bound by
`seal()`, which `build_parser` walks the whole tree to call; no call site can
forget it.

**Sections** group the actions in `--help` — `zones` splits into "The store" and
"The segmenter", `ocr` into reading / correction loop / recognition. They are only
where a group's own module docstring already draws the line: a heading invented
here would teach a reader a distinction the code does not make, and four groups
have too few actions to want one. The four globals likewise sit in their own
`OptionGroup` so they stop crowding out the flags an action is actually about.

**Help text is Markdown and is rendered as such.** These strings have always been
written that way — `**bold**` for the sentence that matters, backticks for every
path and flag — because they are read in the source at least as often as on
screen, and they were being printed with the asterisks in them. `rich` renders
them (`_markdown`); a pair of regexes here would be the one-off reimplementation
this project's own rules call a tell. Only the *body* goes through it: an option's
one-line help stays cloup's, which wraps it into a measured second column, and
handing that back pre-wrapped would have the two of them wrapping to different
widths. The theme is `cloup.HelpTheme`; `NO_COLOR` and a pipe both turn it off
through `render.colour`.

**The cost, stated because it is on the hot path.** click is 28 ms of import and
cloup another 36 ms, and unlike rich they cannot be deferred — the command tree is
built out of their classes. A payload invocation went **0.11 s → 0.20 s**, which
every model invocation pays. `rich.markdown` is another 75 ms but only on
`--help`, which is a human action. That is the migration's one real regression,
and it buys completion, declared constraints, sectioned help and the TUI.

| helper | what it is for |
|---|---|
| `refs_arg(p, all_=…)` | the `PP-NNN [PP-NNN ...]` positional. `nargs` is `+`, or `*` with a `--all` whose help must name *what it enumerates* — "every page" is four different sets here |
| `page_refs(a)` | the refs named, `[]` for `--all`. **Parses every one before the caller does any work**, and holds the three-way exclusion between refs, `--all` and `--itinerary` |
| `one_page_only(a, …)` | refuses a per-page flag given several refs. `--out` is why it exists: nothing errored before, the second page overwrote the first's images |
| `out_per_ref(a, pairs)` | one ref emits what it always did; several pool with `ref` first. A list-valued field is **split out**, never left in the row: a list of records becomes a count with its own ref-keyed table, a list of scalars is space-joined into the cell |
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
decides the shape because the caller named one page. In a split-out sub-table the
caller named several and the rows are a *subset* of them, so dropping the `ref`
column would leave a table whose rows belong to a page it does not name. `_pool`
is the unconditional form and is what the sub-tables use.

**Which treatment a list field gets is decided per field over every page, never
per cell.** An empty list cannot say whether it would have held records or
scalars, so a per-cell rule prints `errors: ""` beside `warnings: 1` in one row
and the column means two things.

This splitting used to be a second function, and `out_per_ref` *raised* on a list
field to make the caller choose. That was the wrong trade — the split is exactly
what the thinking caller writes, so refusing bought nothing and left every plural
verb whose payload happened to carry a list broken until somebody ran it with two
refs. `ocr clean` was found that way, in use, with its tests green.

**The field set is decided over every payload, never `pairs[0]`** — a field absent
from page one and a list on page five reached `_pool` unsplit and tripped its guard
after all the work was done. And the `# field` sub-tables come out in the records'
own order rather than a `set`'s, since Python randomises string hashing per
process and they were reordering between runs of one unchanged command; CLAUDE.md
records the same hazard permuting a model's class map.

**A list inside a record of a list-valued payload is deliberately not handled.**
Where a payload is already one row per finding, a list in a cell means the verb is
emitting a shape that is not a table, and `_pool`'s guard firing is the right
outcome rather than something to absorb. `proposal check` was found that way and
fixed at the source — its six detectors now share one key set
(`proposal_check.ISSUE_FIELDS`, built only through `issue()`), where before they
each named their own fields and a corpus sweep printed 265 findings as 51 KB of
nested blocks.

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

**`parallel.py`** — one ordered map, `pmap(fn, items, jobs)`, for the sweeps whose
per-page cost is a raster decode. A **thread** pool: PNG inflate is ~0.16 s of a
page against ~0.02 s of measuring, and zlib/PIL/numpy release the GIL for it, so
threads buy the concurrency without an interpreter and a fresh `lxml`/`numpy`
import per worker — the trade that matters on a 4-core VPS, where N × the resident
set binds long before N × the CPU. Workers come from `os.process_cpu_count()`,
which honours affinity, so a run confined by `taskset` asks for what it has.

Three properties callers depend on. **Results are ordered**, because every caller
pools into a ref-keyed table or accumulates rows in scan order and completion order
would reshuffle the report by which page decoded first. **`jobs=1` builds no pool
at all** — it is the control arm, not a debug switch: the claim these verbs rest on
is that concurrency moves wall clock and nothing else, and saying so means running
both sides and diffing. And **an exception keeps its type**, gaining the item as a
note, because `cli.main` catches four concrete types to turn them into a one-line
`ERROR:` rather than a traceback; `main` prints notes for the same reason.

**A pool is the second thing to reach for.** Both sweeps that looked like
candidates had a larger win in the hot path — `unlicensed_marks` asking a one-entry
dict about every character in the corpus, `validate_page` re-reading all three
split lists twice a page — and the second was also the GIL-bound share capping the
pool's own speedup. The module docstring carries the measurements, including which
verbs were benched and left serial (pure-Python scanning gets *slower*; 0.12 ms of
lxml per page is under the dispatch cost) and the trap that cProfile's per-call
overhead overstates call-heavy code by 6×.

**`ocr predict` is the exception and uses processes, not this.** Its cost is not a
decode: a page is ~17 s, of which `blla.segment` is ~15 and recognition ~1.5, and
the segmenter's time is scipy/shapely baseline vectorization on one core with the
GPU at ~4.5%. That workload is only ~55% GIL-free, so threads plateau at 1.8×
where four processes give 2.8×. See `recognize.predict_workers`.

**`context.py`** — the `PP-NNN` contract (`parse_ref`, `norm_ref`, `stem_for`) and
`build_context`, the per-page input the collation pass consumes. Everything in it is
deterministic and precomputed: a pass that re-derived any of it could disagree with
the validator that checks it.

Also `_running_title`, the page's own folio, read from the three zones a number can
print in — `FOLIO_ZONES`, in order of confidence — and the second witness to
`state.py`'s prediction. `APPARATUS_ZONES` is the same three, kept out of the body
`generate.py` writes and out of the text `detector_flags` reads; the exclusion lives
in `build_context` and **not** in `_lines_from_alto`, which also feeds the lexicon
frequency tables that `keying_spec.md` §5.1 cites. Same reader, two consumers, one
exclusion.

`tier1_terms` is the other selection of Tier-1 tokens, and it calls
`detectors.cyrillic` for the same reason `native_corpus` does. The two disagreed
about Russian until the reading view linked the handles: `й` is `и` + U+0306 and
U+0306 is an inventory member, so `Чукотскій` got a handle from one arm and was
excluded by the other, invisibly from both sides. It also refuses a token that
does not survive `join_broken_words` whole — a handle is what `tei expand` stamps
`#gt`, and the rejoined form is a string no line holds.

**`generate.py`** — the first-draft TEI page, by rule, into `mz/tei/`. Reads
`gt/zones/` for the paragraph boundaries (`MainZone-P` opens one,
`MainZone-Continued` does not) and `gt/ocr/` for the text. A `Continued` band joins
the paragraph above it rather than opening one. **The keyed bands are the
paragraphs, no rule adds to them, and this module opens no raster** — its output is
a pure function of the tracked stores, so a clone reproduces it byte for byte.
`zones.paragraph_starts` used to cut a band it measured as holding two; it gates
`gt/zones/` now, that being the store its findings are answered in. Splits the footnote apparatus at its printed markers and
anchors each note at the matching marker in the body — both the printer's own
marks, so both rules — and emits `<figure n><figDesc>` where each box sits. Emits a
comment naming every judgement it declines: the `MainZone-Other` catch-all, a note
whose marker reads nowhere or reads twice, a figure's place in the prose, and the
language of a Tier-1 form. `diff` compares it against the collated page; the generation stamp
is what lets that comparison tell a difference review made from one a regeneration
made under it.

**`entities.py`** — the encyclopedia store, and the one matcher over it. Parses
`entities/<class>/<slug>.md` on the `readings.md` pattern (heading-sliced, NFD on
read, absence is `{}`); an identity is `class:slug` and lives twice, as the
directory and in the heading, so `check` can compare them — a file's role must not
live only in its directory name. `auto_forms` is the whole bar for a machine link:
one claimant, not `auto: no`, ratified. **`match` is called by three modules** —
`generate` links with it, `context` reports with it, `validate` re-derives `#mz`
against it — because three implementations of one rule would be three witnesses
that are one. **`rule_links` is the same argument one step on**, for the
positional half `auto: once` added: it reduces a `once` form to the page's first
occurrence, and `generate`, `validate`, `relink` and `relink.missing` all go
through it, because a placer and a re-deriver that computed "first" separately
would disagree as a stale-stamp error on a page nobody edited. The count is over
the links a page *already has* — `relink` works on unlinked text, where the
first occurrence is invisible inside its `<rs>` and the second reads as first. `children`/`relatives`/`roots` walk the tree — which is
containment in general and not the geography's: they read no coordinate and no
shape, and they lived in `geo.py` until a caller wanting a people inside a
people had to import the atlas to get one. `geo` re-exports the first two.
**`tree_parent` is the edge those walks follow**, `within:` if there is one and
`part-of:` otherwise, the fallback scoped to `people:`. One function because
five callers must agree exactly — the three above plus `geo.extent_of` and
`geo.unlocated` — and a tree disagreeing with the extent would draw a node in
one place and frame it on another. `within:` is now held to the four
geographical classes at both ends and `entity check` gates it: a people filed
inside a village was borrowing an extent, which `geo:` says directly, and it hung
from that village in the tree as the price. The parser refuses an unknown field
rather than dropping it, `RETIRED_FIELDS` excepted: `part-of:` was silently
discarded by a `[a-z]+` key pattern that could not match a hyphen, and every gate
passed. `area:` is retired there too — a second location field beside `geo:`,
which now repeats and holds a point, a shape or another entity's extent.
`occurrences` finds where an entity appears across a **caller-supplied** page
list, so `entity occurrences` can audit committed `tei/` while the reading view
sweeps what it is actually serving, and neither inherits the other's corpus.
`harness entity rename` is the only thing that moves an identity, and it refuses
while committed `tei/` names the old one.

**`lexicon.py`** — the edition lexicon, `lexicon/<slug>.md`, on `entities.py`'s
pattern and **deliberately thin**: an entry holds an editor's note and nothing
else, because the pronunciation, the attesting pages and the printed glosses are
all derived on every load and a copy of one would go stale while still reading as
an entry. The identity is the **exact surface form**, NFD, carrying no language —
a form only becomes `ckt` when a collator judges it, and an id holding one would
leave every unjudged form unaddressable. The slug is authored, not the form's
`handle_key`: over the corpus's 609 forms that key yields 23 pairs differing only
in case and 34 containing a colon, and it is non-injective by design, so the
check that would catch a collision passes on both files while only one can exist.
`check` refuses two slugs a case-insensitive filesystem could not tell apart.

**`tei_html.py`** — committed TEI to HTML, for the reading view. The apparatus is
rendered rather than tidied away: an unratified rank is marked and an editorial
comment becomes a flag, because a page with an open question must not look
finished. `crop_style` places a raster box inside a clipping frame in percentages
only, so a crop scales to whatever width the panel has.

A Tier-1 span becomes a lexicon link **keyed by the bare form**, so a generated
page links as a collated one does: the handle is lang-less by design, and the
lexicon does not key on language. `_is_tier1` is the discriminator — `xml:lang`
in `TIER1`, *or* no language and an `@index`, which is the generator's handle. Not
"no language" alone: the detector fires on a combining diaeresis, so that would
link ordinary German.

**`ipa.py`** — a keyed Bogoras form to imputed IPA, by rule. Reads no scan and
proposes no glyph, so the firewall is not what it answers to; what it answers to is
fluent nonsense, which is why a character with no row makes the whole form
`partial` and is *named* rather than skipped. Five sorts have a gloss in the p. 10
key and no IPA value, and turning a gloss into a symbol is a judgement.

**`speech.py`** — that IPA to a WAV, by shelling out to `espeak-ng`. Lifted from the
Moll reader's `tts.py`, so its rejected-library reasoning is not re-argued here; what
is new is that **every row of the phoneme table carries the readback espeak actually
gave it**, measured in a frame, and the test compares the table against the installed
binary. That is what caught a bare `r` becoming the English approximant before any
vowel, and `r^` rendering while swallowing what came after.

**`geo.py`** — the compiled shape store, read-only, and the checks over it. Imports
no geometry library: the store's longitudes are already normalized into one
continuous window, so what is left is arithmetic — the heavy work happened once, at
build time. `entity check` gates that a `geo:` member *resolves*; everything geometric is
`geo verify` and **reports**, because a containment disagreement says one of two
authored facts is wrong and cannot say which.

**`geomap.py`** — shapes to an inline SVG map. Lambert azimuthal equal-area, centred
per map: it goes through `sin`/`cos` of longitude, so the antimeridian closes for
good rather than being handled. One 1000-unit `viewBox` for every map, which is what
lets one decimal place be enough at every zoom and keeps a pixel dimension out of it.
`render`'s `mark` is carried, never computed: it sees paths and cannot tell a drainage
basin from a coastline, so `edition_ui.map_context` decides from the shape's *type* and
this only puts it on the root element. Every path also carries the entity it belongs to
(`owned`), because nothing about a path recovers it — a member is the nearest descendant
*with* a shape, and two entities may share one polygon — and that is what a hover
highlights on.

**`edition_ui.py`** — the reading view's domain layer; its routes are
`harness/web/edition.py`. Two columns, a stack of entity/lexicon/scan cards under one map pane, the encyclopedia as a tree over the class, and its audit queue. A footnote marker is not a card — it keeps its href and jumps to the note at the foot, which is already on the page. A map is not a card either: there is only ever one *here*, so it is the pane, and clicking a place moves it. A hover *is* a card, fetched early and floated pointer-inert, which is why it never competes with the stack. Serves committed
`tei/` only, or `mz/tei/` too under `edition serve --drafts`, every draft marked.
Writes `entities/` on a click without `--commit`, as the other editors
write their stores, and **rolls a write back if `entity check` fails on the
result** — every `@ref` in the corpus resolves against that store.

**`alphabet.py`** — the alphabet key as a chart. Joins `data/alphabet.json` (both
printed accounts of Bogoras's notation, and Mythology's arrangement of them) to
`ipa.RULES`, `ipa.MODERN` and the corpus's own attestation counts. **It settles
nothing**: where the witnesses disagree the chart shows all of them. `check` also
compares the store's codepoints against `keying_spec.md` §2.2-2.3, which owns the
inventory — the fact is held twice on purpose and the comparison is what makes
that safe.

**`apparatus.py`** — page-runs: spans of scans the edition serves as one document
(`data/runs.json`), the anchor vocabulary, the folio index over three ranked
witnesses, and `locate`, the single resolver every redirect route goes through.
**The locator and the anchors are the load-bearing part, not the renderers**: a
chapter page will be a run with a derived span, and nothing downstream may care
which kind it got. `edition runs` is the gate. `docs/edition.md` has the model.

**`state.py`** — derived seam state. Folio comes from a committed TEI's `<pb n>` and
propagates forward; `expected_folio` is null wherever the chain breaks, and null is
the answer, not a failure. Also `toc_window`/`toc_search`/`toc_near`.

**`entry_state` and `build_ledger` answer different questions and neither calls the
other.** The ledger walks every scan and computes a `boundary` column needing each
page's *successor*, which is what `tei ledger` reports and wants. `entry_state`
needs two bounded things: a backward walk stopping at the first untranscribed page,
and the milestone fold over its **own part** up to itself. It used to get them by
building the whole ledger, which is quadratic once `tei validate --all` and every
`tei context` pay it per page. The only memo is a dict local to one call, so the
walk and the fold do not parse a page twice; nothing is stored, so nothing needs
invalidating. The narrowing is invisible in the output — the answers are
byte-identical — so `test_folio_fold.py` holds it by spying on `_tei_facts` and
asserting what gets *opened*.

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

**`schema.py`** — the *conformance* check, against committed `data/tei_all.rng`
(TEI P5 4.12.0). Answers "is this actually TEI", which `validate.py` cannot: every
project rule there is expressible in conformant TEI, so a file can satisfy all of
them while using an attribute TEI never defined. Neither subsumes the other.
`check()` for a page, `check_header()` for the bare `<teiHeader>`, which has no
conformant container and is wrapped in a minimal `<TEI>` in memory — never on
disk, since inventing one would settle the assembly scheme by accident. The
compiled grammar is cached per process because libxml2 takes ~17 s over `tei_all`
and ~0.3 ms over a page; `validate()` and `check_corpus_header()` therefore
default `schema=False` and only the CLI turns it on.

**`expand.py`** — writes ratified Tier-1 forms into a collated page, resolving
the `index=` handles the pass writes against `context.tier1_terms`. The model
names the token; the glyphs come from `gt/ocr/`. Refuses rather than ranking two
claims about one set of glyphs: a handle naming no term, a handle on an element
already holding text, a handle outside a Tier-1 `xml:lang`.

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
gets serialized is the `ocr_record` list the recognizer returns, never the lines with `text`
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

**Recognition goes through `kraken.tasks.RecognitionTaskModel`**, not the
deprecated `rpred.rpred` that kraken 8 removes. Two traps in the swap. The config's
`device` is **Lightning Fabric's**, handed straight to `Fabric(devices=…)`, so
`"cuda:0"` fails as `invalid literal for int()` naming neither the field nor the
model — `_fabric_placement` translates, and the rest of the module keeps torch's
spelling because `blla.segment` does. And `no_legacy_polygons` moved from an
`rpred` argument to a config field **with its default flipped**, so leaving it
unset silently restores the slow polygon path.

**`predict_all` parallelizes across processes, and `predict_workers` says how
many.** This is the one sweep in the harness that does not use `parallel.pmap`,
because its cost is not a decode: a page is ~17 s, `blla.segment` ~15 of it and
recognition ~1.5, and the segmenter's time is scipy `correlate1d`, shapely
`intersection` and kraken's own boundary tracing — vectorization on one core, with
the GPU at ~4.5% throughout. Only ~55% of that is GIL-free, so threads plateau at
1.8× where four processes give 2.8×. Consequently `batch_size` is nearly inert
(17.4 s/page at 1, 16.8 at 32) and `num_line_workers` is 0, since it spawns
processes to feed a 1.5 s phase.

`spawn`, not fork — a forked child inherits a CUDA context it cannot use. The
worker count is capped by **free VRAM as well as cores**, read off the card at run
time: a worker holds ~1.4 GB of CUDA context (the weights are 22 MiB of it), and a
constant here would be wrong on the next machine, the same argument the column
measure rests on. An explicit `--jobs` wins outright, including one that will not
fit, which is `predict_skip`'s `single` rule applied to a different resource.

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

**`figrefs.py`** — the cross-references the prose sets at its own pictures:
`(Plate XXVII, Fig. 3)`, `Fig. 87 represents a knife`. `scan` reads a string and
reports what the page prints; `resolve` takes those spans plus `figures.by_number`
and `figures.by_plate` and says which crop each names. **The two halves never
meet in one caller by accident** — `tei_html` calls only the first, because
`stores.render` is cached on the TEI's bytes and a crop handle baked into that
HTML would outlive the box it named. The join is `_figref_state`'s, in
`harness/web/edition.py`, as `<figure>`'s is `_figure_state`'s.

`foreign_citation` is the one guard: Bogoras cites Nelson's and Sauer's plates in
the same words as his own, and `Sauer, Plate XIV` collides with this book's Plate
XIV outright. The names come from `Authorities Quoted`, so telling them apart is
a lookup in a store a human keyed. Measured over the corpus: 601 references link,
114 are another author's, 58 refuse and each names the store that declined.

**`figures.py`** — the figure track whole: `gt/fig/` geometry against
`data/readings.md` text, reconciled by `reconcile()` (`corpus figures`); the
store's writes (`save_figs`, `delete_figs`, its own split lists and
`_rule_exempt.json` under `gt/fig/`, never shared with `gt/zones/`); the checks
(`validate_fig_page`); and the segmenter quartet (`remark_eval`, `assemble`,
`predict`, `score`, `install_model`). Also the generic sheet compositor `lines.py`
reuses, and `read_blocks` — **the one reader of the `OtherTag/@LABEL` + `TAGREFS`
zone encoding**, store-agnostic, with `zones()` and `zones.read_zones` as its two
bindings.

Two caller invariants are this module's alone, and both are silent when broken:

- **A block id's last field is a foreign key** into `data/readings.md`, so
  `save_figs` preserves ids where `save_zones` re-mints them by position. The mint
  floor is the union of the incoming ids and the ids on disk — the batch alone
  cannot see an ordinal a reading still names. Re-minting produces a well-formed
  file with the same counts and the same *set* of suffixes, so `corpus figures`
  still reconciles; only the pairing moves.
- **An empty figure ALTO is never written.** Absence of the file is how this store
  records "no figures on this page", and `zones.blot_one`, `lines.line_gaps` and
  `dispatch.survey` all read an existing file as the opposite. `save_figs` refuses
  and names `fig delete`; the empty region sets a segmenter needs are synthesized
  in `assemble` and land only in `train/`.

**`zones_config.py`** — loads and checks `data/zones_config.json`: the seven types
with their keys and colours, the per-part text measure and anchor calibration, the
declarative order rules. `order_warnings` is pure and is transcribed into the
editor's JS, with `harness/tests/test_zones_order.py` holding the two together. Every rule
here is a *warning* — nothing in this config can refuse a save.

**`lines_config.py`** — the same for `data/lines_config.json`: the line editor's
layers with their colours, its keybindings, its zoom. Deliberately the same shape,
so a human moving between the two editors configures one tool with two subjects
rather than learning a second format. The overlay's stylesheet (`layer_css`) and
the panel's key list are *generated* from it — written out beside it they would be
a second place the colours and keys lived, free to disagree with what the editor
actually binds, and a help panel that lies about the tool is worse than none.
Validation is at load and by name, because every fault here would otherwise
present as a **broken editor**: a key bound twice fires one of its two jobs, and a
layer the drawing code asks for and the config omits simply stops being painted —
on an editor whose whole subject is a mark you have to be able to see.

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

**A sweep writes that cache once, through `record_ink_many`; only the editor uses
`record_ink`.** Both reduce through `_ink_verdict` and write through
`_write_ink_cache`, so there is one reduction and one writer rather than two that
can drift. The per-page form is a read-modify-write of the *whole* file — load
every entry, replace one, re-serialize all of them — which made a corpus sweep
quadratic in the size of the store, and which is the shape that cannot survive
being parallelized: N workers would each load the file, add their entry and write
the lot back, dropping every verdict but the last. The batched form reads once and
writes once, and a test pins the resulting file byte-identical to the per-page
loop's. The temp file carries the pid, because `replace()` is atomic and the write
into the temp is not — an editor saving while a sweep runs is an ordinary sequence.

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

Three exemption sidecars, and they answer different questions. `_rule_exempt.json`
says a page arranges itself unusually and the order rules may stop saying so.
`_ink_exempt.json` says a particular *band* of ink is not type — a smudge, a gutter
blob, offset from the facing page — and carries the reason as a required field.
`_para_exempt.json` says a measured first-line indent is not a paragraph opening,
which is the other answer to `zones paragraphs`: the real findings are answered by
splitting the band in the editor, and without somewhere to put the rest the same
questions came back on every run. All three are scoped to a band and never to a
page — the checks are the only thing that can see a dropped zone or a lumped
paragraph, and a page-wide suppression would hide the next one. All three keep
reporting what they excuse, flagged and carrying the note.

The editor's **store selector** (`/`, or the three HUD pills) is orthogonal to the
itinerary: the itinerary chooses the pages, the selector chooses whose reading of
them is drawn — `zones` (the view, default), `gt`, `mz`. `page_state(store=...)`
resolves it server-side, including the snapping and the presence counts, so the
client never re-derives the store rule. The `zones` pill reports what the *view*
resolves to, which is deliberately not an echo of the current selection: with `mz`
pinned on a page that has both, `shown` is `mz` while the view still answers `gt`.

**`corrections.py`** — human line corrections, and the line half of the ink
question. Two checks run over these pages: `zones check --ink` asks whether ink is
inside any zone, `ocr gaps` asks whether *in-zone* ink is inside any line. They
shared one exemption file, so a band ruled "scanner smudge" while zoning — a claim
about what the zoning need not cover — also stopped the line check from ever
reporting that strip again, and a folio dropped inside a `RunningTitleZone` is
what that hid. One file each now, **overlaid rather than merged**: each band is
settled by the layer whose question it is, and `line_gaps` reports which. The
store *mechanism* is shared and lives here — band-scoped, reason-required,
midpoint-matched — with `zones.py` calling it for its own directory; what differs
is only which question the file answers, which is what each file's `_about` says.

**`web/`** — the web layer: one FastAPI app, one process, one socket per editor.
The four browser tools were four hand-rolled `http.server` handlers with their
HTML in f-strings and their CSS and JS in Python string constants; they are one
app with templates (`harness/web/templates/`), static files (`harness/web/static/`) and declared
request bodies. Four things in it are load-bearing:

  * **Endpoints are declared `def`, not `async def`.** Every handler body here
    blocks — lxml parses a page, PIL opens a raster, the zones segmenter runs a
    torch forward pass. Starlette runs a *sync* endpoint in the anyio worker
    threadpool, which is the thread-per-request behaviour the stdlib shell gave,
    so the bodies came across unchanged. One `async def` doing any of that stalls
    the event loop for every editor at once.
  * **`serve()` binds the ports of the editors in `EDITORS`**, and
    `uvicorn.Server.serve(sockets=[…])` takes them all — so 8731–8734 are four
    doors into one app rather than four servers. That is what lets them share a
    template tree, a store cache and a `Sessions`, and what lets a second
    invocation hand its work to the process already running. Derived from the
    registry rather than written as a literal, which is what let the four move
    over one at a time.
  * **Each door admits one editor.** `port_editor` reads the receiving socket out
    of `scope["server"]`, and a request for another editor's prefix is refused
    naming the port that owns it — every route used to answer on every port, so
    `:8732` served `/lines/save` exactly as `:8733` did. The routers are still all
    mounted, because four apps would mean four `uvicorn.Server`s and lose
    everything the shared process buys; the isolation is per request instead.
    `/static` and the shell's `/`, `/session/{editor}` and `/stop` stay reachable
    everywhere — they belong to the process, and `handoff` posts to the *target*
    editor's port. With no port resolvable the middleware falls open, since a
    `TestClient` has none and the guard is about real sockets.
  * **`errors.fetched` marks a route the page `fetch`es** rather than navigates
    to. Its failures are reported as `{"error": …}` because an HTML traceback
    raises inside the `fetch` and throws away the very reason the page was
    trying to show. The mark is on the endpoint, so a re-pathed route cannot
    drift away from its own error shape.
  * **`files.send_file` is how a file is served**, and not `FileResponse`
    directly: that sets `ETag` and `Last-Modified` and does *not* check
    `If-None-Match` — the conditional logic lives only in `StaticFiles` — so a
    bare `FileResponse` re-sends the whole body behind headers saying it need
    not.

**Two rules for adding a template or an editor**, both learned the hard way:

  * **Never name a context key `items`, `keys`, `values`, `get`, `pop`, `copy`,
    `update` or `clear`.** Jinja resolves `row.items` to the dict *method* before
    it looks for the key, so the loop silently iterates a bound method instead of
    failing. It cost the entity card's `contains` row and the review palette's
    key grid; both were renamed (`entries`, `glyphs`) rather than written as
    `row['items']`, because the next person adding a row would hit it again.
  * **A test that asserts on behaviour reads the `.js` file, not the page.** The
    scripts are static assets now, so grepping the HTML for a handler finds
    nothing — and the tempting fix is to re-inline the script, which undoes the
    change. `test_zones_ui.py` and `test_review_session.py` both read
    `harness/web/static/js/` directly for this reason.

**`harness/web/cache.py`** — store reads memoised on a **digest of the file's contents**,
not on its mtime. Measured on this filesystem: 190 of 200 immediate rewrites
produce an identical `st_mtime_ns`, because inode timestamps come from a coarse
~1 ms clock and the nanosecond field reports that granularity rather than
removing it. A timestamp key would not have narrowed the staleness window, only
made it hard to reproduce — and these are tools whose stores are edited
underneath the running server. What makes hashing affordable is measured too:
parsing a TEI page costs ~22× reading and hashing it. `harness/web/stores.py` applies it,
and lives in the web layer because a cache is a property of a *server*: the CLI
reads a store once and exits.

**`zones_ui.py`** — the segmentation editor's state and writes; its routes are
`harness/web/zones.py` and its markup the templates beside it. `GET /page/<ref>.png` is a
route because a full page as a data URI is ~10 MB of markup.
The client sends a column index and never an x — the geometry is re-measured
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
in `prior_note`. `is_medial` generalises `detectors.medial_cap_positions` to the small caps
rather than copying its lookbehind class; the two agree on every live position and a
test holds them together. **Both read the hyphen rule off that one definition** —
inside a Tier-1 token a hyphen is word-internal, so a compound's element-initial
capital is medial, while in English (`Baffin-Land`) it is not. They once agreed on
the opposite and were wrong together, which `Hɪtoˊ-Lap` cost two pages.

**`lookup.py`** — a ratified native form found by a typeable key, and the handle a
reader writes instead of retyping its glyphs. **Two strings, and conflating them is
the trap.** `marks.fold` is the *bucket*: it collapses every contrast axis, which is
what makes `Čeˊwɪn` and `Čeˊwin` one word and lets the conflict be seen at all.
`marks.handle_key` is the *key*: it marks every non-ASCII character, so the key
cannot be read back as a spelling and cannot teach a reader an `i` that is not there.
Marking distinguishes, so the two spellings have different keys — which is why the
ambiguity refusal lives on the bucket, and a precise key pointing into a contested
one is refused all the same. Three invariants for callers: expansion happens **on
write**, so the proposal and the decision compare like with like and `ocr
corrections` never sees a correction the tooling manufactured; `as_typed` is the
provenance record and the review badge is **derived** from it, never asserted by the
reader whose claim it describes; and **nothing half-expands** — one refused handle
aborts the whole write, on `tei expand`'s rule one stage earlier.

**`paths.py`** — the `review/<ref>/` layout authority, and `DERIVED`. Also
`page_dirs`, because `review/` has children that are not pages: the dispatch queue
and its claim markers live beside the directories they deal out, so **no caller may
glob `review/*` and assume a ref**. Five did, and three survived only by filtering
on `proposal.json` existing.

**`migrate.py`** — moving every stored coordinate from the legacy `pdftoppm`
render's space into the extracted master's. A **translation**, taken as one rounded
integer per page from `data/pdf_images.json`, and that is what makes it checkable:
extents do not move, so a width that changed means the operation was not the one
this module claims. Two gates, because the obvious one is vacuous here —
`content_digest` hashes `String/@CONTENT`, which `gt/zones/`, `gt/fig/` and
`mz/zones/` have none of, so a **structural** digest carries them: the block-id set,
the label multiset, and every box's extent. Ids are never re-minted (395 captions
key on a `gt/fig/` id, and a `gt/lines/` correction id encodes the y it was made
at). `data/_migrated.json` is the receipt, and it exists because **part 2 does not
move** — 2550×3525 before and after, so no size check can tell "correctly untouched"
from "not yet reached". The driver is `tools/migrate_to_master.py`, on
`migrate_fig_bboxes.py`'s rule that a migration argued for only inside a script
nobody imports is a migration nobody can check.

**`dispatch.py`** — a dispatched pass's fan-out: `queue` validates a batch and
writes its queue file, `claim` takes the next ref off it with `O_CREAT|O_EXCL`,
`reconcile` says what came back. Two templates, both living in a track's
`dispatch.md` rather than here, and the module only substitutes and refuses.

**Two tracks, one `Track` value.** `READING` deals pages to `groundtruth-reader` out
of `review/`; `COLLATION` deals them to `collator` out of `tei/`. What varies is four
paths, the per-page block and the deliverable `reconcile` looks for — so it is a
frozen dataclass rather than a second module, because the locking is the part it
would be worst to have two of: a bug there deals one page twice and nothing says so
until the batch comes back wrong. Every public function takes `track=READING`.

What the tracks do *not* share is the refusal set. Reading refuses a page with
ground truth (a reader sent at one stops being an independent witness); collation
refuses a page with TEI (it would overwrite committed work) and treats ground truth
as the *better* input. And **an uncollated predecessor is not a refusal for
collation** — it was an implicit one while that pass ran serially, since `tei seam`
refuses without a predecessor, and moving the seam to the coordinator is what lets a
batch go out in any order.

**`reservations.py`** — the far end of the collation fan-out: the open comments a
batch left in its pages, pooled and classified so they can be read against each
other rather than one file at a time. Its class table is a second copy of the comment
forms the collation contract fixes, held to them by `test_reservations.py` — which
checks that every pattern matches a stated form, and not the reverse, because an
unmatched contract form lands in `other` where somebody sees it while an unmatched
pattern is dead surface that never fires.

**The prompt every reader gets names no page**, and that is the invariant the
module exists to hold: identity of a subagent's first turn is what makes its
context cacheable, so a ref written into a prompt costs every sibling the whole
shared prefix. Anything that varies between readers must arrive from a tool call —
which is what `claim` is. `sync_transcludes` is the other half: it refills the
agent definition's marked blocks from `keying_spec.md` and the checklist, so the
contract sits in the system prompt without the spec becoming two files. It is a
verb writing a tracked file with no `--commit`, deliberately, and the exception is
stated in `VERBS.md`: the write is a byte-copy under a test
(`test_transclusion.py`), not a judgement.
**`pipeline.py`** — the lifecycle census: where each page has got to across every
store at once, on one ladder (`scanned` → `zoned-mz` → `zoned-gt` → `ocr-mz` →
`proposed` → `decided` → `ocr-gt` → `collated`). `STAGES` is the whole content —
`stage` is the furthest rung reached and `skipped` everything below it that is
absent, both derived from that one tuple so they cannot disagree. **`skipped` is
why the module exists**: `stage` is a summary, and a summary that can hide the
anomaly it summarises is the shape this project is organised against. A rung a
route legitimately omits is not a skip, and getting that wrong costs the column
its value — `zoned-mz` first counted against every exempt page, 83 plates
drowning the one page that really had no prediction behind it. It reads
**path presence only**, never a file's contents, which is what makes it ~0.4 s
over 832 pages and also what it cannot answer — whether a page's zoning is any
*good* is `zones check`'s question and costs a raster. It gained a `generated`
rung when collation became gated on one — a page with ground truth and no `mz/tei/`
is genuinely not ready, and the ladder names which step is missing. It no longer
feeds `context.build_context`: with the gate in place that payload could only ever
have carried one value.
**`proposal_check.py`** — a proposal's `resolved` field against its `text`, plus the
field-editing verbs; `check` also runs `marks`' two deterministic arms when given a
ref. **Every issue is one record shape** — `ISSUE_FIELDS`, built only through
`issue()`, and `marks.page_issues` imports that constructor rather than writing
literals. Six detectors feed one list, and a ragged list of records is not a table:
they used to name their own fields (`context`, `in_text`, `in_text_not_resolved`,
`explained`), which silently degraded the whole report to TOON's nested form. No
field holds a list; codepoint sets and the footnote arm's note are rendered into
`detail` as text. **`codepoints.py`** — one job.

**`emit.py`** — the serializers, TOON and JSON, and nothing else. It does not know
what a terminal is and must not learn: **`render.py`** owns that half, and the split
is what keeps the model's view and the human's view from being one negotiation.

**`render.py`** — the human view. `mode(a)` returns one of `json`/`toon`/`table`
and is the only place the choice is made; the default is `sys.stdout.isatty()`, so
a model piping the output keeps getting TOON byte-for-byte while a human gets
columns and neither has to say so. Four properties bind callers:

- **Nothing truncates.** rich ellipsizes a cell that will not fit; prototyped over
  `views check --all` (169 columns natural) at 80 it also wrapped one field across
  five rows. A `…` inside a page ref or a Tier-1 form is a value that reads as a
  value and is not. The console is therefore built at the table's *own* measured
  width and never narrower, so rich is never in the position of having to shrink a
  column. Output wider than the screen is the pager's problem, not the renderer's.
- **Colour says what type a cell is, never what it means.** The palette is rich's
  own `repr.*` theme rather than one invented here: null dim-magenta, the two
  booleans green and red, headers bold. The renderer knows a cell's type and
  nothing else — it cannot tell `keyed: false` (an unread page) from `ok: false`
  (a gate failed) — so any scheme claiming to say which is a verdict the display
  layer is not entitled to make. **Numbers are deliberately unpainted**, and that
  is the half worth knowing: the grid already right-justifies an all-numeric
  column, so painting it encodes one fact twice, and since numbers are most of the
  cells in most of these tables the first cut turned `views check --all` into a
  wall of cyan zeros with the two informative marks lost inside it. Colour earns
  its place by being rare. The one exception is `render.report`, which paints
  `tei validate`'s `RESULT: PASS`/`FAIL` — that report states its own verdict, so
  colouring it asserts nothing the text does not. It is also the only painted path
  reachable outside table mode, hence gated on the mode rather than on `colour()`,
  and it renders through `Style.render` rather than a `Console` because a console
  has a width and a width crops: the first cut cut `METRICS:` off at the eightieth
  column.
- **A payload that TOON would degrade falls back to TOON.** Uniform records, a flat
  record, and a list of scalars are drawn; a ragged key set, a nested value or a
  list in a cell is not. Drawing one would mean leaving a hole and saying nothing
  about it.
- **Scalars are spelled as TOON spells them** — `null`, `true`, `false`. Two
  renderings disagreeing about the word for a value would put `None` in front of a
  human and `null` in front of the model for the same ledger cell.
- **`--json` is one document per invocation.** Sections buffer through `collect`
  and `main` emits them with `flush`: bare when a verb printed one, an object
  keyed by section when it printed several, the first key defaulting to the
  action's own name so a verb names only its *extra* tables. It used to emit N
  documents on one stream — 15 of 58 measured invocations were not
  `json.load`-able, on the one flag whose purpose is being parseable. A **name
  collision refuses**, because two sections sharing a key would drop a whole
  table into the other's slot and leave a consumer a plausible document missing
  half its content. Known limit, stated rather than half-fixed: the key set
  follows which sections had content, so consumers should use `.get()`; making
  the shape a pure function of the verb would mean each declaring a schema.
- **Progress goes to stderr, and `render.progress(label)` is the only place that
  knows what a bar is.** It yields a `tick(item, done, total)` for
  `parallel.pmap`/`ptrack`, or **None** when stderr is not a terminal — in which
  case `pmap` skips the call entirely, so a redirected run is exactly what it was
  before the bar existed. That is what keeps the four benched sweeps diffable
  against `--jobs 1`, and it is measured: 11.8 / 11.0 / 0.7 s against the 11.2 /
  10.9 / 0.7 s baselines. The bar starts on **elapsed time** (`PROGRESS_AFTER`),
  never item count — a count cannot tell a 4-page raster sweep from a 40-page
  `ocr lines`, one being seconds and the other milliseconds — and it is
  `transient`, so what stays on screen is the payload.
- **The pager is opt-in — `--pager`, `$PAGER`, default `less -SRFX`, table mode
  only.** It was on by default on git's reasoning, `-F` printing and exiting when
  the content already fits; the default is off because that reasoning charges the
  *ordinary* case. A table that fits went through a subprocess and a pipe to
  arrive looking the same, and one that did not took the terminal from someone who
  had not asked for it. `pager(a)` replaces `sys.stdout` rather than pushing
  sections through, so every print reaches it, including `tei validate`'s prose,
  which never went through `out()`; `less` renders progressively, so a long
  multi-ref run still shows its first report immediately. An absent pager falls
  back to printing rather than failing. **`zones edit` and `ocr review` refuse it
  at registration** (`pageable=False`), because they print a URL and block on a
  server.
  Consequence that bites: **`mode(a)` is resolved and cached before the
  redirect.** Asked afterwards, `isatty()` is False and every table silently
  comes back as TOON — the terminal's output format decided by the fact that we
  are showing it to the terminal.
- **A section's `name` is a JSON key, not a heading.** TOON prints a `# name`
  line only where one was already printed (`out_per_ref`'s split-out list
  fields), because TOON is what every skill and every model reads and naming a
  section must not change it. Table mode labels every named section, having no
  legacy and needing the label: several aligned tables in a row are otherwise
  indistinguishable from one table that changed shape.
- **rich is imported lazily and only in table mode**, because it costs 38 ms
  against `harness.cli`'s 55 ms on a CLI whose whole `--help` is 110 ms. It has to
  be rich rather than a hand-rolled aligner for this corpus's own reason:
  `len("g̣")` is 2 where its display width is 1, the store being NFD corpus-wide,
  so a character-counting aligner would misalign every column of Tier-1 forms.

## Invariants that bind callers

- **Dedupe by real path when walking stores.** `ocr/*.xml` are symlinks into
  `gt/ocr/`, so a naive walk sees each file twice, and a writer meets it again under
  the second name, finds it already done, and skips silently — the report then
  undercounts exactly what it touched. `normalize.scoped_files` does this.
- **`context._lines_from_alto` drops empty lines and discards `@ID`**, so a position
  in the plaintext it produces is *not* an ALTO index. Join through
  `lines.page_lines`.
  `detector_flags` used to inherit that offset; it now carries `index`, the ALTO
  identity, so a flag joins `ocr_lines` and resolves with `ocr zoom --only`. The
  position was replaced, not supplemented — see `detectors.detect_all`.
- **A line polygon can exclude printed text.** `1-074` prints `5.` and `9.` outside
  their boxes; `1-073` puts its `5.` and its folio outside *every* box on the page.
  The omission is horizontal, so vertical padding never reaches it — `PAD_X` is
  sized for it, wide enough that a box strangling a folio still renders the whole
  number. It was a `--margins` flag widening to the `PrintSpace`, which failed
  twice over: it made the ordinary case conditional on asking, and since the
  widened crop spans the sheet it silently redefined what a `@P` span was a
  percentage of, so the aim that would have hit the folio became unguessable.
- **Reading `String/@CONTENT` out of `gt/fig/` returns `""` for every zone.** Not an
  error — nothing, which is worse. Caption text comes from `figures.readings()`.
- **The three lookalike tables differ by scope and must not be merged.** See
  `harness/tests/test_lookalike_scope.py`, which exists because a consolidation was very
  nearly carried out on the strength of an audit that called the difference drift.
- **Keep one fixed key set across a list of records.** The TOON encoder collapses a
  uniform list to a header plus rows; one ragged record de-tabularizes the whole
  table into the verbose nested form. It does not error, so nothing tells you: a
  detector-per-shape list read fine one page at a time and printed 265 findings as
  51 KB of nested blocks over the corpus. If several producers feed one list, give
  them one constructor (`proposal_check.issue`) rather than one convention.
- **A sweep measures in the pool and folds outside it.** Counters, caches and
  label censuses stay single-threaded and in ref order, so `--jobs` changes wall
  clock and nothing else. A read-modify-write of a shared file inside the loop is
  the shape that breaks silently under a pool — every writer but the last is lost —
  and it is usually also quadratic before anyone parallelizes it; batch it
  (`zones.record_ink_many`).
- **A sweep reports completions; it does not draw them.** `pmap`'s `tick` is
  called from the *calling* thread via `as_completed`, never from a worker: a
  counter inside the mapped function would put display work on N workers while the
  caller sat blocked, with a shared object touched concurrently to do it. That
  swap moved two previously-free properties into `parallel.py`'s hands, and both
  are pinned by `test_parallel.py` — results land by **submission index** (the
  yield order is completion order), and an exception is re-raised in **item**
  order, because `pool.map` surfaced the earliest failing *item* and a sweep over
  832 pages must not start naming a different page than it used to.
- **Profile before reaching for cores, and check the profile against a stopwatch.**
  The two sweeps that looked like pool candidates each had a larger single-threaded
  win in the hot path, and in one case that same work was what capped the pool.
  cProfile's per-call overhead overstates call-heavy code — it reported one of them
  at 19% where the wall clock said 3%.
- **Resolve a zone's type by `OtherTag/@LABEL`, never by tag ID.** eScriptorium
  assigns those per export (`BT55`/`BT56` in one, `BT68`/`BT69` in the next), so
  hardcoding them fails silently rather than loudly: it once left a migration that
  "quietly became a no-op that reported success"
  (`git log -- tools/strip_graphiczone_lines.py`). `figures.read_blocks` is the
  only place that resolves a label.
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

**Two kinds of test here hold a property nothing in the output can show.**
`test_parallel.py` pins that `jobs=1` runs in the *calling thread* rather than a
pool of one — a serial arm that still went through an executor would compare the
executor with itself, which is this project's oldest failure shape. And
`test_folio_fold.py`'s spy asserts which TEI files `entry_state` opens: its
narrowing was byte-identical in every output, so only a test of what gets read can
keep it from growing back. Where a change is invisible by construction, test the
work rather than the answer.

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
