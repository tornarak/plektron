"""Page-runs, the anchor vocabulary, the folio index and the locator.

The renderers are the visible half and the cheap half. What is held here is the
part a chapter page will inherit unchanged: that a run's span is stated three times
and checked rather than merged, that one function mints every anchor, and that the
locator resolves by *rank* and refuses rather than guessing.

**The folio witness that had to be declared.** All three apparatus stores carry a
`folio` beside a `ref`, and in only one of them do the two describe the same leaf.
`authorities.json` says "this entry was printed on `1-023`, which is folio 3";
`loi.json` says "this figure appears on folio 17" while its `ref` is the
List-of-Illustrations leaf the caption was *read from*. Read the second as a folio
witness and every folio in the book resolves to the List of Illustrations, at a rank
above the running titles that had it right. `KINDS[…]["folio_of_leaf"]` is that
distinction, and `test_loi_folio_is_not_its_leafs_folio` is why it cannot be dropped.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import apparatus as A
from harness import state

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


# ------------------------------------------------------------------ fixtures


def _runs(root: Path, *runs: dict) -> None:
    root.joinpath("edition").mkdir(parents=True, exist_ok=True)
    root.joinpath("edition", "runs.json").write_text(
        json.dumps({"runs": list(runs)}), encoding="utf-8")


def _store(root: Path, name: str, doc) -> None:
    root.joinpath("edition").mkdir(parents=True, exist_ok=True)
    root.joinpath("edition", name).write_text(json.dumps(doc), encoding="utf-8")


def _exempt(root: Path, *refs: str, kind: str = "apparatus") -> None:
    """Rule these leaves out of the transcription tracks.

    `apparatus` by default because a run's leaves must be ruled exactly that — the
    printed Contents, List of Illustrations, Authorities and Alphabet, whose content
    this repository holds parsed. `kind=` is for the tests that need a leaf which is
    out of the tracks but is *not* eligible to be in a run.
    """
    p = root / "gt" / "zones" / f"_{kind}.lst"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(f"chukchi-{r}.xml\n" for r in refs), encoding="utf-8")


def _ocr_page(root: Path, ref: str, head: str, folio: str | None) -> None:
    """A `gt/ocr/` page whose running title carries a folio, the way the book
    sets it: the head and the number on one printed line, split into two by the
    segmenter. The ALTO carries no label — the band that makes those lines a
    running title is `gt/zones/`'s, written beside it."""
    from conftest import write_zones
    lines = [head] + ([folio] if folio else [])
    body = "".join(
        f'<TextLine ID="l{i}" HPOS="{300 + i * 900}" VPOS="200" '
        f'WIDTH="600" HEIGHT="60"><String CONTENT="{t}"/></TextLine>'
        for i, t in enumerate(lines))
    p = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2781" HEIGHT="3866">'
        f'<PrintSpace><TextBlock ID="text_{ref}" HPOS="300" VPOS="200" '
        f'WIDTH="2000" HEIGHT="60">{body}</TextBlock></PrintSpace>'
        "</Page></Layout></alto>", encoding="utf-8")
    write_zones(root, ref, [("RunningTitleZone", 180, 280)], x0=300, x1=2300)


def _loi(root: Path) -> dict:
    """Two leaves of List of Illustrations, in the real store's shape: the entry
    is *printed on* `ref` and *describes* something on `folio`."""
    _store(root, "loi.json", {
        "source": {"refs": ["1-014", "1-015"]},
        "figures": [
            {"kind": "figure", "numbers": [1], "caption": "Sledge",
             "folio": 17, "ref": "1-014"},
            {"kind": "figure", "numbers": [2], "caption": "Harpoon",
             "folio": 60, "ref": "1-015"},
        ],
        "plates": [{"kind": "plate", "number": "I", "caption": "Village",
                    "opposite_folio": 29, "ref": "1-015"}],
    })
    return {"id": "illustrations", "kind": "loi", "title": "List of Illustrations",
            "refs": ["1-014", "1-015"], "source": "edition/loi.json"}


def _authorities(root: Path) -> dict:
    _store(root, "authorities.json", {
        "source": {"refs": ["1-023", "1-024"]},
        "authorities": [
            {"key": "steller1774", "ref": "1-023", "folio": "3",
             "printed": [{"ref": "1-023", "text": "STELLER. Beschreibung…"}]},
            {"key": "dall1870", "ref": "1-024", "folio": "4",
             "printed": [{"ref": "1-024", "text": "DALL. Alaska…"}]},
        ],
    })
    return {"id": "authorities", "kind": "authorities", "title": "Authorities Quoted",
            "refs": ["1-023", "1-024"], "source": "edition/authorities.json"}


@pytest.fixture
def book(tmp_path: Path) -> Path:
    """Both apparatus runs, four exempt leaves, and two body pages whose running
    titles witness folios 17 and 60 — the two an LoI entry also names."""
    _runs(tmp_path, _loi(tmp_path), _authorities(tmp_path))
    _exempt(tmp_path, "1-014", "1-015", "1-023", "1-024")
    _ocr_page(tmp_path, "1-037", "THE CHUKCHEE.", "17")
    _ocr_page(tmp_path, "1-086", "RELIGION.", "60")
    return tmp_path


# -------------------------------------------------------------------- anchors


def test_anchor_is_minted_in_one_place():
    assert A.anchor("leaf", "1-015") == "leaf-1-015"
    assert A.anchor("folio", 231) == "folio-231"
    assert A.anchor("toc", "front.authorities-quoted") == "toc-front.authorities-quoted"


def test_leaf_anchor_normalises_its_ref():
    """`1-15` and `1-015` are one leaf and must not mint two ids — a link built
    from the loose spelling would land nowhere."""
    assert A.anchor("leaf", "1-15") == A.anchor("leaf", "1-015")


def test_unknown_anchor_kind_raises():
    with pytest.raises(ValueError):
        A.anchor("chapter", "chI")


# ----------------------------------------------------------------- the model


def test_runs_absent_is_empty_not_an_error(tmp_path: Path):
    """A store, not a farm: "this book declares no runs" is a true statement about
    a corpus, and the next book may have no List of Illustrations at all."""
    assert A.runs(tmp_path) == []
    assert A.run_for("1-014", tmp_path) is None
    assert A.entries_for("1-014", tmp_path) == []


def test_run_for_finds_the_span(book: Path):
    assert A.run_for("1-015", book)["id"] == "illustrations"
    assert A.run_for("1-024", book)["id"] == "authorities"
    assert A.run_for("1-100", book) is None


def test_entries_for_is_the_leafs_own(book: Path):
    """`loi.json` keeps figures and plates in two lists; a leaf gets both."""
    assert len(A.entries_for("1-014", book)) == 1
    assert len(A.entries_for("1-015", book)) == 2      # one figure, one plate


def test_a_leaf_outside_every_run_has_no_entries(book: Path):
    assert A.entries_for("1-037", book) == []


def test_no_fallback_when_a_store_lacks_per_entry_refs(tmp_path: Path):
    """A store that cannot say which leaf an entry was printed on renders
    nothing, rather than attributing the whole list to one leaf. The gate is
    where that is reported."""
    _store(tmp_path, "toc.json", [{"title": "Introductory", "page_start": 1,
                                   "id": "front.introductory"}])
    _runs(tmp_path, {"id": "contents", "kind": "toc", "title": "Contents",
                     "refs": ["1-005"], "source": "edition/toc.json"})
    _exempt(tmp_path, "1-005")
    assert A.entries_for("1-005", tmp_path) == []
    rules = {e["rule"] for e in A.check(tmp_path)["errors"]}
    assert "no-entry-provenance" in rules


# ------------------------------------------------------------ load_toc shapes


def test_load_toc_accepts_both_shapes(tmp_path: Path):
    entries = [{"title": "Introductory", "page_start": 1, "id": "front.introductory"}]
    _store(tmp_path, "toc.json", entries)
    assert state.load_toc(tmp_path) == entries
    _store(tmp_path, "toc.json", {"source": {"refs": ["1-005"]}, "entries": entries})
    assert state.load_toc(tmp_path) == entries


def test_load_toc_missing_is_empty(tmp_path: Path):
    assert state.load_toc(tmp_path) == []


# ------------------------------------------------------- what contains a folio

#: A printed list in miniature, with the two shapes that break a naive fold: front
#: matter at level 0 ahead of the chapters, and a section that is the last thing
#: before the next chapter opens.
_TOC = [
    {"level": 0, "title": "Introductory", "page_start": 1, "id": "front.intro"},
    {"level": 0, "title": "Alphabet", "page_start": 10, "id": "front.alphabet"},
    {"level": 1, "title": "Names", "page_start": 11, "id": "chI"},
    {"level": 2, "title": "Names", "page_start": 11, "id": "chI.1"},
    {"level": 3, "title": "Ai'wan", "page_start": 12, "id": "chI.1a"},
    {"level": 2, "title": "Habitat", "page_start": 14, "id": "chI.2"},
    {"level": 1, "title": "Neighbors", "page_start": 20, "id": "chII"},
]


def test_toc_containing_is_the_open_chain_shallowest_first():
    assert state.toc_containing(_TOC, 13) == ["chI", "chI.1", "chI.1a"]
    # The section changes and the subsection under the old one closes with it.
    assert state.toc_containing(_TOC, 14) == ["chI", "chI.2"]
    # On a heading's own first folio the heading is already open.
    assert state.toc_containing(_TOC, 11) == ["chI", "chI.1"]
    # Past the last entry the last chapter is still what contains you: the store
    # records no `page_end`, and stopping at the final `page_start` would leave
    # every page of the last chapter in no chapter at all.
    assert state.toc_containing(_TOC, 900) == ["chII"]


def test_a_chapter_closes_the_front_matter_before_it():
    """Level 0 is folded as level 1. Left at its own depth the Alphabet would
    stay open under every chapter that follows it, because a chapter clears only
    what is deeper than itself."""
    assert state.toc_containing(_TOC, 10) == ["front.alphabet"]
    assert state.toc_containing(_TOC, 11) == ["chI", "chI.1"]


def test_an_unwitnessed_folio_is_contained_by_nothing():
    """The refusal `toc_starts` already makes. Most of the book has no witnessed
    folio, and a locator that guessed the nearest chapter would be indistinguish-
    able, on screen, from one that knew."""
    assert state.toc_containing(_TOC, None) == []
    # Before the first entry, too — nothing precedes page 1.
    assert state.toc_containing(_TOC, 0) == []
    assert state.toc_containing([], 13) == []


def test_toc_containing_reads_the_real_store():
    """Against `edition/toc.json` itself, because the fold rests on that file being
    ordered and its `page_start` monotonic, which no fixture can witness for it.

    Two properties over every entry: the chain a heading's own first folio
    produces ends with that heading, and the chain is monotonic in level.
    """
    toc = state.load_toc(Path(__file__).resolve().parents[2] / "jesup" / "bogoras-chukchi")
    assert len(toc) > 300, "the real store, not a fixture"
    levels = {e["id"]: max(e.get("level") or 0, 1) for e in toc if e.get("id")}
    for e in toc:
        chain = state.toc_containing(toc, e["page_start"])
        assert chain, f"{e['id']} places nothing"
        depths = [levels[i] for i in chain]
        assert depths == sorted(set(depths)), f"{e['id']}: {chain} is not a chain"
        # The last entry printed at this folio is the deepest one open here, and
        # every entry is reached by its own page_start unless a later one shares
        # it — which is exactly how the printed list nests.
        assert e["id"] in chain or any(
            o["page_start"] == e["page_start"] and toc.index(o) > toc.index(e)
            for o in toc if o.get("id") in chain)


# --------------------------------------------------------------- folio index


def test_running_title_witnesses_a_folio(book: Path):
    idx = A.folio_index(book)
    assert {w["ref"] for w in idx[17]} >= {"1-037"}
    assert idx[17][0]["witness"] == "running-title"


def test_authorities_folio_witnesses_its_own_leaf(book: Path):
    """The entry *is* the thing printed on that page, so its folio is the leaf's."""
    idx = A.folio_index(book)
    assert [w["ref"] for w in idx[3]] == ["1-023"]
    assert idx[3][0]["witness"] == "apparatus"


def test_loi_folio_is_not_its_leafs_folio(book: Path):
    """The regression this file exists for. `loi.json`'s entry on `1-014` names
    folio 17, which is where the *figure* is — `1-037`. Counted as a witness it
    would place `1-014` at folio 17 as `apparatus`, outranking the running title
    that has it right, and every folio lookup in the book would land in the List
    of Illustrations."""
    idx = A.folio_index(book)
    assert [w["ref"] for w in idx[17]] == ["1-037"]
    assert "1-014" not in {w["ref"] for ws in idx.values() for w in ws}


def test_tei_outranks_a_running_title(book: Path):
    """A collated page's `<pb n>` is a human's reading; the running title is a
    mechanical lift off ground truth. Rank resolves — and the loser stays in the
    index, because a disagreement is a finding rather than a tie to break."""
    p = book / "tei" / "chukchi-1-038.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<pb n="17"/><p>x</p></body></text></TEI>', encoding="utf-8")
    idx = A.folio_index(book)
    assert [w["witness"] for w in idx[17]] == ["tei", "running-title"]
    assert A.locate(book, folio=17, index=idx)["ref"] == "1-038"


def test_same_rank_collision_refuses(book: Path):
    """Two pages claiming one folio at one rank is not a tie to break."""
    _ocr_page(book, "1-039", "THE CHUKCHEE.", "17")
    idx = A.folio_index(book)
    out = A.locate(book, folio=17, index=idx)
    assert "url" not in out
    assert {c["ref"] for c in out["candidates"]} == {"1-037", "1-039"}


# ------------------------------------------------------------------- locate


def test_locate_by_ref_lands_inside_its_run(book: Path):
    out = A.locate(book, ref="1-015")
    assert out["url"] == "/run/illustrations"
    assert out["anchor"] == "leaf-1-015"


def test_locate_by_ref_outside_a_run_is_the_page(book: Path):
    out = A.locate(book, ref="1-037")
    assert out["url"] == "/page/1-037"
    assert out["anchor"] == ""


def test_locate_by_folio_inside_a_run_uses_the_folio_anchor(book: Path):
    out = A.locate(book, folio=3)
    assert out["url"] == "/run/authorities"
    assert out["anchor"] == "folio-3"


def test_locate_by_toc_id_goes_through_page_start(book: Path):
    """The precursor property: a heading resolves today, wherever a witness
    places its opening folio, and will keep resolving unchanged once the chapter
    has a run of its own."""
    _store(book, "toc.json", [{"title": "Religion", "page_start": 60, "id": "chXI"}])
    assert A.locate(book, toc_id="chXI")["ref"] == "1-086"


def test_locate_refuses_an_unwitnessed_folio_and_names_neighbours(book: Path):
    out = A.locate(book, folio=18)
    assert "url" not in out
    assert [n["folio"] for n in out["nearest"]][0] == 17


def test_locate_on_an_unknown_toc_id_says_so(book: Path):
    _store(book, "toc.json", [])
    out = A.locate(book, toc_id="chXCIX")
    assert out["nearest"] == [] and "no ToC entry" in out["why"]


def test_locate_takes_exactly_one_key(book: Path):
    with pytest.raises(ValueError):
        A.locate(book)
    with pytest.raises(ValueError):
        A.locate(book, ref="1-014", folio=3)


# --------------------------------------------------------------------- gate


def test_a_clean_book_gates_clean(book: Path):
    assert A.check(book)["errors"] == []


def test_a_run_over_a_page_the_pipeline_still_owns_fails(book: Path):
    _exempt(book, "1-014", "1-023", "1-024")          # 1-015 no longer ruled
    errs = [e for e in A.check(book)["errors"] if e["rule"] == "not-apparatus"]
    assert [e["detail"] for e in errs] == ["1-015"]


def test_a_run_over_a_leaf_ruled_something_else_fails(book: Path):
    """Not merely exempt — **`apparatus`**. A run renders a store this repository
    holds parsed, so a plate in one would render as a list of entries it does not
    have. The looser test could not say so: a plate is out of the transcription
    tracks exactly as the Contents is, and under it this declaration passed."""
    _exempt(book, "1-014", "1-023", "1-024")
    _exempt(book, "1-015", kind="plate")
    errs = [e for e in A.check(book)["errors"] if e["rule"] == "not-apparatus"]
    assert [e["detail"] for e in errs] == ["1-015"]
    assert "ruled `plate`" in errs[0]["why"]


def test_a_leaf_ruled_apparatus_that_no_run_names_fails(book: Path):
    """The other direction, which nothing used to check. `apparatus` promises the
    leaf's content is held parsed somewhere; the run is what names *which* store.
    Without one the edition can say nothing about the page and serves a bare scan
    — a promise with no reading behind it."""
    _exempt(book, "1-014", "1-023", "1-024", "1-099")
    errs = [e for e in A.check(book)["errors"]
            if e["rule"] == "apparatus-not-in-run"]
    assert [e["detail"] for e in errs] == ["1-099"]


def test_an_unknown_kind_fails(tmp_path: Path):
    _runs(tmp_path, {"id": "glossary", "kind": "glossary", "title": "Glossary",
                     "refs": ["1-005"], "source": ""})
    _exempt(tmp_path, "1-005")
    assert any(e["rule"] == "unknown-kind" for e in A.check(tmp_path)["errors"])


def test_a_discontiguous_run_fails(book: Path):
    _runs(book, {**_loi(book), "refs": ["1-014", "1-016"]}, _authorities(book))
    assert any(e["rule"] == "discontiguous" for e in A.check(book)["errors"])


def test_overlapping_runs_fail(book: Path):
    _runs(book, _loi(book),
          {**_authorities(book), "id": "other", "refs": ["1-014", "1-015"]})
    assert any(e["rule"] == "overlapping-runs" for e in A.check(book)["errors"])


def test_span_disagreement_between_the_two_statements_fails(book: Path):
    """`runs.json` says one span and the store's own `source.refs` says another.
    Both are already in the tree; the check is that they agree, not a merge."""
    _runs(book, {**_loi(book), "refs": ["1-014", "1-015", "1-016"]},
          _authorities(book))
    _exempt(book, "1-014", "1-015", "1-016", "1-023", "1-024")
    errs = [e for e in A.check(book)["errors"] if e["rule"] == "span-disagreement"]
    assert errs and "source.refs" in errs[0]["detail"]


def test_an_editors_leaf_for_a_non_exempt_page_fails(book: Path):
    """It would never be served — `leaf_source` refuses it — so a file sitting
    there is work that will silently do nothing until somebody says so."""
    p = book / "edition" / "page-img" / "chukchi-1-037.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    assert any(e["rule"] == "leaf-not-exempt" for e in A.check(book)["errors"])


def test_a_reshaped_editors_leaf_fails(book: Path, tmp_path: Path):
    """A rescale is a touch-up; a different aspect ratio is a crop or a stretch,
    which makes it a different leaf rather than a better one."""
    from PIL import Image
    (book / "scans").mkdir(exist_ok=True)
    Image.new("L", (1000, 2000), 255).save(book / "scans" / "chukchi-1-014.png")
    d = book / "edition" / "page-img"
    d.mkdir(parents=True, exist_ok=True)
    Image.new("L", (2000, 4000), 255).save(d / "chukchi-1-014.png")
    assert not [e for e in A.check(book)["errors"] if e["rule"] == "leaf-reshaped"]

    Image.new("L", (2000, 3000), 255).save(d / "chukchi-1-014.png")
    errs = [e for e in A.check(book)["errors"] if e["rule"] == "leaf-reshaped"]
    assert errs and "chukchi-1-014.png" in errs[0]["detail"]


def test_a_vector_leaf_reports_unmeasured_rather_than_fine(book: Path):
    """An SVG has no pixel aspect to compare. `""` means unmeasured and must not
    be read as measured-and-clean — the `_ink_verdict` distinction, here too."""
    d = book / "edition" / "page-img"
    d.mkdir(parents=True, exist_ok=True)
    (d / "chukchi-1-014.svg").write_text("<svg/>", encoding="utf-8")
    rows = {r["ref"]: r for r in A.check(book)["editor_leaves"]}
    assert rows["1-014"] == {"ref": "1-014", "file": "chukchi-1-014.svg",
                             "scale": "vector", "aspect": ""}


def test_a_run_leaf_the_store_records_no_entry_for_fails(book: Path):
    """The run demands full presence: every leaf it names must be witnessed.
    A run declaring a leaf its store says nothing about renders an empty
    apparatus page, and nothing else in the tree could report it."""
    doc = json.loads((book / "edition" / "authorities.json").read_text())
    doc["authorities"] = [e for e in doc["authorities"] if e["ref"] != "1-024"]
    _store(book, "authorities.json", doc)
    errs = [e for e in A.check(book)["errors"] if e["rule"] == "unwitnessed-leaf"]
    assert errs and "1-024" in errs[0]["detail"]


def test_an_entry_outside_every_run_is_kept_and_renders_nowhere(book: Path):
    """The converse is NOT a failure, and gating it was the wrong direction.

    Authorities Quoted is an open list — folio 9's asterism ("For other
    authorities see references in the text") admits a work printed anywhere in
    the book, and Bogoras uses it: the chapter XXIII footnote on `3-146`/`3-147`
    is a second bibliography of twenty-one numbered works. Making the run the
    store's boundary meant the only way to record one was to strip its `ref` —
    discarding the leaf it is printed on to satisfy a check about rendering.

    Nothing is needed to keep such an entry off a leaf: `entries_for` resolves
    the leaf to a run first and returns [] when there is none."""
    doc = json.loads((book / "edition" / "authorities.json").read_text())
    doc["authorities"].append(
        {"key": "priklonsky1896", "ref": "3-146", "folio": "680",
         "printed": [{"ref": "3-146", "text": "14. Приклонскій, В. Л. …"}]})
    _store(book, "authorities.json", doc)
    assert not [e for e in A.check(book)["errors"]
                if e["rule"] in ("span-disagreement", "unwitnessed-leaf")]
    assert A.entries_for("3-146", book) == []
