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

import sys
from pathlib import Path

from ..marks import marks as marks_report
from ..paths import proposal_path
from ..proposal_check import _parse_which, line_codepoints, replace_in_field
from ..proposal_check import check as check_proposal
from ..proposal_check import fix as fix_proposal
from ..proposal_check import set_field as set_proposal_field
from ._common import out

REF_HELP = "page ref: part and scan index, e.g. 1-052"
PATH_HELP = "proposal file (default review/PP-NNN/proposal.json)"
FIELD_HELP = ("which field of the line to act on (default text). Applies to "
              "codepoints, set and replace alike")


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
        import argparse
        raise argparse.ArgumentTypeError(
            f"{v!r}: expected all, first, last, an occurrence number (3), or an "
            f"inclusive range (2:4), all 1-based — {e}") from e
    return v


def _target(p, **kw):
    p.add_argument("ref", metavar="PP-NNN", help=REF_HELP)
    p.add_argument("--path", type=Path, default=None, help=PATH_HELP)
    return p


def register(sub, common):
    g = sub.add_parser("proposal", help="a page's reading proposal — the "
                       "resolved/text cross-check, and the field editors that "
                       "keep patching one out of ad-hoc Python")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    p = _target(add("check", help="cross-check the `resolved` field against the "
                "codepoints `text` actually contains — catches a mistyped "
                "combining mark (ring below for dot below, diaeresis for caron) "
                "before it reaches review. Also flags a straight apostrophe "
                "anywhere (never a genuine reading, corpus-wide) and a bare "
                "suffix matching a known dot-prone shape (keying_spec.md §5.1, "
                "e.g. -gɪn/-gɪt/-gɪ missing g's dot-below). Exit 1 on any "
                "mismatch"))
    p.set_defaults(func=run_check)

    p = _target(add("fix", help="apply the one unambiguous correction — a single "
                "mark the resolved field names but the text doesn't contain, "
                "swapped for the single mark text has that resolved doesn't — "
                "and write the file back"))
    p.set_defaults(func=run_fix)

    p = _target(add("codepoints", help="name every non-ASCII character in one "
                "line's field, instead of running the resolved/text check — a "
                "spot check while authoring, before resolved is even written"))
    p.add_argument("line", metavar="LINE", help="the line's index")
    p.add_argument("--field", default="text", choices=("text", "resolved", "note"),
                   help=FIELD_HELP)
    p.set_defaults(func=run_codepoints)

    p = _target(add("set", help="set one line's field. The value is NFD-"
                "normalized on write, so it never fights an Edit-tool exact-match "
                "failure against the file's own NFD form"))
    p.add_argument("line", metavar="LINE", help="the line's index")
    p.add_argument("--field", default="text", choices=("text", "resolved", "note"),
                   help=FIELD_HELP)
    p.add_argument("--value", default=None,
                   help="the replacement text; omit to read stdin")
    p.set_defaults(func=run_set)

    p = _target(add("replace", help="replace occurrence(s) of --old with --new in "
                "one line's field — the surgical alternative to `set` for a "
                "single wrong character in an otherwise-correct line, which "
                "retypes the whole field and risks a second, unrelated slip "
                "while fixing the first"))
    p.add_argument("line", metavar="LINE", help="the line's index")
    p.add_argument("--old", required=True, help="text to find")
    p.add_argument("--new", required=True, help="text to substitute")
    p.add_argument("--field", default="text", choices=("text", "resolved", "note"),
                   help=FIELD_HELP)
    p.add_argument("--which", default="all", type=_which,
                   help="which occurrence(s) of --old to replace — \"all\" "
                        "(default), \"first\", \"last\", an occurrence number "
                        "(\"3\"), or an inclusive range (\"2:4\"), all 1-based, "
                        "left to right")
    p.set_defaults(func=run_replace)

    p = add("marks", help="is the character distribution of these readings "
            "plausible — before a human opens them. Three arms: `rare` lists a "
            "form the corpus almost never sets (a bare g is 6.1%% of Tier-1 g); "
            "`conflict` finds one word spelled two ways across the refs and the "
            "store; `ratio` compares the expected-form share, in types, against a "
            "leave-one-out prior. Pass every ref of a pass together: most pages "
            "carry a handful of Tier-1 terms, so pooling gives a sample worth "
            "holding against the corpus, and one job adrift reads differently "
            "from every job leaning the same way — the second is the prompt or "
            "the spec. Always exits 0")
    p.add_argument("ref", metavar="PP-NNN", nargs="+",
                   help=REF_HELP + ". Pass several: they are reported "
                        "individually and pooled as scope=ALL")
    p.add_argument("--decisions", action="store_true",
                   help="read decision.json instead of proposal.json — the last "
                        "state before restore writes; the pair of runs brackets "
                        "the adjudication")
    p.add_argument("--min-types", type=int, default=None, metavar="N",
                   help="types a scope needs before ratio judges it; under this "
                        "the row reads outside=? [data/marks_config.json]")
    p.add_argument("--rare-max", type=float, default=None, metavar="PCT",
                   help="a confusable at or below this share of its axis is rare "
                        "enough to list every occurrence [data/marks_config.json]")
    p.set_defaults(func=run_marks)


def _path(a) -> Path:
    return a.path or proposal_path(a.ref, a.root)


def run_check(a) -> int:
    mismatches = check_proposal(_path(a), a.ref, a.root)
    out(a, mismatches)
    return 1 if mismatches else 0


def run_fix(a) -> int:
    out(a, fix_proposal(_path(a)))
    return 0


def run_codepoints(a) -> int:
    out(a, line_codepoints(_path(a), a.line, a.field))
    return 0


def run_set(a) -> int:
    value = a.value if a.value is not None else sys.stdin.read().rstrip("\n")
    out(a, set_proposal_field(_path(a), a.line, a.field, value))
    return 0


def run_replace(a) -> int:
    out(a, replace_in_field(_path(a), a.line, a.field, a.old, a.new, a.which))
    return 0


def run_marks(a) -> int:
    out(a, marks_report(a.ref, a.root, decisions=a.decisions,
                        min_types=a.min_types, rare_max=a.rare_max))
    return 0
