"""The figure-caption track: `gt/fig/` for geometry, `data/readings.md` for text.

**The two are separate stores and neither substitutes for the other.** The 252
figure ALTOs in `gt/fig/` carry `GraphicZone` blocks (the images) and
`GraphicZone-FigDesc` blocks (where a caption sits) — 414 and 395 of them
respectively — and **no `TextLine` at all**: every line was stripped, because the
exported line segmentation dropped whole printed lines and a line-level witness
in the ALTO would have silently disagreed with the readings. So the caption text
lives only in `data/readings.md`, one block per FigDesc zone, keyed
`<ref>|<zone-id suffix>` and read by hand off the 300 dpi scans.

Anything that wants caption text must go through `readings()`. Reading
`String/@CONTENT` out of `gt/fig/` returns the empty string for every zone on every
page — not an error, just nothing, which is the worst possible failure here.

There is no longer a keyed/unkeyed boundary. All 395 captions in
`data/readings.md` are hand-read, so the old `KEYED_COUNT = 50` marker is gone;
`gt/fig/` and `data/readings.md` reconcile 1:1 in both directions, and that
reconciliation is the check worth running — `reconcile()` below.

Zone types are read from `OtherTag/@LABEL`, never from the tag ID. The IDs are
per-export (`BT55`/`BT56` in one export, `BT68`/`BT69` in the next) and code
that hardcodes them fails silently rather than loudly.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

from lxml import etree

from .context import norm_ref, parse_ref

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


def zone_suffix(block_id: str) -> str:
    """The part of a block id that keys `data/readings.md`.

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
        p.write_text("".join(e + "\n" for e in entries), encoding="utf-8")
    return {"ref": ref, "split": split}


def load_rule_exempt(root: Path = Path("."),
                     store: str = FIGDIR) -> dict[str, list[str]]:
    p = fig_dir(root, store) / RULE_EXEMPT_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return {k: list(v) for k, v in data.items()} if isinstance(data, dict) else {}


def set_rule_exempt(ref: str, rules: list[str], root: Path = Path("."),
                    store: str = FIGDIR) -> dict:
    """Record which warnings a human has accepted on this page.

    An exempted rule **still reports**, flagged — the zone store's discipline, for
    its reason: a warning that vanishes when excused leaves no way to notice that
    the excuse has outlived the page it was written for.
    """
    ref = norm_ref(ref)
    data = load_rule_exempt(root, store)
    if rules:
        data[ref] = sorted(set(rules))
    else:
        data.pop(ref, None)
    p = fig_dir(root, store) / RULE_EXEMPT_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True,
                            ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ref": ref, "rules": data.get(ref, [])}


# ---------------------------------------------------------- the segmenter
#
# The zone track's quartet, mirrored, with one difference that decides everything
# else: **this model trains on the raw `scans/`**, where zones-seg trains on
# `scans/w-figs-blotted/`. It has to — the blot paints figures white, and a figure
# segmenter cannot learn from pages where its target has been erased. That is also
# why the two are separate models rather than one with four classes: they read
# different rasters.
WORKDIR = "train/bogoras-fig"
MODELDIR = "models/bogoras-fig"
MODEL_NAME = "fig-seg"
DEFAULT_MODEL = f"{MODELDIR}/{MODEL_NAME}.safetensors"


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
        if splits.get(ref) == "exempt" or alto_for(ref, root).exists():
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
    """Lay out `train/bogoras-fig/` for `ketos segtrain`, and report the command.

    ketos resolves a page's image through the ALTO's own
    `sourceImageInformation/fileName`, relative to the XML, so each page's file and
    its raster sit together under the name the ALTO already carries.

    **The raster is the raw `scans/` page, never the blot.** `zones assemble` links
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

    work = root / WORKDIR
    for p in sorted(work.glob("*")) if work.exists() else []:
        if p.is_file() or p.is_symlink():
            p.unlink()
    work.mkdir(parents=True, exist_ok=True)

    splits = load_splits(root, FIGDIR)
    lists: dict[str, list[str]] = {"train": [], "eval": []}
    positives = synthesized = 0
    missing: list[str] = []
    for ref, split in sorted(splits.items(), key=lambda kv: parse_ref(kv[0])):
        scan = root / "scans" / f"chukchi-{ref}.png"
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
        lists[split].append(f"{WORKDIR}/{name}.xml")

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
            device=device, workers=workers, load=load, work=WORKDIR,
            out=f"{WORKDIR}/run-{_fig_next_run(root)}"),
    }
    notes = [n for n in (base_note,
                         "pages with no raster were left out of both lists"
                         if missing else "") if n]
    if notes:
        out["note"] = "; ".join(notes)
    return out


def predict(refs: list[str], root: Path = Path("."),
            model_path: str | Path | None = None, device: str = "auto",
            force: bool = False) -> list[dict]:
    """Run the figure segmenter over pages and write raw ALTO into `mz/fig/`.

    Input is the **raw scan**, matching what the model was trained on and unlike
    `zones predict`, which reads the blot. **No exempt skip**: plates are exempt in
    the zone track and are exactly where figures live.

    `--force` to overwrite, because an `mz/` file's `ProcessingStep` is the store's
    only witness to which model wrote it, and quietly replacing one loses that.
    """
    from .zones import _model_sha256, load_segmenter

    model_path = model_path or DEFAULT_MODEL
    net, sha, dev = None, "", device
    out = []
    for ref in refs:
        ref = norm_ref(ref)
        dest = alto_for(ref, root, MZFIGDIR)
        scan = root / "scans" / f"chukchi-{ref}.png"
        if not scan.exists():
            out.append({"ref": ref, "wrote": False, "note": "no raster"})
            continue
        if dest.exists() and not force:
            out.append({"ref": ref, "wrote": False, "note": "exists; --force"})
            continue
        if net is None:
            net, dev = load_segmenter(model_path, device)
            sha = _model_sha256(root / model_path if not Path(model_path)
                                .is_absolute() else Path(model_path))
        out.append(_predict_one(ref, root, net, dev, model_path, sha, dest))
    return out


def _predict_one(ref, root, net, dev, model_path, sha, dest) -> dict:
    from kraken import blla
    from PIL import Image

    from .zones import build_alto

    with Image.open(root / "scans" / f"chukchi-{ref}.png") as s:
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
    desc = tree.getroot().find("{*}Description")
    from lxml import etree as _et
    steps = _et.SubElement(desc, "{http://www.loc.gov/standards/alto/ns-v4#}"
                                 "Processing")
    _et.SubElement(steps, "{http://www.loc.gov/standards/alto/ns-v4#}"
                          "processingStepDescription").text = (
        f"{model_path} sha256:{sha[:16]} device:{dev}")
    tmp = dest.with_suffix(".xml.tmp")
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
               standalone=None, pretty_print=True)
    tmp.replace(dest)
    return {"ref": ref, "wrote": True,
            "figures": sum(1 for b in blocks if b["label"] == GRAPHIC),
            "captions": sum(1 for b in blocks if b["label"] == FIGDESC)}


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

    work = root / WORKDIR
    lists = {s: work / f"{s}.lst" for s in FIG_SPLITS}
    missing = [s for s, p in lists.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"{WORKDIR}/{missing[0]}.lst is gone, so the split this run consumed "
            "cannot be frozen beside the model — re-run `harness fig assemble` "
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


def _fig_next_run(root: Path) -> int:
    n = 1
    while (root / WORKDIR / f"run-{n}").exists():
        n += 1
    return n


METS_NS = "http://www.loc.gov/METS/"
XLINK_NS = "http://www.w3.org/1999/xlink"


def build_mets(names: list[str]) -> str:
    """A METS manifest over a list of ALTO filenames, for eScriptorium import.

    The shape mirrors what eScriptorium itself exports: one
    `fileGrp USE="export"` listing the ALTOs, and a physical `structMap` with a
    `div TYPE="page"` each, in filename order — which for `chukchi-PP-NNN` is page
    order. No image fileGrp: on import the pages match images already in the
    document, exactly as on the round-trip of an export.
    """
    from xml.sax.saxutils import quoteattr

    files, divs = [], []
    for i, name in enumerate(names, 1):
        fid = f"export{i}"
        files.append(f'        <file ID="{fid}">\n'
                     f"          <FLocat xlink:href={quoteattr(name)}/>\n"
                     f"        </file>")
        divs.append(f'      <div TYPE="page">\n'
                    f'        <fptr FILEID="{fid}"/>\n'
                    f"      </div>")
    nl = "\n"
    return (f'<mets xmlns="{METS_NS}" xmlns:xlink="{XLINK_NS}">\n'
            f"  <fileSec>\n"
            f'    <fileGrp USE="export">\n{nl.join(files)}\n'
            f"    </fileGrp>\n"
            f"  </fileSec>\n"
            f'  <structMap TYPE="physical">\n'
            f'    <div TYPE="document">\n{nl.join(divs)}\n'
            f"    </div>\n"
            f"  </structMap>\n"
            f"</mets>\n")


def write_mets(root: Path = Path("."), out_dir: str | Path = "",
               store: str = FIGDIR) -> dict:
    """Write `METS.xml` for `gt/fig/` into a directory the caller names.

    **Never into the store.** The manifest that used to live in `gt/fig/METS.xml`
    was an eScriptorium export artifact, tracked, and describing a store that has
    since been rewritten under it — a manifest committed beside the thing it
    manifests is a second copy of the store's shape with nothing keeping the two
    honest. It is built on demand now, and `--out` is required so it cannot land
    back there by omission.

    The manifest names the ALTOs, so a caller zips the store's files and this
    manifest together at the zip root.
    """
    names = sorted(p.name for p in (root / store).glob("chukchi-*.xml"))
    if not names:
        raise ValueError(f"no chukchi-*.xml under {root / store}")
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "METS.xml"
    p.write_text(build_mets(names), encoding="utf-8")
    return {"path": str(p), "files": len(names),
            "first": names[0], "last": names[-1]}


def migrate_page(ref: str, root: Path = Path("."),
                 store: str = FIGDIR) -> dict:
    """One page reduced to bounding boxes with `fig_` ids. Computes, writes nothing.

    Returns `{ref, blocks, remap, before, after}` — `blocks` ready for `build_alto`,
    `remap` the old-to-new suffix map for the page's **FigDesc** blocks alone, since
    those are the ones `data/readings.md` keys by, and `before`/`after` the geometry
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
    (root / READINGS).write_text(new_text, encoding="utf-8")
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
    exempt = load_rule_exempt(root, store).get(ref, [])
    warnings = zc.fig_warnings(cfg, blocks, exempt)
    known = {r["id"] for r in (figs_cfg.get("rules") or [])}
    for r in exempt:
        if r not in known:
            err("unknown-exemption",
                f"{ref} exempts {r!r}, which is not a rule this config declares")

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
              stamp: str | None = None) -> dict:
    """Write one page's figure and caption boxes, atomically, and record the save.

    `blocks` are `{label, x0, y0, x1, y1}` and **optionally `id`**. The durability
    shape is `save_zones`': copy to `.prev`, write `.tmp`, `replace()`, append to an
    append-only journal.

    **An id that arrives is kept, and that is the whole reason this is not
    `save_zones` with a different directory.** A block id's last field is the key
    `data/readings.md` files its caption text under, so re-minting by position — as
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

    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tree = build_alto(ref, blocks, raster_size(ref, root), id_prefix="fig_")

    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".xml.prev").write_bytes(p.read_bytes())
    tmp = p.with_suffix(".xml.tmp")
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

    **It does not touch `data/readings.md`.** A deleted page's captions become
    orphans, which is exactly what `harness corpus figures` exists to report — a
    silent cascade from a geometry withdrawal into hand-read text would be a far
    worse outcome than a loud reconciliation failure. The report names them and a
    human decides.
    """
    ref = norm_ref(ref)
    p = alto_for(ref, root)
    splits = load_splits(root)
    rules = load_rule_exempt(root).get(ref, [])
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
            lst.write_text("".join(e + "\n" for e in entries), encoding="utf-8")
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


def readings(root: Path = Path(".")) -> dict[str, dict]:
    """`data/readings.md` parsed to `{"<ref>|<zone-suffix>": record}`.

    **This is the only source of caption text.** `gt/fig/` carries no `TextLine`.

    `lines` preserves the printed line breaks and the printed hyphenation —
    hyphens are load-bearing in Americanist notation, so joining is a rendering
    decision made downstream, not here. `note` is the raw `@note` text if any,
    and `keyword` the adjudication keyword it opens with, if any.

    A `**bold heading**` on its own line ends the reading and opens trailing
    commentary, kept out of `lines`/`text` and returned as `aside`. `2-030` uses
    this to park a superseded machine attempt beside the human key for
    comparison; folding the two together would have produced 53 lines of two
    different transcriptions of one caption, presented as the caption.
    """
    # NFD on read, matching the corpus form (keying spec section 1). The file is
    # hand-maintained and nothing but `harness corpus normalize` writes it, so it can drift
    # between edits; folding here means a caption's normal form cannot depend on
    # which session keyed it. NFD, never NFKC — NFKC rewrites U+1D4B and U+02D9,
    # which are inventory glyphs.
    p = root / READINGS
    if not p.exists():
        # Absence is `{}`, not an exception — the same disposition `read_blocks`
        # keeps for a missing ALTO, and for the same reason: this module's callers
        # ask "what has been read here" and "nothing" is a legitimate answer. It
        # matters beyond tidiness now that the editor asks on every page it draws,
        # where a corpus with no caption track at all must simply show none.
        return {}
    text = unicodedata.normalize("NFD", p.read_text(encoding="utf-8"))
    hits = list(_HDR.finditer(text))
    out = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[m.end():end].strip("\n")
        note = ""
        if "\n@note:" in "\n" + body:
            body, _, note = body.partition("@note:")
            note = note.strip()
        aside = ""
        cut = re.search(r"^\*\*.*\*\*\s*$", body, re.M)
        if cut:
            body, aside = body[:cut.start()], body[cut.start():].strip()
        lines = [ln for ln in body.strip().split("\n") if ln.strip()]
        out[f"{m.group(1)}|{m.group(2)}"] = {
            "ref": m.group(1),
            "zone_suffix": m.group(2),
            "lines": lines,
            "text": " ".join(lines),
            "note": note,
            "keyword": next((k for k in NOTE_KEYWORDS if note.startswith(k)), ""),
            "aside": aside,
        }
    return out


def readings_for(ref: str, root: Path = Path(".")) -> dict[str, dict]:
    """The readings on one page, keyed by bare zone-id suffix."""
    ref = norm_ref(ref)
    return {r["zone_suffix"]: r for r in readings(root).values()
            if r["ref"] == ref}


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


def paired(ref: str, root: Path = Path(".")) -> dict:
    """One record per figure — the picture, its caption — in reading order.

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
    are keyed by FigDesc suffix in `data/readings.md`), so an empty caption now
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
        texts = readings_for(ref, root)
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


def reconcile(root: Path = Path(".")) -> dict:
    """Cross-check `gt/fig/` against `data/readings.md` in both directions.

    Empty `missing` and `orphan` lists is the invariant. `missing` means a zone
    whose caption was never read; `orphan` means a reading whose zone is gone —
    usually a spurious FigDesc that was deleted from the segmentation, in which
    case the reading should go too.
    """
    known = readings(root)
    missing, orphan, unpaired = [], [], []
    zones, caps = 0, 0
    for ref in fig_refs(root):
        unpaired += [f"{ref}|{zone_suffix(z)}"
                     for z in paired(ref, root)["unpaired_captions"]]
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
        have = {r["zone_suffix"] for r in known.values() if r["ref"] == ref}
        missing += [f"{ref}|{z}" for z in sorted(ids - have)]
        orphan += [f"{ref}|{z}" for z in sorted(have - ids)]
    seen_refs = {r["ref"] for r in known.values()}
    orphan += [k for k, r in sorted(known.items())
               if r["ref"] not in set(fig_refs(root))]
    return {
        "pages": len(fig_refs(root)),
        "graphic_zones": zones,
        "figdesc_zones": caps,
        "readings": len(known),
        "refs_in_readings": len(seen_refs),
        "missing": missing,
        "orphan": sorted(set(orphan)),
        # A caption no picture claimed. Reported rather than gated: `missing` and
        # `orphan` are reconciliation between two stores that must agree, where
        # this is a geometric reading of one of them, and `paired`'s rule is the
        # only witness against it. It should always be empty — see `paired`.
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


def compose_sheets(items, out_dir: Path, per_sheet: int = 10, prefix: str = "sheet",
                   sheet_w: int = SHEET_W, max_h: int | None = None,
                   name_for=None):
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
        sheet.save(path)
        sheets.append(path)
        index.append({"sheet": path.name,
                      "items": [lab for lab, _ in chunk]})
    return sheets, index
