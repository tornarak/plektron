"""The bare-lines rule: `recognize.flatten_page`, and `tools/flatten_ocr.py` over it.

What these hold is the invariant the flatten exists to keep and the property the
plan needed from it. The invariant: document order, line ids and text are
untouched — `index` is identity, and a line that moved would silently re-key an
adjudication. The property: a page fresh from `predict` and a page flattened
after the fact are one shape, and a page already in that shape is a no-op, so the
script can be run twice and the second run says so.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from conftest import write_zones
from lxml import etree

from harness import provenance
from harness.lines import page_lines
from harness.recognize import (
    REC_LABEL,
    block_id,
    flatten_page,
    recognized_by,
)

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
REPO = Path(__file__).resolve().parent.parent.parent


def _tool():
    """`tools/` is scripts, not a package — loaded by path rather than imported."""
    spec = importlib.util.spec_from_file_location(
        "flatten_ocr", REPO / "tools" / "flatten_ocr.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _labelled_page(root: Path, store: str, ref: str = "1-060",
                   rec_sha: str = "abc") -> Path:
    """An `ocr predict`-shaped page as it was written before the rule: two labelled
    blocks, the lines split between them, a line-level `default` type, and the
    two model steps `predict` records."""
    p = root / store / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)

    def line(i, text):
        return (f'<TextLine ID="mz_{ref}_l{i}" HPOS="100" VPOS="{200 + i * 60}" '
                f'WIDTH="1700" HEIGHT="50" TAGREFS="TYPE_3" '
                f'BASELINE="100 {245 + i * 60} 1800 {245 + i * 60}">'
                f'<String CONTENT="{text}" HPOS="100" VPOS="{200 + i * 60}" '
                f'WIDTH="1700" HEIGHT="50"/></TextLine>')

    steps = "".join(
        f'<Processing ID="{ident}"><processingStepDescription>x'
        f'</processingStepDescription><processingStepSettings>'
        f'harness: 1; kind: model; step: harness ocr predict; label: {label}; '
        f'version: kraken 7.0.3; model: m; sha256: {sha}'
        f'</processingStepSettings></Processing>'
        for ident, label, sha in (("OCR_a", "baseline segmentation", "seg"),
                                  ("OCR_b", REC_LABEL, rec_sha)))
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Description><MeasurementUnit>pixel'
        f'</MeasurementUnit>{steps}</Description>'
        '<Tags>'
        '<OtherTag ID="TYPE_1" TYPE="type" LABEL="RunningTitleZone"/>'
        '<OtherTag ID="TYPE_2" TYPE="type" LABEL="MainZone-P"/>'
        '<OtherTag ID="TYPE_3" TYPE="type" LABEL="default"/>'
        '</Tags>'
        '<Layout><Page ID="p" WIDTH="2000" HEIGHT="3000"><PrintSpace>'
        f'<TextBlock ID="mz_{ref}_r1" HPOS="100" VPOS="260" WIDTH="1700" '
        f'HEIGHT="50" TAGREFS="TYPE_1">{line(1, "head")}</TextBlock>'
        f'<TextBlock ID="mz_{ref}_r2" HPOS="100" VPOS="320" WIDTH="1700" '
        f'HEIGHT="110" TAGREFS="TYPE_2">{line(2, "body one")}{line(3, "body two")}'
        '</TextBlock>'
        '</PrintSpace></Page></Layout></alto>',
        encoding="utf-8")
    return p


def _digest(p: Path) -> tuple:
    return _tool().digest(etree.parse(str(p)).getroot())


# ------------------------------------------------------------------ the shape


def test_the_flatten_keeps_ids_boxes_and_text_in_document_order(tmp_path):
    p = _labelled_page(tmp_path, "mz/ocr")
    before = _digest(p)
    alto = etree.parse(str(p)).getroot()
    assert flatten_page(alto, "1-060") is True
    assert _tool().digest(alto) == before
    blocks = alto.findall(".//{*}TextBlock")
    assert [b.get("ID") for b in blocks] == [block_id("1-060")]
    assert blocks[0].get("TAGREFS") is None
    # The block's rectangle is the union of its lines'.
    assert (blocks[0].get("VPOS"), blocks[0].get("HEIGHT")) == ("260", "170")


def test_the_flatten_keeps_the_tags_something_still_references(tmp_path):
    """The line-level `default` type stays; the two block types nothing points at
    any more go. Membership by reference, not by a list of zone labels."""
    p = _labelled_page(tmp_path, "mz/ocr")
    alto = etree.parse(str(p)).getroot()
    flatten_page(alto, "1-060")
    labels = [t.get("LABEL") for t in alto.find(".//{*}Tags")]
    assert labels == ["default"]


def test_a_flattened_page_is_a_no_op(tmp_path):
    p = _labelled_page(tmp_path, "mz/ocr")
    alto = etree.parse(str(p)).getroot()
    assert flatten_page(alto, "1-060") is True
    assert flatten_page(alto, "1-060") is False


def test_page_lines_reads_a_labelled_page_and_its_flattened_form_alike(tmp_path):
    """The point: `zone` is containment against `gt/zones/`, so the baked labels
    were never read and taking them out changes nothing a consumer sees."""
    p = _labelled_page(tmp_path, "mz/ocr")
    # Bands in raster space that hold line 1 and lines 2–3 respectively.
    write_zones(tmp_path, "1-060", [("RunningTitleZone", 250, 320),
                                    ("MainZone-P", 320, 440)])
    labelled = [(r["index"], r["line_id"], r["zone"], r["text"])
                for r in page_lines(p, tmp_path, ref="1-060")]
    _tool().flatten_file(p, commit=True)
    flat = [(r["index"], r["line_id"], r["zone"], r["text"])
            for r in page_lines(p, tmp_path, ref="1-060")]
    assert labelled == flat
    assert [z for _, _, z, _ in flat] == ["RunningTitleZone", "MainZone-P",
                                         "MainZone-P"]


# ------------------------------------------------------------------ the tool


def test_the_tool_appends_a_rule_step_and_leaves_the_recognizer_findable(tmp_path):
    """A file names what produced it, and the recognizer is selected by label —
    `read_producer`'s "last step" would now name the flatten."""
    p = _labelled_page(tmp_path, "mz/ocr", rec_sha="abc")
    rep = _tool().flatten_file(p, commit=True)
    assert rep["changed"] and rep["written"]
    steps = provenance.read_producers(p)
    assert [s.label for s in steps] == ["baseline segmentation", REC_LABEL, "flatten"]
    assert steps[-1].kind == "rule" and steps[-1].step == "tools/flatten_ocr.py"
    assert recognized_by("1-060", "abc", tmp_path)
    assert not recognized_by("1-060", "other", tmp_path)


def test_the_tool_writes_nothing_without_commit(tmp_path):
    p = _labelled_page(tmp_path, "gt/ocr")
    before = p.read_bytes()
    rep = _tool().flatten_file(p, commit=False)
    assert rep == {"path": str(p), "changed": True, "written": False}
    assert p.read_bytes() == before


def test_the_tool_refuses_when_the_digest_moves(tmp_path, monkeypatch):
    """The gate is a real gate: a flatten that touched a line would be refused
    rather than written."""
    tool = _tool()
    p = _labelled_page(tmp_path, "mz/ocr")

    def broken(alto, ref):
        flatten_page(alto, ref)
        alto.find(".//{*}String").set("CONTENT", "moved")
        return True

    monkeypatch.setattr(tool, "flatten_page", broken)
    with pytest.raises(ValueError, match="refusing to write"):
        tool.flatten_file(p, commit=True)


def test_a_second_run_is_clean(tmp_path, capsys):
    import sys
    tool = _tool()
    _labelled_page(tmp_path, "mz/ocr")
    _labelled_page(tmp_path, "gt/ocr")
    monkey = ["flatten_ocr.py", "--root", str(tmp_path), "--commit"]
    sys.argv, saved = monkey, sys.argv
    try:
        tool.main()
        first = capsys.readouterr().out
        tool.main()
        second = capsys.readouterr().out
    finally:
        sys.argv = saved
    assert "gt/ocr: 1 of 1 to flatten" in first
    assert "Clean." in second
