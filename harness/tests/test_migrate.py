"""Moving every stored coordinate into the extracted master's space.

The migration is a **translation**, which is the whole reason it can be checked
this hard: extents do not move, so a width that changed means the operation was
something other than what it claims, and the round trip is exact rather than
approximately exact. `tools/migrate_coords.py` — the 150→300 dpi migration — could
promise neither, because a resample really does resize things.

Two hazards this file exists for. The first is the **vacuous gate**:
`migrate_coords.content_digest` hashes `String/@CONTENT`, and `gt/zones/`,
`gt/fig/` and `mz/zones/` have none at all, so it would pass on the majority of
what is touched while checking nothing. The second is **part 2**, which does not
move: its pages are 2550x3525 before and after, so no dimension check can tell
"correctly untouched" from "not yet reached", and only the receipt can.
"""
from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

from harness import migrate

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

MASTER = (2781, 3866)
RENDER = (2824, 3897)
SHIFT = [21, 15]


def _manifest(root: Path, refs: dict[str, tuple]) -> None:
    """`{ref: (master, render, offset)}`."""
    p = root / "data" / "pdf_images.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {ref: {"master": {"w": m[0], "h": m[1], "bpc": 1, "cs": "DeviceGray",
                            "xref": 1, "rendered": False},
                 "render": list(r), "offset": list(o), "images": []}
           for ref, (m, r, o) in refs.items()}
    p.write_text(json.dumps(doc), encoding="utf-8")


def _alto(root: Path, store: str, ref: str, blocks, size=RENDER,
          with_text: bool = False, with_description: bool = True) -> Path:
    p = root / store / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = ""
    for bid, x, y, w, h in blocks:
        inner = ""
        if with_text:
            inner = (f'<TextLine ID="{bid}_l" HPOS="{x}" VPOS="{y}" '
                     f'WIDTH="{w}" HEIGHT="20" BASELINE="{x} {y + 18} '
                     f'{x + w} {y + 18}">'
                     f'<String ID="{bid}_s" CONTENT="word" HPOS="{x}" '
                     f'VPOS="{y}" WIDTH="40" HEIGHT="20"/></TextLine>')
        body += (f'<TextBlock ID="{bid}" TAGREFS="BT1" HPOS="{x}" VPOS="{y}" '
                 f'WIDTH="{w}" HEIGHT="{h}">'
                 f'<Shape><Polygon POINTS="{x} {y} {x + w} {y} '
                 f'{x + w} {y + h} {x} {y + h}"/></Shape>{inner}</TextBlock>')
    desc = "<Description><sourceImageInformation><fileName>x.png</fileName>" \
           "</sourceImageInformation></Description>" if with_description else ""
    p.write_text(
        f'<alto xmlns="{ALTO_NS}">{desc}<Layout>'
        f'<Page WIDTH="{size[0]}" HEIGHT="{size[1]}" ID="p">'
        f'<PrintSpace HPOS="0" VPOS="0" WIDTH="{size[0]}" HEIGHT="{size[1]}">'
        f"{body}</PrintSpace></Page></Layout>"
        '<Tags><OtherTag ID="BT1" LABEL="MainZone-P"/></Tags></alto>',
        encoding="utf-8")
    return p


def _boxes(path: Path):
    t = etree.parse(str(path))
    return [(b.get("ID"), int(float(b.get("HPOS"))), int(float(b.get("VPOS"))),
             int(float(b.get("WIDTH"))), int(float(b.get("HEIGHT"))))
            for b in t.iter("{*}TextBlock")]


# --- the translation ---------------------------------------------------------

def test_positions_move_and_extents_do_not(tmp_path):
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/zones", "1-100", [("mz_1-100_001", 500, 900, 1778, 160)])
    migrate.run(tmp_path, commit=True)
    assert _boxes(p) == [("mz_1-100_001", 479, 885, 1778, 160)]


def test_the_page_box_becomes_the_master(tmp_path):
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/zones", "1-100", [("a", 500, 900, 100, 100)])
    migrate.run(tmp_path, commit=True)
    t = etree.parse(str(p))
    page = t.find(".//{*}Page")
    assert (int(page.get("WIDTH")), int(page.get("HEIGHT"))) == MASTER
    ps = t.find(".//{*}PrintSpace")
    assert (int(ps.get("WIDTH")), int(ps.get("HEIGHT"))) == MASTER


def test_polygons_and_baselines_move_too(tmp_path):
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/ocr", "1-100", [("a", 500, 900, 200, 100)],
              with_text=True)
    migrate.run(tmp_path, commit=True)
    t = etree.parse(str(p))
    poly = t.find(".//{*}Polygon").get("POINTS").split()
    assert poly[:2] == ["479", "885"]
    base = t.find(".//{*}TextLine").get("BASELINE").split()
    assert base[:2] == ["479", "903"]


def test_the_translation_is_exactly_invertible(tmp_path):
    """A ratio is not. This is the property that lets a mistake be undone rather
    than merely regretted."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    blocks = [("a", 500, 900, 1778, 160), ("b", 37, 21, 300, 90)]
    p = _alto(tmp_path, "gt/zones", "1-100", blocks)
    before = _boxes(p)
    migrate.run(tmp_path, commit=True)
    # And back, by declaring the master to be the render and vice versa.
    _manifest(tmp_path, {"1-100": (RENDER, MASTER, [-SHIFT[0], -SHIFT[1]])})
    migrate.run(tmp_path, commit=True)
    assert _boxes(p) == before


def test_a_page_already_in_master_space_is_left_alone(tmp_path):
    """Part 2's whole corpus. Re-running must not shift it a second time."""
    _manifest(tmp_path, {"2-100": ((2550, 3525), (2550, 3525), [0, 0])})
    p = _alto(tmp_path, "gt/zones", "2-100", [("a", 390, 600, 1776, 200)],
              size=(2550, 3525))
    rep = migrate.run(tmp_path, commit=True)
    assert rep["already"] == 1 and rep["migrated"] == 0
    assert _boxes(p) == [("a", 390, 600, 1776, 200)]


def test_a_page_in_neither_space_aborts_rather_than_guessing(tmp_path):
    """Assuming an unrecognised box must be the old one is how a store gets
    shifted twice."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    _alto(tmp_path, "gt/zones", "1-100", [("a", 10, 10, 50, 50)], size=(999, 999))
    rep = migrate.run(tmp_path, commit=True)
    assert rep["aborted"] == 1
    assert "neither" in rep["files"][0]["why"]


# --- the gates ---------------------------------------------------------------

def test_the_text_digest_is_vacuous_on_a_geometry_store(tmp_path):
    """Not a defect — a fact that the second gate exists because of. `gt/zones/`
    carries no `String` at all, so a text digest over it hashes the empty
    sequence and would pass whatever happened to the boxes."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/zones", "1-100", [("a", 500, 900, 100, 100)])
    t = etree.parse(str(p))
    assert migrate.text_digest(t) == migrate.text_digest(etree.parse(str(
        _alto(tmp_path, "gt/zones", "1-101", [("z", 1, 2, 3, 4)]))))


def test_the_structural_digest_catches_a_changed_extent(tmp_path):
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/zones", "1-100", [("a", 500, 900, 100, 100)])
    before = migrate.structural_digest(etree.parse(str(p)))
    _alto(tmp_path, "gt/zones", "1-100", [("a", 500, 900, 101, 100)])
    assert migrate.structural_digest(etree.parse(str(p))) != before


def test_the_structural_digest_catches_a_dropped_block(tmp_path):
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/zones", "1-100",
              [("a", 500, 900, 100, 100), ("b", 500, 1100, 100, 100)])
    before = migrate.structural_digest(etree.parse(str(p)))
    _alto(tmp_path, "gt/zones", "1-100", [("a", 500, 900, 100, 100)])
    assert migrate.structural_digest(etree.parse(str(p))) != before


def test_the_structural_digest_is_blind_to_the_page_box(tmp_path):
    """`Page` and `PrintSpace` state the raster's size rather than describe a box
    on it, so they are meant to change. Hashing them aborted every page in the
    corpus as 'structure changed' — the check being wrong, not the data."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    a = _alto(tmp_path, "gt/zones", "1-100", [("a", 5, 9, 100, 100)], size=RENDER)
    b = _alto(tmp_path, "gt/zones", "1-101", [("a", 5, 9, 100, 100)], size=MASTER)
    assert (migrate.structural_digest(etree.parse(str(a)))
            == migrate.structural_digest(etree.parse(str(b))))


def test_a_clamped_human_box_is_counted_apart_from_a_machine_one(tmp_path):
    """A prediction pulled back to the edge is noise in a store that `zones
    predict --force` rewrites; a human's box losing pixels is a keyed judgement
    being altered by a migration. One number would hide the difference."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT), "1-101": (MASTER, RENDER, SHIFT)})
    _alto(tmp_path, "mz/zones", "1-100", [("a", 3, 4, 100, 100)])
    rep = migrate.run(tmp_path, commit=True)
    assert rep["clamped"] > 0 and rep["clamped_gt"] == 0
    _alto(tmp_path, "gt/zones", "1-101", [("a", 3, 4, 100, 100)])
    rep = migrate.run(tmp_path, commit=True)
    assert rep["clamped_gt"] > 0


# --- the stores that do not look like the others ------------------------------

def test_a_fragment_with_no_description_still_migrates(tmp_path):
    """`gt/lines/` fragments carry no `Description`, so resolving the raster
    through `sourceImageInformation/fileName` skipped every one of them — a
    silent no-op leaving that store behind while `gt/ocr/` moved."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/lines", "1-100", [("corr_1-100-671", 500, 671, 100, 40)],
              with_description=False)
    rep = migrate.run(tmp_path, commit=True)
    assert rep["migrated"] == 1
    assert _boxes(p)[0][1:3] == (479, 656)


def test_a_correction_id_keeps_the_y_it_was_minted_at(tmp_path):
    """The id is a key, not a measurement: `corrections.save_lines` carries text
    forward by it. Re-minting would break that to keep an arithmetic tidy."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/lines", "1-100", [("corr_1-100-671", 500, 671, 100, 40)],
              with_description=False)
    rep = migrate.run(tmp_path, commit=True)
    assert _boxes(p)[0][0] == "corr_1-100-671"
    assert rep["correction_pages_with_y_in_ids"] == ["1-100"]


def test_a_band_ledger_moves_in_y_and_its_prose_is_left_alone(tmp_path):
    _manifest(tmp_path, {"1-116": (MASTER, RENDER, SHIFT)})
    p = tmp_path / "gt" / "zones" / "_para_exempt.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    note = "indent 170 px against the book's 107-110, on a 695 px ink run"
    p.write_text(json.dumps({"1-116": [{"y0": 2880, "y1": 2930, "note": note}]}),
                 encoding="utf-8")
    rep = migrate.run(tmp_path, commit=True)
    got = json.loads(p.read_text(encoding="utf-8"))["1-116"][0]
    assert (got["y0"], got["y1"]) == (2865, 2915)
    assert got["note"] == note
    assert any(note[:20] in n for b in rep["bands"] for n in b["notes_with_px"])


def test_the_ink_cache_is_deleted_not_migrated(tmp_path):
    """Its stamp is ALTO and exemption mtimes, never the raster — so on part 2,
    whose ALTOs do not move while the raster's content changes underneath them,
    every cached verdict would go on looking valid."""
    _manifest(tmp_path, {"2-100": ((2550, 3525), (2550, 3525), [0, 0])})
    p = tmp_path / "gt" / "zones" / "_ink_cache.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"2-100": {"state": "clean", "stamp": [1, 2]}}', encoding="utf-8")
    rep = migrate.run(tmp_path, commit=True)
    assert "gt/zones/_ink_cache.json" in rep["dropped"]
    assert not p.exists()


# --- the receipt -------------------------------------------------------------

def test_an_unmoved_page_is_recorded_rather_than_omitted(tmp_path):
    """Part 2 is 2550x3525 before and after, so no dimension check can tell
    'correctly untouched' from 'not yet reached'. The receipt is the only thing
    that can, which means it has to name the pages that did not move."""
    _manifest(tmp_path, {"2-100": ((2550, 3525), (2550, 3525), [0, 0]),
                         "1-100": (MASTER, RENDER, SHIFT)})
    _alto(tmp_path, "gt/zones", "2-100", [("a", 390, 600, 100, 100)],
          size=(2550, 3525))
    _alto(tmp_path, "gt/zones", "1-100", [("b", 500, 900, 100, 100)])
    migrate.run(tmp_path, commit=True)
    doc = migrate.read_receipt(tmp_path)
    assert doc["2-100"]["shift"] == [0, 0]
    assert doc["1-100"]["shift"] == SHIFT


def _masterless(root: Path, ref: str, native, render) -> None:
    p = root / "data" / "pdf_images.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    doc[ref] = {"master": {"w": native[0], "h": native[1], "bpc": 8,
                           "cs": "DeviceRGB", "xref": 1, "rendered": True},
                "render": list(render), "offset": [0, 0], "images": []}
    p.write_text(json.dumps(doc), encoding="utf-8")


def test_a_masterless_page_gets_its_page_box_and_nothing_else(tmp_path):
    """The three RGB leaves are one 150 ppi photograph each, so their two spaces
    differ by a **scale**. Safe only because all three are fully exempt and hold no
    coordinate: setting the page box and shifting nothing is exactly right.
    """
    _masterless(tmp_path, "1-361", (1833, 1994), (3665, 3988))
    p = _alto(tmp_path, "gt/zones", "1-361", [], size=(3665, 3988))
    rep = migrate.run(tmp_path, commit=True)
    assert rep["migrated"] == 1 and rep["aborted"] == 0
    page = etree.parse(str(p)).find(".//{*}Page")
    assert (int(page.get("WIDTH")), int(page.get("HEIGHT"))) == (1833, 1994)


def test_a_masterless_page_holding_coordinates_is_refused(tmp_path):
    """This module only translates, and a ratio is what that page would need. The
    emptiness is a fact about this corpus, so it is checked rather than relied on.
    """
    _masterless(tmp_path, "1-361", (1833, 1994), (3665, 3988))
    _alto(tmp_path, "gt/zones", "1-361", [("a", 500, 900, 100, 100)],
          size=(3665, 3988))
    rep = migrate.run(tmp_path, commit=True)
    assert rep["aborted"] == 1
    assert "only translates" in rep["files"][0]["why"]


def test_a_page_box_is_not_a_coordinate(tmp_path):
    """`PrintSpace/@HPOS` states where the raster starts, which is always 0 — it
    does not describe a box on the page. Counting it made all three masterless
    pages abort as "carries coordinates", the same distinction `structural_digest`
    had to make one function earlier.
    """
    _masterless(tmp_path, "1-001", (1391, 1933), (2781, 3866))
    _alto(tmp_path, "gt/zones", "1-001", [], size=(2781, 3866))
    assert migrate.run(tmp_path, commit=True)["aborted"] == 0


def test_report_mode_writes_nothing_at_all(tmp_path):
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    p = _alto(tmp_path, "gt/zones", "1-100", [("a", 500, 900, 100, 100)])
    cache = tmp_path / "gt" / "zones" / "_ink_cache.json"
    cache.write_text("{}", encoding="utf-8")
    rep = migrate.run(tmp_path)
    assert rep["migrated"] == 1
    assert _boxes(p) == [("a", 500, 900, 100, 100)]
    assert cache.exists()
    assert not migrate.receipt_path(tmp_path).exists()


def test_an_abort_anywhere_stops_the_receipt(tmp_path):
    """A receipt naming a partially migrated corpus is worse than none: it is the
    one artefact that says the migration happened."""
    _manifest(tmp_path, {"1-100": (MASTER, RENDER, SHIFT)})
    _alto(tmp_path, "gt/zones", "1-100", [("a", 500, 900, 100, 100)])
    _alto(tmp_path, "gt/ocr", "1-101", [("b", 500, 900, 100, 100)])
    rep = migrate.run(tmp_path, commit=True)
    assert rep["aborted"] == 1
    assert rep["receipt"] == ""
    assert not migrate.receipt_path(tmp_path).exists()


def test_no_manifest_is_an_error_and_not_a_silent_no_op(tmp_path):
    rep = migrate.run(tmp_path, commit=True)
    assert "scans extract" in rep["error"]
