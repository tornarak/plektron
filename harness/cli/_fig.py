"""`harness fig` — the figure and caption track in `gt/fig/`.

A group of its own rather than actions under `zones`, because it names a
different store with a different geometry regime: a zone is a fixed-width band
of the measured text column and a figure is a freely-placed rectangle. The two
tracks share one editor and one keyboard; they share no geometry, no split
lists and no exemption files.

`harness corpus figures` stays where it is and is not aliased here. It is a
corpus-wide reconciliation *between two stores* — geometry against the
hand-read captions in `data/readings.md` — which is the same species as
`corpus normalize` and belongs with it. `fig check` is the different question:
one page's own boxes, against the rules.
"""
from __future__ import annotations

import click

from .. import figures as F
from .. import zones_config as zc
from ._common import action, arg, group, opt, out, out_per_ref, page_refs, refs_arg


def register(cli):
    g = group(cli, "fig", "the figure and caption track in gt/fig/ — freely "
              "placed rectangles over the picture and its caption, paired "
              "with the hand-read text in data/readings.md, and the "
              "segmenter trained on them",
              sections=("The store", "The segmenter"), section="The passes")

    p = action(g, "check", run_check, section="The store",
               help="the gate. Errors are the three that are unarguable — a "
               "label the store does not declare, a polygon that is not the "
               "rectangle its own bbox claims, a box off the raster — and they "
               "set the exit code. Everything else is a warning, configured in "
               "data/zones_config.json and exemptable per page, because a "
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
               "to say so. It does NOT touch data/readings.md: a geometry "
               "withdrawal cascading into hand-read text would be far worse "
               "than the loud reconciliation failure, and the report counts the "
               "captions it orphans so `corpus figures` can name them")
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
    opt(p, "--jobs", type=int, default=None, metavar="N",
        help="worker threads; 1 runs serially and builds no pool [cores, capped]")

    p = action(g, "mets", run_mets, section="The store", pageable=False,
               help="write a METS manifest over gt/fig/ into a directory you "
               "name, for importing the store into eScriptorium. Built on "
               "demand and never tracked: the one that used to sit in gt/fig/ "
               "was an export artifact describing a store that has since been "
               "rewritten, which is the failure mode of committing a manifest "
               "beside the thing it manifests")
    opt(p, "--out", metavar="DIR", required=True,
        help="where to write METS.xml. Required and has no default, so this "
             "cannot land in gt/fig/ by omission")

    # ---- the segmenter -----------------------------------------------------

    p = action(g, "remark-eval", run_remark, section="The segmenter",
               pageable=False,
               help="mint or extend the train/eval split. The universe is every "
               "page with a figure ALTO — exempt plates included, since a plate "
               "carrying figures is the best training page there is — plus the "
               "pages witnessed to have none. Additive: a mark a human made is "
               "never moved, or the held-out set drifts with whatever was keyed "
               "last and stops being held out")
    opt(p, "--fraction", type=float, default=0.20, metavar="F",
        help="share of the newly-marked pages to hold out [0.20]")
    opt(p, "--commit", is_flag=True, help="write the lists; without it, a preview")

    p = action(g, "assemble", run_assemble, section="The segmenter",
               pageable=False,
               help="lay out train/bogoras-fig/ and report the ketos command. "
               "Runs nothing: training holds the GPU for hours and belongs in "
               "your own terminal. A page with no figures gets a synthesized "
               "empty ALTO here and nowhere else — the store never holds one, "
               "because absence of the file is how it records 'no figures'")
    opt(p, "--scratch", is_flag=True,
        help="train from random init rather than fine-tuning blla or the "
             "installed figure model")

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

    p = action(g, "score", run_score, section="The segmenter", pageable=False,
               help="compare mz/fig/ against gt/fig/, per split and per class, "
               "never blended. Pictures and captions are scored apart because "
               "they differ by an order of magnitude in size, and pages "
               "witnessed to have no figures are their own bucket — a box "
               "predicted on one is a false positive with nowhere else to go. "
               "Measurement: always exits 0")
    opt(p, "--model", metavar="M", default=None, help="model path [the installed one]")
    opt(p, "--min-iou", type=float, default=0.5, metavar="F",
        help="area overlap at which a predicted box counts as found [0.5]")

    p = action(g, "install", run_install, section="The segmenter", pageable=False,
               help="score a checkpoint, refuse a swapped class map, then "
               "install it into models/bogoras-fig/ with its manifest and the "
               "split it consumed. Everything that makes a checkpoint "
               "trustworthy is a precondition of installing it, so the copy is "
               "last")
    arg(p, "checkpoint", metavar="CKPT")
    p.help = f"{p.help}\n\nCKPT: the .safetensors ketos wrote."
    opt(p, "--name", default=F.MODEL_NAME, help=f"installed name [{F.MODEL_NAME}]")
    opt(p, "--device", metavar="D", default="auto", help="torch device [auto]")
    opt(p, "--commit", is_flag=True, help="install it; without it, a preview")


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
        reps = [(r, F.validate_fig_page(r, a.root, cfg, store)) for r in named]
        out_per_ref(a, reps)
        bad = any(rep["errors"] for _, rep in reps)
        return 1 if (bad and store == F.FIGDIR) else 0

    refs = F.fig_refs(a.root, store)
    rows = [F.validate_fig_page(r, a.root, cfg, store) for r in refs]
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
    return 1 if any(r["errors"] for r in rows) else 0


def run_delete(a) -> int:
    rows = [F.delete_figs(r, a.root, commit=a.commit) for r in page_refs(a)]
    out(a, rows)
    return 0


def run_crops(a) -> int:
    from pathlib import Path
    rep = F.crop_all(page_refs(a) or None, root=a.root,
                     out_dir=Path(a.out) if a.out else None,
                     force=a.force, jobs=a.jobs)
    rows = rep.pop("rows")
    # The per-page rows only when pages were named. Over the whole store 252 rows
    # of mostly zeroes buries the totals, which are the answer to "did the sweep
    # run"; naming a page means the page is the question.
    out(a, {**rep, "rows": rows} if page_refs(a) else rep)
    return 0


def run_mets(a) -> int:
    out(a, F.write_mets(a.root, a.out))
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
    out(a, {"run this yourself": cmd})
    return 0


def run_predict(a) -> int:
    refs = page_refs(a) or [
        p.stem.replace("chukchi-", "")
        for p in sorted((a.root / "scans").glob("chukchi-*.png"))]
    out(a, F.predict(refs, a.root, model_path=a.model, device=a.device,
                     force=a.force))
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
    rows = F.extend_all(page_refs(a) or None, a.root, max_growth=frac,
                        commit=a.commit)
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
    out(a, F.propose_from_pdf(refs, a.root, force=a.force))
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
