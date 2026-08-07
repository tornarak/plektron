"""The gate. Mechanizes every checkable item of the collation pass's self-check
(`.claude/skills/transcribe-page/SKILL.md`).

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

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .detectors import unlicensed_marks
from .state import load_toc

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
# The closed set the firewall covers: languages the book renders in the same
# ambiguous Americanist notation, so a glyph inside one carries the inventory and
# the ASCII policy. `.claude/skills/transcribe-page/SKILL.md` says when each fires.
# Where the source does not distinguish members of a family, neither does this —
# `ypk` and `ipk` are family and macrolanguage codes on purpose.
TIER1 = {"ckt", "kpy", "ypk", "xcv", "eve", "ipk", "itl"}
# Provenance ranks, strictly ordered, declared as respStmt/@xml:id once in the corpus
# teiHeader and never in a page file — a page is a fragment and defers. `harness tei header`
# (check_corpus_header below) is what holds this dict and that file together; without
# it the two could drift and every page would go on passing. Rank answers *who read this*,
# which is a different question from whether the image decided — that one is
# <unclear>. A confident reading is still only proposed; certainty is not authority.
RESP_RANKS = {
    "#ed": "ratified — a human keyed or confirmed it against the page",
    "#gt": "adopted — transcluded whole from adjudicated ground truth",
    "#llm": "proposed — a model read it off the page image",
    "#htr": "unexamined — recognizer output nobody has looked at",
}
PROPOSED = "#llm"
RATIFIED = "#ed"
# The fourth rank, and the one that needed an argument rather than a slot.
#
# A span `harness tei expand` filled did not have its glyphs read by the collation
# pass at all: they were copied whole out of `gt/ocr/`, where a human adjudicated
# every mark at the raster. So `#llm` is *false* about it — no model chose those
# characters — and `#ed` is false too, since no human read this TEI. The human act
# the firewall requires did happen; it happened one artifact upstream, and the
# honest record of that is its own rank rather than a promotion.
#
# **It is not taken on trust.** Every `#gt` span is checked against
# `context.tier1_terms` for the page — membership in the ratified token set, so
# the match is whole-token by construction and a dropped final mark cannot pass
# the way it would past a substring test (`Qeˊñ` is a substring of `Qeˊñu`). That
# also makes the claim *maintained* rather than stamped: correct the ground truth
# later and a span that used to match stops matching and says so, where an
# attribute written once would go stale in silence.
ADOPTED = "#gt"
# Why a <supplied> stands where it does. Closed, and extended only here — a required
# attribute with a free value guarantees a string rather than a distinction.
#   context   the frame the surrounding prose supplies and the entries do not repeat
#             (a gloss list's shared "of a reindeer", written once as its <head>)
#   ellipsis  a word the sentence itself omits and the reader restores from it
SUPPLIED_REASONS = {"context", "ellipsis"}
# What kind of gloss the *book* prints. Unmarked is the ordinary sense gloss; the
# other two are cued in the print itself, so this is evidence and not judgement.
#
#   literal  the rendering Bogoras introduces with the word "literally". A term
#            routinely carries this *and* a sense gloss — 1-039 sets `Pnauˊkulɪt
#            (“file-mongers,” from pnauˊkun, “file” [literally, “whetting-stone”])`.
#   etymon   the form a word derives from, cued with "from", together with whatever
#            translation the print runs into it. One element for both, because the
#            printed instances are too varied to split the form from its gloss
#            without imposing a structure the page does not have.
#
# Provenance is deliberately *not* here. A gloss nobody printed is `<supplied>`
# inside the gloss — the TEI idiom, and the same mechanism a list's supplied scope
# uses — so `@type` carries one axis and `<supplied>` the other.
GLOSS_TYPES = {"literal", "etymon"}
# What a <name> may be, where the page says. Closed, extended only here and only on
# attestation — "type only what's evidenced" means most names carry none of these,
# and an untyped <name> is the designed outcome rather than an unfinished one.
#
# **Scoped to Tier-1 names, plus persons at every tier**, and the asymmetry is the
# point rather than a limitation. A Chukchee form glossed "a village" or "personal
# name" is a fact only a reader of the page can record, and it is unrecoverable later
# without re-reading; an English ethnonym or a Latin binomial is a string match
# anything can find over finished TEI, so asking a per-page pass to mark every
# "Chukchee" and "Phoca" buys automatable coverage at the price of thousands of hand
# judgements and the errors in them. Hence no `taxon`: the binomials are Latin in
# English prose and out of scope, and a type nothing can carry is dead surface here.
#
# Persons are where that argument fails, so `anthroponym` is not scoped by tier.
# `Steller` bare in a footnote is a man, a work, or a jay, and the string carries
# none of the three; the commonest personal names in the book are its sources, which
# it cites by surname alone. Automatable coverage does not exist for that case, so
# there is nothing to buy it back from.
#
# `event` is unscoped for the same reason and is the second exception, not a
# loosening of the rule. Its attested cases are English — "the Jesup North Pacific
# Expedition", "the Cossack wars" — so a Tier-1 scope would exclude every one of
# them. It is not string-matchable either: the span's extent is the judgement. A
# reader has to decide that "Jesup North Pacific Expedition" is one name and that
# the bare "Jesup" a page later is the same event rather than the man it was named
# after, and no match over finished TEI recovers that. It also removes a live
# mistyping: `1-021` marked `Sibiryakoff` and `Jesup` inside expedition titles as
# `anthroponym`, correctly under the old table and wrongly about the page, because
# a person was the only thing there was to call them.
#
# One element with @type rather than TEI's <persName>/<placeName>/<geogName>,
# because the untyped state has to be expressible in the *same* element: typing a
# name later is then adding an attribute, not changing an element and moving the
# span in every diff. The specific elements also cannot say "this is a name and I do
# not know which kind", which is the state that has to stay findable.
#   zoonym    an individual animal's name. A herding people names its reindeer, so
#             this is common rather than exotic — 1-101 is a whole paragraph about
#             the practice.
#   mythonym  a mythological or supernatural being. Broader than `theonym`, which
#             is the narrower class of gods, because the book names beings that are
#             not gods at all.
#   event     a named historical event or undertaking — an expedition, a war, a
#             treaty. Named, not merely described: "the Cossack wars" is one and
#             "the wars with the Cossacks" is prose about the same thing.
#
# Two rules this table cannot enforce and the pass has to hold to:
#
# **A generic noun is not a name.** `keˊlᴇ` (plural `keˊlet`) and `reˊkkeñ` are
# *kinds* of evil spirit, so they are common nouns and belong in `<term>`. Being
# Tier-1, capitalized and otherworldly makes a form none of a proper noun. Get this
# one right first: a wrong `@type` is a mislabel, but a `<name>` around a common
# noun invents a whole entity that is not there.
#
# **A type comes from the page, never from the form.** Forms that look alike differ
# entirely in class — among `loi.json`'s otherworldly-looking group, one is a god,
# one a village, one a person, the rest common nouns — and nothing in the shape of a
# word says which. `tier1_spans` flags keying risk and carries no class information,
# so it cannot be mined for this; inferring class from shape is the firewall's
# failure mode one category over from glyphs.
NAME_TYPES = {"anthroponym", "ethnonym", "toponym", "hydronym",
              "zoonym", "mythonym", "event"}
# Identity is the annotation pass's, over finished TEI. These attributes are how TEI
# spells it, so refusing them is the deferral made mechanical rather than left as a
# line in a skill's never-do list — a checkable rule does not depend on the pass
# behaving.
NAME_IDENTITY_ATTRS = ("ref", "key", "nymRef")
# The same deferral on <bibl>, which marks a citation's extent and nothing more. The
# attributes differ because TEI spells bibliographic identity differently — @corresp
# and @sameAs point a citation at the work it names — but the rule is one rule: this
# pass records that a work is being cited, never *which* work. `find authority` is
# read while collating and its answer is not written down; `data/authorities.json`
# keys belong to the annotation pass, which resolves them with the whole corpus in
# view rather than one page at a time. The printed list is open ("For other
# authorities see references in the text"), so a body citation outside it is expected
# and a per-page pass resolving what it can would leave a store part-keyed by
# accident of which pages ran first.
BIBL_IDENTITY_ATTRS = ("corresp", "ref", "key", "sameAs")
# What a <measure> may be. Required, unlike a <name>'s type, and the asymmetry is
# deliberate: an untyped name is a real state — the page marked a proper noun and did
# not say what kind — whereas the only reason to mark a measure at all is which regime
# of value it belongs to. A span that counts things merely being counted is not this
# element's business — 1-090's 2,837 reindeer in Alaskan herds, 1-088's four hundred
# fire-arms in a population of four hundred and forty — and a rule that caught those
# would fire on most numbers in the book.
#
# The test is what the counted thing is *doing*, not whether a price is named. The
# 1837 Anui tally ("580 red foxes, 80 gray foxes, 13 black foxes, 268 white foxes")
# is `barter`, not an inventory: that fair reckoned in peltries — 1-079, "the value of
# other peltries was expressed in red-fox units" — and 1-078 calls the tally a value
# outright, "these figures must be at least doubled to reach the real trade value".
# It is "its traffic amounted to two hundred thousand rubles yearly" in the unit the
# fair used.
#
# The three come from the chapter itself rather than from a standard vocabulary, and
# `currency` is not the superset because 1-093 refuses to let it be:
#
#   "The Chukchee trade is carried on exclusively in barter. Money is quite unknown.
#    The Reindeer people have not even a word for it ... The unit of value in Russian
#    trade remains a bundle of tobacco 'not tampered with' ... In recent years
#    brick-tea has also come into use as a standard of value."
#
#   currency  money proper — rubles, kopeks, dollars, cents. Foreign to the trade
#             being described, which is the point: it is the traders' unit.
#   barter    a commodity doing money's job — a bundle of tobacco, a piece of
#             brick-tea, a slab of whalebone, a pair of boots, 1-079's whole red-fox
#             system ("The value of other peltries was expressed in red-fox units").
#   weight    the pud, the Russian pound, the sack. As recondite as the barter units
#             and glossed in the same breath — "one pud (thirty-six pounds
#             Avoirdupois)", "One Russian pound (nine-tenths of a pound Avoirdupois)"
#             — and the denominator of half the prices in the chapter.
MEASURE_TYPES = {"currency", "barter", "weight"}
# The normalizing attributes, refused for the reason @ref is refused on <name>: they
# mint a controlled vocabulary, and a per-page pass minting one produces as many
# vocabularies as there are pages. `unit="pud"` also asserts a regularization the page
# did not make, and `quantity` cannot hold what the chapter actually prints — "$2.50
# to $3.50", "10 to 15 fawn-skins", "6¼ pounds", "20-30 slabs". A range is where a
# per-page pass would start inventing conventions, so the field it would invent them
# in is not available.
MEASURE_IDENTITY_ATTRS = ("unit", "quantity", "commodity")
# How the page opens, as the collator saw it on the raster. Closed, and required.
#
# **This is a witness, not a verdict.** `@part` is the verdict and `harness tei seam`
# is the only thing that writes one, from the page that holds both ends of the gap —
# so the two are not one fact in two places. What they are is a fact and the evidence
# for it, and the evidence had nowhere to live: of the three witnesses the collation
# rules name, two survive into the TEI (the previous page's tail, this page's opening
# text) and the third does not. **The first line's indent is the positive witness —
# a paragraph opening indented is a new one, running flush to the measure continues
# one — and it exists only on the image.** A coordinator reading finished TEI cannot
# recover it, and re-deriving it means reopening rasters the collator already had
# open.
#
# That mattered little while the pass ran serially and wrote its own seam. It is
# load-bearing once collation is dispatched: the collator sees the page, the
# coordinator writes the seam, and this comment is the whole of what crosses.
#
# One comment on every page, which is a cost worth naming. It earns it because ~70%
# of text pages open mid-paragraph, so the question is live nearly everywhere —
# unlike `@facs`, which is reserved for spans that earned it precisely because a
# marker on everything stops meaning anything.
OPENS_PREFIX = "opens:"
OPENS = {
    # A new paragraph begins here; the gap behind is a clean break.
    "indented",
    # An element carries across the gap — the ordinary case, at ~70%.
    "flush to the measure",
    # A heading, a plate, a page whose first line is not prose: there is no measure
    # to judge against. A real answer, not a refusal to look, which is why it is in
    # the set rather than expressed by the comment's absence.
    "no witness",
}
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


CORPUS_HEADER = Path("tei") / "corpus-header.xml"


def check_corpus_header(root: Path, schema: bool = False) -> Report:
    """Gate the corpus teiHeader — the one place the provenance ranks are declared.

    `RESP_RANKS` above is the closed set every page is validated against, and the
    header is what a `@resp` pointer actually resolves to once a page fragment is
    assembled. Two files, one fact, and nothing until now held them together: the
    ranks could be renamed in either place and every page would go on passing,
    because per-page validation deliberately does not check that `@resp` resolves
    locally (a page file is a fragment and defers by design).

    So this checks the *correspondence*, not the header's prose: exactly the ranks
    Python knows about, declared as `respStmt/@xml:id`, no more and no fewer. A
    rank declared here and absent from `RESP_RANKS` is the worse direction — it is
    a rank the corpus advertises and the gate would reject on sight.
    """
    r = Report()
    path = root / CORPUS_HEADER
    if not path.exists():
        r.errors.append(
            f"no corpus teiHeader at {CORPUS_HEADER} — every @resp in the corpus "
            "is a pointer with nothing to resolve against, and no assembly step "
            "can run")
        return r
    try:
        doc = etree.parse(str(path))
    except etree.XMLSyntaxError as e:
        # lxml enforces xml:id uniqueness during parsing, so a duplicated rank
        # never reaches the checks below — it arrives here instead. Worth naming
        # separately: a repeated xml:id is not a malformed document, it is two
        # ranks answering to one @resp, which is the specific failure this gate
        # exists to catch.
        if "already defined" in str(e):
            r.errors.append(
                f"{CORPUS_HEADER} declares the same xml:id twice — @resp would be "
                f"ambiguous, and the ranks are what it points at: {e}")
        else:
            r.errors.append(f"{CORPUS_HEADER} is not well-formed XML: {e}")
        return r

    q = lambda t: f"{{{TEI_NS}}}{t}"
    root_el = doc.getroot()
    if etree.QName(root_el).localname != "teiHeader":
        r.errors.append(
            f"{CORPUS_HEADER} root is <{etree.QName(root_el).localname}>, not "
            "<teiHeader> — it is a fragment spliced in by assembly, like a page file")

    XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
    declared = [s.get(XML_ID) for s in root_el.iter(q("respStmt"))]
    if any(d is None for d in declared):
        r.errors.append(
            "a <respStmt> carries no xml:id — a rank nothing can point at")
        declared = [d for d in declared if d is not None]
    # No duplicate check here: lxml refuses a repeated xml:id at parse time, so it
    # is handled above and a check at this point would be dead code reading as live.

    want = {k.lstrip("#") for k in RESP_RANKS}
    have = set(declared)
    for missing in sorted(want - have):
        r.errors.append(
            f"rank '#{missing}' is in RESP_RANKS but no <respStmt xml:id=\"{missing}\"> "
            f"declares it — pages may emit it and it would resolve to nothing")
    for extra in sorted(have - want):
        r.errors.append(
            f"<respStmt xml:id=\"{extra}\"> declares a rank RESP_RANKS does not "
            f"know — validate would reject resp='#{extra}' on every page that used it")

    for name in ("titleStmt", "publicationStmt", "sourceDesc"):
        if root_el.find(f".//{q(name)}") is None:
            r.errors.append(
                f"no <{name}> — page fragments defer to it by name "
                "(\"see corpus teiHeader\") and would resolve to nothing")

    # Neither branch is an error. The licence is an editorial decision, and a header
    # that says it is undecided is doing its job; what would be wrong is a plausible
    # licence nobody chose. But a *settled* status with no <licence> under it is the
    # worse of the two states and the only one that reads as finished — it asserts
    # the terms exist while naming none, which is the same shape as an empty zone
    # page: indistinguishable from done, to anything that does not look inside.
    avail = root_el.find(f".//{q('availability')}")
    if avail is not None:
        status = avail.get("status")
        if status in (None, "unknown"):
            r.worklist.append(
                "publicationStmt/availability is unsettled — the source is public "
                "domain but this edition's licence has not been chosen")
        elif avail.find(q("licence")) is None:
            r.errors.append(
                f"availability claims status={status!r} but grants no <licence> — "
                "a settled status with no terms under it reads as decided and says "
                "nothing")

    if schema:
        from .schema import check_header
        # The header is a bare <teiHeader> and has no conformant container of its
        # own, so `check_header` wraps it in memory. Nothing is written: inventing
        # a container on disk would settle the assembly scheme by accident.
        r.errors += check_header(root_el, root)

    r.metrics = {"ranks": len(have), "path": str(CORPUS_HEADER)}
    return r


def _check_ids(r: Report, root, ctx: dict | None) -> None:
    """The id scheme, checked rather than prohibited.

    The blanket ban that stood here ("this pass mints no ids") was a real concern
    about *arbitrary* ids generalised into a prohibition on all of them, and it
    blocked three unrelated things at once. What replaces it is a shape check: an
    id is a pure function of the element's kind, the page's ref and the element's
    position among same-kind elements, so the gate can recompute what every id
    *must* be and compare. A checkable rule beats a prohibition, because it does
    not depend on the pass behaving.
    """
    from . import ids as idmod
    from .seam import next_ref, prev_ref, tei_path

    ref = (ctx or {}).get("page_ref")
    croot = Path((ctx or {}).get("root", "."))
    present = idmod.ids_in(root)
    canonical = idmod.canonical_map(root, ref) if ref else {}
    want = dict(canonical)
    referenced = idmod.referenced_ids(root)

    for ident, el in present.items():
        name = etree.QName(el).localname
        parsed = idmod.parse_id(ident)
        if parsed is None:
            r.errors.append(
                f'xml:id="{ident}" on <{name}> is not of the scheme '
                f"{{kind}}-{{PP-NNN}}-{{ordinal}}, kinds {list(idmod.KINDS)}")
            continue
        if ref and parsed["ref"] != ref:
            # The one that matters most now that `prev_tail` hands over the
            # previous page's markup with its ids in it: a copy-paste would
            # otherwise import a foreign id silently.
            r.errors.append(
                f'xml:id="{ident}" embeds ref {parsed["ref"]}, but this is {ref} '
                "— an id names the page it lives on")
        elif ref and want.get(el) != ident:
            r.errors.append(
                f'xml:id="{ident}" on <{name}> should be "{want.get(el)}" — the '
                "ordinal is the element's position among same-kind elements in "
                "document order, not a counter of the ids minted")
        if ident not in referenced and not _referenced_by_neighbour(
                ident, ref, croot, tei_path, prev_ref, next_ref, idmod):
            r.errors.append(
                f'xml:id="{ident}" on <{name}> has no referrer — nothing in this '
                "page or either neighbour points at it. Ids are minted where "
                "something needs to name them, never in advance")

    for p in idmod.pointers_in(root, idmod.IN_FILE_POINTERS):
        if p["id"] not in present:
            r.errors.append(
                f'@{p["attr"]}="#{p["id"]}" on '
                f'<{etree.QName(p["el"]).localname}> resolves to nothing in this page')

    # A supplied gloss is not on the page. It is drawn from this page's prose or
    # from book-internal apparatus, so it is authored English rather than
    # transcribed English, and the two must not be indistinguishable in the file.
    #
    # Both states are marked by a *present* attribute, so neither can be reached by
    # omission: `type="supplied"` requires `@resp`, and a gloss without `@type` is
    # transcription and must not carry one. Note `@resp` means something different
    # here than on a Tier-1 span — "a model authored this English sentence", not "a
    # model read this glyph off the scan". The firewall's subject is glyph identity
    # and does not reach English; what carries over is the rank's actual question,
    # how far this has been checked.
    # `@type` on <gloss> says what *kind* of gloss the book prints, and provenance
    # is no longer on it: a gloss nobody printed is `<supplied>` inside the gloss,
    # which is the TEI idiom and the same mechanism a list's supplied scope uses. So
    # one attribute carries one axis, and the <supplied> rule below already forces
    # @resp and @reason, which is what the old `type="supplied"` pairing existed to
    # guarantee.
    for gl in root.iter(f"{{{TEI_NS}}}gloss"):
        kind, resp = gl.get("type"), gl.get("resp")
        if kind is not None and kind not in GLOSS_TYPES:
            r.errors.append(
                f"<gloss type={kind!r}> is not a declared kind "
                f"({', '.join(sorted(GLOSS_TYPES))}); an unmarked <gloss> is the "
                "ordinary sense gloss")
        if resp is not None:
            r.errors.append(
                f"<gloss resp={resp!r}> — a gloss reproducing the print is "
                "transcription and carries no rank; wrap authored text in "
                "<supplied> instead, which states who wrote it and why")

    # `<supplied>` is editorial text standing in the reading text, so the same
    # question applies to it as to a supplied gloss and to a Tier-1 span: unmarked,
    # it is indistinguishable from transcription.
    #
    # Two differences from the Tier-1 rule, both deliberate. The `#llm`-only
    # restriction does NOT extend here — that exists because this pass may not
    # promote a *glyph identity*, and supplied English contains none, so a human
    # writing one and marking it `#ed` is legitimate. And `@reason` is required from
    # a closed set: a required attribute with a free value guarantees a string
    # rather than a distinction, and drifts on the first typo.
    for sup in root.iter(f"{{{TEI_NS}}}supplied"):
        span = " ".join("".join(sup.itertext()).split())[:40]
        resp, why = sup.get("resp"), sup.get("reason")
        if resp is None:
            r.errors.append(
                f"<supplied> {span!r} without @resp — text standing in the reading "
                "text that is not on the page was authored by someone")
        elif resp not in RESP_RANKS:
            r.errors.append(
                f"<supplied> resp={resp!r} is not a declared rank "
                f"({', '.join(sorted(RESP_RANKS))})")
        if why is None:
            r.errors.append(
                f"<supplied> {span!r} without @reason — why it was supplied is the "
                f"record; declared values are {', '.join(sorted(SUPPLIED_REASONS))}")
        elif why not in SUPPLIED_REASONS:
            r.errors.append(
                f"<supplied reason={why!r}> is not a declared reason "
                f"({', '.join(sorted(SUPPLIED_REASONS))})")

    if not ref:
        return
    for p in idmod.pointers_in(root, idmod.CROSS_FILE_POINTERS):
        parsed = idmod.parse_id(p["id"])
        expect = prev_ref(ref) if p["attr"] == "prev" else next_ref(ref)
        if parsed is None:
            r.errors.append(f'@{p["attr"]}="#{p["id"]}" is not a scheme id')
            continue
        # `prev_ref` is None on the first scan of a part, which has no predecessor
        # at all. Without this the next branch compares a ref against None, takes
        # the mismatch path, and reports "must name None" — a true statement about
        # the variable and nonsense about the book. Found by `ty`.
        if expect is None:
            r.errors.append(
                f'@{p["attr"]}="#{p["id"]}" cannot resolve — {ref} is the first '
                "scan of its part and has no predecessor")
            continue
        if parsed["ref"] != expect:
            r.errors.append(
                f'@{p["attr"]}="#{p["id"]}" names page {parsed["ref"]}, but '
                f'@{p["attr"]} from {ref} must name {expect}')
            continue
        npath = tei_path(expect, croot)
        if not Path(npath).exists():
            # Honest null, same shape as `prev_tail`: the neighbour is not
            # collated, so the pointer is unresolvable rather than wrong.
            r.warnings.append(
                f'@{p["attr"]}="#{p["id"]}" cannot be resolved — {expect} is not '
                "collated yet")
            continue
        target = idmod.ids_in(etree.parse(str(npath)).getroot())
        if p["id"] not in target:
            r.errors.append(
                f'@{p["attr"]}="#{p["id"]}" matches no xml:id in {expect}')


def _referenced_by_neighbour(ident, ref, croot, tei_path, prev_ref, next_ref,
                             idmod) -> bool:
    """Is this id named by `@prev`/`@next` on either adjacent page?

    Read both, never just one. A list spanning three pages leaves the middle
    element referenced from both sides, and checking a single neighbour would
    report a live id as unreferenced.
    """
    if not ref:
        return False
    for cand in (prev_ref(ref), next_ref(ref)):
        if not cand:
            continue
        p = Path(tei_path(cand, croot))
        if not p.exists():
            continue
        if ident in idmod.referenced_ids(etree.parse(str(p)).getroot(),
                                         idmod.CROSS_FILE_POINTERS):
            return True
    return False


def _lang_of(el, default="en") -> str:
    while el is not None:
        v = el.get(XML_LANG)
        if v:
            return v
        el = el.getparent()
    return default


def _opening_witness(body, q, r) -> None:
    """The `opens:` comment: present, leading, and one of the three.

    **Checked as the first comment after `<pb>`, not as the first node.** The
    collation rules also put a folio-disagreement comment immediately after `<pb>`,
    and two comments cannot both be immediate — an unordered pair would fail
    validation according to which one the author happened to write first, and a gate
    that fires on authoring order teaches its reader to work around it. So the order
    is fixed, `opens:` leads, and the comments after it are not this check's business.
    """
    # **After `<pb>`, and the walk starts there rather than at the first node.** A
    # comment is not an element, so the "pb is the first element" check above steps
    # straight over one sitting before it — leaving two positions that both validate,
    # which is how a fixed form becomes two fixed forms nobody chose between.
    nodes = list(body)
    after = []
    for i, node in enumerate(nodes):
        if isinstance(node.tag, str) and node.tag == q("pb"):
            after = nodes[i + 1:]
            break
    lead = None
    for node in after:
        if node.tag is etree.Comment:
            lead = (node.text or "").strip()
        break
    if lead is None or not lead.startswith(OPENS_PREFIX):
        r.errors.append(
            "no <!-- opens: … --> immediately after <pb>. It records the one seam "
            "witness that exists only on the raster — whether the first line is "
            "indented or runs flush to the measure — and the coordinator writing "
            f"@part cannot recover it from the text. One of: "
            f"{', '.join(sorted(OPENS))}")
        return
    value = lead[len(OPENS_PREFIX):].strip()
    if value not in OPENS:
        r.errors.append(
            f"<!-- opens: {value} --> is not one of the three "
            f"({', '.join(sorted(OPENS))}). The set is closed because a coordinator "
            "batches `tei seam --continues/--fresh` off these, and a free-text "
            "witness has to be read one page at a time — which is the thing "
            "dispatching the pass was meant to stop.")


def validate(tei_path: Path, ctx: dict | None = None,
             ratified: bool = False, schema: bool = False) -> Report:
    """Gate one page's TEI. `ratified` switches which provenance rank is expected.

    `schema` adds the **conformance** check — is this actually TEI — against the
    committed `data/tei_all.rng`. It is off here and on at the CLI, because
    compiling `tei_all` costs ~17 s once per process and the test suite calls
    this function hundreds of times. The two checks are complementary and
    neither subsumes the other: every rule below is expressible in conformant
    TEI, so the schema is silent on all of them, and a file can satisfy all of
    them while using an attribute TEI never defined. See `schema.py`.

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

    _opening_witness(body, q, r)

    # forbidden structure.
    #
    # @part used to be banned outright, on the grounds that continuation was a
    # later pass's job. The ban was too wide: a gap's two ends are one fact, and
    # the page *after* the gap is the only place both witnesses exist — it holds
    # the previous page's tail, its own opening text and its own first-line
    # indent. So `harness tei seam` writes @part on both sides, and the TEI is the
    # record rather than a materialization of some sidecar.
    #
    # What is checked here is therefore the *shape*: a legal I/M/F value, on a
    # direct child of <body>, and only on the first or last of them. An element
    # in the middle of a page cannot span either gap, so @part there is always
    # wrong. @prev/@next stay banned — they carry ids, and the id scheme is
    # unsettled; a run-on <list> or <table> is refused by `seam` for that reason
    # rather than given a pointer that resolves to nothing.
    from .seam import body_elements
    spanning = body_elements(root)
    edge = {id(el) for el in (spanning[:1] + spanning[-1:])}
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        name = etree.QName(el).localname
        if el.get("part") is not None:
            if el.get("part") not in ("I", "M", "F"):
                r.errors.append(
                    f"@part={el.get('part')!r} on <{name}> — TEI allows I, M or F")
            elif id(el) not in edge:
                r.errors.append(
                    f"@part on <{name}>, which is neither the first nor the last "
                    "top-level element of <body> — nothing in the middle of a "
                    "page spans either gap")
        for att in ("prev", "next"):
            if el.get(att) is not None and id(el) not in edge:
                r.errors.append(
                    f"@{att} on <{name}>, which is neither the first nor the last "
                    "top-level element of <body> — only those touch a gap")
            if el.get(att) is not None and el.get("part") is not None:
                r.errors.append(
                    f"<{name}> carries both @part and @{att} — one gap, two "
                    "spellings; a fragmentable element is parted, a linkable one "
                    "is linked, never both")
    _check_ids(r, root, ctx)
    # No whitespace immediately before a <note>.
    #
    # The element stands in for the printed marker, and the book sets a thin space
    # before the raised digit ("[albino] ¹)"). That is the same class of thing as
    # the French spacing before `;` and `:` which keying spec 2.9 already
    # overrides: a typesetting convention with no lexical content, which survives
    # nowhere in the book's meaning and which puts a stray space into the reading
    # text of every consumer that strips the marker. Key it tight.
    #
    # Checked here rather than in `normalize` because it is a question about where
    # an element sits, not about a character sequence — `normalize` runs over whole
    # files as text and cannot see that the space precedes a <note> rather than a
    # word.
    #
    # **A note that is a direct child of `<body>` is not anchored at all**, and the
    # whitespace rule has nothing to say about it: there is no character it sets
    # tight against. That is the state every generated page arrives in — the store
    # holds `MarginTextZone-Notes` as one zone for the whole apparatus, so which
    # body marker a note belongs to is a reading and the generator leaves it at the
    # foot. It gets its own error, because the two proxy complaints it used to draw
    # (a stray space, a missing `@n`) both described symptoms of being unanchored
    # while naming something else, and a reviewer who fixes what the message says
    # has not fixed the page.
    for note in root.iter(q("note")):
        if etree.QName(note.getparent()).localname == "body":
            r.errors.append(
                f"<note n={note.get('n')!r}> is a child of <body> — it has not been "
                "anchored. Move it inline to the character its printed marker "
                "follows, and set @n from that marker. Where the apparatus holds "
                "several notes, split them first: the store zones the whole foot as "
                "one block and cannot say how many there are")
            continue
        prev = note.getprevious()
        before = prev.tail if prev is not None else note.getparent().text
        if before and before != before.rstrip():
            r.errors.append(
                f"space before <note n={note.get('n')!r}> — the marker sets tight "
                "against the character it anchors to; the print's thin space is "
                "typesetting, like the French spacing at keying spec 2.9")
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
        # Silent on an unanchored note: the anchoring error already tells the
        # reviewer to set `@n` from the printed marker, and a second line naming the
        # same missing attribute in different words reads as a second thing to do.
        if (note.get("n") is None and NOTE_CONT_COMMENT not in comments_text
                and etree.QName(note.getparent()).localname != "body"):
            r.errors.append("<note> without n= but no continuation comment present")
        if note.get("n") is not None and not note.get("n").isdigit():
            r.warnings.append(f"<note n='{note.get('n')}'>: non-integer marker "
                              "(book uses integers) — confirm against image")

    # figures
    if ctx is not None:
        # The page's own captions are the witness, not a set of ids the context
        # handed over: a figure anchored on the wrong page is the error worth
        # catching, and only the book's own numbering can see it.
        printed = {f["n"] for f in ctx.get("figures_on_page", []) if f["n"]}
        for fig in root.iter(q("figure")):
            n = fig.get("n")
            if n is None:
                r.errors.append("<figure> without n= — anchor it at the figure "
                                "number the caption prints")
            elif n not in printed:
                r.errors.append(
                    f"<figure n='{n}'> — no caption on this page prints that "
                    f"number (this page sets {sorted(printed) or 'none'})")
            if fig.get("facs") is not None:
                # Geometry is the build's join, through `data/readings.md`. A
                # zone id here is the pass placing a figure, which is not its
                # competence and not checkable from the text it can see.
                r.errors.append(
                    f"<figure facs='{fig.get('facs')}'> — figures are anchored "
                    "by the printed number; the build resolves the zones")

    # Tier-1 @facs (optional): if a span cites an OCR line, the line must be
    # real. Mirrors the <figure facs> check above — a dangling citation is
    # strictly worse than none, so it errors rather than warns.
    if ctx is not None:
        line_ids = {str(ln["index"]) for ln in ctx.get("ocr_lines", [])}
        for el in root.iter():
            if not isinstance(el.tag, str) or el.get(XML_LANG) not in TIER1:
                continue
            facs = el.get("facs")
            if facs is None:
                continue
            name = etree.QName(el).localname
            for tok in facs.split():
                lid = tok.lstrip("#")
                if lid not in line_ids:
                    r.errors.append(f"<{name} facs='#{lid}'> matches no "
                                    "supplied OCR line")

    # An unexpanded `index=` is not a dangling pointer — it is a file that never
    # went through `harness tei expand`, holding no text where the ratified form
    # should be. Named as the missing step rather than as a bad reference, and
    # detectable rather than merely suspected: `@index` is not a TEI attribute.
    #
    # **Silent where the element carries no Tier-1 `xml:lang`**, because there the
    # missing step is not this one. `expand` refuses a handle whose element is not
    # a Tier-1 span — "English is not transcluded" — so telling a reviewer to run it
    # would send them to a verb that cannot help, and the check below already says
    # what actually has to happen. Every generated page arrives with one handle per
    # ratified token, so without this the ordinary state of a page nobody has
    # touched is two errors per handle naming two different remedies, one of them
    # inert. A detector firing on the ordinary case buries the one that is not.
    for el in root.iter():
        if (isinstance(el.tag, str) and el.get("index") is not None
                and el.get(XML_LANG) in TIER1):
            r.errors.append(
                f"<{etree.QName(el).localname} index='{el.get('index')}'> was "
                "never expanded — run `harness tei expand` to write the "
                "ratified form in")

    # **A <foreign> with no @xml:lang says nothing at all**, and is the one element
    # where that is true by definition: TEI's <foreign> means "not the surrounding
    # language", so without naming the language it asserts a negative about an
    # unnamed positive. Every other element here has a real untyped state — an
    # untyped <name> records "the page marked a proper noun and did not say what
    # kind", which is a finding — but there is no fact a lang-less <foreign> can be
    # recording.
    #
    # It is a gate rather than a worklist because the pass cannot leave one behind
    # by accident: `harness tei generate` writes exactly this shape, one per
    # `tier1_terms` hit, precisely so the reviewer has to dispose of each. Two
    # dispositions, and both are cheap — assign the language, and `tei expand` fills
    # the ratified glyphs from `gt/ocr/`; or unwrap, because the detector is a floor
    # over inventory marks and cannot tell a Chukchee form from a German surname
    # carrying the same combining diaeresis. `Döring` on `1-022` is the standing
    # case: U+0308 is an inventory mark, `NON_ENGLISH_HITS` fires correctly, and the
    # word is ordinary German in English prose that was never foreign to mark.
    #
    # Unwrapping is the commoner answer on front matter and the rarer one in the
    # body, and nothing here leans either way — that is the judgement being asked
    # for. The check also closes a hole that predates the generator: a hand-written
    # <foreign> with text and no language used to pass in silence.
    for el in root.iter(q("foreign")):
        if el.get(XML_LANG):
            continue
        span = " ".join("".join(el.itertext()).split())[:40]
        held = f"index={el.get('index')!r}" if el.get("index") else repr(span)
        r.errors.append(
            f"<foreign {held}> carries no xml:lang — language unjudged. Assign one "
            "(and `harness tei expand` writes the ratified form in), or unwrap it: "
            "an inventory mark is not by itself a foreign form, and a name in an "
            "ordinary European orthography is not one at all")

    # THE check, re-anchored: provenance rank, not agreement with an upstream file.
    # Every Tier-1 element declares who read it, and this pass may only ever claim
    # the proposed rank. `#ed` is a human's to write; `#htr` belongs to the import.
    # Both the missing case and the over-claim are errors, and the missing case is
    # the more dangerous of the two — an unmarked span is indistinguishable from a
    # ratified one to every consumer that does not check, so silence here would
    # launder a model reading into an adopted glyph identity.
    # The page's ratified tokens, read once. Not from the context payload: this is
    # a check against the store, and reading it out of the same dict the pass was
    # handed would make the two inputs one witness again.
    adopted: set[str] = set()
    if ctx is not None:
        from .context import tier1_terms
        adopted = {t["text"] for t in tier1_terms(ctx["page_ref"],
                                                  Path(ctx["root"]))}
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
        elif resp == ADOPTED:
            # Checked, not accepted. `adopted` holds the page's ratified token set;
            # empty means the page has no ground truth at all, so the claim cannot
            # be true of anything on it.
            text = unicodedata.normalize("NFD", "".join(el.itertext())).strip()
            if text not in adopted:
                r.errors.append(
                    f"PROVENANCE: <{name}> {span!r} claims resp={ADOPTED!r} but "
                    "is not a token in this page's ground truth" +
                    ("" if adopted else
                     " — gt/ocr/ does not hold this page, so nothing on it can "
                     "be adopted") +
                    ". The rank is verified against gt/ocr/ on every run, so it "
                    "also fails once the ground truth is corrected under it")
        elif not ratified and resp != PROPOSED:
            r.errors.append(
                f"PROVENANCE: <{name}> {span!r} claims resp={resp!r} "
                f"({RESP_RANKS[resp]}) — this pass may only emit {PROPOSED!r} or, "
                f"through `harness tei expand`, {ADOPTED!r}; rank rises by a human "
                "act, never by a pass asserting it")
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
    tier1_adopted = 0
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        lang = _lang_of(el)
        own_text = (el.text or "") + "".join(ch.tail or "" for ch in el)
        own_text = unicodedata.normalize("NFD", own_text)
        if lang in TIER1:
            if el.get(XML_LANG) in TIER1:
                tier1_spans += 1
                tier1_adopted += 1 if el.get("resp") == ADOPTED else 0
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
                    f"non-ASCII quote/apostrophe {[f'U+{ord(c):04X}' for c in bad]} "
                    f"in {lang!r} prose: {own_text.strip()[:60]!r}")
        v = el.get(XML_LANG)
        if v and v not in TIER1 and len(v) not in (2, 3):
            r.warnings.append(f"suspicious xml:lang '{v}'")

    # One summary line for the page's provenance state, so a PASS never reads as
    # "these forms are settled". Saying so once is cheaper than a human inferring
    # it from a rank they'd have to go look up.
    #
    # **Split by rank, because it was written when there were three.** It counted
    # every Tier-1 span and called them all proposals "each needing a human reading
    # against the page" — which after `tei expand` is false about exactly the spans
    # `#gt` exists to describe: nobody will read those against this page, the
    # reading happened one artifact upstream, and demanding it again is asking for
    # the retyping the transclusion removed. A worklist line naming work that must
    # not be done is worse than no line, and it is this project's own failure shape
    # — a summary that stays fluent while the thing it summarises moves under it.
    proposed = tier1_spans - tier1_adopted
    if proposed and not ratified:
        r.worklist.append(
            f"{proposed} Tier-1 span(s) at {PROPOSED} — proposals, not adopted "
            "glyph identities; each needs a human reading against the page before "
            "anything downstream may treat it as settled")
    if tier1_adopted:
        r.worklist.append(
            f"{tier1_adopted} Tier-1 span(s) at {ADOPTED} — transcluded from "
            "gt/ocr/ and re-checked against it on this run, so the glyphs want no "
            "reading here; what is unratified about them is which token the pass "
            "chose, not what it says")

    # Proper nouns. The pass marks *category* and never identity: which village
    # Uñiˊsak is, or whether this Allen is that Allen, is the annotation pass's,
    # over finished TEI and with the whole corpus in view.
    names = untyped = 0
    for el in root.iter(q("name")):
        names += 1
        kind = el.get("type")
        if kind is None:
            untyped += 1
        elif kind not in NAME_TYPES:
            r.errors.append(
                f"<name type={kind!r}> is not a declared type "
                f"({', '.join(sorted(NAME_TYPES))})")
        for attr in NAME_IDENTITY_ATTRS:
            if el.get(attr) is not None:
                r.errors.append(
                    f"<name @{attr}> resolves an identity, which this pass does "
                    "not do — mark what the page says the name is and leave "
                    "@ref/@key for the annotation pass over finished TEI")

    # A citation's extent, and nothing about which work it names. Counted rather
    # than gated for presence: a page citing nothing is the ordinary page.
    bibls = 0
    for el in root.iter(q("bibl")):
        bibls += 1
        for attr in BIBL_IDENTITY_ATTRS:
            if el.get(attr) is not None:
                r.errors.append(
                    f"<bibl @{attr}> names which work is cited, which this pass "
                    "does not do — `find authority` is read while collating and "
                    "its answer is not written down; the key is the annotation "
                    "pass's, over finished TEI")

    # Value, and the relations between the ways of stating it. `<measureGrp>` is TEI's
    # "dimensional specifications which relate to the same object", which is read here
    # as *these measures bear on one priced thing* and deliberately not as *these are
    # equal*. The looser reading is the one the chapter needs: 1-094 prices a bundle
    # of tobacco seven ways in one sentence — 30 kopeks in southern Russia, 60 in
    # Yakutsk, 1.80 rubles in Sredne-Kolymsk, 2.40 or 3 black fawn-skins at the Anui
    # fair — and those seven are pointedly *not* equal to each other. Under "equal"
    # the subject would have to sit in seven groups at once, which no tree expresses;
    # under "one object" it is one group, and the ellipsis the print leaves ("in
    # Yakutsk, 60 kopeks") is resolved by the reader who has the paragraph open.
    measures = groups = 0
    for el in root.iter(q("measure"), q("measureGrp")):
        local = etree.QName(el).localname
        if local == "measure":
            measures += 1
            kind = el.get("type")
            if kind is None:
                span = " ".join("".join(el.itertext()).split())[:40]
                r.errors.append(
                    f"<measure> {span!r} carries no @type — which regime "
                    f"of value it belongs to is the whole reason to mark it "
                    f"({', '.join(sorted(MEASURE_TYPES))})")
            elif kind not in MEASURE_TYPES:
                r.errors.append(
                    f"<measure type={kind!r}> is not a declared type "
                    f"({', '.join(sorted(MEASURE_TYPES))})")
        else:
            groups += 1
            if el.find(f".//{q('measure')}") is None:
                r.errors.append(
                    "<measureGrp> holds no <measure> — the element records that "
                    "some measure is a valuation of the thing this span names, so "
                    "one with none in it records nothing")
        for attr in MEASURE_IDENTITY_ATTRS:
            if el.get(attr) is not None:
                r.errors.append(
                    f"<{local} @{attr}> normalizes the value, which this pass does "
                    "not do — the page's own words are the record, and a per-page "
                    "pass minting units produces one vocabulary per page")

    r.metrics = {
        "tier1_spans": tier1_spans,
        # A subset of the above, not a fourth column of the same thing: how much
        # of this page's Tier-1 carries glyphs nobody keyed here.
        "tier1_adopted": tier1_adopted,
        "unclear": len(root.findall(f".//{q('unclear')}")),
        "comments": sum(1 for _ in root.iter(etree.Comment)),
        "notes": sum(1 for _ in root.iter(q("note"))),
        # Reported, never put on the worklist. Under "type only what's evidenced"
        # an untyped name is the designed outcome on most pages, so a worklist line
        # would be permanently non-empty — the noise that buries real signal, and
        # exactly what the footnote-marker rule's prior-superscript condition exists
        # to avoid. Unlike the Tier-1 census above, this count trends nowhere.
        "names": names,
        "names_untyped": untyped,
        "bibls": bibls,
        "measures": measures,
        "measure_groups": groups,
        "worklist": len(r.worklist),
    }
    if schema:
        from .schema import check
        # Last, and appended rather than interleaved: a conformance failure is a
        # different kind of statement from a project-rule failure, and a reader
        # meeting "not conformant TEI" among the edition's own rules would take it
        # for one of them.
        r.errors += check(tree, Path(ctx["root"]) if ctx else Path("."))
    return r
