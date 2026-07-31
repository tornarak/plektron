"""Assemble the per-page input contract (harness rev 2, 'Input contract').

Everything here is deterministic. The model consumes this; it never re-derives it.
Repo layout assumed:  scans/chukchi-PP-NNN.png   fig/chukchi-PP-NNN.xml
                      ocr/chukchi-PP-NNN.xml     tei/chukchi-PP-NNN.xml
                      data/toc.json              data/readings.md
                      data/lexicon_extra.txt     boundaries.json (optional)

PAGE REFS. A page is identified by its **PP-NNN** ref — part, and scan index
within that part — and by nothing else. NNN is a scan index, *not* a printed
folio: part 1 runs 001-362, part 2 001-268, part 3 001-202, while the printed
folio runs continuously 1-732 across the volume with plates and front matter
unpaginated. Neither is derivable from the other, so nothing here tries. A bare
integer is not a page identifier anywhere in this harness; where a folio is
needed it comes from state.py, which knows it only because a transcribed page
recorded one.
"""
from __future__ import annotations
import re, unicodedata
from pathlib import Path
from lxml import etree

from .detectors import detect_all
from .state import entry_state, foreign_terms_nearby, load_toc, toc_window

REF_RE = re.compile(r"^(?:chukchi-)?(\d+)-(\d+)$")


def parse_ref(ref: str) -> tuple[int, int]:
    """'1-048' | '1-48' | 'chukchi-1-048' -> (1, 48). Anything else is an error.

    Deliberately strict about shape and deliberately lenient about zero-padding:
    the ref is typed by hand at a CLI, but a bare integer must never silently
    become a page.
    """
    m = REF_RE.match(str(ref).strip())
    if not m:
        raise ValueError(
            f"{ref!r} is not a page ref — expected PP-NNN (part, scan index "
            "within that part), e.g. '1-048'. Bare page numbers are not page "
            "identifiers: the printed folio is not derivable from the scan index.")
    return int(m.group(1)), int(m.group(2))


def norm_ref(ref: str) -> str:
    """Canonical ref spelling, matching the filenames: part bare, index to 3."""
    part, idx = parse_ref(ref)
    return f"{part}-{idx:03d}"


def stem_for(ref: str, root: Path = Path(".")) -> str:
    return f"chukchi-{norm_ref(ref)}"


def _refs_under(root: Path, pattern: str) -> list[str]:
    refs = []
    for p in root.glob(pattern):
        try:
            refs.append(norm_ref(p.stem))
        except ValueError:
            continue
    return sorted(set(refs), key=parse_ref)


def all_refs(root: Path = Path(".")) -> list[str]:
    """Every ref with OCR present — i.e. workable now. Sparse by construction."""
    return _refs_under(root, "ocr/chukchi-*.xml")


def all_scans(root: Path = Path(".")) -> list[str]:
    """Every ref that physically exists, in (part, scan index) order.

    This, not `all_refs`, is the sequence folio prediction walks. The OCR set is
    sparse — a pilot selection scattered through the volume — so stepping
    through it would happily predict folio+1 across a four-scan gap. Physical
    adjacency is the only thing that licenses the prediction.
    """
    return _refs_under(root, "scans/chukchi-*.png")


ALTO_STRING = ".//{*}TextLine"


def _lines_from_alto(path: Path) -> list[str]:
    """ALTO -> plaintext lines. Namespace-agnostic (eScriptorium exports ALTO 4)."""
    tree = etree.parse(str(path))
    lines = []
    for tl in tree.iter("{*}TextLine"):
        parts = [s.get("CONTENT", "") for s in tl.iter("{*}String")]
        txt = " ".join(p for p in parts if p)
        if txt.strip():
            lines.append(txt)
    return lines


def _draft_text(lines: list[str]) -> str:
    # Paragraph reconstruction is the model's job (indent/blank-line reading of
    # the image); the draft is line-per-line, NFD like everything else.
    return unicodedata.normalize("NFD", "\n".join(lines))


def _figures_on_page(figs_path: Path, root: Path = Path(".")) -> list[dict]:
    """Figure zones from the figure-track ALTO: id, type, bbox, caption text.

    eScriptorium encodes zone types as OtherTag/@LABEL referenced via TAGREFS.
    Confirmed against real exports; resolve by label, never by tag ID, since the
    IDs are assigned per export.

    `bbox` is geometry already sitting in the file (HPOS/VPOS/WIDTH/HEIGHT),
    included so a page with a figure never needs a second, redundant read of the
    ALTO just to place it.

    `text` comes from **`data/readings.md`**, not from the ALTO. `fig/` carries no
    `TextLine` — the lines were stripped, because the exported line segmentation
    dropped whole printed lines. Reading `String/@CONTENT` here used to be the
    source, and after the strip it returned `""` for every zone on every page:
    the model was handed figures with no captions and nothing said so. A
    GraphicZone has no text by construction; a GraphicZone-FigDesc always should,
    so `text: ""` on one means the reading is missing, which
    `figures.reconcile()` is there to catch.

    Coordinates are parsed as float. eScriptorium writes them as `"365.0"`,
    which is not `str.isdigit()`; testing for that instead handed the model an
    empty bbox for every zone on all 250 pages.
    """
    if not figs_path.exists():
        return []
    from .figures import readings_for
    try:
        by_zone = readings_for(norm_ref(figs_path.stem), root)
    except (ValueError, OSError):
        by_zone = {}
    tree = etree.parse(str(figs_path))
    labels = {t.get("ID"): t.get("LABEL", "") for t in tree.iter("{*}OtherTag")}
    out = []
    for blk in tree.iter():
        tag = etree.QName(blk).localname if isinstance(blk.tag, str) else ""
        if tag not in ("TextBlock", "ComposedBlock", "Illustration", "GraphicalElement"):
            continue
        refs = (blk.get("TAGREFS") or "").split()
        zone_types = [labels.get(r, "") for r in refs]
        if any("Graphic" in z for z in zone_types) or tag == "Illustration":
            bbox = None
            if blk.get("HPOS") is not None:
                bbox = {}
                for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"):
                    raw = blk.get(k)
                    if raw is None:
                        continue
                    try:
                        bbox[k] = round(float(raw))
                    except ValueError:
                        continue
            zid = blk.get("ID") or ""
            reading = by_zone.get(zid[-8:])
            out.append({
                "zone_id": blk.get("ID"),
                "zone_type": next((z for z in zone_types if z), tag),
                "bbox": bbox,
                "text": reading["text"] if reading else "",
            })
    return out


def _ocr_lines(ocr_path: Path) -> list[dict]:
    """OCR lines with their ALTO ids, for optional @facs citation on a Tier-1 span.

    Deliberately not `catmus_draft`: that reader (`_lines_from_alto`) drops
    empty lines and discards `@ID`, so its indices don't join back to a real
    ALTO line. This calls the ID-preserving reader instead, and only the
    fields the model can usefully cite — no geometry; it never sees pixels
    here, only proposes a pointer a human later resolves with `harness zoom`.

    Reads the same `ocr/{stem}.xml` the draft already reads — not a second
    ALTO store — since a facs pointer must resolve in the ALTO the model
    actually saw.
    """
    from .lines import page_lines  # local: lines.py imports context at module
                                    # level, so this avoids a cycle.
    return [{"index": r["index"], "line_id": r["line_id"], "text": r["text"]}
            for r in page_lines(ocr_path)]


def build_context(ref: str, root: Path = Path(".")) -> dict:
    ref = norm_ref(ref)
    stem = stem_for(ref, root)
    ocr = root / "ocr" / f"{stem}.xml"
    if not ocr.exists():
        raise FileNotFoundError(f"no {ocr} — {ref} has no OCR yet")

    state = entry_state(ref, root)
    lines = _lines_from_alto(ocr)
    draft = _draft_text(lines)
    detected = detect_all(draft.split("\n"), root)

    return {
        "page_ref": ref,
        "stem": stem,
        # For the validator's benefit: it re-reads the full ToC id set from
        # here rather than the context carrying 300-odd ids the model never
        # reads. Not part of the model's input contract.
        "root": str(root),
        "page_image": str(root / "scans" / f"{stem}.png"),
        "catmus_draft": draft,
        # Folio is a prediction from the preceding transcribed page, or null.
        # Null is not a defect: it means read it off the image and don't guess.
        "expected_folio": state["expected_folio"],
        "folio_basis": {"prior_ref": state["prior_ref"],
                        "basis_ref": state["basis_ref"],
                        "basis_folio": state["basis_folio"]},
        # A neighbourhood with marks, not a resolution. `open` is what the
        # milestone fold believes; it informs, it does not decide.
        "toc_window": toc_window(load_toc(root), state["expected_folio"],
                                 state["believed_open"]),
        "boundary_in": state["boundary_in"],
        "figures_on_page": _figures_on_page(root / "fig" / f"{stem}.xml", root),
        "ocr_lines": _ocr_lines(ocr),
        # Foreign spans already committed on the physically neighbouring pages,
        # recomputed from the TEI each call. For cross-checking a term keyed two
        # ways — never a source to copy from; this page's draft is the only
        # source for this page's Tier-1 content.
        "foreign_terms_nearby": foreign_terms_nearby(ref, root),
        # Two tables, not one: token-level hits and paragraph-level balance
        # complaints are different record shapes and are kept apart so each
        # stays uniform.
        "detector_flags": detected["tokens"],
        "balance_flags": detected["balance"],
        "output_path": str(root / "tei" / f"{stem}.xml"),
    }
