"""The gate. Mechanizes every checkable item of harness rev 2's self-check.

Exit contract: ERRORS block (the model must fix and re-run); WARNINGS accompany
(human review queue); WORKLIST is the Tier-1 lookalike census plus the page's
provenance state — by design not a failure (keying spec §4, two-scope dashboards).

The firewall here is a **provenance** check and not a text-agreement one. Every
Tier-1 span declares its rank in `@resp`, the collation pass may only ever claim
`#llm`, and `--ratified` switches the expectation for a page a human has been
through. What this file deliberately does *not* do is compare Tier-1 text against
`catmus_draft`; see the long comment at the old check's site for why that was
unsatisfiable against real recognizer output and a tautology against a model's own
reading.
"""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree

from .detectors import unlicensed_marks
from .state import load_toc

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
TIER1 = {"ckt", "kpy", "ypk"}
# Provenance ranks, strictly ordered, declared as respStmt/@xml:id in every page's
# teiHeader (the template in transcriber_harness.md). Rank answers *who read this*,
# which is a different question from whether the image decided — that one is
# <unclear>. A confident reading is still only proposed; certainty is not authority.
RESP_RANKS = {
    "#ed": "ratified — a human keyed or confirmed it against the page",
    "#llm": "proposed — a model read it off the page image",
    "#htr": "unexamined — recognizer output nobody has looked at",
}
PROPOSED = "#llm"
RATIFIED = "#ed"
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
            out.append(f"WORKLIST ({len(self.worklist)} items — Tier-1 lookalike "
                       "census and provenance state, not defects):")
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


def validate(tei_path: Path, ctx: dict | None = None,
             ratified: bool = False) -> Report:
    """Gate one page's TEI. `ratified` switches which provenance rank is expected.

    Default is the collation pass's own self-check, where a Tier-1 span may only
    claim `#llm` and anything higher is the promotion the firewall forbids. With
    `ratified` the page has been through a human, so `#ed` is what is expected and
    a remaining `#llm` becomes a worklist line rather than passing unremarked.

    Two modes rather than one permissive rule, because a single rule accepting both
    ranks would make the distinction unfalsifiable — which is the failure the old
    substring test had. Neither mode is silent about the other's state.
    """
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

    # THE check, re-anchored: provenance rank, not agreement with an upstream file.
    # Every Tier-1 element declares who read it, and this pass may only ever claim
    # the proposed rank. `#ed` is a human's to write; `#htr` belongs to the import.
    # Both the missing case and the over-claim are errors, and the missing case is
    # the more dangerous of the two — an unmarked span is indistinguishable from a
    # ratified one to every consumer that does not check, so silence here would
    # launder a model reading into an adopted glyph identity.
    for el in root.iter():
        if not isinstance(el.tag, str) or el.get(XML_LANG) not in TIER1:
            continue
        name = etree.QName(el).localname
        span = " ".join("".join(el.itertext()).split())[:40]
        resp = el.get("resp")
        if resp is None:
            r.errors.append(
                f"PROVENANCE: <{name} xml:lang='{el.get(XML_LANG)}'> {span!r} carries "
                f"no @resp — every Tier-1 span states who read it; use resp='{PROPOSED}'")
        elif resp not in RESP_RANKS:
            r.errors.append(
                f"PROVENANCE: <{name}> resp={resp!r} is not a declared rank "
                f"({', '.join(sorted(RESP_RANKS))})")
        elif not ratified and resp != PROPOSED:
            r.errors.append(
                f"PROVENANCE: <{name}> {span!r} claims resp={resp!r} "
                f"({RESP_RANKS[resp]}) — this pass may only emit {PROPOSED!r}; "
                "rank rises by a human act, never by a pass asserting it")
        elif ratified and resp != RATIFIED:
            r.worklist.append(
                f"unratified: <{name}> {span!r} still at resp={resp!r} "
                f"({RESP_RANKS[resp]}) — needs a reading against the page")

    # Deliberately no check that `@resp` resolves to a <respStmt> in this file. The
    # ranks are declared once in the corpus teiHeader; a page file is a fragment that
    # already defers title, publication and source the same way, so a pointer that
    # dangles when the page is read alone is the normal state and not a defect.
    # `RESP_RANKS` above is the closed set, and membership in it is the real check.

    # The verbatim-substring test against `catmus_draft` used to live here, and is
    # gone. It enforced the *canonicity of the upstream* — every Tier-1 span had to
    # appear character-for-character in whatever `ocr/` happened to hold — and that
    # is not what the firewall is about. The firewall is a rule about **hierarchies
    # of provenance**: a glyph identity may not be *originated* by a model reading a
    # scan, and a lower-authority witness may not be promoted to a higher one. It
    # says nothing about whether some particular upstream file agrees.
    #
    # Anchored to an upstream instead, it was one of three things depending on what
    # the draft happened to be, and never the intended one:
    #
    #   * draft is a human key      -> the test binds, but only incidentally; what
    #                                  binds is the human's authority, not the bytes.
    #   * draft is recognizer output -> unsatisfiable. CATMuS emits no inventory
    #                                  glyph at all (0% of the inventory, measured),
    #                                  so every Tier-1 span fails on a correct TEI.
    #   * draft is an LLM reading    -> tautology. The check compares a TEI against
    #                                  its own source and passes unconditionally,
    #                                  while still rendering as a verified PASS.
    #
    # The replacement belongs in the TEI, not here: each Tier-1 span carries its own
    # provenance, and a ratified build refuses to emit a span whose provenance is
    # machine-proposed. Until that exists this file makes no provenance claim, and
    # the count below is a worklist item rather than a verdict — which is the honest
    # state, where a PASS on an unsatisfiable or tautological test was not.

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
        # Not scoped to Tier-1, unlike the greps above. A licensing violation is an
        # impossible sequence rather than a notation question, so it is wrong in a
        # Latin binomial and in Russian prose for the same reason it is wrong in a
        # Chukchee form — and an ERROR, not a worklist line, since there is no reading
        # for a human to choose between.
        for h in unlicensed_marks(own_text):
            r.errors.append(
                f"MARK LICENCE: {h['mark']} on {h['base']} — licensed only on "
                f"{h['licensed_on']} (keying spec 2.6) in {h['context']!r}")
        if lang not in TIER1:
            bad = sorted({c for c in own_text if c in FORBIDDEN_PROSE})
            if bad:
                r.errors.append(
                    f"non-ASCII quote/apostrophe {['U+%04X' % ord(c) for c in bad]} "
                    f"in {lang!r} prose: {own_text.strip()[:60]!r}")
        v = el.get(XML_LANG)
        if v and v not in TIER1 and len(v) not in (2, 3):
            r.warnings.append(f"suspicious xml:lang '{v}'")

    # One summary line for the page's provenance state, so a PASS never reads as
    # "these forms are settled". In the default mode every span is by construction a
    # proposal, and saying so once is cheaper than a human inferring it from a rank
    # they'd have to go look up.
    if tier1_spans and not ratified:
        r.worklist.append(
            f"{tier1_spans} Tier-1 span(s) at {PROPOSED} — proposals, not adopted "
            "glyph identities; each needs a human reading against the page before "
            "anything downstream may treat it as settled")

    r.metrics = {
        "tier1_spans": tier1_spans,
        "unclear": len(root.findall(f".//{q('unclear')}")),
        "comments": sum(1 for _ in root.iter(etree.Comment)),
        "notes": sum(1 for _ in root.iter(q("note"))),
        "worklist": len(r.worklist),
    }
    return r
