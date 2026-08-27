---
name: rebuild-groundtruth
description: Dispatch and adjudicate a batch of readers over Bogoras, turning rasters into line-keyed proposals and then into ALTO ground truth in gt/ocr/. Use for the ground-truth rebuild, the correction/review workflow, or /rebuild-groundtruth. The reading contract itself lives in the groundtruth-reader agent, not here. Not the TEI collation pass — that is transcribe-page.
---

# Run a batch of readers over the rebuild

**This is the coordinator's document. The reading contract is not in it.**

> A reader's context has exactly one block its siblings can share — its system
> prompt, the only part ahead of every user turn. A `skills:` preload arrives as a
> *message*, behind the turn that varies, so every reader writes it in full; and
> resuming an agent re-injects a preloaded skill whole, which ate half of what a
> two-phase handshake saved. The agent body **is** the system prompt, so the
> contract lives there. Measured on the sibling pass over Moll: ~118k tokens of
> fixed overhead for three readers, down to ~50k.

So `.claude/agents/groundtruth-reader.md` carries the loop, the image ladder, the
proposal contract, the hard rules, and — transcluded whole, gated by
`harness/tests/test_transclusion.py` — the reading checklist and `keying_spec.md`.
**Do not restate any of it here.** The division is by audience: that file is read by
readers, this one by whoever dispatches them, and neither repeats the other.

## Dispatching

`dispatch.md`, beside this file, is the whole procedure: what `queue` refuses and
why each refusal exists, what the two templates carry, and what to check when the
batch returns. In short:

    uv run harness ocr predict PP-NNN ...     in the parent — it wants the GPU
    uv run harness ocr queue PP-NNN ...       validates, writes the queue, prints
                                              THE prompt
    …spawn one groundtruth-reader per page with that prompt, unedited and
      identical, staggering the first launch about ten seconds…
    uv run harness ocr reconcile PP-NNN ...   what came back
    uv run harness proposal marks PP-NNN ...  the batch read distributionally
    uv run harness agents usage               what the fan-out actually paid,
                                              and what its context was made of

**Profile the batch before the transcripts age out** — they live in `/tmp`, and
every change to the prompt or the guard is an experiment whose control arm was
the batch before it. `dispatch.md`'s "Profile the batch" section names the five
rows worth reading and what a rise in each one means.

**The prompt names no page.** Each reader runs `ocr claim`, which takes the next ref
off the queue atomically and prints that page's survey. Identity of the first turn
is what caches, so a ref written into a prompt costs every sibling the whole shared
context — which is why `ocr dispatch`, which rendered one prompt per page, is gone.

The reading half parallelises; **the adjudication half does not**, so the human
takes the pages one at a time afterwards, through one review server for the whole
batch.

## After the batch: adjudicate and restore

This half is a human's, with you assisting. Nothing here is a reader's job, which
is why none of it is in the agent body.

1. **`harness proposal marks PP-NNN ...` over every ref at once**, the moment the
   agents return, and read the per-ref rows against `scope: ALL`. One page adrift is
   a page to re-read; all of them leaning the same way is *systemic* — the prompt or
   the spec, not the readers. `dispatch.md` holds what each arm means.
2. **Start the review server yourself** and hand over a URL — don't ask for a
   command to be run. It serves on loopback and blocks, so run it in the background:

       uv run harness ocr review 2-046 2-047      (run_in_background: true)

   Then give them `http://127.0.0.1:8731/` and report what the readers flagged.
   **Several pages go in one server**, which is the normal shape after a fan-out.
   One page is on screen at a time, reached by navigation — the pages are never
   merged into one document, because a field belonging to a page other than the one
   the reviewer thinks they are keying is this pass's oldest and worst failure.
   **Done** advances to the next page wanting a decision and stops the server only
   on the last, so **the task exiting is the signal that the batch is adjudicated**.
   A page counts as adjudicated when its `decision.json` exists, read off disk per
   request, so re-running the command resumes rather than restarts.

   **Never `pkill` it.** That means interrupting the human to confirm a kill, and it
   is how this loop used to leave a server bound to a page that had since been
   restored — which is how a later save lands on stale text. Foreground is not an
   option either: a review outlasts the command timeout.
3. **`harness corpus normalize review/PP-NNN/decision.json`** before restoring. The
   adjudicator can introduce the same drift classes typing corrections in the
   browser — composed accents, French spacing, a stray lookalike — and it is
   `decision.json`, not the proposal, that becomes ground truth.
4. **`harness ocr restore PP-NNN ... --store mz`** — and run it; **a save is not the
   end of the pass.** A page can sit adjudicated-but-unwritten and look finished
   from outside. Bare `restore` previews `edits`, `geometry_drift` and
   `text_mismatch` and writes nothing; `--commit` writes `gt/ocr/`. `geometry_drift`
   and `text_mismatch` must both be empty. With more than one ref it dry-runs every
   page before writing any, so an unadjudicated line on the second cannot arrive
   with the first already replaced.

   No `--force` on a restoration: the target does not exist, and the guard demanding
   it is the one protecting exactly that.

   **Read `edits` as the page's error profile, not only as a save-check.** It is the
   full proposal-vs-decision diff, so it names which class from `keying_spec.md` §5
   each miss belonged to. A recurring class is the signal to strengthen the
   checklist — §5's own text is the record of past diffs doing exactly that.
5. **`harness ocr clean PP-NNN ...`** last, and only then. The images are the record
   of what the readers actually looked at.

**Do not rewrite an adjudicated proposal's `text` fields.** `edited` is computed
against the proposal, so revising it retroactively erases the measurement — which is
how `1-074`'s was spent.

**Check the returned reports against the raster** where a reader makes a claim about
a Tier-1 disposition. `dispatch.md` records what a batch has actually got wrong, and
the classes recur.

## If you are reading a page yourself

Read `.claude/agents/groundtruth-reader.md` and follow it; it stands alone. The one
thing that does not carry over is the guard hook, which is frontmatter on that agent
— the blindness and write rules it enforces mechanically become yours to keep.
