"""The informant ledger — `edition/informants.json`: who told each item, where, when.

A book of recorded folklore closes each item with the line saying whom it was
taken down from («Записано отъ чукчанки Кутјэ́ўт на р. Молондѣ въ 1895 г.»).
The ledger is those lines, one record per printed line, on the leaf it is
printed on, with the parse beside it. `docs/apparatus.md` owns the shape and
the reasoning; this module loads it and gates it.

**`printed` is the record, and the gate holds the parse to it.** Every field
that restates part of the line — the narrator's `form`, the place as printed,
the year — must occur in `printed`, because a field that can drift from the
line it was parsed from is a second, unchecked witness. That is also what makes
`form` per record rather than per narrator: the same narrator is printed
several ways, and the store keeps what each leaf prints.

**The grouping is editorial and says so.** `narrator` joins records under one
person; the heading name, the `jesup` correspondence and the entity a place
links are judgements at the store's declared `resp`, not readings.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .refs import REF_RE

PATH = Path("edition/informants.json")

#: The ranks a field of this store may claim. A model's work is `#llm`; a human
#: raising it writes `#ed`. Nothing here is a rule's output, so `#mz` and `#gt`
#: — which assert a re-derivation or a ratified transclusion — have no meaning.
RESP = frozenset({"#llm", "#ed"})

_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def load(root: Path = Path(".")) -> dict | None:
    """The store, or None where the text keeps none. A text without recorded
    narrators — *The Chukchee* is a monograph — simply has no ledger."""
    p = Path(root) / PATH
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def census(doc: dict) -> list[dict]:
    """One row per narrator: how many items, where and when. Measurement."""
    recs: dict[str, list[dict]] = {}
    for r in doc.get("records", []):
        recs.setdefault(r.get("narrator"), []).append(r)
    rows = []
    for n in doc.get("narrators", []):
        rs = recs.get(n.get("id"), [])
        places = Counter((r.get("where") or {}).get("place") for r in rs)
        places.pop(None, None)
        rows.append({
            "id": n.get("id"), "name": n.get("name"), "sex": n.get("sex"),
            "items": len({r.get("item") for r in rs}), "records": len(rs),
            "places": "; ".join(f"{p} ×{c}" if c > 1 else p for p, c in places.most_common()),
            "years": " ".join(str(y) for y in sorted({r["year"] for r in rs if r.get("year")})),
            "jesup": (n.get("jesup") or {}).get("form", ""),
        })
    rows.sort(key=lambda r: (-r["items"], r["id"] or ""))
    return rows


def _toc(root: Path) -> list[dict]:
    from .state import load_toc
    return [e for e in load_toc(root) if e.get("id")]


def _spans(toc: list[dict]) -> dict[str, tuple[int, int | None]]:
    """`{item id: (first folio, the next item's first folio)}`. An item's closing
    line sits on its last leaf, which is the next item's first leaf or before."""
    items = [e for e in toc if e.get("level") == 2 and isinstance(e.get("page_start"), int)]
    out = {}
    for a, b in zip(items, items[1:] + [None], strict=True):
        out[a["id"]] = (a["page_start"], b["page_start"] if b else None)
    return out


def _scans(root: Path) -> set[str] | None:
    """The refs this text's raster manifest knows, or None without one."""
    p = Path(root) / "data/pdf_images.json"
    if not p.exists():
        return None
    return {k for k in json.loads(p.read_text(encoding="utf-8")) if REF_RE.match(k)}


def check(root: Path = Path(".")) -> dict:
    """`{"census", "errors", "warnings", "records", "narrators"}` over the store.

    Errors are things the store cannot be: a record naming nobody, a field that
    does not occur in the line it was parsed from, an item or a page the text
    does not have, an entity that is not in the encyclopedia. Warnings are a
    worklist: a record outside its item's printed span (a misplaced item, or a
    heading the ToC lacks), an item that neither has a record nor is declared
    unattributed.
    """
    from .entities import load as load_entities

    root = Path(root)
    doc = load(root)
    errors: list[dict] = []
    warnings: list[dict] = []
    if doc is None:
        return {"census": [], "errors": [], "warnings": [], "records": 0, "narrators": 0}

    def err(where, what):
        errors.append({"where": where, "what": what})

    def warn(where, what):
        warnings.append({"where": where, "what": what})

    src = doc.get("source")
    if not isinstance(src, dict) or not src.get("read_from"):
        err("source", "no source block saying what the store was read from")
    for field, rank in ((src or {}).get("resp") or {}).items():
        if rank not in RESP:
            err(f"source.resp.{field}", f"{rank!r} is not one of {sorted(RESP)}")

    ids: Counter = Counter(n.get("id") for n in doc.get("narrators", []))
    for nid, c in ids.items():
        if not isinstance(nid, str) or not _ID_RE.match(nid):
            err(f"narrator {nid!r}", "an id is lower-case letters, digits and hyphens")
        if c > 1:
            err(f"narrator {nid}", f"declared {c} times")
    for n in doc.get("narrators", []):
        if not n.get("name"):
            err(f"narrator {n.get('id')}", "no name")
        if (j := n.get("jesup")) and j.get("resp") not in RESP:
            err(f"narrator {n.get('id')}.jesup", f"resp {j.get('resp')!r} is not one of {sorted(RESP)}")

    toc = _toc(root)
    toc_ids = {e["id"] for e in toc}
    spans = _spans(toc)
    scans = _scans(root)
    ents = load_entities(root)
    used: Counter = Counter()
    seen: set = set()
    for i, r in enumerate(doc.get("records", []), 1):
        at = f"record {i} ({r.get('ref')}, {r.get('item')})"
        printed = r.get("printed") or ""
        if not printed:
            err(at, "no printed line")
        nid = r.get("narrator")
        used[nid] += 1
        if nid not in ids:
            err(at, f"narrator {nid!r} is not declared")
        if r.get("form") and r["form"] not in printed:
            err(at, f"form {r['form']!r} does not occur in the printed line")
        if (w := r.get("where")):
            if w.get("printed") and w["printed"] not in printed:
                err(at, f"where {w['printed']!r} does not occur in the printed line")
            if (e := w.get("entity")) and e not in ents:
                err(at, f"entity {e!r} is not in the encyclopedia")
        if r.get("year") and str(r["year"]) not in printed:
            err(at, f"year {r['year']} does not occur in the printed line")
        ref = r.get("ref") or ""
        if not REF_RE.match(ref):
            err(at, f"{ref!r} is not a PP-NNN ref")
        elif scans is not None and ref not in scans:
            err(at, f"{ref} is not a page of this text")
        item = r.get("item")
        if toc_ids and item not in toc_ids:
            err(at, f"item {item!r} is not a ToC entry")
        # **Position, not text, identifies a line.** Two items can close on one
        # leaf with identical lines, so the text alone would call a true pair a
        # duplicate; `on_leaf` is where it stands among the leaf's informant lines.
        key = (ref, r.get("on_leaf"))
        if not isinstance(r.get("on_leaf"), int) or r["on_leaf"] < 1:
            err(at, "no on_leaf position")
        elif key in seen:
            err(at, f"a second record at position {r['on_leaf']} on {ref}")
        seen.add(key)
        folio = r.get("folio")
        if item in spans and isinstance(folio, int):
            lo, hi = spans[item]
            if folio < lo or (hi is not None and folio > hi):
                warn(at, f"printed on folio {folio}, outside the item's span "
                         f"{lo}–{hi if hi is not None else '…'} in the ToC")
    for nid in ids:
        if not used[nid]:
            err(f"narrator {nid}", "no record names this narrator")

    un = doc.get("unattributed") or {}
    declared = set(un.get("items") or [])
    have = {r.get("item") for r in doc.get("records", [])}
    for item in sorted(declared & have):
        err(f"unattributed {item}", "declared unattributed but has a record")
    sec = {e["id"]: e.get("chapter") for e in toc if e.get("level") == 2}
    covered = set(un.get("sections") or [])
    for item, chapter in sec.items():
        if item not in have and item not in declared and chapter not in covered:
            warn(f"item {item}", "no informant line, and not declared unattributed")

    return {"census": census(doc), "errors": errors, "warnings": warnings,
            "records": len(doc.get("records", [])), "narrators": len(ids)}
