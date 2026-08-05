---
name: marked-page-warnings
description: The context block's flush-wrap warning is geometric, fires false often, and settles at 2x on one question; the `c`/`c←` continuation markers can span both columns
metadata:
  type: project
---

## flush-wrap / flush-runover is a cheap check, not a prediction

The skill doc frames these warnings as "the one place you should expect to write
`disagrees:` and be right," which can read as though the warning usually fires
true. It does not. **The warning is purely geometric** — two lines near full
measure at the same y-coordinate — and it can name entries that share nothing
but height.

Both cases met so far were false alarms, and both settled at plain 2× on a
single question: **does the left line's last character look like `-`, or like
ordinary end-of-clause punctuation?**

- moll-037: the left line ends `...в ра́зум,` on a comma, and the right opens
  `гэвэн'этгыргын (2) жизнь в`, a distinct flush-left bold headword. No join.
- moll-049: the two lines named were not even adjacent in reading order — left
  was entry 1 wrapping internally (`йъэнкыгин' (мн. йъэнкыги-` completing as
  `н'ыт)` two lines later, well inside entry 1), right was entry 25, unrelated.
- moll-061: left ended `2) застру́г;` on a semicolon, right opened
  `кэлинлелын почтальо́н`.

**How to apply:** zoom the two named lines at 2×, read the left line's final
character, and check whether the right line opens a new bold headword. If it
ends in punctuation other than a hyphen and the right line is a fresh flush-left
headword, they are two entries printed to look adjacent by coincidence of column
width. Note it in `note:` and do **not** force a `disagrees:`.

## An opening continuation can occupy the top of both columns

On moll-038 the page-opening continuation — no headword, carried over from the
previous page — filled the whole top of the left column *and* ran into the top
of the right, where it was marked `c←`. The marked page reuses `←` for "second
half of a split block drawn under one label" whether the block is a numbered
entry or the unnumbered opening continuation, so `c` and `c←` together can be
mistaken for a continuation plus a separate wrapped entry.

**How to apply:** if the top-right carries a marked `c←` band, read it with the
top-left `c` band as one continued block, give it no row, and quote both halves
in the `continues:` comment if useful. Do not start numbering from the right
column — entry 1 begins wherever the marked page's `1` label sits, which may be
well down the right column.

Note that the `←` band has a fault of its own: it can extend past the tail it
was drawn for and swallow the headword below it. See [[bracket-faults]].
