#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11.0", "numpy>=2.0", "scipy>=1.14"]
# ///
"""Split an editor's leaf into the two layers the reading view serves.

`edition/page-img/chukchi-PP-NNN.png` is a **master**: one artefact a human made and
vouches for, tracked because nothing here can rebuild it. `1-361`, part 1's
foldout ethnographic map, was built in ChaiNNer — dejpeg, LAB, L divided by its
own 40 px blur to isolate the linework, upscaled through `2_MangaScaleV3`,
sharpened, colour-burnt back into the 2x-scaled original — and then hand-repaired
where the upscaler had wrecked the legend swatches. No script in this repo
reproduces that, which is exactly why the master is in git.

**Everything below the master is derived, and this is the derivation.** The
master is 21 MB, which is not a thing to hand a browser. The split is Mixed
Raster Content, the same decomposition DjVu and JBIG2-in-PDF make, and it works
because the sheet's two kinds of information have opposite statistics:

    linework   high frequency, one bit deep    -> 1.3 MB anti-aliased PNG
    colour     low frequency, needs no edges   -> 104 KB JPEG at a third scale

Composited in the browser, that is ~1.4 MB against the master's 21 MB with no
legibility cost — every village name in the two insets survives — because the
lettering never has to survive downsampling. It only has to survive a *brightness*
threshold, which it does trivially.

WHAT THE COLOUR LAYER IS NOT. The obvious way to get the ink out of the colour
layer is to mask it and fill from the surroundings, and it is wrong. Diffusion
asks "what colour is nearby", which cannot tell a town-sized Russianized-natives
enclave from a gap between two lines: measured on this sheet, an inpainting deep
enough to clear the Kolyma delta erased the Anadyr and Petropavlovsk enclaves
outright and softened every complex boundary. **A greyscale morphological closing
asks a different question** — "is this dark thing narrower than my brush" — so it
removes lines and lettering by their *width* and never touches a region wider than
the structuring element, whatever colour it is. The enclaves come through at full
saturation with hard edges because they are not operated on at all.

Done per RGB channel and not on lightness in LAB or HSL. Hue and saturation are
ill-defined where lightness is near zero, so under the ink they hold noise, and
lifting the lightness reveals it as green and yellow confetti along every stroke.
RGB has no such degeneracy.

WHAT IT KNOWINGLY DROPS. The coloured underlines that mark town-sized ethnic
enclaves do not survive the closing — they are thin by construction, which is the
one thing the operator is defined to remove. Accepted deliberately: the groups'
areas of settlement are discontinuous, so the value is nearly always inferable
from context, and the master is one click away at `/edition/leaf/PP-NNN`. Recorded
here rather than discovered later by somebody assuming the derivation was
lossless.

Run from the repo root:

    uv run --script tools/build_leaf_layers.py            # every master
    uv run --script tools/build_leaf_layers.py 1-361      # one leaf
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import grey_closing

Image.MAX_IMAGE_PIXELS = None

SRC = Path("edition/page-img")
OUT = Path("mz/page-img")

#: Isolating the linework: divide the LAB lightness by its own blur. A flat area
#: divides to 1 and every stroke falls below it, which is a local threshold that
#: costs no threshold — it follows the paper's own shading instead of fighting it.
#: sigma 20 reproduces the master's own second ChaiNNer pass to RMSE 0.017, and
#: that number is a real check rather than a claim: the authored linework existed
#: first and this was scored against it.
LINE_BLUR = 20.0

#: The anti-aliased layer's ink window and colour. `8%,70%` keeps the soft edge
#: pixels that make dense linework readable at any zoom other than 1:1 — a hard
#: 1-bit mask has no partial coverage to give the browser, so tight passages like
#: the Kolyma delta clump into blobs. The tint is the master's own warm black; a
#: pure `#000` reads as harsher than the paper ever was.
LINE_BLACK, LINE_WHITE = 0.08, 0.70
LINE_TINT = (0x2A, 0x21, 0x18)

#: The closing brush, in pixels **of the half-scale working image** — so 12 px on
#: the master. Every genuine colour feature on this sheet is wider than that; the
#: check when changing it is whether the narrowest one, the coastal Eskimo band on
#: the Chukchi peninsula, is still there afterwards.
CLOSE_RADIUS = 6

#: The colour layer ships at a third of the master. It is upscaled by the browser
#: and smooth colour survives that, which is the whole reason it may be small.
COLOUR_SCALE = 1 / 3
COLOUR_QUALITY = 86


def _disk(radius: int) -> np.ndarray:
    r = int(radius)
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def linework(master: Image.Image) -> Image.Image:
    """The master's ink, isolated. Greyscale, dark strokes on light paper."""
    lab_l = master.convert("LAB").getchannel(0)
    blur = lab_l.filter(ImageFilter.GaussianBlur(LINE_BLUR))
    lit = np.asarray(lab_l, dtype=np.float32)
    base = np.asarray(blur, dtype=np.float32)
    # The denominator is the *blur*, so a stroke divides below 1 and flat paper
    # divides to it. Guarded because a fully black neighbourhood would divide by
    # zero, and clipped because a lighter-than-local pixel may exceed 1.
    out = np.divide(lit, np.maximum(base, 1.0))
    return Image.fromarray((np.clip(out, 0.0, 1.0) * 255).astype(np.uint8), "L")


def line_layer(lines: Image.Image) -> Image.Image:
    """The linework as a tinted RGBA layer: ink opaque, paper transparent."""
    ink = 1.0 - np.asarray(lines, dtype=np.float32) / 255.0
    alpha = (ink - (1.0 - LINE_WHITE)) / (LINE_WHITE - LINE_BLACK)
    alpha = (np.clip(alpha, 0.0, 1.0) * 255).astype(np.uint8)
    rgba = np.zeros(alpha.shape + (4,), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = LINE_TINT
    rgba[..., 3] = alpha
    return Image.fromarray(rgba, "RGBA")


def colour_layer(master: Image.Image) -> Image.Image:
    """The master with its ink closed away: flat colour, every region intact."""
    half = master.convert("RGB").resize(
        (master.width // 2, master.height // 2), Image.LANCZOS)
    arr = np.asarray(half)
    disk = _disk(CLOSE_RADIUS)
    closed = np.dstack([grey_closing(arr[..., c], footprint=disk)
                        for c in range(3)])
    out = Image.fromarray(closed, "RGB")
    # The closing leaves a faint print of its own structuring element; a small
    # median and a light blur take it off without touching the boundaries, which
    # are an order of magnitude wider than either.
    out = out.filter(ImageFilter.MedianFilter(3)).filter(
        ImageFilter.GaussianBlur(1.0))
    w = round(master.width * COLOUR_SCALE)
    return out.resize((w, round(master.height * COLOUR_SCALE)), Image.LANCZOS)


def build(master_path: Path, out_dir: Path) -> list[tuple[Path, int]]:
    stem = master_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(master_path) as im:
        master = im.convert("RGB")
    written = []

    colour = out_dir / f"{stem}.colour.jpg"
    colour_layer(master).save(colour, quality=COLOUR_QUALITY, optimize=True)
    written.append((colour, colour.stat().st_size))

    lines = out_dir / f"{stem}.lines.png"
    line_layer(linework(master)).save(lines, optimize=True)
    written.append((lines, lines.stat().st_size))
    return written


def main(argv: list[str]) -> int:
    root = Path.cwd()
    src, out = root / SRC, root / OUT
    if not src.is_dir():
        print(f"no {SRC}/ under {root} — run from the repo root", file=sys.stderr)
        return 2

    masters = sorted(p for p in src.glob("chukchi-*.png"))
    if argv:
        want = {a.strip() for a in argv}
        masters = [p for p in masters
                   if p.stem.removeprefix("chukchi-") in want]
        missing = want - {p.stem.removeprefix("chukchi-") for p in masters}
        for ref in sorted(missing):
            print(f"no master for {ref} in {SRC}/", file=sys.stderr)
        if missing:
            return 1
    if not masters:
        print(f"no masters in {SRC}/", file=sys.stderr)
        return 0

    for m in masters:
        total = 0
        for path, size in build(m, out):
            print(f"  {size / 1024:8.0f} K  {path.relative_to(root)}")
            total += size
        src_size = m.stat().st_size
        print(f"{m.stem}: {src_size / 1_048_576:.1f} MB master -> "
              f"{total / 1_048_576:.2f} MB pair "
              f"({src_size / total:.0f}x)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
