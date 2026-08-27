"""Key completeness: does the stamp name every store that can change the answer?

`test_web_cache.py` tests the layer below — that `stamp` and `by_file` notice a
deletion, a rename, a same-length edit, a rewrite inside one clock tick. All of
that is about a key *given* its file set. This file tests the file set itself,
which is where the same hazard reappears one storey up: a digest that is
flawless over the wrong three files is a cache that serves a stale answer with
no error signal, which is the failure this project is arranged against.

**The claim under test is written down in the docstrings.** `fig_layout` says
three files, `folio_index` says three witnesses' stores, `occurrences` says two
stamps. Those sentences are the specification; nothing until now compared them
with the key. So each test here reads the docstring's list and mutates every
member of it in turn, asserting the answer moves each time.

**The reader is replaced by a probe that reports its inputs' bytes.** Building a
real `gt/fig/` ALTO, a real geo store and a real alphabet chart would test three
readers to gate one key, and a reader that happened to ignore a file would make
a complete key look incomplete — the wrong module failing. So the memoised inner
call is monkeypatched to a function whose value *is* a digest of the files the
docstring names. Then the only thing that can hide a mutation is the cache key,
which is the thing being gated. Where a real store is cheap (`attestations`,
which has no inner call to stand in for, and `shape`, whose reader carries a
cache of its own) the real reader is used instead and the test says so.

Uncached compositions — `in_reading_order`, `run_for`, `loi_run` — have no key
of their own and are not gated here; they read through the functions that do.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness.web import stores
from harness.web.cache import stamp

TEI_NS = "http://www.tei-c.org/ns/1.0"


# ----------------------------------------------------------------- the harness


def write(p: Path, text: str) -> Path:
    """Write, holding the mtime where the file already had one.

    Pinning it makes every mutation below a same-tick rewrite — the case
    `test_web_cache.py` measured as the *usual* outcome on this filesystem — so
    a key that fell back on a timestamp could not pass by luck.
    """
    p.parent.mkdir(parents=True, exist_ok=True)
    before = p.stat().st_mtime_ns if p.exists() else None
    p.write_text(text, encoding="utf-8")
    if before is not None:
        os.utime(p, ns=(before, before))
    return p


class Probe:
    """A stand-in reader that answers with the current bytes of `files()`.

    `files` is a callable, not a list, because half these keys are globs and an
    added file has to be inside the probe's answer as well as inside the key.
    """

    def __init__(self, files, wrap=lambda d: {"probe": d}) -> None:
        self.files = files
        self.wrap = wrap
        self.calls = 0

    def __call__(self, *a, **k):
        self.calls += 1
        return self.wrap(stamp(self.files()).hex())


def pins(read, *mutations) -> None:
    """Each named mutation must reach `read()`.

    The message carries the input's name rather than the value, because what a
    failure here means is "the docstring names a file the key does not".
    """
    seen = read()
    for name, mutate in mutations:
        mutate()
        now = read()
        assert now != seen, f"{name} is not in the key"
        seen = now


def tei(root: Path, ref: str, body: str, store: str = "tei") -> Path:
    p = Path(root, *store.split("/")) / f"chukchi-{ref}.xml"
    return write(p, f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt>'
                    f"<title>t</title></titleStmt><publicationStmt><p>p</p>"
                    f"</publicationStmt><sourceDesc><p>s</p></sourceDesc>"
                    f"</fileDesc></teiHeader><text><body>{body}</body></text>"
                    "</TEI>")


def runs_json(root: Path, runs: list[dict]) -> Path:
    return write(root / "edition" / "runs.json", json.dumps(runs))


# ------------------------------------------------------------- the encyclopedia


def test_load_is_keyed_on_every_entity_file(tmp_path, monkeypatch):
    files = lambda: sorted((tmp_path / "edition" / "entities").glob("*/*.md"))  # noqa: E731
    probe = Probe(files)
    monkeypatch.setattr("harness.entities.load", probe)
    write(tmp_path / "edition" / "entities" / "place" / "markova.md", "# Markova\n")

    pins(lambda: stores.load(tmp_path),
         ("an edit to an entity",
          lambda: write(tmp_path / "edition" / "entities" / "place" / "markova.md", "# M\n")),
         ("a new entity",
          lambda: write(tmp_path / "edition" / "entities" / "person" / "bogoras.md", "# B\n")),
         ("a new class directory",
          lambda: write(tmp_path / "edition" / "entities" / "event" / "fair.md", "# F\n")),
         ("a deleted entity",
          lambda: (tmp_path / "edition" / "entities" / "person" / "bogoras.md").unlink()))
    assert probe.calls == 5


def test_check_is_keyed_on_the_same_store_as_load(tmp_path, monkeypatch):
    """`_guarded` writes the store and re-checks it inside one request — the
    window `cache.py` measured — so this key has to be the strict one too."""
    files = lambda: sorted((tmp_path / "edition" / "entities").glob("*/*.md"))  # noqa: E731
    monkeypatch.setattr("harness.entities.check", Probe(files))
    write(tmp_path / "edition" / "entities" / "place" / "markova.md", "# Markova\n")

    pins(lambda: stores.check(tmp_path),
         ("an edit to an entity",
          lambda: write(tmp_path / "edition" / "entities" / "place" / "markova.md", "# M\n")),
         ("a new entity",
          lambda: write(tmp_path / "edition" / "entities" / "place" / "anadyr.md", "# A\n")))


def test_lexicon_is_keyed_on_every_note(tmp_path, monkeypatch):
    files = lambda: sorted((tmp_path / "edition" / "lexicon").glob("*.md"))  # noqa: E731
    monkeypatch.setattr("harness.lexicon.load", Probe(files))
    write(tmp_path / "edition" / "lexicon" / "a.md", "one")

    pins(lambda: stores.lexicon_store(tmp_path),
         ("an edit to a note",
          lambda: write(tmp_path / "edition" / "lexicon" / "a.md", "two")),
         ("a new note", lambda: write(tmp_path / "edition" / "lexicon" / "b.md", "three")))


# ------------------------------------------------------------------ page lists


def test_collated_is_keyed_on_the_tei_store(tmp_path, monkeypatch):
    files = lambda: sorted((tmp_path / "tei").glob("chukchi-*.xml"))  # noqa: E731
    monkeypatch.setattr("harness.tei_html.collated", Probe(files, lambda d: [d]))
    tei(tmp_path, "1-021", "<p>one</p>")

    pins(lambda: stores.collated(tmp_path),
         ("an edit to a collated page",
          lambda: tei(tmp_path, "1-021", "<p>two</p>")),
         ("a newly collated page",
          lambda: tei(tmp_path, "1-022", "<p>three</p>")))


def test_readable_is_keyed_on_both_stores(tmp_path, monkeypatch):
    """The union, not `tei/` alone — `_readable_files`' own comment."""
    def files():
        return (sorted((tmp_path / "tei").glob("chukchi-*.xml"))
                + sorted((tmp_path / "mz" / "tei").glob("chukchi-*.xml")))

    monkeypatch.setattr("harness.tei_html.readable", Probe(files, lambda d: [d]))
    tei(tmp_path, "1-021", "<p>one</p>")

    pins(lambda: stores.readable(tmp_path),
         ("an edit under tei/", lambda: tei(tmp_path, "1-021", "<p>two</p>")),
         ("a new draft under mz/tei/",
          lambda: tei(tmp_path, "1-022", "<p>d</p>", "mz/tei")),
         ("an edit under mz/tei/",
          lambda: tei(tmp_path, "1-022", "<p>e</p>", "mz/tei")))


def test_a_page_promoted_out_of_the_drafts_is_seen(tmp_path, monkeypatch):
    """The stale-rank bug `_readable_files` records, pinned by nothing until now.

    A page collated since the last look leaves `mz/tei/` and arrives in `tei/`.
    The union's length does not move and neither does `tei/`'s glob if the key
    were taken over `tei/` alone at the wrong moment — so the mutation here is
    the promotion itself, one file deleted and one written, and what must change
    is the rank the reading view shows for that page.
    """
    def files():
        return (sorted((tmp_path / "tei").glob("chukchi-*.xml"))
                + sorted((tmp_path / "mz" / "tei").glob("chukchi-*.xml")))

    monkeypatch.setattr("harness.tei_html.readable", Probe(files, lambda d: [d]))
    tei(tmp_path, "1-021", "<p>one</p>")
    tei(tmp_path, "1-022", "<p>draft</p>", "mz/tei")
    before = stores.readable(tmp_path)

    def promote():
        (tmp_path / "mz" / "tei" / "chukchi-1-022.xml").unlink()
        tei(tmp_path, "1-022", "<p>draft</p>")

    promote()
    assert len(files()) == 2, "the promotion changed the union's length"
    assert stores.readable(tmp_path) != before, "the drafts store is not in the key"


# --------------------------------------------------------------- leaf rulings


def test_exempt_is_keyed_on_every_leaf_kind_not_a_subset(tmp_path, monkeypatch):
    """`_split_files` derives the list from `LEAF_KINDS`, and the reason it says
    so is that a subset would go stale for exactly the kind somebody just added.
    So every member of the vocabulary is mutated, not a representative one."""
    from harness.zones import LEAF_KINDS, zone_dir

    lists = [zone_dir(tmp_path) / f"_{k}.lst" for k in LEAF_KINDS]
    monkeypatch.setattr("harness.tei_html.exempt",
                        Probe(lambda: lists, lambda d: [d]))

    pins(lambda: stores.exempt(tmp_path),
         *[(f"a ruling written to _{k}.lst",
            (lambda p=p, k=k: write(p, f"chukchi-1-0{len(k):02}\n")))
           for k, p in zip(LEAF_KINDS, lists, strict=True)])


def test_leaf_kinds_shares_the_split_key(tmp_path, monkeypatch):
    """Same files decide both answers, so the map must move when the list does."""
    from harness.zones import LEAF_KINDS, zone_dir

    lists = [zone_dir(tmp_path) / f"_{k}.lst" for k in LEAF_KINDS]
    monkeypatch.setattr("harness.zones.load_splits",
                        Probe(lambda: lists, lambda d: {d: "plate"}))

    pins(lambda: stores.leaf_kinds(tmp_path),
         *[(f"a ruling written to _{k}.lst", (lambda p=p: write(p, "chukchi-1-030\n")))
           for k, p in zip(LEAF_KINDS, lists, strict=True)])


# ----------------------------------------------------------------- the runs


def test_runs_is_keyed_on_the_declaration_and_on_what_it_declares(
        tmp_path, monkeypatch):
    """`_runs_files`' second half: the declaration names its source, so the key
    follows the declaration rather than a fixed path."""
    runs_json(tmp_path, [{"id": "loi", "kind": "loi", "source": "edition/loi.json",
                          "refs": ["1-014"]}])
    write(tmp_path / "edition" / "loi.json", json.dumps({"figures": [], "plates": []}))

    def files():
        out = [tmp_path / "edition" / "runs.json"]
        for r in json.loads((tmp_path / "edition" / "runs.json").read_text()):
            if r.get("source"):
                out.append(tmp_path / r["source"])
        return out

    monkeypatch.setattr("harness.apparatus.runs", Probe(files, lambda d: [{"id": d}]))

    pins(lambda: stores.runs(tmp_path),
         ("an edit to the store a run names",
          lambda: write(tmp_path / "edition" / "loi.json",
                        json.dumps({"figures": [{"n": "1"}], "plates": []}))),
         ("an edit to runs.json",
          lambda: runs_json(tmp_path, [{"id": "loi", "kind": "loi",
                                        "source": "edition/loi.json",
                                        "refs": ["1-014", "1-015"]}])),
         ("a run re-pointed at another store",
          lambda: (write(tmp_path / "edition" / "toc.json", json.dumps([])),
                   runs_json(tmp_path, [{"id": "loi", "kind": "loi",
                                         "source": "edition/toc.json",
                                         "refs": ["1-014", "1-015"]}]))))


def test_run_store_is_keyed_on_the_file_it_names_and_no_other(
        tmp_path, monkeypatch):
    """Both halves of the docstring: an edit to `loi.json` reaches the page, and
    an edit to another store does not — the narrowness is the point, since every
    run would otherwise be re-parsed whenever any of them changed."""
    run = {"id": "loi", "kind": "loi", "source": "edition/loi.json", "refs": ["1-014"]}
    runs_json(tmp_path, [run])
    loi = write(tmp_path / "edition" / "loi.json",
                json.dumps({"figures": [], "plates": []}))
    other = write(tmp_path / "edition" / "authorities.json", json.dumps([]))
    monkeypatch.setattr("harness.apparatus.store_for", Probe(lambda: [loi]))

    pins(lambda: stores.run_store(tmp_path, run),
         ("an edit to the store the run names",
          lambda: write(loi, json.dumps({"figures": [{"n": "1"}], "plates": []}))))

    before = stores.run_store(tmp_path, run)
    write(other, json.dumps([{"name": "Nordenskiold"}]))
    assert stores.run_store(tmp_path, run) == before, "the key is not narrow"


def test_authority_names_is_keyed_on_the_authorities_store(tmp_path, monkeypatch):
    src = "edition/authorities.json"
    runs_json(tmp_path, [{"id": "auth", "kind": "authorities", "source": src,
                          "refs": ["1-012"]}])
    p = write(tmp_path / src, json.dumps({"authorities": []}))
    monkeypatch.setattr("harness.apparatus.authority_names",
                        Probe(lambda: [p], lambda d: frozenset({d})))

    pins(lambda: stores.authority_names(tmp_path),
         ("a work added to Authorities Quoted",
          lambda: write(p, json.dumps({"authorities": [{"name": "Nordenskiold"}]}))))


# ------------------------------------------------------------- the join stores


def test_folio_index_is_keyed_on_all_three_witnesses(tmp_path, monkeypatch):
    """"Keyed on all three witnesses' stores, so a newly collated page moves it."
    The three are the TEI, the keyed ALTO, and the apparatus runs."""
    runs_json(tmp_path, [{"id": "loi", "kind": "loi", "source": "edition/loi.json",
                          "refs": ["1-014"]}])
    write(tmp_path / "edition" / "loi.json", json.dumps({"figures": [], "plates": []}))

    def files():
        return (sorted((tmp_path / "tei").glob("chukchi-*.xml"))
                + sorted((tmp_path / "gt" / "ocr").glob("chukchi-*.xml"))
                + [tmp_path / "edition" / "runs.json", tmp_path / "edition" / "loi.json"])

    monkeypatch.setattr("harness.apparatus.folio_index", Probe(files))

    pins(lambda: stores.folio_index(tmp_path),
         ("a newly collated page", lambda: tei(tmp_path, "1-021", "<pb n='1'/>")),
         ("a newly keyed ALTO page",
          lambda: write(tmp_path / "gt" / "ocr" / "chukchi-1-021.xml", "<alto/>")),
         ("an edit to the apparatus store a run names",
          lambda: write(tmp_path / "edition" / "loi.json",
                        json.dumps({"figures": [{"folio": 17}], "plates": []}))),
         ("an edit to runs.json",
          lambda: runs_json(tmp_path, [{"id": "loi", "kind": "loi",
                                        "source": "edition/loi.json",
                                        "refs": ["1-014", "1-015"]}])))


def test_alphabet_chart_is_keyed_on_the_store_and_on_the_keyed_corpus(
        tmp_path, monkeypatch):
    """The attestation counts move with `gt/ocr/`, so the chart is not a pure
    function of `edition/alphabet.json` and the key cannot pretend it is."""
    from harness.alphabet import STORE

    def files():
        return ([tmp_path / STORE]
                + sorted((tmp_path / "gt" / "ocr").glob("chukchi-*.xml")))

    monkeypatch.setattr("harness.alphabet.chart", Probe(files))
    write(tmp_path / STORE, json.dumps({"sorts": []}))

    pins(lambda: stores.alphabet_chart(tmp_path),
         ("an edit to the alphabet store",
          lambda: write(tmp_path / STORE, json.dumps({"sorts": [{"id": "e"}]}))),
         ("a newly keyed ALTO page",
          lambda: write(tmp_path / "gt" / "ocr" / "chukchi-1-021.xml", "<alto/>")))


def test_by_plate_is_keyed_on_both_sides_of_the_join(tmp_path, monkeypatch):
    """A plate number comes from the List of Illustrations and the leaf it sits
    on comes from `gt/fig/`; either moving changes where the reader is sent."""
    run = {"id": "loi", "kind": "loi", "source": "edition/loi.json", "refs": ["1-014"]}
    runs_json(tmp_path, [run])
    loi = write(tmp_path / "edition" / "loi.json",
                json.dumps({"figures": [], "plates": [{"n": "I"}]}))

    def files():
        return [loi] + sorted((tmp_path / "gt" / "fig").glob("chukchi-*.xml"))

    monkeypatch.setattr("harness.figures.by_plate", Probe(files))

    pins(lambda: stores.by_plate(tmp_path, run),
         ("an edit to the List of Illustrations",
          lambda: write(loi, json.dumps({"figures": [],
                                         "plates": [{"n": "II"}]}))),
         ("a newly boxed figure leaf",
          lambda: write(tmp_path / "gt" / "fig" / "chukchi-1-030.xml", "<alto/>")))


def test_by_number_is_keyed_on_the_figure_store(tmp_path, monkeypatch):
    files = lambda: sorted(  # noqa: E731
        (tmp_path / "gt" / "fig").glob("chukchi-*.xml"))
    monkeypatch.setattr("harness.figures.by_number", Probe(files))
    write(tmp_path / "gt" / "fig" / "chukchi-1-030.xml", "<alto/>")

    pins(lambda: stores.by_number(tmp_path),
         ("a re-boxed figure",
          lambda: write(tmp_path / "gt" / "fig" / "chukchi-1-030.xml", "<alto />")),
         ("a newly boxed leaf",
          lambda: write(tmp_path / "gt" / "fig" / "chukchi-1-031.xml", "<alto/>")))


def test_figure_boxes_is_keyed_on_that_leafs_own_file(tmp_path, monkeypatch):
    """"so a re-boxed plate moves only its own pages" — both halves, since a key
    over the whole store would be correct and would evict the book each time."""
    mine = tmp_path / "gt" / "fig" / "chukchi-1-030.xml"
    write(mine, "<alto/>")
    monkeypatch.setattr("harness.figures.figure_boxes",
                        Probe(lambda: [mine], lambda d: [d]))

    pins(lambda: stores.figure_boxes("1-030", tmp_path),
         ("a re-boxed leaf", lambda: write(mine, "<alto />")))

    before = stores.figure_boxes("1-030", tmp_path)
    write(tmp_path / "gt" / "fig" / "chukchi-1-031.xml", "<alto/>")
    assert stores.figure_boxes("1-030", tmp_path) == before, "the key is not narrow"


def test_fig_layout_is_keyed_on_both_files(tmp_path, monkeypatch):
    """Geometry and zones, and the captions ride in on the first of them.

    This named three files while the caption text lived in `data/readings.md`,
    and the third was the one an obvious key would miss: the captions decide the
    fold and therefore which boxes belong to which figure, so a corrected reading
    moves the placement without touching either ALTO. That is still true — the
    caption now lives *on* the FigDesc block, so an edit to it is an edit to
    `gt/fig/`, and the key that would have missed it is the one it is folded
    into. The last pin is that property: a caption edited in place moves the
    answer.
    """
    files = [tmp_path / "gt" / "fig" / "chukchi-1-030.xml",
             tmp_path / "gt" / "zones" / "chukchi-1-030.xml"]
    monkeypatch.setattr("harness.figures.layout", Probe(lambda: files))

    pins(lambda: stores.fig_layout("1-030", tmp_path),
         ("gt/fig/", lambda: write(files[0], "<alto/>")),
         ("gt/zones/", lambda: write(files[1], "<alto/>")),
         ("an edited caption, which is an edit to gt/fig/",
          lambda: write(files[0], "<alto><!-- Fig. 87 --></alto>")))


def test_fig_layout_reads_a_page_with_no_figures_as_an_empty(tmp_path, monkeypatch):
    """"`stamp` folds a missing file in as absent, so a page with no figures is a
    cheap and correct empty rather than a special case" — and the file arriving
    later still moves the answer, which is what makes the absence safe to key."""
    files = [tmp_path / "gt" / "fig" / "chukchi-1-030.xml",
             tmp_path / "gt" / "zones" / "chukchi-1-030.xml"]
    monkeypatch.setattr("harness.figures.layout", Probe(lambda: files))

    pins(lambda: stores.fig_layout("1-030", tmp_path),
         ("a figure boxed for the first time", lambda: write(files[0], "<alto/>")))


# ----------------------------------------------------------------- the geo store


def _geo(root: Path, shapes: list[dict]) -> Path:
    return write(root / "edition" / "geo" / "index.json",
                 json.dumps({"window": [], "shapes": shapes}))


def test_shape_is_keyed_on_the_index_and_on_the_file(tmp_path, monkeypatch):
    """"`geo.shape` resolves the identity through `index()` before reading, so a
    change to either can change the answer and both have to be in the key.\""""
    _geo(tmp_path, [{"id": "anadyr", "file": "anadyr.json"}])
    f = write(tmp_path / "edition" / "geo" / "anadyr.json",
              json.dumps({"features": []}))
    monkeypatch.setattr("harness.geo.shape",
                        Probe(lambda: [tmp_path / "edition" / "geo" / "index.json", f]))

    pins(lambda: stores.shape("anadyr", tmp_path),
         ("a rebuilt shape file",
          lambda: write(f, json.dumps({"features": [{"type": "Feature"}]}))),
         ("an edit to the index",
          lambda: _geo(tmp_path, [{"id": "anadyr", "file": "anadyr.json",
                                   "name": "Anadyr"}])))


def test_a_rebuilt_shape_file_reaches_the_map(tmp_path):
    """The real reader, and it is the half that works: `_shape`'s key holds the
    file's own bytes and `geo.shape` reads it directly."""
    _geo(tmp_path, [{"id": "anadyr", "file": "anadyr.json"}])
    f = tmp_path / "edition" / "geo" / "anadyr.json"
    write(f, json.dumps({"features": [{"id": 1}]}))
    assert stores.shape("anadyr", tmp_path)["features"] == [{"id": 1}]
    write(f, json.dumps({"features": [{"id": 2}]}))
    assert stores.shape("anadyr", tmp_path)["features"] == [{"id": 2}]


@pytest.mark.xfail(strict=True, reason="geo.index still keys on st_mtime")
def test_an_index_repointed_at_another_file_reaches_the_map(tmp_path):
    """`stores.shape`'s key is complete and the answer is still stale.

    Re-pointing a shape at a different file moves `index.json`'s bytes, so the
    stamp moves and `_shape` re-runs — and `geo.shape` then resolves the row
    through `geo.index`, which is memoised on `st_mtime` (`geo.py`, "Keyed on
    mtime so an edit during a long-lived `edition serve` is picked up without a
    restart"). `cache.py` measured that key: 190 of 200 immediate rewrites carry
    an identical timestamp, so the rebuild is invisible and the old file's
    features are served under the new declaration.

    The mtime is pinned here rather than raced for, so this is the measured case
    and not a flake. Marked expected-to-fail because this file is a gate, not a
    repair: the fix is in `geo.index`, not in the stamp above it.
    """
    _geo(tmp_path, [{"id": "anadyr", "file": "one.json"}])
    g = tmp_path / "edition" / "geo"
    write(g / "one.json", json.dumps({"features": [{"id": 1}]}))
    write(g / "two.json", json.dumps({"features": [{"id": 2}]}))
    assert stores.shape("anadyr", tmp_path)["features"] == [{"id": 1}]

    _geo(tmp_path, [{"id": "anadyr", "file": "two.json"}])
    assert stores.shape("anadyr", tmp_path)["features"] == [{"id": 2}]


def test_shape_survives_an_identity_the_index_does_not_hold(tmp_path, monkeypatch):
    """No row means no file in the key, which must be a stamp rather than a
    KeyError — the index is a store and a missing id is its ordinary answer."""
    _geo(tmp_path, [])
    monkeypatch.setattr("harness.geo.shape",
                        Probe(lambda: [tmp_path / "edition" / "geo" / "index.json"]))
    assert stores.shape("nowhere", tmp_path)["probe"]


# -------------------------------------------------------------------- the sweeps


def test_occurrences_is_keyed_on_the_pages_and_on_the_alias_table(
        tmp_path, monkeypatch):
    """Two stamps, because two stores can change the answer. The alias table is
    the one a key over the corpus alone would miss: a name added to an entity
    makes pages match that matched nothing, with no page having changed."""
    def pages():
        return (sorted((tmp_path / "tei").glob("chukchi-*.xml"))
                + sorted((tmp_path / "mz" / "tei").glob("chukchi-*.xml")))

    def files():
        return pages() + sorted((tmp_path / "edition" / "entities").glob("*/*.md"))

    from test_entities import entry

    monkeypatch.setattr("harness.entities.occurrences", Probe(files))
    # Real records, because `_occurrences` still calls the real `entities.load`
    # for the sweep's arguments; only the sweep itself is stood in for.
    markova = entry(tmp_path, "place:markova", aliases=[("Markova", True)])
    tei(tmp_path, "1-021", "<p>Markova</p>")

    pins(lambda: stores.occurrences(tmp_path),
         ("a newly collated page", lambda: tei(tmp_path, "1-022", "<p>x</p>")),
         ("a generated draft",
          lambda: tei(tmp_path, "1-023", "<p>y</p>", "mz/tei")),
         ("an alias added to an entity",
          lambda: entry(tmp_path, "place:markova",
                        aliases=[("Markova", True), ("Markovo", True)])),
         ("a new entity", lambda: entry(tmp_path, "place:anadyr")))
    assert markova.exists()


def test_attestations_is_keyed_on_the_collated_store(tmp_path):
    """The real reader, because `_attestations` is its own body — there is no
    inner call to stand in for, which is also why nothing else can key it."""
    import unicodedata

    form = unicodedata.normalize("NFD", "mêˊmêl")
    tei(tmp_path, "1-021", f'<p><foreign xml:lang="ckt">{form}</foreign></p>')
    assert stores.attestations(tmp_path)[form] == [("1-021", "ckt")]

    tei(tmp_path, "1-022", f'<p><foreign xml:lang="ckt">{form}</foreign></p>')
    assert stores.attestations(tmp_path)[form] == [("1-021", "ckt"),
                                                   ("1-022", "ckt")]

    tei(tmp_path, "1-022", '<p><foreign xml:lang="ckt">other</foreign></p>')
    assert stores.attestations(tmp_path)[form] == [("1-021", "ckt")]


# ------------------------------------------------------------------ the renderer


def test_render_is_keyed_on_the_page_and_on_the_toc(tmp_path, monkeypatch):
    """"Two files in the key, because two files decide these bytes." A
    `<milestone>` carries an id and no words, so the heading is read out of
    `edition/toc.json` and a corrected heading has to reach the cached HTML."""
    toc = write(tmp_path / "edition" / "toc.json",
                json.dumps([{"id": "chVII", "title": "Reindeer Breeding"}]))
    p = tei(tmp_path, "1-021", '<milestone unit="section" n="chVII"/>')
    monkeypatch.setattr("harness.tei_html.render", Probe(lambda: [p, toc]))

    pins(lambda: stores.render(p, tmp_path),
         ("an edit to the page", lambda: tei(tmp_path, "1-021",
                                             '<milestone unit="section" n="chVI"/>')),
         ("a corrected heading in edition/toc.json",
          lambda: write(toc, json.dumps([{"id": "chVII",
                                          "title": "Reindeer-Breeding"}]))))


def test_a_missing_page_is_not_cached(tmp_path, monkeypatch):
    """Absence is the ordinary state of a derived tree here, and `mz/tei/` is
    one — caching the absence would outlive the `tei generate` that fixes it."""
    write(tmp_path / "edition" / "toc.json", json.dumps([]))
    p = tmp_path / "mz" / "tei" / "chukchi-1-021.xml"
    probe = Probe(lambda: [p])
    monkeypatch.setattr("harness.tei_html.render", probe)

    stores.render(p, tmp_path)
    stores.render(p, tmp_path)
    assert probe.calls == 2, "the absence was cached"


def test_toc_titles_is_keyed_on_the_toc(tmp_path, monkeypatch):
    toc = write(tmp_path / "edition" / "toc.json", json.dumps([{"id": "chVII"}]))
    monkeypatch.setattr(stores, "load_toc",
                        Probe(lambda: [toc],
                              lambda d: [{"id": d, "number": "", "title": ""}]))

    pins(lambda: stores.toc_titles(tmp_path),
         ("an edit to edition/toc.json",
          lambda: write(toc, json.dumps([{"id": "chVII", "number": "VII"}]))))


# --------------------------------------------------------------- the native index


def test_native_is_keyed_on_the_keyed_corpus(tmp_path, monkeypatch):
    files = lambda: sorted(  # noqa: E731
        (tmp_path / "gt" / "ocr").glob("chukchi-*.xml"))
    monkeypatch.setattr("harness.lookup.index", Probe(files))
    write(tmp_path / "gt" / "ocr" / "chukchi-1-021.xml", "<alto/>")

    pins(lambda: stores.native(tmp_path),
         ("a corrected ALTO page",
          lambda: write(tmp_path / "gt" / "ocr" / "chukchi-1-021.xml", "<alto />")),
         ("a newly keyed page",
          lambda: write(tmp_path / "gt" / "ocr" / "chukchi-1-022.xml", "<alto/>")))


def test_the_native_memo_is_the_no_exclude_index_only(tmp_path, monkeypatch):
    """`_native` never passes `exclude`, and the memo is keyed on `(root, gt/ocr
    stamp)` — nothing about a leave-one-out is in that key.

    That is correct today because no web path excludes. It is pinned because the
    failure a future caller would meet is silent: routing a leave-one-out through
    `stores.native` would return the unfiltered index, so a page would be
    corroborated by its own reading, which is the exact thing `lookup.index`'s
    `exclude` exists to prevent. If `stores.native` ever grows an `exclude`
    parameter, this test should fail and the key must grow with it.
    """
    import inspect

    seen = []

    def spy(root, exclude=None):
        seen.append(exclude)
        return {"buckets": {}, "by_key": {}, "unkeyable": {}}

    monkeypatch.setattr("harness.lookup.index", spy)
    write(tmp_path / "gt" / "ocr" / "chukchi-1-021.xml", "<alto/>")
    stores.native(tmp_path)

    assert seen == [None], "stores.native passed an exclude the key does not hold"
    assert "exclude" not in inspect.signature(stores.native).parameters


@pytest.mark.xfail(strict=True, reason="the fold table is not in native's key")
def test_native_notices_the_fold_table(tmp_path, monkeypatch):
    """`lookup.index` reads `config/marks_config.json` for the contrasts it folds
    on, so the fold table decides the buckets — and it is not in the key.

    Marked expected-to-fail rather than fixed here: this file is a gate, not a
    repair. Editing the contrasts under a running `edition serve` serves the old
    bucketing, which is the staleness the whole module is arranged against; the
    fix is to add the config to `native`'s stamp, and this test then passes.
    """
    from harness.marks import CONFIG

    def files():
        return ([tmp_path / CONFIG]
                + sorted((tmp_path / "gt" / "ocr").glob("chukchi-*.xml")))

    monkeypatch.setattr("harness.lookup.index", Probe(files))
    write(tmp_path / "gt" / "ocr" / "chukchi-1-021.xml", "<alto/>")
    write(tmp_path / CONFIG, json.dumps({"contrasts": []}))

    pins(lambda: stores.native(tmp_path),
         ("config/marks_config.json",
          lambda: write(tmp_path / CONFIG,
                        json.dumps({"contrasts": ["˙"]}))))
