---
name: accented-o-looks-like-b
description: an italic о with an acute accent can look like a second б at 4x; crop tighter before concluding a doubled consonant
metadata:
  type: feedback
---

On moll-044, entry 2's gloss "(пробо́ину)" wraps line-final as "(про-" / "ббину)".
At first read, and even at a plain 4x `zoom`, the wrapped "бо́ину" reads as
"ббину" — the acute accent sitting on top of the italic "о" fuses visually with
the letter's curve and reproduces a б's ascender loop, so two genuinely
different letters (б, then accented о) look like the same loop-topped shape
repeated.

**Why:** "проббину" is not a word; "пробо́ину" (accusative of пробо́ина, a
hole/leak) is exactly the kind of well-formed-looking wrong reading the
governing brief warns about — it would have passed every downstream check.

**How to apply:** when a run of what looks like a repeated bold/italic
consonant appears where an accented vowel would also fit grammatically, crop
tighter (a same-scale ImageMagick crop of the existing zoom output, not a
further upscale) rather than trusting the first impression at cap. Isolating
just the 3-4 characters at existing resolution resolved it cleanly here
without violating the no-additional-magnification rule.

See also [[non-entry-brackets]] and the standing instruction's zoom-ladder
section on "the letterform decides."
