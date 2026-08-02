"""`ocr/` as a view over two stores, and the skip rule that feeds it.

The `zones/` layout arrived with `zones link` and a store rule; `ocr/` acquired
the same shape only when `ocr predict` gave it a second store to resolve into.
What is tested here is the part that has no other witness: **which store a name
resolves to**, and **when a page is left alone**.

Nothing here loads a model. Recognition needs a GPU, two checkpoints and ~20 s a
page, and none of that is what goes wrong — what goes wrong is a link pointing at
the machine file when a human file exists, or a sweep quietly replacing the
provenance in a store it was only meant to fill gaps in. Both are pure path logic
and both are silent in every report that would otherwise look complete.

Fixtures live in `tmp_path`, per the suite's rule.
"""
from __future__ import annotations
from pathlib import Path

import pytest

from harness import recognize as R

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _alto(p: Path, text: str = "x") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
        f'<TextBlock ID="b1"><TextLine ID="l1">'
        f'<String CONTENT="{text}"/></TextLine></TextBlock>'
        "</PrintSpace></Page></Layout></alto>", encoding="utf-8")
    return p


@pytest.fixture
def store(tmp_path):
    """One page in gt only, one in mz only, one in both."""
    _alto(tmp_path / R.GTDIR / "chukchi-1-048.xml", "human")
    _alto(tmp_path / R.MZDIR / "chukchi-1-060.xml", "machine")
    _alto(tmp_path / R.GTDIR / "chukchi-1-100.xml", "human")
    _alto(tmp_path / R.MZDIR / "chukchi-1-100.xml", "machine")
    return tmp_path


def test_the_view_names_every_page_once(store):
    rep = R.link_view(store)
    names = sorted(p.name for p in (store / R.VIEWDIR).glob("*.xml"))
    assert names == ["chukchi-1-048.xml", "chukchi-1-060.xml",
                     "chukchi-1-100.xml"]
    assert rep["from_gt"] == 2 and rep["from_mz"] == 1


def test_the_human_file_always_wins(store):
    """The whole rule of the layout. A page in both stores resolves to `gt/`, and
    the machine file stays where it is rather than being moved or removed —
    promotion is `restore` writing gt and the view relinking, never a copy."""
    R.link_view(store)
    link = store / R.VIEWDIR / "chukchi-1-100.xml"
    assert link.resolve() == (store / R.GTDIR / "chukchi-1-100.xml").resolve()
    assert (store / R.MZDIR / "chukchi-1-100.xml").exists()


def test_links_are_relative(store):
    """So the farm survives a clone or a move. An absolute link would work on
    this machine and nowhere else, which is the kind of break that shows up as a
    missing page rather than as a bad link."""
    R.link_view(store)
    import os
    for p in (store / R.VIEWDIR).glob("*.xml"):
        assert not os.path.isabs(os.readlink(p))


def test_a_stale_link_is_removed_not_left_dangling(store):
    R.link_view(store)
    (store / R.MZDIR / "chukchi-1-060.xml").unlink()
    rep = R.link_view(store)
    assert rep["removed"] == 1
    assert not (store / R.VIEWDIR / "chukchi-1-060.xml").exists()
    assert not list((store / R.VIEWDIR).glob("chukchi-1-060.xml"))


def test_link_one_reports_the_store_it_named(store):
    assert R.link_one("1-100", store) == R.GTDIR
    assert R.link_one("1-060", store) == R.MZDIR


def test_ocr_refs_dedupes_by_real_path(store):
    """The view is reachable through the `store` parameter, and a walk that
    counted one inode under two names would undercount in a report that looks
    complete."""
    R.link_view(store)
    assert R.ocr_refs(store, R.VIEWDIR) == ["1-048", "1-060", "1-100"]
    assert R.ocr_refs(store, R.GTDIR) == ["1-048", "1-100"]


def test_an_existing_page_is_kept_unless_forced(store, monkeypatch):
    """The mz file records both models' sha256 — the store's only witness to what
    produced it. A sweep that re-ran unasked would replace that record page by
    page and leave nothing able to say the store had held more than one pass."""
    monkeypatch.setattr(R.Z, "load_splits", lambda root: {})
    assert R.predict_skip("1-060", store) == "already recognized"
    # `--force` gets past that one and lands on the next real precondition.
    assert R.predict_skip("1-060", store, force=True) != "already recognized"


def test_an_exempt_page_is_refused_but_a_named_ref_is_not(store, monkeypatch):
    """`exempt` means a human ruled it not a text page. `single` — naming the ref
    on the command line — is the override, and it is a separate flag from `force`
    because the two excuse different things."""
    monkeypatch.setattr(R.Z, "load_splits", lambda root: {"1-060": "exempt"})
    assert R.predict_skip("1-060", store) == "ruled not a text page"
    assert R.predict_skip("1-060", store, single=True) != "ruled not a text page"


def test_a_page_with_no_zones_is_refused(store, monkeypatch):
    """The structure is what the pass applies. Recognizing flat would put a page
    in the store with nothing in it saying the zones were missing."""
    monkeypatch.setattr(R.Z, "load_splits", lambda root: {})
    monkeypatch.setattr(R.Z, "read_zones",
                        lambda ref, root, **kw: [] if ref == "1-061" else [{"x0": 0}])
    (store / "scans").mkdir(exist_ok=True)
    (store / "scans" / "chukchi-1-061.png").write_bytes(b"")
    assert "no zones" in R.predict_skip("1-061", store)


def test_nothing_here_can_name_the_ground_truth_store():
    """`predict` writes `mz/ocr/` and there is no parameter in which a caller
    could name somewhere else — the property `save_zones` has, for the reason
    this project lost 18 pages of transcription."""
    import inspect
    params = inspect.signature(R.predict).parameters
    assert "store" not in params and "out" not in params and "alto_dir" not in params
