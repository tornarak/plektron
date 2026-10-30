#!/usr/bin/env python
"""One-off: what a workspace shares moves up to `jesup/`. Reports; `--commit` writes.

Kept as a record, like the other `migrate_*` tools. Models are renamed for their
track, because a model shared across a workspace is not the book's it was first fitted
to; the manifest records that book as its `text`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WS = REPO / "jesup"
P = WS / "bogoras-chukchi"
STORES = ("edition/entities", "edition/geo", "edition/entity-images.json")
MOVES = {"bogoras-seg": "zones-seg", "bogoras-fig": "fig-seg", "bogoras-ocr": "text-rec"}


def git(*a: str) -> None:
    subprocess.run(["git", *a], cwd=REPO, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    if (WS / "models").exists():
        raise SystemExit("jesup/models exists: this has run")
    print("up to the workspace:", *STORES, "edition/lexicon (if any)", "models/")
    print("renamed:", MOVES)
    if not a.commit:
        print("report only; --commit writes")
        return 0
    (WS / "edition").mkdir(exist_ok=True)
    for s in STORES:
        git("mv", str(P / s), str(WS / s))
    if (P / "edition/lexicon").exists():
        (P / "edition/lexicon").rename(WS / "edition/lexicon")
    git("mv", str(P / "models"), str(WS / "models"))
    for old, new in MOVES.items():
        if (WS / "models" / old).exists():
            git("mv", str(WS / "models" / old), str(WS / "models" / new))
        if (P / "train" / old).exists():
            (P / "train" / old).rename(P / "train" / new)
    man = WS / "models/zones-seg/zones-seg.json"
    rec = json.loads(man.read_text("utf-8"))
    rec["model"] = "models/zones-seg/zones-seg.safetensors"
    rec = {"text": "chukchi", **rec}
    man.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", "utf-8")
    ig = WS / ".gitignore"
    s = ig.read_text("utf-8")
    s = s.replace("!/*/models/bogoras-seg/\n", "!/*/models/zones-seg/\n"
                                               "/models/*\n!/models/zones-seg/\n"
                                               "/models/zones-seg/*.bak\n")
    s = s.replace("/*/models/bogoras-seg/*.bak", "/*/models/zones-seg/*.bak")
    s = s.replace("!/*/models/bogoras-fig/\n", "!/*/models/fig-seg/\n!/models/fig-seg/\n"
                                               "/models/fig-seg/*.bak\n")
    s = s.replace("/*/models/bogoras-fig/*.bak", "/*/models/fig-seg/*.bak")
    ig.write_text(s, "utf-8")
    links = 0
    for link in (P / "train").rglob("*"):
        if link.is_symlink():
            t = os.readlink(link)
            for old, new in MOVES.items():
                t2 = t.replace(f"/train/{old}/", f"/train/{new}/")
                if t2 != t:
                    t = t2
            if t != os.readlink(link):
                link.unlink()
                link.symlink_to(t)
                links += 1
    print("re-pointed links:", links)
    print("broken under train:", sum(1 for p in (P / "train").rglob("*")
                                     if p.is_symlink() and not p.exists()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
