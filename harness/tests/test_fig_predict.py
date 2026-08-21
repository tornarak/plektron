"""`fig predict`'s two arguments, and why only a call-level test can see them.

`figures.predict` called `zones.load_segmenter(model_path, device)` where the
signature is `(model_path, root)` returning `(net, sha256)`. Three faults came
off that one line and none of them raises where it is written: the model
resolved under `auto/` rather than the repo root, `blla.segment` was handed a
sha256 as its device, and the `ProcessingStep` — an `mz/` file's only witness to
which model wrote it — recorded that sha as the device. All nine other
`load_segmenter` call sites pass `root`.

**There is no output to assert on.** `models/bogoras-fig/` does not exist, so
this verb has never run: no before-state, no golden file, and the failure it
produced would have been a `FileNotFoundError` naming a path nobody asked for.
So the assertions are on the *call*, which is where the fault is visible.

`_predict_one` is the boundary tested rather than `blla.segment` itself, to keep
kraken and torch out of this module. That is sound here because the argument is
passed straight through: `_predict_one`'s `dev` reaches `blla.segment(device=)`
and the `ProcessingStep` text with nothing between, so a wrong value at the
boundary is a wrong value at both consumers.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_scan

from harness import figures as F
from harness import zones as zn


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_scan(tmp_path, "1-021", size=(2824, 3897))
    return tmp_path


@pytest.fixture
def calls(monkeypatch):
    """Capture both boundaries `predict` crosses, and run neither."""
    seen: dict = {}

    def fake_load(model_path, root_arg=None, *a, **k):
        seen["load"] = (model_path, root_arg)
        return object(), "0123456789abcdef" * 4

    def fake_one(ref, root_arg, net, dev, model_path, sha, dest):
        seen["one"] = {"dev": dev, "sha": sha, "model_path": model_path}
        return {"ref": ref, "wrote": True}

    monkeypatch.setattr(zn, "load_segmenter", fake_load)
    monkeypatch.setattr(F, "_predict_one", fake_one)
    return seen


def test_the_segmenter_is_asked_for_the_root_and_not_the_device(root, calls):
    """The `root` slot must hold the repo root.

    Handed `"auto"`, `load_segmenter` does `p = root / p` and looks for the
    weights under `auto/models/bogoras-fig/…`, then raises `FileNotFoundError`
    advising `harness zones assemble` — naming neither the real path nor the
    real fault.
    """
    F.predict(["1-021"], root, device="cpu")
    model_path, root_arg = calls["load"]
    assert root_arg == root, f"load_segmenter got {root_arg!r} in the root slot"
    assert model_path == F.DEFAULT_MODEL


def test_the_device_reaches_the_page_and_the_sha_does_not(root, calls):
    """`dev` and `sha` are two returns of one call and were crossed.

    Asserted as a pair rather than singly: the bug set `dev` to the sha, so a
    test that only checked `sha` was a sha would have passed throughout.
    """
    F.predict(["1-021"], root, device="cpu")
    assert calls["one"]["dev"] == "cpu"
    assert calls["one"]["sha"] == "0123456789abcdef" * 4
    assert calls["one"]["dev"] != calls["one"]["sha"]


def test_auto_is_resolved_before_it_reaches_the_page(root, calls, monkeypatch):
    """`zones.predict_dp` resolves `auto`; this never did.

    Fixing the argument order alone would have left `"auto"` travelling into
    `blla.segment`, which wants a torch device. Pinned to `cpu` here by claiming
    no CUDA, so the assertion holds on any machine.
    """
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    F.predict(["1-021"], root, device="auto")
    assert calls["one"]["dev"] == "cpu"


def test_a_page_with_no_raster_never_loads_the_model(root, calls):
    """The skip comes first, so a bad ref costs no weights load."""
    out = F.predict(["1-099"], root, device="cpu")
    assert out == [{"ref": "1-099", "wrote": False, "note": "no raster"}]
    assert "load" not in calls
