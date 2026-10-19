"""Where an annotation lands on the page, and what it is allowed to emit.

**Placement is asserted on the rendered output and never against a constant.**
A test comparing template line numbers would pass while the block sat in the
wrong half of the document; what a notice promises a reader is that it comes
*before* the text, so the offsets of the two are what the test compares.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness.tests.test_edition import entry, page

LINKS = """
| alias | url | title | note |
|---|---|---|---|
| album | https://example.test/a | An album | 1974 |
"""


def annotation(root: Path, cls: str, slug: str, *, status="ratified",
               attaches=("page:1-021",), title="T", summary="See [[album]].",
               links=LINKS, full="") -> Path:
    p = root / "edition" / "annotations" / cls / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = f"# {cls}:{slug} — {title}\n\n- status: {status}\n"
    body += "".join(f"- attaches: {t}\n" for t in attaches)
    if links:
        body += f"\n## links\n{links}"
    body += f"\n## summary\n\n{summary}\n"
    if full:
        body += f"\n## full\n\n{full}\n"
    p.write_text(body, encoding="utf-8")
    return p


@pytest.fixture
def client(tmp_path):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    entry(tmp_path, "place:markova", status="ratified",
          aliases=[("Markova", True)])
    page(tmp_path, "1-021", '<pb n="1"/><p>At Markova.</p>')
    (tmp_path / "edition").mkdir(exist_ok=True)
    (tmp_path / "edition" / "toc.json").write_text(
        '{"entries": [{"level": 1, "chapter": "I", "title": "One", '
        '"page_start": 1, "id": "chI"}]}', encoding="utf-8")

    def make():
        return TestClient(create_app(tmp_path, Sessions(root=tmp_path),
                                     editor="edition"))
    return tmp_path, make


def test_a_notice_renders_before_the_text_and_a_supplement_after_it(client):
    root, make = client
    annotation(root, "notice", "n", title="A notice")
    annotation(root, "supplement", "s", title="A supplement")
    html = make().get("/edition/page/1-021").text

    notice = html.find("class='ann notice")
    supp = html.find("class='ann supplement")
    article = html.find("<article>")
    assert -1 < notice < article, "a notice must come before the text"
    assert supp > article, "a supplement must come after the text"


def test_a_proposed_annotation_attaches_to_nothing_but_keeps_its_own_page(client):
    root, make = client
    annotation(root, "notice", "n", status="proposed", title="Unsigned")
    c = make()
    assert "class='ann notice" not in c.get("/edition/page/1-021").text
    # Reachable at its own URL, which is where a reviewer reads it before
    # ratifying. A store whose unratified entries were unreachable would have no
    # review step at all.
    own = c.get("/edition/annotation/notice:n")
    assert own.status_code == 200
    assert "Unsigned" in own.text


def test_a_link_alias_resolves_and_a_hostile_one_cannot_emit_markup(client):
    root, make = client
    annotation(root, "notice", "n",
               summary="Hear [[album]] and <script>alert(1)</script>.")
    html = make().get("/edition/page/1-021").text
    assert 'href="https://example.test/a"' in html
    assert ">An album</a>" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_a_javascript_url_never_reaches_an_href(client):
    """`_link_rows` refuses it at the parser, so the store cannot hold one.

    Asserted here as well as in `test_annotations` because this is the surface
    where it would matter: the gate and the renderer are two different promises.
    """
    from harness import annotations as ann

    root = client[0]
    p = annotation(root, "notice", "n")
    p.write_text(p.read_text().replace("https://example.test/a",
                                       "javascript:alert(1)"), encoding="utf-8")
    with pytest.raises(ann.Malformed, match="not an http or https URL"):
        ann.parse(p.read_text(), str(p))


def test_the_unwitnessed_sentence_is_printed_only_when_a_section_is_attached(client):
    """The guard, both ways.

    A page nothing can place carries the sentence — otherwise its absence is
    indistinguishable from there being no such notice. But only where the store
    actually holds a `toc:` attachment: a corpus with none would grow a banner
    on every unplaced leaf explaining why it cannot show a kind of annotation
    nobody has written.
    """
    root, make = client
    page(root, "1-022", "<p>No pb element, so no folio.</p>")

    annotation(root, "notice", "n", attaches=("page:1-021",))
    assert "unplaced" not in make().get("/edition/page/1-022").text

    annotation(root, "notice", "n", attaches=("toc:chI",))
    assert "unplaced" in make().get("/edition/page/1-022").text


def test_a_direct_page_attachment_needs_no_folio_at_all(client):
    """The route that never refuses, asserted on a page that cannot be placed."""
    root, make = client
    page(root, "1-022", "<p>No pb element, so no folio.</p>")
    annotation(root, "notice", "n", attaches=("page:1-022",))
    assert "class='ann notice" in make().get("/edition/page/1-022").text


def test_a_section_notice_sits_under_the_marker_a_reader_lands_on(client):
    """**The contents panel links to `#chI`, which `tei_html` emits inside the
    article.** A notice rendered above the article is therefore above that
    anchor, so following the section from the panel scrolls straight past it —
    the block is on the page and off the screen, at exactly the moment it was
    written to be read.
    """
    root, make = client
    # A *section*, not the chapter: a page carrying a chapter milestone opens a
    # chapter run and is served inside it, where notices pool at the head. The
    # rule here is the single page's.
    (root / "edition" / "toc.json").write_text(
        '{"entries": [{"level": 1, "chapter": "I", "title": "One", '
        '"page_start": 1, "id": "chI"}, {"level": 2, "chapter": "I", '
        '"title": "Names", "page_start": 3, "id": "chI.1"}]}', encoding="utf-8")
    # `<milestone>` is what `tei_html.el_milestone` turns into the anchor the
    # contents panel links to — a boundary, not a container, carrying no text.
    page(root, "1-023",
         '<pb n="3"/><milestone unit="section" n="chI.1"/><p>Body.</p>')
    annotation(root, "notice", "n", attaches=("toc:chI.1",))
    html = make().get("/edition/page/1-023").text

    marker = max(html.find("id='chI.1'"), html.find('id="chI.1"'))
    notice = html.find("class='ann notice")
    assert marker != -1, "this page must mark the section for the test to mean anything"
    assert notice > marker, "a section's notice belongs under the marker"
    assert html.count("class='ann notice") == 1, "placed once, not twice"


def test_a_section_notice_stays_on_top_where_the_page_marks_no_section(client):
    """The other half of the rule. A page *inside* a section that does not print
    its head has no anchor to sit under, and the reader arrived at the page
    rather than at a point inside it."""
    root, make = client
    annotation(root, "notice", "n", attaches=("toc:chI",))
    html = make().get("/edition/page/1-021").text
    notice, article = html.find("class='ann notice"), html.find("<article>")
    assert -1 < notice < article


def test_placing_a_notice_does_not_poison_the_render_cache(client):
    """`stores.render` is `lru_cache`d. Splicing into the record it handed back
    would serve one page's notice on every later render of it."""
    root, make = client
    page(root, "1-023",
         '<pb n="3"/><milestone unit="chapter" n="chI"/><p>Body.</p>')
    annotation(root, "notice", "n", attaches=("toc:chI",))
    c = make()
    first = c.get("/edition/page/1-023").text
    second = c.get("/edition/page/1-023").text
    assert first == second
    assert second.count("class='ann notice") == 1


def test_an_annotation_reaches_an_entity_card(client):
    root, make = client
    annotation(root, "notice", "n", attaches=("entity:place:markova",))
    html = make().get("/edition/entity/place:markova?partial=1").text
    assert html.find("class='ann notice") < html.find("class='gloss'")


def test_the_inline_preview_does_not_reprint_the_whole_shelf(client):
    """**A block over a page of the book is a preview, not the record.**

    The `## links` table is where an annotation keeps its addresses so the prose
    can point into them; it is not a list to reprint on every leaf the
    annotation attaches to. `supplement:music` carries 45 rows, and rendering
    them inline put 16 KB of links above the text on every attached page.

    What the reader gets instead is the summary — whose prose links resolve from
    that same table, so the ones the author actually named are still there — and
    a way through to the rest.
    """
    root, make = client
    rows = "".join(
        f"| a{i:02d} | https://example.test/{i} | Item {i} | |\n" for i in range(12))
    annotation(root, "supplement", "s",
               links="| alias | url | title | note |\n|---|---|---|---|\n" + rows,
               summary="Only [[a00]] is named here.")
    c = make()

    page_html = c.get("/edition/page/1-021").text
    block = re.search(r"<aside class='ann supplement'.*?</aside>",
                      page_html, re.S).group(0)
    assert "<li>" not in block, "the preview reprinted the shelf"
    assert "example.test/0" in block, "the summary's own link should survive"
    assert "example.test/7" not in block, "an unnamed row leaked into the preview"
    assert "/edition/annotation/supplement:s" in block, "no way through"

    # The record itself keeps every row.
    own = c.get("/edition/annotation/supplement:s").text
    assert own.count("example.test/") >= 12


def test_a_card_page_loads_the_script_that_makes_its_links_work(client):
    """**The scripts a template loads have to follow the markup its partials
    emit.**

    `card.html` renders the same partials as `page.html` and carries the same
    sidebar, so it shows the same `a.yt` and `a.ent` anchors — but it listed
    every script *except* `edition.js`, which is the file that intercepts them.
    Nothing errored: the anchors looked live, and a click on a recording left the
    edition instead of opening the player beside the text. The failure is
    invisible to any test that only checks the markup, which is why this one
    checks the pair.
    """
    root, make = client
    annotation(root, "supplement", "s", attaches=("entity:place:markova",),
               links="| alias | url | title | note |\n|---|---|---|---|\n"
                     "| album | https://www.youtube.com/watch?v=j_GLEh8EYYk"
                     "&list=OLAK5uy_k7wp4QTiM | An album | |\n",
               summary="Hear [[album]].")
    c = make()
    for url in ("/edition/annotation/supplement:s",
                "/edition/entity/place:markova"):
        html = c.get(url).text
        assert "class='yt'" in html or 'class="yt"' in html, f"no yt anchor on {url}"
        assert "edition.js" in html, f"{url} shows yt links and loads no handler"
        # `hover.js` first: `edition.js`'s `fill` reads the memo it publishes.
        assert html.find("hover.js") < html.find("edition.js")


def test_every_parsed_key_is_rendered_or_declared(client):
    """A field nobody displays is a field a human maintains for nothing.

    `test_edition.py` holds the entity record to the same rule; this is its
    mirror, and it is what stops the format growing a key the reader never sees.
    """
    from harness import annotations as ann

    root, make = client
    annotation(root, "notice", "n", full="The long text.")
    rec = ann.load(root)["notice:n"]
    html = make().get("/edition/annotation/notice:n").text

    shown_elsewhere = {
        "slug", "class", "id",        # in the ident line, as `notice:n`
        "attaches",                   # rendered as the "attached to" list
        "used_links",                 # the parse-time cross-check, not a field
        "dir_class", "stem", "path",  # filesystem facts `load` adds
        "summary", "full", "links",   # rendered as HTML, not as raw text
    }
    for key, value in rec.items():
        if key in shown_elsewhere or not isinstance(value, str) or not value:
            continue
        assert value in html, f"{key} is parsed and never shown"
