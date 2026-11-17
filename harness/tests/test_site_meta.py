"""What a published page says about itself: its head, its outline, and the files a
crawler reads (`web/meta.py`, `web/site.py`'s sitemaps).

The failure that matters is a tag that is fluent and wrong — a citation naming a
page number nothing recorded, a canonical address for a text that is not
published there. So most of what is here is what must be *absent*.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from lxml import html as LH
from test_edition import page
from test_edition_runs import _scan
from test_site_build import ONE, TWO, _age, _as_own, _declare_image, make_repo

from harness.web import STATIC, meta
from harness.web.edition import _view_h1
from harness.web.site import build_site


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """`test_site_build`'s two-text repo."""
    return make_repo(tmp_path)

HOST = "https://press.example"


def _header(root: Path, *, ptr: str | None = HOST + "/", date_resp: str = "") -> None:
    (root / "tei").mkdir(exist_ok=True)
    (root / "tei" / "corpus-header.xml").write_text(
        '<teiHeader xmlns="http://www.tei-c.org/ns/1.0"><fileDesc><titleStmt>'
        '<title type="main">A Book</title><title type="sub">an edition</title>'
        '<author><persName><forename>Ann</forename><surname>Writer</surname></persName>'
        '</author></titleStmt><publicationStmt><authority>X</authority>'
        + (f'<ptr target="{ptr}"/>' if ptr else "")
        + '<availability><licence target="https://creativecommons.org/publicdomain/zero/1.0/">'
        '<p>Text.</p></licence></availability></publicationStmt><sourceDesc>'
        '<biblStruct><monogr><title>A Book</title><imprint><publisher>A Press</publisher>'
        '<date>1904-1909</date></imprint></monogr><series><title level="s">A Series</title>'
        '<biblScope unit="volume" n="7">VII</biblScope></series></biblStruct>'
        '<listBibl type="parts"><bibl n="1"><title>One</title><date'
        + (f' resp="{date_resp}"' if date_resp else "") + ' when="1904">1904</date>'
        '</bibl></listBibl></sourceDesc></fileDesc></teiHeader>', encoding="utf-8")


def _pages(dest: Path):
    """Every written page a reader lands on: not a stub, not a fragment."""
    for p in sorted(dest.rglob("index.html")):
        rel = p.parent.relative_to(dest).as_posix()
        text = p.read_text(encoding="utf-8")
        if rel.startswith("partial") or "<title>Redirecting</title>" in text:
            continue
        yield rel, text


def _built(repo, tmp_path, **kw) -> Path:
    _header(repo / ONE, **kw)
    _age(repo)
    rep = build_site(repo, tmp_path / "out", jobs=1)
    assert rep.refused == []
    return tmp_path / "out"


def test_every_page_has_one_h1_a_title_its_preview_repeats_and_an_absolute_canonical(
        repo, tmp_path):
    out = _built(repo, tmp_path)
    seen = 0
    for rel, text in _pages(out / ONE):
        tree = LH.fromstring(text)
        assert len(tree.findall(".//h1")) == 1, rel
        title = tree.findtext(".//title")
        assert tree.find(".//meta[@property='og:title']").get("content") == title, rel
        canon = tree.find(".//link[@rel='canonical']").get("href")
        assert canon.startswith(f"{HOST}/{ONE}"), rel
        json.loads(tree.find(".//script[@type='application/ld+json']").text)
        assert tree.get("lang") == "en"
        seen += 1
    assert seen > 3


def test_a_page_cites_the_folio_it_recorded_and_no_other(repo, tmp_path):
    root = repo / ONE
    # `1-021` records folio 1 (`<pb n="1"/>`); this one records none.
    _as_own(page(root, "1-025", "<pb/><p>A page whose folio nobody recorded at all.</p>"), "one")
    _scan(root, "1-025")
    _as_own(root / "scans" / "chukchi-1-025.png", "one")
    out = _built(repo, tmp_path)
    cited = (out / ONE / "page" / "1-021" / "index.html").read_text("utf-8")
    assert '<meta name="citation_firstpage" content="1">' in cited
    assert '<meta name="citation_author" content="Writer, Ann">' in cited
    assert '<meta name="citation_publication_date" content="1904">' in cited
    bare = (out / ONE / "page" / "1-025" / "index.html").read_text("utf-8")
    assert "citation_firstpage" not in bare and "citation_lastpage" not in bare
    assert "pageStart" not in bare


def test_a_part_date_a_model_read_is_not_cited_until_a_human_ratifies_it(repo, tmp_path):
    out = _built(repo, tmp_path, date_resp="#llm")
    cited = (out / ONE / "page" / "1-021" / "index.html").read_text("utf-8")
    assert "citation_publication_date" not in cited
    _header(repo / ONE, date_resp="#ed")
    build_site(repo, tmp_path / "out", jobs=1)
    cited = (out / ONE / "page" / "1-021" / "index.html").read_text("utf-8")
    assert '<meta name="citation_publication_date" content="1904">' in cited


def test_the_preview_image_is_the_texts_one_picture_and_a_file_the_build_wrote(repo, tmp_path):
    _declare_image(repo / ONE, "one")
    out = _built(repo, tmp_path)
    for rel, text in _pages(out / ONE):
        tree = LH.fromstring(text)
        img = tree.find(".//meta[@property='og:image']").get("content")
        assert img == f"{HOST}/{ONE}/cover-1200.jpg", rel
        assert tree.find(".//meta[@property='og:image:alt']").get("content") == "A plate."
    assert (out / ONE / "cover-1200.jpg").is_file()


def test_a_text_with_no_picture_has_no_preview_image(repo, tmp_path):
    out = _built(repo, tmp_path)
    for rel, text in _pages(out / ONE):
        assert "og:image" not in text, rel
        assert '"image"' not in text, rel


def test_a_header_with_no_address_states_none(repo, tmp_path):
    out = _built(repo, tmp_path, ptr=None)
    for rel, text in _pages(out / ONE):
        assert "rel=\"canonical\"" not in text and "og:url" not in text, rel
    assert not (out / ONE / "sitemap.xml").exists()
    assert not (out / "robots.txt").exists()


def test_the_sitemap_lists_the_pages_and_not_the_stubs_or_the_fragments(repo, tmp_path):
    out = _built(repo, tmp_path)
    urls = re.findall(r"<loc>([^<]+)</loc>", (out / ONE / "sitemap.xml").read_text("utf-8"))
    assert f"{HOST}/{ONE}/" in urls and f"{HOST}/{ONE}/page/1-021" in urls
    assert not any("/partial/" in u for u in urls)
    assert len(urls) == len(list(_pages(out / ONE)))
    # Only the text with an address; the root indexes it, and robots.txt names that.
    assert not (out / TWO / "sitemap.xml").exists()
    index = (out / "sitemap.xml").read_text("utf-8")
    assert f"<loc>{HOST}/{ONE}/sitemap.xml</loc>" in index and TWO not in index
    robots = (out / "robots.txt").read_text("utf-8")
    assert f"Sitemap: {HOST}/sitemap.xml" in robots and f"Disallow: /{ONE}/partial/" in robots


def test_an_unpublished_text_states_no_address(repo, tmp_path):
    from test_site_build import _publish
    _header(repo / ONE)
    _publish(repo / ONE, None)
    got = meta.head(repo / ONE, {"origin": HOST, "title": "A Book"},
                    f"/{ONE}/page/1-021", f"/{ONE}", title="x")
    assert got["canonical"] == "" and "url" not in json.loads(got["ld"])


def test_a_view_takes_its_first_milestone_as_its_h1_and_only_that():
    html = ('<h2 class="milestone chapter" id="a">I. One</h2><p>x</p>'
            '<h2 class="milestone section" id="b">Two</h2>')
    got, promoted = _view_h1(html)
    assert promoted and got.count("<h1") == 1 and got.count("<h2") == 1
    assert got.startswith('<h1 class="milestone chapter" id="a">I. One</h1>')
    assert _view_h1("<p>none</p>") == ("<p>none</p>", False)


def test_a_description_is_cut_at_a_word_and_skips_a_note_marker():
    assert meta.clip("word " * 60).endswith("word…")
    html = ('<p>Short.</p><p>The first<a class="noteref" href="#n1">¹</a> real '
            'paragraph of the page.</p>')
    assert meta.first_paragraph(html) == "The first real paragraph of the page."


def test_json_ld_cannot_close_its_own_script_element():
    assert "</script>" not in meta._ld({"name": "</script><b>"})


def test_the_browser_chrome_colour_is_the_stylesheets_background():
    css = (STATIC / "css" / "edition.css").read_text("utf-8")
    light = re.search(r":root \{[^}]*?--bg:(#[0-9a-f]{6})", css).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{[^}]*?--bg:(#[0-9a-f]{6})', css).group(1)
    base = (STATIC.parent / "templates" / "edition" / "base.html").read_text("utf-8")
    assert f'media="(prefers-color-scheme: light)" content="{light}"' in base
    assert f'media="(prefers-color-scheme: dark)" content="{dark}"' in base
