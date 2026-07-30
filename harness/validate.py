"""The gate. Mechanizes every checkable item of harness rev 2's self-check.

Exit contract: ERRORS block (the model must fix and re-run); WARNINGS accompany
(human review queue); WORKLIST is the Tier-1 lookalike census — by design not a
failure (keying spec §4, two-scope dashboards).
"""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree

from .state import load_toc

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
TIER1 = {"ckt", "kpy", "ypk"}
# The four curly quotes are deliberately absent. Under the Tier-1-scoped ASCII policy
# (keying spec section 1) English prose reproduces the print, curly quotes included, so
# forbidding them here would reject correct text. What remains is the set with no
# legitimate use in English at all, each an error wherever it appears.
FORBIDDEN_PROSE = set("\u00B4\u02BC\u02BB\u2010")
LOOKALIKE_GREPS = {  # keying spec §3 — reported over Tier-1 spans as worklist
    "\u00B4": "U+00B4 traps U+02CA", "\u2019": "U+2019 traps U+0027",
    "\u02BC": "U+02BC traps U+0027", "\u02BB": "U+02BB traps U+0027",
    "\u2018": "U+2018 traps U+0027 (turned-comma spirant shape, F10)",
    "\u00B7": "U+00B7 traps U+02D9",
    "\u02E2": "U+02E2 traps U+1D4B/U+1D49", "\u2091": "U+2091 traps U+1D49",
    "\u04E9": "U+04E9 traps U+0275", "\u2010": "U+2010 traps U+002D",
}
# Traps that are a *sequence* rather than a codepoint, and so cannot live in the dict
# above, which is consulted one character at a time. U+0121 used to sit there and was
# unreachable: `own_text` is NFD-normalized before the check, which decomposes U+0121
# to exactly this pair, so the single-codepoint key could never match. The canonical
# glyph is g+U+0323, dot *below*; dot above is the lookalike.
LOOKALIKE_SEQ_GREPS = {"g\u0307": "g+U+0307 (or U+0121) traps g+U+0323"}
NOTE_CONT_COMMENT = "footnote continuation, no marker on this page"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    worklist: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        out = [f"RESULT: {'PASS' if self.ok else 'FAIL'}"]
        for label, items in (("ERROR", self.errors), ("WARN", self.warnings)):
            out += [f"{label}: {i}" for i in items]
        if self.worklist:
            out.append(f"WORKLIST ({len(self.worklist)} Tier-1 lookalike hits — "
                       "to-key census, not defects):")
            out += [f"  {i}" for i in self.worklist]
        # key=value, not a Python repr: the gate's output is read by a human at
        # a terminal and grepped by whatever comes after it, and a
        # single-quoted dict serves neither.
        out.append("METRICS: " + " ".join(f"{k}={v}" for k, v in self.metrics.items()))
        return "\n".join(out)


def _lang_of(el, default="en") -> str:
    while el is not None:
        v = el.get(XML_LANG)
        if v:
            return v
        el = el.getparent()
    return default


def validate(tei_path: Path, ctx: dict | None = None) -> Report:
    r = Report()
    try:
        tree = etree.parse(str(tei_path))
    except (etree.XMLSyntaxError, OSError) as e:
        r.errors.append(f"not well-formed / unreadable: {e}")
        return r
    root = tree.getroot()
    q = lambda t: f"{{{TEI_NS}}}{t}"
    body = root.find(f".//{q('body')}")
    if body is None:
        r.errors.append("no <body>")
        return r

    # pb: first element. @n is the folio the model read off the image; absent
    # @n asserts the page carries no printed folio (plate, blank, part title).
    # That assertion is load-bearing downstream — it tells the seam ledger not
    # to advance the printed count — so it is surfaced, not accepted silently.
    kids = [c for c in body if isinstance(c.tag, str)]
    if not kids or kids[0].tag != q("pb"):
        r.errors.append("<pb> is not the first element in <body>")
    else:
        n = kids[0].get("n")
        if n is None:
            r.warnings.append("<pb/> without @n — asserts this page carries no "
                              "printed folio; confirm against the image")
        elif not n.isdigit():
            r.errors.append(f"<pb n='{n}'> is not an integer folio")
        elif ctx and ctx.get("expected_folio") is not None \
                and int(n) != ctx["expected_folio"]:
            basis = ctx.get("folio_basis", {})
            r.warnings.append(
                f"printed folio {n} != expected {ctx['expected_folio']} "
                f"(predicted from {basis.get('basis_ref')} = "
                f"{basis.get('basis_folio')}) — mismatch comment required "
                "(harness: folio wins, the prediction is only a prediction)")

    # forbidden structure
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        for att in ("part", "prev", "next"):
            if el.get(att) is not None:
                r.errors.append(f"@{att} on <{etree.QName(el).localname}> — "
                                "continuation is the patch pass's job")
        if el.get("{http://www.w3.org/XML/1998/namespace}id"):
            r.errors.append(f"xml:id on <{etree.QName(el).localname}> — "
                            "this pass mints no ids")
    if root.find(f".//{q('lb')}") is not None:
        r.errors.append("<lb/> present — ALTO holds the line record")
    if root.find(f".//{q('div')}") is not None:
        r.errors.append("<div> present — page files are div-less")

    # milestones. An id must exist in the ToC — that is the hard check. Falling
    # outside the supplied window is only a warning: the window is keyed to a
    # predicted folio, so a milestone outside it may mean the prediction is
    # wrong rather than the milestone. Marks inform; they do not decide.
    window_ids, all_toc_ids = set(), set()
    if ctx:
        window_ids = {e["id"] for e in ctx.get("toc_window", [])}
        all_toc_ids = {e["id"] for e in load_toc(Path(ctx.get("root", "."))) if e.get("id")}
    for ms in root.iter(q("milestone")):
        extra = set(ms.keys()) - {"unit", "n"}
        if extra:
            r.errors.append(f"<milestone> carries extra attributes {extra}")
        if ms.get("unit") not in {"chapter", "section", "subsection", "subsubsection"}:
            r.errors.append(f"<milestone unit='{ms.get('unit')}'> not in the level map")
        if all_toc_ids and ms.get("n") not in all_toc_ids:
            r.errors.append(f"<milestone n='{ms.get('n')}'> matches no ToC id")
        # Only meaningful when the window is keyed to a folio at all; with no
        # prediction the window is just the believed-open set, and "outside it"
        # carries no information worth interrupting for.
        elif window_ids and ctx.get("expected_folio") is not None \
                and ms.get("n") not in window_ids:
            r.warnings.append(
                f"<milestone n='{ms.get('n')}'> is a real ToC id but falls outside "
                "the supplied window — either the folio prediction is off or this "
                "milestone belongs elsewhere; resolve before commit")

    # notes
    comments_text = " ".join(c.text or "" for c in root.iter(etree.Comment))
    for note in root.iter(q("note")):
        if note.get("place") != "bottom":
            r.errors.append("a <note> lacks place='bottom'")
        if note.get("n") is None and NOTE_CONT_COMMENT not in comments_text:
            r.errors.append("<note> without n= but no continuation comment present")
        if note.get("n") is not None and not note.get("n").isdigit():
            r.warnings.append(f"<note n='{note.get('n')}'>: non-integer marker "
                              "(book uses integers) — confirm against image")

    # figures
    if ctx is not None:
        zones = {f["zone_id"] for f in ctx.get("figures_on_page", [])}
        for fig in root.iter(q("figure")):
            facs = (fig.get("facs") or "").lstrip("#")
            if facs not in zones:
                r.errors.append(f"<figure facs='#{facs}'> matches no supplied zone")

    # THE check: Tier-1 content is a function of the draft, not a composition.
    # Every element bearing a Tier-1 xml:lang must reproduce draft text verbatim
    # (whitespace-joined, NFD both sides). Everything else in this file is
    # structure; this is the firewall.
    draft_norm = ""
    if ctx is not None:
        draft_norm = " ".join(unicodedata.normalize("NFD",
                              ctx.get("catmus_draft", "")).split())
    for el in root.iter():
        if not isinstance(el.tag, str) or el.get(XML_LANG) not in TIER1:
            continue
        span = " ".join("".join(el.itertext()).split())
        span = unicodedata.normalize("NFD", span)
        if span and ctx is not None and span not in draft_norm:
            r.errors.append(
                f"FIREWALL: <{etree.QName(el).localname} xml:lang="
                f"'{el.get(XML_LANG)}'> content {span[:50]!r} is not a verbatim "
                "substring of the draft — Tier-1 spans are reproduced, never composed")

    # language codes + two-scope codepoint hygiene
    tier1_spans = 0
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        lang = _lang_of(el)
        own_text = (el.text or "") + "".join(ch.tail or "" for ch in el)
        own_text = unicodedata.normalize("NFD", own_text)
        if lang in TIER1:
            tier1_spans += 1 if el.get(XML_LANG) in TIER1 else 0
            for ch_ in own_text:
                if ch_ in LOOKALIKE_GREPS:
                    r.worklist.append(
                        f"[{lang}] <{etree.QName(el).localname}> "
                        f"{LOOKALIKE_GREPS[ch_]} in {own_text.strip()[:40]!r}")
            for seq, msg in LOOKALIKE_SEQ_GREPS.items():
                if seq in own_text:
                    r.worklist.append(
                        f"[{lang}] <{etree.QName(el).localname}> "
                        f"{msg} in {own_text.strip()[:40]!r}")
        else:
            bad = sorted({c for c in own_text if c in FORBIDDEN_PROSE})
            if bad:
                r.errors.append(
                    f"non-ASCII quote/apostrophe {['U+%04X' % ord(c) for c in bad]} "
                    f"in {lang!r} prose: {own_text.strip()[:60]!r}")
        v = el.get(XML_LANG)
        if v and v not in TIER1 and len(v) not in (2, 3):
            r.warnings.append(f"suspicious xml:lang '{v}'")

    r.metrics = {
        "tier1_spans": tier1_spans,
        "unclear": len(root.findall(f".//{q('unclear')}")),
        "comments": sum(1 for _ in root.iter(etree.Comment)),
        "notes": sum(1 for _ in root.iter(q("note"))),
        "worklist": len(r.worklist),
    }
    return r
