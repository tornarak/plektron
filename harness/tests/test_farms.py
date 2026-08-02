"""The derived-tree registry: the shared linking, and the absent/empty distinction.

Two things are pinned here that nothing else can pin.

**A link that must not be resolved.** `relink(resolve=False)` exists because
`scans/w-ocr/`'s ALTO links point at the `ocr/` *view* by design, so that promoting
a page re-points the view and the farm needs no rebuild. Resolved, they would become
links into `gt/ocr/` — every entry would still open the right file, every test that
checked the file's *contents* would pass, and the property would be gone. So the
assertion has to be lexical (`readlink`), not `resolve()`: a test written the obvious
way is a test that cannot fail.

**Absent is not empty, but only for farms.** A missing `ocr/` means nobody built the
view; a missing `mz/ocr/` means nothing has been predicted. The first is a question
never asked, the second is a record that is empty and a perfectly ordinary state.
`test_the_same_function_refuses_a_farm_and_tolerates_a_store` holds both halves in
one place, over one function, because the difference is exactly the kind that gets
"tidied up" by someone who sees only one side of it — the `test_lookalike_scope.py`
precedent.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import write_scan

from harness import farms as F

REPO = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------- the mechanics

def test_a_link_is_relative_so_it_survives_a_clone(tmp_path):
    """An absolute link records this machine and breaks the moment the repo moves."""
    (tmp_path / "store").mkdir()
    target = tmp_path / "store" / "page.xml"
    target.write_text("x")
    view = tmp_path / "view"
    view.mkdir()

    F.relink(view / "page.xml", target)
    assert (view / "page.xml").readlink() == Path("../store/page.xml")


def test_relinking_replaces_rather_than_raising(tmp_path):
    """A rebuild runs over a farm that already exists; that is the normal case."""
    (tmp_path / "store").mkdir()
    for n in ("a.xml", "b.xml"):
        (tmp_path / "store" / n).write_text("x")
    view = tmp_path / "view"
    view.mkdir()

    F.relink(view / "page.xml", tmp_path / "store" / "a.xml")
    F.relink(view / "page.xml", tmp_path / "store" / "b.xml")
    assert (view / "page.xml").readlink() == Path("../store/b.xml")


def test_resolve_false_keeps_a_link_to_a_link(tmp_path):
    """The `w-ocr` case, and the reason the assertion is lexical.

    `zones assemble` was bitten by the resolving form: it followed its targets back
    to `gt/zones/`, so kraken looked for rasters beside the real ALTOs and the blot
    links the function existed to make were never read. Both links below open the
    same bytes; only `readlink` can tell them apart.
    """
    (tmp_path / "store").mkdir()
    real = tmp_path / "store" / "page.xml"
    real.write_text("x")
    (tmp_path / "view").mkdir()
    F.relink(tmp_path / "view" / "page.xml", real)
    (tmp_path / "farm").mkdir()

    F.relink(tmp_path / "farm" / "page.xml", tmp_path / "view" / "page.xml",
             resolve=False)
    assert (tmp_path / "farm" / "page.xml").readlink() == Path("../view/page.xml")
    # It still reaches the file — which is why the lexical check is the only one
    # that means anything here.
    assert (tmp_path / "farm" / "page.xml").read_text() == "x"

    F.relink(tmp_path / "farm" / "page.xml", tmp_path / "view" / "page.xml")
    assert (tmp_path / "farm" / "page.xml").readlink() == Path("../store/page.xml")


def test_rebuild_prunes_what_the_criterion_no_longer_selects(tmp_path):
    """A farm that only ever grew would keep a page deleted from its store, and
    nothing would say so."""
    (tmp_path / "store").mkdir()
    for n in ("a.xml", "b.xml"):
        (tmp_path / "store" / n).write_text("x")
    farm = tmp_path / "farm"

    F.rebuild(farm, {n: tmp_path / "store" / n for n in ("a.xml", "b.xml")},
              "*.xml")
    rep = F.rebuild(farm, {"a.xml": tmp_path / "store" / "a.xml"}, "*.xml")

    assert rep["removed"] == 1
    assert rep["linked"] == 1
    assert not (farm / "b.xml").exists()


def test_a_prune_pattern_does_not_eat_the_other_kind(tmp_path):
    """`scans/w-ocr/` holds PNGs and XMLs and is swept once per kind. One sweep with
    a `*` pattern would have each kind deleting the other's entries."""
    (tmp_path / "store").mkdir()
    (tmp_path / "store" / "p.png").write_text("x")
    (tmp_path / "store" / "p.xml").write_text("x")
    farm = tmp_path / "farm"

    F.rebuild(farm, {"p.png": tmp_path / "store" / "p.png"}, "*.png")
    F.rebuild(farm, {"p.xml": tmp_path / "store" / "p.xml"}, "*.xml")

    assert (farm / "p.png").exists() and (farm / "p.xml").exists()


# ------------------------------------------------------------ absent vs empty

def test_require_names_the_command_that_builds_it(tmp_path):
    """The whole point of refusing: the error has to end the problem, not start it."""
    with pytest.raises(FileNotFoundError) as e:
        F.require(tmp_path, F.OCR_VIEW)
    assert "views build" in str(e.value)
    assert F.OCR_VIEW in str(e.value)


def test_require_returns_the_path_when_it_is_there(tmp_path):
    (tmp_path / F.OCR_VIEW).mkdir(parents=True)
    assert F.require(tmp_path, F.OCR_VIEW) == tmp_path / F.OCR_VIEW


def test_require_is_silent_about_a_missing_store(tmp_path):
    """A store is a record, and an absent record is an empty one. Refusing here
    would refuse a fresh clone for having predicted nothing yet, which is not a
    defect but the ordinary starting state."""
    assert F.require(tmp_path, "mz/ocr") == tmp_path / "mz/ocr"


def test_farm_for_matches_the_path_exactly_never_a_parent(tmp_path):
    """`scans/` and `scans/w-figs/` are both registered and are different farms;
    `gt/ocr/` is inside no farm at all. A prefix match would fold a store into a
    farm and hand `require` the case it must not touch."""
    assert F.farm_for("scans").name == "scans"
    assert F.farm_for("scans/w-figs").name == "w-figs"
    assert F.farm_for("gt/ocr") is None
    assert F.farm_for("scans/chukchi-1-048.png") is None


# ------------------------------------------------------------------ the survey

def test_survey_reports_absent_rather_than_empty(tmp_path):
    """Blank is indistinguishable from clean, which is the fault this exists for."""
    rows = {r["farm"]: r for r in F.survey(tmp_path)}
    assert rows["ocr"]["state"] == "absent"
    assert rows["ocr"]["entries"] == 0


def test_survey_will_not_call_a_verdict_it_cannot_compute(tmp_path):
    """`scans/` has no criterion in this repo, so its row is `?` and its `verified`
    is `none`. Reporting `ok` would be a clean bill of health nobody issued."""
    (tmp_path / "scans").mkdir()
    row = {r["farm"]: r for r in F.survey(tmp_path)}["scans"]
    assert row["state"] == "?"
    assert row["verified"] == "none"


def test_the_raster_farm_never_claims_its_content_was_checked(tmp_path):
    """Membership is knowable; freshness is not. `zones.blot_all` refuses an mtime
    test as unsound — a figure ALTO corrected after the blot was written leaves a
    raster still showing the figure — so `state: ok` must not imply more than was
    tested."""
    row = {f.name: f for f in F.FARMS}["w-figs-blotted"]
    assert row.verified == "membership"
    assert row.verified != "membership+content"


def test_a_page_promoted_to_gt_makes_the_selection_stale_then_ok(tmp_path):
    """The live defect this builder was written for, generalised: `scans/w-ocr/` was
    missing `1-060` because nothing rebuilds a hand-made farm when gt gains a page."""
    (tmp_path / "gt" / "ocr").mkdir(parents=True)
    (tmp_path / F.OCR_VIEW).mkdir(parents=True)
    for ref in ("1-048", "1-060"):
        write_scan(tmp_path, ref)
        (tmp_path / "gt" / "ocr" / f"chukchi-{ref}.xml").write_text("<x/>")
        F.relink(tmp_path / F.OCR_VIEW / f"chukchi-{ref}.xml",
                 tmp_path / "gt" / "ocr" / f"chukchi-{ref}.xml")

    # Built when the store held only one page — the farm's state before today.
    F.rebuild(tmp_path / F.W_OCR,
              {"chukchi-1-048.png": tmp_path / "scans" / "chukchi-1-048.png"},
              "chukchi-*.png")
    F.rebuild(tmp_path / F.W_OCR,
              {"chukchi-1-048.xml": tmp_path / F.OCR_VIEW / "chukchi-1-048.xml"},
              "chukchi-*.xml", resolve=False)

    assert {r["farm"]: r for r in F.survey(tmp_path)}["w-ocr"]["state"] == "stale"
    F.build("w-ocr", tmp_path)
    assert {r["farm"]: r for r in F.survey(tmp_path)}["w-ocr"]["state"] == "ok"
    # And the ALTO still points at the view, not through it.
    assert (tmp_path / F.W_OCR / "chukchi-1-060.xml").readlink() == \
        Path("../../ocr/chukchi-1-060.xml")


def test_METS_is_not_a_page(tmp_path):
    """`gt/ocr/METS` exists and would otherwise be selected into the farm."""
    (tmp_path / "gt" / "ocr").mkdir(parents=True)
    (tmp_path / "gt" / "ocr" / "chukchi-1-048.xml").write_text("<x/>")
    (tmp_path / "gt" / "ocr" / "METS").write_text("<x/>")
    pngs, xmls = F._w_ocr_wanted(tmp_path)
    assert set(xmls) == {"chukchi-1-048.xml"}


def test_a_builder_whose_source_is_absent_is_skipped_with_a_row(tmp_path):
    """Not attempted and not silently dropped. The blot builder opens pixels out of
    `scans/`, so on a clone it cannot run — and dying inside the sweep would leave
    half the farms built with an error naming `pdftoppm` when the views were asked
    for."""
    (tmp_path / "gt" / "fig").mkdir(parents=True)
    rep = F.build("w-figs-blotted", tmp_path)
    assert rep["skipped"] == "no scans/"
    assert rep["linked"] == 0


def test_a_selection_still_builds_with_no_scans(tmp_path):
    """The read/point-at distinction. `w-figs` needs only its tracked membership
    source; an absent `scans/` leaves its links dangling, which is this repo's
    stated disposition for a link into an ignored tree."""
    (tmp_path / "gt" / "fig").mkdir(parents=True)
    (tmp_path / "gt" / "fig" / "chukchi-1-048.xml").write_text("<x/>")
    rep = F.build("w-figs", tmp_path)
    assert rep["skipped"] == ""
    assert rep["linked"] == 1
    link = tmp_path / F.W_FIGS / "chukchi-1-048.png"
    assert link.is_symlink() and not link.exists()      # dangles, loudly


# --------------------------------------------------- the registry vs .gitignore

def test_every_farm_is_gitignored():
    """The analogue of `test_layout.py`'s `DERIVED == gitignored` gate: a farm added
    later must not start committing PNGs as noise.

    Asked of **git**, not of the file's lines. The farms under `scans/` are covered
    by the parent rule rather than by their own entries, so a line-parsing check
    would report them unignored while git ignores them perfectly well — a test that
    fails for being wrong about how the file works.
    """
    for farm in F.FARMS:
        probe = f"{farm.path}/probe.png"
        r = subprocess.run(["git", "check-ignore", "-q", probe],
                           cwd=REPO, capture_output=True)
        assert r.returncode == 0, f"{farm.path} is a farm but is not gitignored"
