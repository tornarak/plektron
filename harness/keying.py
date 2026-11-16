"""The keying rules a text is held to: its workspace's, with its own laid over.

`config/keying.json` holds the tables `keying_spec.md` backs — the inventory,
the lookalike traps at their three scopes, which bases a mark is licensed on —
as data rather than code. The workspace's file is the notation its texts share
(`jesup/config/keying.json`: the Americanist notation of the Jesup volumes);
a text's file names only what that text's book does differently, each change
with its attestation. `layout.layered` composes the two key by key, so a text
is an object over its workspace's prototype. There is no third, built-in layer:
code holding a notation would hand it to every workspace, including one whose
books were never printed in it.

**Every reader takes a `Rules`, never a module constant.** A function that judged
one text's lines by another's rules would raise nothing; the rules are passed in
explicitly from wherever the text's root is known, and `rules(root)` is the one
place they are built.

**A text's overrides are rulings, and each says what licenses it.** `_why` maps
the dotted key path of every leaf the text sets or deletes to its attestation
(`"mark_license.̆.у": "ў — 1-178 Кутјэ́ўт …"`), and a leaf without one is
refused. That is §2.6's "licensed only on attestation the editor has stamped",
made mechanical.

**The three lookalike tables stay three** (`test_lookalike_scope.py`): `lookalikes`
is triage over OCR lines, `lookalike_chars` the corpus-wide file gate,
`lookalike_greps` the worklist inside Tier-1 spans. One file holding all of them
does not merge them.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .layout import DELETE, LayerError, layered, workspace_root

CONFIG = "config/keying.json"

#: Each table, and whether its keys are single codepoints. A sequence table's
#: keys may be longer, which is why it is a table of its own.
CHAR_TABLES = ("inventory", "lookalikes", "tier1_traps", "lookalike_chars",
               "lookalike_greps")
SEQ_TABLES = ("lookalike_seqs", "lookalike_seq_greps")
MARK_TABLES = ("mark_license", "orthographic_bases")
#: Tables of rules rather than of glyphs: which detectors a notation runs, which
#: scripts are never Tier-1, and the prose alphabet a token's notation is measured
#: against. Keyed by name or by ISO 15924 code, from the closed sets below.
RULE_TABLES = ("detectors", "tier2_scripts", "prose_alphabet", "folds",
               "script_folds", "numeral_folds")
TABLES = CHAR_TABLES + SEQ_TABLES + MARK_TABLES + RULE_TABLES

#: The Roman numeral letters, Unicode's Latin: a fact, not a ruling.
ROMAN = frozenset("IVXLCDM")
#: A word, for the word-level folds: a run of letters and the marks on them. A
#: hyphen, an apostrophe or a quote ends one, so each half of `тот-төмwа́ткен` is
#: judged alone, and so is each side of `CONTENT="`.
WORD = re.compile(r"(?:[^\W\d_]|[̀-ͯ])+")

#: The detectors a notation may switch. Each is written for one notation's facts —
#: the Jesup small capitals, its g̣, its stress mark — so a text whose book prints
#: none of them deletes the switch rather than living with the noise. Closed: a
#: name the code does not know would be a switch that switches nothing.
DETECTORS = frozenset({"word_medial_caps", "dot_above_g", "suffix_mark_drop",
                       "apostrophe_unlicensed", "footnote_paren_opener"})

#: Scripts by ISO 15924 code, as codepoint ranges. Unicode's facts, not a
#: notation's, which is why they are code: what the rules say *about* a script is
#: the data. `Cyrl` is the range `detectors.cyrillic` always tested.
SCRIPTS = {"Cyrl": ("\u0400", "\u04ff")}


def in_script(c: str, script: str) -> bool:
    lo, hi = SCRIPTS[script]
    return lo <= c <= hi


class KeyingError(ValueError):
    """Keying rules that cannot be read, composed, or trusted."""


@dataclass(frozen=True)
class Rules:
    """The effective tables for one text, plus what is derived from them once."""

    inventory: frozenset[str]
    lookalikes: frozenset[str]
    tier1_traps: dict[str, str]
    lookalike_chars: dict[str, str]
    lookalike_seqs: dict[str, str]
    lookalike_greps: dict[str, str]
    lookalike_seq_greps: dict[str, str]
    mark_license: dict[str, frozenset[str]]
    orthographic_bases: dict[str, str]
    detectors: frozenset[str] = frozenset()
    tier2_scripts: frozenset[str] = frozenset()
    prose_alphabet: dict[str, frozenset[str]] = field(default_factory=dict)
    #: `{sequence: sequence}` — a sort the editor has identified, keyed as what the
    #: OCR emits for it, in NFD: a letter, or a letter and its mark (`ď` is
    #: d + U+030C). Applied wherever text enters a store.
    folds: dict[str, str] = field(default_factory=dict)
    #: `{script: {"pairs": {latin: letter}, "keep": latin}}` — the Latin lookalikes
    #: a layer sets inside a word of `script`, each with the letter it stands for.
    #: A word holding a letter of the script has its lookalikes folded, but only
    #: if nothing Latin is left afterwards outside `keep` (the notation's own
    #: Latin letters): a Latin name with a Russian ending keeps its `m` or `n`,
    #: so it is left whole. A word with no letter of the script is never touched,
    #: which is what spares a numeral and a Latin or French quotation.
    script_folds: dict[str, dict] = field(default_factory=dict)
    #: `{letter: roman}` — the other scripts' lookalikes of a Roman numeral letter.
    #: A word that is all numeral letters once folded is a numeral, keyed Latin.
    numeral_folds: dict[str, str] = field(default_factory=dict)
    #: `{key path: tier}` — which layer set each leaf. For reports, never logic.
    origin: dict = field(default_factory=dict, compare=False, repr=False)

    def on(self, detector: str) -> bool:
        """Does this text run `detector`? A name outside `DETECTORS` is a bug."""
        if detector not in DETECTORS:
            raise KeyError(detector)
        return detector in self.detectors

    def tier2(self, token: str) -> bool:
        """Is `token` in a script this text never transcribes as Tier-1?

        *The Chukchee* says so of Cyrillic: its Russian is Tier-2 prose (§2.7). The
        1900 *Materials* prints its Chukchi in Cyrillic and deletes the entry, so
        the same test answers False there and the token is judged by its glyphs.
        """
        return any(in_script(c, s) for s in self.tier2_scripts for c in token)

    def fold(self, text: str) -> str:
        """`text` (NFD) with every ruled sort in its codepoints, longest key first,
        then each word the word-level folds reach."""
        if self.folds:
            text = _fold_pattern(tuple(self.folds)).sub(
                lambda m: self.folds[m.group()], text)
        if self.script_folds or self.numeral_folds:
            text = WORD.sub(lambda m: self.fold_word(m.group()), text)
        return text

    def fold_word(self, word: str) -> str:
        """One word under the word-level folds: a numeral to Latin, else a word of
        a folded script with its Latin lookalikes in that script, else itself."""
        if self.numeral_folds:
            roman = "".join(self.numeral_folds.get(c, c) for c in word)
            if roman != word and set(roman) <= ROMAN:
                return roman
        for script, rule in self.script_folds.items():
            if not any(in_script(c, script) for c in word):
                continue
            pairs, keep = rule["pairs"], _keep(rule["keep"])
            out, left, i = [], False, 0
            while i < len(word):
                kept = next((k for k in keep if word.startswith(k, i)), None)
                if kept:
                    out.append(kept)
                    i += len(kept)
                    continue
                c = pairs.get(word[i], word[i])
                left = left or (c.isascii() and c.isalpha())
                out.append(c)
                i += 1
            if not left and "".join(out) != word:
                return "".join(out)
        return word

    def unfolded_latin(self, word: str) -> str:
        """The Latin letters `fold_word` leaves in a word that also holds a letter of
        a folded script, outside that script's keep list; empty if none.

        Such a word is what the fold declines: a Latin letter with no pair
        (`Lawtыlыwа́lын`, a `t` keyed for `т`) leaves it undecided between a
        transclusion and a slip, so it is left whole. Whole, it must be reported,
        because a word holding Cyrillic is a transclusion of nothing."""
        word = self.fold_word(word)
        for script, rule in self.script_folds.items():
            if not any(in_script(c, script) for c in word):
                continue
            rest = word
            for k in _keep(rule["keep"]):
                rest = rest.replace(k, "")
            left = "".join(c for c in rest if c.isascii() and c.isalpha())
            if left:
                return left
        return ""

    @property
    def word_folds_record(self) -> str:
        """The word-level folds as one provenance value; empty when there are none.

        Free of `; ` and `: `, which separate a processing step's settings."""
        parts = [f"{s} {' '.join(f'{a}>{b}' for a, b in sorted(r['pairs'].items()))}"
                 f" keep {r['keep']}" for s, r in sorted(self.script_folds.items())]
        if self.numeral_folds:
            parts.append("numerals " + " ".join(
                f"{a}>{b}" for a, b in sorted(self.numeral_folds.items())))
        return ", ".join(parts)

    def fold_spans(self, text: str) -> list[tuple[int, str, str]]:
        """(offset, from, to) of every fold `fold` would make in `text`, in order:
        a ruled sort, or a whole word the word-level folds rewrite."""
        out = []
        if self.folds:
            out += [(m.start(), m.group(), self.folds[m.group()])
                    for m in _fold_pattern(tuple(self.folds)).finditer(text)]
        # A word is judged as `fold` judges it: after the ruled sorts. Judged raw,
        # `Кэlę` (Latin ę, which folds to є) reported a word fold to `Кэlе̨` that
        # `fold` never makes.
        if self.script_folds or self.numeral_folds:
            sorts = (lambda w: _fold_pattern(tuple(self.folds)).sub(
                lambda m: self.folds[m.group()], w)) if self.folds else (lambda w: w)
            out += [(m.start(), m.group(), w) for m in WORD.finditer(text)
                    if (w := self.fold_word(s := sorts(m.group()))) != s]
        return sorted(out)

    @property
    def t1(self) -> str:
        """The inventory as one regex-class body, in a fixed order."""
        return "".join(sorted(self.inventory))

    @property
    def medial_caps(self) -> re.Pattern:
        return _medial_caps(self.t1)

    @property
    def hyphen_medial_caps(self) -> re.Pattern:
        return _hyphen_medial_caps(self.t1)

    @property
    def licensed_marks(self) -> re.Pattern:
        return _licensed_marks("".join(self.mark_license))

    @property
    def lookalike_probes(self) -> tuple[tuple[str, str], ...]:
        """Chars then sequences, in table order — the report's row order."""
        return tuple(self.lookalike_chars.items()) + tuple(self.lookalike_seqs.items())


@lru_cache(maxsize=64)
def _keep(keep: str) -> tuple[str, ...]:
    """A `script_folds` keep list: space-separated sequences, longest first, so
    `ę` (e + U+0328) is kept whole before a bare `e` could be folded."""
    return tuple(sorted(keep.split(), key=len, reverse=True))


@lru_cache(maxsize=64)
def _fold_pattern(keys: tuple[str, ...]) -> re.Pattern:
    """One alternation over the fold keys, longest first, so `ď` is taken whole."""
    return re.compile("|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True)))


@lru_cache(maxsize=64)
def _medial_caps(t1: str) -> re.Pattern:
    return re.compile(rf"(?<=[a-z{t1}])[AEIL]|(?<=[A-Za-z{t1}])[AEIL](?=[a-z{t1}])")


@lru_cache(maxsize=64)
def _hyphen_medial_caps(t1: str) -> re.Pattern:
    return re.compile(rf"(?<=-)[AEIL](?=[a-z{t1}])")


@lru_cache(maxsize=64)
def _licensed_marks(marks: str) -> re.Pattern:
    return re.compile(f"[{''.join(re.escape(c) for c in marks)}]")


def _leaves(d: dict, path=()):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _leaves(v, path + (k,))
        else:
            yield path + (k,), v


def _check(merged: dict, origin: dict, why: dict, where: str) -> None:
    missing = [t for t in TABLES if not isinstance(merged.get(t), dict)]
    if missing:
        raise KeyingError(f"{where}: no {', '.join(missing)} — the workspace's "
                          f"{CONFIG} must define every table")
    for t in CHAR_TABLES + MARK_TABLES:
        for k in merged[t]:
            if len(k) != 1:
                raise KeyingError(f"{where}: {t} is keyed by single codepoints; got {k!r}")
    for t in MARK_TABLES:
        for m, bases in merged[t].items():
            if not isinstance(bases, dict) or any(len(b) != 1 for b in bases):
                raise KeyingError(f"{where}: {t}[{m!r}] maps single-codepoint bases to "
                                  "their reason")
    for path, v in _leaves({t: merged[t] for t in TABLES}):
        if not (isinstance(v, str) and v.strip()):
            raise KeyingError(f"{where}: {'.'.join(path)} has no value — every entry "
                              "says what it is")
    for name in merged["detectors"]:
        if name not in DETECTORS:
            raise KeyingError(f"{where}: detectors names {name!r}; the code runs "
                              f"{sorted(DETECTORS)}")
    for t in ("tier2_scripts", "prose_alphabet"):
        for code in merged[t]:
            if code not in SCRIPTS:
                raise KeyingError(f"{where}: {t} names script {code!r}; known: "
                                  f"{sorted(SCRIPTS)}")
    for code, letters in merged["prose_alphabet"].items():
        bad = [c for c in letters if not (in_script(c, code) and c.isalpha()
               and unicodedata.normalize("NFD", c) == c)]
        if bad:
            raise KeyingError(f"{where}: prose_alphabet[{code!r}] holds {bad}: an "
                              "alphabet is the script's own letters, each NFD-stable")
    def _sort(s: str) -> bool:
        """A letter, or a letter and its marks, as NFD spells it."""
        return (isinstance(s, str) and 0 < len(s) <= 3
                and unicodedata.normalize("NFD", s) == s
                and not unicodedata.category(s[0]).startswith("M")
                and all(unicodedata.category(c).startswith("M") for c in s[1:]))
    folds = merged["folds"]
    for src, dst in folds.items():
        if not (_sort(src) and _sort(dst)) or src == dst:
            raise KeyingError(f"{where}: folds[{src!r}] = {dst!r}; a fold maps one "
                              "sort (a letter and its marks, in NFD) to another")
        if any(k in dst for k in folds):
            raise KeyingError(f"{where}: folds chain at {dst!r}; each fold lands on "
                              "the sort, never on another fold")
        if any(c in merged["lookalike_chars"] for c in dst):
            raise KeyingError(f"{where}: folds[{src!r}] lands on {dst!r}, which "
                              "lookalike_chars refuses")
    for code, rule in merged["script_folds"].items():
        if code not in SCRIPTS:
            raise KeyingError(f"{where}: script_folds names script {code!r}; known: "
                              f"{sorted(SCRIPTS)}")
        pairs, keep = (rule.get("pairs"), rule.get("keep")) if isinstance(rule, dict) \
            else (None, None)
        if not isinstance(pairs, dict) or not isinstance(keep, str):
            raise KeyingError(f"{where}: script_folds[{code!r}] is "
                              "{\"pairs\": {latin: letter}, \"keep\": latin}")
        for src, dst in pairs.items():
            if not (len(src) == len(dst) == 1 and src.isascii() and src.isalpha()
                    and in_script(dst, code) and dst.isalpha()):
                raise KeyingError(f"{where}: script_folds[{code!r}] pairs {src!r} with "
                                  f"{dst!r}; a pair is one Latin letter and one "
                                  f"letter of {code}")
        bad = [k for k in keep.split()
               if not (_sort(k) and k[0].isascii() and k[0].isalpha())
               or k in pairs]
        if bad or not keep.split():
            raise KeyingError(f"{where}: script_folds[{code!r}] keep {bad or keep!r}: "
                              "keep is the Latin sorts left as they are, space-"
                              "separated, each a letter and its marks in NFD and "
                              "none a bare letter the pairs fold")
    for src, dst in merged["numeral_folds"].items():
        if not (len(src) == 1 and not src.isascii() and dst in ROMAN):
            raise KeyingError(f"{where}: numeral_folds[{src!r}] = {dst!r}; a fold maps "
                              f"one non-Latin letter to a Roman numeral letter "
                              f"({''.join(sorted(ROMAN))})")
    for m, bases in merged["orthographic_bases"].items():
        lic = merged["mark_license"].get(m)
        if lic is not None and not set(bases) <= set(lic):
            raise KeyingError(f"{where}: orthographic_bases[{m!r}] names bases "
                              f"{sorted(set(bases) - set(lic))} the mark is not licensed on")
    # A text's own rulings, each attested. Deletions are recorded in `origin` too.
    # **Only over a prototype**: a text with no workspace layer under it is its own
    # base, and its leaves override nothing, so there is nothing to attest.
    over = any(t.startswith("workspace") for t in origin.values())
    ruled = sorted(".".join(p) for p, tier in origin.items()
                   if over and tier.startswith("text"))
    unattested = [p for p in ruled if not str(why.get(p, "")).strip()]
    if unattested:
        raise KeyingError(f"{where}: the text overrides {unattested} with no `_why` — a "
                          "text's ruling carries its attestation")
    stray = sorted(set(why) - set(ruled))
    if stray:
        raise KeyingError(f"{where}: `_why` names {stray}, which the text does not set")


def _stamp(root: Path) -> tuple:
    ws = workspace_root(root)
    ps = [Path(root) / CONFIG] + ([ws / CONFIG] if ws else [])
    return tuple((str(p), os.stat(p).st_mtime_ns if p.exists() else 0) for p in ps)


def rules(root: Path) -> Rules:
    """The effective keying rules for the text at `root`. Cached per file state."""
    root = Path(root).resolve()
    return _rules(str(root), _stamp(root), True)


def workspace_rules(root: Path) -> Rules:
    """What the workspace of the text at `root` says alone, its text's layer
    left out — the rules a store every text shares is held to."""
    root = Path(root).resolve()
    return _rules(str(root), _stamp(root), False)


def rules_for(path: Path, root: Path) -> Rules:
    """The rules a file is judged by: its text's if it lives under the text,
    else its workspace's. `corpus normalize` reaches `../edition/entities/`
    from a text, and a file every text reads cannot take one text's rulings."""
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return workspace_rules(root)
    return rules(root)


@lru_cache(maxsize=32)
def _rules(root: str, _stamp: tuple, own: bool) -> Rules:
    try:
        merged, origin, why = layered(Path(root), CONFIG, own=own)
    except LayerError as e:
        raise KeyingError(str(e)) from None
    if not merged:
        raise KeyingError(f"no {CONFIG} at {root} or its workspace: a text is keyed "
                          "against rules that are written down, never against none")
    _check(merged, origin, why, root)
    return Rules(
        inventory=frozenset(merged["inventory"]),
        lookalikes=frozenset(merged["lookalikes"]),
        tier1_traps=dict(merged["tier1_traps"]),
        lookalike_chars=dict(merged["lookalike_chars"]),
        lookalike_seqs=dict(merged["lookalike_seqs"]),
        lookalike_greps=dict(merged["lookalike_greps"]),
        lookalike_seq_greps=dict(merged["lookalike_seq_greps"]),
        mark_license={m: frozenset(b) for m, b in merged["mark_license"].items()},
        orthographic_bases={m: "".join(b) for m, b in merged["orthographic_bases"].items()},
        detectors=frozenset(merged["detectors"]),
        tier2_scripts=frozenset(merged["tier2_scripts"]),
        prose_alphabet={k: frozenset(v) for k, v in merged["prose_alphabet"].items()},
        folds=dict(merged["folds"]),
        script_folds={k: {"pairs": dict(v["pairs"]), "keep": v["keep"]}
                      for k, v in merged["script_folds"].items()},
        numeral_folds=dict(merged["numeral_folds"]),
        origin=dict(origin),
    )


def _spell(k: str) -> str:
    """A key as a report can show it: the glyph, then its codepoints, since a
    combining mark alone is invisible and two lookalikes print the same. A name
    (a detector, a script code) is shown as itself."""
    if k.isascii() and k.isidentifier():
        return k
    return f"{k} ({' '.join(f'U+{ord(c):04X}' for c in k)})"


def table_rows(root: Path) -> list[dict]:
    """One row per effective entry, the tier that set it, and a ruling's
    attestation — `corpus rules`. A deletion appears as its own row, since what a
    text removed is as much its ruling as what it added."""
    root = Path(root).resolve()
    rules(root)  # composes and checks: a malformed layer raises before it is shown
    merged, origin, why = layered(root, CONFIG)
    rows = []
    for path, tier in origin.items():
        node = merged
        for k in path:
            node = node.get(k) if isinstance(node, dict) else None
        rows.append({"table": path[0],
                     "entry": " on ".join(_spell(k) for k in reversed(path[1:])),
                     "value": "" if node is None else str(node),
                     "tier": tier, "why": why.get(".".join(path), "")})
    return rows


__all__ = ["CONFIG", "DELETE", "DETECTORS", "SCRIPTS", "in_script", "KeyingError", "Rules", "TABLES", "rules", "rules_for",
           "table_rows", "workspace_rules"]
