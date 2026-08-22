"""Which pages exist, and where the rebuild pass keeps a page's working set.

**Two jobs, and the first arrived when `context.py` was split.** Finding pages —
`all_refs`, `all_scans`, `with_context` and the `_refs_under` walk beneath them —
needs to know the stores and nothing else, and it had been sitting in the module
that assembles a whole collation prompt. It belongs with the layout authority
because that is what it is: a question about what is on disk.

Not in `refs.py` with the ref primitives, for a reason worth stating since the
choice looks arbitrary: `refs.py` is a **leaf** and must stay one, while this
walk needs `farms.require` to tell an unbuilt derived tree from an empty store —
the one place in the harness that distinguishes absent from empty. Putting it in
the leaf would either drag `farms` in behind it or lose that distinction. Here it
costs nothing: this module already imported `farms` for `SCANS`, and `farms` does
not import this one back (`farms.py:417` says why it globs directly rather than
calling `all_scans`), so the pair stays acyclic.

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

import bisect
from pathlib import Path

from . import farms
from .farms import SCANS
from .refs import norm_ref, parse_context, parse_ref


def _refs_under(root: Path, pattern: str) -> list[str]:
    """Every ref matching `pattern`, in (part, scan index) order.

    **Refuses when the directory is a derived tree that was never built**, and this
    is the one place in the harness that distinguishes absent from empty.
    `Path.glob()` on a missing directory returns empty *silently*, so a fresh clone
    used to run `harness ocr pages`, walk an `ocr/` nobody had built, and report zero
    workable pages with exit 0. Blank was indistinguishable from clean — the same
    fault the zone store's `exempt` mark exists to separate.

    **The refusal is scoped by the registry, not by this function**, and the line is
    stores. A missing `mz/ocr/` means nothing has been predicted: a true statement
    about the corpus, and the ordinary state of a clone. A missing `ocr/` means
    nobody built the view: a statement about this working copy. `farms.require`
    raises only for a registered farm path, so `--store mz` over an empty machine
    store still answers "none" — which is the answer — while the view says it was
    never built. See `harness/farms.py` on where that line falls.
    """
    d, _, _ = pattern.rpartition("/")
    if d:
        farms.require(root, d)
    refs = []
    for p in root.glob(pattern):
        try:
            refs.append(norm_ref(p.stem))
        except ValueError:
            continue
    return sorted(set(refs), key=parse_ref)


def all_refs(root: Path = Path("."), alto_dir: str = "ocr") -> list[str]:
    """Every ref with OCR present in `alto_dir` — i.e. workable now.

    The default is the **view**, so this answers "what can be collated", which is
    the question the collation loop asks and which `mz/ocr/` legitimately widens:
    a machine-read page is workable. It was sparse by construction while `gt/ocr/`
    was the only store under the view, and it is not any more.

    Name a real store to ask a narrower question — `gt/ocr/` for "what has a human
    been through", `mz/ocr/` for "what has the recognizer read". **Anything
    computing a published number must do that**, since a figure blended across
    ranks describes neither.
    """
    return _refs_under(root, f"{alto_dir}/chukchi-*.xml")


def all_scans(root: Path = Path(".")) -> list[str]:
    """Every ref that physically exists, in (part, scan index) order.

    This, not `all_refs`, is the sequence folio prediction walks. The OCR set is
    sparse — a pilot selection scattered through the volume — so stepping
    through it would happily predict folio+1 across a four-scan gap. Physical
    adjacency is the only thing that licenses the prediction.
    """
    return _refs_under(root, "scans/chukchi-*.png")


def with_context(refs: list[str], spec: str,
                 root: Path = Path(".")) -> list[str]:
    """`refs` plus their neighbours by scan index, deduplicated and in page order.

    **Neighbours are drawn from `scans/`, never derived by arithmetic.** A ref
    `PP-NNN` sits in a part whose length this function has no business knowing,
    and a window that ran off the end would invent refs no page answers to — so
    the window is applied to the *observed* index list for that part, which also
    means a gap in the scans (an unnumbered plate pulled from the sequence) is
    stepped over rather than silently counted as a page.

    Parts do not run into each other: a window at the head of part 2 does not
    reach back into part 1, because `1-362` and `2-001` are neighbours in the
    binding and nothing else, and a context that crossed there would be asserting
    a continuity the scan index does not carry.
    """
    behind, ahead = parse_context(spec)
    if not (behind or ahead):
        return [norm_ref(r) for r in refs]
    by_part: dict[int, list[int]] = {}
    for r in all_scans(root):
        p, i = parse_ref(r)
        by_part.setdefault(p, []).append(i)
    for idxs in by_part.values():
        idxs.sort()
    out: set[str] = set()
    for r in refs:
        part, idx = parse_ref(r)
        seq = by_part.get(part, [])
        at = bisect.bisect_left(seq, idx)
        lo = max(0, at - behind)
        hi = min(len(seq), at + ahead + 1)
        out.add(norm_ref(r))
        out.update(f"{part}-{i:03d}" for i in seq[lo:hi])
    return sorted(out, key=parse_ref)


def scan_for(ref: str, root: Path = Path(".")) -> Path:
    """The 300 dpi master for one page.

    Here rather than in `zones.py` and again in `edition_ui.py`, which is where
    it was — byte-identical bodies, except that `edition_ui`'s spelled the
    directory as the literal `"scans"` while `zones`' used the constant, so the
    two would have parted company the day the farm moved. `farms.SCANS` is the
    one name for it, and `farms` imports nothing from this package but `refs`,
    which is a leaf — so this cannot become a cycle. The qualifier used to be
    "at module level", because `farms` reached back into `context` from a
    function body for the ref primitives; moving those to `refs.py` is what
    retired the qualifier.
    """
    return root / SCANS / f"chukchi-{norm_ref(ref)}.png"

# Everything under `review/<ref>/` that any verb may recreate from the ALTO and the
# rasters. The gitignore rules mirror this; so does `clean` below. `harness/tests/test_layout.py`
# holds the two to each other, because they drifted while each file's comment claimed
# the other mirrored it — `.gitignore` listed `review.html` and this tuple did not, so
# `clean` left a stale page behind on every finished ref.
#
# `review.html` is a file where the rest are directories; `clean` handles both.
DERIVED = ("crops", "sheets", "zoom", "review.html", "numbered.png")


def review_dir(ref: str, root: Path = Path(".")) -> Path:
    return root / "review" / norm_ref(ref)


def page_dirs(root: Path = Path(".")) -> list[Path]:
    """Every child of `review/` that is a page, in (part, scan index) order.

    **`review/` is not all pages.** Five call sites used to glob `review/*` and treat
    whatever came back as a ref, which held only for as long as nothing else lived
    there. It does now: the dispatch queue and its claim markers are the batch's
    working state and belong beside the pages they deal out, so `_queue.txt` and
    `_claims/` sit here too. Three of those sites survived contact by accident,
    filtering on `proposal.json` or `decision.json` existence; `ocr clean` with no
    refs filtered on `is_dir()` alone and would have handed `_claims` to `norm_ref`,
    where a `ValueError` about bare page numbers is a confusing way to be told the
    verb walked into the wrong directory.

    The underscore is not what excludes them — **being ref-shaped is what includes
    a directory**, so anything else that ever lands in `review/` is out by
    construction rather than by having been anticipated. The name is the whole test,
    exactly as `parse_ref` intends it: a directory is a page because it is called
    one, and nothing infers a page from what it happens to contain.
    """
    out = []
    for d in (root / "review").glob("*"):
        if not d.is_dir():
            continue
        try:
            out.append((parse_ref(d.name), d))
        except ValueError:
            continue
    return [d for _, d in sorted(out)]


def page_refs_under(root: Path = Path(".")) -> list[str]:
    """`page_dirs` as canonical refs — what most callers actually want."""
    return [norm_ref(d.name) for d in page_dirs(root)]


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


def numbered_path(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "numbered.png"


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
