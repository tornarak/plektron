#!/usr/bin/env python3
"""Rescale ALTO geometry to match re-rendered scans. Text is never touched.

`scans/` was rendered at 150 dpi; the PDFs carry a ~300 dpi bitonal master, so
the rasters are re-rendered and every coordinate in the ALTO tree has to follow.

SCALE BY MEASURED RATIO, NOT BY 2. The new rasters are *almost* double: across
all 832 pages, 205 come out one pixel short on width and 627 one pixel short on
height, and not one page is exactly 2x. Doubling literally would push a
right-edge or bottom-edge coordinate past the page box on every page in the
corpus. The ratio is therefore taken per page, per axis, from the two rasters —
never from `2`, and never from `ceil(pt/72*dpi)` either, which looks like it
reproduces poppler but computes 667.44/72*300 as 2781.0000000000005 and predicts
2782 where poppler renders 2781.

Attribute number formatting is preserved: eScriptorium writes `Page/@WIDTH` as
`"1412"` but `TextBlock/@HPOS` as `"365.0"`, and a diff full of gratuitous
`1412` -> `1412.0` churn would bury the changes that matter.

HISTORICAL. This has run; `fig/` and `ocr/` are already in 300 dpi space (`1-116`
is 2824x3897 in both the ALTO and the raster). It is kept because the reasoning
above is the reasoning any future re-render needs, and because re-running it on
already-migrated files would scale them a second time. Check a Page/@WIDTH
against its raster before pointing this at anything.
"""
from __future__ import annotations
import argparse, hashlib, sys, tarfile, time
from pathlib import Path
from lxml import etree

DIRS = ("fig", "ocr", "gt/ocr", "gt/seg")

# Attributes carrying an x-coordinate or a width, and a y-coordinate or height.
X_ATTRS = ("HPOS", "WIDTH")
Y_ATTRS = ("VPOS", "HEIGHT")


def _fmt(value: float, source: str) -> str:
    """Scale a number back into the spelling its source used."""
    if "." in source:
        return f"{value:.1f}"
    return str(int(round(value)))


def _scale_pairs(raw: str, sx: float, sy: float, w: int, h: int) -> str:
    """`POINTS`/`BASELINE`: whitespace-separated alternating x y."""
    toks = raw.split()
    out = []
    for i, t in enumerate(toks):
        try:
            v = float(t)
        except ValueError:
            out.append(t)
            continue
        if i % 2 == 0:
            v = min(max(v * sx, 0.0), w)
        else:
            v = min(max(v * sy, 0.0), h)
        out.append(_fmt(v, t))
    return " ".join(out)


def _scale_box(el, sx: float, sy: float, w: int, h: int) -> None:
    """HPOS/VPOS/WIDTH/HEIGHT, clamped so the box stays inside the page."""
    for attr in X_ATTRS + Y_ATTRS:
        raw = el.get(attr)
        if raw is None:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        el.set(attr, _fmt(v * (sx if attr in X_ATTRS else sy), raw))
    # Clamp after scaling, so an origin+extent that lands outside the new page
    # is pulled back rather than left to fail validation downstream.
    for pos, ext, limit in (("HPOS", "WIDTH", w), ("VPOS", "HEIGHT", h)):
        p_raw, e_raw = el.get(pos), el.get(ext)
        if p_raw is None or e_raw is None:
            continue
        p, e = float(p_raw), float(e_raw)
        if p < 0:
            p = 0.0
        if p > limit:
            p = float(limit)
        if p + e > limit:
            e = limit - p
        el.set(pos, _fmt(p, p_raw))
        el.set(ext, _fmt(e, e_raw))


def content_digest(root) -> str:
    """Hash of every String/@CONTENT in document order — the text-integrity gate."""
    h = hashlib.sha256()
    for s in root.iter("{*}String"):
        h.update((s.get("CONTENT") or "").encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def migrate_file(path: Path, scans: Path) -> dict:
    tree = etree.parse(str(path))
    root = tree.getroot()

    page = root.find(".//{*}Page")
    if page is None:
        return {"path": str(path), "status": "skipped: no Page element"}

    name = root.findtext(".//{*}fileName")
    if not name:
        return {"path": str(path), "status": "skipped: no sourceImageInformation/fileName"}
    img = scans / name
    if not img.exists():
        return {"path": str(path), "status": f"skipped: {img} missing"}

    from PIL import Image
    new_w, new_h = Image.open(img).size
    old_w, old_h = int(float(page.get("WIDTH"))), int(float(page.get("HEIGHT")))
    if (old_w, old_h) == (new_w, new_h):
        return {"path": str(path), "status": "already at target size"}

    sx, sy = new_w / old_w, new_h / old_h
    before = content_digest(root)

    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        local = etree.QName(el).localname
        if local == "Polygon" and el.get("POINTS"):
            el.set("POINTS", _scale_pairs(el.get("POINTS"), sx, sy, new_w, new_h))
            continue
        if el.get("BASELINE"):
            el.set("BASELINE", _scale_pairs(el.get("BASELINE"), sx, sy, new_w, new_h))
        if el.get("HPOS") is not None or el.get("WIDTH") is not None:
            _scale_box(el, sx, sy, new_w, new_h)

    # The page box is set from the raster, not from the scaled arithmetic: the
    # ratio is derived from these numbers, so rounding must not drift them.
    page.set("WIDTH", _fmt(new_w, page.get("WIDTH")))
    page.set("HEIGHT", _fmt(new_h, page.get("HEIGHT")))
    ps = root.find(".//{*}PrintSpace")
    if ps is not None and ps.get("WIDTH") is not None:
        _scale_box(ps, 1.0, 1.0, new_w, new_h)

    after = content_digest(root)
    if before != after:
        return {"path": str(path), "status": "ABORTED: String/@CONTENT changed"}

    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=None)
    return {"path": str(path), "status": "ok",
            "from": f"{old_w}x{old_h}", "to": f"{new_w}x{new_h}",
            "sx": round(sx, 6), "sy": round(sy, 6)}


def alto_files(root: Path) -> list[Path]:
    out = []
    for d in DIRS:
        for p in sorted((root / d).glob("*.xml")):
            # Guard against non-ALTO XML sharing the directory: an earlier
            # eScriptorium export dropped a METS manifest into fig/, which a
            # bare *.xml glob would have happily rewritten.
            head = p.read_bytes()[:2048]
            if b"alto" not in head.lower():
                continue
            out.append(p)
    return out


def backup(files: list[Path], dest: Path) -> Path:
    with tarfile.open(dest, "w:gz") as tar:
        for f in files:
            tar.add(f, arcname=str(f))
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--scans", type=Path, default=None,
                    help="raster directory to scale against (default <root>/scans)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()

    scans = a.scans or (a.root / "scans")
    files = alto_files(a.root)
    print(f"{len(files)} ALTO files across {', '.join(DIRS)}")

    if a.dry_run:
        from PIL import Image
        for p in files[:5]:
            root = etree.parse(str(p)).getroot()
            page = root.find(".//{*}Page")
            img = scans / root.findtext(".//{*}fileName")
            print(f"  {p}: {page.get('WIDTH')}x{page.get('HEIGHT')} -> "
                  f"{Image.open(img).size if img.exists() else 'MISSING'}")
        return 0

    if not a.no_backup:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        tar = backup(files, a.root / f"alto-backup-{stamp}.tar.gz")
        print(f"backup: {tar} ({tar.stat().st_size/1e6:.1f} MB)")

    counts, failures = {}, []
    for p in files:
        r = migrate_file(p, scans)
        key = r["status"] if r["status"] in ("ok",) else r["status"].split(":")[0]
        counts[key] = counts.get(key, 0) + 1
        if r["status"] != "ok":
            failures.append(r)
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    for f in failures[:20]:
        print(f"  ! {f['path']}: {f['status']}")
    return 1 if any(f["status"].startswith("ABORTED") for f in failures) else 0


if __name__ == "__main__":
    sys.exit(main())
