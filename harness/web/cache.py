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

**A build is the exception, and it is scoped to exactly the build.** The digest
buys a server whose stores are edited under it; a static build is one snapshot by
contract — an edit landing mid-crawl yields a site half of one state and half of
the other whatever the cache does — so there the per-request re-read is pure
cost. Measured, it was most of the build: ~80% of a full page re-read and hashed
~5,000 files, and most of the rest re-globbed and re-sorted the same directories.
`frozen()` holds the snapshot: inside it each file is digested once, each stamp
folded once, and each `@listing` globbed once. Outside it nothing changes, and on
exit it forgets everything, so the next build — or the next test — reads afresh.
"""
from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
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


#: The snapshot's memo while `frozen()` holds one, else None.
_snapshot: dict | None = None


@contextmanager
def frozen() -> Iterator[None]:
    """Treat the stores as unchanging until the block exits. Re-entrant: an
    inner block joins the outer snapshot rather than starting a second one."""
    global _snapshot
    outer = _snapshot is not None
    if not outer:
        _snapshot = {}
    try:
        yield
    finally:
        if not outer:
            _snapshot = None


def _memo(key, compute: Callable[[], Any]) -> Any:
    if _snapshot is None:
        return compute()
    try:
        return _snapshot[key]
    except KeyError:
        out = _snapshot[key] = compute()
        return out


def listing(fn: Callable[..., list]) -> Callable[..., list]:
    """A file-set listing, globbed once per snapshot and every call outside one.
    Returns a copy, since callers concatenate onto what they are given."""

    @functools.wraps(fn)
    def wrapper(*args):
        return list(_memo((fn, *args), lambda: fn(*args)))
    return wrapper


def digest(data: bytes) -> bytes:
    return hashlib.blake2b(data, digest_size=_DIGEST).digest()


def file_digest(path: Path) -> bytes | None:
    """One file's digest, or None for a file that is not there."""
    def read() -> bytes | None:
        try:
            return digest(Path(path).read_bytes())
        except OSError:
            return None
    return _memo(("file", str(path)), read)


def stamp(paths: Iterable[Path]) -> bytes:
    """One digest over a file set — the key for a *directory* read.

    Folds each file's path and contents in, so a rename, an edit, a deletion and
    an added file are all a different stamp. The paths must arrive in a stable
    order (sort them) or the same directory hashes differently per call.

    A file that vanishes between the glob and the read is folded in as absent
    rather than raising: a half-written store is a state these tools pass
    through constantly, and the next call will see whatever it settles into.
    """
    paths = tuple(str(p) for p in paths)

    def fold() -> bytes:
        h = hashlib.blake2b(digest_size=_DIGEST)
        for p in paths:
            h.update(p.encode("utf-8"))
            h.update(file_digest(Path(p)) or b"\0missing")
        return h.digest()
    return _memo(("stamp", paths), fold)


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
        key = file_digest(p)
        if key is None:
            return self.fn(p)
        return self._cached(str(p), key)

    def cache_clear(self) -> None:
        self._cached.cache_clear()

    def cache_info(self):
        return self._cached.cache_info()
