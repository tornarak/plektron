# Dispatching the *Materials* reading to subagents

The text's manifest names its reader (`project.json` `"reader":
"materials-reader"`), so `ocr queue`, `ocr claim` and `ocr reconcile` run this
track, not *The Chukchee*'s. The queue, the claims and the shared prompt are the
same machinery (`rebuild-groundtruth/dispatch.md` says why the prompt names no
page). What differs is the contract, `.claude/agents/materials-reader.md`, and
the page block below.

From `jesup/bogoras-materials/`:

1. `uv run harness ocr queue 1-026 1-027 …` validates the batch and prints the
   one prompt.
2. Spawn one `materials-reader` per page with that prompt, unedited and
   identical; stagger the first by about ten seconds so it writes the cache the
   rest read.
3. `uv run harness ocr reconcile 1-026 …` says which came back.
4. Check what came back, before the editor sees it (SKILL.md, "Checking a
   batch").
5. `uv run harness ocr review 1-026 …`, one server for the batch, then
   `ocr restore … --commit`. **Restore a batch before dispatching the next**:
   a restored page's forms are what the next batch's lookup sees.

The claim prompt, sent to every reader:

<!-- claim:begin -->

    Claim a page. If you have no materials-reader contract, stop and say so.

<!-- claim:end -->

The page block, which `ocr claim` renders for the page it hands out:

<!-- prompt:begin -->

    Your page ref is **{ref}**. Do not touch any other page, and do not claim a
    second: one reader, one page.

    What the survey found:
      - `mz/ocr/{stem}.xml`, copy A's text layer, holds {lines} lines.
      - `gt/ocr/{stem}.xml` does not exist, so this is a restoration.{note}

    What a crop of THIS page will show you, measured off its own lines:
    {zoom}

    Native forms keyed on the pages just before this one, most-keyed first —
    reference, not a prediction about your page; the lookup is still the one call
    that settles a key:
    {nearby}

<!-- prompt:end -->
