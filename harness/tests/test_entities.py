"""The entity store: its parser, its gate, and the bar a rule has to clear.

The store is the referent of every `@ref` in the corpus and the source of the
trigger vocabulary `tei generate` applies. What is checkable about it is
mechanical — identities resolve, classes are known, a file agrees with its
directory — and what is not is `status`, which is a human's word and is why the
`proposed`/`ratified` split exists at all.

Most of these are about the failure directions. The passing case goes on passing
whatever happens; a store that silently stops refusing an ambiguous form is how
a rule starts writing links nobody sanctioned.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from harness import entities as E

REPO = Path(__file__).resolve().parent.parent.parent


def entry(root: Path, ident: str, *, status: str = "ratified",
          since: str = "1-021", triggers=(), canonical: str = "",
          extra: str = "", gloss: str = "a gloss") -> Path:
    cls, slug = ident.split(":")
    rows = "\n".join(f"| {f} | {'yes' if a else 'no'} | |" for f, a in triggers)
    p = root / "entities" / cls / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"# {ident} — {canonical or slug.title()}\n\n"
        f"- status: {status}\n- since: {since}\n{extra}"
        f"\n## triggers\n\n| form | auto | note |\n|---|---|---|\n{rows}\n"
        f"\n## gloss\n\n{gloss}\n", encoding="utf-8")
    return p


# ------------------------------------------------------------- the identity

def test_an_identity_is_class_and_slug():
    """`person:jochelson` and `source:jochelson` are the standing case: the man and
    the book he wrote, named by one string on one page."""
    assert E.split_id("person:jochelson") == ("person", "jochelson")


@pytest.mark.parametrize("bad", ["jochelson", ":jochelson", "person:", "person"])
def test_a_bare_slug_is_not_an_identity(bad):
    with pytest.raises(ValueError, match="class:slug"):
        E.split_id(bad)


def test_an_unknown_class_is_refused():
    with pytest.raises(ValueError, match="unknown class"):
        E.split_id("wizard:merlin")


def test_every_class_maps_to_a_name_type_or_to_nothing():
    """The mapping is what lets `validate` compare a `<name @type>` read off the page
    against the class of the entity it points at. A class with neither a type nor a
    declared None would fail that comparison as a KeyError."""
    from harness.validate import NAME_TYPES
    for cls, typ in E.ENTITY_CLASSES.items():
        assert typ is None or typ in NAME_TYPES, cls


# --------------------------------------------------------------- the parser

def test_a_record_parses(tmp_path):
    entry(tmp_path, "place:markova", triggers=[("Markova", True)])
    rec = E.load(tmp_path)["place:markova"]
    assert rec["class"] == "place" and rec["status"] == "ratified"
    assert rec["triggers"] == [{"form": "Markova", "auto": True, "note": ""}]


def test_the_file_is_read_as_nfd(tmp_path):
    """The store is hand-maintained and can drift between edits. A trigger held
    precomposed would fail to match a page held decomposed — a silent miss, which
    is the failure class this project is organised against."""
    p = entry(tmp_path, "person:doring", triggers=[("x", False)])
    p.write_text(p.read_text(encoding="utf-8").replace(
        "| x |", "| " + unicodedata.normalize("NFC", "Döring") + " |"),
        encoding="utf-8")
    form = E.load(tmp_path)["person:doring"]["triggers"][0]["form"]
    assert form == unicodedata.normalize("NFD", "Döring")
    assert form != unicodedata.normalize("NFC", "Döring")


def test_an_absent_store_is_empty_not_an_error(tmp_path):
    assert E.load(tmp_path) == {}


def test_since_is_required(tmp_path):
    """Every apparatus store that skipped this is now unauditable; data/toc.json is
    the standing case, and it is a logged defect rather than a choice."""
    p = entry(tmp_path, "place:markova")
    p.write_text(p.read_text(encoding="utf-8").replace("- since: 1-021\n", ""),
                 encoding="utf-8")
    with pytest.raises(E.Malformed, match="since"):
        E.load(tmp_path)


def test_a_trigger_needs_an_explicit_auto(tmp_path):
    """`auto` is the author's declaration that a form is safe out of context, so
    there is no sensible default for it — either answer is a real claim."""
    p = entry(tmp_path, "place:markova")
    p.write_text(p.read_text(encoding="utf-8").replace(
        "|---|---|---|\n", "|---|---|---|\n| Markova | maybe | |\n"),
        encoding="utf-8")
    with pytest.raises(E.Malformed, match="auto"):
        E.load(tmp_path)


# ----------------------------------------------------------------- the gate

def test_a_clean_store_checks_out(tmp_path):
    entry(tmp_path, "place:markova", triggers=[("Markova", True)])
    assert E.check(tmp_path)["ok"]


def test_the_heading_must_agree_with_the_directory(tmp_path):
    """A file's role must not live only in its directory name — the rule the
    ground-truth loss produced. Here the file says what it is and the gate compares,
    so a moved file is an error rather than a silent reclassification."""
    p = entry(tmp_path, "place:markova")
    moved = tmp_path / "entities" / "water" / "markova.md"
    moved.parent.mkdir(parents=True, exist_ok=True)
    moved.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.unlink()
    assert any("directory" in e for e in E.check(tmp_path)["errors"])


def test_a_file_outside_a_class_directory_is_named(tmp_path):
    """`glob("*/*.md")` cannot see it, so without this it would sit unread and
    unmentioned — indistinguishable from not existing."""
    (tmp_path / "entities").mkdir()
    (tmp_path / "entities" / "stray.md").write_text("# x", encoding="utf-8")
    assert any("outside a class directory" in e for e in E.check(tmp_path)["errors"])


def test_a_dangling_within_is_an_error(tmp_path):
    entry(tmp_path, "place:markova", extra="- within: place:nowhere\n")
    assert any("resolves to nothing" in e for e in E.check(tmp_path)["errors"])


def test_a_dangling_wikilink_is_an_error(tmp_path):
    """`[[class:slug]]` renders as a link, so one that resolves to nothing is a
    link that goes nowhere — and a reader should never be the one to find it."""
    entry(tmp_path, "place:markova", gloss="near [[water:nowhere]] somewhere")
    assert any("[[water:nowhere]] resolves to nothing" in e
               for e in E.check(tmp_path)["errors"])


def test_a_wikilink_in_a_trigger_note_is_checked_too(tmp_path):
    """The notes are where an author explains why a form is suggest-only, and the
    explanation is almost always "it is also that other entity"."""
    entry(tmp_path, "place:markova",
          triggers=[("Markova", False)],
          extra="", gloss="x")
    p = tmp_path / "entities" / "place" / "markova.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "| Markova | no | |", "| Markova | no | see [[person:ghost]] |"),
        encoding="utf-8")
    assert any("[[person:ghost]]" in e for e in E.check(tmp_path)["errors"])


def test_a_within_cycle_is_an_error(tmp_path):
    """A cycle would hang the geography sprint's tree walk rather than fail it,
    which is the worse of the two outcomes."""
    entry(tmp_path, "place:a", extra="- within: place:b\n")
    entry(tmp_path, "place:b", extra="- within: place:a\n")
    assert any("cycle" in e for e in E.check(tmp_path)["errors"])


def test_two_entities_may_share_a_form_and_that_is_reported_not_refused(tmp_path):
    """"Chukchee" really is the people and the language. The store's job is to say
    so, and the generator's is to ask rather than resolve it."""
    entry(tmp_path, "people:chukchee", triggers=[("Chukchee", False)])
    entry(tmp_path, "language:chukchee", triggers=[("Chukchee", False)])
    rep = E.check(tmp_path)
    assert rep["ok"]
    assert rep["collisions"][0]["claimed_by"] == "language:chukchee people:chukchee"


def test_two_entities_may_not_both_claim_a_form_unconditionally(tmp_path):
    """`auto: yes` asserts the form means this entity wherever it appears. Two such
    claims on one form are a contradiction, and one of them is wrong."""
    entry(tmp_path, "people:chukchee", triggers=[("Chukchee", True)])
    entry(tmp_path, "language:chukchee", triggers=[("Chukchee", True)])
    rep = E.check(tmp_path)
    assert not rep["ok"]
    assert any("cannot both own a form" in e for e in rep["errors"])


# -------------------------------------------------------------- the matcher

def idx(*specs):
    return {form: [{"id": i, "auto": a, "status": s} for i, a, s in claims]
            for form, claims in specs}


def test_a_trigger_matches_whole_words_only():
    i = idx(("Ana", [("place:ana", True, "ratified")]))
    assert E.match("Anadyr basin", i) == []
    assert [h["form"] for h in E.match("the Ana river", i)] == ["Ana"]


def test_a_combining_mark_is_a_word_character_here():
    """`\\w` alone is not enough on NFD text: a combining mark is not a word
    character to Python, so a plain boundary would match the first five letters of
    a Tier-1 form whose sixth is a combining diaeresis."""
    i = idx(("Do", [("person:do", True, "ratified")]))
    assert E.match("a D" + unicodedata.normalize("NFD", "ö") + "ring b", i) == []
    assert len(E.match("a Do b", i)) == 1


def test_the_longest_form_wins():
    """Otherwise the bare "Chukchee" would take "Chukchee Peninsula" apart, and the
    unambiguous multi-word triggers — the only ones safe to link — would be the ones
    that never fired."""
    i = idx(("Chukchee", [("people:chukchee", False, "ratified")]),
            ("Chukchee Peninsula", [("place:cp", True, "ratified")]))
    assert [h["form"] for h in E.match("on the Chukchee Peninsula", i)] \
        == ["Chukchee Peninsula"]


def test_a_form_broken_across_a_printed_line_still_matches():
    """`1-021` sets "the Jesup North / Pacific Expedition" across two lines. The
    generated page keeps the printed breaks, so without this the longest and most
    reliable triggers would be exactly the ones that failed at a line end."""
    i = idx(("Jesup North Pacific Expedition",
             [("event:jesup", True, "ratified")]))
    hits = E.match("part of the Jesup North\nPacific Expedition. The", i)
    assert [h["form"] for h in hits] == ["Jesup North Pacific Expedition"]
    assert "\n" in hits[0]["text"]


def test_matching_is_case_sensitive():
    i = idx(("Boas", [("person:boas", True, "ratified")]))
    assert E.match("the boas constrictor", i) == []


# --------------------------------------------------- what a rule may link

def test_a_form_two_entities_claim_is_never_auto_linked():
    """Ambiguous **by construction**, whatever either file says: no author can see
    the other's claim, so the rule reads the whole store and not the entry."""
    i = idx(("Chukchee", [("people:chukchee", True, "ratified"),
                          ("language:chukchee", True, "ratified")]))
    assert E.auto_forms(i) == {}


def test_a_suggest_only_form_is_never_auto_linked():
    i = idx(("Jesup", [("event:jesup", False, "ratified")]))
    assert E.auto_forms(i) == {}


def test_a_proposed_entity_is_never_auto_linked():
    """The whole safety property behind letting a collator propose entries: a
    proposal is inert, and `ratify` is the human act that makes it reachable."""
    i = idx(("Markova", [("place:markova", True, "proposed")]))
    assert E.auto_forms(i) == {}


def test_the_three_conditions_together_are_what_licenses_a_link():
    i = idx(("Markova", [("place:markova", True, "ratified")]))
    assert E.auto_forms(i) == {"Markova": "place:markova"}


# ------------------------------------------------------------ the live store

def test_the_committed_store_checks_out():
    assert E.check(REPO)["ok"]
