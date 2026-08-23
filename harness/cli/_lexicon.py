"""`harness lexicon` — the edition lexicon, its reports, and the gloss dictionary.

Two halves under one group, and the split is worth naming because the group used
to be only the first. **The reports** are frequency arms over restored ground
truth in `gt/ocr/` — misses to file, forms to compare against, marks, affixes,
n-grams — plus `glosses`, which reads committed TEI instead and says so in its
help rather than letting the group heading imply one store. They are report-only
and exit 0. `conflicts` is the only one that consults a *ruling*,
`data/marks_exempt.json`; it is here rather than beside `proposal marks` because
the exemptible question is about the corpus, not about a reader.

**The store** is `new` / `check` / `show` / `ratify`, over `lexicon/`, and takes
the `--commit` discipline every authored store takes. It is thin on purpose: an
entry holds an editor's note and nothing else, because everything else a card
shows — the pronunciation, the attesting pages, the glosses the book prints — is
derived on every load. See `harness/lexicon.py`.
"""
from __future__ import annotations

import click

from .. import lexicon as lex
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
from ..render import progress
from ._common import action, arg, group, opt, out, verdict


def register(cli):
    g = group(cli, "lexicon", "the edition lexicon — one entry per Tier-1 form "
              "an editor has written a note about — plus the frequency reports "
              "over the native corpus and the term<->gloss dictionary from "
              "committed TEI",
              section="Apparatus and reports")
    add = lambda name, fn, **kw: action(g, name, lambda a: _emit(a, fn), **kw)

    p = action(g, "misses", run_misses,
               help="frequency-ranked lexicon_miss tokens across every "
               "OCR'd page, for bulk approval — a proper noun into entities/, "
               "anything else into data/lexicon_extra.txt. Both suppress "
               "lexicon_miss and nothing else, and a Tier-1 form in either is "
               "inert by construction, since the detector only ever tests ASCII "
               "components. `suppressed` names what the entity store already "
               "accounts for, so the second source is never a silent one. "
               "`--common` asks the other question: the dictionary accounts for "
               "every proper noun English happens to spell as a word — `Wolf`, "
               "`Frost`, `Bering` — which is the class of entity candidate this "
               "report is blindest to, so that flag drops it")
    opt(p, "--common", type=click.IntRange(min=0), is_flag=False,
        flag_value=1000, default=None, metavar="N",
        help="report every token the corpus prints instead of the dictionary "
             "misses, less the N commonest word forms and less what entities/ "
             "accounts for. The stoplist is the corpus's own frequency table "
             "and not an imported list, N is a request rather than a count — "
             "the cut lands on a frequency boundary so a tie is never split by "
             "alphabet — and the least frequent words it swallowed are printed "
             "back as `boundary`, which is what says whether N was well chosen. "
             "Folds an English possessive onto the name it is made from, and "
             "moves a row whose every occurrence opens a sentence *and* whose "
             "form the dictionary carries into `sentence_heads` — both "
             "conditions, since either alone loses a real name silently. "
             "Bare, it means 1000 [off]")

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
               "\n\nQUERY: any substring; several are an OR, and a page's whole "
               "unglossed vocabulary belongs in one call — `lexicon lookup kelet "
               "vairgin kulu` is one index build answering three questions, where "
               "three calls are three builds")
    # **The metavar carries the arity, because `-h`'s usage line is where a caller
    # reads it.** This was `QUERY`, and the prose two lines up saying "several are
    # an OR" did not survive the contradiction: readers on the 2-003..2-022 and
    # 2-023.. batches looked up forms one command at a time, paying a fresh index
    # build each, which is the plural convention this repo already applies to refs
    # losing to a singular noun in the usage line.
    arg(p, "queries", nargs=-1, required=True, metavar="QUERY [QUERY ...]")
    opt(p, "--min-pages", type=int, default=1,
        help="withhold the key from a word attested on fewer pages than this. "
             "Counted per fold over all its spellings, so the floor can never hide "
             "a conflict. Defaults to 1 — a hapax the corpus adjudicated once still "
             "gets a key, because most of this vocabulary is rare and withholding "
             "one only sends a reader to retype the form by hand [1]")
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

    p = action(g, "new", run_new,
               help="scaffold an entry at `status: proposed`. **The identity is "
               "the form itself** — the exact string as the page sets it, NFD, "
               "with no language: a form only becomes `ckt` when a collator "
               "judges it, and most of the corpus is unjudged, so a key holding "
               "a language would leave those forms unaddressable. The file name "
               "is a slug you choose; the default is the typeable key reduced "
               "to what a filesystem is safe with, which is not the key itself "
               "because `handle_key` keeps case and emits colons"
               "\n\nFORM: the form, e.g. `Kuluˊči`")
    arg(p, "form", metavar="FORM")
    opt(p, "--slug", metavar="SLUG",
        help="the file name, without `.md`. Defaults to the reduced key; give "
             "one where that collides or reads badly")
    opt(p, "--see", metavar="FORM",
        help="another form in the store this one points at — a variant setting, "
             "a related word. **A pointer and not a claim that the two are one "
             "word**: where the book sets a word two ways that difference is a "
             "finding, and no field here overrides it")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this the file is reported and not created")

    action(g, "check", run_check,
           help="the store gate: every file parses, every identity is unique, no "
           "two slugs differ only in case — which a case-insensitive filesystem "
           "would collapse to one file, silently — and every `see:` resolves. "
           "Exit 1 on any of it. A form the handle key cannot spell is reported "
           "and never fatal: the entry is fine, what it has not got is a "
           "canonical URL, and a reader is owed that fact")

    p = action(g, "show", run_show,
               help="whole records, the editor's note included"
               "\n\nFORM: the form as the heading sets it; several are allowed")
    arg(p, "forms", nargs=-1, required=True, metavar="FORM")

    p = action(g, "ratify", run_ratify,
               help="proposed -> ratified. The human act, and it means the note "
               "has been read against the pages the form occurs on"
               "\n\nFORM: several are allowed")
    arg(p, "forms", nargs=-1, required=True, metavar="FORM")
    opt(p, "--commit", is_flag=True, help="write the change")


LEX_TEMPLATE = """# {form}

- status: proposed
{extra}
## editor's note

(unwritten)
"""


def _resolve_forms(a, store: dict) -> list[str]:
    """The forms named on the command line, refused up front if any is unknown."""
    forms = [lex.norm_form(str(f)) for f in a.forms]
    missing = [f for f in forms if f not in store]
    if missing:
        raise ValueError(f"no such lexicon entry: {', '.join(missing)}")
    return forms


def run_new(a) -> int:
    form = lex.norm_form(str(a.form))
    if not form:
        raise ValueError("the form is empty")
    slug = a.slug or lex.suggest_slug(form)
    p = lex.path_for(slug, a.root)
    if p.exists():
        out(a, {"form": form, "path": str(p), "wrote": False,
                "means": "already exists"})
        return 1
    extra = f"- see: {lex.norm_form(a.see)}\n" if a.see else ""
    text = LEX_TEMPLATE.format(form=form, extra=extra)
    # Parsed before it is written, as `entity new` does: a bad `--see` fails as
    # a message rather than as a file the next `check` has to explain.
    lex.parse(text, where=str(p))
    if a.commit:
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(p, "x", encoding="utf-8") as fh:
                fh.write(text)
        except FileExistsError:
            out(a, {"form": form, "path": str(p), "wrote": False,
                    "means": "already exists — written while this ran"})
            return 1
    out(a, {"form": form, "slug": slug, "path": str(p), "wrote": bool(a.commit),
            "means": "written, status proposed" if a.commit
                     else "would write — pass --commit"})
    return 0


def run_check(a) -> int:
    try:
        r = lex.check(a.root)
    except (lex.Malformed, ValueError) as e:
        out(a, [{"error": str(e)}], "errors", heading=True)
        return verdict(a, 1, "the store does not parse")
    out(a, {k: v for k, v in r.items()
            if k not in ("unkeyable", "errors", "ok")})
    if r["unkeyable"]:
        out(a, r["unkeyable"], "unkeyable", heading=True)
    if r["errors"]:
        out(a, [{"error": e} for e in r["errors"]], "errors", heading=True)
    return verdict(a, 0 if r["ok"] else 1,
                   "the store is coherent" if r["ok"]
                   else "the store has defects; nothing was written")


def run_show(a) -> int:
    store = lex.load(a.root)
    for f in _resolve_forms(a, store):
        out(a, store[f], name=f, heading=True)
    return 0


def run_ratify(a) -> int:
    from pathlib import Path

    store = lex.load(a.root)
    rows = []
    for f in _resolve_forms(a, store):
        rec = store[f]
        if rec["status"] == "ratified":
            rows.append({"form": f, "was": "ratified", "now": "ratified",
                         "wrote": False})
            continue
        p = Path(rec["path"])
        text = p.read_text(encoding="utf-8")
        # Through the store's own field writer, not a substring replace: the
        # parser accepts `- status:proposed` without the space and reads fields
        # only above the first `## section`, so a literal search could land in
        # the editor's note and report a ratification that never happened.
        new = lex.set_status(text, "ratified", where=str(p))
        if new == text:
            raise ValueError(f"{p}: status was already `ratified` in the file "
                             f"though the store read it as {rec['status']!r}")
        if a.commit:
            p.write_text(new, encoding="utf-8")
        rows.append({"form": f, "was": "proposed", "now": "ratified",
                     "wrote": bool(a.commit)})
    out(a, rows)
    return 0


def run_lookup(a) -> int:
    with progress("indexing the corpus") as tick:
        r = search(list(a.queries), a.root, min_pages=a.min_pages,
                   context=a.context, tick=tick)
    out(a, [{k: v for k, v in r.items() if k not in ("matches", "context")}],
        name="scope")
    out(a, r["matches"], name="matches", heading=True)
    out(a, r["context"], name="context", heading=True)
    return 0


def run_ipa(a) -> int:
    if a.every_form:
        with progress("reading the corpus") as tick:
            forms = [r["form"] for r in suggest_native_forms(a.root, tick)]
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


def run_misses(a) -> int:
    # `--common`'s range is the parser's, per VERBS.md's Conventions: 0 is a
    # legible request (cut nothing) and a negative is not a count at all.
    with progress("reading the corpus") as tick:
        rep = suggest_lexicon(a.root, common=a.common, tick=tick)
    out(a, rep)
    return 0


def _emit(a, fn) -> int:
    """The five frequency arms and `glosses`, each one call over a whole store.

    **Every `fn` here takes `tick`, and that is a condition of registering one
    through `add`** rather than something this checks: the reports differ in what
    they count and not in what they walk, so an arm that could not report its
    progress would be the one silent verb in a group whose every other member is
    the same sweep under a different tally.
    """
    with progress("reading the corpus") as tick:
        rep = fn(a.root, tick=tick)
    out(a, rep)
    return 0
