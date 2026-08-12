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

import click

from ..detectors import (
    digraph_frequency,
    mark_base_frequency,
    suffix_frequency,
    suggest_lexicon,
    suggest_native_forms,
)
from ..ids import glossary
from ..ipa import rows as ipa_rows
from ..lookup import search
from ..marks import gt_conflicts
from ._common import action, arg, group, opt, out


def register(cli):
    g = group(cli, "lexicon", "frequency reports over the native corpus "
              "— misses to whitelist, forms to compare against, marks, "
              "affixes and n-grams — plus the term<->gloss dictionary "
              "from committed TEI",
              section="Apparatus and reports")
    add = lambda name, fn, **kw: action(g, name, lambda a: _emit(a, fn), **kw)

    add("misses", suggest_lexicon, help="frequency-ranked lexicon_miss tokens across every "
            "OCR'd page, for bulk approval — a proper noun into entities/, "
            "anything else into data/lexicon_extra.txt. Both suppress "
            "lexicon_miss and nothing else, and a Tier-1 form in either is "
            "inert by construction, since the detector only ever tests ASCII "
            "components. `suppressed` names what the entity store already "
            "accounts for, so the second source is never a silent one")

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

    p = action(g, "lookup", run_lookup,
               help="a ratified native form by a typeable key, with the lines it "
               "was printed on. **The key is marked ASCII and deliberately not "
               "pretty** — `Kuluˊči` is `Kulu'c^i` — because a plain-ASCII key "
               "would spell `Kavraˊlɪt` as `kavralit` and teach an `i` that is not "
               "there, which is the corpus's largest correction family. Match is a "
               "substring of the key, the fold, the form or the key's bare "
               "reduction, so `kulu` finds it. **A word the book spells more than "
               "one way yields no key at all**, and a ruling in "
               "data/marks_exempt.json does not restore it: that ruling says the "
               "ambiguity is real. The key is what a reader writes in braces for "
               "`proposal set` to expand. Reports; never gates"
               "\n\nQUERY: any substring; several are an OR")
    arg(p, "queries", nargs=-1, required=True, metavar="QUERY")
    opt(p, "--min-pages", type=int, default=2,
        help="withhold the key from a word attested on fewer pages than this — "
             "one page is a neighbour, not a convention. Counted per fold over "
             "all its spellings, so the floor can never hide a conflict [2]")
    opt(p, "--context", type=int, default=2,
        help="lines of surrounding text per matched form, which is what makes a "
             "form's sense readable without opening the page [2]")

    p = action(g, "ipa", run_ipa,
               help="imputed IPA for a keyed native form. **The table is a rule "
               "table and nothing here is evidence** — it reads no scan, settles "
               "no glyph, and is a pronunciation sketch of a form a human already "
               "keyed. Rows are graded: `myth` is Bogoras's own account of his "
               "notation in the front matter to *Chukchee Mythology*, `key` is the "
               "printed key at Part 1 p. 10 for the unmarked ASCII sorts it does "
               "not reach. A form containing a sort with no row, or the "
               "undecidable U+0027, comes back `partial` with the characters "
               "named, rather than silently skipping one. Reports; never gates"
               "\n\nFORM: a keyed form, NFD or not; several are several rows")
    arg(p, "forms", nargs=-1, required=False, metavar="FORM")
    opt(p, "--all", "every_form", is_flag=True,
        help="every native form in restored gt/ocr/ instead of the named ones — "
             "the coverage report, which is what says whether the table reaches "
             "the corpus [off]")
    opt(p, "--partial", is_flag=True,
        help="only the forms that did not resolve, which is the worklist "
             "the table is extended from [off]")

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


def run_lookup(a) -> int:
    r = search(list(a.queries), a.root, min_pages=a.min_pages, context=a.context)
    out(a, [{k: v for k, v in r.items() if k not in ("matches", "context")}],
        name="scope")
    out(a, r["matches"], name="matches", heading=True)
    out(a, r["context"], name="context", heading=True)
    return 0


def run_ipa(a) -> int:
    if a.every_form:
        forms = [r["form"] for r in suggest_native_forms(a.root)]
    else:
        forms = list(a.forms)
    if not forms:
        raise click.UsageError("name a FORM, or --all for every native form in gt/ocr/")
    rows = ipa_rows(forms)
    scope = {"forms": len(rows),
             "complete": sum(r["state"] == "complete" for r in rows),
             "partial": sum(r["state"] == "partial" for r in rows)}
    if a.partial:
        rows = [r for r in rows if r["state"] == "partial"]
    out(a, [scope], name="scope")
    out(a, rows, name="forms", heading=True)
    return 0


def _emit(a, fn) -> int:
    out(a, fn(a.root))
    return 0
