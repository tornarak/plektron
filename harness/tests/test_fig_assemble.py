"""The figure segmenter's training set: what goes in it, and what says so.

Two things here are not the zone track's, and both would be invisible if they
broke.

**The raster is the raw scan.** `train assemble zones` links `scans/w-figs-blotted/`
so the zone segmenter cannot learn figure-shaped body zones. The blot paints
figures white, so linking it here would ask this model to find something that
has been erased — and the failure would look like a model that simply never
learns, with nothing pointing at the input.

**Negatives are synthesized at assemble time and stored nowhere.** `gt/fig/`
never holds an empty ALTO: absence of the file is how it records "no figures",
and `zones blot`, `ocr gaps` and the reader dispatch all read an existing file as
"this page has figures". So the empty region set that teaches the model most
pages are empty has to be minted here. Verified against kraken 7.0.3 rather than
assumed — an empty-region ALTO parses to a `baselines` container with no regions
and `BaselineSet.add` accepts it.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_scan

from harness import figures as F
from harness import zones as zn

G, D = F.GRAPHIC, F.FIGDESC


def _box(label, x0, y0, x1, y1):
    return {"label": label, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for ref in ("1-021", "1-022", "1-037"):
        write_scan(tmp_path, ref, size=(2824, 3897))
    # One positive, two pages with no figure ALTO at all.
    F.save_figs("1-037", [_box(G, 400, 900, 2200, 2500)], tmp_path)
    F.set_split("1-021", "train", tmp_path)
    F.set_split("1-022", "eval", tmp_path)
    return tmp_path


def test_the_raster_is_the_raw_scan_not_the_blot(root):
    """The link a copy-paste from `train assemble zones` would get wrong."""
    (root / zn.BLOTDIR).mkdir(parents=True, exist_ok=True)
    (root / zn.BLOTDIR / "chukchi-1-037.png").write_bytes(b"not the scan")
    F.assemble(root)
    link = root / F.DATADIR / "chukchi-1-037.png"
    assert link.resolve() == (root / "scans/chukchi-1-037.png").resolve()


def test_a_positive_links_its_own_alto(root):
    F.assemble(root)
    link = root / F.DATADIR / "chukchi-1-037.xml"
    assert link.is_symlink()
    assert link.resolve() == F.alto_for("1-037", root).resolve()


def test_a_negative_gets_a_synthesized_empty_alto(root):
    """Written into the work dir, and **not** into the store."""
    res = F.assemble(root)
    assert res["negatives"] == 2 and res["positives"] == 1
    xml = root / F.DATADIR / "chukchi-1-021.xml"
    assert xml.exists() and not xml.is_symlink()
    assert F.read_blocks(xml) == []
    assert not F.alto_for("1-021", root).exists()


def test_the_store_still_holds_no_empty_file_afterwards(root):
    """The invariant every reader of `gt/fig/` depends on."""
    F.assemble(root)
    assert sorted(F.fig_refs(root)) == ["1-037"]


def test_the_lists_are_relative_and_unresolved(root):
    """Resolving follows the symlink back to `gt/fig/` and silently trains on the
    store instead of the work dir — `train assemble zones` paid for this once."""
    F.assemble(root)
    lines = (root / F.DATADIR / "train.lst").read_text().split()
    assert lines and all(ln.startswith(f"{F.DATADIR}/") for ln in lines)
    assert not any(ln.startswith("/") for ln in lines)
    assert "gt/fig" not in (root / F.DATADIR / "train.lst").read_text()


def test_the_splits_decide_the_lists(root):
    F.assemble(root)
    train = (root / F.DATADIR / "train.lst").read_text()
    ev = (root / F.DATADIR / "eval.lst").read_text()
    assert "chukchi-1-021.xml" in train and "chukchi-1-022.xml" in ev
    assert "chukchi-1-022.xml" not in train


def test_a_page_with_no_raster_is_reported_not_guessed(root):
    F.set_split("2-999", "train", root)
    res = F.assemble(root)
    assert res["missing_raster"] == ["2-999"]
    assert "chukchi-2-999.xml" not in (root / F.DATADIR / "train.lst").read_text()


def test_the_reported_command_names_the_work_dir_and_runs_nothing(root):
    res = F.assemble(root)
    assert f"-t {F.DATADIR}/train.lst" in res["command"]
    assert f"-e {F.DATADIR}/eval.lst" in res["command"]
    assert "segtrain" in res["command"]
    assert not (root / F.RUNDIR / "run-1").exists()


def test_the_track_base_holds_nothing_but_the_two_halves(root):
    """The layout, asserted rather than described: page links and lists in `data/`,
    checkpoints in `model/`, and nothing loose beside them."""
    F.assemble(root)
    assert sorted(p.name for p in (root / F.WORKDIR).iterdir()) == ["data", "model"]


def test_blla_is_the_base_and_scratch_drops_it(root):
    (root / "models").mkdir(exist_ok=True)
    (root / "models/blla.mlmodel").write_bytes(b"stub")
    res = F.assemble(root)
    assert "--resize new" in res["command"] and res["base"] == "models/blla.mlmodel"
    scr = F.assemble(root, scratch=True)
    assert "-i " not in scr["command"] and scr["base"].startswith("scratch")


def test_no_base_model_says_so_rather_than_silently_training_from_scratch(root):
    """Fine-tuning and random init are different experiments, and the one that
    arrives by a missing file is the one nobody chose."""
    res = F.assemble(root)
    assert res["base"] == "scratch (no base model found)"
    assert "--scratch to mean that deliberately" in res["note"]


# --- the negative witness ----------------------------------------------------

def test_a_page_with_unaccounted_ink_is_unknown_not_negative(tmp_path):
    """The clause `1-191` justifies: unaccounted ink may *be* an undeclared
    figure, so such a page cannot be a witness that there is none."""
    write_scan(tmp_path, "1-021", size=(2824, 3897))
    zn.save_zones("1-021", [{"label": "MainZone-P", "x0": 300, "y0": 600,
                             "x1": 2100, "y1": 900}], tmp_path)
    zn.record_ink("1-021", {"ink_checked": True, "warnings": [],
                            "uncovered": [{"vpos": 1000, "height": 400,
                                           "note": "", "exempted": False}]},
                  tmp_path)
    out = F.negative_refs(tmp_path)
    assert out["negative"] == [] and out["unknown"] == ["1-021"]


def test_an_excused_band_is_unknown_not_negative(tmp_path):
    """The load-bearing half. A band ruled 'not type' makes the check read clean
    while hiding exactly the ink a figure would be — `1-033`, `1-035` and `1-036`
    are the live instances, all 'scanner artifact'."""
    write_scan(tmp_path, "1-021", size=(2824, 3897))
    zn.save_zones("1-021", [{"label": "MainZone-P", "x0": 300, "y0": 600,
                             "x1": 2100, "y1": 900}], tmp_path)
    zn.record_ink("1-021", {"ink_checked": True, "warnings": [],
                            "uncovered": [{"vpos": 1000, "height": 400,
                                           "note": "scanner artifact",
                                           "exempted": True}]}, tmp_path)
    assert F.negative_refs(tmp_path)["unknown"] == ["1-021"]


def test_a_clean_page_is_a_negative(tmp_path):
    write_scan(tmp_path, "1-021", size=(2824, 3897))
    zn.save_zones("1-021", [{"label": "MainZone-P", "x0": 300, "y0": 600,
                             "x1": 2100, "y1": 900}], tmp_path)
    zn.record_ink("1-021", {"ink_checked": True, "warnings": [],
                            "uncovered": []}, tmp_path)
    assert F.negative_refs(tmp_path)["negative"] == ["1-021"]


def test_an_exempt_page_is_never_a_negative(tmp_path):
    """Exempt means "not a text page" — a plate — and plates are where figures
    live. The ink check never ran over it, so it witnesses nothing."""
    write_scan(tmp_path, "1-021", size=(2824, 3897))
    zn.save_zones("1-021", [], tmp_path, split="plate")
    assert F.negative_refs(tmp_path)["negative"] == []


def test_a_cold_cache_yields_unknowns_rather_than_a_small_corpus(tmp_path):
    """The reporting requirement. With no verdicts at all every page is unknown,
    and `remark_eval` has to say so rather than mint a split from nothing."""
    write_scan(tmp_path, "1-021", size=(2824, 3897))
    zn.save_zones("1-021", [{"label": "MainZone-P", "x0": 300, "y0": 600,
                             "x1": 2100, "y1": 900}], tmp_path)
    assert F.negative_refs(tmp_path)["unknown"] == ["1-021"]
    out = F.remark_eval(tmp_path)
    assert out["unknown"] == 1 and "zones check --all --ink" in out["note"]


def test_remark_eval_never_moves_a_human_mark(root):
    F.set_split("1-022", "eval", root)
    F.remark_eval(root, fraction=1.0, commit=True)
    assert F.load_splits(root)["1-022"] == "eval"
