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
CLAUDE_MD_MAX_BYTES = 14_000

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
