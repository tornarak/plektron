"""The lifecycle census — `harness corpus state`, and `page_state` in the context.

Each store's own verb reported its own presence honestly and was blind to the
rest, so "which pages are ready to collate" and "which are half-way through the
reading loop" had no command behind them. This joins them on one ladder.

The tests that matter here are about `skipped`, not about `stage`. `stage` is a
summary and a summary that can hide the anomaly it summarises is this project's
standing failure shape — `2-030` reached `gt/ocr/` by a route the pipeline no
longer offers, and for a long time nothing could see that.
"""
from __future__ import annotations

from pathlib import Path

from harness.pipeline import STAGES, page_state, survey, tally


def touch(root: Path, rel: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    return p


def scanned(root: Path, ref: str = "1-151") -> None:
    touch(root, f"scans/chukchi-{ref}.png")


# --------------------------------------------------------------- the ladder

def test_a_page_nothing_holds_is_absent_not_blank(tmp_path):
    """`absent` is a stage rather than an omission, which is why `--all`
    enumerates `scans/` and not any store: a page no store holds is the most
    interesting row this verb has."""
    row = page_state("1-151", tmp_path)
    assert row["stage"] == "absent"
    assert row["scan"] is False


def test_the_stage_is_the_furthest_rung_reached(tmp_path):
    scanned(tmp_path)
    assert page_state("1-151", tmp_path)["stage"] == "scanned"
    touch(tmp_path, "mz/zones/chukchi-1-151.xml")
    assert page_state("1-151", tmp_path)["stage"] == "zoned-mz"
    touch(tmp_path, "gt/zones/chukchi-1-151.xml")
    assert page_state("1-151", tmp_path)["stage"] == "zoned-gt"
    touch(tmp_path, "mz/ocr/chukchi-1-151.xml")
    assert page_state("1-151", tmp_path)["stage"] == "ocr-mz"
    touch(tmp_path, "review/1-151/proposal.json")
    assert page_state("1-151", tmp_path)["stage"] == "proposed"
    touch(tmp_path, "review/1-151/decision.json")
    assert page_state("1-151", tmp_path)["stage"] == "decided"
    touch(tmp_path, "gt/ocr/chukchi-1-151.xml")
    assert page_state("1-151", tmp_path)["stage"] == "ocr-gt"
    touch(tmp_path, "tei/chukchi-1-151.xml")
    assert page_state("1-151", tmp_path)["stage"] == "collated"


def test_a_full_run_skips_nothing(tmp_path):
    scanned(tmp_path)
    for rel in ("mz/zones/chukchi-1-151.xml", "gt/zones/chukchi-1-151.xml",
                "mz/ocr/chukchi-1-151.xml", "review/1-151/proposal.json",
                "review/1-151/decision.json", "gt/ocr/chukchi-1-151.xml",
                "tei/chukchi-1-151.xml"):
        touch(tmp_path, rel)
    assert page_state("1-151", tmp_path)["skipped"] == ""


# ------------------------------------------------- the rungs that were missed

def test_a_page_that_took_a_retired_route_says_so(tmp_path):
    """`2-030`, reduced: ground truth reached through eScriptorium before the
    review loop existed, so it holds `gt/ocr/` with no prediction and no
    proposal behind it. The summary alone would read `ocr-gt` and say nothing."""
    scanned(tmp_path, "2-030")
    touch(tmp_path, "gt/zones/chukchi-2-030.xml")
    touch(tmp_path, "gt/ocr/chukchi-2-030.xml")
    row = page_state("2-030", tmp_path)
    assert row["stage"] == "ocr-gt"
    assert row["skipped"] == "zoned-mz,ocr-mz,proposed,decided"


def test_only_rungs_below_the_one_reached_count_as_skipped(tmp_path):
    """Everything above the furthest rung is *not yet done*, which is the
    ordinary state of every page in the corpus and not a finding."""
    scanned(tmp_path)
    touch(tmp_path, "mz/zones/chukchi-1-151.xml")
    row = page_state("1-151", tmp_path)
    assert row["stage"] == "zoned-mz"
    assert row["skipped"] == ""


# ----------------------------------------------------------- exempt, and zones

def test_an_exempt_page_has_been_through_the_zoning(tmp_path):
    """`exempt` is a human ruling that this is not a text page, which satisfies
    the rung — the rung asks whether a human has been through it, and "this is a
    plate" is a judgement rather than the absence of one. It is also why the
    column carries `exempt` rather than falling back to `mz` or to blank."""
    scanned(tmp_path, "1-001")
    (tmp_path / "gt" / "zones").mkdir(parents=True)
    (tmp_path / "gt" / "zones" / "_exempt.lst").write_text(
        "chukchi-1-001.png\n", encoding="utf-8")
    row = page_state("1-001", tmp_path)
    assert row["zones"] == "exempt"
    assert row["stage"] == "zoned-gt"


def test_the_ocr_column_reports_gt_over_mz(tmp_path):
    """Same precedence the `ocr/` view resolves by — but both rungs still count,
    since the ladder is about what has happened and not about what is read."""
    scanned(tmp_path)
    touch(tmp_path, "mz/ocr/chukchi-1-151.xml")
    touch(tmp_path, "gt/ocr/chukchi-1-151.xml")
    row = page_state("1-151", tmp_path)
    assert row["ocr"] == "gt"
    assert "ocr-mz" not in row["skipped"]


# ----------------------------------------------------------------- the tally

def test_every_rung_is_listed_even_at_zero(tmp_path):
    """A rung nothing has reached and one everything has passed are different
    facts, and omitting the row makes them look the same."""
    scanned(tmp_path)
    rows = tally(survey(["1-151"], tmp_path))
    assert [r["stage"] for r in rows] == ["absent", *STAGES, "(any skipped rung)"]
    assert {r["stage"]: r["pages"] for r in rows}["scanned"] == 1


def test_the_survey_reads_the_split_lists_once(tmp_path):
    """`survey` exists for this: `page_state` alone would reload the three lists
    per page, and the census walks 832 of them."""
    scanned(tmp_path, "1-001")
    scanned(tmp_path, "1-002")
    assert [r["ref"] for r in survey(["1-002", "1-001"], tmp_path)] == \
        ["1-002", "1-001"]


# ------------------------------------------------- the same row in the payload

def test_the_context_carries_the_page_state(tmp_path):
    """So a collation pass is never left inferring the rank of its own input:
    an empty `tier1_terms` means "no ground truth" on 802 pages and "ground
    truth with no marked forms" on `3-063`, and those call for opposite work."""
    from harness.context import build_context

    scanned(tmp_path)
    alto = ('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout>'
            '<Page><PrintSpace><TextBlock ID="b1"><TextLine ID="l1">'
            '<String CONTENT="ordinary prose"/></TextLine></TextBlock>'
            "</PrintSpace></Page></Layout></alto>")
    for rel in ("ocr/chukchi-1-151.xml", "mz/ocr/chukchi-1-151.xml"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(alto, encoding="utf-8")

    state = build_context("1-151", tmp_path)["page_state"]
    assert state["ocr"] == "mz"
    assert state["stage"] == "ocr-mz"
    assert "ref" not in state          # `page_ref` already says which page
