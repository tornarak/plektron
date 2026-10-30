"""The reading view: the renderer, and the server that writes the store.

Two things worth pinning. The renderer must show what the file says is unfinished
— an edition that tidies away an open question presents a draft as finished, and
that is the failure this whole project is arranged against. And the server writes
`edition/entities/` without `--commit`, on the `zones edit` precedent, so what has to be
true is that it cannot leave the store in a state `entity check` rejects.
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from urllib.parse import quote

import pytest
from markupsafe import escape
from test_entities import entry

from harness import edition_ui, entities, langs, speech, tei_html
from harness.entities import ENTITY_CLASSES

TEI_NS = "http://www.tei-c.org/ns/1.0"
CSS = Path(__file__).resolve().parent.parent / "web" / "static" / "css" / "edition.css"
JS = Path(__file__).resolve().parent.parent / "web" / "static" / "js"
JS = Path(__file__).resolve().parent.parent / "web" / "static" / "js"


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
    # The leaf's opening paragraph carries how it opens; this fixture witnesses
    # nothing, which is its own answer and not a missing one.
    assert got["ok"]
    assert '<p class="opens-unwitnessed">They went to Markova.</p>' in got["html"]


def test_the_keyed_zone_says_whether_the_leaf_opens_a_paragraph(tmp_path):
    """`MainZone-Continued` or not, months earlier, is a witness the rendering
    used to throw away — every page was set as though it carried over."""
    fresh = render(tmp_path, "<!-- zone-opens: fresh (from the zone label) -->"
                             "<p>The first slaughtering is performed</p>")
    assert '<p class="opens-fresh">' in fresh["html"]
    cont = render(tmp_path, "<!-- zone-opens: continued (from the zone label) -->"
                            "<p>of the herd, and the women</p>")
    assert '<p class="opens-continued">' in cont["html"]


def test_the_readers_indent_outranks_the_zone_label(tmp_path):
    """Two independent witnesses, and `opens:` is the one measured off the ink."""
    got = render(tmp_path, "<!-- opens: indented -->"
                           "<!-- zone-opens: continued (from the zone label) -->"
                           "<p>Then the younger people</p>")
    assert '<p class="opens-fresh">' in got["html"]


def test_an_adjudicated_seam_outranks_both(tmp_path):
    """`@part` is what a human decided at the gap, so it is what the page is set
    from — and `tei seam`, not the renderer, is what reports a disagreement."""
    got = render(tmp_path, "<!-- opens: indented -->"
                           '<p part="F">of the herd, and the women</p>')
    assert '<p class="opens-continued">' in got["html"]


def test_no_seam_written_yet_is_not_a_claim_that_one_opens(tmp_path):
    """The absence of `@part` is an unwritten seam, not `part="I"`."""
    got = render(tmp_path, "<!-- zone-opens: continued (from the zone label) -->"
                           "<p>of the herd, and the women</p>")
    assert '<p class="opens-continued">' in got["html"]


def test_a_plate_at_the_head_of_the_leaf_decides_nothing(tmp_path):
    """A figure is not the prose flow: the paragraph under it may still be the
    one that began on the page before."""
    got = render(tmp_path, "<!-- zone-opens: continued (from the zone label) -->"
                           '<figure n="87"><figDesc>Reindeer-Harness</figDesc>'
                           "</figure><p>of the herd, and the women</p>")
    assert '<p class="opens-continued">' in got["html"]


def test_a_leaf_opening_on_a_heading_marks_no_paragraph(tmp_path):
    """A head *is* the break, so the paragraph under it indents by the default and
    needs no witness — which is why `opens: no witness` is a third answer."""
    got = render(tmp_path, '<milestone unit="section" n="chVII.13"/>'
                           "<p>The Chukchee reckon the year</p>")
    assert "<p>The Chukchee reckon the year</p>" in got["html"]
    assert "opens-" not in got["html"]


def test_only_the_leafs_own_first_paragraph_is_marked(tmp_path):
    """Identity, not position — a paragraph inside a quotation is not the one the
    page opens with, however deeply the two nest."""
    got = render(tmp_path, "<!-- zone-opens: fresh (from the zone label) -->"
                           "<p>calling,</p><quote><p>Ho hok hok hok!</p></quote>"
                           "<p>which is quite like the usual call</p>")
    assert '<p class="opens-fresh">calling,</p>' in got["html"]
    assert got["html"].count("opens-") == 1


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


def test_a_tier1_name_the_store_has_no_entry_for_falls_back_to_the_lexicon(tmp_path):
    """**It reached neither.** `el_term` and `el_foreign` route a Tier-1 span
    through `_tier1`; `el_name` went straight to `_referring`, which renders a
    plain span when there is no `@ref`. So a native toponym the store has no
    entry for was the one kind of Tier-1 span on a page that linked nowhere at
    all — and 1-359, a gazetteer, is a page of them.

    The order is the nested-anchor fix's: an entity reference is the more
    specific claim and wins where there is one; the lexicon is the fallback."""
    got = render(tmp_path,
                 '<p><name type="hydronym" xml:lang="eve" resp="#gt">'
                 "Buks˙unda</name></p>")
    assert "/edition/lexicon/" in got["html"]
    assert 'data-type="hydronym"' in got["html"]


def test_a_name_with_an_entity_still_links_to_the_entity(tmp_path):
    """The fallback is a fallback — it must not overtake the specific claim."""
    got = render(tmp_path,
                 '<p><name type="toponym" ref="place:markova" xml:lang="ckt" '
                 'resp="#gt">Uweˊlen</name></p>')
    assert "/edition/entity/place:markova" in got["html"]
    assert "/edition/lexicon/" not in got["html"]


def test_a_tables_head_becomes_its_caption(tmp_path):
    """**It was dropped, and nothing said so.** `el_table` filtered its children
    to `row`, so a `<head>` validated, sat in the file and rendered as nothing —
    while `el_list` had always kept its own. 1-359 is where it showed: seven
    tables whose only titles are their heads, rendering as seven untitled grids
    with the markup saying otherwise and no error in between."""
    got = render(tmp_path,
                 "<p>x</p><table><head>Gishiga Bay.</head>"
                 "<row><cell>a</cell><cell>b</cell></row></table>")
    assert "<caption>Gishiga Bay.</caption>" in got["html"]
    # First child of the table, which is where HTML requires a caption.
    assert re.search(r"<table>\s*<caption>", got["html"])


def test_a_table_keeps_its_trailing_matter_too(tmp_path):
    """The schema ends `<table>` with `model.divBottom`, so a `<trailer>` is
    legal there and would have gone the way the head did. Rendered after the
    table, because HTML admits no element between `<table>` and `<tr>`."""
    got = render(tmp_path,
                 "<p>x</p><table><row><cell>a</cell></row>"
                 "<trailer>after the table</trailer></table>")
    assert "after the table" in got["html"]
    assert got["html"].index("</table>") < got["html"].index("after the table")


def test_no_element_loses_its_text_between_the_tei_and_the_page(tmp_path):
    """**The guard for the whole class, and the one that would have caught the
    head.** A renderer that filters its children by name drops what it does not
    name, and `element()`'s fallback — keep an unknown element's text — never
    runs, because the filter got there first. Nothing about the markup, the
    schema or the gate says so; the words are simply gone from the page.

    So: every word in the TEI body reaches the rendered HTML. Asserted as a
    multiset, since a renderer may reorder — a table's head moves ahead of its
    rows, and notes are gathered at the foot."""
    import unicodedata as u
    from collections import Counter

    from lxml import etree

    body = ("<p>lead in</p>"
            "<table><head>a caption</head>"
            "<row><cell cols='2'>a wide cell</cell></row>"
            "<row><cell>left</cell><cell>right</cell></row>"
            "<trailer>trailing matter</trailer></table>"
            "<list type='gloss'><head>a list head</head>"
            "<item><term xml:id='term-1-021-1'>a term</term>"
            "<gloss target='#term-1-021-1'>a gloss</gloss></item></list>")
    got = render(tmp_path, body)

    def words(t):
        return Counter(u.normalize("NFD", t).split())

    # Tags become a space rather than nothing. `strip_markup` drops them
    # outright, which welds `</caption><td>` into one token — harmless for the
    # search haystack it feeds, since that matches substrings, and wrong for a
    # word-level comparison.
    src = etree.fromstring(f'<body xmlns="{TEI_NS}">{body}</body>'.encode())
    missing = (words(" ".join(src.itertext()))
               - words(re.sub(r"<[^>]+>", " ", got["html"])))
    assert not missing, f"lost between the TEI and the page: {sorted(missing)}"


def test_a_cell_spanning_the_measure_says_so(tmp_path):
    """TEI spells it `@cols`, HTML `colspan`. Dropped, a cell the print runs
    across the measure renders in the first column and misaligns its row."""
    got = render(tmp_path,
                 "<p>x</p><table><row><cell cols='2'>wide</cell></row>"
                 "<row><cell rows='2'>tall</cell></row></table>")
    assert '<td colspan="2">wide</td>' in got["html"]
    assert '<td rowspan="2">tall</td>' in got["html"]


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


def test_a_note_is_a_body_at_the_foot_and_its_marker_is_where_the_print_set_it(tmp_path):
    """The marker used to be drawn by `el_note`, because the note element stood
    where the marker had been. It stands at the foot now, so drawing one there
    would print every superscript in a row in front of its own note text — wrong
    in both places at once. The `<ref type="note">` in the sentence draws it, and
    the first reference carries the id the foot links back to."""
    got = render(tmp_path, '<p>x<ref type="note" n="1" resp="#mz">¹</ref></p>'
                           '<note n="1" place="bottom">See Boas.</note>')
    assert 'class="noteref"' in got["html"] and 'href="#note-1"' in got["html"]
    assert 'id="ref-1"' in got["html"]
    assert got["notes"][0]["n"] == "1" and "See Boas." in got["notes"][0]["html"]


def test_a_note_referenced_twice_draws_two_markers_and_one_body(tmp_path):
    """`1-147` and `1-226` print one note against two markers. The old encoding
    could not say it — a spliced note is in one place — and reported the page as
    ambiguous instead."""
    got = render(tmp_path,
                 '<p>a<ref type="note" n="1" resp="#mz">¹</ref> and '
                 'b<ref type="note" n="1" resp="#mz">¹</ref></p>'
                 '<note n="1" place="bottom">Once.</note>')
    assert got["html"].count('class="noteref"') == 2
    assert got["html"].count('id="ref-1"') == 1, "only the first carries the id"
    assert len(got["notes"]) == 1


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
    """`edition/entities/people/eskimo.md` was written with a list before one rendered,
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


def test_inline_markup_survives_the_line_break_it_was_wrapped_on(tmp_path):
    """**The records are hard-wrapped, and every inline rule refuses `\\n`.**

    `_STRONG`, `_EM`, `_CODE` and `_LINK` all exclude the newline from their
    character classes, so a span that happened to wrap did not match and its
    asterisks were served to the reader as literal text. Silent, and invisible
    to whoever wrote the file, because whether it worked depended on nothing but
    where the line broke — the short bold rendered and the long one did not.

    Found from a rendered annotation, but the entity store had it first: **36
    spans across 29 files**. The fix is markdown's own reading of a hard-wrapped
    paragraph — join it into one logical line before the inline rules run, which
    is what the bullet branch had always done for a wrapped item.
    """
    got = edition_ui.gloss_html("is **clinal and\ncontinuous**, not typed", {})
    assert "<strong>clinal and continuous</strong>" in got
    assert "**" not in got

    got = edition_ui.gloss_html("see [the\npaper](https://e.test/a) for it", {})
    assert 'href="https://e.test/a"' in got and ">the paper</a>" in got

    got = edition_ui.gloss_html("an *emphasis that\nwraps* here", {})
    assert "<em>emphasis that wraps</em>" in got


def test_no_gloss_in_the_store_shows_a_literal_asterisk_pair(tmp_path):
    """The regression stated over the real records rather than a fixture.

    A rule about hard-wrapping cannot be trusted against one hand-written
    example: what broke it was the *distribution* of line lengths in files
    nobody was checking.
    """
    from harness import entities as ents

    store = ents.load(Path("."))
    bad = [k for k, r in store.items()
           if "**" in r["gloss"] and "**" in edition_ui.gloss_html(r["gloss"], store)]
    assert not bad, f"literal ** left in {bad}"


def _top_level_names(src: str) -> set[str]:
    """`const`/`let`/`class`/`function` names declared at brace depth 0.

    Depth-tracked rather than line-anchored, because the whole point is that a
    declaration *inside* a wrapper is not a global — a regex on `^const` calls a
    correctly-wrapped file a collision, which is the wrong answer in the one
    direction that matters. Strings and comments are skipped so a brace inside
    either cannot shift the depth.
    """
    names, depth, i = set(), 0, 0
    while i < len(src):
        c = src[i]
        if c in "\"'`":
            q, i = c, i + 1
            while i < len(src) and src[i] != q:
                i += 2 if src[i] == "\\" else 1
        elif src.startswith("//", i):
            i = src.find("\n", i)
            if i == -1:
                break
        elif src.startswith("/*", i):
            i = src.find("*/", i + 2) + 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0:
            m = re.compile(r"(?:const|let|class|function)\s+([A-Za-z_$][\w$]*)").match(src, i)
            if m and (i == 0 or not (src[i - 1].isalnum() or src[i - 1] in "_$.")):
                names.add(m.group(1))
                i = m.end()
                continue
        i += 1
    return names


def test_no_two_scripts_on_one_page_declare_the_same_global(tmp_path):
    """**Classic scripts share one global scope, so a `const` is page-wide.**

    `ratify.js` and `edition.js` both opened with `const B = STATE.base`, and for
    a long time nothing noticed: `page.html` loaded the second without the first,
    `card.html` the first without the second. The day a card page needed both,
    the duplicate was a `SyntaxError` — which kills the *entire* file, so the
    ratify button and every handler after it went dead, with nothing on the page
    saying why.

    The script list is read out of the templates rather than restated here, so
    this keeps holding when somebody adds a `<script>` to one of them.
    """
    tpl_dir = REPO / "harness" / "web" / "templates" / "edition"
    js_dir = REPO / "harness" / "web" / "static" / "js"
    src = {p.stem: _top_level_names(p.read_text(encoding="utf-8"))
           for p in js_dir.glob("*.js")}

    problems = []
    for tpl in sorted(tpl_dir.glob("*.html")):
        loaded = re.findall(r'src="/static/js/([\w-]+)\.js"',
                            tpl.read_text(encoding="utf-8"))
        seen = {}
        for f in loaded:
            for name in src.get(f, ()):
                if name in seen:
                    problems.append(f"{tpl.name}: `{name}` declared by both "
                                    f"{seen[name]}.js and {f}.js")
                seen[name] = f
    assert not problems, "\n".join(problems)


def test_a_youtube_link_becomes_an_embed_and_keeps_its_playlist(tmp_path):
    """Three shapes, and the middle one is what an album's per-track link is.

    Keeping the `list` is the point of that shape: a reader who opens track 27
    gets the record it belongs to and can play on, rather than coming back for
    track 28.
    """
    e = edition_ui.youtube_embed
    assert e("https://youtu.be/j_GLEh8EYYk") == "j_GLEh8EYYk"
    assert e("https://www.youtube.com/playlist?list=OLAK5uy_k7wp4QTiM") \
        == "videoseries?list=OLAK5uy_k7wp4QTiM"
    assert e("https://www.youtube.com/watch?v=j_GLEh8EYYk&list=OLAK5uy_k7wp4QTiM"
             "&index=1") == "j_GLEh8EYYk?list=OLAK5uy_k7wp4QTiM"


def test_an_escaped_ampersand_does_not_lose_the_playlist(tmp_path):
    """**`_link_html` runs on already-escaped text**, so a watch URL reaches the
    matcher with every `&` as `&amp;`.

    The failure this guards was silent and partial in the worst way: the video
    still embedded, so the card worked and looked right, and only the album was
    gone — from every per-track link on the record at once.
    """
    got = edition_ui.youtube_embed(
        "https://www.youtube.com/watch?v=j_GLEh8EYYk&amp;list=OLAK5uy_k7wp4QTiM")
    assert got == "j_GLEh8EYYk?list=OLAK5uy_k7wp4QTiM"


def test_only_youtube_reaches_the_embed(tmp_path):
    """The iframe `src` is built from ids this function matched, never from the
    URL as given — otherwise a `## links` row would be a way to frame an
    arbitrary page inside the edition."""
    for url in ("https://archive.org/details/chukchi-eskimo/",
                "https://evil.test/x?v=aaaaaaaaaaa&list=PLaaaaaaaaaaaa",
                'https://www.youtube.com/watch?v=abc"onload=x',
                "javascript:alert(1)"):
        assert edition_ui.youtube_embed(url) is None, url

    got = edition_ui.gloss_html(
        "[hear it](https://www.youtube.com/watch?v=j_GLEh8EYYk)", {})
    assert 'class="yt"' in got and 'data-embed="j_GLEh8EYYk"' in got
    # The href stays the real watch URL, so middle-click and no-JS still work.
    assert 'href="https://www.youtube.com/watch?v=j_GLEh8EYYk"' in got


def test_a_subheading_renders_and_only_from_three_hashes(tmp_path):
    """`###` and deeper only. `#` and `##` cannot reach a renderer — both
    authored stores slice their files on `##` — so admitting them would be
    rendering a section boundary as body text."""
    got = edition_ui.gloss_html("### What replaced it\n\nBody.", {})
    assert "<h5>What replaced it</h5>" in got and "###" not in got
    assert "<h6>" in edition_ui.gloss_html("#### Deeper\n\nMore.", {})
    # Escaping still applies inside a heading.
    got = edition_ui.gloss_html("### <script>alert(1)</script>", {})
    assert "<script>" not in got and "&lt;script&gt;" in got


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


def test_a_page_with_no_neighbour_still_says_which_page_it_is(server):
    """**The row is no longer only navigation, so it no longer vanishes.**

    It used to be wrapped in `{% if prev or next %}` and disappear on a page with
    neither neighbour, which was right while it held nothing but two links. It
    now carries the page's identity — the scan ref, and the printed folio beside
    it — because the folio had to come out of the running text: it was a
    `float:right` span in the margin, and a figure floated to the head of the
    page tucked in beside it and shouldered it out of the corner.

    So the *links* are conditional and the row is not. A page that named itself
    only when it happened to have a neighbour would be worse than the float.
    """
    base, _ = server
    body = get(base + "/page/1-021")
    assert body.count("class='neighbours'") == 2
    assert "1-021" in body
    assert "page-prev" not in body and "page-next" not in body


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


def test_no_link_colour_names_a_class_the_store_no_longer_has():
    """The other direction, and the quieter one. A class dropped from the store
    leaves a selector here that is **dead rather than wrong** — it matches
    nothing, breaks nothing, and shows in no rendering — so the test above,
    which walks the store, cannot see it. `language:` sat in the accent family
    for as long as it took someone to read the file."""
    import re
    css = CSS.read_text(encoding="utf-8")
    named = set(re.findall(r'\[data-ref\^="([a-z]+):"\]', css))
    assert named <= set(ENTITY_CLASSES), named - set(ENTITY_CLASSES)


def test_every_link_colour_is_defined_in_both_themes():
    """The drift far likelier than a missing class: a token added to `:root` and
    not to the dark block inherits the light value, and a colour code that holds
    in one theme only is worse than none.

    **The family tokens are read off the family rules**, not listed here. A hand
    list is a fourth copy of the same fact and the one nobody updates: `--pin`
    became a link colour when land and water split into two families, and a
    literal tuple would have gone on asserting about the five it was written
    with. What stays literal is the apparatus tokens, which no `--link` rule
    names and which would otherwise leave the set on the day the last rule using
    one moved."""
    css = CSS.read_text(encoding="utf-8")
    families = set(re.findall(r"--link:\s*var\((--[a-z]+)\)", css))
    assert families, "no --link family rules found; the selector shape moved"
    # **Three blocks, not two, since the theme toggle went in.** Light on bare
    # `:root`; dark under `prefers-color-scheme` for a reader who has never
    # touched the control; dark again under `[data-theme="dark"]` for one who
    # has. CSS cannot union a media query with an attribute selector, so the
    # third is a copy — which is exactly why the next assertion exists.
    for token in families | {"--lex", "--basin", "--hi", "--mark", "--sel"}:
        assert len(re.findall(rf"{token}\s*:", css)) == 3, token


def test_the_two_dark_palettes_are_the_same_palette():
    """The duplication the toggle forced, held to being a duplication.

    A token edited in the media-query block and not in the `[data-theme="dark"]`
    one gives two different dark themes: the reader who set the toggle sees a
    different page from the reader whose system set it, and neither has any way
    to tell. Nothing in CSS prevents that, so it is asserted here — the two
    blocks must carry the identical set of declarations.
    """
    css = CSS.read_text(encoding="utf-8")
    blocks = re.findall(
        r"(?::root:not\(\[data-theme=\"light\"\]\)|:root\[data-theme=\"dark\"\])"
        r"\s*\{(.*?)\}", css, re.S)
    assert len(blocks) == 2, f"expected two dark blocks, found {len(blocks)}"

    def decls(b):
        return sorted(d.strip() for d in b.split(";") if d.strip())

    assert decls(blocks[0]) == decls(blocks[1]), (
        "the two dark palettes have drifted apart")


def test_an_entry_that_can_be_drawn_arrives_with_its_map(server):
    """Reaching an entry and then having to ask for the map made the geography an
    optional extra, and it is not — `within:` is half of what an entry says about
    a place. The pane is what carries it: there is only ever one *here*, and a map
    that could be pushed out of sight by the next three cards was answering a
    question nobody had stopped asking.

    The page composes it (`geomap.js`): the pane names its subject and where
    the facts are, and `map.js` puts the subject on the sitting's map."""
    base, root = server
    entry(root, "place:uelen", extra="- geo: 66.16 -169.8\n")
    body = get(base + "/entity/place:uelen")
    assert "data-sel='place:uelen'" in body
    assert f"data-atlas='{base}/geo/atlas.json'" in body
    assert '<script type="module" src="/static/js/map.js">' in body


def test_a_point_can_be_opened_on_a_map_that_is_not_ours(server):
    """The coordinate is the store's most checkable field and the card is where a
    wrong one gets noticed — but noticing meant copying twelve digits into another
    tab, so nobody did. OpenStreetMap leads because it is the witness the place
    records were built against; the marker is dropped at the point rather than the
    view merely centred there.
    """
    base, root = server
    entry(root, "place:uelen", extra="- geo: 66.16 -169.8\n")
    body = get(base + "/entity/place:uelen")

    assert "66.1600, -169.8000" in body, "the value still leads; links follow it"
    assert ("https://www.openstreetmap.org/?mlat=66.1600&amp;mlon=-169.8000"
            "#map=10/66.1600/-169.8000") in body
    assert ("https://www.google.com/maps/search/?api=1&amp;"
            "query=66.1600,-169.8000") in body
    assert ">OpenStreetMap</a>" in body and ">Google Maps</a>" in body


def test_a_map_link_leaves_the_edition_without_handing_it_the_referrer(server):
    """These are the only outbound links on a card that a reader follows *while*
    reading, and the edition is served from a local host whose URL names the page
    being read. `rel='noreferrer'` is what the `link:` rows already do."""
    base, root = server
    entry(root, "place:uelen", extra="- geo: 66.16 -169.8\n")
    body = get(base + "/entity/place:uelen")
    for anchor in re.findall(r"<a class='maplink'[^>]*>", body):
        assert "rel='noreferrer'" in anchor and "target='_blank'" in anchor


def test_an_entry_with_nothing_to_draw_opens_no_pane(server):
    """Chuvan, Kerek, Siberian Yupik and Tundra Yukaghir are the live cases. An
    empty pane saying so would be a second statement of what the card's own
    `contains`/`within` rows already do not claim.

    **Shipped shut, not absent**: the page's other place links still put places
    on a map, and with no pane in the column they had nowhere to go."""
    base, _ = server
    body = get(base + "/entity/place:markova")
    assert "<div id='map-pane' hidden" in body
    assert "data-sel=" not in body


def test_the_fragment_the_stack_and_the_preview_use_carries_no_map(server):
    """A hover preview and a card in the stack are both read *while* the pane is
    showing the geography. A second copy inside the card would answer a question
    nothing was asking, and cost a map render per hover."""
    base, root = server
    entry(root, "place:uelen", extra="- geo: 66.16 -169.8\n")
    bare = get(base + "/partial/entity/place:uelen")
    assert "Uelen" in bare
    assert "<svg" not in bare and "map-pane" not in bare


def test_the_page_view_ships_the_pane_shut_and_the_stack_apart_from_it(server):
    """`edition.js` indexes `STACK.childNodes` as cards — selected, surfaced,
    pinned, deleted. A pane among them would be all four."""
    base, _ = server
    body = get(base + "/page/1-021")
    assert "id='map-pane' hidden" in body
    assert "id='stack'" in body


# ------------------------------------------------ the sidebar's two tabs

#: A printed list small enough to reason about, over the folios the `server`
#: fixture's pages actually witness. `page_start` is a printed folio, so these are
#: the `<pb n>` values below and not scan refs.
_PANEL_TOC = {"source": {"refs": ["1-007"], "printed_folios": ["v"]},
              "entries": [
    {"level": 0, "chapter": None, "number": None, "title": "Introductory",
     "page_start": 1, "id": "front.intro", "ref": "1-007"},
    {"level": 1, "chapter": "I", "number": "I", "title": "Names and Habitat",
     "page_start": 2, "id": "chI", "ref": "1-007"},
    {"level": 2, "chapter": "I", "number": None, "title": "Ancient Habitat",
     "page_start": 4, "id": "chI.2", "ref": "1-007"},
    # Two sections on one folio, which is the case a containing chain gets wrong:
    # it holds one entry per level, so it names the second and says nothing about
    # the first. `1-249` prints "Animal Food" and "Methods of Cooking" this way.
    {"level": 2, "chapter": "I", "number": None, "title": "Present Habitat",
     "page_start": 4, "id": "chI.3", "ref": "1-007"},
    {"level": 3, "chapter": "I", "number": None, "title": "The Ai'wan",
     "page_start": 5, "id": "chI.3a", "ref": "1-007"},
    {"level": 1, "chapter": "II", "number": "II", "title": "Neighbors",
     "page_start": 10, "id": "chII", "ref": "1-007"},
    {"level": 2, "chapter": "II", "number": None, "title": "Appearance",
     "page_start": 11, "id": "chII.1", "ref": "1-007"},
]}


def _toc(root: Path) -> None:
    import json
    (root / "edition").mkdir(parents=True, exist_ok=True)
    (root / "edition/toc.json").write_text(json.dumps(_PANEL_TOC), encoding="utf-8")


def _panel(body: str) -> str:
    """The contents panel alone. Bounded at both ends on purpose: `class='here'`
    is also the neighbours row's name for the page you are on, and a slice that
    ran to the end of the document would count that as a mark."""
    return body.split("id='panel-contents'")[1].split("</aside>")[0]


def _row(panel: str, title: str) -> str:
    """The `<li>` a title is in, opening tag onwards. A row's marks are on the
    element and the title is inside it, so "is this row marked" is the text
    between the last `<li` before the title and the title itself — and not a
    slice of the panel down to the title, which would carry every enclosing row
    with it."""
    return "<li" + panel.split(title)[0].rsplit("<li", 1)[1]


def test_the_sidebar_ships_its_switch_with_the_contents_shut(server):
    """Entities is the column as it was; contents is rendered, so the switch
    costs no request. **The switch is a checkbox, unchecked**, with the label as
    its face — which panel shows is the stylesheet's reading of it, so the
    contents open with no script at all. It is at the foot of the column, and
    nothing comes between the column and the text, because `#secondary +
    #primary` is the idle rule's selector."""
    base, root = server
    _toc(root)
    body = get(base + "/page/1-021")
    switch = re.search(r"<input type='checkbox' id='toc-switch'[^>]*>", body)
    assert switch and "checked" not in switch.group(0)
    assert re.search(r"<label for='toc-switch' id='toc-toggle'[^>]*>.*TOC.*</label>",
                     body, re.S)
    assert body.index("id='secondary'") < body.index("id='toc-switch'") \
        < body.index("id='toc-toggle'") < body.index("</aside>")
    assert re.search(r"</aside>\s*<div id='primary'", body)
    assert "<div id='panel-contents'>" in body, "the panel is the stylesheet's to show"
    # The fringes are labels for one radio group, neither checked: the column
    # deciding for itself, and the stylesheet's to show or put away.
    for state, fringe in (("side-on", "side-show"), ("side-off", "side-hide")):
        radio = re.search(rf"<input type='radio' name='side' id='{state}'[^>]*>", body)
        assert radio and "checked" not in radio.group(0)
        assert f"<label for='{state}' id='{fringe}'" in body
    assert "id='side-tabs'" not in body
    # The switch did not displace what the column already held.
    assert "id='map-pane' hidden" in body and "id='stack'" in body


def test_the_contents_panel_opens_the_division_holding_this_page(server):
    """Folio 2 opens chapter I and marks it, and the front matter above it — which
    contains no page of the chapter — is neither marked nor opened."""
    base, root = server
    _toc(root)
    page(root, "1-034", '<pb n="2"/><p>The chapter opens.</p>')
    panel = _panel(get(base + "/page/1-034"))
    assert "toc-d1 here'" in panel and panel.count("<details open>") >= 1
    assert " here'" not in _row(panel, "Introductory"), \
        "the front matter is not where this page is"


def test_a_deeper_division_marks_its_chapter_too(server):
    """A section is contained by its chapter, so both are marked and the chapter
    is what opens — a section marked inside a shut chapter would be a mark you
    cannot see. Folio 5 is `chI.3a`, three rungs down."""
    base, root = server
    _toc(root)
    page(root, "1-030", '<pb n="5"/><p>In the chapter.</p>')
    panel = _panel(get(base + "/page/1-030"))
    for depth in (1, 2, 3):
        assert f"toc-d{depth} here'" in panel, f"depth {depth} unmarked"


def test_both_heads_printed_on_one_page_are_marked(server):
    """**A containing chain holds one entry per level**, so a page that prints two
    section heads was told it was in the second of them and nothing about the
    first. `1-249` sets "Animal Food" and "Methods of Cooking" this way. The
    entries whose `page_start` is this folio are marked alongside the chain."""
    base, root = server
    _toc(root)
    page(root, "1-032", '<pb n="4"/><p>Two heads open here.</p>')
    panel = _panel(get(base + "/page/1-032"))
    assert panel.count("toc-d2 here'") == 2
    for title in ("Ancient Habitat", "Present Habitat"):
        assert " here'" in _row(panel, title), f"{title} is not marked"


def test_the_division_you_are_in_is_unrolled_whole(server):
    """Not just the path down to the marked row. A chapter opened to the one row
    that matched shows you the row you already had and hides its neighbours, which
    is the opposite of a locator — so every `<details>` inside the division opens,
    and the divisions around it stay shut."""
    base, root = server
    _toc(root)
    page(root, "1-033", '<pb n="4"/><p>Inside chapter I.</p>')
    panel = _panel(get(base + "/page/1-033"))
    # chI and the sibling section carrying the subsection: both open, and
    # chapter II — which holds a section of its own — stays shut, which is a
    # plain row: its section is not carried at all.
    assert panel.count("<details open>") == 2
    assert "The Ai&#39;wan" in panel, "the open division is unrolled whole"
    assert "Appearance" not in panel and "<details>" not in panel


def test_every_division_is_shown_and_nothing_under_a_shut_one(server):
    """Every top-level division, so the panel still shows what is *around* you —
    one that held only the divisions it could place would answer a different
    question on every page. **But not what is folded inside a shut one**: the
    only thing to do with those rows is click through, and the page that opens
    carries them open. Serving them on every page was ~77 KB of each."""
    base, root = server
    _toc(root)
    panel = _panel(get(base + "/page/1-021"))
    for title in ("Introductory", "Names and Habitat", "Neighbors"):
        assert title in panel, f"{title} is missing from the outline"
    for title in ("Ancient Habitat", "Present Habitat", "The Ai&#39;wan", "Appearance"):
        assert title not in panel, f"{title} is folded away and still carried"
    # Folio 1 is the front matter, which has nothing under it: one row is marked
    # and no `<details>` anywhere is open.
    assert panel.count(" here'") == 1
    assert "<details" not in panel


def test_a_page_whose_folio_nothing_witnesses_marks_nothing(server):
    """The refusal said out loud. An unmarked panel and a panel that could not
    place the page look identical, and most of the book is the second."""
    base, root = server
    _toc(root)
    page(root, "1-031", "<p>No pb, so no folio.</p>")
    panel = _panel(get(base + "/page/1-031"))
    assert " here'" not in panel and "<details open>" not in panel
    assert "Nothing places this leaf in the printed Contents." in panel


def test_an_entity_marks_every_division_it_is_mentioned_in(server):
    """**Past the eight rows the card shows.** `_mentions` truncates its list for
    the card; the panel folds the untruncated one, because a chapter is not
    reached by an entity's first eight pages and a chapter left unmarked reads,
    on screen, exactly like a chapter the entity is absent from.
    """
    base, root = server
    _toc(root)
    # Eleven pages, folios 1–11: eight of them inside the card's cap and in the
    # front matter and chapter I, three past it and in chapter II.
    for i, folio in enumerate(range(1, 12)):
        page(root, f"1-{100 + i}", f'<pb n="{folio}"/><p>At '
             f'<rs ref="place:markova" resp="#mz">Markova</rs>.</p>')
    body = get(base + "/entity/place:markova")
    panel = _panel(body)
    assert "Neighbors" in panel
    # Every division holds mentions, so every one of them opens and counts.
    for title in ("Introductory", "Names and Habitat", "Neighbors"):
        assert title in panel
    assert panel.count("<details open>") == 3
    # The chapter's count is the sum of what lies under it, folded rather than
    # rolled up: chapter I runs folios 2–9, which is eight of the twelve
    # mentions (eleven pages plus the fixture's own 1-021 at folio 1).
    hits = re.findall(r"class='hits' title='(\d+) mention", panel)
    assert hits and sum(int(h) for h in hits) > 8


def test_a_lexicon_card_marks_where_the_form_is_attested(server):
    """The same mark an entity's mentions make, and on the same warrant: the
    lexicon's identity *is* the form, so no alias table stands between the word
    and the pages — there is nothing to be wrong about. `attestations` sweeps
    committed `tei/` and is re-derived every run.

    **A count of pages, not of occurrences.** `_attestations` dedupes on
    `(form, lang)` per page, so the number on a division is how many attested
    pages lie under it, which is the only thing the store recorded.
    """
    base, root = server
    _toc(root)
    # Folio 4 is chapter I's "Ancient Habitat"; folio 11 is chapter II's
    # "Appearance". One attested page in each, and two divisions marked.
    for ref, folio in (("1-040", 4), ("1-041", 11)):
        page(root, ref, f'<pb n="{folio}"/><p>The form is '
             f'<foreign xml:lang="ckt" resp="#ed">o\u02cara\u02c8w\u01ddʟ\u0323at</foreign>.</p>')
    panel = _panel(get(base + f"/lexicon/{quote('ckt:oˊraˈwǝʟ̣at')}"))
    hits = [int(n) for n in re.findall(r"class='hits' title='(\d+) mention", panel)]
    assert hits, "the form is attested and nothing was marked"
    # Two chapters, one page each, and the chapters' own numbers are that sum.
    assert sorted(hits) == [1, 1, 1, 1], hits
    assert " here'" not in panel, "a form has no position, only attestations"


def test_a_form_the_corpus_does_not_attest_blames_no_contents(server):
    """**The refusal is about placement, so it may only fire where there was
    something to place.** A form no store attests has not failed to be placed in
    the printed Contents — it is simply not in the book, which the card's own rows
    say. Sourced from committed `tei/` alone, this note appeared on every card in
    the lexicon, because 0 pages are collated: the corpus's state reported as the
    Contents' failure, which is the one thing this panel must not do."""
    base, root = server
    _toc(root)
    panel = _panel(get(base + "/lexicon/ckt%3AUwe%CB%8Alen"))
    assert "printed Contents" not in panel
    assert " here'" not in panel


def test_a_form_placed_nowhere_says_so(server):
    """Where the corpus *does* attest the form and the folio index can place none
    of those pages, that is a placement failure and gets the sentence — in the
    store's own terms, since a form is attested rather than mentioned."""
    base, root = server
    _toc(root)
    # Attested, and on a page carrying no `<pb>`, so nothing witnesses its folio.
    page(root, "1-050", '<p>Here is <foreign xml:lang="ckt" '
         'resp="#ed">qoraˈŋy</foreign>.</p>')
    panel = _panel(get(base + "/lexicon/" + quote("ckt:qoraˈŋy")))
    assert "No attestation of this form is placed in the printed Contents." in panel


def test_an_entity_with_no_map_still_has_a_sidebar(server):
    """The column stopped being conditional on the geography. An entry that is not
    a place still has somewhere in the book it is talked about, which was the one
    question this page could not answer."""
    base, root = server
    _toc(root)
    entry(root, "person:bogoras", status="proposed")
    body = get(base + "/entity/person:bogoras")
    assert "id='secondary'" in body and "id='panel-contents'" in body
    assert "<div id='map-pane' hidden" in body


@pytest.mark.parametrize("path", ["/atlas", "/entities", "/entity/person:bogoras"])
def test_a_reference_view_carries_the_sidebar_fixed_open(server, path):
    """The entry, the atlas and the encyclopedia are lists of names whose click
    is a request for the map or the card, so the column is their point: the
    reading sidebar, with the pane and the stack, and neither fringe nor idle
    rule able to put it away. The atlas once had a column of its own with no
    stack, and its names reached the map by navigating to `/atlas?at=`."""
    base, root = server
    _toc(root)
    entry(root, "person:bogoras", status="proposed")
    body = get(base + path)
    assert "<aside id='secondary' data-fixed>" in body
    assert "id='stack'" in body and "id='map-pane'" in body
    assert "id='side-hide'" not in body and "id='side-show'" not in body
    assert "/static/js/edition.js" in body and "/static/js/map.js" in body
    assert "atlas?at=" not in body


@pytest.mark.parametrize("path", ["/entity/person:bogoras", "/lexicon/notaform"])
def test_a_card_fragment_is_its_own_path(server, path):
    """The bare card the stack and a preview fetch lives under `/partial/`, not
    behind a query: a static host serves by path and drops the query, so a
    fragment told apart only by `?partial=1` would collide with its page. The
    old spelling is ignored rather than honoured, so nothing can lean on it."""
    base, root = server
    _toc(root)
    entry(root, "person:bogoras", status="proposed")
    page = get(base + path)
    assert "<html" in page.lower()
    assert "<html" not in get(base + "/partial" + path).lower()
    sep = "&" if "?" in path else "?"
    assert "<html" in get(base + path + sep + "partial=1").lower()


# --------------------------------------------------- the footnote popup


def test_the_page_loads_the_note_popup_after_hover(server):
    """`notes.js` places its popup with `hover.js`'s `place`, so it cannot be
    loaded before the file that publishes it."""
    base, _ = server
    body = get(base + "/page/1-021")
    assert "/static/js/notes.js" in body
    assert body.index("/static/js/hover.js") < body.index("/static/js/notes.js")


def test_hover_publishes_the_placement_it_shares(server):
    """One piece of viewport arithmetic for the two things that float beside a
    link in this text. It takes its target as an argument for that reason — a
    version closing over its own box could not be shared. And one grace period,
    so a note and a preview wait the same time for the pointer to arrive."""
    src = (JS / "hover.js").read_text(encoding="utf-8")
    assert "window.CARDS = {get, place, GRACE_MS}" in src
    assert "function place(a, el)" in src
    assert "window.CARDS.GRACE_MS" in (JS / "notes.js").read_text(encoding="utf-8")


def test_the_note_popup_reads_the_foot_and_fetches_nothing(server):
    """The notes are already on the page — `page.html` renders every one of them
    into `#foot` from `doc.notes`. A popup that fetched them would be a second
    renderer for text the server already sent."""
    src = (JS / "notes.js").read_text(encoding="utf-8")
    assert "getElementById('foot')" in src
    assert "fetch(" not in src, "the note is in the DOM; nothing is fetched"


def test_the_marker_is_a_switch_and_the_note_carries_the_jump(server):
    """**Every click on the marker is swallowed, so the jump has to be elsewhere.**
    `.noteref` is an `<a href="#note-N">` and jumps with no script at all, which is
    what this degrades to; a marker that toggles has taken that away, and what it
    took is offered again at the note's own foot. A marker that opened on one
    click and travelled on the next would be two acts on one target,
    distinguished by nothing the reader can see."""
    src = (JS / "notes.js").read_text(encoding="utf-8")
    assert "ev.preventDefault()" in src
    assert 'class="note-jump"' in src
    # The jump's href is the anchor's own, not rebuilt from `data-note`: one
    # spelling of the address, and `tei_html` owns it.
    assert "a.getAttribute('href')" in src
    # Tested before the outside-click case *inside the click handler*, since the
    # jump sits within the popup and that case would otherwise never reach it.
    click = src.split("document.addEventListener('click'")[1]
    assert click.index(".note-jump'") < click.index("closest('.notepop')")


def test_the_note_is_one_shape_hovered_or_kept(server):
    """**`show` takes no "is it kept" flag, and that is the property.** Rendering
    the jump row on the click alone made the popup grow under the pointer — the
    same note in two shapes, the second arriving as a jolt at the moment of
    clicking. A reader is looking at a note, not at a widget that reconfigures
    itself."""
    src = (JS / "notes.js").read_text(encoding="utf-8")
    assert "function show(a) {" in src
    assert "kept" not in src.split("function show(a) {")[1].split("\n  }")[0]


def test_the_jump_row_is_ruled_off_and_sits_left(server):
    """Dashed, because a solid rule reads as part of the note's text and this is
    the popup's own furniture. Left, because the popup is `width:max-content` — a
    row set against the right edge lands somewhere different for every note, and
    the left margin is the one edge they all share."""
    css = CSS.read_text(encoding="utf-8")
    row = css.split(".card.notepop .note-jump{")[1].split("}")[0]
    assert "dashed" in row
    assert "text-align" not in row, "the block's own left edge, not an alignment"


def test_the_note_popup_and_the_preview_can_both_be_reached(server):
    """A kept note and a preview both hold links of their own, and a link the
    pointer cannot reach is one offered and taken back. The preview also needs
    `hover.js` to keep it open across the gap from its link."""
    css = CSS.read_text(encoding="utf-8")
    for sel in (".card.notepop{", ".card.preview{"):
        assert "pointer-events:none" not in css.split(sel)[1].split("}")[0], sel
    src = (JS / "hover.js").read_text(encoding="utf-8")
    assert "GRACE_MS" in src and "box.contains(ev.target)" in src
    # On touch the first tap previews: it has to be held before every
    # document-level click handler, which only a capture on `window` is.
    assert "ev.pointerType === 'touch'" in src
    assert "window.addEventListener('click'" in src and "stopPropagation" in src


def test_the_served_page_holds_what_the_popup_reaches_for(server):
    """**`notes.js` reads the DOM, so the DOM's shape is its contract.** It finds
    a note by the id its marker's own `href` names — not by `li[data-n]`, since a
    chapter's foot holds every leaf's note 1 — and its numeral by
    `a[href^="#ref-"]`: selectors that would go quietly dead if `page.html` or
    `tei_html` renamed anything, since a popup that finds nothing looks exactly
    like a reader who has not hovered."""
    base, root = server
    page(root, "1-060", '<p>x<ref type="note" n="1" resp="#mz">¹</ref></p>'
                        '<note n="1" place="bottom">See Boas.</note>')
    body = get(base + "/page/1-060")
    assert "id='foot'" in body
    assert "data-n='1'" in body and "id='note-1'" in body
    assert 'class="noteref"' in body and 'data-note="1"' in body
    # Quote-agnostic: `tei_html` emits the marker with double quotes and
    # `page.html` writes the backlink with single ones. The selector in
    # `notes.js` is a CSS attribute match and does not care, but a test that
    # spelled one style would fail the day the other changed for no reason.
    assert re.search(r"""href=["']#note-1["']""", body)
    assert re.search(r"""href=["']#ref-1["']""", body)

    src = (JS / "notes.js").read_text(encoding="utf-8")
    assert "li[id=" in src and "getAttribute('href')" in src
    assert 'a[href^="#ref-"]' in src


def test_a_page_with_no_notes_binds_nothing(server):
    """The script leaves immediately where there is no foot. Most pages have no
    notes, and a listener that ran on all of them to find nothing is a listener
    on every pointer move in the book."""
    src = (JS / "notes.js").read_text(encoding="utf-8")
    head = src.split("addEventListener")[0]
    assert "if (!FOOT) return;" in head


def test_the_entity_panel_is_the_same_content_bare(server):
    """One template, wrapped or bare, so a permalink and a click land identically."""
    base, _ = server
    whole = get(base + "/entity/place:markova")
    bare = get(base + "/partial/entity/place:markova")
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


# ------------------------------------------------- the card's own tree

def _taxa(root: Path) -> dict:
    """A four-rung `part-of:` chain with siblings on the bottom two, which is the
    shape the taxon store actually has."""
    entry(root, "taxon:animalia", canonical="Animalia")
    entry(root, "taxon:salmonidae", canonical="Salmonidae",
          extra="- part-of: taxon:animalia\n")
    entry(root, "taxon:oncorhynchus", canonical="Oncorhynchus",
          extra="- part-of: taxon:salmonidae\n")
    entry(root, "taxon:thymallus", canonical="Thymallus", status="proposed",
          extra="- part-of: taxon:salmonidae\n")
    for sp in ("keta", "nerka"):
        entry(root, f"taxon:oncorhynchus-{sp}", canonical=f"O. {sp}",
              extra="- part-of: taxon:oncorhynchus\n")
    from harness.web import stores
    return stores.load(root)


def test_the_card_tree_is_the_spine_from_the_top_of_the_class_down(tmp_path):
    """Every ancestor, each holding only the child on the path — the entry's
    place, not its class's whole subtree. `taxon:thymallus` is a sibling of the
    node the tree runs through and must not appear: a card that opened onto the
    branches either side of the chain would be the class index with the entry
    lost in it."""
    store = _taxa(tmp_path)
    tree = edition_ui.kin_tree("taxon:oncorhynchus", store)

    ids, node = [], tree[0]
    while True:
        ids.append(node["id"])
        if not node["children"]:
            break
        node = node["children"][0]
    assert ids[:3] == ["taxon:animalia", "taxon:salmonidae",
                       "taxon:oncorhynchus"]
    assert "taxon:thymallus" not in str(tree)


def test_the_card_tree_marks_the_entry_and_lists_what_it_holds(tmp_path):
    store = _taxa(tmp_path)
    tree = edition_ui.kin_tree("taxon:oncorhynchus", store)
    subject = tree[0]["children"][0]["children"][0]

    assert subject["selected"] and subject["id"] == "taxon:oncorhynchus"
    assert [k["id"] for k in subject["children"]] == [
        "taxon:oncorhynchus-keta", "taxon:oncorhynchus-nerka"]
    # What a node above holds, said as a count: the branch itself is that node's
    # own card, which is what its name is a link to.
    assert tree[0]["below"] == 5


def test_the_card_tree_takes_part_of_where_the_atlas_takes_within(tmp_path):
    """The two hierarchies, and the card is on the encyclopedia's. `people:naukans`
    hangs from a village under the atlas's edge, which is right on a map and
    leaves a page about peoples showing no subgroups at all."""
    entry(tmp_path, "people:yupik", canonical="Yupik")
    entry(tmp_path, "place:naukan", canonical="Naukan")
    entry(tmp_path, "people:naukans", canonical="Naukans",
          extra="- within: place:naukan\n- part-of: people:yupik\n")
    from harness.web import stores

    store = stores.load(tmp_path)
    assert edition_ui.kin_tree("people:naukans", store)[0]["id"] == "people:yupik"
    assert [n["id"] for n in edition_ui.kin_tree("place:naukan", store)] == []


def test_a_card_tree_of_one_node_is_not_drawn(tmp_path):
    """An entry that belongs to nothing and holds nothing would get its own
    heading back in smaller type, which says nothing and looks like a finding."""
    entry(tmp_path, "person:bogoras", canonical="Bogoras")
    from harness.web import stores

    assert edition_ui.kin_tree("person:bogoras", stores.load(tmp_path)) == []


def test_a_long_child_list_goes_behind_a_fold_that_says_its_size(tmp_path):
    entry(tmp_path, "taxon:aves", canonical="Aves")
    for i in range(edition_ui.KIN_FOLD + 1):
        entry(tmp_path, f"taxon:bird-{i:02}", canonical=f"Bird {i}",
              extra="- part-of: taxon:aves\n")
    from harness.web import stores

    node = edition_ui.kin_tree("taxon:aves", stores.load(tmp_path))[0]
    assert node["children"] == []
    assert len(node["folded"]) == edition_ui.KIN_FOLD + 1
    assert node["summary"] == f"{edition_ui.KIN_FOLD + 1} in it"


def test_the_card_carries_its_tree_and_the_stack_fragment_carries_it_too(tmp_path):
    """The fragment is the whole card wherever it is read, so the tree is in the
    partial the stack injects and not only on the standalone page."""
    _taxa(tmp_path)
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    c = TestClient(create_app(tmp_path, Sessions(root=tmp_path), editor="edition"))
    for url in ("/edition/entity/taxon:oncorhynchus",
                "/edition/partial/entity/taxon:oncorhynchus"):
        body = c.get(url).text
        assert "kin-tree" in body
        assert "/edition/entity/taxon:salmonidae" in body
        assert "/edition/entity/taxon:oncorhynchus-keta" in body


def test_both_trees_are_drawn_by_one_stylesheet_rule(tmp_path):
    """`ent-tree` is the shape and `map-tree` is what only a map means. Two
    hierarchies a reader is told apart by what they say, not by having to learn
    two ways of reading a nested list."""
    geomap = CSS.parent / "geomap.css"
    css = CSS.read_text(encoding="utf-8")
    assert ".ent-tree li.sel > a.node" in css and ".kin-tree {" in css
    # The map's own rules are the controls, and nothing else: a layout rule left
    # behind here would drift from the one above without either looking wrong.
    for rule in ("li { padding", "ul ul { border-left", "a.node { color"):
        assert rule not in geomap.read_text(encoding="utf-8")


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
    got = post(base + "/ratify", {"id": "place:markova"})
    # The response says what the act *did*, not only that it worked: ratifying is
    # also what applies the entry's links to every collated page, and "linked
    # nothing" is an ordinary outcome a caller must be able to tell from a failure.
    assert got["ok"] and got["linked"] == [] and got["pages"] == []
    assert "- status: ratified" in (
        root / "edition" / "entities" / "place" / "markova.md").read_text(encoding="utf-8")


def test_a_write_that_would_break_the_store_is_rolled_back(server):
    """Every `@ref` in the corpus resolves against this store, so a browser that
    could leave it incoherent would break pages nobody is looking at."""
    base, root = server
    entry(root, "water:markova", aliases=[("Markova", True)])
    got = post(base + "/ratify", {"id": "place:markova"})
    assert "refused" in got.get("error", "")
    assert "- status: proposed" in (
        root / "edition" / "entities" / "place" / "markova.md").read_text(encoding="utf-8")


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
    got = get(base + "/partial/lexicon/ckt%3AUwe%CB%8Alen")
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
        # No `geo:` beside the `area:` — `parse` refuses a record carrying both,
        # since a shape is the location and `extent_of` never reads a point next
        # to one. It costs this test nothing: the record dict carries every key
        # whether or not the file sets it, and keys are all this asserts about.
        "# place:x — X\n\n- status: proposed\n- since: 1-021\n"
        "- within: place:y\n- area: watershed:anadyr\n"
        "- frame: 160.0 60.0 170.0 70.0\n"
        "- authority: k\n- link: wikidata:Q1\n\n## aliases\n\n"
        "| form | lang | auto | note |\n|---|---|---|---|\n| X | no | |\n\n"
        "## gloss\n\nx\n", encoding="utf-8")
    rec = entities.parse(text.read_text(encoding="utf-8"))
    covered = set(edition_ui.SHOWN_ELSEWHERE) | set(edition_ui.PROPERTY_FIELDS)
    assert set(rec) <= covered, f"nothing displays {sorted(set(rec) - covered)}"


#: Fields of an `authorities.json` record the card handles by name rather than
#: through `AUTHORITY_FIELDS`, each because it is not a plain string: two carry a
#: rank, two qualify the field above them, and three have shapes of their own.
AUTHORITY_BY_NAME = {
    "key", "cited_as", "printed", "doi", "url", "author_printed", "year_printed",
    "folio",
}


def test_every_field_of_a_transcluded_authority_reaches_the_card():
    """**The no-invisible-fields rule reaches a store the card borrows from.**

    A `source:` entry is mostly its bibliography record, and the card printed
    two fields of it — the key and the title. `cited_as` was the casualty that
    mattered: it is how the *book* names the work, so it is the one field a
    reader holding a footnote can match against, and it appeared nowhere in the
    encyclopedia at all.

    Corpus-facing on purpose. The shape being asserted is `edition/authorities.json`'s
    own, and a fixture would prove only that this test agrees with itself —
    `year_printed`, which is on 3 records of 73, is exactly the field a fixture
    would have been written without.
    """
    from harness import authorities
    works = authorities.load(PROJECT)
    assert works
    shown = {f for f, _ in edition_ui.AUTHORITY_FIELDS} | AUTHORITY_BY_NAME
    keys = {k for w in works for k in w}
    assert keys <= shown, f"nothing displays {sorted(keys - shown)}"


def test_a_ranked_url_carries_its_rank_onto_the_card():
    """`doi` and `url` are `{url, provenance}` — a reading with a rank on it, and
    the rank is shown. A card that printed the link bare would be the unmarked
    span failure in a second store: a scan a model found, rendered exactly like
    one somebody opened."""
    rows = edition_ui._authority_rows("nelson1899", PROJECT)
    ranked = [r for r in rows if r["kind"] == "sourced"]
    assert ranked and all(r["resp"].startswith("#") for r in ranked)
    assert all(r["value"].startswith("http") for r in ranked)


def test_the_printed_block_is_on_the_card_and_the_siglum_with_it():
    """`printed` is the record — `find authority`'s rule, kept here. The parsed
    fields ride beneath it so the two can be read against each other, and the
    siglum sits at the top because it is what a reader arrives holding."""
    rows = edition_ui._authority_rows("maydell1893", PROJECT)
    labels = [r["label"] for r in rows]
    assert "cited as" in labels and "printed" in labels
    assert labels.index("cited as") < labels.index("printed")
    cited = next(r for r in rows if r["label"] == "cited as")
    assert "Maydell, I" in cited["value"] and "Maydell, II" in cited["value"]


def test_the_properties_block_shows_the_geography(tmp_path):
    """The three geography fields, on the card, where a reader can check them
    against the map beside it."""
    entry(tmp_path, "place:y", aliases=[("Y", False)])
    p = tmp_path / "edition" / "entities" / "place" / "x.md"
    p.write_text("# place:x — X\n\n- status: ratified\n- since: 1-021\n"
                 "- within: place:y\n- geo: 66.0 170.0\n\n## aliases\n\n"
                 "| form | lang | auto | note |\n|---|---|---|---|\n\n## gloss\n\nx\n",
                 encoding="utf-8")
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    c = TestClient(create_app(tmp_path, Sessions(root=tmp_path), editor="edition"))
    got = c.get("/edition/partial/entity/place:x").text
    assert "within" in got and "66.0000, 170.0000" in got
    # The inverse too: a parent that could not list its own members would send
    # a reader to the atlas to find out what it holds.
    assert "contains" in c.get("/edition/partial/entity/place:y").text


def test_a_geo_member_reads_both_ways(tmp_path):
    """A people's `geo:` names its villages and is written on its side only, so
    each village's card has to find who names it — the inverse `contains` is to
    `within:`. One row each way, however many members."""
    entry(tmp_path, "place:y", aliases=[("Y", False)])
    entry(tmp_path, "place:z", aliases=[("Z", False)])
    p = tmp_path / "edition" / "entities" / "people" / "x.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# people:x — X\n\n- status: ratified\n- since: 1-021\n"
                 "- geo: place:y\n- geo: place:z\n\n## aliases\n\n"
                 "| form | lang | auto | note |\n|---|---|---|---|\n\n## gloss\n\nx\n",
                 encoding="utf-8")
    store = entities.load(tmp_path)
    rows = edition_ui.property_rows(store["people:x"], store, tmp_path)
    located = [r for r in rows if r["label"] == "located"]
    assert len(located) == 1
    assert [e["id"] for e in located[0]["entries"]] == ["place:y", "place:z"]
    back = edition_ui.property_rows(store["place:y"], store, tmp_path)
    assert [r["entries"] for r in back if r["label"] == "location of"] == [
        [{"id": "people:x", "name": "X"}]]


def test_a_lexicon_card_carries_the_imputed_pronunciation(server):
    """Labelled `imputed`, and the label is not decoration: the IPA is a rule
    table's output and the audio is espeak with no Chukchi voice behind it, so
    the card is where a reader is told that rather than a doc nobody opens."""
    base, _ = server
    got = get(base + "/partial/lexicon/ckt%3AUwe%CB%8Alen")
    assert "/uːweːleːn/" in got
    assert "imputed" in got
    assert "class='speak'" in got


def test_a_partial_imputation_is_shown_and_names_what_it_could_not_read(server):
    """Withholding it would say the form is unpronounceable, when what is true
    is that no rule reaches one of its letters."""
    base, _ = server
    got = get(base + "/partial/lexicon/ckt%3APo%C5%A1a")
    assert "partial" in got and "no rule reaches" in got


@pytest.mark.skipif(shutil.which(speech.ESPEAK) is None,
                    reason="espeak-ng is not installed")
def test_the_speaker_endpoint_returns_a_wav(server):
    base, _ = server
    r = _client().get(base + "/tts/u%CB%90we%CB%90le%CB%90n.wav")
    assert r.headers["content-type"] == "audio/wav"
    assert r.content[:4] == b"RIFF"


def test_the_atlas_lists_only_located_roots(server):
    """Without the scope every person and source in the store is an atlas root,
    and the tree becomes the encyclopedia index with worse navigation."""
    base, root = server
    entry(root, "person:nobody", aliases=[("Nobody", False)])
    got = get(base + "/atlas")
    assert "Nobody" not in got


def test_the_atlas_travels_as_facts_the_store_already_answers(server):
    """The browser composes maps, so the store's answers travel — each from
    the function that owns the rule, never a rule for the browser to re-run."""
    import json

    base, root = server
    entry(root, "place:parent", aliases=[("P", False)])
    p = root / "edition" / "entities" / "place" / "kid.md"
    p.write_text("# place:kid — Kid\n\n- status: ratified\n- since: 1-021\n"
                 "- within: place:parent\n- geo: 66.0 170.0\n\n## aliases\n\n"
                 "| form | lang | auto | note |\n|---|---|---|---|\n\n## gloss\n\nx\n",
                 encoding="utf-8")
    ents = json.loads(get(base + "/geo/atlas.json"))["entities"]
    kid, parent = ents["place:kid"], ents["place:parent"]
    assert kid["parent"] == "place:parent" and kid["ancestors"] == ["place:parent"]
    assert parent["children"] == ["place:kid"]
    assert kid["points"] == [[170.0, 66.0]]            # lon first, in the window
    assert parent["own"] == kid["own"]                 # framed by what is beneath
    assert parent["basis"] == {"kind": "framed"}


def test_a_shape_is_addressed_by_its_id_and_an_unknown_one_is_a_404(server):
    base, _ = server
    with pytest.raises(HTTPError, match="404"):
        get(base + "/geo/shape/watershed:nowhere.json")


def test_a_string_with_nothing_speakable_in_it_is_a_400_not_a_crash(server):
    """The endpoint is a pure function of the URL and does not check that the
    IPA is one this edition imputed, so it has to answer for anything."""
    base, _ = server
    assert _client().get(base + "/tts/%E2%96%A1%E2%96%A1.wav").status_code == 400


def test_a_key_nothing_answers_to_is_refused(server):
    """Refused on what the corpus knows, not on the key's shape. Any string
    could be a Tier-1 form, so there is nothing here to validate — and a card
    that rendered an arbitrary one as a headword, with an imputed pronunciation
    under it, would be inventing a word."""
    base, _ = server
    assert "Nothing in the lexicon" in get(base + "/partial/lexicon/xx%3Afoo")
    assert "Nothing in the lexicon" in get(base + "/partial/lexicon/notaform")


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
PROJECT = REPO / "jesup" / "bogoras-chukchi"
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _gt(root: Path, ref: str, lines: list[str]) -> None:
    """A ground-truth page, plus the committed fold table `lookup.index` needs.

    The real `config/marks.json` and not a copy of one: the fold is what
    decides whether two settings are one word, and a test writing its own would
    be asserting against a table nothing in the corpus uses.
    """
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy(PROJECT / "config" / "marks.json", root / "config")
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
    got = get(base + "/partial/lexicon/Kulu'c^i")
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
        got = get(base + "/partial/lexicon/" + quote(key, safe=""))
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
    got = get(base + "/partial/lexicon/kee%5Elin")
    assert "more than one form" in got
    assert unicodedata.normalize("NFD", "keᵋlin") in got
    assert unicodedata.normalize("NFD", "keᵉlin") in got


def test_the_key_is_case_sensitive_where_a_filename_could_not_be(server):
    """`Aiˊwan` and `aiˊwan` are both this corpus's and key to `Ai'wan` and
    `ai'wan`. A URL keeps them apart; the filesystem the store is *filed* on may
    not, which is why the slug is authored and the key is only the address."""
    base, root = server
    _gt(root, "1-042", ["the Aiˊwan came", "and the aiˊwan went"])
    upper = get(base + "/partial/lexicon/Ai'wan")
    lower = get(base + "/partial/lexicon/ai'wan")
    assert "more than one form" not in upper
    assert unicodedata.normalize("NFD", "Aiˊwan") in upper
    assert unicodedata.normalize("NFD", "aiˊwan") in lower


def test_the_index_lists_every_language_and_the_unjudged(server):
    """Every one of the Tier-1 codes whether or not it holds anything, on the
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
    (root / "edition" / "lexicon").mkdir(parents=True, exist_ok=True)
    (root / "edition" / "lexicon" / "kulu-c-i.md").write_text(
        "# Kuluˊči\n\n- status: proposed\n- since: 1-042\n\n"
        "## editor's note\n\nA bay on the [[place:markova]] side.\n",
        encoding="utf-8")
    got = get(base + "/partial/lexicon/Kulu'c^i")
    assert "A bay on the" in got
    assert "No editor's note" not in got
