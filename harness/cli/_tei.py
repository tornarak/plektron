"""`harness tei` — the TEI store, its ids, and the seam state folded out of it.

The group's domain is `tei/`: what the collation pass consumes (`context`),
what gates its output (`validate`, `header`), what names the elements inside it
(`ids`, `pair`), and what crosses a page boundary (`seam`, `state`, `ledger`).
The last three read the committed TEI and nothing else — there is no
`boundaries.json`, the files are the record.
"""
from __future__ import annotations

from pathlib import Path

from ..context import build_context
from ..emit import emit_lines
from ..ids import fix_page as fix_ids
from ..ids import pair_glosses
from ..seam import set_seam
from ..state import build_ledger, entry_state, ledger_rows
from ..validate import check_corpus_header, validate
from ._common import out

REF_HELP = "page ref: part and scan index, e.g. 1-048"


def register(sub, common):
    g = sub.add_parser("tei", help="the TEI store: the collation pass's input "
                       "contract, the gates on its output, structural ids, and "
                       "the seam state folded out of the committed files")
    act = g.add_subparsers(dest="action", required=True, metavar="ACTION")
    add = lambda name, **kw: act.add_parser(name, parents=[common], **kw)

    p = add("context", help="the whole per-page input contract for the collation "
            "pass, on stdout — seam state, ToC neighbourhood, figure zones and "
            "their captions, OCR line ids, detector flags. Deterministic and "
            "precomputed: the pass consumes this and never re-derives it")
    p.add_argument("ref", metavar="PP-NNN", help=REF_HELP)
    p.set_defaults(func=run_context)

    p = add("validate", help="the gate on one page's TEI. Exit 1 on FAIL. Checks "
            "the output contract, that every @facs resolves against a supplied "
            "zone or OCR line, and that every Tier-1 span carries a @resp rank — "
            "an unmarked span being indistinguishable from a ratified one to "
            "anything that does not look")
    p.add_argument("ref", metavar="PP-NNN", help=REF_HELP)
    p.add_argument("--ratified", action="store_true",
                   help="expect human-ratified provenance (resp='#ed') on Tier-1 "
                        "spans instead of the collation pass's '#llm'; a "
                        "remaining '#llm' becomes a worklist line")
    p.set_defaults(func=run_validate)

    p = add("state", help="one page's seam record — the folio predicted for it, "
            "what that prediction rests on, and which headings are believed "
            "open. expected_folio is null wherever the chain of transcribed "
            "pages breaks, which means read it off the image, not that anything "
            "failed")
    p.add_argument("ref", metavar="PP-NNN", help=REF_HELP)
    p.set_defaults(func=run_state)

    p = add("ids", help="check one page's structural ids against the scheme "
            "{kind}-{PP-NNN}-{ordinal}, where the ordinal is the element's "
            "position among same-kind elements in document order — so every id "
            "is recomputable from the tree alone. --commit renumbers, repairing "
            "any inbound @prev/@next from a neighbour in the same write")
    p.add_argument("ref", metavar="PP-NNN", help="page ref, e.g. 1-100")
    p.add_argument("--commit", action="store_true",
                   help="write the canonical ids (and neighbours' pointers); "
                        "without it, report what would change")
    p.set_defaults(func=run_ids)

    p = add("pair", help="link each <gloss> to its <term> where containment "
            "decides — one of each in a container. Where it does not (two pairs "
            "in one item), report and write nothing: choosing would be "
            "inference. --commit to write")
    p.add_argument("ref", metavar="PP-NNN", help="page ref, e.g. 1-100")
    p.add_argument("--commit", action="store_true",
                   help="write the gloss->term links; without it, report what "
                        "would change")
    p.set_defaults(func=run_pair)

    p = add("seam", help="record whether an element runs across the gap BEFORE "
            "this page, writing @part on this page's first top-level element and "
            "the previous page's last. The page after the gap writes both ends, "
            "because it is the only one holding both witnesses. Preview unless "
            "--commit")
    p.add_argument("ref", metavar="PP-NNN",
                   help="the page AFTER the gap, e.g. 1-100 for the 1-099/1-100 seam")
    mx = p.add_mutually_exclusive_group(required=True)
    mx.add_argument("--continues", dest="open_gap", action="store_true",
                    help="an element carries across: this page opens mid-element")
    mx.add_argument("--fresh", dest="open_gap", action="store_false",
                    help="clean break: this page opens a new element. Clears the "
                         "claim on both sides if one was recorded")
    p.add_argument("--commit", action="store_true",
                   help="write both files; without it, report what would change")
    p.set_defaults(func=run_seam)

    p = add("ledger", help="the seam table across every scan — folio, heading "
            "fold, and whether an element runs across the gap after each page. "
            "That last is read off the committed TEI's @part/@next, where "
            "`tei seam` puts it; 'unknown' means the page is not collated, not "
            "that it is closed")
    p.add_argument("--part", type=int, default=None, help="restrict to one part")
    p.add_argument("--untranscribed", action="store_true",
                   help="refs with no committed TEI — bare, one per line, to "
                        "pipe into xargs; a JSON array under --json")
    p.set_defaults(func=run_ledger)

    p = add("header", help="the gate on the corpus teiHeader — that it exists, "
            "and that the provenance ranks it declares are exactly the ones "
            "`tei validate` enforces on every page. Two files hold one fact; "
            "without this they can drift apart silently, because a page is a "
            "fragment and never resolves @resp locally. Exit 1 on FAIL")
    p.set_defaults(func=run_header)


def run_context(a) -> int:
    out(a, build_context(a.ref, a.root))
    return 0


def _render_gate(a, rep) -> int:
    """A Report's two faces. The default is the rendered text, because a human
    reads it to decide whether to commit; `--json` is for anything consuming the
    verdict as data. The exit code is the contract either way."""
    if getattr(a, "json", False):
        out(a, {"ok": rep.ok, "errors": rep.errors, "warnings": rep.warnings,
                "worklist": rep.worklist, "metrics": rep.metrics})
    else:
        print(rep.render())
    return 0 if rep.ok else 1


def run_validate(a) -> int:
    ctx = build_context(a.ref, a.root)
    return _render_gate(a, validate(Path(ctx["output_path"]), ctx,
                                    ratified=a.ratified))


def run_header(a) -> int:
    return _render_gate(a, check_corpus_header(a.root))


def run_state(a) -> int:
    out(a, entry_state(a.ref, a.root))
    return 0


def run_ids(a) -> int:
    out(a, fix_ids(a.ref, a.root, commit=a.commit))
    return 0


def run_pair(a) -> int:
    out(a, pair_glosses(a.ref, a.root, commit=a.commit))
    return 0


def run_seam(a) -> int:
    out(a, set_seam(a.ref, a.open_gap, a.root, commit=a.commit))
    return 0


def run_ledger(a) -> int:
    if a.untranscribed:
        # A work queue, not a document: bare refs pipe into xargs. Under --json
        # the same refs come back as an array — the serializer changes, the
        # payload does not, which is the rule everywhere else in this CLI and
        # used to be violated here alone.
        from ..context import parse_ref
        led = build_ledger(a.root)
        refs = [r for r, v in led.items()
                if not v["transcribed"]
                and (a.part is None or parse_ref(r)[0] == a.part)]
        if getattr(a, "json", False):
            out(a, refs)
        else:
            print(emit_lines(refs))
        return 0
    out(a, ledger_rows(a.root, part=a.part))
    return 0
