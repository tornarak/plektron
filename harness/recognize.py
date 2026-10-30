"""A raster to text in one pass: blot → lines → OCR → `mz/ocr/`.

The pipeline used to run as three unrelated acts with a human carrying state
between them — segment somewhere, recognize somewhere else, hand-link the result.
This is that loop closed. One command per page, and what it produces is a machine
store beside the human one:

    gt/ocr/     what a human has been through. Tracked.
    mz/ocr/     what the models emitted. Derived, ignored.

**Every read names its store; writes name `gt/ocr/`.** Nothing here writes into the
ground truth — `restore` does that, and only that, from an adjudicated
`decision.json`. This module writes `mz/ocr/` and has no parameter in which a
caller could name anywhere else.

## Bare lines, and no zones at all

`blla` finds baselines and its own regions. **The regions are discarded and
nothing replaces them.** The page is written as one unlabelled block holding every
line in geometric order — `flatten_page` is the shape, and it is the same shape
`tools/flatten_ocr.py` gave every page written before this rule.

This pass used to bake the keyed zones in as ALTO regions, so a line arrived
"already knowing" whether it sat in a running title or a footnote. That was a
stored copy of a fact whose home is `gt/zones/`, and it went stale the moment a
band was re-cut — which is why every consumer had already gone back to geometry:
`generate._assign` because "the bands may have been cut since `ocr predict` wrote
those blocks", `lines.page_lines` for a correction because "stored, a label would
go stale the moment the page was re-zoned". `restore` then copied the stale labels
into `gt/ocr/` on every page. So the association is computed where it is used —
`page_lines` resolves a line's `zone` by containment against `gt/zones/` — and
this pass reads no zone store, needs none, and stamps none into its provenance.

## The blotted raster, for both steps

Input is `scans/w-figs-blotted/`, the same page `zones predict` reads, and a page with
no blot is **refused** as it refuses one. Artwork otherwise raises baselines that
are not type, and every one is a spurious line a downstream consumer has to be told
to ignore.

**Nothing is lost to the blot, and that is a property of how it paints rather than
an acceptable cost.** It fills the *declared* figure box and not a pixel more — the
pad was considered and rejected precisely because body text sits hard against an
inset figure on pages like `1-283`, and padding would have erased it. So the type
survives; only the pictures go. Figure captions go too, since `gt/fig/` declares
`GraphicZone-FigDesc` as well, and they should: captions live in `gt/fig/`
and are not body text.

**Every line `blla` finds is kept.** A line outside every zone used to be counted
here as `lines_outside_zones`; with no zones read there is nothing to count it
against, and the question survives where it was always better asked — `ocr gaps`
asks it of the ink by containment, and `zones check --ink` from the other side.
Dropping a line would be quieter and is exactly the failure that cost this project
a two-line paragraph on `1-053` and 18 pages before that: whatever text is present
reads as correct, so no detector disagrees with anything and the page simply has
less on it than the paper does. Junk in a draft is visible to the human reading
it. A hole is not.

## What work remains is read off `mz/ocr/`, not off an input

A sweep's worklist is every page that physically exists, and `predict_skip` is the
one rule that says which to leave alone: a ruled leaf, a page with no blot, and a
page whose `mz/ocr/` file already records **this recognizer** by sha. The last is
the point. It used to be "a file exists", which made a store written by two
different models look finished; now such a store *is* the non-empty worklist.
"""
from __future__ import annotations

import dataclasses
from functools import lru_cache
from pathlib import Path

from . import paths as P
from . import provenance, train
from . import zones as Z
from .atomic import tmp_for
from .layout import page_files, ref_of, stem_for
from .parallel import capture_stderr as _capture_stderr
from .parallel import gpu_workers, worker_output
from .refs import norm_ref, parse_ref

# `capture_stderr`, `worker_output` and the worker-sizing rule were this module's
# own until `zones` needed them and could not import it — the graph runs
# `recognize` -> `zones` -> `context`, so they moved to `parallel`, underneath
# both. They are imported under the names this file already used, which is what
# keeps `_worker_init` finding them as module globals and keeps the monkeypatch
# seams in `test_worker_stderr.py` pointing at what it actually calls.
# `VRAM_PER_WORKER` is deliberately *not* re-imported: only the sizing rule read
# it, that rule moved, and a constant kept here for old times' sake is a second
# place to look for one number.

# The machine store and its human counterpart. There is no view over the pair:
# every reader names one of these two.
GTDIR = "gt/ocr"
MZDIR = "mz/ocr"

# Stock blla, named explicitly rather than left to kraken's bundled default, so a
# sha256 can travel in the file. A default nobody can point at is a provenance
# field that says "whatever was installed".
DEFAULT_SEG_MODEL = "models/blla.mlmodel"
# CATMuS print, large. Its competence here is known and narrow — ~91% on ASCII and
# **0% of the transcription inventory**, measured against the human-collated
# `tei/chukchi-1-151.xml` — so this store is a witness to line geometry and to
# English, and to nothing else. See docs/pipeline.md before treating
# any Tier-1 form in it as a reading.
DEFAULT_REC_MODEL = "models/catmus-print-fondue-large.mlmodel"

# How many of a page's lines go through one forward pass, and how many worker
# processes extract them. kraken defaults these to 1 and 2.
#
# **Neither is where this pass spends its time, and that was worth measuring
# before tuning.** Recognition is 1.5-1.9 s of a 17 s page; `blla.segment` is the
# other 15 s, and it is not GPU work either — profiled, it is scipy `correlate1d`
# (6.1 s), shapely `intersection` (2.2 s) and kraken's own `boundary_tracing` /
# `moore_neighborhood` (3.2 s), i.e. baseline vectorization on one core. That is
# what the ~4.5% mean GPU utilization is: a brief forward pass, then a quarter of a
# minute of CPU.
#
# So batching buys almost nothing here — 17.4 s/page at `batch=1` against 16.8 at
# `batch=32`, over a 3-page sample. 16 is kept because it costs nothing and a page
# is 30-60 lines, so one batch usually *is* the page.
#
# `num_line_workers` is **0**, i.e. no pool at all. It spawns `torch.multiprocessing`
# workers to feed a 1.5 s phase, which does not pay for itself over a short run and
# adds a process-launch failure mode (it needs a real `__main__`, so it dies under
# `python -` and anything else that execs a script from stdin).
REC_BATCH = 16
REC_LINE_WORKERS = 0

# Every line id this pass mints. Provenance travelling with the data, as everywhere
# else here: a line merged out of context still says what made it.
ID_PREFIX = "mz_"

# The label the recognition step is written under, and the one `recognized_by`
# selects on when it reads the file back. A constant because the two must agree:
# the worklist is decided by finding this step, and a step nobody can find is a
# page that will be recognized again on every sweep.
REC_LABEL = "recognition"


def mz_dir(root: Path = Path(".")) -> Path:
    return root / MZDIR


def alto_for(ref: str, root: Path = Path("."), store: str = MZDIR) -> Path:
    return root / store / f"{stem_for(ref, root)}.xml"


def recognized_by(ref: str, rec_sha: str, root: Path = Path(".")) -> bool:
    """Whether `mz/ocr/` holds this page as read by the recognizer with this sha.

    The recognition step is found by its label, not taken as the file's *last*
    producer: `tools/flatten_ocr.py` appended a rule step after it on every page
    written before the bare-lines rule, and "last" would name the flatten. A file
    with no such step — absent, or written before provenance travelled in it — is
    not recognized by anything this can name, and that is the answer a sweep wants.
    """
    p = alto_for(ref, root, MZDIR)
    if not p.exists():
        return False
    return any(s.label == REC_LABEL and s.sha256 == rec_sha
               for s in provenance.read_producers(p))


def presence(refs: list[str], root: Path = Path(".")) -> list[dict]:
    """Per ref: which real stores hold it. `{ref, gt, mz}`, one fixed key set."""
    out = []
    for ref in refs:
        ref = norm_ref(ref)
        out.append({"ref": ref, "gt": alto_for(ref, root, GTDIR).exists(),
                    "mz": alto_for(ref, root, MZDIR).exists()})
    return out


def ocr_refs(root: Path = Path("."), store: str = MZDIR) -> list[str]:
    """Every ref with a page in this store, in (part, scan index) order.

    Deduped by **real path**, in `zones.zone_refs`' form: a walk that counted one
    inode under two names would undercount silently.
    """
    out, seen = [], set()
    for p in page_files(root / store, ".xml", root):
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
            out.append(ref_of(p.stem, root))
        except ValueError:
            continue
    return sorted(set(out), key=parse_ref)


def load_recognizer(model_path: str | Path = DEFAULT_REC_MODEL,
                    root: Path = Path("."), device: str = "cpu"):
    """The recognition model, plus the sha256 that travels in every file.

    **`kraken.tasks.RecognitionTaskModel`, not `lib.models.load_any`.** The old
    path fed `rpred.rpred`, which kraken 7.0.3 marks deprecated and removes in 8,
    and which recognizes **one line per forward pass** — about 50 tiny GPU calls a
    page with CPU polygon extraction between them, measured at 4.5% mean GPU
    utilization. The task model takes a `RecognitionInferenceConfig` carrying
    `batch_size` and `num_line_workers`, which is what lets a page's lines go
    through together.

    It wraps the bare `TorchVGSLModel` that `models.loaders.load_models` returns and
    builds its own decoder, so the warning this docstring used to carry — that
    `load_models` gives an unwrapped model where a `TorchSeqRecognizer` was needed —
    no longer applies to this constructor. It still applies to `rpred`, which is why
    it is recorded rather than deleted.

    `device` is not passed here: placement is the config's, per call.
    """
    from kraken.models.loaders import load_models
    from kraken.tasks import RecognitionTaskModel

    p = _model_path(model_path, root)
    return RecognitionTaskModel(load_models(str(p))), Z._model_sha256(p)


def _model_path(model_path: str | Path, root: Path) -> Path:
    p = Path(model_path)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        raise FileNotFoundError(
            f"no recognition model at {p}. `models/` carries stock CATMuS print "
            f"(large and tiny); {DEFAULT_REC_MODEL} is the default.")
    return p


def recognizer_sha(model_path: str | Path = DEFAULT_REC_MODEL,
                   root: Path = Path(".")) -> str:
    """The sha256 a page written by this recognizer records — **without loading
    it.** A file hash is what lets a sweep decide its whole worklist before either
    checkpoint comes off disk."""
    return Z._model_sha256(_model_path(model_path, root))


def _fabric_placement(dev: str) -> tuple[str, object]:
    """A torch device string as Lightning Fabric's `(accelerator, devices)`.

    The two vocabularies do not overlap and the failure is unhelpful:
    `prepare_for_inference` hands `config.device` straight to
    `Fabric(devices=...)`, which wants `"auto"`, an int count or a list of
    indices — so `"cuda:0"` comes back as `invalid literal for int() with base 10:
    'cuda:0'`, which names neither the field nor the model. The rest of this
    module speaks torch's spelling because `blla.segment` and `_resolve_device` do,
    so the translation happens here rather than by changing what `--device` means.
    """
    if dev.startswith("cuda"):
        _, _, idx = dev.partition(":")
        return "gpu", [int(idx)] if idx else "auto"
    return "cpu", "auto"


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


#: The page shape's version, which the rule step `tools/flatten_ocr.py` appends
#: records. Bump it if `flatten_page` ever changes what it writes.
FLATTEN_VERSION = 1


def block_id(ref: str) -> str:
    """The one block a flattened page holds. Not `mz_`-prefixed: that prefix means
    "minted by a pass" on a line here and "drawn against a configured column" in
    `zones`, and this block was minted by neither — it is the page's shape, not
    anyone's finding. Starts with a letter because an ALTO `ID` is an `xs:ID`."""
    return f"text_{norm_ref(ref)}"


def flatten_page(alto, ref: str) -> bool:
    """One unlabelled `TextBlock` holding every `TextLine`, in document order.

    `alto` is a parsed tree's root element, edited in place; returns whether
    anything changed, so a caller can tell a rewrite from a no-op. Two callers:
    `predict`, on every page it writes, and `tools/flatten_ocr.py`, once, over
    every page written before this was the rule — one definition of the page
    shape, so `gt/ocr/` never holds two.

    **Document order is preserved byte for byte.** `page_lines` assigns `index`
    from it, and `proposal.json`/`decision.json` are keyed on that, so a line that
    moved would silently re-key every adjudication on the page. The lines are
    moved as elements, in the order `iter` yields them, and nothing is renumbered.
    Line ids are untouched for the same reason.

    The block's rectangle is the union of its lines'. Its label is nothing: the
    zone a line sits in is `page_lines`' to derive from `gt/zones/`, and a label
    stored here is a copy that goes stale on the first re-cut.

    `<Tags>` keeps every `OtherTag` something still references — the line-level
    type kraken writes stays — and loses the block types nothing points at any
    more. Membership by reference, not by name, so the rule needs no list of
    which labels were zone labels.
    """
    ps = alto.find(".//{*}PrintSpace")
    if ps is None:
        return False
    want = block_id(ref)
    lines = list(alto.iter("{*}TextLine"))
    blocks = list(ps.iter("{*}TextBlock"))
    if (len(blocks) == 1 and blocks[0].get("ID") == want
            and blocks[0].get("TAGREFS") is None
            and all(ln.getparent() is blocks[0] for ln in lines)):
        return False

    from lxml import etree

    from .ns import ALTO_NS
    tb = etree.Element(f"{{{ALTO_NS}}}TextBlock", {"ID": want})
    boxes = [tuple(int(float(ln.get(k))) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
             for ln in lines if all(ln.get(k) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))]
    if boxes:
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        for k, v in (("HPOS", x0), ("VPOS", y0), ("WIDTH", x1 - x0), ("HEIGHT", y1 - y0)):
            tb.set(k, str(v))
    for ln in lines:                    # moving an element re-parents it; order kept
        tb.append(ln)
    for b in blocks:
        parent = b.getparent()
        if parent is not None:
            parent.remove(b)
    ps.append(tb)

    tags = alto.find(".//{*}Tags")
    if tags is not None:
        used = set()
        for el in alto.iter():
            if el.get("TAGREFS"):
                used.update(el.get("TAGREFS").split())
        for t in list(tags):
            if t.get("ID") not in used:
                tags.remove(t)
    return True


def predict(ref: str, root: Path = Path("."), seg_net=None, seg_sha: str = "",
            rec_net=None, rec_sha: str = "",
            seg_model: str | Path = DEFAULT_SEG_MODEL,
            rec_model: str | Path = DEFAULT_REC_MODEL,
            device: str = "auto", batch_size: int = REC_BATCH,
            line_workers: int = REC_LINE_WORKERS) -> dict:
    """Segment lines, recognize them, and write ALTO into `mz/ocr/`.

    A loaded model may be passed in — `predict_all` loads once for a whole sweep —
    but then its sha must come with it. A file written with `sha256: ""` carries
    provenance that is present, well-formed and says nothing, which is worse than
    absent because it reads as recorded; `zones.predict` refuses the same omission
    on the same grounds.
    """
    # The refusal precedes the imports: `from kraken import ...` pulls in torch and
    # costs ~1.9 s, and a page without a blot never reaches a model.
    # `zones.predict` orders itself the same way and says why.
    ref = norm_ref(ref)
    blot = Z.blot_dir(root) / f"{stem_for(ref, root)}.png"
    if not blot.exists():
        raise FileNotFoundError(
            f"no blotted raster for {ref} at {blot} — run `harness zones blot` "
            "first. Falling back to `scans/` would put a page in the store whose "
            "lines were found under different conditions from every other one, "
            "with nothing in the file saying so.")

    from kraken import blla, serialization
    from kraken.configs import RecognitionInferenceConfig
    from PIL import Image

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

    # **blla's regions are discarded and nothing replaces them** — see the module
    # head. Document order is geometric: down the page, then across. It is *not*
    # reading order on a two-column or footnoted page, and nothing downstream may
    # assume it is of either store; `page_lines` sorts by `reading_order` and keeps
    # `index` as the identity document order assigned.
    def sort_key(ln):
        pts = ln.baseline or ln.boundary or [(0, 0)]
        return (min(p[1] for p in pts), min(p[0] for p in pts))

    lines = [dataclasses.replace(ln, regions=[], id=f"{ID_PREFIX}{ref}_l{i}")
             for i, ln in enumerate(sorted(seg.lines or [], key=sort_key), 1)]

    bound = dataclasses.replace(seg, lines=lines, regions={},
                                imagename=f"{stem_for(ref, root)}.png")
    # **The records are what gets serialized, not the lines with `text` set on
    # them.** `serialization.serialize` reads `record.prediction` and nothing else
    # — a `BaselineLine` carrying `text` serializes to `CONTENT=""`, which is the
    # `gt/fig/` failure exactly: not an error, nothing, and a reader downstream
    # gets a well-formed page with no words on it. The records preserve the `id`
    # and `regions` set above, so the structure survives the round trip; verified
    # rather than assumed, because nothing in the types says so.
    # **A page's lines go through together.** `rpred` yielded one record per
    # forward pass, so a 50-line page was 50 tiny GPU calls with CPU polygon
    # extraction and dewarping between them — 4.5% mean utilization, the GPU idle
    # through every CPU phase. `batch_size` fills the forward pass;
    # `num_line_workers` runs the extraction that feeds it in parallel.
    #
    # `no_legacy_polygons` has to be restated: it was an argument to `rpred` and is
    # a config field here, and its default flips between the two. Left off, the
    # slow polygon path silently comes back.
    accel, devices = _fabric_placement(dev)
    cfg = RecognitionInferenceConfig(
        batch_size=batch_size, num_line_workers=line_workers,
        no_legacy_polygons=True, accelerator=accel, device=devices)
    records = list(rec_net.predict(page, bound, cfg))
    text = [r.prediction or "" for r in records]

    # **Two producers, written in the order they acted.** The page is segmented
    # and then recognized by two different models, and collapsing the pair would
    # lose whichever a reader happened not to be asking about. `recognized_by`
    # finds the second by `REC_LABEL`, not by position — a later rule step may
    # follow it.
    kv = provenance.kraken_version()
    steps = [
        provenance.kraken_step(provenance.Producer(
            step="harness ocr predict", label="baseline segmentation",
            kind="model", version=kv, model=str(seg_model), sha256=seg_sha,
            device=dev,
            inputs={"raster": f"{Z.BLOTDIR}/{stem_for(ref, root)}.png"}),
            ident="harness-ocr-predict-lines"),
        provenance.kraken_step(provenance.Producer(
            step="harness ocr predict", label=REC_LABEL,
            kind="model", version=kv, model=str(rec_model), sha256=rec_sha,
            device=dev), ident="harness-ocr-predict-text"),
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
    # exports, one `<String CONTENT>` per `TextLine`, and `restore` copies this
    # store's skeleton into it. `lines.page_lines` joins a line's text by
    # concatenating its `String`s, so both forms happen to read alike today —
    # which is precisely how a divergence like this survives: it costs nothing
    # until something reads `String/@CONTENT` expecting a line and gets a word.
    #
    # Nothing is lost that this project uses. The per-glyph boxes and confidences
    # are kraken's own recognition detail; the corpus addresses text at the line,
    # `restore` writes at the line, and review crops at the line.
    xml = serialization.serialize(
        dataclasses.replace(bound, lines=records),
        image_size=size, template="alto", processing_steps=steps,
        sub_line_segmentation=False)

    # **The written shape is `flatten_page`'s, by the same function.** Whatever
    # kraken's template does with region-less lines, the page on disk is one
    # unlabelled block — so a page fresh from the recognizer and a page flattened
    # after the fact are one shape, and `gt/ocr/` never holds two.
    from lxml import etree
    tree = etree.fromstring(xml.encode("utf-8"))
    flatten_page(tree, ref)
    xml = etree.tostring(tree, xml_declaration=True, encoding="UTF-8",
                         pretty_print=True).decode("utf-8")

    out = mz_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    dest = alto_for(ref, root, MZDIR)
    tmp = tmp_for(dest)
    tmp.write_text(xml, encoding="utf-8")
    tmp.replace(dest)

    chars = sum(len(t) for t in text)
    return {"ref": ref, "path": str(dest), "lines": len(lines), "chars": chars}


def predict_skip(ref: str, root: Path = Path("."), force: bool = False,
                 single: bool = False, rec_sha: str = "") -> str:
    """Why this page should not be recognized, or `""` to go ahead.

    One rule in one place, `zones.predict_skip`'s shape and its reasoning:

    - **a page ruled `exempt` is refused**, `force` or not, unless `single` — a
      plate is not a text page, and a recognized plate sits in the store looking
      like any other reading. Naming a ref on the command line is `single`;
    - **a page with no blot is refused**, since `predict` reads nothing else.
      This is the one skip that is a missing *input* rather than a judgement, so
      it names the command that produces it. It used to test the raw scan, which
      `predict` does not open — so a page could pass here and be refused there;
    - **a page this recognizer has already read is kept unless `force`.** The
      test is the sha the file records against `rec_sha`, not the file's
      existence. A file test made a store written by two models look finished;
      under this rule such a store *is* the non-empty worklist, and the record
      does the deciding instead of being overwritten behind it. `force` is how a
      caller re-reads a page that is already current.
    """
    if not single and Z.is_exempt(ref, root):
        return "ruled not a text page"
    if not (Z.blot_dir(root) / f"{stem_for(ref, root)}.png").exists():
        return "no blot (run `harness zones blot`)"
    if not force and recognized_by(ref, rec_sha, root):
        return "already recognized by this model"
    return ""


def predict_all(root: Path = Path("."), refs: list[str] | None = None,
                seg_model: str | Path = DEFAULT_SEG_MODEL,
                rec_model: str | Path = DEFAULT_REC_MODEL,
                device: str = "auto", force: bool = False,
                named: bool = False, jobs: int | None = None, tick=None) -> dict:
    """Recognize over a work-list, or over every page that physically exists.

    What is skipped and why is `predict_skip`'s; this loops and reports. A sweep is
    **resumable by construction** — run it again and it picks up what this
    recognizer has not read — which over 832 pages of two models' inference is the
    difference between an interruption costing minutes and costing the run. The
    worklist is read off `mz/ocr/`'s own provenance, never off an input store: the
    output says what remains.

    Both models load once **per worker**, which is most of why this exists as a
    sweep rather than a shell loop over the single-page form. It is also why
    several refs typed on the command line come *here* rather than looping the
    single-page form: naming two pages should not cost two model loads.

    **The pages run in parallel processes, and the reason is that this is CPU
    work.** A page is ~17 s, of which `blla.segment` is ~15 s and recognition
    ~1.5 s — and the segmenter's time is scipy `correlate1d`, shapely
    `intersection` and kraken's own boundary tracing, i.e. baseline vectorization
    on one core. The GPU sits at ~4.5% mean utilization throughout, so this is the
    one sweep in the harness that wants *cores*, not a fuller batch: measured over
    8 pages, 14.16 s/page serial against 5.14 with four processes. `jobs=1` keeps
    the single-process path exactly as it was.

    **`named` is `predict_skip`'s `single`, and it has to travel.** A ref a human
    typed means that page even if it is ruled exempt; without this the moment a
    two-page invocation started routing through the sweep, a named plate would
    have been dropped in silence by the very command that named it. It defaults
    off because a corpus sweep is exactly the case where the exempt ruling should
    hold.
    """
    if refs is None:
        refs = P.all_scans(root)
    refs = [norm_ref(r) for r in refs]

    # **The work-list is decided before either model is loaded**, so re-running a
    # finished sweep to confirm it is finished costs a directory walk and a file
    # hash rather than two checkpoints off disk. That is what makes "resumable" a
    # thing you will actually do rather than a property the docstring claims.
    rec_sha = recognizer_sha(rec_model, root)
    todo, skipped = [], []
    for ref in refs:
        why = predict_skip(ref, root, force, single=named, rec_sha=rec_sha)
        (skipped.append({"ref": ref, "why": why}) if why else todo.append(ref))

    done, chatter = [], {"stderr_lines": 0, "stderr_log": ""}
    if todo:
        n = predict_workers(jobs, len(todo))
        if n == 1:
            dev = _resolve_device(device)
            seg_net, seg_sha = Z.load_segmenter(seg_model, root)
            rec_net, rec_sha = load_recognizer(rec_model, root, dev)
            from .parallel import ptrack
            for ref in ptrack(todo, tick):
                done.append(predict(ref, root, seg_net, seg_sha, rec_net, rec_sha,
                                    seg_model, rec_model, dev))
        else:
            done, chatter = _predict_pool(todo, n, root, seg_model, rec_model,
                                          device, tick)
    return {"predicted": len(done), "skipped": len(skipped),
            "workers": predict_workers(jobs, len(todo)) if todo else 0,
            "lines": sum(d["lines"] for d in done),
            **chatter,
            "pages": done, "skips": skipped}


# The models a worker process loads once, then keeps. Module-level because a
# `spawn`ed worker has to reach them by import rather than by closure.
_WORKER: dict = {}


# kraken raises this once per recognition call, and it is a property of the
# pinned model rather than of the page: `models/blla.mlmodel` predates the new
# polygon extractor, so every page is "trained with old version". The caveat is
# real and is recorded in `VERBS.md`'s `ocr predict` entry, which is where a
# statement true of all 832 pages belongs.
#
# **Suppressed in the workers because they are the one place it cannot be
# handled.** A `spawn`ed child inherits fd 2, so its warnings go straight to the
# terminal, underneath a progress bar that redraws by moving the cursor — rich
# redirects `stderr`, but only Python-level writes in the *parent*. The result is
# frames left stranded at the wrong line and a count that appears frozen while
# the store fills normally, which is how a 689-page sweep loses the only signal
# it has. On the serial path the same warning is raised in-process, rich catches
# it, and it prints tidily above the bar — so this is scoped to the pool.
# Defined in `zones`, beside `load_segmenter`, since both pooled sweeps filter it
# and that module may not import this one. Re-exported under the name this file
# and `test_worker_stderr.py` have always used.
POLYGON_WARNING = Z.POLYGON_WARNING


def _worker_init(root: Path, seg_model, rec_model, device: str,
                 log_dir=None) -> None:
    import os
    import warnings

    # **Both of these run before the models load**, which is not tidiness: kraken
    # and torch both talk during a load, and a warning raised while the recognizer
    # comes up is as much a write to the shared fd as one raised on page 400.
    if log_dir is not None:
        _capture_stderr(log_dir)
    # By message, not by category: `UserWarning` from kraken is a channel worth
    # keeping open, and a blanket filter in a worker would silence the next
    # warning nobody has seen yet. This one is a property of the pinned model
    # rather than of any page — `VERBS.md` states it once — so filtering it keeps
    # the capture file empty in the ordinary case, and an empty file is what makes
    # a non-empty one worth reading.
    warnings.filterwarnings("ignore", message=POLYGON_WARNING)

    os.chdir(root)
    dev = _resolve_device(device)
    seg_net, seg_sha = Z.load_segmenter(seg_model, root)
    rec_net, rec_sha = load_recognizer(rec_model, root, dev)
    _WORKER.update(root=root, dev=dev, seg_net=seg_net, seg_sha=seg_sha,
                   rec_net=rec_net, rec_sha=rec_sha,
                   seg_model=seg_model, rec_model=rec_model)


def _worker_predict(ref: str) -> dict:
    w = _WORKER
    return predict(ref, w["root"], w["seg_net"], w["seg_sha"],
                   w["rec_net"], w["rec_sha"], w["seg_model"], w["rec_model"],
                   w["dev"])


def _predict_pool(todo, n, root, seg_model, rec_model, device,
                  tick=None) -> list[dict]:
    """`todo` across `n` processes, each loading the models once.

    **Processes, not the thread pool the raster sweeps use**, and the difference
    is measured rather than assumed. Over 8 pages: 14.16 s/page serial, 7.89 with
    4 threads (1.8x), 5.14 with 4 processes (2.8x, and that figure *includes* four
    model loads). Threads plateau at 4 and 8 is no better, which is what a ~55%
    GIL-free workload does — the segmenter's cost is scipy and shapely with a lot
    of Python between them, not one long C call.

    **`spawn`, not fork.** A forked child inherits a CUDA context it cannot use.

    Results come back in `todo` order, so the report does not reshuffle by which
    page happened to finish first — which `as_completed` plus a pre-sized list
    gives, where `ex.map` gave it for free. The swap buys the progress `tick`: at
    ~17 s a page this is the longest silence in the CLI, and `ex.map` blocks the
    caller for the whole sweep with nothing to report from.
    """
    import multiprocessing as mp
    import tempfile
    from concurrent.futures import ProcessPoolExecutor, as_completed

    results: list = [None] * len(todo)
    log_dir = Path(tempfile.mkdtemp(prefix="harness-predict-"))
    with ProcessPoolExecutor(
            max_workers=n, mp_context=mp.get_context("spawn"),
            initializer=_worker_init,
            initargs=(root, seg_model, rec_model, device, log_dir)) as ex:
        futures = {ex.submit(_worker_predict, r): i for i, r in enumerate(todo)}
        for done, fut in enumerate(as_completed(futures), 1):
            i = futures[fut]
            results[i] = fut.result()
            if tick:
                tick(todo[i], done, len(todo))
    return results, worker_output(log_dir)


def predict_workers(jobs: int | None, n_pages: int) -> int:
    """How many processes this sweep will use — `parallel.gpu_workers`, named.

    Kept as a name here because `harness/README.md` and `VERBS.md` both cite it,
    and a doc should not have to move for a refactor. The rule and the VRAM cap
    are `parallel`'s, since `train score zones` sizes its pool the same way and cannot
    import this module.
    """
    return gpu_workers(jobs, n_pages)


# ==========================================================================
# Training a recognizer on the keyed corpus
# ==========================================================================
#
# The third training track, after `zones-seg` and `fig-seg`, and the first that
# fits a *recognizer* rather than a segmenter. `gt/ocr/` is already the artifact
# a recognizer trains on and was never built to be one: an ALTO whose every
# `TextLine` carries a polygon and a ratified `CONTENT` is a line image paired
# with its transcription, which is the whole of what CTC needs. No character
# boxes, no word boxes — the loss aligns a variable-length output to a
# variable-length string by itself.
#
# **Why bother, when `DEFAULT_REC_MODEL` reads English at ~91%.** Because the
# 9% is not spread evenly. CATMuS print scores **0% of the transcription
# inventory** (see `DEFAULT_REC_MODEL` above), garbles every Cyrillic passage,
# drops the superscript footnote markers §2.10 declares, and straightens the
# curly quotes the English prose reproduces. Those are four systematic failures
# on ~2.27 M characters of ratified text keyed to one spec — which is the exact
# shape of thing a fine-tune fixes and a bigger general model does not.
#
# Nothing here trains anything. `assemble` lays out the directory and reports
# the invocation; a run holds the GPU for hours and belongs in the operator's
# own terminal, as it does on both sibling tracks.

#: All from `train.OCR`, which is where the track record lives. `zones`' split of
#: the track, verbatim: `data/` is the laid-out training set, its two page lists
#: and the compiled datasets; `model/` holds a run's checkpoints. Separated so a
#: glob over the training set cannot pick up a checkpoint, and clearing one half
#: does not touch the other.
WORKDIR = train.OCR.workdir
DATADIR = train.OCR.datadir
RUNDIR = train.OCR.rundir
MODELDIR = train.OCR.modeldir
MODEL_NAME = train.OCR.model_name
INSTALLED_MODEL = train.OCR.default_model

#: The split marks live in the store they divide, beside `gt/fig/`'s and
#: `gt/zones/`'s, and are read and written by `figures`' helpers — which take a
#: `store` parameter for exactly this, so a second track need not carry a second
#: copy of the same four functions.
SPLIT_STORE = train.OCR.split_store


def rec_splits(root: Path = Path(".")) -> dict[str, str]:
    """`{ref: "train"|"eval"}` over `gt/ocr/_train.lst` and `_eval.lst`."""
    from .figures import load_splits
    return load_splits(root, SPLIT_STORE)


def remark_eval(root: Path = Path("."), fraction: float = 0.10,
                commit: bool = False) -> dict:
    """Mint or extend the recognizer's train/eval split over `gt/ocr/`.

    **The unit is the page, and this is the one decision in the track that a
    default would get wrong.** kraken's own `-p/--partition` divides the pooled
    *line* set, and every sibling recipe online uses it. On this corpus that
    leaks: lines off one leaf share its ink weight, its wear, its bleed-through
    and the compositor's own stick, so a model that has seen forty lines of a
    page has seen the conditions under which the other ten were printed. The
    held-out number then measures memorising a page rather than reading a new
    one, and it measures it *high*, which is the direction nobody checks.
    Supplying `-t`/`-e` explicitly is what turns `--partition` off (kraken sets
    it to 1 when an evaluation set is named), and `assemble` always supplies
    both.

    Additive, stratified per part, and spread rather than taken off the front —
    `zones.remark_eval`'s three properties for its three reasons. A mark a human
    or an earlier run made is never moved, or the held-out set drifts with
    whatever was keyed most recently and stops being held out.

    The default fraction is **0.10 rather than the segmenters' 0.20**, and the
    difference is that this track's unit is a line: a tenth of 717 pages is ~3000
    held-out lines, where a tenth of the zone corpus would be a few dozen pages.
    Both tracks want an eval set big enough to separate two models; here that
    costs proportionally less of the training data.
    """
    from .figures import set_split
    from .zones import _spread

    seen = rec_splits(root)
    universe = ocr_refs(root, GTDIR)
    fresh = [r for r in universe if r not in seen]

    by_part: dict[str, list[str]] = {}
    for r in fresh:
        by_part.setdefault(r.split("-")[0], []).append(r)
    picked: set[str] = set()
    for _part, refs in by_part.items():
        picked.update(_spread(refs, int(round(len(refs) * fraction))))

    plan = {r: ("eval" if r in picked else "train") for r in fresh}
    out = {
        "keyed_pages": len(universe),
        "already_marked": len(seen),
        "newly_marked": len(plan),
        "to_eval": sum(1 for v in plan.values() if v == "eval"),
        "committed": commit,
    }
    if not commit:
        out["preview"] = "nothing written — pass --commit"
        return out
    for ref, split in plan.items():
        set_split(ref, split, root, SPLIT_STORE)
    return out




#: The four invocations `assemble` reports, as templates rather than strings
#: built at the call site — so the one place a flag is written down is the one
#: place it is read, and a kraken upgrade is a single edit here.
#:
#: **Every flag below was verified against `ketos --help` and against kraken
#: 7.0.3's own source in this environment**, not against a tutorial. Four are
#: not what a remembered 4.x-era invocation would give you:
#:
#: - **`-u NFD`, said out loud.** The corpus is NFD corpus-wide and `ketos`
#:   applies no normalization unless told to, so omitting this happens to work
#:   — until a store drifts, at which point two spellings of one glyph become
#:   two codec entries and the model learns both badly. CLAUDE.md's rule that
#:   any normalization must name its form applies to somebody else's tool too.
#:   **Never `NFKC`/`NFKD` here**: they destroy `ᵋ` U+1D4B and `˙` U+02D9,
#:   which are inventory glyphs this model exists to learn.
#: - **`--resize union`.** The default is `fail`, and it would: CATMuS's codec
#:   has none of the transcription inventory. `union` keeps every codepoint the
#:   base model already reads and appends ours, where `new` would refit the
#:   output layer to this corpus alone and throw away the English competence
#:   that is the reason for fine-tuning rather than starting from scratch.
#:   `kraken/train/vgsl.py` implements exactly `fail`, `union` and `new` — the
#:   help advertises `add` and `both`, and `recognition.py`'s own mismatch
#:   error suggests `add`. Both crash.
#: - **Compiled to binary first, and trained from that.** `-f alto` works
#:   directly, and re-extracts and dewarps 30 000 line polygons on every epoch.
#:   `ketos compile` pays that once.
#: - **`-s` is group-level and means the seed**; on `ketos train` it means
#:   `--spec`, a network architecture. `-d` and `--workers` are group-level too,
#:   and are read off this machine so the reported command runs as printed —
#:   the zone track's was once handed over without them and duly trained on
#:   kraken's default single loader worker.
COMPILE_CMD = (
    "uv run ketos compile -f alto --linetype baselines"
    " -F {work}/{split}.lst -o {work}/{split}.arrow"
)
TRAIN_CMD = (
    "uv run ketos -s 42 -d {device} --workers {workers} train"
    " -f binary -u NFD{load}"
    " {work}/train.arrow -e {work}/eval.mft"
    " -o {out} --augment -B {batch}"
    " -q early -N 100 --min-epochs 10 --lag 10"
)
TEST_CMD = (
    "uv run ketos -d {device} --workers {workers} test"
    " -f binary -u NFD -m {model} -e {work}/eval.mft"
)


def assemble(root: Path = Path("."), scratch: bool = False,
             batch: int = 8, tick=None) -> dict:
    """Lay out `train/bogoras-ocr/data/` for `ketos`, and report the invocations.

    ketos resolves a line's image through the ALTO's own
    `sourceImageInformation/fileName`, relative to the XML — so each page's
    ground truth and its raster are symlinked side by side under the name the
    ALTO already carries, exactly as on both segmentation tracks.

    **The raster is `scans/w-figs-blotted/`, because that is what `predict`
    reads.** This is the mirror image of `figures.assemble`, which links the raw
    scan, and the two are opposite for the same underlying rule: a model is
    trained on the raster it will be asked to read. A line polygon that runs up
    against an inset figure — `1-283` is the standing example — is dewarped with
    that figure's ink in it on the raw page and with white in it on the blot, and
    a model trained on one and run on the other meets a line it has never seen a
    version of. **Refuses a page with no blot** rather than falling back, on
    `zones.assemble`'s reasoning: a set half of which was assembled by a
    different method is not a training set, and nothing downstream could tell.

    **`eval.mft` exists because `-e` takes a manifest, not a dataset.** kraken's
    `_validate_manifests` opens the file named by `-t`/`-e` and reads paths out
    of it, so the eval *dataset* has to be named from inside a file rather than
    on the command line; `train.arrow` goes in as the positional ground truth
    and needs no such wrapper. The same function is worth knowing about for a
    second reason: **an entry that is not a file is dropped with a log warning
    and nothing else.** A `.lst` written with the wrong relative prefix does not
    fail — it trains on less, silently. Compare the line count `ketos compile`
    reports against `lines` below before reading any accuracy figure.

    Paths in the lists are **relative to the repo root and unresolved.**
    Resolving them follows the symlink back into `gt/ocr/` and compiles the
    store instead of the work directory — `zones.assemble` records the lesson
    and it applies here verbatim.
    """
    from .lines import page_lines
    from .parallel import ptrack
    from .zones import _runtime_flags, blot_dir

    work = root / DATADIR
    for p in sorted(work.glob("*")) if work.exists() else []:
        if p.is_file() or p.is_symlink():
            p.unlink()
    work.mkdir(parents=True, exist_ok=True)
    # Made here rather than left to `ketos -o`: kraken creates the output
    # directory it is given but not its parents, and the reported command is
    # meant to run as printed.
    (root / RUNDIR).mkdir(parents=True, exist_ok=True)

    splits = rec_splits(root)
    listed: dict[str, list[str]] = {"train": [], "eval": []}
    lines = {"train": 0, "eval": 0}
    chars = {"train": 0, "eval": 0}
    missing: list[str] = []
    unmarked: list[str] = []
    corrections = 0

    for ref in ptrack(ocr_refs(root, GTDIR), tick):
        split = splits.get(ref)
        # A page nobody has marked is left out of both lists and named, never
        # defaulted into train. On the segmentation tracks an unmarked page is a
        # newly keyed one and `DEFAULT_SPLIT` is harmless; here it would quietly
        # enlarge the training set between a `remark-eval` and a run, so the two
        # numbers a report is compared against would come from different sets.
        if split is None:
            unmarked.append(ref)
            continue
        blot = blot_dir(root) / f"{stem_for(ref, root)}.png"
        if not blot.exists():
            missing.append(ref)
            continue
        name = f"{stem_for(ref, root)}"
        img = work / f"{name}.png"
        if not img.exists():
            img.symlink_to(blot.resolve())
        xml = work / f"{name}.xml"
        if not xml.exists():
            xml.symlink_to(alto_for(ref, root, GTDIR).resolve())
        listed[split].append(f"{DATADIR}/{name}.xml")
        # Counted from the store, so the report says what is going in before
        # `ketos compile` says what came out and the two can disagree out loud.
        # Empty lines are excluded because `--skip-empty-lines` is kraken's
        # default; that is the only difference the two counts should show.
        #
        # **`src: "corr"` lines are counted apart and do not train.** A
        # correction is a box a human drew over ink the segmenter left unboxed;
        # `page_lines` appends it at read time and it is *not* in the ALTO, so
        # `ketos compile -f alto` cannot see it. Every other consumer in the
        # harness inherits the merge, which makes this the one place where
        # taking the merged view would quietly overstate the training set —
        # by exactly the lines a human went out of their way to add.
        for rec in page_lines(alto_for(ref, root, GTDIR), root, ref):
            text = (rec.get("text") or "").strip()
            if not text:
                continue
            if rec.get("src") == "corr":
                corrections += 1
                continue
            lines[split] += 1
            chars[split] += len(text)

    for split, names in listed.items():
        (work / f"{split}.lst").write_text(
            "".join(n + "\n" for n in sorted(names)), encoding="utf-8")
    (work / "eval.mft").write_text(f"{DATADIR}/eval.arrow\n", encoding="utf-8")

    device, workers = _runtime_flags()
    if scratch:
        load, base, why = "", "scratch (asked for)", (
            "random init on kraken's default recognition spec. Nothing is "
            "resized because there is no codec to reconcile")
    elif (root / INSTALLED_MODEL).exists():
        load, base, why = (f" -i {INSTALLED_MODEL} --resize union",
                           INSTALLED_MODEL,
                           "continuing this project's own recognizer; `union` "
                           "so a codepoint keyed since the last run is added "
                           "rather than the codec being refitted")
    elif (root / DEFAULT_REC_MODEL).exists():
        load, base, why = (f" -i {DEFAULT_REC_MODEL} --resize union",
                           DEFAULT_REC_MODEL,
                           "CATMuS print large: the ~91% ASCII competence is "
                           "kept and the inventory is appended to its codec")
    else:
        # Says so rather than quietly emitting a from-scratch command.
        # Fine-tuning and random init are different experiments, and the one
        # that arrives by way of a missing file is the one nobody chose.
        load, base, why = "", "scratch (no base model found)", (
            f"no {DEFAULT_REC_MODEL} and nothing installed, so the reported "
            "command trains from random init — pass --scratch to mean that")

    out_dir = f"{RUNDIR}/{train.next_run(train.OCR, root)}"
    rep = {
        "dir": str(work),
        "train_pages": len(listed["train"]), "eval_pages": len(listed["eval"]),
        "train_lines": lines["train"], "eval_lines": lines["eval"],
        "train_chars": chars["train"], "eval_chars": chars["eval"],
        "corrections_excluded": corrections,
        "unmarked": " ".join(unmarked),
        "missing_blot": " ".join(missing),
        "base": base,
        "base_why": why,
        "raster": "scans/w-figs-blotted/ — what `ocr predict` reads",
        "note": ("flags verified against `ketos --help` and kraken 7.0.3's own "
                 "source, not against a tutorial: -s/-d/--workers are "
                 "group-level, --resize implements only fail/union/new, and -e "
                 "takes a manifest naming the dataset. Re-verify after any "
                 "kraken upgrade. Compare the line count `ketos compile` "
                 "reports against train_lines/eval_lines — a manifest entry "
                 "that is not a file is dropped with a warning and nothing "
                 "else, so a bad prefix trains on less rather than failing."),
    }
    rep["commands"] = [
        COMPILE_CMD.format(work=DATADIR, split="train"),
        COMPILE_CMD.format(work=DATADIR, split="eval"),
        TRAIN_CMD.format(device=device, workers=workers, load=load,
                         work=DATADIR, out=out_dir, batch=batch),
        # **A glob, because the run names the file with its own score.**
        # `ketos train` converts its best checkpoint to
        # `best_{val_metric:.4f}.safetensors`, so the name is not knowable until
        # the run ends. Inside a fresh per-run directory the glob matches exactly
        # one file, which is the other half of why `_next_run` exists — the zone
        # track's three runs once shared a directory and were distinguishable
        # only by an accuracy in a filename, which is not an identity.
        # `ketos test` loads it through `load_from_weights`, the non-`.ckpt`
        # branch, which takes safetensors and `.mlmodel` alike.
        TEST_CMD.format(device=device, workers=workers, work=DATADIR,
                        model=f"{out_dir}/best_*.safetensors"),
        # **The baseline is reported with the run, not left to be remembered.**
        # A CER for the fine-tune is not a result on its own; it is one against
        # what the corpus is read with today, taken over the same held-out
        # pages by the same command. Two numbers made the same way.
        TEST_CMD.format(device=device, workers=workers, work=DATADIR,
                        model=DEFAULT_REC_MODEL),
    ]
    if unmarked:
        rep["note"] += (f" {len(unmarked)} keyed pages carry no split mark and "
                        "are in neither list — run `train remark-eval ocr --commit`.")
    if corrections:
        rep["note"] += (f" {corrections} ratified lines live in gt/lines/ rather "
                        "than in the ALTO and cannot be compiled from it; they "
                        "are excluded and counted, not silently folded in.")
    return rep
