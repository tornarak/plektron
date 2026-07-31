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

One exception to "unambiguous therefore fixable": a word-medial ASCII A/E/I/L
(`detectors.MEDIAL_CAPS`) counts toward the codepoint accounting so a line
with two independent errors is correctly seen as ambiguous rather than as a
false clean swap (see `_notation_codepoints`), but `fix()` never auto-replaces
one even when it is the lone dangling item — a mistyped combining mark (ring
below for dot below) is a shape slip with one obvious correction; a plain
capital letter sitting where a small-cap belongs is closer to a reading
judgement, so it stays a `check()` flag for a human to resolve.
"""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path

from .codepoints import non_ascii
from .detectors import (INVENTORY_CHARS, MEDIAL_CAPS, apostrophe_flags,
                        suffix_mark_flags)

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

    Also counts a word-medial ASCII A/E/I/L (`detectors.MEDIAL_CAPS`, the same
    check `harness context` already runs over OCR text) as a codepoint present.
    This is what `1-100` line 37 needed and did not have: a plain 'A' typed for
    small-cap ᴀ is invisible to every check above (ASCII, not a combining mark),
    so on a line that *also* had an unrelated ı-for-ɪ slip, `fix()`'s "exactly
    one dangling item on each side" test saw a false 1-for-1 and silently swapped
    the wrong pair. Folding the ASCII hit into `present` restores the true count
    — either it now matches `resolved` correctly, or `fix()` sees two dangling
    items and correctly refuses to guess instead of pairing them wrong.
    """
    nfd = unicodedata.normalize("NFD", text)
    codepoints = [ord(ch) for ch in nfd
                 if ch in NOTATION_CHARS or unicodedata.category(ch) == "Mn"]
    codepoints += [ord(m.group()) for m in MEDIAL_CAPS.finditer(nfd)]
    return codepoints


def _stated_codepoints(resolved: str) -> set[int]:
    return {int(h, 16) for h in HEX_RE.findall(resolved)}


def set_field(path: Path, line: str, field: str, value: str) -> dict:
    """Set one line's field, NFD-normalizing on write.

    Exists because hand-typing a replacement for `Edit` risks producing NFC
    where the file (already run through `normalize --convert`) holds NFD —
    `ñ` typed as one keystroke is U+00F1, the file's is `n`+U+0303, and the two
    are invisible to each other under exact string match. Writing through here
    instead of Edit sidesteps the mismatch by construction: whatever comes in,
    NFD goes out, same as `normalize.py`'s one conversion point.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = data.setdefault("lines", {}).setdefault(line, {})
    rec[field] = unicodedata.normalize("NFD", value)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return {"path": str(path), "line": line, "field": field}


def _parse_which(which: str, count: int) -> list[int]:
    """0-based occurrence indices `which` selects, out of `count` found.

    "all" (every occurrence), "first", "last", a bare 1-based index ("3"),
    or a 1-based inclusive range ("2:4"). Kept separate from the replace
    logic so a bad spec (out of range) is caught before anything is written.
    """
    if which == "all":
        return list(range(count))
    if which == "first":
        return [0] if count else []
    if which == "last":
        return [count - 1] if count else []
    if ":" in which:
        lo, hi = which.split(":", 1)
        return list(range(int(lo) - 1, int(hi)))
    return [int(which) - 1]


def replace_in_field(path: Path, line: str, field: str, old: str, new: str,
                     which: str = "all") -> dict:
    """Replace occurrence(s) of `old` with `new` in one line's field.

    The surgical alternative to `set_field`: fixing one mistyped character in
    an otherwise-correct 70-character line by retyping the whole field (the
    only option before this existed) risks introducing a *second*, unrelated
    slip while fixing the first — a hand-retyped line is exactly the kind of
    silent second error the firewall's provenance ranks exist to catch, not a
    tool anyone should have to lean on routinely. This only touches the
    occurrences named.

    `which` selects among matches of `old`, left to right, 1-based: "all"
    (default), "first", "last", "N" (the Nth occurrence), or "N:M" (the Nth
    through Mth inclusive). Matching and the write-back both happen in NFD,
    same reasoning as `set_field` — a precomposed `old`/`new` typed by hand
    and the file's own decomposed form are invisible to each other otherwise.
    Raises ValueError if `old` doesn't occur, or `which` names an occurrence
    that doesn't exist — never silently replaces fewer than asked.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = data.get("lines", {}).get(line)
    if rec is None:
        raise KeyError(f"no line {line!r} in {path}")
    text = unicodedata.normalize("NFD", rec.get(field, ""))
    old_n = unicodedata.normalize("NFD", old)
    new_n = unicodedata.normalize("NFD", new)
    if not old_n:
        raise ValueError("--old must not be empty")
    positions = []
    start = 0
    while True:
        i = text.find(old_n, start)
        if i == -1:
            break
        positions.append(i)
        start = i + len(old_n)
    if not positions:
        raise ValueError(f"{old!r} does not occur in line {line} field {field!r}")
    selected = _parse_which(which, len(positions))
    bad = [i for i in selected if i < 0 or i >= len(positions)]
    if bad:
        raise ValueError(f"{which!r} out of range: only {len(positions)} "
                         f"occurrence(s) of {old!r} found")
    new_text = text
    for idx in sorted(selected, reverse=True):
        p = positions[idx]
        new_text = new_text[:p] + new_n + new_text[p + len(old_n):]
    rec[field] = unicodedata.normalize("NFD", new_text)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return {"path": str(path), "line": line, "field": field, "old": old,
            "new": new, "which": which, "occurrences": len(positions),
            "replaced": len(selected)}


def line_codepoints(path: Path, line: str, field: str = "text") -> list[dict]:
    """Non-ASCII characters in one line's field, named — a typed-mark spot check.

    Not a substitute for `check()`/`resolved`: this names what is actually in
    the text (e.g. "U+0131 LATIN SMALL LETTER DOTLESS I" where U+026A ɪ was
    intended), it does not know what was *meant*. Use it to settle a doubt
    about one line while authoring, before `resolved` is even written.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = data.get("lines", {}).get(line)
    if rec is None:
        raise KeyError(f"no line {line!r} in {path}")
    return non_ascii(rec.get(field, ""))


def check(path: Path) -> list[dict]:
    """Per-line mismatches between what `text` contains and what `resolved` claims,
    plus apostrophe hits independent of `resolved` entirely.

    Five shapes, in order of how actionable they are: a straight apostrophe
    anywhere in `text` (`detectors.apostrophe_flags` — not gated on
    `resolved` at all, and not gated on the token looking Tier-1 either;
    every straight apostrophe in the corpus checked out either an English
    possessive that should be curly or a mistyped Tier-1 stress mark, never
    a genuine reading, so this fires unconditionally); a token matching a
    known dot-prone suffix shape, unmarked (`detectors.suffix_mark_flags` —
    a table of base+mark+suffix-continuation entries keyed to keying_spec.md
    §5.1's measured bare-vs-marked skews, also unconditional); `text` carries
    notation with no `resolved` field at all
    (nothing to check against — the skill's contract was skipped); `resolved`
    names a codepoint absent from `text` (the field describes a reading the
    characters do not contain, so either was mistyped); `text` carries a
    codepoint `resolved` never mentions (the field is incomplete, or the
    character is the wrong one).
    """
    apostrophe_issues = {
        "english": "straight apostrophe on an English token (§1: the book "
                   "sets curly ’ in English prose too — same rule as the "
                   "quote pair; not Tier-1, so no licensing exception applies)",
        "unlicensed": "apostrophe unlicensed (§2.1: not post-b/p/d/t/g/k, not "
                      "V_V — almost certainly a mistyped stress mark)",
        "ambiguous": "apostrophe in V_V position (§4: licensed in principle, "
                     "but zero confirmed instances corpus-wide — almost "
                     "certainly a mistyped stress mark, not auto-fixable "
                     "since the swap needs a human's confirmation)",
    }
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for idx, rec in sorted(data.get("lines", {}).items(), key=lambda kv: int(kv[0])):
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        for hit in apostrophe_flags(text):
            out.append({"line": idx, "issue": apostrophe_issues[hit["kind"]],
                        "token": hit["token"], "context": hit.get("context", hit["token"])})
        for hit in suffix_mark_flags(text):
            out.append({"line": idx, "issue": f"bare suffix, expected "
                        f"{hit['expected']!r} (§5.1: strong corpus-wide "
                        "bare-vs-marked skew for this shape) — check for a "
                        "dropped mark", "token": hit["token"]})
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

    A medial ASCII A/E/I/L never gets auto-replaced, even in an otherwise-clean
    1-for-1 — it still *counts* toward `present` (via `_notation_codepoints`),
    because that accounting is what makes a line with two independent errors
    correctly report as two dangling items instead of a false clean swap. But
    which small-cap an ASCII capital was meant to be is a judgement call in a
    way a mistyped combining mark is not (ring below vs dot below is a shape
    slip; 'A' vs 'ᴀ' vs a genuine capital is not), so the swap itself is left
    to a human — `check()` still flags it via the same mismatch report.
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
        if wrong in "AEIL":
            continue  # medial ASCII cap: flagged by check(), never auto-swapped
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
