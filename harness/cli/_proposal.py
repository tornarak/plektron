"""`harness proposal` — the reading proposal in `review/PP-NNN/proposal.json`.

`check` is the gate; the other four are field editors, and they exist so that
inspecting or patching a proposal never needs ad-hoc Python. A hand-typed `Edit`
against this file can silently fail to match its own NFD form — a precomposed
`ñ` typed by hand is not the file's `n` + U+0303 — which is exactly the class of
failure `set`/`replace` remove by normalizing on write.

These write without `--commit`, unlike everything touching `gt/` or `tei/`.
A proposal is a working file of a live pass, kept with a `.prev` and a journal,
not an authored store; and the pass that runs these is mid-page with the raster
open, which is the human act a gate would otherwise be asking for twice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ..detectors import native_corpus
from ..marks import marks as marks_report
from ..paths import proposal_path
from ..proposal_check import DEFECT, _parse_which, line_codepoints, replace_in_field
from ..proposal_check import _lexicon_loader as lexicon_loader
from ..proposal_check import check as check_proposal
from ..proposal_check import fix as fix_proposal
from ..proposal_check import set_field as set_proposal_field
from ..proposal_check import set_fields as set_proposal_fields
from ._common import (
    REF_HELP,
    action,
    arg,
    group,
    one_page_only,
    opt,
    out,
    out_per_ref,
    page_refs,
    refs_arg,
    verdict,
)

PATH_HELP = "proposal file (default review/PP-NNN/proposal.json)"
FIELD_HELP = ("which field of the line to act on (default text). Applies to "
              "codepoints, set and replace alike. `class` is the note's class and "
              "takes a closed vocabulary — doubt, semantic, print, draft, layout, "
              "artifact — refused at the write rather than reported afterwards, "
              "since an unknown class reads downstream as no class at all")


def _which(v: str) -> str:
    """Validate `--which` at parse time rather than inside the replacer.

    The grammar is small — all/first/last/N/N:M — but it is a grammar, so
    `choices=` cannot express it. Parsing it here means a typo is a usage error
    with the accepted forms in the message, not a traceback after the file has
    been opened.
    """
    try:
        _parse_which(v, 1)
    except (ValueError, KeyError) as e:
        raise click.BadParameter(
            f"{v!r}: expected all, first, last, an occurrence number (3), or an "
            f"inclusive range (2:4), all 1-based — {e}") from e
    return v


def _target(p, all_: str | None = None):
    """The ref positional and `--path`, which is the pair that needs the guard.

    `--path` names *one* file, so it and a second ref are a usage error rather
    than a silent choice of which page it meant. The three actions that act on
    one line (`codepoints`, `set`, `replace`) take a `LINE` positional besides;
    `set` and `replace` are singular for that reason — a line index belongs to one
    proposal — while `codepoints` keeps the plural and splits the trailing bare
    number off itself, a ref and an index being disjoint token shapes here.
    """
    if all_:
        refs_arg(p, all_=all_)
    else:
        arg(p, "ref", metavar="PP-NNN")
        p.help = f"{p.help}\n\nPP-NNN: {REF_HELP}."
    opt(p, "--path", type=click.Path(path_type=Path), default=None, help=PATH_HELP)
    return p


def register(cli):
    g = group(cli, "proposal", "a page's reading proposal — the "
              "resolved/text cross-check, and the field editors that "
              "keep patching one out of ad-hoc Python",
              sections=("Checking", "Editing one field"), section="The passes")

    c = _target(action(g, "check", run_check, section="Checking",
                       help="cross-check the `resolved` field against the "
                       "codepoints `text` actually contains — catches a mistyped "
                       "combining mark (ring below for dot below, diaeresis for "
                       "caron) before it reaches review. Also flags a straight "
                       "apostrophe anywhere (never a genuine reading, corpus-wide) "
                       "and a bare suffix matching a known dot-prone shape "
                       "(keying_spec.md §5.1, e.g. -gɪn/-gɪt/-gɪ missing g's "
                       "dot-below). Every issue carries a severity; exit 1 on a "
                       "defect, never on an advisory alone"),
                all_="every review/ page with a proposal")
    opt(c, "--strict", is_flag=True,
        help="gate on advisories too — for a sweep meant to chase every prompt, "
             "not for a page pass, where a rare form that is simply rare would "
             "make the gate unpassable [off]")

    _target(action(g, "fix", run_fix, section="Editing one field",
                   help="apply the one unambiguous correction — a single "
                   "mark the resolved field names but the text doesn't contain, "
                   "swapped for the single mark text has that resolved doesn't — "
                   "and write the file back"),
            all_="every review/ page with a proposal")

    # **`LINE` is the trailing bare number, beside the plural refs.** It was a
    # `--line` flag on the argument that a variadic positional cannot tell an index
    # from another ref, which is not true here — a ref is `PP-NNN` and a bare
    # number is refused as one corpus-wide, so the two shapes are disjoint. Omitted,
    # it names every line, which is the more useful default anyway: a census of what
    # a proposal actually contains.
    p = _target(action(g, "codepoints", run_codepoints, section="Editing one field",
                       help="name every non-ASCII character in a "
                       "line's field, instead of running the resolved/text check — "
                       "a spot check while authoring, before resolved is even "
                       "written"
                       "\n\nLINE: the line's index, as a trailing bare number. "
                       "Omit it for every line on the page."),
                all_="every review/ page with a proposal")
    opt(p, "--field", default="text",
        type=click.Choice(("text", "resolved", "note", "class")), help=FIELD_HELP)

    p = _target(action(g, "set", run_set, section="Editing one field",
                       help="set one line's field, or many lines' in one write. "
                       "The value is NFD-"
                       "normalized on write, so it never fights an Edit-tool "
                       "exact-match failure against the file's own NFD form"
                       "\n\nLINE: the line's index. Omit it and pipe a "
                       '{\"line\": \"text\"} object on stdin to set many lines at '
                       "once — a page whose every line needs authoring cannot "
                       "afford two turns per line."))
    arg(p, "line", metavar="[LINE]", required=False, default=None)
    opt(p, "--field", default="text",
        type=click.Choice(("text", "resolved", "note", "class")), help=FIELD_HELP)
    opt(p, "--value", default=None, help="the replacement text; omit to read stdin")
    opt(p, "--values", default=None,
        help='the bulk form: a {"line": "text"} object setting many lines in one '
             "write, used instead of LINE. Omit both and the object is read from "
             "stdin instead")

    p = _target(action(g, "replace", run_replace, section="Editing one field",
                       help="replace occurrence(s) of --old with --new in "
                       "one line's field — the surgical alternative to `set` for a "
                       "single wrong character in an otherwise-correct line, which "
                       "retypes the whole field and risks a second, unrelated slip "
                       "while fixing the first"
                       "\n\nLINE: the line's index."))
    arg(p, "line", metavar="LINE")
    opt(p, "--old", required=True, help="text to find")
    opt(p, "--new", required=True, help="text to substitute")
    opt(p, "--field", default="text",
        type=click.Choice(("text", "resolved", "note", "class")), help=FIELD_HELP)
    opt(p, "--which", default="all", callback=lambda c, prm, v: _which(v),
        help="which occurrence(s) of --old to replace — \"all\" "
             "(default), \"first\", \"last\", an occurrence number "
             "(\"3\"), or an inclusive range (\"2:4\"), all 1-based, "
             "left to right")

    p = action(g, "marks", run_marks, section="Checking",
               help="is the character distribution of these readings "
            "plausible — before a human opens them. Three arms: `rare` lists a "
            "form the corpus almost never sets (a bare g is 6.1% of Tier-1 g); "
            "`conflict` finds one word spelled two ways across the refs and the "
            "store; `ratio` compares the expected-form share, in types, against a "
            "leave-one-out prior. Pass every ref of a pass together: most pages "
            "carry a handful of Tier-1 terms, so pooling gives a sample worth "
            "holding against the corpus, and one job adrift reads differently "
            "from every job leaning the same way — the second is the prompt or "
            "the spec. Always exits 0")
    refs_arg(p, all_="every review/ page with a proposal",
             extra=": they are reported individually and pooled as scope=ALL. "
                   "**--all says less than a batch does** — the prior is "
                   "leave-one-out over gt/ocr/, so pooling every proposal drives "
                   "the sample towards its own prior and the ratio arm goes quiet")
    opt(p, "--decisions", is_flag=True,
        help="read decision.json instead of proposal.json — the last "
             "state before restore writes; the pair of runs brackets "
             "the adjudication")
    opt(p, "--min-types", type=int, default=None, metavar="N",
        help="types a scope needs before ratio judges it; under this "
             "the row reads outside=? [data/marks_config.json]")
    opt(p, "--rare-max", type=float, default=None, metavar="PCT",
        help="a confusable at or below this share of its axis is rare "
             "enough to list every occurrence [data/marks_config.json]")


def _path(a, ref: str | None = None) -> Path:
    return a.path or proposal_path(ref or a.ref, a.root)


def _proposals(a) -> list[str]:
    """The pages this invocation names, or every one holding a proposal.

    `--path` names one file, so it and a second ref are a usage error. `review/`
    is authored working state rather than a farm or a store, so an empty answer
    is a true statement — nothing has been proposed — and not an unbuilt tree.
    """
    refs = page_refs(a)
    one_page_only(a, {"path": "--path"}, refs)
    if refs:
        return refs
    from ..paths import page_refs_under
    return [r for r in page_refs_under(a.root)
            if proposal_path(r, a.root).exists()]


def run_check(a) -> int:
    # Every ref in the run is excluded from every page's prior. A batch's pages
    # were read by agents forbidden to see each other, so two of them agreeing is
    # one witness, not two — and after `restore` both sit in `gt/ocr/` looking
    # like corroboration. See `proposal_check._named_key_issues`.
    refs = list(_proposals(a))
    cohort = frozenset(refs)
    # Built once for the run, not once per page: the cohort is the same for every
    # ref, so the index each page would build is the same index. Lazy, so a run
    # whose notes never name a key still pays nothing.
    lex = lexicon_loader(a.root, cohort)
    # Same reasoning for `marks.page_issues`' prior: one walk of `gt/ocr/` for the
    # run rather than one per page. The walk does not depend on the ref — only the
    # leave-one-out filtering does — and it is 2.4s at 645 pages.
    corpus = native_corpus(a.root) if len(refs) > 1 else None
    # The second index: full, for the handle-resolves check. See `check`.
    lex_all = lexicon_loader(a.root, ())
    pairs = [(r, check_proposal(_path(a, r), r, a.root, cohort, lex, corpus,
                                lex_all)) for r in refs]
    # Exit is the worst across refs: one dirty page fails the batch, which is the
    # contract a gate has to have or a batch would launder a failure.
    out_per_ref(a, pairs)
    # **Gated on defects, not on the report being non-empty.** An advisory is
    # measurement — a corpus share saying "go look" — and measurement never gates
    # (VERBS.md, Conventions). It gated until now, and since a rare-but-correct
    # form cannot be made common, the gate was unsatisfiable: eight of eighteen
    # failing proposals failed on advisories alone, and the reading brief had been
    # rewritten to teach readers that exit 1 is sometimes fine. `--strict` restores
    # the old behaviour for a sweep that means to chase every prompt.
    gating = [m for _, ms in pairs for m in ms
              if a.strict or m.get("severity", DEFECT) == DEFECT]
    # The severity split is exactly what the exit code cannot express: 0 with
    # advisories printed and 0 with nothing found are the same number and not the
    # same result, and a reader that cannot run `echo $?` was reading the empty
    # table for the difference. Named here, once, in the verb's own words.
    found = [m for _, ms in pairs for m in ms]
    advisories = len(found) - len([m for m in found
                                   if m.get("severity", DEFECT) == DEFECT])
    if gating:
        means = (f"{len(gating)} gating issue{'' if len(gating) == 1 else 's'} "
                 "above — each is yours to fix, then run this again")
    elif advisories:
        means = (f"no defects; {advisories} "
                 f"advisor{'y' if advisories == 1 else 'ies'} above. An advisory "
                 "is measurement, not a fault — answer it in the line's note and "
                 "go on")
    else:
        means = "clean — no defects, no advisories"
    return verdict(a, 1 if gating else 0, means)


def run_fix(a) -> int:
    out_per_ref(a, [(r, fix_proposal(_path(a, r), a.root)) for r in _proposals(a)])
    return 0


def run_codepoints(a) -> int:
    # A trailing bare integer is the line index, and the rest are refs. The
    # ambiguity this was avoided for — "a variadic positional has no way to tell
    # the index from another ref" — does not exist in this corpus: a ref is
    # PP-NNN and a bare number is refused as one everywhere, with its own message
    # saying the printed folio is not derivable from the scan index. The two
    # token shapes are disjoint, so the split is mechanical.
    #
    # It matters because the alternative was a flag on this action and a
    # positional on `set`/`replace`, which is one shape for three actions a
    # reader uses in the same breath — and readers guessed the positional anyway.
    refs = list(getattr(a, "ref", None) or ())
    a.line = refs.pop() if refs and refs[-1].isdigit() else None
    a.ref = tuple(refs)
    out_per_ref(a, [(r, line_codepoints(_path(a, r), a.line, a.field))
                    for r in _proposals(a)])
    return 0


def run_set(a) -> int:
    if a.line is not None:
        value = a.value if a.value is not None else sys.stdin.read().rstrip("\n")
        out(a, set_proposal_field(_path(a), a.line, a.field, value, a.root))
        return 0
    # No LINE: stdin is a `{line: value}` object and every one of them is written
    # in a single pass. See `set_fields` for why the batch form is load-bearing
    # rather than a convenience.
    if a.value is not None:
        raise ValueError("--value sets one line, so it needs a LINE; the bulk "
                         "form takes its object in --values or on stdin")
    # `--values` is not redundant with stdin, and the reader is why: its guard
    # refuses any unquoted operator, so `<` and `|` are both unavailable to it and
    # stdin cannot be reached from inside a reading pass at all. This is the same
    # pairing the single form already has — `--value` or stdin — for the same
    # reason at a different scale.
    raw = a.values if a.values is not None else sys.stdin.read()
    raw = raw.strip()
    if not raw:
        raise ValueError("no LINE and no values: give a line index to set one "
                         'field, or a {"line": "text"} object in --values to set many')
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"stdin is not JSON ({e}) — the bulk form takes a "
                         '{"line": "text"} object, one entry per line to set') from e
    if not isinstance(values, dict) or not values:
        raise ValueError('stdin must be a non-empty {"line": "text"} object, not '
                         f"{type(values).__name__}")
    bad = sorted(k for k, v in values.items()
                 if not str(k).isdigit() or not isinstance(v, str))
    if bad:
        raise ValueError(f"{', '.join(bad[:5])}: every key is a line index and "
                         "every value is the field's text")
    out(a, set_proposal_fields(_path(a), values, a.field, a.root))
    return 0


def run_replace(a) -> int:
    out(a, replace_in_field(_path(a), a.line, a.field, a.old, a.new, a.which))
    return 0


def run_marks(a) -> int:
    out(a, marks_report(_proposals(a), a.root, decisions=a.decisions,
                        min_types=a.min_types, rare_max=a.rare_max))
    return 0
