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

## Why the contract is the agent body and not a skill

**A reader's context has exactly one block its siblings can share: its system
prompt.** That is the only part sitting ahead of every user turn, and a cache
prefix ends at the first differing byte — so anything after the turn that names
the page is written fresh by every reader, however identical it is.

The reading contract used to be a `skills:` preload. A preloaded skill arrives
as a *message*, behind the task prompt, which put ~41,000 characters of
invariant text on the wrong side of the one thing that varies. Three
measurements, in order of how much each cost to learn:

- **No launch order touches it.** A reader launched concurrently with a sibling
  opened at 13,613 read / 21,080 written; one launched twelve seconds later at
  13,706 / 21,326. Within 1%.
- **A page-less handshake moved it, and paid for it twice.** Sending every
  reader the word `standby` first made the whole preamble identical — the first
  wrote 35,952 and both siblings read it. But the page then had to arrive by
  resume, **and resume re-injects the preloaded skill in full**: two copies of
  43,740 bytes in the transcript, the second behind each reader's own reply, so
  every reader wrote it. Request 2 cost 14,916 tokens for all three, identically
  and separately, against ~4,600 for a reader with no resume.
- **Moving the contract into the agent body beats both**, because the body *is*
  the system prompt. Nothing shared comes after the ref, so the ref can vary
  freely, no handshake is needed and nothing is re-injected.

Fixed overhead for a three-reader batch, requests 1 and 2, measured:

| dispatch | writes |
|---|---|
| skill preloaded, ref in turn 1 | ~121,700 |
| skill preloaded, `standby` handshake | 80,700 |
| **contract in the agent body, ref in turn 1** | **~50,000** |

**Stagger the first launch only.** The first reader writes the system prompt and
the rest read it; ten seconds is enough. That is the whole of the timing rule
now — there is no second phase, no `ready`, and no TTL window to stay inside.

**Check it rather than assume it.** `harness agents usage` groups a batch into
cohorts by opening size: six readers should be one cohort of six, one cold and
five warm, `missed 0`. Six singleton cohorts means a byte varied ahead of the
block, and the `preamble` table names which turn.

The prompt carries a ref and the assertion that the reader holds its own
contract. It does **not** carry the page's measurement: that was a rendered
fourteen-line block a coordinator retyped per reader, which is precisely the
failure this project is organised against — the folio, the entry count and the
wrap list reproduced by an LLM with no downstream check able to see a mistyped
digit. A reader given a count one too high finds a discrepancy, writes
`disagrees:`, and is *credited* for catching something the coordinator invented;
tesseract has no opinion about how many entries a page has. The reader runs
`context` itself, which also ends a staleness bug nobody had hit: a pasted block
is a snapshot, and a page re-measured after dispatch would be read against
numbers that no longer describe it.

One thing that moves the number and is nobody's fault: readers write to
`.claude/agent-memory/moll-reader/`, and the memory index is in their system
prompt. When it changes the prefix changes and everything after it is re-cached,
so a batch following one where a reader recorded something pays a full write.
That is the cost of the memory channel, not a defect in it — and it is now a
cost against the whole ~36k system prompt rather than 13.7k of it, which is the
price of having moved the contract into the shared block.

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
  contract in the agent body would misfire on every line of them. The medial-stem
  appendix has its own pass and its own write-up.

## What the prompt carries, and what it deliberately does not

**The standing half lives in `.claude/agents/moll-reader.md`, not here**, and the
split is by what varies. The agent definition carries everything true of *every*
page — the whole reading contract, the loop, the Bash surface, the hard rules,
the report shape. **The rendered prompt carries the ref once and one assertion,
and the assertion has no ref in it.** So the only thing that varies across a
batch is eight characters, and eight characters that fail loudly when wrong.

It carried six lines more than that until the contract moved. They were the
deliverable path, the STOP, the Read/Write paths and the report instruction —
every one of them already standing in the agent body, and the ref repeated in
four of them. Restating standing text in a rendered prompt is the duplication
this repo treats as a defect, and it is the worse half of it: the copy in the
prompt is the one that drifts, because it is the one a coordinator retypes. A
prompt should name what varies and assert what it expects; anything else in it
is a second normative text with a shorter half-life than the first.

**The template is not in the Python.** It sits below, delimited by the `page`
marker pair, and `entry_bounds.py` only substitutes and refuses. A template copied into code is a second normative text
that drifts from the first, and the drift is invisible because both look
authoritative. The same reasoning put the collation prompt in `harness tei
context` and the reading prompt in `harness ocr dispatch`.

A marker counts **only on a line of its own**, because this file explains its own
delimiters. A substring search finds the sentence describing a template before it
finds the template, and returns the explanation as the prompt — which is what
happened the first time a second marker pair was added here, and which printed a
paragraph of prose to a coordinator as though it were a reader's instructions.

What the split costs is a new way to be wrong, and it is this repo's oldest one:
**a reader dispatched under the wrong agent type gets none of the standing half,
and nothing in the prompt would look amiss** — a role living only in how the
thing was spawned, the same fault as a role living only in a directory name.
Nothing inside a task can see its own `subagent_type`, so the template opens by
asserting what it expects the reader to already hold and telling it to stop if
it does not. That assertion is the only witness available, and it costs two
lines of an otherwise bare prompt.

That check has already earned itself once, under the older arrangement where the
contract was a preloaded skill. A reader started with `claude --agent` rather
than by dispatch reported the pass doc absent and stopped: the `skills:`
frontmatter is honoured on the dispatch path and appears not to be on that one.
The stop was correct and the temptation was to write a recovery path around it —
"read the skill yourself and carry on" — which would have turned a missing shared
prefix into a silent runtime branch and hidden the very thing this file measures.

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

    uv run python scratch/chukchi/entry_bounds.py reconcile moll-023 moll-024 moll-025
    uv run python scratch/chukchi/entry_bounds.py witness moll-023 moll-024 moll-025
    uv run python scratch/chukchi/check_entries.py

`reconcile` first, and it is the only witness over how the refs were dealt. `dispatch` refuses a
ref named twice on the way out; this checks what came back, because **a
duplicated or skipped ref is a *valid* ref** and so fails silently everywhere
else — two readers on one page overwrite each other's file and the batch is one
page short, with nothing downstream able to say which page went missing. Exit 1
names the refs that produced no table.

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

<!-- page:begin -->

    Your page is **{ref}**. Do not touch any other page.

    Your standing instructions are your agent definition, and they are the
    whole job: the loop, the deliverable, what to report. **If you have not
    been given them, you were dispatched as the wrong agent type — stop and say
    so rather than reading a page without them.**

<!-- page:end -->

<!-- claim:begin -->

    You are a `moll-reader`. Your page is not named here: run

        uv run python scratch/chukchi/entry_bounds.py claim

    and it will print one ref, which is yours and nobody else's. Read that
    page and no other. If it prints nothing, the queue is empty — stop and say
    so rather than choosing a page yourself.

    Your standing instructions are your agent definition, and they are the
    whole job: the loop, the deliverable, what to report. **If you have not
    been given them, you were dispatched as the wrong agent type — stop and say
    so rather than reading a page without them.**

<!-- claim:end -->
