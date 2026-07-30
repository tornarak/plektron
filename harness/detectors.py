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
# the spec says so outright \u2014 the breve is productive as a length mark, so further
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
# of the three and missed the third \u2014 one page, one form, three occurrences, and the
# inconsistency survived a human pass because nothing compared them. Breve-on-j is now
# unrepresentable rather than merely wrong.
MARK_LICENSE = {
    "\u0306": set("ui"),  # breve, a length mark: \u016D (\u00A72.2) and \u012D (\u00A72.6)
}


def unlicensed_marks(text: str) -> list[dict]:
    """Every combining mark sitting on a base its licence does not cover.

    Assumes NFD, so a base is simply the character before the mark. A mark in
    initial position has no base at all and is reported the same way \u2014 it cannot be
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
            "base": (f"{base!r} (U+{ord(base):04X})" if base else "(nothing \u2014 "
                     "mark in initial position)"),
            "licensed_on": " ".join(sorted(allowed)),
            "context": text[max(0, i - 12):i + 8],
        })
    return out
# There is deliberately no SMART_QUOTES detector. Curly quotes are what the book
# prints, and under the Tier-1-scoped ASCII policy (keying spec section 1) English
# prose reproduces them, so a flag here fires on correct text: the noise this
# module's docstring warns about. The rule that survives is narrow, that inside a
# Tier-1 span U+2019 traps U+0027, and it can only be enforced where the language is
# known. The draft plaintext carries no markup, so it lives in
# validate.LOOKALIKE_GREPS against the TEI instead.
# Word-*medial*, which means the small-cap letterform sits inside the word. The
# capital must be adjacent to a lower-case letter AND not be the word's first
# letter \u2014 without that second condition every capitalised English word
# beginning A/E/I/L ("English", "Iron", "Later") fires, which is both noise and,
# because a hit used to suppress the lexicon check, a mask over real signal.
MEDIAL_CAPS = re.compile(r"(?<=[a-z])[AEIL]|(?<=[A-Za-z])[AEIL](?=[a-z])")
DOT_ABOVE_G = re.compile(r"\u0121|g\u0307")
TOKEN = re.compile(r"[^\s]+")
# Punctuation stripped from a token's *edges* before lexicon lookup. Internal
# hyphens and apostrophes are load-bearing in English too ("sea-mammals",
# "don't"), so they survive to the split below instead of being deleted.
EDGE_PUNCT = "\"'()[]{}.,;:!?\u2014\u2013-*\u2020\u2021\u00A7\u00B6"
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
    expected to carry \u2014 Latin binomials, ethnonyms, Bogoras's recurring
    coinages. It suppresses `lexicon_miss` and nothing else: the inventory,
    apostrophe, dot-above-g and smart-quote detectors never consult it. A
    whitelist able to blind a Tier-1 detector would be a hole in the firewall,
    so it is denied the opportunity structurally rather than by discipline.

    Stronger than that, and worth stating because it is what actually holds the
    line: `lexicon_miss` only ever tests ASCII components, so a Tier-1 form
    listed in the whitelist is inert there \u2014 it could not have been a lexicon
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
    """`data/lexicon_extra.txt` \u2014 one term per line, `#` comments, blanks ok."""
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
    and apostrophes and each component checked separately \u2014 otherwise
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
            if MEDIAL_CAPS.search(tok):
                hits.append("word_medial_caps")
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
