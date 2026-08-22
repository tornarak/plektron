"""The caption pass: its flat store, its sheets, and the rules it selects.

Three things are worth holding here, and none of them is a line.

**The four save invariants.** They are `review.save_decisions`' and they are the
reason that function is trustworthy — full text for every key, `edited` computed
server-side, NFD in, an empty payload refused. A second implementation of them is
a second chance to drop one silently, so each is pinned.

**Rule selection off the target.** `proposal check` runs four arms that ask about
one page's lines. A caption proposal has no page and no line indices, and those
arms would fire on every one of 395 captions. The branch is taken from the key
shape rather than a flag, so what pins it is that a caption-keyed file gets the
caption rules and a line-keyed one is untouched.

**`captions` is a target and not a ref.** `norm_ref` must keep refusing it
everywhere else, or a store verb could be handed it.
"""
from __future__ import annotations

import json

import pytest

from harness import captions as C
from harness.paths import CAPTIONS, decisions_path, proposal_path, review_dir
from harness.proposal_check import caption_keyed
from harness.refs import norm_ref

KEY = "1-151|002"
OTHER = "1-049|004"


def _propose(root, blocks: dict, blind: bool | None = True) -> None:
    p = proposal_path(CAPTIONS, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc: dict = {"lines": {k: {"text": v} for k, v in blocks.items()}}
    if blind is not None:
        doc["blind"] = blind
    p.write_text(json.dumps(doc), encoding="utf-8")


# --------------------------------------------------------------- the store


def test_the_proposal_lives_beside_the_pages_and_is_not_one(tmp_path):
    """`review/captions/`, reached by the same two functions a page's pair is.

    The word is what makes `harness proposal check captions` work — a `proposal`
    verb's target is a proposal, and this names one — and keeping it inside
    `review_dir` is what stops the rest of the harness learning it.
    """
    assert review_dir(CAPTIONS, tmp_path) == tmp_path / "review" / "captions"
    assert proposal_path(CAPTIONS, tmp_path).name == "proposal.json"
    assert decisions_path(CAPTIONS, tmp_path).name == "decision.json"


def test_captions_is_not_a_ref(tmp_path):
    """The word reaches `review_dir` and nothing else.

    If `norm_ref` learned it, every store verb would accept `captions` as a page
    and go looking for `chukchi-captions.png`.
    """
    with pytest.raises(ValueError):
        norm_ref(CAPTIONS)


def test_page_dirs_does_not_read_it_as_a_page(tmp_path):
    """Being ref-shaped is what includes a directory, so this costs nothing."""
    from harness.paths import page_dirs

    _propose(tmp_path, {KEY: "x"})
    (tmp_path / "review" / "1-151").mkdir(parents=True)
    assert [d.name for d in page_dirs(tmp_path)] == ["1-151"]


def test_absent_proposal_says_who_writes_it(tmp_path):
    """Absence raises rather than returning `{}`, unlike a page's.

    There is exactly one of these, so its absence means the pass has not run —
    which is a different fact from "this page has not been read yet", of which the
    corpus has hundreds and every one legitimate.
    """
    with pytest.raises(ValueError, match="read-captions"):
        C.load_proposal(tmp_path)


# ------------------------------------------------- the four save invariants


def test_every_key_keeps_its_full_text_not_just_the_edited_ones(tmp_path):
    """`fig restore` builds `gt/fig/` from this file alone.

    If an unedited caption carried only a flag, what reached the store would
    depend on the proposal still being byte-identical — and then correcting a
    reading would silently change what "unedited" resolved to.
    """
    _propose(tmp_path, {KEY: "as read", OTHER: "also as read"})
    C.save_decisions({KEY: "as read", OTHER: "changed"}, tmp_path)
    saved = C.load_decisions(tmp_path)
    assert saved[KEY]["text"] == "as read"
    assert saved[OTHER]["text"] == "changed"


def test_edited_is_computed_here_and_not_taken_from_the_caller(tmp_path):
    """It is the pass's primary signal, so the thing measured cannot report it."""
    _propose(tmp_path, {KEY: "as read"})
    C.save_decisions({KEY: {"text": "as read", "edited": True}}, tmp_path)
    assert C.load_decisions(tmp_path)[KEY]["edited"] is False

    C.save_decisions({KEY: {"text": "different", "edited": False}}, tmp_path)
    assert C.load_decisions(tmp_path)[KEY]["edited"] is True


def test_text_is_folded_to_nfd_on_the_way_in(tmp_path):
    """Browsers submit whatever the keyboard produced; the corpus is NFD."""
    _propose(tmp_path, {KEY: "x"})
    C.save_decisions({KEY: "Uñiˊsak"}, tmp_path)          # precomposed ñ
    assert "̃" in C.load_decisions(tmp_path)[KEY]["text"]
    assert "ñ" not in C.load_decisions(tmp_path)[KEY]["text"]


def test_an_empty_save_is_refused_and_withdraw_is_how_it_is_said(tmp_path):
    """One file for the whole corpus, so an empty save is every ruling at once."""
    _propose(tmp_path, {KEY: "x"})
    C.save_decisions({KEY: "x"}, tmp_path)
    with pytest.raises(ValueError, match="every ruling"):
        C.save_decisions({}, tmp_path)
    assert C.load_decisions(tmp_path)
    C.save_decisions({}, tmp_path, withdraw=True)
    assert not C.load_decisions(tmp_path)


def test_a_save_keeps_one_prev_and_journals_what_differed(tmp_path):
    """Two saves destroy `.prev`; nothing destroys the journal."""
    _propose(tmp_path, {KEY: "x"})
    C.save_decisions({KEY: "first"}, tmp_path)
    C.save_decisions({KEY: "second"}, tmp_path)
    p = decisions_path(CAPTIONS, tmp_path)
    assert json.loads(p.with_suffix(".json.prev").read_text())["lines"][KEY]["text"] \
        == "first"
    rows = [json.loads(x) for x in
            p.with_suffix(".jsonl").read_text().splitlines()]
    assert [r["changed"] for r in rows] == [[], [KEY]]


def test_a_keyword_outside_the_closed_set_is_refused(tmp_path):
    """A free-text ruling belongs in `note`, where nothing reads it as a verdict."""
    _propose(tmp_path, {KEY: "x"})
    with pytest.raises(ValueError, match="not an adjudication keyword"):
        C.save_decisions({KEY: {"text": "x", "keyword": "PROBABLY FINE"}}, tmp_path)
    C.save_decisions({KEY: {"text": "x", "keyword": "MISPRINT"}}, tmp_path)
    assert C.load_decisions(tmp_path)[KEY]["keyword"] == "MISPRINT"


# ----------------------------------------------------------- the blind flag


@pytest.mark.parametrize("declared,expected", [(True, True), (False, False),
                                               (None, None)])
def test_blindness_is_three_valued_because_unstated_is_not_false(
        tmp_path, declared, expected):
    """A skill has no guard hook, so this is a declaration, not an enforcement.

    What it buys is that `fig witness` can say which it was. A file that says
    nothing is not the same claim as one that says `false`, and collapsing the two
    would make an old proposal indistinguishable from a contaminated one.
    """
    _propose(tmp_path, {KEY: "x"}, blind=declared)
    assert C.proposal_is_blind(tmp_path) is expected


# ------------------------------------------------------- the cross-page guard


def test_patch_refuses_the_whole_form_when_one_key_moved(tmp_path):
    """All-or-nothing, and prior-text — `review.patch_decisions`' pair.

    Every document this pass renders is cross-page, which is exactly the shape
    that once wrote a field belonging to a key the reviewer was not looking at.
    """
    _propose(tmp_path, {KEY: "a", OTHER: "b"})
    C.save_decisions({KEY: "a", OTHER: "b"}, tmp_path)
    C.save_decisions({KEY: "moved under the form", OTHER: "b"}, tmp_path)

    with pytest.raises(ValueError, match="changed under this document"):
        C.patch([{"key": KEY, "prior": "a", "text": "one"},
                 {"key": OTHER, "prior": "b", "text": "two"}], tmp_path)
    # Neither landed: the good edit is not applied on the strength of the bad one.
    assert C.load_decisions(tmp_path)[OTHER]["text"] == "b"


def test_patch_will_not_invent_a_ruling(tmp_path):
    """A patch edits a decision; it does not make one."""
    _propose(tmp_path, {KEY: "a", OTHER: "b"})
    C.save_decisions({KEY: "a"}, tmp_path)
    with pytest.raises(ValueError, match="no saved decision"):
        C.patch([{"key": OTHER, "prior": "b", "text": "x"}], tmp_path)


# -------------------------------------------------- rule selection by target


def test_the_key_shape_is_what_says_which_rules_apply():
    """Read off the file, so a flag cannot disagree with the thing it describes."""
    assert caption_keyed({"lines": {KEY: {}, OTHER: {}}})
    assert not caption_keyed({"lines": {"0": {}, "1": {}}})
    assert not caption_keyed({"lines": {}})
    # Mixed is not caption-keyed: one line index means the line arms still apply,
    # and guessing which half to run would be worse than running the page rules.
    assert not caption_keyed({"lines": {KEY: {}, "1": {}}})


# ---------------------------------------------------------------- the sheets

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _fig_alto(tmp_path, ref: str, blocks) -> None:
    """A figure-track ALTO. `blocks` is (id, label, x, y, w, h)."""
    p = tmp_path / "gt" / "fig" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<TextBlock ID="{i}" TAGREFS="{"BT77" if lab.endswith("FigDesc") else "BT78"}"'
        f' HPOS="{x}.0" VPOS="{y}.0" WIDTH="{w}.0" HEIGHT="{h}.0"/>'
        for i, lab, x, y, w, h in blocks)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
        f"<PrintSpace>{body}</PrintSpace></Page></Layout><Tags>"
        '<OtherTag ID="BT77" TYPE="type" LABEL="GraphicZone-FigDesc"/>'
        '<OtherTag ID="BT78" TYPE="type" LABEL="GraphicZone"/>'
        "</Tags></alto>", encoding="utf-8")


def _raster(tmp_path, ref: str) -> None:
    from PIL import Image
    p = tmp_path / "scans" / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (2824, 3897), 255).save(p)


def test_a_landscape_caption_is_padded_on_the_reading_axis(tmp_path):
    """Above and below, because that is where the missing printed line would be.

    The pad is the whole reason a caption strip is not a `fig crops` crop: a box
    drawn round the wrong number of lines is this store's commonest defect, and a
    strip cut at the declared edge cannot show the line that was left out.
    """
    from harness.figures import caption_strips

    _fig_alto(tmp_path, "1-151", [("fig_1-151_002", "GraphicZone-FigDesc",
                                   400, 1000, 600, 100)])
    _raster(tmp_path, "1-151")
    (key, strip, rec), = caption_strips("1-151", tmp_path, pad=0.5)
    assert key == "1-151|002"
    assert rec["orientation"] == "upright"
    assert rec["pad"] == 50
    # Grown on y by the pad at each end; x untouched.
    assert strip.size == (600, 100 + 2 * 50)


def test_a_portrait_caption_is_turned_upright_and_padded_on_x(tmp_path):
    """A plate sets its caption rotated beside the picture, reading bottom-to-top.

    Two things are pinned. The strip comes back **wider than tall** — it was
    rotated, so a reader meets left-to-right type. And the pad went on x, because
    for rotated type the next printed line stacks sideways; padding y would grow
    the strip along the line it already has and show nothing new.
    """
    from harness.figures import caption_strips

    _fig_alto(tmp_path, "1-049", [("fig_1-049_004", "GraphicZone-FigDesc",
                                   400, 1000, 90, 500)])
    _raster(tmp_path, "1-049")
    (_, strip, rec), = caption_strips("1-049", tmp_path, pad=0.5)
    assert rec["orientation"] == "rotated"
    assert rec["pad"] == 45
    # 90 wide + 2*45 pad = 180 on the page's x, which becomes the strip's height.
    assert strip.size == (500, 180)
    assert strip.width > strip.height


def test_pad_zero_cuts_at_the_declared_edge(tmp_path):
    """Offered so the choice is visible, not because it is a good default."""
    from harness.figures import caption_strips

    _fig_alto(tmp_path, "1-151", [("fig_1-151_002", "GraphicZone-FigDesc",
                                   400, 1000, 600, 100)])
    _raster(tmp_path, "1-151")
    (_, strip, rec), = caption_strips("1-151", tmp_path, pad=0.0)
    assert rec["pad"] == 0
    assert strip.size == (600, 100)


def test_only_figdesc_blocks_become_strips(tmp_path):
    """A `GraphicZone` is a picture. `fig crops` is what cuts those."""
    from harness.figures import caption_strips

    _fig_alto(tmp_path, "1-151", [
        ("fig_1-151_001", "GraphicZone", 400, 100, 600, 800),
        ("fig_1-151_002", "GraphicZone-FigDesc", 400, 1000, 600, 100)])
    _raster(tmp_path, "1-151")
    assert [k for k, _, _ in caption_strips("1-151", tmp_path)] == ["1-151|002"]


def test_the_manifest_keys_every_strip_back_to_its_sheet(tmp_path):
    """What the reader and the review page both read back.

    Order is reading order — ref, then position down the page — so a sheet is
    walked the way the book is.
    """
    from harness.figures import write_caption_sheets

    _fig_alto(tmp_path, "1-151", [
        ("fig_1-151_003", "GraphicZone-FigDesc", 400, 2000, 600, 100),
        ("fig_1-151_002", "GraphicZone-FigDesc", 400, 1000, 600, 100)])
    _raster(tmp_path, "1-151")
    man = write_caption_sheets(tmp_path / "out", tmp_path)

    assert man["captions"] == 2
    assert list(man["blocks"]) == ["1-151|002", "1-151|003"]
    for rec in man["blocks"].values():
        assert (tmp_path / "out" / rec["sheet"]).exists()
    assert json.loads((tmp_path / "out" / "manifest.json").read_text())["captions"] == 2


def test_a_page_with_no_caption_block_contributes_nothing(tmp_path):
    """`3-006` and `3-007` carry a picture the book captions nowhere."""
    from harness.figures import write_caption_sheets

    _fig_alto(tmp_path, "3-006", [("fig_3-006_001", "GraphicZone",
                                   400, 100, 600, 800)])
    _raster(tmp_path, "3-006")
    assert write_caption_sheets(tmp_path / "out", tmp_path)["captions"] == 0


def test_zoom_magnifies_the_same_block_the_sheet_showed(tmp_path):
    """The region is `caption_strips`' own, not a second guess at where it is.

    That is the whole reason the verb exists: the alternative a reader reaches for
    is `convert` with hand-typed bounds, which names the wrong region the moment a
    coordinate is fat-fingered and which no later reader can check.
    """
    from harness.figures import write_caption_zoom

    _fig_alto(tmp_path, "1-049", [("fig_1-049_006", "GraphicZone-FigDesc",
                                   400, 1000, 600, 100)])
    _raster(tmp_path, "1-049")
    rows = write_caption_zoom("1-049|006", tmp_path / "z", tmp_path, zoom=2)
    assert rows and rows[0]["zoom"] == 2
    assert rows[0]["key"] == "1-049|006"
    assert (tmp_path / "z").exists()


def test_zoom_refuses_past_the_ceiling(tmp_path):
    """4x is the rung above which a magnifier returns the resampler, not the page."""
    from harness.figures import write_caption_zoom

    _fig_alto(tmp_path, "1-049", [("fig_1-049_006", "GraphicZone-FigDesc",
                                   400, 1000, 600, 100)])
    _raster(tmp_path, "1-049")
    with pytest.raises(ValueError, match="past the ceiling"):
        write_caption_zoom("1-049|006", tmp_path / "z", tmp_path, zoom=8)


def test_zoom_needs_a_caption_key_not_a_ref(tmp_path):
    """A page has several captions, so a ref names no one block to magnify."""
    from harness.figures import write_caption_zoom

    _fig_alto(tmp_path, "1-049", [("fig_1-049_006", "GraphicZone-FigDesc",
                                   400, 1000, 600, 100)])
    _raster(tmp_path, "1-049")
    with pytest.raises(ValueError, match="not a caption key"):
        write_caption_zoom("1-049", tmp_path / "z", tmp_path)
    with pytest.raises(ValueError, match="names no caption block"):
        write_caption_zoom("1-049|404", tmp_path / "z", tmp_path)


def test_zoom_takes_no_pad_where_the_sheet_takes_one(tmp_path):
    """The sheet pads to show a line the box may have missed; a zoom asks about a
    glyph *inside* the box, so padding would spend magnification on neighbours."""
    from harness.figures import caption_strips, write_caption_zoom

    _fig_alto(tmp_path, "1-049", [("fig_1-049_006", "GraphicZone-FigDesc",
                                   400, 1000, 600, 100)])
    _raster(tmp_path, "1-049")
    (_, unpadded, _), = caption_strips("1-049", tmp_path, pad=0.0)
    rows = write_caption_zoom("1-049|006", tmp_path / "z", tmp_path, zoom=1)
    # One strip at 1x, so the sheet carries the block's own 100px height.
    assert unpadded.height == 100
    assert len(rows) == 1


# --------------------------------------------------------- the fold, and restore


def test_a_lines_own_indentation_is_folded_away_on_write(tmp_path):
    """Where a printed line sits is the compositor's business, not the text's.

    It reaches the store through a textarea — the adjudicator types a continuation
    line and indents it to match the page, which is the natural thing to do. It
    also trips §2.9's multi-space rule, which scans raw source and cannot tell an
    indent *inside a string value* from sentence spacing.
    """
    _propose(tmp_path, {KEY: "a"})
    C.save_decisions({KEY: "Fig. 213. Compass.\n  “sun has gone out”).\n\ttab too"},
                     tmp_path)
    assert C.load_decisions(tmp_path)[KEY]["text"] == (
        "Fig. 213. Compass.\n“sun has gone out”).\ntab too")


def test_the_fold_does_not_touch_the_break_itself(tmp_path):
    """Only the space around a line. The break is load-bearing: 31 of the 196
    multi-line captions carry a hyphen at one, and a wrap hyphen and a compound
    hyphen are not mechanically separable without it."""
    _propose(tmp_path, {KEY: "a"})
    C.save_decisions({KEY: "Bundle of Leaf-\nTobacco."}, tmp_path)
    assert C.load_decisions(tmp_path)[KEY]["text"] == "Bundle of Leaf-\nTobacco."


def test_restore_writes_one_string_per_printed_line(tmp_path):
    """The block's own bbox on the TextLine, no geometry on the Strings.

    Geometry-less `String` is the corpus's universal practice — 27,595 of 27,595
    in `gt/ocr/` carry no HPOS. Several under one TextLine is the new part, and it
    is new because a caption's printed lines are a property of its one box.
    """
    from lxml import etree

    from harness.figures import alto_for, block_text

    _fig_alto(tmp_path, "1-086", [("fig_1-086_002", "GraphicZone-FigDesc",
                                   845, 2660, 580, 90)])
    _propose(tmp_path, {"1-086|002": "Bundle of Leaf-\nTobacco."})
    C.restore(tmp_path, commit=True)

    blk = etree.parse(str(alto_for("1-086", tmp_path))).find(".//{*}TextBlock")
    assert block_text(blk) == ["Bundle of Leaf-", "Tobacco."]
    tl = blk.find("{*}TextLine")
    # The block's own bbox, copied verbatim rather than re-derived — so a store
    # whose coordinates are floats keeps floats, and the TextLine can never claim
    # a region the block does not.
    assert [tl.get(k) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")] == \
           [blk.get(k) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]
    assert all(s.get("HPOS") is None for s in tl.findall("{*}String"))


def test_restore_refuses_a_block_with_neither_ruling_nor_reading(tmp_path):
    """A partial restore leaves holes nothing can see: `fig check` finds an absent
    block, never an absent caption nobody expected."""
    _fig_alto(tmp_path, "1-086", [
        ("fig_1-086_002", "GraphicZone-FigDesc", 845, 2660, 580, 90),
        ("fig_1-086_004", "GraphicZone-FigDesc", 845, 2800, 580, 90)])
    _propose(tmp_path, {"1-086|002": "only one of the two"})
    with pytest.raises(ValueError, match="neither a ruling nor a reading"):
        C.restore(tmp_path, commit=True)


def test_restore_will_not_overwrite_text_without_force(tmp_path):
    """Once this has run every FigDesc holds a caption, so a second pass is a
    deliberate act and `force` is how a caller says they meant it."""
    _fig_alto(tmp_path, "1-086", [("fig_1-086_002", "GraphicZone-FigDesc",
                                   845, 2660, 580, 90)])
    _propose(tmp_path, {"1-086|002": "first"})
    C.restore(tmp_path, commit=True)
    _propose(tmp_path, {"1-086|002": "second"})

    assert C.restore(tmp_path, commit=True)["skipped_holding_text"] == 1
    from lxml import etree

    from harness.figures import alto_for, block_text
    blk = etree.parse(str(alto_for("1-086", tmp_path))).find(".//{*}TextBlock")
    assert block_text(blk) == ["first"]
    C.restore(tmp_path, force=True, commit=True)
    blk = etree.parse(str(alto_for("1-086", tmp_path))).find(".//{*}TextBlock")
    assert block_text(blk) == ["second"]


def test_a_geometry_save_carries_ratified_caption_text_across(tmp_path):
    """**The quietest destructive path in this store, and it is closed here.**

    `save_figs` mints a whole ALTO from geometry, so after the migration an
    ordinary box edit in the browser would delete every ratified caption on the
    page — well-formed file, no check failing at save time, indistinguishable from
    a normal save.
    """
    from lxml import etree

    from harness.figures import alto_for, block_text, save_figs, zones

    _fig_alto(tmp_path, "1-086", [("fig_1-086_002", "GraphicZone-FigDesc",
                                   845, 2660, 580, 90)])
    _raster(tmp_path, "1-086")
    _propose(tmp_path, {"1-086|002": "Bundle of Leaf-\nTobacco."})
    C.restore(tmp_path, commit=True)

    blocks = [{"label": b["label"], "id": b["id"], "x0": b["hpos"],
               "y0": b["vpos"], "x1": b["hpos"] + b["width"],
               "y1": b["vpos"] + b["height"] + 25} for b in zones("1-086", tmp_path)]
    save_figs("1-086", blocks, tmp_path)

    blk = etree.parse(str(alto_for("1-086", tmp_path))).find(".//{*}TextBlock")
    assert block_text(blk) == ["Bundle of Leaf-", "Tobacco."]
    assert blk.get("HEIGHT") == "115"          # the geometry edit did land


def test_a_geometry_save_refuses_to_drop_a_block_holding_ratified_text(tmp_path):
    """Withdrawing a picture is `fig delete`. Withdrawing a caption a human ruled
    on is not something a geometry save does silently."""
    from harness.figures import save_figs, zones

    _fig_alto(tmp_path, "1-086", [
        ("fig_1-086_001", "GraphicZone", 845, 2000, 580, 600),
        ("fig_1-086_002", "GraphicZone-FigDesc", 845, 2660, 580, 90)])
    _raster(tmp_path, "1-086")
    _propose(tmp_path, {"1-086|002": "a ruling stands behind this"})
    C.restore(tmp_path, commit=True)

    keep = [{"label": b["label"], "id": b["id"], "x0": b["hpos"], "y0": b["vpos"],
             "x1": b["hpos"] + b["width"], "y1": b["vpos"] + b["height"]}
            for b in zones("1-086", tmp_path) if b["label"] == "GraphicZone"]
    with pytest.raises(ValueError, match="ratified caption text"):
        save_figs("1-086", keep, tmp_path)
    save_figs("1-086", keep, tmp_path, drop_text=True)   # said explicitly, allowed


def test_check_swaps_the_orphan_rule_rather_than_firing_the_line_one(tmp_path):
    """The whole point of the branch: a caption key resolves against `gt/fig/`.

    Under the line rule every one of these would be reported as "line index is not
    in the store", which is 395 findings and no information.
    """
    from harness.proposal_check import check

    (tmp_path / "gt" / "fig").mkdir(parents=True)
    (tmp_path / "gt" / "fig" / "chukchi-1-151.xml").write_text(
        '<?xml version="1.0"?>'
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Tags>'
        '<OtherTag ID="BT1" LABEL="GraphicZone-FigDesc"/></Tags><Layout><Page>'
        '<PrintSpace><TextBlock ID="fig_1-151_002" TAGREFS="BT1" HPOS="1" '
        'VPOS="1" WIDTH="9" HEIGHT="9"/></PrintSpace></Page></Layout></alto>',
        encoding="utf-8")
    _propose(tmp_path, {KEY: "present", "1-151|404": "absent"})

    issues = check(proposal_path(CAPTIONS, tmp_path), root=tmp_path)
    orphans = [i for i in issues if "GraphicZone-FigDesc" in i["issue"]]
    assert [i["line"] for i in orphans] == ["1-151|404"]
    assert not any("line index" in i["issue"] for i in issues)
