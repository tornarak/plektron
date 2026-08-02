"""Zones to text in one pass: `zones/` + a raster → lines → OCR → `mz/ocr/`.

The pipeline used to run as three unrelated acts with a human carrying state
between them — segment somewhere, recognize somewhere else, hand-link the result
into `ocr/`. This is that loop closed. One command per page, and what it produces
is a machine store beside the human one, reachable through the same view.

**Three stores, and the third is a view** — the shape `gt/zones/`, `mz/zones/`,
`zones/` already has, adopted here for the reason it was adopted there:

    gt/ocr/     what a human has been through. Tracked.
    mz/ocr/     what the models emitted. Derived, ignored.
    ocr/        the read view over both, the human file always winning.

**Reads may resolve through `ocr/`; writes name `gt/ocr/`.** Nothing here writes
into the ground truth — `restore` does that, from an adjudicated `decision.json`,
and `adopt_gaps` adds empty geometry. This module writes `mz/ocr/` and the view,
and it has no parameter in which a caller could name anywhere else.

## What the zones are for

`blla` finds baselines and its own regions; **its regions are discarded and ours
replace them.** That is the whole point of the pass. The old pipeline's regions
"had no semantic value and were only used to impose a reading order"; these carry
the seven declared types, so a line arrives already knowing whether it sits in a
running title, a paragraph, a footnote or a signature line. The collation pass
gets that structure for free instead of re-deriving it from the raster.

Zones come from the **`zones/` view**, so a page a human has keyed is read from
`gt/zones/` and a page only the segmenter has seen is read from `mz/zones/` — the
best available structure, with its provenance still readable from where the link
points. A page with no zones at all is refused rather than recognized flat: the
structure is what this pass exists to apply, and a page without it would land in
the store looking like any other, with nothing in it saying the zones were missing.

## The blotted raster, for both steps

Input is `scans-fig-blotted/`, the same page `zones predict` reads, and a page with
no blot is **refused** as it refuses one. Artwork otherwise raises baselines that
are not type, and every one is a spurious line a downstream consumer has to be told
to ignore.

**Nothing is lost to the blot, and that is a property of how it paints rather than
an acceptable cost.** It fills the *declared* figure box and not a pixel more — the
pad was considered and rejected precisely because body text sits hard against an
inset figure on pages like `1-283`, and padding would have erased it. So the type
survives; only the pictures go. Figure captions go too, since `gt/fig/` declares
`GraphicZone-FigDesc` as well, and they should: captions live in `data/readings.md`
and are not body text.

**A line whose baseline still falls in no zone is kept, not dropped.** It is
assigned to no region, counted, and reported as `lines_outside_zones`. Blotting
makes this rare rather than impossible — an undeclared figure, a plate, a smudge —
and dropping the remainder would be quieter and is exactly the failure that cost
this project a two-line paragraph on `1-053` and 18 pages before that: whatever
text is present reads as correct, so no detector disagrees with anything and the
page simply has less on it than the paper does. Junk in a draft is visible to the
human reading it. A hole is not.

That count is therefore a **signal, not noise**. Non-zero on an ordinary text page
means either a figure is undeclared or a zone is missing, which is what
`zones check --ink` catches from the other side.
"""
from __future__ import annotations

import dataclasses
import os
from functools import lru_cache
from pathlib import Path

from .context import norm_ref, parse_ref
from . import zones as Z

# The machine store, its human counterpart, and the view over both. `lines.py`
# spells the view `DEFAULT_ALTO_DIR = "ocr"`; these are the two real stores it
# resolves to, and the reason a writer must never take the view's name.
GTDIR = "gt/ocr"
MZDIR = "mz/ocr"
VIEWDIR = "ocr"

# Stock blla, named explicitly rather than left to kraken's bundled default, so a
# sha256 can travel in the file. A default nobody can point at is a provenance
# field that says "whatever was installed".
DEFAULT_SEG_MODEL = "models/blla.mlmodel"
# CATMuS print, large. Its competence here is known and narrow — ~91% on ASCII and
# **0% of the transcription inventory**, measured against the human-collated
# `tei/chukchi-1-151.xml` — so this store is a witness to line geometry and to
# English, and to nothing else. See CLAUDE.md's Collation section before treating
# any Tier-1 form in it as a reading.
DEFAULT_REC_MODEL = "models/catmus-print-fondue-large.mlmodel"

# Every id this pass mints. Provenance travelling with the data, as everywhere
# else here: a block or line merged out of context still says what made it.
ID_PREFIX = "mz_"
# The catch-all for lines no zone claimed. A distinct id stem rather than a flag
# somewhere, so filtering them is a string test on the ALTO alone.
UNZONED = "unzoned"


def mz_dir(root: Path = Path(".")) -> Path:
    return root / MZDIR


def alto_for(ref: str, root: Path = Path("."), store: str = MZDIR) -> Path:
    return root / store / f"chukchi-{norm_ref(ref)}.xml"


def has_text(ref: str, root: Path = Path("."), store: str = MZDIR) -> bool:
    """Whether this store holds a recognized page — file present, lines or not.

    The `has_zones` distinction, for the same reason: a file with no lines is a
    record that the pass ran and found nothing, and a missing file is a record
    that nobody ran it. Only the file's existence separates them.
    """
    return alto_for(ref, root, store).exists()


def ocr_refs(root: Path = Path("."), store: str = MZDIR) -> list[str]:
    """Every ref with a page in this store, in (part, scan index) order.

    Deduped by **real path**, in `zones.zone_refs`' form and for its reason: the
    `store` parameter makes the view reachable, and a walk that counted one inode
    under two names would undercount silently.
    """
    out, seen = [], set()
    for p in (root / store).glob("chukchi-*.xml"):
        try:
            if not p.exists():          # follows the link: a dangling entry is not a page
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


def load_recognizer(model_path: str | Path = DEFAULT_REC_MODEL,
                    root: Path = Path("."), device: str = "cpu"):
    """The recognition model, plus the sha256 that travels in every file.

    `kraken.lib.models.load_any` rather than `models.loaders.load_models`, and the
    difference matters: the latter returns a bare `TorchVGSLModel`, while `rpred`
    needs the `TorchSeqRecognizer` that wraps it with a decoder and a codec. Handed
    the unwrapped model it fails on a missing attribute rather than on a type, which
    reads as a damaged model instead of the wrong constructor.
    """
    from kraken.lib import models as lm

    p = Path(model_path)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        raise FileNotFoundError(
            f"no recognition model at {p}. `models/` carries stock CATMuS print "
            f"(large and tiny); {DEFAULT_REC_MODEL} is the default.")
    return lm.load_any(str(p), device=device), Z._model_sha256(p)


@lru_cache(maxsize=4)
def _resolve_device(device: str) -> str:
    """Cached: `torch.cuda.is_available()` initializes CUDA and costs ~1 s, and a
    GPU does not appear part-way through a process. `zones._runtime_flags` is
    cached for the same reason."""
    if device != "auto":
        return device
    try:
        import torch
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _own(line, bands: list[tuple[str, int, int]]) -> str | None:
    """Which zone this line sits in, by the midpoint of its baseline.

    The midpoint rather than any overlap fraction, because the zones are a
    *partition*: a baseline has exactly one y and belongs to whichever band
    contains it. An overlap rule would need a tie-break at every abutting
    boundary, and 545 of the corpus's boundaries abut exactly.
    """
    pts = line.baseline or line.boundary or []
    ys = [p[1] for p in pts]
    if not ys:
        return None
    mid = sum(ys) / len(ys)
    for rid, y0, y1 in bands:
        if y0 <= mid <= y1:
            return rid
    return None


def predict(ref: str, root: Path = Path("."), seg_net=None, seg_sha: str = "",
            rec_net=None, rec_sha: str = "",
            seg_model: str | Path = DEFAULT_SEG_MODEL,
            rec_model: str | Path = DEFAULT_REC_MODEL,
            device: str = "auto") -> dict:
    """Segment lines, recognize them, and write ALTO into `mz/ocr/`.

    A loaded model may be passed in — `predict_all` loads once for a whole sweep —
    but then its sha must come with it. A file written with `sha256: ""` carries
    provenance that is present, well-formed and says nothing, which is worse than
    absent because it reads as recorded; `zones.predict` refuses the same omission
    on the same grounds.
    """
    # Both refusals precede the imports: `from kraken import ...` pulls in torch and
    # costs ~1.9 s, and neither a page without a blot nor a page without zones ever
    # reaches a model. `zones.predict` orders itself the same way and says why.
    ref = norm_ref(ref)
    blot = Z.blot_dir(root) / f"chukchi-{ref}.png"
    if not blot.exists():
        raise FileNotFoundError(
            f"no blotted raster for {ref} at {blot} — run `harness zones blot` "
            "first. Falling back to `scans/` would put a page in the store whose "
            "lines were found under different conditions from every other one, "
            "with nothing in the file saying so.")

    zs = Z.read_zones(ref, root, store=Z.VIEWDIR)
    if not zs:
        raise ValueError(
            f"{ref} has no zones in `{Z.VIEWDIR}/` — key it in `harness zones "
            f"edit {ref}`, or run `harness zones predict {ref}`. Recognizing it "
            "flat would put a page in the store with no structure and nothing in "
            "it saying the structure was missing.")

    from PIL import Image
    from kraken import blla, rpred, serialization, containers
    from kraken.containers import ProcessingStep

    if seg_net is None:
        seg_net, seg_sha = Z.load_segmenter(seg_model, root)
    elif not seg_sha:
        raise ValueError("predict(seg_net=...) needs the model's sha256 too")
    if rec_net is None:
        rec_net, rec_sha = load_recognizer(rec_model, root, _resolve_device(device))
    elif not rec_sha:
        raise ValueError("predict(rec_net=...) needs the model's sha256 too")
    dev = _resolve_device(device)

    with Image.open(blot) as src:
        page = src.convert("RGB")
    size = page.size

    seg = blla.segment(page, model=seg_net, device=dev)

    # **Our regions replace blla's.** Each zone becomes one Region carrying its
    # declared label; the boundary is the zone's own rectangle, which it already is
    # in `gt/zones/` (a polygon that is not its own bounding box is a save-time
    # error there) and is the honest reduction of a free `mz/zones/` polygon.
    regions: dict[str, list] = {}
    bands: list[tuple[str, int, int]] = []
    for i, z in enumerate(zs, 1):
        rid = f"{ID_PREFIX}{ref}_r{i}"
        x0, y0, x1, y1 = z["x0"], z["y0"], z["x1"], z["y1"]
        # **`tags` is `{key: [{"type": label}]}`, not `{key: label}`**, and the
        # difference is silent. `serialization.serialize` builds its typology with
        # `for t in v if 'type' in t` — handed a bare string, that iterates
        # *characters*, matches none, and writes `TAGREFS=""` with a single
        # `OtherTag LABEL="default"`. Geometry, ids and reading order all survive,
        # so the file looks structured and carries no labels at all: the one thing
        # this pass exists to put in it, absent, with nothing saying so.
        regions.setdefault(z["label"], []).append(
            containers.Region(id=rid,
                              boundary=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                              tags={"type": [{"type": z["label"]}]}))
        bands.append((rid, y0, y1))

    order = {rid: i for i, (rid, _, _) in enumerate(bands)}
    placed = []
    for ln in (seg.lines or []):
        rid = _own(ln, bands)
        placed.append((ln, rid))
    outside = sum(1 for _, rid in placed if rid is None)

    # Reading order is zone order, then down the page inside a zone. Document order
    # in the written file therefore *is* reading order — unlike `gt/ocr/`, where the
    # two diverge on 18 of 20 pages because the ALTO's order is whatever the export
    # assigned. Nothing downstream may assume that of the gt store; it holds here
    # because this writer controls both.
    def sort_key(item):
        ln, rid = item
        ys = [p[1] for p in (ln.baseline or ln.boundary or [(0, 0)])]
        xs = [p[0] for p in (ln.baseline or ln.boundary or [(0, 0)])]
        return (order.get(rid, len(order)), min(ys), min(xs))

    placed.sort(key=sort_key)
    lines = [dataclasses.replace(ln, regions=[rid] if rid else [],
                                 id=f"{ID_PREFIX}{ref}_l{i}"
                                 if rid else f"{ID_PREFIX}{ref}_{UNZONED}{i}")
             for i, (ln, rid) in enumerate(placed, 1)]

    bound = dataclasses.replace(seg, lines=lines, regions=regions,
                                imagename=f"chukchi-{ref}.png")
    # **The records are what gets serialized, not the lines with `text` set on
    # them.** `serialization.serialize` reads `record.prediction` and nothing else
    # — a `BaselineLine` carrying `text` serializes to `CONTENT=""`, which is the
    # `gt/fig/` failure exactly: not an error, nothing, and a reader downstream
    # gets a well-formed page with no words on it. The records preserve the `id`
    # and `regions` set above, so the structure survives the round trip; verified
    # rather than assumed, because nothing in the types says so.
    records = list(rpred.rpred(rec_net, page, bound, no_legacy_polygons=True))
    text = [r.prediction or "" for r in records]

    steps = [
        ProcessingStep(id="harness-ocr-predict-lines", category="processing",
                       description="baseline segmentation, harness ocr predict",
                       settings={"model": str(seg_model), "sha256": seg_sha,
                                 "device": dev,
                                 "input": f"{Z.BLOTDIR}/chukchi-{ref}.png",
                                 "regions_from": f"{Z.VIEWDIR}/chukchi-{ref}.xml"}),
        ProcessingStep(id="harness-ocr-predict-text", category="processing",
                       description="recognition, harness ocr predict",
                       settings={"model": str(rec_model), "sha256": rec_sha,
                                 "device": dev}),
    ]
    # **`sub_line_segmentation=False`, and it is not a size optimization.**
    # `serialize` defaults it True, which makes the ALTO template walk each
    # record's per-character `cuts` and emit a `<String>` per word, an `<SP>` per
    # space and a `<Glyph>` per character: 3375 glyphs and 681 strings on `1-048`
    # where the store's other pages carry 49 strings, one per line, and a 30 KB
    # file becomes 1.4 MB.
    #
    # The size is the symptom. The reason to turn it off is that **this store must
    # be shaped like the one beside it**: `gt/ocr/` descends from eScriptorium
    # exports, one `<String CONTENT>` per `TextLine`, and `ocr/` is a view under
    # which a consumer reads either without asking which. `lines.page_lines` joins
    # a line's text by concatenating its `String`s, so both forms happen to read
    # alike today — which is precisely how a divergence like this survives: it
    # costs nothing until something reads `String/@CONTENT` expecting a line and
    # gets a word.
    #
    # Nothing is lost that this project uses. The per-glyph boxes and confidences
    # are kraken's own recognition detail; the corpus addresses text at the line,
    # `restore` writes at the line, and review crops at the line.
    xml = serialization.serialize(
        dataclasses.replace(bound, lines=records),
        image_size=size, template="alto", processing_steps=steps,
        sub_line_segmentation=False)

    out = mz_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    dest = alto_for(ref, root, MZDIR)
    tmp = dest.with_suffix(".xml.tmp")
    tmp.write_text(xml, encoding="utf-8")
    tmp.replace(dest)

    linked = link_one(ref, root)
    chars = sum(len(t) for t in text)
    return {"ref": ref, "path": str(dest), "zones": len(zs),
            "lines": len(lines), "lines_outside_zones": outside,
            "chars": chars, "linked": linked}


def predict_skip(ref: str, root: Path = Path("."), force: bool = False,
                 single: bool = False) -> str:
    """Why this page should not be recognized, or `""` to go ahead.

    One rule in one place, `zones.predict_skip`'s shape and its reasoning:

    - **an existing page is kept unless `force`**, because the file records the
      sha256 of the two models that wrote it, and re-running unasked after a model
      change would replace that record page by page and leave nothing able to say
      the store had ever held more than one pass's output;
    - **a page ruled `exempt` is refused**, `force` or not, unless `single` — a
      plate is not a text page, and a recognized plate sits in the store looking
      like any other reading. Naming a ref on the command line is `single`;
    - **a page with no zones is refused**, since the structure is what the pass
      applies. This is the one skip that is a missing *input* rather than a
      judgement, so it names the command that produces it.
    """
    if not single and Z.load_splits(root).get(ref) == "exempt":
        return "ruled not a text page"
    if not force and has_text(ref, root, MZDIR):
        return "already recognized"
    if not (root / "scans" / f"chukchi-{ref}.png").exists():
        return "no raster"
    if not Z.read_zones(ref, root, store=Z.VIEWDIR):
        return "no zones (run `harness zones predict`)"
    return ""


def predict_all(root: Path = Path("."), refs: list[str] | None = None,
                seg_model: str | Path = DEFAULT_SEG_MODEL,
                rec_model: str | Path = DEFAULT_REC_MODEL,
                device: str = "auto", force: bool = False) -> dict:
    """Recognize over a work-list, or over every page that has zones.

    What is skipped and why is `predict_skip`'s; this loops and reports. A sweep is
    **resumable by construction** — run it again and it picks up what has nothing —
    which over 832 pages of two models' inference is the difference between an
    interruption costing minutes and costing the run.

    Both models load once for the whole sweep, which is most of why this exists as
    a sweep rather than a shell loop over the single-page form.
    """
    if refs is None:
        refs = Z.zone_refs(root, Z.VIEWDIR)
    refs = [norm_ref(r) for r in refs]

    # **The work-list is decided before either model is loaded**, so re-running a
    # finished sweep to confirm it is finished costs a directory walk rather than
    # two checkpoints off disk. That is what makes "resumable" a thing you will
    # actually do rather than a property the docstring claims.
    todo, skipped = [], []
    for ref in refs:
        why = predict_skip(ref, root, force)
        (skipped.append({"ref": ref, "why": why}) if why else todo.append(ref))

    done = []
    if todo:
        dev = _resolve_device(device)
        seg_net, seg_sha = Z.load_segmenter(seg_model, root)
        rec_net, rec_sha = load_recognizer(rec_model, root, dev)
        for ref in todo:
            done.append(predict(ref, root, seg_net, seg_sha, rec_net, rec_sha,
                                seg_model, rec_model, dev))
    return {"predicted": len(done), "skipped": len(skipped),
            "lines": sum(d["lines"] for d in done),
            "outside": sum(d["lines_outside_zones"] for d in done),
            "pages": done, "skips": skipped}


# ------------------------------------------------------------------ the view

def link_one(ref: str, root: Path = Path(".")) -> str:
    """Point `ocr/<ref>` at the best store that has it. Returns the store it named.

    The human file always wins, so promoting a page is a matter of `restore`
    writing `gt/ocr/` and this relinking — never of moving anything. A machine page
    with a gt counterpart is left in `mz/ocr/` and simply not pointed at, which is
    what keeps the two stores from aliasing.
    """
    ref = norm_ref(ref)
    view = root / VIEWDIR
    view.mkdir(parents=True, exist_ok=True)
    store = GTDIR if alto_for(ref, root, GTDIR).exists() else MZDIR
    target = alto_for(ref, root, store)
    if not target.exists():
        return ""
    link = view / f"chukchi-{ref}.xml"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(os.path.relpath(target.resolve(), view.resolve()))
    return store


def link_view(root: Path = Path(".")) -> dict:
    """Rebuild `ocr/`: one name per page, the human file winning wherever it exists.

    `zones.link_view`'s twin, and deliberately so — the two stores-plus-a-view
    layouts should be one shape, since the whole argument for the layout is that a
    file's role must not live only in the directory holding it.

    Links are relative, so the farm survives a clone or a move; a link whose target
    has gone is removed and counted rather than left to dangle, since a dangling
    entry reads as a missing page rather than as a stale link.

    `from_gt`/`from_mz` is the number worth reading: how much of the corpus is still
    only the machines' word.
    """
    view = root / VIEWDIR
    view.mkdir(parents=True, exist_ok=True)

    gt = set(ocr_refs(root, GTDIR))
    mz = set(ocr_refs(root, MZDIR))
    wanted = {}
    for ref in sorted(gt | mz, key=parse_ref):
        store = GTDIR if ref in gt else MZDIR
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
