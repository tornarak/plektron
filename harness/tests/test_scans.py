"""The rasters: cutting them, reading them back, and swapping a re-cut tree in.

**None of this could be tested before.** The cut was `tools/extract_scans.py`, a
PEP 723 script outside the package, so the assertions that matter — that a master
placed at a known offset comes back at that offset, that a photograph pastes as an
exact block, that a page at half scale is refused rather than resampled — had no
file to live in. Part 3 was read ~35 px short on every side for twenty months and
nothing failed, because nothing was asking.

The fixtures build real PDFs with pymupdf rather than mocking the reader: what is
under test is the arithmetic between a PDF's coordinate space and a raster's, and a
fake `page.rect` would be the arithmetic testing itself.

One caution the fixtures encode: **assert on placement and pixels, never on `bpc`.**
PyMuPDF re-encodes an inserted image at its own discretion, so what the manifest
records as bit depth is a fact about the PDF writer and not about the geometry.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from harness import scans
from harness.cli import main

pytest.importorskip("pymupdf")

PT = 72.0 / 300.0            # PostScript points per device pixel at 300 dpi


def _pdf(path: Path, pages: list[dict]) -> Path:
    """Write a PDF whose pages hold images at exact 300 dpi placements.

    Each page is `{"box": (w_px, h_px), "master": (w, h, x, y), "photos": [...]}`,
    everything in **device pixels** — the units the manifest speaks — converted to
    points here so that a test states the geometry it means.
    """
    import pymupdf
    from PIL import Image

    doc = pymupdf.open()
    for spec in pages:
        bw, bh = spec["box"]
        page = doc.new_page(width=bw * PT, height=bh * PT)
        for kind, (w, h, x, y, scale) in spec["images"]:
            im = Image.new("L", (w, h), 255)
            # A recognisable corner, so a paste can be checked for *placement* and
            # not merely for size: a block of ink at (0, 0) of the source.
            for px in range(min(8, w)):
                for py in range(min(8, h)):
                    im.putpixel((px, py), 0)
            if kind == "bitonal":
                im = im.convert("1")
            buf = path.parent / f"_{kind}_{w}x{h}.png"
            im.save(buf)
            rect = pymupdf.Rect(x * PT, y * PT,
                                (x + w * scale) * PT, (y + h * scale) * PT)
            page.insert_image(rect, filename=str(buf))
    doc.save(str(path))
    doc.close()
    return path


def _corpus(root: Path, pages: list[dict], name: str = " Part II ") -> Path:
    d = root / "pdfs"
    d.mkdir(parents=True, exist_ok=True)
    return _pdf(d / f"The Chukchee,{name}- Test.pdf", pages)


def _one_page(root: Path, master=(400, 600), box=(400, 600), at=(0, 0), photos=()):
    images = [("bitonal", (master[0], master[1], at[0], at[1], 1.0))]
    images += [("grey", p) for p in photos]
    return _corpus(root, [{"box": box, "images": images}])


# --- the arithmetic -----------------------------------------------------------

def test_the_snap_rounds_a_float32_edge_to_the_integer_it_is():
    """`1-037`'s live case, as a unit.

    PyMuPDF parses PDF numbers at float32, so an edge that is exactly 435 arrives as
    434.9999897. A bare `floor` grows the rect by a pixel and reports a placement the
    source does not have; `1e-6` would not catch it at all.
    """
    assert scans._out(434.9999897, up=False) == 435
    assert scans._out(434.9999897, up=True) == 435
    # And a *genuine* fraction still rounds outward in both directions. 0.01 pt is
    # 0.0417 px, forty times the snap, so nothing real is inside it.
    assert scans._out(434.5, up=False) == 434
    assert scans._out(434.5, up=True) == 435


def test_the_master_is_found_at_its_own_placement_not_the_page_box(tmp_path):
    """The failure that cost part 3 ~35 px a side: measuring against the page box.

    The master here is 400x600 inside a 440x640 box at (21, 15) — part 1's shape in
    miniature — so a reading taken from the box would give the wrong size *and* the
    wrong origin.
    """
    _one_page(tmp_path, master=(400, 600), box=(440, 640), at=(21, 15))
    manifest, records = scans.extract(tmp_path)
    assert [r["refuse"] for r in records] == [""]
    e = manifest["2-001"]
    assert (e["master"]["w"], e["master"]["h"]) == (400, 600)
    assert e["offset"] == [21, 15]
    # The render size is the *box*, recorded and not computed: master + offset would
    # give 421x615 and miss by the right-hand margin.
    assert e["render"] == [440, 640]


def test_a_bitonal_page_is_cut_at_mode_1_and_its_own_size(tmp_path):
    _one_page(tmp_path, master=(400, 600), box=(440, 640), at=(21, 15))
    out = tmp_path / "cut"
    scans.extract(tmp_path, rasters=out)
    from PIL import Image
    with Image.open(out / "chukchi-2-001.png") as im:
        assert im.size == (400, 600)
        assert im.mode == "1"


def test_a_photograph_pastes_nearest_at_its_integral_scale(tmp_path):
    """Every native sample survives as an exact block, and lands where it was.

    This is what makes a crop from the composite the same pixels as the embedded
    original at a different size, rather than two different pictures.
    """
    _one_page(tmp_path, master=(400, 600), box=(400, 600), at=(0, 0),
              photos=[(50, 40, 100, 200, 2.0)])
    manifest, _ = scans.extract(tmp_path, rasters=tmp_path / "cut")
    im0 = manifest["2-001"]["images"][0]
    assert im0["rect"] == [100, 200, 200, 280]
    assert im0["w"], im0["h"] == (50, 40)

    from PIL import Image
    with Image.open(tmp_path / "cut" / "chukchi-2-001.png") as im:
        assert im.mode == "L"          # a halftone is not two-valued
        # The source's 8x8 ink corner is an exact 16x16 block at the rect's origin.
        assert im.getpixel((100, 200)) == 0
        assert im.getpixel((115, 215)) == 0
        assert im.getpixel((117, 217)) != 0


# --- the refusals -------------------------------------------------------------

def test_a_master_not_at_scale_one_is_refused_not_resampled(tmp_path):
    """The whole point: a page that is not what it claims is named, not rendered."""
    _corpus(tmp_path, [{"box": (400, 600),
                        "images": [("bitonal", (800, 1200, 0, 0, 0.5))]}])
    _, records = scans.extract(tmp_path)
    assert "not at scale 1.0" in records[0]["refuse"]


def test_two_full_page_images_are_refused(tmp_path):
    _corpus(tmp_path, [{"box": (400, 600),
                        "images": [("bitonal", (400, 600, 0, 0, 1.0)),
                                   ("grey", (400, 600, 0, 0, 1.0))]}])
    _, records = scans.extract(tmp_path)
    assert "full-page images" in records[0]["refuse"]


def test_a_photo_outside_its_master_is_refused(tmp_path):
    _one_page(tmp_path, master=(400, 600), box=(500, 700), at=(0, 0),
              photos=[(50, 40, 450, 100, 1.0)])
    _, records = scans.extract(tmp_path)
    assert "falls outside the master" in records[0]["refuse"]


def test_a_non_integral_paste_is_refused(tmp_path):
    _one_page(tmp_path, master=(400, 600), box=(400, 600), at=(0, 0),
              photos=[(50, 40, 100, 200, 1.7)])
    _, records = scans.extract(tmp_path)
    assert "pastes at" in records[0]["refuse"]


def test_a_masterless_page_that_has_a_master_is_refused(tmp_path, monkeypatch):
    """The half of the carve-out nothing checked.

    `MASTERLESS` was asserted in two files and verified in neither, and it is
    precisely the set of pages whose two coordinate spaces differ by a *scale* — so a
    wrong member is every coordinate on that page wrong by a factor, silently. The
    other direction needs no test of its own: a page outside the set with no
    scale-1.0 master is refused by the scale check above.
    """
    monkeypatch.setattr(scans, "MASTERLESS", {"2-001"})
    _one_page(tmp_path, master=(400, 600), box=(400, 600), at=(0, 0))
    _, records = scans.extract(tmp_path)
    assert "named in MASTERLESS" in records[0]["refuse"]


def test_a_dangling_pdfs_link_is_named_rather_than_traced(tmp_path):
    """Every git worktree has one: the links are relative to the primary checkout."""
    d = tmp_path / "pdfs"
    d.mkdir()
    (d / "The Chukchee, Part II - Test.pdf").symlink_to(tmp_path / "nowhere.pdf")
    with pytest.raises(FileNotFoundError, match="dangle in a worktree"):
        scans.extract(tmp_path)


# --- reading the tree back ----------------------------------------------------

def _manifest(root: Path, entries: dict) -> None:
    """`{ref: (master_wh, render_wh, offset, images)}` straight to disk."""
    doc = {}
    for ref, (m, r, o, imgs) in entries.items():
        doc[ref] = {"master": {"w": m[0], "h": m[1], "bpc": 1, "cs": "DeviceGray",
                               "xref": 1, "rendered": False},
                    "render": list(r), "offset": list(o), "images": list(imgs)}
    p = root / "data" / "pdf_images.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"_about": "test", **doc}), encoding="utf-8")


def _raster(root: Path, ref: str, size, mode="1", where="scans") -> Path:
    from PIL import Image
    p = root / where / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, 1 if mode == "1" else 255).save(p)
    return p


def _run(capsys, *argv) -> tuple[int, dict]:
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_info_reports_both_halves_and_whether_they_agree(tmp_path, capsys):
    _manifest(tmp_path, {"2-001": ((400, 600), (440, 640), (21, 15), [])})
    _raster(tmp_path, "2-001", (400, 600))
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "info", "2-001")
    assert code == 0
    # One table, so `--json` is that table bare — a list, not an object.
    row = doc[0]
    assert row["master"] == "400x600" and row["px"] == "400x600"
    assert row["offset"] == "21,15" and row["agrees"] is True


def test_info_says_so_when_the_tree_and_the_manifest_disagree(tmp_path, capsys):
    _manifest(tmp_path, {"2-001": ((400, 600), (440, 640), (21, 15), [])})
    _raster(tmp_path, "2-001", (440, 640))         # the legacy render, still there
    _, doc = _run(capsys, "--root", str(tmp_path), "scans", "info", "2-001")
    # One table, so `--json` is that table bare — a list, not an object.
    row = doc[0]
    assert row["agrees"] is False


def test_audit_gates_on_a_size_and_on_a_mode(tmp_path, capsys):
    """A bitonal page that came back 8-bit means something resampled it."""
    _manifest(tmp_path, {"2-001": ((400, 600), (400, 600), (0, 0), []),
                         "2-002": ((400, 600), (400, 600), (0, 0), [])})
    _raster(tmp_path, "2-001", (440, 640))                  # wrong size
    _raster(tmp_path, "2-002", (400, 600), mode="L")        # wrong mode
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "audit", "--all")
    assert code == 1
    found = {(f["ref"], f["finding"]) for f in doc["findings"] if f["gates"]}
    assert found == {("2-001", "size"), ("2-002", "mode")}


def test_audit_is_clean_when_the_tree_is_what_the_manifest_says(tmp_path, capsys):
    _manifest(tmp_path, {"2-001": ((400, 600), (400, 600), (0, 0), [])})
    _raster(tmp_path, "2-001", (400, 600))
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "audit", "--all")
    assert code == 0 and doc["audit"]["gating"] == 0


def test_census_counts_the_three_kinds(tmp_path, capsys):
    _manifest(tmp_path, {"2-001": ((400, 600), (400, 600), (0, 0), []),
                         "2-002": ((400, 600), (400, 600), (0, 0),
                                   [{"xref": 2, "w": 50, "h": 40, "bpc": 8,
                                     "cs": "DeviceGray", "ppi": 150,
                                     "rect": [10, 10, 110, 90]}])})
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "census", "--all")
    assert code == 0
    assert doc["census"]["bitonal"] == 1
    assert doc["census"]["composite"] == 1
    assert doc["census"]["photographs"] == 1


# --- provenance ---------------------------------------------------------------

def test_a_cut_raster_says_what_it_was_cut_from(tmp_path):
    """`scans/` is `#mz`, and a file copied out of the tree leaves the manifest.

    The digest recorded is the **PDF's**, never the PNG's own: a file's hash of
    itself restates the file and witnesses nothing.
    """
    pdf = _one_page(tmp_path)
    scans.extract(tmp_path, rasters=tmp_path / "cut")
    prov = scans.read_png_provenance(tmp_path / "cut" / "chukchi-2-001.png")
    assert prov.kind == "rule"             # a procedure, not a model's guess
    assert prov.model is None and prov.sha256 is None   # a rule names no checkpoint
    assert prov.inputs["ref"] == "2-001"
    # The basename, never this machine's path.
    assert prov.inputs["source"] == pdf.name
    assert prov.inputs["source_sha256"] == scans._digest(pdf)
    assert prov.inputs["master"] == "400x600"


def test_the_chunk_is_the_same_record_an_alto_would_carry(tmp_path):
    """One vocabulary, three carriers. A raster is `#mz` like an `mz/` ALTO, and
    what it holds is `provenance.encode` of the same `Producer` — so `decode` reads
    either and there is no fourth spelling of the fact to keep in step."""
    from harness import provenance

    _one_page(tmp_path)
    scans.extract(tmp_path, rasters=tmp_path / "cut")
    from PIL import Image
    with Image.open(tmp_path / "cut" / "chukchi-2-001.png") as im:
        raw = im.info[scans.PNG_KEY]
    assert raw.startswith(f"harness: {provenance.SCHEMA}; kind: rule; ")
    assert provenance.decode(raw) == scans.read_png_provenance(
        tmp_path / "cut" / "chukchi-2-001.png")


def test_two_runs_over_one_pdf_are_byte_identical(tmp_path):
    """No timestamp and no absolute path in the chunk, so the tree stays diffable.

    A provenance block carrying the hour it was written would make every re-cut
    differ from the last for a reason that is about nothing, and the check that the
    port reproduced the corpus pixel for pixel could never have been run.
    """
    _one_page(tmp_path)
    scans.extract(tmp_path, rasters=tmp_path / "a")
    scans.extract(tmp_path, rasters=tmp_path / "b")
    assert ((tmp_path / "a" / "chukchi-2-001.png").read_bytes()
            == (tmp_path / "b" / "chukchi-2-001.png").read_bytes())


def test_the_manifest_digests_its_sources(tmp_path):
    pdf = _one_page(tmp_path)
    manifest, _ = scans.extract(tmp_path)
    src = manifest["_sources"]["2"]
    assert src["file"] == pdf.name and src["sha256"] == scans._digest(pdf)
    assert src["pages"] == 1


def test_audit_makes_a_fuss_when_a_source_changed_underneath(tmp_path, capsys):
    """The PDFs live outside the repository behind a symlink and can be replaced.

    Every coordinate in every store is keyed to pixels cut from a particular byte
    sequence, so a source that changed is not necessarily a disaster — it is a
    thing that must not be found out later.
    """
    _one_page(tmp_path)
    scans.extract(tmp_path, rasters=tmp_path / "scans")
    manifest, _ = scans.extract(tmp_path)
    scans.write_manifest(manifest, tmp_path / scans.PDF_IMAGES)

    # The same corpus, re-scanned: a second page makes it a different file.
    _corpus(tmp_path, [{"box": (400, 600),
                        "images": [("bitonal", (400, 600, 0, 0, 1.0))]},
                       {"box": (400, 600),
                        "images": [("bitonal", (400, 600, 0, 0, 1.0))]}])
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "audit", "--all")
    assert code == 1
    changed = [f for f in doc["findings"] if f["finding"] == "source-changed"]
    assert changed and changed[0]["gates"] is True


def test_a_source_this_machine_cannot_see_is_reported_and_does_not_gate(
        tmp_path, capsys):
    """Every worktree's `pdfs/` links dangle, and so does a fresh clone's.

    An audit that failed there is one people learn to run with `|| true`, so the
    absence is a row with `gates: false` — unverifiable is not the same as wrong.
    """
    _one_page(tmp_path)
    manifest, _ = scans.extract(tmp_path, rasters=tmp_path / "scans")
    scans.write_manifest(manifest, tmp_path / scans.PDF_IMAGES)
    for p in (tmp_path / "pdfs").glob("*.pdf"):
        p.unlink()
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "audit", "--all")
    assert code == 0
    absent = [f for f in doc["findings"] if f["finding"] == "source-absent"]
    assert absent and absent[0]["gates"] is False


def test_a_raster_cut_from_another_source_is_a_gating_finding(tmp_path, capsys):
    """Two independent records of one cut: the chunk in the PNG and the manifest
    entry. A disagreement means one of them belongs to a different run."""
    _one_page(tmp_path)
    manifest, _ = scans.extract(tmp_path, rasters=tmp_path / "scans")
    manifest["_sources"]["2"]["sha256"] = "0" * 64
    scans.write_manifest(manifest, tmp_path / scans.PDF_IMAGES)
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "audit", "--all")
    assert code == 1
    assert any(f["finding"] == "source-mismatch" for f in doc["findings"])


def test_a_raster_with_no_chunk_is_unwitnessed_not_wrong(tmp_path, capsys):
    """Every raster cut before the block existed. Reported, never a defect."""
    _manifest(tmp_path, {"2-001": ((400, 600), (400, 600), (0, 0), [])})
    _raster(tmp_path, "2-001", (400, 600))
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "audit", "--all")
    assert code == 0
    unwit = [f for f in doc["findings"] if f["finding"] == "unwitnessed"]
    assert unwit and unwit[0]["gates"] is False


# --- the coordinate-space gate ------------------------------------------------

def _alto(root: Path, store: str, ref: str, size) -> Path:
    p = root / store / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout>'
        f'<Page WIDTH="{size[0]}" HEIGHT="{size[1]}" ID="p">'
        f'<PrintSpace HPOS="0" VPOS="0" WIDTH="{size[0]}" HEIGHT="{size[1]}">'
        '<TextBlock ID="b" HPOS="100" VPOS="200" WIDTH="50" HEIGHT="20"/>'
        "</PrintSpace></Page></Layout></alto>", encoding="utf-8")
    return p


def test_space_gates_on_a_page_left_in_the_legacy_render(tmp_path, capsys):
    _manifest(tmp_path, {"2-001": ((400, 600), (440, 640), (21, 15), [])})
    _alto(tmp_path, "gt/zones", "2-001", (440, 640))
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "space", "--all")
    assert code == 1
    assert doc["not_master"][0]["space"] == "render"


def test_space_passes_when_every_page_is_in_master_space(tmp_path, capsys):
    _manifest(tmp_path, {"2-001": ((400, 600), (440, 640), (21, 15), [])})
    _alto(tmp_path, "gt/zones", "2-001", (400, 600))
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "space", "--all")
    assert code == 0 and doc["space"]["master"] == 1


# --- the swap -----------------------------------------------------------------

def _tree(root: Path, name: str, entries: dict) -> Path:
    """A cut tree: rasters plus the manifest it was cut at."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    doc = {}
    for ref, (m, r, o, imgs) in entries.items():
        doc[ref] = {"master": {"w": m[0], "h": m[1], "bpc": 1, "cs": "DeviceGray",
                               "xref": 1, "rendered": False},
                    "render": list(r), "offset": list(o), "images": list(imgs)}
        _raster(root, ref, m, where=name)
    (d / scans.TREE_MANIFEST).write_text(json.dumps(doc), encoding="utf-8")
    return d


def _swap_corpus(tmp_path: Path) -> Path:
    """A corpus in the old space, and a tree cut 10 px wider and 10 px further in.

    **The re-cut page changes size as well as placement, and it has to.** A page
    whose two spaces are the same size but a non-zero shift apart cannot be placed
    from anything in the file — see the ambiguity test below — so a fixture that
    moved a page without resizing it would be testing a case the code refuses.
    Which is realistic: a master that moved inside its page box moved because the
    crop changed.
    """
    _manifest(tmp_path, {"2-001": ((400, 600), (440, 640), (21, 15), []),
                         "2-002": ((400, 600), (440, 640), (0, 0), [])})
    _raster(tmp_path, "2-001", (400, 600))
    _raster(tmp_path, "2-002", (400, 600))
    _alto(tmp_path, "gt/zones", "2-001", (400, 600))
    _alto(tmp_path, "gt/zones", "2-002", (400, 600))
    # A painted farm and a review working directory, both derived from pixels.
    _raster(tmp_path, "2-001", (400, 600), where="scans/w-figs-blotted")
    (tmp_path / "review" / "2-001" / "crops").mkdir(parents=True)
    (tmp_path / "review" / "2-001" / "proposal.json").write_text("{}", "utf-8")
    return _tree(tmp_path, "cut",
                 {"2-001": ((410, 600), (440, 640), (31, 15), []),
                  "2-002": ((400, 600), (440, 640), (0, 0), [])})


def test_swap_reports_the_shift_and_writes_nothing(tmp_path, capsys):
    _swap_corpus(tmp_path)
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                     str(tmp_path / "cut"))
    assert code == 0
    # The one page that moved, and it moved by the difference of two placements —
    # not by either manifest's `offset`, which is 21 and 31.
    assert [(s["ref"], s["shift"]) for s in doc["shifts"]] == [("2-001", "10,0")]
    assert doc["swap"]["committed"] is False
    assert (tmp_path / "cut").is_dir()          # nothing moved
    from lxml import etree
    b = etree.parse(str(tmp_path / "gt/zones/chukchi-2-001.xml")).find(".//{*}TextBlock")
    assert b.get("HPOS") == "100"


def test_swap_names_every_dependent_and_leaves_authored_images_alone(tmp_path, capsys):
    _swap_corpus(tmp_path)
    _, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                  str(tmp_path / "cut"))
    deps = {d["dependent"] for d in doc["dependents"]}
    assert "gt/zones" in deps and "scans/w-figs-blotted" in deps
    # **The select farms are absent**, being links by filename: a filename does not
    # move under a shift, and a filter on `kind` would have discarded them for
    # nothing.
    assert "scans/plate" not in deps
    # And `review/*/` is never named whole — it holds tracked adjudications.
    assert "review/*/" not in deps
    assert "review/*/crops" in deps
    assert {t["path"] for t in doc["touched_up"]} == {"ed/page-img", "ed/fig-img"}


def test_swap_commits_the_whole_transaction(tmp_path, capsys):
    _swap_corpus(tmp_path)
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                     str(tmp_path / "cut"), "--commit")
    assert code == 0 and doc["swap"]["committed"] is True

    from lxml import etree
    # The moved page's box moved by exactly the shift; its extent did not.
    b = etree.parse(str(tmp_path / "gt/zones/chukchi-2-001.xml")).find(".//{*}TextBlock")
    assert (b.get("HPOS"), b.get("WIDTH")) == ("90", "50")
    # The page that did not move is untouched.
    b2 = etree.parse(str(tmp_path / "gt/zones/chukchi-2-002.xml")).find(".//{*}TextBlock")
    assert b2.get("HPOS") == "100"
    # The tree is installed, without the manifest it travelled with.
    assert (tmp_path / "scans" / "chukchi-2-001.png").exists()
    assert not (tmp_path / "scans" / scans.TREE_MANIFEST).exists()
    assert not (tmp_path / "cut").exists()
    # The painted farm and the derived review images are gone; the adjudication is
    # not.
    assert not (tmp_path / "scans/w-figs-blotted").exists()
    assert not (tmp_path / "review/2-001/crops").exists()
    assert (tmp_path / "review/2-001/proposal.json").exists()
    # The receipt says which space the stores are now in, because a zero shift
    # leaves a page byte-identical and nothing else could tell.
    receipt = json.loads((tmp_path / "data/_migrated.json").read_text())
    assert receipt["2-001"]["shift"] == [10, 0]
    assert receipt["2-002"]["shift"] == [0, 0]
    # And the tracked manifest is the new one.
    assert scans.pdf_images(tmp_path)["2-001"]["offset"] == [31, 15]


def test_a_tree_missing_a_ref_aborts_with_nothing_moved(tmp_path, capsys):
    """The assertion the whole stage-verify-move design exists for."""
    _swap_corpus(tmp_path)
    (tmp_path / "cut" / "chukchi-2-002.png").unlink()
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                     str(tmp_path / "cut"), "--commit")
    assert code == 1
    assert any(r["why"].startswith("missing") for r in doc["refusals"])
    assert doc["swap"]["committed"] is False
    assert (tmp_path / "cut").is_dir()
    from lxml import etree
    b = etree.parse(str(tmp_path / "gt/zones/chukchi-2-001.xml")).find(".//{*}TextBlock")
    assert b.get("HPOS") == "100"
    assert not (tmp_path / "data/_migrated.json").exists()


def test_a_same_size_shift_is_refused_because_no_box_can_place_it(tmp_path, capsys):
    """Part 2's hazard, arriving on a page that actually has to move.

    2550x3525 before and after is why the corpus migration needed a receipt at all:
    a page box cannot distinguish "correctly untouched" from "not yet reached". When
    the shift is *zero* that ambiguity is harmless. When it is not, both available
    guesses are wrong — "already" leaves every coordinate stale, "source" may shift a
    page twice — so the run aborts and nothing moves.
    """
    _manifest(tmp_path, {"2-001": ((400, 600), (440, 640), (21, 15), [])})
    _raster(tmp_path, "2-001", (400, 600))
    _alto(tmp_path, "gt/zones", "2-001", (400, 600))
    _tree(tmp_path, "cut", {"2-001": ((400, 600), (440, 640), (31, 15), [])})
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                     str(tmp_path / "cut"), "--commit")
    assert code == 1
    assert any("which side of it" in r["why"] for r in doc["refusals"])
    assert doc["swap"]["committed"] is False


def test_a_tree_with_no_manifest_is_refused(tmp_path, capsys):
    """A directory of PNGs with no geometry cannot be placed, and saying which
    space it is in would be the guess this group exists to refuse."""
    _swap_corpus(tmp_path)
    (tmp_path / "cut" / scans.TREE_MANIFEST).unlink()
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                     str(tmp_path / "cut"), "--commit")
    assert code == 1
    assert "no manifest" in doc["refusals"][0]["why"]


def test_a_scaled_page_carrying_coordinates_aborts_the_swap(tmp_path):
    """Two spaces related by a ratio: a translation is the wrong operation.

    The masterless RGB leaves are the live case — one 150 ppi photograph each, where
    the legacy render doubled them. They carry no coordinate, which is *why* the
    corpus migration was safe; this checks the fact rather than resting on it.
    """
    from harness import migrate
    old = {"1-361": {"master": {"w": 1833, "h": 1994, "rendered": True},
                     "offset": [0, 0], "render": [3665, 3988], "images": []}}
    new = {"1-361": {"master": {"w": 3665, "h": 3988, "rendered": True},
                     "offset": [0, 0], "render": [3665, 3988], "images": []}}
    step = migrate.plan(old, new)["1-361"]
    assert step["scaled"] is True

    _alto(tmp_path, "gt/fig", "1-361", (1833, 1994))
    rec = migrate.migrate_file(tmp_path / "gt/fig/chukchi-1-361.xml", step, False)
    assert rec["action"] == "ABORTED" and "only translates" in rec["why"]


# --- the flags ----------------------------------------------------------------

def test_a_partial_manifest_is_a_usage_error(tmp_path, capsys):
    """`--commit` and `--rasters` describe the corpus; refs describe a page.

    A manifest written from three refs would look complete and hold three pages,
    which is worse than no manifest — and a three-page tree would pass `swap`'s
    audit against its own three-page manifest and install itself as `scans/`.
    """
    _one_page(tmp_path)
    code = main(["--root", str(tmp_path), "scans", "extract", "2-001", "--commit"])
    assert code == 2
    assert "whole corpus" in capsys.readouterr().err


def test_refs_without_the_write_flags_report_just_those_pages(tmp_path, capsys):
    _corpus(tmp_path, [{"box": (400, 600),
                        "images": [("bitonal", (400, 600, 0, 0, 1.0))]},
                       {"box": (400, 600),
                        "images": [("bitonal", (400, 600, 0, 0, 1.0))]}])
    code, doc = _run(capsys, "--root", str(tmp_path), "scans", "extract", "2-002")
    assert code == 0 and doc["extract"]["pages"] == 1
    assert not (tmp_path / "data" / "pdf_images.json").exists()


# --- the pool -----------------------------------------------------------------

def _multipage(root: Path, n: int) -> Path:
    """A PDF of `n` pages, each a scale-1.0 master, for the pool tests."""
    return _corpus(root, [{"box": (400, 600),
                           "images": [("bitonal", (400, 600, 0, 0, 1.0))]}
                          for _ in range(n)])


def test_the_pool_and_the_serial_arm_agree(tmp_path):
    """**The control arm, and it is the only thing that makes the pool sayable.**

    `parallel.py`'s rule: a sweep that grew a `--jobs` has to stay diffable against
    `--jobs 1`, because "concurrency changed wall clock and nothing else" is a claim
    about output, not about speed. Over the real corpus the two manifests are
    byte-identical and both equal the committed one; this holds it on a synthetic
    so the property is checked on every run rather than on the day someone thought
    to look.
    """
    _multipage(tmp_path, 40)
    serial, recs1 = scans.extract(tmp_path, jobs=1)
    pooled, recs8 = scans.extract(tmp_path, jobs=8)
    assert serial == pooled
    assert [r["ref"] for r in recs1] == [r["ref"] for r in recs8]
    # And in page order, not completion order — the ordering `pchunks` promises.
    assert [r["ref"] for r in recs1] == [f"2-{i:03d}" for i in range(1, 41)]


def test_the_cut_rasters_agree_too(tmp_path):
    """Same again for the pixels, since the workers write them, not the parent."""
    _multipage(tmp_path, 8)
    scans.extract(tmp_path, rasters=tmp_path / "a", jobs=1)
    scans.extract(tmp_path, rasters=tmp_path / "b", jobs=4)
    for ref in (f"2-{i:03d}" for i in range(1, 9)):
        assert ((tmp_path / "a" / f"chukchi-{ref}.png").read_bytes()
                == (tmp_path / "b" / f"chukchi-{ref}.png").read_bytes())


def test_the_bar_is_told_a_ref_and_a_page_count(tmp_path):
    """**What the pool counts is not what a human reads.**

    A chunk is a tuple holding a PDF path, sixteen page numbers and the source
    record with its sha256, and `rich` renders the item field with `str()` — so
    ticking with the work-item filled the terminal with one page's geometry per
    completion, at eight workers, and counted 3 where the report said 40. The bar
    gets a ref and a page count.
    """
    _multipage(tmp_path, 40)
    seen = []
    scans.extract(tmp_path, tick=lambda item, done, total: seen.append(
        (item, done, total)), jobs=4)
    assert all(re.fullmatch(r"\d+-\d{3}", str(i)) for i, _, _ in seen), seen[:2]
    assert [t for _, _, t in seen] == [40] * len(seen)
    assert [d for _, d, _ in seen][-1] == 40


@pytest.mark.parametrize("verb", ["info", "census", "audit", "space"])
def test_the_read_sweeps_label_their_bar_with_a_ref(tmp_path, verb):
    """The same hazard in the four threaded sweeps, whose work-items are
    `(ref, manifest-entry)` and `(store, Path)` pairs."""
    _manifest(tmp_path, {"2-001": ((400, 600), (400, 600), (0, 0), []),
                         "2-002": ((400, 600), (400, 600), (0, 0), [])})
    _raster(tmp_path, "2-001", (400, 600))
    _raster(tmp_path, "2-002", (400, 600))
    _alto(tmp_path, "gt/zones", "2-001", (400, 600))
    seen = []
    tick = lambda item, done, total: seen.append(str(item))   # noqa: E731
    # `info` takes an explicit ref list — the CLI's `_scope` resolves `--all` for
    # it — where the other three read `None` as "every page the manifest holds".
    scope = ["2-001", "2-002"] if verb == "info" else None
    getattr(scans, verb)(scope, tmp_path, tick=tick)
    assert seen, f"{verb} drew no ticks"
    assert all(re.fullmatch(r"\d+-\d{3}", s) for s in seen), seen


def test_a_raster_is_opened_once_for_its_size_and_its_provenance(tmp_path):
    """Five touches of one file where two do.

    `exists()`, an open for the size, a `stat` for the bytes, then a *second* open
    for the `tEXt` chunk. Free on a local disk and four network round trips on the
    NFS this has to run on, so the facts come out of one open. Measured on the real
    corpus: 3062 `openat` to 2224 over 832 pages.
    """
    _one_page(tmp_path)
    scans.extract(tmp_path, rasters=tmp_path / "scans")
    facts = scans._raster_facts(tmp_path / "scans" / "chukchi-2-001.png")
    assert facts["px"] == "400x600"
    assert facts["prov"] is not None and facts["prov"].kind == "rule"


def test_the_dependents_table_counts_this_run_and_not_the_graph(tmp_path, capsys):
    """**What a dry-run prints must be about the run, not about the dependency
    graph.**

    It listed every store as `translated` and every farm as `discarded` — a static
    statement of what *depends on* the geometry — directly above a `stores` block
    reading `migrated: 0`. Two answers to one question in one report, and the
    confident-looking one was wrong: on a re-cut from the same PDFs nothing moves,
    and the table said everything would.
    """
    _swap_corpus(tmp_path)                       # 2-001 shifts, 2-002 does not
    _, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                  str(tmp_path / "cut"))
    by = {d["dependent"]: d for d in doc["dependents"]}
    # gt/zones holds two pages and exactly one of them moves.
    assert (by["gt/zones"]["files"], by["gt/zones"]["changes"]) == (2, 1)
    assert by["gt/zones"]["response"] == "translated"
    # A store with nothing in it says nothing would happen, rather than "translated".
    assert by["gt/ocr"]["changes"] == 0 and by["gt/ocr"]["response"] == "—"
    # The painted farm holds one raster and loses it.
    assert by["scans/w-figs-blotted"]["changes"] == 1
    # And the headline adds up without the reader summing a table.
    assert doc["swap"]["pages_shifted"] == 1
    assert doc["swap"]["files_changing"] == 1


def test_a_swap_that_would_do_nothing_says_so(tmp_path, capsys):
    """The live case: a re-cut from the same PDFs. Every count is zero except the
    rasters themselves and the derived trees that go with them."""
    _manifest(tmp_path, {"2-001": ((400, 600), (400, 600), (0, 0), [])})
    _raster(tmp_path, "2-001", (400, 600))
    _alto(tmp_path, "gt/zones", "2-001", (400, 600))
    _tree(tmp_path, "cut", {"2-001": ((400, 600), (400, 600), (0, 0), [])})
    _, doc = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                  str(tmp_path / "cut"))
    assert doc["swap"]["pages_shifted"] == 0
    assert doc["swap"]["files_changing"] == 0
    assert all(d["response"] == "—" for d in doc["dependents"]
               if d["kind"] == "coordinates")


def test_the_swap_carries_the_trees_source_digests(tmp_path, capsys):
    """**A swap must not unwitness the corpus, and one did.**

    `read_manifest` strips every underscore key, because every other caller wants
    pages and only pages — so `{"_about": ABOUT, **new}` wrote the page entries and
    silently dropped `_sources`, the block digesting the three PDFs. The rasters
    kept their own chunks, so `audit` went on checking a raster against a manifest
    that could no longer say what the sources were: the finding that answers "was
    this cut from the file it claims" lost half its evidence and reported nothing
    about the loss. Found in the live corpus after a real swap, not here.
    """
    _swap_corpus(tmp_path)
    src = {"2": {"file": "test.pdf", "sha256": "a" * 64, "bytes": 1, "pages": 2}}
    tree_manifest = tmp_path / "cut" / scans.TREE_MANIFEST
    doc = json.loads(tree_manifest.read_text())
    tree_manifest.write_text(json.dumps({"_sources": src, **doc}))

    code, _ = _run(capsys, "--root", str(tmp_path), "scans", "swap",
                   str(tmp_path / "cut"), "--commit")
    assert code == 0
    after = scans.manifest_meta(tmp_path / scans.PDF_IMAGES)
    assert after["_sources"] == src, "the tree's digests did not survive the swap"
    assert "_about" in after
