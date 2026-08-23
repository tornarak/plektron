"""Corpus normal-form and lookalike gate.

`keying_spec.md` section 1 has declared **NFD, corpus-wide** with a verification
one-liner for as long as the spec has existed, and nothing ever ran it. This is that
one-liner promoted to something a pre-commit hook can call, which matters because the
drift it was written to catch had already happened: `data/readings.md` held both
encodings of the same glyph (17 precomposed `ê` against 13 decomposed, and similarly
for `ñ` and `ä`), so exact comparison between it and any other store silently failed.

**NFD, and never NFKC.** NFKC has a compatibility decomposition for two inventory
glyphs and destroys them outright — U+1D4B (113 occurrences) folds to plain U+025B,
U+02D9 (11) folds to space + combining dot. A `normalize()` call here without an
explicit form, or with the "more thorough" one, is a silent corpus-wide glyph
substitution. Name the form every time.

Five rules, all mechanical:

  nfd          every scoped file is NFD-conformant.
  marks        every combining mark sits on a base its licence covers (§2.6).
  lookalikes   no scoped file carries a lookalike with no legitimate English use.
  spacing      no run of 2+ spaces survives between non-space characters, and no
               space sits immediately before `;`, `:`, `,`, `!`, or `?` (§2.9).
  footnotes    a page's footnote markers form a continuous run from 1, each occurs
               at least twice (body reference + note opener), and no line opens
               with a bare ASCII digit where a superscript was meant.

`footnotes` reports alongside `lookalikes` and for a related reason: both of its
invariants break legitimately at a page seam, where a note's reference and its text
land on different pages, so a hit is a page to look at rather than a proven defect.

`spacing` blocks alongside `nfd` and `marks`, where `lookalikes` only reports — same
split as below: a lookalike needs a human ruling on what the page prints, so it is
firewalled and can only ever be a worklist line; a double space after a sentence
period or a thin space before a semicolon has no such ruling to make; §2.9 already
settled both as typesetting artifacts with no lexical content, so there is nothing
being pre-empted by collapsing them. Safe to run on raw file source for the same
reason NFD is: neither pattern occurs in JSON or XML structural whitespace (an
indented line's leading spaces are preceded by a newline, not a non-space
character, so the multi-space regex never touches indentation), so this cannot
reformat a file's own syntax the way a blind global collapse would.

The middle one **blocks**, alongside `nfd`, where the third only reports — and the
split is the difference between an error and a question. A lookalike needs a human
ruling on what the page prints, so it is firewalled and can only ever be a worklist
line. An unlicensed mark has no such ruling available: `ɪ` + breve or `j` + breve is
not a hard choice between two glyphs, it is a sequence the notation does not contain,
so nothing is being pre-empted by refusing it. See `detectors.MARK_LICENSE` for why
`j` is the reason this is enforced in code rather than trusted to a spec table.

Note what `convert` does **not** do with it: nothing. Fixing an unlicensed mark means
choosing a different glyph, and a tool that picks the intended one is a tool adopting
a glyph identity on its own authority. The gate names the occurrence; a human keys it.

The second rule is *unscoped* by necessity, and that needs saying because the ASCII
policy is not. Under the Tier-1-scoped policy the four curly quotes are legitimate in
English prose, and U+2019-inside-Tier-1 is enforced against the TEI by
`validate.LOOKALIKE_GREPS`, where the language is actually known. But `data/readings.md`
carries no language markup at all, so nothing here can tell a caption's English from
its Chukchee. What survives that limitation is the set of characters with no
legitimate use in *either*: the confusable modifier letters, and `g`+U+0307 for
`g`+U+0323. Those are reportable wherever they sit.

Reported as worklist, never as error. Each one needs a human ruling on what the page
prints, and that is firewalled — see `keying_spec.md` section 1.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .detectors import apostrophe_flags, footnote_report, unlicensed_marks
from .parallel import ptrack
from .proposal_check import key_order

# §2.9: sentence-ending double space and thin space before ;/:/,/!/? are typesetting
# artifacts with no lexical content — mechanical, print-invariant, corpus-wide.
# The lookbehind/lookahead require a non-space neighbor on each side, so a line's
# leading indentation (preceded by a newline) never matches.
#
# `!` and `?` joined the class late, and the gap is why they had to: the rule was
# gated for `;:,` and unenforced for the other two, so drift there was invisible to
# `check` and `normalize` alike. 1535 `!`/`?` tokens sat closed-up in `gt/ocr/` — not
# because the press closed them but because every reader did, unbidden and unrecorded,
# until one on `3-041` read §2.9's list as exhaustive and preserved `eh !` on L35 while
# closing `daughter !` on L34, inconsistent with itself one line away. The enumeration
# here and the one in the spec are the same list, and neither may narrow without the
# other.
#
# A **run** of `!`/`?` is excluded, and that is not fussiness: `data/readings.md` writes
# an unknown figure number as `(??/???? ??/????)`, where the space before each `??` is
# notation and not typesetting. Widening the class without the lookahead made
# `--commit` willing to rewrite that file's placeholders — a gate corrupting a store it
# was only meant to measure. `;:,` need no such guard because no notation repeats them.
_MULTI_SPACE = re.compile(r"(?<=\S) {2,}(?=\S)")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([;:,]|[!?](?![!?]))")

# A necessary condition for either pattern above, in one pass and **without
# lookaround** — the same characters, matched rather than asserted.
#
# It exists to answer "is there anything in this file at all", which is a different
# question from "where", and the two want different regexes. Over the corpus it
# rejects 448 of 449 files, so the per-line walk in `_spacing_hits` almost never
# runs. Measured, because two obvious spellings are both worse: `search()`ing the
# real lookbehind pattern costs 278 ms against this one's 190 ms, and a plain
# substring precheck is a thousand times cheaper still but filters *nothing* — `"  "`
# is in every indented JSON file in the corpus, which is exactly why the real pattern
# demands a non-space on each side.
_SPACING_ANY = re.compile(r"\S {2,}\S|[ \t][;:,!?]|[ \t][¹²³⁴⁵⁶⁷⁸⁹]|\"[¹²³⁴⁵⁶⁷⁸⁹]\S")

# §2.10 marker spacing, and it is **two rules with opposite signs**, which is why
# neither is `_SPACE_BEFORE_PUNCT` with a wider class.
#
# A body reference sets tight against whatever precedes it — `mouth.¹`, `tales¹`,
# `Steller,¹`. An opener sets marker, space, text — `¹ See, for instance`. Measured
# over `gt/ocr/` the day this was written: 225 tight against 13 spaced in the body,
# 208 spaced against 1 tight in openers. Both leans are the print's, not a keyer's
# preference.
#
# **Position is read off the quote, not off a parse** — `convert`'s safety argument
# is that it rewrites raw source and never parses, so the two file shapes have to be
# recognised by their punctuation. Both put the transcribed line immediately after a
# `"`: JSON as `"text": "…` and ALTO as `CONTENT="…`. So a marker preceded by `"` is
# at the head of a line and is an opener; anything else is a reference. The
# lookbehind excludes `"` for exactly that reason — without it the opener rule and
# the body rule would fight over the same character.
#
# The thirteen body offenders included `Nelson ¹)`, `Kiˊhi ¹)` and `[albino] ¹)`,
# which the print really does space and which were kept spaced deliberately, to stop
# the marker being lumped into the Tier-1 token beside it. That fear was unfounded:
# `detectors.EDGE_PUNCT` already carries `¹²³⁴⁵⁶⁷⁸⁹` and `str.strip` eats from both
# ends, so `Kiˊhi¹)` and `Kiˊhi` tokenize identically. Closing the space costs the
# lexicon nothing, which is the whole reason this rule can be mechanical.
_MARKER_TIGHT = re.compile(r"(?<=[^\s\"])[ \t]+([¹²³⁴⁵⁶⁷⁸⁹])")
_MARKER_OPENER = re.compile(r"(?<=\")([¹²³⁴⁵⁶⁷⁸⁹])(?=\S)")

# **The body rule does not run on a line that opens a note.** Reading position off
# the quote settles the *first* marker on a line and says nothing about a second, and
# short notes are set run-in: `2-018` L33 prints `¹ Regarding … see Chapter XVII.` and
# then, after a wide gap, `² See p. 42.` — two openers, one line. The second has text
# before it, so `_MARKER_TIGHT` claimed it as a body reference and `--commit` would
# have written `XVII.² See p. 42.`, gluing note 2's opener onto note 1's text. It was
# caught in the 2-003..2-022 batch only because the adjudicator had *already* spaced
# that marker by hand: the gate was proposing to revert a human correction.
#
# `. ` + marker + ` ` + text is structurally identical in `XVII. ² See` and in a
# genuinely spaced body reference like `mouth. ¹ The next`, so no local pattern tells
# them apart. What does is the line: a body line never opens with a marker. So the
# discriminator stays "read it off the quote" — it just reads the *line's* first
# marker rather than each marker's own left-hand neighbour, and where that says
# "note", the body rule has no business on the line at all.
#
# This narrows the licence rather than adding a competing rule. What it gives up is
# tightening a body reference inside a footnote's own text, which the store does not
# attest — against a corruption that is attested once in twenty pages.
_OPENER_LINE = re.compile(r"\"[¹²³⁴⁵⁶⁷⁸⁹]")

# A proposal's or decision's `note` and `resolved` are editorial commentary *about*
# the page, not print-reproduction content, so §2.9 does not reach them: an
# adjudicator's sentence is not a line of Bogoras and there is no printed spacing
# for it to be drifting from. `_quote_hits` and `_apostrophe_hits` already scope
# this way, and by the cleaner route — they parse the JSON and read `text`. These
# two cannot, because `convert`'s whole safety argument is that it rewrites raw
# source and never parses (see its docstring), so they recognise the field by the
# shape of its line instead. Sound because these files are written by
# `json.dump(indent=…)`, one field per physical line, with any newline inside a
# value escaped rather than set.
#
# `1-194`'s note is the case: "Woke Nonsense  Line" reported as corpus drift and
# `--commit` would have rewritten the human's prose to match a rule about print.
_JSON_COMMENTARY = re.compile(r'^\s*"(?:note|resolved)":')


def _skip_line(line: str, commentary: bool) -> bool:
    """Lines no spacing rule applies to: `#` comments, and — in JSON — the two
    commentary fields. `commentary` is the caller saying "this file has them"."""
    return bool(line.lstrip().startswith("#")
                or (commentary and _JSON_COMMENTARY.match(line)))


def _fix_spacing(text: str, commentary: bool = False) -> str:
    """Collapse §2.9 spacing drift, line by line, skipping `#`-comment lines.

    Line-by-line (not a whole-text regex) so a `#`-prefixed line — `lexicon_extra.txt`'s
    own documented comment convention — can be left untouched: its comments include a
    multi-space-indented usage example, which is code formatting, not sentence spacing,
    and the blanket regex does not know the difference.
    """
    out = []
    for line in text.split("\n"):
        if _skip_line(line, commentary):
            out.append(line)
            continue
        line = _MULTI_SPACE.sub(" ", line)
        line = _SPACE_BEFORE_PUNCT.sub(r"\1", line)
        if not _OPENER_LINE.search(line):
            line = _MARKER_TIGHT.sub(r"\1", line)
        line = _MARKER_OPENER.sub(r"\1 ", line)
        out.append(line)
    return "\n".join(out)


def _spacing_hits(text: str, commentary: bool = False) -> list[dict]:
    """Every spacing-drift occurrence, located. One record per match, not a tally —
    same reasoning as `_lookalikes`: a count is not something a reader can act on."""
    # **Whole-text probe first.** The line walk exists for the `#`-comment skip, so
    # it cannot be replaced — but it runs over every line of every scoped file, and
    # the corpus is overwhelmingly clean. One C-level search over the file answers
    # "is there anything here at all" and lets the common case skip the loop
    # entirely. A hit still has to be located line by line, since a match confined
    # to comment lines is not a hit.
    if not _SPACING_ANY.search(text):
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _skip_line(line, commentary):
            continue
        pats = [(_MULTI_SPACE, "2+ spaces (§2.9 sentence spacing)"),
                (_SPACE_BEFORE_PUNCT, "space before ;/:/,/!/? (§2.9)"),
                (_MARKER_OPENER, "no space after a note opener (§2.10)")]
        if not _OPENER_LINE.search(line):
            pats.insert(2, (_MARKER_TIGHT, "space before a footnote marker (§2.10)"))
        for pat, label in pats:
            for m in pat.finditer(line):
                hits.append({"issue": label, "line": lineno,
                            "token": _token_at(line, m.start())})
    return hits

# Directories whose XML is corpus, and the individual data files. Prose that *quotes*
# glyph examples is out of scope, and by two different mechanisms worth seeing
# together: root-level *.md (CLAUDE.md, keying_spec.md) are excluded by not being
# listed, and `.claude/skills/*/SKILL.md` — which now carries the collation rules and
# the same kind of examples — is outside every glob here to begin with. Either would
# fail a gate meant for the corpus text itself.
#
# **`ocr/` is deliberately absent, and `gt/ocr/` is what stands in its place.** The
# view used to be listed first, on the reasoning that it and `gt/ocr/` were one
# store under two names and the dedupe below would fold them together. That stopped
# being true when `ocr predict` gave the view a second real store to resolve into:
# a link now reaches `mz/ocr/`, raw recognizer output, and the corpus gate would
# then **block on a machine store** — which is the thing `zones check --store mz`
# exists to prevent on the other side of the house. It is not a near miss. One
# predicted page contributes 978 `spacing` hits, and they are not even text: they
# are the whitespace kraken sets inside `<SP>` attributes. Naming the real store
# keeps every gt page in scope, since the view never held anything else.
SCOPE_GLOBS = ("gt/ocr/*.xml", "gt/fig/*.xml", "tei/*.xml",
               # The entity store is hand-authored and holds two kinds of text
               # at once: gloss prose, which is English and sets curly quotes,
               # and alias forms, which may be Tier-1 and where a straight
               # apostrophe is the licensed stress mark. Both need NFD — a
               # alias the store spells precomposed silently fails to match a
               # page that spells it decomposed, and a silent miss is the
               # failure class the whole project is organised against — so the
               # NFD arm sweeps the file whole and the two prose arms skip the
               # table rows. See `_is_entity`.
               "entities/*/*.md",
               "data/readings.md", "data/*.json", "data/lexicon_extra.txt",
               # decision.json is an editorial act — the adjudicated record that
               # `restore` actually writes to gt/ocr/ — so it stays in the default
               # sweep alongside the rest of the corpus. `save_decisions` normalizes
               # on write, so this is a regression check, not a live worklist.
               "review/*/decision.json",
               # The caption pass's pair, keyed `<ref>|<suffix>` rather than by line
               # index — one file each rather than one per page, because a caption
               # is short and most pages hold one (see `captions.py`).
               #
               # **Both, and the proposal is not optional here the way a line
               # proposal is.** That one reaches `gt/ocr/` only through a decision,
               # and `save_decisions` folds on the way; this one is *compared byte
               # for byte against `data/readings.md`* by `fig witness`, which is the
               # whole reason it exists, and a comparison between two normal forms
               # of the same glyph is the exact drift this module was written for —
               # `readings.md` itself once held 17 precomposed `ê` against 13
               # decomposed. It was left out first on the reasoning that `proposal
               # fix` folds the file. It does not: `fix` swaps one mark against
               # `resolved` and touches nothing else, so the reading sat outside
               # every NFD gate there is until a reader hit it and said so.
               "review/captions/proposal.json",
               "review/captions/decision.json")

# `proposal.json` is a model's pre-adjudication reading, checked on demand
# (`--path review/PP-NNN/proposal.json`, part of the rebuild-groundtruth loop
# itself) rather than swept by the bare corpus-wide walk. It was in SCOPE_GLOBS
# once, after a `1-151` proposal kept a precomposed ê inside a Tier-1 form with
# the file's own note correctly spelling it e+U+0302 — nothing normalized a
# hand-authored proposal at all back then. But a proposal for an
# already-restored, already-adjudicated page is dead weight, not live state:
# its worklist-class findings (apostrophe licensing chief among them) are
# exactly the "human reading judgement, never auto-fixed" class documented in
# keying_spec.md, so on a finished page they can never be resolved and just
# accumulate as permanent corpus-wide noise (`3-004` is why this line exists —
# 61 apostrophe hits in a proposal whose page had already been keyed, reviewed,
# and committed). Keeping proposal.json checkable by explicit `--path` keeps the
# `1-151` protection for the one place it matters — mid-pass, before `--convert`
# is run on the file currently being authored.
PATH_ONLY_GLOBS = ("review/*/proposal.json",)


def _is_entity(p: Path) -> bool:
    """An `entities/<class>/<slug>.md` record.

    By position rather than by suffix: `.md` alone would also catch every
    document in the repo if one were ever added to a glob, and the two prose
    arms below scope themselves on this answer.
    """
    return p.suffix == ".md" and p.parent.parent.name == "entities"

# Codepoints with no legitimate use in English prose *or* in the transcription system,
# so their presence is a defect regardless of which one a given span is. The curly
# quotes are deliberately absent: the book prints them and English prose reproduces
# them. Keep the messages in `validate.LOOKALIKE_GREPS`'s idiom — "X traps Y" reads as
# "X is what gets typed when Y was meant".
LOOKALIKE_CHARS = {
    "´": "U+00B4 traps U+02CA",
    "ʼ": "U+02BC traps U+02CA",
    "ʻ": "U+02BB traps U+02CA",
    "·": "U+00B7 traps U+02D9",
    "ˢ": "U+02E2 traps U+1D4B/U+1D49",
    "ₑ": "U+2091 traps U+1D49",
    "ө": "U+04E9 traps U+0275",
    "‐": "U+2010 traps U+002D",
    # §2.11 is categorical — "the book sets one dash, U+2014, no en dash" — and the
    # store agrees: 1041 U+2014 against 0 U+2013 over 476 keyed pages. It traps the
    # HYPHEN rather than the em dash, because what actually gets typed as U+2013 is a
    # numeric range (`1820–24`), and a range is a compound joiner, not one of §2.11's
    # three dash settings. `3-188` keyed one and was first "corrected" to em, which
    # was the same error one sort over; the corpus sets ranges 38 hyphen to 0 dash.
    "–": "U+2013 traps U+002D",
    # Not in keying_spec.md §2.3 at all — the only licensed dotless small-cap
    # sort is ɪ (U+026A). Plain Turkish dotless-ı is the ASCII-keyboard-adjacent
    # slip for it: `1-100`'s proposal keyed it ~20 times this way, of which
    # `proposal-check --fix` only caught the ones that happened to be a clean
    # 1-for-1 swap against `resolved` — the rest needed a hand-rolled script.
    "ı": "U+0131 traps U+026A",
    " ": "U+00A0 traps U+0020 (breaks word tokenization)",
}
# Traps that are a sequence, not a codepoint. U+0121 decomposes to exactly this pair,
# so post-NFD there is nothing else to look for; the canonical glyph is g+U+0323.
LOOKALIKE_SEQS = {"ġ": "g+U+0307 (or U+0121) traps g+U+0323"}


# The two tables flattened once, in the order `_lookalikes` reports them — chars then
# sequences — because that order is the report's row order, and a worklist that
# reshuffled itself would show as churn in every diff. Built here rather than inside
# the line loop, which was rebuilding it 67k times over a corpus run.
_LOOKALIKE_PROBES = list(LOOKALIKE_CHARS.items()) + list(LOOKALIKE_SEQS.items())
_LOOKALIKE_PROBES_FLAT = tuple(p for p, _ in _LOOKALIKE_PROBES)


def scoped_files(root: Path = Path("."), include_path_only: bool = False) -> list[Path]:
    """Distinct corpus files, one entry per inode.

    Deduplicating by real path is load-bearing rather than tidy wherever two globs
    can reach one inode: without it `scan` reports the same file twice under both
    names (inflating the offender count by the size of the overlap), and `convert`
    writes it via the first name, then reaches the second, finds it already
    conformant and silently skips — so the report undercounts exactly the files that
    were touched twice. Both failures are quiet, and the second is the sort that
    reads as "nothing to do".

    The overlap this was written for was `ocr/*.xml` against `gt/ocr/*.xml`, and
    **that glob is gone** — see SCOPE_GLOBS on why a view with two real stores under
    it cannot gate the corpus. The dedupe stays: it is unconditional in the README's
    rule, the failure it prevents is a silent undercount, and the next store added
    here will not announce that it aliases another.

    The first name encountered wins; glob order follows SCOPE_GLOBS.

    `include_path_only` adds `PATH_ONLY_GLOBS` (currently just `proposal.json`) to
    the walk — set only when the caller was given an explicit `--path`, so a bare
    corpus-wide sweep never picks these up but `--path review/PP-NNN/proposal.json`
    (or a directory containing one) still finds it.
    """
    out: list[Path] = []
    seen: set = set()
    globs = SCOPE_GLOBS + PATH_ONLY_GLOBS if include_path_only else SCOPE_GLOBS
    for pat in globs:
        for p in sorted(root.glob(pat)):
            # A directory can hold both `mets.xml` and `METS.xml`; neither is corpus,
            # and a manifest has no text to normalize.
            if not p.is_file() or p.name.lower() == "mets.xml":
                continue
            try:
                key = p.resolve()
            except OSError:  # broken symlink
                continue
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out


def _lookalikes(text: str) -> list[dict]:
    """Every lookalike occurrence, located. Assumes NFD input.

    One record per occurrence with the line and the containing token, not a per-file
    tally. A count tells a reader that something is wrong somewhere in a 54 KB file,
    which is not a finding they can act on — and every one of these needs a human
    ruling on what the page actually prints, so the report has to name the word. Same
    idiom as `validate.LOOKALIKE_GREPS`'s worklist, which quotes its context.
    """
    # The probe table was being rebuilt — two dicts, `.items()`, concatenated — once
    # per *line*, i.e. 67k times over the corpus, and then searched with one
    # `str.find` loop per probe. Same answer for one whole-text search and, on a hit,
    # a per-line pass. Ordering is preserved deliberately: hits come out grouped by
    # probe within a line, as they did, because the report is a worklist a human
    # reads down and reshuffling it would show as churn in every diff.
    if not any(probe in text for probe in _LOOKALIKE_PROBES_FLAT):
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for probe, msg in _LOOKALIKE_PROBES:
            start = 0
            while (pos := line.find(probe, start)) != -1:
                hits.append({"trap": msg, "line": lineno,
                             "token": _token_at(line, pos)})
                start = pos + len(probe)
    return hits


STRAIGHT_QUOTE_TRAP = "U+0022 traps curly “ ” — the book sets curly quotes throughout"


def _quote_hits(p: Path, root: Path) -> list[dict]:
    """Straight U+0022 inside *authored English content* — content-scoped, unlike
    `_lookalikes`'s raw-file-text scan. XML attribute/tag syntax and JSON's own
    string delimiters are built from U+0022, so a blind file-wide grep would flag
    the file's own syntax on every line; this parses each file and only looks at
    the text a human or model actually wrote. `1-100`'s proposal keyed 16 glosses
    with `\"…\"` where every other page in the corpus already used the curly
    quotes the book prints — a keying-convention slip, not a JSON escaping
    problem, and the reason this check exists rather than a whole-format change.

    A hit does not imply the quotes were on one line: a printed gloss can wrap
    across ALTO lines, so a curly pair's open and close may sit in different
    `text` fields entirely. This only flags the straight-quote occurrence; it
    does not attempt to pair or fix one, since guessing which close belongs to
    which open across lines is exactly the kind of guess this module elsewhere
    refuses to make.

    Every occurrence is its own record, not one per line/field — a line with
    two straight quotes (a whole gloss) previously reported as a single hit,
    which undercounts exactly the thing a reader needs to go fix each of. XML
    hits are keyed by **ALTO order index**, the same index `harness ocr lines`
    and `harness ocr zoom --only` use — not the opaque `TextLine/@ID` — so a hit
    is directly actionable (`harness ocr zoom PP-NNN --only <index>`) rather than
    requiring a second lookup to translate the id into something zoomable.

    `note`/`resolved` fields and `@note:`-prefixed `readings.md` lines are
    **not scanned at all**, not just excused on a miss: those are editorial
    commentary *about* the corpus, not print-reproduction content, and can
    legitimately quote something verbatim that a curly conversion would
    misrepresent — `1-151`'s note cites literal XML (`<pb n="115"/>`), where
    "fixing" the attribute quotes to curly would turn a syntax citation into
    nonsense. Only `text` (the keyed content) and non-`@note` prose are
    checked, where the "book sets curly quotes" premise actually holds.
    """
    rel = str(p.relative_to(root))
    hits = []
    if p.suffix == ".json" and p.name in ("proposal.json", "decision.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return hits
        for idx, rec in sorted(data.get("lines", {}).items(), key=key_order):
            val = rec.get("text", "")
            start = 0
            while (pos := val.find('"', start)) != -1:
                hits.append({"path": rel, "trap": STRAIGHT_QUOTE_TRAP,
                            "line": idx, "token": f"text: {_token_at(val, pos)}"})
                start = pos + 1
    elif p.suffix == ".xml" and p.parent.name == "ocr":
        from lxml import etree
        try:
            root_el = etree.parse(str(p)).getroot()
        except (etree.XMLSyntaxError, OSError):
            return hits
        for i, tl in enumerate(root_el.iter("{*}TextLine")):
            for s in tl.findall("{*}String"):
                content = s.get("CONTENT") or ""
                start = 0
                while (pos := content.find('"', start)) != -1:
                    hits.append({"path": rel, "trap": STRAIGHT_QUOTE_TRAP,
                                "line": i, "token": _token_at(content, pos)})
                    start = pos + 1
    elif p.name == "readings.md" or _is_entity(p):
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("@note") or line.startswith("|"):
                continue
            start = 0
            while (pos := line.find('"', start)) != -1:
                hits.append({"path": rel, "trap": STRAIGHT_QUOTE_TRAP,
                            "line": lineno, "token": _token_at(line, pos)})
                start = pos + 1
    return hits


_APOSTROPHE_TRAPS = {
    "english": "U+0027 traps curly ’ — English prose sets curly apostrophes "
              "too (§1), same rule as the quote pair",
    "unlicensed": "U+0027 inside a Tier-1 form (§2.1: no licensed position) "
                 "— a mistyped stress mark U+02CA",
}


def _apostrophe_hits(p: Path, root: Path) -> list[dict]:
    """Every straight U+0027 in *authored content*, same content-scoping as
    `_quote_hits` (JSON `text` fields, `ocr`/`gt/ocr` `CONTENT` attributes,
    non-`@note` `readings.md` lines) but the per-occurrence judgement is
    `detectors.apostrophe_flags`, which names the kind: an English token
    wants the curly ’ the book sets, a Tier-1 token has no licensed position
    for the codepoint at all (§2.1), so both are defects. A corpus-wide check
    found zero legitimate straight apostrophes anywhere in restored ground
    truth.
    """
    rel = str(p.relative_to(root))
    hits = []
    if p.suffix == ".json" and p.name in ("proposal.json", "decision.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return hits
        for idx, rec in sorted(data.get("lines", {}).items(), key=key_order):
            val = rec.get("text", "")
            for h in apostrophe_flags(val):
                hits.append({"path": rel, "trap": _APOSTROPHE_TRAPS[h["kind"]],
                            "line": idx, "token": f"text: {h['token']}"})
    elif p.suffix == ".xml" and p.parent.name == "ocr":
        from lxml import etree
        try:
            root_el = etree.parse(str(p)).getroot()
        except (etree.XMLSyntaxError, OSError):
            return hits
        for i, tl in enumerate(root_el.iter("{*}TextLine")):
            for s in tl.findall("{*}String"):
                content = s.get("CONTENT") or ""
                for h in apostrophe_flags(content):
                    hits.append({"path": rel, "trap": _APOSTROPHE_TRAPS[h["kind"]],
                                "line": i, "token": h["token"]})
    elif p.name == "readings.md" or _is_entity(p):
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("@note") or line.startswith("|"):
                continue
            for h in apostrophe_flags(line):
                hits.append({"path": rel, "trap": _APOSTROPHE_TRAPS[h["kind"]],
                            "line": lineno, "token": h["token"]})
    return hits


def _footnote_hits(p: Path, root: Path) -> list[dict]:
    """Page-level footnote-marker consistency, per file. Report-only.

    Scoped to OCR ALTO and adjudicated proposals — the stores that hold a
    page's running text in line order. `gt/fig/` is excluded because it carries
    no `TextLine` at all (harness/README.md), and the `data/` apparatus because a
    marker there is a citation, not a note anchor.

    Rides on `normalize` rather than a verb of its own because everything this
    needs is already here — the corpus walk, the dedupe by real path, the
    report-only tier, and an ALTO parse in document order — and because the
    skill already mandates `normalize --check` before a commit, so a check
    living here is one nobody has to remember to run separately.

    Blocking tier: **none**. This sits with `lookalikes`, not with `nfd`/
    `spacing`/`marks`. Both invariants have a legitimate exception at a page
    seam, where a note's reference and its text fall on different pages and the
    pairing breaks with nothing miskeyed — so a hit is a page to look at, not a
    proven defect. See `detectors.footnote_report` for the rule itself.
    """
    rel = str(p.relative_to(root))
    texts: list[str] = []
    if p.suffix == ".json" and p.name in ("proposal.json", "decision.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        texts = [rec.get("text", "") for _, rec in
                 sorted(data.get("lines", {}).items(), key=key_order)]
    elif p.suffix == ".xml" and p.parent.name == "ocr":
        from lxml import etree
        try:
            root_el = etree.parse(str(p)).getroot()
        except (etree.XMLSyntaxError, OSError):
            return []
        texts = [" ".join(s.get("CONTENT") or "" for s in tl.findall("{*}String"))
                 for tl in root_el.iter("{*}TextLine")]
    else:
        return []

    rep = footnote_report(texts)
    hits = []
    if rep["gaps"]:
        hits.append({"path": rel, "trap": "marker run has gaps",
                     "line": "-", "token": f"missing {rep['gaps']} from 1..{max(rep['counts'])}"})
    if rep["singletons"]:
        hits.append({"path": rel, "trap": "marker printed twice, keyed once",
                     "line": "-", "token": f"{rep['singletons']} occurs once "
                                           "(body reference + note opener expected)"})
    for op in rep["ascii_openers"]:
        hits.append({"path": rel, "trap": "bare ASCII digit where a superscript was meant",
                     "line": op["line"], "token": op["text"]})
    return hits


def _token_at(line: str, pos: int) -> str:
    """The whitespace-delimited token containing `pos`, capped for display."""
    left = line.rfind(" ", 0, pos) + 1
    right = line.find(" ", pos)
    tok = line[left:right if right != -1 else len(line)]
    return tok[:48] if tok.strip() else repr(line[max(0, pos - 20):pos + 20])


def _precomposed(text: str) -> str:
    """Which characters NFD would decompose, and how many of each.

    `delta: 3` says how big the change is but not what it touches, and a reviewer
    deciding whether to accept a rewrite of hand-keyed ground truth needs the latter.
    """
    counts: dict[str, int] = {}
    for ch in text:
        if ord(ch) > 127 and unicodedata.decomposition(ch) \
                and not unicodedata.decomposition(ch).startswith("<"):
            counts[ch] = counts.get(ch, 0) + 1
    return " ".join(f"{c}(U+{ord(c):04X})×{n}"
                    for c, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def _filter_scoped(universe: list[Path], paths: list[Path]) -> list[Path]:
    """Narrow `universe` to files matching `paths` — each entry either a file
    (exact match) or a directory (every scoped file resolving underneath it).

    Mixed lists work: `--path review/1-052 --path data/readings.md` scopes to
    both a whole page directory and one unrelated file. Either way this only
    narrows the corpus glob, never widens it — a directory outside `SCOPE_GLOBS`
    (or with nothing scoped inside it) simply contributes no files.
    """
    files = {p for p in paths if p.is_file()}
    dirs = [p.resolve() for p in paths if p.is_dir()]
    wanted_files = {p.resolve() for p in files}
    out = []
    for p in universe:
        rp = p.resolve()
        if rp in wanted_files or any(rp.is_relative_to(d) for d in dirs):
            out.append(p)
    return out


def scan(root: Path = Path("."), paths: list[Path] | None = None,
         tick=None) -> dict:
    """Per-file conformance, without writing anything.

    `delta` is the codepoint count NFD would add, which is the honest size of the
    change: it is never a character *identity* change, only a representation one.

    `paths`, when given, scopes the walk to those files (or directories — every
    scoped file underneath, e.g. one page's `review/PP-NNN/`) instead of the
    whole corpus glob — a per-page loop step (a proposal just authored) has no
    business rewriting 283 files to check or convert one of them, even though
    `scoped_files` would find it eventually. The files still have to already be
    in scope (an arbitrary path is not silently accepted), so this narrows, it
    does not widen.
    """
    files, offenders, worklist, unlicensed, spacing, footnotes = 0, [], [], [], [], []
    universe = scoped_files(root, include_path_only=paths is not None)
    if paths is not None:
        universe = _filter_scoped(universe, paths)
    for p in ptrack(universe, tick):
        rel = str(p.relative_to(root))
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            offenders.append({"path": rel, "delta": 0, "chars": f"unreadable: {e}"})
            continue
        files += 1
        nfd = unicodedata.normalize("NFD", text)
        if nfd != text:
            offenders.append({"path": rel, "delta": len(nfd) - len(text),
                              "chars": _precomposed(text)})
        # Checked against the NFD form so a precomposed lookalike and its decomposed
        # twin report identically — otherwise the answer would depend on the very
        # drift this verb exists to remove.
        for h in _lookalikes(nfd):
            worklist.append({"path": rel, **h})
        worklist += _quote_hits(p, root)
        worklist += _apostrophe_hits(p, root)
        # Reported per line, since a path plus a context string is not enough to find
        # one occurrence in a 54 KB store.
        for lineno, line in enumerate(nfd.splitlines(), start=1):
            for h in unlicensed_marks(line):
                unlicensed.append({"path": rel, "line": lineno, **h})
        for h in _spacing_hits(text, commentary=p.suffix == ".json"):
            spacing.append({"path": rel, **h})
        footnotes += _footnote_hits(p, root)
    return {"files": files, "nfd_offenders": offenders,
            "unlicensed_marks": unlicensed, "lookalikes": worklist,
            "spacing_offenders": spacing, "footnote_markers": footnotes}


def convert(root: Path = Path("."), dry_run: bool = False,
            paths: list[Path] | None = None, tick=None) -> dict:
    """Rewrite non-conformant files to NFD.

    `paths` scopes to specific files or directories, same contract as `scan`'s —
    see there for why a per-page step should not default to walking the whole
    corpus.

    Operates on **raw file source, never a parsed tree**. Every XML syntax character
    is ASCII and therefore NFD-invariant, so this cannot perturb element order,
    attribute order, quoting or the declaration — which a parse-and-serialize round
    trip absolutely would, burying 100 real codepoint changes in thousands of
    cosmetic ones.

    Two checks, both able to fail. Note which one is *not* here: comparing
    `NFD(before)` against `NFD(after)` proves nothing, because `after` is `NFD(before)`
    and NFD is idempotent, so that assertion passes unconditionally. Canonical
    equivalence is guaranteed by Unicode, not by us; what is worth verifying is
    everything downstream of that guarantee.

      read-back   re-read the file and require it to equal what we meant to write,
                  which catches an encoder or filesystem failure rather than a
                  reasoning failure.
      structure   for XML, parse before and after and require the element count and
                  the `String/@CONTENT` count to match; for JSON, require it to still
                  parse and the `lines` key set to be unchanged. Independent witnesses
                  in both cases: neither knows anything about normal forms or spacing,
                  so neither can agree with the normalizer by construction the way a
                  re-derived digest would.

    A file whose suffix carries a structure check and which **does not parse to
    begin with** is refused, not written: the check is what separates a rewrite
    from a corruption, and there is no way to run it on a file that never
    parsed. The refusal is reported, so an unparseable store file surfaces here
    rather than being quietly rewritten with nothing watching.

    Also collapses §2.9 spacing drift (`_fix_spacing`) in the same pass — mechanical
    and print-invariant same as NFD, so it shares NFD's safety checks rather than
    getting a separate command.

    `tools/migrate_coords.py`'s byte-exact `content_digest` deliberately is not reused
    — it cannot tell "corrupted" from "normalized", which is also why a normalization
    pass must never share a run with a coordinate migration.
    """
    changed, failed = [], []
    universe = scoped_files(root, include_path_only=paths is not None)
    if paths is not None:
        universe = _filter_scoped(universe, paths)
    for p in ptrack(universe, tick):
        try:
            before = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after = _fix_spacing(unicodedata.normalize("NFD", before),
                             commentary=p.suffix == ".json")
        if after == before:
            continue

        if p.suffix == ".xml":
            shape_before, shape_kind = _xml_shape(p), "XML"
        elif p.suffix == ".json":
            shape_before, shape_kind = _json_shape(p), "JSON"
        else:
            shape_before, shape_kind = None, None
        # **A file that does not parse is refused, not written.** The structure
        # check below is the only witness that a rewrite was a rewrite and not a
        # corruption — the read-back proves the bytes landed, never that they
        # still mean what they meant — and a file that never parsed cannot
        # supply one. It used to be written anyway, with the gate skipped,
        # because the gate was guarded on `shape_before is None`, which is also
        # what an ordinary `data/*.json` answers. `_parses` is the narrow
        # question; see there.
        if shape_kind is not None and not _parses(p, shape_kind):
            failed.append({"path": str(p.relative_to(root)),
                           "note": f"REFUSED: {shape_kind} does not parse, so no "
                                   "shape check can witness the rewrite"})
            continue
        if dry_run:
            changed.append({"path": str(p.relative_to(root)),
                            "delta": len(after) - len(before)})
            continue

        p.write_text(after, encoding="utf-8")

        if p.read_text(encoding="utf-8") != after:
            failed.append({"path": str(p.relative_to(root)),
                           "note": "ABORTED: read-back does not match what was written"})
            continue
        if shape_before is not None:
            shape_after = _xml_shape(p) if shape_kind == "XML" else _json_shape(p)
            if shape_after != shape_before:
                failed.append({"path": str(p.relative_to(root)),
                               "note": f"ABORTED: {shape_kind} shape moved "
                                       f"{shape_before} -> {shape_after}"})
                continue
        changed.append({"path": str(p.relative_to(root)),
                        "delta": len(after) - len(before)})
    return {"changed": changed, "failed": failed, "dry_run": dry_run}


def _parses(p: Path, kind: str) -> bool:
    """Does this file parse at all — deliberately narrower than `_*_shape`.

    **The two questions are not the same, and reading one for the other is what
    put a hole in the structure gate.** `_xml_shape` answers `None` only for an
    unparseable file, so there the two coincide; `_json_shape` also answers
    `None` for a file that parses perfectly and simply holds no `lines` key,
    which is every `data/*.json` but a decision. Gating a refusal on `None`
    therefore refused most of `data/` on an XML-shaped intuition.

    So the refusal asks this instead. It is one extra parse, on the files being
    converted only, which already parse twice.
    """
    from lxml import etree
    try:
        if kind == "XML":
            etree.parse(str(p))
        else:
            json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, etree.XMLSyntaxError,
            json.JSONDecodeError):
        return False
    return True


def _json_shape(p: Path) -> tuple | None:
    """(line-index set, per-line text lengths after whitespace-fold). None if it
    will not parse.

    Not a digest of the raw text — the whole point of this rewrite is to change
    whitespace *and* normal form, so a byte-exact check would fail on every
    legitimate conversion. Folding runs of whitespace to a single space, and
    NFD-normalizing, before comparing catches an actual content change (a
    character other than a collapsed space added or removed, or a codepoint
    substituted for a different one) while staying blind to both kinds of drift
    this same pass is licensed to make. Skipping the NFD fold here was a real
    bug, not a hypothetical: a precomposed accented character (one codepoint)
    legitimately becomes multiple codepoints under NFD, which a literal-string
    fold reports as "shape moved" even though nothing but normal form changed —
    the write had already succeeded by the time this ran, so the false abort
    only misreported success as failure, but on a mechanical gate a status that
    can be wrong at all defeats the point of having it.

    **§2.9 spacing is the second kind and was the same bug twice.** Folding runs
    of whitespace is blind to a run becoming shorter, not to a space being
    *removed* — and removing one before `;:,!?`, or restoring one after a
    footnote opener, is exactly what `_fix_spacing` is licensed to do in this
    pass. `purpose ; but` -> `purpose; but` moved the shape and aborted a write
    that had succeeded. So the fold now applies `_fix_spacing` too: the check
    asks whether anything happened *other than* what this pass may do, which is
    the only question it was ever meant to answer. Reported by two readers on
    two chapters (`3-097`, `3-133`), both of whom went and confirmed the file
    was written — the cost of a gate that cries wolf is paid in their turns.
    """
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, dict):
        return None
    folded = {k: _fix_spacing(
                  unicodedata.normalize("NFD", re.sub(r"\s+", " ", v.get("text", ""))),
                  commentary=True).strip()
              for k, v in lines.items()}
    return (frozenset(lines.keys()), folded)


def _xml_shape(p: Path) -> tuple[int, int] | None:
    """(element count, String/@CONTENT count). None if it will not parse.

    Deliberately not a hash of the text: a digest recomputed from the same string the
    normalizer produced would agree with it no matter what, whereas an independent
    parse can disagree.
    """
    from lxml import etree
    try:
        root_el = etree.parse(str(p)).getroot()
    except (etree.XMLSyntaxError, OSError):
        return None
    return (sum(1 for _ in root_el.iter()),
            sum(1 for s in root_el.iter("{*}String") if s.get("CONTENT") is not None))
