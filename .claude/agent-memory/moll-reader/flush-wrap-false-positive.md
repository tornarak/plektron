---
name: flush-wrap-false-positive
description: A flush-wrap warning is often a false alarm, resolved instantly by whether the left line ends in a hyphen or ordinary punctuation
metadata:
  type: project
---

On moll-037 (folio 36), the context block warned `flush-wrap` at y=197: L
column line ends at full measure and R column opens flush at the same height.
Zoomed at default 2x, the left line reads "...в ра́зум," — ends on a comma, not
a hyphen — and the right line opens "гэвэн'этгыргын (2) жизнь в", a plainly
distinct flush-left bold headword with its own apostrophe. No join; the
existing numbering (entry 1, entry 24) was correct as printed.

**Why:** the skill doc frames both flush-wrap and flush-runover warnings as
"the one place you should expect to write disagrees: and be right," which
could read as an expectation that the warning usually fires true. On this page
it did not — the false-alarm case resolved just as fast, at plain 2x, by
checking one thing only: does the left line's last character look like `-` or
does it look like ordinary end-of-clause punctuation (comma, semicolon)?

**How to apply:** treat a flush-wrap/flush-runover warning as a cheap, fast
check, not a predictor of an actual fault. Zoom the two lines named in the
warning at 2x, read the left line's final character, and read whether the
right line opens with a new bold headword. If the left line ends in
punctuation other than a hyphen and the right line's first word is bold and
flush, it is very likely two separate entries printed to look adjacent by
coincidence of column width — note it in `note:`, do not force a
`disagrees:`.
