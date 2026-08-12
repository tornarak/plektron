"""`lexicon/` — what an editor wrote about one Tier-1 form, and nothing else.

The store is thin by design, so most of what these hold is the *absence* of
things: no glosses, no attestations, no pronunciation, because all three are
derived on every load and a copy would go stale in the direction that hides it.

The rest is the filename problem. Naming a file after the form's typeable key is
the obvious scheme and it is measurably unusable — over the corpus's 609
attested forms it yields 23 pairs differing only in case, and the check that
would catch a collision cannot, because `handle_key` is non-injective by design
and both files pass it while only one can exist. So the slug is authored and the
gate is about the filesystem, not about the key.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness import lexicon as lex

FORM = "Kuluˊči"


def entry(root: Path, form: str, *, slug: str = "", status: str = "proposed",
          since: str = "1-042", see: str = "", note: str = "a note") -> Path:
    p = lex.lex_dir(root) / f"{slug or lex.suggest_slug(form)}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {form}\n\n- status: {status}\n- since: {since}\n"
                 + (f"- see: {see}\n" if see else "")
                 + f"\n## editor's note\n\n{note}\n", encoding="utf-8")
    return p


# --- the identity -------------------------------------------------------------

def test_the_identity_is_the_form_and_carries_no_language(tmp_path):
    """A form only becomes `ckt` when a collator judges it, and most of the
    corpus is unjudged. An id holding a language would leave those forms
    unaddressable in the one store built on their being readable first."""
    entry(tmp_path, FORM)
    store = lex.load(tmp_path)
    assert set(store) == {lex.norm_form(FORM)}
    assert ":" not in next(iter(store))


def test_an_absent_store_is_empty_and_not_an_error(tmp_path):
    assert lex.load(tmp_path) == {}
    assert lex.check(tmp_path)["ok"]


def test_a_form_that_is_not_nfd_is_normalized_rather_than_refused(tmp_path):
    """A silent fold, as `entities.parse` does it. The file is hand-maintained
    and can drift between edits; an entry that failed to resolve because a
    session keyed a precomposed character would be a silent miss, and a fold
    recovers it completely."""
    import unicodedata
    entry(tmp_path, unicodedata.normalize("NFC", "Nordenskiöld"))
    assert unicodedata.normalize("NFD", "Nordenskiöld") in lex.load(tmp_path)


# --- the filesystem, which is the part that bites -----------------------------

def test_two_slugs_differing_only_in_case_are_refused(tmp_path):
    """`Aiˊwan` and `aiˊwan` are both this corpus's, and both key to `ai'wan`.
    On a case-insensitive filesystem one file holds them and the other is gone
    with nothing to show for it."""
    entry(tmp_path, "Aiˊwan", slug="Aiwan")
    entry(tmp_path, "aiˊwan", slug="aiwan")
    got = lex.check(tmp_path)
    assert not got["ok"]
    assert any("only in case" in e for e in got["errors"])


def test_two_files_claiming_one_form_are_refused(tmp_path):
    entry(tmp_path, FORM, slug="one")
    entry(tmp_path, FORM, slug="two")
    got = lex.check(tmp_path)
    assert not got["ok"]
    assert any("already the identity" in e for e in got["errors"])


def test_an_unkeyable_form_is_reported_and_never_fatal(tmp_path):
    """`Kereˊt-kun’s` carries U+2019, which is outside the inventory, so it has
    no canonical URL. The entry is not wrong for that — but a reader is owed the
    fact rather than left to find it when the link does not resolve."""
    entry(tmp_path, "Kereˊt-kun’s", slug="keretkuns")
    got = lex.check(tmp_path)
    assert got["ok"]
    assert [u["form"] for u in got["unkeyable"]] == [
        lex.norm_form("Kereˊt-kun’s")]


def test_the_suggested_slug_is_a_reduction_and_not_the_key(tmp_path):
    """`handle_key` keeps case and emits `:` — both are exactly what a filename
    must not depend on."""
    assert lex.suggest_slug(FORM) == "kulu-c-i"
    assert ":" not in lex.suggest_slug("Telqäˊp")


# --- the fields ---------------------------------------------------------------

def test_since_is_required(tmp_path):
    p = lex.lex_dir(tmp_path) / "x.md"
    p.parent.mkdir(parents=True)
    p.write_text(f"# {FORM}\n\n- status: proposed\n\n## editor's note\n\nx\n",
                 encoding="utf-8")
    with pytest.raises(lex.Malformed, match="since"):
        lex.load(tmp_path)


def test_a_dangling_see_is_an_error(tmp_path):
    entry(tmp_path, FORM, see="Čeˊwin")
    got = lex.check(tmp_path)
    assert not got["ok"]
    assert any("resolves to no entry" in e for e in got["errors"])


def test_a_resolving_see_is_not(tmp_path):
    """A pointer, and deliberately not a claim that the two are one word: the
    book sets `Čeˊwɪn` and `Čeˊwin`, and `data/marks_exempt.json` rules that
    ambiguity real. Nothing in this store overrides a ruling."""
    entry(tmp_path, "Čeˊwɪn", slug="cewin-1", see="Čeˊwin")
    entry(tmp_path, "Čeˊwin", slug="cewin-2")
    assert lex.check(tmp_path)["ok"]


def test_nothing_derived_may_be_written_into_a_file(tmp_path):
    """**The load-bearing negative.** A `## glosses` or `## attestations`
    section is not merely unused — it is a second copy of a fact the card
    derives, and it would go stale while still reading as an entry. Refused at
    the parser so it cannot be written by accident."""
    p = lex.lex_dir(tmp_path) / "x.md"
    p.parent.mkdir(parents=True)
    p.write_text(f"# {FORM}\n\n- status: proposed\n- since: 1-042\n"
                 "\n## glosses\n\n\"a bay\"\n", encoding="utf-8")
    with pytest.raises(lex.Malformed, match="derived"):
        lex.load(tmp_path)


def test_the_committed_store_checks_out():
    """Mirrors `test_entities.py`'s. The store may be empty; what must hold is
    that whatever is there parses."""
    assert lex.check(Path(__file__).resolve().parent.parent.parent)["ok"]
