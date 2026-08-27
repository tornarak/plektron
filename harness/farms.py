"""The derived trees: what they are, what builds them, and the linking they share.

Several directories in this repo are **derived** — git does not carry them, and a
fresh clone has none of them. Until this module nothing knew they were a class.
Their path constants sat in four modules under three spellings, the relative-symlink
idiom was copied out five times, and two of them (`scans/w-figs/`, `scans/w-ocr/`)
had no builder at all: they were made by hand, and had drifted, which is exactly
what a directory nobody can regenerate does.

This module is the declaration. `FARMS` names each tree once; `relink`/`rebuild` are
the mechanics every builder shares; `survey` is what `harness views check` prints.

**There is no `view` kind any more.** `ocr/` and `zones/` were symlink farms over
the paired stores, the human file winning, and every reader that took no store read
through them — a blend of ranks in front of the one layer whose subject is rank.
They were retired once the corpus showed every one of their 1,434 links resolving
into `gt/`; every reader names a store now, and `corpus mets` takes an ordered pair
of stores where the combined export is still wanted.

**The registry is also the scope of the absence rule**, and that is its second job.
`Path.glob()` on a missing directory returns empty *silently*, so before this module
existed a fresh clone walked a farm that was never built and reported zero pages with
exit 0. An absent tree and an empty one were indistinguishable — the same fault as an
unkeyed page against a keyed-but-empty one, which `gt/zones`' `exempt` mark exists
to separate.

**But the rule reaches farms and stops there, and the line is stores.** A missing
`mz/ocr/` means nothing has been predicted, which is a true statement about the
corpus and the ordinary state of a clone; a missing `scans/` means nobody has cut the
rasters, which is a statement about this working copy. The first is a record that is
empty, the second is a question that was never asked. So `paths._refs_under` asks
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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from . import train as _train
from .parallel import ptrack

# The one declaration of every derived path. `zones.py` aliases `SCANS` rather
# than being rewritten around it.
SCANS = "scans"
FIGS_BLOT = "scans/w-figs-blotted"
LINE_BLOT = "scans/w-blotted"
W_FIGS = "scans/w-figs"
W_OCR = "scans/w-ocr"
FIG_CROPS = "scans/fig-crops"
# From `train.py`, which owns the track record — the path is a property of the
# zone track, not of the farm registry, and the farm is only the half of it that
# has members. `train` is a leaf, so taking it here closes no loop.
TRAIN_WORK = _train.ZONES.workdir
# The half of the track that is a farm. The base holds two directories and no pages,
# so registering *it* made `views check` count zero entries for a training set that
# was fully laid out — a number that reads as "nothing prepared". `model/` is not a
# farm at all: its contents are a run's output, not links into a store.
TRAIN_DATA = _train.ZONES.datadir

# Imported by value, not by module, because `zones` imports this one: the leaf
# vocabulary lives there (it is a fact about the store) and the farms derived from
# it live here, so the name is copied down rather than the dependency reversed.
# `test_farms.py` holds the two in step.
_LEAF_KINDS = ("plate", "blank", "cover", "map", "apparatus")


@dataclass(frozen=True)
class Farm:
    """One derived tree.

    `kind` is not decoration — it decides what `check` may honestly assert:

        select   a symlink farm over one tree, membership from a criterion.
                 Exactly checkable.
        raster   painted pixels. Membership is checkable; freshness is not
                 checked here — see `verified` below.
        source   no builder in this repo at all.
        scratch  reported, never rebuilt here.

    `verified` is the honesty column: it says how deep the comparison went, so that
    `state: ok` is never read as more than was tested. For `scans/w-figs-blotted/`
    it says `membership`, and the reason wants stating carefully because it was
    stated wrongly here for a long time. It is **not** that content freshness is
    unknowable: `zones.blot_all`'s docstring now records that an mtime test against
    both inputs would in fact catch a figure ALTO corrected after the blot. It is
    that this check declines to open pixel data at all, and that the one case mtime
    genuinely cannot see — a *deleted* figure ALTO, absence having no timestamp — is
    a membership question anyway. Same discipline as `gt/zones/_ink_cache.json`
    reporting `?` rather than blank: a verdict must not out-run its evidence.

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
    # `scans/` only. `blot_one` already tolerates a page with no figure ALTO — it
    # links instead of painting — so `gt/fig/` is not a precondition; the pixels are.
    Farm("w-figs-blotted", FIGS_BLOT, "raster", (SCANS,),
         "harness views build w-figs-blotted", "membership"),
    Farm("w-figs", W_FIGS, "select", ("gt/fig",),
         "harness views build w-figs", "membership"),
    Farm("w-ocr", W_OCR, "select", ("gt/ocr",),
         "harness views build w-ocr", "membership"),
    # The figure crops. `raster` and not `select`: these are cut pixels, not links
    # into `scans/`, so an absent `scans/` stops the builder outright rather than
    # leaving something that dangles loudly. `gt/fig/` is a *read* too, unlike the
    # blot's — `blot_one` tolerates a page with no figure ALTO by linking it
    # through, while here a page with no ALTO has no crops to cut and the store is
    # what says which pages those are.
    Farm("fig-crops", FIG_CROPS, "raster", (SCANS, "gt/fig"),
         "harness fig crops --all", "membership"),
    # Reported, never built here. `scans/` has no builder in this repo — it is
    # `harness scans extract` over `pdfs/`, whose three entries are symlinks
    # pointing outside the repo, so on a clone the rasters cannot be regenerated at
    # all. The script also runs under `uv run --script` with no harness in its
    # environment, which is what keeps a PDF reader out of the package. `train/` is
    # scratch that `train assemble zones` clobbers by design; rebuilding it out of band
    # would be preparing a training run nobody asked for.
    Farm("scans", SCANS, "source", (),
         "harness scans extract --all --rasters DIR && harness scans swap DIR",
         "none"),
    Farm("train", TRAIN_DATA, "scratch", (),
         "harness train assemble zones", "none"),
    # One per leaf kind: `scans/plate/`, `scans/blank/`, and so on, each a farm of
    # links into `scans/` for the leaves ruled that kind. `select`, because
    # membership is a criterion over one tree — and the criterion is a *store*
    # fact, `gt/zones/`'s split, so it is exactly checkable rather than a guess
    # about what somebody meant by sorting a directory.
    #
    # **Derived from `LEAF_KINDS`, never listed.** A kind added to the vocabulary
    # gets its farm here by construction; a hand-written tuple would leave the
    # new one unregistered, and `views check` would report the directory as a
    # stray rather than rebuild it.
    #
    # These began as a hand sort — somebody looked at 94 leaves and put each one
    # in a directory — which is the act the split lists now record. The farm is
    # the sort rebuilt *from* that record, so it survives a `scans/` rebuild
    # instead of being the only copy.
    *(Farm(k, f"{SCANS}/{k}", "select", (SCANS,),
           f"harness views build {k}", "membership")
      for k in _LEAF_KINDS),
)

BY_NAME = {f.name: f for f in FARMS}
BY_PATH = {f.path: f for f in FARMS}

#: Every registered farm, in registry order.
NAMES = tuple(f.name for f in FARMS)

#: The farms `views build` will actually rebuild, in registry order.
BUILDABLE = tuple(f.name for f in FARMS if f.kind in ("select", "raster"))

#: The token that asks for every farm. Spelled out rather than implied by a bare
#: invocation, because `views build` is the most expensive command in the harness
#: — repainting `scans/w-figs-blotted/` is 252 page composites — and the cost is
#: invisible at the call site. Nothing about typing `harness views build` suggests
#: a corpus-wide raster pass, so the default was a trap for exactly the caller who
#: wanted one farm relinked. Making `all` explicit costs three characters and
#: removes the only way to start that pass by accident.
ALL = "all"


def select(names: Iterable[str], *, buildable_only: bool = False) -> tuple[str, ...]:
    """Expand a CLI farm selection into registry order, `all` included.

    Order is the registry's, never the caller's, so a selection is reproducible
    however it was typed. Duplicates collapse — asking for a farm twice is a typo,
    not a request to build it twice.
    """
    pool = BUILDABLE if buildable_only else NAMES
    wanted = set(names)
    if ALL in wanted:
        return tuple(pool)
    return tuple(n for n in pool if n in wanted)


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
    holds no PNGs. A link into a farm of links wants this too, so that the outer
    farm follows the inner rather than silently pointing past it.
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


# ----------------------------------------------------------- the two selections

def _w_figs_wanted(root: Path) -> dict[str, Path]:
    """The pages that have a figure ALTO, raster only."""
    from .figures import fig_refs
    return {f"chukchi-{ref}.png": root / SCANS / f"chukchi-{ref}.png"
            for ref in fig_refs(root)}


def _w_ocr_wanted(root: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """The pages a human has been through, raster and ALTO, as two sweeps.

    **Membership is `gt/ocr/`, and so is the ALTO the link names.** The name reads
    as "pages with OCR" and that is what an earlier draft of this builder
    selected. The directory refuted it: it held exactly the 20 gt pages and none of
    the `mz`-only ones, and the single entry it lacked was the page that had
    entered *gt* that morning. After a corpus `ocr predict` sweep every page has
    OCR, so "pages with OCR" would be all 832, which is no selection. "The raster
    beside the pages a human has been through" stays meaningful however much the
    machine reads. The ALTO link used to point at the `ocr/` view, which the
    hand-made farm had pointed at `gt/ocr/` directly; with the view gone it does
    again, and there is nothing left for `resolve=False` to preserve.

    Two sweeps rather than one because the farm holds two kinds of file and a single
    prune pattern would have each kind deleting the other's entries.
    """
    from .refs import norm_ref, parse_ref
    refs = []
    for p in (root / "gt" / "ocr").glob("chukchi-*.xml"):
        try:
            refs.append(norm_ref(p.stem))
        except ValueError:      # matched the glob but is not a ref
            continue
    refs = sorted(set(refs), key=parse_ref)
    return (
        {f"chukchi-{r}.png": root / SCANS / f"chukchi-{r}.png" for r in refs},
        {f"chukchi-{r}.xml": root / "gt" / "ocr" / f"chukchi-{r}.xml" for r in refs},
    )


def build_w_figs(root: Path = Path(".")) -> dict:
    """`scans/w-figs/`: the raster of every page carrying a figure ALTO."""
    rep = rebuild(root / W_FIGS, _w_figs_wanted(root), "chukchi-*.png")
    return {"farm": "w-figs", **rep}


def build_w_ocr(root: Path = Path(".")) -> dict:
    """`scans/w-ocr/`: raster beside ALTO for every page a human has been through."""
    pngs, xmls = _w_ocr_wanted(root)
    a = rebuild(root / W_OCR, pngs, "chukchi-*.png")
    b = rebuild(root / W_OCR, xmls, "chukchi-*.xml")
    return {"farm": "w-ocr", "dir": a["dir"], "linked": a["linked"] + b["linked"],
            "removed": a["removed"] + b["removed"]}


def build(name: str, root: Path = Path("."), jobs: int | None = None,
          tick=None) -> dict:
    """Rebuild one farm by name. Builders are imported lazily; see the module head.

    `jobs` and `tick` reach only the two raster builders — the link farms are
    symlink churn at ~0.1 ms a page, which `parallel` already rules is not worth a
    pool or a bar. Both used to be dropped here: `blot_all` and `crop_all` accept
    them and draw a bar when reached through `zones blot` or `fig crops`, and were
    silent when reached through this verb, which is the more expensive route.

    A farm whose `reads` are not all present is **skipped with a row**, never
    attempted and never silently dropped. The blot builder opens pixels out of
    `scans/`, so on a clone it cannot run and saying so is the whole of the correct
    behaviour; the two selections only need their tracked membership sources, and
    their raster links are allowed to dangle.
    """
    farm = BY_NAME[name]
    missing = [d for d in farm.reads if not (root / d).is_dir()]
    if missing:
        return {"farm": name, "dir": farm.path, "linked": 0, "removed": 0,
                "skipped": f"no {missing[0]}/"}

    if name == "w-figs-blotted":
        from .zones import blot_all
        rep = blot_all(root, jobs, tick)
        return {"farm": name, "dir": rep["dir"], "linked": rep["total"],
                "removed": 0, "skipped": ""}
    if name == "fig-crops":
        from .figures import crop_all
        rep = crop_all(root=root, jobs=jobs, tick=tick)
        return {"farm": name, "dir": rep["dir"], "linked": rep["written"],
                "removed": 0, "skipped": ""}
    if name in _LEAF_KINDS:
        # `rebuild` does the whole job: it links what the criterion wants and
        # removes what it no longer does, which is what makes a re-ruled leaf move
        # between farms rather than appearing in both.
        rep = rebuild(root / SCANS / name, _wanted_for(name, root) or {},
                      "chukchi-*.png")
        return {"farm": name, **{k: rep[k] for k in ("dir", "linked", "removed")},
                "skipped": ""}
    rep = build_w_figs(root) if name == "w-figs" else build_w_ocr(root)
    return {**rep, "skipped": ""}


# ------------------------------------------------------------------ the survey

def _wanted_for(name: str, root: Path) -> dict[str, Path] | None:
    """What this farm's directory *should* hold, or None if that is not knowable.

    None is a real answer and is why `survey` can report `?`. For `scans/` there is
    no criterion in this repo at all, and for `train/` the criterion is whatever the
    last `train assemble zones` was asked for — neither is a set this module can compute,
    and computing one anyway would be inventing a verdict.
    """
    if name == "w-figs-blotted":
        # Globbed here rather than through `paths.all_scans`, deliberately: that
        # one is guarded, and `scans/` is a registered farm, so it refuses when the
        # directory is absent. The blot farm can outlive `scans/` (its 252 painted
        # pages are real files), and a survey that raised while describing that
        # situation would be the report failing on exactly the machine it is for.
        return {p.name: p for p in (root / SCANS).glob("chukchi-*.png")}
    if name == "w-figs":
        return _w_figs_wanted(root)
    if name == "w-ocr":
        pngs, xmls = _w_ocr_wanted(root)
        return {**pngs, **xmls}
    if name == "fig-crops":
        # Membership is one crop per declared `GraphicZone`, computed from
        # `gt/fig/` rather than from what is on disk — which is what lets the
        # survey say `stale` when a keyed box gained or lost a crop instead of
        # only noticing an empty directory. The value is the *source raster*,
        # since that is what `rebuild`'s callers use to explain a member; a crop
        # is cut from it rather than linked to it.
        from .figures import crops_wanted
        return {name_: root / SCANS / f"chukchi-{ref}.png"
                for name_, ref in crops_wanted(root).items()}
    if name in _LEAF_KINDS:
        # The leaves ruled this kind, each linking to its own raster. Computed
        # from the split lists and not from what is in the directory, so a leaf
        # re-ruled from `plate` to `blank` reports `stale` on both farms rather
        # than sitting in the wrong one indefinitely.
        from .zones import load_splits
        return {f"chukchi-{r}.png": root / SCANS / f"chukchi-{r}.png"
                for r, split in load_splits(root).items() if split == name}
    return None


def survey(root: Path = Path("."), tick: Callable | None = None) -> list[dict]:
    """One fixed-key record per farm — what `harness views check` prints.

    Tests directories itself and never goes through a guarded enumerator: the verb
    that reports absence has to be callable in its presence.

    Three states, and the third is the one worth having. `absent` is the directory
    not existing; `stale` is membership disagreeing with the criterion, or a link
    pointing nowhere; `ok` is neither. What `ok` deliberately does **not** mean is
    "up to date" — the `verified` column says how deep the comparison went, and for
    the painted raster it says `membership`, because nothing here opens pixel data
    or the timestamps behind it. A verdict that let a membership check imply a
    content check would be the fluent nonsense this project is organised against.

    That column used to be justified by calling the painted raster's freshness
    *uncheckable*, which was wrong — see `zones.blot_all`. It is unchecked here,
    which is a statement about this verb and not about the world, and `membership`
    is the honest word for it either way.
    """
    rows = []
    for farm in ptrack(FARMS, tick):
        d = root / farm.path
        present = d.is_dir()
        wanted = _wanted_for(farm.name, root) if present else None
        entries = missing = extra = dangling = 0

        if present:
            have = {p.name for p in d.iterdir() if not p.is_dir()}
            entries = len(have)
            dangling = sum(1 for p in d.iterdir()
                           if p.is_symlink() and not p.exists())
            if wanted is not None:
                missing = len(set(wanted) - have)
                extra = len(have - set(wanted))

        if not present:
            state = "absent"
        elif wanted is None:
            # Nothing to compare against, so no verdict is available. Not `ok`:
            # that would be a clean bill of health nobody issued.
            state = "?"
        elif missing or extra or dangling:
            state = "stale"
        else:
            state = "ok"

        rows.append({"farm": farm.name, "kind": farm.kind, "path": farm.path,
                     "state": state, "entries": entries, "missing": missing,
                     "extra": extra, "dangling": dangling,
                     "verified": farm.verified if wanted is not None else "none",
                     "builder": farm.builder})
    return rows
