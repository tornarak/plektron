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

from .. import entities, geo, lexicon, lookup, tei_html
from .cache import MAXSIZE, by_file, stamp


def _entity_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "entities").glob("*/*.md"))


def _lexicon_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "lexicon").glob("*.md"))


def _gt_ocr_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "gt" / "ocr").glob("chukchi-*.xml"))


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


@lru_cache(maxsize=MAXSIZE)
def _lexicon(root: str, _key: bytes) -> dict:
    return lexicon.load(Path(root))


def lexicon_store(root: Path) -> dict:
    """The edition lexicon — the authored half, which is one field per form."""
    return _lexicon(str(root), stamp(_lexicon_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _native(root: str, _key: bytes) -> dict:
    from ..marks import MarksConfigError
    try:
        return lookup.index(Path(root))
    except MarksConfigError:
        # A root with no `data/marks_config.json` has no fold table, so it has
        # no buckets — the same answer `entities.load` gives for a missing
        # store, and for the same reason: absence is emptiness, not a 500 on a
        # page that would otherwise render.
        return {"buckets": {}, "by_key": {}, "unkeyable": {}}


def native(root: Path) -> dict:
    """Every Tier-1 form attested in `gt/ocr/`, bucketed and keyed.

    **This is the lexicon's population**, and the reason the reading view does
    not wait on collation: 609 forms with the pages and printed lines they occur
    on, out of a store a human has already been through. A whole-corpus parse,
    so it is read once per change to `gt/ocr/` rather than once per card.
    """
    return _native(str(root), stamp(_gt_ocr_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _occurrences(root: str, _key: bytes, _ekey: bytes) -> dict:
    r = Path(root)
    return entities.occurrences(sorted(entities.load(r)), tei_html.readable(r),
                                entities.load(r), r)


def occurrences(root: Path) -> dict:
    """Every entity's mentions across the readable corpus, in one sweep.

    **One sweep for the whole store, not one per entity.** A card asks about a
    single entity, and answering it by parsing every page would make the index
    quadratic the moment anything listed more than one — the trap `_attestations`
    below documents, arrived at the same way.

    Widest corpus here and **narrowed per request** at the route, because the
    reading view serves collated pages only unless `--drafts` says otherwise and
    a mentions row pointing at a page it would 404 is worse than no row. Keying
    the cache on the mode instead would double it to answer a question a filter
    answers.

    Two stamps, because two stores can change the answer: the pages, and the
    alias table the sweep matches with.
    """
    return _occurrences(str(root), stamp(_readable_files(root)),
                        stamp(_entity_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _attestations(root: str, _key: bytes) -> dict:
    """`{form: [(ref, lang), …]}` over every collated page, in one sweep.

    Per-form it was one parse of every collated page *per form asked about*,
    which is fine for a card and quadratic for an index: 730 pages against 609
    forms is ~445,000 parses for one page view. Free today, since `tei/` holds
    no collated page yet — and that is exactly the kind of cost nothing would
    announce when it stopped being free.
    """
    from lxml import etree

    from ..validate import TIER1, XML_LANG

    out: dict[str, list[tuple[str, str]]] = {}
    for ref in tei_html.collated(Path(root)):
        try:
            doc = etree.parse(str(tei_html.page_path(ref, Path(root)))).getroot()
        except (OSError, etree.XMLSyntaxError):
            continue
        seen = set()
        for el in doc.iter():
            if not isinstance(el.tag, str):
                continue
            lang = el.get(XML_LANG)
            if lang not in TIER1:
                continue
            text = lexicon.norm_form("".join(el.itertext()))
            if (text, lang) in seen or not text:
                continue
            seen.add((text, lang))
            out.setdefault(text, []).append((ref, lang))
    return out


def attestations(root: Path) -> dict:
    return _attestations(str(root), stamp(_tei_files(root)))


#: The expensive one, and the reason the ratio in `cache.py` was measured:
#: `search` renders every collated page for every query.
render = by_file(tei_html.render)


@lru_cache(maxsize=MAXSIZE)
def _shape(ident: str, root: str, _key: bytes) -> dict:
    return geo.shape(ident, Path(root))


def shape(ident: str, root: Path) -> dict:
    """One GeoJSON shape. A single map asks for six or more of these out of
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
