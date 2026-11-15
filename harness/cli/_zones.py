"""`harness zones` — the seven-type page segmentation, and the segmenter over it.

Two stores, and the split between them is the point:

    gt/zones/     what a human has been through. Tracked.
    mz/zones/     what the model emitted. Derived, ignored.

`--store` picks which of the two an action reads. It is a closed set of two and
deliberately not a free directory path: that is how a check ends up compared
against its own input. There used to be a read view over the pair, the human file
winning; it was never offered here, since checking through it would have blended
ratified and unratified pages under one exit code, and it is gone from the repo.

**gt gates, mz measures.** `check --store mz` runs the same checks and always
exits 0 — nothing there is ratified, and a raw predicted polygon fails the
fixed-measure width check by construction, so gating it would be permanent
known-false noise and would let a machine store block a build.

Writes name `gt/zones/` through `save_zones`, which takes no store argument at
all: there is no parameter in which a caller could name somewhere else. The only
route from `mz/` to `gt/` is a human in the editor.

**The review pass** sits between the two. An agent reads the rule's `mz/zones/`
file and writes `review/PP-NNN/zones.json`, edits against it (`#llm`); the editor
shows them applied, and a save still writes `gt/zones/`. `bands` is what the agent
reads, `verdict` the gate on what it wrote, and `queue`/`claim`/`reconcile` the
dispatch, the reading pass's machinery over a third track.
"""
from __future__ import annotations

import sys

import click

from ..parallel import ptrack
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
MODEL_HELP = "the segmentation model (default models/zones-seg/zones-seg.safetensors)"
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
              "clicks per zone, x taken from config/zones.json and "
              "never from the pointer — plus the segmenter trained on it",
              sections=("The store", "The segmenter", "The review pass"),
              section="The passes")

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
            "page reachable. `/` and `?` cycle the store shown (gt, mz, "
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

    p = action(g, "propose", run_propose, section="The segmenter", help="derive zones by rule off the text layer's rows "
            "(mz/ocr/, as `ocr import` wrote it) into mz/zones/ — the machine "
            "store, never gt/. A rule, not a model: its file says `kind: rule` "
            "and carries every threshold it used. Only a text whose "
            "config/zones.json holds a `text_rule` block can be proposed")
    refs_arg(p, all_="every page marked train or eval",
             extra=". A ruled leaf is skipped even when named: it holds no zone "
                   "file in either store, and a rule has no case to excuse")
    opt(p, "--commit", is_flag=True,
                   help="write mz/zones/; report only otherwise")
    opt(p, "--force", is_flag=True,
                   help="replace a page's existing mz/zones/ file, whichever "
                        "producer wrote it")

    p = action(g, "bands", run_bands, section="The review pass",
               help="one page's mz/zones/ file as the review pass edits it: its "
               "digest and flags, each band numbered with the line indices whose "
               "vertical centre it holds, the lines no band holds, and the declared "
               "types. Read off the file, never re-derived, so it describes the "
               "file a verdict is against. Measurement — exit 0; exit 2 for a page "
               "with no mz/zones/ or mz/ocr/ file")
    refs_arg(p)

    p = action(g, "verdict", run_verdict, section="The review pass",
               help="the gate on review/PP-NNN/zones.json: it must name the rule's "
               "file as it now is, every op must refer to a band or line the file "
               "has, no two ops may conflict, every op says why, and the bands it "
               "yields must pass the zone errors `check` raises. Errors the rule's "
               "own file already carries are reported as inherited and fail "
               "nothing. Exit 1 when any named verdict fails or is missing")
    refs_arg(p, all_="every page holding a review/PP-NNN/zones.json")

    p = action(g, "queue", run_queue, section="The review pass",
               help="validate a batch for the zone review pass, write it to "
               "review/_zones_queue.txt, and print the one prompt every reviewer "
               "gets. Refuses a ruled leaf, a page keyed in gt/zones/, a page with "
               "no rule file or one predating the flags, and a page already holding "
               "a fresh verdict, naming the remedy. Exit 1 on a refusal")
    refs_arg(p, all_="every page whose rule file carries a flag, less those "
                     "refused, which are listed")
    opt(p, "--sample", type=int, default=0,
        help="with --all, add N unflagged pages drawn by --seed: what measures "
             "what the flags miss")
    opt(p, "--seed", type=int, default=0, help="the --sample draw's seed")
    opt(p, "--note", type=str, default=None,
        help="a sentence appended to every page block in this batch")

    action(g, "claim", run_claim, section="The review pass",
           help="take the next unclaimed ref off review/_zones_queue.txt and print "
           "that page's block. Takes no ref, which is the point. Exit 1 when the "
           "queue is out")

    p = action(g, "reconcile", run_reconcile, section="The review pass",
               help="what the batch came back with — each ref reviewed, CLAIMED "
               "but with no verdict, or unclaimed. Exit 1 naming those that "
               "produced nothing")
    refs_arg(p)

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

    p = action(g, "mark", run_mark, section="The store", help="say what each named leaf is — "
            "a text page's split (train, eval) or a leaf kind (plate, blank, "
            "cover, map, apparatus) — the editor's ruling for many leaves at "
            "once, as off a `scans sheet` contact sheet. A leaf kind drops the "
            "page's zone files in both stores, with `.prev` and the journal, "
            "as the editor does")
    from ..zones import SPLITS
    arg(p, "split", type=click.Choice(SPLITS), metavar="SPLIT")
    # No `--all`, for `delete`'s reason: ruling the whole book one kind is not a
    # thing anyone means, and it would clear every keyed page in the store.
    refs_arg(p)
    opt(p, "--commit", is_flag=True,
                   help="actually write the marks; preview otherwise")

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
        from ..paths import all_scans
        itin = all_scans(a.root)
    start = itin[0] if refs else None
    if not start and itin:
        # Resume: the first page on the list nobody has keyed. Falls back to the
        # head of the list once it is finished, so the session still opens.
        # `keyed` is a store read per page, and `--all` makes the itinerary the
        # whole book — so resuming is a sweep before the socket is bound, with
        # nothing on screen to say the session is still coming up.
        #
        # **`keyed`, not `has_zones`**: a leaf ruled `plate` holds no zone file
        # at all, so the file test would call every exempt leaf unsettled and
        # send the resume back to the same plate every session.
        with progress("finding where to resume") as tick:
            splits = zmod.load_splits(a.root)
            start = next((r for r in ptrack(itin, tick)
                          if not zmod.keyed(r, a.root, splits)), itin[0])
    if not start:
        print("zones edit needs a page to start at: name one or more refs, or "
              "--itinerary to take one from, or --all for the whole book",
              file=sys.stderr)
        return 2
    from ..web import Sessions
    from ..web import serve as web

    session = {"start": start, "itinerary": itin,
               "itinerary_name": a.itinerary or ""}
    joined = web.handoff("zones", session, open_at=f"/?ref={start}", port=a.port,
                         root=a.root)
    if joined:
        import webbrowser

        print(f"zones {start} -> {joined}   (joined the running server)")
        webbrowser.open(joined)
        return 0

    banner = [f"zones {start} -> "
              f"{web.url_for('zones', f'/?ref={start}', port=a.port)}"
              "   (Done button on the page, or ctrl-c)"]
    if itin:
        with progress("counting the itinerary") as tick:
            splits = zmod.load_splits(a.root)
            done = sum(1 for r in ptrack(itin, tick)
                       if zmod.keyed(r, a.root, splits))
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


def run_propose(a) -> int:
    from .. import zones_rule
    from ..zones_config import ConfigError

    zmod, _ = _mod()
    refs = page_refs(a)
    if not refs:
        splits = zmod.load_splits(a.root)
        refs = sorted((r for r, s in splits.items() if s in zmod.TEXT_SPLITS),
                      key=zmod.parse_ref)
    try:
        with progress("proposing") as tick:
            rows, unzoned = zones_rule.propose_many(refs, a.root, commit=a.commit,
                                                    force=a.force, tick=tick)
    except ConfigError as e:
        raise click.UsageError(str(e)) from None
    out(a, rows, name="pages")
    if unzoned:
        out(a, unzoned, name="unzoned", heading=True)
    return 0


def run_bands(a) -> int:
    from .. import zones as zmod
    from .. import zones_review as zr
    from .. import zones_rule
    from ..lines import ink_mask
    from ..zones_config import load_config

    cfg = load_config(a.root)
    heads, bands, unbanded, uncovered = [], [], [], []
    for ref in page_refs(a):
        try:
            b = zr.baseline(ref, a.root)
        except zr.Missing as e:
            raise click.UsageError(str(e)) from None
        # Ink no band covers that looks like a line: what the review pass must
        # be shown, since no line index can point at a line the layer lacks.
        if "text_rule" in cfg:
            ink = ink_mask(zmod.scan_for(b["ref"], a.root))
            uncovered += [{"ref": b["ref"], **m} for m in zones_rule.missing_lines(
                b["ref"], b["zones"], a.root, cfg,
                zmod.page_windows(b["ref"], a.root, cfg, ink), ink)]
        heads.append({"ref": b["ref"], "file": b["file"], "sha256": b["sha256"],
                      "bands": len(b["bands"]), "producer": b["producer"],
                      "version": b["version"],
                      "flags": "(predates flags)" if b["flags"] is None
                      else b["flags"] or "none"})
        bands += [{"ref": b["ref"], **r} for r in b["bands"]]
        unbanded += [{"ref": b["ref"], **r} for r in b["unbanded"]]
    out(a, heads, name="files")
    out(a, bands, name="bands", heading=True)
    if unbanded:
        out(a, unbanded, name="unbanded", heading=True)
    if uncovered:
        out(a, uncovered, name="uncovered", heading=True)
    out(a, zr.types_table(cfg), name="types", heading=True)
    return 0


def run_verdict(a) -> int:
    from .. import zones_review as zr
    from ..paths import page_refs_under, verdict_path
    from ..zones_config import load_config
    from ._common import verdict

    refs = page_refs(a)
    if not refs:
        refs = [r for r in page_refs_under(a.root) if verdict_path(r, a.root).exists()]
    cfg = load_config(a.root)
    pages, errors, inherited = [], [], []
    with progress("judging") as tick:
        recs = [zr.issues(ref, a.root, cfg) for ref in ptrack(refs, tick)]
    for rec in recs:
        v = rec["verdict"] or {}
        got = rec["zones"]
        pages.append({"ref": rec["ref"], "edits": len(v.get("edits") or []),
                      "notes": len(v.get("notes") or []),
                      "errors": len(rec["errors"]),
                      "labels": " ".join(z["label"] for z in got) if got else ""})
        errors += [{"ref": rec["ref"], **e} for e in rec["errors"]]
        inherited += [{"ref": rec["ref"], **e} for e in rec["inherited"]]
    out(a, pages, name="pages")
    if errors:
        out(a, errors, name="errors", heading=True)
    if inherited:
        out(a, inherited, name="inherited", heading=True)
    bad = sorted({e["ref"] for e in errors})
    if bad:
        return verdict(a, 1, f"{len(bad)} of {len(refs)} verdicts fail: "
                             f"{', '.join(bad)}")
    return verdict(a, 0, f"{len(refs)} verdicts pass")


def _flagged(a) -> list[str]:
    """`queue --all`: the flagged pages, plus `--sample` unflagged ones by seed."""
    import random

    from .. import provenance
    zmod, _ = _mod()
    flagged, plain = [], []
    for ref in zmod.zone_refs(a.root, zmod.MZDIR):
        p = provenance.read_producer(zmod.alto_for(ref, a.root, zmod.MZDIR))
        f = p.inputs.get("flags") if p else None
        if f is None:
            continue           # predates the flags, or not the rule's file
        (flagged if f else plain).append(ref)
    rng = random.Random(a.seed)
    extra = rng.sample(plain, min(a.sample, len(plain)))
    return sorted(flagged + extra, key=zmod.parse_ref)


def run_queue(a) -> int:
    from ..dispatch import ZONING, Unready, queue_refs, zoning_build

    refs = page_refs(a)
    if a.sample and refs:
        raise click.UsageError("--sample draws beside --all and means nothing alone")
    if not refs:
        # A refused page is left out of an --all batch rather than failing it:
        # the selection is the tool's, so the refusal is too. Named refs refuse.
        refs, left = [], []
        with progress("selecting") as tick:
            for r in ptrack(_flagged(a), tick):
                try:
                    zoning_build(r, a.root)
                    refs.append(r)
                except Unready as e:
                    left.append({"ref": r, "why": str(e)})
        if left:
            out(a, left, name="left_out", heading=True)
        if not refs:
            raise click.ClickException("nothing to queue: every flagged page was "
                                       "refused")
    try:
        rec = queue_refs(refs, a.root, note=a.note, track=ZONING)
    except Unready as e:
        raise click.ClickException(str(e)) from None
    if getattr(a, "json", False):
        out(a, [rec])
        return 0
    click.echo(rec["prompt"])
    if rec["resynced"]:
        click.echo(f"\nthe reviewer's transcluded contract was out of date and has "
                   f"been rewritten from {', '.join(rec['resynced'])}. The agent "
                   "file is tracked; commit it.", err=True)
    n = len(rec["queued"])
    click.echo(f"\n{n} queued: {', '.join(rec['queued'])}. Send that prompt "
               f"unedited and identical to each of {-(-n // 8)} reviewers, "
               "staggering the first launch about ten seconds.", err=True)
    return 0


def run_claim(a) -> int:
    from ..dispatch import ZONING, claim
    rec = claim(a.root, ZONING)
    if rec is None:
        click.echo("nothing left to claim — the queue is empty or every ref on it "
                   "is taken. Stop and say so; do not pick a page yourself.",
                   err=True)
        return 1
    if getattr(a, "json", False):
        out(a, [rec])
    else:
        click.echo(rec["page_block"])
    return 0


def run_reconcile(a) -> int:
    from ..dispatch import ZONING, reconcile
    rows = reconcile(page_refs(a), a.root, ZONING)
    out(a, rows, name="refs")
    missing = [r["ref"] for r in rows if r["state"] != ZONING.done]
    if missing:
        click.echo(f"{len(missing)} of {len(rows)} came back with no verdict: "
                   f"{', '.join(missing)}. `zones verdict` judges the rest.", err=True)
        return 1
    return 0


def run_score(a) -> int:
    zmod, _ = _mod()
    # `"scoring"`, not `"segmenting"`: `predict` owns that word above, and with a
    # `--model` these two do the same work for opposite reasons. The bar closes
    # before anything is printed — a table written into a live transient bar is
    # what strands the frame.
    with progress("scoring") as tick:
        rep = zmod.score(a.root, model_path=a.model, decode=a.decode,
                         device=a.device, tick=tick, jobs=a.jobs)
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
    with progress("measuring departure") as tick:
        dep = zmod.departures(scored, a.root, tick=tick)
    out(a, zmod.departure_composition(dep), "independence")
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
    with progress("assembling") as tick:
        rep = zmod.assemble(a.root, scratch=a.scratch, tick=tick)
    out(a, rep)
    return 1 if rep["missing_blot"] else 0


def run_install(a) -> int:
    zmod, load_config = _mod()
    # Split out of the `out(...)` call it used to sit inside, so the bar is closed
    # before the report is printed.
    with progress("scoring") as tick:
        rep = zmod.install_model(a.checkpoint, a.root, name=a.name,
                                 cfg=load_config(a.root), commit=a.commit,
                                 device=a.device, tick=tick, jobs=a.jobs)
    out(a, rep)
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
    with progress("measuring independence") as tick:
        rep = zmod.remark_eval(a.root, a.fraction, commit=a.commit, tick=tick)
    out(a, rep)
    return 0


def run_delete(a) -> int:
    zmod, _ = _mod()
    with progress("deleting") as tick:
        rows = [(r, zmod.delete_zones(r, a.root, commit=a.commit))
                for r in ptrack(page_refs(a), tick)]
    out_per_ref(a, rows)
    return 0


def run_mark(a) -> int:
    zmod, _ = _mod()
    rows = zmod.mark(page_refs(a), a.split, a.root, commit=a.commit)
    out(a, rows, name="marks")
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
    with progress("diffing zones") as tick:
        rows = [r for ref_ in ptrack(scope, tick)
                for r in zmod.zone_diff(ref_, a.root, cfg)]
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
    with progress("measuring departure") as tick:
        dep = zmod.departures(page_refs(a) or zmod.zone_refs(a.root), a.root,
                              tick=tick)
    out(a, dep, "departure")
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
