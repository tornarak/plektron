---
name: review-zones
description: Dispatch a batch of zones-reviewer agents over the rule's zones for Bogoras's 1900 «Матеріалы» (jesup/bogoras-materials), each writing review/PP-NNN/zones.json, edits against mz/zones/; then gate the verdicts and hand the pages to the editor. Use for the zone review pass, or on /review-zones. The review contract lives in the zones-reviewer agent, not here. Not the zone keying itself — a human does that in zones edit.
---

# Run a batch of zone reviewers

**This is the coordinator's document. The review contract is not in it**:
`.claude/agents/zones-reviewer.md` carries it whole, with the editor's rulings
(`rulings.md`, beside this file) transcluded. Do not restate either here.

The pass sits between the rule and the editor. `zones propose` writes `mz/zones/`
(`#mz`); a reviewer writes `review/PP-NNN/zones.json` (`#llm`), edits against it;
the editor opens the page in `zones edit`, where the `llm` view shows the edits
applied with their reasons, and a save writes `gt/zones/`. The design is
`docs/multitext.md`, "The review pass".

## The loop

`dispatch.md`, beside this file, holds the two templates `queue` and `claim`
render. In short, with `--root jesup/bogoras-materials` on each:

    uv run harness zones propose --all --commit --force   only if the rule changed:
                                                          it stales every verdict
    uv run harness zones queue --all                      every unkeyed page; validates,
                                                          writes the queue, prints
                                                          THE prompt
    …spawn ceil(n/8) zones-reviewer agents with that prompt, unedited and
      identical, staggering the first launch about ten seconds…
    uv run harness zones reconcile PP-NNN ...             what came back
    uv run harness zones verdict --all                    the gate, every verdict
    uv run harness zones edit PP-NNN ...                  the editor's, not yours

`queue` refuses a ruled leaf, a page keyed in `gt/zones/`, a page whose rule file is
missing or predates the flags, and a page already holding a fresh verdict. Under
`--all` a refused page is left out and listed; a named page refuses the batch.

**Every page is reviewed** (the editor, 2026-11-15): 4 of 20 unflagged pages
needed edits in the first batch, so a flag is a hint, not a selection. **Do not
extend the rule to catch what reviewers correct**: it measures and reads no words,
and a rule fitted to their edits makes its agreement with them one witness. A
fault is the rule's only where it breaks its own measurement (`docs/multitext.md`).

## After the batch

1. **`zones reconcile`** on the queued refs: `reviewed`, `CLAIMED, no verdict` (an
   agent took the page and did not come back), or `unclaimed`.
2. **`zones verdict --all`** must exit 0. A failing verdict is the agent's to fix
   only while it is running; afterwards, delete the file and re-queue the page.
3. **Read a few verdicts against the scan yourself**, the sampled pages first. An
   edit whose `why` names no ruling or description is the contract failing, not
   the page.
4. **Hand the editor `zones edit` over the reviewed pages**, opening in the `llm`
   view, and wait for them to say they have saved. Never poll the server.

A verdict goes stale when the rule rewrites the file, and the editor shows it as
stale without applying it. Re-run the pass on those pages rather than editing a
stale verdict's digest by hand: the digest is the witness that the bands it numbers
are the bands it read.
