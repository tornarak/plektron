"""Self-consistency gate for a reading proposal, not a firewall tool.

`review/PP-NNN/proposal.json` asks the author to spell out codepoints in
`resolved` for any line carrying notation (rebuild-groundtruth SKILL.md,
"The proposal file") precisely because a combining mark that fails to render
looks identical to its absence, and because hand-typing a combining sequence
is easy to fumble into a different mark that looks the same at a glance —
ring below for dot below, diaeresis for caron. The skill already says the
`resolved` field "catches your own typing, since the field and the character
can disagree"; this is that check promoted from something a human re-reads
into something a script runs, same rationale as `normalize.py` promoting the
NFD one-liner.

This is **not** `detectors.MARK_LICENSE` and must not grow into it. That table
is closed by editor attestation and answers "is this glyph possible" — the
question this module answers is narrower and unambiguous: "does the text the
author wrote match the codepoints the same author just said they meant."
Nothing here rules on what the *page* prints; `--fix` only ever moves a line
toward what its own `resolved` field already claims, and only when that claim
is unambiguous. A resolved field the tool cannot reconcile is left alone and
reported, never guessed at.

One exception to "unambiguous therefore fixable": a word-medial ASCII A/E/I/L
(`detectors.MEDIAL_CAPS`) counts toward the codepoint accounting so a line
with two independent errors is correctly seen as ambiguous rather than as a
false clean swap (see `_notation_codepoints`), but `fix()` never auto-replaces
one even when it is the lone dangling item — a mistyped combining mark (ring
below for dot below) is a shape slip with one obvious correction; a plain
capital letter sitting where a small-cap belongs is closer to a reading
judgement, so it stays a `check()` flag for a human to resolve.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Collection
from pathlib import Path

from .codepoints import non_ascii
from .detectors import (
    INVENTORY_CHARS,
    apostrophe_flags,
    footnote_report,
    medial_cap_positions,
    suffix_mark_flags,
)

HEX_RE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")
# The trigger set is `detectors.INVENTORY_CHARS` itself, not a re-derived Unicode
# category — the small caps ᴀᴇɪ and ᵋ are ordinary letter categories (Ll/Lm) and a
# category-based heuristic would miss them entirely, silently exempting exactly
# the glyphs most worth cross-checking. Dotless ı is inventory-adjacent (§2.6's
# ĭ = dotless-i + breve) but absent from INVENTORY_CHARS, so it is added here.
DOTLESS_I = "ı"
NOTATION_CHARS = INVENTORY_CHARS | {DOTLESS_I}

# The one issue-record shape, and the only constructor for it.
#
# Six detectors feed `check` — three here, two in `marks.page_issues`, one in
# `_footnote_issues` — and each used to name its own fields: `context` beside
# `token`, `detail` beside `token`, `in_text`, `in_text_not_resolved` beside
# `in_resolved_not_text`, `explained`. Six key sets over one list of records, which
# is exactly the raggedness `emit`'s docstring says degrades a TOON table to the
# verbose nested form. It did: a corpus sweep emitted 265 findings as 51 KB of
# indented blocks, and pooling several refs tripped `_pool`'s list guard on the way
# past. The detectors already had this rule imposed on them once, for the same
# reason ("one `token` key rather than `span` for some flag types") — this is that
# rule with a constructor behind it, so the next detector cannot quietly reopen it.
#
# `detail` is where a shape that is not a token goes, rendered as text: the
# codepoint sets both `resolved` arms report, and the footnote arm's editorial note.
# A list never reaches the record.
ISSUE_FIELDS = ("line", "issue", "severity", "token", "context", "detail")

# The two severities, and the rule that separates them: **a gate must be
# satisfiable by the actor it gates.**
#
# DEFECT is a claim that something *is* wrong and that the reader can put it
# right — `resolved` naming codepoints the text does not contain, a straight
# apostrophe (never a genuine reading corpus-wide), notation with no `resolved`
# at all, a footnote marker that pairs with nothing.
#
# ADVISORY is measurement: leave-one-out corpus statistics saying "this shape is
# rare, go look". It cannot be *satisfied*, only answered — there is no field
# recording "checked, genuinely bare", and for a cross-page spelling conflict the
# second witness is a page the reader is forbidden to open. It gated anyway until
# now, and the damage was exactly what a gate nobody can pass does: eight of
# eighteen failing proposals in `review/` failed on advisories alone, the reading
# brief had to be rewritten to say "exit 1 is sometimes fine", and a real
# `resolved/text mismatch` became indistinguishable from a rare surname.
#
# So `measurement never gates` (VERBS.md, Conventions) is applied here too. An
# advisory still prints, at the same volume, in the same table — it simply stops
# claiming to be a gate. `--strict` gates on both, for a sweep where every prompt
# is meant to be chased.
DEFECT = "defect"
ADVISORY = "advisory"

# What a reader's `note` is *about*, as a closed set, so the review UI can colour
# the classes apart instead of rendering one undifferentiated amber paragraph.
#
# The set is closed and small on purpose: an open vocabulary is a free-text field
# with extra steps, and the whole value here is that the adjudicator learns six
# colours and can then skip on sight. Each is a different question:
#
#   doubt     the reader could not close it at the 4x ceiling. The only class
#             that asks the adjudicator for a ruling.
#   semantic  the letterforms are settled and the sense is not — the
#             fluent-nonsense case, which is otherwise invisible precisely
#             because nothing about the characters looks wrong.
#   print     a letter or a word the compositor set wrong, keyed verbatim per
#             keying_spec §2.14. Letters and words only: a stray mark of
#             punctuation is a blot, and blots are `artifact`.
#   draft     the *recognizer* read a character wrong and a settled rule says
#             what it is — italic `b` as `6`, a marker as `!` or `?`, `ɪ` as
#             `r`. About `mz/ocr`, not about the book, and the reader cites the
#             rule rather than asking for a ruling.
#   layout    a band, gap, dropped line or covered zone — about geometry rather
#             than glyphs, and settled by a different instrument.
#   artifact  an ink speck ruled not-type. A ruling already made, worth a
#             spot-check and no more; the commonest note there is.
#
# A note with no class is valid and renders neutral: the undimming that makes any
# of this work is earned by writing a note at all, and a reader who is unsure
# which class applies must not be pushed toward silence.
#
# `print` is letters and words because it used to be anything. It was the only class
# that let a reader *conclude* rather than hand up, and what it concluded was that
# the book was wrong — so it absorbed every mark the eye could not otherwise place.
# Five readers of one fifteen-page batch keyed a blot as punctuation and filed it
# here, each having zoomed first, each reporting the ink confirmed; every one was
# struck by the adjudicator. Zooming shows a mark is there, never that it is type.
#
# `draft` was added because its absence was pushing the same error the other way.
# Correcting the recognizer against a settled rule is the commonest thing a reader
# does and it fitted nothing: not `doubt`, since nothing is uncertain; not `print`,
# since the book is not wrong. Over 2026-08-06/07 four readers left the field unset
# and said so, and six filed it as `print` — which asserts a compositor's error
# that did not happen, putting a false claim about the book into the record to
# describe a machine's misreading. A class is cheaper than that.
NOTE_CLASSES = ("doubt", "semantic", "print", "draft", "layout", "artifact")

# What `_added_terminal_punctuation` will question at the end of a line. Sentence
# punctuation only: a closing bracket or quote is structural, routinely spans a
# line break, and disagreeing with the draft about one is ordinary work.
TERMINAL_PUNCTUATION = ",.;:"


def issue(line, text: str, token: str = "", context: str = "",
          detail: str = "", severity: str = DEFECT) -> dict:
    """One issue record, every field present. See `ISSUE_FIELDS`.

    `severity` defaults to `DEFECT` because that is the safe direction: a new
    detector added without thinking about severity gates, and someone notices.
    The reverse default would let one land silently and never fire.
    """
    return {"line": str(line), "issue": text, "severity": severity,
            "token": token, "context": context, "detail": detail}


def _cps(codepoints) -> str:
    """A codepoint set as `U+02CA U+026A`, sorted — `detail` text, not a list."""
    return " ".join(sorted(f"U+{c:04X}" for c in codepoints))


def _notation_codepoints(text: str) -> list[int]:
    """Codepoints a `resolved` field is expected to name.

    Any combining mark at all (Unicode category Mn), not only the ones
    `INVENTORY_CHARS` already knows about — a mark entirely foreign to the
    inventory (ring below, say, where dot below was meant) is exactly the
    error this module exists to catch, and restricting to known-good marks
    would make it invisible for having the wrong identity instead of a
    licensing problem.

    **One exception, and it is a base allow-list rather than a script test.**
    A mark sitting on one of `detectors.ORTHOGRAPHIC_BASES`' bases is ordinary
    European or Russian spelling, not a mark anybody read off a letterform:
    U+0306 on и is Cyrillic й under NFD, U+0308 on o/u/i is ö/ü/ï in a German or
    Russian name. Both were counted for a long time, and readers paid for it —
    six proposals before `3-147` carry near-identical boilerplate in `resolved`
    narrating the Cyrillic decomposition (`1-031`, `1-086`, `1-147`, `1-359`,
    `3-038`, `3-106`), and `3-146` hit the pair eleven times on one page. That is
    the field's own purpose inverted: it exists so a reader accounts for the
    marks it *settled*, which is why a handled line is exempt six lines below;
    demanding an account of й or of `Müller` asks for an invented one,
    indistinguishable from a real account.

    **What stays counted is the point.** `ŭ`/`ĭ` are §2.2/§2.6 sorts, and `ä`/`ë`
    are §2.3 sorts — the single `ë` in the corpus is `Geëk Land` on `1-048`,
    beside `Veᵋñ` on the same line. All still answer for themselves. So does a
    diaeresis on any base the table does not name, the table being an exclusion
    list precisely so a novel one is loud rather than skipped.

    The breve row is also `MARK_LICENSE`'s, and the reasoning for an explicit
    base set over a "consult the table only for Latin bases" script test is
    written there in full — along with why the diaeresis gets no `MARK_LICENSE`
    row of its own, which is a different question from this one and answered the
    other way.

    Also counts a word-medial ASCII A/E/I/L (`detectors.MEDIAL_CAPS`, the same
    check `harness tei context` already runs over OCR text) as a codepoint present.
    This is what `1-100` line 37 needed and did not have: a plain 'A' typed for
    small-cap ᴀ is invisible to every check above (ASCII, not a combining mark),
    so on a line that *also* had an unrelated ı-for-ɪ slip, `fix()`'s "exactly
    one dangling item on each side" test saw a false 1-for-1 and silently swapped
    the wrong pair. Folding the ASCII hit into `present` restores the true count
    — either it now matches `resolved` correctly, or `fix()` sees two dangling
    items and correctly refuses to guess instead of pairing them wrong.
    """
    from .detectors import ORTHOGRAPHIC_BASES

    nfd = unicodedata.normalize("NFD", text)
    codepoints = [ord(ch) for i, ch in enumerate(nfd)
                 if (ch in NOTATION_CHARS or unicodedata.category(ch) == "Mn")
                 and not (i and nfd[i - 1] in ORTHOGRAPHIC_BASES.get(ch, ""))]
    codepoints += [ord(nfd[i]) for i in medial_cap_positions(nfd)]
    return codepoints


def _stated_codepoints(resolved: str) -> set[int]:
    """Codepoints a `resolved` field names, **decomposed to the corpus's own form**.

    A reader naming `U+00EA` means "ê", which is the ordinary way to refer to the
    letter and is how the spec's own tables print it. But the corpus is NFD, so
    U+00EA never occurs in any `text` — comparing the two literally made a
    correctly-named precomposed letter *always* absent from the text and the
    combining mark actually there *always* unaccounted for, one dangling item on
    each side. `fix()` reads exactly that shape as an unambiguous 1-for-1 swap.

    On `1-039` line 38 it fired: `êlh-aˊᵋttᴀm`, NFD, plus a `resolved` naming
    U+00EA, and the "correction" dropped the precomposed letter into the combining
    mark's slot — `e` + `ê` = `eêlh-`. The reader caught it with `codepoints` and
    worked around it by respelling every `resolved` field as decompositions, which
    is a human degrading their own notes to route around a parser.

    Folding here rather than at the call sites because both directions of the
    comparison need it and only one of them was ever going to be remembered.
    """
    out: set[int] = set()
    for h in HEX_RE.findall(resolved):
        for ch in unicodedata.normalize("NFD", chr(int(h, 16))):
            out.add(ord(ch))
    return out


def _stated_but_absent(stated: set[int], text: str) -> set[int]:
    """Codepoints `resolved` names that the text does not contain at all.

    **The two directions of this comparison are not symmetric**, and treating
    them as if they were made the gate punish thoroughness. `_notation_codepoints`
    is deliberately narrow — combining marks and medial caps, the things a
    `resolved` field is *obliged* to name — so subtracting it from `stated`
    flagged any codepoint a reader spelled out that merely was not a combining
    mark, even when it sits plainly in the text. `2-042` was refused for
    documenting the hyphen of `Čiñeiˊ-ñew` and the superscript of `Peruˊten³`: a
    hyphen is load-bearing in Americanist notation and the superscript is the
    entire subject of §2.10, so both are exactly what a careful reader writes
    down, and the gate told them not to.

    What this direction exists to catch is the defect the reading pass names — a
    `resolved` describing a keying decision *the text does not exhibit*, which
    argues an adjudicator into undoing correct work. That is a claim about the
    text's characters, so it is answered against them.
    """
    return stated - {ord(ch) for ch in unicodedata.normalize("NFD", text)}


def _keyed_by_hand(rec: dict, text: str) -> str:
    """The part of a reading the reader's own eyes produced.

    A line with no `as_typed` is all its own; otherwise it is `as_typed` with the
    handles cut out, which leaves exactly the characters the reader keyed. Used by
    the arms that ask a reader to account for what it read.
    """
    from .lookup import HANDLE

    typed = rec.get("as_typed", "")
    return HANDLE.sub("", typed) if typed else text


def _handle_issues(idx: str, rec: dict, text: str, root: Path,
                   lex=None) -> list[dict]:
    """The provenance record and the reading must agree, or neither is evidence.

    **`lex` is why `proposal check` used to take minutes.** `expand` builds the
    corpus index when it is not given one, and this arm calls it once per line
    carrying `as_typed` — so a page that used handles well paid a 2.4s walk for
    each of them, and `3-143`'s nine handles cost 26 seconds on one page. The
    verb was slowest on exactly the pages doing the right thing.

    Two defects here, and still **no arm noticing every hand-typed form the lookup
    could have supplied**: that one would fire on ordinary correct reading on
    nearly every Tier-1 line of every page — a detector firing on ordinary work
    buries the real hits, which is the failure `CLAUDE.md` names — and its only
    actionable reading would be "you should have used a handle here", which is
    pressure to stop looking at the raster.

    `_named_key_issues` is the narrow arm that survives both objections, because
    it fires only where the proposal named the key itself. Measured over the
    twenty-seven pages of chapter XX: eight hits on five pages, every one a form
    whose note quoted the key beside a hand-typed reading.
    """
    from .lookup import HANDLE, expand

    out = []
    typed = rec.get("as_typed", "")
    if typed and not HANDLE.search(typed):
        out.append(issue(idx, "as_typed carries no handle",
                         detail="the field records that the corpus supplied part "
                                "of this line; with no handle in it, it records "
                                "nothing and badges the line for no reason"))
    elif typed:
        want, refusals = expand(typed, root, idx=lex() if callable(lex) else lex)
        if refusals:
            out.append(issue(idx, "as_typed no longer resolves",
                             detail="; ".join(refusals)))
        elif unicodedata.normalize("NFD", want) != unicodedata.normalize("NFD",
                                                                         text):
            out.append(issue(idx, "as_typed does not expand to text",
                             detail=f"expands to {want!r}, line holds {text!r} — "
                                    "one of them was edited without the other, so "
                                    "neither is a record of what happened"))
    if "{" in text or "}" in text:
        out.append(issue(idx, "brace in the reading",
                         detail="no page keys a brace; this is a handle that was "
                                "never expanded, or a character belonging in a "
                                "note rather than in the text"))
    return out


#: A token in a `note` shaped like a lexicon key — bare ASCII carrying at least
#: one of the key alphabet's marks, so ordinary English prose in a note does not
#: match and `Cf. lexicon key taka'lhi_n` does.
_NOTE_KEY = re.compile(r"[A-Za-z][A-Za-z0-9'\-_^.~:)=]*['_^.~:][A-Za-z0-9'\-_^.~:)=]*")

#: The key alphabet's *distinctive* marks — small-cap `_`, dot-below `.`,
#: circumflex `^`, tilde `~`, diaeresis `:`. The apostrophe is deliberately not
#: among them: it is the one key character English prose also uses, so `don't` and
#: `reader's` would make every note look like it named a key.
_KEY_MARK = re.compile(r"[A-Za-z][A-Za-z0-9'\-)=]*(?:[_^~:]|\.[A-Za-z])")

#: On a word boundary, because a substring test on `key` matches `keyed` — which
#: readers write constantly ("keyed from the raster", "not keyed") — and would
#: have left this gate open on nearly every note that has one.
_KEY_WORD = re.compile(r"\b(?:keys?|lexicon|lookup)\b", re.I)


def could_name_key(note: str) -> bool:
    """Whether a `note` could be naming a lexicon key, cheaply.

    The precondition on building the index, which walks the whole corpus and is
    the expensive part of `proposal check`. Three words readers actually use, a
    brace, or a token carrying one of the key alphabet's distinctive marks — the
    last is what catches a key written with no word announcing it.

    **`lookup` is in the list because leaving it out was a hole**: a note reading
    "lookup gave `taka'lhi_n`" names a key and says neither "key" nor "lexicon",
    and the arm never saw it. A word list assembled from the phrasings that
    happened to appear in one chapter is a sample, not a rule, which is why the
    mark test backs it up rather than the words standing alone.
    """
    note = note or ""
    return ("{" in note or bool(_KEY_WORD.search(note))
            or bool(_KEY_MARK.search(note)))


def _lexicon_loader(root: Path, exclude: Collection[str]):
    """A zero-argument callable that builds the lexicon index once, on first call.

    `index` walks the whole corpus, so a page whose notes never name a resolvable
    key must not pay for it — and most pages don't. Handing `check`'s line loop a
    loader rather than an index moves the cost to the first line that actually has
    a token to resolve, and shares one walk across the rest of the page.
    """
    cache: dict = {}

    def load() -> dict:
        if "idx" not in cache:
            from .lookup import index

            cache["idx"] = index(root, exclude=exclude)
        return cache["idx"]

    return load


def _one_key_for(token: str, root: Path, text: str,
                 lex: dict | None = None) -> tuple[str, str] | None:
    """`(key, form)` where `token` reaches exactly one usable key the line holds.

    For a note that names the **query** rather than the key. `search` reduces both
    sides, so `Cepa't` reaches `C^e^pa't` where `expand` — which needs the key
    itself — refuses. Returns `None` on anything but a single usable row: several
    rows mean the corpus offers a choice, and picking one would make this arm the
    thing that settles a spelling.
    """
    from .lookup import bare, search

    # `search` is a substring test over a bare reduction, so a short token is a
    # wildcard: `_NOTE_KEY` finds `n.` inside `takaˊlhɪn.`, whose reduction `n`
    # sits in `takalhin` and "resolves". The exact-key path cannot do this — a key
    # is matched whole — so the floor belongs here and nowhere else.
    if len(bare(token)) < 4:
        return None
    rows = [r for r in search([token], root, idx=lex)["matches"]
            if r["key"] and r["form"] in text]
    if len(rows) != 1:
        return None
    return rows[0]["key"], rows[0]["form"]


def _named_key_issues(idx: str, rec: dict, text: str, root: Path,
                      lex: dict | None = None) -> list[dict]:
    """A `note` naming a key the line then types by hand.

    The narrow arm `_handle_issues` declines to write in general. It fires only
    where **the proposal itself names the key**, so it cannot fire on ordinary
    correct reading, and its actionable reading is never "you should have used a
    handle here" — which would be pressure to stop looking at the raster — but
    "you cited corroboration you did not take". `3-088` wrote `Matches lexicon key
    {Ai'g.i_nto} -> Aiˊg̣ɪnto` into three notes and typed all three by hand;
    `3-094` wrote `Cf. lexicon key taka'lhi_n` beside a hand-typed `takaˊlhɪn`.
    A brace in a note is the sharpest form of the tell: braces do nothing there,
    so one is a handle the reader wrote down and then declined to use.

    **A key the line disagrees with is not this, and must never be reported as
    it.** Where a reader reads its own page against the corpus and keys what it
    sees — `3-085`'s `Eiñeˊwg̣i` against a ratified `Eiñewg̣i`, `3-092`'s capital
    `Tatk-Omruˊwg̣ê`, `3-103`'s `Mɪˊs˙qän` against `Mɪˊs˙qᴀn` — the resolved form
    is *absent* from `text` and nothing fires. That is why the test is whether the
    expansion appears in the line, and not whether a key was mentioned: the
    mention is the reader doing exactly what the contract asks of a form the book
    spells two ways.

    **A note may name the query rather than the key, and that is the same
    finding.** `3-142` wrote "lexicon lookup `Cepa't` returned no key" beside five
    hand-typed `Čêpaˊt` — a query that does return the key, `C^e^pa't`. Resolved
    as a key the token refuses, so the first pass is blind to it; put through
    `search`, which is fuzzy on both sides by design, it lands on one usable row
    whose form the line already holds. Only an unambiguous single hit counts: two
    rows mean the corpus itself offers a choice, and naming one would be this arm
    picking a side, which is the thing it exists not to do.

    **The index must be leave-one-out, and without one this arm does not run.**
    After `restore` a page's own reading is in `gt/ocr/`, so an index containing
    it hands the page a key it alone created: run over the batch that had just
    been restored, this reported `3-131` for not using `Va'li_rg.i_n` — one
    occurrence, on `3-131` — and `3-137` for `li'nlin~qin`, one occurrence, on
    `3-137`. Both readings the adjudicator had accepted, quoted back as
    corrections. That is the two-witnesses-that-are-one failure `CLAUDE.md` names,
    in a fifth place after the verbatim firewall, `review`'s span diff, `zones
    score`'s `unseen` row and `marks`' prior. `check` therefore passes a loader
    only when it has a ref to exclude, and `lex is None` means the caller could
    not exclude anything — the same reason the corpus arms are skipped there.
    """
    from .lookup import HANDLE, expand

    note = rec.get("note", "") or ""
    if lex is None or not note:
        return []
    if not could_name_key(note):
        return []
    used = set(HANDLE.findall(rec.get("as_typed", "") or ""))
    named = [t for t in list(HANDLE.findall(note)) + _NOTE_KEY.findall(note)
             if t not in used]
    if not named:
        return []
    # Built here and not before: `index` walks the corpus, and a page reaches this
    # line only if some note both trips the trigger and holds a token to resolve.
    # `check` hands down a loader rather than an index so the walk happens once per
    # page at most, and not at all on the pages that never get this far.
    lex = lex() if callable(lex) else lex
    out, seen = [], set()
    for cand in named:
        # A key may legitimately end in `.` — a form ending in g̣ keys as `...g.` —
        # so the token as written is tried first and a trailing stop stripped only
        # when that fails. Without the fallback a key closing a sentence (`Cf.
        # lexicon key taka'lhi_n.`) never resolves, which is how most are written.
        variants = (cand, cand[:-1]) if cand.endswith(".") else (cand,)
        if any(v in used or v in seen for v in variants):
            seen.update(variants)
            continue
        seen.update(variants)
        # **Every variant as a key before any of them as a query.** Both passes
        # reach the same form, but only the first names the key the reader should
        # have typed: run them interleaved and `taka'lhi_n.` resolves through
        # `search` and gets reported as reaching `taka'lhi_n`, which is true and
        # useless — the stripped variant *is* the key and says so directly.
        hit = None
        for tok in variants:
            form, refusals = expand("{" + tok + "}", root, idx=lex)
            if not refusals and form in text:
                hit = (tok, tok, form)
                break
        if hit is None:
            for tok in variants:
                if found := _one_key_for(tok, root, text, lex):
                    hit = (tok, *found)
                    break
        if hit is None:
            continue
        # Named as written *and* as the key when they differ: the note said
        # `Cepa't`, the key is `C^e^pa't`, and reporting only the latter would
        # have this arm misquote the proposal — the very thing it is reporting.
        wrote, key, form = hit
        named = (f"the key {key!r}" if wrote == key
                 else f"{wrote!r}, which reaches the key {key!r},")
        out.append(issue(
            idx, f"note names {named} and the line types it by hand",
            token=form,
            detail="the corpus supplies these characters and the reading agrees "
                   "with them, so the handle was available and was not used — a "
                   "hand-retyped form must be re-read for a dropped mark, a keyed "
                   "one was ratified elsewhere. Where the page disagrees with the "
                   "corpus, key what you see: this fires only because the line "
                   "already holds exactly what the key expands to",
            severity=ADVISORY))
    return out


def _expanded(value: str, field: str, root: Path | None) -> tuple[str, str | None]:
    """Resolve any `{key}` handles in a reading, and keep what was typed.

    **The expansion happens here, on write, and not when the review server serves
    the line.** Both put the ratified glyphs in front of the adjudicator, but only
    this one leaves `text` and the decision comparing like with like: expanding at
    serve time would make every handled line differ from its proposal, so it would
    read as a human edit in `save_decisions` and enter `ocr corrections` as a
    correction class — the pass's own error profile polluted by its own tooling.

    `as_typed` is the provenance record and the reason a handle is safe to offer at
    all. The firewall's rule is that a comparison whose witnesses may be one witness
    must say so; a reader that quietly copies a corpus spelling has collapsed two
    witnesses into one, and this is the field that says so, out of which the review
    UI derives the badge. **Derived, never asserted** — a self-reported class could
    be omitted by the reader whose claim it describes.

    Only `text` is expanded. A note may mention a handle without meaning it.
    """
    if field != "text" or "{" not in value:
        return value, None
    from .lookup import expand

    out, refusals = expand(value, root if root is not None else Path("."))
    if refusals:
        raise ValueError("; ".join(refusals) + ". Nothing was written: a "
                         "half-expanded line records neither what was read nor "
                         "what was meant")
    return out, value


def _validated(field: str, value: str) -> str:
    """`value`, or a refusal naming what the field accepts.

    `class` is the one field with a closed vocabulary, so it is the one field where
    a typo is checkable rather than a matter of reading. It is checked here, at the
    write, rather than left to `check` afterwards: an unknown class reads as a
    missing class to everything downstream, and a note whose class silently means
    nothing is exactly the unmarked span the pass exists to prevent.
    """
    if field == "class" and value not in NOTE_CLASSES:
        raise ValueError(
            f"{value!r} is not a note class — expected one of "
            f"{', '.join(NOTE_CLASSES)}")
    return value


def set_field(path: Path, line: str, field: str, value: str,
              root: Path | None = None) -> dict:
    """Set one line's field, NFD-normalizing on write.

    Exists because hand-typing a replacement for `Edit` risks producing NFC
    where the file (already run through `normalize --convert`) holds NFD —
    `ñ` typed as one keystroke is U+00F1, the file's is `n`+U+0303, and the two
    are invisible to each other under exact string match. Writing through here
    instead of Edit sidesteps the mismatch by construction: whatever comes in,
    NFD goes out, same as `normalize.py`'s one conversion point.
    """
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
    rec = data.setdefault("lines", {}).setdefault(line, {})
    text, typed = _expanded(_validated(field, value), field, root)
    rec[field] = unicodedata.normalize("NFD", text)
    _set_as_typed(rec, field, typed)
    _write_json(path, data, _src)
    return {"path": str(path), "line": line, "field": field,
            "expanded": typed or ""}


def _set_as_typed(rec: dict, field: str, typed: str | None) -> None:
    """Record the handles, or **clear the record** when there are none left.

    The clear is the half that matters. A reader that writes a handled line and
    then keys it out by hand has withdrawn the corpus claim, and a stale `as_typed`
    would leave the review UI badging a reading as a corpus match forever after —
    a provenance record that outlives the provenance is worse than none.
    """
    if field != "text":
        return
    if typed is None:
        rec.pop("as_typed", None)
    else:
        rec["as_typed"] = unicodedata.normalize("NFD", typed)


def set_fields(path: Path, values: dict, field: str,
               root: Path | None = None) -> dict:
    """Set one field on many lines, in one write. NFD on the way in, as `set_field`.

    **The turn cost of authoring is what this exists for.** A reader issues a
    command and reads its result as two separate turns, so every single-line write
    costs two of `maxTurns: 80`. `1-101` — a two-column numbered list of native
    names, where nearly every line wants Tier-1 keying — spent 23 `proposal set`,
    3 `proposal replace` and 14 `Edit` calls across 21 distinct lines, hit the cap
    exactly, and was cut off mid-correction with the page still open. Only one line
    was touched more than once, so this was not thrash: it was forty corrections
    arriving one per turn, on a page that needed forty corrections. `1-100`, the
    other structured page in the corpus, ran to 73 turns the same way.

    So the bulk form is not a convenience. A page whose every line needs authoring
    is unreadable within the budget without it, and that class of page is exactly
    the vocabulary list — the densest Tier-1 material in the book, and the material
    the whole pass is for.

    Reports which lines changed and which were already what was asked for, because
    a bulk write that says only "ok" is a bulk write nobody can check.
    """
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
    lines = data.setdefault("lines", {})
    changed, same, expanded = [], [], []
    # **Every line is resolved before any line is written.** One refused handle
    # aborts the whole call rather than leaving a page half-authored, which is the
    # rule `ocr restore` already follows for a multi-ref write and for the same
    # reason: a partial write is the state nobody can tell from a finished one.
    resolved = {}
    for line, value in values.items():
        try:
            resolved[str(line)] = _expanded(_validated(field, value), field, root)
        except ValueError as e:
            raise ValueError(f"line {line}: {e}") from e
    for line in sorted(values, key=lambda k: (len(k), k)):
        rec = lines.setdefault(str(line), {})
        text, typed = resolved[str(line)]
        new = unicodedata.normalize("NFD", text)
        (same if rec.get(field) == new else changed).append(str(line))
        rec[field] = new
        _set_as_typed(rec, field, typed)
        if typed is not None:
            expanded.append(str(line))
    _write_json(path, data, _src)
    return {"path": str(path), "field": field, "set": len(values),
            "changed": ",".join(changed), "unchanged": ",".join(same),
            "expanded": ",".join(expanded)}


def _write_json(path: Path, data: dict, original: str) -> None:
    """Serialize back in the indentation the file already used.

    These editors are aimed at `proposal.json`, which this module also authors
    at `indent=2` — but `--path` lets them target `decision.json`, which
    `review.save_decisions` writes at `indent=1`. Imposing this module's own
    format on a file it does not own turned a 10-line correction across four
    pages into a 716-line diff, which is the same failure `migrate_coords.py`
    documents for attribute number formatting: gratuitous reformatting buries
    the change that matters, and a diff nobody can read is a diff nobody checks.

    Falls back to `indent=2` when the original has no indented line to measure
    (a fresh or single-line file), so an authored proposal keeps its own shape.
    """
    indent = 2
    for ln in original.splitlines()[1:]:
        stripped = ln.lstrip(" ")
        if stripped and stripped != ln:
            indent = len(ln) - len(stripped)
            break
    trailing = "\n" if original.endswith("\n") else ""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + trailing,
                    encoding="utf-8")


def _parse_which(which: str, count: int) -> list[int]:
    """0-based occurrence indices `which` selects, out of `count` found.

    "all" (every occurrence), "first", "last", a bare 1-based index ("3"),
    or a 1-based inclusive range ("2:4"). Kept separate from the replace
    logic so a bad spec (out of range) is caught before anything is written.
    """
    if which == "all":
        return list(range(count))
    if which == "first":
        return [0] if count else []
    if which == "last":
        return [count - 1] if count else []
    if ":" in which:
        lo, hi = which.split(":", 1)
        return list(range(int(lo) - 1, int(hi)))
    return [int(which) - 1]


def replace_in_field(path: Path, line: str, field: str, old: str, new: str,
                     which: str = "all") -> dict:
    """Replace occurrence(s) of `old` with `new` in one line's field.

    The surgical alternative to `set_field`: fixing one mistyped character in
    an otherwise-correct 70-character line by retyping the whole field (the
    only option before this existed) risks introducing a *second*, unrelated
    slip while fixing the first — a hand-retyped line is exactly the kind of
    silent second error the firewall's provenance ranks exist to catch, not a
    tool anyone should have to lean on routinely. This only touches the
    occurrences named.

    `which` selects among matches of `old`, left to right, 1-based: "all"
    (default), "first", "last", "N" (the Nth occurrence), or "N:M" (the Nth
    through Mth inclusive). Matching and the write-back both happen in NFD,
    same reasoning as `set_field` — a precomposed `old`/`new` typed by hand
    and the file's own decomposed form are invisible to each other otherwise.
    Raises ValueError if `old` doesn't occur, or `which` names an occurrence
    that doesn't exist — never silently replaces fewer than asked.
    """
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
    rec = data.get("lines", {}).get(line)
    if rec is None:
        raise KeyError(f"no line {line!r} in {path}")
    text = unicodedata.normalize("NFD", rec.get(field, ""))
    old_n = unicodedata.normalize("NFD", old)
    new_n = unicodedata.normalize("NFD", new)
    if not old_n:
        raise ValueError("--old must not be empty")
    positions = []
    start = 0
    while True:
        i = text.find(old_n, start)
        if i == -1:
            break
        positions.append(i)
        start = i + len(old_n)
    if not positions:
        raise ValueError(f"{old!r} does not occur in line {line} field {field!r}")
    selected = _parse_which(which, len(positions))
    bad = [i for i in selected if i < 0 or i >= len(positions)]
    if bad:
        raise ValueError(f"{which!r} out of range: only {len(positions)} "
                         f"occurrence(s) of {old!r} found")
    new_text = text
    for idx in sorted(selected, reverse=True):
        p = positions[idx]
        new_text = new_text[:p] + new_n + new_text[p + len(old_n):]
    rec[field] = unicodedata.normalize("NFD", new_text)
    _write_json(path, data, _src)
    return {"path": str(path), "line": line, "field": field, "old": old,
            "new": new, "which": which, "occurrences": len(positions),
            "replaced": len(selected)}


def line_codepoints(path: Path, line: str | None = None,
                    field: str = "text") -> list[dict]:
    """Non-ASCII characters in a line's field, named — a typed-mark spot check.

    Not a substitute for `check()`/`resolved`: this names what is actually in
    the text (e.g. "U+0131 LATIN SMALL LETTER DOTLESS I" where U+026A ɪ was
    intended), it does not know what was *meant*. Use it to settle a doubt
    about one line while authoring, before `resolved` is even written.

    `line` omitted means every line on the page, each row carrying its own
    `line`. That is the census the action's plural form needs, and the more
    useful default besides — asking what a proposal actually contains rather
    than confirming one line at a time.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = data.get("lines", {})
    if line is not None:
        rec = lines.get(line)
        if rec is None:
            raise KeyError(f"no line {line!r} in {path}")
        return [{"line": line, **r} for r in non_ascii(rec.get(field, ""))]
    return [{"line": k, **r} for k, rec in lines.items()
            for r in non_ascii(rec.get(field, ""))]


def check(path: Path, ref: str | None = None, root: Path = Path("."),
          cohort: Collection[str] | None = None, lex=None,
          corpus: list[tuple[str, str]] | None = None, lex_all=None) -> list[dict]:
    """Per-line mismatches between what `text` contains and what `resolved` claims,
    plus apostrophe hits independent of `resolved` entirely.

    Given a `ref`, also runs the two deterministic arms of `marks.page_issues` —
    a form whose confusable the corpus almost never sets, and one word spelled two
    ways against the store. Those need the corpus, which is why they arrive with a
    `root` rather than out of the file; without a `ref` they are skipped, since
    leave-one-out cannot be applied to a page that has not said which it is.

    **Overlap with `suffix_mark_flags` is wanted, not deduplicated.** A bare `-gɪn`
    produces both that flag and a rare-form issue on the same line. They are
    independent witnesses reaching one defect from different directions — the
    suffix table from a measured shape, the rare form from a corpus share — and
    this project's governing principle asks for a second witness wherever one is
    cheap. Suppressing either would buy a shorter report with a blind spot in it.

    Five shapes, in order of how actionable they are: a straight apostrophe
    anywhere in `text` (`detectors.apostrophe_flags` — not gated on
    `resolved` at all, and not gated on the token looking Tier-1 either;
    every straight apostrophe in the corpus checked out either an English
    possessive that should be curly or a mistyped Tier-1 stress mark, never
    a genuine reading, so this fires unconditionally); a token matching a
    known dot-prone suffix shape, unmarked (`detectors.suffix_mark_flags` —
    a table of base+mark+suffix-continuation entries keyed to keying_spec.md
    §5.1's measured bare-vs-marked skews, also unconditional); `text` carries
    notation with no `resolved` field at all
    (nothing to check against — the skill's contract was skipped); `resolved`
    names a codepoint absent from `text` (the field describes a reading the
    characters do not contain, so either was mistyped); `text` carries a
    codepoint `resolved` never mentions (the field is incomplete, or the
    character is the wrong one).
    """
    apostrophe_issues = {
        "english": "straight apostrophe on an English token (§1: the book "
                   "sets curly ’ in English prose too — same rule as the "
                   "quote pair; not Tier-1, so no licensing exception applies)",
        "unlicensed": "apostrophe inside a Tier-1 form (§2.1: no licensed "
                      "position — a mistyped stress mark U+02CA)",
    }
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    # **Which arms run is decided by the target, not by a flag.** Four of them ask
    # a question about one page's lines — is this index in the ALTO, did a terminal
    # stop appear that the recognizer's draft lacked, do the footnote markers form
    # a run — and a caption proposal has no page, no line indices and no footnotes.
    # Run against 395 captions they would produce 395 findings and no information.
    # What survives is everything about the *text*: apostrophes, marks, resolved
    # against text. Those are the same questions whatever the key means.
    captions = caption_keyed(data)
    if captions:
        out += _orphan_caption_issues(data, root)
    else:
        out += _segmenter_missed_issues(data)
        out += _footnote_issues(data)
        if ref is not None:
            from .marks import page_issues

            out += _orphan_line_issues(data, ref, root)
            out += _added_terminal_punctuation(data, ref, root)
            out += page_issues(path, ref, root, cohort, corpus)
    # Built once for the page and only when some note could name a key at all —
    # `index` walks the whole corpus, and most pages carry no such note.
    # Leave-one-out or nothing, and the batch is the unit: see
    # `_named_key_issues`. `cohort` is every ref in this run, so a form two
    # siblings introduced cannot come back as either one's prior.
    #
    # A caller checking several refs should build the loader once and pass it:
    # the cohort is constant across a run, so every page would otherwise walk the
    # corpus for an index identical to its siblings'. One walk is 2.4s at 645
    # pages. `run_check` does this; the default keeps a single-page call working.
    if lex is None and ref is not None:
        lex = _lexicon_loader(root, cohort or {ref})
    # **Two indexes, and they are not interchangeable.** `_named_key_issues` asks
    # what an *independent* witness would have offered, so its index excludes the
    # cohort. `_handle_issues` asks whether a handle the reader used still
    # resolves — a provenance check, not a prior — and answering that against a
    # leave-one-out index would report a legitimate handle as broken whenever its
    # key happens to come from a sibling. So this one sees everything.
    if lex_all is None:
        lex_all = _lexicon_loader(root, ())
    for idx, rec in sorted(data.get("lines", {}).items(), key=key_order):
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        nclass, note = rec.get("class", ""), rec.get("note", "")
        if nclass and nclass not in NOTE_CLASSES:
            out.append(issue(idx, f"unknown note class {nclass!r}",
                             detail="one of " + ", ".join(NOTE_CLASSES)))
        if nclass and not note:
            out.append(issue(idx, "note class with no note",
                             detail=f"class {nclass!r} asserts nothing"))
        # Advisory, not a defect, though it is plainly satisfiable: the class
        # only decides which badge the note wears, and the part that fixes the
        # `Kuvár` failure — a noted line is never dimmed — happens without it.
        # Gating on it would make an unclassifiable observation cost the reader
        # its note, which is the opposite of the point.
        if note and not nclass:
            out.append(issue(idx, "note with no class (which of "
                             + "/".join(NOTE_CLASSES) + " is it?)",
                             severity=ADVISORY))
        out += _handle_issues(idx, rec, text, root, lex_all)
        out += _named_key_issues(idx, rec, text, root, lex)
        for hit in apostrophe_flags(text):
            out.append(issue(idx, apostrophe_issues[hit["kind"]],
                             token=hit["token"],
                             context=hit.get("context", hit["token"])))
        for hit in suffix_mark_flags(text):
            out.append(issue(idx, f"bare suffix, expected "
                             f"{hit['expected']!r} (§5.1: strong corpus-wide "
                             "bare-vs-marked skew for this shape) — check for a "
                             "dropped mark", token=hit["token"],
                             severity=ADVISORY))
        # **Scoped to what the reader actually keyed.** `resolved` exists so a
        # reader documents the marks it settled at the raster; a handle is a
        # declaration that it settled none of them, the corpus having supplied the
        # glyphs whole. Demanding a `resolved` for those would ask the reader to
        # narrate a reading that is not its own — and an invented account of how a
        # mark was decided is worse than no account, since it is indistinguishable
        # from a real one. The hand-keyed remainder still answers for itself.
        present = set(_notation_codepoints(_keyed_by_hand(rec, text)))
        if not present:
            continue
        stated = _stated_codepoints(resolved)
        if not stated and not resolved:
            out.append(issue(idx, "notation with no resolved field",
                             detail=f"in text: {_cps(present)}"))
            continue
        extra_in_text = present - stated
        extra_in_resolved = _stated_but_absent(stated, text)
        if extra_in_text or extra_in_resolved:
            sides = []
            if extra_in_text:
                sides.append(f"in text not resolved: {_cps(extra_in_text)}")
            if extra_in_resolved:
                sides.append(f"in resolved not text: {_cps(extra_in_resolved)}")
            out.append(issue(idx, "resolved/text mismatch",
                             detail="; ".join(sides)))
    return out


def _segmenter_missed_issues(data: dict) -> list[dict]:
    """`segmenter_missed` carrying anything at all. A defect, unconditionally.

    **The field is illegal.** It let a reader record printed matter the segmenter
    dropped, inside the proposal, as a finding travelling with the reading. That
    made the proposal the place a segmentation fault was reported, and a reading
    the thing that carried it — so a line's identity could be argued from a
    transcriber's note rather than from a box. The line store is the upstream
    source of truth: `mz/ocr/` patched by the human corrections a zone editor
    draws into `gt/lines/`, every line id anchored there, provenance running
    forward from it. Nothing downstream of that store may propose a line into
    existence, and a proposal is downstream.

    Finding text with no box is still worth finding — it is simply **not the
    transcriber's to correct.** It is upstream human action: a human draws the
    band a box in `harness ocr edit`, the index exists from then on, and the page
    is re-read against a store that now holds it. So a reader reports it *to the
    human, in its report*, and keys nothing; the proposal stays a reading of the
    boxes that exist.

    An **empty** block is inert legacy, not a finding — `fix` strips it silently
    and nothing gates. Only content fires, because only content is a reading that
    went somewhere it may not go.
    """
    block = data.get("segmenter_missed")
    if not block:
        return []
    return [issue("-", "`segmenter_missed` is illegal — the line store is the "
                       "upstream source of truth and a proposal may not propose "
                       "a line into existence. Printed matter with no box is "
                       "upstream human action: report it to the human, key "
                       "nothing, and let a box be drawn in `harness ocr edit` "
                       "before the page is read against it.",
                  detail=f"block holds {len(block)}")]


def _added_terminal_punctuation(data: dict, ref: str, root: Path) -> list[dict]:
    """A line ending in punctuation the machine draft does not end in.

    **The commonest fabrication this pass produces.** Nine line-final commas over
    two batches — `1-079`, `1-092`, `1-099`, then `1-103` L4, `1-104` L33, `1-107`
    L3, `1-109` L35, `1-110` L3 and L24 — none of them on the page, and none of
    them in `mz/ocr` either, so no recognizer artifact carried them in. Six of the
    ten pages in one batch, past readers who had answered every advisory they were
    given, which is what says the rule alone will not hold it.

    Why they appear is not settled. They sit at the end of the value, beside the
    closing quote, which reads like a serialization slip — but three of the four
    inspected sat in a record with no following field, so there was no separator to
    bleed in from. The *shape* is what is stable: always terminal, never mid-line,
    always absent from the draft. So the detector keys on the shape and takes no
    position on the cause.

    **Terminal only, and against the draft rather than against a rule of prose.**
    A comma the reader restores because the recognizer dropped one is a real
    correction and must stay possible; what makes this checkable is that CATMuS is
    a competent witness to ASCII punctuation, so a disagreement is worth one look
    at `@100` — the length of the crop is not a judgement call there.

    A defect when the line says nothing about it, an advisory once the line carries
    a `note`: the gate is satisfiable either way — look, then delete the mark or
    say what you saw — and a reader that looked and found the comma genuinely
    printed must not be stuck. This is `_footnote_issues`'s `explained` shape, for
    the same reason.
    """
    lines = data.get("lines")
    if not isinstance(lines, dict) or not lines:
        return []
    from .lines import DEFAULT_STORE, alto_for_lines, page_lines
    try:
        alto = alto_for_lines(ref, root, DEFAULT_STORE)
    except Exception:
        return []
    if not alto.exists():
        return []
    draft = {str(r["index"]): (r.get("text") or "") for r in page_lines(alto, root)}
    out = []
    for k, rec in sorted(lines.items(), key=lambda kv: (len(kv[0]), kv[0])):
        text = (rec or {}).get("text", "").rstrip()
        was = draft.get(str(k), "").rstrip()
        # Only when the draft has a line to disagree with: an empty one is a
        # recognizer that returned nothing, which is no witness at all.
        if not text or not was or text[-1] not in TERMINAL_PUNCTUATION:
            continue
        if was and was[-1] == text[-1]:
            continue
        # The bodies have to match apart from the mark, or this is not "a comma
        # was added" but "the line was rekeyed", which the reader is entitled to
        # do and which this detector has no opinion about.
        if text[:-1].rstrip() != was:
            continue
        out.append(issue(k, f"line ends {text[-1]!r}, the draft does not — the "
                         "commonest fabrication on this pass is a line-final "
                         "comma that is on no page and in no draft. Look at "
                         "`@100` before keeping it",
                         token=text[-1], context=text[-28:],
                         severity=ADVISORY if (rec or {}).get("note") else DEFECT))
    return out


def _orphan_line_issues(data: dict, ref: str, root: Path) -> list[dict]:
    """Proposal lines with no `TextLine` in the store to hold them.

    **A proposal is keyed by the ALTO's line indices**, and `restore` joins on
    them: a key naming an index the store does not have describes text with no
    box, which is the dropped-line case wearing a different hat. Ground truth is a
    correspondence between a box and its contents, so a reading that has nowhere
    to go is not a reading. It is upstream human action — a box drawn in `ocr
    edit` — and never a line here.

    A defect rather than an advisory because there is nothing to weigh: the index
    either exists or it does not, and `restore` will silently drop what it cannot
    join. Silently is the problem. `1-037` produced the neighbouring version of
    this — a folio appended to the running title's own `text` — which this cannot
    see, since that key is a real index; the reader contract carries that half.

    Resolved through the view *and the corrections overlay*, so a page reads
    against whichever store is current — `mz/ocr/` before a restore and `gt/ocr/`
    after — plus any line a human has since drawn in `ocr edit`. A keyed
    correction is therefore not an orphan: the index exists, which is the whole
    point of giving the line a box. A page with no ALTO at all is skipped rather
    than reported — absent is not the same as wrong, and every line would fire.
    """
    lines = data.get("lines")
    if not isinstance(lines, dict) or not lines:
        return []
    from .lines import DEFAULT_STORE, alto_for_lines, page_lines
    try:
        alto = alto_for_lines(ref, root, DEFAULT_STORE)
    except Exception:
        return []
    if not alto.exists():
        return []
    have = {str(r["index"]) for r in page_lines(alto, root)}
    if not have:
        return []
    return [issue(k, "line index is not in the store — a proposal is keyed by "
                     "the ALTO's line indices and `restore` joins on them, so "
                     "this text has no box to land in. If it is printed matter "
                     "the segmenter missed, that is upstream human action and "
                     "not yours to correct: drop the key, say what you saw in "
                     "your report, and a human gives the band a box in `harness "
                     "ocr edit` before the page is read again.",
                  context=(lines[k] or {}).get("text", "")[:60],
                  detail=f"store holds {len(have)} lines")
            for k in sorted(lines, key=lambda s: (len(s), s))
            if str(k) not in have]


def caption_keyed(data: dict) -> bool:
    """Whether this proposal is the caption pass's rather than a page's.

    **Read off the keys, not off a flag.** A page proposal is keyed by the ALTO's
    line indices and a caption proposal by `<ref>|<zone-suffix>`; the two key
    spaces are disjoint by shape, so the file already says which it is. A
    `--captions` switch beside a `--path` that already names one file would be a
    second way to say the same thing, and the two could then disagree.

    This matters beyond tidiness: half of `check`'s arms resolve a key against one
    page's `gt/ocr/` lines, and every one of them would fire on all 395 captions.
    """
    lines = data.get("lines")
    return bool(isinstance(lines, dict) and lines
                and all("|" in k for k in lines))


def key_order(kv):
    """Sort proposal keys, whichever space they are in.

    Line indices sort numerically; caption keys sort by ref then zone suffix, both
    zero-padded in the store, so lexical order is reading order. Without this a
    plain `int(kv[0])` raises on the first caption key it meets — which it did, in
    three places here and three more in `normalize.py`, because the line pass's key
    space was the only one when they were written. Public and shared for that
    reason: a fourth copy is a fourth chance to forget.
    """
    return (0, int(kv[0]), "") if kv[0].isdigit() else (1, 0, kv[0])


def _orphan_caption_issues(data: dict, root: Path) -> list[dict]:
    """Caption keys naming no `GraphicZone-FigDesc` in `gt/fig/`.

    `_orphan_line_issues` one key space over, and for the identical reason: a
    reading whose block does not exist has nowhere to land, and `fig restore` would
    silently drop it. The block id's last field is the foreign key the whole figure
    track turns on — `figures.save_figs` preserves ids rather than re-minting them
    precisely so this join keeps holding.

    A page with no figure ALTO is reported rather than skipped, unlike the line
    case: the caption store is one flat file over the whole corpus, so a key naming
    an absent page is a typo, never the ordinary state of an unread page.
    """
    lines = data.get("lines")
    if not isinstance(lines, dict) or not lines:
        return []
    from .figures import FIGDESC, zone_suffix, zones
    have: dict[str, set[str]] = {}
    out = []
    for k in sorted(lines, key=lambda s: s):
        ref, _, suffix = k.partition("|")
        if ref not in have:
            try:
                have[ref] = {zone_suffix(b["id"]) for b in zones(ref, root)
                             if b["label"] == FIGDESC}
            except ValueError:
                have[ref] = set()
        if suffix in have[ref]:
            continue
        out.append(issue(
            k, "names no GraphicZone-FigDesc in gt/fig/ — a caption is keyed by "
               "its block's id suffix and `fig restore` joins on it, so this text "
               "has no block to land in. Either the key is mistyped or the box "
               "was withdrawn; check `harness fig check` for the page, and do not "
               "invent a block for it.",
            context=(lines[k] or {}).get("text", "")[:60],
            detail=f"{ref} holds {len(have[ref])} caption block(s)"))
    return out


def _footnote_issues(data: dict) -> list[dict]:
    """`detectors.footnote_report` turned into proposal-check's issue records.

    The contract the editor set: markers may pass **unexplained** so long as
    they form a continuous run from 1 and each occurs at least twice; a page
    that fails either wants a written reason instead. Both failure modes have
    legitimate causes — a note whose reference and text straddle a page seam
    breaks the pairing without anything being miskeyed — so this reports and
    asks, and never refuses. That is a weaker tier than `restore`'s mark-licence
    refusal on purpose: an unlicensed mark is a sequence the notation does not
    contain, whereas an unpaired marker may simply be a page boundary.

    The explanation goes in a page-level `footnotes` key (a sibling of
    `contamination`, same shape of claim: something about the page as a whole
    that the line records cannot carry). Its presence **annotates** the issue
    rather than deleting it, so the reason still reaches the adjudicator instead
    of vanishing into a silent pass — it is appended to `detail` behind an
    `explained:` marker, since this record shares one key set with the other five
    detectors (`ISSUE_FIELDS`) and cannot carry a field of its own.
    """
    texts = [rec.get("text", "") for _, rec in
             sorted(data.get("lines", {}).items(), key=key_order)]
    rep = footnote_report(texts)
    problems = []
    if rep["gaps"]:
        problems.append(f"marker run has gaps: missing {rep['gaps']} from 1..{max(rep['counts'])}")
    if rep["singletons"]:
        problems.append(f"marker(s) {rep['singletons']} occur once; each is printed "
                        "twice (body reference + note opener)")
    for op in rep["ascii_openers"]:
        problems.append(f"line {op['line']} opens with bare ASCII {op['digit']!r} — "
                        f"footnote markers are keyed as the superscript digit, never "
                        f"the plain one: {op['text']!r}")
    # The locants the pairing arms were told to ignore, reported at the advisory
    # tier. They cannot gate — being unpaired is what a locant *is*, so a gate
    # here is the one `1-137` failed by mis-keying `a¹` to `a1`. But the
    # exclusion rests on a bracket and a neighbouring letter, and a genuine
    # marker wearing that shape would vanish out of the count in silence, so it
    # says what it dropped and lets the adjudicator look.
    out = [issue(lo["line"], "figure locant, not a footnote", severity=ADVISORY,
                 token=f"{lo['digit']}", context=lo["text"],
                 detail="a raised numeral labelling a figure sub-part anchors no "
                        "note; excluded from the marker count. Key it as printed.")
           for lo in rep["figure_locants"]]
    if not problems:
        return out
    explained = (data.get("footnotes") or {}).get("note") if \
        isinstance(data.get("footnotes"), dict) else data.get("footnotes")
    detail = "; ".join(problems)
    if explained:
        detail += f" — explained: {explained}"
    return out + [issue("-", "footnote markers", detail=detail)]


def fix(path: Path, root: Path | None = None) -> dict:
    """Apply the one unambiguous class of correction: a single wrong mark.

    Only touches a line where exactly one notation codepoint in `text` has no
    match in `resolved` **and** exactly one codepoint named in `resolved` has
    no match in `text` — a 1-for-1 swap with nothing else to decide between.
    Composes the replacement back to NFC-free NFD (the corpus form) rather than
    guessing a precomposed glyph. Anything less clean (zero or more than one
    of either side) is left alone and still reported, since a guess here is
    exactly what the firewall's reasoning forbids elsewhere.

    A medial ASCII A/E/I/L never gets auto-replaced, even in an otherwise-clean
    1-for-1 — it still *counts* toward `present` (via `_notation_codepoints`),
    because that accounting is what makes a line with two independent errors
    correctly report as two dangling items instead of a false clean swap. But
    which small-cap an ASCII capital was meant to be is a judgement call in a
    way a mistyped combining mark is not (ring below vs dot below is a shape
    slip; 'A' vs 'ᴀ' vs a genuine capital is not), so the swap itself is left
    to a human — `check()` still flags it via the same mismatch report.
    """
    _src = path.read_text(encoding="utf-8")
    data = json.loads(_src)
    changed = []
    if "segmenter_missed" in data and not data["segmenter_missed"]:
        # Inert legacy: the field is illegal but an empty one carries no reading,
        # so it folds away silently rather than gating. A non-empty block is a
        # human's to disposition and `check` reports it — never stripped here,
        # which would delete the finding along with the field.
        del data["segmenter_missed"]
        changed.append({"line": "-", "replaced": "segmenter_missed", "with": ""})
    # **Handles are expanded here because this is where the page is.** The
    # mechanism used to live only in `set_field`, and over one measured day of 63
    # readers it fired zero times: every one of them authored `proposal.json` with
    # `Write` (63 whole-file writes against 16 `proposal set` calls, all of those
    # later edits), so a `{Mec^i'wmi_n}` typed into the file per the contract would
    # have survived into the store as a literal brace. Four readers looked a form
    # up, got its key, and retyped the glyphs by hand — which is the act the handle
    # exists to replace, and the act that produced three ᴇ U+1D07 → ᴀ U+1D00 slips
    # on one name across three pages that day.
    #
    # `fix` runs on every page and already writes, so putting the expansion on this
    # path costs no new step in the loop and no new instruction to remember.
    #
    # Before the codepoint swap below, deliberately: expansion is what makes `text`
    # ratified, and the swap reconciles `text` against `resolved`. Reconciling a
    # line that still holds a brace would compare a handle to a codepoint list.
    for idx, rec in data.get("lines", {}).items():
        text, typed = _expanded(rec.get("text", ""), "text", root)
        if typed is not None:
            rec["text"] = unicodedata.normalize("NFD", text)
            _set_as_typed(rec, "text", typed)
            changed.append({"line": idx, "replaced": typed, "with": rec["text"]})

    for idx, rec in data.get("lines", {}).items():
        text = rec.get("text", "")
        resolved = rec.get("resolved", "")
        if not resolved:
            continue
        present = set(_notation_codepoints(text))
        stated = _stated_codepoints(resolved)
        extra_in_text = present - stated
        extra_in_resolved = _stated_but_absent(stated, text)
        if len(extra_in_text) != 1 or len(extra_in_resolved) != 1:
            continue
        wrong = chr(next(iter(extra_in_text)))
        if wrong in "AEIL":
            continue  # medial ASCII cap: flagged by check(), never auto-swapped
        right = chr(next(iter(extra_in_resolved)))
        nfd = unicodedata.normalize("NFD", text)
        if nfd.count(wrong) != 1:
            continue  # ambiguous position; do not guess which one
        # NFD on the way out, as the docstring has always claimed: `right` comes
        # from a `resolved` field and may be a precomposed sort, and substituting
        # it raw writes NFC into an NFD corpus for `corpus normalize` to find
        # later — if anyone runs it.
        new_text = unicodedata.normalize("NFD", nfd.replace(wrong, right))
        rec["text"] = new_text
        changed.append({"line": idx,
                        "replaced": f"U+{ord(wrong):04X}", "with": f"U+{ord(right):04X}"})
    if changed:
        _write_json(path, data, _src)
    return {"path": str(path), "changed": changed}
