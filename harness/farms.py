"""The derived trees: what they are, what builds them, and the linking they share.

Six directories in this repo are **derived** — git does not carry them, and a fresh
clone has none of them. Until now nothing knew they were a class. Their path
constants sat in four modules under three spellings, the relative-symlink idiom was
copied out five times, and two of them (`scans/w-figs/`, `scans/w-ocr/`) had no
builder at all: they were made by hand, and had drifted, which is exactly what a
directory nobody can regenerate does.

This module is the declaration. `FARMS` names each tree once; `relink`/`rebuild` are
the mechanics every builder shares; `survey` is what `harness views check` prints.

**The registry is also the scope of the absence rule**, and that is its second job.
`Path.glob()` on a missing directory returns empty *silently*, so before this module
existed a fresh clone ran `harness ocr pages`, walked an `ocr/` that was never built,
and reported zero workable pages with exit 0. An absent tree and an empty one were
indistinguishable — the same fault as an unkeyed page against a keyed-but-empty one,
which `gt/zones`' `exempt` mark exists to separate.

**But the rule reaches farms and stops there, and the line is stores.** A missing
`mz/ocr/` means nothing has been predicted, which is a true statement about the
corpus and the ordinary state of a clone; a missing `ocr/` means nobody has built the
view, which is a statement about this working copy. The first is a record that is
empty, the second is a question that was never asked. So `context._refs_under` asks
this module whether the directory it could not find is a registered farm, and refuses
only then — `gt/ocr`, `mz/zones` and any `--from` path stay a silent empty, which is
what they have always been and what they should be.

Nothing here imports `zones` or `recognize`: the builders are looked up lazily inside
`build`, the idiom `zones.blot_one` already uses for `write_fig_blot`. That keeps the
import graph one-directional (`recognize` -> `zones` -> `context`) with this module
underneath all of it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# The one declaration of every derived path. `zones.py` and `recognize.py` alias
# these rather than being rewritten around them — 68 call sites spell `VIEWDIR`,
# and note that name means `"zones"` in one module and `"ocr"` in the other, so
# there is no single constant to hoist. What is hoisted is the *value*.
SCANS = "scans"
OCR_VIEW = "ocr"
ZONES_VIEW = "zones"
FIGS_BLOT = "scans/w-figs-blotted"
LINE_BLOT = "scans/w-blotted"
W_FIGS = "scans/w-figs"
W_OCR = "scans/w-ocr"
TRAIN_WORK = "train/bogoras-seg"


@dataclass(frozen=True)
class Farm:
    """One derived tree.

    `kind` is not decoration — it decides what `check` may honestly assert:

        view     a symlink farm over two stores, the human file winning. Membership
                 is decided by the stores, so it is exactly checkable.
        select   a symlink farm over one tree, membership from a criterion. Also
                 exactly checkable.
        raster   painted pixels. Membership is checkable; **freshness is not** —
                 see `verified` below.
        source   no builder in this repo at all.
        scratch  reported, never rebuilt here.

    `verified` is the honesty column. `zones.blot_all`'s docstring refuses an mtime
    freshness test as unsound: a figure ALTO corrected after the blot was written
    leaves a raster that still shows the figure, and the check would report success
    over it. So for `scans/w-figs-blotted/` membership is knowable and content is
    not, and the row must say `membership` rather than let `state: ok` imply more
    than was tested — the same reason `gt/zones/_ink_cache.json` reports `?` instead
    of blank.

    `reads` is what the *builder* must open, as against what its links merely point
    at, and the two differ in the case that matters. The blot builder reads pixels
    out of `scans/`, so with no `scans/` it cannot run. `w-figs`/`w-ocr` only need
    their membership sources (`gt/fig/`, `gt/ocr/`, both tracked); an absent `scans/`
    leaves their raster links dangling, which is this repo's stated disposition for a
    link into an ignored tree — it "dangles loudly, which is the right failure for a
    derived tree".
    """

    name: str
    path: str
    kind: str
    reads: tuple[str, ...]
    builder: str
    verified: str


FARMS = (
    Farm("ocr", OCR_VIEW, "view", ("gt/ocr", "mz/ocr"),
         "harness views build --only ocr", "membership"),
    Farm("zones", ZONES_VIEW, "view", ("gt/zones", "mz/zones"),
         "harness views build --only zones", "membership"),
    Farm("w-figs-blotted", FIGS_BLOT, "raster", (SCANS, "gt/fig"),
         "harness views build --only w-figs-blotted", "membership"),
    Farm("w-figs", W_FIGS, "select", ("gt/fig",),
         "harness views build --only w-figs", "membership"),
    Farm("w-ocr", W_OCR, "select", ("gt/ocr",),
         "harness views build --only w-ocr", "membership"),
    # Reported, never built here. `scans/` has no builder in this repo — it is
    # `pdftoppm` over `pdfs/`, whose three entries are symlinks pointing outside the
    # repo, so on a clone the rasters cannot be regenerated at all. `train/` is
    # scratch that `zones assemble` clobbers by design; rebuilding it out of band
    # would be preparing a training run nobody asked for.
    Farm("scans", SCANS, "source", (),
         "pdftoppm -r 300 over pdfs/ (see harness/README.md)", "none"),
    Farm("train", TRAIN_WORK, "scratch", (),
         "harness zones assemble", "none"),
)

BY_NAME = {f.name: f for f in FARMS}
BY_PATH = {f.path: f for f in FARMS}

#: The farms `views build` will actually rebuild, in dependency order. `w-ocr`
#: links into the `ocr/` view, so it must follow it.
BUILDABLE = tuple(f.name for f in FARMS if f.kind in ("view", "select", "raster"))


def farm_for(dirpath: str | Path) -> Farm | None:
    """The farm a directory *is*, or None. Matches the path exactly, never a parent.

    Exactness is the whole point: `scans/` and `scans/w-figs/` are both registered
    and are different farms, and `gt/ocr/` is inside no farm at all. A prefix match
    would fold a store into a farm and hand `require` the store-absence case it must
    not touch.
    """
    return BY_PATH.get(str(dirpath).strip("/"))


def require(root: Path, dirpath: str | Path) -> Path:
    """The directory, or `FileNotFoundError` naming the command that builds it.

    Only ever raises for a **registered farm path**. Anything else — a store, an
    `--from` directory — is returned untouched whether or not it exists, because for
    those an empty walk is the correct answer and this module has no standing to say
    otherwise. See the module docstring on where that line falls and why.
    """
    d = root / str(dirpath)
    if d.is_dir():
        return d
    farm = farm_for(dirpath)
    if farm is None:
        return d
    raise FileNotFoundError(
        f"no {farm.name} at {farm.path}/ — it is derived and git does not carry it. "
        f"Build it with: {farm.builder}")


# --------------------------------------------------------------- the mechanics

def relink(link: Path, target: Path, *, resolve: bool = True) -> None:
    """Point `link` at `target` with a **relative** symlink, replacing what is there.

    The idiom this replaces was copied out five times. Relative because an absolute
    link records this machine and breaks on a clone or a move.

    **`resolve=False` is not a convenience, it is a bug class with a name.** With
    `resolve=True` the target is resolved first, so a target that is *itself a
    symlink* is followed to whatever it points at. `zones.assemble` was bitten by
    exactly this: resolving sent its .lst paths straight back into `gt/zones/`,
    kraken looked for rasters beside the real ALTOs, and the blot links the function
    exists to create were never read — it failed loudly only because `gt/zones/`
    holds no PNGs. `scans/w-ocr/`'s ALTO links must point at the `ocr/` **view** and
    not through it, so that promoting a page re-points the view and the farm needs no
    rebuild; resolved, they would silently become links into `gt/ocr/` and that
    property would be gone while every link still worked.
    """
    if link.is_symlink() or link.exists():
        link.unlink()
    dest = target.resolve() if resolve else _absolute(target)
    link.symlink_to(os.path.relpath(dest, link.parent.resolve()))


def _absolute(p: Path) -> Path:
    """Absolute, without following a final symlink — `resolve()` minus the resolving.

    `Path.absolute()` does not normalise `..`, and `resolve()` is the thing being
    avoided, so the parent is resolved (it is a real directory) and the name is put
    back on unresolved.
    """
    return p.parent.resolve() / p.name


def rebuild(dirpath: Path, wanted: dict[str, Path], pattern: str,
            *, resolve: bool = True) -> dict:
    """Make `dirpath` hold exactly `wanted`: one relative symlink per entry.

    Prunes first, then links. Pruning is what makes this a rebuild rather than a
    top-up: an entry the criterion no longer selects is removed and **counted**,
    because a farm that only ever grew would keep a page that had been deleted from
    its store and nothing would say so.

    `pattern` scopes the prune, so a farm holding two kinds of file (`scans/w-ocr/`
    holds PNGs and XMLs) is swept once per kind and neither sweep deletes the other's
    entries.
    """
    dirpath.mkdir(parents=True, exist_ok=True)
    removed = 0
    for p in dirpath.glob(pattern):
        if p.name not in wanted:
            p.unlink()
            removed += 1
    for name, target in wanted.items():
        relink(dirpath / name, target, resolve=resolve)
    return {"dir": str(dirpath), "linked": len(wanted), "removed": removed}
