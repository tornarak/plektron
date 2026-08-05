---
name: folio-can-sit-on-own-thin-alto-line
description: a running-head folio can land on its own separate (near-empty, very narrow) ALTO line rather than sharing the title line's box — check --margins on that line, not just the title line
metadata:
  type: feedback
---

On `1-035`, the running title zone had two ALTO lines: index 0 held the title text
("BOGORAS, THE CHUKCHEE."), and index 1 was a ~19px-wide box with **empty** text —
just the printed vertical divider rule between title and folio. The folio ("115")
was invisible in both lines' plain crops and only appeared once `--margins` widened
line 1's crop to the full PrintSpace: it sat to the right of the divider, within the
same physical row as the title but wrapped into a later strip of the widened image.

**Why:** the skill's precedent (`1-073`/`1-074`) is about a folio/list-number sitting
outside *every* box on the page; this is the same class but the near-empty sliver line
is easy to dismiss as decorative (just the rule) rather than checked with `--margins`
for what else its widened row contains.

**The reading itself is disputed and unadjudicated.** This note's `115` sits in a run
whose neighbours read `[11] 12 13 14 15 16`, which makes the printed folio 15 and the
leading `1` most likely the divider rule this note describes — i.e. the very sliver
the widened crop was opened to inspect. Keep the mechanism, distrust the digits: a
folio recovered from a margin-widened crop of an empty box is exactly where a rule,
a speck or a bleed can be read as type. Nothing here infers a folio from a
neighbour; a human settles it at the raster.

**How to apply:** on a running-title zone, if there's a second, very narrow ALTO line
near the title with empty predicted text, don't assume it's just a rule/divider —
zoom it with `--margins` before deciding it carries nothing. If the sliver line is
the folio's own box, key the folio into **that** line's index (plain ASCII digits,
keying_spec.md §2.12) and note that its ink sits outside the box's plain crop.

**If it turns out there is no box for the folio at all, it is a dropped line and
you report it — see [[folio-with-no-line-is-a-dropped-line]].** An earlier version
of this note said to key it "into whichever line's widened crop actually shows it",
which is wrong and was followed on `1-037`: the folio went into the running title's
own `text`, so the proposal asserted that the title's box contains a number sitting
500 px to its right. Ground truth is a text-to-geometry correspondence, and that
one would have been false. Nothing you key may describe ink outside the line you
are keying.
