#!/usr/bin/env python3
"""Move every stored coordinate into the extracted master's space. The driver only.

    uv run python tools/migrate_to_master.py            # report; writes nothing
    uv run python tools/migrate_to_master.py --commit

**The logic is not here.** It lives in `harness/migrate.py` where the tests can
reach it; this file is the driver and nothing else. `tools/migrate_fig_bboxes.py`
states the rule and the reason: "a migration whose correctness argument sits in a
script that is run once and never imported is a migration nobody can check
afterwards." The previous coordinate migration, `tools/migrate_coords.py`, put its
argument in a docstring instead, and this one deliberately does not.

PRECONDITIONS, both of which this checks rather than assumes:

  - `data/pdf_images.json` exists — `tools/extract_scans.py --commit` writes it,
    and every shift in this migration is read from it per page;
  - `scans/` has already been rebuilt from the masters, or has not been touched at
    all. Either is fine. What is not fine is a half-swapped tree, which is why the
    extractor writes to a sibling and swaps whole.

Run it once. Re-running is safe in the sense that it cannot double-shift — a page
already in the master's space reports `already` and is left alone — but the
receipt at `data/_migrated.json` is what actually distinguishes "part 2, correctly
untouched" from "part 1, not yet reached", since part 2's dimensions do not change.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import migrate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--commit", action="store_true",
                    help="write the stores; without it, report what would move")
    ap.add_argument("--store", action="append", default=None, metavar="DIR",
                    help=f"limit to one store; repeatable {list(migrate.STORES)}")
    ap.add_argument("--refs", nargs="*", default=None, metavar="PP-NNN",
                    help="limit to named pages")
    a = ap.parse_args(argv)

    stores = tuple(a.store) if a.store else migrate.STORES
    rep = migrate.run(a.root, stores=stores, refs=a.refs, commit=a.commit)
    if rep.get("error"):
        print(rep["error"], file=sys.stderr)
        return 1

    print(f"{'migrated':24s} {rep['migrated']}")
    print(f"{'already in master space':24s} {rep['already']}")
    print(f"{'aborted':24s} {rep['aborted']}")
    print(f"{'clamped values':24s} {rep['clamped']}  "
          f"({rep['clamped_gt']} of them in gt/)")

    by_store: dict[tuple[str, str], int] = {}
    for f in rep["files"]:
        key = (f.get("store", "?"), f["action"])
        by_store[key] = by_store.get(key, 0) + 1
    print("\nstore            action     files")
    for (store, action), n in sorted(by_store.items()):
        print(f"  {store:14s} {action:10s} {n}")

    print("\nband ledgers")
    for b in rep["bands"]:
        print(f"  {b['path']:34s} {b['action']:9s} {b['bands']:4d} bands")
        for note in b["notes_with_px"]:
            # Left exactly as written. A width in that prose is still true and a y
            # is not, and rewriting a human's note to keep the arithmetic tidy
            # would be editing the record to match the code.
            print(f"      reread this note: {note}")

    for rel in rep["dropped"]:
        print(f"\ndropped {rel} (its stamp cannot see a raster change)")

    if rep["correction_pages_with_y_in_ids"]:
        n = len(rep["correction_pages_with_y_in_ids"])
        print(f"\n{n} gt/lines page(s) keep correction ids encoding the OLD y — "
              "the id is a key, not a measurement")

    for f in rep["files"]:
        if f["action"] == "ABORTED":
            print(f"ABORTED {f['ref']} {f.get('store', '')}: {f['why']}",
                  file=sys.stderr)

    if rep["receipt"]:
        print(f"\nwrote {rep['receipt']}")
    elif a.commit:
        print("\nnothing written: aborts must be cleared first", file=sys.stderr)
    else:
        print("\nreport only; --commit writes")
    return 1 if rep["aborted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
