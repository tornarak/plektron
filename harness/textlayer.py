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
             root: Path = Path("."), folds: dict[str, str] | None = None
             ) -> provenance.Producer:
    """The record every imported page carries. The PDF is the model's checkpoint.

    `folds` are the editor's identified sorts the import wrote in place of the
    layer's codepoints (`keying.Rules.folds`); recorded, so a reading says it
    is not the layer verbatim.
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
                **({"folds": " ".join(f"{a}>{b}" for a, b in sorted(folds.items()))}
                   if folds else {})})


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
    rules = keying.rules(root)
    row_px = [{**r, "text": rules.fold(r["text"])} for r in row_px]
    tree = alto(ref, root, row_px, size,
                producer(pdf, index, "master", overlap, root, folds=rules.folds))
    mz_dir(root).mkdir(parents=True, exist_ok=True)
    tmp = tmp_for(dest)
    tmp.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8",
                                   pretty_print=True))
    tmp.replace(dest)
    return {"ref": ref, "path": str(dest), "lines": len(row_px),
            "chars": sum(len(r["text"]) for r in row_px)}
