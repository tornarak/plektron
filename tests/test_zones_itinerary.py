"""`--itinerary`: walking a chosen work-list instead of scan order.

The editor's arrow keys walk `all_scans` by default, which is right for keying a
part straight through and wrong for building a training set. `gt/seg/`'s 122 pages
were selected for heterogeneity; reaching them through 700 scans nobody means to key
is not navigation. So a list file — or a directory, since "everything in `gt/seg/`"
is the obvious itinerary and spans two list files.

Two properties matter beyond the plumbing. **An unparseable line is an error, never
a skip** — `lines.parse_selection` takes the same position, because a silently
dropped entry means a page reported as covered was never visited and the report
cannot tell you so. And **a scoped sweep reports pages still to do as rows**, rather
than listing only the finished ones: "how much is left" is the question an itinerary
is being asked, and a sweep that omitted them would call a half-done selection
complete.
"""
from __future__ import annotations
from pathlib import Path

import pytest
from PIL import Image

from harness import zones as zn
from harness import zones_config as zc
from harness import zones_ui as ui

REPO = Path(__file__).resolve().parent.parent


def cfg():
    return zc.load_config(REPO)


def make_scan(tmp_path: Path, ref: str, size=(2824, 3897)):
    d = tmp_path / "scans"
    d.mkdir(parents=True, exist_ok=True)
    Image.new("L", size, 255).save(d / f"chukchi-{ref}.png")


def lst(tmp_path: Path, name: str, refs) -> Path:
    p = tmp_path / name
    p.write_text("".join(f"chukchi-{r}.xml\n" for r in refs), encoding="utf-8")
    return p


def test_a_list_file_is_read_in_page_order(tmp_path):
    for r in ("1-019", "1-005", "2-100"):
        make_scan(tmp_path, r)
    p = lst(tmp_path, "work.lst", ["2-100", "1-019", "1-005"])
    assert zn.load_itinerary(p, tmp_path) == ["1-005", "1-019", "2-100"]


def test_a_directory_means_every_page_file_in_it(tmp_path):
    """'Everything in gt/seg' is the obvious itinerary and spans two list files."""
    d = tmp_path / "seg"
    d.mkdir()
    for r in ("1-019", "1-005"):
        make_scan(tmp_path, r)
        (d / f"chukchi-{r}.xml").write_text("<alto/>", encoding="utf-8")
    assert zn.load_itinerary(d, tmp_path) == ["1-005", "1-019"]


def test_bare_refs_and_paths_are_read_too(tmp_path):
    for r in ("1-019", "1-005"):
        make_scan(tmp_path, r)
    p = tmp_path / "work.lst"
    p.write_text("1-019\ngt/seg/chukchi-1-005.xml\n", encoding="utf-8")
    assert zn.load_itinerary(p, tmp_path) == ["1-005", "1-019"]


def test_blank_lines_and_comments_are_ignored(tmp_path):
    make_scan(tmp_path, "1-019")
    p = tmp_path / "work.lst"
    p.write_text("# the heterogeneous selection\n\nchukchi-1-019.xml\n\n",
                 encoding="utf-8")
    assert zn.load_itinerary(p, tmp_path) == ["1-019"]


def test_duplicates_collapse(tmp_path):
    make_scan(tmp_path, "1-019")
    p = lst(tmp_path, "work.lst", ["1-019", "1-019"])
    assert zn.load_itinerary(p, tmp_path) == ["1-019"]


def test_an_unparseable_line_is_refused_not_skipped(tmp_path):
    """A silently dropped entry means a page reported as covered was never
    visited, and nothing downstream can tell you so."""
    make_scan(tmp_path, "1-019")
    p = tmp_path / "work.lst"
    p.write_text("chukchi-1-019.xml\nnot-a-ref\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a page ref"):
        zn.load_itinerary(p, tmp_path)


def test_a_ref_with_no_raster_is_refused_up_front(tmp_path):
    """Rather than halfway through a keying session, on the page itself."""
    make_scan(tmp_path, "1-019")
    p = lst(tmp_path, "work.lst", ["1-019", "9-999"])
    with pytest.raises(ValueError, match="no raster for 9-999"):
        zn.load_itinerary(p, tmp_path)


def test_a_missing_itinerary_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no itinerary"):
        zn.load_itinerary("nope.lst", tmp_path)


# ------------------------------------------------------------- navigation

def test_the_arrow_keys_follow_the_list_not_scan_order(tmp_path):
    for r in ("1-005", "1-006", "1-007", "1-019"):
        make_scan(tmp_path, r)
    itin = ["1-005", "1-019"]
    st = ui.page_state("1-005", tmp_path, cfg(), itinerary=itin)
    assert st["next"] == "1-019"          # not 1-006
    assert (st["index"], st["total"]) == (1, 2)
    assert st["on_list"] is True


def test_a_page_off_the_list_still_opens_but_has_no_neighbours(tmp_path):
    """The honest answer, rather than silently splicing it into a work-list
    nobody put it on."""
    for r in ("1-005", "1-006", "1-019"):
        make_scan(tmp_path, r)
    st = ui.page_state("1-006", tmp_path, cfg(), itinerary=["1-005", "1-019"])
    assert st["on_list"] is False
    assert st["prev"] is None and st["next"] is None


def test_progress_counts_the_keyed_pages_on_the_list(tmp_path):
    for r in ("1-005", "1-019", "1-020"):
        make_scan(tmp_path, r)
    zn.save_zones("1-019", [], tmp_path)
    st = ui.page_state("1-005", tmp_path, cfg(),
                       itinerary=["1-005", "1-019", "1-020"])
    assert st["done"] == 1 and st["total"] == 3


def test_without_an_itinerary_navigation_is_scan_order(tmp_path):
    for r in ("1-005", "1-006"):
        make_scan(tmp_path, r)
    assert ui.page_state("1-005", tmp_path, cfg())["next"] == "1-006"


# ------------------------------------------------------------- scoped sweep

def test_a_scoped_sweep_reports_unkeyed_pages_as_rows(tmp_path):
    """'How much is left' is what an itinerary is asked. A sweep listing only
    finished pages would call a half-done selection complete."""
    for r in ("1-005", "1-019", "1-020"):
        make_scan(tmp_path, r)
    zn.save_zones("1-019", [], tmp_path)
    summary, rows = zn.validate_corpus(tmp_path, cfg(),
                                       refs=["1-005", "1-019", "1-020"])
    assert summary["pages"] == 3
    assert summary["keyed"] == 1 and summary["todo"] == 2
    assert [r["ref"] for r in rows] == ["1-005", "1-019", "1-020"]
    # Still one fixed key set — the TOON constraint holds over mixed rows.
    assert len({frozenset(r) for r in rows}) == 1


def test_an_unscoped_sweep_still_reports_only_keyed_pages(tmp_path):
    for r in ("1-005", "1-019"):
        make_scan(tmp_path, r)
    zn.save_zones("1-019", [], tmp_path)
    summary, rows = zn.validate_corpus(tmp_path, cfg())
    assert [r["ref"] for r in rows] == ["1-019"]
    assert summary["todo"] == 0
