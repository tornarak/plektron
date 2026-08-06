"""The open questions a collation batch left in its pages, pooled and classified.

**The collation analogue of `proposal marks`.** A dispatched batch comes back as N
page files, each carrying whatever its collator could not settle, and the rules are
explicit that an unanswered reservation *stays* a comment rather than being resolved
into a guess. That is the right per-page behaviour and the wrong per-batch one:
twenty pages of comments read one file at a time is twenty separate judgements, and
the thing worth knowing is whether they agree. One page adrift is a page to re-read.
All of them leaning the same way is the contract or the spec, not the collators.

**The classifier and the contract are two copies of one vocabulary**, so they get a
gate rather than a comment — `test_reservations.py` asserts every pattern here
matches a comment form the agent body actually states. The asymmetry in that check
is deliberate: a form added to the contract with no pattern lands in `other`, which
is visible in the report, while a pattern matching nothing in the contract is dead
surface nobody would ever see. So the gate points at the second.

**`opens:` is not a reservation.** It is on every page by construction, so pooling it
would bury the real rows under itself, and it records an answer rather than a
question. `tei seam` is what reads it.
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

from .context import norm_ref
from .seam import tei_path
from .validate import OPENS_PREFIX

# Ordered: the first pattern that matches wins, so a more specific form goes above a
# more general one. Each is keyed to a comment the collation contract fixes verbatim.
CLASSES: tuple[tuple[str, re.Pattern], ...] = (
    # The folio the page prints disagrees with the folio predicted for it. The
    # sharpest row in the report, and the one that cannot fire at all in a
    # dispatched batch — see `unchecked` below.
    ("folio_disagrees", re.compile(r"printed folio .* disagrees with expected")),
    # A positive assertion that nothing was printed, which the ledger reads as one.
    ("no_folio", re.compile(r"no printed folio on this page")),
    # Heading-shaped text the ToC does not account for. Two causes, kept apart
    # because only one is a finding about the book.
    ("heading_unmatched", re.compile(r"heading-shaped text, no ToC match")),
    ("heading_unchecked", re.compile(r"heading-shaped text, no folio to centre")),
    ("milestone_missing", re.compile(r"expected milestone for .* not found")),
    # A note running over from the previous page, with no marker on this one.
    ("footnote_orphan", re.compile(r"footnote continuation, no marker")),
    # The parallel batch's own blind spot: with `prev_tail` null a page opening on an
    # unnumbered item cannot know which item it is.
    ("list_unresolved", re.compile(r"opens mid-list, no prev_tail")),
)
# **No class for a figure named but not captioned here.** The contract asks for a
# comment and deliberately fixes no wording for it, so a pattern would have been
# built against a guess — and the gate below caught exactly that on its first run.
# Those comments land in `other`, which is visible; a class matching nothing is not.
# If a form gets fixed, the class follows it, not the other way round.


def classify(text: str) -> str:
    for name, pat in CLASSES:
        if pat.search(text):
            return name
    return "other"


def page_reservations(ref: str, root: Path = Path(".")) -> list[dict]:
    """Every open comment in one page, classified. Empty if it is not collated."""
    ref = norm_ref(ref)
    p = tei_path(ref, root)
    if not p.exists():
        return []
    try:
        tree = etree.parse(str(p))
    except (etree.XMLSyntaxError, OSError):
        # Not this verb's gate. `tei validate` says so properly, and a measurement
        # verb that raised on a malformed page would take the whole batch's report
        # down with it.
        return [{"ref": ref, "class": "unreadable",
                 "text": "not well-formed — see `tei validate`"}]
    out = []
    for node in tree.getroot().iter(etree.Comment):
        text = " ".join((node.text or "").split())
        if not text or text.startswith(OPENS_PREFIX):
            continue
        out.append({"ref": ref, "class": classify(text), "text": text})
    return out


def unchecked(refs: list[str], root: Path = Path(".")) -> list[str]:
    """What this batch could not check, which a clean report does not say by itself.

    **`expected_folio` is null on every page of a dispatched batch but the first**,
    because it is a prediction from the preceding *collated* page and in a fan-out
    there isn't one yet. So `folio_disagrees` cannot fire — not because the folios
    agree, but because nothing compared them. A report with no folio rows would
    otherwise read as "no folio problems", which is the fluent-nonsense shape: a
    confident output with the error signal removed rather than answered.

    `tei ledger` is where the check comes back, and it is the better one: it sees the
    whole run's folios at once instead of one gap at a time.
    """
    from .state import entry_state
    blind = [r for r in (norm_ref(x) for x in refs)
             if tei_path(r, root).exists()
             and entry_state(r, root)["expected_folio"] is None]
    if not blind:
        return []
    return [f"{len(blind)} of {len(refs)} had no expected_folio, so no folio "
            f"disagreement could be reported for them ({', '.join(blind[:6])}"
            f"{'…' if len(blind) > 6 else ''}). That is not agreement — nothing "
            "compared them. Run `harness tei ledger` over the run: it folds the "
            "whole sequence at once."]
