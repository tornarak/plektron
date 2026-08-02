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
    return res


# ------------------------------------------------------------------ the page

CSS = """
:root{--bg:#f6f5f3;--fg:#1c1b19;--dim:#6b675f;--line:#d8d4cc;--accent:#2e86ab;
      --warn:#a8620a;--warnbg:rgba(0.9, 0.4, 0.4, 0.4);--err:#a4232b;--errbg:#fbeceb}
@media(prefers-color-scheme:dark){:root{--bg:#16161a;--fg:#e8e6e1;--dim:#9a958c;
      --line:#33323a;--accent:#6ab6d8;--warn:#e0a250;--warnbg:#2f2517;
      --err:#e08b8b;--errbg:#2e1a1a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:13px/1.45 ui-sans-serif,system-ui,sans-serif}
#bar{position:fixed;top:0;left:0;right:0;height:38px;display:flex;gap:14px;
     align-items:center;padding:0 12px;background:var(--bg);
     border-bottom:1px solid var(--line);z-index:20;white-space:nowrap;
     overflow-x:auto}
#bar b{font-weight:600}
.pill{padding:1px 8px;border-radius:10px;border:1px solid var(--line);
      font-size:12px}
.pill.on{background:var(--accent);border-color:var(--accent);color:#fff}
.pill.off{background:var(--warn);border-color:var(--warn);color:#fff}
/* The store selector reads as one control: three adjacent pills, clickable, the
   selected one lit. `—` means that store holds nothing for this page, which is an
   answer and is why the pill still draws rather than being hidden. */
.pill.store{cursor:pointer;font-variant-numeric:tabular-nums}
.pill.store+.pill.store{margin-left:-1px}
#cur{font-weight:600}
#swatch{display:inline-block;width:11px;height:11px;border-radius:2px;
        vertical-align:-1px;margin-right:5px}
#target{color:var(--dim);font-size:12px}
#target.sel{color:var(--fg);font-weight:600}
#msg{margin-left:auto;color:var(--dim)}
#msg.bad{color:var(--err);font-weight:600}
#msg.ok{color:var(--accent)}
/* One scroll container for both axes: the edge-hover autoscroll needs a single
   element whose scrollTop it can drive, and the page is now sized to the text
   column rather than to the leaf, so it is routinely taller than the view. */
#wrap{position:fixed;top:38px;left:0;right:250px;bottom:0;overflow:auto;padding:10px}
/* The stage is a window onto the page's inked band, not the whole leaf: the top
   and bottom of a scan are blank paper, and scrolling through them is time spent
   on nothing. The image is positioned inside it and clipped. */
#stage{position:relative;line-height:0;margin:0 auto;overflow:hidden;
       box-shadow:0 1px 8px rgba(0,0,0,.18)}
#stage img{position:absolute;left:0;display:block;width:100%;height:auto;
           image-rendering:-webkit-optimize-contrast}
@media(prefers-color-scheme:dark){#stage img{filter:invert(1) hue-rotate(180deg)}}
#ov{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}
#panel{position:fixed;right:0;top:38px;width:250px;bottom:0;overflow-y:auto;
       border-left:1px solid var(--line);background:var(--bg);padding:10px 12px;
       z-index:15}
#panel h4{margin:14px 0 6px;font-size:11px;letter-spacing:.06em;
          text-transform:uppercase;color:var(--dim);font-weight:600}
#panel h4:first-child{margin-top:0}
.key{display:flex;justify-content:space-between;gap:8px;padding:1px 0;
     font-size:12px}
.key kbd{font:11px ui-monospace,monospace;background:var(--line);
         border-radius:3px;padding:0 5px}
.tk{display:flex;align-items:center;gap:6px;padding:2px 4px;border-radius:4px;
    cursor:pointer}
.tk:hover{background:var(--line)}
.tk.sel{background:var(--line);font-weight:600}
.tk i{width:11px;height:11px;border-radius:2px;flex:none}
.tk span{flex:1;font-style:normal}
.tk em{font-style:normal;font-size:10px;color:var(--dim);border:1px solid var(--line);
       border-radius:3px;padding:0 4px;cursor:help}
#flags{padding:6px 0;font-size:12px;color:var(--dim)}
#issues{position:fixed;left:0;bottom:0;max-width:calc(100% - 250px);z-index:18}
.iss{padding:6px 12px;border-top:1px solid var(--line);font-size:12px}
.iss.w{background:var(--warnbg);color:var(--warn)}
.iss.e{background:var(--errbg);color:var(--err);font-weight:600}
.iss.x{opacity:.62;font-style:italic}
button{font:inherit;padding:2px 10px;border:1px solid var(--line);border-radius:5px;
       background:var(--bg);color:var(--fg);cursor:pointer}
button:hover{background:var(--line)}
"""

JS = r"""
const T = {}, KEY = {};
CFG.types.forEach(t => { T[t.label] = t; KEY[t.key] = t.label; });
const ACT = {};
for (const [name, k] of Object.entries(CFG.actions || {}))
  if (!name.startsWith('_')) ACT[k] = name;

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
};
let zoom = parseFloat(localStorage.getItem('zonesZoom') || '0') || 0;

const img = document.getElementById('img'), ov = document.getElementById('ov');
const stage = document.getElementById('stage'), wrap = document.getElementById('wrap');
const VIEW = Object.assign({column_margin: 0.10, edge_band_px: 80,
                            edge_overlap_px: 140}, CFG.view || {});

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
  // the live column guide, so the measure a click will use is never a surprise
  const w = win();
  parts.push(`<rect x="${w.x0}" y="${C.y0}" width="${w.x1 - w.x0}"
     height="${C.y1 - C.y0}" fill="none" stroke="var(--accent)" stroke-width="2"
     stroke-dasharray="14 10" opacity=".38"/>`);
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
  // Ink the zones do not account for. Drawn under the preview so it never hides
  // what is being placed, and hatched rather than filled so it reads as a question
  // about the page rather than as another zone.
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

  const pv = preview();
  if (pv) {
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
  if (S.inside && S.hoverY !== null)
    parts.push(`<line x1="0" y1="${S.hoverY}" x2="${P.w}" y2="${S.hoverY}"
       stroke="var(--accent)" stroke-width="2" opacity=".8"/>`);
  parts.push('</svg>');
  ov.innerHTML = parts.join('');
  bar();
  issues();
}

function bar() {
  const t = S.cur ? T[S.cur] : null;
  document.getElementById('swatch').style.background = t ? t.color : 'transparent';
  document.getElementById('cur').textContent = t ? t.name : '(no type)';
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
  document.getElementById('count').textContent =
    S.zones.length + ' zone' + (S.zones.length === 1 ? '' : 's') +
    (S.dirty ? ' •' : '');
  // Say what is under the cursor and what can be done to it. These operations
  // existed before this line did, and were undiscoverable for want of it.
  const tgt = document.getElementById('target');
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
    el.classList.toggle('sel', el.dataset.label === S.cur));
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
  S.pending = null;
  S.sel = -1;
  render();
});
ov.addEventListener('mousedown', e => {
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
  if (S.drag) { S.drag = null; render(); }
});
ov.addEventListener('click', e => {
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
  const res = await post('/save', {
    ref: ST.ref, split: S.split, exempt: S.exempt, nudge: S.nudge,
    ink_exempt: S.inkEx,
    zones: S.zones.map(z => ({label: z.label, y0: z.y0, y1: z.y1,
                              column: z.column, x0: z.x0, x1: z.x1})),
  });
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
  say(`saved ${res.zones} zones to gt` +
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
  if (S.dirty) { try { await save(); } catch (err) {
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
  if (S.dirty) { try { await save(); } catch (err) {
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
  if (KEY[k]) { S.cur = KEY[k]; S.issues = []; render(); e.preventDefault(); return; }
  // A named key carries its shift as a prefix, since it has no case to carry it in.
  // Looked up before the bare name, so `Shift+ArrowUp` cannot fall through to
  // whatever plain `ArrowUp` does — the two are a selection and a resize.
  const a = (e.shiftKey && k.length > 1 && ACT['Shift+' + k])
          || ACT[k] || ACT[k.toLowerCase()];
  if (!a) return;
  e.preventDefault();
  switch (a) {
    case 'cancel': S.pending = null; S.sel = -1; break;
    case 'undo':
      if (S.zones.length) {
        S.zones.pop(); S.dirty = true; S.issues = []; S.sel = -1;
        const last = S.zones[S.zones.length - 1];
        S.pending = S.chain && last ? resume(last.label, last.y1) : null;
      }
      break;
    case 'delete': {
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
      if (S.dirty) { try { await save(); } catch (err) {
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
  try { if (S.dirty) await save(); } catch (err) {
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
  if (S.dirty) { e.preventDefault(); e.returnValue = ''; }
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
              "zoom_in": "zoom in", "zoom_out": "zoom out"}

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
        h.append(f"<div class='tk' data-label=\"{t['label']}\">"
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


LIST_CSS = """
table{border-collapse:collapse;width:100%;font-size:13px}
th{position:sticky;top:0;background:var(--bg);text-align:left;font-weight:600;
   font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);
   padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:5px 10px;border-bottom:1px solid var(--line)}
tr:hover td{background:var(--line)}
tr.here td{background:var(--line);font-weight:600}
td.ref a{color:var(--fg);text-decoration:none;font-weight:600}
td.ref a:hover{text-decoration:underline}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;
     margin-right:7px;vertical-align:-1px}
.s-todo{background:transparent;border:1px solid var(--dim)}
/* Hollow like `todo`, because it is one — nothing is keyed here. Coloured, because
   a page with a prediction waiting is a different piece of work from a blank one. */
.s-proposed{background:transparent;border:1px solid var(--warn)}
.s-ok{background:#3f8f5f}
.s-warn{background:var(--warn)}
.s-err{background:var(--err)}
td.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--dim)}
th.num{text-align:right}
/* The machine count reads as the fainter of the pair on purpose: the two columns
   are not equals, one being a tracked human ruling and the other a proposal. */
td.num.dim{opacity:.6}
td.detail{color:var(--dim);font-size:12px}
/* `unknown` is its own state and looks like one: a blank cell would read as
   "clean" where it means "nothing has read this page's raster since it changed". */
td.ink{font-size:12px;color:var(--dim);white-space:nowrap;cursor:help}
td.ink[data-ink="ink"]{color:var(--warn);font-weight:600}
td.ink[data-ink="unknown"]{opacity:.5}
#inkrun{margin-left:auto}
td.pick,th.pick{width:1%;padding-right:0}
td.pick input,th.pick input{cursor:pointer;margin:0}
/* One bar per zone, in reading order: the page's composition at a glance, which
   a count cannot give. Hover names the type. */
.z{display:inline-block;width:7px;height:15px;border-radius:2px;margin-right:2px;
   vertical-align:-2px;cursor:help}
#filters{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{display:flex;align-items:center;gap:6px;padding:2px 9px;border-radius:11px;
      border:1px solid var(--line);font-size:12px;cursor:pointer;user-select:none}
.chip:hover{background:var(--line)}
.chip.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.chip i{display:inline-block;width:9px;height:9px;border-radius:2px}
.chip.on i{outline:1px solid var(--bg)}
#shown{color:var(--dim);font-size:12px;margin-left:4px}
#head{position:sticky;top:0;background:var(--bg);padding:14px 16px 10px;
      border-bottom:1px solid var(--line);z-index:5}
#head h1{margin:0 0 4px;font-size:15px;display:flex;align-items:center;gap:10px}
/* The scope link sits in the title because it changes what the title names — the
   universe of rows, not which of them are shown. It is not a filter. */
#scope{font-weight:400;text-decoration:none;color:inherit}
/* The force box is a control, not a selector; it never lights and never filters. */
#force{cursor:pointer}
#force input{cursor:pointer;margin:0}
#head p{margin:0;color:var(--dim);font-size:12px}
#wrapl{padding:0 16px 40px}
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

    Loopback only and 404 on anything unrouted, as `review.serve` is: this holds
    unpublished editorial work and has no business being reachable. The one route
    beyond the two `review` needs is the raster — a 2824x3897 page as a base64 data
    URI is some 10 MB of markup per render, where `review`'s line crops are small
    enough that inlining them was the cheaper trick.
    """
    import json as _json
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    root = Path(root)
    cfg = zc.load_config(root)
    start = norm_ref(ref)
    # Loaded on first use and kept — see the `/predict` route. A list holding one
    # slot rather than a global, so it dies with the server.
    segmenter: list = [None]

    class Handler(BaseHTTPRequestHandler):
        # Silence the per-request log; see `review.serve` on the signature.
        def log_message(self, format: str, *args) -> None:
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
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
                try:
                    body = render_html(r, root, cfg, nudge, itinerary,
                                       itinerary_name, sel).encode("utf-8")
                except Exception as e:
                    self._send(500, "text/plain; charset=utf-8",
                               str(e).encode("utf-8"))
                    return
                self._send(200, "text/html; charset=utf-8", body)
                return
            if u.path == "/list":
                q = parse_qs(u.query)
                cur = (q.get("ref") or [""])[0]
                sc = (q.get("scope") or ["stores"])[0]
                try:
                    body = render_list_html(root, cfg, itinerary, itinerary_name,
                                            norm_ref(cur) if cur else "",
                                            "all" if sc == "all" else "stores")
                except Exception as e:
                    self._send(500, "text/plain; charset=utf-8",
                               str(e).encode("utf-8"))
                    return
                self._send(200, "text/html; charset=utf-8", body.encode("utf-8"))
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
                try:
                    rec = ink_state(r, root, cfg)
                except Exception as e:
                    self._send(500, "application/json",
                               _json.dumps({"error": str(e)}).encode("utf-8"))
                    return
                self._send(200, "application/json",
                           _json.dumps(rec, ensure_ascii=False).encode("utf-8"))
                return
            if u.path.startswith("/page/") and u.path.endswith(".png"):
                # Through norm_ref, so the path cannot name a file outside `scans/`.
                try:
                    r = norm_ref(u.path[len("/page/"):-len(".png")])
                except ValueError:
                    self.send_error(404)
                    return
                p = zn.scan_for(r, root)
                if not p.exists():
                    self.send_error(404)
                    return
                self._send(200, "image/png", p.read_bytes())
                return
            self.send_error(404)

        def do_POST(self):
            if self.path == "/done":
                self._send(200, "application/json", b"{}")
                # From another thread: `shutdown()` blocks until the serve loop
                # exits, and the serve loop is what is running this handler.
                threading.Thread(target=srv.shutdown, daemon=True).start()
                return
            if self.path == "/predict":
                # One page per call, but the **model stays resident** between them —
                # loading it costs ~5 s, and a bulk run that paid that per page is
                # the clunkiness this replaces. The client drives the loop so it can
                # show progress, exactly as the ink runner does.
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    payload = _json.loads(self.rfile.read(n) or b"{}")
                    r = norm_ref(payload.get("ref", ""))
                    # The same rule the CLI sweep uses, asked here so a bulk run
                    # through the browser and one through the terminal cannot
                    # disagree about what they left alone.
                    why = zn.predict_skip(r, root, bool(payload.get("force")),
                                          single=bool(payload.get("single")))
                    if why:
                        self._send(200, "application/json", _json.dumps(
                            {"ref": r, "skipped": why}).encode("utf-8"))
                        return
                    if segmenter[0] is None:
                        segmenter[0] = zn.load_segmenter(zn.DEFAULT_MODEL, root)
                    net, sha = segmenter[0]
                    res = zn.predict_dp(r, root, net=net, sha=sha,
                                        model_path=zn.DEFAULT_MODEL, cfg=cfg)
                except Exception as e:
                    self._send(500, "application/json",
                               _json.dumps({"error": str(e)}).encode("utf-8"))
                    return
                print(f"segmented {res['ref']}: {res['zones']} zones -> mz/zones/")
                self._send(200, "application/json",
                           _json.dumps(res, ensure_ascii=False).encode("utf-8"))
                return
            if self.path == "/delete":
                # The only route that removes keyed work. Confirmed on the page and
                # journalled here; `.prev` keeps it one deep either way.
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    payload = _json.loads(self.rfile.read(n) or b"{}")
                    res = zn.delete_zones(payload.get("ref", ""), root, commit=True)
                except Exception as e:
                    self._send(500, "application/json",
                               _json.dumps({"error": str(e)}).encode("utf-8"))
                    return
                print(f"deleted {res['path']}: was {res['zones']} zones "
                      f"[{res['split'] or 'unmarked'}]")
                self._send(200, "application/json",
                           _json.dumps(res, ensure_ascii=False).encode("utf-8"))
                return
            if self.path != "/save":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = _json.loads(self.rfile.read(n) or b"{}")
                res = save_payload(payload, root, cfg)
            except Exception as e:      # report it to the page, never a blank failure
                self._send(500, "application/json",
                           _json.dumps({"error": str(e)}).encode("utf-8"))
                return
            note = f" · {len(res['errors'])} error(s)" if res["errors"] else ""
            print(f"saved {res['path']}: {res['zones']} zones "
                  f"[{res['labels'] or 'none'}] {res['split']}{note}")
            self._send(200, "application/json",
                       _json.dumps(res, ensure_ascii=False).encode("utf-8"))

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/?ref={start}"
    print(f"zones {start} -> {url}   (Done button on the page, or ctrl-c)")
    if itinerary:
        done = sum(1 for r in itinerary if zn.has_zones(r, root))
        print(f"itinerary {itinerary_name}: {len(itinerary)} pages, {done} keyed")
    print(f"store -> {zn.zone_dir(root)}")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    else:
        print("done — server stopped from the page")
    finally:
        srv.server_close()
