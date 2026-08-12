"""The reading view: the renderer, and the server that writes the store.

Two things worth pinning. The renderer must show what the file says is unfinished
— an edition that tidies away an open question presents a draft as finished, and
that is the failure this whole project is arranged against. And the server writes
`entities/` without `--commit`, on the `zones edit` precedent, so what has to be
true is that it cannot leave the store in a state `entity check` rejects.
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

import pytest
from markupsafe import escape
from test_entities import entry

from harness import edition_ui, langs, speech, tei_html
from harness.entities import ENTITY_CLASSES

TEI_NS = "http://www.tei-c.org/ns/1.0"
CSS = Path(__file__).resolve().parent.parent / "web" / "static" / "css" / "edition.css"


def page(root: Path, ref: str, body: str) -> Path:
    p = root / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>t</title>'
        f"</titleStmt><publicationStmt><p>p</p></publicationStmt>"
        f"<sourceDesc><p>s</p></sourceDesc></fileDesc></teiHeader>"
        f"<text><body>{body}</body></text></TEI>", encoding="utf-8")
    return p


def draft(root: Path, ref: str, body: str) -> Path:
    """The same page in `mz/tei/` — what `tei generate` would have left. Written
    by naming the store, which is the only way anything reaches it: `tei/` is
    never a farm of links over this one (`test_layout.py`)."""
    p = root / "mz" / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>t</title>'
        f"</titleStmt><publicationStmt><p>p</p></publicationStmt>"
        f"<sourceDesc><p>s</p></sourceDesc></fileDesc></teiHeader>"
        f"<text><body>{body}</body></text></TEI>", encoding="utf-8")
    return p


def render(root: Path, body: str) -> dict:
    return tei_html.render(page(root, "1-021", f'<pb n="1"/>{body}'))


# ------------------------------------------------------------- the renderer

def test_prose_becomes_prose(tmp_path):
    got = render(tmp_path, "<p>They went to Markova.</p>")
    assert got["ok"] and "<p>They went to Markova.</p>" in got["html"]


def test_the_folio_is_reported(tmp_path):
    assert render(tmp_path, "<p>x</p>")["folio"] == "1"


def test_an_entity_link_is_a_link_with_its_ref(tmp_path):
    """A link and not a button: it has a URL that works on its own, so middle-click
    and open-in-new-tab keep doing what a reader expects."""
    got = render(tmp_path, '<p><rs ref="place:markova" resp="#mz">M</rs></p>')
    assert 'href="/edition/entity/place:markova"' in got["html"]
    assert got["refs"] == ["place:markova"]


def test_an_entity_reference_over_a_tier1_handle_is_one_anchor(tmp_path):
    """**The bug this pins renders perfectly and breaks only in a browser.** The
    generator encloses a Tier-1 handle in `<rs>` rather than reaching into it,
    and the handle renders as a link into the lexicon — so both were emitting an
    `<a>`, one inside the other. HTML has no anchor inside an anchor: the parser
    closes the outer one, so the entity link was discarded and every linked
    native toponym read as a lexicon entry. Nothing in the markup said so.

    The entity link is the one that survives. The handle keeps its class and
    `data-key`, so it is still styled as Tier-1 and still previewable, and the
    card it opens is where its lexicon entry is reachable."""
    got = render(tmp_path,
                 '<p><rs ref="place:uelen" resp="#mz">'
                 '<foreign xml:lang="ckt" resp="#gt">Uweˊlen</foreign>'
                 "</rs></p>")
    html = got["html"]
    assert 'href="/edition/entity/place:uelen"' in html
    assert "/edition/lexicon/" not in html
    assert 'data-key="Uweˊlen"' in html          # still a known form
    assert not re.search(r"<a\b[^>]*>(?:(?!</a>).)*<a\b", html, re.S)
    # And the form is still counted, so the lexicon's census does not move.
    assert "Uweˊlen" in got["forms"]


def test_a_tier1_handle_outside_an_entity_reference_still_links_to_the_lexicon(tmp_path):
    got = render(tmp_path,
                 '<p><foreign xml:lang="ckt" resp="#gt">Kuluˊči</foreign></p>')
    assert "/edition/lexicon/" in got["html"]


def test_an_unsettled_rank_is_marked_and_a_settled_one_is_not(tmp_path):
    """The audit affordance. `#llm` and `#mz` are readings nobody has ratified, and
    an edition that showed them identically to `#ed` would be asserting a
    confidence the file does not carry."""
    unsettled = render(tmp_path, '<p><rs ref="a:b" resp="#mz">M</rs></p>')["html"]
    settled = render(tmp_path, '<p><rs ref="a:b" resp="#ed">M</rs></p>')["html"]
    assert "unsettled" in unsettled and "unsettled" not in settled


def test_an_editorial_comment_survives_as_a_flag(tmp_path):
    """A collator's unanswered question is *in* the file and is the honest state of
    the page. Hiding it in the rendering would make an unfinished page look
    finished."""
    got = render(tmp_path, "<p>x<!-- entity candidate: 'Chukchee' -->y</p>")
    assert 'class="flag question"' in got["html"]


def test_a_note_becomes_a_marker_and_a_body(tmp_path):
    got = render(tmp_path, '<p>x<note n="1" place="bottom">See Boas.</note></p>')
    assert 'class="noteref"' in got["html"]
    assert got["notes"][0]["n"] == "1" and "See Boas." in got["notes"][0]["html"]


def test_an_unfilled_handle_is_shown_as_one(tmp_path):
    """The gate refuses a lang-less <foreign>, so one here means the page was
    committed with a question open. Rendering nothing would hide that."""
    got = render(tmp_path, '<p><foreign index="1"/></p>')
    assert 'class="flag question"' in got["html"]


def test_a_page_that_will_not_parse_costs_that_page_and_not_the_server(tmp_path):
    p = tmp_path / "tei" / "chukchi-1-021.xml"
    p.parent.mkdir(parents=True)
    p.write_text("<TEI><body>", encoding="utf-8")
    got = tei_html.render(p)
    assert not got["ok"] and got["why"]


def test_markup_in_the_source_text_is_escaped(tmp_path):
    got = render(tmp_path, "<p>a &lt;script&gt; tag</p>")
    assert "<script>" not in got["html"] and "&lt;script&gt;" in got["html"]


def test_a_crop_is_all_ratios(tmp_path):
    """A crop scaled to a fixed pixel width keeps that width inside a panel that is
    almost never that wide, and the right-hand end of every crop is lost. The Moll
    reader had the pixel version first."""
    css = tei_html.crop_style((100, 200, 300, 400), (1000, 2000), pad=0)
    assert css["outer"] == "aspect-ratio:200/200"
    assert "%" in css["inner"] and "px" not in css["inner"]


def test_a_tier1_form_becomes_a_lexicon_link(tmp_path):
    """A reader meeting a keyed Chukchi word wants somewhere to put it.

    **The key is the bare form**, not `lang:form` as it was: the lexicon's
    identity carries no language, because a form only becomes `ckt` when a
    collator judges it. The language rides as `lang=` and decides nothing about
    which card opens."""
    got = render(tmp_path, '<p><foreign xml:lang="ckt" resp="#ed">Uweˊlen</foreign></p>')
    assert 'class="tier1 lex' in got["html"] and "lang=\"ckt\"" in got["html"]
    assert "ckt%3A" not in got["html"]
    assert got["forms"] == [unicodedata.normalize("NFD", "Uweˊlen")]


def test_an_unjudged_handle_links_the_same_word_to_the_same_card(tmp_path):
    """**A generated page links too.** The handle's glyphs came off adjudicated
    ground truth and are as settled as the collated page's; the only thing
    missing is the language, which the lexicon does not key on. So a reader
    meets the same card whether or not the page has been collated — which is
    most of the book, for a long while yet."""
    judged = render(tmp_path,
                    '<p><foreign xml:lang="ckt" resp="#ed">Uweˊlen</foreign></p>')
    draft = render(tmp_path, '<p><foreign index="1">Uweˊlen</foreign></p>')
    assert 'class="tier1 lex' in draft["html"]
    assert judged["forms"] == draft["forms"]
    assert "lang=" not in draft["html"]


def test_a_langless_span_without_a_handle_is_not_a_lexicon_link(tmp_path):
    """The discriminator is `@index` and not "has no language". The detector
    fires on a combining diaeresis exactly as on a Chukchee form, so a rule
    linking every lang-less `<foreign>` would reach ordinary German the moment
    one arrived unmarked."""
    got = render(tmp_path, "<p><foreign>Döring</foreign></p>")
    assert "lex" not in got["html"] and got["forms"] == []


def test_a_non_tier1_foreign_is_not_a_lexicon_link(tmp_path):
    """German in an English sentence is a foreign span, not a form this edition
    keys. A link would promise an entry that could never exist."""
    got = render(tmp_path, '<p><foreign xml:lang="de">Döring</foreign></p>')
    assert "lex" not in got["html"]


def test_a_lexicon_key_is_nfd(tmp_path):
    """The corpus is NFD, so the key has to be — otherwise the same word reached
    from two pages would open two cards."""
    got = render(tmp_path, '<p><foreign xml:lang="ckt" resp="#ed">'
                           + unicodedata.normalize("NFC", "ré") + "</foreign></p>")
    assert got["forms"] == [unicodedata.normalize("NFD", "ré")]


# --------------------------------------------------------- authored markup

def test_an_entry_names_another_in_double_brackets(tmp_path):
    """Bare `person:jochelson` in prose was unclickable and, worse,
    indistinguishable from prose that merely mentions the shape of an id."""
    store = {"person:x": {"canonical": "Waldemar X"}}
    got = edition_ui.gloss_html("worked with [[person:x]] there", store)
    assert 'href="/edition/entity/person:x"' in got and "Waldemar X" in got


def test_a_gloss_is_escaped_before_anything_else(tmp_path):
    got = edition_ui.gloss_html("a <script>alert(1)</script> tag", {})
    assert "<script>" not in got and "&lt;script&gt;" in got


def test_a_gloss_becomes_paragraphs_and_not_preformatted_text(tmp_path):
    """The records are hard-wrapped at 79 columns for editing. Rendering that
    wrapping in a panel of a different width was reproducing an editing artifact
    as if it were the author's line breaks."""
    got = edition_ui.gloss_html("one line\nwrapped here\n\nsecond para", {})
    assert got.count("<p>") == 2
    assert "<br" not in got


def test_a_gloss_may_be_written_as_a_list(tmp_path):
    """`entities/people/eskimo.md` was written with a list before one rendered,
    so the card showed a paragraph of literal `- ` lines. An author writing
    markdown in a markdown file is not a mistake to be trained out."""
    got = edition_ui.gloss_html("three groups:\n\n- one\n- two\n- three", {})
    assert got.count("<li>") == 3
    assert "<ul>" in got and got.count("<p>") == 1
    assert "- one" not in got


def test_a_wrapped_bullet_stays_one_item(tmp_path):
    """Deciding per line would open a `<ul>` around a paragraph that happens to
    wrap onto a dash, and split every bullet the records hard-wrap."""
    got = edition_ui.gloss_html("- one item that runs\n  onto a second line\n- two", {})
    assert got.count("<li>") == 2
    assert "runs onto a second line" in got


def test_a_gloss_may_link_out_and_only_over_http(tmp_path):
    """The allowlist is the point of escaping first: `escape()` fixes the *text*
    of an attribute and says nothing about its scheme, so `javascript:` in an
    `href` walks straight past it."""
    got = edition_ui.gloss_html("see [Eskaleut](https://en.wikipedia.org/wiki/E)", {})
    assert 'href="https://en.wikipedia.org/wiki/E"' in got
    assert 'rel="noopener noreferrer"' in got and "Eskaleut" in got

    bad = edition_ui.gloss_html("see [click](javascript:alert(1))", {})
    assert "<a" not in bad and "javascript" in bad   # shown, never linked


def test_a_gloss_takes_strong_before_em(tmp_path):
    """`*em*` tried first would eat the leading asterisk of each pair and leave
    a stray one either side."""
    got = edition_ui.gloss_html("**bold** and *italic*", {})
    assert "<strong>bold</strong>" in got and "<em>italic</em>" in got
    assert "*" not in got


def test_the_search_index_still_sees_text_and_not_markup(tmp_path):
    """A list and a link are new elements in the haystack `/search` greps, and
    a query for a word inside one must still find it."""
    html = edition_ui.gloss_html("- see [Anadyr](https://example.org/a) basin", {})
    assert "Anadyr basin" in edition_ui.strip_markup(html)


def test_a_link_row_holds_an_identifier_and_not_a_url(tmp_path):
    """`wikipedia:Chukchi_people`, so the store holds what the thing *is* and the
    address lives in one place. A site that moves its paths costs one line."""
    got = edition_ui.link_html("wikipedia:Chukchi_people")
    assert "https://en.wikipedia.org/wiki/Chukchi_people" in got
    assert "/static/site/wikipedia.svg" in got and 'target="_blank"' in got.replace("'", '"')


def test_an_unknown_link_kind_is_shown_rather_than_dropped(tmp_path):
    got = edition_ui.link_html("doi:10.1234/x")
    assert "doi:10.1234/x" in got


# ------------------------------------------------------------- the server

#: Set by the `server` fixture; `get`/`post` reach for it.
_CLIENT = None


@pytest.fixture
def server(tmp_path):
    """The app over a `TestClient`.

    This was a real server on a real port: a daemon thread, a hardcoded 8799,
    and a loop that polled `/` up to two hundred times waiting for it to answer.
    None of that tested anything — the invariants that *are* about a socket
    (loopback binding, refusing a held port) are `test_web_shell.py`'s, against
    `bind()` itself, which is where they live.
    """
    global _CLIENT
    entry(tmp_path, "place:markova", status="proposed",
          aliases=[("Markova", True)])
    page(tmp_path, "1-021", '<pb n="1"/><p>At '
         '<rs ref="place:markova" resp="#mz">Markova</rs>.</p>')

    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    _CLIENT = TestClient(
        create_app(tmp_path, Sessions(root=tmp_path), editor="edition"))
    # The base is the mount prefix rather than a host: the four tools share one
    # app, and every route this suite names is the reading view's.
    yield "/edition", tmp_path
    _CLIENT = None


class HTTPError(Exception):
    """Carries the status in its message, so `pytest.raises(...)` matching on
    `"404"` reads the same as it did against `urllib`."""


def _client():
    """The fixture's client, or a clear failure.

    `_CLIENT` is module state so `get`/`post` keep the signatures the tests were
    written against; this is what stops "outside the fixture" showing up as an
    AttributeError on None three frames away.
    """
    assert _CLIENT is not None, "get/post used outside the `server` fixture"
    return _CLIENT


def get(url: str) -> str:
    r = _client().get(url)
    if r.status_code >= 400:
        raise HTTPError(f"HTTP {r.status_code} for {url}")
    return r.text


def post(url: str, obj) -> dict:
    r = _client().post(url, json=obj)
    if r.status_code >= 400:
        raise HTTPError(f"HTTP {r.status_code} for {url}")
    return r.json()


def test_the_index_lists_collated_pages(server):
    base, _ = server
    assert "1-021" in get(base + "/")


def test_a_page_renders_with_its_link(server):
    base, _ = server
    assert 'data-ref="place:markova"' in get(base + "/page/1-021")


def test_an_uncollated_page_says_so_rather_than_showing_the_baseline(server):
    """`mz/tei/` is a draft nobody has read, and an end-user preview is the last
    place it belongs."""
    base, _ = server
    with pytest.raises(Exception) as e:
        get(base + "/page/2-999")
    assert "404" in str(e.value)


def test_a_ref_shaped_like_a_path_is_refused(server):
    base, _ = server
    with pytest.raises(Exception) as e:
        get(base + "/page/..%2F..%2Fetc%2Fpasswd")
    assert "404" in str(e.value)


def test_a_page_carries_its_neighbours_at_both_ends(server):
    """A page is a screenful or several, and a reader who has got to the bottom
    should not have to go back up to leave. Two copies, and **no `id` on either**
    — they used to be `id='prev-page'`/`'next-page'`, which two copies would make
    invalid, with `getElementById` silently answering with the first."""
    base, root = server
    for r in ("1-020", "1-022"):
        page(root, r, '<pb n="1"/><p>x</p>')
    body = get(base + "/page/1-021")
    assert body.count("class='neighbours'") == 2
    assert "prev-page" not in body and "next-page" not in body
    assert body.count("page-prev") == 2 and body.count("page-next") == 2


def test_a_page_with_no_neighbour_carries_no_block_at_either_end(server):
    """The `{% if prev or next %}` guard lives in the macro, so it is written
    once and cannot come apart between the two call sites."""
    base, _ = server
    assert "class='neighbours'" not in get(base + "/page/1-021")


def test_the_neighbours_claim_no_tabindex(server):
    """They held 1 and 2 while `tei_html` numbered the text's own links from 3 —
    one number in three files. Worse, `edition.js` counted the anchors and then
    addressed them by attribute value, so the first or last page of any listing,
    which has only one neighbour, left a gap: the count fell one short of the
    highest live index and the last link on the page could not be reached. The
    arrow keys go to a neighbour directly; the up/down walk is for the text."""
    base, root = server
    page(root, "1-022", '<pb n="1"/><p>x</p>')
    body = get(base + "/page/1-021")
    assert "class='neighbours'" in body
    assert 'tabindex="1"' not in body and 'tabindex="2"' not in body


def test_every_entity_class_has_exactly_one_link_colour():
    """`ENTITY_CLASSES` is the authority, the corpus header's `prefixDef` set is a
    second copy held to it by `harness tei header`, and the stylesheet is a third.
    A class added there and forgotten here would fall back to the accent silently,
    which is indistinguishable from one deliberately left at the default; a class
    named in two families would take whichever rule came last."""
    css = CSS.read_text(encoding="utf-8")
    for cls in ENTITY_CLASSES:
        assert css.count(f'[data-ref^="{cls}:"]') == 1, cls


def test_every_link_colour_is_defined_in_both_themes():
    """The drift far likelier than a missing class: a token added to `:root` and
    not to the dark block inherits the light value, and a colour code that holds
    in one theme only is worse than none."""
    css = CSS.read_text(encoding="utf-8")
    for token in ("--flora", "--abstract", "--lex", "--basin", "--hi"):
        assert len(re.findall(rf"{token}\s*:", css)) == 2, token


def test_an_entry_that_can_be_drawn_arrives_with_its_map(server):
    """Reaching an entry and then having to ask for the map made the geography an
    optional extra, and it is not — `within:` is half of what an entry says about
    a place. The pane is what carries it: there is only ever one *here*, and a map
    that could be pushed out of sight by the next three cards was answering a
    question nobody had stopped asking."""
    base, root = server
    entry(root, "place:uelen", extra="- geo: 66.16 -169.8\n")
    body = get(base + "/entity/place:uelen")
    assert "id='map-pane'" in body and "<svg class='map" in body
    assert "data-ent='place:uelen'" in body   # the pin, for the highlight


def test_an_entry_with_nothing_to_draw_opens_no_pane(server):
    """Chuvan, Kerek, Siberian Yupik and Tundra Yukaghir are the live cases. An
    empty pane saying so would be a second statement of what the card's own
    `contains`/`within` rows already do not claim."""
    base, _ = server
    assert "id='map-pane'" not in get(base + "/entity/place:markova")


def test_the_fragment_the_stack_and_the_preview_use_carries_no_map(server):
    """A hover preview and a card in the stack are both read *while* the pane is
    showing the geography. A second copy inside the card would answer a question
    nothing was asking, and cost a map render per hover."""
    base, root = server
    entry(root, "place:uelen", extra="- geo: 66.16 -169.8\n")
    bare = get(base + "/entity/place:uelen?partial=1")
    assert "Uelen" in bare
    assert "<svg" not in bare and "map-pane" not in bare


def test_the_page_view_ships_the_pane_shut_and_the_stack_apart_from_it(server):
    """`edition.js` indexes `STACK.childNodes` as cards — selected, surfaced,
    pinned, deleted. A pane among them would be all four."""
    base, _ = server
    body = get(base + "/page/1-021")
    assert "id='map-pane' hidden" in body
    assert "id='stack'" in body


def test_the_entity_panel_is_the_same_content_bare(server):
    """One template, wrapped or bare, so a permalink and a click land identically."""
    base, _ = server
    whole = get(base + "/entity/place:markova")
    bare = get(base + "/entity/place:markova?partial=1")
    assert "<main" in whole and "<main" not in bare
    assert "Markova" in bare


def test_an_entity_card_says_where_it_is_mentioned(server):
    """The card named exactly one page — `since:`, an authored field — while the
    lexicon card beside it listed every printed line. A linked mention is one the
    page already carries an `@ref` for; an unlinked one is an alias hit nobody
    has resolved, and it arrives with the prose either side of it."""
    base, root = server
    page(root, "1-030", "<pb n='2'/><p>They wintered at Markova that year.</p>")
    body = get(base + "/entity/place:markova")

    assert "mentioned on 2 of 2 page(s), 2 time(s)" in body
    assert "1-021" in body and "1-030" in body
    assert "1 linked" in body                     # the 1-021 `<rs>`
    assert "<mark>Markova</mark>" in body         # the 1-030 alias hit
    assert "wintered at" in body                  # the window before it


def test_a_draft_mention_is_out_of_scope_until_drafts_is_on(server):
    """The sweep is over the whole readable corpus and the card is filtered to
    what the view is serving. Without `--drafts` a generated page 404s by design,
    so a row naming one would send a reader nowhere."""
    base, root = server
    draft(root, "1-040", "<pb n='3'/><p>Beyond Markova lies the pass.</p>")
    body = get(base + "/entity/place:markova")
    assert "1-040" not in body

    _CLIENT.app.state.drafts = True
    try:
        body = get(base + "/entity/place:markova")
        assert "1-040" in body and "draft" in body
    finally:
        _CLIENT.app.state.drafts = False


def test_no_mention_says_how_many_pages_it_looked_at(server):
    """A bare zero cannot be told from "never mentioned", and today it means one
    of two other things entirely — nothing collated, or `mz/tei/` not built."""
    base, root = server
    entry(root, "person:ghost", aliases=[("Nobody", True)])
    body = get(base + "/entity/person:ghost")
    assert "No mention found across the 1 page(s)" in body


def test_a_linked_mention_is_not_also_counted_unlinked(server):
    """The double-count `_unlinked_text` exists to stop: matching over the whole
    body reported the same number for a page where every instance was linked as
    for one where none was, which inverts what the column is for."""
    from harness.web import stores

    _, root = server
    got = stores.occurrences(root)["place:markova"]
    assert [r["ref"] for r in got["linked"]] == ["1-021"]
    assert got["unlinked"] == []
    # And the rank travels with the row rather than being read off the path.
    assert got["linked"][0]["rank"] == "collated"


def test_the_mention_list_is_capped_and_says_what_it_left_out(server):
    """A card is for sizing an entry up, not for reading the corpus through. What
    must not happen is the cap being silent — a truncated list reads as coverage
    — so the page count and the verb that prints the rest are both on the card."""
    from harness.web.edition import MENTIONS

    base, root = server
    for i in range(MENTIONS + 3):
        page(root, f"1-1{i:02}", f"<pb n='{i}'/><p>Past Markova, mile {i}.</p>")
    body = get(base + "/entity/place:markova")

    # `MENTIONS` rows, of which 1-021 sorts first and is the linked one.
    assert body.count("<mark>Markova</mark>") == MENTIONS - 1
    assert f"mentioned on {MENTIONS + 4} of {MENTIONS + 4} page(s)" in body
    assert f"and {4} more page(s)" in body
    assert "harness entity occurrences place:markova" in body


def test_several_mentions_on_one_page_are_one_row_with_a_count(server):
    """"Where does this appear" is a page question. Per-occurrence rows answered
    it badly: four hits on one page filled half the card with the same word."""
    base, root = server
    page(root, "1-030", "<pb n='2'/><p>Markova, and beyond Markova, and "
                        "past Markova again.</p>")
    body = get(base + "/entity/place:markova")

    assert "mentioned on 2 of 2 page(s), 4 time(s)" in body
    assert "3 unlinked" in body
    assert body.count(">1-030</a>") == 1


def test_the_encyclopedia_is_a_tree_over_the_whole_class_vocabulary(server):
    """**Every class, including the ones nothing is filed under.** Four of the
    eleven are empty today, and a list of only the populated ones would show half
    the vocabulary while looking complete — the silence the atlas's `absent` rows
    exist to break, one store over."""
    base, _ = server
    body = get(base + "/entities")
    for cls in ENTITY_CLASSES:
        assert f">{cls}</code>" in body, cls
    # The one populated class says how many; the empty ones say nothing is there.
    assert "(1)" in body and "(0)" in body


def test_the_encyclopedia_puts_proposed_entries_first(server):
    """It is named for an ordering and used to assert only that the words
    "awaiting audit" appeared — a substring of the count in the title bar, true
    whatever the order was and true if the list were empty. Proposed-first is now
    within a class, and this is what says so."""
    base, root = server
    entry(root, "place:anadyrsk", status="ratified", aliases=[("Anadyrsk", True)])
    body = get(base + "/entities")
    assert body.index("place:markova") < body.index("place:anadyrsk")
    assert "awaiting audit" in body


def test_the_encyclopedia_nests_a_people_inside_a_people(server):
    """`within:` is containment in general. The index stopped at two levels on
    the ground that nothing made a people a child of a people, which was already
    false — the Maritime and Reindeer Chukchi sit under the Chukchi, and the
    fact was visible only on the atlas, which will not draw a people."""
    base, root = server
    entry(root, "people:chukchi", aliases=[("Chukchi", True)])
    entry(root, "people:maritime-chukchi", extra="- within: people:chukchi\n")
    body = get(base + "/entities")

    parent = body.index("data-ref='people:chukchi'")
    child = body.index("data-ref='people:maritime-chukchi'")
    assert parent < child
    # Nested, not merely adjacent: a `<ul>` opens between the two.
    assert "<ul>" in body[parent:child]


def test_a_parent_in_another_class_does_not_nest(server):
    """Following the field across classes would file the rivers under *place*
    and leave *water* a list of orphans. Such a child sits at the top of its own
    class, where its card is what names the parent."""
    base, root = server
    entry(root, "place:chukotka", aliases=[("Chukotka", True)])
    entry(root, "water:anadyr", extra="- within: place:chukotka\n")
    body = get(base + "/entities")

    water = body.index(">water</code>")
    assert body.index("water:anadyr") > water
    # And it is not also drawn under `place`, which would show it twice.
    assert body.count("data-ref='water:anadyr'") == 1


def test_ratifying_writes_the_store(server):
    """The click is the human act — the `zones edit` precedent — and git is the
    witness. What it changes is what a rule may then link corpus-wide."""
    base, root = server
    assert post(base + "/ratify", {"id": "place:markova"}) == {"ok": True}
    assert "- status: ratified" in (
        root / "entities" / "place" / "markova.md").read_text(encoding="utf-8")


def test_a_write_that_would_break_the_store_is_rolled_back(server):
    """Every `@ref` in the corpus resolves against this store, so a browser that
    could leave it incoherent would break pages nobody is looking at."""
    base, root = server
    entry(root, "water:markova", aliases=[("Markova", True)])
    got = post(base + "/ratify", {"id": "place:markova"})
    assert "refused" in got.get("error", "")
    assert "- status: proposed" in (
        root / "entities" / "place" / "markova.md").read_text(encoding="utf-8")


def test_search_finds_the_text_and_the_encyclopedia(server):
    base, _ = server
    got = get(base + "/search?q=Markova")
    assert "in the text" in got and "in the encyclopedia" in got


def test_a_lexicon_card_says_that_nothing_stands_behind_it(server):
    """A card that admits what is missing is worth more than a link that goes
    nowhere — it is the same shape as every other unresolved thing here.

    What is missing narrowed when the store arrived: it used to be the whole
    lexicon, and now it is this form's note. The rest of the card is not empty
    and never was — the notation is phonetic, so the pronunciation follows by
    rule whether or not anybody has written a word."""
    base, _ = server
    got = get(base + "/lexicon/ckt%3AUwe%CB%8Alen?partial=1")
    assert "No editor's note" in got and "Chukchi" in got


def test_every_field_in_a_record_reaches_the_card(tmp_path):
    """**An entity file has no invisible fields.**

    A store a human hand-maintains whose values never reach the page is one
    where a wrong value is never noticed — the same failure as an unratified
    span rendered like a ratified one, one store over. `within:`, `geo:` and
    `area:` were all added to the parser before anything displayed them, which
    is what this gate is for: adding a field now fails here until it is either
    rendered by `_properties` or listed as shown elsewhere.
    """
    from harness import entities
    text = (tmp_path / "x.md")
    text.write_text(
        "# place:x — X\n\n- status: proposed\n- since: 1-021\n"
        "- within: place:y\n- geo: 66.0 170.0\n- area: watershed:anadyr\n"
        "- authority: k\n- link: wikidata:Q1\n\n## aliases\n\n"
        "| form | lang | auto | note |\n|---|---|---|---|\n| X | no | |\n\n"
        "## gloss\n\nx\n", encoding="utf-8")
    rec = entities.parse(text.read_text(encoding="utf-8"))
    covered = set(edition_ui.SHOWN_ELSEWHERE) | set(edition_ui.PROPERTY_FIELDS)
    assert set(rec) <= covered, f"nothing displays {sorted(set(rec) - covered)}"


def test_the_properties_block_shows_the_geography(tmp_path):
    """The three geography fields, on the card, where a reader can check them
    against the map beside it."""
    entry(tmp_path, "place:y", aliases=[("Y", False)])
    p = tmp_path / "entities" / "place" / "x.md"
    p.write_text("# place:x — X\n\n- status: ratified\n- since: 1-021\n"
                 "- within: place:y\n- geo: 66.0 170.0\n\n## aliases\n\n"
                 "| form | lang | auto | note |\n|---|---|---|---|\n\n## gloss\n\nx\n",
                 encoding="utf-8")
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    c = TestClient(create_app(tmp_path, Sessions(root=tmp_path), editor="edition"))
    got = c.get("/edition/entity/place:x?partial=1").text
    assert "within" in got and "66.0000, 170.0000" in got
    # The inverse too: a parent that could not list its own members would send
    # a reader to the atlas to find out what it holds.
    assert "contains" in c.get("/edition/entity/place:y?partial=1").text


def test_a_lexicon_card_carries_the_imputed_pronunciation(server):
    """Labelled `imputed`, and the label is not decoration: the IPA is a rule
    table's output and the audio is espeak with no Chukchi voice behind it, so
    the card is where a reader is told that rather than a doc nobody opens."""
    base, _ = server
    got = get(base + "/lexicon/ckt%3AUwe%CB%8Alen?partial=1")
    assert "/uːweːleːn/" in got
    assert "imputed" in got
    assert "class='speak'" in got


def test_a_partial_imputation_is_shown_and_names_what_it_could_not_read(server):
    """Withholding it would say the form is unpronounceable, when what is true
    is that no rule reaches one of its letters."""
    base, _ = server
    got = get(base + "/lexicon/ckt%3APo%C5%A1a?partial=1")
    assert "partial" in got and "no rule reaches" in got


@pytest.mark.skipif(shutil.which(speech.ESPEAK) is None,
                    reason="espeak-ng is not installed")
def test_the_speaker_endpoint_returns_a_wav(server):
    base, _ = server
    r = _client().get(base + "/tts/u%CB%90we%CB%90le%CB%90n")
    assert r.headers["content-type"] == "audio/wav"
    assert r.content[:4] == b"RIFF"


def test_the_atlas_lists_only_located_roots(server):
    """Without the scope every person and source in the store is an atlas root,
    and the tree becomes the encyclopedia index with worse navigation."""
    base, root = server
    entry(root, "person:nobody", aliases=[("Nobody", False)])
    got = get(base + "/atlas")
    assert "Nobody" not in got


def test_a_node_with_no_boundary_says_its_frame_is_a_frame(server):
    """No source draws Chukotka, and none should — it is tree structure. The
    map is computed from its members and captioned as such, because a frame is
    a viewport and not a claim."""
    base, root = server
    entry(root, "place:parent", aliases=[("P", False)])
    p = root / "entities" / "place" / "kid.md"
    p.write_text("# place:kid — Kid\n\n- status: ratified\n- since: 1-021\n"
                 "- within: place:parent\n- geo: 66.0 170.0\n\n## aliases\n\n"
                 "| form | lang | auto | note |\n|---|---|---|---|\n\n## gloss\n\nx\n",
                 encoding="utf-8")
    got = get(base + "/map/place%3Aparent?partial=1")
    assert "framed by what lies beneath it" in got and "<svg" in got


def test_an_entity_with_nowhere_to_put_says_so_rather_than_drawing_nothing(server):
    base, root = server
    entry(root, "person:nobody2", aliases=[("N", False)])
    assert "Nothing to draw" in get(base + "/map/person%3Anobody2?partial=1")


def test_a_string_with_nothing_speakable_in_it_is_a_400_not_a_crash(server):
    """The endpoint is a pure function of the URL and does not check that the
    IPA is one this edition imputed, so it has to answer for anything."""
    base, _ = server
    assert _client().get(base + "/tts/%E2%96%A1%E2%96%A1").status_code == 400


def test_a_key_nothing_answers_to_is_refused(server):
    """Refused on what the corpus knows, not on the key's shape. Any string
    could be a Tier-1 form, so there is nothing here to validate — and a card
    that rendered an arbitrary one as a headword, with an imputed pronunciation
    under it, would be inventing a word."""
    base, _ = server
    assert "Nothing in the lexicon" in get(base + "/lexicon/xx%3Afoo?partial=1")
    assert "Nothing in the lexicon" in get(base + "/lexicon/notaform?partial=1")


def test_the_site_marks_are_served(server):
    base, _ = server
    assert "<svg" in get(base + "/static/wikipedia.svg")


def test_an_arbitrary_static_path_is_refused(server):
    base, _ = server
    with pytest.raises(Exception) as e:
        get(base + "/static/..%2F..%2Fetc%2Fpasswd")
    assert "404" in str(e.value)


# --- the generated store, shown on purpose and marked wherever it shows -------
#
# `--drafts` turns the reading view into a workstation over `mz/tei/` while the
# generator is being fixed. Two things are under test throughout: that a draft is
# reachable *only* when the operator asked for it, and that when it is reachable
# it never passes for collated text. The second is the one that matters — the
# store this repo already lost was lost because a file's role lived somewhere
# other than the file.


def _app(root, drafts: bool):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app
    return TestClient(create_app(root, Sessions(root=root), editor="edition",
                                 drafts=drafts))


def test_page_source_prefers_the_signed_page_and_says_which_it_gave(tmp_path):
    """Rank comes back with the path, so a caller cannot hold one without the
    other. `page_path` alone is what let a symlinked draft answer to a signed
    page's name."""
    page(tmp_path, "1-021", "<p>signed</p>")
    draft(tmp_path, "1-021", "<p>generated</p>")
    draft(tmp_path, "1-022", "<p>generated</p>")

    p, rank = tei_html.page_source("1-021", tmp_path)
    assert rank == "collated" and p.read_text(encoding="utf-8").count("signed")
    p, rank = tei_html.page_source("1-022", tmp_path)
    assert rank == "draft" and "mz" in p.parts
    assert tei_html.page_source("1-099", tmp_path) == (None, "absent")


def test_readable_is_the_union_and_collated_is_not(tmp_path):
    page(tmp_path, "1-021", "<p>a</p>")
    draft(tmp_path, "1-021", "<p>a</p>")
    draft(tmp_path, "1-005", "<p>b</p>")
    # Scan order, and the page in both stores counted once.
    assert tei_html.readable(tmp_path) == ["1-005", "1-021"]
    assert tei_html.collated(tmp_path) == ["1-021"]


def test_a_draft_is_not_served_unless_it_was_asked_for(tmp_path):
    """Default is the reader's view. The 404 names the flag rather than saying
    only "not collated", because the page does exist and the operator is
    otherwise left guessing whether the generator ever ran."""
    draft(tmp_path, "1-022", "<pb n='2'/><p>generated</p>")
    r = _app(tmp_path, drafts=False).get("/edition/page/1-022")
    assert r.status_code == 404
    assert "--drafts" in r.text


def test_a_draft_is_served_marked_when_it_was(tmp_path):
    draft(tmp_path, "1-022", "<pb n='2'/><p>generated</p>")
    r = _app(tmp_path, drafts=True).get("/edition/page/1-022")
    assert r.status_code == 200
    assert "generated" in r.text and "draft-tag" in r.text


def test_a_signed_page_is_never_marked_a_draft(tmp_path):
    """The mark has to be false of collated pages or it says nothing about the
    ones it appears on."""
    page(tmp_path, "1-021", "<pb n='1'/><p>signed</p>")
    draft(tmp_path, "1-021", "<pb n='1'/><p>generated</p>")
    r = _app(tmp_path, drafts=True).get("/edition/page/1-021")
    assert "signed" in r.text and "generated" not in r.text
    assert "draft-tag" not in r.text


def test_the_listing_marks_the_drafts_and_counts_the_two_apart(tmp_path):
    page(tmp_path, "1-021", "<p>signed</p>")
    draft(tmp_path, "1-022", "<p>generated</p>")
    body = _app(tmp_path, drafts=True).get("/edition/").text
    assert "1 collated" in body and "1 machine draft" in body
    assert body.count("draft-tag") >= 2      # the legend, and the one row


def test_search_reaches_exactly_what_the_listing_does(tmp_path):
    """A page reachable at its own URL and absent from search is the worse of the
    two lies. With drafts off the hit must not appear at all."""
    draft(tmp_path, "1-022", "<pb n='2'/><p>walrus</p>")
    # On the hit row, not on the word: the query echoes in the page title, so
    # "walrus" is in the response either way.
    off = _app(tmp_path, False).get("/edition/search?q=walrus").text
    assert "/edition/page/1-022" not in off and "Nothing found" in off
    on = _app(tmp_path, True).get("/edition/search?q=walrus").text
    assert "/edition/page/1-022" in on and "draft-tag" in on


def test_attestations_never_come_from_a_draft(tmp_path):
    """An attestation says a form was read in a language on a page. Nothing has
    read a generated page, so it cannot witness one — whatever the server was
    started with, since this is not the server's call to make.

    The invariant outlived its first implementation. This used to be a per-form
    walk in `edition_ui`, which is one parse of every collated page *per form
    asked about*; the index that replaced it sweeps once, and had to inherit the
    rule rather than restate it — so the assertion moved with it and the old
    reader is gone."""
    from harness.web import stores

    form = unicodedata.normalize("NFD", "mêˊmêl")
    draft(tmp_path, "1-022",
          '<pb n="2"/><p><foreign xml:lang="ckt">mêˊmêl</foreign></p>')
    assert stores.attestations(tmp_path).get(form) is None
    page(tmp_path, "1-021",
         '<pb n="1"/><p><foreign xml:lang="ckt">mêˊmêl</foreign></p>')
    assert stores.attestations(tmp_path)[form] == [("1-021", "ckt")]


# --- the lexicon, which does not wait on collation ----------------------------
#
# Americanist notation is phonetic: a form's sound follows from the notation by
# rule, without anyone knowing what language it is in. So the reading view can
# stand a lexicon up on adjudicated ground truth today, with the language and the
# printed gloss arriving later from collated TEI as two more derived facts. These
# hold that direction — the card is worth reading *before* an editor has written
# anything, and what an entry adds is the one thing nothing derives.

REPO = Path(__file__).resolve().parent.parent.parent
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _gt(root: Path, ref: str, lines: list[str]) -> None:
    """A ground-truth page, plus the committed fold table `lookup.index` needs.

    The real `data/marks_config.json` and not a copy of one: the fold is what
    decides whether two settings are one word, and a test writing its own would
    be asserting against a table nothing in the corpus uses.
    """
    (root / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "data" / "marks_config.json", root / "data")
    p = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<TextLine ID="l{i}" HPOS="400" VPOS="{300 + i * 60}" WIDTH="1774" '
        f'HEIGHT="50"><String CONTENT="{unicodedata.normalize("NFD", t)}"/>'
        "</TextLine>" for i, t in enumerate(lines))
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
        f'<TextBlock ID="b1">{body}</TextBlock>'
        "</PrintSpace></Page></Layout></alto>", encoding="utf-8")


def test_an_unwritten_unjudged_form_still_renders_a_card(server):
    """**The load-bearing one.** No entry, no collated page, no language — and
    the card still carries the imputed pronunciation and the lines the form was
    printed on, because all three are derived from stores that already exist."""
    base, root = server
    _gt(root, "1-042", ["south of Kuluˊči Bay lies the", "second settlement"])
    got = get(base + "/lexicon/Kulu'c^i?partial=1")
    assert "language unjudged" in got
    assert "south of" in got and "1-042" in got
    assert "No editor's note" in got


def test_all_three_key_forms_reach_the_same_card(server):
    """The handle key is canonical because it is ASCII and half the length; the
    exact form works because that is what `data-key` holds; `lang:form` works
    because a URL somebody wrote down should not stop resolving."""
    base, root = server
    _gt(root, "1-042", ["south of Kuluˊči Bay lies the"])
    from urllib.parse import quote
    form = unicodedata.normalize("NFD", "Kuluˊči")
    for key in ("Kulu'c^i", form, f"ckt:{form}"):
        got = get(base + "/lexicon/" + quote(key, safe="") + "?partial=1")
        assert "south of" in got, key


def test_an_ambiguous_handle_key_refuses_and_names_the_candidates(server):
    """`handle_key` is non-injective by design — `marks.py` says the marker
    classes collide on purpose — so picking one of two forms would resolve the
    corpus's own ambiguity by an accident of iteration order.

    `ᵋ` U+1D4B and `ᵉ` U+1D49 are the real pair: both key to `e^`, and both are
    inventory glyphs, so two forms differing only in which one they carry are
    two words with one address."""
    base, root = server
    _gt(root, "1-042", ["the keᵋlin here", "and the keᵉlin there"])
    got = get(base + "/lexicon/kee%5Elin?partial=1")
    assert "more than one form" in got
    assert unicodedata.normalize("NFD", "keᵋlin") in got
    assert unicodedata.normalize("NFD", "keᵉlin") in got


def test_the_key_is_case_sensitive_where_a_filename_could_not_be(server):
    """`Aiˊwan` and `aiˊwan` are both this corpus's and key to `Ai'wan` and
    `ai'wan`. A URL keeps them apart; the filesystem the store is *filed* on may
    not, which is why the slug is authored and the key is only the address."""
    base, root = server
    _gt(root, "1-042", ["the Aiˊwan came", "and the aiˊwan went"])
    upper = get(base + "/lexicon/Ai'wan?partial=1")
    lower = get(base + "/lexicon/ai'wan?partial=1")
    assert "more than one form" not in upper
    assert unicodedata.normalize("NFD", "Aiˊwan") in upper
    assert unicodedata.normalize("NFD", "aiˊwan") in lower


def test_the_index_lists_every_language_and_the_unjudged(server):
    """Every one of the seven codes whether or not it holds anything, on the
    class tree's reasoning — and *unassigned* last, which is where nearly
    everything sits until collation reaches it."""
    base, root = server
    _gt(root, "1-042", ["south of Kuluˊči Bay lies the"])
    got = get(base + "/lexicon")
    # Escaped, because the names carry apostrophes — the page is autoescaped and
    # asserting against the raw string would be testing the wrong bytes.
    for name in langs.TIER1_NAMES.values():
        assert escape(name) in got
    assert "unassigned" in got.lower()
    assert unicodedata.normalize("NFD", "Kuluˊči") in got


def test_an_editors_note_reaches_the_card(server):
    base, root = server
    _gt(root, "1-042", ["south of Kuluˊči Bay lies the"])
    (root / "lexicon").mkdir()
    (root / "lexicon" / "kulu-c-i.md").write_text(
        "# Kuluˊči\n\n- status: proposed\n- since: 1-042\n\n"
        "## editor's note\n\nA bay on the [[place:markova]] side.\n",
        encoding="utf-8")
    got = get(base + "/lexicon/Kulu'c^i?partial=1")
    assert "A bay on the" in got
    assert "No editor's note" not in got
