"""Runs in the reading view: the redirect, the collapsed listing, the anchors.

The property this file exists to hold is that **a run has one URL and every one
of its leaves reaches it at its own anchor**. Six scans of List of Illustrations
are one printed list; serving them as six pages is serving the binding rather
than the book, and a redirect that lands on a page with no matching anchor is
worse than no redirect at all — the reader arrives at the top of a long list with
no sign of why.

`test_every_leaf_has_an_anchor_even_with_no_entries` is the one that keeps the two
halves honest, since the redirect and the anchor are minted in different modules
and only `apparatus.anchor` stops them drifting.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
REPO = Path(__file__).resolve().parent.parent.parent


def _fig(root: Path, ref: str, caption: str) -> None:
    """One picture and its caption on a leaf, in the shape `figure_boxes` folds:
    a GraphicZone with a FigDesc after it across the page, which is how a plate's
    rotated caption pairs (`figures._gap`)."""
    from harness.tests.test_edition_exempt import _fig_alto, _readings
    _fig_alto(root, ref, [
        (f"fig_{ref}_001", "GraphicZone", 400, 600, 1800, 900),
        (f"fig_{ref}_002", "GraphicZone-FigDesc", 2250, 600, 90, 460)])
    # Appended rather than replacing: a fixture builds several leaves and each
    # call must keep the captions the previous ones wrote.
    doc = {f"{ref}|002": caption}
    old = root / "data" / "readings.md"
    if old.exists():
        for block in old.read_text(encoding="utf-8").split("## ")[1:]:
            k, _, v = block.partition("\n")
            doc.setdefault(k.strip(), v.strip())
    _readings(root, doc)


def _only(root: Path, keep: str) -> Path:
    """The same tree with every figure ALTO but one removed, so a match that was
    ambiguous becomes unique without rebuilding the fixture."""
    for p in (root / "gt" / "fig").glob("chukchi-*.xml"):
        if p.stem != f"chukchi-{keep}":
            p.unlink()
    return root


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _exempt(root: Path, *refs: str, kind: str = "apparatus") -> None:
    """Rule these leaves. `apparatus` by default because a run's leaves must be
    ruled exactly that — these fixtures are about runs, and any other kind is now
    a gate failure rather than a passing declaration."""
    _write(root, f"gt/zones/_{kind}.lst",
           "".join(f"chukchi-{r}.xml\n" for r in refs))


def _scan(root: Path, ref: str) -> None:
    from PIL import Image
    p = root / "scans" / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (2824, 3897), 255).save(p)


def _app(root: Path, drafts: bool = False, follow: bool = True):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app
    return TestClient(create_app(root, Sessions(root=root), editor="edition",
                                 drafts=drafts), follow_redirects=follow)


@pytest.fixture
def book(tmp_path: Path) -> Path:
    """A three-leaf List of Illustrations whose middle leaf the store says
    nothing about, plus two exempt plates either side of it so the collapsed
    listing has neighbours to cross to."""
    _write(tmp_path, "data/loi.json", json.dumps({
        "source": {"refs": ["1-014", "1-015", "1-016"]},
        "figures": [
            {"kind": "figure", "numbers": [1], "caption": "Sledge",
             "folio": 17, "ref": "1-014"},
            {"kind": "figure", "numbers": [2], "caption": "Harpoon",
             "folio": 60, "ref": "1-016"},
        ],
        "plates": [],
    }))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "illustrations", "kind": "loi", "title": "List of Illustrations",
        "refs": ["1-014", "1-015", "1-016"], "source": "data/loi.json"}]}))
    _exempt(tmp_path, "1-013", "1-014", "1-015", "1-016", "1-020")
    for ref in ("1-013", "1-014", "1-015", "1-016", "1-020"):
        _scan(tmp_path, ref)
    return tmp_path


# ------------------------------------------------------------- the redirect


def test_every_leaf_redirects_into_the_run(book: Path):
    """Every leaf, the first included. One canonical URL per run beats a head
    that renders and interior leaves that bounce — with two behaviours there is
    no single address to link, cite or cache."""
    c = _app(book, follow=False)
    for ref in ("1-014", "1-015", "1-016"):
        r = c.get(f"/edition/page/{ref}")
        assert r.status_code == 302
        assert r.headers["location"] == \
            f"/edition/run/illustrations#leaf-{ref}"


def test_a_leaf_outside_any_run_still_renders_itself(book: Path):
    r = _app(book).get("/edition/page/1-020")
    assert r.status_code == 200
    assert "whole-scan" in r.text


def test_an_unknown_run_is_404(book: Path):
    assert _app(book).get("/edition/run/glossary").status_code == 404


# --------------------------------------------------------------- the anchors


def _anchors(text: str) -> list[str]:
    return re.findall(r"id='(leaf-[0-9-]+)'", text)


def test_every_leaf_has_an_anchor_even_with_no_entries(book: Path):
    """`1-015` carries no entry in the store, and still gets a marker: the
    redirect for it exists unconditionally, so the target must too."""
    t = _app(book).get("/edition/run/illustrations").text
    assert _anchors(t) == ["leaf-1-014", "leaf-1-015", "leaf-1-016"]


def test_the_redirect_and_the_anchor_are_minted_together(book: Path):
    """The two are built in different modules — the route in `web/edition.py`,
    the id in a template — and only `apparatus.anchor` keeps them equal."""
    c = _app(book, follow=False)
    frag = c.get("/edition/page/1-016").headers["location"].split("#")[1]
    assert frag in _anchors(_app(book).get("/edition/run/illustrations").text)


def test_a_leaf_mark_links_to_itself(book: Path):
    """A permalink to this point in the run, which is what a reader wants from a
    page break. Not to the raster: the scans are the scan button's."""
    t = _app(book).get("/edition/run/illustrations").text
    for ref in ("1-014", "1-015", "1-016"):
        assert f"id='leaf-{ref}' href='#leaf-{ref}'" in t
    assert "/edition/page/1-014.png" not in t


def test_the_scan_button_gets_the_whole_span(book: Path):
    """The run is one document and its scans are several, so "consult the scan"
    has to mean all of them — a card showing only the head leaf would answer
    about a page the reader may be nowhere near."""
    t = _app(book).get("/edition/run/illustrations").text
    assert '"leaves": ["1-014", "1-015", "1-016"]' in t


def test_the_span_is_one_list_across_its_leaves(book: Path):
    """Seven scans of Contents carry one printed list; closing and reopening a
    `<ul>` at each leaf would break the indentation and the reader's eye at
    boundaries that are facts about the binding."""
    t = _app(book).get("/edition/run/illustrations").text
    assert t.count("<ul class='loi'>") == 1


def test_a_leaf_mark_shows_the_printed_folio_where_the_store_records_one(
        book: Path):
    """The front matter is numbered in roman, which is what the leaf carries and
    what a reader recognises — and which is not a key into the arabic folio
    index. `source.printed_folios` is where that lives."""
    doc = json.loads((book / "data" / "loi.json").read_text())
    doc["source"]["printed_folios"] = ["xii", "xiii", "xiv"]
    _write(book, "data/loi.json", json.dumps(doc))
    t = _app(book).get("/edition/run/illustrations").text
    assert ">xii</a>" in t and ">xiv</a>" in t


def test_a_mismatched_printed_folio_list_falls_back(book: Path):
    """`printed_folios` is positional against `source.refs`. Pairing them off
    anyway when the two disagree in length would attach a folio to the wrong
    leaf, which is worse than showing none."""
    doc = json.loads((book / "data" / "loi.json").read_text())
    doc["source"]["printed_folios"] = ["xii", "xiii"]      # 2 against 3 refs
    _write(book, "data/loi.json", json.dumps(doc))
    t = _app(book).get("/edition/run/illustrations").text
    assert ">xii</a>" not in t
    assert ">1-014</a>" in t


# --------------------------------------------------------------- the listing


def test_a_run_stands_in_the_listing_as_one_entry(book: Path):
    from harness.web import stores
    refs = stores.in_reading_order(book, False)
    assert "1-014" in refs
    assert "1-015" not in refs and "1-016" not in refs


def test_prev_and_next_cross_a_run_in_one_step(book: Path):
    """A reader walking the book meets the list once, not three times — and can
    get back out the way they came."""
    t = _app(book).get("/edition/run/illustrations").text
    assert "/edition/page/1-013" in t and "/edition/page/1-020" in t


def test_the_index_names_the_run(book: Path):
    t = _app(book).get("/edition/").text
    assert "List of Illustrations" in t


# ----------------------------------------------------------------- the links


def test_a_resolvable_figure_number_links_and_an_ambiguous_one_does_not(
        tmp_path: Path):
    """One number on one zone links; a number two plates both carry is printed
    plain, because the book restarts figure numbering on every plate and picking
    one would invent the answer the collision is reporting."""
    from harness.tests.test_edition_exempt import _fig_alto, _readings
    _fig_alto(tmp_path, "1-049", [
        ("fig_1-049_001", "GraphicZone", 400, 600, 1800, 900),
        ("fig_1-049_002", "GraphicZone-FigDesc", 2250, 600, 90, 460)])
    _fig_alto(tmp_path, "1-081", [
        ("fig_1-081_001", "GraphicZone", 400, 600, 1800, 900),
        ("fig_1-081_002", "GraphicZone-FigDesc", 2250, 600, 90, 460)])
    _readings(tmp_path, {"1-049|002": "Fig. 1. Sledge.",
                         "1-081|002": "Fig. 1. Another sledge.",
                         "1-050|002": "Fig. 9. Harpoon."})
    _fig_alto(tmp_path, "1-050", [
        ("fig_1-050_001", "GraphicZone", 400, 600, 1800, 900),
        ("fig_1-050_002", "GraphicZone-FigDesc", 2250, 600, 90, 460)])
    _write(tmp_path, "data/loi.json", json.dumps({
        "source": {"refs": ["1-014"]},
        "figures": [
            {"kind": "figure", "numbers": [1], "caption": "Sledge",
             "folio": 17, "ref": "1-014"},
            {"kind": "figure", "numbers": [9], "caption": "Harpoon",
             "folio": 18, "ref": "1-014"}],
        "plates": []}))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "illustrations", "kind": "loi", "title": "List of Illustrations",
        "refs": ["1-014"], "source": "data/loi.json"}]}))
    _exempt(tmp_path, "1-014")
    _scan(tmp_path, "1-014")

    t = _app(tmp_path).get("/edition/run/illustrations").text
    assert "/edition/fig/1-050/001.png" in t, "9 resolves to one zone"
    assert "/edition/fig/1-049/001.png" not in t, "1 is on two plates"
    assert "/edition/fig/1-081/001.png" not in t


def test_a_plates_own_numbering_does_not_collide_with_the_text_series(
        tmp_path: Path):
    """**The regression that killed the list's first four entries.** Plate
    figures restart at 1 on every plate, so 31 pictures in this corpus print
    `Fig. 1`; folding them into one pool made the List of Illustrations' figures
    1–4 look ambiguous and printed them plain, when a plate's number is only a
    number within that plate and this list does not enumerate them at all.

    So the located plate leaves come out of the pool first, exactly as
    `figrefs.resolve` takes them out for a bare reference in prose. Here two
    plates and one text page all carry a `Fig. 1`, and the entry links the text
    page — the only leaf whose `1` is in the series being listed."""
    for ref, cap in (("1-049", "Fig. 1. Village Uñiˊsak."),
                     ("1-051", "Fig. 1. Anui Fair."),
                     ("1-086", "Fig. 1. Bundle of Leaf-Tobacco.")):
        _fig(tmp_path, ref, cap)
    _write(tmp_path, "data/loi.json", json.dumps({
        "source": {"refs": ["1-014"]},
        "figures": [{"kind": "figure", "numbers": [1],
                     "caption": "Bundle of Leaf-Tobacco",
                     "folio": 60, "ref": "1-014"}],
        "plates": [
            {"kind": "plate", "number": "I", "caption": "Village Uñiˊsak",
             "opposite_folio": 29, "ref": "1-014",
             "segments": ["Village Uñiˊsak"]},
            {"kind": "plate", "number": "II", "caption": "Anui Fair",
             "opposite_folio": 58, "ref": "1-014",
             "segments": ["Anui Fair"]}]}))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "illustrations", "kind": "loi", "title": "List of Illustrations",
        "refs": ["1-014"], "source": "data/loi.json"}]}))
    _exempt(tmp_path, "1-014")
    _scan(tmp_path, "1-014")

    t = _app(tmp_path).get("/edition/run/illustrations").text
    assert re.search(r"href='/edition/fig/1-086/001\.png'\s+"
                     r"data-fig='1-086/001'\s+data-label='Fig\. 1'", t)
    # …and the plates are still linked as plates, by their own join.
    assert "data-label='Plate I'" in t and "data-label='Plate II'" in t


def test_an_unlocated_plate_leaves_its_numbers_ambiguous(tmp_path: Path):
    """The filter's safe direction. Which leaves are plates is `by_plate`'s
    answer, and where it declines the leaf stays in the pool — so a number it
    shares with a text figure goes back to printing plain rather than linking to
    whichever of the two the fold happened to visit first."""
    for ref, cap in (("1-049", "Fig. 1. Village Uñiˊsak."),
                     ("1-086", "Fig. 1. Bundle of Leaf-Tobacco.")):
        _fig(tmp_path, ref, cap)
    _write(tmp_path, "data/loi.json", json.dumps({
        "source": {"refs": ["1-014"]},
        "figures": [{"kind": "figure", "numbers": [1],
                     "caption": "Bundle of Leaf-Tobacco",
                     "folio": 60, "ref": "1-014"}],
        # No caption of this text names it, so the plate does not locate.
        "plates": [{"kind": "plate", "number": "I", "caption": "Reindeer Herd",
                    "opposite_folio": 29, "ref": "1-014",
                    "segments": ["Reindeer Herd"]}]}))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "illustrations", "kind": "loi", "title": "List of Illustrations",
        "refs": ["1-014"], "source": "data/loi.json"}]}))
    _exempt(tmp_path, "1-014")
    _scan(tmp_path, "1-014")

    t = _app(tmp_path).get("/edition/run/illustrations").text
    assert "/edition/fig/1-086/001.png" not in t
    assert "/edition/fig/1-049/001.png" not in t


def test_every_plate_resolves_to_exactly_one_leaf():
    """**The gate on the plate join.** A plate carries no folio and no number on
    its own leaf; the only thing binding it to a page is a caption the printer
    set twice, abbreviated in the list and in full under the picture. All 35
    resolve today, and a drop is a regression in the matcher or in `gt/fig/` —
    either way something a reader would meet as a plate that stopped linking."""
    import json

    from harness import figures as F
    plates = json.loads(
        (REPO / "data" / "loi.json").read_text(encoding="utf-8"))["plates"]
    located = F.by_plate(plates, REPO)
    assert len(located) == len(plates) == 35
    assert located["I"]["ref"] == "1-049"


def test_a_plate_resolving_to_two_leaves_resolves_to_none(tmp_path: Path):
    """A picture shown under the wrong plate is worse than a plate with no
    picture, so an ambiguous match is dropped rather than picked between. An
    earlier matcher took the best-scoring page and bound `1-227` and `1-231` to
    each other's plates on a shared word."""
    from harness import figures as F
    for ref in ("1-049", "1-051"):
        _fig(tmp_path, ref, "Fig. 1. Village Uñiˊsak.")
    plate = {"kind": "plate", "number": "I", "segments": ["Village Uñiˊsak"]}
    assert F.by_plate([plate], tmp_path) == {}
    # …and one leaf alone resolves it
    assert list(F.by_plate([plate], _only(tmp_path, "1-049"))) == ["I"]


def test_the_plate_match_knows_nothing_about_this_book(tmp_path: Path):
    """No `Fig. N.` strip, no title convention, nothing keyed to this volume —
    the list's segment is a substring of the fuller caption either way. The
    alternative considered was computing the leaf from the stated folio and its
    parity, which is the *more* book-specific of the two: scored over the 35 it
    gets 21 right, 8 wrong and 6 unresolved, and its wrong answers land on the
    neighbouring plate's leaf."""
    from harness import figures as F
    _fig(tmp_path, "1-049", "Abbildung 7 — Dorf Uñiˊsak, im Winter.")
    plate = {"kind": "plate", "number": "I", "segments": ["Dorf Uñiˊsak"]}
    assert F.by_plate([plate], tmp_path)["I"]["ref"] == "1-049"


def test_the_plate_match_folds_marks_for_comparison_only(tmp_path: Path):
    """The list sets Plate I's village `Nuˊnligren` where the under-figure
    caption has `Nuˊnlig̣ren` — one place named twice by one printer. The fold
    lives inside the comparison and reaches no store."""
    from harness import figures as F
    _fig(tmp_path, "1-049", "Fig. 2. Village Nuˊnlig̣ren.")
    plate = {"kind": "plate", "number": "I", "segments": ["Village Nuˊnligren"]}
    assert F.by_plate([plate], tmp_path)["I"]["ref"] == "1-049"


def test_a_plate_set_in_two_boxes_links_both(tmp_path: Path):
    """**A plate's keys are its pictures, not its figures.** Plate V is two
    photographs under one caption, and `figure_boxes` folds them into a single
    record keyed on the topmost — so keying the link on `key` showed the reader
    the upper picture and silently dropped the lower. Every consumer takes
    `ref/key` as a handle on a crop, which is a zone."""
    from harness import figures as F
    from harness.tests.test_edition_exempt import _fig_alto, _readings
    _fig_alto(tmp_path, "1-123", [
        ("fig_1-123_001", "GraphicZone", 473, 585, 1986, 1112),
        ("fig_1-123_002", "GraphicZone", 492, 1928, 2016, 1354),
        ("fig_1-123_003", "GraphicZone-FigDesc", 1252, 3287, 534, 70)])
    _readings(tmp_path, {"1-123|003": "Chukchee driving Reindeer."})
    plate = {"kind": "plate", "number": "V",
             "segments": ["Chukchee driving Reindeer"]}
    hit = F.by_plate([plate], tmp_path)["V"]
    assert hit["ref"] == "1-123"
    assert hit["keys"] == ["001", "002"]


def _loi(root: Path, figures: list, plates: list) -> None:
    _write(root, "data/loi.json", json.dumps({
        "source": {"refs": ["1-014"]}, "figures": figures, "plates": plates}))
    _write(root, "data/runs.json", json.dumps({"runs": [{
        "id": "illustrations", "kind": "loi", "title": "List of Illustrations",
        "refs": ["1-014"], "source": "data/loi.json"}]}))


def test_a_plate_referred_to_in_prose_carries_the_printed_lists_caption(
        tmp_path: Path):
    """**The card was headed `Plate I` and said nothing else.** A plate is
    several pictures under several captions and none of them is the plate's, so
    the leaf cannot answer this — the printed list is where a plate's caption is
    set, and it is the same string the list's own links hand to the card. So
    clicking `Plate I` in a sentence and clicking it in the List of Illustrations
    now open the one card, which is what `openFigure`'s id already implied."""
    from harness.web.edition import _figref_state
    _fig(tmp_path, "1-049", "Fig. 1. Village Uñiˊsak.")
    _loi(tmp_path, [], [{"kind": "plate", "number": "I",
                         "caption": "Village Uñiˊsak", "opposite_folio": 29,
                         "ref": "1-014", "segments": ["Village Uñiˊsak"]}])
    got = _figref_state(
        {"figrefs": [{"kind": "plate", "number": "I", "plate": "",
                      "before": ""}]}, tmp_path)
    assert got[0]["pairs"] == ["1-049/001"]
    assert got[0]["label"] == "Plate I"
    assert got[0]["caption"] == "Village Uñiˊsak"


def test_a_figure_referred_to_in_prose_carries_the_caption_under_it(
        tmp_path: Path):
    """A text figure's caption is the one the printer set under the picture, not
    the abbreviation the list carries — the leaf is the store that has it."""
    from harness.web.edition import _figref_state
    _fig(tmp_path, "1-086", "Fig. 1. Bundle of Leaf-Tobacco.")
    _loi(tmp_path, [{"kind": "figure", "numbers": [1],
                     "caption": "Bundle of Leaf-Tobacco", "folio": 60,
                     "ref": "1-014"}], [])
    got = _figref_state(
        {"figrefs": [{"kind": "figure", "number": "1", "plate": "",
                      "before": ""}]}, tmp_path)
    assert got[0]["pairs"] == ["1-086/001"]
    assert got[0]["caption"] == "Fig. 1. Bundle of Leaf-Tobacco."


def test_another_authors_plate_carries_no_caption_either(tmp_path: Path):
    """It is not this book's picture, so there is nothing of this book's to say
    about it — the refusal keeps every field empty and only `why` speaks."""
    from harness.web.edition import _figref_state
    _fig(tmp_path, "1-049", "Fig. 1. Village Uñiˊsak.")
    _loi(tmp_path, [], [{"kind": "plate", "number": "I",
                         "caption": "Village Uñiˊsak", "opposite_folio": 29,
                         "ref": "1-014", "segments": ["Village Uñiˊsak"]}])
    _write(tmp_path, "data/authorities.json", json.dumps({
        "authorities": [{"key": "sauer", "cited_as": [{"name": "Sauer"}]}]}))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [
        {"id": "illustrations", "kind": "loi", "title": "List of Illustrations",
         "refs": ["1-014"], "source": "data/loi.json"},
        {"id": "authorities", "kind": "authorities", "title": "Authorities",
         "refs": ["1-018"], "source": "data/authorities.json"}]}))
    got = _figref_state(
        {"figrefs": [{"kind": "plate", "number": "I", "plate": "",
                      "before": "Sauer, "}]}, tmp_path)
    assert got[0]["pairs"] == [] and got[0]["caption"] == ""
    assert "Sauer" in got[0]["why"]


def test_a_folio_link_is_omitted_where_nothing_witnesses_it(book: Path):
    """A dead link to the refusal page would teach a reader to stop following
    them, so the number is printed plain instead."""
    t = _app(book).get("/edition/run/illustrations").text
    assert "/edition/folio/17" not in t
    assert ">17<" in t or "17" in t


def test_a_toc_entry_is_addressable_by_its_own_id(tmp_path: Path):
    """The precursor property, on the page rather than in the locator: every
    entry carries `toc-{id}`, so a heading has an address before chapters have
    pages of their own — and the same address after."""
    _write(tmp_path, "data/toc.json", json.dumps({
        "source": {"refs": ["1-007"]},
        "entries": [
            {"level": 0, "title": "Introductory", "page_start": 1,
             "id": "front.introductory", "ref": "1-007"},
            {"level": 1, "number": "I", "title": "Names and Habitat",
             "page_start": 11, "id": "chI", "ref": "1-007"}]}))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "contents", "kind": "toc", "title": "Contents",
        "refs": ["1-007"], "source": "data/toc.json"}]}))
    _exempt(tmp_path, "1-007")
    _scan(tmp_path, "1-007")
    t = _app(tmp_path).get("/edition/run/contents").text
    assert "id='toc-chI'" in t and "id='toc-front.introductory'" in t


# ------------------------------------------------------- folio and toc routes


def test_folio_resolves_through_the_apparatus_witness(tmp_path: Path):
    """`authorities.json` places folio 3 on `1-023` with nothing collated —
    the store recorded it while a human was keying the bibliography."""
    _write(tmp_path, "data/authorities.json", json.dumps({
        "source": {"refs": ["1-023"]},
        "authorities": [{"key": "steller1774", "ref": "1-023", "folio": "3",
                         "printed": [{"ref": "1-023", "text": "STELLER."}]}]}))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "authorities", "kind": "authorities", "title": "Authorities Quoted",
        "refs": ["1-023"], "source": "data/authorities.json"}]}))
    _exempt(tmp_path, "1-023")
    _scan(tmp_path, "1-023")
    r = _app(tmp_path, follow=False).get("/edition/folio/3")
    assert r.headers["location"] == "/edition/run/authorities#folio-3"


def test_an_unwitnessed_folio_refuses_rather_than_guessing(book: Path):
    r = _app(book, follow=False).get("/edition/folio/700")
    assert r.status_code == 404
    assert "Nothing in the corpus records folio 700" in r.text


def test_a_toc_id_resolves_through_its_page_start(tmp_path: Path):
    _write(tmp_path, "data/toc.json", json.dumps(
        [{"title": "Authorities Quoted", "page_start": 3,
          "id": "front.authorities-quoted"}]))
    _write(tmp_path, "data/authorities.json", json.dumps({
        "source": {"refs": ["1-023"]},
        "authorities": [{"key": "k", "ref": "1-023", "folio": "3",
                         "printed": []}]}))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "authorities", "kind": "authorities", "title": "Authorities Quoted",
        "refs": ["1-023"], "source": "data/authorities.json"}]}))
    _exempt(tmp_path, "1-023")
    _scan(tmp_path, "1-023")
    r = _app(tmp_path, follow=False).get("/edition/toc/front.authorities-quoted")
    assert r.headers["location"] == "/edition/run/authorities#folio-3"


# --------------------------------------------------------- the editor's leaf


def test_an_editors_leaf_is_served_only_for_an_exempt_page(tmp_path: Path):
    from harness import edition_ui as ui
    _exempt(tmp_path, "1-361")
    _write(tmp_path, "gt/page-img/chukchi-1-361.svg", "<svg/>")
    _write(tmp_path, "gt/page-img/chukchi-1-100.svg", "<svg/>")
    assert ui.leaf_source("1-361", tmp_path)[1] == "ed"
    assert ui.leaf_source("1-100", tmp_path) == (None, "scan")

    c = _app(tmp_path)
    assert c.get("/edition/leaf/1-361").status_code == 200
    assert c.get("/edition/leaf/1-100").status_code == 404


def test_the_editors_leaf_never_reaches_the_pipeline(tmp_path: Path):
    """The two resolvers must diverge on exactly the patched refs and nowhere
    else. `zones.scan_for` is what the segmenters, the ink checks and
    `fig crops` go through, and a sharpened leaf is manufactured evidence."""
    from harness import edition_ui as ui
    from harness import zones
    _exempt(tmp_path, "1-361")
    _write(tmp_path, "gt/page-img/chukchi-1-361.png", "x")
    assert zones.scan_for("1-361", tmp_path).parent.name == "scans"
    assert ui.scan_for("1-361", tmp_path).parent.name == "scans"
    assert ui.leaf_source("1-361", tmp_path)[0].parent.name == "page-img"


def test_a_vector_leaf_wins_over_a_raster_one(tmp_path: Path):
    """Vector first, because `1-361` may become one — a resolver that assumed a
    raster would have to be rewritten the day it did."""
    from harness import edition_ui as ui
    _exempt(tmp_path, "1-361")
    _write(tmp_path, "gt/page-img/chukchi-1-361.png", "x")
    _write(tmp_path, "gt/page-img/chukchi-1-361.svg", "<svg/>")
    assert ui.leaf_source("1-361", tmp_path)[0].suffix == ".svg"


# -------------------------------------------- the open list's tail


@pytest.fixture
def open_list(tmp_path: Path) -> Path:
    """Authorities Quoted over two leaves, plus one work the store records as
    printed on a leaf the run does not cover — the case folio 9's asterism
    admits and `3-146`'s chapter XXIII footnote bibliography actually is."""
    _write(tmp_path, "data/authorities.json", json.dumps({
        "source": {"refs": ["1-023", "1-024"], "count": 2,
                   "unprinted": ["priklonsky1896"]},
        "authorities": [
            {"key": "steller1774", "ref": "1-023", "folio": "3",
             "printed": [{"ref": "1-023", "text": "STELLER. Beschreibung…"}]},
            {"key": "dall1870", "ref": "1-024", "folio": "4",
             "printed": [{"ref": "1-024", "text": "DALL. Alaska…"}]},
            {"key": "priklonsky1896", "ref": "3-146", "folio": "680",
             "printed": [{"ref": "3-146", "text": "14. Приклонскій, В. Л. …"}]},
        ],
    }))
    _write(tmp_path, "data/runs.json", json.dumps({"runs": [{
        "id": "authorities", "kind": "authorities", "title": "Authorities Quoted",
        "refs": ["1-023", "1-024"], "source": "data/authorities.json"}]}))
    _exempt(tmp_path, "1-023", "1-024")
    for ref in ("1-023", "1-024"):
        _scan(tmp_path, ref)
    return tmp_path


def test_a_work_printed_outside_the_run_reaches_the_page(open_list: Path):
    """The list defers to the text and the store has keyed what it defers to, so
    the reader can follow it. Dropping the entry would leave the deferral
    pointing at nothing this edition can reach."""
    body = _app(open_list).get("/edition/run/authorities").text
    assert "priklonsky1896" in body
    assert "Приклонскій" in body


def test_the_tail_is_marked_and_not_folded_into_the_printed_list(open_list: Path):
    """**The marker is the point.** Appended silently, the page would say that
    the printed section contains a work it does not — exactly the conflation
    `source.count` is kept separate from the record count to prevent."""
    body = _app(open_list).get("/edition/run/authorities").text
    assert "authorities-tail" in body
    assert "not printed here" in body
    # The tail opens after the printed list closes, never inside it.
    assert body.index("dall1870") < body.index("authorities-tail")
    assert body.index("authorities-tail") < body.index("priklonsky1896")


def test_the_tail_does_not_join_the_runs_span(open_list: Path):
    """`leaves` drives the scan viewer and the page's own "over N leaves" line.
    A folio-680 entry joining it would make the run claim a leaf the printed
    list does not contain, and the scan button would offer it as one."""
    from harness.web import edition as E
    run = {"id": "authorities", "kind": "authorities",
           "refs": ["1-023", "1-024"], "source": "data/authorities.json"}
    leaves, tail = E._run_leaves(run, open_list)
    assert [leaf["ref"] for leaf in leaves] == ["1-023", "1-024"]
    assert [leaf["ref"] for leaf in tail] == ["3-146"]


def test_a_record_with_no_ref_at_all_stays_off_the_page(open_list: Path):
    """`jochelson1905`'s case: not printed in the book's lists at all, so it has
    no printed block to show. It exists for `find authority` to resolve a body
    citation, and rendering it would put an empty entry on the page."""
    doc = json.loads((open_list / "data" / "authorities.json").read_text())
    doc["authorities"].append({"key": "jochelson1905", "ref": None,
                               "folio": None, "printed": []})
    _write(open_list, "data/authorities.json", json.dumps(doc))
    assert "jochelson1905" not in _app(open_list).get(
        "/edition/run/authorities").text
