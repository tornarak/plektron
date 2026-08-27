"""Every long sweep reports the page it is on, and the report survives forwarding.

**Why these assertions and not an output check.** `render.progress` yields `None`
whenever stderr is not a terminal, and under pytest it never is — so nothing
observable reaches a captured stream and a test that read stdout or stderr would
pass with the instrumentation ripped out. The recorder is injected as `tick`
instead, which is what `test_parallel.py` does for the same reason.

The defect these cover is not "a bar exists" but **a `tick` that stops partway
down**: `train score zones` accepted no callback at all and ran `blla.segment` over 717
pages in silence — minutes indistinguishable from a hung process — because the
chain `install_model -> score -> predicted_zones` had nowhere to put one. So the
forwarding tests assert **object identity**, which is the cheapest true statement
about a value passed through three frames untouched.

The other half is the denominator. A sweep that ticks only the pages it did real
work on reports a total that shrinks as it goes, and the caller asked about all of
them: a skipped page is a page whose answer is "nothing to do", not a page that was
never named.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from conftest import write_scan

from harness import farms
from harness import figures as F
from harness import zones as zn


class Recorder:
    """A `tick(item, done, total)` that remembers, and can be identity-checked."""

    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, item, done: int, total: int) -> None:
        self.calls.append((str(item), done, total))

    @property
    def items(self) -> list[str]:
        return [i for i, _, _ in self.calls]

    def assert_counts_up_to(self, n: int) -> None:
        assert [d for _, d, _ in self.calls] == list(range(1, n + 1)), \
            "the count must be monotonic and start at 1"
        assert {t for _, _, t in self.calls} == {n}, \
            "the total must be the work-list the caller named, and must not move"


# ------------------------------------------------------------ figures.predict

@pytest.fixture
def fig_root(tmp_path: Path, monkeypatch) -> Path:
    """Three pages, one of which has no raster at all."""
    for ref in ("1-021", "1-022"):
        write_scan(tmp_path, ref, size=(2824, 3897))

    monkeypatch.setattr(
        zn, "load_segmenter", lambda *a, **k: (object(), "0" * 64))
    monkeypatch.setattr(
        F, "_predict_one",
        lambda ref, *a, **k: {"ref": ref, "wrote": True})
    return tmp_path


def test_fig_predict_ticks_every_page_including_the_ones_it_skips(fig_root):
    """`2-999` has no raster and is a row saying so — and still a page that was
    asked about. Counting only the pages that segmented would make `--all`'s total
    drop below the 832 the caller named, halfway through a long run."""
    tick = Recorder()
    refs = ["1-021", "1-022", "2-999"]
    rows = F.predict(refs, fig_root, device="cpu", tick=tick)

    assert [r["ref"] for r in rows] == refs
    assert tick.items == refs
    tick.assert_counts_up_to(3)


def test_fig_predict_without_a_tick_is_the_old_behaviour(fig_root):
    """`tick=None` is the default and must stay a no-op: every sweep in this repo
    has to run identically with the reporting off, or the benches stop being
    diffable against it."""
    assert len(F.predict(["1-021", "1-022"], fig_root, device="cpu")) == 2


# --------------------------------------------------------- zones.predicted_zones

def test_predicted_zones_ticks_every_ref_including_the_blotless(tmp_path,
                                                                monkeypatch):
    """The zone twin of the above, and the one that matters most: this is the loop
    that was silent throughout. A page with no blot returns `[]` and is still
    counted."""
    blots = tmp_path / "scans" / "w-figs-blotted"
    blots.mkdir(parents=True)
    write_scan(tmp_path, "1-021", size=(64, 64))
    (blots / "chukchi-1-021.png").write_bytes(
        (tmp_path / "scans" / "chukchi-1-021.png").read_bytes())

    (tmp_path / "m.safetensors").write_bytes(b"pretend weights")
    monkeypatch.setattr(zn, "load_segmenter", lambda *a, **k: (object(), "0" * 64))

    # kraken is stubbed in `sys.modules` rather than imported: `predicted_zones`
    # does `from kraken import blla` inside the function, and this module has no
    # business paying for torch to prove a loop counts.
    class _Seg:
        regions: dict = {}

    fake_kraken = types.ModuleType("kraken")
    fake_blla = types.ModuleType("kraken.blla")
    fake_blla.segment = lambda *a, **k: _Seg()
    fake_kraken.blla = fake_blla
    monkeypatch.setitem(sys.modules, "kraken", fake_kraken)
    monkeypatch.setitem(sys.modules, "kraken.blla", fake_blla)

    tick = Recorder()
    refs = ["1-021", "1-099"]          # the second has no blot
    # `raw` named, because this stubs `blla.segment` and nothing else: the test is
    # about the loop's counting, so it should say which decoder it walks rather
    # than inherit whichever one is currently the default.
    out = zn.predicted_zones(refs, tmp_path, cfg={"min_zone_h_px": 30},
                             model_path="m.safetensors", device="cpu",
                             decode="raw", tick=tick)

    assert out["1-099"] == []
    # **Every ref reported, in no promised order.** A page needing no work — no
    # blot, or a cache hit — is reported the moment it is found, and a segmented
    # one when it finishes; under `--jobs` the second group finishes out of order
    # by construction. What must hold is the count and the total, since those are
    # what a reader is actually reading off the bar.
    assert sorted(tick.items) == sorted(refs)
    tick.assert_counts_up_to(2)


def _one_blotted_page(tmp_path: Path, ref: str = "1-021") -> Path:
    blots = tmp_path / "scans" / "w-figs-blotted"
    blots.mkdir(parents=True, exist_ok=True)
    write_scan(tmp_path, ref, size=(64, 64))
    blot = blots / f"chukchi-{ref}.png"
    blot.write_bytes((tmp_path / "scans" / f"chukchi-{ref}.png").read_bytes())
    return blot


@pytest.fixture
def fake_segmenter(tmp_path, monkeypatch):
    """A counting stand-in for the segmentation call, so a cache hit is observable.

    Writes a real `m.safetensors` too, because the cache key is the **file's**
    sha256 rather than a loaded model's: the parent hashes the bytes and never
    opens a CUDA context, which is what keeps a pool of `n` workers to `n`
    contexts on the card instead of `n + 1`.
    """
    (tmp_path / "m.safetensors").write_bytes(b"pretend weights")
    calls = {"n": 0}

    class _Seg:
        regions: dict = {}

    def segment(*a, **k):
        calls["n"] += 1
        return _Seg()

    fake_kraken = types.ModuleType("kraken")
    fake_blla = types.ModuleType("kraken.blla")
    fake_blla.segment = segment
    fake_kraken.blla = fake_blla
    monkeypatch.setitem(sys.modules, "kraken", fake_kraken)
    monkeypatch.setitem(sys.modules, "kraken.blla", fake_blla)
    monkeypatch.setattr(zn, "load_segmenter", lambda *a, **k: (object(), "ab" * 32))
    # **Both decoders, counted together.** These tests are about the cache and not
    # about decoding, and stubbing only `blla.segment` quietly tied them to `raw` —
    # which stopped being the default the moment `score`'s function default was
    # brought into line with the CLI's `dp`. A fixture that covers one path is a
    # test that silently changes subject when a default moves.
    def dp(*a, **k):
        calls["n"] += 1
        return []

    monkeypatch.setattr(zn, "_dp_zones", dp)
    return calls


CFG = {"min_zone_h_px": 30}


def test_the_second_run_reads_the_cache_instead_of_segmenting(tmp_path,
                                                              fake_segmenter):
    """`install_model` calls `score`, so installing a model *is* this sweep, and the
    documented workflow runs it twice over one checkpoint in two separate processes
    — ~11 min each, every page re-derived from identical weights over identical
    rasters. Measured warm against the installed model: 0.96 s a page under `raw`,
    0.58 under `dp`, and about five seconds for the whole 717 on a cache hit."""
    _one_blotted_page(tmp_path)
    first: dict = {}
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu", stats=first)
    assert fake_segmenter["n"] == 1 and first["cached"] == 0

    second: dict = {}
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu", stats=second)
    assert fake_segmenter["n"] == 1, "the second run must not segment again"
    assert second["cached"] == 1


def test_a_repainted_blot_is_a_miss_not_a_stale_hit(tmp_path, fake_segmenter):
    """`_ink_cache`'s rule: an entry whose stamp no longer matches is **unknown**,
    never stale-but-usable. The blot is what this reads, so the blot is what
    stamps it — `corpus_digest` digests `gt/zones/` geometry and a repainted
    raster does not move it."""
    blot = _one_blotted_page(tmp_path)
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu")
    assert fake_segmenter["n"] == 1

    blot.write_bytes(blot.read_bytes() + b"\0")      # repainted: size and mtime move
    stats: dict = {}
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu", stats=stats)
    assert fake_segmenter["n"] == 2 and stats["cached"] == 0


def test_a_different_checkpoint_cannot_read_another_ones_cache(tmp_path,
                                                               monkeypatch):
    """The key is the weights' own sha256, which is why no flag is needed to make
    this safe: two checkpoints cannot collide, and a stale hit is unreachable by
    any sequence a human can type.

    Two real files with different bytes, since the key is now taken off the file
    rather than out of a loaded model — which is the point, and is also what keeps
    the parent from holding a CUDA context it does not need.
    """
    _one_blotted_page(tmp_path)
    (tmp_path / "a.safetensors").write_bytes(b"weights A")
    (tmp_path / "b.safetensors").write_bytes(b"weights B")
    calls = {"n": 0}

    class _Seg:
        regions: dict = {}

    fake_kraken = types.ModuleType("kraken")
    fake_blla = types.ModuleType("kraken.blla")

    def segment(*a, **k):
        calls["n"] += 1
        return _Seg()

    fake_blla.segment = segment
    fake_kraken.blla = fake_blla
    monkeypatch.setitem(sys.modules, "kraken", fake_kraken)
    monkeypatch.setitem(sys.modules, "kraken.blla", fake_blla)

    monkeypatch.setattr(zn, "load_segmenter", lambda *a, **k: (object(), "x" * 64))
    for name in ("a.safetensors", "b.safetensors"):
        zn.predicted_zones(["1-021"], tmp_path, CFG, model_path=name,
                           device="cpu", decode="raw")
    assert calls["n"] == 2, "the second checkpoint must segment for itself"
    assert len(list((zn.zone_dir(tmp_path, zn.MZDIR) / zn.PRED_CACHE).iterdir())) == 2


def test_the_cache_hides_from_every_store_reader(tmp_path, fake_segmenter):
    """It lives under `mz/zones/`, which is the store for what a model emitted —
    but these are a *candidate* model's and must never be counted as the installed
    one's. `zone_refs` globs `chukchi-*.xml`, so the directory is invisible to it."""
    _one_blotted_page(tmp_path)
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu")
    assert (zn.zone_dir(tmp_path, zn.MZDIR) / zn.PRED_CACHE).is_dir()
    assert zn.zone_refs(tmp_path, zn.MZDIR) == []


def test_cache_false_is_the_control_arm(tmp_path, fake_segmenter):
    """Every cache in this repo has to be diffable against itself switched off."""
    _one_blotted_page(tmp_path)
    for _ in range(2):
        zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                           device="cpu", cache=False)
    assert fake_segmenter["n"] == 2
    assert not (zn.zone_dir(tmp_path, zn.MZDIR) / zn.PRED_CACHE).exists()


def test_the_dp_decode_is_cached_under_its_config(tmp_path, fake_segmenter,
                                                  monkeypatch):
    """**`dp` has to be cached too, and this is the case that nearly went missing.**
    `train score zones`'s CLI default is `dp` while `install_model` takes `score`'s own
    default and gets `raw` — so a raw-only cache would have left the verb a human
    actually runs paying full price, which is how the omission was caught.

    `_dp_zones` reads the config, so the config is part of the input and part of
    the key: an edit to `config/zones_config.json` must miss, not hand back zones
    decoded against numbers nobody is using any more.
    """
    calls = {"n": 0}

    def fake_dp(*a, **k):
        calls["n"] += 1
        return []

    _one_blotted_page(tmp_path)
    monkeypatch.setattr(zn, "_dp_zones", fake_dp)

    for _ in range(2):
        zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                           device="cpu", decode="dp")
    assert calls["n"] == 1, "the second dp run must read the cache"

    zn.predicted_zones(["1-021"], tmp_path, {**CFG, "min_zone_h_px": 31},
                       model_path="m.safetensors", device="cpu", decode="dp")
    assert calls["n"] == 2, "a changed config must miss, never hand back stale zones"


def test_the_two_decoders_never_share_an_entry(tmp_path, fake_segmenter,
                                               monkeypatch):
    """The same weights over the same page give different zones under `raw` and
    `dp` — 61.3% precision against 90.8%, which is the reason `dp` is the default.
    One cache entry for both would hand each verb the other's answer."""
    monkeypatch.setattr(zn, "_dp_zones", lambda *a, **k: [{"label": "dp-shaped"}])
    _one_blotted_page(tmp_path)

    raw = zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                             device="cpu", decode="raw")
    dp = zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                            device="cpu", decode="dp")
    assert raw["1-021"] == [] and dp["1-021"] == [{"label": "dp-shaped"}]

    again: dict = {}
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu", decode="raw", stats=again)
    assert again["cached"] == 1, "raw must still find its own entry, not dp's"


def test_jobs_1_is_the_serial_path_and_spawns_nothing(tmp_path, fake_segmenter,
                                                      monkeypatch):
    """`--jobs 1` has to stay the in-process loop, verbatim. It is the control arm
    every pooled sweep in this repo is diffed against, so a pool that quietly ran
    with one worker would make the comparison meaningless — both sides would be
    the pool."""
    _one_blotted_page(tmp_path)
    _one_blotted_page(tmp_path, "1-022")

    def refuse(*a, **k):
        raise AssertionError("--jobs 1 must not build a pool")

    monkeypatch.setattr(zn, "_segment_pool", refuse)
    stats: dict = {}
    zn.predicted_zones(["1-021", "1-022"], tmp_path, CFG,
                       model_path="m.safetensors", device="cpu", jobs=1,
                       stats=stats)
    assert stats["workers"] == 1 and fake_segmenter["n"] == 2


def test_a_pool_returns_pages_in_the_order_they_were_asked_for(tmp_path,
                                                               fake_segmenter,
                                                               monkeypatch):
    """`as_completed` into a pre-sized list, `recognize._predict_pool`'s rule: the
    report must not reshuffle by which page happened to finish first. Asserted
    against a stand-in pool that deliberately completes backwards."""
    for r in ("1-021", "1-022", "1-031"):
        _one_blotted_page(tmp_path, r)
    refs = ["1-021", "1-022", "1-031"]

    def fake_pool(todo, n, root, model_path, device, decode, cfg, tick=None,
                  done_before=0, total=0, on_done=None):
        # Landing backwards, to prove the caller's dict is keyed by ref and does
        # not depend on completion order.
        for k, (ref, blot) in enumerate(reversed(todo), 1):
            if on_done:
                on_done(ref, blot, [{"label": ref}])
            if tick:
                tick(ref, done_before + k, total)
        return [[{"label": ref}] for ref, _b in todo], {"stderr_lines": 0}

    monkeypatch.setattr(zn, "_segment_pool", fake_pool)
    monkeypatch.setattr(zn, "gpu_workers", lambda jobs, n: 4)

    tick = Recorder()
    out = zn.predicted_zones(refs, tmp_path, CFG, model_path="m.safetensors",
                             device="cpu", jobs=4, tick=tick)
    assert [out[r][0]["label"] for r in refs] == refs, "results follow the ask"
    tick.assert_counts_up_to(3)


def test_a_pooled_run_still_writes_the_cache(tmp_path, fake_segmenter,
                                             monkeypatch):
    """The cache is the parent's, never a worker's — so it must be filled on the
    pooled path too, or the pool would quietly disable Stage 1."""
    _one_blotted_page(tmp_path)

    def fake_pool(todo, n, root, model_path, device, decode, cfg, tick=None,
                  done_before=0, total=0, on_done=None):
        rows = []
        for ref, blot in todo:
            zones = [{"label": "MainZone-P"}]
            rows.append(zones)
            # Per completion, which is the contract: a killed pooled run has to
            # keep the pages it finished, as the serial path does.
            if on_done:
                on_done(ref, blot, zones)
        return rows, {"stderr_lines": 0}

    monkeypatch.setattr(zn, "_segment_pool", fake_pool)
    monkeypatch.setattr(zn, "gpu_workers", lambda jobs, n: 4)
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu", jobs=4)

    stats: dict = {}
    again = zn.predicted_zones(["1-021"], tmp_path, CFG,
                               model_path="m.safetensors", device="cpu",
                               jobs=1, stats=stats)
    assert stats["cached"] == 1 and again["1-021"] == [{"label": "MainZone-P"}]


def test_a_killed_pooled_run_keeps_the_pages_it_finished(tmp_path,
                                                         fake_segmenter,
                                                         monkeypatch):
    """**Caching per completion, not per sweep.** The serial path always stored
    each page as it finished; routing the misses through a pool and storing the
    returned list afterwards silently took that away, so a killed run left nothing
    — on exactly the runs long enough to be killed, which is what the cache is
    for. Modelled by a pool that lands two pages and then dies."""
    for r in ("1-021", "1-022", "1-031"):
        _one_blotted_page(tmp_path, r)

    def dying_pool(todo, n, root, model_path, device, decode, cfg, tick=None,
                   done_before=0, total=0, on_done=None):
        for k, (ref, blot) in enumerate(todo):
            if k == 2:
                raise KeyboardInterrupt("killed mid-sweep")
            on_done(ref, blot, [{"label": "MainZone-P"}])
        raise AssertionError("unreachable")

    monkeypatch.setattr(zn, "_segment_pool", dying_pool)
    monkeypatch.setattr(zn, "gpu_workers", lambda jobs, n: 4)
    with pytest.raises(KeyboardInterrupt):
        zn.predicted_zones(["1-021", "1-022", "1-031"], tmp_path, CFG,
                           model_path="m.safetensors", device="cpu", jobs=4)

    cached = list((zn.zone_dir(tmp_path, zn.MZDIR) / zn.PRED_CACHE).glob("*/*.json"))
    assert sorted(p.stem for p in cached) == ["chukchi-1-021", "chukchi-1-022"]


def test_cached_pages_never_reach_the_pool(tmp_path, fake_segmenter, monkeypatch):
    """A hit costs a stat and a small JSON read, so shipping one to another process
    would cost more than it saves. The pool gets the misses and nothing else."""
    for r in ("1-021", "1-022"):
        _one_blotted_page(tmp_path, r)
    zn.predicted_zones(["1-021"], tmp_path, CFG, model_path="m.safetensors",
                       device="cpu", jobs=1)          # 1-021 now cached

    seen: dict = {}

    def fake_pool(todo, n, root, model_path, device, decode, cfg, tick=None,
                  done_before=0, total=0, on_done=None):
        seen["todo"] = [ref for ref, _b in todo]
        for ref, blot in todo:
            if on_done:
                on_done(ref, blot, [])
        return [[] for _ in todo], {"stderr_lines": 0}

    monkeypatch.setattr(zn, "_segment_pool", fake_pool)
    monkeypatch.setattr(zn, "gpu_workers", lambda jobs, n: 4)
    stats: dict = {}
    zn.predicted_zones(["1-021", "1-022"], tmp_path, CFG,
                       model_path="m.safetensors", device="cpu", jobs=4,
                       stats=stats)
    assert seen["todo"] == ["1-022"] and stats["cached"] == 1


def test_every_default_decoder_is_the_same_decoder():
    """**The CLI's default and the function defaults must agree, and they did not.**

    `train score zones --model X` decoded `dp`; `install_model`, which calls `score`
    without naming one, got the *function* default `raw` — so installing a model
    measured it undecoded (61.3% precision against 90.8% on identical weights) and
    wrote that figure into the manifest, where it disagreed with what `train score zones`
    printed for the same checkpoint with nothing to say why.

    This is the hazard `DECODE_HELP` names in its own last sentence — the 30-point
    decode being what you get by leaving an argument off — surviving one level
    below the flag that was written to prevent it.

    **The declared default moved when the three tracks folded into `train`**, and
    it had to. One `--decode` now serves a pool, so the option must parse with
    `default=None` — a value on the option would be one track's answer given to
    all of them — and `_train._fill` applies `train.DECODE` afterwards. So the
    assertion reads that constant rather than the flag: the guarantee is
    unchanged, but the thing it must be read off is no longer the parser.

    The flag is still checked for `None`, because a literal creeping back onto it
    would take precedence over the constant and quietly restore the split this
    test exists to prevent.
    """
    import inspect

    from harness import train as T
    from harness.cli import build_parser
    from harness.cli._common import _actions

    cli = _actions(build_parser())[("train", "score")]
    flag = next(p for p in cli.params if "--decode" in p.opts)
    assert flag.default is None, (
        "--decode carries a parser default again. It serves a pool of tracks now, "
        "so the default belongs to `train.DECODE`, which is what the functions "
        "below are held against")
    assert T.DECODE == "dp"
    for fn in (zn.score, zn.predicted_zones, zn.install_model):
        got = inspect.signature(fn).parameters["decode"].default
        assert got == T.DECODE, (
            f"{fn.__name__} defaults to {got!r} where `train score zones --decode` "
            f"defaults to {T.DECODE!r}")


def test_the_manifest_records_which_decoder_scored_the_model(tmp_path,
                                                             monkeypatch):
    """A precision figure whose method is unstated cannot be compared with
    anything, and this one has a 30-point twin."""
    import json

    monkeypatch.setattr(zn, "score", lambda *a, **k: {
        "permutation": {"bijective": False, "is_identity": True, "holds_out": 0},
        "splits": [], "pages_compared": 0})
    monkeypatch.setattr(zn, "corpus_digest", lambda *a, **k: "d" * 16)

    lists = tmp_path / zn.DATADIR
    lists.mkdir(parents=True)
    for split in ("train", "eval"):
        (lists / f"{split}.lst").write_text(
            f"{zn.DATADIR}/chukchi-1-021.xml\n", encoding="utf-8")
    ckpt = tmp_path / "best.safetensors"
    ckpt.write_bytes(b"w")

    zn.install_model(ckpt, tmp_path, cfg={"min_zone_h_px": 30}, commit=True)
    man = json.loads(
        (tmp_path / "models/bogoras-seg/zones-seg.json").read_text(encoding="utf-8"))
    assert man["decode"] == "dp"


def test_the_store_branch_takes_no_tick_and_wants_none(tmp_path):
    """Reading `mz/zones/` is ~0.1 s over the whole corpus. A bar there is the
    flash `PROGRESS_AFTER` exists to suppress, so the branch is deliberately
    uninstrumented — asserted so a later 'consistency' edit has to argue with it."""
    tick = Recorder()
    zn.predicted_zones(["1-021"], tmp_path, model_path=None, tick=tick)
    assert tick.calls == []


# ------------------------------------------------------------------ forwarding

def test_score_hands_its_tick_to_the_sweep(tmp_path, monkeypatch):
    seen = {}

    def fake_preds(refs, root, cfg, model_path, decode, device, tick=None,
                   **kw):
        seen["tick"] = tick
        return {}

    monkeypatch.setattr(zn, "predicted_zones", fake_preds)
    monkeypatch.setattr(zn, "_frozen_splits", lambda root: {"1-021": "train"})
    monkeypatch.setattr(zn, "zone_refs", lambda root, store=None: [])

    tick = Recorder()
    zn.score(tmp_path, {"min_zone_h_px": 30}, model_path="m.safetensors",
             tick=tick)
    assert seen["tick"] is tick, "the sweep must get the caller's own callback"


def test_install_hands_its_tick_through_score(tmp_path, monkeypatch):
    """`install` is the verb that hurt, and it is two frames from the loop."""
    seen = {}

    def fake_score(root, cfg=None, model_path=None, decode="raw",
                   device="auto", tick=None, **kw):
        seen["tick"] = tick
        raise RuntimeError("far enough")

    monkeypatch.setattr(zn, "score", fake_score)
    ckpt = tmp_path / "best.safetensors"
    ckpt.write_bytes(b"x")

    tick = Recorder()
    with pytest.raises(RuntimeError, match="far enough"):
        zn.install_model(ckpt, tmp_path, cfg={"min_zone_h_px": 30}, tick=tick)
    assert seen["tick"] is tick


def test_crop_all_hands_its_tick_to_pmap(tmp_path, monkeypatch):
    seen = {}
    # `crop_all` imports `pmap` from `.parallel` inside the function, so the module
    # it is patched on is that one, not `figures`.
    from harness import parallel

    def fake_pmap(fn, items, jobs=None, tick=None):
        seen["tick"] = tick
        return []

    monkeypatch.setattr(parallel, "pmap", fake_pmap)

    tick = Recorder()
    F.crop_all([], tmp_path, tick=tick)
    assert seen["tick"] is tick


def test_views_build_hands_jobs_and_tick_to_the_raster_builders(tmp_path,
                                                                monkeypatch):
    """The gap this closes: `blot_all` accepts both and draws a bar through
    `zones blot`, and `farms.build` dropped them — so the same work was silent
    down the more expensive route."""
    seen = {}
    (tmp_path / "scans").mkdir()

    def fake_blot_all(root, jobs=None, tick=None):
        seen["jobs"], seen["tick"] = jobs, tick
        return {"dir": "x", "total": 0}

    monkeypatch.setattr(zn, "blot_all", fake_blot_all)

    tick = Recorder()
    farms.build("w-figs-blotted", tmp_path, 3, tick)
    assert seen["jobs"] == 3 and seen["tick"] is tick
