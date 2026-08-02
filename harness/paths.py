"""Where the ground-truth rebuild pass keeps a page's working set.

One directory per page — `review/<ref>/` — holding both what was authored and what
was generated:

    review/1-074/proposal.json     a reading. Authored. Never truth.
    review/1-074/decision.json     the adjudication. Authored.
    review/1-074/decision.jsonl    the append-only save journal.
    review/1-074/page.png          symlink to the raster. Ignored, never cleaned.
    review/1-074/sheets/           labelled contact sheets. Derived.
    review/1-074/crops/            one PNG per line. Derived.
    review/1-074/zoom/             magnified strips. Derived.

The earlier layout was parallel by kind — `review/proposals/<ref>.json` against
`review/crops/<ref>/…` — which had two costs. Every verb in the loop had to be told
where to put its images (`--sheets DIR`, `--out DIR`), because there was no directory
that was *the page's*; and finishing with a page meant deleting from three trees or
from none, so nothing was ever deleted. Per-ref, the ephemera are one `harness ocr clean <ref>` away (see `clean` below),
and the flags are overrides rather than ceremony.

What the split did buy was a trivially legible gitignore: two whole directories
tracked, three ignored. That is now a per-name matter, and `DERIVED` below is the
list the ignore rules and `clean()` both read off — keep the two in step.

Three dispositions, not two, and `DERIVED` is only one of them: **tracked** (the
authored files), **derived** (ignored, and removed by `clean`), and **ignored but
kept** — `*.prev`/`*.tmp`/`*.jsonl`, which are recovery data for before a commit
exists, and `page.png`, which is a convenience symlink into an already-ignored
tree. `.gitignore` spells the third group with `review/*/*`-shaped patterns, which
is exactly what keeps `harness/tests/test_layout.py`'s `DERIVED == gitignored` invariant
true over a set that is deliberately not all of what is ignored.

The distinction the old layout carried in its directory names — proposal is not
ground truth — is carried by the filenames instead, and it has to be carried
*somewhere*: 18 pages of real ground truth were lost precisely because a file's role
lived only in the directory holding it. Note that nothing here writes into `gt/`.
`restore` does, once, from `decision.json`.
"""

from pathlib import Path

from .context import norm_ref

# Everything under `review/<ref>/` that any verb may recreate from the ALTO and the
# rasters. The gitignore rules mirror this; so does `clean` below. `harness/tests/test_layout.py`
# holds the two to each other, because they drifted while each file's comment claimed
# the other mirrored it — `.gitignore` listed `review.html` and this tuple did not, so
# `clean` left a stale page behind on every finished ref.
#
# `review.html` is a file where the rest are directories; `clean` handles both.
DERIVED = ("crops", "sheets", "zoom", "review.html")


def review_dir(ref: str, root: Path = Path(".")) -> Path:
    return root / "review" / norm_ref(ref)


def proposal_path(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "proposal.json"


def decisions_path(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "decision.json"


def crops_dir(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "crops"


def sheets_dir(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "sheets"


def zoom_dir(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "zoom"


def html_path(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "review.html"


def page_link(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "page.png"


def ensure_page_link(ref: str, root: Path = Path(".")) -> Path | None:
    """Symlink the page's raster into its own review directory, for a human.

    Third category, alongside `*.prev` / `*.tmp` / `*.jsonl`: **ignored but not
    derived.** Not in `DERIVED`, so `harness ocr clean` leaves it when the images
    go — it costs nothing to keep and the point of it is to be there whenever
    someone opens the directory. Not tracked either, and that one is not a
    preference: `scans/` is itself derived and gitignored, so a committed link
    would dangle in every clone — the same reason `scans/w-figs/` is ignored
    (CLAUDE.md, "Where things stand").

    The link is **relative**, so it survives the repo being moved or cloned to
    a different path, and it is only created when the target actually exists —
    a dangling link inside a page's working directory would read as a missing
    scan rather than as an absent convenience.

    Returns the link path, or None if there was no raster to point at.
    """
    d = review_dir(ref, root)
    target = root / "scans" / f"chukchi-{norm_ref(ref)}.png"
    if not target.exists():
        return None
    link = page_link(ref, root)
    if link.is_symlink() or link.exists():
        return link
    d.mkdir(parents=True, exist_ok=True)
    # Relative to the link's own directory, not to `root` — `os.path.relpath`
    # against the parent is what makes `review/1-048/page.png` resolve through
    # `../../scans/`, which is the form that survives a clone.
    import os
    link.symlink_to(os.path.relpath(target.resolve(), link.parent.resolve()))
    return link


def clean(ref: str, root: Path = Path(".")) -> dict:
    """Remove a page's derived working images, leaving the two authored files
    (`proposal.json`, `decision.json`) untouched.

    Reads `DERIVED` rather than naming the entries again, so a further derived
    name only ever needs adding in one place.
    """
    import shutil
    d = review_dir(ref, root)
    removed = []
    for name in DERIVED:
        p = d / name
        if not p.exists():
            continue
        # `review.html` is a file; the rest are directories. Branch on what is
        # actually there rather than on the name, so adding either kind to
        # DERIVED needs no change here.
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        removed.append(name)
    return {"ref": norm_ref(ref), "removed": removed}
