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

from harness.paths import (DERIVED, crops_dir, decisions_path, html_path,
                           proposal_path, review_dir, sheets_dir, zoom_dir)

REPO = Path(__file__).resolve().parent.parent


def gitignored_review_names():
    """The `review/*/…` entries `.gitignore` treats as derived."""
    out = set()
    for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("review/*/") and not line.startswith("review/*/*"):
            out.add(line[len("review/*/"):].rstrip("/"))
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


@pytest.mark.parametrize("builder,expected", [
    (proposal_path, "proposal.json"),
    (decisions_path, "decision.json"),
    (html_path, "review.html"),
])
def test_file_builders_land_in_the_pages_own_directory(builder, expected, tmp_path):
    p = builder("1-48", tmp_path)
    assert p.parent == tmp_path / "review" / "1-048"
    assert p.name == expected


@pytest.mark.parametrize("builder,expected", [
    (crops_dir, "crops"),
    (sheets_dir, "sheets"),
    (zoom_dir, "zoom"),
])
def test_dir_builders_land_in_the_pages_own_directory(builder, expected, tmp_path):
    p = builder("1-48", tmp_path)
    assert p == tmp_path / "review" / "1-048" / expected


def test_builders_normalize_the_ref():
    """One directory per page, whichever spelling of the ref reached the CLI."""
    assert review_dir("1-48", Path(".")) == review_dir("chukchi-1-048", Path("."))


def test_builders_reject_a_bare_integer():
    with pytest.raises(ValueError):
        review_dir("48", Path("."))
