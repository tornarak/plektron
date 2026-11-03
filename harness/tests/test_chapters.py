"""Chapter runs: spans derived from the milestones, and the page that serves one.

The span is a function of two things the book prints — the ToC's order of
chapters and the leaf each chapter's head is on — so what is held here is that it
is computed from exactly those, refuses where they do not settle it, and that a
chapter renders each leaf as that leaf renders alone.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from test_edition import draft, page

from harness import apparatus, chapters


def _toc(root: Path, *ids: str) -> None:
    """A ToC of chapters only, numbered I, II, … in the order given."""
    romans = ["I", "II", "III", "IV", "V"]
    root.joinpath("edition").mkdir(parents=True, exist_ok=True)
    root.joinpath("edition", "toc.json").write_text(json.dumps({"entries": [
        {"level": 1, "chapter": romans[i], "number": romans[i],
         "title": f"Chapter {romans[i]}", "page_start": 10 * (i + 1), "id": cid}
        for i, cid in enumerate(ids)]}), encoding="utf-8")


def _opens(cid: str, before: str = "") -> str:
    return f'<pb n="1"/>{before}<milestone unit="chapter" n="{cid}" resp="#mz"/><p>Text.</p>'


def _at(body: str, ident: str) -> int:
    """Where the element with this id starts, whichever quote it was written with:
    a mark is macro output, or lxml's serialization inside a joined paragraph."""
    m = re.search(rf"""id=["']{re.escape(ident)}["']""", body)
    assert m, f"no element with id {ident!r}"
    return m.start()


def _exempt(root: Path, *refs: str, kind: str = "plate") -> None:
    p = root / "gt" / "zones" / f"_{kind}.lst"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(f"chukchi-{r}.xml\n" for r in refs), encoding="utf-8")


# ------------------------------------------------------------------- the span


def test_a_span_runs_from_one_opener_to_the_leaf_before_the_next(tmp_path):
    """Pure arithmetic over scan indices, and a leaf with no text in between — a
    plate — is in the chapter because the binding put it there."""
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>More.</p>')
    _exempt(tmp_path, "1-005")                       # a plate, no TEI at all
    page(tmp_path, "1-006", _opens("chII"))
    page(tmp_path, "1-007", '<pb n="4"/><p>End.</p>')
    runs, problems = chapters.derive(tmp_path)
    assert problems == []
    assert [(r["id"], r["refs"]) for r in runs] == [
        ("chI", ["1-003", "1-004", "1-005"]),
        ("chII", ["1-006", "1-007"])]
    assert runs[0]["kind"] == "chapter" and runs[0]["title"] == "I. Chapter I"


def test_the_last_chapter_of_a_part_ends_at_its_last_text_leaf(tmp_path):
    """What follows is the binding's — blanks, the back cover — and a chapter
    claiming those claims leaves nothing places in it. And a chapter never
    crosses a part: the next part's opener ends nothing in this one."""
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-009", '<pb n="9"/><p>Last.</p>')
    page(tmp_path, "2-003", _opens("chII"))
    runs, _ = chapters.derive(tmp_path)
    assert runs[0]["refs"][-1] == "1-009"
    assert runs[1]["refs"] == ["2-003"]


def test_a_draft_opener_counts_and_the_signed_page_wins(tmp_path):
    """Where a chapter is, is a fact about the text and not about who has read
    it, so a draft's milestone places it. But the signed page is the text where
    there is one: a collator who moved the head moves the chapter."""
    _toc(tmp_path, "chI", "chII")
    draft(tmp_path, "1-003", _opens("chI"))
    draft(tmp_path, "1-005", _opens("chII"))          # the generator's guess
    page(tmp_path, "1-005", '<pb n="3"/><p>No head here after all.</p>')
    page(tmp_path, "1-006", _opens("chII"))
    runs, problems = chapters.derive(tmp_path)
    assert problems == []
    assert runs[0]["refs"] == ["1-003", "1-004", "1-005"]


def test_a_leaf_with_text_before_the_head_is_shared(tmp_path):
    """The previous chapter's tail on the opener's own leaf: the leaf is the last
    of one chapter and the first of the next, and each says so."""
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", _opens("chII", before="<p>The end of one.</p>"))
    runs, _ = chapters.derive(tmp_path)
    assert runs[0]["refs"] == ["1-003", "1-004"] and runs[0]["tail_shared"]
    assert runs[1]["refs"] == ["1-004"] and runs[1]["head_shared"]


def test_the_header_and_comments_are_not_text_before_the_head(tmp_path):
    """`preceding::` reaches the teiHeader, and the generator writes comments
    above the first block; neither is a previous chapter's prose."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI", before="<!-- zone-opens: fresh -->"))
    (run,), _ = chapters.derive(tmp_path)
    assert not run["head_shared"]


def test_a_missing_opener_derives_neither_it_nor_the_chapter_before(tmp_path):
    """The chapter before ends where the missing one starts, so its end is
    unknown too. Both stay served a leaf at a time — a span that guessed would
    put one chapter's text under another's title, and look like one that had
    not."""
    _toc(tmp_path, "chI", "chII", "chIII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-008", _opens("chIII"))
    runs, problems = chapters.derive(tmp_path)
    assert [r["id"] for r in runs] == ["chIII"]
    assert {(p["chapter"], p["rule"]) for p in problems} == {
        ("chI", "no-end"), ("chII", "no-opener")}


def test_a_chapter_opened_twice_is_refused(tmp_path):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-009", _opens("chI"))
    runs, problems = chapters.derive(tmp_path)
    assert runs == [] and problems[0]["rule"] == "no-opener"
    assert "1-003" in problems[0]["detail"] and "1-009" in problems[0]["detail"]


def test_the_gate_reports_an_underived_chapter(tmp_path):
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    errors = apparatus.check(tmp_path)["errors"]
    assert {e["rule"] for e in errors} >= {"chapter-no-end", "chapter-no-opener"}


# ---------------------------------------------------------------- the locator


def test_a_heading_link_lands_on_the_heading(tmp_path):
    """The milestone is the heading, so the ToC link lands on it rather than at
    the top of its leaf — and answers where the folio index has no witness."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>x</p>')
    out = apparatus.locate(tmp_path, toc_id="chI", index={})
    assert (out["url"], out["anchor"]) == ("/chapter/i/chapter-i", "i-chapter-i")
    out = apparatus.locate(tmp_path, ref="1-004", index={})
    assert (out["url"], out["anchor"]) == ("/chapter/i/chapter-i", "leaf-1-004")


# --------------------------------------------------------------- the view


@pytest.fixture
def client(tmp_path):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    def make(drafts: bool = False):
        return TestClient(create_app(tmp_path, Sessions(root=tmp_path),
                                     editor="edition", drafts=drafts))
    return make


def test_the_contents_links_a_heading_into_its_chapter(tmp_path, client):
    """A ToC row links to the heading itself, inside the run that holds it, and
    needs no folio witness to: neither page here prints a folio the index knows,
    and before this the row was no link at all."""
    root = tmp_path
    root.joinpath("edition").mkdir(parents=True, exist_ok=True)
    root.joinpath("edition", "toc.json").write_text(json.dumps({"entries": [
        {"level": 1, "chapter": "I", "number": "I", "title": "One",
         "page_start": 10, "id": "chI"},
        {"level": 2, "chapter": "I", "title": "Names", "page_start": 11,
         "id": "chI.1"}]}), encoding="utf-8")
    page(root, "1-003", '<pb/><milestone unit="chapter" n="chI" resp="#mz"/><p>a</p>')
    page(root, "1-004", '<pb/><milestone unit="section" n="chI.1" resp="#mz"/><p>b</p>')
    body = client().get("/edition/chapter/i/one").text
    assert "href='/edition/chapter/i/one#names'" in body
    assert "href='/edition/chapter/i/one#i-one'" in body


def test_a_leaf_redirects_into_its_chapter(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>x</p>')
    r = client().get("/edition/page/1-004", follow_redirects=False)
    assert r.headers["location"] == "/edition/chapter/i/chapter-i#leaf-1-004"


def test_notes_are_scoped_to_their_leaf(tmp_path, client):
    """Every leaf numbers its notes from 1; in one document two `note-1`s send
    every marker to the first."""
    _toc(tmp_path, "chI")
    for ref in ("1-003", "1-004"):
        page(tmp_path, ref,
             ('<milestone unit="chapter" n="chI" resp="#mz"/>' if ref == "1-003"
              else "")
             + '<pb n="1"/><p>A<ref type="note" n="1">¹</ref>.</p>'
               '<note n="1" place="bottom">The note.</note>')
    body = client().get("/edition/chapter/i/chapter-i").text
    for ref in ("1-003", "1-004"):
        assert f'id="ref-{ref}-1" href="#note-{ref}-1"' in body
        assert f"id='note-{ref}-1'" in body
    assert 'href="#note-1"' not in body
    # **Pooled in one foot after the text, grouped by leaf, numbered as printed.**
    foot = body[body.index("id='foot'"):]
    assert body.index("id='foot'") > _at(body, "leaf-1-004")
    assert foot.count("class='foot-leaf'") == 2
    assert foot.index("note-1-003-1") < foot.index("note-1-004-1")
    assert ">1</a>" in foot and ">2</a>" not in foot


def test_notices_and_supplements_are_pooled_once(tmp_path, client):
    """A notice on two leaves of the chapter is shown once, above the text; a
    supplement once, below it."""
    from test_annotation_render import annotation
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>Second leaf.</p>')
    annotation(tmp_path, "notice", "warn", attaches=("page:1-003", "page:1-004"),
               title="Careful", links="", summary="Mind this.")
    annotation(tmp_path, "supplement", "more", attaches=("page:1-004",),
               title="Further", links="", summary="And this.")
    body = client().get("/edition/chapter/i/chapter-i").text
    assert body.count("id='ann-notice:warn'") == 1
    assert body.count("id='ann-supplement:more'") == 1
    assert body.index("ann-notice:warn") < _at(body, "leaf-1-003")
    assert body.index("ann-supplement:more") > body.index("Second leaf.")


def test_a_shared_leaf_greys_the_other_chapters_part_and_links_to_it(tmp_path, client):
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", _opens("chII", before="<p>Tail of one.</p>"))
    c = client()
    one, two = c.get("/edition/chapter/i/chapter-i").text, c.get("/edition/chapter/ii/chapter-ii").text
    # In chapter I the leaf's own text is the tail; chapter II's opening is grey.
    assert "continues in II. Chapter II" in one
    assert "/edition/chapter/ii/chapter-ii#ii-chapter-ii" in one
    # In chapter II the tail is grey, and links back to the leaf in chapter I.
    assert "← from I. Chapter I" in two
    assert "/edition/chapter/i/chapter-i#leaf-1-004" in two
    grey = two[two.index("<div class='other-text'>"):two.index('id="chII"')]
    assert "Tail of one." in grey
    # And the leaf opens chapter II, so *next* from chapter I goes there rather
    # than redirecting back into the chapter it left.
    r = c.get("/edition/page/1-004", follow_redirects=False)
    assert r.headers["location"] == "/edition/chapter/ii/chapter-ii#leaf-1-004"


# -------------------------------------------------------- readable addresses


@pytest.mark.parametrize("title,want", [
    ("Hunting and Fishing; War", "hunting-and-fishing-war"),
    ("Family, Marriage", "family-marriage"),
    ("Taˊn˙ñɪn Wars", "tannɪn-wars"),          # marks gone, a base letter kept
    ("Ke'let", "kelet"),                          # an apostrophe joins, not splits
    ("Other “Beings”", "other-beings"),
])
def test_a_title_slugs_by_one_rule(title, want):
    assert chapters.slugify(title) == want


def test_a_chapters_slug_leads_with_its_roman():
    entry = {"level": 1, "chapter": "VI", "number": "VI",
             "title": "Hunting and Fishing; War", "id": "chVI"}
    assert chapters.slug(entry) == "vi/hunting-and-fishing-war"
    assert chapters.url(entry) == "/chapter/vi/hunting-and-fishing-war"
    assert chapters.heading(entry) == "vi-hunting-and-fishing-war"


def _sectioned(root: Path, *entries: tuple[int, str, str, str]) -> list[dict]:
    """A ToC of `(level, chapter, title, id)` rows, written and returned."""
    toc = [{"level": lv, "chapter": ch, "number": ch if lv == 1 else None,
            "title": t, "page_start": 10, "id": i} for lv, ch, t, i in entries]
    root.joinpath("edition").mkdir(parents=True, exist_ok=True)
    root.joinpath("edition", "toc.json").write_text(json.dumps({"entries": toc}),
                                                    encoding="utf-8")
    return toc


def test_a_title_twice_is_told_apart_by_what_holds_it(tmp_path):
    """Twins under two parents take their parents' slugs; twins in two chapters
    part on the roman, even where the parents' titles are one word too."""
    toc = _sectioned(
        tmp_path,
        (1, "I", "Trade", "chI"), (2, "I", "Anui Fair", "chI.1"),
        (2, "I", "Reindeer", "chI.2"), (3, "I", "Races", "chI.2.1"),
        (2, "I", "Maritime", "chI.3"), (3, "I", "Races", "chI.3.1"),
        (1, "II", "Wars", "chII"), (2, "II", "Trade", "chII.1"),
        (3, "II", "Anui Fair", "chII.1.1"))
    frags, collisions = chapters.fragments(toc)
    assert collisions == []
    assert frags["chI.2.1"] == "reindeer-races"
    assert frags["chI.3.1"] == "maritime-races"
    assert frags["chI.1"] == "i-trade-anui-fair"
    assert frags["chII.1.1"] == "trade-anui-fair"
    assert frags["chI"] == "i-trade" and frags["chI.2"] == "reindeer"


def test_twins_nothing_tells_apart_keep_their_ids_and_are_reported(tmp_path):
    """Two `Names` in one section: no ancestor parts them, and neither may have
    the address by being first."""
    toc = _sectioned(tmp_path, (1, "I", "One", "chI"),
                     (2, "I", "Names", "chI.1"), (2, "I", "Names", "chI.2"))
    frags, collisions = chapters.fragments(toc)
    assert (frags["chI.1"], frags["chI.2"]) == ("chI.1", "chI.2")
    assert [c["toc_id"] for c in collisions] == ["chI.1", "chI.2"]
    errors = apparatus.check(tmp_path)["errors"]
    assert {e["run"] for e in errors if e["rule"] == "fragment-collision"} == {
        "chI.1", "chI.2"}


def test_a_heading_carries_its_fragment_and_its_old_id(tmp_path, client):
    """The old id stands just before the heading, so a `#chI.1` already out in the
    world still lands on it."""
    _toc_with_sections(tmp_path)
    page(tmp_path, "1-003", _opens("chI") + '<milestone unit="section" n="chI.1" '
                                            'resp="#mz"/><p>Text.</p>')
    body = client().get("/edition/chapter/i/names-and-habitat").text
    assert ('<span class="milestone legacy" id="chI.1"></span>'
            '<h2 class="milestone section" id="names">') in body
    assert '<span class="milestone legacy" id="chI"></span>' in body
    assert 'id="i-names-and-habitat"' in body


def test_a_chapters_old_addresses_forward_to_its_name(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    c = client()
    r = c.get("/edition/run/chI", follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (302, "/edition/chapter/i/chapter-i")
    for name in ("I", "i", "i/a-title-since-amended", "I/chapter-i", "i/CHAPTER-I"):
        r = c.get(f"/edition/chapter/{name}", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (
            302, "/edition/chapter/i/chapter-i#i-chapter-i"), name
    r = c.get("/edition/chapter/i/chapter-i", follow_redirects=False)
    assert r.status_code == 200 and "Text." in r.text


def test_an_underived_chapters_name_does_not_forward_to_itself(tmp_path, client):
    """Chapter II never opens, so chapter I has no end and no run: its name is
    not a page, and resolves as its roman does — to the leaf its head is on."""
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    c = client()
    for name in ("i/chapter-i", "I"):
        r = c.get(f"/edition/chapter/{name}", follow_redirects=False)
        assert r.headers["location"] == "/edition/page/1-003#i-chapter-i", name


@pytest.mark.parametrize("name", ["IX", "ix/chapter-ix", "zz/nothing", "i-chapter-i", ""])
def test_a_name_the_contents_does_not_hold_is_refused(tmp_path, client, name):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    r = client().get(f"/edition/chapter/{name}", follow_redirects=False)
    assert r.status_code == 404


def test_shared_text_is_titled_by_the_tocs_neighbour_across_a_gap(tmp_path, client):
    """Chapter III has no opener, so neither it nor II derives. IV's first leaf carries
    III's tail, and the nearest derived chapter, I, must not be credited with it."""
    _toc(tmp_path, "chI", "chII", "chIII", "chIV")
    page(tmp_path, "1-001", _opens("chI"))
    page(tmp_path, "1-003", _opens("chII"))
    page(tmp_path, "1-006", _opens("chIV", before="<p>Tail of three.</p>"))
    body = client().get("/edition/chapter/iv/chapter-iv").text
    # A label and no link: the neighbour has no run to send a reader to.
    assert "<span class='other-label'>← from III. Chapter III</span>" in body
    assert "← from I. Chapter I" not in body
    grey = body[body.index("<div class='other-text'>"):body.index('id="chIV"')]
    assert "Tail of three." in grey


def test_a_chapter_with_no_text_of_its_own_derives_no_run(tmp_path):
    """Its head and the next one's stand together, so there is nothing between them
    and the arithmetic would give a run of no leaves, which every reader indexes."""
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", '<pb n="1"/><milestone unit="chapter" n="chI" resp="#mz"/>'
                            '<milestone unit="chapter" n="chII" resp="#mz"/><p>Text.</p>')
    runs, problems = chapters.derive(tmp_path)
    assert [r["id"] for r in runs] == ["chII"]
    assert [(p["chapter"], p["rule"]) for p in problems] == [("chI", "no-text")]


def test_sweeps_over_the_text_reach_the_inside_of_a_chapter(tmp_path, client):
    """A chapter is one entry in the listing and many leaves of text. Search and an
    entity's mentions are about the text, so neither may walk the listing."""
    from test_entities import entry

    entry(tmp_path, "place:markova", aliases=[("Markova", True)])
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>walrus at '
                            '<rs ref="place:markova" resp="#mz">Markova</rs>.</p>')
    c = client()
    assert "/edition/page/1-004" in c.get("/edition/search?q=walrus").text
    assert "/page/1-004" in c.get("/edition/entity/place:markova").text


def test_the_index_counts_leaves_and_not_the_listing(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>More.</p>')
    _exempt(tmp_path, "1-001", kind="cover")
    assert "2 pages collated" in client().get("/edition/").text


def test_a_division_between_two_on_one_leaf_keeps_its_row(tmp_path, client):
    """I and III land on one leaf and II on none: the Contents still shows II."""
    _toc(tmp_path, "chI", "chII", "chIII")
    page(tmp_path, "1-003", '<pb n="1"/><milestone unit="chapter" n="chI" resp="#mz"/>'
                            '<p>a</p><milestone unit="chapter" n="chIII" resp="#mz"/><p>b</p>')
    assert "Chapter II<" in client().get("/edition/").text


def test_the_search_cap_holds_across_pages_and_says_so(tmp_path, client):
    for i in range(3, 8):
        page(tmp_path, f"1-{i:03d}", f'<pb n="{i}"/><p>{"walrus " * 90}</p>')
    body = client().get("/edition/search?q=walrus").text
    assert body.count("<mark>") == 200 and "the first 200 in the text" in body


def _paras(body: str) -> list[str]:
    """The article's paragraphs, as text with tags stripped."""
    art = body[body.index("run-chapter"):body.index("</article>")]
    # The page mark is drawn in the margin, not read as part of the sentence.
    art = re.sub(r"""<span class=["']leaf-at["'].*?</a>(<span class=["']run-tag["']>[^<]*</span>)?</span>""",
                 "", art, flags=re.S)
    return [re.sub(r"<[^>]+>", "", p).split() for p in
            re.findall(r"<p\b[^>]*>(.*?)</p>", art, re.S)]


def test_a_paragraph_the_leaf_break_cut_is_one_paragraph(tmp_path, client):
    """The next leaf's own witness says it continues — here the zone label, the
    draft's `zone-opens: continued` — so the two halves are one `<p>`, and the
    page mark stands inside it at the turn, as Project Gutenberg sets one."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI") + "<p>The reindeer of the</p>")
    page(tmp_path, "1-004", '<pb n="2"/><!-- zone-opens: continued (z) -->'
                            "<p>tundra are small.</p><p>A new one.</p>")
    body = client().get("/edition/chapter/i/chapter-i").text
    paras = _paras(body)
    assert ["The", "reindeer", "of", "the", "tundra", "are", "small."] in paras
    assert ["A", "new", "one."] in paras
    # The page mark stands inside the paragraph, exactly at the turn.
    at = _at(body, "leaf-1-004")
    assert body.rindex("of the", 0, at) > body.rindex("<p", 0, at)
    assert body.index("tundra", at) < body.index("</p>", at)


def test_a_fresh_paragraph_is_not_joined(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI") + "<p>Ends here.</p>")
    page(tmp_path, "1-004", '<pb n="2"/><!-- zone-opens: fresh (z) -->'
                            "<p>Begins here.</p>")
    paras = _paras(client().get("/edition/chapter/i/chapter-i").text)
    assert ["Ends", "here."] in paras
    assert not any("Ends" in p and "Begins" in p for p in paras)


def test_a_plate_between_the_halves_moves_above_the_paragraph(tmp_path, client):
    """`tei generate`'s rule for a figure the prose runs past, one level up: the
    plate goes to the top of the paragraph it interrupted."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI") + "<p>Half of a</p>")
    _exempt(tmp_path, "1-004")
    page(tmp_path, "1-005", '<pb n="2"/><!-- zone-opens: continued (z) -->'
                            "<p>sentence.</p>")
    body = client().get("/edition/chapter/i/chapter-i").text
    assert any(p[:3] == ["Half", "of", "a"] and "sentence." in p for p in _paras(body))
    assert _at(body, "leaf-1-004") < body.index("Half of a")


def _turn(left: str, right: str, idx: dict) -> tuple[bool, str]:
    """`_turn_word` over two paragraphs' markup: whether it acted, and the text."""
    from lxml import html as LH

    from harness.web.edition import _turn_word
    a, b = LH.fragment_fromstring(left), LH.fragment_fromstring(right)
    done = _turn_word(a, b, "1-004", idx)
    return done, a.text_content() + "|" + b.text_content()


#: The corpus the rule counts against: `form → (mid-line count, refs setting it)`.
_IDX = {"considerable": (40, frozenset({"1-010", "1-011"})),
        "birth-water": (3, frozenset({"1-020"})),
        "springtime": (6, frozenset({"1-030"})),
        "spring-time": (6, frozenset({"1-031"}))}


def test_a_word_the_page_turn_cut_is_closed_by_the_line_end_rule():
    """The corpus sets `considerable` mid-line and never `consider-able`."""
    assert _turn("<p>a very consider-</p>", "<p>able distance.</p>", _IDX) == (
        True, "a very considerable| distance.")


def test_a_compound_the_corpus_sets_hyphenated_keeps_its_hyphen():
    """`birth-water`: set whole, hyphen and all, with no space in the middle."""
    assert _turn("<p>the birth-</p>", "<p>water is</p>", _IDX) == (
        True, "the birth-water| is")


def test_a_word_the_corpus_sets_both_ways_keeps_the_hyphen():
    """The generator's `open` verdict: nothing left to compare, so nothing is
    removed — the hyphen the print set stays."""
    assert _turn("<p>in the spring-</p>", "<p>time they</p>", _IDX) == (
        True, "in the spring-time| they")


def test_a_form_bearing_the_notation_is_never_closed():
    """The firewall's refusal, before any count: `taˊn-` is not English."""
    idx = {"taˊnñɪtan": (9, frozenset({"1-050"}))}
    done, text = _turn("<p>called taˊn-</p>", "<p>ñɪtan by</p>", idx)
    assert "taˊn-ñɪtan" in text


def test_a_half_inside_an_element_is_left_alone():
    """Closing it would move text across an element boundary — a restructuring,
    and no rule here has the standing to do it."""
    done, _ = _turn('<p>the <a class="ent">Chuk-</a></p>', "<p>chee are</p>", _IDX)
    assert not done


def test_a_gap_is_never_joined_across(tmp_path, client):
    """Nothing says what an unread leaf's text did, so the paragraph before it
    stays closed."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI") + "<p>Half of a</p>")
    draft(tmp_path, "1-004", '<pb n="2"/><p>hidden</p>')
    page(tmp_path, "1-005", '<pb n="3"/><!-- zone-opens: continued (z) -->'
                            "<p>sentence.</p>")
    paras = _paras(client().get("/edition/chapter/i/chapter-i").text)
    assert not any("Half" in p and "sentence." in p for p in paras)


def test_an_unreadable_leaf_is_a_gap_said_in_place(tmp_path, client):
    """A draft leaf with drafts hidden. The chapter still renders; the leaf says
    what it is and where the scan is, rather than the text closing over it."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    draft(tmp_path, "1-004", '<pb n="2"/><p>Unread.</p>')
    page(tmp_path, "1-005", '<pb n="3"/><p>Read.</p>')
    body = client().get("/edition/chapter/i/chapter-i").text
    assert "Unread." not in body and "Read." in body
    assert "leaf-tag'>gap" in body and "/edition/page/1-004.png" in body
    assert "Unread." in client(drafts=True).get("/edition/chapter/i/chapter-i").text


def test_the_listing_keeps_a_chapter_whose_opener_is_unread(tmp_path, client):
    """The head stands for the run whenever any leaf of it can be shown, or the
    whole chapter would drop out of the listing for want of its first leaf."""
    _toc(tmp_path, "chI")
    draft(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>x</p>')
    body = client().get("/edition/").text
    assert "1-003" in body
    assert "/edition/page/1-004" not in body


# ------------------------------------------------------------- the outline


def _toc_with_sections(root: Path) -> None:
    """Chapter I with a section and a subsection under it, and chapter II."""
    root.joinpath("edition").mkdir(parents=True, exist_ok=True)
    root.joinpath("edition", "toc.json").write_text(json.dumps({"entries": [
        {"level": 1, "chapter": "I", "number": "I", "title": "Names and Habitat",
         "page_start": 10, "id": "chI"},
        {"level": 2, "chapter": "I", "number": None, "title": "Names",
         "page_start": 10, "id": "chI.1"},
        {"level": 3, "chapter": "I", "number": None, "title": "Ancient Names",
         "page_start": 11, "id": "chI.1.1"},
        {"level": 1, "chapter": "II", "number": "II", "title": "Trade",
         "page_start": 20, "id": "chII"},
    ]}), encoding="utf-8")


def _li(body: str, marker: str) -> str:
    """The outline row that contains `marker`: from its `<li class='ol-…'>` to
    the next row's, since a chapter's row holds its sections' `<li>`s."""
    outline = body.split("<ul class='outline'>")[1].split("</div>")[0]
    items = re.split(r"(?=<li class='ol-)", outline)[1:]
    hits = [it for it in items if marker in it]
    assert len(hits) == 1, f"{len(hits)} rows carry {marker!r}"
    return hits[0]


def test_the_index_nests_a_chapters_sections_under_its_row(tmp_path, client):
    """The index is the printed Contents in the binding's order: a chapter's
    row links to its run and carries its sections, nested as the Contents
    nests them, rather than standing as a scan number with a title beside it."""
    _toc_with_sections(tmp_path)
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-005", _opens("chII"))
    body = client().get("/edition/").text
    row = _li(body, "Names and Habitat")
    assert "href='/edition/chapter/i/names-and-habitat'" in row
    assert "<span class='toc-num'>I.</span>" in row
    assert "toc-d2" in row and ">Names<" in row
    assert "toc-d3" in row and "Ancient Names" in row
    # And the sections are the chapter's, not the next chapter's.
    assert "Trade" not in row
    assert body.index("Names and Habitat") < body.index(" Trade</a>")


def test_a_chapter_with_nothing_collated_still_stands_in_the_outline(tmp_path, client):
    """The listing drops a chapter no leaf of which can be shown, so prev/next
    never walk into it; the Contents still has it, so the outline shows it with
    its count and sends a reader to the run, where every leaf is a gap."""
    _toc(tmp_path, "chI", "chII")
    draft(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>x</p>')
    draft(tmp_path, "1-005", _opens("chII"))
    body = client().get("/edition/").text
    row = _li(body, "Chapter II<")
    assert "href='/edition/chapter/ii/chapter-ii'" in row
    assert "0 of 1 collated" in row
    assert "1 of 2 collated" in _li(body, "Chapter I<")


def test_a_division_nothing_places_keeps_its_place_and_says_so(tmp_path, client):
    """Chapter III opens nowhere, so neither it nor chapter II derives a run.
    Chapter II is still *placed* — its milestone opens it on 1-005, and the
    row sits on that page. Chapter III is placed by nothing: it is listed where
    the Contents puts it, after II, marked unlocated, with no leaf claimed."""
    _toc(tmp_path, "chI", "chII", "chIII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-005", _opens("chII"))
    body = client().get("/edition/").text
    assert "href='/edition/chapter/i/chapter-i'" in body
    two, three = _li(body, "Chapter II<"), _li(body, "Chapter III<")
    assert two.startswith("<li class='ol-page'>")
    assert "href='/edition/page/1-005'" in two and "not located" not in two
    assert three.startswith("<li class='ol-toc'>")
    assert "not located" in three and "href=" not in three
    assert body.index("Chapter I<") < body.index("Chapter II<") < body.index("Chapter III<")


def test_a_leaf_that_is_not_text_is_never_a_draft(tmp_path, client):
    """A cover cannot be collated, and the Contents is a store; tagging either
    `draft` said something false about them to say something true about the
    pages. The tag belongs to a text page alone."""
    _toc(tmp_path, "chI")
    _exempt(tmp_path, "1-001", kind="cover")
    draft(tmp_path, "1-003", _opens("chI"))
    draft(tmp_path, "1-002", '<pb n="1"/><p>front matter</p>')
    body = client(drafts=True).get("/edition/").text
    cover = _li(body, ">1-001<")
    assert "alt='cover, scan 1-001'" in cover and "draft-tag" not in cover
    assert "draft-tag'>uncollated" in _li(body, ">1-002<")
    assert "0 of 1 collated" in _li(body, "Chapter I<")


def test_the_outline_heads_each_part(tmp_path, client):
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "2-003", _opens("chII"))
    body = client().get("/edition/").text
    assert "<h4>Part 1</h4>" in body and "<h4>Part 2</h4>" in body
    assert body.index("Part 1") < body.index("Chapter I<") \
        < body.index("Part 2") < body.index("Chapter II")


# ---------------------------------------------------------- the outline's rows


def _front(root: Path, *entries: tuple[str, int]) -> None:
    """A ToC of level-0 divisions, which the folio index places: no run derives
    from one, so each stands on a page row."""
    root.joinpath("edition").mkdir(parents=True, exist_ok=True)
    root.joinpath("edition", "toc.json").write_text(json.dumps({"entries": [
        {"level": 0, "chapter": None, "number": None, "title": title,
         "page_start": at, "id": f"front.{title.lower()}"}
        for title, at in entries]}), encoding="utf-8")


def _raster(root: Path, ref: str, size: tuple[int, int] = (1000, 1400)) -> None:
    from PIL import Image
    p = root / "scans" / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", size, 255).save(p)


def test_a_blank_leaves_the_outline_and_stays_in_the_walk(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-001", '<pb n="1"/><p>x</p>')
    _exempt(tmp_path, "1-002", kind="blank")
    page(tmp_path, "1-003", _opens("chI"))
    c = client()
    outline = c.get("/edition/").text.split("<ul class='outline'>")[1]
    assert "1-002" not in outline
    assert c.get("/edition/page/1-002").status_code == 200
    assert "/edition/page/1-002" in c.get("/edition/page/1-001").text


def test_a_blank_with_a_division_on_it_keeps_its_row(tmp_path, client):
    """Dropping it would drop a Contents entry with it."""
    _front(tmp_path, ("Intro", 1))
    page(tmp_path, "1-021", '<pb n="1"/><p>x</p>')
    _exempt(tmp_path, "1-021", kind="blank")
    row = _li(client().get("/edition/").text, "Intro<")
    assert row.startswith("<li class='ol-leaf'>") and "1-021" in row


def test_covers_share_a_row_across_a_blank_and_not_across_a_part(tmp_path, client):
    _toc(tmp_path, "chI")
    _exempt(tmp_path, "1-001", "1-003", "2-001", kind="cover")
    _exempt(tmp_path, "1-002", kind="blank")
    page(tmp_path, "1-004", _opens("chI"))
    body = client().get("/edition/").text
    first = _li(body, ">1-001<")
    assert first.startswith("<li class='ol-covers'") and ">1-003<" in first
    assert ">2-001<" in _li(body, "/thumb/2-001.jpg") and ">2-001<" not in first
    assert "src='/edition/thumb/1-003.jpg'" in first
    # Each opens its scan over the page, and the row is one set to walk.
    assert "data-lightbox-group" in first
    assert "data-lightbox='/edition/page/1-003.png'" in first


def test_a_cover_with_a_division_on_it_is_a_row_of_its_own(tmp_path, client):
    _front(tmp_path, ("Intro", 1))
    page(tmp_path, "1-021", '<pb n="1"/><p>x</p>')
    _exempt(tmp_path, "1-021", kind="cover")
    row = _li(client().get("/edition/").text, "Intro<")
    assert row.startswith("<li class='ol-leaf'>")
    assert "ol-thumb-cover" in row and "/edition/thumb/1-021.jpg" in row


def test_the_map_is_a_picture_on_its_row(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    _exempt(tmp_path, "1-005", kind="map")
    row = _li(client().get("/edition/").text, ">1-005<")
    assert "ol-thumb-map" in row and "/edition/thumb/1-005.jpg" in row


def test_the_bar_links_the_books_map_where_it_has_one(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    assert ">Map</a>" not in client().get("/edition/").text
    _exempt(tmp_path, "1-005", kind="map")
    body = client().get("/edition/").text
    assert "href='/edition/page/1-005'>Map</a>" in body
    # The bar and the thumbnail both open it over the page, as the scan here.
    assert body.count("data-lightbox='/edition/page/1-005.png'") == 2


def test_the_map_opens_as_its_two_layers_where_they_are_built(tmp_path, client):
    """Half a pair looks like the map and is not it, so the lightbox gets both."""
    from PIL import Image
    _exempt(tmp_path, "1-005", kind="map")
    master = tmp_path / "edition" / "page-img" / "chukchi-1-005.png"
    layers = tmp_path / "mz" / "page-img"
    master.parent.mkdir(parents=True)
    layers.mkdir(parents=True)
    Image.new("RGB", (8, 8)).save(master)
    Image.new("RGB", (8, 8)).save(layers / "chukchi-1-005.colour.jpg")
    Image.new("L", (8, 8)).save(layers / "chukchi-1-005.lines.png")
    body = client().get("/edition/").text
    assert "data-lightbox='/edition/leaf/1-005/lines.png'" in body
    assert "data-lightbox-under='/edition/leaf/1-005/colour.jpg'" in body
    assert "data-full='/edition/leaf/1-005.png'" in body


def test_every_page_loads_the_one_script_and_no_other_of_the_readers(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-050", '<pb n="1"/><p>x</p>')
    c = client()
    for url in ("/edition/", "/edition/lexicon", "/edition/entities",
                "/edition/annotations", "/edition/page/1-050", "/edition/chapter/i/chapter-i"):
        body = c.get(url).text
        assert body.count("js/edition.js") == 1, url
        scripts = set(re.findall(r"js/(\w+)\.js", body))
        assert scripts <= {"edition", "ratify"}, (url, scripts)


def _alphabet_run(root: Path) -> None:
    (root / "edition").mkdir(parents=True, exist_ok=True)
    (root / "edition" / "alphabet.json").write_text(json.dumps({"sorts": []}), encoding="utf-8")
    (root / "edition" / "runs.json").write_text(json.dumps({"runs": [
        {"id": "alphabet", "kind": "alphabet", "title": "Alphabet", "refs": ["1-030"],
         "source": "edition/alphabet.json"}]}), encoding="utf-8")


def test_the_key_opens_over_the_page_except_on_its_own(tmp_path, client):
    _alphabet_run(tmp_path)
    page(tmp_path, "1-003", '<pb n="1"/><p>x</p>')
    c = client()
    assert "data-modal='/edition/partial/alphabet'" in c.get("/edition/").text
    own = c.get("/edition/run/alphabet")
    assert own.status_code == 200 and "data-modal" not in own.text
    bare = c.get("/edition/partial/alphabet")
    assert bare.status_code == 200 and "<html" not in bare.text
    assert "run-alphabet" in bare.text


def test_a_book_with_no_key_has_no_fragment_of_one(tmp_path, client):
    page(tmp_path, "1-003", '<pb n="1"/><p>x</p>')
    c = client()
    assert c.get("/edition/partial/alphabet").status_code == 404
    assert "data-modal" not in c.get("/edition/").text


def test_a_page_joins_the_division_before_it(tmp_path, client):
    """`1-022` under *Introductory*. The row says a count as a chapter's does, since
    `draft` is a word about one page."""
    _front(tmp_path, ("Intro", 1), ("Auth", 3))
    # Signed where a division opens: a draft's `<pb>` is no folio witness.
    page(tmp_path, "1-021", '<pb n="1"/><p>x</p>')
    draft(tmp_path, "1-022", '<pb n="2"/><p>x</p>')
    page(tmp_path, "1-023", '<pb n="3"/><p>x</p>')
    body = client(drafts=True).get("/edition/").text
    row = _li(body, "Intro<")
    assert "href='/edition/page/1-021'" in row and "href='/edition/page/1-022'" in row
    assert "1 of 2 collated" in row and "draft-tag'>uncollated" not in row
    assert body.count("<li class='ol-page'>") == 2


def test_a_joined_row_of_signed_pages_says_no_count(tmp_path, client):
    _front(tmp_path, ("Intro", 1), ("Auth", 3))
    for ref, n in (("1-021", 1), ("1-022", 2), ("1-023", 3)):
        page(tmp_path, ref, f'<pb n="{n}"/><p>x</p>')
    row = _li(client().get("/edition/").text, "Intro<")
    assert "href='/edition/page/1-022'" in row and "checked" not in row


@pytest.mark.parametrize("hole", ["gap", "leaf"])
def test_a_page_does_not_join_across_a_hole(tmp_path, client, hole):
    _front(tmp_path, ("Intro", 1), ("Auth", 3))
    page(tmp_path, "1-021", '<pb n="1"/><p>x</p>')
    if hole == "leaf":
        _exempt(tmp_path, "1-022")
    page(tmp_path, "1-023", '<pb n="2"/><p>x</p>')
    page(tmp_path, "1-024", '<pb n="3"/><p>x</p>')
    body = client().get("/edition/").text
    assert ">1-023<" not in _li(body, "Intro<")
    assert _li(body, ">1-023<").startswith("<li class='ol-page'>")


def test_a_page_does_not_join_when_the_next_entry_is_unplaced(tmp_path, client):
    """"Lost" might open on this very leaf, so the span has no known end."""
    _front(tmp_path, ("Intro", 1), ("Lost", 99))
    page(tmp_path, "1-021", '<pb n="1"/><p>x</p>')
    page(tmp_path, "1-022", '<pb n="2"/><p>x</p>')
    assert ">1-022<" not in _li(client().get("/edition/").text, "Intro<")


def test_a_rows_tags_come_before_its_number(tmp_path, client):
    _toc(tmp_path, "chI")
    draft(tmp_path, "1-001", '<pb n="1"/><p>x</p>')
    draft(tmp_path, "1-003", _opens("chI"))
    body = client(drafts=True).get("/edition/").text
    for row in (_li(body, ">1-001<"), _li(body, "Chapter I<")):
        assert row.index("draft-tag") < row.index("class='ol-at'")


def _jpeg(resp):
    from io import BytesIO

    from PIL import Image
    assert resp.status_code == 200 and resp.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(resp.content)) as im:
        return im.format, im.size


def test_a_thumbnail_is_a_jpeg_of_its_kinds_width(tmp_path, client):
    _exempt(tmp_path, "1-001", kind="cover")
    _exempt(tmp_path, "1-005", kind="map")
    _raster(tmp_path, "1-001")
    _raster(tmp_path, "1-005")
    c = client()
    assert _jpeg(c.get("/edition/thumb/1-001.jpg")) == ("JPEG", (100, 140))
    assert _jpeg(c.get("/edition/thumb/1-005.jpg")) == ("JPEG", (720, 1008))


def test_a_thumbnail_prefers_the_editors_leaf(tmp_path, client):
    from PIL import Image
    _exempt(tmp_path, "1-005", kind="map")
    _raster(tmp_path, "1-005")
    master = tmp_path / "edition" / "page-img" / "chukchi-1-005.png"
    master.parent.mkdir(parents=True)
    Image.new("RGB", (2000, 1000), "red").save(master)
    assert _jpeg(client().get("/edition/thumb/1-005.jpg"))[1] == (720, 360)


def test_only_the_kinds_the_index_shows_small_have_a_thumbnail(tmp_path, client):
    _exempt(tmp_path, "1-002", kind="blank")
    page(tmp_path, "1-003", '<pb n="1"/><p>x</p>')
    _exempt(tmp_path, "1-009", kind="cover")      # ruled, and no raster to shrink
    _raster(tmp_path, "1-002")
    _raster(tmp_path, "1-003")
    for ref in ("1-002", "1-003", "1-009"):
        assert client().get(f"/edition/thumb/{ref}.jpg").status_code == 404, ref
