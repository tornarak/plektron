"""Cached reads of the stores the reading view goes through.

**The cache lives here, not in the stores.** `entities.load` and
`tei_html.render` are called by the CLI too, where a long-lived process is not
the situation and a cache would be a surprise — `harness entity check` reads the
store once and exits. What makes caching worth it is a *server*: the reading
view re-read and re-parsed every entity file on every request, and `search`
re-parsed every collated page per query. So the memoisation is a property of the
web layer, and the modules underneath stay plain.

Everything here is keyed on contents rather than on a timestamp; `cache.py` has
the measurement that made that the only safe choice.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .. import entities, geo, tei_html
from .cache import MAXSIZE, by_file, stamp


def _entity_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "entities").glob("*/*.md"))


def _tei_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "tei").glob("chukchi-*.xml"))


def _readable_files(root: Path) -> list[Path]:
    """Both stores, because `readable` changes when either does — a page collated
    since the last look moves from one to the other without changing the union's
    length, so keying on `tei/` alone would serve a stale rank."""
    return _tei_files(root) + sorted(
        (Path(root) / "mz" / "tei").glob("chukchi-*.xml"))


@lru_cache(maxsize=MAXSIZE)
def _load(root: str, _key: bytes) -> dict:
    return entities.load(Path(root))


def load(root: Path) -> dict:
    """The encyclopedia. Six call sites per page render, one parse per edit."""
    return _load(str(root), stamp(_entity_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _check(root: str, _key: bytes) -> dict:
    return entities.check(Path(root))


def check(root: Path) -> dict:
    """`entity check`'s report. The encyclopedia index called this immediately
    after `load`, so the store was walked and parsed twice per request."""
    return _check(str(root), stamp(_entity_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _collated(root: str, _key: bytes) -> list[str]:
    return tei_html.collated(Path(root))


def collated(root: Path) -> list[str]:
    return _collated(str(root), stamp(_tei_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _readable(root: str, _key: bytes) -> list[str]:
    return tei_html.readable(Path(root))


def readable(root: Path) -> list[str]:
    """`collated` plus the generated drafts. The draft server's page list."""
    return _readable(str(root), stamp(_readable_files(root)))


#: The expensive one, and the reason the ratio in `cache.py` was measured:
#: `search` renders every collated page for every query.
render = by_file(tei_html.render)


@lru_cache(maxsize=MAXSIZE)
def _shape(ident: str, root: str, _key: bytes) -> dict:
    return geo.shape(ident, Path(root))


def shape(ident: str, root: Path) -> dict:
    """One GeoJSON shape. A single map card asks for six or more of these out of
    a 1.2 MB store, each one re-read and re-decoded.

    Keyed on the index plus that one file: `geo.shape` resolves the identity
    through `index()` before reading, so a change to either can change the
    answer and both have to be in the key.
    """
    root = Path(root)
    row = geo.index(root)["shapes"].get(ident) or {}
    files = [geo.geodir(root) / row["file"]] if row.get("file") else []
    return _shape(ident, str(root), stamp([_index_path(root), *files]))


def _index_path(root: Path) -> Path:
    return geo.geodir(root) / "index.json"
