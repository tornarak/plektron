"""Where each page has got to, across every store at once.

The answer was piecemeal and each piece was honest about its own store and blind
to the rest: `ocr pages --show-store` reports the two OCR stores and the view over
them, `zones check` the two zone stores, `views check` the derived trees, and
nothing at all joined `review/`'s two authored files or `tei/` to any of it. So
"which pages are ready to collate" and "which are half-way through the reading
loop" were questions with no command behind them, answerable only by listing four
directories and intersecting them by eye.

**The ladder is the pipeline, and it is a ladder rather than a set because each
rung's input is the one below it**:

    scanned    pdftoppm over pdfs/, then the greyscale pass — scans/
    zoned-mz   the segmenter ran                            — mz/zones/
    zoned-gt   a human has been through the zones           — gt/zones/
    ocr-mz     baselines + CATMuS ran                       — mz/ocr/
    proposed   a reading proposal exists                    — review/PP-NNN/
    decided    a human adjudicated it                       — review/PP-NNN/
    ocr-gt     `restore` wrote the adjudicated text         — gt/ocr/
    collated   the page has TEI                             — tei/

**`stage` is the furthest rung reached and is therefore a summary, so it ships
beside `skipped`** — the rungs below it that are *not* satisfied. A summary that
can hide the anomaly it is summarising is this project's standing failure shape,
and here the anomaly is real and attested: `2-030` reached `gt/ocr/` through the
eScriptorium route before the review loop existed, so it is `ocr-gt` with no
proposal and no decision, and for a long time nothing could see that. A page
whose `skipped` is non-empty took a route the pipeline no longer offers, which is
worth knowing before trusting anything downstream of it.

**Nothing here reads a file's contents.** Every column is the presence of a path,
which is what makes the survey affordable over 832 pages — and is also the reason
it cannot answer "is this page's zoning any good": that is `zones check`'s
question and it costs a raster. This reports where a page is, never how well.
"""
from __future__ import annotations

from pathlib import Path

from .context import norm_ref
from .paths import decisions_path, proposal_path

# In rung order, lowest first. The order is the module's whole content: `stage`
# is `max` over it and `skipped` is everything below the max that is absent, so
# both derive from this tuple and cannot disagree with each other.
STAGES = ("scanned", "zoned-mz", "zoned-gt", "ocr-mz",
          "proposed", "decided", "ocr-gt", "collated")

# What `zones` reports when a human ruled the page is not a text page at all.
# It satisfies the `zoned-gt` rung: that rung asks whether a human has been
# through the page, and "this is a plate" is a judgement, not the absence of one.
EXEMPT = "exempt"


def page_state(ref: str, root: Path = Path("."),
               splits: dict[str, str] | None = None) -> dict:
    """One page's row. `splits` is passed in by `survey` to read the lists once."""
    from .zones import MZDIR as ZONES_MZ
    from .zones import ZONEDIR as ZONES_GT
    from .zones import alto_for as zone_alto
    from .zones import load_splits, scan_for

    ref = norm_ref(ref)
    if splits is None:
        splits = load_splits(root)

    scan = scan_for(ref, root).exists()
    exempt = splits.get(ref) == EXEMPT
    zones = (EXEMPT if exempt else
             "gt" if zone_alto(ref, root, ZONES_GT).exists() else
             "mz" if zone_alto(ref, root, ZONES_MZ).exists() else "")
    stem = f"chukchi-{ref}.xml"
    ocr_gt = (root / "gt" / "ocr" / stem).exists()
    ocr_mz = (root / "mz" / "ocr" / stem).exists()
    row = {
        "ref": ref,
        "scan": scan,
        "zones": zones,
        # `gt` wins the report the way the view resolves it, but both are kept in
        # the ladder below: a page can hold a prediction and a human file at once,
        # and the rung is about what has *happened*, not about what is read.
        "ocr": "gt" if ocr_gt else "mz" if ocr_mz else "",
        "fig": (root / "gt" / "fig" / stem).exists(),
        "proposal": proposal_path(ref, root).exists(),
        "decision": decisions_path(ref, root).exists(),
        "tei": (root / "tei" / stem).exists(),
    }
    reached = {
        "scanned": scan,
        "zoned-mz": zone_alto(ref, root, ZONES_MZ).exists(),
        "zoned-gt": zones in ("gt", EXEMPT),
        "ocr-mz": ocr_mz,
        "proposed": row["proposal"],
        "decided": row["decision"],
        "ocr-gt": ocr_gt,
        "collated": row["tei"],
    }
    top = max((i for i, s in enumerate(STAGES) if reached[s]), default=-1)
    row["stage"] = STAGES[top] if top >= 0 else "absent"
    row["skipped"] = ",".join(s for s in STAGES[:top] if not reached[s])
    return row


def survey(refs: list[str], root: Path = Path(".")) -> list[dict]:
    """`page_state` over many refs, reading the split lists once."""
    from .zones import load_splits
    splits = load_splits(root)
    return [page_state(r, root, splits) for r in refs]


def tally(rows: list[dict]) -> list[dict]:
    """How many pages sit at each rung, in ladder order — a shape of the corpus.

    Rungs with no pages are still listed. A stage that reads zero because nothing
    has reached it and one that reads zero because everything has passed it are
    different facts, and omitting the row makes them look the same.
    """
    counts = dict.fromkeys(("absent", *STAGES), 0)
    skipped = 0
    for r in rows:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1
        skipped += 1 if r["skipped"] else 0
    out = [{"stage": s, "pages": n} for s, n in counts.items()]
    out.append({"stage": "(any skipped rung)", "pages": skipped})
    return out
