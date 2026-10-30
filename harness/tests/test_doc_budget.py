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
PROJECT = REPO / "jesup" / "bogoras-chukchi"

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
# (now `edition/geo/`, and the path here is the raise's, not a live pointer)
# is **derived but tracked**, which is the one store that contradicts the rule
# the layout block states everywhere else — derived trees are ignored and a
# clone rebuilds them. Here a clone cannot: the sources are outside the
# repository. An agent that read nothing else would delete it as derived cruft
# or try to regenerate it, so the exception has to be visible where the rule is.
#
# **Raised a third time, 15_000 → 15_200, for `lexicon/` (now `edition/lexicon/`)**, and it is the same
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
# **Raised a sixth time, 16_800 → 17_400, for `ed/`** — a genuinely new
# top-level store, which is the same kind as all five above and not the accretion
# this gate exists to stop. `gt/fig-img/` and `gt/page-img/` became
# `ed/fig-img/` and `ed/page-img/`: they hold retouched crops and a hand-worked
# leaf, which are new artefacts an editor vouches for rather than reproductions
# of the page, and `gt/` is the latter. They sat under `gt/` on the reading that
# it means "what a human has been through" — the same loose reading that makes a
# page keyed without a prediction look less `#gt` than one keyed with it. It is
# not what the rank means, and the rank is carried by the path, so the path was
# wrong. `docs/apparatus.md` owns the argument; the two lines here are the
# enumeration the layout block owes every top-level store.
#
# The `gt/` line also gained its definition, which is the part worth the bytes:
# it read "what a human has been through", and an agent inheriting only this file
# would draw exactly the conclusion this move corrects.
#
# **`ed/` has since become `edition/`** and the paths above are that raise's, not
# a live pointer. The argument it records still holds and is why the store is not
# under `gt/`; what changed is the axis the store is named on — `#ed` is a rank
# and lives in `@resp`, while the folder holds a *layer*, which is why
# `marks_exempt.json` is `#ed` and is not in it.
#
# Headroom deliberately left, on the fifth raise's argument.
#
# **Raised a seventh time, 17_400 → 18_000, for the store split**, and it is the
# fifth raise's kind rather than the kind this gate stops. `data/` was a potpourri
# and is now three stores — `edition/` (the layer a reader is served), `config/`
# (what a pass is tuned by, and the editor's rulings over one) and `data/` (the
# receipts and the vendored schema) — so the layout block owes three enumerations
# where it owed one, and it says which of the three a new file belongs in, which
# is the question the old single line could not answer.
#
# The block is *shorter* than it was per store: `entities/`, `lexicon/` and
# `data/geo/` folded into `edition/` and stopped being top-level entries. It
# still landed at 17,397 against a 17,400 cap — three bytes, which is exactly the
# condition the fifth raise's paragraph says this gate must not create, and it
# was reached by rewording a clause rather than by cutting anything. So the
# number moves instead, and the headroom is the point of the size of the move.
CLAUDE_MD_MAX_BYTES = 18_000

CITE_RE = re.compile(r"CLAUDE\.md, [\"'“]([^\"'”)]{4,80})")


def test_claude_md_stays_under_budget():
    size = (REPO / "CLAUDE.md").stat().st_size
    assert size <= CLAUDE_MD_MAX_BYTES, (
        f"CLAUDE.md is {size} bytes against a {CLAUDE_MD_MAX_BYTES} cap. It is "
        "inherited whole by every subagent on every page; new material belongs "
        "in the file the precedence table says owns it, with a pointer here "
        "only if an agent that reads nothing else could violate it."
    )


def _routing_haystack() -> str:
    """CLAUDE.md, plus every document its precedence table routes to.

    **Two levels, because routing is two levels.** `.claude/agents/moll-reader.md`
    is named nowhere in CLAUDE.md, and is not an orphan: the table gives
    `.claude/skills/read-moll-page/` the Moll pass "whole", and that skill names
    its agent three times, including "Read `.claude/agents/moll-reader.md` and
    follow it as written". A one-level check would report it and the only ways to
    satisfy that report are to spend CLAUDE.md budget on a row that says nothing
    new, or to delete a true statement. Both are worse than the check being right.
    """
    router = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    parts = [router]
    for p in sorted(REPO.glob(".claude/skills/*/*.md")) + \
            sorted((REPO / "docs").glob("*.md")):
        named = str(p.relative_to(REPO)) in router or \
            f"{p.parent.relative_to(REPO)}/" in router
        if named:
            parts.append(p.read_text(encoding="utf-8"))
    return "".join(parts)


def _routable():
    """Every document that owns something, by CLAUDE.md's own account of what a
    document is. A skill is named by its directory, everything else by its path."""
    for p in sorted((REPO / "docs").glob("*.md")):
        yield str(p.relative_to(REPO))
    for p in sorted(REPO.glob(".claude/skills/*/SKILL.md")):
        yield f"{p.parent.relative_to(REPO)}/"
    for pat in (".claude/agents/*.md", ".claude/rules/*.md"):
        for p in sorted(REPO.glob(pat)):
            yield str(p.relative_to(REPO))


def test_every_doc_is_named_by_the_router():
    """**Widened from `docs/*.md` alone**, which left 5 skills, 3 agents and
    `.claude/rules/` invisible to the one check that asks whether a document is
    reachable. They are where this project keeps its passes, and a pass nothing
    routes to is a pass nobody runs.

    This is the strict half of the pair. Its sibling — the stranded-citation
    check below — would get *looser* if widened the same way, which is why the
    two are not one commit and not one edit.
    """
    haystack = _routing_haystack()
    orphans = sorted(d for d in _routable() if d not in haystack)
    assert not orphans, (
        f"documents CLAUDE.md's precedence table does not reach: {orphans}. A "
        "doc nothing routes to is a doc nobody reads — add a row saying what it "
        "owns, name it from a document that already has one, or merge it into "
        "one that does."
    )


def test_no_code_citation_is_stranded():
    """**Deliberately not widened, on a measurement.**

    The obvious symmetry with the orphan check above is to grow this haystack to
    the skills, the agents and `harness/README.md` too, on the reasoning that a
    passage which moved into a skill now reads as stranded. Measured both ways:
    **0 stranded either way.** So widening buys nothing today and costs the one
    thing a gate has — a citation that moves into a skill would stop being
    reported, and reporting it is arguably correct, since CLAUDE.md's table says
    which document owns what and a citation should name the owner.

    Left narrow until a real false positive appears, at which point the fix is
    known and this note is why it waits. The two halves of this file pull in
    opposite directions and only one of them was a strengthening.
    """
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
