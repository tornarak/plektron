"""The entity store: its parser, its gate, and the bar a rule has to clear.

The store is the referent of every `@ref` in the corpus and the source of the
alias vocabulary `tei generate` applies. What is checkable about it is
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
          aliases=(), canonical: str = "",
          extra: str = "", gloss: str = "a gloss") -> Path:
    """One store file. An alias is `(form, auto)` or `(form, auto, lang)` — the
    two-tuple stays legal because the language is optional in the store too, and
    a helper that forced it would make every caller state a fact the schema
    calls unstated.

    `auto` is a bool for the two states that predate `once`, or the column's own
    string where a caller means the third."""
    cls, slug = ident.split(":")
    rows = "\n".join(f"| {a[0]} | {a[2] if len(a) > 2 else ''} | "
                     f"{a[1] if isinstance(a[1], str) else ('yes' if a[1] else 'no')}"
                     f" | |" for a in aliases)
    p = root / "edition" / "entities" / cls / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"# {ident} — {canonical or slug.title()}\n\n"
        f"- status: {status}\n{extra}"
        f"\n## aliases\n\n| form | lang | auto | note |\n|---|---|---|---|\n"
        f"{rows}\n\n## gloss\n\n{gloss}\n", encoding="utf-8")
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
    entry(tmp_path, "place:markova", aliases=[("Markova", True)])
    rec = E.load(tmp_path)["place:markova"]
    assert rec["class"] == "place" and rec["status"] == "ratified"
    assert rec["aliases"] == [
        {"form": "Markova", "lang": "", "auto": True, "scope": "all",
         "note": ""}]


def test_the_file_is_read_as_nfd(tmp_path):
    """The store is hand-maintained and can drift between edits. An alias held
    precomposed would fail to match a page held decomposed — a silent miss, which
    is the failure class this project is organised against."""
    p = entry(tmp_path, "person:doring", aliases=[("x", False)])
    p.write_text(p.read_text(encoding="utf-8").replace(
        "| x |", "| " + unicodedata.normalize("NFC", "Döring") + " |"),
        encoding="utf-8")
    form = E.load(tmp_path)["person:doring"]["aliases"][0]["form"]
    assert form == unicodedata.normalize("NFD", "Döring")
    assert form != unicodedata.normalize("NFC", "Döring")


def test_an_absent_store_is_empty_not_an_error(tmp_path):
    assert E.load(tmp_path) == {}


def test_there_is_no_since_field(tmp_path):
    """It was required, as the page whose reading prompted the entry, on the
    argument that an unauditable apparatus store is the `edition/toc.json` defect.
    The argument held and the answer got better: the card derives *every* page
    that mentions the entity. **A `since:` is satisfied by typing a plausible
    ref and an empty mentions list is not**, so it was the weaker witness of the
    two while keeping out entries the book plainly contains whose attesting page
    is among the 558 not yet transcribed. Left in a file it is inert — no key,
    no gate, nothing rendering it."""
    p = entry(tmp_path, "place:markova")
    p.write_text(p.read_text(encoding="utf-8").replace(
        "- status: ratified\n", "- status: ratified\n- since: 1-021\n"),
        encoding="utf-8")
    assert "since" not in E.load(tmp_path)["place:markova"]


def test_an_alias_needs_an_explicit_auto(tmp_path):
    """`auto` is the author's declaration that a form is safe out of context, so
    there is no sensible default for it — either answer is a real claim."""
    p = entry(tmp_path, "place:markova")
    p.write_text(p.read_text(encoding="utf-8").replace(
        "|---|---|---|---|\n", "|---|---|---|---|\n| Markova | | maybe | |\n"),
        encoding="utf-8")
    with pytest.raises(E.Malformed, match="auto"):
        E.load(tmp_path)


# ---------------------------------------------------- the language column

def test_the_old_section_name_is_refused_and_names_the_rename(tmp_path):
    """No compatibility shim. Every file in the store spelled the section and its
    header row identically, so accepting both would put one schema in two
    spellings — which is the defect the column was added to remove, one level up.
    The message has to name the rename, or the author of a file written from
    memory gets "no aliases" and a store that silently links nothing."""
    p = entry(tmp_path, "place:markova", aliases=[("Markova", True)])
    p.write_text(p.read_text(encoding="utf-8")
                 .replace("## aliases", "## triggers"), encoding="utf-8")
    with pytest.raises(E.Malformed, match="`## triggers` is now `## aliases`"):
        E.load(tmp_path)


def test_a_declared_language_is_carried(tmp_path):
    entry(tmp_path, "place:uelen", aliases=[("Uweˊlen", True, "ckt")])
    assert E.load(tmp_path)["place:uelen"]["aliases"][0]["lang"] == "ckt"


def test_a_blank_language_is_unstated_and_not_an_error(tmp_path):
    """Most of the store is blank — 128 of 141 rows are the book's own English,
    where saying so adds nothing. Requiring the column would have made an
    editorial pass out of a schema change."""
    entry(tmp_path, "place:markova", aliases=[("Markova", True)])
    assert E.load(tmp_path)["place:markova"]["aliases"][0]["lang"] == ""
    assert E.check(tmp_path)["ok"]


def test_a_language_outside_the_vocabulary_is_an_error(tmp_path):
    """A gap and a typo want opposite treatment. `rus` is the case that matters:
    it is what the notes used to say, it is a real ISO code, and it is not the
    string a page writes in `xml:lang` — so accepting it would let the store and
    the corpus disagree about one language under two spellings."""
    entry(tmp_path, "people:chukchee", aliases=[("Чукча", True, "rus")])
    with pytest.raises(E.Malformed, match="unknown language 'rus'"):
        E.load(tmp_path)


def test_untagged_aliases_are_counted_and_never_gate(tmp_path):
    """A worklist. "Every foreign name is in the table, tagged" is a standing
    editorial job, and a gate on it would be answered by deleting the alias."""
    entry(tmp_path, "place:uelen",
          aliases=[("Uelen", True), ("Uweˊlen", True, "ckt"), ("Uˊlak", True)])
    got = E.check(tmp_path)
    assert got["aliases_untagged"] == 2
    assert got["ok"]


def test_the_tier1_codes_are_the_language_tables_own(tmp_path):
    """`validate.TIER1` and the lexicon index's names were two hand-kept copies
    of one set, and the alias column would have made a third. Derived, so a code
    cannot be Tier-1 in one file and not in another."""
    from harness import langs, validate
    assert validate.TIER1 is langs.TIER1
    assert set(langs.TIER1_NAMES) == set(langs.TIER1) <= langs.ALIAS_LANGS


# ----------------------------------------------------------------- the gate

def test_a_clean_store_checks_out(tmp_path):
    entry(tmp_path, "place:markova", aliases=[("Markova", True)])
    assert E.check(tmp_path)["ok"]


def test_the_heading_must_agree_with_the_directory(tmp_path):
    """A file's role must not live only in its directory name — the rule the
    ground-truth loss produced. Here the file says what it is and the gate compares,
    so a moved file is an error rather than a silent reclassification."""
    p = entry(tmp_path, "place:markova")
    moved = tmp_path / "edition" / "entities" / "water" / "markova.md"
    moved.parent.mkdir(parents=True, exist_ok=True)
    moved.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.unlink()
    assert any("directory" in e for e in E.check(tmp_path)["errors"])


def test_a_file_outside_a_class_directory_is_named(tmp_path):
    """`glob("*/*.md")` cannot see it, so without this it would sit unread and
    unmentioned — indistinguishable from not existing."""
    (tmp_path / "edition" / "entities").mkdir(parents=True)
    (tmp_path / "edition" / "entities" / "stray.md").write_text("# x", encoding="utf-8")
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


def test_a_wikilink_in_an_alias_note_is_checked_too(tmp_path):
    """The notes are where an author explains why a form is suggest-only, and the
    explanation is almost always "it is also that other entity"."""
    entry(tmp_path, "place:markova",
          aliases=[("Markova", False)],
          extra="", gloss="x")
    p = tmp_path / "edition" / "entities" / "place" / "markova.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "| Markova |  | no | |", "| Markova | | no | see [[person:ghost]] |"),
        encoding="utf-8")
    assert any("[[person:ghost]]" in e for e in E.check(tmp_path)["errors"])


def test_a_within_cycle_is_an_error(tmp_path):
    """A cycle would hang the geography sprint's tree walk rather than fail it,
    which is the worse of the two outcomes."""
    entry(tmp_path, "place:a", extra="- within: place:b\n")
    entry(tmp_path, "place:b", extra="- within: place:a\n")
    assert any("cycle" in e for e in E.check(tmp_path)["errors"])


def test_two_entities_may_share_a_form_and_that_is_reported_not_refused(tmp_path):
    """"Eskimo" really is three peoples in this book. The store's job is to say
    so, and the generator's is to ask rather than resolve it."""
    entry(tmp_path, "people:eskimo", aliases=[("Eskimo", False)])
    entry(tmp_path, "people:yupik", aliases=[("Eskimo", False)])
    rep = E.check(tmp_path)
    assert rep["ok"]
    assert rep["collisions"][0]["claimed_by"] == "people:eskimo people:yupik"


def test_two_entities_may_not_both_claim_a_form_unconditionally(tmp_path):
    """`auto: yes` asserts the form means this entity wherever it appears. Two such
    claims on one form are a contradiction, and one of them is wrong."""
    entry(tmp_path, "people:eskimo", aliases=[("Eskimo", True)])
    entry(tmp_path, "people:yupik", aliases=[("Eskimo", True)])
    rep = E.check(tmp_path)
    assert not rep["ok"]
    assert any("cannot both own a form" in e for e in rep["errors"])


# -------------------------------------------------------------- the matcher

def idx(*specs):
    """An alias index by hand. A claim is `(id, auto, status)` or, where the
    scope matters, `(id, "once"|"yes"|"no", status)` — the string spelling is the
    alias column's own, so a test that means `once` says the word the store does."""
    def claim(i, a, s):
        scope = a if isinstance(a, str) else ("all" if a else "")
        scope = {"yes": "all", "once": "first", "no": ""}.get(scope, scope)
        return {"id": i, "auto": bool(scope), "scope": scope, "status": s}
    return {form: [claim(*c) for c in claims] for form, claims in specs}


def test_an_alias_matches_whole_words_only():
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


def test_a_footnote_marker_does_not_swallow_the_name_in_front_of_it():
    """`Ciˊṛluk⁶` on 1-051. Python's `\\w` matches a superscript digit, so the
    right boundary failed and `match` returned nothing — which cost the page both
    halves at once: no link, and no candidate comment either, so nothing anywhere
    recorded that a name had been passed over. `keying_spec.md` §2.10 makes this
    mechanical rather than a reading: in this corpus a superscript digit is a
    footnote marker and is never anything else.

    Measured at the time: 69 lines set a word against a marker, ~20 of those
    words being entity forms — a footnote is what an author hangs on the names
    that needed a source, so the miss landed on exactly the wrong words."""
    i = idx(("Nelson", [("person:nelson", True, "ratified")]))
    for marker in "¹²³⁴⁵⁶⁷⁸⁹⁰":
        got = E.match(f"as Nelson{marker} reports", i)
        assert [h["form"] for h in got] == ["Nelson"], marker
        # The marker is apparatus and stays outside the span.
        assert got[0]["text"] == "Nelson"
    # An ordinary digit is not a marker (§2.10) and still ends the word.
    assert E.match("as Nelson2 reports", i) == []


def test_the_longest_form_wins():
    """Otherwise the bare "Chukchee" would take "Chukchee Peninsula" apart, and the
    unambiguous multi-word aliases — the only ones safe to link — would be the ones
    that never fired."""
    i = idx(("Chukchee", [("people:chukchee", False, "ratified")]),
            ("Chukchee Peninsula", [("place:cp", True, "ratified")]))
    assert [h["form"] for h in E.match("on the Chukchee Peninsula", i)] \
        == ["Chukchee Peninsula"]


def test_a_form_broken_across_a_printed_line_still_matches():
    """`1-021` sets "the Jesup North / Pacific Expedition" across two lines. The
    generated page keeps the printed breaks, so without this the longest and most
    reliable aliases would be exactly the ones that failed at a line end."""
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
    i = idx(("Eskimo", [("people:eskimo", True, "ratified"),
                        ("people:yupik", True, "ratified")]))
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


# --------------------------------------------------------- `auto: once`

def test_once_parses_as_a_licence_with_a_narrower_scope(tmp_path):
    """`auto` stays the boolean "a rule may link this at all" and the scope is a
    second key. Eight call sites test `claim["auto"]` for truthiness; a
    tri-valued string there would make `"no"` true in all eight silently."""
    entry(tmp_path, "people:chukchi", aliases=[("Chukchee", "once")])
    t = E.load(tmp_path)["people:chukchi"]["aliases"][0]
    assert t["auto"] is True and t["scope"] == "first"


def test_once_licenses_a_link_exactly_as_yes_does():
    """The two differ in how many of a page's occurrences take the link, never in
    which entity the form resolves to — which is why the scope is `rule_links`'
    business and not this function's."""
    i = idx(("Chukchee", [("people:chukchi", "once", "ratified")]))
    assert E.auto_forms(i) == {"Chukchee": "people:chukchi"}


def test_the_auto_column_offers_all_three_when_it_refuses_one(tmp_path):
    """A message naming two of three states is how an author learns the third does
    not exist."""
    p = entry(tmp_path, "place:markova")
    p.write_text(p.read_text(encoding="utf-8").replace(
        "|---|---|---|---|\n", "|---|---|---|---|\n| Markova | | maybe | |\n"),
        encoding="utf-8")
    with pytest.raises(E.Malformed, match="`yes`, `once` or `no`"):
        E.load(tmp_path)


def test_once_collides_with_a_second_claim_exactly_as_yes_does(tmp_path):
    """`once` narrows how many links a page gets, not which entity a form means, so
    it contests a form as fully as `yes`. A gate that let it through would license
    a rule to link a string that is genuinely ambiguous — just less often."""
    entry(tmp_path, "people:eskimo", aliases=[("Eskimo", "once")])
    entry(tmp_path, "people:yupik", aliases=[("Eskimo", "yes")])
    errs = E.check(tmp_path)["errors"]
    assert any("rule-linked for" in e and "Eskimo" in e for e in errs)


def test_rule_links_reduces_a_once_form_to_the_pages_first_occurrence():
    i = idx(("Chukchee", [("people:chukchi", "once", "ratified")]))
    autos = E.auto_forms(i)
    hits = E.match("The Chukchee say. A Chukchee man. The Chukchee again.", i)
    assert len(hits) == 3
    kept = E.rule_links(hits, autos)
    assert [h["start"] for h in kept] == [hits[0]["start"]]


def test_once_is_spent_per_form_and_not_per_entity():
    """The name reads the other way, so this is worth pinning. The alias table is
    keyed on forms and `once` is a property of a row: a page setting both
    "Chukchee" and "Chukchee tribe" links each, which is right on `1-031`, where
    Bogoras enumerates the people's names in five languages. Per entity would
    also make a row's meaning depend on its neighbours."""
    i = idx(("Chukchee", [("people:chukchi", "once", "ratified")]),
            ("Chukchee tribe", [("people:chukchi", "once", "ratified")]))
    autos, seen = E.auto_forms(i), set()
    kept = E.rule_links(E.match("The Chukchee tribe, and a Chukchee man.", i),
                        autos, seen)
    assert sorted(h["form"] for h in kept) == ["Chukchee", "Chukchee tribe"]


def test_rule_links_passes_a_yes_form_through_whole():
    i = idx(("Chukchee", [("people:chukchi", True, "ratified")]))
    hits = E.match("The Chukchee say. A Chukchee man.", i)
    assert len(E.rule_links(hits, E.auto_forms(i))) == 2


def test_the_once_count_is_the_callers_and_spans_the_whole_page():
    """`generate` marks up one block at a time, so the set has to outlive the call
    that spends it — a page whose second paragraph re-linked every ethnonym would
    be `once` per paragraph, which is not a convention anyone reads by."""
    i = idx(("Chukchee", [("people:chukchi", "once", "ratified")]))
    autos, seen = E.auto_forms(i), set()
    first = E.rule_links(E.match("The Chukchee say.", i), autos, seen)
    second = E.rule_links(E.match("The Chukchee again.", i), autos, seen)
    assert len(first) == 1 and second == []


# --------------------------------------------------- setting a field in place

def test_a_field_that_exists_is_replaced_where_it_stands():
    """In place, because a field that moved on every edit would make every diff
    of an entity file a reordering with a change somewhere inside it."""
    from harness.cli._entity import _set_field

    text = ("# place:x — X\n\n- status: ratified\n"
            "- within: place:y\n- geo: 1.0 2.0\n- link: wikidata:Q1\n\n"
            "## gloss\n\nx\n")
    got = _set_field(text, "geo", "3.0 4.0")
    assert "- geo: 3.0 4.0\n- link:" in got
    assert got.count("- geo:") == 1


def test_a_field_that_is_missing_is_inserted_where_the_scaffold_puts_it():
    """`entity new`'s order, so a file a human later reads is not visibly
    divided into what was typed and what a command set."""
    from harness.cli._entity import FIELD_ORDER, _set_field

    text = ("# place:x — X\n\n- status: ratified\n"
            "- link: wikidata:Q1\n\n## gloss\n\nx\n")
    got = _set_field(text, "geo", "watershed:anadyr")
    fields = [line[2:].split(":")[0] for line in got.splitlines()
              if line.startswith("- ")]
    assert fields == ["status", "geo", "link"]
    assert fields == sorted(fields, key=FIELD_ORDER.index)


def test_a_field_is_never_written_into_the_gloss():
    """`- foo: bar` below a `##` is prose, and the parser already draws that
    line the same way."""
    from harness.cli._entity import _set_field

    text = ("# place:x — X\n\n- status: ratified\n- since: 1-021\n\n"
            "## gloss\n\n- authority: this is prose\n")
    got = _set_field(text, "authority", "k")
    head, _, gloss = got.partition("## gloss")
    assert "- authority: k" in head
    assert "- authority: this is prose" in gloss


def test_a_set_field_round_trips_through_the_parser(tmp_path):
    """The guarantee `locate` rests on: it re-parses before it writes, so a bad
    value fails as a message and not as a file."""
    from harness.cli._entity import _set_field, _set_lines

    p = entry(tmp_path, "place:x", extra="- within: place:y\n")
    base = p.read_text(encoding="utf-8")
    assert E.geo_points(E.parse(_set_field(base, "geo", "66.0 -170.0"))) \
        == [(66.0, -170.0)]

    # `_set_lines` is the repeatable sibling, and the reason it has to be one:
    # `_set_field` replaces a single line, so on a union it would overwrite the
    # first member and leave the rest.
    got = _set_lines(base, "geo", ["watershed:anadyr", "marine:chaun-bay"])
    assert E.geo_shapes(E.parse(got)) == ["watershed:anadyr", "marine:chaun-bay"]
    assert E.geo_shapes(E.parse(_set_lines(got, "geo", ["marine:chaun-bay"]))) \
        == ["marine:chaun-bay"], "it replaces the run rather than appending"

    # And the guarantee working: a member that is neither two degrees nor a
    # `kind:slug` fails as a message, so `locate` reports it instead of writing
    # it. **The rule this used to test is gone with the field it policed** — a
    # record carrying a point beside a shape was refused while `geo:` and
    # `area:` were two fields that could only disagree; with one field of
    # members they are a union, and `extent_of` reads both.
    with pytest.raises(E.Malformed, match="three things"):
        E.parse(_set_field(base, "geo", "somewhere near the river"))


# ---------------------------------------------------------------- renaming

class _Args:
    """`run_rename`'s argument object. The CLI builds one out of click; here it
    is spelled out, so a test names exactly the flags it is exercising."""

    def __init__(self, root, old, new, canonical="", commit=True):
        self.root, self.old, self.new = root, old, new
        self.canonical, self.commit = canonical, commit
        self.json = self.toon = self.pager = False


def _rename(tmp_path, old, new, **kw):
    from harness.cli._entity import run_rename
    return run_rename(_Args(tmp_path, old, new, **kw))


def test_a_rename_repoints_within_and_wikilinks(tmp_path):
    """The three ways one entry points at another, and `entity check` gates all
    of them — so a rename that missed one would fail the gate rather than go
    quiet.

    **A `geo:` member is the third, and it was nearly the one that got away.**
    The substitution matched `within|part-of` and had done since there were only
    two fields to point with; a member naming an entity is a fourth reference in
    the same shape, and a missed one dangles. It is safe to rewrite without
    asking what kind of member it is, because neither of the other two kinds can
    collide with an identity: a point is two numbers, and a shape kind may never
    be an entity class.

    The `within:` pair is geographical on both ends, which is now the only thing
    `within:` may be — a village filed inside a *people* was the spelling this
    fixture used, and the spelling the gate exists to refuse."""
    entry(tmp_path, "people:chukchee", aliases=[("Chukchee tribe", True)])
    entry(tmp_path, "land:chukotka-old")
    entry(tmp_path, "place:markova", extra="- within: land:chukotka-old\n",
          gloss="home of the [[people:chukchee]]")
    entry(tmp_path, "people:reindeer", extra="- geo: people:chukchee\n")
    _rename(tmp_path, "people:chukchee", "people:chukchi")

    store = E.load(tmp_path)
    assert "people:chukchi" in store and "people:chukchee" not in store
    assert not (tmp_path / "edition" / "entities" / "people" / "chukchee.md").exists()
    assert "[[people:chukchi]]" in store["place:markova"]["gloss"]
    assert E.geo_refs(store["people:reindeer"]) == ["people:chukchi"]
    assert E.check(tmp_path)["ok"]

    _rename(tmp_path, "land:chukotka-old", "land:chukotka")
    assert E.load(tmp_path)["place:markova"]["within"] == "land:chukotka"
    assert E.check(tmp_path)["ok"]


def test_a_retitled_entry_keeps_the_book_spelling_as_an_alias(tmp_path):
    """Not politeness. `detectors.entity_forms` splits canonicals into the
    corpus's proper-noun dictionary, so a rename that only moved the heading
    would take "Chukchee" out of the dictionary and start reporting it as a
    transcription candidate on every page that prints it."""
    entry(tmp_path, "people:chukchee", canonical="Chukchee",
          aliases=[("Chukchee tribe", True)])
    _rename(tmp_path, "people:chukchee", "people:chukchi", canonical="Chukchi")

    rec = E.load(tmp_path)["people:chukchi"]
    assert rec["canonical"] == "Chukchi"
    assert "Chukchee" in {t["form"] for t in rec["aliases"]}


def test_the_old_canonical_is_not_filed_twice(tmp_path):
    """`parse` refuses a form listed twice in one file, so the naive append
    would break the file the verb had just written."""
    entry(tmp_path, "people:chukchee", canonical="Chukchee",
          aliases=[("Chukchee", False)])
    _rename(tmp_path, "people:chukchee", "people:chukchi", canonical="Chukchi")

    forms = [t["form"] for t in E.load(tmp_path)["people:chukchi"]["aliases"]]
    assert forms.count("Chukchee") == 1


def test_a_rename_carries_a_committed_page_with_it(tmp_path):
    """This used to refuse, on "a rule may not rewrite a page a human signed" —
    which conflated two things. The rule protects what a page *asserts*, and an
    `@ref` asserts "this string names that entity": a rename changes neither
    side of it, only the spelling of the pointer between them. Leaving it behind
    is what breaks the assertion, since the ref then resolves to nothing —
    which `validate` calls worse than no ref at all.

    `mz/tei/` is still named and not touched: it is derived, `tei generate`
    brings it back, and rewriting it would only race the next regeneration. The
    distinction is handed to the caller rather than inferred from a path, which
    is the property the symlink farm destroyed."""
    entry(tmp_path, "place:markova")
    for d, ref in (("tei", "1-021"), (("mz", "tei"), "1-022")):
        p = tmp_path.joinpath(*([d] if isinstance(d, str) else d))
        p.mkdir(parents=True, exist_ok=True)
        (p / f"chukchi-{ref}.xml").write_text(
            '<TEI><rs ref="place:markova">M</rs></TEI>', encoding="utf-8")

    assert _rename(tmp_path, "place:markova", "place:markovo") == 0
    assert not (tmp_path / "edition" / "entities" / "place" / "markova.md").exists()
    assert (tmp_path / "edition" / "entities" / "place" / "markovo.md").exists()
    assert 'ref="place:markovo"' in (
        tmp_path / "tei" / "chukchi-1-021.xml").read_text(encoding="utf-8")
    # Derived, and left alone on purpose.
    assert 'ref="place:markova"' in (
        tmp_path / "mz" / "tei" / "chukchi-1-022.xml").read_text(encoding="utf-8")


def test_a_draft_only_ref_does_not_refuse_the_rename(tmp_path):
    entry(tmp_path, "place:markova")
    d = tmp_path / "mz" / "tei"
    d.mkdir(parents=True)
    (d / "chukchi-1-022.xml").write_text(
        '<TEI><rs ref="place:markova">M</rs></TEI>', encoding="utf-8")

    assert _rename(tmp_path, "place:markova", "place:markovo") == 0
    assert "place:markovo" in E.load(tmp_path)


def test_a_rename_may_not_cross_a_name_type(tmp_path):
    """`place:` → `water:` is toponym to hydronym. A collated page carries
    `<name type="toponym" ref="place:markova">`, and moving the entry would leave
    the ref contradicting the type beside it — which is a re-reading of the page,
    not a rename."""
    entry(tmp_path, "place:markova")
    with pytest.raises(ValueError, match="changes the class"):
        _rename(tmp_path, "place:markova", "water:markova")


def test_a_rename_within_one_name_type_moves_the_class(tmp_path):
    """The other half of the same rule, and what the four geographical classes
    were migrated by. `place:` and `land:` are both `toponym`: a page recorded
    that a reader saw a place-name, and whether that name denotes a point or a
    region is a fact about the store that no page ever asserted. So the collated
    `@ref` is re-pointed like any other rename and the page stays true."""
    entry(tmp_path, "place:kamchatka")
    entry(tmp_path, "place:golyghina", extra="- within: place:kamchatka\n")
    (tmp_path / "tei").mkdir()
    (tmp_path / "tei" / "chukchi-1-021.xml").write_text(
        '<TEI><name type="toponym" ref="place:kamchatka">K</name></TEI>',
        encoding="utf-8")

    assert _rename(tmp_path, "place:kamchatka", "land:kamchatka") == 0
    store = E.load(tmp_path)
    assert "land:kamchatka" in store and "place:kamchatka" not in store
    assert store["place:golyghina"]["within"] == "land:kamchatka"
    page = (tmp_path / "tei" / "chukchi-1-021.xml").read_text(encoding="utf-8")
    assert 'type="toponym" ref="land:kamchatka"' in page
    assert E.check(tmp_path)["ok"]


def test_a_rename_between_two_typeless_classes_is_still_refused(tmp_path):
    """The licence is "the `@type` does not move", and four classes have no
    `@type` at all. Reading `None == None` as "does not move" would let
    `taxon:` → `source:` through on the strength of two absences, which is the
    one way a mechanical rule about equality can be worse than a flat refusal."""
    entry(tmp_path, "taxon:rangifer")
    with pytest.raises(ValueError, match="changes the class"):
        _rename(tmp_path, "taxon:rangifer", "source:rangifer")


def test_a_rename_onto_an_existing_id_is_refused(tmp_path):
    entry(tmp_path, "place:markova")
    entry(tmp_path, "place:anadyr")
    with pytest.raises(ValueError, match="already exists"):
        _rename(tmp_path, "place:markova", "place:anadyr")


def test_a_reported_rename_writes_nothing(tmp_path):
    entry(tmp_path, "place:markova", gloss="x")
    entry(tmp_path, "place:other", gloss="near [[place:markova]]")
    _rename(tmp_path, "place:markova", "place:markovo", commit=False)

    assert (tmp_path / "edition" / "entities" / "place" / "markova.md").exists()
    assert "[[place:markova]]" in E.load(tmp_path)["place:other"]["gloss"]


# ------------------------------------------------------------ the live store

def test_the_committed_store_checks_out():
    assert E.check(REPO)["ok"]


# ------------------------------------------------------------- adding an alias

class _AliasArgs:
    def __init__(self, root, ident, form, lang="", auto="no", note="",
                 commit=True):
        self.root, self.ident, self.form = root, ident, form
        self.lang, self.auto, self.note, self.commit = lang, auto, note, commit
        self.json = self.toon = self.pager = False


def _alias(tmp_path, ident, form, **kw):
    from harness.cli._entity import run_alias
    return run_alias(_AliasArgs(tmp_path, ident, form, **kw))


def test_an_alias_is_normalized_to_nfd_on_the_way_in(tmp_path):
    """The reason this verb exists at all. A `link:` or a `within:` is a line of
    ASCII that a text editor sets as well as a flag would; an alias is a native
    form, and a precomposed character against an NFD store matches nothing and
    shows nothing in the file afterwards."""
    entry(tmp_path, "place:x", aliases=[("X", False)])
    _alias(tmp_path, "place:x", "Йош")      # composed Й
    forms = [t["form"] for t in E.load(tmp_path)["place:x"]["aliases"]]
    assert "Йош" in forms             # decomposed
    assert "Йош" not in forms


def test_an_unresolvable_handle_refuses_and_writes_nothing(tmp_path):
    """`lookup.expand`'s rule, inherited whole: **nothing half-expands.** A row
    with one bad handle is not written rather than written wrong, and a brace
    that survives is its own refusal — no page keys a brace."""
    p = entry(tmp_path, "place:x", aliases=[("X", False)])
    before = p.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="brace|handle"):
        _alias(tmp_path, "place:x", "{no-such-key}")
    assert p.read_text(encoding="utf-8") == before


def test_a_duplicate_form_is_refused_before_it_breaks_the_file(tmp_path):
    """`parse` refuses a form listed twice, so the naive append would break the
    file the verb had just written. Caught with a message instead."""
    entry(tmp_path, "place:x", aliases=[("Markova", True)])
    with pytest.raises(ValueError, match="already lists"):
        _alias(tmp_path, "place:x", "Markova")


def test_the_language_is_checked_and_blank_is_legal(tmp_path):
    """An unstated language is what most of the store says and is a different
    claim from a wrong one, so blank passes and an invented code does not."""
    entry(tmp_path, "place:x", aliases=[("X", False)])
    with pytest.raises(ValueError, match="alias vocabulary"):
        _alias(tmp_path, "place:x", "Y", lang="klingon")
    _alias(tmp_path, "place:x", "Y")
    row = [t for t in E.load(tmp_path)["place:x"]["aliases"] if t["form"] == "Y"]
    assert row and row[0]["lang"] == "" and row[0]["auto"] is False


def test_auto_has_no_default_and_the_flag_is_the_declaration(tmp_path):
    """`auto` is the author's declaration that a form is safe out of context —
    the store's own words — so the flag's absence is `no` and says so in the
    file rather than leaving the cell to be guessed at. All three states write
    the column's own word, which is what makes the file the record of the
    declaration rather than a rendering of a flag."""
    entry(tmp_path, "place:x", aliases=[("X", False)])
    _alias(tmp_path, "place:x", "Loud", auto="yes")
    _alias(tmp_path, "place:x", "Sometimes", auto="once")
    _alias(tmp_path, "place:x", "Quiet")
    got = {t["form"]: (t["auto"], t["scope"])
           for t in E.load(tmp_path)["place:x"]["aliases"]}
    assert got["Loud"] == (True, "all")
    assert got["Sometimes"] == (True, "first")
    assert got["Quiet"] == (False, "")


def test_a_reported_alias_writes_nothing(tmp_path):
    p = entry(tmp_path, "place:x", aliases=[("X", False)])
    before = p.read_text(encoding="utf-8")
    _alias(tmp_path, "place:x", "Y", commit=False)
    assert p.read_text(encoding="utf-8") == before


class _NewArgs:
    def __init__(self, root, ident, canonical):
        self.root, self.ident, self.canonical = root, ident, canonical
        self.aliases, self.lang = (), ""
        self.within = self.part_of = self.authority = ""
        self.geos = ()
        self.commit = True
        self.json = self.toon = self.pager = False


def _scaffold(tmp_path, ident, canonical="X"):
    from harness.cli._entity import run_new
    run_new(_NewArgs(tmp_path, ident, canonical))
    cls, slug = ident.split(":")
    return tmp_path / "edition" / "entities" / cls / f"{slug}.md"


def test_the_scaffolds_placeholder_row_goes_when_a_real_one_arrives(tmp_path):
    """`entity new` writes `| | | no | |` so the table has a body, and `parse`
    reads it as nothing at all. Left standing under a form that *is* an alias it
    reads as an alias whose form went missing — a worse claim than the empty
    table it stood for, and one no human put there."""
    p = _scaffold(tmp_path, "place:x")
    assert "| | | no | |" in p.read_text(encoding="utf-8")
    _alias(tmp_path, "place:x", "Markova")
    text = p.read_text(encoding="utf-8")
    assert "| | | no | |" not in text
    assert "| Markova | | no | |" in text
    assert [t["form"] for t in E.load(tmp_path)["place:x"]["aliases"]] == ["Markova"]


def test_the_placeholder_is_the_only_empty_row_the_store_tolerates(tmp_path):
    """Which is what makes dropping it safe: it cannot be carrying anything. Put
    a note in that same row and `parse` refuses the file outright, so no row the
    verb erases was ever a row someone wrote something in."""
    p = entry(tmp_path, "place:x")
    text = p.read_text(encoding="utf-8").replace(
        "|---|---|---|---|\n", "|---|---|---|---|\n| | | no | the form is lost |\n")
    p.write_text(text, encoding="utf-8")
    with pytest.raises(E.Malformed, match="empty form"):
        E.load(tmp_path)


# --------------------------------------------------- the printed sigla

class _SiglaArgs:
    def __init__(self, root, commit=True):
        self.root, self.commit = root, commit
        self.json = self.toon = self.pager = False


def _authorities(root: Path, *works) -> None:
    """`edition/authorities.json` with just the `cited_as` this verb reads."""
    import json
    p = root / "edition"
    p.mkdir(parents=True, exist_ok=True)
    (p / "authorities.json").write_text(json.dumps({"authorities": [
        {"key": k, "cited_as": [{"name": n, "volume": v, "short_title": t}
                                for n, v, t in cited]}
        for k, cited in works]}), encoding="utf-8")


def _sigla(tmp_path, **kw):
    from harness.cli._entity import run_sigla
    return run_sigla(_SiglaArgs(tmp_path, **kw))


def test_a_volume_yields_both_spellings_and_the_name_joins_them(tmp_path):
    """`Maydell I, p. 331.` and `Maydell, I, pp. 627-680.` sit in one apparatus,
    so the comma carries no information and the store holds both. The *name* is
    what `[Cited, MAYDELL, I, II.]` prints — a two-volume work is one work."""
    _authorities(tmp_path, ("maydell1893", [("Maydell", "I", None),
                                            ("Maydell", "II", None)]))
    p = entry(tmp_path, "source:maydell-1893", canonical="Maydell 1893",
              aliases=[("Maydell", False)], extra="- authority: maydell1893\n")
    _sigla(tmp_path)
    rec = E.load(tmp_path)["source:maydell-1893"]
    assert rec["canonical"] == "Maydell, I, II"
    assert {t["form"] for t in rec["aliases"]} == {
        "Maydell", "Maydell, I", "Maydell I", "Maydell, II", "Maydell II"}
    assert p.read_text(encoding="utf-8").startswith(
        "# source:maydell-1893 — Maydell, I, II\n")


def test_an_uncontested_bare_surname_is_raised_and_never_renames(tmp_path):
    """The book only ever quotes Nelson, so no `person:` claims the string and
    the surname is the work's alone: the row it already holds at `auto: no`
    is raised to `yes`. The heading is untouched — a siglum earns it by saying
    which work, and a surname names the man as readily as the book."""
    _authorities(tmp_path, ("nelson1899", [("Nelson", None, None)]))
    p = entry(tmp_path, "source:nelson-1899", canonical="Nelson 1899",
              aliases=[("Nelson", False)], extra="- authority: nelson1899\n")
    _sigla(tmp_path)
    rec = E.load(tmp_path)["source:nelson-1899"]
    assert rec["canonical"] == "Nelson 1899"
    assert [(t["form"], t["auto"]) for t in rec["aliases"]] == [("Nelson", True)]
    assert p.read_text(encoding="utf-8").startswith(
        "# source:nelson-1899 — Nelson 1899\n")


def test_a_contested_bare_surname_stays_no(tmp_path):
    """`Wrangell` is a man the book narrates and a book it cites, and the alias
    table cannot tell them apart — that is `citations.py`'s job, on the
    locator. Nothing here may raise it."""
    _authorities(tmp_path, ("wrangell1840", [("Wrangell", None, None)]))
    p = entry(tmp_path, "source:wrangell-1840", canonical="Wrangell 1840",
              aliases=[("Wrangell", False)], extra="- authority: wrangell1840\n")
    entry(tmp_path, "person:wrangell", aliases=[("Wrangell", False)])
    before = p.read_text(encoding="utf-8")
    _sigla(tmp_path)
    assert p.read_text(encoding="utf-8") == before


def test_a_noted_surname_row_is_a_ruling_and_stands(tmp_path):
    _authorities(tmp_path, ("nelson1899", [("Nelson", None, None)]))
    p = entry(tmp_path, "source:nelson-1899", canonical="Nelson 1899",
              extra="- authority: nelson1899\n")
    text = p.read_text(encoding="utf-8").replace(
        "|---|---|---|---|\n", "|---|---|---|---|\n| Nelson | | no | too common |\n")
    p.write_text(text, encoding="utf-8")
    _sigla(tmp_path)
    assert E.load(tmp_path)["source:nelson-1899"]["aliases"][0]["auto"] is False


def test_a_short_title_siglum_is_one_row_and_not_two(tmp_path):
    """The short title is set with its comma throughout the footnotes, so unlike
    a volume it has one spelling and yields one row."""
    _authorities(tmp_path, ("boas1888", [("Boas", None, "Central Eskimo")]))
    entry(tmp_path, "source:boas-1888", canonical="Boas 1888",
          aliases=[("Boas", False)], extra="- authority: boas1888\n")
    _sigla(tmp_path)
    rec = E.load(tmp_path)["source:boas-1888"]
    assert rec["canonical"] == "Boas, Central Eskimo"
    assert {t["form"] for t in rec["aliases"]} == {"Boas", "Boas, Central Eskimo"}


def test_a_form_another_entry_claims_is_written_auto_no(tmp_path):
    """`entity check`'s rule applied before the row is written rather than left
    for it to catch afterwards — a form two entities claim is a question for a
    human, not a licence."""
    _authorities(tmp_path, ("dall1870", [("Dall", "I", None)]))
    entry(tmp_path, "source:dall-1870", canonical="Dall 1870",
          extra="- authority: dall1870\n")
    entry(tmp_path, "person:dall", canonical="William Dall",
          aliases=[("Dall, I", False)])
    _sigla(tmp_path)
    rows = {t["form"]: t["auto"]
            for t in E.load(tmp_path)["source:dall-1870"]["aliases"]}
    assert rows["Dall, I"] is False and rows["Dall I"] is True


def test_two_entries_with_one_siglum_do_not_both_claim_it_unconditionally(tmp_path):
    """`alias_index` is a snapshot taken before the first write, so a second
    entry reaching the same form would be told nothing else claims it. Both
    would come out `auto: yes`, which `entity check` refuses outright — one
    commit too late to be cheap."""
    _authorities(tmp_path, ("a1", [("Krause", "I", None)]),
                 ("a2", [("Krause", "I", None)]))
    entry(tmp_path, "source:krause-1881", canonical="Krause 1881",
          extra="- authority: a1\n")
    entry(tmp_path, "source:krause-1882", canonical="Krause 1882",
          extra="- authority: a2\n")
    _sigla(tmp_path)
    store = E.load(tmp_path)
    autos = [t["auto"] for i in ("source:krause-1881", "source:krause-1882")
             for t in store[i]["aliases"] if t["form"] == "Krause, I"]
    assert autos.count(True) == 1, autos


def test_a_reported_run_writes_nothing(tmp_path):
    _authorities(tmp_path, ("boas1888", [("Boas", None, "Central Eskimo")]))
    p = entry(tmp_path, "source:boas-1888", canonical="Boas 1888",
              extra="- authority: boas1888\n")
    before = p.read_text(encoding="utf-8")
    _sigla(tmp_path, commit=False)
    assert p.read_text(encoding="utf-8") == before
