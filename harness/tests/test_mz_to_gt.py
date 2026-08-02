"""The correction flow, sourced from `mz/ocr/` instead of an eScriptorium lump.

`restore` was built for a one-off: `gt/ocr/` held export shells with no
`TextLine` at all, and the pass filled them in page by page. That source is gone
— eScriptorium holds nothing and the repo is the system of record — and the
standing source for an un-keyed page is now `mz/ocr/`, written by `ocr predict`.

**Nothing in `restore` had to change for that**, which is the thing worth pinning.
Its `restoration` mode is defined by the geometry source and the write target
being different files, not by which store the source is, so naming `--store mz`
is the flow. What these tests hold is that it stays true: that a page with no
ground truth at all can be built from a prediction plus an adjudication, that the
machine's *geometry* survives while the machine's *text* does not reach `gt/`
except through a decision, and that the span diff's second-witness refusal is
satisfied by `mz/ocr/` where it is not by the view.

That last one closes a gap CLAUDE.md records as open: "`harness ocr review`'s bare
span diff has no second witness left ... If a second witness is ever wanted again,
it links into `ocr/` from its own store." That is exactly what `mz/ocr/` is.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.review import restore, save_decisions

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _mz_page(root: Path, ref: str = "1-060", texts=("machine one", "machine two")):
    """An `ocr predict`-shaped page: geometry, labels, one String per line."""
    p = root / "mz" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(
        f'<TextLine ID="mz_{ref}_l{i}" HPOS="100" VPOS="{200 + i * 60}" '
        f'WIDTH="1700" HEIGHT="50" BASELINE="100 {245 + i * 60} 1800 {245 + i * 60}">'
        f'<Shape><Polygon POINTS="100 {200 + i * 60} 1800 {250 + i * 60}"/></Shape>'
        f'<String CONTENT="{t}" HPOS="100" VPOS="{200 + i * 60}" '
        f'WIDTH="1700" HEIGHT="50"/></TextLine>'
        for i, t in enumerate(texts, 1))
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
        f'<TextBlock ID="mz_{ref}_r1" TAGREFS="T1">{lines}</TextBlock>'
        "</PrintSpace></Page></Layout>"
        '<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags></alto>',
        encoding="utf-8")
    return p


def _proposal(root: Path, texts, ref: str = "1-060"):
    """A reading of the raster, authored by the pass — never the machine's text.

    Required before decisions can be saved, since `save_decisions` records per
    line whether the human changed the proposal. That the proposal is a *separate*
    reading is the point: seeding it from `mz/ocr/` would collapse the two
    witnesses the span diff compares, and CATMuS reads 0% of the inventory, so on
    Tier-1 forms it would be seeding from a known-blind source.
    """
    import json
    p = root / "review" / ref / "proposal.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "ref": ref,
        "status": "PROPOSAL — not ground truth.",
        "lines": {str(i): {"text": t} for i, t in enumerate(texts)},
    }), encoding="utf-8")
    return p


@pytest.fixture
def page(tmp_path):
    _mz_page(tmp_path)
    _proposal(tmp_path, ["human one", "human two"])
    # What a human adjudicated, deliberately *not* what the machine read.
    save_decisions("1-060", {0: {"text": "human one"}, 1: {"text": "human two"}},
                   tmp_path)
    return tmp_path


def test_a_page_with_no_ground_truth_can_be_built_from_a_prediction(page):
    """The whole point. `gt/ocr/chukchi-1-060.xml` does not exist beforehand; the
    geometry comes from the prediction and the text from the adjudication."""
    rep = restore("1-060", "mz/ocr", page, commit=True)
    assert rep["mode"] == "restoration"
    target = page / "gt" / "ocr" / "chukchi-1-060.xml"
    assert target.exists(), "restore must create the ground-truth file"
    assert rep["lines"] == 2 and not rep["geometry_drift"] and not rep["text_mismatch"]


def test_the_machine_text_does_not_reach_the_ground_truth(page):
    """`mz/ocr/` supplies geometry. Text arrives **only** through `decision.json`,
    which is what keeps a recognizer's reading from becoming ground truth by
    proximity — CATMuS reads 0% of the transcription inventory."""
    from harness.lines import page_lines
    restore("1-060", "mz/ocr", page, commit=True)
    got = [r["text"] for r in page_lines(page / "gt" / "ocr" / "chukchi-1-060.xml")]
    assert got == ["human one", "human two"]
    assert "machine one" not in got


def test_the_machine_geometry_does_survive(page):
    """The half that *is* adopted, and the reason to source from `mz/` at all: a
    page nobody has segmented has no lines to write text into."""
    from harness.lines import page_lines
    restore("1-060", "mz/ocr", page, commit=True)
    src = page_lines(page / "mz" / "ocr" / "chukchi-1-060.xml")
    out = page_lines(page / "gt" / "ocr" / "chukchi-1-060.xml")
    # `strict`: a restore that changed the line count must fail here rather
    # than be checked over the common prefix and pass.
    for a, b in zip(src, out, strict=True):
        assert (a["line_id"], a["vpos"], a["baseline"]) == \
               (b["line_id"], b["vpos"], b["baseline"])


def test_the_preview_writes_nothing(page):
    """`--commit` gates a writer into the ground-truth store, here as everywhere."""
    rep = restore("1-060", "mz/ocr", page)
    assert rep["commit"] is False
    assert not (page / "gt" / "ocr" / "chukchi-1-060.xml").exists()


def test_a_partial_adjudication_is_still_refused(tmp_path):
    """Sourcing from `mz/` changes nothing about the refusals. A prediction has a
    line for every band it found, so a decision short of that is a hole — and
    ground truth with invisible holes is worse than none."""
    _mz_page(tmp_path)
    _proposal(tmp_path, ["human one", "human two"])
    save_decisions("1-060", {0: {"text": "human one"}}, tmp_path)
    with pytest.raises(ValueError, match="have no decision"):
        restore("1-060", "mz/ocr", tmp_path, commit=True)


def test_restoring_twice_needs_force(page):
    """Once the page is ground truth, the second write is a *revision* of human
    work and has to say so — the guard that survives from the rebuild."""
    restore("1-060", "mz/ocr", page, commit=True)
    with pytest.raises(ValueError, match="already holds"):
        restore("1-060", "mz/ocr", page, commit=True)
    rep = restore("1-060", "mz/ocr", page, force=True, commit=True)
    assert rep["mode"] == "restoration", "source is still mz/, so still not a revision"


def test_mz_satisfies_the_span_diffs_second_witness_rule(page):
    """`review`'s bare diff refuses when its source resolves to the ground truth
    the proposal produced. `mz/ocr/` is a different inode from `gt/ocr/`, so it is
    an independent witness — which is what the view is not, once the view starts
    resolving into `gt/`."""
    restore("1-060", "mz/ocr", page, commit=True)
    gt = page / "gt" / "ocr" / "chukchi-1-060.xml"
    mz = page / "mz" / "ocr" / "chukchi-1-060.xml"
    assert mz.resolve() != gt.resolve(), "the diff would compare a file with itself"

    # ...and the view, which points at gt once gt exists, is *not* independent.
    from harness.recognize import VIEWDIR, link_one
    link_one("1-060", page)
    view = page / VIEWDIR / "chukchi-1-060.xml"
    assert view.resolve() == gt.resolve()


def test_a_committed_restore_repoints_the_view_itself(page):
    """The promotion is the write **and** the relink, and `restore` does both.

    `link_one`'s docstring has always said promoting a page is "a matter of
    `restore` writing `gt/ocr/` and this relinking", and `ocr predict` has always
    paired the two for what it writes into `mz/ocr/`. `restore` did not, so a page
    restored from a prediction came back with `gt/ocr/` written and `ocr/` still
    naming `mz/ocr/` — a view one save out of date, visible only to whoever thought
    to run `ocr pages --show-store`, and indistinguishable there from a page still
    genuinely awaiting a keying session.
    """
    from harness.recognize import VIEWDIR
    view = page / VIEWDIR / "chukchi-1-060.xml"
    gt = page / "gt" / "ocr" / "chukchi-1-060.xml"

    # A preview must leave the disk alone — including the view.
    rep = restore("1-060", "mz/ocr", page, commit=False)
    assert rep["view"] == ""
    assert not gt.exists()

    rep = restore("1-060", "mz/ocr", page, commit=True)
    assert rep["view"] == "gt/ocr"
    assert view.resolve() == gt.resolve()


def test_the_restore_report_has_one_key_set_either_way(page):
    """`view` is `""` on a preview, never absent.

    A record list whose keys vary degrades TOON to the verbose nested form, and a
    caller should not have to know which branch produced a report to know which
    keys it has.
    """
    assert (set(restore("1-060", "mz/ocr", page, commit=False))
            == set(restore("1-060", "mz/ocr", page, commit=True)))
