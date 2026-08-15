"""Figure and plate cross-references: what the prose prints, and where it points.

The two halves are tested apart because they are kept apart: `scan` never sees a
store and `resolve` never sees a string. Every case below is a phrase the corpus
actually sets — the shapes came out of a census over `mz/tei/`, not out of
imagination about how a book might cite itself.
"""

from __future__ import annotations

from harness import figrefs


def _printed(text: str) -> list[str]:
    """Each reference as `kind:plate:number`, which is short enough to assert on."""
    return [f"{s['kind']}:{s['plate']}:{s['number']}" for s in figrefs.scan(text)]


# --- scan: what the page prints ----------------------------------------------

def test_a_bare_figure_reference():
    assert _printed("as shown in Fig. 87 above") == ["figure::87"]


def test_a_plate_on_its_own():
    assert _printed("(Plate XIV)") == ["plate::XIV"]


def test_a_plate_scopes_the_figure_attached_to_it():
    """`Plate XXVII, Fig. 3` is the plate's third picture, not text-figure 3.

    **The book restarts figure numbering at 1 on every plate**, so the scope is
    not decoration: unscoped, `Fig. 3` names 16 different pictures.
    """
    assert _printed("(see Plate XXVII, Fig. 3)") == ["plate::XXVII", "figure:XXVII:3"]


def test_a_semicolon_ends_the_plate_s_scope():
    """`(see Plate XXIII, Fig. 2; also Fig. 177)` is two references and one of
    them is the plate's. Reading the second as the plate's too would point a
    reader at a picture on a different leaf, with the caption to match."""
    assert _printed("(see Plate XXIII, Fig. 2; also Fig. 177)") == [
        "plate::XXIII", "figure:XXIII:2", "figure::177"]


def test_a_bracket_does_not_end_it():
    assert _printed("Plates V (Fig. 1)") == ["plate::V", "figure:V:1"]


def test_every_numeral_of_a_run_is_its_own_reference():
    """`Figs. 214, 215, 216` names three pictures, and the List of
    Illustrations' rule applies here for its reason: one link would pick one."""
    assert _printed("(Figs. 214, 215, 216)") == [
        "figure::214", "figure::215", "figure::216"]


def test_a_range_names_the_numerals_it_prints():
    """`Figs. 2-4` links 2 and 4, the numerals actually set. Expanding to 3 would
    put a link on text the page does not have."""
    assert _printed("(see Plate XXI, Figs. 2-4)") == [
        "plate::XXI", "figure:XXI:2", "figure:XXI:4"]


def test_a_sub_letter_is_consumed_and_never_linked():
    """`Fig. 190, a` is a part of one picture and the store keys pictures. The
    letter must be swallowed, not left to be read as another numeral's start."""
    assert _printed("(see Fig. 190, a)") == ["figure::190"]


def test_a_superscript_on_a_sub_letter_changes_nothing():
    assert _printed("(Fig. 21, a¹)") == ["figure::21"]
    assert _printed("(see Fig. 44, c¹)") == ["figure::44"]


def test_a_page_number_after_a_figure_is_not_a_figure():
    """`Fig. 74, k, p. 156` — the run ends at the sub-letter, and `156` is a
    folio. Reading it as a second figure number would link to picture 156."""
    assert _printed("(see Fig. 74, k, p. 156.)") == ["figure::74"]


def test_the_numeral_alone_is_the_span():
    """The span bounds the number and not the `Fig.` in front of it, which is
    what lets a three-numeral run be three separate links."""
    s = figrefs.scan("see Fig. 87 there")[0]
    assert "see Fig. 87 there"[s["start"]:s["end"]] == "87"


def test_prose_with_no_reference_scans_to_nothing():
    assert _printed("The Chukchee retaliate by saying that the Lamut") == []


# --- the authority guard -----------------------------------------------------

NAMES = {"Sauer", "Nelson", "Hough", "Lamp", "Boas"}


def test_another_author_s_plate_is_refused():
    """**The hazard is a correct-looking link to the wrong picture.** This book
    has a Plate XIV and so does Sauer, and nothing in `Plate XIV` tells them
    apart — only the name in front of it, which `Authorities Quoted` holds."""
    assert figrefs.foreign_citation("Compare Sauer, ", NAMES) == "Sauer"


def test_a_short_title_between_the_name_and_the_plate():
    """`W. Hough, in Lamp (Plate 17)` is Hough's. Which of the two names is
    reported does not matter and is not asserted — the store holds `Lamp` as a
    citation name in its own right, so either answer is the same finding."""
    assert figrefs.foreign_citation("W. Hough, in Lamp (", NAMES) in NAMES
    assert figrefs.foreign_citation("Hough, Armor, ", NAMES) == "Hough"


def test_a_sentence_ends_the_citation():
    """An authority named and then left behind does not make the next figure
    reference theirs — refusing there would cost a real link on every page that
    mentions a source."""
    assert figrefs.foreign_citation(
        "as Nelson found. The winter house is drawn in ", NAMES) == ""


def test_this_book_s_own_reference_is_untouched():
    assert figrefs.foreign_citation("The lamp is shown in ", NAMES) == ""


def test_no_authorities_means_no_suppression():
    """An empty store must not silently suppress everything — the guard has to
    fail towards linking this book's own pictures, which is the common case."""
    assert figrefs.foreign_citation("Sauer, ", set()) == ""


def test_authority_names_takes_both_fields():
    got = figrefs.authority_names([
        {"cited_as": [{"name": "Hough", "short_title": "Lamp"}]},
        {"cited_as": [{"name": "Sauer", "short_title": None}]},
        {"cited_as": []},
    ])
    assert got == {"Hough", "Lamp", "Sauer"}


# --- resolve: where it points ------------------------------------------------

#: The corpus's own values, reduced. `1-287` and `1-049` are plate leaves and
#: both carry a picture numbered 1, which is the collision the whole
#: plate-scoping rule is about.
BY_PLATE = {"XXI": {"ref": "1-287", "keys": ["003", "001"]},
            "I": {"ref": "1-049", "keys": ["002", "005", "001"]},
            "V": {"ref": "1-123", "keys": ["001", "002"]}}
BY_NUMBER = {"177": [{"ref": "1-313", "key": "001", "keys": ["001"]}],
             "140": [{"ref": "1-276", "key": "005", "keys": ["005", "006"]}],
             "1": [{"ref": "1-287", "key": "003", "keys": ["003"]},
                   {"ref": "1-049", "key": "002", "keys": ["002"]}]}
BOXES = {"1-287": [{"n": "1", "key": "003", "zone_ids": ["fig_1-287_003"]},
                   {"n": "2", "key": "001", "zone_ids": ["fig_1-287_001"]}],
         "1-123": [{"n": None, "key": "001",
                    "zone_ids": ["fig_1-123_001", "fig_1-123_002"]}]}


def _resolve(**span):
    span = {"kind": "figure", "number": "", "plate": "", **span}
    return figrefs.resolve(span, BY_NUMBER, BY_PLATE, BOXES.get)


def test_a_plate_resolves_to_every_picture_on_its_leaf():
    assert _resolve(kind="plate", number="XXI")["pairs"] == \
        ["1-287/003", "1-287/001"]


def test_a_plate_of_two_pictures_under_one_caption_gives_both():
    """`1-123` is Plate V: two pictures, one caption, no number. Keying on the
    record's `key` drew the upper one and dropped the lower."""
    assert _resolve(kind="plate", number="V")["pairs"] == \
        ["1-123/001", "1-123/002"]


def test_a_plate_scoped_figure_resolves_where_a_bare_one_cannot():
    """The join this module exists for. `Fig. 1` is two records here and
    refuses; `Plate XXI, Fig. 1` is one, because the plate scopes it."""
    assert _resolve(number="1", plate="XXI")["pairs"] == ["1-287/003"]
    assert _resolve(number="1")["pairs"] == []


def test_a_bare_number_excludes_the_plate_leaves():
    """A number on a plate means nothing away from its plate, so it is never
    cited alone — which is what lets a bare `Fig. 1` ignore the plates' copies.
    Both candidates here are on plate leaves, so none is left and it refuses;
    that is the corpus's own answer for `Fig. 1`, whose text figure is the
    fold-out map and has no box in `gt/fig/`."""
    assert _resolve(number="1", plate="")["why"].startswith("0 text figures")


def test_a_figure_drawn_in_two_boxes_names_both():
    """`1-276`'s Fig. 140 is two boxes lettered a and b under one caption."""
    assert _resolve(number="140")["pairs"] == ["1-276/005", "1-276/006"]


def test_a_plate_that_is_not_located_refuses_and_says_so():
    out = _resolve(kind="plate", number="XCIX")
    assert out["pairs"] == [] and "no plate" in out["why"]


def test_a_plate_figure_with_no_numbered_caption_refuses():
    """Plate V's two pictures carry one unnumbered caption, so nothing says
    which is Fig. 2. Counting into the list would answer it by position, which
    is the guess `in_printed_order` already declines to make."""
    out = _resolve(number="2", plate="V")
    assert out["pairs"] == [] and "0 figures numbered 2" in out["why"]


def test_an_unresolved_reference_always_says_which_store_declined():
    """A reader who sees no link needs to know it is a gap in `gt/fig/` and not
    an edition that does not link — every refusal names its reason."""
    for span in ({"kind": "plate", "number": "XCIX"},
                 {"kind": "figure", "number": "999", "plate": ""},
                 {"kind": "figure", "number": "2", "plate": "V"}):
        assert _resolve(**span)["why"]
