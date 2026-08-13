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
pane, and clicking a place moves it rather than adding to it.

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
    WIKILINK,
    check,
    load,
    path_for,
    split_id,
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
    "dplace": ("https://d-place.org/parameters/{}", "D-PLACE", ""),
    "url": ("{}", "", ""),
}

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
PROPERTY_FIELDS = ("within", "area", "geo", "frame", "authority")


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

    if rec["within"]:
        parent = store.get(rec["within"])
        rows.append(
            {
                "kind": "entity",
                "label": "within",
                "id": rec["within"],
                "name": parent["canonical"] if parent else rec["within"],
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

    if rec["area"]:
        s = geo.index(root)["shapes"].get(rec["area"], {})
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
            {"kind": "area", "label": "area", "id": rec["area"], "detail": detail}
        )

    if rec["geo"]:
        lat, lon = rec["geo"]
        rows.append(
            {
                "kind": "point",
                "label": "point",
                "lat": f"{lat:.4f}",
                "lon": f"{lon:.4f}",
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
        from . import authorities

        got = authorities.record(authorities.load(root), rec["authority"])
        rows.append(
            {
                "kind": "authority",
                "label": "authority",
                "id": rec["authority"],
                "title": got.get("title", "") if got else "",
            }
        )

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
    ent_id: str, root: Path, base: str = BASE, store: dict | None = None, shape=None
) -> dict:
    """One entity on a map, drawn inside its parent's extent — as a context.

    `store` and `shape` are injected so the server can hand in its cached
    readers: one map asks for six or more shapes out of a 1.2 MB store, and
    every one of them was a fresh read and JSON decode. They default to the
    plain ones, so this stays callable without a server behind it — the caching
    is the web layer's business and does not belong in a module the CLI imports.

    The framing is the argument. A shape shown alone says only what it looks
    like; shown inside the thing that contains it, it says where it *is* — which
    is the whole reason the Small Anui wants the Kolyma around it and the reason
    the hierarchy is worth authoring at all.

    Three kinds of subject, and the caption distinguishes them because they are
    not equally well founded: a shape a source drew, a point a human keyed, and
    an extent computed from what lies beneath. Only the first two are claims
    about a boundary.
    """
    store = load(root) if store is None else store
    if shape is None:

        def shape(ident):
            return geo.shape(ident, root)

    rec = store.get(ent_id)
    out: dict = {
        "ident": ent_id,
        "base": base,
        "rec": None,
        "svg": "",
        "parent": None,
        "basis": {},
        "absent_note": "",
        "warm": [],
    }
    if rec is None:
        return out
    out["rec"] = rec
    # **Everything one step from here, not everything drawn.** The map is the
    # authority on what can be *highlighted*; it is not the authority on what a
    # reader is about to open. `member_shapes` stops at the nearest descendant
    # with a shape, so the Chukchee Peninsula — two levels under the Russian Far
    # East and one click away — is on no layer at all. This is the whole of "an
    # entry preloads its ancestors and descendants", and it is computed before
    # the extent, so an entity with nothing to draw still warms its kin.
    out["warm"] = geo.relatives(ent_id, store)

    box = geo.extent_of(ent_id, store, root)
    if box is None:
        # `absent` rows are records, not strings — `sought`, `source`, `why` —
        # and this read them as strings, so every shapeless entry raised
        # AttributeError on `.lower()` instead of rendering the note. It stayed
        # hidden while almost every entry had an extent; a batch of bays and
        # capes with neither `area:` nor `geo:` made it the ordinary path.
        # `geo.absent_row` is the one flattener, and it tolerates the old form.
        head = (rec["canonical"].split() or [""])[0].lower()
        for key, raw in sorted(geo.index(root)["absent"].items()):
            row = geo.absent_row(key, raw)
            hay = f'{row["what"]} {row["sought"]} {row["why"]}'.lower()
            if head and head in hay:
                out["absent_note"] = row["why"]
                break
        return out

    parent = store.get(rec["within"]) if rec["within"] else None
    # **A node with neither a shape nor a point is drawn to itself.** Framing on
    # the parent is what makes a *shape* mean something — the Small Anui says
    # where it is only with the Kolyma around it — but a framed node *is* its
    # extent, and framing that on the parent gave Chukotka and the Russian Far
    # East the identical viewBox: the RFE has no parent, so both fell back to the
    # RFE's own. Two maps of two different regions, pixel for pixel the same.
    framed = not rec["area"] and not rec["geo"]
    # **A parent's declared frame is what its children frame on**, or the field
    # would fix one page and leave every page under it drawn to the box the
    # editor had just said was the wrong one — the villages of the Chukchee
    # Peninsula are exactly the pages that needed it.
    up = (parent["frame"] or geo.extent_of(parent["id"], store, root)) \
        if parent else None
    frame_box = box if framed else (up or box)
    # **A declared `frame:` wins over whichever of the two was derived**, and
    # over nothing else: `box` is untouched, so an ancestor still sizes itself on
    # the real geometry and `member_shapes` still draws everything beneath. Both
    # defaults have a case they get wrong — a shapeless container sized by its
    # farthest-strayed descendant, a dense shape squeezed into its parent's box —
    # and one field answers both.
    if rec["frame"]:
        frame_box = rec["frame"]
    frame = geomap.Frame(frame_box)

    def _kind(area: str) -> str:
        """The shape kind an `area:` names — `watershed`, `marine`, `region`, …

        A composite takes its first member's, which is all a composite can
        honestly say: the two unclaimed language areas that make up
        `people:inupiat` are both `langarea:`, and a union of two *different*
        kinds would be a claim about the world nobody has made. Read off the
        declared id and never inferred from the geometry.
        """
        got = geo.split_area(area)
        return got[0].partition(":")[0] if got else ""

    layers: dict[str, list] = {}
    for name, ident in (("land", "base:land"), ("lakes", "base:lakes")):
        doc = shape(ident)
        if doc:
            layers[name] = geomap.owned(frame.paths(doc))

    # Siblings before the parent outline before the subject: the subject drawn
    # under its own siblings would be the one shape you cannot see.
    kin = (
        [
            k
            for k in geo.children(store).get(rec["within"], [])
            if k != ent_id and store[k]["area"]
        ]
        if rec["within"]
        else []
    )
    if kin:
        layers["kin"] = [p for k in kin
                         for p in geomap.owned(frame.paths(shape(store[k]["area"])),
                                               k, _kind(store[k]["area"]))]
    if parent and parent["area"]:
        layers["parent"] = geomap.owned(frame.paths(shape(parent["area"])),
                                        parent["id"], _kind(parent["area"]))

    # **What lies beneath, drawn.** For a node with no boundary of its own this
    # is the whole map — the Russian Far East is not a shape, and a frame with
    # nothing in it but two pins says less than the tree already did. For a node
    # that has one it is still the useful layer: the Kolyma showing the Anuis
    # and the Omolon inside it is the picture the hierarchy was authored for.
    members = geo.member_shapes(ent_id, store)
    if members:
        layers["members"] = [p for ent, s in members
                             for p in geomap.owned(frame.paths(shape(s)), ent,
                                                   _kind(s))]

    subject_doc = shape(rec["area"]) if rec["area"] else {}
    if subject_doc:
        layers["subject"] = geomap.owned(frame.paths(subject_doc), ent_id,
                                         _kind(rec["area"]))
        layers["rivers"] = frame.rivers(subject_doc)
    elif parent and parent["area"]:
        layers["rivers"] = frame.rivers(shape(parent["area"]))

    # **Every descendant that no other layer identifies, as an extent — drawn
    # only under the pointer.** A node with neither a shape nor a point is
    # skipped by `member_shapes`, which descends *through* it to the basins
    # below, so Chukotka appears nowhere on the Russian Far East's map and its
    # name lit up nothing. A box is what there is to draw for it, and a box on
    # every one of them at once is a field of rectangles over the thing you were
    # reading. So the layer is drawn transparent and only the highlight paints
    # it: the answer is there when the question is asked and not before.
    layers["extents"] = [p for ent, ebox in geo.member_extents(ent_id, store, root)
                         if (d := frame.viewport(ebox))
                         for p in geomap.owned([d], ent)]

    pins = []
    for lon, lat, label, ent in geo.pins_under(ent_id, store, root):
        p = frame.point(lon, lat)
        if p:
            pins.append((p[0], p[1], label, ent))

    if rec["area"]:
        row = geo.index(root)["shapes"].get(rec["area"], {})
        km2 = row.get("area_km2")
        out["basis"] = {
            "kind": "shape",
            "id": rec["area"],
            "km2": f"{int(km2):,}" if km2 else "",
            "source": row.get("source", ""),
        }
    elif rec["geo"]:
        out["basis"] = {
            "kind": "point",
            "lat": f"{rec['geo'][0]:.3f}",
            "lon": f"{rec['geo'][1]:.3f}",
        }
    else:
        out["basis"] = {"kind": "framed"}
    out["parent"] = parent
    # **`basin` is read off the shape's type, not the entity's class.** `area:`
    # is typed — `watershed:anadyr` names where the polygon came from — and "this
    # outline is a drainage divide" is a fact about the shape's provenance, not
    # about what kind of thing the record is. Today every `watershed:` in the
    # store happens to sit on a `water:` entity and the two predicates agree;
    # they are still different questions, and only this one answers why the
    # boundary must not be drawn in the colour of the rivers running inside it.
    # The members are left alone: they are the nearest descendants that have a
    # shape, chosen without reference to what drew them.
    mark = "basin" if (rec["area"] or "").startswith("watershed:") else ""
    out["svg"] = geomap.render(frame, layers, pins, mark=mark)
    return out



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
