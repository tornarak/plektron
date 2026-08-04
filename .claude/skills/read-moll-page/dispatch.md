# Dispatching the reading to subagents

The reading parallelises cleanly: nothing on a page depends on anything on any
other except at its top and bottom edges, and those are handled in the contract.
The checking does not — `witness`, `check_entries` and the order rulings all
want the whole batch at once, and a human at the end of them.

**One agent per page, `subagent_type: moll-reader`.** Six at a time has been run
and is comfortable; the first batch of six returned 224 entries with one reading
error in them.

    uv run python scratch/chukchi/entry_bounds.py dispatch moll-023 moll-024 moll-025

That prints one prompt per page. Hand each to one `moll-reader`, unedited.

## Stagger the first launch only, and know what it can and cannot buy

**Launch one reader, wait ~10 s for its opening call to land, then fan out the
rest.** Stagger the *first* one and nothing else: the rest can go together.

A reader's context arrives in this order, which the task transcripts show
directly. Before it acts it has had exactly two conversation turns:

1. the rendered **task prompt** — ~1,800 chars, *different for every page*
2. the preloaded **`SKILL.md`** — ~39,000 chars, *identical for every page*

Everything ahead of those — core system prompt, tool schemas, `CLAUDE.md`, this
agent's body, its memory index — is the system prompt, and is what a reader
reads from cache when it reads anything: **~13.7k tokens**. The remaining
**~21.3k it writes** is the skill plus the prompt.

That split decides what timing can do.

**It cannot touch the ~21.3k.** The largest invariant block in the context sits
*behind* the one block that varies, so two sibling readers diverge at the page
ref and never reconverge; the skill is rewritten in full for every page whatever
the launch order. Measured: a reader launched concurrently with a sibling opened
at **13,613 read / 21,080 written**, one launched twelve seconds later at
**13,706 read / 21,326 written**. Within 1%.

**It may well buy the ~13.7k, and that is what the rule is for.** Concurrent
siblings can each miss and each write that segment, where a stagger lets the
first write it and the rest read it — (N−1) × ~13.7k on a batch of six. Not yet
established: both batches run so far were two readers, and in both the second
read the segment whether it launched with the first or after it, which is
equally consistent with "the stagger worked" and with "it was already warm."
**Two agents cannot separate those; the next batch of six can** — launch all six
together once and check how many opened with a read of ~13.7k. Until then the
rule costs ten seconds and is worth keeping on the chance.

The saving is small against a large allowance and that is not the reason to keep
it. This pass is meant to run on cheaper plans and other platforms, where the
same fixed prefix is paid at every scale.

**The real lever is not timing.** A cache prefix ends at the first differing
byte, so shrinking the task prompt or moving the page context into a file the
reader opens saves nothing — a three-token difference is as fatal as a
three-thousand-token one. The only way to reach the ~21.3k is to move invariant
content *ahead* of the variation: out of the preloaded skill and into the agent
definition body, which is in the system prompt. That is worth ~11k of cache
write per page, over a million across the rest of the book, and it is not free —
`SKILL.md` is the pass's single home for the reading contract, so a split has to
be by *role* (standing contract vs. reference consulted on demand) or it becomes
the duplication this repo treats as a defect. It also assumes the agent body is
itself inside the cached ~13.7k, which is suggested by the numbers holding
steady across batches but is not established.

One thing that *does* move the number: readers write to
`.claude/agent-memory/moll-reader/`, and the memory index is in their system
prompt. When it changes the prefix changes and everything after it is re-cached,
so a batch following one where a reader recorded something pays a full write.
That is the cost of the memory channel, not a fault in it.

## Mark the batch first

The reader's input is `moll-scans/marked/`, not the scan: the page with the
measurement drawn on it, entries tinted and numbered in reading order. A page
with no marked raster has nothing for the reader to key against, so `dispatch`
refuses rather than warns.

    uv run python scratch/chukchi/entry_bounds.py mark moll-023 moll-024 moll-025

Name the refs in one call. `mark` re-measures each page from the ink, and a
shell loop pays the whole measurement per page for no reason — the same argument
that makes `zoom` take several labels.

## What `dispatch` refuses, and why each refusal exists

The refusals are the survey made mechanical. Each names the command that fixes
it, because a prompt is a thing you are about to spend an agent on and "probably
fine" is not a state it should be possible to dispatch from.

- **No marked raster.** Nothing to read. Run `mark`.
- **`entries/moll-NNN.md` already exists.** The page has been read. Re-reading it
  is legitimate — a reader died mid-task, a batch came back wrong — but it is a
  decision, not a default, and the second reading is *not* independent of the
  first if the first is still on disk where its author can consult it. Move the
  old file aside and say in the report that you did and why.
- **Outside the dictionary body.** Folios 9–163 (`moll-010` … `moll-164`). The
  front matter and the three appendices have a different row shape, and the
  contract in SKILL.md would misfire on every line of them. The medial-stem
  appendix has its own pass and its own write-up.

## What the prompt carries, and what it deliberately does not

**The standing half lives in `.claude/agents/moll-reader.md`, not here**, and the
split is by what varies. The agent definition carries everything true of *every*
page — the preloaded pass doc, the loop, the Bash surface, the hard rules, the
report shape. The rendered prompt carries only the ref and the page's own
context block. Two things follow: a clause edited in the agent file reaches the
next reader with no rendering step, and what is page-specific is legible as such
rather than buried in standing prose.

**The template is not in the Python.** It sits between the `<!-- prompt:begin
-->` and `<!-- prompt:end -->` markers below, and `entry_bounds.py` only
substitutes and refuses. A template copied into code is a second normative text
that drifts from the first, and the drift is invisible because both look
authoritative. The same reasoning put the collation prompt in `harness tei
context` and the reading prompt in `harness ocr dispatch`.

What the split costs is a new way to be wrong, and it is this repo's oldest one:
**a reader dispatched under the wrong agent type gets none of the standing half,
and nothing in the prompt would look amiss** — a role living only in how the
thing was spawned, the same fault as a role living only in a directory name.
Nothing inside a task can see its own `subagent_type`, so the template opens by
asserting what it expects the reader to already hold and telling it to stop if
it does not. That assertion is the only witness available.

Three clauses that were in the hand-assembled prompts and are now standing, in
the agent file, because each was written out by hand every time and one of them
was eventually forgotten:

- **Blind to `moll-scans/ocr/`.** Now a hook, not a sentence. The whole design
  rests on it: every error class with no internal signal — a dropped `ь`, an
  invented double consonant — is found by tesseract or not at all, and only
  because tesseract cannot have made the reader's mistake.
- **`CLAUDE.md` does not apply to this book.** The reader loads it whether or
  not it is relevant (there is no frontmatter field that suppresses it), and it
  is the most authoritative-looking document in the context of an agent reading
  a different book in a different script.
- **Write nowhere but the entry store.** Also a hook now.

The guard does not only block: where a rule is an **allowlist** — the two
`entry_bounds.py` verbs, `identify`/`convert` without an enhancement operator,
a write into the entry store or the agent's memory — it returns
`permissionDecision: allow` and the call runs unprompted. A checked call handed
back to the normal permission flow asks the human anyway, and six readers each
cropping a few lines is a stream of prompts about calls something has already
verified; the fifth is not read as carefully as the first, which is how a real
one gets waved through.

**The targets are enumerated too, not just the tools.** A rule that names
`identify` and `convert` but no paths leaves `identify moll-scans/ocr/…` open,
and that is the blindness rule defeated through a different tool name. So every
path argument — and every `Read` — must land inside the pass's own trees, `..`
anywhere is refused outright rather than resolved, and `convert`'s output
argument specifically must be `moll-scans/crops/`. That last one is not tidiness:
a crop is the evidence behind a reading, and a citation to a temp directory is
one the person adjudicating the page cannot open. `dispatch` creates `crops/`,
because the reader's Bash surface has no `mkdir` in it and an absent directory
would reach it as a failure it could do nothing about.

One consequence worth knowing: a reader can no longer `Read` `CLAUDE.md`. It is
injected into its context regardless, and its standing brief already says that
document describes a different book — so the block costs nothing and closes the
one path by which a reader could go looking for corpus rules to apply.

## After the batch returns

In this order, because each answers a question the one before it raises:

    uv run python scratch/chukchi/entry_bounds.py witness moll-023 moll-024 moll-025
    uv run python scratch/chukchi/check_entries.py

`witness` diffs each keyed headword against the OCR store. **A flag is a
question, not a verdict** — of 26 uncorroborated headwords in one ten-page batch,
9 were real errors and the rest were tesseract failing in ways it fails
characteristically (it cannot read bold `ё` at all). Adjudicate the unlabelled
rows; a row labelled with a known quirk is usually not worth a look, but spot-check
one per batch rather than trusting the label blind — a page printing a genuine
`ь` where the reader keyed `ъ` produces a row indistinguishable from the labelled
ones.

`check_entries` sees order, duplicates and contract faults. It calls a
`disagrees:` comment stale purely on the row count, so a reader who found two
offsetting bracket faults reports as stale and is right: read the comment.

**Read the register in `scratch/CATALOG.md` before adjudicating.** It is the
consolidated account of what actually goes wrong on this book and what catches
each class — including the two classes no per-headword comparison can reach,
page-wide accent loss and bracket faults.

<!-- prompt:begin -->

    You are the `moll-reader` agent, reading exactly one page of Moll &
    Inenlikej 1957, «Чукотско-русский словарь», in the repo at {root} (work in
    place; do not create a worktree).

    Your page is **{ref}**. Do not touch any other page.

        Read   scratch/chukchi/moll-scans/marked/{ref}.png
        Write  scratch/chukchi/moll-scans/entries/{ref}.md

    Your standing instructions — the preloaded pass doc, the loop, your Bash
    surface, the hard rules and what to report — are in your agent definition,
    and this prompt does not repeat them. **If you have not been given them, you
    were dispatched as the wrong agent type: stop and say so rather than reading
    a page without them.** What follows is only what is true of {ref} in
    particular.

    {context}

    Deliverable: `scratch/chukchi/moll-scans/entries/{ref}.md`, one row per
    entry in the numbered reading order. STOP THERE — you do not check your own
    work, and the witness pass over the batch is not yours.

    Report back in the four parts your standing instructions specify: the page,
    the doubts you could not close, the zooms, and what the pass made harder
    than it needed to be.

<!-- prompt:end -->
