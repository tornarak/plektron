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
from ..expand import expand_page
from ..generate import Unready, generate
from ..generate import diff as gen_diff
from ..ids import fix_page as fix_ids
from ..ids import pair_glosses
from ..render import mode, report, rule
from ..seam import set_seam
from ..state import build_ledger, entry_state, ledger_rows
from ..validate import check_corpus_header, validate
from ._common import (
    REF_HELP,
    action,
    arg,
    group,
    opt,
    out,
    out_per_ref,
    page_refs,
    refs_arg,
    require_exactly_one,
)


def register(cli):
    g = group(cli, "tei", "the TEI store: the collation pass's input "
              "contract, the gates on its output, structural ids, and "
              "the seam state folded out of the committed files",
              sections=("The collation pass", "Dispatch", "Structure",
                        "Seam state"), section="The passes")

    p = action(g, "context", run_context, section="The collation pass",
               help="the whole per-page input contract for the collation "
               "pass, on stdout — seam state, ToC neighbourhood, figure zones and "
               "their captions, OCR line ids, detector flags. Deterministic and "
               f"precomputed: the pass consumes this and never re-derives it"
               f"\n\nPP-NNN: {REF_HELP}.")
    # **Singular, and one of only four in the CLI.** The payload is one page's
    # collation prompt, built to be handed to one model for one page; a merged
    # stream of them is not consumable by the thing it exists for.
    arg(p, "ref", metavar="PP-NNN")

    p = action(g, "generate", run_generate, section="The collation pass",
               help="build a first-draft TEI page from gt/zones/ and gt/ocr/ into "
               "mz/tei/ — paragraph boundaries off the keyed zone labels, the folio "
               "off the running title, the apparatus dropped, every judgement left "
               "as a comment naming itself. What the collation pass reviews; it "
               "authors nothing the stores already hold")
    refs_arg(p, all_="every page holding both gt/ocr/ and gt/zones/")
    opt(p, "--force", is_flag=True,
        help="replace a baseline that already exists. Off by default because a "
             "baseline a collator has copied is one half of `tei diff`, and moving "
             "it under a review in progress makes that comparison a lie")

    p = action(g, "diff", run_diff, section="The collation pass",
               help="what review changed — the generated baseline in mz/tei/ "
               "against the collated page in tei/. `gen_comments` is the count of "
               "generator questions still unanswered, and `drifted` says the "
               "baseline moved under the review, which makes every other column "
               "noise. Measurement: always exit 0")
    refs_arg(p, all_="every page holding a generated baseline")

    p = action(g, "validate", run_validate, section="The collation pass",
               help="the gate on a page's TEI. Exit 1 on FAIL. Checks "
               "the output contract, that every @facs resolves against a supplied "
               "zone or OCR line, and that every Tier-1 span carries a @resp rank — "
               "an unmarked span being indistinguishable from a ratified one to "
               "anything that does not look")
    refs_arg(p, all_="every collated page in tei/",
             extra=", each rendered as its own report under a `# REF` line — "
                   "prose does not pool, so this is the one action that does not")
    opt(p, "--ratified", is_flag=True,
        help="expect human-ratified provenance (resp='#ed') on Tier-1 "
             "spans instead of the collation pass's '#llm'; a "
             "remaining '#llm' becomes a worklist line")
    _schema_opt(p)

    p = action(g, "expand", run_expand, section="The collation pass",
               help="write ratified Tier-1 forms into a collated page. The "
               "pass names a native term by its handle in tier1_terms rather than "
               "retyping it, and this fills in the string a human adjudicated at "
               "the raster — the model chooses which token, never the glyphs. "
               "Only where gt/ocr/ holds the page. Preview unless --commit")
    refs_arg(p, all_="every collated page in tei/")
    opt(p, "--commit", is_flag=True,
        help="write the ratified forms; without it, report what would change")

    p = action(g, "state", run_state, section="Seam state",
               help="one page's seam record — the folio predicted for it, "
               "what that prediction rests on, and which headings are believed "
               "open. expected_folio is null wherever the chain of transcribed "
               "pages breaks, which means read it off the image, not that anything "
               "failed")
    # No `--all`: `tei ledger` *is* the corpus form of this, and a second
    # spelling of one report is how two answers to one question start to drift.
    refs_arg(p)

    p = action(g, "ids", run_ids, section="Structure",
               help="check one page's structural ids against the scheme "
               "{kind}-{PP-NNN}-{ordinal}, where the ordinal is the element's "
               "position among same-kind elements in document order — so every id "
               "is recomputable from the tree alone. --commit renumbers, repairing "
               "any inbound @prev/@next from a neighbour in the same write")
    refs_arg(p, all_="every collated page in tei/")
    opt(p, "--commit", is_flag=True,
        help="write the canonical ids (and neighbours' pointers); "
             "without it, report what would change")

    p = action(g, "pair", run_pair, section="Structure",
               help="link each <gloss> to its <term> where containment "
               "decides — one of each in a container. Where it does not (two pairs "
               "in one item), report and write nothing: choosing would be "
               "inference. --commit to write")
    refs_arg(p, all_="every collated page in tei/")
    opt(p, "--commit", is_flag=True,
        help="write the gloss->term links; without it, report what would change")

    p = action(g, "seam", run_seam, section="Seam state",
               constraints=(require_exactly_one("continues", "fresh"),),
               help="record whether an element runs across the gap BEFORE "
               "this page, writing @part on this page's first top-level element and "
               "the previous page's last. The page after the gap writes both ends, "
               "because it is the only one holding both witnesses. Preview unless "
               "--commit")
    # No `--all`: `--continues`/`--fresh` is an assertion about *this* seam, and a
    # corpus-wide "everything continues" is not a claim anyone could mean.
    refs_arg(p, extra=" — each the page AFTER its gap, e.g. 1-100 for the "
                      "1-099/1-100 seam")
    # **Two flags under a `require_one` constraint**, declared at the parser — see
    # the `constraints=` above. Click's own `--continues/--fresh` pair was tried
    # first and rejected: it makes giving *both* legal, last one wins, where
    # argparse's required mutually-exclusive group refused. Silently preferring one
    # of two contradictory assertions about a seam is precedence standing in for
    # rejection, and this verb writes *two* pages on the strength of the answer.
    opt(p, "--continues", is_flag=True,
        help="an element carries across: this page opens mid-element")
    opt(p, "--fresh", is_flag=True,
        help="clean break: this page opens a new element. Clears the "
             "claim on both sides if one was recorded")
    opt(p, "--commit", is_flag=True,
        help="write both files; without it, report what would change")

    p = action(g, "queue", run_queue, section="Dispatch",
               help="validate a batch of pages, write it to the collation "
               "claim queue, and print the one prompt every collator of the batch "
               "gets. That prompt names no page: each agent takes its own ref with "
               "`tei claim`, because identity of the first turn is what caches and a "
               "ref written into the prompt costs every sibling the shared context")
    refs_arg(p)
    opt(p, "--note", type=str, default=None,
        help="a sentence appended to every page block in this batch; "
             "per-page notes want separate queue calls")

    p = action(g, "claim", run_claim, section="Dispatch",
               help="take the next unclaimed ref off the collation queue "
               "and print that page's block. Takes no ref, which is the point — the "
               "page arrives from a tool result rather than from a prompt that would "
               "then differ between siblings. Exit 1 when the queue is out")

    p = action(g, "reconcile", run_reconcile, section="Dispatch",
               help="what the batch came back with — each ref collated, "
               "CLAIMED but with no TEI (an agent took the page and did not return), "
               "or unclaimed (nobody took it). The two misses have different causes "
               "and want different answers, so they are not one state")
    refs_arg(p)

    p = action(g, "reservations", run_reservations, section="Dispatch",
               help="the open questions a batch left in its pages, pooled "
               "and classified. Read the rows against each other: one page adrift is "
               "a page to re-read, all of them leaning the same way is the contract "
               "or the spec. Measurement — always exit 0")
    refs_arg(p, all_="every collated page in tei/")

    p = action(g, "ledger", run_ledger, section="Seam state",
               help="the seam table across every scan — folio, heading "
               "fold, and whether an element runs across the gap after each page. "
               "That last is read off the committed TEI's @part/@next, where "
               "`tei seam` puts it; 'unknown' means the page is not collated, not "
               "that it is closed")
    opt(p, "--part", type=int, default=None, help="restrict to one part")
    opt(p, "--untranscribed", is_flag=True,
        help="refs with no committed TEI — bare, one per line, to "
             "pipe into xargs; a JSON array under --json")

    p = action(g, "header", run_header, section="The collation pass",
               help="the gate on the corpus teiHeader — that it exists, "
               "and that the provenance ranks it declares are exactly the ones "
               "`tei validate` enforces on every page. Two files hold one fact; "
               "without this they can drift apart silently, because a page is a "
               "fragment and never resolves @resp locally. Exit 1 on FAIL")
    _schema_opt(p)


def _schema_opt(p) -> None:
    """`--schema/--no-schema`, on by default, on both TEI gates.

    **On by default**, because the point of a conformance check is that it is not
    the thing anyone remembers to run — an invented attribute that reaches a
    hundred pages before a sweep finds it is the cost this exists to avoid. The
    library functions default it *off* instead, so the test suite does not pay
    libxml2's ~17 s `tei_all` compile on every call.

    `--no-schema` is the escape for a tight loop, and it is a real one: the
    compile dominates, where validating a page afterwards is ~0.3 ms. So a corpus
    sweep pays it once and per-page it is 17 s against a collation that took
    minutes.
    """
    opt(p, "--schema/--no-schema", "schema", default=True,
        help="also check the file is conformant TEI, against the "
             "committed data/tei_all.rng. Catches what project rules cannot — an "
             "invented attribute, a value of the wrong datatype [on]")


def run_context(a) -> int:
    out(a, build_context(a.ref, a.root))
    return 0


def _render_gate(a, rep, name: str | None = None) -> int:
    """A Report's two faces. The default is the rendered text, because a human
    reads it to decide whether to commit; `--json` is for anything consuming the
    verdict as data. The exit code is the contract either way.

    `name` is the ref, and only when several were given: under `--json` this verb
    emits one section per page, so without it the document would be N objects on
    one stream with `# 1-100` comment lines between them — which is what it was,
    and what `json.load` refused."""
    if getattr(a, "json", False):
        out(a, {"ok": rep.ok, "errors": rep.errors, "warnings": rep.warnings,
                "worklist": rep.worklist, "metrics": rep.metrics}, name)
    else:
        if name:
            print(f"# {name}" if mode(a) == "toon" else rule(name))
        print(report(rep.render(), mode(a)))
    return 0 if rep.ok else 1


def _collated(root: Path) -> list[str]:
    """Every ref with a committed TEI page. `corpus-header.xml` drops out of its
    own accord — its stem is not a ref, and `_refs_under` skips what will not
    parse. A store rather than a farm, so an empty `tei/` answers empty."""
    from ..context import all_refs
    return all_refs(root, "tei")


def _generatable(root: Path) -> list[str]:
    """Every page holding both inputs. The intersection, not either store alone:
    a page with zones and no ground truth is not a page this can read, and one with
    ground truth and no zones has no paragraph boundaries to honour."""
    from ..context import all_refs
    return sorted(set(all_refs(root, "gt/ocr")) & set(all_refs(root, "gt/zones")))


def run_generate(a) -> int:
    """Report per ref. Never gates: a page it cannot build is `Unready` with the
    verb that fixes it, which is a worklist line and not a failure of this run."""
    rows = []
    for r in page_refs(a) or _generatable(a.root):
        try:
            rows.append(generate(r, a.root, force=a.force))
        except Unready as e:
            from ..generate import skipped
            rows.append(skipped(r, str(e)))
    out(a, rows)
    return 0


def run_diff(a) -> int:
    """An aggregate, like `zones diff`: refs scope the table rather than multiply
    it, and every row already carries `ref`."""
    from ..context import all_refs
    refs = page_refs(a) or all_refs(a.root, "mz/tei")
    out(a, [gen_diff(r, a.root) for r in refs])
    return 0


def run_validate(a) -> int:
    # **The one action that does not pool**, because its payload is a rendered
    # report and prose does not tabulate. N reports, `# REF` separated — the shape
    # `ocr review` used to have and gave up once its payload turned out to be
    # records after all. Exit is the worst across refs.
    refs = page_refs(a) or _collated(a.root)
    worst = 0
    for r in refs:
        ctx = build_context(r, a.root)
        # The page's own path, built here rather than read out of `ctx`. It used to
        # ride in the payload as `output_path`, which put a path the model never
        # needed into every collation prompt so that this one line could avoid
        # recomputing it.
        page = a.root / "tei" / f"chukchi-{ctx['page_ref']}.xml"
        worst = max(worst, _render_gate(a, validate(page, ctx,
                                                    ratified=a.ratified,
                                                    schema=a.schema),
                                        r if len(refs) > 1 else None))
    return worst


def run_header(a) -> int:
    return _render_gate(a, check_corpus_header(a.root, schema=a.schema))


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


def run_expand(a) -> int:
    return _write_all(a, expand_page)


def run_seam(a) -> int:
    # Exactly one of `--continues`/`--fresh` is the parser's business and is
    # declared there; by here one of them is set.
    a.open_gap = a.continues
    refs = page_refs(a)
    if a.commit and len(refs) > 1:
        for r in refs:
            set_seam(r, a.open_gap, a.root, commit=False)
    out_per_ref(a, [(r, set_seam(r, a.open_gap, a.root, commit=a.commit))
                           for r in refs])
    return 0


def run_queue(a) -> int:
    """Write the batch, print the one prompt, or refuse naming the fix.

    The prompt goes to stdout as plain text rather than through a table: it is prose
    meant to be handed to an agent whole, and a renderer that wrapped or truncated it
    would corrupt the one artifact this action exists to produce. Everything
    operational goes to stderr.
    """
    import click

    from ..dispatch import COLLATION, Unready, queue_refs
    try:
        rec = queue_refs(page_refs(a), a.root, note=a.note, track=COLLATION)
    except Unready as e:
        raise click.ClickException(str(e)) from None
    if getattr(a, "json", False):
        out(a, [rec])
        return 0
    click.echo(rec["prompt"])
    if rec["resynced"]:
        click.echo(
            f"\nthe collator's transcluded contract was out of date and has been "
            f"rewritten from {', '.join(rec['resynced'])}. The agent file is "
            "tracked; commit it.", err=True)
    click.echo(
        f"\n{len(rec['queued'])} queued: {', '.join(rec['queued'])}. Send that "
        "prompt unedited and identical to every collator, staggering the first "
        "launch about ten seconds. The seam is yours afterwards, not theirs.",
        err=True)
    return 0


def run_claim(a) -> int:
    """One ref off the queue, rendered. Exit 1 when there is nothing left.

    Exit 1 rather than an empty success: an agent handed a blank answer at exit 0 has
    been told nothing, and picking a page for itself is exactly what a silence
    invites.
    """
    import click

    from ..dispatch import COLLATION, claim
    rec = claim(a.root, COLLATION)
    if rec is None:
        click.echo(
            "nothing left to claim — the queue is empty or every ref on it is "
            "taken. Stop and say so; do not pick a page yourself.", err=True)
        return 1
    if getattr(a, "json", False):
        out(a, [rec])
    else:
        click.echo(rec["page_block"])
    return 0


def run_reconcile(a) -> int:
    import click

    from ..dispatch import COLLATION, reconcile
    rows = reconcile(page_refs(a), a.root, COLLATION)
    out(a, rows, name="refs")
    missing = [r for r in rows if r["state"] != COLLATION.done]
    if not missing:
        return 0
    # **Three ways to come back short, and they want different answers**, so the
    # summary names each rather than pooling them under "no TEI" — which stopped
    # being true the moment `claim` began writing the file. An `unedited` page has a
    # deliverable and no work in it, and telling its coordinator that nothing was
    # produced sends them looking for a missing file that is sitting right there.
    unedited = [r["ref"] for r in missing if r["state"] == COLLATION.unedited]
    held = [r["ref"] for r in missing
            if r["state"] == COLLATION.missing]
    parts = [f"{len(missing)} of {len(rows)} did not come back collated: "
             f"{', '.join(r['ref'] for r in missing)}."]
    if unedited:
        parts.append(
            f"{len(unedited)} byte-identical to the generated baseline "
            f"({', '.join(unedited)}) — claimed and never edited, so the collator "
            "died early or is still on its first turns.")
    if held:
        parts.append(
            f"{len(held)} claimed with no file at all ({', '.join(held)}) — check "
            "it is not simply still running, then decide whether to re-queue.")
    if not unedited and not held:
        parts.append("None is claimed, so the queue outran the collators or they "
                     "were never sent.")
    click.echo(" ".join(parts), err=True)
    return 1


def run_reservations(a) -> int:
    """Pooled, and always exit 0 — measurement never gates."""
    import click

    from ..reservations import page_reservations, unchecked
    refs = page_refs(a)
    rows = [row for ref in refs for row in page_reservations(ref, a.root)]
    out(a, rows, name="reservations")
    if not getattr(a, "json", False):
        for line in unchecked(refs, a.root):
            click.echo(f"\n{line}", err=True)
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
