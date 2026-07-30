"""Line identity and line crops — the addressable unit for span-level review.

Nothing else in the repo keys anything at line granularity, and the existing
reader cannot be pressed into it. `context._lines_from_alto` **drops empty lines
and discards `@ID`**, so index *i* in `catmus_draft` is not the *i*-th `TextLine`
in the ALTO, and the `line` field on every `detector_flags` record inherits that
offset. Nothing may join a detector flag to a crop except through `page_lines`.

That reader is deliberately left alone: changing it would move `catmus_draft`,
and with it the firewall's substring test and every detector line number.

Two rules here, both about not losing the join:

  * Empty lines are **kept**. A segmenter emits them, and dropping them silently
    renumbers everything after. `text` is `""`, position is preserved.
  * Every value is a scalar. The TOON encoder collapses a list of records to a
    header plus rows only while the records are flat and share one key set; a
    single nested dict de-tabularizes the whole table. `context.figures_on_page`
    carries a nested `bbox` and that is exactly why the page context emits in the
    verbose form. So geometry is flattened to `hpos`/`vpos`/`width`/`height`, and
    `baseline`/`points` stay the space-separated strings ALTO already uses.
"""
from __future__ import annotations
import unicodedata
from pathlib import Path
from lxml import etree

from .context import norm_ref
from .figures import _bbox, _scale_for

# Padding around a line crop, in raster pixels, asymmetric on the vertical.
#
# This was 4 briefly, tightened from 14 to stop a sliver of the neighbouring line
# bleeding in on `2-030`'s 21 px-pitch gloss list. That was the wrong trade and it
# cost two real errors on `1-074` alone: the segmentation box excludes a U+0323 sitting
# under a `g` descender (line 11's `Ñerg̣eˊrɪk`, line 5's `Am-g̣roˊkĭ`), so at 4 the dot
# was simply not in the image, and both readings dropped it. Polygon and rectangle
# bounds are identical on these lines, so no choice of box recovers it — only padding.
#
# The harm is asymmetric, which is what the earlier reasoning missed. A bled
# neighbour is clipped, obviously partial, and announces itself. A clipped diacritic
# is invisible: the reader sees a well-formed glyph that is missing a mark, with
# nothing to indicate anything was lost. So pad generously and accept the bleed.
#
# Bottom exceeds top because a below-mark sits under the descender, further outside
# the box than an above-mark sits over the ascender.
PAD_X = 8
PAD_TOP = 10
PAD_BOTTOM = 18

LINE_KEYS = ("index", "line_id", "block_id", "text",
             "hpos", "vpos", "width", "height", "baseline", "points")


def alto_for_lines(ref: str, alto_dir: str = "end-of-eval",
                   root: Path = Path(".")) -> Path:
    """Path to one page's ALTO in whichever store is being read.

    Takes the directory as an argument rather than hardcoding it, because the
    two callers want different stores for the same ref: the review pass reads the
    recognizer output in `end-of-eval/`, the verifier reads the restored ground
    truth in `gt/ocr/`. Note `figures.alto_for` is not this — it is hardwired to
    `fig/` and answers a different question.

    Never resolve to `ocr/`. Those are symlinks into `gt/ocr/`, so naming them
    means a reader of this code has to know that to know what is being touched.
    """
    return root / alto_dir / f"chukchi-{norm_ref(ref)}.xml"


def _line_text(tl) -> str:
    """`String/@CONTENT` joined, NFD. `""` for a line the segmenter left empty."""
    parts = [s.get("CONTENT") or "" for s in tl.iter("{*}String")]
    return unicodedata.normalize("NFD", " ".join(p for p in parts if p))


def page_lines(alto_path: Path) -> list[dict]:
    """One flat record per `TextLine`, document order, empties included.

    `line_id` is the ALTO `@ID`. eScriptorium and kraken both write one; where a
    file omits it the index stands in as `line-<n>`, so the join never silently
    falls back to position alone without saying so.
    """
    tree = etree.parse(str(alto_path))
    out = []
    for i, tl in enumerate(tree.iter("{*}TextLine")):
        bb = _bbox(tl) or {}
        blk = tl.getparent()
        out.append({
            "index": i,
            "line_id": tl.get("ID") or f"line-{i}",
            "block_id": (blk.get("ID") if blk is not None else None),
            "text": _line_text(tl),
            "hpos": bb.get("HPOS"),
            "vpos": bb.get("VPOS"),
            "width": bb.get("WIDTH"),
            "height": bb.get("HEIGHT"),
            "baseline": tl.get("BASELINE"),
            "points": (tl.find("{*}Shape/{*}Polygon").get("POINTS")
                       if tl.find("{*}Shape/{*}Polygon") is not None else None),
        })
    return out


def _poly_bounds(points: str) -> tuple[int, int, int, int] | None:
    """Bounding box of a `Shape/Polygon`, as (x0, y0, x1, y1).

    Preferred over `HPOS/VPOS/WIDTH/HEIGHT` when present: kraken's baseline
    segmentation writes a polygon that follows the ink, and the rectangle it also
    writes is the polygon's bounds — but only sometimes, and a wrong rectangle
    crops a diacritic off the top, which is the one thing this must not do.
    """
    toks = points.split()
    xs, ys = [], []
    for i, t in enumerate(toks):
        try:
            v = float(t)
        except ValueError:
            return None
        (xs if i % 2 == 0 else ys).append(v)
    if not xs or not ys:
        return None
    return round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))


def line_box(rec: dict, sx: float, sy: float, size: tuple[int, int]) -> tuple | None:
    """Crop box in raster space for one `page_lines` record, padded and clamped."""
    src = _poly_bounds(rec["points"]) if rec.get("points") else None
    if src is None:
        if rec.get("hpos") is None or rec.get("width") is None:
            return None
        src = (rec["hpos"], rec["vpos"],
               rec["hpos"] + rec["width"], rec["vpos"] + rec["height"])
    x0, y0, x1, y1 = src
    box = (max(0, round(x0 * sx) - PAD_X),
           max(0, round(y0 * sy) - PAD_TOP),
           min(size[0], round(x1 * sx) + PAD_X),
           min(size[1], round(y1 * sy) + PAD_BOTTOM))
    return box if box[2] > box[0] and box[3] > box[1] else None


def line_crops(ref: str, alto_dir: str = "end-of-eval", root: Path = Path("."),
               scans: str = "scans"):
    """Yield `(record, PIL.Image)` per line on one page, cropped from the raster.

    `_scale_for` is used rather than assuming the two spaces agree. They do agree
    for `end-of-eval/` today — every page's `Page/@WIDTH|@HEIGHT` matches its
    raster exactly — but the reason the primitive exists (no page is exactly ×2,
    see CLAUDE.md) applies the moment anything is re-rendered, and a silently
    mis-scaled crop looks like a recognition error rather than a geometry one.

    No rotate-if-tall heuristic. `caption_crops` has one because captions are
    sometimes set vertically beside a figure; a text line never is, so the test
    could only ever misfire here.
    """
    from PIL import Image
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    page = etree.parse(str(alto)).find(".//{*}Page")
    img = Image.open(root / scans / f"chukchi-{ref}.png")
    sx, sy = _scale_for(page, img.size)

    for rec in page_lines(alto):
        box = line_box(rec, sx, sy, img.size)
        if box is None:
            continue
        yield rec, img.crop(box)


def write_line_sheets(ref: str, out_dir: Path, alto_dir: str = "end-of-eval",
                      root: Path = Path("."), scans: str = "scans",
                      per_sheet: int = 8) -> list[dict]:
    """Compose the page's line crops into labelled contact sheets.

    The reading pass wants a handful of images rather than forty, because reading
    forty separate crops means forty re-orientations — the same context-switch cost
    that made review line-based rather than span-based. The label drawn in the margin
    is the `page_lines` index, so a reading keys straight back to the ALTO line.

    **Nothing is downscaled.** The sheet is sized to the widest crop on the page, not
    to `figures.SHEET_W`. A body line runs ~1770 px against that constant's 1800 less
    the label margin, so the default would have resampled every full-measure line by
    about 0.95 — invisible on ordinary words and exactly the wrong trade here, where
    the question being asked of the image is whether a dot sits below a `g`.
    """
    from .figures import compose_sheets, LABEL_W
    items = [(str(rec["index"]), crop)
             for rec, crop in line_crops(ref, alto_dir, root, scans)]
    if not items:
        return []
    width = max(im.width for _, im in items) + LABEL_W + 20
    sheets, index = compose_sheets(items, out_dir / norm_ref(ref),
                                  per_sheet=per_sheet, prefix="lines",
                                  sheet_w=width)
    # One flat record per sheet, `lines` as a joined string rather than a list:
    # a nested value de-tabularizes the whole TOON table (see the module docstring).
    return [{"sheet": str(out_dir / norm_ref(ref) / e["sheet"]),
             "lines": " ".join(e["items"])} for e in index]


def write_line_crops(ref: str, out_dir: Path, alto_dir: str = "end-of-eval",
                     root: Path = Path("."), scans: str = "scans") -> list[dict]:
    """Crop every line to `out_dir/<ref>/<index>-<line_id>.png`. Returns the records.

    Filenames lead with the zero-padded index so a directory listing is reading
    order — which is what makes `sxiv` over the directory a usable review view.
    """
    ref = norm_ref(ref)
    d = out_dir / ref
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for rec, crop in line_crops(ref, alto_dir, root, scans):
        path = d / f"{rec['index']:03d}-{rec['line_id']}.png"
        crop.save(path)
        out.append({**rec, "crop": str(path)})
    return out
