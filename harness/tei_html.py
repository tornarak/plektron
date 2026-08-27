"""Committed TEI, rendered as the reader's page.

**The first thing in this project that is for a reader rather than an editor**,
and the shape follows from that: a main column of text, and beside it a stack of
cards a click fills — the entity the link names, the lexicon form, the map, the
scan the line was read from. Nothing here writes anything.

Two audiences in one page, resolved by a toggle rather than by two renderers.
The apparatus is visible by default — an unratified span is marked, a
rule-applied link is marked, an editorial comment is a flag you can open —
because the people reading this now are auditing it. **Reader view** hides all of
it and leaves the text. Both are the same HTML with a class on the root, so the
audit view can never drift into showing something the reading view does not have.

**Crops are computed, never cut.** A figure or a line is the whole page raster,
scaled and offset inside a clipping box, in percentages — `crop_style` below.
The browser fetches one image per page however many crops the stack holds, and
nothing on disk has to be kept in step with the ALTO.

What this module does *not* do is decide anything. Every judgement it renders was
made by a collator and is in the file; where the file says a thing is unresolved,
this says so too rather than presenting a tidy page.
"""

from __future__ import annotations

import re
import unicodedata
from html import escape
from pathlib import Path
from urllib.parse import quote

from lxml import etree

from . import figrefs
from .ns import TEI_NS, XML_ID, XML_LANG
from .refs import norm_ref
from .seam import OPENS_MEANS
from .validate import TIER1

#: The languages a lexicon key may name. `validate.TIER1` and nothing else — the
#: forms this edition keys character by character are the ones worth an entry,
#: and a `lang:form` key over English would be a link to a dictionary.
LEXICON_LANGS = TIER1

_TAGS = re.compile(r"<[^>]+>")


def _lang_attr(lang: str) -> str:
    """` lang="ckt"`, or nothing at all where no language is known.

    An empty `lang=""` is not "no language" to a screen reader or a font stack —
    it is a claim that the element has no language, which is a different and
    wrong thing to say about a Chukchi word nobody has judged yet.
    """
    return f' lang="{escape(lang)}"' if lang else ""


#: Elements that may sit between a milestone and the block whose head it names,
#: without being that block. A figure is a **float**: the compositor set it where
#: it fitted on the leaf, which is routinely between a section boundary and the
#: paragraph that section opens with. `<pb/>` is the same case at a leaf edge.
_FLOATS = ("figure", "pb")


def _block_after(el):
    """The first sibling after `el` that could carry the printed head.

    Floats are stepped over rather than treated as the answer. Reading
    `getnext()` alone made an intervening figure mean "the page printed no head",
    which is a statement about typesetting read off an accident of placement.
    """
    for nxt in el.itersiblings():
        # Comments and processing instructions have a callable `tag`; the
        # generator writes several per page, including right after a milestone.
        if not isinstance(nxt.tag, str):
            continue
        if etree.QName(nxt).localname in _FLOATS:
            continue
        return nxt
    return None


def _leads_a_block(el) -> bool:
    """Does the block after this milestone open with the printed head?

    **Evidence, not level.** The obvious rule is "levels 3 and 4 are run-in", which
    is how this book sets them — but it would be the ToC deciding what the page
    did, and a chapter head the compositor ran into its first paragraph would then
    be set twice. What actually decides is whether the head is *there*: a `<label>`
    at the front of the next block is the generator saying it found one, and its
    absence is the generator saying the block held nothing but the heading. Depth
    still governs how each level sets; it does not govern whether the words exist.

    **"Next" means the next block, not the next sibling** (`_block_after`), and
    `1-242` is why. There the milestone is followed by Fig. 103 and only then by
    `<p><label>KETTLE.</label> — The old women still have a vivid recollection …`,
    so the figure was read as the answer, the page was judged to print no head,
    and KETTLE was set twice — once as an `<h2>` off the ToC and once as the
    compositor's own run-in label. The evidence rule was right; it was being asked
    of the wrong element.
    """
    nxt = _block_after(el)
    if nxt is None:
        return False
    first = next(iter(nxt), None)
    if etree.QName(nxt).localname == "quote" and first is not None:
        first = next(iter(first), None)  # <quote><p><label>
    return (
        first is not None
        and etree.QName(first).localname == "label"
        and not (nxt.text or "").strip()
    )


def _is_tier1(el) -> bool:
    """Does this span hold a form the lexicon keys?

    **Two ways to be one, and the second is why a draft page links.** A judged
    span says so: `xml:lang` in `TIER1`. An *unjudged* one is the generator's
    handle — a lang-less element carrying `@index`, which `tier1_terms` put
    there off adjudicated ground truth. The glyphs in it are as settled as the
    collated page's; the only thing missing is the language, and the lexicon
    does not key on language.

    So the discriminator is `@index` and not "has no language". `<foreign
    xml:lang="de">Döring</foreign>` is a foreign span this edition does not key,
    and a rule that linked every lang-less `<foreign>` would eventually link
    that too — the detector fires on a combining diaeresis exactly as on a
    Chukchee form, which is the standing case the generator's own docstring
    names.
    """
    lang = el.get(XML_LANG)
    if lang is not None:
        return lang in LEXICON_LANGS
    return el.get("index") is not None


#: Blocks that are not the prose flow, and so do not decide how the page opens. A
#: figure at the head of a leaf sits above a paragraph that may still be carrying
#: over from the page before; the `<pb>` is the page itself.
_NOT_FLOW = {"pb", "figure"}


def first_flow(body):
    """The first element of `<body>` that is part of the prose flow, or None.

    A heading counts and a figure does not, which is the distinction the question
    "does this page open a paragraph" turns on: a head *is* a break, and a plate
    at the top of a leaf says nothing about the paragraph running underneath it.
    """
    for el in body:
        if isinstance(el.tag, str) and etree.QName(el).localname not in _NOT_FLOW:
            return el
    return None


def page_opens(body) -> str:
    """`fresh`, `continued` or `unwitnessed` — does a paragraph *begin* on this page?

    **The store says, and until this the rendering guessed.** Three witnesses can
    answer, and they are ranked by how much human judgement is behind them:

    1. `@part`/`@prev` on the page's first flow element, which `tei seam` wrote
       after a human adjudicated the gap. `F`/`M`/`@prev` means the element began
       earlier; `I` means it begins here. **Absence is not `I`** — `seam._apply`
       drops the attribute for a closed gap exactly as an unwritten seam leaves it
       absent, so the two are indistinguishable here and absence falls through to
       the witness that can tell them apart rather than asserting a break.
    2. `<!-- opens: … -->`, the collator's measurement of the first line's indent
       off the raster.
    3. `<!-- zone-opens: … -->`, off the keyed zone label — `MainZone-Continued`
       or not. Human-rank too: a segmentation act, months earlier.

    Where they disagree the adjudicated one wins, and `tei seam` is what reports
    the disagreement; deciding it is not a renderer's business. Where none of them
    speaks, `unwitnessed` — which the stylesheet sets flush, because 305 of the 399
    drafts say `continued` and an indent claims a break the print may not have.
    """
    if (el := first_flow(body)) is not None:
        if el.get("prev") or (el.get("part") or "") in ("F", "M"):
            return "continued"
        if el.get("part") == "I":
            return "fresh"
    seen = {}
    for c in body.iter(etree.Comment):
        t = " ".join((c.text or "").split())
        for key, mark in (("zone-opens:", "zones"), ("opens:", "reader")):
            if t.startswith(key) and mark not in seen:
                seen[mark] = t[len(key) :].split("(")[0].strip()
                break
    # `seam.OPENS_MEANS`, not a second copy of it: `no witness` — a leaf opening
    # on a heading — is absent from it there and falls through here for the same
    # reason, being a third answer rather than a missing one.
    if (v := OPENS_MEANS.get(seen.get("reader", ""))) is not None:
        return v
    if (v := seen.get("zones")) in ("fresh", "continued"):
        return v
    return "unwitnessed"


def strip_tags(html: str) -> str:
    """The text of a rendered fragment, for building a key out of it.

    A Tier-1 span can carry `<unclear>` inside it, so the key has to come from
    the text and not from the markup around it.
    """
    return " ".join(_TAGS.sub("", html).split())


#: Where the reading view is mounted. The four browser tools share one server,
#: so a bare `/entity/…` here would resolve against whichever of them owned the
#: root — the links in the page body would leave the edition. Kept beside
#: `edition_ui.BASE`, which has to agree with it.
BASE = "/edition"

#: What each rank means to a reader, and how visible it should be. The three that
#: mean "a human settled this" are quiet; the two that do not are marked, because
#: the whole point of showing provenance is that unfinished work looks unfinished.
RANK_NOTE = {
    "#ed": ("ratified", "a human keyed or confirmed this against the page"),
    "#gt": ("adopted", "keyed at the raster in the ground-truth pass"),
    "#llm": ("proposed", "a model read this off the page; awaiting ratification"),
    "#mz": (
        "mechanical",
        "applied by rule from a store a human keyed — the entity "
        "alias table, or the printed table of contents",
    ),
}
UNSETTLED = ("#llm", "#mz")


def page_path(ref: str, root: Path = Path(".")) -> Path:
    return root / "tei" / f"chukchi-{norm_ref(ref)}.xml"


def draft_path(ref: str, root: Path = Path(".")) -> Path:
    """The generated page. Named, never linked: `tei/` is a store and not a view
    over this one, and `test_tei_is_a_store_and_never_a_farm` holds the pair apart.
    A caller that wants the generated file says so here."""
    return root / "mz" / "tei" / f"chukchi-{norm_ref(ref)}.xml"


def _sorted_refs(refs) -> list[str]:
    return sorted(set(refs), key=lambda r: tuple(int(x) for x in r.split("-")))


def _refs_in(d: Path) -> list[str]:
    if not d.is_dir():
        return []
    return [p.stem.replace("chukchi-", "") for p in d.glob("chukchi-*.xml")]


def collated(root: Path = Path(".")) -> list[str]:
    """Every committed page, in scan order. The edition is what is in `tei/`.

    Signed pages only, deliberately, and it stays that way: this is what the CLI
    banner counts, what `tei expand`/`tei ids` sweep with no refs, and what the
    reading view lists by default. `readable` is the wider set, and the two are
    separate functions rather than one with a flag because every caller here means
    one or the other and none means "whichever".
    """
    return _sorted_refs(_refs_in(root / "tei"))


def page_source(ref: str, root: Path = Path(".")) -> tuple[Path | None, str]:
    """Which file renders this page, and what rank it carries: the signed page if
    there is one, else the generated draft, else nothing.

    **The rank travels with the answer** rather than being inferable from the path
    by whoever receives it. That is the property the symlink farm destroyed — a
    link into `mz/tei/` let a draft answer to a signed page's name, and nothing
    downstream could tell. Here a caller cannot obtain the path without also being
    handed `"collated"` or `"draft"`, so a view that renders one must decide what
    to say about it.

    Precedence is signed-wins, which is `ocr/`'s rule and not a new one. What is
    new is that the loser stays reachable: a draft is not a worse reading of the
    same page, it is the page before anybody read it, and `tei diff` is the tool
    that compares them.
    """
    signed = page_path(ref, root)
    if signed.exists():
        return signed, "collated"
    draft = draft_path(ref, root)
    if draft.exists():
        return draft, "draft"
    return None, "absent"


def readable(root: Path = Path(".")) -> list[str]:
    """Every page that can be rendered at all, signed or generated, in scan order.
    The union: a page collated from a draft appears once, under `collated`'s rank.
    """
    return _sorted_refs(_refs_in(root / "tei") + _refs_in(root / "mz" / "tei"))


def exempt(root: Path = Path(".")) -> list[str]:
    """Pages a human ruled not a text page, in scan order.

    These reach the reader as themselves rather than as prose. `dispatch.py`
    refuses them for both the ground-truth and the collation tracks — the ruling
    is a statement, not an absence — so no amount of transcription will ever
    produce a `tei/` page for one, and leaving them out of the edition would drop
    every plate, foldout and piece of front matter out of the book silently.

    **The ruling is the zone track's and so is the kind** — `zones.LEAF_KINDS`,
    written by a human in `zones edit` at the raster. This reports membership;
    `leaf_kind` reports which. Nothing here derives the kind, and that boundary is
    the point: the edition used to sort these pages with four discriminators
    borrowed from other stores — figure boxes for a plate, `edition/runs.json` for
    the apparatus, `edition/page-img/` for a hand-worked leaf — under which a blank
    verso and the volume's folding map were the same page.
    """
    from .zones import LEAF_KINDS, load_splits

    return _sorted_refs(
        r for r, split in load_splits(root).items() if split in LEAF_KINDS
    )


def leaf_kind(ref: str, root: Path = Path(".")) -> str:
    """What a human ruled this leaf, or `""` for a page still in the tracks.

    A separate reader from `exempt` because the two are asked at different moments
    — the listing wants the set, a page wants its own kind — and because a caller
    holding `""` must not be able to mistake it for a kind. There is no
    `unclassified`: an unmarked page is not a leaf at all.
    """
    from .zones import LEAF_KINDS, load_splits

    marked = load_splits(root).get(norm_ref(ref), "")
    return marked if marked in LEAF_KINDS else ""


def crop_style(
    box: tuple[int, int, int, int], size: tuple[int, int], pad: int = 12
) -> dict:
    """The CSS placing one box of a page raster inside a clipping frame.

    **Every number is a ratio**, which is the whole design. A crop scaled to a
    fixed pixel width keeps that width inside a panel that is almost never that
    wide, so the right-hand end of every crop is cut off and how much you can see
    depends on the browser window. Percentages resolve against the frame, and
    because the frame carries the crop's own `aspect-ratio` the two axes stay in
    the source's proportion at any size.

    Learned from the Moll dictionary's reader, which had the pixel version first.
    """
    iw, ih = size
    x0 = max(0, box[0] - pad)
    y0 = max(0, box[1] - pad)
    x1 = min(iw, box[2] + pad)
    y1 = min(ih, box[3] + pad)
    cw, ch = max(1, x1 - x0), max(1, y1 - y0)
    return {
        "outer": f"aspect-ratio:{cw}/{ch}",
        "inner": (
            f"width:{iw / cw * 100:.4f}%;"
            f"left:{-x0 / cw * 100:.4f}%;"
            f"top:{-y0 / ch * 100:.4f}%"
        ),
    }


def _rank_marks(el) -> tuple[str, str]:
    """The class and the tooltip a `@resp` earns, or empty strings for none."""
    resp = el.get("resp")
    if resp not in RANK_NOTE:
        return "", ""
    short, why = RANK_NOTE[resp]
    cls = " rank" + (" unsettled" if resp in UNSETTLED else "")
    return cls, f"{short} — {why}"


class Renderer:
    """One page's TEI to HTML. Stateful only in what it collects for the stack.

    `notes` and `refs` come out alongside the markup: the note bodies so the foot
    of the page can print them where the print did, and the entity ids so the
    page knows which cards it may be asked for without re-parsing itself.
    """

    def __init__(
        self, ref: str, tabindex_offset: int = 2, titles: dict[str, dict] | None = None
    ):
        self.ref = ref
        self.tabindex = tabindex_offset
        #: `{toc id: {number, title}}`, what a `<milestone n>` is displayed as.
        #: Passed in rather than read here so the caller's cache can name
        #: `edition/toc.json` among its inputs — a title that changed under a memoised
        #: render would otherwise serve a stale heading with nothing to signal it,
        #: which is `stores.render`'s standing rule about the figure geometry.
        self.titles = titles or {}
        self.notes: list[dict] = []
        #: Note numbers already referenced on this page, so the first
        #: reference to each can carry the id the foot links back to.
        self.noterefs: set[str] = set()
        self.refs: list[str] = []
        self.forms: list[str] = []
        #: `{n, i}` per `<figure>`, in document order — the handles the route
        #: needs to hang the right pictures on the right block. Was a list of
        #: bare numbers, which could not name the ten figures that print none.
        self.figures: list[dict] = []
        #: True while rendering the body of an element that carries a `@ref`.
        #: An anchor inside an anchor is not markup HTML has, so the entity link
        #: is the one that survives and a Tier-1 handle inside it renders flat.
        self.in_ref = False
        #: `{kind, number, plate}` per marked cross-reference in the prose, in
        #: document order. **Handles, not answers** — where each one points is
        #: `web/edition._figref_state`'s, for `el_figure`'s reason. Read off the
        #: page's own `<ref>` marks by `el_ref`, never scanned out of the served
        #: text: a link nobody could review is the thing that arrangement fixed.
        self.figrefs: list[dict] = []
        #: True while rendering a `<figDesc>`. A caption reading `Fig. 101.
        #: Reindeer-Harness` is the figure's own name, not a pointer at it, and
        #: linking a picture to itself is noise on every illustrated page.
        self.in_figdesc = False
        #: How the page opens, and the element that opens it — set by `render`
        #: from the page's own witnesses. `page_first` is identity-compared, so a
        #: paragraph nested in a `<quote>` can never be mistaken for the one that
        #: opens the leaf.
        self.opens = "unwitnessed"
        self.page_first = None
        #: The block's plain text so far, which is what `figrefs` looks back
        #: through for the authority that owns a cited plate. Kept here rather
        #: than passed down because the name and the reference are often in
        #: different elements — `<bibl>Sauer</bibl>, Plate XIV`.
        self.seen = ""

    # -- inline ------------------------------------------------------------

    def inline(self, el) -> str:
        """An element's children, marked up. Recursive; text nodes are escaped."""
        out = []
        if el.text:
            out.append(self.text(el.text))
        for kid in el:
            if not isinstance(kid.tag, str):
                if kid.tag is etree.Comment:
                    out.append(self.comment(kid))
                if kid.tail:
                    out.append(self.text(kid.tail))
                continue
            out.append(self.element(kid))
            if kid.tail:
                out.append(self.text(kid.tail))
        return "".join(out)

    def text(self, s: str) -> str:
        """A text node, escaped, and accumulated for what looks back through it.

        **The cross-references are not found here any more.** They are marked in
        the page by `tei generate` and rendered by `el_ref`, which is what makes
        one auditable: found here they existed only in served HTML, where the
        collator reviewing the page never met one and `tei validate` had nothing
        to say about it. `self.seen` is still kept, because the authority guard
        downstream reads the prose in front of a reference and the name is often
        in an element of its own — `<bibl>Sauer</bibl>, Plate XIV`.
        """
        self.seen += s
        return escape(s)

    def el_ref(self, el) -> str:
        """A marked cross-reference, as a handle the route points somewhere.

        **The handle says what the page marked and nothing more** — the kind, the
        number, and the plate that scopes it, read straight off the attributes
        `figrefs.mark` wrote. Which picture that is depends on `gt/fig/`, which
        `stores.render`'s cache does not name, so resolving here would go on
        serving a link to a box somebody has since moved. Same division as
        `<figure>`: the renderer emits the handle and `web/edition._figref_state`
        joins it, where both keys are in hand.

        **`before` rides along, and that is what keeps this store-free.** Some of
        these plates are other people's — `Sauer, Plate XIV` is Sauer's, and this
        book has a Plate XIV too. `tei generate` already refuses to *mark* one,
        so a marked page carries none; a page a collator marked by hand is not
        bound by that, and the route makes the same call with the store in hand.

        A reference inside an entity link renders flat: an anchor inside an
        anchor is not markup HTML has, and `_referring`'s note applies unchanged.
        So does one whose attributes do not spell a reference — `validate` errors
        on that, so it reaches no collated page, and a draft showing it as text
        is the honest rendering of a mark nothing can read.
        """
        # Taken before the body is rendered: `inline` feeds the numeral itself
        # into `seen`, and the guard reads what stands *in front of* a reference.
        before = self.seen[-160:]
        body = self.inline(el)
        # **A note reference is this book's own and resolves on this page.** It
        # goes to `#note-N` and never through `figrefs`, whose handle is a join
        # over `gt/fig/`; there is nothing to join here, the number the printer
        # set being the whole of the address. The marker itself is the body — the
        # character the compositor put in the sentence — so nothing is drawn that
        # the page does not print.
        if el.get("type") == "note" and not self.in_ref and not self.in_figdesc:
            n = el.get("n") or ""
            # **The first reference carries the id the foot links back to.** A
            # note may be referenced more than once — `1-147` prints one against
            # two markers — so "the" reference does not exist; the first is where
            # the reader met it, and every later one still links forward.
            first = n not in self.noterefs
            self.noterefs.add(n)
            back = f' id="ref-{escape(n)}"' if first else ""
            return (
                f'<a class="noteref"{back} href="#note-{escape(n)}" '
                f'data-note="{escape(n)}">{body}</a>'
            )
        handle = figrefs.unmark(el.get("type"), el.get("n"), el.get("cRef"))
        if handle is None or self.in_ref or self.in_figdesc:
            return body
        # **A page reference is an address, not a join, so it links from here.**
        # `/folio/{n}` is the route every other folio link in the edition already
        # goes through, and it answers for itself: a folio no leaf witnesses gets
        # the route's refusal page, which says so, rather than a link this
        # renderer had to consult a store to decide not to draw. That is what
        # keeps the division `el_ref` opens with intact — nothing here is
        # invalidated by a box moving, because no box is involved.
        if handle["kind"] == "page":
            return (
                f'<a class="pageref" target="_blank" href="{BASE}/folio/'
                f'{escape(handle["number"])}">{body}</a>'
            )
        # A chapter, the same way and for the same reason — `/chapter/{roman}`
        # looks the id up in `edition/toc.json` and locates its opening folio, so
        # nothing about the store's key scheme is written into the page.
        if handle["kind"] == "chapter":
            return (
                f'<a class="chapref" target="_blank" href="{BASE}/chapter/'
                f'{quote(handle["number"], safe="")}">{body}</a>'
            )
        i = len(self.figrefs)
        self.figrefs.append(dict(handle, before=before))
        return f'<a class="figref" data-fr="{i}" tabindex="0">{body}</a>'

    def comment(self, node) -> str:
        """An editorial comment, as a flag that opens rather than as invisible text.

        A collator's unanswered question is *in* the file and is the honest state
        of the page; hiding it in the rendering would make an unfinished page
        look finished, which is the one thing this edition is organised against.
        Reader view hides them; the audit view does not.
        """
        text = " ".join((node.text or "").split())
        if not text:
            return ""
        kind = (
            "question"
            if text.startswith(
                ("unresolved", "entity candidate", "entity wanted", "generator:")
            )
            else "editorial"
        )
        return (
            f'<span class="flag {kind}" tabindex="0" '
            f'title="{escape(text)}">?</span>'
        )

    def element(self, el) -> str:
        name = etree.QName(el).localname
        fn = getattr(self, f"el_{name}", None)
        if fn is not None:
            return fn(el)
        return self.inline(el)  # unknown element: keep its text, drop it

    # -- inline elements ---------------------------------------------------

    def _tier1(
        self,
        el,
        body: str,
        cls: str,
        why: str,
        extra: str = "",
        base: str = "tier1 lex",
    ) -> str:
        """A Tier-1 span as a link into the lexicon, or a plain span if it is not one.

        **The key is the bare form**, url-encoded on the way out, because that is
        the lexicon's identity: an entry carries no language, since a form only
        becomes `ckt` when a collator judges it. The language rides as `lang=`
        where one is known and changes nothing about which card opens — so the
        same word reached from a collated page and from a generated draft is one
        card, which is the whole point of keying it this way.

        `lang:form` used to be the key and still resolves; the route accepts all
        three spellings.
        """
        lang = el.get(XML_LANG) or ""
        if not _is_tier1(el) or not body.strip():
            return (
                f'<span class="tier1{cls}"{_lang_attr(lang)} '
                f'title="{escape(why)}"{extra}>{body}</span>'
            )
        key = unicodedata.normalize("NFD", strip_tags(body))
        self.forms.append(key)
        # Inside an entity reference the enclosing `<a>` is the link, so this is
        # a span. `data-key` stays on it: the form is still what it is, and the
        # index of forms above is what `lexicon` counts, so neither the styling
        # nor the census changes — only which of two nested anchors survives.
        if self.in_ref:
            return (
                f'<span class="tier1{cls}"{_lang_attr(lang)} '
                f'data-key="{escape(key)}" title="{escape(why)}"{extra}>'
                f"{body}</span>"
            )
        return (
            f'<a class="{base}{cls}"{_lang_attr(lang)} '
            f'href="{BASE}/lexicon/{quote(key, safe="")}" '
            f'data-key="{escape(key)}" title="{escape(why)}"{extra}>'
            f"{body}</a>"
        )

    def el_foreign(self, el) -> str:
        cls, why = _rank_marks(el)
        # An empty handle is a generated page's unanswered question. It should
        # not reach `tei/` at all — the gate refuses a lang-less <foreign> — so
        # if one is here, say so rather than rendering nothing.
        body = self.inline(el)
        if not body.strip():
            return (
                '<span class="flag question" title="an unfilled handle — '
                'this page was committed with a question open">◌</span>'
            )
        return self._tier1(el, body, cls, why)

    def el_term(self, el) -> str:
        ident = el.get(XML_ID) or ""
        cls, why = _rank_marks(el)
        body = self.inline(el)
        extra = f' id="{escape(ident)}"' if ident else ""
        if _is_tier1(el):
            return self._tier1(el, body, cls, why, extra)
        return f'<span class="term{cls}"{extra} title="{escape(why)}">{body}</span>'

    def el_gloss(self, el) -> str:
        target = (el.get("target") or "").lstrip("#")
        return (
            f'<span class="gloss" data-target="{escape(target)}">'
            f"{self.inline(el)}</span>"
        )

    def el_name(self, el) -> str:
        """A name: the entity it refers to, or — failing that — its lexicon entry.

        **A Tier-1 `<name>` used to reach neither.** `el_term` and `el_foreign`
        both route a Tier-1 span through `_tier1`, and this one went straight to
        `_referring`, which renders a plain `<span>` when there is no `@ref`. So
        a native toponym the store has no entry for was the one kind of Tier-1
        span on a page that linked nowhere at all, and 1-359 is a page of them.

        The order is the same one the nested-anchor fix settled: an entity
        reference is the more specific claim and wins where there is one, and
        the lexicon is what a form falls back to. Both are a link; what changes
        is where it goes.
        """
        if el.get("ref") or not _is_tier1(el):
            return self._referring(el, "name", el.get("type") or "")
        cls, why = _rank_marks(el)
        typ = el.get("type") or ""
        return self._tier1(
            el,
            self.inline(el),
            cls,
            why,
            extra=f' data-type="{escape(typ)}"',
            base="name tier1 lex",
        )

    def el_rs(self, el) -> str:
        return self._referring(el, "rs", "")

    def _referring(self, el, kind: str, typ: str) -> str:
        ref = el.get("ref") or ""
        cls, why = _rank_marks(el)
        # **The entity link wins over the lexicon link, and it has to.** A
        # Tier-1 handle inside an `<rs>` is the normal case — `tei generate`
        # encloses the handle rather than reaching into it — and both renderers
        # were emitting an `<a>`, which is an anchor inside an anchor. HTML has
        # no such thing: the parser closes the outer one, so the entity link was
        # discarded by the browser and every linked native toponym read as a
        # lexicon entry. The inner span keeps its class and `data-key`, so the
        # form is still styled as Tier-1 and still previewable, and the card it
        # opens lists its own aliases as lexicon links.
        inside, self.in_ref = self.in_ref, bool(ref)
        try:
            body = self.inline(el)
        finally:
            self.in_ref = inside
        if not ref:
            return f'<span class="{kind}" data-type="{escape(typ)}">{body}</span>'
        self.tabindex += 1
        tabindex = self.tabindex
        self.refs.append(ref)
        # A link, not a button: it has a URL that works on its own, and the JS
        # intercepts it to fill the stack instead of navigating. Middle-click and
        # "open in new tab" keep working, which is what a reader expects of
        # something that looks like a link.
        return (
            f'<a class="{kind} ent{cls}" tabindex="{tabindex}" href="{BASE}/entity/{escape(ref)}" '
            f'data-ref="{escape(ref)}" data-type="{escape(typ)}" '
            f'title="{escape(why or ref)}">{body}</a>'
        )

    def el_unclear(self, el) -> str:
        return (
            f'<span class="unclear" title="the letterform did not decide">'
            f"{self.inline(el)}</span>"
        )

    def el_supplied(self, el) -> str:
        why = el.get("reason") or ""
        return (
            f'<span class="supplied" title="supplied — {escape(why)}">'
            f"{self.inline(el)}</span>"
        )

    def el_measure(self, el) -> str:
        return (
            f'<span class="measure" data-type="{escape(el.get("type") or "")}">'
            f"{self.inline(el)}</span>"
        )

    def el_measureGrp(self, el) -> str:
        return f'<span class="measure-grp">{self.inline(el)}</span>'

    def el_bibl(self, el) -> str:
        return f'<span class="bibl">{self.inline(el)}</span>'

    def el_emph(self, el) -> str:
        return f"<em>{self.inline(el)}</em>"

    def el_hi(self, el) -> str:
        return f"<em>{self.inline(el)}</em>"

    def el_note(self, el) -> str:
        """A note is a body at the foot, and contributes nothing where it stands.

        The print set them at the foot and the page now encodes them there, so
        this collects the text and emits no markup in the flow: the marker is a
        `<ref type="note">` back in the sentence, and `el_ref` draws it.

        **It used to emit the marker from here**, because the generator spliced
        each note into the prose at the character it anchored to. Left as it was,
        the superscripts would now all render *at the foot*, in a row, in front
        of their own note bodies — the one arrangement that is wrong in both
        places at once.
        """
        n = el.get("n") or str(len(self.notes) + 1)
        i = len(self.notes) + 1
        self.notes.append({"n": n, "i": i, "html": self.inline(el)})
        return ""

    def el_figure(self, el) -> str:
        """A figure becomes a real block with its caption, and no geometry.

        **The caption used to be dropped outright** — this method never called
        `inline`, so the `<figDesc>` the generator had gone to `gt/fig/`
        for reached the reader as nothing at all, behind a `[fig. N]` chip.

        **No coordinates are emitted here, and that is a cache argument as much
        as a store one.** `stores.render`'s key names every store this HTML is
        built from — the page, and `edition/toc.json` for a milestone's title — and
        `gt/fig/` is deliberately not among them; geometry baked into this HTML
        would leave a corrected box serving the old placement out of a cache with
        nothing to signal it. So the page carries only what the TEI says, the route joins
        the pictures in against a key that includes `gt/fig/`, and the two facts
        stay keyed to the stores they came from.

        `data-n` is the printed number and is the handle: over the whole store no
        page has two figures with the same one. `data-i` is document order and
        exists for the ten figures whose caption prints no number — the generator
        emits those as a bare `<figure/>` with no attribute at all, so without it
        they would have no handle whatever. Neither is a claim about geometry.
        """
        n = el.get("n") or ""
        i = len(self.figures)
        self.figures.append({"n": n, "i": i})
        desc = el.find(f"{{{TEI_NS}}}figDesc")
        outside, self.in_figdesc = self.in_figdesc, True
        try:
            cap = (
                "" if desc is None else f"<figcaption>{self.inline(desc)}</figcaption>"
            )
        finally:
            self.in_figdesc = outside
        return (
            f'<figure class="figure" data-figure="{escape(n)}" data-i="{i}">'
            f"{cap}</figure>"
        )

    # -- block elements ----------------------------------------------------

    def el_p(self, el) -> str:
        # **The one paragraph on the page whose indent is not the default.** It
        # carries what `page_opens` read out of the store, and the stylesheet
        # decides what an indent looks like — so a page that opens a paragraph is
        # set as the compositor set it, and one that carries over stays flush.
        # Any other paragraph is a break by construction and needs no mark.
        if el is self.page_first:
            return f'<p class="opens-{self.opens}">{self.inline(el)}</p>'
        return f"<p>{self.inline(el)}</p>"

    def el_quote(self, el) -> str:
        return f"<blockquote>{self.blocks(el)}</blockquote>"

    def el_head(self, el) -> str:
        return f"<h3>{self.inline(el)}</h3>"

    def el_milestone(self, el) -> str:
        # A milestone is a boundary, not a container — TEI's answer to a heading
        # in a text with no divisions keyed. It carries no text by design: the
        # words are in `edition/toc.json` under the id `@n` names, and putting them
        # on the page is this module's job rather than the page file's. A page
        # that repeated the title would be a second copy of it, free to drift.
        #
        # The id is the fallback and not the label. `chVII.13` on a reading page
        # is visibly not a heading, which is the right way for a milestone whose
        # entry has gone missing to fail — a plausible-looking heading built from
        # a slug would not be.
        # **The number is the book's own and the rest is not invented.** 23 of the
        # ToC's 316 entries carry a printed `number` and they are exactly the
        # chapters; the 290 sections and subsections print none. Composing one for
        # them — `VI.2` for the second subsection of chapter VI — would be a
        # numeral this book never sets, arriving in the one place a reader would
        # cite. So a chapter is numbered and a section is not, which is what the
        # page does.
        #
        # Number and title are separate spans, and the punctuation between them is
        # the stylesheet's. The print sets `XI. — GAMES.`; whether the reading view
        # reproduces that or sets the numeral apart is typography, and typography
        # made of `::after` can change without touching what the page asserts.
        n = el.get("n") or ""
        unit = el.get("unit") or ""
        if _leads_a_block(el):
            # **The page already prints this one, so nothing is printed here.**
            # The book sets its deeper heads run-in — `SEAL-HUNTING. — The
            # Maritime Chukchee support themselves …` — and the generator marks
            # that head as `<label>` where it stands. Emitting a block heading too
            # would set the same heading twice, once from the page and once from
            # the ToC. So this is an anchor: the boundary is still in the document
            # and still linkable, and the words stay the ones the compositor set.
            return f'<span class="milestone anchor {escape(unit)}" id="{escape(n)}"></span>'
        label = self.titles.get(n) or {}
        if not label:
            # The id, unstyled, when the ToC has no such entry. Visibly not a
            # heading — which is how a milestone whose entry went missing should
            # fail, a plausible one built out of a slug being the failure this
            # project is arranged against.
            return f'<h2 class="milestone {escape(unit)}" id="{escape(n)}">{escape(n)}</h2>'
        num = (
            f'<span class="milestone-n">{escape(label["number"])}</span>'
            if label.get("number")
            else ""
        )
        return (
            f'<h2 class="milestone {escape(unit)}" id="{escape(n)}">{num}'
            f'<span class="milestone-t">{escape(label["title"])}</span></h2>'
        )

    def el_list(self, el) -> str:
        kind = el.get("type") or ""
        items = "".join(
            self.element(k)
            for k in el
            if isinstance(k.tag, str)
            and etree.QName(k).localname in ("item", "head", "label")
        )
        tag = "ol" if any(k.get("n") for k in el) else "ul"
        return f'<{tag} class="list-{escape(kind)}">{items}</{tag}>'

    def el_item(self, el) -> str:
        n = el.get("n")
        val = f' value="{escape(n)}"' if n and n.isdigit() else ""
        return f"<li{val}>{self.inline(el)}</li>"

    def el_label(self, el) -> str:
        """A gloss list's term, or a heading the compositor ran into its paragraph.

        Two things share the element because TEI's `<label>` is both, and the
        parent tells them apart: in a `<list>` it is the term half of an entry and
        renders as one, and in running prose it is the run-in head the ToC join
        marked, which sets as the milestone beside it says. Branching on the
        parent rather than adding a `@type` keeps the page free of a distinction
        the tree already makes.
        """
        parent = el.getparent()
        if parent is not None and etree.QName(parent).localname == "list":
            return f'<li class="label">{self.inline(el)}</li>'
        return f'<span class="runin">{self.inline(el)}</span>'

    def el_table(self, el) -> str:
        """A table, and **its `<head>` as the caption**.

        The head used to be dropped: this filtered its children to `row` and
        nothing else, so a `<head>` on a table validated, sat in the file, and
        rendered as nothing. `el_list` had always kept its own. 1-359 is where
        it showed — seven tables whose only titles are their heads, so the page
        rendered as seven untitled grids and the markup said otherwise with no
        error anywhere between them.

        `<caption>` rather than a heading above the table, because that is what
        HTML has for exactly this and it stays attached when the table scrolls.
        It must be the table's first child, which is why the head is emitted
        ahead of the rows rather than in document order.

        **Nothing is filtered out.** The schema ends `<table>` with
        `model.divBottom`, so a `<trailer>` is legal there and would have gone
        the same way the head did. `element()` already promises that an element
        it does not know keeps its text; a filter here defeated that promise
        before the fallback could run, which is what made the loss silent. So
        every child is rendered — head as the caption, rows inside the table,
        and anything else after it, since HTML admits no other element between
        `<table>` and `<tr>`.
        """
        head, rows, after = [], [], []
        for k in el:
            if not isinstance(k.tag, str):
                continue
            name = etree.QName(k).localname
            if name == "head":
                head.append(f"<caption>{self.inline(k)}</caption>")
            elif name == "row":
                rows.append(self.element(k))
            else:
                after.append(self.element(k))
        return f"<table>{''.join(head)}{''.join(rows)}</table>" f"{''.join(after)}"

    def el_trailer(self, el) -> str:
        return f'<p class="trailer">{self.inline(el)}</p>'

    def el_row(self, el) -> str:
        cells = "".join(
            self.element(c)
            for c in el
            if isinstance(c.tag, str) and etree.QName(c).localname == "cell"
        )
        return f"<tr>{cells}</tr>"

    def el_cell(self, el) -> str:
        # TEI spells the spans `@cols`/`@rows`; HTML spells them `colspan`/
        # `rowspan`. Dropped, a cell the print runs across the measure — 1-359's
        # "Cape Alutorsky, Cape Anannon", which has no Russian equivalent —
        # renders in the first column and silently misaligns the row.
        tag = "th" if el.get("role") == "label" else "td"
        span = "".join(
            f' {html_attr}="{escape(v)}"'
            for tei_attr, html_attr in (("cols", "colspan"), ("rows", "rowspan"))
            if (v := el.get(tei_attr)) and v.isdigit()
        )
        return f"<{tag}{span}>{self.inline(el)}</{tag}>"

    def el_pb(self, el) -> str:
        """Nothing in the text. The folio is reported in `render`'s `folio` and
        the page navigation prints it beside the scan ref.

        **It used to be a `float:right` span in the margin, and a float in the
        running text is what it could not go on being.** A figure floated to the
        head of a page tucked in beside it and shouldered it out of the corner,
        and the fix is not to make the two floats negotiate: a folio is not part
        of the prose, it identifies the page, and the place a reader looks for
        page identity is the navigation that already carries the scan ref. One
        row now says which page this is, in both of the numbering systems that
        name it, and `CLAUDE.md`'s rule that neither is derivable from the other
        is exactly why it wants both at once.
        """
        return ""

    def blocks(self, parent) -> str:
        out = []
        for kid in parent:
            if not isinstance(kid.tag, str):
                if kid.tag is etree.Comment:
                    out.append(self.comment(kid))
                continue
            # A block is where a citation's reach ends: the authority that owns
            # a plate is named in the same sentence as the plate, never in the
            # paragraph above it.
            self.seen = ""
            out.append(self.element(kid))
        return "\n".join(x for x in out if x)


def render(path: Path, titles: dict[str, dict] | None = None) -> dict:
    """One committed page → `{html, notes, refs, figures, folio, ok}`.

    A page that will not parse returns `ok: False` and says why, rather than
    raising: the reader is a view over a store that is still being written, and
    one bad file should cost that page and not the server.
    """
    try:
        root = etree.parse(str(path)).getroot()
    except (OSError, etree.XMLSyntaxError) as e:
        return {
            "ok": False,
            "why": str(e),
            "html": "",
            "notes": [],
            "refs": [],
            "forms": [],
            "figures": [],
            "figrefs": [],
            "folio": None,
        }
    body = root.find(f".//{{{TEI_NS}}}body")
    if body is None:
        return {
            "ok": False,
            "why": "no <body>",
            "html": "",
            "notes": [],
            "refs": [],
            "forms": [],
            "figures": [],
            "figrefs": [],
            "folio": None,
        }
    ref = path.stem.replace("chukchi-", "")
    r = Renderer(ref, titles=titles)
    r.opens = page_opens(body)
    r.page_first = first_flow(body)
    html = r.blocks(body)
    pb = body.find(f".//{{{TEI_NS}}}pb")
    return {
        "ok": True,
        "why": "",
        "html": html,
        "notes": r.notes,
        "refs": sorted(set(r.refs)),
        "forms": sorted(set(r.forms)),
        "figures": r.figures,
        "figrefs": r.figrefs,
        "folio": (pb.get("n") if pb is not None else None),
    }
