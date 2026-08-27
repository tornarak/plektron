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
from harness.paths import all_refs

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

    `train assemble zones` was bitten by the resolving form: it followed its targets back
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
        F.require(tmp_path, F.W_FIGS)
    assert "views build" in str(e.value)
    assert F.W_FIGS in str(e.value)


def test_require_returns_the_path_when_it_is_there(tmp_path):
    (tmp_path / F.W_FIGS).mkdir(parents=True)
    assert F.require(tmp_path, F.W_FIGS) == tmp_path / F.W_FIGS


def test_require_is_silent_about_a_missing_store(tmp_path):
    """A store is a record, and an absent record is an empty one. Refusing here
    would refuse a fresh clone for having predicted nothing yet, which is not a
    defect but the ordinary starting state."""
    assert F.require(tmp_path, "mz/ocr") == tmp_path / "mz/ocr"


def test_the_same_function_refuses_a_farm_and_tolerates_a_store(tmp_path):
    """The asymmetry, in one place, over one function — because that is what shows
    the scope is the registry and not the call site.

    `harness ocr pages --store mz` reaches `all_refs(root, "mz/ocr")` through the
    very same `_refs_under` that `all_scans` reaches for `scans/`. A blanket
    refusal in that function would refuse a clone for having predicted nothing
    yet, which is not a defect but the ordinary starting state.

    Keep both halves here together. Read alone, either looks like an inconsistency
    worth tidying away — the `test_lookalike_scope.py` situation, where a
    consolidation was nearly carried out on an audit that mistook a real
    distinction for drift.
    """
    with pytest.raises(FileNotFoundError, match="scans extract"):
        all_refs(tmp_path, F.SCANS)             # a farm: never built
    assert all_refs(tmp_path, "mz/ocr") == []   # a store: nothing predicted yet
    assert all_refs(tmp_path, "gt/ocr") == []   # a store: nothing keyed yet


def test_the_store_enumerators_stay_permissive(tmp_path):
    """`zone_refs`/`ocr_refs` only ever walk stores, so nothing there should refuse.
    Five tests failed when a draft of the guard reached them, and every one was a
    fixture legitimately describing a corpus with no predictions in it."""
    from harness.recognize import MZDIR as OMZ
    from harness.recognize import ocr_refs
    from harness.zones import MZDIR as ZMZ
    from harness.zones import zone_refs

    assert zone_refs(tmp_path, ZMZ) == []
    assert ocr_refs(tmp_path, OMZ) == []


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
    assert rows["w-figs"]["state"] == "absent"
    assert rows["w-figs"]["entries"] == 0


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
    for ref in ("1-048", "1-060"):
        write_scan(tmp_path, ref)
        (tmp_path / "gt" / "ocr" / f"chukchi-{ref}.xml").write_text("<x/>")

    # Built when the store held only one page — the farm's state before today.
    F.rebuild(tmp_path / F.W_OCR,
              {"chukchi-1-048.png": tmp_path / "scans" / "chukchi-1-048.png"},
              "chukchi-*.png")
    F.rebuild(tmp_path / F.W_OCR,
              {"chukchi-1-048.xml": tmp_path / "gt" / "ocr" / "chukchi-1-048.xml"},
              "chukchi-*.xml")

    assert {r["farm"]: r for r in F.survey(tmp_path)}["w-ocr"]["state"] == "stale"
    F.build("w-ocr", tmp_path)
    assert {r["farm"]: r for r in F.survey(tmp_path)}["w-ocr"]["state"] == "ok"
    # And the ALTO names the ground-truth store, the only store it ever selects from.
    assert (tmp_path / F.W_OCR / "chukchi-1-060.xml").readlink() == \
        Path("../../gt/ocr/chukchi-1-060.xml")


def test_a_non_page_file_beside_the_altos_is_not_a_page(tmp_path):
    """Two different exclusions, and this test used to exercise only one.

    It was written for the tracked `gt/ocr/METS.xml` — since removed, being a
    `#mz` manifest that had gone stale at 20 files against 663 — and named a
    file `METS`, which the `chukchi-*.xml` glob never matched. So it passed
    without ever reaching the `except ValueError` it was written to cover.

    Both arms are asserted now: a name the glob rejects, and a name the glob
    accepts but `norm_ref` cannot parse, which is the only path to the guard.
    """
    (tmp_path / "gt" / "ocr").mkdir(parents=True)
    (tmp_path / "gt" / "ocr" / "chukchi-1-048.xml").write_text("<x/>")
    (tmp_path / "gt" / "ocr" / "METS.xml").write_text("<x/>")        # glob
    (tmp_path / "gt" / "ocr" / "chukchi-draft.xml").write_text("<x/>")  # guard
    pngs, xmls = F._w_ocr_wanted(tmp_path)
    assert set(xmls) == {"chukchi-1-048.xml"}


def test_there_is_no_view_farm(tmp_path):
    """`ocr/` and `zones/` were symlink views over the paired stores, and every
    reader that took no store read through them — a blend of ranks in front of the
    layer whose subject is rank. Retired; a store is named or nothing is read."""
    assert not any(f.kind == "view" for f in F.FARMS)
    assert F.farm_for("ocr") is None and F.farm_for("zones") is None
    # …and so `require` tolerates the bare names like any other non-farm path.
    assert F.require(tmp_path, "ocr") == tmp_path / "ocr"


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


# ---------------------------------------------------------- the farm selector

def test_all_expands_to_the_pool_it_was_asked_about():
    """`all` means every farm of the *asked* kind, which is not one set.

    `check` reports `scans/` and `train/` and `build` cannot make either, so an
    `all` that meant the same thing on both would either hand `build` two farms it
    has no builder for or hide two from `check`.
    """
    assert F.select([F.ALL]) == F.NAMES
    assert F.select([F.ALL], buildable_only=True) == F.BUILDABLE
    assert "scans" in F.select([F.ALL]) and "scans" not in F.BUILDABLE


def test_a_selection_comes_back_in_registry_order():
    """Order is the registry's and survives however it was typed, so a selection
    is reproducible; duplicates collapse, since asking twice is a typo."""
    assert F.select(["w-ocr", "w-figs"], buildable_only=True) == ("w-figs", "w-ocr")
    assert F.select(["w-ocr", "w-ocr"], buildable_only=True) == ("w-ocr",)


def test_a_bare_build_is_a_usage_error_not_a_build_of_everything():
    """The expensive default, removed.

    Rebuilding the blot tree repaints 252 page composites, and nothing at the call
    site says so — the caller who wanted one view relinked after a `restore` was
    the one paying for it. Exit 2 is the harness's usage-error code, and
    deliberately not the 1 that means a documented gate failed.

    The message is the handler's rather than argparse's since the FARM positional
    became `nargs="*"` beside `--all`, which is the spelling the rest of the CLI
    uses for "everything". Asserting on the *word* would pin whichever of the two
    happens to answer; what the test is for is that a bare invocation refuses and
    that the refusal names the flag that would not have.
    """
    r = subprocess.run(["uv", "run", "harness", "views", "build"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 2
    assert "--all" in r.stderr


def test_check_gates_only_over_the_farms_it_was_asked_about(tmp_path):
    """Scoping the selection scopes the exit code.

    Asking about `w-figs` and being failed for a blot tree nobody named would make
    the code unreadable — and unreadable is how an exit code stops being acted on.
    """
    (tmp_path / "gt" / "fig").mkdir(parents=True)
    (tmp_path / "gt" / "fig" / "chukchi-1-048.xml").write_text("<x/>")
    write_scan(tmp_path, "1-048")
    F.build("w-figs", tmp_path)                     # w-figs is now ok; nothing else exists
    rows = {r["farm"]: r for r in F.survey(tmp_path)}
    assert rows["w-figs"]["state"] == "ok"
    assert rows["w-ocr"]["state"] == "absent"       # would gate, if asked about


# ------------------------------------------------------- the leaf-kind farms

def test_every_leaf_kind_has_a_farm_and_no_farm_outlives_a_kind():
    """`farms._LEAF_KINDS` copies the vocabulary down from `zones`, and a copy is
    a thing that drifts. The failure is quiet in both directions: a kind with no
    farm makes `views check` report its directory as an unregistered stray, and a
    farm with no kind builds an empty directory forever."""
    from harness.zones import LEAF_KINDS
    assert F._LEAF_KINDS == LEAF_KINDS
    for kind in LEAF_KINDS:
        assert F.BY_NAME[kind].path == f"{F.SCANS}/{kind}"
        assert F.BY_NAME[kind].kind == "select"


def test_a_leaf_farm_holds_the_leaves_ruled_that_kind(tmp_path):
    """Membership is the split list, not what is in the directory — which is what
    makes this checkable at all rather than a record of whatever somebody dragged
    where."""
    from harness import zones as zn
    for ref in ("1-049", "1-050"):
        write_scan(tmp_path, ref, (2824, 3897))
    zn.save_zones("1-049", [], tmp_path, split="plate")
    zn.save_zones("1-050", [], tmp_path, split="blank")

    F.build("plate", tmp_path)
    F.build("blank", tmp_path)
    rows = {r["farm"]: r for r in F.survey(tmp_path)}
    assert (rows["plate"]["state"], rows["plate"]["entries"]) == ("ok", 1)
    assert (rows["blank"]["state"], rows["blank"]["entries"]) == ("ok", 1)
    assert (tmp_path / "scans" / "plate" / "chukchi-1-049.png").exists()


def test_re_ruling_a_leaf_moves_it_rather_than_leaving_it_in_both(tmp_path):
    """The state that would otherwise be silent: a leaf re-ruled `plate` -> `blank`
    still linked from `scans/plate/`, where the directory says one thing and the
    store another. `rebuild` removes what the criterion no longer wants, so the
    stale farm reports `stale` before the rebuild and is empty after it."""
    from harness import zones as zn
    write_scan(tmp_path, "1-049", (2824, 3897))
    zn.save_zones("1-049", [], tmp_path, split="plate")
    F.build("plate", tmp_path)

    zn.set_split("1-049", "blank", tmp_path)
    assert {r["farm"]: r["state"] for r in F.survey(tmp_path)}["plate"] == "stale"
    F.build("plate", tmp_path)
    F.build("blank", tmp_path)
    assert not (tmp_path / "scans" / "plate" / "chukchi-1-049.png").exists()
    assert (tmp_path / "scans" / "blank" / "chukchi-1-049.png").exists()
