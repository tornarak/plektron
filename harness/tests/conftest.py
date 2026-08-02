"""Shared fixtures — chiefly: **encode each distinct test raster once.**

The zones suite was 24 s of a 27 s run, and none of it was the logic. A page here
is 2824x3897, and PIL takes ~76 ms to PNG-encode one; writing bytes that are
already encoded takes ~0.5 ms. Every test that touched a page paid the encode
again, for a raster byte-identical to the last one.

So the encode is memoized on its arguments and the tests write the cached bytes.
Nothing about what is on the page changes — `_png` is a pure function of `(mode,
size, ink)` and the file on disk is byte-for-byte what `Image.new(...).save(...)`
produced before — which is the property that makes this a speed change and not a
test change.

**Full page dimensions are kept, deliberately.** Shrinking the raster would be a
bigger win still and would quietly invalidate the suite: the column anchor is
calibrated in pixels (`min_run_px`, `min_run_share`, a 1778 px measure), zone
geometry is checked against `width_tolerance_px`, and `min_zone_h_px` is 30. A
test page that is not the size of a real page tests thresholds against a page
those thresholds were never written for.
"""
from __future__ import annotations

from functools import cache
from io import BytesIO
from pathlib import Path

A4_300 = (2824, 3897)


@cache
def _png(mode: str, size: tuple[int, int], ink: tuple[tuple[int, int, int, int], ...]
         ) -> bytes:
    """One encoded page. Cached for the session on exactly what it depends on.

    `ink` is a tuple of filled `(x0, y0, x1, y1)` rectangles — a tuple rather than
    a list because it is part of the cache key, and hashability is what makes the
    memo correct rather than merely convenient.
    """
    from PIL import Image, ImageDraw

    im = Image.new(mode, size, 255 if mode == "L" else "white")
    if ink:
        dr = ImageDraw.Draw(im)
        black = 0 if mode == "L" else "black"
        for box in ink:
            dr.rectangle(list(box), fill=black)
    buf = BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def write_png(path: Path, size: tuple[int, int] = A4_300, mode: str = "L",
              ink: tuple[tuple[int, int, int, int], ...] = ()) -> Path:
    """Materialize a page. The write is ~0.5 ms; the encode happened once."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png(mode, tuple(size), tuple(ink)))
    return path


def write_scan(tmp_path: Path, ref: str, size: tuple[int, int] = A4_300,
               mode: str = "L",
               ink: tuple[tuple[int, int, int, int], ...] = ()) -> Path:
    """`<tmp_path>/scans/chukchi-<ref>.png`, the layout every reader assumes."""
    return write_png(tmp_path / "scans" / f"chukchi-{ref}.png", size, mode, ink)
