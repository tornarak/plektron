#!/usr/bin/env python3
"""Remove every TextLine from ALTO exports, leaving the zones alone.

The figure track keeps only geometry: `GraphicZone` blocks never carried real
text, and the `GraphicZone-FigDesc` captions are now recorded in
`data/readings.md`, read from the 300 dpi scans. The exported line segmentation
is worse than useless here — it drops whole lines of a caption, so a line-level
witness in the ALTO would silently disagree with the readings file.

This subsumes `strip_graphiczone_lines.py`, which removed lines from
`GraphicZone` blocks only. Zone labels are irrelevant now: no block keeps lines.

Blocks themselves are never touched, so the zone ids that `data/readings.md`
and `harness tei context` key against survive.
"""
import sys
from pathlib import Path
from lxml import etree


def strip_file(path: Path) -> int:
    tree = etree.parse(str(path), etree.XMLParser(remove_blank_text=False))
    root = tree.getroot()

    removed = 0
    for line in root.findall(".//{*}TextLine"):
        line.getparent().remove(line)
        removed += 1

    if removed:
        tree.write(str(path), xml_declaration=True, encoding="UTF-8",
                   standalone=None)
    return removed


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    files = sorted(target.glob("chukchi-*.xml"))
    total = 0
    for p in files:
        n = strip_file(p)
        if n:
            print(f"{p.name}: removed {n} TextLine(s)")
        total += n
    print(f"{len(files)} file(s), total removed: {total}")


if __name__ == "__main__":
    main()
