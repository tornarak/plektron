# Dispatching a batch of zone reviewers

`harness zones queue` prints **the prompt** and `harness zones claim` prints **the
page block**. Both are rendered from the marker pairs below and never assembled by
hand. The prompt names no page: identity of the first turn is what caches, so each
reviewer takes its own refs with `zones claim`.

<!-- claim:begin -->

    Claim a page with `uv run harness zones claim --root jesup/bogoras-materials`.
    If you have no zones-reviewer contract, stop and say so.

<!-- claim:end -->

### The page block `claim` prints

Everything true of one page in particular, and nothing else. The standing rules
live in the agent body.

<!-- prompt:begin -->

    Your page is **{ref}**. The rule's file holds {bands} bands; {unbanded} lines
    are in no band. Its flags: {flags}.{note}

    Run `uv run harness zones bands {ref} --root jesup/bogoras-materials` now.

<!-- prompt:end -->
