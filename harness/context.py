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

# **Where a folio may be printed, in the order it is looked for.** Three places,
# because the book puts the number in three, and the order is the order of
# confidence rather than of frequency:
#
#   RunningTitleZone  the ordinary page. Head line, folio bare beside the head.
#   QuireMarksZone    a chapter opening. No running title at all, the number set
#                     at the **foot** of the page and **in brackets** — `1-151`
#                     reads `[115]` at vpos 3231 of a 3897 px page, and its
#                     collated TEI gives `<pb n="115"/>`.
#   NumberingZone     the old full-SegmOnto vocabulary `gt/ocr/` descends from,
#                     which split the folio out of the head as its own zone. The
#                     current scheme cannot express that split — a fixed-width
#                     vertical partition has nowhere to put it, and the two are on
#                     one printed line (`data/zones_config.json`). Last because it
#                     is the store-specific spelling, not a place on the page: it
#                     appears at the head on `1-048` and at the foot on `1-151`.
#
# Reading all three matters because the two stores speak different vocabularies for
# the same ink, and `gt/ocr/` — which speaks the old one — is where the collation
# frontier is.
FOLIO_ZONES = ("RunningTitleZone", "QuireMarksZone", "NumberingZone")

# Zones whose text the printer set rather than the author: the head line, the
# signature line at the foot of a gathering, and the folio in whichever of them it
# lands. `build_context` keeps them out of the collation draft; see the comment at
# the exclusion for why there and not at the point the page is recognized.
APPARATUS_ZONES = frozenset(FOLIO_ZONES)


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


# A folio is a number standing **alone** on its line, optionally in brackets.
# Arabic for the body, roman for the front matter (part 1's is printed xii-xvii).
#
# **Deliberately strict about everything else**: no other punctuation, no digits
# embedded in words, nothing repaired. A recognizer's `2S` for `28` must fail this
# and fall through, leaving the line for a human to read — the alternative is a
# plausible page number with no error signal, which is the failure this project is
# organised against.
#
# The brackets are captured rather than tolerated. `1-151` prints `[115]` at the
# foot of a chapter opening and its collated TEI reads `<pb n="115"/>`, so the
# editor read through them — but whether a bracketed folio is the printer's or
# supplied is a judgement about the book, and `bracketed` carries it forward
# instead of discarding it at the point the number is parsed.
_FOLIO_RE = re.compile(r"^(\[)?(\d{1,4}|[ivxlcdm]{1,7}|[IVXLCDM]{1,7})(?(1)\])$")


def _folio_in(lines: list[dict]) -> tuple[str, bool] | None:
    """First line that is nothing but a page number. `(folio, bracketed)`."""
    for r in lines:
        m = _FOLIO_RE.match((r["text"] or "").strip())
        if m:
            return m.group(2), bool(m.group(1))
    return None


def _running_title(recs: list[dict], ref: str, root: Path) -> dict | None:
    """The page's own statement of what page it is.

    `{text, folio, folio_from, bracketed, lines}`, or null where the page carries
    none of the three zones a folio can print in — a plate, a blank, a page nobody
    has segmented.

    **The folio is looked for in `FOLIO_ZONES` order, and `folio_from` says which
    one answered.** That order is confidence, not frequency: the head line of an
    ordinary page first; then the bracketed number at the foot of a chapter
    opening; then the old vocabulary's dedicated zone, last because it names a
    store's spelling rather than a place on the page.

    **`text` is the running title and only ever that** — the head line with any
    folio token taken out of it. It is `""` on a page that has no running title,
    which a chapter opening does not: `1-151` has no head at all and still yields a
    folio, from the quire marks. So `text` and `folio` are independent, and neither
    being empty says anything about the other.

    Where nothing parses, `folio` is null and the lines are still in `text` — the
    caller has what the page holds and reads the number itself, the same "null
    means go and look" contract `expected_folio` keeps.

    This is also where the running title *goes*. `build_context` drops all three
    zones from `catmus_draft` as the printer's text; promoting them here means the
    information is restructured rather than discarded, and the folio in particular
    is the part the project needs — `<pb n>` is where page numbering enters the
    corpus.

    Two lines in the head is the ordinary case, not one: the title and the number
    sit on one printed line with a wide gap and the segmenter splits them.
    """
    by_zone = {z: [r for r in recs if r.get("zone") == z] for z in FOLIO_ZONES}
    if not any(by_zone.values()):
        # A store whose blocks carry no label at all: fall back to the zone store's
        # bands and take the lines inside them geometrically.
        for z in FOLIO_ZONES:
            by_zone[z] = _lines_in_zone(recs, ref, root, z)
    if not any(by_zone.values()):
        return None

    folio = bracketed = None
    source = ""
    for z in FOLIO_ZONES:
        hit = _folio_in(by_zone[z])
        if hit:
            folio, bracketed = hit
            source = z
            break

    head = sorted(by_zone["RunningTitleZone"], key=lambda r: r.get("hpos") or 0)
    text = " ".join(t for t in ((r["text"] or "").strip() for r in head)
                    if t and not _FOLIO_RE.match(t))
    return {"text": text, "folio": folio, "folio_from": source or None,
            "bracketed": bracketed, "lines": sum(len(v) for v in by_zone.values())}


def _lines_in_zone(recs: list[dict], ref: str, root: Path,
                   label: str) -> list[dict]:
    """Lines whose vertical midpoint falls in a zone of this label.

    Geometry rather than a label on the block, for the store whose blocks carry
    none. Reads `zones/` — the view, so a human-keyed page answers from
    `gt/zones/` and a machine-keyed one from `mz/zones/`, which is what the view
    is for. Silent `[]` when the page has no zones: absence of a segmentation is
    not an error here, it is the ordinary state of a page nobody has reached.
    """
    try:
        from .zones import VIEWDIR, read_zones
        bands = [(z["y0"], z["y1"]) for z in read_zones(ref, root, store=VIEWDIR)
                 if z["label"] == label]
    except Exception:
        return []
    if not bands:
        return []
    out = []
    for r in recs:
        v, h = r.get("vpos"), r.get("height")
        if v is None or h is None:
            continue
        mid = v + h / 2
        if any(y0 <= mid <= y1 for y0, y1 in bands):
            out.append(r)
    return out


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

    **`APPARATUS_ZONES` are omitted here as well as from the draft**, and for a
    sharper reason than there. The draft excludes them because they are the
    printer's text; this list excludes them because **nothing in the TEI can ever
    point at one**. `@facs` cites the line a Tier-1 span was read from, and a
    running head, a folio and a signature line are not in the body at all — so
    every one of them in this list is a pointer target that would be a mistake to
    use, offered to a pass that is choosing among them.

    A caption line stays, and the difference is worth keeping straight: a caption
    is excluded from the *draft* only, because the project already has a human
    reading of it in `data/readings.md` and showing the model two witnesses of
    different rank invites it to reconcile them. It remains citable, so it remains
    here.

    Omitting records cannot disturb the rest: `index` is an identity assigned by
    ALTO document order, never a position in this list.
    """
    from .lines import page_lines  # local: lines.py imports context at module
                                    # level, so this avoids a cycle.
    return [{"index": r["index"], "line_id": r["line_id"], "text": r["text"]}
            for r in page_lines(ocr_path)
            if r["zone"] not in APPARATUS_ZONES]


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
    # The running head with its folio, and the printer's signature line at the foot
    # of a gathering: the printer's text, not the author's, and now identifiable
    # because `ocr predict` writes the zones in as the ALTO's regions. Excluded on
    # the same terms as a caption — from the draft only. They stay in the store, in
    # `ocr_lines`, and one field away in `harness ocr lines PP-NNN`.
    #
    # **Excluded here and not in `ocr predict`**, because the running head shares
    # its zone with the printed folio, and the folio is where page numbering enters
    # the project (`<pb n>`). Dropping it at write time would take the OCR's only
    # record of it and cost a re-run of the page to get back.
    #
    # An unlabelled block is *kept*: `gt/ocr/` and `gt/seg/` label none, so treating
    # blank as apparatus would empty the draft for every ground-truth page.
    lines = [r["text"] for r in recs
             if r["text"].strip() and not r["in_figdesc"]
             and r["zone"] not in APPARATUS_ZONES]
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
        # What the page itself says it is, off its running title — the second
        # witness to `expected_folio` above, which is a prediction from the
        # preceding page and knows nothing about this one. Cheap, independent, and
        # the two disagreeing is the signal.
        "running_title": _running_title(recs, ref, root),
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
