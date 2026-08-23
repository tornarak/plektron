"""The three model-training tracks as one record, and the little that generalizes.

**Imports nothing from this package.** A leaf, for `refs.py`'s reason: `zones`,
`figures` and `recognize` all read their own constants from here, and any import
in the other direction would close a loop through three of the largest modules in
the package. What is hoisted is the *record*, never a body.

**Why a registry rather than three groups.** `zones`, `fig` and `ocr` each grew
`remark-eval`, `assemble`, `install` and `score`, with one implementation each and
one set of constants each. `harness/VERBS.md` blesses that shape outright — an
action name reused across groups means the same kind of act, and the group carries
which recipe — and the commit that folded `ocr link`/`zones link` into `views`
considered `zones blot` and `fig crops` for the identical fold and **rejected**
them, because those verbs carry capability a merged verb has no way to express.

What overrode it is the second job a registry does, which is the job `farms.py`
does and no per-domain verb can: it becomes the **scope of an absence rule**.
`views check` answers "is any derived tree stale" because there is a list of them;
before this, "which tracks have a split, a laid-out set, an installed model"
had no command behind it and no place for one, exactly as "which pages are ready
to collate" had none before `corpus state`.

**The split helpers are deliberately NOT merged, and this is the thing that
resisted.** `zones.load_splits`/`set_split` carry a **seven**-value vocabulary
(`TEXT_SPLITS + LEAF_KINDS`) and sweep all seven lists on a re-mark; `figures`'
carry two. Merging them would cost the five leaf kinds — a `map` and a `cover` are
split values there and nowhere else. So the record names the store and each track
keeps its own helpers, which is the honest analogue of `farms.build`'s name-keyed
chain: the record generalizes, the bodies do not.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Track:
    """One model this project trains, from its ground-truth store to its install.

    `trainer` is `ketos`'s subcommand and is not cosmetic: `segtrain` trains a
    region segmenter off ALTO geometry and `train` trains a line recognizer off
    ALTO text, and the two take different flags entirely. A field rather than a
    branch, so a reader can see which without opening the module.

    `mz_store` is **what `score` reads**, and naming it here is the correction
    `train score fig --model M` needed: that flag accepted a checkpoint, named it in the
    report and never opened it, because the comparison is always store-against-
    store. A track whose score reads a store says so in the record.

    `default_model` is where `install --commit` puts the winner and where every
    downstream verb looks for it. Note the suffixes differ — the two segmenters
    install `.safetensors` and the recognizer `.mlmodel` — which is a fact about
    what each consumer loads, not an inconsistency to tidy.
    """

    name: str            # the CLI token
    workdir: str         # train/bogoras-*
    modeldir: str        # models/bogoras-*
    model_name: str      # zones-seg | fig-seg | text-rec
    default_model: str   # modeldir/model_name.{safetensors,mlmodel}
    split_store: str     # gt/zones | gt/fig | gt/ocr
    mz_store: str        # what `score` compares against
    fraction: float      # the default share `remark-eval` moves or mints
    trainer: str         # ketos subcommand: segtrain | train

    @property
    def datadir(self) -> str:
        """What `ketos` reads: a raster link and an ALTO per page, plus the lists.

        Split from `model/` because they were one directory, and a thousand page
        links sat beside the run's checkpoints with nothing but a suffix to tell
        them apart. A glob over the training set could pick up a checkpoint, and
        clearing one half touched the other.
        """
        return f"{self.workdir}/data"

    @property
    def rundir(self) -> str:
        return f"{self.workdir}/model"


ZONES = Track(
    name="zones", workdir="train/bogoras-seg", modeldir="models/bogoras-seg",
    model_name="zones-seg",
    default_model="models/bogoras-seg/zones-seg.safetensors",
    split_store="gt/zones", mz_store="mz/zones", fraction=0.20,
    trainer="segtrain")

FIG = Track(
    name="fig", workdir="train/bogoras-fig", modeldir="models/bogoras-fig",
    model_name="fig-seg",
    default_model="models/bogoras-fig/fig-seg.safetensors",
    split_store="gt/fig", mz_store="mz/fig", fraction=0.20,
    trainer="segtrain")

#: **`fraction` is 0.10 and its unit is not the others'.** The two segmenters
#: split pages and hold back a fifth; the recognizer splits pages too but is
#: measured in *lines*, and 10% of the corpus is already ~3,000 eval lines. A
#: fifth would have cost the training set 3,000 more lines to measure something
#: the smaller share measures just as well.
OCR = Track(
    name="ocr", workdir="train/bogoras-ocr", modeldir="models/bogoras-ocr",
    model_name="text-rec",
    default_model="models/bogoras-ocr/text-rec.mlmodel",
    split_store="gt/ocr", mz_store="mz/ocr", fraction=0.10,
    trainer="train")

TRACKS = (ZONES, FIG, OCR)
BY_NAME = {t.name: t for t in TRACKS}
NAMES = tuple(t.name for t in TRACKS)

#: The per-action pools, which are `views`' shape: `check` uses `F.NAMES` and
#: `build` uses `F.BUILDABLE`, and the selector is a positional for the reason
#: `_views._farm_arg` records. A one-value pool is honest rather than a smell —
#: it says the act exists and applies to one track, which is a different
#: statement from the act not existing.
SPLITTABLE = NAMES
ASSEMBLABLE = NAMES
#: `ocr` is absent from both because `ocr install` and `ocr score` do not exist
#: yet — the recognizer has never been trained. Listing it would be a pool
#: promising an action nothing implements.
INSTALLABLE = ("zones", "fig")
SCORABLE = ("zones", "fig")
#: Only the zone segmenter learns names it can permute: `ketos segtrain --resize
#: new` renumbers the output layer, and seven classes can come back in seven
#: orders. `remap` puts the learned names back.
REMAPPABLE = ("zones",)


#: The effective defaults for the track-specific flags on `train`.
#:
#: **These live here rather than in the parser because the parser cannot hold
#: them.** One `--decode` flag now serves a pool of tracks, so it must parse with
#: `default=None` — a value written into the option would be one track's answer
#: given to all of them — and the real default is applied from the record. That
#: moved the number, so it needs a declared home rather than a literal inside a
#: CLI helper.
#:
#: `DECODE` in particular is load-bearing and has been wrong once:
#: `zones score --model X` decoded `dp` while `install_model`, calling `score`
#: without naming one, took the *function* default `raw` — so installing a model
#: measured it undecoded (61.3% precision against 90.8% on identical weights) and
#: wrote that figure into the manifest, where it silently disagreed with what
#: `score` printed for the same checkpoint. `test_every_default_decoder_is_the
#: _same_decoder` holds this constant equal to those function defaults.
DECODE = "dp"
MIN_IOU = 0.5
BATCH = 8


def next_run(track: Track, root: Path = Path(".")) -> str:
    """A fresh `run-N` under the track's `model/`, never reused.

    Three copies of these five lines existed, one per track, and one of them
    returned an `int` while the other two returned `"run-N"` — so the caller's
    formatting was part of the contract in one place and not the other two.

    **The per-run directory is load-bearing rather than tidy.** `ketos` names its
    output `best_<score>.safetensors`, with the checkpoint's own accuracy in the
    filename, so it is not knowable until the run ends. Three runs writing into
    one directory leave their checkpoints distinguishable only by an accuracy,
    which is not an identity — two runs that scored alike are then one file.
    """
    n = 1
    while (Path(root) / track.rundir / f"run-{n}").exists():
        n += 1
    return f"run-{n}"
