"""The raster substrate: what the PDFs hold, what `scans/` holds, and the swap.

`scans/` is derived. It was `pdftoppm -r 300` over `pdfs/` once, and that renders
the *page box*. The three PDFs are MRC-layered — a 1-bit JBIG2 master per page, plus
separate embedded JPEGs for the photographs — and the page boxes they were wrapped
in are arbitrary, so rendering resampled a bitonal master that could have been
copied.

EVERY MASTER IS PLACED AT SCALE 1.0 AND IS EXACTLY 300 DPI, measured against its own
placement rather than the page box. Over 832 pages: 470 at (300.00, 300.00), 359 at
(300.00, 300.04), and 3 masterless RGB pages at 150. "Part 1 at 295.5 dpi, part 3 at
308.4" divided by the mediabox and was wrong for as long as it stood in
`docs/rasters.md`. The parts differ only by a **translation**, which is what those
boxes did:

  part 1  master 2781x3866 centred in a 2824x3897 box  -> +21.375, +15.375 px of
          white padding, a *fractional* offset, so poppler resampled every pixel of
          every page for a shift of three-eighths of one.
  part 2  master 2550x3525 at (0, 0) in a 2550x3525 box. A pure blit was available
          and poppler smeared it anyway: 247 grey values from a 2-value source.
  part 3  part 2's layout jammed onto A4 -> -34.875, -8.58 px, so the render is
          *cropped*, ~35 px off each side. Part 3 was read below source resolution
          for twenty months on the strength of it.

WHAT `extract` REFUSES TO DO QUIETLY. A page is refused, named, and left unwritten
rather than turned into something plausible: two full-page images; a JBIG2 master
that is not at scale 1.0; an embedded image whose rect falls outside its master; a
photo whose paste ratio is not near-integral; and a page named in `MASTERLESS` that
turns out to carry a master after all. The three masterless RGB pages — `1-001`,
`1-002` (covers) and `1-361` (the foldout) — are carved out by name: each is one
150 ppi photograph of a whole leaf, written **at its own size** rather than doubled
to the page's 300 dpi, which added no detail and cost 26.5 MB across the three.

WHY THIS IS A MODULE AND NOT A SCRIPT. It was `tools/extract_scans.py`, outside the
package, where no test could reach it — and the geometry it discovered was readable
only as a JSON blob no verb read back. Both halves are here now: `extract` cuts, and
`info`/`census`/`audit`/`space` answer questions about what was cut, so that an
agent asking "how big is this page, and in which coordinate space" reaches for a
verb rather than for PIL and a heredoc.

THE ONE WRITER TO `scans/` IS `swap`. Rasters are cheap — derived, gitignored,
rebuilt by one command — but a raster in `scans/` whose geometry differs from the
one the stores are keyed to is the defect this whole group exists to make
impossible. So `extract --rasters DIR` always cuts a *sibling*, carrying its own
manifest, and `swap` installs it together with everything that has to move with it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from pathlib import Path

from . import farms, paths, provenance
from .refs import norm_ref, parse_ref

#: The source PDFs' own embedded-image geometry. **Derived but tracked**, on
#: `data/geo/`'s precedent: `pdfs/` are symlinks outside the repository, so a clone
#: cannot rebuild it.
PDF_IMAGES = "data/pdf_images.json"

#: A cut tree carries its own manifest under this name, so that a directory of
#: rasters is never separable from the geometry it was cut at. `swap` diffs it
#: against the committed one; without it there is no way to know what space a tree
#: of PNGs is in, which is exactly the question that went unasked for twenty months.
TREE_MANIFEST = "pdf_images.json"

DPI = 300
PT = DPI / 72.0                      # device px per PostScript point at 300 dpi

#: Named rather than detected: this says what the *source* holds, not what one
#: rendering happened to produce. These three pages carry no JBIG2 master — they are
#: RGB photographs of a cover and a foldout — so the scale-1.0 refusal below does not
#: apply to them and would otherwise refuse its own corpus. **Checked in both
#: directions** by `page_record`: the set was asserted here and in
#: `tools/greyscale_scans.py` and verified in neither, and it is precisely the set of
#: pages whose two coordinate spaces differ by a scale, so a wrong member is a silent
#: scale error rather than a cosmetic one.
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

# --- provenance ---------------------------------------------------------------
#
# **`scans/` is `#mz`, so it says what made it.** Every page here is a rule's
# output — the scanner's own MRC layers, cut by a deterministic procedure — and
# until now the only record of that was a sentence in a doc. Two things carry it:
# the manifest's `_sources` block, which digests the PDFs each page came out of,
# and a tEXt chunk in every PNG, which travels with the file when it is copied out
# of the tree entirely.
#
# **The record is `provenance.Producer`, not a second spelling of it.** That module
# is the one writer for every `mz/` file that says what made it, and a raster is one:
# `kind="rule"`, because a page here is derived from a stated input by a
# deterministic procedure rather than inferred by a model. It had no non-XML carrier,
# so `provenance.encode`/`decode` were made public rather than the wire format
# reimplemented here — a fourth spelling of one fact is exactly what that module
# exists to prevent.
#
#: The tEXt keyword, `provenance.py`'s: the *reader* is there — `read_producers`
#: dispatches on suffix so `corpus provenance` can count a raster store — and a
#: keyword spelled in two modules is the drift this whole arrangement is against.
PNG_KEY = provenance.PNG_KEY

STEP = "harness scans extract --all --rasters DIR"
LABEL = "raster cut from the PDF's own MRC layers"


def _digest(path: Path) -> str:
    """SHA-256 of a file, read in blocks.

    The whole of `pdfs/` is 0.13 s, so nothing here is conditional on a flag: a
    check that only runs when someone remembers to ask is not a check on anything.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sources(root: Path = Path("."), pdfs: list[Path] | None = None) -> dict:
    """Each source PDF, by part: its name, digest, size and page count.

    **The name is the basename, never the path.** The links in `pdfs/` point into a
    library outside the repository whose location differs per machine, so recording
    where this machine found the file would put a fact about one filesystem into a
    tracked manifest — and would make two correct runs produce different files.
    """
    pdfs = sorted((root / "pdfs").glob("*.pdf")) if pdfs is None else pdfs
    import pymupdf

    out = {}
    for pdf in pdfs:
        with pymupdf.open(pdf) as doc:
            pages = doc.page_count
        out[str(part_of(pdf))] = {"file": pdf.name, "sha256": _digest(pdf),
                                  "bytes": pdf.stat().st_size, "pages": pages}
    return out


def _producer(source: dict, rec: dict) -> provenance.Producer:
    """What one page's raster records about the act that cut it.

    The digest carried is the **PDF's**, never the PNG's own — `provenance.py`'s
    rule, and it holds here for its reason: a file's hash of itself restates the
    file and witnesses nothing. What a reader needs is which byte sequence this
    page came out of.
    """
    m = rec.get("master") or {}
    return provenance.Producer(
        step=STEP, label=LABEL, kind="rule", version=_pymupdf_version(),
        inputs={
            "ref": rec["ref"],
            "source": source.get("file", ""),
            "source_sha256": source.get("sha256", ""),
            "master_xref": m.get("xref", ""),
            "master": f"{m.get('w')}x{m.get('h')}",
            "offset": ",".join(str(v) for v in rec.get("offset") or []),
            "photos": len(rec.get("images") or []),
        })


def _pymupdf_version() -> str:
    import pymupdf
    return f"pymupdf {pymupdf.version[0]}"


def read_png_provenance(path: Path) -> provenance.Producer | None:
    """What a raster says made it, or `None`.

    `None` for a PNG written before this existed *and* for one written by something
    else entirely, which is the right conflation: both are unwitnessed, and the
    census counts what can be read rather than what was intended.
    """
    if not path.exists():
        return None
    from PIL import Image
    try:
        with Image.open(path) as im:
            raw = (im.info or {}).get(PNG_KEY, "")
    except OSError:
        return None
    return provenance.decode(str(raw))


ABOUT = (
    "Derived but tracked, on data/geo/'s precedent: pdfs/ are symlinks outside the "
    "repository, so a clone cannot rebuild this. Built by "
    "`harness scans extract --all --commit`. Per page: `master` is the full-page "
    "image scans/ is cut from, `offset` is the integer shift from the legacy "
    "pdftoppm render space into master space (master = render - offset), and "
    "`images` are the embedded photographs with `rect` in MASTER pixels, rounded "
    "outward. `rendered: true` marks the three masterless RGB pages, which are "
    "rasterised at 300 dpi as before and do not move. `_sources` digests the PDFs "
    "these pages were cut from, and `harness scans audit` re-reads them: a source "
    "that changed underneath this file is a finding, not a silence."
)


# --- the manifest -------------------------------------------------------------

def _strip(data: dict) -> dict[str, dict]:
    return {k: v for k, v in data.items() if not k.startswith("_")}


def manifest_meta(path: Path) -> dict:
    """The manifest's underscore keys — `_about`, `_sources` — which `read_manifest`
    strips because every other caller wants pages and only pages."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in data.items() if k.startswith("_")}


def read_manifest(path: Path) -> dict[str, dict]:
    """Any manifest file, by path. Missing or unparseable is `{}`.

    Missing is `{}` rather than a raise, `figures.readings`' disposition and for its
    reason: a corpus that has never run the extractor must show none rather than
    fail. A *caller* that needs one present says so — `swap` refuses a tree with no
    manifest, because there the absence is the finding.
    """
    if not path.exists():
        return {}
    try:
        return _strip(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return {}


def pdf_images(root: Path = Path(".")) -> dict[str, dict]:
    """`data/pdf_images.json` — the source PDFs' own embedded-image geometry.

    **The one witness to a figure's place that no model and no human produced.** The
    scans are MRC-layered: a 1-bit master per page plus separate embedded JPEGs for
    the photographs, and the scanner's own segmentation decided which pixels were
    which. `extract` reads the placement out; this reads what it wrote.

    Per ref: `master` (`w`, `h`, `bpc`, `cs`, `rendered`), `offset` — the integer
    shift from the legacy `pdftoppm` render space into master space, such that
    `master = render - offset` — and `images`, each with `rect` in **master** pixels.

    **`offset` is a historical fact, not a live one.** It records where the master
    sat inside the space the corpus was once rasterised in, and it is spent: the
    stores were moved out of that space and `data/_migrated.json` is the receipt. A
    *future* re-extraction's shift is not this field — it is the difference between
    two manifests' placements, which is `migrate.plan`'s job.
    """
    return read_manifest(root / PDF_IMAGES)


def pdf_images_for(ref: str, root: Path = Path(".")) -> dict:
    """One page's manifest entry, or `{}`."""
    return pdf_images(root).get(norm_ref(ref), {})


def rects_in(entry: dict, page_w: int, page_h: int) -> tuple[list[list[int]], str]:
    """This page's photo rects in the coordinate space a store of size `page_w` x
    `page_h` is using, plus the name of that space.

    **The manifest speaks master space and a store may not.** Before the rasters
    were rebuilt, `gt/fig/` held the legacy render's coordinates, which differ from
    the master's by a translation of up to 35 px — enough to turn a correct box into
    a finding. So the space is *decided from the file's own declared page box* rather
    than assumed, which is `figures._scale_for`'s philosophy applied to translation
    instead of to scale.

    Three answers and no fourth: `master` when the box is the master's own size,
    `render` when it is the legacy render's, and `""` when it is neither — for which
    the caller reports `skip`. A guess here would be a comparison between two
    coordinate systems presented as a fact about figures.

    **The render size is read from the manifest, never computed as master + offset.**
    That arithmetic is wrong by the right-hand margin — part 1's master is 2781x3866
    at (21, 15) inside a 2824x3897 page, so it predicts 2802x3881 — and being wrong
    here does not raise: it files every part 1 page as an unrecognised space and
    reports `skip`, which reads as "nothing to say" about 176 pages that had plenty.
    It did exactly that before this line was a lookup.
    """
    m = entry.get("master") or {}
    mw, mh = m.get("w"), m.get("h")
    rw, rh = entry.get("render") or [0, 0]
    dx, dy = entry.get("offset") or [0, 0]
    rects = [list(im["rect"]) for im in entry.get("images") or []]
    if (page_w, page_h) == (mw, mh):
        return rects, "master"
    if (page_w, page_h) == (rw, rh):
        return [[r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy] for r in rects], "render"
    return [], ""


# --- reading the PDFs ---------------------------------------------------------

def _out(v: float, up: bool) -> int:
    """Round a rect edge outward, having first snapped off the parse error.

    Outward is deliberate: a rect one pixel short of its photo leaves exactly the
    antialiased fringe this whole approach exists to remove. The pad is one thing and
    the arithmetic is another, and neither may stand in for the other — a rect that
    grew by a pixel because of float32 would be a pad nobody chose.
    """
    if abs(v - round(v)) < SNAP:
        return int(round(v))
    return math.ceil(v) if up else math.floor(v)


def part_of(pdf: Path) -> int:
    """Which part a source PDF is, from its filename.

    Longest fragment first: `" Part I "` is a substring of neither `" Part II "` nor
    `" Part III "` given the trailing space, but the ordering is made explicit rather
    than left to depend on that.
    """
    for frag, n in sorted(PARTS, key=lambda t: -len(t[0])):
        if frag in pdf.name:
            return n
    raise ValueError(f"cannot tell which part this is: {pdf.name}")


def page_images(page) -> list[dict]:
    """Every embedded image on the page with its placement, largest first.

    `bbox` from PyMuPDF is already y-down page coordinates, which is the same
    orientation as a raster, so nothing here flips an axis. That is worth stating
    because the PDF's own y runs the other way and the trap is real: part 3's master
    sits 8.58 px above the page top and 8.54 px below its bottom, and an offset taken
    from the wrong edge is wrong by a pixel on one axis only.
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
    master is 2824x3897 at (0, 0) among 357 neighbours at 2781x3866 placed at
    (21, 15), so a constant would be wrong there and silently. (`extract_scans.py`
    said "2824x3866" here, which is the neighbours' height on that page's width —
    a number that had never been read back off the manifest it describes. It is
    2824x3897, and that page is the *whole* page: its master is the media box.)
    """
    rec: dict = {"ref": ref, "refuse": "", "master": None, "offset": [0, 0],
                 "render": [0, 0], "images": []}
    imgs = page_images(page)
    if not imgs:
        rec["refuse"] = "no embedded image"
        return rec

    m = imgs[0]
    mx0, my0, mx1, my1 = m["pt"]
    sx = m["w"] / (mx1 - mx0) if mx1 > mx0 else 0.0
    sy = m["h"] / (my1 - my0) if my1 > my0 else 0.0
    at_scale = abs(sx - PT) <= SCALE_TOL and abs(sy - PT) <= SCALE_TOL

    if ref in MASTERLESS:
        # **The carve-out is checked, not trusted.** The set was asserted in two
        # files and verified in neither, and these are the only three pages whose two
        # coordinate spaces differ by a *scale* rather than a translation — so a page
        # that has quietly acquired a master is a page where every coordinate would
        # be wrong by a factor. The converse direction needs no clause of its own: a
        # page outside the set with no scale-1.0 master already refuses below.
        if at_scale:
            rec["refuse"] = ("named in MASTERLESS but carries a master at scale 1.0; "
                             "the set and the source disagree")
            return rec
        # **Taken at its own size, not rendered.** These three are one RGB photograph
        # of a whole leaf at 150 ppi, and rendering the page at 300 doubled them for
        # nothing: 796 KB of source became 26.5 MB of PNG, and the foldout map came
        # out visibly the worse for it. `render` still records the size poppler used,
        # because that is what the old coordinates are in and it is the only way to
        # recognise them — but no coordinate exists on any of the three, all being
        # fully exempt.
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

    if not at_scale:
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
    # snag `tools/migrate_coords.py` recorded in one: poppler ceils, so 935.1 pt
    # gives 3897 and a `round` gives 3896; but a bare `ceil` "predicts 2782 for the
    # covers where poppler renders 2781", because 667.44/72*300 computes as
    # 2781.0000000000005. Both halves are needed and neither alone is right. This
    # number is a historical fact about a tree that is gone — it exists only so a
    # store's old coordinates can still be recognised — so it has to reproduce what
    # was, not what would be tidiest.
    rec["render"] = [_out(page.rect.width * PT, True),
                     _out(page.rect.height * PT, True)]

    for im in imgs[1:]:
        x0, y0, x1, y1 = im["pt"]
        # **`PT`, not the measured `sx`.** The scale-1.0 refusal above has already
        # established that this master is at exactly 300 dpi; going on to divide by a
        # float32-derived width would quietly reintroduce the error that check exists
        # to exclude, and would make every rect depend on the parse rather than on
        # the fact.
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


def _pil(pix):
    """A PyMuPDF pixmap as a PIL image, without a temp file."""
    from PIL import Image
    mode = {1: "L", 3: "RGB", 4: "CMYK"}[pix.n - pix.alpha]
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def cut_page(doc, rec: dict, out_dir: Path, source: dict | None = None) -> dict:
    """Write one page's raster: the master, with its photographs pasted back.

    **Mode `1` where the page has no photograph**, which is 593 of 832 and is what
    the source actually is — a bitonal master we were rendering to 8-bit greyscale
    and resampling on the way. A page carrying a photograph has to be `L`, since a
    halftone is not two-valued.

    The photographs go back **nearest at their integral scale**, so every native JPEG
    sample survives as an exact block and nothing is invented between them. That is
    also what makes `fig crops --source native` and the composite show the same
    pixels at different sizes rather than two different pictures.
    """
    import pymupdf
    from PIL import Image

    ref = rec["ref"]
    m = rec["master"]
    dest = out_dir / f"chukchi-{ref}.png"
    # **The provenance travels in the file, not only in the manifest.** A raster
    # copied out of the tree — into a training directory, an issue, someone's
    # downloads — leaves the manifest behind, and the question "what is this and
    # what was it cut from" then has no answer at all. Nothing in the chunk is a
    # timestamp or an absolute path, so two runs over the same PDFs produce
    # byte-identical files and the tree stays diffable against itself.
    meta = _png_meta(_producer(source or {}, rec))
    pix = pymupdf.Pixmap(doc, m["xref"])
    if m.get("rendered"):
        # A whole-leaf RGB photograph and nothing to composite onto it. Written at
        # its own size: doubling it to the page's 300 dpi added no detail and cost
        # 26.5 MB across the three.
        _pil(pix).save(dest, pnginfo=meta)
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
        # Lossless: the master holds two values, so mode `1` is the same picture in
        # an eighth of the bits — and it stops colour depth from correlating with
        # "has a figure", which is the confound the blot exists to remove.
        img = img.convert("1")
    img.save(dest, pnginfo=meta)
    return {"ref": ref, "mode": img.mode, "photos": len(rec["images"])}


def _png_meta(p: provenance.Producer):
    """The producer as a PNG tEXt chunk: one encoded string under one keyword.

    One chunk rather than one per field, so what a raster carries is byte-for-byte
    what an ALTO's `processingStepSettings` carries and `provenance.decode` reads
    either. The separator rule and the refusal of a value containing it are
    `Producer.settings`', enforced there — this adds no escaping of its own,
    because two escapings of one format is how a round trip stops being one.
    """
    from PIL.PngImagePlugin import PngInfo

    meta = PngInfo()
    meta.add_text(PNG_KEY, provenance.encode(p))
    return meta


def extract(root: Path = Path("."), refs: list[str] | None = None,
            rasters: Path | None = None, tick=None) -> tuple[dict, list[dict]]:
    """Walk the PDFs. Returns `(manifest, records)`; writes only under `rasters`.

    **Serial, and `--jobs` is deliberately absent.** The per-page cost here is a PNG
    encode, which is exactly the GIL-releasing work `parallel.pmap` exists for — but
    a `pymupdf.Document` is not safe to touch from several threads, and the pool
    would have to be per-PDF with a document each, which is three workers for three
    files of wildly different lengths. The bar reports; the work is one page at a
    time.
    """
    import pymupdf

    pdf_dir = root / "pdfs"
    if not pdf_dir.is_dir():
        raise FileNotFoundError(f"no {pdf_dir}")
    want = {norm_ref(r) for r in refs} if refs else None

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"no PDFs in {pdf_dir}")
    # **A dangling symlink is named here rather than inside the parser.** `pdfs/`
    # holds relative links to a library outside the repository, and they resolve
    # from the primary checkout only — in a git worktree every one of them dangles.
    # PyMuPDF's own `FileNotFoundError` is not the builtin, so it escapes `cli.main`
    # as a traceback; `glob` finds the link and `exists()` follows it, which is the
    # distinction that makes this checkable at all.
    missing = [p for p in pdfs if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} of {len(pdfs)} PDFs cannot be opened: "
            f"{missing[0].name!r} — the links in pdfs/ are relative to the primary "
            "checkout, so they dangle in a worktree; run with --root pointing at a "
            "root whose pdfs/ resolves")

    # Digested before a page is read, so that what every raster records as its
    # source is the file this run actually opened.
    src = sources(root, pdfs)
    manifest: dict = {"_about": ABOUT, "_sources": src}
    records: list[dict] = []
    if rasters is not None:
        rasters.mkdir(parents=True, exist_ok=True)

    # The denominator is counted first, in its own pass, because `pmap`'s rule holds
    # for a hand-rolled bar too: the party that knows the work-list is the one that
    # must size it. `page_count` opens no page.
    if want is not None:
        total = len(want)
    else:
        total = 0
        for pdf in pdfs:
            with pymupdf.open(pdf) as doc:
                total += doc.page_count
    done = 0
    for pdf in pdfs:
        part = part_of(pdf)
        with pymupdf.open(pdf) as doc:
            for i, page in enumerate(doc, start=1):
                ref = f"{part}-{i:03d}"
                if want is not None and ref not in want:
                    continue
                rec = page_record(page, ref)
                if not rec["refuse"] and rasters is not None:
                    cut = cut_page(doc, rec, rasters, src.get(str(part)))
                    rec["mode"] = cut.get("mode", "")
                    if cut.get("refuse"):
                        rec["refuse"] = cut["refuse"]
                records.append(rec)
                done += 1
                if tick:
                    tick(ref, done, total)
                if rec["refuse"]:
                    continue
                manifest[ref] = {"master": rec["master"], "offset": rec["offset"],
                                 "render": rec["render"], "images": rec["images"]}
    return manifest, records


def write_manifest(manifest: dict, path: Path) -> None:
    """Atomically, and in the one spelling both readers expect."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(manifest, indent=1, sort_keys=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


# --- what the rasters are -----------------------------------------------------

def _raster_facts(path: Path) -> dict:
    """A raster's own account of itself, or why there is none.

    Opens the header only — PIL is lazy until `load()` — so this is a stat and a few
    hundred bytes per page rather than a decode of the whole corpus.
    """
    if not path.exists():
        return {"on_disk": False, "px": "", "mode": "", "bytes": 0}
    from PIL import Image
    try:
        with Image.open(path) as im:
            size, mode = im.size, im.mode
    except OSError as e:
        return {"on_disk": True, "px": "", "mode": "", "bytes": path.stat().st_size,
                "why": f"unreadable: {e}"}
    return {"on_disk": True, "px": f"{size[0]}x{size[1]}", "mode": mode,
            "bytes": path.stat().st_size}


def _leaf_kinds(root: Path) -> dict[str, str]:
    """Ref -> the split it is ruled, for the leaf kinds only.

    A leaf kind is why a page may legitimately hold no coordinate at all, so it
    belongs beside the geometry: `1-361` being `map` is the reason its two spaces
    are allowed to differ by a scale. `train`/`eval` are not reported — they say
    which side of a training split a *text* page fell, which is nothing to do with
    what the raster is.
    """
    from .zones import LEAF_KINDS, load_splits
    return {r: s for r, s in load_splits(root).items() if s in LEAF_KINDS}


def info(refs: list[str], root: Path = Path("."), tick=None) -> list[dict]:
    """Per page: the manifest's geometry against the file on disk.

    The verb an agent reaches for instead of `identify` or a PIL one-liner. It
    answers in one place what the manifest knows (master, placement, the photographs
    and their native resolution) and what the tree holds (pixels, mode, bytes), and
    **says whether the two agree** — which neither source can say alone.
    """
    manifest = pdf_images(root)
    leaves = _leaf_kinds(root)
    out = []
    for ref in refs:
        ref = norm_ref(ref)
        entry = manifest.get(ref, {})
        m = entry.get("master") or {}
        facts = _raster_facts(paths.scan_for(ref, root))
        want = f"{m.get('w')}x{m.get('h')}" if m else ""
        rec = {
            "ref": ref,
            "in_manifest": bool(entry),
            "master": want,
            "bpc": m.get("bpc", 0),
            "cs": m.get("cs", ""),
            "rendered": bool(m.get("rendered")),
            "offset": ",".join(str(v) for v in entry.get("offset") or []),
            "render": "x".join(str(v) for v in entry.get("render") or []),
            "leaf": leaves.get(ref, ""),
            "photos": len(entry.get("images") or []),
            **facts,
        }
        # What the file itself says made it — `""` where it says nothing, which is
        # every raster cut before the chunk existed.
        prov = read_png_provenance(paths.scan_for(ref, root))
        rec["cut_from"] = prov.inputs.get("source", "") if prov else ""
        rec["cut_sha"] = (prov.inputs.get("source_sha256", "")[:16]
                          if prov else "")
        # The agreement is computed, not left to the reader to eyeball: an `agrees`
        # column that says `false` is the whole reason both halves are in one table.
        rec["agrees"] = bool(entry) and facts["on_disk"] and facts["px"] == want
        out.append(rec)
    return out


def photos(refs: list[str], root: Path = Path(".")) -> list[dict]:
    """Every embedded photograph on the named pages, in master pixels.

    Its own table rather than a column of `info`: a list-valued field degrades the
    whole outer table to the verbose form, which is `emit.py`'s rule.
    """
    manifest = pdf_images(root)
    out = []
    for ref in refs:
        ref = norm_ref(ref)
        for n, im in enumerate(manifest.get(ref, {}).get("images") or [], start=1):
            x0, y0, x1, y1 = im["rect"]
            out.append({"ref": ref, "n": n, "rect": f"{x0},{y0},{x1},{y1}",
                        "px": f"{x1 - x0}x{y1 - y0}",
                        "native": f"{im['w']}x{im['h']}",
                        "scale": round((x1 - x0) / max(1, im["w"]), 3),
                        "ppi": im.get("ppi", 0), "bpc": im.get("bpc", 0),
                        "cs": im.get("cs", "")})
    return out


def census(refs: list[str] | None = None, root: Path = Path("."),
           tick=None) -> dict:
    """The counts `CLAUDE.md` deliberately refuses to state, from the manifest.

    Deliberately *not* stored anywhere: a number in a file nothing regenerates goes
    stale, and this is the command whose job is to answer instead.
    """
    manifest = pdf_images(root)
    want = {norm_ref(r) for r in refs} if refs else None
    rows = [(ref, e) for ref, e in manifest.items()
            if want is None or ref in want]

    kinds: dict[str, int] = {}
    masters: dict[str, int] = {}
    offsets: dict[str, int] = {}
    photo_n = 0
    total_bytes = 0
    on_disk = 0
    for ref, e in rows:
        m = e.get("master") or {}
        imgs = e.get("images") or []
        photo_n += len(imgs)
        kind = ("rendered" if m.get("rendered")
                else "composite" if imgs else "bitonal")
        kinds[kind] = kinds.get(kind, 0) + 1
        masters[f"{m.get('w')}x{m.get('h')}"] = (
            masters.get(f"{m.get('w')}x{m.get('h')}", 0) + 1)
        off = ",".join(str(v) for v in e.get("offset") or [0, 0])
        offsets[off] = offsets.get(off, 0) + 1
        p = paths.scan_for(ref, root)
        if p.exists():
            on_disk += 1
            total_bytes += p.stat().st_size
        if tick:
            tick(ref, sum(kinds.values()), len(rows))

    summary = {"pages": len(rows), "photographs": photo_n,
               "on_disk": on_disk, "bytes": total_bytes}
    summary.update({k: kinds.get(k, 0)
                    for k in ("bitonal", "composite", "rendered")})
    return {
        "census": summary,
        "masters": [{"size": k, "pages": v}
                    for k, v in sorted(masters.items(), key=lambda kv: -kv[1])],
        "offsets": [{"offset": k, "pages": v}
                    for k, v in sorted(offsets.items(), key=lambda kv: -kv[1])],
    }


def check_sources(root: Path = Path("."), meta_path: Path | None = None) -> list[dict]:
    """The PDFs on disk against the digests the manifest recorded.

    **The fuss this makes is the point.** `scans/` is derived from three files that
    live outside the repository and are reachable only through a symlink, so they
    can be replaced, re-downloaded or silently updated with nothing in the corpus
    noticing — and every coordinate in every store is keyed to pixels cut from a
    particular byte sequence. A changed source is not necessarily a disaster; it is
    a thing that must not be discovered later.

    Three findings and they are different, which is why each carries `gates`:
    `source-changed` is a digest mismatch and gates; `source-absent` is a source
    the manifest names that is not on this machine, and `unrecorded` is a manifest
    written before this block existed. **Neither of those two gates**, because
    neither is a disagreement — the links dangle in every worktree and on any clone
    that has not fetched the PDFs, and a corpus that cannot see its sources has not
    thereby lost them. A check that failed there would be a check every clone
    learns to ignore.
    """
    meta = manifest_meta(meta_path if meta_path is not None else root / PDF_IMAGES)
    recorded = meta.get("_sources") or {}
    if not recorded:
        return [{"ref": "", "finding": "unrecorded", "gates": False,
                 "detail": "the manifest records no source digests; re-run "
                           "`scans extract --all --commit` to add them"}]
    out = []
    on_disk = {}
    for p in sorted((root / "pdfs").glob("*.pdf")):
        if p.exists():
            on_disk[p.name] = p
    for part, rec in sorted(recorded.items()):
        name = rec.get("file", "")
        p = on_disk.get(name)
        if p is None:
            out.append({"ref": f"part {part}", "finding": "source-absent",
                        "gates": False, "detail": f"{name} is not in pdfs/ (a worktree's links "
                                  "dangle; not a defect by itself)"})
            continue
        got = _digest(p)
        if got != rec.get("sha256"):
            out.append({"ref": f"part {part}", "finding": "source-changed",
                        "gates": True, "detail": f"{name} is sha256 {got[:16]}…, the manifest "
                                  f"recorded {str(rec.get('sha256'))[:16]}… — "
                                  "the rasters were cut from a different file"})
    return out


def audit(refs: list[str] | None = None, root: Path = Path("."),
          tree: Path | None = None, manifest: dict | None = None,
          tick=None) -> list[dict]:
    """The manifest against a tree of rasters. One function, two callers.

    `scans audit` runs it over `scans/` and the committed manifest; `swap` runs it
    over the cut tree and the manifest that tree carries, before it moves anything.
    Same findings, same wording — a check that said something different depending on
    who asked would be two checks.

    Findings only: a page that is present, right-sized and right-moded says nothing.
    """
    tree = tree if tree is not None else root / farms.SCANS
    meta_path = (tree / TREE_MANIFEST) if manifest is not None else root / PDF_IMAGES
    manifest = manifest if manifest is not None else pdf_images(root)
    want = {norm_ref(r) for r in refs} if refs else None

    out = check_sources(root, meta_path)
    # **One row, not one per page.** A tree cut before the provenance chunk existed
    # is *entirely* unwitnessed, and 832 identical rows bury the findings that are
    # about a page. It is still said, and said with its count, because a silence
    # here would read as "every raster is witnessed".
    unwitnessed: list[str] = []
    # Part number -> the digest the manifest says that part's pages were cut from,
    # which is what each raster's own chunk is checked against.
    recorded_sha = {part: (rec.get("sha256") or "") for part, rec
                    in (manifest_meta(meta_path).get("_sources") or {}).items()}
    seen = set()
    todo = [(r, e) for r, e in manifest.items() if want is None or r in want]
    for ref, e in todo:
        seen.add(ref)
        if tick:
            tick(ref, len(seen), len(todo))
        m = e.get("master") or {}
        facts = _raster_facts(tree / f"chukchi-{ref}.png")
        if not facts["on_disk"]:
            out.append({"ref": ref, "finding": "missing", "gates": True,
                        "detail": f"manifest has {m.get('w')}x{m.get('h')}, "
                                  "no raster"})
            continue
        if facts.get("why"):
            out.append({"ref": ref, "finding": "unreadable", "gates": True,
                        "detail": facts["why"]})
            continue
        want_px = f"{m.get('w')}x{m.get('h')}"
        if facts["px"] != want_px:
            out.append({"ref": ref, "finding": "size", "gates": True,
                        "detail": f"raster {facts['px']}, manifest {want_px}"})
        # **Mode is checked against what the source is, not against a list of modes
        # seen.** A bitonal page that came back `L` means something resampled it,
        # which is the entire failure this tree was rebuilt to undo.
        expect = ("RGB" if m.get("rendered")
                  else "L" if e.get("images") else "1")
        if facts["mode"] != expect:
            out.append({"ref": ref, "finding": "mode", "gates": True,
                        "detail": f"raster {facts['mode']}, expected {expect}"})
        # **The raster's own account of itself, against the manifest's.** These are
        # two independent records of the same cut — the chunk was written into the
        # PNG and the entry into the JSON — so a disagreement means one of them
        # belongs to a different run. A page carrying no chunk is `unwitnessed`
        # rather than wrong: it predates the block, and saying otherwise would make
        # every raster cut before today read as a defect.
        prov = read_png_provenance(tree / f"chukchi-{ref}.png")
        cut_sha = prov.inputs.get("source_sha256", "") if prov else ""
        if prov is None:
            unwitnessed.append(ref)
        elif (recorded_sha and cut_sha
              and cut_sha != recorded_sha.get(ref.split("-")[0], "")):
            out.append({"ref": ref, "finding": "source-mismatch", "gates": True,
                        "detail": f"raster was cut from sha256 {cut_sha[:16]}…, "
                                  "the manifest records another for this part"})

    if tree.is_dir():
        for p in sorted(tree.glob("chukchi-*.png")):
            ref = norm_ref(p.stem)
            if want is not None and ref not in want:
                continue
            if ref not in seen and ref not in manifest:
                out.append({"ref": ref, "finding": "orphan", "gates": True,
                            "detail": "raster with no manifest entry"})

    if unwitnessed:
        shown = ", ".join(unwitnessed[:3])
        out.append({"ref": "", "finding": "unwitnessed", "gates": False,
                    "detail": f"{len(unwitnessed)} rasters carry no provenance "
                              f"chunk ({shown}…): cut before the block existed. "
                              "Re-cut and swap to witness them"})
    return out


def space(refs: list[str] | None = None, root: Path = Path("."),
          tick=None) -> list[dict]:
    """Which coordinate space every store page declares, by its own page box.

    **This gates**, where measurement usually does not. The migration into master
    space is complete and has a receipt; a page still declaring the legacy render's
    box, or a box that is neither, is a defect that will silently mis-place every
    coordinate on it. Reporting that at exit 0 would be filing a fault as a fact.
    """
    from lxml import etree

    from .migrate import STORES, page_box

    manifest = pdf_images(root)
    want = {norm_ref(r) for r in refs} if refs else None
    # The work-list first, because the bar's denominator is every store's pages
    # together and no one store knows it — `pmap`'s rule, hand-rolled.
    todo = [(store, p) for store in STORES
            if (root / store).is_dir()
            for p in sorted((root / store).glob("chukchi-*.xml"))
            if want is None or norm_ref(p.stem) in want]
    out = []
    for n, (store, p) in enumerate(todo, start=1):
        ref = norm_ref(p.stem)
        if tick:
            tick(ref, n, len(todo))
        try:
            box = page_box(etree.parse(str(p)))
        except etree.XMLSyntaxError as e:
            out.append({"ref": ref, "store": store, "box": "",
                        "space": "unparseable", "detail": str(e)[:60]})
            continue
        entry = manifest.get(ref, {})
        _, name = rects_in(entry, box[0], box[1])
        out.append({"ref": ref, "store": store,
                    "box": f"{box[0]}x{box[1]}",
                    "space": name or ("no-entry" if not entry else "neither"),
                    "detail": ""})
    return out


# --- the swap -----------------------------------------------------------------

def geometry_dependents(root: Path = Path(".")) -> list[dict]:
    """Everything keyed to the rasters' geometry, and how each answers a shift.

    **Composed from what already declares itself**, never re-enumerated here. The
    coordinate stores are `migrate.STORES`; the painted trees are the farms whose
    own `reads` names `scans/`. That last rule is doing real work rather than
    restating a list: it *excludes* the `select` leaf farms (`scans/plate/` and the
    rest), which are links by filename and unaffected by a shift, and a filter on
    `kind` would have discarded them for nothing.

    `gt/page-img/` and `gt/fig-img/` are absent on purpose and reported by `swap`
    instead: they are a human's touch-ups cut from a raster, so a geometry change
    makes them stale — but nothing mechanical may rewrite an authored image, and a
    tool that silently regenerated one would be overwriting the only copy of work no
    script can reproduce.
    """
    from .migrate import BAND_FILES, DROP_FILES, STORES

    out = [{"dependent": s, "kind": "coordinates", "response": "translated",
            "rebuild": ""} for s in STORES]
    out += [{"dependent": b, "kind": "bands", "response": "y-shifted",
             "rebuild": ""} for b in BAND_FILES]
    out += [{"dependent": d, "kind": "cache", "response": "dropped",
             "rebuild": "refilled on next use"} for d in DROP_FILES]
    for f in farms.FARMS:
        if f.kind == "raster" and farms.SCANS in f.reads:
            out.append({"dependent": f.path, "kind": "painted",
                        "response": "discarded", "rebuild": f.builder})
    # **`paths.DERIVED`, not `review/`.** A review directory holds `proposal.json`
    # and `decision.json`, both tracked and neither derived from a raster; only the
    # crops, sheets, zoom, numbered page and rendered HTML are pixels. Discarding
    # the directory would take a pass's adjudicated readings with it.
    out += [{"dependent": f"review/*/{d}", "kind": "derived images",
             "response": "discarded", "rebuild": "harness ocr crops / sheets / zoom"}
            for d in paths.DERIVED]
    return out


#: Authored images cut from a raster. **Reported, never touched.**
TOUCHED_UP = ("gt/page-img", "gt/fig-img")


def _tree_manifest(tree: Path) -> dict[str, dict]:
    return read_manifest(tree / TREE_MANIFEST)


def swap(tree: Path, root: Path = Path("."), commit: bool = False) -> dict:
    """Install a cut tree, and move everything keyed to its geometry with it.

    Swapping the rasters is the cheap half — they are `#mz`, and a bad one costs a
    re-run. The point of the verb is the other half: six coordinate stores, two band
    ledgers, a cache whose stamp cannot see a raster change, the painted farms and
    the review working set all describe pixels in the *old* master's space, and a
    tree installed without them is a corpus where every box is silently off by the
    difference between two placements.

    **What "atomic" can honestly mean across six trees.** Not one syscall. The
    guarantee here is stage-verify-move plus a receipt: every store's translation is
    computed and digest-checked before anything is written, any refusal aborts the
    whole run with nothing moved, and `data/_migrated.json` records which manifest
    the stores are now in. That last part is not ceremony — a zero shift leaves a
    page byte-identical, so "correctly untouched" and "not yet reached" cannot be
    told apart by looking, which is what the receipt is for.
    """
    from . import migrate

    new = _tree_manifest(tree)
    rep: dict = {"swap": {"tree": str(tree), "committed": False},
                 "refusals": [], "shifts": [], "dependents": [],
                 "touched_up": [], "stores": {}}
    if not new:
        rep["refusals"].append({"what": str(tree / TREE_MANIFEST),
                                "why": "no manifest; a tree of rasters with no "
                                       "geometry cannot be placed"})
        return rep

    old = pdf_images(root)
    plan = migrate.plan(old, new)
    rep["shifts"] = [{"ref": r, "shift": f"{p['shift'][0]},{p['shift'][1]}",
                      "from": "x".join(str(v) for v in p["from"]),
                      "to": "x".join(str(v) for v in p["to"]),
                      "scaled": p["scaled"]}
                     for r, p in sorted(plan.items(), key=lambda kv: parse_ref(kv[0]))
                     if p["shift"] != (0, 0) or p["from"] != p["to"]]

    # The tree must be what its own manifest says before any of this is believed —
    # the gating findings only, on `run_audit`'s reasoning: a tree cut on a machine
    # that has the PDFs and swapped on one that does not is an ordinary state.
    for f in audit(None, root, tree=tree, manifest=new):
        if f["gates"]:
            rep["refusals"].append({"what": f["ref"],
                                    "why": f"{f['finding']}: {f['detail']}"})

    # Dry-run the migration whatever happens: its refusals are findings the caller
    # needs *before* deciding, and running it twice is cheap next to a half-moved
    # corpus.
    dry = migrate.run(root, refs=None, commit=False, old=old, new=new)
    rep["stores"] = {k: dry.get(k, 0) for k in
                     ("migrated", "already", "aborted", "clamped", "clamped_gt")}
    rep["files"] = [f for f in dry["files"] if f["action"] == "ABORTED"]
    for f in rep["files"]:
        rep["refusals"].append({"what": f"{f.get('store', '')}/{f['ref']}",
                                "why": f["why"]})

    rep["dependents"] = geometry_dependents(root)
    rep["touched_up"] = [{"path": t, "files": len(list((root / t).glob("*")))
                          if (root / t).is_dir() else 0,
                          "note": "authored; re-cut by hand if the geometry moved"}
                         for t in TOUCHED_UP]

    if not commit or rep["refusals"]:
        return rep

    # --- past this line the stage has been verified; what follows is the move ----
    migrate.run(root, refs=None, commit=True, old=old, new=new)
    write_manifest({"_about": ABOUT, **new}, root / PDF_IMAGES)

    # **The old tree is moved aside, not deleted, until the new one is in place.**
    # Deleting first leaves a window where a failed move — a full disk, a rename
    # across filesystems interrupted — has taken `scans/` and not replaced it. The
    # aside is removed only once the new tree has arrived.
    #
    # A symlink is unlinked rather than walked: a worktree commonly has `scans/`
    # pointing at the primary checkout's, and `rmtree` through that link would
    # delete the real corpus.
    dest = root / farms.SCANS
    aside = None
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        aside = dest.with_name(f"{dest.name}.swapping.{os.getpid()}")
        dest.rename(aside)
    try:
        shutil.move(str(tree), str(dest))
    except OSError:
        if aside is not None:
            aside.rename(dest)
        raise
    if aside is not None:
        shutil.rmtree(aside)
    (dest / TREE_MANIFEST).unlink(missing_ok=True)

    discarded = []
    for dep in rep["dependents"]:
        if dep["kind"] not in ("painted", "derived images"):
            continue
        pat = dep["dependent"]
        for p in (sorted(root.glob(pat)) if "*" in pat else [root / pat]):
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            else:
                continue
            discarded.append(str(p.relative_to(root)))
    rep["swap"]["discarded"] = len(discarded)
    rep["swap"]["committed"] = True
    return rep
