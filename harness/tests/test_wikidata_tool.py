"""`tools/wikidata.py`'s two offline judgements.

The network half cannot be tested here and is not the part that can go wrong
quietly: a failed request is loud. What can go wrong quietly is the ranking —
if `_parent_shape` stops walking, or the class words stop matching, the tool
goes on printing candidates in a plausible order with the right one no longer
first, and nothing says so. Those two are pure functions over the store, so
they are held here.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from harness.tests.test_entities import entry

ROOT = Path(__file__).resolve().parent.parent.parent


def _tool():
    """`tools/` is scripts, not a package — loaded by path rather than imported.

    Skipped rather than failed where `requests` is absent: the module imports it
    at the top, and a tree without it is a tree where the tool cannot run, not
    one where it is broken.
    """
    pytest.importorskip("requests")
    spec = importlib.util.spec_from_file_location(
        "_wikidata_tool", ROOT / "tools" / "wikidata.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_wikidata_tool"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_parent_shape_is_the_nearest_ancestor_that_has_one(tmp_path):
    """Reading `within:` once would report "no parent shape" for most of the
    store and throw the check away: a village's parent is Chukotka, which no
    source draws, and *its* parent is Northeast Siberia, which none draws
    either. The first ancestor with an `area:` is what a candidate coordinate
    should fall inside."""
    w = _tool()
    entry(tmp_path, "land:kamchatka", extra="- area: region:kamchatka\n")
    entry(tmp_path, "land:olutora", extra="- within: land:kamchatka\n")
    entry(tmp_path, "place:golyghina", extra="- within: land:olutora\n")
    from harness.entities import load

    store = load(tmp_path)
    assert w._parent_shape("place:golyghina", store) == "region:kamchatka"
    assert w._parent_shape("land:kamchatka", store) == ""


def test_a_within_cycle_does_not_hang_the_walk(tmp_path):
    """`entity check` gates against a cycle, so this is unreachable through the
    store — and the walk is over authored text that a half-finished edit can put
    in that state between two runs of the gate."""
    w = _tool()
    entry(tmp_path, "land:a", extra="- within: land:b\n")
    entry(tmp_path, "land:b", extra="- within: land:a\n")
    from harness.entities import load

    assert w._parent_shape("land:a", load(tmp_path)) == ""


def test_the_class_words_separate_a_river_from_the_village_on_it():
    """The disambiguator the four-class split bought. Searching `Хатырка`
    returns both, both are real, both are in the window and both fall inside the
    same shapes — no coordinate test can separate them, because they are in the
    same place. The class can, and this edition is full of the case: the Anadyr,
    the Gishiga and the Kolyuchin each name a river, a settlement and a bay."""
    w = _tool()

    def reads(cls, desc):
        return any(x in desc.lower() for x in w.CLASS_WORDS[cls])

    assert reads("river", "river in Russia")
    assert not reads("river", "human settlement in Anadyrsky District")
    assert reads("place", "human settlement in Anadyrsky District")
    assert not reads("place", "river in Russia")
    assert reads("water", "bay of the Gulf of Anadyr")
    assert reads("land", "island in the United States of America")


def test_every_geographical_class_has_words_to_match_on():
    """`GEO_CLASSES` is what the sweep iterates and `CLASS_WORDS` is what ranks
    what it finds. A class in the first and not the second ranks every candidate
    equally and silently — the tool still prints, just in the wrong order."""
    w = _tool()
    assert set(w.GEO_CLASSES) == set(w.CLASS_WORDS)


def test_the_user_agent_is_ascii():
    """An HTTP header is latin-1 by the standard. The em-dash this line was
    first written with raised on every call, and the failure surfaced as "no
    candidate carries a coordinate" — a broken request rendered as a finding
    about the world, which is this tool's worst failure mode."""
    _tool().UA.encode("latin-1")


def test_a_gap_from_the_entrys_own_point_reads_differently_by_class():
    """Same number, opposite meaning. A `place:` **is** its coordinate, so two
    sources 0.5 km apart on Anadyr corroborate each other — and that pair had
    never had a second witness, the store's points having come off a chart. A
    `land:` point is a nominal centre: the first run reported the Chukchi
    Peninsula 45.2 km out, which says nothing about either source."""
    w = _tool()
    assert "own point" in w._own_mark("place", 0.5)
    assert "not a finding" in w._own_mark("land", 45.2)
    assert "not a finding" in w._own_mark("water", 12.0)


def test_the_distance_is_kilometres_and_crosses_the_antimeridian():
    """Kilometres, unlike every other distance here, which measure a point
    against a polygon in the polygon's own units. A degree of longitude at 65°N
    is 47 km against a degree of latitude's 111, so one number for both would
    make an east-west disagreement read as under half the error it is.

    And haversine takes the wrap for free: the difference enters only as
    `sin(dlon/2)²`, so 179.9 against −179.9 is 0.2° apart and not 359.8."""
    w = _tool()
    assert 110 < w._km((65.0, 179.9), (66.0, 179.9)) < 112
    # The same 0.2° east-west is 9.4 km, not 22 — which is the whole reason this
    # is not reported in degrees.
    assert 9 < w._km((65.0, 179.9), (65.0, -179.9)) < 10
    assert w._km((65.0, 10.0), (65.0, 10.0)) == 0.0


def test_a_wkt_point_is_read_lon_then_lat():
    """SPARQL returns `Point(lon lat)` and every other coordinate in this
    project is written latitude first — the one place the two conventions meet,
    and a silent transposition would put Chukotka in the Indian Ocean, which is
    outside the window and so would be reported as a rejected candidate rather
    than as a bug."""
    w = _tool()
    assert w._wkt("Point(179.0989 62.2753)") == (62.2753, 179.0989)
    assert w._wkt("Point(-174.6167 67.4667)") == (67.4667, -174.6167)
    assert w._wkt("http://example/not-a-point") == (None, None)
    assert w._wkt("Point(nonsense)") == (None, None)


def test_the_sparql_values_block_tags_cyrillic_as_russian():
    """The store's Russian aliases are the identifications that actually work —
    `Хатырка` finds what `Vatɪˊrkan` never will — and a language tag is required
    on every literal in the block. Tagging a Cyrillic name `@en` matches
    nothing, silently."""
    w = _tool()
    import re

    seen = {}

    class _Fake:
        status_code = 200

        def raise_for_status(self): pass

        def json(self): return {"results": {"bindings": []}}

    def fake_get(url, params=None, **kw):
        seen["q"] = params["query"]
        return _Fake()

    old, w.SESSION.get = w.SESSION.get, fake_get
    try:
        w.sparql_names(["Хатырка", "Cape Navarin"])
    finally:
        w.SESSION.get = old
    values = re.search(r"VALUES \?name \{(.*?)\}", seen["q"], re.S).group(1)
    assert '"Хатырка"@ru' in values
    assert '"Cape Navarin"@en' in values
