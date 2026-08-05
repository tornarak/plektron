"""Human line corrections, and the line half of the ink question.

Two ink checks run over these pages and they ask **different questions**:

- `zones check --ink` asks *is this ink inside any zone?* Ink outside every
  region is a defect in the zoning — a column the segmenter missed, a marginal
  note nobody boxed.
- `ocr gaps` asks *is this in-zone ink inside any line?* Ink a zone covers but no
  `TextLine` does is a dropped line — the fault that is invisible to every
  text-level check, because the text that is there is correct and so nothing
  disagrees with anything.

They were sharing one exemption file, and that made a ruling about one question
silently answer the other. A band marked "scanner smudge" during zoning — a
statement about what the *zoning* need not cover — also stopped the line check
from ever reporting that strip of paper again. The two are now one file each,
written by their own editor, and **overlaid rather than merged**: each band is
settled by the layer whose question it belongs to, and each editor shows the
other layer so a human can see that the neighbouring check has already spoken.

The boundary between them is a mutual audit. A band this layer finds *outside*
every zone is not this layer's business, and it is either a zone-check miss or a
standing zone-level ruling — which is why `ocr edit` reads both files and refuses
to record a correction out there, naming `zones edit` instead.

**The mechanism is shared, the meaning is not.** A ruling is band-scoped and
carries a required reason in both layers, so that core lives here and `zones.py`
calls it for its own directory. What differs is only which question the file
answers, which is what the `_about` blurb in each file says.
"""
from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

from .context import norm_ref, parse_ref

INK_EXEMPT_JSON = "_ink_exempt.json"

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

# Provenance travelling with the data, as `zones.ID_PREFIX` does. A line whose id
# starts with this was drawn by a human in `ocr edit` over ink the segmenter left
# unboxed; nothing else in any store carries it.
CORR_ID_PREFIX = "corr_"

LINE_EXEMPT_ABOUT = (
    "Bands of ink **inside a zone** that a human has ruled are not a dropped "
    "line — a printed rule, a footnote separator, a smudge the zoning covers. "
    "Each carries the reason it was ruled so, and each is scoped to its own "
    "band: exempting a whole page would hide the next dropped line on it. A "
    "matched band still reports, flagged `exempted` and carrying its note. This "
    "is the *line* layer; ink outside every zone is the zoning's question and "
    "lives in gt/zones/_ink_exempt.json. Keyed PP-NNN.")


def lines_dir(root: Path = Path(".")) -> Path:
    """The line-correction store. Authored and tracked, like `gt/zones/`."""
    return Path(root) / "gt" / "lines"


def lines_path(ref: str, root: Path = Path(".")) -> Path:
    return lines_dir(root) / f"chukchi-{norm_ref(ref)}.xml"


# --------------------------------------------------------------- the fragment

def load_lines(ref: str, root: Path = Path(".")) -> list[dict]:
    """This page's corrections, in raster coordinates. `[]` when there are none.

    No file means no human has drawn a line on this page — the same
    file-existence-is-the-record rule `gt/zones/` follows. There is deliberately
    no way to express "looked and found nothing" here: unlike a zoning, which
    partitions the whole page and can legitimately be empty, a correction store
    with no corrections in it says exactly what its absence says.
    """
    p = lines_path(ref, root)
    if not p.exists():
        return []
    root_el = etree.parse(str(p)).getroot()
    page = root_el.find(".//{*}Page")
    pw = int(page.get("WIDTH") or 0) if page is not None else 0
    ph = int(page.get("HEIGHT") or 0) if page is not None else 0
    out = []
    for tl in root_el.iter("{*}TextLine"):
        s = tl.find("{*}String")
        x, y = int(tl.get("HPOS")), int(tl.get("VPOS"))
        w, h = int(tl.get("WIDTH")), int(tl.get("HEIGHT"))
        out.append({"id": tl.get("ID"), "x0": x, "y0": y, "x1": x + w,
                    "y1": y + h, "text": (s.get("CONTENT") or "") if s is not None
                    else "", "page_w": pw, "page_h": ph})
    return sorted(out, key=lambda r: (r["y0"], r["x0"]))


def build_fragment(ref: str, boxes: list[dict], size: tuple[int, int]):
    """The store's ALTO, in the dialect `page_lines` already parses.

    Lifted from the late `lines.adopt_gaps`, which built exactly this shape
    in-place inside `gt/ocr/`. What changes is only where it lands: a file of its
    own, at raster scale, folded over whichever store answers for the page — so a
    correction is reachable on the ~690 pages that have no ground truth, which is
    the whole reason that verb could not do this job.

    **The `String` is empty by construction**, and the legitimacy of this writer
    rests on it exactly as it rested on `adopt_gaps`: the editor draws a box, and
    nothing here originates a reading. Text arrives later, from `restore`, out of
    an adjudicated decision.
    """
    w, h = size
    nsmap = {None: ALTO_NS}
    root_el = etree.Element(f"{{{ALTO_NS}}}alto", nsmap=nsmap)
    layout = etree.SubElement(root_el, f"{{{ALTO_NS}}}Layout")
    page = etree.SubElement(layout, f"{{{ALTO_NS}}}Page", {
        "ID": f"corr_page_{ref}", "PHYSICAL_IMG_NR": "1",
        "WIDTH": str(w), "HEIGHT": str(h)})
    ps = etree.SubElement(page, f"{{{ALTO_NS}}}PrintSpace", {
        "HPOS": "0", "VPOS": "0", "WIDTH": str(w), "HEIGHT": str(h)})
    for b in boxes:
        x, y = int(b["x0"]), int(b["y0"])
        bw, bh = int(b["x1"]) - x, int(b["y1"]) - y
        ident = b.get("id") or f"{CORR_ID_PREFIX}{ref}-{y}"
        geom = {"HPOS": str(x), "VPOS": str(y),
                "WIDTH": str(bw), "HEIGHT": str(bh)}
        rect = f"{x} {y} {x + bw} {y} {x + bw} {y + bh} {x} {y + bh}"
        blk = etree.SubElement(ps, f"{{{ALTO_NS}}}TextBlock",
                               {"ID": f"{ident}_block", **geom})
        etree.SubElement(etree.SubElement(blk, f"{{{ALTO_NS}}}Shape"),
                         f"{{{ALTO_NS}}}Polygon", {"POINTS": rect})
        tl = etree.SubElement(blk, f"{{{ALTO_NS}}}TextLine", {
            "ID": ident, "BASELINE": f"{x} {y + bh} {x + bw} {y + bh}", **geom})
        etree.SubElement(etree.SubElement(tl, f"{{{ALTO_NS}}}Shape"),
                         f"{{{ALTO_NS}}}Polygon", {"POINTS": rect})
        etree.SubElement(tl, f"{{{ALTO_NS}}}String",
                         {"CONTENT": b.get("text") or "", **geom})
    return etree.ElementTree(root_el)


def save_lines(ref: str, boxes: list[dict], root: Path = Path(".")) -> dict:
    """Write this page's corrections. No store parameter, on purpose.

    `save_zones`' property: there is no argument in which to name somewhere else,
    so nothing can write a human's geometry into a machine store by passing the
    wrong string. Durability is that function's too — `.prev` beside the file,
    write to `.tmp`, `replace`.

    **An empty save deletes the file**, which is the opposite of `save_zones`'
    rule and for the same underlying reason. There, an empty page and an unvisited
    page are byte-identical, so an empty save would erase the difference between
    having judged and not; here the file's *existence* is the whole record, and a
    file holding no corrections would claim a human drew something when they
    withdrew everything. Withdrawing the last correction is a real act and this is
    how it is recorded.

    **Text already in the store is carried forward by id**, never taken from the
    caller for a line that already exists. The editor is geometry-only and has no
    business round-tripping an adjudicated reading through a browser; but a human
    who nudges a box after `restore` has written its text must not thereby lose
    it. The id is minted from the position where the line was first drawn and
    then travels with it, so moving a box keeps its text.
    """
    from .zones import raster_size
    ref = norm_ref(ref)
    p = lines_path(ref, root)

    keep = {r["id"]: r["text"] for r in load_lines(ref, root) if r["text"]}
    boxes = [dict(b, text=b.get("text") or keep.get(b.get("id"), ""))
             for b in boxes or []]

    if not boxes:
        existed = p.exists()
        if existed:
            p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
            p.unlink()
        return {"ref": ref, "path": str(p), "lines": 0, "removed": existed}

    tree = build_fragment(ref, boxes, raster_size(ref, root))
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    tmp = p.with_suffix(".xml.tmp")
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
               standalone=None, pretty_print=True)
    tmp.replace(p)
    return {"ref": ref, "path": str(p), "lines": len(boxes), "removed": False}


# --------------------------------------------------------------- the shared core

def load_exemptions(store: Path) -> dict[str, list[dict]]:
    """Every ruling in one layer's file, keyed by ref. `{}` when absent."""
    p = Path(store) / INK_EXEMPT_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A corrupt file reads as no rulings, which makes every band on every
        # ruled page report again. That is the safe direction for a detector
        # whose failure mode is silence — over-reporting is noise, under-
        # reporting is a dropped line nobody hears about.
        return {}
    return {k: list(v) for k, v in data.items() if not k.startswith("_")}


def clean_regions(ref: str, regions: list[dict] | None) -> list[dict]:
    """Validate and normalise one page's rulings.

    **A reason is required and is the point of the file.** Every suppression is a
    claim that something on the paper is not what the check took it for, and
    "the tool complained and I made it stop" is not a record of anything. A year
    from now the note is the only thing that distinguishes a ruled artifact from
    a hidden mistake.
    """
    clean = []
    for r in regions or []:
        note = (r.get("note") or "").strip()
        if not note:
            raise ValueError(
                f"ink exemption for {ref} at y={r.get('y0')} has no reason — the "
                "reason is the record; without it the entry is indistinguishable "
                "from a hidden mistake")
        y0, y1 = sorted((int(r["y0"]), int(r["y1"])))
        clean.append({"y0": y0, "y1": y1, "note": note})
    clean.sort(key=lambda r: r["y0"])
    return clean


def write_exemptions(store: Path, data: dict[str, list[dict]],
                     about: str) -> Path:
    """One layer's file, refs in page order, carrying what it is for."""
    p = Path(store) / INK_EXEMPT_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    doc: dict = {"_about": about}
    doc.update({k: data[k] for k in sorted(data, key=parse_ref)})
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    return p


def ink_excuse(band: dict, regions: list[dict]) -> dict | None:
    """The recorded region covering this band, if any.

    Matched on the band's **midpoint**, not on its edges: the band is re-measured
    from the raster on every run and its exact extent moves by a pixel or two with
    any change to a neighbouring zone, so an edge test would silently stop matching.
    The midpoint is stable, and regions are stored tight enough that it cannot
    wander into a neighbouring finding.
    """
    mid = band["vpos"] + band["height"] / 2
    for r in regions:
        if r["y0"] <= mid <= r["y1"]:
            return r
    return None


# --------------------------------------------------------------- the line layer

def load_ink_exempt(root: Path = Path(".")) -> dict[str, list[dict]]:
    """Line-level rulings: bands inside a zone that are not dropped lines."""
    return load_exemptions(lines_dir(root))


def set_ink_exempt(ref: str, regions: list[dict],
                   root: Path = Path(".")) -> dict:
    """Record bands inside a zone that a human has ruled are not a line.

    Scoped to a band, never to the page: the next dropped line on the same leaf
    must still report. The zone layer's equivalent is `zones.set_ink_exempt`, and
    the two files are never merged — see this module's docstring for why.
    """
    ref = norm_ref(ref)
    clean = clean_regions(ref, regions)
    data = load_ink_exempt(root)
    if clean:
        data[ref] = clean
    else:
        data.pop(ref, None)
    write_exemptions(lines_dir(root), data, LINE_EXEMPT_ABOUT)
    return {"ref": ref, "ink_exempt": data.get(ref, [])}
