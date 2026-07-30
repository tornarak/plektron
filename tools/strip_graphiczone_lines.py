#!/usr/bin/env python3
"""Remove TextLine elements from GraphicZone TextBlocks in ALTO exports.

SUPERSEDED by `strip_lines.py`, and kept only for the tag-ID lesson below. The
distinction it draws is gone: `fig/` now holds no TextLine in *any* block, and
caption text lives in `data/readings.md`. Do not point this at `fig/` expecting
it to preserve captions — there are none left to preserve. Note also that its
`main()` globs `*.xml`, which would try to parse the METS manifest sitting in
`fig/`; `strip_lines.py` globs `chukchi-*.xml` instead.

GraphicZone blocks hold figure geometry; any TextLine inside one is a
segmentation artifact. GraphicZone-FigDesc blocks were left untouched.

Zones are resolved through `OtherTag/@LABEL`, never through the tag ID. The IDs
are assigned per export — this script previously hardcoded `BT55`/`BT56`, which
the current export spells `BT68`/`BT69`, so it had quietly become a no-op that
reported success. `TAGREFS` is a space-separated list, so it is split rather
than compared whole.
"""
import sys
from pathlib import Path
from lxml import etree

GRAPHIC = "GraphicZone"


def strip_file(path: Path) -> int:
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    labels = {t.get("ID"): t.get("LABEL", "") for t in root.iter("{*}OtherTag")}

    removed = 0
    for block in root.iter("{*}TextBlock"):
        refs = (block.get("TAGREFS") or "").split()
        if not any(labels.get(r) == GRAPHIC for r in refs):
            continue
        for line in block.findall("{*}TextLine"):
            block.remove(line)
            removed += 1

    if removed:
        tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=None)
    return removed


def main():
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    total = 0
    for xml_path in sorted(target_dir.glob("*.xml")):
        n = strip_file(xml_path)
        if n:
            print(f"{xml_path.name}: removed {n} TextLine(s)")
        total += n
    print(f"total removed: {total}")


if __name__ == "__main__":
    main()
