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
from ._common import REF_HELP, out, out_per_ref, page_refs, refs_arg, section


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
    # **Singular, and one of only four in the CLI.** The payload is one page's
    # collation prompt, built to be handed to one model for one page; a merged
    # stream of them is not consumable by the thing it exists for.
    p.add_argument("ref", metavar="PP-NNN", help=REF_HELP)
    p.set_defaults(func=run_context)

    p = add("validate", help="the gate on a page's TEI. Exit 1 on FAIL. Checks "
            "the output contract, that every @facs resolves against a supplied "
            "zone or OCR line, and that every Tier-1 span carries a @resp rank — "
            "an unmarked span being indistinguishable from a ratified one to "
            "anything that does not look")
    refs_arg(p, all_="every collated page in tei/",
             extra=", each rendered as its own report under a `# REF` line — "
                   "prose does not pool, so this is the one action that does not")
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
    # No `--all`: `tei ledger` *is* the corpus form of this, and a second
    # spelling of one report is how two answers to one question start to drift.
    refs_arg(p)
    p.set_defaults(func=run_state)

    p = add("ids", help="check one page's structural ids against the scheme "
            "{kind}-{PP-NNN}-{ordinal}, where the ordinal is the element's "
            "position among same-kind elements in document order — so every id "
            "is recomputable from the tree alone. --commit renumbers, repairing "
            "any inbound @prev/@next from a neighbour in the same write")
    refs_arg(p, all_="every collated page in tei/")
    p.add_argument("--commit", action="store_true",
                   help="write the canonical ids (and neighbours' pointers); "
                        "without it, report what would change")
    p.set_defaults(func=run_ids)

    p = add("pair", help="link each <gloss> to its <term> where containment "
            "decides — one of each in a container. Where it does not (two pairs "
            "in one item), report and write nothing: choosing would be "
            "inference. --commit to write")
    refs_arg(p, all_="every collated page in tei/")
    p.add_argument("--commit", action="store_true",
                   help="write the gloss->term links; without it, report what "
                        "would change")
    p.set_defaults(func=run_pair)

    p = add("seam", help="record whether an element runs across the gap BEFORE "
            "this page, writing @part on this page's first top-level element and "
            "the previous page's last. The page after the gap writes both ends, "
            "because it is the only one holding both witnesses. Preview unless "
            "--commit")
    # No `--all`: `--continues`/`--fresh` is an assertion about *this* seam, and a
    # corpus-wide "everything continues" is not a claim anyone could mean.
    refs_arg(p, extra=" — each the page AFTER its gap, e.g. 1-100 for the "
                      "1-099/1-100 seam")
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


def _collated(root: Path) -> list[str]:
    """Every ref with a committed TEI page. `corpus-header.xml` drops out of its
    own accord — its stem is not a ref, and `_refs_under` skips what will not
    parse. A store rather than a farm, so an empty `tei/` answers empty."""
    from ..context import all_refs
    return all_refs(root, "tei")


def run_validate(a) -> int:
    # **The one action that does not pool**, because its payload is a rendered
    # report and prose does not tabulate. N reports, `# REF` separated — the shape
    # `ocr review` used to have and gave up once its payload turned out to be
    # records after all. Exit is the worst across refs.
    refs = page_refs(a) or _collated(a.root)
    worst = 0
    for r in refs:
        if len(refs) > 1:
            section(a, r)
        ctx = build_context(r, a.root)
        worst = max(worst, _render_gate(a, validate(Path(ctx["output_path"]), ctx,
                                                    ratified=a.ratified)))
    return worst


def run_header(a) -> int:
    return _render_gate(a, check_corpus_header(a.root))


def run_state(a) -> int:
    out_per_ref(a, [(r, entry_state(r, a.root)) for r in page_refs(a)])
    return 0


def _write_all(a, fn) -> int:
    """`ids` and `pair`: the same shape, and the same up-front rule as `restore`.

    With more than one ref and `--commit`, every page is previewed first — both
    report what they would change without writing — so a page that cannot be
    repaired does not arrive with earlier pages already rewritten.
    """
    refs = page_refs(a) or _collated(a.root)
    if a.commit and len(refs) > 1:
        for r in refs:
            fn(r, a.root, commit=False)
    out_per_ref(a, [(r, fn(r, a.root, commit=a.commit)) for r in refs])
    return 0


def run_ids(a) -> int:
    return _write_all(a, fix_ids)


def run_pair(a) -> int:
    return _write_all(a, pair_glosses)


def run_seam(a) -> int:
    refs = page_refs(a)
    if a.commit and len(refs) > 1:
        for r in refs:
            set_seam(r, a.open_gap, a.root, commit=False)
    out_per_ref(a, [(r, set_seam(r, a.open_gap, a.root, commit=a.commit))
                           for r in refs])
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
