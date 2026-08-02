"""Assemble the per-page input contract for the collation pass.

Everything here is deterministic. The model consumes this; it never re-derives it.
Repo layout assumed:  scans/chukchi-PP-NNN.png   gt/fig/chukchi-PP-NNN.xml
                      ocr/chukchi-PP-NNN.xml     tei/chukchi-PP-NNN.xml
                      data/toc.json              data/readings.md
                      data/lexicon_extra.txt

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
    """ALTO -> plaintext lines, in **reading order**, empties dropped.

    Order comes from `lines.page_lines` rather than a second walk of the tree.
    This reader produces `catmus_draft`, and `_ocr_lines` beside it in the same
    page context is built from `page_lines` directly: if one were in segmenter
    order and the other in reading order, the two halves of a single contract
    would disagree silently, which is worse than either order alone. Deriving
    both from one banded source makes that impossible by construction instead of
    by two implementations agreeing.

    `lines.py`'s module docstring used to say this reader was "deliberately left
    alone: changing it would move `catmus_draft`, and with it the firewall's
    substring test and every detector line number." Half of that is spent -- the
    verbatim-substring test is gone (see the comment at its old site in
    `validate.validate`). The live half stands: `catmus_draft` and
    `detector_flags`' line numbers must agree *with each other*, and they still
    do, because `build_context` derives both from this one call.

    Empty lines are still dropped, so index *i* here is **not** the *i*-th
    `TextLine` -- unchanged, and still the reason nothing may join a detector
    flag to a crop except through `page_lines`.

    Imported locally: `lines` imports `norm_ref` from this module, so a
    module-level import here would be circular.
    """
    from .lines import page_lines
    return [rec["text"] for rec in page_lines(path) if rec["text"].strip()]


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

    `text` comes from **`data/readings.md`**, not from the ALTO. `gt/fig/` carries no
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
    ref = norm_ref(figs_path.stem)
    from .figures import readings_for, zones
    try:
        by_zone = readings_for(ref, root)
    except (ValueError, OSError):
        by_zone = {}
    out = []
    for z in zones(ref, root):
        # Only figure zones. The store also holds an eScriptorium `dummyblock` with
        # no geometry (`1-037`) and one degenerate 1x1 unlabelled box (`2-094`,
        # residue from deleting the phantom captions CLAUDE.md's figure-track note
        # describes); neither is a figure and neither may reach the model.
        if "Graphic" not in z["label"]:
            continue
        zid = z["id"] or ""
        reading = by_zone.get(zid[-8:])
        out.append({
            "zone_id": z["id"],
            "zone_type": z["label"],
            "bbox": {"HPOS": z["hpos"], "VPOS": z["vpos"],
                     "WIDTH": z["width"], "HEIGHT": z["height"]},
            "text": reading["text"] if reading else "",
        })
    return out


def _figure_line_warnings(recs: list[dict], figures: list[dict]) -> list[dict]:
    """Lines the segmenter ran across a figure boundary, and lines inside artwork.

    Two segmenter failures the collation pass has to be told about rather than
    left to infer:

      * `straddles_caption` — one `TextLine` spanning the end of a wrapped caption
        and the start of body text. The caption's own reading is attached, so the
        model can see which half is already accounted for.
      * `inside_graphic` — a line wholly inside a plain `GraphicZone`. Usually the
        zone is simply drawn too large: `3-006`'s `CONSANGUINITY.` is a real
        section heading sitting inside caption-less artwork. Reported, never
        suppressed — the alternative deletes headings.

    **The split is geometric, and only geometric.** A page's ALTO carries one
    `String` per `TextLine` with no word- or glyph-level boxes (and `restore`
    requires exactly one), so the pixel boundary between caption and body cannot be
    mapped to a character offset in the line's text. `caption_side` and `body_side`
    are therefore the two *boxes*; the text is handed over whole and the division
    is left to the reader, who can see the page. Splitting the string at a
    proportional index would be a fabricated position — the shape of guess this
    project exists to refuse.

    Empty on all 20 restored pages: no real straddle occurs in the pilot set, so
    this ships exercised only by fixture. Threshold and shape want revisiting the
    first time a genuine one turns up.
    """
    by_zone = {f["zone_id"]: f for f in figures}
    out = []
    for r in recs:
        zid = r.get("figdesc_straddle")
        if zid:
            z = by_zone.get(zid, {})
            bb = z.get("bbox") or {}
            cut = bb.get("VPOS")
            out.append({
                "kind": "straddles_caption", "index": r["index"],
                "line_id": r["line_id"], "zone_id": zid,
                "caption_side": f"{r['hpos']},{r['vpos']},{r['width']},"
                                f"{max(0, (cut or r['vpos']) - r['vpos'])}",
                "body_side": f"{r['hpos']},{cut},{r['width']},"
                             f"{max(0, r['vpos'] + r['height'] - (cut or r['vpos']))}",
                "caption": (z.get("text") or "")[:200],
            })
        elif r.get("in_graphic"):
            out.append({
                "kind": "inside_graphic", "index": r["index"],
                "line_id": r["line_id"], "zone_id": r["in_graphic"],
                "caption_side": "", "body_side": "", "caption": "",
            })
    return out


def _ocr_lines(ocr_path: Path) -> list[dict]:
    """OCR lines with their ALTO ids, for optional @facs citation on a Tier-1 span.

    Deliberately not `catmus_draft`: that reader (`_lines_from_alto`) drops
    empty lines and discards `@ID`, so its indices don't join back to a real
    ALTO line. This calls the ID-preserving reader instead, and only the
    fields the model can usefully cite — no geometry; it never sees pixels
    here, only proposes a pointer a human later resolves with `harness ocr zoom`.

    Reads the same `ocr/{stem}.xml` the draft already reads — not a second
    ALTO store — since a facs pointer must resolve in the ALTO the model
    actually saw.
    """
    from .lines import page_lines  # local: lines.py imports context at module
                                    # level, so this avoids a cycle.
    return [{"index": r["index"], "line_id": r["line_id"], "text": r["text"]}
            for r in page_lines(ocr_path)]


def build_context(ref: str, root: Path = Path(".")) -> dict:
    """The whole per-page input contract for the collation pass, as one dict.

    Everything a model needs to produce this page's TEI and nothing it would have
    to re-derive: the ref and stem, the seam state folded forward from committed
    TEI, a ToC neighbourhood, the figure zones with their captions, the OCR line
    ids a Tier-1 span may cite in `@facs`, and the detector flags. Deterministic
    and precomputed by design — a pass that re-derived any of this could disagree
    with the validator that checks it.

    Imported locally, not at module scope: `figures` imports `norm_ref` from here,
    so a top-level import would close a cycle. Three other call sites in this
    package do the same for the same reason.
    """
    from .figures import FIGDIR
    from .seam import tail as seam_tail
    ref = norm_ref(ref)
    stem = stem_for(ref, root)
    ocr = root / "ocr" / f"{stem}.xml"
    if not ocr.exists():
        raise FileNotFoundError(f"no {ocr} — {ref} has no OCR yet")

    state = entry_state(ref, root)
    # The draft is assembled here, not inside `_lines_from_alto`, because that
    # reader is shared with `detectors.suggest_lexicon` and the corpus frequency
    # tables. Excluding caption lines there would silently move published numbers:
    # `2-030`'s caption alone carries 10 of the corpus's 109 U+0323 marks — 9.2% of
    # them, from 2.0% of its characters — and keying_spec section 5.1 cites those
    # tables for the "~90% of g's carry the dot" prior. Same reader, two consumers,
    # and only one of them wants the exclusion.
    from .lines import page_lines
    recs = page_lines(ocr, root)
    # A caption is text the project already has a *human* reading of
    # (`data/readings.md`, all 395), and it reaches the model below as
    # `figures_on_page[].text`. Leaving the line segment in the draft too would
    # hand the model the same caption twice, from two witnesses of different rank,
    # and invite it to reconcile them. Marked lines are excluded from the draft
    # only — they stay in `gt/ocr/`, in the review queue, and in `ocr_lines`, the
    # last because that is what a `@facs` pointer resolves against.
    lines = [r["text"] for r in recs if r["text"].strip() and not r["in_figdesc"]]
    draft = _draft_text(lines)
    detected = detect_all(draft.split("\n"), root)
    figures = _figures_on_page(root / FIGDIR / f"{stem}.xml", root)

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
        # The end of the previous page's committed TEI, so the pass can see
        # whether this page opens mid-element instead of inferring it. Null when
        # the predecessor is not collated — then the seam is genuinely unknown and
        # `harness tei seam` will refuse it too. About 70% of text pages open
        # mid-paragraph (measured over the keyed zone corpus), so this is the
        # common case, not an edge one.
        "prev_tail": seam_tail(ref, root),
        "figures_on_page": figures,
        # Segmenter faults where a line meets a figure: a line running from a
        # wrapped caption into body text, or a line sitting inside artwork. Both
        # are reported rather than acted on — see `_figure_line_warnings`.
        "figure_line_warnings": _figure_line_warnings(recs, figures),
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
