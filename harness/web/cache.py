"""Store reads memoised on the file's own contents.

**The key is what makes this safe, and it is the whole design.** These are
editorial tools: the stores are edited underneath a running server, by the very
person looking at the page. A cache that could return a stale entry would show a
reading view confidently displaying an entity the file no longer contains —
plausible, current-looking, and wrong, with nothing anywhere to signal it. That
is the failure this project is arranged against, and a cache is an unusually
good way to introduce it.

**Why not mtime.** `geo.py` keys its one index on `st_mtime`, and the obvious
generalisation was `st_mtime_ns` — finer, therefore safe. It is not. Measured on
this repo's filesystem (ext4), **190 of 200 immediate rewrites produced an
identical `st_mtime_ns`**: the kernel stamps inodes from a coarse clock with
about 1 ms of granularity, and the nanosecond field carries that granularity
faithfully rather than fixing it. A write and a re-read inside one request —
which `_guarded` does, writing the entity store and immediately re-checking it —
falls inside that window essentially always. So an mtime key does not narrow the
staleness window here, it merely makes it hard to reproduce, which is worse.

**So the key is a digest of the bytes.** That has no window at all: the same
contents give the same answer, and any difference is a different key, whatever
the clock did. It costs a read and a hash per call, and the measurement that
makes it affordable is that **parsing a TEI page costs about 22× reading and
hashing it** — parsing is what is being saved, and it is the expensive half by
more than an order of magnitude. A cache that has to be reasoned about before it
can be trusted is not worth the speed; this one can be checked in a sentence.

Nothing here caches a write path, and nothing caches across processes. A cache
that outlived the server would be a second store, and this project has opinions
about stores that can disagree.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

# Big enough that a corpus sweep does not evict its own working set — `search`
# renders every collated page — and small enough to stay a cache rather than a
# leak. 730 pages is the whole book.
MAXSIZE = 1024

# Not for integrity, only for identity: blake2b is fast and the inputs are this
# repo's own files. Digest truncated because a collision would need two of our
# own store files to collide in 128 bits.
_DIGEST = 16


def digest(data: bytes) -> bytes:
    return hashlib.blake2b(data, digest_size=_DIGEST).digest()


def stamp(paths: Iterable[Path]) -> bytes:
    """One digest over a file set — the key for a *directory* read.

    Folds each file's path and contents in, so a rename, an edit, a deletion and
    an added file are all a different stamp. The paths must arrive in a stable
    order (sort them) or the same directory hashes differently per call.

    A file that vanishes between the glob and the read is folded in as absent
    rather than raising: a half-written store is a state these tools pass
    through constantly, and the next call will see whatever it settles into.
    """
    h = hashlib.blake2b(digest_size=_DIGEST)
    for p in paths:
        h.update(str(p).encode("utf-8"))
        try:
            h.update(p.read_bytes())
        except OSError:
            h.update(b"\0missing")
    return h.digest()


class by_file:  # noqa: N801 — used as a decorator, so it reads as one
    """Memoise a one-file reader on that file's contents.

    A missing file is not cached at all — absence is the ordinary state of a
    derived tree here (`scans/` is gitignored, so a fresh clone has none of it),
    and caching it would outlive the build that fixes it.

    A class rather than a closure with attributes bolted on, so `cache_clear`
    and `cache_info` are declared members a type checker can see.
    """

    def __init__(self, fn: Callable[[Path], Any]) -> None:
        self.fn = fn
        self._cached = lru_cache(maxsize=MAXSIZE)(
            lambda path, _key: fn(Path(path)))
        self.__doc__ = fn.__doc__
        self.__name__ = getattr(fn, "__name__", "by_file")

    def __call__(self, path: Path) -> Any:
        p = Path(path)
        try:
            key = digest(p.read_bytes())
        except OSError:
            return self.fn(p)
        return self._cached(str(p), key)

    def cache_clear(self) -> None:
        self._cached.cache_clear()

    def cache_info(self):
        return self._cached.cache_info()
