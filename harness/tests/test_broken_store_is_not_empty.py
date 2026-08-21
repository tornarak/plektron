"""A store that will not parse must not read as a store with nothing in it.

Two `except Exception` sites turned a broken file into a plausible ordinary
answer, which is the failure this project names in its first paragraph. Both are
places where the empty answer is also the *common* answer, so nothing downstream
could ever have noticed.

`zones._figure_rects` returned `[]`, which its three callers read as "no
illustrations on this page" — true of 580 of 832 pages. The docstring three
lines above the guard says that when figure rects are not subtracted a surviving
plate edge "reads as a 400 px indent. That is where the 523 false positives came
from." The guard reinstated exactly that, silently.

`detectors._restored_refs` dropped an unparseable `gt/ocr/` page out of the keyed
list, leaving it indistinguishable from an empty export shell — in the one
function whose stated job is telling those two apart.

Both now let the fault out. Neither had to grow a new absence case: absence was
already handled correctly, above the guard, which is what made the guards pure
loss.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_scan

from harness import detectors, zones


def _fig_alto(root: Path, ref: str, body: str) -> Path:
    p = root / "gt" / "fig" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


class TestFigureRects:

    def test_a_page_with_no_figure_file_is_still_empty(self, tmp_path):
        """The ordinary case, and the one the guard was mistaken for handling.

        `figures.read_blocks` returns `[]` for a missing file on its own, above
        where the guard sat — so removing it costs this nothing.
        """
        assert zones._figure_rects("1-021", tmp_path) == []

    def test_an_unparseable_figure_file_is_not_an_empty_page(self, tmp_path):
        """Named exactly rather than `pytest.raises(Exception)`: a bare catch
        here would pass on a `TypeError` from some later refactor, and report
        that as the guard working.

        This one surfaces as lxml's own error, which `cli.main` does **not**
        net — `XMLSyntaxError` subclasses `SyntaxError`. That is a wider issue
        than this fix (every unguarded `etree.parse` in the package shares it)
        and is left for the report rather than widened into here; what matters
        for this site is that the fault leaves the function at all.
        """
        from lxml import etree

        _fig_alto(tmp_path, "1-021", "<alto><TextBlock")
        with pytest.raises(etree.XMLSyntaxError):
            zones._figure_rects("1-021", tmp_path)

    def test_a_well_formed_file_still_yields_its_rects(self, tmp_path):
        _fig_alto(tmp_path, "1-021",
                  '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">'
                  '<Layout><Page><PrintSpace>'
                  '<TextBlock ID="b1" HPOS="10" VPOS="20" WIDTH="30" HEIGHT="40"/>'
                  '</PrintSpace></Page></Layout></alto>')
        assert zones._figure_rects("1-021", tmp_path) == [(10, 40, 20, 60)]


class TestRestoredRefs:

    def test_an_empty_shell_is_excluded_quietly(self, tmp_path):
        """Still the ordinary exclusion: a page with no `CONTENT` is not keyed,
        and that is a fact about the page rather than a fault."""
        write_scan(tmp_path, "1-021")
        p = tmp_path / "gt" / "ocr" / "chukchi-1-021.xml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">'
                     '<String CONTENT=""/></alto>', encoding="utf-8")
        assert detectors._restored_refs(tmp_path) == []

    def test_an_unparseable_page_is_not_an_unkeyed_page(self, tmp_path):
        write_scan(tmp_path, "1-021")
        p = tmp_path / "gt" / "ocr" / "chukchi-1-021.xml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<alto><String", encoding="utf-8")

        with pytest.raises(ValueError, match="1-021"):
            detectors._restored_refs(tmp_path)

    def test_the_refusal_is_one_cli_main_can_print(self, tmp_path):
        """`ValueError`, not lxml's `XMLSyntaxError` — that subclasses
        `SyntaxError`, which `cli.main` does not net, so it would reach a user
        as a traceback naming lxml rather than the page."""
        write_scan(tmp_path, "1-021")
        p = tmp_path / "gt" / "ocr" / "chukchi-1-021.xml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<alto><String", encoding="utf-8")

        with pytest.raises(ValueError) as e:
            detectors._restored_refs(tmp_path)
        assert not isinstance(e.value, SyntaxError)

    def test_a_keyed_page_still_comes_back(self, tmp_path):
        write_scan(tmp_path, "1-021")
        p = tmp_path / "gt" / "ocr" / "chukchi-1-021.xml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">'
                     '<String CONTENT="word"/></alto>', encoding="utf-8")
        assert detectors._restored_refs(tmp_path) == ["1-021"]
