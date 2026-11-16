---
name: read-materials-page
description: Read pages of Bogoras's 1900 «Матеріалы» (jesup/bogoras-materials) into review/PP-NNN/proposal.json — dispatch a batch of materials-reader agents off the queue, check what comes back, and hand it to the editor; or do one page yourself. Use when reading, proposing or "doing" pages of the 1900 Materials, or on /read-materials-page PP-NNN. Not The Chukchee's pass — that is rebuild-groundtruth.
---

# Read pages of the 1900 *Materials*

The stores are under `jesup/bogoras-materials/`; run every command from there or
with `--root jesup/bogoras-materials`.

**The reading contract is `.claude/agents/materials-reader.md`, whole**: the pass,
the keying conventions and the editor's rulings. It is not repeated here. To do
a page yourself, follow it as written, skipping only `ocr claim`.

**Dispatching a batch** is `dispatch.md` beside this file: `ocr queue`, one
`materials-reader` per page with the one prompt it prints, `ocr reconcile`. The
text's manifest names its reader (`project.json` `reader`), which is how those
verbs know this track from *The Chukchee*'s.

## Checking a batch, before the editor sees it

The readers cannot see each other, and the editor reads no Russian, so this is
the last look a Russian line gets. Per page:

- `proposal check REF` exits 0, and `corpus normalize` is clean on the batch.
- Every `doubt` is one the contract allows: a mark or letter the rules do not
  cover, or a native form the scan leaves open. A `doubt` on a ruled letter, or
  on Russian, is the reader handing its work on: settle it at the scan.
- Every line whose text departs from both copies has a reason a reader of the
  note could check. A native form that both copies agree on and the reader
  changed is the place to zoom yourself.
- The same name across the batch's pages is spelled one way, or the difference
  is in a `doubt`. Readers in one batch do not see each other's forms, so this is
  the only place two spellings meet before the editor's queue.

Then one review server for the batch (`ocr review …`), and `ocr restore … --commit`
once the editor has saved. **Restore before dispatching the next batch**: the
next lookup sees only restored pages.

## What the editor does with it

The editor's queue on a page is its `doubt` lines and the forms in `native`,
nothing else. Each native form is a model's reading until the editor ratifies it
against the scan (`#llm` until then, whatever both copies say). What a page
contributes to this text's own dictionary is its `native` list, with the gloss
where the prose gives one, in a `semantic` note.

`harness ocr review` shows each line's `native` forms and confines the page's
queue to those lines, the `doubt` lines and any line outside the prose alphabet;
the standing prose is shown dimmed and never saved as the editor's. Its keyboard
is this text's `config/keyboard.json`, phonetic Cyrillic with the notation's
letters (`>` types the circumflex). Each native form carries its standing against
the forms other pages ratified: ✓ *seen*, ≠ a near miss with the ratified
spelling beside it (where to look on the scan), or *new*. A page is in the index
once restored, so restoring after each review session is what grows it.
