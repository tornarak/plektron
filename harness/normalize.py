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

Four rules, all mechanical:

  nfd          every scoped file is NFD-conformant.
  marks        every combining mark sits on a base its licence covers (§2.6).
  lookalikes   no scoped file carries a lookalike with no legitimate English use.
  spacing      no run of 2+ spaces survives between non-space characters, and no
               space sits immediately before `;`, `:`, or `,` (§2.9).

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

from .detectors import apostrophe_flags, unlicensed_marks

# §2.9: sentence-ending double space and thin space before ;/:/, are typesetting
# artifacts with no lexical content — mechanical, print-invariant, corpus-wide.
# The lookbehind/lookahead require a non-space neighbor on each side, so a line's
# leading indentation (preceded by a newline) never matches.
_MULTI_SPACE = re.compile(r"(?<=\S) {2,}(?=\S)")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([;:,])")


def _fix_spacing(text: str) -> str:
    """Collapse §2.9 spacing drift, line by line, skipping `#`-comment lines.

    Line-by-line (not a whole-text regex) so a `#`-prefixed line — `lexicon_extra.txt`'s
    own documented comment convention — can be left untouched: its comments include a
    multi-space-indented usage example, which is code formatting, not sentence spacing,
    and the blanket regex does not know the difference.
    """
    out = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            out.append(line)
            continue
        line = _MULTI_SPACE.sub(" ", line)
        line = _SPACE_BEFORE_PUNCT.sub(r"\1", line)
        out.append(line)
    return "\n".join(out)


def _spacing_hits(text: str) -> list[dict]:
    """Every spacing-drift occurrence, located. One record per match, not a tally —
    same reasoning as `_lookalikes`: a count is not something a reader can act on."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        for pat, label in ((_MULTI_SPACE, "2+ spaces (§2.9 sentence spacing)"),
                           (_SPACE_BEFORE_PUNCT, "space before ;/:/, (§2.9)")):
            for m in pat.finditer(line):
                hits.append({"issue": label, "line": lineno,
                            "token": _token_at(line, m.start())})
    return hits

# Directories whose XML is corpus, and the individual data files. Root-level *.md are
# excluded deliberately: CLAUDE.md and transcriber_harness.md quote glyph examples in
# prose and would fail a gate meant for the text itself.
SCOPE_GLOBS = ("ocr/*.xml", "gt/ocr/*.xml", "gt/seg/*.xml", "fig/*.xml", "tei/*.xml",
               "data/readings.md", "data/*.json", "data/lexicon_extra.txt",
               # decision.json is an editorial act — the adjudicated record that
               # `restore` actually writes to gt/ocr/ — so it stays in the default
               # sweep alongside the rest of the corpus. `save_decisions` normalizes
               # on write, so this is a regression check, not a live worklist.
               "review/*/decision.json")

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

# Codepoints with no legitimate use in English prose *or* in the transcription system,
# so their presence is a defect regardless of which one a given span is. The curly
# quotes are deliberately absent: the book prints them and English prose reproduces
# them. Keep the messages in `validate.LOOKALIKE_GREPS`'s idiom — "X traps Y" reads as
# "X is what gets typed when Y was meant".
LOOKALIKE_CHARS = {
    "´": "U+00B4 traps U+02CA",
    "ʼ": "U+02BC traps U+0027",
    "ʻ": "U+02BB traps U+0027",
    "·": "U+00B7 traps U+02D9",
    "ˢ": "U+02E2 traps U+1D4B/U+1D49",
    "ₑ": "U+2091 traps U+1D49",
    "ө": "U+04E9 traps U+0275",
    "‐": "U+2010 traps U+002D",
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


def scoped_files(root: Path = Path("."), include_path_only: bool = False) -> list[Path]:
    """Distinct corpus files, one entry per inode.

    **`ocr/*.xml` are symlinks into `gt/ocr/`** — one store under two names, not two
    copies. Deduplicating by real path is therefore load-bearing rather than tidy:
    without it `scan` reports the same file twice under both names (inflating the
    offender count by the size of the overlap), and `convert` writes it via the first
    name, then reaches the second, finds it already conformant and silently skips —
    so the report undercounts exactly the files that were touched twice. Both
    failures are quiet, and the second is the sort that reads as "nothing to do".

    The first name encountered wins, so `ocr/…` is what gets reported: glob order
    follows SCOPE_GLOBS.

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
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for probe, msg in list(LOOKALIKE_CHARS.items()) + list(LOOKALIKE_SEQS.items()):
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
    hits are keyed by **ALTO order index**, the same index `harness lines`
    and `harness zoom --only` use — not the opaque `TextLine/@ID` — so a hit
    is directly actionable (`harness zoom PP-NNN --only <index>`) rather than
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
        for idx, rec in sorted(data.get("lines", {}).items(), key=lambda kv: int(kv[0])):
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
    elif p.name == "readings.md":
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("@note"):
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
    "unlicensed": "U+0027 unlicensed here (§2.1: not post-b/p/d/t/g/k, not "
                 "V_V) — almost certainly a mistyped stress mark U+02CA",
    "ambiguous": "U+0027 in V_V position (§4: shape alone decides stress vs. "
                "pause) — a human call on the raster, not a defect by itself",
}


def _apostrophe_hits(p: Path, root: Path) -> list[dict]:
    """Every straight U+0027 in *authored content*, same content-scoping as
    `_quote_hits` (JSON `text` fields, `ocr`/`gt/ocr` `CONTENT` attributes,
    non-`@note` `readings.md` lines) but the per-occurrence judgement is
    `detectors.apostrophe_flags` rather than a blind substring match, since
    unlike U+0022 this codepoint has one real, licensed reading (spirant/
    pause, §2.1) and a blind flag-everything rule would report correct
    Tier-1 text as broken. What survives that exemption is still everything
    that has actually turned out wrong so far — a corpus-wide check found
    zero legitimate apostrophes of either kind (Tier-1 or English) anywhere
    in restored ground truth; see `detectors.apostrophe_flags`.
    """
    rel = str(p.relative_to(root))
    hits = []
    if p.suffix == ".json" and p.name in ("proposal.json", "decision.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return hits
        for idx, rec in sorted(data.get("lines", {}).items(), key=lambda kv: int(kv[0])):
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
    elif p.name == "readings.md":
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("@note"):
                continue
            for h in apostrophe_flags(line):
                hits.append({"path": rel, "trap": _APOSTROPHE_TRAPS[h["kind"]],
                            "line": lineno, "token": h["token"]})
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


def scan(root: Path = Path("."), paths: list[Path] | None = None) -> dict:
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
    files, offenders, worklist, unlicensed, spacing = 0, [], [], [], []
    universe = scoped_files(root, include_path_only=paths is not None)
    if paths is not None:
        universe = _filter_scoped(universe, paths)
    for p in universe:
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
        for h in _spacing_hits(text):
            spacing.append({"path": rel, **h})
    return {"files": files, "nfd_offenders": offenders,
            "unlicensed_marks": unlicensed, "lookalikes": worklist,
            "spacing_offenders": spacing}


def convert(root: Path = Path("."), dry_run: bool = False,
            paths: list[Path] | None = None) -> dict:
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
    for p in universe:
        try:
            before = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after = _fix_spacing(unicodedata.normalize("NFD", before))
        if after == before:
            continue

        if p.suffix == ".xml":
            shape_before, shape_kind = _xml_shape(p), "XML"
        elif p.suffix == ".json":
            shape_before, shape_kind = _json_shape(p), "JSON"
        else:
            shape_before, shape_kind = None, None
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
    """
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, dict):
        return None
    folded = {k: unicodedata.normalize("NFD", re.sub(r"\s+", " ", v.get("text", ""))).strip()
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
