"""Move every stored coordinate from the legacy render's space into the master's.

`scans/` was `pdftoppm -r 300` over the *page box*, and the page boxes the scans
were wrapped in are arbitrary. `harness scans extract` cuts the rasters from the
embedded master instead, which changes each page's pixel dimensions — and every
coordinate in `gt/zones/`, `gt/ocr/`, `gt/fig/`, `gt/lines/`, `mz/zones/` and
`mz/ocr/` has to follow.

**TRANSLATE, DO NOT SCALE, AND THAT IS THE WHOLE OF IT.** Every master in the
corpus is placed at scale 1.0 and is exactly 300 dpi; the parts differ only by
where the master sits inside its page box. So the operation is `x - dx`, `y - dy`
with the shift read per page from `data/pdf_images.json`, and:

  - **extents never move.** A width is the same width in both spaces. That is what
    makes the structural digest below a real check rather than a formality.
  - **it is exactly invertible**, where a ratio is not. `tools/migrate_coords.py`
    was right to refuse a bare `2` and take a measured ratio per page per axis, but
    that was a different migration: 150 dpi to 300 really was a resample. Applying
    a ratio here would resample coordinates that only needed moving.
  - **the shift is a single rounded integer per page**, not a per-coordinate
    rounding. The true offsets are fractional — part 1's is 21.375 px — and
    rounding each coordinate independently would spread that eighth of a pixel
    around as drift.

Part 2 does not move at all: its master was always the page box, so `dx, dy` is
`(0, 0)` for all 268 pages. **That is why a size check cannot serve as the
idempotence guard** — 2550x3525 before and after cannot distinguish "correctly
untouched" from "not yet reached" — and why this writes a receipt instead.

TWO INTEGRITY GATES, BECAUSE THE OBVIOUS ONE IS VACUOUS HERE.
`migrate_coords.content_digest` hashes every `String/@CONTENT`, which is the empty
sequence for `gt/zones/`, `gt/fig/` and `mz/zones/` — it would pass on the majority
of files this touches while checking nothing. So the text digest is kept for the
stores that have text, and a **structural** digest carries the rest: the block-id
set, the `OtherTag/@LABEL` multiset, and every box's width and height. All three
are invariant under translation by definition, so any drift in them is a defect
rather than a difference.

IDS ARE NEVER RE-MINTED. `data/readings.md` keys 395 captions by the last field of
a `gt/fig/` block id. And `gt/lines/` correction ids encode the y they were made at
(`corr_PP-NNN-671`), which this deliberately leaves alone: the id is a key, not a
measurement, and re-minting it would break the id-keyed carry-forward in
`corrections.save_lines`. The report names those pages so the divergence is on the
record rather than discovered later.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lxml import etree

from .figures import PDF_IMAGES, pdf_images
from .refs import norm_ref, parse_ref

#: Stores holding raster-pixel coordinates. **`ocr/` and `zones/` are absent on
#: purpose**: they are the read views, and migrating through a view writes through
#: a view, which is the one thing the store layout forbids outright.
STORES = ("gt/zones", "gt/ocr", "gt/fig", "gt/lines", "mz/zones", "mz/ocr")

#: Band ledgers: bare `{y0, y1}` with no page box anywhere in the file, matched by
#: midpoint. They carry no x, so only the y shift applies.
BAND_FILES = ("gt/zones/_para_exempt.json", "gt/zones/_ink_exempt.json",
              "gt/lines/_ink_exempt.json")

#: Deleted rather than migrated. Its `stamp` is the mtimes of a page's ALTO and of
#: `_ink_exempt.json`, never the raster — so on **part 2**, whose ALTOs do not move
#: while the raster's content changes underneath them, every cached verdict would
#: go on looking valid. `zones.cached_ink` returns None for an unknown page and the
#: keying refills it, so dropping the file costs nothing and keeping it costs the
#: one thing the cache exists to prevent.
DROP_FILES = ("gt/zones/_ink_cache.json",)

RECEIPT = "_migrated.json"

X_POS, Y_POS = ("HPOS",), ("VPOS",)
EXTENTS = ("WIDTH", "HEIGHT")


def _fmt(value: float, source: str) -> str:
    """Put a number back in the spelling its source used.

    eScriptorium writes `Page/@WIDTH` as `"1412"` and `TextBlock/@HPOS` as
    `"365.0"`, and a diff full of gratuitous `1412` -> `1412.0` churn would bury
    the changes that matter. `migrate_coords.py`'s rule, kept.
    """
    return f"{value:.1f}" if "." in source else str(int(round(value)))


def render_space(manifest: dict[str, dict]) -> dict[str, dict]:
    """The legacy pdftoppm space, expressed as a manifest.

    **This is what makes the original migration a special case rather than a
    separate code path.** A store in render space is a store whose master is the
    page box and whose placement is the origin — so the render space *is* a
    manifest, with `master` set to the recorded render size and `offset` at
    `(0, 0)`, and "render -> master" is then just one manifest to another. Writing
    it this way is not tidiness: it means the corpus's one real migration and every
    future re-cut are checked by the same code, rather than the tested path being
    the one that will never run again.
    """
    out = {}
    for ref, e in manifest.items():
        w, h = e.get("render") or [0, 0]
        m = e.get("master") or {}
        out[ref] = {"master": {"w": w, "h": h, "rendered": bool(m.get("rendered"))},
                    "offset": [0, 0], "render": [w, h], "images": []}
    return out


def plan(old: dict[str, dict], new: dict[str, dict]) -> dict[str, dict]:
    """Per ref: the page boxes either side, the shift between them, and `scaled`.

    **The shift is the difference of two placements, not either manifest's
    `offset`.** `offset` records where a master sat inside the *legacy* render, and
    it is spent — the stores left that space and `data/_migrated.json` says so.
    What a store needs when the rasters are re-cut is `new placement - old
    placement`, per page, because a coordinate is at `x` in the old master, at
    `x + old_offset` in the shared page space both manifests describe, and at
    `x + old_offset - new_offset` in the new one. Reading `offset` directly would
    re-apply a shift that has already been applied once.

    `scaled` marks the pages where the two spaces differ by a **ratio** rather than
    a translation — the masterless RGB leaves, whose own ppi is whatever the
    photograph was. A translation cannot express that, so `migrate_file` refuses
    such a page if it carries any coordinate at all rather than moving it wrongly.
    """
    out = {}
    for ref, n in new.items():
        o = old.get(ref)
        nm = n.get("master") or {}
        to = (nm.get("w", 0), nm.get("h", 0))
        if o is None:
            # A page the old manifest never had. Nothing of ours is in its space, so
            # there is nothing to translate — but it is reported, not assumed away.
            out[ref] = {"from": to, "to": to, "shift": (0, 0), "scaled": False,
                        "new": True}
            continue
        om = o.get("master") or {}
        frm = (om.get("w", 0), om.get("h", 0))
        ox, oy = o.get("offset") or [0, 0]
        nx, ny = n.get("offset") or [0, 0]
        # Two spaces are related by a scale, not a translation, when either side is a
        # page taken at its own ppi and the sizes disagree. Both sides are checked:
        # a page that stops being masterless is as much a ratio as one that starts.
        scaled = ((bool(om.get("rendered")) or bool(nm.get("rendered")))
                  and frm != to)
        out[ref] = {"from": frm, "to": to, "shift": (nx - ox, ny - oy),
                    "scaled": scaled, "new": False}
    return out


def shifts(root: Path = Path(".")) -> dict[str, tuple[int, int]]:
    """Every page's legacy `(dx, dy)`, such that `master = render - (dx, dy)`."""
    return {ref: tuple(e.get("offset") or [0, 0])
            for ref, e in pdf_images(root).items()}


def text_digest(tree) -> str:
    """SHA-256 over every `String/@CONTENT` in document order."""
    h = hashlib.sha256()
    for el in tree.iter("{*}String"):
        h.update((el.get("CONTENT") or "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def structural_digest(tree) -> str:
    """SHA-256 over what a translation cannot change: ids, labels, and extents.

    The gate for the geometry-only stores, where `text_digest` hashes nothing at
    all. Sorted, so document order is free to be irrelevant; extents included,
    because a translation that resized something has stopped being a translation.
    """
    ids, labels, ext = [], [], []
    for el in tree.iter("{*}OtherTag"):
        labels.append(el.get("LABEL") or "")
    for el in tree.iter():
        if el.get("ID"):
            ids.append(el.get("ID"))
        # **`Page` and `PrintSpace` are excluded, and the exclusion is the point.**
        # They state the raster's size rather than describe a box on it, so they
        # are *supposed* to change — they are set from the manifest, not
        # translated. Hashing them made every page in the corpus abort as
        # "structure changed", which is the check being wrong rather than the data.
        if etree.QName(el).localname in ("Page", "PrintSpace"):
            continue
        w, h = el.get("WIDTH"), el.get("HEIGHT")
        if w is not None and h is not None and el.get("HPOS") is not None:
            ext.append(f"{float(w):.1f}x{float(h):.1f}")
    h = hashlib.sha256()
    for part in (sorted(ids), sorted(labels), sorted(ext)):
        for s in part:
            h.update(s.encode("utf-8"))
            h.update(b"\0")
        h.update(b"\1")
    return h.hexdigest()


def _shift_pairs(raw: str, dx: int, dy: int, w: int, h: int) -> tuple[str, int]:
    """`POINTS`/`BASELINE`: whitespace-separated alternating x y."""
    out, clamped = [], 0
    for i, t in enumerate(raw.split()):
        try:
            v = float(t)
        except ValueError:
            out.append(t)
            continue
        limit = w if i % 2 == 0 else h
        moved = v - (dx if i % 2 == 0 else dy)
        fixed = min(max(moved, 0.0), float(limit))
        clamped += fixed != moved
        out.append(_fmt(fixed, t))
    return " ".join(out), clamped


def _shift_box(el, dx: int, dy: int, w: int, h: int) -> int:
    """Move an origin; leave its extent alone. Returns how many values clamped.

    **The extent is not touched, and that is the invariant.** Under a translation a
    box keeps its size, so a width that changed here would mean the operation was
    something other than what this module claims to do — which is exactly what
    `structural_digest` then refuses.
    """
    clamped = 0
    for attr, d, limit in (("HPOS", dx, w), ("VPOS", dy, h)):
        raw = el.get(attr)
        if raw is None:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        moved = v - d
        # A box drawn into the margin the master does not include has nowhere to
        # go. Clamped and counted rather than left to fail validation later.
        ext = float(el.get(EXTENTS[0 if attr == "HPOS" else 1]) or 0)
        fixed = min(max(moved, 0.0), max(0.0, float(limit) - ext))
        clamped += fixed != moved
        el.set(attr, _fmt(fixed, raw))
    return clamped


def migrate_tree(tree, dx: int, dy: int, size: tuple[int, int]) -> dict:
    """Translate one parsed ALTO in place. Returns a per-file record."""
    w, h = size
    clamped = 0
    for el in tree.iter():
        tag = etree.QName(el).localname
        if tag in ("Page", "PrintSpace"):
            continue
        if el.get("HPOS") is not None or el.get("VPOS") is not None:
            clamped += _shift_box(el, dx, dy, w, h)
        for attr in ("POINTS", "BASELINE"):
            raw = el.get(attr)
            if raw:
                moved, n = _shift_pairs(raw, dx, dy, w, h)
                el.set(attr, moved)
                clamped += n
    # The page box is *set* from the manifest, never translated: it is a statement
    # about the new raster's size, which is a fact and not a moved coordinate.
    for el in tree.iter():
        tag = etree.QName(el).localname
        if tag == "Page":
            el.set("WIDTH", _fmt(w, el.get("WIDTH") or "0"))
            el.set("HEIGHT", _fmt(h, el.get("HEIGHT") or "0"))
        elif tag == "PrintSpace":
            el.set("HPOS", _fmt(0, el.get("HPOS") or "0"))
            el.set("VPOS", _fmt(0, el.get("VPOS") or "0"))
            el.set("WIDTH", _fmt(w, el.get("WIDTH") or "0"))
            el.set("HEIGHT", _fmt(h, el.get("HEIGHT") or "0"))
    return {"clamped": clamped}


def page_box(tree) -> tuple[int, int]:
    page = tree.find(".//{*}Page")
    if page is None:
        return (0, 0)
    try:
        return (int(float(page.get("WIDTH"))), int(float(page.get("HEIGHT"))))
    except (TypeError, ValueError):
        return (0, 0)


def migrate_file(path: Path, step: dict, commit: bool) -> dict:
    """One ALTO, from one manifest's space into another's.

    `step` is one entry of `plan`: the page box either side, the shift between them,
    and whether the two are related by a scale. Reports rather than raises; the
    caller decides what gates.
    """
    ref = norm_ref(path.stem)
    rec = {"ref": ref, "path": str(path), "action": "", "clamped": 0, "why": ""}
    try:
        tree = etree.parse(str(path))
    except etree.XMLSyntaxError as e:
        rec["action"] = "ABORTED"
        rec["why"] = f"unparseable: {e}"
        return rec

    box = page_box(tree)
    # **Where the two spaces are the same size and the shift is not zero, the page
    # box cannot say which of them this file is in**, and neither can anything else
    # in the file. Refused, because both of the available guesses are wrong: calling
    # it "already" leaves every coordinate on the page unmoved and silently stale,
    # and calling it "source" shifts a page that may already have been shifted. This
    # is part 2's hazard — 2550x3525 before and after — arriving on a page that
    # actually has to move, which the render->master migration never faced because
    # every page that moved also changed size.
    if step["from"] == step["to"] and step["shift"] != (0, 0):
        rec["action"] = "ABORTED"
        rec["why"] = (f"page box {box[0]}x{box[1]} is both the source and the "
                      f"target size, and the shift is {step['shift']}: no box can "
                      "say which side of it this file is on")
        return rec
    if box == step["to"]:
        rec["action"] = "already"
        return rec
    if box != step["from"]:
        # Neither space. Refused rather than translated on the assumption that it
        # must have been the old one — that assumption is how a store ends up
        # shifted twice.
        rec["action"] = "ABORTED"
        rec["why"] = (f"page box {box[0]}x{box[1]} is neither the source "
                      f"{step['from']} nor the target {step['to']}")
        return rec

    # **Where the two spaces differ by a scale, a translation is the wrong
    # operation.** The three masterless RGB leaves are one 150 ppi photograph each,
    # where the legacy render doubled them; moving a coordinate between those spaces
    # would need a ratio, which this module does not do and should not start doing
    # for three pages. All three are fully exempt and hold no coordinate at all, so
    # setting the page box and shifting nothing is exactly right — but that is a
    # fact about this corpus, checked here rather than relied upon.
    # `Page` and `PrintSpace` are excluded for `structural_digest`'s reason, and
    # this is the second time that distinction has had to be made: they *state* the
    # raster's size rather than describe a box on it, so `PrintSpace/@HPOS` is not
    # a coordinate and counting it made all three abort as "carries coordinates".
    if step.get("scaled") and any(
            etree.QName(el).localname not in ("Page", "PrintSpace")
            and (el.get("HPOS") is not None or el.get("POINTS") is not None
                 or el.get("BASELINE") is not None)
            for el in tree.iter()):
        rec["action"] = "ABORTED"
        rec["why"] = ("masterless page carries coordinates; the two spaces "
                      "differ by a scale and this migration only translates")
        return rec

    before = (text_digest(tree), structural_digest(tree))
    out = migrate_tree(tree, step["shift"][0], step["shift"][1], step["to"])
    after = (text_digest(tree), structural_digest(tree))
    if before != after:
        rec["action"] = "ABORTED"
        rec["why"] = ("content or structure changed: "
                      + ("text" if before[0] != after[0] else "structure"))
        return rec

    rec["clamped"] = out["clamped"]
    rec["action"] = "migrated"
    if commit:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tree.write(str(tmp), xml_declaration=True, encoding="UTF-8",
                   standalone=None)
        tmp.replace(path)
    return rec


def _alto_files(root: Path, store: str) -> list[Path]:
    d = root / store
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("chukchi-*.xml")):
        # The guard `migrate_coords.py` grew after a stray METS manifest in the
        # figure store nearly got rewritten.
        if b"alto" in p.read_bytes()[:2048].lower():
            out.append(p)
    return out


def migrate_bands(root: Path, shifts_by_ref: dict, commit: bool) -> list[dict]:
    """The `{y0, y1}` ledgers, which record no page box and so cannot self-check.

    Their `note` prose quotes pixel measurements — "indent 170 px against the
    book's 107-110, on a 695 px ink run" — and those are **left exactly as
    written** and reported instead. A width in that prose is still true; a y is
    not, and rewriting a human's note to keep an arithmetic claim tidy would be
    editing the record to match the code.
    """
    out = []
    for rel in BAND_FILES:
        p = root / rel
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out.append({"path": rel, "action": "ABORTED", "bands": 0,
                        "why": "unparseable", "notes_with_px": []})
            continue
        moved, notes = 0, []
        for ref, bands in data.items():
            if ref.startswith("_") or not isinstance(bands, list):
                continue
            dy = (shifts_by_ref.get(norm_ref(ref)) or (0, 0))[1]
            for b in bands:
                if not isinstance(b, dict):
                    continue
                if dy:
                    for k in ("y0", "y1"):
                        if isinstance(b.get(k), (int, float)):
                            b[k] = max(0, b[k] - dy)
                    moved += 1
                if "px" in str(b.get("note", "")):
                    notes.append(f"{ref}: {b.get('note', '')[:60]}")
        out.append({"path": rel, "action": "migrated" if moved else "already",
                    "bands": moved, "why": "", "notes_with_px": notes})
        if commit and moved:
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            tmp.replace(p)
    return out


def receipt_path(root: Path) -> Path:
    return root / "data" / RECEIPT


def read_receipt(root: Path) -> dict:
    p = receipt_path(root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run(root: Path = Path("."), stores: tuple[str, ...] = STORES,
        refs: list[str] | None = None, commit: bool = False,
        old: dict | None = None, new: dict | None = None) -> dict:
    """Translate every store from one manifest's space into another's.

    **The default pair is the historical one** — the legacy render space into the
    committed manifest's masters — so the corpus's one real migration is this
    function with its arguments left out. `scans swap` passes the pair explicitly:
    the committed manifest as `old`, the cut tree's as `new`. One code path, and the
    special case is a default rather than a branch.
    """
    manifest = pdf_images(root) if new is None else new
    if not manifest:
        return {"error": f"no {PDF_IMAGES}; run `harness scans extract --all "
                         "--commit`",
                "files": [], "bands": [], "dropped": [], "receipt": ""}
    source = render_space(manifest) if old is None else old
    steps = plan(source, manifest)
    want = {norm_ref(r) for r in refs} if refs else None

    files, corr_pages = [], []
    for store in stores:
        for p in _alto_files(root, store):
            ref = norm_ref(p.stem)
            if want is not None and ref not in want:
                continue
            if ref not in steps:
                files.append({"ref": ref, "path": str(p), "action": "ABORTED",
                              "clamped": 0, "why": "no manifest entry"})
                continue
            rec = migrate_file(p, steps[ref], commit)
            rec["store"] = store
            files.append(rec)
            if store == "gt/lines" and rec["action"] == "migrated":
                corr_pages.append(ref)

    sh = {ref: s["shift"] for ref, s in steps.items()}
    bands = migrate_bands(root, sh, commit)

    dropped = []
    for rel in DROP_FILES:
        p = root / rel
        if p.exists():
            dropped.append(rel)
            if commit:
                p.unlink()

    moved = [f for f in files if f["action"] == "migrated"]
    aborted = [f for f in files if f["action"] == "ABORTED"]
    rec_path = ""
    if commit and not aborted:
        doc = read_receipt(root)
        doc.setdefault("_about", (
            "Which manifest's space each page's stored coordinates are in, and the "
            "shift that put them there. A page whose shift is [0, 0] is recorded "
            "rather than omitted — the whole point is that 'correctly untouched' "
            "and 'not yet reached' must be distinguishable, and page dimensions "
            "cannot tell them apart."))
        for f in files:
            if f["action"] in ("migrated", "already"):
                doc[f["ref"]] = {"shift": list(steps[f["ref"]]["shift"]),
                                 "size": list(steps[f["ref"]]["to"])}
        p = receipt_path(root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        rec_path = str(p)

    return {
        "files": files,
        "migrated": len(moved),
        "already": sum(1 for f in files if f["action"] == "already"),
        "aborted": len(aborted),
        "clamped": sum(f["clamped"] for f in files),
        # **Clamping in `gt/` is a different event from clamping in `mz/`.** A
        # machine prediction pulled back to the page edge is noise in a store that
        # `zones predict --force` rewrites; a *human's* box losing pixels is a
        # keyed judgement being altered by a migration, and wants looking at before
        # anything is written. On this corpus the count is 24 and 0. Reporting one
        # number would have made those indistinguishable.
        "clamped_gt": sum(f["clamped"] for f in files
                          if f.get("store", "").startswith("gt/")),
        "bands": bands,
        "dropped": dropped,
        # `gt/lines/` ids encode the y they were made at and are deliberately not
        # re-minted. Named so the divergence is on the record.
        "correction_pages_with_y_in_ids": sorted(set(corr_pages),
                                                 key=parse_ref),
        "receipt": rec_path,
    }
