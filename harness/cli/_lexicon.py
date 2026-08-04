"""`harness lexicon` — frequency reports over the corpus, and the gloss dictionary.

Seven actions where there were six mutually-exclusive-in-fact flags on one verb,
declared independent and resolved by if-chain precedence, so `--marks --native`
silently ran `--marks`.

Six read restored ground truth in `gt/ocr/`; `glosses` reads committed TEI
instead, which is why it is worth naming its source in the help rather than
letting the group heading imply one store. All are report-only and exit 0.

`conflicts` is the seventh and the only one that consults a *ruling* —
`data/marks_exempt.json`. It is here rather than beside `proposal marks` because
the exemptible question is about the corpus, not about a reader: see
`marks.gt_conflicts`.
"""
from __future__ import annotations

from ..detectors import (
    digraph_frequency,
    mark_base_frequency,
    suffix_frequency,
    suggest_lexicon,
    suggest_native_forms,
)
from ..ids import glossary
from ..marks import gt_conflicts
from ._common import action, group, out


def register(cli):
    g = group(cli, "lexicon", "frequency reports over the native corpus "
              "— misses to whitelist, forms to compare against, marks, "
              "affixes and n-grams — plus the term<->gloss dictionary "
              "from committed TEI",
              section="Apparatus and reports")
    add = lambda name, fn, **kw: action(g, name, lambda a: _emit(a, fn), **kw)

    add("misses", suggest_lexicon, help="frequency-ranked lexicon_miss tokens across every "
            "OCR'd page, for bulk approval into data/lexicon_extra.txt. That "
            "file suppresses lexicon_miss and nothing else — a Tier-1 form "
            "listed there is inert by construction, since the detector only "
            "ever tests ASCII components")

    add("native", suggest_native_forms,
        help="invert: the most frequent native (Tier-1) word forms "
            "in restored gt/ocr/, for spotting a likely misspelling by "
            "comparison rather than by dictionary")

    add("marks", mark_base_frequency,
        help="bare-vs-marked frequency per base letter across the "
            "native corpus — e.g. is a bare g or a dotted g̣ the more likely "
            "reading, prior to opening the raster")

    add("suffixes", suffix_frequency,
        help="weighted suffix frequency (length 2-8) over the "
            "native corpus, diacritics and stress marks stripped before counting")

    add("digraphs", digraph_frequency,
        help="weighted digraph/trigraph frequency over the native "
            "corpus, with marks and the corpus's own top suffixes stripped first "
            "so stems aren't drowned by the suffix family repeating itself")

    add("conflicts", gt_conflicts,
        help="one word spelled two ways in gt/ocr/ — the ground-truth arm "
            "of `proposal marks`' conflict check, corpus-wide. Rows are one per "
            "(fold, form, page) and carry the line numbers, so a fold is a "
            "worklist rather than a notification. Where the book itself sets a "
            "word two ways, a ruling goes in data/marks_exempt.json scoped to "
            "the fold and the pages it was read on; a ruled row still appears, "
            "flagged and carrying its reason, and an entry whose conflict no "
            "longer occurs reports as stale. Nothing here is exempted in "
            "`proposal marks`: a proposal records what a reader wrote, and that "
            "is the measurement rather than a defect to silence")

    add("glosses", glossary,
        help="the corpus's term<->gloss pairs from committed TEI — "
            "the dictionary the <gloss target> links make queryable. Pairs come "
            "from @target and never from containment, so terms nobody has linked "
            "are reported as a count rather than guessed at. `scope` is the frame "
            "the entry's gloss list supplies once as a supplied <head> and its "
            "glosses never repeat — without which “white mixed with brown” says "
            "nothing about what is white. It can arrive from the previous page: "
            "a list running across a seam carries no second head, so the scope "
            "resolves back through @prev")


def _emit(a, fn) -> int:
    out(a, fn(a.root))
    return 0
