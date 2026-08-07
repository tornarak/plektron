"""The segmentation editor: one local page, two clicks a zone.

`review.py --serve` is the template — stdlib `ThreadingHTTPServer` on loopback, the
page built as a Python string, no static files, a Done button that stops the server
so nobody manages the process by hand. What differs is why it exists. The review
queue replaced a text editor; this replaces eScriptorium, whose import/export loop
is the friction the whole store layout was designed around.

**The interaction is the specification.** A zone's left and right edges come from
`data/zones_config.json`; the pointer supplies only a top and a bottom. So the
editor cannot express a zone of the wrong width, and the fixed-measure claim the
training set rests on is true by construction rather than by care. Chain mode then
makes the bottom of one zone the top of the next, which is what a vertical
partition *is* — so an ordinary page of prose costs one type key and one click per
zone, and the ten-second page is arithmetic rather than aspiration.

**The session is the server, not the page.** `review --serve` binds one ref because
a review is one page's worth of work; keying segmentation is a sweep, so the arrow
keys walk `all_scans` and the ref in the URL is only where the sweep started.

Three decisions worth naming because their opposites are the obvious choice:

- **Navigation saves only if something changed.** An unconditional autosave would
  mint an empty zone file for every page merely skimmed past, and an empty file is
  a *claim* here — "looked at, holds nothing", which is what a plate legitimately
  is. Only an explicit save may make one.
- **The column is measured per page, not configured per part.** The measure is
  stable across the book (~1780 px) but its position drifts up to 236 px inside a
  single part, so a constant was ~104 px out on `1-048`. That measurement took the
  verso/recto distinction with it — parity explained only part of the drift — and
  what is left is a manual ±4 px nudge, which is UI state and reaches no file.
- **Order rules warn in the browser and again on the server.** The client copy is
  what makes a violation visible at the keystroke rather than at the save; the
  server's `zones.validate_page` is the one that counts, and its result replaces
  the client's on every save. `harness/tests/test_zones_order.py` is what holds the two
  transcriptions together.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import figures as fg
from . import webui
from . import zones as zn
from . import zones_config as zc
from .context import all_scans, norm_ref, parse_ref

PORT = 8732


def _resolve_column(z: dict, windows: list[dict], tol: float) -> int | None:
    """Which of the page's columns a stored zone sits in, if any.

    Needed only so that a reopened page's zones follow a column nudge instead of
    staying where they were. A zone matching nothing keeps its stored x and is
    reported `column: null` — the editor leaves it alone rather than snapping it
    somewhere plausible, and `validate_page` has already raised against it.
    Guessing here would repair the symptom and lose the finding.
    """
    if not windows:
        return None
    offs = [max(abs(z["x0"] - w["x0"]), abs(z["x1"] - w["x1"])) for w in windows]
    best_off = min(offs)
    return offs.index(best_off) if best_off <= tol else None


def _snap_column(z: dict, windows: list[dict]) -> int:
    """Which configured column a *predicted* region is offering itself as.

    Deliberately not `_resolve_column`. That one asks whether a stored zone still
    matches a column within tolerance and answers `null` when it does not, because a
    stored zone whose x means nothing is a finding and snapping it would repair the
    symptom. A prediction is the opposite case: kraken's x is not a claim about the
    column at all — the model was never shown that the measure is fixed — so there is
    no finding to lose, and every region has to land in some column for a human to
    see and rule on it. Widest horizontal overlap, falling back to the first column.
    """
    best, best_ov = 0, -1
    for i, w in enumerate(windows):
        ov = min(z["x1"], w["x1"]) - max(z["x0"], w["x0"])
        if ov > best_ov:
            best, best_ov = i, ov
    return best


# `paras` is not a store. It is `gt/zones/` with the paragraph rule applied,
# computed on open and written nowhere — which is what it always should have been.
# Persisting it into `mz/` made that store mean three things at once (raw kraken, DP
# decode, and this), so `--diff` over the corpus reported 507 invented regions that
# were nothing of the kind. A proposal derived from ground truth is not machine
# output, and giving it a slot in the machine store made the store's name a lie.
#
# It was called `split` until the name was read back cold and meant nothing: the
# topbar already carries a `split` pill two places to its left, and that one is the
# train/eval/exempt mark. Two unrelated things under one word in one strip of UI.
STORES = ("gt", "mz", "zones", "paras")

# What the selector is offering, in the pill's tooltip. The store names are short
# enough to be cryptic, and three of the four are not directories.
STORE_HELP = {
    "gt": "gt/zones/ — what a human has been through. A save always lands here",
    "mz": "mz/zones/ — what the segmenter emitted, shown as an unsaved proposal",
    "zones": "the view: the human file wherever there is one, the machine's otherwise",
    "paras": "gt with the paragraph rule applied — a proposal, computed live and "
             "stored nowhere",
}

# What each name resolves to. `zones` is the view and resolves by the same rule
# `link_view` writes — the human file wherever there is one — computed rather than
# read off the farm, so the editor does not silently depend on `--link` having been
# run since the last prediction.
STORE_DIR = {"gt": zn.ZONEDIR, "mz": zn.MZDIR}


def effective_store(ref: str, root: Path, store: str) -> str:
    """Which real store answers for this page under the selected name.

    Returns `"gt"`, `"mz"`, or `""` when the selection has nothing for the page —
    and that third case is a state worth drawing rather than an error. Asking for
    `mz` on a page nobody has predicted is a fair question with the answer "nothing
    here", and it is exactly the question a reviewer walking an itinerary is asking.
    """
    if store == "zones":
        for s in ("gt", "mz"):
            if zn.has_zones(ref, root, STORE_DIR[s]):
                return s
        return ""
    if store == "paras":
        return "paras" if zn.has_zones(ref, root, zn.ZONEDIR) else ""
    return store if zn.has_zones(ref, root, STORE_DIR[store]) else ""


def _machine_proposal(ref: str, root: Path, windows: list[dict],
                      labels: set[str],
                      min_h: int = 0) -> tuple[list[dict], list[str], int]:
    """`mz/zones/`'s regions as unsaved bands, plus the labels that were dropped.

    What comes back is a *proposal*: y from each predicted polygon's bounding box,
    x from the page's configured column, which is exactly the geometry two clicks
    would have produced. The editor shows it, the human corrects it, and the save
    goes to `gt/zones/` through the same `save_zones` every other page uses.
    Nothing here writes, and nothing here can reach a human's file.

    A label the config does not declare is **dropped and returned**, not mapped to
    something plausible: `validate_page` calls an undeclared label an error, so
    quietly renaming one would hide a model trained against a different class map
    behind a page that looks ordinary.

    Regions shorter than `min_zone_h_px` are dropped too, and counted. This is the
    store's own rule that a zone thinner than a mis-click is not a zone — the same
    one `validate_page` errors on — and the model leans on it hard: **over half its
    raw output falls under it**, median predicted height 24 px against a 30 px floor,
    with a lower quartile of 7. Measured over the held-out pages, dropping them costs
    **nothing** in recall (93.9% either way, no zone goes missing) and removes
    **every** spurious region, 26 to 0. Keeping them would hand the editor 2.5 bands
    to delete for every one worth looking at, on a page where each is already an
    error the gate would raise.

    The slivers stay in `mz/zones/` regardless: that store holds what the model
    emitted, and this is the proposal built from it.
    """
    out, dropped, short = [], [], 0
    for z in zn.read_zones(ref, root, store=zn.MZDIR):
        if z["y1"] - z["y0"] < min_h:
            short += 1
            continue
        if z["label"] not in labels:
            dropped.append(z["label"])
            continue
        col = _snap_column(z, windows)
        out.append({"label": z["label"], "y0": z["y0"], "y1": z["y1"],
                    "column": col,
                    "x0": windows[col]["x0"], "x1": windows[col]["x1"]})
    return sorted(out, key=lambda z: z["y0"]), sorted(set(dropped)), short


def _uncovered(ref: str, root: Path, cfg: dict) -> list[dict]:
    """The page's uncovered-ink bands, recording the verdict on the way past.

    The raster read is happening anyway — every page the editor opens pays for it.
    Throwing the answer away and making the page list ask for it again is the only
    reason that list would ever be slow, so it is written down instead.
    """
    r = zn.validate_page(ref, root, cfg, ink=True)
    zn.record_ink(ref, r, root)
    return r["uncovered"]


def _fig_state(ref: str, root: Path, cfg: dict) -> dict:
    """The figure track's half of one page's state.

    `gt/fig/` wins wherever it exists; `mz/fig/` shows only where it does not, and
    then as a **proposal** — the same rule the zone half keeps, for the same reason,
    and the reason is not symmetry. A machine figure box that reached `gt/fig/`
    unexamined would be painted white by `zones blot` into the rasters the *zone*
    segmenter trains on, so a wrong one does not merely sit there being wrong: it
    teaches. That is why there is no read view over the pair, and why promoting a
    proposal is an explicit act here as well.

    Rectangles pass through untouched in both directions. No snap, no column.
    """
    gt = fg.zones(ref, root)
    proposal = ""
    if not gt and fg.alto_for(ref, root, fg.MZFIGDIR).exists():
        gt = fg.zones(ref, root, fg.MZFIGDIR)
        proposal = "mz"
    figs = [{"id": b["id"], "label": b["label"],
             "x0": b["hpos"], "y0": b["vpos"],
             "x1": b["hpos"] + b["width"], "y1": b["vpos"] + b["height"]}
            for b in gt]
    exempt = fg.load_rule_exempt(root).get(ref, [])
    return {
        "figs": figs,
        "fig_proposal": proposal,
        # An `mz` proposal's ids are the machine's and mean nothing to
        # `data/readings.md`, so they are dropped rather than carried into a save
        # where they would look like keys. `save_figs` mints real ones.
        "fig_ids": "" if proposal else "gt",
        "fig_exempt": exempt,
        "fig_warnings": zc.fig_warnings(cfg, gt, exempt),
        "fig_present": {
            "gt": len(fg.zones(ref, root)) or None,
            "mz": (len(fg.zones(ref, root, fg.MZFIGDIR))
                   if fg.alto_for(ref, root, fg.MZFIGDIR).exists() else None),
        },
        "fig_readings": sorted(fg.readings_for(ref, root)),
    }


def page_state(ref: str, root: Path, cfg: dict, nudge: int = 0,
               itinerary: list[str] | None = None, store: str = "zones") -> dict:
    """Everything the editor needs for one page, resolved server-side.

    The columns come from `zones.measure_frame` — read off this page's own ink
    rather than from a per-part constant, because the measure is stable across the
    book while its position drifts up to 236 px inside a single part. `nudge`
    carries a manual correction across navigation for the rare page the anchor
    cannot read; it is UI state and reaches no file.

    `store` is **which store is being looked at, and it is orthogonal to the
    itinerary**: the itinerary chooses the pages, this chooses whose reading of them
    you see. `zones` (the default) is the view — the human file wherever there is
    one, the machine's otherwise — and `gt`/`mz` pin one store, including onto a page
    that has nothing in it, because "the model produced nothing here" and "nobody has
    keyed this" are both answers rather than errors.

    Whatever is selected, **a save writes `gt/zones/`**. Showing `mz` shows it as a
    *proposal* — snapped to the configured column, opening clean — so the only route
    from a prediction to ground truth is a human editing or explicitly saving it.
    """
    ref = norm_ref(ref)
    # The itinerary replaces scan order as the sequence the arrow keys walk. A page
    # reached by URL that is not on the list still opens and still saves — it simply
    # has no neighbours, which is the honest answer rather than silently splicing it
    # into a work-list nobody put it on.
    scans = itinerary or all_scans(root)
    try:
        i = scans.index(ref)
    except ValueError:
        i = -1
    m = zn.measure_frame(ref, root, cfg)
    windows = [{"x0": w["x0"] + nudge, "x1": w["x1"] + nudge} for w in m["columns"]]
    tol = cfg["width_tolerance_px"]
    if store not in STORES:
        raise ValueError(f"store must be one of {', '.join(STORES)}, not {store!r}")
    keyed = zn.has_zones(ref, root)
    shown = effective_store(ref, root, store)

    zones, dropped, short = [], [], 0
    if shown == "gt":
        for z in zn.read_zones(ref, root):
            zones.append({"label": z["label"], "y0": z["y0"], "y1": z["y1"],
                          "column": _resolve_column(z, windows, tol),
                          "x0": z["x0"], "x1": z["x1"]})
    elif shown == "mz":
        zones, dropped, short = _machine_proposal(
            ref, root, windows, set(zc.types_by_label(cfg)),
            int(cfg["min_zone_h_px"]))
    elif shown == "paras":
        # gt with the paragraph rule applied, computed here and stored nowhere.
        for z in zn.split_at_paragraphs(zn.read_zones(ref, root), ref, root, cfg):
            zones.append({"label": z["label"], "y0": z["y0"], "y1": z["y1"],
                          "column": _resolve_column(z, windows, tol),
                          "x0": z["x0"], "x1": z["x1"]})
    w, h = zn.raster_size(ref, root)
    return {
        "ref": ref,
        "page": {"w": w, "h": h},
        "columns": windows,
        # The vertical crop. A view concern only — nothing validates against it,
        # and a zone drawn outside the ink is already an error the ink check finds.
        "content": m["content"],
        "anchor": {"measured": m["measured"], "source": m["source"], "nudge": nudge},
        "zones": zones,
        "keyed": keyed,
        # Which store was asked for, which one answered, and what each holds. The
        # HUD draws all three: an unmarked proposal would be indistinguishable from
        # work someone had already done, which is the confusion the two stores exist
        # to prevent, arriving through the one surface that reads from both. And the
        # presence counts are what make the selector navigable — you can see there is
        # something in `mz` before switching to it, rather than switching to find out.
        "store": store,
        "shown": shown,
        # What the *view* resolves to, which is not the same as what the current
        # selection resolved to and must not be drawn from it: with `mz` pinned on a
        # page that has both, `shown` is `mz` while the view still answers `gt`. The
        # pill reports the store rule, not the thing being looked at.
        "view": effective_store(ref, root, "zones"),
        "present": {
            "gt": len(zn.read_zones(ref, root)) if keyed else None,
            "mz": (len(zn.read_zones(ref, root, store=zn.MZDIR))
                   if zn.has_zones(ref, root, zn.MZDIR) else None),
        },
        # How many zones the paragraph rule would make of this page — so the pill
        # says whether it would change anything before you switch to it.
        "paras_zones": (len(zn.split_at_paragraphs(
            zn.read_zones(ref, root), ref, root, cfg)) if keyed else "—"),
        "proposal": "mz" if shown == "mz" else "",
        "proposal_dropped": dropped,
        "proposal_short": short,
        "split": zn.load_splits(root).get(ref, zn.DEFAULT_SPLIT),
        "exempt": zn.load_exempt(root).get(ref, []),
        # Ink no zone accounts for, shown as the page is keyed rather than only
        # after a save. Skipped on a page with no zones, where every mark on the
        # leaf is uncovered and the answer would be noise. Recorded on the way past,
        # so the page list is a reader of work already done rather than a job.
        "uncovered": _uncovered(ref, root, cfg) if zones else [],
        "ink_exempt": zn.load_ink_exempt(root).get(ref, []),
        # --- the figure track, parallel and not inside the above ---------------
        #
        # It rides the same page state because it is the same page and the same
        # human looking at it, but every field is its own: `figs` never mixes into
        # `zones`, and neither list is derivable from the other. Note there is no
        # column resolution here and no `_snap_column` — a picture's x is what
        # somebody saw, and this is the exact inverse of the guarantee the zone
        # half rests on.
        **_fig_state(ref, root, cfg),
        "prev": scans[i - 1] if i > 0 else None,
        "next": scans[i + 1] if 0 <= i < len(scans) - 1 else None,
        "index": i + 1, "total": len(scans),
        "on_list": i >= 0,
        # How much of the work-list is behind you. The count is what a sweep is
        # for, and it is not derivable from the position when the list is not
        # being walked in order.
        "done": sum(1 for r in scans if zn.has_zones(r, root)),
    }


def save_payload(payload: dict, root: Path, cfg: dict) -> dict:
    """Turn the editor's y-pairs into stored zones, resolving x from the config.

    **The client never supplies an x for a zone it drew.** It sends a column index;
    the geometry is re-measured here from the page itself. That is the whole
    guarantee — an editor cannot save a hand-sized zone because there is no field in
    which to put one. The exception is a zone whose stored x matched no column when
    the page was opened (`column: null`), which is passed through untouched so that
    reopening a page cannot silently rewrite geometry it did not understand.

    The nudge is applied here rather than trusted from the client's x for the same
    reason: it is a single number the server can bound, not an arbitrary rectangle.
    """
    ref = norm_ref(payload["ref"])
    nudge = int(payload.get("nudge") or 0)
    wins = [{"x0": w["x0"] + nudge, "x1": w["x1"] + nudge}
            for w in zn.page_windows(ref, root, cfg)]
    out = []
    for z in payload.get("zones") or []:
        y0, y1 = sorted((int(round(z["y0"])), int(round(z["y1"]))))
        if z.get("column") is None and z.get("x0") is not None:
            x0, x1 = int(z["x0"]), int(z["x1"])
        else:
            w = wins[min(int(z.get("column") or 0), len(wins) - 1)]
            x0, x1 = int(w["x0"]), int(w["x1"])
        out.append({"label": z["label"], "x0": x0, "y0": y0, "x1": x1, "y1": y1})

    res = zn.save_zones(ref, out, root,
                        split=payload.get("split"),
                        exempt=payload.get("exempt") or [])
    zn.set_ink_exempt(ref, payload.get("ink_exempt") or [], root)
    check = zn.validate_page(ref, root, cfg, ink=True)
    zn.record_ink(ref, check, root)
    res["errors"] = check["errors"]
    res["warnings"] = check["warnings"]
    res["uncovered"] = check["uncovered"]
    # So the topbar can redraw the store selector against what is now on disk rather
    # than leave the counts as they were when the page was served. The `paras` count
    # is derived from `gt`, so a save moves it too, and a stale proposal count sitting
    # beside a fresh one is the kind of thing this project reads as a live number.
    res["paras_zones"] = len(zn.split_at_paragraphs(
        zn.read_zones(ref, root), ref, root, cfg))
    res.update(_save_figs(payload, ref, root, cfg))
    return res


def _save_figs(payload: dict, ref: str, root: Path, cfg: dict) -> dict:
    """The figure half of a save, and it is **opt-in by the payload's shape**.

    No `figs` key means the figure store is not touched — not read, not rewritten,
    not stamped. That is not an optimisation. `zones blot` keys its rasters off
    `gt/fig/`'s mtimes, so rewriting 252 identical files during ordinary zone
    keying would stale the entire blot tree and, through it, everything the zone
    segmenter trains on. A pure zone edit must leave no trace here.

    **The client's rectangles are taken as given**, bounded to the page and
    otherwise unaltered — the deliberate inverse of the zone half above, where the
    server supplies x precisely so a hand-sized zone cannot be saved. The claim
    differs: a zone's width is a property of the book, so a drawn one is a small
    lie; a picture's edges are a property of that picture, and only the person
    looking at it can say where they are.
    """
    if "figs" not in payload:
        return {}
    w, h = zn.raster_size(ref, root)
    blocks = []
    for f in payload.get("figs") or []:
        x0, x1 = sorted((int(round(f["x0"])), int(round(f["x1"]))))
        y0, y1 = sorted((int(round(f["y0"])), int(round(f["y1"]))))
        b = {"label": f["label"],
             "x0": max(0, x0), "y0": max(0, y0),
             "x1": min(w, x1), "y1": min(h, y1)}
        # An id survives only when it came from `gt/fig/`. A machine proposal's
        # ids are the segmenter's and key nothing, so carrying them into a save
        # would put a string shaped like a `data/readings.md` key into the store
        # with no reading behind it.
        if f.get("id") and payload.get("fig_ids") == "gt":
            b["id"] = f["id"]
        blocks.append(b)

    rules = payload.get("fig_exempt") or []
    if not blocks:
        # The store's refusal is right and the editor must not merely relay it:
        # a human who deleted the last box has an intent, and `fig delete` is it.
        return {"fig_error": (
            "no figure boxes left on this page. Absence of the file is how this "
            "store records 'no figures here', so an empty one would say the "
            f"opposite — withdraw the page instead: harness fig delete {ref} "
            "--commit")}
    res = fg.save_figs(ref, blocks, root, rules=rules)
    check = fg.validate_fig_page(ref, root, cfg)
    return {
        "figs_saved": res["blocks"],
        "fig_errors": check["errors"],
        "fig_warnings": check["warnings"],
        # A caption box with no reading behind it is not an error — the geometry
        # is drawn before the text is keyed, in that order, by design. But it is
        # the one thing a human leaves the editor to do, so the page says which
        # block is waiting rather than letting `corpus figures` find it later.
        "readings_missing": [
            f"{ref}|{fg.zone_suffix(b['id'])}"
            for b in fg.zones(ref, root)
            if b["label"] == fg.FIGDESC
            and fg.zone_suffix(b["id"]) not in {
                r["zone_suffix"] for r in fg.readings_for(ref, root).values()}],
        # `zones blot` paints this page's raster from these boxes, so the blot is
        # now stale and the zone segmenter's input with it. Said here because
        # `blot_all` is unconditional and nothing else will mention it.
        "blot_stale": True,
    }


# ------------------------------------------------------------------ the page

CSS = webui.CHROME_CSS

JS = r"""
const T = {}, KEY = {};
CFG.types.forEach(t => { T[t.label] = t; KEY[t.key] = t.label; });
const ACT = {};
for (const [name, k] of Object.entries(CFG.actions || {}))
  if (!name.startsWith('_')) ACT[k] = name;
// The figure track's actions join the same map — one keyboard, and the config
// loader has already refused any key bound in two of the three namespaces.
for (const [name, k] of Object.entries((CFG.figures || {}).actions || {}))
  if (!name.startsWith('_')) ACT[k] = name;
const FKEY = {};
((CFG.figures || {}).types || []).forEach(t => { FKEY[t.key] = t.label; });

let S = {
  zones: ST.zones.map(z => ({...z})),
  cur: null, col: 0, pending: null, hoverY: null, inside: false,
  hover: -1, sel: -1, nearEdge: null,
  // A machine proposal opens **clean**, and that is load-bearing rather than
  // incidental. Navigation saves whatever is dirty on the way out, so a proposal
  // marked dirty on arrival would let the arrow keys walk an itinerary promoting
  // predictions into ground truth unread — the one thing the two stores exist to
  // stop. Clean means passing through a page writes nothing; promoting it takes an
  // edit or an explicit save, which is a human act either way.
  chain: true, dirty: false, split: ST.split, exempt: ST.exempt.slice(),
  issues: [], drag: null, nudge: ST.anchor.nudge || 0,
  ink: (ST.uncovered || []).map(b => ({...b})),
  inkEx: (ST.ink_exempt || []).map(r => ({...r})),
  // ---- the figure track, parallel to everything above --------------------
  // `figTrack` switches what the pointer does, never what is drawn: the layer
  // renders either way, dimmed when it is not the one being edited, because a
  // picture you cannot see is a picture you will draw a zone over.
  // `figsDirty` is separate from `dirty` so that a pure zone edit sends no
  // `figs` key at all — `zones blot` reads `gt/fig/`'s mtimes, so rewriting the
  // figure store during ordinary keying would stale every training raster.
  figTrack: false, figs: (ST.figs || []).map(f => ({...f})),
  figCur: null, figSel: -1, figHover: -1, figDrag: null, figsDirty: false,
  figExempt: (ST.fig_exempt || []).slice(), figPending: null, capBeside: false,
  hoverX: null,
};
const FT = {};
((CFG.figures || {}).types || []).forEach(t => { FT[t.label] = t; });
const FIG_ACTIONS = (CFG.figures || {}).actions || {};
let zoom = parseFloat(localStorage.getItem('zonesZoom') || '0') || 0;

const img = document.getElementById('img'), ov = document.getElementById('ov');
const stage = document.getElementById('stage'), wrap = document.getElementById('wrap');
const VIEW = Object.assign({column_margin: 0.10, edge_band_px: 80,
                            edge_overlap_px: 140}, CFG.view || {});
// How far the track you are *not* editing recedes. Two numbers rather than one
// because the two layers are not equally in the way: a keyed page carries eight
// or ten body zones against two or three figure boxes, so the zone layer has to
// go much quieter under the figure track than the other way round.
const FIGV = Object.assign({dim_zones: 0.14, dim_figs: 0.45},
                           (CFG.figures || {}).view || {});

// ---- column geometry: measured on the server off this page's own ink, then
// shifted by the manual nudge. Not computed here from a per-part constant — the
// measure is stable across the book but its position drifts up to 236 px inside
// one part, so there is no constant to compute from.
function windows() {
  return ST.columns.map(w => ({x0: w.x0 - (ST.anchor.nudge || 0) + S.nudge,
                               x1: w.x1 - (ST.anchor.nudge || 0) + S.nudge}));
}
function win() {
  const w = windows();
  return w[Math.min(S.col, w.length - 1)];
}
function zoneX(z) {
  if (z.column === null || z.column === undefined) return {x0: z.x0, x1: z.x1};
  const w = windows();
  return w[Math.min(z.column, w.length - 1)];
}

// ---- fit: default is the whole page in the viewport, zoom steps from there
function applyZoom() {
  // Fit the **text column** to the view, not the leaf. The column is what is being
  // judged and what every click lands in; the margins carry nothing, and fitting
  // the whole page spent most of the screen on paper. A modest margin either side
  // keeps the column's edges visible so a bad anchor is obvious.
  const w = win();
  const colW = (w.x1 - w.x0) * (1 + 2 * VIEW.column_margin);
  const fit = (wrap.clientWidth - 20) / colW;
  const s = zoom ? fit * Math.pow(1.25, zoom) : fit;
  const px = Math.round(ST.page.w * s) + 'px';
  const hpx = Math.round((ST.content.y1 - ST.content.y0) * s) + 'px';
  // Only re-lay-out when the size actually changed. Doing it every render would
  // fight the editor's own horizontal scrolling on every mouse move.
  if (stage.style.width !== px || stage.style.height !== hpx) {
    stage.style.width = px;
    stage.style.height = hpx;
    // The image keeps its full height and is slid up behind the clip, so
    // `img.getBoundingClientRect()` still describes the whole page — which is
    // what `yAt` reads, and why cropping the view changes no coordinate maths.
    img.style.top = Math.round(-ST.content.y0 * s) + 'px';
    requestAnimationFrame(centreColumn);
  }
  return s;
}

// Centre the column horizontally rather than the page: on a leaf whose text sits
// well off-centre — and they do, by up to 236 px — centring the paper puts the
// column off to one side.
function centreColumn() {
  const r = img.getBoundingClientRect();
  if (!r.width) return;
  const w = win(), s = r.width / ST.page.w;
  const mid = (w.x0 + w.x1) / 2 * s;
  wrap.scrollLeft = Math.max(0, mid - wrap.clientWidth / 2 + 10);
}

// ---- hover the top or bottom edge to jump a screen, instantly
//
// A jump, not a scroll. At this zoom the leaf is about two screens tall, so the
// movement actually wanted is "show me the other half" — and a continuous scroll
// makes that a thing to wait for and steer, when it should be one flick of the
// wrist. `edge_overlap_px` of the old view is kept so the join is readable and a
// zone boundary never lands in the seam.
//
// Armed once per entry into the band: after a jump the cursor is still inside it,
// so without this it would page again on the next mouse move and run off the leaf.
let edgeArmed = true;
function edgeScroll(clientY) {
  const r = wrap.getBoundingClientRect(), band = VIEW.edge_band_px;
  const inTop = clientY - r.top < band, inBot = r.bottom - clientY < band;
  if (!inTop && !inBot) { edgeArmed = true; return; }
  if (!edgeArmed) return;
  edgeArmed = false;
  const step = Math.max(80, wrap.clientHeight - VIEW.edge_overlap_px);
  wrap.scrollTop += inTop ? -step : step;
}
function edgeStop() { edgeArmed = true; }
function yAt(ev) {
  const r = img.getBoundingClientRect();
  return Math.max(0, Math.min(ST.page.h,
    Math.round((ev.clientY - r.top) * (ST.page.h / r.height))));
}
// The figure track's pointer, and the reason it is a *pair* where the zone
// track's is a scalar. There is no `xAt` above because a zone has no x to take
// from the pointer; here the pointer is the only thing that knows.
function ptAt(ev) {
  const r = img.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(ST.page.w,
       Math.round((ev.clientX - r.left) * (ST.page.w / r.width)))),
    y: yAt(ev),
  };
}
// Topmost box under a point, searched back to front so the one drawn last — the
// one a human sees on top — is the one that answers.
function figHit(p) {
  for (let i = S.figs.length - 1; i >= 0; i--) {
    const f = S.figs[i];
    if (p.x >= f.x0 && p.x <= f.x1 && p.y >= f.y0 && p.y <= f.y1) return i;
  }
  return -1;
}
// Arm the next box's **first corner** off the one just committed. This is
// `resume()` in two dimensions, and it hands over exactly as much: the zone
// chain gives the next zone its top edge and asks the human for the bottom, so
// this gives the next box one corner and asks for the opposite one.
//
// It armed a whole finished rectangle once — the picture's width, an assumed
// height — and that was wrong twice over. The height was a guess, and captions
// in this book run from one line to five; and a box that arrives complete has
// no handle, so correcting it meant deleting it and drawing it again. A corner
// imputes nothing and still saves the placement, which is the part that is
// actually predictable.
//
// The caption's corner is the picture's **bottom-left** — where the reading
// continues, the same edge `resume()` returns. `caption_beside` re-arms at the
// top-right for the captions set vertically alongside.
function armCaption(fig) {
  const cap = ((CFG.figures || {}).types || [])
    .find(t => t.auto_place && t.auto_place.after === fig.label);
  if (!cap) { S.figPending = null; return; }
  S.figPending = S.capBeside
    ? {label: cap.label, x: fig.x1, y: fig.y0, from: fig}
    : {label: cap.label, x: fig.x0, y: fig.y1, from: fig};
  S.figCur = cap.label;
}
function addFig(box) {
  S.figs.push(box);
  S.figsDirty = true; S.figSel = -1;
  if (box.label === 'GraphicZone') armCaption(box); else S.figPending = null;
}
// The rectangle an armed corner and the cursor describe between them.
function pendingRect() {
  if (!S.figPending || S.hoverX === null || S.hoverY === null) return null;
  const p = S.figPending;
  return {label: p.label,
          x0: Math.min(p.x, S.hoverX), x1: Math.max(p.x, S.hoverX),
          y0: Math.min(p.y, S.hoverY), y1: Math.max(p.y, S.hoverY)};
}
// ---- the caption-count rule, transcribed from zones_config.fig_warnings.
// Held to that function by harness/tests/test_zones_ui.py, the same way
// test_zones_order.py holds `orderWarnings` — two copies of one vocabulary, and
// the gate points at the copy that would otherwise drift silently.
function figWarnings() {
  const on = new Set(((CFG.figures || {}).rules || []).map(r => r.id));
  const out = [];
  if (on.has('captions-lte-figures')) {
    const nf = S.figs.filter(f => f.label === 'GraphicZone').length;
    const nc = S.figs.filter(f => f.label === 'GraphicZone-FigDesc').length;
    if (nc > nf)
      out.push({rule: 'captions-lte-figures',
                detail: `${nc} captions to ${nf} ${nf === 1 ? 'picture'
                        : 'pictures'} — this book never sets more`,
                exempted: S.figExempt.includes('captions-lte-figures')});
  }
  return out;
}

// ---- the order rules, transcribed from zones_config.order_warnings.
// Held to that function by harness/tests/test_zones_order.py; a rule added there has to
// be added here, and the shapes are the same so the banner reads identically
// whether it came from the browser or from the save.
function orderWarnings() {
  const on = new Set((CFG.order_rules || []).map(r => r.id));
  const rank = l => (T[l] ? T[l].rank : null);
  const zs = S.zones.slice().sort((a, b) => a.y0 - b.y0);
  const out = [];
  const warn = (rule, detail) =>
    out.push({rule, detail, exempted: S.exempt.includes(rule)});
  if (on.has('title-first')) {
    const i = zs.findIndex(z => rank(z.label) === 0);
    if (i > 0) warn('title-first',
      `${zs[i].label} at y=${zs[i].y0} is below ${zs[0].label} at y=${zs[0].y0}`);
  }
  if (on.has('rank-monotone')) {
    const r = zs.filter(z => rank(z.label) !== null && rank(z.label) !== undefined);
    for (let i = 1; i < r.length; i++)
      if (rank(r[i].label) < rank(r[i - 1].label))
        warn('rank-monotone',
          `${r[i].label} (rank ${rank(r[i].label)}) at y=${r[i].y0} follows ` +
          `${r[i-1].label} (rank ${rank(r[i-1].label)}) at y=${r[i-1].y0}`);
  }
  if (on.has('max-per-page'))
    for (const t of CFG.types) {
      if (!t.max_per_page) continue;
      const n = zs.filter(z => z.label === t.label).length;
      if (n > t.max_per_page)
        warn('max-per-page',
          `${t.label} occurs ${n} times, max_per_page is ${t.max_per_page}`);
    }
  return out;
}

// ---- render
function render() {
  applyZoom();
  const P = ST.page, C = ST.content, parts = [];
  // The viewBox is the cropped band, so everything below still draws in page
  // coordinates and nothing else in this file has to know the view is cropped.
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg"
    viewBox="0 ${C.y0} ${P.w} ${C.y1 - C.y0}"
    preserveAspectRatio="none" width="100%" height="100%">`);
  // ---- how loud the *other* track is ------------------------------------
  // The inactive track stays on the page and stops competing for the eye. A
  // keyed page carries eight or ten body zones, and at full strength they bury
  // the two or three boxes being drawn over them; hiding them outright is worse,
  // because where the text sits is how you judge where a picture ends.
  //
  // The ink bands are deliberately **not** dimmed with them. On the figure track
  // an unaccounted band is the most useful mark on the page — very often it *is*
  // the undeclared picture you are about to draw, which is exactly how `1-191`
  // surfaced — so it is the one piece of zone-track furniture that gets louder
  // by comparison rather than quieter.
  const zoneDim = S.figTrack ? (FIGV.dim_zones ?? 0.14) : 1;
  // the live column guide, so the measure a click will use is never a surprise
  const w = win();
  parts.push(`<rect x="${w.x0}" y="${C.y0}" width="${w.x1 - w.x0}"
     height="${C.y1 - C.y0}" fill="none" stroke="var(--accent)" stroke-width="2"
     stroke-dasharray="14 10" opacity="${.38 * zoneDim}"/>`);
  parts.push(`<g opacity="${zoneDim}">`);
  const dragging = new Set((S.drag || []).map(g => g.i));
  S.zones.forEach((z, i) => {
    const g = zoneX(z), t = T[z.label], c = t ? t.color : '#999';
    const bad = z.column === null || z.column === undefined;
    const picked = i === S.sel;
    const on = picked || i === S.hover || dragging.has(i);
    parts.push(`<rect x="${g.x0}" y="${z.y0}" width="${g.x1 - g.x0}"
       height="${z.y1 - z.y0}" fill="${c}" fill-opacity="${on ? .30 : .17}"
       stroke="${c}" stroke-width="${bad ? 6 : (on ? 6 : 3)}"
       ${bad ? 'stroke-dasharray="12 8"' : ''}/>`);
    // A selection outlives the pointer, so it needs a mark the pointer is not
    // supplying: a second rule inset from the first, in the page's own ink colour.
    if (picked)
      parts.push(`<rect x="${g.x0 + 10}" y="${z.y0 + 10}"
         width="${g.x1 - g.x0 - 20}" height="${z.y1 - z.y0 - 20}" fill="none"
         stroke="var(--fg)" stroke-width="3" stroke-dasharray="16 10"/>`);
    parts.push(`<rect x="${g.x0}" y="${z.y0}" width="${g.x1 - g.x0}" height="4"
       fill="${c}"/>`);
    parts.push(`<text x="${g.x0 + 10}" y="${z.y0 + 42}" font-size="34"
       fill="${c}" font-family="ui-sans-serif,sans-serif">${i + 1}. ${
       t ? t.name : z.label}${bad ? ' [off-measure]' : ''}</text>`);
    // Grab handles on the zone under the cursor. Shift-drag was already here and
    // was invisible, which is the same as not being here.
    if (on) {
      const hw = 46, hh = 14;
      for (const y of [z.y0, z.y1])
        parts.push(`<rect x="${(g.x0 + g.x1) / 2 - hw}" y="${y - hh / 2}"
           width="${hw * 2}" height="${hh}" rx="6" fill="${c}"
           fill-opacity=".9"/>`);
    }
  });
  parts.push('</g>');
  // Ink the zones do not account for. Drawn under the preview so it never hides
  // what is being placed, and hatched rather than filled so it reads as a question
  // about the page rather than as another zone. **Outside the dimming group**: see
  // `zoneDim` above — on the figure track this is the mark worth following.
  parts.push(`<defs><pattern id="hatch" width="18" height="18"
     patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
     <rect width="18" height="18" fill="var(--warn)" fill-opacity=".12"/>
     <line x1="0" y1="0" x2="0" y2="18" stroke="var(--warn)" stroke-width="6"
       stroke-opacity=".5"/></pattern></defs>`);
  S.ink.forEach(b => {
    const ex = inkExcuse(b);
    parts.push(`<rect x="${w.x0 - 40}" y="${b.vpos}" width="${w.x1 - w.x0 + 80}"
       height="${b.height}" fill="url(#hatch)" stroke="var(--warn)"
       stroke-width="${ex ? 2 : 4}" stroke-dasharray="${ex ? '10 8' : ''}"
       opacity="${ex ? .5 : 1}"/>`);
    parts.push(`<text x="${w.x1 + 50}" y="${b.vpos + b.height / 2 + 12}"
       font-size="32" fill="var(--warn)" font-family="ui-sans-serif,sans-serif"
       opacity="${ex ? .6 : 1}">${ex ? '✓ ' + esc(ex.note)
       : 'unaccounted ink — i'}</text>`);
  });

  // ---- the figure layer ---------------------------------------------------
  // Always drawn, dimmed when the pointer is not on this track. Free rectangles:
  // x comes from the box, never from `win()`, which is the whole difference
  // between this track and the one above.
  S.figs.forEach((f, i) => {
    const t = FT[f.label], c = t ? t.color : '#999';
    const on = S.figTrack && (i === S.figSel || i === S.figHover);
    const dim = S.figTrack ? 1 : (FIGV.dim_figs ?? 0.45);
    parts.push(`<rect x="${f.x0}" y="${f.y0}" width="${f.x1 - f.x0}"
       height="${f.y1 - f.y0}" fill="${c}" fill-opacity="${on ? .26 : .12}"
       stroke="${c}" stroke-width="${on ? 6 : 3}" opacity="${dim}"
       ${ST.fig_proposal ? 'stroke-dasharray="18 10"' : ''}/>`);
    parts.push(`<text x="${f.x0 + 10}" y="${f.y0 + 42}" font-size="34"
       fill="${c}" opacity="${dim}" font-family="ui-sans-serif,sans-serif"
       >${t ? t.name : f.label}${ST.fig_proposal ? ' (proposed)' : ''}</text>`);
  });
  // The armed corner, and the box it and the cursor describe. Nothing is
  // committed until a click; the corner is drawn whether or not the pointer is
  // on the page, because it is the thing that stays true when the cursor wanders.
  if (S.figPending) {
    const p = S.figPending;
    const c = FT[p.label] ? FT[p.label].color : 'var(--accent)';
    const pr = pendingRect();
    if (pr)
      parts.push(`<rect x="${pr.x0}" y="${pr.y0}" width="${pr.x1 - pr.x0}"
         height="${pr.y1 - pr.y0}" fill="${c}" fill-opacity=".18" stroke="${c}"
         stroke-width="4" stroke-dasharray="14 9"/>`);
    // The corner itself. Deliberately direction-neutral — a mark implying which
    // way the box grows would be wrong, since the opposite corner may be put
    // anywhere. A ring so it reads against both a white margin and a halftone.
    parts.push(`<circle cx="${p.x}" cy="${p.y}" r="15" fill="${c}"
       stroke="var(--bg)" stroke-width="5"/>`);
  }
  if (S.figDrag) {
    const d = S.figDrag, c = S.figCur && FT[S.figCur] ? FT[S.figCur].color
                                                     : 'var(--accent)';
    parts.push(`<rect x="${d.x0}" y="${d.y0}" width="${d.x1 - d.x0}"
       height="${d.y1 - d.y0}" fill="${c}" fill-opacity=".22" stroke="${c}"
       stroke-width="4"/>`);
  }

  const pv = preview();
  if (pv && !S.figTrack) {
    const c = S.cur && T[S.cur] ? T[S.cur].color : 'var(--accent)';
    parts.push(`<rect x="${w.x0}" y="${pv[0]}" width="${w.x1 - w.x0}"
       height="${pv[1] - pv[0]}" fill="${c}" fill-opacity=".22" stroke="${c}"
       stroke-width="3"/>`);
  }
  if (S.pending !== null) {
    // The anchor. Drawn last so it sits on top of its own band and of any zone
    // it overlaps, and drawn whether or not the pointer is on the page — it is
    // the thing that is still true when the cursor has wandered off.
    const c = S.cur && T[S.cur] ? T[S.cur].color : 'var(--accent)';
    parts.push(`<line x1="0" y1="${S.pending}" x2="${P.w}" y2="${S.pending}"
       stroke="${c}" stroke-width="4"/>`);
  }
  // The cursor guide, which is the one thing that genuinely has no meaning once
  // the pointer is off the page.
  //
  // **A crosshair on the figure track, a single rule on the zone track**, and the
  // difference is the point rather than decoration: a zone takes only a y, so a
  // vertical line there would promise a freedom the page does not have. Toggling
  // the track used to look like the editor freezing — the zone preview correctly
  // stops following the cursor and nothing took its place — so the pointer now
  // says which of the two it is doing.
  if (S.inside && S.hoverY !== null) {
    const c = S.figTrack && S.figCur && FT[S.figCur]
            ? FT[S.figCur].color : 'var(--accent)';
    parts.push(`<line x1="0" y1="${S.hoverY}" x2="${P.w}" y2="${S.hoverY}"
       stroke="${c}" stroke-width="2" opacity=".8"/>`);
    if (S.figTrack && S.hoverX !== null)
      parts.push(`<line x1="${S.hoverX}" y1="${C.y0}" x2="${S.hoverX}"
         y2="${C.y1}" stroke="${c}" stroke-width="2" opacity=".8"/>`);
  }
  parts.push('</svg>');
  ov.innerHTML = parts.join('');
  bar();
  trackChips();
  issues();
}

function bar() {
  // The track pill, and the swatch reads off whichever track is live. Before
  // this the bar went on describing zone state while the pointer was drawing
  // figures, so the one control that had changed was the one thing unmentioned.
  const tp = document.getElementById('track');
  const figT = S.figTrack ? FT[S.figCur] : null;
  tp.textContent = S.figTrack ? 'FIGURES' : 'zones';
  tp.className = 'pill' + (S.figTrack ? ' on' : '');
  tp.title = `${CFG.actions.toggle_track || (FIG_ACTIONS.toggle_track || 'b')}`
           + ' switches track';
  if (S.figTrack) tp.style.background = figT ? figT.color : '';
  else tp.style.background = '';

  const t = S.figTrack ? figT : (S.cur ? T[S.cur] : null);
  document.getElementById('swatch').style.background = t ? t.color : 'transparent';
  document.getElementById('cur').textContent =
    t ? t.name : (S.figTrack ? '(no figure type)' : '(no type)');
  const anc = document.getElementById('anchor');
  anc.textContent = (ST.anchor.measured ? 'anchored' : ST.anchor.source) +
    (S.nudge ? ` ${S.nudge > 0 ? '+' : ''}${S.nudge}` : '');
  anc.className = 'pill' + (ST.anchor.measured ? '' : ' on');
  const w = windows();
  document.getElementById('col').textContent =
    w.length > 1 ? `col ${S.col + 1}/${w.length}` : '1 col';
  const sp = document.getElementById('split');
  sp.textContent = S.split === 'exempt' ? 'exempt — not a text page' : S.split;
  sp.className = 'pill' + (S.split === 'train' ? '' :
                           S.split === 'eval' ? ' on' : ' off');
  const ch = document.getElementById('chain');
  ch.textContent = 'chain'; ch.className = 'pill' + (S.chain ? ' on' : '');
  document.getElementById('count').textContent = S.figTrack
    ? (S.figs.length + ' box' + (S.figs.length === 1 ? '' : 'es') +
       (S.figsDirty ? ' •' : ''))
    : (S.zones.length + ' zone' + (S.zones.length === 1 ? '' : 's') +
       (S.dirty ? ' •' : ''));
  // Say what is under the cursor and what can be done to it. These operations
  // existed before this line did, and were undiscoverable for want of it.
  const tgt = document.getElementById('target');
  if (S.figTrack) {
    // The figure track has no measure and no chain, so the zone affordances
    // below are all false here. Saying what *is* available is the whole fix: the
    // track draws on a drag, and a drag leaves nothing on screen until it starts.
    const j = S.figSel >= 0 ? S.figSel : S.figHover;
    if (S.figPending)
      tgt.textContent = 'corner set at the picture’s '
        + (S.capBeside ? 'top-right' : 'foot')
        + ' · click the opposite corner · '
        + (FIG_ACTIONS.caption_beside || 'B') + ' moves it beside · '
        + 'right-click drops it';
    else if (j >= 0) {
      const f = S.figs[j], ft = FT[f.label];
      tgt.textContent = `${ft ? ft.name : f.label} · `
        + (S.figSel === j ? 'press a figure key to change it · Esc deselects'
                          : 'click to select')
        + ' · x deletes';
    } else {
      tgt.textContent = figT
        ? `drag to draw a ${figT.name}`
        : 'pick a figure type first';
    }
    tgt.className = S.figSel >= 0 ? 'sel' : '';
    document.querySelectorAll('.tk').forEach(el =>
      el.classList.toggle('sel', el.dataset.track === 'fig'
                                 && el.dataset.label === S.figCur));
    return;
  }
  const i = target();
  // The boundary case first, because on a partition it is the commonest one and it
  // now *overrides* selecting. Saying so is what keeps the override from reading as
  // the editor ignoring the click.
  if (S.nearEdge !== null && S.pending === null) {
    tgt.textContent = `edge at ${S.nearEdge} · click starts a zone here`;
    tgt.className = 'sel';
  } else if (i >= 0) {
    const z = S.zones[i], t = T[z.label];
    tgt.textContent = `#${i + 1} ${t ? t.name : z.label} · ` +
      (S.sel === i ? 'press a type key to change it · Esc deselects'
                   : 'click to select · shift+key retypes') +
      ' · x deletes';
    tgt.className = S.sel === i ? 'sel' : '';
  } else { tgt.textContent = ''; tgt.className = ''; }
  document.querySelectorAll('.tk').forEach(el =>
    el.classList.toggle('sel', el.dataset.track !== 'fig'
                               && el.dataset.label === S.cur));
}

// The chips of the track you are not on go quiet, so the panel says which half
// of the keyboard is live. Pressing `p` on the figure track does nothing, and a
// chip that still looks armed is the panel promising otherwise.
function trackChips() {
  document.querySelectorAll('.tk').forEach(el => {
    const mine = (el.dataset.track === 'fig') === S.figTrack;
    el.style.opacity = mine ? '1' : String(FIGV.dim_figs ?? 0.45);
  });
}

function issues() {
  const all = S.issues.length ? S.issues : orderWarnings().map(w => ({...w, kind: 'w'}));
  document.getElementById('issues').innerHTML = all.map(w =>
    `<div class="iss ${w.kind === 'e' ? 'e' : 'w'}${w.exempted ? ' x' : ''}">` +
    `${w.rule}: ${w.detail}${w.exempted ? ' — exempted' : ''}</div>`).join('');
}

function say(m, cls) {
  const el = document.getElementById('msg');
  el.textContent = m; el.className = cls || '';
}

// ---- editing
// A type may declare its own height, for a shape the book repeats at one size —
// the running title is a single line of fixed size, so only its top is ever in
// question and it costs one click rather than two.
function autoH() {
  const t = T[S.cur];
  return (t && t.default_height) || 0;
}
function gapAfter(label) {
  const t = T[label];
  return (t && t.gap_after) || 0;
}
// Whether the chain carries on past this type at all. Default true; off for the
// types that end the column (footnotes, the signature line) and for the catch-all,
// whose neighbours are by definition unpredictable. Guessing a top that is usually
// wrong costs a right-click every time, which is worse than not guessing.
function chainAfter(label) {
  const t = T[label];
  return !t || t.chain_after !== false;
}
// Where the chain resumes after a zone of this type: its foot, plus whatever dead
// space the page predictably leaves below it. Null when the type ends the chain.
function resume(label, y1) {
  return chainAfter(label) ? y1 + gapAfter(label) : null;
}

function place(y0, y1) {
  if (!S.cur) { say('pick a type first', 'bad'); return; }
  S.zones.push({label: S.cur, y0, y1, column: S.col});
  S.pending = S.chain ? resume(S.cur, y1) : null;
  S.sel = -1; S.dirty = true; S.issues = [];
  const nxt = (CFG.auto_select.after || {})[S.cur];
  if (nxt) S.cur = nxt;
  render();
}

// The band a click would commit right now, or null. Drawn as the preview, so what
// a one-click type is about to place is never a guess.
function preview() {
  const h = autoH();
  if (S.pending !== null) {
    if (h) return [S.pending, S.pending + h];
    if (S.hoverY === null) return null;
    return [Math.min(S.pending, S.hoverY), Math.max(S.pending, S.hoverY)];
  }
  // With no anchor set there is nothing tentative to preserve, so a fixed-height
  // band only tracks a pointer that is actually on the page.
  if (h && S.inside && S.hoverY !== null) return [S.hoverY, S.hoverY + h];
  return null;
}
function hit(y) {
  for (let i = S.zones.length - 1; i >= 0; i--)
    if (y >= S.zones[i].y0 && y <= S.zones[i].y1) return i;
  return -1;
}
function nearestEdge(i, y) {
  const z = S.zones[i];
  return Math.abs(y - z.y0) <= Math.abs(y - z.y1) ? 'y0' : 'y1';
}
// The exact y of an existing boundary within grabbing distance, or null.
//
// Separate from `edgesAt` and deliberately stingier. That one collects every edge
// on a boundary so a shift-drag moves both sides together; this one answers "is the
// click *on* a boundary", and it has to leave a zone's middle clickable or a zone
// becomes impossible to select. Hence the per-zone cap: the grab band is never more
// than a third of the zone's height, so even at `min_zone_h_px` the middle third
// still selects. Returns the boundary's own coordinate, not the click's, so a new
// zone starts flush against the old one and the partition stays a partition.
function anchorAt(y) {
  const snap = 10 * pxPerScreen();
  let best = null;
  S.zones.forEach(z => {
    const band = Math.min(snap, (z.y1 - z.y0) / 3);
    for (const e of [z.y0, z.y1])
      if (Math.abs(y - e) <= band &&
          (best === null || Math.abs(e - y) < Math.abs(best - y))) best = e;
  });
  return best;
}
// What an edit acts on: the zone clicked, or failing that the one under the
// cursor. One rule, so `x`, the nudges and a retype never disagree about their
// subject — and a selection survives the pointer wandering off the zone.
function target() { return S.sel >= 0 ? S.sel : S.hover; }

// ---- keyboard selection
//
// `S.zones` is in the order the zones were drawn, which on a revised page is not
// the order they sit in. Everything the arrows do is in **reading order**, since
// that is the only order visible on screen; the array index is an identity, as it
// is everywhere else in this project.
function byY() {
  return S.zones.map((z, i) => i).sort((a, b) => S.zones[a].y0 - S.zones[b].y0);
}
function below(i) {
  const o = byY(), k = o.indexOf(i);
  return k >= 0 && k < o.length - 1 ? o[k + 1] : -1;
}
// Clamped at both ends rather than wrapped. Wrapping would throw the view a whole
// leaf on a keypress that looks like a step, and the stop is the tell that you are
// at the end — the same reason the page arrows do not wrap round the corpus.
function stepSel(d) {
  if (!S.zones.length) return;
  const o = byY(), cur = target();
  // **From no selection, either arrow starts at the top.** A page arrives with
  // nothing selected, and the direction of the first keypress is not a statement
  // about where to begin — walking a page always begins at its head, so `ArrowUp`
  // on arrival must not land on the footnotes. The selection is not carried across
  // a page: `nav` is a real navigation and the state is rebuilt from the server,
  // so this *is* the reset, applied where it is observable rather than as a flag
  // set on load. Setting `S.sel` at load time instead would break keying — a type
  // key retypes the selected zone, so a page would open with `p` meaning "relabel
  // the running title" rather than "the next zone is a paragraph".
  if (cur < 0) { S.sel = o[0]; }
  else {
    const k = o.indexOf(cur);
    S.sel = o[Math.min(o.length - 1, Math.max(0, k + d))];
  }
  S.hover = -1;
  revealZone(S.sel);
}
// Page-wise, like the edge hover, and for the same reason: at this zoom the leaf is
// about two screens, so the movement wanted is "show me the other half", and a
// smooth scroll would be a thing to wait for. Steps until the zone is on screen —
// bounded, since a zone taller than the viewport can never satisfy the test, and
// then its top edge is the one to show.
function revealZone(i) {
  const z = S.zones[i];
  if (!z) return;
  const step = Math.max(80, wrap.clientHeight - VIEW.edge_overlap_px);
  const pad = VIEW.edge_overlap_px / 2;
  for (let n = 0; n < 40; n++) {
    // Re-read every pass: both rects are live, so a scroll above is already in
    // them, and the loop is over "is it on screen yet" rather than over arithmetic
    // predicting where it landed.
    const r = img.getBoundingClientRect(), w = wrap.getBoundingClientRect();
    if (!r.height) return;
    const s = r.height / ST.page.h;
    const top = r.top + z.y0 * s, bot = r.top + z.y1 * s;
    const was = wrap.scrollTop;
    if (top < w.top + pad) wrap.scrollTop -= step;
    else if (bot > w.bottom - pad && top > w.top + pad) wrap.scrollTop += step;
    else break;
    if (wrap.scrollTop === was) break;   // hit an end; nothing more to show
  }
}

function esc(s) {
  return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}
// Matched on the band's midpoint, as the server does — the band is re-measured
// from the raster each run and its edges move by a pixel or two, so an edge test
// would silently stop matching.
function inkExcuse(b) {
  const mid = b.vpos + b.height / 2;
  return S.inkEx.find(r => r.y0 <= mid && mid <= r.y1) || null;
}
function inkAt(y) {
  return S.ink.find(b => y >= b.vpos - 20 && y <= b.vpos + b.height + 20) || null;
}

// Page pixels per screen pixel, so a grab tolerance stays the same size under the
// hand at any zoom.
function pxPerScreen() {
  const r = img.getBoundingClientRect();
  return r.width ? ST.page.w / r.width : 1;
}

// Every zone edge within grabbing distance of y. A vertical partition shares its
// boundaries — chain mode makes the next zone's top exactly the last one's bottom —
// so dragging one boundary has to move both sides of it, or the drag opens a gap
// or an overlap that the editor then has to repair by hand.
function edgesAt(y) {
  const snap = 10 * pxPerScreen();
  const out = [];
  S.zones.forEach((z, i) => {
    if (Math.abs(y - z.y0) <= snap) out.push({i, edge: 'y0'});
    if (Math.abs(y - z.y1) <= snap) out.push({i, edge: 'y1'});
  });
  return out;
}
// The edges that *are* this boundary, rather than the ones near enough to grab.
//
// `edgesAt`'s window answers "which boundary did the pointer mean", and is
// generous on purpose — 10 screen pixels, so tens of page pixels at working zoom.
// The keyboard already knows which edge it holds, so reusing that window there
// swept up the neighbour across a small gap and carried it along: nearly half the
// boundaries in this store leave a gap of a few pixels, so a resize translated the
// pair and the gap survived every keypress, which is not what "resize" means.
//
// Coincident edges still move together, and must: they are one boundary, and moving
// only one side of it opens an overlap in a store whose partition check refuses one.
function edgesSharing(y) {
  const out = [];
  S.zones.forEach((z, i) => {
    if (Math.abs(y - z.y0) <= 1) out.push({i, edge: 'y0'});
    if (Math.abs(y - z.y1) <= 1) out.push({i, edge: 'y1'});
  });
  return out;
}

ov.addEventListener('mousemove', e => {
  if (S.figTrack) {
    const p = ptAt(e);
    S.hoverY = p.y; S.hoverX = p.x; S.inside = true;
    S.figHover = figHit(p);
    if (S.figDrag) {
      S.figDrag.x0 = Math.min(S.figDrag._ax, p.x);
      S.figDrag.x1 = Math.max(S.figDrag._ax, p.x);
      S.figDrag.y0 = Math.min(S.figDrag._ay, p.y);
      S.figDrag.y1 = Math.max(S.figDrag._ay, p.y);
    }
    edgeScroll(e.clientY);
    render();
    return;
  }
  S.hoverY = yAt(e);
  S.inside = true;
  S.hover = hit(S.hoverY);
  // Holds the boundary's coordinate rather than a boolean: the status line names
  // it, and a click will anchor there exactly. It was a bool that nothing read.
  S.nearEdge = S.drag ? S.nearEdge : anchorAt(S.hoverY);
  edgeScroll(e.clientY);
  if (S.drag) {
    // Move every edge that was on this boundary, together, so the partition
    // stays a partition. Each is clamped so a zone cannot be dragged inside out.
    for (const g of S.drag) {
      const z = S.zones[g.i];
      if (g.edge === 'y0') z.y0 = Math.min(S.hoverY, z.y1 - 4);
      else z.y1 = Math.max(S.hoverY, z.y0 + 4);
    }
    S.dirty = true; S.issues = [];
  }
  render();
});
// The page range actually on screen right now, in page coordinates. Scroll
// position decides it, so when the view is scrolled to an extreme this is the
// extreme of the printed content — which is what makes overshooting resolve to
// "the top of the text" rather than to some arbitrary row.
function visibleBand() {
  const r = img.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
  const sc = ST.page.h / r.height;
  const top = (Math.max(wr.top, r.top) - r.top) * sc;
  const bot = (Math.min(wr.bottom, r.bottom) - r.top) * sc;
  return [Math.max(top, ST.content.y0), Math.min(bot, ST.content.y1)];
}

ov.addEventListener('mouseleave', e => {
  // Overshooting the top or bottom resolves to that edge rather than being
  // discarded. Running a zone to the first or last line of the page is the
  // commonest thing a partition has to do, and pixel-hunting the boundary for it
  // is the one part of the flow that cannot be done by feel. Leaving *sideways* —
  // for the panel — keeps the last position instead: no edge was aimed at.
  //
  // `hoverY` is kept either way. Blanking it read as "cancelled" when the anchor
  // is in fact still set and the next click still commits.
  const r = img.getBoundingClientRect();
  const raw = (e.clientY - r.top) * (ST.page.h / r.height);
  const [vt, vb] = visibleBand();
  if (raw < vt) S.hoverY = Math.round(vt);
  else if (raw > vb) S.hoverY = Math.round(vb);
  S.inside = false; S.hover = -1; S.nearEdge = null;
  edgeStop(); render();
});
// Right-click cancels a half-placed zone and breaks the chain. Chaining is right
// for the common case — a partition shares its boundaries — but a page has plenty
// of whitespace where the next zone does not start at the last one's foot, and
// reaching for Escape mid-click is a hand off the mouse every time.
ov.addEventListener('contextmenu', e => {
  e.preventDefault();
  if (S.figTrack) { S.figPending = null; S.figSel = -1; render(); return; }
  S.pending = null;
  S.sel = -1;
  render();
});
ov.addEventListener('mousedown', e => {
  // On the figure track a plain drag *is* the placement gesture — the idiom is
  // `lines_ui.py`'s, which has drawn free rectangles over this same raster for
  // as long as the line editor has existed. Nothing here is shift-modified,
  // because unlike a zone edge there is no second thing a drag could mean.
  if (S.figTrack) {
    // With a corner armed the gesture is click-to-finish, not drag: starting a
    // fresh rectangle here would silently discard the hand-off. Right-click or
    // Esc drops the corner, after which dragging works as usual.
    if (e.shiftKey || !S.figCur || S.figPending) return;
    e.preventDefault();
    const p = ptAt(e);
    S.figDrag = {_ax: p.x, _ay: p.y, x0: p.x, y0: p.y, x1: p.x, y1: p.y};
    return;
  }
  // Shift makes a drag an edge adjustment. Plain clicks stay unambiguous — the
  // primary flow must never have to wonder whether it was a click or a grab, and
  // chain mode puts the cursor on an existing edge constantly.
  if (!e.shiftKey) return;
  const g = edgesAt(yAt(e));
  if (!g.length) return;
  e.preventDefault();
  S.drag = g;
});
window.addEventListener('mouseup', () => {
  edgeStop();
  if (S.figDrag) {
    const d = S.figDrag;
    S.figDrag = null;
    // Below the floor it was a click, not a drag, and a click is how an armed
    // caption is adopted. Committing a 3 px box instead would be the editor
    // taking a slip of the hand as a claim about the page.
    const min = ((CFG.figures || {}).min_size_px) || 24;
    if (d.x1 - d.x0 >= min && d.y1 - d.y0 >= min)
      addFig({label: S.figCur, x0: d.x0, y0: d.y0, x1: d.x1, y1: d.y1});
    render();
    return;
  }
  if (S.drag) { S.drag = null; render(); }
});
ov.addEventListener('click', e => {
  if (S.figTrack) {
    if (e.shiftKey) return;
    // Mid-placement a click always finishes the box, exactly as it does on the
    // zone track — only an idle click can mean "select", or landing on the
    // picture you just drew would select it instead of completing its caption.
    const pr = pendingRect();
    if (pr) {
      const min = ((CFG.figures || {}).min_size_px) || 24;
      if (pr.x1 - pr.x0 >= min && pr.y1 - pr.y0 >= min) {
        S.figPending = null;
        addFig(pr);
      } else {
        say('too small — the opposite corner has to clear min_size_px', 'bad');
      }
    } else {
      S.figSel = figHit(ptAt(e));
    }
    render();
    return;
  }
  if (e.shiftKey) return;
  const y = yAt(e);
  // Mid-placement, a click always finishes the zone. Only an idle click can mean
  // "select", so the primary flow is never interrupted by landing on a zone —
  // and with chain mode a click lands on an existing boundary constantly.
  if (S.pending === null) {
    // **A click on an existing boundary starts a zone there, it does not select.**
    // `hit` is inclusive of both edges, so before this the commonest act on a
    // partition — carry on from where the last zone stopped — landed inside the
    // zone above and selected it, and the anchor had to be placed by eye just below
    // the line instead. Anchoring on the boundary's own coordinate also means the
    // new zone butts exactly against the old one rather than a pixel or two off.
    const at = anchorAt(y);
    if (at !== null) {
      S.sel = -1;
      const ah = autoH();
      if (ah) { place(at, at + ah); return; }
      S.pending = at; render(); return;
    }
    const i = hit(y);
    if (i >= 0) { S.sel = (S.sel === i ? -1 : i); render(); return; }
    S.sel = -1;
  }
  const h = autoH();
  if (h) {
    // Height is known, so the click settles the whole zone. When the chain is
    // already holding a top, that top wins and the click is the confirmation —
    // which is what the preview has been showing all along.
    const top = S.pending !== null ? S.pending : y;
    place(top, top + h);
    return;
  }
  if (S.pending === null) { S.pending = y; render(); return; }
  place(Math.min(S.pending, y), Math.max(S.pending, y));
});

// ---- server
async function post(path, body) {
  const r = await fetch(path, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!r.ok) throw new Error((await r.json()).error || r.statusText);
  return r.json();
}
// Writing `gt/zones/` from a view that is not `gt` is an **adoption**, not a save,
// and it asks. Without this, `s` while looking at a machine proposal silently turned
// the model's word into ground truth with the same keystroke that saves your own
// work — indistinguishable acts, one of which is the thing the two stores exist to
// keep apart. Once adopted the page has gt of its own, so it never asks again.
function confirmAdoption() {
  if (!ST.proposal && ST.shown !== 'paras') return true;
  const src = ST.proposal ? 'the segmenter' : 'the paragraph rule';
  return confirm(
    `Adopt ${S.zones.length} zones proposed by ${src} as ground truth for `
    + `${ST.ref}?\n\nThis writes gt/zones/, which is the tracked record of what a `
    + `human has been through. Nothing else writes there.`);
}

async function save() {
  // Caught here rather than as a 500 from the server, because the remedy is a
  // choice between three different statements and the page is where they are made.
  // Reachable in one obvious way: key a page, then delete every zone on it.
  if (!S.zones.length && S.split !== 'exempt') {
    say('no zones: press ' + (CFG.actions.toggle_split || 't') + ' for exempt if '
        + 'this is a plate, or ' + (CFG.actions.delete_page || 'X')
        + ' to un-key the page', 'bad');
    return;
  }
  if (!confirmAdoption()) { say('not adopted', 'bad'); return; }
  const body = {
    ref: ST.ref, split: S.split, exempt: S.exempt, nudge: S.nudge,
    ink_exempt: S.inkEx,
    zones: S.zones.map(z => ({label: z.label, y0: z.y0, y1: z.y1,
                              column: z.column, x0: z.x0, x1: z.x1})),
  };
  // **The `figs` key goes only when the figure track was actually touched.**
  // `zones blot` keys the segmenter's training rasters off `gt/fig/`'s mtimes,
  // so sending an unchanged figure list on every ordinary zone save would stale
  // all 252 blots and, through them, everything the zone model learns from.
  if (S.figsDirty) {
    body.fig_ids = ST.fig_ids;
    body.fig_exempt = S.figExempt;
    body.figs = S.figs.map(f => ({id: f.id, label: f.label,
                                  x0: f.x0, y0: f.y0, x1: f.x1, y1: f.y1}));
  }
  const res = await post('/save', body);
  if (res.fig_error) { say(res.fig_error, 'bad'); return res; }
  // The bands are re-measured against what was just written, so what is on screen
  // is always the finding for the zones as they now stand.
  S.ink = (res.uncovered || []).map(b => ({...b}));
  S.dirty = false;
  S.issues = res.errors.map(e => ({...e, kind: 'e', exempted: false}))
             .concat(res.warnings.map(w => ({...w, kind: 'w'})));
  // What is on screen is now ground truth, and the topbar has to say so. Before
  // this, adopting a proposal left the selector reading `gt —` and the banner still
  // claiming a machine proposal, so the one act the store split exists to make
  // visible was the one act with no visible outcome — and pressing `s` again
  // re-asked to adopt something already adopted.
  ST.keyed = true;
  ST.proposal = '';
  ST.shown = 'gt';
  if (ST.present) ST.present.gt = res.zones;
  ST.paras_zones = res.paras_zones;
  renderStores();
  let extra = '';
  if (S.figsDirty) {
    S.figsDirty = false;
    ST.fig_proposal = ''; ST.fig_ids = 'gt';
    if (ST.fig_present) ST.fig_present.gt = res.figs_saved;
    extra = ` · ${res.figs_saved} figure box(es)`;
    // The one thing a human has to leave the editor to finish. Said now, naming
    // the block, rather than left for `corpus figures` to find as an orphan.
    if ((res.readings_missing || []).length)
      extra += ` · key ${res.readings_missing.join(', ')} in data/readings.md`;
    S.issues = S.issues
      .concat((res.fig_errors || []).map(e => ({...e, kind: 'e', exempted: false})))
      .concat((res.fig_warnings || []).map(w => ({...w, kind: 'w'})));
  }
  say(`saved ${res.zones} zones to gt` + extra +
      (res.errors.length ? ` · ${res.errors.length} error(s)` : ''),
      res.errors.length ? 'bad' : 'ok');
  render();
  return res;
}

// The selector, redrawn from `ST` after a write. Server-rendered on load; this is
// the same rule applied to the one thing that can change without a navigation.
function renderStores() {
  const n = {
    gt: ST.present && ST.present.gt != null ? String(ST.present.gt) : '—',
    mz: ST.present && ST.present.mz != null ? String(ST.present.mz) : '—',
    zones: ST.keyed ? '→gt' : (ST.present && ST.present.mz != null ? '→mz' : '—'),
    paras: ST.paras_zones == null ? '—' : String(ST.paras_zones),
  };
  for (const k in n) {
    const el = document.querySelector('#store-' + k + ' .n');
    if (el) el.textContent = n[k];
  }
  const p = document.getElementById('proposal');
  if (p && !ST.proposal) p.remove();
}
async function nav(ref) {
  if (!ref) return;
  // Dirty only. An unconditional save would mint an empty zone file for every
  // page skimmed past, and an empty file is a claim: "looked at, holds nothing".
  if (S.dirty || S.figsDirty) { try { await save(); } catch (err) {
    say('not saved: ' + err.message, 'bad'); return; } }
  // The nudge rides along: a page needing one usually has neighbours that do too,
  // and the next page re-measures its own anchor regardless.
  location = `/?ref=${ref}` + (S.nudge ? `&nudge=${S.nudge}` : '') +
    (ST.store !== 'zones' ? `&store=${ST.store}` : '');
}

// Switching store is a navigation, not a client-side toggle: the zones, the
// proposal snapping and the presence counts are all resolved server-side, and
// re-deriving any of them here would be a second implementation of the store rule.
// It saves first for the same reason `nav` does — and a proposal is never dirty on
// arrival, so cycling away from one still writes nothing.
async function navStore(name) {
  if (S.dirty || S.figsDirty) { try { await save(); } catch (err) {
    say('not saved: ' + err.message, 'bad'); return; } }
  location = `/?ref=${ST.ref}` + (S.nudge ? `&nudge=${S.nudge}` : '') +
    (name !== 'zones' ? `&store=${name}` : '');
}

// ---- keys
window.addEventListener('keydown', async e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  // A type key retypes the **selected** zone, and only otherwise sets what the
  // next one will be. Selecting is an explicit act — a click on an idle canvas —
  // so this cannot surprise anyone who has not just performed it, and misreading
  // a paragraph start for a continuation is the likeliest mistake on the page.
  // Shift does the same to the merely hovered zone, without the click.
  const retype = (e.shiftKey && S.hover >= 0) ? S.hover
               : (!e.shiftKey && S.sel >= 0 && KEY[k]) ? S.sel : -1;
  if (retype >= 0 && KEY[k.toLowerCase()]) {
    S.zones[retype].label = KEY[k.toLowerCase()];
    S.dirty = true; S.issues = [];
    render(); e.preventDefault(); return;
  }
  // On the figure track the type keys select a figure type and the zone types are
  // out of reach — one keyboard, but the track decides which half of it is live,
  // so `p` cannot place a paragraph band while somebody is drawing pictures.
  if (S.figTrack && FKEY[k]) {
    if (S.figSel >= 0) { S.figs[S.figSel].label = FKEY[k]; S.figsDirty = true; }
    else { S.figCur = FKEY[k]; S.figPending = null; }
    render(); e.preventDefault(); return;
  }
  if (!S.figTrack && KEY[k]) {
    S.cur = KEY[k]; S.issues = []; render(); e.preventDefault(); return;
  }
  // A named key carries its shift as a prefix, since it has no case to carry it in.
  // Looked up before the bare name, so `Shift+ArrowUp` cannot fall through to
  // whatever plain `ArrowUp` does — the two are a selection and a resize.
  const a = (e.shiftKey && k.length > 1 && ACT['Shift+' + k])
          || ACT[k] || ACT[k.toLowerCase()];
  if (!a) return;
  e.preventDefault();
  switch (a) {
    case 'toggle_track': {
      S.figTrack = !S.figTrack;
      // Each track drops whatever it had half-placed. Carrying an armed anchor
      // across the switch would fire it on a click meant for the other track.
      S.pending = null; S.sel = -1; S.figPending = null; S.figSel = -1;
      if (S.figTrack && !S.figCur) S.figCur = 'GraphicZone';
      // Announced, because the visible consequence of the switch is that
      // something *stops*: the zone preview no longer follows the cursor. Silence
      // there reads as a freeze rather than a mode.
      const ft = S.figTrack && FT[S.figCur];
      say(S.figTrack
          ? `figure track — drag to draw a ${ft ? ft.name : 'box'}`
          : 'zone track — click a top, then a bottom', 'ok');
      break; }
    case 'caption_beside':
      // Moves the armed corner to the picture's top-right, for the ~19 plate
      // captions this book sets vertically beside their picture rather than
      // under it. Only ever re-poses the corner; it commits nothing.
      S.capBeside = !S.capBeside;
      if (S.figPending && S.figPending.from) armCaption(S.figPending.from);
      break;
    case 'cancel': S.pending = null; S.sel = -1; S.figPending = null; break;
    case 'undo':
      if (S.zones.length) {
        S.zones.pop(); S.dirty = true; S.issues = []; S.sel = -1;
        const last = S.zones[S.zones.length - 1];
        S.pending = S.chain && last ? resume(last.label, last.y1) : null;
      }
      break;
    case 'delete': {
      if (S.figTrack) {
        const j = S.figSel >= 0 ? S.figSel : S.figHover;
        if (j < 0) break;
        S.figs.splice(j, 1);
        S.figSel = -1; S.figHover = -1; S.figPending = null; S.figsDirty = true;
        break;
      }
      const i = target();
      if (i < 0) break;
      S.zones.splice(i, 1);
      // Both cleared: every index above the removed one has shifted, so keeping
      // either would point at a different zone than the one that was targeted.
      S.sel = -1; S.hover = -1; S.dirty = true; S.issues = [];
      break; }
    // Absorb the zone below into this one. The commonest correction on a machine
    // page by a long way — 42% of gt boundaries are same-label, so the paragraph
    // rule and the decoder both over-split, and re-drawing the pair by hand is four
    // clicks for a boundary that just needs to go.
    //
    // **The surviving label is this zone's**, always, including where the two
    // differ. The alternative is to refuse a mixed merge, which would be the tool
    // declining exactly the case worth having it for — `MainZone-P` swallowing the
    // `MainZone-Continued` under it is a paragraph the decoder split in two.
    case 'merge_down': {
      const i = target();
      if (i < 0) { say('nothing selected to merge', 'bad'); break; }
      const j = below(i);
      if (j < 0) { say('nothing below this zone', 'bad'); break; }
      const a1 = S.zones[i], b1 = S.zones[j];
      // Across columns the union is not a band of anything: on a two-column page
      // the zone below in reading order can be the head of the other column, and
      // merging them would produce geometry that means nothing on the paper.
      if (a1.column !== b1.column) {
        say('the zone below is in another column', 'bad'); break;
      }
      const label = a1.label;
      a1.y0 = Math.min(a1.y0, b1.y0); a1.y1 = Math.max(a1.y1, b1.y1);
      S.zones.splice(j, 1);
      // The array shifted under the selection if the absorbed zone sat earlier in
      // it — the drawing order and the reading order are not the same list.
      S.sel = j < i ? i - 1 : i;
      S.hover = -1; S.dirty = true; S.issues = [];
      say(b1.label === label ? 'merged' : `merged as ${label}`, 'ok');
      break; }
    case 'sel_up': stepSel(-1); break;
    case 'sel_down': stepSel(1); break;
    case 'ink_exempt': {
      if (S.hoverY === null) break;
      const b = inkAt(S.hoverY);
      if (!b) { say('no unaccounted ink under the cursor', 'bad'); break; }
      const had = inkExcuse(b);
      if (had) {   // second press takes the ruling back
        S.inkEx = S.inkEx.filter(r => r !== had);
        S.dirty = true; say('ruling withdrawn'); break;
      }
      // The reason is required, and is the whole point of the record: this is the
      // only check that can see a dropped zone, so every suppression of it is a
      // claim that something on the paper is not printing.
      const note = (window.prompt(
        'Why is this ink not type? (e.g. "scanner smudge", "gutter blob", '
        + '"offset from facing page")') || '').trim();
      if (!note) { say('not ruled — a reason is required', 'bad'); break; }
      S.inkEx.push({y0: b.vpos, y1: b.vpos + b.height, note});
      S.dirty = true; say('ruled not type: ' + note, 'ok');
      break; }
    case 'anchor_left': S.nudge -= 4; S.dirty = true; S.issues = []; break;
    case 'anchor_right': S.nudge += 4; S.dirty = true; S.issues = []; break;
    case 'anchor_reset': S.nudge = 0; S.dirty = true; S.issues = []; break;
    case 'cycle_column':
      S.col = (S.col + 1) % windows(S.side).length; break;
    case 'toggle_split': {
      // train -> eval -> exempt -> train. `exempt` is the plates, maps, foldouts
      // and blanks: not text pages at all, so in neither the training nor the
      // eval set, and not judged by layout rules written for a text page.
      const order = ['train', 'eval', 'exempt'];
      S.split = order[(order.indexOf(S.split) + 1) % order.length];
      S.dirty = true; S.issues = [];
      break; }
    case 'toggle_chain': S.chain = !S.chain; break;
    case 'segment_page': {
      // Asks, for two reasons. It is shift+s, one key from `save`, and the two do
      // opposite things — one writes what you keyed into gt, the other replaces
      // this page's machine prediction. And it overwrites: any existing mz for the
      // page goes, including one you may have been comparing against.
      const had = ST.present && ST.present.mz;
      if (!confirm(
        `Run the segmenter on ${ST.ref}?\n\n`
        + `Writes mz/zones/`
        + (had ? `, replacing the ${had} zones already predicted for it` : '')
        + `. gt/zones/ is untouched.`)) { say('not segmented', 'bad'); break; }
      say('segmenting…');
      let res;
      // `single` and `force` both: the dialog above already said it replaces what
      // is there, and asking for this one page is what excuses a page ruled exempt.
      try { res = await post('/predict',
                             {ref: ST.ref, force: true, single: true}); }
      catch (err) { say('segmenter: ' + err.message, 'bad'); break; }
      // Reload so the prediction is on screen, since the whole point was to look at
      // it. Writes `mz/zones/`; `gt` is untouched until you adopt.
      //
      // **Staying put where the view already answers `mz`.** On an unkeyed page the
      // view falls through to the machine store by its own rule, so pinning `mz`
      // adds nothing and costs the thing the view is for: navigate on to a keyed
      // neighbour with `mz` pinned and it opens blank, or worse, on that page's
      // prediction instead of the work already done. Pin only from a store that
      // would otherwise keep showing something else.
      say(`segmented: ${res.zones} zones`, 'ok');
      await navStore(ST.store === 'zones' && !ST.keyed ? 'zones' : 'mz');
      return;
    }
    case 'delete_page': {
      if (!ST.keyed) { say('nothing keyed for this page', 'bad'); break; }
      // Typed, not pressed. The other destructive key here (`x`) removes one zone
      // and is undoable in the session; this removes the page from the tracked
      // store along with its split and every exemption, so it asks for the ref
      // itself rather than a click that a mis-hit could supply.
      const t = prompt(
        `Un-key ${ST.ref}? This deletes it from gt/zones/ and drops its split and `
        + `exemptions. Type the ref to confirm:`);
      if (t !== ST.ref) { say('not deleted', 'bad'); break; }
      const res = await post('/delete', {ref: ST.ref});
      say(`deleted ${ST.ref} (was ${res.zones} zones)`, 'ok');
      // `ST` is the page as it was served; the file is gone now, so the flag has to
      // follow or a second `X` would ask to delete what is not there, and `save`
      // would think there was something to overwrite.
      ST.keyed = false;
      if (ST.present) ST.present.gt = null;
      ST.paras_zones = null;
      renderStores();
      S.zones = []; S.dirty = false; S.issues = []; S.split = 'train';
      break;
    }
    // Forward on `/`, back on `?`. One direction only meant that comparing two
    // stores — the thing the selector exists for — cost a full lap through the
    // third every time you wanted the previous one back.
    case 'cycle_store':
    case 'cycle_store_back': {
      const order = ['zones', 'gt', 'mz', 'paras'];
      const i = order.indexOf(ST.store);
      const step = a === 'cycle_store' ? 1 : order.length - 1;
      await navStore(order[(i + step) % order.length]);
      return;
    }
    case 'exempt': {
      if (S.figTrack) {
        const g = figWarnings().find(w => !w.exempted);
        if (g) { S.figExempt.push(g.rule); S.figsDirty = true;
                 say(`exempted ${g.rule}`, 'ok'); }
        else if (S.figExempt.length) { S.figExempt = []; S.figsDirty = true;
                                       say('figure exemptions cleared', 'ok'); }
        break;
      }
      const f = orderWarnings().find(w => !w.exempted);
      if (f) { S.exempt.push(f.rule); S.dirty = true;
               say(`exempted ${f.rule}`, 'ok'); }
      else if (S.exempt.length) { S.exempt = []; S.dirty = true;
                                  say('exemptions cleared', 'ok'); }
      break; }
    case 'nudge_back': case 'nudge_forward': {
      const i = target();
      if (i < 0) break;
      const d = a === 'nudge_back' ? -2 : 2;
      // A shared boundary moves whole, so the partition never opens an overlap —
      // but only edges that genuinely coincide are shared. A neighbour across a gap
      // stays put, which is what lets a nudge close one. With a zone selected but
      // the cursor elsewhere, the bottom edge is the one meant.
      const edge = S.hoverY === null || S.hover !== i
                 ? 'y1' : nearestEdge(i, S.hoverY);
      const at = S.zones[i][edge];
      for (const g of edgesSharing(at)) {
        const z = S.zones[g.i];
        if (g.edge === 'y0') z.y0 = Math.min(z.y0 + d, z.y1 - 4);
        else z.y1 = Math.max(z.y1 + d, z.y0 + 4);
      }
      S.dirty = true; S.issues = [];
      break; }
    case 'page_list':
      // Save first: the list reports what is on disk, so walking to it with
      // unsaved work would show this page as it was before the last few zones.
      if (S.dirty || S.figsDirty) { try { await save(); } catch (err) {
        say('not saved: ' + err.message, 'bad'); return; } }
      location = `/list?ref=${ST.ref}`;
      return;
    case 'zoom_in': zoom += 1; localStorage.setItem('zonesZoom', zoom); break;
    case 'zoom_out': zoom -= 1; localStorage.setItem('zonesZoom', zoom); break;
    case 'save': try { await save(); } catch (err) { say(err.message, 'bad'); } return;
    case 'prev_page': await nav(ST.prev); return;
    case 'next_page': await nav(ST.next); return;
    case 'done': await done(); return;
  }
  render();
});

async function done() {
  try { if (S.dirty || S.figsDirty) await save(); } catch (err) {
    say('not saved — not stopping: ' + err.message, 'bad'); return; }
  await post('/done', {});
  say('server stopped — you can close this tab', 'ok');
}

img.addEventListener('load', centreColumn);
document.querySelectorAll('.tk').forEach(el =>
  el.addEventListener('click', () => { S.cur = el.dataset.label; render(); }));
document.getElementById('btnsave').addEventListener('click',
  () => save().catch(err => say(err.message, 'bad')));
document.getElementById('btndone').addEventListener('click', done);
document.querySelectorAll('.pill.store').forEach(el =>
  el.addEventListener('click', () => navStore(el.dataset.store)));
window.addEventListener('resize', render);
window.addEventListener('beforeunload', e => {
  if (S.dirty || S.figsDirty) { e.preventDefault(); e.returnValue = ''; }
});

// Auto-select on load is the same rule as after a commit, applied to whatever the
// page already ends with: a fresh page starts on `fresh_page` (the running title),
// and a page being revised picks up after its own last zone.
if (!S.zones.length) {
  S.cur = CFG.auto_select.fresh_page || CFG.types[0].label;
} else {
  const last = S.zones.slice().sort((a, b) => a.y0 - b.y0).pop();
  S.cur = (CFG.auto_select.after || {})[last.label] || last.label;
}
render();
requestAnimationFrame(centreColumn);
"""


def render_html(ref: str, root: Path, cfg: dict, nudge: int = 0,
                itinerary: list[str] | None = None,
                itinerary_name: str = "", store: str = "zones") -> str:
    """The whole editor, as one string. No static files, as in `review.py`."""
    st = page_state(ref, root, cfg, nudge, itinerary, store)
    st["itinerary"] = itinerary_name
    acts = {k: v for k, v in (cfg.get("actions") or {}).items()
            if not k.startswith("_")}
    pretty = {"cycle_store": "show gt / mz / paras / the view",
              "cycle_store_back": "…and back",
              "segment_page": "run the segmenter on this page (asks)",
              "delete_page": "un-key this page (types the ref)",
              "cancel": "cancel / break chain", "undo": "undo last zone",
              "delete": "delete zone under cursor",
              "merge_down": "absorb the zone below (keeps this label)",
              "sel_up": "select the zone above", "sel_down": "select the zone below",
              "anchor_left": "nudge column left 4 px",
              "anchor_right": "nudge column right 4 px",
              "anchor_reset": "reset to measured anchor",
              "cycle_column": "cycle column", "toggle_split": "train / eval / exempt",
              "toggle_chain": "chain mode", "exempt": "exempt the order warning",
              "ink_exempt": "rule ink under cursor not type",
              "page_list": "the whole list and its statuses",
              "save": "save", "done": "save and stop server",
              "prev_page": "previous page", "next_page": "next page",
              "nudge_back": "resize: edge up 2 px",
              "nudge_forward": "resize: edge down 2 px",
              "zoom_in": "zoom in", "zoom_out": "zoom out",
              "toggle_track": "switch to the figure track (and back)",
              "caption_beside": "put the armed caption beside, not below"}
    # One keyboard, so the figure track's actions are listed with the rest rather
    # than in their own panel. `load_config` has already refused any key bound in
    # two of the three namespaces, and `test_zones_ui.py` requires every action
    # here to have both a `case` in the JS and a `<kbd>` below.
    acts.update({k: v for k, v in
                 ((cfg.get("figures") or {}).get("actions") or {}).items()
                 if not k.startswith("_")})

    h = ["<!doctype html><html><head><meta charset='utf-8'>",
         f"<title>zones {st['ref']}</title><style>{CSS}</style></head><body>"]

    h.append("<div id='bar'>")
    h.append(f"<b>{st['ref']}</b>")
    if itinerary_name:
        h.append(f"<span class='pill' title='itinerary: {itinerary_name}'>"
                 + (f"{st['index']}/{st['total']}" if st["on_list"]
                    else f"off-list · {st['total']}")
                 + f" · {st['done']} done</span>")
    else:
        h.append(f"<span class='pill'>{st['index']}/{st['total']}</span>")
    # **Which track the pointer is on, first and loudest.** Everything else in
    # this bar describes the page; this describes what a click will do, and
    # without it pressing the toggle read as the editor freezing — the zone
    # preview stops following the cursor, which is correct and looked broken.
    h.append("<span class='pill' id='track'></span>")
    h.append("<span><i id='swatch'></i><span id='cur'></span></span>")
    h.append("<span class='pill' id='anchor'></span>")
    h.append("<span class='pill' id='col'></span>")
    h.append("<span class='pill' id='split'></span>")
    h.append("<span class='pill' id='chain'></span>")
    # The store selector: which store is being looked at, what each holds, and which
    # one answered. Three facts rather than one, because the useful question at a
    # glance is "is there anything in the other store" — visible here instead of
    # discovered by switching. `/` cycles.
    sel = st.get("store", "zones")
    for name in STORES:
        if name == "zones":
            n = f"→{st.get('view')}" if st.get("view") else "—"
        elif name == "paras":
            n = str(st.get("paras_zones", "—"))
        else:
            c = (st.get("present") or {}).get(name)
            n = "—" if c is None else str(c)
        klass = "pill store on" if name == sel else "pill store"
        h.append(f"<span class='{klass}' id='store-{name}' data-store='{name}' "
                 f"title='press / to cycle · {STORE_HELP[name]}'>{name} "
                 f"<span class='n'>{n}</span></span>")
    # Only ever set when the machine store is what answered. An unlabelled proposal
    # would look exactly like a page someone had already keyed, which is the one
    # confusion the two stores exist to prevent.
    if st.get("proposal"):
        dropped = st.get("proposal_dropped") or []
        short = st.get("proposal_short") or 0
        h.append("<span class='pill on' id='proposal' title='"
                 "predicted by the segmenter, not yet ruled on — correct it and "
                 "save, and it becomes ground truth'>machine proposal"
                 + (f" · {short} sliver(s) under the minimum height dropped"
                    if short else "")
                 + (f" · {len(dropped)} label(s) dropped: {', '.join(dropped)}"
                    if dropped else "")
                 + "</span>")
    h.append("<span id='count'></span>")
    h.append("<span id='target'></span>")
    h.append("<span id='msg'></span>")
    h.append("<button id='btnsave'>save</button><button id='btndone'>Done</button>")
    h.append("</div>")

    h.append("<div id='wrap'><div id='stage'>")
    h.append(f"<img id='img' src='/page/{st['ref']}.png' alt='page {st['ref']}'>")
    h.append("<div id='ov'></div>")
    h.append("</div></div>")

    h.append("<div id='panel'><h4>types</h4>")
    for t in cfg["types"]:
        # A one-click type is worth flagging in the list: its height is not being
        # judged, so its behaviour under the pointer differs from every other type.
        note = ""
        if t.get("default_height"):
            note = (f"<em title='fixed {t['default_height']} px, one click"
                    + (f", chain resumes {t['gap_after']} px below"
                       if t.get("gap_after") else "") + "'>1&#8203;click</em>")
        if t.get("chain_after") is False:
            note += ("<em title='the chain stops here — the next top is left "
                     "unset rather than guessed'>ends</em>")
        h.append(f"<div class='tk' data-track='zone' data-label=\"{t['label']}\">"
                 f"<i style='background:{t.get('color', '#999')}'></i>"
                 f"<span>{t.get('name', t['label'])}</span>{note}"
                 f"<kbd>{t['key']}</kbd></div>")
    h.append("<h4>actions</h4>")
    for name, key in acts.items():
        h.append(f"<div class='key'><span>{pretty.get(name, name)}</span>"
                 f"<kbd>{key}</kbd></div>")
    h.append("<h4>drawing</h4>")
    h.append("<div class='key'><span>set top, then bottom</span><kbd>click ×2</kbd></div>")
    h.append("<div class='key'><span>cancel / break chain</span><kbd>right-click</kbd></div>")
    h.append("<h4>existing zones</h4>")
    h.append("<div class='key'><span>select one</span><kbd>click it</kbd></div>")
    h.append("<div class='key'><span>then change its type</span><kbd>type key</kbd></div>")
    h.append("<div class='key'><span>retype without selecting</span>"
             "<kbd>shift + type key</kbd></div>")
    h.append("<div class='key'><span>move a boundary</span><kbd>shift-drag</kbd></div>")
    h.append("<div class='key'><span>jump a screen</span>"
             "<kbd>hover top / bottom</kbd></div>")
    figs_cfg = cfg.get("figures") or {}
    if figs_cfg.get("types"):
        h.append("<h4>figure track</h4>")
        for t in figs_cfg["types"]:
            h.append(f"<div class='tk' data-track='fig' data-label=\"{t['label']}\">"
                     f"<i style='background:{t.get('color', '#999')}'></i>"
                     f"<span>{t.get('name', t['label'])}</span>"
                     f"<kbd>{t['key']}</kbd></div>")
        h.append("<div class='key'><span>draw a box</span><kbd>drag</kbd></div>")
        h.append("<div class='key'><span>set the opposite corner</span>"
                 "<kbd>click</kbd></div>")
        h.append("<div class='key'><span>drop it</span>"
                 "<kbd>right-click</kbd></div>")
        h.append("<div id='flags'>The figure track is a <em>parallel</em> store: "
                 "freely-placed rectangles over the picture and its caption, not "
                 "bands of the column, and its x comes from the pointer rather "
                 "than the measure — the one place in this editor where it does. "
                 "Committing a picture arms the caption's first corner at its "
                 "bottom-left, and one further click sets the opposite one — the "
                 "chain's hand-off in two dimensions, imputing no size. The "
                 "caption's <em>text</em> is "
                 "not keyed here: draw the box, save, and the banner names the "
                 "block to key in data/readings.md.</div>")
    h.append("<div id='flags'>Chain mode carries the last bottom edge into the next "
             "zone, so a run of prose is one key and one click each; right-click "
             "breaks it where the page leaves whitespace. The dashed guide is the "
             "column a click will use. Zones share their boundaries, so dragging "
             "one moves both sides of it and the partition stays whole.</div>")
    h.append("</div>")

    h.append("<div id='issues'></div>")
    h.append("<script>const CFG=" + json.dumps(cfg, ensure_ascii=False)
             + ";const ST=" + json.dumps(st, ensure_ascii=False) + ";</script>")
    h.append("<script>" + JS + "</script></body></html>")
    return "\n".join(h)


def ink_state(ref: str, root: Path, cfg: dict, recheck: bool = False) -> dict:
    """One page's uncovered-ink verdict, from the cache or by reading the raster.

    The cache is the point. This is the one check that opens the page image — ~0.27
    s against ~1 ms for everything else — but the editor already runs it on every
    page it opens and every page it saves, so by the time a list of keyed pages is
    worth looking at, the answers exist. The list reads them; only a page nobody has
    been through since it changed costs anything, and that one is asked for
    explicitly.
    """
    if not recheck:
        hit = zn.cached_ink(ref, root)
        if hit is not None:
            return dict(hit, ref=norm_ref(ref))
    return zn.record_ink(ref, zn.validate_page(ref, root, cfg, ink=True), root)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _ink_cell(ink: dict) -> str:
    """The verdict in one cell. `?` is not a failure — it is a page whose zones
    changed since anything last read its raster, which is exactly what the check
    button is for."""
    s = ink["state"]
    if s == "ink":
        n = ink.get("bands", 0)
        txt = f"{n} band" + ("" if n == 1 else "s")
    elif s == "ruled":
        txt = f"{ink.get('ruled', 0)} ruled"
    else:
        txt = {"clean": "—", "skip": "·", "unknown": "?"}.get(s, s)
    return txt + (" · stale" if ink.get("stale") else "")


LIST_CSS = webui.LIST_CSS + """
/* Zones-only: one bar per zone, in reading order — the page's composition at a
   glance, which a count cannot give. Hover names the type. */
.z{display:inline-block;width:7px;height:15px;border-radius:2px;margin-right:2px;
   vertical-align:-2px;cursor:help}
#inkrun{margin-left:auto}
td.ink{font-size:12px;color:var(--dim);white-space:nowrap;cursor:help}
td.ink[data-ink="ink"]{color:var(--warn);font-weight:600}
td.ink[data-ink="unknown"]{opacity:.5}
/* The scope link sits in the title because it changes what the title names — the
   universe of rows, not which of them are shown. It is not a filter. */
#scope{font-weight:400;text-decoration:none;color:inherit}
/* The force box is a control, not a selector; it never lights and never filters. */
#force{cursor:pointer}
#force input{cursor:pointer;margin:0}
"""

def render_list_html(root: Path, cfg: dict, itinerary: list[str] | None = None,
                     itinerary_name: str = "", current: str = "",
                     scope: str = "stores") -> str:
    """Every page in the work-list with its status, as one table.

    The counts alone never say *which* page, and a keying sweep is exactly the case
    where that is the question — the ref with an error, the four still to do. So the
    same information `harness zones check` prints goes on a page the editor can reach in
    one keystroke and leave in one click.

    Rendered without the raster (`ink=False`), because this is a list of 122 pages
    and the ink pass is ~0.20 s each — most of a minute before anything appeared. The
    ink column is therefore **read from the cache** every keyed page has already
    filled in by being opened. That check is the only one that can see a zone that
    was never drawn, so a list silent about it would be silent about exactly the
    fault the partition exists to catch — but a page whose verdict is not on hand
    reads `?`, and going and getting it is a button. Unknown is a state worth
    drawing; a stale verdict rendered as a live one is not.

    `scope="all"` widens the universe from "pages either store holds" to **every
    scan in the corpus**, which is what a whole-book segmentation run needs: the
    pages worth predicting are precisely the ones neither store has ever heard of,
    so the default view cannot show one. It costs a `validate_page` per row, but
    without the raster — over the 832 pages that is a stat and a parse each for the
    few that have files, and nothing at all for the rest.
    """
    by_label = zc.types_by_label(cfg)
    # Unscoped, the universe is **both stores**, not just the keyed one. A page with
    # a prediction and no ground truth is the only kind of work this list exists to
    # queue, and enumerating `gt/zones/` alone would mean the `proposed` state could
    # never appear on the default view — a column that cannot display its own value.
    # An itinerary still overrides it outright: a work-list is a work-list.
    if itinerary is not None:
        refs = itinerary
    elif scope == "all":
        refs = all_scans(root)
    else:
        refs = sorted(set(zn.zone_refs(root)) | set(zn.zone_refs(root, zn.MZDIR)),
                      key=parse_ref)
    rows = []
    n_keyed = n_err = n_warn = 0
    for ref in refs:
        r = zn.validate_page(ref, root, cfg, ink=False)
        keyed = r["keyed"]
        n_keyed += bool(keyed)
        n_err += len(r["errors"])
        n_warn += len(r["warnings"])
        if not keyed:
            # Two kinds of "to do", and the difference is the whole review queue:
            # a page with a prediction waiting to be ruled on, and a page nobody and
            # nothing has touched. One file-existence test, ~1 ms, same as every
            # other column here bar the ink verdict.
            state = "proposed" if zn.has_zones(ref, root, zn.MZDIR) else "todo"
        elif r["errors"]:
            state = "err"
        elif r["warnings"]:
            state = "warn"
        else:
            state = "ok"
        detail = "; ".join(sorted({e["rule"] for e in r["errors"]})) \
            or "; ".join(sorted({w["rule"] for w in r["warnings"]})) or ""
        labels = [z["label"] for z in zn.read_zones(ref, root)]
        # An unkeyed page and one ruled not-a-text-page are settled without asking:
        # neither can have ink left over, so neither is ever queued for a check.
        if state in ("todo", "proposed") or r["split"] == "exempt":
            ink = {"state": "skip"}
        else:
            ink = zn.cached_ink(ref, root) or {"state": "unknown"}
        # Both stores, per page, as counts. The `proposed` state only ever names a
        # page with *no* ground truth, so until this column existed a prediction
        # sitting beside keyed work was invisible in the list — and "is there
        # anything to compare against" is the question that sends you to a page.
        # One parse each, in a loop that already parses gt and validates it.
        n_mz = (len(zn.read_zones(ref, root, store=zn.MZDIR))
                if zn.has_zones(ref, root, zn.MZDIR) else None)
        rows.append((ref, state, r["split"] or "", r["zones"], n_mz,
                     detail, labels, ink))

    n_ink = sum(1 for r in rows if r[7]["state"] == "ink")
    n_unknown = sum(1 for r in rows if r[7]["state"] == "unknown")
    n_mz_rows = sum(1 for r in rows if r[4] is not None)

    h = ["<!doctype html><html><head><meta charset='utf-8'>",
         f"<title>zones · {itinerary_name or 'store'}</title>",
         f"<style>{CSS}{LIST_CSS}</style></head><body>"]
    h.append("<div id='head'>")
    # Named for what it enumerates. Keyed off the mz *column* rather than off the
    # `proposed` state, which only ever fires where there is no ground truth — with
    # a prediction over the whole corpus that count is zero and the heading would
    # have read `gt/zones` over a table half of which is the machine's.
    title = (itinerary_name or ("every scan" if scope == "all" else
             "gt/zones + mz/zones" if n_mz_rows else "gt/zones"))
    h.append(f"<h1>{title} — {len(rows)} pages")
    # The scope toggle is a link, not a filter chip: it changes what the server
    # enumerates, and a page in neither store has no row to hide or show. Absent
    # under an itinerary, which overrides the universe outright.
    if itinerary is None:
        other = "stores" if scope == "all" else "all"
        h.append(f"<a class='chip' id='scope' href='/list?scope={other}"
                 + (f"&ref={current}" if current else "") + "' title='"
                 + ("back to the pages either store holds"
                    if scope == "all" else
                    "every scan in the corpus, including pages neither store has "
                    "heard of — what a whole-book segmentation run needs")
                 + "'>" + ("just the stores" if scope == "all"
                           else f"all {len(all_scans(root))} scans") + "</a>")
    h.append("</h1>")
    n_prop = sum(1 for r in rows if r[1] == "proposed")
    h.append(f"<p>{n_keyed} keyed · {len(rows) - n_keyed} to do"
             + (f" ({n_prop} predicted)" if n_prop else "")
             + (f" · {n_mz_rows} with mz" if n_mz_rows else "") + " · "
             f"{n_err} error{'' if n_err == 1 else 's'} · "
             f"{n_warn} warning{'' if n_warn == 1 else 's'} · "
             f"<span id='inkprog'>{n_ink} with uncovered ink, {n_unknown} "
             f"unchecked</span> — press <kbd>Esc</kbd> or click a ref to go back"
             "<span id='shown'></span></p>")
    # Filter chips. Types carry their own colour so the strip in each row and the
    # chip that selects it are recognisably the same thing.
    h.append("<div id='filters'>")
    h.append("<span class='chip' id='segrun' title='run the segmenter on the "
             "checked pages — shift-click a checkbox to take a range. Writes "
             "mz/zones/; gt is untouched'>segment selected</span>")
    # Off by default, and the default is the safe one: a page that already has a
    # prediction is left alone. Over a whole-book run the pages worth the GPU time
    # are the ones with nothing, and re-predicting the rest would overwrite the very
    # files someone may be comparing against — including, after a retrain, replacing
    # output whose ProcessingStep records a *different* model sha, which is the one
    # thing in the store that says which model spoke.
    h.append("<label class='chip' id='force' title='by default a page that already "
             "has mz is skipped; tick this to re-run the segmenter over it'>"
             "<input type='checkbox' id='forcebox'> overwrite existing mz</label>")
    h.append("<span class='chip' data-state='todo'>still to do</span>")
    h.append("<span class='chip' data-state='proposed'>machine proposal</span>")
    h.append("<span class='chip' data-state='err'>has errors</span>")
    h.append("<span class='chip' data-ink='ink'>uncovered ink</span>")
    if n_unknown:
        # Explicit, because it is ~0.20 s a page of raster work and the only slow
        # thing this list can do. Everything else here is already paid for.
        h.append(f"<span class='chip' id='inkrun'>check ink · {n_unknown} "
                 f"page{'' if n_unknown == 1 else 's'}</span>")
    for t in cfg["types"]:
        h.append(f"<span class='chip' data-label=\"{t['label']}\">"
                 f"<i style='background:{t.get('color', '#999')}'></i>"
                 f"{t.get('name', t['label'])}</span>")
    h.append("</div></div>")

    h.append("<div id='wrapl'><table><thead><tr>"
             "<th class='pick'><input type='checkbox' id='pickall'></th>"
             "<th>page</th><th>status</th><th>split</th>"
             "<th class='num' title='zones in gt/zones/'>gt</th>"
             "<th class='num' title='zones in mz/zones/'>mz</th>"
             "<th>composition</th><th>ink</th><th>findings</th>"
             "</tr></thead><tbody>")
    for ref, state, split, nz, n_mz, detail, labels, ink in rows:
        here = " class='here'" if ref == current else ""
        # One bar per zone, in reading order. A count says how many; this says
        # what kind and in what order, which is what a glance down the list is for.
        strip = "".join(
            f"<i class='z' style='background:"
            f"{by_label.get(lab, {}).get('color', '#999')}' title=\""
            f"{by_label.get(lab, {}).get('name', lab)}\"></i>" for lab in labels)
        # A keyed page holding nothing prints `0`, not blank: that is a plate a human
        # ruled on, and blank is what a page nobody has reached looks like.
        gt_cell = "" if state in ("todo", "proposed") else str(nz)
        h.append(f"<tr{here} data-state='{state}' data-ink='{ink['state']}' "
                 f"data-mz='{'y' if n_mz is not None else 'n'}' "
                 f"data-labels=\"{' '.join(sorted(set(labels)))}\">"
                 f"<td class='pick'><input type='checkbox' data-ref='{ref}'></td>"
                 f"<td class='ref'><a href='/?ref={ref}'>{ref}</a></td>"
                 f"<td><i class='dot s-{state}'></i>{state}</td>"
                 f"<td>{split}</td>"
                 f"<td class='num'>{gt_cell}</td>"
                 f"<td class='num dim mz'>{'' if n_mz is None else n_mz}</td>"
                 f"<td>{strip}</td>"
                 f"<td class='ink' data-ref='{ref}' data-ink='{ink['state']}' "
                 f"title=\"{_esc(ink.get('note', ''))}\">"
                 f"{_ink_cell(ink)}</td>"
                 f"<td class='detail'>{detail}</td></tr>")
    h.append("</tbody></table></div>")
    back = f"/?ref={current}" if current else "/"
    h.append("<script>" + r"""
const rows = [...document.querySelectorAll('tbody tr')];
// A chip is a filter **iff it carries the attribute that says what it selects**.
// Several chips here are buttons or links wearing the same style, and the rule used
// to be a growing list of `:not(#id)` — which fails open: add another and it joins
// the filter set with an undefined key, hiding every row in the table.
const chips = [...document.querySelectorAll(
  '#filters .chip[data-state], #filters .chip[data-ink], #filters .chip[data-label]')];
const on = new Set();

// Any-of, not all-of: the question a filter answers here is "which pages have a
// block quote", not "which have every type I clicked". Selecting two widens the
// set, which is what the chips look like they do.
function apply() {
  let shown = 0;
  for (const tr of rows) {
    const labels = new Set((tr.dataset.labels || '').split(' ').filter(Boolean));
    const hit = !on.size || [...on].some(k =>
      k.startsWith('state:') ? tr.dataset.state === k.slice(6) :
      k.startsWith('ink:') ? tr.dataset.ink === k.slice(4) : labels.has(k));
    tr.style.display = hit ? '' : 'none';
    if (hit) shown++;
  }
  document.getElementById('shown').textContent =
    on.size ? ` · showing ${shown} of ${rows.length}` : '';
}
for (const c of chips) {
  const key = c.dataset.state ? 'state:' + c.dataset.state
            : c.dataset.ink ? 'ink:' + c.dataset.ink : c.dataset.label;
  c.addEventListener('click', () => {
    on.has(key) ? on.delete(key) : on.add(key);
    c.classList.toggle('on', on.has(key));
    apply();
  });
}
// ---- selection, and the segmenter over it
//
// Shift-click extends from the last box touched, over the rows *as filtered* — so a
// range means what it looks like on screen rather than what the unfiltered table
// would have given. `anchor` is the last plain click; shift without one behaves as a
// plain click, which is what every list in every file manager does.
const boxes = () => [...document.querySelectorAll("tbody tr:not([hidden]) td.pick input")];
let anchor = null;
document.querySelector('tbody').addEventListener('click', e => {
  const box = e.target.closest("td.pick input");
  if (!box) return;
  const all = boxes();
  if (e.shiftKey && anchor && all.includes(anchor)) {
    const [a, b] = [all.indexOf(anchor), all.indexOf(box)].sort((x, y) => x - y);
    for (let i = a; i <= b; i++) all[i].checked = box.checked;
  }
  anchor = box;
  countPicked();
});
const pickall = document.getElementById('pickall');
if (pickall) pickall.addEventListener('change', () => {
  boxes().forEach(b => { b.checked = pickall.checked; });
  anchor = null; countPicked();
});
const segrun = document.getElementById('segrun');
function picked() { return boxes().filter(b => b.checked); }
function countPicked() {
  const n = picked().length;
  if (segrun) segrun.textContent = n ? `segment ${n} selected` : 'segment selected';
}

// Sequential, and for the same reason as the ink pass below: this is GPU work in
// the process serving the editor. The model is loaded once server-side and stays
// resident, which is what makes a bulk run worth doing at all — paying the ~5 s load
// per page is the friction this replaces.
if (segrun) segrun.addEventListener('click', async () => {
  if (segrun.dataset.busy) return;
  const todo = picked();
  if (!todo.length) { segrun.textContent = 'nothing selected'; return; }
  // Asks once, before any of it. A whole-book run is a quarter of an hour of GPU
  // and 832 files, and the count is the only thing that distinguishes it from the
  // three-page run this button was built for.
  const force = !!(document.getElementById('forcebox') || {}).checked;
  const over = todo.filter(b => b.closest('tr').dataset.mz === 'y').length;
  if (todo.length > 20 && !confirm(
      `Segment ${todo.length} pages?\n\n`
      + (force
         ? `${over} of them already have a prediction and it will be replaced.\n\n`
         : over ? `${over} already have one and will be skipped.\n\n` : '')
      + `Writes mz/zones/. gt/zones/ is untouched. The tab has to stay open.`)) {
    segrun.textContent = 'not run'; return;
  }
  segrun.dataset.busy = '1'; segrun.classList.add('on');
  let done = 0, failed = 0, skipped = 0;
  for (const box of todo) {
    try {
      const r = await (await fetch('/predict', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ref: box.dataset.ref, force})})).json();
      if (r.error) throw new Error(r.error);
      const row = box.closest('tr');
      // The server decides what to skip, so the reason comes back rather than being
      // re-derived here — a client that decided for itself would be a second copy of
      // the rule, and the CLI sweep uses the first one.
      if (r.skipped) {
        skipped++;
        row.title = 'skipped: ' + r.skipped;
        box.checked = false;
      } else {
      row.title = `segmenter: ${r.zones} zones`;
      // The count is in hand, so the column it belongs in is filled now rather than
      // left for a reload. An unkeyed row also stops being `todo` — that state is
      // "nobody and nothing has touched this", and something just has.
      const cell = row.querySelector('td.mz');
      if (cell) { cell.textContent = r.zones; row.dataset.mz = 'y'; }
      if (row.dataset.state === 'todo') {
        row.dataset.state = 'proposed';
        const st = row.children[2];
        if (st) st.innerHTML = "<i class='dot s-proposed'></i>proposed";
      }
      box.checked = false;
      }
    } catch (e) { failed++; box.closest('tr').title = 'segmenter: ' + e.message; }
    segrun.textContent = `segmenting · ${++done}/${todo.length}`
                       + (skipped ? ` · ${skipped} skipped` : '')
                       + (failed ? ` · ${failed} failed` : '');
  }
  segrun.classList.remove('on');
  delete segrun.dataset.busy;
  segrun.textContent = `segmented ${done - failed - skipped}`
                     + (skipped ? ` · ${skipped} skipped` : '')
                     + (failed ? ` · ${failed} failed` : '');
});

// The ink pass, on demand and one page at a time. Sequential rather than parallel:
// it is CPU-bound raster work in the same process that serves the editor, and a
// burst of it would make the next page open slowly. Only the pages whose verdict
// is not on hand are asked — everything else was answered when it was keyed.
const runner = document.getElementById('inkrun');
const prog = document.getElementById('inkprog');
if (runner) runner.addEventListener('click', async () => {
  if (runner.dataset.busy) return;
  runner.dataset.busy = '1';
  runner.classList.add('on');
  const todo = [...document.querySelectorAll("td.ink[data-ink='unknown']")];
  let done = 0;
  for (const td of todo) {
    let r;
    try {
      r = await (await fetch('/ink?ref=' + td.dataset.ref)).json();
    } catch (e) {
      td.textContent = '!'; td.title = String(e); continue;
    }
    td.dataset.ink = r.state;
    td.parentElement.dataset.ink = r.state;
    td.textContent = r.state === 'ink' ? r.bands + (r.bands === 1 ? ' band' : ' bands')
                   : r.state === 'ruled' ? r.ruled + ' ruled'
                   : ({clean: '—', skip: '·'})[r.state] || r.state;
    if (r.stale) td.textContent += ' · stale';
    td.title = r.note || '';
    runner.textContent = `checking ink · ${++done}/${todo.length}`;
    apply();
  }
  const n = document.querySelectorAll("tr[data-ink='ink']").length;
  prog.textContent = `${n} with uncovered ink, 0 unchecked`;
  runner.remove();
});

addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    // Esc clears a filter first, and only leaves the list once it is unfiltered —
    // otherwise the one keystroke both discards the filter and the page.
    if (on.size) { on.clear(); chips.forEach(c => c.classList.remove('on')); apply(); }
    else location = 'BACKURL';
  }
});
""".replace("BACKURL", back) + "</script></body></html>")
    return "\n".join(h)


# ---------------------------------------------------------------- the server

def serve(ref: str, root: Path = Path("."), port: int = PORT,
          itinerary: list[str] | None = None, itinerary_name: str = "") -> None:
    """Serve the editor on 127.0.0.1 and accept saves.

    The shell — loopback bind, silent request log, traceback-on-page, the raster
    route, shutdown from the page — is `harness/webui.py`'s, shared with `review`
    and `ocr edit`. What stays here is the routing and what a save means.
    """
    from urllib.parse import parse_qs, urlparse

    root = Path(root)
    cfg = zc.load_config(root)
    start = norm_ref(ref)
    # Loaded on first use and kept — see the `/predict` route. A list holding one
    # slot rather than a global, so it dies with the server.
    segmenter: list = [None]

    class Handler(webui.EditorHandler):
        editor = "zones"
        fetched = ("/ink",)   # the list drives this from JS and parses JSON

        def get(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                q = parse_qs(u.query)
                r = (q.get("ref") or [start])[0]
                try:
                    nudge = int((q.get("nudge") or ["0"])[0])
                except ValueError:
                    nudge = 0
                sel = (q.get("store") or ["zones"])[0]
                if sel not in STORES:
                    sel = "zones"
                self.send_html(render_html(r, root, cfg, nudge, itinerary,
                                           itinerary_name, sel))
                return
            if u.path == "/list":
                q = parse_qs(u.query)
                cur = (q.get("ref") or [""])[0]
                sc = (q.get("scope") or ["stores"])[0]
                self.send_html(render_list_html(
                    root, cfg, itinerary, itinerary_name,
                    norm_ref(cur) if cur else "",
                    "all" if sc == "all" else "stores"))
                return
            if u.path == "/ink":
                q = parse_qs(u.query)
                try:
                    r = norm_ref((q.get("ref") or [""])[0])
                except ValueError:
                    self.send_error(404)
                    return
                # One page, the slow way if the cache cannot answer. The list drives
                # this itself, one call at a time, and only for the pages it drew
                # as unknown.
                self.send_json(ink_state(r, root, cfg))
                return
            if u.path.startswith("/page/") and u.path.endswith(".png"):
                # Through norm_ref, so the path cannot name a file outside `scans/`.
                try:
                    r = norm_ref(u.path[len("/page/"):-len(".png")])
                except ValueError:
                    self.send_error(404)
                    return
                self.send_png(zn.scan_for(r, root))
                return
            self.send_error(404)

        def post(self):
            # Every route here is a `fetch`, so a raise is reported to the page as
            # `{"error": …}` by the shell — never a blank failure.
            if self.path == "/done":
                self.send_json({})
                self.stop_from_page()
                return
            if self.path == "/predict":
                # One page per call, but the **model stays resident** between them —
                # loading it costs ~5 s, and a bulk run that paid that per page is
                # the clunkiness this replaces. The client drives the loop so it can
                # show progress, exactly as the ink runner does.
                payload = self.body_json()
                r = norm_ref(payload.get("ref", ""))
                # The same rule the CLI sweep uses, asked here so a bulk run
                # through the browser and one through the terminal cannot
                # disagree about what they left alone.
                why = zn.predict_skip(r, root, bool(payload.get("force")),
                                      single=bool(payload.get("single")))
                if why:
                    self.send_json({"ref": r, "skipped": why})
                    return
                if segmenter[0] is None:
                    segmenter[0] = zn.load_segmenter(zn.DEFAULT_MODEL, root)
                net, sha = segmenter[0]
                res = zn.predict_dp(r, root, net=net, sha=sha,
                                    model_path=zn.DEFAULT_MODEL, cfg=cfg)
                print(f"segmented {res['ref']}: {res['zones']} zones -> mz/zones/")
                self.send_json(res)
                return
            if self.path == "/delete":
                # The only route that removes keyed work. Confirmed on the page and
                # journalled here; `.prev` keeps it one deep either way.
                res = zn.delete_zones(self.body_json().get("ref", ""), root,
                                      commit=True)
                print(f"deleted {res['path']}: was {res['zones']} zones "
                      f"[{res['split'] or 'unmarked'}]")
                self.send_json(res)
                return
            if self.path != "/save":
                self.send_error(404)
                return
            res = save_payload(self.body_json(), root, cfg)
            note = f" · {len(res['errors'])} error(s)" if res["errors"] else ""
            print(f"saved {res['path']}: {res['zones']} zones "
                  f"[{res['labels'] or 'none'}] {res['split']}{note}")
            self.send_json(res)

    url = f"http://127.0.0.1:{port}/?ref={start}"
    banner = [f"zones {start} -> {url}   (Done button on the page, or ctrl-c)"]
    if itinerary:
        done = sum(1 for r in itinerary if zn.has_zones(r, root))
        banner.append(
            f"itinerary {itinerary_name}: {len(itinerary)} pages, {done} keyed")
    banner.append(f"store -> {zn.zone_dir(root)}")
    webui.run(Handler, port, url, banner)
