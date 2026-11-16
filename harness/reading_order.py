"""`harness ocr order`: the unread pages in the order that front-loads the lexicon.

A native form ratified on one page is a ✓ *seen* on every later page that prints
it, and a key the next reader can type. So the order pages are read in decides
how soon the repeats are cheap. Most forms are printed once (82% of the 1900
*Materials*' 1,338, 2026-11-16), and no order changes what a page holding only
those costs; what an order can move is the repeats, and reading by the book
reaches them slowly (4% of them pre-seen after 20 pages, against 68% greedy).

**A greedy order, re-derived from the stores on every call.** Each step takes the
page whose forms not yet seen recur most on the other unread pages. "Seen"
starts as every form on a page already in `gt/ocr/`, so the order answers for
the corpus as it stands after the last restore, and a batch is the next N rows.

**The forms are the text layer's, and the merge is the lookup's.** Copy A's
tokens (`mz/ocr/`), outside the apparatus and any `DiscardZone`, that the
witness would call native, each reduced by the near-miss reduction
(`marks.reduction`, `config/handle.json` `reduce`) so the copies' misreadings of
one word count as one. That merges too eagerly as well as too little — an
inflected form is its own token, and two words a confusion class folds together
are one — so the numbers are an order's evidence, never a census of the lexicon.
"""
from __future__ import annotations

import unicodedata
from collections import Counter
from pathlib import Path

from . import keying, marks
from . import zones as zmod
from .detectors import EDGE_PUNCT, TOKEN, bears_inventory, tier2
from .lines import page_lines
from .recognize import MZDIR, alto_for
from .refs import APPARATUS_ZONES, DISCARD_ZONES, norm_ref


def page_forms(path: Path, ref: str, root: Path, rules, table,
               dropped: bool = False) -> Counter:
    """One page's native forms, reduced, with their counts. With `dropped`, each
    form as a layer that lost a droppable letter reads it too (`Кэє` for
    `Кэ́lє`): what a ratified page makes seen, since the layers' reading of a later
    page may be that one."""
    out: Counter = Counter()
    for r in page_lines(path, root, ref=ref):
        if r["zone"] in DISCARD_ZONES or r["zone"] in APPARATUS_ZONES:
            continue
        text = rules.fold(unicodedata.normalize("NFD", r["text"] or ""))
        for m in TOKEN.finditer(text):
            tok = m.group().strip(EDGE_PUNCT)
            if tok and not tier2(tok, rules) and bears_inventory(tok, rules):
                out[marks.reduction(tok, table)] += 1
                if dropped and (d := marks.dropped_reduction(tok, table)):
                    out[d] += 1
    return out


def greedy(unread: dict[str, Counter], seen: set[str]) -> list[dict]:
    """The pages in greedy order: each step the page whose forms not in `seen`
    occur most often on the other unread pages (`buys`). Ties go to the earlier
    page. `seen` is not modified."""
    total: Counter = Counter()
    for c in unread.values():
        total.update(c)
    seen, left, rows = set(seen), dict(unread), []

    def gain(r: str) -> int:
        return sum(total[f] - n for f, n in left[r].items() if f not in seen)
    while left:
        best = max(left, key=lambda r: (gain(r), [-x for x in zmod.parse_ref(r)]))
        rows.append({"rank": len(rows) + 1, "ref": best, "forms": len(left[best]),
                     "new": sum(1 for f in left[best] if f not in seen),
                     "buys": gain(best)})
        seen.update(left[best])
        del left[best]
    return rows


def order(root: Path = Path("."), refs: list[str] | None = None) -> dict:
    """The candidates in greedy order, each row with what it buys.

    `refs` narrows the candidates; the default is every text page with a text
    layer and no ground truth. Returns `{"pages": rows, "summary": {...}}`.
    """
    root = Path(root)
    rules = keying.rules(root)
    table = marks.handle_table(root)
    splits = zmod.load_splits(root)
    unread: dict[str, Counter] = {}
    seen: set[str] = set()
    for ref in sorted(splits, key=zmod.parse_ref):
        if splits[ref] not in zmod.TEXT_SPLITS:
            continue
        gt = alto_for(ref, root, "gt/ocr")
        if gt.exists():
            seen.update(page_forms(gt, ref, root, rules, table, dropped=True))
            continue
        mz = alto_for(ref, root, MZDIR)
        if mz.exists():
            unread[ref] = page_forms(mz, ref, root, rules, table)
    if refs is not None:
        wanted = {norm_ref(r) for r in refs}
        unread = {r: c for r, c in unread.items() if r in wanted}

    total: Counter = Counter()
    for c in unread.values():
        total.update(c)
    occ = sum(total.values())
    # Repeats on unread pages of a form not yet seen: the most any order can
    # pre-see. Forms already seen are pre-seen whatever is read next.
    fresh = {f: v for f, v in total.items() if f not in seen}
    ceiling = sum(v - 1 for v in fresh.values())

    rows, bought = [], 0
    for row in greedy(unread, seen):
        bought += row["buys"]
        rows.append({**row, "cumulative": f"{bought / ceiling:.0%}" if ceiling else "—"})
    return {"pages": rows,
            "summary": {"unread": len(unread), "occurrences": occ,
                        "distinct": len(total),
                        "already_seen": sum(v for f, v in total.items() if f not in fresh),
                        "ceiling": ceiling}}


__all__ = ["greedy", "order", "page_forms"]
