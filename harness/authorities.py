"""Search `edition/authorities.json` — the book's own bibliography, as a lookup.

The consumer is the annotation pass, which meets a citation in the body and has
to say which of the 74 works it names. Three properties of the store make that a
search problem rather than a dictionary lookup, and all three are recorded in
docs/apparatus.md:

  - **The siglum is not the only surface form, or even the common one.** The
    footnote form (`Dall, I, p. 375.`) resolves against `cited_as`, but most
    references are indirect prose — "Krause reports that…" — carrying the name
    alone. So `author` has to be reachable, and so does the title, and so does
    the printed block itself when nothing else catches.
  - **`name` is ambiguous by construction.** 52 sigla over 34 distinct names:
    three Krauses, three Houghs, two Masons, two Jacksons, four Jochelsons.
    A search that returned one hit would be manufacturing a resolution.
  - **The list is open.** No hit is a legitimate outcome — folio 9's asterism
    says so — and is not a reconciliation failure the way a figure outside LoI
    1–302 would be.

Hence: every hit is returned, never one; each carries `matched`, the field that
caught it, so the caller can weigh a siglum hit against a full-text one; and
nothing here decides. The ranking sorts, it does not filter.

Matching is mechanical word-set containment, in the same shape as
`state.toc_search` and for the same reason — it exists to *check* a citation
someone has read, and a fuzzier match manufactures confirmation. The one
concession is `printed`, which is a case-folded substring test, because that
tier's job is to find a string the caller copied off the page verbatim.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .state import _norm_words

# Rank order, strongest first. `matched` names one of these and the sort key is
# its index, so a siglum hit always precedes a full-text one for the same query.
TIERS = ("key", "siglum", "author", "title", "printed")

_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
          "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}

# A page locator, in the forms the book's footnotes set it. Matched *anywhere* in
# the query and removed before anything else is looked at, which is what lets the
# rest be tokenized freely: `p. 375` has to stop being two tokens before a bare
# integer may be read as a volume, or the page number becomes the volume.
_PAGE_RE = re.compile(r"\bpp?\.\s*[\d]+(?:\s*[-–,]\s*\d+)*", re.I)

# Above this, a bare integer is much likelier a year than a volume. The book runs
# to three volumes and cites no higher than X; `Bogoras 1902` is a plausible query
# and reading 1902 as a volume would silently return nothing.
_MAX_VOLUME = 20


def parse_citation(query: str) -> tuple[str, int | None]:
    """Split a footnote-form citation into search text and a volume.

    `Dall, I, p. 375.` is the form a caller copies out of the body, and fed whole
    it matches nothing: the page locator is not in the store and the volume lives
    in its own field.

    **Commas are separators, not signal.** The print is inconsistent about the one
    before a volume — `Maydell I, p. 331.` sits in the same apparatus as
    `Krasheninnikoff, II, p. 49.` — so this splits on commas *and* whitespace alike
    and asks the same question of every token. An earlier version split on commas
    only, which meant `Maydell I` was a single token, was not a bare numeral, and
    kept its volume in the search text. That happened to resolve anyway, because
    the match is by word set, but it made the `volume` field depend on a
    typographic accident, and a caller filtering on it would have been quietly
    wrong for half the citations in the book.

    So: the page locator goes first, wherever it sits; then a token that is exactly
    a roman numeral or a small integer becomes the volume (the first such token —
    a citation names one work); everything else is search text in the order given.
    A short-title siglum (`Hough, Lamp`) survives untouched, since neither token is
    a numeral.

    Deliberately still shallow. Resolving a citation properly — deciding *which*
    Krause, against a body that mostly refers to authors in prose — is the
    annotation pass's job and wants a reader, not a regex. This only has to stop
    the obvious noise from reaching a word-set match.

    The CLI echoes what this took, on stderr, because a query silently rewritten
    is a query whose empty result you cannot explain.
    """
    vol = None
    keep = []
    for tok in re.split(r"[,\s]+", _PAGE_RE.sub(" ", query)):
        s = tok.strip().rstrip(".")
        if not s:
            continue
        v = _volume(s)
        if v is not None and vol is None and v <= _MAX_VOLUME:
            vol = v
            continue
        keep.append(s)
    return " ".join(keep), vol


def load(root: Path = Path(".")) -> list[dict]:
    """The bibliography, or an error — never an empty list.

    It used to return `[]` for a missing file, and that is the project's own
    failure mode aimed at an apparatus store: "no such authority" and "you are
    not standing in the repo" become the same answer, and the search reports a
    confident nothing. The store is committed and required, so its absence is a
    broken tree, not a legitimate state.
    """
    p = root / "edition/authorities.json"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} — the bibliography is committed and required; "
            "a missing one means the wrong root, not an empty list"
        )
    return json.loads(p.read_text(encoding="utf-8"))["authorities"]


def _volume(v) -> int | None:
    """`II`, `ii`, `2` -> 2. The print sets roman; a caller may type either.

    Returns None for anything unparseable rather than raising, since an
    unparseable volume should widen the search, not abort it.
    """
    if v is None:
        return None
    s = str(v).strip().lower().rstrip(".")
    if s.isdigit():
        return int(s)
    return _ROMAN.get(s)


def _siglum(c: dict) -> str:
    """A `cited_as` record as one readable string — `Dall, I`, `Hough, Lamp`.

    Display only. The comma before the volume is not reliable in the print
    (docs/apparatus.md), which is why the store keeps the three parts separate; this
    reassembles them in one fixed style rather than reproducing any page.
    """
    bits = [c.get("name") or ""]
    if c.get("volume"):
        bits.append(str(c["volume"]))
    if c.get("short_title"):
        bits.append(str(c["short_title"]))
    return ", ".join(b for b in bits if b)


def _copy(w: dict) -> str:
    """Which located-copy fields this record carries. See docs/apparatus.md: `#llm` on
    every one of them, so this says a match was *proposed*, not ratified."""
    have = [k for k in ("doi", "url") if w.get(k)]
    return "+".join(have) if have else "-"


def _row(w: dict, matched: str | None = None, cited: str | None = None) -> dict:
    """One compact result record. The key set is fixed across every row and every
    mode, because TOON's tabular collapse degrades silently on a ragged list."""
    return {
        "key": w["key"],
        "matched": matched,
        "cited_as": cited if cited is not None else (
            " | ".join(_siglum(c) for c in w["cited_as"]) or None),
        "author": w.get("author"),
        "year": w.get("year"),
        "title": (w.get("title") or "")[:70] or None,
        "lang": w.get("lang"),
        "in": w.get("in"),
        "folio": w.get("folio"),
        "copy": _copy(w),
    }


def _hit(w: dict, query: str, q: set[str], volume: int | None):
    """Strongest tier `w` matches `query` at, with the siglum that caught it.

    Returns (tier, cited_as_display) or None. `volume`, when given, excludes on
    **contradiction, not on absence**: a body citation writing a volume names one
    of the per-volume entries a multi-volume siglum splits into, so a work every
    one of whose sigla carries a different volume is a different work and drops
    out at every tier — otherwise `Dall, I` returns `Dall, II` one rank down,
    which looks like a candidate and is not. A work with no siglum at all, or one
    whose siglum records no volume, is not contradicted and stays in.
    """
    if query.strip().lower() == w["key"].lower():
        return "key", None

    if volume is not None and w["cited_as"] and all(
            _volume(c.get("volume")) not in (None, volume) for c in w["cited_as"]):
        return None

    for c in w["cited_as"]:
        if volume is not None and _volume(c.get("volume")) != volume:
            continue
        # Name, short title, or the whole reassembled siglum — the last so that
        # `Hough, Lamp` matches as typed, without the caller having to know
        # which of the three fields each half of it lives in.
        if q and (q == _norm_words(c.get("name") or "")
                  or q == _norm_words(c.get("short_title") or "")
                  or q == _norm_words(_siglum(c))):
            return "siglum", _siglum(c)

    if q and q <= _norm_words(w.get("author") or ""):
        return "author", None
    for f in ("title", "title_en"):
        t = _norm_words(w.get(f) or "")
        if q and t and q <= t:
            return "title", None

    needle = unicodedata.normalize("NFD", query).casefold()
    for p in w.get("printed", []):
        if needle and needle in unicodedata.normalize("NFD", p.get("text", "")).casefold():
            return "printed", None
    return None


def search(works: list[dict], query: str, volume=None,
           unlocated: bool = False) -> list[dict]:
    """Every work matching `query`, strongest tier first. Never collapses to one.

    An empty query lists the whole store — the same rows, unranked, which is what
    makes `--unlocated` a worklist rather than a search.
    """
    vol = _volume(volume)
    q = _norm_words(query or "")
    out = []
    for w in works:
        if unlocated and _copy(w) != "-":
            continue
        if not (query or "").strip():
            out.append(_row(w))
            continue
        h = _hit(w, query, q, vol)
        if h:
            out.append(_row(w, matched=h[0], cited=h[1] if h[1] else _row(w)["cited_as"]))
    if (query or "").strip():
        out.sort(key=lambda r: (TIERS.index(r["matched"]), r["key"]))
    return out


def siglum_forms(cited_as: list[dict]) -> list[str]:
    """Every spelling of one work's printed siglum, longest first.

    **The comma is not information and the book proves it twice.** `Maydell I,
    p. 331.` and `Maydell, I, pp. 627-680.` are the same siglum in the same
    apparatus, which is the fact `parse_citation` was built around; so a volume
    yields both spellings and the alias table carries both. A short title is set
    with the comma throughout the corpus's footnotes and yields the one.

    A siglum that is only a surname yields nothing. It is already the entry's
    alias, and it is the ambiguous case the citation rule exists for —
    `person:nelson` claims `Nelson` too, and no spelling of a bare name can tell
    the man from the book.
    """
    out: list[str] = []
    for c in cited_as:
        name, vol, title = c.get("name"), c.get("volume"), c.get("short_title")
        if not name:
            continue
        if vol:
            out += [f"{name}, {vol}", f"{name} {vol}"]
        if title:
            out.append(f"{name}, {title}")
    return sorted(dict.fromkeys(out), key=len, reverse=True)


def siglum_name(cited_as: list[dict]) -> str:
    """The printed siglum as one name — `Maydell, I, II`, `Boas, Central Eskimo`.

    What `Authorities Quoted` itself sets in its `[Cited, …]` line, which is
    where a two-volume work becomes one name and not two: the printer wrote
    `[Cited, MAYDELL, I, II.]`, and a work is one work however many volumes it
    was bound in. Empty where the list records no siglum.
    """
    if not cited_as:
        return ""
    name = cited_as[0].get("name") or ""
    parts = [c.get("volume") or c.get("short_title") or "" for c in cited_as
             if (c.get("name") or "") == name]
    return ", ".join([name, *[p for p in parts if p]])


def sigla(works: list[dict], name: str | None = None) -> list[dict]:
    """The resolution table: one row per `cited_as` entry, not per work.

    52 rows from 34 printed sigla, because a siglum printed over several volumes
    splits into one entry per volume. This is the table an annotation pass wants
    in front of it — the ambiguity is visible in it rather than discovered one
    lookup at a time.

    Not to be confused with `authority_names`' 47, which this docstring once
    was: that is every name Bogoras cites a work under, the 34 carrying a
    printed siglum plus 13 cited without one.
    """
    q = _norm_words(name or "")
    out = []
    for w in works:
        for c in w["cited_as"]:
            if q and q != _norm_words(c.get("name") or ""):
                continue
            out.append({
                "name": c.get("name"),
                "volume": c.get("volume"),
                "short_title": c.get("short_title"),
                "key": w["key"],
                "author": w.get("author"),
                "year": w.get("year"),
                "title": (w.get("title") or "")[:60] or None,
            })
    out.sort(key=lambda r: ((r["name"] or "").lower(),
                            _volume(r["volume"]) or 0,
                            r["short_title"] or ""))
    return out


def record(works: list[dict], key: str) -> dict:
    """One work in full, `printed` blocks included — `printed` is the record and
    the parsed fields lose to it on disagreement."""
    for w in works:
        if w["key"] == key:
            return w
    raise KeyError(f"no authority with key {key!r}; "
                   f"try `harness find authority {key}` to search")
