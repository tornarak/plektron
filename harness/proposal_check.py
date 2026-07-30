"""Self-consistency gate for a reading proposal, not a firewall tool.

`review/PP-NNN/proposal.json` asks the author to spell out codepoints in
`resolved` for any line carrying notation (rebuild-groundtruth SKILL.md,
"The proposal file") precisely because a combining mark that fails to render
looks identical to its absence, and because hand-typing a combining sequence
is easy to fumble into a different mark that looks the same at a glance —
ring below for dot below, diaeresis for caron. The skill already says the
`resolved` field "catches your own typing, since the field and the character
can disagree"; this is that check promoted from something a human re-reads
into something a script runs, same rationale as `normalize.py` promoting the
NFD one-liner.

This is **not** `detectors.MARK_LICENSE` and must not grow into it. That table
is closed by editor attestation and answers "is this glyph possible" — the
question this module answers is narrower and unambiguous: "does the text the
author wrote match the codepoints the same author just said they meant."
Nothing here rules on what the *page* prints; `--fix` only ever moves a line
toward what its own `resolved` field already claims, and only when that claim
is unambiguous. A resolved field the tool cannot reconcile is left alone and
reported, never guessed at.
"""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path

from .detectors import INVENTORY_CHARS

HEX_RE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")
# The trigger set is `detectors.INVENTORY_CHARS` itself, not a re-derived Unicode
# category — the small caps ᴀᴇɪ and ᵋ are ordinary letter categories (Ll/Lm) and a
# category-based heuristic would miss them entirely, silently exempting exactly
# the glyphs most worth cross-checking. Dotless ı is inventory-adjacent (§2.6's
# ĭ = dotless-i + breve) but absent from INVENTORY_CHARS, so it is added here.
DOTLESS_I = "ı"
NOTATION_CHARS = INVENTORY_CHARS | {DOTLESS_I}


def _notation_codepoints(text: str) -> list[int]:
    """Codepoints a `resolved` field is expected to name.

    Any combining mark at all (Unicode category Mn), not only the ones
    `INVENTORY_CHARS` already knows about — a mark entirely foreign to the
    inventory (ring below, say, where dot below was meant) is exactly the
    error this module exists to catch, and restricting to known-good marks
    would make it invisible for having the wrong identity instead of a
    licensing problem.
    """
    nfd = unicodedata.normalize("NFD", text)
    return [ord(ch) for ch in nfd
            if ch in NOTATION_CHARS or unicodedata.category(ch) == "Mn"]


def _stated_codepoints(resolved: str) -> set[int]:
    return {int(h, 16) for h in HEX_RE.findall(resolved)}


def check(path: Path) -> list[dict]:
    """Per-line mismatches between what `text` contains and what `resolved` claims.

    Three shapes, in order of how actionable they are: `text` carries notation
    with no `resolved` field at all (nothing to check against — the skill's
    contract was skipped); `resolved` names a codepoint absent from `text`
    (the field describes a reading the characters do not contain, so either
    was mistyped); `text` carries a codepoint `resolved` never mentions (the
    field is incomplete, or the character is the wrong one).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for idx, rec in sorted(data.get("lines", {}).items(), key=lambda kv: int(kv[0])):
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        present = set(_notation_codepoints(text))
        if not present:
            continue
        stated = _stated_codepoints(resolved)
        if not stated and not resolved:
            out.append({"line": idx, "issue": "notation with no resolved field",
                        "in_text": sorted(f"U+{c:04X}" for c in present)})
            continue
        extra_in_text = present - stated
        extra_in_resolved = stated - present
        if extra_in_text or extra_in_resolved:
            out.append({
                "line": idx, "issue": "resolved/text mismatch",
                "in_text_not_resolved": sorted(f"U+{c:04X}" for c in extra_in_text),
                "in_resolved_not_text": sorted(f"U+{c:04X}" for c in extra_in_resolved),
            })
    return out


def fix(path: Path) -> dict:
    """Apply the one unambiguous class of correction: a single wrong mark.

    Only touches a line where exactly one notation codepoint in `text` has no
    match in `resolved` **and** exactly one codepoint named in `resolved` has
    no match in `text` — a 1-for-1 swap with nothing else to decide between.
    Composes the replacement back to NFC-free NFD (the corpus form) rather than
    guessing a precomposed glyph. Anything less clean (zero or more than one
    of either side) is left alone and still reported, since a guess here is
    exactly what the firewall's reasoning forbids elsewhere.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = []
    for idx, rec in data.get("lines", {}).items():
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        if not resolved:
            continue
        present = set(_notation_codepoints(text))
        stated = _stated_codepoints(resolved)
        extra_in_text = present - stated
        extra_in_resolved = stated - present
        if len(extra_in_text) != 1 or len(extra_in_resolved) != 1:
            continue
        wrong = chr(next(iter(extra_in_text)))
        right = chr(next(iter(extra_in_resolved)))
        nfd = unicodedata.normalize("NFD", text)
        if nfd.count(wrong) != 1:
            continue  # ambiguous position; do not guess which one
        new_text = nfd.replace(wrong, right)
        rec["text"] = new_text
        changed.append({"line": idx,
                        "replaced": f"U+{ord(wrong):04X}", "with": f"U+{ord(right):04X}"})
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return {"path": str(path), "changed": changed}
