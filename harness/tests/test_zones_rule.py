"""`harness zones propose`: zones by rule off the text layer's rows.

The derivation is tested on synthetic rows in the 1900 *Materials*' geometry
(600 dpi, a 2986 px column at x0 = 600) with its own thresholds, so a number
here means what it means on the book. The store half runs on a fixture text.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from conftest import chukchi_zone_config, write_scan, write_zone_config
from lxml import etree

from harness import provenance, zones, zones_rule
from harness.ns import ALTO_NS
from harness.zones_config import TEXT_RULE_KEYS, ConfigError, load_config

X0, M = 600, 2986
RULE = {"head_max_y": 700, "foot_max_w": 200, "number_pad": 40, "gap_min_px": 80,
        "indent_px": 210, "indent_tol": 50, "heading_max_w": 2000, "centre_tol": 60,
        "gutter_min_px": 60, "gutter_min_rows": 3,
        "gutter_max_offset": 300, "rule_bridge_px": 10, "rule_fill_min": 0.9, "footrule_min_px": 450,
        "footrule_max_start": 400, "footrule_max_end": 1000,
        "stream_rule_min_px": 2700, "speck_max_chars": 2, "speck_max_px": 60,
        "missing_min_h": 60, "missing_edge_px": 5}
CFG = {"text_rule": RULE, "width_tolerance_px": 80}
BLANK = np.zeros((7000, 4800), dtype=bool)


class Page:
    """Rows top to bottom, each placed at a pitch below the last unless told."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.y = 800

    def add(self, text: str, x: int = X0, w: int = M, h: int = 100,
            y: int | None = None, pitch: int = 125) -> int:
        if y is None:
            y = self.y
        self.rows.append({"index": len(self.rows), "text": text, "hpos": x,
                          "vpos": y, "width": w, "height": h})
        self.y = y + pitch
        return len(self.rows) - 1

    def gap(self, px: int) -> None:
        self.y += px

    def para(self, n: int, indent: bool = True) -> None:
        self.add("Первая строка абзаца", x=X0 + 210 if indent else X0,
                 w=M - 210 if indent else M)
        for _ in range(n - 1):
            self.add("продолженіе абзаца")


def labels(page: Page, ink=BLANK) -> list[str]:
    return [b["label"] for b in zones_rule.derive(page.rows, X0, M, ink, CFG).bands]


def centred(page: Page, text: str, w: int = 600) -> int:
    return page.add(text, x=X0 + (M - w) // 2, w=w)


# ---------------------------------------------------------------- the body


def test_an_indent_starts_a_paragraph_and_a_flush_line_continues_one():
    p = Page()
    p.add("Г. БОГОРАЗЪ", y=560)
    p.para(3, indent=False)
    p.para(4)
    assert labels(p) == ["RunningTitleZone", "MainZone-Continued", "MainZone-P"]


def test_a_structural_gap_ends_a_band_where_no_indent_marks_it():
    # Section I: the Chukchi, then its Russian continuing from the page before.
    p = Page()
    p.para(3, indent=False)
    p.gap(150)
    p.para(3, indent=False)
    assert labels(p) == ["MainZone-Continued", "MainZone-Continued"]


def test_ordinary_leading_does_not_end_a_band():
    p = Page()
    p.para(2, indent=False)
    p.gap(40)                       # 65 px of white: front-matter leading
    p.add("продолженіе")
    assert labels(p) == ["MainZone-Continued"]


def test_a_short_centred_line_is_a_heading():
    p = Page()
    p.para(2, indent=False)
    p.gap(200)
    centred(p, "26.", w=145)
    p.gap(100)
    p.para(3)
    assert labels(p) == ["MainZone-Continued", "MainZone-Other", "MainZone-P"]


def test_the_chapter_opener_has_no_running_head():
    p = Page()
    centred(p, "ВВЕДЕНІЕ", w=660)
    p.rows[0]["vpos"] = 2156
    p.y = 2574
    p.para(3)
    assert labels(p) == ["MainZone-Other", "MainZone-P"]


# ---------------------------------------------------------------- the margins


def test_line_numbers_are_a_field_of_the_line():
    p = Page()
    p.para(2, indent=False)
    p.add("5 чашчушачһын ендемычһын", x=X0 - 80, w=M + 80)      # verso
    p.add("кэлє нумэкэт- 10", w=M + 120)                          # recto
    # Its own row, between two lines (`1-177` l33), taking no line's place.
    p.add("15", x=X0 + M + 60, w=90, h=68, y=p.y - 50, pitch=50)
    p.add("продолженіе")
    got = zones_rule.derive(p.rows, X0, M, BLANK, CFG)
    assert [b["label"] for b in got.bands] == ["MainZone-Continued"]
    assert got.numbers == 3 and got.unzoned == []


def test_a_numbered_line_never_reads_as_an_indent():
    p = Page()
    p.para(2, indent=False)
    p.add("5 ӄары-м нэўс̧", x=X0 - 100, w=M + 100)
    assert labels(p) == ["MainZone-Continued"]


def test_the_heads_split_out_letter_joins_the_head():
    p = Page()
    p.add("144 Г. БОГОРАЗЪ , 1,44", y=575, w=2963, h=112)
    p.add("В.", x=X0 + 1140, y=626, w=55, h=61)
    p.y = 808
    p.para(2, indent=False)
    got = zones_rule.derive(p.rows, X0, M, BLANK, CFG)
    head = got.bands[0]
    assert head["label"] == "RunningTitleZone" and head["rows"] == [0, 1]


def test_a_speck_is_left_unzoned_and_cuts_no_gap():
    p = Page()
    p.para(2, indent=False)
    p.add("/", x=3000, w=31, h=51, y=p.y - 60, pitch=60)
    p.para(2, indent=False)
    got = zones_rule.derive(p.rows, X0, M, BLANK, CFG)
    assert [b["label"] for b in got.bands] == ["MainZone-Continued"]
    assert [u["reason"] for u in got.unzoned] == ["speck"]


def test_a_small_mark_with_a_letter_is_a_speck_too():
    # `1-288`: a 35 px `C` beside a title, which made a band of negative height.
    p = Page()
    p.para(2, indent=False)
    p.gap(150)
    centred(p, "Сказка о сироткѣ .", w=1660)
    p.add("C", x=X0 + 2400, w=35, h=35, y=p.y - 115)
    p.gap(100)
    p.para(2)
    got = zones_rule.derive(p.rows, X0, M, BLANK, CFG)
    assert [b["label"] for b in got.bands] == \
        ["MainZone-Continued", "MainZone-Other", "MainZone-P"]
    assert all(b["y1"] > b["y0"] for b in got.bands)
    assert [u["text"] for u in got.unzoned] == ["C"]


# ---------------------------------------------------------------- the foot


def test_a_signature_set_small_grows_to_the_minimum_height():
    # `1-029`: `II`, a 54 px box against the store's 60 px minimum.
    p = Page()
    p.para(3, indent=False)
    p.gap(200)
    p.add("II", x=X0 + 2400, w=57, h=54)
    got = zones_rule.derive(p.rows, X0, M, BLANK, dict(CFG, min_zone_h_px=60)).bands
    assert got[-1]["label"] == "QuireMarksZone"
    assert got[-1]["y1"] - got[-1]["y0"] == 60
    assert got[-2]["y1"] <= got[-1]["y0"]


def test_a_signature_and_a_chapter_folio_are_quire_marks():
    p = Page()
    p.para(3, indent=False)
    p.add("16", x=X0 + 2500, w=91, h=62)
    assert labels(p)[-1] == "QuireMarksZone"
    q = Page()
    q.para(3, indent=False)
    q.add("I", x=X0 + 2540, w=46, h=69)
    assert labels(q)[-1] == "QuireMarksZone"


def test_a_heading_number_with_text_below_is_no_quire_mark():
    p = Page()
    p.para(2, indent=False)
    p.gap(200)
    centred(p, "44.", w=141)
    p.gap(100)
    p.para(2)
    assert "QuireMarksZone" not in labels(p)


def test_footnotes_with_no_rule_over_them_are_the_reviewers():
    # Set smaller and opening `1)`, but neither is measured as a footnote: only
    # the printed rule is (2026-11-15, rules are measurement).
    p = Page()
    p.para(6, indent=False)
    p.gap(100)
    p.add("1) В. Г. Богоразъ, Краткій отчетъ", x=X0 + 210, w=M - 210, pitch=100)
    p.add("(съ картою маршрутовъ)", pitch=100)
    assert labels(p) == ["MainZone-Continued", "MainZone-P"]


def _rule_ink(y: int, x: int, w: int) -> np.ndarray:
    ink = BLANK.copy()
    ink[y:y + 6, x:x + w] = True
    return ink


def test_footnotes_at_the_bodys_pitch_are_known_by_their_rule():
    # `1-278`: two notes, `1)` and `2)`, at the body's pitch, under a short rule.
    p = Page()
    p.para(6, indent=False)
    p.gap(100)
    p.add("1) Јэті? — Тыјэтјаӄ", x=X0 + 210, w=M - 400)
    p.add("2) Тумђын ым кэлэ", x=X0 + 210, w=M - 900)
    rule_y = p.rows[-2]["vpos"] - 80
    assert "MarginTextZone-Notes" not in labels(p)
    assert labels(p, _rule_ink(rule_y, X0 + 10, 840)) == \
        ["MainZone-Continued", "MarginTextZone-Notes"]
    # A broken rule still counts; a centred one under a heading does not.
    broken = _rule_ink(rule_y, X0 + 10, 840)
    broken[:, X0 + 400:X0 + 406] = False
    assert labels(p, broken)[-1] == "MarginTextZone-Notes"
    assert labels(p, _rule_ink(rule_y, X0 + 1280, 420))[-1] == "MainZone-P"


def test_the_rule_alone_starts_the_footnotes():
    # `1-049`: a document a footnote introduces, under the rule, opening with no
    # `N)`. What a line says is not read.
    p = Page()
    p.para(6, indent=False)
    p.gap(100)
    p.add("Копія. № 8712.", x=X0 + 210, w=M - 900)
    p.add("Объявленіе")
    rule_y = p.rows[-2]["vpos"] - 80
    assert labels(p, _rule_ink(rule_y, X0 + 10, 840)) == \
        ["MainZone-Continued", "MarginTextZone-Notes"]


def test_a_rule_is_found_where_the_boxes_close_the_gap_over_it():
    # `1-387`: the layer's boxes drift, and leave 10 px between the last body
    # line and the first note, with the footnote rule printed in between.
    p = Page()
    p.para(6, indent=False)
    p.add("1) Мећы-танӈытан т. е. русскій", x=X0 + 210, w=M - 1700, y=p.y - 115)
    p.add("2) Ораwеђа пераркын", x=X0 + 210, w=M - 210)
    rule_y = p.rows[-2]["vpos"] - 30
    assert labels(p, _rule_ink(rule_y, X0 + 10, 840)) == \
        ["MainZone-Continued", "MarginTextZone-Notes"]


def test_letters_bridged_into_a_long_run_are_no_rule():
    # `1-179`: a long word in close bold type, its letters under rule_bridge_px
    # apart, bridges into a run a footnote rule's length. A rule is solid.
    p = Page()
    p.para(6, indent=False)
    p.para(3)
    ink = BLANK.copy()
    y = p.rows[6]["vpos"] - 30
    for x in range(X0 + 10, X0 + 850, 14):          # 6 px of ink, 8 px of white
        ink[y:y + 6, x:x + 6] = True
    assert labels(p, ink) == ["MainZone-Continued", "MainZone-P"]


def test_a_margin_mark_joined_to_a_row_is_taken_off_it():
    # `1-100` l13: a `}` in the margin fused into a note's second line.
    p = Page()
    p.add("25 (стр. 103). вата", x=X0 + 210, w=M - 210)
    p.add("} д'ѣленіе прилагается", x=X0 - 1230, w=M + 1230)
    p.add("полномъ иждивеніи")
    got = zones_rule.derive(p.rows, X0, M, BLANK, CFG)
    assert [b["label"] for b in got.bands] == ["MainZone-P"]
    assert got.unzoned == [] and got.numbers == 0
    # A misread recto number at the end (`зо` for 30) is a mark too.
    q = Page()
    q.para(2, indent=False)
    q.add("По прежнему зо", w=M + 100)
    assert [b["label"] for b in zones_rule.derive(q.rows, X0, M, BLANK, CFG).bands] \
        == ["MainZone-Continued"]


def test_a_continued_band_under_a_stream_rule_raises_no_flag():
    # Section I: the Chukchi, a full-width rule, its Russian continuing.
    p = Page()
    p.para(3, indent=False)
    p.gap(150)
    p.para(3, indent=False)
    rule_y = p.rows[3]["vpos"] - 90
    assert flags(p) == ["continued"]
    assert flags(p, _rule_ink(rule_y, X0 + 5, 2970)) == []


def test_numbered_proverbs_at_the_bodys_size_are_not_footnotes():
    p = Page()
    p.para(6, indent=False)
    p.gap(100)
    p.add("1) Лживого человѣка слушать", x=X0 + 210, w=M - 210)
    p.add("(удовлетворенъ) слушая . 2) Калъ")
    assert "MarginTextZone-Notes" not in labels(p)


# ---------------------------------------------------------------- the text is not read


def test_in_the_notes_every_indent_is_a_band_and_the_opener_is_not_read():
    # A note's printed opener is the reviewer's to read against the ruling, so
    # an indented line that opens none is a band like any other, and the same
    # geometry under other words gives the same bands.
    def page(words: list[str]) -> Page:
        p = Page()
        p.para(2, indent=False)               # a note carried over
        p.add(words[0], x=X0 + 215, w=M - 215)
        p.add("продолженіе примѣчанія")
        p.add("Сравнить №5 , прим . 26 .", w=883)
        p.add(words[1], x=X0 + 215, w=M - 215)
        p.add(words[2], x=X0 + 215, w=M - 215)
        return p

    notes = page(["21 (стр . 81). Єлыӄыкына", "и еще одна строка",
                  "22 (стр. 84). вачһааркын"])
    plain = page(["Первая строка", "вторая строка", "третья строка"])
    assert labels(notes) == labels(plain) == \
        ["MainZone-Continued", "MainZone-P", "MainZone-P", "MainZone-P"]


# ---------------------------------------------------------------- refusals


def test_a_fused_row_is_unzoned_and_never_bridged():
    p = Page()
    p.para(2, indent=False)
    # No margin mark to take off: two printed lines the layer read as one row.
    p.add("сросшаяся строка двухъ строкъ", x=-6, w=4220)
    p.add("полномъ иждивеніи")
    got = zones_rule.derive(p.rows, X0, M, BLANK, CFG)
    assert [b["label"] for b in got.bands] == ["MainZone-Continued", "MainZone-Continued"]
    assert got.bands[0]["y1"] <= p.rows[2]["vpos"] < got.bands[1]["y0"]
    assert "4220 px" in got.unzoned[0]["reason"]


def test_bands_whose_lines_overlap_meet_at_the_midpoint():
    p = Page()
    p.para(2, indent=False)
    p.add("тѣсная строка", x=X0 + 210, w=M - 210, h=150, y=p.y - 40)
    p.add("продолженіе")
    got = zones_rule.derive(p.rows, X0, M, BLANK, CFG).bands
    assert len(got) == 2
    assert all(a["y1"] <= b["y0"] for a, b in zip(got, got[1:], strict=False))


# ---------------------------------------------------------------- parallel columns


def _two_columns(page: Page, n: int, split: int) -> np.ndarray:
    """`n` lines whose ink stops either side of a 90 px gutter at `split`."""
    ink = BLANK.copy()
    for _ in range(n):
        i = page.add("Эпээ - цэмкын нумэкэткін ъмыló Энээ-рэмкын", w=M)
        r = page.rows[i]
        ink[r["vpos"] + 20:r["vpos"] + 80, X0 + 10:split - 45] = True
        ink[r["vpos"] + 20:r["vpos"] + 80, split + 45:X0 + M - 10] = True
    return ink


def test_lines_sharing_a_gutter_are_one_other_band():
    p = Page()
    p.para(2, indent=False)
    p.gap(150)
    ink = _two_columns(p, 5, X0 + M // 2)
    got = zones_rule.derive(p.rows, X0, M, ink, CFG)
    assert [b["label"] for b in got.bands] == ["MainZone-Continued", "MainZone-Other"]
    assert got.gutters == ["90@+0x5"]


def test_a_gutter_far_off_centre_is_a_river():
    p = Page()
    p.para(2, indent=False)
    p.gap(150)
    ink = _two_columns(p, 5, X0 + M // 2 + 450)
    assert "MainZone-Other" not in labels(p, ink)


def test_two_lines_are_not_enough_for_a_column_pair():
    p = Page()
    p.para(2, indent=False)
    p.gap(150)
    ink = _two_columns(p, 2, X0 + M // 2)
    assert "MainZone-Other" not in labels(p, ink)


# ---------------------------------------------------------------- flags


def flags(page: Page, ink=BLANK) -> list[str]:
    return zones_rule.derive(page.rows, X0, M, ink, CFG).flags


def test_a_plain_page_carries_no_flag():
    p = Page()
    p.add("Г. БОГОРАЗЪ", y=560)
    p.para(3, indent=False)
    p.para(4)
    assert flags(p) == []


def test_a_speck_raises_no_flag_and_a_fused_row_does():
    p = Page()
    p.para(2, indent=False)
    p.add("/", x=3000, w=31, h=51, y=p.y - 60, pitch=60)
    p.para(2, indent=False)
    assert flags(p) == []
    q = Page()
    q.para(2, indent=False)
    q.add("} д'ѣленіе прилагается", x=-6, w=4220)
    q.add("полномъ иждивеніи")
    assert flags(q) == ["unzoned", "continued"]


def test_a_continued_band_below_the_first_is_flagged():
    p = Page()
    p.para(3, indent=False)
    p.gap(150)
    p.para(3, indent=False)
    assert flags(p) == ["continued"]


def test_a_parallel_block_is_flagged_and_the_notes_are_not_read():
    p = Page()
    p.para(2, indent=False)
    p.gap(150)
    assert "parallel" in flags(p, _two_columns(p, 5, X0 + M // 2))
    q = Page()
    q.add("21 (стр . 81). Єлыӄыкына", x=X0 + 215, w=M - 215)
    q.add("продолженіе")
    assert flags(q) == []


# ---------------------------------------------------------------- the store

FX_M = 1778          # the fixture text's part-1 measure, at 300 dpi
FX_X0 = 479
#: The Materials' thresholds at the fixture's 300 dpi: every pixel figure halved.
FX_RULE = {k: (v if k in ("gutter_min_rows", "rule_fill_min") else v // 2)
           for k, v in RULE.items()}


def _alto(rows: list[tuple[int, int, int, int, str]], step: str) -> bytes:
    a = etree.Element(f"{{{ALTO_NS}}}alto", nsmap={None: ALTO_NS})
    d = etree.SubElement(a, f"{{{ALTO_NS}}}Description")
    kind = {"kind": "model", "model": "pdfs/x.pdf", "sha256": "ab" * 32}
    d.append(provenance.alto_processing(provenance.Producer(
        step=step, label="text layer", version="1", **kind)))
    ps = etree.SubElement(etree.SubElement(etree.SubElement(
        a, f"{{{ALTO_NS}}}Layout"), f"{{{ALTO_NS}}}Page",
        {"WIDTH": "2824", "HEIGHT": "3897"}), f"{{{ALTO_NS}}}PrintSpace")
    tb = etree.SubElement(ps, f"{{{ALTO_NS}}}TextBlock", {"ID": "b"})
    for i, (x, y, w, h, text) in enumerate(rows, 1):
        box = {"HPOS": str(x), "VPOS": str(y), "WIDTH": str(w), "HEIGHT": str(h)}
        tl = etree.SubElement(tb, f"{{{ALTO_NS}}}TextLine", {"ID": f"l{i}", **box})
        etree.SubElement(tl, f"{{{ALTO_NS}}}String", {"CONTENT": text, **box})
    return etree.tostring(a, xml_declaration=True, encoding="UTF-8")


def _store(tmp_path, ref="1-002", split="train", step="harness ocr import",
           rule=True):
    cfg = chukchi_zone_config()
    if rule:
        cfg["text_rule"] = FX_RULE
    write_zone_config(tmp_path, cfg)
    write_scan(tmp_path, ref)
    rows = [(FX_X0, 300, FX_M, 50, "2 Г. БОГОРАЗЪ"),
            (FX_X0 + 105, 420, FX_M - 105, 50, "Первая строка")]
    rows += [(FX_X0, 482 + 62 * k, FX_M, 50, "продолженіе") for k in range(5)]
    p = tmp_path / "mz" / "ocr" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_alto(rows, step))
    if split:
        zones.set_splits({ref: split}, tmp_path)
    return tmp_path


def test_preview_writes_nothing_and_commit_writes_only_mz(tmp_path):
    root = _store(tmp_path)
    rows, _ = zones_rule.propose_many(["1-002"], root)
    assert rows[0]["zones"] == 2 and not rows[0]["skipped"]
    assert not zones.alto_for("1-002", root, zones.MZDIR).exists()
    zones_rule.propose_many(["1-002"], root, commit=True)
    dest = zones.alto_for("1-002", root, zones.MZDIR)
    assert dest.exists() and not zones.alto_for("1-002", root).exists()
    got = provenance.read_producer(dest)
    assert got.kind == "rule" and got.step == "harness zones propose"
    assert got.model is None
    assert {f"rule.{k}" for k in TEXT_RULE_KEYS} <= set(got.inputs)
    assert got.inputs["flags"] == rows[0]["flags"]
    assert [z["label"] for z in zones.read_zones("1-002", root, store=zones.MZDIR)] == \
        ["RunningTitleZone", "MainZone-P"]


def test_an_existing_file_is_kept_without_force(tmp_path):
    root = _store(tmp_path)
    zones_rule.propose_many(["1-002"], root, commit=True)
    rows, _ = zones_rule.propose_many(["1-002"], root, commit=True)
    assert rows[0]["skipped"].startswith("mz/zones already holds a file")
    rows, _ = zones_rule.propose_many(["1-002"], root, commit=True, force=True)
    assert not rows[0]["skipped"]


def test_a_ruled_leaf_is_skipped_even_when_named(tmp_path):
    root = _store(tmp_path, split="plate")
    rows, _ = zones_rule.propose_many(["1-002"], root, commit=True)
    assert rows[0]["skipped"] == "ruled not a text page"
    assert not zones.alto_for("1-002", root, zones.MZDIR).exists()


def test_an_unmarked_page_is_skipped(tmp_path):
    root = _store(tmp_path, split="")
    rows, _ = zones_rule.propose_many(["1-002"], root)
    assert rows[0]["skipped"] == "not marked train or eval"


def test_rows_a_recognizer_wrote_are_not_a_text_layer(tmp_path):
    root = _store(tmp_path, step="harness ocr predict")
    rows, _ = zones_rule.propose_many(["1-002"], root)
    assert "not the text layer" in rows[0]["skipped"]


def test_a_text_never_calibrated_for_the_rule_is_refused(tmp_path):
    root = _store(tmp_path, rule=False)
    with pytest.raises(ConfigError, match="text_rule"):
        zones_rule.propose_many(["1-002"], root)


def test_a_mistyped_threshold_is_refused_at_load(tmp_path):
    cfg = chukchi_zone_config()
    cfg["text_rule"] = dict(RULE, gap_min=80)
    write_zone_config(tmp_path, cfg)
    with pytest.raises(ConfigError, match="gap_min"):
        load_config(tmp_path)
    cfg["text_rule"] = {k: v for k, v in RULE.items() if k != "indent_px"}
    (tmp_path / "config" / "zones.json").write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ConfigError, match="indent_px"):
        load_config(tmp_path)


def test_a_printed_line_with_no_row_is_flagged_uncovered(tmp_path):
    # `1-092`: a title the text layer has no row for, so no zone can hold it.
    root = _store(tmp_path)
    rows, _ = zones_rule.propose_many(["1-002"], root)
    assert "uncovered" not in rows[0]["flags"]
    # Glyphs, not a bar: a solid run that long is what a printed rule makes.
    glyphs = tuple((x, 1000, x + 24, 1045) for x in range(FX_X0 + 600, FX_X0 + 1200, 40))
    write_scan(root, "1-002", ink=glyphs)
    rows, _ = zones_rule.propose_many(["1-002"], root)
    assert "uncovered" in rows[0]["flags"].split(",")
    # The leaf's own edge, in the raster's last rows, is not a line.
    write_scan(root, "1-002", ink=((FX_X0, 3897 - 40, FX_X0 + FX_M, 3897),))
    rows, _ = zones_rule.propose_many(["1-002"], root)
    assert "uncovered" not in rows[0]["flags"]


def test_the_check_sets_aside_ink_measured_not_to_be_a_line(tmp_path):
    # The editor's ruling (2026-11-15): on a text zoned by rule, uncovered ink
    # that is not line-shaped is a `mark`, kept in `uncovered` with its reason and
    # raising no warning; it is never folded into `exempted`, a human's ruling.
    root = _store(tmp_path)
    zones_rule.propose_many(["1-002"], root, commit=True)
    zs = zones.read_zones("1-002", root, store=zones.MZDIR)
    zones.save_zones("1-002", zs, root=root)        # keyed, so the check reads gt
    glyphs = tuple((x, 1000, x + 24, 1045) for x in range(FX_X0 + 600, FX_X0 + 1200, 40))
    edge = ((FX_X0, 3897 - 40, FX_X0 + FX_M, 3897),)
    speck = ((FX_X0 + 900, 2000, FX_X0 + 1200, 2020),)   # 20 px: under a line
    write_scan(root, "1-002", ink=glyphs + edge + speck)
    rep = zones.validate_page("1-002", root, ink=True)
    by_y = {b["vpos"] // 100: b for b in rep["uncovered"]}
    assert by_y[10]["mark"] == ""                                 # a line: raised
    assert "edge" in by_y[38]["mark"] and "shorter" in by_y[20]["mark"]
    assert not any(b["exempted"] for b in rep["uncovered"])
    assert [w["rule"] for w in rep["warnings"]] == ["uncovered-ink"]
