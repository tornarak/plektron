"""The `train` group: the registry, the pools, and the refusals that make the
fold honest.

Three verbs (`zones`, `fig`, `ocr`) had each grown `remark-eval`/`assemble`/
`install`/`score`, three implementations of four acts. The fold is `views`' —
one group, a `TRACK` positional with a per-action pool — and the objection that
kept `zones blot` and `fig crops` *out* of that fold was capability: a merged
verb has "no way to express" what its members carry. So the load-bearing tests
here are the **refusals**. `--batch` is ocr's, `--min-iou` is fig's,
`--model`/`--decode`/`--jobs` are zones', and each must exit 2 on a track that
cannot use it. A silent no-op would mean a caller configured a training run with
a flag nothing read, which is the failure this project is organised against.

The second group of tests holds the fold to **changing nothing**. Every constant
the three modules used to declare is now read from `train.py`, and the values
must be identical — a fold that moves a path has moved a training set.
"""
from __future__ import annotations

import pytest

from harness import figures as F
from harness import recognize as R
from harness import train as T
from harness import zones as Z
from harness.cli import build_parser, main
from harness.cli._common import RENAMED_ACTIONS, _actions

# ---------------------------------------------------------------- the registry

def test_the_record_reproduces_every_constant_it_replaced():
    """**The fold must not move a path.** Each module read its own literals;
    they now come from the record, and a difference here is a training set
    laid out somewhere else or a model installed under another name."""
    assert (Z.WORKDIR, Z.DATADIR, Z.RUNDIR) == (
        "train/bogoras-seg", "train/bogoras-seg/data", "train/bogoras-seg/model")
    assert Z.MODELDIR == "models/bogoras-seg"
    assert Z.DEFAULT_MODEL == "models/bogoras-seg/zones-seg.safetensors"

    assert (F.WORKDIR, F.DATADIR, F.RUNDIR) == (
        "train/bogoras-fig", "train/bogoras-fig/data", "train/bogoras-fig/model")
    assert F.MODELDIR == "models/bogoras-fig"
    assert F.MODEL_NAME == "fig-seg"
    assert F.DEFAULT_MODEL == "models/bogoras-fig/fig-seg.safetensors"

    assert (R.WORKDIR, R.DATADIR, R.RUNDIR) == (
        "train/bogoras-ocr", "train/bogoras-ocr/data", "train/bogoras-ocr/model")
    assert R.MODELDIR == "models/bogoras-ocr"
    assert R.MODEL_NAME == "text-rec"
    assert R.INSTALLED_MODEL == "models/bogoras-ocr/text-rec.mlmodel"
    assert R.SPLIT_STORE == "gt/ocr"


def test_the_farm_registry_reads_its_train_path_from_the_record():
    """One home for `train/bogoras-seg`. The path is a property of the zone
    track and the farm is only the half of it that has members, so `farms`
    imports from `train` and never the reverse — which is also why `train` can
    be a leaf."""
    from harness import farms

    assert farms.TRAIN_WORK == T.ZONES.workdir
    assert farms.TRAIN_DATA == T.ZONES.datadir


def test_the_suffixes_differ_and_that_is_not_an_inconsistency():
    """The segmenters install `.safetensors` and the recognizer `.mlmodel`,
    because that is what each consumer loads. Pinned so a tidying pass that
    made them agree would fail rather than break the loaders."""
    assert T.ZONES.default_model.endswith(".safetensors")
    assert T.FIG.default_model.endswith(".safetensors")
    assert T.OCR.default_model.endswith(".mlmodel")


def test_the_recognizer_holds_back_less_and_says_why():
    """0.10 against the segmenters' 0.20: the unit here is a line, so a tenth of
    the keyed corpus is already thousands of held-out lines. A fifth would cost
    the training set 3 000 more to measure what the smaller share measures."""
    assert (T.ZONES.fraction, T.FIG.fraction, T.OCR.fraction) == (0.20, 0.20, 0.10)


def test_next_run_allocates_a_fresh_directory(tmp_path):
    """The per-run directory is load-bearing rather than tidy: `ketos` names its
    output `best_<score>.safetensors`, so runs sharing a directory are
    distinguishable only by an accuracy — which is not an identity."""
    assert T.next_run(T.ZONES, tmp_path) == "run-1"
    (tmp_path / T.ZONES.rundir / "run-1").mkdir(parents=True)
    assert T.next_run(T.ZONES, tmp_path) == "run-2"
    # Per track, not per repo: two tracks' run-1 are different directories.
    assert T.next_run(T.FIG, tmp_path) == "run-1"


# ---------------------------------------------------------------- the pools

def test_the_pools_only_promise_actions_that_exist():
    """`ocr` is absent from `install` and `score` because the recognizer has
    never been trained and neither action is implemented for it. A pool listing
    it would advertise a verb that cannot run — and `train remap`'s one-value
    pool is the same honesty from the other side: the act exists and applies to
    one track, which is not the same as the act not existing."""
    assert T.INSTALLABLE == ("zones", "fig") and "ocr" not in T.INSTALLABLE
    assert T.SCORABLE == ("zones", "fig") and "ocr" not in T.SCORABLE
    assert T.REMAPPABLE == ("zones",)
    assert T.SPLITTABLE == T.ASSEMBLABLE == ("zones", "fig", "ocr")


@pytest.mark.parametrize("act,pool", [
    ("remark-eval", T.SPLITTABLE), ("assemble", T.ASSEMBLABLE),
    ("install", T.INSTALLABLE), ("score", T.SCORABLE), ("remap", T.REMAPPABLE)])
def test_each_action_declares_its_own_pool(act, pool):
    """The parser's `click.Choice` is the pool, not a prose list. `views build`'s
    fence drifted in exactly this way — five of its farms are generated by a
    comprehension, so no hand-written list could track them."""
    cmd = _actions(build_parser())[("train", act)]
    got = next(p for p in cmd.params if p.name == "track")
    assert tuple(got.type.choices) == pool


def test_a_track_outside_the_pool_is_a_usage_error():
    assert main(["train", "remap", "fig"]) == 2
    assert main(["train", "score", "ocr"]) == 2
    assert main(["train", "install", "ocr", "x.safetensors"]) == 2


# ---------------------------------------------------------------- the refusals

@pytest.mark.parametrize("argv", [
    ["train", "assemble", "zones", "--batch", "8"],
    ["train", "assemble", "fig", "--batch", "8"],
    ["train", "score", "fig", "--model", "x.safetensors"],
    ["train", "score", "fig", "--decode", "raw"],
    ["train", "score", "fig", "--jobs", "2"],
    ["train", "score", "zones", "--min-iou", "0.5"],
    ["train", "install", "fig", "x.safetensors", "--jobs", "2"],
])
def test_a_flag_the_track_cannot_use_exits_2(argv):
    """**The capability objection, answered.** Silently ignoring the flag is the
    alternative and it is worse: the caller typed something, the tool did
    something else, and on `assemble` that means a training set laid out under a
    setting nothing read. `_common.one_page_only` is the same refusal."""
    assert main(argv) == 2


def test_the_refusal_names_the_tracks_that_do_accept_it(capsys):
    main(["train", "assemble", "zones", "--batch", "8"])
    err = capsys.readouterr()
    assert "--batch" in (err.err + err.out)
    assert "ocr only" in (err.err + err.out)


def test_score_fig_refuses_model_rather_than_ignoring_it(capsys):
    """The flag this fold had to fix. `figures.score` accepted a `model_path`,
    printed it in the report and **never opened it** — the comparison is always
    `mz/fig/` against `gt/fig/`, so the report named a checkpoint it had not
    consulted. Under one verb `--model` means "segment this in memory", which
    the figure track cannot do, so it refuses."""
    assert main(["train", "score", "fig", "--model", "x.safetensors"]) == 2
    out = capsys.readouterr()
    assert "zones only" in (out.err + out.out)


# ---------------------------------------------------------------- migration

@pytest.mark.parametrize("old,new", [
    (("zones", "assemble"), "train assemble zones"),
    (("zones", "score"), "train score zones"),
    (("zones", "install"), "train install zones"),
    (("zones", "remap"), "train remap zones"),
    (("zones", "remark-eval"), "train remark-eval zones"),
    (("fig", "assemble"), "train assemble fig"),
    (("fig", "score"), "train score fig"),
    (("fig", "install"), "train install fig"),
    (("fig", "remark-eval"), "train remark-eval fig"),
    (("ocr", "assemble"), "train assemble ocr"),
    (("ocr", "remark-eval"), "train remark-eval ocr"),
])
def test_every_moved_spelling_names_its_replacement(old, new):
    """Click answers a removed action with "No such command", which names the
    problem and not the fix. Nothing mechanical calls this harness — the
    consumers are documents and a human's memory — so the table is the only
    thing that carries a caller across."""
    assert RENAMED_ACTIONS[old] == new
    assert ("train", new.split()[1]) in _actions(build_parser())


def test_the_moved_actions_are_gone_from_their_old_groups():
    """The other direction: a fold that left the old spelling working would be
    two surfaces for one act, which is what the fold was for."""
    live = _actions(build_parser())
    for group, act in RENAMED_ACTIONS:
        if group in ("zones", "fig", "ocr"):
            assert (group, act) not in live, f"{group} {act} still exists"
