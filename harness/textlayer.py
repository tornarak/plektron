"""A source PDF's own text layer, read into `mz/ocr/` as ALTO.

**The second text arrived with its text already read.** The Google Books copies of
the 1900 *Materials* carry an invisible OCR layer under every page image, and its
Russian is near-clean. Running kraken over those pages would replace a reading we
have with a worse one — kraken has no Cyrillic model at all — so this module
carries the layer into the store `ocr predict` writes, in the shape `ocr predict`
writes it, and the ladder goes on unchanged from `ocr-mz`.

**Carried, not trusted.** The glyphs were inferred from a raster by Google's
engine, so the file says `kind: model` and names the PDF as that model's only
checkpoint, by path and by digest. Nothing here promotes a glyph: the page reaches
`gt/ocr/` only through `ocr review` and `ocr restore`, which is to say through a
human, exactly as a kraken page does.

**The rows are rebuilt, by rule, and the rule is recorded.** The layer's own
"lines" are not lines: copy A over-segments a baseline into fragments (three on
one row of printed p. 144 where copy B has one). Fragments whose vertical centres
sit inside each other's box, and whose horizontal extents do not overlap, are one
row; `ROW_OVERLAP` is the threshold and it is written into the provenance, so two
imports can be compared.

**Boxes are in master pixels**, the space every store on this text speaks: the
layer's point coordinates, less the master's own placement origin on the page,
times `dpi / 72`. The origin is read off the page, never assumed to be zero, and a
rotated page is refused because its text space is not the master's.

**The boxes come from font metrics, not ink.** The layer is set in
`GlyphLessFont`, whose boxes are the engine's word boxes stretched to a nominal
font size. A box consistently a little tall or short is harmless — zones and the
generator place a line by its vertical centre — but an offset one is not, which
is why a sample is overlaid with `ocr crops` before a whole text is imported.
And an offset is what the 1900 *Materials* turned out to have, drifting down the
page and differing block to block, so the boxes are moved onto the scan's ink at
import (`align`), y only, with the fit recorded.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from . import keying, provenance
from .atomic import tmp_for
from .layout import dpi as text_dpi
from .layout import stem_for
from .ns import ALTO_NS
from .recognize import ID_PREFIX, MZDIR, alto_for, block_id, mz_dir
from .refs import norm_ref, parse_ref

#: Two fragments are one row when each one's vertical centre lies within this
#: fraction of the smaller one's height from the other's. Measured on printed
#: p. 144 of copy A; recorded in every file this writes.
ROW_OVERLAP = 0.5

#: The `label` every file this writes carries, which is how a later reader asks
#: whether a page in `mz/ocr/` came from a text layer or from a recognizer.
LABEL = "text layer of the source PDF"
STEP = "harness ocr import"


#: The box-to-ink alignment (`align`). A row's ink baseline is searched within
#: this many px of its box: the 1900 Materials' boxes drift up to ~100 px by the
#: foot of a page.
ALIGN_SEARCH_PX = 130
#: Where the layer's baseline sits against the ink's when nothing has drifted:
#: this far below it. It is the font metric's, not a drift, so it is never
#: applied. Measured over the Materials' 451 text pages (2026-11-07): the fit at
#: each page's first row has median -25 px, and three in four lie in -30..-15.
#: It is also where every fit starts, so a page whose rows mostly lock onto a
#: neighbouring line (1-289, 1-397, 125 px off) is not fitted to that lock.
ALIGN_BASELINE_DROP = 25
#: Rows at least this share of the widest row's width vote on the fit: a full
#: row's ink fills its box from end to end, a short one's may not.
ALIGN_ROW_SHARE = 0.6
#: A fit leaving a median residual above this is not trusted, and the page keeps
#: the layer's geometry: of the 451, all but one fit to 7.3 px or better.
ALIGN_MAX_RESID_PX = 8
#: A vote this far from the first fit is dropped before the second: a row whose
#: box sat over a figure, a rule or a neighbour's ascenders.
ALIGN_TRIM_PX = 15
#: How near a line's ink must start and end to its box's for the row to count as
#: on its own line, in the block test: the layer's boxes are word boxes, so
#: their ends are the ink's give or take a glyph's side bearing.
ALIGN_EDGE_PX = 40
#: Fewer votes than this and the page is left as the layer gave it.
ALIGN_MIN_ROWS = 5


class TextLayerError(ValueError):
    """A page whose text layer cannot be carried into the master's space."""


def master_pdf(ref: str, root: Path) -> tuple[Path, int]:
    """The PDF `scans` cut this page from, and the page's 1-based index in it."""
    from .scans import part_of
    part, index = parse_ref(norm_ref(ref))
    for pdf in sorted((Path(root) / "pdfs").glob("*.pdf")):
        if part_of(pdf, root) == part:
            return pdf, index
    raise TextLayerError(f"{ref}: no PDF in pdfs/ is part {part}")


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s.replace(" ", " "))


def fragments(page) -> list[dict]:
    """The layer's own lines, in page points: `{text, box, baseline}`."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            spans = [s for s in line["spans"] if s["text"]]
            text = "".join(s["text"] for s in spans)
            if not text.strip():
                continue
            out.append({"text": text, "box": tuple(line["bbox"]),
                        "baseline": spans[0]["origin"][1]})
    return out


def rows(frags: list[dict], overlap: float = ROW_OVERLAP) -> list[dict]:
    """Fragments on one baseline as one row, rows down the page then across.

    A fragment joins the first row already holding something on its line — its
    centre within `overlap` × the smaller height of a member's — provided it
    overlaps no member horizontally. Two fragments stacked in one column are two
    rows however close they sit, which is what keeps a tightly set note apart from
    the text above it.
    """
    def cy(b):
        return (b[1] + b[3]) / 2

    def h(b):
        return max(1e-6, b[3] - b[1])

    built: list[list[dict]] = []
    for f in sorted(frags, key=lambda f: (cy(f["box"]), f["box"][0])):
        b = f["box"]
        for row in built:
            if all(abs(cy(b) - cy(m["box"])) <= overlap * min(h(b), h(m["box"]))
                   and (b[2] <= m["box"][0] or b[0] >= m["box"][2]) for m in row):
                row.append(f)
                break
        else:
            built.append([f])
    out = []
    for row in built:
        row.sort(key=lambda f: f["box"][0])
        xs0, ys0, xs1, ys1 = zip(*(f["box"] for f in row), strict=True)
        out.append({"text": " ".join(f["text"].strip() for f in row),
                    "box": (min(xs0), min(ys0), max(xs1), max(ys1)),
                    "baseline": sorted(f["baseline"] for f in row)[len(row) // 2]})
    out.sort(key=lambda r: (r["box"][1], r["box"][0]))
    return out


def to_px(row: dict, origin: tuple[float, float], dpi: int) -> dict:
    """A row in master pixels: boxes rounded outward, so a box never loses ink."""
    import math
    k = dpi / 72.0
    ox, oy = origin
    x0, y0, x1, y1 = row["box"]
    px = (math.floor((x0 - ox) * k), math.floor((y0 - oy) * k),
          math.ceil((x1 - ox) * k), math.ceil((y1 - oy) * k))
    return {"text": _nfd(row["text"]), "box": px,
            "baseline": round((row["baseline"] - oy) * k)}


def _ink_baselines(ink, box: tuple[int, int, int, int], search: int) -> list[int]:
    """The ink baselines near this row: the bottom of each dense band of rows.

    Summed across the row's own columns, a line of type is densest through its
    x-height and drops sharply at the baseline; ascenders and descenders are thin
    by comparison. So the bands where the profile holds half its peak or more are
    the lines' x-height bands, one per line, and each one's last row is that
    line's baseline on the scan.
    """
    import numpy as np
    x0, y0, x1, y1 = box
    lo, hi = max(0, y0 - search), min(ink.shape[0], y1 + search)
    if hi <= lo or x1 <= x0:
        return []
    prof = ink[lo:hi, max(0, x0):x1].sum(axis=1)
    if prof.max() <= 0:
        return []
    dense = np.concatenate(([False], prof >= 0.5 * prof.max(), [False]))
    edges = np.flatnonzero(np.diff(dense.astype(np.int8)))
    return [lo + int(b) - 1 for b in edges[1::2]]


def align(rows_px: list[dict], ink) -> tuple[list[dict], dict]:
    """The rows moved vertically onto the scan's ink, and the fit that moved them.

    **The layer's boxes drift against the raster, and the placement does not
    explain it.** Over the 1900 Materials the master is placed at exactly
    `dpi / 72` on every page, yet the boxes sit up to ~80 px off the ink by the
    foot of a page, by an amount that differs page to page and runs both ways:
    the digitizer's OCR placed its words with a drift of its own. A zone's edge
    drawn from a drifted box cuts off the ink of the line it holds.

    So each full row votes the distance from its layer baseline to the nearest
    ink baseline on the scan (`_ink_baselines`), and the shift is fitted as a
    line down the page (`offset + slope * y`). The votes are then taken again
    against the fit's prediction rather than the layer's baseline, so a drift of
    more than half a line's pitch still finds its own line, and refitted without
    the votes far from it. Every box, and its baseline, moves by the fit at its
    own baseline. Only y moves: text, x and the row order are untouched, so line
    indices mean what they meant. A page with too few votes is left as is.
    """
    import numpy as np
    widest = max((r["box"][2] - r["box"][0] for r in rows_px), default=0)
    full = [r for r in rows_px if r["box"][2] - r["box"][0] >= ALIGN_ROW_SHARE * widest]
    near = {id(r): _ink_baselines(ink, r["box"], ALIGN_SEARCH_PX) for r in full}

    def votes(predict) -> tuple:
        ys, ss = [], []
        for r in full:
            want = r["baseline"] + predict(r["baseline"])
            if near[id(r)]:
                b = min(near[id(r)], key=lambda v: abs(v - want))
                ys.append(r["baseline"])
                ss.append(b - r["baseline"])
        return np.array(ys, dtype=float), np.array(ss, dtype=float)

    # The first votes are the ink baselines nearest where an undrifted layer
    # puts them; a robust first fit (Theil-Sen, the median of pairwise slopes)
    # is not pulled by the few that lock onto a neighbour, and the least-squares
    # refits then drop the votes far from it.
    slope, offset = 0.0, -float(ALIGN_BASELINE_DROP)
    y, s = votes(lambda v, a=slope, b=offset: a * v + b)
    fit = {"rows": len(y), "offset": 0.0, "slope": 0.0, "resid": 0.0}
    if len(y) < ALIGN_MIN_ROWS:
        return rows_px, {**fit, "applied": False, "why": "too few full rows"}
    i, j = np.triu_indices(len(y), 1)
    dy = y[j] - y[i]
    ok = dy != 0
    slope = float(np.median((s[j] - s[i])[ok] / dy[ok])) if ok.any() else 0.0
    offset = float(np.median(s - slope * y))
    keep = np.ones_like(s, dtype=bool)
    for _ in range(2):
        y, s = votes(lambda v, a=slope, b=offset: a * v + b)
        keep = np.abs(s - (slope * y + offset)) <= ALIGN_TRIM_PX
        if keep.sum() < ALIGN_MIN_ROWS:
            return rows_px, {**fit, "applied": False, "why": "the votes disagree"}
        slope, offset = (float(v) for v in np.polyfit(y[keep], s[keep], 1))
    resid = float(np.median(np.abs(s[keep] - (slope * y[keep] + offset))))
    fit = {"rows": int(keep.sum()), "offset": round(offset + ALIGN_BASELINE_DROP, 1),
           "slope": round(slope * 1000, 2), "resid": round(resid, 1)}

    def drift(v: float) -> int:
        """The box's move: the fit, less the metric's own drop."""
        return round(slope * v + offset + ALIGN_BASELINE_DROP)

    if resid > ALIGN_MAX_RESID_PX:
        return rows_px, {**fit, "applied": False, "why": "the fit is loose"}
    if any(abs(drift(r["baseline"])) > ALIGN_SEARCH_PX for r in rows_px):
        return rows_px, {**fit, "applied": False, "why": "the drift exceeds the search"}
    # **The drift is the page's, and a block may not share it.** The layer places
    # some blocks on their own, the footnotes most often: on `1-243` the body
    # drifts 70 px by its foot while its footnotes sit where an undrifted layer
    # puts them, so the page's fit moved them a whole line too far. Each block of
    # rows between two structural gaps therefore takes the page's drift or none,
    # whichever puts more of its rows on an ink baseline.
    order = sorted(range(len(rows_px)), key=lambda k: rows_px[k]["baseline"])
    pitches = np.diff([rows_px[k]["baseline"] for k in order])
    # 1.25 pitches: an over-eager split costs nothing, since a block that
    # shares the page's drift keeps it; a missed one leaves footnotes on the
    # body's drift (`1-397`: 185 px above its notes, against a 127 px pitch).
    gap = 1.25 * float(np.median(pitches)) if len(pitches) else 0.0
    blocks: list[list[int]] = []
    for n, k in enumerate(order):
        if n and pitches[n - 1] > gap:
            blocks.append([])
        if not blocks:
            blocks.append([])
        blocks[-1].append(k)

    def on_ink(ks: list[int], move) -> int:
        """Rows that land on their own line: an ink baseline where the row's
        baseline says, and that line's ink starting and ending where its box
        does. The second half is what tells two lines a pitch apart: in a block
        of footnotes set close, a whole-line move still lands every row on some
        line's baseline, but an indented opener on a flush line's ink does not
        start where its box does."""
        n = 0
        for k in ks:
            r = rows_px[k]
            m = move(r["baseline"])
            want = r["baseline"] + m - ALIGN_BASELINE_DROP
            x0, y0, x1, y1 = r["box"]
            near_ = _ink_baselines(ink, (x0, y0 + m, x1, y1 + m), ALIGN_TRIM_PX * 2)
            if not any(abs(b - want) <= ALIGN_TRIM_PX for b in near_):
                continue
            lo = max(0, x0 - 4 * ALIGN_EDGE_PX)
            band = ink[max(0, want - 30):max(0, want), lo:x1 + 4 * ALIGN_EDGE_PX]
            cols = lo + np.flatnonzero(band.any(axis=0)) if band.size else []
            if len(cols) and abs(int(cols[0]) - x0) <= ALIGN_EDGE_PX \
                    and abs(int(cols[-1]) - x1) <= ALIGN_EDGE_PX:
                n += 1
        return n

    # Each block's candidates: the page's drift, none, and the constant shift each
    # of its rows votes for (its nearest ink baseline). The drift is tried first,
    # so it wins a tie; a block takes another move only where more of its rows
    # land on their own line under it.
    moves = [0] * len(rows_px)
    own = 0
    for ks in blocks:
        cands: list = [drift, lambda _: 0]
        seen = set()
        for k in ks:
            r = rows_px[k]
            for b in _ink_baselines(ink, r["box"], ALIGN_SEARCH_PX):
                c = b - (r["baseline"] - ALIGN_BASELINE_DROP)
                if abs(c) <= ALIGN_SEARCH_PX and round(c / 4) not in seen:
                    seen.add(round(c / 4))
                    cands.append(lambda _, c=c: int(c))
        best = max(cands, key=lambda f: on_ink(ks, f))
        if best is not drift:
            own += 1
        for k in ks:
            moves[k] = best(rows_px[k]["baseline"])
    out = []
    for r, d in zip(rows_px, moves, strict=True):
        x0, y0, x1, y1 = r["box"]
        out.append({**r, "box": (x0, y0 + d, x1, y1 + d), "baseline": r["baseline"] + d})
    return out, {**fit, "applied": True, "blocks": len(blocks), "own_shift": own}


def page_rows(page, dpi: int, overlap: float = ROW_OVERLAP) -> tuple[list[dict], tuple]:
    """One PDF page's rows in its master's pixels, and the master's size."""
    from .scans import page_images
    if page.rotation:
        raise TextLayerError(f"PDF page {page.number + 1} is rotated "
                             f"{page.rotation}°: its text space is not the master's")
    imgs = page_images(page)
    if not imgs:
        raise TextLayerError(f"PDF page {page.number + 1} holds no master")
    m = imgs[0]
    origin = (m["pt"][0], m["pt"][1])
    return ([to_px(r, origin, dpi) for r in rows(fragments(page), overlap)],
            (m["w"], m["h"]))


def producer(pdf: Path, pdf_page: int, copy: str, overlap: float = ROW_OVERLAP,
             root: Path = Path("."), folds: dict[str, str] | None = None,
             align: str = "", word_folds: str = "") -> provenance.Producer:
    """The record every imported page carries. The PDF is the model's checkpoint.

    `folds` are the editor's identified sorts the import wrote in place of the
    layer's codepoints (`keying.Rules.folds`); recorded, so a reading says it
    is not the layer verbatim. `word_folds` says the same of the word-level
    folds (`keying.Rules.script_folds`, `numeral_folds`), which rewrite whole
    words and so are recorded as the rule, not as a list of pairs.
    """
    import os

    import pymupdf
    with pymupdf.open(pdf) as doc:
        made_by = (doc.metadata or {}).get("producer", "") or "unrecorded"
    return provenance.Producer(
        step=STEP, label=LABEL, kind="model",
        version=f"pymupdf {pymupdf.VersionBind}",
        model=os.path.relpath(pdf, root), sha256=provenance.digest(pdf),
        inputs={"engine": "the OCR that made the text layer", "copy": copy,
                "pdf_page": pdf_page, "text_layer_producer": made_by.replace("; ", ", "),
                "row_overlap": overlap,
                **({"align": align} if align else {}),
                **({"folds": " ".join(f"{a}>{b}" for a, b in sorted(folds.items()))}
                   if folds else {}),
                **({"word_folds": word_folds} if word_folds else {})})


def alto(ref: str, root: Path, row_px: list[dict], size: tuple[int, int],
         prod: provenance.Producer):
    """One page as `ocr predict` writes one: a bare block of lines, document order
    down the page, one `String` per line, ids `mz_<ref>_l<i>`."""
    from lxml import etree

    def el(parent, tag, **attrs):
        return etree.SubElement(parent, f"{{{ALTO_NS}}}{tag}",
                                {k: str(v) for k, v in attrs.items()})

    ref = norm_ref(ref)
    top = etree.Element(f"{{{ALTO_NS}}}alto", nsmap={None: ALTO_NS})
    desc = el(top, "Description")
    el(desc, "MeasurementUnit").text = "pixel"
    el(el(desc, "sourceImageInformation"), "fileName").text = \
        f"{stem_for(ref, root)}.png"
    desc.append(provenance.alto_processing(prod, ident="OCR_harness-ocr-import"))
    w, h = size
    page = el(el(top, "Layout"), "Page", WIDTH=w, HEIGHT=h, PHYSICAL_IMG_NR=0,
              ID="page_0")
    ps = el(page, "PrintSpace", HPOS=0, VPOS=0, WIDTH=w, HEIGHT=h)
    if row_px:
        bx0 = min(r["box"][0] for r in row_px)
        by0 = min(r["box"][1] for r in row_px)
        bx1 = max(r["box"][2] for r in row_px)
        by1 = max(r["box"][3] for r in row_px)
    else:
        bx0 = by0 = bx1 = by1 = 0
    tb = el(ps, "TextBlock", ID=block_id(ref), HPOS=bx0, VPOS=by0,
            WIDTH=bx1 - bx0, HEIGHT=by1 - by0)
    for i, r in enumerate(row_px, 1):
        x0, y0, x1, y1 = r["box"]
        bl = min(max(r["baseline"], y0), y1)
        tl = el(tb, "TextLine", ID=f"{ID_PREFIX}{ref}_l{i}", HPOS=x0, VPOS=y0,
                WIDTH=x1 - x0, HEIGHT=y1 - y0, BASELINE=f"{x0} {bl} {x1} {bl}")
        el(el(tl, "Shape"), "Polygon",
           POINTS=f"{x0} {y0} {x1} {y0} {x1} {y1} {x0} {y1}")
        el(tl, "String", CONTENT=r["text"], HPOS=x0, VPOS=y0,
           WIDTH=x1 - x0, HEIGHT=y1 - y0)
    return top


def imported(ref: str, root: Path = Path(".")) -> bool:
    """Is this page's `mz/ocr/` reading a text layer's, by its own record."""
    p = alto_for(ref, root, MZDIR)
    return p.exists() and any(pr.label == LABEL for pr in provenance.read_producers(p))


def import_page(ref: str, root: Path = Path("."), force: bool = False,
                overlap: float = ROW_OVERLAP) -> dict:
    """Carry one page's text layer into `mz/ocr/`. Kept unless `force`."""
    import pymupdf
    from lxml import etree

    ref = norm_ref(ref)
    dest = alto_for(ref, root, MZDIR)
    if dest.exists() and not force:
        return {"ref": ref, "skipped": "already in mz/ocr (--force to re-import)"}
    pdf, index = master_pdf(ref, root)
    with pymupdf.open(pdf) as doc:
        row_px, size = page_rows(doc[index - 1], text_dpi(root), overlap)
    row_px, fit = _aligned(ref, root, row_px, size)
    rules = keying.rules(root)
    row_px = [{**r, "text": rules.fold(r["text"])} for r in row_px]
    tree = alto(ref, root, row_px, size,
                producer(pdf, index, "master", overlap, root, folds=rules.folds,
                         align=fit, word_folds=rules.word_folds_record))
    mz_dir(root).mkdir(parents=True, exist_ok=True)
    tmp = tmp_for(dest)
    tmp.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8",
                                   pretty_print=True))
    tmp.replace(dest)
    return {"ref": ref, "path": str(dest), "lines": len(row_px),
            "chars": sum(len(r["text"]) for r in row_px), "align": fit}


def _aligned(ref: str, root: Path, row_px: list[dict],
             size: tuple[int, int]) -> tuple[list[dict], str]:
    """`align` against the page's raster, and the fit as its provenance says it.

    The raster is the master cut out of the same PDF (`scans extract`), so the two
    share one pixel space; one of another size is not that master, and the rows
    are left as the layer gave them rather than aligned to the wrong page.
    """
    from .lines import ink_mask
    from .paths import scan_for
    scan = scan_for(ref, root)
    if not scan.exists():
        return row_px, "none: no raster in scans/"
    ink = ink_mask(scan)
    if (ink.shape[1], ink.shape[0]) != tuple(size):
        return row_px, (f"none: the raster is {ink.shape[1]}x{ink.shape[0]}, "
                        f"the master {size[0]}x{size[1]}")
    out, fit = align(row_px, ink)
    said = (f"drift {fit['offset']} px at y=0, {fit['slope']} px per 1000 px, "
            f"{fit['rows']} rows, median residual {fit['resid']} px, less a "
            f"{ALIGN_BASELINE_DROP} px baseline drop")
    if not fit["applied"]:
        return row_px, f"none: {fit['why']} ({said})"
    return out, said
