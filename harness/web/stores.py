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

from .. import alphabet, apparatus, entities, figures, geo, lexicon, lookup, tei_html
from ..refs import norm_ref
from ..state import load_toc
from .cache import MAXSIZE, digest, stamp


def _entity_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "edition" / "entities").glob("*/*.md"))


def _lexicon_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "edition" / "lexicon").glob("*.md"))


def _annotation_files(root: Path) -> list[Path]:
    return sorted((Path(root) / "edition" / "annotations").glob("*/*.md"))


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
def _annotations(root: str, _key: bytes) -> dict:
    from .. import annotations as ann
    return ann.load(Path(root))


def annotations(root: Path) -> dict:
    """The editor's notices and supplements. Asked for on every page render."""
    return _annotations(str(root), stamp(_annotation_files(root)))


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


def _split_files(root: Path) -> list[Path]:
    """Every list a leaf ruling can be written in.

    All of them, derived from the vocabulary rather than named: a cache keyed on a
    subset would serve a stale answer for exactly the kind somebody had just added,
    and the staleness would look like the editor's save not having worked.
    """
    from ..zones import LEAF_KINDS, zone_dir
    return [zone_dir(Path(root)) / f"_{k}.lst" for k in LEAF_KINDS]


@lru_cache(maxsize=MAXSIZE)
def _exempt(root: str, _key: bytes) -> list[str]:
    return tei_html.exempt(Path(root))


def exempt(root: Path) -> list[str]:
    """The not-a-text-page rulings, keyed on the split lists that hold them."""
    return _exempt(str(root), stamp(_split_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _leaf_kinds(root: str, _key: bytes) -> dict[str, str]:
    from ..zones import LEAF_KINDS, load_splits
    return {r: s for r, s in load_splits(Path(root)).items() if s in LEAF_KINDS}


def leaf_kinds(root: Path) -> dict[str, str]:
    """`{ref: kind}` for every leaf a human ruled out of the tracks.

    The map rather than `exempt`'s list, because the listing needs to say *which*
    for each row and a second lookup per ref would re-read the lists 115 times.
    Same cache key: one set of files decides both answers.
    """
    return _leaf_kinds(str(root), stamp(_split_files(root)))


def _runs_files(root: Path) -> list[Path]:
    """`runs.json` and every store a declared run reads. A run's page changes when
    either does, and the second half is why this is a function rather than one
    path: the declaration names its source, so the key follows the declaration."""
    p = Path(root) / apparatus.RUNS_JSON
    out = [p]
    for r in apparatus.load_runs(Path(root)):
        if r.get("source"):
            out.append(Path(root) / r["source"])
    return out


@lru_cache(maxsize=MAXSIZE)
def _runs(root: str, _key: bytes) -> list[dict]:
    return apparatus.runs(Path(root))


def runs(root: Path) -> list[dict]:
    """Every run the edition serves. Read on every page render, parsed once."""
    return _runs(str(root), stamp(_runs_files(root)))


def run_for(root: Path, ref: str) -> dict | None:
    ref = norm_ref(ref)
    for r in runs(root):
        if ref in [norm_ref(x) for x in r.get("refs") or []]:
            return r
    return None


@lru_cache(maxsize=MAXSIZE)
def _run_store(root: str, rid: str, _key: bytes) -> dict:
    run = next((r for r in apparatus.runs(Path(root)) if r.get("id") == rid), None)
    return apparatus.store_for(run or {}, Path(root))


def run_store(root: Path, run: dict) -> dict:
    """A run's backing store, normalised. Keyed on the file it names, so an edit
    to `loi.json` reaches the page and an edit to another store does not."""
    src = run.get("source")
    return _run_store(str(root), run.get("id") or "",
                      stamp([Path(root) / src] if src else []))


@lru_cache(maxsize=MAXSIZE)
def _folio_index(root: str, _key: bytes) -> dict:
    return apparatus.folio_index(Path(root))


def folio_index(root: Path) -> dict:
    """The folio witnesses. Its third witness is one ALTO parse per keyed page —
    measured at 0.32 s over 275 of them, which is cheap enough that this cache is
    a courtesy rather than the thing that makes the route possible. Keyed on all
    three witnesses' stores, so a newly collated page moves it."""
    return _folio_index(str(root), stamp(
        _tei_files(root) + _gt_ocr_files(root) + _runs_files(root)))


def folio_by_ref(root: Path) -> dict[str, int]:
    """The folio index inverted — `{ref: folio}` — built once per index.

    `apparatus.folio_of` scans the whole index for one ref, which is the right
    shape for the one lookup a page view does and the wrong one for an entity's
    mentions: those are a ref list that can run to hundreds, and asking each of
    them separately is the index walked once per row.

    The strongest witness wins, which is the order `folio_index` already puts
    them in; a ref witnessed at two folios keeps the first, since a leaf has one
    folio and the disagreement is `apparatus.locate`'s to report, not this
    dictionary's to average.
    """
    out: dict[str, int] = {}
    for folio, seen in folio_index(root).items():
        for w in seen:
            out.setdefault(w["ref"], folio)
    return out


@lru_cache(maxsize=MAXSIZE)
def _alphabet(root: str, _key: bytes) -> dict:
    return alphabet.chart(Path(root))


def alphabet_chart(root: Path) -> dict:
    """The alphabet key joined to what this edition knows about it. Keyed on
    the store and on `gt/ocr/`, since the attestation counts move with the
    keyed corpus."""
    return _alphabet(str(root), stamp(
        [Path(root) / alphabet.STORE] + _gt_ocr_files(root)))


@lru_cache(maxsize=MAXSIZE)
def _by_plate(root: str, rid: str, _key: bytes) -> dict:
    run = next((r for r in apparatus.runs(Path(root)) if r.get("id") == rid), None)
    doc = apparatus.store_for(run or {}, Path(root))
    return figures.by_plate([e for e in doc["entries"]
                             if e.get("kind") == "plate"], Path(root))


def by_plate(root: Path, run: dict) -> dict:
    """Roman plate number -> the leaf it is on and the pictures on it. Keyed on
    both sides of the join, since either moving changes the answer."""
    src = run.get("source")
    return _by_plate(str(root), run.get("id") or "", stamp(
        ([Path(root) / src] if src else [])
        + sorted((Path(root) / "gt" / "fig").glob("chukchi-*.xml"))))


@lru_cache(maxsize=MAXSIZE)
def _by_number(root: str, _key: bytes) -> dict:
    return figures.by_number(Path(root))


def by_number(root: Path) -> dict:
    """Printed figure number -> the zones carrying it. The List of Illustrations
    links through this."""
    return _by_number(str(root), stamp(
        sorted((Path(root) / "gt" / "fig").glob("chukchi-*.xml"))))


@lru_cache(maxsize=MAXSIZE)
def _figure_boxes(root: str, ref: str, _key: bytes) -> tuple:
    return tuple(figures.figure_boxes(ref, Path(root)))


def figure_boxes(ref: str, root: Path) -> tuple:
    """One leaf's figures, with the numbers their captions print. Keyed on that
    leaf's own `gt/fig/` file, so a re-boxed plate moves only its own pages."""
    return _figure_boxes(str(root), ref, stamp(
        [Path(root) / "gt" / "fig" / f"chukchi-{norm_ref(ref)}.xml"]))


def loi_run(root: Path) -> dict:
    """The List of Illustrations run, which is what locates the plates.

    Found by `kind` rather than by id, because the id is one book's word for it
    and the kind is the vocabulary every book shares — `apparatus.KINDS`.
    """
    return next((r for r in apparatus.runs(root) if r.get("kind") == "loi"), {})


@lru_cache(maxsize=MAXSIZE)
def _authority_names(root: str, _key: bytes) -> frozenset:
    return apparatus.authority_names(Path(root))


def authority_names(root: Path) -> frozenset:
    """The names Bogoras cites other people's work under.

    A cross-reference is only this book's if no authority stands in front of it,
    and `Authorities Quoted` is the store of exactly those names. Keyed on the
    store it comes from, so adding a work reaches the pages that cite it.
    """
    run = next((r for r in apparatus.runs(root)
                if r.get("kind") == "authorities"), {})
    src = run.get("source")
    return _authority_names(str(root),
                            stamp([Path(root) / src] if src else []))


def in_reading_order(root: Path, drafts: bool) -> list[str]:
    """Every page the edition can show, in scan order — prose and plates alike.

    **Prev/next has to cross a plate**, or a reader walking the book falls off it
    at every illustration and has no way back on. So the exempt pages are threaded
    into the same list rather than given a listing of their own, and the ordering
    is the scan index, which is the order the binding puts them in.

    **A run stands in the list as its first ref and its other leaves are dropped.**
    Six scans of List of Illustrations are one document, and threading all six
    would make a reader press *next* six times to cross a list they have already
    read whole — every one of those leaves redirecting back to the page they are
    already on. The type stays `list[str]` and so does the `refs.index(ref)`
    arithmetic every caller does on it; what changes is that one member of the
    list can now stand for several scans, and `run_for` is how a caller asks.
    """
    seen = readable(root) if drafts else collated(root)
    refs = tei_html._sorted_refs([*seen, *exempt(root)])
    interior = {norm_ref(r) for run in runs(root)
                for r in (run.get("refs") or [])[1:]}
    return [r for r in refs if r not in interior]


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
        # A root with no `config/marks.json` has no fold table, so it has
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
    forms is ~445,000 parses for one page view. Nearly free while `tei/` held
    one page — and that is exactly the kind of cost nothing would announce as it
    stopped being free, which is why the sweep was written before it mattered.
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
#:
#: **Keyed on the TEI file's bytes and nothing else, which is why the figure
#: geometry is deliberately not in what it returns.** `tei_html` emits a
#: `<figure>` carrying only what the page says; the pictures are joined in at the
#: route, off `fig_layout` below, whose key names the three stores that can
#: change the answer. Putting a box in the rendered HTML would let a corrected
#: `gt/fig/` serve stale placement out of this cache with nothing to signal it.
@lru_cache(maxsize=MAXSIZE)
def _render(path: str, _page: bytes, _toc: bytes, root: str) -> dict:
    return tei_html.render(Path(path), toc_titles(Path(root)))


def render(path: Path, root: Path = Path(".")) -> dict:
    """One page's HTML, memoised on the page **and the ToC**.

    **Two files in the key, because two files decide these bytes.** A
    `<milestone>` carries an id and no words — TEI's answer to a heading in a
    div-less text, with the words left to whoever displays it — so the renderer
    reads the title out of `edition/toc.json`. That makes the ToC an input to the
    HTML, and an input that is not in the key is exactly how a corrected heading
    goes on being served with nothing to signal it.

    **This is not a licence to fold in the figure geometry**, which is still
    joined at the route and deliberately absent from what `tei_html` returns. The
    difference is not that the key may hold only one file; it is that the geometry
    join is per-figure over three stores and produces *placement*, where a page
    that placed a picture from a stale cache would look right and be wrong.
    """
    key = stamp([Path(root) / "edition" / "toc.json"])
    try:
        return _render(str(path), digest(Path(path).read_bytes()), key, str(root))
    except OSError:
        # A missing file is not cached at all — absence is the ordinary state of a
        # derived tree here, and caching it would outlive the build that fixes it.
        # `cache.by_file`'s rule, kept because this is no longer using it.
        return tei_html.render(Path(path), toc_titles(Path(root)))


render.cache_clear = _render.cache_clear               # type: ignore[attr-defined]
render.cache_info = _render.cache_info                 # type: ignore[attr-defined]


@lru_cache(maxsize=MAXSIZE)
def _toc_titles(root: str, _key: bytes) -> dict[str, dict]:
    return {e["id"]: {"number": e.get("number") or "", "title": e.get("title") or ""}
            for e in load_toc(Path(root)) if e.get("id")}


def toc_titles(root: Path) -> dict[str, dict]:
    """`{toc id: {number, title}}` — what a `<milestone n>` is displayed as.

    The number is carried because the book prints one on every chapter head and
    on nothing else, and a heading that dropped it would be citing a chapter the
    reader cannot find. It is never composed: 23 of the store's entries have one
    and the other 293 print none.
    """
    return _toc_titles(str(root), stamp([Path(root) / "edition" / "toc.json"]))


@lru_cache(maxsize=MAXSIZE)
def _fig_layout(ref: str, root: str, _key: bytes) -> dict:
    return figures.layout(ref, Path(root))


def fig_layout(ref: str, root: Path) -> dict:
    """One page's figures and where they sat in the measure.

    Two files can change this answer and both are in the key: the figure store —
    geometry *and* caption, the captions deciding the fold and therefore which
    boxes belong to which figure — and the zones the column is read from. It was
    three while the caption text lived in a file of its own; that file is gone and
    the third entry with it, which is the one kind of key change that is safe to
    make: an input folded into one already named. `stamp` folds a missing file in
    as absent, so a page with no figures is a cheap and correct empty rather than
    a special case.
    """
    root = Path(root)
    return _fig_layout(ref, str(root), stamp([
        root / "gt" / "fig" / f"chukchi-{ref}.xml",
        root / "gt" / "zones" / f"chukchi-{ref}.xml",
    ]))


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
