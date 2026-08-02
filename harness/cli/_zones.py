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

from ._common import REF_HELP, out

ITIN_HELP = ("a work-list to walk instead of scan order: an .lst file in gt/seg's "
             "format, or a directory taken to mean every page file in it (so "
             "`--itinerary gt/seg` is that whole selection, chosen for "
             "heterogeneity). A work-list, not a filter — a page not on it still "
             "opens and still saves, it simply has no neighbours")
MODEL_HELP = "the segmentation model (default models/bogoras-seg/zones-seg.safetensors)"
DEVICE_HELP = "torch device — 'auto' takes cuda:0 when it is available, else cpu"
DECODE_HELP = (
    "how a prediction becomes zones. 'raw' vectorises each class heatmap "
    "blob-wise, as kraken does. 'dp' decodes the page as a chain of bands by "
    "exact dynamic programming, which makes overlaps and sub-minimum slivers "
    "unrepresentable and merges a fragmented band — the mechanical rules built "
    "in rather than checked afterwards. The order rules are deliberately left "
    "out: they are warnings, and a decoder that could not break them would make "
    "them unfalsifiable")


def register(sub, common):
    g = sub.add_parser("zones", help="the seven-type page segmentation in "
                       "gt/zones/ — a vertical partition of the text column, two "
                       "clicks per zone, x taken from data/zones_config.json and "
                       "never from the pointer — plus the segmenter trained on it")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    def store_flag(p):
        p.add_argument("--store", choices=("gt", "mz"), default="gt",
                       help="which store to read: 'gt' (default) is the human one "
                            "and errors set the exit code; 'mz' is the machine "
                            "one and is measurement — it always exits 0. A closed "
                            "set of two rather than a free directory, and the "
                            "view is deliberately not offered")
        return p

    p = store_flag(add("check", help="the gate. With a ref, that page's errors "
                   "and warnings in full; bare, a sweep of every keyed page. "
                   "Errors are mechanical (a width no column offers, two zones on "
                   "top of each other) and set the exit code; the ordering "
                   "assumptions are warnings, configurable and exemptible, "
                   "because a page that breaks them is the interesting page "
                   "rather than the rejected one"))
    p.add_argument("ref", metavar="PP-NNN", nargs="?",
                   help="page ref, e.g. 1-048. Omit to sweep the whole store")
    p.add_argument("--itinerary", metavar="LST", default=None,
                   help=f"scope the sweep to a work-list. {ITIN_HELP}")
    p.add_argument("--ink", action="store_true",
                   help="SWEEP ONLY: also read every raster and report ink no "
                        "zone accounts for. Off by default because it costs "
                        "~0.20 s a page against ~1 ms for the file-level checks. "
                        "Always on for a single page, where it is the check that "
                        "catches a dropped zone, so it is not a flag there")
    p.add_argument("--lines", action="store_true",
                   help="SINGLE PAGE ONLY: every zone's lines of type — 1-based "
                        "zone and line, y, height, indent against the page's own "
                        "body margin, width. `h` is the tell for the two "
                        "line-detection failures: ~6 px is a speck that passed "
                        "the floor, ~100 px is two lines a descender welded. Off "
                        "by default: it is only wanted when something inside a "
                        "zone is in question, and it costs a second raster decode")
    p.set_defaults(func=run_check)

    p = add("edit", help="open the segmentation editor on 127.0.0.1 and keep "
            "serving — the session steps through pages with the arrow keys and "
            "saves into gt/zones/, so the ref is where to start, not the only "
            "page reachable. `/` and `?` cycle the store shown (view, gt, mz, "
            "paras); a machine page opens as an unsaved proposal and promoting it "
            "takes an edit or an explicit save")
    p.add_argument("ref", metavar="PP-NNN", nargs="?",
                   help="page to open at. Omit with --itinerary to resume at the "
                        "first page on the list nobody has keyed")
    p.add_argument("--itinerary", metavar="LST", default=None, help=ITIN_HELP)
    p.add_argument("--port", type=int, default=8732,
                   help="port (default 8732; `ocr review --serve` holds 8731, so "
                        "both can run at once)")
    p.set_defaults(func=run_edit)

    p = add("predict", help="run the trained segmenter and write raw ALTO into "
            "mz/zones/ — the machine store, never gt/. Input is always the "
            "blotted raster, since that is what the model was trained on. A page "
            "that already has a prediction is left alone unless --force, so a "
            "sweep is resumable and a retrain cannot silently replace the model "
            "sha each file records")
    p.add_argument("ref", metavar="PP-NNN", nargs="?",
                   help="one page. An exempt mark does not stop it — naming a "
                        "page is the request. Omit to sweep")
    p.add_argument("--itinerary", metavar="LST", default=None,
                   help=f"predict over a work-list. {ITIN_HELP}")
    p.add_argument("--force", action="store_true",
                   help="re-run over pages that already have a prediction. What "
                        "you want after installing a new model, and only then — "
                        "the mz file's sha256 is the store's only witness to "
                        "which model wrote it")
    p.add_argument("--model", default=None, help=MODEL_HELP)
    p.add_argument("--decode", choices=("raw", "dp"), default="raw",
                   help=DECODE_HELP)
    p.add_argument("--device", default="auto", help=DEVICE_HELP)
    p.set_defaults(func=run_predict)

    p = add("score", help="compare predictions against gt/zones/ — recall and "
            "precision per split, never blended, plus the confusion matrix and a "
            "held-out permutation test. Bare, it scores what is in mz/zones/; "
            "with --model it segments in memory and writes nothing, which is how "
            "a checkpoint gets measured before it is installed. Refuses if the "
            "frozen split lists are gone: the live ones move, so without them the "
            "training pages cannot be told from the rest. Measurement — exit 0")
    p.add_argument("--model", default=None,
                   help=f"{MODEL_HELP}. Given, the checkpoint is segmented in "
                        "memory rather than read out of mz/zones/")
    p.add_argument("--decode", choices=("raw", "dp"), default="raw",
                   help=DECODE_HELP)
    p.add_argument("--device", default="auto", help=DEVICE_HELP)
    p.set_defaults(func=run_score)

    p = add("assemble", help="build train/bogoras-seg/ from the train/eval marks: "
            "each page's zone ALTO beside its blotted raster, ready for ketos "
            "segtrain. Reports the invocation; runs nothing. Pure scratch — the "
            "split a model trained on travels in that model's own manifest, so "
            "this may be clobbered freely")
    p.add_argument("--scratch", action="store_true",
                   help="train from random init: no -i, kraken's default "
                        "segmentation spec. The one configuration in which the "
                        "class-map permutation cannot arise, there being no "
                        "output layer to renumber")
    p.set_defaults(func=run_assemble)

    p = add("install", help="install a trained checkpoint into models/bogoras-seg/ "
            "with a manifest beside it. Scores it in memory first and **refuses a "
            "permuted class map** — that check stops being something to remember "
            "and becomes a precondition of the artifact existing. The manifest "
            "records the split it trained on, its classes and merges, a digest of "
            "gt/zones/ at the time, and the score; every path in it is relative")
    p.add_argument("checkpoint", metavar="CHECKPOINT",
                   help="the .ckpt or .safetensors a training run wrote")
    p.add_argument("--name", default="zones-seg",
                   help="installed model name (default zones-seg). The accuracy "
                        "stays out of it: a default path that changes every "
                        "retrain is a default nobody can use")
    p.add_argument("--device", default="auto", help=DEVICE_HELP)
    p.add_argument("--commit", action="store_true",
                   help="copy the checkpoint and its split into "
                        "models/bogoras-seg/; preview otherwise")
    p.set_defaults(func=run_install)

    p = add("remap", help="put the learned names back on the model's output "
            "channels, when `score` shows the disagreement is a consistent "
            "relabelling rather than a weak model. Derives the map on the "
            "training pages, refuses unless it is 1-1 and holds out; the original "
            "is kept as .bak")
    p.add_argument("--model", default=None, help=MODEL_HELP)
    p.add_argument("--commit", action="store_true",
                   help="rewrite the model's class map; preview otherwise")
    p.set_defaults(func=run_remap)

    p = add("remark-eval", help="move a fraction of the train set into eval — "
            "stratified per part, independent pages first, spread rather than "
            "taken off the front. Additive: a page a human already marked eval or "
            "exempt is never touched")
    p.add_argument("fraction", metavar="FRACTION", type=float,
                   help="fraction of train to move, e.g. 0.20")
    p.add_argument("--commit", action="store_true",
                   help="write the split marks; report otherwise")
    p.set_defaults(func=run_remark_eval)

    p = add("delete", help="un-key a page — remove its file from gt/zones/ and "
            "every mark that referred to it (split, rule and ink exemptions). The "
            "one thing the store could not express: `save_zones` refuses an empty "
            "save, so a page keyed in error could be corrected but not withdrawn. "
            "Keeps `.prev` and records the act in the journal")
    p.add_argument("ref", metavar="PP-NNN", help=REF_HELP)
    p.add_argument("--commit", action="store_true",
                   help="actually remove; preview otherwise")
    p.set_defaults(func=run_delete)

    p = add("diff", help="what differs between gt/zones/ and mz/zones/ — paired "
            "by vertical overlap, reported as only_in_gt (a missed region), "
            "only_in_mz (an invented one), label (paired but named differently) "
            "or edge (same region, cut elsewhere, beyond min_zone_h_px). "
            "Measurement — exit 0")
    p.add_argument("ref", metavar="PP-NNN", nargs="?",
                   help="one page. Omit for every page in both stores")
    p.set_defaults(func=run_diff)

    p = add("paragraphs", help="audit the paragraph-boundary rule, both "
            "directions. `false_negative` = a boundary gt asserts that the rule "
            "would not recover, which is a trustworthy recall figure; "
            "`false_positive` = the rule firing inside a zone, a worklist and NOT "
            "a precision figure, since each is either a keying slip or a false "
            "alarm and gt cannot arbitrate. The segmenter cannot do this check at "
            "all: two abutting MainZone-P rectangles rasterize to one target. "
            "Measurement — exit 0")
    p.add_argument("ref", metavar="PP-NNN", nargs="?",
                   help="one page. Omit for the whole corpus, or scope with "
                        "--itinerary")
    p.add_argument("--itinerary", metavar="LST", default=None, help=ITIN_HELP)
    p.set_defaults(func=run_paragraphs)

    p = add("link", help="rebuild zones/, the read view over both stores: one "
            "name per page, the human file winning wherever it exists. Derived "
            "and gitignored; reads may resolve through it, writes never do")
    p.set_defaults(func=run_link)

    p = add("blot", help="write the figure-blotted raster the segmenter trains "
            "on — gt/fig/ zones painted **white**, so paragraph wrap around an "
            "illustration cannot shape what the model learns about zone geometry. "
            "Distinct from `ocr blot`, which paints lines and figures in "
            "conspicuous colours for a human to read; this one has to look like "
            "blank paper. The declared box is painted and not a pixel more")
    p.add_argument("ref", metavar="PP-NNN", nargs="?",
                   help="one page. Omit for all 832")
    p.set_defaults(func=run_blot)


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
    if a.ref:
        rep = zmod.validate_page(a.ref, a.root, cfg, ink=True, store=store)
        out(a, rep)
        # The zones themselves, by default — reading a page's layout used to mean
        # opening the editor. `--lines` swaps in the line-by-line breakdown,
        # which matters only when something *inside* a zone is in question and
        # costs a second raster decode besides.
        rows = (zmod.page_zone_lines(a.ref, a.root, cfg, store=store) if a.lines
                else zmod.page_zones_table(a.ref, a.root, store=store))
        if rows:
            out(a, rows)
        return 1 if (rep["errors"] and store == zmod.ZONEDIR) else 0
    summary, rows = zmod.validate_corpus(a.root, cfg, ink=a.ink,
                                         refs=_itin(a, zmod), store=store)
    out(a, summary)
    if rows:
        out(a, rows)
    return 1 if (summary["errors"] and store == zmod.ZONEDIR) else 0


def run_edit(a) -> int:
    zmod, _ = _mod()
    itin = _itin(a, zmod)
    start = a.ref
    if not start and itin:
        # Resume: the first page on the list nobody has keyed. Falls back to the
        # head of the list once it is finished, so the session still opens.
        start = next((r for r in itin if not zmod.has_zones(r, a.root)), itin[0])
    if not start:
        print("zones edit needs a ref to start at, e.g. `harness zones edit "
              "1-048` — or an --itinerary to take one from", file=sys.stderr)
        return 2
    from ..zones_ui import serve as serve_zones
    serve_zones(start, a.root, a.port, itin, a.itinerary or "")
    return 0


def run_predict(a) -> int:
    zmod, _ = _mod()
    model = a.model or zmod.DEFAULT_MODEL
    if a.ref:
        # One named page still overrides the exempt skip — naming it is the
        # request — but it no longer bypasses the skip entirely. It used to, so a
        # named ref silently overwrote an existing prediction along with the
        # model sha that file records, which is the one witness in the store to
        # which model spoke. `--force` is how a re-prediction says it meant it.
        why = zmod.predict_skip(a.ref, a.root, force=a.force, single=True)
        if why:
            out(a, {"ref": zmod.norm_ref(a.ref), "predicted": 0, "skipped": why})
            return 0
        net, sha = zmod.load_segmenter(model, a.root)
        fn = zmod.predict_dp if a.decode == "dp" else zmod.predict
        out(a, fn(a.ref, a.root, net=net, sha=sha, model_path=model,
                  device=a.device))
        return 0
    rep = zmod.predict_all(a.root, refs=_itin(a, zmod), model_path=model,
                           device=a.device, decode=a.decode, force=a.force)
    out(a, rep)
    # Same contract as `assemble`'s missing_blot: a page the model was asked
    # about and could not be shown is a gap in the run, not a quiet omission.
    return 1 if rep["skipped_no_blot"] else 0


def run_score(a) -> int:
    zmod, _ = _mod()
    rep = zmod.score(a.root, model_path=a.model, decode=a.decode, device=a.device)
    conf = rep.pop("confusion")
    out(a, rep)
    out(a, conf)
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
    out(a, zmod.delete_zones(a.ref, a.root, commit=a.commit))
    return 0


def run_diff(a) -> int:
    from collections import Counter
    zmod, load_config = _mod()
    cfg = load_config(a.root)
    scope = ([zmod.norm_ref(a.ref)] if a.ref else
             sorted(set(zmod.zone_refs(a.root)) & set(zmod.zone_refs(a.root, zmod.MZDIR)),
                    key=zmod.parse_ref))
    rows = [r for ref_ in scope for r in zmod.zone_diff(ref_, a.root, cfg)]
    out(a, {"pages": len(scope), "differences": len(rows),
            "pages_differing": len({r["ref"] for r in rows}),
            "by_kind": " ".join(f"{k}:{v}" for k, v in
                                sorted(Counter(r["kind"] for r in rows).items()))})
    if rows:
        out(a, rows)
    return 0


def run_paragraphs(a) -> int:
    zmod, load_config = _mod()
    scope = [zmod.norm_ref(a.ref)] if a.ref else _itin(a, zmod)
    summary, rows = zmod.paragraph_audit(a.root, load_config(a.root), refs=scope)
    out(a, summary)
    if rows:
        out(a, rows)
    return 0


def run_link(a) -> int:
    zmod, _ = _mod()
    out(a, zmod.link_view(a.root))
    return 0


def run_blot(a) -> int:
    zmod, _ = _mod()
    out(a, zmod.blot_one(a.ref, a.root) if a.ref else zmod.blot_all(a.root))
    return 0
