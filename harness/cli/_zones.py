"""`harness zones` — the seven-type page segmentation, and the segmenter over it.

Three stores and a view, and the split between them is the point:

    gt/zones/     what a human has been through. Tracked.
    mz/zones/     what the model emitted. Derived, ignored.
    zones/        the read view over both, the human file always winning.

`--store` picks which of the two real stores an action reads. It is a closed set
of two and deliberately not a free directory path, unlike the `ocr` group's
a free path: that is how a check ends up compared against its own input, and
checking through the view would blend ratified and unratified pages under one
exit code. The view is not offered for the same reason.

**gt gates, mz measures.** `check --store mz` runs the same checks and always
exits 0 — nothing there is ratified, and a raw predicted polygon fails the
fixed-measure width check by construction, so gating it would be permanent
known-false noise and would let a machine store block a build.

Writes name `gt/zones/` through `save_zones`, which takes no store argument at
all: there is no parameter in which a caller could name somewhere else. The only
route from `mz/` to `gt/` is a human in the editor.
"""
from __future__ import annotations

import sys

import click

from ..render import progress
from ._common import (
    action,
    add_jobs,
    arg,
    group,
    one_page_only,
    opt,
    out,
    out_per_ref,
    page_refs,
    refs_arg,
)

ITIN_HELP = ("a work-list to walk instead of scan order: an .lst file "
             "(`chukchi-1-019.xml` per line; bare refs and paths also read), or "
             "a directory taken to mean every page file in it, so "
             "`--itinerary gt/zones` walks the whole store and "
             "`--itinerary gt/zones/_train.lst` walks one split. A work-list, "
             "not a filter — a page not on it still opens and still saves, it "
             "simply has no neighbours")
MODEL_HELP = "the segmentation model (default models/bogoras-seg/zones-seg.safetensors)"
DEVICE_HELP = "torch device — 'auto' takes cuda:0 when it is available, else cpu"
DECODE_HELP = (
    "how a prediction becomes zones [dp]. 'dp' decodes the page as a chain of "
    "bands by exact dynamic programming, which makes overlaps and sub-minimum "
    "slivers unrepresentable and merges a fragmented band — the mechanical rules "
    "built in rather than checked afterwards — and then applies the paragraph "
    "split. 'raw' vectorises each class heatmap blob-wise, as kraken does, and is "
    "kept for measuring the model apart from the decoder. The order rules are "
    "deliberately left out of 'dp': they are warnings, and a decoder that could "
    "not break them would make them unfalsifiable. "
    "**The default is 'dp' because the decode matters more than the model has** — "
    "on identical weights, blob vectorisation scores 61.3% precision, the DP "
    "80.1%, and the DP plus the paragraph split 90.8%. It was 'raw', and that made "
    "the 30-point decode the thing you got by leaving an argument off, which is "
    "the hazard `--all` exists to prevent one line further up this file")


def register(cli):
    g = group(cli, "zones", "the seven-type page segmentation in "
              "gt/zones/ — a vertical partition of the text column, two "
              "clicks per zone, x taken from data/zones_config.json and "
              "never from the pointer — plus the segmenter trained on it",
              sections=("The store", "The segmenter"), section="The passes")

    def store_flag(p):
        return opt(p, "--store", type=click.Choice(("gt", "mz")), default="gt",
                   help="which store to read: 'gt' (default) is the human one "
                        "and errors set the exit code; 'mz' is the machine "
                        "one and is measurement — it always exits 0. A closed "
                        "set of two rather than a free directory, and the "
                        "view is deliberately not offered")

    p = store_flag(action(g, "check", run_check, section="The store", help="the gate. Named pages give their errors "
                   "and warnings in full; --all sweeps every keyed page. "
                   "Errors are mechanical (a width no column offers, two zones on "
                   "top of each other) and set the exit code; the ordering "
                   "assumptions are warnings, configurable and exemptible, "
                   "because a page that breaks them is the interesting page "
                   "rather than the rejected one"))
    refs_arg(p, all_="every page the store holds")
    add_jobs(p)
    opt(p, "--itinerary", metavar="LST", default=None,
                   help=f"scope the sweep to a work-list. {ITIN_HELP}")
    opt(p, "--ink", is_flag=True,
                   help="SWEEP ONLY: also read every raster and report ink no "
                        "zone accounts for. Off by default because it costs "
                        "~0.20 s a page against ~1 ms for the file-level checks. "
                        "Always on for named pages, however many — naming two "
                        "must not quietly buy a weaker check than naming one — "
                        "where it is what catches a dropped zone")
    opt(p, "--lines", is_flag=True,
                   help="SINGLE PAGE ONLY: every zone's lines of type — 1-based "
                        "zone and line, y, height, indent against the page's own "
                        "body margin, width. `h` is the tell for the two "
                        "line-detection failures: ~6 px is a speck that passed "
                        "the floor, ~100 px is two lines a descender welded. Off "
                        "by default: it is only wanted when something inside a "
                        "zone is in question, and it costs a second raster decode")

    p = action(g, "edit", run_edit, section="The store", pageable=False, help="open the segmentation editor on 127.0.0.1 and keep "
            "serving — the session steps through pages with the arrow keys and "
            "saves into gt/zones/, so the ref is where to start, not the only "
            "page reachable. `/` and `?` cycle the store shown (view, gt, mz, "
            "paras); a machine page opens as an unsaved proposal and promoting it "
            "takes an edit or an explicit save")
    refs_arg(p, all_="every scan, in order",
             extra=", and several *are* an itinerary: the session opens at the "
                   "first and walks the list. One ref is a page to start at, not "
                   "the only page reachable")
    opt(p, "--itinerary", metavar="LST", default=None, help=ITIN_HELP)
    opt(p, "--port", type=int, default=8732,
                   help="port (default 8732; `ocr review` holds 8731, so "
                        "both can run at once)")

    p = action(g, "predict", run_predict, section="The segmenter", help="run the trained segmenter and write raw ALTO into "
            "mz/zones/ — the machine store, never gt/. Input is always the "
            "blotted raster, since that is what the model was trained on. A page "
            "that already has a prediction is left alone unless --force, so a "
            "sweep is resumable and a retrain cannot silently replace the model "
            "sha each file records")
    refs_arg(p, all_="every page with a blotted raster",
             extra=". An exempt mark does not stop a named page — naming it is "
                   "the request — and several go through one process, the model "
                   "loading once")
    opt(p, "--itinerary", metavar="LST", default=None,
                   help=f"predict over a work-list. {ITIN_HELP}")
    opt(p, "--force", is_flag=True,
                   help="re-run over pages that already have a prediction. What "
                        "you want after installing a new model, and only then — "
                        "the mz file's sha256 is the store's only witness to "
                        "which model wrote it")
    opt(p, "--model", default=None, help=MODEL_HELP)
    opt(p, "--decode", type=click.Choice(("raw", "dp")), default="dp",
                   help=DECODE_HELP)
    opt(p, "--device", default="auto", help=DEVICE_HELP)

    p = action(g, "score", run_score, section="The segmenter", help="compare predictions against gt/zones/ — recall and "
            "precision per split, never blended, plus the confusion matrix and a "
            "held-out permutation test. Bare, it scores what is in mz/zones/; "
            "with --model it segments in memory and writes nothing, which is how "
            "a checkpoint gets measured before it is installed. Refuses if the "
            "frozen split lists are gone: the live ones move, so without them the "
            "training pages cannot be told from the rest. Measurement — exit 0")
    opt(p, "--model", default=None,
                   help=f"{MODEL_HELP}. Given, the checkpoint is segmented in "
                        "memory rather than read out of mz/zones/")
    opt(p, "--decode", type=click.Choice(("raw", "dp")), default="dp",
                   help=DECODE_HELP)
    opt(p, "--device", default="auto", help=DEVICE_HELP)

    p = action(g, "assemble", run_assemble, section="The segmenter", help="build train/bogoras-seg/ from the train/eval marks: "
            "each page's zone ALTO beside its blotted raster, ready for ketos "
            "segtrain. Reports the invocation; runs nothing. Pure scratch — the "
            "split a model trained on travels in that model's own manifest, so "
            "this may be clobbered freely")
    opt(p, "--scratch", is_flag=True,
                   help="train from random init: no -i, kraken's default "
                        "segmentation spec. The one configuration in which the "
                        "class-map permutation cannot arise, there being no "
                        "output layer to renumber")

    p = action(g, "install", run_install, section="The segmenter", help="install a trained checkpoint into models/bogoras-seg/ "
            "with a manifest beside it. Scores it in memory first and **refuses a "
            "permuted class map** — that check stops being something to remember "
            "and becomes a precondition of the artifact existing. The manifest "
            "records the split it trained on, its classes and merges, a digest of "
            "gt/zones/ at the time, and the score; every path in it is relative")
    arg(p, "checkpoint", metavar="CHECKPOINT")
    p.help += "\n\nCHECKPOINT: the .ckpt or .safetensors a training run wrote."
    opt(p, "--name", default="zones-seg",
                   help="installed model name (default zones-seg). The accuracy "
                        "stays out of it: a default path that changes every "
                        "retrain is a default nobody can use")
    opt(p, "--device", default="auto", help=DEVICE_HELP)
    opt(p, "--commit", is_flag=True,
                   help="copy the checkpoint and its split into "
                        "models/bogoras-seg/; preview otherwise")

    p = action(g, "remap", run_remap, section="The segmenter", help="put the learned names back on the model's output "
            "channels, when `score` shows the disagreement is a consistent "
            "relabelling rather than a weak model. Derives the map on the "
            "training pages, refuses unless it is 1-1 and holds out; the original "
            "is kept as .bak")
    opt(p, "--model", default=None, help=MODEL_HELP)
    opt(p, "--commit", is_flag=True,
                   help="rewrite the model's class map; preview otherwise")

    p = action(g, "remark-eval", run_remark_eval, section="The segmenter", help="move a fraction of the train set into eval — "
            "stratified per part, independent pages first, spread rather than "
            "taken off the front. Additive: a page a human already marked eval or "
            "exempt is never touched")
    arg(p, "fraction", metavar="FRACTION", type=float)
    p.help += "\n\nFRACTION: fraction of train to move, e.g. 0.20."
    opt(p, "--commit", is_flag=True,
                   help="write the split marks; report otherwise")

    p = action(g, "delete", run_delete, section="The store", help="un-key a page — remove its file from gt/zones/ and "
            "every mark that referred to it (split, rule and ink exemptions). The "
            "one thing the store could not express: `save_zones` refuses an empty "
            "save, so a page keyed in error could be corrected but not withdrawn. "
            "Keeps `.prev` and records the act in the journal")
    # **No `--all`, and this is the one place the absence is a safety property
    # rather than a cost.** "Un-key the whole ground-truth store" must not be one
    # flag away from a command someone types. `ocr clean` has `--all` precisely
    # because it deletes only derived output; this deletes authored work.
    refs_arg(p)
    opt(p, "--commit", is_flag=True,
                   help="actually remove; preview otherwise")

    p = action(g, "diff", run_diff, section="The store", help="what differs between gt/zones/ and mz/zones/ — paired "
            "by vertical overlap, reported as only_in_gt (a missed region), "
            "only_in_mz (an invented one), label (paired but named differently) "
            "or edge (same region, cut elsewhere, beyond min_zone_h_px). "
            "Measurement — exit 0")
    refs_arg(p, all_="every page present in both stores")

    p = action(g, "paragraphs", run_paragraphs, section="The store", help="audit the paragraph-boundary rule, both "
            "directions. `false_negative` = a boundary gt asserts that the rule "
            "would not recover, which is a trustworthy recall figure; "
            "`false_positive` = the rule firing inside a zone, a worklist and NOT "
            "a precision figure, since each is either a keying slip or a false "
            "alarm and gt cannot arbitrate. The segmenter cannot do this check at "
            "all: two abutting MainZone-P rectangles rasterize to one target. "
            "Measurement — exit 0")
    refs_arg(p, all_="every keyed page")
    add_jobs(p)
    opt(p, "--itinerary", metavar="LST", default=None, help=ITIN_HELP)

    p = action(g, "blot", run_blot, section="The store", help="write the figure-blotted raster the segmenter trains "
            "on — gt/fig/ zones painted **white**, so paragraph wrap around an "
            "illustration cannot shape what the model learns about zone geometry. "
            "Distinct from `ocr blot`, which paints lines and figures in "
            "conspicuous colours for a human to read; this one has to look like "
            "blank paper. The declared box is painted and not a pixel more")
    # **No mtime skip under `--all`, because skip policy here is undecided** — it
    # waits on the dependency graph, which is its own sprint. Not because a stale
    # blot is undetectable: `zones.blot_all` records what an mtime test can and
    # cannot see, and a corrected figure ALTO is one of the things it can.
    refs_arg(p, all_="all 832 scans")
    add_jobs(p)


def _mod():
    from .. import zones as zmod
    from ..zones_config import load_config
    return zmod, load_config


def _itin(a, zmod):
    return (zmod.load_itinerary(a.itinerary, a.root)
            if getattr(a, "itinerary", None) else None)


def run_check(a) -> int:
    zmod, load_config = _mod()
    store = {"gt": zmod.ZONEDIR, "mz": zmod.MZDIR}[a.store]
    cfg = load_config(a.root)
    refs = page_refs(a)
    if refs:
        # `--lines` is the page's own zone-by-zone breakdown, so it names one page
        # in the same way `ocr zoom --only` does.
        one_page_only(a, {"lines": "--lines"}, refs)
        # **Named pages always ink-check, however many.** The flag is a sweep
        # economy — ~0.20 s a page against ~1 ms — and naming two pages must not
        # quietly buy a weaker check than naming one, since this is the only check
        # that can see a *missing* zone.
        reps = [(r, zmod.validate_page(r, a.root, cfg, ink=True, store=store))
                for r in refs]
        # `errors`, `warnings` and `uncovered` are lists, so pooling puts their
        # counts in the row and each gets its own ref-keyed table.
        out_per_ref(a, reps)
        rows = [(r, zmod.page_zone_lines(r, a.root, cfg, store=store) if a.lines
                 else zmod.page_zones_table(r, a.root, store=store))
                for r in refs]
        if any(v for _, v in rows):
            out_per_ref(a, rows, "lines" if a.lines else "zones")
        bad = any(rep["errors"] for _, rep in reps)
        return 1 if (bad and store == zmod.ZONEDIR) else 0
    with progress("checking zones") as tick:
        summary, rows = zmod.validate_corpus(a.root, cfg, ink=a.ink,
                                             refs=_itin(a, zmod), store=store,
                                             jobs=a.jobs, tick=tick)
    out(a, summary)
    if rows:
        out(a, rows, "pages")
    return 1 if (summary["errors"] and store == zmod.ZONEDIR) else 0


def run_edit(a) -> int:
    zmod, _ = _mod()
    refs = page_refs(a)
    # **Several refs *are* an itinerary.** The editor already walks a list with
    # the arrow keys, so a typed list needs no new machinery — it is the same
    # work-list an `.lst` supplies, spelled for the two-page case that would
    # otherwise want a scratch file. `--all` walks the book.
    itin = refs or _itin(a, zmod)
    if getattr(a, "all", False):
        from ..context import all_scans
        itin = all_scans(a.root)
    start = itin[0] if refs else None
    if not start and itin:
        # Resume: the first page on the list nobody has keyed. Falls back to the
        # head of the list once it is finished, so the session still opens.
        start = next((r for r in itin if not zmod.has_zones(r, a.root)), itin[0])
    if not start:
        print("zones edit needs a page to start at: name one or more refs, or "
              "--itinerary to take one from, or --all for the whole book",
              file=sys.stderr)
        return 2
    from ..web import Sessions
    from ..web import serve as web

    session = {"start": start, "itinerary": itin,
               "itinerary_name": a.itinerary or ""}
    joined = web.handoff("zones", session, open_at=f"/?ref={start}", port=a.port)
    if joined:
        import webbrowser

        print(f"zones {start} -> {joined}   (joined the running server)")
        webbrowser.open(joined)
        return 0

    banner = [f"zones {start} -> "
              f"{web.url_for('zones', f'/?ref={start}', port=a.port)}"
              "   (Done button on the page, or ctrl-c)"]
    if itin:
        done = sum(1 for r in itin if zmod.has_zones(r, a.root))
        banner.append(
            f"itinerary {a.itinerary or ''}: {len(itin)} pages, {done} keyed")
    banner.append(f"store -> {zmod.zone_dir(a.root)}")
    web.serve("zones", a.root, Sessions(root=a.root, by_editor={"zones": session}),
              banner=banner, open_at=f"/?ref={start}",
              ports={"zones": a.port} if a.port else None)
    return 0


def run_predict(a) -> int:
    zmod, _ = _mod()
    model = a.model or zmod.DEFAULT_MODEL
    named = page_refs(a)
    if len(named) == 1:
        # One named page still overrides the exempt skip — naming it is the
        # request — but it no longer bypasses the skip entirely. It used to, so a
        # named ref silently overwrote an existing prediction along with the
        # model sha that file records, which is the one witness in the store to
        # which model spoke. `--force` is how a re-prediction says it meant it.
        ref = named[0]
        why = zmod.predict_skip(ref, a.root, force=a.force, single=True)
        if why:
            out(a, {"ref": ref, "predicted": 0, "skipped": why})
            return 0
        net, sha = zmod.load_segmenter(model, a.root)
        fn = zmod.predict_dp if a.decode == "dp" else zmod.predict
        out(a, fn(ref, a.root, net=net, sha=sha, model_path=model,
                  device=a.device))
        return 0
    # Several named refs go through the sweep — the model loads once — carrying
    # `named` so the single-page override travels with them. Without it a page a
    # human ruled exempt would be skipped in silence by the command that named it.
    with progress("segmenting") as tick:
        rep = zmod.predict_all(a.root, refs=named or _itin(a, zmod),
                               model_path=model, device=a.device,
                               decode=a.decode, force=a.force,
                               named=bool(named), tick=tick)
    out(a, rep)
    # Same contract as `assemble`'s missing_blot: a page the model was asked
    # about and could not be shown is a gap in the run, not a quiet omission.
    return 1 if rep["skipped_no_blot"] else 0


def run_score(a) -> int:
    zmod, _ = _mod()
    rep = zmod.score(a.root, model_path=a.model, decode=a.decode, device=a.device)
    conf = rep.pop("confusion")
    scored = rep.pop("scored_refs")
    out(a, rep)
    out(a, conf)
    # **What each split is made of, beside what the model scored on it.** A recall
    # figure over a held-out set half of which is the model's own segmentation with
    # the edges pulled straight measures how well the model agrees with itself, and
    # the number cannot say so. `_independent` has been the rule `remark-eval`
    # selects on since the set was drawn; this is the first thing to report it, so
    # the qualifier travels with the figure instead of expiring at selection time.
    out(a, zmod.departure_composition(zmod.departures(scored, a.root)),
        "independence")
    # A consistent relabelling is a different fault from a weak model and has a
    # different remedy, so it does not get to hide in a table.
    p = rep["permutation"]
    if p["bijective"] and not p["is_identity"] and p["holds_out"] >= 90:
        print(f"\nRELABELLING, not a weak model: a 1-1 map derived on the "
              f"training pages predicts {p['holds_out']}% of the held-out zones. "
              f"The geometry was learned; the names on the output channels are "
              f"wrong. `harness zones remap --commit` renames them.",
              file=sys.stderr)
    return 0


def run_assemble(a) -> int:
    zmod, _ = _mod()
    rep = zmod.assemble(a.root, scratch=a.scratch)
    out(a, rep)
    return 1 if rep["missing_blot"] else 0


def run_install(a) -> int:
    zmod, load_config = _mod()
    out(a, zmod.install_model(a.checkpoint, a.root, name=a.name,
                              cfg=load_config(a.root), commit=a.commit,
                              device=a.device))
    return 0


def run_remap(a) -> int:
    zmod, _ = _mod()
    rep = zmod.remap_model(a.root, a.model or zmod.DEFAULT_MODEL, commit=a.commit)
    ch = rep.pop("channels")
    out(a, rep)
    out(a, ch)
    return 0


def run_remark_eval(a) -> int:
    zmod, _ = _mod()
    out(a, zmod.remark_eval(a.root, a.fraction, commit=a.commit))
    return 0


def run_delete(a) -> int:
    zmod, _ = _mod()
    out_per_ref(a, [(r, zmod.delete_zones(r, a.root, commit=a.commit))
                    for r in page_refs(a)])
    return 0


def run_diff(a) -> int:
    from collections import Counter
    zmod, load_config = _mod()
    cfg = load_config(a.root)
    # An aggregate: refs scope it and do not multiply it — the summary is over
    # whatever was named, and the rows already carry `ref`.
    scope = page_refs(a) or sorted(
        set(zmod.zone_refs(a.root)) & set(zmod.zone_refs(a.root, zmod.MZDIR)),
        key=zmod.parse_ref)
    rows = [r for ref_ in scope for r in zmod.zone_diff(ref_, a.root, cfg)]
    out(a, {"pages": len(scope), "differences": len(rows),
            "pages_differing": len({r["ref"] for r in rows}),
            "by_kind": " ".join(f"{k}:{v}" for k, v in
                                sorted(Counter(r["kind"] for r in rows).items()))})
    if rows:
        out(a, rows, "differences")
    # Per-page departure, which is a different question from the zone-level rows
    # above: not *what* differs but **how far the human went beyond the model** —
    # the scale `_independent` reads and, until now, the only thing in this
    # package computed by a private function and reported by nothing.
    #
    # **Its scope is the keyed store, not the intersection the rows above use.**
    # `no prediction` is the strongest independence claim in the table, and a
    # report that only visits pages which *have* a prediction can never emit it —
    # a column reporting coverage it does not have, which is the trap `LOOKALIKES`
    # already paid for once with U+0121. So the counts differ between the two
    # sections by exactly the pages nothing predicted, and that is the point.
    out(a, zmod.departures(page_refs(a) or zmod.zone_refs(a.root), a.root),
        "departure")
    return 0


def run_paragraphs(a) -> int:
    zmod, load_config = _mod()
    scope = page_refs(a) or _itin(a, zmod)
    with progress("auditing paragraphs") as tick:
        summary, rows = zmod.paragraph_audit(a.root, load_config(a.root),
                                             refs=scope, jobs=a.jobs, tick=tick)
    out(a, summary)
    if rows:
        out(a, rows, "boundaries")
    return 0


def run_blot(a) -> int:
    zmod, _ = _mod()
    refs = page_refs(a)
    # No mtime skip under `--all`, deliberately — see the registration.
    if refs:
        from ..parallel import pmap
        with progress("blotting") as tick:
            done = pmap(lambda r: zmod.blot_one(r, a.root), refs, a.jobs, tick)
        out_per_ref(a, list(zip(refs, done, strict=True)))
    else:
        with progress("blotting") as tick:
            rep = zmod.blot_all(a.root, jobs=a.jobs, tick=tick)
        out(a, rep)
    return 0
