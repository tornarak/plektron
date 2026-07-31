#!/usr/bin/env python3
"""Write a METS manifest over a directory of ALTO files, for eScriptorium import.

The shape mirrors what eScriptorium itself exports: a single
`fileGrp USE="export"` listing the ALTO files, and a physical `structMap` with
one `div TYPE="page"` per file, in filename order — which for `chukchi-PP-NNN`
is page order. No image fileGrp: on import the pages are matched to images
already in the document, exactly as on a round-trip of an export.

    uv run python tools/make_mets.py gt/fig

Then zip the directory contents (the manifest at the zip root, not the
directory) and import that.

An eScriptorium export ships its own manifest, and it may be spelled `METS.xml`
rather than `mets.xml`. If one is already there we overwrite *that* file, because
a zip carrying two manifests is an import hazard and writing a second spelling
alongside the first is how you end up with one.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

METS = "http://www.loc.gov/METS/"
XLINK = "http://www.w3.org/1999/xlink"


def build(names: list[str]) -> str:
    files, divs = [], []
    for i, name in enumerate(names, 1):
        fid = f"export{i}"
        files.append(
            f'        <file ID="{fid}">\n'
            f"          <FLocat xlink:href={quoteattr(name)}/>\n"
            f"        </file>"
        )
        divs.append(
            f'      <div TYPE="page">\n'
            f'        <fptr FILEID="{fid}"/>\n'
            f"      </div>"
        )
    nl = "\n"
    return (
        f'<mets xmlns="{METS}" xmlns:xlink="{XLINK}">\n'
        f"  <fileSec>\n"
        f'    <fileGrp USE="export">\n'
        f"{nl.join(files)}\n"
        f"    </fileGrp>\n"
        f"  </fileSec>\n"
        f'  <structMap TYPE="physical">\n'
        f'    <div TYPE="document">\n'
        f"{nl.join(divs)}\n"
        f"    </div>\n"
        f"  </structMap>\n"
        f"</mets>\n"
    )


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    names = sorted(p.name for p in target.glob("chukchi-*.xml"))
    if not names:
        sys.exit(f"no chukchi-*.xml under {target}")
    existing = [p for p in target.iterdir()
                if p.is_file() and p.name.lower() == "mets.xml"]
    out = existing[0] if existing else target / "mets.xml"
    out.write_text(build(names), encoding="utf-8")
    print(f"{out}: {len(names)} file(s), {names[0]} .. {names[-1]}")


if __name__ == "__main__":
    main()
