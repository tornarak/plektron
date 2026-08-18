"""The reading view — collated TEI, the encyclopedia, and the scan, in a browser.

**The first surface in this project aimed at a reader**, and the second thing it
is for is auditing, which is why both live in one page behind a toggle rather
than in two renderers that could drift.

The layout is two columns: the text, and beside it a **map pane** over a **stack**
of cards. A click on an entity link or the scan button pushes a card to the top
of the stack; the stack keeps what you have opened, in the order you opened it,
and a pinned card stays above the rest. It is what makes an annotated edition
readable at all: what you consulted stays consulted, and a footnote never costs
you your place. A map is not a card — there is only ever one *here*, so it is the
pane; what it holds is a *selection*, and clicking a place adds it, with the tree
beneath naming what contains them all.

**It writes to `entities/`, and the click is the human act.** That is the
`zones edit` precedent, not a new licence: a loopback server, a tracked store, and
git as the witness. Ratifying an entry here is the same act as
`harness entity ratify --commit`, done where the evidence is — the entry beside
its attestations and the pages it was read from. Every write runs `entity check`
on the result first and refuses one that would leave the store incoherent.

Committed `tei/` only. `mz/tei/` is a generated baseline nobody has read, and an
end-user preview is the last place it belongs.

**This module no longer renders a page.** The routes and every piece of markup
are `harness/web/edition.py` and the templates beside it. What stays is what a
different front end would still need: the little markup a gloss may use, what an
imputed pronunciation is allowed to claim, which fields of a record must reach a
reader, and the two guarded writes — each of which is a rule about the edition
rather than about HTTP.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

from . import geo, geomap
from .cli._entity import TEMPLATE
from .context import norm_ref
from .entities import (
    GEO_CLASSES,
    WIKILINK,
    check,
    load,
    path_for,
    split_id,
    tree_parent,
)

PORT = 8734
REF_OK = re.compile(r"^\d+-\d+$")

#: Where the reading view is mounted. The four tools share one server, so a bare
#: `/entity/…` in a link would resolve against whichever of them owned the root.
#: A constant rather than a per-request value because the mount point is fixed
#: at registration (`harness/web/edition.py`), and threading a request through
#: `gloss_html` to reach it would put a web concern inside a text transform.
BASE = "/edition"


def scan_for(ref: str, root: Path) -> Path:
    return root / "scans" / f"chukchi-{norm_ref(ref)}.png"


#: Where an editor's own version of a whole leaf lives, and the extensions it may
#: take, **vector first**. `1-361`, part 1's foldout map, is the leaf this exists
#: for and it may end up an SVG; a resolver that assumed a raster would have to be
#: rewritten the day it did.
PAGE_IMG = "gt/page-img"
LEAF_MEDIA = {".svg": "image/svg+xml", ".png": "image/png",
              ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
LEAF_EXTS = tuple(LEAF_MEDIA)


def leaf_source(ref: str, root: Path) -> tuple[Path | None, str]:
    """An editor's version of this leaf, or nothing. `(path, rank)`.

    `figures.crop_source`'s doctrine one level up — *"an enhanced figure is a new
    artefact somebody made and vouches for"* — for a whole leaf rather than a
    crop, and `tei_html.page_source`'s rule that the rank travels with the answer
    so no caller can hold the path without knowing whose it is.

    **Two boundaries, and both are the point.**

    It is *reading view only*: `zones.scan_for` is what the segmenters, the ink
    checks and `fig crops` resolve through, and it never consults this. An
    upscaled or sharpened leaf is manufactured evidence and must not reach
    anything that measures ink.

    It is *exempt only*. A file for a page the pipeline still owns is ignored
    here and reported by `edition runs`, rather than being honoured quietly the
    day somebody adds a branch.
    """
    from .zones import load_splits

    ref = norm_ref(ref)
    if load_splits(root).get(ref) != "exempt":
        return None, "scan"
    for ext in LEAF_EXTS:
        p = root / PAGE_IMG / f"chukchi-{ref}{ext}"
        if p.exists():
            return p, "ed"
    return None, "scan"


#: Where `tools/build_leaf_layers.py` writes what it derives from a master, and
#: what the two layers are called. Derived and gitignored, `mz/tei/`'s disposition:
#: a rule's output over a tracked store, rebuilt in one command.
PAGE_IMG_LAYERS = "mz/page-img"
LEAF_LAYERS = {"colour": ".colour.jpg", "lines": ".lines.png"}


def leaf_layers(ref: str, root: Path) -> dict[str, Path] | None:
    """The master split for delivery — `{"colour": …, "lines": …}` or nothing.

    A master is one artefact and this is the same artefact in two files, so the
    rank does not travel here the way `leaf_source`'s does: these are *derived
    from* the vouched-for leaf, and a caller that has them already knows an
    editor's leaf exists. `leaf_source` remains the authored file's own address.

    **Both or neither.** Half a Mixed Raster pair is not a degraded rendering of
    the leaf, it is a different picture — the colour layer alone is a blurred
    smear with no coastlines or names, and the linework alone is a bare outline
    with every ethnic area gone. Either would render without erroring and look
    like the map, which is the failure mode this project is built against, so a
    missing half falls back to the master rather than showing the survivor.
    """
    ref = norm_ref(ref)
    if leaf_source(ref, root)[0] is None:
        return None
    out = {name: root / PAGE_IMG_LAYERS / f"chukchi-{ref}{ext}"
           for name, ext in LEAF_LAYERS.items()}
    return out if all(p.exists() for p in out.values()) else None


# --------------------------------------------------------------- the page


def _raster_size(ref: str, root: Path) -> tuple[int, int]:
    """The scan's pixel size, or a plausible default if it is not on disk.

    `scans/` is derived and absent in a fresh clone, and the reading view should
    still render the text — the scan card simply has nothing to show. A default
    keeps the aspect ratio sane instead of collapsing the frame to zero.
    """
    try:
        from PIL import Image

        with Image.open(scan_for(ref, root)) as im:
            return im.size
    except Exception:
        return (2550, 3300)


# ------------------------------------------------------------- the entities

#: How a `link:` row renders. The prefix is the whole vocabulary — an entity
#: record says `wikipedia:Chukchi_people`, not a URL, so the store holds the
#: *identifier* and this holds the address. A site that moves its paths then
#: costs one line here rather than an edit to every record.
LINK_KINDS = {
    "wikipedia": ("https://en.wikipedia.org/wiki/{}", "Wikipedia", "wikipedia"),
    "wikidata": ("https://www.wikidata.org/wiki/{}", "Wikidata", "wikidata"),
    # The gazetteer that carries the small Siberian features Wikidata does not —
    # abandoned settlements, unnamed bays — and the identity a `geo:` derived by
    # `tools/gazetteer.py` was derived *from*. Without a row here that provenance
    # would be a number in a file nothing resolves.
    "geonames": ("https://www.geonames.org/{}", "GeoNames", ""),
    "dplace": ("https://d-place.org/parameters/{}", "D-PLACE", ""),
    "url": ("{}", "", ""),
}

#: Where a `geo:` point can be opened on somebody else's map. Same shape and same
#: argument as `LINK_KINDS`: the record holds the coordinate, this holds the
#: address, and a service that changes its query format costs one line here.
#:
#: **OpenStreetMap leads because it is the witness the store was built against** —
#: the place records say so in their own glosses ("cross-referenced against
#: Operational Navigation Charts and OpenStreetMap"), so the link a reader follows
#: to check a coordinate is the map the editor checked it on. The `mlat`/`mlon`
#: pair drops a marker at the point rather than merely centring there, which is
#: the difference between "this spot" and "somewhere in this view".
#:
#: **The zoom is deliberately low.** These are coordinates for vanished
#: settlements and unnamed bays, derived from a 1900s gazetteer against charts;
#: opening at street level would dress a ±1 km reading as a doorstep. z10 shows
#: the coast and the river mouth a reader needs to judge it by.
MAP_SERVICES = (
    ("OpenStreetMap",
     "https://www.openstreetmap.org/?mlat={lat:.4f}&mlon={lon:.4f}"
     "#map=10/{lat:.4f}/{lon:.4f}"),
    ("Google Maps",
     "https://www.google.com/maps/search/?api=1&query={lat:.4f},{lon:.4f}"),
)


def map_links(lat: float, lon: float) -> list[dict]:
    """`MAP_SERVICES` resolved against one coordinate, as `{name, url}` rows.

    Built here rather than in the template so the template keeps doing the one
    thing it is good at — escaping — and a service added above cannot arrive as
    markup. The `&` in a query string is escaped by Jinja on the way out, which is
    correct in an `href` and is why these are handed over as plain strings.
    """
    return [{"name": name, "url": url.format(lat=lat, lon=lon)}
            for name, url in MAP_SERVICES]


_STRONG = re.compile(r"\*\*([^*\n]+)\*\*")
_EM = re.compile(r"\*([^*\n]+)\*")
_CODE = re.compile(r"`([^`\n]+)`")
#: `[text](url)`, on already-escaped input — so the URL arrives with `&` as
#: `&amp;` and `"` as `&quot;`, and the character class can simply refuse the
#: rest. No parentheses inside the target: a Wikipedia disambiguator such as
#: `Anadyr_(river)` is exactly the case that would break, and it belongs in a
#: `link:` row where the store holds the identifier rather than the address.
_LINK = re.compile(r"\[([^\]\n]+)\]\(([^\s()<>]+)\)")
#: A gloss may link out to `http` and `https` and to nothing else. **The
#: allowlist is the point of escaping first**: `javascript:` in an `href` is the
#: injection that surviving `escape()` would otherwise walk straight past, since
#: escaping fixes the *text* of an attribute and says nothing about its scheme.
LINK_SCHEMES = ("http://", "https://")
#: A markdown bullet: `- ` or `* ` at the start of a line.
_BULLET = re.compile(r"^[-*]\s+(.*)$")


def _link_html(m: re.Match) -> str:
    """`[text](url)` → an anchor, or the literal text where the scheme is not ours.

    Rendered as the source wrote it rather than dropped, because a gloss that
    silently loses an author's link is worse than one that shows its brackets:
    the second is visible and gets fixed.
    """
    label, href = m.group(1), m.group(2)
    if not href.lower().startswith(LINK_SCHEMES):
        return m.group(0)
    return (f'<a class="out" href="{href}" target="_blank" '
            f'rel="noopener noreferrer">{label}</a>')


def inline_html(text: str, store: dict) -> str:
    """One line of authored text: escaped, then the small markup a gloss may use.

    `[[…]]`, `[text](url)`, `**strong**`, `*em*` and `` `code` ``. No paragraph
    wrapping and no lists — this is for a table cell or a caption, where
    `gloss_html`'s block elements would be wrong.

    **Escaped first, then a closed set of rules**, which is the whole safety
    argument: a store value cannot smuggle markup in, and each rule adds exactly
    the element it names. `**strong**` is tried before `*em*` or the em rule
    would eat the first asterisk of each pair.
    """
    out = escape(text)
    out = WIKILINK.sub(lambda m: _entity_link(m.group(1), store), out)
    out = _LINK.sub(_link_html, out)
    out = _CODE.sub(r"<code>\1</code>", out)
    out = _STRONG.sub(r"<strong>\1</strong>", out)
    return _EM.sub(r"<em>\1</em>", out)


def _entity_link(ident: str, store: dict) -> str:
    rec = store.get(ident)
    return (
        f'<a class="ent{"" if rec else " dangling"}" data-ref="{ident}" '
        f'href="{BASE}/entity/{ident}" title="{escape(ident)}">'
        f'{escape(rec["canonical"] if rec else ident)}</a>'
    )


def gloss_html(text: str, store: dict) -> str:
    """An entity's gloss as HTML: escaped first, then the little markup it may use.

    **`[[class:slug]]` is how one entry names another.** Bare `person:jochelson`
    in running prose was unmarked and unclickable, and worse, indistinguishable
    from prose that merely mentions the shape — the brackets say "this is a
    reference" the way they do in every wiki, and `entity check` can then refuse
    one that resolves to nothing.

    Escaped before anything else, so a gloss is text and never markup. The rest
    is a closed set of rules — `*em*`, `**strong**`, `` `code` ``, `[text](url)`
    and `- ` bullets — recognised **because the records already use them**, which
    is the whole argument for each one. `entities/people/eskimo.md` was written
    with a list and an external link before either rendered, so the card showed
    a paragraph of literal `- ` lines and a bare `[…](…)`: an author writing
    markdown in a markdown file is not a mistake to be trained out.

    No markdown library. Escape-first plus a closed set is what keeps a store
    value from reaching the page as markup, and a general parser would trade
    that for a much larger surface nobody here needs.
    """
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        if not para.strip():
            continue
        # A block is a list when its *first* line is a bullet. Deciding per line
        # would let a paragraph that happens to wrap onto a dash open a `<ul>`
        # around one sentence.
        lines = para.split("\n")
        if _BULLET.match(lines[0].strip()):
            items = []
            for line in lines:
                m = _BULLET.match(line.strip())
                if m:
                    items.append(m.group(1))
                elif items:
                    # A continuation line belongs to the item above it, which is
                    # how markdown reads a wrapped bullet.
                    items[-1] += " " + line.strip()
            out.append("<ul>" + "".join(
                f"<li>{inline_html(i, store)}</li>" for i in items) + "</ul>")
        else:
            out.append(f"<p>{inline_html(para, store)}</p>")
    return "".join(out)


def link_html(row: str) -> str:
    """One `link:` row as an outbound link, with its site's mark where there is one.

    `target=_blank`: these leave the edition, and a reader who followed one out of
    a page they were reading would have to find their place again.
    """
    kind, _, rest = row.partition(":")
    fmt, label, icon = LINK_KINDS.get(kind, ("", "", ""))
    if not fmt:
        return f"<div class='meta'>{escape(row)}</div>"
    href = fmt.format(rest)
    mark = (
        f"<img class='site' src='/static/site/{icon}.svg' alt=''>"
        if icon
        else "<span class='site'>↗</span>"
    )
    return (
        f"<div class='meta'><a class='out' href='{escape(href)}' "
        f"target='_blank' rel='noopener noreferrer'>{mark}"
        f"{escape(label or rest)}</a></div>"
    )


# The Tier-1 languages by the name a reader wants are `langs.TIER1_NAMES`, and
# every language the edition can name is `langs.LANGS`. They were stated here
# and again in `validate.TIER1`, which is the duplication that module exists to
# remove — the alias column would have made it three.


#: Fields the card renders somewhere other than the properties block, and the
#: two that are the identity itself. Named rather than left implicit, because
#: `test_edition.py` asserts that every key `entities.parse` produces is either
#: here or rendered by `property_rows` — **a field nobody displays is a field a
#: human maintains for nothing**, and the store gained `within:`, `geo:` and
#: `area:` before anything showed them.
SHOWN_ELSEWHERE = {
    "id",
    "class",
    "slug",  # the identity, in the heading and the code
    "canonical",
    "status",
    "links",
    "aliases",
    "gloss",
    "dir_class",
    "stem",
    "path",  # `load`'s bookkeeping, not the record
}


#: The fields `property_rows` renders. Together with `SHOWN_ELSEWHERE` this must
#: cover every key `entities.parse` returns, and `test_edition.py` says so.
PROPERTY_FIELDS = ("within", "part_of", "area", "geo", "frame", "authority")


def property_rows(rec: dict, store: dict, root: Path) -> list[dict]:
    """Every remaining field of the record, as typed rows.

    The rule this exists to keep is that **an entity file has no invisible
    fields**. A store a human hand-maintains whose values never reach the page
    is one where a wrong value is never noticed — which is the same failure as
    an unratified span rendered like a ratified one, one store over.

    `contains` is the one row that is not a field. It is the inverse of
    `within:` and it is here because the tree is the whole point of the
    geography, and a parent that could not list its own members would send a
    reader to the atlas to find out what it holds.

    **Rows carry a `kind`, not markup.** They used to be built here as HTML
    strings, which meant every value's escaping was this function's to remember
    — and a field added later would inherit whatever the line beside it happened
    to do. The template renders each kind and escapes everything, so a new field
    cannot smuggle raw markup in through a store value.
    """
    rows: list[dict] = []

    # Two rows, never merged: `within:` is where the thing is and `part-of:` is
    # what it belongs to. A card showing one row for both would reintroduce, at
    # the reader's end, exactly the ambiguity the two fields were split to end.
    for field, label in (("within", "within"), ("part_of", "part of")):
        if rec[field]:
            parent = store.get(rec[field])
            rows.append(
                {
                    "kind": "entity",
                    "label": label,
                    "id": rec[field],
                    "name": parent["canonical"] if parent else rec[field],
                }
            )

    kids = geo.children(store).get(rec["id"], [])
    if kids:
        rows.append(
            {
                "kind": "entities",
                "label": "contains",
                "entries": [{"id": k, "name": store[k]["canonical"]} for k in kids],
            }
        )

    # **One row per `geo:` member, in the order the file writes them.** The field
    # is a union and the card is the place a wrong value gets noticed, so a
    # record naming two polygons must show two rows: collapsing them to "area"
    # with a composite id printed once was legible only to somebody who already
    # knew the spelling.
    for sid in geo.geo_shapes(rec):
        s = geo.index(root)["shapes"].get(sid, {})
        km2 = s.get("area_km2")
        detail = " · ".join(
            x
            for x in (
                s.get("name", ""),
                f"{int(km2):,} km²" if km2 else "",
                s.get("source", ""),
                # The delineator's own admission, carried to the page. A basin
                # outline a reader is about to trust is one whose publisher may
                # have said it was coarse.
                "coarse delineation" if s.get("precision") == "low" else "",
            )
            if x
        )
        rows.append(
            {"kind": "area", "label": "area", "id": sid, "detail": detail}
        )

    for lat, lon in geo.geo_points(rec):
        rows.append(
            {
                "kind": "point",
                "label": "point",
                "lat": f"{lat:.4f}",
                "lon": f"{lon:.4f}",
                # A coordinate a reader cannot open is a coordinate nobody checks,
                # and these are the store's most checkable field: a point derived
                # from a 1900s gazetteer either lands on the right headland or it
                # does not. The card is where a wrong value gets noticed, which is
                # the whole argument for `_props.html`, and until now the noticing
                # meant copying twelve digits into another tab.
                "maps": map_links(lat, lon),
            }
        )

    # An entity member is a location too, and it is the one kind a reader cannot
    # check by looking at a number — so it says whose extent this record is
    # borrowing, by name, and links there.
    for m in geo.geo_refs(rec):
        target = store.get(m)
        rows.append(
            {
                "kind": "entity",
                "label": "extent of",
                "id": m,
                "name": target["canonical"] if target else m,
            }
        )

    if rec["frame"]:
        w, s, e, n = rec["frame"]
        rows.append(
            {
                "kind": "plain",
                "label": "frame",
                # Said in words as well as numbers, because four bare degrees are
                # the one field on this card a reader cannot check by looking:
                # the map above is *drawn* to them, so it can never disagree.
                "value": f"{w:g}–{e:g}°E, {s:g}–{n:g}°N — the map's view, "
                         f"not a boundary",
            }
        )

    if rec["authority"]:
        rows.extend(_authority_rows(rec["authority"], root))

    return rows


#: Every plain field of an `authorities.json` record, in reading order, and the
#: label the card gives it. The rest are handled by name: `key` and `cited_as`
#: and `printed` have shapes of their own, `doi` and `url` carry a rank, and
#: `author_printed` / `year_printed` qualify the field above them rather than
#: standing alone. `test_edition.py` holds all of that against the live store,
#: so a field added to the bibliography cannot arrive invisible on the one page
#: that transcludes it.
AUTHORITY_FIELDS = (
    ("author", "author"), ("title", "title"), ("title_en", "title (English)"),
    ("container", "in"), ("in", "in"), ("place", "place"), ("year", "year"),
    ("lang", "language"), ("ref", "listed on"), ("note", "note"),
)

#: The two fields whose value is `{url, provenance}` — a reading with a rank on
#: it, which is shown and never flattened away.
AUTHORITY_SOURCED = (("doi", "DOI"), ("url", "copy"))


def _authority_rows(key: str, root: Path) -> list[dict]:
    """The bibliography record this entry *is*, whole, as rows.

    **A transcluded store is still a store, and the no-invisible-fields rule
    reaches it.** The card used to print the key and the title and stop, which
    left `cited_as` — the field that says how the book *names* the work, and so
    the only one a reader holding a footnote can match against — nowhere in the
    encyclopedia at all. The rest were no better off; they were merely less
    missed.

    **`printed` is the record**, which is `find authority`'s rule and this
    follows it: the block a human copied off the page comes first and the parsed
    fields ride beneath, so the two can be read against each other rather than
    one standing in for the other. A work the printer set twice — the Russian
    entry and Bogoras's own English rendering — shows both, because the page did.
    """
    from . import authorities

    got = authorities.record(authorities.load(root), key)
    rows = [{"kind": "authority", "label": "authority", "id": key,
             "title": got.get("title", "") if got else ""}]
    if not got:
        return rows
    if got.get("cited_as"):
        # **The siglum is the field a reader arrives holding.** `Maydell, I` is
        # what the footnote printed; everything else on this card is what the
        # bibliography says about it, and is no use until this line matches.
        rows.append({"kind": "plain", "label": "cited as",
                     "value": " · ".join(
                         authorities.siglum_forms(got["cited_as"])
                         or [authorities.siglum_name(got["cited_as"])])})
    for field, label in AUTHORITY_FIELDS:
        v = got.get(field)
        if not v:
            continue
        if field == "author" and got.get("author_printed") == "rule":
            # Not a fact the page states: the list runs several works under one
            # author's name and prints it once, so the attribution here is the
            # store's inference from the layout and says so.
            v = f"{v} — carried down from the entry above, not printed again"
        if field == "year" and got.get("year_printed"):
            # **Printed wins, and here it is a range the parsed int flattens.**
            # `1834, 1835, 1836` became `1834`, which is right for sorting and
            # wrong as a statement about the book.
            v = f"{got['year_printed']} — printed; {v} as the store sorts it"
        if field == "ref" and got.get("folio"):
            v = f"{v} (folio {got['folio']})"
        rows.append({"kind": "plain", "label": label, "value": str(v)})
    for field, label in AUTHORITY_SOURCED:
        v = got.get(field)
        if not v:
            continue
        # The rank rides with the reading, here as everywhere: a scan a model
        # found is a proposal until somebody opens it.
        rows.append({"kind": "sourced", "label": label,
                     "value": v.get("url", ""),
                     "resp": v.get("provenance", "")})
    for b in got.get("printed", []):
        rows.append({"kind": "printed", "label": "printed",
                     "value": b.get("text", ""), "lang": b.get("lang") or "en",
                     "block": b.get("kind") or ""})
    return rows


def strip_markup(html: str) -> str:
    """Rendered page HTML back to plain text, for the search index.

    Unescapes after stripping the tags, which the version this replaces did not:
    the input is already-escaped HTML, so what came out carried `&amp;` where
    the page had `&` — and it was then interpolated back into a result row as
    markup, so the entity was re-emitted rather than shown.
    """
    from html import unescape

    return unescape(re.sub("<[^>]+>", "", html))


def map_context(
    idents, root: Path, base: str = BASE, store: dict | None = None, shape=None,
    hidden=(), dropped=(),
) -> dict:
    """A selection of entities on one map, with the tree that frames it.

    `store` and `shape` are injected so the server can hand in its cached
    readers: one map asks for six or more shapes out of a 1.2 MB store, and
    every one of them was a fresh read and JSON decode. They default to the
    plain ones, so this stays callable without a server behind it — the caching
    is the web layer's business and does not belong in a module the CLI imports.

    The framing is the argument. A shape shown alone says only what it looks
    like; shown inside the thing that contains it, it says where it *is* — which
    is the whole reason the Small Anui wants the Kolyma around it and the reason
    the hierarchy is worth authoring at all. **The selection generalises that
    rather than replacing it**: a map of several places frames on the first thing
    that contains them all, so a reader who puts Uelen beside Mariinsky Post is
    shown what it takes to hold both, and the tree beneath the map names it.

    Three kinds of subject, and the caption distinguishes them because they are
    not equally well founded: a shape a source drew, a point a human keyed, and
    an extent computed from what lies beneath. Only the first two are claims
    about a boundary.

    **The sheet is not the frame.** Everything is drawn into the widest extent
    the reader can reach from here — the outermost node of the tree — and
    `view` opens on the frame within it. That split is what lets hiding a node
    re-frame the map with no round trip and nothing re-projected: the candidate
    rectangles travel as numbers (`frames`), already in sheet units, and
    choosing one is writing it into the `viewBox`. For a single subject the
    sheet *is* the frame and the output is what it always was.
    """
    store = load(root) if store is None else store
    if shape is None:

        def shape(ident):
            return geo.shape(ident, root)

    # **A bare id is one selection, spelled the short way.** Not defensiveness: a
    # string is iterable, so without this the commonest call in the codebase
    # would select each of its own characters, find none of them in the store and
    # report "no entry" about an entity that is right there. A wrong answer that
    # looks like a legitimate one is the failure this edition is organised
    # against, and it costs a line to make impossible.
    sel = list(dict.fromkeys([idents] if isinstance(idents, str) else idents))
    hidden = {h for h in hidden if h}
    dropped = {d for d in dropped if d}
    out: dict = {
        "ident": sel[0] if sel else "",
        "base": base,
        "rec": None,
        "svg": "",
        "parent": None,
        "basis": {},
        "absent_note": "",
        "warm": [],
        "subjects": [],
        "drawn": [],
        "tree": [],
        "frames": {"order": [], "box": {}, "own": {}},
    }
    known = [i for i in sel if i in store]
    if not known:
        return out
    # **A `geo:` member joins the selection, unless it was dropped.** The map of
    # a people that names its villages *is* those villages, so they are subjects
    # and not context: they frame it, they are pinned, they are named in the tree
    # as chosen, and each can be taken off again. Faking the last of those in the
    # tree was tried and is the reason this is here — a row that renders selected
    # while the client's selection does not hold it cannot be clicked off,
    # because the click reads the selection and the highlight read something
    # else. One fact, one place.
    #
    # **`dropped` is why absence is not enough.** This function is asked afresh
    # on every interaction and cannot remember, so "not in the selection" means
    # both "never added" and "just taken off" — and expanding on the first
    # reading undoes the second, which put a village back on the map the moment a
    # reader clicked it away. So dismissal is said out loud, the way `hidden` is,
    # and for the same reason: a rule that re-derives has to be told what a human
    # decided, or it will re-derive over them.
    #
    # **One level, not transitively.** A member is what this record says about
    # where it is; what *its* members say is its own map's business, and
    # following the chain would put the Chukchee Peninsula's villages on a map of
    # the Yupik by way of two hops nobody asked for.
    known = list(dict.fromkeys(
        known + [m for i in known for m in geo.geo_refs(store[i])
                 if m in store and m not in dropped]))

    def _own(i):
        """How big this thing is — what a container sizes itself on.

        **A declared frame is a box to draw to**, and `extent_of` deliberately
        does not return one — a viewport carries padding somebody chose for
        another map. It is the fallback here rather than the answer, so an
        ancestor still sizes itself on real geometry; without it at all,
        `land:parapolsky-dol` reported "nothing to draw" while carrying the very
        box `geo bounds` had measured for it from the two bays that define it.
        """
        return geo.extent_of(i, store, root) or store[i]["frame"]

    # **A hidden node is drawn and not painted.** Everything the selection
    # implies goes into the SVG whatever is hidden; hiding is a rule about paint
    # and about what the frame may sit on, and it is applied out in the browser
    # so that showing a node again costs nothing. What `hidden` changes *here* is
    # only the framing — which is why `live` appears in the frame rule below and
    # nowhere in the drawing.
    live = [i for i in known if i not in hidden]
    boxes = {i: _own(i) for i in known}
    out["drawn"] = [i for i in known if boxes[i]]

    # **Everything one step from here, not everything drawn.** The map is the
    # authority on what can be *highlighted*; it is not the authority on what a
    # reader is about to open. `member_shapes` stops at the nearest descendant
    # with a shape, so the Chukchee Peninsula — two levels under the Russian Far
    # East and one click away — is on no layer at all. This is the whole of "an
    # entry preloads its ancestors and descendants", and it is computed before
    # the extent, so an entity with nothing to draw still warms its kin.
    # `relatives` is the `within:` chain and stays that — the encyclopedia reads
    # it, and widening it would put a people's villages into the containment
    # tree. But a `geo:` member is drawn on this map and clickable, so it has to
    # be warmed here or the first click on a pin fetches nothing.
    warm = {w for i in known for w in geo.relatives(i, store)}
    warm |= {m for i in known for m in geo.geo_refs(store[i])}
    out["warm"] = sorted(warm - set(known))

    solo = known[0] if len(known) == 1 else ""
    rec = store[solo] if solo else None
    out["rec"] = rec
    out["subjects"] = [{"id": i, "rec": store[i], "hidden": i in hidden,
                        "drawn": bool(boxes.get(i)),
                        "basis": _basis(i, store, root)} for i in known]
    if rec:
        out["basis"] = out["subjects"][0]["basis"]

    order = [a for a in geo.common_ancestors(known, store) if a in store]

    if not any(boxes.values()):
        # The tree is built whatever the geometry says, because it is the only
        # way back: a reader who has put a shapeless entity on the map still
        # needs the node to click. Nothing is drawn, so nothing is in it but the
        # selection and what holds it.
        out["tree"] = _map_tree(known, hidden, store, order, set())
        # `absent` rows are records, not strings — `sought`, `source`, `why` —
        # and this read them as strings, so every shapeless entry raised
        # AttributeError on `.lower()` instead of rendering the note. It stayed
        # hidden while almost every entry had an extent; a batch of bays and
        # capes with neither `area:` nor `geo:` made it the ordinary path.
        # `geo.absent_row` is the one flattener, and it tolerates the old form.
        if rec:
            head = (rec["canonical"].split() or [""])[0].lower()
            for key, raw in sorted(geo.index(root)["absent"].items()):
                row = geo.absent_row(key, raw)
                hay = f'{row["what"]} {row["sought"]} {row["why"]}'.lower()
                if head and head in hay:
                    out["absent_note"] = row["why"]
                    break
        return out

    # **The frame is the box that holds what is selected, and nothing else.**
    #
    # It used to be the first common ancestor's extent, on the argument that a
    # shape shown inside its container says where it *is*. That argument is
    # sound and the selection is now what carries it: a reader who wants a place
    # in its parent's context says so by putting the parent on the map too, one
    # click, visible in the tree. Framing on the ancestor by default meant every
    # map of a village was a map of the peninsula with a dot on it — most of the
    # picture spent on the answer to a question nobody had asked, and no way to
    # ask the tighter one at all.
    #
    # A declared `frame:` on the one selected entity still wins, because that
    # field exists to say "look at this box" about exactly this map. It no longer
    # reaches a *child's* map, which it did while children framed on their
    # parents: a frame is a viewport authored for one subject, and the subject is
    # now always the thing selected.
    cand: list[str] = [solo] if solo and store[solo]["frame"] else []
    frame_box = next((store[a]["frame"] for a in cand if a not in hidden), None)
    if frame_box is None:
        frame_box = geomap.union_box([boxes[i] for i in live]) \
            or geomap.union_box(boxes.values())

    # The sheet: every frame the reader can reach without asking again. Now that
    # the frame is a union of the per-entity boxes, hiding one can only tighten
    # it — so the sheet is that union, the map opens on the whole of it, and a
    # re-frame never wants a ring that was culled as off-sheet.
    sheet_box = geomap.union_box(
        [frame_box, *boxes.values()] + [store[a]["frame"] for a in cand])
    frame = geomap.Frame(sheet_box)
    view = frame.rect(frame_box)
    out["frames"] = {
        "order": list(cand),
        "box": {a: _rect_str(frame.rect(store[a]["frame"])) for a in cand},
        "own": {i: _rect_str(frame.rect(b)) for i, b in boxes.items() if b},
    }

    def _kind(sid: str) -> str:
        """The shape kind an id names — `watershed`, `marine`, `region`, …

        Read off the declared id and never inferred from the geometry. It took
        a whole `area:` and split off the first member's kind while several
        shapes were one comma-joined string; each member is now passed in on its
        own, and is drawn in its own kind's hue rather than in the first one's —
        which is the honest answer where a record names two kinds, and identical
        to the old one where it does not.
        """
        return sid.partition(":")[0]

    # **Every record the map draws, collected as it is drawn.** The tree below is
    # built from this set and not from a second walk of the store, because the
    # tree is a *legend* for the picture: a shape on the map with no name under
    # it is unreadable, and a name under it for something not drawn points at
    # nothing. Two walks would agree today and diverge on the first change to
    # either — the failure this edition is organised against, in miniature. The
    # coastline is in no record's name and joins nothing.
    on_map: set[str] = set()

    def owned(paths, ent: str = "", kind: str = ""):
        if ent:
            on_map.add(ent)
        return geomap.owned(paths, ent, kind)

    layers: dict[str, list] = {}
    for name, ident in (("land", "base:land"), ("lakes", "base:lakes")):
        doc = shape(ident)
        if doc:
            layers[name] = owned(frame.paths(doc))

    # Siblings before the parent outline before the subject: the subject drawn
    # under its own siblings would be the one shape you cannot see.
    #
    # **Only for a single subject.** Siblings are context for a thing that has
    # none of its own; once the reader has put several places on the map, the
    # selection *is* the context, and every sibling of every one of them is a
    # field of outlines over the shapes they asked to compare.
    kin = (
        [
            k
            for k in geo.children(store).get(tree_parent(store[solo]), [])
            if k != solo and geo.geo_shapes(store[k])
        ]
        if solo and tree_parent(store[solo])
        else []
    )
    if kin:
        layers["kin"] = [p for k in kin
                         for sid in geo.geo_shapes(store[k])
                         for p in owned(frame.paths(shape(sid)), k, _kind(sid))]
    # The outline of whatever the map is framed on, dashed to say it is context
    # rather than subject. For a single subject that is its parent, which is what
    # this layer has always drawn.
    # **The tree's root, not the frame's.** They were one node while the frame
    # sat on the common ancestor; now the frame is the selection's own box and
    # the containing outline is pure context — which is what it was drawn dashed
    # to say. Skipped when hidden, that being what hiding a containing node now
    # means: it no longer moves the frame, so paint is all it has left to change.
    holder = next((a for a in order[:1] if a not in hidden), "")
    if holder and geo.geo_shapes(store[holder]):
        layers["parent"] = [p for sid in geo.geo_shapes(store[holder])
                            for p in owned(frame.paths(shape(sid)),
                                           holder, _kind(sid))]
        out["parent"] = store[holder]

    # **A place drawn twice is drawn once, as the subject.** Selecting the Kolyma
    # and one of its tributaries puts the tributary in both layers, and the paths
    # are identical, so the pair would differ only in which stroke won.
    drawn: set[str] = set()
    subject = []
    for i in known:
        for sid in geo.geo_shapes(store[i]):
            subject += owned(frame.paths(shape(sid)), i, _kind(sid))
            drawn.add(i)
    if subject:
        layers["subject"] = subject

    # **What lies beneath, drawn.** For a node with no boundary of its own this
    # is the whole map — the Russian Far East is not a shape, and a frame with
    # nothing in it but two pins says less than the tree already did. For a node
    # that has one it is still the useful layer: the Kolyma showing the Anuis
    # and the Omolon inside it is the picture the hierarchy was authored for.
    members = []
    for i in known:
        for ent, s in geo.member_shapes(i, store):
            if ent in drawn:
                continue
            drawn.add(ent)
            members += owned(frame.paths(shape(s)), ent, _kind(s))
    if members:
        layers["members"] = members

    # The subjects' own drainage, or — when not one of them has a shape of its
    # own — the holder's, so a map of a shapeless node still shows the rivers
    # running through what it frames. Never both: the fallback is for the case
    # where there is no subject drainage to show, not for the case where the
    # subject's happens to be empty.
    if any(geo.geo_shapes(store[i]) for i in known):
        rivers = [r for i in known for sid in geo.geo_shapes(store[i])
                  for r in frame.rivers(shape(sid))]
        if rivers:
            layers["rivers"] = rivers
    elif holder and geo.geo_shapes(store[holder]):
        layers["rivers"] = [r for sid in geo.geo_shapes(store[holder])
                            for r in frame.rivers(shape(sid))]

    # **Every descendant that no other layer identifies, as an extent — drawn
    # only under the pointer.** A node with neither a shape nor a point is
    # skipped by `member_shapes`, which descends *through* it to the basins
    # below, so Chukotka appears nowhere on the Russian Far East's map and its
    # name lit up nothing. A box is what there is to draw for it, and a box on
    # every one of them at once is a field of rectangles over the thing you were
    # reading. So the layer is drawn transparent and only the highlight paints
    # it: the answer is there when the question is asked and not before.
    extents, seen = [], set()
    for i in known:
        for ent, ebox in geo.member_extents(i, store, root):
            if ent in drawn or ent in seen:
                continue
            seen.add(ent)
            if d := frame.viewport(ebox):
                extents += owned([d], ent)
    layers["extents"] = extents

    # **A pin for a place that was chosen, and for no other.** `pins_under`
    # plotted two levels down, so selecting the Chukchee Peninsula put thirty-four
    # village dots and thirty-four labels over the outline — and named all
    # thirty-four in the tree below it. None of them had been asked for. It is
    # the framing rule again and the same answer: context is selected, not
    # assumed, and a place a reader wants on the map is one click away in the
    # running text or in the atlas. `depth=0` is `pins_under` plotting the
    # entity and nothing beneath it, which keeps the longitude shifting in the
    # one place that owns it.
    pins, plotted = [], set()
    for i in known:
        for lon, lat, label, ent in geo.pins_under(i, store, root, depth=0):
            if ent in plotted:
                continue
            plotted.add(ent)
            p = frame.point(lon, lat)
            if p:
                pins.append((p[0], p[1], label, ent))
                on_map.add(ent)

    # The tree is a legend for the picture, so it is built from the picture:
    # `on_map` is what the layers above actually put on it, collected as they
    # went. A village drawn as a pin, a basin drawn as a member and a region
    # drawn only as an invisible extent all get a name under the map, and each
    # of those names lights its own shape.
    out["tree"] = _map_tree(known, hidden, store, order, on_map)

    # **`basin` is read off the shape's type, not the entity's class.** `area:`
    # is typed — `watershed:anadyr` names where the polygon came from — and "this
    # outline is a drainage divide" is a fact about the shape's provenance, not
    # about what kind of thing the record is. Today every `watershed:` in the
    # store happens to sit on a `water:` entity and the two predicates agree;
    # they are still different questions, and only this one answers why the
    # boundary must not be drawn in the colour of the rivers running inside it.
    # The members are left alone: they are the nearest descendants that have a
    # shape, chosen without reference to what drew them.
    #
    # Every subject, not any: with several on the map the mark can only speak
    # for the map, and a selection that mixes a basin with a coastline is not a
    # basin map. One subject reduces it to what it always was.
    # **`all(())` is `True`, so the emptiness has to be tested separately.** Once
    # a record's shapes are a list rather than a single possibly-blank string,
    # an entity with no shape at all satisfies "every shape is a watershed"
    # vacuously, and a people or a bare point would have been marked a basin.
    subject_shapes = [s for i in live for s in geo.geo_shapes(store[i])]
    mark = "basin" if subject_shapes and all(
        s.startswith("watershed:") for s in subject_shapes) else ""
    out["svg"] = geomap.render(frame, layers, pins, mark=mark, view=view)
    return out


def _rect_str(rect) -> str:
    """A `Frame.rect` as the four numbers a `viewBox` wants, or `""`."""
    return " ".join(f"{v:.1f}" for v in rect) if rect else ""


def _basis(ent_id: str, store: dict, root: Path) -> dict:
    """How well founded this subject's outline is — a shape, a point, or a box.

    Five kinds, and they are not equally well founded: a shape a source drew, a
    point a human keyed, another entity's extent this one transcludes, a
    parent's extent inherited, and a box computed from what lies beneath. Only
    the first two are claims about a boundary, and the caption says which it is
    looking at rather than leaving a reader to assume the strongest.

    **`transcluded` is why the template's catch-all had to stop asserting.** It
    read "framed by what lies beneath it — no source draws a boundary for this",
    which was true of the one case that reached it and is false of a people that
    names its villages: something is drawn, it is just drawn somewhere else. A
    new kind rendering as the wrong sentence with no error is the failure this
    edition is arranged against, so the else-branch says only what it knows.
    """
    rec = store[ent_id]
    shapes = geo.geo_shapes(rec)
    if shapes:
        # The first, where a record names several. The caption is a basis and
        # not a census — `property_rows` lists every member — and a caption that
        # grew a list would say least about the case it exists for.
        row = geo.index(root)["shapes"].get(shapes[0], {})
        km2 = row.get("area_km2")
        return {
            "kind": "shape",
            "id": shapes[0],
            "km2": f"{int(km2):,}" if km2 else "",
            "source": row.get("source", ""),
            "more": len(shapes) - 1,
        }
    points = geo.geo_points(rec)
    if points:
        return {"kind": "point",
                "lat": f"{points[0][0]:.3f}", "lon": f"{points[0][1]:.3f}"}
    refs = geo.geo_refs(rec)
    if refs:
        return {"kind": "transcluded", "id": refs[0], "more": len(refs) - 1}
    if rec["class"] == "people" and not geo.children(store).get(ent_id):
        # A people with no sprachraum of its own is shown at its parent's, and
        # the card has to say so: a subgroup lives inside its ethnicity's area
        # by what the word means, which bounds it truthfully and draws no
        # boundary anybody has claimed. `extent_of` carries the argument, and
        # the same order — where it is, then what it belongs to.
        up = tree_parent(rec)
        if up:
            return {"kind": "inherited", "id": up}
    return {"kind": "framed"}


def _map_tree(sel: list[str], hidden: set, store: dict, order: list[str],
              on_map: set) -> list[dict]:
    """**A legend for the map: every record it drew, and what holds them.**

    A map of several places is unreadable as a list — Uelen, the Anadyr and the
    Chukchee Peninsula say nothing about each other in a row — and the thing
    that makes them one picture is the node that contains them all. So the tree
    runs from that node, the first common ancestor of the selection, down
    through the branches that reach everything drawn.

    **Everything drawn, not only what was selected.** Putting a parent on the
    map draws its members, and a shape with no name under it is a shape a reader
    cannot ask about — they could see nine basins inside Chukotka and find one
    name in the tree. `on_map` comes from the layer building itself rather than
    from a second walk of the store, so the two cannot come to disagree about
    what is on the picture.

    **And what a chosen node offers, which is not the same set.** Since a pin is
    drawn only for a place that was chosen, a reader who selects the Chukchee
    Peninsula sees its outline and no villages — and with the tree holding only
    what was drawn, there was nowhere left to find one. So the direct children of
    a selected node are listed too, whether or not they are on the picture. That
    is the drill-down: select a region, read what is in it, choose one. Direct
    children and no deeper, and only under a node the reader chose, or the tree
    would be the whole atlas with the map buried in it.

    It still ends at the common ancestor going *up*: above that is not on the
    map, and a tree that ran to the top of the store would be the atlas with the
    map's own contents buried in it.

    **Hidden nodes stay in the tree.** Hiding is "do not paint this and do not
    frame on it", which is only useful if there is something left to click to
    undo it. Dismissing is the other control, and it takes a place out of the
    selection entirely.

    **A `geo:` member needs nothing here.** It is drawn because the subject named
    it — the forty-one villages of `people:maritime-chukchi` *are* its map — and
    it reaches this function already in `sel`, because `map_context` puts it
    there. That is what makes it selected and unfolded without this function
    knowing the field exists, and it is also what makes it *clickable off*: the
    row's highlight and the client's selection are one fact, so a reader who
    clicks a village they did not ask for gets it off the map rather than added
    to it a second time. Hanging them under the naming entity instead was tried
    and taken out — it moved forty-one villages out of the geography, which is
    where a reader looks for them, to say something the selection already said.
    """
    from .entities import ancestors

    kids_of = geo.children(store)
    offered = {k for i in sel for k in kids_of.get(i, []) if k in store}
    stop = order[0] if order else ""
    nodes = {i for i in set(sel) | set(on_map) | offered if i in store}
    for i in list(nodes):
        chain = [a for a in ancestors(i, store) if a in store]
        if stop:
            # **A node that *is* the root climbs no further.** Walking up and
            # breaking on `stop` never breaks for `stop` itself — its own
            # ancestors are all above it — so a map of one village, whose parent
            # outline is drawn and whose parent is the root, ran the chain to the
            # top of the store and rooted the tree at the Russian Far East. A
            # node not under the root does not climb either: it is its own root,
            # which is the honest shape for something the frame does not contain.
            if i == stop or stop not in chain:
                continue
            chain = chain[:chain.index(stop) + 1]
        nodes.update(chain)

    kids: dict[str, list[str]] = {}
    for n in nodes:
        up = tree_parent(store[n])
        if up in nodes:
            kids.setdefault(up, []).append(n)

    def rank(ident: str) -> tuple:
        # **The non-geographical rows come first**, and then by what the reader
        # sees rather than by id: `place:` sorts before `water:`, so id order
        # interleaves the classes and puts the Anadyr after every village on it.
        #
        # A people or a language is not another rung of the containment tree —
        # it is an overlay on it, and there are always few of them against many
        # villages. Sorted in among the settlements they cover, the Naukans and
        # the Sireniks land in the middle of a list of forty and read as two more
        # places. At the top they read as what they are: the divisions, and then
        # the ground.
        rec = store[ident]
        return (rec["class"] in GEO_CLASSES, rec["canonical"], ident)

    def by_name(ids):
        return sorted(ids, key=rank)

    def build(ident: str) -> dict:
        rec = store[ident]
        chosen = ident in sel
        below = [build(k) for k in by_name(kids.get(ident, []))]
        # **What is on the map is open; what is merely on offer is folded.**
        # A flat list makes the pane taller than the map it explains — you scroll
        # past the names to reach the picture — and the thirty-four villages of
        # the Chukchee Peninsula are exactly that list. But they have to be
        # *there*: they are how a reader adds one, and nothing else names them.
        #
        # Keying on drawn-ness rather than on whose child it is answers both. The
        # open rows are the legend, which is what the tree is for; the fold is
        # the offer, which is what it grew. A node carrying a selection is never
        # folded whatever else is true of it, or a place the reader chose could
        # end up buried in a closed summary, drawn on the map with no name
        # anywhere to light it.
        #
        # **A non-geographical child is never folded either.** The fold is sized
        # against the thirty-four villages of the Chukchee Peninsula, and a
        # people or a language is the opposite case: there are two of them under
        # the Siberian Yupik and they are what the node *is divided into*.
        # Folding them put the divisions behind a "2 more" summary on a map whose
        # subject is the division, which is the one row a reader opened it for.
        out_kids, folded = [], []
        for c in below:
            keep = (c["carries"] or c["drawn"]
                    or c["cls"] not in GEO_CLASSES)
            (out_kids if keep else folded).append(c)
        out_kids.sort(key=lambda c: (c["cls"] in GEO_CLASSES,
                                     not c["selected"], c["canonical"]))
        return {
            "id": ident,
            "canonical": rec["canonical"],
            "cls": rec["class"],
            "selected": chosen,
            "hidden": ident in hidden,
            "drawn": ident in on_map,
            "carries": chosen or any(c["carries"] for c in below),
            "children": out_kids,
            "folded": folded,
        }

    roots = by_name(n for n in nodes if tree_parent(store[n]) not in nodes)
    built = [build(r) for r in roots]
    built.sort(key=lambda c: (c["cls"] in GEO_CLASSES,
                              not c["selected"], c["canonical"]))
    return built



def _guarded(root: Path, write, report=None) -> dict:
    """Run a write, then refuse it if the store no longer checks out.

    `report` is a thunk read *after* the write survives the gate, so a caller can
    say what the act did. `{"ok": True}` alone was indistinguishable from "it
    worked and changed nothing", which is the answer to a different question:
    ratifying an entity whose form no page has yet printed is a success, and a
    reader watching for links needs to be told that rather than left to infer it.

    The browser is a human acting, not a pass proposing, so it does not need
    `--commit` — the click is the act, and git is the witness. What it does need
    is to be unable to leave the store in a state `entity check` rejects, because
    every `@ref` in the corpus resolves against it and a broken store breaks
    pages nobody is looking at.
    """
    undo = write()
    rep = check(root)
    if not rep["ok"]:
        undo()
        return {
            "error": "refused — the store would not check out: "
            + "; ".join(rep["errors"][:3])
        }
    return {"ok": True, **(report() if report else {})}


def _ratify(ent_id: str, root: Path) -> dict:
    try:
        split_id(ent_id)
    except ValueError as e:
        return {"error": str(e)}
    p = path_for(ent_id, root)
    if not p.exists():
        return {"error": f"no entry at {p}"}
    before = p.read_text(encoding="utf-8")
    if "- status: proposed" not in before:
        return {"error": "not a proposed entry"}

    def write():
        p.write_text(
            before.replace("- status: proposed", "- status: ratified", 1),
            encoding="utf-8",
        )
        # **The same second half as `harness entity ratify`**, because there are
        # two ways to ratify and only one of them applying the links it licenses
        # would leave the browser and the terminal putting the corpus in
        # different states. `relink.apply_to_corpus` is the one implementation;
        # its undo list joins this one so a store that fails the gate takes the
        # pages back with it.
        from .relink import apply_to_corpus

        got, _left, undo = apply_to_corpus(root, load(root))
        applied.extend(got)

        def back():
            for fn in undo:
                fn()
            p.write_text(before, encoding="utf-8")

        return back

    applied: list[dict] = []

    def report() -> dict:
        # **The drafts too, and by regenerating them.** `relink` touches
        # committed `tei/` alone, which is one page — so an entry that page does
        # not print linked nothing however often the book printed it, and the
        # click looked like it had failed. The drafts are where a reader with
        # `--drafts` is actually reading, and leaving them was the wrong half of
        # the act. They are *regenerated* rather than relinked because a draft
        # carries the generator's own questions beside its text, and a fresh
        # `<rs>` standing next to a comment saying no rule may write one is two
        # halves of a file contradicting each other.
        from .relink import refresh_drafts

        stale = refresh_drafts(root, load(root), [ent_id])
        return {"linked": applied,
                "pages": sorted({r["ref"] for r in applied}),
                "drafts": stale}

    return _guarded(root, write, report=report)


def _new(body: dict, root: Path) -> dict:
    ident = (body.get("id") or "").strip()
    try:
        split_id(ident)
    except ValueError as e:
        return {"error": str(e)}
    p = path_for(ident, root)
    if p.exists():
        return {"error": f"{ident} already exists"}
    rows = "\n".join(
        f"| {t.strip()} | | no | |" for t in (body.get("aliases") or []) if t.strip()
    )
    text = TEMPLATE.format(
        ident=ident,
        canonical=body.get("canonical") or ident,
        extra="",
        rows=rows or "| | | no | |",
    )

    def write():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return lambda: p.unlink(missing_ok=True)

    return _guarded(root, write)
