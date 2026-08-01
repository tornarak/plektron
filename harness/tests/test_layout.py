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
    from harness.paths import clean as clean_page, ensure_page_link, review_dir

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
