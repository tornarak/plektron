"""`pmap`: order, the serial arm, and what happens to an exception.

The sweeps it serves are pure maps over pages — decode a raster, measure it, fold
the result — so the only properties that matter are that the answers come back in
the order they were asked for, that `jobs=1` is a real control arm rather than a
pool of one, and that a failure still says which page it was.
"""
from __future__ import annotations

import threading

import pytest

from harness.parallel import MAX_WORKERS, pmap, workers


def test_results_come_back_in_input_order():
    """Not completion order. Every caller pools into one ref-keyed table or
    accumulates rows in scan order, so finishing order would shuffle the report by
    which page happened to decode first."""
    def slow_for_the_first(x):
        # The earliest item finishes last, so completion order is the reverse.
        threading.Event().wait(0.02 if x == 0 else 0)
        return x
    assert pmap(slow_for_the_first, range(8), jobs=4) == list(range(8))


def test_it_actually_runs_on_several_threads():
    seen: set[int] = set()
    lock = threading.Lock()

    def note(x):
        threading.Event().wait(0.01)
        with lock:
            seen.add(threading.get_ident())
        return x

    pmap(note, range(8), jobs=4)
    assert len(seen) > 1


def test_jobs_1_builds_no_pool():
    """The control arm has to be the calling thread, not a pool of one.

    The claim these changes rest on is that parallelism moves wall clock and
    nothing else, and that is only checkable by running both sides and diffing. A
    serial path that still went through an executor would compare the executor
    with itself — the shape this project keeps meeting and keeps refusing.
    """
    main = threading.get_ident()
    assert pmap(lambda _: threading.get_ident(), range(4), jobs=1) == [main] * 4


def test_one_item_needs_no_pool_either():
    main = threading.get_ident()
    assert pmap(lambda _: threading.get_ident(), ["1-048"]) == [main]


def test_an_empty_work_list_is_not_an_error():
    assert pmap(lambda _: 1 / 0, [], jobs=4) == []


@pytest.mark.parametrize("jobs", [1, 4])
def test_a_failure_names_the_item_and_keeps_its_type(jobs):
    """The type is preserved on purpose: `cli.main` catches four concrete
    exception types to turn them into a one-line `ERROR:` rather than a
    traceback, so wrapping would route every in-sweep failure past that."""
    def boom(ref):
        if ref == "1-049":
            raise FileNotFoundError("no raster")
        return ref

    with pytest.raises(FileNotFoundError) as caught:
        pmap(boom, ["1-048", "1-049", "1-050"], jobs=jobs)
    assert "while processing '1-049'" in "; ".join(caught.value.__notes__)


def test_worker_count_honours_affinity_and_the_cap():
    assert workers(3) == 3
    assert 1 <= workers() <= MAX_WORKERS


def test_zero_jobs_is_a_usage_error():
    with pytest.raises(ValueError, match="at least 1"):
        workers(0)
