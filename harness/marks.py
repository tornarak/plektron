"""Is this batch's character distribution plausible — before a human opens it.

`dispatch.md` has long told the coordinator to run `harness lexicon marks` and
compare a batch against it by eye, calling it "the only check in the loop that
needs neither a raster nor a reader's cooperation… the one that would have caught
the most". This is that comparison computed. `lexicon marks` cannot be scoped to a
page at all, and it groups by base letter, so it cannot express `ɪ`/`i` — which is
not a mark on a base — at any scope.

**Three arms, and they are not equally strong.** Read them in this order:

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
  firewall, `review`'s span diff and `zones score`'s `unseen` row. Excluding
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
import unicodedata
from collections.abc import Collection
from pathlib import Path

from .detectors import (
    EDGE_PUNCT,
    INVENTORY_CHARS,
    TOKEN,
    bears_inventory,
    cyrillic,
    native_corpus,
    native_corpus_lines,
)
from .refs import norm_ref

CONFIG = "data/marks_config.json"


class MarksConfigError(ValueError):
    """A malformed config, raised at load rather than met halfway through a run.

    Same posture as `zones_config.ConfigError`: a contrast silently dropped for a
    missing field would make the arm that needed it quietly report nothing, which
    is indistinguishable from a clean batch.
    """


def config_path(root: Path = Path(".")) -> Path:
    return root / CONFIG


def load_config(root: Path = Path(".")) -> dict:
    """Read and check `data/marks_config.json`.

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
    if not isinstance(contrasts, list) or not contrasts:
        raise MarksConfigError(f"{p}: 'contrasts' must be a non-empty list")
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
    return cfg


EXEMPT = "data/marks_exempt.json"


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


def is_medial(token: str, i: int) -> bool:
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
    return prev == "-" and any(c in INVENTORY_CHARS for c in token)


def _find(token: str, needle: str, position: str) -> list[int]:
    """Indices where `needle` occurs, filtered by the contrast's position scope."""
    out, start = [], 0
    while (i := token.find(needle, start)) != -1:
        if position == "any" or not is_medial(token, i):
            out.append(i)
        start = i + 1
    return out


def sites(token: str, c: dict) -> tuple[list[int], list[int]]:
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
    exp = _find(token, c["expected"], c["position"])
    covered = set(exp) if c["expected"].startswith(c["confusable"]) else set()
    conf = [i for i in _find(token, c["confusable"], c["position"]) if i not in covered]
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


# **One marker per mark class, and the classes collide on purpose.** `^` serves the
# superscripts and the caron/circumflex, `.` both dots. A collision yields two
# distinct forms with one key, which `lookup` already refuses as a key collision, so
# inventing a marker against a case the corpus does not attest would be guesswork
# ahead of an instance — the rule `tier1_terms` states for ranges.
#
# A combining mark contributes **only** its marker: after NFD its base is already an
# ASCII letter and has passed through. An atomic letter contributes an ASCII base
# and a marker; `ˊ` and `˙` are marks that stand alone and so contribute no base.
HANDLE_MARKERS = {
    "ˊ": "'", "˙": ".",
    "ɪ": "i_", "ᴇ": "e_", "ᴀ": "a_", "ʟ": "l_", "ɵ": "o_",
    "ᵋ": "e^", "ᵉ": "e^",
    "̣": ".", "̌": "^", "̂": "^", "̃": "~",
    "̈": ":", "̆": ")", "̄": "=",
}


def handle_key(token: str) -> str:
    """The typed handle for one form: ASCII through, every other character marked.

    **A plain-ASCII key would teach the reader the wrong glyph.** `fold` collapses
    exactly the axes this pass gets wrong most often — dropped U+0323 is the largest
    single correction class in the store, and `i`/`ɪ`/`I` the largest family — so a
    key spelled `kavralit` asserts an `i` that is not there, to a reader who will
    key it from memory on a later page. Every non-ASCII character therefore leaves a
    visible marker, and the key cannot be read back as a spelling.

        Kuluˊči            -> kulu'c^i
        Kavraˊlɪt          -> kavra'li_t
        Notaˊs˙qa-vaˊɪrg̣ɪn -> nota's.qa-va'i_rg.i_n

    **This is not `fold` and must not be**: marking a collapse distinguishes it,
    and the bucket exists to *not* distinguish — `Čeˊwɪn` and `Čeˊwin` are one word
    there and two keys here. So the ambiguity refusal lives on the bucket, and a
    precise key pointing into a contested one is refused all the same. Without that
    split, a reader could name a side of a live conflict by spelling it exactly.

    U+0027 and U+002D pass through as themselves: the ASCII policy makes both
    load-bearing inside Tier-1 and 147 of the 499 attested forms carry a hyphen, so
    stripping them would merge forms the book distinguishes.

    **Case passes through too, and lowercasing was tried first.** It collided on 11
    of the 499 — `Aiˊwan`/`aiˊwan`, `Kavraˊlɪt`/`kavraˊlɪt`, and nine more, every
    one a word attested both sentence-initially and mid-sentence. Case is not a
    glyph identity a reader has to guess at: it is legible at any zoom, unlike the
    dot-below this key exists to stop asserting, so the reader types the case it
    sees and the collision disappears. `fold` still casefolds, so the two remain one
    bucket and a genuine `I`/`ɪ` disagreement — which casefolding cannot hide, U+026A
    having no case mapping — is still caught there.

    Raises on a character `HANDLE_MARKERS` does not reach, rather than dropping it.
    A silent pass-through is how a new inventory glyph would start producing keys
    that read as spellings, which is the one thing this function exists to prevent.
    """
    out = []
    for ch in unicodedata.normalize("NFD", token):
        if ch.isascii():
            out.append(ch)
        elif ch in HANDLE_MARKERS:
            out.append(HANDLE_MARKERS[ch])
        else:
            raise ValueError(
                f"no handle marker for U+{ord(ch):04X} in {token!r} — add it to "
                "HANDLE_MARKERS beside the inventory member it belongs to")
    return "".join(out)


def page_tokens(path: Path) -> list[tuple[str, str]]:
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
            if tok and not cyrillic(tok) and bears_inventory(tok):
                out.append((idx, tok))
    return out


def _axis_counts(tokens, contrast) -> tuple[int, int]:
    """(expected occurrences, confusable occurrences) under the position scope."""
    exp = conf = 0
    for tok in tokens:
        e, f = sites(tok, contrast)
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
          rare_max: float) -> list[dict]:
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
        exp_n, conf_n = _axis_counts(prior_tokens, c)
        axis_n = exp_n + conf_n
        if not axis_n:
            continue
        conf_pct = round(100 * conf_n / axis_n, 1)
        if conf_pct > rare_max:
            continue
        for ref, toks in batch.items():
            forms: dict[str, list[str]] = {}
            for line, tok in toks:
                if sites(tok, c)[1]:
                    forms.setdefault(tok, []).append(line)
            for tok, lines in sorted(forms.items()):
                out.append({
                    "ref": ref, "form": unicodedata.normalize("NFC", tok),
                    "count": len(lines), "lines": " ".join(lines),
                    "position": c["position"], "corpus_pct": conf_pct,
                    "corpus_n": axis_n, "spec": c.get("spec", "")})
    return out


def _ratio_rows(c: dict, batch: dict, prior: dict, min_types: int) -> list[dict]:
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
        exp = sum(1 for t in types if sites(t, c)[0])
        conf = sum(1 for t in types if sites(t, c)[1])
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
          min_types: int | None = None, rare_max: float | None = None) -> dict:
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

    refs = [norm_ref(r) for r in refs]
    under_test = set(refs)

    batch: dict[str, list[tuple[str, str]]] = {}
    pages = []
    for ref in refs:
        p = _source_path(ref, root, decisions)
        if not p.exists():
            raise FileNotFoundError(
                f"no {'decision' if decisions else 'proposal'} for {ref} at {p}")
        toks = page_tokens(p)
        batch[ref] = toks
        pages.append({"ref": ref, "source": str(p.relative_to(root))
                      if p.is_relative_to(root) else str(p),
                      "tokens": len(toks), "types": len({t for _, t in toks})})

    # Leave-one-out, unconditionally — see the module docstring. Not `if ref in
    # store`: a conditional exclusion is the same rule with a step where it can be
    # forgotten, and the collapse it prevents is silent.
    prior: dict[str, list[str]] = {}
    for ref, tok in native_corpus(root):
        if ref not in under_test:
            prior.setdefault(ref, []).append(_nfd(tok))
    prior_tokens = [t for toks in prior.values() for t in toks]

    rare = _rare(batch, prior_tokens, contrasts, rare_max)
    ratio = [r for c in contrasts for r in _ratio_rows(c, batch, prior, min_types)]

    # No exemptions on this side, deliberately. A proposal is a **record of what a
    # reader wrote**, not a store to be corrected — rewriting one is forbidden
    # after adjudication because `edited` is computed against it, so a conflict here
    # is the measurement rather than a defect. Silencing one would delete the very
    # thing the file exists to hold. Exemptions belong to `lexicon conflicts`, over
    # ground truth, where a fold really can be the book's own inconsistency.
    return {"refs": " ".join(refs),
            "source": "decisions" if decisions else "proposals",
            "prior_pages": len(prior), "prior_note": PRIOR_NOTE,
            "pages": pages, "rare": rare,
            "conflict": _conflicts(batch, prior, contrasts), "ratio": ratio}


def gt_conflicts(root: Path = Path(".")) -> dict:
    """One word spelled two ways in **ground truth** — the corpus-wide arm.

    The store side of `proposal marks`' `conflict`, and the difference between
    them is which question the answer is evidence for. A conflict in a proposal is
    a **reader's** disagreement, and it is *data*: `proposal.json` is a record of
    what someone wrote, never rewritten after adjudication because `edited` is
    computed against it, so there is nothing there to silence and no exemption
    file. A conflict in `gt/ocr/` is a claim about the **corpus** — either a
    keying slip to repair, or the book setting one word two ways — and only the
    second kind can be ruled on. That is what `data/marks_exempt.json` holds.

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
    for ref, idx, tok in native_corpus_lines(root):
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
    running `proposal check` on a clone that has no `data/marks_config.json`
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
    batch = {ref: page_tokens(path)}
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
    for hit in _rare(batch, prior_tokens, cfg["contrasts"], cfg["rare_max_pct"]):
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
    # corpus holds. `data/marks_exempt.json` rules on ground truth and is consulted
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
