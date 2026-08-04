"""How far a human's ruling went beyond the prediction it started from.

`page_departure` and `_independent` have been here since the eval set was drawn —
`--remark-eval` selects on them — and **nothing reported them afterwards**. So
"this held-out page is the model's own segmentation with the edges pulled
straight" was knowable once, at selection time, and invisible at every reading of
a score since. A qualifier that outlives its number by exactly one command is the
same shape as a provenance rank nothing re-checks.

These tests are about the two ways such a report goes wrong: a kind it can never
emit, and a kind that emits so often it buries the one that matters.
"""
from __future__ import annotations

from pathlib import Path

from harness import zones as zn

ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Tags><OtherTag ID="BT1" LABEL="{label}"/></Tags>
  <Layout><Page WIDTH="2824" HEIGHT="3897"><PrintSpace>
    <TextBlock ID="b1" HPOS="700" VPOS="{y0}" WIDTH="1778" HEIGHT="{h}"
               TAGREFS="BT1">
      <Shape><Polygon POINTS="700 {y0} 2478 {y0} 2478 {y1} 700 {y1}"/></Shape>
    </TextBlock>
  </PrintSpace></Page></Layout>
</alto>
"""


def write_page(root: Path, ref: str, store: str, *, y0=600, y1=900,
               label="MainZone-P") -> None:
    d = root / store
    d.mkdir(parents=True, exist_ok=True)
    (d / f"chukchi-{ref}.xml").write_text(
        ALTO.format(label=label, y0=y0, y1=y1, h=y1 - y0), encoding="utf-8")


def mark(root: Path, ref: str, split: str) -> None:
    d = root / zn.ZONEDIR
    d.mkdir(parents=True, exist_ok=True)
    lst = {"train": zn.TRAIN_LST, "eval": zn.EVAL_LST,
           "exempt": zn.EXEMPT_LST}[split]
    with (d / lst).open("a", encoding="utf-8") as fh:
        fh.write(f"chukchi-{ref}.png\n")


# ------------------------------------------------------------- the five kinds

def test_a_ratified_prediction_is_the_weakest_claim(tmp_path):
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    write_page(tmp_path, "1-048", zn.MZDIR)
    row = zn.departures(["1-048"], tmp_path)[0]
    assert row["kind"] == "identical"
    assert row["shift_px"] == 0
    assert row["independent"] is False


def test_a_nudge_is_not_a_judgement(tmp_path):
    """The distinction the criterion exists to draw. A held-out set made of
    pages whose edges were pulled straight measures how well the model agrees
    with itself."""
    write_page(tmp_path, "1-048", zn.ZONEDIR, y0=600 + zn.NUDGE_PX - 5)
    write_page(tmp_path, "1-048", zn.MZDIR)
    row = zn.departures(["1-048"], tmp_path)[0]
    assert row["kind"] == "geometry only"
    assert row["independent"] is False


def test_a_real_boundary_correction_is(tmp_path):
    write_page(tmp_path, "1-048", zn.ZONEDIR, y0=600 + zn.NUDGE_PX + 5)
    write_page(tmp_path, "1-048", zn.MZDIR)
    assert zn.departures(["1-048"], tmp_path)[0]["independent"] is True


def test_a_structural_difference_reports_no_distance(tmp_path):
    """A page whose zone count or labelling differs has no per-edge
    correspondence to measure, and `page_departure` returns a sentinel there.
    Publishing it would put 10**9 in a column of pixel values."""
    write_page(tmp_path, "1-048", zn.ZONEDIR, label="RunningTitleZone")
    write_page(tmp_path, "1-048", zn.MZDIR, label="MainZone-P")
    row = zn.departures(["1-048"], tmp_path)[0]
    assert row["kind"] == "a label differs"
    assert row["shift_px"] is None
    assert row["independent"] is True


def test_no_prediction_is_the_strongest_and_must_be_reachable(tmp_path):
    """The kind a report scoped to the *intersection* of the two stores can
    never emit — a column advertising coverage it does not have, which is the
    trap `LOOKALIKES` paid for once with U+0121. It is also what a freshly
    scanned volume gives for free, so it is the kind that matters next."""
    write_page(tmp_path, "1-359", zn.ZONEDIR)
    row = zn.departures(["1-359"], tmp_path)[0]
    assert row["kind"] == "no prediction"
    assert row["independent"] is True


# ------------------------------------------------- the kind that would bury it

def test_a_plate_is_off_the_scale_not_at_the_end_of_it(tmp_path):
    """An exempt page has no correct segmentation — `score` excludes them for
    that reason — so it has nothing to have departed *from*. Left to fall
    through, its empty file against an absent prediction reads as `no
    prediction`, the table's strongest claim: 83 plates, and `1-359` invisible
    among them. Kept as a row rather than dropped, because a silent exclusion is
    how a shrinking denominator reads as a result."""
    (tmp_path / zn.ZONEDIR).mkdir(parents=True)
    (tmp_path / zn.ZONEDIR / "chukchi-1-001.xml").write_text(
        ALTO.format(label="MainZone-P", y0=0, y1=0, h=0)
            .replace("<TextBlock", "<!--").replace("</TextBlock>", "-->"),
        encoding="utf-8")
    mark(tmp_path, "1-001", "exempt")
    write_page(tmp_path, "1-359", zn.ZONEDIR)

    rows = {r["ref"]: r for r in zn.departures(["1-001", "1-359"], tmp_path)}
    assert rows["1-001"]["kind"] == "exempt"
    assert rows["1-001"]["independent"] is False
    assert rows["1-359"]["kind"] == "no prediction"


# --------------------------------------------------------------- the roll-up

def test_the_composition_is_what_belongs_beside_a_recall_figure(tmp_path):
    """A held-out set half of which is the model's own segmentation measures how
    well the model agrees with itself, and the number alone cannot say so."""
    for i, (y0, split) in enumerate(
            ((600, "eval"), (600, "eval"), (600 + zn.NUDGE_PX + 5, "eval")), 1):
        ref = f"1-{i:03d}"
        write_page(tmp_path, ref, zn.ZONEDIR, y0=y0)
        write_page(tmp_path, ref, zn.MZDIR)
        mark(tmp_path, ref, split)

    comp = zn.departure_composition(
        zn.departures(["1-001", "1-002", "1-003"], tmp_path))
    assert len(comp) == 1
    row = comp[0]
    assert row["split"] == "eval" and row["pages"] == 3
    assert row["identical"] == 2 and row["geometry_only"] == 1
    assert row["independent"] == 1
    assert row["nudge_px"] == zn.NUDGE_PX


def test_every_kind_gets_a_column_even_at_zero(tmp_path):
    """Same reason `corpus state --tally` lists every rung: a kind nothing
    reached and a kind everything passed are different facts."""
    write_page(tmp_path, "1-048", zn.ZONEDIR)
    write_page(tmp_path, "1-048", zn.MZDIR)
    row = zn.departure_composition(zn.departures(["1-048"], tmp_path))[0]
    for _kind, field in zn.DEPARTURE_KINDS:
        assert field in row
