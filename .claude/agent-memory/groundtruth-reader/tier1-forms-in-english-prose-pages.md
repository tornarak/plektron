---
name: tier1-forms-in-english-prose-pages
description: A page that reads as ordinary English narrative can still carry Tier-1-notation ethnonyms/toponyms mid-sentence — check every proper noun, not just pages that "look" like gazetteer/vocabulary lists
metadata:
  type: feedback
---

`1-036` is a page of continuous English narrative (tribal history, no vocabulary
list, no obvious phonetic transcription) that nonetheless embeds a Chukchee
ethnonym repeatedly: `Čaˊačên`/`Čaˊačêt` (×5) and river names `Čaˊan`/`Čaˊwan`,
each carrying a caron (č, settled §2.2), a circumflex (ê, settled §2.2), and a
raised mark between two vowels that the CATMuS machine text rendered
inconsistently as `’`, and once as a bare `/` (`Ca/wan` for `Čaˊwan`) — evidence
that even a common ASCII-substitution failure mode isn't limited to Tier-1
`ɪ`→`r`; a stress mark can come out as a slash too.

**Why this matters:** nothing about the page's genre (a "Neighboring Tribes"
historical section, not a lexicon) predicted this. The standing rule ("a page
believed to be all English is a prior, not a licence") is not hypothetical —
apply the same full Tier-1 checklist (§4/§5.8 raised-mark-defaults-to-stress,
one-stress-per-multisyllabic-word) to any name that looks like it could be a
transliterated native form, wherever it turns up in otherwise plain narrative.

**How to apply:** when contact-sheet-reading an "ordinary" page, watch for any
capitalized word carrying a caron/circumflex/breve/raised mark even mid-sentence
in English prose — that word gets the full raster treatment (zoom, resolved
field, stress-vs-apostrophe default) exactly like a gazetteer entry would.

Related: the same page's footnote-2 *opener* printed as a full-height digit
(not visibly raised, unlike the footnote-1 opener and both body references) —
still keyed as superscript per keying_spec.md §2.10's settled rule ("there is
no plain-digit convention... at the reference and at the opener alike"). Worth
knowing that §2.10's settled rule overrides a raster impression: don't let a
opener that "looks like a plain digit" talk you out of the superscript keying.
