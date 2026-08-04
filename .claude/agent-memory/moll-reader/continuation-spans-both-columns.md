---
name: continuation-spans-both-columns
description: An opening continuation (marked c) can occupy the top of BOTH columns, not just the left — watch for a matching c← at the top of the right column
metadata:
  type: project
---

On moll-038 the page-opening continuation (no headword, carried over from the
previous page) was long enough to fill the entire top of the left column *and*
run on into the top of the right column, where it was marked `c←` (the same
marker normally used for the second half of a wrapped definition). This is
distinct from the ordinary case where `c` sits alone at the top-left and entry
1 starts the right column at its own top.

**Why:** the marked-page convention reuses `←` for "second half of a split
block, drawn under one label" whether that block is a numbered entry or the
unnumbered opening continuation. Seeing `c` and `c←` together could be
mistaken for two different things (a continuation and a separate wrapped
entry) if you don't read both crops before deciding.

**How to apply:** if the top-right of the page carries a pink/marked `c←`
band, read it together with the top-left `c` band as one continued block, give
it no row, and quote both halves in the `continues:` comment if useful. Don't
start entry numbering from the right column in this case — the real entry 1
begins wherever the marked page's `1` label sits, which may be lower down the
right column.
