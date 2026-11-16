"""Name every non-ASCII character in a string.

Written after the third time a session hand-rolled `python3 -c "...ord(ch)>127..."`
mid-pass to check whether a typed mark was the intended codepoint or a lookalike
(U+0131 dotless ı for U+026A small-cap ɪ, U+0027 apostrophe for U+02CA stress,
combining ring for combining dot-below). Recurring op, so it belongs here rather
than in another one-off snippet next session. Exposed as `proposal-check
--codepoints LINE`, not a standalone verb — it answers the same question
`proposal-check` already asks ("does this line's text hold the codepoints I
think it does"), just with names instead of a resolved-field cross-check.
"""
from __future__ import annotations

import re
import unicodedata


def non_ascii(s: str) -> list[dict]:
    """One record per non-ASCII character: the glyph, its codepoint, its name.

    Plain ASCII (ord <= 127) is dropped — that was the actual filter every
    hand-rolled version of this used, because the letters, digits and space
    that make up the bulk of a line are never the thing in doubt.
    """
    return [
        {"char": ch, "codepoint": f"U+{ord(ch):04X}",
         "name": unicodedata.name(ch, "<unnamed>")}
        for ch in s if ord(ch) > 127
    ]


def _foreign_letter(ch: str) -> bool:
    """A letter of a script other than Latin (Cyrillic, Greek …). Not a modifier
    letter: The Chukchee's stress `ˊ` (U+02CA) and `ᵋ` are letters to Unicode,
    named outside LATIN, and are marks in the notation."""
    return (ch.isalpha() and unicodedata.category(ch) != "Lm"
            and not unicodedata.name(ch, "").startswith("LATIN"))


def spot_check(s: str) -> list[dict]:
    """`non_ascii`, plus each ASCII letter inside a word that holds a letter of
    another script — the line as `proposal codepoints` spells it out.

    **An ASCII letter is the thing in doubt there.** The 1900 *Materials* key the
    tall l and w as Latin inside Cyrillic words (`пы́ӈыlте`), and a Latin lookalike
    slipped into a Russian word (`Tоже`) is the commonest typing slip; a listing
    that drops ASCII hides both, which two readers mistook for the letters having
    been lost. A word wholly in Latin script, *The Chukchee*'s notation included,
    is listed as `non_ascii` lists it, so that text's output does not change.
    """
    out = []
    for word in re.split(r"(\s+)", s):
        mixed = any(_foreign_letter(c) for c in word)
        for ch in word:
            if ord(ch) > 127 or (mixed and ch.isascii() and ch.isalpha()):
                out.append({"char": ch, "codepoint": f"U+{ord(ch):04X}",
                            "name": unicodedata.name(ch, "<unnamed>")})
    return out
