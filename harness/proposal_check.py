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

import json
import re
import unicodedata
from pathlib import Path

from .codepoints import non_ascii
from .detectors import (
    INVENTORY_CHARS,
    MEDIAL_CAPS,
    apostrophe_flags,
    footnote_report,
    suffix_mark_flags,
)

HEX_RE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")
# The trigger set is `detectors.INVENTORY_CHARS` itself, not a re-derived Unicode
# category — the small caps ᴀᴇɪ and ᵋ are ordinary letter categories (Ll/Lm) and a
# category-based heuristic would miss them entirely, silently exempting exactly
# the glyphs most worth cross-checking. Dotless ı is inventory-adjacent (§2.6's
# ĭ = dotless-i + breve) but absent from INVENTORY_CHARS, so it is added here.
DOTLESS_I = "ı"
NOTATION_CHARS = INVENTORY_CHARS | {DOTLESS_I}

# The one issue-record shape, and the only constructor for it.
#
# Six detectors feed `check` — three here, two in `marks.page_issues`, one in
# `_footnote_issues` — and each used to name its own fields: `context` beside
# `token`, `detail` beside `token`, `in_text`, `in_text_not_resolved` beside
# `in_resolved_not_text`, `explained`. Six key sets over one list of records, which
# is exactly the raggedness `emit`'s docstring says degrades a TOON table to the
# verbose nested form. It did: a corpus sweep emitted 265 findings as 51 KB of
# indented blocks, and pooling several refs tripped `_pool`'s list guard on the way
# past. The detectors already had this rule imposed on them once, for the same
# reason ("one `token` key rather than `span` for some flag types") — this is that
# rule with a constructor behind it, so the next detector cannot quietly reopen it.
#
# `detail` is where a shape that is not a token goes, rendered as text: the
# codepoint sets both `resolved` arms report, and the footnote arm's editorial note.
# A list never reaches the record.
ISSUE_FIELDS = ("line", "issue", "severity", "token", "context", "detail")

# The two severities, and the rule that separates them: **a gate must be
# satisfiable by the actor it gates.**
#
# DEFECT is a claim that something *is* wrong and that the reader can put it
# right — `resolved` naming codepoints the text does not contain, a straight
# apostrophe (never a genuine reading corpus-wide), notation with no `resolved`
# at all, a footnote marker that pairs with nothing.
#
# ADVISORY is measurement: leave-one-out corpus statistics saying "this shape is
# rare, go look". It cannot be *satisfied*, only answered — there is no field
# recording "checked, genuinely bare", and for a cross-page spelling conflict the
# second witness is a page the reader is forbidden to open. It gated anyway until
# now, and the damage was exactly what a gate nobody can pass does: eight of
# eighteen failing proposals in `review/` failed on advisories alone, the reading
# brief had to be rewritten to say "exit 1 is sometimes fine", and a real
# `resolved/text mismatch` became indistinguishable from a rare surname.
#
# So `measurement never gates` (VERBS.md, Conventions) is applied here too. An
# advisory still prints, at the same volume, in the same table — it simply stops
# claiming to be a gate. `--strict` gates on both, for a sweep where every prompt
# is meant to be chased.
DEFECT = "defect"
ADVISORY = "advisory"


def issue(line, text: str, token: str = "", context: str = "",
          detail: str = "", severity: str = DEFECT) -> dict:
    """One issue record, every field present. See `ISSUE_FIELDS`.

    `severity` defaults to `DEFECT` because that is the safe direction: a new
    detector added without thinking about severity gates, and someone notices.
    The reverse default would let one land silently and never fire.
    """
    return {"line": str(line), "issue": text, "severity": severity,
            "token": token, "context": context, "detail": detail}


def _cps(codepoints) -> str:
    """A codepoint set as `U+02CA U+026A`, sorted — `detail` text, not a list."""
    return " ".join(sorted(f"U+{c:04X}" for c in codepoints))


def _notation_codepoints(text: str) -> list[int]:
    """Codepoints a `resolved` field is expected to name.

    Any combining mark at all (Unicode category Mn), not only the ones
    `INVENTORY_CHARS` already knows about — a mark entirely foreign to the
    inventory (ring below, say, where dot below was meant) is exactly the
    error this module exists to catch, and restricting to known-good marks
    would make it invisible for having the wrong identity instead of a
    licensing problem.

    Also counts a word-medial ASCII A/E/I/L (`detectors.MEDIAL_CAPS`, the same
    check `harness tei context` already runs over OCR text) as a codepoint present.
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


def _stated_but_absent(stated: set[int], text: str) -> set[int]:
    """Codepoints `resolved` names that the text does not contain at all.

    **The two directions of this comparison are not symmetric**, and treating
    them as if they were made the gate punish thoroughness. `_notation_codepoints`
    is deliberately narrow — combining marks and medial caps, the things a
    `resolved` field is *obliged* to name — so subtracting it from `stated`
    flagged any codepoint a reader spelled out that merely was not a combining
    mark, even when it sits plainly in the text. `2-042` was refused for
    documenting the hyphen of `Čiñeiˊ-ñew` and the superscript of `Peruˊten³`: a
    hyphen is load-bearing in Americanist notation and the superscript is the
    entire subject of §2.10, so both are exactly what a careful reader writes
    down, and the gate told them not to.

    What this direction exists to catch is the defect the reading pass names — a
    `resolved` describing a keying decision *the text does not exhibit*, which
    argues an adjudicator into undoing correct work. That is a claim about the
    text's characters, so it is answered against them.
    """
    return stated - {ord(ch) for ch in unicodedata.normalize("NFD", text)}


def set_field(path: Path, line: str, field: str, value: str) -> dict:
    """Set one line's field, NFD-normalizing on write.

    Exists because hand-typing a replacement for `Edit` risks producing NFC
    where the file (already run through `normalize --convert`) holds NFD —
    `ñ` typed as one keystroke is U+00F1, the file's is `n`+U+0303, and the two
    are invisible to each other under exact string match. Writing through here
    instead of Edit sidesteps the mismatch by construction: whatever comes in,
    NFD goes out, same as `normalize.py`'s one conversion point.
    """
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
    rec = data.setdefault("lines", {}).setdefault(line, {})
    rec[field] = unicodedata.normalize("NFD", value)
    _write_json(path, data, _src)
    return {"path": str(path), "line": line, "field": field}


def _write_json(path: Path, data: dict, original: str) -> None:
    """Serialize back in the indentation the file already used.

    These editors are aimed at `proposal.json`, which this module also authors
    at `indent=2` — but `--path` lets them target `decision.json`, which
    `review.save_decisions` writes at `indent=1`. Imposing this module's own
    format on a file it does not own turned a 10-line correction across four
    pages into a 716-line diff, which is the same failure `migrate_coords.py`
    documents for attribute number formatting: gratuitous reformatting buries
    the change that matters, and a diff nobody can read is a diff nobody checks.

    Falls back to `indent=2` when the original has no indented line to measure
    (a fresh or single-line file), so an authored proposal keeps its own shape.
    """
    indent = 2
    for ln in original.splitlines()[1:]:
        stripped = ln.lstrip(" ")
        if stripped and stripped != ln:
            indent = len(ln) - len(stripped)
            break
    trailing = "\n" if original.endswith("\n") else ""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + trailing,
                    encoding="utf-8")


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
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
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
    _write_json(path, data, _src)
    return {"path": str(path), "line": line, "field": field, "old": old,
            "new": new, "which": which, "occurrences": len(positions),
            "replaced": len(selected)}


def line_codepoints(path: Path, line: str | None = None,
                    field: str = "text") -> list[dict]:
    """Non-ASCII characters in a line's field, named — a typed-mark spot check.

    Not a substitute for `check()`/`resolved`: this names what is actually in
    the text (e.g. "U+0131 LATIN SMALL LETTER DOTLESS I" where U+026A ɪ was
    intended), it does not know what was *meant*. Use it to settle a doubt
    about one line while authoring, before `resolved` is even written.

    `line` omitted means every line on the page, each row carrying its own
    `line`. That is the census the action's plural form needs, and the more
    useful default besides — asking what a proposal actually contains rather
    than confirming one line at a time.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = data.get("lines", {})
    if line is not None:
        rec = lines.get(line)
        if rec is None:
            raise KeyError(f"no line {line!r} in {path}")
        return [{"line": line, **r} for r in non_ascii(rec.get(field, ""))]
    return [{"line": k, **r} for k, rec in lines.items()
            for r in non_ascii(rec.get(field, ""))]


def check(path: Path, ref: str | None = None, root: Path = Path(".")) -> list[dict]:
    """Per-line mismatches between what `text` contains and what `resolved` claims,
    plus apostrophe hits independent of `resolved` entirely.

    Given a `ref`, also runs the two deterministic arms of `marks.page_issues` —
    a form whose confusable the corpus almost never sets, and one word spelled two
    ways against the store. Those need the corpus, which is why they arrive with a
    `root` rather than out of the file; without a `ref` they are skipped, since
    leave-one-out cannot be applied to a page that has not said which it is.

    **Overlap with `suffix_mark_flags` is wanted, not deduplicated.** A bare `-gɪn`
    produces both that flag and a rare-form issue on the same line. They are
    independent witnesses reaching one defect from different directions — the
    suffix table from a measured shape, the rare form from a corpus share — and
    this project's governing principle asks for a second witness wherever one is
    cheap. Suppressing either would buy a shorter report with a blind spot in it.

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
    out += _footnote_issues(data)
    if ref is not None:
        from .marks import page_issues

        out += _orphan_line_issues(data, ref, root)
        out += page_issues(path, ref, root)
    for idx, rec in sorted(data.get("lines", {}).items(), key=lambda kv: int(kv[0])):
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        for hit in apostrophe_flags(text):
            out.append(issue(idx, apostrophe_issues[hit["kind"]],
                             token=hit["token"],
                             context=hit.get("context", hit["token"])))
        for hit in suffix_mark_flags(text):
            out.append(issue(idx, f"bare suffix, expected "
                             f"{hit['expected']!r} (§5.1: strong corpus-wide "
                             "bare-vs-marked skew for this shape) — check for a "
                             "dropped mark", token=hit["token"],
                             severity=ADVISORY))
        present = set(_notation_codepoints(text))
        if not present:
            continue
        stated = _stated_codepoints(resolved)
        if not stated and not resolved:
            out.append(issue(idx, "notation with no resolved field",
                             detail=f"in text: {_cps(present)}"))
            continue
        extra_in_text = present - stated
        extra_in_resolved = _stated_but_absent(stated, text)
        if extra_in_text or extra_in_resolved:
            sides = []
            if extra_in_text:
                sides.append(f"in text not resolved: {_cps(extra_in_text)}")
            if extra_in_resolved:
                sides.append(f"in resolved not text: {_cps(extra_in_resolved)}")
            out.append(issue(idx, "resolved/text mismatch",
                             detail="; ".join(sides)))
    return out


def _orphan_line_issues(data: dict, ref: str, root: Path) -> list[dict]:
    """Proposal lines with no `TextLine` in the store to hold them.

    **A proposal is keyed by the ALTO's line indices**, and `restore` joins on
    them: a key naming an index the store does not have describes text with no
    box, which is the dropped-line case wearing a different hat. Ground truth is a
    correspondence between a box and its contents, so a reading that has nowhere
    to go is a finding — `segmenter_missed` — and never a line.

    A defect rather than an advisory because there is nothing to weigh: the index
    either exists or it does not, and `restore` will silently drop what it cannot
    join. Silently is the problem. `1-037` produced the neighbouring version of
    this — a folio appended to the running title's own `text` — which this cannot
    see, since that key is a real index; the reader contract carries that half.

    Resolved through the view, so a page reads against whichever store is current:
    `mz/ocr/` before a restore and `gt/ocr/` after, the latter including any line
    `adopt-gap` has since created. A page with no ALTO at all is skipped rather
    than reported — absent is not the same as wrong, and every line would fire.
    """
    lines = data.get("lines")
    if not isinstance(lines, dict) or not lines:
        return []
    from .lines import DEFAULT_ALTO_DIR, alto_for_lines, page_lines
    try:
        alto = alto_for_lines(ref, DEFAULT_ALTO_DIR, root)
    except Exception:
        return []
    if not alto.exists():
        return []
    have = {str(r["index"]) for r in page_lines(alto, root)}
    if not have:
        return []
    return [issue(k, "line index is not in the store — a proposal is keyed by "
                     "the ALTO's line indices and `restore` joins on them, so "
                     "this text has no box to land in. If it is printed matter "
                     "the segmenter missed, it belongs in `segmenter_missed`; "
                     "`ocr adopt-gap` makes the index later, from the measured "
                     "band.",
                  context=(lines[k] or {}).get("text", "")[:60],
                  detail=f"store holds {len(have)} lines")
            for k in sorted(lines, key=lambda s: (len(s), s))
            if str(k) not in have]


def _footnote_issues(data: dict) -> list[dict]:
    """`detectors.footnote_report` turned into proposal-check's issue records.

    The contract the editor set: markers may pass **unexplained** so long as
    they form a continuous run from 1 and each occurs at least twice; a page
    that fails either wants a written reason instead. Both failure modes have
    legitimate causes — a note whose reference and text straddle a page seam
    breaks the pairing without anything being miskeyed — so this reports and
    asks, and never refuses. That is a weaker tier than `restore`'s mark-licence
    refusal on purpose: an unlicensed mark is a sequence the notation does not
    contain, whereas an unpaired marker may simply be a page boundary.

    The explanation goes in a page-level `footnotes` key (a sibling of
    `contamination`, same shape of claim: something about the page as a whole
    that the line records cannot carry). Its presence **annotates** the issue
    rather than deleting it, so the reason still reaches the adjudicator instead
    of vanishing into a silent pass — it is appended to `detail` behind an
    `explained:` marker, since this record shares one key set with the other five
    detectors (`ISSUE_FIELDS`) and cannot carry a field of its own.
    """
    texts = [rec.get("text", "") for _, rec in
             sorted(data.get("lines", {}).items(), key=lambda kv: int(kv[0]))]
    rep = footnote_report(texts)
    problems = []
    if rep["gaps"]:
        problems.append(f"marker run has gaps: missing {rep['gaps']} from 1..{max(rep['counts'])}")
    if rep["singletons"]:
        problems.append(f"marker(s) {rep['singletons']} occur once; each is printed "
                        "twice (body reference + note opener)")
    for op in rep["ascii_openers"]:
        problems.append(f"line {op['line']} opens with bare ASCII {op['digit']!r} — "
                        f"footnote markers are keyed as the superscript digit, never "
                        f"the plain one: {op['text']!r}")
    if not problems:
        return []
    explained = (data.get("footnotes") or {}).get("note") if \
        isinstance(data.get("footnotes"), dict) else data.get("footnotes")
    detail = "; ".join(problems)
    if explained:
        detail += f" — explained: {explained}"
    return [issue("-", "footnote markers", detail=detail)]


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
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
    changed = []
    for idx, rec in data.get("lines", {}).items():
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        if not resolved:
            continue
        present = set(_notation_codepoints(text))
        stated = _stated_codepoints(resolved)
        extra_in_text = present - stated
        extra_in_resolved = _stated_but_absent(stated, text)
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
        _write_json(path, data, _src)
    return {"path": str(path), "changed": changed}
