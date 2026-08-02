"""`harness lexicon` — frequency reports over the corpus, and the gloss dictionary.

Six actions where there were six mutually-exclusive-in-fact flags on one verb,
declared independent and resolved by if-chain precedence, so `--marks --native`
silently ran `--marks`.

Five read restored ground truth in `gt/ocr/`; `glosses` reads committed TEI
instead, which is why it is worth naming its source in the help rather than
letting the group heading imply one store. All are report-only and exit 0.
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
from ._common import out


def register(sub, common):
    g = sub.add_parser("lexicon", help="frequency reports over the native corpus "
                       "— misses to whitelist, forms to compare against, marks, "
                       "affixes and n-grams — plus the term<->gloss dictionary "
                       "from committed TEI")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    p = add("misses", help="frequency-ranked lexicon_miss tokens across every "
            "OCR'd page, for bulk approval into data/lexicon_extra.txt. That "
            "file suppresses lexicon_miss and nothing else — a Tier-1 form "
            "listed there is inert by construction, since the detector only "
            "ever tests ASCII components")
    p.set_defaults(func=lambda a: _emit(a, suggest_lexicon))

    p = add("native", help="invert: the most frequent native (Tier-1) word forms "
            "in restored gt/ocr/, for spotting a likely misspelling by "
            "comparison rather than by dictionary")
    p.set_defaults(func=lambda a: _emit(a, suggest_native_forms))

    p = add("marks", help="bare-vs-marked frequency per base letter across the "
            "native corpus — e.g. is a bare g or a dotted g̣ the more likely "
            "reading, prior to opening the raster")
    p.set_defaults(func=lambda a: _emit(a, mark_base_frequency))

    p = add("suffixes", help="weighted suffix frequency (length 2-8) over the "
            "native corpus, diacritics and stress marks stripped before counting")
    p.set_defaults(func=lambda a: _emit(a, suffix_frequency))

    p = add("digraphs", help="weighted digraph/trigraph frequency over the native "
            "corpus, with marks and the corpus's own top suffixes stripped first "
            "so stems aren't drowned by the suffix family repeating itself")
    p.set_defaults(func=lambda a: _emit(a, digraph_frequency))

    p = add("glosses", help="the corpus's term<->gloss pairs from committed TEI — "
            "the dictionary the <gloss target> links make queryable. Pairs come "
            "from @target and never from containment, so terms nobody has linked "
            "are reported as a count rather than guessed at. `scope` is the frame "
            "the entry's gloss list supplies once as a supplied <head> and its "
            "glosses never repeat — without which “white mixed with brown” says "
            "nothing about what is white. It can arrive from the previous page: "
            "a list running across a seam carries no second head, so the scope "
            "resolves back through @prev")
    p.set_defaults(func=lambda a: _emit(a, glossary))


def _emit(a, fn) -> int:
    out(a, fn(a.root))
    return 0
