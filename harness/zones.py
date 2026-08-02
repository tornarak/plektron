"""`gt/zones/`: the seven-type page segmentation, its store and its checks.

A zone here is a **fixed-width band of the text column** — two clicks give its top
and bottom, and its left and right edges come from `data/zones_config.json`, never
from the pointer. That is not a shortcut, it is the modelling claim: the book sets
one measure, ~1794 px across all three parts (see the config's `_provenance`), so a
page's zones form a vertical partition of a column whose width was decided by the
printer. Letting the editor drag an x-edge would offer a freedom the page does not
have, and every hand-drawn width would then be a small lie the trainer learns.

**Why a second store rather than more of `gt/seg/`.** That directory holds 122
pages under the full SegmOnto vocabulary, drawn as free polygons around ink. Both
the label set and the geometry regime differ from this one, and nothing in an ALTO
says which scheme produced it — the same absence of an internal witness that lost
18 pages of transcription when a file's role lived only in the directory holding
it. So the role lives in the directory again, and this time the directories do not
alias: `gt/seg/` is the old attempt, kept and read-only; `gt/zones/` is this one.
Every block written here also carries an **`mz_` id prefix**, so provenance travels
with the data and a file merged out of context is still identifiable.

**Side (verso/recto) is not stored.** The UI holds it, flips it with `v`, and
alternates it across page navigation; it reaches this module only as the input that
resolves a column window into an x-pair, and is gone by the time anything is
written. Consequently validation never asks which side a page was keyed as — only
whether each zone's x-extent is one this page's config offers at all, which is a
question with a mechanical answer.

Three files sit beside the pages, all tracked:

    gt/zones/_train.lst        the training split, one filename per line
    gt/zones/_eval.lst         the held-out split; `gt/seg/`'s format exactly
    gt/zones/_exempt.lst       plates, maps and blanks — not text pages at all,
                               and so in neither of the two above
    gt/zones/_rule_exempt.json {ref: [rule-id, ...]} — order rules ruled on
    gt/zones/_ink_exempt.json  {ref: [{y0,y1,note}]} — bands of ink ruled not type,
                               each with the reason it was ruled so

`_journal.jsonl` and the `.prev`/`.tmp` pairs are recovery data and ignored. So is
`_ink_cache.json`, which is derived: the uncovered-ink verdict per page, written by
whatever last ran the check, stamped with the mtimes it was true for.
"""
from __future__ import annotations
import os
import json
import time
from pathlib import Path

from lxml import etree

from .context import norm_ref, parse_ref
from .figures import read_blocks
from . import zones_config as zc
from functools import lru_cache

ZONEDIR = "gt/zones"
SCANS = "scans"

# The machine store and the view joining the two. `mz/zones/` holds what the trained
# segmenter emitted, raw: free polygons at whatever x kraken drew, kraken's own ids.
# `zones/` is a symlink farm over both in which the human file always wins — the same
# shape as `ocr/` over `gt/ocr/`, and the same rule: **reads may resolve through the
# view; writes never do.** Both are derived and gitignored, `mz/` because it is
# regenerable from `models/` and `scans-fig-blotted/`, the view because half its
# links point into `mz/` and a committed farm would dangle on clone.
MZDIR = "mz/zones"
VIEWDIR = "zones"

# Provenance travelling with the data, as with `lines.GAP_ID_PREFIX`. A block whose
# id starts with this was drawn in this tool against a configured column; one whose
# id does not came from somewhere else and its width means something different.
#
# **Machine output carries no such prefix**, and the near-collision is worth naming
# because the store is `mz/zones/` while this prefix is `mz_`: the two mean different
# things. This marks a band a human drew against a configured column, wherever it
# ends up; a predicted block keeps the id kraken gave it. That difference is the
# internal witness — the thing whose absence, when a file's role lived only in the
# directory holding it, cost this project 18 pages of transcription.
ID_PREFIX = "mz_"

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = (f"{ALTO_NS} "
                   "http://www.loc.gov/standards/alto/v4/alto-4-2.xsd")

TRAIN_LST = "_train.lst"
EVAL_LST = "_eval.lst"
EXEMPT_LST = "_exempt.lst"

# Three splits, not two. `exempt` is the plates, maps, foldouts and blanks — pages
# a human has looked at and ruled *not a text page*, which is a different statement
# from "keyed and holds nothing" and a very different one from "not reached yet".
# They are excluded from training and from eval alike: a plate has no text column,
# so it is neither an example of the layout nor a fair test of it, and letting one
# into eval would report a model as wrong about a page that has no right answer.
SPLITS = ("train", "eval", "exempt")

# Deliberately not `_exempt.json`. That name sat one character from `_exempt.lst`
# while meaning something else entirely — which order rules a human has accepted on
# a page, not whether the page is a text page at all. Two files whose names differ
# by an extension and whose contents answer different questions is exactly the kind
# of near-collision this repo has already paid for once.
RULE_EXEMPT_JSON = "_rule_exempt.json"

# Per-region exemptions from the ink check alone, each carrying a human reason.
# Separate from the rule exemptions because the thing being excused is different in
# kind: not "this page arranges itself unusually" but "this particular mark is not
# type". Scoped to a band rather than to the page, because exempting a whole page's
# ink check would hide the next genuinely dropped zone on it — and the whole value
# of the check is that a dropped zone is invisible to everything else.
INK_EXEMPT_JSON = "_ink_exempt.json"
INK_CACHE_JSON = "_ink_cache.json"      # derived; ignored, like the journal
JOURNAL = "_journal.jsonl"

# What a page saved with no explicit mark becomes. Held out has to be a deliberate
# act: a default of "eval" would quietly shrink the training set, and a split that
# drifts with keying order is not a held-out set at all.
DEFAULT_SPLIT = "train"


def zone_dir(root: Path = Path("."), store: str = ZONEDIR) -> Path:
    """The directory a zone file lives in — `gt/zones/` unless told otherwise.

    The default is the whole design of this parameter. Every sidecar reader below
    calls `zone_dir(root)` bare and therefore keeps resolving to the human store
    without a line of change: a split, a rule exemption and an ink ruling are
    statements about a *page*, not about a store's files, and there is no such thing
    as the machine store's opinion of which pages are held out. Anything that does
    pass a store is reading page geometry, which is the one thing the two stores
    both have.
    """
    return root / store


def alto_for(ref: str, root: Path = Path("."), store: str = ZONEDIR) -> Path:
    return zone_dir(root, store) / f"chukchi-{norm_ref(ref)}.xml"


def scan_for(ref: str, root: Path = Path(".")) -> Path:
    return root / SCANS / f"chukchi-{norm_ref(ref)}.png"


def raster_size(ref: str, root: Path = Path(".")) -> tuple[int, int]:
    """The page's pixel dimensions, read from the raster itself.

    `Image.open` does not decode; only the header is touched, which matters when a
    session steps through pages one keystroke at a time.
    """
    from PIL import Image
    p = scan_for(ref, root)
    if not p.exists():
        raise FileNotFoundError(f"no raster for {norm_ref(ref)} at {p}")
    with Image.open(p) as im:
        return im.size


def load_itinerary(path: str | Path, root: Path = Path(".")) -> list[str]:
    """A work-list of refs, from an `.lst` file or a directory of page files.

    The editor's prev/next walk `all_scans` by default, which is right for keying a
    part straight through and wrong for everything else. A training set wants a
    *chosen* sequence — `gt/seg/`'s 122 pages were selected for heterogeneity, and
    stepping to them through 700 scans nobody means to key is not navigation.

    Accepts either a list file in `gt/seg/`'s format (`chukchi-1-019.xml` per line,
    bare refs and paths also read) or a directory, which is taken to mean every page
    file in it. The second is there because "everything in `gt/seg/`" is the obvious
    itinerary and spans two list files, and making that a shell incantation would be
    the kind of friction this tool exists to remove.

    **An unparseable line is an error, never a skip.** `lines.parse_selection` takes
    the same position for the same reason: a silently dropped entry means a page
    reported as covered was never visited, and the report cannot tell you so.
    """
    p = Path(path)
    if not p.exists():
        p = root / path
    if not p.exists():
        raise ValueError(f"no itinerary at {path}")

    if p.is_dir():
        names = sorted(q.name for q in p.glob("chukchi-*.xml"))
    else:
        names = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]

    out: list[str] = []
    for i, name in enumerate(names, start=1):
        stem = Path(name).stem.replace("chukchi-", "")
        try:
            ref = norm_ref(stem)
        except ValueError as e:
            raise ValueError(f"{p}:{i}: {name!r} is not a page ref — {e}") from e
        if ref not in out:
            out.append(ref)
    out.sort(key=parse_ref)

    missing = [r for r in out if not scan_for(r, root).exists()]
    if missing:
        raise ValueError(
            f"{p}: no raster for {', '.join(missing[:6])}"
            + (f" and {len(missing) - 6} more" if len(missing) > 6 else ""))
    return out


def zone_refs(root: Path = Path("."), store: str = ZONEDIR) -> list[str]:
    """Every ref with a zone file in this store, in (part, scan index) order.

    Deduped by **real path**, not by name, in the `seen`-set form
    `normalize.scoped_files` uses. Neither caller here points this at `zones/` — the
    `--store` flag deliberately offers only the two real stores, and `link_view`
    enumerates them directly — so this is not fixing a live miscount. It is here
    because the `store` parameter makes a symlink farm reachable for the first time
    and the README's dedupe-by-real-path rule is unconditional; the failure it
    prevents is a silent undercount, which is invisible in any report that would
    otherwise look complete.
    """
    out = []
    seen: set[Path] = set()
    for p in zone_dir(root, store).glob("chukchi-*.xml"):
        try:
            # `exists()` follows the link, so a dangling entry is skipped: a link
            # with no target is not a page, and counting one would put a ref in the
            # report whose file cannot be read. `resolve()` is non-strict and would
            # happily hand back the missing path, so this test is doing the work the
            # OSError guard looks like it is doing — that one is for symlink loops.
            if not p.exists():
                continue
            real = p.resolve()
        except OSError:
            continue
        if real in seen:
            continue
        seen.add(real)
        try:
            out.append(norm_ref(p.stem.replace("chukchi-", "")))
        except ValueError:
            continue
    return sorted(set(out), key=parse_ref)


def read_zones(ref: str, root: Path = Path("."),
               with_points: bool = False, store: str = ZONEDIR) -> list[dict]:
    """This page's zones in reading order — `{label, x0, y0, x1, y1, id}`.

    Sorted by top edge, because these are a vertical partition and document order
    is not guaranteed to be one: a zone inserted between two others is appended by
    the writer, exactly as `lines.adopt_gaps` appends a recovered line rather than
    renumbering around it.

    Empty for a page never keyed. That is not the same as a page keyed and found to
    hold nothing — the latter has a file with no blocks in it, and `has_zones`
    below is what tells them apart.
    """
    out = []
    for b in read_blocks(alto_for(ref, root, store), with_points=with_points):
        rec = {"id": b["id"], "label": b["label"],
               "x0": b["hpos"], "y0": b["vpos"],
               "x1": b["hpos"] + b["width"], "y1": b["vpos"] + b["height"]}
        if with_points:
            rec["points"] = b["points"]
        out.append(rec)
    return sorted(out, key=lambda z: (z["y0"], z["x0"]))


def has_zones(ref: str, root: Path = Path("."), store: str = ZONEDIR) -> bool:
    """Whether this page has been keyed at all — file present, zones or not.

    The distinction is the point. A plate carries no text column, so its correct
    segmentation is zero zones; an empty file is that record. A page nobody has
    opened is also zero zones. Only the file's existence separates "looked at,
    holds nothing" from "not looked at", which is why navigation never writes one.

    **Asked of the default store, this answers "has a human been through it".** The
    editor's resume and its unkeyed counts depend on that reading, so a machine
    prediction must never satisfy them: `--predict` over an itinerary would
    otherwise mark the whole list done and leave the next session with nowhere to
    resume. A caller that means "is there a prediction" passes `store=MZDIR` and is
    asking a different question.

    That separation lives outside the store, though, which is why an empty file is
    only allowed to mean the first when the page is marked `exempt` — see
    `save_zones`. A file is a weak witness: it survives a `cp -r`, and the loss this
    project has already paid for was exactly a role that lived nowhere but a path.
    """
    return alto_for(ref, root, store).exists()


# ------------------------------------------------------------ column anchoring

def _content_rows(ink, width: int, cfg: dict) -> tuple[int, int] | None:
    """First and last row of real ink on the page, or None if there is none.

    A run of `CONTENT_MIN_RUN` consecutive inked rows is required at each end, so a
    speck of scanner dirt in the margin cannot stretch the band across half a page
    of blank paper. The per-row threshold is a share of the page *width* rather
    than of the densest row: taking it from the maximum would let one black
    photograph raise the bar above every line of type on the same page.
    """
    import numpy as np
    row = ink.sum(axis=1)
    inked = row > max(3, int(width * cfg["view"]["content_ink_fraction"]))
    if not inked.any():
        return None
    run = CONTENT_MIN_RUN
    # A row qualifies as an end of the band only if it starts (or finishes) `run`
    # consecutive inked rows.
    ok = np.convolve(inked.astype(int), np.ones(run, dtype=int), "valid") == run
    hits = np.flatnonzero(ok)
    if not len(hits):
        return int(np.flatnonzero(inked)[0]), int(np.flatnonzero(inked)[-1])
    return int(hits[0]), int(hits[-1] + run - 1)


# Fewer consecutive inked rows than this at the top or bottom of a page is dirt,
# not type: the shortest confirmed line of print in this corpus is `3-005`'s
# centred `AFFINITY.` at 23 px of ink, so 4 is far below anything real.
CONTENT_MIN_RUN = 4


def _column_runs(col, n_rows: int, a: dict) -> list[tuple[int, int]]:
    """Contiguous runs of inked columns in the profile, small gaps bridged.

    **Runs, not outermost columns, and that is the whole robustness of the anchor.**
    Density cannot tell a text column from a mark in the margin: `1-033` carries a
    long stroke in its left margin whose densest column holds 774 inked rows —
    *more than any column of type on the same page* — and thresholding on density
    duly took it for the edge of the measure and put the column 52 px too far left.

    Width can tell them apart, decisively. Summed down the page nearly every column
    inside the measure carries something, so the text block is one wide run;
    a margin mark is a narrow run with white paper between it and the block. Over
    all 20 ground-truth pages this yields exactly one run, 1741-1765 px wide. On
    `1-033` it yields two: a 10 px smudge and the real 1746 px block.

    `max_run_gap_px` bridges the white space that does occur inside a measure
    without bridging the margin, which is far wider than any of it.
    """
    import numpy as np
    inked = col > max(3, n_rows * a["ink_row_share"])
    idx = np.flatnonzero(inked)
    if not len(idx):
        return []
    gap = int(a["max_run_gap_px"])
    runs, start, prev = [], int(idx[0]), int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev > gap:
            runs.append((start, prev))
            start = i
        prev = i
    runs.append((start, prev))
    return runs


def measure_frame(ref: str, root: Path = Path("."),
                  cfg: dict | None = None, ink=None) -> dict:
    """Where this page's text column sits, and how far down the leaf it runs.

    Both measurements come off one raster read, because the editor needs both on
    every page load and the read is the expensive part.

    The **vertical** half exists to save the editor a screen. At column-fit zoom a
    full leaf is around three screens tall, and the top and bottom of it are blank
    paper — margin the printer left, plus whatever the scanner caught around the
    page. Framing to the ink instead takes an ordinary page to two screens, which
    is one hover-jump saved on every page of 832.

    Returns `content` as a page-coordinate band with `view.content_pad_px` of air
    either side, clamped to the leaf. It is a **view** concern only: nothing
    validates against it and no zone is constrained by it, since a zone drawn
    outside the ink is already an error the ink check would find.

    **The finding this whole function exists for.** The measure is a property of the
    book and barely moves: 1774-1797 px across the 20 line-precise pages in
    `gt/ocr/`, all three parts. Where it *sits* moves a great deal — the left edge
    runs 399..760 px within part 1, 342..462 within part 2 and 310..546 within part
    3, and up to 170 px between two pages of the same scan-index parity. That is
    scan registration, not typography.

    So the first design here was wrong and measurably so: a per-part constant put
    `1-048`'s column at 618..2410 where the page sets 722..2498, ~104 px out, and
    verso/recto could not rescue it because parity explains only part of the drift.
    Anchoring per page off the raster's own ink removes the whole problem, and takes
    the verso/recto distinction with it — there is nothing left for it to do.

    Method: column-wise ink over the middle band of the page (running head and
    footer excluded, since a centred head is narrower than the measure and would
    drag the left edge right), threshold at a fraction of the densest column, then
    take the outermost inked columns and correct by the calibrated pads. Those pads
    are the systematic gap between an ink edge and a line box's edge: +17 left and
    -11 right, measured against all 20 ground-truth pages, where the corrected
    result lands within ~20 px every time.

    Refuses rather than guesses when there is too little ink — `1-330`'s widest run
    is 80 px against a 1778 px measure — and falls back to the part's `fallback_x0`,
    reporting `measured: false` so the editor can say so rather than quietly draw a
    guide in the wrong place.
    """
    from .lines import ink_mask
    cfg = cfg or zc.load_config(root)
    ref = norm_ref(ref)
    spec = zc.part_spec(cfg, ref)
    a = cfg["columns"]["anchor"]
    measure = int(spec["measure"])
    pad = int(cfg["view"]["content_pad_px"])

    # `ink` lets a caller that has already decoded the page hand it over. The decode
    # is the cost of this whole check — see `lines.ink_mask`.
    ink = ink_mask(ink if ink is not None else scan_for(ref, root))
    h, w = ink.shape

    rows = _content_rows(ink, w, cfg)
    content = ({"y0": max(0, rows[0] - pad), "y1": min(h, rows[1] + pad)}
               if rows else {"y0": 0, "y1": h})

    over = zc.override_windows(cfg, ref)
    if over is not None:
        return {"ref": ref, "columns": over, "measured": False,
                "source": "override", "content": content}

    band = ink[int(h * a["band_top"]):int(h * a["band_bottom"]), :]
    col = band.sum(axis=0)
    runs = _column_runs(col, band.shape[0], a)
    # Specks out by absolute width, then take the SPAN of what survives — not the
    # widest single run. A sparse page fragments: `1-022` yields nine runs whose
    # widest is 863 px against a 1778 px measure, and demanding one run as wide as
    # the measure sent it to the fallback with the column 245 px out. Its span,
    # 766..2502, is the measure.
    keep = [r for r in runs if r[1] - r[0] >= a["min_run_px"]]
    wide = keep if keep and (keep[-1][1] - keep[0][0]) >= measure * a["min_run_share"] \
        else []

    if wide:
        x0 = int(wide[0][0]) - int(a["ink_pad_left"])
        # The width is the invariant, so it is taken from the config and the
        # measurement is used only to place it. Letting a page's own ink set the
        # width too would make every short last line and every wide running head a
        # vote on the measure.
        x0 = max(0, min(x0, w - measure))
        return {"ref": ref, "columns": [{"x0": x0, "x1": x0 + measure}],
                "measured": True, "source": "ink", "content": content,
                "detected": {"x0": int(wide[0][0]), "x1": int(wide[-1][1])},
                "runs_rejected": len(runs) - len(wide)}

    x0 = int(spec["fallback_x0"])
    return {"ref": ref, "columns": [{"x0": x0, "x1": x0 + measure}],
            "measured": False, "source": "fallback", "content": content}


def measure_columns(ref: str, root: Path = Path("."),
                    cfg: dict | None = None, ink=None) -> dict:
    """Back-compatible name for the horizontal half of `measure_frame`."""
    return measure_frame(ref, root, cfg, ink)


def page_windows(ref: str, root: Path = Path("."),
                 cfg: dict | None = None, ink=None) -> list[dict]:
    """Just the windows, for callers that do not care how they were arrived at."""
    return measure_frame(ref, root, cfg, ink)["columns"]


# ---------------------------------------------------------------- split marking

def _lst_path(root: Path, split: str) -> Path:
    return zone_dir(root) / {"train": TRAIN_LST, "eval": EVAL_LST,
                             "exempt": EXEMPT_LST}[split]


def _read_lst(p: Path) -> list[str]:
    if not p.exists():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def load_splits(root: Path = Path(".")) -> dict[str, str]:
    """`{ref: "train"|"eval"|"exempt"}` over the three lists.

    A ref in more than one file resolves to the **most exclusionary** of them —
    `exempt` over `eval` over `train`. Every one of these lists exists to keep
    pages out of something, so the safe reading of a contradiction is the one that
    honours the exclusion rather than the one that trains on a plate.
    `validate_corpus` reports the duplicate separately rather than leaving the
    resolution silent.
    """
    rank = {"train": 0, "eval": 1, "exempt": 2}
    out: dict[str, str] = {}
    for split in SPLITS:
        for name in _read_lst(_lst_path(root, split)):
            try:
                ref = norm_ref(Path(name).stem.replace("chukchi-", ""))
            except ValueError:
                continue
            if ref not in out or rank[split] > rank[out[ref]]:
                out[ref] = split
    return out


def set_split(ref: str, split: str, root: Path = Path(".")) -> dict:
    """Put this page in exactly one of the two lists.

    Removes from both before adding, so a page toggled back and forth cannot end up
    in each — the state that makes an eval set meaningless while both files still
    look plausible.
    """
    if split not in SPLITS:
        raise ValueError(f"split must be one of {', '.join(SPLITS)}, not {split!r}")
    ref = norm_ref(ref)
    name = f"chukchi-{ref}.xml"
    zone_dir(root).mkdir(parents=True, exist_ok=True)
    for which in SPLITS:
        p = _lst_path(root, which)
        entries = [e for e in _read_lst(p) if e != name]
        if which == split:
            entries.append(name)
        entries = sorted(set(entries),
                         key=lambda e: parse_ref(Path(e).stem.replace("chukchi-", "")))
        p.write_text("".join(e + "\n" for e in entries), encoding="utf-8")
    return {"ref": ref, "split": split}


NUDGE_PX = 20


def page_departure(ref: str, root: Path) -> tuple[str, int]:
    """How far this page's gt departs from the prediction it may have come from.

    Returns a kind and the largest edge move in pixels, `10**9` where the shapes do
    not correspond at all. The kinds, weakest claim first:

        identical           the prediction ratified with nothing changed
        geometry only       same zones, same labels, edges moved
        a label differs     a human retyped something
        zone count differs  a human added, removed or split a zone
        no prediction       nothing to have copied

    **The distinction this exists to draw is structural against cosmetic**, and it
    was not drawn at first: the original test asked only whether the two files
    differed, which a 5 px nudge satisfies exactly as a redrawn page does. Over the
    eval set that mislabelled 98 tidy-ups as independent judgements and reported the
    set 0% contaminated when about half of it is the model's own segmentation with
    the edges pulled straight. A threshold that any real edit clears is not a
    threshold; `NUDGE_PX` is where a boundary correction starts.

    A store fact, deliberately. Git knows which pages predate the adoption pass and
    would answer more sharply, but that answer expires the moment a file is touched,
    and there is no such history at all for the next volume.
    """
    if not has_zones(ref, root, MZDIR):
        return ("no prediction", 10**9)
    # Keyword, not positional: `read_zones`'s third parameter is `with_points`, and
    # passing the store there reads *gt both times* and reports every page identical
    # — a comparison whose two witnesses are one witness, in the function written to
    # find exactly that. It failed loudly only because `--diff` had already counted
    # 241 differing pages and this said 1.
    def key(store):
        return [(z["label"], z["y0"], z["y1"])
                for z in read_zones(ref, root, store=store)]
    g, m = key(ZONEDIR), key(MZDIR)
    if len(g) != len(m):
        return ("zone count differs", 10**9)
    if [z[0] for z in g] != [z[0] for z in m]:
        return ("a label differs", 10**9)
    shift = max((max(abs(a[1] - b[1]), abs(a[2] - b[2]))
                 for a, b in zip(g, m)), default=0)
    return ("identical" if shift == 0 else "geometry only", shift)


def _independent(ref: str, root: Path, nudge_px: int = NUDGE_PX) -> bool:
    """Whether a human's ruling on this page went beyond straightening the edges.

    The criterion `--remark-eval` selects on. A page whose every boundary moved less
    than `nudge_px` is **not** counted: as evidence about a model it is that model's
    own output, and a held-out set made of those measures how well the model agrees
    with itself.
    """
    kind, shift = page_departure(ref, root)
    return kind != "identical" and shift > nudge_px


def _spread(items: list, k: int) -> list:
    """`k` items spread evenly through the sequence, not the first `k`.

    Held-out pages taken off the front of a list are a contiguous run of the book,
    and a contiguous run is one chapter, one layout, one typesetter's habits. Even
    spacing is the cheapest way to make the sample look like the volume.
    """
    if k <= 0 or not items:
        return []
    if k >= len(items):
        return list(items)
    return [items[i * len(items) // k] for i in range(k)]


def set_splits(mapping: dict[str, str], root: Path = Path(".")) -> dict:
    """Assign many pages at once, rewriting each list exactly once.

    `set_split` rewrites all three files per call, so a corpus-wide reassignment
    through it is quadratic and — worse — leaves the lists in a valid-looking
    intermediate state after every page. Pages not named keep whatever they had.
    """
    for split in mapping.values():
        if split not in SPLITS:
            raise ValueError(f"split must be one of {', '.join(SPLITS)}, not {split!r}")
    current = load_splits(root)
    current.update({norm_ref(r): s for r, s in mapping.items()})
    zone_dir(root).mkdir(parents=True, exist_ok=True)
    counts = {}
    for split in SPLITS:
        refs = sorted((r for r, s in current.items() if s == split), key=parse_ref)
        counts[split] = len(refs)
        _lst_path(root, split).write_text(
            "".join(f"chukchi-{r}.xml\n" for r in refs), encoding="utf-8")
    return counts


def remark_eval(root: Path = Path("."), fraction: float = 0.20,
                commit: bool = False) -> dict:
    """Move a fraction of `train` into `eval`, per part, independent pages first.

    **Additive: nothing already in `eval` or `exempt` is touched.** A page a human
    put in the held-out set is a judgement, and re-deriving the whole split would
    silently overwrite every one of them — the same reason `--assemble` stopped
    being allowed to rewrite the frozen lists.

    Three properties, in the order they matter:

    - **Stratified by part**, proportionally to each part's own `train` count. An
      eval set drawn globally lands where the pages are, and by page count this
      corpus is three volumes that were keyed in very different ways; a model
      measured on one of them says nothing about reuse on the others.
    - **Independent pages first** (`_independent`), so a held-out page is as far as
      the store can tell not the model's own output handed back to it. Where a part
      has too few, the rest are filled from the remainder rather than the quota
      being quietly shortened — and the report says how many of each went in, since
      that ratio is what the resulting eval figure has to be read against.
    - **Spread, not taken off the front** (`_spread`), within each of those two
      groups.

    Reports without writing unless `commit`.
    """
    splits = load_splits(root)
    train = sorted((r for r, s in splits.items() if s == "train"), key=parse_ref)
    target = round(fraction * len(train))

    by_part: dict[str, list[str]] = {}
    for ref in train:
        by_part.setdefault(ref.split("-")[0], []).append(ref)

    # Largest-remainder, so the per-part quotas sum to the target exactly rather
    # than drifting a page or two under it through independent rounding.
    exact = {p: target * len(rs) / len(train) for p, rs in by_part.items()}
    quota = {p: int(v) for p, v in exact.items()}
    for p in sorted(exact, key=lambda p: -(exact[p] - quota[p]))[:target - sum(quota.values())]:
        quota[p] += 1

    picked, rows = [], []
    for part in sorted(by_part):
        indep = [r for r in by_part[part] if _independent(r, root)]
        rest = [r for r in by_part[part] if r not in set(indep)]
        take = _spread(indep, quota[part])
        fill = _spread(rest, quota[part] - len(take))
        picked += take + fill
        rows.append({"part": part, "train": len(by_part[part]),
                     "quota": quota[part], "independent": len(take),
                     "filled": len(fill), "pool_independent": len(indep)})

    if commit:
        for ref in picked:
            set_split(ref, "eval", root)

    after = load_splits(root)
    return {"committed": commit, "fraction": fraction,
            "moved": len(picked),
            "eval_before": sum(1 for s in splits.values() if s == "eval"),
            "eval_after": sum(1 for s in after.values() if s == "eval")
                          if commit else
                          sum(1 for s in splits.values() if s == "eval") + len(picked),
            "parts": rows,
            "refs": " ".join(sorted(picked, key=parse_ref))}


# ------------------------------------------------------------------ exemptions

def load_exempt(root: Path = Path(".")) -> dict[str, list[str]]:
    p = zone_dir(root) / RULE_EXEMPT_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {k: list(v) for k, v in data.items() if not k.startswith("_")}


def set_exempt(ref: str, rules: list[str], root: Path = Path(".")) -> dict:
    """Record which order rules a human has ruled on for this page.

    Tracked, and a sidecar rather than an attribute in the ALTO: an eScriptorium
    round trip drops anything the schema does not know, so an exemption living
    there would evaporate on the first re-import with nothing to show for it.
    """
    ref = norm_ref(ref)
    data = load_exempt(root)
    if rules:
        data[ref] = sorted(set(rules))
    else:
        data.pop(ref, None)
    p = zone_dir(root) / RULE_EXEMPT_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"_about": ("Order rules a human has looked at and accepted, per page. A "
                      "listed rule still reports — it is flagged `exempted`, never "
                      "hidden. Keyed PP-NNN.")}
    doc.update({k: data[k] for k in sorted(data, key=parse_ref)})
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    return {"ref": ref, "exempt": data.get(ref, [])}


def load_ink_exempt(root: Path = Path(".")) -> dict[str, list[dict]]:
    p = zone_dir(root) / INK_EXEMPT_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {k: list(v) for k, v in data.items() if not k.startswith("_")}


def ink_stamp(ref: str, root: Path = Path(".")) -> list[int]:
    """What a cached ink verdict is only valid for: this page's zones, and the
    exemption ledger — the two files that can change the answer. The ledger is
    written without touching the ALTO, so its mtime has to be in here too.

    `mtime_ns`, not `mtime`: an integer compares exactly through JSON, and two
    saves a few milliseconds apart have to be distinguishable or the second one
    inherits the first one's verdict.
    """
    out = []
    for p in (alto_for(ref, root), zone_dir(root) / INK_EXEMPT_JSON):
        try:
            out.append(p.stat().st_mtime_ns)
        except OSError:
            out.append(0)
    return out


def load_ink_cache(root: Path = Path(".")) -> dict[str, dict]:
    p = zone_dir(root) / INK_CACHE_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def cached_ink(ref: str, root: Path = Path(".")) -> dict | None:
    """This page's stored verdict, or None if it was never asked or has gone stale.

    None rather than the stale record, and that is the whole discipline of the
    thing: a verdict about a page as it was two saves ago, rendered in the same
    column as a live one, is exactly the fluent nonsense this project is organised
    against. Unknown is a state the list can draw; wrong is not.
    """
    ref = norm_ref(ref)
    hit = load_ink_cache(root).get(ref)
    if hit and hit.get("stamp") == ink_stamp(ref, root):
        return hit
    return None


def record_ink(ref: str, report: dict, root: Path = Path(".")) -> dict:
    """Reduce one `validate_page(ink=True)` result to a verdict, and store it.

    The ink pass is ~0.20 s of raster work against ~1 ms for every other check, so
    a list of 122 pages cannot run it on render. But the editor **already runs it**
    on every page it opens and every page it saves, and the corpus sweep runs it
    under `--ink`; the answer is being computed and thrown away. So it is written
    here instead, and the list is a reader of what keying already produced rather
    than a job that recomputes it.

    Four states, and the one that must survive the reduction is `ruled` against
    `clean`: a page whose bands were all excused has to stay distinguishable from
    one where nothing was ever found, since that difference is the record that
    `_ink_exempt.json` exists to keep.
    """
    ref = norm_ref(ref)
    if not report.get("ink_checked"):
        # Not keyed, or ruled not a text page. Uncovered ink is a statement about
        # nothing here, and caching "clean" would be a claim.
        rec = {"state": "skip", "bands": 0, "ruled": 0, "stale": 0, "note": ""}
    else:
        live = [b for b in report["uncovered"] if not b.get("exempted")]
        ruled = [b for b in report["uncovered"] if b.get("exempted")]
        stale = [w for w in report["warnings"]
                 if w["rule"] == "stale-ink-exemption"]
        rec = {"state": "ink" if live else ("ruled" if ruled else "clean"),
               "bands": len(live), "ruled": len(ruled), "stale": len(stale),
               "note": "; ".join(
                   [f"y={b['vpos']}..{b['vpos'] + b['height']}" for b in live]
                   + [f"y={b['vpos']}..{b['vpos'] + b['height']} ruled: {b['note']}"
                      for b in ruled] + [w["detail"] for w in stale])}
    rec["stamp"] = ink_stamp(ref, root)

    data = load_ink_cache(root)
    data[ref] = rec
    p = zone_dir(root) / INK_CACHE_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"_about": ("Derived and disposable: the uncovered-ink verdict for each "
                      "page, cached because it is the one check that reads the "
                      "raster. `stamp` is the mtime of the page's ALTO and of "
                      "_ink_exempt.json; an entry whose stamp no longer matches is "
                      "unknown, not stale-but-usable. Delete this file freely — "
                      "keying refills it.")}
    doc.update({k: data[k] for k in sorted(data, key=parse_ref)})
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    tmp.replace(p)
    return dict(rec, ref=ref)


def set_ink_exempt(ref: str, regions: list[dict],
                   root: Path = Path(".")) -> dict:
    """Record bands of ink on this page that a human has ruled are not type.

    **A reason is required and is the point of the file.** The check this excuses
    is the only one that can see a dropped zone, so every suppression of it is a
    claim that something on the paper is not printing — a scanner smudge, a gutter
    blob, an offset from the facing page. Those are all real and all common in this
    scan set, but "the tool complained and I made it stop" is not a record of
    anything, and a year from now the note is the only thing that distinguishes a
    ruled artifact from a hidden mistake.

    Scoped to a band, never to the page: the next dropped zone on the same leaf
    must still report.
    """
    ref = norm_ref(ref)
    clean = []
    for r in regions or []:
        note = (r.get("note") or "").strip()
        if not note:
            raise ValueError(
                f"ink exemption for {ref} at y={r.get('y0')} has no reason — the "
                "reason is the record; without it the entry is indistinguishable "
                "from a hidden mistake")
        y0, y1 = sorted((int(r["y0"]), int(r["y1"])))
        clean.append({"y0": y0, "y1": y1, "note": note})
    clean.sort(key=lambda r: r["y0"])

    data = load_ink_exempt(root)
    if clean:
        data[ref] = clean
    else:
        data.pop(ref, None)
    p = zone_dir(root) / INK_EXEMPT_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"_about": ("Bands of ink ruled *not type* — smudges, gutter blobs, "
                      "offset from the facing page. Each carries the reason it was "
                      "ruled so, and each is scoped to its own band: exempting a "
                      "whole page's ink check would hide the next dropped zone on "
                      "it. A matched band still reports, flagged `exempted` and "
                      "carrying its note. Keyed PP-NNN.")}
    doc.update({k: data[k] for k in sorted(data, key=parse_ref)})
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    return {"ref": ref, "ink_exempt": data.get(ref, [])}


def _ink_excuse(band: dict, regions: list[dict]) -> dict | None:
    """The recorded region covering this band, if any.

    Matched on the band's **midpoint**, not on its edges: the band is re-measured
    from the raster on every run and its exact extent moves by a pixel or two with
    any change to a neighbouring zone, so an edge test would silently stop matching.
    The midpoint is stable, and regions are stored tight enough that it cannot
    wander into a neighbouring finding.
    """
    mid = band["vpos"] + band["height"] / 2
    for r in regions:
        if r["y0"] <= mid <= r["y1"]:
            return r
    return None


# ---------------------------------------------------------------- ALTO writing

def build_alto(ref: str, zones: list[dict], size: tuple[int, int],
               id_prefix: str = ID_PREFIX) -> etree._ElementTree:
    """One page's zones as an eScriptorium-shaped ALTO 4.2 tree.

    Written in the export dialect rather than a minimal valid one so the file can
    go straight into `ketos segtrain` and, if the GUI is ever wanted again, back
    into eScriptorium without a converter in between — the import/export loop being
    the friction this tool exists to remove.

    **No `TextLine` anywhere.** These are regions; a line-level witness would be a
    second claim about the page that nothing here verified, which is why `gt/fig/`
    carries none either.

    `PrintSpace` is the whole page, matching every other store in the repo — it
    carries no information and `lines --margins` already treats it as the escape
    hatch it is. Page dimensions are the raster's own, so coordinates are in raster
    space and the ALTO→raster scale is 1.0 *for files written here*; readers still
    go through `figures._scale_for`, since a file may not have been.
    """
    w, h = size
    nsmap = {None: ALTO_NS, "xsi": XSI_NS}
    alto = etree.Element(f"{{{ALTO_NS}}}alto", nsmap=nsmap)
    alto.set(f"{{{XSI_NS}}}schemaLocation", SCHEMA_LOCATION)

    desc = etree.SubElement(alto, f"{{{ALTO_NS}}}Description")
    etree.SubElement(desc, f"{{{ALTO_NS}}}MeasurementUnit").text = "pixel"
    src = etree.SubElement(desc, f"{{{ALTO_NS}}}sourceImageInformation")
    etree.SubElement(src, f"{{{ALTO_NS}}}fileName").text = f"chukchi-{ref}.png"

    ordered = sorted(zones, key=lambda z: (z["y0"], z["x0"]))
    # Only the labels this page actually uses are declared. Exports carry the whole
    # vocabulary and that is how `gt/seg/` ended up with a dangling TAGREFS and 21
    # declared types where 15 were used; a tag list that is exactly the page's
    # contents cannot drift from them.
    tags = etree.SubElement(alto, f"{{{ALTO_NS}}}Tags")
    tag_id: dict[str, str] = {}
    for z in ordered:
        if z["label"] in tag_id:
            continue
        tid = f"BT{len(tag_id) + 1}"
        tag_id[z["label"]] = tid
        etree.SubElement(tags, f"{{{ALTO_NS}}}OtherTag", {
            "ID": tid, "LABEL": z["label"],
            "DESCRIPTION": f"block type {z['label']}"})

    layout = etree.SubElement(alto, f"{{{ALTO_NS}}}Layout")
    page = etree.SubElement(layout, f"{{{ALTO_NS}}}Page", {
        "WIDTH": str(w), "HEIGHT": str(h), "PHYSICAL_IMG_NR": "0",
        "ID": "eSc_dummypage_"})
    ps = etree.SubElement(page, f"{{{ALTO_NS}}}PrintSpace", {
        "HPOS": "0", "VPOS": "0", "WIDTH": str(w), "HEIGHT": str(h)})

    for i, z in enumerate(ordered, start=1):
        x0, y0 = int(round(z["x0"])), int(round(z["y0"]))
        x1, y1 = int(round(z["x1"])), int(round(z["y1"]))
        blk = etree.SubElement(ps, f"{{{ALTO_NS}}}TextBlock", {
            "HPOS": str(x0), "VPOS": str(y0),
            "WIDTH": str(x1 - x0), "HEIGHT": str(y1 - y0),
            "ID": f"{id_prefix}{ref}_{i:03d}", "TAGREFS": tag_id[z["label"]]})
        shape = etree.SubElement(blk, f"{{{ALTO_NS}}}Shape")
        etree.SubElement(shape, f"{{{ALTO_NS}}}Polygon", {
            "POINTS": f"{x0} {y0} {x1} {y0} {x1} {y1} {x0} {y1}"})
    return etree.ElementTree(alto)


def save_zones(ref: str, zones: list[dict], root: Path = Path("."),
               split: str | None = None, exempt: list[str] | None = None,
               stamp: str | None = None) -> dict:
    """Write one page's zones, atomically, and record the save.

    Same durability shape as `review.save_decisions`, for the same reason it has
    one: copy to `.prev`, write `.tmp`, `replace()`, then append to an append-only
    journal. Two saves in a row destroy `.prev`; nothing destroys the journal. This
    repo has lost hand-keyed work to a write it could not roll back once, and the
    cost of not repeating that is three lines.

    `zones` carry resolved coordinates — the caller has already turned a side and a
    column index into an x-pair. Nothing below knows what a side is.

    **An empty page is refused unless it is marked `exempt`**, and this is the same
    distinction the three splits exist to draw. A text page with no zones and a page
    nobody has reached are byte-identical in this store — `zone_refs` finds both,
    the sweep counts both as keyed, the list draws both as done — so an empty save
    does not record a judgement, it erases the difference between having made one
    and not. `exempt` is how a human says "I looked at this and it is not a text
    page"; that is a statement, and it saves. "Nothing here" is not.

    Mechanical, like every other refusal here: it needs no reading of the page, and
    no layout rule can be configured to allow it.
    """
    ref = norm_ref(ref)
    effective = split or load_splits(root).get(ref) or DEFAULT_SPLIT
    if not zones and effective != "exempt":
        raise ValueError(
            f"{ref} has no zones and is marked {effective!r} — an empty text page "
            "is indistinguishable from one nobody has reached, so it would be "
            "counted as keyed while recording nothing. Three ways out, and they say "
            "different things: mark it exempt if it is a plate, map, foldout or "
            "blank; key it if it is a text page; or **delete it** — `harness zones "
            f"delete {ref} --commit`, or `X` in the editor — if it should not be "
            "in the store at all. That third one is reachable from here: a page "
            "keyed and then emptied has no other way to be withdrawn.")
    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    size = raster_size(ref, root)
    tree = build_alto(ref, zones, size)

    p = alto_for(ref, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    tmp = p.with_suffix(".xml.tmp")
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
               standalone=None, pretty_print=True)
    tmp.replace(p)

    if exempt is not None:
        set_exempt(ref, exempt, root)
    marked = load_splits(root).get(ref)
    if split is not None:
        set_split(ref, split, root)
    elif marked is None:
        set_split(ref, DEFAULT_SPLIT, root)

    counts: dict[str, int] = {}
    for z in zones:
        counts[z["label"]] = counts.get(z["label"], 0) + 1
    with (zone_dir(root) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"saved_at": stamp, "ref": ref, "zones": len(zones),
                             "labels": counts,
                             "split": split or marked or DEFAULT_SPLIT},
                            ensure_ascii=False) + "\n")
    return {"ref": ref, "path": str(p), "zones": len(zones),
            "split": split or marked or DEFAULT_SPLIT,
            "labels": " ".join(f"{k}:{v}" for k, v in sorted(counts.items()))}


def delete_zones(ref: str, root: Path = Path("."), commit: bool = False,
                 stamp: str | None = None) -> dict:
    """Un-key a page: remove its file and every mark that referred to it.

    **The one operation the store had no way to express.** `save_zones` refuses zero
    zones unless the page is exempt, so a page keyed in error — the wrong ref, or one
    that should never have been opened — could be corrected but not withdrawn. That
    left "keyed and holds nothing" as the only way to say "this should not be here",
    and that string already means something else entirely.

    Removes the marks too, or the page would keep a split and its exemptions while
    having no zones — a ref in `_train.lst` naming a file that does not exist is the
    kind of dangling claim `harness corpus figures` exists to catch elsewhere.

    Same durability shape as a save, because this is the more dangerous direction:
    `.prev` keeps the file one deep, the journal records the act, and `--commit` is
    required. `gt/` is tracked, so git is the real backstop — but the journal is what
    survives the window before a commit exists, which is exactly when this repo lost
    18 pages once.
    """
    ref = norm_ref(ref)
    p = alto_for(ref, root)
    splits = load_splits(root)
    rules = load_exempt(root).get(ref, [])
    ink_ex = load_ink_exempt(root).get(ref, [])
    zones = read_zones(ref, root) if p.exists() else []

    out = {"ref": ref, "path": str(p), "exists": p.exists(),
           "zones": len(zones), "split": splits.get(ref) or "",
           "rule_exemptions": " ".join(rules),
           "ink_exemptions": len(ink_ex), "committed": commit}
    if not p.exists():
        out["note"] = "nothing to delete"
        return out
    if not commit:
        out["note"] = "preview only — pass --commit to delete"
        return out

    p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    p.unlink()
    # Out of all three lists: `set_split` removes from every one before adding, so
    # there is no "unset" — the removal is done by rewriting them without this ref.
    for which in SPLITS:
        q = _lst_path(root, which)
        entries = [e for e in _read_lst(q) if e != f"chukchi-{ref}.xml"]
        q.write_text("".join(e + "\n" for e in entries), encoding="utf-8")
    if rules:
        set_exempt(ref, [], root)
    if ink_ex:
        set_ink_exempt(ref, [], root)

    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with (zone_dir(root) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"deleted_at": stamp, "ref": ref,
                             "zones": len(zones),
                             "split": splits.get(ref) or ""},
                            ensure_ascii=False) + "\n")
    return out


# ---------------------------------------------------------------- validation

def _is_rectangle(points: str, x0: int, y0: int, x1: int, y1: int) -> bool:
    """Whether a `POINTS` string is the axis-aligned rectangle its bbox claims.

    Everything this tool writes is one by construction, so the check exists for
    what it does *not* write: a file hand-edited, or round-tripped through
    eScriptorium where a zone can be dragged into any shape at all. A polygon that
    is not a rectangle means the width is no longer the column's width, and the
    fixed-measure claim this whole store rests on has quietly stopped holding for
    that page.
    """
    try:
        vals = [float(v) for v in points.split()]
    except ValueError:
        return False
    if len(vals) != 8:
        return False
    corners = {(round(vals[i]), round(vals[i + 1])) for i in range(0, 8, 2)}
    return corners == {(x0, y0), (x1, y0), (x1, y1), (x0, y1)}


def _overlap(a: dict, b: dict) -> int:
    """Overlapping area's shorter side, or 0 if the two do not overlap at all.

    **Both axes, never just the vertical.** Two-column pages put a left-column zone
    and a right-column zone at the same height on purpose, and a y-only test would
    report every row of `3-005`'s gazetteer as a collision. `lines.mark_figure_overlap`
    learned the same lesson from the other direction — a y-only test there misread
    14 body lines of `1-151` as caption.
    """
    dx = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    dy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    return 0 if dx <= 0 or dy <= 0 else min(dx, dy)


def _width_error(z: dict, measure: int, tol: float) -> str | None:
    """Whether this zone is the book's measure wide. The cheap half of the check.

    Split from the position check deliberately. The **width** is the invariant and
    is knowable from the config alone, so the corpus sweep can test it over every
    page for nothing; the **position** varies per page by up to 236 px within a
    part and can only be had by reading the raster, so it waits for `--ink`. A
    hand-sized zone — the thing the fixed-measure design exists to exclude — is
    caught by the cheap half.
    """
    w = z["x1"] - z["x0"]
    off = abs(w - measure)
    if off <= tol:
        return None
    return (f"is {w} px wide against the part's {measure} px measure "
            f"({off} px out, tolerance {tol:.0f})")


def _position_error(z: dict, windows: list[dict], tol: float) -> str | None:
    """Whether this zone sits on the page's own measured column."""
    best, best_off = None, None
    for w in windows:
        off = max(abs(z["x0"] - w["x0"]), abs(z["x1"] - w["x1"]))
        if best_off is None or off < best_off:
            best, best_off = w, off
    if best is None:
        return "no column could be measured or configured for this page"
    if best_off <= tol:
        return None
    return (f"x {z['x0']}..{z['x1']} is {best_off:.0f} px off the column measured "
            f"on this page ({best['x0']}..{best['x1']}); tolerance is {tol:.0f}")


def uncovered_ink(ref: str, zones: list[dict], root: Path = Path("."),
                  cfg: dict | None = None,
                  windows: list[dict] | None = None, ink=None) -> list[dict]:
    """Bands of ink inside the text column that no zone and no figure accounts for.

    The partition check, and the only one that consults the page rather than the
    file. Measured exactly as `lines.line_gaps` measures a dropped line — same
    `ink_bands`, same thresholds — because it is the same question asked of
    different boxes: the segmenter that dropped whole printed lines from `1-053`
    and `1-048` will drop whole zones here, and nothing in the ALTO can disagree
    with a page that simply has less on it than the paper does.

    Figure zones are masked, or every illustrated page reports its own artwork —
    `3-006` gave 12 bands that way and `2-030` two, all graphics.

    **Bounded by the configured column**, so ink in the margins is out of scope by
    construction: a running head that overhangs the measure, a folio set outside
    it, the scanner's dark gutter. That is the same window `line_gaps` derives from
    a page's own lines, and it carries the same limitation — this finds dropped
    *body* material, not everything on the leaf.
    """
    import numpy as np
    from .lines import COVER_PAD, ink_bands, ink_mask
    from .figures import zones as fig_zones

    cfg = cfg or zc.load_config(root)
    ref = norm_ref(ref)
    ink = ink_mask(ink if ink is not None else scan_for(ref, root))
    h = ink.shape[0]
    windows = windows or page_windows(ref, root, cfg, ink)

    covered = np.zeros(h, dtype=bool)
    for box in list(zones) + [{"y0": z["vpos"], "y1": z["vpos"] + z["height"]}
                              for z in fig_zones(ref, root)]:
        covered[max(0, int(box["y0"]) - COVER_PAD):
                min(h, int(box["y1"]) + COVER_PAD)] = True

    x0 = min(int(win["x0"]) for win in windows)
    x1 = max(int(win["x1"]) for win in windows)
    return _merge_bands(ink_bands(ink, x0, x1, covered))


def _merge_bands(bands: list[dict]) -> list[dict]:
    """Collapse runs of ink separated by less than a line's height into one finding.

    `ink_bands` measures *lines*, which is right for `lines.line_gaps` — a dropped
    line is the unit of that repair. Here the unit is a **zone**, and one missing
    zone is a whole paragraph's worth of lines: an under-segmented `1-048` reported
    38 separate bands, one per line of body text, for a single missing region. That
    is a count, not a finding, and 38 lines of correct output is exactly how a real
    signal gets buried.

    The threshold is the median band height rather than a constant, so it scales
    with the type on the page and needs no tuning per part: inter-line gaps in this
    book run ~10 px against ~32 px of ink, while a genuinely separate uncovered
    region is separated by a covered zone, which is unboundedly larger. A lone
    dropped heading between two covered zones stays its own finding, which is the
    case that must not be merged away.
    """
    if not bands:
        return []
    heights = sorted(b["height"] for b in bands)
    gap = heights[len(heights) // 2]
    out = [dict(bands[0], bands=1)]
    for b in bands[1:]:
        last = out[-1]
        end = last["vpos"] + last["height"]
        if b["vpos"] - end <= gap:
            right = max(last["hpos"] + last["width"], b["hpos"] + b["width"])
            last["hpos"] = min(last["hpos"], b["hpos"])
            last["width"] = right - last["hpos"]
            last["height"] = b["vpos"] + b["height"] - last["vpos"]
            last["bands"] += 1
        else:
            out.append(dict(b, bands=1))
    return out


def validate_page(ref: str, root: Path = Path("."), cfg: dict | None = None,
                  ink: bool = True, store: str = ZONEDIR) -> dict:
    """Check one page's zones. Errors are mechanical; warnings are judgement.

    The split is the governing distinction in this repo and it is worth stating in
    one line: an **error** is something that cannot be true of a page keyed in this
    tool — a label nobody declared, a zone thinner than a mis-click, two zones on
    top of each other, a width no configured column offers. A **warning** is a page
    that does not look like most pages, which is a description and never a verdict.
    Only errors set the exit code.

    Every ordering assumption is therefore a warning, per the brief: they are
    configurable in `data/zones_config.json`, exemptible per page, and a page that
    breaks them is the interesting page rather than the rejected one.

    `ink` is the raster read — ~0.20 s, against ~1 ms for everything else — so the
    corpus sweep leaves it off by default and says so in its report. The UI turns it
    on, since a save is already a round trip and a dropped zone is exactly what an
    editor cannot see by looking at their own work.

    `store` chooses whose geometry is checked, and **what the report means changes
    with it while the report itself does not**. Over `gt/zones/` these are defects
    in work a human signed; over `mz/zones/` they are measurements of a model, since
    nothing there is ratified and a raw polygon fails the fixed-measure width check
    by construction. That difference belongs to the caller — `cli` gates on one and
    not the other — because a check that softened its own findings depending on who
    produced them would be unable to tell you the model is wrong.

    The sidecars are read from `gt/` whichever store is checked, and that is right:
    an ink exemption rules that some mark on the *page* is not type, which is true
    no matter whose zones are being measured against it.
    """
    cfg = cfg or zc.load_config(root)
    ref = norm_ref(ref)
    zones = read_zones(ref, root, with_points=True, store=store)
    labels = set(zc.types_by_label(cfg))
    tol = cfg["width_tolerance_px"]
    min_h = cfg["min_zone_h_px"]
    max_ov = cfg["max_overlap_px"]

    errors: list[dict] = []

    def err(rule: str, detail: str):
        errors.append({"rule": rule, "detail": detail})

    # `save_zones` refuses to write this, but a page can already be in the state —
    # it predates the refusal, or arrived by hand — and it is the one defect that
    # makes a page *look finished*. Everything downstream counts it as keyed.
    if has_zones(ref, root, store) and not zones \
            and load_splits(root).get(ref) != "exempt":
        err("empty-page",
            "keyed with no zones and not marked exempt — indistinguishable from a "
            "page nobody has reached, while counting as done. Mark it exempt if it "
            "is a plate, map, foldout or blank; key it if it is a text page; or "
            "delete it (`--delete --commit`) if it does not belong in the store."
            # The remedy is the human store's. A file here with nothing in it means
            # the model found nothing on a page a human has not ruled blank, which
            # is a finding about the model and has no "mark it exempt" answer.
            if store == ZONEDIR else
            "the model returned no region for a page not ruled exempt")

    measure = int(zc.part_spec(cfg, ref)["measure"])
    over = zc.override_windows(cfg, ref)
    # The measured column needs the raster, so it is only consulted when the ink
    # pass is running anyway. An override is free and always applies.
    #
    # **One decode for both.** The anchor and the ink bands are two measurements
    # over the same mask, and reading the PNG twice was most of what this check
    # cost — 0.16 s of inflate against ~0.02 s of measuring.
    page_ink = None
    if ink and zones:
        from .lines import ink_mask
        page_ink = ink_mask(scan_for(ref, root))
    windows = over if over is not None else (
        page_windows(ref, root, cfg, page_ink) if page_ink is not None else None)

    for z in zones:
        where = f"{z['label']} at y={z['y0']}"
        if z["label"] not in labels:
            err("unknown-label",
                f"{z['label']!r} at y={z['y0']} is not a type declared in the config")
        if z["y1"] - z["y0"] < min_h:
            err("min-height",
                f"{where} is {z['y1'] - z['y0']} px tall, minimum is {min_h}")
        if z["x1"] <= z["x0"] or z["y1"] <= z["y0"]:
            err("degenerate", f"{where} has a non-positive extent")
        if over is None:
            msg = _width_error(z, measure, tol)
            if msg:
                err("column-width", f"{where} {msg}")
        if windows is not None:
            msg = _position_error(z, windows, tol)
            if msg:
                err("column-position", f"{where}: {msg}")
        if z.get("points") and not _is_rectangle(z["points"], z["x0"], z["y0"],
                                                 z["x1"], z["y1"]):
            err("not-a-rectangle",
                f"{where} has a polygon that is not its bounding box — the "
                "fixed-measure claim does not hold for this zone")

    for i, a in enumerate(zones):
        for b in zones[i + 1:]:
            ov = _overlap(a, b)
            if ov > max_ov:
                err("overlap",
                    f"{a['label']} at y={a['y0']} and {b['label']} at y={b['y0']} "
                    f"overlap by {ov} px, maximum is {max_ov}")

    if zones:
        try:
            _, page_h = raster_size(ref, root)
            for z in zones:
                if z["y1"] > page_h:
                    err("off-page",
                        f"{z['label']} at y={z['y0']} ends at {z['y1']}, past the "
                        f"page's {page_h} px")
        except FileNotFoundError:
            err("no-raster", f"no scan for {ref}; geometry cannot be checked")

    split = load_splits(root).get(ref)
    # A page marked `exempt` is a plate, a map, a foldout or a blank — a human has
    # ruled it not a text page. The layout warnings all describe how a *text* page
    # is normally arranged, so on this one they describe nothing and would be
    # permanent known-false noise, which is what buries real signal. The mechanical
    # errors above still stand: whatever zones the page does carry must still be
    # the right shape, or the mark is hiding a mistake rather than a plate.
    if split == "exempt":
        return {"ref": ref, "keyed": has_zones(ref, root, store), "zones": len(zones),
                "split": split, "ink_checked": False,
                "errors": errors, "warnings": [], "uncovered": []}

    exempt = load_exempt(root).get(ref, [])
    warnings = zc.order_warnings(cfg, zones, exempt)

    # A typo in a rule id disables that rule silently — `order_warnings` ignores
    # what it does not implement, deliberately, so that one bad id cannot take the
    # rest down. This is where the typo becomes visible again.
    implemented = {"title-first", "rank-monotone", "max-per-page"}
    for r in cfg.get("order_rules") or []:
        if r.get("id") not in implemented:
            warnings.append({"rule": "unknown-rule",
                             "detail": f"config declares rule {r.get('id')!r}, "
                                       "which nothing implements — it is doing nothing",
                             "exempted": False})

    fired = {w["rule"] for w in warnings}
    for rid in exempt:
        if rid not in fired:
            warnings.append({"rule": "stale-exemption",
                             "detail": f"{rid!r} is exempted for this page but no "
                                       "longer fires — the exemption can go",
                             "exempted": False})

    bands = []
    if ink and zones:
        bands = uncovered_ink(ref, zones, root, cfg, windows, page_ink)
        regions = load_ink_exempt(root).get(ref, [])
        for b in bands:
            excuse = _ink_excuse(b, regions)
            b["exempted"] = bool(excuse)
            b["note"] = excuse["note"] if excuse else ""
            rows = (f"{b['bands']} rows of ink" if b.get("bands", 1) > 1
                    else f"{b['height']} px of ink")
            warnings.append({
                "rule": "uncovered-ink",
                "detail": f"{rows} spanning y={b['vpos']}..{b['vpos'] + b['height']} "
                          f"(x {b['hpos']}..{b['hpos'] + b['width']}) that no zone "
                          "and no figure accounts for"
                          + (f" — ruled not type: {excuse['note']}" if excuse else ""),
                # The band still reports when excused, exactly as an exempted order
                # rule does. A suppression that vanished would make this file the
                # one place a wrong call could hide.
                "exempted": bool(excuse) or "uncovered-ink" in exempt})
        # A region that no longer matches anything is worth saying: the page was
        # re-keyed, or the band moved, and the note is now describing nothing.
        for r in regions:
            if not any(_ink_excuse(b, [r]) for b in bands):
                warnings.append({
                    "rule": "stale-ink-exemption",
                    "detail": f"y={r['y0']}..{r['y1']} ({r['note']!r}) matches no "
                              "band any more — the exemption can go",
                    "exempted": False})

    return {"ref": ref, "keyed": has_zones(ref, root, store), "zones": len(zones),
            "split": split, "ink_checked": bool(ink and zones),
            "errors": errors, "warnings": warnings, "uncovered": bands}


def validate_corpus(root: Path = Path("."), cfg: dict | None = None,
                    ink: bool = False, refs: list[str] | None = None,
                    store: str = ZONEDIR) -> tuple[dict, list[dict]]:
    """Every keyed page, one flat record each, plus a summary.

    Two returns rather than one nested object because TOON collapses a uniform
    record list to a header and rows and degrades to the verbose form the moment
    the keys go ragged — so the summary and the table are emitted separately, as
    `cli` already does for `lines`.

    List-valued fields are joined into strings here for the same reason. The counts
    are what a sweep is for; `harness zones check PP-NNN` is where a page's own findings
    are read in full.

    `refs` scopes it to a work-list. A page on the list that has not been keyed is
    **reported as a row with no zones**, not omitted: "still to do" is the answer an
    itinerary is being asked for, and a sweep that silently listed only finished
    pages would report a half-done selection as complete.
    """
    cfg = cfg or zc.load_config(root)
    splits = load_splits(root)
    rows, n_err, n_warn = [], 0, 0
    labels: dict[str, int] = {}
    seen: dict[str, int] = {}
    for s in SPLITS:
        for name in _read_lst(_lst_path(root, s)):
            seen[name] = seen.get(name, 0) + 1
    dup = sorted(n for n, c in seen.items() if c > 1)
    for ref in (refs if refs is not None else zone_refs(root, store)):
        r = validate_page(ref, root, cfg, ink=ink, store=store)
        if ink and store == ZONEDIR:
            # A sweep that read 122 rasters and kept nothing would make the page
            # list ask for the same work again.
            #
            # **Only for the human store.** The cache is keyed by ref alone and
            # stamped with the page ALTO's mtime, and it feeds the editor's page
            # list, which lists ground truth. Letting a machine sweep write here
            # would put two verdicts about one page under one key with nothing to
            # tell them apart — a verdict about work nobody has done, drawn in the
            # same column as one about work someone has. A machine page's ink is
            # measured fresh when asked for, and recorded nowhere.
            record_ink(ref, r, root)
        n_err += len(r["errors"])
        n_warn += len(r["warnings"])
        for z in read_zones(ref, root, store=store):
            labels[z["label"]] = labels.get(z["label"], 0) + 1
        rows.append({
            "ref": ref, "split": r["split"] or "", "zones": r["zones"],
            "errors": len(r["errors"]), "warnings": len(r["warnings"]),
            "detail": "; ".join(e["rule"] for e in r["errors"])
                      or "; ".join(sorted({w["rule"] for w in r["warnings"]}))
                      or "",
        })
    # Counted off the reported rows rather than off the split files, so a scoped
    # sweep reports its own scope. Over the whole store the two agree.
    summary = {"pages": len(rows),
               "keyed": sum(1 for r in rows if r["split"]),
               "todo": sum(1 for r in rows if not r["split"]),
               "train": sum(1 for r in rows if r["split"] == "train"),
               "eval": sum(1 for r in rows if r["split"] == "eval"),
               "exempt": sum(1 for r in rows if r["split"] == "exempt"),
               "zones": sum(r["zones"] for r in rows),
               "errors": n_err, "warnings": n_warn,
               "ink_checked": ink,
               # The class distribution, because it is read before every training
               # run — a class with no instances cannot be in a class map, and one
               # that has stopped growing while the rest doubled is the argument for
               # folding it. It had been counted by hand twice, which is the tell.
               "labels": " ".join(f"{k}:{v}" for k, v in
                                  sorted(labels.items(), key=lambda kv: -kv[1])),
               "in_both_lists": " ".join(dup)}
    return summary, rows


# ------------------------------------------------------- the blotted corpus

BLOTDIR = "scans-fig-blotted"


def blot_dir(root: Path = Path(".")) -> Path:
    return root / BLOTDIR


def blot_one(ref: str, root: Path = Path(".")) -> dict:
    """This page's training raster: figures painted white, or a link if it has none.

    **A page with no figure ALTO is linked, not copied.** 580 of the 832 pages have
    no figure at all, and copying them would duplicate roughly 1.5 GB of identical
    pixels for nothing. The whole directory is gitignored and rebuildable in one
    command, so a link that dangles in a fresh clone is the disposition already
    chosen for `scans/w-figs/` and for `review/*/page.png` — and it dangles loudly,
    which is the right failure for a derived tree.
    """
    from .lines import write_fig_blot
    import os
    ref = norm_ref(ref)
    src = scan_for(ref, root)
    if not src.exists():
        return {"ref": ref, "path": "", "action": "no-raster", "painted": 0}
    out = blot_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    if not (root / "gt" / "fig" / f"chukchi-{ref}.xml").exists():
        link = out / f"chukchi-{ref}.png"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(os.path.relpath(src.resolve(), out.resolve()))
        return {"ref": ref, "path": str(link), "action": "linked", "painted": 0}
    rep = write_fig_blot(ref, out, root)
    return {"ref": ref, "path": rep["path"], "action": "painted",
            "painted": rep["painted"]}


def blot_all(root: Path = Path(".")) -> dict:
    """Rebuild the whole blotted corpus.

    **Unconditional, never incremental.** A freshness test against mtimes would be
    wrong in the one case that matters: a figure ALTO corrected after the blot was
    written leaves a raster that still shows the figure, and the sweep would report
    success over it. Repainting 252 pages costs seconds and cannot go stale.
    """
    from .context import all_scans
    painted = linked = missing = 0
    for ref in all_scans(root):
        r = blot_one(ref, root)
        if r["action"] == "painted":
            painted += 1
        elif r["action"] == "linked":
            linked += 1
        else:
            missing += 1
    return {"dir": str(blot_dir(root)), "painted": painted, "linked": linked,
            "no_raster": missing, "total": painted + linked}


# ------------------------------------------------------------- the predictor

# Models this project trains live together, tracked, one directory apart from the
# downloaded weights in `models/` — which are large, third-party and gitignored.
# A model here is an artifact with a manifest beside it; see `install_model`.
MODELDIR = "models/bogoras-seg"
DEFAULT_MODEL = f"{MODELDIR}/zones-seg.safetensors"


def mz_dir(root: Path = Path(".")) -> Path:
    return root / MZDIR


def manifest_path(model_path: str | Path, root: Path = Path(".")) -> Path:
    """`<model>.json` — the handful of facts about a model that are *not* lists.

    Deliberately small. The split lives in `<model>.train.lst`/`.eval.lst`, verbatim
    copies in the format `--assemble` already writes, because re-encoding a list of
    filenames as JSON buys nothing and creates a second copy to drift. The class set
    is not here either: it is in the weights, and `load_segmenter` reads it.

    What is left is genuinely not a list — a corpus digest, the score at install
    time, what it was fine-tuned from, the merges in force. Everything is **relative
    to the repo root**: this file is tracked, and a record of one machine's
    filesystem is no record at all.
    """
    p = Path(model_path)
    if not p.is_absolute():
        p = root / p
    return p.with_suffix(".json")


def load_manifest(model_path: str | Path, root: Path = Path(".")) -> dict | None:
    p = manifest_path(model_path, root)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def corpus_digest(root: Path = Path("."), store: str = ZONEDIR) -> str:
    """A digest of the keyed store, so a manifest can notice the ground truth moved.

    Ref, zone count and geometry — not file bytes, which change on every save
    whether or not the zones did. Its job is to let `score` say "this model trained
    on a corpus that has since changed" rather than silently compare against a moved
    reference, which is the same claim `_ink_cache`'s mtime stamp makes about a
    page's ink and for the same reason.
    """
    import hashlib
    h = hashlib.sha256()
    for ref in zone_refs(root, store):
        h.update(ref.encode())
        for z in read_zones(ref, root, store=store):
            h.update(f"{z['label']}:{z['y0']}:{z['y1']}".encode())
    return h.hexdigest()[:16]


def _model_sha256(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_segmenter(model_path: str | Path = DEFAULT_MODEL,
                   root: Path = Path(".")) -> tuple[object, str]:
    """The trained region model, plus the sha256 that will travel in every file.

    Loaded through `kraken.models.loaders.load_models`, and that choice is not
    cosmetic. `TorchVGSLModel.load_model` — which every 4.x-era example and kraken's
    own `blla` default still call — is **CoreML-only**: handed a safetensors file it
    fails inside protobuf with `Wire format was corrupt`, which reads as a damaged
    model rather than as the wrong reader. Its deprecation warning names
    `kraken.registry.load_model` as the replacement, and **that does not exist in
    7.0.3** — `kraken.registry` exports four constants and no loader. So neither the
    documented path nor the advertised one works, which is the concrete case for
    this repo's standing rule: verify against the installed source.

    **`hyper_params` is set here because `ketos segtrain` does not write it and
    `blla.segment` reads it unguarded** (`kraken/blla.py:94` indexes
    `user_metadata['hyper_params']` before testing for `padding` inside it). Every
    model this project trains therefore raises `KeyError: 'hyper_params'` on its
    first inference — checked against `models/plates-seg-best.safetensors` too, which
    is missing the key identically. Setting it empty restores the documented default
    the guarded branch would have given, `padding = (0, 0)`; it invents no
    hyperparameter and changes nothing the model learned.
    """
    from kraken.models.loaders import load_models
    p = Path(model_path)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        raise FileNotFoundError(
            f"no segmentation model at {p} — train one with `harness zones "
            f"assemble` and the ketos command it reports, then put the result at "
            f"{DEFAULT_MODEL}")
    models = load_models(p)
    if not models:
        raise ValueError(f"{p} holds no model")
    net = models[0]
    net.user_metadata.setdefault("hyper_params", {})
    return net, _model_sha256(p)


# Provenance for a band decoded by the segmental DP rather than vectorised from the
# heatmap blob-wise. A different prefix from `mz_` for the reason that one exists:
# the geometry means something different, and a file merged out of context has to
# say so itself.
DP_ID_PREFIX = "dp_"


def _segmental_decode(rows, min_len: int, gap_min: int = 1):
    """The best chain of labelled bands down a page, by exact dynamic programming.

    `rows` is `(n_rows, n_classes)` of independent per-row class probabilities. What
    comes back is `[(start, end, class_index_or_None)]` covering `0..n_rows`, `None`
    meaning whitespace.

    **Why a DP rather than thresholding each class and vectorising the blobs**, which
    is what `blla.vec_regions` does: a page of this corpus is a *vertical partition*,
    and blob-wise decoding does not know that. Measured over the keyed corpus, a page
    is a chain of at most 13 bands, 545 boundaries abut exactly, 482 leave a small
    gap, and **2 overlap in the whole corpus**. So the structure is a linear chain,
    exact search over it is cheap, and the constraints can be *built in* rather than
    hoped for:

    - one label per row, so overlapping bands are unrepresentable;
    - a minimum duration, so a sliver cannot be emitted — where the current pipeline
      produces them at a median height of 24 px against a 30 px floor and has them
      filtered out afterwards, losing nothing but having wasted the region;
    - adjacent runs of one label are one band, which is most of the fragmentation.

    **What is deliberately *not* built in: the order rules.** `rank-monotone`,
    `title-first` and `max-per-page` are warnings in `validate_page` and must stay
    violable, because the book breaks its own conventions and a page that breaks them
    is the interesting page rather than the rejected one. A decoder that could not
    emit such a page would make the warning unfalsifiable and would silently
    normalise exactly what the check exists to surface. The line drawn here is the
    project's own: **the decoder may enforce what `validate_page` calls an error and
    must not enforce what it calls a warning.**

    Cost is the negative log likelihood of "exactly one class active on this row" —
    `-log p_c - Σ log(1 - p_c')` — so two classes both confident on one row is
    penalised rather than silently producing the overlap it used to.

    Runs in `O(n_rows · n_classes)` via prefix sums and a running minimum, not the
    `O(n²)` the segment formulation suggests: the best predecessor of row `j` is a
    minimum over a *prefix*, so it is carried forward instead of rescanned.
    """
    import numpy as np
    p = np.clip(np.asarray(rows, dtype=np.float64), 1e-6, 1 - 1e-6)
    n, k = p.shape
    log_off = np.log1p(-p)                       # log(1 - p), per row per class
    all_off = log_off.sum(axis=1)                # every class silent: whitespace
    # -(log p_c + Σ_{c'≠c} log(1-p_c')) for each class, plus the whitespace state.
    per_class = -(np.log(p) + (all_off[:, None] - log_off))
    cost = np.concatenate([per_class, -all_off[:, None]], axis=1)   # last = gap

    pre = np.zeros((n + 1, k + 1))
    np.cumsum(cost, axis=0, out=pre[1:])
    mins = [(int(gap_min) if s == k else int(min_len)) for s in range(k + 1)]

    INF = float("inf")
    best = np.full(n + 1, INF)
    best[0] = 0.0
    back = [None] * (n + 1)
    run_min = [INF] * (k + 1)
    run_arg = [-1] * (k + 1)
    for j in range(1, n + 1):
        for s in range(k + 1):
            i = j - mins[s]
            if i >= 0 and best[i] < INF:
                v = best[i] - pre[i, s]
                if v < run_min[s]:
                    run_min[s], run_arg[s] = v, i
            if run_arg[s] < 0:
                continue
            tot = run_min[s] + pre[j, s]
            if tot < best[j]:
                best[j] = tot
                back[j] = (run_arg[s], s)

    out, j = [], n
    while j > 0 and back[j] is not None:
        i, s = back[j]
        out.append((i, j, None if s == k else s))
        j = i
    out.reverse()
    # Adjacent runs of one label are one band — the fragmentation fix, and the
    # reason the DP needs no rule against splitting a paragraph in two.
    merged = []
    for seg in out:
        if merged and merged[-1][2] == seg[2] and merged[-1][1] == seg[0]:
            merged[-1] = (merged[-1][0], seg[1], seg[2])
        else:
            merged.append(seg)
    return merged


def _dp_zones(ref: str, root: Path, cfg: dict, net, page,
              device: str = "cuda:0") -> list[dict]:
    """This page's bands, decoded from the heatmap. The shared half of `predict_dp`.

    Extracted so that scoring a model and writing a prediction run the *same* decode
    rather than two copies of it — a measurement of a decoder that is not the decoder
    is a measurement of nothing.
    """
    import numpy as np
    from kraken.blla import compute_segmentation_map
    rets = compute_segmentation_map(page, None, net, device)
    hm = rets["heatmap"]
    sx, sy = rets["scale"]
    labels = sorted(rets["cls_map"]["regions"], key=rets["cls_map"]["regions"].get)
    idxs = [rets["cls_map"]["regions"][l] for l in labels]

    windows = page_windows(ref, root, cfg)
    if len(windows) > 1:
        # A two-column page is two chains, not one. Collapsing x across both columns
        # and the gutter would produce a single confident partition of something
        # that is not one — refuse rather than answer the wrong question.
        raise ValueError(
            f"{ref} resolves to {len(windows)} columns; the segmental decode models "
            "a page as one vertical chain and would average across the gutter")
    w = windows[0]
    x0 = max(0, int(w["x0"] / sx))
    x1 = min(hm.shape[2], max(x0 + 1, int(w["x1"] / sx)))
    rows = np.stack([hm[i, :, x0:x1].mean(axis=1) for i in idxs], axis=1)

    segs = _segmental_decode(rows, max(1, int(round(cfg["min_zone_h_px"] / sy))))
    return [{"label": labels[s], "x0": w["x0"], "x1": w["x1"],
             "y0": int(round(i * sy)), "y1": int(round(j * sy))}
            for i, j, s in segs if s is not None]


def predict_dp(ref: str, root: Path = Path("."), net=None, sha: str = "",
               model_path: str | Path = DEFAULT_MODEL, device: str = "auto",
               cfg: dict | None = None) -> dict:
    """Predict one page by decoding the heatmap as a chain of bands.

    Same network, same weights, same blotted input as `predict`; only the decode
    differs. Rather than thresholding each class map and vectorising the blobs, the
    heatmap is reduced to per-row class scores across the page's own measured text
    column and handed to `_segmental_decode`, which returns a partition.

    Two things follow that the blob decode cannot give. The x is the **configured
    column**, because the band is a band — which is the same resolution the editor
    applies to a proposal, done once here instead of on the way past. And the output
    is already what `validate_page` calls legal: no overlaps, nothing under the
    minimum height, one band per run of a label.

    Written into `mz/zones/` like any other prediction, with `decoder` in the
    provenance and a `dp_` id prefix, so which decode produced a file is readable
    from the file rather than from what was running at the time.
    """
    import numpy as np
    from PIL import Image
    from kraken.blla import compute_segmentation_map
    from kraken.containers import ProcessingStep

    cfg = cfg or zc.load_config(root)
    ref = norm_ref(ref)
    blot = blot_dir(root) / f"chukchi-{ref}.png"
    if not blot.exists():
        raise FileNotFoundError(
            f"no blotted raster for {ref} at {blot} — run `harness zones blot` "
            "first. Predicting off the plain scan would ask the model a different "
            "question than the one it was trained on.")
    if net is None:
        net, sha = load_segmenter(model_path, root)
    elif not sha:
        raise ValueError(
            "predict_dp(net=...) needs the model's sha256 too — a prediction whose "
            "provenance field is empty cannot be told from one that was checked")
    if device == "auto":
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    with Image.open(blot) as src:
        page = src.convert("RGB")
    size = page.size
    zones = _dp_zones(ref, root, cfg, net, page, device)
    # **The paragraph split is part of the decode, not an afterthought.** Two
    # abutting `MainZone-P` rectangles rasterize to one training target, so the
    # segmenter cannot emit the boundary between them — and 42% of the boundaries in
    # `gt/zones/` are exactly that. A prediction without this step under-segments the
    # page by that proportion no matter how good the model is, which is why it runs
    # here rather than being left for a human to notice.
    from .lines import ink_mask
    ink = ink_mask(page)
    before = len(zones)
    zones = split_at_paragraphs(zones, ref, root, cfg, ink)
    split_added = len(zones) - before

    step = ProcessingStep(
        id="harness-zones-predict",
        category="processing",
        description="region segmentation, harness zones predict --decode dp",
        settings={"model": str(model_path), "sha256": sha, "device": device,
                  "decoder": "segmental-dp + paragraph-split",
                  "paragraph_cuts": split_added,
                  "input": f"{BLOTDIR}/chukchi-{ref}.png"})
    tree = build_alto(ref, zones, size, id_prefix=DP_ID_PREFIX)
    # The provenance kraken would have written for us on the blob path; here the
    # writer is ours, so the step is spliced in by hand rather than dropped.
    desc = tree.getroot().find(f"{{{ALTO_NS}}}Description")
    proc = etree.SubElement(desc, f"{{{ALTO_NS}}}Processing", {"ID": "OCR_0"})
    etree.SubElement(proc, f"{{{ALTO_NS}}}processingStepDescription").text = \
        step.description
    etree.SubElement(proc, f"{{{ALTO_NS}}}processingStepSettings").text = \
        "; ".join(f"{k}: {v}" for k, v in step.settings.items())
    soft = etree.SubElement(proc, f"{{{ALTO_NS}}}processingSoftware")
    etree.SubElement(soft, f"{{{ALTO_NS}}}softwareName").text = "harness zones"

    out = mz_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    dest = alto_for(ref, root, MZDIR)
    tmp = dest.with_suffix(".xml.tmp")
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    tmp.replace(dest)
    return {"ref": ref, "path": str(dest), "zones": len(zones),
            "labels": " ".join(sorted({z["label"] for z in zones}))}


def predict(ref: str, root: Path = Path("."), net=None, sha: str = "",
            model_path: str | Path = DEFAULT_MODEL, device: str = "auto") -> dict:
    """Run the segmenter over one page and write raw ALTO into `mz/zones/`.

    Three properties, each of which is a rule this repo already keeps elsewhere.

    **The input is the blotted raster, and a page with no blot is refused.** That is
    what the model was trained on — figures painted white so a paragraph wrapping an
    illustration cannot shape what it learned about zone geometry — so predicting off
    the plain scan asks a different question of it, and asks it on exactly the 252
    pages where the difference exists. `assemble` refuses the same substitution for
    the same reason.

    **What is written is what the model emitted.** Free polygons at whatever x
    kraken drew, kraken's own ids, kraken's own ALTO dialect. Snapping to a
    configured band is a human act and happens in the editor, on the way into
    `gt/zones/`. A store that quietly normalised its contents would no longer be
    able to tell you what the model did.

    **Provenance travels in the file.** The `Processing` block names this harness,
    the model's path and its sha256, so a prediction is identifiable from its own
    bytes — the property whose absence, when a file's role lived only in the
    directory holding it, cost this project 18 pages of transcription. `imagename`
    is set to the bare `chukchi-PP-NNN.png` the gt store writes, rather than the
    `scans-fig-blotted/...` path kraken would otherwise record, so the two stores
    name a page's raster the same way.
    """
    # **The refusal comes before the imports**, because `from kraken import blla`
    # pulls in torch and costs ~1.9 s, and a page with no blot never needs either.
    # Cheap-check-then-load rather than load-then-check is worth stating as a habit:
    # the check is what the caller most often hits.
    ref = norm_ref(ref)
    blot = blot_dir(root) / f"chukchi-{ref}.png"
    if not blot.exists():
        raise FileNotFoundError(
            f"no blotted raster for {ref} at {blot} — run `harness zones blot` "
            "first. Predicting off the plain scan would ask the model a different "
            "question than the one it was trained on.")

    from PIL import Image
    from kraken import blla, serialization
    from kraken.containers import ProcessingStep

    if net is None:
        net, sha = load_segmenter(model_path, root)
    elif not sha:
        # A caller reusing a loaded model has to carry its hash along with it.
        # Without this the file is written with `sha256: ""` — provenance that is
        # present, well-formed and says nothing, which is worse than absent because
        # it reads as recorded. Same reason `set_ink_exempt` refuses a missing note.
        raise ValueError(
            "predict(net=...) needs the model's sha256 too — a prediction whose "
            "provenance field is empty cannot be told from one that was checked")
    if device == "auto":
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    with Image.open(blot) as src:
        # `convert` is a copy, so it outlives the `with`; `src` is what holds the
        # file handle and what the block is here to close.
        page = src.convert("RGB")
    size = page.size
    seg = blla.segment(page, model=net, device=device)
    # The gt store's own name for the raster (`build_alto`), not the blotted path
    # kraken defaults to: the two stores describe one page and should say so alike.
    seg.imagename = f"chukchi-{ref}.png"
    step = ProcessingStep(
        id="harness-zones-predict",
        category="processing",
        description="region segmentation, harness zones predict",
        settings={"model": str(model_path), "sha256": sha, "device": device,
                  "input": f"{BLOTDIR}/chukchi-{ref}.png"})
    xml = serialization.serialize(seg, image_size=size, template="alto",
                                  processing_steps=[step])

    out = mz_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    dest = alto_for(ref, root, MZDIR)
    tmp = dest.with_suffix(".xml.tmp")
    tmp.write_text(xml, encoding="utf-8")
    tmp.replace(dest)
    regions = {k: len(v) for k, v in (seg.regions or {}).items() if v}
    return {"ref": ref, "path": str(dest),
            "zones": sum(regions.values()),
            "labels": " ".join(sorted(regions))}


def predict_skip(ref: str, root: Path = Path("."), force: bool = False,
                 splits: dict | None = None, single: bool = False) -> str:
    """Why this page should not be predicted, or `""` to go ahead.

    One rule, in one place, because there are two callers — the CLI sweep and the
    editor's bulk button — and a client that decided for itself would be a second
    copy of it, drifting from this one the moment either changed.

    **`exempt` is refused outright, `force` or not.** A human has ruled the page not
    a text page — a plate, a map, a foldout, a blank — so a prediction there
    manufactures zones for a page with no right answer and then sits in the store
    looking like any other reading. `assemble` keeps them out of training and eval on
    the same grounds. `single` is the override, and it is a separate flag from
    `force` because the two excuse different things — one says "I mean this page
    even though it is a plate", the other "replace what is there". Naming a ref on
    the command line, or pressing the key on the page itself, is `single`.

    **An existing prediction is kept unless `force`.** The reason is not politeness
    about GPU time: an mz file records the sha256 of the model that wrote it, which
    is the only thing in the store saying *which* model spoke. Re-predicting
    everything after a retrain, unasked, would replace that record page by page and
    leave nothing able to tell you the store had ever held two models' output. Skip
    by default and the sha stays true to the file it is on.
    """
    if not single and (splits if splits is not None
                       else load_splits(root)).get(ref) == "exempt":
        return "ruled not a text page"
    if not force and has_zones(ref, root, MZDIR):
        return "already predicted"
    if not (blot_dir(root) / f"chukchi-{ref}.png").exists():
        return "no blotted raster"
    return ""


def predict_all(root: Path = Path("."), refs: list[str] | None = None,
                model_path: str | Path = DEFAULT_MODEL,
                device: str = "auto", decode: str = "raw",
                force: bool = False) -> dict:
    """Predict over a work-list, or over every page that has a blotted raster.

    What is skipped and why is `predict_skip`'s; this loops and reports. A sweep is
    therefore **resumable by construction** — run it again and it picks up the pages
    that have nothing, which over 832 pages of GPU work is the difference between an
    interruption costing minutes and costing the run.

    The model is loaded once for the whole run, which is most of why this exists as
    a sweep rather than a shell loop over the single-page form.
    """
    import time
    net, sha = load_segmenter(model_path, root)
    splits = load_splits(root)
    if refs is None:
        from .context import all_scans
        refs = all_scans(root)

    started = time.monotonic()
    done, no_blot, exempted, already = 0, [], 0, 0
    zones = 0
    for ref in refs:
        why = predict_skip(ref, root, force, splits)
        if why == "ruled not a text page":
            exempted += 1
            continue
        if why == "already predicted":
            already += 1
            continue
        if why:
            no_blot.append(ref)
            continue
        fn = predict_dp if decode == "dp" else predict
        r = fn(ref, root, net=net, sha=sha, model_path=model_path, device=device)
        zones += r["zones"]
        done += 1
    return {"dir": str(mz_dir(root)), "decoder": decode,
            "predicted": done, "zones": zones,
            "exempt_skipped": exempted,
            "already_predicted": already,
            "skipped_no_blot": " ".join(no_blot),
            "model": str(model_path), "sha256": sha,
            "elapsed_s": round(time.monotonic() - started, 1)}


# ------------------------------------------------------------- paragraph edges

def _para_ink(ref: str, root: Path = Path(".")):
    """The raster this check reads: **figure-blotted**, falling back to the scan.

    A figure is a solid block of ink spanning hundreds of rows, and a row counts as
    inked if any pixel in it is dark — so on a page where text wraps around an
    illustration the figure welds every line it touches into one run, and a merged
    run reports the leftmost ink of all of them, which is never an indent. That is
    not a limit of the indent rule; it is reading the wrong raster.

    `scans-fig-blotted/` is also what the segmenter is trained and predicted on, so
    reading it here makes the check and the decoder see the same page.
    """
    from .lines import ink_mask
    blot = blot_dir(root) / f"chukchi-{norm_ref(ref)}.png"
    return ink_mask(blot if blot.exists() else scan_for(ref, root))


def _figure_rects(ref: str, root: Path = Path(".")) -> list[tuple[int, int, int, int]]:
    """`(x0, x1, y0, y1)` for every figure zone on the page, from `gt/fig/`.

    Both axes, because the x is what makes a wrapped line readable. Text set beside
    an illustration is a real column with a real left margin — it is *not*
    unjudgeable, which is what an earlier version of this claimed on no evidence.
    On `1-143` the figure sits right and 453 px of text wraps left, indented exactly
    as any other line.

    What is unreadable is the strip the figure occupies. Blotting paints the
    declared box white and **the declared box is not the whole illustration** — a
    rule or a plate edge routinely survives just outside it, and such a leftover
    spans the figure's width, so its leftmost ink is the figure's left edge and it
    reads as a 400 px indent. That is where the 523 false positives came from, not
    from the wrapped text.
    """
    from .figures import zones as fig_zones
    try:
        return [(z["hpos"], z["hpos"] + z["width"],
                 z["vpos"], z["vpos"] + z["height"]) for z in fig_zones(ref, root)]
    except Exception:
        return []


def _ink_lines(ink, y0: int, y1: int, x0: int, x1: int,
               min_h: int, min_w: int,
               figs: list[tuple[int, int, int, int]] | None = None
               ) -> list[list]:
    """Lines of type inside a band: `[y0, y1, left, right, strip]`, reading order.

    Row-runs of ink, bounded to the text column, with two floors. `min_h` drops a
    run too short to be a line; `min_w` drops one too *narrow* — a run 4 to 21 px
    wide is a speck in the margin, and five of the first twenty spurious paragraph
    breaks found were exactly that.

    `left`/`right` are offsets from `x0`, **not yet indents**: they become indents
    only after `_page_margins` subtracts the margin the page's own body establishes.
    Doing that here, per band, was a measured regression — a zone whose head is
    flush sets its own minimum, so the head reported an indent of 0 against itself,
    and 61 boundaries went missing that way.
    """
    import numpy as np
    sub = ink[y0:y1, x0:x1]
    rows = sub.any(axis=1)
    runs, s = [], None
    for i, v in enumerate(rows):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if i - s >= min_h:
                runs.append((s, i))
            s = None
    if s is not None and len(rows) - s >= min_h:
        runs.append((s, len(rows)))
    out = []
    for a, b in runs:
        ay, by = y0 + a, y0 + b
        # Where a run shares rows with a figure, measure only the strip of column
        # *outside* it — the side the text actually wraps on, whichever is wider.
        # Two things fall out. The figure's own leftover ink is no longer looked at,
        # so a surviving rule stops reading as a huge indent. And the wrapped text
        # is measured against its own margin, which is the strip's edge rather than
        # the column's, so a line beside a figure is judged like any other.
        lo, hi = 0, x1 - x0
        over = [f for f in (figs or []) if ay < f[3] and by > f[2]]
        if over:
            fl, fr = min(f[0] for f in over), max(f[1] for f in over)
            left_w = max(0, min(fl, x1) - x0)
            right_w = max(0, x1 - max(fr, x0))
            if left_w >= right_w:
                lo, hi = 0, left_w
            else:
                lo, hi = max(fr, x0) - x0, x1 - x0
        if hi - lo < min_w:
            continue           # nothing left to read: genuinely unjudgeable
        cols = np.where(sub[a:b, lo:hi].any(axis=0))[0]
        if len(cols) and cols[-1] - cols[0] >= min_w:
            out.append([ay, by, lo + int(cols[0]), lo + int(cols[-1]), (lo, hi)])

    return out


def _page_margins(lines: list[list], min_w: int) -> dict[int, int]:
    """The left margin each column of the **page** sets — `{strip_lo: margin}`.

    **Indent is measured against the margin the page's body establishes**, not the
    column edge, not the figure's bbox, and — this is the part that had to be
    learned twice — not the zone's own lines.

    Against the figure's box it read the gutter as an indent on every wrapped line:
    `1-146` gave 41,42,42,42,41,41,41 on eight consecutive lines, then 52,53,53,53,
    53,52,51 on seven more. A constant offset across a run of lines is a margin; a
    paragraph indent happens on one line.

    Against the *zone's* own lines it was worse in the other direction: a zone whose
    head is flush left is its own minimum, so the head measured 0 against itself and
    61 asserted boundaries vanished, taking recall from 95.3% to 88.4%. Pooling
    across the page fixes that — a flush head is still compared with where the page
    actually sets its text.

    Strips within `min_w` of each other are one column: a figure and its caption are
    separate zones with separate widths (`1-146`: GraphicZone ends at 1140, FigDesc
    at 1164), and keying on the exact edge splits one wrapped column into groups of
    two or three lines, which is too few to carry a margin.
    """
    edges = sorted({ln[4][0] for ln in lines})
    cluster: dict[int, int] = {}
    cid = 0
    for i, e in enumerate(edges):
        if i and e - edges[i - 1] > min_w:
            cid += 1
        cluster[e] = cid
    mins: dict[int, int] = {}
    for ln in lines:
        k = cluster[ln[4][0]]
        mins[k] = min(mins.get(k, ln[2]), ln[2])
    return {e: mins[cluster[e]] for e in edges}


def _page_lines(zones: list[dict], ink, figs, min_h: int, min_w: int
                ) -> dict[int, list[tuple[int, int, int, int]]]:
    """Every zone's lines, with indents normalised against the whole page.

    Two passes: detect raw across all zones, establish the page's margins, then
    subtract. One pass per zone cannot do this — the margin is a property of the
    page's typography, not of whichever band happens to be under inspection.
    """
    raw = {i: _ink_lines(ink, z["y0"], z["y1"], z["x0"], z["x1"],
                         min_h, min_w, figs)
           for i, z in enumerate(zones)}
    margins = _page_margins([ln for v in raw.values() for ln in v], min_w)
    return {i: [(ay, by, left - margins[lo], right - margins[lo])
                for ay, by, left, right, (lo, _hi) in v]
            for i, v in raw.items()}


def paragraph_starts(ref: str, root: Path = Path("."), cfg: dict | None = None,
                     zones: list[dict] | None = None, ink=None,
                     store: str = ZONEDIR) -> list[dict]:
    """Lines that open a paragraph *inside* a body zone — places it should be two.

    The one implementation, and it has two consumers on purpose. As a **check** it
    finds keying slips, where several paragraphs were saved as one zone; run over
    the corpus it found 20 such lines, 15 of which were exactly that and were fixed.
    As a **decoder step** it splits a predicted band, which the segmenter cannot do
    at all — two abutting `MainZone-P` rectangles rasterize to one continuous target,
    so the boundary is gone before the network sees it.

    A zone's own first line is never reported: that boundary already exists. Only
    labels listed in the config's `paragraph_split.labels` are examined, since an
    indent means something else inside a footnote or a running title.

    `index` is **1-based, within the zone** — the ordinal a human counts down the
    band — with `zone` likewise 1-based in reading order. `y` rides along for
    anything that needs to point at the raster.
    """
    cfg = cfg or zc.load_config(root)
    spec = cfg.get("paragraph_split") or {}
    indent = int(spec.get("indent_px", 40))
    labels = set(spec.get("labels") or [])
    min_h = int(spec.get("min_line_h_px", 6))
    min_w = int(spec.get("min_line_w_px", 50))
    if not labels:
        return []

    ref = norm_ref(ref)
    if zones is None:
        zones = read_zones(ref, root, store=store)
    if ink is None:
        ink = _para_ink(ref, root)

    figs = _figure_rects(ref, root)
    by_zone = _page_lines(zones, ink, figs, min_h, min_w)
    out = []
    for zi, z in enumerate(zones, start=1):
        if z["label"] not in labels:
            continue
        rows = by_zone[zi - 1]
        for li, (ly0, ly1, left, right) in enumerate(rows, start=1):
            if li == 1:
                continue                     # the zone's own head, already a boundary
            if left >= indent:
                out.append({"ref": ref, "zone": zi, "label": z["label"],
                            "index": li, "y": ly0,
                            "indent": left, "width": right - left})
    return out


def split_at_paragraphs(zones: list[dict], ref: str, root: Path = Path("."),
                        cfg: dict | None = None, ink=None) -> list[dict]:
    """Cut each body zone at the paragraph openings inside it.

    The decoder half of `paragraph_starts`. Splits are made at the *top of the
    opening line*, so the new zone begins where its first line begins — matching how
    the editor draws one, and how `gt/zones/` records the 561 abutting pairs.
    """
    cfg = cfg or zc.load_config(root)
    spec = cfg.get("paragraph_split") or {}
    min_h = int(cfg.get("min_zone_h_px", 30))
    direction = spec.get("consolidate", "down")

    marks: dict[int, list[int]] = {}
    for s in paragraph_starts(ref, root, cfg, zones=zones, ink=ink):
        marks.setdefault(s["zone"], []).append(s["y"])
    if not marks:
        return zones
    out = []
    for zi, z in enumerate(zones, start=1):
        cuts = sorted(marks.get(zi, []))
        if not cuts:
            out.append(z)
            continue
        edges = [z["y0"], *cuts, z["y1"]]
        segs = [[a, b, z["label"]] for a, b in zip(edges, edges[1:]) if b > a]
        for a, b, _lab in _consolidate(segs, min_h, direction):
            out.append({**z, "y0": a, "y1": b})
    return out


def _consolidate(segs: list[list], min_h: int,
                 direction: str = "down") -> list[list]:
    """Fold fragments under `min_h` into a neighbour **of the same label**.

    A cut is made at the top of the opening *line*, so whatever sat above it is left
    behind as its own band — usually the whitespace between two paragraphs, sometimes
    a speck the line detector took for a line. Those are not zones by the store's own
    rule (`min_zone_h_px`), they are invisible at any zoom, and every one of them
    would be a `min-height` error the moment it was saved.

    **Same label, always.** Splitting one zone produces pieces that all share its
    label, so within `split_at_paragraphs` the rule costs nothing — which is exactly
    why it is written down rather than left to hold by accident. Applied to a
    decoder's output, where adjacent bands genuinely differ, merging a sliver into
    whatever happens to sit beside it would silently retype a strip of the page.

    `direction` decides which way a fragment goes when both neighbours match — `down`
    into the paragraph below, which is right when the fragment is leading whitespace.
    Where only one side matches, that side is used regardless of preference. Where
    **neither** matches the fragment is left standing, and that is the honest
    outcome: `validate_page` will call it a `min-height` error, which is a finding
    about the decode rather than something to paper over.

    Iterates to a fixed point, since folding one fragment can leave another short.
    """
    segs = [list(s) for s in segs]
    while len(segs) > 1:
        for i, s in enumerate(segs):
            if s[1] - s[0] >= min_h:
                continue
            order = ((i + 1, i - 1) if direction == "down" else (i - 1, i + 1))
            merged = False
            for j in order:
                if 0 <= j < len(segs) and j != i and segs[j][2] == s[2]:
                    segs[j][0] = min(segs[j][0], s[0])
                    segs[j][1] = max(segs[j][1], s[1])
                    segs.pop(i)
                    merged = True
                    break
            if merged:
                break
        else:
            break
    return segs


def _line_health(heights: list[int]) -> dict:
    """Whether line detection is separating lines or merging them.

    A line of type here is ~45 px. Runs at roughly double that are two lines a
    single dark pixel joined — a descender, a speck, bleed-through — and a merged
    run reports the leftmost ink of both, so an indented opening reads as flush.
    That is the one way this detector can be wrong without anything looking wrong,
    which is why it is measured rather than assumed.
    """
    if not heights:
        return {"line_h_median": 0, "lines_merged_suspected": 0}
    v = sorted(heights)
    med = v[len(v) // 2]
    return {"line_h_median": med,
            "line_h_p90": v[int(0.9 * len(v))],
            "line_h_max": v[-1],
            "lines_merged_suspected": sum(1 for h in v if h >= 1.6 * med),
            "lines_total": len(v)}


def page_zones_table(ref: str, root: Path = Path("."),
                     store: str = ZONEDIR) -> list[dict]:
    """One page's zones, flat and 1-based — what the page *is*, not what is wrong.

    `validate_page` reports findings; until now nothing printed the zones
    themselves, so reading a page's layout meant opening the editor or writing a
    loop. `zone` matches the editor's own numbering and the audit's `zone` column.
    """
    return [{"zone": i, "label": z["label"],
             "y0": z["y0"], "y1": z["y1"], "h": z["y1"] - z["y0"],
             "x0": z["x0"], "x1": z["x1"]}
            for i, z in enumerate(read_zones(ref, root, store=store), start=1)]


def zone_diff(ref: str, root: Path = Path("."),
              cfg: dict | None = None) -> list[dict]:
    """What differs between `gt/zones/` and `mz/zones/` for one page.

    Paired by greatest vertical overlap, as `score` pairs zones for the same reason:
    these are a vertical partition, so overlap is the honest correspondence. Four
    kinds, and they want different things done about them —

    - `only_in_gt`  a zone the machine store has nothing over: a missed region
    - `only_in_mz`  a zone with no counterpart keyed: an invented one
    - `label`       paired, but named differently
    - `edge`        paired and named alike, but a boundary moved by more than
                    `min_zone_h_px` — the same region, cut in a different place

    `edge` is deliberately tolerant: a cut lands on the opening line's ink while an
    editor clicks in the whitespace above it, so a few px of disagreement is the two
    conventions meeting rather than a difference worth reporting.
    """
    cfg = cfg or zc.load_config(root)
    tol = int(cfg.get("min_zone_h_px", 30))
    ref = norm_ref(ref)
    gt = read_zones(ref, root, store=ZONEDIR)
    mz = read_zones(ref, root, store=MZDIR)

    def best(z, pool):
        b, ov = None, 0
        for p in pool:
            v = _y_overlap(z, p)
            if v > ov:
                b, ov = p, v
        return b

    rows, paired = [], set()
    for i, g in enumerate(gt, start=1):
        m = best(g, mz)
        if m is None:
            rows.append({"ref": ref, "kind": "only_in_gt", "zone": i,
                         "gt": f"{g['label']} {g['y0']}..{g['y1']}", "mz": "",
                         "delta": ""})
            continue
        paired.add(id(m))
        if m["label"] != g["label"]:
            rows.append({"ref": ref, "kind": "label", "zone": i,
                         "gt": f"{g['label']} {g['y0']}..{g['y1']}",
                         "mz": f"{m['label']} {m['y0']}..{m['y1']}", "delta": ""})
        elif abs(m["y0"] - g["y0"]) > tol or abs(m["y1"] - g["y1"]) > tol:
            rows.append({"ref": ref, "kind": "edge", "zone": i,
                         "gt": f"{g['label']} {g['y0']}..{g['y1']}",
                         "mz": f"{m['label']} {m['y0']}..{m['y1']}",
                         "delta": f"{m['y0'] - g['y0']:+d}/{m['y1'] - g['y1']:+d}"})
    for m in mz:
        if id(m) not in paired and best(m, gt) is None:
            rows.append({"ref": ref, "kind": "only_in_mz", "zone": 0, "gt": "",
                         "mz": f"{m['label']} {m['y0']}..{m['y1']}", "delta": ""})
    return rows


def page_zone_lines(ref: str, root: Path = Path("."), cfg: dict | None = None,
                    store: str = ZONEDIR) -> list[dict]:
    """Every zone's lines of type, as a flat table — the page as the checks see it.

    `zone`/`line` are 1-based; `indent` is measured against the margin the page's
    body establishes, so a paragraph opening stands out against a body line's 2-10.
    `h` is the giveaway for the two ways line detection fails: ~6 px is a speck that
    passed the floor, ~100 px is two lines a descender welded together.

    Exists because it was written by hand three times while diagnosing this, which
    is the tell that a verb was missing. Every consumer of a raster in this module
    reads the same thing; this is the one that shows it.
    """
    cfg = cfg or zc.load_config(root)
    spec = cfg.get("paragraph_split") or {}
    min_h = int(spec.get("min_line_h_px", 6))
    min_w = int(spec.get("min_line_w_px", 50))
    ref = norm_ref(ref)
    zones = read_zones(ref, root, store=store)
    if not zones:
        return []
    ink = _para_ink(ref, root)
    by_zone = _page_lines(zones, ink, _figure_rects(ref, root), min_h, min_w)
    out = []
    for zi, z in enumerate(zones):
        for li, (a, b, left, right) in enumerate(by_zone[zi], start=1):
            out.append({"zone": zi + 1, "label": z["label"],
                        "line": li, "y": a, "h": b - a,
                        "indent": left, "width": right - left})
    return out


def _same_label_runs(zones: list[dict]) -> list[list[dict]]:
    """Consecutive same-label zones that abut, grouped.

    This is the page **as a segmenter can give it**. Two adjacent `MainZone-P`
    rectangles rasterize to one continuous target, so no model trained on this store
    can produce the boundary between them — it has to be recovered from the ink
    afterwards. Merging the run back is therefore not a convenience, it is the
    honest input to the test: reproducing a boundary the input already contains
    would measure nothing.
    """
    runs: list[list[dict]] = []
    for z in zones:
        if (runs and runs[-1][-1]["label"] == z["label"]
                and z["y0"] - runs[-1][-1]["y1"] <= 2):
            runs[-1].append(z)
        else:
            runs.append([z])
    return runs


def paragraph_audit(root: Path = Path("."), cfg: dict | None = None,
                    refs: list[str] | None = None,
                    store: str = ZONEDIR) -> tuple[dict, list[dict]]:
    """How well the indent rule finds paragraph boundaries, and where it does not.

    Both directions in one pass, because quoting either alone has already caused
    confusion here — a recall measured on a convenient sample was reported beside a
    fire-count from the whole corpus as though they were one number. They are not,
    and they have different denominators:

    - **`false_negative`** — `gt/zones/` asserts a boundary the rule does not produce.
      Measured against a *positive assertion* by an editor, so this one is
      trustworthy.
    - **`false_positive`** — the rule produces a boundary gt does not have. Still a
      worklist rather than a precision figure, because **gt cannot arbitrate**: it is
      the thing the rule corrects, and of the first twenty found, 15 were keying
      slips and were fixed.

    **What is compared is the page the rule would produce, not where it fires.**
    Earlier this counted firings, which overstated the damage badly: consolidation
    folds a cut whose upper fragment is whitespace straight back, so 34 of 47 flagged
    pages came out identical to the keying and were still being counted against the
    rule. A firing that changes nothing is not an error in any sense worth reporting.

    Each same-label run is merged before the rule sees it, because **that is the page
    a segmenter can give**: two abutting `MainZone-P` rectangles rasterize to one
    target, so the boundary between them is not in any model's output and has to be
    recovered from the ink. Handing the rule a page that already contains the answer
    would measure nothing.

    Boundaries match within `min_zone_h_px`, since a cut lands on the opening line's
    ink while an editor clicks in the whitespace above it.

    Report only, exit 0. Reads a raster per page.
    """
    from .lines import ink_mask
    cfg = cfg or zc.load_config(root)
    spec = cfg.get("paragraph_split") or {}
    labels = set(spec.get("labels") or [])
    min_h = int(spec.get("min_line_h_px", 6))
    min_w = int(spec.get("min_line_w_px", 50))
    splits = load_splits(root)

    rows: list[dict] = []
    pages = asserted = recovered = internal = fired = 0
    # Every detected line's height. A "line" here is a run of rows with ink in them,
    # bounded by a *completely blank* row — so nothing accumulates, but one dark
    # pixel merges two lines into one run, and a merged run reports the leftmost ink
    # of both. That would read an indented paragraph opening as flush. If merging is
    # happening, it shows up as a population at roughly twice the median height.
    line_heights: list[int] = []
    for ref in (refs if refs is not None else zone_refs(root, store)):
        if splits.get(ref) == "exempt":
            continue
        zones = read_zones(ref, root, store=store)
        if not zones:
            continue
        try:
            ink = _para_ink(ref, root)
        except FileNotFoundError:
            continue
        pages += 1
        figs = _figure_rects(ref, root)
        tol = int(cfg.get("min_zone_h_px", 30))
        by_zone = _page_lines(zones, ink, figs, min_h, min_w)
        line_heights.extend(l[1] - l[0] for v in by_zone.values() for l in v)

        zi = 0
        for run in _same_label_runs(zones):
            first = zi + 1
            zi += len(run)
            if run[0]["label"] not in labels:
                continue
            merged = {**run[0], "y1": run[-1]["y1"]}
            want = [z["y0"] for z in run[1:]]           # what the editor keyed

            starts = paragraph_starts(ref, root, cfg, zones=[merged], ink=ink)
            mlines = _page_lines([merged], ink, figs, min_h, min_w)[0]
            internal += max(0, len(mlines) - 1)
            got_zones = split_at_paragraphs([merged], ref, root, cfg, ink)
            got = [z["y0"] for z in got_zones[1:]]      # what survives consolidation
            fired += len(got)
            detail = {s["y"]: s for s in starts}

            used = set()
            for w in want:
                asserted += 1
                hit = next((g for g in got
                            if g not in used and abs(g - w) <= tol), None)
                if hit is not None:
                    used.add(hit)
                    recovered += 1
                else:
                    # The **detected line** at that boundary, not the fired ones.
                    # Consulting only `starts` conflated "no line there" with "a
                    # line, just under threshold", since a start below `indent_px`
                    # never enters that dict — and every one of the 29 misses
                    # therefore reported -1, which read as a line-detection failure.
                    # `1-056` is the counter-example: indent 36 against a 40 floor.
                    ln = next((l for l in mlines if abs(l[0] - w) <= tol), None)
                    rows.append({"kind": "false_negative", "ref": ref, "zone": first,
                                 "label": run[0]["label"],
                                 "index": want.index(w) + 2, "y": w,
                                 "indent": ln[2] if ln else -1,
                                 "width": (ln[3] - ln[2]) if ln else -1,
                                 "h": (ln[1] - ln[0]) if ln else -1})
            for g in got:
                if g in used:
                    continue
                d = detail.get(g, {})
                rows.append({"kind": "false_positive", "ref": ref, "zone": first,
                             "label": run[0]["label"],
                             "index": d.get("index", -1), "y": g,
                             "indent": d.get("indent", -1),
                             "width": d.get("width", -1),
                             "h": d.get("h", -1)})

    fn = [r for r in rows if r["kind"] == "false_negative"]
    return ({"pages_read": pages,
             "asserted_boundaries": asserted,
             "recovered": recovered,
             "recall_pct": round(100 * recovered / asserted, 1) if asserted else 0.0,
             "false_negatives": len(fn),
             # Three ways to miss, and they have different remedies: no line was
             # detected there at all (welded or dropped), a line was seen but sits
             # near the margin, or it is just under the threshold.
             "fn_no_line_detected": sum(1 for r in fn if r["indent"] < 0),
             "fn_flush_left": sum(1 for r in fn if 0 <= r["indent"] < 10),
             "fn_slight_indent": sum(1 for r in fn if 10 <= r["indent"]),
             "boundaries_produced": fired,
             "false_positives": len(rows) - len(fn),
             "pages_changed": len({r["ref"] for r in rows
                                   if r["kind"] == "false_positive"}),
             **_line_health(line_heights),
             "note": ("measured on the page the rule *produces*, after "
                      "consolidation — not on where it fires, which counted cuts "
                      "that fold straight back and so overstated the damage. Each "
                      "same-label run is merged first, because that is the page a "
                      "segmenter can give. Boundaries match within min_zone_h_px. "
                      "`false_positive` is still a worklist rather than a rate: gt "
                      "cannot arbitrate, being what the rule corrects")},
            rows)


# ---------------------------------------------------------------- the scoring

def model_split_path(model_path: str | Path, split: str,
                     root: Path = Path(".")) -> Path:
    p = Path(model_path)
    if not p.is_absolute():
        p = root / p
    return p.with_suffix(f".{split}.lst")


def model_splits(model_path: str | Path,
                 root: Path = Path(".")) -> dict[str, str] | None:
    """The split **this model** trained on, from the lists copied beside it.

    Verbatim copies of the `train.lst`/`eval.lst` the run consumed — same format,
    same `_read_lst`, no translation. A JSON re-encoding would be a second
    representation of one fact, and two files holding one fact is what `harness
    header` exists to catch.

    Why beside the model at all: `train/bogoras-seg/*.lst` is the *next* run's input
    and is rewritten by every `--assemble`, so reading it to interpret an existing
    model meant scoring model A against model B's split whenever anything had been
    prepared in between — silently, with a confident train/eval breakdown that was
    simply wrong. A model carrying its own split cannot be mis-attributed.
    """
    out: dict[str, str] = {}
    for split in ("train", "eval"):
        p = model_split_path(model_path, split, root)
        if not p.exists():
            continue
        for name in _read_lst(p):
            try:
                out[norm_ref(Path(name).stem.replace("chukchi-", ""))] = split
            except ValueError:
                continue
    return out or None


def _frozen_splits(root: Path = Path(".")) -> dict[str, str] | None:
    """The split the training run actually consumed, from `bogoras-seg/*.lst`.

    **Not `load_splits`.** The live lists move — a page keyed after the run defaults
    into `train` — so asking them which pages the model trained on gives an answer
    that is wrong in exactly the direction that flatters the model. Returns None when
    the frozen lists are missing, and the caller refuses rather than substituting.
    """
    work = root / WORKDIR
    out: dict[str, str] = {}
    for split in ("train", "eval"):
        p = work / f"{split}.lst"
        if not p.exists():
            return None
        for name in _read_lst(p):
            try:
                out[norm_ref(Path(name).stem.replace("chukchi-", ""))] = split
            except ValueError:
                continue
    return out or None


def _y_overlap(a: dict, b: dict) -> int:
    return max(0, min(a["y1"], b["y1"]) - max(a["y0"], b["y0"]))


def predicted_zones(refs: list[str], root: Path = Path("."),
                    cfg: dict | None = None,
                    model_path: str | Path | None = None,
                    decode: str = "raw", device: str = "auto") -> dict[str, list]:
    """`{ref: [zone]}` — the predictions to score, from a store or from a model.

    One place, because there were three. `score`, `_recall_precision` and
    `_permutation_test` each used to read `mz/zones/` for themselves, which is three
    reads of the same file per page and three places to change; and every time a
    model needed checking *before* being installed, the same predict-and-compare
    was written out again by hand. It was written three times. This is the verb.

    With `model_path`, pages are segmented **in memory and nothing is written** —
    which is the point: a model can be measured before it is trusted, without
    overwriting the store or disturbing an editing session. Without it, the existing
    `mz/zones/` is read, which is what a bare `--score` means.
    """
    if model_path is None:
        return {r: read_zones(r, root, store=MZDIR) for r in refs}

    from PIL import Image
    from kraken import blla
    cfg = cfg or zc.load_config(root)
    net, _ = load_segmenter(model_path, root)
    if device == "auto":
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    out: dict[str, list] = {}
    for ref in refs:
        blot = blot_dir(root) / f"chukchi-{ref}.png"
        if not blot.exists():
            out[ref] = []
            continue
        with Image.open(blot) as s:
            page = s.convert("RGB")
        if decode == "dp":
            out[ref] = _dp_zones(ref, root, cfg, net, page)
            continue
        seg = blla.segment(page, model=net, device=device)
        out[ref] = [
            {"label": label,
             "x0": min(p[0] for p in g.boundary), "x1": max(p[0] for p in g.boundary),
             "y0": min(p[1] for p in g.boundary), "y1": max(p[1] for p in g.boundary)}
            for label, group in (seg.regions or {}).items() for g in group]
    return out


def score(root: Path = Path("."), cfg: dict | None = None,
          model_path: str | Path | None = None, decode: str = "raw",
          device: str = "auto") -> dict:
    """Compare `mz/zones/` against `gt/zones/` on every page that has both.

    Zones here are a vertical partition, so a prediction is matched to the ground
    truth it **overlaps most in y** — the honest pairing for bands, and the one that
    separates "found the right region and named it wrong" from "missed the region",
    which is the distinction the aggregate accuracy destroys.

    Two refusals, both about not manufacturing a number:

    - the split comes from the **frozen** `bogoras-seg/*.lst` the run consumed, and
      if those are gone this refuses rather than falling back to the live lists,
      which move as pages are keyed;
    - the result is reported **per split and never blended**. The model trained on
      the `train` pages, so agreement there is the editor's own judgement read back —
      the same hazard as `review`'s span diff comparing a proposal against the ground
      truth it produced, and it gets the same refusal rather than an average.

    `confusion` is the payload when something is systematically wrong: a model that
    finds the regions and misnames them consistently is a mapping fault, and looks
    nothing like a model that is merely weak.
    """
    # **The model's own split first.** A manifest cannot be mis-attributed; the
    # working directory's lists can, since `--assemble` rewrites them whenever the
    # next run is prepared. Falling back to them is still allowed — a checkpoint has
    # no manifest until it is installed, and scoring one is the whole point of
    # `--install` — but the report says which was used so the reader knows whether
    # the breakdown belongs to this model or to whatever was last laid out.
    frozen = model_splits(model_path, root) if model_path else None
    split_src = "manifest"
    if frozen is None:
        frozen = _frozen_splits(root)
        split_src = f"{WORKDIR}/*.lst"
    if frozen is None:
        raise FileNotFoundError(
            f"no split for this model: neither a manifest beside it nor "
            f"{WORKDIR}/train.lst. One of them has to say what the run trained on, "
            "or the score is blended with the training set and reads better than "
            "it is.")

    man = load_manifest(model_path, root) if model_path else None
    moved = bool(man and man.get("corpus_digest")
                 and man["corpus_digest"] != corpus_digest(root))

    gt_refs = set(zone_refs(root, ZONEDIR))
    mz_refs = set(zone_refs(root, MZDIR))
    # **An exempt page is not scored.** A human has ruled it not a text page, so it
    # has no correct segmentation and the model cannot be right or wrong about it —
    # every region it draws there counts as spurious and nothing can offset them.
    # `assemble` keeps these out of training and eval for the same reason: a plate
    # is neither an example of the layout nor a fair test of it.
    #
    # This was not hypothetical. Seven plates keyed exempt mid-session put 240
    # predictions against zero ground truth into the `unseen` row and took its
    # precision from 79% to 53%, which reads as the model degrading on new pages
    # when what changed was the denominator.
    splits_now = load_splits(root)
    # With a model given there is no store to intersect with: every keyed page is a
    # page it can be asked about, which is the point of measuring before installing.
    candidates = gt_refs if model_path is not None else (gt_refs & mz_refs)
    skipped_exempt = sorted(r for r in candidates
                            if splits_now.get(r) == "exempt")
    both = sorted(candidates - set(skipped_exempt), key=parse_ref)

    cfg = cfg or zc.load_config(root)
    preds = predicted_zones(both, root, cfg, model_path, decode, device)

    buckets = {"trained-on": [], "eval": [], "unseen": []}
    confusion: dict[tuple[str, str], int] = {}
    for ref in both:
        bucket = {"train": "trained-on", "eval": "eval"}.get(frozen.get(ref), "unseen")
        truth = read_zones(ref, root, store=ZONEDIR)
        pred = preds[ref]
        for t in truth:
            best, best_ov = None, 0
            for p in pred:
                ov = _y_overlap(t, p)
                if ov > best_ov:
                    best, best_ov = p, ov
            got = best["label"] if best is not None else ""
            confusion[(t["label"], got)] = confusion.get((t["label"], got), 0) + 1
            buckets[bucket].append(t["label"] == got)

    # Two rows per split: what the model emitted, and what survives the store's own
    # minimum height. The second is not a kinder scoring — `min_zone_h_px` is the
    # rule that a zone shorter than a mis-click cannot be a zone, `validate_page`
    # already errors on one, and over half the raw output falls under it. Reporting
    # only the filtered figure would flatter the model; reporting only the raw one
    # would describe output nobody would ever be shown.
    min_h = int(cfg["min_zone_h_px"])
    rows = []
    for k, v in buckets.items():
        refs_k = [r for r in both
                  if {"train": "trained-on", "eval": "eval"}.get(
                      frozen.get(r), "unseen") == k]
        for tag, floor in (("as emitted", 0), (f">={min_h}px", min_h)):
            rows.append({
                "split": k, "counting": tag,
                "pages": len(refs_k),
                **_recall_precision(refs_k, root, floor, preds)})

    conf = [{"truth": t, "predicted": p or "(unmatched)", "n": n}
            for (t, p), n in sorted(confusion.items(), key=lambda kv: -kv[1])]
    return {"pages_compared": len(both),
            # Counted and named, never a silent drop: a scored set that shrank
            # without saying so would look like pages that were never predicted.
            "exempt_skipped": " ".join(skipped_exempt),
            "note": ("matched by greatest y-overlap; never blended across splits — "
                     "the model trained on the `trained-on` rows, so agreement "
                     "there is this editor's own judgement read back. Pages ruled "
                     "exempt are excluded: a plate has no correct segmentation, so "
                     "every region drawn on one is spurious and nothing can offset it"),
            "model": str(model_path) if model_path else "mz/zones/",
            "decoder": decode if model_path else "(as stored)",
            "split_from": split_src,
            # A verdict about a corpus that has since moved is the same class of
            # thing as a stale ink verdict drawn in a live column: it reads as
            # current and is not. Reported, never silently corrected.
            "corpus_moved_since_training": moved,
            "splits": rows, "confusion": conf,
            "permutation": _permutation_test(both, frozen, root, preds)}


def _recall_precision(refs: list[str], root: Path = Path("."),
                      floor: int = 0, preds: dict | None = None) -> dict:
    """Both directions, because `label_agreement` only looks one way.

    That figure walks the **human's** zones and asks whether the best-overlapping
    prediction is named right. A model that emitted every correct band and fifty
    spurious slivers beside them would score identically — the extra output is
    invisible to it, and the first model did exactly that, putting 13 regions on a
    page the editor gave 6. So:

    - `recall` — human zones with a correctly-labelled prediction over them;
    - `precision` — predicted zones whose best human match agrees. This is what
      falls when the model over-segments, and it is the number to read next to a
      flattering recall;
    - `missed` / `spurious` — the two failures in counts rather than percentages,
      since on a 6-zone page a percentage hides how few things are being divided;
    - `edge_px` — the median of |Δtop| and |Δbottom| over correctly-labelled pairs.
      Median, not mean: one region spanning half the page would otherwise dominate
      a statistic meant to describe ordinary agreement.

    Nothing here is thresholded into a pass. A zone is "matched" if any prediction
    overlaps it at all, which is generous by design — being generous about matching
    and strict about the label is what keeps this measuring *naming* rather than
    silently measuring geometry twice.
    """
    gt_n = pred_n = hit = pred_hit = 0
    missed = spurious = 0
    edges: list[int] = []
    for ref in refs:
        truth = read_zones(ref, root, store=ZONEDIR)
        src = preds[ref] if preds is not None else read_zones(ref, root, store=MZDIR)
        pred = [p for p in src if p["y1"] - p["y0"] >= floor]
        gt_n += len(truth)
        pred_n += len(pred)
        for t in truth:
            best, ov = None, 0
            for p in pred:
                o = _y_overlap(t, p)
                if o > ov:
                    best, ov = p, o
            if best is None:
                missed += 1
            elif best["label"] == t["label"]:
                hit += 1
                edges.append(abs(best["y0"] - t["y0"]))
                edges.append(abs(best["y1"] - t["y1"]))
        for p in pred:
            best, ov = None, 0
            for t in truth:
                o = _y_overlap(t, p)
                if o > ov:
                    best, ov = t, o
            if best is None:
                spurious += 1
            elif best["label"] == p["label"]:
                pred_hit += 1
    med = sorted(edges)[len(edges) // 2] if edges else None
    return {"gt_zones": gt_n, "pred_zones": pred_n,
            "recall": round(100 * hit / gt_n, 1) if gt_n else 0.0,
            "precision": round(100 * pred_hit / pred_n, 1) if pred_n else 0.0,
            "missed": missed, "spurious": spurious,
            "edge_px": med}


def _permutation_test(refs: list[str], frozen: dict[str, str],
                      root: Path = Path("."), preds: dict | None = None) -> dict:
    """Is the disagreement a **consistent relabelling** or a weak model?

    The two look nothing alike and the answer decides what to do next: a permutation
    means the geometry was learned and only the name attached to each output channel
    is wrong — recoverable without retraining — where diffuse error means the model
    itself is no good.

    Derived on the **training** pages and tested on the **held-out** ones, which is
    the only thing that makes it evidence rather than a curve fitted to noise. A
    permutation read off a set and then scored on the same set would agree with
    itself by construction; agreeing on pages it was not derived from is a claim
    about the model. `holds_out` is that number and it is the one to read.

    Reports `bijective` separately, because a mapping that sends two truth labels to
    one predicted label is not a relabelling at all — it is two classes the model
    cannot tell apart, and calling that a permutation would be the fluent-nonsense
    move this whole apparatus exists to prevent.
    """
    votes: dict[str, dict[str, int]] = {}
    held: list[tuple[str, str]] = []
    for ref in refs:
        split = frozen.get(ref)
        truth = read_zones(ref, root, store=ZONEDIR)
        pred = preds[ref] if preds is not None else read_zones(ref, root, store=MZDIR)
        for t in truth:
            best, best_ov = None, 0
            for p in pred:
                ov = _y_overlap(t, p)
                if ov > best_ov:
                    best, best_ov = p, ov
            if best is None:
                continue
            if split == "train":
                votes.setdefault(t["label"], {})
                votes[t["label"]][best["label"]] = \
                    votes[t["label"]].get(best["label"], 0) + 1
            elif split == "eval":
                held.append((t["label"], best["label"]))

    # truth -> the label the model most often emits for it, learned on train only.
    perm = {t: max(c.items(), key=lambda kv: kv[1])[0] for t, c in votes.items()}
    targets = list(perm.values())
    bijective = len(set(targets)) == len(targets)

    agree = sum(1 for t, p in held if perm.get(t) == p)
    return {
        "derived_on": "trained-on pages only",
        "bijective": bijective,
        # The identity is a bijection that holds out perfectly on a *correct* model,
        # so `bijective` alone cannot mean "the labels are shuffled". This is the
        # field that separates the two, and without it the fixed model reports its
        # own correctness as the fault it just had.
        "is_identity": all(t == p for t, p in perm.items()),
        "holds_out": (round(100 * agree / len(held), 1) if held else 0.0),
        "held_out_zones": len(held),
        "map": " ".join(f"{t}->{p}" for t, p in sorted(perm.items())),
    }


def install_model(checkpoint: str | Path, root: Path = Path("."),
                  name: str = "zones-seg", cfg: dict | None = None,
                  commit: bool = False, device: str = "auto") -> dict:
    """Score a checkpoint, refuse it if its class map is permuted, and install it.

    Installing is a verb rather than a `cp` because everything that makes a
    checkpoint trustworthy is a *precondition of it being installed*, and every one
    of those checks was previously something to remember:

    1. score it in memory against `gt/zones/`, writing nothing;
    2. **refuse a permuted class map.** `--resize` renumbers the output layer and
       Python randomises string hashing per process, so a run can silently emit a
       model whose stored names do not match what its channels learned. The first
       one did: 0.2% agreement on its own training data. `--remap-model` repairs it,
       but a permuted model must never reach `models/` unnoticed;
    3. write the manifest, which is what makes the model self-describing;
    4. only then copy.

    Paths in the manifest are **relative to the repo root**, never absolute — it is
    committed, and a record of one machine's filesystem is no record at all.
    """
    import shutil
    cfg = cfg or zc.load_config(root)
    src = Path(checkpoint)
    if not src.is_absolute():
        src = root / src
    if not src.exists():
        raise FileNotFoundError(f"no checkpoint at {checkpoint}")

    rep = score(root, cfg, model_path=checkpoint, device=device)
    perm = rep["permutation"]
    if perm["bijective"] and not perm["is_identity"] and perm["holds_out"] >= 90:
        raise ValueError(
            "refusing to install: the class map is permuted — a 1-1 relabelling "
            f"derived on the training pages predicts {perm['holds_out']}% of "
            "held-out zones, which means the geometry was learned and the names on "
            "the output channels are wrong. Run `--remap-model --commit` against "
            "this checkpoint first. See CLAUDE.md, '--resize shuffled the class "
            "names'.")

    dest_dir = root / MODELDIR
    rel = f"{MODELDIR}/{name}.safetensors"
    dest = root / rel
    kept = {f"{r['split']}/{r['counting']}":
            {"pages": r["pages"], "recall": r["recall"],
             "precision": r["precision"]}
            for r in rep["splits"] if r["pages"]}

    # The split is copied, not re-encoded — see `model_splits`.
    lists = {s: root / WORKDIR / f"{s}.lst" for s in ("train", "eval")}
    missing = [s for s, p in lists.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"no {', '.join(missing)}.lst in {WORKDIR} — the split this checkpoint "
            "trained on has to be copied beside it, or nothing can tell later which "
            "pages it saw. Run `--assemble` before training, and install before "
            "assembling again.")

    man = {
        "name": name,
        "model": rel,                       # relative, always: this file is tracked
        "installed_from": Path(checkpoint).as_posix(),
        "sha256": _model_sha256(src),
        "train_merges": zc.train_merges(cfg),
        "corpus_digest": corpus_digest(root),
        "kraken": _kraken_version(),
        "score": kept,
    }
    counts = {s: len(_read_lst(p)) for s, p in lists.items()}
    out = {"model": rel,
           "train_pages": counts["train"], "eval_pages": counts["eval"],
           "score": " ".join(f"{k} r{v['recall']}/p{v['precision']}"
                             for k, v in kept.items()),
           "corpus_digest": man["corpus_digest"],
           "committed": commit}
    if not commit:
        out["note"] = "preview only — pass --commit to install"
        return out

    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    for s, p in lists.items():
        shutil.copy(p, model_split_path(rel, s, root))
    manifest_path(rel, root).write_text(
        json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out["wrote"] = (f"{rel}, {name}.json, {name}.train.lst, {name}.eval.lst")
    return out


def _kraken_version() -> str:
    try:
        from importlib.metadata import version
        return version("kraken")
    except Exception:
        return "unknown"


MIN_HOLDOUT = 80.0


def remap_model(root: Path = Path("."), model_path: str | Path = DEFAULT_MODEL,
                commit: bool = False, cfg: dict | None = None) -> dict:
    """Put the learned names back on the model's output channels.

    `ketos segtrain` under `--resize new` stored a `class_mapping` that does not
    match what the network's channels actually learned: the corpus scored **0.2% on
    its own training data**, which is far below the ~14% that guessing among seven
    classes would give, and no amount of undertraining does that. What it is instead
    is a **permutation** — the geometry was learned and the names are shuffled — and
    `score` measures it: a 1-1 map derived on the training pages predicted 93.9% of
    held-out zones it was never fitted to.

    So the repair is a rename, not a retrain, and it is preferred over one for a
    reason worth writing down: both `--resize` branches assign new class indices by
    iterating a **set difference** (`kraken/train/blla.py:531` and `:574`), and
    Python randomises string hashing per process, so the order varies run to run.
    Retraining is therefore a lottery — it might come out clean, differently
    permuted, or the same — where this is deterministic and checkable.

    **The direction is the part to get right.** `score`'s map reads truth → what the
    model calls it. A region truly of class `T` therefore surfaces on the channel
    currently named `perm[T]`, so that channel *means* `T`, and the corrected mapping
    is `new[T] = old[perm[T]]`.

    Refuses unless the permutation is bijective, holds out above `MIN_HOLDOUT`, and
    covers every class the model declares. A map that sent two truth labels to one
    predicted label would not be a relabelling at all — it would be two classes the
    model cannot separate — and renaming on that basis would bury a real defect
    inside a file nobody can audit. `--commit` is required to write, and the original
    is kept beside it as `.bak`, as kraken's own `contrib/set_seg_options.py` does.
    """
    from kraken.models.loaders import load_models
    from kraken.models.writers import write_safetensors

    rep = score(root, cfg)
    perm_rep = rep["permutation"]
    perm = dict(p.split("->") for p in perm_rep["map"].split() if "->" in p)

    # The evidence is checked **before the model is opened**, so that thin evidence
    # refuses for the reason it is thin rather than for whatever the filesystem
    # happens to say first. A refusal that names the wrong cause is a refusal
    # somebody will work around.
    problems = []
    if perm_rep["is_identity"]:
        problems.append("the map is the identity — the model's labels already agree "
                        "with the ground truth, so there is nothing to rename")
    if not perm_rep["bijective"]:
        problems.append("the map is not 1-1 — two classes the model cannot separate "
                        "is not a relabelling")
    if perm_rep["holds_out"] < MIN_HOLDOUT:
        problems.append(f"it predicts only {perm_rep['holds_out']}% of held-out "
                        f"zones, under the {MIN_HOLDOUT}% this requires")
    if problems:
        raise ValueError("refusing to rewrite the class mapping: "
                         + "; ".join(problems))

    p = Path(model_path)
    if not p.is_absolute():
        p = root / p
    models = load_models(p)
    old = dict(models[0].user_metadata["class_mapping"]["regions"])

    missing = sorted(set(old) - set(perm))
    if missing:
        raise ValueError(
            "refusing to rewrite the class mapping: no evidence for "
            + ", ".join(missing) + " — absent from the ground truth compared, so "
            "nothing says what those channels learned")

    new = {t: old[perm[t]] for t in perm}
    if sorted(new.values()) != sorted(old.values()):
        raise ValueError("the rewritten mapping does not cover the same channels — "
                         "refusing rather than writing a model that indexes a "
                         "heatmap it does not have")

    changed = [{"channel": c,
                "was": next(k for k, v in old.items() if v == c),
                "now": next(k for k, v in new.items() if v == c)}
               for c in sorted(old.values())]
    out = {"model": str(p), "holds_out": perm_rep["holds_out"],
           "channels": changed, "committed": commit}
    if not commit:
        out["note"] = "preview only — pass --commit to write"
        return out

    import shutil
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists():
        shutil.copy(p, bak)
    models[0].user_metadata["class_mapping"]["regions"] = new
    p.unlink()
    write_safetensors(models, p)
    out["backup"] = str(bak)
    out["sha256"] = _model_sha256(p)
    return out


# ------------------------------------------------------------------- the view

def link_view(root: Path = Path(".")) -> dict:
    """Rebuild `zones/`: one name per page, the human file winning wherever it exists.

    The same shape as `ocr/` over `gt/ocr/`, and the same rule — **reads may resolve
    through the view, writes never do.** What the view buys is that a consumer asks
    for a page's segmentation without asking who produced it, while the answer to
    "who produced it" stays readable from where the link points.

    Links are relative, so the farm survives a clone or a move; a link whose target
    has gone is removed and counted rather than left to dangle, since a dangling
    entry here would read as a missing page rather than as a stale link.

    The `from_gt`/`from_mz` split is the number worth reading: it is how much of the
    corpus is still only the machine's word.
    """
    import os
    view = root / VIEWDIR
    view.mkdir(parents=True, exist_ok=True)

    gt = set(zone_refs(root, ZONEDIR))
    mz = set(zone_refs(root, MZDIR))
    wanted = {}
    for ref in sorted(gt | mz, key=parse_ref):
        store = ZONEDIR if ref in gt else MZDIR
        wanted[f"chukchi-{ref}.xml"] = alto_for(ref, root, store)

    removed = 0
    for p in view.glob("chukchi-*.xml"):
        if p.name not in wanted:
            p.unlink()
            removed += 1

    for name, target in wanted.items():
        link = view / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(os.path.relpath(target.resolve(), view.resolve()))

    return {"dir": str(view), "from_gt": len(gt), "from_mz": len(mz - gt),
            "removed": removed}


# --------------------------------------------------------- segtrain assembly

# Pure scratch. Nothing reads it once training has finished — the split a model
# trained on travels in that model's own manifest, not in a file here — so
# `--assemble` may clobber it freely and there is no "back up the lists first" step
# to remember. It used to be both the training input *and* the only record of what a
# past run consumed, which meant preparing a new run destroyed the ability to
# interpret the model you already had.
WORKDIR = "train/bogoras-seg"


def _write_merged(src: Path, dest: Path, merges: dict[str, str]) -> bool:
    """Copy a zone ALTO into the training set with `train_merges` applied.

    Rewrites `OtherTag/@LABEL` only — the geometry, the ids and the `TAGREFS` are
    untouched, so what the segmenter sees is this page exactly as keyed but with two
    classes answering to one name. Two tags that collide after folding are left as
    two tags carrying the same label, which is what kraken's own merged-class support
    expects (`BaselineSet.merged_classes`: several strings, one index).

    Returns whether anything was folded, so `assemble` can report the count rather
    than leave the training set quietly different from the store.
    """
    tree = etree.parse(str(src))
    hit = False
    for tag in tree.iter(f"{{{ALTO_NS}}}OtherTag"):
        label = tag.get("LABEL")
        if label in merges:
            tag.set("LABEL", merges[label])
            hit = True
    tree.write(str(dest), xml_declaration=True, encoding="UTF-8")
    return hit


def assemble(root: Path = Path("."), scratch: bool = False) -> dict:
    """Lay out `bogoras-seg/` for `ketos segtrain`, and report the invocation.

    ketos resolves a page's image through the ALTO's own
    `sourceImageInformation/fileName`, relative to the XML — so the zone file and
    its **blotted** raster have to sit in one directory under the name the ALTO
    already carries. Both are symlinked; nothing is copied.

    **Refuses a page whose blot is missing** rather than falling back to the plain
    scan. Silently training half the set on unblotted pages would teach exactly the
    figure-shaped body zone the blot exists to prevent, and the resulting model
    would look fine everywhere except the 252 pages that matter.

    The `ketos segtrain` command line is *reported, not run*, and the reported form
    is **verified against `ketos --help` in this environment** (kraken 7.0.3) rather
    than remembered. Four things about it are not what a 4.x-era tutorial or an
    earlier draft of this function would give you:

    - **`-s` means two different things at the two levels** — the seed on the group,
      the VGSL spec on `segtrain`. `ketos segtrain -s 42` would be read as a network
      architecture. The seed is worth setting: without it the run is not repeatable,
      and `-r/--deterministic` seeds 42 by itself if none is given.
    - **Anything about a particular machine is left off deliberately.** `-d/--device`
      and `--workers` are also group-level options and also go before the subcommand,
      but they describe whoever is running rather than what this corpus needs, so
      they are the operator's to add. The defaults (`auto`, one worker) run anywhere.
    - **`--suppress-regions` / `--suppress-baselines` are gone.** Region-only is not
      a flag any more; it follows from the data, and `gt/zones/` carries no
      `TextLine` at all, so there is nothing for a baseline head to learn.
    - **`-i models/blla.mlmodel --resize new`** rather than training from scratch.
      blla is the stock layout model and `new` sets the output layer to exactly the
      training data's classes — dropping blla's single `text` region class and its
      `default` baseline for these seven regions, keeping the features underneath.
      115 pages is not enough to learn a convolutional stack from nothing, and
      `models/plates-seg-best.safetensors` is the same size as blla, so the one
      segmentation model this project has already trained was made the same way.
    - **`--resize`'s own `--help` lists two values the code rejects.** It advertises
      `add|union|both|new|fail`; `kraken/train/blla.py` implements `fail`, `union`
      and `new`, and anything else falls into an `else` whose `ValueError` crashes
      on a wrong attribute — so `--resize both` fails with an unreadable
      `AttributeError: 'BLLASegmentationModel' object has no attribute 'resize'`
      after the data has loaded. `both` is also exactly what the help *describes*
      as fitting the layer to the training classes, which is what `new` does. This
      is the concrete case for the rule above the whole file: verify against the
      source, not the help, and never against a tutorial.

    Output goes to `bogoras-seg/`, not `models/`: segtrain writes a checkpoint per
    epoch, and this repo keeps only the trained model, in `models/`, by hand.
    """
    import os
    splits = load_splits(root)
    # A corpus with no config declares no folds. Tolerated rather than fatal because
    # assembly is otherwise entirely a question about `gt/zones/` and the blots —
    # and it is not silent: `merged` in the report is what was folded, so an empty
    # value is a statement rather than an absence.
    try:
        merges = zc.train_merges(zc.load_config(root))
    except (FileNotFoundError, ValueError):
        merges = {}
    work = root / WORKDIR
    work.mkdir(parents=True, exist_ok=True)
    counts = {"train": 0, "eval": 0}
    missing: list[str] = []
    listed: dict[str, list[str]] = {"train": [], "eval": []}
    merged_pages = 0

    exempted = 0
    for ref in zone_refs(root):
        split = splits.get(ref, DEFAULT_SPLIT)
        # A plate is neither an example of the layout nor a fair test of it, so it
        # goes into neither list. Counted, not silently dropped — a set that
        # shrank without saying so would look like pages that were never keyed.
        if split == "exempt":
            exempted += 1
            continue
        alto = alto_for(ref, root)
        blot = blot_dir(root) / f"chukchi-{ref}.png"
        if not blot.exists():
            missing.append(ref)
            continue
        # The raster is always a link — it is identical to what is in the store.
        # The ALTO is a link only when nothing is folded: with `train_merges`
        # declared it has to be a **copy**, since the training set must differ from
        # `gt/zones/` in exactly one respect and the store must not learn of it.
        # Writing through a symlink here would edit the ground truth, which is the
        # failure this repo has already paid for once.
        for target, name in ((alto, f"chukchi-{ref}.xml"),
                             (blot, f"chukchi-{ref}.png")):
            link = work / name
            if link.is_symlink() or link.exists():
                link.unlink()
            if merges and target is alto:
                merged_pages += _write_merged(target, link, merges)
            else:
                link.symlink_to(os.path.relpath(target.resolve(), work.resolve()))
        # The work-dir path, **unresolved and relative to the root** — and both
        # halves of that are load-bearing.
        #
        # `.resolve()` here followed the symlink straight back to `gt/zones/`, so
        # the lists named the real ALTO, kraken looked for the raster beside *it*,
        # and the blot links this function exists to make were never read. It failed
        # loudly ("All 115 samples in dataset invalid") only because `gt/zones/`
        # holds no PNGs; had a scan ever been copied in there, the whole set would
        # have trained unblotted and looked fine.
        #
        # Relative because an absolute path records this machine. The lists sit in a
        # gitignored directory so nothing was committed, but the reported command
        # already assumes the repo root as cwd, and a path that only works on one
        # filesystem is not something to leave lying around on the strength of a
        # `.gitignore` line.
        listed[split].append(f"{WORKDIR}/chukchi-{ref}.xml")
        counts[split] += 1

    for split in ("train", "eval"):
        (work / f"{split}.lst").write_text(
            "".join(p + "\n" for p in sorted(listed[split])), encoding="utf-8")

    classes = sorted({merges.get(z["label"], z["label"])
                      for ref in zone_refs(root)
                      if splits.get(ref, DEFAULT_SPLIT) != "exempt"
                      for z in read_zones(ref, root)})
    _dev, _wrk = _runtime_flags()
    if scratch:
        # No `-i`, so `ketos segtrain` builds the network from its default VGSL spec
        # with random weights. Verified against `ketos segtrain --help` for kraken
        # 7.0.3: `-i/--load` is optional and `-s/--spec` carries the default.
        #
        # This is the one configuration in which the permutation cannot arise even
        # in principle. `--resize` is what renumbers an existing output layer, and
        # there is no existing output layer — the class map is built once, from this
        # data, by the run that uses it. `--score` afterwards is still the rule, but
        # here it is confirmation rather than the only line of defence.
        base, resize, why = "", "", (
            "from scratch: no base model, kraken's default segmentation spec, "
            "random init. Nothing is renumbered because nothing is being reused")
    else:
        base, resize, why = _base_and_resize(root, classes)
    return {"dir": str(work),
            "train": counts["train"], "eval": counts["eval"],
            "exempt_skipped": exempted,
            "missing_blot": " ".join(missing),
            "merged": " ".join(f"{k}->{v}" for k, v in sorted(merges.items())),
            "merged_pages": merged_pages,
            "classes": " ".join(classes),
            "base": base or "(none — from scratch)",
            "resize": resize or "(none needed)",
            "resize_why": why,
            "note": ("region-only — gt/zones/ carries no TextLine, so there is no "
                     "baseline head to train. Flags verified against `ketos --help` "
                     "for kraken 7.0.3: -s is group-level here and means --spec on "
                     "segtrain, and -d/--workers are group-level too. Those two are "
                     "read off this machine so the command runs as printed — it "
                     "once did not, and trained on one worker. Re-verify after any "
                     "kraken upgrade."),
            "command": SEGTRAIN_CMD.format(
                work=WORKDIR, out=f"{WORKDIR}/{_next_run(root)}",
                device=_dev, workers=_wrk,
                load=("" if not base else
                      f" -i {base}" + (f" --resize {resize}" if resize else "")))}


def _base_and_resize(root: Path, classes: list[str]) -> tuple[str, str, str]:
    """What to fine-tune from, and whether `--resize` is needed at all.

    **Omitting `--resize` when the class sets already match is the single change
    that removes the permutation lottery.** Both branches assign new class indices
    by iterating a `set` difference, and Python randomises string hashing per
    process, so any run that renumbers may emit a model whose stored names do not
    match what its channels learned. A run that renumbers *nothing* cannot.

    Prefers this project's own installed model over stock blla, since after the
    first run there is always something better to start from — and reads its class
    set from its manifest rather than opening the weights.
    """
    installed = root / DEFAULT_MODEL
    if installed.exists():
        # Read from the weights, not from a manifest field. The class map is
        # already in the model; recording it beside would be a second copy of one
        # fact, and this one can silently disagree with what the network does — as
        # it did for the whole of run 1.
        try:
            net, _ = load_segmenter(DEFAULT_MODEL, root)
            have = set(net.user_metadata["class_mapping"]["regions"])
        except Exception:
            return ("models/blla.mlmodel", "new",
                    "an installed model is present but unreadable; falling back to "
                    "stock blla")
        if have == set(classes):
            return (DEFAULT_MODEL, "",
                    "the installed model already has exactly these classes, so "
                    "nothing is renumbered and the permutation lottery is off")
        return (DEFAULT_MODEL, "new",
                "the installed model's classes differ ("
                + ", ".join(sorted(have ^ set(classes)))
                + ") so the output layer is refitted — run `--score` afterwards, "
                  "since renumbering can permute the class map")
    return ("models/blla.mlmodel", "new",
            "no installed model yet; blla is the stock layout net and its single "
            "`text` region class is replaced by these")


def _next_run(root: Path) -> str:
    """A fresh output directory per run. Three runs writing `best_*.safetensors`
    into one directory left them distinguishable only by an accuracy in the
    filename, which is not an identity."""
    n = 1
    while (root / WORKDIR / f"run-{n}").exists():
        n += 1
    return f"run-{n}"


# The invocation `--assemble` reports. A template rather than a string built at the
# call site, so the one place it is written down is the one place it is read — and
# so a `harness` change and a flag change are the same edit. Paths are relative to
# the repo root, which is the cwd the command assumes.
SEGTRAIN_CMD = (
    "uv run ketos -s 42 -d {device} --workers {workers} segtrain"
    " -f alto{load}"
    " -t {work}/train.lst -e {work}/eval.lst"
    " -o {out} --augment -q early -N 200 --min-epochs 15 --lag 15"
)


# Cached because `torch.cuda.is_available()` initializes CUDA and costs ~1 s, and
# the answer cannot change inside one process: a GPU does not appear mid-run. The
# suite called this once per `assemble` test and paid for it every time.
@lru_cache(maxsize=1)
def _runtime_flags() -> tuple[str, int]:
    """The device and worker count for the reported command, read off this machine.

    These used to be omitted on the grounds that the command should carry nothing
    machine-specific — and the note told the reader to add them by hand. That is a
    command which does not work until edited, and it duly got run with kraken's
    default **single** data-loading worker, which on this corpus is the difference
    between an evening and a week. A reported command is for running; if it needs a
    machine's details then it needs them derived, not deferred to whoever reads it.

    Derived rather than pinned for the same reason the column measure is: the two
    facts live in the machine, and a number written down here is wrong on the next
    one. Falls back to CPU only when torch says there is no GPU.
    """
    device = "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda:0"
    except Exception:
        pass
    # Leave the main process and one core to spare; kraken's loader saturates the
    # rest. `cpu_count` can return None on exotic platforms.
    return device, max(1, (os.cpu_count() or 4) - 2)
