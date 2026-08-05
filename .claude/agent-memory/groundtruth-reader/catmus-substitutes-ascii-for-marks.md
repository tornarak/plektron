---
name: catmus-substitutes-ascii-for-marks
description: the recognizer replaces a mark it cannot read with whatever ASCII glyph is near its shape, and the substitute is not predictable — the register of observed cases
metadata:
  type: feedback
---

One failure class, many disguises: where the print carries a mark CATMuS has no
sort for, `mz/ocr/` shows some ASCII character of roughly that silhouette. The
substitute is **not stable**, so no lookup table retires the raster.

Observed, page by page:

| printed | came through as | where |
|---|---|---|
| raised stress U+02CA | `’` , `'` , `/` | `1-036` (`Ca/wan` for `Čaˊwan`) |
| superscript footnote digit | `!` , `?` | `1-037` L4, `1-044` L29/L30 |
| small-cap ɪ U+026A | `i` , `I` , `r` | throughout — the leading residual class, §5.2 |
| ɵ U+0275 | `e` , twice in one word | `1-042` (`Ne'ekan` for `Nɵˊɵkan`) |

**Why:** the recognizer is not choosing between *marks*, it is choosing among the
sorts it has, so the error is shaped by the glyph's outline rather than by
phonology. That is also why a substitution can look like ordinary punctuation and
survive a read-through: `Wrangell.!` parses as a typo, not as a lost superscript.

**How to apply:** a stray `!`, `?`, `/` or quote sitting where no punctuation
belongs — after a period, mid-word, at a line end — is a mark until the raster says
otherwise. Same for a plain vowel inside an otherwise-marked Tier-1 word. Neither
is a licence to key from expectation: the raster decides, and §2.10's rule already
settles the footnote case in advance (superscript at reference and opener alike,
whatever the machine shows).

Openers seem to survive more often than in-body references — an observed pattern
across four pages, not a rule, and not a reason to skip one.
