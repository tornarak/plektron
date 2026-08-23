# Current pipeline

Moved out of `CLAUDE.md` whole. The per-pass rules live in the skills; this
is the shape of the whole, stage by stage, and the design reasoning behind
the stages that are built.

## Pages

1. **Zoning** — this project's own segmenter (`harness zones predict` →
   `mz/zones/`), corrected in the editor into `gt/zones/`, read through `zones/`.
   **These regions carry semantic value**, which is the difference from the old
   pipeline: seven declared types, a vertical partition of a measured column. The
   LADaS regions they replaced had none and existed only to impose a reading order.
2. **Lines + recognition, one pass** — `harness ocr predict` → `mz/ocr/`, linked
   into `ocr/`. `blla` finds baselines off `scans/w-figs-blotted/`, the same raster
   `zones predict` reads, so artwork raises no baselines; **its regions are
   discarded and the zones replace them**, so a line arrives already knowing
   whether it sits in a running title, a paragraph, a footnote or a signature
   line, and the collation pass gets that structure instead of re-deriving it.
   The label travels in the ALTO as `OtherTag/@LABEL` via `TAGREFS` and surfaces
   as `zone` in `harness ocr lines`. Reading order is zone order, then down the
   page — so in this store, unlike `gt/ocr/`, document order *is* reading order.

   **Nothing is lost to the blot**, and that is a property of how it paints rather
   than a cost accepted: it fills the *declared* figure box and not a pixel more,
   the pad having been rejected precisely because body text sits hard against an
   inset figure on `1-283`. Figure captions do go, and should — they live in
   `gt/fig/` on the block that captions them, and are not body text.

   **It also paints the source's own photograph rects**, from
   `data/pdf_images.json`, and that buys two things the old blot argued for
   instead of having. A human box stopping a few pixels inside a photograph used
   to leave a rim of antialiased halftone at its edge; the rect is the
   photograph's exact extent as the scanner recorded it, so the region is blank by
   construction. And what remains after painting is the bitonal master's two
   values plus white, so the tree converts to mode `1` losslessly and **every one
   of the 829 trainable pages has the same colour depth**. The old rule — keep the
   source mode, or depth correlates with "has a figure" — was managing exactly the
   confound this removes. The 3 RGB pages have no master, carry a leaf kind, and
   reach no trainer. 18 MB for the tree, against 726 MB of rasters before the rebuild.

   The human boxes stay authoritative: 21 keyed pictures are line work the scanner
   left in the master and have no rect, and every caption is type and has none.
   The manifest supplements the store; it does not replace it.

   **A store keeps every line the page sets; a consumer filters by zone label.**
   That rule has now been derived three times from scratch — for `mz/ocr/`, for
   `catmus_draft`/`ocr_lines`, and for the reading proposal — so it is stated here
   once. **Which side a thing is on is decided by what it writes, not by what it
   looks like**: the proposal → `decision.json` → `restore` chain *writes*
   `gt/ocr/`, so it is a store path and keys the apparatus like everything else.
   The 20 restored pages carry **49 apparatus lines and all 49 are keyed**; a
   proposal that omitted them could not restore anyway, since `restore` refuses a
   partial rather than admit ground truth with invisible holes.

   So `context.APPARATUS_ZONES` — running title, quire marks, and the old
   vocabulary's numbering zone — leave the **collation draft, not the store**. The
   filter sits at the consumer rather than at `ocr predict` because those zones
   **carry the printed folio**, and the folio is where page numbering enters the
   project; dropping it at write time would take the OCR's only record of it and
   cost a re-run of the page. An *unlabelled* block is kept, since a store may
   label none and treating blank as apparatus would empty the draft for every page
   of it.

   They leave **`ocr_lines`** as well, and for a sharper reason than the draft's:
   that list is the set of `@facs` pointer targets, and a running head, a folio or
   a signature line is never in the TEI body, so citing one is a mistake by
   construction. A **caption** is different and stays — it is dropped from the
   draft only, because the project already holds a human reading of it on the
   FigDesc block in `gt/fig/`, and it remains legitimately citable.

   **They leave the draft and arrive as `running_title`**, a `tei context` field
   carrying `{text, folio, folio_from, bracketed, lines}` — restructured rather
   than discarded. That folio is the **second witness** to `expected_folio`, which
   is a prediction from the preceding transcribed page and knows nothing about this
   one; the two disagreeing is the signal, and a second witness this cheap is what
   the governing principle asks for.

   **The book prints the number in three places and the corpus spells them in two
   vocabularies**, so it is looked for in order of confidence: the head line of an
   ordinary page; then a **bracketed** number at the *foot* of a chapter opening,
   which is `QuireMarksZone` in the current scheme (`1-151` reads `[115]` at vpos
   3231 of a 3897 px page, and its collated TEI gives `<pb n="115"/>`); then
   `NumberingZone`, the full-SegmOnto zone `gt/ocr/` descends from, last because it
   names a store's spelling rather than a place on the page — it appears at the
   head on `1-048` and at the foot on `1-151`. `folio_from` records which answered.
   Nothing is repaired: `2S` for `28` leaves `folio` null and stays in `text`.

   Recognition is stock CATMuS — a witness to line geometry and English and to
   nothing else (it reads 0% of the inventory; the measurement and its
   substitution table live with the passes that use it). The `Processing` block
   names both models and both sha256s — two of them, one per act, because the
   segmenter and the recognizer are different models and collapsing the pair
   would lose whichever a reader was not asking about. `harness/provenance.py`
   is the one writer behind every `mz/` store's block, and `corpus provenance`
   is the census over them.

   **A line `blla` finds outside every zone is kept, not dropped**, assigned to no
   region and counted as `lines_outside_zones`. Artwork produces these and they are
   visible junk; a dropped line is invisible, and that asymmetry is the whole
   reason for the rule. A high count on an ordinary text page means the artwork was
   mis-zoned or a zone is missing — the same finding `zones check --ink` reaches
   from the other side.

3. **Generation** — `harness tei generate` → `mz/tei/`, by rule and no model.
   Paragraph boundaries come from the keyed `MainZone-P`/`MainZone-Continued`
   labels and from nothing else, and **the stage reads no raster at all** — its
   output is a pure function of the tracked stores, so a fresh clone reproduces it.
   `zones.paragraph_starts` measures first-line indents off the scan and once cut a
   keyed band it read as holding two, which let a speck of dirt in `1-160`'s gutter
   add 20 paragraphs the keying never had; commenting instead of cutting failed the
   same way, since every finding it makes is answered by editing `gt/zones/`. It is
   a gate on the zone store now (`harness zones paragraphs`, ruled in
   `gt/zones/_para_exempt.json`); `<pb n>` from
   the running title's folio; apparatus zones and caption lines dropped;
   `MarginTextZone-Notes` split at its printed markers and each note anchored at
   the matching marker in the prose; figures emitted as `<figure n><figDesc>`
   where their boxes sit; every ratified `tier1_terms` hit lifted into an empty
   `<foreign index="N"/>`.

   **This stage exists because the collation pass was re-deriving adjudicated
   facts.** A collator read the raster and decided where paragraphs began — on
   pages whose `gt/zones/` records exactly that, keyed by a human. The second
   derivation can disagree with the first, nothing downstream can tell which is
   right, and the disagreement is invisible because both look like prose.

   **A `Continued` band joins the paragraph above it.** Obvious from the label and
   wrong here for a long time: both labels mapped to `p` and each band emitted its
   own block, so a paragraph the printer ran across a band boundary came out broken
   mid-sentence. The store had said so all along, which is this stage's whole
   premise, applied to itself.

   **It is a small fix and worth sizing honestly**: 15 paragraphs over the 274
   generated pages. 213 of the corpus's 228 `Continued` bands are the *first* body
   band on their page — the ordinary case of a paragraph running over from the page
   before — and those still open a `<p>` here, because there is nothing above them
   on this page to join. Rejoining across the page boundary is the seam's problem,
   not this stage's.

   **What the printer marked is a rule; what a reader must decide is not**, and
   the footnotes are where that line moved. Splitting the apparatus at its
   superscripts and anchoring each note at the same character in the body are both
   character identity — the compositor set both marks and the recognizer read
   both — so the generator does them, and the reading view gets one clickable
   marker instead of a single `<note>` carrying three notes' text. What it still
   refuses is the case where the evidence is short: a marker that reads nowhere in
   the prose, or reads in two places, leaves the note at the foot saying which of
   the two happened. Notes in this book anchor on their own page, so an unmatched
   marker means the marker did not read.

   **Figures are placed by geometry and are meant to be moved.** The box's
   position is real evidence and puts the figure on the right part of the right
   page; the anchor the edition wants is where the prose says "(Fig. 87, a)",
   which is a reading. So each one carries a comment saying exactly that. A figure
   whose box falls inside a paragraph comes out at the *head* of it rather than splitting
   it — which would undo what `MainZone-Continued` records. Note that
   `context._figures_on_page` withholds geometry from the *model* on purpose and
   this stage keeps it: a rule may use what a model may not, because a rule cannot
   be persuaded by what it sees.

   **What it will not do is the other half.** Headings, tables, verse and captions
   all land in `MainZone-Other`, whose `rank: null` says the store declines to tell
   them apart; a figure's place in the prose is a reading; language is a judgement
   no inventory-mark detector can make. Each of those leaves a comment naming
   itself, and the set of those comments is the next stage's worklist.

4. **Collation** — an LLM reviews the generated page against the scan, and its
   deliverable is `tei/`. `harness tei claim` copies the baseline into place, so
   the agent opens a file rather than authoring one, and **the difference between
   the two stores is the record of what review judged** (`harness tei diff`) — a
   comparison the pass did not have while it authored from plaintext. Context comes
   from `harness tei context`, which now carries everything about the page that is
   *not in the page*; gated by `harness tei validate`.

   **Collation runs only after `gt/ocr/`**, which reverses the earlier position that
   it "runs on whatever draft is current". Taking either store left the pass unable
   to see, per page, whether it was reading a human's adjudication or a recognizer
   at 0% on the inventory — and the defence against that was a long section of prose
   telling the model not to trust its own input. `docs/decisions.md` carries the
   reversal.

   **And it has contracted, rung by rung, until little is left in it.** Each stage
   above took something out of collation and gave it to a rule or a gate: the keyed
   zone labels became the paragraph boundaries (stage 3, built precisely because the
   pass was re-deriving adjudicated facts); the unambiguous entity links are laid at
   `#mz` while the page is generated (stage 5); Tier-1 glyph identity is settled in
   `gt/ocr` before a collator sees anything at all; and the classes that used to fill
   a collator's worklist — footnote markers keyed as ASCII digits, straight quotes
   for curly, French spacing — are caught per page by `proposal check` and
   `corpus normalize` during the reading pass, mechanically and without judgement.
   What is left is the residue the contract always named: a heading against a table,
   where a note anchors, whether a form is foreign. Real judgement, and not much of
   it.

   **So the sequencing has changed: the OCR pass runs over the whole text first, and
   collation follows it.** That is not a claim that collation is unnecessary, but one
   about what is worth doing next, and it rests on a property the reading view
   already has — `harness edition serve --drafts` renders `mz/tei/` beside the
   committed pages. A generated page is a draft nobody has read and the view says so
   on its face, but it *reads*, which makes a **beta edition available from ground
   truth alone**. What then stands between the corpus and something usable is the
   encyclopedic work — the entity and lexicon stores, the indices, the geography —
   and not this stage. Collation becomes enrichment over a readable edition rather
   than the gate in front of one.

   **What that costs is the measurement `docs/open-questions.md` is waiting for.**
   The generator's agreement with a human pass is still measured on `1-021`/`1-022`
   alone, and finishing the OCR pass first defers the batch that would turn one page
   into a rate. A deliberate trade rather than an oversight: the evidence is cheaper
   to collect against a finished corpus, and the pages are not going anywhere.

5. **Annotation** — partly built, and it turned out not to be a stage after the
   others so much as a store the earlier ones consult. `entities/` holds one
   markdown record per entity; `tei generate` links the unambiguous forms by rule
   at `#mz` while it is building the page, and everything contested arrives as a
   candidate comment for the collator to settle. So annotation is **continuous with
   collation** rather than a pass over finished TEI, which is what makes it
   affordable: the reader who is already looking at the page decides, once, and
   `entity occurrences` finds every other instance afterwards.

   **That is the per-page route, and it needs a collator. The corpus-wide one does
   not, and with collation deferred it is the one that runs.**
   `harness lexicon misses --common` ranks the tokens no English lexicon accounts
   for across every OCR'd page — a candidate list drawn from ground truth alone, and
   the reason the entity store and `data/lexicon_extra.txt` suppress `lexicon_miss`
   and nothing else. `entity new` scaffolds at `proposed`, `entity occurrences`
   finds the rest of a form once one instance is understood, `entity alias` and
   `entity locate` fill the record, and `entity check` gates the lot. The store
   holds **482 entries against zero collated pages** — `0d6fe61` alone added 152 —
   which is the plainest available statement of the point: the encyclopedia owes
   this stage nothing.

   **And the store is the unit of work, not the page.** `#mz` links are re-derived
   from `entities/` on every `tei generate`, so an alias written today reaches every
   page that has ever been generated, retroactively and without re-reading one of
   them. That is why the encyclopedic pass is worth running *ahead* of collation
   rather than behind it: its output compounds over the whole corpus, where a
   collator's judgement lands on a page. It also sets the failure mode — a careless
   alias propagates just as widely, which is what `auto: no` and `licensed: false`
   are for, and why a proposal is inert until a human ratifies it.

   What the collator still owns is the contested case: two entities sharing a form,
   a link no alias table may license, a form whose language is a judgement. Those
   wait as candidate comments in `mz/tei/` until the pass runs, and waiting costs
   nothing, because the comments are rebuilt with the page.

   What is not built is the **published indices** — the toponym gazetteer, the
   species list, the D-PLACE linkage — which are derivable from the store plus
   committed TEI and want an ordering nothing has yet chosen. `docs/edition.md`
   owns the store and the rule; `docs/open-questions.md` carries what is left.

6. **Compilation** — TBD for epub and print. The **reading view exists**:
   `harness edition serve` renders committed `tei/` in two columns with the
   entities, notes and scan crops beside it, and is the surface the eventual export
   has to match. It is not a compiler — nothing is assembled, and the corpus
   teiHeader is still spliced by nothing — but it is where the edition is now read.

## Final Product

1. **Original Scan Page** - `scans/chukchi-PP-NNN.png`
2. **Figures, geometry and caption together** - `gt/fig/chukchi-PP-NNN.xml`. ALTO containing only `GraphicZone` and `GraphicZone-FigDesc` blocks, as **bounding boxes**, each FigDesc carrying its adjudicated caption as one `String` per printed line. Geometry is written in the zone editor's figure track (`b`); the text by `harness fig restore`, out of `review/captions/decision.json` over `proposal.json`. Checked by `harness fig check`; **absence of the file is how the store records "no figures on this page"**, so it never holds an empty one. `docs/apparatus.md` is the track's record.
3. **The caption's reasoning** - `review/captions/proposal.json` (`#llm`, the blind re-read) and `decision.json` (`#ed`). What the reader *said about* a caption stays here; only the ratified text reaches the store. The caption text used to live in a markdown file of its own, keyed by the same block-id suffix; the two then drifted 58 captions apart with nothing reporting it, and that file is gone.
4. **OCR transcript** - `ocr/chukchi-PP-NNN.xml`, the view: `gt/ocr/` where a human
   has been through the page, `mz/ocr/` otherwise. ALTO carrying the zones as
   regions and the lines within them. The regions are no longer useless — they are
   the seven declared types, and they are what stage 3 reads structure out of.
   **The collation pass no longer sees this file at all**: it reads a generated
   page built from `gt/ocr/` by name, and the guard hook refuses it the raw ALTO.
5. **Generated TEI** - `mz/tei/chukchi-PP-NNN.xml`. Derived and gitignored, and
   **there is deliberately no view over the tei pair** the way `ocr/` covers the OCR
   stores: a view exists to give one name to a page's current best reading, and here
   naming the two apart is the whole point. It carries a generation stamp — version
   plus a digest of both inputs — which is what lets `tei diff` tell a difference
   review made from one a regeneration made under it.
6. **TEI** - `tei/chukchi-PP-NNN.xml`. Also the system of record for seam state:
   its `<pb>` is where the printed folio enters the project, and `harness tei ledger`
   folds the committed files into the per-ref ledger the next page is built from.

   **Written by a dispatched collator, one agent per page**, off the queue
   `harness tei queue` writes — the same shape as the ground-truth loop, and for the
   same reason: the contract has to sit in a system prompt for siblings to share it.
   The pass looked serial and was not. Only the *seam* is, and it was never the
   page's work — `@part` is `harness tei seam`'s, written from the page holding both
   ends of the gap, so a collator records the one witness only it has (the first
   line's indent, as `<!-- opens: … -->`) and the coordinator writes the verdict
   after the batch. What a fan-out gives up is `prev_tail` and `expected_folio` on
   every page but the first; `tei reservations` names what that blinded and
   `tei ledger` is where the folio check comes back, over the whole run at once.

   **`claim` puts the working copy here**, copied from `mz/tei/`, because the
   collator has no `cp` in its allowlist and must not have one — a copy it could
   perform is a copy it could perform in the wrong direction, over the baseline that
   is the other half of the diff. That is also why `reconcile` grew a fourth state:
   once claiming creates the deliverable, the deliverable's existence stops meaning
   the agent came back, and `CLAIMED, unedited` is byte equality against the
   baseline saying so.
7. ???
8. PROFIT!
