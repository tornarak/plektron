"""A sweep's workers must not write to the terminal the progress bar is drawing on.

`ocr predict --all` is the longest-running command in the harness — ~689 pages at
several seconds each — so the progress bar is the only signal there is that it is
alive. It was useless: the count appeared frozen while `mz/ocr/` filled normally.

The bar was not at fault. `_predict_pool` runs `spawn`ed children, which inherit
the parent's fd 2, and kraken warns once per recognition call that the pinned
`blla.mlmodel` predates its new polygon extractor. Rich redirects `stderr`, but
only Python-level writes in the *parent*, so those child writes land between
frames; the cursor is then not where rich believes it is and its erase-and-redraw
strands the frame being watched. Both symptoms — scrambled output, and a number
that never moves — are one cause.

So the filter goes in `_worker_init`, which is the one place it can go: the parent
cannot intercept another process's fd, and the serial path does not need it
(there the warning is raised in-process and rich prints it tidily above the bar).

These tests avoid loading either model — that is minutes of CPU and a GPU context
per call, and the thing under test is one line that must run *before* any of it.
"""

from __future__ import annotations

import warnings

import pytest

from harness import recognize
from harness.recognize import POLYGON_WARNING, _worker_init


@pytest.fixture
def bare_worker(monkeypatch, tmp_path):
    """`_worker_init` with the model loads stubbed out, filters restored after.

    The loaders are the whole cost of the real thing and none of the behaviour
    being checked, so they are replaced rather than paid for. `warnings.filters`
    is process-global, so the fixture puts it back — a test that installs a filter
    and leaves it there silences whatever runs next.
    """
    monkeypatch.setattr(recognize.Z, "load_segmenter", lambda *a, **k: (None, "seg"))
    monkeypatch.setattr(recognize, "load_recognizer", lambda *a, **k: (None, "rec"))
    monkeypatch.setattr(recognize, "_resolve_device", lambda d: "cpu")
    monkeypatch.chdir(tmp_path)
    saved = warnings.filters[:]
    yield tmp_path
    warnings.filters[:] = saved


def _installed():
    """The filters `_worker_init` added, as `(action, pattern, category)`.

    **Asserted against the registry rather than by raising the warning**, because
    the obvious functional test is a tautology: `catch_warnings(record=True)`
    resets `warnings.filters`, so a test that then re-adds the filter and observes
    silence proves only that `filterwarnings` works. It passes with `_worker_init`
    doing nothing at all.
    """
    return [(f[0], f[1].pattern if f[1] else None, f[2]) for f in warnings.filters]


def test_the_polygon_warning_is_silenced_in_a_worker(bare_worker):
    """The one that floods: once per recognition call, 689 times a sweep."""
    before = _installed()
    _worker_init(bare_worker, "seg.mlmodel", "rec.mlmodel", "cpu")
    added = [f for f in _installed() if f not in before]
    assert ("ignore", POLYGON_WARNING, Warning) in added, added


def test_it_is_filtered_by_message_not_by_category(bare_worker):
    """A blanket filter would silence the next warning nobody has seen yet, in a
    process whose output nothing else reads. The channel stays open."""
    before = _installed()
    _worker_init(bare_worker, "seg.mlmodel", "rec.mlmodel", "cpu")
    added = [f for f in _installed() if f not in before]
    assert added, "installed nothing"
    # Every filter it adds names a message. One that named only a category would
    # match anything kraken raises from anywhere.
    assert all(pattern for _action, pattern, _cat in added), added


def test_the_guards_are_installed_before_the_models_load(monkeypatch, tmp_path):
    """Ordering is the whole point: kraken and torch both talk during a load, so a
    write raised *while* the recognizer comes up is as much a write to the shared
    fd as one raised on page 400."""
    order: list[str] = []
    monkeypatch.setattr(recognize, "_capture_stderr",
                        lambda d: order.append("capture"))
    monkeypatch.setattr(warnings, "filterwarnings",
                        lambda *a, **k: order.append("filter"))
    monkeypatch.setattr(recognize.Z, "load_segmenter",
                        lambda *a, **k: (order.append("seg"), (None, "s"))[1])
    monkeypatch.setattr(recognize, "load_recognizer",
                        lambda *a, **k: (order.append("rec"), (None, "r"))[1])
    monkeypatch.setattr(recognize, "_resolve_device", lambda d: "cpu")
    monkeypatch.chdir(tmp_path)

    _worker_init(tmp_path, "seg.mlmodel", "rec.mlmodel", "cpu", tmp_path)
    assert order == ["capture", "filter", "seg", "rec"]


# --- the capture itself ----------------------------------------------------

def test_capture_redirects_fd_2_not_the_python_object(monkeypatch, tmp_path):
    """`dup2`, because scipy, shapely and torch all have C in them.

    Rebinding `sys.stderr` leaves fd 2 pointing at the terminal, so a C extension
    writing to the file descriptor would still land between two frames of the bar
    — which is the entire failure being fixed.
    """
    import os

    calls = []
    # Only `dup2` is stubbed — the real `open`/`close` still run, so the fd this
    # opens is closed rather than leaked into the rest of the suite. Patching the
    # `os` module itself is what reaches the function's own `import os`.
    monkeypatch.setattr(os, "dup2", lambda a, b: calls.append((a, b)))
    recognize._capture_stderr(tmp_path)
    assert len(calls) == 1
    assert calls[0][1] == 2, "must replace fd 2 itself"
    assert (tmp_path / f"worker-{os.getpid()}.log").exists(), \
        "named per process, so four workers cannot interleave into one file"


def test_worker_output_reports_what_a_worker_wrote(tmp_path):
    (tmp_path / "worker-1.log").write_text("boom\nsecond line\n", encoding="utf-8")
    rep = recognize.worker_output(tmp_path)
    assert rep["stderr_lines"] == 2
    assert rep["stderr_log"] == str(tmp_path)
    assert tmp_path.exists(), "a directory with something in it is kept"


def test_a_quiet_run_reports_nothing_and_leaves_nothing(tmp_path):
    """An empty capture is removed, which is what makes a non-empty one worth
    reading — and it keeps the summary honest on the ordinary run."""
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "worker-1.log").write_text("", encoding="utf-8")
    (logs / "worker-2.log").write_text("\n  \n", encoding="utf-8")
    assert recognize.worker_output(logs) == {"stderr_lines": 0,
                                             "stderr_log": ""}
    assert not logs.exists()


def test_worker_output_survives_a_directory_that_never_existed(tmp_path):
    """The serial path never makes one, and a sweep that refused every page
    closes its pool without a worker having run."""
    assert recognize.worker_output(tmp_path / "gone")["stderr_lines"] == 0


def test_the_message_is_the_one_kraken_actually_raises():
    """Pinned against the text seen in a real run, since a filter that matches
    nothing fails silently and looks exactly like a filter that works."""
    observed = ("Enforcing use of the new polygon extractor for models trained "
                "with old version. Accuracy may be affected.")
    assert observed.startswith(POLYGON_WARNING)
