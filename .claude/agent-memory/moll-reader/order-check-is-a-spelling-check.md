---
name: order-check-is-a-spelling-check
description: A collation warning is usually the book's own misfiling, but before ruling it so, test whether one dropped letter would put the pair back in order — that is the only check in this pass that catches a well-formed misreading
metadata:
  type: project
---

`check_entries.py` reports a pair as out of collation order. Most of the time
that is the printed book's own doing, and the ruling goes in
`_order_exempt.md`. But **a dropped letter moves a headword past its
neighbour**, and when it does, this warning is the only signal anywhere in the
pass. The headword is still well-formed Chukchi, the gloss still makes sense,
and no reader feels any doubt — so nothing else fires.

**The test is mechanical and takes one line of thought: would adding or
changing a single letter put the pair back in order?** If yes, go to the raster
before writing an exemption. In one batch of 26 folios this test caught four:

| keyed | printed | how the order gave it away |
|---|---|---|
| `ыягты` | `ыяагты` | neighbours are `ыяа`, `ыяайпы`, `ыяакэн` — the whole run is `ыяа-`, and only this one broke it |
| `энаймэлгын` | `энаймэёлгын` | `ё` precedes `й`, so the real form sorts before `энаймэйвык` and the file's did not. `-ёлгын` is a productive instrument suffix; a missing one is easy to not see |
| `э'к'эльтык` | `э'к'эльэтык` | `э` follows `ы`, so the printed form sorts after `э'к'эльын` and the file's before it |
| `элгэел` | `элгээл` | did **not** fix the order — the pair inverts either way — but the raster check the warning provoked found the error anyway |

That last row is the useful one. The warning does not have to be *explained* by
the misreading for it to be worth the crop: it only has to send you back to the
page. Three of the four were also flagged by the OCR witness, so the two checks
overlap — but the witness reports ~100 uncorroborated headwords a batch and
most are tesseract's own `г`/`т` and `й`/`и` confusions, while an order warning
is rare and always means something. **Read the order warnings first.**

The converse discipline matters as much: of 26 warnings in that batch, 22 were
genuinely the book's, and each was ruled only after cropping both entries and
confirming both readings. See [[what-settles-a-letterform]] for what settles a
letterform once you are looking at it. An exemption written without the crop
would have buried all four of these.
