"""The skill's account of the installed model against the model's own manifest.

`.claude/skills/train-zones/SKILL.md` owns "its measured state" by `CLAUDE.md`'s
routing table, so nothing else in the repo corrects it. It said the installed
model trained on 211 pages, held out 60, and scored 95.2/80.1 on eval. The
manifest says 578, 138, and 97.8/91.2 — **not one of the four matched.** A
retrain judged against the stale figures would have looked like an improvement
while being worse than the weights already installed, which is the decision this
skill exists to inform.

This is worth a gate where the other stale numbers in this repo are not, and the
reason is narrow: **the model manifest is machine-written**, so there is a source
of truth to compare against. `train install zones --commit` writes `score`, `pages`,
`recall` and `precision` from the run itself. A doc asserting one of those is
asserting something checkable, unlike a timing measurement or a prose count.

What it holds: every percentage and page count the skill states about the
installed model must appear in the manifest. Not the reverse — the manifest
carries figures the prose has no reason to quote.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SKILL = REPO / ".claude" / "skills" / "train-zones" / "SKILL.md"
MANIFEST = REPO / "models" / "bogoras-seg" / "zones-seg.json"

#: The block of the skill that talks about the installed model. Scoped, because
#: the file also discusses hypothetical runs and worked examples, and a
#: corpus-wide number scrape would drag those in and fail on arithmetic that was
#: never a claim about this model.
SECTION = re.compile(r"The installed model trained on(.+?)\n\n\*\*", re.S)


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _claimed() -> str:
    m = SECTION.search(SKILL.read_text(encoding="utf-8"))
    assert m, ("the installed-model paragraph in SKILL.md no longer starts "
               "'The installed model trained on' — this gate is stale, which is "
               "the failure it exists to prevent")
    return m.group(1)


@pytest.mark.skipif(not MANIFEST.exists(),
                    reason="no installed model in this tree")
def test_the_page_counts_match_the_manifest():
    """`trained on N` / `held out M` against `score.*.pages`."""
    scores = _manifest()["score"]
    trained = {v["pages"] for k, v in scores.items() if k.startswith("trained-on")}
    held = {v["pages"] for k, v in scores.items() if k.startswith("eval")}
    claimed = {int(n) for n in re.findall(r"\*\*(\d+)\*\*", _claimed())}
    assert trained <= claimed, f"SKILL.md does not state trained-on {trained}"
    assert held <= claimed, f"SKILL.md does not state held-out {held}"


@pytest.mark.skipif(not MANIFEST.exists(),
                    reason="no installed model in this tree")
def test_every_percentage_stated_is_one_the_manifest_records():
    """The direction that matters: a figure in the prose that the run never
    produced. The manifest may hold figures the prose does not quote."""
    real = {v[k] for v in _manifest()["score"].values()
            for k in ("recall", "precision")}
    stated = {float(x) for x in re.findall(r"(\d+\.\d+)%?", _claimed())}
    stray = stated - real
    assert not stray, (
        f"SKILL.md states {sorted(stray)}, which the manifest does not record. "
        f"It has {sorted(real)}. A retrain judged against a figure no run "
        f"produced can look like an improvement while being worse.")


@pytest.mark.skipif(not MANIFEST.exists(),
                    reason="no installed model in this tree")
def test_the_scrape_actually_found_numbers():
    """Guard on the guard: a reworded paragraph would make both assertions above
    pass over an empty set."""
    claimed = _claimed()
    assert re.findall(r"\d+\.\d+", claimed), "no percentages found in the section"
    assert re.findall(r"\*\*\d+\*\*", claimed), "no page counts found in the section"


def test_the_manifest_is_shaped_the_way_this_gate_reads_it():
    """`train install zones --commit` writes this; if its shape moves, so must this."""
    if not MANIFEST.exists():
        pytest.skip("no installed model in this tree")
    scores = _manifest()["score"]
    assert scores, "manifest carries no score block"
    for key, v in scores.items():
        assert {"pages", "recall", "precision"} <= set(v), key
