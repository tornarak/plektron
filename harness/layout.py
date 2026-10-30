"""Which text a store belongs to, and what its page files are called.

**One text, one stem, in kebab-case**: `chukchi`, `chukchi-mythology`, `koryak`,
`yukaghir`. A page's files are `<stem>-PP-NNN.*` in every store, and the stem is
declared once, in the `project.json` at the top of the text's stores. Nothing
derives it from the folder and nothing guesses it: a store with no manifest
refuses, because a default stem would be one book's name wearing the clothes of a
fact about every book.

**Above `refs.py`, which imports nothing**, and this imports only that. `refs.py`
holds the readings that need nothing but their argument; a stem needs the
manifest, so everything that has to spell a file name comes here.
"""
from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from .refs import REF_RE, norm_ref, parse_ref

#: The name of the manifest, and of what makes a directory a text's.
PROJECT_JSON = "project.json"

STEM_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*$")


class ProjectError(ValueError):
    """A manifest that is missing or says something it may not."""


@cache
def _project(path: str) -> dict:
    p = Path(path) / PROJECT_JSON
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProjectError(f"no {PROJECT_JSON} at {path}: not a text's stores") from None
    except json.JSONDecodeError as e:
        raise ProjectError(f"{p}: not JSON: {e}") from None
    stem = rec.get("stem") if isinstance(rec, dict) else None
    if not isinstance(stem, str) or not STEM_RE.match(stem):
        raise ProjectError(f"{p}: `stem` must be kebab-case, e.g. `chukchi-mythology`; "
                           f"got {stem!r}")
    return rec


def project(root: Path = Path(".")) -> dict:
    """The manifest of the text whose stores sit at `root`."""
    return _project(str(Path(root).resolve()))


def stem(root: Path = Path(".")) -> str:
    """This text's file-name stem, without the joining hyphen."""
    return project(root)["stem"]


def stem_for(ref: str, root: Path = Path(".")) -> str:
    """The file-name stem of one page: `1-48` -> `chukchi-1-048`."""
    return f"{stem(root)}-{norm_ref(ref)}"


def ref_of(name: str, root: Path = Path(".")) -> str:
    """The page ref a file stem names, in this text. `chukchi-1-048` -> `1-048`.

    **Another text's stem is refused, not stripped**: `koryak-1-048` is not this
    book's 1-048, however much it looks like it. A bare ref names no book to
    disagree with, so it reads as this text's.
    """
    name = str(name).strip()
    if REF_RE.match(name):
        return norm_ref(name)
    own = f"{stem(root)}-"
    if name.startswith(own) and REF_RE.match(name[len(own):]):
        return norm_ref(name[len(own):])
    raise ValueError(f"{name!r} is not a page ref of `{stem(root)}`: expected "
                     f"{own}PP-NNN or a bare PP-NNN")


def page_files(directory: Path, suffix: str, root: Path = Path(".")) -> list[Path]:
    """The page files under `directory`, in (part, scan index) order.

    The whole name must be `<stem>-<ref><suffix>`, which a glob cannot say: a
    figure's crop `chukchi-1-048-a.png` and another text's `chukchi-mythology-1-048.png`
    both match `chukchi-*.png`. A directory that is not there holds no pages, as
    it does for a glob.
    """
    own = f"{stem(root)}-"
    found = []
    for p in Path(directory).glob(f"{own}*{suffix}"):
        rest = p.name[len(own):-len(suffix)] if suffix else p.name[len(own):]
        if REF_RE.match(rest):
            found.append((parse_ref(rest), p))
    return [p for _, p in sorted(found, key=lambda t: t[0])]
