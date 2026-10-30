"""Every prose figure that counts a store, against the store's own reader.

The pass that wrote this had just corrected the authorities numbers at **two
sites of eighteen**, having found the other sixteen only by grepping the literal
rather than trusting a list. Before that, `docs/edition.md` carried "466 of 738"
alias rows where the store holds 439 of 711 — a wrong figure produced by a
markdown scrape that counted 27 empty `| | | no | |` placeholder rows which
`entities.load` correctly rejects, written *during* the pass that was fixing
wrong figures. A number a human maintains by hand goes stale silently, and
prose is where this project keeps its reasoning, so a stale number here is a
wrong premise for the next decision.

**Only a figure with a machine-readable source of truth is gated**, which is
`test_model_manifest.py`'s rule and the reason it holds where a general
number-sweep would not. Each entry below names one claim site, the regex that
anchors it in its own sentence, and the reader that answers it. Nothing is
scraped corpus-wide.

**A live count and a historical one are indistinguishable to a regex.** The METS
anecdote in `docs/rasters.md`, `harness/README.md` and `harness/VERBS.md` says a
manifest "manifested 20 files against a store of 663" — a fact about a moment,
which must *not* track the live store. That is why this is an explicit table and
not a sweep, and it is the same blind spot `test_doc_refs.py`'s `PATH_RE` has
from the other direction: what a pattern cannot see, a person has to declare.

**Only a figure counting a CLOSED set belongs here at all**, and that rule was
learned from the one entry that broke. `edition/entities/` grows every time somebody
writes an entity, so gating a prose count of it meant retyping a number into
`docs/pipeline.md` on every pass — keeping a figure correct in a place CLAUDE.md
says no figure belongs: *"counts deliberately absent — they go stale in a file
nothing regenerates."* A gate that maintains a defect reads as diligence. The
sentence lost its number and made the same argument; the claim was deleted, not
repaired. What is left counts the book's own bibliography and sigla, the rasters
the three PDFs hold, and the pages carrying figures — sets that move only when
the artifact is re-read, which is when a human is looking at the sentence anyway.

**And a figure belongs in ONE document**, the one the CLAUDE.md precedence table
says owns the store. This gate held the works and sigla totals at three sites
each and was thereby maintaining the triplication rather than surfacing it —
*"a fact stated twice is a defect"* — so `harness/README.md` and
`harness/VERBS.md` now argue without the numbers and name `docs/apparatus.md`,
which owns them. Six claim sites went; no argument did.

**`gt/ocr` is deliberately absent.** No doc states its size as a live claim, and
this gate does not invent one.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
PROJECT = REPO / "jesup" / "bogoras-chukchi"


# --------------------------------------------------------------- the readers
#
# Each answers through the store's own parser, never a scrape of its file. That
# rule is what the alias figure cost when it was broken: `entities.load` rejects
# a row with no form, and a regex over the markdown does not.

def _glob(rel: str) -> int:
    return len(list((PROJECT / rel).glob("chukchi-*.xml")))


def _authorities(kind: str) -> int:
    from harness import apparatus
    if kind == "printed":
        doc = json.loads((PROJECT / "edition" / "authorities.json").read_text("utf-8"))
        return doc["source"]["count"]
    if kind == "records":
        return len(apparatus._authorities(PROJECT))
    sigla = apparatus.sigla(PROJECT)
    if kind == "sigla_rows":
        return len(sigla)
    if kind == "sigla_names":
        return len({r["name"] for r in sigla})
    raise AssertionError(kind)


COUNTS = {
    "fig_pages":      lambda: _glob("gt/fig"),
    "zone_pages":     lambda: _glob("gt/zones"),
    "scans":          lambda: len(list((PROJECT / "scans").glob("chukchi-*.png"))),
    "entities":       lambda: len(list((PROJECT / "edition" / "entities").glob("*/*.md"))),
    "works_printed":  lambda: _authorities("printed"),
    "works_records":  lambda: _authorities("records"),
    "sigla_rows":     lambda: _authorities("sigla_rows"),
    "sigla_names":    lambda: _authorities("sigla_names"),
}


# ----------------------------------------------------------------- the claims

@dataclass(frozen=True)
class Claim:
    doc: str
    key: str
    pattern: str
    #: Derived and gitignored, so absent on a fresh clone rather than wrong.
    derived: bool = False


CLAIMS = (
    Claim("CLAUDE.md", "scans",
          r"scans/\s+the (\d+) rasters, 300 dpi", derived=True),
    Claim("docs/apparatus.md", "fig_pages",
          r"The (\d+) pages with figures have been segmented"),
    # **`edition/entities/` is deliberately absent, and its removal is the rule this
    # table now states.** It was the one claim here counting a store under
    # active growth, so it was also the only one that ever went stale — every
    # entity written broke it, and the repair was always to retype a number
    # into prose that CLAUDE.md says should not carry one: "counts deliberately
    # absent — they go stale in a file nothing regenerates." The sentence it
    # anchored argues that the encyclopedia runs ahead of collation, and
    # "hundreds of entries against zero collated pages" argues it exactly as
    # well while being true forever. A gate that keeps a number correct in a
    # place the number does not belong is maintaining the defect.
    #
    # What stays below all counts a **closed set** — the book's own bibliography
    # and sigla, the rasters the three PDFs hold, the pages that carry figures.
    # Those move when the artifact is re-read, which is when a human should be
    # looking at the sentence anyway. **The test for whether a figure belongs
    # here is not "can a reader answer it" but "is the set it counts closed";
    # for an open one, delete the figure rather than gate it.**
    #
    # The two authorities quantities that are routinely confused: `source.count`
    # is the folios 3-9 list, the record count includes the unprinted
    # `jochelson1905`. Both are gated, at the sentence that distinguishes them.
    Claim("docs/apparatus.md", "works_printed",
          r"front\.authorities-quoted`\): \*\*(\d+) works\*\*"),
    Claim("docs/apparatus.md", "works_records",
          r"not the record count\.\*\* The store holds \*\*(\d+)\*\*"),
    Claim("docs/apparatus.md", "sigla_names",
          r"one entry per volume — (\d+) printed\n?\s*sigla"),
    Claim("docs/apparatus.md", "sigla_rows",
          r"sigla, (\d+) `cited_as` entries"),
    # **`harness/README.md` and `harness/VERBS.md` are absent, and that is the
    # routing table being obeyed rather than a gap.** Those two documents each
    # restated the works and sigla totals — the same four numbers written in
    # three places, which CLAUDE.md calls a defect outright, and which this
    # gate was quietly maintaining instead of exposing. `docs/apparatus.md`
    # owns the apparatus stores; both now make their argument without the
    # figures and name the owner, so the count exists once and is checked once.
    # Six claim sites went with them, and nothing about the sentences' meaning
    # did: "sigla outnumber the names they share" is the same argument as
    # "67 sigla share 42 names" for every purpose a reader of a module map has.
)


def _text(doc: str) -> str:
    return (REPO / doc).read_text(encoding="utf-8")


@pytest.mark.parametrize("c", CLAIMS, ids=lambda c: f"{c.doc}:{c.key}")
def test_the_claim_is_still_where_the_gate_looks(c: Claim):
    """**The guard on the guard.** A regex that stops matching is a gate that
    silently checks nothing, which is worse than no gate — it reads as coverage.
    If this fails, the prose was reworded: re-anchor the pattern, do not delete
    the entry."""
    assert re.search(c.pattern, _text(c.doc)), (
        f"{c.doc}: nothing matches {c.pattern!r} any more. The sentence stating "
        f"{c.key!r} was reworded or removed, so this gate has stopped checking "
        "it. Re-anchor the pattern against the new wording.")


@pytest.mark.parametrize("c", CLAIMS, ids=lambda c: f"{c.doc}:{c.key}")
def test_the_figure_matches_the_store(c: Claim):
    if c.derived and not (PROJECT / "scans").exists():
        pytest.skip("scans/ is derived and absent from this clone")
    m = re.search(c.pattern, _text(c.doc))
    assert m, "covered by the companion test; skipping the arithmetic"
    assert int(m.group(1)) == COUNTS[c.key](), (
        f"{c.doc} says {m.group(1)} for {c.key!r}; the store's own reader says "
        f"{COUNTS[c.key]()}. The doc is stale — or the store changed and the "
        "prose is the record of what it used to be.")


def test_every_reader_answers():
    """A count that raises or returns zero would make its claim vacuously
    checkable, so the readers are exercised on their own before anything leans
    on them. `scans` is exempt: derived, and legitimately absent."""
    for key, fn in COUNTS.items():
        if key == "scans" and not (PROJECT / "scans").exists():
            continue
        assert fn() > 0, f"{key} reader returned nothing — the gate is hollow"


def test_the_two_authorities_quantities_are_not_the_same_number():
    """73 and 74 have been conflated repeatedly, in both directions, and a gate
    that happened to pass because they were equal would be no gate at all. The
    difference is `source.unprinted` — `jochelson1905`, cited 36 times in parts
    2 and 3 and impossible in part 1's list."""
    doc = json.loads((PROJECT / "edition" / "authorities.json").read_text("utf-8"))
    assert COUNTS["works_records"]() == \
        COUNTS["works_printed"]() + len(doc["source"]["unprinted"])
    assert COUNTS["works_records"]() != COUNTS["works_printed"]()


def test_sigla_rows_exceed_the_names_they_resolve():
    """The reason the resolution table has more rows than sigla: a siglum
    printed across several volumes is a row per volume. If these ever became
    equal the `52 over 34` sentences would be true by coincidence."""
    assert COUNTS["sigla_rows"]() > COUNTS["sigla_names"]()
