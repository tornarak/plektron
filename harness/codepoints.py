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
