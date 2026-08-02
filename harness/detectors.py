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
they are two record shapes — `{type, line, token}` and
`{type, paragraph, detail}`. Interleaved they would be a ragged table, which
the tabular encoder cannot collapse; see emit.py.

The floor is a floor, but it is not an excuse for noise above it. A detector
that fires on ordinary English is worse than one that stays quiet, because it
buries the real hits and — where a hit suppresses a later check — masks them
outright. Hence the word-boundary guard on MEDIAL_CAPS, the edge-only
punctuation stripping in `lexicon_miss`, and the whitelist.
"""
from __future__ import annotations
import re, unicodedata
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


def unlicensed_marks(text: str) -> list[dict]:
    """Every combining mark sitting on a base its licence does not cover.

    Assumes NFD, so a base is simply the character before the mark. A mark in
    initial position has no base at all and is reported the same way — it cannot be
    licensed by anything, and it is a real corruption rather than a keying choice.
    """
    text = unicodedata.normalize("NFD", text)
    out = []
    for i, ch in enumerate(text):
        allowed = MARK_LICENSE.get(ch)
        if allowed is None:
            continue
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
# Word-*medial*, which means not the first character of a whitespace-delimited
# token — excluding that position is required, or every capitalised English
# word beginning A/E/I/L ("English", "Iron", "Later") fires, which is both noise
# and, because a hit used to suppress the lexicon check, a mask over real
# signal. No lowercase-neighbor requirement beyond that: a capital sitting
# right after a stress mark, hyphen, or apostrophe inside a token is exactly as
# sketchy as one after a lowercase letter — 2-034’s "Lo" in a stressed,
# hyphenated Tier-1 compound (corrected to small-cap ʟ by review) was missed
# by the old lowercase-only version because the preceding character was a
# stress mark, not a letter. Trade-off worth naming: this also fires on a
# capital right after an opening paren/quote glued to the same token
# ("(In fact…"), which the old rule happened to dodge.
MEDIAL_CAPS = re.compile(r"(?<!^)(?<!\s)[AEIL]")
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
EDGE_PUNCT = "\"'()[]{}.,;:!?—\u2013-*\u2020\u2021\u00A7\u00B6"
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

_WORDS: dict[str, set[str]] = {}


def _lexicon(root: Path = Path(".")) -> set[str]:
    """System dictionary, plus the project's own additions. Cached per root.

    `data/lexicon_extra.txt` holds what a general English dictionary cannot be
    expected to carry — Latin binomials, ethnonyms, Bogoras's recurring
    coinages. It suppresses `lexicon_miss` and nothing else: the inventory,
    apostrophe, dot-above-g and smart-quote detectors never consult it. A
    whitelist able to blind a Tier-1 detector would be a hole in the firewall,
    so it is denied the opportunity structurally rather than by discipline.

    Stronger than that, and worth stating because it is what actually holds the
    line: `lexicon_miss` only ever tests ASCII components, so a Tier-1 form
    listed in the whitelist is inert there — it could not have been a lexicon
    miss in the first place.
    """
    key = str(root.resolve())
    if key not in _WORDS:
        words: set[str] = set()
        for cand in (Path("/usr/share/dict/american-english"),
                     Path("/usr/share/dict/words"),
                     root / "data" / "english_lexicon.txt"):
            if cand.exists():
                words = {w.strip().lower()
                         for w in cand.read_text(encoding="utf-8").splitlines()}
                break
        _WORDS[key] = words | load_extra_lexicon(root)
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
    """
    core = tok.strip(EDGE_PUNCT)
    if not core:
        return False
    parts = [p for p in re.split(r"[-'\u2019]", core) if p]
    if not parts:
        return False
    for p in parts:
        if len(p) <= 3 or not p.isascii() or not p.isalpha():
            continue
        if p.lower() not in lex:
            return True
    return False


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

    `texts` must be in **reading order**; "earlier" is meaningless otherwise.

    Returns counts and offenders; the caller decides what is an issue.
    """
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
            openers.append({"line": i, "digit": int(m.group(1)), "text": t[:60]})
        if any(ch in SUPERSCRIPT_DIGITS for ch in t):
            seen_superscript = True
    return {"counts": {n: counts[n] for n in sorted(counts)},
            "gaps": gaps, "singletons": singletons, "ascii_openers": openers}


def detect_all(lines: list[str], root: Path = Path(".")) -> dict[str, list[dict]]:
    """Token-level flags and paragraph-level balance flags, kept apart.

    Two lists rather than one because they are two different record shapes —
    `{type, line, token}` and `{type, paragraph, detail}`. Interleaved they
    would be a ragged table, which the tabular encoder cannot collapse (see
    emit.py); separated, both collapse to a header and rows.
    """
    flags: list[dict] = []
    balance: list[dict] = []
    lex = _lexicon(root)
    para, para_no = [], 1
    for i, line in enumerate(lines, start=1):
        line = unicodedata.normalize("NFD", line)
        if not line.strip():
            balance += _balance(para, para_no)
            para, para_no = [], para_no + 1
            continue
        para.append(line)
        for m in TOKEN.finditer(line):
            tok = m.group()
            hits = []  # union semantics: a token may carry several types
            if any(c in INVENTORY_CHARS for c in tok):
                hits.append("inventory_glyph")
            if any(c in LOOKALIKES for c in tok):
                hits.append("apostrophe_adjacency")
            if DOT_ABOVE_G.search(tok):
                hits.append("dot_above_g")
            if _suffix_mark_drop(tok.strip(EDGE_PUNCT)):
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
                flags.append({"type": h, "line": i, "token": tok})
            # Union semantics, as the module docstring says: only a detector
            # that has already established the token is not English earns the
            # right to suppress the lexicon check.
            if lex and not (set(hits) & NON_ENGLISH_HITS) and lexicon_miss(tok, lex):
                flags.append({"type": "lexicon_miss", "line": i, "token": tok})
    balance += _balance(para, para_no)
    return {"tokens": flags, "balance": balance}


def suggest_lexicon(root: Path = Path(".")) -> list[dict]:
    """Frequency-ranked `lexicon_miss` tokens across every OCR'd page.

    Terms get approved into `data/lexicon_extra.txt` in bulk from a real count,
    rather than one page at a time as they happen to surface. Tokens already in
    the file do not appear, so the list shortens as it is worked through.

    Judgement about what belongs in the file stays with the human: this only
    says what is frequent, not what is English.
    """
    from .context import all_refs, stem_for, _lines_from_alto, _draft_text

    counts: dict[str, int] = {}
    where: dict[str, str] = {}
    for ref in all_refs(root):
        ocr = root / "ocr" / f"{stem_for(ref, root)}.xml"
        if not ocr.exists():
            continue
        draft = _draft_text(_lines_from_alto(ocr))
        for f in detect_all(draft.split("\n"), root)["tokens"]:
            if f["type"] != "lexicon_miss":
                continue
            tok = f["token"].strip(EDGE_PUNCT)
            if not tok:
                continue
            counts[tok] = counts.get(tok, 0) + 1
            where.setdefault(tok, ref)
    return [{"token": t, "count": c, "first_seen": where[t]}
            for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


# Marks that visibly attach after a base letter, for `mark_base_frequency`. Not
# `INVENTORY_CHARS`'s combining subset reused wholesale: U+02D9 (dot above, the
# palatalization postposed mark, §2.1) is grouped with the atomics there because
# it does not compose under NFD, but for "what sits after this base letter" it
# behaves exactly like a combining mark and belongs in this set too.
_MARKS_AFTER = {"̣", "̌", "̃", "̂", "̈", "̆",
                "̄", "˙"}


def _restored_refs(root: Path = Path(".")) -> list[str]:
    """Refs whose `gt/ocr/` ALTO actually holds text — shells excluded.

    `all_refs` walks `ocr/*.xml`, which is only ever a symlink into `gt/ocr/`
    (CLAUDE.md, "`ocr/*.xml` are symlinks into `gt/ocr/`"), so this reads
    `gt/ocr/` by name rather than double-counting the same file under both
    names. Also the one filter that knows which of the 20 pilot refs are
    still empty export shells (CLAUDE.md, "The ground-truth loss").
    """
    from .context import all_refs, stem_for

    out = []
    for ref in all_refs(root):
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
    inventory (CLAUDE.md, "What CATMuS can and cannot read"), so it is not a
    witness to native spelling at all, only to line geometry and English.
    `inventory_glyph` is the exact test `detect_all` already applies, reused
    rather than re-derived so the two stay in lockstep. A floor, not a census,
    for the same reason stated at the top of this module: a native token
    carrying no mark at all (a bare `c`, `s`, `j`, `x`, `h`) is invisible to
    it by construction and never enters this corpus.
    """
    out = []
    for ref in _restored_refs(root):
        p = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
        tree = etree.parse(str(p))
        for s in tree.getroot().iter("{*}String"):
            line = unicodedata.normalize("NFD", s.get("CONTENT") or "")
            for m in TOKEN.finditer(line):
                tok = m.group().strip(EDGE_PUNCT)
                if tok and any(c in INVENTORY_CHARS for c in tok):
                    out.append((ref, tok))
    return out


def suggest_native_forms(root: Path = Path(".")) -> list[dict]:
    """Frequency-ranked native (Tier-1) word forms across restored ground truth.

    Inverted from `suggest_lexicon`: that hunts frequent tokens no English
    lexicon knows, to whitelist as real English. This hunts frequent tokens
    already confirmed non-English, so a reviewer keying a new page has a
    reference set of known-good forms to check a new reading against — a
    proposal that's a near-miss against one of these (one mark off, one base
    letter swapped) is a candidate misspelling rather than a genuinely new
    word. `1-073`'s j/breve slip and `2-040`'s dropped g̣ (CLAUDE.md, "Error
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
    U+0323 under `g`, three times now (`1-074`, `1-100`, `2-040`; CLAUDE.md,
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
# Curly quotes a token can carry at its edge that EDGE_PUNCT (built for
# English prose punctuation) doesn't cover — a gloss quote wrapping a native
# form leaves one on the token when the tokenizer splits on whitespace alone.
_EDGE_QUOTES = "“”\"'"


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
        w = _strip_marks(rec["form"].strip(_EDGE_QUOTES))
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
    stripped = [(_strip_marks(rec["form"].strip(_EDGE_QUOTES)), rec["count"])
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
