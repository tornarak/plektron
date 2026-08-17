---
name: transcribe-page
description: Collate pages of Bogoras into TEI — dispatch a batch of collators off the queue, or do one page yourself. Use when asked to transcribe, collate, or "do" a page or a range, or on /transcribe-page PP-NNN. The coordinator's half; the reading contract lives in .claude/agents/collator.md.
---

# Collate pages (OCR → TEI)

**This is the coordinator's document. The collation contract is not in it.**

> A collator's context has exactly one block its siblings can share — its system
> prompt, the only part ahead of every user turn. A `skills:` preload arrives as a
> *message*, behind the turn that varies, so every collator writes it in full.
> The agent body **is** the system prompt, so the contract lives there. Measured on
> the sibling pass over the raster: ~118k tokens of fixed overhead for three agents,
> down to ~50k.

So `.claude/agents/collator.md` carries the loop, the output contract, the firewall,
language spans, structural ids and the self-check. **Do not restate any of it here.**
It carries **no** transcluded text, which is a decision and is gated as one by
`harness/tests/test_transclusion.py`: it held `keying_spec.md` whole while the pass
authored Tier-1 text from a plaintext draft, and a rule copies the adjudicated form
in now. The reader still carries the spec, because it reads glyphs off the raster. The division is by audience: that file is read by collators, this one by
whoever dispatches them.

`dispatch.md`, beside this file, is the procedure and the two rendered texts.

## The shape of the pass

Per page it is one agent, one file: `tei/chukchi-PP-NNN.xml`, validating, plus a
report. What it does **not** do is the seam.

**Only the seam is serial, and it was never the page's work anyway.** `@part`,
`@prev` and `@next` are `harness tei seam`'s, written from the page that holds both
ends of the gap. So the per-page pass produces a body and a *witness*; you produce
the link, in scan order, once the batch is in.

Of the seam's three witnesses, two survive into the TEI — the previous page's tail
is in its own file, this page's opening text is in this one — and the third does
not. The first line's indent lives on the raster, which the collator had open and
you do not. That is what `<!-- opens: … -->` is for, and it is why every page must
carry one.

## Dispatching

    uv run harness corpus state --all --stage ocr-gt --refs   what is ready
    uv run harness tei queue PP-NNN ...       validates, generates any missing
                                              baseline, writes the queue, prints
                                              THE prompt
    …spawn one collator per page with that prompt, unedited and identical,
      staggering the first launch about ten seconds…
    uv run harness tei reconcile PP-NNN ...   what came back
    uv run harness tei reservations PP-NNN ... the open questions, pooled
    uv run harness entity list                what the batch proposed
    uv run harness agents usage               what the fan-out paid

**The prompt names no page.** Each collator runs `tei claim`, which takes the next
ref off the queue atomically. Identity of the first turn is what caches, so a ref
written into a prompt costs every sibling the whole shared context.

`queue` refuses a page that is already collated, **has no `gt/ocr/` or no
`gt/zones/`**, is marked exempt, or
is named twice — and refuses a batch whose agent file is missing, since the agent
body *is* the contract. It does **not** refuse a page whose predecessor is
uncollated: that is the change that makes a batch possible at all.

## What a dispatched batch gives up, and where it comes back

Two nulls, both narrow, both paid back afterwards. Say them out loud when you report
the batch, because neither is visible in a page that validates.

- **`prev_tail` is null on every page but the first.** The cost is one case: a list
  running across the gap, where `<item n="14">` is what tells the next page its
  unnumbered opening item is 15. Collators are told to leave it unnumbered and
  comment; `tei reservations` surfaces those as `list_unresolved`, and you re-read
  them against their predecessors.
- **`expected_folio` is null likewise**, so the folio had one witness rather than
  two while the pass ran. `tei ledger` is where the second comes back, and it is the
  better check: it folds the whole run at once instead of one gap at a time.
  `tei reservations` says how many pages were blind rather than letting a clean
  report imply the folios agreed.

The ToC window does *not* degrade: `tei context` centres it on the page's own
running title when there is no prediction, which is better evidence than the
prediction was.

## After the batch

The collating half parallelises; this half does not.

1. **`harness tei reconcile PP-NNN ...`** the moment the agents return — `collated`,
   `CLAIMED, unedited` (took the page, changed nothing), `CLAIMED, no TEI` (took the
   page, did not come back), or `unclaimed`. **`unedited` is new and is why the
   check still works**: `claim` now creates the deliverable, so its presence stopped
   meaning an agent came back — a collator that died on its first turn leaves a file
   byte-identical to the baseline, and only comparing them says so.
   `harness tei diff` is the finer version of the same question: `gen_comments`
   counts the generator's questions still unanswered.
2. **`harness tei reservations PP-NNN ...`** over every ref at once, and read the
   rows *against each other*. One page adrift is a page to re-read; all of them
   leaning the same way is systemic — the contract or the spec, not the collators.
   This is the whole reason the verb exists: twenty page files read one at a time
   are twenty separate judgements, which is exactly what a per-page pass cannot do
   for itself.
3. **The entities the batch proposed**, before the seam, because a duplicate is
   cheapest to fix while both pages are still in view:

       uv run harness entity list          proposed sort first
       uv run harness entity check         collisions, and the store's coherence

   Collators propose at `status: proposed`, which no rule links. Read each entry
   against the page its `since:` names and `entity ratify` what holds up —
   ratifying is what lets `tei generate` link the form on every other page, so it
   is the act that has to be a human's. **Read them against each other too**: two
   collators meeting the same man on two pages mint two slugs for him, and only
   you can see both. Merge before ratifying, never after — a ratified id is one
   other pages' `@ref` may already point at.

   A proposal nobody ratifies is a durable, harmless state, not a failure.
4. **The seam, in scan order.** Read the `<!-- opens: … -->` comments, then:

       uv run harness tei seam 1-076 1-077 1-078 --continues --commit
       uv run harness tei seam 1-085 --fresh --commit

   About 70% of text pages open mid-paragraph, so `--continues` is the ordinary
   case. **`seam` refuses where the two sides are different kinds** — a `<p>` ending
   one page and a `<list>` opening the next — which is precisely the failure a batch
   collated out of order can produce. Let it refuse and re-read that page; do not
   reach for a way around it.
5. **`harness tei ledger`** over the run: the folios should be consecutive.
6. **`harness tei validate PP-NNN ... --all`** last, once the seams are written.
7. **Commit the batch once**, after the seam sweep. A page committed mid-batch has
   no seam and looks finished from outside.

**A reservation nobody answered stays a comment in the file.** That is the durable
state, not a queue you failed to clear. Answer what you can, and note each
resolution inside the comment it settles — `resolved: <answer> per editor` — so the
next reader of that page sees the question and its answer together.

**Do not rewrite a collator's output to fix something you could have asked about.**
The file is the record of what one pass produced from one page; revising it silently
is how a measurement becomes an assertion.

## If you are collating a page yourself

`/transcribe-page PP-NNN` is still a legitimate way to do one page. Read
`.claude/agents/collator.md` and follow it; it stands alone. Two things do not carry
over: the guard hook, which is frontmatter on that agent — the read and write rules
it enforces mechanically become yours to keep — and the division of labour. You are
both parties, in that order: collate the page and record the witness first, then put
the contract down and run `tei seam` as the coordinator.
