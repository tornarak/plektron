"""The reading view: the renderer, and the server that writes the store.

Two things worth pinning. The renderer must show what the file says is unfinished
— an edition that tidies away an open question presents a draft as finished, and
that is the failure this whole project is arranged against. And the server writes
`entities/` without `--commit`, on the `zones edit` precedent, so what has to be
true is that it cannot leave the store in a state `entity check` rejects.
"""
from __future__ import annotations

import shutil
import unicodedata
from pathlib import Path

import pytest
from test_entities import entry

from harness import edition_ui, speech, tei_html

TEI_NS = "http://www.tei-c.org/ns/1.0"


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
    """A reader meeting a keyed Chukchi word wants somewhere to put it. The key is
    `lang:form` and names the form itself, because there is no lexicon store — the
    card it opens says so rather than pretending otherwise."""
    got = render(tmp_path, '<p><foreign xml:lang="ckt" resp="#ed">Uweˊlen</foreign></p>')
    assert 'class="tier1 lex' in got["html"]
    assert "ckt%3AUwe" in got["html"]
    assert got["forms"] == ["ckt:Uweˊlen"]


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
    assert got["forms"] == ["ckt:" + unicodedata.normalize("NFD", "ré")]


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
          triggers=[("Markova", True)])
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


def test_the_entity_panel_is_the_same_content_bare(server):
    """One template, wrapped or bare, so a permalink and a click land identically."""
    base, _ = server
    whole = get(base + "/entity/place:markova")
    bare = get(base + "/entity/place:markova?partial=1")
    assert "<main" in whole and "<main" not in bare
    assert "Markova" in bare


def test_the_encyclopedia_puts_proposed_entries_first(server):
    base, _ = server
    assert "awaiting audit" in get(base + "/entities")


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
    entry(root, "water:markova", triggers=[("Markova", True)])
    got = post(base + "/ratify", {"id": "place:markova"})
    assert "refused" in got.get("error", "")
    assert "- status: proposed" in (
        root / "entities" / "place" / "markova.md").read_text(encoding="utf-8")


def test_search_finds_the_text_and_the_encyclopedia(server):
    base, _ = server
    got = get(base + "/search?q=Markova")
    assert "in the text" in got and "in the encyclopedia" in got


def test_a_lexicon_card_says_that_nothing_stands_behind_it(server):
    """An empty card that admits it is empty is worth more than a link that goes
    nowhere — it is the same shape as every other unresolved thing here."""
    base, _ = server
    got = get(base + "/lexicon/ckt%3AUwe%CB%8Alen?partial=1")
    assert "No lexicon entry" in got and "Chukchi" in got


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
        "- authority: k\n- link: wikidata:Q1\n\n## triggers\n\n"
        "| form | auto | note |\n|---|---|---|\n| X | no | |\n\n"
        "## gloss\n\nx\n", encoding="utf-8")
    rec = entities.parse(text.read_text(encoding="utf-8"))
    covered = set(edition_ui.SHOWN_ELSEWHERE) | set(edition_ui.PROPERTY_FIELDS)
    assert set(rec) <= covered, f"nothing displays {sorted(set(rec) - covered)}"


def test_the_properties_block_shows_the_geography(tmp_path):
    """The three geography fields, on the card, where a reader can check them
    against the map beside it."""
    entry(tmp_path, "place:y", triggers=[("Y", False)])
    p = tmp_path / "entities" / "place" / "x.md"
    p.write_text("# place:x — X\n\n- status: ratified\n- since: 1-021\n"
                 "- within: place:y\n- geo: 66.0 170.0\n\n## triggers\n\n"
                 "| form | auto | note |\n|---|---|---|\n\n## gloss\n\nx\n",
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
    entry(root, "person:nobody", triggers=[("Nobody", False)])
    got = get(base + "/atlas")
    assert "Nobody" not in got


def test_a_node_with_no_boundary_says_its_frame_is_a_frame(server):
    """No source draws Chukotka, and none should — it is tree structure. The
    map is computed from its members and captioned as such, because a frame is
    a viewport and not a claim."""
    base, root = server
    entry(root, "place:parent", triggers=[("P", False)])
    p = root / "entities" / "place" / "kid.md"
    p.write_text("# place:kid — Kid\n\n- status: ratified\n- since: 1-021\n"
                 "- within: place:parent\n- geo: 66.0 170.0\n\n## triggers\n\n"
                 "| form | auto | note |\n|---|---|---|\n\n## gloss\n\nx\n",
                 encoding="utf-8")
    got = get(base + "/map/place%3Aparent?partial=1")
    assert "framed by what lies beneath it" in got and "<svg" in got


def test_an_entity_with_nowhere_to_put_says_so_rather_than_drawing_nothing(server):
    base, root = server
    entry(root, "person:nobody2", triggers=[("N", False)])
    assert "Nothing to draw" in get(base + "/map/person%3Anobody2?partial=1")


def test_a_string_with_nothing_speakable_in_it_is_a_400_not_a_crash(server):
    """The endpoint is a pure function of the URL and does not check that the
    IPA is one this edition imputed, so it has to answer for anything."""
    base, _ = server
    assert _client().get(base + "/tts/%E2%96%A1%E2%96%A1").status_code == 400


def test_a_lexicon_key_in_an_unknown_language_is_refused(server):
    base, _ = server
    assert "Not a lexicon key" in get(base + "/lexicon/xx%3Afoo?partial=1")


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
    started with, since this is not the server's call to make."""
    draft(tmp_path, "1-022",
          '<pb n="2"/><p><foreign xml:lang="ckt">mêˊmêl</foreign></p>')
    assert edition_ui._attestations("ckt", "mêˊmêl", tmp_path) == []
    page(tmp_path, "1-021",
         '<pb n="1"/><p><foreign xml:lang="ckt">mêˊmêl</foreign></p>')
    assert edition_ui._attestations("ckt", "mêˊmêl", tmp_path) == ["1-021"]
