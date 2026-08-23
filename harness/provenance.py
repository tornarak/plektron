"""What made an `mz/` file, written so a machine can read it back.

**Imports nothing from this package** but `ns.py`, which is itself a leaf — so
this cannot join an import cycle either, and `zones`, `figures`, `recognize` and
`generate` may all take it at module scope. `refs.py`'s docstring has the
reasoning; the constraint is checked by `test_leaf_modules.py`, which holds this
module to importing leaves and nothing else.

**Why it exists.** Every `mz/` store already carried *something* about its
producer, and no two carried it alike. `mz/zones/` and `mz/ocr/` wrote a
`<Processing>` block from four hand-built places with no shared writer;
`mz/fig/` wrote a bare `f"{model_path} sha256:{sha[:16]} device:{dev}"` from a
fifth and a rule description from a sixth; `mz/tei/` wrote an XML comment, which
is invisible to XPath, to `tei validate` and to every consumer. Six spellings of
one fact is six chances for a file to be written without it, and nothing could
count them because nothing could read them.

**`kind` is the load-bearing field**, and it is why this is a record rather than
a format. A `mz/fig/` page from `fig propose` is derived from the scanner's own
MRC segmentation — a *rule* — and a page from `fig predict` is a model's guess.
Both are proposals and neither outranks a human, but they are different kinds of
witness, and the store had no way to say which it held. That gap is exactly what
`train score fig --model M` exploited: it accepted a checkpoint, named it in the report
and never loaded it, so the report answered a question about a model from a store
that might hold no model's work at all. A reader that must ask which producer
spoke is a reader that will assume.

**A machine-readable block declares itself.** `processingStepSettings` opens with
`harness: 1`; a block without it is legacy free text and `read_producer` returns
`None` for it rather than scraping `model:` out of prose. That is deliberate and
it is what makes the census an instrument: before the backfill the old blocks
must read *unwitnessed*, or the number cannot move and the backfill cannot be
told from a no-op.

**Nothing here writes the output's own hash.** `sha256` is the *model file's*,
which is what makes two runs comparable; a digest of the file it is sitting in
would restate the file and witness nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ns import ALTO_NS, TEI_NS

#: Bumped when the settings vocabulary changes in a way a reader must notice.
#: Its presence is also the discriminator — see the module docstring.
SCHEMA = "1"

#: The two kinds of witness. A `rule` derives its output from a stated input by a
#: deterministic procedure (the PDF's own image placements, the keyed zone
#: labels); a `model` inferred it from a raster. Neither ranks above a human, and
#: `#mz` is what both write — but a rule is reproducible from its input and a
#: model is reproducible only from its checkpoint, so the two are not one thing.
KINDS = ("model", "rule")

#: What the settings string cannot contain, because it is what separates fields.
#: Refused at serialization rather than escaped: no path or device in this corpus
#: holds one, so an escape would be untested machinery guarding nothing, while a
#: refusal names the day it stops being true.
_FORBIDDEN = ("; ", "\n", "\r")

_IN = "in."


@dataclass(frozen=True)
class Producer:
    """One act that produced one file. Two of these where two acts did.

    `step` is the invocation as a human would type it, **including any flag that
    changes the output** — `harness zones predict --decode raw` and `--decode dp`
    are different producers and the store has to say which spoke. That asymmetry
    once cost a corpus-wide sweep: only the dp arm named its decoder, so a raw
    file was silent, and a re-prediction under the default decoder replaced a
    dp-decoded store while the ~20% fall in zone count was read as a property of
    the rasters.
    """

    step: str                       # "harness zones predict --decode dp"
    label: str                      # "region segmentation"
    kind: str                       # "model" | "rule"
    version: str                    # kraken's, or the generator's own
    model: str | None = None        # repo-relative path; None for a rule
    sha256: str | None = None       # of the model file, never of the output
    device: str | None = None
    inputs: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # **Inputs are strings on construction, not at serialization.** They are
        # written as text and read back as text, so a record built with
        # `paragraph_cuts=3` and the same record read off disk have to *be* the
        # same record — otherwise every round-trip test compares unequal for a
        # reason that has nothing to do with what is being tested, and the
        # obvious repair is to weaken the comparison.
        object.__setattr__(self, "inputs",
                           {str(k): str(v) for k, v in (self.inputs or {}).items()})
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, not {self.kind!r}")
        if not self.step or not self.label or not self.version:
            raise ValueError("step, label and version are all required — a "
                             "producer that does not name itself witnesses "
                             "nothing")
        if self.kind == "model":
            # The refusal `zones.predict` already made for its own callers,
            # moved to where every writer meets it. A file written with
            # `sha256: ""` carries provenance that is present, well-formed and
            # says nothing, which is worse than absent: it reads as recorded.
            if not self.model or not self.sha256:
                raise ValueError(
                    f"{self.step}: kind='model' needs both model and sha256 — a "
                    "prediction whose provenance field is empty cannot be told "
                    "from one that was checked")
        elif self.model or self.sha256:
            raise ValueError(
                f"{self.step}: kind='rule' must name no model and no sha256. A "
                "rule that carries a checkpoint path is the confusion this "
                "field exists to prevent")

    @property
    def description(self) -> str:
        """The human sentence, and the exact string the six writers already wrote."""
        return f"{self.label}, {self.step}"

    def settings(self) -> dict[str, str]:
        """The flat `k: v` map both serializations carry. Order is the wire order."""
        out = {"harness": SCHEMA, "kind": self.kind, "step": self.step,
               "label": self.label, "version": self.version}
        if self.model:
            out["model"] = self.model
        if self.sha256:
            out["sha256"] = self.sha256
        if self.device:
            out["device"] = self.device
        for k, v in self.inputs.items():
            out[f"{_IN}{k}"] = str(v)
        for k, v in out.items():
            if any(bad in v for bad in _FORBIDDEN):
                raise ValueError(
                    f"{k}={v!r} contains a field separator {_FORBIDDEN}. The "
                    "settings string is `k: v` joined by '; ' — a value holding "
                    "one would parse back as two fields, and provenance that "
                    "reads back wrong is worse than none")
        return out


def _encode(p: Producer) -> str:
    return "; ".join(f"{k}: {v}" for k, v in p.settings().items())


def _decode(text: str) -> Producer | None:
    """The settings string back to a record, or `None` if it is not one of ours."""
    fields: dict[str, str] = {}
    for part in (text or "").split("; "):
        k, sep, v = part.partition(": ")
        if sep:
            fields[k.strip()] = v.strip()
    if fields.get("harness") != SCHEMA:
        return None
    try:
        return Producer(
            step=fields["step"], label=fields["label"], kind=fields["kind"],
            version=fields["version"], model=fields.get("model"),
            sha256=fields.get("sha256"), device=fields.get("device"),
            inputs={k[len(_IN):]: v for k, v in fields.items()
                    if k.startswith(_IN)})
    except (KeyError, ValueError):
        # A block that opens with our marker but will not reconstruct is
        # corrupt, not legacy. Same answer either way — unwitnessed — because
        # the census counts what can be *read*, and a half-parsed producer
        # reported as present is the fluent nonsense this file is against.
        return None


# --------------------------------------------------------------- ALTO


def kraken_version() -> str:
    """The pinned recognizer/segmenter version, read rather than written down.

    A constant here would be a second home for a number `uv.lock` already fixes,
    and the whole point of recording it is to be able to tell a file written
    before an upgrade from one written after.

    **From the installed distribution's metadata, not `kraken.__version__`** —
    the package does not define that attribute, so a `getattr(..., 'unknown')`
    reads `unknown` forever while looking like it works. That is the shape of
    failure this whole module is against, and it turned up on the first call.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return f"kraken {version('kraken')}"
    except PackageNotFoundError:              # pragma: no cover - not installed
        return "kraken (not installed)"


def alto_processing(p: Producer, ident: str = "OCR_0"):
    """`<Processing>` for a hand-built ALTO tree. Caller appends to `<Description>`.

    Matches kraken's own ALTO template field for field, so the two paths into
    these stores produce one shape and `read_producer` needs one parser.
    """
    from lxml import etree

    proc = etree.Element(f"{{{ALTO_NS}}}Processing", {"ID": ident})
    etree.SubElement(proc, f"{{{ALTO_NS}}}processingStepDescription").text = \
        p.description
    etree.SubElement(proc, f"{{{ALTO_NS}}}processingStepSettings").text = _encode(p)
    soft = etree.SubElement(proc, f"{{{ALTO_NS}}}processingSoftware")
    etree.SubElement(soft, f"{{{ALTO_NS}}}softwareName").text = "harness"
    return proc


def kraken_step(p: Producer, ident: str | None = None):
    """The same record as a `kraken.containers.ProcessingStep`.

    Two of the six writers hand their step to `kraken.serialization.serialize`
    rather than building the element themselves. kraken's ALTO template renders
    `settings` as `k: v` joined by `'; '` — identical to `alto_processing` — so a
    file written either way reads back the same, which is the property that lets
    the two paths coexist without a second parser.
    """
    from kraken.containers import ProcessingStep

    return ProcessingStep(
        id=ident or p.step.replace(" ", "-").replace("--", ""),
        category="processing", description=p.description, settings=p.settings())


# --------------------------------------------------------------- TEI


def tei_appinfo(p: Producer):
    """`<appInfo>` for a TEI `<encodingDesc>`. Caller appends or serializes it.

    `mz/tei/` recorded its producer as an XML comment, which no XPath reaches and
    no schema constrains. TEI has an element for exactly this and it is not
    optional-in-spirit: the collated pages are the corpus, and a fact that only a
    text search can find is a fact the corpus does not carry.
    """
    from lxml import etree

    # `nsmap` so this serializes with TEI as the *default* namespace rather than
    # under a generated `ns0:` prefix. The two are equivalent to a parser and not
    # to a person, and this element lands in a file humans read and hand-edit.
    info = etree.Element(f"{{{TEI_NS}}}appInfo", nsmap={None: TEI_NS})
    app = etree.SubElement(info, f"{{{TEI_NS}}}application", {
        "ident": p.step.replace(" ", "-"), "version": p.version})
    # `<label>` then `<p>`, which is TEI's own content model for `application`
    # (`model.labelLike*, model.pLike*`) — the settings go in a paragraph rather
    # than a `<note>`, which the schema does not admit here.
    etree.SubElement(app, f"{{{TEI_NS}}}label").text = p.description
    etree.SubElement(app, f"{{{TEI_NS}}}p").text = _encode(p)
    return info


def encode(p: Producer) -> str:
    """The producer as the flat `k: v; …` string both serializations carry.

    Public because a **third** carrier needs it and is not XML: `scans/` is `#mz`
    too, and every cut raster carries this string in a PNG `tEXt` chunk — a raster
    copied out of the tree leaves its manifest behind, so the file has to say what
    made it on its own. The ALTO and TEI writers below wrap this; `harness/scans.py`
    writes it into a chunk and reads it back with `decode`. Exposing the encoder is
    what keeps that from becoming a fourth spelling of the same fact, which is the
    whole thing this module exists to prevent.
    """
    return _encode(p)


def decode(text: str) -> Producer | None:
    """One settings string back to a record, or `None` if it is not one of ours.

    `encode`'s inverse, public for its reason. `None` covers both a block written
    before this vocabulary and one written by something else — the right
    conflation, since the census counts what can be *read*.
    """
    return _decode(text)


# --------------------------------------------------------------- reading


#: The PNG `tEXt` keyword a raster's producer is written under. Here rather than in
#: `harness/scans.py` because the *reader* below has to know it and this module may
#: not import that one — `scans` imports this. PNG keywords are Latin-1 and at most
#: 79 characters, which `harness` satisfies and a URI would not.
PNG_KEY = "harness"


def read_producers(path: str | Path) -> list[Producer]:
    """Every machine-readable producer in one file, in wire order.

    A page carries more than one where more than one act made it: `ocr predict`
    segments and then recognizes, with a different model in each, and collapsing
    the pair would lose whichever was asked about. Legacy blocks are absent from
    this list rather than approximated — see the module docstring.

    **Three carriers, one question.** ALTO's `processingStepSettings`, TEI's
    `appInfo`, and a PNG `tEXt` chunk — because `scans/` is `#mz` too and a cut
    raster says what it was cut from. Dispatching here rather than at the call
    site is what lets `census` count a raster store without learning a second way
    to ask; a `.png` carries exactly one producer, there being one act that cuts it.
    """
    from lxml import etree

    path = Path(path)
    if path.suffix.lower() == ".png":
        from PIL import Image
        try:
            with Image.open(path) as im:
                got = decode(str((im.info or {}).get(PNG_KEY, "")))
        except OSError:
            return []
        return [got] if got else []
    try:
        root = etree.parse(str(path)).getroot()
    except (OSError, etree.XMLSyntaxError):
        return []
    texts = [(e.text or "") for e in
             root.iter(f"{{{ALTO_NS}}}processingStepSettings")]
    texts += [(e.text or "") for e in root.iter(f"{{{TEI_NS}}}p")
              if e.getparent() is not None
              and e.getparent().tag == f"{{{TEI_NS}}}application"]
    return [p for p in (_decode(t) for t in texts) if p is not None]


def read_producer(path: str | Path) -> Producer | None:
    """The **last** producer in the file, or `None`.

    Last rather than first because the acts are written in the order they
    happened, so the last one is what shaped the payload a reader is holding —
    on an `ocr predict` page that is the recognizer, not the segmenter that fed
    it. Ask `read_producers` where both matter.
    """
    got = read_producers(path)
    return got[-1] if got else None


def witnessed(path: str | Path) -> bool:
    """Whether the file says what made it. The census's one predicate."""
    return bool(read_producers(path))


# --------------------------------------------------------------- the census

#: The `mz/` stores and the glob that enumerates each. Every store a model or a
#: rule writes is here; the authored stores are not, because a human's own file
#: is witnessed by `@resp` and by the fact that a human wrote it.
MZ_STORES = (("mz/zones", "*.xml"), ("mz/ocr", "*.xml"),
             ("mz/fig", "*.xml"), ("mz/tei", "*.xml"),
             # **`scans/` is `#mz` and belongs in the count.** It is not under
             # `mz/` because it predates that split and every path in the repo
             # names it, but it is a rule's output like the rest: cut from the
             # PDFs' own layers by a deterministic procedure. Leaving it out
             # would make the census answer "everything is witnessed" about a
             # corpus whose largest derived store says nothing. Top-level glob,
             # so the farms underneath it are not walked twice.
             ("scans", "*.png"))


def census(root: str | Path = ".", stores=MZ_STORES) -> list[dict]:
    """Per store: how many files, how many say what made them, and by what.

    **Measurement — this never gates**, per the harness conventions, and it is
    the instrument the backfill is proved by rather than a tidiness report. An
    unwitnessed file is one whose provenance cannot be *read*: a legacy free-text
    block counts as unwitnessed, which is the whole reason the number can move.

    `producers` is the distinct set seen, so a store part-written by two versions
    of one command says so instead of averaging into a single reassuring row.
    """
    root = Path(root)
    rows = []
    for store, pattern in stores:
        d = root / store
        files = sorted(d.glob(pattern)) if d.is_dir() else []
        seen: dict[str, int] = {}
        witnessed_n = 0
        for f in files:
            got = read_producers(f)
            if got:
                witnessed_n += 1
            for p in got:
                key = f"{p.step} [{p.kind}] {p.version}"
                seen[key] = seen.get(key, 0) + 1
        rows.append({
            "store": store, "files": len(files), "witnessed": witnessed_n,
            "unwitnessed": len(files) - witnessed_n,
            "producers": "; ".join(f"{k} x{v}" for k, v in sorted(seen.items())),
        })
    return rows
