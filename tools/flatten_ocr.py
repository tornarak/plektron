#!/usr/bin/env python3
"""Flatten every OCR ALTO to one unlabelled block: the zones come out of the store.

    uv run --script tools/flatten_ocr.py            # report, write nothing
    uv run --script tools/flatten_ocr.py --commit   # write

`ocr predict` used to bake the keyed zones into the page it wrote — one labelled
`TextBlock` per zone, the zone's rectangle on it, the label reachable through
`TAGREFS` — and `restore` copied that skeleton into `gt/ocr/`. So both stores held
a copy of `gt/zones/`'s content, in a store that is not its home, in a form that
went stale on the first re-cut. Every consumer had already gone back to geometry
for exactly that reason; `lines.page_lines` now derives a line's zone by
containment for every record, and `ocr predict` writes bare lines.

This is the one-shot that brings the pages written before that rule into the same
shape, so `gt/ocr/` holds one shape and not two. The shape itself is
`recognize.flatten_page`, which `predict` applies to its own output — one
definition, two callers.

WHAT IS INVARIANT, AND CHECKED. `page_lines` assigns `index` from document order
and every `proposal.json`/`decision.json` is keyed on it, so a line that moved
would silently re-key an adjudication. Before and after the flatten, three digests
must match or the page is refused: the `TextLine` id sequence, every line's box,
and the `String/@CONTENT` sequence. Block ids and the `OtherTag` multiset are
*expected* to change and are outside the digest — the inverse of
`migrate.structural_digest`, which held them invariant because a translation
must not touch them.

IDEMPOTENT BY CONSTRUCTION. A page already in the flattened shape is reported as
unchanged and not rewritten, so a second run ends "Clean." No receipt is needed,
unlike the coordinate migration whose part-2 pages could not tell "done" from
"unreached" by inspection.

PROVENANCE. A rule step is appended to every page rewritten, `mz/` and `gt/`
alike — a file names what produced it. The existing segmentation step's
`regions_from` input is left as it is: it is a true record of that act, and the
appended step is the record that the regions have since gone. It is also why
`recognize.recognized_by` finds the recognizer by label rather than as the file's
last producer.

The 717 `gt/ocr/` rewrites are tracked files; commit them as their own change,
staged by name.

HISTORICAL. This has run, 2026-08-27, over all 1,434 pages of both stores: every
page reported one block, no block label, line ids, boxes and text unchanged, and a
second run said "Clean." Before it ran, the containment-derived zone was compared
against the label each `gt/ocr/` block still carried, corpus-wide: 30,026 lines
agreed and 16 disagreed, on `1-097` (14 lines, a band re-labelled `Continued` →
`P` since prediction) and `2-085` (2 lines, unzoned at prediction and under a
running-title band added since) — the staleness this removed, and the record of
what the labels said before they went. It stays runnable and idempotent, so a
page that somehow arrives labelled can be brought into shape; a page `ocr predict`
writes never needs it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lxml import etree

from harness import provenance
from harness.atomic import tmp_for
from harness.ns import ALTO_NS
from harness.recognize import FLATTEN_VERSION, GTDIR, MZDIR, flatten_page
from harness.refs import norm_ref, parse_ref

STORES = (GTDIR, MZDIR)
STEP = "tools/flatten_ocr.py"
IDENT = "OCR_tools-flatten-ocr"


def digest(alto) -> tuple:
    """What the flatten must not touch: line ids, line boxes, the text."""
    lines = list(alto.iter("{*}TextLine"))
    return (
        tuple(ln.get("ID") for ln in lines),
        tuple((ln.get("HPOS"), ln.get("VPOS"), ln.get("WIDTH"), ln.get("HEIGHT"))
              for ln in lines),
        tuple(s.get("CONTENT") or "" for s in alto.iter("{*}String")),
    )


def producer() -> provenance.Producer:
    return provenance.Producer(step=STEP, label="flatten", kind="rule",
                               version=f"harness {FLATTEN_VERSION}")


def flatten_file(path: Path, commit: bool) -> dict:
    """One page: flatten in memory, verify the digest, write if asked."""
    ref = norm_ref(path.stem.replace("chukchi-", ""))
    tree = etree.parse(str(path))
    alto = tree.getroot()
    before = digest(alto)
    if not flatten_page(alto, ref):
        return {"path": str(path), "changed": False, "written": False}
    after = digest(alto)
    if before != after:
        raise ValueError(f"{path}: the flatten moved a line, an id or a String — "
                         "refusing to write. This is the invariant the script "
                         "exists to keep; look before running it again")
    desc = alto.find(f"{{{ALTO_NS}}}Description")
    if desc is None:
        desc = etree.Element(f"{{{ALTO_NS}}}Description")
        alto.insert(0, desc)
    desc.append(provenance.alto_processing(producer(), IDENT))
    if commit:
        tmp = tmp_for(path)
        tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
                   pretty_print=True)
        tmp.replace(path)
    return {"path": str(path), "changed": True, "written": commit}


def pages(root: Path) -> list[Path]:
    out = []
    for store in STORES:
        for p in (root / store).glob("chukchi-*.xml"):
            try:
                norm_ref(p.stem.replace("chukchi-", ""))
            except ValueError:
                continue
            out.append(p)
    return sorted(out, key=lambda p: (str(p.parent),
                                      parse_ref(p.stem.replace("chukchi-", ""))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--commit", action="store_true",
                    help="write the flattened pages; without it, report only")
    a = ap.parse_args()

    changed = dict.fromkeys(STORES, 0)
    seen = dict.fromkeys(STORES, 0)
    for p in pages(a.root):
        store = f"{p.parent.parent.name}/{p.parent.name}"
        seen[store] += 1
        rep = flatten_file(p, a.commit)
        if rep["changed"]:
            changed[store] += 1
            print(f"{'wrote' if rep['written'] else 'would flatten'}  {p}")
    for s in STORES:
        print(f"{s}: {changed[s]} of {seen[s]} to flatten")
    if not any(changed.values()):
        print("Clean.")
    elif not a.commit:
        print("\nNothing written. Re-run with --commit to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
