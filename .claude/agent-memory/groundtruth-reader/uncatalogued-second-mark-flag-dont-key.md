---
name: uncatalogued-second-mark-flag-dont-key
description: a raised mark whose shape doesn't match any catalogued sort, or that would create a second stress mark in one word, gets flagged in note and left unkeyed rather than forced into the nearest catalogued codepoint
metadata:
  type: feedback
---

On `1-048` (gazetteer of Chukchee village names), two cases came up where a
visible raised mark didn't cleanly fit the inventory:

1. Line 18/20, `Veᵋñ`: the mark over `n` reads more angular/pointed at 4x than
   the flatter tilde on `Uñiˊsak` elsewhere on the same page. No caron-`n` is
   catalogued (keying_spec.md §2.2 licenses only `ñ`, n+U+0303). Keyed as `ñ`
   anyway (closest catalogued sort) and flagged the shape discrepancy in `note`,
   per §5.9's rule that an uncatalogued codepoint is far more likely a
   misreading than the inventory being incomplete.

2. Line 47, `Kihiˊni Island` (first mention only): a second, crisp raised mark
   sits after the word, distinct in shape from the stress mark earlier in the
   same word. Keying it as a second U+02CA would violate the culminative-stress
   rule (§2.1/§5.5, ≤1 per word — the word already has one). It doesn't sit in
   a licensed V_V or post-consonant environment for the pause/spirant U+0027
   either. Here the resolution was different from case 1: rather than force it
   into any catalogued mark, it was **left unkeyed entirely** (text matches the
   second, unambiguous occurrence of the same word later in the line), with the
   observation described in `note` for adjudication.

**Why two different resolutions:** case 1 has an available catalogued sort that
plausibly *is* what was meant (ñ is licensed, common, and the word needs some
nasal); case 2 has no catalogued sort that fits the position without breaking a
validated rule (culminative stress), so keying anything there would either fail
`proposal check` or silently assert something false. When a catalogued fallback
exists and is phonologically sensible, use it and flag the shape doubt. When no
catalogued option can be made to fit without violating a validated rule, don't
force one in — describe what you saw in `note` and move on; `proposal check`
stays clean either way if you get this right (it did, on both counts, at first
pass on case 1 and case 2 immediately).

**How to apply:** before keying an ambiguous raised mark, ask (a) does a
catalogued sort fit here phonologically/positionally, and (b) would keying it
violate a validated rule (culminative stress, mark-licensing table §2.6)? If
(a) yes and (b) no: key the catalogued sort, flag the doubt. If (a) no or (b)
yes: don't key it, describe it in `note`, let the human resolve it in
`harness ocr edit`.
