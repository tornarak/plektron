"""Find a ratified native form, and name it without retyping its glyphs.

Two halves of one mechanism, and the second is why the first is safe to have.

**The lookup** searches the Tier-1 forms a human has adjudicated in `gt/ocr/`,
returning each with its pages and the lines it was printed on, so a form's sense is
readable from where it occurs — `Kuluˊči` alone is a string, "south of Kuluˊči Bay"
is a place.

**The handle** is how a reader names one without keying it: `{Kulu'c^i}` in a
proposal, expanded by `proposal set` on write. `text` then holds the real form and
`as_typed` holds the line as the reader wrote it, so the review UI can show the
adjudicator a claim about a corpus match rather than a reading — which is the whole
point, because `CLAUDE.md` says a comparison whose witnesses may be one witness must
say so. A reader that quietly copies a corpus spelling stops being an independent
witness and the adjudicator's confirmation becomes a confirmation of the corpus.

**Why the ambiguity refusal is not a nicety.** `data/marks_exempt.json` records that
the book sets `Čeˊwɪn` (1-042) and `Čeˊwin` (1-052) — one word, two settings — and
that 1-042's reader flagged the disagreement instead of harmonizing to the older
page's ground truth. A lookup that answers with one spelling is a machine for
erasing that. So a bucket holding more than one form yields no handle at all, and an
**exemption does not restore it**: ruling that the book sets a word two ways is a
statement that the ambiguity is real, which is the strongest possible reason to
refuse to pick a side.

**The floor.** `--min-pages` counts pages *per bucket*, over all its forms together.
Per-form would be worse than useless: `Čeˊwɪn` and `Čeˊwin` have one page each, so a
per-form floor at the default deletes the corpus's only genuine ambiguity from the
lookup instead of refusing it. A floor may withhold a handle from a form the corpus
barely attests; it may never hide a conflict.

**`gt/ocr/` only.** The lookup's entire authority is that a human adjudicated these
marks at the raster. A list built from `mz/` would be garbled forms offered to be
copied verbatim — the failure this exists to prevent, inverted.
"""
from __future__ import annotations

import re
from pathlib import Path

from .detectors import native_corpus_context
from .marks import fold, handle_key, load_config

# A handle is a key in braces. The character class is `handle_key`'s output
# alphabet — ASCII alphanumerics, the two load-bearing ASCII marks the key passes
# through (U+0027, U+002D), and the markers — so a brace holding anything else was
# never a handle and is reported as the stray brace it is.
HANDLE = re.compile(r"\{([A-Za-z0-9'\-_^.~:)=]+)\}")


def index(root: Path = Path(".")) -> dict:
    """Every attested form, bucketed, keyed, and carrying the lines it occurs on.

    Returns `{"buckets": {bucket: {...}}, "by_key": {key: bucket}, "unkeyable":
    [...]}`. `unkeyable` is named and never silently dropped: a token whose key
    cannot be built is one this instrument cannot offer, and a caller that reports
    "not found" without saying so has converted a gap into a corpus-wide negative.
    """
    contrasts = load_config(root)["contrasts"]
    buckets: dict[str, dict] = {}
    unkeyable: list[dict] = []
    for r in native_corpus_context(root):
        tok = r["token"]
        try:
            key = handle_key(tok)
        except ValueError as e:
            unkeyable.append({"form": tok, "ref": r["ref"], "why": str(e)})
            continue
        b = buckets.setdefault(fold(tok, contrasts),
                               {"forms": {}, "refs": set(), "count": 0})
        f = b["forms"].setdefault(key, {"form": tok, "key": key, "count": 0,
                                        "refs": set(), "lines": []})
        f["count"] += 1
        f["refs"].add(r["ref"])
        f["lines"].append({"ref": r["ref"], "line": r["line"], "text": r["text"]})
        b["refs"].add(r["ref"])
        b["count"] += 1
    by_key = {k: bk for bk, b in buckets.items() for k in b["forms"]}
    return {"buckets": buckets, "by_key": by_key, "unkeyable": unkeyable}


def resolve(key: str, root: Path = Path("."), min_pages: int = 2,
            idx: dict | None = None) -> tuple[str | None, str]:
    """A key to its ratified form, or `(None, why)`.

    Every refusal is a refusal to guess, and each says which one it is so the caller
    can act: an unknown key is a typo or an unattested form, an ambiguous one is the
    book disagreeing with itself, a thin one is a form the corpus barely attests.
    """
    idx = idx if idx is not None else index(root)
    bucket = idx["by_key"].get(key)
    if bucket is None:
        return None, f"no ratified form has the key {key!r}"
    b = idx["buckets"][bucket]
    if len(b["forms"]) > 1:
        spelt = ", ".join(sorted(f["form"] for f in b["forms"].values()))
        return None, (f"{key!r} names one of {len(b['forms'])} spellings the corpus "
                      f"holds for this word ({spelt}) — the book sets it more than "
                      "one way and nothing here may pick for you. Read the raster "
                      "and key what it shows")
    if len(b["refs"]) < min_pages:
        return None, (f"{key!r} is attested on {len(b['refs'])} page(s), below the "
                      f"floor of {min_pages} — one page is a neighbour, not a "
                      "convention. Read the raster")
    return next(iter(b["forms"].values()))["form"], ""


def expand(text: str, root: Path = Path("."), min_pages: int = 2,
           idx: dict | None = None) -> tuple[str, list[str]]:
    """Substitute every handle in a line, or refuse the whole line.

    **Nothing half-expands.** `tei expand` leaves an unresolved handle exactly as it
    is rather than dropping it, so the fault stays where a reader will meet it; the
    same rule one stage earlier means a line with one bad handle is not written at
    all, since a partly-expanded line is a record of neither what was read nor what
    was meant.

    Returns `(expanded, refusals)`. A non-empty `refusals` means nothing was
    written. A stray `{` that is not a handle is its own refusal: the corpus keys
    no brace — 1-359 prints one joining two Russian names and its reader recorded
    it in a note, which is the treatment — so a brace in `text` is either a handle
    this cannot resolve or a character that does not belong there.
    """
    idx = idx if idx is not None else index(root)
    refusals: list[str] = []

    def sub(m: re.Match) -> str:
        form, why = resolve(m.group(1), root, min_pages, idx)
        if form is None:
            refusals.append(why)
            return m.group(0)
        return form

    out = HANDLE.sub(sub, text)
    # Only when nothing else refused: an unresolved handle is left in place by
    # design, so its brace would otherwise raise a second complaint restating the
    # first, and a refusal that says two things says neither clearly.
    if not refusals and ("{" in out or "}" in out):
        refusals.append(
            "a brace survives in the line and is not a handle this can read — "
            "no page keys a brace, so it is either a mistyped handle or a "
            "character that belongs in a note rather than in the reading")
    return out, refusals


def search(queries: list[str], root: Path = Path("."), min_pages: int = 2,
           context: int = 2) -> dict:
    """Forms matching any query, with what a reader needs to judge them.

    Matched against the key, the bucket, the form and the key's bare-ASCII
    reduction, so `kulu`, `kuluci` and `Kulu'c^i` all reach `Kuluˊči`. Substring,
    not prefix: the interesting query is often a stem in the middle of a compound.
    """
    idx = index(root)
    qs = [q.casefold() for q in queries]
    rows, seen = [], set()
    for bucket, b in sorted(idx["buckets"].items()):
        ambiguous = len(b["forms"]) > 1
        pages = len(b["refs"])
        for key, f in sorted(b["forms"].items()):
            bare = "".join(c for c in key if c.isalnum()).casefold()
            hay = (key.casefold(), bucket.casefold(), f["form"].casefold(), bare)
            if not any(q in h for q in qs for h in hay):
                continue
            usable = not ambiguous and pages >= min_pages
            seen.add(bucket)
            rows.append({
                "key": key if usable else "",
                "form": f["form"],
                "count": f["count"],
                "pages": pages,
                "refs": " ".join(sorted(f["refs"])),
                "ambiguous": ambiguous,
                "why": ("" if usable else
                        "the book sets this word more than one way" if ambiguous
                        else f"attested on {pages} page(s), below the floor "
                             f"of {min_pages}"),
            })
    lines = [ln for bucket in sorted(seen)
             for f in idx["buckets"][bucket]["forms"].values()
             for ln in f["lines"][:context]]
    return {
        "queries": " ".join(queries),
        "min_pages": min_pages,
        "forms_indexed": sum(len(b["forms"]) for b in idx["buckets"].values()),
        # **Stated on every run, because an empty result is not a corpus-wide
        # negative.** The selection requires an inventory glyph, so a native token
        # carrying no mark at all — a bare `c`, `s`, `j`, `x`, `h` — is invisible
        # here by construction. "Not found" means not found *by this instrument*.
        "floor": "forms carrying no inventory glyph are invisible to this index; "
                 "an empty result is not evidence the corpus lacks the word",
        "unkeyable": len(idx["unkeyable"]),
        "matches": rows,
        "context": lines,
    }
