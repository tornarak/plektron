---
name: read-moll-page
description: Dispatch and check a batch of readers over Moll & Inenlikej 1957, «Чукотско-русский словарь». Use when reading pages of the Chukchi–Russian dictionary into scratch/chukchi/moll-md/entries/, or on /read-moll-page. The reading contract itself lives in the moll-reader agent, not here. Not a Bogoras corpus pass — nothing it produces may enter gt/ or tei/.
---

# Run a batch over the Moll dictionary

**This is the coordinator's document. The reading contract is not in it.**

Everything a reader needs — the page anatomy, what counts as an entry, the
character inventory, the zoom ladder, the output contract, the hard rules — is
the body of `.claude/agents/moll-reader.md`, and it sits there for a reason that
was measured rather than chosen:

> An agent's system prompt is the only part of its context ahead of every user
> turn, so it is the only part siblings can share. A skill preloaded by
> frontmatter arrives as a *message* instead, behind the turn that names the
> page — so every reader wrote it in full, and on resume it was injected a
> second time and written again. Moving it into the agent body cut the fixed
> overhead of a three-reader batch from ~118k tokens to ~50k.

One home for the contract, and it is the agent file: a clause edited there
reaches the next reader with no rendering step and no copy. **Do not restate any
of it here.** A rule in two places is the defect this repo is organised against,
and this one would be invisible, both files looking equally authoritative.

## What this document is for

`dispatch.md`, beside this file, is the whole of it: how to dispatch a batch,
what `dispatch` refuses and why, the prompt template, and what to run when the
batch comes back — `reconcile`, `witness`, `check_entries`, `normalize_entries`.

    uv run python scratch/chukchi/entry_bounds.py dispatch moll-043 moll-044 moll-045

Read `dispatch.md` before running one, and the register in `scratch/CATALOG.md`
before adjudicating what comes back. That register is the consolidated account
of what actually goes wrong on this book and what catches each class — including
the ones no per-headword comparison can reach.

## If you are reading a page yourself

You are not a `moll-reader`, so you do not have the contract. Read
`.claude/agents/moll-reader.md` and follow it as written; it stands alone.

One thing does not carry over: its hard rules assume the guard hook, which fires
only for the subagent. Working by hand, the blindness rule is yours to keep —
`scratch/chukchi/moll-md/ocr/` is the independent witness your page will be
diffed against, and opening it collapses two witnesses into one.
