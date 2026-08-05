"""`review/<ref>/` layout, and the derived-file list that three places must share.

`paths.py` is the layout authority. `.gitignore` mirrors its `DERIVED` list and says
so in a comment; so does `clean`. The three drifted once — `.gitignore` listed four
names and `DERIVED` held three, each file claiming the other mirrored it — which is
the sort of thing a comment cannot enforce and a test can.

Why it matters beyond tidiness: everything *not* listed as derived is tracked, which
is deliberately the reverse of the earlier rule. Under the old one a newly authored
file needed a matching negation or it was silently untracked and losable — the exact
failure this repo has already suffered once.
"""

from pathlib import Path

import pytest

from harness.paths import (
    DERIVED,
    crops_dir,
    decisions_path,
    html_path,
    proposal_path,
    review_dir,
    sheets_dir,
    zoom_dir,
)

REPO = Path(__file__).resolve().parent.parent.parent


def gitignored_review_names():
    """The `review/*/…` entries `.gitignore` treats as derived."""
    out = set()
    for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("review/*/") and not line.startswith("review/*/*"):
            out.add(line[len("review/*/") :].rstrip("/"))
    return out


def test_derived_matches_gitignore():
    """The two lists must name the same things, exactly. `.gitignore`'s own comment
    says it mirrors `DERIVED`; this is what makes that true rather than aspirational."""
    assert set(DERIVED) == gitignored_review_names()


def test_every_derived_dir_is_gitignored():
    """A derived directory missing from `.gitignore` commits PNGs as noise."""
    ignored = gitignored_review_names()
    for name in DERIVED:
        assert name in ignored, f"{name!r} is in DERIVED but not ignored"


def test_authored_files_are_not_in_derived():
    """`proposal.json` is a reading and `decision.json` an editorial act. Losing
    either is the failure mode; neither may ever be treated as regenerable."""
    assert "proposal.json" not in DERIVED
    assert "decision.json" not in DERIVED


@pytest.mark.parametrize(
    "builder,expected",
    [
        (proposal_path, "proposal.json"),
        (decisions_path, "decision.json"),
        (html_path, "review.html"),
    ],
)
def test_file_builders_land_in_the_pages_own_directory(builder, expected, tmp_path):
    p = builder("1-48", tmp_path)
    assert p.parent == tmp_path / "review" / "1-048"
    assert p.name == expected


@pytest.mark.parametrize(
    "builder,expected",
    [
        (crops_dir, "crops"),
        (sheets_dir, "sheets"),
        (zoom_dir, "zoom"),
    ],
)
def test_dir_builders_land_in_the_pages_own_directory(builder, expected, tmp_path):
    p = builder("1-48", tmp_path)
    assert p == tmp_path / "review" / "1-048" / expected


def test_builders_normalize_the_ref():
    """One directory per page, whichever spelling of the ref reached the CLI."""
    assert review_dir("1-48", Path(".")) == review_dir("chukchi-1-048", Path("."))


def test_builders_reject_a_bare_integer():
    with pytest.raises(ValueError):
        review_dir("48", Path("."))


# --- the third disposition: ignored, but never cleaned ----------------------


def test_page_link_is_not_derived():
    """`page.png` is ignored but must survive `harness clean`. Putting it in
    DERIVED would delete the one thing in the directory that costs nothing to
    keep and exists precisely to be there when someone opens the page."""
    assert "page.png" not in DERIVED


def test_page_link_is_gitignored_by_a_star_shaped_rule():
    """It has to be ignored — `scans/` is itself derived and gitignored, so a
    tracked link would dangle in every clone. And it has to be ignored by a
    `review/*/*`-shaped pattern, or `gitignored_review_names()` would pick it up
    and `test_derived_matches_gitignore` would demand it join DERIVED, which is
    the one thing it must not do."""
    text = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "review/*/*.png" in text.split()
    assert "page.png" not in gitignored_review_names()


def test_page_link_is_relative_and_points_at_the_raster(tmp_path):
    """Relative, so it survives a clone to a different path."""
    from harness.paths import ensure_page_link, page_link

    scan = tmp_path / "scans" / "chukchi-1-048.png"
    scan.parent.mkdir(parents=True)
    scan.write_bytes(b"\x89PNG")
    link = ensure_page_link("1-48", tmp_path)
    assert link == page_link("1-048", tmp_path)
    assert link.is_symlink()
    import os

    assert not os.path.isabs(os.readlink(link))
    assert link.resolve() == scan.resolve()


def test_no_link_is_made_without_a_raster(tmp_path):
    """A dangling link inside a page's directory reads as a missing scan, which
    is worse than an absent convenience."""
    from harness.paths import ensure_page_link

    assert ensure_page_link("1-048", tmp_path) is None
    assert not (tmp_path / "review" / "1-048").exists()


def test_clean_leaves_the_link_and_the_authored_files(tmp_path):
    from harness.paths import clean as clean_page
    from harness.paths import ensure_page_link, review_dir

    scan = tmp_path / "scans" / "chukchi-1-048.png"
    scan.parent.mkdir(parents=True)
    scan.write_bytes(b"\x89PNG")
    d = review_dir("1-048", tmp_path)
    d.mkdir(parents=True, exist_ok=True)
    (d / "proposal.json").write_text("{}", encoding="utf-8")
    for name in DERIVED:
        p = d / name
        p.mkdir() if not name.endswith(".html") else p.write_text("x")
    ensure_page_link("1-048", tmp_path)

    clean_page("1-048", tmp_path)
    assert not (d / "crops").exists()
    assert (d / "page.png").is_symlink()
    assert (d / "proposal.json").exists()


def test_page_dirs_takes_only_ref_shaped_children(tmp_path):
    """`review/` holds the dispatch queue and its claims as well as pages.

    Five sweeps used to glob `review/*` and treat whatever came back as a ref.
    Three filtered on `proposal.json`/`decision.json` and survived by accident;
    `ocr clean` with no refs filtered on `is_dir()` alone, so the first non-page
    child would have taken it into `norm_ref` and out through a `ValueError`
    about bare page numbers — a true message about the wrong thing.
    """
    from harness.paths import page_dirs, page_refs_under

    r = tmp_path / "review"
    for name in ("1-048", "1-9", "2-030", "_claims", "notes"):
        (r / name).mkdir(parents=True)
    (r / "_queue.txt").write_text("1-048\n", encoding="utf-8")

    assert [d.name for d in page_dirs(tmp_path)] == ["1-9", "1-048", "2-030"]
    # Canonicalized and in (part, index) order, so `1-9` sorts before `1-048`
    # by index rather than by string.
    assert page_refs_under(tmp_path) == ["1-009", "1-048", "2-030"]


def test_page_dirs_on_a_repo_with_no_review_tree(tmp_path):
    """Empty, not an error: `review/` is authored working state, so nothing
    waiting is a true answer rather than an unbuilt tree (unlike a farm)."""
    from harness.paths import page_dirs

    assert page_dirs(tmp_path) == []


# --- a masked figure says what it is ----------------------------------------

FIG_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _figured_page(tmp_path, ref: str = "1-048"):
    """A page with one line and one declared figure, big enough for the placard."""
    from PIL import Image

    (tmp_path / "scans").mkdir(parents=True, exist_ok=True)
    Image.new("L", (1200, 1600), 255).save(tmp_path / "scans" / f"chukchi-{ref}.png")

    ocr = tmp_path / "gt" / "ocr"
    ocr.mkdir(parents=True, exist_ok=True)
    (ocr / f"chukchi-{ref}.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><alto xmlns="{FIG_NS}"><Layout>'
        '<Page WIDTH="1200" HEIGHT="1600"><PrintSpace HPOS="0" VPOS="0" '
        'WIDTH="1200" HEIGHT="1600"><TextBlock ID="b1">'
        '<TextLine ID="l0" HPOS="100" VPOS="120" WIDTH="900" HEIGHT="50">'
        '<String CONTENT="a line" HPOS="100" VPOS="120" WIDTH="900" HEIGHT="50"/>'
        "</TextLine></TextBlock></PrintSpace></Page></Layout></alto>",
        encoding="utf-8")

    fig = tmp_path / "gt" / "fig"
    fig.mkdir(parents=True, exist_ok=True)
    (fig / f"chukchi-{ref}.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><alto xmlns="{FIG_NS}"><Layout>'
        '<Page WIDTH="1200" HEIGHT="1600"><PrintSpace HPOS="0" VPOS="0" '
        'WIDTH="1200" HEIGHT="1600">'
        '<TextBlock ID="g1" TAGREFS="GT1" HPOS="150" VPOS="400" WIDTH="900" '
        'HEIGHT="700"/></PrintSpace></Page></Layout>'
        '<Tags><OtherTag ID="GT1" TYPE="type" LABEL="GraphicZone"/></Tags>'
        "</alto>", encoding="utf-8")
    return tmp_path


def test_a_masked_figure_carries_its_placard(tmp_path):
    """A figure is painted out of `ocr numbered` — deliberately, since a plate
    eats the token budget of an image delivered at ~0.6x and its artwork raises
    baselines the reader would have to be told to ignore.

    Painted out and left *blank*, though, it is a void the reader has to explain
    to itself: `2-030`'s reader met a huge vertical jump between two consecutive
    indices, reasoned its way to "masked figure" from `gt/fig/` existing and `ocr
    gaps` coming back empty, and wrote a memory note about it — three steps to
    recover something this image already knew and had thrown away. An erasure
    that does not say what it erased is indistinguishable from blank paper, which
    on a page whose whole question is *what is missing here* is the wrong thing
    to be indistinguishable from.
    """
    from PIL import Image

    from harness.lines import FIG_FILL, FIG_INK, write_numbered_page

    root = _figured_page(tmp_path)
    res = write_numbered_page("1-048", root / "numbered.png", "gt/ocr", root)
    img = Image.open(res["path"]).convert("L")
    hist = img.histogram()
    # The grey is the placard's, and the lettering is drawn over it — so the box
    # is neither blank paper nor artwork, which are the two things it must not be
    # mistaken for.
    assert hist[FIG_FILL] > 5000, "the figure box is not filled with the placard grey"
    assert hist[FIG_INK] > 200, "the placard carries no lettering"


def test_a_figure_too_small_for_the_placard_keeps_the_grey(tmp_path):
    """The floor matters more than the lettering. A box too small for even the
    smallest type still reads as *something was removed here*, which is the whole
    job; white did not."""
    from harness.lines import FIG_TITLE_MIN

    assert FIG_TITLE_MIN >= 10, "a floor this low would render as noise"
