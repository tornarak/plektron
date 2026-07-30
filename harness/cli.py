"""CLI entry: the verbs the model calls from Claude Code.

Pages are addressed by **PP-NNN** ref — part, and scan index within that part —
never by a bare page number. The printed folio is not derivable from the scan
index (see context.py), so a bare integer would silently name the wrong page.

  uv run harness context 1-048    -> the input contract
  uv run harness validate 1-048   -> gate report; exit 1 on FAIL
  uv run harness pages            -> refs with OCR present
  uv run harness state 1-048      -> one page's seam record
  uv run harness ledger           -> the whole seam table
  uv run harness toc-search TEXT  -> ToC entries matching a heading
  uv run harness toc-near FOLIO   -> ToC entries around a known folio
  uv run harness lexicon          -> frequent lexicon misses, to whitelist
  uv run harness normalize --check -> NFD + lookalike gate; exit 1 on drift

Output is TOON (see emit.py). `--json` on any verb restores indented JSON for
anything that needs to parse it as a contract.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from .context import build_context, all_refs
from .detectors import suggest_lexicon
from .emit import emit, emit_lines
from .lines import (ZOOM, ZOOM_CLIENT_W, ZOOM_OVERLAP, ZOOM_SHEET_H, alto_for_lines,
                    page_lines, parse_selection, write_line_crops,
                    write_line_sheets, write_line_zoom)
from .normalize import scan, convert
from .review import (group_spans, page_spans, render_queue_html, restore, serve,
                     summary)
from .state import (build_ledger, entry_state, ledger_rows, load_toc,
                    toc_window, toc_search, WINDOW)
from .validate import validate


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--json", action="store_true",
                    help="indented JSON instead of TOON")

    # The same two globals accepted *after* the verb as well, which is where a
    # hand types them. SUPPRESS is what makes that safe: without it the
    # subparser's own default would overwrite a value given before the verb.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="indented JSON instead of TOON")

    sub = ap.add_subparsers(dest="cmd", required=True)
    add = lambda name, **kw: sub.add_parser(name, parents=[common], **kw)

    # Verbs that name a page all take the ref the same way and reject a bare
    # integer identically — `state` included, since a seam record belongs to
    # one page as much as a context does.
    for name in ("context", "validate", "state"):
        p = add(name)
        p.add_argument("ref", metavar="PP-NNN",
                       help="page ref: part and scan index, e.g. 1-048")
        if name == "validate":
            p.add_argument("--ratified", action="store_true",
                           help="expect human-ratified provenance (resp='#ed') on "
                                "Tier-1 spans instead of the collation pass's "
                                "'#llm'; a remaining '#llm' becomes a worklist line")

    add("pages")

    lg = add("ledger", help="the seam table across every scan — "
                        "folio, heading fold, boundary")
    lg.add_argument("--part", type=int, default=None,
                    help="restrict to one part")
    lg.add_argument("--untranscribed", action="store_true",
                    help="bare refs with no committed TEI, one per line")

    ts = add("toc-search", help="ToC entries whose title matches a "
                        "heading you've read off the page (word-set match) — "
                        "for resolving a heading toc_window came back empty or "
                        "thin on, against a folio you now know")
    ts.add_argument("query", help="heading text as read off the page")
    ts.add_argument("--folio", type=int, default=None,
                    help="sort matches near this folio first")

    tn = add("toc-near", help="ToC entries near a *known* folio — "
                        "use once the printed folio has been read off the "
                        "page, not a substitute for toc_window's prediction")
    tn.add_argument("folio", type=int)
    tn.add_argument("--span", type=int, default=WINDOW,
                    help=f"folios either side of the target (default {WINDOW})")

    ln = add("lines", help="per-line records for one page — line id, geometry "
                        "and text, in ALTO order with empties kept, which is the "
                        "join detector_flags' line numbers cannot supply")
    ln.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-048")
    ln.add_argument("--from", dest="alto_dir", default="end-of-eval",
                    help="ALTO directory to read (default end-of-eval)")
    ln.add_argument("--crops", type=Path, default=None,
                    help="also write one PNG per line under this directory")
    ln.add_argument("--sheets", type=Path, default=None,
                    help="compose the line crops into labelled contact sheets here, "
                         "index drawn in the margin, nothing downscaled — the reading "
                         "pass's instrument; emits the sheet/lines map instead of the "
                         "line table")
    ln.add_argument("--per-sheet", type=int, default=8,
                    help="lines per contact sheet (default 8)")
    ln.add_argument("--margins", action="store_true",
                    help="widen every crop to the PrintSpace margins — a line "
                         "polygon can exclude printed text that belongs to the "
                         "line, and what it excludes sits in the margin (list "
                         "numbers, the folio)")
    ln.add_argument("--full", action="store_true",
                    help="include baseline and polygon points, which are long "
                         "enough to make the table unreadable by default")

    zm = add("zoom", help="magnify selected lines — overlapping strips at an "
                        "integer scale, packed into as few sheets as the height "
                        "budget allows, for the second look a contact sheet leaves "
                        "open")
    zm.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-073")
    zm.add_argument("--only", default=None, metavar="SPEC",
                    help="line indices to magnify, e.g. 7,20,22-26 "
                         "(default every line on the page)")
    zm.add_argument("--zoom", type=int, default=ZOOM,
                    help=f"display px per source px, as delivered (default {ZOOM}). "
                         "Higher wraps each line into more strips, and a form seen "
                         "only in halves is the risk being traded against — escalate "
                         "for one question, not by default. --zoom 1 wraps least")
    zm.add_argument("--window", type=int, default=None,
                    help="source px per strip; derived from --zoom so that the "
                         "delivered scale really is --zoom. Overriding it upward "
                         "makes the sheet exceed the client width, and the scale is "
                         "then whatever the client's fitting leaves")
    zm.add_argument("--client-w", type=int, default=ZOOM_CLIENT_W,
                    help=f"px the reading client shows per image (default "
                         f"{ZOOM_CLIENT_W}); every sheet is padded to exactly this, "
                         "so the scale does not vary with how long the lines are")
    zm.add_argument("--overlap", type=int, default=ZOOM_OVERLAP,
                    help=f"px shared by consecutive strips (default "
                         f"{ZOOM_OVERLAP}), so no glyph is only ever seen cut")
    zm.add_argument("--sheet-h", type=int, default=ZOOM_SHEET_H,
                    help=f"max sheet height in px (default {ZOOM_SHEET_H}) — a "
                         "taller sheet gets fitted to the display, undoing the zoom")
    zm.add_argument("--margins", action="store_true",
                    help="widen to the PrintSpace margins, to catch text a line "
                         "polygon excludes")
    zm.add_argument("--smooth", action="store_true",
                    help="Lanczos instead of nearest-neighbour: better for "
                         "comparing letterforms, worse for deciding whether a "
                         "faint mark is present, since it invents greys")
    zm.add_argument("--out", type=Path, default=Path("review/zoom"),
                    help="output directory (default review/zoom)")
    zm.add_argument("--from", dest="alto_dir", default="end-of-eval",
                    help="ALTO providing the line geometry (default end-of-eval)")

    rv = add("review", help="span-level diff between a reading proposal and the "
                        "recognizer output, grouped by substitution class — the "
                        "queue for rebuilding ground truth")
    rv.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-074")
    rv.add_argument("--from", dest="alto_dir", default="end-of-eval",
                    help="recognizer ALTO directory (default end-of-eval)")
    rv.add_argument("--html", type=Path, default=None,
                    help="write the browser review page here instead of a table")
    rv.add_argument("--spans", action="store_true",
                    help="every span individually, not grouped by class")
    rv.add_argument("--serve", action="store_true",
                    help="serve the review page on 127.0.0.1 and accept saves "
                         "into review/decisions/PP-NNN.json")
    rv.add_argument("--port", type=int, default=8731)

    rs = add("restore", help="write adjudicated review decisions into "
                        "gt/ocr/ as ground truth, keeping the recognizer geometry")
    rs.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-074")
    rs.add_argument("--from", dest="alto_dir", default="end-of-eval",
                    help="ALTO providing the line geometry (default end-of-eval)")
    rs.add_argument("--force", action="store_true",
                    help="overwrite a target that already holds text — only 1-048 "
                         "and 2-030 do, and they are the surviving hand-keyed pages")

    nz = add("normalize", help="NFD conformance and lookalike census across "
                        "the corpus stores (keying spec section 1) — --check "
                        "reports and exits 1 on drift, bare form converts")
    nz.add_argument("--check", action="store_true",
                    help="report only; exit 1 if any file is not NFD")
    nz.add_argument("--dry-run", action="store_true",
                    help="with no --check: name the files that would change")

    lx = add("lexicon", help="frequency-ranked lexicon_miss tokens "
                        "across every OCR'd page, for bulk approval into "
                        "data/lexicon_extra.txt")
    lx.add_argument("--suggest", action="store_true",
                    help="accepted for symmetry; this is the only mode")

    a = ap.parse_args(argv)
    out = lambda obj: print(emit(obj, a.json))

    try:
        if a.cmd == "pages":
            out(all_refs(a.root))
            return 0
        if a.cmd == "state":
            out(entry_state(a.ref, a.root))
            return 0
        if a.cmd == "ledger":
            if a.untranscribed:
                # A work queue, not a document: bare refs pipe into xargs.
                led = build_ledger(a.root)
                from .context import parse_ref
                print(emit_lines(r for r, v in led.items()
                                 if not v["transcribed"]
                                 and (a.part is None or parse_ref(r)[0] == a.part)))
                return 0
            out(ledger_rows(a.root, part=a.part))
            return 0
        if a.cmd == "context":
            out(build_context(a.ref, a.root))
            return 0
        if a.cmd == "validate":
            ctx = build_context(a.ref, a.root)
            rep = validate(Path(ctx["output_path"]), ctx, ratified=a.ratified)
            # The gate's default face is the rendered report — it is read by a
            # human deciding whether to commit. --json is for anything that
            # needs the verdict as data; the exit code is the contract either way.
            if getattr(a, "json", False):
                out({"ok": rep.ok, "errors": rep.errors, "warnings": rep.warnings,
                     "worklist": rep.worklist, "metrics": rep.metrics})
            else:
                print(rep.render())
            return 0 if rep.ok else 1
        if a.cmd == "toc-search":
            out(toc_search(load_toc(a.root), a.query, folio=a.folio))
            return 0
        if a.cmd == "toc-near":
            out(toc_window(load_toc(a.root), a.folio, [], span=a.span))
            return 0
        if a.cmd == "lexicon":
            out(suggest_lexicon(a.root))
            return 0
        if a.cmd == "zoom":
            out(write_line_zoom(
                a.ref, a.out,
                only=parse_selection(a.only) if a.only else None,
                zoom=a.zoom, window=a.window, overlap=a.overlap,
                sheet_h=a.sheet_h, client_w=a.client_w,
                alto_dir=a.alto_dir, root=a.root,
                margins=a.margins, smooth=a.smooth))
            return 0
        if a.cmd == "lines":
            if a.sheets:
                # The sheet map is its own table — a different key set from the line
                # records, so it cannot be merged into one emit without collapsing
                # both to the verbose nested form.
                out(write_line_sheets(a.ref, a.sheets, a.alto_dir, a.root,
                                      per_sheet=a.per_sheet, margins=a.margins))
                return 0
            recs = (write_line_crops(a.ref, a.crops, a.alto_dir, a.root,
                                     margins=a.margins) if a.crops
                    else page_lines(alto_for_lines(a.ref, a.alto_dir, a.root)))
            if not a.full:
                # Drop the two long geometry strings. Dropped from every record,
                # never some — a ragged key set collapses the table to the
                # verbose nested form (see emit.py).
                drop = ("baseline", "points")
                recs = [{k: v for k, v in r.items() if k not in drop} for r in recs]
            out(recs)
            return 0
        if a.cmd == "review":
            if a.serve:
                serve(a.ref, a.alto_dir, a.root, a.port)
                return 0
            if a.html:
                a.html.parent.mkdir(parents=True, exist_ok=True)
                a.html.write_text(
                    render_queue_html(a.ref, a.alto_dir, a.root), encoding="utf-8")
                print(f"{a.html}: review page for {a.ref}")
                return 0
            spans = page_spans(a.ref, a.alto_dir, a.root)
            n = len(page_lines(alto_for_lines(a.ref, a.alto_dir, a.root)))
            # Two calls, two tables. Summary and queue have different key sets, so
            # emitting them as one list would collapse the whole thing to the
            # verbose nested form (see emit.py).
            print(emit(summary(spans, n), getattr(a, "json", False)))
            out(spans if a.spans else group_spans(spans))
            return 0
        if a.cmd == "restore":
            out(restore(a.ref, a.alto_dir, a.root, a.force))
            return 0
        if a.cmd == "normalize":
            if a.check:
                rep = scan(a.root)
                out(rep)
                # NFD drift and an unlicensed mark both block: each is an error with
                # no reading to adjudicate. The lookalike census does not — it is a
                # to-key worklist needing a human ruling on what the page prints,
                # which is firewalled, same contract as validate's WORKLIST.
                return 1 if (rep["nfd_offenders"]
                             or rep["unlicensed_marks"]) else 0
            out(convert(a.root, dry_run=a.dry_run))
            return 0
    except (ValueError, FileNotFoundError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
