"""Shared CLI machinery: the globals parser, the emitter, and the rename trap.

Three things live here because every group module needs them and none owns them.

**`common` is attached to every *action* parser, not to the group parsers.**
`--root`/`--json` are declared on the top-level parser so they may be typed
before the verb, and again here so they may be typed after it — which is where a
hand puts them. With two tiers of subparsers the *last* parser to run is the
action's, so `harness zones predict --json` only parses if `predict` itself
carries them. `argparse.SUPPRESS` is what makes the double declaration safe:
without it the subparser's own default would overwrite a value given earlier on
the line.

**The rename trap** exists because this CLI went from one tier to two in a hard
cutover, with no aliases. Nothing mechanical calls the harness — no test, no
script — so the consumers are documents: this repo's CLAUDE.md, three skills,
and a human's memory. argparse's own error for a retired spelling is
`invalid choice` or `unrecognized arguments`, neither of which says where the
thing went. These two tables do.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from ..emit import emit


def globals_parser() -> argparse.ArgumentParser:
    """The `--root`/`--json` parent, one instance per registration pass."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS,
                        help=argparse.SUPPRESS)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="indented JSON instead of TOON")
    return common


def out(a, obj) -> None:
    """Emit one table. TOON by default, indented JSON under `--json`.

    A verb emitting several tables calls this several times, deliberately: TOON
    collapses a uniform record list to a header row plus data rows, and a ragged
    key set degrades it to the verbose nested form. Two key sets, two tables.
    """
    print(emit(obj, getattr(a, "json", False)))


# Retired tier-1 verbs -> where each went. Keys are what `argv[1]` used to be.
RENAMED_VERBS = {
    "context": "tei context REF",
    "validate": "tei validate REF",
    "state": "tei state REF",
    "ids": "tei ids REF  (or `tei pair REF`, which was --pair)",
    "seam": "tei seam REF --continues|--fresh",
    "header": "tei header",
    "ledger": "tei ledger",
    "pages": "ocr pages",
    "lines": "ocr lines REF  (--gaps/--crops/--sheets/--blot/--adopt-gap are "
             "now `ocr gaps`/`ocr crops`/`ocr sheets`/`ocr blot`/`ocr adopt-gap`)",
    "zoom": "ocr zoom REF",
    "review": "ocr review REF",
    "restore": "ocr restore REF",
    "clean": "ocr clean REF",
    "proposal-check": "proposal check REF  (--fix/--codepoints/--set/--replace "
                      "are now `proposal fix`/`codepoints`/`set`/`replace`)",
    "toc-search": "find toc QUERY",
    "toc-near": "find folio N",
    "authority": "find authority QUERY",
    "figures": "corpus figures",
    "normalize": "corpus normalize  (--convert is now --commit)",
}

# Retired flag spellings under a group name that survived. Keyed by the group,
# because `--blot` is a live flag nowhere and an action in two places.
RENAMED_FLAGS = {
    ("zones", "--serve"): "zones edit [REF]",
    ("zones", "--predict"): "zones predict [REF]",
    ("zones", "--score"): "zones score",
    ("zones", "--assemble"): "zones assemble",
    ("zones", "--install"): "zones install CHECKPOINT",
    ("zones", "--remap-model"): "zones remap",
    ("zones", "--remark-eval"): "zones remark-eval FRACTION",
    ("zones", "--delete"): "zones delete REF",
    ("zones", "--diff"): "zones diff [REF]",
    ("zones", "--paragraphs"): "zones paragraphs [REF]",
    ("zones", "--link"): "zones link",
    ("zones", "--blot"): "zones blot [REF]",
    ("zones", "--ink"): "zones check --ink",
    ("zones", "--lines"): "zones check --lines",
    ("zones", "--from"): "zones check --store gt|mz",
    ("lexicon", "--native"): "lexicon native",
    ("lexicon", "--marks"): "lexicon marks",
    ("lexicon", "--suffixes"): "lexicon suffixes",
    ("lexicon", "--digraphs"): "lexicon digraphs",
    ("lexicon", "--glosses"): "lexicon glosses",
}


def walk_surface(parser) -> dict[tuple[str, str], set[str]]:
    """`{(group, action): {flags}}` for the whole two-tier parser.

    One walk, two consumers: the rename trap needs the action names to tell an
    old spelling from a new one, and the VERBS.md gate test needs the flags too.
    Deriving both from the real parser is the point — a second hand-maintained
    list of actions would be one more pair of files holding one fact.
    """
    surface = {}
    for group_act in parser._subparsers._group_actions:
        for gname, gparser in group_act.choices.items():
            for act_act in gparser._subparsers._group_actions:
                for aname, aparser in act_act.choices.items():
                    flags = set()
                    for act in aparser._actions:
                        flags.update(o for o in act.option_strings
                                     if o.startswith("--") and o != "--help")
                    surface[(gname, aname)] = flags
    return surface


def check_renamed(argv: list[str], actions: dict[str, set[str]]) -> str | None:
    """The new spelling for a retired one, or None if nothing matched.

    Runs before argparse, so a retired verb never reaches the `invalid choice`
    path. Only the first match is reported: someone typing two retired flags
    wants to be told where the command went, not given a list.

    **The flag table is consulted only when no action was named**, and that
    condition is load-bearing rather than an optimization. `--ink` and `--lines`
    are retired spellings under `zones` *and* live flags of `zones check`, so a
    trap that scanned regardless would reject `zones check --ink` — the correct
    new form — and tell the user to type what they had just typed. Old-form
    commands are `harness GROUP [REF] --flag`, so the tell is that the token
    after the group is a flag, or a ref, or absent: anything but an action name.
    """
    if not argv:
        return None
    head = argv[0]
    if head in RENAMED_VERBS:
        return RENAMED_VERBS[head]
    if len(argv) > 1 and argv[1] in actions.get(head, ()):
        return None
    for tok in argv[1:]:
        if not tok.startswith("-"):
            continue
        flag = tok.split("=", 1)[0]
        if (head, flag) in RENAMED_FLAGS:
            return RENAMED_FLAGS[(head, flag)]
    return None


def die_renamed(new: str) -> int:
    print(f"That spelling is gone. This is now:\n\n    harness {new}\n\n"
          "The verbs are two-tier since the reorganization: a group "
          "(tei/ocr/proposal/zones/lexicon/find/corpus) then an action. "
          "`harness --help`, or harness/VERBS.md for the full reference.",
          file=sys.stderr)
    return 2
