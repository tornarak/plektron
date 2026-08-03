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
wants a different tool and should say so rather than growing this one.

**What this is for is a raster decode, and the cheap sweeps were measured and left
alone.** The rule that came out of benching them is worth stating so the next
caller does not re-derive it: a page has to be doing something that *releases* the
GIL before a thread pool can help.

  zones blot --all         114.4s -> 15.2s   PNG decode + paint + encode
  zones check --all --ink  100.5s -> 29.4s   PNG decode, then measuring
  zones paragraphs --all    87.9s -> 21.8s   PNG decode, then measuring
  corpus normalize --all     0.84s -> 0.93s  **slower** — pure-Python scanning
  832 x read_zones           0.098s -> 0.096s  noise — 0.12 ms of lxml per page

`corpus normalize` is the instructive one. It walks 449 files and is the largest
of the cheap sweeps, so it was the best candidate among them — and pooling it made
it *slower*, because its per-file work is regex and string scanning that holds the
GIL from start to finish. Threads there buy nothing and charge contention for it.
The lxml verbs (`zones diff`, `ocr lines`) fail for the opposite reason: lxml does
drop the GIL, but a page parses in 0.12 ms, which is under the cost of handing it
to another thread.

So none of them carry `--jobs`, and that is a measurement rather than a hunch. A
verb whose page cost is milliseconds of Python does not want this module; one that
opens a raster does.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

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


def pmap(fn: Callable, items: Iterable, jobs: int | None = None) -> list:
    """`[fn(x) for x in items]`, concurrently, in order.

    Raises whatever `fn` raised, with the item that raised it added as a note —
    the type is preserved deliberately, because `cli.main` catches four concrete
    types to turn them into a one-line `ERROR:` instead of a traceback, and
    wrapping would route every failure inside a sweep past that.
    """
    items = list(items)
    n = workers(jobs)
    if n == 1 or len(items) < 2:
        return [_call(fn, x) for x in items]
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(lambda x: _call(fn, x), items))


def _call(fn: Callable, item):
    try:
        return fn(item)
    except Exception as exc:
        # A sweep names one page among hundreds, and "no such file" without it
        # sends the reader back through the whole store to find which.
        exc.add_note(f"while processing {item!r}")
        raise
