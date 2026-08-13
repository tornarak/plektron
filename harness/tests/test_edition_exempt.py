"""Pages a human ruled not a text page, in the reading view.

`dispatch.py` refuses an exempt page for both the ground-truth and the collation
tracks, so no amount of transcription will ever produce a `tei/` page for one.
Left out of the edition they would take every plate, foldout and piece of front
matter with them, silently — 115 pages of this book.

The rule for showing one is deliberately thin: **figures if the figure store has
boxes here, the whole scan if it has none.** Sorting these into plates, maps,
half-titles and blanks would mean deciding what a page *is* from evidence no
store carries, and getting that wrong on the next book is the failure this
pipeline is supposed to be past.
"""
from __future__ import annotations

from pathlib import Path

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _exempt_lst(root: Path, *refs: str) -> None:
    p = root / "gt" / "zones" / "_exempt.lst"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(f"chukchi-{r}.xml\n" for r in refs), encoding="utf-8")


def _fig_alto(root: Path, ref: str, blocks) -> None:
    p = root / "gt" / "fig" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<TextBlock ID="{i}" TAGREFS="{"BT77" if lab.endswith("FigDesc") else "BT78"}"'
        f' HPOS="{x}.0" VPOS="{y}.0" WIDTH="{w}.0" HEIGHT="{h}.0"/>'
        for i, lab, x, y, w, h in blocks)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
        f"<PrintSpace>{body}</PrintSpace></Page></Layout><Tags>"
        '<OtherTag ID="BT77" TYPE="type" LABEL="GraphicZone-FigDesc"/>'
        '<OtherTag ID="BT78" TYPE="type" LABEL="GraphicZone"/>'
        "</Tags></alto>", encoding="utf-8")


def _readings(root: Path, blocks: dict[str, str]) -> None:
    root.joinpath("data").mkdir(parents=True, exist_ok=True)
    root.joinpath("data", "readings.md").write_text(
        "".join(f"## {k}\n{v}\n\n" for k, v in blocks.items()), encoding="utf-8")


def _tei(root: Path, ref: str, body: str) -> None:
    p = root / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>t</title>'
        "</titleStmt><publicationStmt><p>p</p></publicationStmt>"
        "<sourceDesc><p>s</p></sourceDesc></fileDesc></teiHeader>"
        f"<text><body>{body}</body></text></TEI>", encoding="utf-8")


def _raster(root: Path, ref: str) -> None:
    from PIL import Image
    p = root / "scans" / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (2824, 3897), 255).save(p)


def _app(root, drafts: bool = False):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app
    return TestClient(create_app(root, Sessions(root=root), editor="edition",
                                 drafts=drafts))


# -- the two shapes -----------------------------------------------------------

def test_an_exempt_page_with_figures_shows_them(tmp_path):
    # A plate's caption is set rotated *beside* its picture and, per
    # `figures._gap`, after it across the page — so the caption's x is greater
    # than the picture's. Placed to the left it pairs with nothing, which is
    # what this fixture did first.
    _exempt_lst(tmp_path, "1-049")
    _fig_alto(tmp_path, "1-049", [
        ("fig_1-049_001", "GraphicZone", 400, 2400, 1800, 900),
        ("fig_1-049_002", "GraphicZone-FigDesc", 2250, 2400, 90, 460),
        ("fig_1-049_003", "GraphicZone", 400, 600, 1800, 900),
        ("fig_1-049_004", "GraphicZone-FigDesc", 2250, 600, 90, 460)])
    _readings(tmp_path, {"1-049|002": "Fig. 2. Village Nuˊnligren.",
                         "1-049|004": "Fig. 1. Village Uñiˊsak."})
    _raster(tmp_path, "1-049")

    r = _app(tmp_path).get("/edition/page/1-049")
    assert r.status_code == 200
    assert "/edition/fig/1-049/001.png" in r.text
    assert "/edition/fig/1-049/003.png" in r.text
    # NFD both sides. `figures.readings` normalizes on read, corpus-wide, so the
    # served caption carries n + U+0303 where this file's literal is precomposed
    # — a needle written the natural way simply misses.
    import unicodedata
    assert unicodedata.normalize("NFD", "Village Uñiˊsak") in \
        unicodedata.normalize("NFD", r.text), "the caption comes with the picture"
    assert "whole-scan" not in r.text


def test_an_exempt_page_without_figures_shows_the_whole_leaf(tmp_path):
    """Including a blank one. The reader sees the leaf and can see it is blank;
    a page that *said* "blank" would assert what no store witnesses — 113 of the
    115 exempt pages hold zero zones, and a map nobody boxed looks identical."""
    _exempt_lst(tmp_path, "1-050")
    _readings(tmp_path, {})
    _raster(tmp_path, "1-050")

    r = _app(tmp_path).get("/edition/page/1-050")
    assert r.status_code == 200
    assert "whole-scan" in r.text
    assert "/edition/page/1-050.png" in r.text
    assert "/edition/fig/" not in r.text


def test_it_says_the_page_was_ruled_out_and_claims_nothing_more(tmp_path):
    """The mark is on the page, not only in the listing — a URL typed straight in
    skips the listing. What it says is what the store says: not a text page. Not
    plate, not map, not blank."""
    _exempt_lst(tmp_path, "1-001")
    _readings(tmp_path, {})
    _raster(tmp_path, "1-001")

    import re
    text = _app(tmp_path).get("/edition/page/1-001").text
    assert "not a text page" in text
    # The prose only. Scoped rather than searched whole, because `target='_blank'`
    # on the link to the scan is markup and matched the naive version of this.
    prose = " ".join(re.findall(r">([^<>]+)<", text)).lower()
    for claim in ("plate", "blank", "half-title", "foldout", "map"):
        assert claim not in prose, f"the store does not witness {claim!r}"


# -- the reading order --------------------------------------------------------

def test_prev_next_crosses_an_exempt_page(tmp_path):
    """Or a reader walking the book falls off it at every illustration."""
    _exempt_lst(tmp_path, "1-050")
    _readings(tmp_path, {})
    _raster(tmp_path, "1-050")
    _tei(tmp_path, "1-049", "<p>before</p>")
    _tei(tmp_path, "1-051", "<p>after</p>")

    c = _app(tmp_path)
    assert "/edition/page/1-050" in c.get("/edition/page/1-049").text
    on_plate = c.get("/edition/page/1-050").text
    assert "/edition/page/1-049" in on_plate
    assert "/edition/page/1-051" in on_plate


def test_a_page_nobody_ruled_on_still_says_it_is_not_collated(tmp_path):
    """Exemption is a judgement; not-yet-transcribed is an absence. A page that
    is merely untranscribed must not be dressed up as a decision."""
    _exempt_lst(tmp_path)
    _readings(tmp_path, {})
    _raster(tmp_path, "2-100")

    r = _app(tmp_path).get("/edition/page/2-100")
    assert r.status_code == 404
    assert "not collated" in r.text


# -- succession ---------------------------------------------------------------

def _f(n, key):
    return {"key": key, "n": n, "zone_ids": [key], "caption_zone": "",
            "caption": "", "box": (0, 0, 10, 10), "y": 0}


def test_figures_run_in_the_order_the_book_numbers_them(tmp_path):
    """A rotated plate numbers as the turned page reads: `1-049` runs 3, 1, 2
    down the sheet and `1-227` runs 2, 4, 1, 3. Position would show a reader
    Fig. 3 first on a page whose own caption says Fig. 1."""
    from harness.figures import in_printed_order
    got = in_printed_order([_f("3", "a"), _f("1", "b"), _f("2", "c")])
    assert [f["n"] for f in got] == ["1", "2", "3"]


def test_a_page_with_an_unnumbered_figure_keeps_its_geometric_order(tmp_path):
    """`1-215`. A partial ordering would have to place the unnumbered one, and
    there is nothing to place it with."""
    from harness.figures import in_printed_order
    figs = [_f("2", "a"), _f(None, "b"), _f("1", "c")]
    assert [f["key"] for f in in_printed_order(figs)] == ["a", "b", "c"]


def test_non_integer_figure_numbers_fall_back_to_position(tmp_path):
    """Another book may number IV or 12a. Position is honest; inventing a
    collation order for arbitrary strings is a rule about one book pretending to
    be general."""
    from harness.figures import in_printed_order
    figs = [_f("IV", "a"), _f("II", "b")]
    assert [f["key"] for f in in_printed_order(figs)] == ["a", "b"]
