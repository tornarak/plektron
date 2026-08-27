"""The alphabet key, as a chart: `edition/alphabet.json` joined to what this
edition has since worked out about it.

Scan 1-030 is the p. 10 key, and it is the page a reader turns to on meeting
`taˊn˙ñɪtan`. The printed page answers badly — fifty lines of "as in English",
in no order, with the structure of the system nowhere on it. Everything needed
to answer well is already in the repository, in four places that have never
been in one room:

    edition/alphabet.json   the two printed keys transcribed, and Mythology's own
                         arrangement of the sorts into grids
    ipa.RULES            what each sort is worth, on Bogoras's own account,
                         with its grade and its hedge
    ipa.MODERN           what a current description calls the same sound
    lookup.index         how often the sort actually occurs in the keyed corpus

**This module only joins them.** It settles nothing: where the four disagree
the chart shows all four, which is the whole reason `MODERN` is a second table
rather than a column of the first. A gap stays a gap — four sorts have a gloss
and no IPA value, and they appear on the chart as sorts with no IPA value.

**The store and `keying_spec.md` state the codepoints twice, on purpose.** The
spec owns the inventory (CLAUDE.md's precedence table) and the store has to be
machine-readable; rather than merge them, `check` compares them and fails on a
divergence — the same idiom as a run's three statements of one span, and as
`test_cli_surface` against `VERBS.md`.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

STORE = "edition/alphabet.json"
SPEC = "keying_spec.md"


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def load(root: Path = Path(".")) -> dict:
    """The store, or an empty one. A store, so absence is emptiness."""
    p = Path(root) / STORE
    if not p.exists():
        return {"keys": [], "grids": {}, "sorts": [], "rules": [], "notes": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _attestations(root: Path) -> dict[str, int]:
    """How many attested forms carry each sort, by longest match.

    Counted over forms rather than occurrences, and over the *keyed* corpus
    only: this is "how much of the book does this sort unlock", which is a
    question about the sorts a reader will actually meet. A sort with no count
    is not thereby absent from the book — only from what has been keyed.
    """
    from . import lookup
    from .marks import MarksConfigError

    # `{}` is a real answer — a clone with nothing keyed yet — and it used to be
    # the answer to a corpus that would not read as well, which surfaces in the
    # chart as confident zeros against every sort. Narrowed to the config
    # absence, which is the case worth absorbing; a broken corpus travels.
    try:
        idx = lookup.index(Path(root))
    except MarksConfigError:
        return {}
    forms = {d["form"] for v in idx.get("buckets", {}).values()
             for d in v.get("forms", {}).values()}
    return {"": len(forms)} | _count(forms)


def _count(forms: set[str]) -> dict[str, int]:
    from . import ipa

    seqs = sorted((_nfd(s) for s, _, _, _ in ipa.RULES), key=len, reverse=True)
    out: dict[str, int] = {}
    for f in forms:
        w = _nfd(f).lower()
        seen = set()
        i = 0
        while i < len(w):
            for s in seqs:
                if w.startswith(s, i):
                    seen.add(s)
                    i += len(s)
                    break
            else:
                i += 1
        for s in seen:
            out[s] = out.get(s, 0) + 1
    return out


def chart(root: Path = Path(".")) -> dict:
    """The whole page's data: the grids, and one record per sort.

    Each record carries every witness side by side and marks where they part —
    `ipa` is Bogoras's own account, `modern` is a current description's, and
    `hedge` is where a source offered two values and this edition emits the
    first. A sort the rule table has no value for comes back with `ipa: ""` and
    `why` naming the gloss it has instead of one.
    """
    from . import ipa as I

    store = load(root)
    rules = {_nfd(s): (out, grade, alt) for s, out, grade, alt in I.RULES}
    modern = {_nfd(k): v for k, v in I.MODERN.items()}
    counts = _attestations(Path(root))

    rows = []
    for i, s in enumerate(store.get("sorts", []), 1):
        key = _nfd(s["sort"])
        out, grade, alt = rules.get(key, ("", "", ""))
        phoneme, note = modern.get(key, ("", ""))
        rows.append({
            "sort": s["sort"],
            # Positional and not the sort itself: a fragment holding a combining
            # sequence is legal and unusable, and `ʟ̣` and `ʟ` would differ by an
            # invisible character in a URL somebody has to be able to paste.
            "anchor": f"sort-{i}",
            "codepoint": s.get("codepoint", ""),
            "glosses": s.get("glosses", []),
            "note": s.get("note", ""),
            "ipa": out,
            "grade": grade,
            "hedge": alt,
            "modern": phoneme,
            "modern_note": note,
            "forms": counts.get(key, 0),
            # Said rather than left to be inferred from an empty `ipa`: the
            # difference between "no value" and "value not yet worked out" is
            # the difference this project exists to keep.
            "why": ("" if out else
                    "a gloss and no symbol; turning one into the other is a "
                    "judgement rather than a lookup"),
        })
    return {
        "keys": store.get("keys", []),
        "grids": store.get("grids", {}),
        "rules": store.get("rules", []),
        "notes": store.get("notes", []),
        "sorts": rows,
        "by_sort": {r["sort"]: r for r in rows},
        "attested_forms": counts.get("", 0),
    }


#: The `keying_spec.md` sections whose tables are keyed by the sort itself.
#: **§2.1 is deliberately not among them**: its rows are keyed by a description
#: of the mark ("word stress, postposed to the stressed vowel") rather than by
#: the glyph, so there is nothing to join on. Nor is §3, whose table looks
#: identical and means the opposite — a forbidden lookalike beside the codepoint
#: that should have been keyed instead. Sniffing rows for something
#: codepoint-shaped picks that up and silently compares the wrong column.
SPEC_SECTIONS = ("### 2.2 ", "### 2.3 ")

#: The header a codepoint column carries in each: §2.2 calls it NFD because its
#: sorts are sequences, §2.3 Codepoint because its are atomic.
_CODE_HEADERS = ("nfd", "codepoint")
_SORT_HEADERS = ("sort", "glyph")


def _cells(line: str) -> list[str]:
    return [_clean(c) for c in line.strip().strip("|").split("|")]


def spec_codepoints(root: Path = Path(".")) -> dict[str, str]:
    """`{sort: codepoint}` as `keying_spec.md` §2.2-2.3 tabulate them.

    Parsed rather than restated, so the comparison is against the document a
    keyer actually reads, and **header-driven** rather than shape-driven: the
    columns are found by their names, so a table that gains a column still
    reads and a table that means something else is not mistaken for this one.
    """
    p = Path(root) / SPEC
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for head in SPEC_SECTIONS:
        start = text.find(head)
        if start < 0:
            continue
        nxt = text.find("\n### ", start + 1)
        body = text[start:nxt if nxt > 0 else len(text)]
        cols: tuple[int, int] | None = None
        for line in body.splitlines():
            if not line.startswith("|"):
                cols = None
                continue
            cells = _cells(line)
            if cols is None:
                lower = [c.lower() for c in cells]
                si = next((i for i, c in enumerate(lower)
                           if c in _SORT_HEADERS), None)
                ci = next((i for i, c in enumerate(lower)
                           if c in _CODE_HEADERS), None)
                if si is not None and ci is not None:
                    cols = (si, ci)
                continue
            if set("".join(cells)) <= set("-: "):        # the separator row
                continue
            si, ci = cols
            if max(si, ci) < len(cells) and cells[si] and cells[ci]:
                out[_nfd(cells[si])] = cells[ci]
    return out


def _clean(s: str) -> str:
    """Markdown emphasis, code ticks and the dotted circle off; space folded."""
    s = s.replace("**", "").replace("*", "").replace("`", "").replace("◌", "")
    return " ".join(s.split())


def check(root: Path = Path(".")) -> dict:
    """The gate: the store against `ipa.RULES` and against `keying_spec.md`.

    Three things fail. A sort the store marks as having an IPA value that the
    rule table has no row for, or the reverse — the flag is the store's claim
    about the table and a stale one is worse than none. A grid cell naming a
    sort the store does not list, which would draw a chart with a hole in it. A
    codepoint the spec and the store disagree on, which is the two-witness
    check the duplication exists for.
    """
    from . import ipa as I

    store = load(root)
    errors: list[dict] = []
    sorts = {_nfd(s["sort"]): s for s in store.get("sorts", [])}
    rules = {_nfd(s) for s, _, _, _ in I.RULES}

    for key, s in sorts.items():
        if bool(s.get("ipa")) != (key in rules):
            errors.append({
                "sort": s["sort"], "rule": "ipa-flag-stale",
                "detail": f"store says ipa={bool(s.get('ipa'))}, "
                          f"ipa.RULES {'has' if key in rules else 'has no'} row"})
    for key in sorted(rules - set(sorts)):
        errors.append({"sort": key, "rule": "sort-missing",
                       "detail": "ipa.RULES has a row and the store no entry"})

    for name, grid in (store.get("grids") or {}).items():
        for row in grid.get("rows", []):
            for cell in row.get("cells", []):
                if cell and _nfd(cell) not in sorts:
                    errors.append({"sort": cell, "rule": "grid-cell-unknown",
                                   "detail": f"in the {name} grid"})

    spec = spec_codepoints(root)
    checked = 0
    for key, s in sorts.items():
        want = spec.get(key)
        if want is None:
            continue
        checked += 1
        if _norm_code(want) != _norm_code(s.get("codepoint", "")):
            errors.append({
                "sort": s["sort"], "rule": "codepoint-disagreement",
                "detail": f"keying_spec.md says {want!r}, "
                          f"the store says {s.get('codepoint', '')!r}"})

    return {"sorts": len(sorts), "spec_checked": checked, "errors": errors}


def _norm_code(s: str) -> str:
    """`a + U+0308` and `a+U+0308` are one codepoint spelling."""
    return re.sub(r"\s+", "", s).upper()
