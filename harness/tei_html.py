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

from .context import norm_ref
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


def strip_tags(html: str) -> str:
    """The text of a rendered fragment, for building a key out of it.

    A Tier-1 span can carry `<unclear>` inside it, so the key has to come from
    the text and not from the markup around it.
    """
    return " ".join(_TAGS.sub("", html).split())


TEI_NS = "http://www.tei-c.org/ns/1.0"

#: Where the reading view is mounted. The four browser tools share one server,
#: so a bare `/entity/…` here would resolve against whichever of them owned the
#: root — the links in the page body would leave the edition. Kept beside
#: `edition_ui.BASE`, which has to agree with it.
BASE = "/edition"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

#: What each rank means to a reader, and how visible it should be. The three that
#: mean "a human settled this" are quiet; the two that do not are marked, because
#: the whole point of showing provenance is that unfinished work looks unfinished.
RANK_NOTE = {
    "#ed": ("ratified", "a human keyed or confirmed this against the page"),
    "#gt": ("adopted", "keyed at the raster in the ground-truth pass"),
    "#llm": ("proposed", "a model read this off the page; awaiting ratification"),
    "#htr": ("unexamined", "recognizer output nobody has looked at"),
    "#mz": ("rule-applied", "linked from the entity store's trigger table"),
}
UNSETTLED = ("#llm", "#htr", "#mz")


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

    def __init__(self, ref: str, tabindex_offset: int = 2):
        self.ref = ref
        self.tabindex = tabindex_offset
        self.notes: list[dict] = []
        self.refs: list[str] = []
        self.forms: list[str] = []
        self.figures: list[str] = []

    # -- inline ------------------------------------------------------------

    def inline(self, el) -> str:
        """An element's children, marked up. Recursive; text nodes are escaped."""
        out = []
        if el.text:
            out.append(escape(el.text))
        for kid in el:
            if not isinstance(kid.tag, str):
                if kid.tag is etree.Comment:
                    out.append(self.comment(kid))
                if kid.tail:
                    out.append(escape(kid.tail))
                continue
            out.append(self.element(kid))
            if kid.tail:
                out.append(escape(kid.tail))
        return "".join(out)

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

    def _tier1(self, el, body: str, cls: str, why: str, extra: str = "") -> str:
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
        return (
            f'<a class="tier1 lex{cls}"{_lang_attr(lang)} '
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
        return self._referring(el, "name", el.get("type") or "")

    def el_rs(self, el) -> str:
        return self._referring(el, "rs", "")

    def _referring(self, el, kind: str, typ: str) -> str:
        ref = el.get("ref") or ""
        cls, why = _rank_marks(el)
        body = self.inline(el)
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
        """A note becomes a marker here and a body at the foot.

        The print set them at the foot and the reader wants them both places: a
        superscript to keep the sentence readable, and the text where the eye
        goes. The stack gets it too, so a note read once stays put while you keep
        reading.
        """
        n = el.get("n") or str(len(self.notes) + 1)
        i = len(self.notes) + 1
        self.notes.append({"n": n, "i": i, "html": self.inline(el)})
        return (
            f'<a class="noteref" id="ref-{i}" href="#note-{i}" '
            f'data-note="{i}">{escape(n)}</a>'
        )

    def el_figure(self, el) -> str:
        n = el.get("n") or ""
        self.figures.append(n)
        return (
            f'<span class="figure-anchor" data-figure="{escape(n)}">'
            f"[fig. {escape(n)}]</span>"
        )

    # -- block elements ----------------------------------------------------

    def el_p(self, el) -> str:
        return f"<p>{self.inline(el)}</p>"

    def el_quote(self, el) -> str:
        return f"<blockquote>{self.blocks(el)}</blockquote>"

    def el_head(self, el) -> str:
        return f"<h3>{self.inline(el)}</h3>"

    def el_milestone(self, el) -> str:
        # A milestone is a boundary, not a container — TEI's answer to a heading
        # in a text with no divisions keyed. Rendered as one, since that is what
        # the page prints.
        label = el.get("n") or el.get("unit") or ""
        return f'<h2 class="milestone">{escape(label)}</h2>'

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
        return f'<li class="label">{self.inline(el)}</li>'

    def el_table(self, el) -> str:
        rows = "".join(
            self.element(r)
            for r in el
            if isinstance(r.tag, str) and etree.QName(r).localname == "row"
        )
        return f"<table>{rows}</table>"

    def el_row(self, el) -> str:
        cells = "".join(
            self.element(c)
            for c in el
            if isinstance(c.tag, str) and etree.QName(c).localname == "cell"
        )
        return f"<tr>{cells}</tr>"

    def el_cell(self, el) -> str:
        tag = "th" if el.get("role") == "label" else "td"
        return f"<{tag}>{self.inline(el)}</{tag}>"

    def el_pb(self, el) -> str:
        n = el.get("n")
        # The folio, in the margin, as the print has it. A page with none says so
        # rather than showing a blank: an unnumbered page is a real state here
        # (plates and front matter print no folio at all).
        return (
            f'<span class="folio" title="printed folio">'
            f'{escape(n) if n else "—"}</span>'
        )

    def blocks(self, parent) -> str:
        out = []
        for kid in parent:
            if not isinstance(kid.tag, str):
                if kid.tag is etree.Comment:
                    out.append(self.comment(kid))
                continue
            out.append(self.element(kid))
        return "\n".join(x for x in out if x)


def render(path: Path) -> dict:
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
            "folio": None,
        }
    ref = path.stem.replace("chukchi-", "")
    r = Renderer(ref)
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
        "folio": (pb.get("n") if pb is not None else None),
    }
