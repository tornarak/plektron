"""The corpus is NFD, and every mark on a base is licensed — as a gate, not a verb.

`CLAUDE.md` says `harness corpus normalize` **is** the gate. It was not one:
nothing ran it. It is a verb a human invokes, and the only test asserting
`not rep["nfd_offenders"]` (`test_footnotes.py`) runs against a fixture rather
than the tree. So conformance held exactly as often as someone remembered to
check, and in August 2026 a single 152-entry authoring pass put **twelve files**
out of conformance in three days — names pasted from sources arrive NFC, and
`entities.parse` normalizes on read, so nothing downstream ever complained.

That last part is why a gate is the right instrument rather than a louder
docstring. The breach was invisible to every consumer: alias matching,
`lexicon lookup` and `marks.fold` all saw decomposed text whatever the file
held. A rule whose violation has no symptom needs something that looks.

**Only the two arms with no reading to adjudicate are gated here**, which is the
same line `normalize --commit` itself draws — it writes these and reports the
rest:

  - `nfd_offenders` — a representation difference, never a character identity
    one. `NFD(text)` is the answer and there is nothing to decide.
  - `unlicensed_marks` — a mark on a base `keying_spec` §2.6 does not license.
    Currently zero, and it is the arm that would catch an invented glyph, which
    is the failure the firewall exists for.

**Three arms are deliberately not gated**, and saying why is the point of the
distinction:

  - `lookalikes` (20 today) is a standing editorial backlog, not drift. The
    trap is scoped — inside Tier-1 spans U+0027 and U+002D are the only
    apostrophe and hyphen, while English prose reproduces the print *including*
    curly quotes — so an ASCII apostrophe in a keyed page is a judgement about
    whether that line is quoting or writing. `test_lookalike_scope.py` holds
    the two tables apart for the same reason.

    It was 516 while the quote and apostrophe arms also read
    `edition/entities/`, and that was nearly the whole of it: an entry is the
    editor's own voice, so "the book sets curly quotes" was never a premise
    that held over it. Those two arms no longer read that store at all
    (`normalize.scoped_files`); its NFD arm is untouched, which is the one the
    breach above was actually about.
  - `footnote_markers` (6) is a bare ASCII digit where a superscript sort was
    meant, in three `gt/ocr` pages and their matching `review/` decisions. Each
    needs a reading against the raster.
  - `spacing_offenders` is auto-fixable and still not gated, on evidence: the
    one instance in the store sat inside a quotation of 1-190, where the space
    stood between an editor's elision and the book's own semicolon. Deciding it
    took reading the sentence. Something that needed a human once is not
    something to fail a build on unattended — revisit if it recurs and the
    reading is always the same.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.normalize import scan, scoped_files

REPO = Path(__file__).resolve().parent.parent.parent
PROJECT = REPO / "jesup" / "bogoras-chukchi"


@pytest.fixture(scope="module")
def report() -> dict:
    """One walk for both assertions — it reads ~2,000 files and costs ~4s."""
    return scan(PROJECT)


def test_the_scan_actually_reached_the_corpus(report):
    """**The guard on the guard.** Both assertions below are vacuously true over
    an empty walk, and this gate lives or dies on the walk being real. A glob
    that stopped matching would turn the whole file green and silent, which is
    the failure it exists to prevent, one level up."""
    assert report["files"] > 0, "the corpus glob matched nothing"
    scoped = {str(p.relative_to(PROJECT)) for p in scoped_files(PROJECT)}
    assert any(s.startswith("edition/entities/") for s in scoped), \
        "edition/entities/ is out of scope — the store where the last drift appeared"
    assert any(s.startswith("gt/ocr/") for s in scoped), \
        "gt/ocr/ is out of scope — the store the NFD rule is chiefly about"


def test_the_corpus_is_nfd(report):
    """`keying_spec.md` §1, corpus-wide. **Never NFKC**: it has compatibility
    decompositions for two inventory glyphs and destroys them — `ᵋ` U+1D4B
    becomes plain U+025B, `˙` U+02D9 becomes space plus combining dot."""
    bad = report["nfd_offenders"]
    assert not bad, (
        f"{len(bad)} file(s) hold precomposed characters: "
        + "; ".join(f"{o['path']} ({o['chars']})" for o in bad[:8])
        + ". Fix with `harness corpus normalize --all --commit`, which folds "
        "these mechanically — a representation change, never an identity one."
    )


def test_every_mark_is_licensed(report):
    """`keying_spec.md` §2.6. A mark on a base the spec does not license is a
    glyph nobody declared, which is the shape an invented reading takes — so
    this is the arm nearest the firewall, and it is zero rather than small."""
    bad = report["unlicensed_marks"]
    assert not bad, (
        f"{len(bad)} unlicensed mark/base pair(s): {bad[:8]}. Unlike NFD drift "
        "this is not mechanically fixable — the reading is wrong, or §2.6 needs "
        "the pair added by a human who checked the raster."
    )
