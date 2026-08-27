#!/usr/bin/env python3
"""Give `edition/toc.json` the provenance it was written without. **One-shot.**

`loi.json` and `authorities.json` each open with a `source` block naming the
scans they were read from, and each entry carries the leaf it was printed on.
`toc.json` was written as a bare list and so had nowhere to put either, which is
what `docs/open-questions.md` recorded: *"every other apparatus store is auditable
back to a page and this one is not."*

This writes it down. The reading, taken off `scans/chukchi-1-00{7..13}.png` at
300 dpi and ratified by hand before this ran:

    leaf   folio  entries  first .. last
    1-007  v      42       Introductory (1) ..
                             Economical Value of Reindeer-Breeding (95)
    1-008  vi     51       Dog-Breeding (98) .. Work in Wood (210)
    1-009  vii    52       Work in Iron (215) .. Songs (361)
    1-010  viii   52       Charms of the Maritime Chukchee (362) ..
                             Tricks performed in the Light (443)
    1-011  ix     52       Sexual Perversion and Transformed Shamans (448) ..
                             Marriage-Ruptures (596)
    1-012  x      51       Polygyny (598) .. Maydell's Reform (705)
    1-013  xi     16       Expansion of the Reindeer Chukchee and New Tribute
                             (707) .. General Conclusions (732)
                  ---
                  316 of 316

**Only the seven first entries were read; the rest follow contiguously**, which
is what makes this nine judgements rather than 316. That is safe because the
store's order is the printed order — asserted here rather than assumed: each
boundary title matches exactly one entry, the seven indices are strictly
increasing, and the counts sum to the whole store. Any of those failing is the
finding, and the script refuses rather than writing a partial attribution.

The second witness is that each leaf's *last* entry is the one immediately before
the next leaf's first, and on `1-007` and `1-008` that entry was also read off the
scan and agrees. No entry is assigned by proximity or by folio arithmetic.

This is book-internal apparatus, which the firewall explicitly exempts — *"the
printed TOC is not subject to this; it is evidence, and it binds"* — and no glyph
identity is at stake either way: the act is assigning a printed entry to the leaf
it was printed on.

Idempotent, but pointless twice: it refuses a store that already has a `source`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: `(ref, printed folio, title of the first entry, its page_start)`. The
#: page_start is carried so the match is on two fields rather than a title that
#: might repeat — "Names" and "Habitations" both occur twice in this store.
LEAVES = [
    ("1-007", "v", "Introductory", 1),
    ("1-008", "vi", "Dog-Breeding", 98),
    ("1-009", "vii", "Work in Iron", 215),
    ("1-010", "viii", "Charms of the Maritime Chukchee", 362),
    ("1-011", "ix", "Sexual Perversion and Transformed Shamans", 448),
    ("1-012", "x", "Polygyny", 598),
    ("1-013", "xi", "Expansion of the Reindeer Chukchee and New Tribute", 707),
]

SOURCE = {
    "what": "Table of Contents, Bogoras, The Chukchee, part 1 front matter",
    "read_from": "scans at 300 dpi, directly",
    "covers": "the whole volume: folios 1-732 across parts 1-3",
    "caveats": [
        "Only each leaf's FIRST entry was read off the scan; the rest are "
        "assigned contiguously, which the store's printed order licenses. "
        "tools/toc_provenance.py asserts that order rather than assuming it.",
        "The printed folios are roman (v-xi) and so are not keys into the "
        "arabic folio index; a ToC leaf is reached by its ref.",
    ],
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--commit", action="store_true",
                    help="write; otherwise report the assignment and stop")
    a = ap.parse_args(argv)

    p = a.root / "edition" / "toc.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, list):
        print(f"{p} already carries a source block — nothing to do", file=sys.stderr)
        return 1

    starts = []
    for ref, _folio, title, page in LEAVES:
        hits = [i for i, e in enumerate(doc)
                if e.get("title") == title and e.get("page_start") == page]
        if len(hits) != 1:
            print(f"{ref}: {title!r} at page {page} matches {len(hits)} entries, "
                  "not 1 — refusing", file=sys.stderr)
            return 1
        starts.append(hits[0])
    if starts != sorted(set(starts)):
        print(f"the leaf boundaries are not in printed order: {starts} — refusing",
              file=sys.stderr)
        return 1

    ends = starts[1:] + [len(doc)]
    for (ref, folio, _, _), s, e in zip(LEAVES, starts, ends, strict=True):
        for entry in doc[s:e]:
            entry["ref"] = ref
        print(f"{ref}  {folio:<5} {e - s:>3} entries   "
              f"{doc[s]['title']!r} ({doc[s]['page_start']}) .. "
              f"{doc[e - 1]['title']!r} ({doc[e - 1]['page_start']})")
    assigned = sum(1 for e in doc if e.get("ref"))
    print(f"{'':13}{assigned:>3} of {len(doc)} assigned")
    if assigned != len(doc):
        print("some entries fall outside every leaf — refusing", file=sys.stderr)
        return 1

    if not a.commit:
        print("\nreport only; --commit writes")
        return 0

    out = {
        "source": {**SOURCE,
                   "refs": [r for r, _, _, _ in LEAVES],
                   "printed_folios": [f for _, f, _, _ in LEAVES]},
        "entries": doc,
    }
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(p)
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
