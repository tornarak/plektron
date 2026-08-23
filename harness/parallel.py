"""One parallel map, for the sweeps whose per-page work is a raster decode.

**Threads, not processes**, and that is a measurement rather than a preference.
What the raster sweeps actually cost is PNG inflate — `lines.ink_mask` is ~0.16 s
of zlib against ~0.02 s for all the measuring put together — and zlib, PIL and
numpy all release the GIL for the duration. A process pool would buy the same
concurrency and charge an interpreter plus a fresh `lxml`/`numpy` import per
worker, which is the wrong trade on the machines this has to run on: 4-core i5s,
small VPSes and university time-shares, where N × the resident set is the binding
constraint rather than N × the CPU.

**Ordered results.** Every caller pools its output into one table keyed by ref, or
accumulates rows in scan order, so a map that returned completions in finishing
order would reorder the report by which page happened to decode first — output
that changes run to run for reasons that are about nothing.

**`jobs=1` builds no pool at all.** It is not a debug switch: it is the control
arm. This project's habit is to distrust a comparison whose two sides may be one
thing, and the only way to say that parallelism changed nothing but wall clock is
to run both and diff. A serial path that still went through an executor would be
testing the executor against itself.

Nothing here is a work queue, a scheduler or a progress bar. A sweep is a pure map
over pages and a fold afterwards; the moment a caller needs more than that, it
wants a different tool and should say so rather than growing this one. `pmap`'s
`tick` is the one concession and stays inside that line: it *reports* completions
to a callable the caller supplies, and this module never learns what a terminal
is or imports anything to draw on one.

**What this is for is a raster decode, and the cheap sweeps were measured and left
alone.** The rule that came out of benching them is worth stating so the next
caller does not re-derive it: a page has to be doing something that *releases* the
GIL before a thread pool can help.

  zones blot --all         114.4s -> 15.2s   PNG decode + paint + encode
  zones check --all --ink  100.5s -> 25.7s   PNG decode, then measuring
  zones paragraphs --all    87.9s -> 21.8s   PNG decode, then measuring
  corpus normalize          0.30s -> 0.31s   **slower** — pure-Python scanning
  832 x read_zones         0.098s -> 0.096s  noise — 0.12 ms of lxml per page

`corpus normalize` is the instructive one. It walks 449 files and is the largest
of the cheap sweeps, so it was the best candidate among them — and pooling it made
it *slower*, because its per-file work is regex and string scanning that holds the
GIL from start to finish. Threads there buy nothing and charge contention for it.
(Re-measured after that verb was optimized 2.2x: still 0.97x, and the ratio barely
moved, because making GIL-bound work faster leaves it GIL-bound.) The lxml verbs
(`zones diff`, `ocr lines`) fail for the opposite reason: lxml does drop the GIL,
but a page parses in 0.12 ms, under the cost of handing it to another thread.

So none of them carry `--jobs`, and that is a measurement rather than a hunch. A
verb whose page cost is milliseconds of Python does not want this module; one that
opens a raster does.

**And a pool is the second thing to reach for, not the first.** Both sweeps that
looked like pool candidates turned out to have a bigger win sitting in the hot
path: `corpus normalize` was 57% one dict lookup per character, and
`zones check --ink` re-read all three split lists twice a page. Profiling first
would have found those with no concurrency at all, and the second one was also
what capped this module's speedup on that verb — GIL-bound work is both the thing
a thread pool cannot help and the thing most worth deleting. Measure where the
time goes before deciding it needs more cores.

One caveat on that profiling, learned here: cProfile's per-call overhead badly
distorts call-heavy code. It put `load_splits` at 19% of `zones check` where the
wall-clock truth was ~3%. Confirm a profile's finding against a stopwatch before
acting on its magnitude.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# The default cap, above what a 4-core machine offers and below what this
# repository's 16-core one does.
#
# Past roughly this many threads the GIL-bound fraction of a page — parsing its
# ALTO, walking its zones — stops overlapping and starts queueing, so the curve
# flattens while the memory does not: each worker holds a decoded ~11 M-pixel
# boolean mask while it measures. A number rather than a formula because it is a
# ceiling on diminishing returns, not a property of the work; the bench that
# accompanies each verb's `--jobs` is what may move it.
MAX_WORKERS = 8


def workers(jobs: int | None = None) -> int:
    """How many threads a sweep will actually use.

    `os.process_cpu_count()` rather than `os.cpu_count()`: it honours CPU affinity,
    so a run confined to two cores by `taskset` or by a scheduler on a shared
    machine asks for two threads instead of sixteen. That is the ordinary case on
    a time-share, not an exotic one.
    """
    if jobs is not None:
        if jobs < 1:
            raise ValueError(f"--jobs must be at least 1, got {jobs}")
        return jobs
    return max(1, min(os.process_cpu_count() or 1, MAX_WORKERS))


def pmap(fn: Callable, items: Iterable, jobs: int | None = None,
         tick: Callable | None = None) -> list:
    """`[fn(x) for x in items]`, concurrently, in order.

    Raises whatever `fn` raised, with the item that raised it added as a note —
    the type is preserved deliberately, because `cli.main` catches four concrete
    types to turn them into a one-line `ERROR:` instead of a traceback, and
    wrapping would route every failure inside a sweep past that.

    **`tick(item, done, total)` is called once per completion, from the calling
    thread.** It is how a caller draws a progress bar without this module knowing
    what one is — the same shape as the serializer, which `cli` supplies rather
    than `emit` choosing. A counter inside `_call` would have put the drawing on N
    workers and left the caller blocked in `pool.map` doing nothing, which is
    display work on the critical path and a shared object touched concurrently to
    do it. Futures already carry a completion channel; `as_completed` yields on it
    here.

    It takes the total because **`pmap` is the only party that knows it.** The
    sweeps compute their own work-list — `validate_corpus` decides which pages the
    store holds, `blot_all` splits links from rasters — so a caller sizing the bar
    up front would have to re-derive that list, which is a second implementation of
    the thing whose answer is the bar's denominator.

    Two invariants that channel costs a little care to keep:

    - **Order.** `as_completed` yields by completion, so results land in a
      pre-sized list by submission index. Every caller pools its output into one
      table or accumulates rows in scan order.
    - **Which failure is reported.** `pool.map` surfaced the exception of the
      earliest *item* that failed; completion order would surface the earliest to
      *finish*, so a sweep over 832 pages could name a different page than it used
      to. Exceptions are collected and re-raised in item order. Nothing is lost by
      waiting — `pool.map` did not cancel queued work either, `with` exiting
      through `shutdown(wait=True)` — so both forms run the sweep out regardless.
    """
    items = list(items)
    n = workers(jobs)
    total = len(items)
    if n == 1 or total < 2:
        out = []
        for done, x in enumerate(items, 1):
            out.append(_call(fn, x))
            if tick:
                tick(x, done, total)
        return out

    results: list = [None] * total
    errors: dict[int, BaseException] = {}
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = {pool.submit(_call, fn, x): i for i, x in enumerate(items)}
        for done, fut in enumerate(as_completed(futures), 1):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except BaseException as exc:      # noqa: BLE001 — re-raised below
                errors[i] = exc
            if tick:
                tick(items[i], done, total)
    if errors:
        raise errors[min(errors)]
    return results


def ptrack(items: Iterable, tick: Callable | None = None):
    """`items`, reporting each one to `tick` as the loop body finishes it.

    The serial counterpart of `pmap`'s `tick`, for the loops that are slow without
    being poolable: `ocr crops`/`sheets`/`zoom` write many PNGs a page, `ocr
    predict` is ~17 s a page over its own process pool, `zones predict` runs GPU
    inference in a plain `for`. None of them wants a thread pool and all of them
    sit silent for minutes.

    It ticks **after** the body rather than before, so the count is work finished
    rather than work started — the same thing `pmap` reports, and the difference
    between the two is a whole page on a sweep whose pages take seventeen seconds.
    """
    items = list(items)
    for i, x in enumerate(items, 1):
        yield x
        if tick:
            tick(x, i, len(items))


def _call(fn: Callable, item):
    try:
        return fn(item)
    except Exception as exc:
        # A sweep names one page among hundreds, and "no such file" without it
        # sends the reader back through the whole store to find which.
        exc.add_note(f"while processing {item!r}")
        raise


# ----------------------------------------------------- the GPU-worker machinery
#
# **Processes, where everything above is threads**, and the split is measured
# rather than stylistic. A neural sweep here is a brief forward pass and then a
# long stretch of single-core Python — scipy, shapely, and kraken's own tracing —
# so a thread pool gives back only the GIL-free share. `ocr predict` over 8 pages:
# 14.16 s/page serial, 7.89 with 4 threads (1.8x), 5.14 with 4 processes (2.8x,
# and that figure includes four model loads).
#
# It lives here rather than in `recognize`, where it was written, because
# `zones` needs it too and **`zones` cannot import `recognize`** — the graph runs
# `recognize` -> `zones` -> `context`, and this module sits under all of them.
# `recognize` keeps its own names bound to these, so the monkeypatch seams its
# tests use still point at the objects its `_worker_init` actually calls.

# What one worker costs on the card, measured: ~1.6 GB, nearly all of it CUDA and
# cuDNN context rather than weights (a recognizer's parameters are 22 MiB, and a
# segmenter touches the GPU only during its forward pass). Used to divide *free*
# VRAM at run time rather than to assert a worker count — the number that fits is
# a property of the card, and a constant here would be wrong on the next machine.
VRAM_PER_WORKER = 1.6 * 1024 ** 3


def gpu_workers(jobs: int | None, n_items: int) -> int:
    """How many processes a model sweep will use.

    **Capped by VRAM as well as cores.** Four is the ceiling by default rather
    than `MAX_WORKERS`: past that the pages queue behind one another on the card's
    context anyway, and each worker is ~1.6 GB that has to exist at once.

    A `jobs` a human typed wins outright, including one that will not fit. Naming
    it is the request, and the same rule holds for `--jobs 1`, which is the serial
    control arm every pooled sweep in this repo has to stay diffable against.
    """
    import os

    if jobs is not None:
        if jobs < 1:
            raise ValueError(f"--jobs must be at least 1, got {jobs}")
        return min(jobs, n_items)
    n = max(1, min(os.process_cpu_count() or 1, 4))
    try:
        import torch
        if torch.cuda.is_available():
            free, _total = torch.cuda.mem_get_info()
            n = max(1, min(n, int(free / VRAM_PER_WORKER)))
    except Exception:
        pass
    return max(1, min(n, n_items))


def capture_stderr(log_dir) -> None:
    """Point this process's fd 2 at a file of its own, and never at the terminal.

    **A worker must not be able to write where the parent is drawing.** Filtering
    a known warning by message cannot promise that — it names one warning, and the
    next library that clears its throat mid-sweep would break the display again
    with nobody able to say why. This closes the channel rather than the message:
    whatever the child emits, present or future, Python-level or from inside a C
    extension, lands in a file instead of between two frames of a progress bar.

    `dup2` and not `sys.stderr =`, for that last reason: rebinding the Python
    object leaves fd 2 pointing at the terminal, and scipy, shapely and torch all
    have C in them.

    Nothing is silenced. The parent reads these files when the pool closes and
    reports what they hold; an empty one is removed.
    """
    import os
    fd = os.open(Path(log_dir) / f"worker-{os.getpid()}.log",
                 os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd, 2)
    os.close(fd)


def worker_output(log_dir) -> dict:
    """What the workers wrote to their captured stderr, and where it is.

    Read after the pool closes rather than streamed: the whole point is that this
    text must not reach the terminal while the bar is live, and a sweep that ends
    is the moment it can be read safely.

    **Empty files are removed and an empty run reports nothing**, which is what
    makes a non-empty one worth looking at. The directory survives only if it has
    something in it, so the path in the report always names a file that exists.
    """
    log_dir = Path(log_dir)
    files = sorted(log_dir.glob("worker-*.log")) if log_dir.exists() else []
    kept, lines = [], 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            kept.append(f)
            lines += len(text.strip().splitlines())
        else:
            f.unlink()
    if not kept:
        if log_dir.exists():
            log_dir.rmdir()
        return {"stderr_lines": 0, "stderr_log": ""}
    return {"stderr_lines": lines, "stderr_log": str(log_dir)}
