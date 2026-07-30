"""The figure-caption track: `fig/` for geometry, `data/readings.md` for text.

**The two are separate stores and neither substitutes for the other.** The 252
figure ALTOs in `fig/` carry `GraphicZone` blocks (the images) and
`GraphicZone-FigDesc` blocks (where a caption sits) — 414 and 395 of them
respectively — and **no `TextLine` at all**: every line was stripped, because the
exported line segmentation dropped whole printed lines and a line-level witness
in the ALTO would have silently disagreed with the readings. So the caption text
lives only in `data/readings.md`, one block per FigDesc zone, keyed
`<ref>|<zone-id suffix>` and read by hand off the 300 dpi scans.

Anything that wants caption text must go through `readings()`. Reading
`String/@CONTENT` out of `fig/` returns the empty string for every zone on every
page — not an error, just nothing, which is the worst possible failure here.

There is no longer a keyed/unkeyed boundary. All 395 captions in
`data/readings.md` are hand-read, so the old `KEYED_COUNT = 50` marker is gone;
`fig/` and `data/readings.md` reconcile 1:1 in both directions, and that
reconciliation is the check worth running — `reconcile()` below.

Zone types are read from `OtherTag/@LABEL`, never from the tag ID. The IDs are
per-export (`BT55`/`BT56` in one export, `BT68`/`BT69` in the next) and code
that hardcodes them fails silently rather than loudly.
"""
from __future__ import annotations
import re, unicodedata
from pathlib import Path
from lxml import etree

from .context import norm_ref, parse_ref

GRAPHIC = "GraphicZone"
FIGDESC = "GraphicZone-FigDesc"

FIGDIR = "fig"
READINGS = "data/readings.md"


def _labels(tree) -> dict[str, str]:
    return {t.get("ID"): t.get("LABEL", "") for t in tree.iter("{*}OtherTag")}


def _block_label(blk, labels: dict[str, str]) -> str:
    """First non-empty zone label on a block. TAGREFS is space-separated."""
    for r in (blk.get("TAGREFS") or "").split():
        if labels.get(r):
            return labels[r]
    return ""


def _bbox(el) -> dict | None:
    """HPOS/VPOS/WIDTH/HEIGHT as ints.

    Parsed as float first: eScriptorium writes these as `"365.0"`, which is not
    `str.isdigit()`. Assuming otherwise is how `context._figures_on_page` came
    to hand the model an empty bbox for all 250 pages.
    """
    vals = {}
    for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"):
        v = el.get(k)
        if v is None:
            return None
        try:
            vals[k] = round(float(v))
        except ValueError:
            return None
    return vals


def fig_refs(root: Path = Path(".")) -> list[str]:
    """Every ref with a figure-track ALTO, in (part, scan index) order."""
    refs = []
    for p in (root / FIGDIR).glob("chukchi-*.xml"):
        try:
            refs.append(norm_ref(p.stem))
        except ValueError:
            continue
    return sorted(set(refs), key=parse_ref)


def alto_for(ref: str, root: Path = Path(".")) -> Path:
    return root / FIGDIR / f"chukchi-{norm_ref(ref)}.xml"


# Adjudication keywords that may open a reading's `@note`. The first two are
# terminal — the page was re-examined and the question is closed. The rest mark
# work outstanding. Kept here so a consumer can filter on them without
# re-deriving the vocabulary from prose. Order is longest-first so that a prefix
# match cannot shadow a longer keyword.
NOTE_KEYWORDS = (
    "CONFLICT WITH THE LIST OF ILLUSTRATIONS",
    "KEYING REQUIRED",
    "ZONE TOO SMALL",
    "ZONE MISPLACED",
    "VERBATIM",
    "MISPRINT",
)
TERMINAL_KEYWORDS = ("VERBATIM", "MISPRINT")

_HDR = re.compile(r"^## (\S+?)\|(\S+)$", re.M)


def readings(root: Path = Path(".")) -> dict[str, dict]:
    """`data/readings.md` parsed to `{"<ref>|<zone-suffix>": record}`.

    **This is the only source of caption text.** `fig/` carries no `TextLine`.

    `lines` preserves the printed line breaks and the printed hyphenation —
    hyphens are load-bearing in Americanist notation, so joining is a rendering
    decision made downstream, not here. `note` is the raw `@note` text if any,
    and `keyword` the adjudication keyword it opens with, if any.

    A `**bold heading**` on its own line ends the reading and opens trailing
    commentary, kept out of `lines`/`text` and returned as `aside`. `2-030` uses
    this to park a superseded machine attempt beside the human key for
    comparison; folding the two together would have produced 53 lines of two
    different transcriptions of one caption, presented as the caption.
    """
    # NFD on read, matching the corpus form (keying spec section 1). The file is
    # hand-maintained and nothing but `harness normalize` writes it, so it can drift
    # between edits; folding here means a caption's normal form cannot depend on
    # which session keyed it. NFD, never NFKC — NFKC rewrites U+1D4B and U+02D9,
    # which are inventory glyphs.
    text = unicodedata.normalize(
        "NFD", (root / READINGS).read_text(encoding="utf-8"))
    hits = list(_HDR.finditer(text))
    out = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[m.end():end].strip("\n")
        note = ""
        if "\n@note:" in "\n" + body:
            body, _, note = body.partition("@note:")
            note = note.strip()
        aside = ""
        cut = re.search(r"^\*\*.*\*\*\s*$", body, re.M)
        if cut:
            body, aside = body[:cut.start()], body[cut.start():].strip()
        lines = [l for l in body.strip().split("\n") if l.strip()]
        out[f"{m.group(1)}|{m.group(2)}"] = {
            "ref": m.group(1),
            "zone_suffix": m.group(2),
            "lines": lines,
            "text": " ".join(lines),
            "note": note,
            "keyword": next((k for k in NOTE_KEYWORDS if note.startswith(k)), ""),
            "aside": aside,
        }
    return out


def readings_for(ref: str, root: Path = Path(".")) -> dict[str, dict]:
    """The readings on one page, keyed by bare zone-id suffix."""
    ref = norm_ref(ref)
    return {r["zone_suffix"]: r for r in readings(root).values()
            if r["ref"] == ref}


def caption_blocks(path: Path, root: Path = Path(".")) -> list[dict]:
    """FigDesc zones on one page, in document order, with their reading.

    Geometry comes from the ALTO, text from `data/readings.md`. A zone with no
    reading is a reconciliation failure, not an empty caption, so it is reported
    with `reading: None` rather than an empty string — see `reconcile()`.
    """
    tree = etree.parse(str(path))
    labels = _labels(tree)
    try:
        ref = norm_ref(Path(path).stem)
        by_zone = readings_for(ref, root)
    except ValueError:
        by_zone = {}
    out = []
    for blk in tree.iter("{*}TextBlock"):
        if _block_label(blk, labels) != FIGDESC:
            continue
        zid = blk.get("ID") or ""
        out.append({
            "zone_id": zid,
            "bbox": _bbox(blk),
            "reading": by_zone.get(zid[-8:]),
        })
    return out


def reconcile(root: Path = Path(".")) -> dict:
    """Cross-check `fig/` against `data/readings.md` in both directions.

    Empty `missing` and `orphan` lists is the invariant. `missing` means a zone
    whose caption was never read; `orphan` means a reading whose zone is gone —
    usually a spurious FigDesc that was deleted from the segmentation, in which
    case the reading should go too.
    """
    known = readings(root)
    missing, orphan = [], []
    zones, caps = 0, 0
    for ref in fig_refs(root):
        tree = etree.parse(str(alto_for(ref, root)))
        labels = _labels(tree)
        ids = set()
        for blk in tree.iter("{*}TextBlock"):
            lab = _block_label(blk, labels)
            if lab == GRAPHIC:
                zones += 1
            elif lab == FIGDESC:
                caps += 1
                ids.add((blk.get("ID") or "")[-8:])
        have = {r["zone_suffix"] for r in known.values() if r["ref"] == ref}
        missing += [f"{ref}|{z}" for z in sorted(ids - have)]
        orphan += [f"{ref}|{z}" for z in sorted(have - ids)]
    seen_refs = {r["ref"] for r in known.values()}
    orphan += [k for k, r in sorted(known.items())
               if r["ref"] not in set(fig_refs(root))]
    return {
        "pages": len(fig_refs(root)),
        "graphic_zones": zones,
        "figdesc_zones": caps,
        "readings": len(known),
        "refs_in_readings": len(seen_refs),
        "missing": missing,
        "orphan": sorted(set(orphan)),
    }


def graphic_zones(path: Path) -> list[dict]:
    """GraphicZone blocks — geometry only; these never carry text."""
    tree = etree.parse(str(path))
    labels = _labels(tree)
    return [{"zone_id": blk.get("ID"), "bbox": _bbox(blk)}
            for blk in tree.iter("{*}TextBlock")
            if _block_label(blk, labels) == GRAPHIC]


def snapshot(root: Path = Path(".")) -> dict:
    """Every FigDesc zone with its reading, keyed by ref. Geometry + text."""
    out = {}
    for ref in fig_refs(root):
        blocks = caption_blocks(alto_for(ref, root), root)
        if blocks:
            out[ref] = blocks
    return out


# ---------------------------------------------------------------------------
# Caption crops
#
# Crops are taken from the FigDesc **zone box**. There is nothing else left to
# crop from — the per-line boxes are gone with the TextLines — but the zone box
# was the right unit anyway: the line segmentation used to drop whole printed
# lines (on `1-146` it lost "Boot of Curried Reindeer-Skin." out of the middle of
# fig. 27's caption), and a zone crop keeps a dropped line visible where a line
# crop would reproduce the loss. This is the path back to the page when a reading
# is in doubt.

PAD = 12          # px of margin around a zone crop, at the raster's resolution
SHEET_W = 1800    # composite sheet width
GUTTER = 14       # vertical space between strips
LABEL_W = 90      # left margin reserved for the index number

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _scale_for(alto_page, image_size) -> tuple[float, float]:
    """Ratio between the ALTO's coordinate space and the raster's.

    Returns (1.0, 1.0) once the two agree. Deriving this rather than assuming
    it means crops are correct whether or not the coordinate rescale has run,
    and it never hardcodes 2 — no page is exactly double (see CLAUDE.md).
    """
    aw = float(alto_page.get("WIDTH"))
    ah = float(alto_page.get("HEIGHT"))
    return image_size[0] / aw, image_size[1] / ah


def caption_crops(ref: str, root: Path = Path("."), scans: str = "scans"):
    """(zone_id, PIL.Image) per FigDesc zone on one page, cropped from the raster."""
    from PIL import Image
    ref = norm_ref(ref)
    alto = alto_for(ref, root)
    tree = etree.parse(str(alto))
    page = tree.find(".//{*}Page")
    img = Image.open(root / scans / f"chukchi-{ref}.png")
    sx, sy = _scale_for(page, img.size)

    for blk in caption_blocks(alto, root):
        bb = blk["bbox"]
        if not bb:
            continue
        box = (max(0, round(bb["HPOS"] * sx) - PAD),
               max(0, round(bb["VPOS"] * sy) - PAD),
               min(img.size[0], round((bb["HPOS"] + bb["WIDTH"]) * sx) + PAD),
               min(img.size[1], round((bb["VPOS"] + bb["HEIGHT"]) * sy) + PAD))
        crop = img.crop(box)
        # Some captions are set vertically beside their figure (`1-192`'s
        # Fig. 66, `1-202`'s Fig. 82). Left as-is they are unreadable in a
        # composite and eat a whole sheet's height, so rotate them upright.
        # Threshold is deliberately lax: printed captions are wide and short,
        # so anything markedly taller than it is wide is set vertically.
        if crop.height > crop.width * 1.8:
            crop = crop.rotate(-90, expand=True)
        yield blk["zone_id"], crop


def compose_sheets(items, out_dir: Path, per_sheet: int = 10, prefix: str = "sheet"):
    """Tile (label, image) pairs into indexed composite sheets.

    Each strip gets its index drawn in the left margin and a rule beneath it, so
    a reading can be keyed back to a zone without relying on order alone. Strips
    wider than the sheet are scaled down; nothing is scaled up, since upsampling
    print costs legibility for no gain.
    """
    from PIL import Image, ImageDraw, ImageFont
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype(FONT_PATH, 26)
    except OSError:
        font = ImageFont.load_default()

    sheets, index = [], []
    for start in range(0, len(items), per_sheet):
        chunk = items[start:start + per_sheet]
        scaled = []
        for label, im in chunk:
            avail = SHEET_W - LABEL_W - 20
            if im.width > avail:
                h = max(1, round(im.height * avail / im.width))
                im = im.resize((avail, h), Image.LANCZOS)
            scaled.append((label, im))
        height = sum(im.height + GUTTER for _, im in scaled) + GUTTER
        sheet = Image.new("L", (SHEET_W, height), 255)
        draw = ImageDraw.Draw(sheet)
        y = GUTTER
        for label, im in scaled:
            sheet.paste(im.convert("L"), (LABEL_W, y))
            draw.text((10, y + 4), label.split(":")[0], fill=0, font=font)
            y += im.height + GUTTER
            draw.line([(0, y - GUTTER // 2), (SHEET_W, y - GUTTER // 2)], fill=180, width=1)
        n = len(sheets) + 1
        path = out_dir / f"{prefix}-{n:03d}.png"
        sheet.save(path)
        sheets.append(path)
        index.append({"sheet": path.name,
                      "items": [lab for lab, _ in chunk]})
    return sheets, index
