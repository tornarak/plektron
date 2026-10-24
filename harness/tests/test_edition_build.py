"""`edition build`: the reading view written to disk as a static site.

What has to hold is that the site *is* the served output and that it fails rather
than shipping something a reader would find broken: a link with nothing behind
it, a card the stack would fetch and get a 404 for, an entry nothing reaches.
And that two builds of one tree are the same bytes, since that is what makes a
build usable as a regression net.
"""
from __future__ import annotations

import filecmp
from pathlib import Path

import pytest
from test_edition import page
from test_edition_runs import _scan
from test_entities import entry

from harness.web.build import _canon, build, norm_base


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    entry(root, "place:markova", status="proposed", aliases=[("Markova", True)])
    page(root, "1-021", '<pb n="1"/><p>At '
         '<rs ref="place:markova" resp="#mz">Markova</rs>.</p>')
    _scan(root, "1-021")
    return root


def _files(d: Path) -> list[str]:
    return sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file())


def test_a_tree_with_nothing_missing_builds_clean(tree, tmp_path):
    site = build(tree, tmp_path / "site", base="/bogoras")
    assert site.rows == []
    out = tmp_path / "site"
    # The page, the card on its own page, and the bare fragment the stack and the
    # hover preview fetch — the last reached only through a `data-ref`.
    for rel in ("index.html", "page/1-021/index.html", "page/1-021.png",
                "entity/place:markova/index.html",
                "partial/entity/place:markova/index.html",
                "annotations/index.html", "static/js/edition.js",
                "static/js/geomap.js", "geo/atlas.json"):
        assert (out / rel).is_file(), rel
    # The page composes every map, so none is written down.
    assert not (out / "map").exists() and not (out / "partial" / "map").exists()


def test_every_link_names_the_base_and_none_names_the_live_mount(tree, tmp_path):
    build(tree, tmp_path / "site", base="/bogoras/")
    for p in (tmp_path / "site").rglob("*.html"):
        text = p.read_text(encoding="utf-8")
        assert "'/edition/" not in text and '"/edition/' not in text, p
        assert "'/static/" not in text and '"/static/' not in text, p
    assert "/bogoras/entity/place:markova" in (
        tmp_path / "site" / "page" / "1-021" / "index.html").read_text()


def test_a_static_page_offers_no_search_and_no_ratify(tree, tmp_path):
    build(tree, tmp_path / "site")
    card = (tmp_path / "site" / "entity" / "place:markova" / "index.html").read_text()
    assert "/search" not in card
    assert "class='ratify'" not in card


def test_two_builds_of_one_tree_are_the_same_bytes(tree, tmp_path):
    """And one of them pooled: concurrency may move the wall clock and nothing
    else, and the only way to say so is to build both and compare."""
    build(tree, tmp_path / "a", base="/x", jobs=1)
    build(tree, tmp_path / "b", base="/x", jobs=2)
    a, b = _files(tmp_path / "a"), _files(tmp_path / "b")
    assert a == b
    _match, mismatch, errors = filecmp.cmpfiles(
        tmp_path / "a", tmp_path / "b", a, shallow=False)
    assert mismatch == [] and errors == []


def test_a_link_with_no_file_behind_it_is_refused_and_names_who_links_it(
        tree, tmp_path):
    """The scan is asked for by the scan card's script, off `STATE.ref` — no
    href names it, which is exactly the URL a crawl of hrefs alone would miss."""
    (tree / "scans" / "chukchi-1-021.png").unlink()
    site = build(tree, tmp_path / "site")
    assert [(r["url"], r["from"]) for r in site.rows] == [
        ("/page/1-021.png", ["/page/1-021"])]
    assert "HTTP 404" in site.rows[0]["why"]


def test_an_entry_nothing_mentions_is_still_reached_through_its_index(
        tree, tmp_path):
    entry(tree, "person:unmentioned", aliases=[("Unmentioned", False)])
    site = build(tree, tmp_path / "site")
    assert site.rows == []
    assert "/entity/person%3Aunmentioned" in site.files


def test_what_nothing_links_to_is_an_orphan(tree, tmp_path, monkeypatch):
    """Seeding from the stores would publish it, and hide that nobody can find
    it — so the crawl does not seed, and the stores are asked afterwards. The
    annotations index went unlinked for its whole life until this asked."""
    from harness.web import build as B

    links = B._links
    monkeypatch.setattr(B, "_links", lambda text, base: [
        x for x in links(text, base) if not x.endswith("/annotations")])
    site = build(tree, tmp_path / "site")
    assert site.rows == [{"url": "/annotations", "why": "nothing links to it",
                          "from": []}]
    assert not (tmp_path / "site" / "annotations").exists()


def test_a_redirect_is_a_stub_that_keeps_the_fragment(tmp_path):
    from harness.web.build import _stub
    stub = _stub("/x/run/chI#leaf-1-004")
    assert "location.replace" in stub and "url=/x/run/chI#leaf-1-004" in stub


@pytest.mark.parametrize("given,want", [("/", ""), ("", ""), ("/bogoras/", "/bogoras"),
                                        ("bogoras", "/bogoras")])
def test_the_base_is_normalised(given, want):
    assert norm_base(given) == want


def test_two_spellings_of_one_path_are_one_url():
    """`quote` and `encodeURIComponent` disagree on `'`, and a host decodes both
    to the one file."""
    assert _canon("/lexicon/Ke%27let") == _canon("/lexicon/Ke'let")
