#!/usr/bin/env python
"""One-off: a ratification names the text it was made against. Reports; `--commit` writes.

An alias says "this form, in this book, means this entity", and every `ratified` in the
store was a human's judgement with this book's corpus in view. Leaving it unqualified
would have the next book's pages linked by rule on a judgement nobody made about them.
"""
from __future__ import annotations

import argparse
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / "jesup" / "edition" / "entities"
OLD, NEW = "- status: ratified\n", "- status: ratified chukchi\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    n = 0
    for f in sorted(STORE.glob("*/*.md")):
        text = f.read_text("utf-8")
        if OLD in text:
            n += 1
            if a.commit:
                f.write_text(text.replace(OLD, NEW, 1), "utf-8")
    print(f"{n} entries" + ("" if a.commit else "; --commit writes"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
