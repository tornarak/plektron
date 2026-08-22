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
# Declared rather than discovered because `click.Choice` needs the pool at parse
# time, and because a typo should be a usage error naming the alternatives rather
# than an empty export. A store absent from a given clone — every `mz/` tree is
# derived and gitignored — is not an error here: the verb reports what it found,
# and finding nothing is the usage error, not being unlisted.
#
# The two bare names are the read views (`ocr/`, `zones/`), which resolve into
# whichever store holds each page and are therefore the ones you would usually
# hand to eScriptorium.
ALTO_STORES = (
    "gt/ocr", "gt/fig", "gt/zones", "gt/lines",
    "mz/ocr", "mz/fig", "mz/zones",
    "ocr", "zones",
)


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


def write_mets(store: str, out_dir: str | Path,
               root: Path = Path(".")) -> dict:
    """Write `METS.xml` for one ALTO store into a directory the caller names.

    `store` is a path under `root` — one of `ALTO_STORES` when it arrives from
    the CLI, though nothing here requires that, so a caller with a store this
    module has not heard of is not blocked by a list it cannot edit.

    The manifest names the ALTOs and nothing else, so a caller zips the store's
    files and this manifest together at the zip root. It is always `METS.xml`,
    which is the name eScriptorium looks for — so **two stores want two
    directories**, and exporting both into one silently keeps the second.
    """
    names = sorted(p.name for p in (root / store).glob("chukchi-*.xml"))
    if not names:
        raise ValueError(f"no chukchi-*.xml under {root / store}")
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "METS.xml"
    p.write_text(build_mets(names), encoding="utf-8")
    return {"store": store, "path": str(p), "files": len(names),
            "first": names[0], "last": names[-1]}
