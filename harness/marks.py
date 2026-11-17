"""Is this batch's character distribution plausible — before a human opens it.

`dispatch.md` has long told the coordinator to run `harness lexicon marks` and
compare a batch against it by eye, calling it "the only check in the loop that
needs neither a raster nor a reader's cooperation… the one that would have caught
the most". This is that comparison computed. `lexicon marks` cannot be scoped to a
page at all, and it groups by base letter, so it cannot express `ɪ`/`i` — which is
not a mark on a base — at any scope.

**Four arms, and they are not equally strong.** Read them in this order:

`rare` is deterministic and needs no statistics. Bare `g` is 2.8% of Tier-1 `g` —
14 occurrences on 13 pages in the whole store — so a page setting four of them is
visible by listing. Only a contrast whose confusable is *corpus-rare* can reach
this arm, and which those are is derived from the prior at run time rather than
declared, so it moves as the store grows.

`conflict` is deterministic too, and sharper than its size suggests: over the
store only 7 of 1488 folded forms carry more than one spelling — 25 rows on 22
pages — and 4 of those folds are live `i`/`ɪ` inconsistencies inside adjudicated
ground truth.

`ratio` points and never decides, because the marks are lexical rather than
independent. `2-036` is the standing illustration: 6 Tier-1 records over 3 types,
`Pehiˊttin` four of them, so any per-character ratio on that page is one word
rather than six draws. So the arm counts **types**, and reports a rank against
the observed per-page range rather than a p-value, which would assert an
independence model this data refutes. (A per-character binomial flagged 19
page-base cells over the 29 pages adjudicated by 2026-08-02 — the measurement
that settled the design. It has not been re-run at 476 pages, and the figure is
kept as the dated evidence it is rather than restated as if it were current.)

`traps` is the odd one, and the only arm that does not select Tier-1 tokens
first. The other three judge a population; this one asks who *left* it. A form
keyed with a glyph outside the inventory — `Ke’rek` for `Keˊrek`, `Ta’lo` for
`Taˊlo` — carries no inventory member, so it is never selected, so the page
reports `tokens: 0, types: 0` and all three fall silent on a reading that is
wholly wrong. That is not a weak signal, it is the absence of one, and it is
indistinguishable from a page of honest English prose. So `traps` runs over every
token, folds `detectors.TIER1_TRAPS`, and asks whether the store already holds the
result. It needs no knowledge of the notation, only of what has been ratified
before, and it turns the wrong glyph from the thing that hides a page into the
thing that names it. `3-024` and `3-199` are the two pages that motivated it,
two hundred apart with a written post-mortem between them, neither findable.

**Why it takes several refs.** Most pages of this book carry only a handful of
Tier-1 terms, so one page is rarely a sample worth a verdict. Pooling the refs a
coordinator passes — its subagents' returned proposals — gives a body of native
text large enough to hold against the ground-truth corpus, and the contrast
between the individual jobs and their pool is the reading: one job adrift is that
reader on that page, where *every* job leaning the same way is systemic, and
points at the prompt or the keying spec rather than at anyone's reading.

**Everything here is measurement and exits 0.** An outlier is a page to re-read,
never a page to correct by ratio.

Two properties of the prior a reader must carry:

- **It is leave-one-out, unconditionally.** After `restore`, a page's ground truth
  *is* the adjudicated descendant of its own proposal, so a prior containing the
  page under test compares a proposal against its own output. That is the
  two-witnesses-that-are-one failure in a fourth place, after the verbatim
  firewall, `review`'s span diff and `train score zones`'s `unseen` row. Excluding
  conditionally — only when the page is present — is the same thing with a step
  where it can be forgotten.
- **It is no longer drawn from density-selected pages, and that strengthened the
  argument rather than weakening it.** When this was written `gt/ocr/` held 29
  Tier-1-carrying pages chosen for density: median 13 types, range 2 to 56, 7 of
  29 carrying fewer than 5. It now holds **476**: median **3** types, range 1 to
  56, and **337 of 476 carry fewer than 5**. The maximum did not move — the
  densest pages were already in — so what arrived is the ordinary body of the
  book, which is what the earlier note predicted the rest of the corpus would
  look like.

  The consequence is that the `ratio` arm is now silent on the **majority** of
  pages rather than a quarter of them. That is the correct output for n=3, and it
  makes a batch rather than a page the pooling unit by necessity rather than by
  preference.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Collection
from dataclasses import dataclass
from dataclasses import field as dc_field
from functools import lru_cache
from pathlib import Path

from . import keying
from .detectors import (
    EDGE_PUNCT,
    TOKEN,
    bears_inventory,
    native_corpus,
    native_corpus_lines,
    tier2,
)
from .keying import Rules
from .refs import norm_ref

CONFIG = "config/marks.json"


class MarksConfigError(ValueError):
    """A malformed config, raised at load rather than met halfway through a run.

    Same posture as `zones_config.ConfigError`: a contrast silently dropped for a
    missing field would make the arm that needed it quietly report nothing, which
    is indistinguishable from a clean batch.
    """


def config_path(root: Path = Path(".")) -> Path:
    return root / CONFIG


def load_config(root: Path = Path(".")) -> dict:
    """Read and check `config/marks.json`.

    Declares *what to compare and how hard*, and never the priors — those come
    from `gt/ocr/` at run time so the check recalibrates as the store grows
    instead of carrying a number that goes stale unnoticed.

    `expected` is checked to be NFD because the corpus is (`keying_spec.md` §1) and
    a precomposed entry would silently match nothing: `g̣` hand-typed as U+1E21
    never occurs in a store that has been through `corpus normalize`.
    """
    p = config_path(root)
    if not p.exists():
        raise MarksConfigError(f"no marks config at {p} — expected {CONFIG}")
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MarksConfigError(f"{p}: {e}") from e

    contrasts = cfg.get("contrasts")
    # **Empty only when the file says why.** A silently empty list would make every
    # arm that needs a contrast report nothing, indistinguishable from a clean
    # batch; a notation nobody has measured a contrast for yet (the 1900
    # *Materials*, with no ground truth to measure on) declares that in `_none`.
    none = cfg.get("_none")
    if not isinstance(contrasts, list) or not (
            contrasts or (isinstance(none, str) and none.strip())):
        raise MarksConfigError(f"{p}: 'contrasts' must be a non-empty list, or "
                               "empty with `_none` saying why")
    seen = set()
    for c in contrasts:
        for field in ("name", "expected", "confusable", "position"):
            if not c.get(field):
                raise MarksConfigError(f"{p}: a contrast is missing '{field}': {c!r}")
        if c["name"] in seen:
            raise MarksConfigError(f"{p}: duplicate contrast name {c['name']!r}")
        seen.add(c["name"])
        if c["position"] not in ("any", "initial"):
            raise MarksConfigError(
                f"{p}: position of {c['name']!r} must be 'any' or 'initial', "
                f"not {c['position']!r}")
        if unicodedata.normalize("NFD", c["expected"]) != c["expected"]:
            raise MarksConfigError(
                f"{p}: expected of {c['name']!r} is not NFD — the corpus is "
                "(keying_spec §1), so a precomposed entry would match nothing")
        if len(c["confusable"]) != 1:
            raise MarksConfigError(
                f"{p}: confusable of {c['name']!r} must be one character")
    for field, kind in (("rare_max_pct", float), ("min_types", int)):
        v = cfg.get(field)
        if not isinstance(v, kind) or isinstance(v, bool) or v <= 0:
            raise MarksConfigError(f"{p}: '{field}' must be a positive {kind.__name__}")
    sb = cfg.get("stem_boundary")
    if sb is not None and not (isinstance(sb, str) and len(sb) == 1):
        raise MarksConfigError(f"{p}: 'stem_boundary' is one character, or absent")
    return cfg


def stem(token: str, root: Path = Path(".")) -> str:
    """`token` without the prose ending its text's `stem_boundary` marks off.

    The 1900 *Materials* print `’` between a native stem and its Russian case
    ending (`Ајӈан̀ва́т’омъ`, `Ајӈан̀ва́т’а`), so one word would otherwise be as many
    forms as it has cases. The stem is what is native, and what the lexicon keys.

    **Only a prose ending is cut**: everything after the boundary must be letters of
    the text's prose alphabet, so a boundary inside a native form, or one followed
    by notation, leaves the token whole. A text with no `stem_boundary` (*The
    Chukchee*) gets its token back untouched, and so does a token with none. The
    one function every reader of a native form goes through: the corpus walk, a
    proposal's `native` list, the near-miss check and the review statuses.
    """
    return stemmer(root)(token)


def stemmer(root: Path = Path(".")) -> Callable[[str], str]:
    """`stem`, with the text's boundary and prose alphabet read once, for a caller
    stemming every token of a corpus."""
    try:
        sb = load_config(root).get("stem_boundary")
    except MarksConfigError:
        sb = None
    if not sb:
        return lambda token: token
    letters = frozenset().union(*keying.rules(root).prose_alphabet.values())

    def cut(token: str) -> str:
        if sb not in token:
            return token
        head, _, tail = token.rpartition(sb)
        base = "".join(c for c in tail if not unicodedata.category(c).startswith("M"))
        return head if head and base and all(c in letters for c in base) else token
    return cut


EXEMPT = "config/marks_exempt.json"


def exempt_path(root: Path = Path(".")) -> Path:
    return root / EXEMPT


def load_exemptions(root: Path = Path(".")) -> list[dict]:
    """Folds a human has ruled the book's own inconsistency, scoped to pages.

    A conflict is "one word, two spellings", and the book sets some words two ways
    — `2-030`'s `neˊlyiᵋ`/`neˊlyɪᵋ` was read against the raster and both keyings
    found faithful (139135f). Without somewhere to record that, the ruling lives in
    a commit message and the verb re-reports it forever, which is how a standing
    finding buries a new one.

    **Scoped to a fold *and* the refs it was ruled on**, never a fold alone. The
    same word mis-keyed on a page nobody has examined is exactly the finding this
    arm exists for, and a fold-wide entry would silence it — the reasoning behind
    `gt/zones/_ink_exempt.json` being scoped to a band rather than to a page.

    **`note` is required and is the record.** Without one, "the tool complained and
    I made it stop" is indistinguishable from a ruling, and the exemption file is
    precisely where a wrong call would hide.

    Absent file is no exemptions — the ordinary state, not an error.
    """
    p = exempt_path(root)
    if not p.exists():
        return []
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MarksConfigError(f"{p}: {e}") from e
    if not isinstance(doc, list):
        raise MarksConfigError(f"{p}: must be a list of "
                               "{fold, refs, note} entries")
    out = []
    for e in doc:
        if not isinstance(e, dict):
            raise MarksConfigError(f"{p}: entry is not an object: {e!r}")
        for field in ("fold", "refs", "note"):
            if not e.get(field):
                raise MarksConfigError(
                    f"{p}: an entry is missing '{field}': {e!r}"
                    + ("  — the reason is the record, and an entry without one "
                       "cannot be told from a silenced complaint"
                       if field == "note" else ""))
        if not isinstance(e["refs"], list):
            raise MarksConfigError(f"{p}: 'refs' must be a list: {e!r}")
        out.append({"fold": _nfd(e["fold"]),
                    "refs": {norm_ref(r) for r in e["refs"]},
                    "note": e["note"]})
    return out


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def is_medial(token: str, i: int, rules: Rules) -> bool:
    """Is position `i` word-medial — preceded by a letter or a mark?

    **Generalises `detectors.MEDIAL_CAPS` rather than competing with it**, and
    agrees with it exactly: over all 65 ASCII A/E/I/L positions in the store the
    two never disagree (`test_proposal_marks.py` pins it). MEDIAL_CAPS is a regex
    over `[AEIL]` alone; the small caps `ɪ ᴇ ᴀ ʟ` need the same predicate on the
    other side of each contrast, and a second lookbehind class copied by hand is
    the sort of near-duplicate this project holds apart deliberately.

    Why it matters: **position decides whether a case is contentious at all.**
    Word-medially an ASCII cap is essentially never right — 2 in the store against
    509 medial small caps — and MEDIAL_CAPS already says so with a sharper claim
    than any share could. Word-initially both are ordinary: 63 ASCII caps
    (`Alaˊyon`, `Ilhiˊnin`, `Luˊᵋren`) against 55 small caps
    (`ɪnp-luˊwleñ-yiˊᵋlhɪn`, `ᴇnmɪtaˊhɪn`), and frequency evidence is the only
    handle there is.

    **A hyphen inside a Tier-1 token is word-internal**, so an element-initial
    capital in such a compound is medial. This paragraph used to say the
    opposite — that a hyphen is not a letter, so the element read as initial —
    and `Hɪtoˊ-Lap` (2-040, 2-058) is what that cost: nothing flagged it, and
    the initial reading routed it to `smallcap-l`, whose prior of 7 ASCII `L`
    against 0 `ʟ` then endorsed the capital. The gate is the token, not the
    character: in ordinary English a hyphen *does* join two words
    (`Baffin-Land`), and only the inventory glyph tells the two cases apart.
    `detectors.HYPHEN_MEDIAL_CAPS` carries the measurement.
    """
    if i <= 0:
        return False
    prev = token[i - 1]
    if prev.isalpha() or unicodedata.combining(prev) != 0:
        return True
    return prev == "-" and any(c in rules.inventory for c in token)


def _find(token: str, needle: str, position: str, rules: Rules) -> list[int]:
    """Indices where `needle` occurs, filtered by the contrast's position scope."""
    out, start = [], 0
    while (i := token.find(needle, start)) != -1:
        if position == "any" or not is_medial(token, i, rules):
            out.append(i)
        start = i + 1
    return out


def sites(token: str, c: dict, rules: Rules) -> tuple[list[int], list[int]]:
    """(expected sites, *bare* confusable sites) for one contrast in one token.

    The second list is the load-bearing one, and getting it wrong is silent. Where
    the expected form is the confusable plus a mark — `g̣` is `g` + U+0323 — every
    dotted `g` also contains a bare `g`, so a naive count of the confusable counts
    the whole axis and the share collapses toward 50%: measured, `g-dot` read 48.4%
    against the corpus's true 93.9%, which put it above `rare_max_pct` and switched
    the `rare` arm off entirely for the one contrast it was written for. A wrong
    number in a plausible range, disabling a check, with nothing to say so.

    So a confusable site is only bare when it is not the head of an expected match.
    Contrasts whose two sides are disjoint (`ɪ`/`i`) are unaffected by the
    subtraction, which is why it is done here once rather than per contrast kind.
    """
    exp = _find(token, c["expected"], c["position"], rules)
    covered = set(exp) if c["expected"].startswith(c["confusable"]) else set()
    conf = [i for i in _find(token, c["confusable"], c["position"], rules) if i not in covered]
    return exp, conf


def fold(token: str, contrasts: list[dict]) -> str:
    """Collapse every contrast axis, then casefold — the `conflict` bucket key.

    Two spellings of one word land in one bucket; whether they are *a conflict* is
    then decided by comparing the casefolded spellings inside it, which is a
    separate question and the fiddly one:

        neˊlyiᵋ / neˊlyɪᵋ    -> bucket neˊlyiᵋ; casefolds differ  -> conflict
        äˊmmê  / Äˊmmê      -> bucket äˊmmê;  casefolds equal    -> suppressed
        Iᵋplɪˊlɪ / ɪᵋplɪˊlɪ  -> bucket iᵋpliˊli; casefolds differ -> conflict

    The third case is why the suppression is safe. `casefold("I") == "i"` while
    `casefold("ɪ") == "ɪ"` — U+026A has no case mapping at all — so collapsing case
    hides a genuine capitalization difference and never hides `I`/`ɪ`, which the
    corrections census records twice on `1-101` (`Iᵋplɪˊlɪ`). Both are word-initial,
    which is exactly why `MEDIAL_CAPS` was blind to them.

    Longest `expected` first, so `g` + U+0323 is collapsed as a unit before any
    single-character axis can strand its combining mark.
    """
    t = token
    for c in sorted(contrasts, key=lambda c: -len(c["expected"])):
        t = t.replace(c["expected"], c["confusable"])
    return t.casefold()


#: The key table, a text's or else its workspace's, read whole (`layout.shared`).
HANDLE = "config/handle.json"

#: An injective table's grammar (`docs/multitext.md`, the key table). A letter token
#: is an ASCII letter, or one followed by `_` and at most one digit; a mark token is
#: one of these characters. The two sets and the passthrough are disjoint, which is
#: what makes a key parse one way only.
MARK_TOKENS = "'.:~)=^*+"
_LETTER_TOKEN = re.compile(r"[A-Za-z](?:_[0-9]?)?")


@dataclass(frozen=True)
class HandleTable:
    """How a text's native forms are addressed in ASCII: `{codepoint: token}`.

    `passthrough` is the characters that stand for themselves: `"ascii"` for every
    ASCII character, which no injective table may claim, else an explicit string —
    *The Chukchee*'s ASCII letters, hyphen and `!`, whose bases are ASCII after NFD;
    the *Materials*' hyphen and digits, which mark their Latin letters so a Latin
    `l` and a Cyrillic `л` never share a key. `inverse` is filled only for an
    injective table, and is derived from `tokens`, never written by hand.
    """

    tokens: dict[str, str]
    passthrough: str
    injective: bool
    path: str = ""
    inverse: dict[str, str] = dc_field(default_factory=dict)
    #: `{letter: its class's representative}`, casefolded, for the near-miss
    #: reduction (`reduction`). Empty for a table that declares no `reduce`.
    classes: dict[str, str] = dc_field(default_factory=dict)
    reduces: bool = False
    #: Letters a layer has been seen to drop outright, casefolded (`reduce`'s
    #: `dropped`). A confusion class cannot merge a letter that is not there, so
    #: `dropped_reduction` takes these out of a ratified form instead.
    dropped: frozenset[str] = frozenset()

    def passes(self, ch: str) -> bool:
        return ch.isascii() if self.passthrough == "ascii" else ch in self.passthrough


class HandleTableError(ValueError):
    """A key table that cannot be read, or claims an injectivity it lacks."""


def _check_injective(tokens: dict[str, str], passthrough: str, where: str,
                     own_inventory: frozenset[str]) -> dict[str, str]:
    """The checks an injective table must pass; returns the inverse.

    Each entry is one token of the grammar, no two codepoints share a token, a cased
    letter and its case pair key to the same token in the other case, and every
    letter of the text's own inventory has a token. Together these make
    `handle_key` one-to-one and `form_from_key` its exact inverse.

    **The passthrough may hold what no token can begin or end with.** An ASCII
    letter may stand for itself only when no token is that bare letter — so
    *The Chukchee*'s letters pass, every token of theirs carrying a `_` or being a
    mark, and the *Materials*' cannot, `а` being `a`. A digit may stand for itself
    only when no token ends in a bare `_`, or `ɪ` then `1` would read as `i_1`.

    **A combining mark takes a mark token; anything else may take either.** The
    kind is the token's, not the codepoint's category: `ˊ` U+02CA and `ᵋ` U+1D4B
    are both modifier letters, and one is a stress mark and the other a vowel.
    """
    if passthrough == "ascii":
        raise HandleTableError(f"{where}: an injective table cannot pass every ASCII "
                               "character through: a marker would then share its "
                               "key with the character it is spelled with")
    bare = {tok for tok in tokens.values() if len(tok) == 1 and tok.isalpha()}
    trailing = any(tok.endswith("_") for tok in tokens.values())
    bad = [c for c in passthrough
           if c == "_" or c in MARK_TOKENS or not c.isascii()
           or (c.isalpha() and c in bare) or (c.isdigit() and trailing)]
    if bad:
        raise HandleTableError(f"{where}: passthrough holds {bad}, which the token "
                               "grammar uses or cannot spell")
    inverse: dict[str, str] = {}
    for ch, tok in tokens.items():
        is_mark_tok = len(tok) == 1 and tok in MARK_TOKENS
        combining = unicodedata.category(ch).startswith("M")
        ok = is_mark_tok if combining \
            else (is_mark_tok or bool(_LETTER_TOKEN.fullmatch(tok)))
        if not ok:
            kind = "a mark token" if combining else "a letter or mark token"
            raise HandleTableError(f"{where}: U+{ord(ch):04X} keys to {tok!r}, which "
                                   f"is not {kind} of the grammar")
        if tok in inverse:
            raise HandleTableError(
                f"{where}: U+{ord(inverse[tok]):04X} and U+{ord(ch):04X} both key to "
                f"{tok!r}; an injective table names each codepoint once")
        inverse[tok] = ch
    for ch, tok in tokens.items():
        for other in {ch.upper(), ch.lower()} - {ch}:
            if len(other) != 1 or other not in tokens:
                continue
            want = tok[0].upper() + tok[1:] if other == ch.upper() \
                else tok[0].lower() + tok[1:]
            if tokens[other] != want:
                raise HandleTableError(
                    f"{where}: {ch!r} keys to {tok!r} but its case pair {other!r} to "
                    f"{tokens[other]!r}; a case pair differs in the token's case alone")
    missing = sorted(c for c in own_inventory if c not in tokens)
    if missing:
        raise HandleTableError(f"{where}: the text's inventory holds "
                               f"{[f'U+{ord(c):04X}' for c in missing]} with no token")
    return inverse


def handle_table(root: Path = Path(".")) -> HandleTable:
    """The key table for the text at `root`. Cached per file state."""
    from .layout import shared
    p = shared(Path(root), HANDLE)
    if not p.exists():
        raise HandleTableError(f"no {HANDLE} at {root} or its workspace: a form is "
                               "addressed by a declared table, never a default")
    own = _own_inventory(Path(root).resolve())
    return _handle_table(str(p), p.stat().st_mtime_ns, own)


def _own_inventory(root: Path) -> frozenset[str]:
    """The inventory members this text's own keying layer adds, not its workspace's."""
    rules = keying.rules(root)
    return frozenset(p[1] for p, tier in rules.origin.items()
                     if p[0] == "inventory" and tier.startswith("text"))


@lru_cache(maxsize=16)
def _handle_table(path: str, _mtime: int, own_inventory: frozenset[str]) -> HandleTable:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HandleTableError(f"{path}: not JSON: {e}") from None
    tokens = doc.get("tokens")
    if not isinstance(tokens, dict) or not tokens:
        raise HandleTableError(f"{path}: no `tokens`")
    for ch, tok in tokens.items():
        if len(ch) != 1 or not (isinstance(tok, str) and tok and tok.isascii()):
            raise HandleTableError(f"{path}: tokens[{ch!r}] = {tok!r}; a token maps one "
                                   "codepoint to a non-empty ASCII string")
    passthrough = doc.get("passthrough")
    if not isinstance(passthrough, str):
        raise HandleTableError(f"{path}: `passthrough` is \"ascii\" or the characters "
                               "that stand for themselves")
    injective = doc.get("injective")
    if not isinstance(injective, bool):
        raise HandleTableError(f"{path}: `injective` must be stated, true or false")
    inverse = (_check_injective(tokens, passthrough, path, own_inventory)
               if injective else {})
    classes = _reduce_classes(doc.get("reduce"), path)
    return HandleTable(tokens=dict(tokens), passthrough=passthrough,
                       injective=injective, path=path, inverse=inverse,
                       classes=classes, reduces=doc.get("reduce") is not None,
                       dropped=_dropped(doc.get("reduce"), path))


def _dropped(spec, path: str) -> frozenset[str]:
    """`reduce.dropped`: `[{letters, why}]`, each letter one a layer omits."""
    groups = spec.get("dropped") if isinstance(spec, dict) else None
    if groups is None:
        return frozenset()
    if not isinstance(groups, list):
        raise HandleTableError(f"{path}: `reduce.dropped` is a list")
    out: set[str] = set()
    for g in groups:
        letters = g.get("letters") if isinstance(g, dict) else None
        if not (isinstance(letters, str) and letters and str(g.get("why", "")).strip()):
            raise HandleTableError(f"{path}: a dropped entry is `letters` and a "
                                   "`why`, its attestation")
        out.update(unicodedata.normalize("NFD", c).casefold() for c in letters)
    return frozenset(out)


def _reduce_classes(spec, path: str) -> dict[str, str]:
    """The confusion classes, closed transitively: `{letter: representative}`.

    Each class names letters a reader or a layer has been seen to confuse, with its
    attestation. Two classes sharing a letter are one class (`ł` is in the tall-`l`
    class and the barred-`l` one), so the closure is computed here rather than left
    to whoever writes the file to notice.

    A member is one codepoint after NFD, or a letter with one mark that is a letter
    of its own (`й`, `и` + breve, beside `ј`): `reduction` drops marks, so without
    the sequence `й` would reduce to `и`, and a class on `и` would merge a letter
    nobody confuses with `ј`.
    """
    if spec is None:
        return {}
    groups = spec.get("classes") if isinstance(spec, dict) else None
    if not isinstance(groups, list) or not groups:
        raise HandleTableError(f"{path}: `reduce` holds `classes`, a non-empty list")
    parent: dict[str, str] = {}

    def find(c: str) -> str:
        while parent.setdefault(c, c) != c:
            c = parent[c]
        return c
    for g in groups:
        letters = g.get("letters") if isinstance(g, dict) else None
        if not (isinstance(letters, str) and len(letters) >= 2
                and str(g.get("why", "")).strip()):
            raise HandleTableError(f"{path}: a reduce class is `letters` (two or "
                                   "more) and a `why`, its attestation")
        norm: list[str] = []
        for c in unicodedata.normalize("NFD", letters).casefold():
            if _is_mark(c) and norm and len(norm[-1]) == 1 and not _is_mark(norm[-1]):
                norm[-1] += c
            else:
                norm.append(c)
        if any(_is_mark(c[0]) or len(c) > 2 for c in norm) or len(norm) < 2:
            raise HandleTableError(f"{path}: reduce class {letters!r} holds a letter "
                                   "that is not one codepoint, or one letter and "
                                   "one mark, after NFD")
        for c in norm[1:]:
            parent[find(c)] = find(norm[0])
    return {c: min(d for d in parent if find(d) == find(c)) for c in parent}


def _is_mark(c: str) -> bool:
    return unicodedata.category(c).startswith("M")


def reduction(form: str, table: HandleTable) -> str:
    """`form` as the near-miss check compares it: casefolded, every combining mark
    dropped, every letter mapped to its confusion class.

    **Independent of the key's spelling.** The key's letters follow sound, and say
    nothing about what a reader confuses; dropping the `_N` of a token would put
    `с`, `ш` and `щ` together, which no reader confuses. So the classes are
    declared, each with what attests it, and the accents are dropped because an
    accent dropped is the commonest slip there is. A class member that is a letter
    and a mark (`й`) is matched before its mark is dropped.
    """
    out = []
    s = unicodedata.normalize("NFD", form).casefold()
    for i, c in enumerate(s):
        if _is_mark(c):
            continue
        j, rep = i + 1, None
        while j < len(s) and _is_mark(s[j]):
            if (rep := table.classes.get(c + s[j])) is not None:
                break
            j += 1
        out.append(rep if rep is not None else table.classes.get(c, c))
    return "".join(out)


def dropped_reduction(form: str, table: HandleTable) -> str:
    """`reduction(form)` with every `table.dropped` letter taken out first: what a
    layer that dropped them reads, reduced. Applied to the *ratified* side only,
    so a query is compared against the form as a layer would have lost it, and a
    letter the query does have is never removed from it. `""` for a form holding
    none of them, which then has no dropped variant to match."""
    nfd = unicodedata.normalize("NFD", form)
    if not table.dropped or not any(c.casefold() in table.dropped for c in nfd):
        return ""
    return reduction("".join(c for c in nfd if c.casefold() not in table.dropped),
                     table)


def form_from_key(key: str, table: HandleTable) -> str:
    """The form an injective table's key spells: `handle_key`'s exact inverse.

    **For validation, never for expanding a reader's handle.** `lookup.expand`
    resolves a key only against ratified forms; decoding one here proves nothing
    about the corpus, and a reader who could expand any key would type unratified
    glyphs under the CORPUS badge. Refuses a token the table does not hold, a `_`
    after no letter, and any table that is not injective.
    """
    if not table.injective:
        raise HandleTableError(f"{table.path}: not injective, so a key has no single "
                               "form to decode to")
    out, i = [], 0
    while i < len(key):
        c = key[i]
        if "a" <= c.lower() <= "z":
            if key[i + 1:i + 2] == "_":
                tok = key[i:i + 3] if key[i + 2:i + 3].isdigit() else key[i:i + 2]
            elif c not in table.inverse and table.passes(c):
                out.append(c)
                i += 1
                continue
            else:
                tok = c
        elif c in MARK_TOKENS:
            tok = c
        elif table.passes(c):
            out.append(c)
            i += 1
            continue
        else:
            raise ValueError(f"{key!r}: {c!r} at {i} is no token of {table.path}")
        if tok not in table.inverse:
            raise ValueError(f"{key!r}: {tok!r} names no character in {table.path}")
        out.append(table.inverse[tok])
        i += len(tok)
    return "".join(out)


def handle_key(token: str, table: HandleTable) -> str:
    """The typed handle for one form: the passthrough as itself, the rest marked.

    **A plain-ASCII key would teach the reader the wrong glyph.** `fold` collapses
    exactly the axes this pass gets wrong most often — dropped U+0323 is the largest
    single correction class in the store, and `i`/`ɪ`/`I` the largest family — so a
    key spelled `kavralit` asserts an `i` that is not there, to a reader who will
    key it from memory on a later page. Every non-ASCII character therefore leaves a
    visible marker, and the key cannot be read back as a spelling.

        Kuluˊči            -> kulu'c^i
        Kavraˊlɪt          -> kavra'li_t
        Notaˊs˙qa-vaˊɪrg̣ɪn -> nota's*qa-va'i_rg.i_n

    **This is not `fold` and must not be**: marking a collapse distinguishes it,
    and the bucket exists to *not* distinguish — `Čeˊwɪn` and `Čeˊwin` are one word
    there and two keys here. So the ambiguity refusal lives on the bucket, and a
    precise key pointing into a contested one is refused all the same. Without that
    split, a reader could name a side of a live conflict by spelling it exactly.

    U+002D passes through as itself: 147 of the 499 attested forms carry a hyphen,
    so stripping it would merge forms the book distinguishes. U+0027 does not: it
    has no use in Tier-1 (`keying_spec.md` §3 lists it as a trap for U+02CA), and
    in a key `'` *is* the stress marker, so a form carrying one is unkeyable rather
    than silently keyed as the stressed form it imitates.

    **Case passes through too, and lowercasing was tried first.** It collided on 11
    of the 499 — `Aiˊwan`/`aiˊwan`, `Kavraˊlɪt`/`kavraˊlɪt`, and nine more, every
    one a word attested both sentence-initially and mid-sentence. Case is not a
    glyph identity a reader has to guess at: it is legible at any zoom, unlike the
    dot-below this key exists to stop asserting, so the reader types the case it
    sees and the collision disappears. `fold` still casefolds, so the two remain one
    bucket and a genuine `I`/`ɪ` disagreement — which casefolding cannot hide, U+026A
    having no case mapping — is still caught there.

    Raises on a character the table does not reach, rather than dropping it.
    A silent pass-through is how a new inventory glyph would start producing keys
    that read as spellings, which is the one thing this function exists to prevent.
    """
    out = []
    for ch in unicodedata.normalize("NFD", token):
        if ch in table.tokens:
            out.append(table.tokens[ch])
        elif table.passes(ch):
            out.append(ch)
        else:
            raise ValueError(
                f"no handle marker for U+{ord(ch):04X} in {token!r} — add it to "
                f"{table.path or HANDLE} beside the inventory member it belongs to")
    return "".join(out)


def trap_hits(path: Path, known: dict[str, list[str]], rules: Rules) -> list[dict]:
    """Tokens keyed with a trap glyph that become a known native form once folded.

    **The arm that looks where the others cannot.** Every other check here selects
    Tier-1 tokens and then judges them, so a form keyed with a glyph *outside* the
    inventory is not selected at all and the page falls silent — `tokens: 0, types:
    0`, identical to a page of plain English. That is how `3-024`'s `Ta’lo` and
    `3-199`'s `Ke’rek` both survived: the wrong glyph was not a bad reading the
    arms could weigh, it was an exit from their population.

    So this one runs over *every* token, not the native ones, and asks the inverse
    question. Fold `detectors.TIER1_TRAPS` and see whether the result is a form the
    store already holds. `Ke’rek` folds to `Keˊrek`, attested ten times, and the
    row writes itself — no knowledge of Chukchee required, only of what the corpus
    has ratified before.

    `known` is `{casefolded native form: [refs]}`, built once per run by the caller
    rather than per page: the corpus walk is the expensive part and it does not
    change between refs.

    **Casefolded on both sides, deliberately.** A name is sentence-initial on one
    page and mid-sentence on another, and `Keˊrek`/`keˊrek` are the same form for
    this question — the point is to recognise the word, not to rule on its case.
    Reporting the store's own spelling back keeps the caller able to see both.
    """
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for idx, rec in sorted(doc.get("lines", {}).items(), key=lambda kv: int(kv[0])):
        text = _nfd(rec.get("text", ""))
        for m in TOKEN.finditer(text):
            tok = m.group().strip(EDGE_PUNCT)
            if not tok or not any(c in rules.tier1_traps for c in tok):
                continue
            folded = _nfd("".join(rules.tier1_traps.get(c, c) for c in tok))
            if folded == tok:
                continue
            refs = known.get(folded.casefold())
            if refs:
                out.append({"line": idx, "token": tok, "candidate": folded,
                            "seen": len(refs), "refs": " ".join(sorted(set(refs))[:4])})
    return out


def page_tokens(path: Path, rules: Rules) -> list[tuple[str, str]]:
    """(line index, NFD token) for the Tier-1 tokens in a proposal or decision.

    Selection is `detectors.native_corpus`'s, verbatim — NFD, `TOKEN`,
    `EDGE_PUNCT`, keep iff the token carries an `INVENTORY_CHARS` member — so the
    batch side and the corpus side are the same population and a share between
    them means something.

    It inherits that function's floor with it: a native token carrying no mark at
    all is invisible here by construction. The consequence worth stating is that
    **a reading degraded all the way to ASCII contributes zero tokens and every arm
    goes silent on it**, which is why `marks` reports a `pages` row per ref whether
    or not it found anything.
    """
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for idx, rec in sorted(doc.get("lines", {}).items(), key=lambda kv: int(kv[0])):
        text = _nfd(rec.get("text", ""))
        for m in TOKEN.finditer(text):
            tok = m.group().strip(EDGE_PUNCT)
            # **The same selection as the prior's, and it has to be.** This is
            # the batch half of the comparison `native_corpus_context` supplies
            # the other half of; the two were selected by different rules until
            # now — only the prior excluded Cyrillic — so a Russian token was
            # counted here and not there. See `detectors.bears_inventory`.
            if tok and not tier2(tok, rules) and bears_inventory(tok, rules):
                out.append((idx, tok))
    return out


def _axis_counts(tokens, contrast, rules: Rules) -> tuple[int, int]:
    """(expected occurrences, confusable occurrences) under the position scope."""
    exp = conf = 0
    for tok in tokens:
        e, f = sites(tok, contrast, rules)
        exp += len(e)
        conf += len(f)
    return exp, conf


#: Emitted in every report, so it is the one stale claim here that would have
#: reached a reader. It used to say the prior was "about dense pages, not a
#: population estimate" — a caveat telling the reader to discount it. That was
#: true of 29 density-selected pages with a median of 13 Tier-1 types; the store
#: now holds 476 with a median of 3, so the discount had inverted: the prior is
#: closer to a population estimate than the note admitted, and the note was
#: arguing against its own evidence.
PRIOR_NOTE = ("gt/ocr/ minus the refs under test — 476 pages, median 3 Tier-1 "
              "types. The earliest pages were selected for density and the "
              "densest are still in it (range 1 to 56), so it leans dense at the "
              "top; it is no longer a prior about dense pages only")


def _conflicts(batch: dict, prior: dict, contrasts: list[dict]) -> list[dict]:
    """One word, two spellings — across the batch and the store together.

    **Scoped to folds the batch touches**: at least one variant must come from the
    refs under test. The store carries 4 standing `i`/`ɪ` inconsistencies of its
    own — `keiˊñin`, `kukuˊlpin`, `taˊn˙ñitan` and an exempted `čeˊwin`, over 15
    pages between them; re-reporting them on every batch run would bury
    the batch's own finding, which is the same reason `zones check` merges
    adjacent ink bands rather than reporting 38 rows for one missing region.
    Those 3 are a hand-repair worklist for the adjudicator, not this verb's news.

    `in_batch` separates the two shapes a hit takes: `true` when the batch alone
    carries both spellings (one reader, or two, disagreeing inside the run),
    `false` when the second witness is the store (the batch disagrees with
    adjudicated ground truth). One boolean apart, and different findings.
    """
    # (fold -> form -> ref -> line indices). The lines are the point: a fold row
    # naming only its refs told an adjudicator a word was keyed two ways and left
    # them to grep two pages for it, on a verb whose whole output is a worklist.
    buckets: dict[str, dict[str, dict[str, list[str]]]] = {}
    for ref, toks in batch.items():
        for idx, tok in toks:
            (buckets.setdefault(fold(tok, contrasts), {})
                    .setdefault(tok, {}).setdefault(ref, []).append(idx))
    store: dict[str, dict[str, set[str]]] = {}
    for ref, toks in prior.items():
        for tok in toks:
            store.setdefault(fold(tok, contrasts), {}).setdefault(tok, set()).add(ref)

    out = []
    for key, forms in sorted(buckets.items()):
        store_forms = store.get(key, {})
        # Compared casefolded, so `äˊmmê`/`Äˊmmê` is suppressed while `I`/`ɪ`
        # survives — U+026A has no case mapping, so the two never collide. See
        # `fold`'s docstring for the worked cases.
        spellings = {t.casefold() for t in forms} | {t.casefold() for t in store_forms}
        if len(spellings) < 2:
            continue
        nfc = lambda s: unicodedata.normalize("NFC", s)  # noqa: E731
        rows = []
        for form, refs in sorted(forms.items()):
            for ref, idxs in sorted(refs.items()):
                rows.append({"form": nfc(form), "source": "batch", "ref": ref,
                             "lines": ",".join(sorted(idxs, key=int)),
                             "count": len(idxs)})
        for form, refs in sorted(store_forms.items()):
            for ref in sorted(refs):
                # No line indices on this side, and none invented: the prior comes
                # from `native_corpus`, which yields (ref, token) off the ALTO
                # without carrying the line it sat on. Empty is the honest cell —
                # `harness ocr lines REF` is where that side is looked up.
                rows.append({"form": nfc(form), "source": "store", "ref": ref,
                             "lines": "", "count": 0})
        for r in rows:
            out.append({"fold": nfc(key), **r,
                        "in_batch": len({t.casefold() for t in forms}) > 1})
    return out


def _apply_exemptions(rows: list[dict], exemptions: list[dict]) -> list[dict]:
    """Mark the ruled rows; never drop them.

    Every exemption mechanism in this project reports what it silences — the ink
    bands, the layout rules — because the file recording a judgement is the one
    place a wrong judgement is invisible. So an exempt row keeps its place in the
    table and gains the note that rules it.
    """
    for r in rows:
        for e in exemptions:
            if _nfd(r["fold"]) == e["fold"] and r["ref"] in e["refs"]:
                r["exempt"], r["note"] = True, e["note"]
                break
        else:
            r["exempt"], r["note"] = False, ""
    return rows


def _stale_exemptions(rows: list[dict], exemptions: list[dict],
                      under_test: set[str]) -> list[dict]:
    """Entries that matched nothing on a page this run actually looked at.

    Scoped to `under_test`, because an entry about `2-030` is not stale merely
    because this run was about `2-040` — it was never consulted. Only a ref that
    *was* read and no longer carries the conflict says the ruling has outlived
    what it ruled on.
    """
    hit = {(_nfd(r["fold"]), r["ref"]) for r in rows}
    out = []
    for e in exemptions:
        live = e["refs"] & under_test
        if live and not any((e["fold"], r) in hit for r in live):
            out.append({"fold": unicodedata.normalize("NFC", e["fold"]),
                        "refs": " ".join(sorted(live)), "note": e["note"]})
    return out


def _rare(batch: dict, prior_tokens: list[str], contrasts: list[dict],
          rare_max: float, rules: Rules) -> list[dict]:
    """Occurrences of a form whose confusable the corpus almost never sets.

    **Which contrasts this arm can reach is derived, never declared**: exactly
    those whose confusable sits at or under `rare_max` of its axis. Bare `g` at
    2.8% qualifies; plain `i` at ~40% never can, and need not — `ratio` and
    `conflict` carry that one. The division moves with the store rather than with
    a constant somebody would have to remember to revisit, and it has: `g` was
    6.1% over 29 pages and is 2.8% over 476, still comfortably inside the arm.

    One row per `(ref, form)` carrying a count, because a keyer repeats a slip
    along a page — 13 dropped dots on `2-040`, 14 on `3-004`, then a tail of 1-3.
    Four bare `g` on one page is one finding of weight four, and four rows would
    read as four independent signals.

    `corpus_pct` is *occurrence*-level, unlike `ratio`'s type-level `prior_pct`:
    "how often does the corpus set a bare `g`" is a different question from "how
    many forms carry one".

    **It is computed here and cited nowhere**, which corrects a claim this
    docstring used to make. It said the share "is the figure `keying_spec.md`
    §5.1 publishes" — §5 publishes no figure at all, by policy: it is titled
    *Priors (measured; cite the verb, never a number)* and gives the recomputing
    verb instead, precisely because every share in a mid-rebuild store moves. It
    moved: 6.1% over 29 pages, 2.8% over 476.
    """
    out = []
    for c in contrasts:
        exp_n, conf_n = _axis_counts(prior_tokens, c, rules)
        axis_n = exp_n + conf_n
        if not axis_n:
            continue
        conf_pct = round(100 * conf_n / axis_n, 1)
        if conf_pct > rare_max:
            continue
        for ref, toks in batch.items():
            forms: dict[str, list[str]] = {}
            for line, tok in toks:
                if sites(tok, c, rules)[1]:
                    forms.setdefault(tok, []).append(line)
            for tok, lines in sorted(forms.items()):
                out.append({
                    "ref": ref, "form": unicodedata.normalize("NFC", tok),
                    "count": len(lines), "lines": " ".join(lines),
                    "position": c["position"], "corpus_pct": conf_pct,
                    "corpus_n": axis_n, "spec": c.get("spec", "")})
    return out


def _ratio_rows(c: dict, batch: dict, prior: dict, min_types: int,
                rules: Rules) -> list[dict]:
    """Expected-form share, in **types**, against the leave-one-out prior.

    Types rather than tokens because the marks are lexical, not independent: a
    per-character binomial flagged 19 page-base cells over the 29 pages
    adjudicated when this was measured, and `2-036` is why — 6 Tier-1 records
    over 3 types, `Pehiˊttin` four of them, so its `ɪ`/`i` ratio is one word
    rather than six draws. A type counts once toward each side it contains, so
    `miluteˊmkɪn` is one type on each side of the axis rather than a coin-flip.

    `outside` is a **rank** statement against the band, never a p-value — which
    would assert exactly the independence the data refutes. It reads `?` wherever
    a verdict was not computed, never blank: an uncomputed verdict must not draw
    in the same column as a computed one.

    **`ALL` is the refs the caller passed, pooled — nothing more.** Most pages of
    this book carry only a handful of Tier-1 terms, so one page is rarely a sample
    worth a verdict; pooling a coordinator's returned jobs gives a body of native
    text large enough to hold against the ground-truth corpus. It is emitted only
    when more than one ref was passed, since over a single ref it would restate
    that ref's own row under another name.

    **Read the per-ref rows against `ALL`, and `ALL` against `prior_pct`.** They
    answer different questions. One job adrift while the others sit on the prior
    is that reader, on that page. *Every* job leaning the same way — so that `ALL`
    itself parts from the prior — is systemic, and points at the prompt or the
    keying spec rather than at anyone's reading. That second finding is the one
    nothing else in the loop can see, and it is why the pooled row exists.

    The band is the **per-page** spread over ground-truth pages clearing
    `min_types`, and it is a fixed property of the store: it does not move with
    how many refs were passed. It is the right reference for a per-ref row, and a
    conservative one for `ALL`, since a pooled share is a weighted mean of its
    members and so varies less than any of them — `ALL` falling outside it is a
    strong signal rather than a marginal one. `band_n` says how many pages it was
    drawn from, which is not always many: the `g` axis clears `min_types` on only
    6 pages of the store.

    `prior_pct` is the whole prior pooled, computed by the same type-level rule as
    `expected_pct` so the two columns are in the same unit. (`rare`'s `corpus_pct`
    is deliberately *occurrence*-level — "how often does the corpus set a bare g"
    is a different question. Both are computed from the store; neither is quoted
    from `keying_spec`, which by §5's own title publishes the verb and never the
    number.)
    """
    def share(tokens) -> tuple[int, int]:
        types = set(tokens)
        exp = sum(1 for t in types if sites(t, c, rules)[0])
        conf = sum(1 for t in types if sites(t, c, rules)[1])
        return exp, conf

    def pct(tokens) -> tuple[float, int]:
        e, f = share(tokens)
        n = e + f
        return (round(100 * e / n, 1) if n else 0.0), n

    prior_pct, _ = pct([t for toks in prior.values() for t in toks])
    band = []
    for toks in prior.values():
        p, n = pct(toks)
        if n >= min_types:
            band.append(p)
    lo = round(min(band), 1) if band else 0.0
    hi = round(max(band), 1) if band else 0.0

    scopes = [(ref, [t for _, t in toks]) for ref, toks in batch.items()]
    if len(batch) > 1:
        scopes.append(("ALL", [t for toks in batch.values() for _, t in toks]))

    rows = []
    for scope, tokens in scopes:
        p, n = pct(tokens)
        if scope != "ALL" and n < min_types and len(batch) > 1:
            continue
        outside = "?" if (n < min_types or len(band) < 2) else (
            "low" if p < lo else "high" if p > hi else "")
        rows.append({"scope": scope, "contrast": c["name"],
                     "position": c["position"], "types": n,
                     "expected_pct": p, "prior_pct": prior_pct,
                     "gt_min_pct": lo, "gt_max_pct": hi,
                     "band_n": len(band), "outside": outside})
    return rows


def _source_path(ref: str, root: Path, decisions: bool) -> Path:
    from .paths import decisions_path, proposal_path

    return decisions_path(ref, root) if decisions else proposal_path(ref, root)


def marks(refs: list[str], root: Path = Path("."), decisions: bool = False,
          min_types: int | None = None, rare_max: float | None = None,
          tick: Callable | None = None) -> dict:
    """Character-distribution check over a batch of proposals. Never gates.

    `decisions=True` reads `decision.json` instead — the last state before
    `restore` writes. The pair of runs brackets the adjudication, which on `2-040`
    is the whole story of the page in two commands: the proposal keys `vaˊɪrgɪt`
    against the store's `vaˊɪrg̣ɪt`, and the decision does not.

    See the module docstring for the three arms and for why the prior is
    leave-one-out and density-selected.
    """
    cfg = load_config(root)
    contrasts = cfg["contrasts"]
    rare_max = cfg["rare_max_pct"] if rare_max is None else rare_max
    min_types = cfg["min_types"] if min_types is None else min_types
    rules = keying.rules(root)

    refs = [norm_ref(r) for r in refs]
    under_test = set(refs)

    batch: dict[str, list[tuple[str, str]]] = {}
    pages = []
    for ref in refs:
        p = _source_path(ref, root, decisions)
        if not p.exists():
            raise FileNotFoundError(
                f"no {'decision' if decisions else 'proposal'} for {ref} at {p}")
        toks = page_tokens(p, rules)
        batch[ref] = toks
        pages.append({"ref": ref, "source": str(p.relative_to(root))
                      if p.is_relative_to(root) else str(p),
                      "tokens": len(toks), "types": len({t for _, t in toks})})

    # Leave-one-out, unconditionally — see the module docstring. Not `if ref in
    # store`: a conditional exclusion is the same rule with a step where it can be
    # forgotten, and the collapse it prevents is silent.
    #
    # **Read once and iterated twice.** The `prior` and the `known` table below
    # are different tallies of the same walk, and each used to call
    # `native_corpus` for itself — two full reads of `gt/ocr/` per run. One call
    # is also what makes a single bar honest: two would each run to 100%, and a
    # bar that finishes and starts again describes a run that is not happening.
    corpus = native_corpus(root, tick)
    prior: dict[str, list[str]] = {}
    for ref, tok in corpus:
        if ref not in under_test:
            prior.setdefault(ref, []).append(_nfd(tok))
    prior_tokens = [t for toks in prior.values() for t in toks]

    rare = _rare(batch, prior_tokens, contrasts, rare_max, rules)
    ratio = [r for c in contrasts for r in _ratio_rows(c, batch, prior, min_types, rules)]

    # **Not leave-one-out, and that is the difference.** Every other arm compares the
    # batch against a prior the batch is held out of, because it is asking whether
    # this reading is unusual. This one asks whether the store already holds the word,
    # so a sibling page in the same batch is a perfectly good witness — `3-199`'s
    # `Ke’rek` should be answerable by `3-178` keying it correctly an hour earlier.
    known: dict[str, list[str]] = {}
    for ref, tok in corpus:
        known.setdefault(_nfd(tok).casefold(), []).append(ref)
    for ref in refs:
        for tok in {t for _, t in batch[ref]}:
            known.setdefault(tok.casefold(), []).append(ref)
    traps = [{"ref": ref, **hit}
             for ref in refs
             for hit in trap_hits(_source_path(ref, root, decisions), known, rules)]

    # No exemptions on this side, deliberately. A proposal is a **record of what a
    # reader wrote**, not a store to be corrected — rewriting one is forbidden
    # after adjudication because `edited` is computed against it, so a conflict here
    # is the measurement rather than a defect. Silencing one would delete the very
    # thing the file exists to hold. Exemptions belong to `lexicon conflicts`, over
    # ground truth, where a fold really can be the book's own inconsistency.
    return {"refs": " ".join(refs),
            "source": "decisions" if decisions else "proposals",
            "prior_pages": len(prior), "prior_note": PRIOR_NOTE,
            "pages": pages, "rare": rare, "traps": traps,
            "conflict": _conflicts(batch, prior, contrasts), "ratio": ratio}


def gt_conflicts(root: Path = Path("."),
                 tick: Callable | None = None) -> dict:
    """One word spelled two ways in **ground truth** — the corpus-wide arm.

    The store side of `proposal marks`' `conflict`, and the difference between
    them is which question the answer is evidence for. A conflict in a proposal is
    a **reader's** disagreement, and it is *data*: `proposal.json` is a record of
    what someone wrote, never rewritten after adjudication because `edited` is
    computed against it, so there is nothing there to silence and no exemption
    file. A conflict in `gt/ocr/` is a claim about the **corpus** — either a
    keying slip to repair, or the book setting one word two ways — and only the
    second kind can be ruled on. That is what `config/marks_exempt.json` holds.

    `gt/ocr/` explicitly, not the `ocr/` view: this publishes a corpus-wide
    finding, and harness/README.md's rule is that anything that gates or publishes a
    number names the stores. Through the view every machine-read page would
    contribute, and CATMuS reads 0% of the inventory — every one of its Tier-1
    tokens would be a spelling nobody keyed.

    Exempt rows are **kept and flagged**, never dropped, like every other
    exemption here: the file recording a judgement is the one place a wrong
    judgement is invisible. `stale_exemptions` is the other half — an entry whose
    conflict no longer occurs has outlived what it ruled on.
    """
    contrasts = load_config(root)["contrasts"]
    exemptions = load_exemptions(root)

    buckets: dict[str, dict[str, dict[str, list[str]]]] = {}
    read = set()
    for ref, idx, tok in native_corpus_lines(root, tick):
        read.add(ref)
        tok = _nfd(tok)
        (buckets.setdefault(fold(tok, contrasts), {})
                .setdefault(tok, {}).setdefault(ref, []).append(idx))

    rows = []
    for key, forms in sorted(buckets.items()):
        # Casefolded, so `äˊmmê`/`Äˊmmê` is not a conflict while `I`/`ɪ` is —
        # U+026A has no case mapping. See `fold`.
        if len({t.casefold() for t in forms}) < 2:
            continue
        for form, refs in sorted(forms.items()):
            for ref, idxs in sorted(refs.items()):
                rows.append({"fold": unicodedata.normalize("NFC", key),
                             "form": unicodedata.normalize("NFC", form),
                             "ref": ref, "lines": ",".join(sorted(idxs, key=int)),
                             "count": len(idxs)})
    rows = _apply_exemptions(rows, exemptions)
    return {"store": "gt/ocr", "pages_read": len(read),
            "pages_with_a_conflict": len({r["ref"] for r in rows}),
            "folds": len({r["fold"] for r in rows}),
            "exempt_rows": sum(1 for r in rows if r["exempt"]),
            "conflict": rows,
            # Scoped to the pages actually read, not to the pages that still have
            # a conflict: an entry is stale when the page was looked at and no
            # longer carries it, and judging against the rows would call every
            # working exemption stale the moment it did its job.
            "stale_exemptions": _stale_exemptions(rows, exemptions, read)}


def page_issues(path: Path, ref: str, root: Path = Path("."),
                cohort: Collection[str] | None = None,
                corpus: list[tuple[str, str]] | None = None) -> list[dict]:
    """The two deterministic arms over one file, as `proposal_check` issue records.

    Only `rare` and `conflict`, and only these because they are the arms that need
    no sample: each is a statement about a form, not about a distribution. `ratio`
    is deliberately absent — one page is a poor sample and it is the arm that
    cannot decide, so folding it into a per-page gate would be asserting exactly
    what `marks` refuses to.

    `line` carries the first line the form appears on and the detail names the
    rest, because an issue record addresses a line while the finding is about a
    page: a form repeated down the page is one slip, and one row per occurrence
    would report a keyer's single habit as several independent faults.

    Returns nothing rather than raising when the config is absent — a reader
    running `proposal check` on a clone that has no `config/marks.json`
    should get the checks that do not need it, not a traceback.

    **`cohort` is the leave-one-out set and the batch is its unit.** Excluding
    only `ref` was right while a batch's pages reached the corpus one at a time
    and wrong the moment they did not: after `restore` every sibling is in
    `gt/ocr/`, so a form two readers of one pass introduced independently — they
    are forbidden to see each other — comes back as this page's prior. `Yaˊyaq`
    on `3-129` and `3-130` is the attested case. Defaults to `{ref}`, which is
    the old behaviour and correct for a single page.

    **`corpus` lets a caller walk `gt/ocr/` once for a whole run.** The walk is
    2.4s at 645 pages and the result does not depend on `ref` — only the
    filtering does — so a per-page walk cost an 18-page `proposal check` about a
    minute of repeating itself.
    """
    try:
        cfg = load_config(root)
    except MarksConfigError:
        return []
    ref = norm_ref(ref)
    rules = keying.rules(root)
    batch = {ref: page_tokens(path, rules)}
    drop = frozenset(cohort) if cohort else {ref}
    prior: dict[str, list[str]] = {}
    for r, tok in (native_corpus(root) if corpus is None else corpus):
        if r not in drop:     # leave-one-out, as everywhere here
            prior.setdefault(r, []).append(_nfd(tok))
    prior_tokens = [t for toks in prior.values() for t in toks]

    # Built through `proposal_check.issue`, not as literals: these two records join
    # four others in one list, and that list is a table only while every record
    # carries the same keys. See `ISSUE_FIELDS`.
    from .proposal_check import ADVISORY, issue

    # Both arms here are advisories, not defects: each is a corpus *share*
    # inviting a look, and neither is satisfiable by the reader it reaches. A rare
    # form cannot be made common, and the second witness in a spelling conflict is
    # another page — which the firewall forbids a reader to open, so the one actor
    # who could settle it is the one who is not allowed to. See `proposal_check`'s
    # DEFECT/ADVISORY note.
    out = []
    for hit in _rare(batch, prior_tokens, cfg["contrasts"], cfg["rare_max_pct"], rules):
        lines = hit["lines"].split()
        where = f" (and lines {' '.join(lines[1:])})" if len(lines) > 1 else ""
        out.append(issue(
            lines[0] if lines else "-",
            f"rare form: {hit['form']!r} sets a character the corpus "
            f"sets in only {hit['corpus_pct']}% of {hit['corpus_n']} "
            f"(keying_spec §{hit['spec']}) — check for a dropped mark",
            token=hit["form"],
            detail=f"{hit['count']} occurrence(s) on this page{where}",
            severity=ADVISORY))
    # One issue per *fold*, not per row: `_conflicts` emits a row per (fold, form,
    # ref) so the table can name lines, but a word keyed two ways is one fault
    # however many places it surfaces — the same rule that keeps `rare` to one
    # issue per form.
    #
    # And no exemptions here either, for the reason `marks` states: this reads a
    # proposal, and a proposal records what a reader wrote rather than what the
    # corpus holds. `config/marks_exempt.json` rules on ground truth and is consulted
    # only by `lexicon conflicts`.
    folds: dict[str, list[dict]] = {}
    for hit in _conflicts(batch, prior, cfg["contrasts"]):
        folds.setdefault(hit["fold"], []).append(hit)
    for rows in folds.values():
        here = [r for r in rows if r["source"] == "batch" and r["ref"] == ref]
        other = [r for r in rows if r not in here]
        lines = sorted({i for r in here for i in r["lines"].split(",") if i}, key=int)
        against = " ".join(sorted({r["form"] for r in other})) or "(this page only)"
        out.append(issue(
            lines[0] if lines else "-",
            "one word, two spellings" + (
                "" if rows[0]["in_batch"] else " — the other is adjudicated ground truth"),
            token=" ".join(sorted({r["form"] for r in here})),
            detail=f"against {against} on "
                   f"{' '.join(sorted({r['ref'] for r in other})) or ref}"
                   + (f" (lines {','.join(lines)})" if len(lines) > 1 else ""),
            severity=ADVISORY))
    return out
