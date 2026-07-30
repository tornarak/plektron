---
name: transcribe-page
description: Produce the TEI page file for one page of Bogoras from its CATMuS draft and scan. Use when asked to transcribe, collate, or "do" a page, or on /transcribe-page PP-NNN. Covers the full loop - context, drafting, validation, questions to the human.
---

# Transcribe one page (OCR → TEI collation pass)

You are the driver. The scripts are your instruments and your gate; the human
is your court of appeal. **Read `transcriber_harness.md` (repo root) in full
before your first page of a session** — its prompt section is the normative rule set;
this skill only sequences the work.

## Loop, per page ref PP-NNN

Pages are named by **part and scan index** — `1-048` — and never by a bare page
number. NNN is a scan index, not a printed folio; the two aren't derivable from
each other, so the CLI rejects a bare integer rather than guess which of the
three parts you meant.

1. `uv run harness context PP-NNN` — the input contract. Do not
   re-derive anything it supplies (ToC ids, detector flags, figure zones).
   Two of its fields are *predictions*, not facts, and are routinely null:
   `expected_folio` (from the last transcribed numbered page) and the
   `open`/`starts_here` marks on `toc_window`. Read them as a place to look
   first. The page decides.
2. Read the page image at `page_image` with the Read tool. Read draft and
   image **together**; the draft is a starting point, not a source of truth.
3. Draft the TEI to `output_path` per the harness rules. All of them. The
   firewall rules especially: no character inside a Tier-1 `xml:lang` element
   is ever altered, no matter how obviously wrong.
4. `uv run harness validate PP-NNN`. ERRORS: fix and re-run — do not
   argue with the gate; if you believe the gate itself is wrong, that is a
   question for the human, not a license. WORKLIST lines are expected on
   form-dense pages; leave them.
5. Re-read your own output once against the image before declaring done.

## Questions and reservations — when to stop and ask

You are encouraged to ask, and required to in these cases:

- Any unresolved-comment situation the harness defines (heading with no ToC
  match and no list/table; expected milestone not found; content shape that
  fits neither pattern; likely foreign-term variant).
- A folio disagreeing with a non-null `expected_folio`. The printed folio wins,
  but the mismatch is still a question: usually the prediction drifted,
  occasionally the ToC alignment is off.
- A folio you cannot read at all. Rare on these scans, and `<pb/>` is not the
  answer — that asserts the page was never numbered. Comment and ask.
- Anything where the harness would have you guess.

Ask **batched, at the end of a drafting pass**, not one interruption per
doubt: emit the file with the harness's comment forms in place, then present
the human a numbered list of the open comments with your reading of each and
what you'd need to resolve it. Apply their answers, note each resolution
inside the relevant comment (`resolved: <answer> per editor`), re-validate.
A reservation the human hasn't answered stays a comment — durable in the
file — never a silent decision.

## What you never do

- Answer your own question by picking the plausible option. Fluent nonsense
  is the failure mode that matters; "unresolved" is a valid deliverable.
- Touch `@part`/`@prev`/`@next`/`xml:id`, emit `<lb/>`, or mint entity ids.
- Edit anything under `ocr/`, `scans/`, `fig/`, or `data/`, or touch
  `boundaries.json`.
- Copy `expected_folio` into `<pb n=>` because it was supplied. It is the value
  your folio is checked *against*; a folio invented here is one the rest of the
  volume inherits through the ledger.
- Proceed past a FAILing validator.

## Session hygiene

One page per task. After a page passes and its questions are settled, commit
(`git add tei/<stem>.xml && git commit -m "tei: PP-NNN collation pass"`) and
clear context before the next page — a fresh read of each page is a feature;
carried impressions from the previous page are not context, they're
contamination.

What *does* carry across pages carries through the committed file, not through
your head: `uv run harness ledger` folds every committed `<pb>` and
milestone into the seam ledger that the next page's context is built from. So
the commit is the handoff. A consequence worth knowing: working in scan order
gives each page a live `expected_folio`, while jumping around the volume gives
nulls until the gaps fill in. Nulls are correct, not a failure — they just mean
more folios read off the image and fewer cross-checked.
