#!/usr/bin/env python
"""One-off: a citation in the shared entity store names its book. Reports; `--commit`
writes.

A bare `1-044` names no page once a workspace has two texts, so every one becomes
`chukchi-1-044`. All of them are this text's, which is why the rewrite can be mechanical
at all, and it refuses a ref with no scan behind it so that a page range cannot pass for
a ref. `entity check` holds the store to the spelling from here on.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from harness.layout import BARE_REF_RE

REPO = Path(__file__).resolve().parent.parent
TEXT = REPO / "jesup" / "bogoras-chukchi"
STORE = REPO / "jesup" / "edition" / "entities"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    files = refs = 0
    for f in sorted(STORE.glob("*/*.md")):
        text = f.read_text("utf-8")
        hits = BARE_REF_RE.findall(text)
        for ref in hits:
            if not (TEXT / "scans" / f"chukchi-{ref}.png").exists():
                raise SystemExit(f"{f}: {ref} has no scan, so it is not a page ref")
        if hits:
            files, refs = files + 1, refs + len(hits)
            if a.commit:
                f.write_text(BARE_REF_RE.sub(r"chukchi-\1", text), "utf-8")
    print(f"{refs} citations in {files} files" + ("" if a.commit else "; --commit writes"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
