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

import pytest

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


def write_project(root: Path, stem: str = "chukchi") -> Path:
    """`root` as a text's stores: the manifest every store read starts from."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.json").write_text(f'{{"stem": "{stem}"}}\n', encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def _a_text_at_tmp_path(request):
    """Every `tmp_path` root is a text's stores, as the harness requires of a root.

    `chukchi` because that is what the page files the fixtures spell are called.
    A test with no use for `tmp_path` asks for nothing here.
    """
    if "tmp_path" in request.fixturenames:
        write_project(request.getfixturevalue("tmp_path"))


def write_scan(tmp_path: Path, ref: str, size: tuple[int, int] = A4_300,
               mode: str = "L",
               ink: tuple[tuple[int, int, int, int], ...] = ()) -> Path:
    """`<tmp_path>/scans/<stem>-<ref>.png`, the layout every reader assumes."""
    return write_png(tmp_path / "scans" / f"chukchi-{ref}.png", size, mode, ink)


def write_zones(root: Path, ref: str, bands: list[tuple[str, int, int]],
                x0: int = 100, x1: int = 1800) -> Path:
    """A keyed page in `gt/zones/`: one labelled block per `(label, y0, y1)` band.

    Since the OCR ALTOs stopped carrying zone labels, a line's `zone` is derived
    by containment against this store — so a fixture that wants a running title
    or a footnote recognised as one writes the bands here, beside its ALTO.
    """
    p = root / "gt" / "zones" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    tags = "".join(f'<OtherTag ID="BT{i}" LABEL="{label}"/>'
                   for i, (label, _, _) in enumerate(bands, 1))
    blocks = "".join(
        f'<TextBlock ID="mz_{ref}_r{i}" HPOS="{x0}" VPOS="{y0}" WIDTH="{x1 - x0}" '
        f'HEIGHT="{y1 - y0}" TAGREFS="BT{i}"><Shape><Polygon POINTS="{x0} {y0} '
        f'{x1} {y0} {x1} {y1} {x0} {y1}"/></Shape></TextBlock>'
        for i, (_, y0, y1) in enumerate(bands, 1))
    p.write_text('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">'
                 f'<Tags>{tags}</Tags><Layout><Page WIDTH="2824" HEIGHT="3897">'
                 f'<PrintSpace>{blocks}</PrintSpace></Page></Layout></alto>',
                 encoding="utf-8")
    return p


def write_captions(root: Path, blocks: dict[str, str]) -> None:
    """Caption text into `gt/fig/`, keyed `"<ref>|<zone-suffix>"` as the store is.

    The store holds the caption on the FigDesc block that carries its geometry, so
    a fixture that wants one has to put it there. This used to write
    a separate markdown caption file, in five copies of the same helper — which is how a
    caption store nothing read stayed plausible for as long as it did.

    A newline in `text` is a printed line break and is preserved as one: the split
    is what `block_text` keeps, and half of what a caption fixture is testing.
    """
    from harness.figures import save_caption_text

    by_ref: dict[str, dict[str, list[str]]] = {}
    for key, text in blocks.items():
        ref, _, suffix = key.partition("|")
        by_ref.setdefault(ref, {})[suffix] = text.split("\n")
    for ref, texts in by_ref.items():
        save_caption_text(ref, root, texts)
