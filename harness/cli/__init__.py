"""CLI entry: the verbs the model and the editor call from Claude Code.

**Two tiers: a group, then an action.** The group names what the command
touches, the action names what it does to it:

    tei       the TEI store — context, validate, ids, pair, seam, state,
              ledger, header
    ocr       the ALTO stores and the correction loop — pages, lines, gaps,
              adopt-gap, crops, sheets, zoom, blot, review, restore, clean
    proposal  review/PP-NNN/proposal.json — check, fix, codepoints, set, replace
    zones     the page segmentation and its segmenter — check, edit, predict,
              score, assemble, install, remap, remark-eval, delete, diff,
              paragraphs, link, blot
    lexicon   frequency reports and the gloss dictionary — misses, native,
              marks, suffixes, digraphs, glosses
    find      apparatus lookups — toc, folio, authority
    corpus    whole-corpus gates — normalize, figures
    views     the derived trees git does not carry — check, build
    agents    a dispatched batch's cache telemetry — usage

It was one tier for most of this project's life, and grew to 21 verbs whose
flags formed subcommands nobody had named: `zones` alone carried 21 of them,
selected by if-chain precedence, so a wrong combination was silently ignored
rather than rejected. The full reference — what each action reads, what it
writes, and what its exit code means — is `harness/VERBS.md`, and a test holds
that file and this parser together, because two files holding one fact with
nothing between them is how the old surface drifted unnoticed.

Pages are addressed by **PP-NNN** ref — part, and scan index within that part —
never by a bare page number. The printed folio is not derivable from the scan
index (see context.py), so a bare integer would silently name the wrong page.

Four conventions hold across every group:

  - **Report by default; `--commit` writes.** It is the only write-enable, and
    it gates exactly the authored stores (`gt/`, `tei/`, `models/`, the split
    and exemption sidecars). Derived output — crops, sheets, zoom, blots, `mz/`
    predictions, the `zones/` view — writes on invocation, because there the
    write *is* the action and the same command rebuilds it.
  - **Exit 0 clean, 1 a documented gate failed, 2 usage error.** Measurement
    never gates: `zones check --store mz`, `zones score`, `zones diff`,
    `zones paragraphs`, and everything under `find` and `lexicon` always exit 0.
  - **One meaning per flag name.** `--store gt|mz` names one of a group's two
    real stores — a closed set, never a free path, and never the read view,
    which is what omitting it selects; `--force` overwrites existing output;
    `--out` redirects a write.
  - **`--json` swaps the serializer, not the payload** — except on `tei
    validate` and `tei header`, where it swaps a rendered human report for the
    structured verdict. The exit code is the contract either way.

Output is TOON (see emit.py): a tabular encoding that collapses a uniform record
list to a header row plus data rows. Anything emitting a list of records keeps
one fixed key set across them, because a ragged list degrades to the verbose
nested form — which is also why several actions print two tables rather than one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import cloup

from . import (
    _agents,
    _corpus,
    _find,
    _lexicon,
    _ocr,
    _proposal,
    _tei,
    _views,
    _zones,
)
from ._common import (
    CONTEXT,
    _actions,
    _Group,
    check_renamed,
    die_renamed,
    exclusive,
    globals_params,
    seal,
    walk_surface,
)

GROUPS = (_tei, _ocr, _proposal, _zones, _lexicon, _find, _corpus, _views, _agents)


def build_parser() -> click.Group:
    """The whole two-tier command tree. Separate from `main` so the surface test
    can walk it without running anything.

    **`invoke_without_command` plus an explicit refusal**, rather than click's
    `no_args_is_help`. That prints help and exits 0, where argparse exits 2 for a
    missing required subcommand — and a bare `harness` that looks successful is a
    script's silent no-op. `UsageError` restores the 2.
    """
    @click.pass_context
    def root(ctx, **_):
        if ctx.invoked_subcommand is None:
            raise click.UsageError("name a group, then an action", ctx)

    cli = _Group("harness", help=__doc__, callback=root,
                      context_settings=CONTEXT,
                      params=globals_params(root_default=Path(".")),
                      constraints=[exclusive("json", "toon")],
                      invoke_without_command=True, no_args_is_help=False)
    # **The three sections are the ones this repo's own docs already draw.** A
    # heading invented here would teach a reader a distinction the code does not
    # make, which is worse than an alphabetical list.
    for title in ("The passes", "Apparatus and reports", "Whole-corpus"):
        cli.add_section(cloup.Section(title))
    for mod in GROUPS:
        mod.register(cli)
    # Constraints name parameters that only exist once every `opt`/`arg` has run,
    # so they are bound here rather than at construction. One walk, so an action
    # cannot be declared without them.
    for cmd in _actions(cli).values():
        seal(cmd)
    return _with_tui(cli)


def _with_tui(cli: click.Group) -> click.Group:
    """`harness tui`, if `trogon` happens to be installed.

    A form-filling terminal UI over the whole command tree, built by introspecting
    it — verified to walk this one, options, arguments and choices included. It is
    **not** a declared dependency: it pulls `textual`, which is a lot of weight for
    a convenience, and it has not had a release since 2024-10. Guarded rather than
    required, so `uv run --with trogon harness tui` is the whole cost of trying it
    and nothing changes for anyone who does not.
    """
    try:
        from trogon import tui
    except ImportError:
        return cli
    return tui(help="explore the whole command tree in a terminal UI")(cli)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cli = build_parser()

    # The rename trap runs before parsing, so a retired spelling gets told where
    # its command went rather than `No such command` or `no such option`. It is
    # handed the tree's own surface — action names *and* each action's real flags —
    # because both are needed to tell an old form from a new one: `--ink` is a
    # retired `zones` flag and a live `zones check` flag, while `--from` is retired
    # under a live `ocr lines`. Skipped when the user is asking for help, which is
    # the one case where the listing itself answers.
    if not any(t in ("-h", "--help") for t in argv):
        new = check_renamed(argv, walk_surface(cli))
        if new:
            return die_renamed(new)

    try:
        # `standalone_mode=False` so a command's return value reaches us as the
        # exit code and click does not call `sys.exit` out from under the caller —
        # `main` is a function the tests drive directly, not only a console script.
        # The pager and the `--json` flush live in the per-action callback rather
        # than here, since that is where the parsed namespace exists.
        return cli.main(argv, prog_name="harness", standalone_mode=False) or 0
    except click.ClickException as e:
        e.show()
        return e.exit_code
    except click.exceptions.Exit as e:
        # `--help` and `--version` land here, having already printed.
        return e.exit_code
    except click.exceptions.Abort:
        print("Aborted.", file=sys.stderr)
        return 1
    except (ValueError, FileNotFoundError, KeyError, OSError) as e:
        # `OSError` covers the parsers, which raise it rather than
        # `FileNotFoundError` for a missing file — `etree.parse` on an absent ALTO
        # is the common one. It reached the user as a twenty-line traceback while
        # every action named one page; naming several makes a mid-list absence
        # ordinary, and a traceback there says nothing a message could not.
        #
        # Notes are printed because that is where the *page* is. `parallel.pmap`
        # attaches the item it was working on rather than re-raising a new
        # exception, so that these four `except` clauses still catch what they were
        # written for; dropping the note here would throw away the half of the
        # message that says which of 832 pages failed.
        note = "; ".join(getattr(e, "__notes__", ()) or ())
        print(f"ERROR: {e}{f' ({note})' if note else ''}", file=sys.stderr)
        return 2
