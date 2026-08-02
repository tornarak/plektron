"""Line identity and line crops — the addressable unit for span-level review.

Nothing else in the repo keys anything at line granularity, and the existing
reader cannot be pressed into it. `context._lines_from_alto` **drops empty lines
and discards `@ID`**, so index *i* in `catmus_draft` is not the *i*-th `TextLine`
in the ALTO, and the `line` field on every `detector_flags` record inherits that
offset. Nothing may join a detector flag to a crop except through `page_lines`.

That reader used to be described here as "deliberately left alone: changing it
would move `catmus_draft`, and with it the firewall's substring test and every
detector line number." Half of that is spent — the verbatim-substring test was
removed (see the comment at its old site in `validate.validate`). The live half
still binds, and is now satisfied differently: `_lines_from_alto` delegates its
*order* to `page_lines`, so `catmus_draft` and `detector_flags` cannot disagree
with each other or with `ocr_lines`. It still drops empty lines, so its indices
are still not the ALTO's.

**Order is presentation; `index` is identity.** `page_lines` returns lines in
reading order — banded rows, left to right — while `index` stays the position
ALTO document order assigned. The two genuinely diverge: 18 of the 20 restored
pages reorder, 524 positions in all. Since `proposal.json` and `decision.json`
are keyed by `index` and `restore` joins on it, anything that renumbers would
silently mis-map every adjudicated page.

Three rules here, all about not losing the join:

  * Empty lines are **kept**. A segmenter emits them, and dropping them silently
    renumbers everything after. `text` is `""`, position is preserved.
  * Every value is a scalar. The TOON encoder collapses a list of records to a
    header plus rows only while the records are flat and share one key set; a
    single nested dict de-tabularizes the whole table. `context.figures_on_page`
    carries a nested `bbox` and that is exactly why the page context emits in the
    verbose form. So geometry is flattened to `hpos`/`vpos`/`width`/`height`, and
    `baseline`/`points` stay the space-separated strings ALTO already uses.
  * Every record carries **every** key, `None` where it does not apply. The same
    encoder rule from the other side: a ragged key set is what silently degrades
    the table to the nested form, so `in_figdesc`/`in_graphic`/`figdesc_straddle`
    are present on every line, not only on the ones inside a figure.
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


# The store a verb reads when none is named. `ocr/` is the *read view* over every
# OCR store the project has: today a symlink farm into `gt/ocr/`, and the place a
# raw-recognizer sibling (`htr/`, the `#htr` rank) links in beside it if one is ever
# produced again. It is the default because a reader almost always wants "whatever
# this page's OCR currently is", not a named generation of it.
#
# This replaced `end-of-eval/`, the stock-CATMuS output, which was deleted once the
# ground-truth rebuild finished. Four verbs defaulted to it by name and died with an
# OSError the moment it went; hence one constant rather than eight literals.
DEFAULT_ALTO_DIR = "ocr"


def raster_path(ref: str, root: Path = Path("."), scans: str = "scans") -> Path:
    """One page's raster, refusing early and by name.

    Four call sites here open a page with `Image.open`, and on a fresh clone every
    one of them raised `FileNotFoundError: 'scans/chukchi-1-048.png'` — accurate,
    but it reads as a missing *page* when the truth is that `scans/` was never
    rendered, and the two want completely different things from the reader. This
    separates them: `farms.require` speaks first when the whole tree is gone, and
    the per-page message stands when only the page is.
    """
    from . import farms
    farms.require(root, scans)
    p = root / scans / f"chukchi-{norm_ref(ref)}.png"
    if not p.exists():
        raise FileNotFoundError(f"no raster for {norm_ref(ref)} at {p}")
    return p


def alto_for_lines(ref: str, alto_dir: str = DEFAULT_ALTO_DIR,
                   root: Path = Path(".")) -> Path:
    """Path to one page's ALTO in whichever store is being read.

    Takes the directory as an argument rather than hardcoding it, because callers
    want different stores for the same ref: an inspection reads the current OCR
    through `ocr/`, while a comparison against a specific generation names that
    generation. Note `figures.alto_for` is not this — it is hardwired to `gt/fig/`
    and answers a different question.

    **Reads may resolve through `ocr/`; writes may not.** The earlier rule here
    forbade `ocr/` outright, on the grounds that its entries are symlinks into
    `gt/ocr/` and naming them hides what is being touched. That is right about
    *writing* — `restore` still names `gt/ocr/` explicitly, and the loss this repo
    suffered came from a write landing in a store nobody meant to touch. It is
    wrong about reading: resolving a page to its current OCR is the whole purpose
    of a union view, and a read cannot destroy anything.

    The consequence a caller must know: under the default, this can resolve to the
    same real file another part of the same verb writes. `restore` handles that
    case by name — see its `mode` field.

    Refuses when `alto_dir` is a **derived tree that was never built**, so the
    default path on a fresh clone names the missing view rather than letting lxml
    raise `Error reading file 'ocr/chukchi-1-048.xml'` — loud enough, but blaming
    the page for a directory nobody made. A store that merely holds nothing is not
    an error and is not touched; see `farms.require`.
    """
    from . import farms
    farms.require(root, alto_dir)
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


def reading_order(recs: list[dict]) -> list[dict]:
    """Order line records the way a human reads them: banded rows, left to right.

    **A plain `sort(key=(vpos, hpos))` is wrong**, and wrong worst on the layout
    this exists for. Baselines wobble a few pixels across a row, so on `3-005`'s
    two-column kinship table strict sorting puts the gloss *before* its headword
    on four rows of six -- `Mother-in-law.` at vpos 2378 ahead of its own
    `Ñaw-mataˊlɪn` at 2382. That is worse than the segmenter's own order.

    So: group lines into rows whose `vpos` differs by no more than half the
    page's *median line height*, then order each row by `hpos`. The tolerance is
    derived from the page rather than tuned -- on these scans it lands near 30 px
    against a row pitch of ~44 and an observed wobble of <=6, so there is wide
    margin on both sides, and a page set in a different size carries its own
    threshold with it.

    Each line is compared against the **band's first** `vpos`, never the previous
    line's, so a skewed scan cannot accumulate drift and swallow a genuine row.

    Records with no geometry sort last, in index order: they cannot be placed, and
    guessing a position for them would be worse than admitting it.
    """
    placed = [r for r in recs if r.get("vpos") is not None]
    unplaced = [r for r in recs if r.get("vpos") is None]
    heights = sorted(r["height"] for r in placed if r.get("height"))
    tol = (heights[len(heights) // 2] / 2) if heights else 0

    out: list[dict] = []
    band: list[dict] = []
    for r in sorted(placed, key=lambda r: r["vpos"]):
        if band and r["vpos"] - band[0]["vpos"] > tol:
            out += sorted(band, key=lambda r: (r["hpos"] if r["hpos"] is not None else 0))
            band = []
        band.append(r)
    out += sorted(band, key=lambda r: (r["hpos"] if r["hpos"] is not None else 0))
    out += sorted(unplaced, key=lambda r: r["index"])
    for rank, r in enumerate(out):
        r["y_rank"] = rank
    return out


# A line this much inside a `GraphicZone-FigDesc` is that caption, not body text.
# Fraction of the *line's* area, so a caption line inside a large zone still scores
# ~1.0 and a body line merely adjacent to one scores ~0.
FIGDESC_INSIDE = 0.85
# Below this, an overlap is zone-edge noise rather than contact: `2-030`'s line 29
# clips its GraphicZone by 0.08 and is wholly a caption line, nothing straddling.
FIGDESC_TOUCH = 0.05


def _overlap_fraction(rec: dict, z: dict) -> float:
    """Share of a line's box lying inside a zone. 2D, and that matters.

    A Y-only test calls `1-151`'s entire left-hand text column "inside" the figure
    that sits beside it in the right margin — 14 body lines misread as caption at
    the first attempt. Both axes, always.
    """
    if rec.get("hpos") is None or rec.get("vpos") is None:
        return 0.0
    area = (rec.get("width") or 0) * (rec.get("height") or 0)
    if not area:
        return 0.0
    ox = max(0, min(rec["hpos"] + rec["width"], z["hpos"] + z["width"])
             - max(rec["hpos"], z["hpos"]))
    oy = max(0, min(rec["vpos"] + rec["height"], z["vpos"] + z["height"])
             - max(rec["vpos"], z["vpos"]))
    return ox * oy / area


def mark_figure_overlap(recs: list[dict], ref: str, root: Path = Path(".")) -> list[dict]:
    """Tag each line with the figure zone it falls in, if any. Mutates and returns.

    Three outcomes, and the distinction between the first two is the whole point:

      * `in_figdesc` — the line is a **caption**, ≥`FIGDESC_INSIDE` inside a
        `GraphicZone-FigDesc`. The project already holds a human reading of every
        caption in `data/readings.md`, and `harness tei context` hands it to collation
        from there, so a line segment over one is a redundant second witness —
        machine-rank, on the 812 pages not yet keyed by hand.
      * `in_graphic` — the line lies inside a plain `GraphicZone`. **Flagged, never
        suppressed.** `3-006`'s `CONSANGUINITY.` sits wholly inside a caption-less
        oversized zone and is a genuine section heading; a rule keyed on "inside a
        figure" rather than on `FigDesc` would delete it.
      * `figdesc_straddle` — a partial overlap with a caption zone, i.e. one
        `TextLine` running from a wrapped caption into body text. A known segmenter
        failure, reported for a human rather than silently split in the store.

    Every record gets all three keys, `None` when they do not apply: a ragged key
    set silently degrades the TOON table to its verbose nested form (see the module
    docstring), so absent must still be present.
    """
    from .figures import zones as _zones
    zs = _zones(ref, root)
    figdesc = [z for z in zs if "FigDesc" in (z["label"] or "")]
    graphic = [z for z in zs if "Graphic" in (z["label"] or "") and z not in figdesc]
    for rec in recs:
        rec["in_figdesc"] = None
        rec["in_graphic"] = None
        rec["figdesc_straddle"] = None
        for z in figdesc:
            f = _overlap_fraction(rec, z)
            if f >= FIGDESC_INSIDE:
                rec["in_figdesc"] = z["id"]
                break
            if f > FIGDESC_TOUCH:
                rec["figdesc_straddle"] = z["id"]
        if rec["in_figdesc"] is None:
            for z in graphic:
                if _overlap_fraction(rec, z) >= FIGDESC_INSIDE:
                    rec["in_graphic"] = z["id"]
                    break
    return recs


def page_lines(alto_path: Path, root: Path | None = None) -> list[dict]:
    """One flat record per `TextLine`, **reading order**, empties included.

    `index` is assigned from ALTO **document order, before the reorder**, and is
    the record's identity: `proposal.json` and `decision.json` are keyed by it and
    `restore` joins on it. Measured over the 20 restored pages, 18 change order
    under a reading-order sort (524 positions in all; `1-101` moves every one of
    its 59), so renumbering would silently mis-map every adjudicated page. Output
    is reordered; identities never move -- which means the labels appear out of
    numeric sequence, and that is the tell that `index` means identity rather than
    position.

    `y_rank` is the reading position, supplied so no caller re-derives it.

    `line_id` is the ALTO `@ID`. eScriptorium and kraken both write one; where a
    file omits it the index stands in as `line-<n>`, so the join never silently
    falls back to position alone without saying so.

    `zone` is the containing block's declared type, resolved through `TAGREFS` to
    `OtherTag/@LABEL` — **never from the tag ID**, which is assigned per export.
    It is `""` wherever the store does not label its blocks, which is every page of
    `gt/ocr/` and `gt/seg/`: those blocks came from a segmentation whose regions
    carried no semantic value. `mz/ocr/` labels every one, because `ocr predict`
    writes the zones in as the regions, and that field is what lets a consumer drop
    the running title and the signature line without a second walk of the tree.
    """
    from .figures import _block_label, _labels
    tree = etree.parse(str(alto_path))
    labels = _labels(tree)
    out = []
    for i, tl in enumerate(tree.iter("{*}TextLine")):
        bb = _bbox(tl) or {}
        blk = tl.getparent()
        out.append({
            "index": i,
            "line_id": tl.get("ID") or f"line-{i}",
            "block_id": (blk.get("ID") if blk is not None else None),
            "zone": (_block_label(blk, labels) if blk is not None else ""),
            "text": _line_text(tl),
            "hpos": bb.get("HPOS"),
            "vpos": bb.get("VPOS"),
            "width": bb.get("WIDTH"),
            "height": bb.get("HEIGHT"),
            "baseline": tl.get("BASELINE"),
            "points": (tl.find("{*}Shape/{*}Polygon").get("POINTS")
                       if tl.find("{*}Shape/{*}Polygon") is not None else None),
        })
    # Figure-zone marking needs the page's ref and the repo root. Both are derivable
    # from the ALTO's own location (`<root>/<store>/chukchi-<ref>.xml`) so that every
    # caller gets the marking without having to remember to ask — the failure mode
    # §1 hit, where three consumers each had to opt in to reading order. Where the
    # derivation does not hold (a `--out` path, a tmp_path fixture) no figure ALTO is
    # found and every record carries the keys with `None`, which is exactly right:
    # a page with no figure ALTO has no figure.
    try:
        ref = norm_ref(alto_path.stem)
        mark_figure_overlap(out, ref, root if root is not None else alto_path.parent.parent)
    except ValueError:
        for rec in out:
            rec["in_figdesc"] = rec["in_graphic"] = rec["figdesc_straddle"] = None
    return reading_order(out)


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


def line_crops(ref: str, alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
               scans: str = "scans", margins: bool = False):
    """Yield `(record, PIL.Image)` per line on one page, cropped from the raster.

    `_scale_for` is used rather than assuming the two spaces agree. They do agree
    across the current stores — every page's `Page/@WIDTH|@HEIGHT` matches its
    raster exactly — but the reason the primitive exists (no page is exactly ×2,
    see CLAUDE.md) applies the moment anything is re-rendered, and a silently
    mis-scaled crop looks like a recognition error rather than a geometry one.

    No rotate-if-tall heuristic. Captions are sometimes set vertically beside a
    figure and wanted one; a text line never is, so the test
    could only ever misfire here.
    """
    from PIL import Image
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    page = etree.parse(str(alto)).find(".//{*}Page")
    img = Image.open(raster_path(ref, root, scans))
    sx, sy = _scale_for(page, img.size)
    wide = printspace_x(page) if margins else None

    for rec in page_lines(alto):
        box = line_box(rec, sx, sy, img.size, wide)
        if box is None:
            continue
        yield rec, img.crop(box)


# A band of ink shorter than this is a rule, a speck or a stray descender, not a
# dropped line of type.
#
# Measured against *ink height*, which is not the same quantity as a `TextLine`
# box height -- an earlier version of this comment derived the number from "the
# shortest TextLine is 44 px" and was wrong twice over (the true minimum across
# the restored pages is 38, and a box is not its ink). The honest derivation is
# narrower than it looks: the smallest confirmed dropped line in the corpus,
# `3-005`'s centred small-caps `AFFINITY.`, yields **23 px of ink**, and the
# footnote rules this must not report yield 1-4. So 20 sits in the gap between
# them, and a floor of 30 -- which would look conservative -- would have missed a
# real finding. Treat it as measured, not as safe.
MIN_BAND_H = 20
# A row counts as inked when this share of the measured text column is dark. Low,
# because a line of type is mostly white space between letters — the job here is
# to separate "some type on this row" from "blank paper", not to measure density.
ROW_INK_FRACTION = 0.005
# Rows within this many px of an existing TextLine are treated as already covered.
# Ascenders and descenders overshoot a line's own box routinely (CLAUDE.md: a line
# polygon can exclude printed text), and without the slack every page reports its
# own lines back as gaps.
COVER_PAD = 6


def ink_mask(src) -> object:
    """The page as a boolean array, True where the paper is dark.

    The one decode, in one place. Every caller of `ink_bands` and every anchor
    measurement wants the same `< 128` mask off the same raster, and the decode is
    what the check actually costs — ~0.16 s of PNG inflate against ~0.02 s for all
    the measuring put together, on a 2824x3897 leaf. So the mask is a value that
    gets passed around rather than something each measurement re-derives: a page
    validated with `ink=True` used to decode its raster twice, once for the column
    anchor and once for the ink bands.

    Accepts a path or an open PIL image, and returns the array unchanged if handed
    one, so a caller that already has the page never re-reads it.
    """
    import numpy as np
    if isinstance(src, np.ndarray):
        return src
    from PIL import Image
    if hasattr(src, "convert"):
        return np.asarray(src.convert("L")) < 128
    with Image.open(src) as im:
        return np.asarray(im.convert("L")) < 128


def ink_bands(ink, x0: int, x1: int, covered,
              min_h: int = MIN_BAND_H,
              fraction: float = ROW_INK_FRACTION) -> list[dict]:
    """Contiguous bands of ink in the `x0..x1` window that `covered` does not mask.

    The measuring core of `line_gaps`, extracted because `zones.validate_page` asks
    the same question of a page with different boxes drawn on it — "is there ink
    here that nothing accounts for?" — and two implementations of one threshold is
    how the answers start disagreeing. `MIN_BAND_H` and `ROW_INK_FRACTION` are
    derived at their definitions above and both callers inherit the derivation.

    `ink` is an `ink_mask` array; `covered` is one entry per image row, true where
    something already accounts for that row. Returns `{vpos, height, hpos, width}`
    in **raster** coordinates, each band carrying the extent of its own ink rather
    than of the measuring window — a repair needs the geometry of what was found,
    not of where it was looked for.

    Still counts **every other column**, as the original per-pixel loop did, so that
    vectorising this changed no verdict anywhere in the corpus. Sampling costs
    nothing to undo now, but undoing it would move a threshold that was calibrated
    against the sampled count, and the two dropped headings this exists to catch —
    `1-048`'s and `3-005`'s 23 px `AFFINITY.` — sit close enough to it to care.
    """
    import numpy as np
    ink = ink_mask(ink)
    h, w = ink.shape
    x0, x1 = max(0, x0), min(w, x1)
    cols = x1 - x0
    if cols <= 0:
        return []
    band = ink[:, x0:x1]
    threshold = max(1, int(cols * fraction))
    rows = (band[:, ::2].sum(axis=1) * 2 >= threshold)
    rows &= ~np.asarray(covered, dtype=bool)[:h]

    # Run boundaries from a single diff over the row mask, padded either end so a
    # band running to the top or bottom of the page is not lost.
    edges = np.flatnonzero(np.diff(np.concatenate(
        ([0], rows.view(np.int8), [0]))))
    out = []
    for start, end in zip(edges[::2], edges[1::2], strict=True):
        if end - start < min_h:
            continue
        nz = np.flatnonzero(band[start:end].any(axis=0))
        if not len(nz):
            continue
        out.append({"vpos": int(start), "height": int(end - start),
                    "hpos": x0 + int(nz[0]),
                    "width": int(nz[-1] - nz[0]) + 1})
    return out


def line_gaps(ref: str, alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
              scans: str = "scans") -> list[dict]:
    """Bands of ink on the page that no `TextLine` covers — dropped lines.

    The segmentation this corpus was built from **drops whole printed lines**, and
    nothing detected it. `gt/fig/` had its lines stripped for exactly this reason
    (CLAUDE.md), and `1-053` reached restored ground truth missing two lines of
    body text — found only because the footnote-marker check reported a marker
    with no reference, and traced by hand from there. A dropped line is invisible
    to every text-level check by construction: the text that is there is correct,
    so nothing disagrees with anything.

    Measured, never inferred. Row-wise ink over the raster, masked by the existing
    line boxes, contiguous runs above `MIN_BAND_H` reported with the column extent
    of their own ink. The numbers a repair needs come from the page rather than
    from interpolation between its neighbours.

    Report-only, and it will have false positives by design: running heads,
    folios, figure labels and plate captions are ink that legitimately has no
    `TextLine` in an OCR store. A band is a place to look, not a verdict.
    """
    from PIL import Image
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    page = etree.parse(str(alto)).find(".//{*}Page")
    img = Image.open(raster_path(ref, root, scans)).convert("L")
    w, h = img.size
    sx, sy = _scale_for(page, img.size)

    recs = page_lines(alto)
    # Column window from the page's own lines, so the margins (and the scanner's
    # dark gutter) never register as ink. Falls back to the full width if a page
    # somehow has no geometry to measure.
    lefts = [r["hpos"] * sx for r in recs if r.get("hpos") is not None]
    rights = [(r["hpos"] + r["width"]) * sx for r in recs
              if r.get("hpos") is not None and r.get("width") is not None]
    x0, x1 = (int(min(lefts)), int(max(rights))) if lefts else (0, w)
    x0, x1 = max(0, x0), min(w, x1)

    import numpy as np
    covered = np.zeros(h, dtype=bool)
    for r in recs:
        if r.get("vpos") is None or r.get("height") is None:
            continue
        top = max(0, int(r["vpos"] * sy) - COVER_PAD)
        bot = min(h, int((r["vpos"] + r["height"]) * sy) + COVER_PAD)
        covered[top:bot] = True

    # Figures are ink with no TextLine by construction, so without this every
    # illustrated page reports its own artwork as dropped text: `2-030` returned 2
    # bands and `3-006` returned 12, all of them graphics. Masking the declared
    # zones takes both to zero, verified per band on both axes. `gt/fig/` covers
    # 252 of 832 pages; on the rest there is nothing to mask and nothing is lost,
    # since a page with no figure ALTO has no figure.
    from .figures import zones as _zones
    for z in _zones(ref, root):
        top = max(0, int(z["vpos"] * sy) - COVER_PAD)
        bot = min(h, int((z["vpos"] + z["height"]) * sy) + COVER_PAD)
        covered[top:bot] = True

    # The measuring itself is `ink_bands`, shared with `zones.validate_page` so the
    # two detectors cannot drift apart on a threshold.
    return ink_bands(ink_mask(img), x0, x1, covered)


GAP_ID_PREFIX = "gap_"


def adopt_gaps(ref: str, vpos_list: list[int], alto_dir: str = DEFAULT_ALTO_DIR,
               root: Path = Path("."), scans: str = "scans",
               commit: bool = False) -> dict:
    """Materialize measured gap bands as empty `TextLine`s in `gt/ocr/`.

    **Preview unless `commit`.** This is one of exactly two writers into the
    ground-truth store, and for most of its life it was the only one that wrote
    on invocation with no gate at all — `restore` next to it has always required
    `--commit`. Every refusal below (an unmeasured vpos, a band overlapping an
    existing line) is raised before anything is written either way, so the
    preview is a real rehearsal rather than a cheaper check.

    A dropped line cannot be repaired by `restore`, which only writes `CONTENT`
    into lines that already exist. Something has to create the line first, and the
    geometry has to be *measured* rather than interpolated between its neighbours
    -- `line_gaps` already measured it, so this adopts a band by naming its `vpos`.

    **The judgement stays explicit.** Geometry is measured; that a given band is a
    line of type rather than a running head, a figure label or a speck is a human
    call, made by naming the band and recorded in the ALTO by the `gap_` id prefix,
    so a recovered line is identifiable from the store alone.

    **Geometry only, never text.** This is a second writer into `gt/ocr/`, and the
    rebuild skill forbids writing there as a shortcut for the pipeline. What makes
    it legitimate is that every `String` it creates is empty: text still arrives
    solely through `decision.json` -> `restore`, which stays the only writer of
    content. Two guards enforce it -- the target is resolved to `gt/ocr/`
    explicitly rather than through the `ocr/` view, and a band already covered by a
    line is refused rather than duplicated.

    Appended at the end of `PrintSpace`, so the new line takes the highest index
    and nothing existing is renumbered -- `proposal.json` and `decision.json` are
    keyed by index and a shift would mis-map every adjudicated line on the page.
    Document order is not reading order here anyway (running heads and folios
    already sit out of position), and `page_lines` sorts for display, so the
    appended line still shows in its right place.

    After this and before adjudication `restore` will refuse the page -- the new
    lines have no decision yet. That is correct, and it means a repair is one
    uninterrupted sequence rather than two sessions.
    """
    from PIL import Image
    ref = norm_ref(ref)
    target = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
    if not target.exists():
        raise FileNotFoundError(f"{target} does not exist")

    bands = {b["vpos"]: b for b in line_gaps(ref, alto_dir, root, scans)}
    wanted = []
    for v in vpos_list:
        if v not in bands:
            raise ValueError(
                f"{ref}: no measured gap band at vpos={v}. "
                f"Available: {sorted(bands) or 'none'} "
                "(run `harness ocr gaps PP-NNN`; a band must be measured, "
                "never hand-entered)")
        wanted.append(bands[v])

    tree = etree.parse(str(target))
    page = tree.getroot().find(".//{*}Page")
    ps = tree.getroot().find(".//{*}PrintSpace")
    if ps is None:
        raise ValueError(f"{target}: no PrintSpace to append to")
    img = Image.open(raster_path(ref, root, scans))
    sx, sy = _scale_for(page, img.size)

    existing = page_lines(target, root)
    ns = etree.QName(ps).namespace
    added = []
    for b in wanted:
        # Raster space -> ALTO space. The two agree across the current stores, but
        # the ratio is taken per axis rather than assumed, for the same reason
        # `line_crops` does: a silently mis-scaled box looks like a segmentation
        # error rather than a units one.
        x, y = round(b["hpos"] / sx), round(b["vpos"] / sy)
        w, h = round(b["width"] / sx), round(b["height"] / sy)
        clash = [r for r in existing
                 if r.get("vpos") is not None
                 and not (r["vpos"] + r["height"] <= y or y + h <= r["vpos"])
                 and not (r["hpos"] + r["width"] <= x or x + w <= r["hpos"])]
        if clash:
            raise ValueError(
                f"{ref}: band at vpos={b['vpos']} overlaps existing line(s) "
                f"{[c['index'] for c in clash]} — refusing to duplicate a line "
                "that is already segmented")

        suffix = f"{ref}-{b['vpos']}"
        blk = etree.SubElement(ps, f"{{{ns}}}TextBlock", {
            "HPOS": str(x), "VPOS": str(y), "WIDTH": str(w), "HEIGHT": str(h),
            "ID": f"{GAP_ID_PREFIX}textblock_{suffix}"})
        shape = etree.SubElement(blk, f"{{{ns}}}Shape")
        etree.SubElement(shape, f"{{{ns}}}Polygon", {
            "POINTS": f"{x} {y} {x + w} {y} {x + w} {y + h} {x} {y + h}"})
        tl = etree.SubElement(blk, f"{{{ns}}}TextLine", {
            "ID": f"{GAP_ID_PREFIX}line_{suffix}",
            "BASELINE": f"{x} {y + h} {x + w} {y + h}",
            "HPOS": str(x), "VPOS": str(y), "WIDTH": str(w), "HEIGHT": str(h)})
        tshape = etree.SubElement(tl, f"{{{ns}}}Shape")
        etree.SubElement(tshape, f"{{{ns}}}Polygon", {
            "POINTS": f"{x} {y} {x + w} {y} {x + w} {y + h} {x} {y + h}"})
        # Empty by construction. The whole legitimacy of this writer rests on it.
        etree.SubElement(tl, f"{{{ns}}}String", {
            "CONTENT": "", "HPOS": str(x), "VPOS": str(y),
            "WIDTH": str(w), "HEIGHT": str(h)})
        added.append({"vpos": b["vpos"], "line_id": tl.get("ID"),
                      "hpos": x, "y": y, "width": w, "height": h})

    if not commit:
        # The tree was built and every guard passed; it simply is not written.
        # `new_indices` is null rather than guessed: an index is assigned by
        # document order in the file that does not exist yet, and inventing one
        # here would be a number to key against that nothing produced.
        return {"ref": ref, "path": str(target), "committed": False,
                "lines_before": len(existing),
                "lines_after": len(existing) + len(added), "added": added,
                "new_indices": None}

    tree.write(str(target), xml_declaration=True, encoding="UTF-8", standalone=None)
    after = page_lines(target, root)
    return {"ref": ref, "path": str(target), "committed": True,
            "lines_before": len(existing),
            "lines_after": len(after), "added": added,
            "new_indices": [r["index"] for r in after
                            if (r["line_id"] or "").startswith(GAP_ID_PREFIX)]}


def write_blot(ref: str, out_dir: Path, alto_dir: str = DEFAULT_ALTO_DIR,
               root: Path = Path("."), scans: str = "scans") -> dict:
    """The page with every line box and every figure zone painted out.

    The inverse of `line_gaps`, and a check on it: that verb reports what it
    thinks was missed, this one shows the whole page with everything *accounted
    for* erased, so what remains is uncovered by construction and a human can see
    it at a glance rather than trusting a threshold. `MIN_BAND_H` and
    `ROW_INK_FRACTION` cannot hide anything here — nothing is measured, only
    covered.

    Intended corpus-wide once auto-segmentation and OCR land over all 832 pages,
    which is when "did the segmenter miss anything substantial?" stops being
    answerable by reading twenty pages.

    Boxes are painted, not polygons: a polygon follows the ink and would leave a
    fringe of stray pixels around every line that reads as residue. The point is
    to make what is left *conspicuous*, so covering generously is right.
    """
    from PIL import Image, ImageDraw

    from .figures import zones as _zones
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    page = etree.parse(str(alto)).find(".//{*}Page")
    img = Image.open(raster_path(ref, root, scans)).convert("RGB")
    sx, sy = _scale_for(page, img.size)
    d = ImageDraw.Draw(img)

    n_lines = n_zones = 0
    for rec in page_lines(alto, root):
        if rec.get("hpos") is None or rec.get("vpos") is None:
            continue
        d.rectangle([rec["hpos"] * sx, rec["vpos"] * sy,
                     (rec["hpos"] + rec["width"]) * sx,
                     (rec["vpos"] + rec["height"]) * sy], fill=(255, 214, 214))
        n_lines += 1
    for z in _zones(ref, root):
        d.rectangle([z["hpos"] * sx, z["vpos"] * sy,
                     (z["hpos"] + z["width"]) * sx,
                     (z["vpos"] + z["height"]) * sy], fill=(214, 229, 255))
        n_zones += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"chukchi-{ref}.png"
    img.save(path)
    return {"ref": ref, "path": str(path), "lines_blotted": n_lines,
            "zones_blotted": n_zones}


def write_fig_blot(ref: str, out_dir: Path, root: Path = Path("."),
                   scans: str = "scans") -> dict:
    """The page with its figures painted out in white — the segmenter's training input.

    Sibling of `write_blot` and deliberately not a mode of it, because the two have
    opposite audiences. That one paints in conspicuous pink and blue so a *human*
    can see what is left uncovered; this one has to look like blank paper, since a
    model trained on filled blue boxes would learn a feature that exists nowhere at
    inference time. Same geometry, same per-axis `_scale_for`, opposite colour, and
    the reason is worth keeping written down.

    Why blot at all: a paragraph that wraps around an illustration is still one
    paragraph, and its zone is still the full measure. Leaving the figure in teaches
    the model that a body zone sometimes stops halfway down the page for reasons it
    can see — which is true of the ink and false of the coding.

    Boxes rather than polygons, as in `write_blot`: covering generously is right
    when the alternative is a fringe of stray figure pixels the model can key on.

    **The declared box is painted and not a pixel more, and that is a measured
    decision rather than a default.** Over a 40-page sample, 24 pages keep some ink
    within 12 px outside a zone, and the two kinds are not the same thing: on plate
    pages like `1-167` it is a few pixels of the photograph's own edge overhanging
    its box, while on `1-283` it is **body text set hard against an inset figure**.
    A 12 px pad would erase that text on every page like the second, which is a far
    larger confound than the sliver it would tidy on pages like the first. The
    geometry in `gt/fig/` is human-reviewed and reconciled; widening it here would
    be inventing it.

    Returns `painted: 0` for the 580 pages with no figure ALTO. The caller links
    those instead of copying — see `zones.blot_all`.
    """
    from PIL import Image, ImageDraw

    from .figures import zones as _zones
    ref = norm_ref(ref)
    src = root / scans / f"chukchi-{ref}.png"
    zs = _zones(ref, root)
    img = Image.open(src)
    # The figure ALTOs record geometry in the same raster space, but the ratio is
    # taken per page and per axis anyway — no page in this corpus is a clean x2 of
    # its 150 dpi predecessor, and assuming 1.0 is the same class of error.
    if zs:
        alto = _figure_alto_page(ref, root)
        sx, sy = _scale_for(alto, img.size) if alto is not None else (1.0, 1.0)
        # The source mode is kept, never normalized to "L". The 580 figure-less
        # pages reach the trainer as symlinks to the untouched scan, so converting
        # here would hand `ketos segtrain` a corpus that is RGB on one page and
        # greyscale on the next — a difference correlated with "has a figure",
        # which is precisely the thing being blotted out.
        white = 255 if img.mode in ("L", "1") else (255,) * len(img.getbands())
        d = ImageDraw.Draw(img)
        for z in zs:
            d.rectangle([z["hpos"] * sx, z["vpos"] * sy,
                         (z["hpos"] + z["width"]) * sx,
                         (z["vpos"] + z["height"]) * sy], fill=white)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"chukchi-{ref}.png"
    img.save(path)
    img.close()
    return {"ref": ref, "path": str(path), "painted": len(zs)}


def _figure_alto_page(ref: str, root: Path):
    """The `Page` element of this ref's figure ALTO, or None if it has none."""
    from .figures import alto_for as _fig_alto
    p = _fig_alto(ref, root)
    if not p.exists():
        return None
    return etree.parse(str(p)).find(".//{*}Page")


LINE_SHEET_H = 2000


def write_line_sheets(ref: str, out_dir: Path, alto_dir: str = DEFAULT_ALTO_DIR,
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
    from .figures import LABEL_W, compose_sheets
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
                    alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
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

    from .figures import compose_sheets
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


def write_line_crops(ref: str, out_dir: Path, alto_dir: str = DEFAULT_ALTO_DIR,
                     root: Path = Path("."), scans: str = "scans",
                     margins: bool = False) -> list[dict]:
    """Crop every line to `out_dir/<y_rank>-<index>-<line_id>.png`. Returns the records.

    Filenames lead with the zero-padded **reading position**, so a directory
    listing — and `sxiv` over it — really is reading order. They used to lead with
    `index`, on the stated grounds that index order *was* reading order; that was
    wrong on 18 of the 20 restored pages, because ALTO document order is not
    reading order (a running head routinely lands mid-sequence, a folio last).
    `index` stays in the name straight after it, because it is the identity every
    other artefact is keyed by and a filename that cannot be joined back to a
    decision is a filename that has to be re-derived.
    """
    ref = norm_ref(ref)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for rec, crop in line_crops(ref, alto_dir, root, scans, margins):
        path = out_dir / f"{rec['y_rank']:03d}-{rec['index']:03d}-{rec['line_id']}.png"
        crop.save(path)
        out.append({**rec, "crop": str(path)})
    return out
