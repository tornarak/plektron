"""METS manifests over an ALTO store, for eScriptorium import.

**Imports nothing from this package**, like `ns.py` and `atomic.py` and for the
same reason: a manifest is a function of a list of filenames and nothing else,
so nothing here needs a store module, and a leaf cannot join an import cycle.

It lived in `figures.py` while `gt/fig/` was the only store that exported one,
which made the *builder* look like part of the figure track when only its one
caller was. `build_mets` never read a figure: it takes names and returns
markup. Every ALTO store can be handed to eScriptorium, so the verb is
`corpus mets STORE --out DIR` and the code sits where its generality already
was.

**Never written into the store it describes.** A manifest committed beside the
thing it manifests is a second copy of that thing's shape with nothing keeping
the two honest, and both stores that ever held one proved it: `gt/fig/METS.xml`
described a store rewritten under it, and `gt/ocr/METS.xml` — tracked from the
baseline commit, and missed when the `gt/fig` one was removed — manifested 20
files against a store of 663. A METS is `#mz`: mechanical output, re-derived
from its store on every run so that it fails rather than goes stale. `--out` is
required so it cannot land back in a store by omission.
"""
from __future__ import annotations

from pathlib import Path

METS_NS = "http://www.loc.gov/METS/"
XLINK_NS = "http://www.w3.org/1999/xlink"

# Every directory that holds page ALTOs, as `corpus mets` will accept them.
#
# Declared rather than discovered because a typo should be a usage error naming
# the alternatives rather than an empty export. A store absent from a given clone
# — every `mz/` tree is derived and gitignored — is not an error here: the verb
# reports what it found, and finding nothing is the usage error, not being
# unlisted.
#
# **The combined export is a parameter, not a directory.** `ocr/` and `zones/`
# used to be here as read views — symlink farms resolving each page to the human
# file where there was one — and were the ones you would hand to eScriptorium.
# They are gone; the same export is spelled as an ordered pair, `gt/ocr,mz/ocr`,
# first store winning per page, and `write_mets` copies the winning referents
# beside the manifest since no one directory holds them. See `parse_stores`.
ALTO_STORES = (
    "gt/ocr", "gt/fig", "gt/zones", "gt/lines",
    "mz/ocr", "mz/fig", "mz/zones",
)


def parse_stores(spec: str) -> tuple[str, ...]:
    """`gt/ocr` or `gt/ocr,mz/ocr` as a tuple of stores, first winning.

    Every member must be an `ALTO_STORES` name and the pair must not repeat one —
    a store named twice is a typo, not a request. A `ValueError` is the usage
    error `main` renders.
    """
    stores = tuple(s.strip() for s in spec.split(","))
    bad = [s for s in stores if s not in ALTO_STORES]
    if bad:
        raise ValueError(f"{', '.join(bad)}: not an ALTO store. One of "
                         f"{', '.join(ALTO_STORES)}, or an ordered pair such as "
                         "gt/ocr,mz/ocr")
    if len(set(stores)) != len(stores):
        raise ValueError(f"{spec}: a store named twice")
    return stores


def build_mets(names: list[str]) -> str:
    """A METS manifest over a list of ALTO filenames, for eScriptorium import.

    The shape mirrors what eScriptorium itself exports: one
    `fileGrp USE="export"` listing the ALTOs, and a physical `structMap` with a
    `div TYPE="page"` each, in filename order — which for `chukchi-PP-NNN` is page
    order. No image fileGrp: on import the pages match images already in the
    document, exactly as on the round-trip of an export.
    """
    from xml.sax.saxutils import quoteattr

    files, divs = [], []
    for i, name in enumerate(names, 1):
        fid = f"export{i}"
        files.append(f'        <file ID="{fid}">\n'
                     f"          <FLocat xlink:href={quoteattr(name)}/>\n"
                     f"        </file>")
        divs.append(f'      <div TYPE="page">\n'
                    f'        <fptr FILEID="{fid}"/>\n'
                    f"      </div>")
    nl = "\n"
    return (f'<mets xmlns="{METS_NS}" xmlns:xlink="{XLINK_NS}">\n'
            f"  <fileSec>\n"
            f'    <fileGrp USE="export">\n{nl.join(files)}\n'
            f"    </fileGrp>\n"
            f"  </fileSec>\n"
            f'  <structMap TYPE="physical">\n'
            f'    <div TYPE="document">\n{nl.join(divs)}\n'
            f"    </div>\n"
            f"  </structMap>\n"
            f"</mets>\n")


def write_mets(store: str | tuple[str, ...], out_dir: str | Path,
               root: Path = Path("."), *, stem: str) -> dict:
    """Write `METS.xml` for an ALTO store, or an ordered pair of them, into a
    directory the caller names.

    `store` is a path under `root` — one of `ALTO_STORES` when it arrives from
    the CLI, though nothing here requires that, so a caller with a store this
    module has not heard of is not blocked by a list it cannot edit.

    **One store: manifest only.** The manifest names the ALTOs and nothing else,
    so a caller zips the store's files and this manifest together at the zip
    root. It is always `METS.xml`, which is the name eScriptorium looks for — so
    **two exports want two directories**, and writing both into one silently
    keeps the second.

    **A pair: the referents are copied too.** `("gt/ocr", "mz/ocr")` is every page
    either holds, the first store winning where both do — the export the retired
    `ocr/` view used to serve. No directory holds that set, so each page's
    winning file is copied beside the manifest and the caller zips the directory.
    The report says how many came from each store; a rank split that lived only
    in the reader's memory is the kind this repo does not keep. Refuses an out
    dir already holding page ALTOs, since a second run's leftovers would be
    manifested as this one's.
    """
    stores = (store,) if isinstance(store, str) else tuple(store)
    chosen: dict[str, Path] = {}
    for s in stores:                       # first store wins: later ones only fill
        for p in (root / s).glob(f"{stem}-*.xml"):
            chosen.setdefault(p.name, p)
    names = sorted(chosen)
    if not names:
        raise ValueError(f"no {stem}-*.xml under {', '.join(str(root / s) for s in stores)}")
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    rep = {"store": ",".join(stores), "path": str(d / "METS.xml"),
           "files": len(names), "first": names[0], "last": names[-1]}
    if len(stores) > 1:
        import shutil
        stale = sorted(p.name for p in d.glob(f"{stem}-*.xml"))
        if stale:
            raise ValueError(f"{d} already holds {len(stale)} page ALTO(s) "
                             f"({stale[0]} …); a combined export wants an empty "
                             "directory, or the leftovers would be manifested as "
                             "this run's")
        for name in names:
            shutil.copyfile(chosen[name], d / name)
        for s in stores:
            rep[f"from {s}"] = sum(1 for p in chosen.values()
                                   if p.parent == root / s)
    (d / "METS.xml").write_text(build_mets(names), encoding="utf-8")
    return rep
