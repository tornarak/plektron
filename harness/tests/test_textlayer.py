"""`ocr import`: a PDF's own text layer, carried into `mz/ocr/` in master pixels.

The fixtures build real PDFs — a master image at a known placement, and text set
over it as separate fragments — because what is under test is the arithmetic
between the layer's point space and the master's pixel space, and the grouping
of the layer's fragments into rows. A mocked `get_text` would be the code
agreeing with itself.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from harness import provenance, textlayer

pymupdf = pytest.importorskip("pymupdf")

DPI = 600
K = 72.0 / DPI          # points per master pixel

#: A font that has Cyrillic. The base-14 fonts do not, and a text layer set in
#: one extracts as placeholders, which would test nothing about Russian.
CYRILLIC_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
if not CYRILLIC_FONT.exists():
    pytest.skip("no DejaVu Sans to set Cyrillic in", allow_module_level=True)


def _text(root: Path, frags, master=(1200, 1800), at=(0, 0), rotate=0) -> Path:
    """A one-page part-1 PDF: a master at `at` (pixels), and text fragments, each
    `(text, x_px, baseline_px)` in master pixels, set where a reader would see it."""
    from PIL import Image

    (root / "pdfs").mkdir(parents=True, exist_ok=True)
    p = root / "project.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps({**rec, "dpi": DPI, "parts": [{"n": 1, "pdf": "copy"}]}),
                 encoding="utf-8")
    from harness.layout import _project
    _project.cache_clear()

    w, h = master
    img = root / "_m.png"
    Image.new("1", (w, h), 1).save(img)
    doc = pymupdf.open()
    page = doc.new_page(width=(w + 2 * at[0]) * K, height=(h + 2 * at[1]) * K)
    page.insert_image(pymupdf.Rect(at[0] * K, at[1] * K, (at[0] + w) * K,
                                   (at[1] + h) * K), filename=str(img))
    for text, x, base in frags:
        page.insert_text(((at[0] + x) * K, (at[1] + base) * K), text, fontsize=10,
                         fontname="cyr", fontfile=str(CYRILLIC_FONT))
    if rotate:
        page.set_rotation(rotate)
    out = root / "pdfs" / "copy.pdf"
    doc.save(str(out))
    return out


def _lines(root: Path, ref: str = "1-001") -> list[dict]:
    from lxml import etree
    tree = etree.parse(str(root / "mz" / "ocr" / f"chukchi-{ref}.xml"))
    return [{"text": tl.find("{*}String").get("CONTENT"),
             "box": tuple(int(tl.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))}
            for tl in tree.iter("{*}TextLine")]


def test_fragments_on_one_baseline_become_one_row(tmp_path):
    # ~45 px a character at 10 pt and 600 dpi, so the three sit well apart.
    _text(tmp_path, [("весь заговоръ", 700, 300), ("вають ,", 100, 300),
                     ("Праваго", 1800, 300), ("оленя", 100, 600)], master=(2600, 1800))
    rows = [ln["text"] for ln in (textlayer.import_page("1-001", tmp_path), _lines(tmp_path))[1]]
    assert rows == ["вають , весь заговоръ Праваго", "оленя"]


def test_two_fragments_stacked_in_one_column_stay_two_rows(tmp_path):
    """Horizontal overlap is what separates a note set tight under the text."""
    _text(tmp_path, [("первая", 100, 300), ("вторая", 100, 330)])
    textlayer.import_page("1-001", tmp_path)
    assert [ln["text"] for ln in _lines(tmp_path)] == ["первая", "вторая"]


def test_boxes_land_in_master_pixels_net_of_its_placement(tmp_path):
    """The master sits 60 px in from the page corner; the box must not."""
    _text(tmp_path, [("Записано", 200, 400)], at=(60, 90))
    textlayer.import_page("1-001", tmp_path)
    (x, y, w, h), = [ln["box"] for ln in _lines(tmp_path)]
    assert 195 <= x <= 200 and 400 - h <= y < 400 <= y + h + 20


def test_a_rotated_page_is_refused(tmp_path):
    _text(tmp_path, [("текст", 100, 300)], rotate=90)
    with pytest.raises(textlayer.TextLayerError, match="rotated"):
        textlayer.import_page("1-001", tmp_path)


def test_nfc_in_nfd_out(tmp_path):
    _text(tmp_path, [("йц", 100, 300)])           # й, precomposed
    textlayer.import_page("1-001", tmp_path)
    got = _lines(tmp_path)[0]["text"]
    assert got == unicodedata.normalize("NFD", "йц") and len(got) == 3


def test_the_alto_names_the_pdf_as_its_model_by_path_and_digest(tmp_path):
    """The glyphs are the digitizer's guesses, so the file says `model`, and the PDF
    is the only checkpoint that model has."""
    pdf = _text(tmp_path, [("текст", 100, 300)])
    textlayer.import_page("1-001", tmp_path)
    (prod,) = provenance.read_producers(tmp_path / "mz/ocr/chukchi-1-001.xml")
    assert (prod.kind, prod.label, prod.model) == ("model", textlayer.LABEL,
                                                   "pdfs/copy.pdf")
    assert prod.sha256 == provenance.digest(pdf)
    assert prod.inputs["row_overlap"] == str(textlayer.ROW_OVERLAP)
    assert textlayer.imported("1-001", tmp_path)


def test_the_imported_page_is_one_bare_block_like_predicts(tmp_path):
    from lxml import etree
    _text(tmp_path, [("а", 100, 300), ("б", 100, 600)])
    textlayer.import_page("1-001", tmp_path)
    tree = etree.parse(str(tmp_path / "mz/ocr/chukchi-1-001.xml"))
    (block,) = tree.iter("{*}TextBlock")
    assert block.get("ID") == "text_1-001" and block.get("TAGREFS") is None
    assert [tl.get("ID") for tl in tree.iter("{*}TextLine")] == ["mz_1-001_l1",
                                                                  "mz_1-001_l2"]
    assert all(len(tl.findall("{*}String")) == 1 for tl in tree.iter("{*}TextLine"))


def test_the_recognizer_passes_over_an_imported_page(tmp_path):
    from harness.recognize import predict_skip
    _text(tmp_path, [("а", 100, 300)])
    textlayer.import_page("1-001", tmp_path)
    assert "text layer" in predict_skip("1-001", tmp_path)


def test_a_page_already_in_the_store_is_kept_without_force(tmp_path):
    _text(tmp_path, [("а", 100, 300)])
    textlayer.import_page("1-001", tmp_path)
    assert "skipped" in textlayer.import_page("1-001", tmp_path)
    assert "skipped" not in textlayer.import_page("1-001", tmp_path, force=True)


# ---------------------------------------------------------------- alignment
#
# Synthetic ink: each printed line a dense x-height band ending at its baseline,
# and the layer's rows placed where a drifting OCR would put them: its baseline
# `ALIGN_BASELINE_DROP` below the ink's, plus a drift.

import numpy as np  # noqa: E402

DROP = textlayer.ALIGN_BASELINE_DROP


def _page_ink(baselines, x0=600, x1=3586, h=7000):
    ink = np.zeros((h, 4800), dtype=bool)
    for b in baselines:
        ink[b - 44:b + 1, x0:x1] = True          # its last inked row is b
    return ink


def _layer_rows(baselines, drift, x0=600, x1=3586):
    out = []
    for b in baselines:
        lb = b + DROP + drift(b)
        out.append({"text": "строка", "box": (x0, lb - 100, x1, lb + 5), "baseline": lb})
    return out


def test_a_drift_down_the_page_is_fitted_and_taken_off():
    ink_b = [800 + 125 * i for i in range(36)]
    rows = _layer_rows(ink_b, lambda b: round(-0.015 * (b - 800)))
    out, fit = textlayer.align(rows, _page_ink(ink_b))
    assert fit["applied"]
    assert all(abs(r["baseline"] - DROP - b) <= 2 for r, b in zip(out, ink_b, strict=True))
    # Only y moves.
    assert [r["box"][0] for r in out] == [r["box"][0] for r in rows]


def test_an_undrifted_page_is_left_where_it_is():
    ink_b = [800 + 125 * i for i in range(36)]
    rows = _layer_rows(ink_b, lambda b: 0)
    out, fit = textlayer.align(rows, _page_ink(ink_b))
    assert [r["box"] for r in out] == [r["box"] for r in rows]


def test_a_block_placed_on_its_own_keeps_its_own_position():
    # `1-243`: the body drifts 70 px by its foot, its footnotes not at all.
    body = [800 + 125 * i for i in range(36)]
    notes_ink = [body[-1] + 220, body[-1] + 320]
    rows = _layer_rows(body, lambda b: round(-0.015 * (b - 800)))
    rows += _layer_rows(notes_ink, lambda b: 0, x0=810)
    ink = _page_ink(body)
    for b in notes_ink:
        ink[b - 39:b + 1, 810:3586] = True
    out, fit = textlayer.align(rows, ink)
    assert fit["applied"] and fit["own_shift"] >= 1
    assert [r["baseline"] - DROP for r in out[-2:]] == notes_ink


def test_a_page_with_too_few_rows_is_left_as_the_layer_gave_it():
    ink_b = [800, 925, 1050]
    rows = _layer_rows(ink_b, lambda b: 40)
    out, fit = textlayer.align(rows, _page_ink(ink_b))
    assert not fit["applied"] and out == rows
