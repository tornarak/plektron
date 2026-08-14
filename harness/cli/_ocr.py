"""`harness ocr` — the ALTO stores, the line instruments, and the correction loop.

Reads resolve through `ocr/`, the read view over both OCR stores, which is this
group's unnamed default — it resolves per page to the human file where there is
one and the machine file otherwise, i.e. "whatever is current". `--store gt|mz`
names a real store instead, a closed set exactly as `zones check --store` is and
for its reason: a free path is how a check ends up compared against its own
input. **The view is not a value in that set.** It is not a store, and letting it
be named as one is the category error the three-store layout exists to prevent.

`review` is the only action with a store default (`mz`), because it is the only
one where the view is actively wrong: its bare diff needs an independent witness,
and the view resolves to the ground truth the proposal produced as soon as the
page has any.

Writes name `gt/ocr/` explicitly and `restore` is the only one, under `--commit`.
A line the segmenter dropped is given a box by a human in `edit`, into `gt/lines/`
— geometry only, and folded over whichever store answers for the page, so it is
reachable on the pages that have no ground truth at all.

The old `lines` verb carried six modes on one parser — a table, a gap detector,
a geometry writer, and three image writers — selected by if-chain precedence, so
`--gaps` silently voided `--crops` and `--margins` did nothing under either.
They are six actions now, and a flag that does not apply is a parse error rather
than a no-op.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import click

from ..calls import call_summary, log_call, read_calls
from ..context import all_refs, norm_ref
from ..lines import (
    DEFAULT_ALTO_DIR,
    LINE_SHEET_H,
    NUMBER_FONT,
    NUMBER_GUTTER,
    ZOOM,
    ZOOM_CLIENT_W,
    ZOOM_MAX,
    ZOOM_OVERLAP,
    ZOOM_SHEET_H,
    ZOOM_STEPS,
    alto_for_lines,
    line_gaps,
    page_lines,
    parse_selection,
    parse_spans,
    write_blot,
    write_line_crops,
    write_line_sheets,
    write_line_zoom,
    write_numbered_page,
)
from ..parallel import ptrack
from ..paths import (
    clean,
    crops_dir,
    decisions_path,
    ensure_page_link,
    html_path,
    numbered_path,
    sheets_dir,
    zoom_dir,
)
from ..recognize import DEFAULT_REC_MODEL, DEFAULT_SEG_MODEL
from ..render import progress
from ..review import (
    DEFAULT_BOX_LINES,
    DEFAULT_FONT,
    DEFAULT_FONT_SIZE,
    corrections,
    group_spans,
    page_context,
    page_spans,
    restore,
    summary,
)
from ._common import (
    action,
    add_jobs,
    arg,
    exclusive,
    group,
    one_page_only,
    opt,
    out,
    out_per_ref,
    page_refs,
    refs_arg,
)

# **A closed set of the two real stores, and the view is not a value in it** —
# `zones check --store` exactly, and for its reason: a free path is how a check ends
# up compared against its own input, and naming the view as if it were a store is
# the category error the three-store layout exists to prevent. Omitting the flag
# reads through the view, which resolves per page to gt-if-it-exists-else-mz; that
# is "whatever is current for this page", not a store, and it stays unnamed.
STORE_HELP = ("which store to read: 'gt' is what a human has been through, 'mz' "
              "what the recognizer read. Omit to read through the ocr/ view, which "
              "resolves per page to the human file where there is one")
STORES = {"gt": "gt/ocr", "mz": "mz/ocr"}
OUT_HELP =("write the images somewhere other than the page's own review/PP-NNN/ "
            "subdirectory — for a one-off comparison, not for the pass, whose "
            "files the other actions expect to find in the default place")


def _store(p, default=None):
    """`--store gt|mz`, resolved to a directory on the namespace as `alto_dir`.

    `default` is the store a bare invocation reads; `None` means the view. Only
    `review` sets one, because only there is the view actively wrong — see its
    registration.
    """
    opt(p, "--store", type=click.Choice(("gt", "mz")), default=default,
                   help=STORE_HELP + (f" [default: {default}]" if default else ""))
    return p


def _alto_dir(a) -> str:
    return STORES.get(getattr(a, "store", None), DEFAULT_ALTO_DIR)


CANON_REF = re.compile(r"^(?:chukchi-)?[1-3]-\d{3}$")


def ref_and_spec(a) -> tuple[list[str], str | None]:
    """Split `PP-NNN 11@70 13@40` into one ref and its line selection.

    **The selection is the argument, not a flag on one.** It was `--only`, which
    is the wrong shape twice: it reads as a filter over a default of "the whole
    page", when the whole page is the thing nobody wants and the selection is the
    entire point of the verb; and a flag invites the plural positional beside it,
    where the same line numbers name unrelated lines on the next page. One ref,
    then the places on it.

    Tokens are joined with commas, so `11@70 13@40` and `11@70,13@40` are one
    request spelled two ways — a shell splits on spaces and a reader should not
    have to care which it typed.

    A trailing token spelled like a canonical ref is refused rather than read as a
    line range, because `ocr zoom 1-045 1-046` would otherwise silently render
    lines 1 through 46 of the first page: a plausible typo with no error and a
    wrong picture. `11-14` is untouched — no page is part 11, and a three-digit
    tail is what a real ref has.
    """
    given = list(getattr(a, "ref", None) or [])
    if len(given) > 1:
        for tok in given[1:]:
            if CANON_REF.match(tok):
                raise ValueError(
                    f"{tok!r}: one ref at a time here, then the lines on it — "
                    "a line selection follows the page it belongs to, since the "
                    "same indices name different lines on another page")
    a.ref = given[:1]
    spec = ",".join(given[1:]) or None
    return page_refs(a), spec


def register(cli):
    g = group(cli, "ocr", "the ALTO stores and the correction loop — "
              "line records, the dropped-line detector, crops and "
              "contact sheets, the browser review, and the write back "
              "into gt/ocr/",
              sections=("Reading a page", "The correction loop", "Recognition"), section="The passes")
    add = lambda name, **kw: action(g, name, globals()[f"run_{name.replace('-','_')}"], **kw)

    p = _store(add("pages", help="every ref with OCR present, i.e. workable now. "
              "Through the view by default, so a machine-read page counts — that "
              "is what makes it workable. Narrow it with --store"))
    opt(p, "--show-store", is_flag=True,
                   help="a row per ref instead of a bare list: which real stores "
                        "hold the page, and which one the ocr/ view actually "
                        "reaches. `view` is read off the farm rather than derived, "
                        "so a page restored since the last `ocr link` shows up as "
                        "still pointing at mz")

    p = _store(refs_arg(add("lines", help="per-line records for a page — line id, "
              "geometry and text, in reading order with empties kept. `index` is "
              "an identity, not a position: it stays what ALTO document order "
              "assigned, so labels are not consecutive in a banded listing"),
              all_="every page the store read holds"))
    opt(p, "--full", is_flag=True,
                   help="include baseline and polygon points, which are long "
                        "enough to make the table unreadable by default")

    _store(refs_arg(add("text", help="the page as plain text, one keyed line per "
           "line, in reading order with the empties dropped. The dump `ocr lines` "
           "was being run through jq for: the same reading, with the geometry and "
           "the identities taken off"),
           all_="every page the store read holds",
           extra=", and several print under a `# PP-NNN` heading each"))

    # **The pattern is declared before the refs, and has to be.** `ref` is the
    # variadic, and click hands a variadic everything it can reach — a required
    # positional sitting after one is a parse nobody can predict.
    p = add("grep", help="lines matching a regular expression, across whichever "
            "pages are named — the corpus text search `ocr lines --all | rg` was "
            "standing in for. The pattern is normalized to NFD before it "
            "compiles, so a composed character pasted from anywhere matches the "
            "decomposed text the store holds. **`grep` over the store's files "
            "is not this and will lie to you**: ALTO holds one word per "
            "`<String CONTENT=…>`, so a form the page prints sits in the file "
            "as several attributes with markup between them, and a literal "
            "search for it returns a clean zero that reads as *the corpus does "
            "not print this*. This assembles the line before matching")
    arg(p, "pattern", metavar="PATTERN")
    _store(refs_arg(p, all_="every page the store read holds"))
    opt(p, "-i", "--ignore-case", is_flag=True,
        help="fold case. Not the default: this corpus sets Tier-1 forms with "
             "case that carries information, and a native form is more often "
             "sought exactly than approximately")
    opt(p, "--context", type=int, default=0, metavar="N",
        help="lines of surrounding text per hit, on `lexicon lookup --context`'s "
             "reasoning — a form alone is a string, a form in its line is a "
             "sense. Context rows carry hit=false [0]")

    p = _store(refs_arg(add("gaps", help="bands of ink on the raster that no TextLine "
              "covers — the dropped-line detector. The segmentation this corpus "
              "was built from drops whole printed lines and nothing else "
              "notices, because the text that IS there is correct. Measured off "
              "the page, so the geometry a repair needs comes with the report. "
              "Expect running heads and folios among the hits: a band is a place "
              "to look, not a verdict"),
              all_="every page the store read holds — the corpus dropped-line "
                   "sweep, at a raster read per page"))
    add_jobs(p)

    p = _store(add("edit", pageable=False,
               help="the line-correction editor in the browser: adopt a band "
                    "`gaps` found as a line, or rule it not type. The human end "
                    "of that detector, and `zones edit`'s sibling one stage "
                    "down. It draws and never keys — a recovered line's text is "
                    "adjudicated in `ocr review` and written by `restore`, like "
                    "any other line's"))
    refs_arg(p, all_="every page the store read holds — the editor walks them "
                     "with the arrow keys. Not every scan: this corrects lines a "
                     "segmentation missed, so a page with no ALTO has nothing to "
                     "be missing from",
             extra=", and several are the walk: the session opens at the first "
                   "and steps through the list with the arrow keys, `l` showing "
                   "it as a table. One ref is a page to start at, not the only "
                   "page reachable. `--all` walks the store, `--unsettled` "
                   "narrows that to the pages still carrying a band")
    opt(p, "--unsettled", is_flag=True,
                   help="narrow --all to the pages still carrying a band nobody "
                        "has settled. Measured now, not read from a saved list: a "
                        "work-list goes stale the moment a page is worked, and a "
                        "stale one is a claim about the corpus that nothing "
                        "checks. Costs a raster read per page")
    opt(p, "--port", type=int, default=8733, help="port for the editor")
    add_jobs(p)

    # **No `--all` on the image writers, and the absence is deliberate.** Crops and
    # sheets are expensive in time and disk and are called per page by a reading
    # pass that is working on that page; a corpus form would be a lot of bytes
    # nobody asked for. `--out` is why they still need `one_page_only`: with a
    # second ref and one destination, the second page silently overwrote the first.
    p = _store(refs_arg(add("crops", help="one PNG per line, into review/PP-NNN/crops/")))
    opt(p, "--out", type=click.Path(path_type=Path), default=None, help=OUT_HELP)

    p = refs_arg(add("queue", help="validate a batch of pages and write it to the "
              "claim queue, then print the ONE prompt every reader of the batch "
              "gets. The prompt names no page — each reader takes its own ref with "
              "`ocr claim`, so the prompts are identical and the readers can share "
              "a cached context. Refuses a page that is not a restoration candidate "
              "— no zones, no prediction, or ground truth already present, which "
              "would collapse the two witnesses into one"))
    opt(p, "--note", default=None,
                   help="a sentence appended to the branch paragraph of every page "
                        "block in this batch, e.g. \"19 lines over 5 zones suggests "
                        "a sparse page, so the gap check matters more than usual "
                        "here\". Per-page notes want separate queue calls")

    add("claim", help="take the next unclaimed ref off the queue and print that "
        "page's block — the ref, and what the four-store survey found. Takes no "
        "ref: that is the point, the page arriving from a tool call rather than "
        "from a prompt that would then differ between siblings. Exit 1 when the "
        "queue is empty")

    p = refs_arg(add("reconcile", help="what the batch came back with — each named "
              "ref keyed, claimed with no proposal, or never claimed at all. Exit "
              "1 naming any that produced nothing: a page dealt twice or not at "
              "all is a valid ref and fails silently everywhere else"))

    p = _store(refs_arg(add("numbered", help="the whole page with each line's index "
              "drawn in a left gutter, into review/PP-NNN/numbered.png — the "
              "reading pass's first image, and its only one on a page that raises "
              "no doubt. A third of what the page's contact sheets cost to read")))
    opt(p, "--gutter", type=int, default=NUMBER_GUTTER,
                   help=f"px added left of the page for the labels (default "
                        f"{NUMBER_GUTTER}) — added, not overlaid, so a label never "
                        "covers the marginal material a crop's padding recovers")
    opt(p, "--font", "font_size", type=int, default=NUMBER_FONT,
                   help=f"label px in the written image (default {NUMBER_FONT}); a "
                        "full page is delivered at roughly 0.64x whatever is sent, "
                        "so this is about 1.5x the size you want to read")
    opt(p, "--out", type=click.Path(path_type=Path), default=None,
                   help="output file (default review/PP-NNN/numbered.png)")

    # A contact sheet shows whole lines, so it has nowhere to honour `@LO-HI`.
    # Refused rather than ignored: a caller who asked for a quarter of a line and
    # silently got all of it has been handed a different picture than the one their
    # report will describe.
    p = _store(refs_arg(add("sheets", help="compose the line crops into labelled "
              "contact sheets in review/PP-NNN/sheets/, index drawn in the "
              "margin, nothing downscaled — the reading pass's instrument; emits "
              "the sheet/lines map instead of the line table"),
              extra=", followed by the line indices to sheet — "
                    "`ocr sheets 1-048 7,20,22-26` or `ocr sheets 1-048 7 20 22-26`, "
                    "and the whole page if you name none. The rung above "
                    "`numbered`: sheet the lines that image left in doubt, with "
                    "their neighbours"))
    opt(p, "--per-sheet", type=int, default=40,
                   help="lines per contact sheet, upper bound only — --height "
                        "packs by height first (default 40)")
    opt(p, "--height", "sheet_h", type=int, default=LINE_SHEET_H,
                   help=f"max contact-sheet height in px (default {LINE_SHEET_H}); "
                        "fewer, fuller sheets for the same lines")
    opt(p, "--out", type=click.Path(path_type=Path), default=None, help=OUT_HELP)

    refs_arg(add("calls", help="every image this page's reading has opened, in "
             "order, with each zoom's stated reason — written by the tools, not "
             "recalled at the end. Paste it into your report rather than "
             "summarizing it: a tally reconstructed once the answer is known "
             "comes out flattering, and every report in the batch that prompted "
             "this understated its own by two to five times"),
             all_="every page that has a ledger — what the pass has spent, "
                  "page by page, which is the only view that shows one reader "
                  "as an outlier rather than as a number")

    p = _store(refs_arg(add("zoom", help="magnify selected places — overlapping strips "
              "at an integer scale, packed into as few sheets as the height "
              "budget allows, for the second look a contact sheet leaves open"),
              extra=", followed by the places to magnify: `ocr zoom 1-048 11@70 "
                    "13@40 23@60` is three crops, one call, one sheet. `N@P` "
                    "centres a crop at a percentage of that line's width, `N@LO-HI` "
                    "takes a range, and a bare `N` takes the whole line. The edges "
                    "are pinned, so `@0` is the head of the line and `@100` its "
                    "tail whatever its length — `@100` is where a footnote "
                    "reference sits, `@0` where its opener sits, and neither asks "
                    "you to estimate. One line may be named at several places "
                    "(`1@0 1@100`) and renders one crop each"))
    opt(p, "--zoom", type=click.Choice(ZOOM_STEPS), default=ZOOM,
                   help=f"display px per source px, as delivered — {ZOOM} or "
                        f"{ZOOM_MAX}, nothing between (default {ZOOM}). 2 is the "
                        "second look at a line a contact sheet left open; 4 is "
                        "for one mark on one word and warns when used, because "
                        "at 300 dpi a character is ~30 px and every ink pixel is "
                        "already a 4x4 block — past it a magnifier returns the "
                        "resampler, not the page. 3 was legal and became the "
                        "default hesitation; 1 is what a contact sheet already is")
    opt(p, "--reason", required=True,
                   help="why this crop, in a few words — recorded in the call and "
                        "so visible to `agents transcripts`. Required because a "
                        "zoom nobody has to justify is one nobody counts: the "
                        "pages that failed did so at 59 and 81 crops apiece, each "
                        "individually plausible. Naming the question before the "
                        "call is also what distinguishes re-aiming a miss from "
                        "asking the same thing louder")
    opt(p, "--window", type=int, default=None,
                   help="source px per strip; derived from --zoom so that the "
                        "delivered scale really is --zoom. Overriding it upward "
                        "makes the sheet exceed the client width, and the scale "
                        "is then whatever the client's fitting leaves")
    opt(p, "--client-w", type=int, default=ZOOM_CLIENT_W,
                   help=f"px the reading client shows per image (default "
                        f"{ZOOM_CLIENT_W}); every sheet is padded to exactly "
                        "this, so the scale does not vary with how long the "
                        "lines are")
    opt(p, "--overlap", type=int, default=ZOOM_OVERLAP,
                   help=f"px shared by consecutive strips (default "
                        f"{ZOOM_OVERLAP}), so no glyph is only ever seen cut")
    opt(p, "--height", "sheet_h", type=int, default=ZOOM_SHEET_H,
                   help=f"max sheet height in px (default {ZOOM_SHEET_H}) — a "
                        "taller sheet gets fitted to the display, undoing the zoom")
    opt(p, "--smooth", is_flag=True,
                   help="Lanczos instead of nearest-neighbour: better for "
                        "comparing letterforms, worse for deciding whether a "
                        "faint mark is present, since it invents greys")
    opt(p, "--out", type=click.Path(path_type=Path), default=None,
                   help="output directory (default review/PP-NNN/zoom)")

    p = _store(refs_arg(add("blot", help="write the page to scans/w-blotted/ with every "
              "line box and figure zone painted out, so whatever remains is "
              "uncovered by construction. The visual counterpart to `gaps`, and "
              "a check on it: nothing is thresholded here, only covered. Not to "
              "be confused with `zones blot`, which paints figures white for the "
              "segmenter to train on"),
              all_="every page the store read holds"))
    opt(p, "--force", is_flag=True,
                   help="repaint pages whose blot is already newer than their "
                        "ALTO. Only --all skips those; naming a page means it")
    opt(p, "--out", type=click.Path(path_type=Path), default=None,
                   help="output directory (default scans/w-blotted/ — a "
                        "corpus-level destination, unlike the other image "
                        "actions, because the blotted page is not review material)")
    opt(p, "--exemptions/--no-exemptions", default=True,
                   help="paint the bands a human ruled as well as the lines and "
                        "figures, both layers, so a finished page blots to a "
                        "near-blank leaf — the standard the recognition stage "
                        "exists to reach. --no-exemptions keeps the bare page, "
                        "which answers independently of anybody's judgement")
    add_jobs(p)

    # **The one action with a store default, and `mz` is it.** The bare diff needs
    # an *independent* witness; the view stops being one the moment the page has
    # ground truth, because it then resolves to the very file the proposal
    # produced. The runtime refusal below still catches that, but a default nobody
    # has to think about beats an error after the fact — and `mz/ocr/` is a
    # different inode by construction.
    # **The first action to take more than one ref**, for a reason the rest of the
    # group has since caught up with: standing a server up per page made the
    # reviewer wait on the tooling between pages, which got worse the moment the
    # reading half started fanning out to an agent per page.
    p = _store(add("review", pageable=False,
               constraints=(exclusive("serve", "html", "spans"),),
               help="adjudicate reading proposals in the browser "
              "(--serve), one or more pages in one session; bare, a span-level "
              "diff of each proposal against a second witness, grouped by "
              "substitution class"), default="mz")
    refs_arg(p, all_="every page holding a proposal and no decision — the "
                     "pending-adjudication queue",
             extra=": --serve walks them in the order named, one page on screen "
                   "at a time")
    opt(p, "--serve", is_flag=True,
                    help="serve the review page on 127.0.0.1 and accept saves "
                         "into review/PP-NNN/decision.json")
    opt(p, "--html", is_flag=True,
                    help="write the browser review page to "
                         "review/PP-NNN/review.html instead of emitting a table. "
                         "No destination knob: the page embeds its crops as data "
                         "URIs, so where it sits is nobody's business but the "
                         "pass's, and --serve is the usual route")
    opt(p, "--spans", is_flag=True,
                    help="with the bare span diff: every span individually, not "
                         "grouped by class")
    opt(p, "--port", type=int, default=8731, help="port for --serve")
    # **Type, for the two rendered modes.** A review is an hour of comparing a crop
    # against an entry box, so the face those are set in is an ergonomic
    # parameter and not decoration: the book is a Brill, and matching the entry to
    # the printed face makes the comparison one design in two renderings rather
    # than two designs. These decide where the page *starts* — the page carries
    # live steppers for the size and the box, remembered per browser, because the
    # right size for a face is something you find by looking at it beside a crop.
    opt(p, "--font", default=None, metavar="NAME",
        help=f"font family for the entry boxes, prepended to the standing "
             f"fallbacks so an uninstalled name still renders [{DEFAULT_FONT}]")
    opt(p, "--font-size", type=int, default=None, metavar="PX",
        help=f"entry text size [{DEFAULT_FONT_SIZE}]")
    opt(p, "--box-lines", type=int, default=None, metavar="N",
        help=f"lines an entry box holds before it grows — a floor, not a cap "
             f"[{DEFAULT_BOX_LINES}]")
    # **Not paged**, for `zones edit`'s reason: `--serve` prints a URL and blocks
    # in `serve_forever`. It covers the other two modes too, and that is the right
    # trade — one flag deciding whether an action pages is legible, where a rule
    # that paged some invocations of a verb and not others is not.

    p = _store(refs_arg(add("restore", help="preview (default) or write adjudicated "
              "review decisions into gt/ocr/ as ground truth, keeping the source "
              "geometry — --commit required to write. Reports mode=restoration "
              "(filled from another store) or mode=revision (the finished page "
              "re-edited in place)"),
              all_="every page holding an adjudicated decision.json, skipping "
                   "those whose ground truth is already newer than it"))
    opt(p, "--force", is_flag=True,
                   help="overwrite a target that already holds text. Every page "
                        "in gt/ocr/ does now that the rebuild is complete, so "
                        "this is how a revision says it meant it — required for "
                        "one. Under --all it carries the same intent one step "
                        "further and ignores the mtime skip as well")
    opt(p, "--commit", is_flag=True,
                   help="actually write gt/ocr/ — bare form only previews the "
                        "report (edits, geometry_drift, text_mismatch)")

    p = add("corrections", help="what readers actually get wrong: the "
            "character-level proposal->decision corrections, aggregated across "
            "every adjudicated page. The pass's own error profile, which nothing "
            "recorded — restore computes this diff per page and discards it. "
            "An aggregate: refs scope it, they do not multiply it. Always exits 0")
    refs_arg(p, all_="every review/ page holding both files")
    opt(p, "--since", metavar="DATE", default=None,
                   help="only pages whose decision.json saved_at sorts at or "
                        "after this (e.g. 2026-07-31). The store spans this "
                        "project's own history and its oldest error classes are "
                        "ones later rules made impossible, so an unscoped run is "
                        "partly archaeology; a page with no saved_at is excluded "
                        "and named in skipped_unstamped rather than dropped")
    opt(p, "--min", type=int, default=1, metavar="N",
                   help="drop changes seen fewer than N times [1]")

    # No `--commit`, `--all` included: it removes only derived, regenerable output,
    # which is the same reason `crops` writes without one. The verb that deletes an
    # authored file is `zones delete`, and that one has no `--all` at all.
    p = refs_arg(add("clean", help="remove a page's derived working files (crops, "
             "sheets, zoom, review.html) — leaving proposal.json and "
             "decision.json in place; run once a page is restored"),
             all_="every review/ page")

    p = add("predict", help="zones to text in one pass — baseline segmentation "
            "and recognition over scans/, structured by the zones/ view, written "
            "to mz/ocr/ and linked into ocr/. Never gt/ocr/. --all sweeps every "
            "page with zones and resumes where it stopped")
    refs_arg(p, all_="every page with zones",
             extra=", and several go through one process — both models load once, "
                   "which is most of the cost")
    opt(p, "--force", is_flag=True,
                   help="re-run over pages already in mz/ocr/ — the file records "
                        "both models' sha256, which is the store's only witness "
                        "to what produced it, so a rerun replaces that record")
    opt(p, "--itinerary", metavar="LST",
                   help="recognize over a work-list rather than the whole store")
    opt(p, "--seg-model", default=DEFAULT_SEG_MODEL,
                   help=f"the baseline segmentation model [{DEFAULT_SEG_MODEL}]")
    opt(p, "--rec-model", default=DEFAULT_REC_MODEL,
                   help=f"the recognition model [{DEFAULT_REC_MODEL}]. Stock "
                        "CATMuS reads ~91%% of the ASCII and 0%% of the "
                        "transcription inventory — a witness to geometry and to "
                        "English, and to nothing else")
    opt(p, "--device", default="auto", help="torch device [auto]")
    # **Processes here, where the other `--jobs` are threads**, because this is the
    # one sweep whose cost is CPU-side vectorization inside kraken rather than a
    # raster decode. The default is capped by free VRAM as well as by cores, since
    # each worker holds ~1.4 GB of CUDA context.
    add_jobs(p)

    p = add("link", help="rebuild ocr/, the read view over gt/ocr/ and mz/ocr/, "
            "the human file winning wherever it exists. Derived: the links are "
            "relative and a stale one is removed rather than left to dangle")


def run_pages(a) -> int:
    refs = all_refs(a.root, _alto_dir(a))
    if a.show_store:
        from ..recognize import presence
        out(a, presence(refs, a.root))
        return 0
    out(a, refs)
    return 0


def _store_refs(a) -> list[str]:
    """The pages this invocation works on: the ones named, or the store's own.

    `--all` here reads through whatever `--store` resolved to, which is the view
    unless one was named — the `ocr pages` rule, that a machine-read page is
    workable and that is what these verbs report. Neither of them gates and
    neither publishes a rate, so the "name the store, not the view" rule does not
    reach them; `--store` narrows either.
    """
    return page_refs(a) or all_refs(a.root, _alto_dir(a))


def run_lines(a) -> int:
    from ..lines import annexed_bands
    pairs = []
    for r in _store_refs(a):
        recs = page_lines(alto_for_lines(r, _alto_dir(a), a.root), a.root, ref=r)
        # **A line whose box a human has said is short of its ink says so here.**
        # The ruling lives on the band and is read off `ocr gaps`; a reader keys
        # from this table, and without the marker the one view that matters is the
        # one that stays silent. `annexed` is the count of ruled bands naming this
        # index, so a non-zero value means: the printed line is wider than its box,
        # and every crop's padding already carries the rest of it.
        annexed = annexed_bands(r, a.root)
        for rec in recs:
            rec["annexed"] = len(annexed.get(int(rec["index"]), []))
        if not a.full:
            # Drop the two long geometry strings. Dropped from every record, never
            # some — a ragged key set collapses the table to the verbose nested
            # form (see emit.py).
            drop = ("baseline", "points")
            recs = [{k: v for k, v in rec.items() if k not in drop} for rec in recs]
        pairs.append((r, recs))
    out_per_ref(a, pairs)
    return 0


def _keyed_lines(a, ref: str) -> list[dict]:
    """One page's non-empty lines, in reading order.

    The empties are dropped here and kept by `ocr lines`, and the split is by
    what the two are for: an empty record is a *box* with nothing keyed in it,
    which is a fact about the segmentation and belongs in the table a corrector
    reads. In a text dump it is a blank line carrying no information, and in a
    search it is a line that can never match.
    """
    recs = page_lines(alto_for_lines(ref, _alto_dir(a), a.root), a.root, ref=ref)
    return [rec for rec in recs if (rec.get("text") or "").strip()]


def run_text(a) -> int:
    from ..emit import emit_lines

    refs = _store_refs(a)
    pages = [(r, [rec["text"] for rec in _keyed_lines(a, r)]) for r in refs]
    if getattr(a, "json", False):
        out(a, [{"ref": r, "lines": lines} for r, lines in pages])
        return 0
    # Plain lines, not a table, on `tei ledger --untranscribed`'s precedent: the
    # payload is a pipe target and structure is in the way of it. The heading is
    # printed only for several pages, so the one-page form — which is the form
    # anything downstream is likeliest to be reading — is the page and nothing
    # else.
    for r, lines in pages:
        if len(pages) > 1:
            print(f"# {r}")
        print(emit_lines(lines))
    return 0


def run_grep(a) -> int:
    import unicodedata

    # NFD, because the store is NFD corpus-wide and a pattern typed or pasted
    # anywhere else may not be: a composed `č` would match nothing and report a
    # clean corpus-wide negative, which is the worst answer this verb could give.
    # Never NFKC — it destroys two inventory glyphs (see CLAUDE.md, "Encoding").
    pattern = unicodedata.normalize("NFD", a.pattern)
    try:
        rx = re.compile(pattern, re.IGNORECASE if a.ignore_case else 0)
    except re.error as e:
        raise ValueError(f"{a.pattern!r}: not a regular expression — {e}") from None
    if a.context < 0:
        raise ValueError("--context: a count of lines, so not negative")

    refs = _store_refs(a)
    rows: dict[tuple[str, int], dict] = {}
    hits = read = 0
    for r in refs:
        recs = _keyed_lines(a, r)
        read += len(recs)
        for i, rec in enumerate(recs):
            if not rx.search(rec["text"]):
                continue
            hits += 1
            lo = max(0, i - a.context)
            for j in range(lo, min(len(recs), i + a.context + 1)):
                # Keyed by identity, so two hits whose context windows overlap
                # yield one row each and not one per window — and a line that is
                # both a hit and another hit's context stays a hit.
                key = (r, int(recs[j]["index"]))
                if j == i or key not in rows:
                    rows[key] = {"ref": r, "index": recs[j]["index"],
                                 "zone": recs[j]["zone"], "hit": j == i,
                                 "text": recs[j]["text"]}
    # **The scope row prints on every run, empty result or not.** A search that
    # found nothing has two readings — the corpus does not say this, or the
    # pages searched do not hold it — and only `pages`/`store` separate them.
    # Unkeyed pages are not searched and cannot be: `--store gt` over the corpus
    # is a search of the pages a human has been through, not of the book.
    out(a, [{"pattern": a.pattern, "store": a.store or "view", "pages": len(refs),
             "lines": read, "hits": hits}], name="scope", heading=True)
    out(a, list(rows.values()), name="matches", heading=True)
    return 0


def run_gaps(a) -> int:
    from ..corrections import load_lines
    from ..parallel import pmap
    refs = _store_refs(a)
    with progress("measuring ink") as tick:
        done = pmap(lambda r: line_gaps(r, _alto_dir(a), a.root), refs, a.jobs,
                    tick)
    out_per_ref(a, list(zip(refs, done, strict=True)))
    # **A page that has been worked reports differently from one nobody has
    # opened, and without this it does not.** A corrected band stops being a band:
    # the box covers the ink, so it drops out of the table and the page falls
    # silent. Silence is exactly what this detector exists to break, so say how
    # many of them were settled rather than absent.
    #
    # **And it says where the line is, because a count sends the reader hunting.**
    # This reported `corrections: 1` and nothing else, which names no position, no
    # size and no zone — so `1-039`'s reader, told only that a correction existed,
    # spent half its zooms groping across the page for it and read the renderer's
    # own index label as printed ink on the way. The geometry is already in the
    # store and the zone is one lookup away; withholding both made the reader
    # rediscover by image what the file already knew.
    from ..lines import _band_zone
    from ..zones import read_zones
    rows = []
    for r in refs:
        zs = read_zones(r, a.root)
        for c in load_lines(r, a.root):
            box = {"hpos": c["x0"], "vpos": c["y0"],
                   "width": c["x1"] - c["x0"], "height": c["y1"] - c["y0"]}
            rows.append({"ref": r, "zone": _band_zone(box, zs) or "-",
                         "vpos": box["vpos"], "hpos": box["hpos"],
                         "width": box["width"], "height": box["height"],
                         "keyed": c["text"] or ""})
    if rows:
        out(a, {"pages_corrected": len({x["ref"] for x in rows}),
                "corrections": len(rows), "corrected": rows}, "pages_corrected")
    # **A `covered` ruling is the one kind this check can falsify**, so it does.
    # It names a line index, and the store either has that line keying something
    # or it does not — where "not type" rests on the paper alone and nothing here
    # can weigh it. Reported, never gated: `gaps` is measurement, and
    # `measurement never gates` (VERBS.md, Conventions).
    from ..lines import covered_faults
    faults = [f for r in refs for f in covered_faults(r, _alto_dir(a), a.root)]
    if faults:
        out(a, {"covered_faults": faults}, "covered_faults")
    return 0


def _review_html(ctx: dict) -> str:
    """The standalone review page, rendered from the same template the server
    uses. One renderer, so the `--html` file and the served page cannot drift —
    which was the whole argument for the queue being a frame around the page
    rather than a mode inside it."""
    from ..web import STATIC, templates

    return templates.get_template("review/page.html").render(
        **ctx, base="", static="", request=None, inline={
            "css": (STATIC / "css" / "review.css").read_text(encoding="utf-8"),
            "js": (STATIC / "js" / "review.js").read_text(encoding="utf-8"),
        })


def _page_link(a, ref: str | None = None) -> None:
    """The page's own raster, linked into its working directory the first time an
    action materializes that directory. Convenience only — `ocr clean` leaves it,
    and it is keyed to the ref rather than to `--out`, which exists precisely to
    write somewhere that is not the page's directory.

    `ref` is passed explicitly by the actions that take more than one: `a.ref` is a
    list there, and linking against it would name a directory after the whole
    session."""
    if not getattr(a, "out", None):
        ensure_page_link(ref or a.ref, a.root)


def run_calls(a) -> int:
    """The ledger, and the counts that make a raw crop total mean something.

    Reports; never gates. What it is for is the adjudicator's first question —
    was this page read or was it searched — and `repeats` answers it where a bare
    count cannot: seven crops over seven lines is a careful page, seven over two
    is a reader that could not frame what it wanted.
    """
    from ..calls import calls_path
    from ..paths import page_dirs
    refs = page_refs(a) or [d.name for d in page_dirs(a.root)
                            if calls_path(d.name, a.root).exists()]
    out(a, [call_summary(r, a.root) for r in refs])
    # The series only under named refs. A corpus sweep wants the per-page counts —
    # which reader is an outlier — and pooling every call of every page into one
    # table buries exactly that in a few thousand rows.
    if not page_refs(a):
        return 0
    rows = [{"ref": norm_ref(r), **c} for r in refs for c in read_calls(r, a.root)]
    if rows:
        out(a, {"log": rows}, "log")
    return 0


def run_crops(a) -> int:
    refs = page_refs(a)
    one_page_only(a, {"out": "--out"}, refs)
    pairs = []
    with progress("cropping") as tick:
        for r in ptrack(refs, tick):
            _page_link(a, r)
            pairs.append((r, write_line_crops(
                r, a.out or crops_dir(r, a.root), _alto_dir(a), a.root)))
            log_call(r, "crops", a.root, images=len(pairs[-1][1]))
    out_per_ref(a, pairs)
    return 0


def run_queue(a) -> int:
    """Write the batch, print the one prompt, or refuse naming the fix.

    The prompt goes to stdout as plain text rather than through a table: it is
    prose meant to be handed to an agent whole, and a renderer that wrapped or
    truncated it would corrupt the one artifact this action exists to produce.
    Everything operational goes to stderr, so `queue … | pbcopy` carries the
    prompt and nothing else.
    """
    from ..dispatch import Unready, queue_refs
    try:
        rec = queue_refs(page_refs(a), a.root, note=a.note)
    except Unready as e:
        raise click.ClickException(str(e)) from None
    if getattr(a, "json", False):
        out(a, [rec])
        return 0
    click.echo(rec["prompt"])
    n = len(rec["queued"])
    if rec["resynced"]:
        click.echo(
            f"\nthe reader's transcluded contract was out of date and has been "
            f"rewritten from {', '.join(rec['resynced'])}. The agent file is "
            "tracked: commit it, or the next clone dispatches readers against "
            "the old text.", err=True)
    click.echo(
        f"\nqueued {n}: {', '.join(rec['queued'])}. Send the prompt above to "
        f"{n} readers, UNEDITED and IDENTICAL — it names no page, and identity "
        "is what lets them share a cached context. Each takes its own ref off "
        "the queue. Stagger the first launch about ten seconds so it writes the "
        "context the rest read; `ocr reconcile` checks what came back.", err=True)
    return 0


def run_claim(a) -> int:
    """One ref off the queue, rendered. Exit 1 when there is nothing left.

    Exit 1 rather than an empty success: a reader that gets a blank answer at
    exit 0 has been told nothing, and the failure it must not commit — picking a
    page for itself — is exactly what a silence invites.
    """
    from ..dispatch import claim
    rec = claim(a.root)
    if rec is None:
        click.echo(
            "nothing left to claim — the queue is empty or every ref on it is "
            "taken. Stop and say so; do not pick a page yourself.", err=True)
        return 1
    if getattr(a, "json", False):
        out(a, [rec])
    else:
        click.echo(rec["page_block"])
    return 0


def run_reconcile(a) -> int:
    from ..dispatch import reconcile
    rows = reconcile(page_refs(a), a.root)
    out(a, rows, name="refs")
    missing = [r for r in rows if r["state"] != "keyed"]
    if not missing:
        return 0
    held = [r["ref"] for r in missing if r["state"].startswith("CLAIMED")]
    click.echo(
        f"{len(missing)} of {len(rows)} produced no proposal: "
        f"{', '.join(r['ref'] for r in missing)}. "
        + (f"{len(held)} still held by a reader that took the page and did not "
           f"come back ({', '.join(held)}) — check it is not simply still "
           "running, then decide whether to re-queue."
           if held else
           "None of them was claimed, so no reader ever took them: the queue "
           "outran the readers, or they were never sent."), err=True)
    return 1


def run_numbered(a) -> int:
    refs = page_refs(a)
    one_page_only(a, {"out": "--out"}, refs)
    rows = []
    with progress("numbering") as tick:
        for r in ptrack(refs, tick):
            _page_link(a, r)
            rows.append(write_numbered_page(
                r, a.out or numbered_path(r, a.root), _alto_dir(a), a.root,
                gutter=a.gutter, font_size=a.font_size))
            log_call(r, "numbered", a.root, images=1)
    out(a, rows)
    return 0


def run_sheets(a) -> int:
    refs, spec = ref_and_spec(a)
    one_page_only(a, {"out": "--out"}, refs)
    if spec and "@" in spec:
        raise click.UsageError(
            "ocr sheets shows whole lines and cannot honour a @ place; "
            "drop it here, or use `ocr zoom`, which can.")
    pairs = []
    with progress("building sheets") as tick:
        for r in ptrack(refs, tick):
            _page_link(a, r)
            pairs.append((r, write_line_sheets(
                r, a.out or sheets_dir(r, a.root), _alto_dir(a), a.root,
                per_sheet=a.per_sheet, sheet_h=a.sheet_h,
                only=parse_selection(spec) if spec else None)))
            log_call(r, "sheets", a.root, only=spec or "all",
                     images=len(pairs[-1][1]))
    out_per_ref(a, pairs)
    return 0


def apparatus_hits(recs, asked) -> list[int]:
    """Which of the asked-for line indices sit in an apparatus zone, in order.

    Split from the refusal so the decision is testable without a store: what
    counts as apparatus is a question about `FOLIO_ZONES` and a page's own zone
    labels, and neither needs a raster to answer.

    A line whose index the page does not carry is **not** a hit. Asking for a
    line that does not exist is a different error with a different message, and
    swallowing it here would answer the wrong question.
    """
    from ..context import FOLIO_ZONES
    zoned = {int(r["index"]): r.get("zone")
             for r in recs if r.get("index") is not None}
    return [i for i in sorted(asked) if zoned.get(i) in FOLIO_ZONES]


def _refuse_apparatus(ref: str, spec: str | None, a) -> None:
    """Refuse a zoom aimed at the head line, the folio, or a signature mark.

    **The most structured text on the page has been its most expensive.** Four
    pages across two batches spent 42,620 tokens hunting a folio at the ceiling,
    and a fifth keyed a three-digit number off a two-digit one. Neither is a
    perception problem: a folio is two or three ASCII digits in a zone the
    segmenter labels, set in the same type as the running title beside it, and
    anything a 4x crop can say about it the composite already said. Every other
    zoom on the page is a question about a letterform; this one never is.

    So it is refused rather than discouraged, which is the difference between a
    rule and a suggestion — the standing brief has told readers not to do this
    since the second batch, and they kept doing it. The refusal names the two
    rungs that answer instead, because a reader stopped without an alternative
    reaches for a worse one.

    Zone-scoped, not line-scoped: `RunningTitleZone`, `QuireMarksZone` and
    `NumberingZone` are `FOLIO_ZONES`, and which of them a given page's folio
    landed in is exactly what a reader cannot be expected to know in advance.
    """
    if not spec:
        return
    from ..lines import page_lines
    try:
        recs = page_lines(alto_for_lines(ref, _alto_dir(a), a.root), a.root, ref=ref)
    except Exception:
        return          # a page whose lines will not load has a louder problem
    hit = apparatus_hits(recs, parse_spans(spec))
    if not hit:
        return
    which = ", ".join(str(i) for i in hit)
    raise ValueError(
        f"line{'s' if len(hit) > 1 else ''} {which} of {ref} "
        f"{'are' if len(hit) > 1 else 'is'} apparatus — the running title, the "
        "folio, or a signature mark — and zooming it is refused. It is plain "
        "type in a labelled zone, so `ocr numbered` shows it whole and a contact "
        "sheet shows it larger; no crop of it has ever settled anything a "
        "composite did not. Read it off the rung you are already on, and if the "
        "printed number runs wider than its box, `ocr gaps` says so and you key "
        "what is printed. Re-run naming only the lines you have a letterform "
        "question about.")


def run_zoom(a) -> int:
    refs, spec = ref_and_spec(a)
    one_page_only(a, {"out": "--out"}, refs)
    _refuse_apparatus(refs[0], spec, a)
    # Whether this page has ever been zoomed, asked *before* this call is logged:
    # the standing guidance below prints once per page, not once per crop.
    first = not any(c.get("action") == "zoom" for c in read_calls(refs[0], a.root))
    pairs = []
    with progress("zooming") as tick:
        for r in ptrack(refs, tick):
            _page_link(a, r)
            pairs.append((r, write_line_zoom(
                r, a.out or zoom_dir(r, a.root),
                only=parse_spans(spec) if spec else None,
                zoom=a.zoom, window=a.window, overlap=a.overlap,
                sheet_h=a.sheet_h, client_w=a.client_w,
                alto_dir=_alto_dir(a), root=a.root,
                smooth=a.smooth)))
            log_call(r, "zoom", a.root, reason=a.reason, zoom=a.zoom,
                     only=spec or "all", smooth=a.smooth,
                     images=len(pairs[-1][1]))
    out_per_ref(a, pairs)
    # **The standing guidance prints once per page, on the first zoom.** It used to
    # print on every call, on the reasoning that the choice is made on every call —
    # but it is 600-2,000 tokens of stderr, a reader who has read it once has read
    # it, and the same arithmetic now arrives in the claim block before any image is
    # rendered. Measured over eight readings it was the largest avoidable line item
    # after the fixed contract. What stays per-call is what is *about* this call.
    from ..lines import page_lines, zoom_capacity
    recs = page_lines(alto_for_lines(refs[0], _alto_dir(a), a.root), a.root,
                      ref=refs[0])
    caps = zoom_capacity([int(r["width"]) for r in recs if r.get("width")],
                         [int(r["height"]) for r in recs if r.get("height")],
                         overlap=a.overlap, client_w=a.client_w,
                         sheet_h=a.sheet_h)
    here = next((c for c in caps if c["zoom"] == a.zoom), None)
    if first:
        for row in caps:
            click.echo(
                f"  {row['zoom']}x: one crop comes back with ~{row['covers_pct']}% "
                f"of a line whatever you ask for, and {row['points_per_sheet']} of "
                f"them fit one sheet. A whole line is {row['full_strips']} strips.",
                err=True)
        click.echo(
            f"\nSeveral places go in ONE call — `ocr zoom {refs[0]} 11@70 13@40 "
            f"23@60` is one command, one sheet and one image, where three calls are "
            f"six turns. {(here or {}).get('points_per_sheet', 0)} places fit a "
            f"sheet at {a.zoom}x: batch every doubt you already have before reading "
            "any, and one line may be named twice (`1@0 1@100`) for its two ends.",
            err=True)
    # **Asking for less than a strip is the waste this reports.** The span is
    # widened to the window regardless, so a narrow request buys nothing and costs
    # the aiming error that produced it: the batch behind this rule spent three
    # crops framing one word at spans of 20%, each one of them already 40% by the
    # time it rendered.
    asked = parse_spans(spec) if spec else {}
    narrow = sorted(i for i, places in asked.items()
                    for lo, hi in places
                    if lo != hi and hi - lo < (here or {}).get("covers_pct", 0))
    if narrow and here:
        click.echo(
            f"\n{len(narrow)} span(s) narrower than one crop at {a.zoom}x "
            f"(lines {', '.join(map(str, narrow[:8]))}): they were widened to "
            f"~{here['covers_pct']}% anyway. Name the point instead — `N@60` "
            "centres a crop there and asks you for one number, not two.",
            err=True)
    if a.zoom == ZOOM_MAX:
        click.echo(
            f"\n{ZOOM_MAX}x is the ceiling, and it is for one mark on one word — "
            "a diacritic whose shape is the whole question. There is no source "
            "detail above it, so a second call at the same scale on the same ink "
            "returns the same picture and answers nothing new. If this crop did "
            "not settle it, the next move is a different question, a named "
            "contrast on the same line, or `note` saying it is unresolved.",
            err=True)
    return 0


def run_edit(a) -> int:
    from ..web import Sessions
    from ..web import serve as web

    refs = page_refs(a)
    # **Several refs *are* the walk**, the same rule `zones edit` follows: the
    # editor already steps through a list with the arrow keys, so a typed list
    # needs no new machinery.
    walk = refs
    label = ""
    if getattr(a, "all", False):
        # **The store's pages, not every scan.** This editor corrects lines the
        # segmenter missed, which presupposes a segmentation: a page with no ALTO
        # has no lines to be missing from and nothing to measure against, and
        # walking to it means opening an editor with nothing in it. `--all` here
        # is `_store_refs`' rule, the one the rest of the group follows.
        walk = _store_refs(a)
        label = "every page the store holds"
    # **A filter over `--all`, never a saved work-list.** The obvious itinerary
    # here is "the pages `gaps` still leaves live", and writing that to a `.lst`
    # would freeze it: every page worked makes the file wrong, and a stale
    # work-list is a claim about the corpus that nothing checks. Measured at the
    # moment it is asked instead — a raster read per page, which is the same cost
    # the census pays and buys an answer that is true when it is used.
    if getattr(a, "unsettled", False):
        from ..parallel import pmap

        # A page the store cannot answer for has nothing to measure, and asking
        # anyway is a crash rather than an empty answer — `line_gaps` parses the
        # ALTO. Skipped here rather than guarded inside the detector: absence is a
        # fact about this invocation's page list, not about the page.
        def _bands(r: str) -> list[dict]:
            if not alto_for_lines(r, _alto_dir(a), a.root).exists():
                return []
            return line_gaps(r, _alto_dir(a), a.root)

        with progress("measuring ink") as tick:
            bands = pmap(_bands, walk, a.jobs if hasattr(a, "jobs") else 1, tick)
        walk = [r for r, bs in zip(walk, bands, strict=True)
                if any(not b["exempted"] for b in bs)]
        label = "unsettled"
        if not walk:
            print("no page has an unsettled band — nothing to edit")
            return 0
    start = walk[0] if walk else None
    if not start:
        print("ocr edit needs a page to start at: name one or more refs, or "
              "--all for the whole book (--unsettled narrows it to the pages "
              "still carrying a band)", file=sys.stderr)
        return 2
    session = {"start": start, "alto_dir": _alto_dir(a), "itinerary": walk,
               "itinerary_name": label}
    # **Try the running server before binding one.** The four editors share a
    # process now, so a second verb started while one is up hands its work over
    # and opens a tab rather than dying on a held port — which is what they did
    # when each had a server to itself.
    joined = web.handoff("lines", session, open_at=f"/?ref={start}",
                         port=a.port)
    if joined:
        import webbrowser

        print(f"lines {start} -> {joined}   (joined the running server)")
        webbrowser.open(joined)
        return 0

    from ..corrections import lines_dir

    banner = [f"lines {start} -> "
              f"{web.url_for('lines', f'/?ref={start}', port=a.port)}"
              "   (Done button on the page, or ctrl-c)"]
    if walk:
        banner.append(f"itinerary {label}: {len(walk)} pages")
    banner.append(f"store -> {lines_dir(a.root)}")
    web.serve("lines", a.root, Sessions(root=a.root, by_editor={"lines": session}),
              banner=banner, open_at=f"/?ref={start}",
              ports={"lines": a.port} if a.port else None)
    return 0


def run_blot(a) -> int:
    refs = _store_refs(a)
    one_page_only(a, {"out": "--out"}, refs)
    from ..parallel import pmap

    dest = a.out or (a.root / "scans" / "w-blotted")

    # **Named pages are always repainted; only a sweep skips.** The mtime test is
    # cheap and honest here: this paints boxes read out of the ALTO, so an ALTO
    # newer than the blot is exactly the change that matters. `zones blot` skips
    # nothing, because skip policy there is undecided and waits on the dependency
    # graph — not because a stale blot is undetectable. See `zones.blot_all` for
    # what an mtime test there can and cannot see.
    def _stale(r: str) -> bool:
        if not (getattr(a, "all", False) and not a.force):
            return True
        src = alto_for_lines(r, _alto_dir(a), a.root)
        painted = dest / f"chukchi-{r}.png"
        return not (painted.exists() and src.exists()
                    and painted.stat().st_mtime >= src.stat().st_mtime)

    todo = [r for r in refs if _stale(r)]
    skipped = [r for r in refs if r not in set(todo)]
    # The skip is decided first, so the pool gets only pages that will be painted
    # — every one of them a decode, a paint and an encode.
    with progress("blotting") as tick:
        done = pmap(lambda r: write_blot(r, dest, _alto_dir(a), a.root,
                                         exemptions=a.exemptions),
                    todo, a.jobs, tick)
    out_per_ref(a, list(zip(todo, done, strict=True)))
    if skipped:
        out(a, {"skipped_fresh": len(skipped), "refs": " ".join(skipped)},
            "skipped_fresh")
    return 0


def _pending_review(root: Path) -> list[str]:
    """Pages holding a proposal and no decision — the adjudication queue.

    Not a farm and not a store: `review/` is authored working state, so an empty
    answer here is a true statement (nothing is waiting) rather than a tree
    nobody built.
    """
    from ..paths import decisions_path, page_refs_under, proposal_path
    return [r for r in page_refs_under(root)
            if proposal_path(r, root).exists()
            and not decisions_path(r, root).exists()]


def run_review(a) -> int:
    from ..web import Sessions
    from ..web import serve as web

    refs = page_refs(a) or _pending_review(a.root)
    if a.serve:
        for r in refs:
            _page_link(a, r)
        # Every ref's geometry is resolved before the socket is bound, for the
        # reason `page_refs` parses every ref before any work is done: a store
        # that cannot answer for a page is a fact about the invocation, and the
        # invocation is where it should be reported. It used to surface as a 500
        # on navigation — the CLI printed the URL and three reassuring
        # `decisions -> …` lines, then the browser got a traceback that only
        # existed on the server's stderr, which in the ordinary backgrounded case
        # is a log nobody is reading.
        queue = list(dict.fromkeys(norm_ref(r) for r in refs))
        gone = [(r, alto_for_lines(r, _alto_dir(a), a.root)) for r in queue]
        gone = [(r, p) for r, p in gone if not p.exists()]
        if gone:
            other = "gt" if "mz" in _alto_dir(a) else "mz"
            print("ERROR: no ALTO in this store for "
                  + ", ".join(f"{r} ({p})" for r, p in gone)
                  + f" — review reads --store mz by default; try --store {other}, "
                    "or `harness ocr predict` to write the prediction.",
                  file=sys.stderr)
            return 2
        session = {"queue": queue, "alto_dir": _alto_dir(a), "font": a.font,
                   "font_size": a.font_size, "box_lines": a.box_lines}
        joined = web.handoff("review", session, port=a.port)
        if joined:
            import webbrowser

            print(f"review {' '.join(queue)} -> {joined}   "
                  "(joined the running server)")
            webbrowser.open(joined)
            return 0
        banner = [f"review {' '.join(queue)} -> "
                  f"{web.url_for('review', port=a.port)}   "
                  "(Done button on the page, or ctrl-c)"]
        # Say which pages arrive already adjudicated *before* the reviewer meets
        # a strip full of green. A resumed session is the ordinary case; a page
        # unexpectedly carrying decisions is a question, and it should be asked
        # here rather than discovered by the reviewer wondering what they missed.
        banner += [f"decisions -> {decisions_path(r, a.root)}"
                   f"{'   (already present)' if decisions_path(r, a.root).exists() else ''}"
                   for r in queue]
        web.serve("review", a.root,
                  Sessions(root=a.root, by_editor={"review": session}),
                  banner=banner, ports={"review": a.port} if a.port else None)
        return 0
    if a.html:
        for r in refs:
            _page_link(a, r)
            dest = html_path(r, a.root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            # `crop_base` defaults to the directory beside the file, so the
            # standalone page references the crops as `crops/…` and works opened
            # straight off the filesystem — where it used to carry them base64'd
            # because there was no server to address them through.
            dest.write_text(
                _review_html(page_context(r, _alto_dir(a), a.root, font=a.font,
                                          font_size=a.font_size,
                                          box_lines=a.box_lines)),
                encoding="utf-8")
            print(f"{dest}: review page for {r}")
        return 0
    # The bare span diff measures a proposal against a *second witness*. If the
    # store it is pointed at resolves to the ground truth the proposal itself
    # produced, the diff compares a file with its own source and reports a clean
    # 40/40 — the shape of verification without the substance, which is exactly
    # the fault that killed the old verbatim firewall (docs/decisions.md, "What the
    # firewall is not"). So refuse rather than print a reassuring table.
    #
    # Checked for **every** ref before any table is printed. A collapsed witness
    # part-way down a batch would otherwise arrive after several pages of
    # reassuring output, which is where it is least likely to be read.
    for r in refs:
        src = alto_for_lines(r, _alto_dir(a), a.root)
        gt = a.root / "gt" / "ocr" / f"chukchi-{norm_ref(r)}.xml"
        if src.exists() and gt.exists() and src.resolve() == gt.resolve():
            print(f"ERROR: {src} resolves to the ground truth for {r} ({gt}), so "
                  "a proposal diff against it would compare that reading with "
                  "itself and report no differences. The span diff needs an "
                  f"independent witness — `--store mz` is one, or use `harness "
                  f"ocr review {r} --serve` to adjudicate.", file=sys.stderr)
            return 1
    # Two key sets, two tables — and pooled across refs rather than printed as N
    # `# ref`-separated pairs, which is what this did while it was the only
    # multi-ref action. A pooled table parses as one document; the separated form
    # did not parse as anything.
    sums, queues = [], []
    for r in refs:
        spans = page_spans(r, _alto_dir(a), a.root)
        n = len(page_lines(alto_for_lines(r, _alto_dir(a), a.root), a.root, ref=r))
        sums.append((r, summary(spans, n)))
        queues.append((r, spans if a.spans else group_spans(spans)))
    out_per_ref(a, sums)
    out_per_ref(a, queues, "spans" if a.spans else "groups")
    return 0


def run_restore(a) -> int:
    from ..review import restore_skip

    refs = page_refs(a)
    sweep = getattr(a, "all", False)
    if sweep:
        from ..paths import decisions_path, page_refs_under
        refs = [r for r in page_refs_under(a.root)
                if decisions_path(r, a.root).exists()]
    # **Every page is checked before any page is written.** `restore` with
    # `commit=False` runs the whole of its refusal set and touches nothing, so a
    # dry pass over the list is exactly the up-front validation a multi-ref write
    # needs: an unadjudicated line on the fourth page must not arrive with three
    # pages of ground truth already replaced.
    if a.commit and len(refs) > 1:
        for r in refs:
            if not (sweep and restore_skip(r, a.root, a.force)):
                restore(r, _alto_dir(a), a.root, a.force or sweep, commit=False)
    pairs, skipped = [], []
    for r in refs:
        # A sweep asks `restore_skip` and carries `force` on the adjudicator's
        # behalf where it says go: every page in gt/ocr/ holds text, so the bare
        # guard would refuse the whole store and a sweep that refuses everything
        # is not a sweep. A named ref keeps the guard exactly as it was.
        if sweep:
            why = restore_skip(r, a.root, a.force)
            if why:
                skipped.append({"ref": r, "why": why})
                continue
        pairs.append((r, restore(r, _alto_dir(a), a.root,
                                 a.force or sweep, a.commit)))
    # One ref keeps the two-document shape it always had — the report, then the
    # edits — because `edits` was already emitted separately here. Several go
    # through the general split: counts in the row, each list its own ref-keyed
    # table, which for `edits` is the more useful shape anyway, being the whole
    # batch's corrections in one place.
    if len(pairs) == 1 and not sweep:
        rep = pairs[0][1]
        out(a, {k: v for k, v in rep.items() if k != "edits"})
        if rep.get("edits"):
            out(a, rep["edits"], "edits")
    else:
        out_per_ref(a, pairs)
    if skipped:
        out(a, skipped, "skipped")
    return 0


def run_corrections(a) -> int:
    # An aggregate: refs *scope* it rather than multiplying it, so there is one
    # report whether one page was named or forty.
    refs = page_refs(a) or None
    rep = corrections(a.root, refs=refs, since=a.since)
    if a.min > 1:
        rep["changes"] = [c for c in rep["changes"] if c["count"] >= a.min]
    out(a, rep)
    return 0


def run_clean(a) -> int:
    refs = page_refs(a)
    if not refs:
        from ..paths import page_refs_under
        refs = page_refs_under(a.root)
    # `removed` is a list, so this is the splitting emitter: a count per page and
    # the names in their own ref-keyed table.
    out_per_ref(a, [(r, clean(r, a.root)) for r in refs])
    return 0


def run_predict(a) -> int:
    """One page, or a resumable sweep. Imported here because both models pull in
    torch, and paying that on `harness ocr pages` would be the whole group slow
    for one action's sake."""
    from ..recognize import predict, predict_all, predict_skip
    from ..zones import load_itinerary

    named = page_refs(a)
    if len(named) == 1:
        # A named ref is `single`: it overrides the exempt skip, because naming
        # the page is the request. It does not override an existing file — that
        # is what `--force` is for, and the two excuse different things.
        ref = named[0]
        why = predict_skip(ref, a.root, a.force, single=True)
        if why:
            print(f"{ref}: {why}", file=sys.stderr)
            return 0
        out(a, predict(ref, a.root, seg_model=a.seg_model,
                       rec_model=a.rec_model, device=a.device))
        return 0

    # Several named refs go through the sweep too, and that is the point of
    # naming them together: both models load once, which is most of the cost.
    # `named=` carries the single-page override with them, or a page a human
    # ruled exempt would be skipped in silence by the very command that named it.
    refs = named or (load_itinerary(a.itinerary, a.root) if a.itinerary else None)
    with progress("recognizing") as tick:
        rep = predict_all(a.root, refs, a.seg_model, a.rec_model, a.device,
                          a.force, named=bool(named), jobs=a.jobs, tick=tick)
    pages, skips = rep.pop("pages"), rep.pop("skips")
    out(a, rep)
    # Three tables, three key sets. Emitting them as one list would collapse the
    # whole thing to the verbose nested form (see emit.py).
    #
    # **Through `out()` rather than `emit()` directly**, which is what these three
    # used to do. It made no difference while `out` was a one-line wrapper and made
    # this the one action in the CLI that a re-routed print boundary would miss —
    # in the longest-running verb there is, where a silent divergence would take
    # the longest to notice.
    if pages:
        out(a, pages, "pages")
    if skips:
        out(a, skips, "skips")
    return 0


def run_link(a) -> int:
    from ..recognize import link_view
    out(a, link_view(a.root))
    return 0
