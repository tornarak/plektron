"""How a file lands on disk, in one place.

**Imports nothing from this package**, deliberately. Every store module needs
this and `context.py` — the obvious home for a shared primitive — sits in ten
of the nineteen mutual import cycles here, so anything that lives beside it gets
imported through a function body at each call site and the cycle grows. A module
with no package imports cannot join one.

The rule it exists to hold: **a write that replaces a whole file replaces it by
rename, and the temp carries the pid.** `zones._write_ink_cache` had this and
said why — the rename is atomic and the write into the temp is not, so two
processes sharing one `.tmp` interleave their bytes and one of them renames the
result into place, and "the editor saves a page while a sweep is running" is an
ordinary sequence here rather than a theoretical one. That reasoning was applied
to the **disposable cache** and to no other store: six corpus-wide files an
editor and a sweep both write — `_ink_exempt.json`, the split lists, the figure
exemptions, and `data/readings.md`, the whole caption store — were bare
`write_text`, and a `POST /zones/save` performs up to four of them in a row.

Nothing here takes a lock. A rename makes a torn file impossible; it does not
make two readers-modifiers-writers safe, and the last one still wins. That is a
narrower fix than the problem and is worth stating plainly rather than being
mistaken for the whole of it.
"""
from __future__ import annotations

import os
from pathlib import Path


def tmp_for(path: Path, suffix: str = ".tmp") -> Path:
    """The temp `path` should be staged through, carrying this process's pid.

    For the writers that cannot go through `write_atomic` because they do not
    hand over a string — `lxml`'s `tree.write` takes a filename and serializes
    itself. They still need the pid: `zones predict` in a terminal and the
    browser's `POST /zones/predict` on the same page is the documented workflow,
    and two of them sharing one `chukchi-PP-NNN.xml.tmp` interleave their bytes
    before either renames. `*.tmp` is gitignored and the stores are walked by
    glob, so the debris is invisible until something counts it.
    """
    path = Path(path)
    return path.with_name(f"{path.name}.{os.getpid()}{suffix}")


def write_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` through a pid-named temp, then rename.

    Creates the parent directory, on the same reasoning every store writer here
    already does it: a first write to a fresh clone should not need a mkdir at
    the call site.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding=encoding)
        tmp.replace(path)
    except BaseException:
        # A failed write leaves no debris to be mistaken for a store file. The
        # `.tmp` suffix is gitignored and the stores are walked by glob, so a
        # stray one is invisible until something counts it.
        tmp.unlink(missing_ok=True)
        raise
