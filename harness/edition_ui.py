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

**It writes to `edition/entities/`, and the click is the human act.** That is the
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

from . import geo
from .cli._entity import TEMPLATE
from .entities import (
    GEO_CLASSES,
    WIKILINK,
    check,
    kin_children,
    kin_parent,
    load,
    path_for,
    ratify_text,
    split_id,
    tree_parent,
)
from .layout import bare_own_citations, stem_for

# `scan_for` is re-exported: this module's callers name it here, and the
# definition moved to `paths` because there were two byte-identical copies.
from .paths import scan_for
from .refs import norm_ref

PORT = 8734
REF_OK = re.compile(r"^\d+-\d+$")

#: Where the reading view is mounted by default, and the only place that says so.
#: The four tools share one server, so a bare `/entity/…` in a link would resolve
#: against whichever of them owned the root. **A default, not the mount**:
#: `edition build` mounts the router under its own prefix (`web.build.site_app`). Every function that writes a link takes it as a
#: plain string defaulting to this — never a request, because that would put a
#: web concern inside a text transform.
BASE = "/edition"

#: Where the static files are served from, the second prefix a page needs. Not
#: under `BASE` live: one server mounts `/static` for all four tools.
ASSETS = "/static"




#: Where an editor's own version of a whole leaf lives, and the extensions it may
#: take, **vector first**. `1-361`, part 1's foldout map, is the leaf this exists
#: for and it may end up an SVG; a resolver that assumed a raster would have to be
#: rewritten the day it did.
#:
#: **Under `edition/`, not `gt/`, and the move is the definition being applied.**
#: `gt/` is the artifact reproduced or annotated under human-checked judgement; a
#: leaf an editor reworked is an improvement on what the leaf shows, which is the
#: one thing that rank may not be. It sat in `gt/` on the reading that `gt/` means
#: "what a human has been through" — true of it, and not what the rank says.
#: The safety property is untouched: still tracked, still never rewritten by a
#: rule, which was always an argument about the *store* and not about the rank.
#:
#: The store it now sits in is named for the **layer**, not that rank: a retouched
#: leaf is something a reader is served, and `#ed` stays in `@resp` where a rank
#: belongs. See `docs/edition.md`.
PAGE_IMG = "edition/page-img"
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

    It is *exempt only* — any leaf kind, not `map` alone. A file for a page the
    pipeline still owns is ignored here and reported by `edition runs`, rather
    than being honoured quietly the day somebody adds a branch. Narrowing it to
    the kind that happens to use it today (`1-361`, the folding map) would refuse
    a hand-worked plate for no reason the doctrine gives: what licenses an
    editor's leaf is that the page is out of the tracks, not which sort it is.
    """
    from .zones import is_exempt

    ref = norm_ref(ref)
    if not is_exempt(ref, root):
        return None, "scan"
    for ext in LEAF_EXTS:
        p = root / PAGE_IMG / f"{stem_for(ref, root)}{ext}"
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
    out = {name: root / PAGE_IMG_LAYERS / f"{stem_for(ref, root)}{ext}"
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
#: A subheading, `###` or deeper. Never `#` or `##`: both authored stores slice
#: their files on `##`, so anything that shallow is a section boundary and
#: cannot reach a renderer. Admitted on `gloss_html`'s standing argument — the
#: records already use them, an annotation's `## full` being long enough to want
#: them — and it widens nothing that matters for safety: the tag is fixed and
#: its content still goes through `inline_html`, which escapes first.
_HEADING = re.compile(r"^(#{3,6})\s+(.*)$")


#: A YouTube address this view will hold in place. Host first, so nothing else
#: can reach the embed builder at all.
_YT_HOST = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)/")
#: A video id: 11 characters of the URL-safe alphabet, in any of the spellings a
#: link arrives in — `watch?v=…`, `youtu.be/…`, `embed/…`.
_YT_VIDEO = re.compile(
    r"(?:[?&]v=|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})(?:[&?#]|$)")
#: A playlist id. Longer and more varied than a video's — `OLAK5uy_…` for an
#: auto-generated album, `PL…` for a hand-made list — but the same alphabet.
_YT_LIST = re.compile(r"[?&]list=([A-Za-z0-9_-]{12,64})(?:[&#]|$)")


def youtube_embed(url: str) -> str | None:
    """The `embed/` path a YouTube URL should be played at, or `None`.

    **Built from ids this function matched, never from the URL as given.** A
    `## links` row is authored text, and letting any part of it through to an
    iframe `src` would make the store a way to frame arbitrary pages inside the
    edition. Only two capture groups survive, both of a fixed alphabet that
    cannot carry a quote, a slash or a space, so the result needs no re-escaping.

    Three shapes, and an album link is the middle one:

        j_GLEh8EYYk                     a video
        j_GLEh8EYYk?list=OLAK5uy_…      a video, in its playlist
        videoseries?list=OLAK5uy_…      a playlist with no video named

    The middle shape is what the per-track links of an album are, and keeping the
    `list` is the whole point: a reader who opens track 27 gets the record it
    belongs to, and can play on rather than coming back for track 28.
    """
    # **`&amp;` first.** `_link_html` runs on already-escaped text — its own
    # docstring says so — so a watch URL reaches here with every `&` as `&amp;`,
    # and a `[?&]list=` pattern quietly matched nothing. The failure was silent
    # and partial in the worst way: the video still embedded, so the card worked,
    # and only the playlist was gone. Every per-track link on an album lost the
    # album.
    url = url.strip().replace("&amp;", "&")
    if not _YT_HOST.match(url):
        return None
    v = _YT_VIDEO.search(url)
    lst = _YT_LIST.search(url)
    if v and lst:
        return f"{v.group(1)}?list={lst.group(1)}"
    if v:
        return v.group(1)
    if lst:
        return f"videoseries?list={lst.group(1)}"
    return None


def _link_html(m: re.Match) -> str:
    """`[text](url)` → an anchor, or the literal text where the scheme is not ours.

    Rendered as the source wrote it rather than dropped, because a gloss that
    silently loses an author's link is worse than one that shows its brackets:
    the second is visible and gets fixed.

    **A YouTube link opens in the stack instead of leaving the edition.** It is
    the one outbound address this view can hold in place — a card with the player
    in it, titled with the link's own text — and a recording a supplement is
    *about* is exactly what a reader should not have to leave the page to hear.
    The `href` stays the real watch URL, so no-JS, middle-click and "open in new
    tab" all still work; the card is the enhancement and not the mechanism, which
    is `a.fig`'s arrangement.
    """
    label, href = m.group(1), m.group(2)
    if (emb := youtube_embed(href)):
        return (f'<a class="yt" data-embed="{emb}" href="{href}" '
                f'title="play here">{label}</a>')
    if not href.lower().startswith(LINK_SCHEMES):
        return m.group(0)
    return (f'<a class="out" href="{href}" target="_blank" '
            f'rel="noopener noreferrer">{label}</a>')


def inline_html(text: str, store: dict, base: str = BASE, own: str = "") -> str:
    """One line of authored text: escaped, then the small markup a gloss may use.

    `[[…]]`, `[text](url)`, `**strong**`, `*em*` and `` `code` ``. No paragraph
    wrapping and no lists — this is for a table cell or a caption, where
    `gloss_html`'s block elements would be wrong.

    **Escaped first, then a closed set of rules**, which is the whole safety
    argument: a store value cannot smuggle markup in, and each rule adds exactly
    the element it names. `**strong**` is tried before `*em*` or the em rule
    would eat the first asterisk of each pair.
    """
    out = escape(bare_own_citations(text, own) if own else text)
    out = WIKILINK.sub(lambda m: _entity_link(m.group(1), store, base), out)
    out = _LINK.sub(_link_html, out)
    out = _CODE.sub(r"<code>\1</code>", out)
    out = _STRONG.sub(r"<strong>\1</strong>", out)
    return _EM.sub(r"<em>\1</em>", out)


def _entity_link(ident: str, store: dict, base: str = BASE) -> str:
    rec = store.get(ident)
    return (
        f'<a class="ent{"" if rec else " dangling"}" data-ref="{ident}" '
        f'href="{base}/entity/{ident}" title="{escape(ident)}">'
        f'{escape(rec["canonical"] if rec else ident)}</a>'
    )


def gloss_html(text: str, store: dict, base: str = BASE, own: str = "") -> str:
    """An entity's gloss as HTML: escaped first, then the little markup it may use.

    **`[[class:slug]]` is how one entry names another.** Bare `person:jochelson`
    in running prose was unmarked and unclickable, and worse, indistinguishable
    from prose that merely mentions the shape — the brackets say "this is a
    reference" the way they do in every wiki, and `entity check` can then refuse
    one that resolves to nothing.

    Escaped before anything else, so a gloss is text and never markup. The rest
    is a closed set of rules — `*em*`, `**strong**`, `` `code` ``, `[text](url)`
    and `- ` bullets — recognised **because the records already use them**, which
    is the whole argument for each one. `edition/entities/people/eskimo.md` was written
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
                f"<li>{inline_html(i, store, base, own)}</li>" for i in items) + "</ul>")
        elif m := _HEADING.match(lines[0].strip()):
            # `###` and deeper. `#` and `##` cannot reach here — both stores
            # slice their files on `##`, so a heading that shallow is a section
            # boundary and never body text. Two levels are enough for a `## full`
            # that wants subheadings, and they start at `h5` because the card
            # itself has already spent `h4` on the title.
            tag = "h5" if len(m.group(1)) == 3 else "h6"
            body = " ".join(x.strip() for x in lines[1:] if x.strip())
            out.append(f"<{tag}>{inline_html(m.group(2), store, base, own)}</{tag}>")
            if body:
                out.append(f"<p>{inline_html(body, store, base, own)}</p>")
        else:
            # **Joined into one logical line before the inline rules run**, which
            # is markdown's own reading of a hard-wrapped paragraph — and the
            # same thing the bullet branch above already does for a wrapped item.
            #
            # Not cosmetic. `_STRONG`, `_EM`, `_CODE` and `_LINK` all exclude
            # `\n` from their character classes, so a span that happened to wrap
            # simply did not match, and the asterisks were served to the reader
            # as literal text. Silent, and invisible to whoever wrote the file,
            # because it depends on nothing but where the line broke: measured
            # over the store when this was found, **36 spans across 29 entity
            # files** were failing this way.
            out.append(f"<p>{inline_html(' '.join(
                x.strip() for x in lines if x.strip()), store, base, own)}</p>")
    return "".join(out)


def link_html(row: str, assets: str = ASSETS) -> str:
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
        f"<img class='site' src='{assets}/site/{icon}.svg' alt=''>"
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
    "ratified",  # read into `status` by `load`, for the text being served
    "links",
    "image",  # the figure under the heading, `_entity.html`
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
    # check by looking at a number — so it names where this record is, and links
    # there. **One row, as `contains` is one row**: a people naming thirty-seven
    # villages read as thirty-seven rows of "extent of", which said how the map
    # is drawn rather than what the record claims.
    refs = geo.geo_refs(rec)
    if refs:
        rows.append(
            {
                "kind": "entities",
                "label": "located",
                "entries": [
                    {"id": m, "name": store[m]["canonical"] if m in store else m}
                    for m in refs
                ],
            }
        )

    # **And its inverse, as `contains` is `within:`'s.** A `geo:` member is
    # written on one side only, so the village a people names could not say who
    # is located there — the card the question is asked on.
    located_here = sorted(
        r["id"] for r in store.values() if rec["id"] in geo.geo_refs(r)
    )
    if located_here:
        rows.append(
            {
                "kind": "entities",
                "label": "location of",
                "entries": [
                    {"id": r, "name": store[r]["canonical"]} for r in located_here
                ],
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
            v = f"{got['year_printed']} — as printed"
        if field == "ref" and got.get("folio"):
            v = f"{v} (folio {got['folio']})"
        # A record's `note` is the bibliography's working notebook, adjudication
        # and all: `edition serve` shows it and a static site does not.
        rows.append({"kind": "plain", "label": label, "value": str(v),
                     "working": field == "note"})
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
            "name": row.get("name", ""),
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
        return {"kind": "transcluded", "id": refs[0],
                "name": store[refs[0]]["canonical"] if refs[0] in store else refs[0],
                "more": len(refs) - 1}
    if rec["class"] == "people" and not geo.children(store).get(ent_id):
        # A people with no sprachraum of its own is shown at its parent's, and
        # the card has to say so: a subgroup lives inside its ethnicity's area
        # by what the word means, which bounds it truthfully and draws no
        # boundary anybody has claimed. `extent_of` carries the argument, and
        # the same order — where it is, then what it belongs to.
        up = tree_parent(rec)
        if up:
            return {"kind": "inherited", "id": up,
                    "name": store[up]["canonical"] if up in store else up}
    return {"kind": "framed"}


def atlas_data(root: Path, store: dict | None = None) -> dict:
    """**Every fact a map is composed from, per entity, and nothing composed.**

    The browser composes a map out of a selection (`static/js/geomap.js`), and
    a static host has nobody to ask, so the store has to travel. What travels
    is what the store's own rules answer — how big a thing is, what lies
    beneath it with a shape, what holds it — each computed here, by the one
    function that owns the rule, once per entity. What does not travel is any
    of those rules: the walks differ in ways that matter (`ancestors` climbs
    `within:` alone, `children` inverts `tree_parent`), and a second copy in
    JavaScript would be a second place for them to drift apart.

    `own` is what a container sizes itself on: real geometry first, a declared
    `frame:` only when there is none, for the reason `member_extents` gives.
    `points` are `(lon, lat)` with the longitude already in the store's window.
    """
    from .entities import ancestors

    store = load(root) if store is None else store
    idx = geo.index(root)
    kids = geo.children(store)
    absent = [geo.absent_row(k, v) for k, v in sorted(idx["absent"].items())]

    def note(rec: dict) -> str:
        head = (rec["canonical"].split() or [""])[0].lower()
        for row in absent:
            hay = f'{row["what"]} {row["sought"]} {row["why"]}'.lower()
            if head and head in hay:
                return row["why"]
        return ""

    def box(b):
        return list(b) if b else None

    out = {}
    for i in sorted(store):
        rec = store[i]
        out[i] = {
            "canonical": rec["canonical"],
            "cls": rec["class"],
            "parent": tree_parent(rec),
            "ancestors": [a for a in ancestors(i, store) if a in store],
            "children": [k for k in kids.get(i, []) if k in store],
            "relatives": geo.relatives(i, store),
            "own": box(geo.extent_of(i, store, root) or rec["frame"]),
            "frame": box(rec["frame"]),
            "shapes": geo.geo_shapes(rec),
            "points": [[geo._shifted(lon, idx), lat]
                       for lat, lon in geo.geo_points(rec)],
            "refs": geo.geo_refs(rec),
            "members": [list(p) for p in geo.member_shapes(i, store)],
            "extents": [[e, list(b)] for e, b in geo.member_extents(i, store, root)],
            "basis": _basis(i, store, root),
            "absent": note(rec),
        }
    # The coastline and the lakes, where the store has them: no record names
    # them, so nothing else here would say whether they are there to ask for.
    base = [s for s in ("base:land", "base:lakes") if s in idx["shapes"]]
    return {"geo_classes": list(GEO_CLASSES), "base": base, "entities": out}


#: How many children a card lists before they go behind a fold. The map's fold is
#: sized against the thirty-four villages of the Chukchee Peninsula; this one is
#: sized against a genus, where a dozen species is a list a reader reads and forty
#: is a wall between the entry and everything under it.
KIN_FOLD = 12


def kin_tree(ident: str, store: dict) -> list[dict]:
    """**The entry's place in its own class**: what holds it, and what it holds.

    The card's counterpart to the map's tree (`geomap.js`), and the same picture drawn over the
    other hierarchy — `kin_parent`, so `part-of:` leads. The two are deliberately
    not one tree (`entities.kin_parent`), and a card is exactly where that shows:
    a located entry already carries the atlas's answer in the map pane beside it,
    while a genus, a source or a person has no geography at all and had, until
    now, no way to say what it belongs to except a single `part-of:` row that
    named the parent and neither the grandparent nor one sibling.

    **A spine, not a subtree.** Every ancestor up to the top of the class, each
    holding only the child on the path, then the entry, then its direct children
    and no deeper. The map tree earns its breadth by being a legend for a picture;
    here there is no picture, and a card that opened onto the whole of *animalia*
    would bury the entry it is about. What a child holds is said as a count, which
    is the offer: click it and its own card draws that branch.

    The nodes are the same shape the map's macro renders, minus what only a map
    means — nothing here is hidden, drawn, or framed on.
    """
    if ident not in store:
        return []
    kids_of = kin_children(store)
    descendants: dict[str, int] = {}

    def below(i: str, seen: frozenset) -> int:
        # Cycle-safe by the same discipline as `entities.relatives`: `check`
        # gates acyclicity, but this runs inside a page render.
        if i in seen:
            return 0
        if i not in descendants:
            here = frozenset(seen | {i})
            descendants[i] = sum(1 + below(k, here) for k in kids_of.get(i, []))
        return descendants[i]

    def rank(i: str) -> tuple:
        # Proposed first, as everywhere in the encyclopedia: nothing links an
        # unaudited entry by rule, so it is what wants reading. Then by the name
        # a reader sees, not by id.
        rec = store[i]
        return (rec["status"] != "proposed", rec["canonical"], i)

    def node(i: str, selected: bool, children: list[dict]) -> dict:
        rec = store[i]
        return {"id": i, "canonical": rec["canonical"], "cls": rec["class"],
                "status": rec["status"], "selected": selected,
                "below": below(i, frozenset()), "children": children,
                "folded": [], "summary": ""}

    here = sorted(kids_of.get(ident, []), key=rank)
    kids = [node(k, False, []) for k in here]
    mine = node(ident, True, kids)
    if len(kids) > KIN_FOLD:
        mine["children"], mine["folded"] = [], kids
        mine["summary"] = f"{len(kids)} in it"

    out = mine
    seen = {ident}
    up = kin_parent(store[ident], store)
    while up and up in store and up not in seen:
        seen.add(up)
        out = node(up, False, [out])
        up = kin_parent(store[up], store)
    # Nothing to draw for an entry that neither belongs to anything nor holds
    # anything: a one-node tree is the card's own heading, said again in smaller
    # type. The template asks for the list and gets an empty one.
    return [out] if (out is not mine or kids) else []


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
    after = ratify_text(before, root)
    if after == before:
        return {"error": "not a proposed entry"}

    def write():
        p.write_text(
            after,
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


def annotation_blocks(recs: list[dict], store: dict,
                      base: str = BASE) -> list[dict]:
    """Annotation records → what a template prints.

    **The link aliases are expanded before `gloss_html` sees the text**, which is
    why this file needs no new markup rule. `inline_html` resolves
    `entities.WIKILINK` through `_entity_link`, and that function's whole safety
    argument is that its rule set is closed — it knows one store and renders
    everything else as escaped text. Rewriting `[[melodiya-1974]]` into an
    ordinary `[title](url)` first means the result goes through the `_LINK` rule
    and the `LINK_SCHEMES` allowlist that were already here. No new path, and no
    fourth thing marked safe: the two fields below are `gloss_html` output, which
    is the same guarantee the gloss already carries.

    `gloss_html` rather than `inline_html` because a summary may be a bullet
    list — the music supplement is two albums and is literally that — and that
    function already renders `- ` blocks, for the reason its docstring gives.
    """
    from . import annotations as ann

    out = []
    for rec in recs:
        rows = rec.get("links", [])
        body = {
            "id": rec["id"],
            "class": rec["class"],
            "placement": rec["placement"],
            "title": rec["title"],
            "status": rec["status"],
            "url": f"{base}/annotation/{rec['id']}",
            "summary_html": gloss_html(
                ann.expand_links(rec["summary"], rows), store, base),
            # `video` where the row's URL names one, so the shelf opens a player
            # in the stack on the same terms the prose links do.
            "links": [r | {"embed": youtube_embed(r["url"])} for r in rows],
            "has_full": bool(rec.get("full", "").strip()),
            # The section ids this annotation is keyed to, so the route can put
            # it after the one the page actually marks rather than above the
            # whole text. See `insert_after_anchor`.
            "toc": [t["value"] for t in rec.get("attaches", ())
                    if t["kind"] == "toc"],
        }
        out.append(body)
    return out


def annotation_full_html(rec: dict, store: dict, base: str = BASE) -> str:
    """The long text, by the same route as the summary."""
    from . import annotations as ann
    return gloss_html(ann.expand_links(rec.get("full", ""), rec.get("links", [])),
                      store, base)


def insert_after_anchor(html: str, anchor_id: str, block: str) -> str | None:
    """Put `block` directly after the element carrying `id="anchor_id"`.

    `None` where the page does not carry that anchor, which is the caller's cue
    to leave the block where it was.

    **Why a section's notice cannot simply sit above the text.** The contents
    panel links to `#chII.1`, and `tei_html` emits that id *inside* `<article>`.
    A block rendered above the article is therefore above the anchor, so a reader
    arriving from the panel lands below it and the notice is scrolled off the
    top — present on the page, and easy to miss at exactly the moment it was
    written for.

    Two anchor shapes, and the same rule reaches both: a printed head,
    `<h2 class="milestone chapter" id="chII">…</h2>`, and the empty marker a
    section gets when the page does not print its head,
    `<span class="milestone anchor section" id="chII.1"></span>`. Closing at the
    first matching end tag is right for both — an `h2` holds spans but never
    another `h2`, and the marker span is empty.
    """
    m = re.search(rf'<(\w+)[^>]*\bid=["\']{re.escape(anchor_id)}["\'][^>]*>', html)
    if not m:
        return None
    close = f"</{m.group(1)}>"
    end = html.find(close, m.end())
    if end == -1:
        return None
    cut = end + len(close)
    return html[:cut] + block + html[cut:]


#: The two handles `tei_html` leaves in the page for the figure join to find, as
#: it writes them — `el_figure` and `el_figref` build these strings literally, so
#: the patterns are exact rather than tolerant. A tolerant one would go on
#: matching after the renderer changed shape and splice into markup it no longer
#: understands; an exact one stops matching, and `test_figure_render.py` fails.
_FIGURE_OPEN = re.compile(r'<figure class="figure" data-figure="([^"]*)" data-i="(\d+)">')
_FIGREF = re.compile(r'<a class="figref" data-fr="(\d+)" tabindex="0">(.*?)</a>',
                     re.S)


def hang_figures(html: str, head) -> str:
    """Replace each bare `<figure>` opening tag with `head(i, n)`.

    **The join is served, not scripted.** The pictures used to be hung by
    `edition.js` off a `STATE.figs` payload, which made them the one part of the
    edition a reader with no script never saw — the caption read, out of an
    adjudicated store, under a blank space. The reason for the client's half was
    only ever the cache: `stores.render` is keyed on the TEI bytes and geometry
    baked into that HTML would outlive a correction to `gt/fig/`. Splicing here,
    per request, keeps that key honest and still puts the picture in the served
    bytes.

    `head` is handed the document-order index and the printed number **off the
    tag**, not out of the caller's records, so the two handles reach the page
    exactly as the renderer set them. Returning falsy leaves the tag alone, which
    is what a figure the join has nothing to say about wants.
    """
    return _FIGURE_OPEN.sub(
        lambda m: head(int(m.group(2)), m.group(1)) or m.group(0), html)


def link_figrefs(html: str, ref) -> str:
    """Replace each inert `<a class="figref">` with `ref(i, body)`.

    `hang_figures`'s argument, for the same markup written by the same renderer:
    a reference to a picture is a join over `gt/fig/` and the List of
    Illustrations, and a reader with no script got a dotted underline that did
    nothing at all. `body` is the renderer's own inline HTML for the words the
    reference is set over and is passed through untouched — the numeral the
    printer set, with whatever markup the page put on it.

    Non-greedy to the first `</a>`, which is right because a figure reference
    holds a number and never another anchor.
    """
    return _FIGREF.sub(
        lambda m: ref(int(m.group(1)), m.group(2)) or m.group(0), html)
