"""Line identity and line crops — the addressable unit for span-level review.

Nothing else in the repo keys anything at line granularity, and the existing
reader cannot be pressed into it. `context._lines_from_alto` **drops empty lines
and discards `@ID`**, so position *i* in `catmus_draft` is not the *i*-th `TextLine`
in the ALTO. A `detector_flags` record used to carry that position and now carries
`index`, taken from `page_lines` — so a flag joins `ocr_lines`, resolves with
`ocr zoom --only`, and is citable in `@facs`.

That reader used to be described here as "deliberately left alone: changing it
would move `catmus_draft`, and with it the firewall's substring test and every
detector line number." Half of that is spent — the verbatim-substring test was
removed (see the comment at its old site in `validate.validate`). The live half
still binds, and is now satisfied differently: `_lines_from_alto` delegates its
*order* to `page_lines`, so `catmus_draft` and `detector_flags` cannot disagree
with each other or with `ocr_lines`. It still drops empty lines, so a draft
position is still not an ALTO index — which is why a flag now carries the index
outright instead of a position that had to be trusted not to have drifted.

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
from typing import TYPE_CHECKING

from lxml import etree

from .context import norm_ref
from .figures import _bbox, _scale_for

if TYPE_CHECKING:
    import numpy as np

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
#
# **`PAD_X` is wide enough to reveal a clipped folio, and that is what sets it.**
# It was 8, which is a rounding allowance rather than a margin, and the effect was
# that a box strangling its number rendered the number strangled: `1-051`'s
# `sheets/lines-0-1` showed the folio cut in half, on a 21 px box holding a ~70 px
# two-digit number. A reader seeing half a digit does not conclude "the box is
# narrow"; it concludes something is wrong with the page and starts zooming, which
# is where two of three readers in one batch spent six and seven crops apiece.
#
# So the pad covers the worst clipped box the corpus has shown (~20 px) plus the
# whole of the number beyond it plus whitespace either side. The bleed is free in
# the way the last strip and the widened span are free: these pages are set in one
# column with ~500 px of margin, so there is nothing beside a line to bleed *in*.
# 56 also stops just short of costing a strip — a full measure is 3 strips at 2x
# and 7 at 4x padded exactly as it was bare.
PAD_X = 56
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
# **The ceiling is enforced, not advised.** A 300 dpi bitonal scan puts a
# character at ~30 px, so at 4x every ink pixel is already a 4x4 block and there
# is no source detail left to buy — past it a magnifier returns interpolation,
# which is a fact about the resampler rather than about the paper. The prose rule
# has been in the pass doc for months and has been broken repeatedly anyway:
# `2-245` spent ten calls at 6x on a shape question, and the first reader
# dispatched under the queue/claim contract went to 6x nine times and settled a
# laryngeal on one of them. A rule a reader can break is a rule that gets broken,
# and the sibling pass caps its own zoom for exactly this reason.
ZOOM_MAX = 4
# **Two steps, not a range.** A ceiling alone left 1 and 3 legal, and readers used
# them: 3× as a "pragmatic compromise" that is neither the cheap look nor the
# decisive one, and 1× as a contact sheet a contact sheet already gives. Neither
# answers a question the other step does not answer better, so the middle is not a
# judgement to be exercised — it is a place to hesitate, and hesitation here is
# what the zoom counts measure. The batch that produced this rule spent 81 and 59
# zooms on two pages and finished neither, against 7–14 on the three that finished.
ZOOM_STEPS = (2, 4)
ZOOM_CLIENT_W = 1450
ZOOM_OVERLAP = 60
ZOOM_SHEET_H = 1600


def zoom_window(zoom: int, client_w: int = ZOOM_CLIENT_W) -> int:
    """Source px per strip such that `zoom`× of it fills the client width exactly."""
    from .figures import LABEL_W
    return max(40, (client_w - LABEL_W - 20) // max(1, zoom))

def fill_last_strip(a: int, b: int, full: int, window: int,
                    overlap: int = ZOOM_OVERLAP) -> int:
    """Extend `b` so the span's final strip is a whole window, bounded by `full`.

    **A span that wraps used to end short, and the last strip is exactly where
    that hurts.** The widening in `zoom_sheets` fires only when a span is narrower
    than one window, so a *wider* one was cropped flush at `hi` and its tail strip
    carried whatever fraction of a window happened to be left — `@20-60` of a full
    measure lands two strips, the second a third ink and two thirds white.

    The sheet is padded to `client_w` whatever that strip holds, so the text that
    would have completed it costs nothing to include, and withholding it is how a
    reader ends up calling `@55-90` next for the word the boundary cut in half.
    That is the same trade as widening a point, made at the other end of the range,
    and it was found by a reader doing precisely the re-aiming it prevents: `1-046`
    selected every one of its failing zooms by range.

    Only rightward, and only to `full`. Extending left would move a region the
    caller named and can see the label for; running past the line would render
    paper that is not this line's.
    """
    step = max(1, window - overlap)
    n = max(1, -(-max(1, b - a - overlap) // step))
    return min(full, a + step * (n - 1) + window)


def zoom_capacity(widths: list[int], heights: list[int] | None = None,
                  overlap: int = ZOOM_OVERLAP,
                  client_w: int = ZOOM_CLIENT_W,
                  sheet_h: int = ZOOM_SHEET_H) -> list[dict]:
    """What each step costs on *this* page, in strips and in sheets per line.

    A reader choosing a magnification is choosing how much wrapping to accept,
    and until this existed the trade was stated in prose ("higher wraps each line
    into more strips") with the numbers left to intuition — so every reader in the
    batch that prompted this picked the ceiling and none picked the default. The
    figures are the page's own: the measure is the median line width in source
    pixels, because a page of centred headings and a page of full-measure prose
    wrap differently at the same scale and a corpus constant would describe
    neither.

    `full_strips` is what a whole line costs at that step; `point_strips` is what
    `@P` costs. The gap between those two columns is the entire argument for
    naming a point.

    **`point_strips` is not 1.** The obvious guess — a point is one window by
    construction — is wrong, and shipping it would have put a number in front of
    readers that the renderer contradicts on every call: `_snap_to_white` extends
    each edge out to whitespace by up to a quarter-window so no glyph is ever cut,
    so the rendered crop runs to about 1.5 windows and lands on two strips. It is
    derived here the way the renderer derives it, and checked against a real render
    at both steps, because a capacity table that disagrees with the output it
    describes is worse than no table.
    """
    # The measure is the *padded* crop, for the reason the strip height already
    # is one: `line_crops` adds PAD_X either side, and every percentage a caller
    # gives is a share of what was rendered rather than of the ALTO box. Counting
    # the bare box here was a second instance of the same error the strip height
    # once had, and in the same direction — overstating what a call covers.
    measure = (int(sorted(widths)[len(widths) // 2]) + 2 * PAD_X) if widths else 0
    hs = sorted(heights or [])
    line_h = int(hs[len(hs) // 2]) if hs else 0
    out = []
    for z in ZOOM_STEPS:
        window = zoom_window(z, client_w)
        step = max(1, window - overlap)
        full = max(1, -(-max(1, measure - overlap) // step)) if measure else 0
        widened = window + 2 * (window // 4)  # what _snap_to_white can add
        point = max(1, -(-max(1, widened - overlap) // step))
        # **The share of a line one point request comes back with.** This is the
        # number a caller can act on, because percent-of-line is the unit `@LO-HI`
        # is already written in: a reader asking for `@45-65` is asking for 20% of
        # a line that will be widened to this figure anyway, and knowing that in
        # advance is the difference between one crop and three.
        covers = min(100, round(window * 100 / measure)) if measure else 0
        # The strip is the *padded* crop, not the ALTO box — `line_crops` adds
        # PAD_TOP/PAD_BOTTOM so a descender and the mark above a following line are
        # both in the picture. Using the bare box height overstated capacity by
        # three times (13 where the composer fits 4), which is the direction that
        # costs a re-call: a reader told it can batch thirteen doubts and getting
        # four sheets back learns to distrust the table.
        strip_h = (line_h + PAD_TOP + PAD_BOTTOM) * z
        per_sheet = (sheet_h // strip_h) // point if line_h and strip_h else 0
        out.append({"zoom": z, "measure_px": measure, "window_px": window,
                    "full_strips": full, "point_strips": point,
                    "covers_pct": covers, "points_per_sheet": per_sheet})
    return out


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


def _zones_for(ref: str, root: Path = Path(".")) -> list[dict]:
    """This page's declared zones, in raster coordinates, `[]` if never keyed.

    Imported inside the function because `zones` imports `ink_bands`/`ink_mask`
    from this module. Zone geometry is raster geometry by construction — the
    editor draws on the raster and `save_zones` writes what it drew — which is the
    same assumption `page_windows` already makes about the column.
    """
    from .zones import read_zones
    return read_zones(ref, root)


def _fold_corrections(out: list[dict], root: Path | None, ref: str | None,
                      page) -> list[dict]:
    """Append this page's `gt/lines/` corrections to the ALTO's own records.

    The merging lives here rather than in `corrections.py` because it is entirely
    about this structure — it needs `_scale_for`, `_overlap_fraction` and
    `_band_zone`, all of which are geometry over line records. That module owns
    the *store*; this owns what a page's lines are.

    **Indices are assigned after the ALTO's maximum, never interleaved**, which is
    what makes the whole overlay safe: every existing `proposal.json` and
    `decision.json` keyed against this page still names the line it always named.
    Reading position is `reading_order`'s business a few lines below, and it sorts
    the correction into its true place on the page without touching any identity.

    The fragment is stored in **raster** coordinates and the target ALTO may be in
    another space, so the scale is taken per axis from the fragment's own declared
    page size — the same reason `line_crops` derives it instead of assuming: a
    silently mis-scaled box reads as a segmentation error rather than a units one.
    """
    from . import corrections as corr
    if ref is None or page is None:
        return out
    recs = corr.load_lines(ref, root or Path("."))
    if not recs:
        return out

    page_zones = _zones_for(ref, root or Path("."))
    aw, ah = float(page.get("WIDTH") or 0), float(page.get("HEIGHT") or 0)
    for j, r in enumerate(recs):
        rw, rh = r["page_w"] or aw, r["page_h"] or ah
        sx, sy = (rw / aw if aw else 1.0), (rh / ah if ah else 1.0)
        # Containment is asked in raster space, where both the fragment and the
        # zones live; the geometry is scaled into the ALTO's space afterwards.
        band = {"hpos": r["x0"], "vpos": r["y0"],
                "width": r["x1"] - r["x0"], "height": r["y1"] - r["y0"]}
        x, y = round(r["x0"] / sx), round(r["y0"] / sy)
        w, h = round(band["width"] / sx), round(band["height"] / sy)
        out.append({
            "index": len(out) + j,
            "line_id": r["id"],
            "block_id": f"{r['id']}_block",
            "zone": _band_zone(band, page_zones),
            "text": r["text"],
            "hpos": x, "vpos": y, "width": w, "height": h,
            "baseline": f"{x} {y + h} {x + w} {y + h}",
            "points": f"{x} {y} {x + w} {y} {x + w} {y + h} {x} {y + h}",
        })
    return out


def page_lines(alto_path: Path, root: Path | None = None,
               ref: str | None = None) -> list[dict]:
    """One flat record per line, **reading order**, empties included.

    `index` is assigned from ALTO **document order, before the reorder**, and is
    the record's identity: `proposal.json` and `decision.json` are keyed by it and
    `restore` joins on it. Measured over the 20 restored pages, 18 change order
    under a reading-order sort (524 positions in all; `1-101` moves every one of
    its 59), so renumbering would silently mis-map every adjudicated page. Output
    is reordered; identities never move -- which means the labels appear out of
    numeric sequence, and that is the tell that `index` means identity rather than
    position.

    **A page's lines are the store's plus `gt/lines/`'s**, and this is the one
    place that is decided. A correction is a box a human drew over ink the
    segmenter left unboxed; it is appended after the ALTO's last index and carries
    `src: "corr"`, where everything out of the file carries `src: "alto"`. Every
    consumer inherits the merge — the reader's sheets and crops, the review
    server, `proposal check`, `ocr gaps`, `tei context` — because a correction
    nobody downstream can point at is not a correction, it is a note.

    **`ref` is why this parameter exists, and `restore` is why it must.** The ref
    is otherwise derived from `alto_path.stem` below, inside a `try` that degrades
    quietly where the derivation does not hold. `restore` verifies its write by
    comparing `page_lines(src)` against `page_lines(tmp)` — and `tmp` is
    `chukchi-PP-NNN.xml.tmp`, whose stem is `chukchi-PP-NNN.xml` and parses as no
    ref at all. Left to the derivation, one side of that comparison would fold the
    corrections and the other would not, and the mismatch would surface as
    restore's own "the write lost or gained lines" on every corrected page. Pass
    it on both sides or on neither.

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
    A correction's `zone` is resolved differently — by containment against
    `gt/zones/`, since the fragment stores no label — and that is deliberate:
    stored, a label would go stale the moment the page was re-zoned, and the way a
    stranded correction announces itself is by resolving to no zone at all.
    """
    from .figures import _block_label, _labels
    tree = etree.parse(str(alto_path))
    labels = _labels(tree)
    out = []
    for i, tl in enumerate(tree.iter("{*}TextLine")):
        bb = _bbox(tl) or {}
        blk = tl.getparent()
        # Bound once. It used to be `find(...)`ed twice on the same line — once for
        # the guard and once for the value — which parses the XPath and walks the
        # subtree twice for every line in the corpus.
        poly = tl.find("{*}Shape/{*}Polygon")
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
            "points": (poly.get("POINTS") if poly is not None else None),
        })
    for rec in out:
        rec["src"] = "alto"

    # Figure-zone marking needs the page's ref and the repo root. Both are derivable
    # from the ALTO's own location (`<root>/<store>/chukchi-<ref>.xml`) so that every
    # caller gets the marking without having to remember to ask — the failure mode
    # §1 hit, where three consumers each had to opt in to reading order. Where the
    # derivation does not hold (a `--out` path, a tmp_path fixture) no figure ALTO is
    # found and every record carries the keys with `None`, which is exactly right:
    # a page with no figure ALTO has no figure.
    #
    # The corrections fold rides the same derivation, and an explicit `ref` wins
    # over it. Both degrade to "there is nothing to add" rather than raising, and
    # `src` is stamped on every record either way: a caller must never have to tell
    # "this line came from the ALTO" from "this build does not know about
    # corrections".
    at = root if root is not None else alto_path.parent.parent
    try:
        found = norm_ref(ref) if ref else norm_ref(alto_path.stem)
        mark_figure_overlap(out, found, at)
    except ValueError:
        found = None
        for rec in out:
            rec["in_figdesc"] = rec["in_graphic"] = rec["figdesc_straddle"] = None
    if found:
        page = tree.getroot().find(".//{*}Page")
        before = len(out)
        _fold_corrections(out, at, found, page)
        for rec in out[before:]:
            rec["src"] = "corr"
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


def line_box(rec: dict, sx: float, sy: float, size: tuple[int, int]) -> tuple | None:
    """Crop box in raster space for one `page_lines` record, padded and clamped.

    **A line polygon can exclude printed text that belongs to the line**, and what
    it excludes is systematically horizontal: `1-074` prints its list numbers `5.`
    and `9.` outside their boxes, `1-073` does the same with `5.`, and a box
    strangling a folio leaves half the number outside itself. Vertical padding
    cannot reach any of it, which is why `PAD_X` is sized to cover it rather than
    to round off an edge.

    This used to be a `wide` parameter widening the box to the `PrintSpace`, driven
    by a `--margins` flag, and it was the wrong shape twice over. It made the
    ordinary case — a folio you can simply read — conditional on a reader knowing
    to ask; and because the widened crop then spans the whole sheet, every `@P` a
    caller gave was suddenly a percentage of the page rather than of the line, so
    the aim that would have hit the folio was unguessable without probing. Three
    readers in one batch spent six and seven crops each discovering that. The pad
    is unconditional now and there is nothing to ask for.
    """
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


def line_crops(ref: str, alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
               scans: str = "scans"):
    """Yield `(record, PIL.Image)` per line on one page, cropped from the raster.

    `_scale_for` is used rather than assuming the two spaces agree. They do agree
    across the current stores — every page's `Page/@WIDTH|@HEIGHT` matches its
    raster exactly — but the reason the primitive exists (no page is exactly ×2,
    see docs/rasters.md) applies the moment anything is re-rendered, and a silently
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

    for rec in page_lines(alto, root, ref=ref):
        box = line_box(rec, sx, sy, img.size)
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
# Ascenders and descenders overshoot a line's own box routinely (harness/README.md: a line
# polygon can exclude printed text), and without the slack every page reports its
# own lines back as gaps.
COVER_PAD = 6


def ink_mask(src) -> np.ndarray:
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


# How far apart two columns of ink can sit and still be one thing. Inter-word
# spaces run ~25 px at 300 dpi, so a text line holds together; `1-037`'s running
# title ends 514 px short of its folio, so apparatus separates from text without
# either being named. Only the ink decides.
COLUMN_GAP = 80


def _runs(mask, gap: int = 0) -> list[tuple[int, int]]:
    """`(start, end)` of each True run in a 1-D mask, bridging gaps of `<= gap`.

    One diff over the mask, padded either end so a run touching the edge is not
    lost — the same trick the row scan used before this took a second axis.
    """
    import numpy as np
    m = np.asarray(mask, dtype=bool)
    if gap:
        # Bridge first, then find runs: a hole shorter than `gap` is filled by
        # checking whether any True lies within `gap` on both sides.
        idx = np.flatnonzero(m)
        if not len(idx):
            return []
        holes = np.diff(idx)
        for a, d in zip(idx[:-1], holes, strict=True):
            if 1 < d <= gap:
                m[a:a + d] = True
    edges = np.flatnonzero(np.diff(np.concatenate(
        ([0], m.view(np.int8), [0]))))
    return [(int(s), int(e)) for s, e in zip(edges[::2], edges[1::2], strict=True)]


def ink_bands(ink, x0: int, x1: int, covered,
              min_h: int = MIN_BAND_H,
              fraction: float = ROW_INK_FRACTION) -> list[dict]:
    """Contiguous bands of ink in the `x0..x1` window that `covered` does not mask.

    The measuring core of `line_gaps`, extracted because `zones.validate_page` asks
    the same question of a page with different boxes drawn on it — "is there ink
    here that nothing accounts for?" — and two implementations of one threshold is
    how the answers start disagreeing. `MIN_BAND_H` and `ROW_INK_FRACTION` are
    derived at their definitions above and both callers inherit the derivation.

    `ink` is an `ink_mask` array. `covered` is **either** one entry per image row,
    true where something accounts for the whole of that row, **or** a full `(h, w)`
    mask of what the boxes actually cover. Returns `{vpos, height, hpos, width}` in
    **raster** coordinates, each band carrying the extent of its own ink rather
    than of the measuring window — a repair needs the geometry of what was found,
    not of where it was looked for.

    **The two shapes are not the same question, and the difference is a whole
    class of miss.** A row mask can only find text the segmenter dropped
    *vertically*: anything sharing rows with an accounted-for line is masked by
    that line, across the full width. So a folio beside a running title, a list
    number in the margin, a stranded catchword — text missed *horizontally* inside
    a row that is otherwise fine — is invisible by construction. That is exactly
    where this book's marginal apparatus sits: `1-073` strands its folio outside
    every box on the page, `1-074` prints `5.` and `9.` outside theirs, and
    `1-037`'s folio is inside the running-title zone and outside the title line.
    `ocr blot` paints boxes and has always shown these plainly, while claiming in
    its own docstring to be "the inverse of `line_gaps`" — a check on a detector,
    described as equivalent to it, that was never asking the same question.

    **`fraction` is a share of the thing measured, not of the window.** Once
    coverage is box-shaped the leftover ink is unaccounted for by construction, and
    a row projection across the whole window then asks the wrong question: a
    two-character folio is 43 px of ink in a 1,778 px column, so a bar set at
    0.5% of the column (8 ink columns) cuts through the middle of the digits,
    where the thin strokes of a `1` and a `7` carry seven. `1-037`'s folio profiles
    as `27 28 26 21 21 10 10 8 8 8 8 7 7 7 7 7 7 9 8 9 15 17 15 4 5 …` — thirty-six
    rows of type, of which the longest run clearing the bar is eleven, against a
    `MIN_BAND_H` of twenty. Every constant here was calibrated on a full text line
    and silently assumed one.

    So the ink is grouped into its own **columns** first, and each group is
    measured against its own width. A dropped body line is one group spanning the
    column and reads exactly as it always did; a folio is a 43 px group with a bar
    of one. `COLUMN_GAP` is what holds a line together — inter-word spaces run
    ~25 px at 300 dpi, while `1-037`'s title ends 514 px short of its folio — so
    the grouping separates apparatus from text without being told where either is.
    That also removes a boundary: searching the margins as separate strips split
    any band straddling the column edge into two bands at an arbitrary column.

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
    if x1 - x0 <= 0:
        return []
    # Coverage is subtracted from the ink, not from the row index. With a row mask
    # the two are the same thing; with a box mask a row keeps whatever ink no box
    # accounts for, which is the point.
    cov = np.asarray(covered, dtype=bool)
    cov = cov[:h, None] if cov.ndim == 1 else cov[:h, x0:x1]
    band = ink[:, x0:x1] & ~cov

    out = []
    # Row runs first, on *any* leftover ink, so a group is looked for only where
    # something survives the mask. The bar is applied inside the group, never here.
    for r0, r1 in _runs(band.any(axis=1)):
        if r1 - r0 < min_h:
            continue
        sub = band[r0:r1]
        for c0, c1 in _runs(sub.any(axis=0), gap=COLUMN_GAP):
            region = sub[:, c0:c1]
            threshold = max(1, int((c1 - c0) * fraction))
            rows = (region[:, ::2].sum(axis=1) * 2 >= threshold)
            for s, e in _runs(rows):
                if e - s < min_h:
                    continue
                nz = np.flatnonzero(region[s:e].any(axis=0))
                if not len(nz):
                    continue
                out.append({"vpos": int(r0 + s), "height": int(e - s),
                            "hpos": x0 + c0 + int(nz[0]),
                            "width": int(nz[-1] - nz[0]) + 1})
    return sorted(out, key=lambda b: (b["vpos"], b["hpos"]))


def annexed_bands(ref: str, root: Path = Path(".")) -> dict[int, list[dict]]:
    """Per line index, the ruled bands a human has said that line's box is short of.

    **The marker has to reach the line, not just the band.** A `covered_by` ruling
    is read off `ocr gaps`, but a reader keys from `ocr lines` and crops from
    `ocr sheets`/`ocr zoom` — all of which showed the line and said nothing, so the
    one place the ruling mattered was the one place it was invisible. Worse, the
    reading contract tells a reader that an `exempted: true` band is settled and to
    spend no image on it, which is right for `not_type` and precisely inverted for
    this: the ruling says *this line's box does not hold all its ink*, which is an
    instruction to look wider at that line.

    `1-073` is the worked case. Line 1's box is 11 px and holds `5`; the page
    prints `51`. Its reader recovered the second digit from the under-30px
    strangulation heuristic alone, before any ruling existed — so the correct
    reading came from a rule of thumb while a human's explicit statement of the
    same fact sat unread in the ledger.
    """
    ref = norm_ref(ref)
    from . import corrections as corr
    out: dict[int, list[dict]] = {}
    for r in corr.load_ink_exempt(root).get(ref, []):
        if r.get("covered_by") is None:
            continue
        out.setdefault(int(r["covered_by"]), []).append(r)
    return out


def covered_faults(ref: str, alto_dir: str = DEFAULT_ALTO_DIR,
                   root: Path = Path(".")) -> list[dict]:
    """`covered_by` rulings whose named line does not bear them out.

    **This is the half "not type" could never have.** A ruling that ink is not
    printing is unfalsifiable from inside the harness — the only witness is the
    paper, and re-reading it is a human act the firewall reserves. A ruling that
    ink is *covered by line N* names something the store can be asked about, so
    it is checkable for free, and the check is worth more than the field:

    - **`no_line`** — N is not in the store. The ruling points at nothing, and a
      band was suppressed on the authority of a line that does not exist.
    - **`empty_line`** — N is there and its `text` is empty. The ink was ruled
      already-keyed by a line that keys nothing, so the reading really is missing
      and the exemption is hiding exactly what it claims to account for.

    What it deliberately cannot check is whether N's text is the *right* text —
    that is a reading, and reading is not this function's rank. It catches the
    structural lie, which is the one that recurs: `1-073`'s folio was strangled to
    11 px and its line held `5` where the page prints `51`, so a `covered` ruling
    over that band would have been true of a line whose text was half the number.
    `empty_line` does not reach that case; the strangulation rule in the reader
    contract does.
    """
    ref = norm_ref(ref)
    from . import corrections as corr
    regions = [r for r in corr.load_ink_exempt(root).get(ref, [])
               if r.get("covered_by") is not None]
    if not regions:
        return []
    alto = alto_for_lines(ref, alto_dir, root)
    if not alto.exists():
        return []          # absent is not wrong — see `_orphan_line_issues`
    by_index = {int(r["index"]): r for r in page_lines(alto, root)}
    out = []
    for r in regions:
        idx = int(r["covered_by"])
        line = by_index.get(idx)
        if line is None:
            fault, detail = "no_line", f"store holds {len(by_index)} lines"
        elif not (line.get("text") or "").strip():
            fault, detail = "empty_line", "the named line keys nothing"
        else:
            continue
        out.append({"ref": ref, "y0": r["y0"], "y1": r["y1"],
                    "covered_by": idx, "fault": fault,
                    "note": r.get("note", ""), "detail": detail})
    return out


def line_gaps(ref: str, alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
              scans: str = "scans") -> list[dict]:
    """Bands of ink on the page that no `TextLine` covers — dropped lines.

    The segmentation this corpus was built from **drops whole printed lines**, and
    nothing detected it. `gt/fig/` had its lines stripped for exactly this reason
    (docs/decisions.md, "Dropped lines"), and `1-053` reached restored ground truth missing two lines of
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

    **A band a human already ruled carries that ruling.** `gt/zones/_ink_exempt.json`
    is where the zoning pass records a band as not type — a smudge, a gutter blob,
    offset from the facing page — and until this read it, the ruling reached `zones
    check --ink` and the zone editor and stopped there. A reader on the OCR side got
    the band bare and re-adjudicated it from the raster, which is the one thing the
    firewall does not permit a model to do: rank rises by a human act, and a band
    returned unmarked invites a second, lesser witness to re-originate the call.
    Three pages in the `1-031`..`1-036` batch were marked "scanner artifact" during
    zoning and re-argued from scratch anyway.

    **Flagged, never suppressed** — the same rule `zones.validate_page` follows for
    the same file. A matched band still reports, carrying `exempted` and the note
    that ruled it; dropping it would make this the one place a wrong call could
    hide, and the next genuinely dropped line on that page with it.
    """
    from PIL import Image
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    page = etree.parse(str(alto)).find(".//{*}Page")
    img = Image.open(raster_path(ref, root, scans)).convert("L")
    w, h = img.size
    # Both scales are wanted now that coverage is a box rather than a row band;
    # the horizontal *window* still comes from the measured column, which is in
    # raster coordinates already.
    sx, sy = _scale_for(page, img.size)

    # **Rooted and named, both.** Left to the path derivation this resolves the
    # corrections store against `<alto>/../..`, which is `<root>/gt` for a
    # `gt/ocr` page — a directory that never holds one, so the fold found nothing
    # and every corrected band went on reporting as though nobody had touched it.
    # The detector claiming a line is missing *because* it could not see the box
    # somebody drew for it is the exact failure this pass exists to end.
    recs = page_lines(alto, root, ref=ref)
    # Column window from the page's own lines, so the margins (and the scanner's
    # dark gutter) never register as ink. Falls back to the full width if a page
    # somehow has no geometry to measure.
    # The measured column anchor, which is what `zones.uncovered_ink` bounds itself
    # by — so the two detectors ask the same question of the same strip of paper.
    # They did not before: this took the extent of the segmenter's own boxes, which
    # is circular for a detector whose subject is a box the segmenter failed to
    # produce, and disagreed with the zone-level window on 38 of 62 page/store
    # pairs, in both directions (right edge -11..+35 px). The practical cost was
    # that a band only this side could see had no route into `_ink_exempt.json` at
    # all, since the editor only offers what the zone check finds — `1-034`.
    #
    # `img` is handed over so the measure reuses this decode instead of doing its
    # own; the decode is the whole cost of the check. Costs ~13 ms a page anyway
    # (2.02 s -> 2.50 s over 38 pages serially), which buys the agreement.
    #
    # It does couple this to `data/zones_config.json`. The anchor's sparse-page
    # fallback is not a risk it inherits, though: a page reaches an OCR store only
    # through `ocr predict`, which runs from the zones, so a leaf blank enough to
    # defeat the measure never gets zones and never gets here — `1-330`, the
    # exempted reverse of a plate, is exactly that page and has neither. Measured
    # rather than assumed: all 43 pages with OCR anchor from their own ink, none
    # fall back.
    from .zones import page_windows as _page_windows
    _wins = _page_windows(ref, root, ink=img)
    col0, col1 = min(int(v["x0"]) for v in _wins), max(int(v["x1"]) for v in _wins)
    col0, col1 = max(0, col0), min(w, col1)

    # **The measure looks at the whole PrintSpace, not just the column.** The
    # column window exists to keep the margins and the scanner's dark gutter from
    # registering as ink, and it does that job — but the marginal apparatus is on
    # the far side of it by definition, which is the same omission `--margins`
    # exists to undo at the crop.
    #
    # Nothing is hidden and nothing is conflated: a band is labelled `column` or
    # `margin` by where its own ink falls, so the dropped-line signal stays
    # legible and marginal apparatus is a separate reading rather than noise in
    # the same column.
    #
    # **The label is not the reason the folios were being missed**, and this
    # comment said it was. It cited `1-037`'s folio as sitting at raster
    # x 2478-2533 outside a column ending at 2224, "so no amount of box-masking
    # could ever have found it". Measured, that band is at x 2157-2200 and reports
    # `where: column`: it is *inside* the column and inside the running title's
    # rows, and outside only its **box**. The box mask one axis over is what
    # finds it. A 29-page sample across the three parts returns one band, also in
    # column — so `margin` is a rare label rather than the common case, and the
    # widened window is cheap insurance, not the fix.
    ps = printspace_x(page)
    p0, p1 = ((max(0, int(ps[0] * sx)), min(w, int(ps[1] * sx))) if ps
              else (0, w))
    p0, p1 = min(p0, col0), max(p1, col1)

    import numpy as np
    # **Boxes, exactly as `ocr blot` paints them.** That verb calls itself the
    # inverse of this one and shows a human what is left after everything
    # accounted for is erased; masking rows here instead made the two disagree
    # about every horizontally-missed line, silently, in the direction of
    # reporting nothing. `1-037`'s folio sits in the running title's rows and
    # outside its box: blotted it is conspicuous, row-masked it does not exist.
    covered = np.zeros((h, w), dtype=bool)

    def _cover(box_x, box_y, box_w, box_h):
        top = max(0, int(box_y * sy) - COVER_PAD)
        bot = min(h, int((box_y + box_h) * sy) + COVER_PAD)
        left = max(0, int(box_x * sx) - COVER_PAD)
        right = min(w, int((box_x + box_w) * sx) + COVER_PAD)
        covered[top:bot, left:right] = True

    for r in recs:
        if r.get("vpos") is None or r.get("height") is None:
            continue
        if r.get("hpos") is None or r.get("width") is None:
            # No horizontal extent to trust, so fall back to the old reading of
            # this line: it accounts for its whole row band. Under-reporting a
            # band is the safe direction when the geometry is the thing missing.
            top = max(0, int(r["vpos"] * sy) - COVER_PAD)
            bot = min(h, int((r["vpos"] + r["height"]) * sy) + COVER_PAD)
            covered[top:bot, :] = True
            continue
        _cover(r["hpos"], r["vpos"], r["width"], r["height"])

    # Figures are ink with no TextLine by construction, so without this every
    # illustrated page reports its own artwork as dropped text: `2-030` returned 2
    # bands and `3-006` returned 12, all of them graphics. Masking the declared
    # zones takes both to zero, verified per band on both axes. `gt/fig/` covers
    # 252 of 832 pages; on the rest there is nothing to mask and nothing is lost,
    # since a page with no figure ALTO has no figure.
    from .figures import zones as _zones
    for z in _zones(ref, root):
        _cover(z["hpos"], z["vpos"], z["width"], z["height"])

    # The measuring itself is `ink_bands`, shared with `zones.validate_page` so the
    # two detectors cannot drift apart on a threshold.
    #
    # One window over the whole PrintSpace, and the grouping inside `ink_bands`
    # does the rest. Searching the margins as separate strips was the first
    # attempt and it split any band straddling the column edge into two bands at
    # an arbitrary column — a boundary invented by the search rather than found on
    # the page, which is the same fault as the row mask one axis over.
    bands = ink_bands(ink_mask(img), p0, p1, covered)
    for b in bands:
        # Where the band's own ink sits, against the measured text column. A
        # label, never a filter: `margin` is a folio, a list number or a
        # catchword, which is a different question from a dropped body line and
        # wants a different answer — but suppressing it here would rebuild the
        # blind spot one level up.
        b["where"] = ("margin" if b["hpos"] + b["width"] <= col0
                      or b["hpos"] >= col1 else "column")

    # **Which zone the band falls in, if any — and it decides who owns the band.**
    # A page with no zones yields no containment and every band reads out-of-zone.
    # That is the honest degradation rather than a gate: measurement never gates,
    # and it is `ocr edit` that requires zoning, not this.
    page_zones = _zones_for(ref, root)
    for b in bands:
        b["zone"] = _band_zone(b, page_zones)

    # **Two layers, and authority runs downstream only.** Zoning is the first
    # stage of accounting for the ink; recognition is the last, and its job is to
    # account for *all* of it — `ocr blot` over a finished page should leave a
    # blank leaf. So the line layer settles any band, in a zone or not, while the
    # zone layer settles only what is already outside every zone.
    #
    # The asymmetry is the whole point. Upstream must not answer a downstream
    # question: one file used to serve both, so a band ruled "scanner smudge"
    # while zoning also stopped this check from ever reporting that strip of paper
    # again — a claim about what the *zoning* need not cover, silently answering
    # whether a line was dropped. That direction stays shut.
    #
    # Routing by zone in *both* directions was the over-correction, and it left
    # bands no editor could reach. `1-034`'s two sit beside a zone rather than
    # below it, so `line_gaps` sees them (it masks by box) and `zones check --ink`
    # does not (it masks by row) — `ocr edit` refused them as out-of-zone and
    # `zones edit` never offered them at all. Two rulings were written for them
    # and were inert, with nothing saying so.
    #
    # **Flagged, never suppressed**, whichever layer speaks: a matched band still
    # reports, carrying `exempted`, the note that ruled it, and the `layer` that
    # did. Dropping it would make this the one place a wrong call could hide, and
    # the next genuinely dropped line on that page with it.
    from . import corrections as corr
    from .zones import load_ink_exempt as _zone_exempt
    by_layer = {"lines": corr.load_ink_exempt(root).get(ref, []),
                "zones": _zone_exempt(root).get(ref, [])}
    # **`reason` says which of the two dispositions ruled it**, because "exempted"
    # alone made one word carry both — and a reader handed a bare `exempted: true`
    # plus free text had to infer from prose whether the ink was type. `covered`
    # names the line whose box strangled it, so the band is answered rather than
    # dismissed; `not_type` is the original claim, unchanged.
    for b in bands:
        excuse, layer = corr.ink_excuse(b, by_layer["lines"]), "lines"
        if excuse is None and not b["zone"]:
            excuse, layer = corr.ink_excuse(b, by_layer["zones"]), "zones"
        b["exempted"] = bool(excuse)
        b["note"] = excuse["note"] if excuse else ""
        b["layer"] = layer if excuse else ""
        covered = excuse.get("covered_by") if excuse else None
        b["reason"] = ("covered" if covered is not None
                       else "not_type" if excuse else "")
        b["covered_by"] = covered if covered is not None else ""
    return bands


# A band more than half inside a zone is that zone's business. Below it the ink
# is mostly outside every region, which is the zoning's question rather than this
# one — and a band merely clipping a zone's edge is not a line in it.
ZONE_INSIDE = 0.5


def _band_zone(band: dict, zones: list[dict]) -> str:
    """The label of the zone this band is in, or `""` for none.

    Largest overlap wins, and it must clear `ZONE_INSIDE`. Both axes, for the
    reason `_overlap_fraction` gives: a Y-only test hands every marginal mark to
    whatever body zone happens to share its rows.
    """
    best, share = "", 0.0
    for z in zones:
        box = {"hpos": z["x0"], "vpos": z["y0"],
               "width": z["x1"] - z["x0"], "height": z["y1"] - z["y0"]}
        f = _overlap_fraction(band, box)
        if f > share:
            best, share = z["label"], f
    return best if share >= ZONE_INSIDE else ""


def write_blot(ref: str, out_dir: Path, alto_dir: str = DEFAULT_ALTO_DIR,
               root: Path = Path("."), scans: str = "scans",
               exemptions: bool = True) -> dict:
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

    **`exemptions` is on by default, because the standard this verb measures
    against is a blank leaf.** Accounting for the page's ink is what the
    recognition stage is *for*: zoning is the first pass at it, this is the last,
    and a finished page has nothing left that is not a line, a figure or a ruling.
    Painting all three makes the finished state legible as blank rather than as
    "blank apart from the marks you have to remember are ruled".

    It was off for most of this verb's life, on the argument that a bare page is
    the one view answering independently of anybody's judgement, and that with
    rulings painted a wrong one hides ink here too. That is true and it is why
    `--no-exemptions` still exists — but it argued for the wrong default, because
    a view whose success condition is "blank except for some things" cannot be
    read at a glance, which was the whole point of a picture over a threshold.

    **A finished page is near-blank, not perfectly blank, and that is fine.**
    Scanner speckle survives, and so does the odd printed rule; the eye discounts
    both at a glance and a threshold cannot. Which is the argument against
    scoring the leftovers: the picture is for a human to look at, and a residual
    count would turn a page that is plainly done into a number needing
    interpretation.

    Both layers are painted, since both are ink somebody settled.

    They are painted **full width**, which looks careless and is not: a ruling is
    a `y` band with no `x` extent, and `corrections.ink_excuse` matches on the
    band's midpoint alone — so full width is exactly the reach the ruling already
    has in the check this illustrates. Drawing it narrower would show a coverage
    the matcher does not honour.
    """
    from PIL import Image, ImageDraw

    from .figures import zones as _zones
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    page = etree.parse(str(alto)).find(".//{*}Page")
    img = Image.open(raster_path(ref, root, scans)).convert("RGB")
    sx, sy = _scale_for(page, img.size)
    d = ImageDraw.Draw(img)

    n_lines = n_zones = n_exempt = 0
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
    if exemptions:
        from . import corrections as corr
        from .zones import load_ink_exempt as _zone_exempt
        w = img.size[0]
        for regions in (corr.load_ink_exempt(root).get(ref, []),
                        _zone_exempt(root).get(ref, [])):
            for r in regions:
                # Rulings are recorded in raster coordinates, like the bands they
                # answer — no `sy` here, unlike the ALTO geometry above.
                d.rectangle([0, r["y0"], w, r["y1"]], fill=(255, 232, 189))
                n_exempt += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"chukchi-{ref}.png"
    img.save(path)
    return {"ref": ref, "path": str(path), "lines_blotted": n_lines,
            "zones_blotted": n_zones, "exempt_blotted": n_exempt}


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


def figure_boxes(ref: str, root: Path, size: tuple[int, int]) -> list[tuple]:
    """This page's `gt/fig/` zones as `(x0, y0, x1, y1)` in raster space.

    The one place the figure geometry is turned into raster coordinates, so the
    blot, the dropped-line detector and the numbered page all agree about where a
    figure is rather than each scaling it again. Empty for the 580 pages with no
    figure ALTO — which is information, not a gap: the figure track is complete at
    252 pages, so absence means the page has none.

    Per-page and per-axis, as everywhere else here: no page in this corpus is a
    clean x2 of its 150 dpi predecessor, so assuming 1.0 is the same class of error
    the ratio exists to avoid.
    """
    from .figures import zones as _zones
    zs = _zones(ref, root)
    if not zs:
        return []
    alto = _figure_alto_page(ref, root)
    sx, sy = _scale_for(alto, size) if alto is not None else (1.0, 1.0)
    return [(z["hpos"] * sx, z["vpos"] * sy,
             (z["hpos"] + z["width"]) * sx, (z["vpos"] + z["height"]) * sy)
            for z in zs]


# **The whole page, with each line's `index` drawn beside it.** The reading pass's
# first image and, on an English-only page, its only one.
#
# Why it exists is an arithmetic fact about how an image is delivered rather than a
# preference. A model sees an image as 28x28 patches — `ceil(w/28) * ceil(h/28)`
# visual tokens — and anything over the per-image ceiling is downscaled until it
# fits. At the current ceiling (2576 px long edge, 4784 tokens) a 2550x3525 page
# arrives at about 0.64x whatever is sent, so a page composite costs ~4.8k tokens
# and **cannot be made sharper by sending more pixels**. Three contact sheets over
# the same page cost ~14k and are the mandated first read. Most pages are English
# prose that never needs a crop, so the ladder is: this image, then `ocr sheets
# --only` for the lines it leaves in doubt, then `ocr zoom --only` for the marks
# those leave in doubt. Each rung is paid for only where it is used.
#
# Three consequences for the drawing, and each was got wrong once first.
#
# **The label sits immediately left of its own line**, not out at the page edge. The
# scan carries 250-350 px of its own margin, so a label parked in the added gutter
# ends up a third of a thousand pixels from the type it names, and the reader has to
# carry the association across that gap. The gutter still exists, but as *headroom*
# for a line that starts near x=0 rather than as the place labels live.
#
# **Serif, not the mono the contact sheets use.** These labels are read at ~0.6x
# after delivery, and at that size a sans `1` is a bare stroke — the same shape as
# `l` and near enough `7` — where a serifed one is unambiguous. The sheets can stay
# mono because nothing resizes them.
#
# **Sized for the delivered image, not this one.** At 0.64x a 26 px label — the
# sheets' size — arrives at 17 px and is a guess; 48 px arrives at ~31 px and is
# read. Bigger than that was tried and is merely loud: it competes with the type.
NUMBER_GUTTER = 110
NUMBER_FONT = 36
NUMBER_PAD = 26
NUMBER_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

# The placard a masked figure carries. Mid-grey with near-white lettering, which
# reads as a deliberate placement rather than as blank paper or as artwork — the
# two things it must not be mistaken for. Sized to the box at render time: a plate
# gets it large, an inset gets it small, and a box too small for even the floor
# keeps the grey alone, which still says "something was here" where white did not.
FIG_FILL, FIG_INK = 140, 246
FIG_TITLE, FIG_SUB = "BLOTTED FIGURE", "DO NOT TRANSCRIBE"
FIG_TITLE_MIN, FIG_TITLE_MAX = 16, 220
FIG_SUB_RATIO = 0.55


def write_numbered_page(ref: str, out_path: Path, alto_dir: str = DEFAULT_ALTO_DIR,
                        root: Path = Path("."), scans: str = "scans",
                        gutter: int = NUMBER_GUTTER,
                        font_size: int = NUMBER_FONT) -> dict:
    """The page raster with every line's ALTO `index` drawn in a left gutter.

    The label is the `page_lines` **index**, the same identity `ocr sheets`,
    `ocr zoom --only`, `proposal.json` and `restore` all join on — never a position
    in reading order. So the numbers are legitimately not consecutive down the page
    (18 of the 20 restored pages reorder, `1-101` all 59 of them), and that is the
    tell described in docs/segmentation.md rather than a fault in this image.

    **The page is banded, not annotated** — the same idiom `compose_sheets` uses,
    a horizontal rule between neighbours and the number inside its own band, so a
    label's *extent* says which line it belongs to and nothing has to be inferred
    from how close it sits. The alternative tried first was a label per line nudged
    clear of its neighbour with a hairline drawn back to the line it named; a page
    of those reads as ruling rather than as pointing, and buries the page under it.

    Where two lines share a band — a two-column setting, rare here, but `1-101` sets
    twelve such rows and `3-005` six — each gets its own label immediately left of
    its own column, and the divider goes **between the two columns where they
    actually part on the paper**, not at a share of the gutter. A divider at an x
    that means nothing is worse than none: it rules through type and implies a
    boundary the page does not have.
    """
    from PIL import Image, ImageDraw, ImageFont
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    page = etree.parse(str(alto)).find(".//{*}Page")
    src = Image.open(raster_path(ref, root, scans)).convert("L")
    sx, sy = _scale_for(page, src.size)

    canvas = Image.new("L", (src.width + gutter, src.height), 255)
    canvas.paste(src, (gutter, 0))
    size = src.size
    src.close()
    draw = ImageDraw.Draw(canvas)

    # **Figures come out, exactly as they do for the segmenter.** Same geometry the
    # `scans/w-figs-blotted/` farm holds and the same white, computed here per page
    # so a per-page verb does not depend on a corpus-wide farm build. Two reasons it
    # belongs on this image specifically: a plate eats most of the token budget of a
    # composite that is already delivered at ~0.6x, and its artwork raises baselines
    # the reader would then have to be told to ignore. The declared box and not a
    # pixel more — body text sits hard against an inset figure on `1-283`.
    # **And they say so where they were.** Painted out and left blank, the figure
    # is a void the reader has to explain to itself: `2-030`'s reader met a huge
    # vertical gap between two consecutive indices, reasoned its way to "masked
    # figure" from `gt/fig/` existing and `ocr gaps` coming back empty, and wrote
    # a memory note about it — three steps and a raster read to recover something
    # this image already knew and had thrown away. An erasure that does not say
    # what it erased is indistinguishable from blank paper, which on a page whose
    # whole question is *what is missing here* is the wrong thing to be
    # indistinguishable from. Outline and label, in the same grey as the banding,
    # so the void is self-describing and costs no artwork.
    fonts: dict[int, object] = {}

    def at(size: int):
        if size not in fonts:
            try:
                fonts[size] = ImageFont.truetype(NUMBER_FONT_PATH, size)
            except OSError:
                fonts[size] = ImageFont.load_default()
        return fonts[size]

    figs = [(x0 + gutter, y0, x1 + gutter, y1)
            for x0, y0, x1, y1 in figure_boxes(ref, root, size)]
    for box in figs:
        draw.rectangle(box, fill=FIG_FILL)
        # `figure_boxes` scales into raster space and returns floats; `range`
        # below needs integers.
        bw, bh = int(box[2] - box[0]), int(box[3] - box[1])
        # Largest type that fits both lines inside the box. Stepping down rather
        # than solving for it because the metric is the font's, not a formula's —
        # and a placard that overflowed its own box would sit on the body text
        # beside an inset figure, which is the one thing worse than no placard.
        for ts in range(min(FIG_TITLE_MAX, bh // 3), FIG_TITLE_MIN - 1, -4):
            ss = max(FIG_TITLE_MIN, int(ts * FIG_SUB_RATIO))
            tf, sf = at(ts), at(ss)
            tw = draw.textlength(FIG_TITLE, font=tf)
            sw = draw.textlength(FIG_SUB, font=sf)
            gap = ts // 5
            if max(tw, sw) > bw - 24 or ts + gap + ss > bh - 16:
                continue
            y = (box[1] + box[3]) / 2 - (ts + gap + ss) / 2
            draw.text((box[0] + (bw - tw) / 2, y), FIG_TITLE, fill=FIG_INK,
                      font=tf)
            draw.text((box[0] + (bw - sw) / 2, y + ts + gap), FIG_SUB,
                      fill=FIG_INK, font=sf)
            break

    rows, dropped = [], 0
    for rec in page_lines(alto, root):
        if rec.get("vpos") is None or rec.get("height") is None:
            continue
        top, h = rec["vpos"] * sy, rec["height"] * sy
        x0 = (rec["hpos"] or 0) * sx if rec.get("hpos") is not None else 0.0
        x1 = x0 + (rec["width"] or 0) * sx if rec.get("width") is not None else x0
        x0, x1 = gutter + x0, gutter + x1
        # A line whose centre is inside a blotted zone is now numbering blank paper,
        # so it goes. Centre rather than any-overlap: a caption or a body line that
        # merely abuts a figure keeps its number, and only a line the blot actually
        # erased loses one. The line is still in the ALTO and still has its index —
        # `ocr lines` reports it, `sheets --only` will render it. This image just
        # does not point at it.
        if any(a <= (x0 + x1) / 2 <= c and b <= top + h / 2 <= d
               for a, b, c, d in figs):
            dropped += 1
            continue
        rows.append((top, top + h, x0, x1, rec["index"]))
    rows.sort(key=lambda r: (r[0] + r[1], r[2]))
    if not rows:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path)
        return {"ref": ref, "path": str(out_path), "lines": 0, "bands": 0,
                "in_figures": dropped, "size": f"{canvas.width}x{canvas.height}"}

    # **Two lines share a band only when they are set side by side**, and the test
    # has to be a *share* of the line's height rather than any overlap at all.
    # Consecutive lines of ordinary prose already overlap by a few px — box bounds
    # follow ascenders and descenders, which interleave — so "overlaps at all" put
    # 45 lines of `2-031` into 24 bands and 68 of `3-005` into 8, merging exactly
    # the neighbours that must stay apart.
    BAND_OVERLAP = 0.6
    bands: list[list[tuple]] = []
    for row in rows:
        if bands:
            top = min(r[0] for r in bands[-1])
            bottom = max(r[1] for r in bands[-1])
            share = min(bottom, row[1]) - max(top, row[0])
            if share >= BAND_OVERLAP * min(bottom - top, row[1] - row[0]):
                bands[-1].append(row)
                continue
        bands.append([row])

    # The drawn band is not the line's own extent but a **partition of the page's
    # height**, each boundary the midpoint between neighbouring line centres. A
    # partition is what makes the rules read as the contact sheets' rules do —
    # contiguous, no gaps, no overlaps — and it removes the last way a label could
    # sit ambiguously between two lines.
    mids = [(min(r[0] for r in b) + max(r[1] for r in b)) / 2 for b in bands]
    edges = [0.0]
    edges += [(mids[i] + mids[i + 1]) / 2 for i in range(len(mids) - 1)]
    edges.append(float(canvas.height))

    # **Where the number column sits is measured off the page, not off the canvas.**
    # Right-aligning to the added gutter puts it hard against the canvas edge and
    # therefore 150-250 px from the type, because the scan carries its own margin;
    # right-aligning to each line instead makes the column wander with every indent.
    # So: take the left edge of every line, cull the ones far from the median —
    # centred headings, indented list items, a paragraph's first line — and average
    # what is left. That is the body's own left edge, and the numbers sit just
    # inside it. Median-absolute-deviation rather than a fixed tolerance, with a
    # floor, so it behaves on a page whose lines all start at exactly one x (where
    # the deviation is 0) and on one set raggedly.
    lefts = sorted(r[2] for r in rows)
    med = lefts[len(lefts) // 2]
    devs = sorted(abs(x - med) for x in lefts)
    mad = devs[len(devs) // 2]
    kept = [x for x in lefts if abs(x - med) <= max(40.0, 3 * mad)]
    anchor = sum(kept) / len(kept)

    n = 0
    for i, band in enumerate(bands):
        top, bottom = edges[i], edges[i + 1]
        cols = sorted(band, key=lambda r: r[2])
        # **Every band's first number joins the measured column; only the second and
        # later in a split band sit against their own line.** One axis is scanned far
        # faster than numbers that wander with each line's indent, and the page sets
        # plenty of those — so the column is the default and the leftmost line of a
        # two-column row belongs in it like any other. Position only has to carry
        # information for the columns *after* the first, where which number belongs
        # to which is not otherwise recoverable.
        for k, (r_top, r_bottom, x0, _, index) in enumerate(cols):
            label, sz = str(index), font_size
            if k == 0:
                # The measured anchor, but never right of this line's own start.
                # A page mixing a two-column block with body prose pulls the mean
                # right of the narrowest lines, and an un-clamped column then prints
                # its number over the first letter of every one of them — which is
                # both unreadable and a corruption of the thing being read. Clamping
                # costs a slightly ragged column on those lines and nothing else.
                left, at_x = 0.0, min(anchor, x0)
            else:
                left, at_x = cols[k - 1][3], x0
            avail = at_x - left - NUMBER_PAD
            while sz > 14 and draw.textlength(label, font=at(sz)) > avail:
                sz -= 4
            f = at(sz)
            w = draw.textlength(label, font=f)
            draw.text((max(2.0, at_x - NUMBER_PAD - w),
                       (r_top + r_bottom) / 2 - sz * 0.68), label, fill=0, font=f)
            n += 1
        # **The rule crosses the whole page, not just the gutter.** A rule that
        # stops at the gutter edge asks the reader to extend it across 2500 px of
        # type by eye to find out which line the number belongs to, and that is a
        # thing readers get wrong — the band has to physically enclose its line.
        # Drawn light and thin, and on the midpoint between line centres, so it
        # lands in the leading; a descender it clips is still legible under it,
        # where a dark rule would take the glyph.
        if i:
            draw.line([(0, top), (canvas.width, top)], fill=185, width=2)
        # Between the columns where they actually part, not at a share of the
        # gutter: a divider at an arbitrary x rules through type and asserts a
        # boundary the page does not have. Its *extent* is the lines' own, not the
        # band's — the first and last bands run to the canvas edges, so a divider
        # drawn to the partition edge trails hundreds of px up through blank paper
        # and reads as a page-long column rule that separates nothing.
        d_top = min(r[0] for r in cols) - NUMBER_PAD
        d_bottom = max(r[1] for r in cols) + NUMBER_PAD
        for k in range(1, len(cols)):
            xd = (cols[k - 1][3] + cols[k][2]) / 2
            draw.line([(xd, d_top), (xd, d_bottom)], fill=170, width=2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return {"ref": ref, "path": str(out_path), "lines": n, "bands": len(bands),
            "in_figures": dropped, "size": f"{canvas.width}x{canvas.height}"}


# **Sized so a full sheet is never resampled on delivery.** An image costs
# `ceil(w/28) * ceil(h/28)` visual tokens and anything over the 4784 ceiling is
# downscaled to fit. A full-measure sheet is ~1900 px wide, i.e. 68 patches, so the
# height budget is `4784 / 68 = 70` patches — 1960 px. At the old 2000 the tallest
# sheets came to 4896 and were fitted down by about 1%, which is small but is
# exactly the resample `write_line_sheets` refuses to do locally and for the reason
# it refuses: the question being asked of these images is whether a dot sits under a
# `g`. Rounded down to a whole patch row.
LINE_SHEET_H = 1960


def write_line_sheets(ref: str, out_dir: Path, alto_dir: str = DEFAULT_ALTO_DIR,
                      root: Path = Path("."), scans: str = "scans",
                      per_sheet: int = 8,
                      sheet_h: int | None = LINE_SHEET_H,
                      only: set[int] | None = None) -> list[dict]:
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

    `only` restricts the sheet to named line indices, which is what makes this the
    middle rung of the ladder rather than an all-or-nothing first read: a full page's
    sheets cost about three times the numbered page composite, and a reader that has
    already read that composite wants a closer look at the four lines it left open,
    not at all forty. Selecting a *range* around a doubtful line is the usual form —
    neighbours are what settle whether a mark is the page's habit or this line's.
    An index that is not on the page raises, as in `write_line_zoom`: a silently
    dropped selection is a line reported as looked at that was never rendered.
    """
    from .figures import LABEL_W, compose_sheets
    items, seen = [], []
    for rec, crop in line_crops(ref, alto_dir, root, scans):
        if only is not None and rec["index"] not in only:
            continue
        seen.append(rec["index"])
        items.append((str(rec["index"]), crop))
    if only:
        for missing in sorted(set(only) - set(seen)):
            raise ValueError(f"{norm_ref(ref)}: line {missing} is not on the page "
                             "(or has no usable geometry)")
    if not items:
        return []
    width = max(im.width for _, im in items) + LABEL_W + 20
    sheets, index = compose_sheets(items, out_dir,
                                  per_sheet=per_sheet,
                                  name_for=sheet_namer("lines"),
                                  sheet_w=width, max_h=sheet_h)
    # One flat record per sheet, `lines` as a joined string rather than a list:
    # a nested value de-tabularizes the whole TOON table (see the module docstring).
    return [{"sheet": str(out_dir / e["sheet"]),
             "lines": " ".join(e["items"])} for e in index]


def compact_runs(xs) -> str:
    """`{11,12,13,15}` -> `"11-13_15"`. Canonical over the set, not its spelling."""
    xs, parts, i = sorted(set(xs)), [], 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        parts.append(str(xs[i]) if i == j else f"{xs[i]}-{xs[j]}")
        i = j + 1
    return "_".join(parts)


def sheet_namer(base: str, smooth: bool = False, limit: int = 44):
    """A `compose_sheets` namer: each sheet named for the lines it actually holds.

    **Two renderings that differ must not write the same filename, and two that
    agree must.** Sequential numbering satisfies neither. `zoom` and `sheets`
    numbered their output `<base>-001.png` upward into one directory per page, so
    `<base>-001` meant "the first sheet of whatever was asked for last" — a second
    `--only` selection silently replaced the first's images while the first call's
    *returned index*, which names those files and the lines on them, went on
    describing pictures that were no longer there. A reader that issued three
    selections in parallel got one selection's images and three reports of them, and
    had nothing to tell it apart.

    That is this repo's recurring fault in a new place: a claim whose referent was
    swapped underneath it with no error raised. Here it is cheap to make impossible
    rather than merely detectable.

    Naming the *selection* would stop the clobber but not earn the second half —
    sheets would still be numbered within a call, so lines 11-12 would land on a
    different filename depending on what else was selected alongside them. Naming a
    sheet after its own contents means an overlapping call **reuses** the file it
    already agrees with. `--only 11,12,13` and `--only 11-13` are one request by
    construction, and re-running any selection overwrites its own output and nothing
    else's.

    The base carries what changes the pixels rather than which lines: the zoom
    level, and the flag that alters how a line is rendered. Overrides finer than
    those (`--window`, `--overlap`, `--client-w`, `--height`) are not encoded and so
    do reuse names — they are deliberate, rare, per-question adjustments, and a
    filename long enough to carry them is one nobody can read.

    The `m` for a margin-widened render is gone with the flag. Old files carrying
    it are stale renders of a page, not a naming collision: nothing writes that
    prefix now, so an `m` name can only be something `ocr clean` has yet to sweep.
    """
    head = base + ("s" if smooth else "")

    def name(labels) -> str:
        # A contact-sheet label is the bare index; a zoom label is `index.strip`,
        # optionally `:LO-HI` for a partial line. Whole lines compact into runs;
        # a spanned line keeps its span, because two spans of one line are two
        # different pictures and must not land on one filename.
        whole, spanned = set(), {}
        for lab in labels:
            head_, _, span = str(lab).partition(":")
            i = int(head_.split(".")[0])
            if span:
                spanned.setdefault((i, span), None)
            else:
                whole.add(i)
        parts = [compact_runs(whole)] if whole else []
        parts += [f"{i}p{span}" for i, span in spanned]
        slug = "_".join(p for p in parts if p)
        if len(slug) > limit:
            import hashlib
            slug = "n" + hashlib.sha256(slug.encode()).hexdigest()[:8]
        return f"{head}-{slug}"

    return name


FULL_SPAN = (0, 100)


def _snap_to_white(crop, a: int, b: int, budget: int) -> tuple[int, int]:
    """Widen `[a, b)` outward to the nearest blank pixel column, within `budget`.

    A span's edge landing mid-letter is the failure that costs a re-call, and the
    raster already knows where the letters end. Columns rather than any notion of a
    word: this is a bitonal line crop, so "no ink in this column" is exact and needs
    no segmentation. Bounded on each side independently, because a span sitting
    inside one long word has no gap to find and must not creep out to the measure
    hunting for one — in that case the edge stays where the caller put it, which is
    no worse than before.
    """
    import numpy as np
    ink = (np.asarray(crop.convert("L")) < 128).any(axis=0)
    n = len(ink)
    a, b = max(0, min(a, n)), max(0, min(b, n))

    lo = a
    for i in range(a, max(0, a - budget) - 1, -1):
        if i == 0 or not ink[i]:
            lo = i
            break
    hi = b
    for i in range(b, min(n, b + budget) + 1):
        if i == n or not ink[i - 1]:
            hi = i
            break
    return lo, max(lo + 1, hi)


def _crop_to_span(img, asked: tuple[int, int], window: int, overlap: int):
    """One line image narrowed to one requested place. Returns `(crop, lo, hi)`.

    Taken on the crop, so a percentage means a share of *this line's* extent rather
    than of the measure — on a short line like a signature or a centred heading
    those are very different, and the line is what the caller named.

    **A span narrower than one strip is widened to fill it, for free.** The strip is
    a fixed `window` of source pixels whatever it holds and the sheet is padded to
    the client width regardless, so a 20% span of a full measure renders ~360 px
    inside a 670 px window and leaves the rest white. That white is not a saving; it
    is the margin that would have carried the rest of the word. A caller naming a
    place is estimating from a page composite and will sometimes be off by a few
    percent, and the observed cost of clipping is not a bad image but a *re-call*.

    The returned `lo`/`hi` are the span **rendered**, not the one asked for: two
    requests that widen onto the same region are one picture and must share a
    filename, and a name that disagreed with its image is the defect the naming
    scheme exists to prevent.
    """
    lo, hi = asked
    if (lo, hi) == FULL_SPAN:
        return img, lo, hi
    full = img.width
    a = int(full * lo / 100)
    b = max(a + 1, int(full * hi / 100))
    if b - a < window:
        mid = (a + b) // 2
        a, b = mid - window // 2, mid - window // 2 + window
        # At an edge, slide rather than shrink — the caller asked to see a region,
        # and a window pushed flush against the start of the line still shows all
        # of it plus context on one side.
        if a < 0:
            a, b = 0, min(full, window)
        elif b > full:
            a, b = max(0, full - window), full
    a, b = max(0, a), min(full, b)
    # **Then snap both edges out to white, so no glyph is ever cut.** An edge
    # landing mid-letter is what sends a reader back for another look at the same
    # doubt. Whitespace between words is the one boundary the raster itself
    # supplies, so extend to it — bounded, so a place inside a long unbroken word
    # does not creep across the measure.
    a, b = _snap_to_white(img, a, b, budget=window // 4)
    b = fill_last_strip(a, b, full, window, overlap)
    return (img.crop((a, 0, b, img.height)),
            round(max(0, a) * 100 / full), round(min(full, b) * 100 / full))


def parse_spans(spec: str) -> dict[int, list[tuple[int, int]]]:
    """`"7,20@0-25,22-26"` -> `{7: [(0,100)], 20: [(0,25)], 22..26: [(0,100)]}`.

    **`@LO-HI` names a percentage of the line's width**, and it is the answer to the
    commonest waste at this rung: a doubt is almost never about a line, it is about a
    mark, and a mark occupies a few percent of a full measure. `3-063`'s footnote
    references sat in a few characters of the third quarter of their lines and its
    footnote openers in the first few characters of theirs; magnifying the whole line
    to settle them rendered four strips apiece of which three carried nothing bearing
    on the question. `42-43@0-20` is one small sheet where `42-43` was six.

    Percentages rather than pixels because the caller is reading a *report*, not
    measuring a raster — `ocr lines` gives an index, and "the front of it" or "about
    two-thirds along" is what a reader can actually say from a page composite. A
    pixel span would demand a measurement nobody has taken.

    Rejects rather than skips a token it cannot parse. A selection is a claim about
    which lines were looked at, and silently dropping one means a line reported as
    read was never rendered.

    **One line may carry several places, and they render as several crops.** This
    used to be refused, on the ground that unioning two spans gives back the
    whole-line hull the span existed to avoid — which is true of a *union* and was
    the wrong conclusion. Two places on a line are two pictures, exactly as two
    places on two lines are; nothing is merged. The refusal cost real work: three
    readers in one batch independently typed `1@0,1@100`, `45@0,45@100` and
    `1@15,1@30` — the natural way to ask "is the folio at this end or that one" —
    and each was told to pick one and come back, which is precisely the extra turn
    the batching rule exists to remove. Duplicates still collapse, since asking
    twice for the same crop is one crop.
    """
    out: dict[int, list[tuple[int, int]]] = {}
    for tok in spec.replace(" ", "").split(","):
        if not tok:
            continue
        body, at, span = tok.partition("@")
        lo, hi = FULL_SPAN
        if at:
            a, dash, b = span.partition("-")
            if not dash and not b:
                # **`@P` is a point, and it is the form to reach for.** A range
                # asks the caller for two numbers about a word whose extent they
                # cannot see yet, and a guess that is too narrow gets snapped and
                # widened anyway while a guess that is off-centre misses. Naming
                # only where the word *is* removes the half of the estimate that
                # was never knowable: the window is a fixed width of source pixels
                # regardless, so it gets centred on P and rendered at full size.
                # The batch that produced this form spent three crops framing one
                # word — `23@45-65`, `23@70-90`, `23@60-75` — where `23@60` is one.
                lo = hi = int(a)
                if not 0 <= lo <= 100:
                    raise ValueError(f"point {span!r} must satisfy 0 <= P <= 100")
            elif not dash or not b:
                raise ValueError(f"span {span!r} needs LO-HI percentages or a "
                                 f"single point, e.g. {body}@0-25 or {body}@60")
            else:
                lo, hi = int(a), int(b)
                if not 0 <= lo < hi <= 100:
                    raise ValueError(f"span {span!r} must satisfy 0 <= LO < HI <= 100")
        if "-" in body.lstrip("-"):
            x, y = body.split("-", 1)
            first, last = int(x), int(y)
            if last < first:
                raise ValueError(f"range {body!r} runs backwards")
            idxs = range(first, last + 1)
        else:
            idxs = [int(body)]
        for i in idxs:
            at_line = out.setdefault(i, [])
            if (lo, hi) not in at_line:
                at_line.append((lo, hi))
    if not out:
        raise ValueError("empty line selection")
    # A whole-line request absorbs the places on that line: it already contains
    # them, so honouring both would render the same ink twice under two names.
    return {i: ([FULL_SPAN] if FULL_SPAN in s else s) for i, s in out.items()}


def parse_selection(spec: str) -> set[int]:
    """`"7,20,22-26"` -> `{7, 20, 22, 23, 24, 25, 26}`. Raises on anything else.

    The line set of `parse_spans`, for the callers that render whole lines and so
    have nowhere to honour a span.
    """
    return set(parse_spans(spec))


def write_line_zoom(ref: str, out_dir: Path,
                    only: set[int] | dict[int, tuple[int, int]] | None = None,
                    zoom: int = ZOOM, window: int | None = None,
                    overlap: int = ZOOM_OVERLAP, sheet_h: int = ZOOM_SHEET_H,
                    client_w: int = ZOOM_CLIENT_W,
                    alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
                    scans: str = "scans",
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

    **`only` may carry a horizontal span per line**, as `parse_spans` returns, and
    that is where the real saving at this rung is. A doubt is about a mark, not a
    line: `3-063`'s footnote references occupied a few characters of the third
    quarter of their lines, and rendering the whole measure gave four strips of which
    three bore on nothing. A plain `set` still means every line whole, so every
    caller written before spans keeps working.

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
    resample = (Image.Resampling.LANCZOS if smooth
                else Image.Resampling.NEAREST)
    spans = only if isinstance(only, dict) else None
    strips, seen = [], []
    for rec, line_img in line_crops(ref, alto_dir, root, scans):
        if only is not None and rec["index"] not in only:
            continue
        seen.append(rec["index"])
        # **A line can be asked for in several places, and each is its own crop.**
        # Nothing is unioned: `1@0,1@100` is the two ends of a line, two pictures,
        # in one call and one pair of turns.
        places = spans.get(rec["index"], [FULL_SPAN]) if spans else [FULL_SPAN]
        for asked in places:
            crop, lo, hi = _crop_to_span(line_img, asked, window, overlap)
            for k, x in enumerate(range(0, max(1, crop.width - overlap), step)):
                s = crop.crop((x, 0, min(crop.width, x + window), crop.height))
                # Label is line index and strip position *within that line*, so the
                # sequence restarts per line and a form seen twice across an overlap
                # is recognisable as one form rather than two. The span rides after a
                # colon: `compose_sheets` draws only what precedes one, so the margin
                # stays readable while the filename can still say which part was
                # shown — two places on one line are two pictures and must not
                # collide.
                tag = "" if (lo, hi) == FULL_SPAN else f":{lo}-{hi}"
                strips.append((f"{rec['index']}.{k}{tag}",
                               s.resize((s.width * zoom, s.height * zoom), resample)))
    if only:
        for missing in sorted(set(only) - set(seen)):
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
                                  name_for=sheet_namer(f"zoom{zoom}", smooth))
    return [{"sheet": str(out_dir / e["sheet"]), "zoom": zoom,
             "strips": " ".join(e["items"])} for e in index]


def write_line_crops(ref: str, out_dir: Path, alto_dir: str = DEFAULT_ALTO_DIR,
                     root: Path = Path("."), scans: str = "scans") -> list[dict]:
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
    for rec, crop in line_crops(ref, alto_dir, root, scans):
        path = out_dir / f"{rec['y_rank']:03d}-{rec['index']:03d}-{rec['line_id']}.png"
        crop.save(path)
        out.append({**rec, "crop": str(path)})
    return out
