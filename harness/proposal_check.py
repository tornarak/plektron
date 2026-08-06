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

# What a reader's `note` is *about*, as a closed set, so the review UI can colour
# the classes apart instead of rendering one undifferentiated amber paragraph.
#
# The set is closed and small on purpose: an open vocabulary is a free-text field
# with extra steps, and the whole value here is that the adjudicator learns four
# colours and can then skip on sight. Each is a different question:
#
#   doubt     the reader could not close it at the 4x ceiling. The only class
#             that asks the adjudicator for a ruling.
#   semantic  the letterforms are settled and the sense is not — the
#             fluent-nonsense case, which is otherwise invisible precisely
#             because nothing about the characters looks wrong.
#   print     a letter or a word the compositor set wrong, keyed verbatim per
#             keying_spec §2.14. Letters and words only: a stray mark of
#             punctuation is a blot, and blots are `artifact`.
#   layout    a band, gap, dropped line or covered zone — about geometry rather
#             than glyphs, and settled by a different instrument.
#   artifact  an ink speck ruled not-type. A ruling already made, worth a
#             spot-check and no more; the commonest note there is.
#
# A note with no class is valid and renders neutral: the undimming that makes any
# of this work is earned by writing a note at all, and a reader who is unsure
# which class applies must not be pushed toward silence.
#
# `print` is letters and words because it used to be anything. It was the only class
# that let a reader *conclude* rather than hand up, and what it concluded was that
# the book was wrong — so it absorbed every mark the eye could not otherwise place.
# Five readers of one fifteen-page batch keyed a blot as punctuation and filed it
# here, each having zoomed first, each reporting the ink confirmed; every one was
# struck by the adjudicator. Zooming shows a mark is there, never that it is type.
NOTE_CLASSES = ("doubt", "semantic", "print", "layout", "artifact")

# What `_added_terminal_punctuation` will question at the end of a line. Sentence
# punctuation only: a closing bracket or quote is structural, routinely spans a
# line break, and disagreeing with the draft about one is ordinary work.
TERMINAL_PUNCTUATION = ",.;:"


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
    """Codepoints a `resolved` field names, **decomposed to the corpus's own form**.

    A reader naming `U+00EA` means "ê", which is the ordinary way to refer to the
    letter and is how the spec's own tables print it. But the corpus is NFD, so
    U+00EA never occurs in any `text` — comparing the two literally made a
    correctly-named precomposed letter *always* absent from the text and the
    combining mark actually there *always* unaccounted for, one dangling item on
    each side. `fix()` reads exactly that shape as an unambiguous 1-for-1 swap.

    On `1-039` line 38 it fired: `êlh-aˊᵋttᴀm`, NFD, plus a `resolved` naming
    U+00EA, and the "correction" dropped the precomposed letter into the combining
    mark's slot — `e` + `ê` = `eêlh-`. The reader caught it with `codepoints` and
    worked around it by respelling every `resolved` field as decompositions, which
    is a human degrading their own notes to route around a parser.

    Folding here rather than at the call sites because both directions of the
    comparison need it and only one of them was ever going to be remembered.
    """
    out: set[int] = set()
    for h in HEX_RE.findall(resolved):
        for ch in unicodedata.normalize("NFD", chr(int(h, 16))):
            out.add(ord(ch))
    return out


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


def _keyed_by_hand(rec: dict, text: str) -> str:
    """The part of a reading the reader's own eyes produced.

    A line with no `as_typed` is all its own; otherwise it is `as_typed` with the
    handles cut out, which leaves exactly the characters the reader keyed. Used by
    the arms that ask a reader to account for what it read.
    """
    from .lookup import HANDLE

    typed = rec.get("as_typed", "")
    return HANDLE.sub("", typed) if typed else text


def _handle_issues(idx: str, rec: dict, text: str, root: Path) -> list[dict]:
    """The provenance record and the reading must agree, or neither is evidence.

    Two defects and deliberately no third. There is **no arm noticing a hand-typed
    form the lookup could have supplied**: it would fire on ordinary correct reading
    on nearly every Tier-1 line of every page — a detector firing on ordinary work
    buries the real hits, which is the failure `CLAUDE.md` names — and its only
    actionable reading would be "you should have used a handle here", which is
    pressure to stop looking at the raster.
    """
    from .lookup import HANDLE, expand

    out = []
    typed = rec.get("as_typed", "")
    if typed and not HANDLE.search(typed):
        out.append(issue(idx, "as_typed carries no handle",
                         detail="the field records that the corpus supplied part "
                                "of this line; with no handle in it, it records "
                                "nothing and badges the line for no reason"))
    elif typed:
        want, refusals = expand(typed, root)
        if refusals:
            out.append(issue(idx, "as_typed no longer resolves",
                             detail="; ".join(refusals)))
        elif unicodedata.normalize("NFD", want) != unicodedata.normalize("NFD",
                                                                         text):
            out.append(issue(idx, "as_typed does not expand to text",
                             detail=f"expands to {want!r}, line holds {text!r} — "
                                    "one of them was edited without the other, so "
                                    "neither is a record of what happened"))
    if "{" in text or "}" in text:
        out.append(issue(idx, "brace in the reading",
                         detail="no page keys a brace; this is a handle that was "
                                "never expanded, or a character belonging in a "
                                "note rather than in the text"))
    return out


def _expanded(value: str, field: str, root: Path | None) -> tuple[str, str | None]:
    """Resolve any `{key}` handles in a reading, and keep what was typed.

    **The expansion happens here, on write, and not when the review server serves
    the line.** Both put the ratified glyphs in front of the adjudicator, but only
    this one leaves `text` and the decision comparing like with like: expanding at
    serve time would make every handled line differ from its proposal, so it would
    read as a human edit in `save_decisions` and enter `ocr corrections` as a
    correction class — the pass's own error profile polluted by its own tooling.

    `as_typed` is the provenance record and the reason a handle is safe to offer at
    all. The firewall's rule is that a comparison whose witnesses may be one witness
    must say so; a reader that quietly copies a corpus spelling has collapsed two
    witnesses into one, and this is the field that says so, out of which the review
    UI derives the badge. **Derived, never asserted** — a self-reported class could
    be omitted by the reader whose claim it describes.

    Only `text` is expanded. A note may mention a handle without meaning it.
    """
    if field != "text" or "{" not in value:
        return value, None
    from .lookup import expand

    out, refusals = expand(value, root if root is not None else Path("."))
    if refusals:
        raise ValueError("; ".join(refusals) + ". Nothing was written: a "
                         "half-expanded line records neither what was read nor "
                         "what was meant")
    return out, value


def set_field(path: Path, line: str, field: str, value: str,
              root: Path | None = None) -> dict:
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
    text, typed = _expanded(value, field, root)
    rec[field] = unicodedata.normalize("NFD", text)
    _set_as_typed(rec, field, typed)
    _write_json(path, data, _src)
    return {"path": str(path), "line": line, "field": field,
            "expanded": typed or ""}


def _set_as_typed(rec: dict, field: str, typed: str | None) -> None:
    """Record the handles, or **clear the record** when there are none left.

    The clear is the half that matters. A reader that writes a handled line and
    then keys it out by hand has withdrawn the corpus claim, and a stale `as_typed`
    would leave the review UI badging a reading as a corpus match forever after —
    a provenance record that outlives the provenance is worse than none.
    """
    if field != "text":
        return
    if typed is None:
        rec.pop("as_typed", None)
    else:
        rec["as_typed"] = unicodedata.normalize("NFD", typed)


def set_fields(path: Path, values: dict, field: str,
               root: Path | None = None) -> dict:
    """Set one field on many lines, in one write. NFD on the way in, as `set_field`.

    **The turn cost of authoring is what this exists for.** A reader issues a
    command and reads its result as two separate turns, so every single-line write
    costs two of `maxTurns: 80`. `1-101` — a two-column numbered list of native
    names, where nearly every line wants Tier-1 keying — spent 23 `proposal set`,
    3 `proposal replace` and 14 `Edit` calls across 21 distinct lines, hit the cap
    exactly, and was cut off mid-correction with the page still open. Only one line
    was touched more than once, so this was not thrash: it was forty corrections
    arriving one per turn, on a page that needed forty corrections. `1-100`, the
    other structured page in the corpus, ran to 73 turns the same way.

    So the bulk form is not a convenience. A page whose every line needs authoring
    is unreadable within the budget without it, and that class of page is exactly
    the vocabulary list — the densest Tier-1 material in the book, and the material
    the whole pass is for.

    Reports which lines changed and which were already what was asked for, because
    a bulk write that says only "ok" is a bulk write nobody can check.
    """
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
    lines = data.setdefault("lines", {})
    changed, same, expanded = [], [], []
    # **Every line is resolved before any line is written.** One refused handle
    # aborts the whole call rather than leaving a page half-authored, which is the
    # rule `ocr restore` already follows for a multi-ref write and for the same
    # reason: a partial write is the state nobody can tell from a finished one.
    resolved = {}
    for line, value in values.items():
        try:
            resolved[str(line)] = _expanded(value, field, root)
        except ValueError as e:
            raise ValueError(f"line {line}: {e}") from e
    for line in sorted(values, key=lambda k: (len(k), k)):
        rec = lines.setdefault(str(line), {})
        text, typed = resolved[str(line)]
        new = unicodedata.normalize("NFD", text)
        (same if rec.get(field) == new else changed).append(str(line))
        rec[field] = new
        _set_as_typed(rec, field, typed)
        if typed is not None:
            expanded.append(str(line))
    _write_json(path, data, _src)
    return {"path": str(path), "field": field, "set": len(values),
            "changed": ",".join(changed), "unchanged": ",".join(same),
            "expanded": ",".join(expanded)}


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
    out += _segmenter_missed_issues(data)
    out += _footnote_issues(data)
    if ref is not None:
        from .marks import page_issues

        out += _orphan_line_issues(data, ref, root)
        out += _added_terminal_punctuation(data, ref, root)
        out += page_issues(path, ref, root)
    for idx, rec in sorted(data.get("lines", {}).items(), key=lambda kv: int(kv[0])):
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        nclass, note = rec.get("class", ""), rec.get("note", "")
        if nclass and nclass not in NOTE_CLASSES:
            out.append(issue(idx, f"unknown note class {nclass!r}",
                             detail="one of " + ", ".join(NOTE_CLASSES)))
        if nclass and not note:
            out.append(issue(idx, "note class with no note",
                             detail=f"class {nclass!r} asserts nothing"))
        # Advisory, not a defect, though it is plainly satisfiable: the class
        # only decides which badge the note wears, and the part that fixes the
        # `Kuvár` failure — a noted line is never dimmed — happens without it.
        # Gating on it would make an unclassifiable observation cost the reader
        # its note, which is the opposite of the point.
        if note and not nclass:
            out.append(issue(idx, "note with no class (which of "
                             + "/".join(NOTE_CLASSES) + " is it?)",
                             severity=ADVISORY))
        out += _handle_issues(idx, rec, text, root)
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
        # **Scoped to what the reader actually keyed.** `resolved` exists so a
        # reader documents the marks it settled at the raster; a handle is a
        # declaration that it settled none of them, the corpus having supplied the
        # glyphs whole. Demanding a `resolved` for those would ask the reader to
        # narrate a reading that is not its own — and an invented account of how a
        # mark was decided is worse than no account, since it is indistinguishable
        # from a real one. The hand-keyed remainder still answers for itself.
        present = set(_notation_codepoints(_keyed_by_hand(rec, text)))
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


def _segmenter_missed_issues(data: dict) -> list[dict]:
    """`segmenter_missed` carrying anything at all. A defect, unconditionally.

    **The field is illegal.** It let a reader record printed matter the segmenter
    dropped, inside the proposal, as a finding travelling with the reading. That
    made the proposal the place a segmentation fault was reported, and a reading
    the thing that carried it — so a line's identity could be argued from a
    transcriber's note rather than from a box. The line store is the upstream
    source of truth: `mz/ocr/` patched by the human corrections a zone editor
    draws into `gt/lines/`, every line id anchored there, provenance running
    forward from it. Nothing downstream of that store may propose a line into
    existence, and a proposal is downstream.

    Finding text with no box is still worth finding — it is simply **not the
    transcriber's to correct.** It is upstream human action: a human draws the
    band a box in `harness ocr edit`, the index exists from then on, and the page
    is re-read against a store that now holds it. So a reader reports it *to the
    human, in its report*, and keys nothing; the proposal stays a reading of the
    boxes that exist.

    An **empty** block is inert legacy, not a finding — `fix` strips it silently
    and nothing gates. Only content fires, because only content is a reading that
    went somewhere it may not go.
    """
    block = data.get("segmenter_missed")
    if not block:
        return []
    return [issue("-", "`segmenter_missed` is illegal — the line store is the "
                       "upstream source of truth and a proposal may not propose "
                       "a line into existence. Printed matter with no box is "
                       "upstream human action: report it to the human, key "
                       "nothing, and let a box be drawn in `harness ocr edit` "
                       "before the page is read against it.",
                  detail=f"block holds {len(block)}")]


def _added_terminal_punctuation(data: dict, ref: str, root: Path) -> list[dict]:
    """A line ending in punctuation the machine draft does not end in.

    **The commonest fabrication this pass produces.** Nine line-final commas over
    two batches — `1-079`, `1-092`, `1-099`, then `1-103` L4, `1-104` L33, `1-107`
    L3, `1-109` L35, `1-110` L3 and L24 — none of them on the page, and none of
    them in `mz/ocr` either, so no recognizer artifact carried them in. Six of the
    ten pages in one batch, past readers who had answered every advisory they were
    given, which is what says the rule alone will not hold it.

    Why they appear is not settled. They sit at the end of the value, beside the
    closing quote, which reads like a serialization slip — but three of the four
    inspected sat in a record with no following field, so there was no separator to
    bleed in from. The *shape* is what is stable: always terminal, never mid-line,
    always absent from the draft. So the detector keys on the shape and takes no
    position on the cause.

    **Terminal only, and against the draft rather than against a rule of prose.**
    A comma the reader restores because the recognizer dropped one is a real
    correction and must stay possible; what makes this checkable is that CATMuS is
    a competent witness to ASCII punctuation, so a disagreement is worth one look
    at `@100` — the length of the crop is not a judgement call there.

    A defect when the line says nothing about it, an advisory once the line carries
    a `note`: the gate is satisfiable either way — look, then delete the mark or
    say what you saw — and a reader that looked and found the comma genuinely
    printed must not be stuck. This is `_footnote_issues`'s `explained` shape, for
    the same reason.
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
    draft = {str(r["index"]): (r.get("text") or "") for r in page_lines(alto, root)}
    out = []
    for k, rec in sorted(lines.items(), key=lambda kv: (len(kv[0]), kv[0])):
        text = (rec or {}).get("text", "").rstrip()
        was = draft.get(str(k), "").rstrip()
        # Only when the draft has a line to disagree with: an empty one is a
        # recognizer that returned nothing, which is no witness at all.
        if not text or not was or text[-1] not in TERMINAL_PUNCTUATION:
            continue
        if was and was[-1] == text[-1]:
            continue
        # The bodies have to match apart from the mark, or this is not "a comma
        # was added" but "the line was rekeyed", which the reader is entitled to
        # do and which this detector has no opinion about.
        if text[:-1].rstrip() != was:
            continue
        out.append(issue(k, f"line ends {text[-1]!r}, the draft does not — the "
                         "commonest fabrication on this pass is a line-final "
                         "comma that is on no page and in no draft. Look at "
                         "`@100` before keeping it",
                         token=text[-1], context=text[-28:],
                         severity=ADVISORY if (rec or {}).get("note") else DEFECT))
    return out


def _orphan_line_issues(data: dict, ref: str, root: Path) -> list[dict]:
    """Proposal lines with no `TextLine` in the store to hold them.

    **A proposal is keyed by the ALTO's line indices**, and `restore` joins on
    them: a key naming an index the store does not have describes text with no
    box, which is the dropped-line case wearing a different hat. Ground truth is a
    correspondence between a box and its contents, so a reading that has nowhere
    to go is not a reading. It is upstream human action — a box drawn in `ocr
    edit` — and never a line here.

    A defect rather than an advisory because there is nothing to weigh: the index
    either exists or it does not, and `restore` will silently drop what it cannot
    join. Silently is the problem. `1-037` produced the neighbouring version of
    this — a folio appended to the running title's own `text` — which this cannot
    see, since that key is a real index; the reader contract carries that half.

    Resolved through the view *and the corrections overlay*, so a page reads
    against whichever store is current — `mz/ocr/` before a restore and `gt/ocr/`
    after — plus any line a human has since drawn in `ocr edit`. A keyed
    correction is therefore not an orphan: the index exists, which is the whole
    point of giving the line a box. A page with no ALTO at all is skipped rather
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
                     "the segmenter missed, that is upstream human action and "
                     "not yours to correct: drop the key, say what you saw in "
                     "your report, and a human gives the band a box in `harness "
                     "ocr edit` before the page is read again.",
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
    # The locants the pairing arms were told to ignore, reported at the advisory
    # tier. They cannot gate — being unpaired is what a locant *is*, so a gate
    # here is the one `1-137` failed by mis-keying `a¹` to `a1`. But the
    # exclusion rests on a bracket and a neighbouring letter, and a genuine
    # marker wearing that shape would vanish out of the count in silence, so it
    # says what it dropped and lets the adjudicator look.
    out = [issue(lo["line"], "figure locant, not a footnote", severity=ADVISORY,
                 token=f"{lo['digit']}", context=lo["text"],
                 detail="a raised numeral labelling a figure sub-part anchors no "
                        "note; excluded from the marker count. Key it as printed.")
           for lo in rep["figure_locants"]]
    if not problems:
        return out
    explained = (data.get("footnotes") or {}).get("note") if \
        isinstance(data.get("footnotes"), dict) else data.get("footnotes")
    detail = "; ".join(problems)
    if explained:
        detail += f" — explained: {explained}"
    return out + [issue("-", "footnote markers", detail=detail)]


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
    if "segmenter_missed" in data and not data["segmenter_missed"]:
        # Inert legacy: the field is illegal but an empty one carries no reading,
        # so it folds away silently rather than gating. A non-empty block is a
        # human's to disposition and `check` reports it — never stripped here,
        # which would delete the finding along with the field.
        del data["segmenter_missed"]
        changed.append({"line": "-", "replaced": "segmenter_missed", "with": ""})
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
        # NFD on the way out, as the docstring has always claimed: `right` comes
        # from a `resolved` field and may be a precomposed sort, and substituting
        # it raw writes NFC into an NFD corpus for `corpus normalize` to find
        # later — if anyone runs it.
        new_text = unicodedata.normalize("NFD", nfd.replace(wrong, right))
        rec["text"] = new_text
        changed.append({"line": idx,
                        "replaced": f"U+{ord(wrong):04X}", "with": f"U+{ord(right):04X}"})
    if changed:
        _write_json(path, data, _src)
    return {"path": str(path), "changed": changed}
