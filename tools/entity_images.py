#!/usr/bin/env python3
"""Fetch each entity's picture — which Commons file, and what the card owes it —
into `edition/entity-images.json`.

**The picture is Wikidata's P18 for the item the entry already names.** No
search, no match: the identification is the human's `link: wikidata:Q…`, made
and checked by `identify.py` or `gazetteer.py` and a person, and P18 follows
from it mechanically. That makes the pick a rule's, `#mz` — nobody here has
looked at it — and the card says "via Wikidata" so a reader can tell. An editor
who has looked and disagrees writes `image: commons:<file>` in the entry, which
this fetches the same way, or `image: none`, which it skips.

**Several P18 claims are resolved by rank and then by order, and the report
says so.** A preferred claim beats a normal one and a deprecated one is never
taken; among equals the first wins and the row reads `of N`. That is not a
judgement about which picture is better, and it is not meant to look like one —
`of N` is the row a human should open.

**The licence is checked before a row is written** (`pictures.LICENCE`): public
domain, CC0, CC BY, CC BY-SA, copyrighted free use. A file outside that is reported and left off, and
its P18 with it, so the card shows nothing rather than a picture it cannot
attribute. The author comes out of Commons' `Artist` field, which is HTML, as
plain text.

**A failed lookup keeps the row it had.** `gazetteer.py` learned this twice: an
outage that reads as "no picture" deletes a true row on the strength of a
timeout. So a failed chunk marks its rows `!` and carries the prior ledger
through unchanged, and nothing is dropped that was not positively answered.

The bytes are never fetched — the card hotlinks the thumbnail — so what changes
on Commons after this runs is served before this knows. Re-running reports it:
`~` is a file, sha1 or licence that moved.

Wikidata and Commons are live, so this is a `tools/` script and not a harness
verb, the split `gazetteer.py` and `identify.py` sit on. Run it in the project
environment (`uv run python tools/entity_images.py`), whose `lxml` and
`requests` it uses.

    tools/entity_images.py               report: what would change, and why
    tools/entity_images.py --commit      write the ledger
"""
from __future__ import annotations

import argparse
import datetime
import sys
import unicodedata
from pathlib import Path

from lxml import html as lhtml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import pictures  # noqa: E402
from harness.atomic import write_atomic  # noqa: E402
from harness.entities import load  # noqa: E402
from tools.gazetteer import _get, entities  # noqa: E402

COMMONS = "https://commons.wikimedia.org/w/api.php"

#: The thumbnail width asked for. **One of Wikimedia's standard steps**, which
#: its thumbnailer serves from cache; an arbitrary width is a fresh render per
#: reader at best. The card caps the display width below this anyway.
WIDTH = 330

_META = "LicenseShortName|LicenseUrl|Artist|AttributionRequired"


def choose(claims: list[tuple[str, str]]) -> tuple[str, int]:
    """(file, how many it was chosen among). Preferred, else normal; never
    deprecated; first among equals."""
    live = [(r, f) for r, f in claims if r != "deprecated"]
    pool = [f for r, f in live if r == "preferred"] or [f for _, f in live]
    return (pool[0] if pool else ""), len(pool)


def text_of(fragment: str) -> str:
    """Commons' HTML credit as one line of text. Empty in, empty out."""
    if not fragment.strip():
        return ""
    el = lhtml.fragment_fromstring(fragment, create_parent="div")
    return " ".join(el.text_content().split())


def row_of(ii: dict, today: str) -> dict:
    """One `imageinfo` result → a ledger row, in `pictures.FILE_FIELDS` order."""
    em = ii.get("extmetadata") or {}

    def meta(k: str) -> str:
        return str((em.get(k) or {}).get("value", ""))

    return {
        "page": ii["descriptionurl"],
        "thumb": ii.get("thumburl") or ii["url"],
        "width": ii.get("thumbwidth") or ii["width"],
        "height": ii.get("thumbheight") or ii["height"],
        "sha1": ii["sha1"],
        "licence": text_of(meta("LicenseShortName")),
        "licence_url": meta("LicenseUrl"),
        "artist": text_of(meta("Artist")),
        "attribution_required": meta("AttributionRequired") == "true",
        "retrieved": today,
    }


def imageinfo(keys: list[str], today: str, get=_get) -> dict[str, dict]:
    """Ledger key → `{"row": …}`, `{"missing": True}` or `{"failed": why}`.

    Fifty titles a call, the API's limit. Titles go out NFC, which is what
    MediaWiki stores; the answer is mapped back through the API's own
    `normalized` and `redirects` lists rather than by re-spelling it here, so a
    title the server folded differently from `file_key` still finds its row.
    """
    out: dict[str, dict] = {}
    for i in range(0, len(keys), 50):
        chunk = keys[i:i + 50]
        asked = {"File:" + unicodedata.normalize("NFC", k): k for k in chunk}
        try:
            r = get({"action": "query", "prop": "imageinfo", "redirects": 1,
                     "titles": "|".join(asked),
                     "iiprop": "url|sha1|size|extmetadata",
                     "iiurlwidth": WIDTH, "iiextmetadatafilter": _META},
                    api=COMMONS)
        except Exception as e:                            # noqa: BLE001
            print(f"  ! imageinfo {chunk[0]}…: {e}", file=sys.stderr)
            out.update({k: {"failed": str(e)} for k in chunk})
            continue
        q = r.get("query") or {}
        hop = {m["from"]: m["to"]
               for m in (q.get("normalized") or []) + (q.get("redirects") or [])}
        pages = {p["title"]: p for p in (q.get("pages") or {}).values()}
        for title, k in asked.items():
            seen = set()
            while title in hop and title not in seen:
                seen.add(title)
                title = hop[title]
            p = pages.get(title)
            if p is None or "missing" in p or not p.get("imageinfo"):
                out[k] = {"missing": True}
            else:
                out[k] = {"row": row_of(p["imageinfo"][0], today)}
    return out


def sweep(store: dict, prior: dict, items: dict, info: dict) -> tuple[dict, list[dict]]:
    """The new ledger, and one report row per entry it touches. No network.

    `items` is `gazetteer.entities` over the QIDs; `info` is `imageinfo` over
    the files. Split from the fetching so the whole decision — rank, licence,
    what a failure keeps — is testable on canned answers.
    """
    p18: dict[str, str] = {}
    chosen: dict[str, str] = {}      # the pick, before any refusal drops it
    notes: dict[str, str] = {}
    failed: set[str] = set()
    for rec in store.values():
        q = pictures.qid(rec)
        if rec["class"] not in pictures.IMAGE_CLASSES or rec["image"] or not q:
            continue
        got = items.get(q)
        if got is None:
            notes[q] = "item not found"
        elif "failed" in got:
            failed.add(q)
            if q in prior["p18"]:
                p18[q] = prior["p18"][q]
        else:
            f, n = choose(got["p18"])
            if f:
                p18[q] = chosen[q] = pictures.file_key(f)
                if n > 1:
                    notes[q] = f"of {n}"
            else:
                notes[q] = "no P18"

    files: dict[str, dict] = {}
    refused: dict[str, str] = {}
    for k, got in info.items():
        if "failed" in got:
            failed.add(k)
            if k in prior["files"]:
                files[k] = prior["files"][k]
        elif "missing" in got:
            refused[k] = "not on Commons"
        elif not pictures.licence_ok(got["row"]["licence"]):
            refused[k] = f"licence {got['row']['licence']!r} refused"
        else:
            row, was = got["row"], prior["files"].get(k)
            # `retrieved` moves only with the row, so a re-run over an unchanged
            # Commons is an unchanged file.
            if was and {**was, "retrieved": ""} == {**row, "retrieved": ""}:
                row = was
            files[k] = row
    # A P18 kept through a failed item lookup was never asked of Commons, so
    # its file row comes through with it.
    for q in failed & set(p18):
        f = p18[q]
        if f not in info and f in prior["files"]:
            files[f] = prior["files"][f]
    # A P18 whose file was refused goes too: a QID pointing at no row is an
    # `entity check` error, and the card would have nothing to show anyway.
    p18 = {q: f for q, f in p18.items() if f in files}
    new = {"p18": p18, "files": files}

    rows = []
    for rec in sorted(store.values(), key=lambda r: r["id"]):
        if rec["class"] not in pictures.IMAGE_CLASSES or rec["image"] == "none":
            continue
        q = pictures.qid(rec)
        if not (q or rec["image"]):
            continue
        override = rec["image"][8:]
        key = override or chosen.get(q) or p18.get(q, "")
        a, b = pictures.resolve(rec, prior), pictures.resolve(rec, new)
        if (q in failed and not override) or key in failed:
            mark = "!"
        elif not a and b:
            mark = "+"
        elif a and not b:
            mark = "-"
        elif a and b and any(a[k] != b[k] for k in ("file", "sha1", "licence")):
            mark = "~"
        elif b:
            mark = "="
        else:
            mark = " "
        note = refused.get(key) or ("" if override else notes.get(q, ""))
        rows.append({"mark": mark, "id": rec["id"], "file": key,
                     "licence": (b or {}).get("licence", ""), "note": note,
                     "wikipedia": any(ln.startswith("wikipedia:")
                                      for ln in rec["links"])})
    return new, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--commit", action="store_true",
                    help="write edition/entity-images.json")
    a = ap.parse_args(argv)

    store = load(a.root)
    prior = pictures.load(a.root)
    today = datetime.date.today().isoformat()
    qids = sorted({pictures.qid(r) for r in store.values()
                   if r["class"] in pictures.IMAGE_CLASSES
                   and not r["image"] and pictures.qid(r)})
    print(f"  {len(qids)} items on Wikidata …", file=sys.stderr)
    items = entities(qids)
    keys = {pictures.file_key(choose(v["p18"])[0])
            for v in items.values() if "failed" not in v and choose(v["p18"])[0]}
    keys |= {r["image"][8:] for r in store.values()
             if r["image"].startswith("commons:")
             and r["class"] in pictures.IMAGE_CLASSES}
    print(f"  {len(keys)} files on Commons …", file=sys.stderr)
    info = imageinfo(sorted(keys), today)
    new, rows = sweep(store, prior, items, info)

    for r in rows:
        if r["mark"] == " " and not r["note"]:
            continue
        print(f"{r['mark']} {r['id']:<40} {r['file'][:60]:<60} "
              f"{r['licence']:<14} {r['note']}")
    tally = {m: sum(1 for r in rows if r["mark"] == m) for m in "+~-=!"}
    no_p18_wp = sum(1 for r in rows if r["note"] == "no P18" and r["wikipedia"])
    print(f"\n{len(new['files'])} pictures · " + " ".join(
        f"{m}{n}" for m, n in tally.items() if n)
        + f" · no P18 but a Wikipedia article: {no_p18_wp}")
    if tally["!"]:
        print(f"{tally['!']} lookup(s) FAILED — their prior rows are kept, "
              f"nothing was dropped on their account", file=sys.stderr)
    if a.commit:
        write_atomic(a.root / pictures.LEDGER, pictures.dump(new))
        print(f"wrote {pictures.LEDGER}")
    else:
        print("report only; --commit writes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
