"""The reading view: the renderer, and the server that writes the store.

Two things worth pinning. The renderer must show what the file says is unfinished
— an edition that tidies away an open question presents a draft as finished, and
that is the failure this whole project is arranged against. And the server writes
`entities/` without `--commit`, on the `zones edit` precedent, so what has to be
true is that it cannot leave the store in a state `entity check` rejects.
"""
from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import pytest
from test_entities import entry

from harness import edition_ui, tei_html

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
    assert 'href="/entity/place:markova"' in got["html"]
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


# ------------------------------------------------------------- the server

@pytest.fixture
def server(tmp_path):
    """A real server on a real port, as the other editor suites do it."""
    entry(tmp_path, "place:markova", status="proposed",
          triggers=[("Markova", True)])
    page(tmp_path, "1-021", '<pb n="1"/><p>At '
         '<rs ref="place:markova" resp="#mz">Markova</rs>.</p>')
    port = 8799
    t = threading.Thread(
        target=edition_ui.serve,
        kwargs={"root": tmp_path, "port": port, "open_browser": False},
        daemon=True)
    t.start()
    for _ in range(200):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1).read()
            break
        except Exception:
            pass
    yield f"http://127.0.0.1:{port}", tmp_path
    urllib.request.urlopen(urllib.request.Request(
        f"http://127.0.0.1:{port}/stop", method="POST", data=b"{}"), timeout=2)
    t.join(timeout=5)


def get(url: str) -> str:
    return urllib.request.urlopen(url, timeout=5).read().decode()


def post(url: str, obj) -> dict:
    req = urllib.request.Request(
        url, method="POST", data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


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
