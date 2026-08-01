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
import json
import time
from pathlib import Path

from lxml import etree

from .context import norm_ref, parse_ref
from .figures import read_blocks
from . import zones_config as zc

ZONEDIR = "gt/zones"
SCANS = "scans"

# Provenance travelling with the data, as with `lines.GAP_ID_PREFIX`. A block whose
# id starts with this was drawn in this tool against a configured column; one whose
# id does not came from somewhere else and its width means something different.
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


def zone_dir(root: Path = Path(".")) -> Path:
    return root / ZONEDIR


def alto_for(ref: str, root: Path = Path(".")) -> Path:
    return zone_dir(root) / f"chukchi-{norm_ref(ref)}.xml"


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


def zone_refs(root: Path = Path(".")) -> list[str]:
    """Every ref with a zone file, in (part, scan index) order."""
    out = []
    for p in zone_dir(root).glob("chukchi-*.xml"):
        try:
            out.append(norm_ref(p.stem.replace("chukchi-", "")))
        except ValueError:
            continue
    return sorted(set(out), key=parse_ref)


def read_zones(ref: str, root: Path = Path("."),
               with_points: bool = False) -> list[dict]:
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
    for b in read_blocks(alto_for(ref, root), with_points=with_points):
        rec = {"id": b["id"], "label": b["label"],
               "x0": b["hpos"], "y0": b["vpos"],
               "x1": b["hpos"] + b["width"], "y1": b["vpos"] + b["height"]}
        if with_points:
            rec["points"] = b["points"]
        out.append(rec)
    return sorted(out, key=lambda z: (z["y0"], z["x0"]))


def has_zones(ref: str, root: Path = Path(".")) -> bool:
    """Whether this page has been keyed at all — file present, zones or not.

    The distinction is the point. A plate carries no text column, so its correct
    segmentation is zero zones; an empty file is that record. A page nobody has
    opened is also zero zones. Only the file's existence separates "looked at,
    holds nothing" from "not looked at", which is why navigation never writes one.
    """
    return alto_for(ref, root).exists()


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

def build_alto(ref: str, zones: list[dict], size: tuple[int, int]) -> etree._ElementTree:
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
            "ID": f"{ID_PREFIX}{ref}_{i:03d}", "TAGREFS": tag_id[z["label"]]})
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
    """
    ref = norm_ref(ref)
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
                  ink: bool = True) -> dict:
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
    """
    cfg = cfg or zc.load_config(root)
    ref = norm_ref(ref)
    zones = read_zones(ref, root, with_points=True)
    labels = set(zc.types_by_label(cfg))
    tol = cfg["width_tolerance_px"]
    min_h = cfg["min_zone_h_px"]
    max_ov = cfg["max_overlap_px"]

    errors: list[dict] = []

    def err(rule: str, detail: str):
        errors.append({"rule": rule, "detail": detail})

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
        return {"ref": ref, "keyed": has_zones(ref, root), "zones": len(zones),
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

    return {"ref": ref, "keyed": has_zones(ref, root), "zones": len(zones),
            "split": split, "ink_checked": bool(ink and zones),
            "errors": errors, "warnings": warnings, "uncovered": bands}


def validate_corpus(root: Path = Path("."), cfg: dict | None = None,
                    ink: bool = False,
                    refs: list[str] | None = None) -> tuple[dict, list[dict]]:
    """Every keyed page, one flat record each, plus a summary.

    Two returns rather than one nested object because TOON collapses a uniform
    record list to a header and rows and degrades to the verbose form the moment
    the keys go ragged — so the summary and the table are emitted separately, as
    `cli` already does for `lines`.

    List-valued fields are joined into strings here for the same reason. The counts
    are what a sweep is for; `harness zones PP-NNN` is where a page's own findings
    are read in full.

    `refs` scopes it to a work-list. A page on the list that has not been keyed is
    **reported as a row with no zones**, not omitted: "still to do" is the answer an
    itinerary is being asked for, and a sweep that silently listed only finished
    pages would report a half-done selection as complete.
    """
    cfg = cfg or zc.load_config(root)
    splits = load_splits(root)
    rows, n_err, n_warn = [], 0, 0
    seen: dict[str, int] = {}
    for s in SPLITS:
        for name in _read_lst(_lst_path(root, s)):
            seen[name] = seen.get(name, 0) + 1
    dup = sorted(n for n, c in seen.items() if c > 1)
    for ref in (refs if refs is not None else zone_refs(root)):
        r = validate_page(ref, root, cfg, ink=ink)
        if ink:
            # A sweep that read 122 rasters and kept nothing would make the page
            # list ask for the same work again.
            record_ink(ref, r, root)
        n_err += len(r["errors"])
        n_warn += len(r["warnings"])
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
    chosen for `scans-w-figs/` and for `review/*/page.png` — and it dangles loudly,
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


# --------------------------------------------------------- segtrain assembly

WORKDIR = "bogoras-seg"


def assemble(root: Path = Path(".")) -> dict:
    """Lay out `bogoras-seg/` for `ketos segtrain`, and report the invocation.

    ketos resolves a page's image through the ALTO's own
    `sourceImageInformation/fileName`, relative to the XML — so the zone file and
    its **blotted** raster have to sit in one directory under the name the ALTO
    already carries. Both are symlinked; nothing is copied.

    **Refuses a page whose blot is missing** rather than falling back to the plain
    scan. Silently training half the set on unblotted pages would teach exactly the
    figure-shaped body zone the blot exists to prevent, and the resulting model
    would look fine everywhere except the 252 pages that matter.

    The `ketos segtrain` command line is *reported, not run*. Its flags moved across
    the 3→5→6→7 majors and this repo's own rule is to verify them against
    `ketos --help` at the moment of use rather than trust anything written down —
    including this docstring.
    """
    import os
    splits = load_splits(root)
    work = root / WORKDIR
    work.mkdir(parents=True, exist_ok=True)
    counts = {"train": 0, "eval": 0}
    missing: list[str] = []
    listed: dict[str, list[str]] = {"train": [], "eval": []}

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
        for target, name in ((alto, f"chukchi-{ref}.xml"),
                             (blot, f"chukchi-{ref}.png")):
            link = work / name
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(os.path.relpath(target.resolve(), work.resolve()))
        listed[split].append(str((work / f"chukchi-{ref}.xml").resolve()))
        counts[split] += 1

    for split in ("train", "eval"):
        (work / f"{split}.lst").write_text(
            "".join(p + "\n" for p in sorted(listed[split])), encoding="utf-8")

    return {"dir": str(work),
            "train": counts["train"], "eval": counts["eval"],
            "exempt_skipped": exempted,
            "missing_blot": " ".join(missing),
            "note": ("region-only, as models/plates-seg-best.safetensors was — no "
                     "baseline head. Verify every flag against `ketos --help` "
                     "before running; the CLI was reorganized across majors 3-7."),
            "command": (f"ketos segtrain -f alto -t {work}/train.lst "
                        f"-e {work}/eval.lst -o {root}/models/zones-seg --device cuda:0")}
