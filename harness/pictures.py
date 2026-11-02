"""An entity's picture: which one, from where, and under what licence.

**The bytes are Wikimedia's and stay there.** The card hotlinks a Commons
thumbnail; what the repository holds is `edition/entity-images.json`, the
ledger that says which file each picture is and what the reader must be told
about it — author, licence, the file's own page. That is the part an offline
card cannot fetch, so it is the part that is committed. It is derived but
tracked, beside `edition/geo/`, for `geo/`'s reason: its source is outside the
repo, and `tools/entity_images.py` is what writes it.

**Two ranks, and the card says which.** A picture reached through the entry's
own `link: wikidata:Q…` is Wikidata's P18 for that item — a rule applied to a
human's identification, `#mz` and no better, since nobody here looked at the
picture. An `image: commons:…` line in the entity file is an editor's choice and
overrides it; `image: none` is an editor's refusal and suppresses it.

**The ledger is keyed by Wikidata and by Commons, never by entity id.** An
identity changes under `entity rename`, and a class under a move between
`place:` and `land:`; a QID and a file title do not. Keyed by entity, the ledger
would be one more store `rename` had to rewrite, and the first rename that
forgot would orphan a picture with nothing to say so.

Imports only `layout`, which is above a leaf: `entities.check` and the card both
read it, and that keeps it out of any import cycle (`atomic.py` has the argument).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

from .layout import shared

LEDGER = "edition/entity-images.json"

#: The classes that get a picture. **Applied at render, from the entry's current
#: class**, so moving an entry out of scope takes its picture with it and no
#: ledger edit is needed. `being:` is a spirit or a disease filed under an
#: editorial reading — `iteˊyun` at *Trichinellosis* — so its item's picture
#: would illustrate the reading, not the being; `event:`, `institution:` and
#: `source:` have no picture that would say more than the name, and `animal:`
#: is a reindeer with a name and no item.
IMAGE_CLASSES = ("taxon", "person", "people", "place", "land", "water", "river",
                 "sky")

#: The licences a picture may carry, as Commons spells `LicenseShortName`.
#: Public domain, CC0, CC BY / CC BY-SA at any version and port, and Commons'
#: "Copyrighted free use" — any use, attribution or none. **Everything
#: on Commons is free; this is narrower on purpose**, and the line is what the
#: card knows how to attribute: a figcaption naming the author and linking the
#: licence satisfies these and is not known to satisfy GFDL's
#: full-text requirement or a bespoke "Attribution" template. A refused file is
#: reported by the tool and simply absent from the card.
LICENCE = re.compile(
    r"^(?:public domain|pd(?:[- ].*)?|cc0(?: 1\.0)?|cc[- ]by(?:-sa)? \d\.\d(?: [a-z-]+)?"
    r"|copyrighted free use)$",
    re.I)

#: One file's row. Closed, so a hand-edited row missing a field is a defect
#: `entity check` names rather than a card that renders "None".
FILE_FIELDS = ("page", "thumb", "width", "height", "sha1", "licence",
               "licence_url", "artist", "attribution_required", "retrieved")

#: The width the lightbox asks for. **Through `Special:FilePath`, not a thumb
#: URL**: the ledger holds the card's 330px rendition and not the original's
#: size, and a thumb wider than its source is an error where `FilePath` serves
#: the original instead. A standard step, for `tools/entity_images.py`'s reason.
LIGHTBOX = 1920
_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

#: `image:`'s two forms. A title, never a URL — `link:`'s rule, for its reason:
#: the store holds the identifier and the card holds the address.
_IMAGE = re.compile(r"^commons:(?!File:)([^/|#<>\[\]{}]+\.[A-Za-z0-9]+)$")


def licence_ok(name: str) -> bool:
    return bool(LICENCE.match(name.strip()))


def file_key(title: str) -> str:
    """A Commons title as the ledger keys it: NFD, underscores, first letter up.

    MediaWiki folds all three — `Canis lupus.jpg` and `canis_lupus.jpg` are one
    file — and the API hands back spaces where an editor will usually have
    pasted underscores from a URL. Keyed raw, the two spellings of one file
    would be two ledger rows, and an override would read "awaiting fetch" for a
    file that had been fetched. NFD because `edition/*.json` is inside
    `corpus normalize`'s scope; the tool turns it back into NFC for the API.
    """
    t = unicodedata.normalize("NFD", title.strip()).replace(" ", "_")
    if t[:5].lower() == "file:":
        t = t[5:]
    return t[:1].upper() + t[1:]


def image_value(raw: str) -> str:
    """An `image:` field's value, checked. Raises ValueError with the reason."""
    if raw == "none":
        return raw
    m = _IMAGE.match(raw)
    if not m:
        raise ValueError(
            f"`image: {raw}` — `commons:<file title>` (no `File:`, not a URL) "
            f"or `none`")
    return f"commons:{file_key(m.group(1))}"


def qid(rec: dict) -> str:
    """The entry's Wikidata item, or "". The first `link: wikidata:` row."""
    for ln in rec["links"]:
        kind, _, rest = ln.partition(":")
        if kind == "wikidata":
            return rest.strip()
    return ""


def load(root: Path = Path(".")) -> dict:
    """The ledger. **Absent is empty**: before the tool's first run there are no
    pictures, and the card showing none is that fact, not a hidden one."""
    p = shared(root, LEDGER)
    if not p.exists():
        return {"p18": {}, "files": {}}
    got = json.loads(p.read_text(encoding="utf-8"))
    return {"p18": got.get("p18", {}), "files": got.get("files", {})}


def dump(ledger: dict) -> str:
    """The ledger as written: sorted, two-space, one field per line — the shape
    `corpus normalize` reads JSON in."""
    out = {"p18": dict(sorted(ledger["p18"].items())),
           "files": {k: ledger["files"][k] for k in sorted(ledger["files"])}}
    return unicodedata.normalize(
        "NFD", json.dumps(out, ensure_ascii=False, indent=2)) + "\n"


def resolve(rec: dict, ledger: dict) -> dict | None:
    """The picture an entry shows, or None.

    Precedence is the two ranks: an editor's `image:` line beats the rule, and
    `none` beats both. The class is read here and nowhere earlier, which is what
    makes the scope follow the entry.
    """
    if rec["class"] not in IMAGE_CLASSES or rec["image"] == "none":
        return None
    if rec["image"]:
        f, source = rec["image"].removeprefix("commons:"), "editor"
    else:
        f, source = ledger["p18"].get(qid(rec), ""), "wikidata:P18"
    row = ledger["files"].get(f)
    if not row:
        return None
    full = f"{_FILEPATH}{quote(unicodedata.normalize('NFC', f))}?width={LIGHTBOX}"
    return {**row, "file": f, "source": source, "full": full}


def audit(store: dict, ledger: dict) -> tuple[list[str], list[dict]]:
    """`entity check`'s half for pictures: (errors, rows to report).

    **The licence gate here is one witness, not two.** The tool refused the same
    licences by the same pattern before it wrote, so this re-check catches a
    hand-edited row, or a pattern narrowed after a fetch, and nothing else.

    What no offline check can see is Commons itself: a file overwritten after
    the fetch is served new under the old attribution until the tool re-runs
    and reports it changed. Hotlinking cannot pin a version.
    """
    errors: list[str] = []
    rows: list[dict] = []
    for rec in store.values():
        if rec["image"] and rec["class"] not in IMAGE_CLASSES:
            errors.append(
                f"{rec['path']}: `image: {rec['image']}` on a `{rec['class']}:` "
                f"entry. Pictures are for {', '.join(IMAGE_CLASSES)}")
        elif rec["image"].startswith("commons:") \
                and rec["image"][8:] not in ledger["files"]:
            rows.append({"id": rec["id"], "file": rec["image"][8:],
                         "state": "awaiting fetch"})
    for q, f in sorted(ledger["p18"].items()):
        if f not in ledger["files"]:
            errors.append(f"{LEDGER}: p18 {q} names {f!r}, which has no files row")
    for f, row in sorted(ledger["files"].items()):
        missing = [k for k in FILE_FIELDS if k not in row]
        if missing:
            errors.append(f"{LEDGER}: {f!r} lacks {', '.join(missing)}")
        elif not licence_ok(row["licence"]):
            errors.append(
                f"{LEDGER}: {f!r} is {row['licence']!r}, outside the licences "
                f"the card can attribute (pictures.LICENCE)")
    # Orphans are reported and gate nothing: a row nothing reaches renders
    # nowhere, and the tool's next run drops it.
    linked = {qid(r) for r in store.values()
              if r["class"] in IMAGE_CLASSES and not r["image"]}
    reached = {ledger["p18"][q] for q in linked if q in ledger["p18"]} \
        | {r["image"][8:] for r in store.values()
           if r["image"].startswith("commons:")}
    rows += [{"id": q, "file": f, "state": "orphaned p18"}
             for q, f in sorted(ledger["p18"].items()) if q not in linked]
    rows += [{"id": "", "file": f, "state": "orphaned file"}
             for f in sorted(ledger["files"]) if f not in reached]
    return errors, rows
