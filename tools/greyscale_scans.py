#!/usr/bin/env python3
"""Convert `scans/` from RGB to greyscale in place. Pixels are never changed.

`scans/` is `pdftoppm` output and poppler writes RGB, but the PDFs carry a
**1-bit gray JBIG2 master** for every page of type. So each RGB pixel is a grey
one written three times, and decoding it costs three times what it should — on
this corpus ~0.16 s a page against ~0.02 s for all the measuring a raster sweep
actually does, i.e. the decode *is* the sweep.

Measured on `1-048`: 109 ms -> 32 ms (3.4x), 0.60 MB -> 0.37 MB, and the boolean
ink mask `lines.ink_mask` derives is bit-identical. Every raster verb inherits
that — `zones check --ink`, `zones paragraphs`, `ocr gaps`, both blots, the crops
and the review sheets.

THREE PAGES ARE GENUINELY COLOUR AND ARE LEFT ALONE. `pdfimages -list` over the
three PDFs reports exactly three non-gray embedded images in the whole volume —
`1-001`, `1-002` (the covers) and `1-361` (part 1's appended foldout map), all
rgb/8bpc/jpeg at 150 ppi. Everything else is `gray 1 1 jbig2`. That list is the
authority for what may be converted, not a channel comparison of the rasters: it
says what the *source* holds rather than what one rendering happened to produce.

CONVERTED IN PLACE, NOT RE-RENDERED, AND THAT IS THE SAFETY ARGUMENT. Re-running
`pdftoppm -gray` would be tidier to describe and risks the one thing that must not
happen: a page whose dimensions come back a pixel different silently invalidates
every coordinate in `gt/zones/`, `gt/ocr/` and `gt/fig/`, which is what
`tools/migrate_coords.py` exists to record the cost of. `Image.convert("L")`
cannot change dimensions. Each page is checked for identical R/G/B channels
before conversion and its ink mask is compared before and after, so a page that
would lose anything is skipped and reported rather than written.

Re-running is safe: a page already in mode `L` is left alone.

HISTORICAL once it has run. `scans/` is derived and gitignored; if it is ever
rebuilt from `pdfs/`, poppler will write RGB again and this wants re-running.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# From `pdfimages -list` over the three source PDFs: the only non-gray embedded
# images in the volume. Named rather than detected, so a rendering artifact that
# happened to make a text page's channels differ cannot quietly convert it.
COLOUR_PAGES = {"1-001", "1-002", "1-361"}


def ref_of(p: Path) -> str:
    return p.stem.replace("chukchi-", "")


def convert_one(p: Path, commit: bool) -> dict:
    import numpy as np
    from PIL import Image

    ref = ref_of(p)
    rec = {"ref": ref, "action": "", "before": "", "after": "", "bytes": 0}
    with Image.open(p) as im:
        rec["before"] = im.mode
        if ref in COLOUR_PAGES:
            rec["action"] = "kept-colour"
            return rec
        if im.mode == "L":
            rec["action"] = "already-grey"
            return rec
        rgb = np.asarray(im.convert("RGB"))
        if not ((rgb[:, :, 0] == rgb[:, :, 1]).all()
                and (rgb[:, :, 1] == rgb[:, :, 2]).all()):
            # Not in the colour list but not grey either — say so and touch
            # nothing. Converting would discard something the source holds.
            rec["action"] = "SKIPPED-colour-content"
            return rec
        grey = im.convert("L")
        before_mask = np.asarray(im.convert("L")) < 128
        size = im.size

    after_mask = np.asarray(grey) < 128
    if grey.size != size or not (before_mask == after_mask).all():
        rec["action"] = "SKIPPED-mask-differs"
        return rec

    rec["after"] = "L"
    rec["action"] = "converted" if commit else "would-convert"
    if commit:
        # Through a temp in the same directory, so a crash cannot leave a
        # half-written PNG under a name the corpus reads.
        tmp = p.with_suffix(".png.tmp")
        grey.save(tmp, format="PNG", optimize=True)
        tmp.replace(p)
    rec["bytes"] = p.stat().st_size
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--commit", action="store_true",
                    help="write; without it, report what would change")
    ap.add_argument("--jobs", type=int, default=None)
    a = ap.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from harness.parallel import pmap

    pages = sorted((a.root / "scans").glob("chukchi-*.png"))
    if not pages:
        print("no scans/ to convert", file=sys.stderr)
        return 1

    recs = pmap(lambda p: convert_one(p, a.commit), pages, a.jobs)
    tally: dict[str, int] = {}
    for r in recs:
        tally[r["action"]] = tally.get(r["action"], 0) + 1
    for action, n in sorted(tally.items()):
        print(f"{action:24s} {n}")
    bad = [r for r in recs if r["action"].startswith("SKIPPED")]
    for r in bad:
        print(f"  {r['ref']}: {r['action']}", file=sys.stderr)
    total = sum(r["bytes"] for r in recs if r["bytes"])
    if total:
        print(f"{'bytes now':24s} {total / 1e6:.0f} MB")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
