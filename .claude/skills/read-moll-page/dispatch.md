# Dispatching the reading to subagents

The reading parallelises cleanly: nothing on a page depends on anything on any
other except at its top and bottom edges, and those are handled in the contract.
The checking does not — `witness`, `check_entries` and the order rulings all
want the whole batch at once, and a human at the end of them.

**One agent per page, `subagent_type: moll-reader`.** Six at a time has been run
and is comfortable; the first batch of six returned 224 entries with one reading
error in them.

    uv run python scratch/chukchi/entry_bounds.py dispatch moll-023 moll-024 moll-025

That prints **one standby prompt for the whole batch and one page block per
page**, headed as two phases. Every reader gets the standby prompt first, byte
for byte the same; the page block follows once it has answered `ready`. Hand
both over unedited — the next section is why the order matters and what editing
one copy costs.

## Dispatch in two messages, and why the page ref comes second

**Send every reader the same page-less standby prompt, wait for `ready`, then
deal out the pages.** `dispatch` prints the standby prompt once and the page
blocks after it, headed as two phases, for that reason.

A reader's context arrives in this order, which the task transcripts show
directly. Before it acts it has had exactly two conversation turns:

1. the rendered **task prompt**
2. the preloaded **`SKILL.md`** — ~41,000 chars, *identical for every page*

Everything ahead of those — core system prompt, tool schemas, `CLAUDE.md`, this
agent's body, its memory index — is the system prompt. A cache prefix ends at
the first differing byte, so **a page ref in turn 1 puts the largest invariant
block in the context behind the one thing that varies**, and every reader
rewrites the skill in full. That is not a scheduling problem and no launch order
touches it: measured, a reader launched concurrently with a sibling opened at
13,613 read / 21,080 written, one launched twelve seconds later at 13,706 /
21,326. Within 1%.

Take the page ref out of turn 1 and the whole preamble is identical, so the
divergence moves to turn 3 where it is free. **Measured on `moll-038` /
`moll-039`: the first reader wrote 35,798 and the second read 35,798 and wrote
nothing** — where the same two pages under per-page prompts would each have
written ~21.3k of skill. Reader 1 answered `ready` in three chatty sentences and
reader 2 in the two lines asked for, and it cost nothing: both read the full
35,798 on their next request, because that variation sits *behind* the prefix.
Variation at the tail is free; variation at the head costs the whole block.

**Neither message contains any prose at all, and that is deliberate.** Phase 1 is
the single word `standby`; everything it used to say is standing and lives in
the agent definition, which is in the system prompt and which nobody
transcribes. **Phase 2 is the bare ref** — `moll-040`, eight characters. The
reader runs `assign moll-040` on itself and the tool that measures the page also
states the job. So the coordinator hands over one identifier per page and
nothing else, and that identifier is the one thing that fails loudly when wrong.

Phase 2 was a 622-character block until this was measured: the deliverable
sentence, the STOP, the report instruction and three paths, of which only the
ref was information — and the ref appeared in it **five times**, five chances to
write one page's number in another page's message, buried in 600 characters that
are identical across the batch and so read less carefully on the third
repetition. All of it is derivable from the ref, so it is derived.

It carried a rendered fourteen-line context block until this was noticed, and a
coordinator retyping one is precisely the failure this project is organised
against: the folio, the entry count and the wrap list reproduced by an LLM, with
no downstream check able to see a mistyped digit. A reader given a count one too
high finds a discrepancy, writes `disagrees:`, and is *credited* for catching
something the coordinator invented. The witness pass cannot reach it — tesseract
has no opinion about how many entries a page has. Having the reader run the
measurement itself also ends a staleness bug nobody had hit yet: a pasted block
is a snapshot, and a page re-measured after dispatch would be read against
numbers that no longer described it.

Two things this does not excuse. **The standby prompt must go out byte-identical
— editing one copy per reader reintroduces exactly the fault it removes**, which
is why `dispatch` prints it once and says so; at one word that is now hard to
get wrong rather than merely forbidden. And the phases must stay inside
the **five-minute subagent cache TTL**, which is not a documentation figure:
`usage.cache_creation` records the tier each write bought, and `harness agents
usage` reads it back.

**Check it rather than assume it.** `harness agents usage` groups the batch into
cohorts by opening size and prints one row per preamble turn with how many
distinct variants of it the readers had. Six readers should be one cohort of six
with `shared: yes` on every turn. Six singleton cohorts means a byte varied
ahead of the block, and the `preamble` table names which turn.

**Stagger the first launch only.** The first reader has to write the prefix
before anyone can read it; the rest go together once it has.

One thing that moves the number and is nobody's fault: readers write to
`.claude/agent-memory/moll-reader/`, and the memory index is in their system
prompt. When it changes the prefix changes and everything after it is re-cached,
so a batch following one where a reader recorded something pays a full write.
That is the cost of the memory channel, not a defect in it — and it is now a
cost against 35.8k rather than 13.7k, which is the price of having moved the
skill into the shared block.

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
page — the preloaded pass doc, the standby handshake, the loop, the Bash
surface, the hard rules, the report shape. **The rendered prompt carries one
ref and nothing else.** Two things follow: a clause edited in the agent file
reaches the next reader with no rendering step, and there is no page-specific
prose for anything to drift in.

**The templates are not in the Python.** Both sit below, delimited by the
`standby` and `page` marker pairs, and `entry_bounds.py` only
substitutes and refuses. A template copied into code is a second normative text
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
Nothing inside a task can see its own `subagent_type`, so the reader has to be
asked, and the **handshake is where it is asked**: phase 1 ends `pass doc: <held
| missing>` and a `missing` means no page is sent. The check costs a turn that
the two-phase dispatch was spending anyway, and it is mechanical — a coordinator
can test the reply without reading English, which is why the form is two fixed
lines rather than a paragraph.

That check has already earned itself once. A reader started with `claude --agent`
rather than by dispatch reported the pass doc absent and stopped: the `skills:`
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

`reconcile` first, and it is the only witness over phase 2. `dispatch` refuses a
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

<!-- standby:begin -->

    standby

<!-- standby:end -->

<!-- page:begin -->

    Your page is **{ref}**. Do not touch any other page.

        Read   scratch/chukchi/moll-scans/marked/{ref}.png
        Write  scratch/chukchi/moll-scans/entries/{ref}.md

    Deliverable: `scratch/chukchi/moll-scans/entries/{ref}.md`, one row per
    entry in the numbered reading order. STOP THERE — you do not check your own
    work, and the witness pass over the batch is not yours.

    Report back in the four parts your standing instructions specify: the page,
    the doubts you could not close, the zooms, and what the pass made harder
    than it needed to be.

<!-- page:end -->
