"""Every repo-relative path a document names must resolve on disk.

This exists because `transcriber_harness.md` was cited from nine places and every
one of them was found by a human reading files. That is how they went stale in the
first place, and it is the third time a fact in this project has been kept in two
places with nothing holding them together — after `RESP_RANKS` against the corpus
header, and the ledger's `boundary` column against a sidecar that never existed.

The project's answer everywhere else is that a checkable rule beats a convention,
and there is precedent for asserting over committed configuration rather than code
(`harness/README.md` on `DERIVED` against `.gitignore`). Prose is not exempt: a
document naming a file that does not exist is a dangling pointer, and a reader who
follows it learns nothing and does not know why.

Deliberately narrow. It checks that named paths **exist**, not that what they say
about each other is true — no test can do the second, and pretending otherwise
would be worse than not testing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent

# Documents whose business is pointing at other files. Not every markdown file in
# the repo: a page of prose that happens to mention a filename is not making a
# claim the reader will follow.
DOCS = [
    "CLAUDE.md",
    "keying_spec.md",
    "harness/README.md",
    ".claude/skills/transcribe-page/SKILL.md",
    ".claude/skills/rebuild-groundtruth/SKILL.md",
    "docs/segmentation.md",
    "docs/pipeline.md",
    "docs/apparatus.md",
    "docs/rasters.md",
    "docs/decisions.md",
    "docs/open-questions.md",
]

# A repo-relative path inside backticks: it must contain a directory separator.
#
# A bare `normalize.py` in prose names the *module*, not a file at the repo root,
# and `readings.md` names the store rather than a path — matching those would fill
# the exemption list with entries that are not exemptions, which is how a check
# stops meaning anything. What this catches is the form a reader would actually
# follow: a path they could open.
PATH_RE = re.compile(r"`((?:[\w.\-]+/)+[\w.\-]+)`")

# Named but deliberately absent, each for a reason a reader should meet rather
# than trip over. Kept explicit so that "not there" and "not there *yet*" are
# different states — the same distinction `boundary` and the zone `exempt` mark
# draw, and for the same reason.
EXPECTED_ABSENT = {
    # Derived stores, regenerable and gitignored.
    "scans/chukchi-PP-NNN.png",
    "gt/fig/chukchi-PP-NNN.xml",
    "ocr/chukchi-PP-NNN.xml",
    "tei/chukchi-PP-NNN.xml",
    "gt/zones/_ink_cache.json",
    # Placeholders in worked examples, not files.
    "review/PP-NNN/proposal.json",
    "review/PP-NNN/decision.json",
    "tei/chukchi-1-100.xml",
    "data/zones_config.json",
}


def named_paths(doc: str) -> set[str]:
    text = (REPO / doc).read_text(encoding="utf-8")
    return {
        m.group(1) for m in PATH_RE.finditer(text) if _looks_like_a_path(m.group(1))
    }


def _looks_like_a_path(tok: str) -> bool:
    """Not every slash is a separator, and the false positives are instructive.

    The AMNH accession numbers are set as fractions (`70/7867`); the pre-reform
    Russian genitive endings are written `-аго/-яго`; and a repository URL
    (`gitlab.com/scripta/escriptorium`) is a path to somewhere else. Each would
    otherwise land in the exemption list, where it would read as a file this repo
    is missing.
    """
    if not any("a" <= c.lower() <= "z" for c in tok):
        return False  # a fraction, or Cyrillic
    return "." not in tok.split("/", 1)[0]  # a domain, not a directory


@pytest.mark.parametrize("doc", DOCS)
def test_the_document_itself_exists(doc):
    assert (REPO / doc).exists(), f"{doc} is in DOCS but not on disk"


@pytest.mark.parametrize("doc", DOCS)
def test_every_path_it_names_resolves(doc):
    missing = sorted(
        p
        for p in named_paths(doc)
        if p not in EXPECTED_ABSENT and "PP-NNN" not in p and not (REPO / p).exists()
    )
    assert not missing, (
        f"{doc} names paths that do not exist: {missing}. Either the file moved "
        "and the reference did not, or it never existed. If it is deliberately "
        "absent, add it to EXPECTED_ABSENT with a reason."
    )


def test_the_deleted_collation_doc_is_named_nowhere():
    """It was cited from nine places, including a committed TEI artifact. A
    tracked file citing a deleted one is the state this test exists to prevent."""
    offenders = [
        d
        for d in DOCS
        if "transcriber_harness.md" in (REPO / d).read_text(encoding="utf-8")
    ]
    assert not offenders, f"transcriber_harness.md still cited in {offenders}"


def test_the_corpus_header_names_a_real_skill():
    """Not markdown, but the same hazard and the worst instance of it: the header
    is a committed artifact asserting where the output contract is documented, and
    nothing else checks that string."""
    text = (REPO / "tei" / "corpus-header.xml").read_text(encoding="utf-8")
    assert "transcriber_harness.md" not in text
    assert ".claude/skills/transcribe-page/SKILL.md" in text
    assert (REPO / ".claude/skills/transcribe-page/SKILL.md").exists()
