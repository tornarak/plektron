"""`lexicon new` and `lexicon ratify` — the two verbs that write `edition/lexicon/`.

`test_lexicon_store.py` covers the parser and the gate; nothing covered the
writers, which is the half that can put something on disk that a human did not
key. Both take the `--commit` discipline, and both are the only mechanical route
into a **tracked** store, so what they write is what a reviewer will read as
authored.

The argument objects are spelled out rather than driven through click, as
`test_entities.py`'s `_NewArgs` does: a test then names exactly the flags it is
exercising, and a flag it does not name cannot quietly change under it.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from harness import lexicon as lex
from harness.cli import _lexicon as L
from harness.tests.test_lexicon_store import FORM, entry


class _NewArgs:
    """`run_new`'s argument object."""

    def __init__(self, root, form, slug="", see="", commit=True):
        self.root, self.form = root, form
        self.slug, self.see, self.commit = slug, see, commit
        self.json = self.toon = self.pager = False


class _RatifyArgs:
    """`run_ratify`'s argument object. `forms` is plural, per the convention."""

    def __init__(self, root, forms, commit=True):
        self.root, self.forms, self.commit = root, list(forms), commit
        self.json = self.toon = self.pager = False


def _new(tmp_path: Path, form: str, **kw) -> int:
    return L.run_new(_NewArgs(tmp_path, form, **kw))


def _ratify(tmp_path: Path, forms, **kw) -> int:
    return L.run_ratify(_RatifyArgs(tmp_path, forms, **kw))


# --- report by default --------------------------------------------------------

def test_a_reported_new_writes_nothing(tmp_path):
    """"Report by default, `--commit` writes" has to hold on the disk and not
    only in the output — the property `test_relink.py` pins for `entity ratify`.
    A scaffold is the cheapest thing in the repo to run by accident, and a file
    left behind by a dry run is indistinguishable from one an editor minted."""
    _new(tmp_path, FORM, commit=False)
    assert not lex.path_for(lex.suggest_slug(FORM), tmp_path).exists()
    assert not lex.lex_dir(tmp_path).exists(), "not even the directory"
    assert lex.load(tmp_path) == {}


def test_a_reported_ratify_writes_nothing(tmp_path):
    """Ratification is *the human act* — it means somebody read the note against
    the pages the form occurs on. A dry run that moved a status would be the one
    kind of forgery this store exists to make impossible."""
    p = entry(tmp_path, FORM)
    before = p.read_text(encoding="utf-8")
    assert _ratify(tmp_path, [FORM], commit=False) == 0
    assert p.read_text(encoding="utf-8") == before
    assert lex.load(tmp_path)[lex.norm_form(FORM)]["status"] == "proposed"


# --- the form reaching the file ----------------------------------------------

def test_the_form_is_nfd_in_the_file_and_not_only_in_the_report(tmp_path):
    """`run_new` normalizes, but what a later run reads is the file, and the
    heading *is* the identity. A precomposed heading against an NFD store keys an
    entry nothing can address — `entities`' alias fault (`test_entities.py`'s
    "normalized to NFD on the way in") in the store where the identity itself is
    a native form, so the miss is total rather than partial."""
    composed = unicodedata.normalize("NFC", "Nordenskiöld")
    decomposed = unicodedata.normalize("NFD", "Nordenskiöld")
    assert composed != decomposed, "the fixture must actually differ"

    _new(tmp_path, composed, slug="nordenskiold")
    text = lex.path_for("nordenskiold", tmp_path).read_text(encoding="utf-8")
    assert decomposed in text
    assert composed not in text
    assert decomposed in lex.load(tmp_path)


def test_a_slug_is_suggested_from_the_key_and_the_flag_overrides_it(tmp_path):
    """The default is `suggest_slug`, not the handle key itself: the key keeps
    case and emits colons, and both are what a filename must not depend on. The
    flag exists because the suggestion collides — 23 pairs over the corpus differ
    only in case — so an author must be able to name the file."""
    _new(tmp_path, FORM)
    assert lex.path_for(lex.suggest_slug(FORM), tmp_path).exists()
    _new(tmp_path, "Aiˊwan", slug="aiwan-upper")
    assert lex.path_for("aiwan-upper", tmp_path).exists()


def test_an_empty_form_is_refused(tmp_path):
    """The identity is the form; there is no other key to fall back on, so a
    blank one is a file that can never be resolved rather than a defaulted one."""
    with pytest.raises(ValueError, match="empty"):
        _new(tmp_path, "   ")
    assert lex.load(tmp_path) == {}


# --- `--see`, and what the pre-flight parse can and cannot catch --------------

def test_a_see_cannot_forge_a_second_field(tmp_path):
    """`--see` is interpolated into the template, so it is the one channel by
    which a caller writes a *line* rather than a value. It cannot: `norm_form`
    collapses every kind of whitespace, so a smuggled second field arrives as one
    long form on the `see:` line and the entry it produces still says `proposed`.

    This is why the pre-flight `lex.parse` (`_lexicon.py`, before the write)
    never actually fires — see the note on the next test. It is worth pinning
    from the other side: the reason nothing gets through is the normalization,
    and if that ever stopped collapsing newlines this would break loudly."""
    _new(tmp_path, FORM, slug="k", see="Aiˊwan\n- status: ratified")
    text = lex.path_for("k", tmp_path).read_text(encoding="utf-8")
    assert [ln for ln in text.splitlines() if ln.startswith("- status:")] \
        == ["- status: proposed"], "the injection is not on a line of its own"
    rec = lex.parse(text)
    assert rec["status"] == "proposed"
    assert "\n" not in rec["see"]


def test_a_dangling_see_is_written_and_left_to_the_gate(tmp_path):
    """The pre-flight parse is structural only, and `see:` resolution is not a
    structural property of one file — it is a property of the store, which is
    `check`'s question. So `new` accepts a forward reference (the pointed-at
    entry may be minted next) and the gate is what refuses a store where it never
    arrived. Recorded here because the alternative reading — that `new` validates
    the pointer — would leave a reviewer trusting a check that is not run."""
    _new(tmp_path, FORM, slug="k", see="Nobody")
    assert lex.path_for("k", tmp_path).exists()
    got = lex.check(tmp_path)
    assert not got["ok"]
    assert any("resolves to no entry" in e for e in got["errors"])


def test_nothing_is_written_when_the_scaffold_would_not_parse(tmp_path, monkeypatch):
    """The ordering the pre-flight exists for: **a bad scaffold fails as a
    message, never as a file the next `check` has to explain.** No real `--see`
    can currently reach it (the test above says why), so the failure is injected
    at the parser — the point under test is that the write is downstream of the
    parse and not racing it."""
    def refuse(text, where=""):
        raise lex.Malformed(f"{where}: injected")

    monkeypatch.setattr(lex, "parse", refuse)
    p = lex.path_for("k", tmp_path)
    with pytest.raises(lex.Malformed, match="injected"):
        _new(tmp_path, FORM, slug="k")
    assert not p.exists()


# --- round trip ---------------------------------------------------------------

def test_a_committed_scaffold_passes_the_store_gate(tmp_path):
    """The whole point of a scaffold: what the verb writes is what `lexicon
    check` accepts, so a minted entry is never a defect an editor has to repair
    before writing the note it was minted for."""
    assert _new(tmp_path, FORM) == 0
    got = lex.check(tmp_path)
    assert got["ok"], got["errors"]
    assert got["entries"] == 1 and got["proposed"] == 1

    rec = lex.load(tmp_path)[lex.norm_form(FORM)]
    assert rec["status"] == "proposed"
    assert rec["note"] == "(unwritten)"
    assert rec["see"] == ""


def test_scaffold_then_ratify_round_trips(tmp_path):
    """Both writers over one file, in the order a real entry sees them, ending at
    the gate — the only assertion that says the two verbs agree about the file
    format they share."""
    _new(tmp_path, FORM, slug="k", see="")
    assert _ratify(tmp_path, [FORM]) == 0
    assert lex.load(tmp_path)[lex.norm_form(FORM)]["status"] == "ratified"
    assert lex.check(tmp_path)["ok"]
    assert lex.check(tmp_path)["proposed"] == 0


def test_ratify_resolves_a_composed_form_on_the_command_line(tmp_path):
    """`_resolve_forms` normalizes what was typed, so a form pasted out of a
    terminal that composed it still names its entry. Without this the verb would
    report "no such entry" for a form plainly visible in the store."""
    entry(tmp_path, unicodedata.normalize("NFD", "Nordenskiöld"), slug="n")
    _ratify(tmp_path, [unicodedata.normalize("NFC", "Nordenskiöld")])
    assert lex.load(tmp_path)[unicodedata.normalize("NFD", "Nordenskiöld")][
        "status"] == "ratified"


def test_an_unknown_form_is_refused_before_any_of_the_batch_is_written(tmp_path):
    """Refused up front, so a batch is all-or-nothing: a typo in the third form
    must not leave the first two ratified and the run reported as failed."""
    entry(tmp_path, FORM, slug="k")
    before = lex.path_for("k", tmp_path).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="no such lexicon entry"):
        _ratify(tmp_path, [FORM, "Nobody"])
    assert lex.path_for("k", tmp_path).read_text(encoding="utf-8") == before


# --- not minting over something that exists -----------------------------------

def test_an_existing_file_is_never_overwritten(tmp_path):
    """The store is tracked and an entry is an editor's note nothing can rebuild.
    `new` reports the collision and exits 1 rather than writing through it, and
    the slug is authored precisely because collisions are expected."""
    p = entry(tmp_path, FORM, slug="k", note="a note nobody can regenerate")
    before = p.read_text(encoding="utf-8")
    assert _new(tmp_path, "Something Else", slug="k") == 1
    assert p.read_text(encoding="utf-8") == before


# --- ratify, and the one-shot replacement it is built on ----------------------

def test_ratifying_a_ratified_entry_is_a_no_op_row_and_not_a_rewrite(tmp_path):
    """Ratification is idempotent by report, not by re-application: the row says
    `was: ratified, wrote: false` and the file is not touched at all. It matters
    that it is the *file* that is untouched — a rewrite that happened to produce
    the same status would still be this verb writing over an editor's file on a
    run that had nothing to do, and `run_ratify`'s replacement would find no
    `- status: proposed` line and raise."""
    p = entry(tmp_path, FORM, slug="k", status="ratified")
    before = p.read_text(encoding="utf-8")
    mtime = p.stat().st_mtime_ns
    assert _ratify(tmp_path, [FORM]) == 0
    assert p.read_text(encoding="utf-8") == before
    assert p.stat().st_mtime_ns == mtime


def test_ratify_changes_the_field_and_not_a_note_that_quotes_it(tmp_path):
    """The replacement is a literal `str.replace(..., 1)` over the whole file,
    and an editor's note is free prose that may perfectly well quote the status
    line it is discussing — this store's notes are *about* the apparatus. The
    count of 1 is load-bearing: it must land on the field, which the template
    puts above the note, and leave the prose exactly as keyed."""
    quoted = "the card read `- status: proposed` until 1904"
    p = entry(tmp_path, FORM, slug="k", note=quoted)
    _ratify(tmp_path, [FORM])
    text = p.read_text(encoding="utf-8")
    assert "- status: ratified\n" in text
    assert quoted in text, "the note is prose and is not the field"
    assert lex.load(tmp_path)[lex.norm_form(FORM)]["status"] == "ratified"


def test_ratify_is_not_fooled_by_a_field_the_parser_accepts_but_the_literal_misses(
        tmp_path):
    """The adversarial half of the test above, and the one a literal `.replace`
    did not survive. `_FIELD` is `^-\\s+([a-z]+):\\s*(.*?)\\s*$`, so
    `- status:proposed` is a legal, parsed, `proposed` entry — and it is not the
    string `run_ratify` used to search for. The first literal match was then
    whatever the *note* said: the verb edited an editor's prose, left the status
    `proposed`, and reported `now: ratified, wrote: true`.

    That last part is what made it a bug and not a shrug — the run's own report
    asserted a ratification that had not happened, with no error signal
    anywhere. `lexicon.set_status` now finds the field with `_FIELD` itself, in
    the same `head` region `parse` reads, so the writer and the reader cannot
    disagree about what a field line is."""
    p = lex.lex_dir(tmp_path) / "k.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    quoted = "keyed as `- status: proposed` in the first pass"
    p.write_text(f"# {FORM}\n\n- status:proposed\n\n## editor's note\n\n"
                 f"{quoted}\n", encoding="utf-8")
    assert lex.load(tmp_path)[lex.norm_form(FORM)]["status"] == "proposed"

    _ratify(tmp_path, [FORM])
    assert lex.load(tmp_path)[lex.norm_form(FORM)]["status"] == "ratified"
    assert quoted in p.read_text(encoding="utf-8")
