"""`figures._outside` — the grid sampler behind `fig_ink`'s `unaccounted` share.

It was a nested `range` over the rect testing every sample point against every
box. At 300 dpi a photograph rect is ~187,000 sample points, and `corpus figures`
spent **33 of its 34 seconds** inside this one function across 76.7 million
evaluations of the membership test — a cost no output mentions, since the number
it produces is reported and never gated on.

The rewrite marks the *same* grid by slice assignment instead of walking it, so
the work is proportional to the number of boxes rather than to the rect's area.
"Same answer, faster" is the whole claim, and it is invisible by construction:
these hold the old implementation against the new one directly, on randomised
geometry and on the edge cases the old bounds made easy to get wrong.

`hold-the-method-constant`: the reference below is the original code, transcribed
unchanged. If it is ever "tidied" to agree with the implementation it checks, it
stops being a witness.
"""
from __future__ import annotations

import random

import pytest

from harness.figures import _outside


def reference(rect, boxes, pad, step=4):
    """The original nested-range sampler, verbatim. Not to be tidied."""
    x0, y0, x1, y1 = rect
    grown = [(b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad) for b in boxes]
    tot = miss = 0
    for y in range(y0, max(y0 + 1, y1), step):
        for x in range(x0, max(x0 + 1, x1), step):
            tot += 1
            if not any(g[0] <= x <= g[2] and g[1] <= y <= g[3] for g in grown):
                miss += 1
    return (miss / tot) if tot else 0.0


class TestItAgreesWithTheOldSampler:
    @pytest.mark.parametrize("seed", range(40))
    def test_randomised_geometry(self, seed):
        """Boxes that overlap freely, sit proud, miss entirely, or nest — the
        corpus has all four, and the union is why this samples rather than
        computes."""
        rnd = random.Random(seed)
        x0, y0 = rnd.randint(0, 400), rnd.randint(0, 400)
        rect = [x0, y0, x0 + rnd.randint(1, 300), y0 + rnd.randint(1, 300)]
        boxes = []
        for _ in range(rnd.randint(0, 6)):
            bx, by = rnd.randint(0, 500), rnd.randint(0, 500)
            boxes.append((bx, by, bx + rnd.randint(1, 200), by + rnd.randint(1, 200)))
        pad = rnd.choice([0, 1, 5, 20])
        assert _outside(rect, boxes, pad) == pytest.approx(
            reference(rect, boxes, pad)), (rect, boxes, pad)

    @pytest.mark.parametrize("step", [1, 2, 3, 4, 7, 16])
    def test_every_step_agrees(self, step):
        rect = [10, 20, 137, 211]
        boxes = [(0, 0, 60, 60), (100, 100, 300, 300), (55, 90, 70, 105)]
        assert _outside(rect, boxes, 3, step) == pytest.approx(
            reference(rect, boxes, 3, step))


class TestTheEdgesTheBoundsMadeEasyToGetWrong:
    def test_no_boxes_is_entirely_outside(self):
        assert _outside([0, 0, 40, 40], [], 0) == 1.0
        assert _outside([0, 0, 40, 40], [], 0) == reference([0, 0, 40, 40], [], 0)

    def test_one_box_covering_everything_is_zero(self):
        rect, boxes = [10, 10, 50, 50], [(0, 0, 100, 100)]
        assert _outside(rect, boxes, 0) == 0.0

    def test_a_degenerate_rect_still_samples_one_point(self):
        """`max(x0 + 1, x1)` in the original guarantees a sample even when the
        rect has no width, so the result is 0.0 or 1.0 and never a ZeroDivision."""
        for rect in ([5, 5, 5, 5], [5, 5, 4, 4], [5, 5, 5, 40], [5, 5, 40, 5]):
            assert _outside(rect, [], 0) == reference(rect, [], 0) == 1.0
            assert _outside(rect, [(0, 0, 100, 100)], 0) == 0.0

    def test_the_bounds_are_closed_on_both_edges(self):
        """`g0 <= x <= g1`, inclusive. A box touching the rect's first sample
        exactly must cover it — `searchsorted` sidedness is the one place the
        rewrite could have shifted this by a pixel."""
        rect = [0, 0, 1, 1]           # samples exactly (0, 0)
        assert _outside(rect, [(0, 0, 0, 0)], 0) == 0.0
        assert _outside(rect, [(1, 1, 2, 2)], 0) == 1.0
        # …and the pad is what closes a one-pixel gap.
        assert _outside(rect, [(1, 1, 2, 2)], 1) == 0.0

    def test_a_box_entirely_left_of_the_grid_covers_nothing(self):
        rect = [100, 100, 200, 200]
        assert _outside(rect, [(0, 0, 50, 50)], 0) == 1.0
        assert _outside(rect, [(0, 0, 50, 50)], 0) == \
            reference(rect, [(0, 0, 50, 50)], 0)


class TestItIsActuallyFasterOnCorpusScaleGeometry:
    def test_a_realistic_rect_does_not_walk_its_area(self):
        """Not a timing assertion — those are machine-dependent and flaky. This
        pins the shape instead: a rect two orders of magnitude larger in area
        costs the same handful of slice assignments, so the answer arrives at
        all. Under the old sampler this call was ~1.9 million membership tests.
        """
        rect = [0, 0, 2400, 3200]
        boxes = [(100, 100, 900, 1200), (1200, 1500, 2300, 3100)]
        got = _outside(rect, boxes, 8)
        assert 0.0 < got < 1.0
        assert got == pytest.approx(reference(rect, boxes, 8))
