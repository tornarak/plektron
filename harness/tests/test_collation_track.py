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
"""

from __future__ import annotations

from pathlib import Path

import pytest

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

REPO = Path(__file__).resolve().parent.parent.parent
ALTO = ('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout>'
        '<Page WIDTH="2550" HEIGHT="3525"><PrintSpace><TextBlock ID="b1">'
        '<TextLine ID="l1" HPOS="10" VPOS="10" WIDTH="100" HEIGHT="20">'
        '<String CONTENT="hi"/></TextLine></TextBlock>'
        "</PrintSpace></Page></Layout></alto>")


def make_page(root: Path, ref="1-075", *, ocr=True, gt=False, tei=False,
              exempt=False) -> Path:
    """The smallest tree `collate_survey` reads."""
    for store, on in (("ocr", ocr), ("gt/ocr", gt), ("tei", tei)):
        d = root / store
        d.mkdir(parents=True, exist_ok=True)
        if on:
            (d / f"chukchi-{ref}.xml").write_text(ALTO, encoding="utf-8")
    lst = root / "gt/zones/_exempt.lst"
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


def test_ground_truth_is_an_input_here_not_a_disqualification(tmp_path):
    """The inverse of the reading pass's rule, and worth pinning because the two
    stores are the same two. `gt/ocr` means the Tier-1 forms are ratified and
    `tei expand` can write them in, so it is the *better* input."""
    make_page(tmp_path, gt=True)
    assert collate_survey("1-075", tmp_path)["gt"] is True
    assert queue_refs(["1-075"], tmp_path, track=COLLATION)["queued"] == ["1-075"]


def test_an_uncollated_predecessor_is_not_a_refusal(tmp_path):
    """The change that makes a dispatched batch possible. Nothing precedes 1-075 in
    this root, and it queues anyway: the seam is the coordinator's now, so the batch
    need not be contiguous or ordered."""
    make_page(tmp_path)
    assert not (tmp_path / "tei" / "chukchi-1-074.xml").exists()
    assert queue_refs(["1-075"], tmp_path, track=COLLATION)["queued"] == ["1-075"]


def test_a_page_with_no_draft_is_refused_naming_predict(tmp_path):
    make_page(tmp_path, ocr=False)
    with pytest.raises(Unready, match="ocr predict"):
        queue_refs(["1-075"], tmp_path, track=COLLATION)


def test_an_exempt_page_is_refused(tmp_path):
    make_page(tmp_path, exempt=True)
    with pytest.raises(Unready, match="exempt"):
        queue_refs(["1-075"], tmp_path, track=COLLATION)


def test_a_ref_named_twice_is_refused(tmp_path):
    make_page(tmp_path)
    with pytest.raises(Unready, match="named twice"):
        queue_refs(["1-075", "1-075"], tmp_path, track=COLLATION)


def test_a_missing_agent_refuses_the_batch(tmp_path):
    """The agent body *is* the system prompt, so a batch dispatched without one sends
    agents at pages with no rules and nothing would say so until the output came back
    wrong. `agents sync` reports this state; `queue` is where it bites, because that
    is the call about to spend agents on it."""
    make_page(tmp_path)
    (tmp_path / COLLATION.agent).unlink()
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


def test_the_claim_block_names_the_rank_of_its_own_input(tmp_path):
    """`ocr: gt` is the licence to name a handle rather than key a form, and `mz` is
    notice that the inventory is 0% right. The block says which in a word, because it
    is the first thing the collator reads."""
    make_page(tmp_path, gt=True)
    queue_refs(["1-075"], tmp_path, track=COLLATION)
    block = claim(tmp_path, COLLATION)
    assert block["ref"] == "1-075"
    assert "**1-075**" in block["page_block"]
    assert "from the **gt** store" in block["page_block"]
    # `placeholders` is what the *template* declares, a diagnostic for whoever edits
    # the doc — so the check that substitution happened is that the rendered block
    # carries no brace left, not that the list is empty.
    assert block["placeholders"] == "note ocr_store ref"
    assert "{" not in block["page_block"]


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
