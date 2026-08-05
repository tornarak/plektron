"""Human line corrections, and the line half of the ink question.

Two ink checks run over these pages and they ask **different questions**:

- `zones check --ink` asks *is this ink inside any zone?* Ink outside every
  region is a defect in the zoning — a column the segmenter missed, a marginal
  note nobody boxed.
- `ocr gaps` asks *is this in-zone ink inside any line?* Ink a zone covers but no
  `TextLine` does is a dropped line — the fault that is invisible to every
  text-level check, because the text that is there is correct and so nothing
  disagrees with anything.

They were sharing one exemption file, and that made a ruling about one question
silently answer the other. A band marked "scanner smudge" during zoning — a
statement about what the *zoning* need not cover — also stopped the line check
from ever reporting that strip of paper again. The two are now one file each,
written by their own editor, and **overlaid rather than merged**: each band is
settled by the layer whose question it belongs to, and each editor shows the
other layer so a human can see that the neighbouring check has already spoken.

The boundary between them is a mutual audit. A band this layer finds *outside*
every zone is not this layer's business, and it is either a zone-check miss or a
standing zone-level ruling — which is why `ocr edit` reads both files and refuses
to record a correction out there, naming `zones edit` instead.

**The mechanism is shared, the meaning is not.** A ruling is band-scoped and
carries a required reason in both layers, so that core lives here and `zones.py`
calls it for its own directory. What differs is only which question the file
answers, which is what the `_about` blurb in each file says.
"""
from __future__ import annotations

import json
from pathlib import Path

from .context import norm_ref, parse_ref

INK_EXEMPT_JSON = "_ink_exempt.json"

LINE_EXEMPT_ABOUT = (
    "Bands of ink **inside a zone** that a human has ruled are not a dropped "
    "line — a printed rule, a footnote separator, a smudge the zoning covers. "
    "Each carries the reason it was ruled so, and each is scoped to its own "
    "band: exempting a whole page would hide the next dropped line on it. A "
    "matched band still reports, flagged `exempted` and carrying its note. This "
    "is the *line* layer; ink outside every zone is the zoning's question and "
    "lives in gt/zones/_ink_exempt.json. Keyed PP-NNN.")


def lines_dir(root: Path = Path(".")) -> Path:
    """The line-correction store. Authored and tracked, like `gt/zones/`."""
    return Path(root) / "gt" / "lines"


# --------------------------------------------------------------- the shared core

def load_exemptions(store: Path) -> dict[str, list[dict]]:
    """Every ruling in one layer's file, keyed by ref. `{}` when absent."""
    p = Path(store) / INK_EXEMPT_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A corrupt file reads as no rulings, which makes every band on every
        # ruled page report again. That is the safe direction for a detector
        # whose failure mode is silence — over-reporting is noise, under-
        # reporting is a dropped line nobody hears about.
        return {}
    return {k: list(v) for k, v in data.items() if not k.startswith("_")}


def clean_regions(ref: str, regions: list[dict] | None) -> list[dict]:
    """Validate and normalise one page's rulings.

    **A reason is required and is the point of the file.** Every suppression is a
    claim that something on the paper is not what the check took it for, and
    "the tool complained and I made it stop" is not a record of anything. A year
    from now the note is the only thing that distinguishes a ruled artifact from
    a hidden mistake.
    """
    clean = []
    for r in regions or []:
        note = (r.get("note") or "").strip()
        if not note:
            raise ValueError(
                f"ink exemption for {ref} at y={r.get('y0')} has no reason — the "
                "reason is the record; without it the entry is indistinguishable "
                "from a hidden mistake")
        y0, y1 = sorted((int(r["y0"]), int(r["y1"])))
        clean.append({"y0": y0, "y1": y1, "note": note})
    clean.sort(key=lambda r: r["y0"])
    return clean


def write_exemptions(store: Path, data: dict[str, list[dict]],
                     about: str) -> Path:
    """One layer's file, refs in page order, carrying what it is for."""
    p = Path(store) / INK_EXEMPT_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    doc: dict = {"_about": about}
    doc.update({k: data[k] for k in sorted(data, key=parse_ref)})
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    return p


def ink_excuse(band: dict, regions: list[dict]) -> dict | None:
    """The recorded region covering this band, if any.

    Matched on the band's **midpoint**, not on its edges: the band is re-measured
    from the raster on every run and its exact extent moves by a pixel or two with
    any change to a neighbouring zone, so an edge test would silently stop matching.
    The midpoint is stable, and regions are stored tight enough that it cannot
    wander into a neighbouring finding.
    """
    mid = band["vpos"] + band["height"] / 2
    for r in regions:
        if r["y0"] <= mid <= r["y1"]:
            return r
    return None


# --------------------------------------------------------------- the line layer

def load_ink_exempt(root: Path = Path(".")) -> dict[str, list[dict]]:
    """Line-level rulings: bands inside a zone that are not dropped lines."""
    return load_exemptions(lines_dir(root))


def set_ink_exempt(ref: str, regions: list[dict],
                   root: Path = Path(".")) -> dict:
    """Record bands inside a zone that a human has ruled are not a line.

    Scoped to a band, never to the page: the next dropped line on the same leaf
    must still report. The zone layer's equivalent is `zones.set_ink_exempt`, and
    the two files are never merged — see this module's docstring for why.
    """
    ref = norm_ref(ref)
    clean = clean_regions(ref, regions)
    data = load_ink_exempt(root)
    if clean:
        data[ref] = clean
    else:
        data.pop(ref, None)
    write_exemptions(lines_dir(root), data, LINE_EXEMPT_ABOUT)
    return {"ref": ref, "ink_exempt": data.get(ref, [])}
