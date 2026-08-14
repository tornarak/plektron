#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf>=1.24", "pillow>=11.0"]
# ///
"""Build `scans/` from the PDFs' own layers instead of rendering the page.

`scans/` was `pdftoppm -r 300` over `pdfs/`, and that renders the *page box*. The
three PDFs are MRC-layered — a 1-bit JBIG2 master per page, plus separate embedded
JPEGs for the photographs — and the page boxes they were wrapped in are arbitrary,
so rendering resampled a bitonal master that could have been copied.

EVERY MASTER IS PLACED AT SCALE 1.0 AND IS EXACTLY 300 DPI, measured against its own
placement rather than the page box. Over 832 pages: 470 at (300.00, 300.00), 359 at
(300.00, 300.04), and 3 masterless RGB pages at 150. `docs/rasters.md`'s "part 1 at
295.5 dpi, part 3 at 308.4" divided by the mediabox and is wrong. The parts differ
only by a **translation**, which is what those boxes did:

  part 1  master 2781x3866 centred in a 2824x3897 box  -> +21.375, +15.375 px of
          white padding, a *fractional* offset, so poppler resampled every pixel of
          every page for a shift of three-eighths of one.
  part 2  master 2550x3525 at (0, 0) in a 2550x3525 box. A pure blit was available
          and poppler smeared it anyway: 247 grey values from a 2-value source.
  part 3  part 2's layout jammed onto A4 -> -34.875, -8.58 px, so the render is
          *cropped*, ~35 px off each side. Part 3 has been read below source
          resolution since the beginning.

WHAT IT REFUSES TO DO QUIETLY. A page is refused, named, and left unwritten rather
than turned into something plausible: two full-page images; a JBIG2 master that is
not at scale 1.0; an embedded image whose rect falls outside its master; a photo
whose paste ratio is not near-integral. The three masterless RGB pages — `1-001`,
`1-002` (covers) and `1-361` (the foldout) — are carved out by name: each is one
150 ppi photograph of a whole leaf, written **at its own size** rather than doubled
to the page's 300 dpi, which added no detail and cost 26.5 MB across the three.

THE ISOLATION IS THE FIREWALL. This declares its dependencies inline (PEP 723), as
`tools/build_geo.py` does, so it runs under `uv run --script` in an environment that
does **not** contain the harness. That is not an inconvenience to work around: the
harness is offline over what is committed and must never open a PDF, and a script
that *cannot* import it cannot drift into being part of a loop.

    uv run --script tools/extract_scans.py                  # report, writes nothing
    uv run --script tools/extract_scans.py --commit         # write data/pdf_images.json
    uv run --script tools/extract_scans.py --commit --rasters scans.new

`--commit` gates the tracked manifest; `--rasters DIR` additionally cuts the tree.
They are separate because the manifest is the audit's input and is useful before any
raster moves, and because the tree must be swapped whole rather than written in
place — `scans/` may never be half one coordinate space and half the other.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

DPI = 300
PT = DPI / 72.0                      # device px per PostScript point at 300 dpi

#: Named rather than detected, `greyscale_scans.py`'s rule: this says what the
#: *source* holds, not what one rendering happened to produce. These three pages
#: carry no JBIG2 master — they are RGB photographs of a cover and a foldout — so
#: the scale-1.0 refusal below does not apply to them and would otherwise refuse
#: its own corpus.
MASTERLESS = {"1-001", "1-002", "1-361"}

#: Part number by source filename fragment. The PDFs are symlinks whose names carry
#: the part in Roman numerals; `PP-NNN` needs the arabic one.
PARTS = ((" Part I ", 1), (" Part II ", 2), (" Part III ", 3))

SCALE_TOL = 0.001      # a master's px-per-pt against 300/72
PASTE_TOL = 0.02       # a photo's paste ratio against the nearest integer
#: Tolerance for treating a rect edge as landing on an integer. **Sized against the
#: input's precision, not against float64's.** PyMuPDF parses PDF numbers at float32
#: precision — `5.13` arrives as `5.130000114440918` — so an edge that is exactly
#: 435 computes as 434.9999897, and `1e-6` would not catch it while a bare `floor`
#: would expand the rect by a pixel and report a placement the source does not have.
#: The floor under this is the *smallest genuine* fraction: PDF coordinates here are
#: given to two decimal places, and 0.01 pt is 0.0417 px at 300 dpi, so 1e-3 is
#: forty times clear of anything real. `1-037` is the live case.
SNAP = 1e-3


def _out(v: float, up: bool) -> int:
    """Round a rect edge outward, having first snapped off the parse error.

    Outward is deliberate: a rect one pixel short of its photo leaves exactly the
    antialiased fringe this whole change exists to remove. The pad is one thing and
    the arithmetic is another, and neither may stand in for the other — a rect that
    grew by a pixel because of float32 would be a pad nobody chose.
    """
    if abs(v - round(v)) < SNAP:
        return int(round(v))
    return math.ceil(v) if up else math.floor(v)


def part_of(pdf: Path) -> int:
    """Which part a source PDF is, from its filename.

    Longest fragment first: `" Part I "` is a substring of neither `" Part II "`
    nor `" Part III "` given the trailing space, but the ordering is made explicit
    rather than left to depend on that.
    """
    for frag, n in sorted(PARTS, key=lambda t: -len(t[0])):
        if frag in pdf.name:
            return n
    raise SystemExit(f"cannot tell which part this is: {pdf.name}")


def page_images(page) -> list[dict]:
    """Every embedded image on the page with its placement, largest first.

    `bbox` from PyMuPDF is already y-down page coordinates, which is the same
    orientation as a raster, so nothing here flips an axis. That is worth stating
    because the PDF's own y runs the other way and the trap is real: part 3's
    master sits 8.58 px above the page top and 8.54 px below its bottom, and an
    offset taken from the wrong edge is wrong by a pixel on one axis only.
    """
    out = []
    for im in page.get_image_info(xrefs=True):
        x0, y0, x1, y1 = im["bbox"]
        out.append({"xref": im["xref"], "w": im["width"], "h": im["height"],
                    "bpc": im["bpc"], "cs": im["cs-name"],
                    "pt": (x0, y0, x1, y1)})
    out.sort(key=lambda i: -(i["w"] * i["h"]))
    return out


def page_record(page, ref: str) -> dict:
    """One page's manifest entry, or a refusal.

    The geometry is derived **per page**, never from a per-part table: `1-303`'s
    master is 2824x3866 among 357 neighbours at 2781x3866, so a constant would be
    wrong there and silently.
    """
    rec: dict = {"ref": ref, "refuse": "", "master": None, "offset": [0, 0],
                 "render": [0, 0], "images": []}
    imgs = page_images(page)
    if not imgs:
        rec["refuse"] = "no embedded image"
        return rec

    m = imgs[0]
    if ref in MASTERLESS:
        # **Taken at its own size, not rendered.** These three are one RGB
        # photograph of a whole leaf at 150 ppi, and rendering the page at 300
        # doubled them for nothing: 796 KB of source became 26.5 MB of PNG, and the
        # foldout map came out visibly the worse for it. `render` still records the
        # size poppler used, because that is what the old coordinates are in and it
        # is the only way to recognise them — but no coordinate exists on any of
        # the three, all being fully exempt.
        rec["master"] = {"w": m["w"], "h": m["h"], "bpc": m["bpc"], "cs": m["cs"],
                         "xref": m["xref"], "rendered": True}
        rec["render"] = [_out(page.rect.width * PT, True),
                         _out(page.rect.height * PT, True)]
        return rec

    big = [i for i in imgs
           if (i["w"] * i["h"]) >= 0.5 * (m["w"] * m["h"])
           and (i["pt"][2] - i["pt"][0]) >= 0.9 * page.rect.width]
    if len(big) > 1:
        rec["refuse"] = f"{len(big)} full-page images"
        return rec

    mx0, my0, mx1, my1 = m["pt"]
    sx = m["w"] / (mx1 - mx0)
    sy = m["h"] / (my1 - my0)
    if abs(sx - PT) > SCALE_TOL or abs(sy - PT) > SCALE_TOL:
        rec["refuse"] = (f"master not at scale 1.0 "
                         f"({sx * 72 / DPI:.5f}, {sy * 72 / DPI:.5f})")
        return rec

    rec["master"] = {"w": m["w"], "h": m["h"], "bpc": m["bpc"], "cs": m["cs"],
                     "xref": m["xref"], "rendered": False}
    # render -> master is `master = render - offset`. The render sampled the media
    # box at 300 dpi from (0, 0); the master starts at its own bbox origin.
    rec["offset"] = [round(mx0 * PT), round(my0 * PT)]
    # **The legacy render's own size, recorded rather than inferred.** It is the
    # media box at 300 dpi and is *not* the master plus the offset: part 1's master
    # is 2781x3866 at (21, 15) inside a 2824x3897 page, so the arithmetic misses by
    # the right-hand margin. A reader deciding which coordinate space a store is in
    # needs the number, and getting it wrong silently files every part 1 page as
    # unrecognised — which is what it did until this line existed.
    #
    # `_out(.., up=True)` is **ceil-with-a-snap**, which is poppler's rule and the
    # snag `migrate_coords.py` records in one: poppler ceils, so 935.1 pt gives 3897
    # and a `round` gives 3896; but a bare `ceil` "predicts 2782 for the covers where
    # poppler renders 2781", because 667.44/72*300 computes as 2781.0000000000005.
    # Both halves are needed and neither alone is right. This number is a historical
    # fact about a tree that is going away — it exists only so a store's old
    # coordinates can still be recognised — so it has to reproduce what was, not
    # what would be tidiest.
    rec["render"] = [_out(page.rect.width * PT, True),
                     _out(page.rect.height * PT, True)]

    for im in imgs[1:]:
        x0, y0, x1, y1 = im["pt"]
        # **`PT`, not the measured `sx`.** The scale-1.0 refusal above has already
        # established that this master is at exactly 300 dpi; going on to divide by
        # a float32-derived width would quietly reintroduce the error that check
        # exists to exclude, and would make every rect depend on the parse rather
        # than on the fact.
        rect = [_out((x0 - mx0) * PT, False), _out((y0 - my0) * PT, False),
                _out((x1 - mx0) * PT, True), _out((y1 - my0) * PT, True)]
        if (rect[0] < 0 or rect[1] < 0
                or rect[2] > m["w"] or rect[3] > m["h"]):
            rec["refuse"] = f"image xref {im['xref']} falls outside the master"
            return rec
        ratio = (rect[2] - rect[0]) / max(1, im["w"])
        if abs(ratio - round(ratio)) > PASTE_TOL:
            rec["refuse"] = f"image xref {im['xref']} pastes at {ratio:.4f}x"
            return rec
        rec["images"].append({
            "xref": im["xref"], "w": im["w"], "h": im["h"], "bpc": im["bpc"],
            "cs": im["cs"], "ppi": round(im["w"] / ((x1 - x0) / 72.0), 1),
            "rect": rect})
    return rec


ABOUT = (
    "Derived but tracked, on data/geo/'s precedent: pdfs/ are symlinks outside the "
    "repository, so a clone cannot rebuild this. Built by "
    "tools/extract_scans.py --commit. Per page: `master` is the full-page image "
    "scans/ is cut from, `offset` is the integer shift from the legacy pdftoppm "
    "render space into master space (master = render - offset), and `images` are "
    "the embedded photographs with `rect` in MASTER pixels, rounded outward. "
    "`rendered: true` marks the three masterless RGB pages, which are rasterised "
    "at 300 dpi as before and do not move."
)


def _pil(pix):
    """A PyMuPDF pixmap as a PIL image, without a temp file."""
    from PIL import Image
    mode = {1: "L", 3: "RGB", 4: "CMYK"}[pix.n - pix.alpha]
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def cut_page(doc, page, rec: dict, out_dir: Path) -> dict:
    """Write one page's raster: the master, with its photographs pasted back.

    **Mode `1` where the page has no photograph**, which is 593 of 832 and is what
    the source actually is — a bitonal master we were rendering to 8-bit greyscale
    and resampling on the way. A page carrying a photograph has to be `L`, since a
    halftone is not two-valued.

    The photographs go back **nearest at their integral scale**, so every native
    JPEG sample survives as an exact block and nothing is invented between them.
    That is also what makes `fig crops --source native` and the composite show the
    same pixels at different sizes rather than two different pictures.
    """
    import pymupdf
    from PIL import Image

    ref = rec["ref"]
    m = rec["master"]
    dest = out_dir / f"chukchi-{ref}.png"
    pix = pymupdf.Pixmap(doc, m["xref"])
    if m.get("rendered"):
        # A whole-leaf RGB photograph and nothing to composite onto it. Written at
        # its own size: doubling it to the page's 300 dpi added no detail and cost
        # 26.5 MB across the three.
        _pil(pix).save(dest)
        return {"ref": ref, "mode": "RGB", "photos": 0}

    img = _pil(pix)
    if img.mode != "L":
        img = img.convert("L")
    if (img.width, img.height) != (m["w"], m["h"]):
        return {"ref": ref, "mode": "", "photos": 0,
                "refuse": f"master decoded {img.width}x{img.height}, "
                          f"expected {m['w']}x{m['h']}"}

    for im in rec["images"]:
        x0, y0, x1, y1 = im["rect"]
        photo = _pil(pymupdf.Pixmap(doc, im["xref"]))
        if photo.mode not in ("L", "RGB"):
            photo = photo.convert("L")
        target = (x1 - x0, y1 - y0)
        if photo.size != target:
            photo = photo.resize(target, Image.NEAREST)
        if photo.mode != "L":
            photo = photo.convert("L")
        img.paste(photo, (x0, y0))

    if not rec["images"]:
        # Lossless: the master holds two values, so mode `1` is the same picture
        # in an eighth of the bits — and it stops colour depth from correlating
        # with "has a figure", which is the confound the blot exists to remove.
        img = img.convert("1")
    img.save(dest)
    return {"ref": ref, "mode": img.mode, "photos": len(rec["images"])}


def build(root: Path, pdf_dir: Path, rasters: Path | None = None
          ) -> tuple[dict, list[dict]]:
    """Walk every page of every PDF. Returns (manifest, records)."""
    import pymupdf

    manifest: dict = {"_about": ABOUT}
    records = []
    if rasters is not None:
        rasters.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        part = part_of(pdf)
        with pymupdf.open(pdf) as doc:
            for i, page in enumerate(doc, start=1):
                ref = f"{part}-{i:03d}"
                rec = page_record(page, ref)
                if not rec["refuse"] and rasters is not None:
                    cut = cut_page(doc, page, rec, rasters)
                    rec["mode"] = cut.get("mode", "")
                    if cut.get("refuse"):
                        rec["refuse"] = cut["refuse"]
                records.append(rec)
                if rec["refuse"]:
                    continue
                manifest[ref] = {"master": rec["master"], "offset": rec["offset"],
                                 "render": rec["render"], "images": rec["images"]}
    return manifest, records


def report(records: list[dict], manifest_path: Path, wrote: bool) -> int:
    """Aligned columns, `build_geo.py`'s shape. Refusals to stderr and exit 1."""
    ok = [r for r in records if not r["refuse"]]
    bad = [r for r in records if r["refuse"]]
    bitonal = [r for r in ok
               if not r["images"] and not (r["master"] or {}).get("rendered")]
    composite = [r for r in ok if r["images"]]
    rendered = [r for r in ok if (r["master"] or {}).get("rendered")]
    shifted = [r for r in ok if r["offset"] != [0, 0]]
    photos = sum(len(r["images"]) for r in ok)

    print(f"{'pages':24s} {len(records)}")
    print(f"{'  bitonal (mode 1)':24s} {len(bitonal)}")
    print(f"{'  composite (mode L)':24s} {len(composite)}  carrying {photos} photos")
    print(f"{'  rendered as before':24s} {len(rendered)}  "
          f"{' '.join(r['ref'] for r in rendered)}")
    print(f"{'  needing a shift':24s} {len(shifted)}")
    print(f"{'refused':24s} {len(bad)}")

    offsets: dict[tuple[int, int], list[str]] = {}
    for r in ok:
        offsets.setdefault(tuple(r["offset"]), []).append(r["ref"])
    print("\noffset (render -> master)   pages")
    for off, refs in sorted(offsets.items()):
        print(f"  {str(off):24s} {len(refs):4d}  {refs[0]}..{refs[-1]}")

    sizes: dict[tuple[int, int], int] = {}
    for r in ok:
        m = r["master"] or {}
        sizes[(m.get("w"), m.get("h"))] = sizes.get((m.get("w"), m.get("h")), 0) + 1
    print("\nmaster size                 pages")
    for size, n in sorted(sizes.items(), key=lambda kv: -kv[1]):
        print(f"  {str(size):24s} {n:4d}")

    for r in bad:
        print(f"REFUSED {r['ref']}: {r['refuse']}", file=sys.stderr)

    print(f"\nwrote {manifest_path}" if wrote else
          "\nreport only; --commit writes data/pdf_images.json")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--commit", action="store_true",
                    help="write data/pdf_images.json; without it, report only")
    ap.add_argument("--rasters", type=Path, default=None, metavar="DIR",
                    help="also cut the raster tree into DIR (needs --commit). "
                         "A sibling of scans/, swapped whole afterwards.")
    a = ap.parse_args(argv)

    pdf_dir = a.root / "pdfs"
    if not pdf_dir.is_dir():
        raise SystemExit(f"no {pdf_dir}")
    if a.rasters is not None and not a.commit:
        raise SystemExit("--rasters needs --commit")
    manifest, records = build(a.root, pdf_dir, a.rasters)

    out = a.root / "data" / "pdf_images.json"
    if a.commit:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(f".json.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(manifest, indent=1, sort_keys=False) + "\n",
                       encoding="utf-8")
        tmp.replace(out)
    return report(records, out, a.commit)


if __name__ == "__main__":
    raise SystemExit(main())
