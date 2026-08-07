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

from pathlib import Path

import pytest
from conftest import write_scan

from harness import generate as gen
from harness.zones import save_zones

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

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
    """Both stores for one page, plus the blank raster `save_zones` measures.

    The raster is blank, so `paragraph_starts` finds no ink and cuts nothing: the
    bands that come back are the keyed ones exactly. That isolates what the *labels*
    carry — the claim these tests make — from what the indent detector adds on top,
    while still exercising the real code path rather than the degraded one.
    """
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
    re-derive by looking at the raster."""
    blocks = [("MainZone-P", lines_at(["First para line one.",
                                       "First para line two."])),
              ("MainZone-P", lines_at(["Second para opens here."], 290)),
              ("MainZone-Continued", lines_at(["and this continues it."], 335))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["paragraphs"] == 3
    assert "<p>First para line one.\nFirst para line two.</p>" in doc
    assert "<p>Second para opens here.</p>" in doc


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


def test_the_footnote_block_is_found_and_left_unanchored(tmp_path):
    """Half mechanical, half not, and the split is the point. *Which lines are the
    apparatus* is the zone label and is emitted; *which body marker each note
    belongs to* is a reading, so every note stays at the foot under a comment
    saying so. `MarginTextZone-Notes` is one zone for the whole apparatus, so the
    generator cannot even say how many notes there are."""
    blocks = [("MainZone-P", lines_at(["Body text.¹"])),
              ("MarginTextZone-Notes",
               lines_at(["¹ See the authorities quoted."], 245))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["notes"] == 1
    assert '<note place="bottom">¹ See the authorities quoted.</note>' in doc
    assert "which body marker each belongs to is a reading" in doc
    assert 'n="1"' not in doc          # the marker is not assumed to be the number


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


def test_a_ratified_form_arrives_as_an_empty_handle_with_no_language(tmp_path):
    """The glyphs are adjudicated, so they are never retyped — the handle is what
    `tei expand` fills from `gt/ocr/`. The *language* is not adjudicated by
    anything: `tier1_terms` is a floor over inventory marks with no language
    awareness, so it fires on a German surname carrying a combining diaeresis
    exactly as on a Chukchee form. A generator naming a language would be inferring
    one from the shape of a word."""
    blocks = [("MainZone-P", lines_at(["the form kełiˊlın here"]))]
    doc, rep = page(tmp_path, "1-021", blocks)
    assert rep["handles"] == 1
    assert '<foreign index="1"/>' in doc
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


def test_without_a_raster_the_split_degrades_and_the_page_says_so(tmp_path):
    """`scans/` is derived and not in git, so a fresh clone reaches this. The keyed
    boundaries still carry most paragraphs; what is lost is a band a human keyed as
    one zone that sets two paragraphs. A page silently short of paragraphs would be
    indistinguishable from a page that has them all."""
    stores(tmp_path, "1-021", [("MainZone-P", lines_at(["Body."]))])
    # After the stores are written, not before: `save_zones` measures the raster.
    (tmp_path / "scans" / "chukchi-1-021.png").unlink()
    doc, rep = gen.build("1-021", tmp_path)
    assert rep["split_by"] == "zones-only"
    assert "no blotted raster" in doc


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
              lambda d: d.replace('<foreign index="1"/>',
                                  '<name type="ethnonym">Chukchee</name>'))
    row = gen.diff("1-021", tmp_path)
    assert row["foreign"] == "1->0" and row["name"] == "0->1"
    assert row["lang_less"] == 0


# --- the gate speaks once per open question ----------------------------------

def _validated(tmp_path, ref="1-021"):
    from harness.validate import validate
    doc, _ = page(tmp_path, ref, [
        ("MainZone-P", lines_at(["the form kełiˊlın here.¹"])),
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


def test_an_unanchored_note_is_named_as_such(tmp_path):
    """It used to draw two proxy complaints — a stray space before it, and a missing
    `@n` — both describing symptoms of being unanchored while naming something else.
    A reviewer who fixed what those said had not fixed the page."""
    errs = _validated(tmp_path)
    anchor = [e for e in errs if "has not been anchored" in e]
    assert len(anchor) == 1 and "@n from that marker" in anchor[0]
    assert not [e for e in errs if "space before <note" in e]
    assert not [e for e in errs if "without n=" in e]


def test_the_missing_opens_witness_is_the_error_that_remains(tmp_path):
    """The generator will not write it — that comment records what a reader saw on
    the raster — so its absence is the correct state of a generated page and the
    gate is what makes the collator go and look."""
    assert [e for e in _validated(tmp_path) if "opens:" in e]
