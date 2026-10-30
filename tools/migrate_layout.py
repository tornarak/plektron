#!/usr/bin/env python
"""One-off: move the stores into `jesup/bogoras-chukchi/`. Reports; `--commit` writes.

Kept as a record, like the other `migrate_*` tools. Three things a plain `git mv`
would have broken, each checked after the move:

- the `pdfs/` links are relative and point out of the repo, so two levels deeper
  they dangle;
- `train/`'s links into the stores are absolute;
- `.gitignore`'s store rules are anchored at the repo root.

The collated `tei/*.xml` are gitignored, so git cannot restore them. A move inside
one filesystem does not touch their bytes, but take a copy first regardless.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WS = "jesup"
DEST = f"{WS}/bogoras-chukchi"
#: Moved whole. `git mv` of a directory carries what it holds untracked as well.
TRACKED = ("gt", "tei", "review", "edition", "config", "pdfs", "models", "project.json")
UNTRACKED = ("mz", "scans", "train")
DATA = ("data/pdf_images.json", "data/_migrated.json")
#: The rules that stay at the repo root, because they are not about a store.
ROOT_RULES = {"__pycache__/", "*.py[oc]", "build/", "dist/", "wheels/", "*.egg-info",
              ".pytest_cache/", ".ruff_cache/", "scratch/", ".venv", "scans/", "train/",
              "ocr300/", "figs-ocr300/", ".claude/worktrees/"}
MANIFEST = {
    "stem": "chukchi",
    "parts": [{"n": 1, "pdf": " Part I "}, {"n": 2, "pdf": " Part II "},
              {"n": 3, "pdf": " Part III "}],
    "masterless": ["1-001", "1-002", "1-361"],
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True,
                          text=True).stdout


def split_gitignore(text: str) -> tuple[str, str]:
    """(what stays at the root, what moves), each rule with the comment above it."""
    keep, move, block = [], [], []
    for line in text.splitlines():
        rule = line.strip()
        if not rule or rule.startswith("#"):
            block.append(line)
            continue
        if rule in ROOT_RULES:
            keep += block + [line]
        else:
            neg, bare = ("!", rule[1:]) if rule.startswith("!") else ("", rule)
            bare = bare.lstrip("/")
            if bare == "tei/chukchi-*.xml":
                bare = "tei/*-[0-9]*-[0-9]*.xml"
            move += block + [f"{neg}/*/{bare}"]
        block = []
    return "\n".join(keep + block) + "\n", "\n".join(move) + "\n"


def broken(top: Path) -> int:
    return sum(1 for p in top.rglob("*") if p.is_symlink() and not p.exists())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true", help="write; the default reports")
    a = ap.parse_args()
    if git("status", "--porcelain", "--", *TRACKED, *DATA, ".gitignore"):
        raise SystemExit("the stores have uncommitted changes: commit them first")
    if (REPO / DEST).exists():
        raise SystemExit(f"{DEST} already exists: this has run")
    missing = [p for p in (*TRACKED, *UNTRACKED, *DATA) if not (REPO / p).exists()]
    if missing:
        raise SystemExit(f"missing: {missing}")
    train = REPO / "train"
    absolute = [p for p in train.rglob("*") if p.is_symlink()
                and os.readlink(p).startswith(f"{REPO}/")]
    before = {d: broken(REPO / d) for d in ("scans", "review", "train", "pdfs")}
    root_ignore, ws_ignore = split_gitignore((REPO / ".gitignore").read_text("utf-8"))
    print(f"move to {DEST}: {', '.join((*TRACKED, *UNTRACKED, *DATA))}")
    print(f"re-point {len(absolute)} absolute links under train/, and pdfs/")
    print(f".gitignore rules moving: "
          f"{sum(1 for x in ws_ignore.splitlines() if x and not x.startswith('#'))}")
    print(f"dangling before: {before}")
    if not a.commit:
        print("report only; --commit writes")
        return 0

    (REPO / DEST / "data").mkdir(parents=True)
    for p in TRACKED:
        git("mv", p, f"{DEST}/{p}")
    for p in DATA:
        git("mv", p, f"{DEST}/{p}")
    for p in UNTRACKED:
        (REPO / p).rename(REPO / DEST / p)
    dest = REPO / DEST
    for link in dest.joinpath("train").rglob("*"):
        if link.is_symlink() and os.readlink(link).startswith(f"{REPO}/"):
            target = dest / Path(os.readlink(link)).relative_to(REPO)
            link.unlink()
            link.symlink_to(target)
    for link in dest.joinpath("pdfs").iterdir():
        target = os.readlink(link)
        link.unlink()
        link.symlink_to(f"../../{target}")
        if not link.exists():
            raise SystemExit(f"{link} does not resolve")
    (dest / "project.json").write_text(json.dumps(MANIFEST, indent=2) + "\n", "utf-8")
    (REPO / WS / "workspace.json").write_text(
        json.dumps({"title": "Jesup North Pacific Expedition"}, indent=2) + "\n", "utf-8")
    (REPO / ".gitignore").write_text(root_ignore, "utf-8")
    (REPO / WS / ".gitignore").write_text(
        "# Every project in this workspace, so a new one adds no lines. Each rule names\n"
        "# the project by `*`; the reasoning above each is unchanged from when these\n"
        "# sat at the repo root.\n\n" + ws_ignore, "utf-8")
    after = {d: broken(dest / d) for d in before}
    print(f"dangling after: {after}")
    if after != before:
        raise SystemExit("the move changed how many links dangle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
