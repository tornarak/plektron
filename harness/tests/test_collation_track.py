"""The collation track: the same queue machinery, a different pass at the far end.

`Track` exists so the second dispatched pass could reuse the `O_CREAT|O_EXCL` claim
rather than grow a second copy of it — the locking is the part it would be worst to
have two of, since a bug in it shows up as a page dealt twice and nothing says so
until a batch comes back wrong.

What the two tracks do **not** share is the refusal set, and that is the whole of the
design. Reading refuses a page that already has ground truth because a reader sent at
one stops being an independent witness. Collation refuses a page that already has TEI
for a plainer reason: it would overwrite committed work. And an uncollated predecessor
is pointedly not a refusal here — it was an implicit one while the pass ran serially,
because `tei seam` refuses without one, and moving the seam to the coordinator is what
lets a batch be dispatched in any order at all.

**Ground truth used to be an input and is now a precondition**, and the reversal is
this file's other subject. The old rule took a draft from either store on the
reasoning that a machine reading is workable and an adjudicated one merely better;
what that bought was a pass whose input rank varied per page and a contract with a
long section defending against exactly that. Collation now reviews a page *generated*
from adjudicated text, so there is no lower-ranked draft left for the rule to admit,
and the ambiguity is deleted rather than documented.

That moves two things into the dispatcher that used to be nobody's: the baseline is
built at queue time, and `claim` puts the working copy where the agent may write it.
The second is why `reconcile` grew a fourth state — once claiming creates the
deliverable, the deliverable's existence stops meaning the agent came back.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_scan

from harness.dispatch import (
    COLLATE_DOC,
    COLLATION,
    READING,
    Unready,
    claim,
    claim_one,
    collate_survey,
    queue_path,
    queue_refs,
    reconcile,
)
from harness.zones import save_zones

REPO = Path(__file__).resolve().parent.parent.parent
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
ALTO = (f'<alto xmlns="{ALTO_NS}"><Layout>'
        '<Page WIDTH="2824" HEIGHT="3897"><PrintSpace>'
        '<TextBlock ID="b1" HPOS="307" VPOS="200" WIDTH="1700" HEIGHT="45" '
        'TAGREFS="T1">'
        '<TextLine ID="l1" HPOS="307" VPOS="200" WIDTH="1700" HEIGHT="45">'
        '<String CONTENT="hi"/></TextLine></TextBlock>'
        "</PrintSpace></Page></Layout>"
        f'<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags></alto>')


def make_page(root: Path, ref="1-075", *, gt=True, zones=True, tei=False,
              exempt=False) -> Path:
    """The smallest tree `collate_survey` reads, and `queue` can generate from.

    `gt` and `zones` both default on because both are now preconditions: the tests
    that matter turn one off and name what it costs.
    """
    write_scan(root, ref)
    if gt:
        d = root / "gt/ocr"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"chukchi-{ref}.xml").write_text(ALTO, encoding="utf-8")
    if zones:
        save_zones(ref, [{"id": "z1", "label": "MainZone-P", "x0": 307,
                          "y0": 200, "x1": 2085, "y1": 245}], root)
    d = root / "tei"
    d.mkdir(parents=True, exist_ok=True)
    if tei:
        (d / f"chukchi-{ref}.xml").write_text("<TEI/>", encoding="utf-8")
    lst = root / "gt/zones/_plate.lst"
    lst.parent.mkdir(parents=True, exist_ok=True)
    lst.write_text(f"chukchi-{ref}.xml\n" if exempt else "", encoding="utf-8")
    doc = root / COLLATE_DOC
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text((REPO / COLLATE_DOC).read_text(encoding="utf-8"),
                   encoding="utf-8")
    agent = root / COLLATION.agent
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text("stub\n", encoding="utf-8")
    return root


def test_the_two_tracks_do_not_share_a_queue(tmp_path):
    """The sharpest thing that could go wrong with one queue serving two passes: a
    collator claiming a page off the reading batch, or the reverse. Different files,
    so it cannot happen by any race."""
    assert queue_path(tmp_path, READING) != queue_path(tmp_path, COLLATION)
    assert COLLATION.queue.parts[0] == "tei"
    assert READING.queue.parts[0] == "review"


def test_a_collated_page_is_refused(tmp_path):
    """Not the reading pass's independence argument — a plainer one. It would
    overwrite committed work, and the pass's own self-check, re-read your output once
    against the image, would read the previous run's file as this run's."""
    make_page(tmp_path, tei=True)
    with pytest.raises(Unready, match="already exists"):
        queue_refs(["1-075"], tmp_path, track=COLLATION)


def test_ground_truth_is_a_precondition_and_not_merely_a_better_input(tmp_path):
    """The reversal, pinned. This rule used to be the inverse — either store would
    do, and `gt/` was the better one — which left the pass unable to tell, per page,
    whether it was reading adjudicated text or a recognizer at 0% on the inventory.
    The refusal names the loop that fixes it rather than the file that is missing."""
    make_page(tmp_path, gt=False)
    assert collate_survey("1-075", tmp_path)["gt"] is False
    with pytest.raises(Unready, match="rebuild-groundtruth"):
        queue_refs(["1-075"], tmp_path, track=COLLATION)


def test_keyed_zones_are_a_precondition_too(tmp_path):
    """Ground truth alone is not readiness: the paragraph boundaries *are* the keyed
    zone labels, so a page with adjudicated text and no human zoning has no structure
    to generate from. `mz/zones/` is a prediction, which is not an assertion."""
    make_page(tmp_path, zones=False)
    with pytest.raises(Unready, match="zones edit"):
        queue_refs(["1-075"], tmp_path, track=COLLATION)


def test_queue_builds_the_baseline_it_is_about_to_deal_out(tmp_path):
    """Generation is deterministic and wants no GPU, so making the coordinator run it
    separately would only create a way to forget it — and a batch queued without
    baselines fails one page at a time, in front of agents that cannot fix it."""
    make_page(tmp_path)
    assert collate_survey("1-075", tmp_path)["baseline"] is False
    queue_refs(["1-075"], tmp_path, track=COLLATION)
    assert collate_survey("1-075", tmp_path)["baseline"] is True


def test_an_uncollated_predecessor_is_not_a_refusal(tmp_path):
    """The change that makes a dispatched batch possible. Nothing precedes 1-075 in
    this root, and it queues anyway: the seam is the coordinator's now, so the batch
    need not be contiguous or ordered."""
    make_page(tmp_path)
    assert not (tmp_path / "tei" / "chukchi-1-074.xml").exists()
    assert queue_refs(["1-075"], tmp_path, track=COLLATION)["queued"] == ["1-075"]


def test_a_leaf_ruled_not_a_text_page_is_refused(tmp_path):
    make_page(tmp_path, exempt=True)
    with pytest.raises(Unready, match="not a text page"):
        queue_refs(["1-075"], tmp_path, track=COLLATION)


def test_a_ref_named_twice_is_refused(tmp_path):
    make_page(tmp_path)
    with pytest.raises(Unready, match="named twice"):
        queue_refs(["1-075", "1-075"], tmp_path, track=COLLATION)


def test_a_missing_agent_refuses_the_batch(tmp_path, monkeypatch):
    """The agent body *is* the system prompt, so a batch dispatched without one sends
    agents at pages with no rules and nothing would say so until the output came back
    wrong. `agents sync` reports this state; `queue` is where it bites, because that
    is the call about to spend agents on it."""
    make_page(tmp_path)
    (tmp_path / COLLATION.agent).unlink()
    monkeypatch.setattr("harness.dispatch.repo_root", lambda: tmp_path)
    with pytest.raises(Unready, match="whole contract"):
        queue_refs(["1-075"], tmp_path, track=COLLATION)


def test_the_claim_is_atomic_across_the_collation_queue(tmp_path):
    """The property the shared machinery exists to keep. Eight claimers, three refs,
    three distinct answers and no page dealt twice."""
    for ref in ("1-075", "1-076", "1-077"):
        make_page(tmp_path, ref)
    queue_refs(["1-075", "1-076", "1-077"], tmp_path, track=COLLATION)
    got = [claim_one(tmp_path, COLLATION) for _ in range(8)]
    taken = [t[0] for t in got if t is not None]
    assert sorted(taken) == ["1-075", "1-076", "1-077"]
    assert got[3:] == [None] * 5


def test_claiming_puts_the_working_copy_in_place(tmp_path):
    """**The copy is the harness's, not the agent's.** A collator's Bash surface is an
    allowlist with no `cp` in it — a copy it could perform is one it could perform in
    the wrong direction, back over the baseline that is the other half of `tei diff`.
    Copying here also means review starts from the generated bytes exactly, which is
    what makes that diff a record of judgement rather than of transcription."""
    make_page(tmp_path)
    queue_refs(["1-075"], tmp_path, track=COLLATION)
    block = claim(tmp_path, COLLATION)
    assert block["ref"] == "1-075"
    assert "**1-075**" in block["page_block"]
    working = tmp_path / "tei" / "chukchi-1-075.xml"
    assert block["working_file"] == str(working)
    assert working.read_bytes() == (tmp_path / "mz/tei/chukchi-1-075.xml").read_bytes()
    # `placeholders` is what the *template* declares, a diagnostic for whoever edits
    # the doc — so the check that substitution happened is that the rendered block
    # carries no brace left, not that the list is empty.
    assert "{" not in block["page_block"]


def test_the_store_is_no_longer_named_in_the_page_block(tmp_path):
    """`ocr_store` said `gt` or `mz` because either could arrive. With `mz` refused
    outright the word carried no information, and a constant in a prompt is a line
    every sibling pays for on every page to be told what the gate already guarantees."""
    make_page(tmp_path)
    queue_refs(["1-075"], tmp_path, track=COLLATION)
    block = claim(tmp_path, COLLATION)
    assert "ocr_store" not in block["placeholders"]
    assert "mz" not in block["page_block"]


def test_reconcile_keeps_each_track_s_own_words(tmp_path):
    """Deriving the state strings from the track name would have renamed the reading
    pass's report as a side effect of this pass existing — a documented surface broken
    for nothing."""
    make_page(tmp_path)
    make_page(tmp_path, "1-076")
    queue_refs(["1-075", "1-076"], tmp_path, track=COLLATION)
    claim_one(tmp_path, COLLATION)
    (tmp_path / "tei" / "chukchi-1-075.xml").write_text("<TEI/>", encoding="utf-8")
    states = {r["ref"]: r["state"] for r in
              reconcile(["1-075", "1-076"], tmp_path, COLLATION)}
    assert states == {"1-075": "collated", "1-076": "unclaimed"}
    assert READING.missing == "CLAIMED, no proposal"


def test_an_untouched_copy_does_not_read_as_a_collated_page(tmp_path):
    """The fourth state, and the reason it had to exist. `claim` now creates the
    deliverable, so its presence stopped meaning the agent came back: a collator that
    died on its first turn leaves a file that a presence check reports as finished
    work. Byte equality against the baseline is the honest test, and no real page
    survives it — every one arrives with a lang-less wrap, an unresolved zone or a
    missing `opens:` still to clear."""
    make_page(tmp_path)
    queue_refs(["1-075"], tmp_path, track=COLLATION)
    claim(tmp_path, COLLATION)
    assert reconcile(["1-075"], tmp_path, COLLATION)[0]["state"] == "CLAIMED, unedited"
    p = tmp_path / "tei" / "chukchi-1-075.xml"
    p.write_text(p.read_text(encoding="utf-8").replace("<pb", "<!-- read -->\n<pb"),
                 encoding="utf-8")
    assert reconcile(["1-075"], tmp_path, COLLATION)[0]["state"] == "collated"
