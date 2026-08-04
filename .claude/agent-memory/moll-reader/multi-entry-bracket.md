---
name: multi-entry-bracket
description: A single numbered bracket can group far more than two complete entries — check every flush-left bold headword inside a bracket, not just whether it's exactly two
metadata:
  type: project
---

On moll-035 (folio 34), the marked page's bracket "23" spanned a huge block
(a `zoom moll-035:23` crop came back 1170px tall against a normal ~130-320px
single-entry crop) covering: the hyphen-wrap continuation of entry 22's gloss,
then five further complete, distinct, flush-left bold headwords (гыркик I,
гыркик II, гыркимъетык, гыркимъетылын, гыркычевык), each with its own gloss.
None of the five got its own number on the marked image — the tool's next
label after 23 was 24, on the entry after all five.

**Why:** the skill's "when a bracket is not an entry" section frames the
multi-headword fault as "one bracket held two complete entries." This case
was six items (one wrap + five entries) under one label. The unusual crop
height from `zoom` was the tell before I even read the content closely — a
crop several times taller than its neighbors is worth treating as a signal
on its own, not just a byproduct of reading.

**How to apply:** if a `zoom STEM:N` crop comes back much taller than the
entries around it, expect more than one (or more than two) headwords inside.
Read the whole crop and give each flush-left bold headword its own row,
regardless of how many that turns out to be. Write `disagrees:` explaining
the split; the row count will differ from the predicted total by more than
one, and that is expected and correct, not evidence you've made an error.
