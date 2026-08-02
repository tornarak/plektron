"""`harness ocr` — the ALTO stores, the line instruments, and the correction loop.

Reads resolve through `ocr/`, the read view over every OCR store and this
group's default `--from`. Writes name `gt/ocr/` explicitly and there are exactly
two of them: `restore`, which fills text into lines that already exist, and
`adopt-gap`, which creates an empty line so a dropped one can be keyed. Both
require `--commit`.

The old `lines` verb carried six modes on one parser — a table, a gap detector,
a geometry writer, and three image writers — selected by if-chain precedence, so
`--gaps` silently voided `--crops` and `--margins` did nothing under either.
They are six actions now, and a flag that does not apply is a parse error rather
than a no-op.
"""
from __future__ import annotations
from pathlib import Path
import sys

from ._common import out
from ..context import norm_ref
from ..emit import emit
from ..lines import (DEFAULT_ALTO_DIR, LINE_SHEET_H, ZOOM, ZOOM_CLIENT_W,
                     ZOOM_OVERLAP, ZOOM_SHEET_H, alto_for_lines, adopt_gaps,
                     line_gaps, page_lines, parse_selection, write_blot,
                     write_line_crops, write_line_sheets, write_line_zoom)
from ..context import all_refs
from ..paths import (clean, crops_dir, ensure_page_link, html_path, sheets_dir,
                     zoom_dir)
from ..recognize import DEFAULT_REC_MODEL, DEFAULT_SEG_MODEL
from ..review import (group_spans, page_spans, render_queue_html, restore, serve,
                      summary)

REF_HELP = "page ref: part and scan index, e.g. 1-048"
FROM_HELP = (f"ALTO directory to read (default {DEFAULT_ALTO_DIR}, the read view "
             "over every OCR store)")
MARGINS_HELP = ("widen to the PrintSpace margins — a line polygon can exclude "
                "printed text that belongs to the line, and what it excludes "
                "sits in the margin (list numbers, the folio)")
OUT_HELP = ("write the images somewhere other than the page's own review/PP-NNN/ "
            "subdirectory — for a one-off comparison, not for the pass, whose "
            "files the other actions expect to find in the default place")


def _ref(p):
    p.add_argument("ref", metavar="PP-NNN", help=REF_HELP)
    return p


def _from(p):
    p.add_argument("--from", dest="alto_dir", default=DEFAULT_ALTO_DIR,
                   help=FROM_HELP)
    return p


def register(sub, common):
    g = sub.add_parser("ocr", help="the ALTO stores and the correction loop — "
                       "line records, the dropped-line detector, crops and "
                       "contact sheets, the browser review, and the write back "
                       "into gt/ocr/")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    p = add("pages", help="every ref with OCR present, i.e. workable now. Sparse "
            "by construction — a pilot selection scattered through the volume, "
            "not a prefix of it")
    p.set_defaults(func=run_pages)

    p = _from(_ref(add("lines", help="per-line records for one page — line id, "
              "geometry and text, in reading order with empties kept, which is "
              "the join detector_flags' line numbers cannot supply. `index` is "
              "an identity, not a position: it stays what ALTO document order "
              "assigned, so labels are not consecutive in a banded listing")))
    p.add_argument("--full", action="store_true",
                   help="include baseline and polygon points, which are long "
                        "enough to make the table unreadable by default")
    p.set_defaults(func=run_lines)

    p = _from(_ref(add("gaps", help="bands of ink on the raster that no TextLine "
              "covers — the dropped-line detector. The segmentation this corpus "
              "was built from drops whole printed lines and nothing else "
              "notices, because the text that IS there is correct. Measured off "
              "the page, so the geometry a repair needs comes with the report. "
              "Expect running heads and folios among the hits: a band is a place "
              "to look, not a verdict")))
    p.set_defaults(func=run_gaps)

    p = _from(_ref(add("adopt-gap", help="materialize measured `gaps` bands as "
              "empty TextLines in gt/ocr/, so a dropped line can be keyed. "
              "Geometry only, never CONTENT: text still arrives via "
              "decision.json -> restore. Each VPOS must match a measured band; "
              "naming which bands are real lines is the human call")))
    p.add_argument("vpos", metavar="VPOS[,VPOS...]",
                   help="the band(s) to adopt, by the vpos `ocr gaps` reported")
    p.add_argument("--commit", action="store_true",
                   help="actually write gt/ocr/ — bare form reports the lines it "
                        "would create and writes nothing. This is a writer into "
                        "the ground-truth store and gates like `restore` does")
    p.set_defaults(func=run_adopt_gap)

    p = _from(_ref(add("crops", help="one PNG per line, into review/PP-NNN/crops/")))
    p.add_argument("--margins", action="store_true", help=MARGINS_HELP)
    p.add_argument("--out", type=Path, default=None, help=OUT_HELP)
    p.set_defaults(func=run_crops)

    p = _from(_ref(add("sheets", help="compose the line crops into labelled "
              "contact sheets in review/PP-NNN/sheets/, index drawn in the "
              "margin, nothing downscaled — the reading pass's instrument; emits "
              "the sheet/lines map instead of the line table")))
    p.add_argument("--per-sheet", type=int, default=40,
                   help="lines per contact sheet, upper bound only — --height "
                        "packs by height first (default 40)")
    p.add_argument("--height", dest="sheet_h", type=int, default=LINE_SHEET_H,
                   help=f"max contact-sheet height in px (default {LINE_SHEET_H}); "
                        "fewer, fuller sheets for the same lines")
    p.add_argument("--margins", action="store_true", help=MARGINS_HELP)
    p.add_argument("--out", type=Path, default=None, help=OUT_HELP)
    p.set_defaults(func=run_sheets)

    p = _from(_ref(add("zoom", help="magnify selected lines — overlapping strips "
              "at an integer scale, packed into as few sheets as the height "
              "budget allows, for the second look a contact sheet leaves open")))
    p.add_argument("--only", default=None, metavar="SPEC",
                   help="line indices to magnify, e.g. 7,20,22-26 (default every "
                        "line on the page)")
    p.add_argument("--zoom", type=int, default=ZOOM,
                   help=f"display px per source px, as delivered (default {ZOOM}). "
                        "Higher wraps each line into more strips, and a form seen "
                        "only in halves is the risk being traded against — "
                        "escalate for one question, not by default. --zoom 1 "
                        "wraps least")
    p.add_argument("--window", type=int, default=None,
                   help="source px per strip; derived from --zoom so that the "
                        "delivered scale really is --zoom. Overriding it upward "
                        "makes the sheet exceed the client width, and the scale "
                        "is then whatever the client's fitting leaves")
    p.add_argument("--client-w", type=int, default=ZOOM_CLIENT_W,
                   help=f"px the reading client shows per image (default "
                        f"{ZOOM_CLIENT_W}); every sheet is padded to exactly "
                        "this, so the scale does not vary with how long the "
                        "lines are")
    p.add_argument("--overlap", type=int, default=ZOOM_OVERLAP,
                   help=f"px shared by consecutive strips (default "
                        f"{ZOOM_OVERLAP}), so no glyph is only ever seen cut")
    p.add_argument("--height", dest="sheet_h", type=int, default=ZOOM_SHEET_H,
                   help=f"max sheet height in px (default {ZOOM_SHEET_H}) — a "
                        "taller sheet gets fitted to the display, undoing the zoom")
    p.add_argument("--margins", action="store_true", help=MARGINS_HELP)
    p.add_argument("--smooth", action="store_true",
                   help="Lanczos instead of nearest-neighbour: better for "
                        "comparing letterforms, worse for deciding whether a "
                        "faint mark is present, since it invents greys")
    p.add_argument("--out", type=Path, default=None,
                   help="output directory (default review/PP-NNN/zoom)")
    p.set_defaults(func=run_zoom)

    p = _from(_ref(add("blot", help="write the page to scans-blotted/ with every "
              "line box and figure zone painted out, so whatever remains is "
              "uncovered by construction. The visual counterpart to `gaps`, and "
              "a check on it: nothing is thresholded here, only covered. Not to "
              "be confused with `zones blot`, which paints figures white for the "
              "segmenter to train on")))
    p.add_argument("--out", type=Path, default=None,
                   help="output directory (default scans-blotted/ at the root — "
                        "a corpus-level destination, unlike the other image "
                        "actions, because the blotted page is not review material)")
    p.set_defaults(func=run_blot)

    p = _from(_ref(add("review", help="adjudicate a reading proposal in the "
              "browser (--serve); bare, a span-level diff of the proposal "
              "against a second witness, grouped by substitution class")))
    mx = p.add_mutually_exclusive_group()
    mx.add_argument("--serve", action="store_true",
                    help="serve the review page on 127.0.0.1 and accept saves "
                         "into review/PP-NNN/decision.json")
    mx.add_argument("--html", action="store_true",
                    help="write the browser review page to "
                         "review/PP-NNN/review.html instead of emitting a table. "
                         "No destination knob: the page embeds its crops as data "
                         "URIs, so where it sits is nobody's business but the "
                         "pass's, and --serve is the usual route")
    mx.add_argument("--spans", action="store_true",
                    help="with the bare span diff: every span individually, not "
                         "grouped by class")
    p.add_argument("--port", type=int, default=8731, help="port for --serve")
    p.set_defaults(func=run_review)

    p = _from(_ref(add("restore", help="preview (default) or write adjudicated "
              "review decisions into gt/ocr/ as ground truth, keeping the source "
              "geometry — --commit required to write. Reports mode=restoration "
              "(filled from another store) or mode=revision (the finished page "
              "re-edited in place)")))
    p.add_argument("--force", action="store_true",
                   help="overwrite a target that already holds text. Every page "
                        "in gt/ocr/ does now that the rebuild is complete, so "
                        "this is how a revision says it meant it — required for one")
    p.add_argument("--commit", action="store_true",
                   help="actually write gt/ocr/ — bare form only previews the "
                        "report (edits, geometry_drift, text_mismatch)")
    p.set_defaults(func=run_restore)

    p = _ref(add("clean", help="remove a page's derived working files (crops, "
             "sheets, zoom, review.html) — leaving proposal.json and "
             "decision.json in place; run once a page is restored"))
    p.set_defaults(func=run_clean)

    p = add("predict", help="zones to text in one pass — baseline segmentation "
            "and recognition over scans/, structured by the zones/ view, written "
            "to mz/ocr/ and linked into ocr/. Never gt/ocr/. Bare, it sweeps "
            "every page with zones and resumes where it stopped")
    p.add_argument("ref", metavar="PP-NNN", nargs="?", help=REF_HELP)
    p.add_argument("--force", action="store_true",
                   help="re-run over pages already in mz/ocr/ — the file records "
                        "both models' sha256, which is the store's only witness "
                        "to what produced it, so a rerun replaces that record")
    p.add_argument("--itinerary", metavar="LST",
                   help="recognize over a work-list rather than the whole store")
    p.add_argument("--seg-model", default=DEFAULT_SEG_MODEL,
                   help=f"the baseline segmentation model [{DEFAULT_SEG_MODEL}]")
    p.add_argument("--rec-model", default=DEFAULT_REC_MODEL,
                   help=f"the recognition model [{DEFAULT_REC_MODEL}]. Stock "
                        "CATMuS reads ~91%% of the ASCII and 0%% of the "
                        "transcription inventory — a witness to geometry and to "
                        "English, and to nothing else")
    p.add_argument("--device", default="auto", help="torch device [auto]")
    p.set_defaults(func=run_predict)

    p = add("link", help="rebuild ocr/, the read view over gt/ocr/ and mz/ocr/, "
            "the human file winning wherever it exists. Derived: the links are "
            "relative and a stale one is removed rather than left to dangle")
    p.set_defaults(func=run_link)


def run_pages(a) -> int:
    out(a, all_refs(a.root))
    return 0


def run_lines(a) -> int:
    recs = page_lines(alto_for_lines(a.ref, a.alto_dir, a.root))
    if not a.full:
        # Drop the two long geometry strings. Dropped from every record, never
        # some — a ragged key set collapses the table to the verbose nested
        # form (see emit.py).
        drop = ("baseline", "points")
        recs = [{k: v for k, v in r.items() if k not in drop} for r in recs]
    out(a, recs)
    return 0


def run_gaps(a) -> int:
    out(a, line_gaps(a.ref, a.alto_dir, a.root))
    return 0


def run_adopt_gap(a) -> int:
    out(a, adopt_gaps(a.ref, [int(v) for v in a.vpos.split(",")],
                      a.alto_dir, a.root, commit=a.commit))
    return 0


def _page_link(a) -> None:
    """The page's own raster, linked into its working directory the first time an
    action materializes that directory. Convenience only — `ocr clean` leaves it,
    and it is keyed to the ref rather than to `--out`, which exists precisely to
    write somewhere that is not the page's directory."""
    if not getattr(a, "out", None):
        ensure_page_link(a.ref, a.root)


def run_crops(a) -> int:
    _page_link(a)
    out(a, write_line_crops(a.ref, a.out or crops_dir(a.ref, a.root),
                            a.alto_dir, a.root, margins=a.margins))
    return 0


def run_sheets(a) -> int:
    _page_link(a)
    out(a, write_line_sheets(a.ref, a.out or sheets_dir(a.ref, a.root),
                             a.alto_dir, a.root, per_sheet=a.per_sheet,
                             margins=a.margins, sheet_h=a.sheet_h))
    return 0


def run_zoom(a) -> int:
    _page_link(a)
    out(a, write_line_zoom(
        a.ref, a.out or zoom_dir(a.ref, a.root),
        only=parse_selection(a.only) if a.only else None,
        zoom=a.zoom, window=a.window, overlap=a.overlap,
        sheet_h=a.sheet_h, client_w=a.client_w,
        alto_dir=a.alto_dir, root=a.root,
        margins=a.margins, smooth=a.smooth))
    return 0


def run_blot(a) -> int:
    out(a, write_blot(a.ref, a.out or (a.root / "scans-blotted"),
                      a.alto_dir, a.root))
    return 0


def run_review(a) -> int:
    if a.serve:
        _page_link(a)
        serve(a.ref, a.alto_dir, a.root, a.port)
        return 0
    if a.html:
        _page_link(a)
        dest = html_path(a.ref, a.root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_queue_html(a.ref, a.alto_dir, a.root),
                        encoding="utf-8")
        print(f"{dest}: review page for {a.ref}")
        return 0
    # The bare span diff measures a proposal against a *second witness*. If the
    # store it is pointed at resolves to the ground truth the proposal itself
    # produced, the diff compares a file with its own source and reports a clean
    # 40/40 — the shape of verification without the substance, which is exactly
    # the fault that killed the old verbatim firewall (CLAUDE.md, "What the
    # firewall is not"). So refuse rather than print a reassuring table.
    src = alto_for_lines(a.ref, a.alto_dir, a.root)
    gt = a.root / "gt" / "ocr" / f"chukchi-{norm_ref(a.ref)}.xml"
    if src.exists() and gt.exists() and src.resolve() == gt.resolve():
        print(f"ERROR: {src} resolves to the ground truth for {a.ref} ({gt}), so "
              "a proposal diff against it would compare that reading with itself "
              "and report no differences. The span diff needs an independent "
              f"witness — name one with --from, or use `harness ocr review "
              f"{a.ref} --serve` to adjudicate.", file=sys.stderr)
        return 1
    spans = page_spans(a.ref, a.alto_dir, a.root)
    n = len(page_lines(src))
    # Two calls, two tables. Summary and queue have different key sets, so
    # emitting them as one list would collapse the whole thing to the verbose
    # nested form (see emit.py).
    print(emit(summary(spans, n), getattr(a, "json", False)))
    out(a, spans if a.spans else group_spans(spans))
    return 0


def run_restore(a) -> int:
    out(a, restore(a.ref, a.alto_dir, a.root, a.force, a.commit))
    return 0


def run_clean(a) -> int:
    out(a, clean(a.ref, a.root))
    return 0


def run_predict(a) -> int:
    """One page, or a resumable sweep. Imported here because both models pull in
    torch, and paying that on `harness ocr pages` would be the whole group slow
    for one action's sake."""
    from ..recognize import predict, predict_all, predict_skip
    from ..zones import load_itinerary

    if a.ref:
        # A named ref is `single`: it overrides the exempt skip, because naming
        # the page is the request. It does not override an existing file — that
        # is what `--force` is for, and the two excuse different things.
        why = predict_skip(a.ref, a.root, a.force, single=True)
        if why:
            print(f"{norm_ref(a.ref)}: {why}", file=sys.stderr)
            return 0
        out(a, predict(a.ref, a.root, seg_model=a.seg_model,
                       rec_model=a.rec_model, device=a.device))
        return 0

    refs = load_itinerary(a.itinerary, a.root) if a.itinerary else None
    rep = predict_all(a.root, refs, a.seg_model, a.rec_model, a.device, a.force)
    pages, skips = rep.pop("pages"), rep.pop("skips")
    print(emit(rep, getattr(a, "json", False)))
    # Three tables, three key sets. Emitting them as one list would collapse the
    # whole thing to the verbose nested form (see emit.py).
    if pages:
        print(emit(pages, getattr(a, "json", False)))
    if skips:
        print(emit(skips, getattr(a, "json", False)))
    return 0


def run_link(a) -> int:
    from ..recognize import link_view
    out(a, link_view(a.root))
    return 0
