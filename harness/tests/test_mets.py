"""`harness/mets.py` — the manifest builder, which had no test at all.

It moved out of `figures.py` and out of the `fig` group in the same pass, so
what is pinned here is the generality that motivated the move: `build_mets` is a
function of filenames, and `write_mets` serves any store rather than `gt/fig/`.

The property the module exists to hold is **never into the store it describes**,
and that one is structural rather than behavioural — `--out` is `required=True`
in the parser and there is no default to fall back to. `test_cli_surface.py`
gates the flag's presence; what a test can add is that the writer puts the file
where it was told and nowhere else.
"""
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from harness.mets import ALTO_STORES, METS_NS, build_mets, write_mets


def _store(root: Path, store: str, names: list[str]) -> None:
    d = root / store
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / n).write_text("<alto/>", encoding="utf-8")


class TestBuildMets:
    def test_one_file_entry_and_one_page_div_per_name(self):
        xml = build_mets(["chukchi-1-001.xml", "chukchi-1-002.xml"])
        t = ET.fromstring(xml)
        assert len(t.findall(f".//{{{METS_NS}}}file")) == 2
        divs = t.findall(f".//{{{METS_NS}}}div[@TYPE='page']")
        assert len(divs) == 2

    def test_every_fptr_resolves_to_a_declared_file_id(self):
        """The manifest's two halves are joined by FILEID, and a structMap
        pointing at an id no fileGrp declares is the one way this can be
        malformed while still parsing."""
        t = ET.fromstring(build_mets([f"chukchi-1-{i:03d}.xml" for i in range(1, 6)]))
        ids = {f.get("ID") for f in t.findall(f".//{{{METS_NS}}}file")}
        ptrs = {p.get("FILEID") for p in t.findall(f".//{{{METS_NS}}}fptr")}
        assert ptrs == ids
        assert len(ids) == 5

    def test_a_name_needing_escaping_survives_as_a_value(self):
        """`quoteattr` is in the builder for this; the corpus has no such name
        today, which is exactly why nothing would notice it regressing."""
        t = ET.fromstring(build_mets(['a&b"c.xml']))
        loc = t.find(f".//{{{METS_NS}}}FLocat")
        assert loc.get("{http://www.w3.org/1999/xlink}href") == 'a&b"c.xml'

    def test_no_image_filegrp(self):
        """On import the pages match images already in the document. An image
        fileGrp would name rasters the archive does not carry."""
        t = ET.fromstring(build_mets(["chukchi-1-001.xml"]))
        uses = {g.get("USE") for g in t.findall(f".//{{{METS_NS}}}fileGrp")}
        assert uses == {"export"}


class TestWriteMets:
    def test_it_serves_a_store_that_is_not_gt_fig(self, tmp_path):
        """The whole point of the move. `gt/fig` was never special to the code."""
        _store(tmp_path, "gt/ocr", ["chukchi-1-002.xml", "chukchi-1-001.xml"])
        rep = write_mets("gt/ocr", tmp_path / "out", tmp_path)
        assert rep["store"] == "gt/ocr"
        assert rep["files"] == 2
        assert (tmp_path / "out" / "METS.xml").exists()

    def test_names_are_sorted_which_for_this_corpus_is_page_order(self, tmp_path):
        _store(tmp_path, "gt/ocr",
               ["chukchi-1-010.xml", "chukchi-1-002.xml", "chukchi-1-001.xml"])
        rep = write_mets("gt/ocr", tmp_path / "out", tmp_path)
        assert (rep["first"], rep["last"]) == ("chukchi-1-001.xml",
                                               "chukchi-1-010.xml")

    def test_it_writes_only_where_told_and_never_into_the_store(self, tmp_path):
        """The module's reason for existing in this shape."""
        _store(tmp_path, "gt/ocr", ["chukchi-1-001.xml"])
        write_mets("gt/ocr", tmp_path / "out", tmp_path)
        assert not (tmp_path / "gt" / "ocr" / "METS.xml").exists()

    def test_a_non_page_file_beside_the_altos_is_not_manifested(self, tmp_path):
        """`METS.xml` itself is the case that mattered: a stale one sat in
        `gt/ocr/` for the life of the repo, and a rebuild must not list it."""
        _store(tmp_path, "gt/ocr", ["chukchi-1-001.xml"])
        (tmp_path / "gt" / "ocr" / "METS.xml").write_text("<mets/>")
        (tmp_path / "gt" / "ocr" / "notes.txt").write_text("x")
        rep = write_mets("gt/ocr", tmp_path / "out", tmp_path)
        assert rep["files"] == 1

    def test_an_empty_store_raises_rather_than_writing_an_empty_manifest(self, tmp_path):
        """A manifest listing nothing imports as a document with no pages, which
        is a worse outcome than the usage error the CLI turns this into."""
        (tmp_path / "mz" / "fig").mkdir(parents=True)
        with pytest.raises(ValueError, match="no chukchi"):
            write_mets("mz/fig", tmp_path / "out", tmp_path)
        assert not (tmp_path / "out").exists()

    def test_an_absent_store_raises_too(self, tmp_path):
        """Every `mz/` tree is derived and gitignored, so naming one on a fresh
        clone is the ordinary case, not a corrupt tree."""
        with pytest.raises(ValueError, match="no chukchi"):
            write_mets("mz/ocr", tmp_path / "out", tmp_path)

    def test_two_stores_into_one_directory_keep_the_second(self, tmp_path):
        """Documented rather than prevented — the name has to be `METS.xml` for
        eScriptorium. The test exists so the collision is a decision on record
        and not a discovery."""
        _store(tmp_path, "gt/ocr", ["chukchi-1-001.xml"])
        _store(tmp_path, "gt/fig", ["chukchi-2-001.xml", "chukchi-2-002.xml"])
        write_mets("gt/ocr", tmp_path / "out", tmp_path)
        write_mets("gt/fig", tmp_path / "out", tmp_path)
        t = ET.parse(tmp_path / "out" / "METS.xml").getroot()
        assert len(t.findall(f".//{{{METS_NS}}}file")) == 2


class TestStorePool:
    def test_the_pool_is_the_stores_the_repo_declares(self):
        """A typo in `ALTO_STORES` would surface as a `click.Choice` a caller
        cannot satisfy, so the shape is worth pinning: paths under the root,
        no trailing slash, no duplicates."""
        assert len(set(ALTO_STORES)) == len(ALTO_STORES)
        for s in ALTO_STORES:
            assert not s.startswith("/") and not s.endswith("/")
            assert s.count("/") <= 1

    def test_the_two_views_are_in_it(self):
        """`ocr/` and `zones/` are what a person would usually export, since
        they resolve to whichever store holds each page."""
        assert "ocr" in ALTO_STORES and "zones" in ALTO_STORES

    def test_write_mets_does_not_enforce_the_pool(self, tmp_path):
        """The list is a CLI convenience. A caller with a store this module has
        not heard of must not be blocked by a tuple they cannot edit."""
        _store(tmp_path, "elsewhere", ["chukchi-1-001.xml"])
        assert write_mets("elsewhere", tmp_path / "out", tmp_path)["files"] == 1
