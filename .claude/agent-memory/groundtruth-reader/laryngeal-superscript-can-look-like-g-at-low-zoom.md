---
name: laryngeal-superscript-can-look-like-g-at-low-zoom
description: the licensed ᵋ (U+1D4B, laryngeal/glottalization superscript) can read as a superscript "g" loop at 3x zoom; only a closer zoom resolves it as the catalogued epsilon shape, not an uncatalogued mark
metadata:
  type: feedback
---

On `1-038` line 37, `Mêˊlhɪ-t-taˊn˙ñɪtan` prints with a small raised mark between `ɪ`
and the following hyphen. At 3x zoom (`--only 37`, whole-line strips) the mark reads
as a tiny loop with a descender — indistinguishable at that scale from a superscript
"g" (ᵍ), which is not in the inventory anywhere (keying_spec.md has no superscript-g
sort). Re-zoomed to 6x on a narrow span (`37@18-38`) it resolves cleanly as the small
open-e/epsilon outline of ᵋ (U+1D4B), the catalogued laryngeal/glottalization
superscript from §2.1 — a completely different, licensed sort.

**Why:** ᵋ's glyph (a stacked open-e/figure-8-like shape) and a hypothetical
superscript g share enough of a rounded-loop silhouette at low zoom that the wrong
one is easy to default to, especially since "superscript g" sounds phonetically
plausible next to a velar-adjacent form. But keying_spec.md §5.9 is explicit: an
uncatalogued codepoint is far more likely a misreading than the inventory being
incomplete, and ᵋ is already licensed for exactly this environment (glottalization
of the stressed vowel, i.e. immediately after a marked vowel/consonant cluster).

**How to apply:** any small superscript loop/hook mark that isn't obviously the
familiar stress tick (ˊ) or palatalization dot (˙) needs a close (5-6x), narrow-span
zoom before deciding what it is — don't key or describe it off a whole-line 3x
strip. Check it against §2.1's ᵋ/ᵉ shapes first; both are licensed and mutually
confusable per the spec, but neither is a "g" of any kind. The same page's line 35
has the identical root (`Mêˊlhɪ-taˊn˙ñɪtan`) *without* this mark at all — a same-root
contrast on the same page confirms the mark is meaningful (present on one spelling
variant, absent on the other, matching the text's own parenthetical gloss
distinguishing the two forms) rather than print noise.
