"""Which work a printed siglum names, and the ambiguity the alias table cannot end.

`test_citations.py` is the other half and stays its own file: that one is about
`authorities.parse_citation`, the shallow parse behind a human's `find authority`
query. This one is about the rule that links without being asked, which is a
different licence and fails in different places.


`Nelson` is a man and a book. The entity store says exactly that — `person:nelson`
and `source:nelson-1899` both claim the form — so `auto_forms` withholds a link
and the generator asks. The printed citation form answers it: a locator attached
to a name is what a citation *is*, and the 34 sigla of `Authorities Quoted` are a
table a human keyed.

Every string below is one the corpus actually prints. The forms came out of a
census over `mz/tei/`'s footnotes — `ocr grep '^[⁰¹²³⁴⁵⁶⁷⁸⁹]'` is where they were
read — and not out of imagination about how a book might cite.
"""
from __future__ import annotations

from harness import citations

#: The store's own shape, cut to the cases the rule turns on: a name with one
#: work, a name whose works are told apart by volume, and one told apart by a
#: short title.
ROWS = [
    {"name": "Nelson", "volume": None, "short_title": None, "key": "nelson1899"},
    {"name": "Hooper", "volume": None, "short_title": None, "key": "hooper1853"},
    {"name": "Dall", "volume": "I", "short_title": None, "key": "dall1870"},
    {"name": "Dall", "volume": "II", "short_title": None, "key": "dall1877"},
    {"name": "Boas", "volume": None, "short_title": "Central Eskimo",
     "key": "boas1888"},
    {"name": "Boas", "volume": None, "short_title": "Baffin-Land Eskimo",
     "key": "boas1901"},
    {"name": "Hough", "volume": None, "short_title": "Armour", "key": "hough1892"},
    {"name": "Hough", "volume": None, "short_title": "Lamp", "key": "hough1895"},
]


def cited(after: str, name: str = "Nelson") -> str:
    return citations.cited(name, after, ROWS)


# ------------------------------------------------------- the locator is the fact

def test_a_page_locator_makes_it_a_citation():
    assert cited(", pp. 27, 28.") == "nelson1899"
    assert cited(", p. 229.") == "nelson1899"


def test_a_plate_or_a_figure_is_a_locator_too():
    """The book cites other people's illustrations as readily as their pages, and
    a plate number is arabic in some of those books and roman in others."""
    assert cited(", Plate LXXVI, Fig. 1, p. 208.") == "nelson1899"
    assert cited(", Lamp, Plate 15, Fig. 3.", "Hough") == "hough1895"


def test_a_name_with_no_locator_is_the_man():
    """**The refusal this exists for.** `Krause gives for the large village…` is
    a man doing something, and linking it to his book would put a reader in a
    bibliography when the sentence is about a person."""
    assert cited(" gives for the large village only 13 houses") == ""
    assert cited("’s fellow-travellers, says") == ""


def test_a_full_stop_ends_the_citation():
    """`Nelson. Fig. 22, b, shows a sled` — one statement ends and another
    begins, and the figure it then names is *this book's*. The stop is what says
    so, which is why it is the one thing that may not stand in the gap."""
    assert cited(". Fig. 22, b, shows a sled from Indian Point") == ""


def test_a_sentence_that_reaches_a_locator_is_still_a_sentence():
    """`Boas and Kroeber; for instance, compare Fig. 199` has a locator eleven
    words along. A window would take it; only citation furniture may stand in
    the gap, and a lower-case `and` is not that."""
    assert cited(" and Kroeber; for instance, compare Fig. 199, a", "Boas") == ""


# ------------------------------------------------ which work, where there are two

def test_a_volume_tells_two_works_apart():
    assert cited(", I, p. 375.", "Dall") == "dall1870"
    assert cited(" II, p. 12.", "Dall") == "dall1877"


def test_a_short_title_tells_two_works_apart():
    assert cited(", Central Eskimo, p. 537.", "Boas") == "boas1888"
    assert cited(", Baffin-Land Eskimo, Fig. 44, a", "Boas") == "boas1901"


def test_a_possessive_carries_a_short_title():
    """`in Boas’s Central Eskimo, p. 569` (1-358). The apostrophe is the printed
    evidence that the work is being named, not the man."""
    assert cited("’s Central Eskimo, p. 569", "Boas") == "boas1888"


def test_several_works_and_no_discriminator_refuses():
    """A name whose works are told apart by a title, cited with none, resolves to
    nothing rather than to the first of them."""
    assert cited(", p. 88.", "Boas") == ""


def test_a_discriminator_the_store_does_not_hold_refuses():
    """**`Hough, Armor` against the store's `Armour`.** The book prints one
    spelling and `Authorities Quoted` records another, three times in the corpus.
    The refusal is right and the question it raises is about the store, which is
    where a reader should be sent."""
    assert cited(", Armor, p. 634.", "Hough") == ""


def test_an_unlisted_title_cannot_change_a_decided_answer():
    """`Murdoch, Eskimo Bows, pp. 313, 314` and `Hooper, Ten Months among the
    Tents of the Tuski, p. 100`: the store lists no short title for either work,
    and it does not need to — the name names one work, so anything
    citation-shaped between it and the locator leaves the answer alone."""
    assert cited(", Ten Months among the Tents of the Tuski, p. 100.",
                 "Hooper") == "hooper1853"


def test_op_cit_is_citation_furniture():
    """`Gondatti (op. cit., p. 12) mentions…` — the book's way of naming a work
    already cited."""
    assert cited(" (op. cit., p. 12) mentions", "Hooper") == "hooper1853"


def test_a_name_the_table_does_not_hold_resolves_to_nothing():
    assert citations.cited("Kroeber", ", p. 12.", ROWS) == ""


# ------------------------------------------------------- the second lookup

def test_the_work_must_be_one_ratified_entry():
    """An authority no entry claims, or two claiming one, resolves to nothing
    rather than to whichever came first — and a proposed entry is not a rule's to
    apply, which is `auto_forms`' rule wherever a link is made."""
    store = {
        "source:nelson-1899": {"authority": "nelson1899", "status": "ratified"},
        "source:draft": {"authority": "dall1870", "status": "proposed"},
        "source:one": {"authority": "boas1888", "status": "ratified"},
        "source:two": {"authority": "boas1888", "status": "ratified"},
    }
    assert citations.work_of("nelson1899", store) == "source:nelson-1899"
    assert citations.work_of("dall1870", store) == ""
    assert citations.work_of("boas1888", store) == ""
    assert citations.work_of("hooper1853", store) == ""
