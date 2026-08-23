"""`gt/zones/`: the seven-type page segmentation, its store and its checks.

A zone here is a **fixed-width band of the text column** — two clicks give its top
and bottom, and its left and right edges come from `data/zones_config.json`, never
from the pointer. That is not a shortcut, it is the modelling claim: the book sets
one measure, ~1794 px across all three parts (see the config's `_provenance`), so a
page's zones form a vertical partition of a column whose width was decided by the
printer. Letting the editor drag an x-edge would offer a freedom the page does not
have, and every hand-drawn width would then be a small lie the trainer learns.

**The claim is about zones, and `gt/fig/` is where it stops.** A figure is a freely
placed rectangle whose edges only the person looking at the picture can supply, and
it lives in its own store for exactly that reason — `harness/figures.py`. The two
tracks share one editor and one keyboard and no geometry; when reading the rule
above, keep its subject attached, or the figure half reads as an exemption from
something it was never inside.

**Why a second store rather than more of `gt/seg/`.** That directory held 122
pages under the full SegmOnto vocabulary, drawn as free polygons around ink. Both
the label set and the geometry regime differed from this one, and nothing in an
ALTO says which scheme produced it — the same absence of an internal witness that
lost 18 pages of transcription when a file's role lived only in the directory
holding it. So the role lives in the directory again. `gt/seg/` has since been
deleted, no model having been trainable on it; the reasoning is kept because it
is why this store's geometry regime is what it is, not because the old one
survives to be confused with it.
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
    gt/zones/_eval.lst         the held-out split; one filename per line
    gt/zones/_plate.lst        }  what a leaf is where it is not a text page,
    gt/zones/_blank.lst        }  one list per kind (`LEAF_KINDS`). A page in one
    gt/zones/_cover.lst        }  of these is in neither of the two above, and
    gt/zones/_map.lst          }  `is_exempt` is the question every caller asks
    gt/zones/_apparatus.lst    }  rather than naming a list
    gt/zones/_rule_exempt.json {ref: [rule-id, ...]} — order rules ruled on
    gt/zones/_ink_exempt.json  {ref: [{y0,y1,note}]} — bands of ink ruled not type,
                               each with the reason it was ruled so

`_journal.jsonl` and the `.prev`/`.tmp` pairs are recovery data and ignored. So is
`_ink_cache.json`, which is derived: the uncovered-ink verdict per page, written by
whatever last ran the check, stamped with the mtimes it was true for.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, cast

from lxml import etree

from . import corrections as _corr
from . import farms, provenance, train
from . import zones_config as zc

if TYPE_CHECKING:
    from kraken.lib.vgsl import TorchVGSLModel
from .atomic import tmp_for, write_atomic
from .figures import read_blocks, to_rect
from .ns import ALTO_NS
from .parallel import gpu_workers, pmap, ptrack
from .paths import scan_for  # re-exported; this module's callers name it here
from .refs import norm_ref, parse_ref

ZONEDIR = "gt/zones"
# Aliased from `farms.py`, which is the one declaration of every derived path. The
# name stays because 68 call sites across the package spell it — and note `VIEWDIR`
# is a different *value* here and in `recognize.py`, so there was never one constant
# to hoist. What is hoisted is the value.
SCANS = farms.SCANS

# The machine store and the view joining the two. `mz/zones/` holds what the trained
# segmenter emitted, raw: free polygons at whatever x kraken drew, kraken's own ids.
# `zones/` is a symlink farm over both in which the human file always wins — the same
# shape as `ocr/` over `gt/ocr/`, and the same rule: **reads may resolve through the
# view; writes never do.** Both are derived and gitignored, `mz/` because it is
# regenerable from `models/` and `scans/w-figs-blotted/`, the view because half its
# links point into `mz/` and a committed farm would dangle on clone.
MZDIR = "mz/zones"
VIEWDIR = farms.ZONES_VIEW

# Provenance travelling with the data, as with `corrections.CORR_ID_PREFIX`. A block whose
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

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = (f"{ALTO_NS} "
                   "http://www.loc.gov/standards/alto/v4/alto-4-2.xsd")

TRAIN_LST = "_train.lst"
EVAL_LST = "_eval.lst"

#: **What a leaf is, where it is not a text page.** A human has looked at it and
#: ruled it out of the transcription tracks — which is a different statement from
#: "keyed and holds nothing" and a very different one from "not reached yet".
#:
#: This was one value, `exempt`, and it was a *training* flag: kept out of train
#: and eval alike, because a plate has no text column and is therefore neither an
#: example of the layout nor a fair test of it. It stayed one value while five
#: different things accumulated behind it. By the time the ruling reached a reader,
#: the edition was sorting these pages with four discriminators borrowed from other
#: stores — figure boxes for a plate, `data/runs.json` for the apparatus,
#: `gt/page-img/` for a hand-worked leaf — and the one kind with no other store,
#: a **blank**, was indistinguishable from the one whose store was merely
#: unpopulated: the volume's folding map rendered exactly like an empty verso.
#:
#: So the kind *is* the split. Nothing infers it — a model may not propose one and
#: no rule derives one from figure boxes or from a neighbouring page. It is written
#: by a human in `zones edit`, at the moment they are looking at the raster and have
#: already decided, which is the only moment the judgement is cheap and the only
#: authority that may make it.
#:
#: Closed, and an unknown value is a refusal rather than a page that quietly trains.
LEAF_KINDS = ("plate", "blank", "cover", "map", "apparatus")

#: The splits a *text* page can be in — the training bookkeeping, which is the whole
#: of what this axis ever meant before the kinds were separated out of it.
TEXT_SPLITS = ("train", "eval")

#: Two text-page splits and the leaf kinds, in one namespace because they answer one
#: question — *what is this leaf, and what is it therefore in or out of?* A page is
#: `train` or `eval` when it is prose, and one of `LEAF_KINDS` when it is not.
SPLITS = (*TEXT_SPLITS, *LEAF_KINDS)

# The editor offers each kind under its own initial. Asserted rather than assumed:
# two kinds sharing a letter would make one of them unreachable from the keyboard,
# and the symptom is a key that silently does the wrong thing.
assert len({k[0] for k in LEAF_KINDS}) == len(LEAF_KINDS), \
    "leaf kinds must have distinct initials; the editor keys off them"

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
#: Rulings on the first-line indent check — measured indents a human has judged
#: not to be paragraph openings. Its own file and not `_ink_exempt.json`'s,
#: because the two answer different questions about the same page and a shared
#: ledger would make "ruled" mean two things.
PARA_EXEMPT_JSON = "_para_exempt.json"
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
    *chosen* sequence — a split is picked for heterogeneity, and stepping to its
    pages through 700 scans nobody means to key is not navigation.

    Accepts either a list file (`chukchi-1-019.xml` per line, bare refs and paths
    also read) or a directory, which is taken to mean every page file in it. The
    second is there because "everything in `gt/zones/`" is the obvious
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
    the writer, exactly as `lines.page_lines` appends a recovered line after the
    ALTO's last index rather than renumbering around it.

    Empty for a page never keyed. That is not the same as a page keyed and found to
    hold nothing — the latter has a file with no blocks in it, and `has_zones`
    below is what tells them apart.
    """
    out = []
    for b in read_blocks(alto_for(ref, root, store), with_points=with_points):
        out.append(to_rect(b, with_points))
    return sorted(out, key=lambda z: (z["y0"], z["x0"]))


def has_zones(ref: str, root: Path = Path("."), store: str = ZONEDIR) -> bool:
    """Whether this store holds a zone file for this page — zones in it or not.

    A file question and nothing more. **It used to be the answer to "has a human
    been through this page" as well, and it is not any more**: that reading rested
    on an empty file being the record of a leaf a human had ruled out of the text
    tracks, which was true before the leaf kinds existed and stopped being true
    when they arrived. `keyed` is the predicate for that question now, and this one
    should be asked only where the file itself is the subject — an overwrite guard,
    a store census, "is there a prediction" against `MZDIR`.

    Under the leaf kinds an exempt leaf holds **no zone file at all**: the split
    mark is the record that somebody looked, and an empty ALTO beside it was one
    fact stated twice, with the weaker of the two spellings surviving a `cp -r`.
    """
    return alto_for(ref, root, store).exists()


def settled_refs(root: Path = Path("."), store: str = ZONEDIR,
                 splits: dict[str, str] | None = None) -> list[str]:
    """Every page a human has been through: keyed zones, or a ruled leaf.

    `zone_refs` is the store census and answers a file question. This is the
    *worklist* question, and the two stopped being the same answer when a ruled
    leaf stopped holding a file — a sweep or a page list built on `zone_refs`
    alone drops all 115 ruled leaves, so the editor could no longer navigate back
    to a plate it had just ruled and `zones check --all` stopped reporting them at
    all. Both are pages somebody settled, and a census of settled work that omits
    them is wrong in the direction that looks like less work remaining.

    Only for the human store: a machine store has no leaf rulings in it, so the
    union degenerates and `zone_refs` is the whole answer.
    """
    refs = set(zone_refs(root, store))
    if store == ZONEDIR:
        # `splits` for `validate_page`'s reason: seven `.lst` files re-read and
        # every name re-parsed through `norm_ref`. A caller that already holds the
        # map hands it down rather than making a second one.
        splits = load_splits(root) if splits is None else splits
        refs |= {r for r, v in splits.items() if v in LEAF_KINDS}
    return sorted(refs, key=parse_ref)


def keyed(ref: str, root: Path = Path("."),
          splits: dict[str, str] | None = None) -> bool:
    """Has a human been through this page — by keying zones, or by ruling the leaf.

    **The two ways a page gets settled, and they are not interchangeable.** Keying
    zones says "this is a text page and here is its column"; ruling a leaf kind
    says "this is not a text page at all". Both are a human's act and both take the
    page off the worklist, so every caller that means "is there anything left to do
    here" has to accept either — the editor's `keyed` flag, its progress count, and
    the itinerary's resume most of all, since a page that reads unsettled forever
    is one the resume returns to forever.

    **Never satisfied by a machine.** `has_zones(store=MZDIR)` is a different
    question and answering this one with it would let a `zones predict` sweep mark
    the whole corpus done and leave the next session with nowhere to resume.
    """
    return has_zones(ref, root) or is_exempt(ref, root, splits)


# ------------------------------------------------------------ column anchoring

def _content_rows(mask, width: int, cfg: dict) -> tuple[int, int] | None:
    """First and last row of real ink on the page, or None if there is none.

    A run of `CONTENT_MIN_RUN` consecutive inked rows is required at each end, so a
    speck of scanner dirt in the margin cannot stretch the band across half a page
    of blank paper. The per-row threshold is a share of the page *width* rather
    than of the densest row: taking it from the maximum would let one black
    photograph raise the bar above every line of type on the same page.
    """
    import numpy as np
    row = mask.sum(axis=1)
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
                  cfg: dict | None = None, mask=None) -> dict:
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

    # `mask` lets a caller that has already decoded the page hand it over. The
    # decode is the cost of this whole check — see `lines.ink_mask`.
    #
    # **Named `mask` and not `ink`**, which is what it was: `ink` also names a
    # *boolean* on `validate_page` and `validate_corpus` in this module, with
    # opposite defaults, and `validate_page` even reads `bool(ink and zones)` —
    # correct for the flag and a `ValueError: truth value of an array is
    # ambiguous` for the array. Not `ink_mask` either: that is the function
    # called on the next line, and a parameter of that name would shadow it.
    mask = ink_mask(mask if mask is not None else scan_for(ref, root))
    h, w = mask.shape

    rows = _content_rows(mask, w, cfg)
    content = ({"y0": max(0, rows[0] - pad), "y1": min(h, rows[1] + pad)}
               if rows else {"y0": 0, "y1": h})

    over = zc.override_windows(cfg, ref)
    if over is not None:
        return {"ref": ref, "columns": over, "measured": False,
                "source": "override", "content": content}

    band = mask[int(h * a["band_top"]):int(h * a["band_bottom"]), :]
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
                    cfg: dict | None = None, mask=None) -> dict:
    """Back-compatible name for the horizontal half of `measure_frame`."""
    return measure_frame(ref, root, cfg, mask)


def page_windows(ref: str, root: Path = Path("."),
                 cfg: dict | None = None, mask=None) -> list[dict]:
    """Just the windows, for callers that do not care how they were arrived at."""
    return measure_frame(ref, root, cfg, mask)["columns"]


# ---------------------------------------------------------------- split marking

def _lst_path(root: Path, split: str) -> Path:
    """The list a split's members are named in. Derived, not mapped.

    Three values were mapped by hand here. Seven would be a table to keep in step
    with `SPLITS`, and the failure of one going missing is silent — `load_splits`
    iterates `SPLITS`, so an unlisted kind reads as "nobody is in it" rather than
    raising. Deriving the name means a kind added to the vocabulary has its list
    by construction.
    """
    if split not in SPLITS:
        raise KeyError(f"{split!r} is not one of {', '.join(SPLITS)}")
    return zone_dir(root) / f"_{split}.lst"


def _read_lst(p: Path) -> list[str]:
    if not p.exists():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def load_splits(root: Path = Path(".")) -> dict[str, str]:
    """`{ref: split}` over the lists — a text-page split, or what the leaf is.

    A ref in more than one file resolves to the **most exclusionary** of them: any
    leaf kind over `eval` over `train`. Every one of these lists exists to keep
    pages out of something, so the safe reading of a contradiction is the one that
    honours the exclusion rather than the one that trains on a plate.
    `validate_corpus` reports the duplicate separately rather than leaving the
    resolution silent.

    **The leaf kinds do not rank against each other**, and a page in two of them is
    a contradiction no ordering can honestly resolve — a leaf is not more blank than
    it is a plate. They share one rank, so the winner is whichever `SPLITS` names
    first; `validate_corpus` is what reports it, and this does not pretend to
    adjudicate.
    """
    rank = {"train": 0, "eval": 1, **dict.fromkeys(LEAF_KINDS, 2)}
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


def is_exempt(ref: str, root: Path = Path("."),
              splits: dict[str, str] | None = None) -> bool:
    """Has a human ruled this leaf out of the transcription tracks?

    **The one predicate, so that no caller spells the test itself.** Roughly thirty
    sites across nine modules used to compare the split against the string
    `"exempt"`, and two of them — `dispatch.survey` and `dispatch.collate_survey` —
    did not read the split at all but tested for a filename inside `_exempt.lst`.
    That second form **fails open**: the day the list is renamed or its shape
    changes, the test returns `False` and the pass starts dispatching agents at
    plates, silently and with no error to notice. A refusal that quietly stops
    refusing is the failure mode this project is organised against, so the
    question gets one implementation and every caller asks it.

    `splits` is for a caller that has already loaded them and is asking about a
    corpus of pages; it is the same answer, not a cheaper approximation.
    """
    marked = (splits if splits is not None else load_splits(root)).get(
        norm_ref(ref))
    return marked in LEAF_KINDS


def set_split(ref: str, split: str, root: Path = Path(".")) -> dict:
    """Put this page in exactly one of the lists.

    Removes from **every** list before adding, so a page toggled back and forth
    cannot end up in two — the state that makes an eval set meaningless while both
    files still look plausible. It sweeps all of `SPLITS` rather than the pair it
    is moving between, which is what keeps that true as the vocabulary grows: a
    page re-ruled from `plate` to `blank` leaves no member behind.
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
        write_atomic(p, "".join(e + "\n" for e in entries))
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
                 for a, b in zip(g, m, strict=True)), default=0)
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


# The kinds `page_departure` returns, weakest claim about the human first, and
# the field name each takes in a composition row. Ordered, because the order *is*
# the strength scale — a report that listed them alphabetically would put
# `a label differs` above `zone count differs` and say nothing.
DEPARTURE_KINDS = (
    ("identical", "identical"),
    ("geometry only", "geometry_only"),
    ("a label differs", "label_differs"),
    ("zone count differs", "zone_count_differs"),
    ("no prediction", "no_prediction"),
    # Off the scale rather than at the end of it. A plate has no correct
    # segmentation — `score` excludes them for that reason — so it has nothing to
    # have departed *from*, and its empty file against an absent prediction would
    # otherwise read as `no prediction`, the table's strongest claim. That put 83
    # plates in the report and hid `1-359`, the one page that genuinely reached
    # human zoning with nothing predicted, which is the same burial `corpus
    # state`'s `zoned-mz` rung had to be fixed for. Kept as a row and not dropped:
    # a silent exclusion is how a shrinking denominator reads as a result.
    #
    # **One row, not one per leaf kind.** This table measures departure from a
    # prediction, and a plate, a blank and a map have equally nothing to depart
    # from — splitting the row would be five ways of saying "off the scale" in a
    # report that is not about what the leaf is. The kind is in `gt/zones/`; the
    # question here is only whether the page is on the scale at all.
    ("not a text page", "not_a_text_page"),
)


def departures(refs: list[str], root: Path = Path("."),
               nudge_px: int = NUDGE_PX,
               tick: Callable | None = None) -> list[dict]:
    """Per page: how far the human ruling went beyond the prediction it started from.

    **The criterion existed and the audit did not.** `_independent` has been the
    rule `--remark-eval` selects on since the eval set was drawn, and nothing ever
    reported it afterwards — so "this held-out page is the model's own output with
    the edges pulled straight" was knowable at selection time and invisible at
    every reading of a score since. A qualifier that outlives its number by exactly
    one command is the same shape as a provenance rank nothing re-checks.

    `shift` is null where it means nothing: a page whose zone *count* differs has
    no per-edge correspondence to measure, and `page_departure` returns a sentinel
    there rather than a distance. Publishing the sentinel would put 10⁹ in a column
    of pixel values.

    **Two thresholds meet in `zones diff`'s output and they are not the same
    number**, which is worth knowing before reading the two sections together.
    `zone_diff`'s `edge` fires above `min_zone_h_px` (30) and asks *is this a
    different segmentation of the page*; `NUDGE_PX` (20) asks *did the human's
    ruling go beyond straightening edges*. So a page can report zero differences
    and still count independent — `1-052` does, at 22 px. That is not a
    contradiction but it is a real tension, since the looser question currently
    has the tighter bar, and moving either constant moves the eval set.
    """
    splits = load_splits(root)
    out = []
    for ref in ptrack(refs, tick):
        ref = norm_ref(ref)
        split = splits.get(ref, "")
        kind, shift = ("not a text page", 10**9) if split in LEAF_KINDS \
            else page_departure(ref, root)
        out.append({
            "ref": ref,
            # The kind the human ruled, where they ruled one — so the row still
            # says *which* sort of leaf it is even though `kind` above collapses
            # them all to one point off the scale.
            "split": split,
            "kind": kind,
            "shift_px": shift if kind in ("identical", "geometry only") else None,
            # A leaf nobody could segment is off the scale, so it is not
            # independent evidence either — the sentinel shift would otherwise
            # carry it past the threshold and count 83 plates as the strongest
            # witnesses in the set.
            "independent": (kind not in ("identical", "not a text page")
                            and shift > nudge_px),
        })
    return out


def departure_composition(rows: list[dict],
                          nudge_px: int = NUDGE_PX) -> list[dict]:
    """`departures` rolled up per split — what a split is actually *made of*.

    This is the row that belongs beside a recall figure. A held-out set half of
    which is the model's own segmentation measures how well the model agrees with
    itself, and the number alone cannot say so.
    """
    by_split: dict[str, list[dict]] = {}
    for r in rows:
        by_split.setdefault(r["split"] or "(unsplit)", []).append(r)
    out = []
    for split in sorted(by_split):
        rs = by_split[split]
        counts = {field: sum(1 for r in rs if r["kind"] == kind)
                  for kind, field in DEPARTURE_KINDS}
        out.append({"split": split, "pages": len(rs), **counts,
                    "independent": sum(1 for r in rs if r["independent"]),
                    "nudge_px": nudge_px})
    return out


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

    **No caller today, and kept deliberately.** A review pass flagged it as dead
    surface, which by reference count it is; what that count cannot see is that
    it is `record_ink_many`'s twin for these files, and the argument for that one
    is in `README.md`. Deleting it does not remove the quadratic rewrite, it
    removes the thing that already solved it — so the next corpus-wide
    reassignment gets written as the loop this exists to avoid, and the batched
    form has to be rediscovered along with the reason.
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
        write_atomic(_lst_path(root, split),
                     "".join(f"chukchi-{r}.xml\n" for r in refs))
    return counts


def remark_eval(root: Path = Path("."), fraction: float = 0.20,
                commit: bool = False, tick: Callable | None = None) -> dict:
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

    # `_independent` reads both stores per ref and is the whole cost here, so it
    # runs once over the train list — under the bar — rather than per part inside
    # the loop below. Same set, and the only place a count of the work exists.
    independent = {r for r in ptrack(train, tick) if _independent(r, root)}

    picked, rows = [], []
    for part in sorted(by_part):
        indep = [r for r in by_part[part] if r in independent]
        rest = [r for r in by_part[part] if r not in independent]
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
    write_atomic(p, json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return {"ref": ref, "exempt": data.get(ref, [])}


def load_ink_exempt(root: Path = Path(".")) -> dict[str, list[dict]]:
    """Zone-level rulings: ink the zoning legitimately does not cover.

    The line layer's equivalent is `corrections.load_ink_exempt`, over its own
    file. The store mechanism is shared; the question each answers is not.
    """
    return _corr.load_exemptions(zone_dir(root))


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


def cached_ink(ref: str, root: Path = Path("."),
               cache: dict | None = None) -> dict | None:
    """This page's stored verdict, or None if it was never asked or has gone stale.

    None rather than the stale record, and that is the whole discipline of the
    thing: a verdict about a page as it was two saves ago, rendered in the same
    column as a live one, is exactly the fluent nonsense this project is organised
    against. Unknown is a state the list can draw; wrong is not.

    `cache` is a `load_ink_cache` a caller already holds. Without it this parses
    the whole cache file to read one entry, which the zones list did once per row
    over 832 rows. **The staleness check is unaffected and deliberately so**: the
    stamp is compared per ref against the files' live mtimes either way, so a
    hoisted cache still yields `None` for a page saved since it was read. What is
    hoisted is the read, never the verdict.
    """
    ref = norm_ref(ref)
    hit = (load_ink_cache(root) if cache is None else cache).get(ref)
    if hit and hit.get("stamp") == ink_stamp(ref, root):
        return hit
    return None


def _ink_verdict(ref: str, report: dict, root: Path) -> dict:
    """One `validate_page(ink=True)` result reduced to its cache record.

    Four states, and the one that must survive the reduction is `ruled` against
    `clean`: a page whose bands were all excused has to stay distinguishable from
    one where nothing was ever found, since that difference is the record that
    `_ink_exempt.json` exists to keep.
    """
    if not report.get("ink_checked"):
        # Not keyed, or ruled not a text page. Uncovered ink is a statement about
        # nothing here, and caching "clean" would be a claim.
        rec: dict[str, object] = {
            "state": "skip", "bands": 0, "ruled": 0, "stale": 0, "note": ""}
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
    return rec


def _write_ink_cache(data: dict[str, dict], root: Path) -> None:
    """The whole cache, sorted by ref, written through a temp and renamed.

    **The temp carries the pid**, because the rename is atomic and the write into
    the temp is not: two processes sharing one `_ink_cache.json.tmp` interleave
    their bytes and then one of them renames the result into place. The editor
    saves a page while a sweep is running often enough for that to be a real
    sequence rather than a theoretical one.
    """
    p = zone_dir(root) / INK_CACHE_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"_about": ("Derived and disposable: the uncovered-ink verdict for each "
                      "page, cached because it is the one check that reads the "
                      "raster. `stamp` is the mtime of the page's ALTO and of "
                      "_ink_exempt.json; an entry whose stamp no longer matches is "
                      "unknown, not stale-but-usable. Delete this file freely — "
                      "keying refills it.")}
    doc.update({k: data[k] for k in sorted(data, key=parse_ref)})
    tmp = tmp_for(p)
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    tmp.replace(p)


def record_ink(ref: str, report: dict, root: Path = Path(".")) -> dict:
    """Reduce one `validate_page(ink=True)` result to a verdict, and store it.

    The ink pass is ~0.20 s of raster work against ~1 ms for every other check, so
    a list of 122 pages cannot run it on render. But the editor **already runs it**
    on every page it opens and every page it saves, and the corpus sweep runs it
    under `--ink`; the answer is being computed and thrown away. So it is written
    here instead, and the list is a reader of what keying already produced rather
    than a job that recomputes it.

    **One page at a time is the editor's shape, not the sweep's** — a save is one
    verdict and there is nothing to batch. A sweep uses `record_ink_many`, and the
    reason is in that docstring.
    """
    ref = norm_ref(ref)
    rec = _ink_verdict(ref, report, root)
    data = load_ink_cache(root)
    data[ref] = rec
    _write_ink_cache(data, root)
    return dict(rec, ref=ref)


def record_ink_many(items, root: Path = Path(".")) -> list[dict]:
    """Verdicts for many pages, read once and written once.

    `record_ink` is a read-modify-write of the **whole** file: it loads every
    entry, replaces one, and re-serializes all of them. Called per page from a
    sweep that is what 832 pages of it costs — the corpus sweep was re-reading and
    re-writing a 130 KB JSON once for every page it checked, which is quadratic in
    the size of the store for no reason anyone chose.

    It is also the shape that cannot survive being parallelised: the loop would
    have N workers each loading the file, adding their own entry and writing the
    lot back, so every verdict but the last would be dropped. Reading once here and
    writing once after the loop removes both, and the resulting file is identical —
    entries are sorted by `parse_ref` on the way out either way.

    `items` is `[(ref, report)]`, i.e. what a sweep already has in hand.
    """
    data = load_ink_cache(root)
    out = []
    for ref, report in items:
        ref = norm_ref(ref)
        rec = _ink_verdict(ref, report, root)
        data[ref] = rec
        out.append(dict(rec, ref=ref))
    _write_ink_cache(data, root)
    return out


ZONE_EXEMPT_ABOUT = (
    "Bands of ink the **zoning** legitimately does not cover — smudges, gutter "
    "blobs, offset from the facing page. Each carries the reason it was ruled "
    "so, and each is scoped to its own band: exempting a whole page's ink check "
    "would hide the next dropped zone on it. A matched band still reports, "
    "flagged `exempted` and carrying its note. This is the *zone* layer; ink "
    "inside a zone that no line covers is `ocr gaps`'s question and lives in "
    "gt/lines/_ink_exempt.json. Keyed PP-NNN.")


def set_ink_exempt(ref: str, regions: list[dict],
                   root: Path = Path(".")) -> dict:
    """Record bands of ink on this page that a human has ruled the zoning need
    not cover.

    **A reason is required and is the point of the file** — see
    `corrections.clean_regions`, which enforces it for both layers. Scoped to a
    band, never to the page: the next dropped zone on the same leaf must still
    report.

    **This settles the zone-level question only.** It used to settle the
    line-level one too, by being the single file both checks read: a band ruled
    "scanner smudge" while zoning also stopped `ocr gaps` from ever reporting
    that strip again, though the two are different claims about it. The line
    layer is `corrections.set_ink_exempt`.
    """
    ref = norm_ref(ref)
    clean = _corr.clean_regions(ref, regions)
    data = load_ink_exempt(root)
    if clean:
        data[ref] = clean
    else:
        data.pop(ref, None)
    _corr.write_exemptions(zone_dir(root), data, ZONE_EXEMPT_ABOUT)
    return {"ref": ref, "ink_exempt": data.get(ref, [])}


# The matcher is shared with the line layer rather than re-derived, so the two
# readers of these files cannot disagree about which band a region covers.
_ink_excuse = _corr.ink_excuse


# ---------------------------------------------------------------- ALTO writing

def _id_ordinal(block_id: str) -> int:
    """The trailing integer of a block id, or 0 where there is none.

    Only `build_alto`'s minter uses this, and only to avoid reusing an ordinal a
    caller supplied. An eScriptorium id (`eSc_textblock_ca04178c`) has no numeric
    tail and reads 0, which is right: it constrains nothing, and a page mixing the
    two schemes gets fresh ordinals from 1 that cannot collide with hex.
    """
    tail = (block_id or "").rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else 0


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
    carries no information, which is why nothing reads it any more: the crop
    padding that once needed it is a constant now. Page dimensions are the
    raster's own, so coordinates are in raster
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

    # A block that arrives carrying an `id` keeps it; only the rest are minted, and
    # they are minted *past* the highest ordinal present rather than by position.
    #
    # The zone store never supplies one, and does not need to: nothing anywhere
    # points at a zone id, so re-minting the whole page on every save is free. The
    # figure store is the opposite case — `data/readings.md` keys 395 caption blocks
    # by the last field of their block id (`figures.zone_suffix`) — so a figure drawn
    # above an existing one would, under positional minting, silently renumber every
    # block below it and re-point every caption on the page at the wrong picture.
    # That failure writes a well-formed file and breaks no check that runs at save
    # time; `harness corpus figures` would see the same counts reconcile.
    nxt = max((_id_ordinal(z["id"]) for z in ordered if z.get("id")), default=0) + 1
    for z in ordered:
        x0, y0 = int(round(z["x0"])), int(round(z["y0"]))
        x1, y1 = int(round(z["x1"])), int(round(z["y1"]))
        if z.get("id"):
            block_id = z["id"]
        else:
            block_id = f"{id_prefix}{ref}_{nxt:03d}"
            nxt += 1
        blk = etree.SubElement(ps, f"{{{ALTO_NS}}}TextBlock", {
            "HPOS": str(x0), "VPOS": str(y0),
            "WIDTH": str(x1 - x0), "HEIGHT": str(y1 - y0),
            "ID": block_id, "TAGREFS": tag_id[z["label"]]})
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

    **An empty text page is refused**, and this is the distinction the splits exist
    to draw. A text page with no zones and a page nobody has reached would be
    byte-identical in this store — `zone_refs` finds both, the sweep counts both as
    keyed, the list draws both as done — so an empty save does not record a
    judgement, it erases the difference between having made one and not. "Nothing
    here" is not a statement. Mechanical, like every other refusal here: it needs
    no reading of the page, and no layout rule can be configured to allow it.

    **A leaf kind is the statement, and it writes no file at all** — it hands off
    to `clear_leaf`, which removes this page's `gt/zones/` ALTO *and* its
    `mz/zones/` prediction and leaves the mark as the whole record. `exempt => no
    zones`: a leaf has no text column, so there is nothing for a zone to be. An
    empty ALTO beside the mark was the older spelling, from before the kinds
    existed, and it was one fact stated twice with the weaker half surviving a
    `cp -r`.

    The machine file was worse than redundant. A segmenter asked about a leaf with
    no text column does not decline — it finds the column anyway, so the 32
    predictions that outlived a ruling held 98 zones against 1 in ground truth,
    several of them paragraphs on blank paper.

    This is therefore also the repair path for a page keyed *before* it was ruled.
    The editor's slip was that keying zones and then ruling the leaf saved both,
    and nothing ever swept the prediction; the ruling is what clears them now.
    """
    ref = norm_ref(ref)
    effective = split or load_splits(root).get(ref) or DEFAULT_SPLIT
    if not zones and effective not in LEAF_KINDS:
        raise ValueError(
            f"{ref} has no zones and is marked {effective!r} — an empty text page "
            "is indistinguishable from one nobody has reached, so it would be "
            "counted as keyed while recording nothing. Three ways out, and they say "
            "different things: **say what the leaf is** if it is not a text page "
            f"({', '.join(LEAF_KINDS)}); key it if it is a text page; or **delete "
            f"it** — `harness zones delete {ref} --commit`, or `X` in the editor — "
            "if it should not be in the store at all. That third one is reachable "
            "from here: a page keyed and then emptied has no other way to be "
            "withdrawn.")
    if effective in LEAF_KINDS:
        return clear_leaf(ref, root, effective, exempt=exempt, stamp=stamp)
    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    size = raster_size(ref, root)
    tree = build_alto(ref, zones, size)

    p = alto_for(ref, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    tmp = tmp_for(p)
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


def clear_leaf(ref: str, root: Path = Path("."), split: str = "",
               exempt: list[str] | None = None,
               stamp: str | None = None) -> dict:
    """Rule a leaf out of the text tracks: keep the mark, drop both zone files.

    **`exempt => no zones`.** A plate, a blank, a cover, a map, an apparatus leaf
    has no text column, so there is nothing for a zone to be — and the leaf kind in
    the split lists is the whole record that a human looked. Most plates *do* carry
    a running title, and it is deliberately ignored: the folio propagates through
    the seam ledger (`harness/state.py`), so zoning the head of a plate records
    nothing the corpus reads and leaves a text-page label on a leaf that is not one.

    Not `delete_zones`, which is the different act: that withdraws the page from the
    store entirely, mark and all, for a ref keyed in error. This *keeps* the ruling —
    that is the judgement being recorded — and removes only what the ruling makes
    false.

    **`mz/zones/` goes too, and this is the half nothing did before.** A segmenter
    asked about a leaf with no text column does not decline; it finds the column
    anyway. The 32 predictions that outlived a ruling carried 98 zones —
    57 `MainZone-P`, 27 `MainZone-Other`, 9 `RunningTitleZone` — against 1 in
    ground truth, several of them paragraphs on blank paper. Nothing read them,
    because `gt/` outranks `mz/` in the view; that is a fact about today's
    consumers rather than a property of the store.

    `.prev` on both, and the journal, for `save_zones`' durability reason: this
    deletes tracked work, and the window before a commit exists is exactly when
    this repo lost pages once.
    """
    ref = norm_ref(ref)
    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    split = split or load_splits(root).get(ref) or ""
    # **`save_zones`' key set, so a caller need not know which of the two ran.**
    # `zones` is what the page holds *now*, which is zero; `dropped` is what was
    # taken away. Reporting the removed count as `zones` would put a live-looking
    # number on a file that no longer exists — the editor writes it straight into
    # its store selector, so the page would read `gt — 1` with no gt at all.
    # `cleared` is the flag the client keys its redraw off.
    out = {"ref": ref, "path": str(alto_for(ref, root)), "zones": 0,
           "split": split, "labels": "", "dropped": 0, "cleared": ""}
    gone = []
    for store in (ZONEDIR, MZDIR):
        p = alto_for(ref, root, store)
        if not p.exists():
            continue
        if store == ZONEDIR:
            out["dropped"] = len(read_zones(ref, root, store=store))
        p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
        p.unlink()
        gone.append(store)
    out["cleared"] = " ".join(gone)

    if exempt is not None:
        set_exempt(ref, exempt, root)
    if split:
        set_split(ref, split, root)
    with (zone_dir(root) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"saved_at": stamp, "ref": ref, "zones": 0,
                             "labels": {}, "split": split,
                             "dropped": out["dropped"],
                             "cleared": out["cleared"]},
                            ensure_ascii=False) + "\n")
    return out


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
        write_atomic(q, "".join(e + "\n" for e in entries))
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
    # Emptiness is checked once, up front, rather than carried as a `None` through
    # two variables that are only ever set together. The old form was correct and
    # `ty` still flagged it, because nothing in the code said the two move as a
    # pair — and a reader has no better way of knowing it than the checker did.
    if not windows:
        return "no column could be measured or configured for this page"
    offs = [max(abs(z["x0"] - w["x0"]), abs(z["x1"] - w["x1"])) for w in windows]
    best_off = min(offs)
    best = windows[offs.index(best_off)]
    if best_off <= tol:
        return None
    return (f"x {z['x0']}..{z['x1']} is {best_off:.0f} px off the column measured "
            f"on this page ({best['x0']}..{best['x1']}); tolerance is {tol:.0f}")


def uncovered_ink(ref: str, zones: list[dict], root: Path = Path("."),
                  cfg: dict | None = None,
                  windows: list[dict] | None = None, mask=None) -> list[dict]:
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
    it, the scanner's dark gutter. It carries the limitation that goes with that —
    this finds dropped *body* material, not everything on the leaf.

    `line_gaps` bounds itself by the same measured window. This docstring claimed
    that before it was true: it took the extent of the page's own line boxes, which
    differed here in both directions on 38 of 62 page/store pairs, and the
    consequence was not cosmetic — a band only the line side could see never
    reached the zone editor, so no human could rule it and `_ink_exempt.json` had
    no way to record one. Two detectors, one window, or a ruling made in one place
    does not bind the other.
    """
    import numpy as np

    from .figures import zones as fig_zones
    from .lines import COVER_PAD, ink_bands, ink_mask

    cfg = cfg or zc.load_config(root)
    ref = norm_ref(ref)
    mask = ink_mask(mask if mask is not None else scan_for(ref, root))
    h = mask.shape[0]
    windows = windows or page_windows(ref, root, cfg, mask)

    covered = np.zeros(h, dtype=bool)
    for box in list(zones) + [{"y0": z["vpos"], "y1": z["vpos"] + z["height"]}
                              for z in fig_zones(ref, root)]:
        covered[max(0, int(box["y0"]) - COVER_PAD):
                min(h, int(box["y1"]) + COVER_PAD)] = True

    x0 = min(int(win["x0"]) for win in windows)
    x1 = max(int(win["x1"]) for win in windows)
    return _merge_bands(ink_bands(mask, x0, x1, covered))


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
                  ink: bool = True, store: str = ZONEDIR,
                  splits: dict[str, str] | None = None) -> dict:
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
    a ruling is a human's, and which store is being *measured* does not change what
    a human said about the paper.

    **What a ruling settles is narrower than it once claimed, though.** This said
    an ink exemption rules that some mark on the page is not type, "which is true
    no matter whose zones are being measured against it" — and the file was read by
    both this check and `ocr gaps`, so it was true no matter which *question* was
    being asked either. The two are not the same question. Here it means the zoning
    need not cover that ink; over there it would mean no line was dropped in it, a
    claim nobody made while zoning. A folio the segmenter dropped inside a
    `RunningTitleZone` is exactly what the conflation hid. This function reads the
    zone layer, `gt/zones/_ink_exempt.json`, and settles only its own question;
    `harness/corrections.py` holds the line layer and the argument in full.
    """
    cfg = cfg or zc.load_config(root)
    # **Threaded in like `cfg`, and for a sharper reason.** This was read twice per
    # page from inside the two branches below, and each read re-parses all three
    # `.lst` files and `norm_ref`s every entry in them — 832 refs, so 75k
    # `parse_ref` calls and as many `Path.stem`s over a 60-page sample, a fifth of
    # `validate_corpus`'s non-decode time. It is also pure Python, so under `--jobs`
    # it was the GIL-bound share holding the sweep's speedup below what the same
    # pool gives `zones blot`.
    splits = load_splits(root) if splits is None else splits
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
            and not is_exempt(ref, root, splits):
        err("empty-page",
            "keyed with no zones and marked a text page — indistinguishable from a "
            "page nobody has reached, while counting as done. Say what the leaf is "
            f"({', '.join(LEAF_KINDS)}) if it is not a text page; key it if it is; "
            "or delete it (`--delete --commit`) if it does not belong in the store."
            # The remedy is the human store's. A file here with nothing in it means
            # the model found nothing on a page a human has not ruled a leaf, which
            # is a finding about the model and has no "say what it is" answer.
            if store == ZONEDIR else
            "the model returned no region for a page still ruled a text page")

    # **`exempt => no zones`, and the file is what is checked.** A ruled leaf has
    # no text column, so there is nothing for a zone to be and nothing for the
    # store to hold; the split mark is the whole record. The editor clears both
    # stores on a ruling now, so this catches the page that predates that — or one
    # ruled by hand in a `.lst` — and it is an error rather than a warning because
    # it is mechanical and has one remedy.
    #
    # The `mz/` arm is the one with teeth. A segmenter asked about a leaf does not
    # decline, it finds a column anyway: the 32 predictions that outlived a ruling
    # carried 98 zones against 1 in ground truth, several of them paragraphs on a
    # blank leaf. Nothing read them because `gt/` outranks `mz/` in the view, which
    # is a fact about today's consumers and not a property of the store.
    if has_zones(ref, root, store) and is_exempt(ref, root, splits):
        err("exempt-holds-zones",
            f"ruled {splits.get(ref)} — not a text page — while {store}/ still "
            f"holds a zone file ({len(zones)} zone(s)). A leaf has no column for a "
            "zone to sit in, so the ruling is the record and the file is a second, "
            "weaker spelling of it. Re-save the ruling in the editor, which clears "
            "both stores, or key it as a text page if the ruling is wrong.")

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

    split = splits.get(ref)
    # A page marked with a leaf kind is a plate, a map, a cover or a blank — a human
    # has ruled it not a text page. The layout warnings all describe how a *text* page
    # is normally arranged, so on this one they describe nothing and would be
    # permanent known-false noise, which is what buries real signal. The mechanical
    # errors above still stand: whatever zones the page does carry must still be
    # the right shape, or the mark is hiding a mistake rather than a plate.
    if split in LEAF_KINDS:
        # **Settled, though it holds no file.** `exempt => no zones`, so the
        # ruling is the record and the file test would report every plate in
        # the corpus as unkeyed — on the very row a human reads to decide
        # whether a page still needs work.
        return {"ref": ref, "keyed": True, "zones": len(zones),
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
                    store: str = ZONEDIR, jobs: int | None = None,
                    tick=None) -> tuple[dict, list[dict]]:
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
    rows, n_err, n_warn = [], 0, 0
    labels: dict[str, int] = {}
    seen: dict[str, int] = {}
    for s in SPLITS:
        for name in _read_lst(_lst_path(root, s)):
            seen[name] = seen.get(name, 0) + 1
    dup = sorted(n for n, c in seen.items() if c > 1)
    # A sweep that read 832 rasters and kept nothing would make the page list ask
    # for the same work again — so the verdicts are kept, but **collected here and
    # written once** after the loop rather than per page. `record_ink` rewrites the
    # entire cache on every call, so calling it 832 times made the sweep quadratic
    # in the size of the store; `record_ink_many` says the rest.
    #
    # **Only for the human store.** The cache is keyed by ref alone and stamped
    # with the page ALTO's mtime, and it feeds the editor's page list, which lists
    # ground truth. Letting a machine sweep write here would put two verdicts about
    # one page under one key with nothing to tell them apart — a verdict about work
    # nobody has done, drawn in the same column as one about work someone has. A
    # machine page's ink is measured fresh when asked for, and recorded nowhere.
    # **The page is measured in the pool; everything is folded out of it.** Under
    # `--ink` this is a raster decode per page and nothing else, which is what the
    # concurrency is for; the counters, the label census and the cache write stay
    # in one thread and in ref order, so the report is identical whatever `jobs`
    # says. `read_zones` is asked here rather than in the fold for the same reason
    # — it opens the same file `validate_page` just read.
    splits = load_splits(root)

    def _measure(ref: str):
        return (ref,
                validate_page(ref, root, cfg, ink=ink, store=store, splits=splits),
                read_zones(ref, root, store=store))

    verdicts: list[tuple[str, dict]] = []
    # `settled_refs`, not `zone_refs`: a ruled leaf holds no file and is still a
    # page somebody has been through, so a sweep built on the store census
    # alone would drop every plate and report less work as more done.
    todo = list(refs if refs is not None else settled_refs(root, store))
    for ref, r, zs in pmap(_measure, todo, jobs, tick):
        if ink and store == ZONEDIR:
            verdicts.append((ref, r))
        n_err += len(r["errors"])
        n_warn += len(r["warnings"])
        for z in zs:
            labels[z["label"]] = labels.get(z["label"], 0) + 1
        rows.append({
            "ref": ref, "split": r["split"] or "", "zones": r["zones"],
            "errors": len(r["errors"]), "warnings": len(r["warnings"]),
            "detail": "; ".join(e["rule"] for e in r["errors"])
                      or "; ".join(sorted({w["rule"] for w in r["warnings"]}))
                      or "",
        })
    if verdicts:
        record_ink_many(verdicts, root)
    # Counted off the reported rows rather than off the split files, so a scoped
    # sweep reports its own scope. Over the whole store the two agree.
    summary = {"pages": len(rows),
               "keyed": sum(1 for r in rows if r["split"]),
               "todo": sum(1 for r in rows if not r["split"]),
               "train": sum(1 for r in rows if r["split"] == "train"),
               "eval": sum(1 for r in rows if r["split"] == "eval"),
               # **`exempt` is kept as the total, and each kind counted beside
               # it.** The total is what the training reader wants — how many
               # pages are out of both lists — and dropping it would silently
               # change the meaning of a number that has been read for a year.
               # The per-kind counts are the new fact and are added, not
               # substituted; a reader comparing runs across this change sees
               # `exempt` unmoved.
               "exempt": sum(1 for r in rows if r["split"] in LEAF_KINDS),
               **{k: sum(1 for r in rows if r["split"] == k) for k in LEAF_KINDS},
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

BLOTDIR = farms.FIGS_BLOT


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
    ref = norm_ref(ref)
    src = scan_for(ref, root)
    if not src.exists():
        return {"ref": ref, "path": "", "action": "no-raster", "painted": 0}
    out = blot_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    if not (root / "gt" / "fig" / f"chukchi-{ref}.xml").exists():
        link = out / f"chukchi-{ref}.png"
        farms.relink(link, src)
        return {"ref": ref, "path": str(link), "action": "linked", "painted": 0}
    rep = write_fig_blot(ref, out, root)
    return {"ref": ref, "path": rep["path"], "action": "painted",
            "painted": rep["painted"]}


def blot_all(root: Path = Path("."), jobs: int | None = None, tick=None) -> dict:
    """Rebuild the whole blotted corpus.

    **Unconditional because it is cheap, not because freshness is unknowable** —
    and this docstring said the second thing for a long time, wrongly, with
    `farms.py` and CLAUDE.md repeating it. The claim was that a figure ALTO
    corrected after the blot leaves a raster still showing the figure and an mtime
    test would pass it. It would not: a corrected ALTO is *newer* than the blot, so
    a test against both inputs — `scans/` and `gt/fig/` — catches exactly that.
    (Against the scan alone it would be blind, the scan never changing; that is an
    argument for naming the right inputs.)

    What no mtime test can see is a **deleted** figure ALTO. A page whose zones
    were withdrawn should go back to being a link, and the stale painted PNG is
    still newer than the scan — absence has no timestamp. That is a membership
    question rather than a content one, and it is why `views check` verifies this
    farm by membership.

    So repainting everything is not a ruling that an incremental path is a bad
    idea. **Skip policy here is undecided**, and deliberately so: it belongs with
    the dependency graph — every derived artifact naming its inputs, so any verb
    can skip correctly — which is a sprint of its own and has not run. Until it
    does, unconditional is the honest default rather than a design. Named refs
    repaint unconditionally too, for the same reason.

    **The work is partitioned before it is spread, because it is two jobs sharing a
    verb.** 580 of the 832 pages have no figure and are a `relink` — a syscall,
    microseconds, and pure filesystem churn that a thread pool would only add
    contention to. The other 252 decode a PNG, paint it and encode it again, which
    is the part worth spreading. So the links run first and in one thread, and only
    the rasters are handed to `pmap`. Which page is which is `blot_one`'s own answer
    (`gt/fig/` present or not), asked once here rather than reimplemented.
    """
    from .paths import all_scans
    refs = all_scans(root)
    figs = root / "gt" / "fig"
    has_fig = {r: (figs / f"chukchi-{r}.xml").exists() for r in refs}
    links = [r for r in refs if not has_fig[r]]
    rasters = [r for r in refs if has_fig[r]]

    results = [blot_one(r, root) for r in links]
    results += pmap(lambda r: blot_one(r, root), rasters, jobs, tick)

    painted = sum(1 for r in results if r["action"] == "painted")
    linked = sum(1 for r in results if r["action"] == "linked")
    missing = sum(1 for r in results if r["action"] not in ("painted", "linked"))
    return {"dir": str(blot_dir(root)), "painted": painted, "linked": linked,
            "no_raster": missing, "total": painted + linked}


# ------------------------------------------------------------- the predictor

# Models this project trains live together, tracked, one directory apart from the
# downloaded weights in `models/` — which are large, third-party and gitignored.
# A model here is an artifact with a manifest beside it; see `install_model`.
MODELDIR = train.ZONES.modeldir
DEFAULT_MODEL = train.ZONES.default_model


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
                   root: Path = Path(".")) -> tuple[TorchVGSLModel, str]:
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
    # **`cast`, because kraken's own annotations disagree with each other.**
    # `load_models` is declared to return `BaseModel`, while `blla.segment`
    # demands `TorchVGSLModel`; at runtime it is the latter, which is why
    # `.user_metadata` below resolves at all. Naming the real type here is what
    # lets the three `segment(...)` call sites type-check, and confines the
    # library's imprecision to one line instead of spreading `object` through
    # every caller.
    net = cast("TorchVGSLModel", models[0])
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
    idxs = [rets["cls_map"]["regions"][lab] for lab in labels]

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
    from PIL import Image

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

    producer = provenance.Producer(
        step="harness zones predict --decode dp",
        label="region segmentation",
        kind="model", version=provenance.kraken_version(),
        model=str(model_path), sha256=sha, device=device,
        inputs={"decoder": "segmental-dp + paragraph-split",
                "paragraph_cuts": split_added,
                "raster": f"{BLOTDIR}/chukchi-{ref}.png"})
    tree = build_alto(ref, zones, size, id_prefix=DP_ID_PREFIX)
    # The provenance kraken would have written for us on the blob path; here the
    # writer is ours, so the step is spliced in by hand rather than dropped.
    desc = tree.getroot().find(f"{{{ALTO_NS}}}Description")
    desc.append(provenance.alto_processing(producer))

    out = mz_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    dest = alto_for(ref, root, MZDIR)
    tmp = tmp_for(dest)
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
    `scans/w-figs-blotted/...` path kraken would otherwise record, so the two stores
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

    from kraken import blla, serialization
    from PIL import Image

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
    # **Names its decoder, as the dp path already did.** Only one of the two said
    # which it was, so a `raw` file was silent and a silent file is
    # indistinguishable from a dp one to anything that does not already know.
    # That asymmetry cost a corpus-wide sweep: a re-prediction taken with the
    # default decoder replaced a dp-decoded store, and the ~20% fall in zone
    # count that followed was read as a property of the rasters it had just been
    # run against. Both arms name themselves now, and `Producer.step` is where
    # the rule that they must lives.
    producer = provenance.Producer(
        step="harness zones predict --decode raw",
        label="region segmentation",
        kind="model", version=provenance.kraken_version(),
        model=str(model_path), sha256=sha, device=device,
        inputs={"raster": f"{BLOTDIR}/chukchi-{ref}.png"})
    xml = serialization.serialize(
        seg, image_size=size, template="alto",
        processing_steps=[provenance.kraken_step(
            producer, ident="harness-zones-predict")])

    out = mz_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    dest = alto_for(ref, root, MZDIR)
    tmp = tmp_for(dest)
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
    if not single and is_exempt(ref, root, splits):
        return "ruled not a text page"
    if not force and has_zones(ref, root, MZDIR):
        return "already predicted"
    if not (blot_dir(root) / f"chukchi-{ref}.png").exists():
        return "no blotted raster"
    return ""


def predict_all(root: Path = Path("."), refs: list[str] | None = None,
                model_path: str | Path = DEFAULT_MODEL,
                device: str = "auto", decode: str = "raw",
                force: bool = False, named: bool = False, tick=None) -> dict:
    """Predict over a work-list, or over every page that has a blotted raster.

    What is skipped and why is `predict_skip`'s; this loops and reports. A sweep is
    therefore **resumable by construction** — run it again and it picks up the pages
    that have nothing, which over 832 pages of GPU work is the difference between an
    interruption costing minutes and costing the run.

    The model is loaded once for the whole run, which is most of why this exists as
    a sweep rather than a shell loop over the single-page form — and why several
    refs typed on the command line come here rather than looping the single-page
    form.

    **`named` is `predict_skip`'s `single`, and it has to travel.** A ref a human
    typed means that page even where it is ruled exempt; without this, the moment
    a two-page invocation started routing through the sweep, a named plate would
    have been dropped in silence by the very command that named it. Off by default
    because a corpus sweep is exactly where the exempt ruling should hold.
    """
    import time
    net, sha = load_segmenter(model_path, root)
    splits = load_splits(root)
    if refs is None:
        from .paths import all_scans
        refs = all_scans(root)

    started = time.monotonic()
    done, no_blot, exempted, already = 0, [], 0, 0
    zones = 0
    # `ptrack` counts every ref including the skips, deliberately: the denominator
    # a caller wants is the work-list they named, not the subset that turned out to
    # need running, which is not knowable until each page has been asked about.
    from .parallel import ptrack
    for ref in ptrack(refs, tick):
        why = predict_skip(ref, root, force, splits, single=named)
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

    `scans/w-figs-blotted/` is also what the segmenter is trained and predicted on, so
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

    **`[]` here means "no figures on this page" and must not also mean "the
    figure store would not parse".** This was wrapped in `except Exception:
    return []`, which reinstated exactly the condition the paragraph above
    describes — silently, on any page whose `gt/fig/` file was unparseable or
    held a legacy record shape, since a `KeyError` from the comprehension was
    caught alongside `XMLSyntaxError`. The three callers see a list either way
    and cannot tell the two apart; the 523 false positives came back with no
    error signal at all.

    Nothing is caught now, and nothing needs to be: `figures.read_blocks`
    already returns `[]` for a **missing** file — which is how that store
    records "no figures", and is the ordinary case on 580 of 832 pages — and
    every key read below is set unconditionally on every record it yields. So
    the only thing the guard could ever have caught was a real fault.
    """
    from .figures import zones as fig_zones
    return [(z["hpos"], z["hpos"] + z["width"],
             z["vpos"], z["vpos"] + z["height"]) for z in fig_zones(ref, root)]


def _ink_lines(mask, y0: int, y1: int, x0: int, x1: int,
               min_h: int, min_w: int,
               figs: list[tuple[int, int, int, int]] | None = None,
               ) -> list[list]:
    """Lines of type inside a band: `[y0, y1, left, right, strip]`, reading order.

    Row-runs of ink, bounded to the text column, with two floors. `min_h` drops a
    run too short to be a line; `min_w` drops one too *narrow* — a run 4 to 21 px
    wide is a speck in the margin, and five of the first twenty spurious paragraph
    breaks found were exactly that.

    **A row counts as inked if any pixel in it is dark, and a floor was measured
    instead.** One dark pixel in the interline gap therefore welds the lines above
    and below into a single run, which reports the leftmost ink of both, so an
    indented opening reads as flush — 113 suspected welds corpus-wide and a
    `line_h_max` of 586 px against a 49 px median. Requiring a row to carry a
    minimum of ink breaks those welds and finds the boundaries under them (recall
    96.8% → 97.7% at 16 px, welds 113 → 9), but it is also a *line-length* filter:
    a paragraph's short last line carries little ink per row and vanishes whole. It
    cost 25 false positives → 785, and is not in the code. The knowledge is in
    `.claude/skills/train-zones/`, with the rest of the sweep.

    `left`/`right` are offsets from `x0`, **not yet indents**: they become indents
    only after `_page_margins` subtracts the margin the page's own body establishes.
    Doing that here, per band, was a measured regression — a zone whose head is
    flush sets its own minimum, so the head reported an indent of 0 against itself,
    and 61 boundaries went missing that way.
    """
    import numpy as np
    sub = mask[y0:y1, x0:x1]
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
        # **The run's bounds are the union of its rows', and three statistics over
        # the rows were measured instead — mean 8375 false positives, median 4532,
        # bucketed mode 259, against 25 for the union.** The appeal is obvious: a
        # fleck of dirt in the gutter spans five rows of a fifty-row band and under
        # a union it takes the line's left edge outright, which is how `1-160` lost
        # its margin and its one real boundary at once.
        #
        # What defeats it is that the rows disagree *bimodally* rather than noisily.
        # Of a 50 px band roughly 22 rows are x-height and begin at the true left;
        # ~14 are ascender rows carrying ink only from the first *tall* letter, and
        # ~12 descender rows only from the first descender, both often hundreds of
        # px in. So a mean lands between the modes and a median lands in whichever
        # holds half — and which one that is moves with the letters each line
        # happens to open with, which is variance far larger than the 40 px being
        # looked for. The mode is the right statistic for that shape and measured
        # much the best of the three, with the best recall of anything tried
        # (99.5%, 9 missed boundaries against 55) — but still ten times the union's
        # false positives, on 174 pages against 23.
        #
        # The union is kept because **a line's left edge is an extremum by nature**,
        # the leftmost reach of one glyph occupying part of the band's rows, and
        # what dilutes the fleck is the percentile in `_page_margins` instead.
        cols = np.where(sub[a:b, lo:hi].any(axis=0))[0]
        if len(cols) and cols[-1] - cols[0] >= min_w:
            out.append([ay, by, lo + int(cols[0]), lo + int(cols[-1]), (lo, hi)])

    return out


def _page_margins(lines: list[list], min_w: int, pct: int = 25) -> dict[int, int]:
    """The left margin each column of the **page** sets — `{strip_lo: margin}`.

    **A low percentile of the strip's left edges, not their minimum**, and the
    difference is a speck of dirt. `1-160` sets its prose beside a figure and
    scatters flecks down the gutter between them, 4-10 px each, a dozen over 35
    lines. `min_line_w_px` cannot see one — the run it shares rows with is a whole
    line wide — so as the minimum the leftmost fleck became the page's margin, every
    clean line then measured a 40-47 px indent against a 40 px floor, and
    `tei generate` cut 20 paragraphs into a page the keying gives 3. Corpus-wide
    that failure was 96 of the 118 false positives, on five pages.

    The minimum is the one statistic a lone outlier owns outright, which is what
    makes it wrong for a quantity every line on the page attests. `margin_pct`
    spends a fixed share of the strip on dirt and asks the rest to agree; the
    line carrying the fleck still measures against the result as a *negative*
    indent, which is a miss rather than a break — the failure that remains is the
    one that costs least.

    **The population is every line in the strip, and two attempts to refine it both
    measured worse.** A *rolling* window tracking the margin down the page bought
    nothing at 21 lines and lost recall at 11: this book's pages do not drift within
    a page, whatever they do between pages. Restricting the statistic to lines
    justified to the measure — on the reasoning that a short line cannot attest a
    margin — lost 18 more boundaries at the median and changed nothing at the
    quarter. The reasoning was simply wrong: a paragraph's *last* line is short and
    flush left, so it is one of the best witnesses there is, and dropping every
    short line left a population richer in indented openings. A left margin is
    attested by where a line begins, and nothing about where it ends bears on that.

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
    by_strip: dict[int, list[list]] = {}
    for ln in lines:
        by_strip.setdefault(cluster[ln[4][0]], []).append(ln)
    stat: dict[int, int] = {}
    for k, rows in by_strip.items():
        lefts = sorted(ln[2] for ln in rows)
        stat[k] = lefts[len(lefts) * pct // 100]
    return {e: stat[cluster[e]] for e in edges}


def _page_lines(zones: list[dict], mask, figs, min_h: int, min_w: int,
                margin_pct: int = 25
                ) -> dict[int, list[tuple[int, int, int, int]]]:
    """Every zone's lines, with indents normalised against the whole page.

    Two passes: detect raw across all zones, establish the page's margins, then
    subtract. One pass per zone cannot do this — the margin is a property of the
    page's typography, not of whichever band happens to be under inspection.

    `margin_pct` is threaded rather than defaulted at every call site because the
    audit reports the same numbers the decoder acts on: a caller that measured
    against one margin and reported against another would be describing a page
    nobody generated.
    """
    raw = {i: _ink_lines(mask, z["y0"], z["y1"], z["x0"], z["x1"],
                         min_h, min_w, figs)
           for i, z in enumerate(zones)}
    margins = _page_margins([ln for v in raw.values() for ln in v], min_w,
                            margin_pct)
    return {i: [(ay, by, left - margins[lo], right - margins[lo])
                for ay, by, left, right, (lo, _hi) in v]
            for i, v in raw.items()}


def load_para_exempt(root: Path = Path(".")) -> dict[str, list[dict]]:
    """Rulings: measured indents a human has judged not to be paragraph openings.

    **This check's findings are questions about `gt/zones/`, so they are settled in
    `gt/zones/`.** Every one of them is answered by editing the zone store or by
    ruling that there is nothing to answer, and a ruling nobody records is one the
    next person walks again. `_ink_exempt.json` is the pattern and the shape is the
    same: keyed by ref, scoped to a band of the page rather than to the page, and
    the note is required, because "the tool complained and I made it stop" is not a
    record of anything.

    **A ruled start still reports, flagged.** `1-334`'s 1262 px and `1-196`'s
    311 px are not paragraph openings, but they are telling us something about text
    set beside a figure, and a ledger that hid them would lose it.
    """
    return _corr.load_exemptions(zone_dir(root), PARA_EXEMPT_JSON)


def paragraph_starts(ref: str, root: Path = Path("."), cfg: dict | None = None,
                     zones: list[dict] | None = None, mask=None,
                     store: str = ZONEDIR,
                     exempt: dict[str, list[dict]] | None = None) -> list[dict]:
    """Lines that open a paragraph *inside* a body zone — places it should be two.

    The one implementation, and it has two consumers on purpose. As a **check** it
    finds keying slips, where several paragraphs were saved as one zone; run over
    the corpus it found 20 such lines, 18 of which were exactly that and were fixed.
    As a **decoder step** it splits a predicted band, which the segmenter cannot do
    at all — two abutting `MainZone-P` rectangles rasterize to one continuous target,
    so the boundary is gone before the network sees it.

    **What it is not is a producer of structure.** `tei generate` used to cut a
    keyed band on this, which put a measurement over a human's assertion in a file
    that recorded no difference between them, and one speck of dirt in `1-160`'s
    gutter was worth 20 paragraphs the keying never had. The TEI is downstream of
    `gt/zones/` and `gt/ocr/` and of nothing else; this reads the raster, so it
    gates the zone store instead and stops there.

    A zone's own first line is never reported: that boundary already exists. Only
    labels listed in the config's `paragraph_split.labels` are examined, since an
    indent means something else inside a footnote or a running title.

    `index` is **1-based, within the zone** — the ordinal a human counts down the
    band — with `zone` likewise 1-based in reading order. `y` rides along for
    anything that needs to point at the raster. A start inside a band of
    `_para_exempt.json` carries `exempt` and the ruling's `note`; it is still
    returned, since a caller that wants the finding hidden can drop it and one that
    wants it counted cannot invent it.
    """
    cfg = cfg or zc.load_config(root)
    spec = cfg.get("paragraph_split") or {}
    indent = int(spec.get("indent_px", 40))
    labels = set(spec.get("labels") or [])
    min_h = int(spec.get("min_line_h_px", 6))
    min_w = int(spec.get("min_line_w_px", 50))
    margin_pct = int(spec.get("margin_pct", 25))
    min_zone_h = int(cfg.get("min_zone_h_px", 30))
    if not labels:
        return []

    ref = norm_ref(ref)
    if zones is None:
        zones = read_zones(ref, root, store=store)
    if mask is None:
        mask = _para_ink(ref, root)

    figs = _figure_rects(ref, root)
    ruled = (load_para_exempt(root) if exempt is None else exempt).get(ref, ())
    by_zone = _page_lines(zones, mask, figs, min_h, min_w, margin_pct)
    out = []
    for zi, z in enumerate(zones, start=1):
        if z["label"] not in labels:
            continue
        rows = by_zone[zi - 1]
        for li, (ly0, _ly1, left, right) in enumerate(rows, start=1):
            if li == 1:
                continue                     # the zone's own head, already a boundary
            # **And so is a line still at the zone's head.** The exemption above
            # counts lines, and a sub-line of ink defeats it: on `1-075` the band
            # opens on 6 px of descender from the paragraph above — ink the keyer's
            # boundary sits a few pixels too high to exclude — which takes the
            # exemption as line 1, leaving the paragraph's real opening line to
            # report as internal at the book's own 107-110 px indent. It was 19 of
            # 29 findings over the corpus, and the tell is that a page does not
            # open two paragraphs sixteen pixels apart. `min_zone_h_px` is the
            # tolerance, the one the audit matches boundaries with and for the same
            # reason: a cut lands on the opening line's ink, an editor clicks in
            # the whitespace above it.
            if ly0 - z["y0"] <= min_zone_h:
                continue
            if left >= indent:
                hit = next((r for r in ruled
                            if r["y0"] <= ly0 <= r["y1"]), None)
                out.append({"ref": ref, "zone": zi, "label": z["label"],
                            "index": li, "y": ly0,
                            "indent": left, "width": right - left,
                            "exempt": hit is not None,
                            "note": hit["note"] if hit else ""})
    return out


def split_at_paragraphs(zones: list[dict], ref: str, root: Path = Path("."),
                        cfg: dict | None = None, mask=None) -> list[dict]:
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
    for s in paragraph_starts(ref, root, cfg, zones=zones, mask=mask):
        if s["exempt"]:
            continue          # ruled not a paragraph opening; do not cut on it
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
        segs = [[a, b, z["label"]] for a, b in pairwise(edges) if b > a]
        for a, b, _lab in _consolidate(segs, min_h, direction):
            # **`paragraph_open` is the piece's own witness.** Every piece of a
            # split zone inherits that zone's label (`_consolidate`, same-label
            # rule), so the label records what the *zone* was and cannot say which
            # pieces begin a paragraph. This can, and `tei generate` reads it when
            # deciding where a `<p>` starts.
            #
            # As `paragraph_split.labels` stands — `MainZone-P` alone — it tells
            # that caller nothing the label does not, since the only bands cut are
            # ones whose label already opens a paragraph. It is set regardless, so
            # that adding a label to that list cannot quietly make the generator
            # run two measured paragraphs together.
            #
            # `a > z["y0"]` rather than an enumerate index because `_consolidate`
            # may fold a sliver away: what makes a piece an opening is that it
            # begins at a *measured cut*, which is exactly this test.
            out.append({**z, "y0": a, "y1": b, "paragraph_open": a > z["y0"]})
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
    by_zone = _page_lines(zones, ink, _figure_rects(ref, root), min_h, min_w,
                          int(spec.get("margin_pct", 25)))
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
                    refs: list[str] | None = None, store: str = ZONEDIR,
                    jobs: int | None = None,
                    tick=None) -> tuple[dict, list[dict]]:
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
    cfg = cfg or zc.load_config(root)
    spec = cfg.get("paragraph_split") or {}
    labels = set(spec.get("labels") or [])
    min_h = int(spec.get("min_line_h_px", 6))
    min_w = int(spec.get("min_line_w_px", 50))
    margin_pct = int(spec.get("margin_pct", 25))
    splits = load_splits(root)

    rows: list[dict] = []
    pages = asserted = recovered = internal = fired = 0
    # Every detected line's height. A "line" here is a run of rows with ink in them,
    # bounded by a *completely blank* row — so nothing accumulates, but one dark
    # pixel merges two lines into one run, and a merged run reports the leftmost ink
    # of both. That would read an indented paragraph opening as flush. If merging is
    # happening, it shows up as a population at roughly twice the median height.
    line_heights: list[int] = []
    # **One page's measurement, returning its own tallies rather than adding to
    # anyone's.** This is the body of the old loop unchanged; what moved is that it
    # no longer touches the enclosing counters, so it can run in the pool while the
    # fold below stays single-threaded and in ref order. The page costs a raster
    # decode, which is the whole reason for the pool.
    def _one(ref: str) -> dict | None:
        if is_exempt(ref, root, splits):
            return None
        zones = read_zones(ref, root, store=store)
        if not zones:
            return None
        try:
            mask = _para_ink(ref, root)
        except FileNotFoundError:
            return None
        figs = _figure_rects(ref, root)
        tol = int(cfg.get("min_zone_h_px", 30))
        by_zone = _page_lines(zones, mask, figs, min_h, min_w, margin_pct)
        acc: dict = {
            "heights": [ln[1] - ln[0] for v in by_zone.values() for ln in v],
            "internal": 0, "fired": 0, "asserted": 0, "recovered": 0, "rows": []}

        zi = 0
        for run in _same_label_runs(zones):
            first = zi + 1
            zi += len(run)
            if run[0]["label"] not in labels:
                continue
            merged = {**run[0], "y1": run[-1]["y1"]}
            want = [z["y0"] for z in run[1:]]           # what the editor keyed

            starts = paragraph_starts(ref, root, cfg, zones=[merged], mask=mask)
            mlines = _page_lines([merged], mask, figs, min_h, min_w, margin_pct)[0]
            acc["internal"] += max(0, len(mlines) - 1)
            got_zones = split_at_paragraphs([merged], ref, root, cfg, mask)
            got = [z["y0"] for z in got_zones[1:]]      # what survives consolidation
            acc["fired"] += len(got)
            detail = {s["y"]: s for s in starts}

            used = set()
            for w in want:
                acc["asserted"] += 1
                hit = next((g for g in got
                            if g not in used and abs(g - w) <= tol), None)
                if hit is not None:
                    used.add(hit)
                    acc["recovered"] += 1
                else:
                    # The **detected line** at that boundary, not the fired ones.
                    # Consulting only `starts` conflated "no line there" with "a
                    # line, just under threshold", since a start below `indent_px`
                    # never enters that dict — and every one of the 29 misses
                    # therefore reported -1, which read as a line-detection failure.
                    # `1-056` is the counter-example: indent 36 against a 40 floor.
                    ln = next((c for c in mlines if abs(c[0] - w) <= tol), None)
                    acc["rows"].append(
                        {"kind": "false_negative", "ref": ref, "zone": first,
                         "label": run[0]["label"],
                         "index": want.index(w) + 2, "y": w,
                         "indent": ln[2] if ln else -1,
                         "width": (ln[3] - ln[2]) if ln else -1,
                         "h": (ln[1] - ln[0]) if ln else -1,
                         "exempt": False, "note": ""})
            for g in got:
                if g in used:
                    continue
                d = detail.get(g, {})
                acc["rows"].append(
                    {"kind": "false_positive", "ref": ref, "zone": first,
                     "label": run[0]["label"],
                     "index": d.get("index", -1), "y": g,
                     "indent": d.get("indent", -1),
                     "width": d.get("width", -1),
                     "h": d.get("h", -1),
                     # A ruled start is still a row. It is out of the headline
                     # count because a human answered it, and in the table because
                     # the answer was "not a paragraph", not "nothing here".
                     "exempt": bool(d.get("exempt")),
                     "note": d.get("note", "")})
            # **A ruled start never reaches `got`** — the decoder skips it, which
            # is what the ruling is for — so it is put back here rather than
            # disappearing. Out of the headline count because a human answered it;
            # in the table because the answer was "not a paragraph", and the ones
            # ruled so far are saying something about text set beside a figure
            # that a hidden row could not.
            for s in starts:
                if not s["exempt"] or any(abs(s["y"] - w) <= tol for w in want):
                    continue
                acc["rows"].append(
                    {"kind": "ruled", "ref": ref, "zone": first,
                     "label": run[0]["label"],
                     "index": s["index"], "y": s["y"],
                     "indent": s["indent"], "width": s["width"], "h": -1,
                     "exempt": True, "note": s["note"]})
        return acc

    todo = list(refs if refs is not None else zone_refs(root, store))
    for acc in pmap(_one, todo, jobs, tick):
        if acc is None:            # exempt, unkeyed, or no raster — not a page read
            continue
        pages += 1
        line_heights.extend(acc["heights"])
        internal += acc["internal"]
        fired += acc["fired"]
        asserted += acc["asserted"]
        recovered += acc["recovered"]
        rows.extend(acc["rows"])

    fn = [r for r in rows if r["kind"] == "false_negative"]
    return ({"pages_read": pages,
             "asserted_boundaries": asserted,
             "recovered": recovered,
             "recall_pct": round(100 * recovered / asserted, 1) if asserted else 0.0,
             "false_negatives": len(fn),
             # Three ways to miss, and they have different remedies: no line was
             # detected there at all (welded or dropped), a line was seen but sits
             # near the margin, or it is just under the threshold.
             #
             # **`h`, not the sign of `indent`, says whether a line was found.**
             # Both are set to -1 when none was, and while the margin was the
             # strip's minimum no real line could measure negative, so the two
             # were the same test. Under a percentile a line can sit left of the
             # margin — `1-160`'s fleck line reads -36 — and reading that as "no
             # line detected" would send someone to the line detector for a page
             # whose lines are fine. A height cannot be negative and is the
             # witness the record already holds.
             "fn_no_line_detected": sum(1 for r in fn if r["h"] < 0),
             "fn_flush_left": sum(1 for r in fn if r["h"] >= 0 and r["indent"] < 10),
             "fn_slight_indent": sum(1 for r in fn if r["h"] >= 0 and r["indent"] >= 10),
             "boundaries_produced": fired,
             "false_positives": sum(1 for r in rows
                                    if r["kind"] == "false_positive"),
             "ruled": sum(1 for r in rows if r["kind"] == "ruled"),
             "pages_changed": len({r["ref"] for r in rows
                                   if r["kind"] == "false_positive"}),
             **_line_health(line_heights),
             "note": ("measured on the page the rule *produces*, after "
                      "consolidation — not on where it fires, which counted cuts "
                      "that fold straight back and so overstated the damage. Each "
                      "same-label run is merged first, because that is the page a "
                      "segmenter can give. Boundaries match within min_zone_h_px. "
                      "`false_positive` is still a worklist rather than a rate: gt "
                      "cannot arbitrate, being what the rule corrects. `ruled` is "
                      "what a human has already answered, in "
                      "gt/zones/_para_exempt.json — still listed, with its note, "
                      "and out of the worklist")},
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
    """The split the training run actually consumed, from `bogoras-seg/data/*.lst`.

    **Not `load_splits`.** The live lists move — a page keyed after the run defaults
    into `train` — so asking them which pages the model trained on gives an answer
    that is wrong in exactly the direction that flatters the model. Returns None when
    the frozen lists are missing, and the caller refuses rather than substituting.
    """
    work = root / DATADIR
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


# kraken raises this once per process, and it is a property of the pinned model
# rather than of any page: `models/blla.mlmodel` predates its new polygon
# extractor. It lives here, beside `load_segmenter`, because both pooled sweeps
# filter it in their workers and `recognize` may import from this module while the
# reverse is not allowed. `recognize` re-exports the name it has always used.
POLYGON_WARNING = "Enforcing use of the new polygon extractor"

PRED_CACHE = "_pred_cache"


def pred_cache_key(model_sha: str, decode: str, cfg: dict | None = None) -> str:
    """The cache key: the weights, the decoder, and whatever else the decoder reads.

    **`raw` reads nothing but the net**, so the sha and the decoder name it
    completely. **`dp` reads `cfg`** — `_dp_zones` decodes the page against the
    zone config's own numbers — so the config is part of the input and has to be
    part of the key. A key that does not name every input is a stale hit waiting
    to happen, and this one would have been reachable by an ordinary edit to
    `data/zones_config.json`.
    """
    if decode != "dp":
        return f"{model_sha[:16]}-{decode}"
    body = json.dumps(cfg or {}, sort_keys=True, ensure_ascii=False)
    return (f"{model_sha[:16]}-dp-"
            f"{hashlib.sha256(body.encode('utf-8')).hexdigest()[:8]}")


def pred_cache_dir(key: str, root: Path = Path(".")) -> Path:
    """Where a checkpoint's in-memory predictions are kept between processes.

    **Under `mz/zones/`, because that is the store for what a model emitted** and
    this is exactly that — the difference being that these are a *candidate*
    model's and so must not be mistaken for the installed one's. Hence a
    subdirectory keyed by the checkpoint's own sha256 rather than loose files:
    `zone_refs` globs `chukchi-*.xml`, so nothing that reads the store can see it.

    Not `train/bogoras-seg/`, the other obvious home: that track's base holds
    `data/` and `model/` and nothing else, which two tests assert.
    """
    return zone_dir(root, MZDIR) / PRED_CACHE / key


def _cached_pred(path: Path, blot: Path) -> list | None:
    """This page's zones from the cache, or None if nothing usable is there.

    **A stale entry is unknown, never stale-but-usable** — `_ink_cache`'s rule, and
    for its reason: a verdict about the page as it was two saves ago, presented
    beside a live one, is the fluent nonsense this project is organised against.

    Stamped with the *blot's* mtime and size, since the blot is what
    `predicted_zones` actually reads. `corpus_digest` would be the wrong witness:
    it digests `gt/zones/` geometry and a repainted raster does not move it.
    """
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        st = blot.stat()
        if rec["mtime_ns"] == st.st_mtime_ns and rec["size"] == st.st_size:
            return rec["zones"]
    except (OSError, ValueError, KeyError):
        pass
    return None


def _segment_page(blot: Path, net, device: str, decode: str, ref: str,
                  root: Path, cfg: dict) -> list:
    """One page's zones. The unit both the serial loop and the pool run."""
    from kraken import blla
    from PIL import Image

    with Image.open(blot) as s:
        page = s.convert("RGB")
    if decode == "dp":
        return _dp_zones(ref, root, cfg, net, page)
    seg = blla.segment(page, model=net, device=device)
    return [
        {"label": label,
         "x0": min(p[0] for p in g.boundary), "x1": max(p[0] for p in g.boundary),
         "y0": min(p[1] for p in g.boundary), "y1": max(p[1] for p in g.boundary)}
        for label, group in (seg.regions or {}).items() for g in group]


_WORKER: dict = {}


def _seg_worker_init(root: Path, model_path, device: str, decode: str,
                     cfg: dict, log_dir=None) -> None:
    """Load this worker's segmenter once, with its stderr already closed off.

    **The capture comes before the load**, `recognize._worker_init`'s rule and for
    its reason: kraken and torch both talk while a model comes up, and a warning
    raised during the load is as much a write to the shared fd as one raised on
    page 400.
    """
    import os
    import warnings

    from .parallel import capture_stderr

    if log_dir is not None:
        capture_stderr(log_dir)
    # By message, never by category: the pinned `blla.mlmodel` predates kraken's
    # new polygon extractor and says so once per process, which is a property of
    # the model and not of any page. Filtering it keeps the capture file empty in
    # the ordinary case, and an empty file is what makes a non-empty one worth
    # reading.
    warnings.filterwarnings("ignore", message=POLYGON_WARNING)

    os.chdir(root)
    net, _ = load_segmenter(model_path, root)
    _WORKER.update(net=net, device=device, decode=decode, root=root, cfg=cfg)


def _seg_worker(item: tuple[str, str]) -> list:
    ref, blot = item
    w = _WORKER
    return _segment_page(Path(blot), w["net"], w["device"], w["decode"],
                         ref, w["root"], w["cfg"])


def _segment_pool(todo, n, root, model_path, device, decode, cfg, tick=None,
                  done_before=0, total=0, on_done=None):
    """`todo` across `n` processes, each loading the segmenter once.

    `recognize._predict_pool`'s shape, and the same measurement underneath it:
    this sweep is a brief forward pass and then single-core Python, so threads
    return only the GIL-free share. Measured on `train score zones --model --decode raw`
    with `/usr/bin/time -v`: **123% of one CPU** across a 90 s run on a 16-core
    machine, with GPU utilization indistinguishable from the desktop's own idle.
    One core saturated, fifteen idle, the card asleep — which is `ocr predict`'s
    profile exactly, and why `--jobs` means processes on both.

    **`spawn`, not fork**: a forked child inherits a CUDA context it cannot use.

    Results come back in `todo` order — `as_completed` into a pre-sized list —
    so the report never reshuffles by which page happened to finish first. The
    `tick` continues the caller's count rather than restarting it, because the
    cache hits it already reported are part of the same total.

    **`on_done` fires per completion, not at the end**, and that is not a detail:
    the serial path caches each page as it finishes, so an interrupted sweep keeps
    what it did. Returning the whole list and letting the caller store it
    afterwards quietly took that away — a killed pooled run left nothing behind at
    all, which is the property the cache exists for on exactly the runs long
    enough to be killed.
    """
    import multiprocessing as mp
    import tempfile
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from .parallel import worker_output

    out: list = [None] * len(todo)
    log_dir = Path(tempfile.mkdtemp(prefix="harness-segment-"))
    with ProcessPoolExecutor(
            max_workers=n, mp_context=mp.get_context("spawn"),
            initializer=_seg_worker_init,
            initargs=(root, model_path, device, decode, cfg, log_dir)) as ex:
        futures = {ex.submit(_seg_worker, (r, str(b))): i
                   for i, (r, b) in enumerate(todo)}
        for k, fut in enumerate(as_completed(futures), 1):
            i = futures[fut]
            out[i] = fut.result()
            if on_done:
                on_done(todo[i][0], todo[i][1], out[i])
            if tick:
                tick(todo[i][0], done_before + k, total or len(todo))
    return out, worker_output(log_dir)


def predicted_zones(refs: list[str], root: Path = Path("."),
                    cfg: dict | None = None,
                    model_path: str | Path | None = None,
                    decode: str = "dp", device: str = "auto",
                    tick=None, cache: bool = True,
                    stats: dict | None = None,
                    jobs: int | None = None) -> dict[str, list]:
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

    **The model branch reports**, because it used to be the quietest expensive
    thing here: minutes over every keyed page with nothing on the terminal to
    distinguish it from a hung process. Measured on this machine against the
    installed model, warm, 717 pages — **0.96 s a page under `raw` (~11 min), 0.58 s
    under `dp` (~7 min)**. *Not* the ~14 s/page in `.claude/rules/zones.md`: that
    number is `ocr predict`'s, where `blla.segment` also traces baselines, and this
    model is region-only — `gt/zones/` carries no `TextLine`, so there is no
    baseline head and the expensive part never runs. The figure was carried over
    here once and put "~2.8 h" in this file's own docs for a sweep that takes
    eleven minutes.

    The store branch does not report — 717 `read_zones` is ~0.1 s, and a bar there
    is the flash `PROGRESS_AFTER` exists to suppress.

    **And it is cached, keyed on the checkpoint's own sha256.** `install_model`
    calls `score`, so installing a model *is* this sweep — and the documented
    workflow runs it twice over one checkpoint (`install` to preview, then `install
    --commit`), in two separate processes, each re-deriving byte-identical
    predictions from identical weights over identical rasters. ~11 min becomes ~22,
    and a repeat run drops to about five seconds. The figure track never had the
    problem because it predicts to `mz/fig/` and scores the store afterwards; this
    is the zone track keeping its in-memory scoring — which is what lets a
    checkpoint be measured without clobbering `mz/zones/` under an editing
    session — while stopping it from paying for itself a second time.

    `cache=False` is the control arm, and there is deliberately **no flag for it**:
    the key is content-addressed on the weights, so no sequence anybody can type
    reaches a stale hit. `stats`, when given, is filled with `{"cached": n}` so the
    caller can report the reuse rather than leave it invisible.

    **`jobs` runs the misses across processes** — the profile is single-core CPU
    with the card idle, so this is `ocr predict`'s trade and not a new one.
    `--jobs 1` keeps the in-process loop below, unchanged, as the control arm: the
    two must produce identical reports and there is a test that says so.
    """
    if model_path is None:
        return {r: read_zones(r, root, store=MZDIR) for r in refs}

    cfg = cfg or zc.load_config(root)
    # **The sha off the file, not out of a loaded model.** `load_segmenter` returns
    # `_model_sha256(p)` anyway, so hashing 5 MB here buys the cache key without a
    # CUDA context — and the parent holding one was not free: with `--jobs 4` its
    # context plus four workers' is five on an 8 GB card, which does not fit, and
    # the run sat at 3% CPU making no progress at all. The model is loaded below
    # only on the path that actually segments in this process.
    src = Path(model_path)
    if not src.is_absolute():
        src = root / src
    if not src.exists():
        raise FileNotFoundError(f"no segmentation model at {src}")
    sha = _model_sha256(src)
    if device == "auto":
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Both decoders, each under its own key — see `pred_cache_key`. They cannot
    # share: `train score zones` defaults to `dp` while `install_model` takes `score`'s
    # own default and gets `raw`, so the two verbs produce genuinely different
    # zones from the same weights and a shared entry would hand one the other's.
    cdir = (pred_cache_dir(pred_cache_key(sha, decode, cfg), root)
            if (cache and sha) else None)
    hits = 0

    out: dict[str, list] = {}
    todo: list[tuple[str, Path]] = []
    reported = 0

    def _report(item) -> None:
        nonlocal reported
        reported += 1
        if tick:
            tick(item, reported, len(refs))

    def _store(ref: str, blot: Path) -> None:
        if cdir is None:
            return
        st = blot.stat()
        cdir.mkdir(parents=True, exist_ok=True)
        # Written per page rather than as one file at the end, so an interrupted
        # sweep keeps the pages it finished — most of the value, on the run that is
        # actually likely to be killed.
        (cdir / f"chukchi-{ref}.json").write_text(
            json.dumps({"mtime_ns": st.st_mtime_ns, "size": st.st_size,
                        "zones": out[ref]}), encoding="utf-8")

    # **The cache is read and written in the parent, never in a worker.** Both
    # halves of that are deliberate: a hit costs a stat and a small JSON read, so
    # shipping one to another process would cost more than it saves; and keeping
    # every write on this side means the pool's workers stay a pure function from
    # page to zones, with nothing to say about where the answer is kept.
    #
    # A page with no blot still counts. The denominator is the work-list the caller
    # named — `predict_all`'s rule — and a bar whose total shrinks as it goes is a
    # bar that cannot be read.
    for ref in refs:
        blot = blot_dir(root) / f"chukchi-{ref}.png"
        if not blot.exists():
            out[ref] = []
            _report(ref)
            continue
        if cdir is not None:
            got = _cached_pred(cdir / f"chukchi-{ref}.json", blot)
            if got is not None:
                out[ref], hits = got, hits + 1
                _report(ref)
                continue
        todo.append((ref, blot))

    n = gpu_workers(jobs, len(todo)) if todo else 1
    if n > 1:
        # The workers load their own segmenters and this process loads none, which
        # is the whole reason the sha is taken off the file above: `n` contexts on
        # the card, never `n + 1`.
        def _landed(ref, blot, zones):
            out[ref] = zones
            _store(ref, blot)

        _rows, worker = _segment_pool(todo, n, root, model_path, device, decode,
                                      cfg, tick, reported, len(refs),
                                      on_done=_landed)
        reported += len(todo)
        if stats is not None and worker.get("stderr_lines"):
            stats.update(worker)
    elif todo:
        # Loaded here and nowhere else, so a fully cached run — the ordinary case
        # once a checkpoint has been scored once — never touches the GPU at all.
        net, _ = load_segmenter(model_path, root)
        for ref, blot in todo:
            out[ref] = _segment_page(blot, net, device, decode, ref, root, cfg)
            _store(ref, blot)
            _report(ref)

    if stats is not None:
        stats["cached"] = hits
        stats["workers"] = n
    return out


def score(root: Path = Path("."), cfg: dict | None = None,
          model_path: str | Path | None = None, decode: str = "dp",
          device: str = "auto", tick=None, jobs: int | None = None) -> dict:
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
        split_src = f"{DATADIR}/*.lst"
    if frozen is None:
        raise FileNotFoundError(
            f"no split for this model: neither a manifest beside it nor "
            f"{DATADIR}/train.lst. One of them has to say what the run trained on, "
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
                            if is_exempt(r, root, splits_now))
    both = sorted(candidates - set(skipped_exempt), key=parse_ref)

    cfg = cfg or zc.load_config(root)
    pred_stats: dict = {}
    preds = predicted_zones(both, root, cfg, model_path, decode, device, tick,
                            stats=pred_stats, jobs=jobs)

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
    for k in buckets:
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
            # How many of those pages came out of the checkpoint's prediction cache
            # instead of the segmenter. Reported because a cache nobody can see is a
            # cache nobody can trust — and because it is the difference between an
            # eleven-minute run and a five-second one, which the reader should be
            # told before they wonder which of the two just happened.
            "predictions_cached": pred_stats.get("cached", 0),
            # The exact set scored, so the independence report beside it is over
            # those pages and not over a re-derived list that could differ. Popped
            # by the CLI before the report is printed — a 700-ref string is not a
            # row anyone reads.
            "scored_refs": both,
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
                  commit: bool = False, device: str = "auto", tick=None,
                  jobs: int | None = None, decode: str = "dp") -> dict:
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

    # The score is a precondition of installing, not a cheaper preview: the
    # permutation refusal below is derived from it and the manifest embeds it. So a
    # preview run pays the full sweep too, and `tick` is what says so on screen.
    #
    # **`dp`, and named here rather than left to a default.** It scored `raw` for
    # as long as `score`'s *function* default was `raw` while the CLI's was `dp` —
    # so the numbers this verb printed, and wrote into the manifest, were the
    # model's undecoded ones (61.3% precision against 90.8% on identical weights)
    # and did not match what `harness train score zones` showed for the same checkpoint.
    # Nothing was wrong about the model; the manifest simply answered a different
    # question from the one anybody was asking, and said nothing about which.
    rep = score(root, cfg, model_path=checkpoint, device=device, tick=tick,
                jobs=jobs, decode=decode)
    perm = rep["permutation"]
    if perm["bijective"] and not perm["is_identity"] and perm["holds_out"] >= 90:
        raise ValueError(
            "refusing to install: the class map is permuted — a 1-1 relabelling "
            f"derived on the training pages predicts {perm['holds_out']}% of "
            "held-out zones, which means the geometry was learned and the names on "
            "the output channels are wrong. Run `--remap-model --commit` against "
            "this checkpoint first. See the train-zones skill, 'Diagnosing a "
            "permuted class map'.")

    dest_dir = root / MODELDIR
    rel = f"{MODELDIR}/{name}.safetensors"
    dest = root / rel
    kept = {f"{r['split']}/{r['counting']}":
            {"pages": r["pages"], "recall": r["recall"],
             "precision": r["precision"]}
            for r in rep["splits"] if r["pages"]}

    # The split is copied, not re-encoded — see `model_splits`.
    lists = {s: root / DATADIR / f"{s}.lst" for s in ("train", "eval")}
    missing = [s for s, p in lists.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"no {', '.join(missing)}.lst in {DATADIR} — the split this checkpoint "
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
        # **Which decoder the score below was taken with**, because the two differ
        # by ~30 points of precision and a figure that does not say which it is
        # cannot be compared with anything. The manifest is the model's own record;
        # a number in it whose method is unstated is the fluent nonsense this
        # project is organised against.
        "decode": decode,
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
    entry here would read as a missing page rather than as a stale link. The linking
    itself is `farms.rebuild`, shared with `recognize.link_view` — the two were
    line-for-line identical and each said in its docstring that it was the other's
    twin, which is a comment doing a function's job.

    The `from_gt`/`from_mz` split is the number worth reading: it is how much of the
    corpus is still only the machine's word. That part *is* this function's own —
    the shared mechanic counts links, not provenance.
    """
    gt = set(zone_refs(root, ZONEDIR))
    mz = set(zone_refs(root, MZDIR))
    wanted = {}
    for ref in sorted(gt | mz, key=parse_ref):
        store = ZONEDIR if ref in gt else MZDIR
        wanted[f"chukchi-{ref}.xml"] = alto_for(ref, root, store)

    rep = farms.rebuild(root / VIEWDIR, wanted, "chukchi-*.xml")
    return {"dir": rep["dir"], "from_gt": len(gt), "from_mz": len(mz - gt),
            "removed": rep["removed"]}


# --------------------------------------------------------- segtrain assembly

# Pure scratch. Nothing reads it once training has finished — the split a model
# trained on travels in that model's own manifest, not in a file here — so
# `--assemble` may clobber it freely and there is no "back up the lists first" step
# to remember. It used to be both the training input *and* the only record of what a
# past run consumed, which meant preparing a new run destroyed the ability to
# interpret the model you already had.
#
# The three paths come from `train.ZONES`, which is where the track record lives.
# The track's two halves, and the base holds neither: `data/` is what `assemble`
# lays out and what `ketos` reads — a raster link and an ALTO per page, plus the two
# `.lst` files naming them; `model/` is where the run writes its per-epoch
# checkpoints. They were one directory, and a thousand page links sat beside the
# lists and the run outputs with nothing but a suffix to tell them apart. Separated
# so a glob over the training set cannot pick up a checkpoint and clearing one half
# does not touch the other.
WORKDIR = train.ZONES.workdir
DATADIR = train.ZONES.datadir
RUNDIR = train.ZONES.rundir


def _write_merged(src: Path, dest: Path, merges: dict[str, str]) -> bool:
    """Copy a zone ALTO into the training set with `train_merges` applied — **if the
    fold touches this page at all.**

    Rewrites `OtherTag/@LABEL` only — the geometry, the ids and the `TAGREFS` are
    untouched, so what the segmenter sees is this page exactly as keyed but with two
    classes answering to one name. Two tags that collide after folding are left as
    two tags carrying the same label, which is what kraken's own merged-class support
    expects (`BaselineSet.merged_classes`: several strings, one index).

    Returns whether anything was folded — which is also **whether anything was
    written**, and the caller links the page instead when nothing was. A declared
    fold is a statement about the corpus, not about any given page: with
    `MainZone-Quote->MainZone-Other` declared and no page in the store carrying a
    `MainZone-Quote`, this wrote 717 copies to change nothing. A copy that is
    byte-identical to the store is not a safer copy — it is a second file that can
    silently fall behind the first, which is the thing the whole work dir is
    arranged to avoid.
    """
    tree = etree.parse(str(src))
    hit = False
    for tag in tree.iter(f"{{{ALTO_NS}}}OtherTag"):
        label = tag.get("LABEL")
        if label in merges:
            tag.set("LABEL", merges[label])
            hit = True
    if hit:
        tree.write(str(dest), xml_declaration=True, encoding="UTF-8")
    return hit


def assemble(root: Path = Path("."), scratch: bool = False,
             tick: Callable | None = None) -> dict:
    """Lay out `bogoras-seg/` for `ketos segtrain`, and report the invocation.

    ketos resolves a page's image through the ALTO's own
    `sourceImageInformation/fileName`, relative to the XML — so the zone file and
    its **blotted** raster have to sit in one directory under the name the ALTO
    already carries. Both are symlinked — except the ALTO of a page `train_merges`
    actually folds, which is a copy because it has to differ from the store.

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

    Output goes to `bogoras-seg/model/`, not `models/`: segtrain writes a checkpoint
    per epoch, and this repo keeps only the trained model, in `models/`, by hand. The
    training set it reads is `bogoras-seg/data/`, and the two never share a
    directory — a run's checkpoints and its input are cleared on different occasions.
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
    work = root / DATADIR
    work.mkdir(parents=True, exist_ok=True)
    # The run directory, made here rather than left to `ketos -o`: kraken creates the
    # output directory it is given but not its parents, and the reported command is
    # meant to run as printed.
    (root / RUNDIR).mkdir(parents=True, exist_ok=True)
    counts = {"train": 0, "eval": 0}
    missing: list[str] = []
    listed: dict[str, list[str]] = {"train": [], "eval": []}
    merged_pages = 0

    # **Counted from the marks, not from the store.** A plate is neither an example
    # of the layout nor a fair test of it, so it goes into neither list — and the
    # count has to survive, because "a set that shrank without saying so would look
    # like pages that were never keyed" is the whole reason it is reported. Under
    # `exempt => no zones` a ruled leaf holds no file at all, so counting the
    # skips inside the loop below silently reported nought held out where 115 were.
    exempted = sum(1 for v in splits.values() if v in LEAF_KINDS)
    for ref in ptrack(zone_refs(root), tick):
        split = splits.get(ref, DEFAULT_SPLIT)
        # Still guarded, for the page that drifted into holding both a ruling and a
        # file — `zones check` errors on it as `exempt-holds-zones`, and until it is
        # repaired it must not reach a training list.
        if split in LEAF_KINDS:
            continue
        alto = alto_for(ref, root)
        blot = blot_dir(root) / f"chukchi-{ref}.png"
        if not blot.exists():
            missing.append(ref)
            continue
        # The raster is always a link — it is identical to what is in the store.
        # The ALTO is a copy **only on a page the fold actually changes**, since
        # that page has to differ from `gt/zones/` in exactly one respect and the
        # store must not learn of it; writing through a symlink there would edit the
        # ground truth, which is the failure this repo has already paid for once.
        # Every other page is a link, whether or not a fold is declared: a declared
        # fold that no page carries produced 717 copies of files identical to the
        # store, and an identical copy is not a safer one.
        for target, name in ((alto, f"chukchi-{ref}.xml"),
                             (blot, f"chukchi-{ref}.png")):
            link = work / name
            if link.is_symlink() or link.exists():
                link.unlink()
            if merges and target is alto and _write_merged(target, link, merges):
                merged_pages += 1
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
        listed[split].append(f"{DATADIR}/chukchi-{ref}.xml")
        counts[split] += 1

    for split in ("train", "eval"):
        (work / f"{split}.lst").write_text(
            "".join(p + "\n" for p in sorted(listed[split])), encoding="utf-8")

    classes = sorted({merges.get(z["label"], z["label"])
                      for ref in zone_refs(root)
                      if splits.get(ref, DEFAULT_SPLIT) not in LEAF_KINDS
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
                work=DATADIR, out=f"{RUNDIR}/{train.next_run(train.ZONES, root)}",
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
