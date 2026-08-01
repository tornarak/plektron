"""The training corpus: figure-blotted rasters, and the segtrain symlink farm.

Two properties here are the reason the code is shaped the way it is.

**The blot is white and the source mode is kept.** `lines.write_blot` paints pink
and blue because a human reads it; this one is training input, so a filled coloured
box would be a feature that exists nowhere at inference time. And since the 580
figure-less pages reach the trainer as symlinks to the untouched scan, converting
the painted ones to greyscale would make colour depth correlate with "has a figure"
— the exact confound the blot exists to remove.

**Assembly refuses a page whose blot is missing.** Falling back to the plain scan
would train part of the set on unblotted pages and produce a model that looks fine
everywhere except the 252 pages that matter.
"""
from __future__ import annotations
from pathlib import Path

from PIL import Image

from harness import zones as zn


def make_scan(tmp_path: Path, ref: str, size=(600, 800), mode="RGB"):
    d = tmp_path / "scans"
    d.mkdir(parents=True, exist_ok=True)
    im = Image.new(mode, size, "white" if mode == "RGB" else 255)
    # A black block where the "figure" will be, so blotting is observable.
    im.paste(Image.new(mode, (200, 150), "black" if mode == "RGB" else 0), (100, 300))
    im.save(d / f"chukchi-{ref}.png")


def make_fig_alto(tmp_path: Path, ref: str, size=(600, 800),
                  box=(100, 300, 200, 150)):
    d = tmp_path / "gt" / "fig"
    d.mkdir(parents=True, exist_ok=True)
    x, y, w, h = box
    (d / f"chukchi-{ref}.xml").write_text(f"""<?xml version="1.0"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Tags><OtherTag ID="BT1" LABEL="GraphicZone" DESCRIPTION="block type GraphicZone"/></Tags>
  <Layout><Page WIDTH="{size[0]}" HEIGHT="{size[1]}">
    <PrintSpace HPOS="0" VPOS="0" WIDTH="{size[0]}" HEIGHT="{size[1]}">
      <TextBlock HPOS="{x}" VPOS="{y}" WIDTH="{w}" HEIGHT="{h}" ID="b1" TAGREFS="BT1">
        <Shape><Polygon POINTS="{x} {y} {x+w} {y} {x+w} {y+h} {x} {y+h}"/></Shape>
      </TextBlock>
    </PrintSpace></Page></Layout></alto>""", encoding="utf-8")


def test_a_figure_page_is_painted_white(tmp_path):
    make_scan(tmp_path, "3-006")
    make_fig_alto(tmp_path, "3-006")
    rep = zn.blot_one("3-006", tmp_path)
    assert rep["action"] == "painted" and rep["painted"] == 1
    im = Image.open(rep["path"])
    assert im.getpixel((150, 350)) == (255, 255, 255)


def test_the_blot_keeps_the_source_mode(tmp_path):
    """Colour depth must not end up correlated with 'has a figure'."""
    make_scan(tmp_path, "3-006")
    make_fig_alto(tmp_path, "3-006")
    make_scan(tmp_path, "1-048")
    painted = Image.open(zn.blot_one("3-006", tmp_path)["path"])
    linked = Image.open(zn.blot_one("1-048", tmp_path)["path"])
    assert painted.mode == linked.mode == "RGB"


def test_the_blot_keeps_the_page_dimensions(tmp_path):
    make_scan(tmp_path, "3-006")
    make_fig_alto(tmp_path, "3-006")
    assert Image.open(zn.blot_one("3-006", tmp_path)["path"]).size == (600, 800)


def test_text_outside_the_figure_survives(tmp_path):
    """Only the declared zones go. Blotting the page would be a blank page."""
    make_scan(tmp_path, "3-006")
    make_fig_alto(tmp_path, "3-006", box=(100, 300, 50, 50))
    im = Image.open(zn.blot_one("3-006", tmp_path)["path"])
    assert im.getpixel((125, 325)) == (255, 255, 255)   # inside the zone
    assert im.getpixel((250, 400)) == (0, 0, 0)         # the rest of the block


def test_a_figureless_page_is_linked_not_copied(tmp_path):
    """580 of 832 pages; copying them duplicates ~1.5 GB for nothing."""
    make_scan(tmp_path, "1-048")
    rep = zn.blot_one("1-048", tmp_path)
    assert rep["action"] == "linked"
    assert Path(rep["path"]).is_symlink()


def test_the_link_is_relative(tmp_path):
    """So the tree survives the repo being moved, as review/*/page.png does."""
    make_scan(tmp_path, "1-048")
    link = Path(zn.blot_one("1-048", tmp_path)["path"])
    assert not Path(link.readlink()).is_absolute()


def test_blotting_is_idempotent_and_unconditional(tmp_path):
    """A figure ALTO corrected after the blot must not leave a stale raster, so
    there is no mtime test to get wrong — it simply repaints."""
    make_scan(tmp_path, "3-006")
    make_fig_alto(tmp_path, "3-006", box=(100, 300, 50, 50))
    zn.blot_one("3-006", tmp_path)
    make_fig_alto(tmp_path, "3-006", box=(100, 300, 200, 150))
    zn.blot_one("3-006", tmp_path)
    im = Image.open(zn.blot_dir(tmp_path) / "chukchi-3-006.png")
    assert im.getpixel((250, 400)) == (255, 255, 255)


def test_relinking_over_an_existing_link_does_not_fail(tmp_path):
    make_scan(tmp_path, "1-048")
    zn.blot_one("1-048", tmp_path)
    assert zn.blot_one("1-048", tmp_path)["action"] == "linked"


def test_missing_raster_is_reported_not_raised(tmp_path):
    assert zn.blot_one("9-999", tmp_path)["action"] == "no-raster"


def test_sweep_counts_both_kinds(tmp_path):
    for ref in ("1-048", "1-151", "3-006"):
        make_scan(tmp_path, ref)
    make_fig_alto(tmp_path, "3-006")
    rep = zn.blot_all(tmp_path)
    assert (rep["painted"], rep["linked"], rep["total"]) == (1, 2, 3)


# ------------------------------------------------------------------ assemble

def keyed(tmp_path: Path, ref: str, split: str = "train"):
    make_scan(tmp_path, ref)
    zn.save_zones(ref, [{"label": "MainZone-P", "x0": 100, "y0": 100,
                         "x1": 500, "y1": 700}], tmp_path, split=split)


def test_assembly_pairs_each_alto_with_its_blotted_raster(tmp_path):
    """ketos resolves the image through the ALTO's own fileName, relative to the
    XML — so the two have to sit in one directory under that exact name."""
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    work = Path(rep["dir"])
    assert (work / "chukchi-1-048.xml").is_symlink()
    assert (work / "chukchi-1-048.png").is_symlink()
    assert (work / "chukchi-1-048.png").resolve() == \
        (zn.blot_dir(tmp_path) / "chukchi-1-048.png").resolve()


def test_assembly_splits_by_the_marks(tmp_path):
    keyed(tmp_path, "1-048", "train")
    keyed(tmp_path, "1-151", "eval")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    assert (rep["train"], rep["eval"]) == (1, 1)
    work = Path(rep["dir"])
    assert "chukchi-1-048.xml" in (work / "train.lst").read_text()
    assert "chukchi-1-151.xml" in (work / "eval.lst").read_text()


def test_the_lists_name_the_work_dir_copy_not_the_store(tmp_path):
    """kraken reads the raster from `filename.parent / fileName`, so the path in
    the list decides which image is trained on.

    Resolving it followed the symlink back to `gt/zones/` — the lists named the
    real ALTO, kraken looked for the raster beside *that*, and the blot links this
    whole function exists to make were never read. It failed loudly only because
    `gt/zones/` holds no PNGs; one scan copied in there and the entire set would
    have trained unblotted, teaching exactly the figure-shaped body zone the blot
    prevents.
    """
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    line = (Path(rep["dir"]) / "train.lst").read_text().strip()
    assert line == f"{zn.WORKDIR}/chukchi-1-048.xml"
    assert "gt/zones" not in line


def test_the_lists_hold_no_absolute_path(tmp_path):
    """An absolute path records the machine it was assembled on. The directory is
    gitignored, so nothing leaks, but a `.gitignore` line is not a reason to write
    one down."""
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    for split in ("train", "eval"):
        for line in (Path(rep["dir"]) / f"{split}.lst").read_text().split():
            assert not Path(line).is_absolute()


def test_assembly_leaves_exempt_pages_out_of_both_lists(tmp_path):
    """A plate is neither an example of the layout nor a fair test of it —
    letting one into eval would report a model wrong about a page with no right
    answer. Counted rather than silently dropped."""
    keyed(tmp_path, "1-048", "train")
    keyed(tmp_path, "1-049", "exempt")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    assert (rep["train"], rep["eval"], rep["exempt_skipped"]) == (1, 0, 1)
    work = Path(rep["dir"])
    assert not (work / "chukchi-1-049.xml").exists()
    assert "chukchi-1-049" not in (work / "train.lst").read_text()
    assert "chukchi-1-049" not in (work / "eval.lst").read_text()


def test_assembly_refuses_a_page_with_no_blot(tmp_path):
    """Falling back to the plain scan would train part of the set unblotted."""
    keyed(tmp_path, "1-048")
    rep = zn.assemble(tmp_path)
    assert rep["missing_blot"] == "1-048"
    assert rep["train"] == 0
    assert not (Path(rep["dir"]) / "chukchi-1-048.xml").exists()


def test_assembly_is_rerunnable(tmp_path):
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    zn.assemble(tmp_path)
    assert zn.assemble(tmp_path)["train"] == 1


def test_assembly_reports_a_command_it_does_not_run(tmp_path):
    """The ketos CLI moved across majors 3-7; the flags are verified at the
    moment of use, never trusted from a docstring."""
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    assert "ketos" in rep["command"] and "segtrain" in rep["command"]
    assert "ketos --help" in rep["note"]
    assert Path(rep["dir"]).name in rep["command"]      # the lists it just wrote


def test_the_seed_precedes_the_subcommand(tmp_path):
    """kraken 7's `-s` is on the `ketos` group and means the seed; on `segtrain`
    the same letter is the VGSL spec, so putting it after would silently train a
    different network rather than fail."""
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    head, tail = zn.assemble(tmp_path)["command"].split("segtrain", 1)
    assert "-s 42" in head and " -s " not in tail


def test_the_command_runs_as_printed(tmp_path):
    """Reversed on purpose. This used to assert that `-d` and `--workers` were
    *absent*, on the grounds that they describe whoever is running rather than what
    the corpus needs, with the note telling the reader to add them by hand.

    That is a command which does not work until edited, and it was duly run once
    with kraken's default single data-loading worker — the difference between an
    evening and a week on this corpus. A reported command is for running. What must
    not be baked in is a *literal*: the values are read off the machine, so the
    template carries placeholders and the next machine gets its own answer.
    """
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    dev, wrk = zn._runtime_flags()
    assert f"-d {dev}" in rep["command"] and f"--workers {wrk}" in rep["command"]
    # Placeholders in the template, never a machine's answer written down.
    for literal in ("cuda:0", "cpu", "--workers 1", "--workers 14"):
        assert literal not in zn.SEGTRAIN_CMD
    assert wrk >= 1 and dev in ("cpu", "cuda:0")


def test_the_command_fine_tunes_blla_rather_than_starting_over(tmp_path):
    """115 pages will not teach a convolutional stack from nothing, and `new`
    is what replaces blla's `text` region and `default` baseline with these seven
    regions.

    **Not `both`**, which `--help` both lists and describes as doing exactly this:
    kraken 7.0.3 implements only `fail`, `union` and `new`, and `both` falls into
    an `else` whose ValueError crashes on a wrong attribute — so it fails after
    the data has loaded, with an AttributeError naming neither the flag nor the
    problem.
    """
    keyed(tmp_path, "1-048")
    zn.blot_all(tmp_path)
    cmd = zn.assemble(tmp_path)["command"]
    assert "-i models/blla.mlmodel" in cmd and "--resize new" in cmd


def test_assembly_reports_the_classes_the_model_will_carry(tmp_path):
    """What the output layer gets resized to. Reading it off the report beats
    reading it out of the checkpoint afterwards."""
    keyed(tmp_path, "1-048")
    keyed(tmp_path, "1-049", "exempt")
    zn.blot_all(tmp_path)
    rep = zn.assemble(tmp_path)
    assert rep["classes"] == "MainZone-P"
