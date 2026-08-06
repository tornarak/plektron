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
   `data/readings.md` and are not body text.

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
   draft only, because the project already holds a human reading of it in
   `data/readings.md`, and it remains legitimately citable.

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
   names both models and both sha256s.

   **A line `blla` finds outside every zone is kept, not dropped**, assigned to no
   region and counted as `lines_outside_zones`. Artwork produces these and they are
   visible junk; a dropped line is invisible, and that asymmetry is the whole
   reason for the rule. A high count on an ordinary text page means the artwork was
   mis-zoned or a zone is missing — the same finding `zones check --ink` reaches
   from the other side.

3. **Collation** — An LLM (usually Sonnet-class) receives 1) the image of the original scan, 2) the OCR plaintext for that page, and 3) a machine-generated summary with useful contextual data (relevant TOC entries, list of page figures, etc.). It outputs TEI for that page. Built by `harness tei context`; gated by `harness tei validate`. Everything the model receives is deterministic and precomputed — it never re-derives ToC ids, figure zones, or detector flags.
4. **Annotation** — TBD
5. **Compilation** — TBD

## Final Product

1. **Original Scan Page** - `scans/chukchi-PP-NNN.png`
2. **Figure geometry** - `gt/fig/chukchi-PP-NNN.xml`. ALTO containing only `GraphicZone` and `GraphicZone-FigDesc` blocks. No lines, no text.
3. **Figure captions** - `data/readings.md`, keyed `1-123|<zone-id suffix>`. The only caption store.
4. **OCR transcript** - `ocr/chukchi-PP-NNN.xml`, the view: `gt/ocr/` where a human
   has been through the page, `mz/ocr/` otherwise. ALTO carrying the zones as
   regions and the lines within them, dumped to plain text for the collation pass.
   The regions are no longer useless — they are the seven declared types.
5. **TEI** - `tei/chukchi-PP-NNN.xml`. Also the system of record for seam state:
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
6. ???
7. PROFIT!
