# Open questions

The standing record of what is deliberately unresolved. An entry leaves this
file by being settled, and says so when it goes; a confident reason standing
in for an open question is the same failure as a confident reading standing
in for an unread glyph.

## Open

- **The oysters and shells of 1-249 have no entity, and no rank to hang one
  from.** The chapter's opening page has the Maritime Chukchee "gather oysters and
  shells on sandy beaches or in shallow waters", and that is the whole of the
  evidence: no binomial, no second mention, no Chukchee form beside it. Two things
  block an entry. **No true oyster inhabits Chukotkan waters** — Ostreidae do not
  reach the Bering and Chukchi seas — so "oysters" is either a loose English word
  for the mussels and cockles that do, or a report Bogoras took on trust; either
  way the identification would be the store's invention rather than the page's.
  And **the store holds no mollusc anywhere**: minting `taxon:mollusca` for one
  clause would add a rank carrying a single unresolved member, which is what
  [[taxon:animalia]]'s admission rule refuses. Left out of the Chapter VIII pass
  deliberately. **Waits on a second attestation** — another page naming a shellfish,
  or a Chukchee form for one — which would say what the word is doing and give the
  rank something to hold.
- **One curly apostrophe sits inside a Tier-1 span, and nothing exempts it.** The
  book quotes an Iñupiaq form from another author, in that author's notation, and
  the form carries an ordinary U+2019: `3-070` L37, `kin-ĭ-g’un`. `ipk` is a
  Tier-1 code, so the span falls under §3's Tier-1 greps, which since 2026-08-21
  name U+2019 as a trap for stress. The reading is right and the gate is right;
  what is missing is a way to say "this form is in a cited system, not Bogoras's"
  that the grep can see — a notation attribute on the span, or an allow-list keyed
  by ref and line. Waits on a decision about the mechanism.
- **The List of Illustrations has no reader, and the cross-check waits on chapter
  assembly.** `docs/apparatus.md` describes a per-entry reconciliation — every LoI
  text-figure located on a page, no caption numbering outside the LoI, all 35
  plates placed — and it is a hand check living in no code: `figures.reconcile`
  opens `gt/fig/` only, while `harness/VERBS.md` lists
  `edition/loi.json` under `corpus figures`' **Reads**, which is currently untrue.
  Building it was scoped and deferred rather than attempted, and the reason is
  sequencing: an LoI entry says which *folio* a figure falls on, so checking it
  is a question about where a figure sits in the assembled book, and the book is
  not assembled — nothing is collated against 399 drafted. The same holds for
  `edition/toc.json`. Both belong with chapter assembly, after collation, when there
  is a running text for a folio to be a position in.

  Two things not to lose in the meantime. The reconciliation is also the most
  book-specific work in the figure track — plate numbering restarting at 1 per
  plate, the 35-plates/9-full-page-figures split, the LoI's own segment
  conventions — so whatever is built should be reachable only from a book that
  *has* a List of Illustrations, not assumed by the pipeline. And the measured
  state is worth keeping: of 302 LoI text-figures, 300 resolve to exactly one
  page and none to two, with no caption numbering outside the LoI. The two that
  do not are fig. 1 on `1-037`, whose number the printer set below the title, and
  figs. 239 and 240 on `2-068`, which `edition/figure_numbers.json` pairs by hand.
  Both are correct as recorded, so a flat gate on "unlocated is empty" would fail
  on the day it was written.

  **The LoI now has a reader, and it is not the cross-check.** `edition serve`
  renders `edition/loi.json` as a run (`docs/edition.md`), linking each printed
  figure number to its zone through `figures.by_number`. It links and it gates
  nothing, so the reconciliation above is untouched — but the join it needs now
  exists, which is worth knowing when it is finally built.

  **The two the 300 above loses are now keyed by hand, so a reconciliation must
  not read them as derived.** The view folds `figure_boxes` over the figure store
  with the located plate leaves taken out — the book restarts figure numbering on
  every plate, so leaving them in made 1–4 collide with a series they are not in
  — and then applies `edition/figure_numbers.json`, where an editor has named the
  zones for fig. 1 and for `2-068`'s 239 and 240. All **302 of 302** resolve on
  that footing. It remains a different count from the 300 above: this one counts
  LoI numbers against zones, that one text-figures against pages, and only this
  one is patched. Whichever the reconciliation ends up wanting, it should say
  which it is measuring and whether the patches are in or out of scope.

- **Where a plate's rotation is recorded, given that no plate reaches a
  collator.** Rotation is a reading — whether a sideways figure or a
  bottom-to-top plate caption should be turned upright is a judgement about what
  the page means, and this pipeline hands judgements to the collation pass. But
  `dispatch.py` refuses a ruled leaf for both tracks, and every plate is ruled
  `plate`, so the one person entitled to make that call never sees the page. The
  gap is not that the evidence is missing: `figures.paired`'s removed
  `misordered` check found that `1-227` numbers 2, 4, 1, 3 upright and 1, 2, 3, 4
  once the sheet is turned, so the corpus already contains evidence of rotation
  in its caption order. It is that the only witness is an inference and there is
  no store for a human to overrule it in. Crops are taken as the box sits and
  nothing rotates them; `edition/fig-img/` will hold a corrected picture if somebody
  makes one, which is a workaround for the image and not an answer for the fact.

- **Where the index lives is answered, and the answer is that there are two
  objects, not one.** This entry asked whether `lexicon lookup`'s per-run index of
  ratified Tier-1 forms should be persisted as the toponym authority, and refused
  both available answers: persisting under `data/` freezes a store that grows every
  batch, and rebuilding it in the annotation pass makes two passes derive the same
  forms by two paths.

  `edition/entities/` resolves it by being neither. It is **authored, not derived** — a
  human writes an entry and its alias forms — so it is not a snapshot of anything
  and cannot go stale against a store it was computed from. The alias index *is*
  recomputed on every run, from the store, which keeps the recompute-don't-trust
  rule where it belongs. `lexicon lookup` stays what it was: a reader's instrument
  over ratified ground truth, and the place an editor finds the attested spellings
  to put in an entry.

  **What is not yet done is the toponym index itself** — the published, ordered
  thing. `entity occurrences --all` is most of its data. `1-359` is still the
  densest single source, a two-column gazetteer setting native names against their
  pre-reform Russian equivalents, and it is ground truth and uncollated.
- **No part is named by a part title page** — the surrogate has none. Parts II and III
  are named by librarian typescript over an archival sheet that contradicts itself
  (typed 1907/1909 against a printed 1904 imprint), and part I only by the AMNH
  catalogue record, which is its single witness. The catalogue corroborates II and III,
  so those are settled; part I is not, and a copy with part title pages would beat all
  of it. See the teiHeader's `listBibl`, where `@source` points at the catalogue and
  `@resp` is reserved for the model's reading of the rasters.
- **The AMNH catalogue record independently corroborates two apparatus stores**, having
  been consulted for neither: `"Authorities quoted": p. 3-9` against
  `edition/authorities.json`'s folios 3–9, and `35 pl.` against `edition/loi.json`'s plates
  I–XXXV. Cheap second witnesses, and both agree.
- **The ratified build does not exist.** The `--ratified` mode of `validate` reports an
  unratified span as a worklist line, which is the right shape for a page in progress
  but is not a gate: nothing yet *refuses* to publish a `#llm` span. Until it does,
  provenance is recorded and inspectable but not enforced downstream.
- **The skill's page-edge prohibition is still untested, and `1-101` did not test
  it.** The English-correction licence used to permit completing a sentence or
  capitalising a first word at a page edge, which destroys the seam's own text
  witness invisibly. It is now forbidden in prose, and prose is all it is: unlike
  the provenance rank, nothing mechanical can see a page whose opening word was
  quietly capitalised. `1-101` opens on a numbered list item resuming at 15, so
  nothing there tempts a completion — the rule was written for a page opening
  lowercase mid-sentence, which is what `1-100` does, and `1-100` was collated
  before the rule existed. **A page opening mid-sentence, collated after it, is
  the evidence still wanted.** **73.2%** of the 399 keyed pages open on a
  lowercase first word — it was 69.8% at 274 — so the next one in scan order will
  probably do. Quote the measure with the count: it is first-body-line-lowercase,
  which is stricter than "the first main zone is `MainZone-Continued`" (76.7%,
  since a continued paragraph may still open a new sentence) and neither is a
  verb, so both are recomputed by hand and drift quietly if nobody says which was
  taken.
- **A note running across a page seam has no markup.** `<note>` is nested rather
  than a top-level body element, so `seam`'s two-sided-edge machinery does not
  reach it, and the pilot set has no attested instance — so it is deliberately
  unresolved rather than built for. The orphan-foot-text comment names no pass.
- **A word cut by a page turn has no markup either, though this one is attested.**
  The chapter view joins pages, so `consider-|able` across a leaf break became
  something a reader meets. TEI's encoding is `<pb break="no"/>` on the second
  page, and it is a seam fact, so `tei seam` should write it from both committed
  pages. Until then the reading view decides each word at render time by the
  line-end rule (`resolve_break_hyphens`). That is a frequency count, re-derived on
  every render, and a recorded `@break` would outrank it. Waits on `tei seam`
  gaining the flag and on the collation pass reaching these pages; the coordinator's
  step that would write it is `/transcribe-page`'s seam step, which says so.
- **Nothing is collated, and that is now the deliberate state.** `1-021` and
  `1-022` were authored from a plaintext draft under the contract this milestone
  replaced, and were deleted rather than carried forward — a page with no baseline
  is a page `harness tei diff` can say nothing about, and generating one under it
  after the fact would produce a comparison against a file no collator ever saw,
  which is what `drifted` exists to refuse. So the corpus starts collation from
  zero, and every page that enters `tei/` from here has a baseline behind it.

  What those two pages bought before they went is the generator's only measured
  agreement with a human pass, and it is worth keeping: on `1-021` the rules
  produced **the same seven body blocks, the same five paragraph divisions and the
  same note**, differing only in leaving the note unanchored at the foot and in
  flagging both `MainZone-Other` blocks rather than shaping them. On `1-022` the
  one Tier-1 handle it raised was `Döring`, which the human pass had also declined
  to mark as foreign. **One page is not a rate**, and the honest open question is
  whether that holds over a batch — the first real batch is the evidence.

  `1-021` was collated under the review contract and was, for a while, the
  corpus's one committed page. What it measured is the entity half: six `#mz`
  links survived review untouched, three ambiguous candidates the collator
  resolved itself at `#llm`, four candidate comments cleared, and one
  `entity wanted` that became `event:sibiryakoff-expedition`.

  **`tei/` now holds no page at all** — only `corpus-header.xml`, the queue and
  the claims — so that paragraph is the last copy of its own evidence, and by this
  project's own rule a register nobody can re-read against the store is not
  evidence. It is kept as a note of what was once observed and not as a figure
  anything may be measured against. Whoever restarts collation should treat the
  first collated page as the first, not the second.

  **The batch that would turn it into a rate now waits on the OCR pass finishing.**
  The corpus is being read end to end before any of it is collated, for the reason
  in `docs/pipeline.md` §4: `edition serve --drafts` renders `mz/tei/`, so the text
  is readable without this stage, and the encyclopedic work is worth more right now
  than the measurement is. So "one page is not a rate" stands, and stands on
  purpose — not because nobody got to it.
- ~~**The geography view is deferred to a sprint of its own.**~~ **Settled — the
  sprint happened.** The entry wanted a hierarchy of locations navigable as a
  tree, built from GeoJSON then dumped loose in `scratch/`, with no external
  tiles. All of it exists: `edition/geo/` is the store — **derived but tracked**, the
  one store that is, because its sources sit outside the repo and a clone cannot
  rebuild it — carrying 64 shapes across `base/`, `region/`, `watershed/`,
  `langarea/` and `marine/`, of which 62 are claimed by an entity.
  `tools/build_geo.py` builds it, `SOURCES.md` records provenance per shape, and
  `harness geo list` is the census. `entity locate` sets an entry's `geo:`
  members; the atlas renders them with the `within:` chain as its tree, and it is
  still loopback and self-contained. `docs/edition.md` owns the view, the
  `within:`/`geo:`/`part-of:` distinction and what the atlas can and cannot draw.
- **Nothing enforces that a `#mz` link was *wanted*, only that it derives.** The
  gate re-checks that the store still supports every rule-applied link, which is
  what makes the rank honest about provenance. It cannot check that the sentence
  means that entity — that is the collator's deletion, and a page nobody reviewed
  carries its `#mz` links unexamined. This is by design and is why `#mz` renders as
  unsettled in the reading view, but it means **the corpus-wide link count is not a
  correctness measure** and should not be reported as one.
- **Entity identity is settled and the entry that stood here is gone.** It said
  `@ref`/`@key` were gate errors until a scheme existed, and named the shape the
  answer would have to take: lift the refusal rather than route around it, gate
  `@ref` on a referential-integrity check, and give a mechanically-proposed link
  its own rank. All three were built. `edition/entities/<class>/<slug>.md` is the store,
  an identity is `class:slug` because `person:jochelson` and
  `source:jochelson-yukaghir` are the same string and different things, and `#mz`
  is the rank — admitted on `#gt`'s terms, re-derived from the store on every run.
  `docs/edition.md` owns it. `@key` and `@nymRef` stay refused, so the deferral
  survives exactly where it was load-bearing: identity gets one spelling.

  **What is still open is the *ordinal* scheme**, which is a different question
  wearing the same name. Structural `xml:id`s move when content is inserted, so a
  pointer to one held outside the page still breaks silently; they remain stable
  only within a page file's current version, and nothing outside the corpus may
  cite one. An entity `@ref` is not affected — it names a file, not a position.
- **The TEI is validated against TEI**, and the entry that stood here saying
  otherwise wanted "a committed schema and an assembly step". It needed the first
  and not the second. `data/tei_all.rng` is P5 4.12.0 (1.1 MB, committed so the
  gate means the same thing on a fresh clone and after an upstream release), and
  `harness tei validate`/`tei header` run it by default. All nine of the
  previously-unchecked attribute usages are conformant, and a test pins them so
  that stays true while the encoding churns.
  **A page file validates standalone** — the old entry said it would not, which is
  true of `tei/corpus-header.xml` (a bare `<teiHeader>`, wrapped in a minimal
  `<TEI>` *in memory* to be checkable at all) and false of every page, which has a
  real `<TEI>` root. So no assembly step was needed to get here.
  It found one defect immediately: `version="stock"` on `<application>`, where
  `teidata.versionNumber` is a pattern that does not match it, in a file read by
  hand more than once. That is the class this catches and a reader does not.
  **The two gates are complementary and neither shrinks the other**: every project
  rule is expressible in conformant TEI, so the schema is silent on all of them,
  and a file can satisfy all of them while using an attribute TEI never defined.
  `tei_all` and not `tei_lite` — the smaller customizations are strict *subsets*,
  so one would reject markup this project legitimately writes, and a gate that
  fails correct input teaches a reader to ignore it. The cost is the compile
  (~17 s, identical under `xmllint`, so it is the schema's size and not lxml)
  against ~0.3 ms a page, so it is cached per process, a sweep pays it once, and
  the *library* functions default it off or the test suite would pay it on every
  call. Run it after `tei expand`: `index=` is not a TEI attribute, which is what
  makes an unexpanded page detectable, so it fails here too.
- ~~**`edition/toc.json` records no provenance.**~~ **Settled.** It has 316 entries,
  not the 315 this entry claimed, and it now opens with a `source` block in
  `loi.json`'s shape plus a per-entry `ref`: the printed Contents is scans
  `1-007`–`1-013`, folios v–xi. Read off those seven leaves and ratified before
  writing; `tools/toc_provenance.py` holds the reading, the boundaries and the
  three assertions that make seven judgements safe over 316 entries. Every
  apparatus store is now auditable back to a page.
- **The span diff's second witness is back, and it is `mz/ocr/`.** `end-of-eval/`
  was the recognizer store, it was deleted, and the diff refused rather than
  compare a proposal against the ground truth it produced. This entry used to say
  "if a second witness is ever wanted again, it links into `ocr/` from its own
  store" — which is exactly what `ocr predict` built. `harness ocr diff REF
  --spans --store mz` is an independent witness by inode, where the bare view
  stops being one the moment the page has ground truth and the view points at it.
  Name the store, not the view: the refusal catches the collapse, but only after
  you have typed the wrong thing.
- **The segmenter's open questions live with its skill.** The measured state, the
  `unseen`-row collapse and its recurrence condition, `split_from`, the decode
  gains, part 1's deliberate overrepresentation, the unproven `--resize`
  mechanism and the hand-corrected `class_mapping` on the installed model are all
  `.claude/skills/train-zones/SKILL.md`'s — they are training-loop state, and two
  copies of a number is how one goes stale.
- **Whether a `gt/lines/` correction can ever be Tier-1, and what that would take.**
  `tier1_terms` and the `#gt` transclusion `harness tei expand` performs both read
  `gt/ocr/` by name, so a native form keyed into a corrected line would be invisible
  to them. Deferred rather than solved because the census says the class is numerals:
  ~35 unsegmented folios, ~9 printed rules, a handful of unknowns, and not one
  Tier-1 span among them. Extending the transclusion is real design — `tei validate`'s
  membership check and `expand`'s re-check both assume one store — and doing it now
  would be building a mechanism against no attested case. It leaves this list when a
  Tier-1 correction actually exists, and the entry will say which page made it.
- **Who marks value and who draws a citation's boundary.** `<measure>`,
  `<measureGrp>` and `<bibl>` came out of the collation contract, where they were
  144 lines — a fifth of the rules — instrumented by nothing. No generator comment
  asks for one, so a collator either went looking for them on every page or forgot
  they existed, and the measured answer over the corpus is the second: **zero of
  either emitted**, against 1387 entity candidates and 908 language questions the
  rules do ask about. Those two totals were taken over the 274 pages drafted at
  the time and have not been retaken since; **the ratio is the finding and the
  totals are not**, so re-measure before quoting them rather than scaling them.

  The test that moved them is the one that now scopes the whole contract: **that
  pass carries what needs the page in front of it.** A `<bibl>` boundary is drawn
  by reading a note, and the note's text is in the TEI; the barter/currency/weight
  distinction is drawn by reading a sentence, and the sentence is in the TEI too.
  Neither needs the raster. Both are also concentrated rather than spread — the
  value registers are essentially one chapter (*Units and Prices*, `1-079`–`1-094`)
  and citations sit inside `<note>`, which is a query — so a pass that goes looking
  for them will find them without reading 730 pages, which is what asking the
  collator costs.

  What is not deferred: `validate.MEASURE_TYPES`, `MEASURE_IDENTITY_ATTRS`,
  `BIBL_IDENTITY_ATTRS` and the `<measureGrp>`-needs-a-`<measure>` rule stay in the
  gate, unchanged. The vocabulary was never the problem and a later pass will want
  it exactly as written. What was deferred is the *asking*. The reasoning that
  produced the vocabulary — three registers because the book names three, "is this
  thing doing money's job here" as the firing rule, `<measureGrp>` read as "one
  priced object" rather than "these are equal" — is in the git history of
  `.claude/agents/collator.md` and should be recovered from there rather than
  re-derived, since it was settled against pages (`1-079`, `1-093`, `1-094`) and
  the settling is the expensive part.

  It leaves this list when the pass exists, or when a generator comment makes the
  question a collator's again.

- **`train score fig` cannot score a checkpoint in memory, and the zone track
  can.** `train score zones --model X` loads the checkpoint and segments the
  corpus, so a model is measurable *before* it is installed; the figure track's
  score is always `mz/fig/` against `gt/fig/`, so measuring a checkpoint there
  means predicting to the store first — which overwrites whatever the store
  held, and makes the two operations one where the zone track keeps them apart.

  Under the folded verb `--model` therefore means one thing, "segment this
  checkpoint in memory", and **exits 2 for `fig`**. It used to be accepted there
  and silently ignored: `figures.score` took a `model_path`, printed it in the
  report and never opened it, so the report named a model it had not consulted.
  The refusal is not the resolution — it is the honest statement of a gap.

  Closing it means either giving `figures.score` an in-memory path of its own,
  or giving `fig predict` a scratch destination so a checkpoint can be predicted
  somewhere that is not the store. Neither is urgent: `models/fig-seg/` does
  not exist yet, so nothing has ever been scored on this track. **It waits on the
  first figure-segmenter run**, which is when the shape of the answer becomes
  arguable from evidence rather than from symmetry with the zone track.
