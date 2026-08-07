# Dispatching a batch of collators

**This is the procedure. The collation contract is not in it** —
`.claude/agents/collator.md` carries the rules, whole, because a subagent's system
prompt is the only block its siblings can share and everything else arrives behind
the turn that varies. Do not restate any of it here. The division is by audience:
that file is read by collators, this one by whoever dispatches them.

## The two texts, and the rule about both

`harness tei queue` prints **the prompt**, and `harness tei claim` prints **the page
block**. Both are rendered from the marker pairs below and **never assembled by
hand** — that was done twice on the reading track and the second time five clauses
reached the agent that existed nowhere in the doc, so the doc described a prompt
nobody sent and the run measured something unwritten.

**The prompt names no page.** Identity of the first turn is what caches, so a ref
written into it costs every sibling the whole shared context. Each collator takes
its own ref with `tei claim`, atomically.

## The loop

    uv run harness corpus state --all --stage ocr-gt --refs  what is ready
    uv run harness tei queue PP-NNN ...      validates, generates any missing
                                             baseline, writes the queue, prints
                                             THE prompt
    …spawn one collator per page with that prompt, unedited and identical,
      staggering the first launch about ten seconds…
    uv run harness tei reconcile PP-NNN ...  what came back
    uv run harness tei reservations PP-NNN ... the batch's open questions, pooled
    uv run harness agents usage              what the fan-out paid

`queue` refuses a page that is already collated, **has no `gt/ocr/` or no
`gt/zones/`**, is marked exempt, or is named twice — and **not** one whose
predecessor is uncollated, which is the whole reason a batch can be dispatched at
all. It also **generates any missing baseline** on its way past: generation is
deterministic and wants no GPU, so a separate step would only be a step to forget,
and a batch queued without baselines fails one page at a time in front of agents
that cannot fix it.

<!-- claim:begin -->

    Claim a page. If you have no collator contract, stop and say so.

<!-- claim:end -->

### The page block `claim` prints

Everything true of one page in particular, and nothing else. The deliverable, the
STOP, the report instruction and the standing rules are standing text and live in
the agent body. Of two copies of a rule, the one in a rendered prompt is the one
that drifts.

<!-- prompt:begin -->

    Your page ref is **{ref}**. Do not touch any other page, and do not claim a
    second: one collator, one page.

    Your working file already exists at `tei/chukchi-{ref}.xml` — a copy of the
    generated draft, put there for you. Read it first; you are reviewing it, not
    writing it.{note}

    Run `uv run harness tei context {ref}` now. It is the whole input contract —
    the folio witnesses, the ToC window, the ratified Tier-1 handles, the line
    indices `@facs` cites — and it is built fresh for this page.

<!-- prompt:end -->

## After the batch

The reading half parallelises; **the seam does not**, and it is yours rather than
any collator's.

1. **`harness tei reconcile PP-NNN ...`** the moment the agents return — `collated`,
   `CLAIMED, unedited`, `CLAIMED, no TEI` (an agent took it and did not come back),
   or `unclaimed`. `unedited` exists because `claim` now creates the deliverable:
   its presence stopped meaning an agent came back, and byte equality against the
   baseline is what tells the two apart. Then **`harness tei diff PP-NNN ...`** for
   the finer question — `gen_comments` is the generator's questions still
   unanswered, and `drifted` says a baseline moved under a review.
2. **`harness tei reservations PP-NNN ...`** over every ref at once, and read the
   rows against each other. One page adrift is a page to re-read; all of them
   leaning the same way is *systemic* — the contract or the spec, not the collators.
   The verb also says what it could **not** check on this batch, and that is not the
   same as a clean report.
3. **The seam, in scan order.** Every page carries an `<!-- opens: … -->` comment
   recording the one witness only the collator had — the first line's indent on the
   image. Read them, then record each gap:

       uv run harness tei seam 1-076 1-077 1-078 --continues --commit
       uv run harness tei seam 1-085 --fresh --commit

   About 70% of text pages open mid-paragraph, so `--continues` is the ordinary
   case. `seam` refuses where the two sides are different kinds — a `<p>` ending one
   page and a `<list>` opening the next — which is exactly the failure a batch
   dispatched out of order can produce, so let it refuse and re-read that page.
4. **`harness tei ledger`** over the run. Under a dispatched batch `expected_folio`
   is null on every page but the first, so the folio had one witness rather than two
   while the pass ran; the ledger is where the second one comes back, and it sees the
   whole run's folios at once rather than one gap at a time.
5. **`harness tei validate PP-NNN ... --all`** last, once the seams are written.

**A reservation the collator raised and nobody answered stays a comment in the
file.** That is the durable state, not a failure to clear a queue.

## If you are collating a page yourself

Read `.claude/agents/collator.md` and follow it; it stands alone, and
`/transcribe-page PP-NNN` is still a legitimate way to do one page. The one thing
that does not carry over is the guard hook, which is frontmatter on that agent — the
read and write rules it enforces mechanically become yours to keep. The seam is
still not the page's: record the `opens:` witness, and run `tei seam` yourself
afterwards as the coordinator.
