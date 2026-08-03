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

Writes name `gt/ocr/` explicitly and there are exactly two of them: `restore`,
which fills text into lines that already exist, and `adopt-gap`, which creates an
empty line so a dropped one can be keyed. Both require `--commit`.

The old `lines` verb carried six modes on one parser — a table, a gap detector,
a geometry writer, and three image writers — selected by if-chain precedence, so
`--gaps` silently voided `--crops` and `--margins` did nothing under either.
They are six actions now, and a flag that does not apply is a parse error rather
than a no-op.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from ..context import all_refs, norm_ref
from ..lines import (
    DEFAULT_ALTO_DIR,
    LINE_SHEET_H,
    ZOOM,
    ZOOM_CLIENT_W,
    ZOOM_OVERLAP,
    ZOOM_SHEET_H,
    adopt_gaps,
    alto_for_lines,
    line_gaps,
    page_lines,
    parse_selection,
    write_blot,
    write_line_crops,
    write_line_sheets,
    write_line_zoom,
)
from ..parallel import ptrack
from ..paths import clean, crops_dir, ensure_page_link, html_path, sheets_dir, zoom_dir
from ..recognize import DEFAULT_REC_MODEL, DEFAULT_SEG_MODEL
from ..render import progress
from ..review import (
    corrections,
    group_spans,
    page_spans,
    render_queue_html,
    restore,
    serve,
    summary,
)
from ._common import (
    REF_HELP,
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
MARGINS_HELP = ("widen to the PrintSpace margins — a line polygon can exclude "
                "printed text that belongs to the line, and what it excludes "
                "sits in the margin (list numbers, the folio)")
OUT_HELP = ("write the images somewhere other than the page's own review/PP-NNN/ "
            "subdirectory — for a one-off comparison, not for the pass, whose "
            "files the other actions expect to find in the default place")


def _one_ref(p):
    """The singular ref positional — `adopt-gap` only, and it earns it.

    Its second positional is a VPOS measured on *that* page's raster, so a ref
    list would carry a band list belonging to one of them. Everything else in
    this group takes as many refs as you like; `test_cli_surface.py` holds this
    exemption by name so a new singular verb cannot slip in beside it.
    """
    arg(p, "ref", metavar="PP-NNN")
    p.help = f"{p.help}\n\nPP-NNN: {REF_HELP}."
    return p


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
              "geometry and text, in reading order with empties kept, which is "
              "the join detector_flags' line numbers cannot supply. `index` is "
              "an identity, not a position: it stays what ALTO document order "
              "assigned, so labels are not consecutive in a banded listing"),
              all_="every page the store read holds"))
    opt(p, "--full", is_flag=True,
                   help="include baseline and polygon points, which are long "
                        "enough to make the table unreadable by default")

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

    p = _store(_one_ref(add("adopt-gap", help="materialize measured `gaps` bands as "
              "empty TextLines in gt/ocr/, so a dropped line can be keyed. "
              "Geometry only, never CONTENT: text still arrives via "
              "decision.json -> restore. Each VPOS must match a measured band; "
              "naming which bands are real lines is the human call")))
    arg(p, "vpos", metavar="VPOS[,VPOS...]")
    p.help += ("\n\nVPOS: the band(s) to adopt, by the vpos `ocr gaps` reported. "
               "Comma-separated.")
    opt(p, "--commit", is_flag=True,
                   help="actually write gt/ocr/ — bare form reports the lines it "
                        "would create and writes nothing. This is a writer into "
                        "the ground-truth store and gates like `restore` does")

    # **No `--all` on the image writers, and the absence is deliberate.** Crops and
    # sheets are expensive in time and disk and are called per page by a reading
    # pass that is working on that page; a corpus form would be a lot of bytes
    # nobody asked for. `--out` is why they still need `one_page_only`: with a
    # second ref and one destination, the second page silently overwrote the first.
    p = _store(refs_arg(add("crops", help="one PNG per line, into review/PP-NNN/crops/")))
    opt(p, "--margins", is_flag=True, help=MARGINS_HELP)
    opt(p, "--out", type=click.Path(path_type=Path), default=None, help=OUT_HELP)

    p = _store(refs_arg(add("sheets", help="compose the line crops into labelled "
              "contact sheets in review/PP-NNN/sheets/, index drawn in the "
              "margin, nothing downscaled — the reading pass's instrument; emits "
              "the sheet/lines map instead of the line table")))
    opt(p, "--per-sheet", type=int, default=40,
                   help="lines per contact sheet, upper bound only — --height "
                        "packs by height first (default 40)")
    opt(p, "--height", "sheet_h", type=int, default=LINE_SHEET_H,
                   help=f"max contact-sheet height in px (default {LINE_SHEET_H}); "
                        "fewer, fuller sheets for the same lines")
    opt(p, "--margins", is_flag=True, help=MARGINS_HELP)
    opt(p, "--out", type=click.Path(path_type=Path), default=None, help=OUT_HELP)

    p = _store(refs_arg(add("zoom", help="magnify selected lines — overlapping strips "
              "at an integer scale, packed into as few sheets as the height "
              "budget allows, for the second look a contact sheet leaves open")))
    opt(p, "--only", default=None, metavar="SPEC",
                   help="line indices to magnify, e.g. 7,20,22-26 (default every "
                        "line on the page)")
    opt(p, "--zoom", type=int, default=ZOOM,
                   help=f"display px per source px, as delivered (default {ZOOM}). "
                        "Higher wraps each line into more strips, and a form seen "
                        "only in halves is the risk being traded against — "
                        "escalate for one question, not by default. --zoom 1 "
                        "wraps least")
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
    opt(p, "--margins", is_flag=True, help=MARGINS_HELP)
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
    pairs = []
    for r in _store_refs(a):
        recs = page_lines(alto_for_lines(r, _alto_dir(a), a.root))
        if not a.full:
            # Drop the two long geometry strings. Dropped from every record, never
            # some — a ragged key set collapses the table to the verbose nested
            # form (see emit.py).
            drop = ("baseline", "points")
            recs = [{k: v for k, v in rec.items() if k not in drop} for rec in recs]
        pairs.append((r, recs))
    out_per_ref(a, pairs)
    return 0


def run_gaps(a) -> int:
    from ..parallel import pmap
    refs = _store_refs(a)
    with progress("measuring ink") as tick:
        done = pmap(lambda r: line_gaps(r, _alto_dir(a), a.root), refs, a.jobs,
                    tick)
    out_per_ref(a, list(zip(refs, done, strict=True)))
    return 0


def run_adopt_gap(a) -> int:
    out(a, adopt_gaps(a.ref, [int(v) for v in a.vpos.split(",")],
                      _alto_dir(a), a.root, commit=a.commit))
    return 0


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


def run_crops(a) -> int:
    refs = page_refs(a)
    one_page_only(a, {"out": "--out"}, refs)
    pairs = []
    with progress("cropping") as tick:
        for r in ptrack(refs, tick):
            _page_link(a, r)
            pairs.append((r, write_line_crops(
                r, a.out or crops_dir(r, a.root), _alto_dir(a), a.root,
                margins=a.margins)))
    out_per_ref(a, pairs)
    return 0


def run_sheets(a) -> int:
    refs = page_refs(a)
    one_page_only(a, {"out": "--out"}, refs)
    pairs = []
    with progress("building sheets") as tick:
        for r in ptrack(refs, tick):
            _page_link(a, r)
            pairs.append((r, write_line_sheets(
                r, a.out or sheets_dir(r, a.root), _alto_dir(a), a.root,
                per_sheet=a.per_sheet, margins=a.margins, sheet_h=a.sheet_h)))
    out_per_ref(a, pairs)
    return 0


def run_zoom(a) -> int:
    refs = page_refs(a)
    # `--only` is that page's own line indices — an identity, not a position, so
    # the same numbers name unrelated lines on the next page.
    one_page_only(a, {"out": "--out", "only": "--only"}, refs)
    pairs = []
    with progress("zooming") as tick:
        for r in ptrack(refs, tick):
            _page_link(a, r)
            pairs.append((r, write_line_zoom(
                r, a.out or zoom_dir(r, a.root),
                only=parse_selection(a.only) if a.only else None,
                zoom=a.zoom, window=a.window, overlap=a.overlap,
                sheet_h=a.sheet_h, client_w=a.client_w,
                alto_dir=_alto_dir(a), root=a.root,
                margins=a.margins, smooth=a.smooth)))
    out_per_ref(a, pairs)
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
        done = pmap(lambda r: write_blot(r, dest, _alto_dir(a), a.root),
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
    from ..paths import decisions_path, proposal_path
    refs = [d.name for d in sorted((root / "review").glob("*"))
            if proposal_path(d.name, root).exists()
            and not decisions_path(d.name, root).exists()]
    return [norm_ref(r) for r in refs]


def run_review(a) -> int:
    refs = page_refs(a) or _pending_review(a.root)
    if a.serve:
        for r in refs:
            _page_link(a, r)
        serve(refs, _alto_dir(a), a.root, a.port)
        return 0
    if a.html:
        for r in refs:
            _page_link(a, r)
            dest = html_path(r, a.root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(render_queue_html(r, _alto_dir(a), a.root),
                            encoding="utf-8")
            print(f"{dest}: review page for {r}")
        return 0
    # The bare span diff measures a proposal against a *second witness*. If the
    # store it is pointed at resolves to the ground truth the proposal itself
    # produced, the diff compares a file with its own source and reports a clean
    # 40/40 — the shape of verification without the substance, which is exactly
    # the fault that killed the old verbatim firewall (CLAUDE.md, "What the
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
        n = len(page_lines(alto_for_lines(r, _alto_dir(a), a.root)))
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
        from ..paths import decisions_path
        refs = [norm_ref(d.name) for d in sorted((a.root / "review").glob("*"))
                if decisions_path(d.name, a.root).exists()]
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
        refs = [norm_ref(d.name) for d in sorted((a.root / "review").glob("*"))
                if d.is_dir()]
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
