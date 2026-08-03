"""`pmap`: order, the serial arm, and what happens to an exception.

The sweeps it serves are pure maps over pages — decode a raster, measure it, fold
the result — so the only properties that matter are that the answers come back in
the order they were asked for, that `jobs=1` is a real control arm rather than a
pool of one, and that a failure still says which page it was.
"""
from __future__ import annotations

import threading

import pytest

from harness.parallel import MAX_WORKERS, pmap, ptrack, workers


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


# ------------------------------------------------------ tick, and what it costs
#
# `pmap` moved from `pool.map` to `submit` + `as_completed` so it could report
# completions. That swap put two previously-free properties in the hands of this
# file: ordering (results now land by submission index rather than being yielded
# in order) and which failure surfaces (completion order is not item order).


@pytest.mark.parametrize("jobs", [1, 4])
def test_tick_fires_once_per_item_with_a_running_count(jobs):
    seen = []
    out = pmap(lambda x: x * 2, [1, 2, 3, 4], jobs,
               tick=lambda item, done, total: seen.append((item, done, total)))
    assert out == [2, 4, 6, 8]
    assert len(seen) == 4
    assert [d for _, d, _ in seen] == [1, 2, 3, 4], "count must be monotonic"
    assert {t for _, _, t in seen} == {4}
    assert sorted(i for i, _, _ in seen) == [1, 2, 3, 4], "every item reported"


def test_tick_is_called_on_the_calling_thread():
    """The whole reason for `as_completed` over a counter inside `_call`.

    A callback running on N workers would be display work on the critical path,
    with a shared object touched concurrently to do it — and rich's Progress
    would be that object.
    """
    here = threading.current_thread()
    threads = []
    pmap(lambda x: x, range(8), 4,
         tick=lambda *_: threads.append(threading.current_thread()))
    assert set(threads) == {here}


def test_results_stay_ordered_when_completion_order_is_reversed():
    """`as_completed` yields by completion, so ordering is now this module's
    problem rather than `pool.map`'s. Reversed sleeps make the last item finish
    first, which is the case a naive append would get wrong every time."""
    import time

    def slow(i):
        time.sleep((8 - i) * 0.01)
        return i

    assert pmap(slow, range(8), 4) == list(range(8))


def test_the_earliest_item_wins_not_the_earliest_failure():
    """`pool.map` surfaced the exception of the earliest *item* that failed.
    Completion order would surface the earliest to *finish*, so over 832 pages a
    sweep could start naming a different page than it used to — a change nothing
    else would report, in the message whose whole job is saying which page.

    Item 5 fails instantly; item 1 fails slowly. The report must say 1.
    """
    import time

    def fn(i):
        if i == 5:
            raise ValueError("fast")
        if i == 1:
            time.sleep(0.15)
            raise ValueError("slow")
        return i

    with pytest.raises(ValueError, match="slow"):
        pmap(fn, range(8), 4)


def test_no_tick_is_the_same_map_it_always_was():
    """The benched sweeps are diffed against `--jobs 1`; a bar that changed the
    answer would invalidate every one of those numbers."""
    assert pmap(str, range(20), 4) == pmap(str, range(20), 1) == \
        [str(i) for i in range(20)]


# ---------------------------------------------------------------------- ptrack


def test_ptrack_ticks_after_the_body_not_before():
    """The count is work *finished*, which is what `pmap` reports too. On `ocr
    predict` the difference is a whole page — seventeen seconds of claiming to
    have done something that has not started."""
    order = []
    for x in ptrack("ab", lambda item, done, total: order.append(("tick", item))):
        order.append(("body", x))
    assert order == [("body", "a"), ("tick", "a"),
                     ("body", "b"), ("tick", "b")]


def test_ptrack_without_a_tick_is_just_the_items():
    assert list(ptrack([1, 2, 3])) == [1, 2, 3]
