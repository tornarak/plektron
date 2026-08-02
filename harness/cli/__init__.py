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
import argparse
import sys
from pathlib import Path

from . import _corpus, _find, _lexicon, _ocr, _proposal, _tei, _views, _zones
from ._common import check_renamed, die_renamed, globals_parser, walk_surface

GROUPS = (_tei, _ocr, _proposal, _zones, _lexicon, _find, _corpus, _views)


def build_parser() -> argparse.ArgumentParser:
    """The whole two-tier parser. Separate from `main` so the surface test can
    walk it without running anything."""
    ap = argparse.ArgumentParser(
        prog="harness", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."),
                    help="repo root; every path resolves against it (default .)")
    ap.add_argument("--json", action="store_true",
                    help="indented JSON instead of TOON")

    common = globals_parser()
    sub = ap.add_subparsers(dest="group", required=True, metavar="GROUP")
    for mod in GROUPS:
        mod.register(sub, common)
    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = build_parser()

    # The rename trap runs before parsing, so a retired spelling gets told where
    # its command went rather than `invalid choice` or `unrecognized arguments`.
    # It is handed the parser's own surface — action names *and* each action's
    # real flags — because both are needed to tell an old form from a new one:
    # `--ink` is a retired `zones` flag and a live `zones check` flag, while
    # `--from` is retired under a live `ocr lines`. Skipped when the user is
    # asking for help, which is the one case where the listing itself answers.
    if not any(t in ("-h", "--help") for t in argv):
        new = check_renamed(argv, walk_surface(ap))
        if new:
            return die_renamed(new)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, FileNotFoundError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
