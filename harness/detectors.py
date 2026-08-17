"""Mechanical detectors (charter, 'Transcription Detection').

Union: inventory-glyph match ∪ word-medial [AEIL] ∪ dot-above-g ∪
apostrophe-adjacency ∪ English-lexicon miss, plus quote/bracket balance.
All heuristic triage — the numerator is a floor by construction; unmarked
ASCII inventory members (c, s, j, x) are invisible here and always will be.

One member of that union is not like the others. `dot_above_g` is a **trap**
detector: the inventory glyph is g+U+0323 (dot *below*), and g+U+0307 is its
lookalike, so a hit reports a keying error rather than a non-English token. It
therefore does not earn the lexicon suppression the others do — see
NON_ENGLISH_HITS.

`detect_all` returns those as **two** lists, `tokens` and `balance`, because
they are two record shapes — `{type, index, token}` and
`{type, paragraph, detail}`. Interleaved they would be a ragged table, which
the tabular encoder cannot collapse; see emit.py.

`index` is the ALTO line identity, not a position in the draft — see
`detect_all` for why the position it replaced was worse than no number.

The floor is a floor, but it is not an excuse for noise above it. A detector
that fires on ordinary English is worse than one that stays quiet, because it
buries the real hits and — where a hit suppresses a later check — masks them
outright. Hence the word-boundary guard on MEDIAL_CAPS, the edge-only
punctuation stripping in `lexicon_miss`, and the whitelist.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from lxml import etree

# Marked inventory glyphs (keying spec §2), NFD bases + combiners + atomics.
INVENTORY_CHARS = set("ᴀᴇɪʟᵋᵉɵˊ˙") | {"\u0323", "\u030C", "\u0303", "\u0302",
                                        "\u0308", "\u0306", "\u0304"}
# U+0121 is deliberately absent, and the absence is the fix rather than an oversight.
# It decomposes canonically to g+U+0307, and `detect_all` NFD-normalizes every line
# *before* consulting this set, so a single-codepoint member could never match; it sat
# here reporting coverage it did not have. DOT_ABOVE_G tests the sequence instead,
# which is where that trap belongs anyway, since U+0121 is not an apostrophe
# lookalike and flagging it here would duplicate the hit under a misleading name.
LOOKALIKES = set("\u00B4\u2019\u02BC\u02BB\u00B7\u02E2\u2091\u04E9\u2010")

# Mark\u2013base licensing (keying spec \u00A72.6), as a **closed allow-list per mark**: the
# mark may sit on these bases and nowhere else. Closed rather than a deny-list because
# the spec says so outright — the breve is productive as a length mark, so further
# bases may be licensed, but "only on attestation the editor has stamped, never on
# symmetry". A deny-list would silently admit every base nobody had thought of.
#
# Unlike everything else in this module this is **not triage**. A detector answers
# "worth a look"; this answers "impossible", so it is reported as an error and not a
# flag, and it is the one check here that can block a write. The distinction matters
# because an unlicensed mark has no reading to adjudicate: `\u026A` + breve is not a hard
# case between two glyphs, it is a sequence the notation does not contain.
#
# Only marks the spec actually rules on appear. The others (U+0302, U+0303, U+030C,
# U+0323, U+0308, U+0304) have no licensing table yet, and inventing one by analogy
# from the corpus is precisely what \u00A72.6's last paragraph forbids.
#
# `j` is why this exists as code. `1-073` prints \u01F0 three times in `Ne\u01F0-`, `\u00D1e\u02CArg\u0323e\u01F0-`
# and `Qu\u02CAule\u01F0-`; a reading pass took the mark for a breve, and review corrected two
# of the three and missed the third — one page, one form, three occurrences, and the
# inconsistency survived a human pass because nothing compared them. Breve-on-j is now
# unrepresentable rather than merely wrong.
#
# Cyrillic \u0438 is licensed for the breve, and it is not a \u00A72.6 widening. \u0439 is a letter
# of the Russian alphabet whose *canonical* decomposition is \u0438 + U+0306, so NFD turns
# every Russian word carrying one into a base+mark sequence that asserts nothing an
# editor read off a letterform \u2014 the licensing question \u00A72.6 asks does not arise.
# (\u0451 = \u0435 + U+0308 is the same case and needs no entry, since U+0308 has no table.)
#
# It is an entry in the allow-list rather than a script test in `unlicensed_marks`,
# and that was a deliberate call against the tidier-looking alternative. "Consult the
# table only for Latin bases" states the scope more honestly but decides it by
# inference, and the corner cases are unbounded \u2014 marks after digits, punctuation and
# spacing bases, Greek, mixed-script transliteration \u2014 each one a silent skip rather
# than a loud error. An explicit set has exactly the members it has. The comment can
# carry the nuance; the code should stay dumb.
#
# `data/authorities.json` \u2014 73 bibliography entries, most printed twice, once in
# pre-1918 Russian \u2014 is what exposed this: 72 errors, no readings. Collation will hit
# it far harder once Russian body text starts arriving.
MARK_LICENSE = {
    "\u0306": set("ui") | set("\u0438\u0418"),  # breve: \u016D (\u00A72.2), \u012D (\u00A72.6); \u0439/\u0419 Cyrillic short i
}


# The licensed marks as one character class, so *finding* them is a C-level scan
# rather than a dict lookup per character.
#
# This runs over every character of every scoped file on a corpus `normalize`, and
# the table has **one** entry — so it was making 5.7 M `dict.get` calls to locate
# occurrences of a single codepoint, and accounted for 57% of the gate's runtime.
# Derived from the table rather than written out beside it, so adding a mark cannot
# leave the two disagreeing.
_LICENSED_MARKS = re.compile(f"[{''.join(re.escape(c) for c in MARK_LICENSE)}]")


def unlicensed_marks(text: str) -> list[dict]:
    """Every combining mark sitting on a base its licence does not cover.

    Assumes NFD, so a base is simply the character before the mark. A mark in
    initial position has no base at all and is reported the same way — it cannot be
    licensed by anything, and it is a real corruption rather than a keying choice.
    """
    text = unicodedata.normalize("NFD", text)
    out = []
    for m in _LICENSED_MARKS.finditer(text):
        i = m.start()
        ch = m.group()
        allowed = MARK_LICENSE[ch]
        base = text[i - 1] if i else ""
        if base in allowed:
            continue
        out.append({
            "mark": f"U+{ord(ch):04X} {unicodedata.name(ch, 'UNNAMED')}",
            "base": (f"{base!r} (U+{ord(base):04X})" if base else "(nothing — "
                     "mark in initial position)"),
            "licensed_on": " ".join(sorted(allowed)),
            "context": text[max(0, i - 12):i + 8],
        })
    return out


# keying_spec.md §2.1 + §4 script 2: U+0027 is licensed only post-{b p d t g k}
# (spirant) or strictly V_V (pause); any other position is "unconditionally an
# error". §4's one exception is V_V itself, where *both* readings are licensed
# and only printed shape decides — not this function's call, so that position
# is reported separately and never as an error.
#
# Built because a corpus-wide check turned up not one confirmed legitimate
# apostrophe anywhere in restored ground truth — every literal U+0027 found
# was an English possessive on a gloss word — while `3-004` alone put the
# same mistyped-for-stress error on 30+ lines. §5.5 already says "if the only
# raised mark in the word is currently keyed as `'`, that apostrophe is far
# more likely `ˊ` misread"; this is that rule made mechanical rather than
# re-derived by eye on every page.
_SPIRANT_BASES = set("bpdtgk")
# Bare base letters only — NFD strips the diacritic off ä/ë/ê/ŭ down to a
# plain vowel before this runs, and ɵ/ᴀ/ᴇ/ɪ are already atomic. ʟ is a
# lateral consonant despite the small-cap-vowel-series look-alike shape and
# is deliberately not here.
_VOWELS = set("aeiouɵᴀᴇɪ")


def apostrophe_licensing(text: str) -> list[dict]:
    """Every U+0027 in `text`, checked against its licensed environment.

    NFD-normalized first, and marks are skipped when looking for the base
    letter immediately before the apostrophe — 'ê'' is e + circumflex +
    apostrophe, and the circumflex is not what licenses or fails to license
    the mark that follows it.

    Two kinds, deliberately not folded into one: 'unlicensed' is the
    mechanical case §4 calls unconditional — neither environment licenses it,
    so it is reported as wrong, not merely worth a look. 'ambiguous' is the
    V_V position, where the spec itself says shape alone decides; flagged for
    a human to look at the raster, never assumed wrong.
    """
    nfd = unicodedata.normalize("NFD", text)
    out = []
    for i, ch in enumerate(nfd):
        if ch != "'":
            continue
        j = i - 1
        while j >= 0 and unicodedata.category(nfd[j]) == "Mn":
            j -= 1
        prev = nfd[j] if j >= 0 else ""
        nxt = nfd[i + 1] if i + 1 < len(nfd) else ""
        context = nfd[max(0, i - 10):i + 10]
        if prev.lower() in _SPIRANT_BASES:
            continue
        if prev.lower() in _VOWELS and nxt.lower() in _VOWELS:
            out.append({"kind": "ambiguous", "context": context})
            continue
        out.append({"kind": "unlicensed", "context": context})
    return out
# There is deliberately no SMART_QUOTES detector. Curly quotes are what the book
# prints, and under the Tier-1-scoped ASCII policy (keying spec section 1) English
# prose reproduces them, so a flag here fires on correct text: the noise this
# module's docstring warns about. The rule that survives is narrow, that inside a
# Tier-1 span U+2019 traps U+0027, and it can only be enforced where the language is
# known. The draft plaintext carries no markup, so it lives in
# validate.LOOKALIKE_GREPS against the TEI instead.
# Word-*medial*: an ASCII capital A/E/I/L inside a token, where a small-cap
# ᴀ/ᴇ/ɪ/ʟ was meant (keying spec §5.7). The first character of a token is
# excluded, or every capitalised English word beginning A/E/I/L ("English",
# "Iron", "Later") fires — noise, and, because a hit used to suppress the
# lexicon check, a mask over real signal.
#
# **A Tier-1-exclusive character counts as word-internal and as a lowercase
# neighbour**, and that is what the two branches below are for. `2-034`'s `Lo`,
# in a stressed hyphenated compound and corrected to small-cap ʟ by review, sits
# immediately after a stress mark: not a letter, so a plain `(?<=[a-z])` missed
# it. The stress mark is not a word boundary — it is part of the word, and it
# occurs nowhere but inside a Tier-1 form, so it stands in for a lowercase letter
# exactly.
#
# **This replaces a rule that had widened to `(?<!^)(?<!\s)[AEIL]`**, which
# caught the `ˊLo` case by dropping the neighbour requirement altogether and so
# fired on **every all-caps English word in the corpus** — `BOGORAS, THE
# CHUKCHEE.` is the running title of ~694 pages, and every one of them reported
# two hits. That is precisely the failure this module's own docstring names:
# a detector firing on ordinary English buries the real hits. An all-caps token
# cannot fire here again, because neither branch admits an uppercase ASCII
# neighbour on the deciding side — and no Tier-1 form in the restored corpus is
# fully uppercase, so nothing is given up.
_T1 = "".join(sorted(INVENTORY_CHARS))
MEDIAL_CAPS = re.compile(
    rf"(?<=[a-z{_T1}])[AEIL]|(?<=[A-Za-z{_T1}])[AEIL](?=[a-z{_T1}])")
DOT_ABOVE_G = re.compile(r"\u0121|g\u0307")
TOKEN = re.compile(r"[^\s]+")
# keying_spec.md section 5.1: base letter + combining mark pairs known,
# corpus-wide (`harness lexicon marks`), to have a strong bare-vs-marked
# skew inside a specific suffix family -- a bare reading there is
# presumptively suspect before the raster is even consulted. A table rather
# than one regex per class, so a newly measured skew is a data row to add,
# not new code.
#
# Each entry: (mark codepoint, base letter, suffix continuations that base
# must be immediately followed by). `g` + U+0323 (dot below) before
# `-\u026a`/`-\u026an`/`-\u026at` is the only class measured strongly enough to encode so
# far -- dropped dot-below under g is the single most repeated miss in this
# project's keying history, and specifically recurs in this noun-forming
# suffix family, not merely a kinship-vocabulary pattern (`va'\u026arg\u0323\u026an`,
# "spirit", takes the same one). It covers `-g\u026a`/`-g\u026an`/`-g\u026at`, `-rg\u026an`,
# `-\u026arg\u026an`, `-mg\u026an`, ... uniformly, since the check is on `g` itself and
# what precedes it is not consulted. `3-005` is the page that showed a bare
# `g` in this exact position accepted at face value more than once in one
# session, after which this table replaced a single hardcoded regex.
SUFFIX_MARK_DROPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("\u0323", "g", ("\u026a", "\u026an", "\u026at")),
)
# Punctuation stripped from a token's *edges* before lexicon lookup. Internal
# hyphens and apostrophes are load-bearing in English too ("sea-mammals",
# "don't"), so they survive to the split below instead of being deleted.
#
# **U+0027 is deliberately absent, and the absence is the rule rather than an
# oversight.** In this corpus the straight apostrophe is not punctuation at all:
# it is the spirant and pause mark, an `INVENTORY_CHARS` member and a phonetic
# segment in its own right (keying_spec.md §1, §2.1). Stripping it off a
# token's edge deletes a Tier-1 character from the form these reports publish,
# silently and in every arm at once. Nothing is lost on the English side by
# keeping it: `lexicon_miss` splits its core on `'` regardless, so `dogs'` and
# `'tis` reduce to the components they always did.
#
# The curly quotes are the other half of the same cut. The print wraps glosses,
# quoted speech and -- on `2-045`, `3-119`, `3-135` -- native forms in them, so
# a whitespace tokenizer hands the quote back stuck to the token. A form inside
# a gloss quote is not a different word, so they are stripped here, in the one
# shared cut, rather than in a second strip downstream -- which is where they
# used to sit, applied after `suggest_native_forms` had already published the
# quoted form.
#
# **The superscripts are here because a footnote marker is typography, not part of
# the word.** `str.strip` takes a character *set* and stops at the first member it
# does not know, so without them `Keliˊlhu.¹` kept both — the digit blocked the
# period behind it — and entered every native frequency table as a form distinct
# from the `Keliˊlhu` that seven other lines spell. 14 such tokens across the
# store, each splitting a real form's count.
EDGE_PUNCT = "\"()[]{}.,;:!?—\u2013-*\u2020\u2021\u00A7\u00B6“”‘’¹²³⁴⁵⁶⁷⁸⁹"

# A hyphen that is the **last character of a printed line** is the compositor's
# word break, not a hyphen in the word. The ALTO stores one line per printed
# line, so `Chuk-` / `chee` reaches the tokenizer as two tokens and both are
# reported as words no dictionary knows. A letter must precede it, so a rule, a
# dash used as punctuation and a numeric range are not joined.
#
# A word-*internal* hyphen is never touched. It is load-bearing in Americanist
# notation, and the collation licence to join a broken word is restricted to
# European languages -- the hyphenated compounds of `3-004`/`3-005` and
# `2-045`'s quoted spirit-compound are correct as they stand.
#
# The combining run between the letter and the hyphen is not decoration. The
# corpus is NFD, so a native word ending in a marked letter ends in base + mark
# + hyphen, and Python's `\w` does not match a combining mark — without it
# `reˊkkeñ-` / `spirits` stays broken, i.e. the rule would work on English and
# quietly fail on exactly the forms with no dictionary to catch them.
_BREAK_HYPHEN = re.compile(r"[^\W\d_][̀-ͯ]*-$")


def join_broken_words(recs: list[dict]) -> list[str]:
    """Rejoin words the compositor broke across a line end. Same length in, out.

    Takes `lines.page_lines` records and returns their texts, so the caller's
    records and this output stay positional to each other and `index` never
    moves. `text` and `zone` are read, and nothing else.

    `recs` must already be in **reading order**, the printed sequence, which is
    what `page_lines` returns. ALTO document order is *not* it (harness/README.md, "line
    output is in reading order, but `index` is an identity"), and joining along
    document order would splice the foot of one column onto the head of another.

    **Reading order is the whole answer, and the continuation is simply the next
    non-empty line.** A geometric guard sat here for a while — first "a candidate
    more than half the stem's width away in `hpos` is a different column", then a
    vertical restatement of it — and both were mistakes of the same kind, so the
    reasoning is worth keeping rather than the code. `gt/ocr/` is adjudicated
    ground truth in adjudicated order: if the line after a broken word is not its
    continuation, the *segmentation* is wrong, and no arithmetic over boxes here
    can do anything but guess at which of two wrong answers to give. Measured
    over both ALTO stores, the horizontal rule moved 22 joins away from the next
    line: **2 were the case it was written for and 20 were corruptions** — a
    figure runaround read as a column (`1-314` printed `The Chuk-their`, the
    sentence losing `their` outright), a narrow measure beside a figure
    (`1-116`, `1-240`, `2-088`), a caption line 147 px wide whose tolerance came
    out at 73 and refused everything (`1-114`), and, having no vertical bound,
    `1-222` joining `I col-` at vpos 1073 to a word at vpos 3039.

    The 2 it got right are both `1-101`, whose gloss list is mis-segmented: four
    of its lines merge the two columns into one full-measure line mid-sentence
    and the rest do not, so that page does not read linearly however this
    function behaves. **A page whose lines are out of order is fixed in
    `gt/zones/`, not here.**

    The join is positional and says nothing about language. A line ending in
    letter + hyphen takes the first whitespace-delimited token of the next
    non-empty line; that line loses it. Nothing else moves, so the record a token
    sits on is still the record the *word* started on, and every other token
    keeps its line — which is what lets `native_corpus_lines` go on citing
    `index`.

    The join is positional and says nothing about language. A line ending in
    letter + hyphen takes the first whitespace-delimited token of the next
    non-empty line; that line loses it. Nothing else moves, so the record a token
    sits on is still the record the *word* started on, and every other token
    keeps its line — which is what lets `native_corpus_lines` go on citing
    `index`.

    Deliberately no language test, and it is worth stating why rather than
    leaving it to look like an omission. Whether the hyphen is the compositor's
    is a fact about the line break — the measure ran out — and that is equally
    true of an English word and a Tier-1 one. A rule that joined only ASCII would
    leave a native form cut in half in exactly the store that has no dictionary
    to notice.

    **The hyphen is kept, not dropped, and that is the one judgement in here.**
    Dropping it is what a modern de-hyphenator does and it is what this was first
    written to do; measured over `gt/ocr/` it manufactured nine words the book
    does not contain — `reindeerowner`, `treetrunk`, `beaconlamp`,
    `Shootingstars` — because a *real* compound hyphen falling at a line end is
    indistinguishable from a break, and nothing in the ALTO can separate the two.
    Deleting it is also not neutral where it matters most: U+002D is the licensed
    Tier-1 hyphen (keying_spec.md §1), so dropping one inside a native compound
    edits an inventory character on a guess. Keeping it leaves the printed
    ambiguity intact and visible; the English arm resolves it with the dictionary
    it already owns, by testing the concatenation too (`lexicon_miss`), which is a
    reading of the token rather than an edit to it.

    **The continuation must be in the same zone, and that is not the geometric
    guard this function threw out.** That one asked whether a box was too far
    away, which is arithmetic over coordinates and can only guess; this reads the
    label a human keyed. Where the two lines sit in different zones the store is
    not silent about it — it has already said one is prose and the other is the
    apparatus — and a body word's continuation is never a footnote.

    Measured over `gt/ocr/`: **523 joins, of which 4 cross a zone, and all four
    are `MainZone-P` into `MarginTextZone-Notes`.** There is no other cross-zone
    join in the adjudicated corpus, so the rule refuses four things and nothing
    else. All four were corruptions of two texts at once. `1-075` printed
    `…mouth of the Kolyma west-` as its last body line and the join glued the
    following footnote's marker onto it — `Kolyma west-¹` — while the note it
    stole from opened `Bogoras, Chukchee Materials, p. 345.` with no marker left
    at its head. `1-091`, `1-203` and `1-243` are the same, and those four pages
    are exactly the four the generator reported as "no marker at the head of this
    note".

    The stem is left broken, which is the honest outcome: its continuation is the
    *next page's* first body line, and what crosses a page boundary is the seam's
    business and not this function's.

    Iterates from the last line back, so a word broken twice (a stem, a
    continuation itself ending in a hyphen) resolves in one pass.
    """
    out = [(r.get("text") or "") for r in recs]
    for i in range(len(out) - 2, -1, -1):
        stem = out[i].rstrip()
        if not _BREAK_HYPHEN.search(stem):
            continue
        nxt = next((k for k in range(i + 1, len(out)) if out[k].strip()), None)
        if nxt is None:
            continue
        # **A word does not continue into another zone.** Absence of a label on
        # either side is not a barrier — a caller with no zones must still join.
        if recs[i].get("zone") != recs[nxt].get("zone"):
            continue
        parts = out[nxt].split(None, 1)
        out[i] = stem + parts[0]
        out[nxt] = parts[1] if len(parts) > 1 else ""
    return out


# Detectors that already establish a token is not English. For these, a
# lexicon miss is a tautology and adds only bulk. Typographic flags
# (word_medial_caps) say nothing about the language and must not suppress it.
#
# `dot_above_g` is deliberately NOT here, though it was. It is a *trap* detector:
# the inventory glyph is g+U+0323 (dot below, an INVENTORY_CHARS member), and
# g+U+0307 is the lookalike. So a hit means the keying is wrong, not that the token
# is foreign — the opposite of what earns suppression. Leaving it in let a keying
# error silence a lexicon miss, which is exactly the mask the docstring warns of.
NON_ENGLISH_HITS = {"inventory_glyph", "apostrophe_adjacency"}

_WORDS: dict[tuple, set[str]] = {}


def _base_lexicon(root: Path = Path(".")) -> set[str]:
    """System dictionary plus `data/lexicon_extra.txt`, without the entity store.

    Named apart from `_lexicon` because `suggest_lexicon` needs both: the
    difference between the two is exactly what the entity store suppressed, and
    a suppression nobody can see is the thing this whole arrangement is supposed
    not to have.
    """
    words: set[str] = set()
    for cand in (Path("/usr/share/dict/american-english"),
                 Path("/usr/share/dict/words"),
                 root / "data" / "english_lexicon.txt"):
        if cand.exists():
            words = {w.strip().lower()
                     for w in cand.read_text(encoding="utf-8").splitlines()}
            break
    return words | load_extra_lexicon(root)


def entity_forms(root: Path = Path(".")) -> set[str]:
    """Every component of every entity canonical and alias form, lowercased.

    Split the way `lexicon_miss` splits, on whitespace *and* on the internal
    hyphen and apostrophe, because that is the shape the question is asked in:
    `Sredne-Kolymsk` reaches `_unknown_word` as two components, and an entry
    contributing only the joined string would leave both of them missing.

    **Status is not consulted.** `auto_forms` demands `ratified` because a
    machine link into committed TEI is at stake; this writes nothing and only
    removes a triage flag from a report, so the higher bar would be the reason
    cargo-culted without the stake. What makes it safe is the other half —
    re-derived from the store on every load, so deleting an entry starts the
    token missing again on the same run.
    """
    from .entities import load

    out: set[str] = set()
    for rec in load(root).values():
        for form in [rec["canonical"], *(t["form"] for t in rec["aliases"])]:
            for part in re.split(r"[\s\-'’]+", form):
                if part:
                    out.add(part.lower())
    return out


def _entities_stamp(root: Path) -> tuple:
    """Cheap identity for the entity store, for `_lexicon`'s cache key.

    `data/lexicon_extra.txt` only ever changed between processes, so a cache
    keyed on the root alone was safe. `entities/` changes *inside* one:
    `edition_ui._guarded` writes it on a browser click. Stat rather than
    contents because this is recomputed once per page of a corpus sweep and a
    content hash over the store would be ~100 reads each time; the write path
    that matters here goes through `_guarded`, which rewrites whole files.
    """
    d = root / "entities"
    if not d.is_dir():
        return ()
    return tuple(sorted(
        (str(p.relative_to(d)), st.st_mtime_ns, st.st_size)
        for p in d.glob("*/*.md") if (st := p.stat())))


def _lexicon(root: Path = Path(".")) -> set[str]:
    """System dictionary, the project's additions, and the entity store's names.

    `data/lexicon_extra.txt` holds what a general English dictionary cannot be
    expected to carry — Latin binomials, Bogoras's recurring coinages, the
    abbreviations his running heads repeat. It suppresses `lexicon_miss` and
    nothing else: the inventory, apostrophe, dot-above-g and smart-quote
    detectors never consult it. A whitelist able to blind a Tier-1 detector
    would be a hole in the firewall, so it is denied the opportunity
    structurally rather than by discipline.

    **The entity store is the second source, and the proper nouns moved there.**
    They used to be listed in both places — 20 of the whitelist's terms were
    already an entity's canonical or alias — which is one fact in two
    hand-maintained files, each able to go stale against the other. Now a name
    is filed once, as an entry that says which page first attested it, and this
    reads it back out.

    Stronger than either, and worth stating because it is what actually holds
    the line: `lexicon_miss` only ever tests ASCII components of length > 3, so
    a Tier-1 form in *either* source is inert here — it could not have been a
    lexicon miss in the first place. That is what lets an entity carry a native
    alias as an alias without the alias table becoming a way to blind the one
    detector that can catch an unmarked romanized form.
    """
    key = (str(root.resolve()), _entities_stamp(root))
    if key not in _WORDS:
        _WORDS[key] = _base_lexicon(root) | entity_forms(root)
    return _WORDS[key]


def load_extra_lexicon(root: Path = Path(".")) -> set[str]:
    """`data/lexicon_extra.txt` — one term per line, `#` comments, blanks ok."""
    p = root / "data" / "lexicon_extra.txt"
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        term = line.split("#", 1)[0].strip().lower()
        if term:
            out.add(term)
    return out


def lexicon_miss(tok: str, lex: set[str]) -> bool:
    """Is `tok` a word no English lexicon knows?

    Edge punctuation is stripped, then the core is split on internal hyphens
    and apostrophes and each component checked separately — otherwise
    "sea-mammals," normalises to "seamammals" and misses on a compound both
    halves of which are ordinary English. A token counts as a miss if any
    component does.

    **A hyphenated token is then given its second reading**, and only a token
    that misses under both counts. `join_broken_words` rejoins a word the
    compositor broke across a line end and keeps the hyphen, because the hyphen
    it broke on and a hyphen the word owns are the same character on the page; so
    `Chuk-chee` arrives here with two components no dictionary knows and one
    concatenation it does. Testing both is how that ambiguity is read rather than
    decided — nothing edits the token, and a compound the book really owns
    (`sea-mammals`) was already answered by the component pass. Only a token that
    fails both readings is reported.
    """
    core = tok.strip(EDGE_PUNCT)
    if not core:
        return False
    parts = [p for p in re.split(r"[-'\u2019]", core) if p]
    if not parts:
        return False
    if not any(_unknown_word(p, lex) for p in parts):
        return False
    return not (len(parts) > 1 and "".join(parts).lower() in lex)


def _unknown_word(p: str, lex: set[str]) -> bool:
    """One component against the lexicon. Short, non-ASCII and non-alphabetic
    components are never a miss — this detector tests English and nothing else,
    which is also why a Tier-1 form in `data/lexicon_extra.txt` is inert."""
    return len(p) > 3 and p.isascii() and p.isalpha() and p.lower() not in lex


# U+2019 in the position an English possessive puts it: before a final `s`, or
# before a hyphen inside a compound (`Raven’s-Beak`). A trailing one never
# reaches here — `EDGE_PUNCT` cuts it at the tokenizer — so `farmers’` is
# already outside this question.
_GENITIVE = re.compile("’s?(?=$|[-‐])")


def english_genitive(tok: str, lex: set[str]) -> bool:
    """Is every U+2019 in this token an English possessive on a word English knows?

    `apostrophe_adjacency` fires on U+2019 because the corpus keys the stress
    mark as U+02CA and a curly apostrophe in its place is a real and invisible
    defect. But the book also sets ordinary English possessives with a curly
    apostrophe, correctly, and after ratified Tier-1 forms stopped being flagged
    those became **every surviving hit on the ground-truth corpus** — 31 of 31,
    `wife’s` through `Krause’s`. A detector whose whole output is correct English
    buries the hits it exists for.

    **Position alone will not do it**, and the counter-example is the point:
    `keˊlet` mis-keyed as `ke’let` puts a curly apostrophe between two lowercase
    ASCII letters, which is exactly where a possessive sits. So the shape is
    necessary and not sufficient, and the stem must be **positively known** —
    `p.lower() in lex`, not `not _unknown_word(p)`, which passes anything under
    four characters and would have cleared `ke’let` and `kun’s` alike.

    Fails closed: no lexicon, no suppression. What it cannot clear is a
    possessive on a proper noun no dictionary carries (`Orion’s`), which stays
    flagged and is the honest answer — the alternative is guessing that a
    capitalised unknown before `’s` is English, and the corpus is full of
    capitalised unknowns that are not.
    """
    if not lex or "’" not in tok:
        return False
    if len(_GENITIVE.findall(tok)) != tok.count("’"):
        return False
    parts = [p for p in tok.split("’", 1)[0].split("-") if p]
    return bool(parts) and all(
        p.isascii() and p.isalpha() and p.lower() in lex for p in parts)


def apostrophe_flags(text: str) -> list[dict]:
    """Every straight U+0027 in `text`, always flagged — nothing invisible.

    An earlier version of this function only fired on a token that already
    carried some other `INVENTORY_CHARS` member, on the theory that an
    apostrophe alone can't tell Tier-1 from an English contraction
    ("don't"). That reasoning smuggled in a false premise: keying_spec.md §1
    says English prose reproduces the book's curly quotes *including the
    apostrophe* ("cliff's end," "don't"), exactly the rule already enforced
    for the double-quote pair (normalize.py's `_quote_hits`,
    `STRAIGHT_QUOTE_TRAP`) — so a straight apostrophe in an English token is
    not an ambiguous case being conservatively skipped, it is a confirmed
    defect being silently missed. A corpus-wide check turned up zero
    legitimate apostrophes anywhere in restored ground truth, Tier-1 *or*
    English — every one found was either a mistyped Tier-1 stress mark or a
    straight apostrophe on an English possessive that should have been
    curly (`land's end`, `cliff's end` ×2, `man's`/`woman's name` — none of
    which the scoped version could see, since none of those tokens carried
    any other mark).

    Two kinds now: 'english' — no other `INVENTORY_CHARS` member in the
    token, so nothing marks it Tier-1, and the print-reproduction rule for
    English applies; flagged regardless of position, since there is no
    licensed-spirant exception when the token isn't established Tier-1 in
    the first place. Otherwise, `apostrophe_licensing`'s own kinds
    ('unlicensed' / 'ambiguous') apply, exactly as before, since a token
    that *does* carry another inventory glyph is a genuine positional
    question under §2.1, not a print-convention one.
    """
    out = []
    for m in TOKEN.finditer(text):
        tok = m.group()
        if "'" not in tok:
            continue
        if not any(c in INVENTORY_CHARS for c in tok):
            out.append({"token": tok, "kind": "english"})
            continue
        for hit in apostrophe_licensing(tok):
            out.append({"token": tok, **hit})
    return out


def _suffix_mark_drop(core: str) -> str | None:
    """`core` (already NFD, edge-punctuation stripped) against every
    `SUFFIX_MARK_DROPS` entry. Returns the expected marked form on a hit,
    `None` otherwise.

    Checks each token ending in one of a table entry's suffix continuations,
    immediately preceded by the bare base letter (not base+mark) — under
    NFD, a genuinely marked instance has the combining mark sitting between
    base and continuation, so the character immediately before the
    continuation is the mark, not the base, and this naturally skips it
    without a separate "already marked" branch. Longest continuation wins
    per entry, so `-ɪn` is not double-reported as also matching the bare
    `-ɪ` shape.
    """
    for mark, base, continuations in SUFFIX_MARK_DROPS:
        for cont in sorted(continuations, key=len, reverse=True):
            if not core.endswith(cont):
                continue
            i = len(core) - len(cont)
            if i >= 1 and core[i - 1] == base:
                return f"{base}{mark}{cont}"
            break
    return None


def suffix_mark_flags(text: str) -> list[dict]:
    """Every token matching a `SUFFIX_MARK_DROPS` entry, unmarked.

    NFD-normalized first, so the mark and its base are adjacent codepoints
    rather than a precomposed form. Report-only, like every detector in this
    module — a hit names a shape keying_spec.md §5.1 calls dot-prone
    corpus-wide, not a certain error; shape still decides, on the raster,
    not this table.
    """
    nfd = unicodedata.normalize("NFD", text)
    out = []
    for m in TOKEN.finditer(nfd):
        tok = m.group()
        expected = _suffix_mark_drop(tok.strip(EDGE_PUNCT))
        if expected:
            out.append({"token": tok, "expected": expected})
    return out


# Footnote markers. The book sets them as raised digits, and keying_spec's
# working rule (`rebuild-groundtruth`'s SKILL.md, from `2-244` line 1) is the
# actual Unicode superscript, never the plain ASCII digit. A plain digit is the
# nastiest shape of error this project has: it is the *right number*, so it
# reads as correct, and no lookalike grep, lexicon check or mark licence
# touches it. Only counting finds it.
SUPERSCRIPT_DIGITS = {"¹": 1, "²": 2, "³": 3,
                      "⁴": 4, "⁵": 5, "⁶": 6,
                      "⁷": 7, "⁸": 8, "⁹": 9}
# A line opening with a bare digit then a space: the shape of a footnote whose
# marker was keyed ASCII. Measured over the 20 restored pages: 9 lines match,
# 8 are exactly this defect and 1 is a wrapped body line that happens to begin
# with a numeral (`1-053`, "2 houses)."). Numbered lists do NOT collide — the
# book sets those as digit + PERIOD (27 in the same corpus, e.g. "2. Cacanlorgin"),
# which this deliberately does not match. Report-only, like everything here.
ASCII_FOOTNOTE_OPENER = re.compile(r"^([1-9])\s+(?=\S)")
# A figure citation's sub-part locant: `(Fig. 17, f¹)`, a raised numeral picking
# out one labelled detail of a plate. Typographically identical to a footnote
# marker and not one — it anchors nothing, so it is printed once and can only
# ever read as an unpaired marker.
#
# The shape is taken from `gt/ocr/`, which attests four and no counter-example:
# `Fig. 17, f¹)`, `Fig. 155, a¹)`, `Fig. 155, b, d¹)`, `Fig. 155, c¹)`. A **lone
# letter** carries the superscript and a close-paren follows, and both conjuncts
# are load-bearing: the same store holds `Ciˊṛluk⁶),` (a real marker, on a
# multi-letter word) and `Nelson ¹)`, `Kiˊhi ¹)`, `[albino] ¹)` (real markers
# before a paren, spaced off the word). Either half alone would swallow one of
# those.
#
# Deliberately **not** keyed on `Fig.` appearing in the line: `155, a¹),` is a
# citation wrapped across a line break, and the reader keying that line can see
# the locant but not the word that governs it.
FIGURE_LOCANT = re.compile(r"(?<![^\s(])[a-z]([¹²³⁴⁵⁶⁷⁸⁹])\)")


def footnote_report(texts: list[str]) -> dict:
    """Page-level footnote-marker consistency. Counting, never judgement.

    A page's footnote markers are printed twice — once at the reference in the
    body, once opening the note at the foot — and numbering restarts on every
    page (confirmed across all 20 restored pages: each begins again at 1). So
    two mechanical invariants hold with no reading required:

      * the marker values present form a continuous run 1..N, no gaps;
      * each value occurs at least twice.

    Both are *report-only* and both have legitimate exceptions at a page seam,
    where a note's reference and its text can fall on different pages — hence
    `harness proposal check`'s contract of "passes unexplained if clean,
    otherwise wants an explanation" rather than a refusal.

    `ascii_openers` catches the **half-open pairing**: a page that keyed one
    marker as a superscript and another as a plain digit. That is why a bare-digit
    line only counts once a superscript has already appeared earlier in reading
    order — the superscript is what proves this page's own convention, and against
    it a bare digit is an inconsistency rather than a guess. `2-034` is the case:
    body reference `dances.¹`, opener `1 See Chapter XIV.`

    **Without that condition the rule fires on ordinary prose.** `1-053` wraps
    "…Nordquist, / 2 houses)." onto its own line, which is a body continuation
    beginning with a numeral and no kind of footnote — and the page prints no
    footnote 2 at all. A permanent known-false hit is exactly the noise that
    buries real signal, so the condition is not a softening of the check.

    Deliberately **not** keyed on position. "Openers sit at the foot of the page"
    is false often enough to be useless here: some pages are half footnotes, and
    the scan is not consistent enough to support that kind of geometric judgement.

    Known limit, stated because it is not obvious: a page that keys *every* marker
    as ASCII has no superscript to trip the condition, no gaps and no singletons,
    and so passes clean. That was the state of `1-073` and `1-151` before repair —
    and is what a freshly recognized page looks like, since CATMuS emits plain
    digits. Catching that case needs a witness this function does not have.

    A **figure sub-part locant** (`FIGURE_LOCANT`) is dropped before any of this
    runs, and returned in `figure_locants` so the exclusion is visible. It is a
    raised numeral that anchors nothing, so it is printed once and fails the
    pairing invariant by construction — and a reader cannot satisfy a gate by
    keying it right. Two batches proved that the hard way: `1-137` keyed `a¹`
    down to a plain `a1` to get past the check and put a character in the store
    the page does not set, which is the one outcome this whole module exists to
    prevent. The pairing invariants stay a gate for everything else.

    `texts` must be in **reading order**; "earlier" is meaningless otherwise.

    Returns counts and offenders; the caller decides what is an issue.
    """
    # A figure locant is not a marker of anything countable, so it leaves before
    # the counting rather than being forgiven after it: it must not add a count,
    # must not fill a gap, and must not establish the page's superscript
    # convention for `ascii_openers` below.
    #
    # It is *returned* rather than merely dropped. An exclusion that reports
    # nothing is indistinguishable from a detector that never looked, and this
    # one takes a real superscript out of the count on the strength of a
    # neighbouring letter and a bracket — the reading that most wants a second
    # pair of eyes is exactly the one this silences.
    printed, texts = texts, [FIGURE_LOCANT.sub("", t) for t in texts]
    locants = [{"line": i, "digit": int(SUPERSCRIPT_DIGITS[m.group(1)]),
                "text": t[:60]}
               for i, t in enumerate(printed) for m in FIGURE_LOCANT.finditer(t)]

    counts: dict[int, int] = {}
    for text in texts:
        for ch in text:
            n = SUPERSCRIPT_DIGITS.get(ch)
            if n is not None:
                counts[n] = counts.get(n, 0) + 1
    gaps = sorted(set(range(1, max(counts) + 1)) - set(counts)) if counts else []
    singletons = sorted(n for n, c in counts.items() if c < 2)

    openers = []
    seen_superscript = False
    for i, t in enumerate(texts):
        if (m := ASCII_FOOTNOTE_OPENER.match(t)) and seen_superscript:
            openers.append({"line": i, "digit": int(m.group(1)),
                            "text": printed[i][:60]})
        if any(ch in SUPERSCRIPT_DIGITS for ch in t):
            seen_superscript = True
    return {"counts": {n: counts[n] for n in sorted(counts)},
            "gaps": gaps, "singletons": singletons, "ascii_openers": openers,
            "figure_locants": locants}


def detect_all(lines: list[str], root: Path = Path("."),
               indices: list[str] | None = None,
               lex: set[str] | None = None) -> dict[str, list[dict]]:
    """Token-level flags and paragraph-level balance flags, kept apart.

    Two lists rather than one because they are two different record shapes —
    `{type, index, token}` and `{type, paragraph, detail}`. Interleaved they
    would be a ragged table, which the tabular encoder cannot collapse (see
    emit.py); separated, both collapse to a header and rows.

    **A flag carries `index` — the line's ALTO identity — and no longer a `line`
    position.** It used to carry the 1-based position in `catmus_draft`, which
    was the only handle the collation pass had and which joined to nothing: the
    draft drops apparatus zones and figdesc lines, so on `1-151` its 37 entries
    sit against `ocr_lines`' 39, and draft position 6 is ALTO index 4. A pass
    told "line 6" and reaching for `harness ocr zoom --only 6` got a different
    line of the same page, silently. The skill's answer was a rule telling humans
    never to make that join, on the one number the model was given.

    `index` is what `ocr_lines`, `proposal.json`, `decision.json` and `ocr zoom
    --only` all key on, so a flag is now citable in `@facs` and resolvable
    against the raster. The position it replaced disambiguated nothing the token
    in the record did not already say.

    `indices` is positional to `lines`. Omitted — or the wrong length, which
    would misalign every flag rather than fail — `index` is `null`, never a
    guess. `suggest_lexicon` passes nothing, reading only `type` and `token`.

    `lex` overrides the dictionary. One caller passes it — `suggest_lexicon`,
    which detects against `_base_lexicon` so it can report what the entity store
    took off the list. Everything else wants the real one and omits it.
    """
    if indices is not None and len(indices) != len(lines):
        indices = None
    flags: list[dict] = []
    balance: list[dict] = []
    if lex is None:
        lex = _lexicon(root)
    para, para_no = [], 1
    for i, line in enumerate(lines, start=1):
        idx = indices[i - 1] if indices else None
        line = unicodedata.normalize("NFD", line)
        if not line.strip():
            balance += _balance(para, para_no)
            para, para_no = [], para_no + 1
            continue
        para.append(line)
        for m in TOKEN.finditer(line):
            # The **one shared cut**, as `EDGE_PUNCT` says it is. This loop used
            # to publish the raw whitespace-delimited token and strip only where
            # a particular check needed it, so a flag came out as `"mêˊmêl),"` —
            # the printer's punctuation glommed onto a Tier-1 form in the one
            # field a reader is meant to act on. Two costs, and the second is
            # the one that mattered: `harness proposal codepoints` and a raster
            # look were being asked about characters that are not in the word,
            # and the string did not compare equal to the *same form* in
            # `tier1_terms`, which strips. That inequality is what kept the page
            # context handing a collation pass the same evidence twice.
            #
            # U+0027 survives this deliberately (see `EDGE_PUNCT`): it is the
            # spirant mark, not punctuation, so stripping it would delete a
            # Tier-1 character from every report at once.
            tok = m.group().strip(EDGE_PUNCT)
            if not tok:
                continue
            hits = []  # union semantics: a token may carry several types
            if any(c in INVENTORY_CHARS for c in tok):
                hits.append("inventory_glyph")
            seen = set(tok) & LOOKALIKES
            # An English possessive is the one lookalike with an innocent
            # explanation the token itself can supply, and only when U+2019 is
            # the *only* lookalike present: another one in the same token means
            # the form is not ordinary English whatever the apostrophe is doing.
            if seen and not (seen == {"’"} and english_genitive(tok, lex)):
                hits.append("apostrophe_adjacency")
            if DOT_ABOVE_G.search(tok):
                hits.append("dot_above_g")
            if _suffix_mark_drop(tok):
                hits.append("suffix_mark_drop")
            if MEDIAL_CAPS.search(tok):
                hits.append("word_medial_caps")
            if "'" in tok and "inventory_glyph" in hits:
                kinds = {h["kind"] for h in apostrophe_licensing(tok)}
                if "unlicensed" in kinds:
                    hits.append("apostrophe_unlicensed")
                if "ambiguous" in kinds:
                    hits.append("apostrophe_ambiguous")
            for h in hits:
                flags.append({"type": h, "index": idx, "token": tok})
            # Union semantics, as the module docstring says: only a detector
            # that has already established the token is not English earns the
            # right to suppress the lexicon check.
            if lex and not (set(hits) & NON_ENGLISH_HITS) and lexicon_miss(tok, lex):
                flags.append({"type": "lexicon_miss", "index": idx, "token": tok})
    balance += _balance(para, para_no)
    return {"tokens": flags, "balance": balance}


def suggest_lexicon(root: Path = Path(".")) -> dict:
    """Frequency-ranked `lexicon_miss` tokens across every hand-keyed page.

    Terms get approved in bulk from a real count, rather than one page at a time
    as they happen to surface. Tokens already accounted for do not appear, so
    the list shortens as it is worked through.

    Judgement about what belongs where stays with the human: this only says what
    is frequent, not what is English, and not which store a name belongs in.

    **Two lists, because there are now two sources.** Detection runs against
    `_base_lexicon` — the dictionary and `data/lexicon_extra.txt` — and each hit
    is then tested against the full lexicon, so a token the *entity store*
    accounts for comes back under `suppressed` instead of vanishing. A whitelist
    that silently absorbed names would be the same defect as a whitelist nobody
    can audit: the moved proper nouns are still visible, and so is any Tier-1
    form that reaches an alias table and turns out to be ASCII enough to
    matter.

    **`gt/ocr/` by name, not the `ocr/` view.** This used to walk the view, which
    was an alias for the ground truth and nothing else; since `ocr predict` it also
    resolves into `mz/ocr/`, and every recognizer error there is a token no
    dictionary carries — i.e. a `lexicon_miss`. Walking the view would fill this
    list with CATMuS's misreadings and invite them into a **committed, human-edited
    file** that suppresses the very detector meant to catch them. The same rule as
    `normalize`'s scope and `zones check --store mz`: a machine store is measured,
    never allowed to decide.
    """
    from .context import _draft_text, all_refs, stem_for
    from .lines import page_lines

    base, full = _base_lexicon(root), _lexicon(root)
    counts: dict[str, int] = {}
    where: dict[str, str] = {}
    for ref in all_refs(root, "gt/ocr"):
        ocr = root / "gt" / "ocr" / f"{stem_for(ref, root)}.xml"
        if not ocr.exists():
            continue
        # `page_lines` rather than `context._lines_from_alto`, and the join here
        # rather than inside that reader. Both are deliberate: it produces
        # `catmus_draft`, the text handed to the collation pass, which must keep
        # reproducing the page line for line — the model reads the raster beside
        # it — and it drops the geometry the column guard needs. Same reading
        # order either way, `_lines_from_alto` being a projection of this call.
        lines = [t for t in join_broken_words(page_lines(ocr, root, ref=ref))
                 if t.strip()]
        draft = _draft_text(lines)
        for f in detect_all(draft.split("\n"), root, lex=base)["tokens"]:
            if f["type"] != "lexicon_miss":
                continue
            # No second strip: `detect_all` publishes the token already cut, so
            # repeating `EDGE_PUNCT` here would be the "second strip downstream"
            # that constant's own comment records as the thing to stop doing.
            tok = f["token"]
            counts[tok] = counts.get(tok, 0) + 1
            where.setdefault(tok, ref)
    rows = [{"token": t, "count": c, "first_seen": where[t]}
            for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"tokens": [r for r in rows if lexicon_miss(r["token"], full)],
            "suppressed": [r for r in rows
                           if not lexicon_miss(r["token"], full)]}


# Marks that visibly attach after a base letter, for `mark_base_frequency`. Not
# `INVENTORY_CHARS`'s combining subset reused wholesale: U+02D9 (dot above, the
# palatalization postposed mark, §2.1) is grouped with the atomics there because
# it does not compose under NFD, but for "what sits after this base letter" it
# behaves exactly like a combining mark and belongs in this set too.
_MARKS_AFTER = {"̣", "̌", "̃", "̂", "̈", "̆",
                "̄", "˙"}


def _restored_refs(root: Path = Path(".")) -> list[str]:
    """Refs whose `gt/ocr/` ALTO actually holds text — shells excluded.

    `gt/ocr/` by name, at both steps. That used to be phrased as avoiding a
    double count — the view was an alias for this store and nothing else — and
    since `ocr predict` it is the stronger point: the view also resolves into
    `mz/ocr/`, and a recognizer's reading is not restored ground truth however much
    text it holds. Every frequency table this feeds (`lexicon native`, `marks`,
    `suffixes`, `digraphs`) is cited by `keying_spec.md` §5.1, so blending ranks
    here would move published numbers silently.

    Also the one filter that knows which of the 20 pilot refs are still empty
    export shells (CLAUDE.md, "The ground-truth loss").
    """
    from .context import all_refs, stem_for

    out = []
    for ref in all_refs(root, "gt/ocr"):
        p = root / "gt" / "ocr" / f"{stem_for(ref, root)}.xml"
        if not p.exists():
            continue
        try:
            tree = etree.parse(str(p))
        except Exception:
            continue
        if any((s.get("CONTENT") or "").strip()
               for s in tree.getroot().iter("{*}String")):
            out.append(ref)
    return out


def native_corpus(root: Path = Path(".")) -> list[tuple[str, str]]:
    """(ref, token) for every `inventory_glyph`-flagged token in restored ground truth.

    Ground truth only, never OCR draft — draft CATMuS output reads 0% of the
    inventory (the collation skill, "What CATMuS can and cannot read"), so it is not a
    witness to native spelling at all, only to line geometry and English.
    `inventory_glyph` is the exact test `detect_all` already applies, reused
    rather than re-derived so the two stay in lockstep. A floor, not a census,
    for the same reason stated at the top of this module: a native token
    carrying no mark at all (a bare `c`, `s`, `j`, `x`, `h`) is invisible to
    it by construction and never enters this corpus.
    """
    return [(ref, tok) for ref, _, tok in native_corpus_lines(root)]


def cyrillic(token: str) -> bool:
    """Is this Russian rather than Tier-1?

    **Public because two arms select Tier-1 tokens and both must apply it.**
    `native_corpus` builds the frequency tables; `context.tier1_terms` builds
    the handles the generator wraps. They disagreed for a while, and the
    disagreement was visible only from the reading view: `Чукотскій` on 1-031
    got a Tier-1 handle from one and was excluded from the other, so the page
    linked a Russian word to a lexicon that correctly held no card for it.

    **`й` is `и` + U+0306, and U+0306 is an inventory member**, so pre-reform
    Russian walked straight into the native corpus on a breve the inventory means
    as a length mark. Five tokens over three pages — `Край`, `Ушканій`,
    `Черкасскій`, `Черкесскій`, `Чукотскій` — and it was invisible until `1-359`,
    a gazetteer setting a Russian column beside every native name, made the class
    large enough to notice.

    They are not a small error in the right units: Russian is Tier-2, the ASCII
    policy does not reach it and no Cyrillic string is evidence about Bogoras's
    notation at all. Every table `native_corpus` feeds is cited by `keying_spec.md`
    §5.1, so this was five wrong rows inside published numbers.
    """
    return any("Ѐ" <= c <= "ӿ" for c in token)


def native_corpus_lines(root: Path = Path(".")) -> list[tuple[str, str, str]]:
    """(ref, line index, token) — `native_corpus` with the line each token sat on.

    `native_corpus` is this with the middle field dropped and both are
    `native_corpus_context` with fields dropped, rather than three walks over the
    store: the selection rule is the thing that has to match between every arm
    reading native forms, so it is written once.

    **The index is `page_lines`', which is the one `proposal.json` and
    `decision.json` are keyed by** and the one `harness ocr lines` prints. Not
    document order and not a counter: `context._lines_from_alto` drops empty
    lines, so its position is not the ALTO's, and joining through it is the
    documented way to mis-map an adjudicated page (harness/README.md, "Three invariants
    from that work").
    """
    return [(r["ref"], r["line"], r["token"]) for r in native_corpus_context(root)]


def native_corpus_context(root: Path = Path(".")) -> list[dict]:
    """Every native token in ground truth, **with the line it was printed on**.

    The line is what makes a form's sense readable without opening the page:
    `Kuluˊči` alone is a string, and "south of Kuluˊči Bay" is a place. `lexicon
    lookup` is the caller that needs it, and it needs the *joined* text — the same
    string the token was matched in — so a form broken across a column foot cites
    a line that actually contains it.

    Fields: `ref`, `line` (the `page_lines` index), `token`, `text`.
    """
    from .lines import page_lines

    out = []
    for ref in _restored_refs(root):
        p = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
        recs = page_lines(p, root, ref=ref)
        # Reading order is what `page_lines` returns, which is what the join
        # requires: a word broken at the foot of the left column continues at
        # the head of the right one, not at the next ALTO sibling. The records
        # are not reordered and `index` is not renumbered, so a token still
        # cites the line it was printed on.
        texts = [unicodedata.normalize("NFD", t)
                 for t in join_broken_words(recs)]
        for rec, line in zip(recs, texts, strict=True):
            for m in TOKEN.finditer(line):
                tok = m.group().strip(EDGE_PUNCT)
                if tok and not cyrillic(tok) and any(c in INVENTORY_CHARS
                                                      for c in tok):
                    out.append({"ref": ref, "line": str(rec["index"]),
                                "token": tok, "text": line})
    return out


def suggest_native_forms(root: Path = Path(".")) -> list[dict]:
    """Frequency-ranked native (Tier-1) word forms across restored ground truth.

    Inverted from `suggest_lexicon`: that hunts frequent tokens no English
    lexicon knows, to whitelist as real English. This hunts frequent tokens
    already confirmed non-English, so a reviewer keying a new page has a
    reference set of known-good forms to check a new reading against — a
    proposal that's a near-miss against one of these (one mark off, one base
    letter swapped) is a candidate misspelling rather than a genuinely new
    word. `1-073`'s j/breve slip and `2-040`'s dropped g̣ (keying_spec.md §5, "Error
    profile so far") are exactly the class this exists to catch on a future
    page, had the recurring word already been in this list to check against.

    Ground truth only (see `native_corpus`), so this is a floor that grows as
    more of the 20 pilot pages are restored — recompute rather than trust a
    stale run; do not treat an 11/20 snapshot as the final word on frequency.
    """
    counts: dict[str, int] = {}
    refs: dict[str, set[str]] = {}
    for ref, tok in native_corpus(root):
        counts[tok] = counts.get(tok, 0) + 1
        refs.setdefault(tok, set()).add(ref)
    return [{"form": t, "count": c, "refs": " ".join(sorted(refs[t]))}
            for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def mark_base_frequency(root: Path = Path(".")) -> list[dict]:
    """Bare-vs-marked frequency per base letter, across the native corpus.

    A prior for exactly the class of error that keeps recurring — dropped
    U+0323 under `g`, three times now (`1-074`, `1-100`, `2-040`; keying_spec.md §5,
    "Error profile so far"): absent a clean raster read, which form is the
    more likely one? Ground truth only, same floor caveat as `native_corpus`
    — a working prior from what has been restored so far, not a population
    estimate, and worth recomputing rather than trusting once more of the 20
    pilot pages land.
    """
    counts: dict[str, dict[str, int]] = {}
    for _, tok in native_corpus(root):
        i, n = 0, len(tok)
        while i < n:
            ch = tok[i]
            if ch.isalpha() and ch not in _MARKS_AFTER:
                mark = tok[i + 1] if i + 1 < n and tok[i + 1] in _MARKS_AFTER else ""
                base = ch.lower()
                counts.setdefault(base, {})
                counts[base][mark] = counts[base].get(mark, 0) + 1
            i += 1
    out = []
    for base, marks in sorted(counts.items()):
        total = sum(marks.values())
        for mark, n in sorted(marks.items(), key=lambda kv: -kv[1]):
            out.append({"base": base, "form": base + mark, "count": n,
                        "share_pct": round(100 * n / total, 1)})
    return out


# Categories dropped by `_strip_marks`: Mn is the NFD combining series
# (circumflex, diaeresis, tilde, caron, breve, dot-below — everything that
# rides on a base letter), Lm/Sk are the standalone modifier marks that don't
# combine under NFD (U+02CA stress, U+1D4B laryngeal, U+02D9 palatalization,
# U+1D49 onglide). Small-cap letters (ᴀ ᴇ ɪ ʟ) and ɵ are category Ll — real
# base letters, not marks — and survive; so does U+0027 (spirant/pause),
# a real phonetic segment rather than a diacritic on one.
_MARK_CATEGORIES = {"Mn", "Lm", "Sk"}
# `_EDGE_QUOTES` stood here — a second edge strip over `suggest_native_forms`'
# output, covering the curly quotes `EDGE_PUNCT` did not. It is gone because the
# tokenizer now cuts those edges itself, so this was patching a form that had
# already been published quoted in `lexicon native`. It also stripped U+0027,
# which is a Tier-1 segment and not punctuation: a form ending in the spirant
# lost it from every suffix and digraph counted here.


def _strip_marks(tok: str) -> str:
    """`tok`, NFD-normalized, with diacritic/modifier marks removed."""
    tok = unicodedata.normalize("NFD", tok)
    return "".join(c for c in tok if unicodedata.category(c) not in _MARK_CATEGORIES)


def suffix_frequency(root: Path = Path(".")) -> list[dict]:
    """Weighted suffix frequency (length 2-8) over mark-stripped native forms.

    Built to answer a concrete question raised reading `3-004`: `-g̣ɪn` /
    `-rg̣ɪn` / `-ɪrg̣ɪn` are common noun-forming suffixes (not just a
    kinship-vocabulary pattern — `va'ɪrg̣ɪn`, "spirit", takes the same one),
    so a Tier-1 word ending plain `-gin`/`-git` should be treated as
    presumptively wrong on the suffix's own shape, before the raster is even
    consulted (keying_spec.md §5.1). Marks are stripped first (`_strip_marks`)
    so a stress mark or circumflex sitting near the boundary doesn't split one
    real suffix into several accidental variants.

    Ground truth only (`suggest_native_forms`), so this is a floor that grows
    as more of the 20 pilot pages are restored — recompute rather than trust
    a stale run, same caveat as `suggest_native_forms` and `mark_base_frequency`.
    """
    counts: dict[str, int] = {}
    for rec in suggest_native_forms(root):
        w = _strip_marks(rec["form"])
        for length in range(2, 9):
            if len(w) >= length:
                s = w[-length:]
                counts[s] = counts.get(s, 0) + rec["count"]
    return [{"suffix": s, "len": len(s), "count": c}
            for s, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def digraph_frequency(root: Path = Path(".")) -> list[dict]:
    """Weighted digraph/trigraph frequency, marks and top suffixes stripped.

    Two strips before counting, both because a raw scan over untouched forms
    answers a different question than the one asked: `_strip_marks` so a
    diacritic or the stress mark never counts as one of the two-or-three
    letters in an n-gram (a reader doesn't read "e" + acute-stress as a
    digraph, and neither should this); stripping the corpus's own most
    frequent suffixes (the top 12 from `suffix_frequency`, longest match
    first, one strip per word) so the count reflects the *stem*, not the
    suffix family repeating itself under a new name at every rank.

    Ground truth only, same floor caveat as `suffix_frequency` — recompute
    once more of the 20 pilot pages land rather than trusting a stale run.
    """
    forms = suggest_native_forms(root)
    stripped = [(_strip_marks(rec["form"]), rec["count"])
                for rec in forms]

    suf_counts: dict[str, int] = {}
    for w, c in stripped:
        for length in range(2, 9):
            if len(w) >= length:
                s = w[-length:]
                suf_counts[s] = suf_counts.get(s, 0) + c
    top = sorted(suf_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
    # Longest first, so 'ɪrgɪn' consumes a matching word before 'gɪn' can.
    top_suffixes = sorted({s for s, _ in top}, key=len, reverse=True)

    def strip_suffix(w: str) -> str:
        for s in top_suffixes:
            if w.endswith(s) and len(w) > len(s):
                return w[:-len(s)]
        return w

    ngrams: dict[str, int] = {}
    for w, c in stripped:
        stem = strip_suffix(w)
        n = len(stem)
        for i in range(n - 1):
            g = stem[i:i + 2]
            ngrams[g] = ngrams.get(g, 0) + c
        for i in range(n - 2):
            g = stem[i:i + 3]
            ngrams[g] = ngrams.get(g, 0) + c
    return [{"ngram": g, "n": len(g), "count": c} for g, c in
            sorted(ngrams.items(), key=lambda kv: (len(kv[0]), -kv[1], kv[0]))]


def _balance(para_lines: list[str], para_no: int) -> list[dict]:
    if not para_lines:
        return []
    text = " ".join(para_lines)
    out = []
    if text.count('"') % 2:
        out.append({"type": "quote_balance", "paragraph": para_no,
                    "detail": "odd straight-quote count in paragraph"})
    for o, c, name in (("(", ")", "paren"), ("[", "]", "bracket")):
        if text.count(o) != text.count(c):
            out.append({"type": f"{name}_balance", "paragraph": para_no,
                        "detail": f"{text.count(o)} open vs {text.count(c)} close"})
    return out
