"""`harness tei generate`: the rules build the page, the reader judges it.

What is being pinned here is a division of labour, not a file format. Every test
below is one of two claims:

* **the store already knew this**, so the generator must emit it and the collation
  pass must never be asked to re-derive it — paragraph boundaries off the keyed
  `MainZone-P`/`MainZone-Continued` labels, the folio off the running title, the
  apparatus dropped, the footnote block found;
* **the store cannot know this**, so the generator must emit a comment naming the
  question and must not answer it — which zone in `MainZone-Other` is a heading,
  where a note anchors, what language a form is in, where a figure is discussed.

The second set matters more. A generator that guesses produces well-formed TEI
carrying a judgement nobody made, which is this project's defining failure shape;
a generator that leaves a marked hole produces a worklist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_scan

from harness import generate as gen
from harness.detectors import join_broken_words
from harness.tests.test_entities import entry
from harness.tests.test_lexicon_tokens import nfd
from harness.zones import save_zones

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

#: The real repo, for the one thing a `tmp_path` cannot supply: `data/tei_all.rng`
#: is the committed schema and conformance is a claim about that file, not about a
#: copy of it.
REPO = Path(__file__).resolve().parent.parent.parent

# A page's worth of geometry, in the real store's pixel scale — the zone track is
# fixed-width bands of a measured column, so x is constant and only y separates
# them. Heights are well over `min_zone_h_px` (30) so nothing is consolidated away.
X0, X1 = 307, 2085
LINE_H = 45


def band(label: str, y0: int, y1: int, i: int) -> dict:
    return {"id": f"z{i}", "label": label, "x0": X0, "y0": y0, "x1": X1, "y1": y1}


def alto(tmp_path: Path, ref: str, blocks: list[tuple[str, list[tuple[str, int]]]]):
    """Write `gt/ocr/` for the page: blocks of `(label, [(text, vpos), ...])`.

    Hand-built rather than round-tripped through a writer because `gt/ocr/` is
    eScriptorium's shape and nothing in the harness authors it — `restore` merges
    into an existing export. The tags block carries `LABEL` and the blocks point at
    it through `TAGREFS`, which is the one detail that matters: that is how a zone
    label reaches a line, and reading the tag *id* instead is the mistake this
    fixture would hide if it used matching ids.
    """
    tags, body = [], []
    for i, (label, lines) in enumerate(blocks, start=1):
        tags.append(f'<OtherTag ID="T{i}" TYPE="type" LABEL="{label}"/>')
        tl = "".join(
            f'<TextLine ID="l{i}_{j}" HPOS="{X0}" VPOS="{v}" WIDTH="1700" '
            f'HEIGHT="{LINE_H}"><String CONTENT="{t}"/></TextLine>'
            for j, (t, v) in enumerate(lines, start=1))
        body.append(f'<TextBlock ID="b{i}" HPOS="{X0}" VPOS="{lines[0][1]}" '
                    f'WIDTH="1700" HEIGHT="{LINE_H * len(lines)}" '
                    f'TAGREFS="T{i}">{tl}</TextBlock>')
    p = tmp_path / "gt" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
        f'<PrintSpace>{"".join(body)}</PrintSpace></Page></Layout>'
        f'<Tags>{"".join(tags)}</Tags></alto>', encoding="utf-8")
    return p


def stores(tmp_path: Path, ref: str, blocks, bands=None) -> None:
    """Both stores for one page, the blank raster `save_zones` measures, and the
    zone config.

    The raster is blank, so `paragraph_starts` finds no ink and reports nothing:
    the bands that come back are the keyed ones exactly. That isolates what the
    *labels* carry — the claim these tests make — from what the indent check says
    about them, while still exercising the real code path rather than the degraded
    one.

    **The config is copied in because without it that sentence was false.**
    `paragraph_starts` loads it, `_bands` catches what it raises, and every fixture
    here was quietly taking the no-raster path — including the test that asserts
    the no-raster path, which passed for the wrong reason and would have passed
    with the raster present.
    """
    cfg = tmp_path / "data"
    cfg.mkdir(exist_ok=True)
    (cfg / "zones_config.json").write_bytes(
        (REPO / "data" / "zones_config.json").read_bytes())
    write_scan(tmp_path, ref)
    alto(tmp_path, ref, blocks)
    save_zones(ref, bands if bands is not None else bands_for(blocks), tmp_path)


def page(tmp_path: Path, ref: str, blocks, bands=None):
    stores(tmp_path, ref, blocks, bands)
    return gen.build(ref, tmp_path)


def bands_for(blocks) -> list[dict]:
    """Bands whose y-ranges exactly abut the blocks written by `alto`."""
    out, y = [], 200
    for i, (label, lines) in enumerate(blocks, start=1):
        out.append(band(label, y, y + LINE_H * len(lines), i))
        y += LINE_H * len(lines)
    return out


def lines_at(texts: list[str], y0: int = 200) -> list[tuple[str, int]]:
    return [(t, y0 + i * LINE_H) for i, t in enumerate(texts)]


# --------------------------------------------------------- what the store knows

def test_the_keyed_labels_are_the_paragraph_boundaries(tmp_path):
    """`MainZone-P` opens a paragraph and `MainZone-Continued` does not — a human
    keyed that on all 832 pages, and it is the fact the collation pass used to
    re-derive by looking at the raster.

    **A continued band joins the paragraph above it rather than starting one.**
    This test asserted three paragraphs for years while its own first sentence
    said why there are two: `Continued` was mapped to `p` like `P` and emitted a
    block of its own, so a paragraph running across a band boundary came out broken
    mid-sentence. The store said so the whole time.

    Fifteen paragraphs over the corpus — most `Continued` bands open their page and
    are unaffected (`test_a_page_opening_continued_is_still_one_paragraph`).
    """
    blocks = [("MainZone-P", lines_at(["First para line one.",
                                       "First para line two."])),
              ("MainZone-P", lines_at(["Second para opens here."], 290)),
              ("MainZone-Continued", lines_at(["and this continues it."], 335))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["paragraphs"] == 2
    assert "<p>First para line one.\nFirst para line two.</p>" in doc
    assert "<p>Second para opens here.\nand this continues it.</p>" in doc


def test_a_run_of_continued_bands_is_one_paragraph(tmp_path):
    """Three bands, one paragraph. The run is what a page with a figure in it
    looks like: prose, picture, prose, all one paragraph, and the middle band
    keyed `Continued` precisely to say so."""
    blocks = [("MainZone-P", lines_at(["It opens here"])),
              ("MainZone-Continued", lines_at(["and runs on"], 245)),
              ("MainZone-Continued", lines_at(["and ends here."], 290))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["paragraphs"] == 1
    assert "<p>It opens here\nand runs on\nand ends here.</p>" in doc


def test_a_page_opening_continued_is_still_one_paragraph(tmp_path):
    """A page whose first band is `Continued` continues the page before it. There
    is nothing above it to join, so it opens a paragraph here — the alternative is
    dropping the band, and a `<p>` that begins mid-sentence is the honest record of
    what the page prints."""
    blocks = [("MainZone-Continued", lines_at(["continues from the page before."])),
              ("MainZone-P", lines_at(["A fresh one."], 245))]
    _, rep = page(tmp_path, "1-021", blocks)
    assert rep["paragraphs"] == 2


def test_the_page_is_a_pure_function_of_the_tracked_stores(tmp_path):
    """**Delete the raster and the same stores build the same file, byte for
    byte.** The generated page is `gt/zones/` + `gt/ocr/` + the tracked apparatus
    and nothing else, so a fresh clone — which has no `scans/`, that tree being
    derived and gitignored — reproduces what the last run produced.

    It did not hold until the first-line indent check moved out. That check reads
    the raster, and while it lived here a page built from identical stores differed
    by whichever specks of dirt the scan happened to carry: as structure at first,
    since it cut keyed bands, and then as a comment. Both are content in the
    artifact. It gates `gt/zones/` now, which is the store its findings are
    answered in — `harness zones paragraphs`, ruled in `gt/zones/_para_exempt.json`.
    """
    blocks = [("MainZone-P", lines_at(["Opens here.", "and runs on."])),
              ("MainZone-Continued", lines_at(["and finishes here."], 245))]
    stores(tmp_path, "1-021", blocks)
    with_raster, rep = gen.build("1-021", tmp_path)
    (tmp_path / "scans" / "chukchi-1-021.png").unlink()
    without_raster, rep2 = gen.build("1-021", tmp_path)
    assert with_raster == without_raster
    assert rep == rep2
    assert rep["paragraphs"] == 1        # the `Continued` band joins the one above


def test_the_printed_line_breaks_survive(tmp_path):
    """Kept because they cost nothing — TEI collapses whitespace in prose — and
    they are what lets a reviewer read the file against the raster a line at a
    time, which is the comparison the whole pass rests on."""
    blocks = [("MainZone-P", lines_at(["one", "two", "three"]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "<p>one\ntwo\nthree</p>" in doc


def test_the_apparatus_leaves_the_body_and_its_folio_becomes_the_pb(tmp_path):
    """The running head is the printer's text, not the author's — but it carries
    the folio, which is where page numbering enters the project. Dropped from the
    body and promoted to `<pb n>`, never both and never neither.

    The folio stands **alone on its own line**, which is the store's real shape and
    not a convenience: `gt/ocr/` for `1-022` holds `'2'` and `'2 BOGORAS, THE
    CHUKCHEE.'` as two lines, because a human boxed the number separately. That is
    what lets `_FOLIO_RE` stay strict enough to refuse a recognizer's `2S` for `28`
    rather than repair it."""
    blocks = [("RunningTitleZone", lines_at(["12", "12 BOGORAS, THE CHUKCHEE."])),
              ("MainZone-P", lines_at(["Body text."], 290))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["folio"] == "12" and rep["folio_from"] == "RunningTitleZone"
    assert '<pb n="12"/>' in doc
    assert "BOGORAS, THE CHUKCHEE" not in doc


def test_an_unparsed_folio_is_a_hole_not_a_guess(tmp_path):
    """`2S` for `28` must fail and stay failed. Nothing here repairs a folio, and
    a `<pb>` with no `@n` plus a comment is the honest state — the alternative is
    a page number nobody read, indistinguishable from one somebody did."""
    blocks = [("MainZone-P", lines_at(["Body text with no running title."]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["folio"] is None
    assert "<pb/>" in doc and "no folio parsed" in doc


def test_a_note_is_split_at_its_marker_and_the_marker_is_marked_in_place(tmp_path):
    """Both halves are the printer's own marks, so both are rules rather than
    readings. The note begins where its superscript is set; a reference is where
    the same character stands in the prose.

    **Nothing moves.** The note stays at the foot and the marker stays in the
    sentence, wrapped in a `<ref>` — the same act as marking a cross-reference,
    carrying the same `#mz`. It used to be spliced into the prose *at* the marker
    with the character deleted, which cost a note the ability to be referenced
    twice and cost the body a glyph the ground-truth pass had adjudicated.

    `@n` is the **digit**: the collator contract has always specified an integer,
    and `.noteref` superscripts whatever it holds."""
    blocks = [("MainZone-P", lines_at(["Body text.¹"])),
              ("MarginTextZone-Notes",
               lines_at(["¹ See the authorities quoted."], 245))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["notes"] == 1 and rep["notes_anchored"] == 1
    assert rep["noterefs"] == 1
    assert '<p>Body text.<ref type="note" n="1" resp="#mz">¹</ref></p>' in doc
    assert '<note n="1" place="bottom">See the authorities quoted.</note>' in doc


def test_the_thin_space_before_a_marker_is_left_exactly_as_printed(tmp_path):
    """The book sets a space ahead of the raised digit (`1-100`: `[albino] ¹)`),
    and it stays. **The rule that used to eat it is gone with the splice.** A
    `<note>` standing *in place of* a marker had to set tight against the
    character the marker followed, or the space it left behind was stranded and
    `validate` errored on it; nothing stands in place of a marker now, so the
    typesetting is simply the print, kept as printed."""
    blocks = [("MainZone-P", lines_at(["the albino ¹ was taken."])),
              ("MarginTextZone-Notes", lines_at(["¹ A note."], 245))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert ('<p>the albino <ref type="note" n="1" resp="#mz">¹</ref> '
            'was taken.</p>') in doc


def test_a_line_break_before_a_marker_is_not_eaten(tmp_path):
    """The printed line breaks are kept — they are what lets a reviewer read the
    file against the raster a line at a time — so a marker the compositor pushed
    onto the next line must not silently join the two. Nothing consumes anything
    around a marker now, so this holds by construction rather than by a rule
    about which whitespace may be eaten."""
    blocks = [("MainZone-P", lines_at(["the albino", "¹ was taken."])),
              ("MarginTextZone-Notes", lines_at(["¹ A note.", "and more."], 290))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert 'the albino\n<ref type="note" n="1" resp="#mz">¹</ref> was taken.' in doc


def test_several_notes_in_one_zone_become_several_notes(tmp_path):
    """`MarginTextZone-Notes` is one zone for the whole apparatus, which used to
    mean one `<note>` holding every note's text — rendered as a single marker at
    the foot carrying three notes at once."""
    blocks = [("MainZone-P", lines_at(["One¹ and two² here."])),
              ("MarginTextZone-Notes",
               lines_at(["¹ First note.", "² Second note, which",
                         "runs to a second line."], 245))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["notes"] == 2 and rep["notes_anchored"] == 2
    assert '<note n="1" place="bottom">First note.</note>' in doc
    assert ('<note n="2" place="bottom">Second note, which\n'
            'runs to a second line.</note>') in doc


def test_a_marker_that_reads_nowhere_in_the_prose_stays_at_the_foot(tmp_path):
    """The refusal half. Notes in this book anchor on their own page, so a marker
    with no match means it did not read — and the comment says that rather than
    inventing a facing page for it to belong to."""
    blocks = [("MainZone-P", lines_at(["Body text with no marker in it."])),
              ("MarginTextZone-Notes", lines_at(["¹ An orphan."], 245))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["notes"] == 1 and rep["notes_anchored"] == 0
    assert rep["noterefs"] == 0
    assert '<note n="1" place="bottom">An orphan.</note>' in doc
    assert "<ref type=\"note\"" not in doc


def test_a_marker_printed_twice_is_two_references_to_one_note(tmp_path):
    """**This is the inversion.** Two markers reading `¹` used to be refused —
    "which one anchors it is a reading" — because a spliced note can only be in
    one place, so the pass had to choose and would not. It is not a choice: the
    printer set both, and both refer to the one note at the foot. `1-147` and
    `1-226` are the corpus's instances, and they were the last two note flags in
    it."""
    blocks = [("MainZone-P", lines_at(["First¹ and again¹ here."])),
              ("MarginTextZone-Notes", lines_at(["¹ Ambiguous."], 245))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["notes"] == 1 and rep["notes_anchored"] == 1
    assert rep["noterefs"] == 2
    assert doc.count('<ref type="note" n="1" resp="#mz">¹</ref>') == 2
    assert doc.count('<note n="1" place="bottom">Ambiguous.</note>') == 1
    assert "is a reading" not in doc


def test_a_note_whose_marker_did_not_read_gets_no_n(tmp_path):
    """Four blocks in the corpus open with note text and no superscript — the
    recognizer dropped it at the head of the zone. That note is kept whole with no
    `@n` rather than folded into the note below it, which would answer the
    question of which note it is."""
    blocks = [("MainZone-P", lines_at(["Body text.¹"])),
              ("MarginTextZone-Notes",
               lines_at(["Jackson, II, p. 17.", "¹ A real one."], 245))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["notes"] == 2
    assert '<note place="bottom">Jackson, II, p. 17.</note>' in doc
    assert "the recognizer dropped it" in doc


def test_a_quote_zone_becomes_a_quote(tmp_path):
    blocks = [("MainZone-Quote", lines_at(["Quoted matter."]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["quotes"] == 1 and "<quote>" in doc


def test_a_caption_line_is_not_body_text(tmp_path):
    """The project holds a *human* reading of every caption in `data/readings.md`,
    and putting the recognizer's copy in the body too would hand the reviewer two
    witnesses of different rank and invite reconciling them."""
    blocks = [("MainZone-P", lines_at(["Body text."]))]
    stores(tmp_path, "1-021", blocks)
    # A figure zone covering the line makes `page_lines` mark it `in_figdesc`.
    fig = tmp_path / "gt" / "fig" / "chukchi-1-021.xml"
    fig.parent.mkdir(parents=True, exist_ok=True)
    fig.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
        f'<PrintSpace><TextBlock ID="g1" HPOS="{X0}" VPOS="190" WIDTH="1700" '
        f'HEIGHT="80" TAGREFS="T1"/></PrintSpace></Page></Layout>'
        f'<Tags><OtherTag ID="T1" TYPE="type" LABEL="GraphicZone-FigDesc"/></Tags>'
        f'</alto>', encoding="utf-8")
    doc, _ = gen.build("1-021", tmp_path)
    assert "Body text." not in doc


# ----------------------------------------------------- what the store cannot know

def test_mainzone_other_is_a_question_and_not_an_answer(tmp_path):
    """`MainZone-Other` is the catch-all — headings, tables, verse, captions — and
    its `rank: null` says the store declines to order it. So the generator declines
    to shape it, and marks it instead. Guessing `<head>` here would be inventing a
    structural claim from a label that explicitly carries none."""
    blocks = [("MainZone-Other", lines_at(["THE CHUKCHEE."]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["unresolved"] == 1
    assert "unresolved zone (MainZone-Other)" in doc
    assert "<head>" not in doc and "<table>" not in doc


def test_a_ratified_form_arrives_in_place_with_no_language(tmp_path):
    """The word is *there*, and the language is not.

    The glyphs are adjudicated and a rule copies them, exactly as it copies every
    other character of the line — so putting them in costs nothing in fidelity.
    They used to be withheld, which was right when the pass authored the file from
    a plaintext draft and a model might have retyped them; once the generator
    wrote the file that stopped buying anything and started costing the reviewer a
    lookup from `index="1"` to `tier1_terms[1]` before it could judge a word it
    could not see.

    The *language* is not adjudicated by anything: `tier1_terms` is a floor over
    inventory marks with no language awareness, so it fires on a German surname
    carrying a combining diaeresis exactly as on a Chukchee form. A generator
    naming a language would be inferring one from the shape of a word."""
    blocks = [("MainZone-P", lines_at(["the form kełiˊlın here"]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["handles"] == 1
    assert '<foreign index="1">kełiˊlın</foreign>' in doc
    assert "xml:lang" not in doc


def test_the_handle_is_what_the_gate_refuses(tmp_path):
    """The two halves meet here: the generator writes a lang-less `<foreign>` and
    `validate` errors on exactly that. Without the gate the wrap would be a
    suggestion a reviewer could scroll past; with it, every one has to be disposed
    of — assign a language, or unwrap because it was never a foreign form."""
    from harness.validate import validate
    blocks = [("MainZone-P", lines_at(["the form kełiˊlın here"]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    out = tmp_path / "tei" / "chukchi-1-021.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    errs = validate(out, {"page_ref": "1-021", "root": str(tmp_path),
                          "figures_on_page": [], "ocr_lines": [],
                          "toc_window": []}).errors
    assert any("carries no xml:lang" in e for e in errs)


def test_the_opens_witness_is_never_generated(tmp_path):
    """It records what a reader saw on the raster. Deriving it from the zone label
    would leave `tei seam` comparing a value with itself — the one-witness collapse,
    in the place this project has already met it twice. The zone label goes in as
    `zone-opens:`, which is the *other* witness, and the missing `opens:` is a
    validate error the collator clears by looking at the page."""
    blocks = [("MainZone-Continued", lines_at(["...continuing from the last page."]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "<!-- opens:" not in doc
    assert "zone-opens: continued" in doc


def test_a_page_opening_with_a_fresh_paragraph_says_so(tmp_path):
    blocks = [("MainZone-P", lines_at(["A new paragraph opens the page."]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "zone-opens: fresh" in doc


def test_a_line_in_no_zone_is_kept_and_counted(tmp_path):
    """A dropped line is invisible and stray junk is visible, and that asymmetry
    decides it — the same way `ocr predict` decides it one stage earlier."""
    blocks = [("MainZone-P", lines_at(["Body text."]))]
    stores(tmp_path, "1-021", blocks, bands=[band("MainZone-P", 2000, 2100, 1)])
    doc, rep = gen.build("1-021", tmp_path)
    assert rep["outside_zones"] == 1
    assert "inside no zone" in doc and "Body text." in doc


def test_an_unknown_label_is_named_rather_than_silently_prose(tmp_path):
    """The vocabulary lives in `data/zones_config.json` and can grow without this
    module hearing about it. A label with no rule here is a fact about the
    generator, so it says which label it did not know instead of quietly choosing
    a side."""
    blocks = [("MainZone-Verse", lines_at(["A line of verse."]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["unknown_labels"] == "MainZone-Verse"
    assert "unknown zone label 'MainZone-Verse'" in doc


# -------------------------------------------------------------- honest refusals

def test_a_page_without_ground_truth_is_refused_with_the_verb_that_fixes_it(tmp_path):
    write_scan(tmp_path, "1-021")
    save_zones("1-021", [band("MainZone-P", 200, 300, 1)], tmp_path)
    with pytest.raises(gen.Unready, match="rebuild-groundtruth"):
        gen.build("1-021", tmp_path)


def test_a_page_without_keyed_zones_is_refused_too(tmp_path):
    """Ground truth alone is not enough: the paragraph boundaries *are* the zone
    labels, and `mz/zones/` is a prediction rather than a human's assertion."""
    alto(tmp_path, "1-021", [("MainZone-P", lines_at(["Body."]))])
    with pytest.raises(gen.Unready, match="zones edit"):
        gen.build("1-021", tmp_path)


def test_a_missing_raster_is_not_an_error_here(tmp_path):
    """`scans/` is derived and not in git, so a fresh clone reaches this. It used
    to be a degraded build that said so in the file; now it is simply a build,
    there being nothing on this path that wants a raster."""
    stores(tmp_path, "1-021", [("MainZone-P", lines_at(["Body."]))])
    # After the stores are written, not before: `save_zones` measures the raster.
    (tmp_path / "scans" / "chukchi-1-021.png").unlink()
    doc, rep = gen.build("1-021", tmp_path)
    assert rep["paragraphs"] == 1
    assert "<p>Body.</p>" in doc


def test_a_baseline_is_not_replaced_without_force(tmp_path):
    """A baseline a collator has already copied is one half of `tei diff`; moving
    it under a review in progress makes that comparison a lie."""
    blocks = [("MainZone-P", lines_at(["Body."]))]
    stores(tmp_path, "1-021", blocks)
    assert gen.generate("1-021", tmp_path)["written"] is True
    again = gen.generate("1-021", tmp_path)
    assert again["written"] is False and "--force" in again["why"]
    assert gen.generate("1-021", tmp_path, force=True)["written"] is True


def test_a_skipped_row_carries_the_whole_key_set(tmp_path):
    """`emit`'s tabular collapse degrades the *entire* table the moment one record's
    keys differ from its neighbours', so a short row for a skip would cost every
    other page in a sweep its shape."""
    blocks = [("MainZone-P", lines_at(["Body."]))]
    stores(tmp_path, "1-021", blocks)
    full = gen.generate("1-021", tmp_path)
    assert set(gen.skipped("1-022").keys()) == set(full.keys())


# ------------------------------------------------------------------- tei diff

def _reviewed(tmp_path: Path, ref: str, doc: str, edit=None) -> None:
    out = tmp_path / "tei" / f"chukchi-{ref}.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(edit(doc) if edit else doc, encoding="utf-8")


def test_diff_reports_an_untouched_copy_as_unfinished(tmp_path):
    """The row that answers "is this page read yet". A collator that copied the
    baseline and stopped leaves every generator comment standing, and the count of
    those is what says so — not the absence of edits, which a page legitimately
    finished with no changes would also show."""
    blocks = [("MainZone-Other", lines_at(["THE CHUKCHEE."]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    gen.generate("1-021", tmp_path)
    _reviewed(tmp_path, "1-021", doc)
    row = gen.diff("1-021", tmp_path)
    assert row["gen_comments"] >= 1 and "unanswered" in row["why"]


def test_diff_says_when_the_baseline_moved_under_the_review(tmp_path):
    """A regenerated baseline makes every other column noise: the counts would be
    comparing a review against a file it was never taken from. Reporting the
    difference without saying this would read as work somebody did."""
    blocks = [("MainZone-P", lines_at(["Body."]))]
    stores(tmp_path, "1-021", blocks)
    gen.generate("1-021", tmp_path)
    _reviewed(tmp_path, "1-021", gen.gen_path("1-021", tmp_path).read_text())
    assert gen.diff("1-021", tmp_path)["drifted"] is False
    # Ground truth corrected under the review: same page, different bytes in.
    alto(tmp_path, "1-021", [("MainZone-P", lines_at(["Body corrected."]))])
    row = gen.diff("1-021", tmp_path)
    assert row["drifted"] is True and "regenerated since review" in row["why"]


def test_diff_shows_the_shape_of_what_review_did(tmp_path):
    """Counts as `before->after` only where they moved, so a scan of the table shows
    what a reader added. Unwrapping a handle and typing a name are the two
    commonest, and both are visible here."""
    blocks = [("MainZone-P", lines_at(["the form kełiˊlın here"]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    gen.generate("1-021", tmp_path)
    _reviewed(tmp_path, "1-021", doc,
              lambda d: d.replace('<foreign index="1">kełiˊlın</foreign>',
                                  '<name type="ethnonym">Chukchee</name>'))
    row = gen.diff("1-021", tmp_path)
    assert row["foreign"] == "1->0" and row["name"] == "0->1"
    assert row["lang_less"] == 0


# --- the gate speaks once per open question ----------------------------------

def _validated(tmp_path, ref="1-021", body=None):
    from harness.validate import validate
    doc, _ = page(tmp_path, ref, [
        ("MainZone-P", lines_at(body or ["the form kełiˊlın here.¹"])),
        ("MarginTextZone-Notes", lines_at(["¹ See the authorities."], 245))])
    out = tmp_path / "tei" / f"chukchi-{ref}.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return validate(out, {"page_ref": ref, "root": str(tmp_path),
                          "figures_on_page": [], "ocr_lines": [],
                          "toc_window": []}).errors


def test_a_langless_handle_is_not_also_reported_as_unexpanded(tmp_path):
    """`tei expand` refuses a handle on an element that is not a Tier-1 span, so
    naming it as the missing step would send a reviewer to a verb that cannot help.
    Every generated page arrives with one handle per ratified token, so without the
    scope the ordinary state of an untouched page is two errors per handle naming
    two remedies, one of them inert — and a detector firing on the ordinary case
    buries the one that is not."""
    errs = _validated(tmp_path)
    assert len([e for e in errs if "carries no xml:lang" in e]) == 1
    assert not [e for e in errs if "never expanded" in e]


def test_an_anchored_note_draws_no_complaint(tmp_path):
    """The gate used to fire on every generated page, because every generated page
    left its notes at the foot. Now that the generator anchors what it can, an
    error here means the marker really did read nowhere — which is the only
    condition under which it is worth reading."""
    errs = _validated(tmp_path)
    assert not [e for e in errs if "has not been anchored" in e]
    assert not [e for e in errs if "space before <note" in e]
    assert not [e for e in errs if "without n=" in e]


def test_a_note_at_the_foot_is_not_an_error(tmp_path):
    """**The rule that used to sit here is gone, and it said the opposite.** A
    `<note>` that is a direct child of `<body>` drew an error reading "it has not
    been anchored — move it inline to the character its printed marker follows".
    That was right while the generator spliced notes into the prose. It splices
    none now: every note is at the foot, where the printer set it, and the marker
    stays in the sentence carrying a `<ref type="note">`.

    A note whose marker is printed nowhere on the page is still an ordinary note
    with an ordinary `@n`; what it lacks is a reference, and that is visible in
    the text rather than as a gate."""
    errs = _validated(tmp_path, body=["no marker anywhere in this line."])
    assert not [e for e in errs if "has not been anchored" in e]
    assert not [e for e in errs if "space before <note" in e]


def test_the_missing_opens_witness_is_the_error_that_remains(tmp_path):
    """The generator will not write it — that comment records what a reader saw on
    the raster — so its absence is the correct state of a generated page and the
    gate is what makes the collator go and look."""
    assert [e for e in _validated(tmp_path) if "opens:" in e]


# --- the shapes the generator emits are conformant TEI -----------------------
#
# `tei validate --schema` reads `tei/`, so nothing checked the *generator's* own
# markup against the grammar until a collator had copied a page into the store.
# That is the wrong end: a shape the generator emits on all 832 pages is worth
# refusing here, once, rather than on each page after review.


def _conformance(tmp_path, blocks) -> list[str]:
    from lxml import etree

    from harness.schema import check
    doc, _ = page(tmp_path, "1-021", blocks)
    return check(etree.ElementTree(etree.fromstring(doc.encode())), REPO)


def test_an_anchored_note_is_conformant(tmp_path):
    """`<note>` inline in a `<p>`, which is where anchoring puts it."""
    assert _conformance(tmp_path, [
        ("MainZone-P", lines_at(["Body text.¹"])),
        ("MarginTextZone-Notes", lines_at(["¹ See the authorities."], 245))]) == []


def test_a_note_left_at_the_foot_is_conformant(tmp_path):
    """The refusal path emits `<note>` as a child of `<body>`. `validate` calls
    that an unanchored note and says so; the *grammar* has to permit it, or the
    page could not be written down for a human to fix."""
    assert _conformance(tmp_path, [
        ("MainZone-P", lines_at(["No marker here."])),
        ("MarginTextZone-Notes", lines_at(["¹ An orphan."], 245))]) == []


def test_the_figure_shape_is_conformant_on_a_real_figure_page(tmp_path):
    """`<figure n><figDesc>` against the committed grammar, on a page that has a
    figure — which the fixtures above cannot build, the geometry coming from
    `gt/fig/` rather than from the two stores they write.

    The `index` handles are expected and excluded: a lang-less `<foreign
    index="N">` is deliberately not conformant, being the one thing every
    generated page carries that review must replace
    (`test_the_handle_is_what_the_gate_refuses`). Excluded **by name**, so a
    different non-conformance still fails this.
    """
    from lxml import etree

    from harness.schema import check
    if not (REPO / "gt" / "fig" / "chukchi-1-151.xml").exists():
        pytest.skip("1-151 has no figure store in this checkout")
    doc, rep = gen.build("1-151", REPO)
    assert rep["figures"] == 1
    errs = [e for e in check(etree.ElementTree(etree.fromstring(doc.encode())), REPO)
            if "attribute index for element foreign" not in e]
    assert errs == []


def test_a_figure_heads_the_paragraph_it_is_adjacent_to(tmp_path):
    """**A figure the prose ran past goes to the top of that paragraph.**

    It used to come out after it. Both ends are a paragraph boundary and neither
    is the true anchor — that is where the prose says "(Fig. 87, a)", which is a
    reading and the collator's — so the question is only which is the better
    draft, and the top wins twice over. A picture the text wraps around begins
    level with the paragraph's first lines, so the top is the nearer edge to
    where the page has it; and a reader meets the figure before the discussion of
    it rather than after.

    Over the 197 generated figures, those immediately followed by a paragraph
    rose from 141 to 167 and those stranded at the foot of a page fell from 27 to
    3.

    Uses `1-151`, the one ordinary text-figure page in the OCR'd pilot set, so
    the geometry is the store's rather than a fixture's.
    """
    if not (REPO / "gt" / "fig" / "chukchi-1-151.xml").exists():
        pytest.skip("1-151 has no figure store in this checkout")
    doc, rep = gen.build("1-151", REPO)
    assert rep["figures"] == 1

    import re
    body = doc[doc.index("<body>"):]
    # The block sequence, which is what placement is a statement about. Compared
    # against the *neighbouring* block and not against the first paragraph on the
    # page: the figure heads the paragraph it is adjacent to, which on `1-151` is
    # well down the page.
    blocks = [m.group(1) for m in re.finditer(r"<(p|figure|quote|table|head)\b", body)]
    i = blocks.index("figure")
    assert blocks[i + 1:i + 2] == ["p"], (
        f"a figure heads a paragraph; got {blocks[i:i + 2]}")
    # And a numbered figure carries no comment at all. The placement used to be
    # captioned "move me to the first textual reference", which spent the one
    # positional fact measured off the page to restate a reference
    # `<ref type="figure">` already carries — and that reference is routinely on
    # another page, where the instruction could not be followed.
    assert "<!--" not in body[body.index("<figure"):body.index("</figure>")]


def test_a_figure_inside_the_last_paragraph_still_heads_it(tmp_path):
    """The case that broke the rule, and the reason it broke on a seventh of the
    corpus while looking right.

    Each paragraph's close flushed the figures above **the top of whatever band
    came next**, which is the next paragraph's start — correct for every
    paragraph that has one. The last paragraph on a page has none: it is closed
    after the loop with that variable still holding its own first band's y0, so a
    figure inside it failed the test, fell through to the final flush and landed
    at the very foot of the page. Measuring against the paragraph's own bottom is
    the same number everywhere else and the right one here.

    `1-157` is the page that reported it: fig. 36 sits at y 1602 inside a band
    running 1393–3249, the last prose on the page.
    """
    if not (REPO / "gt" / "fig" / "chukchi-1-157.xml").exists():
        pytest.skip("1-157 has no figure store in this checkout")
    import re
    doc, rep = gen.build("1-157", REPO)
    assert rep["figures"] == 1
    body = doc[doc.index("<body>"):]
    blocks = [m.group(1) for m in re.finditer(r"<(p|figure|quote|table|head)\b", body)]
    assert blocks[-1] != "figure", (
        "the figure is inside the last paragraph, not below it")
    i = blocks.index("figure")
    assert blocks[i + 1:i + 2] == ["p"], f"got {blocks}"


# --- a Tier-1 form that is also an entity alias -------------------------------
#
# The rule used to drop every alias hit touching a Tier-1 handle, on the ground
# that a rule resolving an identity for a string whose glyphs it may not name is
# the firewall's failure shape. That holds for reaching *inside* a handle. A store
# that carries `Veᵋñ` as an alias for `place:anadyr` has already made the
# judgement; enclosing the handle applies it without touching a glyph.


def test_an_alias_coinciding_with_a_handle_is_wrapped_not_dropped(tmp_path):
    """The `<rs>` encloses the `<foreign>`; neither element loses anything.

    Each `@resp` stays a claim about its own element — the outer names the
    entity, the inner says a ratified token sits here — so the handle still
    carries no `xml:lang` and the collator's question is untouched."""
    entry(tmp_path, "place:anadyr", canonical="Anadyr",
          aliases=[(nfd("Veᵋñ"), True)])
    blocks = [("MainZone-P", lines_at([nfd("they call it Veᵋñ there")]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert nfd('<rs ref="place:anadyr" resp="#mz"><foreign index="1">Veᵋñ'
               "</foreign></rs>") in doc
    assert rep["handles"] == 1
    assert "xml:lang" not in doc


def test_an_alias_that_contains_a_handle_encloses_it(tmp_path):
    """Containment is decidable without an opinion — *both* of the handle's ends
    are inside the alias — which is what a partial overlap is not. It used to be
    refused with the partial case, on the argument that only coincidence needs no
    opinion about where the form ends; but it is the shape every double-duty
    toponym in this book takes, a bay or a cape named in English around a
    village's own form, and refusing it left those pages linking the village."""
    entry(tmp_path, "place:anadyr", canonical="Anadyr",
          aliases=[(nfd("Veᵋñ there"), True)])
    blocks = [("MainZone-P", lines_at([nfd("they call it Veᵋñ there")]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert ('<rs ref="place:anadyr" resp="#mz">'
            f'<foreign index="1">{nfd("Veᵋñ")}</foreign> there</rs>') in doc


def test_the_wrapped_link_still_re_derives_at_the_gate(tmp_path):
    """`#mz` asserts nothing on its own: `validate` recomputes the owner from the
    store on every run. The nesting must not put the link out of that loop — the
    `<rs>`'s own text is the Tier-1 string, which is the form the alias table
    is keyed on."""
    from harness.validate import validate
    entry(tmp_path, "place:anadyr", canonical="Anadyr",
          aliases=[(nfd("Veᵋñ"), True)])
    blocks = [("MainZone-P", lines_at([nfd("they call it Veᵋñ there")]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    out = tmp_path / "tei" / "chukchi-1-021.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    errs = validate(out, {"page_ref": "1-021", "root": str(tmp_path),
                          "figures_on_page": [], "ocr_lines": [],
                          "toc_window": []}).errors
    assert not any("no longer derives" in e or "resolves the form" in e
                   for e in errs)
    assert not any("never carries a glyph" in e for e in errs)


def test_a_partial_overlap_is_refused_and_leaves_the_question(tmp_path):
    """The refusal that stands. Nothing may say where the form ends when the two
    extents cross — and refusing it in silence used to take the shorter alias's
    hit with it, since `match` is non-overlapping and the longer one had already
    claimed the span. The page lost the link *and* the question.

    Reachable because `_AFTER` forbids a following letter or combining mark but
    not a hyphen: the alias covers the first half of a hyphenated handle and
    stops inside it."""
    entry(tmp_path, "water:keinu-weem", canonical="Bear River",
          aliases=[(nfd("Keiˊñu"), True)])
    blocks = [("MainZone-P",
               lines_at([nfd("beside the Keiˊñu-weˊem they camp")]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "straddles a Tier-1 handle" in doc
    assert "<rs" not in doc


def test_an_unratified_owner_is_named_as_unratified_and_not_as_auto_no(tmp_path):
    """`auto_forms` withholds a link for three reasons; the comment used to name
    one of them whatever the reason was. A reader sent to raise an `auto:` that
    already reads `yes` learns nothing and edits nothing."""
    entry(tmp_path, "place:markova", status="proposed", canonical="Markova",
          aliases=[("Markova", True)])
    blocks = [("MainZone-P", lines_at(["the fair at Markova is large"]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "still `proposed`" in doc
    assert "harness entity ratify place:markova" in doc
    assert "auto: no" not in doc


# ------------------------------------------------------ cross-reference marks
#
# The pointing at the book's own pictures used to be found in the renderer, so it
# existed only in served HTML: no collator saw a link, `tei validate` had nothing
# to say about one, and the failure it produces is not a dead link but a working
# link to the wrong picture. It is marked in the page now, on entity-link terms.


def test_a_printed_cross_reference_is_marked_in_the_page(tmp_path):
    """The numeral alone, because `Figs. 214, 215` names two pictures and one
    element over the run would have to pick one of them."""
    blocks = [("MainZone-P", lines_at(["as shown in Fig. 87 above"]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert 'Fig. <ref type="figure" n="87" resp="#mz">87</ref> above' in doc
    assert rep["figrefs"] == 1


def test_a_plate_scoped_number_carries_the_plate_that_scopes_it(tmp_path):
    """**The one attribute that cannot be recovered from the numeral.** The book
    restarts figure numbering at 1 on every plate, so `Fig. 3` scoped wrongly
    opens a real leaf whose caption reads correctly under the wrong picture."""
    blocks = [("MainZone-P", lines_at(["(see Plate XXVII, Fig. 3)"]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert '<ref type="plate" n="XXVII" resp="#mz">XXVII</ref>' in doc
    assert '<ref type="figure" n="3" cRef="Plate XXVII" resp="#mz">3</ref>' in doc
    assert rep["figrefs"] == 2


def test_another_authors_plate_is_not_marked(tmp_path):
    """`Sauer, Plate XIV` is Sauer's and this book has a Plate XIV too. Marking it
    would put a question to the collator that `Authorities Quoted` has already
    answered, and the edition is bound to decline the link anyway."""
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "authorities.json").write_text(json.dumps({
        "source": {"refs": ["1-023"]},
        "authorities": [{"key": "sauer1802", "ref": "1-023", "folio": "3",
                         "cited_as": [{"name": "Sauer"}],
                         "printed": [{"ref": "1-023", "text": "SAUER."}]}]}),
        encoding="utf-8")
    (tmp_path / "data" / "runs.json").write_text(json.dumps({"runs": [
        {"id": "authorities", "kind": "authorities", "title": "Authorities Quoted",
         "refs": ["1-023"], "source": "data/authorities.json"}]}), encoding="utf-8")
    blocks = [("MainZone-P", lines_at(["compare Sauer, Plate XIV, p. 321",
                                       "and Plate XIV of this book"], 200))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["figrefs"] == 1                      # the second one, not Sauer's
    assert 'Sauer, Plate XIV' in doc


def test_prose_naming_no_picture_is_marked_nowhere(tmp_path):
    """The ordinary page. `figrefs` is 0 and the count is in the report on every
    page, so a run of them reads as a census rather than as a key that appears
    when something happened."""
    blocks = [("MainZone-P", lines_at(["The paddle is short and broad."]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert "<ref" not in doc
    assert rep["figrefs"] == 0


# ------------------------------------------------------------ cited works
#
# `Nelson` is a man and a book, and the store says so — both entries claim the
# form, so the alias table alone can only ask. The printed citation form answers
# it, and `harness/citations.py` is the rule.


def _authorities(tmp_path: Path) -> None:
    """The printed resolution table, as `Authorities Quoted` holds it."""
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "authorities.json").write_text(json.dumps({
        "source": {"refs": ["1-023"]},
        "authorities": [{"key": "nelson1899", "ref": "1-023", "folio": "3",
                         "author": "E. W. Nelson", "year": 1899,
                         "title": "The Eskimo about Bering Strait",
                         "cited_as": [{"name": "Nelson"}],
                         "printed": [{"ref": "1-023", "text": "NELSON."}]}]}),
        encoding="utf-8")
    (tmp_path / "data" / "runs.json").write_text(json.dumps({"runs": [
        {"id": "authorities", "kind": "authorities",
         "title": "Authorities Quoted", "refs": ["1-023"],
         "source": "data/authorities.json"}]}), encoding="utf-8")


def _both_nelsons(tmp_path: Path) -> None:
    entry(tmp_path, "person:nelson", canonical="E. W. Nelson",
          aliases=[("Nelson", False)])
    entry(tmp_path, "source:nelson-1899", canonical="The Eskimo about Bering Strait",
          aliases=[("Nelson", False)], extra="- authority: nelson1899\n")


def test_a_cited_name_is_linked_to_the_work(tmp_path):
    """A locator attached to the name is what a citation is, and it resolves an
    ambiguity `auto_forms` is right to refuse."""
    _authorities(tmp_path)
    _both_nelsons(tmp_path)
    blocks = [("MainZone-P", lines_at(["Compare Nelson, pp. 27, 28."]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert '<rs ref="source:nelson-1899" resp="#mz">Nelson</rs>, pp. 27, 28.' in doc
    assert rep["links"] == 1
    assert "entity candidate" not in doc          # the question is answered


def test_the_same_name_without_a_locator_stays_a_question(tmp_path):
    """`Nelson. Fig. 22, b, shows a sled` is the man, and the store's two claims
    on the form stand unresolved — which is the honest state, and the comment
    says both."""
    _authorities(tmp_path)
    _both_nelsons(tmp_path)
    blocks = [("MainZone-P", lines_at(["as Nelson found. The sled is short."]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "<rs" not in doc
    assert "person:nelson or source:nelson-1899" in doc


def test_a_citation_the_store_cannot_resolve_stays_a_question(tmp_path):
    """The entry has to *be* the work. Without `authority:` nothing joins the
    printed siglum to an entry, and the rule declines rather than picking the
    only `source:` in sight."""
    _authorities(tmp_path)
    entry(tmp_path, "person:nelson", aliases=[("Nelson", False)])
    entry(tmp_path, "source:nelson-1899", aliases=[("Nelson", False)])
    blocks = [("MainZone-P", lines_at(["Compare Nelson, pp. 27, 28."]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "<rs" not in doc
    assert "entity candidate" in doc


def test_the_rule_chooses_among_the_stores_claims_and_never_adds_one(tmp_path):
    """**The licence, stated as a test.** A work whose entry does not claim the
    printed form is not linked by it: the alias table stays the gate on what a
    string may name, and the citation form only says which of its claimants the
    sentence means."""
    _authorities(tmp_path)
    entry(tmp_path, "source:nelson-1899", canonical="The Eskimo",
          aliases=[("Bering Strait", False)], extra="- authority: nelson1899\n")
    blocks = [("MainZone-P", lines_at(["Compare Nelson, pp. 27, 28."]))]
    doc, _ = page(tmp_path, "1-021", blocks)
    assert "<rs" not in doc


def test_a_broken_word_does_not_continue_into_the_footnotes():
    """**One join corrupting two texts, and it looked like a recognizer error.**

    `1-075`, `1-091`, `1-203` and `1-243` each end their last body line on a
    broken word, and the next non-empty line is the first footnote. The join took
    its first token — the printed marker — so the body read `…the Kolyma west-¹`
    and the note it was stolen from opened with no marker at its head. The
    generator then reported "no marker at the head of this note" on exactly those
    four pages, blaming the recognizer for a defect one function downstream.

    **The zone label is not the geometric guard this function threw out.** That
    one asked whether a box sat too far away — arithmetic over coordinates, which
    moved 22 joins and corrupted 20 of them. This reads what a human keyed. And
    it is measured the same way: 523 joins over `gt/ocr/`, of which **4** cross a
    zone, all four `MainZone-P` into `MarginTextZone-Notes`, and all four are
    this. The rule refuses those and nothing else in the corpus.
    """
    recs = [
        {"text": "sailed from the mouth of the Kolyma west-", "zone": "MainZone-P"},
        {"text": "¹ Bogoras, Chukchee Materials, p. 345.",
         "zone": "MarginTextZone-Notes"},
    ]
    got = join_broken_words(recs)
    assert got[0].endswith("west-"), "the stem keeps its hyphen and takes nothing"
    assert got[1].startswith("¹"), "the note keeps the marker at its head"


def test_a_broken_word_still_joins_inside_one_zone():
    """The guard is a zone test and not a new reluctance to join. Absence of a
    label on either side is not a barrier either — a caller handing in records
    with no zones must still get its joins.

    The hyphen survives the join, which is this function's one judgement and not
    an oversight here: dropping it manufactured nine words the book does not
    contain (`reindeerowner`, `treetrunk`), because a real compound hyphen at a
    line end is indistinguishable from a break."""
    same = [{"text": "at a consider-", "zone": "MainZone-P"},
            {"text": "able distance", "zone": "MainZone-P"}]
    assert join_broken_words(same) == ["at a consider-able", "distance"]
    bare = [{"text": "at a consider-"}, {"text": "able distance"}]
    assert join_broken_words(bare) == ["at a consider-able", "distance"]


def test_a_figure_locant_is_not_a_footnote_marker():
    """**`1-285` set one marker per note and the pass called all three
    ambiguous.** It prints `(Fig. 155, d², e¹)`, `(Fig. 155, d³)` and `(Fig. 155,
    a², c²)`, so a raw count found four places reading `²` where the page has one
    real reference, and the notes went unanchored — appended after the two that
    did anchor, which is why the page's notes came out `4, 5, 1, 2, 3`.

    `keying_spec.md` §2.10 already excludes a locant and bounds it textually: "a
    lone letter carries the superscript and a close-paren follows". In the run
    above that is true of `e¹` and false of `d²`, so it caught the last member
    and missed every earlier one. The bound is structural now — whatever
    `figrefs.LOCANTS` consumes after a figure reference, which is the same
    pattern that decided where the reference ended, so one definition governs
    both and a comma-separated list is no harder than a single letter.

    A superscript *outside* a run is still a marker, which is what §2.10 settles
    corpus-wide; this only says where the runs are.
    """
    ref = '<ref type="figure" n="155" resp="#mz">155</ref>'
    body = [f'      <p>They are long, thin tubes¹ (Fig. {ref}, d², '
            f'e¹), inside of which the needles sit; figured by Nelson.²</p>']
    assert gen._marker_sites(body, "¹") == [(0, body[0].index("¹") + 1)], \
        "tubes¹ is the only ¹ that is not a locant"
    assert len(gen._marker_sites(body, "²")) == 1, \
        "d² is a locant however the run is punctuated; Nelson.² is the marker"


def test_a_locant_run_is_bounded_by_the_reference_that_produced_it():
    """The span is what `figrefs.LOCANTS` matches after the emitted `<ref>`, and
    it stops where the printer stops: `Fig. 53, a, a narwhal` consumes `a` and
    leaves the prose alone, the word after it failing the `\\b`."""
    ref = '<ref type="figure" n="53" resp="#mz">53</ref>'
    spans = gen._locant_spans(f'(Fig. {ref}, a, a narwhal) and a note¹')
    assert len(spans) == 1
    a, b = spans[0]
    assert f'(Fig. {ref}, a, a narwhal) and a note¹'[a:b] == ", a, a"
