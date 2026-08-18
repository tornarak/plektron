#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""One-time: `gt/zones/_exempt.lst` -> one list per leaf kind.

`exempt` was a training flag that came to carry a judgement — *this leaf is not a
text page* — and then to stand in for five different things at once. The kind is
now the split value itself (`zones.LEAF_KINDS`), so the one list has to become
five.

**Where the classification comes from, and why it is not derived here.** A human
sorted the 94 non-run leaves by hand into `scans/plate`, `scans/blank`,
`scans/cover` and `scans/map` — symlink farms into `scans/`, made by looking at
each leaf. That sort is the `#ed` act this migration transcribes; nothing in this
script decides what a leaf is. The remaining 21 are the leaves of the runs
`data/runs.json` declares, whose content this repository already holds parsed, and
they become `apparatus`.

Deriving any of it would be the failure this repo is organised against. Figure
boxes do not make a plate — 9 of the 44 boxed leaves are full-page text figures —
and an unboxed leaf is equally a blank verso or the volume's folding map, which is
exactly the confusion that motivated the change.

**Refuses rather than guesses.** The five lists must partition `_exempt.lst`
exactly: same total, no ref in two of them, none outside it. A page that would be
dropped or duplicated stops the whole run with nothing written, because a leaf
silently missing from every list reads downstream as a text page nobody has keyed.

    uv run --script tools/migrate_leaf_kinds.py            # report
    uv run --script tools/migrate_leaf_kinds.py --commit   # write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: The sorted farms, and the kind each one witnesses. `apparatus` is not here: it
#: comes from `data/runs.json`, which is a declaration rather than a sort.
FARMS = {"plate": "scans/plate", "blank": "scans/blank",
         "cover": "scans/cover", "map": "scans/map"}


def _refs_in_farm(d: Path) -> set[str]:
    """The refs a sort directory names. Entries are symlinks into `scans/`; only
    the basename is read, so a dangling link still counts — the classification is
    the human's act and does not depend on the target surviving."""
    if not d.is_dir():
        return set()
    return {p.name.removeprefix("chukchi-").removesuffix(".png")
            for p in d.iterdir() if p.name.startswith("chukchi-")}


def _lst(p: Path) -> set[str]:
    if not p.exists():
        return set()
    return {ln.strip().removeprefix("chukchi-").removesuffix(".xml")
            for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()}


def plan(root: Path) -> dict:
    zones = root / "gt" / "zones"
    exempt = _lst(zones / "_exempt.lst")

    want = {k: _refs_in_farm(root / d) for k, d in FARMS.items()}
    runs = json.loads((root / "data" / "runs.json").read_text(encoding="utf-8"))
    want["apparatus"] = {r for run in runs.get("runs") or []
                         for r in run.get("refs") or []}

    seen: dict[str, str] = {}
    dupes: list[str] = []
    for kind, refs in want.items():
        for r in sorted(refs):
            if r in seen:
                dupes.append(f"{r}: {seen[r]} and {kind}")
            seen[r] = kind

    return {
        "want": want,
        "exempt": exempt,
        "dupes": dupes,
        "unsorted": sorted(exempt - seen.keys()),
        "stray": sorted(seen.keys() - exempt),
        "train": len(_lst(zones / "_train.lst")),
        "eval": len(_lst(zones / "_eval.lst")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--commit", action="store_true",
                    help="write the lists and remove _exempt.lst")
    a = ap.parse_args()

    p = plan(a.root)
    for kind, refs in p["want"].items():
        print(f"  {kind:<10} {len(refs):>4}")
    total = sum(len(v) for v in p["want"].values())
    print(f"  {'':<10} {'':>4}\n  {'total':<10} {total:>4} "
          f"against {len(p['exempt'])} exempt "
          f"({p['train']} train, {p['eval']} eval)")

    bad = False
    for label, rows in (("in two kinds at once", p["dupes"]),
                        ("exempt but sorted nowhere", p["unsorted"]),
                        ("sorted but not exempt", p["stray"])):
        if rows:
            bad = True
            print(f"\n{label}: {len(rows)}")
            for r in rows:
                print(f"    {r}")

    if bad:
        print("\nRefused: the five lists do not partition _exempt.lst. Nothing "
              "written — a leaf missing from every list reads downstream as a "
              "text page nobody has keyed.")
        return 1

    if not a.commit:
        print("\nClean. Re-run with --commit to write.")
        return 0

    zones = a.root / "gt" / "zones"
    for kind, refs in p["want"].items():
        (zones / f"_{kind}.lst").write_text(
            "".join(f"chukchi-{r}.xml\n" for r in sorted(refs)),
            encoding="utf-8")
    # Last, and unconditionally: `load_splits` iterates `SPLITS`, so a leftover
    # `_exempt.lst` is not an error downstream — it is simply never read again.
    # A file that silently stops mattering is worse than one that is gone.
    (zones / "_exempt.lst").unlink(missing_ok=True)
    print(f"\nWrote {len(p['want'])} lists; _exempt.lst removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
