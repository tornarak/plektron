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

from ..render import mode, render


def globals_parser() -> argparse.ArgumentParser:
    """The `--root`/`--json`/`--toon` parent, one instance per registration pass."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS,
                        help=argparse.SUPPRESS)
    add_output_flags(common)
    return common


def add_output_flags(p):
    """`--json`/`--toon`, mutually exclusive, on the top-level parser and on every action.

    **Exclusive at the parser rather than by precedence in `mode()`.** "Argument
    validation is argparse's, not an if-chain's" is a stated convention here, and
    a silently-preferred flag is what the one-tier CLI was retired for — `--marks
    --native` used to run `--marks`.

    Both default to `SUPPRESS` for the reason `_common`'s docstring gives: they are
    declared twice so they may be typed on either side of the verb, and without
    SUPPRESS the action parser's default would overwrite a value given before it.
    """
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="indented JSON instead of TOON")
    g.add_argument("--toon", action="store_true", default=argparse.SUPPRESS,
                   help="TOON even at a terminal, where an aligned table is the "
                        "default — what a skill's model sees, reproduced by hand")
    return p


def out(a, obj) -> None:
    """Emit one section. Aligned table at a terminal, TOON down a pipe, JSON under `--json`.

    A verb emitting several sections calls this several times, deliberately: TOON
    collapses a uniform record list to a header row plus data rows, and a ragged
    key set degrades it to the verbose nested form. Two key sets, two tables.

    The mode is `render.mode(a)` and is decided per invocation, not per section, so
    a verb cannot emit a table and then a TOON block. Which one it is has exactly
    one input beyond the two flags — `sys.stdout.isatty()`.
    """
    print(render(obj, mode(a)))


def section(a, name: str) -> None:
    """The label above a verb's second and subsequent sections.

    A literal `# name` line in TOON and JSON mode, unchanged, because it is what
    anything grepping this output already matches on. At a terminal it becomes a
    rule, since a table already has a header row and a second bare `#` line above
    it reads as part of the data.
    """
    if mode(a) != "table":
        print(f"# {name}")
        return
    from ..render import rule
    print(rule(name))


REF_HELP = "page ref: part and scan index, e.g. 1-048"

ALL_HELP = ("Required for a corpus-wide run: naming nothing is a usage error "
            "rather than a silent sweep, because the cost of a sweep should be "
            "at the call site and not inferred from an omission")


def add_all(p, what: str):
    """`--all`, whose help states *what it enumerates* rather than "everything".

    The parameter is mandatory for that reason. "Every page" is four different
    sets in this repo — the 832 scans, the pages with zones, the pages a store
    holds, the review directories — and which one a sweep walks is the whole
    content of the flag.
    """
    p.add_argument("--all", action="store_true", help=f"{what}. {ALL_HELP}")
    return p


JOBS_HELP = ("worker threads for the per-page raster work; 1 runs serially and "
             "builds no pool [cores, capped]")


def add_jobs(p):
    """`--jobs N`, on the actions whose per-page cost is a raster decode.

    **Declared per-action rather than on the globals parser**, because a flag that
    is accepted where it does nothing is a wrong combination argparse should be
    rejecting, and it is dead surface in the VERBS.md gate besides — the same
    argument that retired `MainZone-Quote` from the store's label set.

    `--jobs 1` is the control arm, not a debug switch: the claim these verbs rest
    on is that concurrency moves wall clock and nothing else, and saying so means
    running both sides and diffing the output.
    """
    p.add_argument("--jobs", type=int, default=None, metavar="N", help=JOBS_HELP)
    return p


def refs_arg(p, *, all_: str | None = None, extra: str = ""):
    """The `PP-NNN [PP-NNN ...]` positional, plus `--all` where there is a corpus form.

    `nargs` is `+` when the action must name pages and `*` when `--all` is the
    other way to say what to work on. There is deliberately no third case: a bare
    `*` with no `--all` would be a sweep spelled as an omission, which is what
    this replaced.
    """
    p.add_argument("ref", metavar="PP-NNN", nargs="*" if all_ else "+",
                   help=REF_HELP + ". Several may be given" + extra)
    if all_:
        add_all(p, all_)
    return p


def page_refs(a) -> list[str]:
    """The refs this invocation names, normalized — `[]` when it named `--all`.

    **Every ref is parsed before the caller does any work**, which is the whole
    point of routing through here: `ocr review` already checked all its refs
    before emitting anything (a refusal arriving after pages of reassuring output
    is worse than no check), and a write verb has the sharper version of the same
    problem — a typo in the fifth ref must not leave four pages written.

    It also holds the three-way exclusion. Refs, `--all` and `--itinerary` are
    three ways of naming a work-list and exactly one may be used, so a caller
    cannot silently prefer one over another; and an action that has `--all` and
    was given none of the three is a usage error rather than a sweep.

    Returning `[]` for `--all` is safe only because of that error: an empty list
    out of here means the corpus was asked for, never that nothing was named.
    """
    from ..context import norm_ref

    refs = getattr(a, "ref", None)
    refs = [refs] if isinstance(refs, str) else list(refs or [])
    given = [name for name, v in (("refs", refs),
                                  ("--all", getattr(a, "all", False)),
                                  ("--itinerary", getattr(a, "itinerary", None)))
             if v]
    if len(given) > 1:
        raise ValueError(
            f"{' and '.join(given)}: refs, --all and --itinerary are three ways "
            "of naming a work-list, and exactly one may be used")
    if not given and hasattr(a, "all"):
        raise ValueError("nothing named: give one or more PP-NNN refs, or --all "
                         "for the whole corpus")
    return [norm_ref(r) for r in refs]


def one_page_only(a, flags: dict[str, str], refs: list[str]) -> None:
    """Refuse a flag that names something only one page has, given several refs.

    A plural positional silently widens every flag beside it, and some of them
    name a thing that exists per page: `--only` is that page's line indices,
    `--out` is one directory that N pages of images would collide in, `--path` is
    one file. Refusing is the point — `--out` in particular had no error at all,
    the second page simply overwrote the first's sheets.

    `flags` maps the attribute name to the spelling to print.
    """
    if len(refs) <= 1:
        return
    for attr, spelling in flags.items():
        if getattr(a, attr, None):
            raise ValueError(f"{spelling} names one page's own — give one ref, "
                             f"not {len(refs)}")


def out_per_ref(a, pairs) -> None:
    """Emit one payload per ref: as-is for one, pooled with a `ref` column for N.

    One ref emits exactly what the single-ref form always emitted, so every
    example in VERBS.md and in the skills stays literally correct; several pool
    into one table whose first field is `ref`. That is the shape `emit`'s own
    docstring argues for — a list of records carrying `ref` as a field rather
    than a dict keyed by ref — and it is what `proposal marks` already does.

    **A list-valued field is split out, not pooled into the row.** TOON collapses
    a uniform record list to a header and rows, but a record holding a nested list
    degrades the *whole outer table* to the verbose form, so one page's `edits`
    would cost the pooled table its shape. Instead the row carries each list's
    **length** and every non-empty list becomes its own ref-keyed table under a
    `# field` line. A count is not a summary standing in for the detail — the
    detail follows, keyed by ref, so nothing is lost and the row stays scannable.
    Two key sets, two tables, which is the rule `out` states.

    **This used to raise instead**, on the reasoning that a caller should be made
    to think about the shape rather than have it chosen for them. That was the
    wrong trade: the split is exactly what the thinking caller writes, so refusing
    bought nothing and left every plural verb whose payload happened to hold a
    list broken until someone ran it with two refs. `ocr clean` was found that
    way, in use, after its tests passed — the guard fired correctly and the bug
    was that there was anything for it to fire on.

    **`--all` always pools, even where it happened to match one page.** The shape
    a caller gets should follow what it asked for, not what the store happened to
    contain — a sweep whose output changed schema on the day the corpus held one
    matching page would be a trap with a long fuse.

    **The field set is decided over every payload, never the first.** It used to be
    read off `pairs[0]`, so a field absent from page one and a list on page five
    reached `_pool` unsplit and tripped its guard — after all the work was done.

    **A list *inside* a record of a list-valued payload is not handled here, on
    purpose.** Where a payload is already one row per finding, a list in a cell is
    the verb emitting a shape that is not a table, and `_pool`'s guard firing is the
    correct outcome rather than something to absorb. `proposal check` was found that
    way and fixed at the source, by giving its six detectors one key set — which is
    the rule `emit`'s own docstring states and the detectors already follow.
    """
    if len(pairs) == 1 and not getattr(a, "all", False):
        out(a, pairs[0][1])
        return
    if not pairs:
        out(a, [])
        return

    # An **ordered** set, so the `# field` blocks below follow the record's own
    # field order rather than a set's iteration order — which Python randomises per
    # process for strings. CLAUDE.md records the same hazard for `--resize`'s class
    # map, where it permuted every label; here it shuffled sub-tables between runs
    # of one unchanged command.
    listy: dict[str, None] = {}
    for _, rep in pairs:
        if isinstance(rep, dict):
            for k, v in rep.items():
                if isinstance(v, list):
                    listy.setdefault(k)
    if not listy:
        _pool(a, pairs)
        return

    # **Which treatment a list field gets is decided per field over every page,
    # never per cell.** A list of **records** becomes a count, the records
    # following in their own table; a list of **scalars** is space-joined into the
    # cell — the convention `corrections`' `pages` and `marks`' `refs` already use,
    # since a table of one bare column is worse than a string. An *empty* list
    # cannot say which it is, so a per-cell rule would print `errors: ""` beside
    # `warnings: 1` in the same row and make the column mean two things.
    tabular = [k for k in listy
               if any(rep.get(k) and isinstance(rep[k][0], dict)
                      for _, rep in pairs)]

    def _cell(key, v):
        if key not in listy:
            return v
        return len(v) if key in tabular else " ".join(map(str, v))

    _pool(a, [(r, {k: _cell(k, v) for k, v in rep.items()}) for r, rep in pairs])
    for key in tabular:
        found = [(r, rep[key]) for r, rep in pairs if rep.get(key)]
        if found:
            section(a, key)
            # **Pooled even when one page contributed.** At the top level the count
            # decides the shape because the caller named one page; here the caller
            # named several and these rows are a *subset* of them, so dropping the
            # `ref` column would leave a table whose rows belong to a page it does
            # not name — findable only by elimination.
            _pool(a, found)


def _pool(a, pairs) -> None:
    """Flatten `[(ref, payload)]` into one table with `ref` first, unconditionally."""
    rows = []
    for ref, payload in pairs:
        for item in (payload if isinstance(payload, list) else [payload]):
            for k, v in item.items():
                if isinstance(v, list):
                    raise ValueError(
                        f"cannot pool {ref}: field {k!r} is a list, which would "
                        "degrade the table — emit it as its own ref-keyed table")
            rows.append({"ref": ref, **item})
    out(a, rows)


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
    # The one action whose ref was a flag. Every other action in the CLI names a
    # page positionally, and once they all took several it was the odd one out
    # rather than the concise one.
    ("ocr", "--ref"): "ocr corrections PP-NNN [PP-NNN ...]  (or --all)",
    # `--from DIR` across the whole `ocr` group became `--store gt|mz`, the same
    # closed set `zones` has had, once `mz/ocr/` gave the group a second real
    # store. It was never used as a free path — only ever `gt/ocr`, `mz/ocr` or
    # the view — so nothing was given up, and the view stopped being nameable,
    # which is the point.
    # `{action}` is filled in from what was actually typed. A group-wide flag
    # rename has no single action to name, and the alternative — picking one as an
    # exemplar — points the reader at a command they did not run.
    ("ocr", "--from"): "ocr {action} --store gt|mz (omit for the ocr/ view)",
    ("lexicon", "--native"): "lexicon native",
    ("lexicon", "--marks"): "lexicon marks",
    ("lexicon", "--suffixes"): "lexicon suffixes",
    ("lexicon", "--digraphs"): "lexicon digraphs",
    ("lexicon", "--glosses"): "lexicon glosses",
    # A required *file* argument spelled as a flag was the smell that prompted the
    # plural pass; the scope is now a positional taking refs and paths alike.
    ("corpus", "--path"): "corpus normalize REF|PATH [REF|PATH ...]  (or --all)",
    # `--all` is a real flag on `tei validate`, `ids` and `pair`, and
    # `check_renamed` skips a flag the named action genuinely has — so this fires
    # only on the three that do not, and the message must read sensibly for all
    # of them, which is why it names the corpus form rather than a substitute.
    ("tei", "--all"): "tei ledger  (the corpus form of `state`; `context` and "
                      "`seam` have none by design)",
}

# Retired *positional values*, keyed by group and value. The flag table cannot
# reach these: `check_renamed` scans tokens beginning with `-`, and `all` was a
# `choices=` value of `views`' FARM positional. One entry today, and it needs the
# table rather than a special case because a bare `invalid choice: 'all'` names
# the problem and not the fix.
RENAMED_VALUES = {
    ("views", "all"): "views {action} --all",
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


def walk_positionals(parser) -> dict[tuple[str, str], dict[str, object]]:
    """`{(group, action): {positional name: nargs}}` for the whole parser.

    A separate walk from `walk_surface` because that one collects
    `option_strings` and a positional has none — deliberately, since the VERBS.md
    gate is about flags and pinning a metavar there would be a style gate wearing
    a correctness gate's clothes. What *is* a correctness question is whether a
    ref positional is plural, and only this sees it.

    `nargs` is `None` for a plain single-value positional, which is what argparse
    stores; the gate reads that as "singular" rather than special-casing it.
    """
    surface = {}
    for group_act in parser._subparsers._group_actions:
        for gname, gparser in group_act.choices.items():
            for act_act in gparser._subparsers._group_actions:
                for aname, aparser in act_act.choices.items():
                    surface[(gname, aname)] = {
                        act.dest: act.nargs for act in aparser._actions
                        if not act.option_strings}
    return surface


def check_renamed(argv: list[str], surface: dict[tuple[str, str], set[str]]
                  ) -> str | None:
    """The new spelling for a retired one, or None if nothing matched.

    Runs before argparse, so a retired spelling never reaches the `invalid choice`
    or `unrecognized arguments` path. Only the first match is reported: someone
    typing two retired flags wants to be told where the command went, not given a
    list.

    **A retired flag is reported even when a live action was named, but only if it
    is not a flag of that action** — and that qualification is the whole
    subtlety. `--ink` and `--lines` are retired spellings under `zones` *and* live
    flags of `zones check`, so a trap that scanned unconditionally would reject
    `zones check --ink`, the correct new form, and tell the user to type what they
    had just typed.

    It used to skip the flag table entirely once an action was named, which was
    the cheap way to get that right and gave up the case that matters more as the
    CLI ages: a flag retired *within* a surviving action. `ocr lines --from` is
    exactly that — the action is right, the flag is not — and under the old rule
    it fell through to argparse's bare "unrecognized arguments: --from", which
    names the problem and not the fix. Asking the parser itself which flags an
    action really has is what makes the narrow test possible.

    **Positional values get the same treatment**, through `RENAMED_VALUES`. A
    retired `choices=` value is invisible to the flag scan, which only looks at
    tokens beginning with `-`, and argparse's own `invalid choice: 'all'` names
    the problem without the fix — the same gap the flag table exists to close.
    Only tokens after the action are considered, so a group or action that
    happened to share the word is not caught by accident.
    """
    if not argv:
        return None
    head = argv[0]
    if head in RENAMED_VERBS:
        return RENAMED_VERBS[head]
    actions = {a for (g, a) in surface if g == head}
    named = argv[1] if len(argv) > 1 and argv[1] in actions else None
    live = surface.get((head, named), set()) if named else set()
    for tok in argv[1:]:
        if not tok.startswith("-"):
            if named and tok != named and (head, tok) in RENAMED_VALUES:
                return RENAMED_VALUES[(head, tok)].format(action=named)
            continue
        flag = tok.split("=", 1)[0]
        if flag in live:
            continue
        if (head, flag) in RENAMED_FLAGS:
            return RENAMED_FLAGS[(head, flag)].format(action=named or "<action>")
    return None


def die_renamed(new: str) -> int:
    print(f"That spelling is gone. This is now:\n\n    harness {new}\n\n"
          "The verbs are two-tier since the reorganization: a group "
          "(tei/ocr/proposal/zones/lexicon/find/corpus) then an action. "
          "`harness --help`, or harness/VERBS.md for the full reference.",
          file=sys.stderr)
    return 2
