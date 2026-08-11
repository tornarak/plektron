"""The line-correction editor: `harness ocr edit`.

`zones edit`'s sibling, one stage down. That editor partitions a page into
regions; this one finds the lines a segmenter dropped *inside* those regions and
gives them a box, so that a reader or the review pass has something to point at.

**It draws and never keys.** The text of a recovered line is adjudicated in `ocr
review` like any other line's and written by `restore` — duplicating that
machinery here would be a second place a reading could be originated, and the
whole store exists on the argument that this writer cannot originate one. What a
human does here is say *there is a line here*, or *that ink is not a line*.

**Two verdicts, one sitting.** A `gaps` band is either a line the segmenter
missed or something that is not type at all — a printed rule, a footnote
separator, a smudge the zoning happens to cover. Both are recorded from the same
view of the same page, because deciding between them is one act and splitting it
across two tools is how bands get left unruled.

**A box in no zone is refused, loudly.** Ink that no region covers is a defect in
the *zoning*, not a line this editor can adopt: it means the segmentation missed
a region, and the honest response is to say so and send the human to `zones edit`
rather than to quietly paper over it one line at a time. That refusal is also
what keeps the two ink checks disjoint — see `harness/corrections.py`.

**This module no longer renders anything.** The page, its routes and its script
are `harness/web/lines.py` and the templates beside it; what stays here is the
part that would be the same whatever served it — the page's state, one row's
counts, and the save with the refusal above built into it. The split is on
purpose: `save_payload` is where the boundary this editor exists to enforce
lives, and it should not be reachable only through a request.
"""
from __future__ import annotations

from pathlib import Path

from . import corrections as corr
from . import zones as zn
from .context import norm_ref
from .lines import DEFAULT_ALTO_DIR, alto_for_lines, line_gaps, page_lines

PORT = 8733

# Where the blotted view is rendered for the toggle. Under `scans/`, which is
# ignored whole, and per-editor rather than sharing `scans/w-blotted/`: that
# directory is the corpus sweep's output and is deliberately painted *without*
# exemptions, so writing this variant into it would corrupt the one view that
# answers independently of anybody's rulings.
BLOT_CACHE = "w-blotted-edit"


def page_state(ref: str, root: Path = Path("."),
               alto_dir: str = DEFAULT_ALTO_DIR) -> dict:
    """Everything the page needs, resolved server-side.

    The client re-derives nothing: it is handed raster-space geometry for every
    layer and draws it. Same rule as the zones editor, and for the same reason —
    a browser that recomputed which store answers, or which layer settles a band,
    could disagree with the server about what it is showing.
    """
    ref = norm_ref(ref)
    w, h = zn.raster_size(ref, root)
    alto = alto_for_lines(ref, alto_dir, root)

    lines, corrected = [], []
    if alto.exists():
        # Raster space, so every layer on the page shares one coordinate system.
        page = None
        from lxml import etree
        page = etree.parse(str(alto)).find(".//{*}Page")
        aw = float(page.get("WIDTH") or w) if page is not None else w
        ah = float(page.get("HEIGHT") or h) if page is not None else h
        sx, sy = (w / aw if aw else 1.0), (h / ah if ah else 1.0)
        for r in page_lines(alto, root, ref=ref):
            if r.get("hpos") is None or r.get("vpos") is None:
                continue
            # `text` travels for the covered-by pick: the overlay draws no line
            # numbers, so the line is chosen by clicking it and the only thing
            # that confirms the right one was clicked is what it keys.
            box = {"x0": round(r["hpos"] * sx), "y0": round(r["vpos"] * sy),
                   "x1": round((r["hpos"] + r["width"]) * sx),
                   "y1": round((r["vpos"] + r["height"]) * sy),
                   "index": r["index"], "zone": r["zone"],
                   "text": r.get("text") or ""}
            (corrected if r["src"] == "corr" else lines).append(box)

    # The fragment is the authority on a correction's geometry — `page_lines`
    # scales into the ALTO's space and back would lose a pixel either way.
    stored = {c["id"]: c for c in corr.load_lines(ref, root)}
    for box, rec in zip(corrected, sorted(stored.values(),
                                          key=lambda r: (r["y0"], r["x0"])),
                        strict=False):
        box.update({k: rec[k] for k in ("id", "x0", "y0", "x1", "y1", "text")})

    zones = zn.read_zones(ref, root)
    bands = line_gaps(ref, alto_dir, root) if alto.exists() else []
    return {
        "ref": ref, "w": w, "h": h,
        "has_zones": zn.has_zones(ref, root),
        "lines": lines,
        "corr": corrected,
        "zones": [{"label": z["label"], "x0": z["x0"], "y0": z["y0"],
                   "x1": z["x1"], "y1": z["y1"]} for z in zones],
        "bands": bands,
        # Both layers travel to the client: this editor writes only the line
        # layer, but a human ruling a band needs to see that the zoning side has
        # already spoken about that strip of paper.
        "line_exempt": corr.load_ink_exempt(root).get(ref, []),
        "zone_exempt": zn.load_ink_exempt(root).get(ref, []),
    }


def page_row(ref: str, root: Path = Path("."),
             alto_dir: str = DEFAULT_ALTO_DIR) -> dict:
    """One page's state for the list — the slow column measured, the rest read.

    `bands` is the raster read (~0.2 s) and everything else is a file test, which
    is why the list draws the cheap columns immediately and fetches this per row.
    """
    ref = norm_ref(ref)
    alto = alto_for_lines(ref, alto_dir, root)
    bands = line_gaps(ref, alto_dir, root) if alto.exists() else []
    return {"ref": ref, "live": sum(1 for b in bands if not b["exempted"]),
            "ruled": sum(1 for b in bands if b["exempted"]),
            "corrections": len(corr.load_lines(ref, root))}


def _zone_of(box: dict, zones: list[dict]) -> str:
    from .lines import _band_zone
    return _band_zone({"hpos": box["x0"], "vpos": box["y0"],
                       "width": box["x1"] - box["x0"],
                       "height": box["y1"] - box["y0"]}, zones)


def save_payload(payload: dict, root: Path = Path("."),
                 alto_dir: str = DEFAULT_ALTO_DIR) -> dict:
    """Write one page's corrections and its line-level rulings.

    Both stores or neither: they are two halves of one sitting, and a save that
    landed one would leave the page in a state no single view describes.

    **Refuses a box in no zone before writing anything.** The message names the
    zone editor because that is where the fault actually is — a line this editor
    cannot place is ink the *zoning* does not cover, and adopting it here would
    record a line inside no region while leaving the region missing.
    """
    ref = norm_ref(payload.get("ref") or "")
    boxes = payload.get("lines") or []
    if not zn.has_zones(ref, root):
        raise ValueError(
            f"{ref} has no zoning. Line correction comes after it: this editor "
            "finds lines dropped *inside* declared regions, and with no regions "
            f"there is nothing to be inside. Key it in `harness zones edit {ref}`")

    zones = zn.read_zones(ref, root)
    stray = [b for b in boxes if not _zone_of(b, zones)]
    if stray:
        where = ", ".join(f"y={b['y0']}-{b['y1']}" for b in stray[:6])
        raise ValueError(
            f"{ref}: {len(stray)} box(es) lie in no zone ({where}). That is a "
            "defect in the zoning, not a line this editor can adopt — ink no "
            "region covers means the segmentation missed a region, and recording "
            "a line inside no region would leave the region missing. Draw the "
            f"zone in `harness zones edit {ref}` first, or rule the band not type "
            "if it is not printing.")

    res = corr.save_lines(ref, boxes, root)
    corr.set_ink_exempt(ref, payload.get("ink_exempt") or [], root)
    # Re-measured after the write, so the page reports what is *left* rather than
    # what the client believed before it saved — and through the same store the
    # page was opened against, or a `--store gt` session would save and then
    # report a tally measured somewhere else.
    bands = line_gaps(ref, alto_dir, root)
    return {**res,
            "live_bands": [b for b in bands if not b["exempted"]],
            "bands": len(bands)}


# What each bound action is called on the page. Held beside the dispatch rather
# than in the config: the config says which key, this says what to call it, and a
# human rebinding a key should not have to restate its name in English.
ACTION_NAMES = {
    "rule_band": "rule a band not type",
    "withdraw_ruling": "withdraw a ruling",
    "delete": "delete selected",
    "zoom_in": "zoom in",
    "zoom_out": "zoom out",
    "zoom_fit": "fit the page",
    "frame_band": "frame the next band",
    "blot": "blotted view",
    "save": "save",
    "list": "the walk, measured",
    "prev_page": "previous page",
    "next_page": "next page",
    "cancel": "deselect",
}
