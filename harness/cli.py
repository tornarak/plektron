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

Output is TOON (see emit.py). `--json` on any verb restores indented JSON for
anything that needs to parse it as a contract.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from .authorities import (load as load_authorities, parse_citation as authority_parse,
                          record as authority_record, search as authority_search, sigla)
from .context import build_context, all_refs
from .detectors import (digraph_frequency, mark_base_frequency, suffix_frequency,
                        suggest_lexicon, suggest_native_forms)
from .emit import emit, emit_lines
from .lines import (LINE_SHEET_H, ZOOM, ZOOM_CLIENT_W, ZOOM_OVERLAP, ZOOM_SHEET_H, alto_for_lines,
                    page_lines, parse_selection, write_line_crops,
                    write_line_sheets, write_line_zoom)
from .normalize import scan, convert
from .paths import clean, crops_dir, html_path, proposal_path, sheets_dir, zoom_dir
from .proposal_check import (check as check_proposal, fix as fix_proposal,
                             line_codepoints, replace_in_field,
                             set_field as set_proposal_field)
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
    zm.add_argument("--from", dest="alto_dir", default="end-of-eval",
                    help="ALTO providing the line geometry (default end-of-eval)")

    rv = add("review", help="span-level diff between a reading proposal and the "
                        "recognizer output, grouped by substitution class — the "
                        "queue for rebuilding ground truth")
    rv.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-074")
    rv.add_argument("--from", dest="alto_dir", default="end-of-eval",
                    help="recognizer ALTO directory (default end-of-eval)")
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
                        "recognizer geometry — --commit required to write")
    rs.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-074")
    rs.add_argument("--from", dest="alto_dir", default="end-of-eval",
                    help="ALTO providing the line geometry (default end-of-eval)")
    rs.add_argument("--force", action="store_true",
                    help="overwrite a target that already holds text — only 1-048 "
                         "and 2-030 do, and they are the surviving hand-keyed pages")
    rs.add_argument("--commit", action="store_true",
                    help="actually write gt/ocr/ — bare form only previews the "
                         "report (edits, geometry_drift, text_mismatch) and writes "
                         "nothing, same contract as normalize's --convert")

    cl = add("clean", help="remove review/PP-NNN/{crops,sheets,zoom} — the "
                        "regenerable working images — leaving proposal.json and "
                        "decision.json in place; run once a page is restored")
    cl.add_argument("ref", metavar="PP-NNN",
                    help="page ref: part and scan index, e.g. 1-053")

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
            elif a.native:
                out(suggest_native_forms(a.root))
            else:
                out(suggest_lexicon(a.root))
            return 0
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
            spans = page_spans(a.ref, a.alto_dir, a.root)
            n = len(page_lines(alto_for_lines(a.ref, a.alto_dir, a.root)))
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
