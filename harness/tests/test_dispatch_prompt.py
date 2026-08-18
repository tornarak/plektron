"""The two dispatch texts are rendered from `dispatch.md`, never transcribed.

Hand-copying the template put five clauses into a prompt an agent actually ran that
existed nowhere in the doc. The doc then described a prompt nobody sent, the run
measured something unwritten, and anyone debugging the result afterwards would have
been reading the wrong text. Same fault as writing a glyph into a note instead of
citing its codepoint — a normative thing reproduced probabilistically, with nothing
to witness the difference.

Two things are worth pinning. The template must stay locatable and fully
substituted, since a stray `{placeholder}` reaching an agent is a literal brace in
an instruction and a `KeyError` is the good outcome. And the refusals must fire,
because they are `dispatch.md`'s four-store survey made mechanical — the check a
coordinator performs by eye and therefore the one that gets skipped.

Fixtures are built in `tmp_path` rather than read off the live corpus, per this
suite's rule, except where a test is explicitly about the repo's own `dispatch.md`.
"""

import re
from pathlib import Path

import pytest

from harness.dispatch import (
    AGENT,
    BEGIN,
    CLAIM_BEGIN,
    CLAIM_END,
    DOC,
    END,
    Unready,
    build,
    claim,
    claim_one,
    collate_survey,
    queue_refs,
    reconcile,
    survey,
    template,
)

REPO = Path(__file__).resolve().parent.parent.parent


def make_page(root: Path, ref="3-063", *, zones=True, mz=True, gt=False,
              figs=False, exempt=False):
    """The smallest tree `survey` reads: four stores and the exempt list."""
    alto = ('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout>'
            '<Page WIDTH="2550" HEIGHT="3525"><PrintSpace>'
            '<TextBlock ID="b1"><TextLine ID="l1" HPOS="10" VPOS="10" '
            'WIDTH="100" HEIGHT="20"><String CONTENT="hi"/></TextLine></TextBlock>'
            '</PrintSpace></Page></Layout></alto>')
    for store, on in (("gt/zones", zones), ("mz/ocr", mz),
                      ("gt/ocr", gt), ("gt/fig", figs)):
        d = root / store
        d.mkdir(parents=True, exist_ok=True)
        if on:
            (d / f"chukchi-{ref}.xml").write_text(alto, encoding="utf-8")
    lst = root / "gt/zones/_plate.lst"
    lst.write_text(f"chukchi-{ref}.xml\n" if exempt else "", encoding="utf-8")
    doc = root / DOC
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text((REPO / DOC).read_text(encoding="utf-8"), encoding="utf-8")
    # A stub agent, because `queue` refuses a root that has none: the agent body *is*
    # the system prompt, so dispatching without one sends readers at pages with no
    # rules. It carries no transclusion markers, which is the point — this fixture is
    # about the queue, and `test_transclusion.py` is about the contract.
    agent = root / AGENT
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text("stub\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("markers,floor", [
    ((BEGIN, END), 400),
    ((CLAIM_BEGIN, CLAIM_END), 40),
])
def test_the_repo_templates_are_locatable_and_nonempty(markers, floor):
    """Against the live doc: the markers are load-bearing and easy to lose.

    The page block's floor was 2000 while it carried the standing instructions
    too. Those moved to `.claude/agents/groundtruth-reader.md`, so it is now the
    page-specific half alone — the ref, the survey, the figures clause — and a
    bound tuned to the old size would fail on the split rather than on a lost
    block. Both are not-empty checks, set well under the real length.
    """
    lines = (REPO / DOC).read_text(encoding="utf-8").splitlines()
    begin, end = markers
    assert lines.count(begin) == 1 and lines.count(end) == 1
    assert lines.index(begin) < lines.index(end)
    assert len(template(REPO, markers)) > floor


def test_the_prompt_every_reader_gets_names_no_page():
    """The property the whole dispatch is built on, asserted against the live doc.

    Three readers dispatched with `moll-043`/`044`/`045` in their prompts all
    opened COLD at the same total — the totals matching because three refs of the
    same byte length cost the same. Byte-identical prompts shared. So identity of
    turn 1 is what caches, and ANYTHING varying in it costs every sibling the
    whole shared context: a `{brace}` here is not a formatting slip, it is the
    saving.
    """
    prompt = template(REPO, (CLAIM_BEGIN, CLAIM_END))
    assert "{" not in prompt and "}" not in prompt
    assert not re.search(r"\b\d-\d{3}\b", prompt), "a ref in the fixed prompt"
    assert "PP-NNN" not in prompt
    # It must still name the agent type, which is the only witness a task has to
    # how it was spawned: a reader dispatched as the wrong type has no body, so
    # the assertion cannot live there.
    assert "groundtruth-reader" in prompt


def test_every_placeholder_the_template_uses_is_supplied(tmp_path):
    """A `{brace}` left in a prompt is a literal brace in an instruction.

    `str.format` raises `KeyError` on an unsupplied name, so this fails loudly if
    someone adds a placeholder to the doc without teaching `build` about it — which
    is the whole point of keeping the prose in the doc.
    """
    rec = build("3-063", make_page(tmp_path))
    assert "{" not in rec["page_block"] and "}" not in rec["page_block"]


def test_the_survey_is_substituted_not_described(tmp_path):
    rec = build("3-063", make_page(tmp_path))
    assert "**3-063**" in rec["page_block"]
    assert "PP-NNN" not in rec["page_block"]
    assert f"{rec['lines']} lines over {rec['blocks']} zones" in rec["page_block"]


def test_the_figure_clause_says_which_situation_the_page_is_in(tmp_path):
    """The two cases say opposite things about what a `gaps` band means.

    Told the wrong one, an agent reads artwork as a dropped line or discounts a
    real one as artwork — so this cannot be left as a word the reader interprets.
    """
    absent = build("3-063", make_page(tmp_path / "a", figs=False))["page_block"]
    present = build("3-063", make_page(tmp_path / "b", figs=True))["page_block"]
    assert "does NOT exist" in absent and "genuine dropped-line candidate" in absent
    assert "are masked out of the detector" in present
    assert "genuine dropped-line candidate" not in present


def test_a_note_lands_in_the_branch_paragraph(tmp_path):
    rec = build("3-063", make_page(tmp_path), note="Sparse page; watch the gaps.")
    assert "does not exist. Sparse page; watch the gaps." in rec["page_block"]


def test_no_note_leaves_no_dangling_space(tmp_path):
    assert "does not exist.\n" in build("3-063", make_page(tmp_path))["page_block"]


@pytest.mark.parametrize("kw,expected", [
    ({"zones": False}, "No zones, no dispatch"),
    ({"exempt": True}, "not a text page"),
    ({"gt": True}, "independent witness"),
    ({"mz": False}, "ocr predict"),
])
def test_a_page_that_is_not_a_candidate_is_refused_with_its_remedy(
        tmp_path, kw, expected):
    """Refusals, not warnings: a prompt is a thing an agent is about to be spent on.

    `gt` present is the sharp one. A reader sent at a keyed page reads the human
    text through every ALTO verb, so its proposal stops being an independent
    witness — and a named range contains such a page sooner or later.
    """
    with pytest.raises(Unready, match=expected):
        build("3-063", make_page(tmp_path, **kw))


def test_both_surveys_ask_the_split_rather_than_the_list(tmp_path):
    """The exempt refusal must not be defeated by renaming the list it reads.

    Both surveys used to test for the page's filename *inside* `_exempt.lst`, and
    that form **fails open**: the day the list is renamed or its shape changes,
    the membership test returns `False`, the refusal below stops refusing, and the
    pass dispatches agents at plates with nothing raising. Asked of the split
    through `zones.is_exempt`, a list this function does not know about is a
    `KeyError` at load rather than a silent negative.

    So the mark is made through the store's own API and never by writing a file
    this test names. That is the whole assertion: whatever file `set_split` lands
    the ruling in, both surveys follow it.

    **The rename is what makes it discriminate**, and it has happened: the ruling
    now lands in `_blank.lst`, so the old containment check against `_exempt.lst`
    would find nothing here and both refusals would silently stop refusing. Ruled
    `blank` rather than `plate` on purpose — `plate` is what the fixture's own
    `exempt=True` writes, and a test that agreed with the fixture's choice of file
    could still be passing for the wrong reason.
    """
    from harness.zones import set_split
    root = make_page(tmp_path, exempt=False)
    assert survey("3-063", root)["exempt"] is False
    assert collate_survey("3-063", root)["exempt"] is False

    set_split("3-063", "blank", root)
    assert not (root / "gt/zones/_exempt.lst").exists()
    assert survey("3-063", root)["exempt"] is True
    assert collate_survey("3-063", root)["exempt"] is True
    with pytest.raises(Unready, match="not a text page"):
        build("3-063", root)


def test_survey_reports_all_four_stores(tmp_path):
    s = survey("3-063", make_page(tmp_path, figs=True, gt=True))
    assert (s["zones"], s["figures"], s["gt"], s["mz"]) == (True, True, True, True)
    assert s["ref"] == "3-063"


def test_a_missing_doc_names_itself_rather_than_raising_a_path_error(tmp_path):
    make_page(tmp_path)
    (tmp_path / DOC).unlink()
    with pytest.raises(Unready, match="only source"):
        template(tmp_path)


def test_a_doc_without_markers_says_so(tmp_path):
    """The markers are the locator, so losing them must not fall back to a guess.

    Finding the block by heading instead would silently pick up whatever prose
    followed `## Template`, which is how a doc edit becomes a prompt edit nobody
    intended.
    """
    make_page(tmp_path)
    (tmp_path / DOC).write_text("# no markers here\n", encoding="utf-8")
    with pytest.raises(Unready, match="prompt:begin"):
        template(tmp_path)


def test_a_marker_inside_a_sentence_is_not_a_marker(tmp_path):
    """A marker counts only on a line of its own, and this is why.

    The doc explains its own delimiters, so a substring search finds the prose
    *describing* a template before the template — which, the first time a second
    marker pair was added, printed that paragraph to a coordinator as though it
    were a reader's instructions.
    """
    make_page(tmp_path)
    (tmp_path / DOC).write_text(
        f"Prose mentioning {BEGIN} mid-sentence, which is not a marker.\n"
        f"\n{BEGIN}\n\n    the real block\n\n{END}\n", encoding="utf-8")
    assert template(tmp_path) == "the real block"


# --- queue, claim, reconcile ------------------------------------------------

def _queued(root, *refs, note=None):
    for r in refs:
        make_page(root, r)
    return queue_refs(list(refs), root, note=note)


def test_queue_returns_the_fixed_prompt_and_writes_the_batch(tmp_path):
    rec = _queued(tmp_path, "3-063", "3-064")
    assert rec["queued"] == ["3-063", "3-064"]
    assert rec["prompt"] == template(tmp_path, (CLAIM_BEGIN, CLAIM_END))
    assert (tmp_path / "review/_queue.txt").read_text() == "3-063\n3-064\n"


def test_a_ref_named_twice_is_refused(tmp_path):
    """One page and two readers: they overwrite each other's proposal and the
    batch comes back short with nothing able to say which page went missing."""
    make_page(tmp_path, "3-063")
    with pytest.raises(Unready, match="named twice"):
        queue_refs(["3-063", "3-63"], tmp_path)


def test_queue_refuses_the_whole_batch_on_one_bad_page(tmp_path):
    """Rendered and discarded, before anything is written. A page whose survey
    raises must fail while the fix is still a command, not in front of a reader
    that has no way to act on it."""
    make_page(tmp_path, "3-063")
    make_page(tmp_path, "3-064", mz=False)
    with pytest.raises(Unready, match="ocr predict"):
        queue_refs(["3-063", "3-064"], tmp_path)
    assert not (tmp_path / "review/_queue.txt").exists()


def test_claim_takes_each_ref_once_then_runs_out(tmp_path):
    _queued(tmp_path, "3-063", "3-064")
    assert claim_one(tmp_path)[0] == "3-063"
    assert claim_one(tmp_path)[0] == "3-064"
    assert claim_one(tmp_path) is None


def test_claim_renders_that_page_and_no_other(tmp_path):
    _queued(tmp_path, "3-063", "3-064")
    first = claim(tmp_path)
    assert "**3-063**" in first["page_block"]
    assert "3-064" not in first["page_block"]


def test_the_note_reaches_the_page_block_through_the_queue(tmp_path):
    _queued(tmp_path, "3-063", note="Sparse page; watch the gaps.")
    assert "does not exist. Sparse page; watch the gaps." in claim(tmp_path)["page_block"]


def test_concurrent_claimers_never_share_a_ref(tmp_path):
    """`O_CREAT|O_EXCL` is the whole mechanism, so this is the test of it.

    Readers are dispatched simultaneously and by design cannot see each other, so
    a lock resting on politeness rests on nothing: the kernel decides who created
    the marker first, and there is no window between the check and the take that
    an `if not exists: write` would leave open. Eight claimers, three refs.
    """
    from concurrent.futures import ThreadPoolExecutor

    _queued(tmp_path, "3-063", "3-064", "3-065")
    with ThreadPoolExecutor(max_workers=8) as ex:
        got = [f.result() for f in [ex.submit(claim_one, tmp_path) for _ in range(8)]]
    refs = sorted(g[0] for g in got if g)
    assert refs == ["3-063", "3-064", "3-065"]
    assert got.count(None) == 5


def test_a_new_queue_clears_the_claims(tmp_path):
    """Cleared with the queue, never separately: a claim standing against a new
    batch silently withholds a page from it, and the batch comes back short for a
    reason that is a file from last week."""
    _queued(tmp_path, "3-063")
    assert claim_one(tmp_path)[0] == "3-063"
    _queued(tmp_path, "3-063")
    assert claim_one(tmp_path)[0] == "3-063"


def test_a_claim_is_never_released(tmp_path):
    """A reader that dies holding one leaves its page unread and its claim
    standing, which is the honest state rather than a silent retry."""
    _queued(tmp_path, "3-063")
    claim_one(tmp_path)
    assert claim_one(tmp_path) is None
    assert (tmp_path / "review/_claims/3-063").exists()


def test_reconcile_tells_the_two_kinds_of_miss_apart(tmp_path):
    """"No proposal" has two causes at scale and they want different answers:
    nobody took the page, or somebody took it and did not come back."""
    from harness.paths import proposal_path

    _queued(tmp_path, "3-063", "3-064", "3-065")
    claim_one(tmp_path)                      # 3-063, taken and keyed
    claim_one(tmp_path)                      # 3-064, taken and lost
    p = proposal_path("3-063", tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")

    states = {r["ref"]: r["state"] for r in
              reconcile(["3-063", "3-064", "3-065"], tmp_path)}
    assert states == {"3-063": "keyed", "3-064": "CLAIMED, no proposal",
                      "3-065": "unclaimed"}


def test_a_claim_is_stamped_for_diagnosis(tmp_path):
    """Nothing reads it to decide anything — a batch of twenty that comes back one
    page short is a question about *which* reader stalled, and a bare marker
    cannot answer it."""
    _queued(tmp_path, "3-063")
    claim_one(tmp_path)
    row = reconcile(["3-063"], tmp_path)[0]
    assert row["claimed_at"].startswith("20")
