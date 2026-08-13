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
    calls unstated."""
    cls, slug = ident.split(":")
    rows = "\n".join(f"| {a[0]} | {a[2] if len(a) > 2 else ''} | "
                     f"{'yes' if a[1] else 'no'} | |" for a in aliases)
    p = root / "entities" / cls / f"{slug}.md"
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
        {"form": "Markova", "lang": "", "auto": True, "note": ""}]


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
    argument that an unauditable apparatus store is the `data/toc.json` defect.
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


def test_a_wikilink_in_an_alias_note_is_checked_too(tmp_path):
    """The notes are where an author explains why a form is suggest-only, and the
    explanation is almost always "it is also that other entity"."""
    entry(tmp_path, "place:markova",
          aliases=[("Markova", False)],
          extra="", gloss="x")
    p = tmp_path / "entities" / "place" / "markova.md"
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
    """"Chukchee" really is the people and the language. The store's job is to say
    so, and the generator's is to ask rather than resolve it."""
    entry(tmp_path, "people:chukchee", aliases=[("Chukchee", False)])
    entry(tmp_path, "language:chukchee", aliases=[("Chukchee", False)])
    rep = E.check(tmp_path)
    assert rep["ok"]
    assert rep["collisions"][0]["claimed_by"] == "language:chukchee people:chukchee"


def test_two_entities_may_not_both_claim_a_form_unconditionally(tmp_path):
    """`auto: yes` asserts the form means this entity wherever it appears. Two such
    claims on one form are a contradiction, and one of them is wrong."""
    entry(tmp_path, "people:chukchee", aliases=[("Chukchee", True)])
    entry(tmp_path, "language:chukchee", aliases=[("Chukchee", True)])
    rep = E.check(tmp_path)
    assert not rep["ok"]
    assert any("cannot both own a form" in e for e in rep["errors"])


# -------------------------------------------------------------- the matcher

def idx(*specs):
    return {form: [{"id": i, "auto": a, "status": s} for i, a, s in claims]
            for form, claims in specs}


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
    got = _set_field(text, "area", "watershed:anadyr")
    fields = [line[2:].split(":")[0] for line in got.splitlines()
              if line.startswith("- ")]
    assert fields == ["status", "area", "link"]
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
    from harness.cli._entity import _set_field

    p = entry(tmp_path, "place:x", extra="- within: place:y\n")
    base = p.read_text(encoding="utf-8")
    assert E.parse(_set_field(base, "geo", "66.0 -170.0"))["geo"] == (66.0, -170.0)
    got = _set_field(base, "area", "watershed:anadyr,marine:chaun-bay")
    assert E.parse(got)["area"] == "marine:chaun-bay,watershed:anadyr"

    # And the guarantee working: setting the second one produces a file that
    # does not parse, so `locate` reports it instead of writing it. A shape is
    # the location and `extent_of` never reads a point beside one.
    with pytest.raises(E.Malformed, match="both"):
        E.parse(_set_field(got, "geo", "66.0 -170.0"))


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
    """The two ways one entry points at another, and `entity check` gates both —
    so a rename that missed one would fail the gate rather than go quiet."""
    entry(tmp_path, "people:chukchee", aliases=[("Chukchee tribe", True)])
    entry(tmp_path, "place:markova", extra="- within: people:chukchee\n",
          gloss="home of the [[people:chukchee]]")
    _rename(tmp_path, "people:chukchee", "people:chukchi")

    store = E.load(tmp_path)
    assert "people:chukchi" in store and "people:chukchee" not in store
    assert not (tmp_path / "entities" / "people" / "chukchee.md").exists()
    assert store["place:markova"]["within"] == "people:chukchi"
    assert "[[people:chukchi]]" in store["place:markova"]["gloss"]
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
    assert not (tmp_path / "entities" / "place" / "markova.md").exists()
    assert (tmp_path / "entities" / "place" / "markovo.md").exists()
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

    assert (tmp_path / "entities" / "place" / "markova.md").exists()
    assert "[[place:markova]]" in E.load(tmp_path)["place:other"]["gloss"]


# ------------------------------------------------------------ the live store

def test_the_committed_store_checks_out():
    assert E.check(REPO)["ok"]
