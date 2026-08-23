"""`harness scans` — the rasters: what the PDFs hold, what the tree holds, the swap.

Everything under here is about the *substrate* the stores are keyed to, which is
why it is one group rather than a corner of `fig` (whose check was the manifest's
first caller and where the reader for it therefore grew) or of `corpus` (which
reports the pipeline's state, not the pixels'). The dividing question is what a
verb would have to open: these open PDFs and PNGs and the geometry manifest, and
nothing else in the CLI does.

**What deliberately does not land here.** Cropping — `ocr zoom` and `fig crops`
already cut pixels for a reader, and a third cropper would be a third set of
padding and scaling rules to keep in step. Rebuilding the derived farms —
`views build` owns that, and `swap` names its `builder` string rather than
calling it. Blotting, which is `zones`'.
"""
from __future__ import annotations

from pathlib import Path

from .. import render, scans
from ._common import (
    action,
    add_jobs,
    arg,
    group,
    opt,
    out,
    page_refs,
    refs_arg,
    verdict,
)


def register(cli):
    g = group(cli, "scans",
              "the source rasters: the geometry the PDFs declare, what "
              "`scans/` actually holds, and the swap that installs a re-cut "
              "tree together with every coordinate keyed to it",
              sections=("Building the tree", "What the rasters are"),
              section="Whole-corpus")

    p = action(g, "extract", run_extract, section="Building the tree",
               help="read the PDFs' own embedded layers and derive each page's "
               "geometry: the 1-bit JBIG2 master, where it is placed, and every "
               "photograph pasted onto it. **Cuts from the layers; never "
               "renders** — rendering samples the *page box*, and the boxes "
               "these scans were wrapped in are arbitrary, which is how part 3 "
               "came to be read ~35 px short on every side for twenty months. "
               "The geometry is derived per page, never per part: `1-303`'s "
               "master is 2824x3897 among 357 neighbours at 2781x3866. "
               "**Refuses rather than guesses** — two full-page images, a "
               "master not at scale 1.0, a photo rect outside its master, a "
               "non-integral paste, or a page named masterless that turns out "
               "to have one. Exit 1 if any page was refused")
    refs_arg(p, all_="every page of every PDF in pdfs/")
    opt(p, "--rasters", metavar="DIR",
        help="also cut the tree, into DIR — **a sibling, never `scans/`**, "
             "carrying its own `pdf_images.json` so that a directory of PNGs is "
             "never separable from the geometry it was cut at. `scans swap` is "
             "what installs it. Requires --all: a manifest is a statement about "
             "the whole corpus")
    opt(p, "--commit", is_flag=True,
        help="write data/pdf_images.json, the one tracked output. Requires "
             "--all, for the same reason --rasters does: a partial manifest "
             "would silently drop the 800 pages it did not walk")
    add_jobs(p, processes=True)

    p = action(g, "swap", run_swap, section="Building the tree",
               help="install a cut tree, and move everything keyed to its "
               "geometry with it. **The rasters are the cheap half** — they are "
               "derived and a bad one costs a re-run; the point of the verb is "
               "the six coordinate stores, the band ledgers, the ink cache, the "
               "painted farms and the review working set, all of which describe "
               "pixels in the old master's space. Reports by default, and the "
               "report is the real one: the per-page shift between the two "
               "manifests, what each store would do, what would be discarded "
               "and what rebuilds it. **The shift is manifest-to-manifest**, "
               "not the manifest's `offset` field, which records the spent "
               "pdftoppm-era placement. Exit 1 if anything was refused")
    arg(p, "tree", metavar="DIR", nargs=1, required=True)
    p.help = f"{p.help}\n\nDIR: a tree cut by `scans extract --rasters`, holding " \
             "its own `pdf_images.json`."
    opt(p, "--commit", is_flag=True,
        help="perform it. Stage-verify-move plus a receipt: every translation "
             "is computed and digest-checked before anything is written, any "
             "refusal aborts with nothing moved, and `data/_migrated.json` "
             "records which manifest the stores are now in — a zero shift "
             "leaves a page byte-identical, so 'correctly untouched' and 'not "
             "yet reached' cannot be told apart by looking")

    p = action(g, "info", run_info, section="What the rasters are",
               help="one page's geometry, from the manifest and from the file "
               "on disk, with **whether the two agree**. Master size, bit "
               "depth, colourspace, the placement, the leaf kind if the page "
               "has one, and every photograph's rect, native size and ppi. "
               "This is the verb to reach for instead of `identify` or a PIL "
               "one-liner: neither of those can see the manifest, which is "
               "where a photograph's own resolution and the shift live. "
               "Reports; never gates")
    refs_arg(p, all_="every page the manifest holds")
    add_jobs(p)

    p = action(g, "census", run_census, section="What the rasters are",
               help="the counts, which are deliberately written down nowhere, "
               "and **one table of combinations rather than three of "
               "marginals**: every distinct `(source file, colour, size, "
               "offset, photographs)` with how many pages hold it, sorted by "
               "the class so each one-off falls beside the class it is an "
               "exception to. Separate distributions could not say whether "
               "the one page at 2824x3897 was also the odd one at (0,0) — it "
               "is. **A class of five pages or fewer is named**, since a row "
               "reading `1 page` is the one worth looking at. A number in a "
               "file nothing regenerates goes stale, so this is the command "
               "that answers instead. Reports; never gates")
    refs_arg(p, all_="every page the manifest holds")
    add_jobs(p)

    p = action(g, "audit", run_audit, section="What the rasters are",
               help="the manifest against the tree on disk: a page in one and "
               "not the other, a size that disagrees, a **mode** that does — a "
               "bitonal page that came back 8-bit means something resampled it, "
               "which is the whole failure the tree was re-cut to undo — and a "
               "raster with no manifest entry. Findings only; a page that is "
               "present and right says nothing. Exit 1 on any finding")
    refs_arg(p, all_="every page the manifest holds")
    add_jobs(p)

    p = action(g, "space", run_space, section="What the rasters are",
               help="which coordinate space each store's pages declare, read "
               "from each file's own page box: `master`, the legacy `render`, "
               "or neither. **This one gates, where measurement usually does "
               "not** — the migration into master space is complete and has a "
               "receipt, so a page still declaring the old box will silently "
               "mis-place every coordinate on it, and reporting that at exit 0 "
               "would file a fault as a fact. Walks the six coordinate stores; "
               "the `ocr/` and `zones/` views are absent on purpose, a view "
               "being two stores' answer under one name. Exit 1 on any page "
               "not in master space")
    refs_arg(p, all_="every page of every coordinate store")
    add_jobs(p)


# --- Building the tree --------------------------------------------------------

def run_extract(a) -> int:
    refs = page_refs(a)
    if refs and (a.commit or a.rasters):
        # A manifest describes the corpus. Written from a handful of refs it would
        # be a file that looks complete and holds nine pages, which is worse than
        # no file — the same reasoning that makes `--all` a flag rather than an
        # omission everywhere else.
        raise ValueError("--commit and --rasters describe the whole corpus: "
                         "use --all, or drop them to report on the refs named")
    rasters = Path(a.rasters) if a.rasters else None
    with render.progress("extract") as tick:
        manifest, records = scans.extract(a.root, refs or None, rasters, tick,
                                          jobs=a.jobs)

    ok = [r for r in records if not r["refuse"]]
    bad = [r for r in records if r["refuse"]]
    photos = sum(len(r["images"]) for r in ok)
    summary = {
        "pages": len(records),
        "bitonal": sum(1 for r in ok
                       if not r["images"] and not (r["master"] or {}).get("rendered")),
        "composite": sum(1 for r in ok if r["images"]),
        "rendered": sum(1 for r in ok if (r["master"] or {}).get("rendered")),
        "photographs": photos,
        "refused": len(bad),
        "manifest": "", "rasters": str(rasters) if rasters else "",
    }
    if a.commit:
        scans.write_manifest(manifest, a.root / scans.PDF_IMAGES)
        summary["manifest"] = scans.PDF_IMAGES
    if rasters is not None:
        # The cut tree carries the geometry it was cut at, whether or not the
        # tracked manifest was written. That is what makes `swap` able to say what
        # space a directory of PNGs is in.
        scans.write_manifest(manifest, rasters / scans.TREE_MANIFEST)

    out(a, summary, name="extract")
    if bad:
        out(a, [{"ref": r["ref"], "why": r["refuse"]} for r in bad],
            name="refused", heading=True)
    return verdict(a, 1 if bad else 0,
                   "a page was refused rather than turned into something "
                   "plausible" if bad else "every page read")


def run_swap(a) -> int:
    rep = scans.swap(Path(a.tree), a.root, commit=a.commit)
    out(a, rep["swap"], name="swap")
    if rep["shifts"]:
        out(a, rep["shifts"], name="shifts", heading=True)
    if rep.get("stores"):
        out(a, rep["stores"], name="stores", heading=True)
    out(a, rep["dependents"], name="dependents", heading=True)
    out(a, rep["touched_up"], name="touched_up", heading=True)
    if rep["refusals"]:
        out(a, rep["refusals"], name="refusals", heading=True)
    sw = rep["swap"]
    # The exit line says what would happen, not merely that something might. A
    # `--commit swaps` that swaps nothing and one that rewrites 3000 coordinates
    # read identically, and the second is the one worth pausing over.
    would = (f"--commit would install {sw.get('rasters', 0)} rasters, "
             f"shift {sw.get('pages_shifted', 0)} pages, rewrite "
             f"{sw.get('files_changing', 0)} stored files and discard "
             f"{sw.get('files_discarded', 0)} derived ones")
    return verdict(a, 1 if rep["refusals"] else 0,
                   "refused; nothing moved" if rep["refusals"]
                   else "swapped" if a.commit else would)


# --- What the rasters are -----------------------------------------------------

def _scope(a) -> list[str]:
    """The refs named, or every page the manifest holds."""
    return page_refs(a) or sorted(scans.pdf_images(a.root))


def run_info(a) -> int:
    refs = _scope(a)
    with render.progress("info") as tick:
        rows = scans.info(refs, a.root, tick, jobs=a.jobs)
    out(a, rows, name="info")
    ph = scans.photos(refs, a.root)
    if ph:
        out(a, ph, name="photos", heading=True)
    return 0


def run_census(a) -> int:
    with render.progress("census") as tick:
        r = scans.census(page_refs(a) or None, a.root, tick, jobs=a.jobs)
    out(a, r["census"], name="census")
    out(a, r["classes"], name="classes", heading=True)
    return 0


def run_audit(a) -> int:
    with render.progress("audit") as tick:
        findings = scans.audit(page_refs(a) or None, a.root, tick=tick, jobs=a.jobs)
    # **`gates` is a column, not a filter.** A source PDF this machine cannot see
    # and a raster cut before the provenance chunk existed are both worth saying and
    # neither is a disagreement — every worktree has dangling `pdfs/` links, and an
    # audit that failed there is an audit people learn to run with `|| true`.
    gating = [f for f in findings if f["gates"]]
    out(a, {"checked": len(_scope(a)), "findings": len(findings),
            "gating": len(gating)}, name="audit")
    if findings:
        out(a, findings, name="findings", heading=True)
    return verdict(a, 1 if gating else 0,
                   "the tree and the manifest disagree" if gating
                   else "every page present, sized and moded as recorded")


def run_space(a) -> int:
    with render.progress("space") as tick:
        rows = scans.space(page_refs(a) or None, a.root, tick, jobs=a.jobs)
    wrong = [r for r in rows if r["space"] != "master"]
    by_space: dict[str, int] = {}
    for r in rows:
        by_space[r["space"]] = by_space.get(r["space"], 0) + 1
    out(a, {"files": len(rows), **by_space}, name="space")
    if wrong:
        out(a, wrong, name="not_master", heading=True)
    return verdict(a, 1 if wrong else 0,
                   "a store page is not in master space" if wrong
                   else "every store page in master space")
