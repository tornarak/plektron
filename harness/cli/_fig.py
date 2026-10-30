"""`harness fig` — the figure and caption track in `gt/fig/`.

A group of its own rather than actions under `zones`, because it names a
different store with a different geometry regime: a zone is a fixed-width band
of the measured text column and a figure is a freely-placed rectangle. The two
tracks share one editor and one keyboard; they share no geometry, no split
lists and no exemption files.

`harness corpus figures` stays where it is and is not aliased here. It is a
corpus-wide reconciliation of the store against itself and against the source
PDFs' own photographs — which is the same species as
`corpus normalize` and belongs with it. `fig check` is the different question:
one page's own boxes, against the rules.
"""
from __future__ import annotations

import click

from .. import figures as F
from .. import zones_config as zc
from ..layout import page_files, ref_of
from ..parallel import ptrack
from ..render import progress
from ._common import (
    action,
    add_jobs,
    arg,
    group,
    opt,
    out,
    out_per_ref,
    page_refs,
    refs_arg,
)


def register(cli):
    g = group(cli, "fig", "the figure and caption track in gt/fig/ — freely "
              "placed rectangles over the picture and its caption, each caption "
              "block carrying its adjudicated text, and the "
              "segmenter trained on them",
              sections=("The store", "The segmenter"), section="The passes")

    p = action(g, "check", run_check, section="The store",
               help="the gate. Errors are the three that are unarguable — a "
               "label the store does not declare, a polygon that is not the "
               "rectangle its own bbox claims, a box off the raster — and they "
               "set the exit code. Everything else is a warning, configured in "
               "config/zones.json and exemptable per page, because a "
               "picture overlapping a picture or a caption more than its share "
               "is the interesting page rather than the rejected one")
    _refs(p, "every page the store holds")
    opt(p, "--store", type=click.Choice(("gt", "mz")), default="gt",
        help="which store to read: 'gt' (default) is the human one and errors "
             "set the exit code; 'mz' is the machine one and is measurement — "
             "it always exits 0. A closed set of two, and there is deliberately "
             "no view over the pair for this store")

    p = action(g, "delete", run_delete, section="The store",
               help="withdraw a page from the figure store: its ALTO, its split "
               "mark and its rule exemptions. The counterpart to the store's "
               "refusal of an empty page — absence of a file is how this store "
               "records 'no figures here', so an emptied page has no other way "
               "to say so. Withdrawing a block withdraws the caption on it, which "
               "is why `save_figs` refuses a geometry save that would drop "
               "ratified text unless the caller says it means to")
    _refs(p)
    opt(p, "--commit", is_flag=True,
        help="actually delete. Without it the row is a preview and nothing is "
             "written")

    p = action(g, "crops", run_crops, section="The store",
               help="cut every declared picture out of its raster into "
               "scans/fig-crops/, one PNG per GraphicZone. Pad 0 — the declared "
               "box and not a pixel more, the blot's rule and for its reason: a "
               "pad pulls body text into the crop wherever prose sits hard "
               "against an inset figure. One crop per box rather than one per "
               "printed figure, because a bounding box over boxes a human drew "
               "separately is a region nobody drew, and on 1-276 that region is "
               "six lines of prose; holding a figure's parts together is the "
               "reader's job. Derived output, so it writes on invocation and "
               "takes no --commit")
    _refs(p, "every page the figure store holds")
    opt(p, "--force", is_flag=True,
        help="re-cut crops that are newer than both their inputs. Without it a "
             "fresh crop is left alone, so a rebuild does not give every file a "
             "new mtime and a new ETag and stop the browser ever caching one")
    opt(p, "--out", metavar="DIR", default=None,
        help="where to write them [scans/fig-crops/]")
    add_jobs(p)

    p = action(g, "witness", run_witness, section="The store",
               help="compare the fresh caption reading against the caption in gt/fig/, "
               "block for block — the whole point of reading them twice. "
               "Measurement and never a gate: two ratified readings disagreeing "
               "is a finding, and which one is right is a human's ruling against "
               "the scan, not this verb's. The header says whether the reading "
               "was blind, because a comparison whose two inputs may be one "
               "input has to say so — a run whose reader had the old file open "
               "prints the same table and means nothing")
    opt(p, "--verdict", type=click.Choice(("differ", "lines_differ", "all")),
        default="differ",
        help="which rows to list. 'differ' (default) is the class the exercise "
             "exists to surface; 'lines_differ' is where only the printed-line "
             "division moved, which is a fact about the box and not the type")

    p = action(g, "restore", run_restore, section="The store",
               help="write the adjudicated captions into gt/fig/ as "
               "String/@CONTENT — one String per printed line, inside one "
               "TextLine carrying the block's own bbox. **This is the "
               "one writer**: the store is populated by restoring rulings, which is "
               "what lets the text carry "
               "#gt. Refuses a block with neither a ruling nor a reading, a "
               "target that already holds text without --force, and any "
               "unlicensed mark")
    _refs(p, "every page the figure store holds")
    opt(p, "--force", is_flag=True,
        help="overwrite captions already in the store. Once this has run every "
             "FigDesc holds one, so a second pass is a deliberate act")
    opt(p, "--commit", is_flag=True,
        help="actually write. Without it the report comes back the same and "
             "nothing on disk changes")

    p = action(g, "review", run_review, section="The store",
               help="adjudicate the captions the two readings disagree on, in "
               "the browser — every one in a single document, each with its own "
               "strip and what the store already holds beside the box. This is "
               "`ocr review --issues` with a different block builder and a "
               "different store: same page, same palette, same keyboard, same "
               "all-or-nothing and prior-text guards, because adjudicating "
               "flagged fields from many pages at once is the same act whatever "
               "the fields are")
    opt(p, "--verdict", type=click.Choice(("differ", "lines_differ", "all")),
        default="differ", help="which disagreements to carry [differ]")
    opt(p, "--port", type=int, default=None, metavar="N",
        help="serve on this port instead of the editor's registered one")

    p = action(g, "zoom", run_zoom, section="The store",
               help="magnify one caption block, sliced into strips that fill the "
               "client. **For a Tier-1 glyph you cannot resolve off the contact "
               "sheet, and for nothing else** — 34 of this store's 395 captions "
               "carry a Tier-1 glyph at all, so the other 361 are settled at 1x "
               "and magnifying them spends images re-reading what you have "
               "already read. 2x default, 4x ceiling; nothing is sharpened or "
               "denoised, since filtering manufactures evidence rather than "
               "revealing it")
    arg(p, "key", metavar="KEY")
    p.help = (f"{p.help}\n\nKEY: the caption's `PP-NNN|<zone-suffix>`, as "
              "`fig sheets` labels every strip and the manifest lists them.")
    opt(p, "--zoom", type=int, default=2, metavar="N",
        help="magnification, 1..4 [2]. At 4x a strip returns about a fifth of a "
             "caption, so a whole one costs several images")
    opt(p, "--reason", required=True,
        help="which glyph, and what you are trying to settle — in a few words, "
             "recorded with the call. Required for `ocr zoom`'s reason: a zoom "
             "nobody has to justify is one nobody counts, and the pages that "
             "failed there did so at 59 and 81 crops apiece, each individually "
             "plausible. Naming the question before the call is also what "
             "separates re-aiming a miss from asking the same thing louder")
    opt(p, "--out", metavar="DIR", default=None,
        help="where to write them [review/captions/zoom/]")

    p = action(g, "sheets", run_sheets, section="The store",
               help="tile every caption onto contact sheets for reading, ~12 "
               "strips apiece. The sheet is the unit of this pass and the "
               "census is why: 151 of the 250 captioned pages hold exactly one "
               "caption and the median caption is 66 characters, so a page is "
               "not a batch. Padded vertically, unlike `fig crops` — a caption "
               "strip exists for somebody to read the type, and the commonest "
               "defect here is a box drawn round the wrong number of printed "
               "lines, which a strip cut at the declared edge cannot show; the "
               "declared edge is ruled on the strip instead. Plate captions set "
               "rotated beside their picture are turned upright, by the same "
               "width>=height test that pairs them. Derived output: it writes "
               "on invocation and takes no --commit")
    _refs(p, "every page the figure store holds")
    opt(p, "--out", metavar="DIR", default=None,
        help="where to write them [review/captions/sheets/]")
    opt(p, "--per-sheet", type=int, default=12, metavar="N",
        help="strips per sheet [12]")
    opt(p, "--pad", type=float, default=F.CAP_PAD, metavar="F",
        help=f"vertical pad as a multiple of the block's own height "
             f"[{F.CAP_PAD}]. 0 cuts at the declared edge and hides exactly the "
             f"defect the pad is for")

    # ---- the segmenter -----------------------------------------------------

    p = action(g, "predict", run_predict, section="The segmenter",
               help="run the figure segmenter and write raw ALTO into mz/fig/ — "
               "the machine store, never gt/. Input is the RAW scan, unlike "
               "zones predict: the blot paints this model's target white")
    _refs(p, "every page with a raster")
    opt(p, "--force", is_flag=True,
        help="overwrite an existing mz/fig/ page. Required because that file's "
             "ProcessingStep is the only witness to which model wrote it")
    opt(p, "--model", metavar="M", default=None, help="model path [the installed one]")
    opt(p, "--device", metavar="D", default="auto", help="torch device [auto]")

    p = action(g, "extend", run_extend, section="The store",
               help="grow keyed pictures to cover the photograph the source PDF "
               "separated out, so the blot leaves no antialiased rim. UNION "
               "ONLY: a box already larger than its photograph is left alone, "
               "because some figures carry line work outside the JPEG that "
               "contracting would uncover. Only a clean 1:1 pair is touched — a "
               "photograph spanning several keyed parts of one lettered figure "
               "is out of scope and stays that way. Refuses any page where the "
               "growth would change which caption goes with which picture")
    _refs(p, "every page with a photograph in the manifest")
    opt(p, "--max-growth", type=float, default=None, metavar="PCT",
        help="largest area increase, in percent, this run may apply to any one "
             "picture. REQUIRED with --commit and has no default: a report run "
             "prints what every box would gain, and the ceiling is picked from "
             "that. A box that would grow more is refused and named")
    opt(p, "--commit", is_flag=True,
        help="write gt/fig/; without it, report what would grow and by how much")

    p = action(g, "propose", run_propose, section="The store",
               help="write mz/fig/ proposals from the source PDF's own embedded "
               "image placements, via data/pdf_images.json. GraphicZone only: "
               "the PDF says where a picture is and nothing at all about "
               "captions. Not the segmenter — a different kind of witness, the "
               "scanner's own decision about which pixels were photograph. On "
               "THIS book it is correctly invisible, since every photograph is "
               "on a page gt/fig/ already covers and gt wins in the editor; it "
               "is the first pass on a book nobody has keyed yet. Writes "
               "master-space coordinates, so run it after the raster rebuild "
               "and not before")
    _refs(p, "every page with a photograph in the manifest")
    opt(p, "--force", is_flag=True,
        help="overwrite an existing mz/fig/ page. Required because that file's "
             "ProcessingStep is the only witness to whether the segmenter or "
             "the PDF wrote it")


def _refs(p, all_: str | None = None):
    return refs_arg(p, all_=all_)


def run_check(a) -> int:
    store = F.FIGDIR if a.store == "gt" else F.MZFIGDIR
    cfg = zc.load_config(a.root)
    named = page_refs(a)

    if named:
        # `errors`, `warnings` and `exempted` are lists, so pooling puts their
        # counts in the page's row and gives each its own ref-keyed table — the
        # shape `zones check` uses, for the same reason: on one page the detail is
        # the answer, and across several the counts are.
        with progress("checking figures") as tick:
            reps = [(r, F.validate_fig_page(r, a.root, cfg, store))
                    for r in ptrack(named, tick)]
        out_per_ref(a, reps)
        bad = any(rep["errors"] for _, rep in reps)
        return 1 if (bad and store == F.FIGDIR) else 0

    refs = F.fig_refs(a.root, store)
    with progress("checking figures") as tick:
        rows = [F.validate_fig_page(r, a.root, cfg, store)
                for r in ptrack(refs, tick)]
    flagged = [r for r in rows if r["errors"] or r["warnings"]]
    out(a, {"pages": len(rows),
            "figures": sum(r["figures"] for r in rows),
            "captions": sum(r["captions"] for r in rows),
            "errors": sum(len(r["errors"]) for r in rows),
            "warnings": sum(len(r["warnings"]) for r in rows),
            "exempted": sum(len(r["exempted"]) for r in rows)})
    # Only the pages with something to say. A row per clean page would be 252
    # lines of zeroes with three findings buried in them, which is how a report
    # stops being read.
    if flagged:
        out(a, [{"ref": r["ref"], "blocks": r["blocks"],
                 "figures": r["figures"], "captions": r["captions"],
                 "rules": "; ".join(
                     [f"{e['rule']}!" for e in r["errors"]]
                     + [w["rule"] for w in r["warnings"]])}
                for r in flagged], "flagged")

    # `mz` measures and never gates — the machine store's faults are a fact about
    # the model, and an exit code over them would make a bad prediction look like
    # a broken repository.
    if store == F.MZFIGDIR:
        return 0
    # The patch table is a claim about *this* store, so it is checked against it
    # here rather than trusted: re-box a leaf and a hand-keyed number may be
    # naming a zone that is gone. Reported only when it has something to say.
    patches = F.check_number_patches(a.root)
    if patches:
        out(a, patches, "figure_numbers.json")
    return 1 if (patches or any(r["errors"] for r in rows)) else 0


def run_delete(a) -> int:
    with progress("deleting") as tick:
        rows = [F.delete_figs(r, a.root, commit=a.commit)
                for r in ptrack(page_refs(a), tick)]
    out(a, rows)
    return 0


def run_crops(a) -> int:
    from pathlib import Path
    with progress("cropping") as tick:
        rep = F.crop_all(page_refs(a) or None, root=a.root,
                         out_dir=Path(a.out) if a.out else None,
                         force=a.force, jobs=a.jobs, tick=tick)
    rows = rep.pop("rows")
    # The per-page rows only when pages were named. Over the whole store 252 rows
    # of mostly zeroes buries the totals, which are the answer to "did the sweep
    # run"; naming a page means the page is the question.
    out(a, {**rep, "rows": rows} if page_refs(a) else rep)
    return 0


def run_restore(a) -> int:
    from .. import captions as C
    with progress("restoring captions") as tick:
        rep = C.restore(a.root, refs=page_refs(a) or None,
                        force=a.force, commit=a.commit, tick=tick)
    out(a, rep)
    return 0


def run_review(a) -> int:
    from .. import captions as C
    from ..web import Sessions
    from ..web import serve as web

    # **Resolved before the socket is bound**, `ocr review`'s rule: a refusal
    # arriving after a browser has opened on an empty page is worse than no check.
    rep = C.witness(a.root)
    rows = [r for r in rep["rows"]
            if a.verdict == "all" or r["verdict"] == a.verdict]
    if not rows:
        print(f"nothing to adjudicate: {rep['agree']} of {rep['compared']} "
              f"captions agree and none is {a.verdict}")
        return 0

    session = {"verdict": a.verdict}
    banner = [
        f"adjudicate {len(rows)} caption(s) the two readings disagree on -> "
        f"{web.url_for('review', path='/captions', port=a.port)}   "
        "(Save all, then ctrl-c)",
        f"  blind read: {rep['blind']}   agree {rep['agree']}/{rep['compared']}",
    ]
    joined = web.handoff("review", session, port=a.port)
    if joined:
        import webbrowser

        url = f"{joined.rstrip('/')}/captions"
        print(f"{banner[0].split(' -> ')[0]} -> {url}   (joined the running server)")
        webbrowser.open(url)
        return 0
    web.serve("review", a.root,
              Sessions(root=a.root, by_editor={"review": session}),
              banner=banner, open_at="/captions",
              ports={"review": a.port} if a.port else None)
    return 0


def run_witness(a) -> int:
    from .. import captions as C
    rep = C.witness(a.root)
    rows = rep.pop("rows")
    if a.verdict != "all":
        rows = [r for r in rows if r["verdict"] == a.verdict]
    out(a, {**rep, "rows": rows})
    # **Exit 0 whatever it finds.** Measurement never gates (VERBS.md,
    # Conventions), and there is nothing here a caller could fix to make it pass:
    # a disagreement is answered by a human ruling in `fig review`, not by editing
    # either store toward the other.
    return 0


def run_zoom(a) -> int:
    from pathlib import Path

    from ..paths import CAPTIONS, review_dir
    out_dir = Path(a.out) if a.out else review_dir(CAPTIONS, a.root) / "zoom"
    rows = F.write_caption_zoom(a.key, out_dir, a.root, zoom=a.zoom)
    out(a, {"key": a.key, "zoom": a.zoom, "sheets": len(rows), "rows": rows})
    return 0


def run_sheets(a) -> int:
    from pathlib import Path

    from ..paths import caption_sheets_dir
    out_dir = Path(a.out) if a.out else caption_sheets_dir(a.root)
    with progress("composing sheets") as tick:
        man = F.write_caption_sheets(out_dir, a.root, refs=page_refs(a) or None,
                                     per_sheet=a.per_sheet, pad=a.pad, tick=tick)
    rotated = sum(1 for b in man["blocks"].values()
                  if b["orientation"] == "rotated")
    # The blocks themselves are the manifest's business, not the terminal's: 395
    # rows would bury the two numbers that answer "did it run and what is there".
    # `rotated` prints because it is the one class a reader has to be told about
    # in advance — a strip that came out sideways is a defect, not a caption.
    out(a, {"sheets": len(man["sheets"]), "captions": man["captions"],
            "rotated": rotated, "out": str(out_dir)})
    return 0


def run_remark(a) -> int:
    out(a, F.remark_eval(a.root, fraction=a.fraction, commit=a.commit))
    return 0


def run_assemble(a) -> int:
    res = F.assemble(a.root, scratch=a.scratch)
    cmd = res.pop("command")
    out(a, res)
    # Printed apart from the row so it can be copied whole. It is reported and
    # never run: training holds the GPU for hours and belongs in the user's own
    # terminal, not inside a verb that looks like it returns.
    #
    # **Named**, because two unnamed sections both take the action's name and
    # `--json` then refuses the pair: `harness fig assemble --json` exited 2 with
    # "2 sections resolve to ['assemble']" for as long as this verb existed. Only
    # the table path was ever exercised. `ocr assemble` spells it the same way.
    out(a, {"run this yourself": cmd}, "run this yourself")
    return 0


def run_predict(a) -> int:
    refs = page_refs(a) or [
        ref_of(p.stem, a.root)
        for p in sorted(page_files(a.root / "scans", ".png", a.root))]
    with progress("segmenting figures") as tick:
        rows = F.predict(refs, a.root, model_path=a.model, device=a.device,
                         force=a.force, tick=tick)
    out(a, rows)
    return 0


def run_extend(a) -> int:
    if a.commit and a.max_growth is None:
        # Not a default, deliberately. The ceiling is a judgement about how far a
        # mechanical rule may move a rectangle a person drew, and a default would
        # make that judgement on their behalf and then look like their decision.
        raise click.UsageError(
            "--commit needs --max-growth PCT: the largest area increase this run "
            "may apply to any one picture. Run without --commit first — it prints "
            "what every box would gain, so the ceiling comes from the evidence.")
    frac = None if a.max_growth is None else a.max_growth / 100.0
    with progress("extending") as tick:
        rows = F.extend_all(page_refs(a) or None, a.root, max_growth=frac,
                            commit=a.commit, tick=tick)
    pcts = sorted(g["pct"] for r in rows for g in r["growth"])
    summary = {"pages": len(rows),
               "would_grow": sum(len(r["growth"]) for r in rows),
               "grew": sum(r["grew"] for r in rows),
               "over_margin": sum(r["over"] for r in rows),
               "out_of_scope": sum(r["out_of_scope"] for r in rows),
               "wrote": sum(1 for r in rows if r["wrote"])}
    if pcts:
        # The distribution, so a ceiling can be picked from it rather than guessed.
        summary |= {"growth_p50": f"{pcts[len(pcts) // 2]:.2f}%",
                    "growth_p90": f"{pcts[int(len(pcts) * 0.9)]:.2f}%",
                    "growth_max": f"{pcts[-1]:.2f}%"}
    out(a, summary)
    if rows:
        out(a, [{"ref": r["ref"], "grew": r["grew"], "over": r["over"],
                 "out_of_scope": r["out_of_scope"], "wrote": r["wrote"],
                 "growth": " ".join(f"{g['pct']:.2f}%" for g in r["growth"]),
                 "note": r["note"]} for r in rows], "per page", heading=True)
    if not a.commit:
        out(a, {"report only": "--commit --max-growth PCT writes gt/fig/"})
    return 0


def run_propose(a) -> int:
    refs = page_refs(a) or sorted(F.pdf_images(a.root))
    with progress("proposing") as tick:
        rows = F.propose_from_pdf(refs, a.root, force=a.force, tick=tick)
    out(a, rows)
    return 0


def run_score(a) -> int:
    res = F.score(a.root, model_path=a.model, min_iou=a.min_iou)
    out(a, {"model": res["model"], "min_iou": res["min_iou"]})
    rows = []
    for split, acc in res["splits"].items():
        for label in (F.GRAPHIC, F.FIGDESC):
            c = acc[label]
            rows.append({"split": split, "class": label, "truth": c["truth"],
                         "predicted": c["predicted"], "matched": c["matched"],
                         "recall": c["recall"], "precision": c["precision"]})
    out(a, rows, "classes")
    out(a, [{"split": s, "pages": v["pages"], "empty_pages": v["empty_pages"],
             "spurious_on_empty": v["spurious_on_empty"]}
            for s, v in res["splits"].items()], "negatives")
    return 0


def run_install(a) -> int:
    out(a, F.install_model(a.checkpoint, a.root, name=a.name,
                           commit=a.commit, device=a.device))
    return 0
