"""What a page ref *is*, and the small readings that need nothing else.

**Imports nothing from this package**, like `ns.py`, `atomic.py` and `mets.py`.
That is the whole point of the module rather than a property it happens to have:
`norm_ref` and `parse_ref` are the two most-imported names in the harness — 31
and 20 non-test call sites — and they lived in `context.py`, which sat in **10 of
the package's 19 mutual import cycles**. Every module that wanted to spell a ref
had to reach into the module that assembles a whole collation prompt, and reach
for it through a function body to avoid closing a loop. That is where the 392
function-local imports came from.

A leaf cannot join a cycle, so these are declared once, at the bottom, and
everything above may take them at module scope.

PAGE REFS. A page is identified by its **PP-NNN** ref — part, and scan index
within that part — and by nothing else. NNN is a scan index, *not* a printed
folio: part 1 runs 001-362, part 2 001-268, part 3 001-202, while the printed
folio runs continuously 1-732 across the volume with plates and front matter
unpaginated. Neither is derivable from the other, so nothing here tries. A bare
integer is not a page identifier anywhere in this harness; where a folio is
needed it comes from `state.py`, which knows it only because a transcribed page
recorded one.

**What is here and what is not.** A reading that needs only its argument lives
here — parsing a ref, reading a folio off lines already loaded, a caption's
figure number. Anything that must *find* a page belongs to `paths.py`, which
knows the stores; anything that assembles a page's context stays in `context.py`,
which knows everything.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

REF_RE = re.compile(r"^(?:chukchi-)?(\d+)-(\d+)$")

# **Where a folio may be printed, in the order it is looked for.** Three places,
# because the book puts the number in three, and the order is the order of
# confidence rather than of frequency:
#
#   RunningTitleZone  the ordinary page. Head line, folio bare beside the head.
#   QuireMarksZone    a chapter opening. No running title at all, the number set
#                     at the **foot** of the page and **in brackets** — `1-151`
#                     reads `[115]` at vpos 3231 of a 3897 px page, and its
#                     collated TEI gives `<pb n="115"/>`.
#   NumberingZone     the old full-SegmOnto vocabulary `gt/ocr/` descends from,
#                     which split the folio out of the head as its own zone. The
#                     current scheme cannot express that split — a fixed-width
#                     vertical partition has nowhere to put it, and the two are on
#                     one printed line (`config/zones.json`). Last because it
#                     is the store-specific spelling, not a place on the page: it
#                     appears at the head on `1-048` and at the foot on `1-151`.
#
# Reading all three matters because the two stores speak different vocabularies for
# the same ink, and `gt/ocr/` — which speaks the old one — is where the collation
# frontier is.
FOLIO_ZONES = ("RunningTitleZone", "QuireMarksZone", "NumberingZone")

# Zones whose text the printer set rather than the author: the head line, the
# signature line at the foot of a gathering, and the folio in whichever of them it
# lands. `build_context` keeps them out of the collation draft; see the comment at
# the exclusion for why there and not at the point the page is recognized.
APPARATUS_ZONES = frozenset(FOLIO_ZONES)


def parse_ref(ref: str) -> tuple[int, int]:
    """'1-048' | '1-48' | 'chukchi-1-048' -> (1, 48). Anything else is an error.

    Deliberately strict about shape and deliberately lenient about zero-padding:
    the ref is typed by hand at a CLI, but a bare integer must never silently
    become a page.
    """
    m = REF_RE.match(str(ref).strip())
    if not m:
        raise ValueError(
            f"{ref!r} is not a page ref — expected PP-NNN (part, scan index "
            "within that part), e.g. '1-048'. Bare page numbers are not page "
            "identifiers: the printed folio is not derivable from the scan index.")
    return int(m.group(1)), int(m.group(2))


def norm_ref(ref: str) -> str:
    """Canonical ref spelling, matching the filenames: part bare, index to 3."""
    part, idx = parse_ref(ref)
    return f"{part}-{idx:03d}"


def stem_for(ref: str, root: Path = Path(".")) -> str:
    """The filename stem for a ref.

    `root` is accepted and ignored — the stem is a function of the ref alone —
    and 7 call sites pass one, so the parameter stays rather than becoming 7
    edits that change no behaviour. Moved verbatim, signature included: a split
    that quietly retyped an argument would be a refactor nobody could check by
    reading the diff.
    """
    return f"chukchi-{norm_ref(ref)}"


CONTEXT_RE = re.compile(r"^(?:(\d+)|(?:(?:-(\d+))?(?:\+(\d+))?))$")


def parse_context(spec: str) -> tuple[int, int]:
    """`'5' | '+5' | '-5' | '-5+3'` -> (behind, ahead). Counts are inclusive.

    A bare count means that many **each way**, which is what someone asking for
    "context" almost always means; the signed forms are for when the question is
    one-sided — what a seam ran into, or what a batch is about to reach.

    Signed and unsigned are deliberately not mixed (`5+3` is refused): a reader of
    the command should not have to know whether the bare number binds left, right
    or both when a sign is already present.
    """
    s = str(spec).strip()
    m = CONTEXT_RE.match(s)
    if not m or not s:
        raise ValueError(
            f"--context {spec!r}: expected N (each way), +N (ahead), -N (behind) "
            "or -N+M. Counts are inclusive and a sign binds only its own side.")
    both, behind, ahead = m.groups()
    if both is not None:
        return int(both), int(both)
    return int(behind or 0), int(ahead or 0)


# A folio is a number standing **alone** on its line, optionally in brackets.
# Arabic for the body, roman for the front matter (part 1's is printed xii-xvii).
#
# **Deliberately strict about everything else**: no other punctuation, no digits
# embedded in words, nothing repaired. A recognizer's `2S` for `28` must fail this
# and fall through, leaving the line for a human to read — the alternative is a
# plausible page number with no error signal, which is the failure this project is
# organised against.
#
# The brackets are captured rather than tolerated. `1-151` prints `[115]` at the
# foot of a chapter opening and its collated TEI reads `<pb n="115"/>`, so the
# editor read through them — but whether a bracketed folio is the printer's or
# supplied is a judgement about the book, and `bracketed` carries it forward
# instead of discarding it at the point the number is parsed.
_FOLIO_RE = re.compile(r"^(\[)?(\d{1,4}|[ivxlcdm]{1,7}|[IVXLCDM]{1,7})(?(1)\])$")


def _folio_in(lines: list[dict]) -> tuple[str, bool] | None:
    """First line that is nothing but a page number. `(folio, bracketed)`."""
    for r in lines:
        m = _FOLIO_RE.match((r["text"] or "").strip())
        if m:
            return m.group(2), bool(m.group(1))
    return None


def _window_folio(expected: int | None, running: dict | None) -> tuple[int | None, str]:
    """Which folio centres `toc_window`, and which witness supplied it.

    **The cold start this exists for.** `expected_folio` is a prediction from the
    preceding *collated* page, so it is null at the front of any run; `toc_window`
    filters ToC entries by distance from it, so with a null folio the distance test
    never fires and the window falls back to `believed_open` — itself a fold over
    collated pages, and likewise empty when nothing precedes. The window therefore
    came back empty, no heading could match an entry that was not in it, and the
    collation rules turn every unmatched heading into an unresolved comment. Serially
    that was the first page of a run; under a dispatched batch it is all of them.
    `1-075` is the case: two headings, both chapter openings, both invisible.

    The page's own running title is the better witness anyway. CLAUDE.md's rule is
    that the page says what page it is and nothing infers it — a running title is the
    page saying so, where `expected_folio` is a neighbour's arithmetic.

    **`expected_folio` is deliberately not filled from this.** It is the *prediction*
    and when there is none there is none; writing this page's own folio into it would
    manufacture the second witness and leave the disagreement check comparing a value
    with itself. That is the comparison whose witnesses may be one witness, which
    CLAUDE.md says must say so — and it says so here, in the returned witness, rather
    than by falling silent.

    `running["folio"]` is transcribed content and so a string, and not always an
    integer: a number that did not read cleanly stays in `text` with `folio` null, on
    `_running_title`'s own "null means go and look" contract. Both witnesses absent is
    a real state, and `"none"` is what separates "nothing near this folio" from "no
    folio to be near" — an empty window alone cannot say which.
    """
    if expected is not None:
        return expected, "expected_folio"
    try:
        return int(str((running or {}).get("folio")).strip()), "running_title"
    except (TypeError, ValueError):
        return None, "none"


def _draft_text(lines: list[str]) -> str:
    # Paragraph reconstruction is the model's job (indent/blank-line reading of
    # the image); the draft is line-per-line, NFD like everything else.
    return unicodedata.normalize("NFD", "\n".join(lines))


_FIG_N = re.compile(r"^\s*Figs?\.\s*(\d+)")


def figure_number(caption: str) -> str | None:
    """The figure number a caption prints, or None.

    Deliberately anchored at the start and deliberately not clever: `1-207`
    opens `Fig. 87, a (??/????), b …` and the answer is 87, where the catalogue
    numbers, the letters and the dimensions that follow are not numbers of
    anything. A caption that does not open this way has no number, which is a
    real state — `3-006`'s zone has no caption at all.
    """
    m = _FIG_N.match(caption or "")
    return m.group(1) if m else None
