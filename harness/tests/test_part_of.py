"""`within:` and `part-of:` — where a thing is, against what it belongs to.

One field carried both until the Naukans made the conflation visible. They are
a Yupik people who lived in a single village, so `within: people:yupik`
inherited the whole Central-plus-Pacific Yupik language area for one settlement
— an extent two orders of magnitude too large, drawn with the confidence of a
measurement — while `within: place:naukan` bought the extent by dropping the
fact that they are Yupik at all. Neither answer was wrong about its own half,
which is the tell that the question was two questions.

The same defect as the `geo:`/`area:` rule, inverted: there, two fields said one
thing and the second could only drift; here, one field said two things and no
reader could tell which it meant.

**Two hierarchies, two edges, and the tests below hold them apart** — because
collapsing them into one function is the mistake that was made twice while this
was being written, once in each direction.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness import entities as E
from harness import geo


def write(root: Path, ident: str, body: str = "", **fields) -> Path:
    cls, _, slug = ident.partition(":")
    p = root / "edition" / "entities" / cls / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(f"- {k.replace('_', '-')}: {v}\n"
                   for k, v in fields.items() if v)
    p.write_text(
        f"# {ident} — {slug.title()}\n\n- status: ratified\n{rows}\n"
        f"## aliases\n\n| form | lang | auto | note |\n|---|---|---|---|\n"
        f"| {slug.title()} | | yes | |\n\n## gloss\n\n{body or '(unwritten)'}\n",
        encoding="utf-8")
    return p


# -- the field itself ---------------------------------------------------------

def test_a_hyphenated_field_name_actually_parses(tmp_path):
    """The bug underneath the bug. `_FIELD` matched `[a-z]+`, which cannot match
    a hyphen, so `- part-of:` was **silently discarded** — the record carried an
    empty value and every gate passed. A parser that drops what it does not
    recognise is the shape this repository has already been hurt by once."""
    write(tmp_path, "people:yupik")
    write(tmp_path, "people:naukans", part_of="people:yupik")
    rec = E.load(tmp_path)["people:naukans"]
    assert rec["part_of"] == "people:yupik"


def test_an_unknown_field_is_refused_rather_than_ignored(tmp_path):
    """The other half of the same fix, and the half that makes the first
    unnecessary next time: a typo'd `- withn:` used to parse cleanly into
    nothing."""
    p = write(tmp_path, "place:x")
    p.write_text(p.read_text(encoding="utf-8").replace(
        "- status: ratified\n", "- status: ratified\n- withn: land:y\n"),
        encoding="utf-8")
    with pytest.raises(E.Malformed) as e:
        E.parse(p.read_text(encoding="utf-8"))
    assert "withn" in str(e.value)


def test_a_retired_field_stays_inert(tmp_path):
    """`since:` was removed and records may still carry it. Refusing it would
    turn dropping a field into a migration of every record that ever had one —
    so the strictness above is bounded by a named list rather than by luck."""
    p = write(tmp_path, "place:markova")
    p.write_text(p.read_text(encoding="utf-8").replace(
        "- status: ratified\n", "- status: ratified\n- since: 1-021\n"),
        encoding="utf-8")
    assert "since" not in E.parse(p.read_text(encoding="utf-8"))


# -- what the gate says -------------------------------------------------------

def test_a_dangling_part_of_is_an_error(tmp_path):
    write(tmp_path, "people:naukans", part_of="people:nobody")
    errs = E.check(tmp_path)["errors"]
    assert any("part-of" in e and "resolves to nothing" in e for e in errs)


def test_an_entry_may_not_be_part_of_itself(tmp_path):
    """The one-step cycle, with its own message: "cycle: people:x → people:x"
    reads as a puzzle, and this is the mistake a copied file makes."""
    write(tmp_path, "people:x", part_of="people:x")
    errs = E.check(tmp_path)["errors"]
    assert any("names its own entry" in e for e in errs)


def test_a_part_of_cycle_is_caught_and_names_its_field(tmp_path):
    write(tmp_path, "people:a", part_of="people:b")
    write(tmp_path, "people:b", part_of="people:a")
    errs = E.check(tmp_path)["errors"]
    assert any("`part-of:` cycle" in e for e in errs), errs


def test_a_geographic_part_of_is_reported_as_a_misfiled_within(tmp_path):
    """`part-of: land:chukotka` on a people is a `within:` in the wrong field,
    and that specific confusion is what the split exists to end."""
    write(tmp_path, "land:chukotka")
    write(tmp_path, "people:x", part_of="land:chukotka")
    errs = E.check(tmp_path)["errors"]
    assert any("points at a place" in e for e in errs), errs


# -- the two hierarchies ------------------------------------------------------

def _yupik(tmp_path):
    write(tmp_path, "land:chukchi-peninsula")
    write(tmp_path, "place:naukan", within="land:chukchi-peninsula",
          geo="66.0267 -169.7019")
    # A `geo:` standing in for the `area:` the real record carries: a temp store
    # holds no `edition/geo/` shapes, and what these tests need from the parent is
    # only that it *has* an extent for a child to inherit.
    write(tmp_path, "people:yupik", geo="64.0 -172.0")
    write(tmp_path, "people:naukans", within="place:naukan",
          part_of="people:yupik")
    # No village of its own: the case the inherited fallback was written for.
    write(tmp_path, "people:kavralit", part_of="people:yupik")
    return E.load(tmp_path)


def test_the_atlas_edge_takes_where_it_is(tmp_path):
    store = _yupik(tmp_path)
    assert E.tree_parent(store["people:naukans"]) == "place:naukan"
    assert "people:naukans" in E.children(store)["place:naukan"]


def test_the_class_edge_takes_what_it_belongs_to(tmp_path):
    """The bug this pair exists to stop: with one shared edge, `people:yupik`
    showed no subgroups at all on a page about peoples, because both of them had
    gone to hang from villages."""
    store = _yupik(tmp_path)
    assert E.kin_parent(store["people:naukans"], store) == "people:yupik"
    assert E.kin_parent(store["people:kavralit"], store) == "people:yupik"


def test_a_people_with_no_village_still_hangs_from_its_ethnicity(tmp_path):
    """`part-of:` alone, so both edges agree — which is why the four subgroups
    that have no settlement kept working through the split and the two that do
    were the ones that broke."""
    store = _yupik(tmp_path)
    assert E.tree_parent(store["people:kavralit"]) == "people:yupik"
    assert "people:kavralit" in E.children(store)["people:yupik"]


def test_a_non_people_never_inherits_along_part_of(tmp_path):
    """The scope is the honesty. A `source:` part of a larger work is not
    *somewhere* because of it, and that edge on the tree would put a
    bibliography on the map."""
    write(tmp_path, "source:whole")
    write(tmp_path, "source:chapter", part_of="source:whole")
    store = E.load(tmp_path)
    assert E.tree_parent(store["source:chapter"]) == ""
    assert E.kin_parent(store["source:chapter"], store) == "source:whole"


# -- the extent ---------------------------------------------------------------

def test_a_village_dwelling_people_takes_its_villages_extent(tmp_path):
    """The whole point. Before the split this inherited its ethnicity's language
    area for a group that lived in one settlement."""
    store = _yupik(tmp_path)
    box = geo.extent_of("people:naukans", store, tmp_path)
    village = geo.extent_of("place:naukan", store, tmp_path)
    assert box == village


def test_the_ethnicity_is_still_the_bound_where_there_is_no_village(tmp_path):
    """A subgroup with no settlement of its own inherits its ethnicity's extent,
    which is the case the fallback was written for and stays true after the
    split — the Reindeer and Maritime Chukchi, the Kavraˊlɪt and the Chuvans
    would otherwise be absent from an atlas largely about them."""
    store = _yupik(tmp_path)
    box = geo.extent_of("people:kavralit", store, tmp_path)
    assert box is not None
    assert box == geo.extent_of("people:yupik", store, tmp_path)


def test_the_worklist_sees_an_entity_that_hangs_from_part_of(tmp_path):
    """`geo.unlocated` scopes to what the atlas can draw, and read `within:`
    directly — so the four subgroups fell out of the worklist entirely the
    moment the field moved. Invisible, not merely unlocated."""
    store = _yupik(tmp_path)
    rows = {r["id"]: r for r in geo.unlocated(store, tmp_path)}
    assert "people:kavralit" in rows
    assert rows["people:kavralit"]["within"] == "people:yupik", \
        "the row names the edge it actually hangs from"
