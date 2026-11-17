"""What a reading-view page says about itself in its `<head>`: a description, its
canonical address, a link preview, citation tags and schema.org JSON-LD.

**Everything is read, nothing is stated here.** The book's title, author, imprint,
series, part dates, the licences and the address the edition is published at all
come from the corpus teiHeader, through `stores.work`; the picture is the text's
one declared `image`. A text whose header lacks a field emits no tag for it,
rather than one built from a default — a citation tag that names the wrong year
is fluent nonsense in exactly the place a reader trusts most.

**A page number is cited only where a page recorded its folio**, and a chapter's
first and last page only where its own first and last text leaves did. The folio
propagates through the seam ledger and nothing infers it (CLAUDE.md, page refs),
so a span with a missing end says nothing about that end.

**Absolute addresses only for a published text.** The canonical URL is the
header's `<ptr>` and the text's `site_base`, which is right on the host and on a
workstation alike — but only a text whose manifest says `publish` is at that
address, so an unpublished one carries none.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, unquote

from .. import layout, tei_html

#: Roughly what a search result shows. Cut at a word, not mid-word.
DESC_LEN = 160
#: The site's own name, for `og:site_name`, as the header's `<authority>` gives it
#: being one text's and not the site's.
SITE_NAME = "Plectrum Press"

#: Entity class → schema.org type. Only where the class says what the thing is;
#: the rest are `Thing`, which claims nothing.
SCHEMA_TYPES = {"person": "Person", "place": "Place", "land": "Place",
                "water": "Place", "river": "Place", "institution": "Organization"}


def clip(text: str, n: int = DESC_LEN) -> str:
    """`text`, whitespace folded, cut back to a word boundary at `n` with an ellipsis."""
    t = " ".join(text.split())
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0].rstrip(",;:—-– ")
    return cut + "…"


def first_paragraph(html: str) -> str:
    """The text of the first `<p>` in rendered page HTML that has words in it — what
    a chapter or a page describes itself by. Tags gone, entities decoded."""
    for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", html, flags=re.S):
        p = m.group(1)
        # A footnote marker is a number in the prose's middle, and noise here.
        p = re.sub(r'<a class="noteref"[^>]*>.*?</a>', "", p, flags=re.S)
        text = tei_html.strip_tags(p)
        if len(text.split()) >= 5:
            return text
    return ""


def _ld(obj: dict) -> str:
    """JSON for a `<script type="application/ld+json">`: `</` escaped, so a string
    in it cannot close the element."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _book(work: dict) -> dict:
    """The printed work, as schema.org has it. Only the fields the header holds."""
    book: dict = {"@type": "Book", "name": work["title"]}
    if work.get("author"):
        book["author"] = {"@type": "Person", "name": work["author"]}
    if work.get("publishers"):
        book["publisher"] = [{"@type": "Organization", "name": p} for p in work["publishers"]]
    if work.get("date"):
        # The volume's range, verbatim: schema.org has no range for `datePublished`,
        # and one year of the three would be a claim the title page does not make.
        book["dateCreated"] = work["date"]
    if work.get("series"):
        book["isPartOf"] = [{"@type": "PublicationVolume", "volumeNumber": s["volume"],
                             "isPartOf": {"@type": "CreativeWorkSeries", "name": s["title"]}}
                            if s["volume"] else {"@type": "CreativeWorkSeries", "name": s["title"]}
                            for s in work["series"]]
    return book


def _part(ref: str) -> str:
    """The part a `PP-NNN` ref is in."""
    return str(int(ref.split("-")[0]))


def head(root: Path, work: dict, path: str, base: str, *, title: str,
         description: str = "", draft: bool = False, kind: str = "website",
         cite: dict | None = None, entity: dict | None = None,
         links: dict[str, str] | None = None, noindex: bool = False) -> dict:
    """The head of one view, as `edition/_meta.html` renders it.

    `path` is the request's path and `base` the prefix it is mounted under, so the
    canonical address is the published one whatever this server mounts. `cite`
    asks for citation tags: `{title, refs, folios}`, the view's own title and its
    text leaves' refs and recorded folios, in order. `entity` is a store record.
    `links` is `rel → href` for `<link>`s: prev, next, up.
    """
    origin = work.get("origin") if layout.publish(root) else ""
    rel = path[len(base):] if base and path.startswith(base) else path
    # Spelled as the host serves it: `build._canon`'s quoting, under which a colon
    # is `%3A` — the host redirects a bare one there (`site/deploy/README.md`).
    rel = quote(unquote(rel), safe="/")
    canonical = f"{origin}{layout.site_base(root)}{rel or '/'}" if origin else ""
    cover = f"{layout.site_base(root) if origin else base}/cover-1200.jpg"
    image = layout.image(root)
    desc = clip(description) if description else ""
    if draft and desc:
        desc = clip("Uncollated transcription — " + desc)

    og = [("og:type", kind), ("og:title", title), ("og:site_name", SITE_NAME),
          ("og:locale", layout.lang(root).replace("-", "_"))]
    if desc:
        og.append(("og:description", desc))
    if canonical:
        og.append(("og:url", canonical))
    if image:
        og += [("og:image", f"{origin}{cover}"), ("og:image:alt", image["caption"])]
    names = [("twitter:card", "summary_large_image" if image else "summary")]
    if noindex:
        names.append(("robots", "noindex"))

    page: dict = {"@context": "https://schema.org", "@type": "WebPage", "name": title,
                  "isPartOf": {"@type": "WebSite", "name": SITE_NAME,
                               **({"url": origin + "/"} if origin else {})},
                  "inLanguage": layout.lang(root)}
    if canonical:
        page["url"] = canonical
    if desc:
        page["description"] = desc
    if work.get("licence_urls"):
        page["license"] = work["licence_urls"]
    if image:
        page["image"] = f"{origin}{cover}"
    book = _book(work)
    cites: list[tuple[str, str]] = []
    if cite is not None:
        refs, folios = cite["refs"], cite["folios"]
        chapter = {"@type": "Chapter", "name": cite["title"], "isPartOf": book}
        if folios and folios[0]:
            chapter["pageStart"] = str(folios[0])
        if folios and folios[-1]:
            chapter["pageEnd"] = str(folios[-1])
        page["mainEntity"] = chapter
        cites = _citation(work, cite["title"], refs, folios, canonical)
    elif entity is not None:
        page["mainEntity"] = _thing(entity)
    else:
        page["mainEntity"] = book
    return {"description": desc, "canonical": canonical, "og": og, "names": names,
            "citation": cites, "licences": work.get("licence_urls") or [],
            "links": sorted((links or {}).items()), "ld": _ld(page)}


def _citation(work: dict, title: str, refs: list[str], folios: list,
              canonical: str) -> list[tuple[str, str]]:
    """Highwire Press tags, which Google Scholar and Zotero read. One date: the
    part's, where the header records one for the part every ref is in; else none."""
    out = [("citation_title", title), ("citation_inbook_title", work["title"])]
    parts = work.get("author_parts") or {}
    if parts.get("surname"):
        out.append(("citation_author",
                    ", ".join(x for x in (parts["surname"], parts.get("forename", "")) if x)))
    in_parts = {_part(r) for r in refs}
    if len(in_parts) == 1:
        date = (work.get("parts") or {}).get(next(iter(in_parts)), {}).get("date")
        if date:
            out.append(("citation_publication_date", date))
    for p in work.get("publishers", [])[:1]:
        out.append(("citation_publisher", p))
    for s in work.get("series", []):
        out.append(("citation_series_title", s["title"]))
        if s["volume"]:
            out.append(("citation_volume", s["volume"]))
            break
    if folios and folios[0]:
        out.append(("citation_firstpage", str(folios[0])))
    if folios and folios[-1]:
        out.append(("citation_lastpage", str(folios[-1])))
    if canonical:
        out.append(("citation_public_url", canonical))
    return out


def _thing(rec: dict) -> dict:
    from .. import edition_ui as ui
    thing: dict = {"@type": SCHEMA_TYPES.get(rec.get("class", ""), "Thing"),
                   "name": rec["canonical"]}
    if rec.get("gloss"):
        thing["description"] = clip(_plain(rec["gloss"]))
    same = []
    for link in rec.get("links") or []:
        kind, _, val = link.partition(":")
        if kind in ui.LINK_KINDS and kind != "url" and val:
            same.append(ui.LINK_KINDS[kind][0].format(val))
    if same:
        thing["sameAs"] = same
    pts = [g for g in rec.get("geo") or [] if g.get("kind") == "point"]
    if thing["@type"] == "Place" and len(pts) == 1:
        thing["geo"] = {"@type": "GeoCoordinates",
                        "latitude": pts[0]["lat"], "longitude": pts[0]["lon"]}
    return thing


def _plain(md: str) -> str:
    """A gloss's Markdown, flattened: links to their text, emphasis marks gone."""
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    return re.sub(r"[*_`]", "", md)


def entity_description(rec: dict | None) -> str:
    return clip(_plain(rec["gloss"])) if rec and rec.get("gloss") else ""

