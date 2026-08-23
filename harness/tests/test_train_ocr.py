"""The recognizer's training set: what goes into it, and what says so.

Four things here would be invisible if they broke, and each is the inverse of a
decision one of the two segmentation tracks made.

**The split unit is the page.** kraken's `-p/--partition` divides the pooled
*line* set and every recipe online uses it. Lines off one leaf share its ink
weight, its wear and its bleed-through, so a line-level split measures
memorising a page rather than reading a new one — and measures it *high*, which
is the direction nobody goes looking. Nothing downstream would disagree with the
resulting number.

**The raster is the blot**, where `figures.assemble` links the raw scan. One
rule — a model is trained on the raster it will be asked to read — and `ocr
predict` reads `scans/w-figs-blotted/`. A copy-paste from the figure track is
exactly how this goes wrong, so it is asserted rather than commented.

**An unmarked page is in neither list.** Both segmentation tracks default an
unmarked ref to `train` harmlessly; here it would quietly enlarge the training
set between a `remark-eval` and a run, so a before/after would compare two
numbers taken over different sets.

**A `gt/lines/` correction cannot be compiled from the ALTO.** `page_lines`
appends it at read time, so every other consumer in the harness sees it and
`ketos compile -f alto` does not. This is the one place where the merged view
would overstate a set, by exactly the lines a human went out of their way to add.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_scan

from harness import recognize as R
from harness import zones as zn

ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Description><sourceImageInformation><fileName>chukchi-{ref}.png</fileName>
  </sourceImageInformation></Description>
  <Layout><Page ID="p" WIDTH="600" HEIGHT="800"><PrintSpace
    HPOS="0" VPOS="0" WIDTH="600" HEIGHT="800">
    <TextBlock ID="b1" HPOS="50" VPOS="100" WIDTH="500" HEIGHT="200">{lines}
    </TextBlock>
  </PrintSpace></Page></Layout>
</alto>
"""
LINE = """
      <TextLine ID="l{n}" HPOS="50" VPOS="{y}" WIDTH="500" HEIGHT="40"
                BASELINE="50 {b} 550 {b}">
        <Shape><Polygon POINTS="50 {y} 550 {y} 550 {b} 50 {b}"/></Shape>
        <String CONTENT="{text}"/>
      </TextLine>"""


def write_page(root: Path, ref: str, texts: list[str],
               store: str = R.GTDIR) -> Path:
    """One page in `gt/ocr/`, with a raster and a blot beside it."""
    lines = "".join(
        LINE.format(n=i, y=100 + i * 50, b=140 + i * 50, text=t)
        for i, t in enumerate(texts, 1))
    p = root / store / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(ALTO.format(ref=ref, lines=lines), encoding="utf-8")
    write_scan(root, ref, size=(600, 800))
    blot = zn.blot_dir(root) / f"chukchi-{ref}.png"
    blot.parent.mkdir(parents=True, exist_ok=True)
    if not blot.exists():
        blot.symlink_to((root / "scans" / f"chukchi-{ref}.png").resolve())
    return p


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for ref in ("1-021", "1-031", "2-014", "2-020", "3-009"):
        write_page(tmp_path, ref, ["one line", "and another"])
    return tmp_path


# --------------------------------------------------------------- the split


def test_every_keyed_page_is_marked_and_the_holdout_is_whole_pages(root):
    R.remark_eval(root, 0.40, commit=True)
    marks = R.rec_splits(root)
    assert len(marks) == 5
    assert set(marks.values()) <= {"train", "eval"}


def test_the_split_is_stratified_per_part(root):
    """A part is a physically separate volume with its own press run. An eval set
    drawn from the corpus as one pool can miss a whole part, and the model would
    then be scored on typography it had trained on exclusively."""
    R.remark_eval(root, 0.50, commit=True)
    marks = R.rec_splits(root)
    held = {r.split("-")[0] for r, s in marks.items() if s == "eval"}
    assert held == {"1", "2"}, "one of each two-page part, none from the singleton"


def test_a_mark_already_made_is_never_moved(root):
    """Held out has to stay held out, or the eval set drifts with whatever was
    keyed most recently and stops being a held-out set at all."""
    from harness.figures import set_split
    set_split("1-021", "eval", root, R.SPLIT_STORE)
    R.remark_eval(root, 1.0, commit=True)
    assert R.rec_splits(root)["1-021"] == "eval"
    rep = R.remark_eval(root, 1.0, commit=True)
    assert rep["newly_marked"] == 0 and rep["already_marked"] == 5


def test_preview_writes_nothing(root):
    rep = R.remark_eval(root, 0.40)
    assert rep["committed"] is False
    assert R.rec_splits(root) == {}


# ------------------------------------------------------------ the layout


def test_the_raster_is_the_blot_not_the_raw_scan(root):
    """The link a copy-paste from `train assemble fig` would get wrong. `ocr predict`
    reads the blot, so a model trained on the raw page meets, at inference, a
    version of every figure-adjacent line it has never seen."""
    R.remark_eval(root, 0.0, commit=True)
    blot = zn.blot_dir(root) / "chukchi-1-021.png"
    blot.unlink()
    blot.write_bytes(b"a distinct blot")
    R.assemble(root)
    link = root / R.DATADIR / "chukchi-1-021.png"
    assert link.resolve() == blot.resolve()
    assert link.resolve() != (root / "scans/chukchi-1-021.png").resolve()


def test_a_page_with_no_blot_is_refused_not_substituted(root):
    R.remark_eval(root, 0.0, commit=True)
    (zn.blot_dir(root) / "chukchi-2-014.png").unlink()
    rep = R.assemble(root)
    assert rep["missing_blot"] == "2-014"
    assert not (root / R.DATADIR / "chukchi-2-014.xml").exists()


def test_an_unmarked_page_is_in_neither_list(root):
    """Never defaulted into train — see the module docstring."""
    from harness.figures import set_split
    for ref in ("1-021", "1-031"):
        set_split(ref, "train", root, R.SPLIT_STORE)
    rep = R.assemble(root)
    assert rep["train_pages"] == 2 and rep["eval_pages"] == 0
    assert set(rep["unmarked"].split()) == {"2-014", "2-020", "3-009"}


def test_the_lists_are_relative_and_unresolved(root):
    """Resolving follows the symlink back into `gt/ocr/` and compiles the store
    instead of the work directory — `zones.assemble`'s recorded lesson."""
    R.remark_eval(root, 0.0, commit=True)
    R.assemble(root)
    listed = (root / R.DATADIR / "train.lst").read_text().split()
    assert listed and all(p.startswith(R.DATADIR) for p in listed)
    assert not any(R.GTDIR in p for p in listed)


def test_the_alto_is_linked_from_the_ground_truth_store(root):
    R.remark_eval(root, 0.0, commit=True)
    R.assemble(root)
    link = root / R.DATADIR / "chukchi-1-021.xml"
    assert link.is_symlink()
    assert link.resolve() == R.alto_for("1-021", root, R.GTDIR).resolve()


def test_the_eval_manifest_names_the_dataset_and_not_the_pages(root):
    """`-e` is a manifest, not a dataset: kraken opens the named file and reads
    paths out of it. The training set goes in as the positional argument and
    needs no such wrapper, which is why only one of these exists."""
    R.remark_eval(root, 1.0, commit=True)
    R.assemble(root)
    mft = (root / R.DATADIR / "eval.mft").read_text().split()
    assert mft == [f"{R.DATADIR}/eval.arrow"]


def test_assemble_clears_a_previous_layout(root):
    R.remark_eval(root, 0.0, commit=True)
    R.assemble(root)
    stale = root / R.DATADIR / "chukchi-9-999.xml"
    stale.write_text("stale")
    R.assemble(root)
    assert not stale.exists()


# ------------------------------------------------- what the counts mean


def test_empty_lines_are_not_counted_because_ketos_skips_them(root):
    write_page(root, "1-050", ["text here", "", "  "])
    R.remark_eval(root, 0.0, commit=True)
    rep = R.assemble(root)
    assert rep["train_lines"] == 5 * 2 + 1


def test_a_correction_is_counted_apart_and_does_not_train(root):
    """It lives in `gt/lines/`, not in the ALTO, so `ketos compile -f alto`
    cannot see it. Folding it into the total would overstate the training set by
    exactly the lines a human went out of their way to add."""
    from harness import corrections as corr
    corr.save_lines("1-021", [{"x0": 50, "y0": 400, "x1": 550, "y1": 430}], root)
    R.remark_eval(root, 0.0, commit=True)
    before = R.assemble(root)["train_lines"]
    # A correction only carries text once `restore` has written one into it; an
    # empty box is skipped as an empty line is, by the same test.
    lines = corr.load_lines("1-021", root)
    lines[0]["text"] = "a line the segmenter dropped"
    corr.save_lines("1-021", lines, root)
    rep = R.assemble(root)
    assert rep["corrections_excluded"] == 1
    assert rep["train_lines"] == before


# ------------------------------------------------- the reported commands


def _cmds(root) -> str:
    R.remark_eval(root, 0.20, commit=True)
    return "\n".join(R.assemble(root)["commands"])


def test_normalization_is_named_and_is_never_a_compatibility_form(root):
    """CLAUDE.md: any normalization must name its form, somebody else's tool
    included. NFKC/NFKD have compatibility decompositions for two inventory
    glyphs and destroy them — `ᵋ` U+1D4B and `˙` U+02D9."""
    cmds = _cmds(root)
    assert "-u NFD" in cmds
    assert "NFKC" not in cmds and "NFKD" not in cmds


def test_the_split_is_passed_explicitly_which_is_what_disables_partition(root):
    """kraken sets `partition` to 1 when an evaluation set is named. Without
    `-e` it would divide the pooled *line* set — the one mistake that would
    invalidate every number this track produces."""
    cmds = _cmds(root)
    assert f"-e {R.DATADIR}/eval.mft" in cmds
    assert "--partition" not in cmds and " -p " not in cmds


def test_resize_uses_only_a_value_kraken_implements(root):
    """`kraken/train/vgsl.py` implements `fail`, `union` and `new`. The help
    advertises `add` and `both`, and `recognition.py`'s own mismatch error
    suggests `add`; both fall into an else that raises. Same trap
    `zones.assemble` records for segtrain, in a second command."""
    cmds = _cmds(root)
    for value in ("--resize add", "--resize both"):
        assert value not in cmds
    if "--resize" in cmds:
        assert "--resize union" in cmds


def test_the_baseline_is_reported_beside_the_finetune(root):
    """A CER for a new model is not a result on its own — it is a result against
    what the corpus is read with today, over the same manifest by the same
    command. Two numbers made the same way, or neither means anything."""
    cmds = [c for c in R.assemble(root)["commands"] if " test " in c]
    assert len(cmds) == 2
    assert any(R.DEFAULT_REC_MODEL in c for c in cmds)
    assert any(R.RUNDIR in c for c in cmds)
    # A glob, because `ketos train` names its output `best_{score}.safetensors`
    # and the score is not knowable until the run ends. The per-run directory is
    # what keeps the glob unambiguous.
    assert any("best_*.safetensors" in c for c in cmds)
    # Same eval set, same flags, one model apart: hold the method constant.
    a, b = (c.replace(R.DEFAULT_REC_MODEL, "M") for c in cmds)
    import re
    assert re.sub(r"-m \S+", "-m M", a) == re.sub(r"-m \S+", "-m M", b)


def test_scratch_names_itself_rather_than_arriving_by_a_missing_file(root):
    """Fine-tuning and random init are different experiments, and the one that
    arrives by way of an absent model is the one nobody chose."""
    rep = R.assemble(root, scratch=True)
    assert "scratch" in rep["base"]
    assert " -i " not in "\n".join(rep["commands"])
    plain = R.assemble(root)
    assert "scratch" in plain["base"] and "no base model found" in plain["base"]


def test_the_run_directory_is_made_so_the_reported_command_runs_as_printed(root):
    """kraken creates the output directory it is given, but not its parents."""
    R.assemble(root)
    assert (root / R.RUNDIR).is_dir()
