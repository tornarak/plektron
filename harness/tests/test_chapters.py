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
    assert (out["url"], out["anchor"]) == ("/edition/run/chI", "chI")
    out = apparatus.locate(tmp_path, ref="1-004", index={})
    assert (out["url"], out["anchor"]) == ("/edition/run/chI", "leaf-1-004")


# --------------------------------------------------------------- the view


@pytest.fixture
def client(tmp_path):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app

    def make(drafts: bool = False):
        return TestClient(create_app(tmp_path, Sessions(root=tmp_path),
                                     editor="edition", drafts=drafts))
    return make


def test_a_leaf_redirects_into_its_chapter(tmp_path, client):
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>x</p>')
    r = client().get("/edition/page/1-004", follow_redirects=False)
    assert r.headers["location"] == "/edition/run/chI#leaf-1-004"


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
    body = client().get("/edition/run/chI").text
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
    body = client().get("/edition/run/chI").text
    assert body.count("id='ann-notice:warn'") == 1
    assert body.count("id='ann-supplement:more'") == 1
    assert body.index("ann-notice:warn") < _at(body, "leaf-1-003")
    assert body.index("ann-supplement:more") > body.index("Second leaf.")


def test_a_shared_leaf_greys_the_other_chapters_part_and_links_to_it(tmp_path, client):
    _toc(tmp_path, "chI", "chII")
    page(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", _opens("chII", before="<p>Tail of one.</p>"))
    c = client()
    one, two = c.get("/edition/run/chI").text, c.get("/edition/run/chII").text
    # In chapter I the leaf's own text is the tail; chapter II's opening is grey.
    assert "continues in II. Chapter II" in one
    assert "/edition/run/chII#chII" in one
    # In chapter II the tail is grey, and links back to the leaf in chapter I.
    assert "← from I. Chapter I" in two
    assert "/edition/run/chI#leaf-1-004" in two
    grey = two[two.index("<div class='other-text'>"):two.index('id="chII"')]
    assert "Tail of one." in grey
    # And the leaf opens chapter II, so *next* from chapter I goes there rather
    # than redirecting back into the chapter it left.
    r = c.get("/edition/page/1-004", follow_redirects=False)
    assert r.headers["location"] == "/edition/run/chII#leaf-1-004"


def _paras(body: str) -> list[str]:
    """The article's paragraphs, as text with tags stripped."""
    art = body[body.index("run-chapter"):body.index("</article>")]
    # The page mark is drawn in the margin, not read as part of the sentence.
    art = re.sub(r"""<a class=["']leaf-mark["'].*?</a>""", "", art, flags=re.S)
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
    body = client().get("/edition/run/chI").text
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
    paras = _paras(client().get("/edition/run/chI").text)
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
    body = client().get("/edition/run/chI").text
    assert any(p[:3] == ["Half", "of", "a"] and "sentence." in p for p in _paras(body))
    assert _at(body, "leaf-1-004") < body.index("Half of a")


def test_a_gap_is_never_joined_across(tmp_path, client):
    """Nothing says what an unread leaf's text did, so the paragraph before it
    stays closed."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI") + "<p>Half of a</p>")
    draft(tmp_path, "1-004", '<pb n="2"/><p>hidden</p>')
    page(tmp_path, "1-005", '<pb n="3"/><!-- zone-opens: continued (z) -->'
                            "<p>sentence.</p>")
    paras = _paras(client().get("/edition/run/chI").text)
    assert not any("Half" in p and "sentence." in p for p in paras)


def test_an_unreadable_leaf_is_a_gap_said_in_place(tmp_path, client):
    """A draft leaf with drafts hidden. The chapter still renders; the leaf says
    what it is and where the scan is, rather than the text closing over it."""
    _toc(tmp_path, "chI")
    page(tmp_path, "1-003", _opens("chI"))
    draft(tmp_path, "1-004", '<pb n="2"/><p>Unread.</p>')
    page(tmp_path, "1-005", '<pb n="3"/><p>Read.</p>')
    body = client().get("/edition/run/chI").text
    assert "Unread." not in body and "Read." in body
    assert "leaf-tag'>gap" in body and "/edition/page/1-004.png" in body
    assert "Unread." in client(drafts=True).get("/edition/run/chI").text


def test_the_listing_keeps_a_chapter_whose_opener_is_unread(tmp_path, client):
    """The head stands for the run whenever any leaf of it can be shown, or the
    whole chapter would drop out of the listing for want of its first leaf."""
    _toc(tmp_path, "chI")
    draft(tmp_path, "1-003", _opens("chI"))
    page(tmp_path, "1-004", '<pb n="2"/><p>x</p>')
    body = client().get("/edition/").text
    assert "1-003" in body
    assert "/edition/page/1-004" not in body
