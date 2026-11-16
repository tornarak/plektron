"""The zone review pass: an agent's verdict, edits against the rule's zones.

A fixture page is proposed by the rule (`zones propose --commit`), so every test
edits a real `mz/zones/` file with its real provenance, and line indices are the
text layer's. The page, at the fixture's 300 dpi:

    band 1  RunningTitleZone     line 0
    band 2  MainZone-P           lines 1 2 3
    band 3  MainZone-Continued   lines 4 5          (after a gap)
            (no band)            line 6             (too wide to be one line)
    band 4  MainZone-Continued   lines 7 8
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from conftest import chukchi_zone_config, write_scan, write_zone_config
from test_zones_rule import FX_M, FX_RULE, FX_X0, _alto

from harness import dispatch, zones, zones_review, zones_rule
from harness import zones_ui as ui
from harness.paths import verdict_path

REF = "1-002"


def _page(tmp_path, ref=REF, fused=True, tall=False):
    rows = [(FX_X0, 300, FX_M, 50, "2 Г. БОГОРАЗЪ"),
            (FX_X0 + 105, 420, FX_M - 105, 50, "Первая строка"),
            (FX_X0, 482, FX_M, 50, "продолженіе"),
            (FX_X0, 544, FX_M, 50, "продолженіе"),
            # Flush after the gap on the flagged page; indented on the plain one,
            # where a Continued band there would be a flag of its own.
            (FX_X0 if fused else FX_X0 + 105, 700, FX_M if fused else FX_M - 105, 50,
             "послѣ пробѣла"),
            (FX_X0, 762, FX_M, 50, "продолженіе")]
    if fused:
        rows.append((FX_X0 - 480, 824, FX_M + 600, 90 if tall else 50, "} сросшаяся"))
    # Without the fused row the paragraph runs on at the body's pitch.
    y = 886 if fused else 824
    rows += [(FX_X0, y, FX_M, 50, "продолженіе"), (FX_X0, y + 62, FX_M, 50, "конецъ")]
    p = tmp_path / "mz" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_alto(rows, "harness ocr import"))
    # Ink under each line, clipped to the column, so the window is measured off
    # the page rather than falling back (a fallback is a flag of its own).
    write_scan(tmp_path, ref, ink=tuple((FX_X0 + 5, y + 10, FX_X0 + FX_M - 5, y + 40)
                                        for _, y, _, _, _ in rows))
    zones.set_splits({ref: "train"}, tmp_path)
    zones_rule.propose_many([ref], tmp_path, commit=True, force=True)


@pytest.fixture
def root(tmp_path):
    cfg = chukchi_zone_config()
    cfg["text_rule"] = FX_RULE
    write_zone_config(tmp_path, cfg)
    _page(tmp_path)
    return tmp_path


def _verdict(root, edits, notes=(), **over):
    base = zones_review.baseline(REF, root)
    v = {"ref": REF, "reviewed": {"file": base["file"],
                                  "bands_sha256": base["bands_sha256"]},
         "bands": len(base["bands"]), "edits": list(edits), "notes": list(notes)}
    v.update(over)
    p = verdict_path(REF, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    return v


def rules(root) -> list[str]:
    return [e["rule"] for e in zones_review.issues(REF, root)["errors"]]


def applied(root) -> list[dict]:
    rec = zones_review.issues(REF, root)
    assert rec["errors"] == [], rec["errors"]
    return rec["zones"]


# ---------------------------------------------------------------- the baseline


def test_bands_are_numbered_with_their_lines_and_the_rest_listed(root):
    b = zones_review.baseline(REF, root)
    assert [(r["band"], r["label"], r["lines"]) for r in b["bands"]] == [
        (1, "RunningTitleZone", "0"), (2, "MainZone-P", "1 2 3"),
        (3, "MainZone-Continued", "4 5"), (4, "MainZone-Continued", "7 8")]
    assert [u["index"] for u in b["unbanded"]] == [6]
    assert b["flags"] == "unzoned,continued"
    assert b["file"] == f"mz/zones/chukchi-{REF}.xml"


def test_the_baseline_is_read_off_the_file_never_re_derived(root):
    # Hand-edit the rule's file: the baseline follows the file, not the rule.
    p = zones.alto_for(REF, root, zones.MZDIR)
    p.write_text(p.read_text(encoding="utf-8").replace(
        "MainZone-P", "MainZone-Other"), encoding="utf-8")
    assert zones_review.baseline(REF, root)["bands"][1]["label"] == "MainZone-Other"


def _rewrite_zones(root, old: str, new: str) -> None:
    p = zones.alto_for(REF, root, zones.MZDIR)
    text = p.read_text(encoding="utf-8")
    assert old in text
    p.write_text(text.replace(old, new), encoding="utf-8")


def test_moving_the_column_keeps_a_verdict_fresh(root):
    # The window moved 22 px left of the ink on every Materials page: the zones'
    # x changed and no band did, so no verdict's band numbers changed meaning.
    _verdict(root, [])
    z = zones.read_zones(REF, root, store=zones.MZDIR)[0]
    _rewrite_zones(root, f'HPOS="{z["x0"]}"', f'HPOS="{z["x0"] - 22}"')
    assert rules(root) == [] and zones_review.fresh(REF, root)


def test_moving_a_band_edge_stales_a_verdict(root):
    _verdict(root, [])
    z = zones.read_zones(REF, root, store=zones.MZDIR)[1]
    _rewrite_zones(root, f'VPOS="{z["y0"]}"', f'VPOS="{z["y0"] - 3}"')
    assert rules(root) == ["stale"] and not zones_review.fresh(REF, root)


def test_a_whole_file_digest_is_stale_until_restamped_on_its_witness(root):
    base = zones_review.baseline(REF, root)
    _verdict(root, [], reviewed={"file": base["file"], "sha256": base["sha256"]})
    assert rules(root) == ["stale"]
    assert zones_review.restamp(REF, root) == "restamped"      # a report
    assert rules(root) == ["stale"]
    assert zones_review.restamp(REF, root, commit=True) == "restamped"
    assert rules(root) == [] and zones_review.restamp(REF, root) == "already"
    # A digest the file no longer has is no witness to these bands.
    _verdict(root, [], reviewed={"file": base["file"], "sha256": "0" * 64})
    assert zones_review.restamp(REF, root, commit=True) == "stale"
    assert rules(root) == ["stale"]


def test_a_parts_window_widens_the_zone_and_not_the_rows_measure(root):
    from harness.zones_config import load_config
    cfg = chukchi_zone_config()
    cfg["text_rule"] = FX_RULE
    cfg["columns"]["parts"]["1"]["window"] = FX_M + 30
    write_zone_config(root, cfg)
    cfg = load_config(root)
    w = zones.page_windows(REF, root, cfg)[0]
    assert w["x1"] - w["x0"] == FX_M + 30
    assert cfg["columns"]["parts"]["1"]["measure"] == FX_M
    cfg["columns"]["parts"]["1"]["window"] = FX_M - 1
    write_zone_config(root, cfg)
    with pytest.raises(ValueError, match="no narrower than its measure"):
        load_config(root)


def test_a_page_with_no_rule_file_is_missing(root):
    zones.alto_for(REF, root, zones.MZDIR).unlink()
    with pytest.raises(zones_review.Missing, match="zones propose"):
        zones_review.baseline(REF, root)


# ---------------------------------------------------------------- apply


def test_a_relabel_and_a_split_on_one_band_both_hold(root):
    _verdict(root, [{"op": "relabel", "band": 2, "label": "MainZone-Other", "why": "a"},
                    {"op": "split", "line": 3, "label": "MainZone-P", "why": "b"}])
    got = applied(root)
    assert [z["label"] for z in got] == ["RunningTitleZone", "MainZone-Other",
                                         "MainZone-P", "MainZone-Continued",
                                         "MainZone-Continued"]
    # The midpoint between line 2's bottom (532) and line 3's top (544).
    assert got[1]["y1"] == got[2]["y0"] == 538
    assert got[1]["why"] == ["a", "b"] and got[2]["why"] == ["b"]


def test_a_merge_takes_the_label_of_the_band_above(root):
    before = zones_review.baseline(REF, root)["zones"]
    _verdict(root, [{"op": "relabel", "band": 3, "label": "MainZone-P", "why": "a"},
                    {"op": "merge", "band": 4, "why": "b"}])
    got = applied(root)
    assert len(got) == 3
    assert got[2]["label"] == "MainZone-P"
    assert (got[2]["y0"], got[2]["y1"]) == (before[2]["y0"], before[3]["y1"])
    assert got[2]["why"] == ["a", "b"]


def test_an_absorb_extends_the_side_it_names(root):
    _verdict(root, [{"op": "absorb", "line": 6, "into": "above", "why": "a"}])
    assert applied(root)[2]["y1"] == 824 + 50
    _verdict(root, [{"op": "absorb", "line": 6, "into": "below", "why": "a"}])
    assert applied(root)[3]["y0"] == 824


def test_an_absorb_inside_a_merge_stretches_no_other_band(root):
    # The pilot's 1-100: a note's flush second line, then its run-on band merged
    # up. The merge spans the line, so the absorb must not reach for band 2.
    before = zones_review.baseline(REF, root)["zones"]
    _verdict(root, [{"op": "absorb", "line": 6, "into": "above", "why": "a"},
                    {"op": "merge", "band": 4, "why": "b"}])
    got = applied(root)
    assert len(got) == 3 and got[1] == before[1]
    assert (got[2]["y0"], got[2]["y1"]) == (before[2]["y0"], before[3]["y1"])
    assert got[2]["why"] == ["b", "a"]


def test_bands_no_edit_touched_come_back_exactly(root):
    before = zones_review.baseline(REF, root)["zones"]
    _verdict(root, [{"op": "relabel", "band": 3, "label": "MainZone-P", "why": "a"}])
    got = applied(root)
    assert [got[i] for i in (0, 1, 3)] == [before[i] for i in (0, 1, 3)]
    assert "why" not in got[0]


# ---------------------------------------------------------------- the gate


def test_no_verdict_is_a_failure_for_a_named_page(root):
    assert rules(root) == ["missing"]


def test_a_verdict_against_an_older_file_is_stale(root):
    _verdict(root, [])
    _page(root, fused=False)                # the rule rewrites the file
    assert rules(root) == ["stale"]
    assert not zones_review.fresh(REF, root)


def test_the_band_count_is_the_witness_the_whole_file_was_read(root):
    _verdict(root, [], bands=3)
    assert rules(root) == ["band-count"]


@pytest.mark.parametrize("edit,rule", [
    ({"op": "relabel", "band": 9, "label": "MainZone-P", "why": "a"}, "band-range"),
    ({"op": "split", "line": 99, "label": "MainZone-P", "why": "a"}, "line-range"),
    ({"op": "relabel", "band": 2, "label": "MainZone-Prose", "why": "a"}, "label"),
    ({"op": "relabel", "band": 2, "label": "MainZone-Other", "why": " "}, "why"),
    ({"op": "relabel", "band": 2, "label": "MainZone-P", "why": "a"}, "no-op"),
    ({"op": "merge", "band": 1, "why": "a"}, "conflict"),
    ({"op": "split", "line": 1, "label": "MainZone-P", "why": "a"}, "conflict"),
    ({"op": "split", "line": 6, "label": "MainZone-P", "why": "a"}, "conflict"),
    ({"op": "absorb", "line": 5, "into": "above", "why": "a"}, "conflict"),
    ({"op": "absorb", "line": 6, "into": "sideways", "why": "a"}, "field"),
    ({"op": "merge", "band": 3, "label": "MainZone-P", "why": "a"}, "field"),
    ({"op": "delete", "band": 3, "why": "a"}, "op"),
])
def test_an_edit_the_file_cannot_hold_is_refused(root, edit, rule):
    _verdict(root, [edit])
    assert rules(root) == [rule]


@pytest.mark.parametrize("edits", [
    [{"op": "relabel", "band": 2, "label": "MainZone-Other", "why": "a"},
     {"op": "relabel", "band": 2, "label": "MainZone-Quote", "why": "b"}],
    [{"op": "relabel", "band": 4, "label": "MainZone-P", "why": "a"},
     {"op": "merge", "band": 4, "why": "b"}],
    [{"op": "split", "line": 3, "label": "MainZone-P", "why": "a"},
     {"op": "split", "line": 3, "label": "MainZone-Other", "why": "b"}],
    [{"op": "absorb", "line": 6, "into": "above", "why": "a"},
     {"op": "absorb", "line": 6, "into": "below", "why": "b"}],
])
def test_two_edits_that_cannot_both_hold_are_refused(root, edits):
    _verdict(root, edits)
    assert "conflict" in rules(root)


def test_an_applied_result_that_overlaps_is_refused(tmp_path):
    cfg = chukchi_zone_config()
    cfg["text_rule"] = FX_RULE
    write_zone_config(tmp_path, cfg)
    _page(tmp_path, tall=True)              # line 6 reaches 914, band 4 opens at 886
    _verdict(tmp_path, [{"op": "absorb", "line": 6, "into": "above", "why": "a"}])
    assert rules(tmp_path) == ["applied overlap"]


def test_a_note_changes_nothing_and_must_say_something(root):
    before = zones_review.baseline(REF, root)["zones"]
    _verdict(root, [], notes=[{"line": 6, "text": "a fused row; the editor rules"}])
    assert applied(root) == before
    _verdict(root, [], notes=[{"line": 6, "text": ""}])
    assert rules(root) == ["notes"]


# ---------------------------------------------------------------- dispatch


def test_the_queue_refuses_what_is_not_the_agents_to_review(root):
    assert dispatch.zoning_build(REF, root)["flags"] == "unzoned,continued"
    _verdict(root, [])
    with pytest.raises(dispatch.Unready, match="already holds a verdict"):
        dispatch.zoning_build(REF, root)
    verdict_path(REF, root).unlink()
    gt = zones.alto_for(REF, root, zones.ZONEDIR)
    gt.parent.mkdir(parents=True, exist_ok=True)
    gt.write_bytes(zones.alto_for(REF, root, zones.MZDIR).read_bytes())
    with pytest.raises(dispatch.Unready, match="a human has keyed"):
        dispatch.zoning_build(REF, root)
    gt.unlink()
    zones.alto_for(REF, root, zones.MZDIR).unlink()
    with pytest.raises(dispatch.Unready, match="no mz/zones"):
        dispatch.zoning_build(REF, root)


def test_a_ruled_leaf_is_refused(root):
    zones.set_splits({REF: "plate"}, root)
    with pytest.raises(dispatch.Unready, match="not a text page"):
        dispatch.zoning_build(REF, root)


def test_claims_are_distinct_and_reconcile_sees_who_came_back(root):
    _page(root, ref="1-003")
    dispatch.queue_refs([REF, "1-003"], root, track=dispatch.ZONING)
    a = dispatch.claim(root, dispatch.ZONING)
    b = dispatch.claim(root, dispatch.ZONING)
    assert {a["ref"], b["ref"]} == {REF, "1-003"}
    assert dispatch.claim(root, dispatch.ZONING) is None
    _verdict(root, [])
    states = {r["ref"]: r["state"] for r in dispatch.reconcile([REF, "1-003"], root,
                                                              dispatch.ZONING)}
    assert states == {REF: "reviewed", "1-003": "CLAIMED, no verdict"}


def test_queue_all_is_every_page_flagged_or_not(root):
    # Every page is reviewed (2026-11-15): a flag is a hint, not a selection.
    from harness.cli._zones import _candidates
    for k in range(3, 9):
        _page(root, ref=f"1-{k:03d}", fused=False)
    got = _candidates(SimpleNamespace(root=root))
    assert got == sorted([REF] + [f"1-{k:03d}" for k in range(3, 9)])


# ---------------------------------------------------------------- the editor


def test_the_llm_view_applies_a_fresh_verdict_and_saves_no_reason(root):
    from harness.zones_config import load_config
    cfg = load_config(root)
    _verdict(root, [{"op": "relabel", "band": 3, "label": "MainZone-P", "why": "a"}])
    st = ui.page_state(REF, root, cfg)
    assert (st["store"], st["shown"], st["proposal"]) == ("llm", "llm", "llm")
    assert [z.get("why") for z in st["zones"]][2] == ["a"]
    assert st["llm_edits"][0]["why"] == "a" and not st["llm_stale"]
    ui.save_payload({"ref": REF, "split": "train", "exempt": [], "zones": st["zones"]},
                    root, cfg)
    saved = zones.alto_for(REF, root, zones.ZONEDIR).read_text(encoding="utf-8")
    assert "why" not in saved
    assert [z["label"] for z in zones.read_zones(REF, root)][2] == "MainZone-P"


def test_a_stale_verdict_is_reported_and_never_applied(root):
    from harness.zones_config import load_config
    cfg = load_config(root)
    _verdict(root, [{"op": "relabel", "band": 3, "label": "MainZone-P", "why": "a"}])
    _page(root, fused=False)
    st = ui.page_state(REF, root, cfg)
    assert st["store"] == "mz" and st["llm_stale"]
    pinned = ui.page_state(REF, root, cfg, store="llm")
    assert pinned["shown"] == "" and pinned["zones"] == []
