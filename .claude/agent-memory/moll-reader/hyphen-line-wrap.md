---
name: hyphen-line-wrap
description: Watch for line-end hyphens splitting Russian gloss words across the indented continuation lines, especially "обере-/гать" (оберегать) forms
metadata:
  type: project
---

On moll-034, three entries (гынритык, гынритыткульын, гынрырэтык) split the
gloss verb оберега́ть/оберега́ющий/оберега́ться across a line break: the first
line ends "обе-" or "обере-" and the next line opens "рега́ть" / "га́ющий" /
"га́ться". This is an ordinary typographic line-end hyphen (per the skill's
own hyphen rule) and must be joined into one word with no hyphen —
"оберега́ть", not "обере-га́ть". On a first pass I kept the hyphen because
the fragments individually look plausible as data-hyphens; only re-zooming
and reading the two line-halves together made clear they're one word broken
by the margin.

**Why:** the skill's hyphen rule already says line-end hyphens join, but it's
easy to key each column line in isolation and miss that a common verb has
been fractured across a wrap — especially when both fragments are individually
well-formed-looking chunks.

**How to apply:** when a gloss line ends in a hyphen, always check the next
line's opening syllable before finalizing the cell; join without the hyphen.
