"""The store cache, and the one way it could make things worse.

Caching a store a human is editing underneath the running server is this
project's characteristic hazard in a new shape: an answer that is plausible,
current-looking, and wrong, with nothing anywhere to signal it. So these test
the *key* — that a stale entry is unreturnable rather than merely unlikely — and
not the hit rate, which is an optimisation and would still be correct at zero.

**The first version of this cache keyed on `st_mtime_ns` and these tests broke
it**, which is the reason they are written this way. Measured here: 190 of 200
immediate rewrites produce an identical `st_mtime_ns`, because inode timestamps
come from a coarse ~1 ms clock and the nanosecond field reports that granularity
rather than removing it. A finer-looking timestamp did not narrow the staleness
window, it only made it hard to reproduce.
"""
from __future__ import annotations

import os

from harness.web import cache


def test_a_second_read_of_an_unchanged_file_is_not_a_second_parse(tmp_path):
    calls = []

    @cache.by_file
    def read(p):
        calls.append(p)
        return p.read_text()

    f = tmp_path / "a.md"
    f.write_text("one")
    assert read(f) == "one"
    assert read(f) == "one"
    assert len(calls) == 1


def test_an_edit_under_a_running_server_is_picked_up(tmp_path):
    """The failure the cache key exists to prevent: the reading view showing an
    entity the file no longer contains, with no error signal anywhere."""

    @cache.by_file
    def read(p):
        return p.read_text()

    f = tmp_path / "a.md"
    f.write_text("one")
    assert read(f) == "one"
    f.write_text("two")
    assert read(f) == "two"


def test_a_rewrite_inside_one_clock_tick_is_seen(tmp_path):
    """The case that killed the mtime key, pinned so it cannot come back.

    Both writes land in the same coarse clock tick, so the inode's timestamp is
    byte-identical across them — on this filesystem that is the *usual* outcome,
    not a rare one. `_guarded` writes the entity store and re-checks it inside a
    single request, which is exactly this window.
    """

    @cache.by_file
    def read(p):
        return p.read_text()

    f = tmp_path / "a.md"
    f.write_text("one")
    assert read(f) == "one"
    before = f.stat().st_mtime_ns
    f.write_text("two")
    # Force the collision rather than hoping for it: the point is that the cache
    # must not depend on the timestamp having moved.
    os.utime(f, ns=(before, before))
    assert f.stat().st_mtime_ns == before
    assert read(f) == "two"


def test_a_same_length_edit_is_seen(tmp_path):
    """Size is not a witness either — the near-miss fix for the mtime key was
    `(mtime, size)`, and this is what it would still have missed."""

    @cache.by_file
    def read(p):
        return p.read_text()

    f = tmp_path / "a.md"
    f.write_text("aaa")
    assert read(f) == "aaa"
    before = f.stat().st_mtime_ns
    f.write_text("bbb")
    os.utime(f, ns=(before, before))
    assert read(f) == "bbb"


def test_a_missing_file_is_not_cached(tmp_path):
    """Absence is the ordinary state of a derived tree here — `scans/` is
    gitignored, so a fresh clone has none of it. Caching the absence would
    outlive the build that fixes it."""
    seen = []

    @cache.by_file
    def read(p):
        seen.append(p)
        return p.read_text() if p.exists() else None

    f = tmp_path / "later.png"
    assert read(f) is None
    assert read(f) is None
    assert len(seen) == 2, "the absence was cached"
    f.write_text("here")
    assert read(f) == "here"


def test_two_files_do_not_share_an_entry(tmp_path):
    """The path is part of the key as well as the contents, so two files that
    happen to hold the same bytes stay two answers."""
    calls = []

    @cache.by_file
    def read(p):
        calls.append(p.name)
        return p.name

    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text("same bytes")
    assert read(tmp_path / "a.md") == "a.md"
    assert read(tmp_path / "b.md") == "b.md"
    assert calls == ["a.md", "b.md"]


def test_the_stamp_notices_a_deletion(tmp_path):
    """A directory key has to see a file removed, not only one edited."""
    for name in "abc":
        (tmp_path / f"{name}.md").write_text(name)
    before = cache.stamp(sorted(tmp_path.glob("*.md")))
    (tmp_path / "c.md").unlink()
    assert cache.stamp(sorted(tmp_path.glob("*.md"))) != before


def test_the_stamp_notices_a_rename(tmp_path):
    """An identity here is `class:slug` and the slug is the filename, so a rename
    is a different store even with every byte unchanged."""
    (tmp_path / "a.md").write_text("body")
    before = cache.stamp(sorted(tmp_path.glob("*.md")))
    (tmp_path / "a.md").rename(tmp_path / "b.md")
    assert cache.stamp(sorted(tmp_path.glob("*.md"))) != before


def test_the_stamp_is_stable_across_calls(tmp_path):
    for name in "abc":
        (tmp_path / f"{name}.md").write_text(name)
    files = sorted(tmp_path.glob("*.md"))
    assert cache.stamp(files) == cache.stamp(files)


def test_a_file_that_vanishes_mid_walk_is_folded_in_not_raised(tmp_path):
    """A half-written store is a state these tools pass through constantly."""
    gone = tmp_path / "gone.md"
    assert cache.stamp([gone]) == cache.stamp([gone])
    gone.write_text("back")
    assert cache.stamp([gone]) != cache.stamp([tmp_path / "never.md"])
