"""The segmentation editor: one local page, two clicks a zone.

`review.py`, served, is the template — stdlib `ThreadingHTTPServer` on loopback, the
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

**The session is the server, not the page.** `ocr review` binds one ref because
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

from pathlib import Path

from . import figures as fg
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


def _fig_photos(ref: str, root: Path) -> list[dict]:
    """The source's photograph rects for this page, in the editor's coordinates.

    Each carries `covered`, so the track can draw an unaccounted photograph
    differently from an accounted one without re-deriving the rule the gate uses.
    An empty list means either no photographs or a page whose stored coordinates
    are in neither known space — `fig_ink` refuses to guess between them, and the
    editor inherits that refusal rather than drawing rects in the wrong place.
    """
    ink = fg.fig_ink(ref, root)
    if not ink["space"]:
        return []
    entry = fg.pdf_images_for(ref, root)
    pw, ph = fg._page_box(fg.alto_for(ref, root))
    rects, _ = fg._rects_in(entry, pw, ph)
    uncovered = {tuple(r) for r in ink["uncovered"]}
    return [{"x0": r[0], "y0": r[1], "x1": r[2], "y1": r[3],
             "covered": tuple(r) not in uncovered} for r in rects]


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

    `fig_photos` is the source PDF's own image placements — a witness neither a
    person nor a model produced — so the track can draw a photograph the keying has
    not accounted for, the way the zone editor draws a band of uncovered ink. Sent
    for every page, not only faulty ones: seeing the rects agree with the boxes is
    what makes the one that does not legible at a glance.
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
    exempt = fg.load_rule_exempt(root).get(ref, {})
    return {
        "figs": figs,
        "fig_proposal": proposal,
        # An `mz` proposal's ids are the machine's and mean nothing to
        # `data/readings.md`, so they are dropped rather than carried into a save
        # where they would look like keys. `save_figs` mints real ones.
        "fig_ids": "" if proposal else "gt",
        "fig_exempt": exempt,
        "fig_warnings": zc.fig_warnings(cfg, gt, exempt),
        "fig_photos": _fig_photos(ref, root),
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

    # **`in`, not `or []`, for both exemption layers.** `save_zones` passes
    # `exempt` through to `set_exempt` whenever it is not None, and `set_exempt`
    # and `set_ink_exempt` both pop the page's entry and rewrite their JSON with
    # no `.prev` and no journal. `.get(...) or []` made "the client never
    # mentioned this" identical to "the client cleared it", which is the one
    # reading a route must never manufacture — and it is what defeats the
    # `exclude_unset=True` the route already sends.
    exempt = (payload["exempt"] or []) if "exempt" in payload else None
    res = zn.save_zones(ref, out, root, split=payload.get("split"),
                        exempt=exempt)
    if "ink_exempt" in payload:
        zn.set_ink_exempt(ref, payload["ink_exempt"] or [], root)
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

    # None where the key was absent, so `save_figs` leaves the rule exemptions
    # standing rather than clearing them — `set_rule_exempt` pops and rewrites
    # with no backup, like the two above.
    rules = (payload["fig_exempt"] or {}) if "fig_exempt" in payload else None
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




def page_context(ref: str, root: Path, cfg: dict, nudge: int = 0,
                 itinerary: list[str] | None = None,
                 itinerary_name: str = "", store: str = "zones",
                 base: str = "/zones") -> dict:
    """Everything the editor page needs, as data.

    The markup is `harness/web/templates/zones/page.html` and the behaviour is
    `static/js/zones.js` — 68 KB that used to be interpolated into every page, on
    the one editor here that is navigated page-to-page with the arrow keys.
    """
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
              "cycle_column": "cycle column", "toggle_split": "train / eval",
              "leaf_kind": "say what this leaf is (not a text page)",
              "toggle_chain": "chain mode",
              "rule_exempt": "exempt the order warning",
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

    types = [{
        "label": t["label"], "key": t["key"],
        "name": t.get("name", t["label"]), "color": t.get("color", "#999"),
        # A one-click type is worth flagging in the list: its height is not being
        # judged, so its behaviour under the pointer differs from every other type.
        "oneclick": (f"fixed {t['default_height']} px, one click"
                     + (f", chain resumes {t['gap_after']} px below"
                        if t.get("gap_after") else "")
                     if t.get("default_height") else ""),
        "ends": t.get("chain_after") is False,
    } for t in cfg["types"]]
    figs_cfg = cfg.get("figures") or {}
    fig_types = [{"label": t["label"], "key": t["key"],
                  "name": t.get("name", t["label"]),
                  "color": t.get("color", "#999")}
                 for t in (figs_cfg.get("types") or [])]

    sel = st.get("store", "zones")
    stores = []
    for name in STORES:
        if name == "zones":
            n = f"\u2192{st.get('view')}" if st.get("view") else "\u2014"
        elif name == "paras":
            n = str(st.get("paras_zones", "\u2014"))
        else:
            c = (st.get("present") or {}).get(name)
            n = "\u2014" if c is None else str(c)
        stores.append({"name": name, "count": n, "on": name == sel,
                       "help": STORE_HELP[name]})

    st["base"] = base
    return {"st": st, "cfg": cfg, "types": types, "fig_types": fig_types,
            "stores": stores, "itinerary_name": itinerary_name,
            "actions": [{"label": pretty.get(k, k), "key": v}
                        for k, v in acts.items()],
            # **The vocabulary travels; the client does not hold a copy.** The
            # split cycle was a literal array in `zones.js`, which meant the set of
            # values lived in two places and only one of them was validated. A kind
            # added to `zones.LEAF_KINDS` and not to that array would be unreachable
            # from the editor and would look like the key not working.
            "text_splits": list(zn.TEXT_SPLITS),
            "leaf_kinds": [{"kind": k, "key": k[0]} for k in zn.LEAF_KINDS],
            "base": base}


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



def list_context(root: Path, cfg: dict, itinerary: list[str] | None = None,
                 itinerary_name: str = "", current: str = "",
                 scope: str = "stores", base: str = "/zones") -> dict:
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
    # **Both read once for the list, not once per row.** `validate_page` builds
    # `load_splits` when not handed one — seven `.lst` files re-read and every
    # name re-parsed through `norm_ref` — and `cached_ink` parses the whole cache
    # file to look up one entry. Over 832 rows that was 9.9s and 2.0s of a 5s
    # response, and 700k `norm_ref` calls. Neither changes per ref inside one
    # render, and the ink staleness check still runs per ref against live mtimes.
    splits = zn.load_splits(root)
    ink_cache = zn.load_ink_cache(root)
    rows = []
    n_keyed = n_err = n_warn = 0
    for ref in refs:
        r = zn.validate_page(ref, root, cfg, ink=False, splits=splits)
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
        if state in ("todo", "proposed") or r["split"] in zn.LEAF_KINDS:
            ink = {"state": "skip"}
        else:
            ink = zn.cached_ink(ref, root, ink_cache) or {"state": "unknown"}
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
    n_prop = sum(1 for r in rows if r[1] == "proposed")

    scope_link = None
    if itinerary is None:
        other = "stores" if scope == "all" else "all"
        scope_link = {
            "href": f"{base}/list?scope={other}"
                    + (f"&ref={current}" if current else ""),
            "title": ("back to the pages either store holds" if scope == "all"
                      else "every scan in the corpus, including pages neither "
                           "store has heard of — what a whole-book segmentation "
                           "run needs"),
            "label": ("just the stores" if scope == "all"
                      else f"all {len(all_scans(root))} scans"),
        }

    out = []
    for ref, state, split, nz, n_mz, detail, labels, ink in rows:
        out.append({
            "ref": ref, "state": state, "split": split, "here": ref == current,
            "ink_state": ink["state"], "ink_note": ink.get("note", ""),
            "ink_cell": _ink_cell(ink), "has_mz": n_mz is not None,
            "label_set": " ".join(sorted(set(labels))),
            # A keyed page holding nothing prints `0`, not blank: that is a plate
            # a human ruled on, and blank is what a page nobody has reached
            # looks like.
            "gt_cell": "" if state in ("todo", "proposed") else str(nz),
            "mz_cell": "" if n_mz is None else str(n_mz),
            "strip": [{"color": by_label.get(lab, {}).get("color", "#999"),
                       "name": by_label.get(lab, {}).get("name", lab)}
                      for lab in labels],
            "detail": detail,
        })
    return {
        "rows": out, "types": [{"label": t["label"],
                                "name": t.get("name", t["label"]),
                                "color": t.get("color", "#999")}
                               for t in cfg["types"]],
        "title": (itinerary_name or ("every scan" if scope == "all" else
                  "gt/zones + mz/zones" if n_mz_rows else "gt/zones")),
        "itinerary_name": itinerary_name, "scope_link": scope_link,
        "n_keyed": n_keyed, "n_err": n_err, "n_warn": n_warn, "n_prop": n_prop,
        "n_ink": n_ink, "n_unknown": n_unknown, "n_mz_rows": n_mz_rows,
        "back": f"{base}/?ref={current}" if current else f"{base}/",
        "base": base,
    }


# ---------------------------------------------------------------- the server
