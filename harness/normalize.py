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

Three rules, all mechanical:

  nfd          every scoped file is NFD-conformant.
  marks        every combining mark sits on a base its licence covers (§2.6).
  lookalikes   no scoped file carries a lookalike with no legitimate English use.

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
import unicodedata
from pathlib import Path

from .detectors import unlicensed_marks

# Directories whose XML is corpus, and the individual data files. Root-level *.md are
# excluded deliberately: CLAUDE.md and transcriber_harness.md quote glyph examples in
# prose and would fail a gate meant for the text itself.
SCOPE_GLOBS = ("ocr/*.xml", "gt/ocr/*.xml", "gt/seg/*.xml", "fig/*.xml", "tei/*.xml",
               "data/readings.md", "data/*.json", "data/lexicon_extra.txt",
               # The review stores. Both are authored text — a proposal is somebody's
               # reading and a decision is an editorial act — so both can carry an
               # inventory glyph and both must be NFD. They were outside the scope
               # until a proposal for `1-151` keyed ê precomposed twice, inside a
               # Tier-1 form, with the same file's own note correctly describing it as
               # e+U+0302. `save_decisions` normalizes on write, so `decisions/` was
               # safe by accident; nothing normalized a hand-authored proposal.
               "review/proposals/*.json", "review/decisions/*.json")

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
    " ": "U+00A0 traps U+0020 (breaks word tokenization)",
}
# Traps that are a sequence, not a codepoint. U+0121 decomposes to exactly this pair,
# so post-NFD there is nothing else to look for; the canonical glyph is g+U+0323.
LOOKALIKE_SEQS = {"ġ": "g+U+0307 (or U+0121) traps g+U+0323"}


def scoped_files(root: Path = Path(".")) -> list[Path]:
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
    """
    out: list[Path] = []
    seen: set = set()
    for pat in SCOPE_GLOBS:
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


def scan(root: Path = Path(".")) -> dict:
    """Per-file conformance, without writing anything.

    `delta` is the codepoint count NFD would add, which is the honest size of the
    change: it is never a character *identity* change, only a representation one.
    """
    files, offenders, worklist, unlicensed = 0, [], [], []
    for p in scoped_files(root):
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
        # Reported per line, since a path plus a context string is not enough to find
        # one occurrence in a 54 KB store.
        for lineno, line in enumerate(nfd.splitlines(), start=1):
            for h in unlicensed_marks(line):
                unlicensed.append({"path": rel, "line": lineno, **h})
    return {"files": files, "nfd_offenders": offenders,
            "unlicensed_marks": unlicensed, "lookalikes": worklist}


def convert(root: Path = Path("."), dry_run: bool = False) -> dict:
    """Rewrite non-conformant files to NFD.

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
                  the `String/@CONTENT` count to match. An independent witness: it
                  knows nothing about normal forms, so it cannot agree with the
                  normalizer by construction the way a re-derived digest would.

    `tools/migrate_coords.py`'s byte-exact `content_digest` deliberately is not reused
    — it cannot tell "corrupted" from "normalized", which is also why a normalization
    pass must never share a run with a coordinate migration.
    """
    changed, failed = [], []
    for p in scoped_files(root):
        try:
            before = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after = unicodedata.normalize("NFD", before)
        if after == before:
            continue

        counts_before = _xml_shape(p) if p.suffix == ".xml" else None
        if dry_run:
            changed.append({"path": str(p.relative_to(root)),
                            "delta": len(after) - len(before)})
            continue

        p.write_text(after, encoding="utf-8")

        if p.read_text(encoding="utf-8") != after:
            failed.append({"path": str(p.relative_to(root)),
                           "note": "ABORTED: read-back does not match what was written"})
            continue
        if counts_before is not None:
            counts_after = _xml_shape(p)
            if counts_after != counts_before:
                failed.append({"path": str(p.relative_to(root)),
                               "note": f"ABORTED: XML shape moved "
                                       f"{counts_before} -> {counts_after}"})
                continue
        changed.append({"path": str(p.relative_to(root)),
                        "delta": len(after) - len(before)})
    return {"changed": changed, "failed": failed, "dry_run": dry_run}


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
