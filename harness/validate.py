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

from . import apparatus, citations, figrefs
from .detectors import unlicensed_marks
from .entities import (
    ENTDIR,
    ENTITY_CLASSES,
    GEO_CLASSES,
    alias_index,
    auto_forms,
    ent_dir,
    load,
    split_id,
)
from .generate import NOTE_MARKERS
from .langs import TIER1
from .ns import TEI_NS, XML_ID, XML_LANG
from .state import load_toc, toc_starts

XML_ID_ATTR = "{http://www.w3.org/XML/1998/namespace}id"
# TIER1 — the closed set the firewall covers — is `langs.TIER1`, re-exported here
# because this module is where every caller has always looked for it.
# `.claude/skills/transcribe-page/SKILL.md` says when each fires.
# Provenance ranks, strictly ordered, declared as respStmt/@xml:id once in the corpus
# teiHeader and never in a page file — a page is a fragment and defers. `harness tei header`
# (check_corpus_header below) is what holds this dict and that file together; without
# it the two could drift and every page would go on passing. Rank answers *who read this*,
# which is a different question from whether the image decided — that one is
# <unclear>. A confident reading is still only proposed; certainty is not authority.
RESP_RANKS = {
    "#ed": "a human's own act — keyed, confirmed against the page, or promoted",
    "#gt": "machine-read, human-ratified — transcluded from adjudicated ground truth",
    "#llm": "a model's work — proposed, awaiting ratification",
    "#mz": "mechanical — a rule over a store a human keyed, re-derived here",
}
PROPOSED = "#llm"
RATIFIED = "#ed"
# The adopted rank, and the one that needed an argument rather than a slot.
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
# The fifth rank, admitted on exactly the terms `#gt` was and refused anything
# more.
#
# It says: a human wrote an alias row into `edition/entities/` declaring that this form,
# in this book, means this entity, and ratified the entry; a rule then applied
# that declaration here. No model chose it, so `#llm` is false; no human read
# this page, so `#ed` is false. As with `#gt` the responsible act happened one
# artifact upstream, and this records where.
#
# **It is not taken on trust either**, and that is the whole of its licence.
# Every `#mz` link is re-derived on every validation run from the store as it
# stands now — the entity still exists, it is still ratified, the alias is
# still there, still says `auto: yes`, is still claimed by no one else, and the
# element's own text still matches it. Weaken the entry, delete the alias, or
# let a second entity claim the form, and every link resting on it fails. An
# attribute written once and never rechecked would go stale in silence, which is
# the failure this whole arrangement exists to make impossible.
#
# **What it may say is bounded by what a store can be asked.** A rule may say
# what a string refers to (`<rs @ref>`), what a printed cross-reference scans as
# (`<ref>`), and which ToC heading the book opens on the folio this page prints
# (`<milestone>`); it may never say what kind of name the page marked, what
# language a form is in, or what its glyphs are — see the `<name @type>` comment
# below, and the Tier-1 branch that refuses `#mz` outright. The third was
# admitted on the same terms as the first two and against the same test: the ToC
# is book-internal apparatus, which CLAUDE.md's firewall exempts because it *is*
# evidence, and the join is re-derived on every run from the printed folio.
RULED = "#mz"
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
# Identity used to be refused outright, because there was nothing to resolve it
# against and a pointer to nothing is worse than no pointer: it reads as resolved.
# `edition/entities/` is that referent now, so `@ref` is legal and *gated* — it must be a
# `class:slug` naming a record on disk, and the check runs on every page on every
# run rather than once when the link was written.
#
# `@key` and `@nymRef` stay refused, and not as leftovers. One spelling for one
# fact: three attributes meaning "which entity" would make "is this name linked"
# a question with three places to look, and a referential-integrity check that
# missed one would be worse than none. `@key` in particular is TEI's *unresolved*
# identifier — a bare string with no scheme — which is exactly what the class
# prefix exists to replace.
NAME_IDENTITY_ATTRS = ("key", "nymRef")
# The same deferral on <bibl>, which marks a citation's extent and nothing more. The
# attributes differ because TEI spells bibliographic identity differently — @corresp
# and @sameAs point a citation at the work it names — but the rule is one rule: this
# pass records that a work is being cited, never *which* work. `find authority` is
# read while collating and its answer is not written down; `edition/authorities.json`
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
FORBIDDEN_PROSE = set("\u00B4\u02BC\u02BB\u2010\u2013")
LOOKALIKE_GREPS = {  # keying spec §3 — reported over Tier-1 spans as worklist
    "\u00B4": "U+00B4 traps U+02CA", "\u2019": "U+2019 traps U+02CA",
    "\u02BC": "U+02BC traps U+02CA", "\u02BB": "U+02BB traps U+02CA",
    "\u2018": "U+2018 traps U+02CA",
    "\u00B7": "U+00B7 traps U+02D9",
    "\u02E2": "U+02E2 traps U+1D4B/U+1D49", "\u2091": "U+2091 traps U+1D49",
    "\u04E9": "U+04E9 traps U+0275", "\u2010": "U+2010 traps U+002D",
    "\u2013": "U+2013 traps U+002D",
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

    # The same correspondence, one store over. An @ref is `class:slug`, and the
    # class is a TEI private URI prefix that has to be declared here or the
    # reference resolves to nothing once a page is assembled. Both directions
    # again, and the extra one is the worse: a prefixDef the code does not know
    # advertises a class `entity check` would refuse to create.
    prefixes = {p.get("ident") for p in root_el.iter(q("prefixDef"))}
    prefixes.discard(None)
    for missing in sorted(set(ENTITY_CLASSES) - prefixes):
        r.errors.append(
            f"entity class {missing!r} has no <prefixDef ident=\"{missing}\"> — "
            f"a @ref of the form '{missing}:…' would resolve to nothing")
    for extra in sorted(prefixes - set(ENTITY_CLASSES)):
        r.errors.append(
            f"<prefixDef ident=\"{extra}\"> declares a class ENTITY_CLASSES does "
            f"not know — nothing can author an entity under it")

    # **And where each prefix resolves *to*, which the `ident` check above does
    # not see.** `@replacementPattern` is the only statement anywhere of how a
    # `class:slug` becomes a file, so it is the one thing in this header that
    # every `@ref` in the corpus passes through — and it is a *path*, which means
    # it goes stale the moment the store moves. It did: the store went from
    # `entities/` to `edition/entities/` and this header was rewritten by hand,
    # because nothing here was looking. A pattern naming a directory that does not
    # exist resolves every reference in the corpus to nothing while `tei header`
    # reports PASS, which is the failure this file exists to refuse.
    #
    # Derived from `entities.ENTDIR` rather than written out, so the store's own
    # location is stated once and the header is checked against it — the idiom
    # `test_cli_surface` uses on `VERBS.md` and `RESP_RANKS` uses just above.
    for p in root_el.iter(q("prefixDef")):
        ident = p.get("ident")
        if ident not in ENTITY_CLASSES:
            continue                      # already reported as an unknown class
        want_pat = f"{ENTDIR}/{ident}/$1.md"
        got = p.get("replacementPattern")
        # Read project first, then workspace: the pattern is relative to whichever
        # holds the store, and a store in neither resolves every reference to nothing.
        if ent_dir(root).is_dir() and not ent_dir(root).parent.joinpath(
                got.split("/")[1] if got and "/" in got else "").is_dir():
            r.errors.append(f"<prefixDef ident=\"{ident}\"> names {got!r}, which "
                            f"neither the text nor its workspace holds")
        if got != want_pat:
            r.errors.append(
                f"<prefixDef ident=\"{ident}\"> resolves to {got!r}, but the "
                f"store is {ENTDIR!r}, so it should be {want_pat!r} — every "
                f"'{ident}:…' reference in the corpus resolves through this")

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


#: What a cross-reference is re-derived *within*. The generator marks one block
#: of prose at a time, so the check has to cut the page the same way or it would
#: read a paragraph's last word into the next one's first. A nested block is left
#: to its own turn — an anchored `<note>` inside a `<p>` is scanned as a note,
#: exactly as `_place_notes` scanned it — which is what keeps a footnote's text
#: out of the middle of the paragraph it hangs in.
FIGREF_BLOCKS = ("p", "quote", "note", "head", "item", "label", "cell",
                 "trailer", "l")

#: A block whose text is **not** scanned, and which still stops the walk. A
#: caption reading `Fig. 101. Reindeer-Harness` is the picture's own name and not
#: a pointer at it — the generator marks none and the renderer linked none — so a
#: `<figDesc>` is cut out of its figure's text rather than left to be read as a
#: reference nobody marked.
FIGREF_OPAQUE = ("figDesc",)


def _figref_flat(el) -> tuple[str, list[tuple[int, int, object]]]:
    """One block's own text, and where each `<ref>` in it starts and ends.

    The same string the generator scanned: the text of this block and of the
    inline elements inside it, with the printed line breaks kept, and without the
    text of any nested block.
    """
    out: list[str] = []
    marks: list[tuple[int, int, object]] = []
    at = 0

    def walk(node, top: bool) -> None:
        nonlocal at
        if not top and etree.QName(node).localname in (
                FIGREF_BLOCKS + FIGREF_OPAQUE):
            # **The marker used to have to be put back here, and does not now.**
            # The generator once spliced a `<note>` into the prose *at* its
            # marker and deleted the character, so this had to re-insert it —
            # one character out, one character back — or it read a different
            # string than the rule read. That was not cosmetic: `1-143` sets
            # "illustrated by Nelson.¹ Fig. 22, b", and without the superscript
            # the authority guard sees `Nelson.` immediately in front of a
            # reference to this book's own figure and refuses a mark the rule
            # correctly wrote. Notes are not spliced any more — the marker stays
            # in the text where the printer set it, wrapped in a `<ref>` — so the
            # string is the print's without anything being restored to it.
            return
        start = at
        if node.text:
            out.append(node.text)
            at += len(node.text)
        for kid in node:
            if isinstance(kid.tag, str):
                walk(kid, False)
            if kid.tail:
                out.append(kid.tail)
                at += len(kid.tail)
        if not top and etree.QName(node).localname == "ref":
            marks.append((start, at, node))

    walk(el, True)
    return "".join(out), marks


def _text_after(el, limit: int = 80) -> str:
    """The prose that follows an element, across whatever markup comes next.

    The citation rule reads what stands after a name, and the locator is
    routinely on the far side of an element boundary — `Nelson, Plate LXXVI,
    Fig. 1` puts a figure reference between the name and its page. So this is
    the element's tail plus its following siblings' text, not `@tail` alone.
    """
    out = [el.tail or ""]
    for sib in el.itersiblings():
        if isinstance(sib.tag, str):
            out.append("".join(sib.itertext()))
        out.append(sib.tail or "")
        if sum(len(s) for s in out) >= limit:
            break
    return "".join(out)[:limit]


def _cites(el, form: str, ref: str, sigla: list[dict], store: dict,
           idx: dict) -> bool:
    """Does the page cite this name here, as the work this link names?

    Three tables and all three must agree: the entity store claims the form for
    this entry, `Authorities Quoted` resolves the printed siglum to one work, and
    that work's `source:` entry is this one. It is the same call the generator
    made, over the same text, which is what makes the mark re-derivable rather
    than merely re-readable.
    """
    if not any(c["id"] == ref for c in idx.get(form, [])):
        return False
    key = citations.cited(form, _text_after(el), sigla)
    return bool(key) and citations.work_of(key, store) == ref


def _figrefs(root, r: Report, ctx: dict | None) -> tuple[int, int]:
    """Every `<ref>` mark re-derived from the page's own text, both directions.

    **This is `#mz`'s licence, applied to the second thing that carries it.** A
    figure cross-reference is a rule reading printed text — the numerals after
    `Fig.`, the plate that scopes them, and the `Authorities Quoted` store's
    answer to whose plate it is. So it is re-derived here on every run exactly as
    an entity link is: edit the text under a mark, or add the citing author to
    the store, and the mark fails rather than going quietly stale.

    The failure it exists to catch is not a broken link. It is a *working* link
    to the wrong picture — the book restarts figure numbering at 1 on every
    plate, so a number scoped to the wrong plate opens a real leaf with a caption
    that reads correctly under it.

    Returns `(marked, unmarked)`. **A printed reference with no mark is a
    worklist line and not an error**, on entity-link terms and for a sharper
    reason: deleting a mark the sentence does not support is precisely what a
    collator is being shown it for. The count says how many, so a page nobody has
    read is not indistinguishable from one where every deletion was somebody's.
    """
    cited = apparatus.authority_names(
        Path(ctx["root"]) if ctx and ctx.get("root") else Path("."))
    marked = unmarked = 0
    seen = set()
    for block in root.iter():
        if not isinstance(block.tag, str):
            continue
        if etree.QName(block).localname not in FIGREF_BLOCKS:
            continue
        flat, marks = _figref_flat(block)
        seen.update(id(el) for _, _, el in marks)
        want = {(s["start"], s["end"]): s for s in figrefs.scan(flat)
                if not figrefs.foreign_citation(flat[:s["start"]], cited)}
        # **A footnote reference is re-derived here too, by its own rule.** It is
        # a `<ref>` and carries `#mz`, so it may not pass unexamined — but it is
        # not a cross-reference and `figrefs.unmark` rightly refuses it: what a
        # figure number resolves to is a join over `gt/fig/`, and what `¹`
        # resolves to is note 1 on this page. Two things are checked, and both
        # read the text this block already holds. The mark must wrap exactly the
        # marker `@n` names — `keying_spec.md` §2.10 fixes that character
        # corpus-wide — and it must not fall inside a figure's locant run, which
        # is the same exclusion the generator applies and computed from the same
        # two objects rather than from a second copy of the rule.
        locants = []
        for sp in figrefs.scan(flat):
            tail = figrefs.LOCANTS.match(flat, sp["end"])
            if tail is not None and tail.end() > sp["end"]:
                locants.append((sp["end"], tail.end()))
        for start, end, el in marks:
            if el.get("type") == "note":
                n, span = el.get("n"), "".join(el.itertext())
                want_char = (NOTE_MARKERS[int(n)]
                             if n and n.isdigit() and int(n) < len(NOTE_MARKERS)
                             else None)
                if span != want_char:
                    r.errors.append(
                        f"<ref type='note' n={n!r}> wraps {span!r}, which is not "
                        f"the marker that number is printed as. The mark stands "
                        f"over the printed superscript and nothing else")
                elif any(a <= start < b for a, b in locants):
                    r.errors.append(
                        f"<ref type='note' n={n!r}> marks a superscript inside a "
                        f"figure's sub-part locants — `(Fig. 155, d², e¹)` names "
                        f"details of one picture and anchors no note")
                continue
            marked += 1
            resp = el.get("resp")
            handle = figrefs.unmark(el.get("type"), el.get("n"), el.get("cRef"))
            span = " ".join("".join(el.itertext()).split())
            if handle is None:
                r.errors.append(
                    f"<ref type={el.get('type')!r} n={el.get('n')!r} "
                    f"cRef={el.get('cRef')!r}> {span[:24]!r} is not a "
                    f"cross-reference this corpus can read. @type is one of "
                    f"{', '.join(figrefs.KINDS)}, @n is the number the page "
                    f"prints, and @cRef — only on a figure — is the plate that "
                    f"scopes it, spelt `Plate XXI`")
                continue
            if resp is not None and resp not in RESP_RANKS:
                r.errors.append(f"<ref n={el.get('n')!r}> carries resp={resp!r}, "
                                f"which is not a declared rank")
            # Taken off the expected set whatever the rank, because the other
            # direction asks whether a printed reference is *marked* and a
            # collator's own `#llm` mark answers that as well as a rule's. Only
            # the re-derivation below is `#mz`'s: a reading is not re-derivable,
            # which is the whole difference between the two ranks.
            hit = want.pop((start, end), None)
            if resp != RULED:
                continue
            # The whole licence of #mz, re-derived: the page still prints this
            # reference, at this extent, scoped to this plate, and no authority
            # in front of it says the plate is somebody else's.
            if hit is None:
                r.errors.append(
                    f'<ref n={el.get("n")!r} resp="{RULED}"> {span[:24]!r} no '
                    f"longer derives: the page's text no longer prints a "
                    f"cross-reference here. Re-run `harness tei generate` for "
                    f'this page, or judge the span yourself and set '
                    f'resp="{PROPOSED}"')
            elif (hit["kind"], hit["number"], hit["plate"]) != (
                    handle["kind"], handle["number"], handle["plate"]):
                says = f"{hit['kind']} {hit['number']}"
                if hit["plate"]:
                    says += f", on Plate {hit['plate']}"
                r.errors.append(
                    f'<ref n={el.get("n")!r} resp="{RULED}"> — the page prints '
                    f"{says} here. A rule-applied mark that disagrees with the "
                    f"rule is the stale stamp {RULED} exists to prevent")
        # The other direction: what the page prints and no mark covers. A page is
        # collated after it is generated, so a rule that widened afterwards leaves
        # a reference plain here — indistinguishable, from outside, from one a
        # collator deleted on purpose.
        unmarked += len(want)
        for s in sorted(want.values(), key=lambda s: s["start"]):
            printed = ("Plate " if s["kind"] == "plate" else "Fig. ") + s["number"]
            if s["plate"]:
                printed += f" (Plate {s['plate']})"
            r.worklist.append(
                f"{printed} is printed here and carries no <ref> mark. Either it was "
                f"generated before the rule found it — `harness tei generate "
                f"--force` — or a collator judged it not a reference")

    # **A mark the check never reached is the state this whole arrangement
    # exists to refuse.** An unchecked `#mz` is indistinguishable from a checked
    # one to anything that does not check, so a `<ref>` outside every scanned
    # block — inside a `<figDesc>`, or loose in the body — is an error rather
    # than a silent pass.
    for el in root.iter(f"{{{TEI_NS}}}ref"):
        if id(el) in seen:
            continue
        marked += 1
        r.errors.append(
            f"<ref n={el.get('n')!r}> stands outside every block this gate "
            f"scans, so nothing re-derives it. A cross-reference belongs in the "
            f"prose that prints it; a caption names its own picture and carries "
            f"none")
    return marked, unmarked


# ---------------------------------------------------------------- the rules
#
# One function per `── rule: name ──` banner in `validate`, extracted from a
# body that had grown to 800 lines. **Argument order is `(root, q, ctx, r)`**,
# inputs before the report they append to, and a rule takes only what it reads —
# the three older helpers here (`_check_ids`, `_opening_witness`, `_figrefs`)
# each chose a different order, which is the naming drift a later pass is for.
#
# A rule that produces a counter **returns it** rather than setting a local, on
# `_figrefs`' precedent: `r.metrics` is assigned wholesale at the end from
# values gathered the length of the function, so a rule that kept its own count
# would be invisible to it. That is why these first ten — the ones that produce
# nothing — came out first and alone.


def _rule_line_and_division(root, q, ctx, r: Report) -> None:
    """Neither element belongs in a page file. ALTO holds the line record, and a
    page is div-less because a chapter spans a hundred of them —
    `docs/edition.md` and the collator's contract carry the reasoning."""
    if root.find(f".//{q('lb')}") is not None:
        r.errors.append("<lb/> present — ALTO holds the line record")
    if root.find(f".//{q('div')}") is not None:
        r.errors.append("<div> present — page files are div-less")


def _rule_notes(root, q, ctx, r: Report) -> None:
    """Marker and note: at the foot, numbered, or explained by a continuation."""
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


def _rule_unexpanded_handle(root, q, ctx, r: Report) -> None:
    """An unexpanded `index=` is not a dangling pointer — it is a file that never
    went through `harness tei expand`, holding no text where the ratified form
    should be. Named as the missing step rather than as a bad reference, and
    detectable rather than merely suspected: `@index` is not a TEI attribute.

    **Silent where the element carries no Tier-1 `xml:lang`**, because there the
    missing step is not this one. `expand` refuses a handle whose element is not
    a Tier-1 span — "English is not transcluded" — so telling a reviewer to run it
    would send them to a verb that cannot help, and `foreign-lang` already says
    what actually has to happen. Every generated page arrives with one handle per
    ratified token, so without this the ordinary state of a page nobody has
    touched is two errors per handle naming two different remedies, one of them
    inert. A detector firing on the ordinary case buries the one that is not.
    """
    for el in root.iter():
        if (isinstance(el.tag, str) and el.get("index") is not None
                and el.get(XML_LANG) in TIER1):
            r.errors.append(
                f"<{etree.QName(el).localname} index='{el.get('index')}'> was "
                "never expanded — run `harness tei expand` to write the "
                "ratified form in")


def _rule_foreign_lang(root, q, ctx, r: Report) -> None:
    """**A <foreign> with no @xml:lang says nothing at all**, and is the one element
    where that is true by definition: TEI's <foreign> means "not the surrounding
    language", so without naming the language it asserts a negative about an
    unnamed positive. Every other element here has a real untyped state — an
    untyped <name> records "the page marked a proper noun and did not say what
    kind", which is a finding — but there is no fact a lang-less <foreign> can be
    recording.

    It is a gate rather than a worklist because the pass cannot leave one behind
    by accident: `harness tei generate` writes exactly this shape, one per
    `tier1_terms` hit, precisely so the reviewer has to dispose of each. Two
    dispositions, and both are cheap — assign the language, and `tei expand` fills
    the ratified glyphs from `gt/ocr/`; or unwrap, because the detector is a floor
    over inventory marks and cannot tell a Chukchee form from a German surname
    carrying the same combining diaeresis. `Döring` on `1-022` is the standing
    case: U+0308 is an inventory mark, `NON_ENGLISH_HITS` fires correctly, and the
    word is ordinary German in English prose that was never foreign to mark.

    Unwrapping is the commoner answer on front matter and the rarer one in the
    body, and nothing here leans either way — that is the judgement being asked
    for. The check also closes a hole that predates the generator: a hand-written
    <foreign> with text and no language used to pass in silence.
    """
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


def _rule_entities(root, q, ctx, r: Report, store=None):
    """Proper nouns, and the entity references over them. The pass marks
    *category* from the page; identity resolves here, against `edition/entities/`.

    **Resolves the store and returns it**, because `relink-missing` needs the
    same one — the second of the three couplings, and returning it is what makes
    that visible at the call site rather than buried in a shared local.

    Returns `(store, names, untyped, refs, ruled)`.
    """
    # Proper nouns, and the entity references over them. The pass marks
    # *category* from the page; identity now resolves, against `edition/entities/`.
    #
    # **A supplied `store` is not the `tier1_terms` case.** That one is re-read
    # from `gt/ocr/` on purpose and must never come out of `ctx`, because the
    # pass authored the TEI *from* `ctx` and checking one against the other would
    # make the two witnesses one. The entity store is the opposite: it is the
    # reference this resolves identity against, not anything the pass produced,
    # and `load(root)` here and in `build_context` read the same files moments
    # apart. Hoisting that read out of a corpus loop shares an input; it does not
    # merge a comparison. Every verdict below is still computed from this page.
    store = load(Path(ctx["root"]) if ctx and ctx.get("root") else Path(".")) \
        if store is None else store
    idx = alias_index(store)
    autos = auto_forms(idx)
    # The printed resolution table, for the names the alias table cannot resolve
    # alone: `Nelson` is a man and a book, and a locator after it says which.
    sigla = apparatus.sigla(
        Path(ctx["root"]) if ctx and ctx.get("root") else Path("."))
    names = untyped = refs = ruled = 0
    # **The `once` forms this page has already spent its rule-link on.** Filled
    # in document order, `root.iter` yielding it. This checks the *count* and not
    # the position — that the link sits on the page's first occurrence rather
    # than its third is `tei diff` against the freshly generated baseline, which
    # is where a placement disagreement belongs and where a reader can see it.
    # What is checked here is the failure that is silent otherwise: two `#mz`
    # links on one form, which is `once` having quietly become twice.
    spent: dict[str, str] = {}
    for el in root.iter(q("name"), q("rs")):
        local = etree.QName(el).localname
        kind = el.get("type")
        if local == "name":
            names += 1
            if kind is None:
                untyped += 1
            elif kind not in NAME_TYPES:
                r.errors.append(
                    f"<name type={kind!r}> is not a declared type "
                    f"({', '.join(sorted(NAME_TYPES))})")
            for attr in NAME_IDENTITY_ATTRS:
                if el.get(attr) is not None:
                    r.errors.append(
                        f"<name @{attr}> spells identity a way this corpus does "
                        f"not — @ref is the one spelling, and it holds a "
                        f"`class:slug` pointing into edition/entities/")
        span = " ".join("".join(el.itertext()).split())
        ref = el.get("ref")
        if local == "rs" and not ref:
            r.errors.append(
                f"<rs> {span[:40]!r} carries no @ref. `rs` is this corpus's "
                "entity reference and nothing else — it says which entity a "
                "string names, so one with no referent marks nothing. Give it a "
                "@ref or unwrap it")
            continue
        if ref is None:
            continue
        refs += 1
        rec = store.get(ref)
        if rec is None:
            try:
                split_id(ref)
                why = "no such entity in edition/entities/"
            except ValueError as e:
                why = str(e).split(": ", 1)[-1]
            r.errors.append(
                f"<{local} ref={ref!r}> resolves to nothing — {why}. Either the "
                f"entry has not been written (`harness entity new {ref}`) or the "
                f"reference is wrong")
            continue
        # A type from the page and a class from the store are two witnesses to
        # one fact, so they are compared rather than one overwriting the other.
        # An *untyped* <name ref> is fine: untyped is a designed state, and the
        # class does not fill it in — only a reader of the page can say the page
        # marked a proper noun of some kind.
        if local == "name" and kind is not None:
            want = ENTITY_CLASSES[rec["class"]]
            if want != kind:
                says = repr(want) if want else "(none — it is never a <name>)"
                r.errors.append(
                    f"<name type={kind!r} ref={ref!r}> — {ref} is class "
                    f"{rec['class']!r}, whose name-type is {says}. One of the "
                    f"two is about the wrong entity")
        # **A rule may mark a proper noun only where the class guarantees one.**
        # `#mz` on a `<name>` asserts two things — that this string names that
        # entity, and that the page marked a proper noun of some category. The
        # first is the alias table's and holds for every class; the second holds
        # for the four geographic classes, whose aliases are named things by
        # construction, and fails for the rest: `people:` carries *the Reindeer
        # people*, `event:` carries *the Expedition*, and a `<name>` around a
        # common noun invents an entity that is not in the book. Those stay
        # `<rs>`, which asserts reference and nothing else. A human may still
        # write `<name resp="#llm">` anywhere the page shows a proper noun; what
        # is refused is a *rule* doing it on the store's word alone.
        if local == "name" and el.get("resp") == RULED \
                and rec["class"] not in GEO_CLASSES:
            r.errors.append(
                f"<name ref={ref!r} resp=\"{RULED}\"> — {rec['class']!r} is not a "
                f"geographic class, so no rule may promote this link to a "
                f"<name>. An alias outside {'/'.join(GEO_CLASSES)} can be a "
                f"common noun, and a <name> around one invents an entity the "
                f"book does not have. Use <rs>, or judge the span yourself and "
                f"set resp=\"{PROPOSED}\"")
        if local == "rs" and kind is not None:
            r.errors.append(
                f"<rs type={kind!r} ref={ref!r}> — an rs carries no @type here. "
                f"The class is the ref's prefix, so a second copy of it can only "
                f"disagree with the first")
        if rec["status"] != "ratified":
            r.worklist.append(
                f"<{local} ref={ref!r}> points at a proposed entry — resolvable, "
                f"but nobody has audited it. `harness entity ratify {ref}` after "
                f"reading it against the pages it claims")
        resp = el.get("resp")
        if resp is not None and resp not in RESP_RANKS:
            r.errors.append(f"<{local} ref={ref!r}> carries resp={resp!r}, which "
                            f"is not a declared rank")
        elif resp == RULED:
            ruled += 1
            # **The whole licence of #mz, re-derived here on every run.** The
            # claim is not "a rule wrote this once" but "the store says this
            # right now": the entry is ratified, the alias is still there and
            # still uncontested, and the text still matches it. Weaken any of
            # those in `edition/entities/` and the link fails rather than going quietly
            # stale — the same maintenance property #gt has, and the only reason
            # a machine-applied rank is admissible at all.
            form = " ".join(span.split())
            owner = autos.get(form)
            if owner is not None and idx[form][0]["scope"] == "first":
                # The second `#mz` link on a `once` form derives from nothing:
                # the rule spent this page's link higher up. Recorded before the
                # `owner is None` cascade so the message below can name where.
                if form in spent:
                    owner = None
                else:
                    spent[form] = owner
            if owner is None and _cites(el, form, ref, sigla, store, idx):
                # **The printed citation form is the other way a rule may resolve
                # a name**, and it is re-derived exactly as the alias table is:
                # the page still prints a locator after this name, the sigla
                # still say which work, and the entry still says it is that work.
                # Edit any of the three and the link fails. It is checked here
                # rather than accepted on the attribute's word for `#mz`'s only
                # reason for existing.
                owner = ref
            if owner is None:
                claims = idx.get(form, [])
                if not claims:
                    why = (f"the store has no alias {form!r} — it was removed, "
                           f"or the text was edited after the link was made")
                elif len(claims) > 1:
                    why = (f"{form!r} is now claimed by "
                           f"{' and '.join(sorted(c['id'] for c in claims))}, so "
                           f"it is ambiguous and no rule may resolve it")
                elif not claims[0]["auto"]:
                    why = f"{form!r} is `auto: no` — it needs a reader, not a rule"
                elif claims[0]["scope"] == "first" and form in spent:
                    why = (f"{form!r} is `auto: once` and this page already "
                           f"links it to {spent[form]}. The convention is one "
                           f"link per page, on the first occurrence; the rest "
                           f"stay bare")
                else:
                    why = (f"{claims[0]['id']} is {store[claims[0]['id']]['status']}"
                           f", and a rule may only apply a ratified entry")
                r.errors.append(
                    f"<{local} ref={ref!r} resp=\"{RULED}\"> no longer derives: {why}. "
                    f"Re-run `harness tei generate` for this page, or judge the "
                    f"span yourself and set resp=\"{PROPOSED}\"")
            elif owner != ref:
                r.errors.append(
                    f"<{local} ref={ref!r} resp=\"{RULED}\"> — the store now resolves "
                    f"{form!r} to {owner}. A rule-applied link that disagrees "
                    f"with the rule is the stale stamp {RULED} exists to prevent")

    return store, names, untyped, refs, ruled


def _rule_provenance(root, q, ctx, r: Report, ratified: bool = False) -> None:
    """THE check, re-anchored: provenance rank, not agreement with an upstream file.

    Every Tier-1 element declares who read it, and this pass may only ever claim
    the proposed rank. `#ed` is a human's to write. Both the missing case and the
    over-claim are errors, and the missing case is the more dangerous of the two —
    an unmarked span is indistinguishable from a ratified one to every consumer
    that does not check, so silence here would launder a model reading into an
    adopted glyph identity.

    **Deliberately no check that `@resp` resolves to a `<respStmt>` in this
    file.** The ranks are declared once in the corpus teiHeader; a page file is a
    fragment that already defers title, publication and source the same way, so a
    pointer that dangles when the page is read alone is the normal state and not
    a defect. `RESP_RANKS` is the closed set, and membership in it is the real
    check.

    **The verbatim-substring test against `catmus_draft` used to live here, and
    is gone.** It enforced the *canonicity of the upstream* — every Tier-1 span
    had to appear character-for-character in whatever `ocr/` happened to hold —
    and that is not what the firewall is about. The firewall is a rule about
    **hierarchies of provenance**: a glyph identity may not be *originated* by a
    model reading a scan, and a lower-authority witness may not be promoted to a
    higher one. It says nothing about whether some particular upstream file
    agrees.

    Anchored to an upstream instead, it was one of three things depending on what
    the draft happened to be, and never the intended one:

      * draft is a human key       -> the test binds, but only incidentally; what
                                      binds is the human's authority, not the bytes.
      * draft is recognizer output -> unsatisfiable. CATMuS emits no inventory
                                      glyph at all (0% of the inventory, measured),
                                      so every Tier-1 span fails on a correct TEI.
      * draft is an LLM reading    -> tautology. The check compares a TEI against
                                      its own source and passes unconditionally,
                                      while still rendering as a verified PASS.

    The replacement belongs in the TEI, not here: each Tier-1 span carries its own
    provenance, and a ratified build refuses to emit a span whose provenance is
    machine-proposed. Until that exists this file makes no provenance claim, and
    `provenance-summary`'s count is a worklist item rather than a verdict — which
    is the honest state, where a PASS on an unsatisfiable or tautological test was
    not.

    **`ratified` selects branches here, and never gates the rule.** It is one of
    only two rules it reaches into at all (`provenance-summary` is the other), so
    it is a parameter rather than a dispatch key.
    """
    # The page's ratified tokens, read once. Not from the context payload: this is
    # a check against the store, and reading it out of the same dict the pass was
    # handed would make the two inputs one witness again.
    adopted: set[str] = set()
    if ctx is not None:
        from .context import tier1_terms
        # `keys=False`: only `text` is read here, and the `key` column costs a
        # walk of every keyed page (1.57s) to build. This ran once per page on
        # top of the one `build_context` already pays, so a corpus-wide
        # `tei validate` was rebuilding the lexicon index twice a page.
        adopted = {t["text"] for t in tier1_terms(ctx["page_ref"],
                                                  Path(ctx["root"]), keys=False)}
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
        elif resp == RULED:
            # Refused here rather than left to fall through, and in *both* modes.
            # Unratified, the "this pass may only emit #llm" branch below would
            # have caught it; ratified, it would have been a worklist line — a
            # rank asserting a machine read a Tier-1 glyph, reported as work
            # pending rather than as the firewall breach it is. The rank is
            # confined to entity reference — `<rs>`, or the geographic `<name>`
            # a rule link is emitted as — and a Tier-1 span is the one place
            # nothing mechanical may speak at all. A rule link *enclosing* a
            # handle is untouched by this: the element carrying `#mz` holds no
            # glyphs of its own, and the `<foreign>` inside keeps its own rank.
            r.errors.append(
                f"PROVENANCE: <{name}> {span!r} claims resp={RULED!r}, which says "
                f"a rule applied it. No rule may originate a Tier-1 reading — "
                f"{RULED} is confined to @ref on an entity reference, and never "
                f"carries a glyph")
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


def _rule_lang_and_glyphs(root, q, ctx, r: Report) -> tuple[int, int]:
    """Declared language codes, and codepoint hygiene **by scope**.

    The scoping is the whole of it, and the two arms are deliberately not one.
    Inside a Tier-1 span the lookalike greps fire, because there U+0027 and
    U+002D are the only apostrophe and hyphen (`keying_spec.md` §1) and anything
    resembling them is a notation question a human answers. Outside one, English
    prose reproduces the print *including* curly quotes, so the same character is
    correct — which is why `LOOKALIKE_GREPS` and the prose table are held apart
    by `test_lookalike_scope.py` rather than merged.

    A **mark licence** violation is not scoped, and that asymmetry is the point:
    an impossible mark/base sequence is wrong in a Latin binomial and in Russian
    prose for the same reason it is wrong in a Chukchee form, so it is an error
    rather than a worklist line — there is no reading for a human to choose
    between.

    **Returns `(tier1_spans, tier1_adopted)`, and this is the rule that counts
    them** — not `provenance`, which is adjacent and whose name suggests it. The
    enumeration commit credited the wrong neighbour;
    `test_validate_rules.py` now checks the attribution against the code.
    """
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
    return tier1_spans, tier1_adopted


def _rule_tier1_unglossed(root, q, ctx, r: Report) -> int:
    """A Tier-1 span a reader can do nothing with. Neither glossed nor identified
    is a warning and not an error, because the book genuinely leaves forms
    bare and no model may write a gloss the page does not carry — the remedy
    is to link the printed gloss, mark the name, or say why neither applies.

    **Glossed is decided by `xml:id` membership, and a span with no id is
    unglossed exactly rather than approximately.** `ids.py` and this file both
    state the scheme's rule as "no id without a referrer": an id exists *iff*
    something points at it. So absence of an id is absence of an incoming
    gloss, by construction and not by luck — which is why there is no
    containment fallback here, the inference `ids.pair_glosses` and
    `ids.page_glossary` both refuse in writing.

    **Identified is a `<name>` carrying an approved `@type`, or an `@ref`.**
    A bare `<name>` is not enough here, and `entities`' `names_untyped` count
    does not license one: that argument is about the page's names at large,
    most of which are English prose and typed only where the page evidences a
    category. A Tier-1 span is a handful per page and the question asked of it
    is different — a native word a reader cannot place is exactly the thing
    this edition exists to resolve, and "it is a name of some kind" places it
    nowhere. `@ref` counts because a rule-applied link is an `<rs>`, which
    carries no `@type` at all: the class is the ref's own prefix.

    **A re-mention does not fire.** `1-101` glosses `qeˊñu` in one item and
    uses it inside another item's gloss; demanding a second gloss there asks
    for the same fact twice. Compared case-sensitively — folding here would
    import `marks.fold`'s judgement that two settings are one word, which is
    not this gate's to make.

    Returns the count of unglossed spans.
    """
    from .ids import glossed_ids

    def _span(el) -> str:
        return unicodedata.normalize(
            "NFD", " ".join("".join(el.itertext()).split()))

    glossed = glossed_ids(root)
    by_id = {i: el for el in root.iter()
             if isinstance(el.tag, str) and (i := el.get(XML_ID_ATTR))}
    glossed_text = {_span(by_id[i]) for i in glossed if i in by_id}
    tier1_unglossed = 0
    for el in root.iter():
        if not isinstance(el.tag, str) or el.get(XML_LANG) not in TIER1:
            continue
        parent = el.getparent()
        if (el.get(XML_ID_ATTR) in glossed
                or any(isinstance(d.tag, str)
                       and etree.QName(d).localname == "name"
                       and d.get("type") in NAME_TYPES
                       for d in el.iter())
                or el.get("ref")
                or (parent is not None and parent.get("ref"))):
            continue
        span = _span(el)
        if span in glossed_text:
            continue
        tier1_unglossed += 1
        r.warnings.append(
            f"<{etree.QName(el).localname} xml:lang={el.get(XML_LANG)!r}> "
            f"{span[:40]!r} is "
            "neither glossed nor identified — no <gloss target> points at it, "
            "no <name> with a declared @type covers it, and no entity @ref "
            "stands over it, so a reader meeting it has nowhere to go. Link "
            "the printed gloss, type the name, or leave it if the page really "
            "says nothing about the word")
    return tier1_unglossed


def _rule_provenance_summary(tier1_spans: int, tier1_adopted: int,
                             ratified: bool, r: Report) -> None:
    """One summary line for the page's provenance state, so a PASS never reads as
    "these forms are settled". Saying so once is cheaper than a human inferring
    it from a rank they'd have to go look up.

    **Split by rank, because it was written when there were three.** It counted
    every Tier-1 span and called them all proposals "each needing a human reading
    against the page" — which after `tei expand` is false about exactly the spans
    `#gt` exists to describe: nobody will read those against this page, the
    reading happened one artifact upstream, and demanding it again is asking for
    the retyping the transclusion removed. A worklist line naming work that must
    not be done is worse than no line, and it is this project's own failure shape
    — a summary that stays fluent while the thing it summarises moves under it.

    **The first coupling, and it takes its counters as arguments** rather than
    reaching for them: `lang-and-glyphs` sets them, not `provenance`, and the
    enumeration commit credited the wrong neighbour. Passing them in is what
    makes the dependency impossible to misread from here.
    """
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


def _rule_relink_missing(tei_path, store, r: Report) -> None:
    """**The other direction of the same check.** `entities` re-derives the `#mz`
    links this page *has*; nothing looked for the ones it lacks. A page is
    collated after it is generated, so an entry ratified afterwards leaves its
    form in plain text here — and from the outside that is indistinguishable from
    a page whose text never printed the form at all. A worklist line, not an
    error: the page is not wrong, it is out of date with a store that moved under
    it, and `harness entity ratify` is what brings it up.

    **One of the three couplings**, and the reason this signature is not
    `(root, q, ctx, r)`: it reuses the `store` the `entities` rule loaded, and it
    reads the file's *text* rather than the parsed tree, so it takes `tei_path`.
    Both are the honest dependencies rather than a uniform shape imposed on them.
    """
    from .relink import missing

    unlinked = missing(tei_path.read_text(encoding="utf-8"), store)
    if unlinked:
        forms = sorted({f"{u['form']} → {u.get('id') or u['why']}"
                        for u in unlinked})
        r.worklist.append(
            f"{len(unlinked)} form(s) a ratified entry now claims sit unlinked "
            f"here: {'; '.join(forms[:6])}"
            f"{' …' if len(forms) > 6 else ''}. The page was collated before the "
            f"store said so; `harness entity ratify` applies them")


def _rule_measures(root, q, ctx, r: Report) -> tuple[int, int]:
    """Value, and the relations between the ways of stating it. `<measureGrp>` is TEI's
    "dimensional specifications which relate to the same object", which is read here
    as *these measures bear on one priced thing* and deliberately not as *these are
    equal*. The looser reading is the one the chapter needs: 1-094 prices a bundle
    of tobacco seven ways in one sentence — 30 kopeks in southern Russia, 60 in
    Yakutsk, 1.80 rubles in Sredne-Kolymsk, 2.40 or 3 black fawn-skins at the Anui
    fair — and those seven are pointedly *not* equal to each other. Under "equal"
    the subject would have to sit in seven groups at once, which no tree expresses;
    under "one object" it is one group, and the ellipsis the print leaves ("in
    Yakutsk, 60 kopeks") is resolved by the reader who has the paragraph open.

    Returns `(measures, groups)`.
    """
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
    return measures, groups


def _rule_bibl_extent(root, q, ctx, r: Report) -> int:
    """A citation's extent, and nothing about which work it names. Counted rather
    than gated for presence: a page citing nothing is the ordinary page.

    **Returns its count**, like every rule here that feeds `metrics`. `r.metrics`
    is assigned wholesale from values gathered the length of `validate`, so a
    rule holding its own counter would simply vanish from the report.
    """
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
    return bibls


def _rule_milestones(root, q, ctx, r: Report) -> None:
    """An id must exist in the ToC — that is the hard check. Falling outside the
    supplied window is only a warning: the window is keyed to a predicted folio,
    so a milestone outside it may mean the prediction is wrong rather than the
    milestone. Marks inform; they do not decide.

    **A `#mz` milestone is re-derived here, on the page's own printed folio.**
    `resp="#mz"` on one says a rule joined `edition/toc.json` to this page, and
    `#mz`'s whole licence is that the claim is recomputed from its store every
    run rather than trusted because it is written down. What is re-derived is
    the durable half — the ToC opens this id at the folio this page prints —
    and not the generator's text match, deliberately: review is expected to
    restructure the block the head sits in, and a check that failed when a
    collator did its job would be a check nobody could satisfy honestly.
    """
    window_ids, all_toc_ids = set(), set()
    starts_here: set[str] = set()
    if ctx:
        window_ids = {e["id"] for e in ctx.get("toc_window", [])}
        toc = load_toc(Path(ctx.get("root", ".")))
        all_toc_ids = {e["id"] for e in toc if e.get("id")}
        pb = root.find(f".//{q('pb')}")
        printed = pb.get("n") if pb is not None else None
        starts_here = {e["id"] for e in
                       toc_starts(toc, int(printed) if (printed or "").isdigit()
                                  else None)}
    for ms in root.iter(q("milestone")):
        extra = set(ms.keys()) - {"unit", "n", "resp"}
        if extra:
            r.errors.append(f"<milestone> carries extra attributes {extra}")
        if ms.get("resp") is not None and ms.get("resp") != RULED:
            r.errors.append(
                f"<milestone resp='{ms.get('resp')}'>: a milestone is either a "
                f"rule's join against edition/toc.json ({RULED}) or a reading with "
                "no @resp at all — no other rank has anything to assert about a "
                "structural boundary")
        if ms.get("unit") not in {"chapter", "section", "subsection", "subsubsection"}:
            r.errors.append(f"<milestone unit='{ms.get('unit')}'> not in the level map")
        if ctx and ms.get("resp") == RULED and ms.get("n") not in starts_here:
            r.errors.append(
                f"<milestone n='{ms.get('n')}' resp='{RULED}'> does not re-derive: "
                "edition/toc.json does not open it at the folio this page prints. "
                f"Either it belongs on another page, or the <pb n> moved under it, "
                f"or a human placed it — in which case drop the @resp, since {RULED} "
                "claims a join no rule would make")
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


def _rule_seam_shape(root, q, ctx, r: Report) -> None:
    """Forbidden structure at a page seam.

    @part used to be banned outright, on the grounds that continuation was a
    later pass's job. The ban was too wide: a gap's two ends are one fact, and
    the page *after* the gap is the only place both witnesses exist — it holds
    the previous page's tail, its own opening text and its own first-line
    indent. So `harness tei seam` writes @part on both sides, and the TEI is the
    record rather than a materialization of some sidecar.

    What is checked here is therefore the *shape*: a legal I/M/F value, on a
    direct child of <body>, and only on the first or last of them. An element
    in the middle of a page cannot span either gap, so @part there is always
    wrong. @prev/@next stay banned — they carry ids, and the id scheme is
    unsettled; a run-on <list> or <table> is refused by `seam` for that reason
    rather than given a pointer that resolves to nothing.
    """
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


def _rule_folio(body, q, ctx, r: Report) -> None:
    """pb: first element. @n is the folio the model read off the image; absent
    @n asserts the page carries no printed folio (plate, blank, part title).
    That assertion is load-bearing downstream — it tells the seam ledger not
    to advance the printed count — so it is surfaced, not accepted silently.

    Takes `body` rather than `root`: it is the only rule about the *order* of
    `<body>`'s children, so the element it needs is the one it asks for.
    """
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


def _rule_figures(root, q, ctx, r: Report) -> None:
    """`<figure n>` against the numbers this page's own captions print."""
    if ctx is None:
        return
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
            # Geometry is the build's join, through `gt/fig/`. A
            # zone id here is the pass placing a figure, which is not its
            # competence and not checkable from the text it can see.
            r.errors.append(
                f"<figure facs='{fig.get('facs')}'> — figures are anchored "
                "by the printed number; the build resolves the zones")


def _rule_tier1_facs(root, q, ctx, r: Report) -> None:
    """Tier-1 @facs (optional): if a span cites an OCR line, the line must be
    real. Mirrors `figures`' `@facs` check — a dangling citation is strictly
    worse than none, so it errors rather than warns."""
    if ctx is None:
        return
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


def validate(tei_path: Path, ctx: dict | None = None,
             ratified: bool = False, schema: bool = False,
             store: dict | None = None) -> Report:
    """Gate one page's TEI. `ratified` switches which provenance rank is expected.

    `store` is an `entities.load` a caller already holds — 29ms of glob-and-parse
    over 461 files, which a corpus run otherwise pays twice a page, once here and
    once in `build_context`. The comment at the read says why sharing it is not
    the collapse of two witnesses into one that `tier1_terms` guards against.

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

    **The rules, in the order they run.** Each is marked in the body with a
    `── rule: name ──` banner, and `test_validate_rules.py` holds this list and
    those banners to each other, so neither can drift. Until this existed the
    count was unknown: a review put it at 22 by counting comment blocks, several
    of which are notes *inside* a rule, and one of which described two rules that
    had been deleted while the code beneath it checked something else entirely.

        folio               <pb> first, @n against the predicted folio
        seam-shape          @part/@prev/@next legal and only at the edges
        line-and-division   no <lb>, no <div> — ALTO holds lines, pages are div-less
        milestones          heading ids exist in the ToC; #mz ones re-derived
        notes               marker/note pairing, and the printed marker's shape
        figures             <figure n> against the page's own printed numbers
        tier1-facs          a cited OCR line must be one the page supplies
        unexpanded-handle   a surviving index= is a file `tei expand` never saw
        foreign-lang        <foreign> with no @xml:lang asserts nothing
        provenance          THE check: rank, never agreement with an upstream file
        lang-and-glyphs     declared codes, and codepoint hygiene by scope
        provenance-summary  one line for the page's state, so PASS is never bare
        tier1-unglossed     a Tier-1 span a reader can do nothing with
        entities            proper nouns and the @ref over them; loads the store
        relink-missing      the same check from the other side; reuses that store
        figrefs             cross-references marked, and printed ones that are not
        bibl-extent         a citation's extent, never which work it names
        measures            value, and the relations between ways of stating it
        metrics             fifteen counters, assigned wholesale
        schema              conformance, and **last** — see the comment there

    **Three couplings**, which are what make this a function rather than a list:
    `provenance-summary` consumes the `tier1_spans`/`tier1_adopted` counters that
    **`lang-and-glyphs`** sets, `relink-missing` reuses the store `entities`
    loaded, and `metrics` gathers counters from the whole length of the body.
    Anything that extracts these into functions has to answer all three; the
    banners mark where.

    That first coupling is worth reading twice, because the enumeration commit
    got it wrong: the counting sits in `lang-and-glyphs`, whose name does not
    suggest it, while `provenance` — which does — counts nothing. They are
    adjacent, which is exactly how the misreading happened.
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

    # ── rule: folio ──────────────────────────────────────────────────────────
    _rule_folio(body, q, ctx, r)

    # ── rule: seam-shape ─────────────────────────────────────────────────────
    _rule_seam_shape(root, q, ctx, r)
    # **Two rules were removed from this spot and their reasoning stayed**, which
    # left a 29-line comment about `<note>` placement sitting immediately above a
    # check about `<lb>` and `<div>`. Nothing tied them together but adjacency,
    # and the heading ("No whitespace immediately before a <note>") described no
    # code at all. Recorded here because a mechanical read of this function —
    # which is what extracting these rules into functions amounts to — would have
    # carried that comment onto the check below and named it for notes.
    #
    # What went, and why, kept because both are live encoding decisions:
    #
    #   **A note at the foot is where a note goes.** The error here used to say a
    #   `<note>` that is a direct child of `<body>` "has not been anchored" and
    #   should move inline to the character its printed marker follows. That was
    #   right while the generator spliced notes into the prose; it splices none
    #   now. The marker stays where the printer set it and carries a
    #   `<ref type="note">`, the note stays at the foot, and a marker printed
    #   twice is simply two references — which is what `1-147` and `1-226` do,
    #   and what the old shape had to call ambiguous because a spliced note can
    #   only be in one place.
    #
    #   **The whitespace rule went the same way and for the same reason.** It
    #   read "space before <note …> — the marker sets tight against the character
    #   it anchors to", which was a rule about an element standing *in place of*
    #   a marker. Nothing stands in place of one now: the thin space the book
    #   sets ahead of a raised digit (`1-100`: `[albino] ¹)`) is the print, kept
    #   as printed, with no element beside it to set tight against.

    # ── rule: line-and-division ──────────────────────────────────────────────
    _rule_line_and_division(root, q, ctx, r)

    # ── rule: milestones ─────────────────────────────────────────────────────
    _rule_milestones(root, q, ctx, r)

    # ── rule: notes ──────────────────────────────────────────────────────────
    _rule_notes(root, q, ctx, r)

    # ── rule: figures ────────────────────────────────────────────────────────
    _rule_figures(root, q, ctx, r)

    # ── rule: tier1-facs ─────────────────────────────────────────────────────
    _rule_tier1_facs(root, q, ctx, r)

    # ── rule: unexpanded-handle ──────────────────────────────────────────────
    _rule_unexpanded_handle(root, q, ctx, r)

    # ── rule: foreign-lang ───────────────────────────────────────────────────
    _rule_foreign_lang(root, q, ctx, r)

    # ── rule: provenance ─────────────────────────────────────────────────────
    _rule_provenance(root, q, ctx, r, ratified)

    # ── rule: lang-and-glyphs ────────────────────────────────────────────────
    # Sets the two Tier-1 counters `provenance-summary` and `metrics` read.
    tier1_spans, tier1_adopted = _rule_lang_and_glyphs(root, q, ctx, r)

    # ── rule: provenance-summary ─────────────────────────────────────────────
    # Consumes `tier1_spans` / `tier1_adopted`, which **`lang-and-glyphs` sets**,
    # not `provenance` — the two rules sit next to each other and the counting
    # happens in the one whose name does not suggest it. One of the three
    # couplings that make this function more than a sequence.
    #
    _rule_provenance_summary(tier1_spans, tier1_adopted, ratified, r)

    # ── rule: tier1-unglossed ────────────────────────────────────────────────
    tier1_unglossed = _rule_tier1_unglossed(root, q, ctx, r)

    # ── rule: entities ───────────────────────────────────────────────────────
    store, names, untyped, refs, ruled = _rule_entities(root, q, ctx, r, store)

    # ── rule: relink-missing ─────────────────────────────────────────────────
    # Takes the `store` the `entities` rule loaded: the second coupling.
    _rule_relink_missing(tei_path, store, r)

    # ── rule: figrefs ────────────────────────────────────────────────────────
    # Its own rule, and the enumeration missed that: it was already a helper
    # before this pass, so it had no banner and fell inside `relink-missing`'s by
    # position. It checks a different thing (cross-references marked, and printed
    # ones carrying no mark) and feeds two of its own counters.
    figrefs_marked, figrefs_missing = _figrefs(root, r, ctx)

    # ── rule: bibl-extent ────────────────────────────────────────────────────
    bibls = _rule_bibl_extent(root, q, ctx, r)

    # ── rule: measures ───────────────────────────────────────────────────────
    measures, groups = _rule_measures(root, q, ctx, r)

    # ── rule: metrics ────────────────────────────────────────────────────────
    # **The third coupling, and the one that constrains the extraction most.**
    # Fifteen keys gathered from locals set the length of this function, and
    # *assigned* wholesale rather than updated — so it must run after every rule
    # that produces a counter, and each extracted rule has to hand its counters
    # back rather than keep them.
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
        # Tier-1 spans with nowhere for a reader to go. A count beside the
        # warnings, so the corpus-wide trend is visible whatever any one page's
        # warnings do — and so a page whose forms the book genuinely leaves bare
        # reads as a number rather than as a page full of defects.
        "tier1_unglossed": tier1_unglossed,
        # Entity references, and how many of them a rule wrote rather than a
        # reader. The second is not a quality measure and must not be read as one:
        # it counts links that still *derive*, not links the sentence supports —
        # only a collator's deletion says that, and an unreviewed page carries its
        # rule-applied links unexamined. It is here because a page where the two
        # numbers are equal has had no entity judged by anybody.
        "entity_refs": refs,
        "ruled_links": ruled,
        # Cross-references marked, and printed ones carrying no mark. The second
        # is not a defect count: a collator who deleted a mark the sentence does
        # not support is doing the job this element was put in the page for, and
        # a page generated before the rule changed shows here too.
        "figrefs": figrefs_marked,
        "figrefs_unmarked": figrefs_missing,
        "bibls": bibls,
        "measures": measures,
        "measure_groups": groups,
        "worklist": len(r.worklist),
    }
    # ── rule: schema ─────────────────────────────────────────────────────────
    # **Must stay last**, for the reason below. The only whole-rule gate in the
    # function: `ratified` gates branches inside `provenance` and
    # `provenance-summary`, never a rule entire.
    if schema:
        from .schema import check
        # Last, and appended rather than interleaved: a conformance failure is a
        # different kind of statement from a project-rule failure, and a reader
        # meeting "not conformant TEI" among the edition's own rules would take it
        # for one of them.
        r.errors += check(tree, Path(ctx["root"]) if ctx else Path("."))
    return r
