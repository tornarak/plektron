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

    scanned    harness scans extract over pdfs/ — scans/
    zoned-mz   the segmenter ran                            — mz/zones/
    zoned-gt   a human has been through the zones           — gt/zones/
    ocr-mz     baselines + CATMuS ran                       — mz/ocr/
    proposed   a reading proposal exists                    — review/PP-NNN/
    decided    a human adjudicated it                       — review/PP-NNN/
    ocr-gt     `restore` wrote the adjudicated text         — gt/ocr/
    generated  the rules built a first-draft TEI            — mz/tei/
    collated   a reader signed the page                     — tei/

**And one terminus off the side of it**, `zoned-exempt`: a leaf a human ruled a
plate, blank, cover, map or apparatus is *finished*, not pending. It holds no
zone file — `exempt => no zones`, the ruling is the record — and it will never
climb another rung, there being no text to recognize, propose or collate. It
read as `zoned-gt` until the stage existed, which put 115 leaves in the column a
reader scans for work still to do.

**`stage` is the furthest rung reached and is therefore a summary, so it ships
beside `skipped`** — the rungs below it that are *not* satisfied. A summary that
can hide the anomaly it is summarising is this project's standing failure shape,
and here the anomaly is real and attested: `2-030` reached `gt/ocr/` through the
eScriptorium route before the review loop existed, so it is `ocr-gt` with no
proposal and no decision, and for a long time nothing could see that. A page
whose `skipped` is non-empty took a route the pipeline no longer offers, which is
worth knowing before trusting anything downstream of it.

**A rung a route legitimately omits is not a skip**, and getting that wrong costs
the column its whole value. `zoned-mz` first counted against every exempt page,
which put 83 plates in the report and left the one page that really did reach
human zoning with no prediction behind it (`1-359`) indistinguishable among them
— 84 rows saying nothing where 1 said something.

**Nothing here reads a file's contents.** Every column is the presence of a path,
which is what makes the survey affordable over 832 pages — and is also the reason
it cannot answer "is this page's zoning any good": that is `zones check`'s
question and it costs a raster. This reports where a page is, never how well.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .paths import decisions_path, proposal_path
from .refs import norm_ref

# In rung order, lowest first. The order is the module's whole content: `stage`
# is `max` over it and `skipped` is everything below the max that is absent, so
# both derive from this tuple and cannot disagree with each other.
STAGES = ("scanned", "zoned-mz", "zoned-gt", "ocr-mz",
          "proposed", "decided", "ocr-gt", "generated", "collated")

#: **Where a ruled leaf stops, and it is a terminus rather than a rung.** A plate
#: or a blank is finished the moment somebody rules it: there is no text to
#: recognize, nothing to propose, nothing to collate, and it will never climb
#: another step. Reported as `zoned-gt` it read as a page *waiting* for OCR, which
#: put 115 leaves in the same column as work that is genuinely pending — the
#: summary hiding the distinction it exists to draw.
#:
#: Not a member of `STAGES`, deliberately, because that tuple is the ladder and
#: `skipped` is "everything below the furthest rung that is absent". A rung no
#: text page can satisfy would be a skipped rung on all 717 of them, which is the
#: same defect one column over. `tally` lists it beside the ladder instead.
EXEMPT_STAGE = "zoned-exempt"

# What `zones` reports when a human ruled the page is not a text page at all: the
# **kind they ruled** — `plate`, `blank`, `cover`, `map`, `apparatus` — and not a
# flat `exempt`. It still satisfies the rungs below, since "this is a plate" is a
# judgement and not the absence of one; what it does *not* do is sit on `zoned-gt`
# as though waiting for OCR. `EXEMPT_STAGE` is where such a page is reported.
#
# Naming the kind here is most of what `--refs` is for. A worklist that said
# `exempt` 115 times could only be crossed off by opening each page; one that says
# `blank` and `map` is a list somebody can act on, which is the whole complaint the
# split vocabulary answers.


def page_state(ref: str, root: Path = Path("."),
               splits: dict[str, str] | None = None) -> dict:
    """One page's row. `splits` is passed in by `survey` to read the lists once."""
    from .zones import MZDIR as ZONES_MZ
    from .zones import ZONEDIR as ZONES_GT
    from .zones import alto_for as zone_alto
    from .zones import is_exempt, load_splits, scan_for

    ref = norm_ref(ref)
    if splits is None:
        splits = load_splits(root)

    scan = scan_for(ref, root).exists()
    exempt = is_exempt(ref, root, splits)
    zones = (splits[ref] if exempt else
             "gt" if zone_alto(ref, root, ZONES_GT).exists() else
             "mz" if zone_alto(ref, root, ZONES_MZ).exists() else "")
    stem = f"chukchi-{ref}.xml"
    ocr_gt = (root / "gt" / "ocr" / stem).exists()
    ocr_mz = (root / "mz" / "ocr" / stem).exists()
    tei_mz = (root / "mz" / "tei" / stem).exists()
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
        # Both TEI stores, like `zones` and `ocr` above and for the same reason:
        # they are two different claims about the page — what the rules produced and
        # what a reader signed — and a single column would have to pick one.
        "tei_mz": tei_mz,
        "tei": (root / "tei" / stem).exists(),
    }
    reached = {
        "scanned": scan,
        # **An exempt page satisfies this rung without a prediction behind it.**
        # `zones predict` is not part of how a plate gets ruled a plate — a human
        # looks and says so — and counting the absence as a skipped rung buried
        # the column's real content: 83 of this corpus's first 84 `zoned-mz`
        # skips were exempt pages, and the one page that actually reached human
        # zoning with no prediction behind it (`1-359`) sat invisible among them.
        # A summary rung that fires on the ordinary case is the same defect as a
        # detector that fires on ordinary English.
        "zoned-mz": exempt or zone_alto(ref, root, ZONES_MZ).exists(),
        # `exempt` and not `zones == "gt"`, because `zones` now carries the kind:
        # asking the boolean keeps this rung independent of the vocabulary, where
        # a membership test against the kind list would have to grow with it.
        "zoned-gt": zones == "gt" or exempt,
        "ocr-mz": ocr_mz,
        "proposed": row["proposal"],
        "decided": row["decision"],
        "ocr-gt": ocr_gt,
        # **Generation is a rung and not a detail**, because collation is now gated
        # on it: `tei queue` refuses a page with no generated draft, so a page that
        # has ground truth and no `mz/tei/` is genuinely not ready and the ladder
        # should say which step is missing. It is also the only rung a single
        # command fills for the whole corpus, which makes a non-empty count here a
        # to-do rather than a finding.
        "generated": tei_mz,
        "collated": row["tei"],
    }
    top = max((i for i, s in enumerate(STAGES) if reached[s]), default=-1)
    row["stage"] = STAGES[top] if top >= 0 else "absent"
    row["skipped"] = ",".join(s for s in STAGES[:top] if not reached[s])
    # A ruled leaf leaves the ladder here. `skipped` is cleared with it: the rungs
    # above are not steps this page failed to take, they are steps that do not
    # apply to it, and a page reported as having skipped seven of them would read
    # as damaged rather than done.
    if exempt:
        row["stage"], row["skipped"] = EXEMPT_STAGE, ""
    return row


def survey(refs: list[str], root: Path = Path("."),
           tick: Callable | None = None) -> list[dict]:
    """`page_state` over many refs, reading the split lists once."""
    from .parallel import ptrack
    from .zones import load_splits
    splits = load_splits(root)
    return [page_state(r, root, splits) for r in ptrack(refs, tick)]


def tally(rows: list[dict]) -> list[dict]:
    """How many pages sit at each rung, in ladder order — a shape of the corpus.

    Rungs with no pages are still listed. A stage that reads zero because nothing
    has reached it and one that reads zero because everything has passed it are
    different facts, and omitting the row makes them look the same.
    """
    counts = dict.fromkeys(("absent", *STAGES, EXEMPT_STAGE), 0)
    skipped = 0
    for r in rows:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1
        skipped += 1 if r["skipped"] else 0
    out = [{"stage": s, "pages": n} for s, n in counts.items()]
    out.append({"stage": "(any skipped rung)", "pages": skipped})
    return out
