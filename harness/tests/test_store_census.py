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

**`gt/ocr` is deliberately absent.** No doc states its size as a live claim, and
this gate does not invent one — it records the asymmetry rather than fixing it,
since which docs should carry which counts is an editorial question and not a
gate's to decide.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent


# --------------------------------------------------------------- the readers
#
# Each answers through the store's own parser, never a scrape of its file. That
# rule is what the alias figure cost when it was broken: `entities.load` rejects
# a row with no form, and a regex over the markdown does not.

def _glob(rel: str) -> int:
    return len(list((REPO / rel).glob("chukchi-*.xml")))


def _alias_rows(blank: bool) -> int:
    from harness.entities import load
    rows = [t for r in load(REPO).values() for t in r["aliases"]]
    return sum(1 for t in rows if not t["lang"]) if blank else len(rows)


def _authorities(kind: str) -> int:
    from harness import apparatus
    if kind == "printed":
        doc = json.loads((REPO / "data" / "authorities.json").read_text("utf-8"))
        return doc["source"]["count"]
    if kind == "records":
        return len(apparatus._authorities(REPO))
    sigla = apparatus.sigla(REPO)
    if kind == "sigla_rows":
        return len(sigla)
    if kind == "sigla_names":
        return len({r["name"] for r in sigla})
    raise AssertionError(kind)


COUNTS = {
    "fig_pages":      lambda: _glob("gt/fig"),
    "zone_pages":     lambda: _glob("gt/zones"),
    "scans":          lambda: len(list((REPO / "scans").glob("chukchi-*.png"))),
    "entities":       lambda: len(list((REPO / "entities").glob("*/*.md"))),
    "alias_rows":     lambda: _alias_rows(blank=False),
    "alias_blank":    lambda: _alias_rows(blank=True),
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
    Claim("docs/pipeline.md", "entities",
          r"holds \*\*(\d+) entries against zero collated pages\*\*"),
    Claim("docs/edition.md", "alias_blank",
          r"most of the store is blank: (\d+) of \d+ rows are"),
    Claim("docs/edition.md", "alias_rows",
          r"most of the store is blank: \d+ of (\d+) rows are"),
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
    Claim("harness/README.md", "works_records",
          r"the book's own (\d+)-work bibliography"),
    Claim("harness/README.md", "sigla_rows",
          r"resolves nothing: (\d+) sigla share \d+ names"),
    Claim("harness/README.md", "sigla_names",
          r"resolves nothing: \d+ sigla share (\d+) names"),
    Claim("harness/VERBS.md", "sigla_rows",
          r"which field caught it: (\d+) sigla share \d+ names"),
    Claim("harness/VERBS.md", "works_records",
          r"Bare, it lists all (\d+) records"),
    Claim("harness/VERBS.md", "works_printed",
          r"records — the (\d+) printed on folios 3–9"),
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
    if c.derived and not (REPO / "scans").exists():
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
        if key == "scans" and not (REPO / "scans").exists():
            continue
        assert fn() > 0, f"{key} reader returned nothing — the gate is hollow"


def test_the_two_authorities_quantities_are_not_the_same_number():
    """73 and 74 have been conflated repeatedly, in both directions, and a gate
    that happened to pass because they were equal would be no gate at all. The
    difference is `source.unprinted` — `jochelson1905`, cited 36 times in parts
    2 and 3 and impossible in part 1's list."""
    doc = json.loads((REPO / "data" / "authorities.json").read_text("utf-8"))
    assert COUNTS["works_records"]() == \
        COUNTS["works_printed"]() + len(doc["source"]["unprinted"])
    assert COUNTS["works_records"]() != COUNTS["works_printed"]()


def test_sigla_rows_exceed_the_names_they_resolve():
    """The reason the resolution table has more rows than sigla: a siglum
    printed across several volumes is a row per volume. If these ever became
    equal the `52 over 34` sentences would be true by coincidence."""
    assert COUNTS["sigla_rows"]() > COUNTS["sigla_names"]()
