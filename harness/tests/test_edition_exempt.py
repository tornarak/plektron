"""Pages a human ruled not a text page, in the reading view.

`dispatch.py` refuses an exempt page for both the ground-truth and the collation
tracks, so no amount of transcription will ever produce a `tei/` page for one.
Left out of the edition they would take every plate, foldout and piece of front
matter with them, silently — 115 pages of this book.

**The kind is read, never inferred** — `zones.LEAF_KINDS`, written by a human in
`zones edit` at the raster. The rule used to be thin because nothing witnessed
anything finer: figures if the figure store had boxes here, the whole scan if it
had none. That is a fact about a *different store*, and under it a blank verso
and the volume's folding map were the same page — which is what the change fixed
and what several tests here now assert the other way round.

What has not changed is the boundary. Nothing derives a kind from figure boxes,
from a neighbouring leaf, or from what the page looks like; a leaf in no kind
list is not a leaf at all and renders as it always did.
"""
from __future__ import annotations

from pathlib import Path

from conftest import write_captions

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _exempt_lst(root: Path, *refs: str, kind: str = "plate") -> None:
    """Rule these leaves, all as one kind. `plate` by default: it is the kind that
    shows its figure crops, which is what most of these fixtures are about."""
    p = root / "gt" / "zones" / f"_{kind}.lst"
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
    write_captions(root, blocks)


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


def test_a_leaf_with_no_figures_shows_the_whole_leaf(tmp_path):
    """A plate whose boxes nobody has drawn yet, a cover, the map. The kind
    chooses the framing; `gt/fig/` still decides whether there are crops, so a
    kind is never allowed to manufacture content the stores do not hold."""
    _exempt_lst(tmp_path, "1-050", kind="cover")
    _readings(tmp_path, {})
    _raster(tmp_path, "1-050")

    r = _app(tmp_path).get("/edition/page/1-050")
    assert r.status_code == 200
    assert "whole-scan" in r.text
    assert "/edition/page/1-050.png" in r.text


def test_a_blank_is_still_served_but_not_at_plate_size(tmp_path):
    """**The ruling is a claim, so the paper stays reachable.** A page that showed
    nothing would be asking the reader to take "blank" on trust, and this store's
    whole discipline is that a claim keeps its evidence beside it — the leaf is
    served, through the same lightbox as any other image.

    What it does not get is the full measure. This is the case the old design
    could not express at all: with the shape decided by whether `gt/fig/` had
    boxes, a blank verso and the volume's folding map were one branch, and the
    blank took plate width in the middle of a run of pictures somebody was paging
    through."""
    _exempt_lst(tmp_path, "1-050", kind="blank")
    _readings(tmp_path, {})
    _raster(tmp_path, "1-050")

    text = _app(tmp_path).get("/edition/page/1-050").text
    assert "whole-scan blank-leaf" in text
    assert "/edition/page/1-050.png" in text, "the paper is still reachable"
    assert "/edition/fig/" not in text


def test_the_page_says_the_kind_the_store_holds_and_no_other(tmp_path):
    """The mark is on the page, not only in the listing — a URL typed straight in
    skips the listing. What it says is exactly what the store says.

    This used to assert the opposite: that the page named *no* kind, because none
    was witnessed anywhere. The words are licensed now, and the property that
    replaces it is that they are licensed **one at a time** — a leaf ruled `cover`
    must not also be described as a plate or a map, which is what a template
    branching on the wrong variable would produce.
    """
    _exempt_lst(tmp_path, "1-001", kind="cover")
    _readings(tmp_path, {})
    _raster(tmp_path, "1-001")

    import re
    text = _app(tmp_path).get("/edition/page/1-001").text
    # The prose only. Scoped rather than searched whole, because `target='_blank'`
    # on the link to the scan is markup and matched the naive version of this.
    # **Script bodies are cut first**, for the same reason one step further in:
    # what is between `<script>` and `</script>` sits between two tags and is not
    # prose either. The head's anti-flash block is a dozen lines of commented
    # JavaScript, and a comment there naming `map.js` is not this page calling a
    # cover leaf a map.
    text = re.sub(r"(?s)<script\b.*?</script>", "", text)
    prose = " ".join(re.findall(r">([^<>]+)<", text)).lower()
    assert "cover" in prose and "title or wrapper leaf" in prose
    for other in ("plate", "blank", "foldout", "map"):
        assert other not in prose, f"the store does not witness {other!r} here"


def test_a_leaf_the_store_says_nothing_about_falls_back(tmp_path):
    """A page in no kind list is not a leaf at all, and must render as it always
    did rather than as an empty branch. This is the state a page is in between
    being marked in the editor and the kind being saved, and on any corpus whose
    vocabulary predates this one."""
    _readings(tmp_path, {})
    _raster(tmp_path, "1-001")
    # No `_exempt_lst` call: the page is in no list, so `page()` never reaches
    # `_exempt_page` at all and the ordinary not-collated path answers.
    assert _app(tmp_path).get("/edition/page/1-001").status_code == 404


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
    assert "not been collated" in r.text


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
