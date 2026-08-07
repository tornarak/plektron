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
from ._common import action, group, opt, out, out_per_ref, page_refs, refs_arg


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


def run_mets(a) -> int:
    out(a, F.write_mets(a.root, a.out))
    return 0
