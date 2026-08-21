"""CLAUDE.md stays a router, and the router stays total.

The size is a finding, not a preference: CLAUDE.md was 40 KB on 2026-07-29 and
130 KB on 2026-08-04 — tripled in six days of ordinary work, by accretion nobody
decided on. Every subagent inherits the file in full on every dispatch, so at
130 KB it was ~46k tokens per reader per page, more than the pass's own
documents put together. A convention did not hold it, so a gate does.

Two failure modes the split created, and the other two tests:

- **An orphan doc.** The split's whole mechanism is that a moved section is one
  `Read` away *because the router names it*. A file under `docs/` that the
  precedence table does not name is a doc nobody reads — the loud absence
  converted to a silent one, the `.gitkeep` fault in prose form.
  `test_doc_refs.py` checks the converse (every path a doc names resolves), so
  the pair is total in both directions.
- **A stranded citation.** Code cites CLAUDE.md by quoted section title, and
  the split moved sections wholesale. A citation whose quoted phrase no longer
  occurs anywhere routable sends a reader to a file that does not say it.
  Substring matching, deliberately: several citations quote mid-paragraph
  prose rather than headings, and `zones.py` splits one citation across two
  string literals, so a per-line regex captures a truncated fragment — which a
  substring test tolerates and an exact-title test would fail on.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Headroom over the ~12 KB the router-plus-invariants rewrite landed at. Bytes,
# not tokens: deterministic, no tokenizer dependency (this corpus measures
# ~0.35 tokens/byte, so this is roughly a 5k-token ceiling).
#
# **Raised once, 14_000 → 14_500, and the reason is the one that licenses a
# raise at all**: routing a reader to `corpus state` instead of `ocr pages` cost
# more bytes than the wrong pointer did, and a router that misroutes is not
# cheaper for being small. A raise to make room for *material* is the accretion
# this gate exists to stop; a raise to make a pointer correct is the gate
# working. Say which one it is here whenever this number moves.
#
# **Raised again, 14_500 → 15_000, by the editor**, for the atlas: `data/geo/`
# is **derived but tracked**, which is the one store that contradicts the rule
# the layout block states everywhere else — derived trees are ignored and a
# clone rebuilds them. Here a clone cannot: the sources are outside the
# repository. An agent that read nothing else would delete it as derived cruft
# or try to regenerate it, so the exception has to be visible where the rule is.
#
# **Raised a third time, 15_000 → 15_200, for `lexicon/`**, and it is the same
# kind of raise as the two above rather than the kind this gate exists to stop.
# The layout block enumerates *every* top-level store; a new tracked one missing
# from it does not make the block shorter, it makes it wrong, and wrong in the
# direction that costs something — an agent reading only this file would meet an
# unlisted directory and take it for the derived cruft the block says everything
# unlisted is. The entry is three lines and says what the store is for and what
# gates it. Nothing else about the lexicon is here: `docs/edition.md` owns it,
# and the row that routes there already existed.
#
# **Raised a fourth time, 15_200 → 16_000, by the editor**, for `gt/page-img/`
# and with headroom deliberately left over. Same kind as the three above: the
# layout block enumerates every top-level store, and `page-img/` is *tracked*
# while sitting under a `gt/` line and beside an `mz/` line that a reader would
# otherwise resolve the wrong way — the tracked half is the ChaiNNer master no
# clone can rebuild, the ignored half is what a leaf is served as. Naming only
# one of the pair is worse than naming neither.
#
# The headroom is the point of the size of the raise. Three of the four raises
# so far were three-byte squeezes that cost more editorial attention than the
# bytes were worth, and a cap tight enough that adding a *store name* requires
# rewording a neighbouring clause is not measuring what it means to measure. It
# still gates accretion — 800 bytes is a paragraph, not a section — but it no
# longer taxes correctness.
#
# **Raised a fifth time, 16_000 → 16_800**, and the reason is that the fourth
# raise's headroom was gone: the file stood at 15,999 against a 16,000 cap, so
# the next correct fact cost a reword — the exact condition the paragraph above
# says this gate should not create. It was found that way, by a review pass that
# could not add the two CLI groups the router had been missing since `geo` and
# `verbs` were added.
#
# Same kind as the four above rather than the kind this gate exists to stop. Two
# routing rows: root `README.md`, which `CLAUDE.md` already cites by name for the
# four provenance levels while the table did not list it, and the Moll pass,
# which is a whole third track with its own agent, skill, scratch store and
# declared dependency and had no route from here at all — an agent meeting
# `scratch/chukchi/` would find nothing in the router that admits it exists.
#
# Deleting the ground-truth-loss retelling paid for about half of it. That
# section was five sentences here and the story is told in full in
# `docs/decisions.md`, which the table already routes to and which owns settled
# history; what stays is the rule the store layout obeys, folded into the `gt/`
# line where it binds.
CLAUDE_MD_MAX_BYTES = 16_800

CITE_RE = re.compile(r"CLAUDE\.md, [\"'“]([^\"'”)]{4,80})")


def test_claude_md_stays_under_budget():
    size = (REPO / "CLAUDE.md").stat().st_size
    assert size <= CLAUDE_MD_MAX_BYTES, (
        f"CLAUDE.md is {size} bytes against a {CLAUDE_MD_MAX_BYTES} cap. It is "
        "inherited whole by every subagent on every page; new material belongs "
        "in the file the precedence table says owns it, with a pointer here "
        "only if an agent that reads nothing else could violate it."
    )


def test_every_doc_is_named_by_the_router():
    router = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    orphans = sorted(
        p.name
        for p in (REPO / "docs").glob("*.md")
        if f"docs/{p.name}" not in router
    )
    assert not orphans, (
        f"docs/ holds files CLAUDE.md's precedence table does not name: "
        f"{orphans}. A doc nothing routes to is a doc nobody reads — add a row "
        "saying what it owns, or merge it into one that has a row."
    )


def test_no_code_citation_is_stranded():
    haystack = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    for doc in (REPO / "docs").glob("*.md"):
        haystack += doc.read_text(encoding="utf-8")
    stranded = []
    for py in (REPO / "harness").rglob("*.py"):
        for line in py.read_text(encoding="utf-8").splitlines():
            for phrase in CITE_RE.findall(line):
                if phrase not in haystack:
                    stranded.append(f"{py.relative_to(REPO)}: {phrase!r}")
    assert not stranded, (
        f"citations of CLAUDE.md quote phrases that occur neither there nor "
        f"under docs/: {stranded}. Either the passage moved somewhere the "
        "router does not reach, or the citation should name the file that now "
        "holds it."
    )
