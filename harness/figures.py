"""The figure-caption track: `gt/fig/` for the geometry **and** the text.

**One store.** The 252 figure ALTOs carry `GraphicZone` blocks (the images) and
`GraphicZone-FigDesc` blocks (where a caption sits) — 414 and 395 of them — and
each FigDesc block carries the adjudicated caption as one `String` per printed
line inside one `TextLine`. `readings()` reads them back; `save_caption_text`
writes them, out of `review/captions/decision.json` over `proposal.json`.

**It was two stores, and that is worth remembering rather than deleting.** The
text lived in `data/readings.md`, keyed `<ref>|<zone-id suffix>`, because the
exported line segmentation had dropped whole printed lines and a line-level
witness in the ALTO would have silently disagreed with the readings. The blind
re-read pass settled that, `fig restore` moved the ratified text into the block
that carries the caption's own geometry — and the markdown was left in place,
still being read by every consumer. The two then drifted: **58 of 395 captions
disagreed**, the store holding the adjudication and the edition serving the
markdown, with nothing anywhere reporting it. The file is gone and the key is now
the block id, which is the same key filed where the thing it names lives.

So `String/@CONTENT` out of `gt/fig/` is the caption, and `block_text` is how to
read it — a list of printed lines, never joined here, because 31 of the 196
multi-line captions break on a hyphen and only some of those hyphens are the
book's.

A caption's reasoning is **not** in this store. What the reader said about a
caption lives in `review/captions/proposal.json` and `decision.json`, which is
also where the two readings of it can still be compared.

Zone types are read from `OtherTag/@LABEL`, never from the tag ID. The IDs are
per-export (`BT55`/`BT56` in one export, `BT68`/`BT69` in the next) and code
that hardcodes them fails silently rather than loudly.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import NotRequired, TypedDict

import numpy as np
from lxml import etree

from . import paths, provenance, train
from .atomic import tmp_for, write_atomic
from .refs import figure_number, norm_ref, parse_ref
from .scans import PDF_IMAGES, pdf_images, pdf_images_for
from .scans import rects_in as _scans_rects_in

GRAPHIC = "GraphicZone"
FIGDESC = "GraphicZone-FigDesc"

# Under `gt/` because the figure track is human-reviewed throughout: all 395 captions
# were read by hand off the 300 dpi scans, and the zone geometry was corrected by hand
# until `reconcile()` came back empty in both directions. It sits beside `gt/ocr/` and
# `gt/seg/` for the same reason they do — `gt/` is what a human has been through, and a
# store's rank should be readable from where it lives rather than from a doc that says
# so. It was a bare top-level `fig/` while that was still an open question.
FIGDIR = "gt/fig"

# What the segmenter emitted, raw, on the `mz/zones/` model: derived, ignored, and
# never a substitute for the human file. There is deliberately **no read view** over
# the pair the way `zones/` covers `gt/zones` and `mz/zones`. Every consumer of
# figure geometry — `zones.blot_one`, `lines.figure_boxes`,
# `context._figures_on_page`, `dispatch.survey` — names `gt/fig` directly, and the
# one thing a view would buy is the one thing that must not happen: `zones blot`
# painting `scans/w-figs-blotted/` from *machine* figure claims and the zone
# segmenter then training on them. A proposal reaches a human through the editor,
# which asks, or not at all.
MZFIGDIR = "mz/fig"
READINGS = "data/readings.md"

#: The version the **derived rasters** stamp into their provenance — the blots,
#: the crops, the numbered page and the contact sheets, in this module and in
#: `lines.py`. One constant for all of them because they are one act at four
#: sizes: cover or cut what is accounted for, and hand the rest to a human to
#: ratify against. Bump it when what any of them draws changes; a file written
#: before the change is then detectable, and a constant nobody moves is the same
#: as no constant at all.
#:
#: Here rather than in `lines.py` because `lines` imports this module and not the
#: reverse, and both write these files.
RASTER_VERSION = 1

#: The version `fig propose` stamps into an `mz/fig/` page's provenance. Bump it
#: when the rule that turns a manifest entry into a block changes — the point of
#: recording it is that a page written before the change is *detectable*, and a
#: constant nobody moves is the same as no constant at all.
PROPOSE_VERSION = 1


#: The rule id `fig check` reports an unaccounted photograph under, and the key a
#: page excuses it by in `gt/fig/_rule_exempt.json`. Declared in
#: `data/zones_config.json` under `figures.rules` so that `unknown-exemption`
#: catches a typo in the excuse rather than letting it read as a judgement.
UNACCOUNTED_RULE = "unaccounted-picture"

#: Its non-gating companion: how much of a photo's rect falls outside every keyed
#: picture. Reported and never gated — a rect legitimately spans the part-boxes of
#: one lettered figure, and the gutter between them belongs to no box.
OUTSIDE_RULE = "picture-outside-boxes"

#: Share of a rect's area outside the keyed boxes above which `OUTSIDE_RULE` fires.
OUTSIDE_SHARE = 0.05

#: Slack when measuring how much of a photo's rect lies outside the keyed boxes.
#: The rect sits proud of a human's box by 1-3 px at the median and 11-18 at p95,
#: so this is set above that: the measure is meant to find a *region* nobody keyed,
#: not to relitigate where an edge was drawn.
UNACCOUNTED_PAD = 20


def zone_suffix(block_id: str) -> str:
    """The part of a block id the caption on it is filed under.

    Two id schemes exist and this reads both: eScriptorium's
    `eSc_textblock_ca04178c` and this project's `fig_1-037_002`. Taking the last
    underscore-delimited field rather than a fixed slice is what lets the two
    coexist while the store migrates, and it is why the migration could land the
    helper first and the files second.

    The suffix is a **foreign key**, which is the whole reason `save_figs` will not
    re-mint ids positionally the way `zones.save_zones` does: there, nothing points
    at a zone id; here, 395 reading blocks do.
    """
    return (block_id or "").rsplit("_", 1)[-1]


def crop_keys(fig: dict) -> list[str]:
    """Every crop one figure is spelt in, as `ref/key`'s key half.

    **A figure is not a box.** 16 of this store's figures are drawn in two — the
    print letters them *a* and *b* under a single caption, and `1-123`'s Plate V
    sets two pictures with one caption and no number at all. `key` is the first
    of those boxes and is the figure's identity, which is right for keying a
    reading and wrong for showing the thing: a card built from `key` alone drew
    Plate V as one picture and silently dropped the other.

    Falls back to `key` where a record carries no `zone_ids`, so a hand-built
    fixture or an older shape still resolves to something rather than to nothing.
    """
    return [zone_suffix(z) for z in fig.get("zone_ids") or []] or (
        [fig["key"]] if fig.get("key") else [])


def _labels(tree) -> dict[str, str]:
    return {t.get("ID"): t.get("LABEL", "") for t in tree.iter("{*}OtherTag")}


def _block_label(blk, labels: dict[str, str]) -> str:
    """First non-empty zone label on a block. TAGREFS is space-separated."""
    for r in (blk.get("TAGREFS") or "").split():
        if labels.get(r):
            return labels[r]
    return ""


def _bbox(el) -> dict | None:
    """HPOS/VPOS/WIDTH/HEIGHT as ints.

    Parsed as float first: eScriptorium writes these as `"365.0"`, which is not
    `str.isdigit()`. Assuming otherwise is how `context._figures_on_page` came
    to hand the model an empty bbox for all 250 pages.
    """
    vals = {}
    for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"):
        v = el.get(k)
        if v is None:
            return None
        try:
            vals[k] = round(float(v))
        except ValueError:
            return None
    return vals


# The two rectangle shapes this project carries, and the conversion between them.
#
# **They are two spellings of one thing and both are load-bearing.** ALTO stores
# a box as origin-plus-extent (`HPOS/VPOS/WIDTH/HEIGHT`), which is what
# `read_blocks` returns unchanged because the store is the record. Every
# *geometric* consumer wants corners, because overlap and containment are
# comparisons of edges — so `zones.read_zones` converts, and so does
# `zones_ui`, and so does this module in four places.
#
# `to_rect` is that conversion, once. It was written out inline at three sites
# and the arithmetic appears at **eighteen** in all; collapsing the three that
# build a rect record is what this does, and the other fifteen are expressions
# in the middle of larger comparisons that want the guard question answered
# first (see `LineRec`'s note on `int | None` geometry).
BLOCK_FIELDS = ("id", "label", "hpos", "vpos", "width", "height")
RECT_FIELDS = ("id", "label", "x0", "y0", "x1", "y1")


class Block(TypedDict):
    """A block as ALTO stores it: origin and extent.

    `with_points=True` adds `points`, which is why this is `total=False`-adjacent
    in spirit — the key is genuinely optional and declared `NotRequired` rather
    than stamped `None`, unlike `LineRec`'s figure keys. The difference is the
    consumer: these records are not emitted as a TOON table, so a ragged key set
    costs nothing here and pretending otherwise would be cargo-culting the line
    record's constraint into a place that does not have it.
    """
    id: str
    label: str
    hpos: int
    vpos: int
    width: int
    height: int
    points: NotRequired[str | None]


class Rect(TypedDict):
    """The same box as corners, which is what every overlap test wants."""
    id: str
    label: str
    x0: int
    y0: int
    x1: int
    y1: int
    points: NotRequired[str | None]


def to_rect(b, with_points: bool = False) -> dict:
    """One `Block` as a `Rect`. The conversion, in one place.

    Three sites built this dict literally and identically — `zones.read_zones`,
    `zones_ui`, and `save_figs` here — which is the shape `crop_name`'s rule
    names: one function where several callers must agree exactly.
    """
    rec = {"id": b["id"], "label": b["label"],
           "x0": b["hpos"], "y0": b["vpos"],
           "x1": b["hpos"] + b["width"], "y1": b["vpos"] + b["height"]}
    if with_points:
        rec["points"] = b.get("points")
    return rec


def read_blocks(path: Path, with_points: bool = False) -> list[dict]:
    """Every `TextBlock` in any ALTO here: `{id, label, hpos, vpos, width, height}`.

    **The one reader of this encoding**, and it is store-agnostic on purpose —
    `zones()` below binds it to `gt/fig/`, `zones.py` binds it to `gt/zones/`, and
    neither walks the tree itself. Four callers now depend on the two properties
    below, and four independent walks is precisely the drift that produced three
    near-identical lookalike tables.

    Zone type comes from `OtherTag/@LABEL` via `TAGREFS`, **never from the tag ID**:
    eScriptorium assigns those per export (`BT55`/`BT56` in one, `BT68`/`BT69` in
    the next), so code that hardcodes them fails silently rather than loudly.
    It cost a migration once, which "quietly became a no-op that reported
    success" — `git log -- tools/strip_graphiczone_lines.py` for the script that
    did it and the docstring that recorded why.

    A missing file returns `[]` rather than raising: absence is the ordinary case
    for both stores it serves — 580 of the 832 pages have no figure ALTO, and the
    zone store starts empty.

    Flat scalars, not a nested `bbox`: a nested value de-tabularizes the whole TOON
    table, which is exactly why the page context currently emits in the verbose
    form (see `lines.py`'s module docstring).

    `with_points` adds the block's raw `Shape/Polygon@POINTS` string, and is off by
    default so that every existing caller's record shape is untouched — the field
    would otherwise surface as noise in `harness tei context`'s figure list. The one
    caller that wants it is `zones.validate_page`, which has to know whether a block
    is really the rectangle its bbox implies; asking here keeps this the only walk
    of the encoding rather than buying that one check a second one.
    """
    if not Path(path).exists():
        return []
    tree = etree.parse(str(path))
    labels = _labels(tree)
    out = []
    for blk in tree.iter("{*}TextBlock"):
        bb = _bbox(blk)
        if bb is None:
            continue
        rec = {"id": blk.get("ID"), "label": _block_label(blk, labels),
               "hpos": bb["HPOS"], "vpos": bb["VPOS"],
               "width": bb["WIDTH"], "height": bb["HEIGHT"]}
        if with_points:
            poly = blk.find("{*}Shape/{*}Polygon")
            rec["points"] = "" if poly is None else (poly.get("POINTS") or "")
        out.append(rec)
    return out


def zones(ref: str, root: Path = Path("."), store: str = FIGDIR,
          with_points: bool = False) -> list[dict]:
    """Every declared zone on one page of the **figure** track.

    Three callers need exactly this — `context._figures_on_page` (to hand the model
    figure geometry and its caption), `lines.line_gaps` (to mask figures out of the
    dropped-line detector), and `lines`' caption-line marking. The walk itself is
    `read_blocks`; what this adds is the binding to `gt/fig/`, which is the part a
    caller must not have to know.

    `store` defaults to the human file, so a caller that does not ask cannot be
    handed a machine proposal. `with_points` forwards to `read_blocks` for
    `validate_fig_page`, which has to know whether a block really is the rectangle
    its bbox implies — the same question `zones.validate_page` asks of its own store.
    """
    return read_blocks(alto_for(ref, root, store), with_points=with_points)


def fig_refs(root: Path = Path("."), store: str = FIGDIR) -> list[str]:
    """Every ref with a figure-track ALTO, in (part, scan index) order."""
    refs = []
    for p in (root / store).glob("chukchi-*.xml"):
        try:
            refs.append(norm_ref(p.stem))
        except ValueError:
            continue
    return sorted(set(refs), key=parse_ref)


def alto_for(ref: str, root: Path = Path("."), store: str = FIGDIR) -> Path:
    return root / store / f"chukchi-{norm_ref(ref)}.xml"


def fig_dir(root: Path = Path("."), store: str = FIGDIR) -> Path:
    return root / store


# --- the store's own sidecars ----------------------------------------------
#
# All four live in `gt/fig/` and none is shared with `gt/zones/`. The two stores
# answer different questions about the same page, and an exemption filed against
# one of them says nothing about the other: this repo has already paid once for a
# single exemption file serving two domains, where a band ruled "not type" for the
# line checker also silenced the zone checker and a dropped folio went unseen.
# Two files that look redundant until the day they are not.
TRAIN_LST = "_train.lst"
EVAL_LST = "_eval.lst"

# Two splits, not the zone store's three. `exempt` there means "a human ruled this
# not a text page" — plates, maps, blanks — and that is a statement about the text
# column, which the figure track does not care about. Plates are where figures
# *live*: exempting them here would hold out exactly the pages worth training on.
FIG_SPLITS = ("train", "eval")

RULE_EXEMPT_JSON = "_rule_exempt.json"
JOURNAL = "_journal.jsonl"
DEFAULT_SPLIT = "train"


def _lst_path(root: Path, split: str, store: str = FIGDIR) -> Path:
    return fig_dir(root, store) / {"train": TRAIN_LST, "eval": EVAL_LST}[split]


def _read_lst(p: Path) -> list[str]:
    if not p.exists():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def load_splits(root: Path = Path("."), store: str = FIGDIR) -> dict[str, str]:
    """`{ref: "train"|"eval"}` over the two lists, `eval` winning a contradiction.

    **A listed ref need not name an existing file.** The lists carry the negatives
    too — pages a human went through in the zone track and found no figure on —
    and a negative is precisely a ref with no `gt/fig/` ALTO. `assemble` is what
    synthesizes the empty region set at training time; the store never holds one,
    because an empty figure ALTO on disk would tell `dispatch.survey` the page has
    figures and tell `zones blot` to repaint a raster for nothing.
    """
    rank = {"train": 0, "eval": 1}
    out: dict[str, str] = {}
    for split in FIG_SPLITS:
        for name in _read_lst(_lst_path(root, split, store)):
            try:
                ref = norm_ref(Path(name).stem.replace("chukchi-", ""))
            except ValueError:
                continue
            if ref not in out or rank[split] > rank[out[ref]]:
                out[ref] = split
    return out


def set_split(ref: str, split: str, root: Path = Path("."),
              store: str = FIGDIR) -> dict:
    """Put this page in exactly one of the two lists, removing it from both first."""
    if split not in FIG_SPLITS:
        raise ValueError(
            f"split must be one of {', '.join(FIG_SPLITS)}, not {split!r}")
    ref = norm_ref(ref)
    name = f"chukchi-{ref}.xml"
    fig_dir(root, store).mkdir(parents=True, exist_ok=True)
    for which in FIG_SPLITS:
        p = _lst_path(root, which, store)
        entries = [e for e in _read_lst(p) if e != name]
        if which == split:
            entries.append(name)
        entries = sorted(set(entries),
                         key=lambda e: parse_ref(
                             Path(e).stem.replace("chukchi-", "")))
        write_atomic(p, "".join(e + "\n" for e in entries))
    return {"ref": ref, "split": split}


def load_rule_exempt(root: Path = Path("."),
                     store: str = FIGDIR) -> dict[str, dict[str, str]]:
    """`{ref: {rule_id: the ruling}}` — which warnings a page has been ruled on.

    **The note is the file**, not decoration on it. `zones.set_ink_exempt` says so
    outright for the ink ledgers — "a reason is required and is the point of the
    file" — and this store spent longer than it should have holding bare rule ids,
    which records that somebody silenced a warning and nothing about why. A reader
    then cannot tell a considered ruling from a keystroke.

    A legacy `[rule, ...]` list still loads, mapping to empty notes rather than
    being dropped: the exemptions are real even where their reasons were never
    written down. `validate_fig_page` reports an empty one as *unruled* so the gap
    is visible instead of inherited.
    """
    p = fig_dir(root, store) / RULE_EXEMPT_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for ref, v in data.items():
        if ref.startswith("_"):
            continue
        if isinstance(v, dict):
            out[ref] = {str(k): str(n or "") for k, n in v.items()}
        else:
            out[ref] = {str(r): "" for r in v}
    return out


RULE_EXEMPT_ABOUT = (
    "Figure-track warnings a human has ruled on, per page, each with the reason. "
    "An exempted rule STILL REPORTS, flagged and carrying its note — a warning "
    "that vanished when excused would leave no way to notice the excuse had "
    "outlived the page it was written for. An entry with an empty note is an "
    "exemption nobody wrote a reason for, and `fig check` says so."
)


def set_rule_exempt(ref: str, rules, root: Path = Path("."),
                    store: str = FIGDIR, require_note: bool = True) -> dict:
    """Record which warnings a human has accepted on this page, and why.

    `rules` is `{rule_id: note}`. A list is accepted for the legacy shape and, with
    `require_note`, refused — because that is exactly the call that loses the
    reason. An exempted rule **still reports**, flagged: a warning that vanishes
    when excused leaves no way to notice that the excuse has outlived the page it
    was written for.
    """
    ref = norm_ref(ref)
    if not isinstance(rules, dict):
        rules = dict.fromkeys(rules or [], "")
    blank = sorted(r for r, note in rules.items() if not str(note).strip())
    if blank and require_note:
        raise ValueError(
            f"{ref}: no reason given for {', '.join(blank)}. An exemption without "
            "one records that somebody silenced a warning and nothing about why; "
            "see gt/fig/_rule_exempt.json's _about.")
    data = load_rule_exempt(root, store)
    if rules:
        data[ref] = {r: str(rules[r]) for r in sorted(rules)}
    else:
        data.pop(ref, None)
    p = fig_dir(root, store) / RULE_EXEMPT_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"_about": RULE_EXEMPT_ABOUT}
    doc.update({k: data[k] for k in sorted(data, key=parse_ref)})
    write_atomic(p, json.dumps(doc, indent=2, sort_keys=False,
                               ensure_ascii=False) + "\n")
    return {"ref": ref, "rules": data.get(ref, {})}


# ---------------------------------------------------------- the segmenter
#
# The zone track's quartet, mirrored, with one difference that decides everything
# else: **this model trains on the raw `scans/`**, where zones-seg trains on
# `scans/w-figs-blotted/`. It has to — the blot paints figures white, and a figure
# segmenter cannot learn from pages where its target has been erased. That is also
# why the two are separate models rather than one with four classes: they read
# different rasters.
#
# All from `train.FIG`, which is where the track record lives. `zones`' split of
# the track, verbatim: `data/` is the laid-out training set and its two `.lst`
# files, `model/` holds a run's checkpoints, and the base holds neither.
WORKDIR = train.FIG.workdir
DATADIR = train.FIG.datadir
RUNDIR = train.FIG.rundir
MODELDIR = train.FIG.modeldir
MODEL_NAME = train.FIG.model_name
DEFAULT_MODEL = train.FIG.default_model


def negative_refs(root: Path = Path(".")) -> dict[str, list[str]]:
    """Pages witnessed to have no figures, and the ones nothing can say about.

    A negative is **a keyed, non-exempt page whose ink check is clean, with no ink
    exemptions and no `gt/fig/` file**. Each clause is load-bearing:

    - *keyed and non-exempt*: an exempt page has no zones, so the ink check never
      ran over it. Exempt pages are plates — exactly where figures live — so
      treating them as negatives would train the model that plates are empty.
      (Exemption disqualifies a page from being a *negative* only; an exempt plate
      that carries a `gt/fig/` file is an ordinary positive and trains.)
    - *ink check clean*: this is the witness. Every band of ink on the page is
      accounted for by text zones alone, so there is nothing left for a figure to
      be. `1-191` is the proof it works — that check, and not exemption status, is
      what exposed its undeclared photograph.
    - *no ink exemptions*: a band ruled `not_type` makes the check read clean while
      hiding exactly the ink a figure would be. Such a page is **unknown**, not
      negative.

    Returns `{"negative": [...], "unknown": [...]}`, and the second list is the
    point. The verdicts come from `gt/zones/_ink_cache.json`, which is derived and
    gitignored, and a stale or absent entry reads *unknown* rather than clean — on
    a cold cache that is every page in the corpus. A caller that quietly trained on
    whatever negatives it happened to find would look exactly like a caller with a
    small corpus, so the count of unknowns is returned to be reported.
    """
    from . import zones as zn

    splits = zn.load_splits(root)
    negative, unknown = [], []
    for ref in zn.zone_refs(root):
        if zn.is_exempt(ref, root, splits) or alto_for(ref, root).exists():
            continue
        # `cached_ink` returns None for a stale or absent verdict rather than the
        # stale record — the distinction this store needs, already drawn there.
        # And the cache's own four states already separate `clean` from `ruled`,
        # so the no-exemptions clause is read off the verdict rather than
        # re-derived from `_ink_exempt.json` beside it.
        hit = zn.cached_ink(ref, root)
        (negative if hit and hit.get("state") == "clean" else unknown).append(ref)
    return {"negative": negative, "unknown": unknown}


def remark_eval(root: Path = Path("."), fraction: float = 0.20,
                commit: bool = False) -> dict:
    """Mint or extend the figure track's train/eval split.

    The universe is the positives (every page with a `gt/fig/` ALTO, exempt ones
    included — a plate carrying figures is the best training page there is) plus
    the witnessed negatives from `negative_refs`.

    **Additive: a mark a human made is never moved.** Held out has to stay held
    out, or the eval set drifts with whatever was keyed most recently and stops
    being a held-out set at all.

    Stratified per part and spread rather than taken from the front, so the eval
    set is not the first fifth of part 1 — `zones._spread` is the same picker the
    zone track uses, for the same reason.

    Reports `unknown` prominently. Those pages are neither trained on nor scored,
    and on a cold `_ink_cache.json` that is every page in the corpus; a run that
    quietly produced a small split would look exactly like a small corpus.
    """
    from .zones import _spread

    seen = load_splits(root, FIGDIR)
    neg = negative_refs(root)
    universe = sorted(set(fig_refs(root)) | set(neg["negative"]), key=parse_ref)
    fresh = [r for r in universe if r not in seen]

    by_part: dict[str, list[str]] = {}
    for r in fresh:
        by_part.setdefault(r.split("-")[0], []).append(r)
    picked: set[str] = set()
    for _part, refs in by_part.items():
        k = int(round(len(refs) * fraction))
        picked.update(_spread(refs, k))

    plan = {r: ("eval" if r in picked else "train") for r in fresh}
    out = {
        "positives": len(fig_refs(root)),
        "negatives": len(neg["negative"]),
        "unknown": len(neg["unknown"]),
        "already_marked": len(seen),
        "newly_marked": len(plan),
        "to_eval": sum(1 for v in plan.values() if v == "eval"),
        "committed": commit,
    }
    if neg["unknown"]:
        out["note"] = (
            f"{len(neg['unknown'])} pages have no usable ink verdict and are "
            "neither trained on nor scored — a page is a witnessed negative only "
            "when its ink check is clean and unexcused. Run `harness zones check "
            "--all --ink` if the cache is cold; "
            + " ".join(neg["unknown"][:8]))
    if not commit:
        out["preview"] = "nothing written — pass --commit"
        return out
    for ref, split in plan.items():
        set_split(ref, split, root)
    return out


def assemble(root: Path = Path("."), scratch: bool = False) -> dict:
    """Lay out `train/bogoras-fig/data/` for `ketos segtrain`, and report the command.

    ketos resolves a page's image through the ALTO's own
    `sourceImageInformation/fileName`, relative to the XML, so each page's file and
    its raster sit together under the name the ALTO already carries.

    **The raster is the raw `scans/` page, never the blot.** `train assemble zones` links
    `scans/w-figs-blotted/` because the zone segmenter must not learn figure-shaped
    body zones; here the blot paints the target white, so training on it would be
    asking the model to find something that has been erased.

    **A negative page's ALTO is synthesized here and stored nowhere.** `gt/fig/`
    never holds an empty file — absence is how it records "no figures", and every
    reader takes an existing file as "this page has figures". Verified against
    kraken 7.0.3: an empty region ALTO parses to a `baselines` container with no
    regions and `BaselineSet.add` accepts it as a page with none, which is what
    teaches the model that most pages are empty.
    """
    from .zones import SEGTRAIN_CMD, _runtime_flags, build_alto, raster_size

    work = root / DATADIR
    for p in sorted(work.glob("*")) if work.exists() else []:
        if p.is_file() or p.is_symlink():
            p.unlink()
    work.mkdir(parents=True, exist_ok=True)
    # See `zones.assemble`: kraken makes the output directory it is given, not its
    # parents, and the reported command has to run as printed.
    (root / RUNDIR).mkdir(parents=True, exist_ok=True)

    splits = load_splits(root, FIGDIR)
    lists: dict[str, list[str]] = {"train": [], "eval": []}
    positives = synthesized = 0
    missing: list[str] = []
    for ref, split in sorted(splits.items(), key=lambda kv: parse_ref(kv[0])):
        scan = paths.scan_for(ref, root)
        if not scan.exists():
            missing.append(ref)
            continue
        name = f"chukchi-{ref}"
        img = work / f"{name}.png"
        if not img.exists():
            img.symlink_to(scan.resolve())
        xml = work / f"{name}.xml"
        src = alto_for(ref, root)
        if src.exists():
            if not xml.exists():
                xml.symlink_to(src.resolve())
            positives += 1
        else:
            build_alto(ref, [], raster_size(ref, root), id_prefix="fig_").write(
                str(xml), xml_declaration=True, encoding="UTF-8",
                standalone=None, pretty_print=True)
            synthesized += 1
        # Relative and unresolved. Resolving follows the symlink back to `gt/fig/`
        # and silently trains on the store instead of the work dir — the lesson
        # `zones.assemble` records, and it applies verbatim.
        lists[split].append(f"{DATADIR}/{name}.xml")

    for split, names in lists.items():
        (work / f"{split}.lst").write_text(
            "".join(n + "\n" for n in names), encoding="utf-8")

    device, workers = _runtime_flags()
    base_note = ""
    if scratch:
        load, base = "", "scratch (asked for)"
    elif (root / DEFAULT_MODEL).exists():
        # Fine-tuning this project's own figure model: the class map is already
        # right, so no `--resize`, which is what permutes an output layer.
        load, base = f" -i {DEFAULT_MODEL}", DEFAULT_MODEL
    elif (root / "models" / "blla.mlmodel").exists():
        load, base = " -i models/blla.mlmodel --resize new", "models/blla.mlmodel"
    else:
        # Says so rather than quietly emitting a from-scratch command. Fine-tuning
        # and training from random init are different experiments, and the one
        # that arrives by a missing file is the one nobody chose.
        load, base = "", "scratch (no base model found)"
        base_note = ("no models/blla.mlmodel and no installed figure model, so "
                     "the reported command trains from random init — pass "
                     "--scratch to mean that deliberately")
    out = {
        "work": str(work), "train": len(lists["train"]), "eval": len(lists["eval"]),
        "positives": positives, "negatives": synthesized,
        "base": base,
        "missing_raster": missing,
        "command": SEGTRAIN_CMD.format(
            device=device, workers=workers, load=load, work=DATADIR,
            out=f"{RUNDIR}/{train.next_run(train.FIG, root)}"),
    }
    notes = [n for n in (base_note,
                         "pages with no raster were left out of both lists"
                         if missing else "") if n]
    if notes:
        out["note"] = "; ".join(notes)
    return out


def predict(refs: list[str], root: Path = Path("."),
            model_path: str | Path | None = None, device: str = "auto",
            force: bool = False, tick=None) -> list[dict]:
    """Run the figure segmenter over pages and write raw ALTO into `mz/fig/`.

    Input is the **raw scan**, matching what the model was trained on and unlike
    `zones predict`, which reads the blot. **No exempt skip**: plates are exempt in
    the zone track and are exactly where figures live.

    `--force` to overwrite, because an `mz/` file's `ProcessingStep` is the store's
    only witness to which model wrote it, and quietly replacing one loses that.
    """
    from .zones import load_segmenter

    model_path = model_path or DEFAULT_MODEL
    # `load_segmenter` takes `(model_path, root)` and returns `(net, sha256)`.
    # Handing it the device put that string in the `root` slot — so the model
    # resolved under `auto/` and the sha came back as the device, which reached
    # `blla.segment` and the ProcessingStep below. `zones.predict_dp` resolves
    # `auto` for the same reason; nothing here ever did.
    if device == "auto":
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    from .parallel import ptrack

    net, sha = None, ""
    out = []
    # Every ref counts, the skips included: `--all` is 832 pages at ~15 s each and
    # the total a reader needs is the one they asked for, not the one left after
    # the run has quietly discounted itself.
    for ref in ptrack(refs, tick):
        ref = norm_ref(ref)
        dest = alto_for(ref, root, MZFIGDIR)
        scan = paths.scan_for(ref, root)
        if not scan.exists():
            out.append({"ref": ref, "wrote": False, "note": "no raster"})
            continue
        if dest.exists() and not force:
            out.append({"ref": ref, "wrote": False, "note": "exists; --force"})
            continue
        if net is None:
            net, sha = load_segmenter(model_path, root)
        out.append(_predict_one(ref, root, net, device, model_path, sha, dest))
    return out


def _predict_one(ref, root, net, dev, model_path, sha, dest) -> dict:
    from kraken import blla
    from PIL import Image

    from .zones import build_alto

    with Image.open(paths.scan_for(ref, root)) as s:
        page = s.convert("RGB")
    seg = blla.segment(page, model=net, device=dev)
    blocks = [{"label": label,
               "x0": min(p[0] for p in g.boundary),
               "x1": max(p[0] for p in g.boundary),
               "y0": min(p[1] for p in g.boundary),
               "y1": max(p[1] for p in g.boundary)}
              for label, group in (seg.regions or {}).items()
              for g in group if label in (GRAPHIC, FIGDESC)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    tree = build_alto(ref, blocks, page.size, id_prefix="mzfig_")
    # The witness to which model wrote this. Without it an `mz/` file is a claim
    # with no provenance, and the store's whole value is that it is separable from
    # anybody's judgement.
    #
    # **`kind="model"` is the half that was missing**, not the model path. This
    # wrote a bare `f"{model_path} sha256:… device:…"` into the description and
    # nothing else, so a `predict` page and a `propose` page — a segmenter's guess
    # and the scanner's own MRC segmentation — were two free-text strings that no
    # reader could tell apart without matching prose. `train score fig --model M` is the
    # bug that grew in that gap.
    desc = tree.getroot().find("{*}Description")
    desc.append(provenance.alto_processing(provenance.Producer(
        step="harness fig predict", label="figure segmentation",
        kind="model", version=provenance.kraken_version(),
        model=str(model_path), sha256=sha, device=dev,
        # **The raw scan, and naming it is not decoration.** The zone segmenter
        # reads `scans/w-figs-blotted/`, where this model's target is painted
        # white; the two models read two rasters and neither can be folded into
        # the other. A file that records which one it was read off is a file that
        # can be told from one produced by the other track.
        inputs={"raster": f"scans/chukchi-{ref}.png"})))
    tmp = tmp_for(dest)
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
               standalone=None, pretty_print=True)
    tmp.replace(dest)
    return {"ref": ref, "wrote": True,
            "figures": sum(1 for b in blocks if b["label"] == GRAPHIC),
            "captions": sum(1 for b in blocks if b["label"] == FIGDESC)}


def propose_from_pdf(refs: list[str], root: Path = Path("."),
                     force: bool = False,
                     tick: Callable | None = None) -> list[dict]:
    """Write `mz/fig/` proposals from the source PDF's own image placements.

    `predict` writes the same store from the figure segmenter. This writes it from
    the scanner's MRC segmentation — the decision, taken when the book was
    digitised, about which pixels were photograph and which were type. It is not a
    better model; it is a **different kind of witness**, and the store is where a
    claim nobody has examined belongs either way.

    **`GraphicZone` only.** The PDF layer says where a *picture* is and says nothing
    whatever about captions, so minting a `GraphicZone-FigDesc` here would be
    authoring a claim the source does not make — the one thing a proposal must not
    do, since what reaches `gt/fig/` is painted into the rasters the zone segmenter
    trains on.

    Refuses to overwrite a page `predict` wrote unless `force`, and says so. The two
    are not interchangeable and an `mz/` file's processing step is the only record
    of which one spoke.

    On **this** book it proposes nothing anyone needs: all 371 photographs sit on
    pages `gt/fig/` already covers, and `zones_ui._fig_state` shows `mz/fig/` only
    where `gt/fig/` is absent, so every proposal here is correctly invisible. It
    earns its keep on the next book, where it is the first pass rather than a
    second opinion — and here as the input to `fig extend`.

    **Writes master-space coordinates**, which is the manifest's space and the one
    the rasters are moving to, and declares it in the `Page` box as every store
    here does. Until `scans/` is rebuilt that is *not* the space `gt/fig/` is in,
    so a proposal written today and read today would sit up to 35 px out. Nothing
    reads one today — no page in this book has an `mz/fig/` file without a `gt/fig/`
    file to outrank it — but that is a fact about this corpus rather than a
    guarantee, so run this after the migration and not before.
    """
    from .parallel import ptrack
    from .zones import build_alto

    manifest = pdf_images(root)
    out = []
    for ref in ptrack(refs, tick):
        ref = norm_ref(ref)
        entry = manifest.get(ref) or {}
        images = entry.get("images") or []
        if not images:
            out.append({"ref": ref, "wrote": False, "figures": 0,
                        "note": "no photographs in the manifest"})
            continue
        dest = alto_for(ref, root, MZFIGDIR)
        if dest.exists() and not force:
            out.append({"ref": ref, "wrote": False, "figures": 0,
                        "note": "exists; --force"})
            continue
        m = entry["master"]
        blocks = [{"label": GRAPHIC, "x0": im["rect"][0], "y0": im["rect"][1],
                   "x1": im["rect"][2], "y1": im["rect"][3]} for im in images]
        dest.parent.mkdir(parents=True, exist_ok=True)
        tree = build_alto(ref, blocks, (m["w"], m["h"]), id_prefix="mzfig_")
        desc = tree.getroot().find("{*}Description")
        # Names the manifest and not a model, so a reader can tell a scanner's
        # segmentation from a segmenter's guess without opening either — and now
        # says so in `kind` rather than only in prose a reader has to recognize.
        desc.append(provenance.alto_processing(provenance.Producer(
            step="harness fig propose", label="embedded-image placement",
            kind="rule", version=f"harness {PROPOSE_VERSION}",
            inputs={"manifest": PDF_IMAGES})))
        tmp = tmp_for(dest)
        tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
                   standalone=None, pretty_print=True)
        tmp.replace(dest)
        out.append({"ref": ref, "wrote": True, "figures": len(blocks),
                    "note": ""})
    return out


def _assignment(ref: str, root: Path) -> tuple:
    """Which caption belongs to which picture, and nothing else about the page.

    `paired`'s rows also carry an `index` — a top-to-bottom ordinal — and that is
    presentation, not a claim about the book: a picture whose box grew upward
    genuinely does start higher, and re-sorting is the store telling the truth.
    Comparing whole rows made `1-167` refuse a correct 12 px growth because two
    boats swapped ordinals while keeping their own captions.
    """
    p = paired(ref, root)
    return (tuple(sorted((f["zone_id"], f["caption_zone"]) for f in p["figures"])),
            tuple(sorted(p["unpaired_captions"])))


def extend_to_rects(ref: str, root: Path = Path("."),
                    max_growth: float | None = None,
                    commit: bool = False) -> dict:
    """Grow keyed pictures to cover the photograph the source separated out.

    **Union only, never intersection.** The rect is the photograph's exact extent,
    so a box that stops inside it leaves an antialiased rim the blot then paints
    around — the fringe this whole change exists to remove. But a box *larger* than
    its rect is left exactly as it is: some figures carry bitonal fringe outside the
    photograph — rules, lettering, a plate border, all living in the master rather
    than the JPEG — and contracting onto the rect would uncover them.

    **Only a clean 1:1 pair is ever touched, and that is the scope of the verb
    rather than a stage of it.** The rect must overlap exactly one picture and that
    picture must be overlapped by exactly one rect. 14 figures in this corpus are
    one photograph spanning several keyed boxes — a figure the book letters
    *a, b, c* under one caption — and there is no correct mechanical answer for
    them: unioning each part with the whole rect makes them duplicates and destroys
    the structure `figure_boxes` folds on, while apportioning the rect between the
    parts would be inventing boundaries the source does not draw. They are reported
    as out of scope and stay that way; a human with the editor is the remedy.

    **`max_growth` is required to write, and is the caller's number.** It is the
    largest area increase, as a fraction, this run may apply to any one box; a box
    that would grow more is refused, counted and named. Nothing is assumed: the
    report says what each box would gain so the ceiling can be chosen from the
    evidence rather than from a default nobody chose. `None` means report only.

    Measured over this store, and the three numbers sum to the 371 photographs:
    **272 grow, 85 are already large enough, 14 are out of scope.** Over the 272
    that move, area growth is **p50 +0.59 %, p90 +1.74 %, max +9.81 %** — a fringe
    correction, not a re-keying. (Taken over all 357 in-scope pairs the medians read
    lower, because 85 of them gain nothing; the distribution that matters is the one
    over boxes that actually change, and that is what the verb prints.) The 85 are
    the union-only rule earning itself: every one is a box a human drew *outside*
    the photograph, which contracting would have spoiled.

    **The caption assignment must not move**, and *only* the assignment. `_gap`
    pairs a picture to a caption by distance with a perpendicular-overlap
    requirement, so growing a picture moves it toward one; the growth is far below
    any plausible gap, but that is a prediction and the diff is a fact.

    What the diff compares is `{picture: caption}` and the unpaired list — **not
    `paired`'s `index`**, which is a top-to-bottom ordinal and moves for reasons
    that are not faults. `1-167` is the case that taught this: Plate XI's four
    boats, where box 002 grew *upward* by 12 px and overtook 001 in the sort, so
    every picture kept its own caption and the whole page was refused anyway. A
    box that now starts higher genuinely does start higher; ordering is a fact
    about geometry, and this verb is allowed to change geometry.
    """
    ref = norm_ref(ref)
    rep: dict = {"ref": ref, "grew": 0, "unchanged": 0, "out_of_scope": 0,
                 "over": 0, "growth": [], "wrote": False, "note": ""}
    entry = pdf_images_for(ref, root)
    if not (entry.get("images") or []):
        return rep
    path = alto_for(ref, root)
    if not path.exists():
        rep["note"] = "no figure ALTO"
        return rep
    pw, ph = _page_box(path)
    rects, space = _rects_in(entry, pw, ph)
    if not space:
        rep["note"] = f"page box {pw}x{ph} is in neither known space"
        return rep

    blocks = read_blocks(path)
    pics = [b for b in blocks if b["label"] == GRAPHIC]
    boxes = {b["id"]: [b["hpos"], b["vpos"], b["hpos"] + b["width"],
                       b["vpos"] + b["height"]] for b in pics}

    def area(b) -> int:
        return max(1, (b[2] - b[0]) * (b[3] - b[1]))

    grown: dict[str, list[int]] = {}
    for r in rects:
        hit = [i for i, box in boxes.items() if _overlaps(r, tuple(box))]
        if len(hit) != 1:
            rep["out_of_scope"] += 1
            continue
        bid = hit[0]
        if sum(1 for r2 in rects if _overlaps(r2, tuple(boxes[bid]))) != 1:
            rep["out_of_scope"] += 1
            continue
        box = boxes[bid]
        union = [min(box[0], r[0]), min(box[1], r[1]),
                 max(box[2], r[2]), max(box[3], r[3])]
        if union == box:
            rep["unchanged"] += 1
            continue
        growth = area(union) / area(box) - 1.0
        rep["growth"].append({"id": bid, "pct": round(growth * 100, 2),
                              "from": list(box), "to": union})
        if max_growth is not None and growth > max_growth:
            rep["over"] += 1
            continue
        grown[bid] = union

    rep["grew"] = len(grown)
    # `max_growth` is what separates a report from a write, so a caller that has not
    # named one gets the measurement and nothing else. Not a default: the number is
    # a judgement about how far a mechanical rule may move a human's rectangle, and
    # this file is not the place that judgement is made.
    if not grown or not commit or max_growth is None:
        return rep

    before = _assignment(ref, root)
    out_blocks = []
    for b in blocks:
        x0, y0, x1, y1 = (grown[b["id"]] if b["id"] in grown else
                          [b["hpos"], b["vpos"], b["hpos"] + b["width"],
                           b["vpos"] + b["height"]])
        out_blocks.append({"id": b["id"], "label": b["label"],
                           "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    save_figs(ref, out_blocks, root)
    after = _assignment(ref, root)
    if after != before:
        # Put it back. A pairing change means a caption now belongs to a different
        # picture, which is a claim about the book that a fringe correction has no
        # business making.
        save_figs(ref, [{"id": b["id"], "label": b["label"], "x0": b["hpos"],
                         "y0": b["vpos"], "x1": b["hpos"] + b["width"],
                         "y1": b["vpos"] + b["height"]} for b in blocks], root)
        rep["grew"] = 0
        rep["note"] = "refused: this would change which caption goes with which "\
                      "picture"
        return rep
    rep["wrote"] = True
    return rep


def extend_all(refs: list[str] | None = None, root: Path = Path("."),
               max_growth: float | None = None, commit: bool = False,
               tick: Callable | None = None) -> list[dict]:
    """`extend_to_rects` over a set of pages, reporting only what it touched."""
    from .parallel import ptrack

    refs = refs if refs is not None else sorted(pdf_images(root))
    out = []
    for ref in ptrack(refs, tick):
        rec = extend_to_rects(ref, root, max_growth=max_growth, commit=commit)
        if rec["grew"] or rec["out_of_scope"] or rec["over"] or rec["note"]:
            out.append(rec)
    return out


def _iou(a: dict, b: dict) -> float:
    ox = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    oy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    if ox <= 0 or oy <= 0:
        return 0.0
    inter = ox * oy
    ua = (a["x1"] - a["x0"]) * (a["y1"] - a["y0"])
    ub = (b["x1"] - b["x0"]) * (b["y1"] - b["y0"])
    return inter / (ua + ub - inter)


def score(root: Path = Path("."), model_path: str | Path | None = None,
          min_iou: float = 0.5) -> dict:
    """Compare `mz/fig/` against `gt/fig/`, per split and per class, never blended.

    **Matched by area overlap**, not by y — the zone track pairs on y because zones
    are bands, and pairing figures that way would call two side-by-side pictures one
    match. Boxes at `min_iou` or better, greedily best-first.

    **Pictures and captions are scored separately.** They differ by an order of
    magnitude in size, so a single figure recall would be carried by whichever class
    is commoner and would hide a model that finds every picture and no caption.

    **Negatives are their own bucket.** A page witnessed to have no figures is a
    third of the eval set, and a box predicted on one is a false positive with
    nowhere else to be counted — folding those into the picture precision would let
    a model that hallucinates on empty pages hide behind the pages that have some.

    Per split and never averaged, for `zones.score`'s reason: agreement on the
    trained-on pages is the editor's own judgement read back.
    """
    splits = load_splits(root, FIGDIR)
    rows: dict[str, dict] = {}
    for split in FIG_SPLITS:
        refs = [r for r, s in splits.items() if s == split]
        acc = {"pages": 0, "empty_pages": 0, "spurious_on_empty": 0}
        for label in (GRAPHIC, FIGDESC):
            acc[label] = {"truth": 0, "predicted": 0, "matched": 0}
        for ref in sorted(refs, key=parse_ref):
            pred_path = alto_for(ref, root, MZFIGDIR)
            if not pred_path.exists():
                continue
            acc["pages"] += 1
            truth = [{"label": b["label"], "x0": b["hpos"], "y0": b["vpos"],
                      "x1": b["hpos"] + b["width"], "y1": b["vpos"] + b["height"]}
                     for b in zones(ref, root)]
            pred = [{"label": b["label"], "x0": b["hpos"], "y0": b["vpos"],
                     "x1": b["hpos"] + b["width"], "y1": b["vpos"] + b["height"]}
                    for b in read_blocks(pred_path)]
            if not truth:
                acc["empty_pages"] += 1
                acc["spurious_on_empty"] += len(pred)
                continue
            for label in (GRAPHIC, FIGDESC):
                t = [b for b in truth if b["label"] == label]
                p = [b for b in pred if b["label"] == label]
                acc[label]["truth"] += len(t)
                acc[label]["predicted"] += len(p)
                used = set()
                for tb in t:
                    best, bi = 0.0, -1
                    for i, pb in enumerate(p):
                        if i in used:
                            continue
                        v = _iou(tb, pb)
                        if v > best:
                            best, bi = v, i
                    if best >= min_iou:
                        used.add(bi)
                        acc[label]["matched"] += 1
        for label in (GRAPHIC, FIGDESC):
            a = acc[label]
            a["recall"] = round(100 * a["matched"] / a["truth"], 1) if a["truth"] else None
            a["precision"] = (round(100 * a["matched"] / a["predicted"], 1)
                              if a["predicted"] else None)
        rows[split] = acc
    return {"model": str(model_path or DEFAULT_MODEL), "min_iou": min_iou,
            "splits": rows}


def install_model(checkpoint: str | Path, root: Path = Path("."),
                  name: str = MODEL_NAME, commit: bool = False,
                  device: str = "auto") -> dict:
    """Score a checkpoint, refuse a swapped class map, then install it.

    `zones.install_model`'s shape and its reasoning: everything that makes a
    checkpoint trustworthy is a precondition of installing it, so the checks run
    before anything is copied and the manifest is written before the weights.

    With two classes the permutation test degenerates to a swap test, which is
    still worth running — `--resize new` renumbers the output layer, and a model
    that has learned "caption" on the channel it calls "picture" scores plausibly
    on counts while being wrong about every box.
    """
    import shutil

    from .zones import _kraken_version, _model_sha256, corpus_digest

    src = Path(checkpoint)
    if not src.is_absolute():
        src = root / src
    if not src.exists():
        raise FileNotFoundError(f"no checkpoint at {checkpoint}")

    work = root / DATADIR
    lists = {s: work / f"{s}.lst" for s in FIG_SPLITS}
    missing = [s for s, p in lists.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"{DATADIR}/{missing[0]}.lst is gone, so the split this run consumed "
            "cannot be frozen beside the model — re-run `harness train assemble fig` "
            "before installing, or the scores would belong to a split nobody kept")

    sc = score(root, src)
    swapped = _swap_check(sc)
    out = {"checkpoint": str(checkpoint), "name": name, "committed": False,
           "swapped_map": swapped, "scores": sc["splits"]}
    if swapped:
        out["note"] = ("the two classes look swapped — captions scoring as "
                       "pictures and the reverse. Not installed")
        return out
    if not commit:
        out["note"] = "preview only — pass --commit to install"
        return out

    dest_dir = root / MODELDIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "model": f"{MODELDIR}/{name}{src.suffix}",
        "installed_from": str(checkpoint),
        "sha256": _model_sha256(src),
        "corpus_digest": corpus_digest(root, store=FIGDIR),
        "kraken": _kraken_version(),
        "trained_on": "scans/ (raw) — the blot paints this model's target white",
        "scores": sc["splits"],
    }
    (dest_dir / f"{name}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for s, p in lists.items():
        shutil.copy(p, dest_dir / f"{name}.{s}.lst")
    shutil.copy(src, dest_dir / f"{name}{src.suffix}")
    out["committed"] = True
    out["path"] = f"{MODELDIR}/{name}{src.suffix}"
    return out


def _swap_check(sc: dict) -> bool:
    """Would calling every picture a caption and vice versa score better?

    The two-class degenerate of `zones`' permutation refusal. Read off `train`,
    where the model has seen the answer: a correct model agrees with itself there,
    and a swapped one disagrees with itself everywhere.
    """
    t = sc["splits"].get("train") or {}
    g, d = t.get(GRAPHIC) or {}, t.get(FIGDESC) or {}
    if not g.get("truth") or not d.get("truth"):
        return False
    straight = (g.get("matched", 0) + d.get("matched", 0))
    # A swapped model matches almost nothing straight while predicting plenty.
    return straight == 0 and (g.get("predicted", 0) + d.get("predicted", 0)) > 0




def migrate_page(ref: str, root: Path = Path("."),
                 store: str = FIGDIR) -> dict:
    """One page reduced to bounding boxes with `fig_` ids. Computes, writes nothing.

    Returns `{ref, blocks, remap, before, after}` — `blocks` ready for `build_alto`,
    `remap` the old-to-new suffix map for the page's **FigDesc** blocks alone, since
    those are the ones a caption is keyed by, and `before`/`after` the geometry
    as a sorted tuple so the caller can assert they match.

    **The reduction changes no reader's answer, by construction.** Every consumer of
    this store already goes through `read_blocks`, which takes `HPOS/VPOS/WIDTH/
    HEIGHT` through `_bbox` and never looks at the polygon unless asked. 395 of the
    store's 809 polygons are skewed quads or 5-to-9-gons that disagree with their
    own bbox, and nothing has ever read them. So this writes down what was already
    being read, and `after == before` is a check of that claim rather than a hope.
    """
    from .zones import raster_size

    ref = norm_ref(ref)
    blocks = read_blocks(alto_for(ref, root, store))
    geom = sorted((b["label"], b["hpos"], b["vpos"], b["width"], b["height"])
                  for b in blocks)

    ordered = sorted(blocks, key=lambda b: (b["vpos"], b["hpos"]))
    out, remap = [], {}
    for i, b in enumerate(ordered, start=1):
        new_id = f"fig_{ref}_{i:03d}"
        if b["label"] == FIGDESC:
            remap[zone_suffix(b["id"])] = f"{i:03d}"
        out.append({"id": new_id, "label": b["label"],
                    "x0": b["hpos"], "y0": b["vpos"],
                    "x1": b["hpos"] + b["width"],
                    "y1": b["vpos"] + b["height"]})

    return {"ref": ref, "blocks": out, "remap": remap, "before": geom,
            "after": sorted((b["label"], b["x0"], b["y0"],
                             b["x1"] - b["x0"], b["y1"] - b["y0"]) for b in out),
            "size": raster_size(ref, root)}


def remap_readings(text: str, remap: dict[str, dict[str, str]]) -> tuple[str, int]:
    """Rewrite `## <ref>|<suffix>` headers through a per-ref suffix map.

    Header-only and by whole line: a caption's *text* may legitimately contain
    anything, including something shaped like a key, so a global substitution over
    the file is the one implementation that must not be used here.

    Returns the new text and the number of headers rewritten, so the caller can
    check it against the number of FigDesc blocks rather than trusting the walk.
    """
    n = 0

    def sub(m):
        nonlocal n
        ref, old = m.group(1), m.group(2)
        new = (remap.get(ref) or {}).get(old)
        if new is None:
            return m.group(0)
        n += 1
        return f"## {ref}|{new}"

    return _HDR.sub(sub, text), n


def migrate_store(root: Path = Path("."), commit: bool = False) -> dict:
    """Reduce every page of `gt/fig/` to boxes, re-mint ids, re-key the readings.

    Report by default. `--commit` writes the 252 ALTOs and `data/readings.md`
    together, because they are one fact in two files: a store whose ids moved and a
    readings file still keyed to the old ones reconciles to nothing at all.

    Refuses on any page whose geometry would change, and on a readings rewrite whose
    header count does not match the FigDesc blocks the remap covered. Both are
    conditions the caller could not otherwise see until `corpus figures` failed,
    by which point the store is already rewritten.
    """
    from .zones import build_alto

    pages, drift, changed = [], [], 0
    remap: dict[str, dict[str, str]] = {}
    for ref in fig_refs(root):
        m = migrate_page(ref, root)
        if m["before"] != m["after"]:
            drift.append(ref)
        remap[ref] = m["remap"]
        changed += len(m["remap"])
        pages.append(m)

    text = (root / READINGS).read_text(encoding="utf-8")
    new_text, rewritten = remap_readings(text, remap)

    out = {"pages": len(pages), "blocks": sum(len(p["blocks"]) for p in pages),
           "captions": changed, "headers_rewritten": rewritten,
           "geometry_drift": drift, "committed": False}
    if drift:
        out["note"] = ("geometry changed on these pages — the reduction must be "
                       "the bbox every reader already computes, and is not")
        return out
    if rewritten != changed:
        out["note"] = (f"{changed} caption blocks remapped but {rewritten} headers "
                       "rewritten — a reading names a zone this store does not have")
        return out
    if not commit:
        out["note"] = "preview only — pass --commit to write"
        return out

    for p in pages:
        tree = build_alto(p["ref"], p["blocks"], p["size"], id_prefix="fig_")
        tree.write(str(alto_for(p["ref"], root)), xml_declaration=True,
                   encoding="UTF-8", standalone=None, pretty_print=True)
    write_atomic(root / READINGS, new_text)
    out["committed"] = True
    return out


def validate_fig_page(ref: str, root: Path = Path("."), cfg: dict | None = None,
                      store: str = FIGDIR) -> dict:
    """Check one page of the figure store: mechanical errors, configured warnings.

    The division is `zones.validate_page`'s and means the same thing here. An
    **error** is a fault no reading of the page could excuse; a **warning** is a
    domain expectation about *this book*, configurable, exemptable, and never
    gating.

    Only three things qualify as errors, and the list is short on purpose. A label
    this store does not declare is one, because nothing could read it. A polygon
    that is not the rectangle its own bbox claims is one, because every reader here
    takes the bbox and the polygon would be a claim nobody consumes. A box off the
    raster is one, because it describes a region of a page that does not exist.

    Everything else — a picture overlapping a picture, a box too small to be a
    picture, more captions than pictures — is a warning, and `zones_config.
    fig_warnings` holds the reasoning for why the first two moved there.
    """
    from . import zones_config as zc
    from .zones import _is_rectangle, raster_size

    cfg = cfg or zc.load_config(root)
    ref = norm_ref(ref)
    figs_cfg = cfg.get("figures") or {}
    declared = {t["label"] for t in zc.fig_types(cfg)}

    path = alto_for(ref, root, store)
    blocks = read_blocks(path, with_points=True)
    errors: list[dict] = []

    def err(rule: str, detail: str):
        errors.append({"rule": rule, "detail": detail})

    try:
        page_w, page_h = raster_size(ref, root)
    except (FileNotFoundError, OSError):
        page_w = page_h = 0

    for b in blocks:
        x0, y0 = b["hpos"], b["vpos"]
        x1, y1 = x0 + b["width"], y0 + b["height"]
        if b["label"] not in declared:
            err("undeclared-label",
                f"{b['id']} carries {b['label']!r}, which this store does not "
                f"declare ({', '.join(sorted(declared))})")
        if page_w and (x0 < 0 or y0 < 0 or x1 > page_w or y1 > page_h):
            err("off-raster",
                f"{b['id']} spans {x0},{y0}..{x1},{y1} on a {page_w}x{page_h} page")
        if not _is_rectangle(b.get("points", ""), x0, y0, x1, y1):
            err("not-a-rectangle",
                f"{b['id']}'s polygon is not the rectangle its bbox claims — this "
                "store carries boxes, and every reader of it takes the bbox")

    pics = [b for b in blocks if b["label"] == GRAPHIC]
    exempt = load_rule_exempt(root, store).get(ref, {})
    warnings = zc.fig_warnings(cfg, blocks, exempt)
    known = {r["id"] for r in (figs_cfg.get("rules") or [])}
    for r in exempt:
        if r not in known:
            err("unknown-exemption",
                f"{ref} exempts {r!r}, which is not a rule this config declares")
    # An exemption carrying no reason is reported, not honoured silently. It still
    # suppresses the gate — the human did rule — but a store that cannot tell a
    # considered ruling from a keystroke is the thing `_rule_exempt.json`'s note
    # exists to prevent, so the gap is surfaced rather than inherited.
    unruled = sorted(r for r, note in exempt.items() if not str(note).strip())
    for r in unruled:
        warnings.append({"rule": "unruled-exemption", "exempted": False,
                         "detail": f"{ref} exempts {r!r} with no reason recorded"})

    # The two manifest rules. **Evaluated here and not in `zc.fig_warnings`**, which
    # is pure over the page's own blocks — this one has to read
    # `data/pdf_images.json`, and putting I/O behind that signature would make a
    # declarative evaluator lie about what it depends on.
    ink = fig_ink(ref, root, store) if UNACCOUNTED_RULE in known else None
    if ink and ink["state"] in ("unaccounted", "ruled"):
        detail = (
            f"{len(ink['uncovered'])} of {ink['rects']} photograph(s) the source "
            f"separates out are overlapped by no GraphicZone: "
            + "; ".join(f"{r[0]},{r[1]}..{r[2]},{r[3]}" for r in ink["uncovered"])
            + (f" ({ink['note']})" if ink["note"] else ""))
        if ink["state"] == "unaccounted":
            err(UNACCOUNTED_RULE, detail)
        else:
            # Excused, and therefore **still reported** — as a flagged warning,
            # since the error channel has no exempted lane. Dropping it here
            # because a page once ruled on it is the failure `set_rule_exempt`'s
            # docstring names: a warning that vanishes when excused leaves no way
            # to notice the excuse has outlived the page it was written for.
            warnings.append({"rule": UNACCOUNTED_RULE,
                             "detail": _ruled(detail, exempt, UNACCOUNTED_RULE),
                             "exempted": True})
    if ink and OUTSIDE_RULE in known:
        for o in ink["outside"]:
            base = (f"{o['share'] * 100:.1f}% of the photograph at "
                    f"{o['rect'][0]},{o['rect'][1]}..{o['rect'][2]},"
                    f"{o['rect'][3]} lies outside every keyed picture")
            warnings.append({
                "rule": OUTSIDE_RULE,
                "detail": _ruled(base, exempt, OUTSIDE_RULE),
                "exempted": OUTSIDE_RULE in exempt})

    return {
        "ref": ref, "keyed": path.exists(), "blocks": len(blocks),
        "figures": len(pics),
        "captions": sum(1 for b in blocks if b["label"] == FIGDESC),
        "split": load_splits(root, store).get(ref) or "",
        "errors": errors,
        "warnings": [w for w in warnings if not w["exempted"]],
        "exempted": [w for w in warnings if w["exempted"]],
    }


def save_figs(ref: str, blocks: list[dict], root: Path = Path("."),
              split: str | None = None, rules: list[str] | None = None,
              stamp: str | None = None, drop_text: bool = False) -> dict:
    """Write one page's figure and caption boxes, atomically, and record the save.

    `blocks` are `{label, x0, y0, x1, y1}` and **optionally `id`**. The durability
    shape is `save_zones`': copy to `.prev`, write `.tmp`, `replace()`, append to an
    append-only journal.

    **An id that arrives is kept, and that is the whole reason this is not
    `save_zones` with a different directory.** A block id's last field is the key
    its caption text is filed under, so re-minting by position — as
    the zone store does, harmlessly, because nothing points at a zone id — would
    re-point every caption below an inserted figure at the wrong picture. It would
    do so silently: the file stays well-formed, the counts still reconcile, and
    `harness corpus figures` comes back clean because it compares *sets* of
    suffixes, which are unchanged. `1-191` is the live case — its undeclared
    photograph sorts above all four existing blocks.

    **An empty page is refused**, and unlike the zone store there is no `exempt`
    escape: the figure store's absence of a file is already the statement "no
    figures here", read that way by `dispatch.survey`, `zones.blot_one` and
    `lines.line_gaps` alike. Writing an empty ALTO would claim the opposite of what
    it means. Withdrawal is `delete_figs`, and the message says so, because a human
    deleting a page's last box in the editor arrives here with no other way out.
    """
    from .zones import build_alto, raster_size

    ref = norm_ref(ref)
    if not blocks:
        raise ValueError(
            f"{ref} has no figure boxes, and an empty figure ALTO would mean the "
            "opposite of what it says: absence of the file is how this store "
            "records 'no figures on this page', and every reader of it — the "
            "reader dispatch survey, the blot, the dropped-line detector — takes "
            "an existing file as 'this page has figures'. If the page has none, "
            f"withdraw it: `harness fig delete {ref} --commit`.")
    for b in blocks:
        if b["label"] not in (GRAPHIC, FIGDESC):
            raise ValueError(
                f"{ref} carries {b['label']!r}, which is not a figure-track label. "
                f"This store declares {GRAPHIC} and {FIGDESC} and nothing else; a "
                "body-text zone belongs in `gt/zones/`.")

    p = alto_for(ref, root)

    # Mint the missing ids here rather than leaving them to `build_alto`, because
    # the high-water mark this store needs is not visible from one batch. Two ways
    # a freed ordinal could otherwise come back: the caller dropped an id it was
    # handed, or this very save removes the highest-numbered block. Both would let
    # the next mint land on a number a reading still names, and a stale caption
    # re-attaching to a new picture is the exact silent mispairing this store is
    # built to make impossible.
    #
    # It is a floor, not a guarantee across time: a block deleted in one save and
    # another added in the next can still collide. That window is *gated* rather
    # than closed — deleting a caption block orphans its reading, `harness corpus
    # figures` exits 1 on an orphan, and the store cannot reach the collision
    # without a human passing through that failure and deciding what the reading
    # was for. A persistent counter would close it and would put the store's
    # identity in a file nothing else reads; the reconciliation is the better
    # witness because it is the one already being run.
    from .zones import _id_ordinal
    on_disk = [b["id"] for b in read_blocks(p)] if p.exists() else []
    nxt = max((_id_ordinal(i) for i in
               on_disk + [b.get("id") or "" for b in blocks]), default=0) + 1
    blocks = [dict(b) for b in blocks]
    for b in sorted(blocks, key=lambda b: (b["y0"], b["x0"])):
        if not b.get("id"):
            b["id"] = f"fig_{ref}_{nxt:03d}"
            nxt += 1

    # **The caption text is read off the old file and carried across the rebuild.**
    # `build_alto` mints a whole ALTO from geometry, which is right for boxes and
    # fatal for text: once `fig restore` has run, every FigDesc carries a caption a
    # human ratified, and a geometry save from the browser editor would delete all
    # of them — writing a well-formed file, breaking no check at save time, and
    # looking exactly like an ordinary save. That is the quietest destructive path
    # in this store, so it is closed here rather than gated downstream.
    #
    # Carried **by block id**, never by position: the id is the key the text is
    # filed under, and `save_figs` preserves ids for precisely this class of reason.
    # A block whose id is gone from this save is a block the caller withdrew, so its
    # text goes with it — that is `delete_figs`' outcome arriving one verb over.
    held = {}
    if p.exists():
        old = etree.parse(str(p))
        old_labels = _labels(old)
        held = {blk.get("ID"): lines
                for blk in old.iter("{*}TextBlock")
                if _block_label(blk, old_labels) == FIGDESC
                and (lines := block_text(blk))}
    keeping = {b.get("id") for b in blocks}
    dropped = sorted(k for k in held if k not in keeping)
    if dropped and not drop_text:
        raise ValueError(
            f"{ref}: this save drops {len(dropped)} block(s) that hold ratified "
            f"caption text ({', '.join(dropped[:4])}). Withdrawing a picture is "
            f"`fig delete`; withdrawing a caption whose text a human ruled on is "
            f"not something a geometry save should do silently. Pass "
            f"`drop_text=True` if that is really meant.")

    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tree = build_alto(ref, blocks, raster_size(ref, root), id_prefix="fig_")
    if held:
        labels = _labels(tree)
        for blk in tree.iter("{*}TextBlock"):
            lines = held.get(blk.get("ID"))
            if lines and _block_label(blk, labels) == FIGDESC:
                _add_text_line(blk, lines)

    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    tmp = tmp_for(p)
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
               standalone=None, pretty_print=True)
    tmp.replace(p)

    if rules is not None:
        set_rule_exempt(ref, rules, root)
    marked = load_splits(root).get(ref)
    if split is not None:
        set_split(ref, split, root)
    elif marked is None:
        set_split(ref, DEFAULT_SPLIT, root)

    counts: dict[str, int] = {}
    for b in blocks:
        counts[b["label"]] = counts.get(b["label"], 0) + 1
    with (fig_dir(root) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"saved_at": stamp, "ref": ref,
                             "blocks": len(blocks), "labels": counts,
                             "split": split or marked or DEFAULT_SPLIT},
                            ensure_ascii=False) + "\n")
    return {"ref": ref, "path": str(p), "blocks": len(blocks),
            "figures": counts.get(GRAPHIC, 0), "captions": counts.get(FIGDESC, 0),
            "split": split or marked or DEFAULT_SPLIT}


def delete_figs(ref: str, root: Path = Path("."), commit: bool = False,
                stamp: str | None = None) -> dict:
    """Withdraw a page from the figure store: its file, its split mark, its rules.

    The counterpart to `save_figs`' refusal of an empty page, and the only way to
    say "this page has no figures after all". Same durability as a save, because
    this is the more dangerous direction, and `--commit` is required.

    **A deleted page's captions go with it**, the text living on the blocks
    being deleted. That is why `save_figs` refuses a *geometry* save that would
    drop a block still holding ratified text: withdrawing a picture is this verb,
    deliberate and `--commit`-gated, where a silent cascade out of an ordinary
    save would be the worse outcome. The report names them and a
    human decides.
    """
    ref = norm_ref(ref)
    p = alto_for(ref, root)
    splits = load_splits(root)
    rules = load_rule_exempt(root).get(ref, {})
    blocks = read_blocks(p) if p.exists() else []
    caps = sum(1 for b in blocks if b["label"] == FIGDESC)

    out = {"ref": ref, "path": str(p), "exists": p.exists(),
           "blocks": len(blocks), "captions_orphaned": caps,
           "split": splits.get(ref) or "", "rule_exemptions": " ".join(rules),
           "committed": commit}
    if not p.exists():
        out["note"] = "nothing to delete"
        return out
    if not commit:
        out["note"] = "preview only — pass --commit to delete"
        return out

    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    p.unlink()
    for which in FIG_SPLITS:
        lst = _lst_path(root, which)
        entries = [e for e in _read_lst(lst) if e != f"chukchi-{ref}.xml"]
        if lst.exists():
            write_atomic(lst, "".join(e + "\n" for e in entries))
    if rules:
        set_rule_exempt(ref, [], root)
    with (fig_dir(root) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"saved_at": stamp, "ref": ref, "deleted": True,
                             "blocks": len(blocks),
                             "captions_orphaned": caps}, ensure_ascii=False) + "\n")
    return out


# Adjudication keywords that may open a reading's `@note`. The first two are
# terminal — the page was re-examined and the question is closed. The rest mark
# work outstanding. Kept here so a consumer can filter on them without
# re-deriving the vocabulary from prose. Order is longest-first so that a prefix
# match cannot shadow a longer keyword.
NOTE_KEYWORDS = (
    "CONFLICT WITH THE LIST OF ILLUSTRATIONS",
    "KEYING REQUIRED",
    "ZONE TOO SMALL",
    "ZONE MISPLACED",
    "VERBATIM",
    "MISPRINT",
)
TERMINAL_KEYWORDS = ("VERBATIM", "MISPRINT")

_HDR = re.compile(r"^## (\S+?)\|(\S+)$", re.M)


def _page_readings(ref: str, root: Path) -> dict[str, dict]:
    """One page's captions, off its own `gt/fig/` ALTO. `{}` for a page with none.

    NFD on read, keying spec §1's form and the rule `data/readings.md` kept before
    it. `save_caption_text` writes what the adjudication holds and `corpus
    normalize` gates the store, but a normal form that depends on which writer ran
    is exactly what folding here prevents.
    """
    p = alto_for(ref, root)
    if not p.exists():
        return {}
    try:
        tree = etree.parse(str(p))
    except (OSError, etree.XMLSyntaxError):
        # Absence and unreadability are both `{}` — `read_blocks`' disposition,
        # and for its reason: callers ask "what has been read here" and "nothing"
        # is a legitimate answer for a store still being written.
        return {}
    labels = _labels(tree)
    out = {}
    for blk in tree.iter("{*}TextBlock"):
        if _block_label(blk, labels) != FIGDESC:
            continue
        lines = [unicodedata.normalize("NFD", ln) for ln in block_text(blk) if ln]
        if not lines:
            continue
        suffix = zone_suffix(blk.get("ID") or "")
        out[suffix] = {"ref": ref, "zone_suffix": suffix,
                       "lines": lines, "text": " ".join(lines)}
    return out


def readings(root: Path = Path(".")) -> dict[str, dict]:
    """Every caption in `gt/fig/`, as `{"<ref>|<zone-suffix>": record}`.

    **The store holds the caption, and this is how it is read back.** It used to
    parse `data/readings.md`, which was the caption store before the adjudicated
    text moved into the ALTO under the block that carries the caption's own
    geometry. Both files existed for a while and **58 of the 395 captions had
    drifted apart** — `½` against `1/2`, catalogue numbers that gained a suffix
    letter on a re-read, `6cm.` against `6 cm.` — with the store holding the
    adjudication and the edition serving the markdown. One caption store, keyed by
    the block id, is what closes that.

    `lines` preserves the printed line breaks and so the printed hyphenation:
    **31 of the 196 multi-line captions break on a hyphen and they are not the
    same kind of hyphen** — `Leaf-Tobacco` is the book's compound and `attach-ing`
    is a wrap artifact. Joining is a rendering decision downstream, never here.
    `block_text` keeps the division for that reason and this preserves it.

    A caption's `@note` is **not** here any more. The adjudication that produced
    the text records its own reasoning in `review/captions/proposal.json` and
    `review/captions/decision.json`, which is where a reader of a note should go;
    a second copy filed beside the text would be a note that could outlive it.
    """
    out = {}
    for ref in fig_refs(root):
        for suffix, rec in _page_readings(ref, root).items():
            out[f"{ref}|{suffix}"] = rec
    return out


def readings_for(ref: str, root: Path = Path("."),
                 all_readings: dict | None = None) -> dict[str, dict]:
    """The captions on one page, keyed by bare zone-id suffix.

    `all_readings` is a `readings(root)` a caller already holds — `reconcile` and
    `tei generate` sweep the store once and hand it down. Without it this now
    reads **one page's ALTO** rather than the whole caption store, which reverses
    the old cost: `data/readings.md` had to be parsed entire to answer about one
    page, and a page's own file answers directly.
    """
    ref = norm_ref(ref)
    if all_readings is None:
        return _page_readings(ref, root)
    return {r["zone_suffix"]: r for r in all_readings.values() if r["ref"] == ref}


# **The manifest lives in `scans.py`, and these are its names here.** It is a fact
# about the rasters rather than about figures — `migrate`, `zones_ui` and the new
# `scans` group all read it — and it sat in this module only because the figure
# check was its first caller. Aliased rather than swept: one definition, one import
# line, and every existing `figures.pdf_images` / `figures._rects_in` call site
# keeps working, which is the whole of what a re-export is for.
_rects_in = _scans_rects_in


def _ruled(detail: str, exempt: dict, rule: str) -> str:
    """A finding's text with the ruling that excused it, where there is one.

    The note travels **with the finding**, not in a file the reader has to go and
    open, which is what makes "still reports, flagged" worth anything: an excused
    warning that shows without its reason is indistinguishable from one nobody has
    looked at.
    """
    note = str((exempt or {}).get(rule, "")).strip()
    return f"{detail} — ruled: {note}" if note else detail


def _page_box(path: Path) -> tuple[int, int]:
    """An ALTO's declared page size, or `(0, 0)`.

    **The file's own statement of which coordinate space it is in.** Every store
    here records it, and reading it rather than assuming is what lets one check run
    against both the legacy render's coordinates and the master's.
    """
    if not path.exists():
        return (0, 0)
    page = etree.parse(str(path)).find(".//{*}Page")
    try:
        return (int(float(page.get("WIDTH"))), int(float(page.get("HEIGHT"))))
    except (AttributeError, TypeError, ValueError):
        return (0, 0)


def _overlaps(a: list[int], b: tuple[int, int, int, int]) -> bool:
    """Do two boxes share any area at all?"""
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _outside(rect: list[int], boxes: list[tuple[int, int, int, int]],
             pad: int, step: int = 4) -> float:
    """Fraction of `rect` lying outside every box in `boxes`, padded by `pad`.

    Sampled on a grid rather than computed exactly: the boxes overlap freely, so an
    exact answer wants a union of rectangles, and this number is **reported and
    never gated on** — a measure that only has to be right to a percent should not
    carry a geometry library's worth of ways to be wrong.

    **The same grid, marked by slice rather than walked point by point.** This was
    a nested `range` over the rect testing every sample against every box, and at
    300 dpi a photograph rect is ~187,000 samples: `corpus figures` spent **33 of
    its 34 seconds here**, over 76.7 million evaluations of the membership test.
    Since the sample coordinates are sorted, the indices a box covers are two
    `searchsorted` calls per axis, and marking them is one slice assignment — so
    the work is proportional to the number of boxes rather than to the area.

    `searchsorted` reproduces the old bounds exactly: `left` on the low edge gives
    the first sample `>= g0`, `right` on the high edge the first `> g1`, which is
    the closed interval `g0 <= v <= g1` the loop tested.
    `test_fig_ink_geometry.py` holds the two implementations against each other on
    randomised inputs, because "same answer, faster" is the whole claim and it is
    not visible in any output.
    """
    x0, y0, x1, y1 = rect
    xs = np.arange(x0, max(x0 + 1, x1), step)
    ys = np.arange(y0, max(y0 + 1, y1), step)
    tot = int(xs.size) * int(ys.size)
    if not tot:
        return 0.0
    covered = np.zeros((ys.size, xs.size), dtype=bool)
    for b in boxes:
        ix0 = np.searchsorted(xs, b[0] - pad, "left")
        ix1 = np.searchsorted(xs, b[2] + pad, "right")
        iy0 = np.searchsorted(ys, b[1] - pad, "left")
        iy1 = np.searchsorted(ys, b[3] + pad, "right")
        if ix1 > ix0 and iy1 > iy0:
            covered[iy0:iy1, ix0:ix1] = True
    return float(int((~covered).sum()) / tot)


def fig_ink(ref: str, root: Path = Path("."), store: str = FIGDIR,
            pad: int = UNACCOUNTED_PAD) -> dict:
    """Photographs the source separated out that the figure store never accounted
    for — the figure track's answer to `zones`' uncovered ink.

    **Accounted for means overlapped, not contained**, and that is a measurement
    rather than a preference. Over the 371 rects in this corpus, 255 merely
    partially overlap their best-matching keyed box, 86 are contained by it and 17
    contain it; the rect sits a little proud of what a human drew, by 1-3 px at the
    median. A containment rule reports 131 findings on a store that is in fact
    complete. Overlap reports 0, which is the truth.

    **Computed live, with no cache.** `zones.cached_ink` exists because uncovered
    ink is the one check that reads the raster; this one reads a small tracked JSON
    already in memory, so a cache would buy nothing and could go stale, which is the
    only thing it could do.

    Four states, `zones._ink_verdict`'s so the two read alike:

        skip          no photos on this page, or a page box in neither space
        clean         every rect overlapped by a keyed picture
        ruled         the uncovered ones are all exempted
        unaccounted   a rect no keyed picture touches

    A page carrying photos with **no figure ALTO at all is `unaccounted`, not
    `skip`** — a photograph nobody keyed is the loudest thing this can find, and
    filing it under "nothing to say" would lose exactly the case it exists for.

    `outside` rides alongside: the share of each rect's area beyond every keyed box.
    **Reported, never gated**, because a rect legitimately spans several part-boxes
    of one lettered figure and the gutter between them belongs to no box. Today 14
    pages exceed 5 %; 13 of those are such figures.

    The fourteenth is why this reports at all. `1-287`'s rect runs to x=2190 across
    a rotated caption sitting at 2098..2206 — **the scanner put the caption's pixels
    in the photo layer**, so on that page the rect is not the picture's extent and
    growing the box onto it would pull the caption inside the picture. A large
    `outside` share therefore means one of two things: a lettered figure, or a rect
    that cannot be trusted as a boundary. Neither is a fault in the keying, which is
    why this never gates — and the thing to watch is whether the list is still these
    pages, not whether it is empty.
    """
    ref = norm_ref(ref)
    entry = pdf_images_for(ref, root)
    if not (entry.get("images") or []):
        return {"ref": ref, "state": "skip", "space": "", "rects": 0,
                "uncovered": [], "ruled": 0, "outside": [], "note": "no photos"}

    path = alto_for(ref, root, store)
    blocks = read_blocks(path)
    if not path.exists():
        # No keying at all, and the page has photographs. Every rect is unaccounted
        # for; the page box cannot be read, so the rects are reported in the space
        # the manifest states.
        rects = [list(im["rect"]) for im in entry["images"]]
        return {"ref": ref, "state": "unaccounted", "space": "master",
                "rects": len(rects), "uncovered": rects, "ruled": 0,
                "outside": [], "note": "photos on a page with no figure ALTO"}

    pw, ph = _page_box(path)
    if not pw:
        return {"ref": ref, "state": "skip", "space": "", "rects": 0,
                "uncovered": [], "ruled": 0, "outside": [], "note": "no page box"}

    rects, space = _rects_in(entry, pw, ph)
    if not space:
        m = entry.get("master") or {}
        return {"ref": ref, "state": "skip", "space": "", "rects": 0,
                "uncovered": [], "ruled": 0, "outside": [],
                "note": f"page box {pw}x{ph} is neither master {m.get('w')}x"
                        f"{m.get('h')} nor its render"}

    boxes = [(b["hpos"], b["vpos"], b["hpos"] + b["width"], b["vpos"] + b["height"])
             for b in blocks if b["label"] == GRAPHIC]
    uncovered = [r for r in rects if not any(_overlaps(r, b) for b in boxes)]
    outside = [{"rect": r, "share": round(_outside(r, boxes, pad), 4)}
               for r in rects]
    exempt = load_rule_exempt(root, store).get(ref, {})
    ruled = UNACCOUNTED_RULE in exempt
    state = ("clean" if not uncovered
             else "ruled" if ruled else "unaccounted")
    return {"ref": ref, "state": state, "space": space, "rects": len(rects),
            "uncovered": uncovered, "ruled": len(uncovered) if ruled else 0,
            "outside": [o for o in outside if o["share"] > OUTSIDE_SHARE],
            "note": ""}


def _gap(g: dict, c: dict) -> float | None:
    """Distance from picture `g` to caption `c`, or None if `c` cannot be its caption.

    Landscape caption: below, overlapping horizontally. Portrait caption
    (a rotated plate caption): beside, overlapping vertically. See `paired`.
    """
    if c["width"] >= c["height"]:
        if c["vpos"] < g["vpos"] or (
                min(c["hpos"] + c["width"], g["hpos"] + g["width"])
                <= max(c["hpos"], g["hpos"])):
            return None
        return c["vpos"] - (g["vpos"] + g["height"])
    # The same rule rotated: a landscape caption is set *after* its picture down
    # the page, a rotated one *after* it across the page. Without the second
    # half, `1-273`'s top-right plate ties at 30 px between the caption on its own
    # right and the one belonging to the picture on its left, and document order
    # breaks the tie the wrong way.
    if c["hpos"] < g["hpos"] or (
            min(c["vpos"] + c["height"], g["vpos"] + g["height"])
            <= max(c["vpos"], g["vpos"])):
        return None
    # Signed separation, so a caption whose box just overlaps its picture's right
    # edge (4 px on `1-227`) scores slightly *better* than one merely near it,
    # rather than being ranked by a distance between origins — which put a plate's
    # caption 1040 px away from the picture it sits on top of.
    return max(c["hpos"] - (g["hpos"] + g["width"]),
               g["hpos"] - (c["hpos"] + c["width"]))


def paired(ref: str, root: Path = Path("."),
           all_readings: dict | None = None) -> dict:
    """One record per figure — the picture, its caption — in reading order.

    `all_readings` is passed straight to `readings_for`. It matters most to
    `reconcile`, which already holds a `readings(root)` and then called this once
    per figure page — 252 further whole-store sweeps, each
    to keep one page's rows.

    **The pairing is done here, once, and recorded.** `GraphicZone`↔FigDesc
    pairing is not in the data, and every consumer that re-derives it derives it
    differently; `context._figures_on_page` used to not derive it at all, handing
    the collation pass both zones flat and letting the model sort them out. What
    that produced on `1-151` is in the committed TEI: the model anchored the
    figure correctly and then emitted an orphan comment about the caption zone,
    because the skill says to name an unreferenced zone and a FigDesc is
    unreferenced **by construction**. A permanent known-false comment waiting on
    all 252 figure pages.

    **A figure is a `GraphicZone`.** The FigDesc is its caption, not a second
    figure, so it is a field here rather than a row — which is also why `text: ""`
    stops being the normal case: a picture zone can never carry a reading (they
    are keyed by FigDesc suffix), so an empty caption now
    means `3-006`, artwork the book captions nowhere.

    **The rule branches on the caption's own shape, and the book is why.** A text
    figure sets its caption *below* the picture, landscape — `1-151`'s is 610×96.
    A **plate sets it rotated, beside** the picture, reading bottom-to-top:
    `1-049`'s three are 86×457, 92×506, 82×636. A below-only rule leaves every
    plate caption unclaimed, which is exactly what it did — 19 of them over 14
    pages, all plates. So a landscape caption is looked for below its picture and
    a portrait one beside it, each requiring overlap on the other axis. The
    discriminator is `width >= height`, a property of the box rather than a
    threshold anyone has to calibrate, and it needs no prior classification of
    the page: a mixed page pairs correctly zone by zone.

    Overlap on the perpendicular axis is **required, not preferred**. It is what
    keeps a two-column plate from pairing across the gutter, and on `2-085` it is
    what stops the store's 14×38 speck of a `GraphicZone` from claiming fig. 253's
    caption — the speck stays a captionless figure, which is a defect showing
    rather than a defect absorbed.

    Pairing is **one-way**: several pictures may share one caption, which is what
    the book does on 17 pages (`1-276`'s fig. 138 *a, b, c*, `2-085`'s fig. 253
    *a, b*), and no caption is ever split between pictures.

    **Order is a plain top-to-bottom, left-to-right sort of the picture boxes**,
    and deliberately not the ALTO's document order, which eScriptorium and the
    old figure network assigned arbitrarily. Nor is it `lines.reading_order`:
    that bands rows on half the median *line* height, which is the right
    tolerance for type and meaningless for artwork.

    **`index` is a handle, not a claim about the book's own order**, because the
    book does not always number geometrically: a rotated plate numbers as the
    *turned* page reads (`1-227` is 2,4,1,3 upright), and `1-260` numbers its
    tall right-hand figure 123 between two in the left column. That costs
    nothing, since a consumer matches on the caption's printed number and uses
    the index only to name a zone — see the removed `misordered` check at the
    foot of `reconcile` for what happened when this was treated as a rule.

    `unpaired_captions` is a FigDesc no picture claimed. It should always be
    empty — docs/apparatus.md records that all five caption-heavy pages were segmentation
    faults and were deleted — so a non-empty list is a new fault, which is
    exactly the signal it was supposed to be once noise stopped sharing the
    bucket. `reconcile` reports it; nothing here refuses.
    """
    ref = norm_ref(ref)
    blocks = zones(ref, root)
    caps = [b for b in blocks if b["label"] == FIGDESC]
    try:
        texts = readings_for(ref, root, all_readings)
    except (ValueError, OSError):
        texts = {}

    claimed, figures = set(), []
    graphics = sorted((b for b in blocks if b["label"] == GRAPHIC),
                      key=lambda b: (b["vpos"], b["hpos"]))
    for i, g in enumerate(graphics, 1):
        reach = [(d, c) for c in caps if (d := _gap(g, c)) is not None]
        cap = min(reach, key=lambda dc: dc[0], default=(None, None))[1]
        if cap is not None:
            claimed.add(cap["id"])
        suffix = zone_suffix(cap["id"]) if cap is not None else ""
        reading = texts.get(suffix)
        figures.append({
            "index": i,
            "zone_id": g["id"],
            "caption_zone": cap["id"] if cap is not None else "",
            "caption": reading["text"] if reading else "",
        })
    return {
        "figures": figures,
        "unpaired_captions": [c["id"] for c in caps if c["id"] not in claimed],
    }


def figure_boxes(ref: str, root: Path = Path("."),
                 all_readings: dict | None = None) -> list[dict]:
    """One record per **printed** figure on a page, top first.

    `paired` returns one row per `GraphicZone`; the book does not. 16 figures in
    this corpus are set in several boxes — `1-276`'s fig. 138 *a, b, c*,
    `2-085`'s fig. 253 *a, b* — and the lettering that tells them apart lives
    inside the one caption. So this folds `paired`'s rows on the caption and each
    record is a thing the book numbers:

        {"key": "001",                    # the topmost picture zone's suffix
         "n": "87" | None,                # refs.figure_number(caption)
         "zone_ids": ["fig_1-207_001",…], # every picture box under this caption
         "caption_zone": "fig_1-207_004", # full id, as `paired` gives it; "" if none
         "caption": "Fig. 87, a …",
         "box": (x0, y0, x1, y1),         # union of the pictures; caption excluded
         "y": 938}                        # None box only if every zone id is dangling

    **`box` excludes the caption and `y` does not, and the difference is the
    point.** `box` is what gets cropped, and a crop wants the picture: the
    caption is already carried as text, and on the ~19 plates whose caption is
    set rotated beside the picture, including it would widen the crop by the
    height of a line of type turned on its side. `y` is where the *figure* sits
    for placement purposes, which is the top of whichever of its parts comes
    first — the definition `generate._figures_with_geometry` has always used, and
    it is preserved exactly so that folding that function onto this one cannot
    move a single figure in `mz/tei/`. Measured: the two agree on all 398 figures
    today, a caption never being set above its picture. The byte-identical
    regeneration is what witnesses it if that ever stops being true.

    **Captionless artwork is never folded.** `3-006` and `3-007` carry a picture
    the book captions nowhere, and an empty caption is not evidence that two such
    pictures are one figure, so each keys on its own zone id instead. That is the
    same reasoning as `paired`'s `text: ""` note, one level up.

    `key` is the topmost picture's zone suffix, which is what names the crop.
    Deliberately not the figure number — plate figures restart at 1 on every
    plate and collide with the text-figure series, 10 figures print no number at
    all, and a number is a *reading* of the caption where a zone id is the
    store's own foreign key, the one `save_figs` preserves where `zones.save_zones`
    re-mints. Deliberately not a page-local ordinal either: `docs/apparatus.md`
    records that shape failing twice, the zone count not being the figure count
    in either direction.

    `all_readings` is a `readings(root)` a caller already holds, handed down to
    `paired` — the same `idx=` idiom `readings_for` documents, extended one rung
    because `generate` is the sweep that needed it: without it a 691-page run
    re-reads the whole caption store 691 times.
    """
    ref = norm_ref(ref)
    boxes = {b["id"]: b for b in zones(ref, root)}
    groups: dict[str, list[dict]] = {}
    for f in paired(ref, root, all_readings)["figures"]:
        # An empty caption groups by zone id, i.e. not at all. `paired` has
        # already sorted by position, so first-seen is topmost throughout.
        groups.setdefault(f["caption"] or f"\0{f['zone_id']}", []).append(f)

    out = []
    for members in groups.values():
        pics = [boxes[m["zone_id"]] for m in members if m["zone_id"] in boxes]
        first = members[0]
        # `y` exactly as the generator has always computed it: over the first
        # member's own picture and caption zones, not over the union.
        tops = [boxes[z]["vpos"] for z in (first["zone_id"], first["caption_zone"])
                if z in boxes]
        rec = {
            "key": zone_suffix(first["zone_id"]),
            "n": figure_number(first["caption"]),
            "zone_ids": [m["zone_id"] for m in members],
            "caption_zone": first["caption_zone"],
            "caption": first["caption"],
            "box": (min(p["hpos"] for p in pics),
                    min(p["vpos"] for p in pics),
                    max(p["hpos"] + p["width"] for p in pics),
                    max(p["vpos"] + p["height"] for p in pics)) if pics else None,
            "y": min(tops) if tops else 0,
        }
        out.append(rec)
    return sorted(out, key=lambda f: f["y"])


#: Fallback for `figures.float_min_residual` when the book's config omits it.
#: **A knob, not a discovery** — the real one lives in `data/zones_config.json`,
#: because it is a fact about how a particular book sets its pictures and this
#: pipeline is meant for more than one. A default here only keeps a config that
#: predates the key working.
FLOAT_MIN_RESIDUAL = 0.33


def layout(ref: str, root: Path = Path(".")) -> dict:
    """The page's figures with their placement relative to the text column.

    **The column is read, not measured, and that is what makes this cheap.**
    `zones.measure_frame` derives a column from the page's ink, which costs a
    raster decode and can fall back; but every zone a human keys is drawn against
    the configured column, so the answer is already in `gt/zones/`. Measured over
    all **719 keyed pages: every page's zones share exactly one `(x0, x1)`**, and
    its width is exactly the part's configured measure. So one zone is the whole
    answer, no pixels are opened, and the reading view can call this per request.

    `source` is `"zones"` or `"none"`, decided by whether the page has zones at
    all — **never by whether it is a plate.** 113 of the 115 exempt pages have
    none, which is right (a plate has no prose to wrap), but `1-245` and `1-316`
    do, and a rule keyed on plate-hood would get those two wrong in a way nothing
    would notice.

    Per figure, on top of `figure_boxes`:

        left_frac   where the union starts, as a share of the measure
        width_frac  how much of the measure the union covers, clamped to 1.0
        overflows   True if the union runs outside the column at all
        side        "left" | "right" | "full"
        parts       one entry per keyed picture, each with its own left_frac,
                    width_frac and overflows

    **`side` is the group's and the sizes are the parts'.** A figure is one block in
    the flow and floats as one, but its pictures keep their own widths: the store
    spells a lettered figure as several boxes under one caption, `write_crops` cuts
    one image per box, and sizing every one of them by the union stretches the
    narrow ones. Measured here: 24 of the 32 parts across 16 multi-part groups, the
    worst `2-085`'s fig. 253 at x3.95. The union survives for ordering and for
    `side`, and is not a size.

    `side` is `full` when the residual gutter is under `FLOAT_MIN_RESIDUAL` of
    the measure — what is left could not hold a line of type — and otherwise the
    side with the smaller gutter, ties left.

    **What this reproduces is where the box sat, which is not the same as knowing
    the print wrapped text around it.** Zones are always the full measure, so the
    store cannot witness a wrap; a figure that sat in the left half of the
    measure is evidence for floating it left and no more than that. The reading
    view marks it as such rather than presenting recovered layout.
    """
    from . import zones_config as zc
    from .zones import read_zones
    ref = norm_ref(ref)
    figs = figure_boxes(ref, root)
    zs = read_zones(ref, root)
    if not zs:
        return {"ref": ref, "column": None, "source": "none", "figures": figs}
    # Read off the raw config rather than through `load_config`, which validates
    # the whole document and raises `ConfigError` — a `ValueError` subclass — for
    # defects that have nothing to do with this number. Going through it would
    # mean an unrelated typo in `types` silently reverted the threshold to the
    # module default, which is precisely the quiet decision this project refuses.
    # A presentation default is not worth refusing to render a page over, so a
    # missing key falls back; a *malformed* one does not, and says so.
    residual = FLOAT_MIN_RESIDUAL
    try:
        raw = json.loads(zc.config_path(root).read_text(encoding="utf-8"))
        val = (raw.get("figures") or {}).get("float_min_residual")
    except (OSError, ValueError):
        val = None
    if val is not None:
        residual = float(val)

    cx0, cx1 = zs[0]["x0"], zs[0]["x1"]
    measure = max(1, cx1 - cx0)
    boxes = {b["id"]: b for b in zones(ref, root)}

    def place(x0: int, x1: int) -> dict:
        """One rectangle's share of the measure."""
        # Clamped before the gutters are taken, so a box that overruns the column
        # cannot produce a negative gutter and read as hugging the opposite side.
        lo, hi = max(x0, cx0), min(x1, cx1)
        width = max(0, hi - lo)
        return {"left_frac": round((lo - cx0) / measure, 4),
                "width_frac": round(min(1.0, width / measure), 4),
                "overflows": x0 < cx0 - 5 or x1 > cx1 + 5}

    out = []
    for f in figs:
        if f["box"] is None:
            out.append({**f, "left_frac": 0.0, "width_frac": 1.0,
                        "overflows": False, "side": "full", "parts": []})
            continue
        x0, y0, x1, y1 = f["box"]
        lo, hi = max(x0, cx0), min(x1, cx1)
        width = max(0, hi - lo)
        gl, gr = lo - cx0, cx1 - hi
        # `side` is the **group's**, from the union, and stays that way: a figure is
        # one block in the flow and floats as one, whatever its parts do inside it.
        side = ("full" if (measure - width) / measure < residual
                else "left" if gl <= gr else "right")
        # `parts` is each keyed picture's own share of the measure. **The size comes
        # from the part and never from the union**, which is `write_crops`' rule one
        # layer up: a bounding box over boxes a human drew separately "is a region
        # no human drew", and `1-276`'s fig. 140 has its two boxes stacked at
        # different widths. `write_crops` cuts per picture, so a renderer sizing
        # every crop by the group's union scales the narrow ones up to it —
        # measured over this store, 24 of the 32 parts in 16 multi-part groups,
        # worst `2-085` fig. 253 at x3.95, a 304 px woodcut drawn 1202 px wide.
        parts = [{"zone_id": z, **place(boxes[z]["hpos"],
                                        boxes[z]["hpos"] + boxes[z]["width"])}
                 for z in f["zone_ids"] if z in boxes]
        out.append({**f, **place(x0, x1), "side": side, "parts": parts})
    return {"ref": ref, "column": {"x0": cx0, "x1": cx1, "measure": measure},
            "source": "zones", "figures": out}


def by_number(root: Path = Path(".")) -> dict[str, list[dict]]:
    """`{printed number: [{"ref", "key"}, …]}` over the whole figure store.

    The List of Illustrations names a figure by its printed number and says
    nothing about where it is; `figure_boxes` knows where every figure is and
    what number its caption carries. This is the join, and it is what lets the
    LoI's entries link to the pictures they describe.

    **A list per number, never one entry.** Plate figures restart at 1 on every
    plate and so collide with the text-figure series outright, which is the same
    reason `figure_boxes` keys on a zone suffix rather than a number. A caller
    that wants a link takes the single-element case and prints plain text
    otherwise — resolving a two-element list to one would be inventing the
    answer the collision is telling it nobody has.

    Numbers are the caption's own, as `refs.figure_number` read them, and are
    kept as strings for that reason: `figure_boxes` does not parse them into
    integers and neither does this.

    **Then `data/figure_numbers.json` overrides, because a printer who set a page
    his own way is not a rule to be widened.** Three figures in this corpus have
    no derivable number — the map on `1-037`, whose number is set after the title,
    and `2-068`'s 239 and 240, two pictures above two stacked captions that the
    pairing read as one two-box figure. Bending either derivation to admit them
    would mis-fire on every leaf that is ordinary; a human names them instead. A
    patch **replaces** its number's derived entries rather than joining them, so a
    number a rule already got half-right does not end up ambiguous by being
    corrected — which is also what takes the swallowed picture back off 239.
    """
    out: dict[str, list[dict]] = {}
    for ref in fig_refs(root):
        for f in figure_boxes(ref, root):
            if f.get("n"):
                out.setdefault(str(f["n"]), []).append(
                    {"ref": ref, "key": f["key"], "keys": crop_keys(f)})
    for p in number_patches(root):
        out[str(p["n"])] = [{"ref": p["ref"], "key": p["keys"][0],
                             "keys": list(p["keys"])}]
    return out


def number_patches(root: Path = Path(".")) -> list[dict]:
    """`data/figure_numbers.json`'s entries, or none if the file is absent.

    An editor's table, not a derivation: each entry says which zones on which
    leaf a printed figure number names, and `why` records what the rule saw
    instead. Absent is empty rather than an error — a corpus whose printers
    behaved needs no patches, and this reads as a store like any other.
    """
    p = Path(root) / "data" / "figure_numbers.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("figures") or []


def check_number_patches(root: Path = Path(".")) -> list[dict]:
    """What is wrong with the patch table, as a list of rows; empty is clean.

    **A patch asserts a fact about `gt/fig/` and so must fail rather than go
    stale.** Its whole licence is that a human looked at the leaf; re-box that
    leaf and the zone it names may be gone, at which point the entry is a claim
    about a page that no longer exists. So the zones are checked against the
    store on every run, the same reason `#gt` and `#mz` are re-derived.
    """
    bad = []
    for p in number_patches(root):
        n, ref, keys = str(p.get("n", "")), p.get("ref", ""), p.get("keys") or []
        if not n or not ref or not keys:
            bad.append({"n": n, "ref": ref, "rule": "n, ref and keys are required"})
            continue
        if not str(p.get("why", "")).strip():
            bad.append({"n": n, "ref": ref, "rule": "no `why`: a patch has to say "
                                                    "what the rule saw instead"})
        have = {k for f in figure_boxes(ref, root) for k in crop_keys(f)}
        missing = [k for k in keys if k not in have]
        if missing:
            bad.append({"n": n, "ref": ref,
                        "rule": f"no such picture zone: {', '.join(missing)}"})
    seen: dict[str, int] = {}
    for p in number_patches(root):
        seen[str(p.get("n", ""))] = seen.get(str(p.get("n", "")), 0) + 1
    bad += [{"n": n, "ref": "", "rule": f"{c} entries patch this number"}
            for n, c in sorted(seen.items()) if c > 1]
    return bad


def _match_key(s: str) -> str:
    """A caption reduced for matching a printed list's abbreviated version of it
    against the keyed one under the picture.

    **Combining marks come off, and that is a matching device rather than a
    claim about a glyph**: the List of Illustrations sets Plate I's village as
    `Nuˊnligren` where the under-figure caption has `Nuˊnlig̣ren`, one place
    named twice by one printer. The fold lives inside one comparison and reaches
    no store.

    **Nothing here knows what book this is.** An earlier version stripped a
    leading `Fig. N.` from the caption, which is this book's convention and
    another book's mistake; it turned out to be unnecessary, since the list's
    segment is a substring of the fuller caption either way. Removing it costs
    nothing — still 35 of 35 — and takes the last book-specific token out of the
    match.
    """
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def by_plate(plates: list[dict], root: Path = Path(".")) -> dict[str, dict]:
    """`{plate number: {"ref", "keys"}}` — where each plate actually is, `keys`
    being every picture zone on that leaf, in printed order.

    **The one thing that locates a plate, and it has to be derived.** A plate is
    an inserted leaf carrying no folio and no number of its own on the page; the
    printed list gives it a roman numeral and an "Opp. page", and the figure
    store gives every picture on every leaf. Nothing joins them but the caption
    the printer set twice — abbreviated in the list, in full under the picture.

    `plates` is passed in rather than read, so this module keeps its back to the
    apparatus stores: `resolve_figures` takes both sides the same way and for
    the same reason.

    **Every segment must be found, and exactly one leaf must qualify.** A plate
    naming three villages must find all three on one page. Anything looser
    matched `1-227` and `1-231` to each other's plates on a shared word, and
    anything that resolves to two leaves resolves to none — the caller links
    what is here and prints the rest plain, since a picture shown under the
    wrong plate is worse than a plate with no picture.

    Order inside a leaf is `in_printed_order`'s: a rotated plate numbers as the
    turned page reads, and `1-049` runs 3, 1, 2 down the paper.

    **Why not compute the leaf from the stated folio instead**, which looks like
    less machinery: because it is both less general and less right. The printed
    list's numbers do follow a parity rule here — an odd "Opp. page" is the leaf
    the plate faces, an even one the leaf before it — but that rule is an
    empirical property of *this* volume, where this match knows nothing about any
    book. Scored against this function over the 35: parity gets **21 right, 8
    wrong and 6 unresolved**. The 8 are the dangerous kind — it puts Plate VI on
    `1-123`, which is Plate V's leaf, and Plate VII on `1-129`, which is Plate
    VI's — a confident answer under the wrong caption. The 6 include every plate
    in parts 2 and 3, whose facing folio no page has yet witnessed; a caption
    needs no folio index and reaches them all.
    """
    pages = {ref: [_match_key(f["caption"]) for f in figure_boxes(ref, root)
                   if f["caption"]]
             for ref in fig_refs(root)}
    out: dict[str, dict] = {}
    for p in plates:
        segs = [_match_key(s) for s in (p.get("segments") or [p.get("caption", "")])]
        segs = [s for s in segs if s]
        if not segs:
            continue
        hits = [ref for ref, caps in pages.items()
                if all(any(s in c for c in caps) for s in segs)]
        if len(hits) != 1:
            continue
        ref = hits[0]
        out[str(p.get("number"))] = {
            "ref": ref,
            # **Every picture on the leaf, not every figure.** `key` names the
            # topmost box of a folded record, so keying on it showed one part of
            # a multi-box plate and silently dropped the rest — Plate V is two
            # boxes under one caption and linked as one. The consumers all take
            # `ref/key` as a handle on a *crop*, which is a zone, so the leaf's
            # zone suffixes are what it owes them; the folding stays where it
            # belongs, in ordering the figures and in what a caption covers.
            "keys": [k for f in in_printed_order(figure_boxes(ref, root))
                     for k in crop_keys(f)],
        }
    return out


def in_printed_order(figs: list[dict]) -> list[dict]:
    """The page's figures in the order the book numbers them, where it can be.

    `figure_boxes` sorts by position, which is right for placing a figure in
    prose and wrong for showing a page's figures in succession: **a rotated
    plate numbers as the turned page reads.** `1-049` runs 3, 1, 2 down the
    sheet and `1-227` runs 2, 4, 1, 3 — 20 of the 115 exempt pages present their
    figures in an order the book does not use, so position would show a reader
    Fig. 3 first on a page whose own caption says Fig. 1.

    **Only when every figure on the page prints a number**, because a partial
    ordering would have to decide where the unnumbered one goes, and there is
    nothing to decide it with. `1-215` is the live instance and keeps its
    geometric order. Same discipline as everywhere else here: the rule takes what
    is mechanical and declines the rest rather than inventing a tiebreak.

    Not a reading, and not a claim about the sheet: the printed numbers are the
    book's own sequence, read off captions a human keyed.
    """
    if not all(f.get("n") for f in figs):
        return list(figs)
    try:
        return sorted(figs, key=lambda f: int(f["n"]))
    except (TypeError, ValueError):
        # A book whose figure numbers are not integers ("12a", "IV"). Position is
        # the honest fallback; guessing a collation order for arbitrary strings
        # would be a rule about one book's numbering pretending to be general.
        return list(figs)


def resolve_figures(handles: list[dict], figs: list[dict]) -> list[dict]:
    """Match each `<figure>` in a page's TEI to the figures the store holds.

    `handles` is `tei_html`'s `[{n, i}]` in document order; `figs` is `layout`'s
    list. Returns one row per handle, `figure` being the matched record or None.

    **`@n` first, because a printed number is the book's own handle**, and it is
    matched only when it identifies exactly one figure on the page. Over Bogoras
    no page has two figures sharing a number; a book where one does gets an
    unresolved row naming the collision rather than the first of the pair.

    **The unnumbered fall back to document order, and only while there is one of
    them on the page.** The generator emits a numberless caption as a bare
    `<figure/>` with no attribute at all, so order is the only handle left — but
    order in the *file* stops matching order on the *page* the moment a collator
    moves a figure to the sentence that refers to it, which is exactly what the
    collation contract asks them to do. With one such figure the question does
    not arise. With two it is unanswerable by rule, and this refuses instead of
    pairing them off in the order they happen to appear.

    **Anything unresolved shows as a marked gap.** Never "the next unused crop":
    a wrong picture under a right caption is precisely the fluent nonsense this
    project is built against, and it is invisible — the caption reads correctly
    and the image is simply of something else. An unresolved figure is a question
    on the page, and a question is what a collator answers. That is the division
    throughout: the rule takes what is mechanical and hands over what is not.

    One function because the reading view and `corpus figures`' gate both need
    this answer, and two implementations of it could disagree about a page while
    each looked right on its own.
    """
    by_n: dict[str, list[dict]] = {}
    for f in figs:
        if f["n"]:
            by_n.setdefault(f["n"], []).append(f)
    unnumbered = [f for f in figs if not f["n"]]

    # More than one numberless figure on a page makes document order a guess
    # rather than a handle, because collation moves figures. Refuse the lot.
    ambiguous = len([h for h in handles if not h["n"]]) > 1 or len(unnumbered) > 1

    out, used = [], 0
    for h in handles:
        if h["n"]:
            hit = by_n.get(h["n"]) or []
            # Two figures sharing a printed number on one page is a store defect,
            # not something to break a tie in. Report it unresolved and say why.
            match = hit[0] if len(hit) == 1 else None
            why = "" if match else ("no figure with this number" if not hit
                                    else f"{len(hit)} figures share n={h['n']}")
        elif ambiguous:
            match, why = None, (
                "several figures here print no number, and once a figure has been "
                "moved to its anchor the order in the file is not the order on the "
                "page — say which picture this is")
        elif used < len(unnumbered):
            match, why = unnumbered[used], ""
            used += 1
        else:
            match, why = None, "unnumbered, and the store has no figure left"
        out.append({**h, "figure": match, "why": why})
    return out


def reconcile(root: Path = Path("."), tick: Callable | None = None) -> dict:
    """Check `gt/fig/` against itself and against the source PDF's photographs.

    Empty `missing` is the invariant: a FigDesc block carrying no caption text is
    a caption nobody has read, and `fig restore` is what fills it.

    **There is no `orphan` any more, and its removal is the point of the
    retirement.** It meant "a reading whose zone is gone" and it was the other
    half of a cross-check between two stores — `data/readings.md` held the text,
    this store held the geometry, and either could name a block the other did not.
    The text now lives on the block, so a caption cannot outlive the thing it
    captions and the list could only ever be empty. A check that cannot fail is a
    clean bill of health nobody issued, so it is gone rather than reassuring.

    What that cross-check was really guarding is now guarded by construction, and
    by `save_figs`, which refuses a geometry save that would drop a block holding
    ratified text.
    """
    from .parallel import ptrack

    known = readings(root)
    by_ref: dict[str, dict] = {}
    for r in known.values():
        by_ref.setdefault(r["ref"], {})[r["zone_suffix"]] = r
    missing, unpaired = [], []
    zones, caps = 0, 0
    for ref in ptrack(fig_refs(root), tick):
        unpaired += [f"{ref}|{zone_suffix(z)}"
                     for z in paired(ref, root, known)["unpaired_captions"]]
        tree = etree.parse(str(alto_for(ref, root)))
        labels = _labels(tree)
        ids = set()
        for blk in tree.iter("{*}TextBlock"):
            lab = _block_label(blk, labels)
            if lab == GRAPHIC:
                zones += 1
            elif lab == FIGDESC:
                caps += 1
                ids.add(zone_suffix(blk.get("ID")))
        have = set(by_ref.get(ref, {}))
        missing += [f"{ref}|{z}" for z in sorted(ids - have)]
    seen_refs = {r["ref"] for r in known.values()}
    keyed_refs = set(fig_refs(root))

    # The third store, and the only one of the three no person and no model wrote:
    # the source PDFs' own image placements. `unaccounted` is the gate — a
    # photograph the book contains and this store does not mention. `unkeyed` is a
    # page carrying photographs with no figure ALTO at all, which is the same fault
    # one level up and is listed separately so the fix is obvious. `line_art` is
    # the reverse direction and **never gates**: a keyed picture the PDF did not
    # separate out is line work the scanner left in the bitonal master, which is
    # ordinary.
    manifest = pdf_images(root)
    unaccounted, unkeyed, loose = [], [], []
    rects_total = 0
    for ref, entry in sorted(manifest.items()):
        n = len(entry.get("images") or [])
        if not n:
            continue
        rects_total += n
        if ref not in keyed_refs:
            unkeyed.append(f"{ref}({n})")
            continue
        ink = fig_ink(ref, root)
        if ink["state"] == "unaccounted":
            unaccounted += [f"{ref}|{r[0]},{r[1]}" for r in ink["uncovered"]]
        loose += [f"{ref}|{o['share']:.2f}" for o in ink["outside"]]

    # The reverse direction, counted and not listed: a keyed picture no photo rect
    # overlaps is line work the scanner left in the bitonal master. Ordinary, so it
    # is a number rather than a worklist. (`read_blocks` directly, because `zones`
    # the module function is shadowed here by `zones` the counter.)
    line_art = 0
    for ref in sorted(keyed_refs):
        entry = manifest.get(ref) or {}
        blocks = read_blocks(alto_for(ref, root))
        pw, ph = _page_box(alto_for(ref, root))
        rects, space = _rects_in(entry, pw, ph) if entry else ([], "")
        for b in blocks:
            if b["label"] != GRAPHIC:
                continue
            box = (b["hpos"], b["vpos"], b["hpos"] + b["width"],
                   b["vpos"] + b["height"])
            if not any(_overlaps(r, box) for r in rects):
                line_art += 1

    return {
        "pages": len(fig_refs(root)),
        "graphic_zones": zones,
        "figdesc_zones": caps,
        "readings": len(known),
        "refs_in_readings": len(seen_refs),
        "pdf_photographs": rects_total,
        "unaccounted": unaccounted,
        "unkeyed_photo_pages": unkeyed,
        "line_art_pictures": line_art,
        "loose_boxes": loose,
        "missing": missing,
        # A caption no picture claimed. Reported rather than gated: `missing` is a
        # fact about the store's own contents, where this is a *geometric* reading
        # of it and `paired`'s rule is the only witness against it. It should
        # always be empty — see `paired`.
        "unpaired_captions": unpaired,
    }
# A `misordered` column was built here and removed, and the reasoning is worth
# keeping because it looks like a free second witness and is not. It checked
# `paired`'s geometric order against the figure numbers the captions themselves
# print, expecting them to come out ascending. Over the corpus it reported 19
# pages, and **not one was a pairing error** — every pairing on the five worked
# through by hand (`1-227`, `1-049`, `1-117`, `1-260`, `2-181`) is right. What it
# had found was two properties of the book:
#
#   * a **rotated plate numbers in rotated reading order**. `1-227` reads
#     `2,4,1,3` upright and `1,2,3,4` once the page is turned to read its own
#     bottom-to-top captions;
#   * the book does not always number geometrically at all. `1-260` numbers the
#     tall right-hand figure 123, between two figures in the left column.
#
# So the check cannot separate a pairing error from a page set that way, and its
# whole output was permanent known-false rows in a report whose value is that
# `missing` and `orphan` are empty. Signal buried by noise, in the one place the
# noise could not be reduced.


# `graphic_zones`, `snapshot` and `caption_crops` lived here and were removed: no
# caller anywhere in the package, the tools, or the skills, and `caption_crops` was
# referenced only inside a comment in `lines.py`. They were written against a figure
# build that does not exist yet; when it does, it will want its own crop geometry
# rather than these, and git has them either way. `caption_blocks` went with them —
# `snapshot` and `caption_crops` were its only callers.
#
# `fig_refs` and `alto_for` look like they belong to the same dead cluster and do
# not: `reconcile()` above calls both, and `reconcile` is reachable as
# `harness corpus figures`.


# ---------------------------------------------------------------------------
# Caption crops
#
# Crops are taken from the FigDesc **zone box**. There is nothing else left to
# crop from — the per-line boxes are gone with the TextLines — but the zone box
# was the right unit anyway: the line segmentation used to drop whole printed
# lines (on `1-146` it lost "Boot of Curried Reindeer-Skin." out of the middle of
# fig. 27's caption), and a zone crop keeps a dropped line visible where a line
# crop would reproduce the loss. This is the path back to the page when a reading
# is in doubt.

SHEET_W = 1800    # composite sheet width
GUTTER = 14       # vertical space between strips
LABEL_W = 90      # left margin reserved for the index number

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _scale_for(alto_page, image_size) -> tuple[float, float]:
    """Ratio between the ALTO's coordinate space and the raster's.

    Returns (1.0, 1.0) once the two agree. Deriving this rather than assuming
    it means crops are correct whether or not the coordinate rescale has run,
    and it never hardcodes 2 — no page is exactly double (see docs/rasters.md).
    """
    aw = float(alto_page.get("WIDTH"))
    ah = float(alto_page.get("HEIGHT"))
    return image_size[0] / aw, image_size[1] / ah


CROPDIR = "scans/fig-crops"

#: Where a human's version of a picture goes, and the whole reason it is a
#: *separate, tracked* directory rather than an edit in place.
#:
#: `scans/fig-crops/` is derived: `fig crops --force` rewrites every file in it
#: and it is gitignored, so a touched-up figure left there would be destroyed by
#: the next rebuild with no copy anywhere. That is this repository's one
#: catastrophic failure re-enacted — 17 of 20 hand-keyed pages were once
#: replaced by export shells because a file's role lived only in the name of the
#: directory holding it. The rule that came out of it holds here unchanged:
#: **a store's name is its role, and nothing writes through a view.**
#:
#: **Under `ed/`, not `gt/`.** This lived in `gt/` on the argument that "`gt/` is
#: what a human has been through", which is true of a retouched crop and is not
#: what the rank means: `gt/` is the artifact reproduced or annotated, and an
#: enhanced figure is an improvement on what the page shows — the one direction
#: that rank excludes. The tracked-and-never-rebuilt property that made this a
#: store in the first place is an argument about the store, not the rank, and
#: survives the move unchanged.
#:
#: Named `fig-img/` and deliberately not `figs/`, which sat one character from
#: the `gt/fig/` geometry store — the same near-miss `_exempt.lst` /
#: `_exempt.json` was renamed to avoid. Under `ed/` the collision is gone and the
#: name is kept anyway: it still says what the files are, and renaming a store
#: twice in one move is how a path in a doc goes stale.
#:
#: Enhancement is **manual by design**. Nothing in this module sharpens,
#: denoises, upscales or otherwise improves a picture: a crop is the pixels the
#: raster has inside a box a human drew. An enhanced figure is a new artefact
#: somebody made and vouches for, so it arrives as a file in a tracked store,
#: not as a filter in a pipeline.
FIG_IMG = "ed/fig-img"


def crop_source(ref: str, key: str, root: Path = Path(".")) -> tuple[Path, str]:
    """Where one figure's picture comes from, and whose it is.

    Returns `(path, rank)` — `"ed"` for a human's file in `ed/fig-img/`, `"mz"`
    for the machine crop. The human file wins, exactly as `ocr/` resolves over
    `gt/ocr/` and `mz/ocr/`, and for the same reason: a reader wants the best
    available version and every consumer must resolve it the same way.

    The path is returned whether or not it exists; the caller reports a missing
    machine crop as a build that has not run.
    """
    ref = norm_ref(ref)
    human = root / FIG_IMG / crop_name(ref, key)
    if human.exists():
        return human, "ed"
    return root / CROPDIR / crop_name(ref, key), "mz"


def crop_name(ref: str, key: str) -> str:
    """The filename one figure's crop takes. `1-151`, `001` -> `chukchi-1-151-001.png`.

    One function because three callers need to agree exactly — the writer, the
    farm's membership computation, and the route that serves them — and a name
    re-derived per caller is the drift this module's `read_blocks` docstring
    already records the cost of.
    """
    return f"chukchi-{norm_ref(ref)}-{key}.png"


def write_crops(ref: str, out_dir: Path, root: Path = Path("."),
                scans: str = "scans", force: bool = False) -> list[dict]:
    """Crop every printed figure on one page out of its raster. Returns the records.

    **Pad 0 — the declared box and not a pixel more.** This is the blot's rule,
    and `docs/pipeline.md` records why it is the blot's rule: the pad was
    "rejected precisely because body text sits hard against an inset figure on
    `1-283`". A pad would pull prose into the crop on every page shaped like that
    one. Note this is the opposite choice from `lines.line_box`, which pads
    (`PAD_X = 56`) on purpose — a line crop exists for a human to read *in
    context*, and a figure crop exists to be the figure.

    **One crop per declared `GraphicZone`, never a union of several.** A union was
    tried first, on the reasoning that the book calls `1-276`'s fig. 140 one
    figure and letters its parts inside a single caption — and the area cost
    looked negligible, the worst union being 1.75× its parts. Looking at the
    output is what refuted it: fig. 140's two boxes are stacked at different
    widths, so their bounding rectangle spans the text column beside the upper
    one and the crop came out with six lines of body prose in it. **1.75× of
    *area* was 1.75× of *page*, and the page there is text.** A bounding box over
    boxes a human drew separately is a region no human drew, which is the whole
    of why this store holds rectangles rather than one box per figure.

    So the mechanical act stays mechanical — a declared box becomes an image —
    and holding the parts of fig. 140 together is presentation: `figure_boxes`
    groups them under their one caption and the reader stacks that group's crops
    beneath a single `<figcaption>`. Nothing is lost and nothing is invented.

    **A crop newer than both its inputs is left alone**, `lines.write_line_crops`'
    rule verbatim and for its reason: served as files, an unconditional re-save
    gives every crop a new mtime and a new `ETag` on every build, so nothing ever
    caches. The name encodes the geometry via the zone id, so a crop whose name
    still matches and whose file postdates the ALTO and the raster is the crop
    those two produce. `force` overrides it.
    """
    from PIL import Image

    from .lines import raster_path
    ref = norm_ref(ref)
    figs = figure_boxes(ref, root)
    if not figs:
        return []

    alto = alto_for(ref, root)
    raster = raster_path(ref, root, scans)
    page = etree.parse(str(alto)).find(".//{*}Page")
    src = max((p.stat().st_mtime for p in (alto, raster) if p.exists()), default=0.0)

    boxes = {b["id"]: b for b in zones(ref, root)}
    # Flattened to (figure, picture) pairs first, so the write loop is one level
    # deep and every part still knows the figure it belongs to.
    parts = [(f, boxes[z]) for f in figs for z in f["zone_ids"] if z in boxes]

    out_dir.mkdir(parents=True, exist_ok=True)
    img = None
    # Lazily, beside the decode and for its reason: a page whose every crop is
    # already fresh writes nothing and should read nothing either.
    sha: str | None = None
    sx = sy = 1.0
    recs = []
    for f, z in parts:
        key = zone_suffix(z["id"])
        path = out_dir / crop_name(ref, key)
        # `n` and `group` travel with every part, so a consumer can stack the
        # three crops of fig. 138 under its one caption without re-deriving the
        # grouping `figure_boxes` already did. `human` says a person's version of
        # this picture exists in `ed/fig-img/` and is what readers will see —
        # reported on every run, because a rebuild that silently shadowed one
        # would make the manual work look lost.
        rec = {"ref": ref, "key": key, "n": f["n"], "group": f["key"],
               "name": path.name,
               "human": (root / FIG_IMG / crop_name(ref, key)).exists()}
        if not force and path.exists() and path.stat().st_mtime >= src:
            recs.append(rec | {"written": False, "why": "fresh"})
            continue
        # Opened once, and only if something actually needs writing — the decode
        # is the whole cost of this pass (see .claude/rules/zones.md).
        if img is None:
            img = Image.open(raster)
            sx, sy = _scale_for(page, img.size)
        x0, y0 = z["hpos"], z["vpos"]
        x1, y1 = x0 + z["width"], y0 + z["height"]
        box = (max(0, round(x0 * sx)), max(0, round(y0 * sy)),
               min(img.size[0], round(x1 * sx)), min(img.size[1], round(y1 * sy)))
        if box[2] <= box[0] or box[3] <= box[1]:
            # A box entirely off the raster. `fig check` already errors on this;
            # here it is a row rather than a crash, so one bad page cannot stop a
            # corpus sweep.
            recs.append(rec | {"written": False, "why": "off-raster"})
            continue
        if sha is None:
            sha = provenance.digest(raster)
        img.crop(box).save(path, pnginfo=provenance.png_meta(provenance.Producer(
            step="harness fig crops", label="one figure's box cut from the page",
            kind="rule", version=str(RASTER_VERSION),
            inputs={"source": raster.name, "source_sha256": sha, "ref": ref,
                    "store": "gt/fig", "key": key, "group": f["key"],
                    "n": f["n"]})))
        recs.append(rec | {"written": True, "why": ""})
    return recs


def crop_all(refs: list[str] | None = None, root: Path = Path("."),
             out_dir: Path | None = None, scans: str = "scans",
             force: bool = False, jobs: int | None = None, tick=None) -> dict:
    """Crop the named pages, or every page the figure store holds.

    Threaded on `parallel.pmap` for `zones blot`'s reason: the PNG decode is the
    whole cost and it releases the GIL, so threads get most of the win without an
    interpreter per worker. `--jobs 1` builds no pool and is the control arm.
    """
    from .parallel import pmap
    dest = Path(out_dir) if out_dir is not None else root / CROPDIR
    todo = [norm_ref(r) for r in refs] if refs else fig_refs(root)

    def one(ref: str) -> dict:
        try:
            recs = write_crops(ref, dest, root, scans, force)
        except FileNotFoundError as e:
            return {"ref": ref, "figures": 0, "written": 0, "fresh": 0,
                    "off_raster": 0, "human": 0, "note": str(e).split(":")[0]}
        return {
            "ref": ref,
            "figures": len(recs),
            "written": sum(1 for r in recs if r["written"]),
            "fresh": sum(1 for r in recs if r["why"] == "fresh"),
            "off_raster": sum(1 for r in recs if r["why"] == "off-raster"),
            "human": sum(1 for r in recs if r["human"]),
            "note": "",
        }

    rows = list(pmap(one, todo, jobs, tick))
    return {
        "dir": str(dest.relative_to(root)) if dest.is_relative_to(root) else str(dest),
        "pages": len(rows),
        "figures": sum(r["figures"] for r in rows),
        "written": sum(r["written"] for r in rows),
        "fresh": sum(r["fresh"] for r in rows),
        "off_raster": sum(r["off_raster"] for r in rows),
        "human": sum(r["human"] for r in rows),
        "rows": rows,
    }


def crops_wanted(root: Path = Path(".")) -> dict[str, str]:
    """`{crop filename: the ref it comes from}` over the whole figure store.

    The farm's membership, computed from `gt/fig/` rather than from what happens
    to be on disk — which is what lets `views check` say `stale` when a keyed box
    gained or lost a crop, instead of only noticing an empty directory.

    **One entry per `GraphicZone`, which is what `write_crops` writes.** These two
    have to enumerate the same set or the farm reports drift against itself
    forever, so this reads the zones directly rather than going through
    `figure_boxes`' grouping — the grouping is about captions and has no say in
    how many images exist.
    """
    return {crop_name(ref, zone_suffix(b["id"])): ref
            for ref in fig_refs(root)
            for b in zones(ref, root) if b["label"] == GRAPHIC}


#: Vertical pad on a caption strip, as a multiple of the block's own height.
#:
#: **The opposite choice from `write_crops`' pad 0, and for the opposite reason.**
#: A picture crop wants the picture, so a pad there pulls body prose in. A caption
#: crop exists for somebody to *read the type*, and the commonest defect in this
#: store is a box drawn around the wrong number of printed lines — the very failure
#: that stripped the `TextLine`s in the first place. A strip cut at the declared
#: edge cannot show a line the box excluded, so the reader would reproduce the
#: segmentation's mistake with no way to see it. The pad is what makes a dropped
#: line visible, and the rule drawn at the declared edge is what keeps it honest
#: about which pixels the store actually claims.
CAP_PAD = 0.6


def caption_strips(ref: str, root: Path = Path("."), scans: str = "scans",
                   pad: float = CAP_PAD):
    """One padded, upright image per `GraphicZone-FigDesc` on a page.

    Yields `(key, image, record)` in reading order, `key` being `<ref>|<suffix>` —
    the key the store files each caption under, so a reading taken off these strips
    joins it block for block when `fig witness` compares them.

    **Portrait strips are rotated, and the discriminator is `paired`'s own.** A
    plate sets its caption rotated beside the picture, reading bottom-to-top —
    `1-049`'s three are 86×457, 92×506, 82×636 against a text figure's 610×96 — so
    `width >= height` is what tells the two apart, exactly as `_gap` uses it to
    decide whether to look below a picture or beside it. Deriving it from the box
    rather than from a prior classification of the page means a mixed page comes
    out right zone by zone, and it needs no threshold anyone has to calibrate.

    The rotation is presentation and **nothing about it reaches `gt/fig/`**: the
    record carries `orientation` so the reading can be keyed back, and the store
    keeps saying what it said.
    """
    from PIL import Image

    from .lines import raster_path
    ref = norm_ref(ref)
    caps = [b for b in zones(ref, root) if b["label"] == FIGDESC]
    if not caps:
        return
    caps.sort(key=lambda b: (b["vpos"], b["hpos"]))

    alto, raster = alto_for(ref, root), raster_path(ref, root, scans)
    if not raster.exists():
        return
    page = etree.parse(str(alto)).find(".//{*}Page")
    img = Image.open(raster)
    sx, sy = _scale_for(page, img.size)

    for b in caps:
        x0, y0 = b["hpos"], b["vpos"]
        x1, y1 = x0 + b["width"], y0 + b["height"]
        # Padded on the reading axis only. A rotated caption reads along y in page
        # space, so its "next line" is sideways — padding the wrong axis there would
        # widen the strip into the picture and show nothing a reader needs.
        upright = b["width"] >= b["height"]
        grow = int(round((b["height"] if upright else b["width"]) * pad))
        if upright:
            cy0, cy1, cx0, cx1 = y0 - grow, y1 + grow, x0, x1
        else:
            cy0, cy1, cx0, cx1 = y0, y1, x0 - grow, x1 + grow
        box = (max(0, int(cx0 * sx)), max(0, int(cy0 * sy)),
               min(img.width, int(cx1 * sx)), min(img.height, int(cy1 * sy)))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        strip = img.crop(box)

        # The declared edge, drawn on the padded strip: everything between the two
        # rules is what the store claims, everything outside is what it left out.
        # Without this the pad would silently enlarge the box in the reader's mind,
        # which is the same defect as no pad at all wearing the other hat.
        from PIL import ImageDraw
        strip = strip.convert("L")
        d = ImageDraw.Draw(strip)
        if upright:
            for edge in (int(y0 * sy) - box[1], int(y1 * sy) - box[1]):
                d.line([(0, edge), (strip.width, edge)], fill=190, width=1)
        else:
            for edge in (int(x0 * sx) - box[0], int(x1 * sx) - box[0]):
                d.line([(edge, 0), (edge, strip.height)], fill=190, width=1)
            # Bottom-to-top type turned upright to read left-to-right. **ROTATE_270,
            # not ROTATE_90**: PIL rotates counter-clockwise, and this type already
            # reads bottom-to-top, so a second counter-clockwise turn stands it on
            # its head. Verified against `1-049`'s three plate captions rather than
            # reasoned about — the first attempt was upside down and looked, at a
            # glance, merely rotated.
            strip = strip.transpose(Image.Transpose.ROTATE_270)

        key = f"{ref}|{zone_suffix(b['id'])}"
        yield key, strip, {"key": key, "ref": ref,
                           "suffix": zone_suffix(b["id"]),
                           "orientation": "upright" if upright else "rotated",
                           "pad": grow, "box": [x0, y0, x1, y1]}


def write_caption_sheets(out_dir: Path, root: Path = Path("."),
                         refs: list[str] | None = None, scans: str = "scans",
                         per_sheet: int = 12, pad: float = CAP_PAD,
                         tick: Callable | None = None) -> dict:
    """Tile every caption in the corpus onto contact sheets. Returns the manifest.

    **The sheet is the unit of work for this pass, and the census is why.** 151 of
    the 250 captioned pages hold exactly one caption; the median caption is 66
    characters over one or two printed lines. Dealing that out a page at a time —
    a directory, a queue entry and an agent apiece — would be scaffolding standing
    in for a store. Twelve strips to a sheet puts the whole corpus in ~33 images.

    `compose_sheets` already does the tiling, draws each strip's label in the left
    margin and rules between strips, so a reading keys back to its zone without
    relying on order. Its own docstring notes captions are the case where
    downscaling costs nothing: the reading is of ordinary words, not of whether a
    dot sits under a `g`.

    The manifest is what the reader and the review page both read back — key to
    sheet, orientation, and the pad each strip carries.
    """
    from .parallel import ptrack

    refs = [norm_ref(r) for r in (refs or fig_refs(root))]
    items, recs = [], {}
    for ref in ptrack(refs, tick):
        for key, strip, rec in caption_strips(ref, root, scans, pad):
            items.append((key, strip))
            recs[key] = rec
    if not items:
        return {"sheets": [], "captions": 0, "blocks": {}}

    sheets, index = compose_sheets(items, out_dir, per_sheet=per_sheet,
                                   prefix="captions",
                                   producer=_sheet_producer(
                                       "harness fig sheets",
                                       "caption strips tiled for reading",
                                       {"store": "gt/fig", "scans": scans,
                                        "pad": pad, "captions": len(recs),
                                        "refs": len(refs)}))
    for entry in index:
        for i, key in enumerate(entry["items"]):
            recs[key]["sheet"] = entry["sheet"]
            recs[key]["strip"] = i
    man = {"sheets": [p.name for p in sheets], "captions": len(recs),
           "per_sheet": per_sheet, "pad": pad, "blocks": recs}
    write_atomic(out_dir / "manifest.json",
                 json.dumps(man, ensure_ascii=False, indent=1))
    return man


def write_caption_zoom(key: str, out_dir: Path, root: Path = Path("."),
                       zoom: int = 2, scans: str = "scans",
                       overlap: int = 60, sheet_h: int = 1600,
                       client_w: int = 1450) -> list[dict]:
    """One caption block, magnified and sliced into strips that fill the client.

    The reading pass reached for `convert` with hand-typed pixel bounds, which is
    the failure `lines.write_line_zoom` was built to end one store over: bounds
    nobody can check, naming the wrong region the moment a coordinate is
    fat-fingered. Here the region is `caption_strips`' own, so a zoom is the *same*
    block enlarged rather than a second guess at where it is.

    **Pad 0, unlike the contact sheet.** The sheet pads to show a printed line the
    box may have missed; a zoom answers a question about a glyph inside the box, and
    padding it would spend magnification on the neighbours.

    2x by default and 4x the ceiling, the project's rule: at 4x a strip returns
    about a fifth of a caption, so a whole one costs several images, and there is no
    rung above because filtering manufactures evidence rather than revealing it.
    """
    from PIL import Image

    from .lines import ZOOM_MAX, sheet_namer, zoom_window

    if not 1 <= zoom <= ZOOM_MAX:
        raise ValueError(f"zoom is 1..{ZOOM_MAX}; {zoom} is past the ceiling, and "
                         "past it magnification stops adding evidence")
    ref, _, suffix = key.partition("|")
    if not suffix:
        raise ValueError(f"{key!r} is not a caption key — they are "
                         "`PP-NNN|<zone-suffix>`, as `harness fig sheets` labels "
                         "every strip and as the manifest lists them")
    strip = next((s for k, s, _ in caption_strips(ref, root, scans, pad=0.0)
                  if k == key), None)
    if strip is None:
        raise ValueError(f"{key} names no caption block on {ref}")

    window = zoom_window(zoom, client_w)
    step = max(1, window - overlap)
    resample = Image.Resampling.NEAREST
    strips = []
    for i, x in enumerate(range(0, max(1, strip.width - overlap), step)):
        s = strip.crop((x, 0, min(strip.width, x + window), strip.height))
        strips.append((f"{suffix}.{i}",
                       s.resize((s.width * zoom, s.height * zoom), resample)))

    sheets, index = compose_sheets(strips, out_dir, per_sheet=len(strips),
                                   sheet_w=client_w, max_h=sheet_h,
                                   name_for=sheet_namer(f"{ref}-zoom{zoom}"),
                                   producer=_sheet_producer(
                                       "harness fig zoom",
                                       "one caption block magnified in strips",
                                       {"store": "gt/fig", "scans": scans,
                                        "ref": ref, "key": key, "zoom": zoom}))
    return [{"sheet": str(out_dir / e["sheet"]), "key": key, "zoom": zoom,
             "strips": " ".join(e["items"])} for e in index]


def _add_text_line(blk, lines: list[str]):
    """One `TextLine` on a FigDesc block, carrying the block's own bbox verbatim.

    The bbox is copied rather than re-derived, so a store whose coordinates are
    floats keeps floats and the `TextLine` can never claim a region the block does
    not. The `String`s take no geometry: 27,595 of 27,595 in `gt/ocr/` carry none,
    so that is the corpus's practice rather than a liberty taken here.

    Shared by `save_caption_text` and `save_figs` — the writer and the rebuild —
    because two spellings of this shape is how the rebuild would come to emit a
    `TextLine` the reader does not recognise.
    """
    from .zones import ALTO_NS

    tl = etree.SubElement(blk, f"{{{ALTO_NS}}}TextLine", {
        "ID": f"{blk.get('ID')}_l1",
        "HPOS": blk.get("HPOS"), "VPOS": blk.get("VPOS"),
        "WIDTH": blk.get("WIDTH"), "HEIGHT": blk.get("HEIGHT")})
    for line in lines:
        etree.SubElement(tl, f"{{{ALTO_NS}}}String", {"CONTENT": line})
    return tl


def block_text(blk) -> list[str]:
    """The printed lines a FigDesc `TextBlock` carries, or `[]`.

    One `String` per printed line inside one `TextLine`. Reading it back is a
    list, never a joined string, for the reason the store keeps the division at
    all: **31 of the 196 multi-line captions carry a hyphen at the break and they
    are not the same kind of hyphen.** `Leaf-Tobacco`, `Netting-Shuttles`,
    `Ice-Scoop` are compounds the book hyphenates and a join must keep tight;
    `Walrus-Hunt-ing` and `attach-ing` are wrap artifacts and a join must drop the
    hyphen. Nothing mechanical separates them, so the break is the evidence that
    the question exists, and a reader that flattens it has thrown that away.
    """
    return [s.get("CONTENT") or ""
            for tl in blk.iter("{*}TextLine")
            for s in tl.findall("{*}String")]


def save_caption_text(ref: str, root: Path = Path("."), texts: dict | None = None,
                      stamp: str | None = None) -> dict:
    """Write caption text into one page's `gt/fig/` ALTO, keeping the geometry.

    **Parses the tree and edits it; never rebuilds it.** `save_figs` goes through
    `zones.build_alto`, which mints a whole file from `{label, box, id}` — right
    for geometry and fatal here, because a rebuild is exactly how the ids that key
    this text would move. Nothing structural is touched: the `TextLine` is
    inserted under the block it belongs to, after the `Shape`, and every
    coordinate in the file is the one that was already there.

    `texts` maps a zone suffix to its list of printed lines. A block the caller
    does not name is left exactly as it is, so this is an overlay rather than a
    replacement — a page can be restored twice without the second run needing to
    re-supply the first's.

    The `TextLine` takes the **block's own bbox** and the `String`s take no
    geometry at all. That is not a liberty: 27,595 of 27,595 `String` elements in
    `gt/ocr/` carry no `HPOS`, so a geometry-less `String` is this corpus's
    universal practice. What is new is *several* of them under one `TextLine` —
    the maximum anywhere else is one — and it is new because a caption's printed
    lines are a property of its box rather than of separate boxes: the segmenter
    that would have given each its own baseline is the one that dropped whole
    lines, which is why they were stripped in the first place.

    Durability is the store's own: copy to `.prev`, write `.tmp`, `replace()`, and
    append to `gt/fig/_journal.jsonl`. A write here that no journal records would
    be the one write nothing can reconstruct.
    """

    ref = norm_ref(ref)
    texts = texts or {}
    p = alto_for(ref, root)
    if not p.exists():
        raise ValueError(f"{ref} has no figure ALTO — absence of the file is how "
                         f"this store says 'no figures here', and a caption "
                         f"cannot be written into a page that has none")
    tree = etree.parse(str(p))
    labels = _labels(tree)

    wrote, skipped = [], []
    for blk in tree.iter("{*}TextBlock"):
        if _block_label(blk, labels) != FIGDESC:
            continue
        suffix = zone_suffix(blk.get("ID"))
        lines = texts.get(suffix)
        if lines is None:
            skipped.append(suffix)
            continue
        for old in blk.findall("{*}TextLine"):
            blk.remove(old)
        tl = _add_text_line(blk, lines)
        # Indented as the block's existing children are, so the first geometry save
        # after this does not reformat all 250 files as diff noise on top of
        # whatever box it actually moved. Both values are read off the file rather
        # than assumed: `blk.text` is the whitespace that indents `Shape`, and the
        # last child's tail is the whitespace that closes the block. The new
        # `TextLine` takes the first and inherits the second.
        prev = blk.find("{*}Shape")
        if prev is not None and blk.text and not blk.text.strip():
            tl.tail, prev.tail = prev.tail, blk.text
        wrote.append(suffix)

    missing = sorted(set(texts) - set(wrote))
    if missing:
        raise ValueError(
            f"{ref}: {', '.join(missing)} name no GraphicZone-FigDesc on this "
            f"page. A block id's last field is the key this text is filed under, "
            f"and writing text for a block that is not there would put a reading "
            f"in a file with nothing to attach it to.")

    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    tmp = tmp_for(p)
    # `lxml` ends the document at `</alto>` with no newline; `save_figs`' writer
    # ends with one, because `pretty_print` adds it. Two conventions in one store
    # means whichever verb touched a page last shows up as a whitespace diff on
    # the next one, so this settles on the one that already covers most of the
    # store and is the ordinary shape of a text file.
    tree.write(str(tmp), encoding="UTF-8", xml_declaration=True)
    with tmp.open("ab") as fh:
        fh.write(b"\n")
    tmp.replace(p)
    with (fig_dir(root) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"saved_at": stamp, "ref": ref, "captions": wrote,
                             "untouched": skipped}, ensure_ascii=False) + "\n")
    return {"ref": ref, "written": len(wrote), "untouched": len(skipped),
            "blocks": wrote}


def caption_manifest(root: Path = Path(".")) -> dict:
    """The sheet manifest, or `{}` before `harness fig sheets` has run."""
    from .paths import caption_sheets_dir
    p = caption_sheets_dir(root) / "manifest.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _chunk_sheets(items, per_sheet: int, max_h: int | None):
    """Split (label, image) pairs into sheet-sized runs, in order.

    `per_sheet` alone cannot express what a magnified sheet needs. Every viewer
    downscales an image to fit *both* its dimensions, so a sheet taller than the
    display resamples the whole thing down and cancels the magnification it was
    built to deliver — a strip enlarged 3× and then fitted into a 2000 px box has
    been enlarged by rather less. So the packing constraint is total height, and a
    count cap only bounds it when every strip is the same height, which line crops
    are not.
    """
    run, used = [], GUTTER
    for label, im in items:
        cost = im.height + GUTTER
        if run and (len(run) >= per_sheet
                    or (max_h is not None and used + cost > max_h)):
            yield run
            run, used = [], GUTTER
        run.append((label, im))
        used += cost
    if run:
        yield run


def _sheet_producer(step: str, label: str, inputs: dict) -> provenance.Producer:
    """A contact sheet's producer, for the callers that build one.

    **No `source_sha256`, and its absence is the honest report rather than an
    omission.** A caption sheet tiles strips cut from *many* rasters — the whole
    keyed corpus, on a full run — so there is no one master to digest, and a field
    naming one of them would be a witness to the wrong file. What identifies the
    picture is the store the strips were cut by and the labels on it, both of
    which are here. The single-raster cutters use `lines._raster_producer`, which
    does carry the digest because it has one to carry.
    """
    return provenance.Producer(step=step, label=label, kind="rule",
                               version=str(RASTER_VERSION), inputs=inputs)


def compose_sheets(items, out_dir: Path, per_sheet: int = 10, prefix: str = "sheet",
                   sheet_w: int = SHEET_W, max_h: int | None = None,
                   name_for=None, producer: provenance.Producer | None = None):
    """Tile (label, image) pairs into indexed composite sheets.

    Each strip gets its index drawn in the left margin and a rule beneath it, so
    a reading can be keyed back to a zone without relying on order alone. Strips
    wider than the sheet are scaled down; nothing is scaled up, since upsampling
    print costs legibility for no gain.

    `sheet_w` is a parameter and not the constant because the caller may know that
    no strip should be scaled at all. Downscaling is cheap for a caption, where the
    reading is of ordinary words; it is not cheap for a body line, where the whole
    question is whether a dot sits under a `g` — see `lines.write_line_sheets`,
    which sizes the sheet to the widest crop for exactly that reason.

    `max_h` caps a sheet's height as well as its strip count; see `_chunk_sheets`.

    **`producer` is the caller's, because only the caller knows what was cut.**
    This function tiles labelled pictures and has no idea whether they are caption
    crops, body lines or magnified strips, nor which raster or store they came off
    — so a record invented here would name the tiler and omit everything a reader
    needs. Each sheet takes the caller's record with its own `n` and its first and
    last label folded in, which is what joins a sheet back to the lines on it: the
    returned index says the same thing and is thrown away with the process.

    `name_for(labels) -> str` names each sheet after **what is on it** instead of its
    position in this call. Sequential numbering is only safe when a directory has one
    writer: `<prefix>-001.png` means "the first sheet of whatever was last asked
    for", so two `--only` selections over one page overwrite each other and each
    call's returned index goes on naming files that now hold the other's pictures.
    Content-derived names make an overlapping call *reuse* a file rather than fight
    over it, which is also what makes re-running a selection idempotent. Duplicates
    within a single call — a line whose strips straddle two sheets — take a `-b`,
    `-c` suffix in chunk order, since the packing is deterministic.
    """
    from PIL import Image, ImageDraw, ImageFont
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype(FONT_PATH, 26)
    except OSError:
        font = ImageFont.load_default()

    sheets, index, used = [], [], {}
    for chunk in _chunk_sheets(items, per_sheet, max_h):
        scaled = []
        for label, im in chunk:
            avail = sheet_w - LABEL_W - 20
            if im.width > avail:
                h = max(1, round(im.height * avail / im.width))
                im = im.resize((avail, h), Image.Resampling.LANCZOS)
            scaled.append((label, im))
        height = sum(im.height + GUTTER for _, im in scaled) + GUTTER
        sheet = Image.new("L", (sheet_w, height), 255)
        draw = ImageDraw.Draw(sheet)
        y = GUTTER
        for label, im in scaled:
            sheet.paste(im.convert("L"), (LABEL_W, y))
            draw.text((10, y + 4), label.split(":")[0], fill=0, font=font)
            y += im.height + GUTTER
            draw.line([(0, y - GUTTER // 2), (sheet_w, y - GUTTER // 2)], fill=180, width=1)
        if name_for is None:
            stem = f"{prefix}-{len(sheets) + 1:03d}"
        else:
            stem = name_for([lab for lab, _ in chunk])
            k = used.get(stem, 0)
            used[stem] = k + 1
            if k:
                stem = f"{stem}-{chr(ord('b') + k - 1)}"
        path = out_dir / f"{stem}.png"
        labels = [lab for lab, _ in chunk]
        if producer is None:
            sheet.save(path)
        else:
            sheet.save(path, pnginfo=provenance.png_meta(replace(
                producer, inputs={**producer.inputs, "n": str(len(chunk)),
                                  "first": labels[0], "last": labels[-1]})))
        sheets.append(path)
        index.append({"sheet": path.name,
                      "items": [lab for lab, _ in chunk]})
    return sheets, index
