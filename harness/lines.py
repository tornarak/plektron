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

# **`--zoom N` means N display pixels per source pixel, as delivered.** Everything
# else follows from that, and deriving it is what keeps the number true:
#
#   window = (ZOOM_CLIENT_W - margins) / zoom    source px per strip
#   sheet  = ZOOM_CLIENT_W exactly, padded       so nothing is fitted on arrival
#
# A client shows about `ZOOM_CLIENT_W` px per image whatever you send it, so
# `source px per image × display px per source px` is a **constant**. Zoom picks a
# point on that curve; it cannot buy detail. Which is why building the sheet wider than
# the client does not reduce wrapping so much as make the scale untrue — and untrue by
# a *variable* factor, since a sheet sized to its widest strip is fitted by an amount
# that depends on how long the selected lines happen to be, so the same `--zoom 2`
# delivers 1.6× on a list and 1.0× on full-measure prose. To wrap less, lower the zoom
# (`--zoom 1` puts almost any line in one strip, and says 1×). Padding every sheet to
# the full width is what keeps the content out of the arithmetic.
#
# Wrapping is the real cost being traded, and it is not small: every strip boundary is
# a place where a form is seen in halves, and a reading assembled from halves is more
# fragile than one taken whole. 2× is the default because it resolves what matters on a
# 300 dpi bitonal scan — the breve on `1-073`'s `j̆`, the dot under its `g̣` — while
# leaving a full-measure line in two strips and a list line in one. Escalate per
# question: 6× when the question is one mark's shape, and take the wrapping there.
#
# The overlap is what keeps a boundary from being a blind spot: consecutive strips
# share enough that no glyph is only ever seen cut. Height is capped for the same
# reason as width, against the client's shorter axis.
ZOOM = 2
ZOOM_CLIENT_W = 1450
ZOOM_OVERLAP = 60
ZOOM_SHEET_H = 1600


def zoom_window(zoom: int, client_w: int = ZOOM_CLIENT_W) -> int:
    """Source px per strip such that `zoom`× of it fills the client width exactly."""
    from .figures import LABEL_W
    return max(40, (client_w - LABEL_W - 20) // max(1, zoom))

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
    """`String/@CONTENT` joined, NFD. `""` for a line the segmenter left empty.

    `¬` is substituted to `-`: a recurring CATMuS mis-recognition of the printed
    line-final hyphen (22 occurrences across 12 end-of-eval files), never a real
    character in this corpus's witness or ground truth. Mechanical, not a reading
    — the glyph it stands in for is unambiguous, unlike anything in keying_spec.md.
    """
    parts = [s.get("CONTENT") or "" for s in tl.iter("{*}String")]
    text = " ".join(p for p in parts if p).replace("¬", "-")
    return unicodedata.normalize("NFD", text)


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


def printspace_x(page) -> tuple[int, int] | None:
    """(left, right) of the `PrintSpace` in ALTO coordinates. None if absent."""
    ps = page.find("{*}PrintSpace") if page is not None else None
    bb = _bbox(ps) if ps is not None else None
    if not bb or bb.get("HPOS") is None or bb.get("WIDTH") is None:
        return None
    return bb["HPOS"], bb["HPOS"] + bb["WIDTH"]


def line_box(rec: dict, sx: float, sy: float, size: tuple[int, int],
             wide: tuple[int, int] | None = None) -> tuple | None:
    """Crop box in raster space for one `page_lines` record, padded and clamped.

    `wide` widens the box to those ALTO x-bounds, normally the `PrintSpace`'s. It
    exists because **a line polygon can exclude printed text that belongs to the
    line**, and the material it excludes is systematically the material sitting in
    the margins: `1-074` prints its list numbers `5.` and `9.` outside their boxes,
    `1-073` does the same with `5.` and strands the folio `51` outside every box on
    the page. Vertical padding cannot reach any of it — the omission is horizontal.

    Widening is not free, so it is not the default: a full-measure crop already runs
    to both margins, and on a short line the extra width pulls in whatever else the
    margin holds. It is a second look at a line, not a better one.
    """
    src = _poly_bounds(rec["points"]) if rec.get("points") else None
    if src is None:
        if rec.get("hpos") is None or rec.get("width") is None:
            return None
        src = (rec["hpos"], rec["vpos"],
               rec["hpos"] + rec["width"], rec["vpos"] + rec["height"])
    x0, y0, x1, y1 = src
    if wide is not None:
        x0, x1 = min(x0, wide[0]), max(x1, wide[1])
    box = (max(0, round(x0 * sx) - PAD_X),
           max(0, round(y0 * sy) - PAD_TOP),
           min(size[0], round(x1 * sx) + PAD_X),
           min(size[1], round(y1 * sy) + PAD_BOTTOM))
    return box if box[2] > box[0] and box[3] > box[1] else None


def line_crops(ref: str, alto_dir: str = "end-of-eval", root: Path = Path("."),
               scans: str = "scans", margins: bool = False):
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
    wide = printspace_x(page) if margins else None

    for rec in page_lines(alto):
        box = line_box(rec, sx, sy, img.size, wide)
        if box is None:
            continue
        yield rec, img.crop(box)


LINE_SHEET_H = 2000


def write_line_sheets(ref: str, out_dir: Path, alto_dir: str = "end-of-eval",
                      root: Path = Path("."), scans: str = "scans",
                      per_sheet: int = 8, margins: bool = False,
                      sheet_h: int | None = LINE_SHEET_H) -> list[dict]:
    """Compose the page's line crops into labelled contact sheets, in `out_dir` itself.

    `out_dir` is the destination, not a parent to hang a per-ref directory off — the
    per-ref directory is `paths.sheets_dir(ref)` and the caller has already resolved
    it. Same for `write_line_zoom` and `write_line_crops`.

    The reading pass wants a handful of images rather than forty, because reading
    forty separate crops means forty re-orientations — the same context-switch cost
    that made review line-based rather than span-based. The label drawn in the margin
    is the `page_lines` index, so a reading keys straight back to the ALTO line.

    **Nothing is downscaled.** The sheet is sized to the widest crop on the page, not
    to `figures.SHEET_W`. A body line runs ~1770 px against that constant's 1800 less
    the label margin, so the default would have resampled every full-measure line by
    about 0.95 — invisible on ordinary words and exactly the wrong trade here, where
    the question being asked of the image is whether a dot sits below a `g`.

    `sheet_h` packs by total height rather than a fixed line count (`per_sheet` is
    still an upper bound, raised well past what height alone would ever hit) — a page
    of short list lines like `1-053` fits far more than 8 per sheet before 2000px
    fills, and fewer, fuller sheets is fewer re-orientations for the same read.
    """
    from .figures import compose_sheets, LABEL_W
    items = [(str(rec["index"]), crop)
             for rec, crop in line_crops(ref, alto_dir, root, scans, margins)]
    if not items:
        return []
    width = max(im.width for _, im in items) + LABEL_W + 20
    sheets, index = compose_sheets(items, out_dir,
                                  per_sheet=per_sheet, prefix="lines",
                                  sheet_w=width, max_h=sheet_h)
    # One flat record per sheet, `lines` as a joined string rather than a list:
    # a nested value de-tabularizes the whole TOON table (see the module docstring).
    return [{"sheet": str(out_dir / e["sheet"]),
             "lines": " ".join(e["items"])} for e in index]


def parse_selection(spec: str) -> set[int]:
    """`"7,20,22-26"` -> `{7, 20, 22, 23, 24, 25, 26}`. Raises on anything else.

    Rejects rather than skips a token it cannot parse. A selection is a claim about
    which lines were looked at, and silently dropping one means a line reported as
    read was never rendered.
    """
    out: set[int] = set()
    for tok in spec.replace(" ", "").split(","):
        if not tok:
            continue
        if "-" in tok.lstrip("-"):
            a, b = tok.split("-", 1)
            lo, hi = int(a), int(b)
            if hi < lo:
                raise ValueError(f"range {tok!r} runs backwards")
            out.update(range(lo, hi + 1))
        else:
            out.add(int(tok))
    if not out:
        raise ValueError("empty line selection")
    return out


def write_line_zoom(ref: str, out_dir: Path, only: set[int] | None = None,
                    zoom: int = ZOOM, window: int | None = None,
                    overlap: int = ZOOM_OVERLAP, sheet_h: int = ZOOM_SHEET_H,
                    client_w: int = ZOOM_CLIENT_W,
                    alto_dir: str = "end-of-eval", root: Path = Path("."),
                    scans: str = "scans", margins: bool = False,
                    smooth: bool = False) -> list[dict]:
    """Magnified lines, sliced into overlapping strips and packed into few sheets.

    The reading pass needs this constantly — a contact sheet settles most of a line
    and leaves two or three forms wanting a closer look, and until this existed that
    closer look meant an ad-hoc crop script per page, with hand-typed pixel bounds
    that no later reader can check and that name the wrong region the moment a
    coordinate is fat-fingered. Here the bounds come from the same `line_box` the
    crops and the review page use, so a zoom is the *same* region enlarged rather
    than a second guess at where the line is.

    Strips from every selected line share the sheets, packed to `sheet_h`. One image
    per line would be the obvious shape and is the wrong one: what a reader pays here
    scales with the number of images, not their size. For the same reason, select
    every line you mean to look at in **one** call — a page's whole notation set in
    two sheets beats the same lines fetched four times, and running the verb once per
    doubt spends more than the closer look is worth.

    **Nearest-neighbour, not Lanczos.** The scan is bitonal, so every interpolated
    value is a grey the page does not contain, and smooth grey around a mark is
    precisely the appearance of a mark that is faintly there. Pixel replication can
    only make the raster bigger, never different — and the point of enlarging is to
    get past a viewer's downscaling, which replication does as well as any filter.
    `smooth` is there for shape comparison, where the question is which letterform it
    is rather than whether a mark is present.
    """
    from PIL import Image
    from .figures import compose_sheets, LABEL_W
    window = window or zoom_window(zoom, client_w)
    step = max(1, window - overlap)
    resample = Image.LANCZOS if smooth else Image.NEAREST
    strips, seen = [], []
    for rec, crop in line_crops(ref, alto_dir, root, scans, margins=margins):
        if only is not None and rec["index"] not in only:
            continue
        seen.append(rec["index"])
        for k, x in enumerate(range(0, max(1, crop.width - overlap), step)):
            s = crop.crop((x, 0, min(crop.width, x + window), crop.height))
            # Label is line index and strip position *within that line*, so the
            # sequence restarts per line and a form seen twice across an overlap is
            # recognisable as one form rather than two.
            strips.append((f"{rec['index']}.{k}",
                           s.resize((s.width * zoom, s.height * zoom), resample)))
    if only:
        for missing in sorted(only - set(seen)):
            raise ValueError(f"{norm_ref(ref)}: line {missing} is not on the page "
                             "(or has no usable geometry)")
    if not strips:
        return []
    # Fixed width, not the widest strip: a sheet sized to its content is fitted down
    # by a content-dependent factor on arrival, so `zoom` would mean a different
    # magnification on every selection. Padding costs white pixels and buys a number
    # that is the same every time.
    sheets, index = compose_sheets(strips, out_dir, per_sheet=len(strips),
                                  sheet_w=client_w, max_h=sheet_h,
                                  prefix=f"zoom{zoom}")
    return [{"sheet": str(out_dir / e["sheet"]), "zoom": zoom, "margins": margins,
             "strips": " ".join(e["items"])} for e in index]


def write_line_crops(ref: str, out_dir: Path, alto_dir: str = "end-of-eval",
                     root: Path = Path("."), scans: str = "scans",
                     margins: bool = False) -> list[dict]:
    """Crop every line to `out_dir/<index>-<line_id>.png`. Returns the records.

    Filenames lead with the zero-padded index so a directory listing is reading
    order — which is what makes `sxiv` over the directory a usable review view.
    """
    ref = norm_ref(ref)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for rec, crop in line_crops(ref, alto_dir, root, scans, margins):
        path = out_dir / f"{rec['index']:03d}-{rec['line_id']}.png"
        crop.save(path)
        out.append({**rec, "crop": str(path)})
    return out
