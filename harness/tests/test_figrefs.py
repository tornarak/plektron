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


def test_one_numeral_may_carry_several_sub_letters():
    """`Figs. 188, a, i` is one picture and two of its details. Consuming only
    the first left `i` where the next member should be, and the run ended
    there."""
    assert _printed("(Figs. 188, a, i)") == ["figure::188"]


def test_the_sub_letters_stop_at_the_first_word():
    """`1-358` sets a gloss inside the run: `Fig. 53, a, a narwhal`. The second
    `a` is a sub-letter and `narwhal` is not, so the repeat has to stop — a
    letter followed by more letters fails the word boundary."""
    assert _printed("(Fig. 53, a, a narwhal; Fig. 52, a, a dog)") == [
        "figure::53", "figure::52"]


def test_a_semicolon_separates_the_members_of_a_lettered_run():
    """`1-171`. The comma is already spoken for inside a member — `44, a¹` is one
    picture and its detail — so the printer raises the separator a rank. Stopping
    at the first member printed the other two plain."""
    assert _printed("(Figs. 44, a¹; 46, a¹; 46, b)") == [
        "figure::44", "figure::46", "figure::46"]


def test_a_semicolon_run_carries_the_plate_scope_to_every_member():
    """One run, one scope: the members after the semicolon are the same plate's,
    which is what `Plates X, Fig. 4` means when the run continues."""
    assert _printed("(Plate XXI, Figs. 2, a; 4, b)") == [
        "plate::XXI", "figure:XXI:2", "figure:XXI:4"]


def test_a_semicolon_still_ends_a_run_before_anything_but_a_numeral():
    """`1-334` sets both halves of the rule in one reference: the semicolon
    carries the run to `190` and ends it at `also`. `; see also Fig. 177` and
    `Fig. 69; b` end it too — a sub-letter with no number before it is not a
    member — so the separator never reaches past what it separates."""
    assert _printed("(Figs. 188, a, i; 190, b; also Plate XXVIII)") == [
        "figure::188", "figure::190", "plate::XXVIII"]
    assert _printed("(Fig. 87; see also Fig. 177)") == [
        "figure::87", "figure::177"]
    assert _printed("Detail of Bow represented in Fig. 69; b (??/????)") == [
        "figure::69"]


def test_the_semicolon_is_the_figure_run_s_alone():
    """`I` is a roman numeral, so a semicolon in the plate loop would read a
    second plate out of a pronoun. A plate run continues past one only where
    a `, Fig.` follows the roman, and the licence stays as narrow as that."""
    assert _printed("(Plate II; I have seen it)") == ["plate::II"]


def test_a_plate_run_continues_past_its_figure():
    """`1-301` sets `Plates XXIII, Fig. 1; XXIV, Fig. 2; also Fig. 168`: two
    plates, each with its own picture, then a text figure. The semicolon still
    ends each plate's scope — `Fig. 2` is XXIV's and `168` is nobody's — but
    reading only the first plate left `XXIV` plain and its figure unscoped,
    which is a link to text-figure 2."""
    assert _printed("(Plates XXIII, Fig. 1; XXIV, Fig. 2; also Fig. 168)") == [
        "plate::XXIII", "figure:XXIII:1", "plate::XXIV", "figure:XXIV:2",
        "figure::168"]
    assert _printed("(Plates X, Fig. 4; XI, Fig. 1).") == [
        "plate::X", "figure:X:4", "plate::XI", "figure:XI:1"]


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


def test_a_possessive_is_the_word_that_says_whose_figure_it_is():
    """`1-358` sets `with Kroeber’s Fig. 52, a, a dog` twice, and both were
    marked as this book's until the mark moved into the page where somebody could
    read it. The apostrophe is the printed evidence and the store holds the name.
    """
    assert figrefs.foreign_citation("with Kroeber’s ", NAMES | {"Kroeber"}) \
        == "Kroeber"
    assert figrefs.foreign_citation("with Nelson's ", NAMES) == "Nelson"


def test_ibid_is_somebody_else_s_book():
    """`1-277` prints `¹ Nelson, Fig. 32, p. 116.` and under it `² Ibid., Fig.
    33, p. 117.` — Nelson's Fig. 33, and it was linked to this book's. `Ibid.`
    never points at this book, which cites itself with `See p.`, so the word
    stands where a name would and takes the same furniture — including a page
    locator, which `2-069` sets before the figure: `Ibid., p. 325, Fig. 115`."""
    assert figrefs.foreign_citation("² Ibid., ", NAMES) == "Ibid."
    assert figrefs.foreign_citation("² Ibid., p. 325, ", NAMES) == "Ibid."
    assert figrefs.foreign_citation("³ Ibid., Plate XLV, ", NAMES) == "Ibid."
    assert figrefs.foreign_citation("Ibid, ", NAMES) == "Ibid."


def test_a_run_s_later_members_are_the_same_author_s():
    """The guard is asked once per numeral. For the `4` of `Ibid., Plate
    XLVIII, Figs. 3, 4` (1-285) and the `29` of `Murdoch, Eskimo Bows, Plate X,
    Fig. 27; Plate XI, Figs. 28, 29` (1-195), what stands between the name and
    the span is the references before it — furniture of the same citation,
    not prose that ends it."""
    assert figrefs.foreign_citation(
        "⁴ Ibid., Plate XLVIII, Figs. 3, ", NAMES) == "Ibid."
    assert figrefs.foreign_citation(
        "¹ Murdoch, Eskimo Bows, Plate X, Fig. 27; Plate XI, Figs. 28, ",
        NAMES | {"Murdoch"}) == "Murdoch"


def test_the_five_furniture_shapes_that_leaked():
    """Each read off the page it leaked on, when the reading view started serving
    these as real links and a sweep could count them. All seven references these
    cover were linking to this book's pictures under another author's number:
    a working link with a plausible caption under it, which is the failure the
    guard exists to prevent, surviving inside the guard. `docs/decisions.md`.
    """
    N = NAMES | {"Nelson", "Schrenck", "Teit", "Hough", "Lamp"}
    # A run past its second member: `Figs. N` was furniture and the bare numeral
    # after it was not, so 1-145's `Figs. 3, 4, 5` guarded 3 and 4 and let 5 out.
    assert figrefs.foreign_citation(
        "Schrenck, II, Plate XXXVI, Figs. 3, 4, ", N) == "Schrenck"
    assert figrefs.foreign_citation(
        "See Nelson, Plate LXXXVI, Figs. 5, 6, 20, ", N) == "Nelson"
    # A bare numeral takes the locants a numbered one does (1-226).
    assert figrefs.foreign_citation("Compare Nelson, Fig. 22, 1, ", N) == "Nelson"
    # `and` joining a run, and `also` continuing it past a semicolon (1-259).
    assert figrefs.foreign_citation(
        "Nelson, Plates LXXXVIII and ", N) == "Nelson"
    assert figrefs.foreign_citation(
        "Nelson, Plates LXXXVIII and LXXXIX; also Fig. ", N) == "Nelson"
    # The semicolon between two citations of one work (1-278).
    assert figrefs.foreign_citation(
        "Compare Teit, Fig. 127, p. 185; and Fig. ", N) == "Teit"
    # An arabic plate number — Hough numbers his plates in arabic, and this
    # book's own are roman, so it is a tell rather than an ambiguity (1-241).
    assert figrefs.foreign_citation(
        "Compare the illustration in Hough, Lamp, Plate 15, Fig. ", N) == "Hough"
    # The dash of a numeral range, the guard being asked at the 164 (2-071).
    assert figrefs.foreign_citation(
        "Compare Nelson, p. 448, Figs. 162-", N) == "Nelson"


def test_a_footnote_marker_after_a_name_ends_the_citation():
    """`illustrated by Nelson.\u00b9 Fig. 22` (1-143) is Bogoras's own figure. The
    superscript is not a decimal digit, so no numeral branch steps over it — which
    is what keeps the widened furniture off the sentence that merely mentions a
    source."""
    N = NAMES | {"Nelson"}
    assert figrefs.foreign_citation(
        "which is illustrated by Nelson.\u00b9 Fig. ", N) == ""
    assert figrefs.foreign_citation(
        "as described by Nelson,\u00b9 except that the ribs are set closer (Fig. ",
        N) == ""


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
BOXES = {"1-287": [{"n": "1", "key": "003", "caption": "Fig. 1. Ke´lE.",
                    "zone_ids": ["fig_1-287_003"]},
                   {"n": "2", "key": "001", "caption": "Fig. 2. Ke´lE.",
                    "zone_ids": ["fig_1-287_001"]}],
         "1-276": [{"n": "140", "key": "005",
                    "caption": "Fig. 140. Drum-Sticks: a, b.",
                    "zone_ids": ["fig_1-276_005", "fig_1-276_006"]}],
         "1-123": [{"n": None, "key": "001",
                    "zone_ids": ["fig_1-123_001", "fig_1-123_002"]}]}


# Every caption a leaf prints, whether or not the geometry paired it to a picture.
# `2-068` is the case: the pairing folded both pictures under Fig. 239's caption,
# so Fig. 240's is on the leaf and in no box record, and `figure_numbers.json`
# names the zones by hand. `1-313` prints two of the same number.
CAPTIONS = {ref: [b["caption"] for b in boxes if b.get("caption")]
            for ref, boxes in BOXES.items()}
CAPTIONS["2-068"] = ["Fig. 239 (??/???? a). Wooden Figure.",
                     "Fig. 240 (??/????). Leather Ornament."]
CAPTIONS["1-313"] = ["Fig. 177. One.", "Fig. 177. Other."]
BY_NUMBER["9"] = [{"ref": "1-037", "key": "001", "keys": ["001"]}]
BOXES["1-037"] = [{"n": None, "key": "001", "zone_ids": ["fig_1-037_001"],
                   "caption": "Map, by W. Bogoras and W. Jochelson. Fig. 9."}]
CAPTIONS["1-037"] = ["Map, by W. Bogoras and W. Jochelson. Fig. 9."]
BY_NUMBER["239"] = [{"ref": "2-068", "key": "004", "keys": ["004"]}]
BY_NUMBER["240"] = [{"ref": "2-068", "key": "002", "keys": ["002"]}]
BOXES["2-068"] = [{"n": "239", "key": "002",
                   "caption": "Fig. 239 (??/???? a). Wooden Figure.",
                   "zone_ids": ["fig_2-068_002", "fig_2-068_004"]}]


def _resolve(**span):
    span = {"kind": "figure", "number": "", "plate": "", **span}
    return figrefs.resolve(span, BY_NUMBER, BY_PLATE, BOXES.get, CAPTIONS.get)


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


def test_a_reference_carries_the_caption_under_the_picture():
    """A card headed `Fig. 140` names a number; the caption names the thing. It
    comes off the same leaf the picture does, matched on the store's own key."""
    assert _resolve(number="140")["caption"] == "Fig. 140. Drum-Sticks: a, b."
    assert _resolve(number="1", plate="XXI")["caption"] == "Fig. 1. Ke´lE."


def test_a_whole_plate_takes_no_caption_from_its_leaf():
    """Plate XXI is two pictures under two captions and neither is the plate's.
    Only the printed list sets that one, so this leaves it to the caller rather
    than handing back whichever caption came first."""
    assert _resolve(kind="plate", number="XXI")["caption"] == ""


def test_a_hand_numbered_figure_takes_the_caption_that_prints_its_number():
    """`2-068`: the pairing folded both pictures under Fig. 239's caption and left
    Fig. 240's paired to nothing, and `edition/figure_numbers.json` names the
    zones by hand. Matched on zone key, 240 got 239's caption and 239 got none —
    a link with the wrong caption under it. The caption is the one on the leaf
    that prints the number, which is the join the pairing cannot get wrong."""
    assert _resolve(number="239")["caption"] == \
        "Fig. 239 (??/???? a). Wooden Figure."
    assert _resolve(number="240")["caption"] == \
        "Fig. 240 (??/????). Leather Ornament."


def test_a_caption_that_parses_no_number_is_still_its_hand_numbered_figures():
    """The map on `1-037` sets its number after the title, so no caption on the
    leaf prints it and the number cannot find it. The patched zone's own record
    carries it, and its `n` is None — which is the one shape in which the record
    and not the number is the witness. Numbered 9 here because the fixture's
    `Fig. 1` is spoken for by the plate collision the tests above want."""
    assert _resolve(number="9")["caption"] == \
        "Map, by W. Bogoras and W. Jochelson. Fig. 9."


def test_a_caption_is_absent_rather_than_a_neighbours():
    """`1-313` prints Fig. 177 twice, so no single caption is the reference's. The
    picture still resolves and the caption is simply empty — never whichever
    came first."""
    out = _resolve(number="177")
    assert out["pairs"] == ["1-313/001"] and out["caption"] == ""


def test_an_unresolved_reference_always_says_which_store_declined():
    """A reader who sees no link needs to know it is a gap in `gt/fig/` and not
    an edition that does not link — every refusal names its reason."""
    for span in ({"kind": "plate", "number": "XCIX"},
                 {"kind": "figure", "number": "999", "plate": ""},
                 {"kind": "figure", "number": "2", "plate": "V"}):
        assert _resolve(**span)["why"]


# --- scan: a page reference, which has to prove itself ------------------------

def test_the_deictic_page_reference():
    """The commonest shape in the footnotes, and the one the rule is for."""
    assert _printed("See p. 15.") == ["page::15"]
    assert _printed("Compare p. 221.") == ["page::221"]
    assert _printed("añqaˊlɪt (see p. 11).") == ["page::11"]
    assert _printed("called Kiˊhi (cf. p. 30): hence") == ["page::30"]
    assert _printed("from twelve to fifteen years. See also p. 75.") == ["page::75"]


def test_a_page_run_is_a_link_each():
    """The List of Illustrations' rule, unchanged: one link for `pp. 33, 161`
    would have to pick one of two."""
    assert _printed("Compare pp. 33, 161.") == ["page::33", "page::161"]
    assert _printed("See pp. 13 and 311.") == ["page::13", "page::311"]


def test_what_follows_a_folio_is_a_place_on_it_not_a_second_folio():
    """`_SEP` continues a run only where a numeral follows, so the matter after
    the comma stays out — it locates something *on* the page just named."""
    assert _printed("See p. 141, footnote.") == ["page::141"]
    assert _printed("Compare p. 19, Footnote 2.") == ["page::19"]
    assert _printed("Compare also p. 312, Footnote 4.") == ["page::312"]


def test_a_page_locator_closing_a_citation_is_not_scanned():
    """**The failure this rule exists to refuse.** 268 page locators are printed
    across the generated corpus and only about a quarter are this book's; every
    one of these names somebody else's page, and a mark on one would open a real
    leaf of *this* book with prose that reads correctly under it."""
    for s in ("Nelson, Fig. 93, p. 271.",
              "Ibid., p. 115.",
              "Compare Nelson, Plate LXX, Fig. 12, p. 184.",
              "Boas, Baffin-Land Eskimo, Fig. 44, a, c-e, p. 34.",
              "Middendorff, IV, Part 2, p. 1105.",
              "W. H. Hooper, Ten Months among the Tents of the Tuski, p. 100."):
        assert not [x for x in figrefs.scan(s) if x["kind"] == "page"], s


def test_a_cue_the_locator_does_not_immediately_follow_is_not_one():
    """The clause that separates the deictic from a citation, and the two cases
    that fixed it. `1-066` — the *He* is Maydell, whose volume the sentence
    before it named; `1-068` — Bogoras's other book, named in the same breath.
    Both print a bare parenthesised locator and neither opens on a cue."""
    assert _printed("Maydell, I, pp. 627-680. He even asserts (p. 77) that") == []
    assert _printed("published in my “Chukchee Materials” (p. 52), a man") == []
    assert _printed("See Vol. VI, The Koryak, p. 123.") == []
    assert _printed("See Fig. 110, p. 190.") == ["figure::110"]


def test_a_page_is_never_scoped_to_a_plate():
    """`unmark` refuses a `@cRef` here for the reason it refuses one on a plate:
    a folio is an address and nothing scopes it."""
    assert figrefs.unmark("page", "15", None) == {
        "kind": "page", "number": "15", "plate": ""}
    assert figrefs.unmark("page", "15", "Plate XXI") is None


def test_page_is_a_kind_a_marked_page_can_carry():
    """`validate` names `KINDS` in its refusal, so a kind the scan emits and the
    reader does not is a mark nothing downstream could read."""
    assert "page" in figrefs.KINDS
    assert figrefs.mark({"kind": "page", "number": "15", "plate": ""}) == (
        ' type="page" n="15"')


# --- scan: a chapter, which is scanned on the plate's terms --------------------

def test_a_chapter_reference():
    """`Chapter` is furniture and the roman is the handle, so this is scanned
    permissively — the name in front of it is the discriminator, exactly as for
    a plate, and that is what a page locator has no room for."""
    assert _printed("See Chapter XII.") == ["chapter::XII"]
    assert _printed("They will be discussed at length, in Chapter XIII.") == [
        "chapter::XIII"]
    assert _printed("See Chapter VI, section on armor.") == ["chapter::VI"]


def test_a_chapter_reference_tolerates_the_stop_the_page_sets():
    """`2-004` prints `Compare Chapter. XIII.` in adjudicated ground truth, so
    it is what the leaf sets. The mark covers the roman and a stop before it
    changes nothing about which chapter is meant."""
    assert _printed("Compare Chapter. XIII.") == ["chapter::XIII"]


def test_another_author_s_chapter_is_scanned_and_the_guard_declines_it():
    """`Compare Bogdanovitch, Chapter V.` — the one of the corpus's 19 chapter
    references that is not this book's. It is *found* here, because what the page
    prints is a fact about the string; `foreign_citation` is what refuses it, and
    that division is the whole shape of this module."""
    assert _printed("Compare Bogdanovitch, Chapter V.") == ["chapter::V"]
    assert figrefs.foreign_citation("Compare Bogdanovitch, ", {"Bogdanovitch"})


def test_a_chapter_named_by_its_title_is_not_matched():
    """Deliberate. `See chapter on shamanism.` would resolve — `Shamanism` is a
    level-1 title and nothing else — but `See chapter on charms.` would have to
    choose among six entries carrying *Charms*. A rule that resolves one and
    guesses the other is worse than one that leaves both as worklist lines."""
    assert _printed("See chapter on shamanism.") == []
    assert _printed("See chapter on charms.") == []


def test_the_two_kinds_can_stand_in_one_note():
    """`1-243` sets both: a chapter and a page in one footnote."""
    assert _printed("See Chapter XII; cf. also p. 101.") == [
        "chapter::XII", "page::101"]


def test_a_chapter_is_never_scoped_to_a_plate():
    assert figrefs.unmark("chapter", "XII", None) == {
        "kind": "chapter", "number": "XII", "plate": ""}
    assert figrefs.unmark("chapter", "XII", "Plate XXI") is None


# -- the second witness: the numbers the book prints ---------------------------

PLATES = frozenset({"I", "II", "XIV", "XXXV"})
FIGURES = frozenset({"1", "2", "94", "302"})


def _span(kind, number, plate=""):
    return {"kind": kind, "number": number, "plate": plate}


def test_a_plate_past_the_book_s_last_is_not_this_book_s():
    """Schrenck's Plate XXXVI and Nelson's Plate LXXXIX. The printed List of
    Illustrations stops at XXXV, so no sentence can make them this book's."""
    assert figrefs.outside_the_book(_span("plate", "XXXVI"), PLATES, FIGURES) \
        == "this book prints no Plate XXXVI"
    assert figrefs.outside_the_book(_span("plate", "LXXXIX"), PLATES, FIGURES)
    assert figrefs.outside_the_book(_span("plate", "XIV"), PLATES, FIGURES) == ""


def test_a_figure_on_a_foreign_plate_is_judged_by_the_plate():
    """`Nelson, Plate LXXXVI, Fig. 23` — nothing can be said about how many
    figures another author put on his plate, but the plate itself is not here."""
    assert figrefs.outside_the_book(_span("figure", "23", "LXXXVI"),
                                    PLATES, FIGURES)
    assert figrefs.outside_the_book(_span("figure", "23", "XIV"),
                                    PLATES, FIGURES) == ""


def test_a_bare_figure_past_the_book_s_last():
    """Boas's Fig. 525, where the guard could not read back to the name because
    the author is named *after* the numeral — `in Boas's Central Eskimo`."""
    assert figrefs.outside_the_book(_span("figure", "525"), PLATES, FIGURES) \
        == "this book prints no Fig. 525"
    assert figrefs.outside_the_book(_span("figure", "302"), PLATES, FIGURES) == ""


def test_it_is_a_set_and_not_a_ceiling():
    """The printed list has no gap here, but a set says what a ceiling cannot and
    cannot be fooled by one appearing later."""
    assert figrefs.outside_the_book(_span("figure", "3"), PLATES, FIGURES)
    assert figrefs.outside_the_book(_span("plate", "III"), PLATES, FIGURES)


def test_knowing_nothing_is_not_an_answer():
    """A caller with no List of Illustrations knows nothing about the book's
    range. Treating that as "the book prints everything" would disarm the guard
    silently; treating it as "the book prints nothing" would refuse the corpus.
    It declines, and `foreign_citation` stands alone as it did before."""
    assert figrefs.outside_the_book(_span("plate", "XXXVI"), frozenset(),
                                    FIGURES) == ""
    assert figrefs.outside_the_book(_span("figure", "525"), PLATES,
                                    frozenset()) == ""


def test_the_two_witnesses_are_independent():
    """The prose guard reads the sentence and the range guard reads the number,
    and neither can be talked out of its answer by the other's blind spot. Boas's
    Fig. 525 is the case: no name precedes it, so the first says nothing."""
    assert figrefs.foreign_citation("compare Fig. 199, a, with Fig. ",
                                    NAMES | {"Boas"}) == ""
    assert figrefs.outside_the_book(_span("figure", "525"), PLATES, FIGURES)


def test_the_citation_s_head_is_the_name_returned():
    """`Authorities Quoted` holds Hough under his name *and* under his short
    title `Lamp`, so `Hough, Lamp, Plate 15, Fig. 3` (1-241) qualifies twice.

    The answer is shown to a reader now — it is the hover text on a refused
    reference — so it must not depend on which member of a set came first: on
    some runs the page said `Lamp's figure, not this book's`, naming a short
    title as though it were a person. The name that opens a citation governs it.
    """
    N = {"Hough", "Lamp"}
    assert figrefs.foreign_citation(
        "Compare the illustration in Hough, Lamp, Plate 15, Fig. ", N) == "Hough"
    assert figrefs.foreign_citation(
        "Compare the illustration in Hough, Lamp, Plate 15, Fig. ",
        {"Lamp", "Hough"}) == "Hough"
    # The short title alone still answers where the name is not printed.
    assert figrefs.foreign_citation("Compare Lamp, Plate 15, Fig. ", N) == "Lamp"
