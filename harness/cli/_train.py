"""`harness train` — the three model-training tracks under one verb.

An action lands here if its subject is *training a model*: minting the held-out
split, laying out the training set, installing a checkpoint, scoring one. What
stays behind in `zones`, `fig` and `ocr` is everything about the **stores** —
`predict` writes `mz/` and is inference, `propose` is a rule, `blot` paints
rasters, `check`/`edit`/`delete` are the store's own.

**TRACK is a positional with a per-action pool**, which is `views`' shape: `views
check` takes `F.NAMES` and `views build` takes `F.BUILDABLE`, and the selector is
a positional because `--only` already means "line indices" throughout `ocr` and
the harness holds to one meaning per flag name. A one-value pool (`train remap
zones`) is honest rather than a smell: it says the act exists and applies to one
track, which is a different statement from the act not existing.

**No `--all`.** `views` needed it because relinking every farm is one coherent
act. Assembling three unrelated training sets is not, and "everything" on the
most expensive verbs in the harness would be a trap rather than a convenience.

**A flag that does not apply to the named track is a parse-time refusal, not a
silent no-op** (`_track_only`, modelled on `_common.one_page_only`). This is
precisely the capability objection that killed the `zones blot`/`fig crops` fold —
a merged verb having "no way to express" what its members carry — and the refusal
is what answers it: the capability is still expressible, and asking for it on a
track that has none is an error rather than a shrug.

**`--model` is the flag that had to change meaning, and Phase 1 is why it could.**
`zones score --model` loads the checkpoint and segments in memory; `fig score
--model` accepted a path, named it in the report and **never opened it**, because
that comparison is always `mz/fig/` against `gt/fig/`. Under one verb the flag
means one thing — "score this checkpoint in memory" — and it refuses for `fig`,
naming the store to read instead. With `mz/` provenance in place, `train score
fig` reports the producer it actually read out of the store, which is the true
answer to the question `--model` was pretending to answer.
"""
from __future__ import annotations

import click

from .. import train as T
from ._common import action, arg, group, opt
from ._common import add_jobs as _add_jobs
from ._zones import DECODE_HELP, DEVICE_HELP, MODEL_HELP


def register(cli):
    g = group(cli, "train", "train, score and install this project's models — "
              "the zone segmenter, the figure segmenter and the text "
              "recognizer, one track each",
              section="Whole-corpus")

    p = action(g, "remark-eval", run_remark_eval, pageable=False,
               help="mint or extend a track's train/eval split. Stratified per "
               "part, independent pages first, spread rather than taken off the "
               "front. **Additive**: a mark a human already made is never moved, "
               "or the held-out set drifts with whatever was keyed last and "
               "stops being held out")
    _track_arg(p, T.SPLITTABLE)
    opt(p, "--fraction", type=float, default=None, metavar="F",
        help="share to hold out [the track's own: 0.20 for the segmenters, "
             "0.10 for ocr, whose unit is a line rather than a page]")
    opt(p, "--commit", is_flag=True,
        help="write the split marks; without it, a preview")

    p = action(g, "assemble", run_assemble, pageable=False,
               help="lay out a track's train/bogoras-*/data/ from its split "
               "marks and report the ketos invocation. **Runs nothing** — a run "
               "holds the GPU for hours and belongs in your own terminal. Pure "
               "scratch: the split a model trained on travels in that model's "
               "own manifest, so this may be clobbered freely")
    _track_arg(p, T.ASSEMBLABLE)
    opt(p, "--scratch", is_flag=True,
        help="train from random init rather than fine-tuning the base model. "
             "For the segmenters it is also the one configuration in which the "
             "class-map permutation cannot arise, there being no output layer "
             "to renumber")
    opt(p, "--batch", type=int, default=None, metavar="N",
        help=f"ocr only: lines per forward pass in the reported command "
             f"[{T.BATCH}]. The first thing to lower if the run runs out of VRAM")

    p = action(g, "install", run_install, pageable=False,
               help="score a checkpoint, **refuse a permuted class map**, then "
               "install it into models/bogoras-*/ with a manifest and the split "
               "it consumed. Everything that makes a checkpoint trustworthy is a "
               "precondition of the artifact existing, so the copy is last")
    _track_arg(p, T.INSTALLABLE)
    arg(p, "checkpoint", metavar="CHECKPOINT")
    p.help += ("\n\nCHECKPOINT: the .safetensors a run wrote. It is named "
               "best_<score>.safetensors in the run's own directory — ketos puts "
               "the checkpoint's own accuracy in the filename, so it is not "
               "knowable until the run ends.")
    opt(p, "--name", default=None,
        help="installed model name [the track's own]. The accuracy stays out of "
             "it: a default path that changes every retrain is a default nobody "
             "can use")
    opt(p, "--device", default="auto", help=DEVICE_HELP)
    opt(p, "--commit", is_flag=True,
        help="copy the checkpoint and its split into models/; preview otherwise")
    _add_jobs(p, processes=True)

    p = action(g, "score", run_score, pageable=False,
               help="compare a track's mz/ store against its ground truth, per "
               "split and never blended — agreement on the trained-on pages is "
               "the editor's own judgement read back. Measurement: exit 0")
    _track_arg(p, T.SCORABLE)
    opt(p, "--model", default=None,
        help=f"zones only: {MODEL_HELP}. Given, the checkpoint is segmented in "
             "memory rather than read out of mz/zones/. Refused for fig, whose "
             "score always reads the store — see the group help")
    opt(p, "--decode", type=click.Choice(("raw", "dp")), default=None,
        help=f"zones only: {DECODE_HELP}")
    opt(p, "--device", default="auto", help=DEVICE_HELP)
    opt(p, "--min-iou", type=float, default=None, metavar="F",
        help=f"fig only: area overlap at which a predicted box counts as "
             f"found [{T.MIN_IOU}]")
    _add_jobs(p, processes=True)

    p = action(g, "remap", run_remap, pageable=False,
               help="put the learned names back on the model's output channels, "
               "when `score` shows the disagreement is a consistent relabelling "
               "rather than a weak model. Derives the map on the training pages, "
               "refuses unless it is 1-1 and holds out; the original is kept "
               "as .bak")
    _track_arg(p, T.REMAPPABLE)
    opt(p, "--model", default=None, help=MODEL_HELP)
    opt(p, "--commit", is_flag=True,
        help="rewrite the model's class map; preview otherwise")


def _track_arg(p, pool):
    """The track selector, identical on every action but for its pool."""
    arg(p, "track", metavar="TRACK", type=click.Choice(pool))
    p.help = (f"{p.help}\n\nTRACK: which model. One of: {', '.join(pool)}.")


def _track_only(a, flags: dict[str, tuple[str, ...]]) -> None:
    """Refuse a flag the named track has no way to use.

    `flags` maps the attribute to `(spelling, *tracks that accept it)`. A silent
    no-op is the alternative and it is worse than an error: the caller typed
    something, the tool did something else, and nothing said so — which on a verb
    that lays out a training set means a run configured by a flag that was never
    read. `_common.one_page_only` is the same refusal for the same reason.
    """
    for attr, spec in flags.items():
        spelling, tracks = spec[0], spec[1:]
        if getattr(a, attr, None) is not None and a.track not in tracks:
            raise ValueError(
                f"{spelling} does not apply to the {a.track} track — it is "
                f"{'/'.join(tracks)} only. One meaning per flag name, so a flag "
                "that means nothing here is an error rather than an omission")


def _fill(a, **defaults):
    """Put a track's own default on the namespace where the caller named none.

    A shared flag has to parse with `default=None` — three tracks' defaults
    differ, and a value written into the parser would be one track's answer given
    to all three. So the default is applied here, from the record, and the
    delegate below sees exactly the namespace its own registration used to build.
    """
    for k, v in defaults.items():
        if getattr(a, k, None) is None:
            setattr(a, k, v)
    return a


#: **The bodies are delegated, not reimplemented, and that is deliberate.**
#: Each existing runner does real work after the call — `zones score` splits out
#: the confusion matrix and the per-split composition, `fig score` builds the
#: per-class table and the `spurious_on_empty` bucket, `ocr assemble` numbers four
#: commands. Rewriting them here would change three report shapes in the same
#: commit that moves the verbs, and a fold that changes a number has changed
#: behaviour: there would be no way to tell a fold bug from an intended
#: normalization. So the group is a **surface** over the same bodies, and the
#: reports are identical field for field.
#:
#: The plan this came from called for a normalized `{track, dir, train, eval,
#: base, missing, commands}` head, as `farms.build` does for its builders. That
#: is still worth doing and is not done here, for the reason above — it is a
#: second change, with its own before-and-after.


def run_remark_eval(a) -> int:
    a = _fill(a, fraction=T.BY_NAME[a.track].fraction)
    if a.track == "zones":
        from ._zones import run_remark_eval as delegate
    elif a.track == "fig":
        from ._fig import run_remark as delegate
    else:
        from ._ocr import run_remark_eval as delegate
    return delegate(a)


def run_assemble(a) -> int:
    _track_only(a, {"batch": ("--batch", "ocr")})
    a = _fill(a, batch=T.BATCH)
    if a.track == "zones":
        from ._zones import run_assemble as delegate
    elif a.track == "fig":
        from ._fig import run_assemble as delegate
    else:
        from ._ocr import run_assemble as delegate
    return delegate(a)


def run_install(a) -> int:
    _track_only(a, {"jobs": ("--jobs", "zones")})
    a = _fill(a, name=T.BY_NAME[a.track].model_name)
    if a.track == "zones":
        from ._zones import run_install as delegate
    else:
        from ._fig import run_install as delegate
    return delegate(a)


def run_score(a) -> int:
    _track_only(a, {"model": ("--model", "zones"),
                    "decode": ("--decode", "zones"),
                    "jobs": ("--jobs", "zones"),
                    "min_iou": ("--min-iou", "fig")})
    a = _fill(a, decode=T.DECODE, min_iou=T.MIN_IOU)
    if a.track == "zones":
        from ._zones import run_score as delegate
    else:
        from ._fig import run_score as delegate
    return delegate(a)


def run_remap(a) -> int:
    from ._zones import run_remap as delegate
    return delegate(a)
