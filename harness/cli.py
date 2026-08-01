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
  uv run harness authority TEXT   -> works in data/authorities.json matching a
                                     citation read in the body; --sigla for the
                                     whole resolution table, --key for one record
  uv run harness lexicon          -> frequent lexicon misses, to whitelist
  uv run harness lexicon --native -> inverted: frequent native word forms,
                                     from restored ground truth, for spotting
                                     a likely misspelling by comparison
  uv run harness lexicon --marks  -> bare-vs-marked frequency per base letter,
                                     same corpus (e.g. plain g vs dotted g̣)
  uv run harness lexicon --suffixes -> weighted suffix frequency (len 2-8),
                                     marks stripped, same corpus
  uv run harness lexicon --digraphs -> weighted digraph/trigraph frequency,
                                     marks and the top suffixes stripped
  uv run harness normalize        -> NFD + §2.9 spacing + lookalike gate,
                                     report only; --convert required to write
  uv run harness figures          -> reconcile gt/fig/ zone geometry against
                                     data/readings.md captions, both directions;
                                     exit 1 if `missing` or `orphan` is non-empty
  uv run harness zones            -> sweep gt/zones/; with a ref, that page's
                                     errors and warnings in full
  uv run harness zones 1-048 --serve -> the segmentation editor: two clicks a
                                     zone, x from data/zones_config.json, arrow
                                     keys walk the corpus
  uv run harness zones --blot     -> the figure-blotted training rasters
  uv run harness zones --assemble -> bogoras-seg/, ready for ketos segtrain
  uv run harness zones --predict  -> run the trained segmenter into mz/zones/
  uv run harness zones --link     -> rebuild zones/, the view over both stores
  uv run harness zones --from mz  -> check the machine store: same report, but
                                     measurement, so it never sets the exit code

The line verbs (`lines`, `zoom`, `review`, `restore`) read ALTO from `ocr/` unless
`--from` says otherwise. That is the read view over every OCR store, not a store
itself; writes always name `gt/ocr/`. See lines.DEFAULT_ALTO_DIR.

Output is TOON (see emit.py). `--json` on any verb restores indented JSON for
anything that needs to parse it as a contract.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from .authorities import (load as load_authorities, parse_citation as authority_parse,
                          record as authority_record, search as authority_search, sigla)
from .context import build_context, all_refs, norm_ref
from .detectors import (digraph_frequency, mark_base_frequency, suffix_frequency,
                        suggest_lexicon, suggest_native_forms)
from .emit import emit, emit_lines
from .lines import (DEFAULT_ALTO_DIR, LINE_SHEET_H, ZOOM, ZOOM_CLIENT_W,
                    ZOOM_OVERLAP, ZOOM_SHEET_H, alto_for_lines,
                    adopt_gaps, line_gaps, page_lines, parse_selection,
                    write_blot,
                    write_line_crops,
                    write_line_sheets, write_line_zoom)
from .normalize import scan, convert
from .paths import (clean, crops_dir, ensure_page_link, html_path, proposal_path,
                    sheets_dir, zoom_dir)
from .proposal_check import (check as check_proposal, fix as fix_proposal,
                             line_codepoints, replace_in_field,
                             set_field as set_proposal_field)
from .review import (group_spans, page_spans, render_queue_html, restore, serve,
                     summary)
from .state import (build_ledger, entry_state, ledger_rows, load_toc,
                    toc_window, toc_search, WINDOW)
from .validate import validate, check_corpus_header
from .zones import DEFAULT_MODEL as ZONES_MODEL
from .seam import set_seam
from .ids import fix_page as fix_ids, glossary, pair_glosses


def main(argv=None):
    # The module docstring is a worked usage summary and was visible only to
    # someone reading the source. Raw formatting because it is already laid out.
    ap = argparse.ArgumentParser(
        prog="harness", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."),
                    help="repo root; every path resolves against it (default .)")
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
    #
    # These carried no `help=` for most of the project's life, purely because they
    # were written before the habit set in. argparse omits a helpless subparser
    # from the listing entirely, so the four most load-bearing verbs in the
    # collation loop appeared only as bare names inside the brace list.
    PAGE_VERB_HELP = {
        "context": "the whole per-page input contract for the collation pass, on "
                   "stdout — seam state, ToC neighbourhood, figure zones and their "
                   "captions, OCR line ids, detector flags. Deterministic and "
                   "precomputed: the pass consumes this and never re-derives it",
        "validate": "the gate on one page's TEI. Exit 1 on FAIL. Checks the output "
                    "contract, that every @facs resolves against a supplied zone or "
                    "OCR line, and that every Tier-1 span carries a @resp rank — an "
                    "unmarked span being indistinguishable from a ratified one to "
                    "anything that does not look",
        "state": "one page's seam record — the folio predicted for it, what that "
                 "prediction rests on, and which headings are believed open. "
                 "expected_folio is null wherever the chain of transcribed pages "
                 "breaks, which means read it off the image, not that anything failed",
    }
    for name in ("context", "validate", "state"):
        p = add(name, help=PAGE_VERB_HELP[name])
        p.add_argument("ref", metavar="PP-NNN",
                       help="page ref: part and scan index, e.g. 1-048")
        if name == "validate":
            p.add_argument("--ratified", action="store_true",
                           help="expect human-ratified provenance (resp='#ed') on "
                                "Tier-1 spans instead of the collation pass's "
                                "'#llm'; a remaining '#llm' becomes a worklist line")

    idp = add("ids", help="check one page's structural ids against the scheme "
                          "{kind}-{PP-NNN}-{ordinal}, where the ordinal is the "
                          "element's position among same-kind elements in document "
                          "order — so every id is recomputable from the tree alone. "
                          "--fix renumbers, repairing any inbound @prev/@next from "
                          "a neighbour in the same write")
    idp.add_argument("ref", metavar="PP-NNN", help="page ref, e.g. 1-100")
    idp.add_argument("--fix", action="store_true",
                     help="write the canonical ids (and neighbours' pointers); "
                          "without it, report what would change")
    idp.add_argument("--pair", action="store_true",
                     help="link each <gloss> to its <term> where containment "
                          "decides — one of each in a container. Where it does "
                          "not (two pairs in one item), report and write nothing: "
                          "choosing would be inference. Add --fix to write")

    sm = add("seam", help="record whether an element runs across the gap BEFORE "
                          "this page, writing @part on this page's first "
                          "top-level element and the previous page's last. The "
                          "page after the gap writes both ends, because it is the "
                          "only one holding both witnesses. Preview unless "
                          "--commit")
    sm.add_argument("ref", metavar="PP-NNN",
                    help="the page AFTER the gap, e.g. 1-100 for the 1-099/1-100 seam")
    g = sm.add_mutually_exclusive_group(required=True)
    g.add_argument("--continues", dest="open_gap", action="store_true",
                   help="an element carries across: this page opens mid-element")
    g.add_argument("--fresh", dest="open_gap", action="store_false",
                   help="clean break: this page opens a new element. Clears the "
                        "claim on both sides if one was recorded")
    sm.add_argument("--commit", action="store_true",
                    help="write both files; without it, report what would change")

    add("header", help="the gate on the corpus teiHeader — that it exists, and "
                       "that the provenance ranks it declares are exactly the ones "
                       "validate enforces on every page. Two files hold one fact; "
                       "without this they can drift apart silently, because a page "
                       "is a fragment and never resolves @resp locally. Exit 1 on "
                       "FAIL")

    add("pages", help="every ref with OCR present, i.e. workable now. Sparse by "
                      "construction — a pilot selection scattered through the "
                      "volume, not a prefix of it")

    lg = add("ledger", help="the seam table across every scan — folio, heading "
                        "fold, and whether an element runs across the gap after "
                        "each page. That last is read off the committed TEI's "
                        "@part/@next, where `harness seam` puts it; 'unknown' "
                        "means the page is not collated, not that it is closed")
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
    ln.add_argument("--from", dest="alto_dir", default=DEFAULT_ALTO_DIR,
                    help=f"ALTO directory to read (default {DEFAULT_ALTO_DIR}, the "
                         "read view over every OCR store)")
    ln.add_argument("--adopt-gap", metavar="VPOS[,VPOS...]", default=None,
                    help="materialize the named --gaps bands as empty TextLines in "
                         "gt/ocr/, so a dropped line can be keyed. Geometry only, "
                         "never CONTENT: text still arrives via decision.json -> "
                         "restore. Each VPOS must match a measured band; naming "
                         "which bands are real lines is the human call")
    ln.add_argument("--blot", action="store_true",
                    help="write the page to scans-blotted/ with every line box and "
                         "figure zone painted out, so whatever remains is uncovered "
                         "by construction. The visual counterpart to --gaps, and a "
                         "check on it: nothing is thresholded here, only covered")
    ln.add_argument("--gaps", action="store_true",
                    help="bands of ink on the raster that no TextLine covers — the "
                         "dropped-line detector. The segmentation this corpus was "
                         "built from drops whole printed lines and nothing else "
                         "notices, because the text that IS there is correct. "
                         "Measured off the page, so the geometry a repair needs "
                         "comes with the report. Expect running heads and folios "
                         "among the hits: a band is a place to look, not a verdict")
    ln.add_argument("--crops", action="store_true",
                    help="also write one PNG per line, into review/PP-NNN/crops/")
    ln.add_argument("--sheets", action="store_true",
                    help="compose the line crops into labelled contact sheets in "
                         "review/PP-NNN/sheets/, index drawn in the margin, nothing "
                         "downscaled — the reading pass's instrument; emits the "
                         "sheet/lines map instead of the line table")
    ln.add_argument("--out", type=Path, default=None,
                    help="write the images somewhere other than the page's own "
                         "review/PP-NNN/ subdirectory — for a one-off comparison, "
                         "not for the pass, whose files the other verbs expect to "
                         "find in the default place")
    ln.add_argument("--per-sheet", type=int, default=40,
                    help="lines per contact sheet, upper bound only — --sheet-h "
                         "packs by height first (default 40)")
    ln.add_argument("--sheet-h", type=int, default=LINE_SHEET_H,
                    help=f"max contact-sheet height in px (default {LINE_SHEET_H}); "
                         "fewer, fuller sheets for the same lines")
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
    zm.add_argument("--out", type=Path, default=None,
                    help="output directory (default review/PP-NNN/zoom)")
    zm.add_argument("--from", dest="alto_dir", default=DEFAULT_ALTO_DIR,
                    help=f"ALTO providing the line geometry (default {DEFAULT_ALTO_DIR})")

    rv = add("review", help="adjudicate a reading proposal in the browser "
                        "(--serve); bare, a span-level diff of the proposal "
                        "against a second witness, grouped by substitution class")
    rv.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-074")
    rv.add_argument("--from", dest="alto_dir", default=DEFAULT_ALTO_DIR,
                    help=f"ALTO directory to read (default {DEFAULT_ALTO_DIR}). For "
                         "the bare span diff this must name a genuine second "
                         "witness: diffing a proposal against the ground truth it "
                         "produced compares a file with itself")
    rv.add_argument("--html", action="store_true",
                    help="write the browser review page to review/PP-NNN/review.html "
                         "instead of emitting a table. No destination knob: the page "
                         "embeds its crops as data URIs, so where it sits is nobody's "
                         "business but the pass's, and --serve is the usual route")
    rv.add_argument("--spans", action="store_true",
                    help="every span individually, not grouped by class")
    rv.add_argument("--serve", action="store_true",
                    help="serve the review page on 127.0.0.1 and accept saves "
                         "into review/PP-NNN/decision.json")
    rv.add_argument("--port", type=int, default=8731)

    rs = add("restore", help="preview (default) or write adjudicated review "
                        "decisions into gt/ocr/ as ground truth, keeping the "
                        "source geometry — --commit required to write. Reports "
                        "mode=restoration (filled from another store) or "
                        "mode=revision (the finished page re-edited in place)")
    rs.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-074")
    rs.add_argument("--from", dest="alto_dir", default=DEFAULT_ALTO_DIR,
                    help=f"ALTO providing the line geometry (default {DEFAULT_ALTO_DIR})")
    rs.add_argument("--force", action="store_true",
                    help="overwrite a target that already holds text. Every page in "
                         "gt/ocr/ does now that the rebuild is complete, so this is "
                         "how a revision says it meant it — required for one")
    rs.add_argument("--commit", action="store_true",
                    help="actually write gt/ocr/ — bare form only previews the "
                         "report (edits, geometry_drift, text_mismatch) and writes "
                         "nothing, same contract as normalize's --convert")

    cl = add("clean", help="remove a page's derived working files (crops, sheets, "
                        "zoom, review.html) — leaving proposal.json and "
                        "decision.json in place; run once a page is restored")
    cl.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-053")

    add("figures", help="reconcile the figure track — gt/fig/ zone geometry "
                        "against data/readings.md caption text, in both "
                        "directions. `missing` (a zone whose caption was never "
                        "read) and `orphan` (a reading whose zone is gone) must "
                        "both be empty; a total that merely matches is not "
                        "coverage, which is how two absent pages once went "
                        "unnoticed by cancelling against two zone-only ones")

    zo = add("zones", help="the seven-type page segmentation in gt/zones/ — a "
                        "vertical partition of the text column, two clicks per "
                        "zone, x taken from data/zones_config.json and never from "
                        "the pointer. Bare form sweeps every keyed page; with a "
                        "ref it reports that page's errors and warnings in full. "
                        "Errors are mechanical (a width no column offers, two "
                        "zones on top of each other) and set the exit code; the "
                        "ordering assumptions are warnings, configurable and "
                        "exemptible, because a page that breaks them is the "
                        "interesting page rather than the rejected one")
    zo.add_argument("ref", metavar="PP-NNN", nargs="?",
                    help="page ref, e.g. 1-048. Omit to sweep the whole store")
    zo.add_argument("--serve", action="store_true",
                    help="open the segmentation editor on 127.0.0.1 at the given "
                         "ref and keep serving — the session steps through pages "
                         "with the arrow keys and saves into gt/zones/, so the ref "
                         "is where to start, not the only page reachable")
    zo.add_argument("--port", type=int, default=8732,
                    help="port for --serve (default 8732; `review --serve` holds "
                         "8731, so both can run at once)")
    zo.add_argument("--itinerary", metavar="LST", default=None,
                    help="a work-list to walk instead of scan order: an .lst file "
                         "in gt/seg's format, or a directory taken to mean every "
                         "page file in it (so `--itinerary gt/seg` is that whole "
                         "selection, which was chosen for heterogeneity). With "
                         "--serve the arrow keys follow it and the ref may be "
                         "omitted, in which case the session opens at the first "
                         "page on the list not yet keyed. Without --serve it "
                         "scopes the sweep to the same pages")
    zo.add_argument("--ink", action="store_true",
                    help="with the corpus sweep: also read every raster and report "
                         "ink no zone accounts for. Off by default because it costs "
                         "~0.20 s a page against ~1 ms for the file-level checks; "
                         "always on for a single page, where it is the check that "
                         "catches a dropped zone")
    zo.add_argument("--blot", action="store_true",
                    help="write the figure-blotted raster used for training — "
                         "gt/fig/ zones painted white so paragraph wrap around an "
                         "illustration cannot shape what the model learns. With a "
                         "ref, one page; bare, all 832")
    zo.add_argument("--assemble", action="store_true",
                    help="build bogoras-seg/ from the train/eval marks: each page's "
                         "zone ALTO beside its blotted raster, ready for ketos "
                         "segtrain. Reports the invocation; runs nothing")
    zo.add_argument("--predict", action="store_true",
                    help="run the trained segmenter and write raw ALTO into "
                         "mz/zones/ — the machine store, never gt/. With a ref, one "
                         "page (and an exempt mark does not stop it: naming a page "
                         "is the request); with --itinerary, that list; bare, every "
                         "page that has a blotted raster and is not marked exempt. "
                         "Input is always the blotted raster, since that is what "
                         "the model was trained on")
    zo.add_argument("--model", default=None,
                    help=f"the segmentation model for --predict "
                         f"(default {ZONES_MODEL})")
    zo.add_argument("--decode", choices=("raw", "dp"), default="raw",
                    help="how a prediction becomes zones. 'raw' vectorises each "
                         "class heatmap blob-wise, as kraken does. 'dp' decodes the "
                         "page as a chain of bands by exact dynamic programming, "
                         "which makes overlaps and sub-minimum slivers "
                         "unrepresentable and merges a fragmented band — the "
                         "mechanical rules built in rather than checked afterwards. "
                         "The order rules are deliberately left out: they are "
                         "warnings, and a decoder that could not break them would "
                         "make them unfalsifiable")
    zo.add_argument("--device", default="auto",
                    help="torch device for --predict — 'auto' takes cuda:0 when it "
                         "is available, else cpu")
    zo.add_argument("--score", action="store_true",
                    help="compare predictions against gt/zones/ — recall and "
                         "precision per split, never blended, plus the confusion "
                         "matrix and a held-out permutation test. Bare, it scores "
                         "what is in mz/zones/; with --model it segments in memory "
                         "and writes nothing, which is how a checkpoint gets "
                         "measured before it is installed. --decode picks the "
                         "decoder. Refuses if bogoras-seg/*.lst is gone: the live "
                         "split lists move, so without the frozen ones the training "
                         "pages cannot be told from the rest")
    zo.add_argument("--install", metavar="CHECKPOINT", default=None,
                    help="install a trained checkpoint into models/bogoras-seg/ "
                         "with a manifest beside it. Scores it in memory first and "
                         "**refuses a permuted class map** — that check stops being "
                         "something to remember and becomes a precondition of the "
                         "artifact existing. The manifest records the split it "
                         "trained on, its classes and merges, a digest of gt/zones/ "
                         "at the time, and the score; every path in it is relative. "
                         "Preview without --commit; --name sets the installed name")
    zo.add_argument("--name", default="zones-seg",
                    help="installed model name for --install (default zones-seg)")
    zo.add_argument("--remap-model", dest="remap_model", action="store_true",
                    help="put the learned names back on the model's output "
                         "channels, when --score shows the disagreement is a "
                         "consistent relabelling rather than a weak model. Derives "
                         "the map on the training pages, refuses unless it is 1-1 "
                         "and holds out; preview only without --commit, and the "
                         "original is kept as .bak")
    zo.add_argument("--commit", action="store_true",
                    help="required to write: with --remap-model it rewrites the "
                         "model's class map, with --install it copies the "
                         "checkpoint and its split into models/bogoras-seg/. To "
                         "*see* the paragraph split, open the editor and press / to "
                         "the `split` view — it is computed on open and stored "
                         "nowhere, being a proposal derived from gt rather than "
                         "anything a machine produced")
    zo.add_argument("--lines", action="store_true",
                    help="with a ref: every zone's lines of type — 1-based zone and "
                         "line, y, height, indent against the page's own body "
                         "margin, width. `h` is the tell for the two line-detection "
                         "failures: ~6 px is a speck that passed the floor, ~100 px "
                         "is two lines a descender welded. Off by default — it is "
                         "only wanted when something inside a zone is in question, "
                         "and it costs a second raster decode")
    zo.add_argument("--delete", action="store_true",
                    help="with a ref: un-key the page — remove its file from "
                         "gt/zones/ and every mark that referred to it (split, rule "
                         "and ink exemptions). The one thing the store could not "
                         "express: `save_zones` refuses an empty save, so a page "
                         "keyed in error could be corrected but not withdrawn. "
                         "Keeps `.prev`, records the act in the journal, and needs "
                         "--commit; preview otherwise")
    zo.add_argument("--diff", action="store_true",
                    help="what differs between gt/zones/ and mz/zones/ — paired by "
                         "vertical overlap, reported as only_in_gt (a missed "
                         "region), only_in_mz (an invented one), label (paired but "
                         "named differently) or edge (same region, cut elsewhere, "
                         "beyond min_zone_h_px). With a ref, that page; bare, every "
                         "page in both stores")
    zo.add_argument("--paragraphs", action="store_true",
                    help="audit the paragraph-boundary rule, both directions. "
                         "`false_negative` = a boundary gt asserts that the rule "
                         "would not recover, which is a trustworthy recall figure; "
                         "`false_positive` = the rule firing inside a zone, a "
                         "worklist and NOT a precision figure, since each is either "
                         "a keying slip or a false alarm and gt cannot arbitrate. "
                         "The segmenter cannot do this check at all: two abutting "
                         "MainZone-P rectangles rasterize to one target. Reports "
                         "ref, zone and 1-based line index; report only, exit 0")
    zo.add_argument("--link", action="store_true",
                    help="rebuild zones/, the read view over both stores: one name "
                         "per page, the human file winning wherever it exists. "
                         "Derived and gitignored; reads may resolve through it, "
                         "writes never do")
    zo.add_argument("--from", dest="store", choices=("gt", "mz"), default="gt",
                    help="which store to check: 'gt' (default) is the human one and "
                         "errors set the exit code; 'mz' is the machine one and is "
                         "measurement — it always exits 0, because nothing there is "
                         "ratified and a raw polygon fails the fixed-measure width "
                         "check by construction. A closed set of two rather than a "
                         "free directory, and the view is deliberately not offered: "
                         "checking through zones/ would blend ratified and "
                         "unratified pages under one exit code")

    nz = add("normalize", help="NFD conformance, §2.9 spacing, and lookalike "
                        "census across the corpus stores — bare form (or "
                        "--check) only reports; --convert is required to write")
    nz_mode = nz.add_mutually_exclusive_group()
    nz_mode.add_argument("--check", action="store_true",
                    help="report only; exit 1 on drift (this is also the default "
                         "with neither flag — bare `normalize` never writes)")
    nz_mode.add_argument("--convert", action="store_true",
                    help="write the fixes. Required to touch any file — there is "
                         "no bare-form write any more, scoped or not")
    nz.add_argument("--dry-run", action="store_true",
                    help="with --convert: name the files that would change, write nothing")
    nz.add_argument("--path", type=Path, action="append", default=None,
                    help="scope to this file or directory instead of the whole "
                         "corpus (repeatable) — for checking/converting one "
                         "just-authored file, e.g. a proposal, or a whole page "
                         "directory like review/1-052, without touching the "
                         "other 280+ corpus files")

    pc = add("proposal-check", help="cross-check a reading proposal's `resolved` "
                        "field against the codepoints its `text` actually contains "
                        "— catches a mistyped combining mark (ring below for dot "
                        "below, diaeresis for caron) before it reaches review. Also "
                        "flags a straight apostrophe anywhere (never a genuine "
                        "reading, corpus-wide) and a bare suffix matching a known "
                        "dot-prone shape (keying_spec.md §5.1, e.g. -gɪn/-gɪt/-gɪ "
                        "missing g's dot-below), unconditionally")
    pc.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-052")
    pc.add_argument("--path", type=Path, default=None,
                    help="proposal file (default review/PP-NNN/proposal.json)")
    pc.add_argument("--fix", action="store_true",
                    help="apply the one unambiguous correction (a single mark "
                         "the resolved field names but the text doesn't contain, "
                         "swapped for the single mark text has that resolved "
                         "doesn't) and write the file back")
    pc.add_argument("--codepoints", metavar="LINE", default=None,
                    help="name every non-ASCII character in one line's field "
                         "instead of running the resolved/text check — a spot "
                         "check while authoring, before resolved is even written")
    pc.add_argument("--field", default="text", choices=("text", "resolved", "note"),
                    help="field to inspect, with --codepoints (default text)")
    pc.add_argument("--set", metavar="LINE", default=None,
                    help="set one line's field (see --field) instead of checking "
                         "— value comes from --value or stdin, and is NFD-"
                         "normalized on write, so it never fights an Edit-tool "
                         "exact-match failure against the file's own NFD form "
                         "(a precomposed ñ typed by hand vs. the file's n+U+0303)")
    pc.add_argument("--value", default=None,
                    help="the replacement text for --set; omit to read stdin")
    pc.add_argument("--replace", metavar="LINE", default=None,
                    help="replace occurrence(s) of --old with --new in one "
                         "line's field (see --field) instead of checking — "
                         "the surgical alternative to --set for a single "
                         "wrong character in an otherwise-correct line: --set "
                         "retypes the whole field, which risks a second, "
                         "unrelated slip while fixing the first")
    pc.add_argument("--old", default=None,
                    help="text to find, with --replace")
    pc.add_argument("--new", default=None,
                    help="text to substitute, with --replace")
    pc.add_argument("--which", default="all",
                    help="with --replace: which occurrence(s) of --old to "
                         "replace — \"all\" (default), \"first\", \"last\", "
                         "an occurrence number (\"3\"), or an inclusive range "
                         "(\"2:4\"), all 1-based, left to right")

    au = add("authority", help="works in data/authorities.json matching a "
                        "citation read in the body — the siglum (Dall, I), a "
                        "bare name in prose (Krause reports…), a title, or any "
                        "string off the printed entry. Every match is returned "
                        "and ranked, never resolved to one: 51 sigla share 34 "
                        "names, so a single answer would be manufactured. No "
                        "hit is a legitimate outcome — the list is open")
    au.add_argument("query", nargs="?", default="",
                    help="a citation or a name as read off the page, not a "
                         "sentence: matching is word-set containment, so 'Krause' "
                         "finds the prose reference and 'Krause reports' finds "
                         "nothing. A footnote form ('Dall, I, p. 375.') is "
                         "accepted whole — the volume and page locator are lifted "
                         "out and the lift is echoed on stderr. Omit to list all 73")
    au.add_argument("--volume", default=None,
                    help="volume the citation names (II or 2, either form); "
                         "normally read out of the query itself. Excludes on "
                         "contradiction, not absence — a work whose every siglum "
                         "names a different volume drops out, one with no siglum "
                         "or no recorded volume stays in")
    au.add_argument("--sigla", action="store_true",
                    help="the resolution table instead: one row per cited_as "
                         "entry rather than per work, so the collisions are "
                         "visible at once; QUERY, if given, restricts to that name")
    au.add_argument("--key", default=None,
                    help="one work in full, printed blocks included — printed is "
                         "the record and the parsed fields lose to it")
    au.add_argument("--unlocated", action="store_true",
                    help="only works with neither doi nor url — the 36 with no "
                         "copy located, i.e. the worklist")

    lx = add("lexicon", help="frequency-ranked lexicon_miss tokens "
                        "across every OCR'd page, for bulk approval into "
                        "data/lexicon_extra.txt; --native inverts to the most "
                        "frequent native (Tier-1) word forms in restored ground "
                        "truth, for spotting a likely misspelling by comparison; "
                        "--marks gives the bare-vs-marked frequency per base "
                        "letter over the same corpus; --suffixes and --digraphs "
                        "mine the same corpus for common affixes and n-grams")
    lx.add_argument("--glosses", action="store_true",
                    help="the corpus's term↔gloss pairs from committed TEI — the "
                         "dictionary the <gloss target> links make queryable. "
                         "Pairs come from @target and never from containment, so "
                         "terms nobody has linked are reported as a count rather "
                         "than guessed at. `scope` is the frame the entry's gloss "
                         "list supplies once as a supplied <head> and its glosses "
                         "never repeat — without which “white mixed with brown” "
                         "says nothing about what is white. It can arrive from the "
                         "previous page: a list running across a seam carries no "
                         "second head, so the scope resolves back through @prev")
    lx.add_argument("--native", action="store_true",
                    help="invert: most frequent native (Tier-1) word forms in "
                         "restored gt/ocr/, not English-lexicon misses")
    lx.add_argument("--marks", action="store_true",
                    help="bare-vs-marked frequency per base letter across the "
                         "native corpus — e.g. is a bare g or a dotted g̣ the "
                         "more likely reading, prior to the raster")
    lx.add_argument("--suffixes", action="store_true",
                    help="weighted suffix frequency (length 2-8) over the "
                         "native corpus, diacritics and stress marks stripped "
                         "before counting")
    lx.add_argument("--digraphs", action="store_true",
                    help="weighted digraph/trigraph frequency over the native "
                         "corpus, with marks and the corpus's own top suffixes "
                         "stripped first so stems aren't drowned by the "
                         "suffix family repeating itself")

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
        if a.cmd == "ids":
            fn = pair_glosses if a.pair else fix_ids
            out(fn(a.ref, a.root, commit=a.fix))
            return 0
        if a.cmd == "seam":
            out(set_seam(a.ref, a.open_gap, a.root, commit=a.commit))
            return 0
        if a.cmd == "header":
            rep = check_corpus_header(a.root)
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
        if a.cmd == "proposal-check":
            path = a.path or proposal_path(a.ref, a.root)
            if a.set is not None:
                value = a.value if a.value is not None else sys.stdin.read().rstrip("\n")
                out(set_proposal_field(path, a.set, a.field, value))
                return 0
            if a.replace is not None:
                if a.old is None or a.new is None:
                    print("--replace requires --old and --new", file=sys.stderr)
                    return 2
                out(replace_in_field(path, a.replace, a.field, a.old, a.new, a.which))
                return 0
            if a.codepoints is not None:
                out(line_codepoints(path, a.codepoints, a.field))
                return 0
            if a.fix:
                out(fix_proposal(path))
                return 0
            mismatches = check_proposal(path)
            out(mismatches)
            return 1 if mismatches else 0
        if a.cmd == "authority":
            works = load_authorities(a.root)
            if a.key:
                out(authority_record(works, a.key))
            elif a.sigla:
                out(sigla(works, a.query or None))
            else:
                # A footnote-form query carries a volume and a page locator that
                # are not searchable text; parse_citation lifts them out. Echoed
                # on stderr rather than folded into the payload, so stdout stays
                # the same bare table every other verb emits — but echoed at all,
                # because a silently rewritten query is an unexplainable miss.
                q, vol = authority_parse(a.query)
                if a.volume is None and vol is not None:
                    print(f"note: read volume {vol} out of the query; "
                          f"searching {q!r}", file=sys.stderr)
                out(authority_search(works, q, volume=a.volume or vol,
                                     unlocated=a.unlocated))
            return 0
        if a.cmd == "lexicon":
            if a.marks:
                out(mark_base_frequency(a.root))
            elif a.suffixes:
                out(suffix_frequency(a.root))
            elif a.digraphs:
                out(digraph_frequency(a.root))
            elif a.glosses:
                out(glossary(a.root))
            elif a.native:
                out(suggest_native_forms(a.root))
            else:
                out(suggest_lexicon(a.root))
            return 0
        # The page's own raster, linked into its working directory the first time a
        # verb materializes that directory. Convenience only — `harness clean` leaves
        # it, and it is keyed to the ref rather than to `--out`, which exists
        # precisely to write somewhere that is not the page's directory. Guarded on
        # the verb actually writing there, so a bare `harness lines PP-NNN` (which
        # only prints a table) does not conjure a directory as a side effect.
        writes_review_dir = (
            a.cmd == "zoom"
            or (a.cmd == "lines" and (getattr(a, "crops", False) or getattr(a, "sheets", False)))
            or (a.cmd == "review" and (getattr(a, "serve", False) or getattr(a, "html", False)))
        )
        if writes_review_dir and not getattr(a, "out", None):
            ensure_page_link(a.ref, a.root)

        if a.cmd == "zoom":
            out(write_line_zoom(
                a.ref, a.out or zoom_dir(a.ref, a.root),
                only=parse_selection(a.only) if a.only else None,
                zoom=a.zoom, window=a.window, overlap=a.overlap,
                sheet_h=a.sheet_h, client_w=a.client_w,
                alto_dir=a.alto_dir, root=a.root,
                margins=a.margins, smooth=a.smooth))
            return 0
        if a.cmd == "lines":
            if a.adopt_gap:
                out(adopt_gaps(a.ref, [int(v) for v in a.adopt_gap.split(",")],
                               a.alto_dir, a.root))
                return 0
            if a.blot:
                out(write_blot(a.ref, a.out or (a.root / "scans-blotted"),
                               a.alto_dir, a.root))
                return 0
            if a.gaps:
                out(line_gaps(a.ref, a.alto_dir, a.root))
                return 0
            if a.sheets:
                # The sheet map is its own table — a different key set from the line
                # records, so it cannot be merged into one emit without collapsing
                # both to the verbose nested form.
                out(write_line_sheets(a.ref, a.out or sheets_dir(a.ref, a.root),
                                      a.alto_dir, a.root,
                                      per_sheet=a.per_sheet, margins=a.margins,
                                      sheet_h=a.sheet_h))
                return 0
            recs = (write_line_crops(a.ref, a.out or crops_dir(a.ref, a.root),
                                     a.alto_dir, a.root,
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
                dest = html_path(a.ref, a.root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(
                    render_queue_html(a.ref, a.alto_dir, a.root), encoding="utf-8")
                print(f"{dest}: review page for {a.ref}")
                return 0
            # The bare span diff measures a proposal against a *second witness*. If
            # the store it is pointed at resolves to the ground truth the proposal
            # itself produced, the diff compares a file with its own source and
            # reports a clean 40/40 — the shape of verification without the
            # substance, which is exactly the fault that killed the old verbatim
            # firewall (CLAUDE.md, "What the firewall is not"). So refuse rather
            # than print a reassuring table: there is nothing here to measure.
            src = alto_for_lines(a.ref, a.alto_dir, a.root)
            gt = a.root / "gt" / "ocr" / f"chukchi-{norm_ref(a.ref)}.xml"
            if src.exists() and gt.exists() and src.resolve() == gt.resolve():
                print(f"ERROR: {src} resolves to the ground truth for {a.ref} "
                      f"({gt}), so a proposal diff against it would compare that "
                      "reading with itself and report no differences. The span "
                      "diff needs an independent witness — name one with --from, "
                      f"or use `harness review {a.ref} --serve` to adjudicate.",
                      file=sys.stderr)
                return 1
            spans = page_spans(a.ref, a.alto_dir, a.root)
            n = len(page_lines(src))
            # Two calls, two tables. Summary and queue have different key sets, so
            # emitting them as one list would collapse the whole thing to the
            # verbose nested form (see emit.py).
            print(emit(summary(spans, n), getattr(a, "json", False)))
            out(spans if a.spans else group_spans(spans))
            return 0
        if a.cmd == "restore":
            out(restore(a.ref, a.alto_dir, a.root, a.force, a.commit))
            return 0
        if a.cmd == "clean":
            out(clean(a.ref, a.root))
            return 0
        if a.cmd == "figures":
            from .figures import reconcile
            rep = reconcile(a.root)
            out(rep)
            # Exit non-zero on a real reconciliation failure, so this can gate.
            # The counts alone never decide it: 250 pages was once the expected
            # total *and* wrong in two compensating directions at the same time.
            return 1 if (rep["missing"] or rep["orphan"]) else 0
        if a.cmd == "zones":
            from . import zones as zmod
            from .zones_config import load_config
            itin = zmod.load_itinerary(a.itinerary, a.root) if a.itinerary else None
            if a.serve:
                start = a.ref
                if not start and itin:
                    # Resume: the first page on the list nobody has keyed. Falls
                    # back to the head of the list once it is finished, so the
                    # session still opens rather than refusing.
                    start = next((r for r in itin
                                  if not zmod.has_zones(r, a.root)), itin[0])
                if not start:
                    print("zones --serve needs a ref to start at, e.g. "
                          "`harness zones 1-048 --serve` — or an --itinerary to "
                          "take one from", file=sys.stderr)
                    return 2
                from .zones_ui import serve as serve_zones
                serve_zones(start, a.root, a.port, itin, a.itinerary or "")
                return 0
            if a.blot:
                rep = zmod.blot_all(a.root) if not a.ref else zmod.blot_one(a.ref, a.root)
                out(rep)
                return 0
            if a.assemble:
                rep = zmod.assemble(a.root)
                out(rep)
                return 1 if rep["missing_blot"] else 0
            if a.predict:
                model = a.model or zmod.DEFAULT_MODEL
                if a.ref:
                    # A single named ref runs even when the page is marked exempt.
                    # The sweep skips those — a plate has no right answer — but
                    # naming one page is itself the request.
                    net, sha = zmod.load_segmenter(model, a.root)
                    fn = zmod.predict_dp if a.decode == "dp" else zmod.predict
                    rep = fn(a.ref, a.root, net=net, sha=sha,
                             model_path=model, device=a.device)
                    out(rep)
                    return 0
                rep = zmod.predict_all(a.root, refs=itin, model_path=model,
                                       device=a.device, decode=a.decode)
                out(rep)
                # Same contract as `--assemble`'s missing_blot: a page the model was
                # asked about and could not be shown is a gap in the run, not a
                # quiet omission.
                return 1 if rep["skipped_no_blot"] else 0
            if a.score:
                # `--model` here measures a checkpoint *before* it is installed,
                # in memory, writing nothing — which is how a permuted model gets
                # caught without first overwriting the store with its output.
                rep = zmod.score(a.root, model_path=a.model, decode=a.decode,
                                 device=a.device)
                conf = rep.pop("confusion")
                out(rep)
                out(conf)
                # A consistent relabelling is a different fault from a weak model
                # and has a different remedy, so it does not get to hide in a table.
                p = rep["permutation"]
                if p["bijective"] and not p["is_identity"] and p["holds_out"] >= 90:
                    print(f"\nRELABELLING, not a weak model: a 1-1 map derived on "
                          f"the training pages predicts {p['holds_out']}% of the "
                          f"held-out zones. The geometry was learned; the names on "
                          f"the output channels are wrong.", file=sys.stderr)
                return 0
            if a.install:
                cfg = load_config(a.root)
                out(zmod.install_model(a.install, a.root, name=a.name, cfg=cfg,
                                       commit=a.commit, device=a.device))
                return 0
            if a.remap_model:
                rep = zmod.remap_model(a.root, a.model or zmod.DEFAULT_MODEL,
                                       commit=a.commit)
                ch = rep.pop("channels")
                out(rep)
                out(ch)
                return 0
            if a.delete:
                if not a.ref:
                    print("zones --delete needs a ref: it un-keys one page",
                          file=sys.stderr)
                    return 2
                out(zmod.delete_zones(a.ref, a.root, commit=a.commit))
                return 0
            if a.diff:
                cfg = load_config(a.root)
                scope = ([zmod.norm_ref(a.ref)] if a.ref else
                         sorted(set(zmod.zone_refs(a.root))
                                & set(zmod.zone_refs(a.root, zmod.MZDIR)),
                                key=zmod.parse_ref))
                rows = [r for ref_ in scope
                        for r in zmod.zone_diff(ref_, a.root, cfg)]
                from collections import Counter
                out({"pages": len(scope), "differences": len(rows),
                     "pages_differing": len({r["ref"] for r in rows}),
                     "by_kind": " ".join(f"{k}:{v}" for k, v in
                                         sorted(Counter(r["kind"]
                                                        for r in rows).items()))})
                if rows:
                    out(rows)
                return 0
            if a.paragraphs:
                cfg = load_config(a.root)
                scope = [zmod.norm_ref(a.ref)] if a.ref else itin
                summary_, rows = zmod.paragraph_audit(a.root, cfg, refs=scope)
                out(summary_)
                if rows:
                    out(rows)
                return 0
            if a.link:
                out(zmod.link_view(a.root))
                return 0
            store = {"gt": zmod.ZONEDIR, "mz": zmod.MZDIR}[a.store]
            cfg = load_config(a.root)
            if a.ref:
                rep = zmod.validate_page(a.ref, a.root, cfg, ink=True, store=store)
                out(rep)
                # The zones themselves, by default — reading a page's layout used to
                # mean opening the editor. `--lines` swaps in the line-by-line
                # breakdown, which matters only when something *inside* a zone is in
                # question and costs a second raster decode besides: `validate_page`
                # reads `scans/`, the line pass reads the figure-blotted copy.
                if a.lines:
                    rows_ = zmod.page_zone_lines(a.ref, a.root, cfg, store=store)
                else:
                    rows_ = zmod.page_zones_table(a.ref, a.root, store=store)
                if rows_:
                    out(rows_)
                # **Measurement never gates.** Nothing in `mz/` is ratified, and a
                # raw predicted polygon fails the fixed-measure width check by
                # construction — so a non-zero exit here would be permanent
                # known-false noise, and would also mean a machine store could
                # block a build that has nothing to do with it.
                return 1 if (rep["errors"] and store == zmod.ZONEDIR) else 0
            summary_, rows = zmod.validate_corpus(a.root, cfg, ink=a.ink, refs=itin,
                                                  store=store)
            out(summary_)
            if rows:
                out(rows)
            return 1 if (summary_["errors"] and store == zmod.ZONEDIR) else 0
        if a.cmd == "normalize":
            # Bare form and --check are the same thing: report only. --convert is
            # the only way to write, scoped or not — no more bare-form write, which
            # used to rewrite the whole corpus on a habit-driven omission of --check.
            if not a.convert:
                rep = scan(a.root, paths=a.path)
                out(rep)
                # NFD drift, an unlicensed mark, and §2.9 spacing drift all block:
                # each is an error with no reading to adjudicate. The lookalike
                # census does not — it is a to-key worklist needing a human ruling
                # on what the page prints, which is firewalled, same contract as
                # validate's WORKLIST.
                return 1 if (rep["nfd_offenders"] or rep["unlicensed_marks"]
                             or rep["spacing_offenders"]) else 0
            out(convert(a.root, dry_run=a.dry_run, paths=a.path))
            return 0
    except (ValueError, FileNotFoundError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
