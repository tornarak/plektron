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


TWO_SECTIONS = (
    '{"entries": [{"level": 1, "chapter": "I", "title": "One", '
    '"page_start": 1, "id": "chI"}, {"level": 2, "chapter": "I", '
    '"title": "Names", "page_start": 3, "id": "chI.1"}, {"level": 2, '
    '"chapter": "I", "title": "Drinks", "page_start": 3, "id": "chI.2"}]}')


def _sections(root):
    (root / "edition" / "toc.json").write_text(TWO_SECTIONS, encoding="utf-8")
    page(root, "1-023",
         '<pb n="3"/><milestone unit="section" n="chI.1"/><p>Of names.</p>'
         '<milestone unit="section" n="chI.2"/><p>Of drinks.</p>')


def test_a_section_supplement_sits_at_that_sections_foot(client):
    """**The bottom of the section, not of the page.** Below the text is the
    foot of everything the page shows; the supplement is about one section, and
    the next section's head is where that section stops."""
    root, make = client
    _sections(root)
    annotation(root, "supplement", "s", attaches=("toc:chI.1",))
    html = make().get("/edition/page/1-023").text
    supp = html.find("class='ann supplement")
    assert html.find("Of names.") < supp < html.find("Of drinks.")


def test_a_block_goes_to_the_narrowest_section_and_appears_once(client):
    """Keyed to the chapter and to its second section, the section is narrower;
    keyed to both sections, the first one wins. Either way it is printed once."""
    root, make = client
    _sections(root)
    annotation(root, "notice", "n", attaches=("toc:chI", "toc:chI.2"))
    annotation(root, "supplement", "s", attaches=("toc:chI.2", "toc:chI.1"))
    html = make().get("/edition/page/1-023").text
    assert html.count("class='ann notice") == 1
    assert html.count("class='ann supplement") == 1
    notice, supp = html.find("class='ann notice"), html.find("class='ann supplement")
    assert html.find("Of names.") < notice < html.find("Of drinks."), \
        "a notice on chI and chI.2 belongs at the top of chI.2"
    assert html.find("Of names.") < supp < html.find("Of drinks."), \
        "two sections at one depth: the first in the text"


def test_a_section_opened_before_the_page_ends_on_it(client):
    """A page that begins inside a section has that section's foot and not its
    top: the notice stays above the text, the supplement lands where the next
    section's head stands."""
    root, make = client
    # chI.2 opens on folio 4, so the printed Contents alone puts folio 4 in chI.2
    # and never reaches chI.1, which the page begins in.
    (root / "edition" / "toc.json").write_text(
        TWO_SECTIONS.replace('"page_start": 3, "id": "chI.2"',
                             '"page_start": 4, "id": "chI.2"'), encoding="utf-8")
    page(root, "1-024", '<pb n="4"/><p>Still names.</p>'
                        '<milestone unit="section" n="chI.2"/><p>Of drinks.</p>')
    annotation(root, "notice", "n", attaches=("toc:chI.1",))
    annotation(root, "supplement", "s", attaches=("toc:chI.1",))
    html = make().get("/edition/page/1-024").text
    assert -1 < html.find("class='ann notice") < html.find("<article>")
    supp = html.find("class='ann supplement")
    assert html.find("Still names.") < supp < html.find("Of drinks.")


def test_blocks_at_one_place_keep_their_order():
    from harness import edition_ui as ui

    html = ('<p>a</p><span class="milestone anchor section" id="x"></span>'
            '<p>b</p>')
    marks = ui.section_marks(html, {"chI.1": "x"}, {"chI": 1, "chI.1": 2})
    blocks = [{"id": i, "toc": ["chI.1"]} for i in ("one", "two", "three")]
    out, top, bottom = ui.place_annotations(
        html, blocks, [], marks, {"chI": 1, "chI.1": 2},
        lambda bs: "".join(f"[{b['id']}]" for b in bs))
    assert (top, bottom) == ([], [])
    assert out.index("[one]") < out.index("[two]") < out.index("[three]")
    assert out.index('id="x"') < out.index("[one]") < out.index("<p>b</p>")


def test_the_views_own_division_is_left_to_the_caller():
    """A chapter shown whole sets its own blocks above and below the text, after
    its footnotes; splicing one at the body's end would put it above them."""
    from harness import edition_ui as ui

    html = '<h2 class="milestone chapter" id="i-one">One</h2><p>a</p>'
    levels = {"chI": 1}
    marks = ui.section_marks(html, {"chI": "i-one"}, levels)
    b = {"id": "s", "toc": ["chI"]}
    out, _, bottom = ui.place_annotations(html, [], [b], marks, levels,
                                          lambda bs: "[s]", keep={"chI"})
    assert out == html and bottom == [b]


def test_an_attached_section_links_to_its_heading_not_its_leaf(client):
    """The "attached to" row goes where a ToC link goes: the chapter, at the
    heading's fragment. A bare `/page/` drops the reader above the heading."""
    root, make = client
    (root / "edition" / "toc.json").write_text(TWO_SECTIONS, encoding="utf-8")
    page(root, "1-023",
         '<pb n="3"/><milestone unit="section" n="chI.1"/><p>Of names.</p>')
    annotation(root, "supplement", "s", attaches=("toc:chI.1",))
    html = make().get("/edition/annotation/supplement:s").text
    assert "#names" in html, "the row names the heading's fragment"
    assert "/edition/page/1-023'" not in html and '/edition/page/1-023"' not in html


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
    html = make().get("/edition/partial/entity/place:markova").text
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
        "status",                     # a pill when proposed; settled is quiet
        "used_links",                 # the parse-time cross-check, not a field
        "dir_class", "stem", "path",  # filesystem facts `load` adds
        "summary", "full", "links",   # rendered as HTML, not as raw text
    }
    for key, value in rec.items():
        if key in shown_elsewhere or not isinstance(value, str) or not value:
            continue
        assert value in html, f"{key} is parsed and never shown"
