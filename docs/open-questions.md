# Open questions

The standing record of what is deliberately unresolved. An entry leaves this
file by being settled, and says so when it goes; a confident reason standing
in for an open question is the same failure as a confident reading standing
in for an unread glyph.

## Open

- **No part is named by a part title page** — the surrogate has none. Parts II and III
  are named by librarian typescript over an archival sheet that contradicts itself
  (typed 1907/1909 against a printed 1904 imprint), and part I only by the AMNH
  catalogue record, which is its single witness. The catalogue corroborates II and III,
  so those are settled; part I is not, and a copy with part title pages would beat all
  of it. See the teiHeader's `listBibl`, where `@source` points at the catalogue and
  `@resp` is reserved for the model's reading of the rasters.
- **The AMNH catalogue record independently corroborates two apparatus stores**, having
  been consulted for neither: `"Authorities quoted": p. 3-9` against
  `data/authorities.json`'s folios 3–9, and `35 pl.` against `data/loi.json`'s plates
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
  the evidence still wanted.** 69.8% of text pages qualify, so the next one in
  scan order will probably do.
- **A note running across a page seam has no markup.** `<note>` is nested rather
  than a top-level body element, so `seam`'s two-sided-edge machinery does not
  reach it, and the pilot set has no attested instance — so it is deliberately
  unresolved rather than built for. The orphan-foot-text comment names no pass.
- **Corpus-stable identity is not settled**, and the id scheme deliberately does
  not provide it: ordinals move when content is inserted, so a pointer held
  outside the page would break silently. These ids are stable within a page file's
  current version and nothing outside the corpus may cite one. The annotation
  passes need their own scheme, over finished TEI. What has changed is the *scope*
  of what is deferred: a Tier-1 name's **category** is now recorded by the
  collation pass, because only a reader of the page can see it, and only the
  **identity** waits — `@ref`/`@key` are gate errors until that scheme exists.
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
- **`data/toc.json` (315 entries) records no provenance.** `loi.json` and
  `authorities.json` both name the scans they were read from; this one does not,
  and the printed ToC's scan range is not recoverable from the file. Someone who
  knows should write it down — every other apparatus store is auditable back to a
  page and this one is not.
- **The span diff's second witness is back, and it is `mz/ocr/`.** `end-of-eval/`
  was the recognizer store, it was deleted, and the diff refused rather than
  compare a proposal against the ground truth it produced. This entry used to say
  "if a second witness is ever wanted again, it links into `ocr/` from its own
  store" — which is exactly what `ocr predict` built. `harness ocr review REF
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
